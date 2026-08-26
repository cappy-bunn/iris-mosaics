; Apply iris_prep.pro though the FUV background subtraction, then stop. (ie., includes dark subtraction, etc.)

f = file_search('./deep_mosaics/20151018/level_1/*.fits', count=nfits) ; gets local file listing
; nfits = 100 ; How many files to apply the following to, for testing only. Comment otherwise.
for kk =0,nfits-1 do begin 
 read_iris, f[kk], index, data 
 iris_prep, index, data, oindex, odata, /noflat, /nobad, /nowarp, /filter_fid

 hdr = struct2fitshead(oindex) 
 file = file_basename(f[kk])
 writefits, './deep_mosaics/20151018/level_11_plus_iris_prep_bg_sub/'+file, odata, hdr 
endfor
end