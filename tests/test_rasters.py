"""Tests for raster gap-filling and reshaping."""

import numpy as np
import pytest

from iris_mosaics.rasters import plan_rasters


def make_solar_x(n_raster, n_img, step=2.0, drop=()):
    """Build a solar_x sequence, optionally dropping given (raster, image) frames."""
    xs = []
    for r in range(n_raster):
        for i in range(n_img):
            if (r, i) in drop:
                continue
            xs.append(i * step)
    return np.array(xs, dtype=float)


def test_complete_sequence_needs_no_padding():
    solar_x = make_solar_x(3, 8)
    layout = plan_rasters(solar_x, num_img_per_raster=8)
    assert layout.num_rasters == 3
    assert layout.num_images_padded == 24
    assert not layout.inserted.any()


def test_gap_inside_a_raster_is_filled():
    # drop one image from the middle of raster 1
    solar_x = make_solar_x(3, 8, drop={(1, 4)})
    layout = plan_rasters(solar_x, num_img_per_raster=8)
    assert layout.num_images_original == 23
    assert layout.num_images_padded == 24
    assert layout.inserted.sum() == 1
    assert layout.num_rasters == 3


def test_missing_frames_off_the_end_are_filled():
    # drop the last two images of raster 2 -> a short raster at the end
    solar_x = make_solar_x(3, 8, drop={(2, 6), (2, 7)})
    layout = plan_rasters(solar_x, num_img_per_raster=8)
    assert layout.num_images_padded == 24
    assert layout.inserted.sum() == 2


def test_pad_unpad_roundtrip_is_exact():
    solar_x = make_solar_x(4, 8, drop={(1, 3), (2, 0), (2, 1), (3, 5)})
    layout = plan_rasters(solar_x, num_img_per_raster=8)

    cube = np.arange(layout.num_images_original * 2 * 3, dtype=float)
    cube = cube.reshape(layout.num_images_original, 2, 3)

    padded = layout.pad(cube)
    assert padded.shape[0] == layout.num_images_padded
    assert np.isnan(padded[layout.inserted]).all()

    recovered = layout.unpad(padded)
    np.testing.assert_array_equal(recovered, cube)


def test_roundtrip_survives_the_raster_reshape():
    """pad -> to_rasters -> from_rasters -> unpad must return the original."""
    solar_x = make_solar_x(4, 8, drop={(1, 3), (2, 0), (3, 5), (3, 6)})
    layout = plan_rasters(solar_x, num_img_per_raster=8)

    cube = np.random.default_rng(0).normal(
        size=(layout.num_images_original, 2, 3)
    )
    rasters = layout.to_rasters(layout.pad(cube))
    assert rasters.shape[:2] == (layout.num_rasters, 8)

    flat = layout.from_rasters(rasters)
    np.testing.assert_allclose(layout.unpad(flat), cube)


def test_differing_numbers_of_missing_images_per_raster():
    """Two short rasters missing *different* counts must both come back right.

    This is the case the original notebook code mishandled: the removal loop
    walked the rasters in ascending order while indexing the per-raster missing
    counts in descending order.
    """
    solar_x = make_solar_x(4, 8, drop={(1, 0), (3, 0), (3, 1), (3, 2)})
    layout = plan_rasters(solar_x, num_img_per_raster=8)
    assert sorted(layout.num_missing_images.tolist()) == [1, 3]

    cube = np.arange(layout.num_images_original, dtype=float)[:, None, None]
    cube = np.broadcast_to(cube, (layout.num_images_original, 2, 2)).copy()
    np.testing.assert_array_equal(layout.unpad(layout.pad(cube)), cube)


def test_indivisible_sequence_raises():
    """A raster longer than num_img_per_raster cannot be padded into shape.

    Short rasters are filled, so the failure mode that actually reaches the
    check is an over-long one -- normally meaning num_img_per_raster is wrong
    for this mosaic.
    """
    solar_x = make_solar_x(2, 10)  # 10 images per raster, but we claim 8
    with pytest.raises(ValueError, match="do not divide into rasters"):
        plan_rasters(solar_x, num_img_per_raster=8)


def test_pad_rejects_wrong_length_cube():
    layout = plan_rasters(make_solar_x(2, 8), num_img_per_raster=8)
    with pytest.raises(ValueError, match="layout expects"):
        layout.pad(np.zeros((5, 2, 2)))
