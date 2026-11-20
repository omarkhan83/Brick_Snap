"""Experiment 4: list a model's parts with the box each spans, nearest the front first.

    uv run python exp4_parts.py MODEL.ldr [ZMAX]

One line per part: line number, part, colour, and its box in studs (x, z: 20 LDU) and plates
(y: 8 LDU, counted UP from the ground, so a brick on the ground spans plates 0 to 3). Only parts
whose front (smallest z) is at most ZMAX LDU are listed (default: all). A reading aid for
choosing what to clear; it changes nothing.
"""

import sys
from pathlib import Path

import numpy as np

from bricksnap.lab.edit import parts_in_box, world_box


def main() -> None:
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    zmax = float(sys.argv[2]) if len(sys.argv) > 2 else 1e9
    big = np.array([1e6, 1e6, 1e6])
    rows = []
    for p in parts_in_box(text, -big, big, mode="touching"):
        a, b = world_box(p)
        if a[2] > zmax:
            continue
        rows.append((a[2], p, a, b))
    rows.sort(key=lambda r: (r[0], -r[2][1]))
    for _, p, a, b in rows:
        print(
            f"{p.line:4d} {p.key:14s} c{p.colour:<3d} "
            f"x {a[0] / 20:6.2f}..{b[0] / 20:6.2f}  z {a[2] / 20:6.2f}..{b[2] / 20:6.2f}  "
            f"plates {-b[1] / 8:5.2f}..{-a[1] / 8:5.2f}"
        )


if __name__ == "__main__":
    main()
