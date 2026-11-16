"""Tests for bricksnap.checks: Build to Report.

Builds are written by hand as lists of Placement so these tests do not depend on the layout
solver. Part ids used: 3005 brick 1x1, 3003 brick 2x2, 3001 brick 2x4 (4 along part X),
3024 plate 1x1, 3460 plate 1x8, 3070b tile 1x1 (no studs).
"""

from __future__ import annotations

import re
import time

import numpy as np
import pytest

from bricksnap.checks import _footprint_distance, check
from bricksnap.types import Build, Placement, Report

RED, BLUE, GREY = 4, 1, 71


def P(part: str, x: int, y: int, z: int, rot: int = 0, color: int = RED) -> Placement:
    return Placement(part, color, x, y, z, rot=rot)


def positions_in(text: str) -> list[tuple[int, int, int]]:
    return [(int(a), int(b), int(c)) for a, b, c in re.findall(r"x=(\d+), y=(\d+), z=(\d+)", text)]


# ---- empty and sound --------------------------------------------------------------------------


def test_empty_build(catalog):
    r = check(Build(shape=(4, 4, 6)), catalog)
    assert isinstance(r, Report)
    assert not r.ok
    assert r.part_count == 0
    assert r.components == 0
    assert not r.grounded and not r.stands
    assert r.loose == [] and r.weak_spots == []
    assert r.text == "The build has no parts."


def test_sound_stack(catalog):
    # three 2x4 bricks, each shifted so it holds the one below with several studs
    build = Build(
        shape=(8, 4, 12),
        parts=[P("3001", 0, 0, 0), P("3001", 2, 0, 3, color=BLUE), P("3001", 0, 0, 6)],
    )
    r = check(build, catalog)
    assert r.ok
    assert r.part_count == 3
    assert r.components == 1
    assert r.loose == []
    assert r.grounded and r.stands
    assert r.collisions == [] and r.out_of_bounds == [] and r.unknown_parts == []
    assert r.weak_spots == []
    # cells: 24 each; centres x = 2, 4, 2; y = 1; z = 1.5, 4.5, 7.5
    assert r.centre_of_mass == pytest.approx((8 / 3, 1.0, 4.5))
    assert r.text.splitlines()[0] == "OK: 3 parts in one connected piece; it stands."


def test_single_part_centre_is_cell_centre(catalog):
    r = check(Build(shape=(2, 2, 3), parts=[P("3024", 0, 0, 0)]), catalog)
    assert r.ok
    assert r.centre_of_mass == pytest.approx((0.5, 0.5, 0.5))
    assert r.text == "OK: 1 part in one connected piece; it stands."


def test_rotated_part_footprint_used(catalog):
    # a 2x4 turned 90 degrees covers 2 in x and 4 in y
    r = check(Build(shape=(2, 4, 3), parts=[P("3001", 0, 0, 0, rot=90)]), catalog)
    assert r.ok
    assert r.centre_of_mass == pytest.approx((1.0, 2.0, 1.5))


def test_report_round_trips_through_json(catalog):
    build = Build(shape=(8, 4, 12), parts=[P("3001", 0, 0, 0), P("3001", 2, 0, 3)])
    r = check(build, catalog)
    assert Report.from_json(r.to_json()) == r


# ---- pieces, loose parts, ground -----------------------------------------------------------


def test_two_towers_side_by_side_are_two_pieces(catalog):
    # left tower: two 2x2 bricks; right tower: three 2x2 bricks, touching sideways only
    parts = [
        P("3003", 0, 0, 0),
        P("3003", 0, 0, 3),
        P("3003", 2, 0, 0, color=BLUE),
        P("3003", 2, 0, 3, color=BLUE),
        P("3003", 2, 0, 6, color=BLUE),
    ]
    r = check(Build(shape=(4, 2, 12), parts=parts), catalog)
    assert not r.ok
    assert r.components == 2
    # both towers touch the ground; the taller one has more cells so it is the main piece
    assert r.loose == [0, 1]
    assert r.grounded and r.stands
    assert r.collisions == []
    first = r.text.splitlines()[0]
    assert first.startswith("NOT BUILDABLE: ")
    assert "the parts form 2 separate pieces with 2 loose parts" in first
    assert "2 parts are not attached through studs to the main piece of 3 parts" in r.text
    assert "Red Brick 2 x 2 (3003) at x=0, y=0, z=0" in r.text
    assert "Red Brick 2 x 2 (3003) at x=0, y=0, z=3" in r.text


def test_main_piece_tie_goes_to_lowest_index(catalog):
    parts = [P("3005", 0, 0, 0), P("3005", 2, 0, 0)]
    r = check(Build(shape=(3, 1, 3), parts=parts), catalog)
    assert r.components == 2
    assert r.loose == [1]


def test_main_piece_is_the_one_with_most_cells_not_most_parts(catalog):
    # three 1x1 plates stacked (3 parts, 3 cells) against one 2x4 brick (1 part, 24 cells)
    parts = [P("3024", 5, 0, 0), P("3024", 5, 0, 1), P("3024", 5, 0, 2), P("3001", 0, 0, 0)]
    r = check(Build(shape=(6, 2, 3), parts=parts), catalog)
    assert r.components == 2
    assert r.loose == [0, 1, 2]
    assert r.centre_of_mass == pytest.approx((2.0, 1.0, 1.5))


