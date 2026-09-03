"""Solar-disk geometry on the mosaic grid.

Disk-centre fitting, radial distance and mu, equal-area annuli, and the
plotting-orientation helpers. Split out of ``read_full_disk_mosaic`` because
that module imports ``reproject``/``regridding`` for mosaic assembly, and the
science side needs only this geometry, which is plain numpy and astropy.
"""

from __future__ import annotations

import numpy as np


def _solar_axes(wcs):
    """0-based FITS-axis indices of (Solar X, Solar Y), read from CTYPE."""
    ctypes = [str(c).upper() for c in wcs.wcs.ctype]
    ax_x = next(i for i, c in enumerate(ctypes) if 'X' in c)
    ax_y = next(i for i, c in enumerate(ctypes) if 'Y' in c)
    return ax_x, ax_y


def for_plotting(data2d, wcs2d):
    """Return (image, wcs) oriented so Solar X is horizontal.

    WCSAxes draws the FIRST WCS axis along the horizontal, and a
    matched image must be indexed in reversed FITS order. So the WCS
    axes are swapped and the image transposed TOGETHER -- doing one
    without the other misregisters the image against the coordinate
    grid. Use this at the plot boundary only; keep all science in the
    native orientation.

    Usage:
        img, w = for_plotting(display[:, :, j], wcs2d)
        ax = plt.subplot(projection=w)
        ax.imshow(img, origin='lower')
    """
    ax_x, _ = _solar_axes(wcs2d)
    if ax_x == 0:
        return data2d, wcs2d  # already Solar X first
    return data2d.T, wcs2d.swapaxes(0, 1)


def solar_geometry(wcs, shape, rsun_arcsec, center=(0.0, 0.0)):
    """Per-pixel radial distance and mu on the mosaic spatial grid.

    Axis-order aware: which WCS axis is Solar X vs Solar Y is read
    from CTYPE, so this works with the native (Y, X) WCS from
    build_mosaic / build_mosaic_slices AND with a swapped plotting
    WCS -- as long as `shape` is the shape of the MATCHING array.
    For a 3-axis WCS the spectral axis must be FITS axis 1 (as built
    by build_mosaic); it is evaluated at pixel 0.

    Parameters
    ----------
    wcs : astropy.wcs.WCS
        2-axis spatial or 3-axis (WAVE, Solar Y, Solar X) WCS.
    shape : tuple
        Spatial shape of the matching array, in that array's own
        numpy order (e.g. data.shape[:2] for the cube, img.shape for
        a plotting-oriented image).
    rsun_arcsec : float
        Apparent solar radius at the mosaic epoch, in arcsec.
        Per-epoch value, e.g.:
            from sunpy.coordinates import sun
            rsun_arcsec = sun.angular_radius(date).to_value(u.arcsec)
    center : (float, float)
        Disk-center position (x0, y0) in arcsec, from
        find_disk_center. Fit per mosaic; do not reuse one epoch's
        offset for another.

    Returns
    -------
    r : ndarray, `shape`
        Radial distance from disk center in arcsec.
    mu : ndarray, `shape`
        cos(heliocentric angle); NaN off the disk (r > rsun).
    """
    n = wcs.naxis
    ax_x, ax_y = _solar_axes(wcs)
    idx = np.indices(shape)
    npts = idx[0].size

    args = []
    for a in range(n):
        if a in (ax_x, ax_y):
            args.append(idx[n - 1 - a].ravel())  # numpy axis of FITS axis a
        else:
            args.append(np.zeros(npts))  # dummy spectral pixel
    world = wcs.all_pix2world(*args, 0)

    wx = (((world[ax_x] + 180) % 360) - 180) * 3600.0  # deg -> arcsec
    wy = (((world[ax_y] + 180) % 360) - 180) * 3600.0

    r = np.hypot(wx - center[0], wy - center[1]).reshape(shape)

    with np.errstate(invalid='ignore'):
        mu = np.sqrt(1.0 - (r / rsun_arcsec) ** 2)  # NaN where r > rsun
    return r, mu


def annulus_labels(mu, n=9, off_limb='drop'):
    """Equal-solar-surface-area annulus label per pixel.

    Equal surface area on the sphere == equal Delta-mu, so annulus k
    (k = 0 ... n-1, 0 = center circle) is mu in (1-(k+1)/n, 1-k/n].

    Parameters
    ----------
    mu : ndarray
        From solar_geometry (NaN off-disk). Labels come out in the
        same orientation as the mu array passed in.
    n : int
        Number of annuli.
    off_limb : 'drop' or 'outer'
        Policy for off-disk pixels (r > rsun): -1 (excluded) or folded
        into the outermost annulus n-1. Use the SAME policy at every
        epoch.

    Returns
    -------
    labels : int ndarray, same shape; -1 = excluded.
    """
    labels = np.full(mu.shape, -1, dtype=int)
    on = np.isfinite(mu)
    labels[on] = np.clip(np.floor((1.0 - mu[on]) * n), 0, n - 1).astype(int)
    if off_limb == 'outer':
        labels[~on] = n - 1
    return labels


