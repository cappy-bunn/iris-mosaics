"""Tests for the processing steps hoisted out of the notebooks."""

import astropy.units as u
import numpy as np
import pytest

from iris_mosaics import background, despike, fixed_pattern


# --------------------------------------------------------------------------
# fixed pattern
# --------------------------------------------------------------------------

def test_off_disk_mask_marks_outside_the_occulting_radius():
    x = np.array([0, 0, 2000, 0]) * u.arcsec
    y = np.array([0, 500, 0, 2000]) * u.arcsec
    mask = fixed_pattern.off_disk_mask(x, y, limb_radius=960 * u.arcsec, margin=60 * u.arcsec)
    # disk centre and 500" out are on-disk; 2000" out is off-disk
    assert not mask[0] and not mask[1]
    assert mask[2] and mask[3]


def test_off_disk_margin_widens_the_exclusion():
    x = np.array([1000.0]) * u.arcsec
    y = np.array([0.0]) * u.arcsec
    assert fixed_pattern.off_disk_mask(x, y, 960 * u.arcsec, margin=0 * u.arcsec)[0]
    # with a 60" margin the same pixel falls inside the occulting disk
    assert not fixed_pattern.off_disk_mask(x, y, 960 * u.arcsec, margin=60 * u.arcsec)[0]


def test_off_disk_center_offset_shifts_the_circle():
    x = np.array([-1000.0]) * u.arcsec
    y = np.array([0.0]) * u.arcsec
    plain = fixed_pattern.off_disk_mask(x, y, 960 * u.arcsec, margin=0 * u.arcsec)
    shifted = fixed_pattern.off_disk_mask(
        x, y, 960 * u.arcsec, margin=0 * u.arcsec,
        center_offset=(100 * u.arcsec, 0 * u.arcsec),
    )
    assert plain[0]        # 1000" from an unshifted centre -> off disk
    assert not shifted[0]  # shifting the centre brings it inside


def test_off_disk_mask_does_not_mutate_its_input():
    x = np.array([100.0]) * u.arcsec
    y = np.array([0.0]) * u.arcsec
    fixed_pattern.off_disk_mask(x, y, 960 * u.arcsec,
                                center_offset=(50 * u.arcsec, 0 * u.arcsec))
    assert x[0] == 100 * u.arcsec


def test_one_sided_trimmed_mean_discards_the_bright_tail():
    # 9 values at 1.0 and one huge outlier; cutting 10% removes the outlier
    cube = np.ones((10, 1, 1))
    cube[-1] = 1000.0
    result = fixed_pattern.one_sided_trimmed_mean(cube, percent_to_cut=10)
    assert result[0, 0] == pytest.approx(1.0)


def test_one_sided_trimmed_mean_keeps_low_values():
    """Only the high side is trimmed -- faint pixels must survive."""
    cube = np.ones((10, 1, 1))
    cube[0] = -5.0
    result = fixed_pattern.one_sided_trimmed_mean(cube, percent_to_cut=10)
    assert result[0, 0] < 1.0


def test_one_sided_trimmed_mean_does_not_mutate_input():
    cube = np.ones((10, 1, 1))
    cube[-1] = 1000.0
    fixed_pattern.one_sided_trimmed_mean(cube, percent_to_cut=10)
    assert cube[-1, 0, 0] == 1000.0


def test_chunked_nanmean_matches_numpy():
    rng = np.random.default_rng(0)
    cube = rng.normal(size=(37, 5, 6))
    cube[rng.random(cube.shape) < 0.2] = np.nan
    np.testing.assert_allclose(
        fixed_pattern.chunked_nanmean(cube, chunks=5),
        np.nanmean(cube, axis=0),
    )


def test_chunked_nanmean_all_nan_column_is_nan():
    cube = np.full((4, 2, 2), np.nan)
    cube[:, 0, 0] = 1.0
    result = fixed_pattern.chunked_nanmean(cube)
    assert result[0, 0] == 1.0
    assert np.isnan(result[1, 1])


