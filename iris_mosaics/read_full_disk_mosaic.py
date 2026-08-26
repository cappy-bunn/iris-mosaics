
import pathlib as pl
import numpy as np
import typing as tp
import astropy.units as u
import scipy.io
from astropy.io import fits
import astropy.wcs
import reproject
import regridding
from textwrap import wrap
import matplotlib.pyplot as plt
# from irispy import iris_tools


def read_sg_image_lvl1(image_filename: pl.Path) -> tp.Tuple[np.ndarray]:

    image_hdu_list = fits.open(image_filename)
    image_hdu_list.info()
    for item in image_hdu_list:
        print(repr(item.header))

    image = image_hdu_list[1].data  # 3D cube     # 3D cube summed in space (x, y), possibly calibrated
    header = image_hdu_list[1].header

    return image


def read_sg_image_old(image_filename: pl.Path, fuv_channel: str = 'fuv1') -> tp.Tuple[astropy.wcs.WCS, fits.HDUList, bool]:

    image_hdu_list = fits.open(image_filename)
    header = image_hdu_list[0].header
    saa = bool(image_hdu_list[0].header['SAA'])

    if fuv_channel == 'fuv1':
        w = astropy.wcs.WCS(header)

    elif fuv_channel == 'fuv2':
        header2 = header.copy()
        header2['CRPIX1'] = header['CRPIX1A']
        header2['CRPIX2'] = header['CRPIX2A']
        header2['CRVAL1'] = header['CRVAL1A']
        header2['CRVAL2'] = header['CRVAL2A']
        header2['CRVAL3'] = header['CRVAL3A']
        header2['CDELT1'] = header['CDELT1A']
        header2['CDELT2'] = header['CDELT2A']
        header2['CDELT3'] = header['CDELT3A']
        header2['CTYPE1'] = header['CTYPE1A']
        header2['CTYPE2'] = header['CTYPE2A']
        header2['CTYPE3'] = header['CTYPE3A']
        header2['CUNIT1'] = header['CUNIT1A']
        header2['CUNIT2'] = header['CUNIT2A']
        header2['CUNIT3'] = header['CUNIT3A']
        header2['PC1_1'] = header['PC1_1A']
        header2['PC1_2'] = header['PC1_2A']
        header2['PC2_1'] = header['PC2_1A']
        header2['PC2_2'] = header['PC2_2A']
        header2['PC3_1'] = header['PC3_1A']
        header2['PC3_2'] = header['PC3_2A']
        w = astropy.wcs.WCS(header2)
        # print(repr(header2))

    else:
        raise NotImplementedError

    return w, image_hdu_list, saa

def read_sg_image(image_filename: pl.Path, fuv_channel: str = 'fuv1') -> tp.Tuple[astropy.wcs.WCS, fits.HDUList, bool]:

    image_hdu_list = fits.open(image_filename)
    header = image_hdu_list[0].header
    saa = bool(header['SAA'])

    try:
        key = {'fuv1': ' ', 'fuv2': 'A'}[fuv_channel]
    except KeyError:
        raise NotImplementedError(fuv_channel)

    w = astropy.wcs.WCS(header, key=key)
    return w, image_hdu_list, saa

def read_full_disk_mosaic(mosaic_filename: pl.Path) -> tp.Tuple[np.ndarray, astropy.wcs.WCS, np.ndarray, u.Quantity]:

    mosaic_hdu_list = fits.open(mosaic_filename)
    # print(mosaic_hdu_list[0].header['LAMREF'])
    mosaic_hdu_list.info()
    for item in mosaic_hdu_list:
        print(repr(item.header))

    w = astropy.wcs.WCS(mosaic_hdu_list[0].header)
    cube = mosaic_hdu_list[0].data          # 3D cube
    cube_spatial_sum = mosaic_hdu_list[1].data      # 3D cube summed in space (x, y), possibly calibrated
    header = mosaic_hdu_list[0].header
    exp_time = header['EXPTIME']*u.s

    # data = mosaic_hdu_list[0].data
    # data_sum = data.sum(axis=0)
    # data_sum = rebin.rebin(data_sum, [6, 1])
    # return data_sum
    return cube, w, cube_spatial_sum, exp_time


