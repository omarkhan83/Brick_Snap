"""Tests for the free-build lab (bricksnap/lab/), a research prototype.

They read the real LDraw library zip (skipped when it is not on this machine) and cache what
they parse under the lab cache, so after the first run they are quick. No test starts a real
AI session: the session runner is tried with a stand-in ``claude`` on PATH.
"""

from __future__ import annotations

import base64
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest

from bricksnap.lab import ldraw_lib

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(),
    reason=f"the lab's tests read the LDraw parts library, which is not on this machine "
    f"({ldraw_lib.zip_path()}); the rest of BrickSnap does not need it",
)

UP = "1 0 0 0 1 0 0 0 1"


def line(colour: int, x: float, y: float, z: float, name: str, m: str = UP) -> str:
    return f"1 {colour} {x} {y} {z} {m} {name}"


@pytest.fixture(scope="module")
def lib() -> ldraw_lib.Library:
    return ldraw_lib.library()


def check(text: str):
    from bricksnap.lab.validate import check as run

    return run(text)


def kinds(report) -> list[str]:
    return [i.kind for i in report.problems]


# ---- reading parts ----------------------------------------------------------------------------


def test_resolve_and_header(lib):
    assert lib.resolve("3001.dat") == ("part", "3001.dat")
    assert lib.resolve("S\\3001S01.DAT") == ("subpart", "s/3001s01.dat")
    assert lib.resolve("stud.dat") == ("primitive", "stud.dat")
    assert lib.resolve("48/4-4cyli.dat") == ("primitive", "48/4-4cyli.dat")
    assert lib.resolve("nosuchpart.dat") is None
    h = lib.header("3001.dat")
    assert h.description == "Brick 2 x 4" and h.org == "Part" and h.category == "Brick"


def test_brick_geometry_and_connectors(lib):
    p = lib.part("3001.dat")
    assert np.allclose(p.bbox_min, [-40, 0, -20]) and np.allclose(p.bbox_max, [40, 24, 20])
    assert p.size() == (4.0, 2.0, 3.0)
    top = p.top_studs()
    assert len(top) == 8 and all(abs(s.pos[1]) < 1e-6 for s in top)
    assert sorted({round(float(s.pos[0])) for s in top}) == [-30, -10, 10, 30]
    tubes = p.tubes
    assert len(tubes) == 3 and all(t.open for t in tubes)
    assert all(np.allclose(t.end[1], 24) for t in tubes if t.end is not None)
    # the hollow underside counts as solid
    assert p.inside(np.array([[0.0, 20.0, 0.0], [-30.0, 22.0, 10.0]])).all()
    assert not p.inside(np.array([[0.0, -2.0, 0.0], [50.0, 10.0, 0.0]])).any()


def test_side_stud_and_other_connectors(lib):
    p = lib.part("87087.dat")
    dirs = sorted(ldraw_lib.direction_word(s.axis) for s in p.studs)
    assert dirs == ["-z", "up"]
    side = next(s for s in p.studs if s.axis[1] > -0.5)
    assert np.allclose(side.pos, [0, 10, -10])
    wheels = lib.part("4600.dat")
    assert sorted(c.kind for c in wheels.others) == ["wheel pin", "wheel pin"]
    clip = lib.part("60897.dat")
    assert [c.kind for c in clip.others] == ["clip"]


def test_arch_span_stays_open(lib):
    from bricksnap.lab.place import sockets

    p = lib.part("3659.dat")
    assert p.bottom_at(-31, 1) == pytest.approx(24, abs=0.5)  # a leg
    assert p.bottom_at(1, 1) < 12  # under the span
    assert [tuple(np.round(s.pos[[0, 2]])) for s in sockets(p)] == [(-30, 0), (30, 0)]


def test_sockets(lib):
    from bricksnap.lab.place import sockets

    s = sockets(lib.part("3001.dat"))
    assert [x.kind for x in s].count("grid") == 8 and [x.kind for x in s].count("tube") == 3
    assert len(sockets(lib.part("3794b.dat"))) == 2  # a jumper plate: two cells, one stud
    assert len(sockets(lib.part("30028b.dat"))) == 0  # a tyre takes no stud
    leaf = lib.part("2417.dat")
    rings = {tuple(np.round(t.end[[0, 2]])) for t in leaf.tubes if t.end is not None}
    assert {tuple(np.round(x.pos[[0, 2]])) for x in sockets(leaf)} == rings  # only its rings
    assert len(sockets(lib.part("4032a.dat"))) == 5  # round 2 x 2: four corners and the centre


# ---- search -----------------------------------------------------------------------------------

# query -> acceptable first results
QUERIES = {
    "brick 2 x 4": {"3001.dat"},
    "plate 1 x 1 round": {"6141.dat"},
    "tile 1 x 2": {"3069b.dat"},
    "slope 45 2 x 2": {"3039.dat"},
    "wing 2 x 4 left": {"41770a.dat", "41770b.dat"},
    "curved slope 4 x 1": {"61678.dat"},
    "brick 1 x 1 with stud on side": {"87087.dat"},
    "plate 1 x 2 with clip": {"78256.dat", "92280.dat", "60470a.dat", "60470b.dat"},
    "cone 1 x 1": {"4589.dat"},
    "arch 1 x 4": {"3659.dat"},
    "headlight brick": {"4070.dat"},
    "jumper plate": {"3794b.dat"},
    "cheese slope": {"54200.dat"},
    "bracket 1 x 2 - 1 x 2": {"99780.dat", "99781.dat"},
    "technic pin": {"3673.dat"},
    "round brick 2 x 2": {"6143.dat", "3941.dat"},
    "leaf": {"2682a.dat", "2423.dat", "2417.dat"},
    "plant leaves": {"2423.dat", "2417.dat"},
    "plate 2 x 2 with wheel pins": {"4488.dat", "4600.dat", "4870.dat"},
    "wheel for wheel pin": {"30027b.dat", "30027c.dat"},
    "steering wheel": {"874.dat", "2819.dat", "2741.dat", "30663.dat"},
    "3001": {"3001.dat"},
}


def test_search_puts_obvious_answers_first():
    from bricksnap.lab.search import load_index

    index = load_index()
    wrong = {}
    for query, ok in QUERIES.items():
        first = index.search(query, 3)[0].name
        if first not in ok:
            wrong[query] = first
    assert not wrong


def test_index_leaves_out_what_it_should():
    from bricksnap.lab.search import exclusion_reason, load_index

    assert exclusion_reason("4073.dat", "~Moved to 6141", "Part", "Plate") == "moved"
    assert exclusion_reason("3001p11.dat", "Brick 2 x 4 with Pattern", "Part", "") == "patterned"
    assert exclusion_reason("x.dat", "=Tile 1 x 1", "Part", "") == "alias"
    assert exclusion_reason("x.dat", "Brick 2 x 2", "Shortcut", "") == "shortcut"
    assert exclusion_reason("x.dat", "Duplo Brick 2 x 2", "Part", "Duplo") == "other system"
    index = load_index()
    assert "3001.dat" in index.by_name and "4073.dat" not in index.by_name
    assert index.stats["indexed"] > 4000


def test_hit_line_says_size_studs_origin():
    from bricksnap.lab.search import load_index

    text = load_index().search("brick 2 x 4", 1)[0].line()
    assert "3001.dat: Brick 2 x 4" in text and "4 x 2 studs x 3 plates" in text
    assert "8 on top" in text and "origin at the centre of the top face" in text


# ---- checking ---------------------------------------------------------------------------------


def test_two_bricks_stacked_is_fine():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -48, 0, "3001.dat"))
    assert r.ok and not r.issues
    assert r.summary().startswith("2 parts of 1 kind, no problems")
    assert [(x.holder, x.held, len(x.studs)) for x in r.links] == [(1, 2, 8)]


def test_half_a_stud_off():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 10, -48, 0, "3001.dat"))
    assert "stud" in kinds(r) and "loose" in kinds(r)
    stud = next(i for i in r.problems if i.kind == "stud")
    assert "line 2" in stud.text and "10 LDU off" in stud.text and "to 0 -48 0" in stud.text


def test_overlap():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 20, -24, 0, "3003.dat"))
    over = next(i for i in r.problems if i.kind == "overlap")
    assert "line 1" in over.text and "line 2" in over.text and "same space" in over.text


def test_floating():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -56, 0, "3001.dat"))
    loose = next(i for i in r.problems if i.kind == "loose")
    assert loose.lines == [2] and "floats 8 LDU" in loose.text and "move it down by 8" in loose.text


def test_tile_on_side_stud():
    tile_m = "1 0 0 0 0 -1 0 1 0"  # its top faces -z, its underside the brick's side
    r = check(line(4, 0, -24, 0, "87087.dat") + "\n" + line(15, 0, -14, -18, "3070b.dat", tile_m))
    assert r.ok and r.links[0].how == "sideways"


