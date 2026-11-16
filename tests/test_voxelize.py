"""Tests for bricksnap.voxelize.voxelize: grid, filling, colour, hollowing, speed."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
import shapes
import trimesh
import trimesh.visual

from bricksnap.seed import load_seed
from bricksnap.types import (
    CELL_MM,
    DEFAULT_COLOUR,
    EMPTY,
    FINISH_SLOPED,
    FINISH_STUDS,
    Design,
    Seed,
    SeedError,
)
from bricksnap.voxelize import _snap, voxelize

CELL = np.asarray(CELL_MM)


def concat(*meshes: trimesh.Trimesh) -> trimesh.Trimesh:
    joined = trimesh.util.concatenate(list(meshes))
    assert isinstance(joined, trimesh.Trimesh)
    return joined


def seed_from(mesh: trimesh.Trimesh, face_colors=None) -> Seed:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    vertices = vertices - vertices.min(axis=0)
    return Seed(vertices=vertices, faces=np.asarray(mesh.faces), face_colors=face_colors)


def box_seed(size_mm, origin=(0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=size_mm)
    mesh.apply_translation(np.asarray(size_mm) / 2 + np.asarray(origin))
    return mesh


def body(design: Design) -> np.ndarray:
    """The filled array cut down to the cells the seed occupies (without the padding)."""
    ox, oy, oz = design.seed_offset
    f = design.filled
    return f[ox : f.shape[0] - ox, oy : f.shape[1] - oy, : f.shape[2] - 3 * ox]


def quad(a, b, c, d) -> list[list]:
    return [[a, b, c], [a, c, d]]


def surface_cells_reference(tris_cells: np.ndarray, shape, density: int = 40) -> set:
    """Cells hit by very dense point samples: a subset of the cells the surface passes through."""
    found = set()
    lengths = np.linalg.norm(np.roll(tris_cells, -1, axis=1) - tris_cells, axis=2).max(axis=1)
    n = np.floor(density * lengths).astype(int) + 1
    for k in np.unique(n):
        s, t = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
        keep = s + t <= k
        u, v = s[keep] / k, t[keep] / k
        weights = np.stack([1 - u - v, u, v], axis=1)
        points = np.einsum("kj,mjd->mkd", weights, tris_cells[n == k]).reshape(-1, 3)
        cells = np.clip(np.floor(points + 1e-6).astype(int), 0, np.asarray(shape) - 1)
        found |= set(map(tuple, np.unique(cells, axis=0).tolist()))
    return found


# ---- grid -----------------------------------------------------------------------------------


def test_exact_multiples_do_not_gain_a_cell(catalog):
    design = voxelize(seed_from(box_seed((64.0, 40.0, 32.0))), catalog)
    assert design.shape == (8 + 4, 5 + 4, 10 + 6)
    assert design.seed_offset == (2, 2, 0)
    assert body(design).shape == (8, 5, 10)
    assert body(design).all()
    assert design.filled.sum() == 8 * 5 * 10


def test_rounding_noise_does_not_gain_a_cell(catalog):
    mesh = box_seed((64.0, 40.0, 32.0))
    seed = seed_from(mesh)
    seed.vertices = seed.vertices * (1 + 1e-12)  # 64.000000000064 mm
    design = voxelize(seed, catalog)
    assert body(design).shape == (8, 5, 10) and body(design).all()
    seed.vertices = seed_from(mesh).vertices * (1 - 1e-12)  # a hair under the boundary
    design = voxelize(seed, catalog)
    assert body(design).shape == (8, 5, 10) and body(design).all()


def test_partial_cells_round_up(catalog):
    design = voxelize(seed_from(box_seed((64.5, 41.0, 33.0))), catalog)
    assert body(design).shape == (9, 6, 11)
    assert body(design).all()


def test_cells_are_not_cubes(catalog):
    """A 32 mm cube is 4 studs across and 10 plates tall."""
    design = voxelize(seed_from(box_seed((32.0, 32.0, 32.0))), catalog)
    assert body(design).shape == (4, 4, 10)
    assert body(design).all()


@pytest.mark.parametrize("margin", [0, 1, 3])
def test_padding_follows_margin_studs(catalog, margin):
    design = voxelize(seed_from(box_seed((16.0, 24.0, 9.6))), catalog, margin_studs=margin)
    assert design.shape == (2 + 2 * margin, 3 + 2 * margin, 3 + 3 * margin)
    assert design.seed_offset == (margin, margin, 0)
    m = margin
    assert design.filled[m : m + 2, m : m + 3, 0:3].all()
    assert design.filled.sum() == 2 * 3 * 3  # nothing in the padding


def test_model_stands_on_z0_and_padding_is_above(catalog):
    design = voxelize(seed_from(box_seed((16.0, 16.0, 16.0))), catalog)
    assert design.filled[:, :, 0].any()
    top = np.nonzero(design.filled.any(axis=(0, 1)))[0].max()
    assert design.shape[2] - 1 - top == 6  # 3 * margin_studs empty layers on top


def test_seed_point_lands_in_its_documented_cell(catalog):
    """A point p (mm) lies in cell floor(p / CELL_MM) + seed_offset."""
    big = box_seed((80.0, 80.0, 32.0))
    small = box_seed((2.0, 2.0, 1.0), origin=(85.0, 85.0, 40.0))  # far corner, off on its own
    seed = seed_from(concat(big, small))
    design = voxelize(seed, catalog, margin_studs=3)
    p = np.array([86.0, 86.0, 40.5])
    cell = tuple(np.floor(p / CELL).astype(int) + np.array(design.seed_offset))
    assert design.filled[cell]
    island = design.filled.copy()
    island[3:13, 3:13, 0:10] = False  # remove the big box: exactly 10 x 10 x 10 cells
    assert set(zip(*np.nonzero(island), strict=True)) == {cell}
    assert design.filled[3:13, 3:13, 0:10].all()


def test_design_fields_start_empty(catalog):
    design = voxelize(seed_from(box_seed((16.0, 16.0, 16.0))), catalog)
    assert isinstance(design, Design)
    assert design.colors.dtype == np.int16
    assert design.finish is not None
    assert design.finish.dtype == np.uint8 and not design.finish.any()
    assert design.finish.shape == design.colors.shape
    assert design.details == [] and design.regions == {} and design.log == []


# ---- which cells are filled ---------------------------------------------------------------------


def test_solid_shapes_are_filled_inside(catalog):
    sphere = trimesh.creation.icosphere(3, radius=40.0)
    design = voxelize(seed_from(sphere), catalog)
    f = body(design)
    assert f.shape == (10, 10, 25)
    cx, cy, cz = (np.array(f.shape) // 2).tolist()
    assert f[cx, cy, cz] and f[:, cy, cz].sum() >= 8
    # a filled ball has no empty cell enclosed by filled cells
    from scipy import ndimage

    assert np.array_equal(ndimage.binary_fill_holes(f), f)


def test_every_cell_the_surface_passes_through_is_marked(catalog):
    for mesh in (trimesh.creation.icosphere(3, radius=50.0), trimesh.creation.torus(40.0, 12.0)):
        seed = seed_from(mesh)
        design = voxelize(seed, catalog)
        filled = body(design)
        tris = seed.vertices[seed.faces] / CELL
        reference = surface_cells_reference(tris, filled.shape)
        missed = [c for c in reference if not filled[c]]
        assert missed == []


def test_cell_clipped_only_at_its_corner_is_marked(catalog):
    """Half-cell point sampling misses this cell; the surface does pass through it."""
    a, b = (2.05, 0.0), (0.0, 2.05)  # plane x + y = 2.05 cells cuts the corner of column (1, 1)
    corners = [(a[0], a[1], 0.0), (b[0], b[1], 0.0), (b[0], b[1], 3.0), (a[0], a[1], 3.0)]
    vertices = np.array(corners) * CELL
    seed = Seed(vertices=vertices, faces=np.array([[0, 1, 2], [0, 2, 3]]))
    filled = body(voxelize(seed, catalog))
    assert filled.shape == (3, 3, 3)
    assert filled[1, 1, :].all()
    assert filled[2, 0, :].all() and filled[0, 2, :].all()
    assert not filled[0, 0, :].any() and not filled[2, 2, :].any()  # an open sheet: no fill


@pytest.mark.parametrize("facing_up", [True, False])
def test_face_on_a_cell_boundary_marks_one_layer_not_two(catalog, facing_up):
    """A sheet lying exactly on z = 3 plates goes in one layer: the one behind its front side
    (the solid side of a face is opposite its normal, as in any closed mesh)."""
    z = 3 * 3.2
    sheet = quad((0, 0, z), (16, 0, z), (16, 16, z), (0, 16, z))  # wound to face up (+z)
    if not facing_up:
        sheet = [tri[::-1] for tri in sheet]
    post = quad((0, 0, 0), (1, 0, 0), (1, 0, 19.2), (0, 0, 19.2))  # gives the model height
    tris = np.array(sheet + post, dtype=float)
    vertices = tris.reshape(-1, 3)
    seed = Seed(vertices=vertices, faces=np.arange(len(vertices)).reshape(-1, 3))
    filled = body(voxelize(seed, catalog))
    assert filled.shape == (2, 2, 6)
    layer_counts = filled.sum(axis=(0, 1)).tolist()
    sheet_layer = 2 if facing_up else 3
    assert layer_counts[sheet_layer] == 4
    assert [n for i, n in enumerate(layer_counts) if i != sheet_layer] == [1] * 5  # the post


def test_boxes_whose_sides_are_on_cell_boundaries_are_not_fattened(catalog):
    """Two 2 x 2 stud blocks side by side with a 1-stud gap: the gap stays empty."""
    a = box_seed((16.0, 16.0, 9.6))
    b = box_seed((16.0, 16.0, 9.6), origin=(24.0, 0.0, 9.6))
    filled = body(voxelize(seed_from(concat(a, b)), catalog))
    assert filled.shape == (5, 2, 6)
    assert filled[0:2, :, 0:3].all() and filled[3:5, :, 3:6].all()
    assert filled.sum() == 2 * 12


@pytest.mark.parametrize("fmt", ["stl", "glb", "ply"])
def test_blocky_model_stored_in_float32_keeps_its_gaps(tmp_path, catalog, fmt):
    """Binary STL, GLB and PLY store single-precision coordinates, so a face meant to sit on
    a stud boundary comes back a hair off it. That must not fatten the blocks."""
    a = trimesh.creation.box(bounds=[[0.0, 0.0, 0.0], [0.3, 0.2, 0.12]])
    b = trimesh.creation.box(bounds=[[0.4, 0.0, 0.0], [0.8, 0.2, 0.12]])
    path = tmp_path / f"gap.{fmt}"
    concat(a, b).export(str(path))
    seed = load_seed(path, studs=8, up="z")
    xs = seed.vertices[:, 0] / CELL[0]
    assert not np.all(xs == np.round(xs)), "the file should carry float32 noise"
    design = voxelize(seed, catalog, margin_studs=0)
    assert design.shape == (8, 2, 3)
    columns = "".join("#" if c else "." for c in design.filled.any(axis=(1, 2)))
    assert columns == "###.####"
    assert design.filled.sum() == 7 * 2 * 3


def test_random_blocks_with_single_precision_noise_are_exact(catalog):
    """Boxes on whole stud and plate boundaries, written in float32 at 0.1 units per stud
    (as an exported file holds them): exactly their own cells are filled."""
    from scipy import ndimage

    rng = np.random.default_rng(8)
    shape = (24, 24, 30)
    expected = np.zeros(shape, dtype=bool)
    meshes = []
    for _ in range(25):
        lo = rng.integers(0, np.array(shape) - 1)
        hi = np.minimum(lo + rng.integers(1, 6, size=3), shape)
        expected[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = True
        units = np.array([0.1, 0.1, 0.04])  # one stud is 0.1 units, one plate 0.04
        meshes.append(trimesh.creation.box(bounds=[lo * units, hi * units]))
    mesh = concat(*meshes)
    file_units = np.asarray(mesh.vertices).astype(np.float32).astype(np.float64)
    vertices = file_units * 80.0  # 0.1 units per stud -> 8 mm per stud
    # the corner block pins the grid to the full shape, as load_seed's minimum corner does
    corner = trimesh.creation.box(bounds=[[0, 0, 0], [0.1, 0.1, 0.04]])
    far = trimesh.creation.box(bounds=[np.array(shape) * units - units, np.array(shape) * units])
    extra = concat(corner, far)
    expected[0, 0, 0] = expected[-1, -1, -1] = True
    extra_vertices = np.asarray(extra.vertices).astype(np.float32).astype(np.float64) * 80.0
    seed = Seed(
        vertices=np.concatenate([vertices, extra_vertices]),
        faces=np.concatenate([np.asarray(mesh.faces), np.asarray(extra.faces) + len(vertices)]),
    )
    design = voxelize(seed, catalog, margin_studs=0)
    assert design.shape == shape
    assert np.array_equal(design.filled, ndimage.binary_fill_holes(expected))


def test_seed_away_from_the_origin_is_moved_there(catalog):
    """A Seed whose minimum corner is not at zero is not squashed into the grid."""
    for origin in [(80.0, 0.0, 0.0), (-80.0, -8.0, -3.2)]:
        mesh = box_seed((32.0, 32.0, 32.0), origin=origin)
        seed = Seed(vertices=np.asarray(mesh.vertices, dtype=float), faces=mesh.faces)
        design = voxelize(seed, catalog, margin_studs=0)
        assert design.shape == (4, 4, 10)
        assert design.filled.all()


def test_thin_shell_open_box_stays_open(catalog):
    """A cup with walls 0.4 mm thick: walls are one cell, the inside stays empty."""
    w, t, h = 48.0, 0.4, 32.0
    i0, i1 = t, w - t
    faces = []
    # outside walls and floor
    faces += quad((0, 0, 0), (w, 0, 0), (w, w, 0), (0, w, 0))
    faces += quad((0, 0, 0), (w, 0, 0), (w, 0, h), (0, 0, h))
    faces += quad((0, w, 0), (w, w, 0), (w, w, h), (0, w, h))
    faces += quad((0, 0, 0), (0, w, 0), (0, w, h), (0, 0, h))
    faces += quad((w, 0, 0), (w, w, 0), (w, w, h), (w, 0, h))
    # inside walls and floor
    faces += quad((i0, i0, t), (i1, i0, t), (i1, i1, t), (i0, i1, t))
    faces += quad((i0, i0, t), (i1, i0, t), (i1, i0, h), (i0, i0, h))
    faces += quad((i0, i1, t), (i1, i1, t), (i1, i1, h), (i0, i1, h))
    faces += quad((i0, i0, t), (i0, i1, t), (i0, i1, h), (i0, i0, h))
    faces += quad((i1, i0, t), (i1, i1, t), (i1, i1, h), (i1, i0, h))
    tris = np.array(faces, dtype=float)
    vertices = tris.reshape(-1, 3)
    seed = Seed(vertices=vertices, faces=np.arange(len(vertices)).reshape(-1, 3))
    filled = body(voxelize(seed, catalog))
    assert filled.shape == (6, 6, 10)
    assert filled[:, :, 0].all()  # the floor
    ring = np.ones((6, 6), dtype=bool)
    ring[1:5, 1:5] = False
    for z in range(1, 10):
        assert np.array_equal(filled[:, :, z], ring), f"layer {z}"


def test_thin_closed_shell_is_filled_solid(catalog):
    """A hollow ball with a 0.3 mm wall: the flood cannot get in, so it is filled."""
    outer = trimesh.creation.icosphere(3, radius=40.0)
    inner = trimesh.creation.icosphere(3, radius=39.7)
    inner.invert()
    design = voxelize(seed_from(concat(outer, inner)), catalog)
    solid = voxelize(seed_from(outer), catalog)
    assert np.array_equal(design.filled, solid.filled)


def test_feature_thinner_than_a_cell_keeps_its_cells(catalog):
    """A 0.5 mm thin fin sticking out of a block does not vanish."""
    block = box_seed((32.0, 32.0, 32.0))
    fin = box_seed((0.5, 20.0, 20.0), origin=(32.0, 6.0, 6.0))
    filled = body(voxelize(seed_from(concat(block, fin)), catalog))
    assert filled.shape == (5, 4, 10)
    assert filled[4].sum() > 0  # the fin column
    assert filled[4, 1:3, 2:8].all()


def test_small_hole_in_the_surface_is_tolerated(catalog):
    sphere = trimesh.creation.icosphere(4, radius=40.0)
    holed = sphere.copy()
    holed.update_faces(np.arange(len(holed.faces)) % 997 != 0)  # punch a few small holes
    assert len(holed.faces) < len(sphere.faces)
    assert np.array_equal(
        voxelize(seed_from(holed), catalog).filled, voxelize(seed_from(sphere), catalog).filled
    )


def test_below_the_ground_counts_as_outside(catalog):
    """An upside-down bucket (open at the bottom) stays hollow: the flood gets in from below."""
    w, h = 40.0, 32.0
    faces = []
    faces += quad((0, 0, h), (w, 0, h), (w, w, h), (0, w, h))  # the bottom, now on top
    faces += quad((0, 0, 0), (w, 0, 0), (w, 0, h), (0, 0, h))
    faces += quad((0, w, 0), (w, w, 0), (w, w, h), (0, w, h))
    faces += quad((0, 0, 0), (0, w, 0), (0, w, h), (0, 0, h))
    faces += quad((w, 0, 0), (w, w, 0), (w, w, h), (w, 0, h))
    tris = np.array(faces, dtype=float)
    vertices = tris.reshape(-1, 3)
    seed = Seed(vertices=vertices, faces=np.arange(len(vertices)).reshape(-1, 3))
    filled = body(voxelize(seed, catalog))
    assert filled.shape == (5, 5, 10)
    assert not filled[1:4, 1:4, :9].any()
    assert filled[:, :, 9].all()


def test_flood_is_six_connected(catalog):
    """Two boxes touching only along an edge: the flood passes the diagonal gap between them
    only through faces, so the empty cells next to the edge stay empty."""
    a = box_seed((16.0, 16.0, 9.6))
    b = box_seed((16.0, 16.0, 9.6), origin=(16.0, 16.0, 0.0))
    filled = body(voxelize(seed_from(concat(a, b)), catalog))
    assert filled.shape == (4, 4, 3)
    assert filled[0:2, 0:2].all() and filled[2:4, 2:4].all()
    assert not filled[2:4, 0:2].any() and not filled[0:2, 2:4].any()


# ---- colour -------------------------------------------------------------------------------------


def test_uncoloured_seed_uses_the_default_colour(catalog):
    design = voxelize(seed_from(box_seed((24.0, 24.0, 24.0))), catalog)
    assert set(np.unique(design.colors).tolist()) == {EMPTY, DEFAULT_COLOUR}


def test_default_colour_can_be_chosen(catalog):
    design = voxelize(seed_from(box_seed((24.0, 24.0, 24.0))), catalog, default_colour=4)
    assert set(np.unique(design.colors).tolist()) == {EMPTY, 4}


def test_colours_snap_to_the_catalogue(catalog):
    red = catalog.colours[4].rgb
    mesh = box_seed((24.0, 24.0, 24.0))
    off_red = np.clip(np.array(red) + (6, -5, 4), 0, 255)
    colours = np.tile(off_red, (len(mesh.faces), 1)).astype(np.uint8)
    design = voxelize(seed_from(mesh, colours), catalog)
    assert catalog.nearest_colour(off_red) == 4
    assert set(np.unique(design.colors).tolist()) == {EMPTY, 4}


def test_transparent_colours_are_never_chosen(catalog):
    clear = [c for c in catalog.colours.values() if c.transparent]
    if not clear:
        pytest.skip("the catalogue has no transparent colours")
    mesh = box_seed((24.0, 24.0, 24.0))
    colours = np.tile(clear[0].rgb, (len(mesh.faces), 1)).astype(np.uint8)
    design = voxelize(seed_from(mesh, colours), catalog)
    used = set(np.unique(design.colors).tolist()) - {EMPTY}
    assert not any(catalog.colours[c].transparent for c in used)


def two_tone_tower(catalog, top_code=4, bottom_code=1):
    """A 3 x 3 stud tower, 6 bricks tall: the lower 4 bricks one colour, the top 2 another."""
    bottom = box_seed((24.0, 24.0, 38.4))
    top = box_seed((24.0, 24.0, 19.2), origin=(0.0, 0.0, 38.4))
    mesh = concat(bottom, top)
    colours = np.zeros((len(mesh.faces), 3), dtype=np.uint8)
    colours[: len(bottom.faces)] = catalog.colours[bottom_code].rgb
    colours[len(bottom.faces) :] = catalog.colours[top_code].rgb
    return seed_from(mesh, colours)


def test_surface_cells_take_the_colour_of_their_surface(catalog):
    design = voxelize(two_tone_tower(catalog), catalog, margin_studs=0)
    c = design.colors
    assert c.shape == (3, 3, 18)
    shell = np.ones(c.shape, dtype=bool)
    shell[1, 1, 1:-1] = False  # the one column of inside cells
    # the shared face at z = 12 plates is the blue part's top (nudged into layer 11) and the
    # red part's bottom (nudged into layer 12), so the colours split exactly there
    assert (c[:, :, :12][shell[:, :, :12]] == 1).all()
    assert (c[:, :, 12:][shell[:, :, 12:]] == 4).all()
    # inside cells: 12 layers of blue surface beat 6 of red
    assert (c[1, 1, 1:12] == 1).all()
    assert (c[1, 1, 13:-1] == 1).all()


def test_inside_cells_take_the_most_common_surface_colour(catalog):
    # a 6 x 6 stud box, 6 bricks tall: blue all round, red only on its top face
    mesh = box_seed((48.0, 48.0, 57.6))
    on_top = mesh.triangles_center[:, 2] > 57.0
    assert on_top.sum() == 2
    colours = np.tile(catalog.colours[1].rgb, (len(mesh.faces), 1)).astype(np.uint8)
    colours[on_top] = catalog.colours[4].rgb
    design = voxelize(seed_from(mesh, colours), catalog, margin_studs=0)
    c = design.colors
    assert c.shape == (6, 6, 18)
    assert (c[1:-1, 1:-1, -1] == 4).all()  # the top layer, away from the side walls
    assert (c[:, :, :-1] == 1).all()  # sides, bottom, and the whole inside are blue
    # the top edge cells hold 8 x 8 mm of red and 8 x 3.2 mm of blue: red wins on area
    assert (c[:, :, -1] == 4).all()


def test_colour_vote_follows_surface_area_not_triangle_count(catalog):
    """One big red triangle and many tiny blue ones in the same cell: red covers more."""
    big = [(0.0, 0.0, 0.0), (7.0, 0.0, 0.0), (0.0, 7.0, 0.0)]
    tiny = [[(x, 7.5, 0.0), (x + 0.1, 7.5, 0.0), (x, 7.6, 0.0)] for x in np.linspace(0, 7, 40)]
    pole = [(0.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 3.0)]  # gives the model height
    tris = np.array([big, *tiny, pole], dtype=float)
    vertices = tris.reshape(-1, 3)
    colours = np.array(
        [catalog.colours[4].rgb] + [catalog.colours[1].rgb] * 40 + [catalog.colours[4].rgb],
        dtype=np.uint8,
    )
    seed = Seed(vertices=vertices, faces=np.arange(len(vertices)).reshape(-1, 3),
                face_colors=colours)  # fmt: skip
    design = voxelize(seed, catalog, margin_studs=0)
    assert design.colors[0, 0, 0] == 4


def test_repeated_runs_give_identical_colours(catalog):
    a, b = sorted([4, 1])
    seed = two_tone_tower(catalog, top_code=4, bottom_code=1)
    first = voxelize(seed, catalog)
    for _ in range(3):
        assert np.array_equal(voxelize(seed, catalog).colors, first.colors)
    assert {a, b} <= set(np.unique(first.colors).tolist())


@pytest.mark.parametrize("x_code, y_code", [(4, 1), (1, 4)])
def test_a_real_colour_tie_goes_to_the_lower_code(catalog, x_code, y_code):
    """A 3 x 3 x 3 cell box: one colour on both x faces, another on both y faces, white on
    top and bottom. Each vertical edge column holds exactly 8 x 3.2 mm of each side colour."""
    mesh = box_seed((24.0, 24.0, 9.6))
    normals = np.round(mesh.face_normals).astype(int)
    colours = np.tile(catalog.colours[15].rgb, (len(mesh.faces), 1)).astype(np.uint8)
    colours[normals[:, 0] != 0] = catalog.colours[x_code].rgb
    colours[normals[:, 1] != 0] = catalog.colours[y_code].rgb
    c = voxelize(seed_from(mesh, colours), catalog, margin_studs=0).colors
    assert c.shape == (3, 3, 3)
    middle = c[:, :, 1]
    assert [middle[0, 0], middle[2, 0], middle[0, 2], middle[2, 2]] == [1, 1, 1, 1]
    assert middle[0, 1] == x_code and middle[2, 1] == x_code  # only the x face passes here
    assert middle[1, 0] == y_code and middle[1, 2] == y_code


def test_colour_snapping_agrees_with_the_catalogue(catalog):
    rng = np.random.default_rng(11)
    palette = [c.rgb for c in catalog.colours.values() if not c.transparent]
    # midpoints between two catalogue colours whose channels sum to even numbers are exact
    # ties; the catalogue picks the first in its own order, and so must the fast path
    ties = [
        tuple((np.array(a) + np.array(b)) // 2)
        for i, a in enumerate(palette)
        for b in palette[i + 1 :]
        if all((x + y) % 2 == 0 for x, y in zip(a, b, strict=True))
    ]
    assert ties, "the catalogue should have at least one exact midpoint"
    colours = np.concatenate(
        [rng.integers(0, 256, size=(3000, 3)), np.array(palette), np.array(ties)]
    ).astype(np.uint8)
    codes, index = _snap(colours, catalog)
    got = codes[index].tolist()
    want = [catalog.nearest_colour(c) for c in colours.tolist()]
    assert got == want


def test_colour_snapping_is_fast_with_many_distinct_colours(catalog):
    rng = np.random.default_rng(5)
    colours = rng.integers(0, 256, size=(200_000, 3)).astype(np.uint8)
    start = time.perf_counter()
    codes, index = _snap(colours, catalog)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"took {elapsed:.1f} s"
    assert len(index) == 200_000 and set(codes.tolist()) <= set(catalog.colours)


def test_textured_like_colours_many_distinct_rgb_values(catalog):
    mesh = trimesh.creation.icosphere(3, radius=40.0)
    rng = np.random.default_rng(3)
    colours = rng.integers(0, 256, size=(len(mesh.faces), 3)).astype(np.uint8)
    design = voxelize(seed_from(mesh, colours), catalog)
    used = set(np.unique(design.colors).tolist()) - {EMPTY}
    assert used <= set(catalog.colours)
    assert len(used) > 3


# ---- hollow -------------------------------------------------------------------------------------


@pytest.mark.parametrize("shell", [1, 2])
def test_hollow_matches_the_shell_rule(catalog, shell):
    solid = voxelize(seed_from(box_seed((80.0, 80.0, 64.0))), catalog)
    hollow = voxelize(seed_from(box_seed((80.0, 80.0, 64.0))), catalog, hollow=True,
                      shell_studs=shell)  # fmt: skip
    expected = shapes.hollowed(solid, shell_studs=shell)
    assert np.array_equal(hollow.colors, expected.colors)
    f = body(hollow)
    assert f.shape == (10, 10, 20)
    s = shell
    assert not f[s:-s, s:-s, 3 * s : -3 * s].any()  # the deep inside is empty
    assert f[:, :, : 3 * s].all()  # the floor is kept (below the ground counts as outside)
    assert f[:, :, -3 * s :].all()  # and the roof
    assert f[:s].all() and f[-s:].all() and f[:, :s].all() and f[:, -s:].all()


def test_hollow_on_a_sphere_matches_the_shell_rule(catalog):
    seed = seed_from(trimesh.creation.icosphere(3, radius=60.0))
    solid = voxelize(seed, catalog)
    hollow = voxelize(seed, catalog, hollow=True)
    assert np.array_equal(hollow.colors, shapes.hollowed(solid).colors)
    assert hollow.filled.sum() < solid.filled.sum()


def test_hollow_never_changes_the_outside_shape(catalog):
    seed = seed_from(trimesh.creation.torus(40.0, 15.0))
    solid = voxelize(seed, catalog).filled
    hollow = voxelize(seed, catalog, hollow=True, shell_studs=1).filled
    assert not (hollow & ~solid).any()
    # every filled cell next to an empty one (or the grid edge) is still there
    padded = np.pad(solid, 1, constant_values=False)
    exposed = solid & ~(
        padded[2:, 1:-1, 1:-1] & padded[:-2, 1:-1, 1:-1] & padded[1:-1, 2:, 1:-1]
        & padded[1:-1, :-2, 1:-1] & padded[1:-1, 1:-1, 2:] & padded[1:-1, 1:-1, :-2]
    )  # fmt: skip
    assert (hollow[exposed]).all()


def test_hollow_small_model_is_all_shell(catalog):
    seed = seed_from(box_seed((32.0, 32.0, 32.0)))
    assert np.array_equal(
        voxelize(seed, catalog, hollow=True).colors, voxelize(seed, catalog).colors
    )


def test_hollow_keeps_colours_of_the_shell(catalog):
    seed = two_tone_tower(catalog)
    solid = voxelize(seed, catalog)
    hollow = voxelize(seed, catalog, hollow=True, shell_studs=1)
    kept = hollow.filled
    assert np.array_equal(hollow.colors[kept], solid.colors[kept])


# ---- the sample model ---------------------------------------------------------------------------


def test_pawn_at_16_studs_stands_upright_in_the_padded_grid(pawn_path, catalog):
    design = voxelize(load_seed(pawn_path, studs=16), catalog)
    assert design.seed_offset == (2, 2, 0)
    # 30 x 30 x 42.5 mm scaled to 128 mm tall: 90.4 mm = 12 studs across, 40 plates tall
    assert design.shape == (12 + 4, 12 + 4, 40 + 6)
    f = design.filled
    layers = np.nonzero(f.any(axis=(0, 1)))[0]
    assert layers.min() == 0 and layers.max() == 39
    area = f.sum(axis=(0, 1))
    assert area[0] > 3 * area[39]  # a wide base and a small head
    assert area[0] == area.max()
    # the base fills the 12 x 12 stud body footprint's middle
    assert f[2:14, 2:14, 0].sum() == f[:, :, 0].sum()
    assert f[8, 8, :40].all()  # solid down the middle
    # roughly symmetric front to back and left to right
    xs, ys, _ = np.nonzero(f)
    assert abs(xs.mean() - ys.mean()) < 0.01
    assert set(np.unique(design.colors).tolist()) == {EMPTY, DEFAULT_COLOUR}


def test_same_input_gives_an_identical_design(pawn_path, catalog):
    seed = load_seed(pawn_path, studs=20)
    first = voxelize(seed, catalog, hollow=True)
    second = voxelize(seed, catalog, hollow=True)
    assert np.array_equal(first.colors, second.colors)
    assert first.seed_offset == second.seed_offset


# ---- bad input and speed ------------------------------------------------------------------------


def test_seed_without_triangles_is_rejected(catalog):
    seed = Seed(vertices=np.zeros((3, 3)), faces=np.zeros((0, 3), dtype=np.int64))
    with pytest.raises(SeedError, match="no triangles"):
        voxelize(seed, catalog)


def test_nan_vertex_is_rejected(catalog):
    seed = seed_from(box_seed((16.0, 16.0, 16.0)))
    seed.vertices[0, 0] = np.nan
    with pytest.raises(SeedError, match="damaged"):
        voxelize(seed, catalog)


@pytest.mark.parametrize(
    "kwargs",
    [{"shell_studs": 0}, {"shell_studs": 1.5}, {"margin_studs": -1}, {"margin_studs": True}],
)
def test_bad_arguments(catalog, kwargs):
    with pytest.raises(ValueError):
        voxelize(seed_from(box_seed((16.0, 16.0, 16.0))), catalog, **kwargs)


@pytest.mark.parametrize("bad", [-1, 999, 70_000, True, 4.0, "4"])
def test_default_colour_must_be_a_catalogue_colour(catalog, bad):
    with pytest.raises(ValueError, match="default_colour"):
        voxelize(seed_from(box_seed((16.0, 16.0, 16.0))), catalog, default_colour=bad)


def test_default_colour_must_not_be_transparent(catalog):
    clear = [c.code for c in catalog.colours.values() if c.transparent]
    if not clear:
        pytest.skip("the catalogue has no transparent colours")
    with pytest.raises(ValueError, match="default_colour"):
        voxelize(seed_from(box_seed((16.0, 16.0, 16.0))), catalog, default_colour=clear[0])


def test_face_colours_of_the_wrong_length(catalog):
    mesh = box_seed((16.0, 16.0, 16.0))
    seed = seed_from(mesh, np.zeros((3, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="face_colors"):
        voxelize(seed, catalog)


def test_200k_triangles_at_48_studs_is_fast(catalog):
    mesh = trimesh.creation.torus(10.0, 4.0, major_sections=500, minor_sections=200)
    assert len(mesh.faces) == 200_000
    seed = seed_from(mesh)
    seed.vertices *= 48 * 8.0 / seed.extent_mm.max()
    start = time.perf_counter()
    design = voxelize(seed, catalog, hollow=True)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"took {elapsed:.1f} s"
    assert design.shape == (48 + 4, 48 + 4, int(np.ceil(seed.extent_mm[2] / 3.2 - 1e-6)) + 6)


def tall_cylinder(sections: int, studs: int) -> Seed:
    mesh = trimesh.creation.cylinder(radius=10.0, height=60.0, sections=sections)
    seed = seed_from(mesh)
    seed.vertices *= studs * 8.0 / seed.extent_mm.max()
    return seed


@pytest.mark.parametrize("sections, studs", [(5000, 48), (5000, 96), (20_000, 96)])
def test_long_thin_triangles_are_fast(catalog, sections, studs):
    """A CAD-style cylinder: every side triangle runs the full height (240 plates at 96
    studs) and every cap triangle runs from the centre to the rim."""
    seed = tall_cylinder(sections, studs)
    start = time.perf_counter()
    design = voxelize(seed, catalog, margin_studs=0)
    elapsed = time.perf_counter() - start
    assert elapsed < 6.0, f"took {elapsed:.1f} s"
    across = studs // 3  # radius 10 against height 60: the diameter is a third of the height
    f = design.filled
    assert f.shape == (across, across, studs * 5 // 2)
    assert (f == f[:, :, :1]).all()  # every layer is the same disc
    # the disc: cells clearly inside the circle are filled, cells clearly outside are not
    centre, radius = across / 2, across / 2
    i = np.arange(across)
    near_x = np.clip(centre, i, i + 1) - centre  # nearest point of each column to the centre
    distance = np.hypot(near_x[:, None], near_x[None, :])
    layer = f[:, :, 0]
    assert layer[distance < radius - 0.01].all()
    assert not layer[distance > radius + 0.01].any()


def test_big_triangles_at_96_studs(catalog):
    """A few huge triangles are split, not sampled point by point in Python."""
    seed = seed_from(box_seed((768.0, 400.0, 160.0)))
    start = time.perf_counter()
    design = voxelize(seed, catalog)
    assert time.perf_counter() - start < 5.0
    assert body(design).shape == (96, 50, 50) and body(design).all()


# ---- slope hints --------------------------------------------------------------------------------


def hints(seed: Seed, catalog, **kwargs) -> tuple[Design, np.ndarray, np.ndarray]:
    """The Design (no padding), its sloped cells and its open-topped filled cells."""
    design = voxelize(seed, catalog, margin_studs=0, **kwargs)
    f = design.filled
    above = np.concatenate([f[:, :, 1:], np.zeros(f.shape[:2] + (1,), dtype=bool)], axis=2)
    assert design.finish is not None
    return design, design.finish == FINISH_SLOPED, f & ~above


def prism_xz(profile, length: float) -> trimesh.Trimesh:
    """A solid made by pushing a convex (x, z) outline in mm ``length`` mm along y."""
    ring = np.asarray(profile, dtype=float)
    n = len(ring)
    front = np.c_[ring[:, 0], np.zeros(n), ring[:, 1]]
    back = np.c_[ring[:, 0], np.full(n, length), ring[:, 1]]
    faces = [[0, i, i + 1] for i in range(1, n - 1)]
    faces += [[n, n + i + 1, n + i] for i in range(1, n - 1)]
    for i in range(n):
        j = (i + 1) % n
        faces += [[i, j, n + j], [i, n + j, n + i]]
    mesh = trimesh.Trimesh(np.vstack([front, back]), np.asarray(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    assert mesh.is_watertight and mesh.volume > 0
    return mesh


def wedge(angle_degrees: float, run_studs: int, width_studs: float = 3) -> trimesh.Trimesh:
    """A ramp rising along x at a real angle (in mm), with a vertical back wall."""
    run = run_studs * 8.0
    rise = run * np.tan(np.radians(angle_degrees))
    return prism_xz([(0.0, 0.0), (run, 0.0), (run, rise)], width_studs * 8.0)


def test_box_gets_no_sloped_cells(catalog):
    """Its top edges hold top and side together; the side is a wall and does not count."""
    for size, origin in [((64.0, 40.0, 32.0), (0, 0, 0)), ((30.5, 21.3, 17.9), (3.1, 0.7, 1.3))]:
        mesh = box_seed(size, origin)
        seed = Seed(vertices=np.asarray(mesh.vertices, dtype=float), faces=mesh.faces)
        design, sloped, open_top = hints(seed, catalog)
        assert open_top.sum() == design.shape[0] * design.shape[1]
        assert not sloped.any()
        assert design.finish is not None and (design.finish == FINISH_STUDS).all()


def test_upright_cylinder_gets_no_sloped_cells(catalog):
    mesh = trimesh.creation.cylinder(radius=40.0, height=50.0, sections=96)
    _, sloped, open_top = hints(seed_from(mesh), catalog)
    assert open_top.sum() > 50
    assert not sloped.any()


@pytest.mark.parametrize(
    "angle, expect_sloped",
    [
        (15, False),
        (19, False),
        (21, True),
        (25, True),
        (45, True),
        (65, True),
        (69, True),
        (71, False),
        (75, False),
    ],
)
def test_ramps_at_real_angles(catalog, angle, expect_sloped):
    """Only surfaces between 20 and 70 degrees from level (measured in mm) are sloped."""
    run = {15: 8, 19: 8, 21: 8, 25: 6, 45: 5, 65: 4, 69: 4, 71: 4, 75: 4}[angle]
    design, sloped, open_top = hints(seed_from(wedge(angle, run)), catalog)
    assert design.shape[:2] == (run, 3)
    assert not (sloped & ~open_top).any()
    if expect_sloped:
        # every column along the ramp; the last one also holds the back wall
        columns = sloped.any(axis=2)
        assert columns[: run - 1].all(), columns.astype(int).T
    else:
        assert not sloped.any()


@pytest.mark.parametrize(
    "plates_per_stud, expect_sloped",
    [
        (0.5, False),  # 26.6 degrees counted in cells, but 11.3 degrees in mm
        (3.0, True),  # 71.6 degrees counted in cells, but 50.2 degrees in mm
    ],
)
def test_angles_are_measured_in_millimetres_not_cells(catalog, plates_per_stud, expect_sloped):
    run_studs = 6
    rise = run_studs * plates_per_stud * 3.2
    mesh = prism_xz([(0.0, 0.0), (run_studs * 8.0, 0.0), (run_studs * 8.0, rise)], 24.0)
    _, sloped, _ = hints(seed_from(mesh), catalog)
    if expect_sloped:
        assert sloped.any(axis=2)[: run_studs - 1].all()
    else:
        assert not sloped.any()


def test_pitched_roof_is_sloped_along_both_faces(catalog):
    """A 45-degree roof, 8 studs wide with its ridge on a stud boundary, 5 studs long:
    the top cell of every column is sloped, the gable ends included."""
    roof = prism_xz([(0.0, 0.0), (64.0, 0.0), (32.0, 32.0)], 40.0)
    design, sloped, open_top = hints(seed_from(roof), catalog)
    assert design.shape == (8, 5, 10)
    assert not (sloped & ~open_top).any()
    zz = np.arange(design.shape[2])
    top = (design.filled * zz).argmax(axis=2)
    x, y = np.meshgrid(np.arange(8), np.arange(5), indexing="ij")
    assert sloped[x, y, top].all()


def top_sloped(design: Design, sloped: np.ndarray) -> np.ndarray:
    """For each (x, y) column: is its highest filled cell sloped?"""
    zz = np.arange(design.shape[2])
    top = (design.filled * zz).argmax(axis=2)
    x, y = np.meshgrid(np.arange(design.shape[0]), np.arange(design.shape[1]), indexing="ij")
    return sloped[x, y, top]


@pytest.mark.parametrize("angle", [30, 45, 60])
@pytest.mark.parametrize("length", [40.2, 40.5, 41.0])
def test_roof_whose_gable_pokes_a_little_into_one_more_row(catalog, angle, length):
    """The gable wall at the far end only just reaches into a sixth row of studs. It runs
    along the slope, not across it, so it must not take the slope away from that row."""
    rise = 32.0 * np.tan(np.radians(angle))
    roof = prism_xz([(0.0, 0.0), (64.0, 0.0), (32.0, rise)], length)
    design, sloped, open_top = hints(seed_from(roof), catalog)
    assert design.shape[:2] == (8, 6)
    assert not (sloped & ~open_top).any()
    assert top_sloped(design, sloped).all(), top_sloped(design, sloped).astype(int).T


def test_roof_on_an_odd_sized_house_is_sloped_to_its_far_end(catalog):
    """A 61 x 40.4 mm house with a 45-degree roof: the last row, which the house only just
    reaches, is sloped like every other row. (Column x=3 holds the ridge in its middle,
    where the two faces cancel sideways, so it keeps its studs in every row.)"""
    w, d, h = 61.0, 40.4, 19.2
    house = concat(
        box_seed((w, d, h)),
        prism_xz([(0.0, h), (w, h), (w / 2, h + w / 2)], d),
    )
    design, sloped, _ = hints(seed_from(house), catalog)
    rows = top_sloped(design, sloped).T  # rows[y] is the row of columns at y
    assert design.shape[:2] == (8, 6)
    expected = np.array([True, True, True, False, True, True, True, True])
    for y, row in enumerate(rows):
        assert np.array_equal(row, expected), f"row y={y}: {row.astype(int)}"


def test_narrow_free_standing_ramp_is_sloped_in_every_column(catalog):
    """A 45-degree ramp only 2 mm wide: its side walls run along the slope, so every column
    along it is sloped, not every other one."""
    design, sloped, open_top = hints(seed_from(wedge(45, 6, width_studs=0.25)), catalog)
    assert design.shape[:2] == (6, 1)
    assert not (sloped & ~open_top).any()
    assert sloped.any(axis=2)[:5].all(), sloped.any(axis=2).astype(int).T


def test_roof_made_of_thin_sheets_is_sloped(catalog):
    """A roof modelled as two 1 mm sheets (as low-poly houses often are): each top cell
    holds both the sheet's top and its underside. Undersides are left out, so the cell
    follows the top and is sloped; were they averaged in, the two faces would cancel and
    the roof would get no slopes at all."""
    s = 1.0 * np.sqrt(2.0)  # 1 mm thick, measured upright
    roof = concat(
        prism_xz([(0.0, 0.0), (32.0, 32.0), (32.0, 32.0 + s), (0.0, s)], 40.0),
        prism_xz([(32.0, 32.0), (64.0, 0.0), (64.0, s), (32.0, 32.0 + s)], 40.0),
    )
    design, sloped, open_top = hints(seed_from(roof), catalog)
    assert design.shape[:2] == (8, 5)
    assert not (sloped & ~open_top).any()
    assert top_sloped(design, sloped).all(), top_sloped(design, sloped).astype(int).T


def test_roof_on_a_house(catalog):
    """A 30-degree roof on a box: the roof is sloped, the walls and eaves stay as they are."""
    w, d, h = 48.0, 32.0, 19.2
    rise = (w / 2) * np.tan(np.radians(30))
    house = concat(
        box_seed((w, d, h)),
        prism_xz([(0.0, h), (w, h), (w / 2, h + rise)], d),
    )
    design, sloped, open_top = hints(seed_from(house), catalog)
    assert sloped.any(axis=2).all()  # every column, as the roof covers all of them
    assert not sloped[:, :, : int(h / 3.2) - 1].any()  # nothing in the walls


def test_wall_with_a_tiny_chamfer_is_not_sloped(catalog):
    """A block whose right side pokes 0.5 mm into a new column, with a 0.4 mm chamfer on
    its top edge: that column's top cell is mostly wall, so it keeps its studs."""
    h = 19.2
    profile = [(0.0, 0.0), (32.5, 0.0), (32.5, h - 0.4), (32.1, h), (0.0, h)]
    design, sloped, _ = hints(seed_from(prism_xz(profile, 16.0)), catalog)
    assert design.shape == (5, 2, 6)
    assert not sloped.any()


