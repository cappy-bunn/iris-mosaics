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

- `read_full_disk_mosaic.py` (mosaic assembly, WCS handling, plotting
  helpers). Depends only on standard scientific packages plus `reproject` and
  `regridding` — no FURST or kgpy dependency.
- `iris_sra_c_*.geny` radiometric calibration files
- The two IDL `.pro` scripts actually in use on filament — copy into `idl/`
  so they are finally under version control:
  `apply_iris_prep_through_bg_subtraction.pro` and
  `apply_remaining_iris_prep.pro`. The rest of
  `/disk/data/cbunn/calibrated_iris_mosaics/` (including
  `download_mosaic_lvl1.pro`, retired because it missed files — level 1 is
  now downloaded locally via sunpy/JSOC) is historical and stays put.

Confirmed NOT used (do not migrate): `apply_saa_mask.ipynb`,
`find_and_remove_iris_prep_background.ipynb`, `inpaint.py`,
`inpaint_array.py` (inpainting superseded by the Gauss-Seidel relaxation fill
in `background_subtraction.ipynb`; remaining `inpaint`/`kgpy` imports in the
canonical notebooks are vestigial — imported, never called — and go away with
dead-code pruning).

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

1. **Credentials.** DONE. SSH public-key authentication is set up and a
   `Host filament` alias lives in `~/.ssh/config`, so transfers no longer need
   a password at all. The old `upload_to_filament.ipynb` embedded the filament
   password in a `pysftp.Connection(...)` call; that notebook is rewritten
   against the key, and **no credentials of any kind enter this repository,
   ever**. (The password itself is deliberately not being rotated: it was only
   ever exposed on a private group server that is no longer reachable, and
   everyone who could have seen it already has filament access.)
2. **Notebook output stripping.** DONE. `nbstripout` is installed as a git
   filter with `.gitattributes` committed, so notebook outputs never reach git
   (the FURST copies run to 24 MB). Working copies keep their outputs locally;
   commits are clean sources. A fresh clone needs `pip install nbstripout &&
   nbstripout --install` once to activate the filter locally.

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

### Phase 2 — parameterize (remove manual cell editing) — COMPLETE

8. DONE. One `config/<date>.yaml` per mosaic holds the JSOC time range, data
   root, raster geometry, spectral binning, wavelength shift and per-date
   notes; `iris_mosaics.MosaicConfig` loads it and resolves the standard level
   directories and pickle names. Notebooks now open with a single
   `cfg = MosaicConfig.load('<date>')` instead of a hardcoded
   `D:\IRIS data\...` path. Configs exist for 20140324, 20151018, 20190912,
   20220507 and 20240811; add one per new mosaic.
9. DONE. Hoisted into the package, all unit tested:
   - `iris_mosaics.rasters` — raster reshape-and-gap-fill, which was duplicated
     cell for cell between `apply_rolling_trimmed_mean` and
     `wavelength_calibration`; both now share it. `plan_rasters` computes the
     layout without touching data; `pad`/`unpad` are exact inverses tracked by
     index.
   - `iris_mosaics.despike` — the Astro-SCRAPPY wrapper, plus the NaN-sentinel
     handling and mostly-NaN image flagging.
   - `iris_mosaics.fixed_pattern` — off-disk masking, the one-sided trimmed
     mean, and a chunked `nanmean` for cubes too large to hold in memory.
   - `iris_mosaics.background` — Gauss-Seidel fill and the step-2 2D polynomial
     fit, both operating per detector tap.
   - `iris_mosaics.plotting.plot_lines_sidebyside` — was defined identically in
     three notebooks.

   The occulting geometry `is_off_disk` used (limb radius, disk-centre offsets)
   was carried in commented-out per-date blocks; it now lives in each config's
   `off_disk` section. Values recovered for 20140324, 20190912 and 20240811;
   20151018 and 20220507 have placeholders to fill in when they are processed.
10. DONE. `iris_mosaics.manifest` keeps one JSON file per mosaic in
    `status/`, recording each completed step with its date and any details the
    step wants to store (file counts, parameters). `docs/STATUS.md` is
    generated from these by `render_status_markdown()` and should not be edited
    by hand. Seeded from the ledger transcribed out of the PDF: 22 mosaics.

    `Manifest.out_of_order()` flags steps whose dates run backwards — it
    independently rediscovered the 2019-09-12 anomaly the PDF had marked
    "Do I need to rerun this??" (despiked 2026-01-14, but fixed-pattern removed
    2026-04-06), which is exactly the question the ledger could not answer.

### Phase 3 — automate (including filament) — COMPLETE

11. **Remote execution instead of remote elimination.** DONE.
    `iris_mosaics.remote` renders each IDL pass from a template in `idl/`
    (`prep_part1.pro.template`, `prep_part2.pro.template`) with this mosaic's
    paths substituted, uploads it, and launches it under `screen -dm` so it
    outlives the SSH connection and any VPN drop. The hand-edited
    `.pro` files are kept for reference but are no longer the thing that runs.

    Completion is detected by a sentinel file holding the **shell's** exit
    status, not by anything IDL writes, so a crashed or killed IDL reports
    `failed` rather than appearing to run forever. `launch` refuses to start a
    second copy of a job that is already running.

    Remote commands are piped to `sh` over **stdin** rather than passed as
    arguments: ssh flattens arguments into one string for the login shell to
    re-parse, so argument quoting would have to survive tcsh as well as sh.
    An earlier attempt using `sh -c '<quoted>'` failed exactly this way.