def test_plate_under_brick():
    r = check(line(14, 0, -8, 0, "3020.dat") + "\n" + line(4, 0, -32, 0, "3001.dat"))
    assert r.ok and r.links[0].holder == 1 and len(r.links[0].studs) == 8


def test_unknown_file_name_gets_close_names():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -48, 0, "30001.dat"))
    unknown = next(i for i in r.problems if i.kind == "unknown part")
    assert "Line 2" in unknown.text and "3001.dat (Brick 2 x 4)" in unknown.text


def test_bad_lines_and_matrices():
    text = "\n".join(
        [
            "1 4 0 -24 0 1 0 0 0 1 0 3001.dat",  # too short
            "1 4 0 -24 0 2 0 0 0 1 0 0 0 1 3001.dat",  # stretched
            "1 4 0 -24 40 -1 0 0 0 1 0 0 0 1 3001.dat",  # mirrored
            "1 4 0 -24 80 1 0 0 0 1 0 0 0 1 s/3001s01.dat",  # a sub-part
            "1 4 0 0 120 1 0 0 0 1 0 0 0 1 3001.dat",  # below the ground
        ]
    )
    k = kinds(check(text))
    for expected in ("format", "matrix", "mirrored", "not a part", "below ground"):
        assert expected in k


def test_nothing_on_the_ground_and_tipping():
    r = check(line(4, 0, -48, 0, "3001.dat"))
    assert "ground" in kinds(r)
    tower = [line(4, 0, -8, 0, "3024.dat")] + [
        line(4, 30, -8 - 24 * (k + 1), 0, "3009.dat") for k in range(1)
    ]
    r = check("\n".join(tower))
    assert "tips over" in kinds(r) or "loose" in kinds(r)


def test_a_bar_standing_in_a_clip_is_tested_for_fit():
    clip = line(72, 0, -8, 0, "60897.dat")
    bar = line(0, 0, -60, -20, "87994.dat")  # 60 LDU long, standing in the clip
    r = check(clip + "\n" + bar)
    assert not r.problems
    assert any("by the clip of line 1 round its bar" in w for w in fit_words(r)), r.text()


# ---- false alarms seen on official sets (experiment 3), each beside its wrong twin ----------


def unchecked_words(report) -> list[str]:
    """The joints known by name only (the NOT CHECKED section)."""
    return [i.text for i in report.unchecked if i.kind == "joint"]


def fit_words(report) -> list[str]:
    """The joints tested for fit ("line N (part) is held ...")."""
    return [i.text for i in report.fits]


@pytest.mark.parametrize("key", ["343.dat", "932.dat", "993.dat"])
def test_a_solid_with_no_triangle_facing_an_axis_is_built(key):
    # these parts have no triangle facing one of the three axes: the rays along it see nothing,
    # and that empty answer must still come back in x, y, z order
    from bricksnap.lab import solid

    s = solid.build_solid(solid.triangles(key))
    assert s.full.shape == s.deep.shape and s.full.ndim == 3 and s.full.any()
    up = np.eye(3)
    d, _, _ = solid.interference((key, np.zeros(3), up), (key, np.array([0.0, 0, 2]), up))
    assert d >= 0


def test_real_shapes_tell_touching_from_overlapping():
    from bricksnap.lab import solid

    up = np.eye(3)

    def placed(key, x, y, z):
        return (key, np.array([x, y, z], dtype=float), up)

    # a plate seated on a plate's studs shares nothing; side by side they only touch
    d, _, need = solid.interference(placed("3020.dat", 0, -8, 0), placed("3020.dat", 0, -16, 0))
    assert d == 0
    d, _, _ = solid.interference(placed("3001.dat", 0, -24, 0), placed("3001.dat", 0, -24, 40))
    assert d <= 0.5 < need
    # pushed half a plate (4 LDU) into it, or sideways by 4: a 4 LDU wall is shared
    for b in (placed("3020.dat", 0, -12, 0), placed("3020.dat", 0, -8, 36)):
        d, v, need = solid.interference(placed("3020.dat", 0, -8, 0), b)
        assert d >= 2.0 > need and v > 1000
    assert solid.in_the_way(placed("3001.dat", 0, -24, 0), placed("3001.dat", 0, -24, 38))
    assert not solid.in_the_way(placed("3001.dat", 0, -24, 0), placed("3001.dat", 0, -48, 0))


SLOPE_OVER_PLATE_END = [
    line(4, 0, -24, 0, "3001.dat"),
    line(1, 20, -32, 10, "3023b.dat"),  # under the slope's higher half only
    line(14, 20, -24, 0, "15068.dat"),  # its lower half on the brick's studs
]


def test_curved_slope_over_a_plate_end_only_touches():
    r = check("\n".join(SLOPE_OVER_PLATE_END))
    assert r.ok, r.text()


def test_curved_slope_sunk_a_plate_into_the_plate_is_an_overlap():
    sunk = SLOPE_OVER_PLATE_END[:2] + [line(14, 20, -16, 0, "15068.dat")]
    r = check("\n".join(sunk))
    assert any(i.kind == "overlap" and i.lines == [2, 3] for i in r.problems)


BESIDE_A_FLANGE = [
    line(4, 0, -8, 0, "3020.dat"),
    line(1, 0, -16, 10, "3023b.dat"),
    line(2, 0, -24, 10, "3023b.dat"),
    line(14, 0, -32, 10, "99781.dat"),  # its flange hangs down in front of the two plates
]


def test_plates_against_a_brackets_flange_only_touch():
    r = check("\n".join(BESIDE_A_FLANGE))
    assert r.ok, r.text()


def test_a_plate_pushed_into_a_brackets_flange_is_reported():
    pushed = BESIDE_A_FLANGE[:3] + [line(14, 0, -32, 14, "99781.dat")]
    r = check("\n".join(pushed))
    assert not r.ok and any(4 in i.lines for i in r.problems if i.kind in ("overlap", "stud"))


BAR_IN_OPEN_STUDS = [
    line(4, 0, -24, 0, "3062b.dat"),  # round brick with an open stud
    line(15, 0, -32, 0, "85861.dat"),  # round plate with an open stud
    line(15, 0, -84, 0, "87994.dat"),  # Bar 3L through the plate, into the brick's stud
]


def test_a_bar_in_an_open_stud_is_a_joint_not_checked():
    r = check("\n".join(BAR_IN_OPEN_STUDS))
    assert r.ok, r.text()
    words = fit_words(r)
    assert any(w.startswith("line 3 (") and "bar in an open stud of line 2" in w for w in words)
    assert not unchecked_words(r)


def test_a_bar_beside_the_stud_is_not_held():
    beside = BAR_IN_OPEN_STUDS[:2] + [line(15, 10, -96, 0, "87994.dat")]
    r = check("\n".join(beside))
    assert any(i.kind == "loose" and i.lines == [3] for i in r.problems)
    assert not any("bar in" in w for w in unchecked_words(r) + fit_words(r))


def test_a_pin_is_too_thick_for_an_open_stud():
    pin = BAR_IN_OPEN_STUDS[:2] + [line(15, 0, -36, 0, "3673.dat", "0 1 0 -1 0 0 0 0 1")]
    r = check("\n".join(pin))
    assert any(i.kind == "stud" and i.lines == [2, 3] for i in r.problems)
    assert "loose" in kinds(r)


def test_a_bar_through_a_round_bricks_middle():
    r = check(
        "\n".join(
            [
                line(4, 0, -8, 0, "3022.dat"),
                line(15, 0, -32, 0, "3941.dat"),
                line(15, 0, -76, 0, "87994.dat"),
            ]
        )
    )
    assert r.ok, r.text()
    assert any("bar in an axle hole" in w for w in fit_words(r))


def test_a_claw_standing_in_an_open_stud():
    claw = [
        line(4, 0, -24, 0, "3005.dat"),
        line(15, 0, -32, 0, "85861.dat"),
        line(0, 0, -38, 0, "10187.dat", "0 0 1 0 1 0 -1 0 0"),  # its bar-shaped end down
    ]
    r = check("\n".join(claw))
    assert r.ok, r.text()
    assert any("bar in an open stud" in w for w in fit_words(r))
    # on a plain stud (no hollow) the same claw collides
    solid_stud = [claw[0], line(15, 0, -32, 0, "6141.dat"), claw[2]]
    on_solid = check("\n".join(solid_stud))
    assert any(i.kind == "stud" and i.lines == [2, 3] for i in on_solid.problems)