def test_cone(catalog):
    """A 45-degree cone is sloped all round, except at its tip, where the slopes meet from
    every side; cones steeper than 70 degrees or flatter than 20 have no sloped cells.
    (The cone is 11 studs across, so its tip is in the middle of one column; with the tip on
    a corner, each of the four columns there holds one side of it, and is sloped.)"""
    mesh = trimesh.creation.cone(radius=44.0, height=44.0, sections=96)
    design, sloped, open_top = hints(seed_from(mesh), catalog)
    assert not (sloped & ~open_top).any()
    xs, ys, zs = np.nonzero(open_top)
    centre = np.array(design.shape[:2]) / 2
    distance = np.hypot(xs + 0.5 - centre[0], ys + 0.5 - centre[1])
    away = distance > 1.5
    assert sloped[xs[away], ys[away], zs[away]].all()
    tip = zs == zs.max()
    assert not sloped[xs[tip], ys[tip], zs[tip]].any()
    for height in (44.0 * np.tan(np.radians(80)), 44.0 * np.tan(np.radians(10))):
        steep_or_flat = trimesh.creation.cone(radius=44.0, height=height, sections=96)
        assert not hints(seed_from(steep_or_flat), catalog)[1].any()


def sphere_seed() -> Seed:
    return seed_from(trimesh.creation.icosphere(4, radius=64.0))


