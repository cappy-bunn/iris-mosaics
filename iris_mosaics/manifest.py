"""Per-mosaic processing manifest.

Replaces the hand-kept ledger. Each pipeline step records what it did, so
"which mosaics are through the background subtraction?" and "was this despiked
before or after the fixed pattern was removed?" become queries rather than
recollection.

Manifests are small JSON files in ``status/`` and are version controlled, so
the record survives independently of the data drive.

    >>> from iris_mosaics import Manifest
    >>> m = Manifest.load('20240811')
    >>> m.record('despiked', n_files=11767)     # doctest: +SKIP
    >>> m.save()                                # doctest: +SKIP
    >>> m.completed('despiked')
    True

``docs/STATUS.md`` is generated from these by :func:`render_status_markdown`.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib as pl

STATUS_DIR = pl.Path(__file__).parent.parent / "status"

#: Pipeline steps in order. Keys are what steps record; values are the labels
#: used in the generated status document.
STEPS = {
    "level_1": "L1 downloaded from JSOC",
    "level_11": "L1.1 iris_prep part 1 + Wülser background",
    "fixed_pattern_removed": "Fixed pattern removed",
    "despiked": "Despiked",
    "rolling_trimmed_mean": "Rolling trimmed mean",
    "level_12": "L1.2 MSU background subtracted",
    "level_15": "L1.5 remainder of iris_prep",
    "level_15_rebinned": "L1.5 rebinned",
    "level_16": "L1.6 radiometric conversion calculated",
    "mosaic": "Mosaic assembled",
}


@dataclasses.dataclass
class Manifest:
    """What has been done to one mosaic."""

    date: str
    steps: dict = dataclasses.field(default_factory=dict)
    notes: str = ""

    @classmethod
    def path_for(cls, date: str) -> pl.Path:
        return STATUS_DIR / f"{date}.json"

    @classmethod
    def load(cls, date: str) -> "Manifest":
        """Load a manifest, or start an empty one if the mosaic has no record."""
        path = cls.path_for(date)
        if not path.exists():
            return cls(date=date)
        doc = json.loads(path.read_text(encoding="utf-8"))
        return cls(date=doc["date"], steps=doc.get("steps", {}), notes=doc.get("notes", ""))

    @classmethod
    def available(cls) -> list[str]:
        if not STATUS_DIR.exists():
            return []
        return sorted(p.stem for p in STATUS_DIR.glob("*.json"))

    def save(self) -> pl.Path:
        STATUS_DIR.mkdir(parents=True, exist_ok=True)
        path = self.path_for(self.date)
        doc = {"date": self.date, "steps": self.steps, "notes": self.notes}
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        return path

    def record(self, step: str, date: str | None = None, **details) -> None:
        """Mark a step complete.

        ``date`` defaults to today (ISO format). Extra keyword arguments are
        stored alongside — file counts, parameters used, anything worth being
        able to look up later.
        """
        if step not in STEPS:
            raise KeyError(f"unknown step {step!r}; known: {', '.join(STEPS)}")
        entry = {"date": date or dt.date.today().isoformat()}
        entry.update(details)
        self.steps[step] = entry

    def completed(self, step: str) -> bool:
        return step in self.steps

    def completed_on(self, step: str) -> str | None:
        entry = self.steps.get(step)
        return entry["date"] if entry else None

    @property
    def furthest_step(self) -> str | None:
        """The last step in pipeline order that has been completed."""
        done = [s for s in STEPS if s in self.steps]
        return done[-1] if done else None

    def out_of_order(self) -> list[tuple[str, str]]:
        """Pairs of steps whose recorded dates run backwards.

        A later pipeline step dated before an earlier one usually means
        something was re-run, or the ledger is wrong. Either way it is worth
        seeing rather than discovering during analysis.
        """
        done = [(s, self.steps[s]["date"]) for s in STEPS if s in self.steps]
        problems = []
        for (earlier, d1), (later, d2) in zip(done, done[1:]):
            if d2 < d1:
                problems.append((earlier, later))
        return problems


def _config_summary(date: str) -> str:
    """One-line summary of a mosaic's config, or "" if it has none."""
    from .config import MosaicConfig

    try:
        cfg = MosaicConfig.load(date)
    except FileNotFoundError:
        return ""

    bits = []
    if cfg.wavelength_shift is not None:
        bits.append(f"wavelength shift {cfg.wavelength_shift.value:+g} Å")
    if cfg.spectral_binning != 1:
        bits.append(f"{cfg.spectral_binning}× spectral binning")
    if cfg.num_img_per_raster != 64:
        bits.append(f"{cfg.num_img_per_raster} images/raster")
    return "*" + "; ".join(bits) + "*" if bits else ""


def render_status_markdown() -> str:
    """Generate the contents of ``docs/STATUS.md`` from every manifest."""
    lines = [
        "# Status of deep FDMs",
        "",
        "**Generated from `status/*.json` by `iris_mosaics.manifest`. Do not edit by",
        "hand** — record progress with `Manifest.record(...)` instead.",
        "",
        "See [RUNBOOK.md](RUNBOOK.md) for the procedure. Per-mosaic parameters live in",
        "`config/<date>.yaml`; the ones shown here are a summary of that file.",
        "",
    ]
    manifests = [Manifest.load(d) for d in Manifest.available()]
    if not manifests:
        lines.append("_No manifests recorded yet._")
        return "\n".join(lines) + "\n"

    for m in manifests:
        lines.append(f"## {m.date[:4]}-{m.date[4:6]}-{m.date[6:]}")
        lines.append("")
        if m.notes:
            lines.append(f"{m.notes}")
            lines.append("")

        params = _config_summary(m.date)
        if params:
            lines.append(params)
            lines.append("")
        if not m.steps:
            lines.append("- _not started_")
        else:
            for step, label in STEPS.items():
                entry = m.steps.get(step)
                if entry is None:
                    continue
                extra = ", ".join(
                    f"{k}={v}" for k, v in entry.items() if k != "date"
                )
                suffix = f" ({extra})" if extra else ""
                lines.append(f"- {label} — {entry['date']}{suffix}")
        for earlier, later in m.out_of_order():
            lines.append(
                f"- ⚠️ **{later}** is dated before **{earlier}**; may need rerunning"
            )
        lines.append("")

    return "\n".join(lines) + "\n"
