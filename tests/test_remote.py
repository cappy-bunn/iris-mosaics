"""Tests for IDL script rendering and the remote runner's guard rails.

Nothing here touches filament; the ssh layer is stubbed.
"""

import pytest

from iris_mosaics import MosaicConfig, remote


@pytest.fixture
def cfg():
    return MosaicConfig.load("20240811")


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def test_render_prep1_substitutes_paths(cfg):
    script = remote.render("prep1", cfg)
    assert "/deep_mosaics/20240811/level_1/*.fits" in script
    assert "/deep_mosaics/20240811/level_11_plus_iris_prep_bg_sub" in script
    assert "{input_glob}" not in script and "{output_dir}" not in script


def test_render_prep1_keywords_match_the_runbook(cfg):
    script = remote.render("prep1", cfg)
    for kw in ("/noflat", "/nobad", "/nowarp", "/filter_fid"):
        assert kw in script
    # part 1 must NOT suppress the background subtraction -- that is its job
    assert "/noback" not in script
    # header_temps shifts things wildly and is deliberately unused
    assert "/header_temps" not in script


def test_render_prep2_keywords_match_the_runbook(cfg):
    script = remote.render("prep2", cfg)
    for kw in ("/nosat", "/nodark", "/noback", "/shift_wave", "/shift_fid",
               "/poly2d", "/filter_wave", "/filter_fid", "/filter_aia"):
        assert kw in script
    assert "/header_temps" not in script


def test_render_prep2_reads_level_12_writes_level_15(cfg):
    script = remote.render("prep2", cfg)
    assert "/deep_mosaics/20240811/level_12/*.fits" in script
    assert "/deep_mosaics/20240811/level_15" in script


def test_render_is_per_mosaic(cfg):
    other = MosaicConfig.load("20190912")
    assert "20240811" in remote.render("prep1", cfg)
    assert "20190912" in remote.render("prep1", other)
    assert "20240811" not in remote.render("prep1", other)


def test_unknown_step_rejected(cfg):
    with pytest.raises(KeyError, match="unknown IDL step"):
        remote.render("prep3", cfg)


def test_job_names_are_unique_per_step_and_mosaic(cfg):
    other = MosaicConfig.load("20190912")
    names = {
        remote.job_name("prep1", cfg),
        remote.job_name("prep2", cfg),
        remote.job_name("prep1", other),
    }
    assert len(names) == 3


# --------------------------------------------------------------------------
# status reporting
# --------------------------------------------------------------------------

class FakeSSH:
    """Stand-in for _ssh that returns a canned stdout."""

    def __init__(self, stdout=""):
        self.stdout = stdout
        self.commands = []

    def __call__(self, command, check=True):
        self.commands.append(command)

        class R:
            pass

        r = R()
        r.stdout = self.stdout
        r.stderr = ""
        r.returncode = 0
        return r


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("SENTINEL:0", "done"),
        ("SENTINEL:1", "failed"),
        ("SENTINEL:137", "failed"),
        ("RUNNING", "running"),
        ("ABSENT", "not started"),
    ],
)
def test_status_interpretation(cfg, monkeypatch, reply, expected):
    monkeypatch.setattr(remote, "_ssh", FakeSSH(reply))
    assert remote.status("prep1", cfg) == expected


def test_status_ignores_the_login_banner(cfg, monkeypatch):
    """filament prints a banner on every connection; only the last line counts."""
    banner = "----\nThis is a solar physics group machine.\n----\nSENTINEL:0"
    monkeypatch.setattr(remote, "_ssh", FakeSSH(banner))
    assert remote.status("prep1", cfg) == "done"


def test_a_crashed_idl_reports_failed_not_running(cfg, monkeypatch):
    """The shell writes the sentinel, so a nonzero exit is visible."""
    monkeypatch.setattr(remote, "_ssh", FakeSSH("SENTINEL:2"))
    assert remote.status("prep2", cfg) == "failed"


# --------------------------------------------------------------------------
# guard rails
# --------------------------------------------------------------------------

def test_launch_refuses_to_start_a_second_copy(cfg, monkeypatch):
    monkeypatch.setattr(remote, "status", lambda step, cfg: "running")
    with pytest.raises(RuntimeError, match="already running"):
        remote.launch("prep1", cfg)


def test_launch_dry_run_returns_the_script_without_connecting(cfg, monkeypatch):
    def explode(*a, **k):
        raise AssertionError("dry run must not touch filament")

    monkeypatch.setattr(remote, "_ssh", explode)
    script = remote.launch("prep1", cfg, dry_run=True)
    assert "iris_prep" in script


def test_cleanup_refuses_on_count_mismatch(cfg, monkeypatch):
    monkeypatch.setattr("iris_mosaics.transfer.remote_count", lambda d, pattern="*.fits": 11767)
    with pytest.raises(RuntimeError, match="Reconcile before deleting"):
        remote.cleanup_level(cfg, "level_1", expected_count=11000, confirm=True)


def test_cleanup_refuses_without_confirm(cfg, monkeypatch):
    monkeypatch.setattr("iris_mosaics.transfer.remote_count", lambda d, pattern="*.fits": 11767)
    with pytest.raises(RuntimeError, match="without confirm=True"):
        remote.cleanup_level(cfg, "level_1", expected_count=11767)


def test_cleanup_deletes_when_verified(cfg, monkeypatch):
    monkeypatch.setattr("iris_mosaics.transfer.remote_count", lambda d, pattern="*.fits": 11767)
    fake = FakeSSH()
    monkeypatch.setattr(remote, "_ssh", fake)
    target = remote.cleanup_level(cfg, "level_1", expected_count=11767, confirm=True)
    assert target.endswith("/level_1")
    assert any(c.startswith("rm -rf ") and c.endswith("/level_1") for c in fake.commands)
