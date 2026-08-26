# Migration plan: FURST/iris_fdm → iris-mosaics

Goal: move the IRIS full-disk mosaic (FDM) processing pipeline out of the FURST
repository (`FURST/furst/science/iris_fdm/`) into this repository, then
incrementally automate it while keeping the introspective, diagnostic character
of the notebooks.

Scope: **pipeline only**. Science-analysis notebooks (EE detection,
active-vs-quiet, plotting studies) stay in FURST for now. Plain copy, no git
history carried over; history remains findable in FURST.

## Pipeline inventory

The canonical processing chain (see `Notes_on_IRIS_FDM_datasets.pdf`; the PDF
predates some notebook changes, and this table supersedes it where they differ):

| # | Level | Step | Runs on | Canonical tool |
|---|-------|------|---------|----------------|
| 1 | L1 | JSOC query + download | local | `download_level_1.ipynb` (sunpy/Fido) |
| 2 | — | upload to filament | transfer | `upload_to_filament.ipynb` (to be rewritten; see Credentials) |
| 3 | L1.1 | `iris_prep` part 1 + Wülser Zernike FUV bg subtraction | filament (IDL/SSW) | `apply_iris_prep_through_bg_subtraction.pro` |
| 4 | — | download to local | transfer | manual |
| 5 | L1.1+ | fixed pattern removal (off-disk trimmed mean / Otsu) | local | `remove_fixed_pattern_full_ccd.ipynb` — NOT `remove_fixed_pattern.ipynb`, which is superseded |
| 6 | L1.1+ | despike (Astro-SCRAPPY; NaN handling; double-despike pass) | local | `despike_and_save.ipynb` |
| 7 | — | rolling trimmed mean along raster dim | local | `apply_rolling_trimmed_mean.ipynb` |
| 8 | L1.2 | two-step MSU background subtraction | local | `background_subtraction.ipynb` |
| 9 | — | reupload to filament | transfer | manual |
| 10 | L1.5 | remainder of `iris_prep` (no bg sub; wave/fid shifts) | filament (IDL/SSW) | `apply_remaining_iris_prep.pro` |
| 11 | — | redownload | transfer | manual |
| 12 | — | wavelength calibration via neutral lines | local | `wavelength_calibration.ipynb` |
| 13 | L1.6 | radiometric calibration conversion array | local | `radiometric_calibration.ipynb` |
| 14 | FDM | assemble and save mosaic | local | `build_and_save_mosaic.ipynb` |

Supporting code to migrate:

- `read_full_disk_mosaic.py` (mosaic assembly, WCS handling, plotting helpers)
- `inpaint.py`, `inpaint_array.py`
- `iris_sra_c_*.geny` radiometric calibration files
- IDL `.pro` scripts currently living only on filament at
  `/disk/data/cbunn/calibrated_iris_mosaics/` — copy into `idl/` so they are
  finally under version control (`download_mosaic_lvl1.pro`,
  `apply_iris_prep_through_bg_subtraction.pro`, `apply_remaining_iris_prep.pro`,
  and anything else that folder holds)

To confirm whether still used before migrating: `apply_saa_mask.ipynb`,
`find_and_remove_iris_prep_background.ipynb`.

Explicitly left behind: figures, `.ai` files, `raster.tar.gz`, superseded and
exploratory notebooks (`remove_fixed_pattern.ipynb`, `build_mosaic_test.ipynb`,
`despike_threshold_test.ipynb`, EE-detection and science-study notebooks, the
`mcintosh/` IDL collection, `daniela_radiometric_calibration_code/`).

## Target layout

```
iris-mosaics/
├── iris_mosaics/          # Python package (from read_full_disk_mosaic.py, inpaint*, plus code extracted from notebooks)
├── notebooks/             # pipeline notebooks, outputs stripped, dead code pruned
├── idl/                   # .pro scripts from filament
├── config/                # one YAML per mosaic (dates, paths, raster length, binning, shifts, quirks)
├── docs/                  # this file, the runbook (PDF → markdown), processing status
└── pyproject.toml         # pinned deps: sunpy, astropy, astroscrappy, pyinterp, numba, ...
```

## Phases

### Phase 0 — hygiene (before anything is copied)

1. **Credentials.** Remove the filament credentials embedded in
   `upload_to_filament.ipynb`: rotate the filament password, set up SSH
   public-key authentication, and put host settings in `~/.ssh/config`.
   No credentials of any kind in this repository, ever.
2. **Notebook output stripping.** Install `nbstripout` as a git filter in this
   repo so notebook outputs never reach git (the current copies run to 24 MB).
   Working copies keep their outputs locally; commits are clean sources.

### Phase 1 — faithful transfer (no behavior change)

3. Copy the canonical notebooks and supporting code into the layout above.
4. While copying each notebook, **prune dead code**: cells after the final
   "Save data" cell, superseded experiments mid-notebook, and commented-out
   alternatives that are no longer relevant. The originals remain untouched in
   FURST, so nothing is lost.
