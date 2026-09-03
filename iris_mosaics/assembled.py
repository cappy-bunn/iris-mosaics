"""Handing the assembled mosaic to science.

This is the pipeline's output contract, the seam between processing (this
package) and analysis (the science repository). Everything downstream should
reach the data through here rather than by spelling a ``D:`` path or re-typing
a calibration value:

    >>> from iris_mosaics import assembled
    >>> assembled.not_ready_reasons('20190912')     # [] when science can start
    >>> m = assembled.load('20190912')              # doctest: +SKIP
    >>> m.data.shape, m.wavelength[0], m.dn2flux[0] # doctest: +SKIP

What the pipeline hands over, per mosaic:

- the **assembled mosaic**, a pickled dict of ``data`` (x, y, wavelength) and
  a 3-axis ``wcs``, written by ``build_and_save_mosaic.ipynb``;
- the **radiometric factor**, a small FITS file whose primary HDU converts DN
  to W nm⁻¹ sr⁻¹ m⁻² and whose ``WAVELENGTH`` extension says at which
  wavelengths, written by ``radiometric_calibration.ipynb``;
- the **wavelength shift**, from ``config/<date>.yaml``.

:func:`load` applies the wavelength shift, interpolates the radiometric factor
onto the mosaic's wavelength axis, and crops the empty border around the disk,
exactly as the science notebooks did by hand. It does *not* multiply the cube
by the factor: the cube is ~17 GB and the caller should decide when to spend
that memory. :meth:`AssembledMosaic.calibrate` does it on request.

:func:`provenance` records what went in, so a science product can say which
mosaic file, which shift and which version of this package produced it.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib as pl
import pickle
import subprocess

import astropy.units as u
import numpy as np
from astropy.io import fits
from scipy import interpolate

from .config import MosaicConfig
from .manifest import Manifest

#: Half-width of the region kept around the disk. The assembled mosaic carries
#: an empty border; ±1000″ comfortably contains the ~960″ disk.
DEFAULT_CROP = 1000 * u.arcsec


# --------------------------------------------------------------------------
# pieces (pure, testable)
# --------------------------------------------------------------------------

def wavelength_axis(wcs, n_spectral: int) -> u.Quantity:
    """Wavelength of every spectral pixel, in Angstrom.

    The spectral axis is the first FITS axis (the last numpy axis) and the WCS
    reports it in metres.
    """
    pix = np.arange(n_spectral)
    wave, _, _ = wcs.all_pix2world(pix, 0, 0, 0)
    return (wave * u.m).to(u.AA)


def read_dn2flux(path) -> tuple[u.Quantity, u.Quantity]:
    """The radiometric factor and the wavelengths it is tabulated at."""
    with fits.open(path) as hl:
        factor = hl[0].data * u.Unit(hl[0].header["BUNIT"])
        wave = hl["WAVELENGTH"].data * u.Unit(hl["WAVELENGTH"].header["BUNIT"])
    return factor, wave


def interpolate_dn2flux(
    factor: u.Quantity, factor_wave: u.Quantity, wavelength: u.Quantity
) -> u.Quantity:
    """Resample the radiometric factor onto the mosaic's wavelength axis.

    Raises ValueError if the mosaic axis extends beyond the tabulated range —
    extrapolating a calibration silently would be worse than stopping.
    """
    fw = factor_wave.to(u.AA).value
    w = wavelength.to(u.AA).value
    lo, hi = fw.min(), fw.max()
    if w.min() < lo or w.max() > hi:
        raise ValueError(
            f"mosaic wavelength axis {w.min():.3f}..{w.max():.3f} Å extends beyond "
            f"the radiometric factor's {lo:.3f}..{hi:.3f} Å; the factor cannot be "
            "interpolated onto it"
        )
    f = interpolate.interp1d(fw, factor.value)
    return f(w) * factor.unit


def crop_to_disk(data: np.ndarray, wcs, half_width: u.Quantity = DEFAULT_CROP):
    """Cut the empty border off the assembled mosaic.

    Keeps the square from ``-half_width`` to ``+half_width`` in both solar
    coordinates. Returns ``(data, spatial_wcs, (kmin, kmax, jmin, jmax))`` where
    ``spatial_wcs`` is the 2-axis WCS of the cropped spatial plane.

    Follows the science notebooks exactly: pixel bounds come from
    ``all_world2pix`` at the two corners, the slice is inclusive of ``max``,
    and the spectral axis is dropped from the WCS afterwards.
    """
    hw = half_width.to(u.deg).value
    _, jmax, kmax = wcs.all_world2pix(0, hw, hw, 0)
    _, jmin, kmin = wcs.all_world2pix(0, -hw, -hw, 0)
    jmin, jmax, kmin, kmax = int(jmin), int(jmax), int(kmin), int(kmax)

    cropped = data[kmin:kmax + 1, jmin:jmax + 1, :]
    spatial_wcs = wcs[kmin:kmax + 1, jmin:jmax + 1, :].deepcopy().dropaxis(0)
    return cropped, spatial_wcs, (kmin, kmax, jmin, jmax)


def solar_radius(date: str) -> u.Quantity:
    """The apparent photospheric solar radius at the mosaic epoch, from the
    ``RSUN_OBS`` header of a level 1.5 file near the middle of the mosaic.

    This is the radius mu and the equal-area annuli should be built on. The
    transition-region emission extends a few arcsec above it (the automated
    limb fit lands ~4″ higher on 2019-09-12), so anything meant to *contain*
    the emission is a separate, larger boundary, not a substitute for this.
    """
    cfg = MosaicConfig.load(date)
    files = cfg.files("level_15")
    if not files:
        raise FileNotFoundError(f"no level 1.5 files for {date} under {cfg.level_path('level_15')}")
    header = fits.getheader(files[len(files) // 2])
    if "RSUN_OBS" not in header:
        raise KeyError(f"RSUN_OBS missing from {files[len(files) // 2]}")
    return float(header["RSUN_OBS"]) * u.arcsec


# --------------------------------------------------------------------------
# readiness and provenance
# --------------------------------------------------------------------------

def not_ready_reasons(date: str) -> list[str]:
    """Why science cannot start on this mosaic yet. Empty means it can.

    Checks the manifest (level 1.6 and the assembled mosaic recorded), the two
    files, and that a wavelength shift has been determined.
    """
    reasons = []
    try:
        cfg = MosaicConfig.load(date)
    except FileNotFoundError as e:
        return [str(e)]

    m = Manifest.load(date)
    if not m.completed("level_16"):
        reasons.append("radiometric calibration (level_16) is not recorded in the manifest")
    if not m.completed("mosaic"):
        reasons.append("mosaic assembly is not recorded in the manifest")
    if not cfg.mosaic_path.exists():
        reasons.append(f"assembled mosaic not found: {cfg.mosaic_path}")
    if not cfg.radiometric_path.exists():
        reasons.append(f"radiometric factor not found: {cfg.radiometric_path}")
    if cfg.wavelength_shift is None:
        reasons.append(
            "no wavelength shift in the config; run wavelength_calibration.ipynb "
            f"and set wavelength_shift_angstrom in config/{date}.yaml"
        )
    return reasons


def _git_commit() -> str | None:
    """This package's git commit, or None if that cannot be determined."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=pl.Path(__file__).parent, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _file_record(path: pl.Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    st = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "bytes": st.st_size,
        "modified": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }


