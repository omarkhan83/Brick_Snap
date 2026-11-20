"""Tests for the layout solver (bricksnap/layout.py).

Connectivity is checked here directly with bricksnap.connect (not bricksnap.checks), so these
tests stand on their own: one piece means one connected component of the connection graph.
"""

from __future__ import annotations

import base64
import time
import zlib
from collections import Counter, defaultdict

import networkx as nx
import numpy as np
import pytest
import shapes
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from bricksnap.connect import connection_graph, occupancy
from bricksnap.layout import solve
from bricksnap.types import DEFAULT_COLOUR, EMPTY, Build, Design

WHITE, RED = 15, 4

CASES = {
    "box-6x4x4": lambda: shapes.box(6, 4, 4),
    "box-12x12x4": lambda: shapes.box(12, 12, 4),
    "box-20x20x20": lambda: shapes.box(20, 20, 20),
    "cylinder-8x6": lambda: shapes.cylinder(8, 6),
    "cylinder-12x10": lambda: shapes.cylinder(12, 10),
    "cylinder-20x16": lambda: shapes.cylinder(20, 16),
    "sphere-8": lambda: shapes.sphere(8),
    "sphere-16": lambda: shapes.sphere(16),
    "sphere-24": lambda: shapes.sphere(24),
}


# ---- helpers ----------------------------------------------------------------------------------


def design_of(filled: np.ndarray, colour: int = DEFAULT_COLOUR) -> Design:
    return Design(colors=np.where(filled, colour, EMPTY).astype(np.int16))


def assert_build_matches_design(design, build, catalog, *, known_colours=True):
    """Every filled cell is covered by exactly one part of its colour; nothing else is."""
    occ, collisions, out_of_bounds, unknown = occupancy(build, catalog)
    assert build.shape == design.shape
    assert not collisions, f"{len(collisions)} pairs of parts overlap"
    assert not out_of_bounds, f"{len(out_of_bounds)} parts stick out of the grid"
    if known_colours:
        assert not unknown, f"{len(unknown)} parts are not real part and colour pairs"
    assert np.array_equal(occ >= 0, design.filled), (
        "the parts do not cover exactly the filled cells"
    )
    part_colour = np.array([p.color for p in build.parts], dtype=np.int16)
    covered = occ >= 0
    assert np.array_equal(part_colour[occ[covered]], design.colors[covered]), (
        "a part has the wrong colour"
    )
    for p in build.parts:
        assert catalog.parts[p.part].kind in ("brick", "plate")
        assert p.rot in (0, 90)
        assert p.step >= 1, "every part needs a building step"
    assert build.report is None


def pieces(build: Build, catalog) -> list[int]:
    """Sizes (in parts) of the connected pieces, largest first."""
    g = connection_graph(build, catalog)
    return sorted((len(c) for c in nx.connected_components(g)), reverse=True)


def assert_one_piece(build: Build, catalog) -> None:
    got = pieces(build, catalog)
    assert len(got) == 1, f"{len(got)} pieces; loose parts: {sum(got[1:])} (sizes {got[:8]})"


def solve_checked(design, catalog, **kw) -> Build:
    build = solve(design, catalog, **kw)
    assert_build_matches_design(design, build, catalog)
    return build


def lower_bound(colors: np.ndarray) -> int:
    """Fewest pieces any layout of these cells can have, worked out without the solver.

    Join every two vertically adjacent filled cells (they are always in one part or in two
    parts that hold each other) and every two side-by-side cells of one colour (one part
    could cover both). Parts can join nothing else, so no layout has fewer pieces than this.
    """
    filled = colors != EMPTY
    idx = np.full(colors.shape, -1, dtype=np.int64)
    n = int(filled.sum())
    idx[filled] = np.arange(n)
    rows, cols = [], []
    for axis in range(3):
        lo = tuple(slice(None, -1) if a == axis else slice(None) for a in range(3))
        hi = tuple(slice(1, None) if a == axis else slice(None) for a in range(3))
        m = filled[lo] & filled[hi]
        if axis < 2:
            m &= colors[lo] == colors[hi]
        rows.append(idx[lo][m])
        cols.append(idx[hi][m])
    r, c = np.concatenate(rows), np.concatenate(cols)
    graph = coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n))
    return int(connected_components(graph, directed=False)[0])


def decode_design(shape: tuple[int, int, int], packed: str) -> Design:
    """A design stored as zlib + base64 text, one character per cell: '.', 'r' or 'w'."""
    text = zlib.decompress(base64.b64decode(packed)).decode()
    codes = {".": EMPTY, "r": RED, "w": WHITE}
    return Design(colors=np.array([codes[ch] for ch in text], dtype=np.int16).reshape(shape))


# ---- the acceptance shapes --------------------------------------------------------------------


@pytest.mark.parametrize("hollow", [False, True], ids=["solid", "hollow"])
@pytest.mark.parametrize("case", list(CASES))
def test_acceptance_shapes_build_as_one_piece(case, hollow, catalog):
    design = CASES[case]()
    if hollow:
        design = shapes.hollowed(design)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)


def test_hollow_shapes_really_are_hollow(catalog):
    # make sure the hollow cases above exercise a cavity and a ceiling held from above
    design = shapes.hollowed(shapes.box(20, 20, 20))
    assert (design.colors == EMPTY).sum() > 0
    build = solve_checked(design, catalog)
    occ = occupancy(build, catalog)[0]
    hanging = 0
    for p in build.parts:
        w, d, _ = catalog.footprint(p)
        if p.z > 0 and (occ[p.x : p.x + w, p.y : p.y + d, p.z - 1] < 0).all():
            hanging += 1
    assert hanging > 0, "the ceiling over the cavity should hang from the parts above it"
    assert_one_piece(build, catalog)


@pytest.mark.parametrize("shell", [1, 2])
@pytest.mark.parametrize(
    "make",
    [lambda: shapes.box(10, 10, 8), lambda: shapes.cylinder(16, 8), lambda: shapes.sphere(20)],
    ids=["box", "cylinder", "sphere"],
)
def test_thin_shells_build_as_one_piece(make, shell, catalog):
    # a one-stud shell has floors and ceilings one brick thick: bricks alone fall apart there
    design = shapes.hollowed(make(), shell)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)


# ---- colours ----------------------------------------------------------------------------------


@pytest.mark.parametrize("band", [3, 4, 2, 1], ids=["band3", "band4", "band2", "band1"])
def test_striped_two_colours_build_as_one_piece(band, catalog):
    design = shapes.striped(shapes.cylinder(12, 8), band_plates=band)
    build = solve_checked(design, catalog)
    assert {p.color for p in build.parts} == {4, 15}
    assert_one_piece(build, catalog)


def test_striped_sphere_with_colour_changes_inside_courses(catalog):
    design = shapes.striped(shapes.sphere(16), colours=(4, 15, 1), band_plates=2)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)