# def build_mosaic(file_paths_list, indices: tp.Tuple[slice, slice] = (slice(None), slice(None))) -> tp.Tuple[np.ndarray, astropy.wcs.WCS]:
#
#     file0 = file_paths_list[0]
#
#     xmax = (1100 * u.arcsec).to(u.deg)
#     xmin = -xmax
#     ymax = (1100 * u.arcsec).to(u.deg)
#     ymin = -ymax
#     lmin = (1391.8 * u.angstrom).to(u.m)
#     lmax = (1406 * u.angstrom).to(u.m)
#
#     # Make a new WCS object
#     wcs, hdul, saa = read_sg_image(file0, 'fuv2')
#
#     sg_image = hdul[0].data
#     # global_wcs = wcs.copy()
#     # global_wcs.wcs.pc = np.identity(3)
#     cdelt_x = (2 * u.arcsec).to(u.deg).value
#     # global_wcs.wcs.cdelt[~0] = cdelt_x
#     # global_wcs.wcs.crpix[~0] = 0
#     # global_wcs.wcs.crval[~0] = xmin.value
#     # global_wcs.wcs.cdelt[~1] = (2*u.arcsec).to(u.deg).value
#     # kmin, jmin, imin = global_wcs.all_world2pix(lmin.value, ymin.value, xmin.value, 0)
#     # kmax, jmax, imax = global_wcs.all_world2pix(lmax.value, ymax.value, xmax.value, 0)
#     # kmin, jmin, imin = int(kmin), int(jmin), int(imin)
#     # kmax, jmax, imax = int(kmax), int(jmax), int(imax)
#     # print(kmax, jmax, imax)
#     # nx, ny, nl = imax - imin, jmax - jmin, kmax - kmin
#     nx = (xmax - xmin) / (cdelt_x << u.deg)
#     ny = (ymax - ymin) / (wcs.wcs.cdelt[1] << u.deg)
#     # nl = (lmax - lmin) / (wcs.wcs.cdelt[0] << u.m)
#     nl = sg_image.shape[~0]
#
#     nx = int(nx)
#     ny = int(ny)
#     nl = int(nl)
#
#     wcs_dict = {
#         'CTYPE1': 'WAVE',
#         'CUNIT1': 'm',
#         'CDELT1': wcs.wcs.cdelt[0],
#         'CRPIX1': wcs.wcs.crpix[0],
#         'CRVAL1': wcs.wcs.crval[0],
#         'NAXIS1': nl,
#         'CTYPE2': 'Solar Y',
#         'CUNIT2': 'deg',
#         'CDELT2': wcs.wcs.cdelt[1],
#         'CRPIX2': 0,
#         'CRVAL2': ymin.value,
#         'NAXIS2': ny,
#         'CTYPE3': 'Solar X',
#         'CUNIT3': 'deg',
#         'CDELT3': cdelt_x,
#         'CRPIX3': 0,
#         'CRVAL3': xmin.value,
#         'NAXIS3': nx,
#     }
#     # global_wcs_header = global_wcs.to_header()
#     # print(repr(global_wcs_header))
#     # global_wcs_header['NAXIS1'] = nl
#     # global_wcs_header['NAXIS2'] = ny
#     # global_wcs_header['NAXIS3'] = nx
#     # global_wcs_header['LATPOLE'] = 90.
#     # print(repr(global_wcs_header))
#     global_wcs = astropy.wcs.WCS(wcs_dict)
#     # global_wcs._naxis.append(1)
#     # naxis = global_wcs._naxis
#     # naxis[1] = 4000
#     # naxis[2] = 4000
#     # global_wcs._naxis = naxis
#     # global_wcs.set()
#     # global_wcs = global_wcs.slice((slice(None), slice(None), slice(kmin, kmax)))
#
#     kmin, jmin, imin = global_wcs.all_world2pix(lmin.value, ymin.value, xmin.value, 0)
#     kmax, jmax, imax = global_wcs.all_world2pix(lmax.value, ymax.value, xmax.value, 0)
#     kmin, jmin, imin = int(kmin), int(jmin), int(imin)
#     kmax, jmax, imax = int(kmax), int(jmax), int(imax)
#
#     global_data = np.full((nx, ny, kmax-kmin), fill_value=np.nan)
#     global_wcs = global_wcs[:, :, kmin:kmax]
#
#     # print(repr(global_wcs))
#
#     for file in file_paths_list:
#         wcs, hdul, saa = read_sg_image(file, 'fuv2')
#         if saa:
#             continue
#         # wcs = wcs[(slice(None), ) + indices]
#         sg_image = hdul[0].data[indices]
#         # nan_mask = np.isnan(sg_image)
#         x = np.array([0])
#         y = np.arange(sg_image.shape[0])
#         wmin, _, _ = wcs.all_world2pix(lmin.value, 0, 0, 0)
#         wmax, _, _ = wcs.all_world2pix(lmax.value, 0, 0, 0)
#         w = np.arange(int(wmin), int(wmax))
#         x, y, w = np.meshgrid(x, y, w, indexing='ij')
#         # sg_image[nan_mask] = 0
#         x, y, w = x.flatten(), y.flatten(), w.flatten()
#         ww, wy, wx = wcs.all_pix2world(w, y, x, 0)
#         wx, wy = ((wx + 180) % 360) - 180, ((wy + 180) % 360) - 180
#         gw, gy, gx = global_wcs.all_world2pix(ww, wy, wx, 0)
#         gx, gy, gw = np.round(gx), np.round(gy), np.round(gw)
#         gx, gy, gw = gx.astype(int), gy.astype(int), gw.astype(int)
#         where_nonzero = np.isfinite(sg_image[y, w])
#         global_data[gx[where_nonzero], gy[where_nonzero], gw[where_nonzero]] = sg_image[y, w][where_nonzero]
#
#     return global_data, global_wcs