def test_sphere_has_a_band_on_its_upper_half(catalog):
    seed = sphere_seed()
    design, sloped, open_top = hints(seed, catalog)
    assert design.shape == (16, 16, 40)
    assert not (sloped & ~open_top).any()
    # how far above level the sphere is at each open cell's middle (its latitude)
    xs, ys, zs = np.nonzero(open_top)
    middle = (np.c_[xs, ys, zs] + 0.5) * CELL - 64.0
    latitude = np.degrees(np.arcsin(middle[:, 2] / np.linalg.norm(middle, axis=1)))
    marked = sloped[xs, ys, zs]
    assert marked.sum() > 60
    assert marked[(latitude > 30) & (latitude < 62)].all()  # the band
    assert not marked[latitude > 78].any()  # not on the very top
    assert not marked[latitude < 0].any()  # not below the equator
    assert not sloped[:, :, :20].any()
    # the band goes all the way round
    angle = np.degrees(np.arctan2(middle[marked, 1], middle[marked, 0]))
    assert np.histogram(angle, bins=8, range=(-180, 180))[0].min() > 0


def test_inside_out_mesh_gets_no_sloped_cells(catalog):
    """Normals follow the winding: wound inside out, the top of a sphere faces down, which
    counts as an underside, so nothing is sloped (the cells filled stay about the same)."""
    mesh = trimesh.creation.icosphere(4, radius=64.0)
    mesh.invert()
    design, sloped, _ = hints(seed_from(mesh), catalog)
    assert not sloped.any()
    normal, _, _ = hints(sphere_seed(), catalog)
    assert abs(int(design.filled.sum()) - int(normal.filled.sum())) < 0.15 * normal.filled.sum()


