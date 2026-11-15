# Large builds freeze the page, and every rebuild leaks graphics memory
- status: open
- owner: nobody

- `build()` runs everything in one go on every click of a size or fill button, including generating the full
  STL even if it is never downloaded. Near the size limit (measured: a solid 34x34x34 build) that is about
  2.5 seconds frozen, 3.6 million triangles, and a 180 MB file held in memory. The limit counts grid cells,
  not output size.
- Print renders every booklet page to an image at once; a 600-page booklet will likely run out of memory
  (not tested in a browser).
- Each rebuild creates new three.js geometries and materials and never disposes the old ones
  (lines 555-577, and the model preview material at line 337). Image and download blob URLs are never revoked.

Done when the STL is generated only on download, old 3D objects are disposed on rebuild, and the size limit
reflects what a browser can actually handle.

## Notes
Found in the 2026-11-15 code review.