5. Fix imports: `furst.science.iris_fdm` → `iris_mosaics`. Add
   `pyproject.toml`; create a fresh environment from it and verify one
   already-processed mosaic's notebooks run end-to-end against existing data.
6. Copy the `.pro` scripts off filament into `idl/`.
7. Convert the PDF notes into `docs/RUNBOOK.md` (procedure) and
   `docs/STATUS.md` (per-mosaic processing ledger), updating both to match
   current practice.

### Phase 2 — parameterize (remove manual cell editing)

8. One `config/<date>.yaml` per mosaic: JSOC time range, data root, raster
   length (64), spectral binning, wavelength shift, known missing rasters,
   per-date quirks. Notebooks read the config instead of hardcoding
   `date_string` and `D:\IRIS data\...` paths.
9. Move duplicated/substantial logic into the package: raster
   reshape-and-gap-fill (currently duplicated between
   `apply_rolling_trimmed_mean` and `wavelength_calibration`),
   `plot_lines_sidebyside`, despike wrapper, fixed-pattern removal, the
   two-step background subtraction. Notebooks become thin: load config → call
   package function → plot diagnostics.
10. Replace the hand-kept status ledger with a machine-readable manifest per
    mosaic (`status.json`: step, completion date, file counts/hashes) that each
    step updates automatically.

### Phase 3 — automate (including filament)

11. **Remote execution instead of remote elimination.** `iris_prep` is deep
    SSW IDL and stays on filament. Automate around it:
    - SSH key auth (from phase 0) enables non-interactive remote commands.
    - Run IDL in batch mode over SSH (exact invocation TBD after access
      testing; see below).
    - Long jobs (7–9 h) must survive dropped connections: launch under
      `nohup`/`screen`/`tmux` and poll a sentinel file for completion.
12. **Transfers.** Replace pysftp file loops with `rsync` if available on both
    ends (restartable, verifiable), else batched `sftp`/`scp` with retry.
    Transfers are the slowest pipeline stage (5–10 h); restartability matters
    more than raw speed.
13. **Orchestration.** A small CLI, e.g.
    `python -m iris_mosaics run 20240811 --from despike --to build`, where each
    step declares file inputs/outputs and completed steps are skipped.
    Snakemake is a good fit if a real DAG runner proves warranted. Diagnostic
    notebooks executed per-run via papermill give an inspectable record of
    every mosaic without manual clicking.

### Filament access: probe results (tested 2026-08-26)

- [x] Public-key SSH auth works (ed25519 key installed; `Host filament` alias
      in `~/.ssh/config`).
- [x] Non-interactive command execution works.
- [x] Plain IDL 8.5.1 runs headless over SSH; license checks out with no tty.
- [x] SSW IDL batch mode works: `echo "print, 2+2" | sswidl` loads the full
      SSW environment (500 paths, `IRIS_DATA=/archive/iris/data`, personal
      `IDL_STARTUP`) and executes. `sswidl` is a tcsh alias for
      `/ssw/gen/setup/ssw_idl`, available even in non-interactive shells.
- [x] `rsync`, `screen`, and `tmux` all present.
- [x] Detached jobs survive disconnect: `screen -dm sh -c "..."` keeps running
      after the SSH session closes; poll a sentinel file for completion.
- [ ] VPN/jump-host requirement from off campus: still to confirm (one
      connectivity drop observed mid-testing; cause not yet identified).

Constraints learned while probing:

- **Remote login shell is tcsh**, and it rejects bash-isms (`2>&1` →
  "Ambiguous output redirect"; `>>` to a nonexistent file fails under
  noclobber). Interactive-prompting aliases are also present (`rm` → `rm -i`),
  which hang or fail with no tty. Automation must wrap remote commands in
  `sh -c '...'` or upload script files rather than passing compound shell
  strings, and use explicit flags (`rm -f`) rather than relying on defaults.
- **`/disk/data` (NFS mount `helicity:/hl0`) is 100% full** — ~181 GB free of
  39 TB at probe time. A mosaic's level-1 data plus intermediates may not fit.
  Check free space before every run; the orchestrator should refuse to start a
  transfer that doesn't fit.
- The `.pro` collection in `/disk/data/cbunn/calibrated_iris_mosaics/` is
  larger than the runbook implies (`apply_dark_sub_iris_prep.pro`,
  `apply_only_background_subtraction.pro`, `apply_iris_prep_fuv_only.pro`,
  several `test_*.pro`). Triage live vs. historical during the Phase 1 copy.

## Order of value

Phases 0–1 are quick and unblock everything. Phase 2 alone removes most of the
error-prone per-mosaic cell editing. Item 11 (remote IDL + restartable
transfers) is what collapses the "babysit filament for a week" problem.
