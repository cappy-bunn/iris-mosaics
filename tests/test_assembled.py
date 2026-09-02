"""Tests for the pipeline-to-science handoff.

The pure pieces (wavelength axis, crop, radiometric resampling) are tested on
synthetic WCSs and arrays. Readiness and provenance are tested against a
temporary config and manifest. Nothing here touches the 17 GB mosaics.
"""

import pathlib as pl

import astropy.units as u
import astropy.wcs
import numpy as np
import pytest
from astropy.io import fits

from iris_mosaics import assembled, manifest
from iris_mosaics.config import MosaicConfig
from iris_mosaics.manifest import Manifest


# --------------------------------------------------------------------------
# synthetic geometry shaped like a real assembled mosaic
# --------------------------------------------------------------------------

def make_wcs(n_wave=50, n_y=40, n_x=30, pix_arcsec=2.0, wave0_A=1390.0, dwave_A=0.05):
    """3-axis WCS: (wavelength in m, solar-y in deg, solar-x in deg).

    The spatial axes are centred so that world (0, 0) is mid-image, which is
    what lets the crop test reason about which pixels survive.
    """
    w = astropy.wcs.WCS(naxis=3)
    w.wcs.ctype = ["WAVE", "HPLT-TAN", "HPLN-TAN"]
    w.wcs.cunit = ["m", "deg", "deg"]
    w.wcs.crpix = [1, (n_y + 1) / 2, (n_x + 1) / 2]
    w.wcs.crval = [wave0_A * 1e-10, 0.0, 0.0]
    w.wcs.cdelt = [dwave_A * 1e-10, pix_arcsec / 3600, pix_arcsec / 3600]
    w.array_shape = (n_x, n_y, n_wave)
    return w


def test_wavelength_axis_matches_the_wcs():
    w = make_wcs(n_wave=5, wave0_A=1390.0, dwave_A=0.05)
    axis = assembled.wavelength_axis(w, 5)
    assert axis.unit == u.AA
    np.testing.assert_allclose(axis.value, [1390.0, 1390.05, 1390.10, 1390.15, 1390.20], atol=1e-6)


def test_crop_keeps_only_the_square_around_the_disk():
    n_x, n_y, n_wave = 30, 40, 5
    w = make_wcs(n_wave=n_wave, n_y=n_y, n_x=n_x, pix_arcsec=2.0)
    data = np.arange(n_x * n_y * n_wave, dtype=float).reshape(n_x, n_y, n_wave)

    # ±10" at 2"/pixel keeps about 11 pixels on each spatial axis
    cropped, spatial_wcs, (kmin, kmax, jmin, jmax) = assembled.crop_to_disk(
        data, w, half_width=10 * u.arcsec
    )
    assert cropped.shape[-1] == n_wave, "spectral axis untouched"
    assert cropped.shape[0] == kmax - kmin + 1
    assert cropped.shape[1] == jmax - jmin + 1
    assert 9 <= cropped.shape[0] <= 12 and 9 <= cropped.shape[1] <= 12
    assert spatial_wcs.naxis == 2, "spectral axis dropped from the WCS"


def test_crop_slice_is_inclusive_of_max():
    """The notebooks used kmax + 1; a plain [kmin:kmax] would drop a row."""
    w = make_wcs(n_y=40, n_x=30, pix_arcsec=2.0)
    data = np.zeros((30, 40, 5))
    cropped, _, (kmin, kmax, jmin, jmax) = assembled.crop_to_disk(data, w, 10 * u.arcsec)
    assert cropped.shape[0] == kmax - kmin + 1


def test_crop_is_a_view_not_a_copy():
    """A 17 GB cube must not be duplicated by cropping."""
    w = make_wcs()
    data = np.zeros((30, 40, 50))
    cropped, _, _ = assembled.crop_to_disk(data, w, 10 * u.arcsec)
    assert np.shares_memory(cropped, data)


# --------------------------------------------------------------------------
# radiometric factor
# --------------------------------------------------------------------------

def test_interpolate_dn2flux_is_exact_for_linear_data():
    fw = np.linspace(1354.0, 1407.0, 100) * u.AA
    factor = (2.0 + 0.01 * (fw.value - 1354.0)) * u.Unit("W nm-1 sr-1 m-2")
    wave = np.array([1360.0, 1380.123, 1400.0]) * u.AA
    out = assembled.interpolate_dn2flux(factor, fw, wave)
    np.testing.assert_allclose(out.value, 2.0 + 0.01 * (wave.value - 1354.0), rtol=1e-9)
    assert out.unit == factor.unit


