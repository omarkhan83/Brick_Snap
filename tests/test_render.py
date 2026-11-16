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


# ---- stage 2: real part shapes ---------------------------------------------------------------

SLOPES = ("3040b", "3039", "54200", "85984", "4286", "11477")
ROUNDS = ("98138", "6141", "14769", "3062b", "6143", "59900", "4740")
ROTS = (0, 90, 180, 270)
SIDE_VIEWS = ("front", "right", "back", "left")
# grid direction of picture right, and of "towards the viewer", in each side view
PICTURE_RIGHT = {"front": (1, 0), "right": (0, 1), "back": (-1, 0), "left": (0, -1)}
TOWARDS = {"front": (0, -1), "right": (1, 0), "back": (0, 1), "left": (-1, 0)}


def colour_for(catalog, pid: str) -> int:
    for c in (RED, BLUE, YELLOW, GREEN):
        if catalog.exists(pid, c):
            return c
    raise AssertionError(f"no test colour for {pid}")


def lone(catalog, pid: str, rot: int = 0, z: int = 0) -> tuple[Build, Placement]:
    """One part with a free cell all round it (and above it)."""
    p = Placement(pid, colour_for(catalog, pid), 1, 1, z, rot, 1)
    w, d, h = catalog.footprint(p)
    return Build((w + 2, d + 2, z + h + 2), [p]), p


def dot(a, b) -> int:
    return a[0] * b[0] + a[1] * b[1]