def test_a_bar_tube_takes_a_bar():
    from bricksnap.lab.validate import Placed, _ends

    lib = ldraw_lib.library()
    p = lib.part("23443.dat")  # Bar Tube with Handle: a tube for a bar, and a handle
    tube = Placed(1, 2, np.zeros(3), np.eye(3), "23443.dat", "23443.dat", p, 0)
    assert {"bar-", "bar+"} <= _ends(tube, tube, np.zeros((2, 3)))


TURN_X = "0 0 -1 0 1 0 1 0 0"
AXLE_AND_WHEELS = [
    line(72, 10, -40, 0, "3700.dat", TURN_X),  # holes along x, at y -30
    line(72, -10, -40, 0, "3700.dat", TURN_X),
    line(71, 0, -30, 0, "44294.dat"),  # Technic Axle 7, through both holes
    line(15, 60, -30, 0, "55982.dat", TURN_X),
    line(0, 60, -30, 0, "89201.dat", TURN_X),
    line(15, -60, -30, 0, "55982.dat", "0 0 1 0 1 0 -1 0 0"),
    line(0, -60, -30, 0, "89201.dat", "0 0 1 0 1 0 -1 0 0"),
]


def test_axles_are_read_as_axles(lib):
    for key in ("44294.dat", "3704.dat"):
        assert {c.kind for c in lib.part(key).others} == {"axle"}
    assert {c.kind for c in lib.part("43093.dat").others} == {"axle", "pin"}  # axle pin
    assert {c.kind for c in lib.part("3713.dat").others} == {"axle hole"}  # a bush
    assert {c.kind for c in lib.part("6538b.dat").others} == {"axle hole"}  # a joiner


def test_an_axle_through_a_brick_carrying_wheels():
    r = check("\n".join(AXLE_AND_WHEELS))
    assert r.ok, r.text()
    axle = [w for w in fit_words(r) if "on the axle of line" in w]
    assert len(axle) == 4  # two bricks, two wheels: each tested for fit


def test_an_axle_that_misses_the_hole_is_reported():
    missed = list(AXLE_AND_WHEELS)
    missed[2] = line(71, 0, -38, 0, "44294.dat")  # 8 LDU above the holes' line
    r = check("\n".join(missed))
    assert any(i.kind == "overlap" and i.lines == [1, 3] for i in r.problems)
    assert any(i.kind == "loose" and 3 in i.lines for i in r.problems)
    assert not any("axle" in w for w in unchecked_words(r) + fit_words(r))


CUTOUT = "0 0 -1 0 1 0 1 0 0"  # 29120 turned: its cutout end towards +x


def test_a_stud_under_a_slope_with_a_cutout(lib):
    from bricksnap.lab.place import sockets
    from bricksnap.lab.validate import stud_grid

    part = lib.part("29120.dat")
    assert stud_grid(part) == (0.0, 10.0)  # cells at z -10 and 10, from its flush end
    assert part.socket_phase() == (0.0, 13.0)  # what place numbers sockets by: unchanged
    # the same two sockets, in the same order, now on the checker's grid
    assert [round(float(s.pos[2])) for s in sockets(part)] == [-10, 10]
    r = check(line(72, 0, -8, 0, "3022.dat") + "\n" + line(72, 20, 0, 10, "29120.dat", CUTOUT))
    assert r.ok, r.text()


def test_a_slope_with_a_cutout_half_a_stud_off_is_reported():
    r = check(line(72, 0, -8, 0, "3022.dat") + "\n" + line(72, 30, 0, 10, "29120.dat", CUTOUT))
    stud = next(i for i in r.problems if i.kind == "stud")
    assert "10 LDU off" in stud.text


TOOTH_ON_SIDE = "1 0 0 0 0 1 0 -1 0"  # its stud points along +z


def test_a_stud_in_a_technic_pin_hole():
    brick = line(72, 0, -24, 0, "32000.dat")  # pin holes along z at x -10 and 10, y -14
    r = check(brick + "\n" + line(15, -10, -14, -10, "49668.dat", TOOTH_ON_SIDE))
    assert r.ok, r.text()
    assert any("in its Technic pin hole" in w for w in fit_words(r))
    off = check(brick + "\n" + line(15, -6, -14, -10, "49668.dat", TOOTH_ON_SIDE))
    assert any(i.kind == "stud" for i in off.problems) and "loose" in kinds(off)


def test_the_same_part_twice_is_an_overlap_even_when_it_joins_by_hinges():
    hinge = line(8, 0, -8, 0, "3937.dat")  # hinge brick base: joins by a hinge
    r = check(hinge + "\n" + hinge)
    over = next(i for i in r.problems if i.kind == "overlap")
    assert over.lines == [1, 2] and "same part twice" in over.text
    assert not r.unchecked and not r.fits


# ---- the limits of a bar in a hollow (the review's cases): each fails if its limit loosens --


def joined_by_bar(report, lines) -> bool:
    """A bar in a hollow between the two lines, which is a joint tested for fit."""
    return any(set(i.lines) == set(lines) and "as a bar in" in i.text for i in report.fits)


OPEN_STUD_PLATE = [line(7, 0, -8, 0, "3036.dat"), line(14, 10, -16, 10, "85861.dat")]


def bar_at(y: float, extra: str = "") -> str:
    return line(1, 10, y, 10, "87994.dat") + extra


def test_a_bar_must_be_in_the_open_stud_its_depth_less_one():
    # the stud's base is at y -16, its tip at -20; Bar 3L is 60 long, its end at y + 60
    for into, joined in ((4, True), (3, True), (2, False), (1, False)):
        r = check("\n".join([*OPEN_STUD_PLATE, bar_at(-76 - (4 - into))]))
        assert joined_by_bar(r, [2, 3]) == joined, into
        assert (not r.problems) == joined, into


def test_an_upper_half_hung_on_a_bar_entering_by_1_is_loose():
    upper = [
        line(1, 10, -79, 10, "87994.dat"),
        line(2, 10, -80, 20, "4085c.dat"),
        line(2, 0, -88, 30, "3020.dat"),
        line(2, 0, -112, 30, "3001.dat"),
    ]
    r = check("\n".join([*OPEN_STUD_PLATE, *upper]))
    assert any(i.kind == "loose" and 3 in i.lines for i in r.problems)


def test_a_bar_leaning_5_degrees_in_an_open_stud_is_not_held():
    m = "0.99619 -0.08716 0 0.08716 0.99619 0 0 0 1"
    lean = line(1, 15.22934, -75.77168, 10, "87994.dat", m)  # its end on the stud's base
    r = check("\n".join([*OPEN_STUD_PLATE, lean]))
    assert not joined_by_bar(r, [2, 3]) and r.problems
    # turned about a point 8 LDU above the stud's base: never 1 LDU off the axis there,
    # but leaning 5 degrees
    pivot = line(1, 14.5297, -75.7714, 10, "87994.dat", m)
    r = check("\n".join([*OPEN_STUD_PLATE, pivot]))
    assert not joined_by_bar(r, [2, 3]) and r.problems


def test_a_plate_floating_2_above_a_jumper_is_not_held():
    base = [line(7, 0, -8, 0, "3036.dat"), line(14, 0, -16, -30, "3794b.dat")]
    seated = check("\n".join([*base, line(1, 0, -24, -30, "3023b.dat")]))
    assert seated.ok and joined_by_bar(seated, [2, 3])
    floating = check("\n".join([*base, line(1, 0, -26, -30, "3023b.dat")]))
    assert any(i.kind == "loose" and i.lines == [3] for i in floating.problems)


def test_a_bar_driven_through_a_bricks_top_is_an_overlap():
    r = check(line(4, 0, -24, 0, "3003.dat") + "\n" + line(1, 0, -72, 0, "87994.dat"))
    assert any(i.kind == "overlap" and i.lines == [1, 2] for i in r.problems)
    assert not joined_by_bar(r, [1, 2])


def test_a_bar_driven_past_a_jumpers_4_deep_stud_is_reported():
    r = check(
        "\n".join(
            [
                line(4, 0, -24, 0, "3003.dat"),
                line(14, 0, -32, 10, "3794b.dat"),
                line(1, 0, -88, 10, "87994.dat"),  # 8 into a stud whose hollow is 4 deep
            ]
        )
    )
    assert not r.ok and not joined_by_bar(r, [2, 3])


def test_a_bar_down_a_round_bricks_middle_and_on_into_the_plate_is_reported():
    text = [
        line(7, 0, -8, 0, "3036.dat"),
        line(14, 0, -32, 0, "3941.dat"),
        line(1, 0, -82, 0, "30374.dat"),  # 80 long: 6 LDU on into the plate's top
    ]
    r = check("\n".join(text))
    assert any(i.kind == "overlap" and i.lines == [1, 3] for i in r.problems)
    text[2] = line(1, 0, -88, 0, "30374.dat")  # down to the plate's top: fine
    assert check("\n".join(text)).ok


