"""Raster geometry: locating raster boundaries and padding gaps.

A mosaic is a sequence of spectrograph images taken as a series of rasters, each
nominally ``num_img_per_raster`` images stepping in solar x. Images go missing,
both inside a raster and off its ends, so the image sequence does not reshape
cleanly into a (raster, image) grid until the gaps are padded with NaNs.

This logic was previously duplicated, cell for cell, in
``apply_rolling_trimmed_mean.ipynb`` and ``wavelength_calibration.ipynb``.

Typical use::

    solar_x, solar_y, t_obs = read_pointing(files)
    layout = plan_rasters(solar_x, num_img_per_raster=64)
    cube_padded = layout.pad(cube)                 # NaN-filled gaps
    cube_rasters = layout.to_rasters(cube_padded)  # (n_raster, n_img, ny, nx)
    ...                                            # filter along the raster axis
    cube_flat = layout.from_rasters(cube_rasters)
    cube_out = layout.unpad(cube_flat)             # back to original length

``pad`` and ``unpad`` are exact inverses: ``unpad`` removes precisely the frames
``pad`` inserted, tracked by index rather than recomputed.
"""

from __future__ import annotations

import dataclasses

import astropy.time
import numpy as np


def read_pointing(files, fuv_channel: str = "fuv2"):
    """Read pointing and observation time from each file's header.

    Returns ``(solar_x, solar_y, t_obs)`` where the first two are arrays of
    arcsec (header ``CRVAL3``/``CRVAL2``) and ``t_obs`` is an
    :class:`astropy.time.Time`.
    """
    from .read_full_disk_mosaic import read_sg_image  # heavy deps, load on use

    solar_x, solar_y, t_obs = [], [], []
    for file in files:
        _, hdu, _ = read_sg_image(file, fuv_channel)
        solar_x.append(hdu[0].header["CRVAL3"])
        solar_y.append(hdu[0].header["CRVAL2"])
        t_obs.append(hdu[0].header["T_OBS"])
    return np.array(solar_x), np.array(solar_y), astropy.time.Time(t_obs)


@dataclasses.dataclass
class RasterLayout:
    """How an image sequence maps onto a (raster, image) grid.

    ``source_index`` is the core of it: one entry per padded frame, holding the
    index of the original image it came from, or -1 for an inserted NaN frame.
    """

    num_img_per_raster: int
    source_index: np.ndarray
    solar_x_filled: np.ndarray
    missing_image_index: np.ndarray
    raster_jump_index: np.ndarray
    length_of_rasters: np.ndarray
    raster_missing_end_index: np.ndarray
    num_missing_images: np.ndarray

    @property
    def num_images_original(self) -> int:
        return int(np.count_nonzero(self.source_index >= 0))

    @property
    def num_images_padded(self) -> int:
        return int(self.source_index.size)

    @property
    def num_rasters(self) -> int:
        return self.num_images_padded // self.num_img_per_raster

    @property
    def inserted(self) -> np.ndarray:
        """Boolean mask over padded frames: True where a NaN frame was inserted."""
        return self.source_index < 0

    def pad(self, cube: np.ndarray) -> np.ndarray:
        """Insert NaN frames so the sequence divides evenly into rasters."""
        if cube.shape[0] != self.num_images_original:
            raise ValueError(
                f"cube has {cube.shape[0]} images, layout expects "
                f"{self.num_images_original}"
            )
        out = np.full(
            (self.num_images_padded, *cube.shape[1:]), np.nan, dtype=float
        )
        real = ~self.inserted
        out[real] = cube[self.source_index[real]]
        return out

    def unpad(self, cube: np.ndarray) -> np.ndarray:
        """Remove exactly the frames :meth:`pad` inserted."""
        if cube.shape[0] != self.num_images_padded:
            raise ValueError(
                f"cube has {cube.shape[0]} images, layout expects "
                f"{self.num_images_padded}"
            )
        order = np.argsort(self.source_index[~self.inserted])
        return cube[~self.inserted][order]

    def to_rasters(self, cube: np.ndarray) -> np.ndarray:
        """Reshape a padded cube to ``(n_raster, num_img_per_raster, ...)``."""
        if cube.shape[0] != self.num_images_padded:
            raise ValueError(
                f"cube has {cube.shape[0]} images, expected {self.num_images_padded}; "
                "call pad() first"
            )
        return cube.reshape(self.num_rasters, self.num_img_per_raster, *cube.shape[1:])

    @staticmethod
    def from_rasters(cube: np.ndarray) -> np.ndarray:
        """Collapse the raster axis back into a flat image sequence."""
        return cube.reshape(-1, *cube.shape[2:])


def plan_rasters(
    solar_x: np.ndarray,
    num_img_per_raster: int = 64,
    step_arcsec: float = 2.0,
    gap_range: tuple[float, float] = (3.0, 5.0),
) -> RasterLayout:
    """Work out where images are missing and how the sequence splits into rasters.

    Gaps *within* a raster show up as a jump in ``solar_x`` larger than the
    nominal step but smaller than a full slew — ``gap_range`` bounds that. A
    negative jump marks the start of the next raster. Rasters left with fewer
    than ``num_img_per_raster`` images are padded at their start.

    No data is touched here; use :meth:`RasterLayout.pad` for that.
    """
    solar_x = np.asarray(solar_x)
    n = solar_x.size

    # Gaps inside a raster: one image missing between i and i+1.
    diff = np.diff(solar_x)
    missing_image_index = np.nonzero((diff > gap_range[0]) & (diff < gap_range[1]))[0]

    # Build the padded ordering. -1 marks an inserted frame.
    source_index = []
    solar_x_filled = []
    missing_set = set(missing_image_index.tolist())
    for i in range(n):
        source_index.append(i)
        solar_x_filled.append(solar_x[i])
        if i in missing_set:
            source_index.append(-1)
            solar_x_filled.append(solar_x[i] + step_arcsec)
    source_index = np.array(source_index)
    solar_x_filled = np.array(solar_x_filled)

    # Raster boundaries: solar_x jumps backwards at the start of each raster.
    raster_jump_index = np.nonzero(np.diff(solar_x_filled) < 0)[0] + 1
    raster_jump_index = np.insert(raster_jump_index, 0, 0)
    raster_jump_index = np.append(raster_jump_index, len(solar_x_filled))

    length_of_rasters = np.diff(raster_jump_index)
    raster_missing_end_index = np.nonzero(length_of_rasters < num_img_per_raster)[0]
    num_missing_images = num_img_per_raster - length_of_rasters[raster_missing_end_index]

    # Pad short rasters at their start. Walk backwards so earlier offsets hold.
    for k in range(len(raster_missing_end_index) - 1, -1, -1):
        start = raster_jump_index[raster_missing_end_index[k]]
        pad = np.full(num_missing_images[k], -1)
        source_index = np.insert(source_index, start, pad)
        solar_x_filled = np.insert(
            solar_x_filled, start, np.full(num_missing_images[k], np.nan)
        )

    total = source_index.size
    if total % num_img_per_raster:
        raise ValueError(
            f"after padding, {total} images do not divide into rasters of "
            f"{num_img_per_raster}. Check gap_range={gap_range} and "
            f"num_img_per_raster."
        )

    return RasterLayout(
        num_img_per_raster=num_img_per_raster,
        source_index=source_index,
        solar_x_filled=solar_x_filled,
        missing_image_index=missing_image_index,
        raster_jump_index=raster_jump_index,
        length_of_rasters=length_of_rasters,
        raster_missing_end_index=raster_missing_end_index,
        num_missing_images=num_missing_images,
    )