def test_two_colours_meeting_inside_a_course(catalog):
    design = shapes.box(8, 6, 4)
    design.colors[:, :, :4] = 4  # the colour changes between plate 3 and plate 4
    design.colors[:, :, 4:] = 15
    build = solve_checked(design, catalog)
    kinds = Counter(catalog.parts[p.part].kind for p in build.parts)
    assert kinds["plate"] > 0 and kinds["brick"] > 0
    assert_one_piece(build, catalog)


def test_two_colours_side_by_side_with_staggered_boundary(catalog):
    design = shapes.box(8, 8, 4)
    for z in range(design.shape[2]):
        design.colors[:, :, z] = 15
        design.colors[: 3 + 2 * ((z // 3) % 2), :, z] = 4  # boundary moves every course
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)


def test_two_colours_split_by_a_straight_wall_cannot_join(catalog):
    """Known impossibility: parts are one colour each and side-by-side parts do not hold
    each other, so a red half and a white half meeting on one vertical plane through every
    layer can never be one piece. The solver must still cover it, without raising."""
    design = shapes.box(8, 6, 3)
    design.colors[:4] = 4
    design.colors[4:] = 15
    build = solve_checked(design, catalog)
    assert len(pieces(build, catalog)) == 2


def test_only_real_part_and_colour_pairs(catalog):
    # the 2x8 brick (3007) does not exist in Dark Tan (28), the 2x4 (3001) does
    assert catalog.exists("3001", 28) and not catalog.exists("3007", 28)
    design = shapes.box(16, 16, 4, colour=28)
    build = solve_checked(design, catalog)
    assert all(catalog.exists(p.part, p.color) for p in build.parts)
    assert "3007" not in {p.part for p in build.parts}
    assert_one_piece(build, catalog)
    # in a colour that has it, the 2x8 is used on a big plain box
    build = solve_checked(shapes.box(16, 16, 4, colour=71), catalog)
    assert "3007" in {p.part for p in build.parts}


def test_many_colours_use_only_existing_parts(catalog):
    colours = (308, 36, 43, 46, 78, 92)  # colours with the most missing parts
    design = shapes.box(16, 12, 4)
    for i, c in enumerate(colours):
        design.colors[:, :, 2 * i : 2 * i + 2] = c
    build = solve_checked(design, catalog)
    assert all(catalog.exists(p.part, p.color) for p in build.parts)
    assert_one_piece(build, catalog)


def test_colour_with_no_parts_uses_one_by_ones_and_does_not_raise(catalog):
    design = shapes.box(3, 2, 2, colour=9999)  # not a catalogue colour at all
    build = solve(design, catalog)
    assert_build_matches_design(design, build, catalog, known_colours=False)
    assert {(catalog.parts[p.part].sx, catalog.parts[p.part].sz) for p in build.parts} == {(1, 1)}


# ---- awkward shapes ---------------------------------------------------------------------------


def test_single_cell(catalog):
    design = design_of(np.ones((1, 1, 1), dtype=bool))
    build = solve_checked(design, catalog)
    assert [(p.part, p.x, p.y, p.z, p.step) for p in build.parts] == [("3024", 0, 0, 0, 1)]


def test_empty_design_gives_empty_build(catalog):
    design = design_of(np.zeros((4, 3, 6), dtype=bool))
    build = solve(design, catalog)
    assert build.parts == [] and build.shape == (4, 3, 6)


def test_single_brick_cell_is_one_brick(catalog):
    build = solve_checked(design_of(np.ones((1, 1, 3), dtype=bool)), catalog)
    assert [p.part for p in build.parts] == ["3005"]


@pytest.mark.parametrize("dims", [(1, 16, 4), (16, 1, 4), (1, 30, 3)])
def test_one_wide_wall(dims, catalog):
    build = solve_checked(shapes.box(*dims), catalog)
    assert_one_piece(build, catalog)


def test_one_wide_wall_one_brick_tall_uses_plates(catalog):
    # a single course longer than 8 studs cannot hold together as bricks, but staggered
    # plates can
    build = solve_checked(shapes.box(16, 1, 1), catalog)
    assert_one_piece(build, catalog)
    assert all(catalog.parts[p.part].kind == "plate" for p in build.parts)


def test_one_brick_tall_slab_holds_together(catalog):
    build = solve_checked(shapes.box(6, 4, 1), catalog)
    assert_one_piece(build, catalog)


def test_slab_that_is_one_part_stays_one_brick(catalog):
    build = solve_checked(shapes.box(4, 2, 1), catalog)
    assert [p.part for p in build.parts] == ["3001"]


def test_single_plate_layer_too_long_cannot_join(catalog):
    """Known impossibility: one layer of plates 9 studs long needs two parts side by side,
    and side-by-side parts do not hold each other."""
    build = solve_checked(design_of(np.ones((1, 9, 1), dtype=bool)), catalog)
    assert len(pieces(build, catalog)) == 2


def test_l_shape(catalog):
    filled = np.zeros((8, 8, 9), dtype=bool)
    filled[:, :3, :] = True
    filled[:3, :, :] = True
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)


def test_l_shape_thin_and_short(catalog):
    filled = np.zeros((10, 10, 6), dtype=bool)
    filled[:, :1, :] = True
    filled[:1, :, :] = True
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)


@pytest.mark.parametrize("nz", [1, 2, 4, 5, 7, 8, 10, 11])
def test_heights_that_are_not_whole_bricks(nz, catalog):
    footprint = (4, 2) if nz == 1 else (9, 7)  # one plate layer only joins as one part
    design = design_of(np.ones((*footprint, nz), dtype=bool))
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)
    if nz >= 3:
        assert any(catalog.parts[p.part].kind == "brick" for p in build.parts)


def test_overhanging_table_top(catalog):
    # four legs and a top one brick thick: the top hangs off the legs
    filled = np.zeros((12, 12, 12), dtype=bool)
    for x0 in (0, 10):
        for y0 in (0, 10):
            filled[x0 : x0 + 2, y0 : y0 + 2, :9] = True
    filled[:, :, 9:] = True
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)


def test_awkward_design_does_not_raise(catalog):
    design = shapes.box(8, 8, 2)
    x, y, _ = np.indices(design.shape)
    design.colors[(x + y) % 2 == 0] = 4  # checkerboard: nothing can be joined
    build = solve_checked(design, catalog)
    assert len(build.parts) == 64 * 2  # a 1x1 brick per column per course


# ---- thin features one plate thick ------------------------------------------------------------
#
# Every design in this section was checked independently to allow ONE piece (or the stated
# number): an exact search over all plate tilings with connectivity constraints found such
# a layout, and that layout was verified with bricksnap.connect. A brick can always be
# swapped for three stacked plates with the same connections, so plate tilings are enough.
# The solver used to leave loose parts on all of them.