CAT = (
    Path(__file__).parent.parent
    / "docs/research/2026-11-19-ai-as-the-builder/with-tools/our-cat.ldr"
)


def moved(text: str, n: int, dx: float = 0, dy: float = 0) -> str:
    lines = text.splitlines()
    t = lines[n - 1].split()
    t[2], t[3] = str(float(t[2]) + dx), str(float(t[3]) + dy)
    lines[n - 1] = " ".join(t)
    return "\n".join(lines)


def test_a_whisker_moved_into_a_side_stud_at_an_angle_is_not_a_bar_joint():
    cat = CAT.read_text()
    assert check(cat).ok
    r = check(moved(cat, 127, dx=4))
    assert any(127 in i.lines for i in r.problems)


def test_a_surface_along_the_axis_is_not_a_bar():
    # the hinge base moved up 8: an open side stud's axis runs along its round outside
    r = check(moved(CAT.read_text(), 126, dy=-8))
    assert any(i.kind == "stud" and i.lines == [77, 126] for i in r.problems)


AXLE_IN_BRICK = [line(7, 0, -8, 0, "3036.dat"), line(14, 0, -32, 10, "3700.dat")]


def test_an_axle_askew_3_degrees_joins_8_does_not():
    m3 = "0 0 1 0.05234 0.99863 0 -0.99863 0.05234 0"
    m15 = "0 0 1 0.13917 0.99027 0 -0.99027 0.13917 0"  # 8 degrees
    ok = check("\n".join([*AXLE_IN_BRICK, line(1, 0, -22, 10, "3705.dat", m3)]))
    assert ok.ok and any("on the axle of line" in w for w in fit_words(ok))
    bad = check("\n".join([*AXLE_IN_BRICK, line(1, 0, -22, 10, "3705.dat", m15)]))
    assert not bad.ok and not any("axle" in w for w in unchecked_words(bad) + fit_words(bad))


def test_a_bush_2_beyond_the_axles_end_is_not_on_it():
    axle = line(1, 0, -22, 10, "3705.dat", "0 0 1 0 1 0 -1 0 0")
    r = check("\n".join([*AXLE_IN_BRICK, axle, line(2, 0, -22, 61.5, "3713.dat")]))
    assert any(i.kind == "loose" and i.lines == [4] for i in r.problems)
    on = check("\n".join([*AXLE_IN_BRICK, axle, line(2, 0, -22, 40, "3713.dat")]))
    assert on.ok


def test_two_studs_in_one_pin_hole_the_second_is_reported():
    text = [
        *AXLE_IN_BRICK,
        line(1, 0, -22, 0, "3024.dat", "1 0 0 0 0 1 0 -1 0"),  # stud in from the front
        line(2, 0, -22, 20, "3024.dat", "1 0 0 0 0 -1 0 1 0"),  # and one from the back
    ]
    r = check("\n".join(text))
    stud = next(i for i in r.problems if i.kind == "stud")
    assert stud.lines == [4, 2] and "takes one stud" in stud.text
    assert check("\n".join(text[:3])).ok


def test_place_seats_parts_with_a_cutout_where_the_checker_wants_them(lib):
    from bricksnap.lab.place import place, sockets
    from bricksnap.lab.validate import numbered_studs

    base = line(7, 0, -8, 0, "3031.dat")
    for key in ("29120.dat", "29119.dat", "6044.dat", "3388.dat", "28920.dat", "39739.dat"):
        p = lib.part(key)
        # how many studs and sockets, and their order, are as before (positions of the
        # sockets move onto the checker's grid)
        assert len(sockets(p)) >= 1 and len(numbered_studs(p)) == len(p.studs)
        for turn in range(4):
            placed = place(base, key, 4, 1, stud=6, turn=turn)
            r = check(base + "\n" + placed.line)
            assert r.ok, (key, turn, r.text())


def test_the_line_about_parts_held_only_by_unchecked_joints_is_never_cut():
    from bricksnap.lab.validate import MAX_OTHERS

    text = []  # hinge halves (known by name only), each base on a 1 x 2 brick
    for k in range(MAX_OTHERS + 5):
        text.append(line(4, 60 * k, -24, 10, "3004.dat"))
        text.append(line(72, 60 * k, -48, 10, "3937.dat"))
        text.append(line(0, 60 * k, -48, 10, "3938.dat"))
    r = check("\n".join(text))
    out = r.text()
    assert "joined to what stands on the ground only through those joints" in out
    assert "more joints of the same sort (5 hinge)" in out
    assert "only by joints the checker cannot confirm" in r.summary()


ALONG_Z = "1 0 0 0 0 -1 0 1 0"  # a bar's length along +z


def test_a_bar_must_be_3_ldu_into_a_technic_bricks_through_hole():
    # the library draws the hole as two 2 LDU primitives, one at each face: one hole, 20 deep
    brick = [line(7, 0, -8, 0, "3036.dat"), line(14, 0, -32, 10, "3700.dat")]  # face at z 0
    for into, joined in ((1, False), (2, False), (3, True), (4, True)):
        bar = line(1, 0, -22, -60 + into, "87994.dat", ALONG_Z)
        r = check("\n".join([*brick, bar]))
        assert joined_by_bar(r, [2, 3]) == joined, into
        assert any("a loose fit" in w for w in fit_words(r)) == joined, into


def test_a_bar_right_through_technic_holes_and_a_bush():
    base = line(7, 0, -8, 0, "3036.dat")
    bar = line(1, 0, -22, -20, "87994.dat", ALONG_Z)  # from z -20 to 40
    r = check("\n".join([base, line(14, 0, -32, 10, "3700.dat"), bar]))
    assert r.ok and joined_by_bar(r, [2, 3])
    r = check("\n".join([base, line(14, 0, -32, 10, "32064a.dat"), bar]))
    assert r.ok and any("bar in an axle hole" in w for w in fit_words(r))
    bush = line(2, 0, -22, 30, "3713.dat")  # on the bar beyond the brick
    r = check("\n".join([base, line(14, 0, -32, 10, "3700.dat"), bar, bush]))
    assert r.ok and joined_by_bar(r, [3, 4]), r.text()


def test_a_bar_drawn_as_a_tube_is_a_bar():
    # the bar of "Plate 1 x 1 Round with Bar" is drawn hollow at its end
    text = [
        line(7, 0, -8, 0, "3036.dat"),
        line(14, 10, -32, 10, "59900.dat"),  # a cone: an open stud on top
        line(1, 12, -52, 10, "32828.dat", "0 -1 0 1 0 0 0 0 1"),
    ]
    r = check("\n".join(text))
    assert r.ok and joined_by_bar(r, [2, 3]), r.text()


# ---- a named joint excuses only what it needs (the review's cases): each fails if its limit
# loosens ----------------------------------------------------------------------------------------


FIT_WORDS = {  # how a joint tested for fit says what holds the part
    "wheel pin": "on the wheel pin of line",
    "tyre on a wheel": "round the wheel line",
    "axle": "on the axle of line",
    "Technic pin": "on the Technic pin of line",
}


def fitted(report, lines, words: str) -> bool:
    """A joint of this sort between the two lines, tested for fit."""
    said = FIT_WORDS.get(words, words)
    return any(set(i.lines) == set(lines) and said in i.text for i in report.fits)


def joint_between(report, lines, words: str) -> bool:
    """A joint of this sort between the two lines, of either kind."""
    named = any(
        i.kind == "joint" and i.lines == lines and words in i.text for i in report.unchecked
    )
    return named or fitted(report, lines, words)


def overlap_between(report, lines) -> bool:
    return any(i.kind == "overlap" and i.lines == lines for i in report.problems)


TURN_Z = "-1 0 0 0 1 0 0 0 -1"


def clip_under_handle(dy: float) -> str:
    # a 1 x 1 clip plate on the ground; a plate with a handle turned so its bar lies in the clip
    return "\n".join(
        [line(15, 0, -8, 0, "11476.dat"), line(4, 0, -10.5 + dy, -40, "2540.dat", TURN_Z)]
    )


@pytest.mark.parametrize("dy, held", [(0, True), (-7, True), (-8, False), (-12, False)])
def test_a_clip_holds_a_handle_only_at_its_bar(dy, held):
    # the clip's point is 0.5 LDU from the bar at dy 0, 7.5 at dy -7 (CLIP_REACH), 8.5 at -8
    r = check(clip_under_handle(dy))
    assert joint_between(r, [1, 2], "bar in a clip") == held, r.text()
    assert (not r.problems) == held, r.text()