def test_unknown_part_on_the_ground_gives_no_ground_contact(catalog):
    # the only part at z=0 has an id that is not in the parts table: the real bricks above it
    # float, and they (not the zero-cell unknown part) are the main piece
    parts = [P("nope", 0, 0, 0), P("3001", 0, 0, 3), P("3001", 0, 0, 6)]
    r = check(Build(shape=(4, 4, 12), parts=parts), catalog)
    assert not r.ok
    assert r.unknown_parts == [0]
    assert r.loose == [0]
    assert not r.grounded and not r.stands
    assert r.centre_of_mass == pytest.approx((2.0, 1.0, 6.0))
    first = r.text.splitlines()[0]
    assert "does not touch the ground" in first
    assert "tip over" not in r.text
    assert "its lowest part is the Red Brick 2 x 4 (3001) at x=0, y=0, z=3" in r.text


def test_only_unknown_parts_does_not_talk_about_the_ground(catalog):
    r = check(Build(shape=(4, 4, 6), parts=[P("nope", 0, 0, 0)]), catalog)
    assert not r.ok
    assert r.unknown_parts == [0]
    assert not r.grounded
    assert r.text.splitlines()[0] == "NOT BUILDABLE: 1 part; 1 part is not in the parts table."


@pytest.mark.parametrize("height", [3, 6])
def test_part_turned_by_an_impossible_angle_is_reported(catalog, height):
    # with and without room above the part: either way a Report comes back, not an error
    build = Build(shape=(4, 4, height), parts=[P("3001", 0, 0, 0, rot=45)])
    r = check(build, catalog)
    assert isinstance(r, Report)
    assert not r.ok
    assert r.unknown_parts == [0]
    first = r.text.splitlines()[0]
    assert first.startswith("NOT BUILDABLE: 1 part; ")
    assert "turned by an angle" in first
    assert "Red Brick 2 x 4 (3001) at x=0, y=0, z=0 (turned 45 degrees)" in r.text
    assert "0, 90, 180 or 270 degrees" in r.text
    assert "colour" not in r.text
    assert "Traceback" not in r.text


def test_impossible_angle_among_good_parts(catalog):
    # the badly turned part holds nothing and weighs nothing; the rest is still checked
    parts = [P("3001", 0, 0, 0), P("3001", 0, 0, 3), P("3003", 0, 0, 6, rot=30)]
    r = check(Build(shape=(4, 4, 12), parts=parts), catalog)
    assert not r.ok
    assert r.unknown_parts == [2]
    assert r.loose == [2]
    assert r.grounded and r.stands
    assert r.centre_of_mass == pytest.approx((2.0, 1.0, 3.0))
    assert "1 part is turned by an angle that is not a quarter turn, so it cannot" in r.text
    two = check(
        Build(shape=(4, 4, 6), parts=[P("3005", 0, 0, 0, rot=10), P("3005", 1, 0, 0, rot=-45)]),
        catalog,
    )
    assert two.unknown_parts == [0, 1]
    assert "2 parts are turned by an angle that is not a quarter turn, so they cannot" in two.text
    assert "(turned -45 degrees)" in two.text
    # quarter turns written as other multiples of 90 are fine
    ok = check(Build(shape=(4, 2, 3), parts=[P("3001", 0, 0, 0, rot=360)]), catalog)
    assert ok.ok


def test_part_floating_in_mid_air(catalog):
    parts = [P("3003", 0, 0, 0), P("3003", 0, 0, 3), P("3005", 4, 4, 9, color=BLUE)]
    r = check(Build(shape=(6, 6, 12), parts=parts), catalog)
    assert not r.ok
    assert r.components == 2
    assert r.loose == [2]
    assert r.grounded  # the main piece is on the ground
    assert "Blue Brick 1 x 1 (3005) at x=4, y=4, z=9" in r.text
    assert "1 part is not attached" in r.text


def test_grounded_piece_beats_bigger_floating_piece(catalog):
    parts = [P("3005", 0, 0, 0), P("3001", 0, 0, 6), P("3001", 0, 0, 9)]
    r = check(Build(shape=(4, 2, 12), parts=parts), catalog)
    assert r.loose == [1, 2]
    assert r.grounded


def test_nothing_touches_the_ground(catalog):
    parts = [P("3003", 0, 0, 3), P("3003", 0, 0, 6), P("3005", 3, 3, 9)]
    r = check(Build(shape=(4, 4, 12), parts=parts), catalog)
    assert not r.ok
    assert not r.grounded
    assert not r.stands
    assert r.loose == [2]  # the bigger floating piece is the main one
    assert "does not touch the ground" in r.text
    assert "its lowest part is the Red Brick 2 x 2 (3003) at x=0, y=0, z=3" in r.text
    assert "tip over" not in r.text


def test_tile_has_no_studs_so_part_above_is_not_connected(catalog):
    parts = [P("3005", 0, 0, 0), P("3070b", 0, 0, 3, color=GREY), P("3005", 0, 0, 4)]
    r = check(Build(shape=(1, 1, 8), parts=parts), catalog)
    assert not r.ok
    assert r.components == 2
    assert r.loose == [2]  # the tile sits on the brick, but nothing holds on to the tile
    assert "Red Brick 1 x 1 (3005) at x=0, y=0, z=4" in r.text


# ---- collisions, grid, catalogue -------------------------------------------------------------


def test_overlapping_parts(catalog):
    parts = [P("3003", 0, 0, 0), P("3003", 1, 1, 0, color=BLUE)]
    r = check(Build(shape=(4, 4, 3), parts=parts), catalog)
    assert not r.ok
    assert r.collisions == [(0, 1)]
    assert "1 pair of parts overlaps" in r.text.splitlines()[0]
    assert (
        "the Red Brick 2 x 2 (3003) at x=0, y=0, z=0 and the Blue Brick 2 x 2 (3003) at "
        "x=1, y=1, z=0 both fill x=1, y=1, z=0"
    ) in r.text