def wall_with_shelf(depth: int, height: int, length: int = 8) -> Design:
    """A wall 2 studs thick, 8 long and 4 bricks tall with a shelf one plate thick."""
    colors = np.full((2 + depth, 8, 12), EMPTY, dtype=np.int16)
    colors[:2] = WHITE
    colors[2:, :length, height] = WHITE
    return Design(colors=colors)


@pytest.mark.parametrize("height", [0, 3, 4, 7, 11])
@pytest.mark.parametrize("depth", [2, 3, 4, 5, 6])
def test_wall_with_one_plate_shelf_is_one_piece(depth, height, catalog):
    # the shelf's cells have nothing above or below: only a plate reaching back into the
    # wall can hold them, so the wall bricks beside the shelf have to become plates
    build = solve_checked(wall_with_shelf(depth, height), catalog)
    assert_one_piece(build, catalog)


@pytest.mark.parametrize("height", [0, 4, 7, 9, 10])
@pytest.mark.parametrize("depth", [4, 6])
def test_wall_with_short_deep_shelf_is_one_piece(depth, height, catalog):
    build = solve_checked(wall_with_shelf(depth, height, length=4), catalog)
    assert_one_piece(build, catalog)


def tiny_designs() -> dict[str, Design]:
    seven = np.full((2, 2, 4), EMPTY, dtype=np.int16)
    seven[1, 1, :] = WHITE
    seven[0, 1, 2:] = WHITE
    seven[1, 0, 3] = WHITE
    eight = np.full((2, 4, 2), EMPTY, dtype=np.int16)  # plates only
    eight[0, 1:3, 0] = WHITE
    eight[1, 2, 0] = WHITE
    eight[0, 0:3, 1] = WHITE
    eight[1, 2:4, 1] = WHITE
    bar = np.full((6, 1, 6), EMPTY, dtype=np.int16)  # a 1x6 bar one plate thick on a post
    bar[:, 0, 3] = WHITE
    bar[0, 0, 3:] = WHITE
    return {
        "seven-cells": Design(colors=seven),
        "eight-cells": Design(colors=eight),
        "bar": Design(colors=bar),
    }


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
@pytest.mark.parametrize("name", ["seven-cells", "eight-cells", "bar"])
def test_tiny_designs_that_need_the_right_parts(name, seed, catalog):
    # seven cells: a 1x2 plate at z=2 and a 1x2 plate at z=3 join everything;
    # eight cells: z=1 is a 1x3 + 1x2, z=0 a 1x2 across the gap + a 1x1;
    # bar: a single 1x6 plate along the bar
    build = solve_checked(tiny_designs()[name], catalog, seed=seed)
    assert_one_piece(build, catalog)


def cone(radius: float, height: int) -> Design:
    n = int(np.ceil(2 * radius))
    x, y, z = np.meshgrid(
        np.arange(n) + 0.5, np.arange(n) + 0.5, np.arange(height) + 0.5, indexing="ij"
    )
    inside = (x - radius) ** 2 + (y - radius) ** 2 <= (radius * (1 - z / height)) ** 2
    return design_of(inside, WHITE)


@pytest.mark.parametrize(
    "radius, height, shell",
    [(7.9, 12, 0), (8.4, 13, 0), (7.5, 22, 1), (6.9, 12, 1), (5.8, 14, 2), (4.9, 13, 2)],
)
def test_cones_are_one_piece(radius, height, shell, catalog):
    # the rim of each disc sticks out one plate beyond the disc above: those cells have
    # nothing above them, and the base disc's rim nothing below either
    design = cone(radius, height)
    if shell:
        design = shapes.hollowed(design, shell)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)


# Saved designs from earlier runs that left avoidable loose parts. A12 can be one piece. The
# others cannot, for reasons that can be checked by hand: in A64 a white cell has only red
# or empty cells beside it and nothing above; A57 is three bodies that never touch in a way
# a part could join; in A54 the two large bodies meet at a single pair of cells that nothing
# else can hold on to. Their minimums were proven by the exact search described above.
SAVED_CASES = {
    "A12": (
        (9, 9, 15),
        595,
        1,
        (
            "eNqtk0EShSAMQ2/Uw2WT638FKkkRFs7vwvFpSwKlES1ARvB+NMLF7AgJJ7QK8n5pQT5VQgNnTmFE1Aw6TUxd"
            "+xCfYrGBk42iW23Edxu+FBeh/9qYzZHa3kRoH21llmM/40tTrl34374ppvC8LlAc14y7GH8te+d5JBccxSmk"
            "qq1WaG+jJS2ulOCmHhtzZSGYiUQfzDwumbLN4agLmOrjCm4j9BY4vlykMvqUzqayN3eRdVfLKJ7xB8Rjff8="
        ),
    ),
    "A54": (
        (11, 11, 10),
        496,
        2,
        (
            "eNqtk0sOACEIQ2/Uw3XD9SfxQ0FxYjLTVUMMTyqSu9AlB7PdQQ5bzWrhrEDj27nAmv1G58FoI2SaOhcOtzDT"
            "YGLQrY/B1cXZblmtHwOtQejWEVxc5KYxWUQ9p+idT7R2XNzhZrG7ftsDLdyMYRVkc5rK9OT0HjebuDnkBEMG"
            "dRpxm963uPwpceuqX6GiuDNRM3zQmvTC9evgF2UYsh1vjN/0AOpDYr4="
        ),
    ),
    "A57": (
        (8, 8, 12),
        395,
        3,
        (
            "eNqdklEOwCAMQm/E4frD9besarGpuo0vTPShVMBuASAJFzm8Pd4+Kp0YWCASxLLt+MkPqtjImvyaCU7Eig+x"
            "exWc3mvvlpyWftMzmRoBASkz8WWwJbKcS7zc244s98zSz5PmW3lpVlqWxtu/O/D5gr/NugDXDPYD"
        ),
    ),
    "A64": (
        (15, 15, 7),
        639,
        2,
        (
            "eNq1k0EShDAIBH/E4+Yy31cDRNCo0WX7EIxGOlAFSVnhhoVO+wBIA7bTTxraDusJbIjoKrqK/WlB04nlTR60"
            "F0D3eWoPcBHsWDZoZsd2DIUNRAfDQMRz6jvI8MheaZAHQwzPqZEgvUf3RNFkDRjBZ/Q2mO7VD6KX4JJKy+7q"
            "4dK7z4p8Bnm03CZHg91H6kiiWFG41d9E7iNshAsLO01/GrXKFo7tMFF5YWNfauQEC/sPyxg="
        ),
    ),
}