def body_box(frame, catalog, p):
    """Picture (col0, col1, row_top, row_bottom) of the part's body, pixel indices inclusive."""
    w, d, h = catalog.footprint(p)
    lo = np.array([p.x, p.y, p.z], float)
    hi = lo + (w, d, h)
    corners = np.array(
        [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
    )
    pic = frame.project(corners)
    c0, c1 = pic[:, 0].min(), pic[:, 0].max()
    r0, r1 = pic[:, 1].min(), pic[:, 1].max()
    # pixels whose centres fall inside
    return (
        int(math.ceil(c0 - 0.5)),
        int(math.floor(c1 - 0.5)),
        int(math.ceil(r0 - 0.5)),
        int(math.floor(r1 - 0.5)),
    )


def plain(im) -> np.ndarray:
    return drawn_mask(arr(im))


def stud_row_columns(frame, catalog, p, c0: int, c1: int, read_leftwards: bool) -> list[int]:
    """Indices (counted from the high end, as the profile is read) of the body columns whose
    pixel centres lie over the part's stud rows."""
    low = catalog.low_side(p)
    axis = 0 if low[0] != 0 else 1
    rows = {(x, y)[axis] for x, y in catalog.stud_cells(p)}
    out = []
    for k, col in enumerate(range(c0, c1 + 1)):
        g = [p.x + 0.5, p.y + 0.5, p.z + 0.5]
        # the grid coordinate along the slope's axis at this column's centre
        a0 = frame.project([[*(g[:axis] + [0.0] + g[axis + 1 :])]])[0, 0]
        a1 = frame.project([[*(g[:axis] + [1.0] + g[axis + 1 :])]])[0, 0]
        coord = (col + 0.5 - a0) / (a1 - a0)
        if any(r < coord < r + 1 for r in rows):
            out.append(c1 - col if read_leftwards else k)
    return sorted(out)


def assert_falls_towards_low_side(catalog, build, p, *, alone: bool = True, s: int = 16) -> None:
    """In both side views across its slope, the part's columns fall from full height over its
    stud rows to a low lip at its low side."""
    low = catalog.low_side(p)
    assert low is not None
    views = [v for v in SIDE_VIEWS if dot(PICTURE_RIGHT[v], low) != 0]
    assert len(views) == 2
    for view in views:
        f = R.view_frame(build.shape, view, labels=False, px_per_stud=s)
        m = plain(R.render_build(build, catalog, view, labels=False, px_per_stud=s))
        c0, c1, r0, r1 = body_box(f, catalog, p)
        full = r1 - r0 + 1
        heights = m[r0 : r1 + 1, c0 : c1 + 1].sum(axis=0)
        leftwards = dot(PICTURE_RIGHT[view], low) < 0
        if leftwards:  # low side on the picture's left: read leftwards
            heights = heights[::-1]
        # from the high end to the low end the columns only get shorter
        assert (np.diff(heights) <= 1).all(), (view, heights.tolist())
        assert heights[0] >= full - 1, (view, heights.tolist())
        assert heights[-1] <= 0.4 * full, (view, heights.tolist())
        assert heights[-1] >= 1  # the low lip is there
        # full height over the stud rows, and already lower a little past them
        studded = stud_row_columns(f, catalog, p, c0, c1, leftwards)
        if catalog.stud_cells(p):
            assert studded, (view, p)
            assert (heights[studded] >= full - 1).all(), (view, heights.tolist(), studded)
            past = max(studded) + 3
            assert heights[past] < heights[studded].min(), (view, heights.tolist(), studded)
        if alone:  # nothing is drawn beside the part
            assert not m[r0 : r1 + 1, : c0 - 1].any() and not m[r0 : r1 + 1, c1 + 2 :].any()


@pytest.mark.parametrize("pid", SLOPES)
@pytest.mark.parametrize("rot", ROTS)
def test_wedge_seen_from_the_side_falls_towards_its_low_side(catalog, pid, rot):
    build, p = lone(catalog, pid, rot)
    assert_falls_towards_low_side(catalog, build, p)
    if catalog.stud_cells(p):  # at a larger scale the flat top and the crease are sharper
        build, p = lone(catalog, pid, rot)
        assert_falls_towards_low_side(catalog, build, p, s=32)


@pytest.mark.parametrize("pid", ("3039", "3040b", "4286", "11477"))
def test_the_same_slope_in_four_rotations_in_one_build_each_falls_its_own_way(catalog, pid):
    """Copies of one part in different rotations are not drawn alike: each falls towards its
    own low side (a gable roof is two 3039 back to back)."""
    colour = colour_for(catalog, pid)
    parts, pos = [], 1
    for step, rot in enumerate(ROTS, start=1):
        p = Placement(pid, colour, pos, pos, 0, rot, step)
        w, d, _ = catalog.footprint(p)
        parts.append(p)
        pos += max(w, d) + 1  # along a diagonal, so no two overlap in any side view
    build = Build((pos, pos, 5), parts)
    for p in parts:
        assert_falls_towards_low_side(catalog, build, p, alone=False)
    # a gable: rot 0 and rot 180 back to back, seen from the side, peak in the middle
    gable = Build(
        (2, 4, 4), [Placement("3039", RED, 0, 0, 0, 0), Placement("3039", RED, 0, 2, 0, 180)]
    )
    f = R.view_frame(gable.shape, "right", labels=False)
    m = plain(R.render_build(gable, catalog, "right", labels=False))
    _, _, r0, r1 = body_box(f, catalog, Placement("3039", RED, 0, 0, 0, 0))
    cols = [int(f.project([[0, y, 0]])[0, 0]) for y in (0.1, 1.5, 2.5, 3.9)]
    heights = [int(m[r0 : r1 + 1, c].sum()) for c in cols]
    full = r1 - r0 + 1
    assert heights[0] < 0.5 * full and heights[3] < 0.5 * full, heights
    assert heights[1] >= full - 1 and heights[2] >= full - 1, heights


@pytest.mark.parametrize("pid", ("3039", "3040b", "4286", "11477", "3665b", "3062b"))
def test_a_turned_design_detail_looks_like_the_same_part_in_a_build(catalog, pid):
    colour = colour_for(catalog, pid)
    for rot in ROTS:
        p = Placement(pid, colour, 1, 1, 0, rot)
        w, d, h = catalog.footprint(p)
        shape = (w + 2, d + 2, h + 2)
        design = Design(
            colors=np.full(shape, EMPTY, dtype=np.int16),
            details=[Detail(part=pid, color=colour, x=1, y=1, z=0, rot=rot)],
        )
        build = Build(shape, [p])
        for view in R.VIEWS:
            sd = R.silhouette(design, catalog, view, px_per_stud=16)
            sb = R.silhouette(build, catalog, view, px_per_stud=16)
            assert sd.sum() > 50 and (sd == sb).all(), (pid, rot, view, (sd != sb).sum())
            a = R.render_design(design, catalog, view).tobytes()
            assert a == R.render_build(build, catalog, view).tobytes(), (pid, rot, view)


@pytest.mark.parametrize("pid", SLOPES + ("3665b",))
@pytest.mark.parametrize("rot", ROTS)
def test_wedge_seen_end_on_is_a_rectangle(catalog, pid, rot):
    build, p = lone(catalog, pid, rot)
    low = catalog.low_side(p)
    for view in SIDE_VIEWS:
        if dot(TOWARDS[view], low) == 0:
            continue
        f = R.view_frame(build.shape, view, labels=False)
        m = plain(R.render_build(build, catalog, view, labels=False))
        c0, c1, r0, r1 = body_box(f, catalog, p)
        assert m[r0 : r1 + 1, c0 : c1 + 1].all(), view
        outside = m.copy()
        outside[: r1 + 1, c0 : c1 + 1] = False  # the body, and studs standing on it
        assert not outside.any(), view


@pytest.mark.parametrize("pid", SLOPES)
@pytest.mark.parametrize("rot", ROTS)
def test_slanted_face_seen_from_the_low_side_is_lighter_than_the_back(catalog, pid, rot):
    build, p = lone(catalog, pid, rot)
    low = catalog.low_side(p)
    pics = {}
    for view in SIDE_VIEWS:
        if dot(TOWARDS[view], low) != 0:
            f = R.view_frame(build.shape, view, labels=False)
            c0, c1, r0, r1 = body_box(f, catalog, p)
            im = R.render_build(build, catalog, view, labels=False)
            row = r0 + (r1 - r0) // 3  # in the upper part of the body: on the slanted face
            pics[dot(TOWARDS[view], low)] = sum(sample(im, (c0 + c1) / 2 + 0.5, row + 0.5))
    assert pics[1] > pics[-1] + 30, pics


@pytest.mark.parametrize("pid", SLOPES + ("3665b",))
@pytest.mark.parametrize("rot", ROTS)
def test_wedge_from_above_has_studs_only_on_its_stud_cells(catalog, pid, rot):
    build, p = lone(catalog, pid, rot, z=1)
    low = catalog.low_side(p)
    f = R.view_frame(build.shape, "top")
    im = R.render_build(build, catalog, "top")
    w, d, h = catalog.footprint(p)
    studs = set(catalog.stud_cells(p))
    across = (0.0, 0.42) if low[0] != 0 else (0.42, 0.0)  # along the face, not down it
    top = p.z + h
    # a flat top of the same height, for comparison: a 1x1 brick whose top is level with it
    ref = Build(build.shape, [Placement("3005", p.color, 0, 0, top - 3)])
    ref_im = R.render_build(ref, catalog, "top")
    flat = sum(sample(ref_im, *f.project([[0.08, 0.92, top]])[0, :2]))
    for x in range(p.x, p.x + w):
        for y in range(p.y, p.y + d):
            centre = sum(sample(im, *f.project([[x + 0.5, y + 0.5, top]])[0, :2]))
            side = sum(
                sample(im, *f.project([[x + 0.5 + across[0], y + 0.5 + across[1], top]])[0, :2])
            )
            if (x, y) in studs:
                assert centre > side + 20, (x, y)
            else:
                assert abs(centre - side) < 12, (x, y)
                if pid != "3665b":  # a slanted face is darker than a flat top
                    assert centre < 0.9 * flat, (x, y, centre, flat)


@pytest.mark.parametrize("pid", SLOPES)
def test_slanted_face_from_above_darkens_towards_the_low_edge(catalog, pid):
    for rot in ROTS:
        build, p = lone(catalog, pid, rot)
        low = catalog.low_side(p)
        f = R.view_frame(build.shape, "top")
        im = R.render_build(build, catalog, "top")
        w, d, h = catalog.footprint(p)
        slanted = [
            c
            for c in ((x, y) for x in range(p.x, p.x + w) for y in range(p.y, p.y + d))
            if c not in set(catalog.stud_cells(p))
        ]
        # the slanted cell nearest the low edge is darker than the one nearest the top
        ranked = sorted(slanted, key=lambda c, low=low: dot(c, low))
        lo_cell, hi_cell = ranked[-1], ranked[0]
        lo_pt = (lo_cell[0] + 0.5 + 0.3 * low[0], lo_cell[1] + 0.5 + 0.3 * low[1], h)
        hi_pt = (hi_cell[0] + 0.5 - 0.3 * low[0], hi_cell[1] + 0.5 - 0.3 * low[1], h)
        assert (
            sum(sample(im, *f.project([lo_pt])[0, :2]))
            < sum(sample(im, *f.project([hi_pt])[0, :2])) - 12
        ), (pid, rot)


@pytest.mark.parametrize("pid", SLOPES + ("3665b",))
@pytest.mark.parametrize("rot", ROTS)
def test_mirrored_views_show_the_mirror_image(catalog, pid, rot):
    build, _ = lone(catalog, pid, rot)
    for a, b in (("front", "back"), ("right", "left")):
        ma = plain(R.render_build(build, catalog, a, labels=False))
        mb = plain(R.render_build(build, catalog, b, labels=False))
        assert ma.shape == mb.shape
        assert (ma != mb[:, ::-1]).sum() <= 2, (a, b, (ma != mb[:, ::-1]).sum())


@pytest.mark.parametrize("pid", SLOPES + ("3665b",))
def test_wedge_in_iso_is_cut_away_and_turns_with_rot(catalog, pid):
    masks = {}
    for rot in ROTS:
        build, p = lone(catalog, pid, rot)
        w, d, h = catalog.footprint(p)
        colors = np.full(build.shape, EMPTY, dtype=np.int16)
        colors[catalog.cells(p)] = p.color
        box = Design(colors=colors, finish=np.full(colors.shape, FINISH_SMOOTH, np.uint8))
        mw = plain(R.render_build(build, catalog, "iso"))
        mb = plain(R.render_design(box, catalog, "iso"))
        assert mw.sum() < mb.sum() and (mw != mb).sum() > 30, (rot, mw.sum(), mb.sum())
        masks[rot] = mw
    for a, b in ((0, 180), (90, 270)):
        if masks[a].shape == masks[b].shape:
            assert (masks[a] != masks[b]).sum() > 30, (pid, a, b)


@pytest.mark.parametrize("rot", ROTS)
def test_inverted_slope_is_cut_away_underneath(catalog, rot):
    build, p = lone(catalog, "3665b", rot)
    low = catalog.low_side(p)
    assert low is not None
    for view in SIDE_VIEWS:
        if dot(PICTURE_RIGHT[view], low) == 0:
            continue
        f = R.view_frame(build.shape, view, labels=False)
        m = plain(R.render_build(build, catalog, view, labels=False))
        c0, c1, r0, r1 = body_box(f, catalog, p)
        cols = m[r0 : r1 + 1, c0 : c1 + 1]
        if dot(PICTURE_RIGHT[view], low) > 0:  # full end on the right: read from the left
            cols = cols[:, ::-1]
        # read from the full end (low side) to the thin end
        assert cols[:, 1].all() and cols[0].all()  # full column, and the whole top row
        assert not cols[-2, -2] and not cols[-1, -2]  # under the thin end: nothing
        heights = cols.sum(axis=0)
        assert heights[-1] <= 0.4 * (r1 - r0 + 1)
        assert (np.diff(heights) <= 1).all()


@pytest.mark.parametrize("pid", ROUNDS)
@pytest.mark.parametrize("rot", ROTS)
def test_round_parts_are_round_from_above(catalog, pid, rot):
    build, p = lone(catalog, pid, rot)
    w, d, h = catalog.footprint(p)
    f = R.view_frame(build.shape, "top", labels=False)
    m = plain(R.render_build(build, catalog, "top", labels=False))
    for cx, cy in ((p.x, p.y), (p.x + w, p.y), (p.x, p.y + d), (p.x + w, p.y + d)):
        ix = 0.08 if cx == p.x else -0.08
        iy = 0.08 if cy == p.y else -0.08
        col, row = f.project([[cx + ix, cy + iy, h]])[0, :2]
        assert not m[int(row), int(col)], (pid, rot, cx, cy)
    col, row = f.project([[p.x + w / 2, p.y + d / 2, h]])[0, :2]
    assert m[int(row), int(col)]
    # the outline is a circle: as wide as it is deep, and narrower along the diagonals
    rows, cols = np.nonzero(m)
    assert abs((rows.max() - rows.min()) - (cols.max() - cols.min())) <= 1
    assert m.sum() < 0.85 * (w * 16) * (d * 16) * 1.0


@pytest.mark.parametrize("pid", ROUNDS)
def test_round_parts_are_round_in_iso(catalog, pid):
    build, p = lone(catalog, pid)
    colors = np.full(build.shape, EMPTY, dtype=np.int16)
    colors[catalog.cells(p)] = p.color
    box = Design(colors=colors, finish=np.full(colors.shape, FINISH_SMOOTH, np.uint8))
    mr = plain(R.render_build(build, catalog, "iso"))
    mb = plain(R.render_design(box, catalog, "iso"))
    assert mr.sum() < 0.92 * mb.sum(), (mr.sum(), mb.sum())
    # the far corner of the box (top left of the iso picture) is cut away
    f = R.view_frame(build.shape, "iso")
    w, d, h = catalog.footprint(p)
    col, row = f.project([[p.x + 0.04, p.y + d - 0.04, h]])[0, :2]
    assert mb[int(row), int(col)] and not mr[int(row), int(col)]


def test_cone_tapers_from_the_side(catalog):
    for rot in ROTS:
        build, p = lone(catalog, "59900", rot)
        for view in SIDE_VIEWS:
            f = R.view_frame(build.shape, view, labels=False)
            m = plain(R.render_build(build, catalog, view, labels=False))
            c0, c1, r0, r1 = body_box(f, catalog, p)
            near_top = m[r0 + 2].sum()
            near_bottom = m[r1 - 3].sum()
            assert near_top < near_bottom - 3, (view, near_top, near_bottom)


@pytest.mark.parametrize(
    "pid", ("3070b", "3069b", "2431", "3068b", "87079", "98138", "14769", "4740")
)
def test_parts_without_studs_show_none(catalog, pid):
    for rot in (0, 90):
        build, p = lone(catalog, pid, rot)
        for view in SIDE_VIEWS:
            f = R.view_frame(build.shape, view, labels=False)
            m = plain(R.render_build(build, catalog, view, labels=False))
            _, _, r0, _ = body_box(f, catalog, p)
            assert m[r0 : r0 + 3].any() and not m[: r0 - 1].any(), view
        f = R.view_frame(build.shape, "top")
        im = R.render_build(build, catalog, "top")
        w, d, h = catalog.footprint(p)
        if pid == "4740":  # the dish has rings of its own
            continue
        mid = np.array([p.x + w / 2, p.y + d / 2])
        for x in range(p.x, p.x + w):
            for y in range(p.y, p.y + d):
                c = np.array([x + 0.5, y + 0.5])
                inwards = np.sign(mid - c) / max(1.0, float(np.abs(np.sign(mid - c)).sum()) ** 0.5)
                if not inwards.any():
                    inwards = np.array([1.0, 0.0])
                ring = sum(sample(im, *f.project([[*(c + 0.27 * inwards), h]])[0, :2]))
                inner = sum(sample(im, *f.project([[*(c + 0.1 * inwards), h]])[0, :2]))
                assert abs(ring - inner) < 12, (pid, x, y)


def test_studs_on_round_parts_and_slopes_are_drawn(catalog):
    for pid in ("3062b", "6141", "59900", "3040b"):
        build, p = lone(catalog, pid)
        w, d, h = catalog.footprint(p)
        (sx, sy), *_ = catalog.stud_cells(p)
        f = R.view_frame(build.shape, "top")
        im = R.render_build(build, catalog, "top")
        centre = sum(sample(im, *f.project([[sx + 0.5, sy + 0.5, h]])[0, :2]))
        ring = sum(sample(im, *f.project([[sx + 0.5 + 0.27, sy + 0.5, h]])[0, :2]))
        assert centre > ring + 30, pid
        f = R.view_frame(build.shape, "right")
        im = R.render_build(build, catalog, "right")
        _, row = f.project([[0, 0, h + 0.25]])[0, :2]
        col, _ = f.project([[0, sy + 0.5, 0]])[0, :2]
        assert drawn_mask(arr(im))[int(row), int(col)], pid


def test_a_part_on_a_slope_hides_its_stud(catalog):
    p = Placement("3039", RED, 0, 0, 0, 0)
    alone = Build((2, 2, 5), [p])
    covered = Build((2, 2, 5), [p, Placement("3069b", BLUE, 0, 1, 3, 0)])
    f = R.view_frame(alone.shape, "top")
    for build, stud in ((alone, True), (covered, False)):
        im = R.render_build(build, catalog, "top")
        centre = sum(sample(im, *f.project([[0.5, 1.5, 4]])[0, :2]))
        side = sum(sample(im, *f.project([[0.08, 1.5, 4]])[0, :2]))
        assert (centre > side + 20) == stud


@pytest.mark.parametrize("front", ("3062b", "3040b", "6143"))
def test_a_stud_behind_a_shaped_part_is_hidden(catalog, front):
    """Seen from the front, a blue brick's stud stands behind a red round brick or slope that
    is as tall as it is: none of it shows."""
    w, d, h = catalog.footprint(Placement(front, RED, 0, 0, 3, 0))
    parts = [Placement("3005", BLUE, 0, d, 0), Placement("3005", YELLOW, 0, 0, 0)]
    parts.append(Placement(front, colour_for(catalog, front), 0, 0, 3, 0))
    b = Build((w, d + 1, 7), parts)
    for s in (16, 32):
        assert blue_mask(arr(R.render_build(b, catalog, "front", px_per_stud=s))).sum() == 0
    # with only a stack of yellow plates and a tile in front, the blue stud shows above it
    stack = [Placement(pid, YELLOW, 0, 0, z) for z, pid in enumerate(("3024", "3024", "3070b"))]
    bare = Build(b.shape, parts[:1] + stack)
    assert blue_mask(arr(R.render_build(bare, catalog, "front"))).sum() > 20


def test_a_stud_behind_the_cut_away_of_a_wedge_is_drawn(catalog):
    """Seen from the right, a red 1x3 slope stands in front of a blue plate. Near its low lip
    the slope is lower than the plate's stud, so the stud shows above it."""
    b = Build((2, 3, 4), [Placement("3024", BLUE, 0, 0, 0), Placement("4286", RED, 1, 0, 0, 0)])
    f = R.view_frame(b.shape, "right", px_per_stud=32)
    im = arr(R.render_build(b, catalog, "right", px_per_stud=32))
    col, row = f.project([[0, 0.3, 1.3]])[0, :2]
    assert blue_mask(im[int(row), int(col)][None, None])[0, 0]
    col, row = f.project([[0, 2.5, 1.3]])[0, :2]  # where the slope is full height: red
    assert is_red(im[int(row), int(col)])


@pytest.mark.parametrize("above", ("3070b", "3062b", "3005"))
def test_a_stud_under_a_part_higher_up_is_hidden_from_above(catalog, above):
    """A blue brick's stud with a red part floating two plates above it: from above the red
    part's top covers the stud."""
    b = Build((1, 1, 9), [Placement("3005", BLUE, 0, 0, 0), Placement(above, RED, 0, 0, 5)])
    f = R.view_frame(b.shape, "top")
    im = R.render_build(b, catalog, "top")
    for dx in (0.0, 0.2, -0.2):
        assert is_red(sample(im, *f.project([[0.5 + dx, 0.5, 9]])[0, :2])), (above, dx)
    if above != "3062b":  # the round brick leaves the blue corners of the brick showing
        assert blue_mask(arr(im)).sum() == 0


def inverted_over_stud() -> Build:
    """A red inverted slope on a blue 1x2 brick: its thin end overhangs the brick's stud at
    y=0 with an open space under it."""
    return Build(
        (1, 2, 7), [Placement("3004", BLUE, 0, 0, 0, 90), Placement("3665b", RED, 0, 0, 3, 0)]
    )


def test_a_stud_under_the_open_end_of_an_inverted_slope_is_drawn(catalog):
    b = inverted_over_stud()
    assert catalog.low_side(b.parts[1]) == (0, 1)  # full at y=1, cut away over y=0
    for view in ("right", "left", "front"):
        f = R.view_frame(b.shape, view, px_per_stud=32)
        im = arr(R.render_build(b, catalog, view, px_per_stud=32))
        col, row = f.project([[0.5 if view == "front" else 0, 0.35, 3.25]])[0, :2]
        assert blue_mask(im[int(row), int(col)][None, None])[0, 0], (view, im[int(row), int(col)])
    # under the full end there is no stud: the slope sits on it
    f = R.view_frame(b.shape, "right", px_per_stud=32)
    im = arr(R.render_build(b, catalog, "right", px_per_stud=32))
    col, row = f.project([[0, 1.5, 3.25]])[0, :2]
    assert is_red(im[int(row), int(col)])
    # from above the slope's flat top hides it
    assert blue_mask(arr(R.render_build(b, catalog, "top"))).sum() == 0
    # iso shows more blue than with the full end over the stud as well
    full = Build(b.shape, [b.parts[0], Placement("3004", RED, 0, 0, 3, 90)])
    blue_iso = blue_mask(arr(R.render_build(b, catalog, "iso"))).sum()
    assert blue_iso > blue_mask(arr(R.render_build(full, catalog, "iso"))).sum() + 10


def test_a_stud_under_an_inverted_slope_detail_is_drawn_in_a_design(catalog):
    colors = np.full((1, 2, 7), EMPTY, dtype=np.int16)
    colors[:, :, 0:3] = BLUE
    d = Design(colors=colors, details=[Detail(part="3665b", color=RED, x=0, y=0, z=3)])
    f = R.view_frame(d.shape, "right", px_per_stud=32)
    im = arr(R.render_design(d, catalog, "right", px_per_stud=32))
    col, row = f.project([[0, 0.35, 3.25]])[0, :2]
    assert blue_mask(im[int(row), int(col)][None, None])[0, 0]
    col, row = f.project([[0, 1.5, 3.25]])[0, :2]
    assert is_red(im[int(row), int(col)])
    # and the Design looks like the Build of it
    b = inverted_over_stud()
    for view in R.VIEWS:
        assert (R.silhouette(d, catalog, view) == R.silhouette(b, catalog, view)).all(), view


def test_slopes_and_bricks_hide_each_other_by_depth(catalog):
    """Seen from the right: a red slope in front of a blue brick shows the brick above its
    slanted face; a red brick in front hides a blue slope completely."""
    slope_front = Build(
        (4, 2, 4), [Placement("3003", BLUE, 0, 0, 0), Placement("3039", RED, 2, 0, 0, 0)]
    )
    f = R.view_frame(slope_front.shape, "right")
    im = R.render_build(slope_front, catalog, "right")
    low_end = sample(im, *f.project([[4, 0.4, 2.6]])[0, :2])
    high_end = sample(im, *f.project([[4, 1.5, 1.5]])[0, :2])
    assert blue_mask(np.array([[low_end]]))[0, 0] and is_red(high_end)
    brick_front = Build(
        (4, 2, 4), [Placement("3039", BLUE, 0, 0, 0, 0), Placement("3003", RED, 2, 0, 0)]
    )
    assert blue_mask(arr(R.render_build(brick_front, catalog, "right"))).sum() == 0
    # in iso, the brick behind shows above the slope too
    im = arr(R.render_build(slope_front, catalog, "iso"))
    assert blue_mask(im).sum() > 100


def test_shaped_parts_line_up_with_box_parts(catalog):
    """Shaped parts are drawn in the same frame: a slope's high end and a brick beside it
    share the top edge, and the picture size does not change."""
    b = Build((4, 2, 4), [Placement("3003", BLUE, 0, 0, 0), Placement("3039", RED, 2, 0, 0, 0)])
    plain_b = Build((4, 2, 4), [Placement("3003", BLUE, 0, 0, 0), Placement("3003", RED, 2, 0, 0)])
    for view in R.VIEWS:
        assert R.render_build(b, catalog, view).size == R.render_build(plain_b, catalog, view).size
    f = R.view_frame(b.shape, "front", labels=False)
    m = plain(R.render_build(b, catalog, "front", labels=False))
    mp = plain(R.render_build(plain_b, catalog, "front", labels=False))
    # seen from the front (the low side) the slope covers exactly the brick's rectangle
    assert (m != mp).sum() == 0
    f = R.view_frame(b.shape, "right", labels=False)
    m = plain(R.render_build(b, catalog, "right", labels=False))
    c0, c1, r0, r1 = body_box(f, catalog, Placement("3003", BLUE, 2, 0, 0))
    assert m[r0, c1 - 2] and m[r1, c0]


def test_design_details_are_drawn_by_shape(catalog):
    colors = np.full((5, 4, 6), EMPTY, dtype=np.int16)
    colors[:, :, 0] = WHITE
    details = [
        Detail(part="14769", color=RED, x=0, y=0, z=1),
        Detail(part="3040b", color=RED, x=2, y=0, z=1, rot=0),
        Detail(part="6141", color=YELLOW, x=4, y=3, z=1),
    ]
    d = Design(colors=colors, details=details)
    f = R.view_frame(d.shape, "top")
    im = R.render_design(d, catalog, "top")
    assert is_red(sample(im, *f.cell_center(0, 0, 1)))
    corner = sample(im, *f.project([[0.15, 0.15, 2]])[0, :2])
    assert not is_red(corner) and sum(corner) > 500  # the white floor shows at the corner
    # the slope detail falls to the front: from the right its columns shrink towards -y
    f = R.view_frame(d.shape, "right", labels=False)
    m = plain(R.render_design(d, catalog, "right", labels=False))
    c0, c1, r0, r1 = body_box(f, catalog, Placement("3040b", RED, 2, 0, 1))
    heights = m[r0 : r1 + 1, c0 : c1 + 1].sum(axis=0)
    assert heights[0] < heights[-1] - 8
    # the round plate carries its stud
    f = R.view_frame(d.shape, "top")
    centre = sum(sample(im, *f.project([[4.5, 3.5, 2]])[0, :2]))
    ring = sum(sample(im, *f.project([[4.77, 3.5, 2]])[0, :2]))
    assert centre > ring + 30


def test_box_parts_draw_as_before_next_to_shaped_ones(catalog):
    """A brick's own pixels do not change when a slope stands elsewhere in the grid."""
    brick = Placement("3001", BLUE, 0, 0, 0)
    alone = Build((6, 4, 6), [brick])
    both = Build((6, 4, 6), [brick, Placement("3039", RED, 4, 2, 0, 90)])
    for view in R.VIEWS:
        a = arr(R.render_build(alone, catalog, view))
        b = arr(R.render_build(both, catalog, view))
        blue = blue_mask(a)
        assert blue.sum() > 100
        assert (a[blue] == b[blue]).all(), view


def test_iso_shades_a_slanted_face_between_top_and_sides(catalog):
    """In iso a slope's flat sides take exactly the box shades, and its slanted face has a
    shade of its own: lighter than the front and the right side, unlike the flat top."""
    slope = Build((4, 4, 5), [Placement("3039", RED, 1, 1, 0, 0)])
    box = Build((4, 4, 5), [Placement("3003", RED, 1, 1, 0, 0)])
    f = R.view_frame(slope.shape, "iso")
    si, bi = R.render_build(slope, catalog, "iso"), R.render_build(box, catalog, "iso")

    def at(im, pt):
        return np.array(sample(im, *f.project([pt])[0, :2]), dtype=int)

    right, top = (3.0, 2.0, 1.5), (2.0, 2.2, 3.0)
    assert np.abs(at(si, right) - at(bi, right)).sum() <= 3  # same right side shade
    assert np.abs(at(si, top) - at(bi, top)).sum() <= 3  # same flat top shade
    slant = at(si, (2.0, 1.5, 1.75))
    assert slant.sum() > at(bi, (2.0, 1.0, 1.5)).sum() + 20  # lighter than the box front
    assert slant.sum() > at(si, right).sum() + 60
    assert np.abs(slant - at(si, top)).sum() >= 8  # and told apart from the flat top


def outline_rows(im, col: int, r0: int, r1: int) -> list[int]:
    """Rows in [r0, r1] of column col drawn markedly darker than both neighbours."""
    a = arr(im).sum(axis=2)
    return [r for r in range(r0, r1 + 1) if a[r, col] < 0.8 * min(a[r - 1, col], a[r + 1, col])]


def test_the_crease_between_flat_top_and_slanted_face_is_outlined_from_above(catalog):
    for rot in ROTS:
        build, p = lone(catalog, "3039", rot)
        low = catalog.low_side(p)
        f = R.view_frame(build.shape, "top")
        im = R.render_build(build, catalog, "top")
        a = arr(im).sum(axis=2)
        # walk from the high edge to the low edge, half-way between the two studs
        line = []
        for k in range(1, 64):
            t = k / 64 * 2
            c = (p.x + 1 - low[0] * (1 - t), p.y + 1 - low[1] * (1 - t))
            col, row = f.project([[c[0], c[1], 3]])[0, :2]
            line.append(int(a[int(row), int(col)]))
        mid = len(line) // 2  # the crease is at the middle of the part
        window = line[mid - 4 : mid + 4]
        assert min(window) < 0.8 * min(line[mid - 12], line[mid + 12]), (rot, line)


def test_a_round_side_outlines_like_a_box_from_the_side(catalog):
    """Seen from the side a round brick, and the bands of a dish, have no outline inside
    them: only around the part."""
    for pid in ("3062b", "6143", "4740", "59900"):
        build, p = lone(catalog, pid)
        f = R.view_frame(build.shape, "front", px_per_stud=32)
        im = R.render_build(build, catalog, "front", px_per_stud=32)
        c0, c1, r0, r1 = body_box(f, catalog, p)
        sx, _ = catalog.stud_cells(p)[0] if catalog.stud_cells(p) else (p.x, p.y)
        for x in {p.x + catalog.footprint(p)[0] / 2, sx + 0.5}:
            col = int(f.project([[x, 0, 0]])[0, 0])
            assert outline_rows(im, col, r0 + 1, r1 - 1) == [], (pid, x)


def test_upto_step_leaves_out_later_shaped_parts(catalog):
    parts = [
        Placement("3001", BLUE, 0, 0, 0, 0, 1),
        Placement("3039", RED, 0, 0, 3, 0, 2),
        Placement("3062b", RED, 3, 1, 3, 0, 2),
        Placement("6143", RED, 2, 0, 6, 0, 3),
    ]
    b = Build((4, 2, 10), parts)
    for view in R.VIEWS:
        first = arr(R.render_build(b, catalog, view, upto_step=1))
        only = arr(R.render_build(Build(b.shape, parts[:1]), catalog, view))
        assert (first == only).all(), view
        assert red_mask(first).sum() == 0
        second = arr(R.render_build(b, catalog, view, upto_step=2))
        assert (second == arr(R.render_build(Build(b.shape, parts[:3]), catalog, view))).all()
        assert red_mask(second).sum() > 30


def test_leaving_out_hidden_shaped_parts_changes_no_pixel(catalog, monkeypatch):
    """Straight views skip shaped parts that cannot show (behind an identical part, or behind
    box cells); the pictures are exactly those drawn with every part."""
    # a wall of identical round bricks, and a stack of identical round plates
    parts = [Placement("3062b", RED, x, y, 6, 0) for x in range(0, 5, 2) for y in range(0, 5, 2)]
    parts += [Placement("6141", YELLOW, 6, 6, z) for z in range(3)]
    # a round brick half behind a box (front view), and a slope wholly behind boxes
    parts += [Placement("3005", BLUE, 0, 0, 0), Placement("6143", YELLOW, 0, 3, 0)]
    parts += [Placement("3005", BLUE, 3, 0, 0), Placement("3005", BLUE, 4, 0, 0)]
    parts += [Placement("3039", RED, 3, 2, 0, 0)]
    # a narrow cone in front of a round brick of the same size: the brick shows around it
    parts += [Placement("59900", YELLOW, 5, 0, 0), Placement("3062b", RED, 5, 3, 0)]
    # in line with the wall seen from the front, but beside it seen from above
    parts += [Placement("3062b", RED, 4, 6, 0)]
    # two identical inverted slopes in a line, and a slope seen end-on
    parts += [Placement("3665b", RED, 6, 0, 6, 0), Placement("3665b", RED, 6, 3, 6, 0)]
    parts += [Placement("4286", GREEN, 0, 6, 3, 90)]
    b = Build((7, 7, 10), parts)
    scene = R._build_scene(b, catalog, None)
    assert len(scene.inst_key) == len([p for p in parts if not p.part.startswith("300")])
    hidden = {}
    for view in STRAIGHT:
        cells = R._to_view_axes(scene.cells, view)
        hidden[view] = R._hidden_parts(scene, view, R._first_hit(cells)[1])
    assert hidden["front"].sum() >= 8 and hidden["top"].sum() >= 2  # the test does skip parts
    culled = {
        (v, s): R.render_build(b, catalog, v, px_per_stud=s).tobytes()
        for v in STRAIGHT
        for s in (3, 16, 21)
    }
    monkeypatch.setattr(
        R, "_hidden_parts", lambda scene, view, box_depth: np.zeros(len(scene.inst_key), bool)
    )
    for (v, s), pic in culled.items():
        assert R.render_build(b, catalog, v, px_per_stud=s).tobytes() == pic, (v, s)


def test_shaped_output_is_deterministic(catalog):
    parts = [
        Placement(pid, colour_for(catalog, pid), 3 * i % 12, 3 * (i // 4), 0, (90 * i) % 360)
        for i, pid in enumerate(SLOPES + ROUNDS + ("3665b",))
    ]
    b = Build((12, 12, 5), parts)
    for view in R.VIEWS:
        assert (
            R.render_build(b, catalog, view).tobytes() == R.render_build(b, catalog, view).tobytes()
        )


# ---- stage 2: silhouette ---------------------------------------------------------------------


@pytest.mark.parametrize("view", R.VIEWS)
def test_silhouette_of_box_seed_and_its_build_are_identical(catalog, view):
    box = ((0, 0, 0), (4, 2, 6))
    offset = (1, 1, 1)
    seed = seed_of(box)
    b = Build((6, 4, 9), [Placement("3001", RED, 1, 1, 1), Placement("3001", BLUE, 1, 1, 4)])
    s_seed = R.silhouette(seed, catalog, view, grid_shape=b.shape, seed_offset=offset)
    s_build = R.silhouette(b, catalog, view)
    f = R.view_frame(b.shape, view, px_per_stud=8, labels=False)
    assert s_seed.shape == s_build.shape == (f.height, f.width)
    assert s_seed.dtype == bool and s_seed.sum() > 50
    if view == "iso":
        assert (s_seed != s_build).sum() <= 0.01 * s_seed.sum()
    else:
        assert (s_seed == s_build).all()
    # and the Design of those cells gives the same outline
    d = design_of(b.shape, offset, box)
    assert (R.silhouette(d, catalog, view) == s_build).all()


def test_silhouette_follows_the_scale_and_leaves_out_studs(catalog):
    b = one_brick((1, 1, 0), shape=(3, 3, 6))
    for s in (5, 8, 16):
        sil = R.silhouette(b, catalog, "front", px_per_stud=s)
        f = R.view_frame(b.shape, "front", px_per_stud=s, labels=False)
        assert sil.shape == (f.height, f.width)
        rows = np.nonzero(sil.any(axis=1))[0]
        _, top = f.project([[0, 0, 3]])[0, :2]
        assert rows.min() >= int(top) - 1  # no stud bumps above the top face
        # exactly the brick's body: s columns by 1.2 s rows (sampled at pixel centres)
        assert sil.sum() in (s * math.floor(1.2 * s), s * math.ceil(1.2 * s)), (s, sil.sum())


def test_wedge_build_has_a_smaller_side_silhouette(catalog):
    base = [Placement("3001", RED, 0, 0, 0)]
    brick = Build((4, 2, 6), base + [Placement("3003", RED, 0, 0, 3)])
    wedge = Build((4, 2, 6), base + [Placement("3039", RED, 0, 0, 3, 0)])
    for view in ("right", "left"):
        sb = R.silhouette(brick, catalog, view)
        sw = R.silhouette(wedge, catalog, view)
        assert sw.sum() < sb.sum() - 20
        assert not (sw & ~sb).any()  # the wedge lies inside the brick's outline
    assert (
        R.silhouette(wedge, catalog, "front").sum() == R.silhouette(brick, catalog, "front").sum()
    )


def test_silhouette_errors_are_plain(catalog):
    seed = seed_of(((0, 0, 0), (2, 2, 3)))
    with pytest.raises(ValueError, match="grid"):
        R.silhouette(seed, catalog, "front")
    with pytest.raises(ValueError, match="seed, a Design or a Build"):
        R.silhouette("not a model", catalog, "front")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="Unknown view"):
        R.silhouette(one_brick((0, 0, 0)), catalog, "under")


# ---- stage 2: the rough row ------------------------------------------------------------------


def yellow_mask(a: np.ndarray) -> np.ndarray:
    return (a[..., 0] > 150) & (a[..., 1] > 120) & (a[..., 2] < 80)


def test_compare_sheet_with_rough_has_three_rows_in_order(catalog):
    d = shapes.box(4, 2, 2, colour=RED)
    two = [Placement("3001", RED, 0, 0, 0, 0, 1), Placement("3001", RED, 0, 0, 3, 0, 2)]
    b = Build(d.shape, two)
    rough = Build(d.shape, [Placement(p.part, YELLOW, p.x, p.y, p.z, p.rot, p.step) for p in two])
    sheet = arr(R.compare_sheet(blue_seed(), d, b, catalog, rough=rough))
    blue_rows = np.nonzero(blue_mask(sheet).any(axis=1))[0]
    yellow_rows = np.nonzero(yellow_mask(sheet).any(axis=1))[0]
    red_rows = np.nonzero(red_mask(sheet).any(axis=1))[0]
    assert len(blue_rows) and len(yellow_rows) and len(red_rows)
    assert blue_rows.max() < yellow_rows.min() and yellow_rows.max() < red_rows.min()
    # same columns and same scale in the rough and build rows
    ycols = np.nonzero(yellow_mask(sheet).any(axis=0))[0]
    rcols = np.nonzero(red_mask(sheet).any(axis=0))[0]
    assert ycols.min() == rcols.min() and ycols.max() == rcols.max()
    assert (
        abs(int(yellow_mask(sheet).sum()) - int(red_mask(sheet).sum()))
        < 0.1 * red_mask(sheet).sum()
    )
    # the extra row makes the sheet taller
    two_rows = arr(R.compare_sheet(blue_seed(), d, b, catalog))
    assert sheet.shape[0] > two_rows.shape[0] * 1.3
    # each row's pictures are exactly the single renders
    views = ("front", "right", "top", "iso")
    items = [(f"seed - {v}", R.render_seed(blue_seed(), v, d.shape)) for v in views]
    items += [(f"rough - {v}", R.render_build(rough, catalog, v)) for v in views]
    items += [(f"build - {v}", R.render_build(b, catalog, v)) for v in views]
    title = "Seed (top row), rough conversion (middle row) and build (bottom row)"
    expected = R.contact_sheet(items, columns=4, title=title)
    assert R.compare_sheet(blue_seed(), d, b, catalog, rough=rough).tobytes() == expected.tobytes()


def test_compare_sheet_rough_captions_and_titles(catalog):
    d = shapes.box(2, 2, 1, colour=RED)
    b = Build(d.shape, [Placement("3003", RED, 0, 0, 0)])
    views = ("front", "top")
    items, title = R._compare_items(
        blue_seed((2, 2, 3)), d, b, catalog, views=views, px_per_stud=16, rough=b
    )
    assert [c for c, _ in items] == [
        "seed - front",
        "seed - top",
        "rough - front",
        "rough - top",
        "build - front",
        "build - top",
    ]
    assert "rough" in title.lower() and title.lower().index("seed") < title.lower().index("rough")
    for (_, a), (_, c) in zip(items[2:4], items[4:6], strict=True):
        assert a.tobytes() == c.tobytes()  # same build: same picture, same scale
    items, title = R._compare_items(None, d, None, catalog, views=views, px_per_stud=16, rough=b)
    assert [c for c, _ in items] == [
        "rough - front",
        "rough - top",
        "design - front",
        "design - top",
    ]
    assert title.lower().startswith("rough")


def test_compare_sheet_without_rough_is_unchanged(catalog):
    d = shapes.box(4, 2, 2, colour=RED)
    b = Build(d.shape, [Placement("3001", RED, 0, 0, 0, 0, 1), Placement("3001", RED, 0, 0, 3)])
    views = ("front", "right", "top", "iso")
    for seed, build in ((blue_seed(), b), (blue_seed(), None), (None, b)):
        # without rough the sheet is the seed row (if any) above the build or design row,
        # each picture exactly the single render, as before stage 2
        items = []
        if seed is not None:
            items += [(f"seed - {v}", R.render_seed(seed, v, d.shape)) for v in views]
        if build is not None:
            items += [(f"build - {v}", R.render_build(build, catalog, v)) for v in views]
        else:
            items += [(f"design - {v}", R.render_design(d, catalog, v)) for v in views]
        what = "build" if build is not None else "design"
        title = f"Seed (top row) and {what} (bottom row)" if seed is not None else "Build"
        expected = R.contact_sheet(items, columns=4, title=title).tobytes()
        assert R.compare_sheet(seed, d, build, catalog).tobytes() == expected
        assert R.compare_sheet(seed, d, build, catalog, rough=None).tobytes() == expected
    items, title = R._compare_items(
        blue_seed(),
        d,
        b,
        catalog,
        views=("front", "right", "top", "iso"),
        px_per_stud=16,
        rough=None,
    )
    assert title == "Seed (top row) and build (bottom row)" and len(items) == 8


def test_compare_sheet_with_shaped_parts_is_fast(catalog):
    nx, ny, courses = 25, 20, 10
    kinds = ("3005", "3062b", "54200", "3005", "59900", "3070b", "98138", "6141")
    parts = []
    for x in range(nx):
        for y in range(ny):
            for c in range(courses):
                pid = (
                    kinds[(x + 2 * y + c) % len(kinds)]
                    if c == courses - 1
                    else ("3062b" if (x + y + c) % 3 == 0 else "3005")
                )
                parts.append(
                    Placement(pid, colour_for(catalog, pid), x, y, 3 * c, 90 * (x % 4), c + 1)
                )
    assert len(parts) == 5000
    b = Build((nx, ny, 3 * courses), parts)
    m = trimesh.creation.icosphere(subdivisions=4, radius=80.0)
    v = m.vertices - m.vertices.min(axis=0)
    seed = Seed(vertices=v * np.array([200 / 160, 160 / 160, 96 / 160]), faces=np.asarray(m.faces))
    d = Design(colors=np.full(b.shape, RED, dtype=np.int16))
    start = time.perf_counter()
    sheet = R.compare_sheet(seed, d, b, catalog, rough=b)
    elapsed = time.perf_counter() - start
    assert sheet.width > 0
    assert elapsed < 5.0, elapsed


def test_compare_sheet_of_5000_round_parts_is_fast(catalog):
    """A hard case: every part is a 2x2 dish (many slanted facets), with a rough row."""
    parts = [
        Placement("4740", RED, 2 * (i % 25), 2 * ((i // 25) % 20), i // 500, 0, 1)
        for i in range(5000)
    ]
    b = Build((50, 40, 10), parts)
    d = Design(colors=np.full(b.shape, EMPTY, dtype=np.int16))
    start = time.perf_counter()
    sheet = R.compare_sheet(None, d, b, catalog, rough=Build(b.shape, list(parts)))
    elapsed = time.perf_counter() - start
    assert sheet.width > 0
    assert elapsed < 5.0, elapsed