def test_hollowing_keeps_the_finish_of_the_cells_that_remain(catalog):
    seed = sphere_seed()
    solid, solid_sloped, _ = hints(seed, catalog)
    hollow, hollow_sloped, _ = hints(seed, catalog, hollow=True)
    assert hollow.filled.sum() < solid.filled.sum()
    kept = hollow.filled
    assert solid.finish is not None and hollow.finish is not None
    assert np.array_equal(hollow.finish[kept], solid.finish[kept])
    assert (hollow.finish[~kept] == FINISH_STUDS).all()
    assert np.array_equal(hollow_sloped, solid_sloped)  # no sloped cell was hollowed out


def test_slope_hints_can_be_turned_off(catalog):
    design, sloped, _ = hints(sphere_seed(), catalog, slope_hints=False)
    assert not sloped.any()
    assert design.finish is not None and (design.finish == FINISH_STUDS).all()
    with_hints = hints(sphere_seed(), catalog)[0]
    assert np.array_equal(design.colors, with_hints.colors)  # the cells do not change


def test_slope_hints_are_deterministic(pawn_path, catalog):
    seed = load_seed(pawn_path, studs=20)
    first = voxelize(seed, catalog)
    assert first.finish is not None and (first.finish == FINISH_SLOPED).any()
    for _ in range(2):
        again = voxelize(seed, catalog)
        assert again.finish is not None and np.array_equal(again.finish, first.finish)
    assert first.fingerprint() == voxelize(seed, catalog).fingerprint()