def annulus_radii(rsun_arcsec, n=9):
    """Outer boundary radii of the n equal-surface-area annuli, arcsec.

    r_k = R * sqrt(k * (2n - k)) / n,  k = 1 ... n
    """
    k = np.arange(1, n + 1)
    return rsun_arcsec * np.sqrt(k * (2 * n - k)) / n


def _fit_circle(x, y):
    """Algebraic (Kasa) least-squares circle fit. Returns x0, y0, R."""
    A = np.column_stack([2 * x, 2 * y, np.ones_like(x)])
    b = x ** 2 + y ** 2
    (a, bb, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    return a, bb, np.sqrt(c + a ** 2 + bb ** 2)


def find_disk_center(image, wcs2d, threshold=None):
    """Fit the disk center from the limb in a full-disk intensity image.

    Use a bright plane (e.g. the line-core slice from
    build_mosaic_slices, built with skip_saa=False so the limb has as
    few gaps as possible). Works in either orientation, as long as
    `image` and `wcs2d` are a matched pair. The fitted center applies
    to the science cube too -- the strips share the same world frame.

    Parameters
    ----------
    image : ndarray, 2D
        Intensity image; off-disk pixels dim or NaN.
    wcs2d : astropy.wcs.WCS
        The matching celestial WCS.
    threshold : float, optional
        Disk/off-disk intensity cut. Default: 0.2 x median of finite
        positive pixels. Check the printed edge-point count if the
        default misbehaves.

    Returns
    -------
    x0, y0 : float
        Disk-center offset in arcsec -- pass as `center=` to
        solar_geometry and plot_annuli. Log these per epoch.
    r_fit : float
        Fitted limb radius, arcsec. DIAGNOSTIC ONLY: expect it a few
        arcsec ABOVE the photospheric (ephemeris) radius, because TR
        emission extends above the photospheric limb. Keep using the
        ephemeris radius for mu and the annuli; use r_fit only as a
        sanity check that the fit converged sensibly.
    """
    img = np.asarray(image, dtype=float)
    finite = np.isfinite(img)
    if threshold is None:
        threshold = 0.2 * np.nanmedian(img[finite & (img > 0)])
    mask = finite & (img > threshold)

    # Outermost mask crossings along both axes -> limb edge points.
    # Interior gaps (missing strips) don't produce edge points along
    # their own axis; the ones they produce along the other axis are
    # removed by the outlier-rejection pass below.
    pts = []
    for i in range(mask.shape[0]):
        j = np.flatnonzero(mask[i])
        if j.size >= 2:
            pts.append((i, j[0]))
            pts.append((i, j[-1]))
    for j in range(mask.shape[1]):
        i = np.flatnonzero(mask[:, j])
        if i.size >= 2:
            pts.append((i[0], j))
            pts.append((i[-1], j))
    pts = np.array(pts, dtype=float)

    # numpy axis 0 <-> FITS axis 2, numpy axis 1 <-> FITS axis 1;
    # which world output is X vs Y is read from CTYPE.
    ax_x, ax_y = _solar_axes(wcs2d)
    world = wcs2d.all_pix2world(pts[:, 1], pts[:, 0], 0)
    wx = (((world[ax_x] + 180) % 360) - 180) * 3600.0
    wy = (((world[ax_y] + 180) % 360) - 180) * 3600.0

    x0, y0, r_fit = _fit_circle(wx, wy)

    # One robust rejection pass: drop points off the fitted circle
    # (missing-strip artifacts, stray bright features), then refit.
    resid = np.hypot(wx - x0, wy - y0) - r_fit
    mad = 1.4826 * np.median(np.abs(resid - np.median(resid)))
    keep = np.abs(resid - np.median(resid)) < 3 * max(mad, 1e-6)
    x0, y0, r_fit = _fit_circle(wx[keep], wy[keep])

    print(f'find_disk_center: {keep.sum()}/{keep.size} edge points, '
          f'center=({x0:+.2f}, {y0:+.2f})", r_fit={r_fit:.2f}"')
    return x0, y0, r_fit


def plot_annuli(ax, rsun_arcsec, n=9, center=(0.0, 0.0), **kwargs):
    """Overlay annulus boundaries on a WCSAxes plot of the mosaic.

    `center` is (x0, y0) in arcsec regardless of orientation; the
    world-coordinate order the transform expects is read from the
    axes' own WCS, so this works with both native and for_plotting
    orientations.

    Usage:
        img, w = for_plotting(display[:, :, j], wcs2d)
        ax = plt.subplot(projection=w)
        ax.imshow(img, origin='lower')
        plot_annuli(ax, rsun_arcsec, center=(x0, y0))
    """
    from matplotlib.patches import Circle
    style = dict(fill=False, edgecolor='w', linewidth=0.6, alpha=0.7)
    style.update(kwargs)
    ax_x, _ = _solar_axes(ax.wcs)
    cx, cy = center[0] / 3600.0, center[1] / 3600.0  # arcsec -> deg
    cworld = (cx, cy) if ax_x == 0 else (cy, cx)
    for r in annulus_radii(rsun_arcsec, n) / 3600.0:
        ax.add_patch(Circle(cworld, r,
                            transform=ax.get_transform('world'), **style))
