"""Per-mosaic calibration values.

Values determined once by the pipeline notebooks and needed again later during
science analysis. Kept here rather than inside a notebook cell so they can be
looked up directly:

    >>> from iris_mosaics import wavelength_shift
    >>> wavelength_shift('20240811')
    <Quantity -0.018 Angstrom>
"""

import pathlib as pl

import astropy.units as u
import yaml

CONFIG_DIR = pl.Path(__file__).parent.parent / "config"
_WAVELENGTH_SHIFTS = CONFIG_DIR / "wavelength_shifts.yaml"


def _load(path: pl.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def wavelength_shifts() -> dict[str, u.Quantity]:
    """All known wavelength shifts, keyed by mosaic date string (YYYYMMDD)."""
    doc = _load(_WAVELENGTH_SHIFTS)
    unit = u.Unit(doc["units"])
    return {date: value * unit for date, value in doc["shifts"].items()}


def wavelength_shift(date_string: str) -> u.Quantity:
    """Wavelength shift for one mosaic, as an additive offset.

    Apply as ``sg_wavelength_full + wavelength_shift(date_string)`` to align the
    neutral lines with their nominal positions.

    Raises KeyError if the mosaic has not been wavelength calibrated yet; run
    ``notebooks/wavelength_calibration.ipynb`` and add the result to
    ``config/wavelength_shifts.yaml``.
    """
    shifts = wavelength_shifts()
    if date_string not in shifts:
        known = ", ".join(sorted(shifts)) or "none"
        raise KeyError(
            f"no wavelength shift recorded for {date_string!r}; known: {known}. "
            "Run notebooks/wavelength_calibration.ipynb and add it to "
            "config/wavelength_shifts.yaml"
        )
    return shifts[date_string]