def test_slope_hints_only_in_the_body_never_in_the_padding(catalog):
    design = voxelize(sphere_seed(), catalog)  # default margin of 2
    assert design.finish is not None
    sloped = design.finish == FINISH_SLOPED
    assert sloped.any()
    assert not (sloped & ~design.filled).any()
    assert not sloped[:2].any() and not sloped[-2:].any() and not sloped[:, :, 40:].any()


def test_200k_triangles_at_48_studs_with_slope_hints_is_fast(catalog):
    mesh = trimesh.creation.icosphere(5, radius=1.0)  # 20,480 triangles, made denser below
    mesh = mesh.subdivide().subdivide()
    mesh = trimesh.Trimesh(mesh.vertices[:, :] * [1.0, 1.0, 0.6], mesh.faces)
    faces = np.asarray(mesh.faces)[:200_000]  # a bowl-like cap and band, open at the bottom
    mesh = trimesh.Trimesh(mesh.vertices, faces)
    seed = seed_from(mesh)
    seed.vertices *= 48 * 8.0 / seed.extent_mm.max()
    start = time.perf_counter()
    design = voxelize(seed, catalog)
    elapsed = time.perf_counter() - start
    assert len(seed.faces) == 200_000
    assert elapsed < 5.0, f"took {elapsed:.1f} s"
    assert design.finish is not None and (design.finish == FINISH_SLOPED).sum() > 100


