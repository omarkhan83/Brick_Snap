"""Tests for bricksnap.design: the edit operations, the log, replay, shape masks, OP_SCHEMA."""

from __future__ import annotations

import copy
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
    OpResult,
    apply_ops,
    replay,
    shape_mask,
    validate_op,
)
from bricksnap.types import EMPTY, FINISH_SMOOTH, FINISH_STUDS, Design, Detail

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
    assert [v["properties"]["op"]["const"] for v in variants] == ["add", "remove", "paint"]
    for v in variants:
        assert v["additionalProperties"] is False
        assert "op" in v["required"] and "shape" in v["required"]
        assert ("color" in v["required"]) == (v["properties"]["op"]["const"] != "remove")


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