@pytest.mark.parametrize(
    "name, seed",
    # A54 runs repair to the end of its budget (its minimum is above the lower bound
    # repair aims for), so it is checked on fewer seeds to keep this file quick
    [(n, s) for n in SAVED_CASES for s in ((0, 2) if n == "A54" else (0, 1, 2, 3))],
)
def test_saved_cases_reach_their_proven_minimum(name, seed, catalog):
    shape, cells, minimum, packed = SAVED_CASES[name]
    design = decode_design(shape, packed)
    assert int(design.filled.sum()) == cells and {4, 15} <= set(np.unique(design.colors))
    build = solve_checked(design, catalog, seed=seed)
    got = pieces(build, catalog)
    assert len(got) == minimum, f"{len(got)} pieces, {minimum} is possible (sizes {got[:8]})"


def random_blob(seed: int) -> Design:
    """A small random lump; odd seeds have two colours in random patches."""
    rng = np.random.default_rng(seed)
    shape = (int(rng.integers(4, 9)), int(rng.integers(4, 9)), int(rng.integers(3, 10)))
    noise = ndimage.gaussian_filter(rng.random(shape), sigma=(1.2, 1.2, 1.8))
    filled = noise > np.quantile(noise, 1 - rng.uniform(0.35, 0.6))
    colours = np.full(shape, WHITE, dtype=np.int16)
    if seed % 2:
        tint = ndimage.gaussian_filter(rng.random(shape), sigma=2.0)
        colours[tint > np.median(tint)] = RED
    return Design(colors=np.where(filled, colours, EMPTY).astype(np.int16))


def random_shell(seed: int) -> Design:
    """The one-cell-thick skin of a random lump: thin walls, floors and overhangs."""
    rng = np.random.default_rng([seed, 7])
    shape = (int(rng.integers(6, 11)), int(rng.integers(6, 11)), int(rng.integers(6, 13)))
    noise = ndimage.gaussian_filter(rng.random(shape), sigma=(1.8, 1.8, 2.7))
    lump = noise > np.quantile(noise, 1 - rng.uniform(0.5, 0.75))
    skin = lump & ~ndimage.binary_erosion(lump, structure=np.ones((3, 3, 3)), border_value=0)
    return design_of(skin, WHITE)


# seeds for which the exact search showed that the lower bound below can be reached
BLOB_SEEDS = [2, 4, 7, 9, 11, 13, 15, 17, 21, 23, 25, 27, 28, 29, 35, 41, 42, 43]
SHELL_SEEDS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 58]


@pytest.mark.parametrize(
    "make, seed",
    [(random_blob, s) for s in BLOB_SEEDS] + [(random_shell, s) for s in SHELL_SEEDS],
    ids=[f"blob{s}" for s in BLOB_SEEDS] + [f"shell{s}" for s in SHELL_SEEDS],
)
def test_random_shapes_reach_the_lower_bound(make, seed, catalog):
    design = make(seed)
    build = solve_checked(design, catalog)
    bound = lower_bound(design.colors)
    got = pieces(build, catalog)
    assert len(got) == bound, f"{len(got)} pieces where {bound} is possible (sizes {got[:8]})"


def test_lower_bound_helper():
    # the helper above is the yardstick for several tests, so check it on known answers
    assert lower_bound(shapes.box(3, 3, 1).colors) == 1
    split = shapes.box(8, 6, 3)
    split.colors[:4] = RED
    split.colors[4:] = WHITE
    assert lower_bound(split.colors) == 2  # two colours meeting on one vertical plane
    apart = np.full((5, 1, 1), EMPTY, dtype=np.int16)
    apart[[0, 2, 4], 0, 0] = WHITE
    assert lower_bound(apart) == 3
    assert lower_bound(wall_with_shelf(3, 4).colors) == 1


# ---- quality ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dims",
    [
        (6, 4, 4),
        (12, 12, 4),
        (20, 20, 20),
        (10, 6, 3),
        # odd sides leave one-stud strips that used to fill up with 1x1s and 1x2s
        (7, 7, 2),
        (7, 7, 4),
        (7, 7, 6),
        (6, 7, 2),
        (8, 9, 2),
        (9, 9, 2),
        (9, 9, 4),
        (9, 9, 6),
        (11, 12, 2),
        (9, 17, 6),
    ],
)
def test_solid_box_uses_mostly_big_bricks(dims, catalog):
    build = solve_checked(shapes.box(*dims), catalog)
    small = sum(1 for p in build.parts if catalog.parts[p.part].sx * catalog.parts[p.part].sz <= 2)
    assert small <= len(build.parts) / 3, f"{small} of {len(build.parts)} are 1x1 or 1x2"
    assert all(catalog.parts[p.part].kind == "brick" for p in build.parts)


@pytest.mark.parametrize("dims", [(12, 12, 4), (10, 6, 3), (20, 20, 6), (20, 20, 20)])
def test_solid_box_joints_are_staggered(dims, catalog):
    """No brick sits exactly on a brick of the same footprint (that would start a tower),
    and nearly every brick above the first course bridges two or more bricks below."""
    build = solve_checked(shapes.box(*dims), catalog)
    occ = occupancy(build, catalog)[0]
    upper = bridging = 0
    for p in build.parts:
        if p.z == 0:
            continue
        upper += 1
        w, d, _ = catalog.footprint(p)
        below = np.unique(occ[p.x : p.x + w, p.y : p.y + d, p.z - 1])
        if len(below) >= 2:
            bridging += 1
            continue
        q = build.parts[int(below[0])]
        assert (q.x, q.y, catalog.footprint(q)[:2]) != (p.x, p.y, (w, d)), f"{p} is a tower"
    assert bridging >= 0.9 * upper, f"only {bridging} of {upper} bricks bridge a joint"


# ---- steps ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: shapes.box(12, 12, 4),
        lambda: shapes.sphere(16),
        lambda: shapes.striped(shapes.cylinder(12, 8), band_plates=4),
    ],
    ids=["box", "sphere", "striped"],
)
def test_steps(make, catalog):
    build = solve_checked(make(), catalog)
    by_step: dict[int, list] = defaultdict(list)
    for p in build.parts:
        by_step[p.step].append(p)
    assert sorted(by_step) == list(range(1, len(by_step) + 1)), "steps are numbered 1, 2, 3..."
    for step, parts in by_step.items():
        assert len(parts) <= 8, f"step {step} has {len(parts)} parts"
        heights = {(p.z, catalog.parts[p.part].kind) for p in parts}
        assert len(heights) == 1, f"step {step} mixes heights {heights}"
    # bottom first: a part never comes in an earlier step than a part lower down
    order = sorted(build.parts, key=lambda p: p.step)
    zs = [p.z for p in order]
    assert zs == sorted(zs)
    assert [p.step for p in build.parts] == sorted(p.step for p in build.parts)