# Updated version of build_mosaic with help from Claude
def build_mosaic(
        file_paths_list,
        indices: tp.Tuple[slice, slice] = (slice(None), slice(None)),
        skip_saa: bool = True,
) -> tp.Tuple[np.ndarray, astropy.wcs.WCS]:
    """Assemble SG strips into a full-disk (x, y, wave) mosaic cube.

    Parameters
    ----------
    file_paths_list : sequence of paths
        SG strip files, in the order they should be laid down. Where two
        valid values land on the same mosaic pixel, the later file wins,
        so keep this list deterministically ordered (e.g. sorted).
    indices : (slice, slice)
        Optional (spatial, spectral) restriction of each strip,
        interpreted in original detector pixel coordinates so the WCS
        stays aligned even for slices with a nonzero start.
    skip_saa : bool
        If True (default), strips flagged as SAA are skipped (science
        products). If False, all strips are included (display mosaics
        without missing patches).
    """
    xmax = (1100 * u.arcsec).to(u.deg)
    xmin = -xmax
    ymax = (1100 * u.arcsec).to(u.deg)
    ymin = -ymax
    lmin = (1391.8 * u.angstrom).to(u.m)
    lmax = (1406.5 * u.angstrom).to(u.m)

    # Global grid: spectral solution inherited from the first file, so
    # file 0 must be a good (repaired, binned-axis) file.
    wcs0, hdul0, _ = read_sg_image(file_paths_list[0], 'fuv2')
    nl = hdul0[0].data.shape[-1]
    hdul0.close()

    cdelt_x = (2 * u.arcsec).to(u.deg).value
    nx = int((xmax - xmin) / (cdelt_x << u.deg))
    ny = int((ymax - ymin) / (wcs0.wcs.cdelt[1] << u.deg))

    wcs_dict = {
        'CTYPE1': 'WAVE',
        'CUNIT1': 'm',
        'CDELT1': wcs0.wcs.cdelt[0],
        'CRPIX1': wcs0.wcs.crpix[0],
        'CRVAL1': wcs0.wcs.crval[0],
        'NAXIS1': nl,
        'CTYPE2': 'Solar Y',
        'CUNIT2': 'deg',
        'CDELT2': wcs0.wcs.cdelt[1],
        'CRPIX2': 0,
        'CRVAL2': ymin.value,
        'NAXIS2': ny,
        'CTYPE3': 'Solar X',
        'CUNIT3': 'deg',
        'CDELT3': cdelt_x,
        'CRPIX3': 0,
        'CRVAL3': xmin.value,
        'NAXIS3': nx,
    }
    global_wcs = astropy.wcs.WCS(wcs_dict)

    kmin, _, _ = global_wcs.all_world2pix(lmin.value, ymin.value, xmin.value, 0)
    kmax, _, _ = global_wcs.all_world2pix(lmax.value, ymax.value, xmax.value, 0)
    kmin, kmax = int(kmin), int(kmax)
    nw = kmax - kmin

    global_data = np.full((nx, ny, nw), fill_value=np.nan)
    global_wcs = global_wcs[:, :, kmin:kmax]

    for file in file_paths_list:
        wcs, hdul, saa = read_sg_image(file, 'fuv2')
        if saa and skip_saa:
            hdul.close()
            continue

        full = hdul[0].data  # (space, wave), original pixel numbering

        # Rows/columns to use, in ORIGINAL detector pixel coordinates.
        y_idx = np.arange(full.shape[0])[indices[0]]

        wlo, _, _ = wcs.all_world2pix(lmin.value, 0, 0, 0)
        whi, _, _ = wcs.all_world2pix(lmax.value, 0, 0, 0)
        wlo = max(int(np.floor(wlo)), 0)  # clip to the detector:
        whi = min(int(np.ceil(whi)), full.shape[1])  # negative w would wrap
        w_idx = np.arange(wlo, whi)
        w_allowed = np.zeros(full.shape[1], dtype=bool)
        w_allowed[indices[1]] = True
        w_idx = w_idx[w_allowed[w_idx]]

        x, y, w = np.meshgrid(np.array([0]), y_idx, w_idx, indexing='ij')
        x, y, w = x.ravel(), y.ravel(), w.ravel()

        ww, wy, wx = wcs.all_pix2world(w, y, x, 0)
        wx = ((wx + 180) % 360) - 180
        wy = ((wy + 180) % 360) - 180
        gw, gy, gx = global_wcs.all_world2pix(ww, wy, wx, 0)
        gx = np.round(gx).astype(int)
        gy = np.round(gy).astype(int)
        gw = np.round(gw).astype(int)

        vals = full[y, w]
        # Valid data only: borders are NaN in current files, 0 in older
        # ones -- neither may overwrite a neighboring strip's real value.
        good = np.isfinite(vals) & (vals != 0)
        # Bounds guard: negative indices would silently wrap to the
        # opposite edge of the mosaic.
        good &= (gx >= 0) & (gx < nx) & (gy >= 0) & (gy < ny) \
                & (gw >= 0) & (gw < nw)

        global_data[gx[good], gy[good], gw[good]] = vals[good]
        hdul.close()

    return global_data, global_wcs