def test_part_outside_the_grid(catalog):
    parts = [P("3003", 0, 0, 0), P("3003", 3, 0, 0)]
    r = check(Build(shape=(4, 4, 6), parts=parts), catalog)
    assert not r.ok
    assert r.out_of_bounds == [1]
    assert "1 part sticks out of the grid" in r.text.splitlines()[0]
    assert "4 x 4 x 6 grid (cells x=0 to 3, y=0 to 3, z=0 to 5)" in r.text
    assert "at x=3, y=0, z=0, covering x=3 to 4, y=0 to 1, z=0 to 2" in r.text
    assert r.loose == [1]


def test_collision_is_the_only_fault(catalog):
    # two 2x2 bricks overlapping on top of a 2x4 base: one grounded piece that stands, so
    # the overlap alone must fail the build
    parts = [P("3001", 0, 0, 0), P("3003", 0, 0, 3), P("3003", 1, 0, 3)]
    r = check(Build(shape=(4, 2, 6), parts=parts), catalog)
    assert r.collisions == [(1, 2)]
    assert r.components == 1 and r.grounded and r.stands
    assert r.out_of_bounds == [] and r.unknown_parts == []
    assert not r.ok
    assert r.text.splitlines()[0] == "NOT BUILDABLE: 3 parts; 1 pair of parts overlaps."


def test_negative_position_is_outside_the_grid(catalog):
    r = check(Build(shape=(4, 4, 6), parts=[P("3005", -1, 0, 0)]), catalog)
    assert r.out_of_bounds == [0]
    assert not r.ok


def test_unknown_part_id(catalog):
    parts = [P("3003", 0, 0, 0), P("99999", 0, 0, 3)]
    r = check(Build(shape=(2, 2, 6), parts=parts), catalog)
    assert not r.ok
    assert r.unknown_parts == [1]
    assert r.loose == [1]
    assert '"99999"' in r.text
    assert "not in the parts table" in r.text
    assert "at x=0, y=0, z=3" in r.text
    # an unknown part weighs nothing: the centre of mass is the 2x2 brick's
    assert r.centre_of_mass == pytest.approx((1.0, 1.0, 1.5))


def test_real_part_in_a_colour_it_does_not_come_in(catalog):
    part = next(
        p for p in catalog.parts.values() if p.kind == "brick" and set(catalog.colours) - p.colours
    )
    missing = min(set(catalog.colours) - part.colours)
    w, d = part.sx, part.sz
    parts = [P(part.id, 0, 0, 0, color=missing)]
    r = check(Build(shape=(w, d, 3), parts=parts), catalog)
    assert not r.ok
    assert r.unknown_parts == [0]
    assert r.components == 1 and r.grounded and r.stands  # still placed and weighed
    name = catalog.colours[missing].name
    assert f"{part.name} is not made in {name}" in r.text
    assert "colour that does not exist" in r.text.splitlines()[0]


def test_colour_not_in_colour_table(catalog):
    r = check(Build(shape=(1, 1, 3), parts=[P("3005", 0, 0, 0, color=9999)]), catalog)
    assert r.unknown_parts == [0]
    assert "colour 9999 is not in the colour table" in r.text


def test_examples_capped_at_five(catalog):
    # one base and seven floating 1x1 bricks
    parts = [P("3001", 0, 0, 0)] + [P("3005", x, 5, 6) for x in range(7)]
    r = check(Build(shape=(8, 8, 12), parts=parts), catalog)
    assert r.loose == list(range(1, 8))
    assert "; and 2 more" in r.text


# ---- standing ---------------------------------------------------------------------------------


def test_overhang_does_not_stand(catalog):
    # a 1x8 plate balanced at one end on a 1x1 brick
    parts = [P("3005", 0, 0, 0), P("3460", 0, 0, 3)]
    r = check(Build(shape=(8, 1, 4), parts=parts), catalog)
    assert not r.ok
    assert r.components == 1 and r.grounded
    assert not r.stands
    # cells: brick 3 at x=0.5, plate 8 at x=4
    assert r.centre_of_mass[0] == pytest.approx((3 * 0.5 + 8 * 4) / 11)
    assert "it would tip over" in r.text.splitlines()[0]
    assert "outline spans x=0.00 to 1.00, y=0.00 to 1.00" in r.text
    assert f"{r.centre_of_mass[0] - 1:.2f} studs outside" in r.text


def test_centre_on_the_edge_counts_as_standing(catalog):
    # 1x1 brick (3 cells, centre x=0.5), a 1x2 plate on it (2 cells, centre x=1.0) and three
    # 1x1 plates stacked on the plate's far stud (3 cells, centre x=1.5): (1.5+2+4.5)/8 = 1.0,
    # exactly over the edge of the 1x1 base
    parts = [P("3005", 0, 0, 0), P("3023b", 0, 0, 3)] + [P("3024", 1, 0, z) for z in (4, 5, 6)]
    r = check(Build(shape=(2, 1, 7), parts=parts), catalog)
    assert r.centre_of_mass[0] == pytest.approx(1.0)
    assert r.stands
    assert r.ok
    # one more plate on the far end tips it over
    parts.append(P("3024", 1, 0, 7))
    r = check(Build(shape=(2, 1, 8), parts=parts), catalog)
    assert r.centre_of_mass[0] > 1.0
    assert not r.stands


def test_straight_line_footprint(catalog):
    # a 1x8 plate on the ground: the footprint is one long strip of cells
    r = check(Build(shape=(8, 1, 1), parts=[P("3460", 0, 0, 0)]), catalog)
    assert r.ok and r.stands


def test_two_separate_ground_contacts_hull(catalog):
    # two 1x1 bricks four studs apart joined by a 1x8 plate: centre over the gap still stands
    parts = [P("3005", 0, 0, 0), P("3005", 7, 0, 0), P("3460", 0, 0, 3)]
    r = check(Build(shape=(8, 1, 4), parts=parts), catalog)
    assert r.ok
    assert r.centre_of_mass[0] == pytest.approx(4.0)


