"""Two-step FUV background subtraction.

The background under the Si IV lines varies with where the instrument is
pointed, so it is estimated from the data rather than from a fixed model:

**Step 1** — mask the spectral lines and fiducials out of the rolling
trimmed-mean images, smooth what is left, and fill the masked regions by
Gauss-Seidel relaxation. The filled image is the background.

**Step 2** — fit whatever background survives step 1 with a low-order 2D
polynomial, per image, and subtract that too.

Both steps treat the detector's upper and lower taps separately: the tap
boundary is a hard discontinuity down the middle of the frame, and smoothing or
fitting across it would smear one tap's level into the other.

Together these remove essentially all the background, including some genuine
continuum. That is an accepted trade — the science target is the far wings of
the Si IV lines, not the continuum level.
"""

from __future__ import annotations

import numpy as np

#: Vacuum rest wavelengths, Angstrom.
SI_IV_1394 = 1393.757
SI_IV_1403 = 1402.770

C_KM_S = 299792.458


def velocity_to_pixels(velocity_km_s: float, wavelength: float, dispersion: float) -> float:
    """Half-width in pixels corresponding to a Doppler velocity.

    Used to decide how much of the spectrum around a line to mask: everything
    within ``velocity_km_s`` of line centre is considered line, not background.
    """
    return (velocity_km_s / C_KM_S) * wavelength / dispersion


def gauss_seidel_fill(images: np.ndarray, slices) -> np.ndarray:
    """Fill masked (NaN) regions by Gauss-Seidel relaxation, tap by tap.

    ``images`` is a stack; ``slices`` is the sequence of row slices that split
    the frame into independently-filled regions (the upper and lower taps).
    Relaxation is run separately within each, so no signal crosses the tap
    boundary.

    Requires ``pyinterp``.
    """
    import pyinterp
    import pyinterp.fill

    filled = np.empty_like(images, dtype=float)
    for region in slices:
        height, width = images[0][region].shape
        x_axis = pyinterp.Axis(np.arange(0, width, 1.0))
        y_axis = pyinterp.Axis(np.arange(0, height, 1.0))
        for i, image in enumerate(images):
            grid = pyinterp.Grid2D(y_axis, x_axis, image[region])
            _, region_filled = pyinterp.fill.gauss_seidel(grid)
            filled[i][region] = region_filled
    return filled


def fit_polynomial_background(
    images: np.ndarray,
    slices,
    line_mask: np.ndarray | None = None,
    degree: int = 3,
    quantiles: tuple[float, float] = (0.1, 0.9),
) -> np.ndarray:
    """Fit and return the residual background of each image (step 2).

    For every image: mask the spectral lines, drop pixels outside
    ``quantiles`` so bright features do not drag the fit, then fit a 2D
    polynomial of ``degree`` separately within each region of ``slices``.

    Images that are entirely NaN, and regions with nothing left to fit, are
    returned as NaN rather than raising.
    """
    from astropy.modeling import fitting, models

    p_init = models.Polynomial2D(degree=degree)
    fit_p = fitting.LevMarLSQFitter()

    background = np.full(images.shape, np.nan, dtype=float)

    for i, image in enumerate(images):
        image = image.copy()
        if line_mask is not None:
            image[line_mask] = np.nan

        q_low, q_high = np.nanquantile(image, quantiles)
        image[image > q_high] = np.nan
        image[image < q_low] = np.nan

        finite = np.isfinite(image)
        if not finite.any():
            continue

        for region in slices:
            region_finite = finite[region]
            if not region_finite.any():
                continue
            height, width = image[region].shape
            y, x = np.mgrid[:height, :width]
            fit = fit_p(
                p_init,
                x[region_finite],
                y[region_finite],
                image[region][region_finite],
            )
            background[i][region] = fit(x, y)

    return background