# ---- the seed keeps its place on the grid ---------------------------------------------------

CAT = Path(__file__).resolve().parent.parent / "samples" / "models" / "cat.glb"


def rounded_bar(width: float, height: float, length: float, radius: float) -> trimesh.Trimesh:
    """A bar along y whose two top edges are rounded alike: mirror-symmetric in x, exactly.

    The (x, z) outline is centred on x = 0, and its left half is the right half negated."""
    angles = np.radians(np.linspace(0.0, 90.0, 7))
    right = [(width / 2, 0.0)] + [
        (width / 2 - radius + radius * np.cos(a), height - radius + radius * np.sin(a))
        for a in angles
    ]
    left = [(-x, z) for x, z in reversed(right)]
    return prism_xz(right + left, length)


def coloured_by_facing(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Flat tops red, everything else blue (so the colours are as symmetric as the shape)."""
    colours = np.tile(np.array([20, 40, 220, 255], dtype=np.uint8), (len(mesh.faces), 1))
    colours[np.asarray(mesh.face_normals)[:, 2] > 0.99] = (200, 30, 30, 255)
    mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=colours)
    return mesh


def swap_xy(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """The same solid turned so x and y change places (faces reversed to keep facing out)."""
    vertices = np.asarray(mesh.vertices)[:, [1, 0, 2]]
    return trimesh.Trimesh(vertices, np.asarray(mesh.faces)[:, ::-1], process=False)


def at_zero(seed: Seed) -> Seed:
    """The seed as load_seed used to leave it: minimum corner at (0, 0, 0)."""
    vertices = seed.vertices - seed.vertices.min(axis=0)
    return Seed(vertices=vertices, faces=seed.faces, face_colors=seed.face_colors)


def mirrored(design: Design, axis: int) -> bool:
    assert design.finish is not None
    return bool(
        np.array_equal(design.colors, np.flip(design.colors, axis))
        and np.array_equal(design.finish, np.flip(design.finish, axis))
    )


@pytest.mark.parametrize(
    ("width", "radius", "axis"),
    [(9.71, 1.6, 0), (6.4, 1.3, 0), (9.71, 1.6, 1), (6.4, 1.3, 1)],
)
def test_symmetric_model_comes_out_symmetric(tmp_path, catalog, width, radius, axis):
    """A bar of fractional width with both top edges rounded: mirror-symmetric in the grid.

    With the old placement (minimum corner at 0) the rounding on one side fell in a narrow
    last column and was marked sloped while the other side was not."""
    mesh = rounded_bar(width, 3.0, 16.0, radius)  # file units: studs
    if axis == 1:
        mesh = swap_xy(mesh)
    path = tmp_path / "bar.ply"
    coloured_by_facing(mesh).export(str(path))
    seed = load_seed(path, studs=16)
    assert seed.face_colors is not None
    slack = (np.ceil(width) - width) / 2 * 8.0
    assert seed.vertices.min(axis=0)[axis] == pytest.approx(slack, abs=1e-4)

    design = voxelize(seed, catalog)
    assert design.finish is not None
    assert body(design).shape[axis] == np.ceil(width)
    assert (design.finish == FINISH_SLOPED).any()
    assert len(np.unique(design.colors[design.colors != EMPTY])) == 2
    assert np.array_equal(design.filled, np.flip(design.filled, axis))
    assert mirrored(design, axis)
    assert mirrored(voxelize(seed, catalog, hollow=True, shell_studs=1), axis)

    # the same mesh placed the old way is the one that came out lopsided
    old = voxelize(at_zero(seed), catalog)
    assert old.shape == design.shape
    assert not mirrored(old, axis)


def test_cat_slope_hints_are_mirror_symmetric(catalog):
    """The sample cat is mirror-symmetric left to right; so are its filled cells, colours
    and slope hints at 16 studs. Placed the old way, its back was sloped on one side only."""
    seed = load_seed(CAT, studs=16)
    assert seed.vertices.min(axis=0)[0] == pytest.approx((10 - 9.71465903) / 2 * 8, abs=1e-6)
    design = voxelize(seed, catalog)
    assert design.finish is not None
    assert (design.finish == FINISH_SLOPED).sum() > 10
    assert np.array_equal(design.filled, design.filled[::-1])
    assert mirrored(design, 0)
    assert not mirrored(voxelize(at_zero(seed), catalog), 0)


def test_seed_starting_at_zero_gives_the_same_design_as_before(catalog, pawn_path):
    """Fingerprints of Designs made before the seed kept its offset (seeds starting at 0).

    The cat's two values were recorded again when colour matching began to count lightness
    half (bricksnap/catalog); with the earlier weighting the code still gives the earlier
    values, so only the colours differ. The pawn has no colours and never changed."""
    cat = at_zero(load_seed(CAT, studs=16))
    assert voxelize(cat, catalog).fingerprint() == "140cbc02fe84b9e7"
    assert voxelize(cat, catalog, hollow=True, shell_studs=1).fingerprint() == "8e8ed1a8400f9386"
    pawn = at_zero(load_seed(pawn_path, studs=24))
    assert voxelize(pawn, catalog, hollow=True).fingerprint() == "851d2a1e04735432"


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("start_cells", [3.7, 1.0, -0.4, -2.0])
def test_seed_not_starting_in_the_first_cell_is_moved_to_zero(catalog, axis, start_cells):
    """Outside the first cell (or anywhere but 0 in z) the seed is moved to start at 0."""
    base = at_zero(load_seed(CAT, studs=12))
    shift = np.zeros(3)
    shift[axis] = start_cells * CELL[axis]
    moved = Seed(vertices=base.vertices + shift, faces=base.faces, face_colors=base.face_colors)
    assert voxelize(moved, catalog).fingerprint() == voxelize(base, catalog).fingerprint()


def test_seed_starting_within_the_first_cell_keeps_its_offset(catalog):
    """A seed point p lies in body cell floor(p / CELL_MM) when the seed starts within the
    first cell and fits in ceil(extent / cell) cells there; z always starts at 0."""
    bar = box_seed((20.0, 24.0, 9.6), origin=(3.0, 0.0, 1.6))  # 2.5 studs, starting 3 mm in
    nub = box_seed((0.6, 24.0, 3.2), origin=(16.4, 0.0, 11.2))  # on top, at x = 2.05 cells
    seed = seed_from(concat(bar, nub))
    seed.vertices += [3.0, 0.0, 1.6]  # seed_from moved it to 0; put it back
    design = voxelize(seed, catalog, margin_studs=0)
    assert design.shape == (3, 3, 4)  # 2.5 studs need 3 cells, 4 plates need 4 layers
    assert design.filled[:, :, :3].all()
    assert np.flatnonzero(design.filled[:, :, 3].any(axis=1)).tolist() == [2]
    # moved to 0 the nub would be at 13.4 mm, in column 1
    at_0 = voxelize(seed_from(concat(bar, nub)), catalog, margin_studs=0)
    assert np.flatnonzero(at_0.filled[:, :, 3].any(axis=1)).tolist() == [1]

    # a seed that would need one more cell at its offset is moved to 0 instead of squashed
    box = box_seed((24.0, 24.0, 9.6), origin=(3.2, 0.0, 0.0))
    design = voxelize(seed_from(box), catalog, margin_studs=0)
    moved = Seed(vertices=np.asarray(box.vertices, dtype=float), faces=box.faces)
    assert voxelize(moved, catalog, margin_studs=0).fingerprint() == design.fingerprint()
    assert design.shape == (3, 3, 3) and design.filled.all()