def test_parts_in_a_step_touch(catalog):
    build = solve_checked(shapes.box(20, 20, 4), catalog)
    by_step: dict[int, list] = defaultdict(list)
    for p in build.parts:
        by_step[p.step].append(p)
    for step, parts in by_step.items():
        grid = np.full((20, 20), -1)
        for i, p in enumerate(parts):
            w, d, _ = catalog.footprint(p)
            grid[p.x : p.x + w, p.y : p.y + d] = i
        g = nx.Graph()
        g.add_nodes_from(range(len(parts)))
        for lo, hi in ((grid[:-1], grid[1:]), (grid[:, :-1], grid[:, 1:])):
            hit = (lo >= 0) & (hi >= 0) & (lo != hi)
            g.add_edges_from(zip(lo[hit].tolist(), hi[hit].tolist(), strict=True))
        assert nx.is_connected(g), f"step {step} has parts that do not touch"


@pytest.mark.parametrize(
    "make",
    [lambda: shapes.hollowed(shapes.sphere(24)), lambda: shapes.sphere(16), lambda: cone(7.9, 12)],
    ids=["hollow-sphere-24", "sphere-16", "cone"],
)
def test_curved_shapes_do_not_get_one_part_per_step(make, catalog):
    """On curves many plates stand alone among bricks; they still share steps with nearby
    parts of the same height instead of each getting a step of its own."""
    build = solve_checked(make(), catalog)
    by_step: dict[int, list] = defaultdict(list)
    for p in build.parts:
        by_step[p.step].append(p)
    height = Counter((p.z, catalog.parts[p.part].kind) for p in build.parts)
    # a single part is fine when it is the only part of its height and kind
    singles = sum(
        1
        for parts in by_step.values()
        if len(parts) == 1 and height[(parts[0].z, catalog.parts[parts[0].part].kind)] > 1
    )
    # fewest steps possible with one height and at most 8 parts per step; the spheres used
    # to take more than three times as many, with four steps in five holding one part
    fewest = sum(-(-n // 8) for n in height.values())
    assert len(by_step) <= 1.25 * fewest, f"{len(by_step)} steps where {fewest} would do"
    assert singles <= 0.2 * len(by_step), f"{singles} of {len(by_step)} steps hold a lone part"
    for parts in by_step.values():
        assert len({(p.z, catalog.parts[p.part].kind) for p in parts}) == 1
        assert len(parts) <= 8


# ---- determinism and speed --------------------------------------------------------------------


def test_deterministic_for_a_seed(catalog):
    design = shapes.hollowed(shapes.sphere(16))
    assert solve(design, catalog, seed=3).parts == solve(design, catalog, seed=3).parts
    assert solve(design, catalog).parts == solve(design, catalog, seed=0).parts


@pytest.mark.parametrize("seed", [1, 2, 7])
def test_other_seeds_are_valid_too(seed, catalog):
    design = shapes.hollowed(shapes.cylinder(12, 10))
    build = solve_checked(design, catalog, seed=seed)
    assert_one_piece(build, catalog)


def test_negative_seed_is_accepted(catalog):
    design = shapes.hollowed(shapes.cylinder(8, 4))
    build = solve_checked(design, catalog, seed=-1)
    assert build.parts == solve(design, catalog, seed=-1).parts
    assert_one_piece(build, catalog)


def test_does_not_change_the_design(catalog):
    design = shapes.striped(shapes.sphere(8))
    before = design.colors.copy()
    solve(design, catalog)
    assert np.array_equal(design.colors, before)


def test_speed_solid_20_box(catalog):
    design = shapes.box(20, 20, 20)  # 24,000 cells
    start = time.perf_counter()
    build = solve(design, catalog)
    elapsed = time.perf_counter() - start
    assert elapsed < 5, f"solving 24,000 cells took {elapsed:.1f} s"
    assert_one_piece(build, catalog)


def test_speed_large_model(catalog):
    design = shapes.box(34, 25, 14)  # 35,700 cells
    start = time.perf_counter()
    build = solve(design, catalog)
    elapsed = time.perf_counter() - start
    assert elapsed < 20, f"solving {int(design.filled.sum())} cells took {elapsed:.1f} s"
    assert_one_piece(build, catalog)


def test_speed_sixteen_stud_sphere(catalog):
    design = shapes.hollowed(shapes.sphere(16))
    start = time.perf_counter()
    solve(design, catalog)
    assert time.perf_counter() - start < 1.5


def test_big_model_with_a_shelf_too_deep_to_hold_ends_in_time(catalog):
    """A shelf one plate thick and 10 studs deep: a plate reaching back into the wall can
    hold at most 7 studs of it, so the far 3 can never join. Repair keeps trying until its
    budget runs out, which must stay well inside the time allowed for a model this size."""
    colors = np.full((30, 16, 24), EMPTY, dtype=np.int16)
    colors[:20] = DEFAULT_COLOUR
    colors[20:, :, 12] = DEFAULT_COLOUR
    design = Design(colors=colors)
    start = time.perf_counter()
    build = solve_checked(design, catalog)
    assert time.perf_counter() - start < 10
    g = connection_graph(build, catalog)
    main: set[int] = max(nx.connected_components(g), key=len)
    for i in set(g.nodes) - main:  # every loose part reaches the far end of the shelf
        p = build.parts[i]
        assert p.x + catalog.footprint(p)[0] - 1 >= 27, f"{p} could have been held"


def test_hopeless_design_ends_quickly(catalog):
    # every part is its own piece and no repair can help: the solver must give up in time
    design = design_of(np.ones((40, 40, 1), dtype=bool))
    start = time.perf_counter()
    build = solve_checked(design, catalog)
    assert time.perf_counter() - start < 10
    assert len(build.parts) >= 25


# ---- sturdiness -------------------------------------------------------------------------------


def checks_weak_spots(build: Build, catalog) -> tuple[int, int]:
    """(weak spots, largest load) exactly as bricksnap.checks finds them."""
    from bricksnap.checks import _find_spots, check

    report = check(build, catalog)
    heading = [ln for ln in report.text.splitlines() if "weak spot" in ln and "strengthen" in ln]
    count = int(heading[0].split()[0]) if heading else 0
    occ = occupancy(build, catalog)[0]
    g = connection_graph(build, catalog, occ)
    biggest: set[int] = max(nx.connected_components(g), key=len)
    main = sorted(biggest)
    anchors = {i for i in main if build.parts[i].z == 0}
    largest = max(
        (s.at_stake for s in _find_spots(build, catalog, occ, g, main, anchors)), default=0
    )
    return count, largest


def head_and_body() -> Design:
    """A body standing on the ground and a head as big as its upper half stuck to its side.

    They share a face six studs wide and four bricks tall; the head stands on nothing else.
    """
    filled = np.zeros((12, 6, 24), dtype=bool)
    filled[:6, :, :] = True  # the body, 6 x 6 studs, 8 bricks tall
    filled[6:, :, 12:] = True  # the head, 6 x 6 studs, 4 bricks tall, beside the body's top
    return design_of(filled)


def crossing_levels(build: Build, catalog, plane_x: int, levels: range) -> int:
    """Plate levels in which some part reaches across the plane between x-1 and x."""
    crossed = set()
    for p in build.parts:
        w, _, h = catalog.footprint(p)
        if p.x < plane_x < p.x + w:
            crossed.update(z for z in range(p.z, p.z + h) if z in levels)
    return len(crossed)


@pytest.mark.parametrize("seed", list(range(0, 40)))
def test_lone_links_agree_with_the_checks(seed, catalog):
    from bricksnap.layout import lone_links, sturdiness

    design = random_blob(seed) if seed % 4 else random_shell(seed)
    build = solve(design, catalog, sturdy=False)
    count, largest = checks_weak_spots(build, catalog)
    links = lone_links(build, catalog)
    assert len(links) == count
    assert max((ln.load for ln in links), default=0) == largest
    assert sturdiness(build, catalog)[:2] == (largest, count)


def test_lone_links_agree_with_the_checks_on_a_finished_build(catalog):
    # tiles, slopes and detail parts too: the analysis goes through bricksnap.connect
    from bricksnap.layout import lone_links

    build = Build.load(
        __import__("pathlib").Path(__file__).parent.parent
        / "samples"
        / "projects"
        / "cat-designed"
        / "build.json"
    )
    count, largest = checks_weak_spots(build, catalog)
    links = lone_links(build, catalog)
    assert (len(links), max(ln.load for ln in links)) == (count, largest)
    assert links == sorted(links, key=lambda ln: -ln.load)


def test_lone_links_of_a_plain_column(catalog):
    # five 1x1 bricks stacked, each joined to the next by one stud: the joint over the
    # bottom brick carries four, the next one three; the parts carry the same groups as the
    # joints, so the joints stand for them, and smaller groups are not weak spots
    from bricksnap.layout import lone_links, sturdiness

    build = solve(design_of(np.ones((1, 1, 15), dtype=bool)), catalog)
    links = lone_links(build, catalog)
    assert [(ln.load, ln.joint is not None) for ln in links] == [(4, True), (3, True)]
    assert sturdiness(build, catalog) == (4, 2, 7)
    assert checks_weak_spots(build, catalog) == (2, 4)


def test_head_against_a_body_is_tied_in_many_layers(catalog):
    # The shape the contract names. The solver already met this before the sturdiness work
    # (its build here is unchanged), so this is a guard against losing it, not a test of the
    # sturdiness step; the shapes below are the ones the step and the seam rule change.
    from bricksnap.layout import sturdiness

    design = head_and_body()
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)
    levels = range(12, 24)
    crossed = crossing_levels(build, catalog, 6, levels)
    assert crossed >= len(levels) / 2, f"the shared face is crossed in {crossed} of 12 levels"
    head = sum(1 for p in build.parts if p.x >= 6)
    largest = sturdiness(build, catalog)[0]
    assert largest <= head / 4, f"{largest} parts hang on one link; the head has {head} parts"


def uncrossed_neighbours(build: Build, catalog, plane_x: int, courses: range) -> int:
    """Pairs of neighbouring brick courses in which no part reaches across the plane."""
    levels = set()
    for p in build.parts:
        w, _, h = catalog.footprint(p)
        if p.x < plane_x < p.x + w:
            levels.update(range(p.z, p.z + h))
    crossed = [any(z in levels for z in range(3 * k, 3 * k + 3)) for k in courses]
    return sum(1 for a, b in zip(crossed, crossed[1:], strict=False) if not a and not b)


def test_a_head_wider_than_the_body(catalog):
    # like the sample cat's head: wider than the body it is stuck to, so the parts of the
    # head beside the shared face would rather run along it than across it. The solver used
    # to hang the whole head on one part.
    from bricksnap.layout import sturdiness

    filled = np.zeros((9, 6, 21), dtype=bool)
    filled[:6, 1:5, :] = True  # the body, 6 x 4 studs, 7 bricks tall
    filled[6:, :, 12:] = True  # the head, 3 x 6 studs, its top three bricks beside the body
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)
    assert uncrossed_neighbours(build, catalog, 6, range(4, 7)) == 0
    head = sum(1 for p in build.parts if p.x >= 6)
    largest = sturdiness(build, catalog)[0]
    assert largest <= head / 4, f"{largest} parts hang on one link; the head has {head} parts"