def test_interpolate_dn2flux_refuses_to_extrapolate():
    fw = np.linspace(1354.0, 1407.0, 100) * u.AA
    factor = np.ones(100) * u.Unit("W nm-1 sr-1 m-2")
    with pytest.raises(ValueError, match="extends beyond"):
        assembled.interpolate_dn2flux(factor, fw, np.array([1350.0, 1400.0]) * u.AA)


def test_read_dn2flux_roundtrip(tmp_path):
    """Read back the exact file layout radiometric_calibration.ipynb writes."""
    factor = np.linspace(1.0, 3.0, 20)
    wave = np.linspace(1354.33, 1406.99, 20)
    prim = fits.PrimaryHDU(data=factor)
    prim.header["BUNIT"] = "W nm-1 sr-1 m-2"
    ext = fits.ImageHDU(data=wave, name="WAVELENGTH")
    ext.header["BUNIT"] = "Angstrom"
    path = tmp_path / "f.fits"
    fits.HDUList([prim, ext]).writeto(path)

    f, w = assembled.read_dn2flux(path)
    np.testing.assert_allclose(f.value, factor)
    assert f.unit == u.Unit("W nm-1 sr-1 m-2")
    assert w.unit == u.AA


# --------------------------------------------------------------------------
# readiness and provenance against a temporary config + manifest
# --------------------------------------------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A fake mosaic '20990101' with config, manifest and files under tmp_path."""
    monkeypatch.setattr(manifest, "STATUS_DIR", tmp_path / "status")
    cfg = MosaicConfig(
        date="20990101",
        data_root=tmp_path / "data",
        wavelength_shift=0.01 * u.AA,
    )
    cfg.data_root.mkdir()
    monkeypatch.setattr(assembled.MosaicConfig, "load", classmethod(lambda cls, d: cfg))

    m = Manifest(date="20990101")
    m.record("level_16", date="2026-01-01")
    m.record("mosaic", date="2026-01-02")
    m.save()

    cfg.mosaic_path.write_bytes(b"x")
    cfg.radiometric_path.write_bytes(b"x")
    return cfg


def test_ready_when_everything_is_in_place(sandbox):
    assert assembled.not_ready_reasons("20990101") == []


def test_not_ready_without_level_16(sandbox):
    m = Manifest.load("20990101")
    del m.steps["level_16"]
    m.save()
    reasons = assembled.not_ready_reasons("20990101")
    assert any("level_16" in r for r in reasons)


def test_not_ready_without_the_mosaic_file(sandbox):
    sandbox.mosaic_path.unlink()
    reasons = assembled.not_ready_reasons("20990101")
    assert any("assembled mosaic not found" in r for r in reasons)


def test_not_ready_without_a_wavelength_shift(sandbox):
    sandbox.wavelength_shift = None
    reasons = assembled.not_ready_reasons("20990101")
    assert any("wavelength shift" in r for r in reasons)


def test_load_refuses_an_unready_mosaic(sandbox):
    sandbox.radiometric_path.unlink()
    with pytest.raises(RuntimeError, match="not ready for science"):
        assembled.load("20990101")


def test_provenance_records_files_shift_and_commit(sandbox):
    p = assembled.provenance("20990101")
    assert p["mosaic_date"] == "20990101"
    assert p["assembled_mosaic"]["exists"] and p["assembled_mosaic"]["bytes"] == 1
    assert p["radiometric_factor"]["exists"]
    assert p["wavelength_shift_angstrom"] == pytest.approx(0.01)
    assert p["manifest"]["level_16"] == "2026-01-01"
    assert p["iris_mosaics_commit"] is None or len(p["iris_mosaics_commit"]) == 40


def test_config_science_paths():
    cfg = MosaicConfig(date="20190912", data_root=pl.Path("D:/x/20190912"))
    assert cfg.mosaic_path.name == "level_15_fdm.pickle"
    assert cfg.radiometric_path.name == "20190912_radiometric_calibration_conversion_factor.fits"
    assert cfg.area_path.name == "20190912_area_sg_fuv.fits"
