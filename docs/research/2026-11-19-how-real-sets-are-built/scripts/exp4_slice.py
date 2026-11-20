"""Experiment 4: print a slice of a model as a grid, to see what is behind a face.

    uv run python exp4_slice.py MODEL.ldr AXIS VALUE [LO HI]

AXIS "z": the slice at z = VALUE studs (rows: plates from the top down; columns: x studs).
AXIS "x": the slice at x = VALUE studs (rows: plates; columns: z studs, front on the left).
Each cell shows the line number of the part whose box holds the cell's centre (last two
digits; '..' for empty). LO HI limit the plates shown (default: all). A reading aid only.
"""

import sys
from pathlib import Path

import numpy as np

from bricksnap.lab.edit import parts_in_box, world_box


def main() -> None:
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    axis, value = sys.argv[2], float(sys.argv[3])
    big = np.array([1e6, 1e6, 1e6])
    boxes = [(p.line, *world_box(p)) for p in parts_in_box(text, -big, big, mode="touching")]
    lo = np.min([b[1] for b in boxes], axis=0)
    hi = np.max([b[2] for b in boxes], axis=0)
    p_lo = int(sys.argv[4]) if len(sys.argv) > 5 else int(-hi[1] // 8)
    p_hi = int(sys.argv[5]) if len(sys.argv) > 5 else int(-lo[1] // 8) + 1
    col = 0 if axis == "z" else 2
    c_lo, c_hi = int(np.floor(lo[col] / 20)), int(np.ceil(hi[col] / 20))
    print("plate  " + " ".join(f"{c:>3d}" for c in range(c_lo, c_hi)))
    for plate in range(p_hi - 1, p_lo - 1, -1):
        y = -(plate + 0.5) * 8
        cells = []
        for c in range(c_lo, c_hi):
            pt = np.array([0.0, y, 0.0])
            pt[col] = (c + 0.5) * 20
            pt[2 if axis == "z" else 0] = value * 20
            hit = [ln for ln, a, b in boxes if np.all(pt > a) and np.all(pt < b)]
            cells.append(f"{hit[-1] % 100:>3d}" if hit else " ..")
        print(f"{plate:5d}  " + " ".join(cells))


if __name__ == "__main__":
    main()
