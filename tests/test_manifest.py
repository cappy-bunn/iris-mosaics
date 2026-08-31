"""Tests for the per-mosaic processing manifest."""

import pytest

from iris_mosaics import manifest
from iris_mosaics.manifest import Manifest


@pytest.fixture
def status_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "STATUS_DIR", tmp_path)
    return tmp_path


def test_missing_manifest_starts_empty(status_dir):
    m = Manifest.load("20990101")
    assert m.steps == {}
    assert m.furthest_step is None


def test_record_and_roundtrip(status_dir):
    m = Manifest.load("20240811")
    m.record("level_1", date="2026-05-28", n_files=11767)
    m.save()

    again = Manifest.load("20240811")
    assert again.completed("level_1")
    assert again.completed_on("level_1") == "2026-05-28"
    assert again.steps["level_1"]["n_files"] == 11767


def test_record_defaults_to_today(status_dir):
    import datetime as dt

    m = Manifest.load("20240811")
    m.record("despiked")
    assert m.completed_on("despiked") == dt.date.today().isoformat()


def test_unknown_step_rejected(status_dir):
    m = Manifest.load("20240811")
    with pytest.raises(KeyError, match="unknown step"):
        m.record("polish_the_mirror")


def test_furthest_step_follows_pipeline_order_not_insertion_order(status_dir):
    m = Manifest.load("20240811")
    m.record("level_15", date="2026-07-28")
    m.record("level_1", date="2026-05-28")   # recorded later, earlier in pipeline
    assert m.furthest_step == "level_15"


def test_out_of_order_detects_backwards_dates(status_dir):
    """The 2019-09-12 case: despiked dated before fixed-pattern removal."""
    m = Manifest.load("20190912")
    m.record("fixed_pattern_removed", date="2026-04-06")
    m.record("despiked", date="2026-01-14")
    assert m.out_of_order() == [("fixed_pattern_removed", "despiked")]


def test_out_of_order_quiet_when_dates_ascend(status_dir):
    m = Manifest.load("20240811")
    m.record("fixed_pattern_removed", date="2026-07-08")
    m.record("despiked", date="2026-07-21")
    assert m.out_of_order() == []


def test_render_status_lists_each_mosaic(status_dir):
    a = Manifest(date="20240811", notes="binned")
    a.record("level_1", date="2026-05-28")
    a.save()
    Manifest(date="20210418").save()

    text = manifest.render_status_markdown()
    assert "## 2024-08-11" in text
    assert "## 2021-04-18" in text
    assert "L1 downloaded from JSOC — 2026-05-28" in text
    assert "_not started_" in text
    assert "binned" in text


def test_render_status_surfaces_the_warning(status_dir):
    m = Manifest(date="20190912")
    m.record("fixed_pattern_removed", date="2026-04-06")
    m.record("despiked", date="2026-01-14")
    m.save()
    assert "may need rerunning" in manifest.render_status_markdown()


def test_render_status_with_no_manifests(status_dir):
    assert "_No manifests recorded yet._" in manifest.render_status_markdown()