def _triangle_footprint_build(n_top: int) -> Build:
    # three 1x1 feet at the corners (0,0), (7,0) and (0,7) of an 8x8 area, joined by 1x8
    # plates; n_top 1x1 bricks stacked over the fourth corner (7,7), where there is no foot.
    # The footprint's convex hull is a triangle, its bounding box the whole 8x8 square.
    parts = [
        P("3005", 0, 0, 0),
        P("3005", 7, 0, 0),
        P("3005", 0, 7, 0),
        P("3024", 0, 7, 3),
        P("3460", 0, 0, 3),
        P("3460", 0, 0, 4, rot=90),
        P("3460", 0, 7, 5),
    ]
    parts += [P("3005", 7, 7, 6 + 3 * k) for k in range(n_top)]
    return Build(shape=(8, 8, 40), parts=parts)


@pytest.mark.parametrize("n_top", [0, 2])
def test_triangle_footprint_stands_with_little_weight_on_the_far_corner(catalog, n_top):
    r = check(_triangle_footprint_build(n_top), catalog)
    assert r.components == 1
    assert r.grounded
    assert r.centre_of_mass[0] + r.centre_of_mass[1] <= 9.0
    assert r.stands and r.ok


def test_convex_hull_not_bounding_box_decides_standing(catalog):
    # ten bricks on the far corner put the centre of mass inside the 8x8 bounding box of the
    # ground contact but outside its hull, whose long edge runs from (8, 1) to (1, 8): x + y = 9
    r = check(_triangle_footprint_build(10), catalog)
    assert r.components == 1
    assert r.grounded
    cx, cy, _ = r.centre_of_mass
    assert 0 < cx < 8 and 0 < cy < 8
    assert cx + cy > 9
    assert not r.stands and not r.ok
    assert "it would tip over" in r.text.splitlines()[0]
    # the text gives the outline's corners, not its span, and the nearest point of it
    tip = next(line for line in r.text.splitlines() if line.startswith("It would tip over"))
    assert "outline spans" not in tip
    assert "corners at (0, 0), (8, 0), (8, 1), (1, 8), (0, 8)" in tip
    expected = (cx + cy - 9) / np.sqrt(2)
    assert f"{expected:.2f} studs outside" in tip
    nx_, ny_ = cx - (cx + cy - 9) / 2, cy - (cx + cy - 9) / 2
    assert f"nearest point of the outline is at x={nx_:.2f}, y={ny_:.2f}" in tip


def test_footprint_distance_degenerate_cases():
    # a single point
    assert _footprint_distance(np.array([[1.0, 1.0]]), np.array([1.0, 1.0])) == 0.0
    assert _footprint_distance(np.array([[1.0, 1.0]]), np.array([4.0, 5.0])) == pytest.approx(5)
    # repeated points collapse to one
    pts = np.array([[2.0, 2.0]] * 4)
    assert _footprint_distance(pts, np.array([2.0, 3.0])) == pytest.approx(1.0)
    # collinear points: the hull is a segment
    line = np.array([[0.0, 0.0], [1.0, 0.0], [3.0, 0.0], [2.0, 0.0]])
    assert _footprint_distance(line, np.array([1.5, 0.0])) == 0.0
    assert _footprint_distance(line, np.array([1.5, 2.0])) == pytest.approx(2.0)
    assert _footprint_distance(line, np.array([5.0, 0.0])) == pytest.approx(2.0)
    # a proper square: inside, on the edge, on a corner, outside
    sq = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    assert _footprint_distance(sq, np.array([0.5, 0.5])) == 0.0
    assert _footprint_distance(sq, np.array([1.0, 0.5])) == 0.0
    assert _footprint_distance(sq, np.array([1.0, 1.0])) == 0.0
    assert _footprint_distance(sq, np.array([2.0, 2.0])) == pytest.approx(np.sqrt(2))
    assert _footprint_distance(sq, np.array([0.5, -3.0])) == pytest.approx(3.0)


# ---- weak spots ------------------------------------------------------------------------------


def test_build_held_by_one_stud(catalog):
    parts = [
        P("3001", 0, 0, 0),  # base 2x4
        P("3005", 0, 0, 3, color=BLUE),  # 1x1 on one stud of the base
        P("3003", 0, 0, 6),  # 2x2 on the single stud of the 1x1
        P("3003", 0, 0, 9),
        P("3003", 0, 0, 12),
    ]
    r = check(Build(shape=(4, 2, 15), parts=parts), catalog)
    assert r.ok  # weak spots do not fail a build
    assert len(r.weak_spots) == 2
    first, second = r.weak_spots
    assert first.startswith("4 parts above x=0, y=0, z=3 hang on a single stud")
    assert "the Blue Brick 1 x 1 (3005) at x=0, y=0, z=3 sits on only one stud" in first
    assert "Red Brick 2 x 4 (3001) at x=0, y=0, z=0" in first
    assert "the group spans x=0 to 1, y=0 to 1, z=3 to 14" in first
    assert second.startswith("3 parts above x=0, y=0, z=6 hang on a single stud")
    assert r.text.splitlines()[0] == "OK: 5 parts in one connected piece; it stands."
    assert "2 weak spots" in r.text
    assert first in r.text and second in r.text


def test_single_stud_on_rotated_base_reports_the_right_stud(catalog):
    # base 2x4 turned 90 degrees covers x 0..1, y 0..3; the 1x1 sits on its stud at (1, 3)
    parts = [
        P("3001", 0, 0, 0, rot=90),
        P("3005", 1, 3, 3),
        P("3005", 1, 3, 6),
        P("3005", 1, 3, 9),
    ]
    r = check(Build(shape=(2, 4, 12), parts=parts), catalog)
    assert r.weak_spots
    assert r.weak_spots[0].startswith("3 parts above x=1, y=3, z=3 hang on a single stud")