@pytest.mark.parametrize("dx, clash", [(2, True), (10, True), (40, False)])
def test_two_bar_tubes_in_one_another_are_an_overlap(dx, clash):
    # each has a tube for a bar and a handle: being joinable does not excuse sharing the tube
    r = check(line(4, 0, -6, 0, "23443.dat") + "\n" + line(1, dx, -6, 0, "23443.dat"))
    assert overlap_between(r, [1, 2]) == clash, r.text()
    if clash:
        assert "more than their bar in a clip joint needs" in r.text()


@pytest.mark.parametrize("z, clash", [(20, False), (18, True)])
def test_a_pin_pushed_too_far_brings_its_brick_into_the_other(z, clash):
    # a brick with a pin, its pin in a Technic brick's hole: home at z 20; at z 18 the bricks
    # share a 2 LDU wall outside the hole's room (JOINT_ROOM "pin hole", 8 LDU)
    r = check(line(7, 0, -24, 0, "3700.dat") + "\n" + line(4, 0, -24, z, "2458.dat"))
    assert overlap_between(r, [1, 2]) == clash, r.text()
    assert (not r.problems) == (not clash), r.text()
    if clash:
        assert "more than their Technic pin joint needs" in r.text()


WHEEL_PIN_PLATE = line(72, 0, -30, 0, "4488.dat")  # its pins end at x 34 and -34


def wheel_at(x: float, m: str = "0 0 -1 0 1 0 1 0 0", tyre_dx: float | None = 6) -> str:
    lines = [WHEEL_PIN_PLATE, line(71, x, -25, 0, "6014b.dat", m)]
    if tyre_dx is not None:
        lines.append(line(0, x + tyre_dx, -25, 0, "6015.dat", m))
    return "\n".join(lines)


@pytest.mark.parametrize("x, held", [(30, True), (36, True), (37, False), (40, False)])
def test_a_wheel_must_be_on_its_pin(x, held):
    # the wheel's 7.5 LDU hole must share all but WHEEL_PLAY (2 LDU) with the pin: 5.5 at x 36
    r = check(wheel_at(x, tyre_dx=None))
    assert joint_between(r, [1, 2], "wheel pin") == held, r.text()
    assert (not any(i.kind == "loose" for i in r.problems)) == held, r.text()
    # with its tyre the wheel is judged the same; the tyre itself need only be round the
    # pin's line (WHEEL_IN), so a wheel slid off with its tyre still hangs on the tyre
    r = check(wheel_at(x))
    assert joint_between(r, [1, 2], "wheel pin") == held, r.text()


def test_a_wheel_turned_across_its_pin_is_an_overlap():
    r = check(wheel_at(30, UP))
    assert not joint_between(r, [1, 2], "wheel pin")
    assert overlap_between(r, [1, 2]), r.text()


@pytest.mark.parametrize("dx, on", [(6, True), (10, True), (18, False)])
def test_a_tyre_is_on_its_wheel_only_round_it(dx, on):
    r = check(wheel_at(30, tyre_dx=dx))
    assert joint_between(r, [2, 3], "tyre on a wheel") == on, r.text()


@pytest.mark.parametrize("dx, clash", [(10, True), (20, True), (40, False)])
def test_two_wheels_with_tyres_are_not_a_tyre_on_a_wheel(dx, clash):
    # 66727c01 is a wheel and its tyre in one part: two of them are not a tyre on a wheel
    turned = "0 0 -1 0 1 0 1 0 0"
    r = check(
        line(0, 0, -20, 0, "66727c01.dat", turned)
        + "\n"
        + line(0, dx, -20, 0, "66727c01.dat", turned)
    )
    assert not joint_between(r, [1, 2], "tyre on a wheel"), r.text()
    assert overlap_between(r, [1, 2]) == clash, r.text()


BAR_ON_A_BRICK = [line(7, 0, -8, 0, "3036.dat"), line(14, 0, -32, 0, "3003.dat")]


@pytest.mark.parametrize("sunk", [2, 4, 6])
def test_a_bar_sunk_into_a_solid_top_is_told_it_is_inside(sunk):
    r = check("\n".join([*BAR_ON_A_BRICK, line(1, 0, -92 + sunk, 0, "87994.dat")]))
    loose = next(i.text for i in r.problems if i.kind == "loose")
    assert f"It is sunk {sunk} LDU into line 2 (3003.dat" in loose, loose
    assert f"move line 3 by (0 -{sunk} 0), to 0 -92 0" in loose, loose
    assert "no part under it" not in loose and "rests on" not in loose


@pytest.mark.parametrize("sunk", [0, 1])
def test_a_bar_on_a_solid_top_is_not_called_sunk(sunk):
    r = check("\n".join([*BAR_ON_A_BRICK, line(1, 0, -92 + sunk, 0, "87994.dat")]))
    loose = next(i.text for i in r.problems if i.kind == "loose")
    assert "sunk" not in loose, loose


@pytest.mark.parametrize("sunk", [2, 4, 6])
def test_a_bar_sunk_into_an_end_wall_is_told_the_way_out(sunk):
    # a bar lying along x, its end pushed into the end of a 2 x 4 brick (which ends at x 40)
    turned = "0 1 0 -1 0 0 0 0 1"  # the bar's own y (its length) along world x
    text = [line(7, 0, -8, 0, "3036.dat"), line(14, 0, -32, 0, "3001.dat")]
    r = check("\n".join([*text, line(1, 40 - sunk, -20, 0, "87994.dat", turned)]))
    loose = next(i.text for i in r.problems if i.kind == "loose")
    assert f"It is sunk {sunk} LDU into line 2 (3001.dat" in loose, loose
    assert f"move line 3 by ({sunk} 0 0), to 40 -20 0" in loose, loose


def test_words_that_name_a_move_onto_studs_are_kept():
    # a plate floating over a held bar: the older words already say how to put it on studs
    text = [line(7, 0, -8, 0, "3036.dat"), line(14, 10, -16, 10, "85861.dat")]
    text += [line(1, 10, -72, 10, "87994.dat"), line(4, 10, -69, 0, "3023b.dat")]
    loose = next(i.text for i in check("\n".join(text)).problems if i.kind == "loose")
    assert "Fix: move it down by" in loose and "sunk" not in loose, loose


def test_a_part_with_a_pin_is_never_told_it_is_sunk():
    # a Technic pin pushed 4 LDU down into a brick's top: pins go into things by design
    r = check("\n".join([*BAR_ON_A_BRICK, line(1, 0, -48, 0, "3673.dat", "1 0 0 0 0 1 0 -1 0")]))
    assert not any("sunk" in i.text for i in r.problems), r.text()


def test_a_turntable_shares_what_it_needs():
    # Technic Turntable Type 2, top on base, as the library assembles it (50163)
    text = [line(72, 0, -9, 0, "48452.dat"), line(0, 0, -9, 0, "48168.dat")]
    r = check("\n".join(text))
    assert not r.problems and joint_between(r, [1, 2], "turntable"), r.text()


def test_a_wheel_without_a_hole_has_its_line_from_its_shape():
    # 30027a's box is a 20 LDU cube, so its box gives no axis; its shape is round about z
    from bricksnap.lab.validate import _body_axis

    found = _body_axis("30027a.dat")
    assert found is not None and found[1] == 2 and abs(found[3] - 10) < 0.6
    assert _body_axis("3001.dat") is None
    # as the library assembles it, its tyre is on it; slid 8 LDU along the axis it is not
    tyre = "1 256 0 -18 {} 1 0 0 0 1 0 0 0 1 30028b.dat"
    r = check("\n".join([line(4, 0, -18, 0, "30027a.dat"), tyre.format(0)]))
    assert not r.problems and joint_between(r, [1, 2], "tyre on a wheel"), r.text()
    r = check("\n".join([line(4, 0, -18, 0, "30027a.dat"), tyre.format(8)]))
    assert not joint_between(r, [1, 2], "tyre on a wheel"), r.text()


@pytest.mark.parametrize("x, held", [(36, True), (38, False)])
def test_a_wheel_with_no_hole_must_be_on_half_its_width(x, held):
    # 30027a (20 LDU wide, no hole primitive) on a 4488 pin that ends at x 34: its hub is taken
    # as half its width, so the pin must be in 10 - WHEEL_PLAY = 8 LDU: 8 at x 36, 6 at x 38
    t = (
        line(72, 0, -30, 0, "4488.dat")
        + "\n"
        + line(4, x, -25, 0, "30027a.dat", "0 0 -1 0 1 0 1 0 0")
    )
    assert joint_between(check(t), [1, 2], "wheel pin") == held