# New build mosaic using "regrid"
def build_mosaic_regrid(file_paths_list) -> tp.Tuple[np.ndarray, astropy.wcs.WCS]:
    # NOTE: WCS has units of deg and meters instead of arcsec and angstroms

    file0 = file_paths_list[0]

    xmax = (1100 * u.arcsec)
    xmin = -xmax
    ymax = (1100 * u.arcsec)
    ymin = -ymax
    lmin = (1391.5 * u.angstrom)
    lmax = (1406 * u.angstrom)

    # Make a new WCS object
    wcs, hdul, saa = read_sg_image(file0, 'fuv2')

    sg_image = hdul[0].data

    cdelt_x = (2 * u.arcsec)

    # Account for the fact that we are spreading a ~0.33 arcsec wide pixel into a 2 arcsec wide pixel
    radiometic_factor = cdelt_x / (wcs.wcs.cdelt[2] * u.deg)
    radiometic_factor = radiometic_factor.to_value(u.dimensionless_unscaled)

    nx = (xmax - xmin) / (cdelt_x)
    ny = (ymax - ymin) / (wcs.wcs.cdelt[1] * u.deg)
    nl = sg_image.shape[~0]

    nx = int(nx)
    ny = int(ny)
    nl = int(nl)

    wcs_dict = {
        'CTYPE1': 'WAVE',
        'CUNIT1': 'm',
        'CDELT1': wcs.wcs.cdelt[0],
        'CRPIX1': wcs.wcs.crpix[0],
        'CRVAL1': wcs.wcs.crval[0],
        'NAXIS1': nl,
        'CTYPE2': 'Solar Y',
        'CUNIT2': 'deg',
        'CDELT2': wcs.wcs.cdelt[1],
        'CRPIX2': 0,
        'CRVAL2': ymin.to_value(u.deg),
        'NAXIS2': ny,
        'CTYPE3': 'Solar X',
        'CUNIT3': 'deg',
        'CDELT3': cdelt_x.to_value(u.deg),
        'CRPIX3': 0,
        'CRVAL3': xmin.to_value(u.deg),
        'NAXIS3': nx,
    }

    global_wcs = astropy.wcs.WCS(wcs_dict)

    kmin, jmin, imin = global_wcs.world_to_pixel(lmin, ymin, xmin)
    kmax, jmax, imax = global_wcs.world_to_pixel(lmax, ymax, xmax)
    print(imin, jmin, kmin)
    print(imax, jmax, kmax)
    kmin, jmin, imin = int(kmin), int(jmin), int(imin)
    kmax, jmax, imax = int(kmax), int(jmax), int(imax)

    global_data = np.full((nx, ny, kmax-kmin), fill_value=np.nan)
    global_wcs = global_wcs[:, :, kmin:kmax]

    wavelength, y, x = global_wcs.array_index_to_world(*np.indices(global_data[...,0:1].shape))
    print(x.mean(), y.mean(), wavelength.mean())
    print(x.shape, y.shape, wavelength.shape)

    for file in file_paths_list:
        wcs, hdul, saa = read_sg_image(file, 'fuv2')
        # Skip image if SAA flag is 1
        if saa:
            continue
        sg_image = hdul[0].data * radiometic_factor
        sg_image = sg_image[...,kmin:kmax]
        wcs.wcs.cdelt[2] = cdelt_x.to_value(u.deg)
        wcs = wcs[...,kmin:kmax]
        shape_vertices = (2,) + tuple(n + 1 for n in sg_image.shape)
        indices = np.indices(
            (shape_vertices[0],
            shape_vertices[1],
            1)
        )
        wavelength_i, y_i, x_i = wcs.array_index_to_world(*indices)
        print(x_i.mean(), y_i.mean(), wavelength_i.mean())
        print(x_i.shape, y_i.shape, wavelength_i.shape)
        weights = regridding.weights(
            coordinates_input=(x_i, y_i),
            coordinates_output=(x, y),
            axis_input=(0, 1),
            axis_output=(0, 1),
            method='conservative'
        )
        print(weights)
        regridding.regrid_from_weights(
            *weights,
            values_input=sg_image,
            values_output=global_data,
            axis_input=(0, 1),
            axis_output=(0, 1),
        )


# Use this to build a mosaic from .sav files from LMSAL
def build_mosaic_sav(fits_file_list, sav_files_list, indices: tp.Tuple[slice, slice] = (slice(None), slice(None))) -> tp.Tuple[np.ndarray, astropy.wcs.WCS]:

    file0 = fits_file_list[0]

    xmax = (1000 * u.arcsec).to(u.deg)
    xmin = -xmax
    ymax = (1000 * u.arcsec).to(u.deg)
    ymin = -ymax
    lmin = (1391.5 * u.angstrom).to(u.m)
    lmax = (1406 * u.angstrom).to(u.m)

    # Make a new WCS object
    wcs, hdul, _ = read_sg_image(file0, 'fuv2')

    sg_image = hdul[0].data
    # global_wcs = wcs.copy()
    # global_wcs.wcs.pc = np.identity(3)
    cdelt_x = (2 * u.arcsec).to(u.deg).value
    # global_wcs.wcs.cdelt[~0] = cdelt_x
    # global_wcs.wcs.crpix[~0] = 0
    # global_wcs.wcs.crval[~0] = xmin.value
    # global_wcs.wcs.cdelt[~1] = (2*u.arcsec).to(u.deg).value
    # kmin, jmin, imin = global_wcs.all_world2pix(lmin.value, ymin.value, xmin.value, 0)
    # kmax, jmax, imax = global_wcs.all_world2pix(lmax.value, ymax.value, xmax.value, 0)
    # kmin, jmin, imin = int(kmin), int(jmin), int(imin)
    # kmax, jmax, imax = int(kmax), int(jmax), int(imax)
    # print(kmax, jmax, imax)
    # nx, ny, nl = imax - imin, jmax - jmin, kmax - kmin
    nx = (xmax - xmin) / (cdelt_x << u.deg)
    ny = (ymax - ymin) / (wcs.wcs.cdelt[1] << u.deg)
    # nl = (lmax - lmin) / (wcs.wcs.cdelt[0] << u.m)
    nl = sg_image.shape[~0]

    nx = int(nx)
    ny = int(ny)
    nl = int(nl)

    wcs_dict = {
        'CTYPE1': 'WAVE',
        'CUNIT1': 'm',
        'CDELT1': wcs.wcs.cdelt[0],
        'CRPIX1': wcs.wcs.crpix[0],
        'CRVAL1': wcs.wcs.crval[0],
        'NAXIS1': nl,
        'CTYPE2': 'Solar Y',
        'CUNIT2': 'deg',
        'CDELT2': wcs.wcs.cdelt[1],
        'CRPIX2': 0,
        'CRVAL2': ymin.value,
        'NAXIS2': ny,
        'CTYPE3': 'Solar X',
        'CUNIT3': 'deg',
        'CDELT3': cdelt_x,
        'CRPIX3': 0,
        'CRVAL3': xmin.value,
        'NAXIS3': nx,
    }
    # global_wcs_header = global_wcs.to_header()
    # print(repr(global_wcs_header))
    # global_wcs_header['NAXIS1'] = nl
    # global_wcs_header['NAXIS2'] = ny
    # global_wcs_header['NAXIS3'] = nx
    # global_wcs_header['LATPOLE'] = 90.
    # print(repr(global_wcs_header))
    global_wcs = astropy.wcs.WCS(wcs_dict)
    # global_wcs._naxis.append(1)
    # naxis = global_wcs._naxis
    # naxis[1] = 4000
    # naxis[2] = 4000
    # global_wcs._naxis = naxis
    # global_wcs.set()
    # global_wcs = global_wcs.slice((slice(None), slice(None), slice(kmin, kmax)))

    kmin, jmin, imin = global_wcs.all_world2pix(lmin.value, ymin.value, xmin.value, 0)
    kmax, jmax, imax = global_wcs.all_world2pix(lmax.value, ymax.value, xmax.value, 0)
    kmin, jmin, imin = int(kmin), int(jmin), int(imin)
    kmax, jmax, imax = int(kmax), int(jmax), int(imax)

    global_data = np.zeros((nx, ny, kmax-kmin))
    global_wcs = global_wcs[:, :, kmin:kmax]

    # print(repr(global_wcs))

    fits_img_num = 0
    sav_img_num = 0

    for i, file in enumerate(sav_files_list):
        raster = scipy.io.readsav(file)['datatemp']

        for img in raster:
            if sav_img_num in (11150, 11773):
                sav_img_num += 1
                continue
            fits_file = fits_file_list[fits_img_num]
            wcs, _, _ = read_sg_image(fits_file, 'fuv2')
            # wcs = wcs[(slice(None), ) + indices]
            sg_image = img[indices].copy()
            nan_mask = np.isnan(sg_image)
            x = np.array([0])
            y = np.arange(sg_image.shape[0])
            wmin, _, _ = wcs.all_world2pix(lmin.value, 0, 0, 0)
            wmax, _, _ = wcs.all_world2pix(lmax.value, 0, 0, 0)
            w = np.arange(int(wmin), int(wmax))
            x, y, w = np.meshgrid(x, y, w, indexing='ij')
            sg_image[nan_mask] = 0
            x, y, w = x.flatten(), y.flatten(), w.flatten()
            ww, wy, wx = wcs.all_pix2world(w, y, x, 0)
            wx, wy = ((wx + 180) % 360) - 180, ((wy + 180) % 360) - 180
            gw, gy, gx = global_wcs.all_world2pix(ww, wy, wx, 0)
            gx, gy, gw = np.round(gx), np.round(gy), np.round(gw)
            gx, gy, gw = gx.astype(int), gy.astype(int), gw.astype(int)
            where_nonzero = sg_image[y, w] != 0.0
            global_data[gx[where_nonzero], gy[where_nonzero], gw[where_nonzero]] = sg_image[y, w][where_nonzero]
            fits_img_num += 1
            sav_img_num += 1

    return global_data, global_wcs