def test_group_hanging_below_a_single_stud(catalog):
    # a column standing on the ground with an arm on top; under the arm's far end hangs a
    # 1x1 column pressed onto one stud from below
    parts = [
        P("3003", 0, 0, 0),
        P("3003", 0, 0, 3),
        P("3003", 0, 0, 6),
        P("3460", 0, 0, 9),  # 1x8 plate, x 0..7 at y=0
        P("3005", 7, 0, 6),  # its stud enters the plate's underside at x=7
        P("3005", 7, 0, 3),
        P("3024", 7, 0, 2),  # a plate under that, still clear of the ground
    ]
    r = check(Build(shape=(8, 2, 10), parts=parts), catalog)
    assert r.components == 1
    hang = [s for s in r.weak_spots if "hang from a single stud" in s]
    assert hang, r.weak_spots
    assert hang[0].startswith("3 parts below x=7, y=0, z=9 hang from a single stud")


def test_articulation_part_reported(catalog):
    parts = [
        P("3001", 0, 0, 0),  # base 2x4: x 0..3, y 0..1
        P("3003", 1, 0, 3, color=BLUE),  # 2x2 neck on four studs
        P("3001", 0, 0, 6),  # 2x4 on the neck's four studs only
        P("3003", 0, 0, 9),
        P("3003", 2, 0, 9),
    ]
    r = check(Build(shape=(4, 2, 12), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 1
    s = r.weak_spots[0]
    assert s.startswith("3 parts depend on the Blue Brick 2 x 2 (3003) at x=1, y=0, z=3")
    assert "only link to the ground" in s
    assert "the group spans x=0 to 3, y=0 to 1, z=6 to 11" in s
    assert positions_in(s)[0] == (1, 0, 3)


def test_articulation_part_holding_a_group_through_two_connections(catalog):
    # the 2x2 neck holds two 1x2 bricks, and both hold the 2x4 above: the neck carries the
    # group through two connections, so it is a cut point without being a bridge end
    parts = [
        P("3001", 0, 0, 0),
        P("3003", 1, 0, 3, color=BLUE),
        P("3004", 0, 0, 6),
        P("3004", 2, 0, 6),
        P("3001", 0, 0, 9),
        P("3003", 0, 0, 12),
    ]
    r = check(Build(shape=(4, 2, 15), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 1
    assert r.weak_spots[0].startswith(
        "4 parts depend on the Blue Brick 2 x 2 (3003) at x=1, y=0, z=3"
    )


def test_single_stud_joint_ranked_ahead_of_soundly_held_column(catalog):
    # a 2x2 column, a 1x1 brick at z=42, and more 2x2 bricks on its single stud: the two
    # single-stud joints come first, and each run of 2x2 bricks that carry everything above
    # them is one sentence, not one per brick
    parts = [P("3003", 0, 0, 3 * k) for k in range(14)]
    parts += [P("3005", 0, 0, 42, color=BLUE)]
    parts += [P("3003", 0, 0, 45 + 3 * k) for k in range(15)]
    r = check(Build(shape=(2, 2, 90), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 4
    a, b, c, d = r.weak_spots
    assert a.startswith("16 parts above x=0, y=0, z=42 hang on a single stud")
    assert b.startswith("15 parts above x=0, y=0, z=45 hang on a single stud")
    assert c.startswith("28 parts depend on the Red Brick 2 x 2 (3003) at x=0, y=0, z=3")
    assert "first of 12 parts in a row" in c
    assert "ending at the Red Brick 2 x 2 (3003) at x=0, y=0, z=36" in c
    assert d.startswith("14 parts depend on the Red Brick 2 x 2 (3003) at x=0, y=0, z=45")
    assert "first of 12 parts in a row" in d
    assert "ending at the Red Brick 2 x 2 (3003) at x=0, y=0, z=78" in d
    assert "4 weak spots" in r.text
    assert "not listed" not in r.text


def test_sound_column_is_one_weak_spot(catalog):
    parts = [P("3003", 0, 0, 3 * k) for k in range(30)]
    r = check(Build(shape=(2, 2, 90), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 1
    s = r.weak_spots[0]
    assert s.startswith("28 parts depend on the Red Brick 2 x 2 (3003) at x=0, y=0, z=3")
    assert "first of 26 parts in a row" in s
    assert "ending at the Red Brick 2 x 2 (3003) at x=0, y=0, z=78" in s
    assert "1 weak spot to strengthen" in r.text


def test_unlisted_weak_spots_described_as_less_serious(catalog):
    # on one 2x4 base: a column of fifteen 1x1 bricks (thirteen single-stud joints with 3 or
    # more parts above) and a column of nine 2x2 bricks (one run of soundly held bricks with 8
    # parts at stake). The ten slots go to single-stud joints (15 down to 6 parts); the run is
    # left out although it carries more than 6 parts, so the rest is "less serious", not
    # "smaller"
    parts = [P("3001", 0, 0, 0)]
    parts += [P("3005", 0, 0, 3 + 3 * k) for k in range(15)]
    parts += [P("3003", 2, 0, 3 + 3 * k) for k in range(9)]
    r = check(Build(shape=(4, 2, 50), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 10
    assert all("single stud" in s for s in r.weak_spots)
    assert [int(s.split()[0]) for s in r.weak_spots] == list(range(15, 5, -1))
    assert "14 weak spots" in r.text
    assert "and 4 less serious weak spots not listed" in r.text


def test_long_sound_column_is_fast(catalog):
    parts = [P("3003", 0, 0, 3 * k) for k in range(3000)]
    start = time.perf_counter()
    r = check(Build(shape=(2, 2, 9000), parts=parts), catalog)
    elapsed = time.perf_counter() - start
    assert r.ok
    assert len(r.weak_spots) == 1
    assert "first of 2996 parts in a row" in r.weak_spots[0]
    assert elapsed < 2.0, f"took {elapsed:.2f} s"


def test_small_groups_are_ignored(catalog):
    # only two parts hang on the single stud: not worth reporting
    parts = [P("3001", 0, 0, 0), P("3005", 0, 0, 3), P("3003", 0, 0, 6)]
    r = check(Build(shape=(4, 2, 12), parts=parts), catalog)
    assert r.ok
    assert r.weak_spots == []


def test_grounded_part_not_called_a_weak_spot(catalog):
    # everything stands on one base brick; above it two routes hold the top brick
    parts = [P("3001", 0, 0, 0), P("3003", 0, 0, 3), P("3003", 2, 0, 3), P("3001", 0, 0, 6)]
    r = check(Build(shape=(4, 2, 9), parts=parts), catalog)
    assert r.ok
    assert r.weak_spots == []


def test_plain_stack_middle_parts_are_articulation_points(catalog):
    # a straight stack of 2x4 bricks: each middle brick is the only link for those above it
    parts = [P("3001", 0, 0, 3 * k) for k in range(5)]
    r = check(Build(shape=(4, 2, 15), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 1  # only the brick at z=3 has 3 or more parts above it
    assert r.weak_spots[0].startswith(
        "3 parts depend on the Red Brick 2 x 4 (3001) at x=0, y=0, z=3"
    )


def test_weak_spots_capped_at_ten(catalog):
    # a tall column of 1x1 bricks: every joint is a single stud
    parts = [P("3005", 0, 0, 3 * k) for k in range(20)]
    r = check(Build(shape=(1, 1, 60), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 10
    counts = [int(s.split()[0]) for s in r.weak_spots]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == 19  # everything above the bottom brick
    assert "17 weak spots" in r.text
    assert "and 7 smaller weak spots not listed" in r.text


def test_one_unlisted_weak_spot_is_singular(catalog):
    # a column of fourteen 1x1 bricks: eleven single-stud joints with 3 or more parts above,
    # ten shown
    parts = [P("3005", 0, 0, 3 * k) for k in range(14)]
    r = check(Build(shape=(1, 1, 42), parts=parts), catalog)
    assert len(r.weak_spots) == 10
    assert "11 weak spots" in r.text
    assert r.text.endswith("- and 1 smaller weak spot not listed.")


def test_cut_part_with_a_loop_above_it(catalog):
    # a 1x4 plate rests on two 1x1 bricks standing on one base (a loop below it) and carries
    # two 1x2 plates joined again by a 1x4 plate (a loop above it): the 1x4 plate is the only
    # link for the three plates above, although every part above it has two connections
    parts = [
        P("3001", 0, 0, 0),  # base 2x4, x 0..3
        P("3005", 0, 0, 3),
        P("3005", 3, 0, 3),
        P("3710", 0, 0, 6, color=BLUE),  # 1x4 plate on both 1x1 bricks
        P("3023b", 0, 0, 7),
        P("3023b", 2, 0, 7),
        P("3710", 0, 0, 8),
    ]
    r = check(Build(shape=(4, 2, 9), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 1, r.weak_spots
    assert r.weak_spots[0].startswith(
        "3 parts depend on the Blue Plate 1 x 4 (3710) at x=0, y=0, z=6"
    )


def test_two_grounded_towers_joined_by_one_stud(catalog):
    # two towers of five 2x2 bricks, both on the ground, joined only by a 1x4 plate that
    # sits on one stud of each: lifting the model pulls them apart
    parts = [P("3003", 0, 0, 3 * k) for k in range(5)]
    parts += [P("3003", 4, 0, 3 * k, color=BLUE) for k in range(5)]
    parts += [P("3710", 1, 0, 15, color=GREY)]
    r = check(Build(shape=(6, 2, 16), parts=parts), catalog)
    assert r.ok  # weak spots do not fail a build
    joints = [s for s in r.weak_spots if "single stud" in s]
    assert len(joints) == 2, r.weak_spots
    left = next(s for s in joints if "x=1, y=0, z=15" in s)
    right = next(s for s in joints if "x=4, y=0, z=15" in s)
    # the left joint cuts off the left tower (5 parts); the right one the right tower
    assert left.startswith("5 parts are joined to the rest by a single stud at x=1, y=0, z=15")
    assert "the Light Bluish Grey Plate 1 x 4 (3710) at x=1, y=0, z=15 sits on only one" in left
    assert "Red Brick 2 x 2 (3003) at x=0, y=0, z=12" in left
    assert "the group spans x=0 to 1, y=0 to 1, z=0 to 14" in left
    assert "lifted" in left
    assert right.startswith("5 parts are joined to the rest by a single stud at x=4, y=0, z=15")
    assert "the group spans x=4 to 5, y=0 to 1, z=0 to 14" in right
    assert "weak spot" in r.text and left in r.text


def test_table_with_legs_on_single_studs(catalog):
    # four legs of four 2x2 bricks, a 1x1 brick on each leg, and a top of 2x8 plates resting
    # on those 1x1 bricks: every leg hangs on one stud once the table is lifted
    parts: list[Placement] = []
    for lx, ly in [(0, 0), (6, 0), (0, 6), (6, 6)]:
        parts += [P("3003", lx, ly, 3 * k) for k in range(4)]
    for lx, ly in [(1, 1), (6, 1), (1, 6), (6, 6)]:
        parts.append(P("3005", lx, ly, 12, color=BLUE))
    parts += [
        P("3034", 0, 0, 15, rot=90),
        P("3034", 6, 0, 15, rot=90),
        P("3034", 0, 0, 16),
        P("3034", 0, 6, 16),
    ]
    r = check(Build(shape=(8, 8, 20), parts=parts), catalog)
    assert r.ok
    assert r.weak_spots
    legs = [s for s in r.weak_spots if s.startswith("4 parts are joined to the rest")]
    assert len(legs) == 4, r.weak_spots
    for s in legs:
        assert "single stud" in s
    assert "single stud at x=1, y=1, z=12" in r.text


def test_leg_joined_to_a_grounded_column_by_one_stud(catalog):
    # a column of five 2x4 bricks and a leg of five 1x1 bricks, both on the ground, joined by
    # a 1x4 plate on one stud of each
    parts = [P("3001", 0, 0, 3 * k) for k in range(5)]
    parts += [P("3005", 6, 0, 3 * k, color=BLUE) for k in range(5)]
    parts += [P("3710", 3, 0, 15, color=GREY)]
    r = check(Build(shape=(8, 2, 16), parts=parts), catalog)
    assert r.ok
    assert any(
        s.startswith("5 parts are joined to the rest by a single stud at x=3, y=0, z=15")
        for s in r.weak_spots
    ), r.weak_spots
    assert any(
        s.startswith("5 parts are joined to the rest by a single stud at x=6, y=0, z=15")
        for s in r.weak_spots
    ), r.weak_spots


def test_grounded_sections_joined_through_one_part(catalog):
    # two towers of three 2x2 bricks on the ground, side by side, joined only through a 2x2
    # brick that holds each with two studs: no single-stud joint, but that brick is the only
    # link between them
    parts = [P("3003", 0, 0, 3 * k) for k in range(3)]
    parts += [P("3003", 2, 0, 3 * k, color=BLUE) for k in range(3)]
    parts += [P("3003", 1, 0, 9, color=GREY)]
    r = check(Build(shape=(4, 2, 12), parts=parts), catalog)
    assert r.ok
    assert len(r.weak_spots) == 1, r.weak_spots
    s = r.weak_spots[0]
    assert s.startswith(
        "3 parts depend on the Light Bluish Grey Brick 2 x 2 (3003) at x=1, y=0, z=9"
    )
    assert "lifted" in s
    # the tower whose bottom part has the lower index stays as "the rest"
    assert "the group spans x=2 to 3, y=0 to 1, z=0 to 8" in s


def test_grounded_section_joined_to_its_only_link_through_a_loop(catalog):
    # a stack of nine 2x2 plates and a small grounded section (two 2x2 bricks with two 1x2
    # bricks on top) are joined only through a 2x2 brick; it sits on both 1x2 bricks, so the
    # small section reaches it by two routes, yet it is still that section's only link
    parts = [P("3022", 0, 0, z) for z in range(9)]
    parts += [
        P("3003", 1, 0, 9, color=GREY),  # the link, on the top plate and on both 1x2 bricks
        P("3003", 2, 0, 0, color=BLUE),
        P("3003", 2, 0, 3, color=BLUE),
        P("3004", 2, 0, 6, color=BLUE),
        P("3004", 2, 1, 6, color=BLUE),
    ]
    r = check(Build(shape=(4, 2, 12), parts=parts), catalog)
    assert r.ok
    # The plates are links too, and the smaller side is what comes away. Above the plate at
    # z=7 hang 6 parts (the top plate, the link and the small section), against 7 plates
    # below; then 5 above the top plate; then the small section's 4 above the link. That is
    # one run of three parts ending at the link. Below the plate at z=6 hang 6 plates against
    # 7 parts above, a run going down to the plate at z=3 (3 plates below it).
    assert len(r.weak_spots) == 2, r.weak_spots
    down, up = r.weak_spots
    assert down.startswith(
        "6 parts depend on the Red Plate 2 x 2 (3022) at x=0, y=0, z=6 to stay joined to the rest"
    )
    assert "first of 4 parts in a row" in down
    assert "ending at the Red Plate 2 x 2 (3022) at x=0, y=0, z=3" in down
    assert up.startswith(
        "6 parts depend on the Red Plate 2 x 2 (3022) at x=0, y=0, z=7 to stay joined to the rest"
    )
    assert "the group spans x=0 to 3, y=0 to 1, z=0 to 11" in up
    assert "first of 3 parts in a row" in up
    assert "ending at the Light Bluish Grey Brick 2 x 2 (3003) at x=1, y=0, z=9" in up


def _random_build(catalog, rng: np.random.Generator, n: int, size: int) -> Build:
    # parts dropped onto a small area: each one lands on the highest part under it (so it is
    # held by that part's studs) or on the ground
    kinds = ["3005", "3004", "3003", "3001", "3024", "3023b", "3710", "3022", "3020"]
    height = np.zeros((size, size), dtype=int)
    parts: list[Placement] = []
    while len(parts) < n:
        part = str(rng.choice(kinds))
        rot = int(rng.choice([0, 90]))
        probe = P(part, 0, 0, 0, rot=rot)
        w, d, h = catalog.footprint(probe)
        if w > size or d > size:
            continue
        x, y = int(rng.integers(0, size - w + 1)), int(rng.integers(0, size - d + 1))
        z = int(height[x : x + w, y : y + d].max())
        height[x : x + w, y : y + d] = z + h
        parts.append(P(part, x, y, z, rot=rot))
    return Build(shape=(size, size, int(height.max()) + 1), parts=parts)


def _brute_force_spots(graph, main: list[int], anchors: set[int], parts) -> set:
    import networkx as nx

    expected: set = set()
    low_index = min(main)
    sub = graph.subgraph(main)
    for a in main:
        if a in anchors:
            continue
        comps = [set(c) for c in nx.connected_components(sub.subgraph(set(main) - {a}))]
        ungrounded = set().union(*(c for c in comps if not c & anchors))
        if len(ungrounded) >= 3:
            expected.add((1, a, frozenset(ungrounded)))
        grounded = [c for c in comps if c & anchors]
        if len(grounded) >= 2:
            stays = max(grounded, key=lambda c: (len(c), -min(c)))
            away = set().union(*(c for c in grounded if c is not stays))
            if len(away) >= 3:
                expected.add((1, a, frozenset(away)))
    for u, v, data in sub.edges(data=True):
        if data.get("studs") != 1:
            continue
        cut = nx.Graph(sub)
        cut.remove_edge(u, v)
        comps = [set(c) for c in nx.connected_components(cut)]
        if len(comps) == 1:
            continue
        one, two = comps
        if not one & anchors or not two & anchors:
            away = one if not one & anchors else two
        else:
            # the smaller side comes away; on a tie, the side with the lowest index stays
            away = min((one, two), key=lambda c: (len(c), low_index in c))
        if len(away) >= 3:
            expected.add((0, frozenset((u, v)), frozenset(away)))
    return expected


@pytest.mark.parametrize("seed", range(6))
def test_weak_spot_search_matches_brute_force(catalog, seed):
    # every part and single-stud joint whose loss cuts off 3 or more parts, found by removing
    # each one in turn, must be exactly what the search finds
    import networkx as nx

    from bricksnap.checks import _find_spots
    from bricksnap.connect import connection_graph, occupancy

    rng = np.random.default_rng(seed)
    compared = 0
    for _ in range(40):
        build = _random_build(catalog, rng, int(rng.integers(6, 26)), int(rng.choice([3, 4, 6])))
        occ, _, _, _ = occupancy(build, catalog)
        graph = connection_graph(build, catalog, occ)
        pieces: list[set[int]] = [set(c) for c in nx.connected_components(graph)]
        main = sorted(max(pieces, key=len))
        anchors = {i for i in main if build.parts[i].z == 0}
        if len(main) < 4:
            continue
        found = set()
        for s in _find_spots(build, catalog, occ, graph, main, anchors):
            what = frozenset((s.lower, s.upper)) if s.kind == 0 else s.part
            found.add((s.kind, what, frozenset(s.members())))
        assert found == _brute_force_spots(graph, main, anchors, build.parts)
        compared += 1
    assert compared > 20


def test_weak_spots_in_floating_main_piece_measured_from_its_bottom(catalog):
    parts = [P("3005", 0, 0, 3 * k) for k in range(1, 6)]
    r = check(Build(shape=(1, 1, 18), parts=parts), catalog)
    assert not r.grounded
    assert r.weak_spots
    assert r.weak_spots[0].startswith("4 parts above x=0, y=0, z=6")


# ---- text quality and speed -------------------------------------------------------------------


def test_many_problems_listed_together(catalog):
    parts = [
        P("3003", 0, 0, 0),
        P("3003", 1, 0, 0),  # overlaps
        P("3005", 9, 0, 0),  # out of the grid
        P("nope", 0, 0, 3),  # unknown
    ]
    r = check(Build(shape=(4, 4, 6), parts=parts), catalog)
    assert not r.ok
    first = r.text.splitlines()[0]
    assert first.startswith("NOT BUILDABLE: ")
    for words in ("overlap", "out of the grid", "not in the parts table", "separate pieces"):
        assert words in first
    assert first.startswith("NOT BUILDABLE: 4 parts; ")
    assert "Traceback" not in r.text


def test_five_thousand_parts_under_two_seconds(catalog):
    # layers of 2x4 plates over a 40 x 40 area, turned and shifted from layer to layer so
    # every plate holds plates of the layers above and below: one sound piece
    parts: list[Placement] = []
    z = 0
    while len(parts) < 5000:
        rot = 0 if z % 2 == 0 else 90
        w, d = (4, 2) if rot == 0 else (2, 4)
        ox, oy = {0: (0, 0), 1: (0, 2), 2: (2, 0), 3: (0, 0)}[z % 4]
        layer = [
            P("3020", x, y, z, rot=rot)
            for x in range(ox, 40 - w + 1, w)
            for y in range(oy, 40 - d + 1, d)
        ]
        covered = np.zeros((40, 40), dtype=bool)
        for p in layer:
            covered[p.x : p.x + w, p.y : p.y + d] = True
        # fill the strips the shift leaves at the edges with 2x2 plates
        layer += [
            P("3022", x, y, z)
            for x in range(0, 40, 2)
            for y in range(0, 40, 2)
            if not covered[x, y]
        ]
        parts += layer
        z += 1
    parts = parts[:5000]
    build = Build(shape=(40, 40, z), parts=parts)
    assert len(parts) == 5000
    start = time.perf_counter()
    r = check(build, catalog)
    elapsed = time.perf_counter() - start
    assert r.part_count == 5000
    assert r.ok, r.text
    assert r.components == 1 and r.collisions == []
    assert elapsed < 2.0, f"took {elapsed:.2f} s"


def test_long_single_stud_column_is_fast(catalog):
    # worst case for weak spots: 3,000 parts, every joint a single stud and every part a
    # cut point; the search must stay linear and only the top ten sentences are written
    parts = [P("3005", 0, 0, 3 * k) for k in range(3000)]
    start = time.perf_counter()
    r = check(Build(shape=(1, 1, 9000), parts=parts), catalog)
    elapsed = time.perf_counter() - start
    assert r.ok
    assert len(r.weak_spots) == 10
    assert r.weak_spots[0].startswith("2999 parts above x=0, y=0, z=3")
    assert elapsed < 2.0, f"took {elapsed:.2f} s"
