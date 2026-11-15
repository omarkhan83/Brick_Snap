# A flat model freezes the tab, and a zero-length ruler gives "Infinity studs"
- status: open
- owner: nobody

Two inputs with a zero measurement are accepted and then divided by:

- **Flat 3D model** (all points at the same height, such as an exported 2D logo). `setModel` and `build()`
  divide by the model height, the sizes become Infinity and NaN, the "very big build" guard is skipped
  because `NaN > 40000` is false, and `voxelize` loops forever. The tab hangs when Next is pressed on the
  Upload step. A model with zero width or depth ends in "No bricks fit" instead.
- **Ruler clicked twice on the same spot** (or two clicks a few pixels apart). `ready()` only checks that
  there are two clicks, so the scale is Infinity or absurdly large and every size reads "Infinity x Infinity
  studs". The message says to pick bigger bricks, which cannot help.

Done when a model with a zero dimension is rejected at upload with a clear message, the ruler step needs the
two clicks to be a sensible distance apart, and `build()` refuses any size that is not a finite number.

## Notes
Found in the 2026-11-15 code review.
