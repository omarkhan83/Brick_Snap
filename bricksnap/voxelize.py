"""Seed to Design: decide which grid cells are filled, and what colour each is.

CONTRACT (tests are in tests/test_voxelize.py)

``voxelize(seed, catalog, hollow=False, shell_studs=2, margin_studs=2,
default_colour=DEFAULT_COLOUR) -> Design``

Grid
- A cell is CELL_MM = (8, 8, 3.2) mm. The body of the model needs
  ``ceil(extent / cell)`` cells per axis (at least 1; subtract a tiny epsilon before ceil so
  an exact multiple does not gain a cell).
- The grid is padded so later edits have room to grow the shape: ``margin_studs`` cells on
  each side in x and y, and ``3 * margin_studs`` cells above in z. Nothing is added below:
  the model stands on z = 0. ``Design.seed_offset`` is ``(margin_studs, margin_studs, 0)``.

Which cells are filled (port of the prototype, legacy/index.html lines 349-364)
1. Mark every cell the surface passes through, by sampling each triangle with points spaced
   under half a cell apart along every axis (cells are not cubes: scale accordingly).
2. Flood-fill the empty space inward from the outside of the grid (6-connected). Every cell
   the flood cannot reach is inside the model and is filled too.
   This tolerates scans with small holes, and guarantees a feature thinner than one cell
   still gets its cells rather than vanishing.

Colour
- If ``seed.face_colors`` is None every filled cell gets ``default_colour``.
- Otherwise snap each surface sample's RGB with ``catalog.nearest_colour`` (solid colours
  only) and give each surface cell the most common snapped colour among its samples. Cells
  with no sample (the inside) get the most common colour of the whole surface.

Hollow
- With ``hollow=True`` empty the deep inside and keep a shell. A filled cell is kept when
  some "outside" cell lies within ``shell_studs`` cells of it in x and in y and within
  ``3 * shell_studs`` cells in z (a box neighbourhood). Everything beyond the grid counts as
  outside, including below the ground, so a hollow model keeps a floor.
- Only space enclosed by the model is emptied; the outside shape must not change.

Other
- ``finish`` is all zeros; ``details``, ``regions`` and ``log`` start empty.
- Deterministic: the same inputs give an identical Design.
- Speed: a 200,000-triangle mesh at 48 studs in well under 10 seconds (use numpy and
  scipy.ndimage; no Python loop over cells or samples).

Implementation notes
--------------------
- Everything is done in cell units (millimetres divided by CELL_MM), where a cell is a unit
  cube, so the anisotropic 8 x 8 x 3.2 mm cell needs no special cases after that.
- The seed's vertices are expected to start at (0, 0, 0), as ``load_seed`` leaves them. If
  they do not, the model is moved there first rather than squashed into the grid. A point p
  strictly inside a cell is then in body cell floor(p / CELL_MM).
- Coordinates within 1e-4 of a cell (0.8 micrometres across, 0.3 up) of a cell boundary are
  snapped onto it. Binary STL, GLB and PLY store single precision, so a face meant to sit on
  a boundary comes back up to about 3e-5 of a cell off it; without the snap, the faces at
  right angles to it would reach into the next cell and fatten blocky models.
- Step 1 is exact rather than sampled. Point sampling at half-cell spacing (the prototype's
  method) misses about one surface cell in ten where a triangle only clips a cell's corner.
  Instead each triangle is clipped against the cell slabs, one axis after the other
  (Sutherland-Hodgman, vectorised; a piece has at most 9 corners), so every final piece is
  the part of one triangle inside one cell, with its exact area. The work is proportional
  to the cells a triangle passes through, not to its length, so the long slivers of CAD
  exports cost no more than evenly sized triangles. Triangles are processed in batches
  sized by an estimate of their piece count, to bound memory.
- A cell is marked when the surface passes through its inside; merely touching its boundary
  does not count, nor does reaching less than 1e-9 of a cell into it (so the side of a box
  whose base is 9.6 mm, which is 2.9999999999999996 plates in floating point, does not poke
  into the layer below). Pieces are clipped to the cell shrunk by that 1e-9.
- A face lying exactly on a cell boundary (every face of a box whose size is a whole number
  of cells) would then mark nothing, and rounding could put it a hair either side. So each
  triangle is first nudged 1e-6 of a cell (well over that 1e-9) against its normal, into
  the solid: a box's right face at exactly x = 10 cells goes in cell 9, its left face at
  x = 0 in cell 0, and a 10-cell box stays 10 cells wide wherever it sits. This uses the
  triangles' winding (the usual outward-facing convention); a face wound the wrong way
  lands one cell outside at worst, never leaves a gap. Anything that still ends up beyond
  the body is clamped into it. Zero-area triangles mark nothing.
- A "sample" for the colour vote is one (triangle, cell) piece, weighted by its area in
  square millimetres, so the vote follows visible surface area. Votes within one part in a
  million of the best count as a tie, and a tie goes to the lower LDraw code. "The most
  common colour of the whole surface" counts surface cells (ties again to the lower code).
- Colours are snapped with ``Catalog.nearest_colours`` (closest as eyes judge it; the
  first catalogue colour wins an exact tie).
  ``default_colour`` must be a solid colour of the catalogue.
- The flood fill labels the empty space (6-connected) and keeps the pieces that touch any
  face of the grid; beyond every face of the grid, including below z = 0, is outside.
- The hollow rule is a box erosion, done as three 1-D minimum filters.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from scipy import ndimage

from bricksnap.catalog import Catalog
from bricksnap.types import CELL_MM, DEFAULT_COLOUR, EMPTY, Design, Seed, SeedError

_CEIL_EPS = 1e-6  # cells; an exact multiple of the cell size does not gain a cell
_SNAP = 1e-4  # cells; coordinates this close to a cell boundary are put on it
_NUDGE = 1e-6  # cells; how far each triangle is moved into the solid before testing
_TOUCH = 1e-9  # cells; reaching less than this into a cell counts as only touching it
_TIE = 1e-6  # relative; colour votes this close to the best count as a tie
_PIECES = 250_000  # (triangle, cell) pieces made per batch, to bound memory


def voxelize(
    seed: Seed,
    catalog: Catalog,
    *,
    hollow: bool = False,
    shell_studs: int = 2,
    margin_studs: int = 2,
    default_colour: int = DEFAULT_COLOUR,
) -> Design:
    """Turn a Seed into a Design (see the module docstring for the rules)."""
    shell_studs = _whole(shell_studs, "shell_studs", minimum=1)
    margin_studs = _whole(margin_studs, "margin_studs", minimum=0)
    default_colour = _solid_colour(default_colour, catalog)
    vertices = np.asarray(seed.vertices, dtype=np.float64)
    faces = np.asarray(seed.faces, dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("Seed.vertices must be an (n, 3) array")
    if faces.size == 0:
        raise SeedError("The model has no triangles, so there is nothing to turn into bricks.")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("Seed.faces must be an (m, 3) array")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("Seed.faces refers to vertices that do not exist")
    if not np.isfinite(vertices[faces]).all():
        raise SeedError("The model is damaged: some of its points have no valid position.")
    face_colors = seed.face_colors
    if face_colors is not None:
        face_colors = np.asarray(face_colors)
        if face_colors.shape != (len(faces), 3):
            raise ValueError("Seed.face_colors must be an (m, 3) array, one RGB per face")

    tris = vertices[faces]
    tris = (tris - tris.reshape(-1, 3).min(axis=0)) / np.asarray(CELL_MM, dtype=np.float64)
    nearest = np.round(tris)
    tris = np.where(np.abs(tris - nearest) < _SNAP, nearest, tris)  # (m, 3, 3) in cells
    extent = tris.reshape(-1, 3).max(axis=0)
    nx, ny, nz = (int(max(1, np.ceil(e - _CEIL_EPS))) for e in extent)
    body = (nx, ny, nz)

    # colour of each face, as an index into `codes`
    if face_colors is None:
        codes = np.asarray([default_colour], dtype=np.int64)
        face_code = np.zeros(len(faces), dtype=np.int64)
    else:
        codes, face_code = _snap(face_colors, catalog)

    # 1. every cell the surface passes through, and the colour vote in it
    cell_flat, piece_code, weight = _surface_cells(tris, body, face_code, len(codes))
    surface_colour = np.full(nx * ny * nz, EMPTY, dtype=np.int64)
    if len(cell_flat):
        win_cell, win_code = _vote(cell_flat, piece_code, weight, len(codes))
        surface_colour[win_cell] = codes[win_code]
    surface_colour = surface_colour.reshape(body)
    surface = surface_colour != EMPTY

    # 2. flood the empty space from outside the grid; what it cannot reach is inside
    filled = _fill_inside(surface)
    inside_colour = _most_common(surface_colour[surface]) if surface.any() else default_colour
    colours = np.where(surface, surface_colour, np.where(filled, inside_colour, EMPTY))

    if hollow:
        colours[filled & ~_keep_shell(filled, shell_studs)] = EMPTY

    m = margin_studs
    grid = np.full((nx + 2 * m, ny + 2 * m, nz + 3 * m), EMPTY, dtype=np.int16)
    grid[m : m + nx, m : m + ny, :nz] = colours
    return Design(colors=grid, seed_offset=(m, m, 0))


# ---- helpers --------------------------------------------------------------------------------


def _whole(value: Any, name: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | np.integer) or value < minimum:
        raise ValueError(f"{name} must be a whole number of at least {minimum}, not {value!r}")
    return int(value)


def _solid_colour(value: Any, catalog: Catalog) -> int:
    colour = None
    if isinstance(value, int | np.integer) and not isinstance(value, bool):
        colour = catalog.colours.get(int(value))
    if colour is None or colour.transparent:
        raise ValueError(
            f"default_colour must be the LDraw code of a solid colour in the parts table, "
            f"not {value!r}"
        )
    return int(colour.code)


def _snap(face_colors: np.ndarray, catalog: Catalog) -> tuple[np.ndarray, np.ndarray]:
    """Snap every distinct face RGB to the catalogue: (sorted codes, code index per face).

    The snapping itself is ``Catalog.nearest_colours`` (solid colours only), so a colour
    lands on the same catalogue colour here as anywhere else in BrickSnap."""
    rgb = np.clip(np.round(face_colors.astype(np.float64)), 0, 255)
    distinct, which = np.unique(rgb, axis=0, return_inverse=True)
    snapped = catalog.nearest_colours(distinct, solid_only=True)
    codes, code_index = np.unique(snapped, return_inverse=True)
    return codes, code_index[which.ravel()]


def _vote(
    cell: np.ndarray, code: np.ndarray, weight: np.ndarray, n_codes: int
) -> tuple[np.ndarray, np.ndarray]:
    """The winning colour index of each cell: most area, near-ties to the lower index.

    ``code`` indexes the sorted LDraw codes, so the lower index is the lower code."""
    unique, inverse = np.unique(cell * n_codes + code, return_inverse=True)
    votes = np.bincount(inverse.ravel(), weights=weight, minlength=len(unique))
    vote_cell, vote_code = unique // n_codes, unique % n_codes  # by cell, then by code
    starts = np.flatnonzero(np.r_[True, vote_cell[1:] != vote_cell[:-1]])
    best = np.maximum.reduceat(votes, starts)
    best = np.repeat(best, np.diff(np.r_[starts, len(votes)]))
    contender = np.flatnonzero(votes >= best * (1.0 - _TIE))
    _, first = np.unique(vote_cell[contender], return_index=True)  # lowest code per cell
    winners = contender[first]
    return vote_cell[winners], vote_code[winners]


def _most_common(values: np.ndarray) -> int:
    found, counts = np.unique(values, return_counts=True)
    return int(found[np.argmax(counts)])  # np.unique sorts, so ties go to the lower code


def _surface_cells(
    tris: np.ndarray, body: tuple[int, int, int], face_code: np.ndarray, n_codes: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every (cell, triangle) pair where the triangle passes through the cell's inside.

    ``tris`` is (m, 3, 3) in cell units, ``face_code`` the colour index of each triangle.
    Returns flat body-cell indices, the colour index of each pair, and its vote weight: the
    area (mm²) of the triangle inside the cell where colours compete, else 1. Exact areas
    take a full clip, so they are only worked out for the cells that need them.
    """
    normal = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(normal, axis=1)
    keep = np.flatnonzero(length > 0)  # zero-area triangles mark nothing
    unit = normal[keep] / length[keep, None]
    nudged = tris[keep] - _NUDGE * unit[:, None, :]  # into the solid, against the normal

    # a rough count of the pieces each triangle makes: its projected areas plus its spans
    span = nudged.max(axis=1) - nudged.min(axis=1)
    estimate = 0.5 * np.abs(normal[keep]).sum(axis=1) + span.sum(axis=1) + 1.0
    # cut along the axis with the most slabs last: that cut makes the most pieces, and the
    # last cut can be skipped when only the cells are wanted
    axes = tuple(int(i) for i in np.argsort(span.sum(axis=0), kind="stable"))
    shape = np.asarray(body, dtype=np.int64)

    def flat(cell: np.ndarray) -> np.ndarray:
        cell = np.clip(cell, 0, shape - 1)
        return np.ravel_multi_index((cell[:, 0], cell[:, 1], cell[:, 2]), body)

    # pass 1: which cells each triangle passes through (no areas)
    cells_out, which_out = [], []
    for batch in _batches(np.arange(len(keep)), estimate):
        _, _, owner, cell = _clip_to_cells(nudged[batch], axes)
        if n_codes == 1:  # one colour: only the set of cells matters
            cells_out.append(np.unique(flat(cell)))
            continue
        cells_out.append(flat(cell))
        which_out.append(batch[owner])
    if not cells_out:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty, np.zeros(0)
    cell_flat = np.concatenate(cells_out)
    weight = np.ones(len(cell_flat))
    if n_codes == 1:
        return cell_flat, np.zeros(len(cell_flat), dtype=np.int64), weight
    which = np.concatenate(which_out)  # position in `keep` of each piece's triangle
    code = face_code[keep[which]]

    # pass 2: exact areas for the pieces in cells where more than one colour meets
    pairs = np.unique(cell_flat * n_codes + code) // n_codes
    contested = np.zeros(int(np.prod(shape)), dtype=bool)
    contested[pairs[1:][pairs[1:] == pairs[:-1]]] = True
    in_contest = contested[cell_flat]
    if not in_contest.any():
        return cell_flat, code, weight
    involved = np.unique(which[in_contest])
    cells_out, codes_out, weights_out = [], [], []
    for batch in _batches(involved, estimate[involved]):
        poly, count, owner, cell = _clip_to_cells(
            nudged[batch], axes, select=lambda c: contested[flat(c)]
        )
        cells_out.append(flat(cell))
        codes_out.append(face_code[keep[batch[owner]]])
        weights_out.append(_polygon_area_mm(poly, count))
    return (
        np.concatenate([cell_flat[~in_contest], *cells_out]),
        np.concatenate([code[~in_contest], *codes_out]),
        np.concatenate([weight[~in_contest], *weights_out]),
    )


