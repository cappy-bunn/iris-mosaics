"""Pipeline orchestration: what has been done, and what to do next.

Each step declares where its input comes from and where its output goes, so
"what runs next for this mosaic?" is answered by looking at the data and the
manifest rather than by remembering.

    >>> from iris_mosaics import pipeline
    >>> pipeline.next_step('20240811')          # doctest: +SKIP
    'mosaic'

Local steps are notebooks — deliberately so, since the introspection is the
point. This module does not run them; it tells you which to open, checks their
inputs exist, and records completion. The two IDL steps *are* run from here,
via :mod:`iris_mosaics.remote`, because babysitting a 7-hour interactive
session is exactly what is worth automating.
"""

from __future__ import annotations

import dataclasses

from .config import MosaicConfig
from .manifest import Manifest


@dataclasses.dataclass(frozen=True)
class Step:
    """One stage of the pipeline."""

    name: str
    where: str            # 'local', 'filament', or 'transfer'
    how: str              # notebook filename, IDL step name, or transfer direction
    manifest_step: str | None
    needs: str | None     # manifest step that must be complete first
    description: str


#: The pipeline in order.
STEPS = (
    Step("download", "local", "download_level_1.ipynb", "level_1", None,
         "Query JSOC and download level 1 (~3 h)"),
    Step("upload_l1", "transfer", "push level_1", None, "level_1",
         "rsync level 1 to filament (~10 h)"),
    Step("prep1", "filament", "prep1", "level_11", "level_1",
         "iris_prep through the FUV background subtraction (~7 h)"),
    Step("download_l11", "transfer", "pull level_11", None, "level_11",
         "rsync level 1.1 back to the local archive (~1 h)"),
    Step("fixed_pattern", "local", "remove_fixed_pattern_full_ccd.ipynb",
         "fixed_pattern_removed", "level_11",
         "Remove the fixed pattern (must precede despiking)"),
    Step("despike", "local", "despike_and_save.ipynb", "despiked",
         "fixed_pattern_removed", "Despike with Astro-SCRAPPY"),
    Step("rolling_mean", "local", "apply_rolling_trimmed_mean.ipynb",
         "rolling_trimmed_mean", "despiked",
         "Rolling trimmed mean along the raster dimension"),
    Step("background", "local", "background_subtraction.ipynb", "level_12",
         "rolling_trimmed_mean", "Two-step background subtraction -> level 1.2"),
    Step("upload_l12", "transfer", "push level_12", None, "level_12",
         "rsync level 1.2 to filament (~6 h)"),
    Step("prep2", "filament", "prep2", "level_15", "level_12",
         "Remainder of iris_prep -> level 1.5 (~9 h)"),
    Step("download_l15", "transfer", "pull level_15", None, "level_15",
         "rsync level 1.5 back to the local archive (~5 h)"),
    Step("wavelength", "local", "wavelength_calibration.ipynb", None, "level_15",
         "Fit the neutral lines; record the shift in config/<date>.yaml"),
    Step("radiometric", "local", "radiometric_calibration.ipynb", "level_16",
         "level_15", "Radiometric conversion factor -> level 1.6"),
    Step("mosaic", "local", "build_and_save_mosaic.ipynb", "mosaic", "level_16",
         "Assemble and save the mosaic"),
)

STEPS_BY_NAME = {s.name: s for s in STEPS}


def completed_steps(date: str) -> list[str]:
    """Names of pipeline steps whose manifest entry is recorded."""
    m = Manifest.load(date)
    return [s.name for s in STEPS if s.manifest_step and m.completed(s.manifest_step)]


def _recorded_step_order(m: Manifest) -> list[Step]:
    """Pipeline steps that carry a manifest entry, in order."""
    return [s for s in STEPS if s.manifest_step is not None]