def build_mosaic_single_wavelength(fdm_data, fdm_wcs, indices: tp.Tuple[slice, slice] = (slice(None), slice(None))) -> tp.Tuple[np.ndarray, astropy.wcs.WCS]:

    xmax = (1000 * u.arcsec).to(u.deg)
    xmin = -xmax
    ymax = (1000 * u.arcsec).to(u.deg)
    ymin = -ymax
    lmin = (1393.7 * u.angstrom).to(u.m)
    lmax = (1393.8 * u.angstrom).to(u.m)

    sg_image = fdm_data[0]
    wcs = fdm_wcs[0]

    cdelt_x = (2 * u.arcsec).to(u.deg).value
    nx = (xmax - xmin) / (cdelt_x << u.deg)
    ny = (ymax - ymin) / (wcs.wcs.cdelt[1] << u.deg)
    nl = sg_image.shape[~0]

    nx = int(nx)
    ny = int(ny)
    nl = int(nl)

    wcs_dict = {
        'CTYPE1': 'WAVE',
        'CUNIT1': 'm',
        'CDELT1': wcs.wcs.cdelt[0],
        'CRPIX1': wcs.wcs.crpix[0],
        'CRVAL1': wcs.wcs.crval[0],
        'NAXIS1': nl,
        'CTYPE2': 'Solar Y',
        'CUNIT2': 'deg',
        'CDELT2': wcs.wcs.cdelt[1],
        'CRPIX2': 0,
        'CRVAL2': ymin.value,
        'NAXIS2': ny,
        'CTYPE3': 'Solar X',
        'CUNIT3': 'deg',
        'CDELT3': cdelt_x,
        'CRPIX3': 0,
        'CRVAL3': xmin.value,
        'NAXIS3': nx,
    }

    global_wcs = astropy.wcs.WCS(wcs_dict)

    kmin, jmin, imin = global_wcs.all_world2pix(lmin.value, ymin.value, xmin.value, 0)
    kmax, jmax, imax = global_wcs.all_world2pix(lmax.value, ymax.value, xmax.value, 0)
    kmin, jmin, imin = int(kmin), int(jmin), int(imin)
    kmax, jmax, imax = int(kmax), int(jmax), int(imax)

    kmin = 775
    kmax = kmin + 1

    global_data = np.full((nx, ny, kmax-kmin), fill_value=np.nan)
    global_wcs = global_wcs[:, :, kmin:kmax]

    for i, img in enumerate(fdm_data):

        sg_image = fdm_data[i]
        wcs = fdm_wcs[i]

        x = np.array([0])
        y = np.arange(sg_image.shape[0])
        wmin, _, _ = wcs.all_world2pix(lmin.value, 0, 0, 0)
        wmax, _, _ = wcs.all_world2pix(lmax.value, 0, 0, 0)
        w = np.arange(int(wmin), int(wmax))
        x, y, w = np.meshgrid(x, y, w, indexing='ij')
        x, y, w = x.flatten(), y.flatten(), w.flatten()
        ww, wy, wx = wcs.all_pix2world(w, y, x, 0)
        wx, wy = ((wx + 180) % 360) - 180, ((wy + 180) % 360) - 180
        gw, gy, gx = global_wcs.all_world2pix(ww, wy, wx, 0)
        gx, gy, gw = np.round(gx), np.round(gy), np.round(gw)
        gx, gy, gw = gx.astype(int), gy.astype(int), gw.astype(int)
        where_nonzero = np.isfinite(sg_image[y, 0])
        where_nonzero = np.squeeze(where_nonzero)
        global_data[gx[where_nonzero], gy[where_nonzero], 0] = sg_image[y, 0][where_nonzero]

    return global_data, global_wcs