@pytest.mark.parametrize("z, tested", [(-10, True), (-12, True), (-12.5, False)])
def test_a_stud_in_a_pin_hole_is_tested_for_fit_within_2_ldu_of_its_face(z, tested):
    # a tooth plate's side stud in a Technic brick's hole: seated at z -10; its base may be up
    # to 2 LDU outside the hole's face (a stated limit), not 2.5
    brick = line(72, 0, -24, 0, "32000.dat")
    r = check(brick + "\n" + line(15, -10, -14, z, "49668.dat", TOOTH_ON_SIDE))
    assert any("in its Technic pin hole" in w for w in fit_words(r)) == tested, r.text()
    assert ("loose" in kinds(r)) == (not tested)


PIN_ALONG_Z = "0 0 1 0 1 0 -1 0 0"  # a pin's own x (its length) along world z


@pytest.mark.parametrize(
    "x, z, tested",
    [(0, -10, True), (0, -12, True), (0, -13, False), (1.5, -10, True), (2, -10, False)],
)
def test_a_technic_pin_is_tested_for_fit_on_its_holes_line_and_depth(x, z, tested):
    # a half pin in a Technic brick's 20 LDU through hole: home at z -10; it must be in all but
    # PIN_PLAY (2 LDU) of the shorter of pin and hole (18 at z -12, 17 at -13), and on the
    # hole's line within AXLE_LDU (1.5)
    brick = line(7, 0, -24, 0, "3700.dat")
    r = check(brick + "\n" + line(4, x, -14, z, "4274.dat", PIN_ALONG_Z))
    assert fitted(r, [1, 2], "Technic pin") == tested, r.text()
    # either way it is a joint: when its fit is not measured it is known by name only
    assert joint_between(r, [1, 2], "Technic pin"), r.text()
    assert (not r.unchecked) == tested


@pytest.mark.parametrize("z, tested", [(10, True), (12, True), (13, False)])
def test_a_full_pins_other_half_is_tested_too(z, tested):
    # the library draws a full Technic pin with a pin primitive for one half only; the other
    # half (here the one in the hole, from z -10 at home) is taken from its box
    brick = line(7, 0, -24, 0, "3700.dat")
    r = check(brick + "\n" + line(4, 0, -14, z, "3673.dat", PIN_ALONG_Z))
    assert fitted(r, [1, 2], "Technic pin") == tested, r.text()


PLANE_WHEEL = "0 0 -1 0 1 0 1 0 0"  # as the builder of the Cessna put its wheels on


@pytest.mark.parametrize("x, tested", [(90, True), (96, True), (97, False)])
def test_a_wheel_with_a_round_box_is_tested_on_half_its_width(x, tested):
    # 4624 has no hole primitive: its line is its round box's axis (BOX_ROUND), its hub half
    # its 16 LDU width, so the 4488's pin must be in 8 - WHEEL_PLAY = 6 LDU: 12 at home (x 90),
    # 6 at x 96, 5 at x 97
    t = line(15, 60, -23, 20, "4488.dat") + "\n" + line(71, x, -18, 20, "4624.dat", PLANE_WHEEL)
    assert fitted(check(t), [1, 2], "wheel pin") == tested


def test_a_tyre_is_tested_for_fit_only_when_both_boxes_are_round():
    # 3641 on 4624: both boxes round (two sides equal) -> tested for fit
    t = [
        line(71, 90, -18, 20, "4624.dat", PLANE_WHEEL),
        line(0, 90, -18, 20, "3641.dat", PLANE_WHEEL),
    ]
    assert fitted(check("\n".join(t)), [1, 2], "tyre on a wheel")
    # 32247's box is 108 x 107.2 (more than BOX_ROUND apart): its line comes from its shape,
    # which is enough to accept its tyre (the library's 32248) but not to measure the fit
    r = check("1 4 0 -65 0 1 0 0 0 1 0 0 0 1 32247.dat\n1 256 0 -65 0 1 0 0 0 1 0 0 0 1 539.dat\n")
    assert not r.problems and joint_between(r, [1, 2], "tyre on a wheel"), r.text()
    assert not fitted(r, [1, 2], "tyre on a wheel"), r.text()


def test_a_part_on_a_joint_tested_for_fit_is_held_as_on_studs():
    brick = line(7, 0, -24, 0, "3700.dat")
    r = check(brick + "\n" + line(4, 0, -14, -10, "4274.dat", PIN_ALONG_Z))
    text = r.text()
    assert r.summary().endswith("every part is held, nothing overlaps, and it stands.")
    assert "NOT CHECKED" not in text
    assert "- line 1 is held on the Technic pin of line 2 (in 20 LDU, 18 asked)" in text
    assert text.endswith(
        "(Joints tested for fit are measured, as studs are, for where and how far one part "
        "goes into the other; how firmly any joint grips is not judged.)"
    )
    off = check(brick + "\n" + line(4, 0, -14, -13, "4274.dat", PIN_ALONG_Z)).text()
    assert "(1 of them only by joints the checker cannot confirm)" in off
    assert "NOT CHECKED (joints known by name only: the checker has not measured the fit" in off
    assert "a Technic pin joint, known by name only" in off and "Joints tested for fit" not in off


def test_report_text_sections():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 10, -48, 0, "3001.dat"))
    text = r.text()
    assert text.startswith("SUMMARY: 2 parts of 1 kind, 2 problems")
    assert "PROBLEMS (fix these):" in text and "HOW IT HOLDS TOGETHER:" in text
    assert "rough" in text


# ---- placing by connection -------------------------------------------------------------------


def test_place_builds_valid_models():
    from bricksnap.lab.place import place

    text = ""

    def put(**kw):
        nonlocal text
        p = place(text, **kw)
        text += p.line + "\n"
        return p

    put(part="3001.dat", colour=4, line=0, x=0, z=0)
    p = put(part="3024.dat", colour=14, line=1, stud=1)
    assert p.line == "1 14 -30 -32 -10 1 0 0 0 1 0 0 0 1 3024.dat"
    put(part="87087.dat", colour=1, line=1, stud=8)
    put(part="3070b.dat", colour=15, line=3, stud=2)  # on the side stud
    put(part="3003.dat", colour=2, line=1, stud=2, turn=1)
    put(part="2417.dat", colour=2, line=5, stud=4, socket=4)  # a leaf on its ring
    put(part="3005.dat", colour=1, line=0, x=100, z=0)
    put(part="3024.dat", colour=1, line=7, stud=1)
    r = check(text)
    assert r.ok, r.text()
    assert len(r.links) == 6


def test_place_turn_counts_in_the_model_frame():
    from bricksnap.lab.place import place

    base = place("", "3032.dat", 15, 0, turn=1).line + "\n"
    p = place(base, "3009.dat", 4, 1, stud=1, turn=1)
    assert p.line.split()[5:14] == ["0", "0", "1", "0", "1", "0", "-1", "0", "0"]  # turn 1
    assert "spans x -40..-20" in p.note
    assert check(base + p.line).ok


def test_place_under_a_socket():
    from bricksnap.lab.place import place

    text = place("", "3001.dat", 4, 0, x=0, z=0).line + "\n"
    hang = place(text, "3024.dat", 1, 1, under_socket=1)
    assert hang.line == "1 1 -30 0 -10 1 0 0 0 1 0 0 0 1 3024.dat"


def test_place_errors_are_plain():
    from bricksnap.lab.place import PlaceError, place

    text = place("", "3001.dat", 4, 0).line + "\n"
    with pytest.raises(PlaceError, match="8 studs"):
        place(text, "3001.dat", 4, 1, stud=9)
    with pytest.raises(PlaceError, match="socket"):
        place(text, "3001.dat", 4, 1, stud=1, socket=99)
    with pytest.raises(PlaceError, match="Say where"):
        place(text, "3001.dat", 4, 1)
    with pytest.raises(PlaceError, match="search_parts"):
        place(text, "nosuch.dat", 4, 1, stud=1)


# ---- the tools --------------------------------------------------------------------------------


@pytest.fixture
def work(tmp_path: Path) -> Path:
    (tmp_path / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 2}))
    return tmp_path


def texts(blocks) -> str:
    return "\n".join(b["text"] for b in blocks if b["type"] == "text")


