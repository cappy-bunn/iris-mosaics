"""Tests for pipeline ordering and the CLI's manifest handling."""

import pytest

from iris_mosaics import manifest, pipeline
from iris_mosaics.manifest import Manifest


@pytest.fixture
def status_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "STATUS_DIR", tmp_path)
    return tmp_path


def test_steps_are_in_pipeline_order():
    names = [s.name for s in pipeline.STEPS]
    assert names.index("fixed_pattern") < names.index("despike"), (
        "fixed-pattern removal must precede despiking -- the despiker would "
        "otherwise remove part of the pattern"
    )
    assert names.index("prep1") < names.index("background")
    assert names.index("background") < names.index("prep2")
    assert names.index("radiometric") < names.index("mosaic")


def test_every_step_names_a_real_prerequisite():
    manifest_steps = set(manifest.STEPS)
    for s in pipeline.STEPS:
        if s.needs is not None:
            assert s.needs in manifest_steps, f"{s.name} needs unknown {s.needs}"
        if s.manifest_step is not None:
            assert s.manifest_step in manifest_steps, s.name


def test_next_step_of_a_fresh_mosaic_is_the_download(status_dir):
    Manifest(date="20210418").save()
    assert pipeline.next_step("20210418") == "download"


def test_next_step_advances_as_work_is_recorded(status_dir):
    m = Manifest(date="20240811")
    m.record("level_1")
    m.save()
    assert pipeline.next_step("20240811") == "prep1"

    m.record("level_11")
    m.save()
    assert pipeline.next_step("20240811") == "fixed_pattern"


def test_next_step_is_none_when_finished(status_dir):
    m = Manifest(date="20240811")
    for step in ("level_1", "level_11", "fixed_pattern_removed", "despiked",
                 "rolling_trimmed_mean", "level_12", "level_15", "level_16",
                 "mosaic"):
        m.record(step)
    m.save()
    assert pipeline.next_step("20240811") is None


def test_blocked_reason_when_prerequisite_missing(status_dir):
    Manifest(date="20240811").save()
    reason = pipeline.blocked_reason("20240811", "prep1")
    assert reason is not None and "level_1" in reason


def test_not_blocked_once_prerequisite_recorded(status_dir):
    m = Manifest(date="20240811")
    m.record("level_1")
    m.save()
    assert pipeline.blocked_reason("20240811", "prep1") is None


def test_first_step_has_no_prerequisite(status_dir):
    Manifest(date="20240811").save()
    assert pipeline.blocked_reason("20240811", "download") is None


def test_plan_marks_done_next_and_pending(status_dir):
    m = Manifest(date="20240811")
    m.record("level_1")
    m.save()
    states = dict(pipeline.plan("20240811"))
    assert states["download"] == "done"
    assert states["prep1"] == "next"
    assert states["mosaic"] == "pending"


def test_summary_flags_out_of_order_work(status_dir):
    m = Manifest(date="20190912")
    m.record("fixed_pattern_removed", date="2026-04-06")
    m.record("despiked", date="2026-01-14")
    m.save()
    assert "may need rerunning" in pipeline.summary("20190912")


def test_overview_lists_every_mosaic(status_dir):
    Manifest(date="20240811").save()
    m = Manifest(date="20190912")
    m.record("level_1")
    m.save()
    text = pipeline.overview()
    assert "20240811" in text and "20190912" in text


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_record_writes_the_manifest(status_dir, capsys):
    from iris_mosaics.__main__ import main

    rc = main(["record", "despiked", "20240811", "--on", "2026-07-21",
               "--n-files", "11767"])
    assert rc == 0
    m = Manifest.load("20240811")
    assert m.completed_on("despiked") == "2026-07-21"
    assert m.steps["despiked"]["n_files"] == 11767


def test_cli_status_of_one_mosaic(status_dir, capsys):
    from iris_mosaics.__main__ import main

    m = Manifest(date="20240811")
    m.record("level_1")
    m.save()
    assert main(["status", "20240811"]) == 0
    out = capsys.readouterr().out
    assert "download" in out and "prep1" in out


def test_cli_idl_launch_refuses_when_blocked(status_dir, capsys):
    from iris_mosaics.__main__ import main

    Manifest(date="20240811").save()   # nothing done yet
    rc = main(["idl", "launch", "prep1", "20240811"])
    assert rc == 1
    assert "refusing to launch" in capsys.readouterr().err


# --------------------------------------------------------------------------
# gaps in a historical record must not be mistaken for outstanding work
# --------------------------------------------------------------------------

def test_next_step_skips_gaps_behind_the_furthest_progress(status_dir):
    """The old ledger never tracked the rolling trimmed mean.

    A mosaic recorded through level 1.6 must not be reported as needing to go
    back and redo that stage.
    """
    m = Manifest(date="20240811")
    for step in ("level_1", "level_11", "fixed_pattern_removed", "despiked",
                 "level_12", "level_15", "level_16"):
        m.record(step)
    m.save()
    assert pipeline.next_step("20240811") == "mosaic"


def test_record_gaps_reports_the_hole(status_dir):
    m = Manifest(date="20240811")
    for step in ("level_1", "level_11", "fixed_pattern_removed", "despiked",
                 "level_12", "level_15", "level_16"):
        m.record(step)
    m.save()
    assert pipeline.record_gaps("20240811") == ["rolling_mean"]


def test_no_gaps_reported_for_a_contiguous_record(status_dir):
    m = Manifest(date="20240811")
    m.record("level_1")
    m.record("level_11")
    m.save()
    assert pipeline.record_gaps("20240811") == []


def test_summary_mentions_gaps(status_dir):
    m = Manifest(date="20240811")
    for step in ("level_1", "level_11", "fixed_pattern_removed", "despiked",
                 "level_12", "level_15", "level_16"):
        m.record(step)
    m.save()
    assert "unrecorded but implied" in pipeline.summary("20240811")


def test_fresh_mosaic_has_no_gaps(status_dir):
    Manifest(date="20210418").save()
    assert pipeline.record_gaps("20210418") == []
    assert pipeline.next_step("20210418") == "download"