def provenance(date: str) -> dict:
    """What a science product built from this mosaic was built from.

    Store this alongside the product. Everything here is either a file's
    identity or a configuration value, so it is cheap to record and answers
    "which version of the mosaic did this come from" months later.
    """
    cfg = MosaicConfig.load(date)
    m = Manifest.load(date)
    shift = cfg.wavelength_shift
    return {
        "mosaic_date": date,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "iris_mosaics_commit": _git_commit(),
        "assembled_mosaic": _file_record(cfg.mosaic_path),
        "radiometric_factor": _file_record(cfg.radiometric_path),
        "wavelength_shift_angstrom": None if shift is None else float(shift.to(u.AA).value),
        "spectral_binning": cfg.spectral_binning,
        "num_img_per_raster": cfg.num_img_per_raster,
        "manifest": {
            step: entry.get("date") for step, entry in m.steps.items()
        },
        "notes": cfg.notes,
    }


# --------------------------------------------------------------------------
# the handoff
# --------------------------------------------------------------------------

@dataclasses.dataclass
class AssembledMosaic:
    """One mosaic, ready for science.

    ``data`` is the cropped cube in DN with axes (x, y, wavelength). ``wcs`` is
    the full 3-axis WCS *before* cropping, kept for anyone who needs the
    spectral axis; ``spatial_wcs`` is the 2-axis WCS of the cropped plane, which
    is what maps and annuli want. ``wavelength`` already includes the shift.
    ``dn2flux`` is on the same grid as ``wavelength``.
    """

    date: str
    data: np.ndarray
    wcs: object
    spatial_wcs: object
    wavelength: u.Quantity
    wavelength_shift: u.Quantity
    dn2flux: u.Quantity
    crop: tuple
    provenance: dict

    @property
    def shape(self):
        return self.data.shape

    def calibrate(self, dtype=np.float32) -> u.Quantity:
        """The cube in physical units: ``data * dn2flux`` along the spectral axis.

        Allocates a full copy of the cube. At ~17 GB for a deep mosaic that is
        a deliberate choice, which is why :func:`load` does not do it for you.
        """
        return (self.data.astype(dtype, copy=False) * self.dn2flux.value.astype(dtype)) * self.dn2flux.unit


def load(
    date: str,
    crop_half_width: u.Quantity = DEFAULT_CROP,
    require_ready: bool = True,
) -> AssembledMosaic:
    """Load a mosaic the way the science notebooks did, in one call.

    Reads the assembled mosaic, applies the config's wavelength shift, resamples
    the radiometric factor onto the wavelength axis, and crops the border. With
    ``require_ready`` the manifest and files are checked first and a clear
    error names whatever is missing.

    This reads a ~17 GB pickle; expect a few minutes and that much memory.
    """
    if require_ready:
        reasons = not_ready_reasons(date)
        if reasons:
            raise RuntimeError(
                f"mosaic {date} is not ready for science:\n  - " + "\n  - ".join(reasons)
            )

    cfg = MosaicConfig.load(date)
    if cfg.wavelength_shift is None:
        raise RuntimeError(f"mosaic {date} has no wavelength shift in its config")

    with open(cfg.mosaic_path, "rb") as f:
        fdm = pickle.load(f)
    data, wcs = fdm["data"], fdm["wcs"]
    wcs.array_shape = data.shape

    wavelength = wavelength_axis(wcs, data.shape[-1]) + cfg.wavelength_shift
    factor, factor_wave = read_dn2flux(cfg.radiometric_path)
    dn2flux = interpolate_dn2flux(factor, factor_wave, wavelength)

    data, spatial_wcs, crop = crop_to_disk(data, wcs, crop_half_width)

    return AssembledMosaic(
        date=date,
        data=data,
        wcs=wcs,
        spatial_wcs=spatial_wcs,
        wavelength=wavelength,
        wavelength_shift=cfg.wavelength_shift,
        dn2flux=dn2flux,
        crop=crop,
        provenance=provenance(date),
    )
