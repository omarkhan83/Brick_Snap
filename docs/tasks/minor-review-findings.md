# Smaller findings from the first code review
- status: open
- owner: nobody

Independent small items. Take any one; delete its line when it is fixed, and delete this file when empty.

- Ruler clicks are about 1-2% off: `pos()` (line 376) measures the canvas including its 3px border.
- A corrupt or unsupported image does nothing at all: no `onerror` on the image (lines 286-294) or on the
  model `FileReader` (lines 303-309).
- "This file doesn't say how big it is" never goes away after the user sets a height (`MODEL.guessed`,
  line 343).
- Not confirmed on real photos: `autoBox` (line 183) merges nearby blobs into the object's box, so a ruler
  placed right next to the object, as the instructions ask, may be included and inflate the size.
- The exported STL is made of overlapping closed shells (studs and tubes poke 0.1 mm into the brick body).
  Common slicers merge these; a strict mesh checker will complain.
- `tools/make-pawn.ps1` line 6 formats numbers using the computer's locale, so on a decimal-comma system it
  writes an invalid STL. The `make-*.ps1` scripts are Windows-only; the README does not say so.

## Notes
Found in the 2026-11-15 code review.
