"""Tests for path translation and rsync command construction."""

import pytest

from iris_mosaics import transfer


@pytest.mark.parametrize(
    "windows, expected",
    [
        (r"D:\IRIS data\deep_mosaics\20240811", "/mnt/d/IRIS data/deep_mosaics/20240811"),
        (r"C:\Users\Cappy", "/mnt/c/Users/Cappy"),
        (r"D:\a\b\c", "/mnt/d/a/b/c"),
        ("/already/posix", "/already/posix"),
        ("relative/path", "relative/path"),
    ],
)
def test_to_wsl_path(windows, expected):
    assert transfer.to_wsl_path(windows) == expected


def test_to_wsl_path_lowercases_drive():
    assert transfer.to_wsl_path(r"D:\x").startswith("/mnt/d/")


def test_push_syncs_contents_not_the_directory_itself():
    """Both ends need trailing slashes or rsync nests the directory."""
    argv = transfer._rsync_argv(
        transfer.to_wsl_path(r"D:\data\level_12").rstrip("/") + "/",
        "host:/remote/level_12/",
        dry_run=False,
        size_only=False,
        extra=(),
    )
    src, dst = argv[-2], argv[-1]
    assert src.endswith("/")
    assert dst.endswith("/")
    assert src == "/mnt/d/data/level_12/"


def test_rsync_argv_carries_resume_flags():
    argv = transfer._rsync_argv("a/", "b/", dry_run=False, size_only=False, extra=())
    assert "--partial" in argv  # resume after a dropped VPN
    assert "-a" in argv


def test_dry_run_and_size_only_flags():
    argv = transfer._rsync_argv("a/", "b/", dry_run=True, size_only=True, extra=())
    assert "--dry-run" in argv
    assert "--size-only" in argv

    argv = transfer._rsync_argv("a/", "b/", dry_run=False, size_only=False, extra=())
    assert "--dry-run" not in argv
    assert "--size-only" not in argv


def test_ssh_command_specifies_identity():
    """rsync's -e carries the ssh spec.

    Note both `wsl -e` and rsync's own `-e` appear on Windows, so find the one
    whose value actually looks like an ssh invocation.
    """
    argv = transfer._rsync_argv("a/", "b/", dry_run=False, size_only=False, extra=())
    ssh = next(v for v in argv if v.startswith("ssh "))
    assert "BatchMode=yes" in ssh
    assert transfer.WSL_IDENTITY in ssh
    # the ssh spec must be the value of an -e flag
    assert argv[argv.index(ssh) - 1] == "-e"


def test_check_room_raises_when_short(monkeypatch, tmp_path):
    (tmp_path / "a.fits").write_bytes(b"x" * 1000)
    monkeypatch.setattr(transfer, "remote_free_bytes", lambda path="/disk/data": 500)
    with pytest.raises(RuntimeError, match="not enough room"):
        transfer.check_room(tmp_path)


def test_check_room_passes_when_space_available(monkeypatch, tmp_path):
    (tmp_path / "a.fits").write_bytes(b"x" * 1000)
    monkeypatch.setattr(transfer, "remote_free_bytes", lambda path="/disk/data": 10_000)
    transfer.check_room(tmp_path)  # must not raise