# --------------------------------------------------------------------------
# despike
# --------------------------------------------------------------------------

def test_replace_nans_swaps_in_the_sentinel():
    cube = np.array([[[1.0, np.nan], [np.nan, 4.0]]])
    out, mask = despike.replace_nans(cube)
    assert (out == despike.NAN_SENTINEL).sum() == 2
    assert mask.sum() == 2
    assert np.isfinite(out).all()


def test_flag_mostly_nan_images():
    nan_mask = np.zeros((3, 10, 10), dtype=bool)
    nan_mask[1, :, :] = True       # 100% NaN
    nan_mask[2, 0, 0] = True       # 1 pixel in 100 -> 1%, not above threshold
    flagged = despike.flag_mostly_nan_images(nan_mask, threshold=0.01)
    assert not flagged[0]
    assert flagged[1]
    assert not flagged[2]


def test_count_spikes_per_image():
    spike_mask = np.zeros((3, 4, 4), dtype=bool)
    spike_mask[0, 0, 0] = True
    spike_mask[2, :, 0] = True
    np.testing.assert_array_equal(despike.count_spikes(spike_mask), [1, 0, 4])


# --------------------------------------------------------------------------
# background
# --------------------------------------------------------------------------

def test_velocity_to_pixels():
    # 90 km/s at Si IV 1394 with 0.0127 A/pix
    width = background.velocity_to_pixels(90, background.SI_IV_1394, 0.0127)
    assert width == pytest.approx(32.9, abs=0.5)


def test_velocity_to_pixels_scales_linearly():
    a = background.velocity_to_pixels(50, background.SI_IV_1394, 0.0127)
    b = background.velocity_to_pixels(100, background.SI_IV_1394, 0.0127)
    assert b == pytest.approx(2 * a)


def test_polynomial_background_recovers_a_plane():
    """A known low-order background must be fit back out."""
    height, width = 20, 30
    y, x = np.mgrid[:height, :width]
    truth = 3.0 + 0.5 * x + 0.25 * y
    images = truth[None].astype(float).copy()

    fit = background.fit_polynomial_background(
        images, slices=[slice(None)], degree=1, quantiles=(0.0, 1.0)
    )
    np.testing.assert_allclose(fit[0], truth, rtol=1e-6)


def test_polynomial_background_fits_taps_independently():
    """The tap boundary is a hard step; each side must be fit on its own."""
    height, width = 20, 10
    images = np.zeros((1, height, width))
    images[0, :10] = 5.0    # upper tap
    images[0, 10:] = 50.0   # lower tap

    slices = [slice(0, 10), slice(10, 20)]
    fit = background.fit_polynomial_background(
        images, slices=slices, degree=1, quantiles=(0.0, 1.0)
    )
    assert fit[0, :10].mean() == pytest.approx(5.0, abs=0.1)
    assert fit[0, 10:].mean() == pytest.approx(50.0, abs=0.1)


def test_polynomial_background_skips_all_nan_images():
    images = np.full((2, 8, 8), np.nan)
    y, x = np.mgrid[:8, :8]
    images[1] = 1.0 + 0.1 * x
    fit = background.fit_polynomial_background(
        images, slices=[slice(None)], degree=1, quantiles=(0.0, 1.0)
    )
    assert np.isnan(fit[0]).all()
    assert np.isfinite(fit[1]).all()


def test_polynomial_background_applies_the_line_mask():
    """Masked pixels must not pull the fit toward the line's brightness."""
    height, width = 12, 12
    images = np.ones((1, height, width))
    line_mask = np.zeros((height, width), dtype=bool)
    line_mask[:, 5:7] = True
    images[0][line_mask] = 500.0   # a bright "line"

    fit = background.fit_polynomial_background(
        images, slices=[slice(None)], line_mask=line_mask,
        degree=1, quantiles=(0.0, 1.0),
    )
    # the fit should follow the background level of 1, not the 500 line
    assert fit[0].mean() == pytest.approx(1.0, abs=0.1)