def test_a_tower_on_a_wide_base(catalog):
    from bricksnap.layout import sturdiness

    filled = np.zeros((10, 10, 24), dtype=bool)
    filled[:, :, :6] = True  # a base two bricks thick
    filled[3:7, 3:7, 6:] = True  # a 4 x 4 tower six bricks tall on it
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)
    plain = solve(design_of(filled), catalog, sturdy=False)
    tower = sum(1 for p in build.parts if p.z >= 6)
    largest = sturdiness(build, catalog)[0]
    assert largest <= sturdiness(plain, catalog)[0]
    assert largest < 3, f"{largest} of the tower's {tower} parts hang on one part"


def test_a_t_shape(catalog):
    # a stem with a bar across its top: each arm of the bar hangs off the stem
    from bricksnap.layout import sturdiness

    filled = np.zeros((12, 4, 24), dtype=bool)
    filled[4:8, :, :18] = True
    filled[:, :, 18:] = True
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)
    levels = range(18, 24)
    for plane in (4, 8):
        assert crossing_levels(build, catalog, plane, levels) >= len(levels) / 2
    assert sturdiness(build, catalog)[0] < 3


def head_off_centre() -> np.ndarray:
    """A body 8 x 4 studs, 8 bricks tall, and a small head 7 x 4 studs, 3 bricks tall, stuck
    to its side one stud off-centre, standing on nothing else. The body's 8-stud width suits
    2 x 8 bricks that end exactly at the shared face, so the face tends to stay uncrossed."""
    filled = np.zeros((15, 5, 24), dtype=bool)
    filled[:8, 0:4, :] = True
    filled[8:, 1:5, 9:18] = True
    return filled


def test_a_small_head_gets_a_second_connection(catalog):
    # a build of about 34 parts: the step must be allowed to add a part or two even though
    # 2 in 100 of 34 rounds down to none (it used to leave the whole head on one 2 x 8)
    from bricksnap.layout import sturdiness

    design = design_of(head_off_centre())
    plain = solve(design, catalog, sturdy=False)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)
    head = sum(1 for p in build.parts if p.x >= 8)
    before, after = sturdiness(plain, catalog)[0], sturdiness(build, catalog)[0]
    assert before > head / 4  # without the step the head hangs on one part
    assert after <= head / 4, f"{after} parts hang on one link; the head has {head} parts"
    assert uncrossed_neighbours(build, catalog, 8, range(3, 6)) == 0