12. **Transfers.** DONE. `iris_mosaics.transfer` wraps rsync with `--partial`
    for resume-after-drop, plus free-space and file-count checks;
    `upload_to_filament.ipynb` uses it. Windows OpenSSH has no rsync, so it is
    reached through **WSL** (Ubuntu, WSL1 — `/mnt/d` is near-native: a stat walk
    of 11,767 files took 0.63 s). WSL has its own `~/.ssh`; the key is copied
    there, and the host is given fully qualified since WSL does not inherit the
    Windows ssh config.

    Note `size_only=True`: rsync's default size+mtime comparison re-sends
    everything uploaded by the old scp/pysftp route, because those mtimes do not
    match the local files. Comparing size alone correctly recognises them as
    already present. Verified against 20240811 level_12 (11,767 files,
    53.7 GB): default would re-send all of them, `--size-only` sends none.
13. **Storage lifecycle.** DONE. `remote.cleanup_level` deletes a superseded
    level from filament, but only when given the number of files verified in
    the local archive *and* that number matches what is on filament, *and*
    `confirm=True` is passed explicitly. Deleting data is not something to do
    on inference: the local archive is the only copy that matters.
14. **Orchestration.** DONE for the parts worth automating.
    `iris_mosaics.pipeline` declares the 14 steps with their prerequisites, and
    `python -m iris_mosaics` drives them:

    ```
    python -m iris_mosaics status                  # every mosaic, one line each
    python -m iris_mosaics status 20240811         # step by step
    python -m iris_mosaics idl launch prep1 20240811
    python -m iris_mosaics idl watch  prep1 20240811
    python -m iris_mosaics record despiked 20240811 --n-files 11767
    ```

    `idl launch` refuses to start when the prerequisite step is not recorded
    (overridable with `--force`); `idl watch` polls, reports the output file
    count as progress, records the manifest entry on success, and prints the
    log tail on failure.

    **Local steps stay in the notebooks deliberately.** The introspection is
    the point of them, and a papermill-style headless run would discard exactly
    what makes them useful. The CLI says which notebook is next and records
    that it was done, rather than pretending to run it.

    `next_step` reports the first unrecorded step *after* the furthest one
    completed, not simply the first unrecorded one — the transcribed ledger has
    holes (it never tracked the rolling trimmed mean), and a mosaic at level 1.6
    should not be told to redo an earlier stage. Those holes are surfaced
    separately by `record_gaps` rather than silently trusted.

### Storage lifecycle

Two tiers, with different rules:

- **`D:` (local) — the archive.** Every level of every mosaic is kept
  (`D:\IRIS data\deep_mosaics\<date>\level_*`). Nothing is deleted here.
- **filament — scratch space only.** `/disk/data` is at ~100% capacity, so a
  mosaic's previous level is deleted as soon as the next level is being
  produced. Only the level currently being worked on should exist there.

Requirements this places on the orchestrator:

- Check free space on filament *before* starting a transfer and refuse to
  start one that will not fit, rather than filling a shared group disk.
- After a remote step completes and its output has been downloaded **and
  verified** against the local archive, delete the now-superseded remote level.
  Deletion must be gated on verified local copies, never on the transfer
  merely having been attempted — the local archive is the only copy that
  matters.
- Never delete anything on `D:`.

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
- [x] **Campus VPN is required.** The connectivity drop observed mid-testing
      was the VPN disconnecting; filament became reachable again immediately on
      reconnecting. (This appears to be newer or stricter than expected —
      historically the VPN did not seem necessary.) Any unattended
      orchestration must therefore assume the VPN can drop mid-run: remote jobs
      must survive disconnection (they do, see `screen` above) and transfers
      must be restartable (`rsync`).

Constraints learned while probing:

- **Remote login shell is tcsh**, and it rejects bash-isms (`2>&1` →
  "Ambiguous output redirect"; `>>` to a nonexistent file fails under
  noclobber). Interactive-prompting aliases are also present (`rm` → `rm -i`),
  which hang or fail with no tty. Automation must wrap remote commands in
  `sh -c '...'` or upload script files rather than passing compound shell
  strings, and use explicit flags (`rm -f`) rather than relying on defaults.
- **`/disk/data` (NFS mount `helicity:/hl0`) is effectively full** — ~181 GB
  free of 39 TB at probe time. Filament is working space, not storage: the
  current practice is to **delete the previous level of a mosaic on filament
  as soon as the next level is being produced**. The local `D:` drive is the
  archive and keeps every level. Automation must reproduce this discipline
  explicitly rather than inheriting it as a habit (see Storage lifecycle
  below).
- The `.pro` collection in `/disk/data/cbunn/calibrated_iris_mosaics/` is
  larger than the runbook implies (`apply_dark_sub_iris_prep.pro`,
  `apply_only_background_subtraction.pro`, `apply_iris_prep_fuv_only.pro`,
  several `test_*.pro`). Triage live vs. historical during the Phase 1 copy.

## Order of value

Phases 0–1 are quick and unblock everything. Phase 2 alone removes most of the
error-prone per-mosaic cell editing. Item 11 (remote IDL + restartable
transfers) is what collapses the "babysit filament for a week" problem.
