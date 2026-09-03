"""Tests for the disk geometry helpers, in particular axis identification.

The assembled mosaic's WCS names its axes "Solar Y"/"Solar X"; the level 1.5
files that feed it use HPLT-TAN/HPLN-TAN. Both must resolve to the same
(x, y) axis indices or every downstream map is transposed.
"""

import astropy.wcs
import numpy as np
import pytest

from iris_mosaics import geometry


def wcs_with(ctypes, cunit="deg"):
    w = astropy.wcs.WCS(naxis=len(ctypes))
    w.wcs.ctype = ctypes
    w.wcs.cunit = ["m" if c == "WAVE" else cunit for c in ctypes]
    w.wcs.crpix = [1] * len(ctypes)
    w.wcs.crval = [0] * len(ctypes)
    w.wcs.cdelt = [1e-10 if c == "WAVE" else 1 / 3600 for c in ctypes]
    return w


@pytest.mark.parametrize(
    "ctypes, expected",
    [
        (["Solar Y", "Solar X"], (1, 0)),                 # the assembled mosaic
        (["WAVE", "Solar Y", "Solar X"], (2, 1)),         # its 3-axis parent
        (["HPLT-TAN", "HPLN-TAN"], (1, 0)),               # level 1.5 files
        (["WAVE", "HPLT-TAN", "HPLN-TAN"], (2, 1)),
        (["HPLN-TAN", "HPLT-TAN"], (0, 1)),               # the other order
        (["SOLAR-X", "SOLAR-Y"], (0, 1)),
    ],
)
def test_solar_axes_recognises_both_naming_conventions(ctypes, expected):
    assert geometry._solar_axes(wcs_with(ctypes)) == expected


def test_solar_axes_rejects_unidentifiable_axes():
    with pytest.raises(ValueError, match="cannot identify"):
        geometry._solar_axes(wcs_with(["RA---TAN", "DEC--TAN"]))


def test_solar_geometry_is_the_same_under_both_conventions():
    """mu must not depend on which names the WCS happens to use."""
    shape = (30, 40)
    # 20.3, not 20.0: at 1"/pixel a few pixels sit at exactly r = 20, and the
    # TAN and linear projections differ there at the 1e-10 level, which is
    # enough to flip the on/off-disk test for those pixels alone.
    r1, mu1 = geometry.solar_geometry(wcs_with(["Solar Y", "Solar X"]), shape, 20.3)
    r2, mu2 = geometry.solar_geometry(wcs_with(["HPLT-TAN", "HPLN-TAN"]), shape, 20.3)
    # HPLN/HPLT-TAN is a gnomonic projection, "Solar X/Y" is linear; within a
    # few tens of arcsec of the reference point they differ at the 1e-7 level,
    # which is far below anything the analysis resolves.
    np.testing.assert_allclose(r1, r2, rtol=1e-5, atol=1e-6)
    np.testing.assert_array_equal(np.isnan(mu1), np.isnan(mu2))
    np.testing.assert_allclose(mu1[np.isfinite(mu1)], mu2[np.isfinite(mu2)], rtol=1e-5, atol=1e-6)


def test_annulus_labels_equal_area_policy():
    mu = np.array([1.0, 0.95, 0.5, 0.05, np.nan])
    labels = geometry.annulus_labels(mu, n=9, off_limb="drop")
    assert labels[0] == 0 and labels[-1] == -1
    assert labels[3] == 8
    folded = geometry.annulus_labels(mu, n=9, off_limb="outer")
    assert folded[-1] == 8