def test_tools_build_and_check(work, monkeypatch):
    from bricksnap.lab import picture, tools

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)  # no LeoCAD
    t = texts(tools.call_tool(work, "search_parts", {"query": "brick 2 x 4", "limit": 2}))
    assert "3001.dat" in t
    t = texts(tools.call_tool(work, "place", {"part": "3001.dat", "colour": 4, "line": 0}))
    assert "Added as line 1" in t
    t = texts(
        tools.call_tool(work, "place", {"part": "3001.dat", "colour": 1, "line": 1, "stud": 1})
    )
    assert "line 2 is held by" in t
    t = texts(tools.call_tool(work, "part_info", {"line": 2}))
    assert "stud 1: at (-30, -48, -10) pointing up" in t
    t = texts(tools.call_tool(work, "add", {"ldraw": line(2, 200, -80, 0, "3005.dat")}))
    assert "Loose" in t
    t = texts(tools.call_tool(work, "remove", {"lines": [3]}))
    assert "Removed line 3" in t
    t = texts(tools.call_tool(work, "check", {}))
    assert "no problems" in t and "Checks left after this one: 1" in t
    assert (work / "attempts" / "attempt-001-report.txt").exists()
    t = texts(tools.call_tool(work, "submit", {"ldraw": line(4, 0, -24, 0, "3001.dat")}))
    assert "Attempt 2" in t
    t = texts(tools.call_tool(work, "check", {}))
    assert t.startswith("ERROR:") and "all 2 checks" in t
    assert texts(tools.call_tool(work, "model", {})).startswith("  1: 1 4 0 -24 0")
    calls = (work / "calls.jsonl").read_text().splitlines()
    assert len(calls) == 10 and json.loads(calls[-2])["error"] is True  # the refused check


def test_tool_errors_never_raise(work):
    from bricksnap.lab import tools

    for name, args in (
        ("place", {"part": "3001.dat", "colour": "red", "line": 0}),
        ("place", {"part": "3001.dat", "colour": 4, "line": 5, "stud": 1}),
        ("search_parts", {"query": ""}),
        ("part_info", {"part": "nosuch"}),
        ("remove", {"lines": [9]}),
        ("look", {"latitude": 30, "longitude": 0}),
        ("no_tool", {}),
    ):
        blocks = tools.call_tool(work, name, args)
        assert len(blocks) == 1 and blocks[0]["text"].startswith("ERROR:"), (name, blocks)


def test_text_is_scrubbed(work):
    from bricksnap.lab import tools

    t = texts(tools.call_tool(work, "add", {"ldraw": f"0 from someone@example.com in {work}"}))
    assert "someone@example.com" not in (work / "model.ldr").read_text()
    assert str(work) not in t


def test_blind_mode_has_one_submit(tmp_path):
    from bricksnap.lab import tools

    (tmp_path / "config.json").write_text(json.dumps({"mode": "blind"}))
    assert [t["name"] for t in tools.tools_for(tmp_path)] == ["submit"]
    assert texts(tools.call_tool(tmp_path, "search_parts", {"query": "x"})).startswith("ERROR:")
    t = texts(tools.call_tool(tmp_path, "submit", {"ldraw": line(4, 0, -24, 0, "3001.dat")}))
    assert t == "Saved. Your model has been handed in."
    assert "ERROR" in texts(tools.call_tool(tmp_path, "submit", {"ldraw": "1 4 0 0 0 3001.dat"}))
    assert (tmp_path / "final.ldr").exists()


def test_reference_tool_appears_with_pictures(tmp_path):
    from PIL import Image

    from bricksnap.lab import tools

    (tmp_path / "config.json").write_text(json.dumps({"mode": "blind"}))
    (tmp_path / "reference").mkdir()
    Image.new("RGB", (20, 20), "red").save(tmp_path / "reference" / "reference-1.png")
    assert [t["name"] for t in tools.tools_for(tmp_path)] == ["submit", "reference"]
    blocks = tools.call_tool(tmp_path, "reference", {})
    assert [b["type"] for b in blocks] == ["text", "image"]


# ---- pictures (LeoCAD) ------------------------------------------------------------------------


def test_pictures(tmp_path):
    from PIL import Image

    from bricksnap.lab import picture

    if not picture.available():
        pytest.skip("LeoCAD or xvfb-run is not here")
    text = line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -48, 0, "3003.dat") + "\n"
    out = picture.model_sheet(text, tmp_path / "m.png", title="test")
    with Image.open(out) as im:
        assert im.width == 3 * picture.PANEL_PX
        arr = np.asarray(im.convert("RGB"))
    # three panels with something red drawn in each
    for k in range(3):
        panel = arr[100:, k * picture.PANEL_PX : (k + 1) * picture.PANEL_PX]
        red = (panel[..., 0] > 150) & (panel[..., 1] < 80) & (panel[..., 2] < 80)
        assert red.sum() > 500
    assert picture.part_sheet("87087.dat", tmp_path / "p.png").exists()


def test_projection_matches_a_front_view():
    from bricksnap.lab.picture import camera, project

    eye, target = camera(np.array([-40.0, -24, -20]), np.array([40.0, 0, 20]), 0, 0)
    px = project(np.array([[40.0, -12, 0], [-40.0, -12, 0], [0, -24, -20]]), eye, target, 900)
    assert px[0, 0] > 450 > px[1, 0]  # +x is to the right seen from the front
    assert px[2, 1] < 450  # up (-y) is up in the picture


# ---- the MCP server ---------------------------------------------------------------------------


def test_mcp_server_serves_the_tools(work):
    import anyio
    from mcp import ClientSession, StdioServerParameters, stdio_client

    from bricksnap.lab.tools import TOOLS

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "bricksnap.lab.mcp_server", str(work)]
    )

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            a = await session.call_tool("place", {"part": "3001.dat", "colour": 4, "line": 0})
            b = await session.call_tool(
                "place", {"part": "3001.dat", "colour": 4, "line": 7, "stud": 1}
            )
            return listed.tools, a, b

    listed, a, b = anyio.run(go)
    assert [t.name for t in listed] == [t["name"] for t in TOOLS]
    assert not a.is_error and "Added as line 1" in a.content[0].text
    assert b.is_error and "There is no line 7" in b.content[0].text


# ---- running a session (with a stand-in claude) ---------------------------------------------

