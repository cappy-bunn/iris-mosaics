# iris-mosaics

Tools and analysis for IRIS full-Sun mosaics, with an emphasis on characterizing and
removing the pointing-dependent FUV background.

## The IRIS instrument

The *Interface Region Imaging Spectrograph* (IRIS) is a NASA Small Explorer launched in
June 2013 and led by the Lockheed Martin Solar and Astrophysics Laboratory. It was built
to observe the **interface region**, the chromosphere and transition region that sit
between the photosphere and the corona, where most of the mechanical energy heating the
outer atmosphere is deposited and where the plasma transitions from partially ionized and
collisionally dominated to fully ionized and magnetically dominated.

IRIS consists of a 19 cm Cassegrain telescope feeding two instruments that observe
simultaneously:

- **Spectrograph.** A long, narrow slit (0.33″ wide, 175″ long) feeding three passbands:
  - **FUV1**, ≈1332–1358 Å: C II 1334/1335 Å, O I 1355 Å, Fe XII 1349 Å
  - **FUV2**, ≈1389–1407 Å: Si IV 1394/1403 Å, O IV 1400/1401/1405 Å
  - **NUV**, ≈2783–2834 Å: Mg II h & k (2803 / 2796 Å) and the Mg II triplet
- **Slit-jaw imager (SJI).** Context images in filters centered near 1330 Å (C II),
  1400 Å (Si IV), 2796 Å (Mg II k), and 2832 Å (Mg II wing).

Together these lines span temperatures from the photosphere (~5,000 K) through the
chromosphere and transition region to ~10 MK flare plasma, at spatial scales of a few
tenths of an arcsecond and velocity resolution of order 1 km/s.

Because the spectrograph sees only the strip of Sun under the slit, spectral maps are
built by **rastering**: the secondary mirror steps the slit across the target, and the
resulting sequence of exposures is stacked into a spectral image cube with two spatial
axes and one wavelength axis.

## The mosaics

IRIS's raster field of view is small compared to the solar disk, so IRIS periodically
executes a **full-Sun mosaic**: a campaign in which the spacecraft repoints across a grid
of tiles, running a coarse raster at each pointing, until the entire disk (plus some
off-limb margin) has been covered. The individual rasters are then co-registered and
stitched into a single full-disk spectral map, effectively a full-Sun spectroheliogram
in the IRIS lines.

These mosaics are the only IRIS data product that places the instrument's high-resolution
diagnostics in a global context. They support:

- full-disk maps of chromospheric and transition-region line intensities, Doppler shifts,
  and line widths;
- comparison of quiet Sun, coronal holes, active regions, and the off-limb corona within a
  single self-consistent dataset;
- calibration and cross-comparison against full-disk imagers and spectrographs;
- irradiance studies, since the mosaic integrates the full disk in known spectral lines.

The cost of that coverage is time and heterogeneity. A mosaic takes hours to complete, so
different tiles see the Sun at different times and, critically for this repository, at
different **pointings**.

## Why the FUV background must be subtracted

The signal recorded in an IRIS FUV exposure is not purely the solar spectrum from the
region under the slit. It also carries a background pedestal: detector dark and readout
bias, particle background, and scattered light that reaches the FUV detector without
following the nominal optical path.

For most IRIS science this pedestal is a nuisance term. For the mosaics it is a
first-order systematic, because in the FUV the astrophysical signal is faint. Quiet-Sun
and especially off-limb FUV line intensities can be comparable to, or smaller than, the
background itself. Any full-disk map of FUV intensity is therefore a map of
*signal plus background*, and structure in the background propagates directly into the
scientific result, producing spurious center-to-limb trends, tile-to-tile
discontinuities at mosaic seams, and biased off-limb intensities.

Critically, the background is **not a constant** that can be measured once and removed
everywhere: it varies with where the instrument is pointed, and a mosaic steps the
pointing across the entire disk by construction. That the variation is correlated with
position on the disk is what makes it dangerous. A pointing-dependent background
masquerades as a center-to-limb variation, which is precisely the kind of signal these
mosaics are used to measure.

### The shadow notch at Si IV 1394

Superposed on the smoother part of the background is a shadow whose edge falls across the
**Si IV 1394 Å** line. The line does not sit on a flat portion of the shadow but in the
*gradient* at its edge, so the background level changes sharply across the line profile
itself. This has been the hardest component of the background to account for, and it is
the limiting factor for work on this line.

## Current approach

Two corrections are used in combination:

1. **Pipeline Zernike background subtraction.** J.-P. Wülser's background model, built on
   Zernike polynomials, entered the IRIS pipeline in 2024–2025. It is a large improvement
   over the original background subtraction, but on its own it does not reach the accuracy
   these studies require.

2. **Brute-force background removal.** A direct empirical subtraction developed here. It
   takes no detector-temperature or orbital-state input. It works from the data.

Applied together, the two remove essentially all of the background. This almost certainly
takes some genuine continuum with it. That is acceptable for the science target here,
which is the **far wings of the Si IV lines** rather than the continuum level.

## Status

Early. Nothing here is calibrated science yet.