def wcs_to_bins(cube: np.ndarray, w: astropy.wcs.WCS) -> tp.List[np.ndarray]:
    sh = cube.shape
    bins = []
    for axis_index, axis_length in enumerate(sh):
        w_i = np.arange(axis_length)
        x_i = np.arange(axis_length)
        y_i = np.arange(axis_length)
        pixels = np.stack([x_i, y_i, w_i]).transpose()
        coordinates = w.all_pix2world(pixels, 0)
        coordinates = coordinates[:, -1 - axis_index]
        bins.append(coordinates)
    return bins


def spectral_plot(cube, fits_spatial_sum, wcs_info, bins, name: str) -> tp.Tuple[np.ndarray, np.ndarray]:
    # Retrieved Spectrum
    mask = np.ones_like(cube)
    # nx = cube.shape[1]
    # ny = cube.shape[2]
    # rx = nx/2
    # ry = ny/2
    # x = np.linspace(-rx,rx,nx)
    # y = np.linspace(-ry,ry,ny)
    # x,y = np.meshgrid(x,y,indexing='ij')
    # circle_condition = x*x/(rx*rx) + y*y/(ry*ry)
    # mask[circle_condition > 1] = 0
    mask[cube == 0] = 0
    mask_summed = np.sum(mask, axis=(1, 2))
    # plt.imshow(mask)
    # spectrum = np.sum(cube*mask, axis=(1, 2))/np.sum(mask)
    # spectrum = np.sum(cube, axis=(1, 2))/mask_summed
    spectrum = np.sum(cube, axis=(1, 2))
    spectrum_max = np.max(spectrum)
    spectrum_norm = spectrum / spectrum_max

    # Provided .fits spectrum
    fits_spectrum = fits_spatial_sum
    fits_spectrum_max = np.max(fits_spectrum)
    fits_spectrum_norm = fits_spectrum / fits_spectrum_max

    c = 2.99792e5   #[km/s]
    wavelength = bins[0]
    lamref = wcs_info.wcs.crval[-1]
    delta_v = (c * (lamref - wavelength) / lamref)  #[km/s]

    # Plot each spectra
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(delta_v, spectrum_norm, label="Summed FDM spectrum")
    ax.plot(delta_v, fits_spectrum_norm, label=".fits file spectrum")
    ax.set_title('Normalized IRIS FDM {!s} spectra summed across disk'.format(name))
    ax.set_xlabel('Doppler Velocity (km/s)')
    ax.set_ylabel('Intensity (arb. unit)')
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels)

    # Plot difference between them
    figdiff, axdiff = plt.subplots(figsize=(8, 2))
    axdiff.plot(delta_v, spectrum_norm - fits_spectrum_norm)
    axdiff.set_title('Difference between the IRIS FDM spatially-summed {!s} spectra'.format(name))
    axdiff.set_xlabel('Doppler Velocity (km/s)')
    axdiff.set_ylabel('Difference (arb. unit)')

    return spectrum_max, fits_spectrum_max, mask_summed


# def convert_(self, new_unit_type, time_obs=None, response_version=4, detector_type: str = "FUV"):
#     # Get spectral dispersion per pixel.
#     spectral_wcs_index = np.where(np.array(self.wcs.wcs.ctype) == "WAVE")[0][0]
#     spectral_dispersion_per_pixel = self.wcs.wcs.cdelt[spectral_wcs_index] * \
#         self.wcs.wcs.cunit[spectral_wcs_index]
#     # Get solid angle from slit width for a pixel.
#     lat_wcs_index = ["HPLT" in c for c in self.wcs.wcs.ctype]
#     lat_wcs_index = np.arange(len(self.wcs.wcs.ctype))[lat_wcs_index]
#     lat_wcs_index = lat_wcs_index[0]
#     solid_angle = self.wcs.wcs.cdelt[lat_wcs_index] * \
#                   self.wcs.wcs.cunit[lat_wcs_index] * iris_tools.SLIT_WIDTH
#     # Get wavelength for each pixel.
#     spectral_data_index = (-1) * (np.arange(len(self.dimensions)) + 1)[spectral_wcs_index]
#     obs_wavelength = self.axis_world_coords(2)
#
#     if self.unit.is_equivalent(iris_tools.RADIANCE_UNIT):
#         new_data = self.data
#         new_uncertainty = self.uncertainty
#         new_unit = self.unit
#     else:
#         # Ensure spectrogram is in units of counts/s.
#         cube = self.convert_to("photons")
#         try:
#             cube = cube.apply_exposure_time_correction()
#         except ValueError(iris_tools.APPLY_EXPOSURE_TIME_ERROR):
#             pass
#         # Convert to radiance units.
#         new_data_quantities = iris_tools.convert_or_undo_photons_per_sec_to_radiance(
#             (cube.data * cube.unit, cube.uncertainty.array * cube.unit),
#             time_obs, response_version, obs_wavelength, detector_type,
#             spectral_dispersion_per_pixel, solid_angle)
#         new_data = new_data_quantities[0].value
#         new_uncertainty = new_data_quantities[1].value
#         new_unit = new_data_quantities[0].unit