FAKE = r"""#!{python}
import json, os, sys
argv = sys.argv[1:]
cfg = json.load(open(argv[argv.index("--mcp-config") + 1]))
server = cfg["mcpServers"]["bricksnap"]
folder = server["args"][-1]
record = {{"argv": argv, "stdin": sys.stdin.read(), "server": server}}
json.dump(record, open(os.environ["FAKE_RECORD"], "w"))
mode = json.load(open(os.path.join(folder, "config.json")))["mode"]
model = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 1 0 -48 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
open(os.path.join(folder, "final.ldr" if mode == "blind" else "model.ldr"), "w").write(model)
events = [
    {{"type": "system", "subtype": "init", "model": "claude-fable-5-2", "apiKeySource": "none",
      "tools": ["mcp__bricksnap__submit"],
      "mcp_servers": [{{"name": "bricksnap", "status": "connected"}}]}},
    {{"type": "assistant", "message": {{"model": "claude-fable-5-2", "content": [
        {{"type": "tool_use", "id": "t1", "name": "mcp__bricksnap__check", "input": {{}}}}]}}}},
    {{"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
      "result": "Two red bricks. Mail me at someone@example.com.", "total_cost_usd": 0.5,
      "usage": {{"input_tokens": 100, "output_tokens": 20}},
      "modelUsage": {{"claude-fable-5-2": {{}}}}}},
]
for e in events:
    print(json.dumps(e), flush=True)
"""


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(FAKE.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_RECORD", str(record))
    return record


@pytest.mark.parametrize("mode", ["tools", "blind"])
def test_run_session_saves_everything(fake_claude, tmp_path, monkeypatch, mode, capsys):
    from bricksnap.lab import picture, run

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    out = tmp_path / "session"
    with pytest.raises(SystemExit) as stop:
        run.main(["Build two bricks", "--out", str(out), "--max-checks", "5"], mode=mode)
    assert stop.value.code == 0
    record = json.loads(fake_claude.read_text())
    argv = record["argv"]
    assert argv[argv.index("--model") + 1] == "claude-fable-5-2"
    assert argv[argv.index("--allowedTools") + 1] == "mcp__bricksnap"
    assert "--strict-mcp-config" in argv and "--bare" not in argv
    prompt = argv[argv.index("--system-prompt-file") + 1]
    assert prompt.endswith("blind_prompt.md" if mode == "blind" else "prompt.md")
    assert record["server"]["args"][:2] == ["-m", "bricksnap.lab.mcp_server"]
    assert '"Build two bricks"' in record["stdin"]
    assert ("5 checks" in record["stdin"]) == (mode == "tools")
    session = json.loads((out / "session.json").read_text())
    assert session["ok"] and session["turns"] == 3 and session["mode"] == mode
    assert session["usage_reported"]["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert session["tools_called"] == {"check": 1}
    assert session["final_summary"].startswith("2 parts of 1 kind, no problems")
    assert "<account email>" in session["closing_words"]
    assert (out / "final.ldr").exists() and (out / "final-report.txt").exists()
    transcript = next((out / "transcript").glob("*.jsonl")).read_text()
    assert "someone@example.com" not in transcript and "<account email>" in transcript
    assert "results in" in capsys.readouterr().out


def test_run_refuses_a_used_folder(tmp_path):
    from bricksnap.lab import run

    (tmp_path / "x").write_text("y")
    with pytest.raises(SystemExit, match="not empty"):
        run.prepare(tmp_path, "tools", 5, [])


def test_message_and_prompts():
    from bricksnap.lab import run

    m = run.message("a red fire truck", "tools", 12, 2)
    assert '"a red fire truck"' in m and "12 checks" in m and "call reference first" in m
    assert "submit" in run.message("x", "blind", 12, 0)
    for f in (run.PROMPT_FILE, run.BLIND_PROMPT_FILE):
        text = f.read_text()
        assert "points DOWN" in text and "0 0 1 0 1 0 -1 0 0" in text


def test_message_for_a_change():
    from bricksnap.lab import run

    m = run.message(
        "make it blue",
        "tools",
        25,
        0,
        start="1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat",
        change_of="a red car",
    )
    assert '"a red car"' in m and '"make it blue"' in m and "Call check first" in m
    assert "Build this model" not in m and "25 checks" in m
    assert "# When you are asked for a change" in run.PROMPT_FILE.read_text()


def test_image_blocks_are_png(tmp_path):
    from PIL import Image

    from bricksnap.lab.tools import _image_block

    Image.new("RGB", (40, 30), "blue").save(tmp_path / "a.png")
    block = _image_block(tmp_path / "a.png")
    assert block["media_type"] == "image/png"
    assert base64.b64decode(block["data"]).startswith(b"\x89PNG")


# ---- starting from a model; filling, clearing and mirroring ----------------------------------

DUCK = (
    Path(__file__).resolve().parent.parent / "samples" / "projects" / "duck-showcase" / "build.ldr"
)


def test_big_model_report_is_short():
    import time

    if not DUCK.exists():
        pytest.skip("the duck sample is not here")
    started = time.monotonic()
    r = check(DUCK.read_text())
    assert time.monotonic() - started < 20
    assert r.ok, r.text()  # BrickSnap's own output passes
    text = r.text()
    assert len(text.splitlines()) < 12
    assert "parts are held by studs" in text and "held by a single stud" in text


def test_long_issue_lists_are_cut_short():
    lines = [line(4, 40 * k, -100, 0, "3005.dat") for k in range(60)]  # 60 loose bricks
    lines.append(line(4, -400, -24, 0, "3001.dat"))
    text = check("\n".join(lines)).text()
    assert "... and" in text and "more (" in text


def test_fill_is_one_piece_and_checks_clean():
    from bricksnap.lab.edit import fill

    solid = fill((-40, 0, -20), (4, 2, 3), 4)
    assert solid.lines == ["1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat", "0 STEP"]
    assert len(solid.free_studs) == 8
    for top, hollow in (("tiles", False), ("studs", True), ("studs", False)):
        f = fill((-60, 0, -60), (6, 6, 6), 1, top=top, hollow=hollow)
        assert check("\n".join(f.lines)).ok
        assert (len(f.free_studs) == 0) == (top == "tiles")
    tiled = fill((0, -24, 0), (2, 1, 2), 14, top="tiles")
    assert tiled.lines[-2].endswith("3069b.dat")  # the plain tile, not the grille


def test_fill_refuses_off_grid_corners():
    from bricksnap.lab.edit import EditError, fill

    with pytest.raises(EditError, match="multiples of 10"):
        fill((5, 0, 0), (2, 2, 3), 4)
    with pytest.raises(EditError, match="3 by 3"):
        fill((0, 0, 0), (2, 2, 3), 4, hollow=True)


def test_parts_in_box_modes():
    from bricksnap.lab.edit import parts_in_box

    text = "\n".join(
        [
            line(4, 0, -24, 0, "3001.dat"),
            line(1, 0, -48, 0, "3003.dat"),
            line(2, 60, -24, 0, "3005.dat"),
        ]
    )
    lo, hi = np.array([-45.0, -60, -25]), np.array([45.0, -30, 25])
    assert [p.line for p in parts_in_box(text, lo, hi)] == [2]
    assert [p.line for p in parts_in_box(text, lo, hi, "touching")] == [2]
    big_lo = np.array([-45.0, -60, -25])
    assert [p.line for p in parts_in_box(text, big_lo, np.array([45.0, 0, 25]), "inside")] == [1, 2]


def test_mirror():
    from bricksnap.lab.edit import mirror

    text = "\n".join(
        [
            line(4, 40, -24, 0, "3039.dat"),
            line(4, 60, -8, -40, "41770a.dat"),
            line(2, 50, -24, 60, "87087.dat", "0 0 1 0 1 0 -1 0 0"),
            line(4, 0, -24, 0, "3001.dat"),
            line(2, 30, -40, 80, "3741a.dat"),
        ]
    )
    out = {m.line: m for m in mirror(text, [1, 2, 3, 4, 5])}
    assert out[1].new_line == "1 4 -40 -24 0 1 0 0 0 1 0 0 0 1 3039.dat"
    assert out[2].new_line == "1 4 -60 -8 -40 1 0 0 0 1 0 0 0 1 41769a.dat"
    assert "Right" in out[2].note
    assert out[3].new_line == "1 2 -50 -24 60 0 0 -1 0 1 0 1 0 0 87087.dat"  # stud now +x
    assert out[4].new_line is None and "its own copy" in out[4].note
    assert out[5].new_line is None and "build that side yourself" in out[5].note


def test_centre_x_keeps_the_stud_grid():
    from bricksnap.lab.edit import centre_x

    text, shift = centre_x(line(4, 180, -24, 0, "3001.dat") + "\n0 STEP\n")
    assert shift == -180 and text.startswith("1 4 0 -24 0 ")
    assert centre_x(line(4, 30, -24, 0, "3005.dat"))[1] == -30


def test_tools_fill_mirror_remove_box(work, monkeypatch):
    from bricksnap.lab import tools

    t = texts(tools.call_tool(work, "fill", {"at": [-40, 0, -40], "size": [4, 4, 3], "colour": 4}))
    assert "Added" in t and "studs free on top" in t
    stack = "\n".join(
        [
            line(4, 200, -24, 0, "3001.dat"),
            line(1, 200, -48, 0, "3001.dat"),
            line(14, 170, -56, -10, "3024.dat"),
            line(2, 230, -72, 0, "87087.dat", "0 0 1 0 1 0 -1 0 0"),
        ]
    )
    n = len(tools._model(work).splitlines())
    tools.call_tool(work, "add", {"ldraw": stack})
    t = texts(tools.call_tool(work, "mirror", {"lines": [n + 4], "plane_x": 200}))
    assert "Added 1 mirrored parts" in t and "its own mirror image, at 170 -72 0" in t
    t = texts(
        tools.call_tool(
            work, "remove_box", {"min": [9, -6, -1], "max": [11, -3, 1], "unit": "studs"}
        )
    )
    assert t.startswith("Removed 1 parts") and f"lines {n + 2} " in t
    assert f"Now loose (3 parts): lines {n + 3}, {n + 4}, {n + 5}" in t
    t = texts(tools.call_tool(work, "remove_box", {"min": [500, 0, 0], "max": [600, -10, 10]}))
    assert "No part is in that box" in t
    for bad in (
        {"at": [5, 0, 0], "size": [2, 2, 3], "colour": 4},
        {"at": [0, 0], "size": [1, 1, 1], "colour": 4},
    ):
        assert texts(tools.call_tool(work, "fill", bad)).startswith("ERROR:")


@pytest.mark.parametrize("mode", ["tools", "blind"])
def test_run_with_start(fake_claude, tmp_path, monkeypatch, mode):
    from bricksnap.lab import picture, run

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    start = tmp_path / "start.ldr"
    start.write_text("0 a start\n" + line(4, 180, -24, 0, "3001.dat") + "\n")
    out = tmp_path / "session"
    with pytest.raises(SystemExit):
        run.main(["Improve it", "--out", str(out), "--start", str(start)], mode=mode)
    cfg = json.loads((out / "config.json").read_text())
    assert cfg["start"] == {"file": "start.ldr", "moved_x_by": -180.0}
    assert (out / "attempts" / "attempt-000-report.txt").read_text().startswith("Attempt 0")
    stdin = json.loads(fake_claude.read_text())["stdin"]
    if mode == "blind":
        assert "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat" in stdin  # the model is in the message
    else:
        assert "Call check first" in stdin
    session = json.loads((out / "session.json").read_text())
    assert session["checks"] == 0 and session["start"] == "start.ldr"


def test_start_model_ends_with_a_step(work):
    from bricksnap.lab import tools

    tools.start_model(work, line(4, 0, -24, 0, "3001.dat") + "\n\n")
    assert tools._model(work).splitlines()[-1] == "0 STEP"
    assert tools._attempts(work) == []  # attempt 0 is not one of the checks
