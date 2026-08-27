"""Per-mosaic configuration.

Each mosaic has one YAML file in ``config/`` holding the values that used to be
edited by hand into notebook cells: the JSOC time range, where the data lives,
the raster geometry, the spectral binning, and the wavelength calibration shift.

    >>> from iris_mosaics import MosaicConfig
    >>> cfg = MosaicConfig.load('20240811')
    >>> cfg.level_path('level_12')
    WindowsPath('D:/IRIS data/deep_mosaics/20240811/level_12')
    >>> cfg.wavelength_shift
    <Quantity -0.018 Angstrom>
"""

from __future__ import annotations

import dataclasses
import pathlib as pl

import astropy.units as u
import yaml

CONFIG_DIR = pl.Path(__file__).parent.parent / "config"

#: Standard sub-directory names within a mosaic's data root.
LEVEL_DIRS = {
    "level_1": "level_1",
    "level_11": "level_11_plus_iris_prep_bg_sub",
    "level_11_fpr": "level_11_iris_prep_bgsub_fixed_pattern_removed",
    "level_12": "level_12",
    "level_15": "level_15",
    "level_15_rebinned": "level_15_rebinned",
}

#: Standard pickle names within a mosaic's data root, formatted with the line.
PICKLE_NAMES = {
    "despiked": "level_11_fpr_despiked_{line}.pickle",
    "rolling_trimmed_mean": "level_11_fpr_despiked_rtm_{line}.pickle",
    "background_filled": "trim_mean_painted_in_background_smooth_{line}.pickle",
    "background_step_2": "polynomial_fit_bgsub_step_2_{line}.pickle",
}


@dataclasses.dataclass
class MosaicConfig:
    """Everything that varies from one mosaic to the next."""

    date: str
    data_root: pl.Path
    jsoc_start: str | None = None
    jsoc_end: str | None = None
    num_img_per_raster: int = 64
    raster_step: u.Quantity = 2 * u.arcsec
    spectral_binning: int = 1
    wavelength_shift: u.Quantity | None = None
    notes: str = ""

    @classmethod
    def load(cls, date: str) -> "MosaicConfig":
        """Load ``config/<date>.yaml``."""
        path = CONFIG_DIR / f"{date}.yaml"
        if not path.exists():
            known = ", ".join(sorted(p.stem for p in CONFIG_DIR.glob("*.yaml")))
            raise FileNotFoundError(
                f"no config for mosaic {date!r} at {path}. Known mosaics: {known or 'none'}"
            )
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        jsoc = doc.get("jsoc") or {}
        raster = doc.get("raster") or {}
        shift = doc.get("wavelength_shift_angstrom")

        return cls(
            date=str(doc["date"]),
            data_root=pl.Path(doc["data_root"]),
            jsoc_start=jsoc.get("start"),
            jsoc_end=jsoc.get("end"),
            num_img_per_raster=raster.get("num_img_per_raster", 64),
            raster_step=raster.get("step_arcsec", 2) * u.arcsec,
            spectral_binning=doc.get("spectral_binning", 1),
            wavelength_shift=None if shift is None else shift * u.AA,
            notes=doc.get("notes", ""),
        )

    @classmethod
    def available(cls) -> list[str]:
        """Date strings of every mosaic with a config file."""
        return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))

    def level_path(self, level: str) -> pl.Path:
        """Directory for a processing level.

        Accepts either a key of :data:`LEVEL_DIRS` (``'level_12'``,
        ``'level_11_fpr'``, ...) or a literal directory name.
        """
        return self.data_root / LEVEL_DIRS.get(level, level)

    def pickle_path(self, kind: str, line: str | int) -> pl.Path:
        """Path of one of the standard intermediate pickles.

        ``kind`` is a key of :data:`PICKLE_NAMES`; ``line`` is 1394 or 1403.
        """
        if kind not in PICKLE_NAMES:
            raise KeyError(f"unknown pickle {kind!r}; known: {', '.join(PICKLE_NAMES)}")
        return self.data_root / PICKLE_NAMES[kind].format(line=line)

    def files(self, level: str, pattern: str = "*.fits") -> list[pl.Path]:
        """Sorted data files for a processing level."""
        return sorted(self.level_path(level).glob(pattern))

    @property
    def remote_root(self) -> str:
        """Working directory for this mosaic on filament."""
        return f"/disk/data/cbunn/calibrated_iris_mosaics/deep_mosaics/{self.date}"