def _solar_axes(wcs):
    """0-based FITS-axis indices of (Solar X, Solar Y), read from CTYPE."""
    ctypes = [str(c).upper() for c in wcs.wcs.ctype]
    ax_x = next(i for i, c in enumerate(ctypes) if 'X' in c)
    ax_y = next(i for i, c in enumerate(ctypes) if 'Y' in c)
    return ax_x, ax_y


def for_plotting(data2d, wcs2d):
    """Return (image, wcs) oriented so Solar X is horizontal.

    WCSAxes draws the FIRST WCS axis along the horizontal, and a
    matched image must be indexed in reversed FITS order. So the WCS
    axes are swapped and the image transposed TOGETHER -- doing one
    without the other misregisters the image against the coordinate
    grid. Use this at the plot boundary only; keep all science in the
    native orientation.

    Usage:
        img, w = for_plotting(display[:, :, j], wcs2d)
        ax = plt.subplot(projection=w)
        ax.imshow(img, origin='lower')
    """
    ax_x, _ = _solar_axes(wcs2d)
    if ax_x == 0:
        return data2d, wcs2d  # already Solar X first
    return data2d.T, wcs2d.swapaxes(0, 1)


def solar_geometry(wcs, shape, rsun_arcsec, center=(0.0, 0.0)):
    """Per-pixel radial distance and mu on the mosaic spatial grid.

    Axis-order aware: which WCS axis is Solar X vs Solar Y is read
    from CTYPE, so this works with the native (Y, X) WCS from
    build_mosaic / build_mosaic_slices AND with a swapped plotting
    WCS -- as long as `shape` is the shape of the MATCHING array.
    For a 3-axis WCS the spectral axis must be FITS axis 1 (as built
    by build_mosaic); it is evaluated at pixel 0.

    Parameters
    ----------
    wcs : astropy.wcs.WCS
        2-axis spatial or 3-axis (WAVE, Solar Y, Solar X) WCS.
    shape : tuple
        Spatial shape of the matching array, in that array's own
        numpy order (e.g. data.shape[:2] for the cube, img.shape for
        a plotting-oriented image).
    rsun_arcsec : float
        Apparent solar radius at the mosaic epoch, in arcsec.
        Per-epoch value, e.g.:
            from sunpy.coordinates import sun
            rsun_arcsec = sun.angular_radius(date).to_value(u.arcsec)
    center : (float, float)
        Disk-center position (x0, y0) in arcsec, from
        find_disk_center. Fit per mosaic; do not reuse one epoch's
        offset for another.

    Returns
    -------
    r : ndarray, `shape`
        Radial distance from disk center in arcsec.
    mu : ndarray, `shape`
        cos(heliocentric angle); NaN off the disk (r > rsun).
    """
    n = wcs.naxis
    ax_x, ax_y = _solar_axes(wcs)
    idx = np.indices(shape)
    npts = idx[0].size

    args = []
    for a in range(n):
        if a in (ax_x, ax_y):
            args.append(idx[n - 1 - a].ravel())  # numpy axis of FITS axis a
        else:
            args.append(np.zeros(npts))  # dummy spectral pixel
    world = wcs.all_pix2world(*args, 0)

    wx = (((world[ax_x] + 180) % 360) - 180) * 3600.0  # deg -> arcsec
    wy = (((world[ax_y] + 180) % 360) - 180) * 3600.0

    r = np.hypot(wx - center[0], wy - center[1]).reshape(shape)

    with np.errstate(invalid='ignore'):
        mu = np.sqrt(1.0 - (r / rsun_arcsec) ** 2)  # NaN where r > rsun
    return r, mu


def annulus_labels(mu, n=9, off_limb='drop'):
    """Equal-solar-surface-area annulus label per pixel.

    Equal surface area on the sphere == equal Delta-mu, so annulus k
    (k = 0 ... n-1, 0 = center circle) is mu in (1-(k+1)/n, 1-k/n].

    Parameters
    ----------
    mu : ndarray
        From solar_geometry (NaN off-disk). Labels come out in the
        same orientation as the mu array passed in.
    n : int
        Number of annuli.
    off_limb : 'drop' or 'outer'
        Policy for off-disk pixels (r > rsun): -1 (excluded) or folded
        into the outermost annulus n-1. Use the SAME policy at every
        epoch.

    Returns
    -------
    labels : int ndarray, same shape; -1 = excluded.
    """
    labels = np.full(mu.shape, -1, dtype=int)
    on = np.isfinite(mu)
    labels[on] = np.clip(np.floor((1.0 - mu[on]) * n), 0, n - 1).astype(int)
    if off_limb == 'outer':
        labels[~on] = n - 1
    return labels


def annulus_radii(rsun_arcsec, n=9):
    """Outer boundary radii of the n equal-surface-area annuli, arcsec.

    r_k = R * sqrt(k * (2n - k)) / n,  k = 1 ... n
    """
    k = np.arange(1, n + 1)
    return rsun_arcsec * np.sqrt(k * (2 * n - k)) / n


