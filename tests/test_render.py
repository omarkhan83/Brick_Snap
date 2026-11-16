"""Tests for bricksnap.render: geometry of the pictures, labels, hiding, sheets."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest
import shapes
import trimesh
from PIL import Image, ImageDraw

from bricksnap import render as R
from bricksnap.types import (
    CELL_MM,
    EMPTY,
    FINISH_SMOOTH,
    Build,
    Design,
    Detail,
    Placement,
    Seed,
)

RED, BLUE, YELLOW, GREEN, WHITE = 4, 1, 14, 2, 15
STRAIGHT = ("front", "right", "back", "left", "top")


# ---- helpers -------------------------------------------------------------------------------


def arr(im: Image.Image) -> np.ndarray:
    assert im.mode == "RGB"
    return np.asarray(im).astype(np.int32)


def is_red(px) -> bool:
    r, g, b = (int(v) for v in px)
    return r > 110 and g < 70 and b < 70


def red_mask(a: np.ndarray) -> np.ndarray:
    return (a[..., 0] > 110) & (a[..., 1] < 70) & (a[..., 2] < 70)


def blue_mask(a: np.ndarray) -> np.ndarray:
    return (a[..., 2] > 100) & (a[..., 2] > a[..., 0] + 50)


def drawn_mask(a: np.ndarray) -> np.ndarray:
    """Pixels that are neither background nor faint grid lines."""
    bg = np.abs(a - np.array(R.BACKGROUND)).sum(axis=2) > 24
    grid = np.abs(a - np.array(R.GRID_LINE)).sum(axis=2) > 24
    return bg & grid


def one_brick(cell, shape=(6, 5, 9), part="3005", color=RED) -> Build:
    x, y, z = cell
    return Build(shape=shape, parts=[Placement(part, color, x, y, z, 0, 1)])


def box_seed(lo_cells, hi_cells) -> Seed:
    """A box mesh whose corners sit exactly on cell corners (seed_offset applied by caller)."""
    lo = np.asarray(lo_cells, float) * (8.0, 8.0, 3.2)
    hi = np.asarray(hi_cells, float) * (8.0, 8.0, 3.2)
    m = trimesh.creation.box(extents=hi - lo)
    v = m.vertices - m.vertices.min(axis=0)
    return Seed(vertices=v, faces=np.asarray(m.faces, dtype=np.int64))


def sample(im: Image.Image, col: float, row: float):
    return im.getpixel((int(math.floor(col)), int(math.floor(row))))


# ---- frames and sizes ----------------------------------------------------------------------


@pytest.mark.parametrize("s", [4, 8, 16, 25])
def test_image_size_follows_scale_without_labels(s):
    shape = (7, 5, 11)
    pad = math.ceil(s / 4) + 2
    for view in ("front", "back"):
        f = R.view_frame(shape, view, px_per_stud=s, labels=False)
        assert (f.area_width, f.area_height) == (7 * s, round(11 * 0.4 * s))
        assert (f.width, f.height) == (7 * s + 2 * pad, round(11 * 0.4 * s) + 2 * pad)
    for view in ("right", "left"):
        f = R.view_frame(shape, view, px_per_stud=s, labels=False)
        assert (f.area_width, f.area_height) == (5 * s, round(11 * 0.4 * s))
    f = R.view_frame(shape, "top", px_per_stud=s, labels=False)
    assert (f.area_width, f.area_height) == (7 * s, 5 * s)


def test_rendered_images_have_frame_size(catalog):
    build = one_brick((1, 1, 0))
    for view in R.VIEWS:
        for labels in (True, False):
            f = R.view_frame(build.shape, view, px_per_stud=12, labels=labels)
            im = R.render_build(build, catalog, view, px_per_stud=12, labels=labels)
            assert im.mode == "RGB"
            assert im.size == (f.width, f.height)


def test_drawn_extent_matches_scale(catalog):
    """A smooth 4 x 3 x 6-plate box covers exactly 4 studs by 6 plates of pixels."""
    d = shapes.box(4, 3, 2, colour=RED)
    d.finish = np.full(d.shape, FINISH_SMOOTH, dtype=np.uint8)  # no studs sticking up
    for s in (10, 16):
        im = R.render_design(d, catalog, "front", px_per_stud=s, labels=False)
        rows, cols = np.nonzero(red_mask(arr(im)) | drawn_mask(arr(im)))
        assert cols.max() - cols.min() + 1 == 4 * s
        assert rows.max() - rows.min() + 1 == round(6 * 0.4 * s)
        top = R.render_design(d, catalog, "top", px_per_stud=s, labels=False)
        rows, cols = np.nonzero(drawn_mask(arr(top)))
        assert (cols.max() - cols.min() + 1, rows.max() - rows.min() + 1) == (4 * s, 3 * s)


def test_all_views_share_the_scale():
    shape = (9, 4, 12)
    fs = {v: R.view_frame(shape, v, px_per_stud=16) for v in R.VIEWS}
    # 1 stud along x is 16 px in front, back and top; 1 plate is 6.4 px in all side views
    for v in ("front", "back", "top"):
        a = fs[v].project([[0, 0, 0], [1, 0, 0]])
        assert abs(abs(a[1, 0] - a[0, 0]) - 16) < 1e-9
    for v in ("front", "right", "back", "left"):
        a = fs[v].project([[0, 0, 0], [0, 0, 1]])
        assert abs(abs(a[1, 1] - a[0, 1]) - 6.4) < 1e-9
    # iso is orthographic at the same scale: a 1 mm step moves at most 16/8 px
    a = fs["iso"].project([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 2.5]])
    for k in (1, 2, 3):
        d = np.hypot(*(a[k, :2] - a[0, :2]))
        assert 0 < d <= 16 + 1e-9


def test_frame_projection_directions():
    """Picture right / up follow the contract for every straight-on view."""
    shape = (6, 5, 9)
    expect = {  # view: (grid step for picture right, grid step for picture up)
        "front": ((1, 0, 0), (0, 0, 1)),
        "right": ((0, 1, 0), (0, 0, 1)),
        "back": ((-1, 0, 0), (0, 0, 1)),
        "left": ((0, -1, 0), (0, 0, 1)),
        "top": ((1, 0, 0), (0, 1, 0)),
    }
    for view, (right, up) in expect.items():
        f = R.view_frame(shape, view)
        o = np.array([3.0, 2.0, 4.0])
        p0, pr, pu = f.project([o, o + right, o + up])
        assert pr[0] > p0[0] and abs(pr[1] - p0[1]) < 1e-9, view
        assert pu[1] < p0[1] and abs(pu[0] - p0[0]) < 1e-9, view


# ---- labels --------------------------------------------------------------------------------


def test_tick_steps():
    f = R.view_frame((20, 8, 30), "front")
    t = R.axis_ticks(f)
    assert [i for i, _ in t["u"]] == list(range(0, 20, 2))
    assert [i for i, _ in t["v"]] == list(range(0, 30, 3))
    wide = R.view_frame((60, 8, 6), "front")
    assert [i for i, _ in R.axis_ticks(wide)["u"]] == list(range(0, 60, 5))
    top = R.view_frame((10, 12, 6), "top")
    assert [i for i, _ in R.axis_ticks(top)["v"]] == list(range(0, 12, 2))
    assert R.axis_ticks(R.view_frame((4, 4, 4), "iso")) == {"u": [], "v": []}
    # at a tiny scale the numbers spread out instead of overlapping
    small = R.axis_ticks(R.view_frame((40, 8, 60), "front", px_per_stud=3))
    us = [i for i, _ in small["u"]]
    assert us[0] == 0 and us[1] - us[0] > 2
    vs = [i for i, _ in small["v"]]
    assert all(i % 3 == 0 for i in vs) and vs[1] - vs[0] > 3


def test_tick_positions_follow_mirrored_axes():
    """The tick for cell i sits over the centre of cell i, computed independently here."""
    nx, ny, nz = 7, 5, 9
    s = 16
    for view in STRAIGHT:
        f = R.view_frame((nx, ny, nz), view, px_per_stud=s)
        ticks = R.axis_ticks(f)
        for i, col in ticks["u"]:
            if view in ("front", "top", "right"):
                want = f.left + (i + 0.5) * s
            elif view == "back":
                want = f.left + (nx - i - 0.5) * s
            else:  # left
                want = f.left + (ny - i - 0.5) * s
            assert abs(col - want) < 1e-9, (view, i)
        for i, row in ticks["v"]:
            pitch = s if view == "top" else 0.4 * s
            n = ny if view == "top" else nz
            want = f.top + (n - i - 0.5) * pitch
            assert abs(row - want) < 1e-9, (view, i)


@pytest.mark.parametrize("view", STRAIGHT)
def test_red_brick_appears_where_the_labels_say(catalog, view):
    """A red brick at cell (4, 2, 3) shows up at the label positions for 4, 2 and 3."""
    cell = (4, 2, 3)
    build = one_brick(cell, shape=(7, 5, 9))
    im = R.render_build(build, catalog, view)
    f = R.view_frame(build.shape, view)
    ticks = R.axis_ticks(f)
    u_axis = {"front": 0, "back": 0, "top": 0, "right": 1, "left": 1}[view]
    v_axis = 1 if view == "top" else 2
    u_pos = dict(ticks["u"])
    v_pos = dict(ticks["v"])
    col, row = u_pos[cell[u_axis]], v_pos[cell[v_axis]]
    assert is_red(sample(im, col, row)), (view, sample(im, col, row))
    # one labelled tick away along either axis there is nothing
    for j in (cell[u_axis] - 2, cell[u_axis] + 2):
        if j in u_pos:
            assert not is_red(sample(im, u_pos[j], row)), (view, j)
    for j in (cell[v_axis] - 3, cell[v_axis] + 3):
        if j in v_pos:
            assert not is_red(sample(im, col, v_pos[j])), (view, j)
    # the red region is exactly one cell wide at the scale
    a = arr(im)
    cols = np.nonzero(red_mask(a)[int(row)])[0]
    assert cols.min() <= col <= cols.max()
    assert cols.max() - cols.min() + 1 <= 16


@pytest.mark.parametrize("view", STRAIGHT)
def test_tick_marks_and_numbers_are_drawn_under_ticks(catalog, view):
    build = one_brick((1, 1, 0), shape=(9, 7, 12))
    im = R.render_build(build, catalog, view)
    a = arr(im)
    f = R.view_frame(build.shape, view)
    bottom = f.top + f.area_height
    dark = a.sum(axis=2) < 400
    for i, col in R.axis_ticks(f)["u"]:
        c = int(math.floor(col))
        assert dark[bottom + 3 : bottom + 6, c].all(), (view, i)  # the tick mark
        # number: dark text pixels in the label row, centred on the tick
        band = dark[bottom + 7 : bottom + 7 + 14, max(0, c - 12) : c + 13]
        ys, xs = np.nonzero(band)
        assert len(xs) > 0, (view, i)
        centre = max(0, c - 12) + (xs.min() + xs.max()) / 2
        assert abs(centre - c) <= 3, (view, i, centre, c)
    for i, row in R.axis_ticks(f)["v"]:
        r = int(math.floor(row))
        assert dark[r, f.left - 6 : f.left - 2].all(), (view, i)
        band = dark[max(0, r - 7) : r + 8, : f.left - 8]
        ys, _ = np.nonzero(band)
        assert len(ys) > 0, (view, i)
        middle = max(0, r - 7) + (ys.min() + ys.max()) / 2
        assert abs(middle - r) <= 3, (view, i)


LABEL_SHAPE = (7, 5, 9)
# view: (cell indices numbered along the bottom, picture column of cell i relative to the
# drawing area, bottom title, cells numbered up the side, row of cell i, side title)
LABEL_EXPECT = {
    "front": ([0, 2, 4, 6], lambda i: (i + 0.5) * 16, "x ->", [0, 3, 6], "z ^"),
    "back": ([0, 2, 4, 6], lambda i: (7 - i - 0.5) * 16, "<- x", [0, 3, 6], "z ^"),
    "right": ([0, 2, 4], lambda i: (i + 0.5) * 16, "y ->", [0, 3, 6], "z ^"),
    "left": ([0, 2, 4], lambda i: (5 - i - 0.5) * 16, "<- y", [0, 3, 6], "z ^"),
    "top": ([0, 2, 4, 6], lambda i: (i + 0.5) * 16, "x ->", [0, 2, 4], "y ^"),
}


def numbered(labels, kind: str) -> list[tuple[str, int]]:
    out = []
    for lab in labels:
        if lab.kind == kind:
            assert lab.at is not None
            out.append((lab.text, lab.at))
    return out


@pytest.mark.parametrize("view", STRAIGHT)
def test_label_texts_are_the_cell_indices(view):
    """The printed numbers are the indices of the cells under them, z in plates, and the
    axis titles show the direction (mirrored in the back and left views)."""
    f = R.view_frame(LABEL_SHAPE, view, px_per_stud=16)
    labels = R.label_texts(f)
    u_cells, u_col, u_title, v_cells, v_title = LABEL_EXPECT[view]
    side_pitch = 16 if view == "top" else 6.4
    side_n = LABEL_SHAPE[1] if view == "top" else LABEL_SHAPE[2]
    # positions to the pixel (a cell centre can fall on a pixel boundary)
    got_u = numbered(labels, "u")
    want_u = [(str(i), f.left + u_col(i)) for i in u_cells]
    assert [t for t, _ in got_u] == [t for t, _ in want_u], view
    assert all(abs(a - w) <= 1 for (_, a), (_, w) in zip(got_u, want_u, strict=True)), view
    got_v = numbered(labels, "v")
    want_v = [(str(i), f.top + (side_n - i - 0.5) * side_pitch) for i in v_cells]
    assert [t for t, _ in got_v] == [t for t, _ in want_v], view
    assert all(abs(a - w) <= 1 for (_, a), (_, w) in zip(got_v, want_v, strict=True)), view
    assert [lab.text for lab in labels if lab.kind == "u-axis"] == [u_title]
    assert [lab.text for lab in labels if lab.kind == "v-axis"] == [v_title]
    assert R.label_texts(R.view_frame(LABEL_SHAPE, view, labels=False)) == []
    assert R.label_texts(R.view_frame(LABEL_SHAPE, "iso")) == []


@pytest.mark.parametrize("view", STRAIGHT)
def test_label_pixels_are_those_texts(catalog, view):
    """Each label on the picture is exactly its text drawn in the label font, so a wrong
    digit or a missing title would show up as different pixels."""
    build = one_brick((1, 1, 0), shape=LABEL_SHAPE)
    im = R.render_build(build, catalog, view)
    f = R.view_frame(LABEL_SHAPE, view)
    font = R._font(16)
    labels = R.label_texts(f)
    assert len(labels) >= 4
    for lab in labels:
        ref = Image.new("RGB", im.size, R.BACKGROUND)
        ImageDraw.Draw(ref).text((lab.x, lab.y), lab.text, fill=R.INK, font=font)
        ra = arr(ref)
        ink = np.abs(ra - np.array(R.BACKGROUND)).sum(axis=2) > 0
        ys, xs = np.nonzero(ink)
        assert len(xs) > 0, (view, lab.text)
        box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
        assert (arr(im)[box] == ra[box]).all(), (view, lab.text)
        # a different text in the same place does not match
        other = Image.new("RGB", im.size, R.BACKGROUND)
        wrong = "8" if lab.text != "8" else "1"
        ImageDraw.Draw(other).text((lab.x, lab.y), wrong, fill=R.INK, font=font)
        assert not (arr(im)[box] == arr(other)[box]).all(), (view, lab.text)


def test_labels_off_leaves_plain_margin(catalog):
    build = one_brick((0, 0, 0))
    im = R.render_build(build, catalog, "front", labels=False)
    f = R.view_frame(build.shape, "front", labels=False)
    a = arr(im)
    margin = np.ones(a.shape[:2], dtype=bool)
    margin[f.top - 4 : f.top + f.area_height, f.left : f.left + f.area_width] = False
    assert (np.abs(a[margin] - np.array(R.BACKGROUND)).sum(axis=1) == 0).all()


# ---- views, hiding, depth ------------------------------------------------------------------


def test_back_view_mirrors_front_view(catalog):
    """With a one-stud-deep build, the back view is the front view flipped left to right."""
    # a one-deep L shape: 1x4 brick along the bottom, 1x1 brick on its left end
    parts = [Placement("3010", RED, 0, 0, 0, 0, 1), Placement("3005", RED, 0, 0, 3, 0, 2)]
    build = Build(shape=(6, 1, 9), parts=parts)
    front = red_mask(arr(R.render_build(build, catalog, "front", labels=False)))
    back = red_mask(arr(R.render_build(build, catalog, "back", labels=False)))
    assert front.sum() > 100
    assert (back == front[:, ::-1]).mean() > 0.995
    # the tall end is at small x: on the left in front, on the right in back
    f_cols = np.nonzero(front[:, :].any(axis=0))[0]
    b_cols = np.nonzero(back.any(axis=0))[0]
    assert f_cols.min() < front.shape[1] / 2 < b_cols.max()


def test_left_view_mirrors_right_view(catalog):
    parts = [Placement("3010", RED, 0, 0, 0, 90, 1), Placement("3005", RED, 0, 3, 3, 0, 2)]
    build = Build(shape=(1, 6, 9), parts=parts)
    right = red_mask(arr(R.render_build(build, catalog, "right", labels=False)))
    left = red_mask(arr(R.render_build(build, catalog, "left", labels=False)))
    assert right.sum() > 100
    assert (left == right[:, ::-1]).mean() > 0.995
    # the 1x1 on top is at y = 3: right of centre in "right", left of centre in "left"
    f = R.view_frame(build.shape, "right", labels=False)
    row = int(f.cell_center(0, 3, 4)[1])
    r_cols = np.nonzero(right[row])[0]
    l_cols = np.nonzero(left[row])[0]
    assert r_cols.mean() > right.shape[1] / 2 > l_cols.mean()


def test_top_view_has_front_at_the_bottom(catalog):
    parts = [Placement("3005", RED, 0, 4, 0, 0, 1), Placement("3005", BLUE, 0, 0, 0, 0, 1)]
    im = arr(R.render_build(Build(shape=(2, 5, 3), parts=parts), catalog, "top"))
    red_rows = np.nonzero(red_mask(im).any(axis=1))[0]
    blue_rows = np.nonzero(blue_mask(im).any(axis=1))[0]
    assert red_rows.max() < blue_rows.min()


def test_nearer_parts_hide_farther_ones(catalog):
    parts = [Placement("3005", RED, 2, 0, 0, 0, 1), Placement("3005", BLUE, 2, 3, 0, 0, 1)]
    build = Build(shape=(5, 5, 3), parts=parts)
    for view, colour_test in (("front", is_red), ("back", lambda p: not is_red(p))):
        f = R.view_frame(build.shape, view)
        im = R.render_build(build, catalog, view)
        px = sample(im, *f.cell_center(2, 0, 1))
        assert colour_test(px), (view, px)
    back = arr(R.render_build(build, catalog, "back"))
    assert blue_mask(back).sum() > 50 and red_mask(back).sum() == 0
    front = arr(R.render_build(build, catalog, "front"))
    assert blue_mask(front).sum() == 0


def test_iso_hides_far_parts(catalog):
    wall = [
        Placement("3008", RED, 0, 0, 0, 0, 1),
        Placement("3008", RED, 0, 0, 3, 0, 1),
    ]
    hidden = Placement("3005", BLUE, 3, 1, 0, 0, 1)  # right behind the wall
    with_wall = R.render_build(Build((8, 4, 9), wall + [hidden]), catalog, "iso")
    without = R.render_build(Build((8, 4, 9), [hidden]), catalog, "iso")
    assert blue_mask(arr(without)).sum() > 100
    assert blue_mask(arr(with_wall)).sum() == 0
    assert red_mask(arr(with_wall)).sum() > 500


def test_iso_box_has_lighter_top_and_darker_sides(catalog):
    build = Build((4, 4, 3), [Placement("3068b", RED, 1, 1, 0, 0, 1)])  # 2x2 tile, no studs
    im = R.render_build(build, catalog, "iso")
    f = R.view_frame(build.shape, "iso")
    top = sample(im, *f.project([[2.0, 2.0, 1.0]])[0, :2])
    front = sample(im, *f.project([[2.0, 1.0, 0.5]])[0, :2])
    right = sample(im, *f.project([[3.0, 2.0, 0.5]])[0, :2])
    assert all(is_red(p) or p[0] > 150 for p in (top, front, right))
    assert sum(top) > sum(front) > sum(right)


def test_farther_parts_are_darker(catalog):
    parts = [Placement("3005", RED, 0, 0, 0, 0, 1), Placement("3005", RED, 2, 4, 0, 0, 1)]
    build = Build(shape=(3, 5, 3), parts=parts)
    f = R.view_frame(build.shape, "front")
    im = R.render_build(build, catalog, "front")
    near = sample(im, *f.cell_center(0, 0, 1))
    far = sample(im, *f.cell_center(2, 4, 1))
    assert is_red(near) and is_red(far)
    assert far[0] < near[0] - 10


def test_nearer_parts_hide_farther_ones_in_side_and_top_views(catalog):
    """Right looks from +x (large x is nearest), left from -x, top from above."""
    parts = [Placement("3005", RED, 0, 2, 0, 0, 1), Placement("3005", BLUE, 4, 2, 0, 0, 1)]
    build = Build(shape=(5, 5, 3), parts=parts)
    right = arr(R.render_build(build, catalog, "right"))
    assert blue_mask(right).sum() > 50 and red_mask(right).sum() == 0
    left = arr(R.render_build(build, catalog, "left"))
    assert red_mask(left).sum() > 50 and blue_mask(left).sum() == 0
    stack = [Placement("3005", RED, 2, 2, 0, 0, 1), Placement("3005", BLUE, 2, 2, 3, 0, 2)]
    top = arr(R.render_build(Build(shape=(5, 5, 6), parts=stack), catalog, "top"))
    assert blue_mask(top).sum() > 50 and red_mask(top).sum() == 0
    # turned upside down (blue at the bottom) the top view shows red
    flipped = [Placement("3005", BLUE, 2, 2, 0, 0, 1), Placement("3005", RED, 2, 2, 3, 0, 2)]
    top = arr(R.render_build(Build(shape=(5, 5, 6), parts=flipped), catalog, "top"))
    assert red_mask(top).sum() > 50 and blue_mask(top).sum() == 0


@pytest.mark.parametrize("view", STRAIGHT)
def test_farther_parts_are_darker_in_every_straight_view(catalog, view):
    """Two red bricks at opposite corners: the one nearer the viewer is brighter."""
    p, q = (0, 0, 0), (4, 4, 3)
    parts = [Placement("3005", RED, *p, 0, 1), Placement("3005", RED, *q, 0, 1)]
    build = Build(shape=(5, 5, 6), parts=parts)
    near, far = {
        "front": (p, q),
        "back": (q, p),
        "right": (q, p),
        "left": (p, q),
        "top": (q, p),
    }[view]
    f = R.view_frame(build.shape, view)
    im = R.render_build(build, catalog, view)
    # sample beside the stud of a brick seen from above
    shift = (0.2, 0.2, 0.0) if view == "top" else (0.0, 0.0, 0.0)
    pn = sample(im, *f.cell_center(near[0] + shift[0], near[1] + shift[1], near[2] + 1))
    pf = sample(im, *f.cell_center(far[0] + shift[0], far[1] + shift[1], far[2] + 1))
    assert is_red(pn) and is_red(pf), (view, pn, pf)
    assert pf[0] < pn[0] - 10, (view, pn, pf)


def test_iso_farther_parts_are_darker(catalog):
    build = Build((4, 12, 3), [Placement("3003", RED, 1, 0, 0), Placement("3003", RED, 1, 9, 0)])
    f = R.view_frame(build.shape, "iso")
    im = R.render_build(build, catalog, "iso")
    near = sample(im, *f.project([[3.0, 1.0, 1.5]])[0, :2])
    far = sample(im, *f.project([[3.0, 10.0, 1.5]])[0, :2])
    assert all(p[0] > 80 and p[1] < 40 and p[2] < 40 for p in (near, far)), (near, far)
    assert far[0] < near[0] - 5, (near, far)


def test_iso_parts_are_outlined(catalog):
    """In iso too, two 1x2 bricks side by side show a darker seam than one 1x4 brick."""
    two = Build((4, 1, 3), [Placement("3004", RED, 0, 0, 0), Placement("3004", RED, 2, 0, 0)])
    one = Build((4, 1, 3), [Placement("3010", RED, 0, 0, 0)])
    f = R.view_frame(two.shape, "iso")
    col, row = f.project([[2.0, 0.0, 1.5]])[0, :2]
    c, r = int(math.floor(col)), int(math.floor(row))
    a2 = arr(R.render_build(two, catalog, "iso"))
    a1 = arr(R.render_build(one, catalog, "iso"))
    seam2 = a2[r, c - 1 : c + 2].sum(axis=1).min()
    seam1 = a1[r, c - 1 : c + 2].sum(axis=1).min()
    assert seam2 < seam1 - 40, (seam2, seam1)


def test_far_stud_is_hidden_by_a_nearer_taller_part(catalog):
    """The stud on top of a far brick does not show through a taller brick in front."""
    parts = [
        Placement("3005", RED, 1, 0, 0, 0, 1),
        Placement("3005", RED, 1, 0, 3, 0, 2),
        Placement("3005", BLUE, 1, 2, 0, 0, 1),
    ]
    build = Build((3, 3, 6), parts)
    front = arr(R.render_build(build, catalog, "front"))
    assert red_mask(front).sum() > 100
    assert blue_mask(front).sum() == 0
    # with nothing in front, the blue brick and its stud show
    alone = arr(R.render_build(Build((3, 3, 6), [parts[2]]), catalog, "front"))
    assert blue_mask(alone).sum() > 100


def test_top_view_studs_are_rings(catalog):
    build = one_brick((1, 1, 0), shape=(3, 3, 3))
    f = R.view_frame(build.shape, "top")
    im = R.render_build(build, catalog, "top")
    centre = sample(im, *f.project([[1.5, 1.5, 3.0]])[0, :2])
    ring = sample(im, *f.project([[1.5 + 0.27, 1.5, 3.0]])[0, :2])
    plain = sample(im, *f.project([[1.15, 1.15, 3.0]])[0, :2])
    assert sum(ring) < sum(plain) - 20, (ring, plain)
    assert sum(centre) > sum(plain) + 20, (centre, plain)


def test_iso_studs_are_drawn(catalog):
    """A 1x1 plate and a 1x1 tile differ only by the stud, which iso must show."""
    plate = arr(R.render_build(Build((3, 3, 2), [Placement("3024", RED, 1, 1, 0)]), catalog, "iso"))
    tile = arr(R.render_build(Build((3, 3, 2), [Placement("3070b", RED, 1, 1, 0)]), catalog, "iso"))
    assert (np.abs(plate - tile).sum(axis=2) > 20).sum() > 20


def test_background_is_light(catalog):
    build = one_brick((1, 1, 0))
    m = trimesh.creation.icosphere(subdivisions=1, radius=8.0)
    seed = Seed(vertices=m.vertices - m.vertices.min(axis=0), faces=np.asarray(m.faces))
    d = shapes.box(2, 2, 1)
    for view in R.VIEWS:
        for im in (
            R.render_build(build, catalog, view),
            R.render_design(d, catalog, view),
            R.render_seed(seed, view, build.shape),
        ):
            assert arr(im)[-1, -1].sum() > 600, view
            assert arr(im)[0, -1].sum() > 600, view
    sheet = R.compare_sheet(seed, d, None, catalog)
    assert arr(sheet)[-1, -1].sum() > 600


def test_neighbouring_parts_are_outlined(catalog):
    """Two 1x2 bricks side by side show a dark line between them; one 1x4 does not."""
    two = Build((4, 1, 3), [Placement("3004", RED, 0, 0, 0), Placement("3004", RED, 2, 0, 0)])
    one = Build((4, 1, 3), [Placement("3010", RED, 0, 0, 0)])
    f = R.view_frame(two.shape, "front")
    row = int(f.cell_center(0, 0, 1)[1])
    col = int(f.left + 2 * 16)  # first pixel column of cell x = 2
    a2 = arr(R.render_build(two, catalog, "front"))
    a1 = arr(R.render_build(one, catalog, "front"))
    seam2 = a2[row, col - 1 : col + 1].sum(axis=1).min()
    seam1 = a1[row, col - 1 : col + 1].sum(axis=1).min()
    assert seam2 < seam1 - 40
    # and every part has an outline against the background
    left_edge = a1[row, f.left]
    inside = a1[row, f.left + 8]
    assert left_edge.sum() < inside.sum() - 40


def test_exposed_studs_are_drawn(catalog):
    build = one_brick((1, 0, 0), shape=(3, 1, 6))
    f = R.view_frame(build.shape, "front")
    im = R.render_build(build, catalog, "front")
    col, _ = f.cell_center(1, 0, 0)
    _, row_above = f.project([[1.5, 0.5, 3.25]])[0, :2]
    assert is_red(sample(im, col, row_above))  # a stud just above the top face
    assert not is_red(sample(im, f.left + 1 * 16 + 1, row_above))  # beside the stud
    # a stud covered by a part on top is not drawn: plates leave no gap
    covered = Build((3, 1, 6), [Placement("3005", RED, 1, 0, 0), Placement("3024", BLUE, 1, 0, 3)])
    im2 = R.render_build(covered, catalog, "front")
    assert not is_red(sample(im2, col, row_above))


def test_upto_step_hides_later_parts(catalog):
    parts = [Placement("3001", RED, 0, 0, 0, 0, 1), Placement("3001", BLUE, 0, 0, 3, 0, 2)]
    build = Build((4, 2, 6), parts)
    for view in ("front", "iso"):
        all_parts = arr(R.render_build(build, catalog, view))
        step1 = arr(R.render_build(build, catalog, view, upto_step=1))
        step2 = arr(R.render_build(build, catalog, view, upto_step=2))
        assert all_parts.shape == step1.shape
        assert blue_mask(all_parts).sum() > 100
        assert blue_mask(step1).sum() == 0 and red_mask(step1).sum() > 100
        assert (step2 == all_parts).all()
    nothing = arr(R.render_build(build, catalog, "front", upto_step=0))
    assert red_mask(nothing).sum() == 0


def test_bad_parts_do_not_crash(catalog):
    parts = [
        Placement("3005", RED, 0, 0, 0),
        Placement("no-such-part", RED, 1, 0, 0),
        Placement("3005", 9999, 1, 0, 0),  # colour not in the table: drawn magenta
        Placement("3001", RED, 2, 0, 0),  # sticks out of the grid: not drawn
    ]
    build = Build((3, 1, 3), parts)
    for view in R.VIEWS:
        R.render_build(build, catalog, view)
    f = R.view_frame(build.shape, "front")
    px = sample(R.render_build(build, catalog, "front"), *f.cell_center(1, 0, 1))
    assert px[0] > 180 and px[2] > 180 and px[1] < 80
    px = sample(R.render_build(build, catalog, "front"), *f.cell_center(2, 0, 1))
    assert not is_red(px)


def test_empty_build_renders_blank(catalog):
    for view in R.VIEWS:
        im = R.render_build(Build((3, 3, 3), []), catalog, view)
        assert red_mask(arr(im)).sum() == 0


# ---- designs -------------------------------------------------------------------------------


def test_design_cells_in_their_colours(catalog):
    colors = np.full((4, 3, 6), EMPTY, dtype=np.int16)
    colors[0, 0, 0:3] = RED
    colors[3, 0, 3] = BLUE
    d = Design(colors=colors)
    f = R.view_frame(d.shape, "front")
    im = R.render_design(d, catalog, "front")
    assert is_red(sample(im, *f.cell_center(0, 0, 1)))
    blue = sample(im, *f.cell_center(3, 0, 3))
    assert blue[2] > blue[0] + 50
    assert not is_red(sample(im, *f.cell_center(1, 0, 1)))
    for view in R.VIEWS:
        f = R.view_frame(d.shape, view)
        assert R.render_design(d, catalog, view).size == (f.width, f.height)


def test_design_finish_controls_studs(catalog):
    colors = np.full((3, 1, 4), EMPTY, dtype=np.int16)
    colors[1, 0, 0] = RED
    studs = Design(colors=colors)
    smooth = Design(colors=colors, finish=np.full(colors.shape, FINISH_SMOOTH, np.uint8))
    f = R.view_frame(studs.shape, "front")
    col, _ = f.cell_center(1, 0, 0)
    _, row = f.project([[1.5, 0.5, 1.25]])[0, :2]
    assert is_red(sample(R.render_design(studs, catalog, "front"), col, row))
    assert not is_red(sample(R.render_design(smooth, catalog, "front"), col, row))


def test_design_details_are_drawn(catalog):
    colors = np.full((3, 3, 4), EMPTY, dtype=np.int16)
    colors[:, :, 0] = WHITE
    d = Design(colors=colors, details=[Detail(part="98138", color=RED, x=1, y=1, z=1)])
    f = R.view_frame(d.shape, "top")
    im = R.render_design(d, catalog, "top")
    assert is_red(sample(im, *f.cell_center(1, 1, 1)))
    assert not is_red(sample(im, *f.cell_center(0, 0, 0)))


def test_design_and_build_line_up(catalog):
    """A Design and a Build covering the same cells give the same silhouette."""
    d = shapes.box(4, 2, 1, colour=RED)
    b = Build(d.shape, [Placement("3001", RED, 0, 0, 0, 0, 1)])
    for view in R.VIEWS:
        md = drawn_mask(arr(R.render_design(d, catalog, view, labels=False)))
        mb = drawn_mask(arr(R.render_build(b, catalog, view, labels=False)))
        assert md.shape == mb.shape
        assert (md == mb).mean() > 0.99, view


# ---- seeds ---------------------------------------------------------------------------------


@pytest.mark.parametrize("view", R.VIEWS)
def test_seed_lines_up_with_design(catalog, view):
    """A box seed covering cells 1..4 x 1..3 x 0..5 matches a Design of those cells."""
    offset = (1, 1, 0)
    seed = box_seed((0, 0, 0), (4, 3, 6))
    colors = np.full((6, 5, 8), EMPTY, dtype=np.int16)
    colors[1:5, 1:4, 0:6] = RED
    d = Design(colors=colors, finish=np.full(colors.shape, FINISH_SMOOTH, np.uint8))
    d.seed_offset = offset
    si = arr(R.render_seed(seed, view, d.shape, seed_offset=offset))
    di = arr(R.render_design(d, catalog, view))
    assert si.shape == di.shape
    ms, md = drawn_mask(si), drawn_mask(di)
    iou = (ms & md).sum() / (ms | md).sum()
    if view == "iso":
        assert iou > 0.98, iou
    else:
        assert iou > 0.995, iou
        rows_s, cols_s = np.nonzero(ms)
        rows_d, cols_d = np.nonzero(md)
        assert abs(cols_s.min() - cols_d.min()) <= 1 and abs(cols_s.max() - cols_d.max()) <= 1
        assert abs(rows_s.min() - rows_d.min()) <= 1 and abs(rows_s.max() - rows_d.max()) <= 1


def box_mesh(lo_cells, hi_cells) -> trimesh.Trimesh:
    """A box mesh spanning exactly the given cell corners, in seed millimetres."""
    lo = np.asarray(lo_cells, float) * np.asarray(CELL_MM)
    hi = np.asarray(hi_cells, float) * np.asarray(CELL_MM)
    m = trimesh.creation.box(extents=hi - lo)
    m.apply_translation((lo + hi) / 2 - m.bounds.mean(axis=0))
    return m


def seed_of(*boxes) -> Seed:
    m = trimesh.util.concatenate([box_mesh(lo, hi) for lo, hi in boxes])
    assert isinstance(m, trimesh.Trimesh)
    return Seed(vertices=np.asarray(m.vertices), faces=np.asarray(m.faces, dtype=np.int64))


def design_of(shape, offset, *boxes) -> Design:
    colors = np.full(shape, EMPTY, dtype=np.int16)
    for lo, hi in boxes:
        sl = tuple(slice(a + o, b + o) for a, b, o in zip(lo, hi, offset, strict=True))
        colors[sl] = RED
    d = Design(colors=colors, finish=np.full(shape, FINISH_SMOOTH, np.uint8))
    d.seed_offset = offset
    return d


@pytest.mark.parametrize("view", R.VIEWS)
@pytest.mark.parametrize("s", [5, 16, 17])
def test_off_centre_seed_lines_up_exactly(catalog, view, s):
    """An off-centre box seed covers exactly the pixels of the Design of its cells."""
    box = ((0, 0, 0), (5, 3, 10))
    offset = (2, 3, 1)
    d = design_of((9, 7, 13), offset, box)
    si = arr(R.render_seed(seed_of(box), view, d.shape, seed_offset=offset, px_per_stud=s))
    di = arr(R.render_design(d, catalog, view, px_per_stud=s))
    ms, md = drawn_mask(si), drawn_mask(di)
    assert ms.sum() > 50
    assert (ms != md).sum() == 0, (view, s, (ms != md).sum())


@pytest.mark.parametrize("view", R.VIEWS)
def test_asymmetric_seed_is_not_mirrored(catalog, view):
    """An L-shaped seed, lopsided along every axis, matches its Design pixel for pixel."""
    boxes = (((0, 0, 0), (5, 2, 3)), ((0, 0, 3), (2, 4, 9)))
    offset = (2, 1, 1)
    d = design_of((9, 7, 12), offset, *boxes)
    si = arr(R.render_seed(seed_of(*boxes), view, d.shape, seed_offset=offset, labels=False))
    di = arr(R.render_design(d, catalog, view, labels=False))
    ms, md = drawn_mask(si), drawn_mask(di)
    assert ms.sum() > 50
    assert (ms != md).sum() == 0, (view, (ms != md).sum())
    # and the shape really is lopsided in this view: mirroring it would not match
    if view != "iso":
        assert (md != md[:, ::-1]).sum() > 50


def test_seed_faces_are_shaded_by_the_light():
    """In iso, the front and right faces of a grey cube get different brightness."""
    box = ((0, 0, 0), (3, 3, 8))
    f = R.view_frame((5, 5, 10), "iso")
    im = R.render_seed(seed_of(box), "iso", (5, 5, 10), seed_offset=(1, 1, 1))
    front = sample(im, *f.project([[2.5, 1.0, 5.0]])[0, :2])
    right = sample(im, *f.project([[4.0, 2.5, 5.0]])[0, :2])
    top = sample(im, *f.project([[2.5, 2.5, 9.0]])[0, :2])
    sums = sorted([sum(front), sum(right), sum(top)])
    assert sums[1] - sums[0] > 15 and sums[2] - sums[1] > 15, (front, right, top)


def test_seed_sphere_is_round_and_centred():
    m = trimesh.creation.icosphere(subdivisions=3, radius=40.0)
    seed = Seed(vertices=m.vertices - m.vertices.min(axis=0), faces=np.asarray(m.faces))
    shape = (10, 10, 25)  # 80 mm in every direction
    for view in ("front", "right", "top", "iso"):
        im = arr(R.render_seed(seed, view, shape, labels=False))
        rows, cols = np.nonzero(drawn_mask(im))
        h, w = rows.max() - rows.min() + 1, cols.max() - cols.min() + 1
        assert abs(h - w) <= 3, (view, h, w)
        assert abs(w - 160) <= 3, (view, w)
        f = R.view_frame(shape, view, labels=False)
        cx, cy = f.project([[5.0, 5.0, 12.5]])[0, :2]
        assert abs((cols.min() + cols.max()) / 2 - cx) <= 2
        assert abs((rows.min() + rows.max()) / 2 - cy) <= 2


def test_seed_is_shaded_and_coloured():
    m = trimesh.creation.icosphere(subdivisions=2, radius=20.0)
    v = m.vertices - m.vertices.min(axis=0)
    grey = Seed(vertices=v, faces=np.asarray(m.faces))
    im = arr(R.render_seed(grey, "front", (5, 5, 13), labels=False))
    body = im[drawn_mask(im)]
    assert body.std(axis=0).mean() > 10  # flat-shaded: not a single flat colour
    assert (np.abs(body[:, 0] - body[:, 2]) < 12).mean() > 0.95  # grey
    coloured = Seed(
        vertices=v,
        faces=np.asarray(m.faces),
        face_colors=np.tile(np.array([[30, 90, 200]], np.uint8), (len(m.faces), 1)),
    )
    im = arr(R.render_seed(coloured, "front", (5, 5, 13), labels=False))
    bluish = (im[..., 2] > im[..., 0] + 40) & (im[..., 2] > im[..., 1] + 20)
    assert bluish.sum() > 0.9 * drawn_mask(im).sum()


def test_seed_with_bad_faces_is_rejected():
    seed = Seed(vertices=np.zeros((3, 3)), faces=np.array([[0, 1, 5]]))
    with pytest.raises(ValueError, match="corners"):
        R.render_seed(seed, "front", (2, 2, 2))


def test_empty_seed_renders_blank():
    seed = Seed(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64))
    im = R.render_seed(seed, "iso", (2, 2, 2))
    assert drawn_mask(arr(im)).sum() == 0


# ---- sheets --------------------------------------------------------------------------------


def solid(colour, size=(40, 30)) -> Image.Image:
    return Image.new("RGB", size, colour)


def test_contact_sheet_layout():
    colours = [(200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0), (0, 200, 200)]
    items = [(f"item {i}", solid(c)) for i, c in enumerate(colours)]
    sheet = R.contact_sheet(items, columns=3, title="Five squares")
    a = arr(sheet)
    centres = []
    for c in colours:
        ys, xs = np.nonzero((a == np.array(c)).all(axis=2))
        assert len(xs) == 40 * 30
        centres.append((xs.mean(), ys.mean()))
    # row 0: items 0, 1, 2 left to right; row 1: items 3, 4 below them
    assert centres[0][0] < centres[1][0] < centres[2][0]
    assert abs(centres[0][1] - centres[2][1]) < 1
    assert centres[3][1] > centres[0][1] + 30
    assert abs(centres[3][0] - centres[0][0]) < 1 and abs(centres[4][0] - centres[1][0]) < 1
    # captions are drawn above each picture, and the title above everything
    ys0 = np.nonzero((a == np.array(colours[0])).all(axis=2))[0].min()
    xs0 = np.nonzero((a == np.array(colours[0])).all(axis=2))[1].min()
    caption = a[ys0 - 16 : ys0, xs0 : xs0 + 40]
    assert (caption.sum(axis=2) < 300).any()
    assert (a[:20].sum(axis=2) < 300).any()


def test_contact_sheet_errors():
    with pytest.raises(ValueError, match="no pictures"):
        R.contact_sheet([])
    with pytest.raises(ValueError, match="column"):
        R.contact_sheet([("a", solid((0, 0, 0)))], columns=0)


def test_contact_sheet_without_title_and_mixed_sizes():
    sheet = R.contact_sheet([("a", solid((200, 0, 0), (50, 20))), ("b", solid((0, 0, 200)))])
    assert sheet.mode == "RGB"
    assert sheet.width >= 50 + 40 and sheet.height >= 30


def blue_seed(shape_cells=(4, 2, 6)) -> Seed:
    s = box_seed((0, 0, 0), shape_cells)
    s.face_colors = np.tile(np.array([[30, 90, 220]], np.uint8), (len(s.faces), 1))
    return s


def test_compare_sheet_has_seed_row_above_build_row(catalog):
    d = shapes.box(4, 2, 2, colour=RED)
    b = Build(d.shape, [Placement("3001", RED, 0, 0, 0, 0, 1), Placement("3001", RED, 0, 0, 3)])
    sheet = arr(R.compare_sheet(blue_seed(), d, b, catalog))
    blue_rows = np.nonzero(blue_mask(sheet).any(axis=1))[0]
    red_rows = np.nonzero(red_mask(sheet).any(axis=1))[0]
    assert len(blue_rows) and len(red_rows)
    assert blue_rows.max() < red_rows.min()
    # four columns, one per view, the same left edges in both rows
    blue_cols = np.nonzero(blue_mask(sheet).any(axis=0))[0]
    red_cols = np.nonzero(red_mask(sheet).any(axis=0))[0]
    assert abs(blue_cols.min() - red_cols.min()) <= 2
    assert abs(blue_cols.max() - red_cols.max()) <= 2


def test_compare_sheet_uses_design_without_build(catalog):
    d = shapes.box(4, 2, 2, colour=GREEN)
    sheet = R.compare_sheet(blue_seed(), d, None, catalog, views=("front", "top"))
    a = arr(sheet)
    green = (a[..., 1] > 90) & (a[..., 0] < 60) & (a[..., 2] < 80)
    assert green.sum() > 100
    assert np.nonzero(blue_mask(a).any(axis=1))[0].max() < np.nonzero(green.any(axis=1))[0].min()


def test_compare_sheet_without_seed_is_one_row(catalog):
    d = shapes.box(4, 2, 2, colour=RED)
    with_seed = R.compare_sheet(blue_seed(), d, None, catalog, views=("front", "iso"))
    without = R.compare_sheet(None, d, None, catalog, views=("front", "iso"))
    assert without.height < with_seed.height * 0.7
    assert blue_mask(arr(without)).sum() == 0
    assert red_mask(arr(without)).sum() > 100


def green_mask(a: np.ndarray) -> np.ndarray:
    return (a[..., 1] > 50) & (a[..., 1] > a[..., 0] + 30) & (a[..., 1] > a[..., 2] + 15)


def bluish_mask(a: np.ndarray) -> np.ndarray:
    """Blue seed pixels, including its darkest shaded faces and outline."""
    return (a[..., 2] > a[..., 0] + 15) & (a[..., 2] > a[..., 1] + 8)


def test_compare_sheet_bottom_row_is_the_build_when_given(catalog):
    d = shapes.box(4, 2, 2, colour=GREEN)
    b = Build(d.shape, [Placement("3001", RED, 0, 0, 0, 0, 1), Placement("3001", RED, 0, 0, 3)])
    with_build = arr(R.compare_sheet(blue_seed(), d, b, catalog))
    assert red_mask(with_build).sum() > 500
    assert green_mask(with_build).sum() == 0
    without = arr(R.compare_sheet(blue_seed(), d, None, catalog))
    assert green_mask(without).sum() > 500
    assert red_mask(without).sum() == 0


def test_compare_sheet_scale_and_seed_offset_reach_every_picture(catalog):
    """At 8 px per stud everything is drawn at half size, and the seed (placed with the
    Design's seed_offset) stands in exactly the same columns as the build."""
    box = ((0, 0, 0), (4, 2, 6))
    offset = (2, 1, 0)
    d = design_of((8, 4, 8), offset, box)
    b = Build(d.shape, [Placement("3001", RED, 2, 1, 0, 0, 1), Placement("3001", RED, 2, 1, 3)])
    seed = seed_of(box)
    seed.face_colors = np.tile(np.array([[30, 90, 220]], np.uint8), (len(seed.faces), 1))
    counts = {}
    for s in (8, 16):
        a = arr(R.compare_sheet(seed, d, b, catalog, views=("front", "top"), px_per_stud=s))
        blue, red = bluish_mask(a), red_mask(a)
        assert np.nonzero(blue.any(axis=1))[0].max() < np.nonzero(red.any(axis=1))[0].min()
        blue_cols = set(np.nonzero(blue.any(axis=0))[0].tolist())
        red_cols = set(np.nonzero(red.any(axis=0))[0].tolist())
        assert len(blue_cols ^ red_cols) <= 4, (s, sorted(blue_cols ^ red_cols))
        counts[s] = (blue.sum(), red.sum())
    for k in range(2):
        ratio = counts[8][k] / counts[16][k]
        assert 0.18 < ratio < 0.32, (k, ratio)


def test_compare_sheet_rejects_unknown_view(catalog):
    d = shapes.box(2, 2, 1)
    with pytest.raises(ValueError, match="Unknown view"):
        R.compare_sheet(None, d, None, catalog, views=("front", "underneath"))
    with pytest.raises(ValueError, match="at least one view"):
        R.compare_sheet(None, d, None, catalog, views=())


# ---- errors, determinism, speed ------------------------------------------------------------


def test_errors_are_plain(catalog):
    build = one_brick((0, 0, 0))
    with pytest.raises(ValueError, match='Unknown view "side".*front, right, back, left'):
        R.render_build(build, catalog, "side")
    with pytest.raises(ValueError, match="pixels per stud"):
        R.render_build(build, catalog, "front", px_per_stud=0)
    with pytest.raises(ValueError, match="at least one cell"):
        R.view_frame((0, 3, 3), "front")


def test_smallest_scale_draws_every_plate(catalog):
    """Below 3 px per stud a plate would be under a pixel tall and could vanish, so 2 is
    refused; at 3 a one-plate tile shows at every height."""
    one = Build((4, 1, 12), [Placement("2431", RED, 0, 0, 0)])
    with pytest.raises(ValueError, match="3 or more"):
        R.render_build(one, catalog, "front", px_per_stud=2)
    with pytest.raises(ValueError, match="3 or more"):
        R.view_frame((4, 1, 12), "iso", px_per_stud=2)
    for z in range(12):
        build = Build((4, 1, 12), [Placement("2431", RED, 0, 0, z)])
        for view in ("front", "right", "back", "left"):
            im = arr(R.render_build(build, catalog, view, px_per_stud=3, labels=False))
            reddish = (im[..., 0] > im[..., 1] + 40) & (im[..., 0] > im[..., 2] + 40)
            assert reddish.sum() >= 3, (z, view)


def test_output_is_deterministic(catalog):
    d = shapes.striped(shapes.sphere(8), (RED, BLUE))
    m = trimesh.creation.icosphere(subdivisions=3, radius=32.0)
    seed = Seed(vertices=m.vertices - m.vertices.min(axis=0), faces=np.asarray(m.faces))
    b = Build(d.shape, [Placement("3005", RED, 3, 3, 3 * k, 0, k + 1) for k in range(6)])
    for view in R.VIEWS:
        assert (
            R.render_design(d, catalog, view).tobytes()
            == R.render_design(d, catalog, view).tobytes()
        )
        assert R.render_seed(seed, view, d.shape).tobytes() == (
            R.render_seed(seed, view, d.shape).tobytes()
        )
    one = R.compare_sheet(seed, d, b, catalog).tobytes()
    two = R.compare_sheet(seed, d, b, catalog).tobytes()
    assert one == two


def test_compare_sheet_for_5000_parts_is_fast(catalog):
    nx, ny, courses = 25, 20, 10
    colours = (RED, BLUE, YELLOW, GREEN)
    parts = [
        Placement("3005", colours[(x + y + c) % 4], x, y, 3 * c, 0, c + 1)
        for x in range(nx)
        for y in range(ny)
        for c in range(courses)
    ]
    assert len(parts) == 5000
    b = Build((nx, ny, 3 * courses), parts)
    m = trimesh.creation.icosphere(subdivisions=4, radius=80.0)
    v = m.vertices - m.vertices.min(axis=0)
    seed = Seed(vertices=v * np.array([200 / 160, 160 / 160, 96 / 160]), faces=np.asarray(m.faces))
    d = Design(colors=np.full(b.shape, RED, dtype=np.int16))
    start = time.perf_counter()
    sheet = R.compare_sheet(seed, d, b, catalog)
    elapsed = time.perf_counter() - start
    assert sheet.width > 0
    assert elapsed < 5.0, elapsed
