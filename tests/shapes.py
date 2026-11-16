"""Simple shapes built directly as Designs, for tests that should not depend on the voxeliser.

Sizes are given the way a builder thinks: studs across, and height in BRICKS (3 plates each).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from bricksnap.types import DEFAULT_COLOUR, EMPTY, Design


def _design(filled: np.ndarray, colour: int = DEFAULT_COLOUR) -> Design:
    colors = np.full(filled.shape, EMPTY, dtype=np.int16)
    colors[filled] = colour
    return Design(colors=colors)


def box(studs_x: int, studs_y: int, bricks_z: int, colour: int = DEFAULT_COLOUR) -> Design:
    return _design(np.ones((studs_x, studs_y, bricks_z * 3), dtype=bool), colour)


def cylinder(diameter: int, bricks_z: int, colour: int = DEFAULT_COLOUR) -> Design:
    """An upright cylinder ``diameter`` studs across."""
    c = diameter / 2
    x, y = np.meshgrid(np.arange(diameter) + 0.5, np.arange(diameter) + 0.5, indexing="ij")
    disc = (x - c) ** 2 + (y - c) ** 2 <= c * c
    return _design(np.repeat(disc[:, :, None], bricks_z * 3, axis=2), colour)


def sphere(diameter: int, colour: int = DEFAULT_COLOUR) -> Design:
    """A sphere ``diameter`` studs across (2.5 plates to the stud, so it is round in mm)."""
    nz = int(round(diameter * 2.5))
    c = diameter / 2
    x, y, z = np.meshgrid(
        np.arange(diameter) + 0.5, np.arange(diameter) + 0.5, np.arange(nz) + 0.5, indexing="ij"
    )
    inside = ((x - c) / c) ** 2 + ((y - c) / c) ** 2 + ((z - nz / 2) / (nz / 2)) ** 2 <= 1
    return _design(inside, colour)


def hollowed(design: Design, shell_studs: int = 2) -> Design:
    """The same outside shape with the deep inside emptied, keeping a shell.

    Mirrors the rule in bricksnap/voxelize.py: a cell is kept when an outside cell lies
    within ``shell_studs`` in x and y and ``3 * shell_studs`` in z; beyond the grid counts
    as outside.
    """
    filled = design.filled
    s = shell_studs
    structure = np.ones((2 * s + 1, 2 * s + 1, 6 * s + 1), dtype=bool)
    deep = ndimage.binary_erosion(filled, structure=structure, border_value=0)
    out = design.copy()
    out.colors[deep] = EMPTY
    return out


def striped(design: Design, colours: tuple[int, ...] = (4, 15), band_plates: int = 3) -> Design:
    """Recolour a design in horizontal bands, to exercise colour handling."""
    out = design.copy()
    for z in range(out.shape[2]):
        layer = out.colors[:, :, z]
        layer[layer != EMPTY] = colours[(z // band_plates) % len(colours)]
    return out
