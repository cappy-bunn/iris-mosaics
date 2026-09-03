"""IRIS full-disk mosaic processing.

Configuration, raster geometry, calibration values and plotting import
eagerly — they are pure-python and cheap. The mosaic-building routines in
:mod:`iris_mosaics.read_full_disk_mosaic` pull in ``reproject``/``regridding``
and are loaded on first use, so importing this package stays light:

    >>> from iris_mosaics import MosaicConfig       # no heavy imports
    >>> from iris_mosaics import build_mosaic_regrid  # loads them now
"""

from .config import MosaicConfig
from .calibration import wavelength_shift, wavelength_shifts
from .plotting import plot_lines_sidebyside
from .rasters import RasterLayout, plan_rasters, read_pointing
from .manifest import Manifest
from .assembled import AssembledMosaic
from .geometry import (
    for_plotting, solar_geometry, annulus_labels, annulus_radii,
    plot_annuli, find_disk_center,
)
from . import assembled, background, despike, fixed_pattern, geometry, transfer

#: Names served lazily from .read_full_disk_mosaic
_MOSAIC_EXPORTS = frozenset({
    "read_full_disk_mosaic",
    "wcs_to_bins",
    "spectral_plot",
    "read_sg_image",
    "read_sg_image_lvl1",
    "read_sg_image_old",
    "build_mosaic",
    "build_mosaic_regrid",
    "build_mosaic_sav",
    "build_mosaic_single_wavelength",
})

__all__ = sorted(
    _MOSAIC_EXPORTS
    | {
        "MosaicConfig",
        "RasterLayout",
        "plan_rasters",
        "read_pointing",
        "plot_lines_sidebyside",
        "wavelength_shift",
        "wavelength_shifts",
        "Manifest",
        "AssembledMosaic",
        "assembled",
        "background",
        "despike",
        "fixed_pattern",
        "transfer",
    }
)


def __getattr__(name: str):
    if name in _MOSAIC_EXPORTS:
        from . import read_full_disk_mosaic

        return getattr(read_full_disk_mosaic, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
