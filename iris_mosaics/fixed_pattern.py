"""Fixed-pattern removal from off-disk pixels.

The detector carries a fixed pattern that shows up wherever there is no solar
signal. Estimating it from **off-disk** pixels — those outside an occulting
radius drawn generously around the limb — and subtracting removes it.

Must run *before* despiking: the despiker would otherwise remove part of the
fixed pattern, corrupting the estimate.

The occulting geometry is per mosaic (the disk is not perfectly centred in the
pointing, and the limb radius changes through the year), so it comes from
``config/<date>.yaml`` rather than being edited into the notebook.
"""

from __future__ import annotations

import astropy.units as u
import numpy as np


def off_disk_mask(
    x: u.Quantity,
    y: u.Quantity,
    limb_radius: u.Quantity,
    margin: u.Quantity = 60 * u.arcsec,
    center_offset: tuple[u.Quantity, u.Quantity] = (0 * u.arcsec, 0 * u.arcsec),
) -> np.ndarray:
    """True where a pixel lies outside the occulting disk.

    ``margin`` is added to the limb radius so that near-limb stray light does
    not contaminate the estimate. ``center_offset`` recentres the circle on the
    actual disk, which the pointing does not place exactly at the origin.

    ``x`` is wrapped into [-180°, 180°] first — helioprojective longitudes come
    back near 360° on one side otherwise.
    """
    x = x.copy()
    wrapped = abs(x) > 180 * u.deg
    x[wrapped] = x[wrapped] % (360 * u.deg)

    x = x + center_offset[0]
    y = y + center_offset[1]

    radius = limb_radius + margin
    return np.square(x) + np.square(y) > np.square(radius)


def off_disk_mask_from_config(x, y, cfg, header=None):
    """:func:`off_disk_mask` with the geometry taken from a :class:`MosaicConfig`.

    If the config leaves ``limb_radius_arcsec`` null, the value is read from the
    FITS header keyword ``RSUN_OBS`` and the config's margin applied on top.
    """
    if cfg.limb_radius is not None:
        limb_radius = cfg.limb_radius
    elif header is not None and "RSUN_OBS" in header:
        limb_radius = header["RSUN_OBS"] * u.arcsec + 10 * u.arcsec
    else:
        raise ValueError(
            f"mosaic {cfg.date} has no limb_radius_arcsec in its config and no "
            "RSUN_OBS header was supplied"
        )
    return off_disk_mask(
        x, y,
        limb_radius=limb_radius,
        margin=cfg.off_disk_margin,
        center_offset=cfg.disk_center_offset,
    )


def one_sided_trimmed_mean(
    cube: np.ndarray, percent_to_cut: float = 10.0, axis: int = 0
) -> np.ndarray:
    """Mean over ``axis`` after discarding the brightest ``percent_to_cut``%.

    Only the high side is trimmed: the off-disk distribution has a bright tail
    from residual spikes and stray light, but no significant low-end outliers.

    ``cube`` is not modified.
    """
    cube = cube.copy()
    upper = np.nanpercentile(cube, 100 - percent_to_cut, axis=axis)
    cube[cube > upper] = np.nan
    return np.nanmean(cube, axis=axis)


def chunked_nanmean(cube: np.ndarray, axis: int = 0, chunks: int = 8) -> np.ndarray:
    """``np.nanmean`` over ``axis`` for cubes too large to hold in memory.

    Accumulates a running sum and count over slices of the remaining axes.
    Equivalent to ``np.nanmean(cube, axis=axis)`` but with a bounded footprint.
    """
    if axis != 0:
        cube = np.moveaxis(cube, axis, 0)
    shape = cube.shape[1:]
    total = np.zeros(shape, dtype=float)
    count = np.zeros(shape, dtype=int)
    step = max(1, cube.shape[0] // chunks)
    for start in range(0, cube.shape[0], step):
        block = cube[start:start + step]
        finite = np.isfinite(block)
        total += np.where(finite, block, 0).sum(axis=0)
        count += finite.sum(axis=0)
    with np.errstate(invalid="ignore"):
        return np.where(count > 0, total / count, np.nan)
