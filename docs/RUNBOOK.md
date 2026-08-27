# Runbook: processing an IRIS full-disk mosaic

Supersedes `Notes_on_IRIS_FDM_datasets.pdf`. Per-mosaic progress is tracked in
[STATUS.md](STATUS.md).

Levels produced, in order: **L1** (raw from JSOC) → **L1.1** (`iris_prep` part 1
+ Wülser Zernike FUV background) → fixed-pattern removed → despiked → **L1.2**
(MSU two-step background subtracted) → **L1.5** (`iris_prep` part 2) → **L1.6**
(radiometrically calibrated) → assembled mosaic.

Steps run either **locally** or on **filament**; the data crosses between them
four times, which dominates the wall-clock time.

## Before you start

- Connect to the **campus VPN**. filament is unreachable without it.
- SSH to filament uses key authentication via the `filament` alias in
  `~/.ssh/config`. No passwords anywhere.
- Check free space on filament (`ssh filament 'df -h /disk/data'`). `/disk/data`
  runs at capacity; see [Storage](#storage).

## 1. Download level 1 (local, ~3 h)

`notebooks/download_level_1.ipynb`

Find the mosaic's start and end times from the IRIS data search and give them a
2-minute margin. Set `date_string`, `t_start`, `t_end`. JSOC takes ~40 min to
process the export request and emails when ready; the download itself is ~2.5 h.

> The old IDL route (`download_mosaic_lvl1.pro` on filament) is retired — it did
> not retrieve all the files.

## 2. Upload level 1 to filament (~10 h)

`notebooks/upload_to_filament.ipynb` with `level = 'level_1'`.

## 3. Level 1.1: iris_prep part 1 + Wülser background (filament, ~7 h)

`idl/apply_iris_prep_through_bg_subtraction.pro`

Edit the input/output paths in the `.pro` file for this mosaic, then:

```
ssh filament
cd /disk/data/cbunn/calibrated_iris_mosaics/
sswidl
IDL> .r apply_iris_prep_through_bg_subtraction.pro
```

Runs `iris_prep` only as far as the FUV background subtraction, using
`/noflat, /nobad, /nowarp, /filter_fid`:

| keyword | effect |
|---|---|
| `/noflat` | do not apply flat fielding |
| `/nobad` | do not set bad pixels to zero |
| `/nowarp` | do not apply warping |
| `/filter_fid` | fiducial filtering |

Note `/header_temps` (use temperature data in image headers) shifts things
wildly and is not used.

For a long unattended run, launch it detached so a VPN drop cannot kill it:

```
ssh filament "screen -dm sh -c 'cd /disk/data/cbunn/calibrated_iris_mosaics && sswidl < apply_iris_prep_through_bg_subtraction.pro > prep1.log 2>&1'"
```

## 4. Download level 1.1 to local (~1 h)

## 5. Remove the fixed pattern (local)

`notebooks/remove_fixed_pattern_full_ccd.ipynb`

Builds a fixed-pattern image from a trimmed mean of the **off-disk** pixels and
subtracts it. Must run **before** despiking — otherwise part of the fixed
pattern is removed by the despiker and the estimate is corrupted.

Top 10% of off-disk values are cut to suppress spikes. (An Otsu's-method
variant was tried and abandoned.)

## 6. Despike (local)

`notebooks/despike_and_save.ipynb`

Astro-SCRAPPY cosmic-ray detection. The despiker mishandles spikes adjacent to
NaNs, and leftover large spikes badly influence the polynomial fit in the
background subtraction, so NaNs are dealt with before despiking:

- If a **significant fraction** of a spectrograph image is NaN, the whole image
  is called NaN (`all_nan_mask_*`).
- Otherwise the NaN pixels are set to a **large value (16384)**, which the
  despiker then treats as a spike and squashes.

Because the despiker repairs those pixels, the NaNs are deliberately **not**
restored afterwards — the `sg_*_dspk[nan_mask_*] = np.nan` line stays commented
out. Uncommenting it would throw away the despiker's repair.

Images with excessive spikes are identified and the worst are set to NaN
entirely. (A second despiking pass over the moderately spiky images was tried
and dropped — not worth the cost.)

## 7. Level 1.2: two-step background subtraction (local)

First `notebooks/apply_rolling_trimmed_mean.ipynb` — a rolling trimmed mean
along the raster dimension, which is the input to the next step. This is also
where missing images are identified and filled with NaNs so the data reshapes
cleanly into 64-image rasters.

Then `notebooks/background_subtraction.ipynb`:

- **Step 1** — mask the spectral lines (and fiducials), smooth the trimmed-mean
  images, fill the masked regions by Gauss-Seidel relaxation (`pyinterp`), and
  correct the **notched region at Si IV 1394** by multiplying by the smoothed
  Wülser FUV background image. Subtract the result.
- **Step 2** — fit the remaining background per image with a low-order (degree
  3) 2D polynomial and subtract that too.

Together these remove essentially all the background, including some genuine
continuum. That is acceptable: the science target is the far wings of the Si IV
lines, not the continuum level.

## 8. Reupload to filament (~6 h)

`notebooks/upload_to_filament.ipynb` with `level = 'level_12'`.

## 9. Level 1.5: remainder of iris_prep (filament, ~9 h)

`idl/apply_remaining_iris_prep.pro` — same launch pattern as step 3.

Uses `/nosat, /nodark, /noback, /shift_wave, /shift_fid, /poly2d, /filter_wave,
/filter_fid, /filter_aia`:

| keyword | effect |
|---|---|
| `/noback` | do not subtract the visible scattered-light background (ours is already applied) |
| `/nodark`, `/nosat` | dark and saturation steps already done in part 1 |
| `/shift_wave` | time- and temperature-dependent shift to nominal wavelengths |
| `/shift_fid` | time- and temperature-dependent shift to place fiducials |
| `/poly2d` | shifts very slightly bluer |

`/header_temps` shifts everything up a lot and is not used.

## 10. Redownload to local (~5 h)

## 11. Wavelength calibration

`notebooks/wavelength_calibration.ipynb` — fits the neutral lines (Fe II
1392.149, S I 1392.588, Fe II 1392.817 vacuum) and prints a single constant
offset at the bottom of the notebook.

The shift is **per mosaic**. Record new values in
`config/wavelength_shifts.yaml`, where they can be read back during science
analysis without reopening the notebook:

```python
from iris_mosaics import wavelength_shift
sg_wavelength_aligned = sg_wavelength_full + wavelength_shift('20240811')
```

## 12. Level 1.6: radiometric calibration (~30 min)

`notebooks/radiometric_calibration.ipynb`

Needs the effective area (from `get_dn2phot_and_area_sg.pro` on filament) and
`DN2PHOT_SG`. Rather than writing a whole second copy of the mosaic, only the
wavelength-dependent conversion array is saved, and applied when reading.

Mosaics with 2× spectral binning (e.g. 2024-08-11) are rebinned first.

## 13. Assemble the mosaic (~30 min)

`notebooks/build_and_save_mosaic.ipynb` — stitches the rasters into the full
disk and saves the mosaic with its WCS.

## Storage

Two tiers with different rules:

- **`D:` (local)** is the archive. Every level of every mosaic is kept. Nothing
  is deleted.
- **filament** is scratch space. `/disk/data` runs at capacity, so delete the
  previous level as soon as the next one is produced — but only after the
  output has been downloaded **and verified** locally.

## Reference

- Flats, FUV backgrounds, `.geny` files on filament: `/sswdb/iris/data`
- LMSAL background subtraction (old and new):
  <https://hesperia.gsfc.nasa.gov/ssw/iris/idl/msu/calibration/>