def head_variant(bw: int, bd: int, hd: int, hw: int, off: int, hb: int, z0: int) -> np.ndarray:
    """A body ``bw`` x ``bd`` studs and 8 bricks tall; beside it (from x = bw) a head ``hd``
    deep and ``hw`` wide, centred on the body or ``off`` studs off, ``hb`` bricks tall,
    starting at plate level ``z0`` (a multiple of 3), standing on nothing else."""
    top = z0 + 3 * hb
    ny = max(bd, hw) + 1
    filled = np.zeros((bw + hd, ny, max(24, top)), dtype=bool)
    by = (ny - bd) // 2
    filled[:bw, by : by + bd, :24] = True
    hy = (ny - hw) // 2 + off
    filled[bw:, max(0, hy) : hy + hw, z0:top] = True
    return filled


HEAD_VARIANTS = [
    # narrow and off-centre heads on a body whose width suits parts that end at the face
    (8, 4, 2, 4, 1, 3, 9),
    (8, 4, 7, 4, 1, 3, 9),
    (8, 6, 2, 4, 0, 4, 12),
    (8, 6, 4, 6, 1, 4, 9),
    (8, 6, 7, 4, 1, 4, 9),
    (8, 6, 6, 4, 0, 3, 15),
    (8, 6, 3, 8, 0, 3, 9),
    (8, 6, 2, 8, 0, 4, 9),
    (6, 4, 3, 4, 1, 3, 12),
    (6, 6, 2, 6, 0, 4, 9),
    (4, 6, 3, 4, 1, 2, 9),
    (4, 4, 6, 8, 0, 4, 12),
]


