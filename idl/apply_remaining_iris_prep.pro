; After applying the first part of iris_prep using 'apply_iris_prep_through_bg_subtraction.pro' (getting "level 1.1" data), then applying own background subtraction (getting "level 1.2" data), this applies the rest of iris_prep to get level 1.5.

tic

; f = file_search('./deep_mosaics/20240811/level_12/*_fuv.fits', count=nfits) ; gets local file listing
f = file_search('./deep_mosaics/20240811/level_12/*.fits', count=nfits)

min_file_index = 0 ; Set to 0 for normal full dataset operations
; max_file_index = 1
max_file_index = nfits ; Set to nfits for normal full dataset operations

for kk =min_file_index,max_file_index-1 do begin 
 read_iris, f[kk], index, data 
 iris_prep, index, data, oindex, odata, /nosat, /nodark, /noback, /shift_wave, /shift_fid, /poly2d, /filter_wave, /filter_fid, /filter_aia

 hdr = struct2fitshead(oindex) 
 file = file_basename(f[kk])
 writefits, './deep_mosaics/20240811/level_15/'+file, odata, hdr 
 ; writefits, './deep_mosaics/20190912/'+'test_keywords_11.fits', odata, hdr 
endfor

toc

end