def _batches(items: np.ndarray, estimate: np.ndarray) -> list[np.ndarray]:
    """Split ``items`` into runs whose estimated piece counts add up to about _PIECES."""
    bounds = np.searchsorted(np.cumsum(estimate), np.arange(_PIECES, estimate.sum(), _PIECES))
    return [b for b in np.split(items, np.unique(bounds)) if len(b)]


def _clip_to_cells(
    tris: np.ndarray,
    axes: tuple[int, ...] = (0, 1, 2),
    select: Callable[[np.ndarray], np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Cut triangles (p, 3, 3) into their parts inside each cell (shrunk by _TOUCH).

    Returns the pieces as padded polygons (q, w, 3) with w <= 9, their corner counts (q,),
    the triangle each came from (q,) and its cell (q, 3). The cells are always exact, but
    without ``select`` the pieces are not clipped along the last axis. With ``select``
    (cells (q, 3) -> bool mask), only the selected pieces are returned, fully clipped.
    """
    p = len(tris)
    poly = np.array(tris, dtype=np.float64)
    count = np.full(p, 3, dtype=np.int64)
    owner = np.arange(p)
    cell = np.zeros((p, 3), dtype=np.int64)
    for step_index, axis in enumerate(axes):
        used = np.arange(poly.shape[1])[None, :] < count[:, None]
        coord = poly[:, :, axis]
        low = np.where(used, coord, np.inf).min(axis=1)
        high = np.where(used, coord, -np.inf).max(axis=1)
        first = np.floor(low + _TOUCH).astype(np.int64)
        last = np.ceil(high - _TOUCH).astype(np.int64) - 1  # slabs whose inside it reaches
        n_slabs = np.maximum(last - first + 1, 0)
        rep = np.repeat(np.arange(len(poly)), n_slabs)
        k = first[rep] + np.arange(len(rep)) - np.repeat(np.cumsum(n_slabs) - n_slabs, n_slabs)
        owner, count, cell = owner[rep], count[rep], cell[rep]
        cell[:, axis] = k
        if step_index == len(axes) - 1:
            if select is None:
                return poly[rep], count, owner, cell
            chosen = np.flatnonzero(select(cell))
            rep, k, owner, count, cell = (
                rep[chosen],
                k[chosen],
                owner[chosen],
                count[chosen],
                cell[chosen],
            )
        poly, low, high = poly[rep], low[rep], high[rep]
        for bound, above, cut in (
            (k + _TOUCH, True, low < k + _TOUCH),
            (k + 1.0 - _TOUCH, False, high > k + 1.0 - _TOUCH),
        ):
            rows = np.flatnonzero(cut)
            if len(rows) == 0:
                continue
            clipped, new_count = _clip(poly[rows], count[rows], axis, bound[rows], above=above)
            if clipped.shape[1] > poly.shape[1]:
                poly = np.concatenate([poly, np.zeros((len(poly), 1, 3))], axis=1)
            poly[rows] = clipped
            count[rows] = new_count
        width = int(count.max()) if len(count) else 3
        poly = poly[:, : max(width, 3)]
    return poly, count, owner, cell


def _clip(
    poly: np.ndarray, count: np.ndarray, axis: int, bound: np.ndarray, *, above: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Keep the part of each convex polygon on one side of the plane coord[axis] = bound.

    Returns polygons one corner wider than the input (a cut adds at most one corner)."""
    q, width, _ = poly.shape
    slots = np.arange(width)
    used = slots[None, :] < count[:, None]
    following = np.where(slots[None, :] + 1 < count[:, None], slots[None, :] + 1, 0)
    a = poly
    b = poly[np.arange(q)[:, None], following]
    da = a[:, :, axis] - bound[:, None]
    db = b[:, :, axis] - bound[:, None]
    if not above:
        da, db = -da, -db
    a_in, b_in = da >= 0, db >= 0
    crossing = used & (a_in != b_in)
    t = np.divide(da, da - db, out=np.zeros_like(da), where=crossing)
    meet = a + t[:, :, None] * (b - a)
    meet[:, :, axis] = bound[:, None]
    out = np.stack([a, meet], axis=2).reshape(q, 2 * width, 3)
    ok = np.stack([used & a_in, crossing], axis=2).reshape(q, 2 * width)
    row, col = np.nonzero(ok)
    dest = (np.cumsum(ok, axis=1) - 1)[row, col]
    result = np.zeros((q, width + 1, 3))
    result[row, dest] = out[row, col]
    return result, ok.sum(axis=1)


def _polygon_area_mm(poly: np.ndarray, count: np.ndarray) -> np.ndarray:
    """Area in mm² of each flat convex polygon (padded corners beyond ``count`` ignored)."""
    mm = poly * np.asarray(CELL_MM)
    rel = mm[:, 1:] - mm[:, :1]
    fan = np.cross(rel[:, :-1], rel[:, 1:])  # triangle (0, i, i + 1) for i = 1 .. w - 2
    real = (np.arange(1, poly.shape[1] - 1)[None, :] + 1) < count[:, None]
    return 0.5 * np.linalg.norm((fan * real[:, :, None]).sum(axis=1), axis=1)


def _fill_inside(surface: np.ndarray) -> np.ndarray:
    """Surface plus every empty cell the outside cannot reach through faces (6-connected)."""
    empty = ~surface
    labels, _ = ndimage.label(empty, structure=ndimage.generate_binary_structure(3, 1))
    border = np.concatenate(
        [
            labels[0].ravel(),
            labels[-1].ravel(),
            labels[:, 0].ravel(),
            labels[:, -1].ravel(),
            labels[:, :, 0].ravel(),
            labels[:, :, -1].ravel(),
        ]
    )
    outside_labels = np.unique(border[border > 0])
    outside = np.isin(labels, outside_labels)
    return ~outside


def _keep_shell(filled: np.ndarray, shell_studs: int) -> np.ndarray:
    """Filled cells with an outside cell within the shell box (beyond the grid is outside)."""
    s = shell_studs
    deep = filled.astype(np.uint8)
    for axis, size in ((0, 2 * s + 1), (1, 2 * s + 1), (2, 6 * s + 1)):
        deep = ndimage.minimum_filter1d(deep, size=size, axis=axis, mode="constant", cval=0)
    return filled & (deep == 0)