@pytest.mark.parametrize("variant", HEAD_VARIANTS)
def test_heads_against_bodies_are_crossed_every_second_course(variant, catalog):
    # the contract's seam rule: parts cross a face shared through several layers in at least
    # every second layer wherever the cells allow (a 1 x 2 brick across always fits here)
    filled = head_variant(*variant)
    build = solve_checked(design_of(filled), catalog)
    assert_one_piece(build, catalog)
    bw, z0, top = variant[0], variant[6], min(24, variant[6] + 3 * variant[5])
    gaps = uncrossed_neighbours(build, catalog, bw, range(z0 // 3, top // 3))
    assert gaps == 0, f"{gaps} pairs of neighbouring courses have no part across the face"


def test_small_builds_get_enough_work_for_sturdiness(catalog):
    # a lump of 150 cells and about 45 parts: the work allowed is a share of the work done
    # before, which for a build this small is a handful of trials. A floor lets the step
    # reach the heavy links (it used to stop with 21 parts on one link, where 5 is possible).
    from bricksnap.layout import sturdiness

    design = random_blob(2146)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)
    assert sturdiness(build, catalog)[0] <= 5


@pytest.mark.parametrize(("seed", "most"), [(4020, 0), (4236, 4)])
def test_thin_shells_get_enough_work_to_be_tied(seed, most, catalog, monkeypatch):
    # one-cell-thick shells (the hat's brim, the pineapple's skin): every layer is a thin
    # ring, so a tie takes several re-tilings. With work for about three quarters of the
    # solve and as many re-tilings as before the step (the old allowance) these kept 10 and
    # 23 parts on one link; the step now has the work to tie them
    import bricksnap.layout as layout_module
    from bricksnap.layout import sturdiness

    design = random_shell(seed)
    build = solve_checked(design, catalog)
    assert_one_piece(build, catalog)
    assert sturdiness(build, catalog)[0] <= most
    monkeypatch.setattr(layout_module, "STURDY_SHARE", 0.75)
    monkeypatch.setattr(layout_module, "STURDY_TILE_SHARE", 1.0)
    assert sturdiness(solve(design, catalog), catalog)[0] >= 10


def test_lone_links_get_parts_of_their_own_after_the_faces(catalog, monkeypatch):
    # the faces are crossed first and may use all the parts the step may add; the lone links
    # then get as many again, or they could only be given changes that add no part (this
    # shell kept 6 parts on one link that way; the sample pineapple and duck did the same)
    import bricksnap.layout as layout_module
    from bricksnap.layout import sturdiness

    design = random_shell(3225)
    plain = solve(design, catalog, sturdy=False)
    build = solve_checked(design, catalog)
    assert sturdiness(build, catalog) == (0, 0, 0)
    n = len(plain.parts)
    assert len(build.parts) <= n + 2 * max(3, int(0.02 * n))
    cross = layout_module._Solver._cross_faces
    used: list[int] = []

    def counted(self, score, max_parts):
        before = sum(p is not None for p in self.parts)
        cross(self, score, max_parts)
        used.append(sum(p is not None for p in self.parts) - before)

    monkeypatch.setattr(layout_module._Solver, "_cross_faces", counted)
    solve(design, catalog)
    assert used and used[0] > 0  # the faces did use parts here


@pytest.mark.thorough
def test_the_sturdiness_step_at_most_quadruples_the_time_on_spikes(catalog):
    # the contract's promise, on the kind of shape that costs the step most: a field of thin
    # spikes 24 studs square, about 1,400 parts, hundreds of weak spots with places to try.
    # Measured 3.2 times (1.69 s against 0.53); taken alternately, the best of three each, so
    # a busy machine slows both alike
    rng = np.random.default_rng(8)
    heights = np.full((24, 24), 6)
    pick = rng.random((24, 24)) < 0.5
    heights[pick] = rng.integers(12, 40, size=int(pick.sum()))
    design = design_of(np.arange(40)[None, None, :] < heights[:, :, None])
    with_step, without = [], []
    for _ in range(3):
        start = time.perf_counter()
        solve(design, catalog, sturdy=False)
        without.append(time.perf_counter() - start)
        start = time.perf_counter()
        solve(design, catalog)
        with_step.append(time.perf_counter() - start)
    ratio = min(with_step) / min(without)
    assert ratio <= 4.0, f"{min(with_step):.2f} s against {min(without):.2f} s"


@pytest.mark.thorough
def test_sturdiness_never_makes_random_blobs_worse(catalog):
    from bricksnap.layout import sturdiness

    better = 0
    for seed in range(100):
        design = random_blob(1000 + seed) if seed % 3 else random_shell(1000 + seed)
        plain = solve(design, catalog, sturdy=False)
        build = solve_checked(design, catalog)
        assert len(pieces(build, catalog)) <= len(pieces(plain, catalog)), f"seed {seed}"
        got, before = sturdiness(build, catalog), sturdiness(plain, catalog)
        assert got[0] <= before[0], f"seed {seed}: largest load {before[0]} -> {got[0]}"
        assert got <= before, f"seed {seed}: {before} -> {got}"
        # crossing faces may add at most 2 parts in 100 to what there was (at least 3 parts),
        # and the lone links as many again
        n = len(plain.parts)
        assert len(build.parts) <= n + 2 * max(3, int(0.02 * n)), f"seed {seed}"
        better += got < before
    assert better >= 10, f"only {better} of 100 blobs got sturdier"


def test_sturdy_builds_still_number_their_steps(catalog):
    # on a build the sturdiness step really changes, so the steps are numbered after it
    design = design_of(head_off_centre())
    build = solve_checked(design, catalog)
    plain = solve(design, catalog, sturdy=False)
    where = lambda b: sorted((p.part, p.x, p.y, p.z, p.rot) for p in b.parts)  # noqa: E731
    assert where(build) != where(plain)
    steps = [p.step for p in build.parts]
    assert steps == sorted(steps) and sorted(set(steps)) == list(range(1, max(steps) + 1))
    by_step: dict[int, list] = defaultdict(list)
    for p in build.parts:
        by_step[p.step].append(p)
    for parts in by_step.values():
        assert len(parts) <= 8
        assert len({(p.z, catalog.parts[p.part].kind) for p in parts}) == 1
    order = sorted(build.parts, key=lambda p: p.step)
    assert [p.z for p in order] == sorted(p.z for p in order)


# ---- stage 4: pinned side-stud bricks ------------------------------------------------------


def _pinned_cases(catalog):
    solid = design_of(np.ones((6, 5, 9), dtype=bool))
    wall = design_of(np.ones((10, 1, 6), dtype=bool))  # one stud thick, two courses tall
    return [
        (solid, [catalog.side_stud_brick("front", DEFAULT_COLOUR, 2, 0, 3)]),
        (
            solid,
            [
                catalog.side_stud_brick("left", DEFAULT_COLOUR, 0, 2, 6),
                catalog.side_stud_brick("right", DEFAULT_COLOUR, 5, 2, 6),
                catalog.side_stud_brick("back", DEFAULT_COLOUR, 3, 4, 0),
            ],
        ),
        (wall, [catalog.side_stud_brick("front", DEFAULT_COLOUR, 4, 0, 3)]),
    ]


def test_pinned_bricks_are_placed_exactly_and_the_rest_is_tiled_around_them(catalog):
    for design, pins in _pinned_cases(catalog):
        build = solve(design, catalog, pinned=pins)
        got = [p for p in build.parts if p.part == "87087"]
        assert sorted((p.x, p.y, p.z, p.rot, p.color) for p in got) == sorted(
            (p.x, p.y, p.z, p.rot, p.color) for p in pins
        )
        assert all(p.step >= 1 for p in build.parts)
        occ, collisions, out_of_bounds, unknown = occupancy(build, catalog)
        assert not collisions and not out_of_bounds and not unknown
        assert np.array_equal(occ >= 0, design.filled)
        for p in build.parts:
            if p.part != "87087":
                assert catalog.parts[p.part].kind in ("brick", "plate")
        assert_one_piece(build, catalog)


def test_nothing_pinned_gives_the_same_build(catalog):
    design = design_of(np.ones((7, 5, 10), dtype=bool))
    a = solve(design, catalog)
    b = solve(design, catalog, pinned=())
    assert a.parts == b.parts


def test_a_pinned_brick_is_held_like_a_one_by_one_brick(catalog):
    # a single column: the pin in the middle course holds the courses above and below
    design = design_of(np.ones((1, 1, 9), dtype=bool))
    pin = catalog.side_stud_brick("front", DEFAULT_COLOUR, 0, 0, 3)
    build = solve(design, catalog, pinned=[pin])
    assert pin.part in [p.part for p in build.parts]
    assert_one_piece(build, catalog)


def test_a_pin_the_solver_cannot_place_is_refused_in_words(catalog):
    design = design_of(np.ones((4, 4, 6), dtype=bool))
    bad = [
        catalog.side_stud_brick("front", DEFAULT_COLOUR, 1, 0, 1),  # not in a course
        catalog.side_stud_brick("front", 4, 1, 0, 0),  # cells of another colour
        catalog.side_stud_brick("front", DEFAULT_COLOUR, 1, 0, 6),  # outside the grid
    ]
    for pin in bad:
        with pytest.raises(ValueError, match="pinned 87087"):
            solve(design, catalog, pinned=[pin])
    pin = catalog.side_stud_brick("front", DEFAULT_COLOUR, 1, 0, 0)
    with pytest.raises(ValueError, match="pinned twice"):
        solve(design, catalog, pinned=[pin, pin])


def _some_pins(design: Design, catalog, rng, most: int = 4):
    """Up to ``most`` side-stud bricks where one could go: a course of one colour the brick
    is made in, with the model going on above or below it."""
    from bricksnap.types import FACE_OUT

    c = design.colors
    nx, ny, nz = c.shape
    spots = []
    for x in range(nx):
        for y in range(ny):
            for z in range(0, nz - 2, 3):
                col = c[x, y, z : z + 3]
                if (
                    col[0] == EMPTY
                    or (col != col[0]).any()
                    or not catalog.side_stud_exists(int(col[0]))
                ):
                    continue
                if (z > 0 and c[x, y, z - 1] != EMPTY) or (z + 3 < nz and c[x, y, z + 3] != EMPTY):
                    spots.append((x, y, z))
    rng.shuffle(spots)
    pins, used = [], set()
    for x, y, z in spots:
        if len(pins) == most:
            break
        if any((x, y, zz) in used for zz in (z - 3, z + 3)):
            continue  # not stacked: a stack could be held by nothing
        used.add((x, y, z))
        face = list(FACE_OUT)[len(pins) % 4]
        pins.append(catalog.side_stud_brick(face, int(c[x, y, z]), x, y, z))
    return pins


def test_repair_and_sturdiness_never_move_a_pinned_brick(catalog):
    """Pins in random lumps and shells, where repair and the sturdiness step have work to do
    around them: every pin stays exactly where it was put, and nothing else changes kind."""
    rng = np.random.default_rng(5)
    tried = 0
    for seed in range(20):
        design = random_blob(seed) if seed % 2 else random_shell(seed)
        pins = _some_pins(design, catalog, rng)
        if not pins:
            continue
        tried += 1
        build = solve(design, catalog, seed=seed, pinned=pins)
        got = sorted((p.x, p.y, p.z, p.rot, p.color) for p in build.parts if p.part == "87087")
        assert got == sorted((p.x, p.y, p.z, p.rot, p.color) for p in pins), seed
        occ, collisions, out_of_bounds, _ = occupancy(build, catalog)
        assert not collisions and not out_of_bounds
        assert np.array_equal(occ >= 0, design.filled), seed
    assert tried >= 15


def test_a_pinned_cell_stays_a_brick_cell_where_slabs_turn_into_plates(catalog):
    from bricksnap.layout import _Solver

    slab = design_of(np.ones((8, 6, 3), dtype=bool))  # one course thick: plates
    pin = catalog.side_stud_brick("front", DEFAULT_COLOUR, 3, 0, 0)
    plain = _Solver(slab, catalog, 0)
    assert not plain.brick[3, 0, 0]
    assert _Solver(slab, catalog, 0, (pin,)).brick[3, 0, 0]
