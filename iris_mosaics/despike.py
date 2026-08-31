"""Cosmic-ray / spike removal.

Wraps Astro-SCRAPPY's ``detect_cosmics`` so it can be applied across an
arbitrarily-shaped stack of spectrograph images.

Two details matter and are easy to get wrong:

- **Padding.** ``detect_cosmics`` behaves badly at frame edges, so each image is
  padded before detection and the pad is trimmed off afterwards.
- **NaNs.** The despiker mishandles spikes adjacent to NaNs. The pipeline
  therefore replaces NaN pixels with a large sentinel (16384) *before* calling
  this, letting the despiker treat them as spikes and repair them. Those pixels
  are deliberately not restored to NaN afterwards — see the runbook.
"""

from __future__ import annotations

import astroscrappy
import numpy as np

#: Value the pipeline substitutes for NaN before despiking, large enough that
#: the despiker treats it as a spike and repairs it.
NAN_SENTINEL = 16384


def despike_cube(
    cube: np.ndarray,
    axis: tuple[int, int] = (-2, -1),
    pad_width: int = 5,
    **kwargs,
):
    """Despike every image in a stack.

    ``cube`` may have any number of leading axes; ``axis`` names the two image
    axes. Returns ``(despiked, spike_mask)`` with the same shape as ``cube``.

    Extra keyword arguments go to :func:`astroscrappy.detect_cosmics`
    (``sigclip``, ``objlim``, ``readnoise``, ...).

    ``pad_width`` is padded onto each image before detection and trimmed after;
    raise it if spikes near the frame edge are being missed.
    """
    axis_new = (-2, -1)
    cube_new = np.moveaxis(cube, source=axis, destination=axis_new)

    result = np.empty_like(cube)
    result_mask = np.empty_like(cube, dtype=bool)

    shape_orthogonal = tuple(np.array(cube.shape)[:-2])
    for index in np.ndindex(*shape_orthogonal):
        mask_i, result_i = astroscrappy.detect_cosmics(
            indat=np.pad(cube_new[index], pad_width=pad_width),
            **kwargs,
        )
        trim = (
            ...,
            slice(pad_width, -pad_width or None),
            slice(pad_width, -pad_width or None),
        )
        result[index] = result_i[trim]
        result_mask[index] = mask_i[trim]

    result = np.moveaxis(result, source=axis_new, destination=axis)
    result_mask = np.moveaxis(result_mask, source=axis_new, destination=axis)
    return result, result_mask


def replace_nans(cube: np.ndarray, sentinel: int = NAN_SENTINEL):
    """Swap NaNs for the sentinel so the despiker can repair them.

    Returns ``(cube, nan_mask)``. ``cube`` is modified in place.
    """
    nan_mask = ~np.isfinite(cube)
    cube[nan_mask] = sentinel
    return cube, nan_mask


def flag_mostly_nan_images(nan_mask: np.ndarray, threshold: float = 0.01):
    """Images too full of NaNs to be worth despiking.

    Returns a boolean mask over the leading axis, True where the fraction of
    NaN pixels exceeds ``threshold``. Those images are set entirely to NaN
    rather than repaired.
    """
    axes = tuple(range(1, nan_mask.ndim))
    fraction = nan_mask.sum(axis=axes) / np.prod(nan_mask.shape[1:])
    return fraction > threshold


def count_spikes(spike_mask: np.ndarray) -> np.ndarray:
    """Number of spikes found in each image."""
    axes = tuple(range(1, spike_mask.ndim))
    return np.nansum(spike_mask, axis=axes)