def _fit_circle(x, y):
    """Algebraic (Kasa) least-squares circle fit. Returns x0, y0, R."""
    A = np.column_stack([2 * x, 2 * y, np.ones_like(x)])
    b = x ** 2 + y ** 2
    (a, bb, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    return a, bb, np.sqrt(c + a ** 2 + bb ** 2)


def find_disk_center(image, wcs2d, threshold=None):
    """Fit the disk center from the limb in a full-disk intensity image.

    Use a bright plane (e.g. the line-core slice from
    build_mosaic_slices, built with skip_saa=False so the limb has as
    few gaps as possible). Works in either orientation, as long as
    `image` and `wcs2d` are a matched pair. The fitted center applies
    to the science cube too -- the strips share the same world frame.

    Parameters
    ----------
    image : ndarray, 2D
        Intensity image; off-disk pixels dim or NaN.
    wcs2d : astropy.wcs.WCS
        The matching celestial WCS.
    threshold : float, optional
        Disk/off-disk intensity cut. Default: 0.2 x median of finite
        positive pixels. Check the printed edge-point count if the
        default misbehaves.

    Returns
    -------
    x0, y0 : float
        Disk-center offset in arcsec -- pass as `center=` to
        solar_geometry and plot_annuli. Log these per epoch.
    r_fit : float
        Fitted limb radius, arcsec. DIAGNOSTIC ONLY: expect it a few
        arcsec ABOVE the photospheric (ephemeris) radius, because TR
        emission extends above the photospheric limb. Keep using the
        ephemeris radius for mu and the annuli; use r_fit only as a
        sanity check that the fit converged sensibly.
    """
    img = np.asarray(image, dtype=float)
    finite = np.isfinite(img)
    if threshold is None:
        threshold = 0.2 * np.nanmedian(img[finite & (img > 0)])
    mask = finite & (img > threshold)

    # Outermost mask crossings along both axes -> limb edge points.
    # Interior gaps (missing strips) don't produce edge points along
    # their own axis; the ones they produce along the other axis are
    # removed by the outlier-rejection pass below.
    pts = []
    for i in range(mask.shape[0]):
        j = np.flatnonzero(mask[i])
        if j.size >= 2:
            pts.append((i, j[0]))
            pts.append((i, j[-1]))
    for j in range(mask.shape[1]):
        i = np.flatnonzero(mask[:, j])
        if i.size >= 2:
            pts.append((i[0], j))
            pts.append((i[-1], j))
    pts = np.array(pts, dtype=float)

    # numpy axis 0 <-> FITS axis 2, numpy axis 1 <-> FITS axis 1;
    # which world output is X vs Y is read from CTYPE.
    ax_x, ax_y = _solar_axes(wcs2d)
    world = wcs2d.all_pix2world(pts[:, 1], pts[:, 0], 0)
    wx = (((world[ax_x] + 180) % 360) - 180) * 3600.0
    wy = (((world[ax_y] + 180) % 360) - 180) * 3600.0

    x0, y0, r_fit = _fit_circle(wx, wy)

    # One robust rejection pass: drop points off the fitted circle
    # (missing-strip artifacts, stray bright features), then refit.
    resid = np.hypot(wx - x0, wy - y0) - r_fit
    mad = 1.4826 * np.median(np.abs(resid - np.median(resid)))
    keep = np.abs(resid - np.median(resid)) < 3 * max(mad, 1e-6)
    x0, y0, r_fit = _fit_circle(wx[keep], wy[keep])

    print(f'find_disk_center: {keep.sum()}/{keep.size} edge points, '
          f'center=({x0:+.2f}, {y0:+.2f})", r_fit={r_fit:.2f}"')
    return x0, y0, r_fit


def plot_annuli(ax, rsun_arcsec, n=9, center=(0.0, 0.0), **kwargs):
    """Overlay annulus boundaries on a WCSAxes plot of the mosaic.

    `center` is (x0, y0) in arcsec regardless of orientation; the
    world-coordinate order the transform expects is read from the
    axes' own WCS, so this works with both native and for_plotting
    orientations.

    Usage:
        img, w = for_plotting(display[:, :, j], wcs2d)
        ax = plt.subplot(projection=w)
        ax.imshow(img, origin='lower')
        plot_annuli(ax, rsun_arcsec, center=(x0, y0))
    """
    from matplotlib.patches import Circle
    style = dict(fill=False, edgecolor='w', linewidth=0.6, alpha=0.7)
    style.update(kwargs)
    ax_x, _ = _solar_axes(ax.wcs)
    cx, cy = center[0] / 3600.0, center[1] / 3600.0  # arcsec -> deg
    cworld = (cx, cy) if ax_x == 0 else (cy, cx)
    for r in annulus_radii(rsun_arcsec, n) / 3600.0:
        ax.add_patch(Circle(cworld, r,
                            transform=ax.get_transform('world'), **style))


if __name__ == '__main__':
    # Science path -- native orientation, no transposes anywhere:
    #
    # x0, y0, r_fit = find_disk_center(display[:, :, 0], wcs2d)
    # r, mu = solar_geometry(wcs2d, data.shape[:2], rsun_arcsec,
    #                        center=(x0, y0))
    # labels = annulus_labels(mu, n=9, off_limb='drop')
    # means = [np.nanmean(data[:, :, 0][labels == i]) for i in range(9)]
    #
    # Plot path -- convert at the boundary, nowhere else:
    #
    # img, w = for_plotting(display[:, :, 0], wcs2d)
    # ax = plt.subplot(projection=w)
    # ax.imshow(img, origin='lower')
    # plot_annuli(ax, rsun_arcsec, center=(x0, y0))
    pass


def test_read_full_disk_mosaic():

    path = pl.Path(__file__).parent
    mosaic_filename = pl.Path('data/IRISMosaic_20130930_Si1393.fits')
    mosaic_filename = path / mosaic_filename

    cube, bins, cube_spatial_sum, exp_time = read_full_disk_mosaic(mosaic_filename)

    assert cube.size > 0                # .size is total number of elements in array
    assert cube.ndim == 3               # Verify it is 3D
    assert cube_spatial_sum.size > 0
    assert cube_spatial_sum.ndim == 1   # Verify it is 1D