# Status of deep FDMs

Per-mosaic processing progress. Transcribed from
`Notes_on_IRIS_FDM_datasets.pdf` (August 2026); that PDF is superseded by this
file and [RUNBOOK.md](RUNBOOK.md).

Levels: **L1** raw → **L1.1** iris_prep part 1 + Wülser background → **FPR**
fixed pattern removed → **DSP** despiked → **L1.2** MSU background subtracted →
**L1.5** iris_prep part 2 → **L1.6** radiometric conversion calculated →
**MOSAIC** assembled.

`*` = 5-second step cadence instead of 9-second.

## Fully processed to L1.6

### 2014-03-24 `*`
- L1 downloaded via JSOC python notebook — 2026-05-12
- L1.1 + JPW background subtraction — 2026-05-14
- FPR — 2026-05-15
- DSP — 2026-05-18
- L1.2 MSU background subtracted — 2026-05-25
- L1.5 — 2026-05-26
- L1.6 radiometric conversion calculated — 2026-07-30
- JSOC time range: `2014-03-24 03:18:00` → `2014-03-25 03:25:00`

### 2019-09-12
- L1 downloaded — 2023-02-07
- L1.1 + JPW background subtracted — 2026-01-10
- FPR — 2026-04-06
- DSP — 2026-01-14 **(date precedes FPR — needs checking, possible rerun)**
- L1.2 MSU background subtracted — 2026-04-07
- L1.5 — 2026-04-15
- L1.6 radiometric conversion calculated — 2026-07-30
- JSOC time range: `2019-09-12 12:25:00` → `2019-09-14 03:10:00`

### 2024-08-11
- L1 downloaded — 2026-05-28
- L1.1 + iris_prep background subtraction — 2026-06-30
- FPR — 2026-07-08
- DSP — 2026-07-21
- L1.2 MSU background subtracted — 2026-07-26
- L1.5 — 2026-07-28
- L1.5 rebinned (had 2× spectral pixels) — 2026-07-31
- L1.6 radiometric conversion calculated — 2026-07-31
- JSOC time range: `2024-08-11 00:02:44` → `2024-08-12 14:03:23`

## Partially processed

### 2015-10-18 (a couple of rasters are missing)
- L1 downloaded via JSOC python notebook — 2025-03-27
- L1.1 + iris_prep background subtraction — 2026-07-07
- JSOC time range: `2015-10-18 10:26:27` → `2015-10-20 01:05:02`

### 2022-05-07
- L1 downloaded — 2026-06-30
- L1.1 + iris_prep background subtraction — 2026-07-03
- JSOC time range: `2022-05-07 12:38:55` → `2022-05-09 03:11:37`

### 2019-05-05
- L1 downloaded — 2024-02-21
- L1.1 processed — 2025-01-03
- FPR — 2025-01-15
- DSP — 2025-01-16

### 2015-04-01 (large chunk of data missing)
- L1 downloaded via JSOC python notebook — 2025-03-26

### 2017-10-21
- L1 downloaded — 2024-02-18
- L1.1 processed — 2024-02-20

### 2018-08-25
- L1 downloaded — 2024-02-20
- L1.1 processed — 2024-02-21

### 2020-04-22
- L1 downloaded — 2024-01-19
- L1.1 processed — 2024-01-23

### 2020-09-06
- L1 downloaded — 2024-01-24
- L1.1 processed — 2024-01-25

## Not yet started

- 2013-10-27 `*`
- 2014-03-17 `*`
- 2019-04-13 (large chunk of data missing)
- 2021-04-18
- 2021-10-16
- 2022-09-25
- 2023-03-27 (very close in time to 2023-04-29 — maybe just choose one)
- 2023-04-29
- 2023-09-05
- 2024-03-10
- 2024-09-02 (very close in time to 2024-08-11, and the Si IV channel is
  degraded in some parts)

## Per-mosaic parameters

Values that currently live as edited cells or commented-out blocks in the
notebooks, to be moved into `config/<date>.yaml` in Phase 2 of the migration:

| mosaic | wavelength shift | notes |
|---|---|---|
| 2014-03-24 | (in `wavelength_calibration.ipynb`) | 5 s step cadence |
| 2019-09-12 | −0.018 Å | |
| 2024-08-11 | (in `wavelength_calibration.ipynb`) | 2× spectral binning; needs rebinning before L1.6 |

Raster length is 64 images for all mosaics processed so far.
