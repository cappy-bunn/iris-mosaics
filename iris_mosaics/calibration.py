"""Per-mosaic calibration values.

Values determined once by the pipeline notebooks and needed again later during
science analysis. They live in the per-mosaic configs under ``config/`` so
there is a single source of truth, but are reachable directly:

    >>> from iris_mosaics import wavelength_shift
    >>> wavelength_shift('20240811')
    <Quantity -0.018 Angstrom>
"""

from __future__ import annotations

import astropy.units as u

from .config import MosaicConfig


def wavelength_shifts() -> dict[str, u.Quantity]:
    """Wavelength shifts for every mosaic that has been calibrated."""
    shifts = {}
    for date in MosaicConfig.available():
        shift = MosaicConfig.load(date).wavelength_shift
        if shift is not None:
            shifts[date] = shift
    return shifts


def wavelength_shift(date_string: str) -> u.Quantity:
    """Wavelength shift for one mosaic, as an additive offset.

    Apply as ``sg_wavelength_full + wavelength_shift(date_string)`` to align the
    neutral lines with their nominal positions.

    Raises KeyError if the mosaic has not been wavelength calibrated yet; run
    ``notebooks/wavelength_calibration.ipynb`` and set
    ``wavelength_shift_angstrom`` in ``config/<date>.yaml``.
    """
    shift = MosaicConfig.load(date_string).wavelength_shift
    if shift is None:
        known = ", ".join(sorted(wavelength_shifts())) or "none"
        raise KeyError(
            f"mosaic {date_string!r} has no wavelength shift recorded yet; "
            f"calibrated mosaics: {known}. Run "
            "notebooks/wavelength_calibration.ipynb and set "
            f"wavelength_shift_angstrom in config/{date_string}.yaml"
        )
    return shift