def next_step(date: str) -> str | None:
    """The first unrecorded step *after* the furthest one completed.

    Not simply the first unrecorded step: historical records have gaps (the old
    ledger never tracked the rolling trimmed mean, for instance), and a mosaic
    that reached level 1.6 does not need to go back and redo an earlier stage.
    Genuine gaps are reported separately by :func:`record_gaps` rather than
    being mistaken for outstanding work.

    Transfer steps have no manifest entry of their own — they are implied by
    the step that follows — so they are skipped here.
    """
    m = Manifest.load(date)
    ordered = _recorded_step_order(m)

    last_done = -1
    for i, s in enumerate(ordered):
        if m.completed(s.manifest_step):
            last_done = i

    for s in ordered[last_done + 1:]:
        if not m.completed(s.manifest_step):
            return s.name
    return None


def record_gaps(date: str) -> list[str]:
    """Steps left unrecorded even though later work is done.

    These are almost always holes in the record rather than missing work — the
    pipeline could not have gone on without them — but they are worth seeing,
    because the alternative is silently trusting an incomplete ledger.
    """
    m = Manifest.load(date)
    ordered = _recorded_step_order(m)

    last_done = -1
    for i, s in enumerate(ordered):
        if m.completed(s.manifest_step):
            last_done = i

    if last_done < 0:          # nothing done yet, so nothing can be a gap
        return []              # (guard: ordered[:-1] would be almost everything)

    return [
        s.name for s in ordered[:last_done]
        if not m.completed(s.manifest_step)
    ]


def blocked_reason(date: str, step: str) -> str | None:
    """Why ``step`` cannot run yet, or None if its prerequisite is satisfied."""
    s = STEPS_BY_NAME[step]
    if s.needs is None:
        return None
    m = Manifest.load(date)
    if not m.completed(s.needs):
        return f"{step!r} needs {s.needs!r}, which is not recorded as complete"
    return None


def plan(date: str) -> list[tuple[str, str]]:
    """Every step with its state: ``done``, ``next``, or ``pending``."""
    m = Manifest.load(date)
    upcoming = next_step(date)
    rows = []
    for s in STEPS:
        if s.manifest_step and m.completed(s.manifest_step):
            state = "done"
        elif s.name == upcoming:
            state = "next"
        else:
            state = "pending"
        rows.append((s.name, state))
    return rows


def summary(date: str) -> str:
    """Human-readable status of one mosaic."""
    cfg_note = ""
    try:
        cfg = MosaicConfig.load(date)
        if cfg.notes:
            cfg_note = f"  {cfg.notes}\n"
    except FileNotFoundError:
        cfg_note = "  (no config file for this mosaic)\n"

    m = Manifest.load(date)
    lines = [f"{date}", cfg_note.rstrip("\n")] if cfg_note else [f"{date}"]
    for name, state in plan(date):
        s = STEPS_BY_NAME[name]
        mark = {"done": "[x]", "next": "->", "pending": "[ ]"}[state]
        when = ""
        if s.manifest_step and m.completed(s.manifest_step):
            when = f"  {m.completed_on(s.manifest_step)}"
        lines.append(f"  {mark:3s} {name:14s} {s.where:9s}{when}")
    for earlier, later in m.out_of_order():
        lines.append(f"  !!  {later} is dated before {earlier}; may need rerunning")
    gaps = record_gaps(date)
    if gaps:
        lines.append(
            f"  ..  unrecorded but implied by later work: {', '.join(gaps)}"
        )
    return "\n".join(lines)


def overview() -> str:
    """One line per mosaic: how far it has got, and what is next."""
    lines = []
    for date in Manifest.available():
        m = Manifest.load(date)
        furthest = m.furthest_step or "-"
        upcoming = next_step(date) or "complete"
        warn = " !!" if m.out_of_order() else ""
        gaps = f" (gaps: {len(record_gaps(date))})" if record_gaps(date) else ""
        lines.append(f"{date}  at:{furthest:22s} next:{upcoming}{warn}{gaps}")
    return "\n".join(lines)
