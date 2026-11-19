"""Tests for bricksnap.design: the edit operations, the log, replay, shape masks, OP_SCHEMA."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
from typing import Any

import numpy as np
import pytest
from shapes import box

from bricksnap.design import (
    OP_SCHEMA,
    OPS,
    ROTATIONS,
    SHAPE_OPS,
    OpResult,
    apply_ops,
    replay,
    shape_mask,
    validate_op,
)
from bricksnap.types import (
    EMPTY,
    FINISH_NAMES,
    FINISH_SLOPED,
    FINISH_SMOOTH,
    FINISH_STUDS,
    Design,
    Detail,
    Placement,
)

RED, ORANGE, BLUE, GREY = 4, 25, 1, 71


def B(lo, hi) -> dict[str, Any]:
    return {"type": "box", "min": list(lo), "max": list(hi)}


def E(center, radius) -> dict[str, Any]:
    def as_list(v):
        return list(v) if isinstance(v, list | tuple) else v

    return {"type": "ellipsoid", "center": as_list(center), "radius": as_list(radius)}


def add(shape, color=RED) -> dict[str, Any]:
    return {"op": "add", "shape": shape, "color": color}


def paint(shape, color=RED) -> dict[str, Any]:
    return {"op": "paint", "shape": shape, "color": color}


def remove(shape) -> dict[str, Any]:
    return {"op": "remove", "shape": shape}


def snapshot(d: Design) -> tuple[bytes, bytes, str]:
    assert d.finish is not None
    return d.colors.tobytes(), d.finish.tobytes(), json.dumps(d.log)


def half_box() -> Design:
    """A 6 x 5 x 9 grid with the bottom 3 plates filled grey and the rest empty."""
    colors = np.full((6, 5, 9), EMPTY, dtype=np.int16)
    colors[:, :, :3] = GREY
    return Design(colors=colors)


def one(design: Design, op: Any, catalog) -> OpResult:
    (result,) = apply_ops(design, [op], catalog)
    return result


def rejected(design: Design, op: Any, catalog) -> str:
    """Apply ``op``, check it was rejected without touching the design, return the message."""
    before = snapshot(design)
    result = one(design, op, catalog)
    assert not result.applied
    assert result.cells_changed == 0
    assert snapshot(design) == before, "a rejected operation changed the design"
    assert "Traceback" not in result.message
    return result.message


# ---- shape_mask: boxes ----------------------------------------------------------------------


def test_box_mask_is_inclusive():
    m = shape_mask(B((1, 2, 3), (2, 2, 5)), (6, 5, 9))
    assert m.shape == (6, 5, 9) and m.dtype == bool
    expected = np.zeros((6, 5, 9), dtype=bool)
    expected[1:3, 2:3, 3:6] = True
    assert np.array_equal(m, expected)


def test_single_cell_box():
    m = shape_mask(B((0, 0, 0), (0, 0, 0)), (3, 3, 3))
    assert m.sum() == 1 and m[0, 0, 0]


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("side", ["low", "high"])
def test_box_clipped_at_each_face(axis, side):
    grid = (6, 5, 9)
    lo, hi = [1, 1, 1], [3, 3, 3]
    if side == "low":
        lo[axis] = -4
    else:
        hi[axis] = grid[axis] + 7
    m = shape_mask(B(lo, hi), grid)
    expected = np.zeros(grid, dtype=bool)
    sl = [slice(1, 4)] * 3
    sl[axis] = slice(0, 4) if side == "low" else slice(1, grid[axis])
    expected[tuple(sl)] = True
    assert np.array_equal(m, expected)


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("side", ["low", "high"])
def test_box_entirely_outside_each_face_gives_empty_mask(axis, side):
    grid = (6, 5, 9)
    lo, hi = [1, 1, 1], [3, 3, 3]
    if side == "low":
        lo[axis], hi[axis] = -5, -1
    else:
        lo[axis], hi[axis] = grid[axis], grid[axis] + 3
    assert not shape_mask(B(lo, hi), grid).any()


def test_box_covering_more_than_the_grid_is_the_whole_grid():
    assert shape_mask(B((-100, -100, -100), (10**12, 10**12, 10**12)), (4, 3, 2)).all()


def test_box_accepts_whole_floats_and_tuples():
    a = shape_mask({"type": "box", "min": (0.0, 1, 2), "max": [2, 3.0, 4]}, (5, 5, 5))
    b = shape_mask(B((0, 1, 2), (2, 3, 4)), (5, 5, 5))
    assert np.array_equal(a, b)


# ---- shape_mask: ellipsoids -----------------------------------------------------------------


def brute_ellipsoid(center, radius, grid) -> np.ndarray:
    out = np.zeros(grid, dtype=bool)
    for x in range(grid[0]):
        for y in range(grid[1]):
            for z in range(grid[2]):
                d = sum(
                    ((p - c) / r) ** 2 for p, c, r in zip((x, y, z), center, radius, strict=True)
                )
                out[x, y, z] = d <= 1 + 1e-9
    return out


def test_ellipsoid_integer_centre():
    m = shape_mask(E((4, 4, 4), (1, 1, 1)), (9, 9, 9))
    assert m.sum() == 7  # centre plus its six neighbours
    assert m[4, 4, 4] and m[3, 4, 4] and m[5, 4, 4] and m[4, 4, 5]
    assert not m[3, 3, 4]


def test_ellipsoid_radius_half_is_one_cell():
    m = shape_mask(E((2, 3, 1), (0.5, 0.5, 0.5)), (5, 5, 5))
    assert m.sum() == 1 and m[2, 3, 1]


def test_ellipsoid_fractional_centre_between_two_cells():
    # centre halfway between x = 1 and x = 2; both are exactly on the surface
    m = shape_mask(E((1.5, 2, 2), (0.5, 0.5, 0.5)), (5, 5, 5))
    assert m.sum() == 2 and m[1, 2, 2] and m[2, 2, 2]


def test_ellipsoid_fractional_centre_and_radius_match_the_formula():
    rng = random.Random(7)
    grid = (9, 8, 12)
    for _ in range(40):
        center = [rng.uniform(-2, g + 2) for g in grid]
        radius = [rng.uniform(0.5, 4.5) for _ in grid]
        m = shape_mask(E(center, radius), grid)
        assert np.array_equal(m, brute_ellipsoid(center, radius, grid)), (center, radius)


def test_ellipsoid_surface_cells_survive_rounding():
    # ((2 - 1.4) / 0.6) ** 2 is 1.0000000000000004 in floating point; x = 2 is on the surface
    m = shape_mask(E((1.4, 0, 0), (0.6, 0.5, 0.5)), (4, 1, 1))
    assert m[:, 0, 0].tolist() == [False, True, True, False]


def test_ellipsoid_elongated_in_z():
    m = shape_mask(E((2, 2, 5), (1, 1, 2.5)), (5, 5, 11))
    assert m[2, 2, 3] and m[2, 2, 7] and not m[2, 2, 2] and not m[2, 2, 8]


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("side", ["low", "high"])
def test_ellipsoid_clipped_at_each_face(axis, side):
    grid = (7, 6, 8)
    center = [3.0, 3.0, 4.0]
    center[axis] = 0.0 if side == "low" else grid[axis] - 1.0
    radius = (2.0, 2.0, 2.0)
    m = shape_mask(E(center, radius), grid)
    assert np.array_equal(m, brute_ellipsoid(center, radius, grid))
    assert 0 < m.sum() < 33  # a full radius-2 ball has 33 cells; this one lost a part


def test_ellipsoid_entirely_outside_gives_empty_mask():
    assert not shape_mask(E((-5, 2, 2), (2, 2, 2)), (5, 5, 5)).any()
    assert not shape_mask(E((2, 2, 30.5), (1, 1, 1)), (5, 5, 5)).any()


def test_huge_ellipsoid_fills_the_grid():
    assert shape_mask(E((0, 0, 0), (1e6, 1e6, 1e6)), (4, 4, 4)).all()


def test_shape_mask_raises_value_error_on_malformed_shape():
    with pytest.raises(ValueError, match="Unknown shape type"):
        shape_mask({"type": "cone"}, (3, 3, 3))
    with pytest.raises(ValueError, match='missing "max"'):
        shape_mask({"type": "box", "min": [0, 0, 0]}, (3, 3, 3))
    with pytest.raises(ValueError, match="at least 0.5"):
        shape_mask(E((1, 1, 1), (0.4, 1, 1)), (3, 3, 3))
    with pytest.raises(ValueError, match="min is greater than its max"):
        shape_mask(B((2, 0, 0), (1, 0, 0)), (3, 3, 3))


# ---- applying: the happy path ---------------------------------------------------------------


def test_add_fills_only_empty_cells(catalog):
    d = half_box()
    r = one(d, add(B((0, 0, 2), (1, 0, 4)), ORANGE), catalog)
    assert r.applied and r.op == "add" and r.index == 0
    assert r.cells_changed == 4  # z 3 and 4 were empty; z 2 was already filled
    assert d.colors[0, 0, 2] == GREY
    assert (d.colors[0:2, 0, 3:5] == ORANGE).all()
    assert "Added 4 cells of Orange (25)" in r.message


def test_paint_recolours_only_filled_cells(catalog):
    d = half_box()
    r = one(d, paint(B((0, 0, 1), (0, 0, 5)), BLUE), catalog)
    assert r.applied and r.cells_changed == 2
    assert d.colors[0, 0, 1] == BLUE and d.colors[0, 0, 2] == BLUE
    assert d.colors[0, 0, 3] == EMPTY
    assert "Painted 2 cells Blue (1)" in r.message


def test_paint_counts_only_cells_whose_colour_changes(catalog):
    d = half_box()
    one(d, paint(B((0, 0, 0), (0, 0, 0)), RED), catalog)
    r = one(d, paint(B((0, 0, 0), (1, 0, 0)), RED), catalog)
    assert r.applied and r.cells_changed == 1


def test_remove_empties_filled_cells(catalog):
    d = half_box()
    r = one(d, remove(B((0, 0, 0), (5, 4, 0))), catalog)
    assert r.applied and r.cells_changed == 30
    assert (d.colors[:, :, 0] == EMPTY).all()
    assert (d.colors[:, :, 1:3] == GREY).all()
    assert "Removed 30 cells" in r.message


def test_remove_may_leave_a_single_cell(catalog):
    d = half_box()
    r = one(d, remove(B((0, 0, 0), (5, 4, 2))), catalog)
    assert not r.applied
    r = one(d, remove(E((2.5, 2, 1), (10, 10, 10))), catalog)
    assert not r.applied  # the ellipsoid covers everything too
    r = one(d, remove(B((1, 0, 0), (5, 4, 2))), catalog)
    assert r.applied and int(d.filled.sum()) == 15  # the x = 0 slab is left
    r = one(d, remove(B((0, 0, 0), (0, 4, 2))), catalog)
    assert not r.applied and "remove all 15 filled cells" in r.message
    r = one(d, remove(B((0, 0, 1), (0, 4, 2))), catalog)
    r = one(d, remove(B((0, 1, 0), (0, 4, 0))), catalog)
    assert r.applied and int(d.filled.sum()) == 1 and d.colors[0, 0, 0] == GREY


def test_ellipsoid_operations(catalog):
    d = half_box()
    r = one(d, add(E((3, 2, 4), (1, 1, 1)), ORANGE), catalog)
    assert r.applied and r.cells_changed == 7
    r = one(d, paint(E((3, 2, 4), (0.5, 0.5, 0.5)), RED), catalog)
    assert r.applied and r.cells_changed == 1 and d.colors[3, 2, 4] == RED


def test_add_and_remove_reset_finish_and_paint_keeps_it(catalog):
    d = half_box()
    assert d.finish is not None
    d.finish[:, :, :] = FINISH_SMOOTH
    one(d, paint(B((0, 0, 0), (0, 0, 0)), RED), catalog)
    assert d.finish[0, 0, 0] == FINISH_SMOOTH
    one(d, add(B((0, 0, 3), (0, 0, 3))), catalog)
    assert d.finish[0, 0, 3] == FINISH_STUDS
    one(d, remove(B((1, 0, 2), (1, 0, 2))), catalog)
    assert d.finish[1, 0, 2] == FINISH_STUDS
    assert d.finish[2, 0, 2] == FINISH_SMOOTH


def test_clipped_shape_is_applied_and_says_so(catalog):
    d = half_box()
    r = one(d, add(B((4, 3, 7), (9, 9, 20))), catalog)
    assert r.applied and r.cells_changed == 2 * 2 * 2
    assert "outside the grid (x 0..5, y 0..4, z 0..8)" in r.message
    r = one(d, add(B((0, 0, 3), (0, 0, 3))), catalog)
    assert "outside" not in r.message


def test_colour_written_as_whole_float_is_accepted(catalog):
    d = half_box()
    r = one(d, add(B((0, 0, 3), (0, 0, 3)), 4.0), catalog)
    assert r.applied and d.colors[0, 0, 3] == 4


def test_transparent_colours_are_allowed(catalog):
    d = half_box()
    assert catalog.colours[47].transparent
    assert one(d, add(B((0, 0, 3), (0, 0, 3)), 47), catalog).applied


# ---- operations that change nothing ---------------------------------------------------------


def test_add_where_everything_is_filled(catalog):
    d = half_box()
    before = snapshot(d)
    r = one(d, add(B((0, 0, 0), (2, 2, 2))), catalog)
    assert not r.applied and r.cells_changed == 0
    assert "already filled" in r.message and '"paint"' in r.message
    assert not r.message.startswith("Rejected")
    assert snapshot(d) == before


def test_remove_where_everything_is_empty(catalog):
    d = half_box()
    before = snapshot(d)
    r = one(d, remove(B((0, 0, 5), (2, 2, 8))), catalog)
    assert not r.applied and r.cells_changed == 0
    assert "every cell inside that box [0, 0, 5]..[2, 2, 8] is already empty" in r.message
    assert snapshot(d) == before


def test_paint_where_everything_is_empty(catalog):
    d = half_box()
    r = one(d, paint(B((0, 0, 5), (2, 2, 8))), catalog)
    assert not r.applied and "is empty" in r.message and '"add"' in r.message
    assert d.log == []


def test_paint_with_the_same_colour(catalog):
    d = half_box()
    r = one(d, paint(B((0, 0, 0), (2, 2, 2)), GREY), catalog)
    assert not r.applied and "already Light Bluish Grey (71)" in r.message
    assert d.log == []


# ---- rejections -----------------------------------------------------------------------------


def test_rejects_non_object_operation(catalog):
    d = half_box()
    msg = rejected(d, "paint it red", catalog)
    assert msg.startswith("Rejected:") and "must be an object" in msg
    assert one(d, ["add"], catalog).op == ""


def test_rejects_missing_op(catalog):
    msg = rejected(half_box(), {"shape": B((0, 0, 0), (1, 1, 1)), "color": 4}, catalog)
    assert 'missing "op"' in msg and '"add"' in msg and '"remove"' in msg and '"paint"' in msg


def test_rejects_unknown_op_with_suggestion(catalog):
    d = half_box()
    r = one(d, {"op": "paints", "shape": B((0, 0, 0), (0, 0, 0)), "color": 4}, catalog)
    assert r.op == "paints" and not r.applied
    assert 'Unknown op "paints"' in r.message and 'Did you mean "paint"?' in r.message
    msg = rejected(d, {"op": "fill", "shape": B((0, 0, 0), (0, 0, 0)), "color": 4}, catalog)
    assert 'Unknown op "fill"' in msg and "fill empty cells" in msg
    msg = rejected(d, {"op": 3, "shape": B((0, 0, 0), (0, 0, 0)), "color": 4}, catalog)
    assert "Unknown op 3" in msg
    assert one(d, {"op": 3}, catalog).op == ""


def test_non_ascii_text_is_echoed_as_written(catalog):
    d = half_box()
    msg = rejected(d, {"op": "añadir", "shape": B((0, 0, 0), (0, 0, 0)), "color": 4}, catalog)
    assert 'Unknown op "añadir"' in msg and "\\u" not in msg
    msg = rejected(d, add(B((0, 0, 0), (0, 0, 0)), "rouge é"), catalog)
    assert '"rouge é"' in msg and "\\u" not in msg
    long = "é" * 100
    msg = rejected(d, {"op": long, "shape": B((0, 0, 0), (0, 0, 0)), "color": 4}, catalog)
    assert f'Unknown op "{"é" * 56}...' in msg


def test_shortened_value_never_ends_in_half_an_escape(catalog):
    # Control characters are still shown as escapes; the cut must not split one.
    d = half_box()
    for pad in range(8):
        name = "a" * pad + "\x01" * 40
        msg = rejected(d, {"op": name, "shape": B((0, 0, 0), (0, 0, 0)), "color": 4}, catalog)
        shown = msg.split("Unknown op ", 1)[1].split("...", 1)[0]
        assert re.fullmatch(r'"a*(\\u0001)*', shown), shown


def test_rejects_missing_shape(catalog):
    msg = rejected(half_box(), {"op": "add", "color": 4}, catalog)
    assert '"add" needs a "shape"' in msg and '"type": "box"' in msg


def test_rejects_shape_that_is_not_an_object(catalog):
    msg = rejected(half_box(), add([0, 0, 0]), catalog)
    assert '"shape" must be an object' in msg and "[0, 0, 0]" in msg


def test_rejects_missing_or_unknown_shape_type(catalog):
    d = half_box()
    msg = rejected(d, add({"min": [0, 0, 0], "max": [1, 1, 1]}), catalog)
    assert 'missing "type"' in msg and '"box"' in msg and '"ellipsoid"' in msg
    msg = rejected(d, add({"type": "sphere", "center": [1, 1, 1], "radius": [1, 1, 1]}), catalog)
    assert 'Unknown shape type "sphere"' in msg and '"ellipsoid"' in msg
    msg = rejected(d, add({"type": "Box", "min": [0, 0, 0], "max": [1, 1, 1]}), catalog)
    assert 'Did you mean "box"?' in msg


def test_rejects_unknown_fields_with_suggestions(catalog):
    d = half_box()
    msg = rejected(d, {"op": "add", "shape": B((0, 0, 3), (0, 0, 3)), "colour": 4}, catalog)
    assert 'unexpected field "colour"' in msg and 'Did you mean "color"?' in msg
    msg = rejected(d, add({"type": "ellipsoid", "centre": [1, 1, 1], "radius": [1, 1, 1]}), catalog)
    assert 'unexpected field "centre"' in msg and 'Did you mean "center"?' in msg
    msg = rejected(d, {**add(B((0, 0, 3), (0, 0, 3))), "symmetric": True}, catalog)
    assert 'unexpected field "symmetric"' in msg and '"op", "shape", "color"' in msg
    msg = rejected(d, add({**B((0, 0, 3), (0, 0, 3)), "size": [1, 1, 1]}), catalog)
    assert 'The box has an unexpected field "size"' in msg


def test_rejects_remove_with_colour(catalog):
    msg = rejected(half_box(), {**remove(B((0, 0, 0), (0, 0, 0))), "color": 4}, catalog)
    assert '"remove" does not take a "color"' in msg


@pytest.mark.parametrize("field", ["min", "max"])
def test_rejects_box_missing_corner(catalog, field):
    shape = B((0, 0, 0), (1, 1, 1))
    del shape[field]
    msg = rejected(half_box(), add(shape), catalog)
    assert f'The box is missing "{field}"' in msg


@pytest.mark.parametrize("field", ["center", "radius"])
def test_rejects_ellipsoid_missing_field(catalog, field):
    shape = E((1, 1, 1), (1, 1, 1))
    del shape[field]
    msg = rejected(half_box(), add(shape), catalog)
    assert f'The ellipsoid is missing "{field}"' in msg


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0,0,0", 'list of three whole numbers [x, y, z], but it is "0,0,0"'),
        (5, "list of three whole numbers [x, y, z], but it is 5"),
        ([0, 0], "exactly three whole numbers [x, y, z], but it has 2: [0, 0]"),
        ([0, 0, 0, 0], "but it has 4"),
        ([0, "1", 0], '"min" y must be a number, but it is "1"'),
        ([0, 0, True], '"min" z must be a number, but it is true'),
        ([0, None, 0], '"min" y must be a number, but it is null'),
        ([1.5, 0, 0], '"min" x is 1.5, but box corners must be whole cells. Use 1 or 2'),
        ([0, float("nan"), 0], '"min" y is NaN; it must be a finite number'),
        ([0, 0, float("inf")], '"min" z is Infinity; it must be a finite number'),
    ],
)
def test_rejects_bad_box_corner(catalog, value, expected):
    msg = rejected(half_box(), add({"type": "box", "min": value, "max": [2, 2, 2]}), catalog)
    assert expected in msg


@pytest.mark.parametrize(
    ("center", "radius", "expected"),
    [
        ([1, 1], [1, 1, 1], '"center" must have exactly three numbers [x, y, z], but it has 2'),
        ([1, 1, 1], 2, '"radius" must be a list of three numbers [x, y, z], but it is 2'),
        ([1, "a", 1], [1, 1, 1], '"center" y must be a number, but it is "a"'),
        ([1, 1, 1], [1, float("nan"), 1], '"radius" y is NaN; it must be a finite number'),
        ([float("-inf"), 1, 1], [1, 1, 1], '"center" x is -Infinity'),
        ([1, 1, 1], [1, 0.25, 1], "at least 0.5, but the y radius is 0.25"),
        ([1, 1, 1], [0, 1, -1], "the x radius is 0, z radius is -1"),
    ],
)
def test_rejects_bad_ellipsoid(catalog, center, radius, expected):
    msg = rejected(half_box(), add(E(center, radius)), catalog)
    assert expected in msg


def test_rejects_box_with_min_above_max(catalog):
    msg = rejected(half_box(), paint(B((3, 0, 11), (1, 1, 9))), catalog)
    assert "min x = 3 but max x = 1" in msg and "min z = 11 but max z = 9" in msg
    assert '"min": [1, 0, 9], "max": [3, 1, 11]' in msg
    assert "min y" not in msg


@pytest.mark.parametrize(
    ("shape", "axis_text"),
    [
        (B((-5, 0, 0), (-1, 1, 1)), "x -5..-1"),
        (B((6, 0, 0), (8, 1, 1)), "x 6..8"),
        (B((0, -3, 0), (1, -1, 1)), "y -3..-1"),
        (B((0, 5, 0), (1, 9, 1)), "y 5..9"),
        (B((0, 0, -2), (1, 1, -1)), "z -2..-1"),
        (B((0, 0, 9), (1, 1, 12)), "z 9..12"),
        (E((2, 2, 15), (1, 1, 2)), "z 13..17"),
        (E((-3.5, 2, 2), (1, 1, 1)), "x -4..-3"),
    ],
)
def test_rejects_shape_entirely_outside_with_valid_ranges(catalog, shape, axis_text):
    msg = rejected(half_box(), add(shape), catalog)
    assert "entirely outside the grid" in msg
    assert axis_text in msg
    assert "Valid cells are x 0..5, y 0..4, z 0..8" in msg


@pytest.mark.parametrize(
    "shape",
    [
        E((-1.5, -1.5, -1.5), (2, 2, 2)),  # misses past a corner of the grid
        E((-1.5, -1.5, 4), (2, 2, 2)),  # misses past an edge of the grid
        E((6.5, 5.5, 9.5), (2, 2, 2)),  # misses past the opposite corner
    ],
)
def test_rejects_ellipsoid_missing_the_grid_diagonally_with_valid_ranges(catalog, shape):
    # Each axis of the bounding box overlaps the grid, but the ball itself does not.
    assert not shape_mask(shape, (6, 5, 9)).any()
    d = half_box()
    before = snapshot(d)
    msg = rejected(d, add(shape), catalog)
    assert "entirely outside the grid" in msg
    assert "Valid cells are x 0..5, y 0..4, z 0..8" in msg
    assert "too small" not in msg
    assert snapshot(d) == before and d.log == []


def test_rejects_ellipsoid_containing_no_cell(catalog):
    msg = rejected(half_box(), add(E((2.3, 2.3, 4.3), (0.5, 0.5, 0.5))), catalog)
    assert "too small to contain any cell" in msg


def _cells_anywhere(center, radius) -> int:
    """How many cells the ellipsoid holds when it is moved well inside a big grid by 10."""
    moved = [c + 10 for c in center]
    return int(shape_mask(E(moved, radius), (30, 30, 30)).sum())


def test_ellipsoid_whose_bounds_cross_the_edge_but_no_cell_does_is_not_called_clipped(catalog):
    # The bounding box reaches x = -1, but no cell of the ellipsoid lies outside the grid.
    center, radius = (0.4, 2.5, 4.5), (1.45, 0.75, 0.75)
    assert _cells_anywhere(center, radius) == 4
    d = half_box()
    r = one(d, add(E(center, radius)), catalog)
    assert r.applied and r.cells_changed == 4
    assert "outside" not in r.message and "ignored" not in r.message


def test_ellipsoid_with_cells_really_outside_the_grid_still_says_so(catalog):
    # Four of its eight cells are at x = -1, outside the grid.
    center, radius = (-0.5, 2.5, 4.5), (1.45, 1, 1)
    inside = int(shape_mask(E(center, radius), (6, 5, 9)).sum())
    assert _cells_anywhere(center, radius) > inside > 0
    r = one(half_box(), add(E(center, radius)), catalog)
    assert r.applied and r.cells_changed == inside
    assert "Part of the shape lay outside the grid (x 0..5, y 0..4, z 0..8)" in r.message


def test_ellipsoid_straddling_the_edge_with_no_cell_anywhere_is_too_small(catalog):
    center, radius = (-0.4, 2.5, 4.5), (0.6, 0.6, 0.6)
    assert _cells_anywhere(center, radius) == 0
    d = half_box()
    before = snapshot(d)
    msg = rejected(d, add(E(center, radius)), catalog)
    assert "too small to contain any cell" in msg
    assert "entirely outside" not in msg
    assert snapshot(d) == before and d.log == []


def test_huge_clipped_ellipsoid_is_applied_quickly_and_says_it_was_clipped(catalog):
    # Far too big to look at every cell beyond the grid; it is reported as clipped.
    d = half_box()
    r = one(d, add(E((3, 2, 4), (1e6, 1e6, 1e6))), catalog)
    assert r.applied and r.cells_changed == 6 * 5 * 6
    assert "Part of the shape lay outside the grid" in r.message


def test_rejects_missing_colour_with_valid_codes(catalog):
    msg = rejected(half_box(), {"op": "paint", "shape": B((0, 0, 0), (1, 1, 1))}, catalog)
    assert '"paint" needs a "color"' in msg
    assert "4 Red" in msg and "71 Light Bluish Grey" in msg and "0 Black" in msg


def test_rejects_unknown_colour_and_lists_every_valid_code(catalog):
    msg = rejected(half_box(), add(B((0, 0, 3), (1, 1, 3)), 999), catalog)
    assert "Colour 999 is not in the catalogue" in msg
    for code, colour in catalog.colours.items():
        assert f"{code} {colour.name}" in msg


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("red", '"color" must be a whole-number colour code, but it is "red". Red is code 4.'),
        ("Light Bluish Grey", "Light Bluish Grey is code 71."),
        (4.5, "but it is 4.5"),
        (True, "but it is true"),
        (None, "but it is null"),
        ([4], "but it is [4]"),
    ],
)
def test_rejects_colour_of_wrong_type(catalog, value, expected):
    msg = rejected(half_box(), add(B((0, 0, 3), (1, 1, 3)), value), catalog)
    assert expected in msg and "Valid codes: 0 Black" in msg


def test_rejects_remove_that_would_empty_the_design(catalog):
    d = half_box()
    msg = rejected(d, remove(B((-10, -10, -10), (100, 100, 100))), catalog)
    assert "remove all 90 filled cells" in msg and "completely empty" in msg


def test_rejected_operation_does_not_stop_later_ones(catalog):
    d = half_box()
    results = apply_ops(
        d,
        [
            add(B((0, 0, 3), (0, 0, 3))),
            {"op": "bogus"},
            add(B((9, 9, 9), (10, 10, 10))),
            paint(B((1, 1, 1), (1, 1, 1)), BLUE),
        ],
        catalog,
    )
    assert [r.index for r in results] == [0, 1, 2, 3]
    assert [r.applied for r in results] == [True, False, False, True]
    assert [r.op for r in results] == ["add", "bogus", "add", "paint"]
    assert d.colors[1, 1, 1] == BLUE and d.colors[0, 0, 3] == RED


def test_apply_ops_needs_a_list(catalog):
    with pytest.raises(ValueError, match="expects a list of operations"):
        apply_ops(half_box(), add(B((0, 0, 3), (0, 0, 3))), catalog)  # ty: ignore[invalid-argument-type]


def test_empty_list_does_nothing(catalog):
    d = half_box()
    before = snapshot(d)
    assert apply_ops(d, [], catalog) == []
    assert snapshot(d) == before


# ---- the log --------------------------------------------------------------------------------


def mixed_ops() -> list[dict[str, Any]]:
    return [
        paint(B((0, 0, 0), (5, 0, 2)), RED),  # applied
        add(E((2.5, 2, 4.5), (1.5, 1.5, 2)), ORANGE),  # applied
        add(B((0, 0, 0), (1, 1, 1))),  # nothing to add
        remove(B((0, 4, 0), (5, 4, 0))),  # applied
        {"op": "paint", "shape": B((0, 0, 0), (1, 1, 1)), "color": 12345},  # rejected
        paint(E((3, 2, 2), (1, 1, 1)), BLUE),  # applied
        remove(B((0, 4, 0), (5, 4, 0))),  # already empty
        add(B((0, 0, 8), (0, 0, 8)), 4.0),  # applied
    ]


def test_log_holds_exactly_the_applied_operations(catalog):
    d = half_box()
    ops = mixed_ops()
    given = copy.deepcopy(ops)
    results = apply_ops(d, ops, catalog)
    applied = [ops[r.index] for r in results if r.applied]
    assert [r.applied for r in results] == [True, True, False, True, False, True, False, True]
    assert d.log == applied
    assert ops == given, "apply_ops must not change the operations it was given"
    assert json.loads(json.dumps(d.log)) == d.log


def test_log_is_a_copy_of_the_operation(catalog):
    d = half_box()
    op = add(B((0, 0, 3), (1, 1, 3)))
    apply_ops(d, [op], catalog)
    op["shape"]["max"][0] = 5
    op["color"] = 1
    assert d.log == [add(B((0, 0, 3), (1, 1, 3)))]


def test_log_turns_numpy_numbers_and_tuples_into_plain_json(catalog):
    d = half_box()
    op = {
        "op": "add",
        "shape": {"type": "box", "min": (np.int64(0), 0, 3), "max": np.array([1, 1, 3]).tolist()},
        "color": np.int32(4),
    }
    assert one(d, op, catalog).applied
    assert d.log == [add(B((0, 0, 3), (1, 1, 3)))]
    assert type(d.log[0]["color"]) is int
    json.dumps(d.log)


def test_log_turns_numpy_long_double_into_plain_json(catalog):
    d = half_box()
    op = {
        "op": "add",
        "shape": {
            "type": "ellipsoid",
            "center": [np.longdouble(2), np.float32(2), np.float16(4)],
            "radius": [np.longdouble(1), 1, 1],
        },
        "color": np.longdouble(4),
    }
    r = one(d, op, catalog)
    assert r.applied and r.cells_changed == 7
    assert d.log == [add(E((2, 2, 4), (1, 1, 1)))]
    assert type(d.log[0]["shape"]["center"][0]) is float
    assert type(d.log[0]["color"]) is float
    json.dumps(d.log)
    d.copy()  # copying goes through the log too


def test_log_appends_to_existing_log(catalog):
    d = half_box()
    apply_ops(d, [add(B((0, 0, 3), (0, 0, 3)))], catalog)
    apply_ops(d, [add(B((1, 0, 3), (1, 0, 3)))], catalog)
    assert len(d.log) == 2 and d.log[1]["shape"]["min"] == [1, 0, 3]


# ---- replay ---------------------------------------------------------------------------------


def assert_same(a: Design, b: Design) -> None:
    assert a.finish is not None and b.finish is not None
    assert a.colors.dtype == b.colors.dtype and a.colors.tobytes() == b.colors.tobytes()
    assert a.finish.tobytes() == b.finish.tobytes()
    assert a.seed_offset == b.seed_offset
    assert a.details == b.details and a.regions == b.regions and a.log == b.log


def test_replay_reproduces_the_design_exactly(catalog):
    base = half_box()
    base.seed_offset = (1, 2, 0)
    base.details.append(Detail(part="98138", color=0, x=1, y=0, z=3))
    base.regions["top"] = B((0, 0, 2), (5, 4, 2))
    d = base.copy()
    apply_ops(d, mixed_ops(), catalog)
    apply_ops(d, [remove(E((0, 0, 0), (2, 2, 2))), paint(B((5, 4, 0), (5, 4, 0)), 15)], catalog)
    again = replay(base, d.log, catalog)
    assert_same(again, d)
    assert again is not base and base.log == [] and int(base.filled.sum()) == 90


def test_replay_does_not_change_the_base(catalog):
    base = half_box()
    before = snapshot(base)
    replay(base, [paint(B((0, 0, 0), (1, 1, 1)), RED)], catalog)
    assert snapshot(base) == before


def test_replay_of_an_empty_log_is_a_copy(catalog):
    base = half_box()
    out = replay(base, [], catalog)
    assert_same(out, base)
    out.colors[0, 0, 0] = RED
    assert base.colors[0, 0, 0] == GREY


def test_replay_after_saving_and_loading(catalog, tmp_path):
    base = box(4, 3, 2)
    d = base.copy()
    apply_ops(d, [paint(B((0, 0, 0), (3, 0, 5)), RED), add(E((2, 1, 7), (1, 1, 1.5)), 14)], catalog)
    base.save(tmp_path / "design.base.npz")
    d.save(tmp_path / "design.npz", tmp_path / "design.json")
    loaded_base = Design.load(tmp_path / "design.base.npz")
    loaded = Design.load(tmp_path / "design.npz", tmp_path / "design.json")
    assert_same(replay(loaded_base, loaded.log, catalog), loaded)


def test_replay_prefix_gives_undo(catalog):
    base = half_box()
    d = base.copy()
    apply_ops(d, [add(B((0, 0, 3), (0, 0, 3))), paint(B((0, 0, 0), (0, 0, 0)), BLUE)], catalog)
    undone = replay(base, d.log[:-1], catalog)
    assert undone.colors[0, 0, 0] == GREY and undone.colors[0, 0, 3] == RED


def test_replay_raises_when_the_log_does_not_fit_the_base(catalog):
    base = half_box()
    with pytest.raises(ValueError, match=r"Edit 2 of 2 in the log could not be replayed"):
        replay(base, [paint(B((0, 0, 0), (0, 0, 0))), add(B((0, 0, 0), (0, 0, 0)))], catalog)
    with pytest.raises(ValueError, match="Colour 999 is not in the catalogue"):
        replay(base, [paint(B((0, 0, 0), (0, 0, 0)), 999)], catalog)


def test_random_edit_sequences_replay_exactly(catalog):
    rng = random.Random(1234)
    codes = sorted(catalog.colours)
    for _ in range(20):
        base = half_box()
        d = base.copy()
        for _ in range(15):
            if rng.random() < 0.5:
                lo = [rng.randint(-2, 7) for _ in range(3)]
                shape = B(lo, [v + rng.randint(-1, 4) for v in lo])
            else:
                shape = E(
                    [rng.uniform(-1, 9) for _ in range(3)], [rng.uniform(0.3, 3) for _ in range(3)]
                )
            kind = rng.choice(["add", "remove", "paint"])
            op = remove(shape) if kind == "remove" else {"op": kind, "shape": shape}
            if kind != "remove":
                op["color"] = rng.choice(codes)
            before = snapshot(d)
            n_log = len(d.log)
            (r,) = apply_ops(d, [op], catalog)
            if r.applied:
                assert r.cells_changed > 0 and len(d.log) == n_log + 1 and d.log[-1] == op
                assert d.filled.any()
            else:
                assert snapshot(d) == before
        assert_same(replay(base, d.log, catalog), d)


def test_cells_changed_counts_colour_changes(catalog):
    rng = random.Random(99)
    d = half_box()
    for _ in range(30):
        lo = [rng.randint(0, 5) for _ in range(3)]
        op = {
            "op": rng.choice(["add", "paint"]),
            "shape": B(lo, [v + 2 for v in lo]),
            "color": rng.choice([RED, BLUE, GREY]),
        }
        before = d.colors.copy()
        (r,) = apply_ops(d, [op], catalog)
        assert r.cells_changed == int((before != d.colors).sum())


# ---- OP_SCHEMA ------------------------------------------------------------------------------


def _type_ok(value: Any, kind: str) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "null":
        return value is None
    raise AssertionError(f"validator does not know type {kind}")


SUPPORTED_KEYWORDS = {
    "type",
    "const",
    "enum",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "minimum",
    "anyOf",
    "oneOf",
    "title",
    "description",
}


def schema_valid(value: Any, schema: dict[str, Any]) -> bool:
    """A small JSON Schema validator covering the keywords OP_SCHEMA uses."""
    unknown = set(schema) - SUPPORTED_KEYWORDS
    assert not unknown, f"OP_SCHEMA uses keywords this test does not check: {unknown}"
    if "type" in schema and not _type_ok(value, schema["type"]):
        return False
    if "const" in schema and not (
        value == schema["const"] and type(value) is type(schema["const"])
    ):
        return False
    if "enum" in schema and not any(
        value == e and not isinstance(value, bool) for e in schema["enum"]
    ):
        return False
    if "minimum" in schema and _type_ok(value, "number") and value < schema["minimum"]:
        return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            return False
        for k, v in value.items():
            if k in props:
                if not schema_valid(v, props[k]):
                    return False
            elif schema.get("additionalProperties", True) is False:
                return False
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            return False
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            return False
        if "items" in schema and not all(schema_valid(v, schema["items"]) for v in value):
            return False
    if "anyOf" in schema and not any(schema_valid(value, s) for s in schema["anyOf"]):
        return False
    return not ("oneOf" in schema and sum(schema_valid(value, s) for s in schema["oneOf"]) != 1)


def test_schema_is_plain_self_contained_json():
    text = json.dumps(OP_SCHEMA)
    assert json.loads(text) == OP_SCHEMA
    assert "$ref" not in text and "$defs" not in text
    assert OP_SCHEMA["type"] == "object"
    variants = OP_SCHEMA["anyOf"]
    assert [v["properties"]["op"]["const"] for v in variants] == list(OPS)
    for v in variants:
        name = v["properties"]["op"]["const"]
        assert v["additionalProperties"] is False
        assert "op" in v["required"]
        assert ("shape" in v["required"]) == (name in SHAPE_OPS)
        assert ("color" in v["required"]) == (name in ("add", "paint", "place_detail"))


def test_schema_colour_enum_matches_catalogue(catalog):
    add_variant = OP_SCHEMA["anyOf"][0]
    color = add_variant["properties"]["color"]
    assert color["type"] == "integer"
    assert sorted(color["enum"]) == sorted(catalog.colours)
    assert "4 Red" in color["description"]


VALID_EXAMPLES: list[Any] = [
    {"op": "paint", "shape": {"type": "box", "min": [2, 0, 9], "max": [5, 1, 11]}, "color": 4},
    {
        "op": "add",
        "shape": {"type": "ellipsoid", "center": [8, 3, 20], "radius": [2, 1, 3]},
        "color": 25,
    },  # noqa: E501
    {"op": "remove", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 7, 2]}},
    {"op": "add", "shape": {"type": "box", "min": [-3, 0, 0], "max": [100, 0, 0]}, "color": 0},
    {
        "op": "paint",
        "shape": {"type": "ellipsoid", "center": [1.5, 2, 0.25], "radius": [0.75, 0.75, 7.75]},
        "color": 484,
    },  # noqa: E501
    {"op": "add", "shape": {"type": "box", "min": [1.0, 2, 3], "max": [4, 5, 6.0]}, "color": 4.0},
]

INVALID_EXAMPLES: list[Any] = [
    "add",
    [],
    {},
    {"op": "add"},
    {"op": "fill", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": 999},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": "red"},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": True},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "colour": 4},
    {"op": "remove", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"type": "box", "min": [0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"type": "box", "min": [0.5, 0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0]}, "color": 4},
    {"op": "add", "shape": {"type": "cone", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"min": [0, 0, 0], "max": [1, 1, 1]}, "color": 4},
    {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1], "x": 1}, "color": 4},  # noqa: E501
    {
        "op": "add",
        "shape": {"type": "ellipsoid", "center": [0, 0, 0], "radius": [0.4, 1, 1]},
        "color": 4,
    },  # noqa: E501
    {
        "op": "add",
        "shape": {"type": "ellipsoid", "center": [0, 0, 0], "radius": [1, 1]},
        "color": 4,
    },  # noqa: E501
    {
        "op": "add",
        "shape": {"type": "ellipsoid", "center": [0, "0", 0], "radius": [1, 1, 1]},
        "color": 4,
    },  # noqa: E501
    {
        "op": "add",
        "shape": {"type": "ellipsoid", "centre": [0, 0, 0], "radius": [1, 1, 1]},
        "color": 4,
    },  # noqa: E501
    {"op": "add", "shape": "box", "color": 4},
]


@pytest.mark.parametrize("op", VALID_EXAMPLES)
def test_schema_and_apply_ops_accept_valid_operations(catalog, op):
    assert schema_valid(op, OP_SCHEMA)
    validate_op(op, catalog)
    d = Design(colors=np.full((10, 10, 30), GREY, dtype=np.int16))
    r = one(d, op, catalog)
    assert not r.message.startswith("Rejected"), r.message


@pytest.mark.parametrize("op", INVALID_EXAMPLES)
def test_schema_and_apply_ops_reject_invalid_operations(catalog, op):
    assert not schema_valid(op, OP_SCHEMA)
    with pytest.raises(ValueError):
        validate_op(op, catalog)
    assert one(half_box(), op, catalog).message.startswith("Rejected:")


def _mutations(rng: random.Random, value: Any, depth: int = 0) -> Any:
    """A randomly damaged copy of an operation, to probe the schema and the validator."""
    junk = [None, True, False, 0, -1, 0.4, 0.5, 2.5, 7, 4, 999, "x", "box", "add", [], {}, [1, 2]]
    if isinstance(value, dict):
        out = dict(value)
        roll = rng.random()
        if roll < 0.15 and out:
            del out[rng.choice(list(out))]
        elif roll < 0.25:
            out[rng.choice(["color", "colour", "extra", "type", "op", "shape"])] = rng.choice(junk)
        elif out:
            k = rng.choice(list(out))
            out[k] = _mutations(rng, out[k], depth + 1)
        return out
    if isinstance(value, list):
        out_list = list(value)
        roll = rng.random()
        if roll < 0.15:
            out_list.append(rng.choice([0, 1.5]))
        elif roll < 0.3 and out_list:
            out_list.pop()
        elif out_list:
            i = rng.randrange(len(out_list))
            out_list[i] = _mutations(rng, out_list[i], depth + 1)
        return out_list
    return rng.choice(junk)


def test_schema_agrees_with_validation_on_random_operations(catalog):
    """Whatever apply_ops accepts the schema accepts, and almost vice versa.

    The schema cannot express "min <= max", so only that may pass the schema and still be
    rejected by apply_ops.
    """
    rng = random.Random(2024)
    disagreements = []
    checked = accepted = 0
    for _ in range(4000):
        op = _mutations(rng, copy.deepcopy(rng.choice(VALID_EXAMPLES)))
        try:
            validate_op(op, catalog)
            ok, message = True, ""
        except ValueError as err:
            ok, message = False, str(err)
        in_schema = schema_valid(op, OP_SCHEMA)
        checked += 1
        accepted += ok
        if ok and not in_schema:
            disagreements.append(("apply_ops accepts but schema rejects", op))
        if in_schema and not ok and "min is greater than its max" not in message:
            disagreements.append(("schema accepts but apply_ops rejects", op, message))
    assert not disagreements, disagreements[:5]
    assert accepted > 200 and checked - accepted > 1000  # the fuzzing exercised both sides


def test_schema_describes_units_for_the_model():
    text = json.dumps(OP_SCHEMA)
    assert "studs" in text and "plates" in text and "inclusive" in text
    assert "0.5" in text


def test_min_radius_in_schema_matches_validation(catalog):
    ellipsoid = OP_SCHEMA["anyOf"][0]["properties"]["shape"]["anyOf"][1]
    assert ellipsoid["properties"]["radius"]["items"]["minimum"] == 0.5
    validate_op(add(E((0, 0, 0), (0.5, 0.5, 0.5))), catalog)
    with pytest.raises(ValueError):
        validate_op(add(E((0, 0, 0), (0.4999, 0.5, 0.5))), catalog)


def test_non_finite_numbers_are_rejected_everywhere(catalog):
    for bad in (math.nan, math.inf, -math.inf):
        for field in ("center", "radius"):
            shape = E((1, 1, 1), (1, 1, 1))
            shape[field][1] = bad
            with pytest.raises(ValueError, match="finite"):
                validate_op(add(shape), catalog)
        with pytest.raises(ValueError, match="whole-number colour code"):
            validate_op(add(B((0, 0, 0), (1, 1, 1)), bad), catalog)


def test_extreme_numbers_give_messages_not_crashes(catalog):
    d = half_box()
    msg = rejected(d, add(E((10**400, 1, 1), (1, 1, 1))), catalog)
    assert '"center" x is far too large' in msg
    msg = rejected(d, add(E((1e308, 1, 1), (1e300, 1, 1))), catalog)
    assert "entirely outside the grid" in msg and "[1e+308, 1, 1]" in msg
    msg = one(d, add(E((1e308, 1, 1), (1e308, 1, 1))), catalog).message
    assert "already filled" in msg  # its surface passes through x = 0
    r = one(d, add(E((-1e308, 2, 4), (1.7e308, 1, 1)), ORANGE), catalog)
    assert r.applied
    msg = rejected(d, add(B((10**400, 0, 0), (10**401, 1, 1))), catalog)
    assert "entirely outside the grid" in msg
    r = one(d, add(B((-(10**400), 0, 3), (10**400, 0, 3)), ORANGE), catalog)
    assert r.applied and r.cells_changed == 6
    json.dumps(d.log)


HUGE = 10**5000  # more digits than Python will turn into text by default


@pytest.mark.parametrize(
    "op",
    [
        add(B((HUGE, 0, 0), (10 * HUGE, 1, 1))),
        add(B((-HUGE, 0, 3), (HUGE, 0, 3))),
        add(B((0, 0, 3), (1, 1, 3)), HUGE),
        add(B((0, 0, 3), (1, 1, 3)), -HUGE),
        add(B((HUGE, 0, 3), (1, 1, 3))),  # min greater than max
        add(E((HUGE, 1, 1), (1, 1, 1))),
        add({"type": "box", "min": [HUGE, 0], "max": [1, 1, 1]}),
        add({"type": "box", "min": [0, 0, 0], "max": [1, 1, 1], HUGE: 1}),
        {"op": HUGE, "shape": B((0, 0, 0), (1, 1, 1))},
        HUGE,
    ],
    ids=[
        "box-outside",
        "box-spanning",
        "colour",
        "negative-colour",
        "min-above-max",
        "ellipsoid",
        "short-corner",
        "field-name",
        "op-name",
        "bare-number",
    ],
)
def test_gigantic_integers_are_rejected_with_short_messages(catalog, op):
    d = half_box()
    before = snapshot(d)
    msg = rejected(d, op, catalog)
    assert len(msg) < 1000, msg  # the list of valid colours alone takes about 600
    assert snapshot(d) == before and d.log == []


def test_deeply_nested_values_give_messages_not_crashes(catalog):
    deep: list = []
    cur = deep
    for _ in range(100_000):
        nxt: list = []
        cur.append(nxt)
        cur = nxt
    d = half_box()
    msg = rejected(d, {"op": "add", "shape": deep, "color": 4}, catalog)
    assert '"shape" must be an object' in msg and "nested too deeply" in msg
    msg = rejected(d, deep, catalog)
    assert "Each operation must be an object" in msg
    msg = rejected(d, add(B((0, 0, 3), (1, 1, 3)), deep), catalog)
    assert '"color" must be a whole-number colour code' in msg
    assert d.log == []


def test_gigantic_box_corner_says_it_is_too_large(catalog):
    msg = rejected(half_box(), add(B((-HUGE, 0, 3), (HUGE, 0, 3))), catalog)
    assert '"min" x is far too large' in msg


def test_long_numbers_are_shortened_in_messages(catalog):
    d = half_box()
    big = 10**4000  # json.loads accepts this many digits
    corner = json.loads(json.dumps(add(B((big, 0, 0), (big + 1, 1, 1)))))
    msg = rejected(d, corner, catalog)
    assert "entirely outside the grid" in msg and "1e+4000" in msg
    assert len(msg) < 400, msg
    r = one(d, add(B((-big, 0, 3), (big, 0, 3)), ORANGE), catalog)
    assert r.applied and len(r.message) < 400 and "1e+4000" in r.message
    json.dumps(d.log)
    msg = rejected(d, add(B((0, 0, 3), (1, 1, 3)), 1e300), catalog)
    assert "Colour 1e+300 is not in the catalogue" in msg
    msg = rejected(d, add(B((0, 0, 3), (1, 1, 3)), 123456789012345678901234567890), catalog)
    assert "Colour 1.23e+29 is not in the catalogue" in msg
    msg = rejected(d, add(E((1e308, 1, 1), (1e300, 1, 1))), catalog)
    assert "x 1e+308..1e+308" in msg and len(msg) < 400, msg
    msg = rejected(d, add(B((10**30, 0, 0), (5, 1, 1))), catalog)
    assert "min x = 1e+30 but max x = 5" in msg and len(msg) < 400, msg
    # small whole numbers are still shown in full
    msg = rejected(d, add(B((0, 0, 3), (1, 1, 3)), 123456), catalog)
    assert "Colour 123456 is not" in msg


# ==== stage 2: set_finish, place_detail, remove_detail and "mirror" ========================


def table() -> Design:
    """An 8 x 6 x 12 grid with the bottom 3 plates (one brick) filled grey; mirror x -> 7 - x."""
    colors = np.full((8, 6, 12), EMPTY, dtype=np.int16)
    colors[:, :, :3] = GREY
    return Design(colors=colors)


def finish_op(shape, word="smooth", **extra) -> dict[str, Any]:
    return {"op": "set_finish", "shape": shape, "finish": word, **extra}


def detail(part="98138", color=0, at=(1, 0, 3), **extra) -> dict[str, Any]:
    return {"op": "place_detail", "part": part, "color": color, "at": list(at), **extra}


def undetail(at, **extra) -> dict[str, Any]:
    return {"op": "remove_detail", "at": list(at), **extra}


def full_snapshot(d: Design) -> tuple:
    return (*snapshot(d), json.dumps([vars(x) for x in d.details]))


def rejected_fully(design: Design, op: Any, catalog) -> str:
    """Like ``rejected`` but also checks the details were left alone."""
    before = full_snapshot(design)
    msg = rejected(design, op, catalog)
    assert full_snapshot(design) == before
    assert msg.startswith("Rejected: "), msg
    return msg


def covered(catalog, d: Detail) -> set[tuple[int, int, int]]:
    xs, ys, zs = catalog.cells(Placement(d.part, d.color, d.x, d.y, d.z, d.rot))
    return {
        (x, y, z)
        for x in range(xs.start, xs.stop)
        for y in range(ys.start, ys.stop)
        for z in range(zs.start, zs.stop)
    }


# ---- set_finish -----------------------------------------------------------------------------


def test_set_finish_marks_only_filled_cells(catalog):
    d = table()
    r = one(d, finish_op(B((0, 0, 1), (1, 1, 4)), "smooth"), catalog)
    assert r.applied and r.cells_changed == 8  # 2 x 2 x 2 filled cells; z 3..4 are empty
    assert d.finish is not None
    assert (d.finish[0:2, 0:2, 1:3] == FINISH_SMOOTH).all()
    assert int((d.finish != FINISH_STUDS).sum()) == 8
    assert (d.colors == table().colors).all(), "set_finish must not change colours"
    assert 'Marked 8 cells "smooth" (tiles on top)' in r.message
    assert d.log == [finish_op(B((0, 0, 1), (1, 1, 4)), "smooth")]


@pytest.mark.parametrize("word", list(FINISH_NAMES))
def test_set_finish_accepts_every_finish_word(catalog, word):
    d = table()
    d.finish[:] = FINISH_SLOPED if word != "sloped" else FINISH_SMOOTH  # ty: ignore[invalid-assignment]
    r = one(d, finish_op(B((0, 0, 2), (0, 0, 2)), word), catalog)
    assert r.applied and r.cells_changed == 1
    assert d.finish is not None and d.finish[0, 0, 2] == FINISH_NAMES[word]


def test_set_finish_counts_only_cells_whose_finish_changes(catalog):
    d = table()
    one(d, finish_op(B((0, 0, 2), (3, 0, 2)), "sloped"), catalog)
    r = one(d, finish_op(B((0, 0, 2), (5, 0, 2)), "sloped"), catalog)
    assert r.cells_changed == 2


def test_set_finish_says_where_the_finish_will_show(catalog):
    d = table()
    r = one(d, finish_op(B((0, 0, 2), (1, 0, 2))), catalog)
    assert "Each has nothing directly above it" in r.message
    r = one(d, finish_op(B((0, 0, 0), (1, 0, 1))), catalog)
    assert "None of them has an empty cell directly above it" in r.message
    r = one(d, finish_op(B((2, 0, 1), (4, 0, 2))), catalog)
    assert "3 of them have nothing directly above" in r.message
    r = one(d, finish_op(B((5, 0, 1), (5, 0, 2))), catalog)
    assert "1 of them has nothing directly above" in r.message


def test_set_finish_on_the_top_layer_of_the_grid_shows(catalog):
    d = Design(colors=np.full((2, 2, 2), GREY, dtype=np.int16))
    r = one(d, finish_op(B((0, 0, 1), (0, 0, 1))), catalog)
    assert "Each has nothing directly above it" in r.message


def test_set_finish_nothing_to_mark(catalog):
    d = table()
    msg = one(d, finish_op(B((0, 0, 5), (3, 3, 6))), catalog)
    assert not msg.applied and "every cell inside that box" in msg.message
    assert '"set_finish" only marks filled cells' in msg.message
    one(d, finish_op(B((0, 0, 2), (1, 1, 2))), catalog)
    r = one(d, finish_op(B((0, 0, 2), (1, 1, 2))), catalog)
    assert not r.applied and r.cells_changed == 0
    assert 'already "smooth"' in r.message
    r = one(d, finish_op(B((2, 2, 2), (3, 3, 2)), "studs"), catalog)
    assert not r.applied and 'already "studs"' in r.message
    assert len(d.log) == 1


@pytest.mark.parametrize(
    "value, expected",
    [
        ("tiles", 'Did you mean "smooth"?'),
        ("tile", 'Did you mean "smooth"?'),
        ("slope", 'Did you mean "sloped"?'),
        ("stud", 'Did you mean "studs"?'),
        ("Smooth", 'Did you mean "smooth"?'),
        ("glossy", 'Unknown finish "glossy"'),
        (1, '1 means "smooth"; write the word'),
        (2.0, '2 means "sloped"'),
        (None, "but it is null"),
        (True, "but it is true"),
    ],
)
def test_set_finish_rejects_bad_finish_words(catalog, value, expected):
    msg = rejected_fully(table(), finish_op(B((0, 0, 2), (1, 1, 2)), value), catalog)
    assert expected in msg
    assert '"studs"' in msg and '"smooth"' in msg and '"sloped"' in msg


def test_set_finish_needs_a_finish_and_a_shape(catalog):
    msg = rejected_fully(table(), {"op": "set_finish", "shape": B((0, 0, 2), (1, 1, 2))}, catalog)
    assert '"set_finish" needs a "finish"' in msg
    msg = rejected_fully(table(), {"op": "set_finish", "finish": "smooth"}, catalog)
    assert '"set_finish" needs a "shape"' in msg
    msg = rejected_fully(table(), {**finish_op(B((0, 0, 2), (1, 1, 2))), "color": 4}, catalog)
    assert 'unexpected field "color"' in msg and '"finish"' in msg


def test_set_finish_shape_outside_the_grid(catalog):
    msg = rejected_fully(table(), finish_op(B((20, 0, 0), (21, 1, 1))), catalog)
    assert "entirely outside the grid" in msg and "x 0..7" in msg


def test_add_and_remove_still_reset_finish_after_set_finish(catalog):
    d = table()
    one(d, finish_op(B((0, 0, 0), (7, 5, 2))), catalog)
    one(d, remove(B((0, 0, 2), (0, 0, 2))), catalog)
    one(d, add(B((0, 0, 2), (0, 0, 2))), catalog)
    assert d.finish is not None and d.finish[0, 0, 2] == FINISH_STUDS
    one(d, paint(B((1, 0, 2), (1, 0, 2))), catalog)
    assert d.finish[1, 0, 2] == FINISH_SMOOTH


# ---- "mirror" on shape operations -----------------------------------------------------------


@pytest.mark.parametrize("name", ["add", "remove", "paint", "set_finish"])
def test_mirror_applies_the_shape_and_its_mirror_image(catalog, name):
    def op_for(shape, mirror=None):
        op: dict[str, Any] = {"op": name, "shape": shape}
        if name in ("add", "paint"):
            op["color"] = RED
        if name == "set_finish":
            op["finish"] = "sloped"
        if mirror is not None:
            op["mirror"] = mirror
        return op

    z = 3 if name == "add" else 1
    shape = B((0, 1, z), (1, 2, z + 1))
    twin = B((6, 1, z), (7, 2, z + 1))
    mirrored = table()
    r = one(mirrored, op_for(shape, True), catalog)
    by_hand = table()
    apply_ops(by_hand, [op_for(shape), op_for(twin)], catalog)
    assert r.applied and r.cells_changed == 16
    assert mirrored.colors.tobytes() == by_hand.colors.tobytes()
    assert mirrored.finish is not None and by_hand.finish is not None
    assert mirrored.finish.tobytes() == by_hand.finish.tobytes()
    assert "and its mirror image, the box [6, 1, " in r.message
    assert mirrored.log == [op_for(shape, True)], "the log keeps the operation as given"


def test_mirror_false_is_the_same_as_no_mirror(catalog):
    a, b = table(), table()
    ra = one(a, add(B((0, 0, 3), (1, 1, 4))), catalog)
    rb = one(b, {**add(B((0, 0, 3), (1, 1, 4))), "mirror": False}, catalog)
    assert (ra.applied, ra.cells_changed, ra.message) == (rb.applied, rb.cells_changed, rb.message)
    assert snapshot(a)[:2] == snapshot(b)[:2]
    assert b.log[0]["mirror"] is False


def test_mirror_counts_a_cell_in_both_once(catalog):
    d = table()
    r = one(d, {**add(B((2, 0, 3), (4, 0, 3))), "mirror": True}, catalog)
    assert r.cells_changed == 4  # x 2..4 and x 3..5 overlap in x 3..4
    assert d.colors[2:6, 0, 3].tolist() == [RED] * 4


def test_mirror_of_a_shape_on_the_middle_says_so(catalog):
    d = table()
    r = one(d, {**add(B((3, 0, 3), (4, 0, 3))), "mirror": True}, catalog)
    assert r.cells_changed == 2 and "its own mirror image" in r.message


def test_mirror_of_an_ellipsoid(catalog):
    d = table()
    r = one(d, {**add(E((1, 2, 6), (1, 1, 2))), "mirror": True}, catalog)
    assert "ellipsoid centred at [6, 2, 6]" in r.message
    assert (d.colors[::-1] == d.colors).all()


def test_mirror_of_a_clipped_shape_is_clipped_too(catalog):
    d = table()
    r = one(d, {**add(B((-3, 0, 3), (0, 0, 3))), "mirror": True}, catalog)
    assert r.cells_changed == 2 and d.colors[0, 0, 3] == RED and d.colors[7, 0, 3] == RED
    assert "outside the grid" in r.message and "the box [7, 0, 3]..[10, 0, 3]" in r.message


def test_mirror_remove_may_not_empty_the_design(catalog):
    d = Design(colors=np.full((4, 1, 1), GREY, dtype=np.int16))
    msg = rejected(d, {**remove(B((0, 0, 0), (1, 0, 0))), "mirror": True}, catalog)
    assert "completely empty" in msg


@pytest.mark.parametrize("value", [1, 0, "true", None, [True]])
def test_mirror_must_be_true_or_false(catalog, value):
    for op in (
        add(B((0, 0, 3), (0, 0, 3))),
        finish_op(B((0, 0, 2), (0, 0, 2))),
        detail(),
        undetail((1, 0, 3)),
    ):
        msg = rejected_fully(table(), {**op, "mirror": value}, catalog)
        assert '"mirror" must be true or false' in msg


@pytest.mark.parametrize(
    "name",
    [
        "delete_detail",
        "erase_detail",
        "clear_detail",
        "unplace_detail",
        "delete_details",
        "DeleteDetail",
        "remove_details",
        "removeDetail",
    ],
)
def test_unknown_op_for_removing_a_detail_points_to_remove_detail(catalog, name):
    msg = rejected(table(), {"op": name, "at": [1, 0, 3]}, catalog)
    assert 'Did you mean "remove_detail"?' in msg, msg
    assert "place_detail" in msg  # the full list of operations still follows


def test_unknown_mirror_like_fields_and_ops_point_to_mirror(catalog):
    msg = rejected(table(), {**add(B((0, 0, 3), (0, 0, 3))), "mirrored": True}, catalog)
    assert 'Did you mean "mirror"?' in msg
    msg = rejected(table(), {**add(B((0, 0, 3), (0, 0, 3))), "symmetric": True}, catalog)
    assert 'Did you mean "mirror"?' in msg and 'optionally "mirror"' in msg
    msg = rejected(table(), {"op": "mirror", "shape": B((0, 0, 0), (1, 1, 1))}, catalog)
    assert '"mirror" is not an operation' in msg and '"mirror": true' in msg


# ---- place_detail ---------------------------------------------------------------------------


def test_place_detail_on_top_of_the_model(catalog):
    d = table()
    before = d.colors.copy()
    r = one(d, detail("98138", 0, (1, 0, 3)), catalog)
    assert r.applied and r.cells_changed == 0, r.message
    assert d.details == [Detail("98138", 0, 1, 0, 3, 0)]
    assert (d.colors == before).all()
    assert d.log == [detail("98138", 0, (1, 0, 3))]
    assert r.message.startswith("Placed a Black Tile 1 x 1 Round with Groove (98138)")
    assert "x=1, y=0, z=3" in r.message and "1 detail part." in r.message
    assert "slanted" not in r.message


def test_place_detail_with_rotation_covers_the_turned_footprint(catalog):
    d = table()
    r = one(d, detail("3069b", 15, (2, 1, 3), rot=90), catalog)
    assert r.applied, r.message
    assert d.details == [Detail("3069b", 15, 2, 1, 3, 90)]
    assert "covering x=2, y=1..2, z=3" in r.message


def test_place_detail_accepts_whole_floats(catalog):
    d = table()
    r = one(d, detail("98138", 0.0, (1.0, 0, 3.0), rot=180.0), catalog)
    assert r.applied, r.message
    assert d.details == [Detail("98138", 0, 1, 0, 3, 180)]
    assert type(d.details[0].x) is int and type(d.details[0].rot) is int


@pytest.mark.parametrize(
    "part, rot, direction",
    [
        ("3040b", 0, "the front (-y)"),
        ("3040b", 90, "the right (+x)"),
        ("3039", 180, "the back (+y)"),
        ("54200", 270, "the left (-x)"),
    ],
)
def test_place_detail_slope_says_which_way_it_runs_down(catalog, part, rot, direction):
    d = table()
    r = one(d, detail(part, 4, (2, 2, 3), rot=rot), catalog)
    assert r.applied, r.message
    assert f"Its slanted face runs down towards {direction}." in r.message


def test_place_detail_rejects_a_part_that_is_not_a_detail(catalog):
    msg = rejected_fully(table(), detail("3001", 4), catalog)
    assert 'Part "3001"' in msg and "not a detail part" in msg
    for p in catalog.detail_parts():
        assert f"{p.id} {p.name}" in msg
    msg = rejected_fully(table(), detail("nonsense", 4), catalog)
    assert 'Unknown detail part "nonsense"' in msg and "98138 Tile 1 x 1 Round" in msg


def test_place_detail_part_hints(catalog):
    msg = rejected_fully(table(), detail(98138, 0), catalog)
    assert 'written as text in quotes: "98138"' in msg
    msg = rejected_fully(table(), detail("3070", 0), catalog)
    assert 'Did you mean "3070b"' in msg
    msg = rejected_fully(table(), detail("tile 1 x 1 round with groove", 0), catalog)
    assert 'is part "98138"' in msg
    msg = rejected_fully(table(), detail(["98138"], 0), catalog)
    assert '"part" must be the id of a detail part written as text' in msg
    msg = rejected_fully(table(), {"op": "place_detail", "color": 0, "at": [1, 0, 3]}, catalog)
    assert '"place_detail" needs a "part"' in msg


def test_place_detail_rejects_a_colour_the_part_is_not_made_in(catalog):
    part = catalog.parts["4740"]
    missing = next(c for c in sorted(catalog.colours) if c not in part.colours)
    msg = rejected_fully(table(), detail("4740", missing, (2, 2, 3)), catalog)
    assert f"is not made in {catalog.colours[missing].name} ({missing})" in msg
    for c in part.colours:
        assert f"{c} {catalog.colours[c].name}" in msg
    msg = rejected_fully(table(), detail("98138", 9999), catalog)
    assert "Colour 9999 is not in the catalogue" in msg
    msg = rejected_fully(table(), {"op": "place_detail", "part": "98138", "at": [1, 0, 3]}, catalog)
    assert '"place_detail" needs a "color"' in msg


def test_place_detail_unknown_or_missing_colour_lists_the_colours_the_part_is_made_in(catalog):
    part = catalog.parts["4740"]
    made = [c for c in sorted(catalog.colours) if c in part.colours]
    not_made = [c for c in sorted(catalog.colours) if c not in part.colours]
    assert made and not_made
    unknown = next(c for c in range(1000) if c not in catalog.colours)
    for op in (
        detail("4740", unknown, (2, 2, 3)),
        {"op": "place_detail", "part": "4740", "at": [2, 2, 3]},
        detail("4740", "purple-ish", (2, 2, 3)),
    ):
        msg = rejected_fully(table(), op, catalog)
        assert "Dish 2 x 2 Inverted (4740) is made in: " in msg, msg
        listed = {int(c) for c in re.findall(r"(?<![\w.=])(\d+) [A-Z]", msg.split("made in: ")[1])}
        assert listed == set(made), msg
    msg = rejected_fully(table(), detail("4740", unknown, (2, 2, 3)), catalog)
    assert f"Colour {unknown} is not in the catalogue" in msg
    msg = rejected_fully(table(), {"op": "place_detail", "part": "4740", "at": [2, 2, 3]}, catalog)
    assert '"place_detail" needs a "color"' in msg
    # Without a valid part, the whole catalogue is still listed.
    msg = rejected_fully(table(), {"op": "add", "shape": B((0, 0, 3), (0, 0, 3))}, catalog)
    assert all(f"{c} {catalog.colours[c].name}" in msg for c in catalog.colours)


def test_place_detail_rejects_a_cell_outside_the_grid(catalog):
    msg = rejected_fully(table(), detail("3068b", 0, (7, 0, 3)), catalog)
    assert "would cover x=7..8, y=0..1, z=3" in msg and "x=8 is outside the grid" in msg
    assert "x 0..7, y 0..5, z 0..11" in msg
    msg = rejected_fully(table(), detail("98138", 0, (-1, 0, 3)), catalog)
    assert "x=-1 is outside the grid" in msg
    msg = rejected_fully(table(), detail("3062b", 0, (0, 0, 10)), catalog)
    assert "z=12 is outside the grid" in msg


def test_place_detail_rejects_a_filled_cell_and_suggests_a_height(catalog):
    msg = rejected_fully(table(), detail("98138", 0, (1, 0, 1)), catalog)
    assert "x=1, y=0, z=1, which is filled" in msg
    assert "A detail stands in empty cells" in msg
    assert '"at": [1, 0, 3] would fit' in msg


def test_place_detail_rejects_a_cell_with_nothing_below(catalog):
    d = table()
    one(d, remove(B((3, 3, 2), (3, 3, 2))), catalog)
    msg = rejected_fully(d, detail("3068b", 0, (2, 2, 3)), catalog)
    assert "the cell x=3, y=3, z=3 of its bottom layer has nothing below it" in msg
    assert "x=3, y=3, z=2 is empty" in msg
    assert "not flat (z=1 in some columns, z=2 in others)" in msg
    msg = rejected_fully(table(), detail("98138", 0, (1, 0, 6)), catalog)
    assert "nothing below it" in msg and '"at": [1, 0, 3] would fit' in msg


def test_place_detail_rejects_the_ground(catalog):
    d = Design(colors=np.full((4, 4, 4), EMPTY, dtype=np.int16))
    d.colors[0, 0, 0] = GREY
    msg = rejected_fully(d, detail("98138", 0, (2, 2, 0)), catalog)
    assert "z=0 is the ground" in msg


def test_place_detail_rejects_a_cell_taken_by_another_detail(catalog):
    d = table()
    assert one(d, detail("3068b", 0, (2, 2, 3)), catalog).applied
    msg = rejected_fully(d, detail("98138", 15, (3, 3, 3)), catalog)
    assert "x=3, y=3, z=3 is already taken by the Black Tile 2 x 2 with Groove (3068b)" in msg
    assert '{"op": "remove_detail", "at": [2, 2, 3]}' in msg


def test_place_detail_is_not_blocked_by_a_detail_on_another_level(catalog):
    d = table()
    one(d, detail("98138", 0, (1, 0, 3)), catalog)
    one(d, add(B((2, 0, 3), (2, 0, 3)), RED), catalog)
    assert one(d, detail("98138", 0, (2, 0, 4)), catalog).applied
    # Two details in the same column x=1, y=0, on different levels.
    d = table()
    assert one(d, detail("98138", 0, (1, 0, 3)), catalog).applied
    assert one(d, add(B((1, 0, 5), (1, 0, 5)), RED), catalog).applied
    r = one(d, detail("98138", 15, (1, 0, 6)), catalog)
    assert r.applied, r.message
    assert [(x.x, x.y, x.z) for x in d.details] == [(1, 0, 3), (1, 0, 6)]


def test_place_detail_rejects_a_tall_detail_whose_upper_cell_is_filled(catalog):
    d = table()
    assert one(d, add(B((3, 0, 5), (3, 0, 5)), RED), catalog).applied
    msg = rejected_fully(d, detail("59900", 0, (3, 0, 3)), catalog)  # cone, 3 plates tall
    assert "it would cover x=3, y=0, z=5, which is filled" in msg
    d = table()
    assert one(d, add(B((2, 3, 4), (2, 3, 4)), RED), catalog).applied
    msg = rejected_fully(d, detail("54200", 4, (2, 3, 3)), catalog)  # slope, 2 plates tall
    assert "it would cover x=2, y=3, z=4, which is filled" in msg


@pytest.mark.parametrize(
    "rot, expected",
    [
        (45, '"rot" must be 0, 90, 180 or 270'),
        (-90, "same turn as 270; use 270"),
        (360, "same turn as 0; use 0"),
        ("90", 'but it is "90"'),
        (True, "but it is true"),
        (90.5, "but it is 90.5"),
    ],
)
def test_place_detail_rejects_bad_rot(catalog, rot, expected):
    msg = rejected_fully(table(), detail(rot=rot), catalog)
    assert expected in msg


@pytest.mark.parametrize(
    "at, expected",
    [
        ([1, 0], "exactly three whole numbers"),
        ([1, 0, 3, 4], "exactly three whole numbers"),
        ([1.5, 0, 3], '"at" x is 1.5, but a cell position is whole. Use 1 or 2.'),
        ([1, "0", 3], '"at" y must be a number'),
        ("1, 0, 3", "must be a list of three whole numbers"),
        ([1, 0, math.inf], "finite"),
    ],
)
def test_place_detail_rejects_bad_at(catalog, at, expected):
    op = detail()
    op["at"] = at
    msg = rejected_fully(table(), op, catalog)
    assert expected in msg


def test_place_detail_needs_at(catalog):
    msg = rejected_fully(table(), {"op": "place_detail", "part": "98138", "color": 0}, catalog)
    assert '"place_detail" needs "at"' in msg


def test_place_detail_unexpected_fields(catalog):
    msg = rejected_fully(table(), {**detail(), "rotation": 90}, catalog)
    assert 'Did you mean "rot"?' in msg
    assert '"op", "part", "color", "at", and optionally "rot", "face" and "mirror"' in msg
    msg = rejected_fully(table(), {**detail(), "position": [1, 0, 3]}, catalog)
    assert 'Did you mean "at"?' in msg
    msg = rejected_fully(table(), {**detail(), "shape": B((0, 0, 0), (1, 1, 1))}, catalog)
    assert 'unexpected field "shape"' in msg


def test_place_detail_of_a_gigantic_position_gives_a_short_message(catalog):
    msg = rejected_fully(table(), detail(at=(10**30, 0, 3)), catalog)
    assert "x=1e+30 is outside the grid" in msg and len(msg) < 400


def test_every_detail_part_can_be_placed_in_every_rotation(catalog):
    big = Design(colors=np.full((12, 12, 12), EMPTY, dtype=np.int16))
    big.colors[:, :, :3] = GREY
    for part in catalog.detail_parts():
        colour = min(part.colours)
        for rot in ROTATIONS:
            d = big.copy()
            r = one(d, detail(part.id, colour, (4, 4, 3), rot=rot), catalog)
            assert r.applied, (part.id, rot, r.message)
            assert ("slanted face" in r.message) == bool(part.slope)


# ---- place_detail with "mirror" -------------------------------------------------------------


def _mirror_ok(catalog, nx: int, a: Detail, b: Detail) -> None:
    pa = Placement(a.part, a.color, a.x, a.y, a.z, a.rot)
    pb = Placement(b.part, b.color, b.x, b.y, b.z, b.rot)
    assert covered(catalog, b) == {(nx - 1 - x, y, z) for x, y, z in covered(catalog, a)}
    down = catalog.low_side(pa)
    assert catalog.low_side(pb) == (None if down is None else (-down[0], down[1]))
    assert sorted(catalog.stud_cells(pb)) == sorted(
        (nx - 1 - x, y) for x, y in catalog.stud_cells(pa)
    )
    assert (a.part, a.color) == (b.part, b.color)
    part = catalog.parts[a.part]
    if part.body_max[2] - part.body_min[2] > 20 * part.sz + 1:  # sticks out along its own Z
        ax, ay = _part_z_direction(a.rot)
        assert _part_z_direction(b.rot) == (-ax, ay), (a.part, a.rot, b.rot)


def _part_z_direction(rot: int) -> tuple[int, int]:
    """Grid direction of the part's own +Z axis at this turn (the rotation table)."""
    return {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[rot]


def _wide_table(nx: int = 12) -> Design:
    d = Design(colors=np.full((nx, 8, 10), EMPTY, dtype=np.int16))
    d.colors[:, :, :3] = GREY
    return d


@pytest.mark.parametrize("rot", ROTATIONS)
@pytest.mark.parametrize(
    "part", ["3040b", "3039", "54200", "85984", "4286", "11477", "3069b", "3068b", "4740"]
)
def test_mirrored_detail_is_the_mirror_image(catalog, part, rot):
    """For every slope and for a 1x2 and 2x2 detail: the twin covers the mirrored cells, a
    slope's twin runs down the mirrored way, and the studs are mirrored too."""
    d = _wide_table()
    colour = min(catalog.parts[part].colours)
    r = one(d, detail(part, colour, (1, 2, 3), rot=rot, mirror=True), catalog)
    assert r.applied, r.message
    assert len(d.details) == 2 and "Also placed its mirror image" in r.message
    first, twin = d.details
    assert (first.x, first.y, first.z, first.rot) == (1, 2, 3, rot)
    _mirror_ok(catalog, 12, first, twin)
    if catalog.parts[part].slope:
        assert "The mirror image's slanted face runs down towards" in r.message


def test_every_detail_part_has_a_mirror_image_in_every_rotation(catalog):
    for part in catalog.detail_parts():
        colour = min(part.colours)
        for rot in ROTATIONS:
            d = _wide_table(20)
            r = one(d, detail(part.id, colour, (0, 0, 3), rot=rot, mirror=True), catalog)
            assert r.applied and len(d.details) == 2, (part.id, rot, r.message)
            _mirror_ok(catalog, 20, *d.details)


def test_mirrored_slope_facing_right_faces_left(catalog):
    d = _wide_table()
    one(d, detail("3040b", 4, (1, 2, 3), rot=90, mirror=True), catalog)
    a, b = (Placement(x.part, x.color, x.x, x.y, x.z, x.rot) for x in d.details)
    assert catalog.low_side(a) == (1, 0) and catalog.low_side(b) == (-1, 0)
    assert (d.details[1].x, d.details[1].rot) == (9, 270)


@pytest.mark.parametrize("rot", ROTATIONS)
@pytest.mark.parametrize("part", ["3069b", "98138", "3068b", "4740"])
def test_mirrored_symmetric_detail_keeps_its_rotation(catalog, part, rot):
    d = _wide_table()
    r = one(d, detail(part, 0, (1, 2, 3), rot=rot, mirror=True), catalog)
    assert r.applied and len(d.details) == 2, r.message
    assert [x.rot for x in d.details] == [rot, rot]
    w = catalog.footprint(Placement(part, 0, 1, 2, 3, rot))[0]
    assert (d.details[1].x, d.details[1].y) == (12 - 1 - w, 2)


@pytest.mark.parametrize("rot, twin_rot", [(0, 0), (90, 270), (180, 180), (270, 90)])
def test_mirrored_clip_plate_points_its_clip_the_mirrored_way(catalog, rot, twin_rot):
    """60897's clip sticks out of the part along its own -Z: the mirror image must point the
    other way along x, which takes rot 270 for rot 90 and the other way round."""
    d = table()
    r = one(d, detail("60897", 0, (1, 2, 3), rot=rot, mirror=True), catalog)
    assert r.applied and len(d.details) == 2, r.message
    first, twin = d.details
    assert (first.x, first.rot) == (1, rot)
    assert (twin.x, twin.y, twin.z, twin.rot) == (6, 2, 3, twin_rot)
    assert f"Also placed its mirror image at x=6, y=2, z=3 (rot {twin_rot})" in r.message
    ax, ay = _part_z_direction(rot)
    assert _part_z_direction(twin.rot) == (-ax, ay)


def test_mirrored_detail_on_the_middle_is_placed_once(catalog):
    d = table()  # nx = 8: a 2-wide part at x 3..4 is centred
    r = one(d, detail("3068b", 0, (3, 1, 3), mirror=True), catalog)
    assert r.applied and len(d.details) == 1
    assert "left-right middle" in r.message and "only one was placed" in r.message
    d = table()
    r = one(d, detail("3040b", 4, (3, 1, 3), rot=90, mirror=True), catalog)
    assert r.applied and len(d.details) == 1 and "only one was placed" in r.message


def test_mirrored_detail_that_would_overlap_is_placed_once(catalog):
    d = table()
    one(d, detail("3069b", 0, (2, 1, 3), mirror=True), catalog)
    assert len(d.details) == 2  # x 2..3 and x 4..5 touch but do not overlap
    d = Design(colors=np.full((7, 3, 6), EMPTY, dtype=np.int16))
    d.colors[:, :, :3] = GREY
    r = one(d, detail("3068b", 0, (2, 0, 3), mirror=True), catalog)  # x 2..3 and x 3..4
    assert r.applied and len(d.details) == 1
    assert "would overlap it, so only one was placed" in r.message
    assert "centred" not in r.message  # (7 - 2) is odd: no centred spot
    d = Design(colors=np.full((7, 3, 6), EMPTY, dtype=np.int16))
    d.colors[:, :, :3] = GREY
    r = one(d, detail("63864", 0, (1, 0, 3), mirror=True), catalog)  # x 1..3 and x 3..5
    assert "would overlap it" in r.message and "use x=2" in r.message


def test_mirrored_detail_needs_both_places_free(catalog):
    d = table()
    one(d, add(B((6, 0, 3), (6, 0, 3)), RED), catalog)
    msg = rejected_fully(d, detail("98138", 0, (1, 0, 3), mirror=True), catalog)
    assert "would fit, but its mirror image at x=6, y=0, z=3 (rot 0) cannot go there" in msg
    assert "x=6, y=0, z=3, which is filled" in msg and "Nothing was placed" in msg
    assert 'leave out "mirror"' in msg
    d = table()
    one(d, detail("98138", 0, (6, 0, 3)), catalog)
    msg = rejected_fully(d, detail("98138", 0, (1, 0, 3), mirror=True), catalog)
    assert "its mirror image at x=6, y=0, z=3" in msg and "already taken" in msg
    msg = rejected_fully(d, detail("98138", 0, (6, 0, 3), mirror=True), catalog)
    assert "The Black Tile 1 x 1 Round with Groove (98138) at x=6, y=0, z=3" in msg
    assert "already taken" in msg


# ---- remove_detail --------------------------------------------------------------------------


def test_remove_detail_by_any_cell_it_covers(catalog):
    for cell in [(2, 2, 3), (3, 3, 3), (2, 3, 3), (3, 2, 5)]:
        d = table()
        one(d, detail("6143", 0, (2, 2, 3)), catalog)  # round brick 2x2, 3 plates tall
        r = one(d, undetail(cell), catalog)
        assert r.applied and r.cells_changed == 0 and d.details == []
        assert "Removed the Black Brick 2 x 2 Round Reinforced (6143) at x=2, y=2, z=3" in r.message
        assert d.log[-1] == undetail(cell)


def test_remove_detail_where_there_is_none(catalog):
    d = table()
    msg = rejected_fully(d, undetail((1, 0, 3)), catalog)
    assert "No detail part covers x=1, y=0, z=3" in msg and "no detail parts" in msg
    one(d, detail("98138", 0, (5, 5, 3)), catalog)
    msg = rejected_fully(d, undetail((1, 0, 3)), catalog)
    assert "The detail parts now are: the Black Tile 1 x 1 Round with Groove (98138)" in msg
    assert "x=5, y=5, z=3" in msg
    msg = rejected_fully(d, undetail((5, 5, 4)), catalog)
    assert "No detail part covers x=5, y=5, z=4" in msg


def test_remove_detail_lists_at_most_a_dozen_details(catalog):
    d = Design(colors=np.full((10, 10, 4), EMPTY, dtype=np.int16))
    d.colors[:, :, 0] = GREY
    apply_ops(d, [detail("98138", 0, (x, y, 1)) for x in range(5) for y in range(4)], catalog)
    assert len(d.details) == 20
    msg = rejected_fully(d, undetail((9, 9, 1)), catalog)
    assert "and 8 more" in msg and len(msg) < 2000


def test_remove_detail_needs_at(catalog):
    msg = rejected_fully(table(), {"op": "remove_detail"}, catalog)
    assert '"remove_detail" needs "at"' in msg
    msg = rejected_fully(table(), {**undetail((1, 0, 3)), "part": "98138"}, catalog)
    assert 'unexpected field "part"' in msg and '"op", "at", and optionally "mirror"' in msg
    assert "Did you mean" not in msg  # "part" belongs to place_detail; "at" would mislead


def test_remove_detail_with_mirror_removes_both(catalog):
    d = table()
    one(d, detail("98138", 0, (1, 0, 3), mirror=True), catalog)
    one(d, detail("98138", 15, (3, 3, 3)), catalog)
    r = one(d, undetail((1, 0, 3), mirror=True), catalog)
    assert r.applied and d.details == [Detail("98138", 15, 3, 3, 3, 0)]
    assert "and its mirror image, the Black Tile" in r.message and "x=6, y=0, z=3" in r.message


def test_remove_detail_with_mirror_when_only_one_side_has_one(catalog):
    d = table()
    one(d, detail("98138", 0, (1, 0, 3)), catalog)
    r = one(d, undetail((1, 0, 3), mirror=True), catalog)
    assert r.applied and d.details == []
    assert "No detail part covers the mirrored cell x=6, y=0, z=3" in r.message
    d = table()
    one(d, detail("98138", 0, (6, 0, 3)), catalog)
    r = one(d, undetail((1, 0, 3), mirror=True), catalog)
    assert r.applied and d.details == [] and "its mirror image did" in r.message
    msg = rejected_fully(d, undetail((1, 0, 3), mirror=True), catalog)
    assert "or its mirror image x=6, y=0, z=3" in msg


def test_remove_detail_with_mirror_of_a_detail_on_the_middle(catalog):
    d = table()
    one(d, detail("3068b", 0, (3, 1, 3)), catalog)
    r = one(d, undetail((3, 1, 3), mirror=True), catalog)
    assert r.applied and d.details == [] and "covers its own mirror image" in r.message


# ---- details never dangle -------------------------------------------------------------------


def test_add_into_a_detail_removes_it(catalog):
    d = table()
    one(d, detail("98138", 0, (1, 0, 3)), catalog)
    one(d, detail("98138", 0, (5, 0, 3)), catalog)
    r = one(d, add(B((0, 0, 3), (2, 2, 3)), RED), catalog)
    assert r.applied and d.details == [Detail("98138", 0, 5, 0, 3, 0)]
    assert (
        "This also removed the Black Tile 1 x 1 Round with Groove (98138) at x=1, y=0, z=3, "
        "because a cell it stood in is now filled." in r.message
    )


def test_add_into_the_upper_cells_of_a_tall_detail_removes_it(catalog):
    d = table()
    one(d, detail("59900", 0, (1, 0, 3)), catalog)  # a cone, 3 plates tall
    r = one(d, add(B((1, 0, 5), (1, 0, 5)), RED), catalog)
    assert r.applied and d.details == [] and "also removed" in r.message


def test_removing_the_cells_under_a_detail_removes_it(catalog):
    d = table()
    one(d, detail("3069b", 0, (1, 0, 3)), catalog)  # stands on x 1..2
    r = one(d, remove(B((2, 0, 2), (2, 0, 2))), catalog)  # only one of the two cells below
    assert r.applied and d.details == []
    assert "because a cell it stood on is now empty" in r.message


def test_removing_two_details_names_both(catalog):
    d = table()
    one(d, detail("98138", 0, (1, 0, 3), mirror=True), catalog)
    r = one(d, {**remove(B((1, 0, 2), (1, 0, 2))), "mirror": True}, catalog)
    assert d.details == [] and "This also removed 2 details" in r.message
    assert "x=1, y=0, z=3" in r.message and "x=6, y=0, z=3" in r.message


def test_edits_that_leave_a_detail_supported_keep_it(catalog):
    d = table()
    one(d, detail("98138", 0, (1, 0, 3)), catalog)
    ops = [
        add(B((2, 0, 3), (2, 0, 5)), RED),  # beside it
        add(B((1, 0, 4), (1, 0, 4)), RED),  # above it (not in it)
        remove(B((1, 0, 0), (1, 0, 1))),  # under it, but not directly below
        remove(B((5, 5, 2), (5, 5, 2))),  # elsewhere
        paint(B((0, 0, 0), (7, 5, 11)), BLUE),
        finish_op(B((0, 0, 0), (7, 5, 11)), "smooth"),
    ]
    results = apply_ops(d, ops, catalog)
    assert all(r.applied for r in results), [r.message for r in results]
    assert d.details == [Detail("98138", 0, 1, 0, 3, 0)]
    assert not any("also removed" in r.message for r in results)


def test_an_unknown_detail_part_already_in_the_design_is_left_alone(catalog):
    d = table()
    d.details.append(Detail("no-such-part", 0, 1, 0, 3, 0))
    r = one(d, add(B((0, 0, 3), (3, 3, 3)), RED), catalog)
    assert r.applied and len(d.details) == 1
    assert "No detail part covers" in rejected(d, undetail((1, 0, 3)), catalog)


# ---- log and replay with the stage 2 operations ---------------------------------------------


def stage2_ops() -> list[dict[str, Any]]:
    return [
        finish_op(B((0, 0, 2), (1, 5, 2)), "smooth", mirror=True),
        detail("98138", 0, (2, 0, 3), mirror=True),
        detail("3040b", 4, (0, 3, 3), rot=90, mirror=True),
        detail("98138", 0, (2, 0, 3)),  # rejected: taken
        add(E((3.5, 3, 5), (1, 1, 2)), ORANGE),
        {**remove(B((2, 0, 2), (2, 0, 2))), "mirror": True},  # drops both eyes
        undetail((7, 3, 4)),
        finish_op(B((0, 0, 0), (7, 5, 11)), "sloped"),
        detail("3068b", 15, (3, 0, 3)),
        {**paint(B((0, 0, 0), (2, 5, 1)), BLUE), "mirror": True},
    ]


def test_stage2_log_holds_exactly_the_applied_operations(catalog):
    d = table()
    ops = stage2_ops()
    given = copy.deepcopy(ops)
    results = apply_ops(d, ops, catalog)
    assert [r.applied for r in results] == [True] * 3 + [False] + [True] * 6, [
        r.message for r in results
    ]
    assert d.log == [ops[r.index] for r in results if r.applied]
    assert ops == given
    assert d.details == [
        Detail("3040b", 4, 0, 3, 3, 90),
        Detail("3068b", 15, 3, 0, 3, 0),
    ]


def test_replay_reproduces_details_finishes_and_mirrors(catalog, tmp_path):
    base = table()
    d = base.copy()
    apply_ops(d, stage2_ops(), catalog)
    assert len(d.details) == 2 and d.finish is not None and d.finish.any()
    assert any(op.get("mirror") for op in d.log)
    again = replay(base, d.log, catalog)
    assert_same(again, d)
    d.save(tmp_path / "d.npz", tmp_path / "d.json")
    loaded = Design.load(tmp_path / "d.npz", tmp_path / "d.json")
    assert_same(replay(base, loaded.log, catalog), loaded)
    for n in range(len(d.log) + 1):  # every prefix replays (undo)
        replay(base, d.log[:n], catalog)


def test_random_stage2_sequences_replay_exactly(catalog):
    rng = random.Random(7)
    parts = catalog.detail_parts()
    seen: dict[str, int] = {"placed": 0, "dropped": 0, "removed": 0, "mirrored": 0}
    for _ in range(30):
        base = table()
        d = base.copy()
        for _ in range(25):
            roll = rng.random()
            x, y = rng.randrange(8), rng.randrange(6)
            mirror = rng.random() < 0.4
            if roll < 0.3:
                part = rng.choice(parts)
                op = detail(
                    part.id,
                    min(part.colours),
                    (x, y, rng.choice([3, 4])),
                    rot=rng.choice(ROTATIONS),
                    mirror=mirror,
                )
            elif roll < 0.4:
                spot = rng.choice(d.details) if d.details else None
                op = undetail((spot.x, spot.y, spot.z) if spot else (x, y, 3), mirror=mirror)
            elif roll < 0.6:
                z = rng.randrange(1, 5)
                op = {**add(B((x, y, z), (x + 1, y, z)), RED), "mirror": mirror}
            elif roll < 0.8:
                z = rng.randrange(0, 4)
                op = {**remove(B((x, y, z), (x, y + 1, z))), "mirror": mirror}
            else:
                op = finish_op(
                    B((x, y, 0), (x, y, 5)), rng.choice(list(FINISH_NAMES)), mirror=mirror
                )
            (r,) = apply_ops(d, [op], catalog)
            seen["placed"] += r.applied and op["op"] == "place_detail"
            seen["removed"] += r.applied and op["op"] == "remove_detail"
            seen["dropped"] += "also removed" in r.message
            seen["mirrored"] += r.applied and op.get("mirror", False)
            for det in d.details:  # never dangling, never overlapping the grid
                cells = covered(catalog, det)
                assert all(d.colors[c] == EMPTY for c in cells)
                assert all(d.colors[c[0], c[1], det.z - 1] != EMPTY for c in cells if c[2] == det.z)
        assert_same(replay(base, d.log, catalog), d)
    assert min(seen.values()) >= 5, seen  # every kind of change really happened


def test_a_log_saved_by_stage_1_still_replays(catalog):
    """These operations and this base were written by stage 1; the result must not change."""
    log = json.loads(
        '[{"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [5, 0, 2]}, '
        '"color": 4}, {"op": "add", "shape": {"type": "ellipsoid", "center": [2.5, 2, 4.5], '
        '"radius": [1.5, 1.5, 2]}, "color": 25}, {"op": "remove", "shape": {"type": "box", '
        '"min": [0, 4, 0], "max": [5, 4, 0]}}, {"op": "add", "shape": {"type": "box", "min": '
        '[0, 0, 8], "max": [0, 0, 8]}, "color": 4.0}]'
    )
    out = replay(half_box(), log, catalog)
    assert out.log == log and out.details == []
    # counts and a hash of the cells, as stage 1's code produced them
    assert int((out.colors == RED).sum()) == 19 and int((out.colors == ORANGE).sum()) == 16
    assert int(out.filled.sum()) == 101
    digest = hashlib.sha256(out.colors.astype("<i2").tobytes()).hexdigest()[:16]
    assert digest == "a16e1c67d0e56b46"
    assert out.finish is not None and not out.finish.any()


# ---- OP_SCHEMA for the stage 2 operations ---------------------------------------------------


def _variant(name: str) -> dict[str, Any]:
    (v,) = [v for v in OP_SCHEMA["anyOf"] if v["properties"]["op"]["const"] == name]
    return v


def test_schema_lists_exactly_the_fields_the_code_accepts(catalog):
    from bricksnap.design import _OP_FIELDS, _OPTIONAL_FIELDS

    assert OP_SCHEMA["required"] == ["op"]
    for name in OPS:
        v = _variant(name)
        assert set(v["properties"]) == set(_OP_FIELDS[name])
        assert set(v["required"]) == set(_OP_FIELDS[name]) - set(_OPTIONAL_FIELDS)
        assert v["properties"]["mirror"] == {"type": "boolean"}


def test_schema_lists_the_finish_words_detail_parts_and_rotations(catalog):
    assert _variant("set_finish")["properties"]["finish"]["enum"] == list(FINISH_NAMES)
    props = _variant("place_detail")["properties"]
    assert props["part"]["enum"] == [p.id for p in catalog.detail_parts()]
    assert props["rot"]["enum"] == [0, 90, 180, 270] == list(ROTATIONS)
    assert sorted(props["color"]["enum"]) == sorted(catalog.colours)
    for p in catalog.detail_parts():
        assert f"{p.id} {p.name} ({p.sx}x{p.sz}, " in props["part"]["description"]
    assert "runs down towards the right (+x) at 90" in props["rot"]["description"]
    assert "slopes run down towards the front (-y) at rot 0" in props["part"]["description"]
    for name in ("remove", "paint", "set_finish"):  # same shape rules as add, no descriptions
        assert json.dumps(_variant(name)["properties"]["shape"]["anyOf"]) == json.dumps(
            _strip(OP_SCHEMA["anyOf"][0]["properties"]["shape"]["anyOf"])
        )
    assert "mirror" in OP_SCHEMA["description"] and "nx-1-x" in OP_SCHEMA["description"]


def _strip(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip(v) for k, v in schema.items() if k != "description"}
    if isinstance(schema, list):
        return [_strip(v) for v in schema]
    return schema


def test_schema_stays_reasonably_small():
    assert len(json.dumps(OP_SCHEMA)) < 10_000


VALID_STAGE2: list[Any] = [
    finish_op(B((0, 0, 0), (3, 3, 2)), "smooth"),
    finish_op(E((4, 4, 6), (2, 2, 3)), "sloped", mirror=True),
    finish_op(B((0, 0, 0), (3, 3, 2)), "studs", mirror=False),
    detail("98138", 0, (1, 0, 3)),
    detail("3040b", 4, (1, 2, 3), rot=90, mirror=True),
    detail("6143", 15, (2, 2, 3), rot=0.0),
    detail("3069b", 0.0, (1.0, 2, 3), rot=270),
    undetail((1, 0, 3)),
    undetail((1, 0, 3), mirror=True),
    {**add(B((0, 0, 3), (1, 1, 4))), "mirror": True},
    {**remove(B((0, 0, 0), (1, 7, 2))), "mirror": False},
    {**paint(E((2, 2, 2), (1, 1, 1)), BLUE), "mirror": True},
]

INVALID_STAGE2: list[Any] = [
    {"op": "set_finish", "shape": B((0, 0, 0), (1, 1, 1))},
    finish_op(B((0, 0, 0), (1, 1, 1)), "tiles"),
    finish_op(B((0, 0, 0), (1, 1, 1)), 1),
    {**finish_op(B((0, 0, 0), (1, 1, 1))), "color": 4},
    {"op": "set_finish", "finish": "smooth"},
    detail("3001", 4),
    detail(98138, 0),
    detail("98138", 999),
    detail("98138", 0, rot=45),
    detail("98138", 0, rot=-90),
    detail("98138", 0, at=(1.5, 0, 3)),
    {"op": "place_detail", "part": "98138", "color": 0},
    {"op": "place_detail", "part": "98138", "at": [1, 0, 3]},
    {**detail(), "rotation": 90},
    {**detail(), "mirror": 1},
    {"op": "remove_detail"},
    {"op": "remove_detail", "at": [1, 0]},
    {**undetail((1, 0, 3)), "color": 0},
    {**add(B((0, 0, 0), (1, 1, 1))), "mirror": "yes"},
    {"op": "mirror", "shape": B((0, 0, 0), (1, 1, 1))},
]


@pytest.mark.parametrize("op", VALID_STAGE2)
def test_schema_and_apply_ops_accept_valid_stage2_operations(catalog, op):
    assert schema_valid(op, OP_SCHEMA)
    validate_op(op, catalog)


@pytest.mark.parametrize("op", INVALID_STAGE2)
def test_schema_and_apply_ops_reject_invalid_stage2_operations(catalog, op):
    assert not schema_valid(op, OP_SCHEMA)
    with pytest.raises(ValueError):
        validate_op(op, catalog)
    assert one(table(), op, catalog).message.startswith("Rejected:")


def test_schema_agrees_with_validation_on_random_stage2_operations(catalog):
    """As for stage 1. The schema cannot say which colours a part is made in, so only that
    and "min <= max" may pass the schema and still be rejected."""
    rng = random.Random(2026)
    disagreements = []
    accepted = 0
    for _ in range(5000):
        op = _mutations(rng, copy.deepcopy(rng.choice(VALID_STAGE2)))
        if isinstance(op, dict) and rng.random() < 0.2:
            op[rng.choice(["mirror", "rot", "part", "finish", "at"])] = rng.choice(
                [True, 0, 90, 45, "98138", "3001", "smooth", "tiles", [1, 0, 3], None]
            )
        try:
            validate_op(op, catalog)
            ok, message = True, ""
        except ValueError as err:
            ok, message = False, str(err)
        accepted += ok
        in_schema = schema_valid(op, OP_SCHEMA)
        if ok and not in_schema:
            disagreements.append(("apply_ops accepts but schema rejects", op))
        if (
            in_schema
            and not ok
            and "is not made in" not in message
            and ("min is greater than its max" not in message)
        ):
            disagreements.append(("schema accepts but apply_ops rejects", op, message))
    assert not disagreements, disagreements[:5]
    assert accepted > 300


_OP_IN_TEXT = re.compile(r'\{"op": ')


def _examples_in(text: str) -> list[Any]:
    """Every JSON object written as {"op": ...} inside a message."""
    found = []
    for m in _OP_IN_TEXT.finditer(text):
        depth = 0
        for end in range(m.start(), len(text)):
            depth += {"{": 1, "}": -1}.get(text[end], 0)
            if depth == 0:
                found.append(json.loads(text[m.start() : end + 1]))
                break
    return found


def _stage2_messages(catalog) -> list[str]:
    messages = []
    d = table()
    one(d, detail("3068b", 0, (2, 2, 3)), catalog)
    for op in INVALID_STAGE2 + [
        detail("98138", 0, (3, 3, 3)),  # taken
        detail("98138", 0, (1, 0, 1)),  # filled, with a suggestion
        detail("98138", 0, (1, 0, 7)),  # nothing below, with a suggestion
        undetail((7, 5, 3)),
        detail("98138", 0, (5, 2, 3), mirror=True),  # mirror image taken
        {"op": "fill"},
        {},
    ]:
        messages.append(one(d.copy(), op, catalog).message)
    return messages


def test_every_example_in_a_message_is_a_valid_operation(catalog):
    examples = [e for msg in _stage2_messages(catalog) for e in _examples_in(msg)]
    assert len(examples) >= 4
    for e in examples:
        assert schema_valid(e, OP_SCHEMA), e
        validate_op(e, catalog)
    suggested = [
        m for msg in _stage2_messages(catalog) for m in re.findall(r'"at": \[[-\d, ]+\]', msg)
    ]
    assert suggested
    for text in suggested:
        op = {**detail(), **json.loads("{" + text + "}")}
        assert schema_valid(op, OP_SCHEMA)
        validate_op(op, catalog)


def test_suggested_positions_really_fit(catalog):
    d = table()
    for at in [(1, 0, 1), (1, 0, 0), (1, 0, 7), (4, 4, 9)]:
        msg = rejected_fully(d, detail("98138", 0, at), catalog)
        (text,) = re.findall(r'"at": (\[[-\d, ]+\]) would fit', msg)
        assert one(d.copy(), detail("98138", 0, json.loads(text)), catalog).applied


def test_stage2_messages_have_no_tracebacks_and_use_plain_coordinates(catalog):
    for msg in _stage2_messages(catalog):
        assert "Traceback" not in msg and "Error" not in msg
        assert "(1, 0, 3)" not in msg  # coordinates are written x=…, y=…, z=…


# ---- stage 4: details on a face (sideways) --------------------------------------------------


def wall() -> Design:
    """An 8 x 6 x 12 grid: a grey block at x 1..6, y 1..4, z 0..5 (two brick courses), so its
    front face is at y = 1 and the column in front of it at y = 0; mirror x -> 7 - x."""
    colors = np.full((8, 6, 12), EMPTY, dtype=np.int16)
    colors[1:7, 1:5, :6] = GREY
    return Design(colors=colors)


def side(at=(2, 0, 3), face="front", part="98138", **extra) -> dict[str, Any]:
    return detail(part=part, at=at, face=face, **extra)


def test_a_detail_can_lie_on_a_face(catalog):
    d = wall()
    r = one(d, side(), catalog)
    assert r.applied, r.message
    assert d.details == [Detail("98138", 0, 2, 0, 3, 0, "front")]
    assert "on the front face" in r.message and "x=2, y=1, z=3..5" in r.message
    assert d.log == [side()]
    assert replay(wall(), d.log, catalog).details == d.details


def test_a_detail_on_each_face_and_its_column(catalog):
    for at, face in (
        ((2, 0, 3), "front"),
        ((7, 2, 0), "right"),
        ((3, 5, 0), "back"),
        ((0, 2, 3), "left"),
    ):
        d = wall()
        r = one(d, side(at=at, face=face), catalog)
        assert r.applied, (face, r.message)
        p = Placement("98138", 0, *at, face=face)
        assert catalog.footprint(p) == (1, 1, 3)


def test_a_sideways_detail_must_sit_in_a_brick_course(catalog):
    msg = rejected_fully(wall(), side(at=(2, 0, 4)), catalog)
    assert "multiple of 3" in msg and "z=3 or z=6" in msg
    assert '"at": [2, 0, 3] with "face": "front" would fit' in msg


def test_a_sideways_detail_needs_its_column_empty(catalog):
    msg = rejected_fully(wall(), side(at=(2, 1, 3)), catalog)
    assert "x=2, y=1, z=3 is filled" in msg
    assert '"at": [2, 0, 3]' in msg


def test_a_sideways_detail_needs_the_cells_behind_it_filled(catalog):
    msg = rejected_fully(wall(), side(at=(2, 0, 6)), catalog)
    assert "x=2, y=1, z=6..8" in msg and "z=6, z=7, z=8 are empty" in msg
    assert '"at": [2, 0, 3]' in msg  # the nearest course that works


def test_a_sideways_detail_needs_a_side_stud_brick_in_that_colour(catalog):
    d = wall()
    d.colors[2, 1, 3:6] = 31  # Lavender: 87087 is not made in it
    msg = rejected_fully(d, side(), catalog)
    assert "87087" in msg and "not made in that colour" in msg and "Paint those three cells" in msg


def test_the_cells_behind_a_sideways_detail_must_be_one_colour(catalog):
    d = wall()
    d.colors[2, 1, 4] = 4  # red between grey: the brick would be two colours
    msg = rejected_fully(d, side(), catalog)
    assert (
        "not one colour (z=3 Light Bluish Grey (71), z=4 Red (4), z=5 Light Bluish Grey (71))"
        in msg
    )
    fix = (
        '{"op": "paint", "shape": {"type": "box", "min": [2, 1, 3], "max": [2, 1, 5]}, "color": 71}'
    )
    assert fix in msg
    assert one(d, json.loads(fix), catalog).applied
    r = one(d, side(), catalog)
    assert r.applied and "a Light Bluish Grey (71) brick with a stud on its side" in r.message


def test_only_one_stud_one_plate_details_may_face_sideways(catalog):
    msg = rejected_fully(wall(), side(part="59900"), catalog)
    assert "cannot lie on a face" in msg
    for pid in ("98138", "3070b", "6141"):
        assert pid in msg
    assert "60897" not in msg


def test_a_sideways_detail_takes_no_turn(catalog):
    msg = rejected_fully(wall(), side(rot=90), catalog)
    assert '"rot": 0' in msg


def test_an_unknown_face_is_explained(catalog):
    msg = rejected_fully(wall(), side(face="forward"), catalog)
    assert '"face" must be' in msg and 'Did you mean "front"?' in msg
    assert validate_op(side(face="left"), catalog) is None


def test_one_brick_holds_one_sideways_detail(catalog):
    d = wall()
    assert one(d, side(at=(1, 0, 3)), catalog).applied
    msg = rejected_fully(d, side(at=(0, 1, 3), face="left"), catalog)
    assert "already holds" in msg


def test_a_mirrored_sideways_detail_swaps_left_and_right(catalog):
    d = wall()
    r = one(d, side(mirror=True), catalog)
    assert r.applied, r.message
    assert [(x.x, x.face) for x in d.details] == [(2, "front"), (5, "front")]
    d = wall()
    r = one(d, side(at=(0, 2, 3), face="left", mirror=True), catalog)
    assert r.applied, r.message
    assert [(x.x, x.face) for x in d.details] == [(0, "left"), (7, "right")]


def test_a_sideways_detail_goes_when_its_column_fills_or_its_brick_empties(catalog):
    d = wall()
    one(d, side(), catalog)
    r = one(
        d,
        {"op": "add", "shape": {"type": "box", "min": [2, 0, 5], "max": [2, 0, 5]}, "color": GREY},
        catalog,
    )
    assert r.applied and d.details == [] and "is now filled" in r.message
    d = wall()
    one(d, side(), catalog)
    r = one(
        d, {"op": "remove", "shape": {"type": "box", "min": [2, 1, 5], "max": [2, 1, 5]}}, catalog
    )
    assert r.applied and d.details == [] and "brick behind it" in r.message
    d = wall()
    one(d, side(), catalog)
    one(
        d, {"op": "remove", "shape": {"type": "box", "min": [4, 1, 5], "max": [4, 1, 5]}}, catalog
    )  # elsewhere
    assert len(d.details) == 1


def test_remove_detail_finds_a_sideways_detail_by_any_cell_of_its_column(catalog):
    d = wall()
    one(d, side(), catalog)
    r = one(d, undetail((2, 0, 5)), catalog)
    assert r.applied and d.details == [] and "on the front face" in r.message


def test_the_schema_offers_the_face(catalog):
    place = next(s for s in OP_SCHEMA["anyOf"] if s["properties"]["op"]["const"] == "place_detail")
    assert place["properties"]["face"]["enum"] == ["top", "front", "right", "back", "left"]
    assert "face" not in place["required"]


def test_the_brick_behind_a_sideways_detail_needs_the_model_above_or_below_it(catalog):
    d = wall()
    d.colors[:, :, 3:] = EMPTY  # one course: a brick there would be held by nothing
    msg = rejected_fully(d, side(at=(2, 0, 0)), catalog)
    assert "nothing directly above or below" in msg


def test_a_sideways_detail_and_an_upright_one_never_share_a_cell(catalog):
    d = wall()
    d.colors[1:7, 0, :3] = GREY  # a ledge in front of the bottom course
    assert one(d, detail(at=(2, 0, 3)), catalog).applied  # upright, on the ledge
    msg = rejected_fully(d, side(), catalog)
    assert "is already taken by" in msg
    d = wall()
    d.colors[1:7, 0, :3] = GREY
    assert one(d, side(), catalog).applied
    msg = rejected_fully(d, detail(at=(2, 0, 3)), catalog)
    assert "is already taken by" in msg
