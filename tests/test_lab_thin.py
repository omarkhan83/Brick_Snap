"""Thin members on clips and bars: the constructions a styled model needs (struts, blades,
rails, aerials, legs), each built from library parts in a small model and checked with every
joint in it tested for fit, then broken one way and seen reported; and the limits of a clip
tested for fit on a bar or a handle, each on both sides.

The geometry is worked out here from the parts themselves (``frame``, ``grip_line``): where a
clip's grip is, where a handle's bar is, which way a bar tube's bore points.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pytest

from bricksnap.lab import ldraw_lib

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(),
    reason=f"the lab's tests read the LDraw parts library, which is not on this machine "
    f"({ldraw_lib.zip_path()}); the rest of BrickSnap does not need it",
)

BASE = "1 7 0 -8 0 1 0 0 0 1 0 0 0 1 3036.dat\n"  # a 6 x 8 plate on the ground


def check(text: str):
    from bricksnap.lab.validate import check as run

    return run(text)


def line(colour: int, pos, m, key: str) -> str:
    from bricksnap.lab.place import ldraw_line

    return ldraw_line(colour, np.asarray(pos, float), np.asarray(m, float), key) + "\n"


def frame(a_local, a_world, b_local, b_world) -> np.ndarray:
    """The rotation taking local direction a to world a, and b (made square to a) to b."""

    def basis(a, b):
        a = np.asarray(a, float) / np.linalg.norm(a)
        b = np.asarray(b, float) - (np.asarray(b, float) @ a) * a
        b = b / np.linalg.norm(b)
        return np.stack([a, b, np.cross(a, b)], 1)

    return basis(a_world, b_world) @ basis(a_local, b_local).T


def placed(text: str, n: int):
    from bricksnap.lab.validate import Placed

    t = text.splitlines()[n - 1].split()
    pos = np.array([float(v) for v in t[2:5]])
    m = np.array([float(v) for v in t[5:14]]).reshape(3, 3)
    return Placed(n, int(t[1]), pos, m, t[14], t[14], ldraw_lib.library().part(t[14]), 0)


def handle_middle(text: str, n: int):
    """The middle of the handle's bar of line n, and its direction (world)."""
    from bricksnap.lab.validate import _handle_bars

    e0, e1 = _handle_bars(placed(text, n))[0]
    return (e0 + e1) / 2, (e1 - e0) / np.linalg.norm(e1 - e0)


def held_only(report) -> list[int]:
    return next((i.lines for i in report.unchecked if i.kind == "held by unchecked joints"), [])


def all_fitted(report) -> bool:
    """No problem, nothing held only by joints known by name, no joint known by name."""
    return not report.problems and not held_only(report) and not report.unchecked


def clips_fitted(report) -> int:
    return sum(1 for i in report.fits if "by the clip of line" in i.text)


def tubes_fitted(report) -> int:
    return sum(1 for i in report.fits if "bar in a bar tube" in i.text)


# ---- a bar in a bar tube --------------------------------------------------------------------

# 11090 (Bar Tube with Clip): its clip at its origin along its own z, its bore from y 30 (open)
# in to a stop at y 20; here it stands on its clip's handle, the bore pointing down
HANDLE = "1 72 0 -16 -50 1 0 0 0 1 0 0 0 1 48336.dat\n"  # its handle over the plate's front edge


def tube_on_handle(angle: float) -> tuple[str, np.ndarray, np.ndarray]:
    """11090 on the handle, its bore turned ``angle`` degrees down from straight out (-z)."""
    text = BASE + HANDLE
    mid, hd = handle_middle(text, 2)
    a = math.radians(angle)
    out = np.array([0, math.sin(a), -math.cos(a)])
    R = frame([0, 0, 1], hd, [0, 1, 0], out)
    return text + line(15, mid, R, "11090.dat"), mid + R @ np.array([0, 30.0, 0]), out


@pytest.mark.parametrize("into, held", [(2, False), (3, True), (10, True)])
def test_a_bar_in_the_tube_of_11090_is_tested_for_fit(into, held):
    # the bar must be in BAR_DEPTH - BAR_PLAY = 3 LDU (the bore is 10 deep, to a stop)
    text, mouth, out = tube_on_handle(-90)  # bore pointing straight up
    R = frame([0, 1, 0], -out, [1, 0, 0], [1, 0, 0])  # the bar's length up into the bore
    bar = line(1, mouth + out * (60 - into), R, "87994.dat")  # its top end `into` LDU in
    r = check(text + bar)
    assert (tubes_fitted(r) == 1) == held, r.text()
    if held:
        assert all_fitted(r), r.text()


def test_a_bar_pushed_past_the_stop_of_11090_is_an_overlap():
    text, mouth, out = tube_on_handle(-90)
    R = frame([0, 1, 0], -out, [1, 0, 0], [1, 0, 0])
    r = check(text + line(1, mouth + out * (60 - 14), R, "87994.dat"))  # 14 in: 4 past it
    assert any(i.kind == "overlap" and 4 in i.lines for i in r.problems), r.text()
    assert tubes_fitted(r) == 0


def tube_bores(key: str) -> list[tuple[list[float], list[float]]]:
    from bricksnap.lab.validate import Placed, _tube_hollows

    p = Placed(1, 0, np.zeros(3), np.eye(3), key, key, ldraw_lib.library().part(key), 0)
    return [(np.round(h.p0, 1).tolist(), np.round(h.p1, 1).tolist()) for h in _tube_hollows(p)]


def test_a_bar_tubes_bore_has_a_wall_round_it():
    # 11090's axis is empty at its clip end too, but no wall stands round it there (6 of 8
    # points 5 LDU out): only the real bore, from y 30 to its stop at 20, is one
    assert tube_bores("11090.dat") == [([0.0, 30.0, 0.0], [0.0, 20.0, 0.0])]


def test_a_bar_tubes_bore_is_at_least_bar_depth_deep():
    # 20612 (a ring with three bar tubes) also has a hole 3.9 LDU deep at its middle, less
    # than BAR_DEPTH (4): not a bore; its tube along x is
    assert tube_bores("20612.dat") == [([20.0, 2.7, 0.0], [13.0, 2.7, 0.0])]


def test_a_bar_tubes_wall_is_looked_for_just_outside_a_bar():
    # 24122 has a bar tube at each end (along x) and a pin hole across its middle (along z):
    # the wall is looked for BAR_RING (5) out, just outside a bar (4); at 6 the pin hole would
    # count as bores, at 6.5 the tubes would not
    assert tube_bores("24122.dat") == [
        ([20.0, 0.0, 0.0], [10.5, 0.0, 0.0]),
        ([-20.0, 0.0, 0.0], [-10.0, 0.0, 0.0]),
    ]


# ---- a clip on a bar: its limits ------------------------------------------------------------

CLIP = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 60897.dat\n"  # its grip: through (0, -4, -20), along y


def bar_by_clip(x: float = 0.0, top: float = -60.0, deg: float = 0.0) -> str:
    """A Bar 3L (60 long, down its own y) by 60897's clip: moved x across, its top end at
    ``top``, leaning ``deg`` degrees about x through the clip's point."""
    a = math.radians(deg)
    R = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    c = np.array([0, -4.0, -20])
    return line(0, c + R @ (np.array([x, top, -20.0]) - c), R, "87994.dat")


def test_a_bar_through_the_clips_grip_is_tested_for_fit():
    r = check(CLIP + bar_by_clip())
    assert clips_fitted(r) == 1 and all_fitted(r), r.text()
    said = next(i.text for i in r.fits)
    assert said.startswith("line 2 (87994.dat) is held by the clip of line 1 round its bar")


@pytest.mark.parametrize("deg, held", [(0, True), (5, True), (6, False)])
def test_a_bar_leaning_in_a_clip_is_fitted_up_to_clip_deg(deg, held):
    # CLIP_DEG (5 degrees) between the bar and the grip's direction
    assert (clips_fitted(check(CLIP + bar_by_clip(deg=deg))) == 1) == held


@pytest.mark.parametrize("x, held", [(0, True), (1, False)])
def test_a_bar_off_the_grip_is_not_fitted(x, held):
    # 1 LDU across, the clip's inside reaches within 3 LDU of the bar's line: not in its grip
    r = check(CLIP + bar_by_clip(x=x))
    assert (clips_fitted(r) == 1) == held, r.text()


@pytest.mark.parametrize("top, held", [(-7.0, True), (-6.5, True), (-6.0, False)])
def test_a_clip_must_be_on_the_bar_not_at_its_end(top, held):
    # the bar must be bar-thick GRIP_HALF (2 LDU) either side of the grip's middle (y -4)
    assert (clips_fitted(check(CLIP + bar_by_clip(top=top))) == 1) == held


@pytest.mark.parametrize("x, joined", [(7, True), (12, False)])
def test_a_bar_standing_beside_a_clip_is_joined_only_within_its_reach(x, joined):
    # CLIP_REACH (7.5 LDU) for a bar part as for a handle: 12 LDU beside it is not joined
    r = check(CLIP + bar_by_clip(x=x))
    joint = any(i.kind == "joint" and set(i.lines) == {1, 2} for i in r.unchecked + r.fits)
    assert joint == joined, r.text()
    assert clips_fitted(r) == 0


def test_a_thick_stop_in_the_clip_is_not_a_fit():
    # the rail moved so that its thick stop is in a clip: not bar-thick there
    assert clips_fitted(check(rail())) == 2
    r = check(rail(shift=0))  # the stop (y -6 to 0) in the clip at y -4
    assert clips_fitted(r) == 1, r.text()


def test_a_bar_with_clips_of_its_own_is_still_a_bar():
    # Bar 2L with Three Clips (3628) has clip primitives; its name still makes it a bar, and a
    # clip round that bar is tested for fit (before, its own clips hid its name: "Loose")
    text = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3005.dat\n1 72 0 -32 0 1 0 0 0 1 0 0 0 1 60897.dat\n"
    r = check(text + "1 4 0 -8 -20 1 0 0 0 1 0 0 0 1 3628.dat\n")
    assert clips_fitted(r) == 1 and all_fitted(r), r.text()


@pytest.mark.parametrize("x, held", [(0, True), (-9, False)])
def test_a_clip_with_no_primitive_must_be_round_the_bar(x, held):
    # 15712 (no clip primitive): the grip is where the clip is round the bar (GRIP_RING of 12
    # points at GRIP_R): the leg 9 LDU to the side passes its box, touching it, not its grip
    text = leg().splitlines()
    t = text[-1].split()
    t[2] = str(float(t[2]) + x)
    r = check("\n".join([*text[:-1], " ".join(t)]) + "\n")
    assert (clips_fitted(r) == 1) == held, r.text()


def test_a_part_wider_than_a_bar_has_no_bar_line_from_its_box():
    # 6190 (Bar 1 x 3, 16 LDU across: more than BAR_BOX) gets no line from its box's long axis,
    # which is not its bar; a clip on its bar is measured on the clip's own axis and fitted
    R = frame([0, 1, 0], [1, 0, 0], [1, 0, 0], [0, 1, 0])  # 60897's grip (its y) along x
    grip = np.array([-7.5, -34.1, 0.0])  # on 6190's bar, which runs along its own x
    text = "1 7 0 -30 0 1 0 0 0 1 0 0 0 1 6190.dat\n"
    r = check(text + line(72, grip - R @ np.array([0, 4.0, -20]), R, "60897.dat"))
    assert clips_fitted(r) == 1, r.text()


ON_BRICK = "1 7 0 -24 0 1 0 0 0 1 0 0 0 1 3005.dat\n"
CLIP_61252 = "1 14 0 -32 0 1 0 0 0 1 0 0 0 1 61252.dat\n"
CLIP_60897 = "1 14 0 -32 0 1 0 0 0 1 0 0 0 1 60897.dat\n"


@pytest.mark.parametrize(
    "clip, bar",
    [
        # the review's cases: a bar in an inside corner of the clip's part, not in its grip
        (CLIP_61252, "1 4 30 -35.5 -9.5 0 -1 0 1 0 0 0 0 1 87994.dat"),
        (CLIP_60897, "1 4 -8.5 -75 -13.5 1 0 0 0 1 0 0 0 1 87994.dat"),
        (CLIP_60897, "1 4 8.5 -75 -13.5 1 0 0 0 1 0 0 0 1 87994.dat"),
    ],
)
def test_a_bar_in_a_corner_beside_a_clip_is_not_in_its_grip(clip, bar):
    # a closed grip has the clip round more than half the bar (GRIP_RING 7 of 12); an inside
    # corner gives half (6), and the bar there is not held by the clip
    r = check(ON_BRICK + clip + bar + "\n")
    assert clips_fitted(r) == 0, r.text()


@pytest.mark.parametrize(
    "clip, bar",
    [
        (CLIP_61252, "1 4 0 -30 -76 0 0 1 1 0 0 0 1 0 87994.dat"),  # end-on into the mouth
        (CLIP_61252, "1 4 25.7 -29.5 -35.4 0 -0.866 0.5 1 0 0 0 0.5 0.866 87994.dat"),  # 30 deg
        (
            "1 14 0 -32 0 1 0 0 0 1 0 0 0 1 15712.dat\n",
            "1 4 0 -94 0 1 0 0 0 1 0 0 0 1 87994.dat",  # standing end-on in a tile clip
        ),
    ],
)
def test_a_bar_across_a_clips_grip_is_not_fitted(clip, bar):
    # the grip has one direction (``grip_lines``, for clips with or without a primitive): a bar
    # end-on into the clip's mouth or 30 degrees across it is not along it
    r = check(ON_BRICK + clip + bar + "\n")
    assert clips_fitted(r) == 0, r.text()


def test_a_thick_u_clip_has_no_closed_grip_and_is_known_by_name():
    from bricksnap.lab.validate import grip_lines

    assert grip_lines("4085c.dat") == []
    assert [d.round(3).tolist() for _, d in grip_lines("60897.dat")] == [[0.0, 1.0, 0.0]]
    # 15712 has no clip primitive: its grip is found in its shape, along its own z
    assert [d.round(3).tolist() for _, d in grip_lines("15712.dat")] == [[0.0, 0.0, 1.0]]
    # a roadsign's C-clip is round the bar at 7 points of 12 (the least a closed grip has)
    assert len(grip_lines("30258.dat")) == 1


def test_a_grip_is_looked_for_in_the_clip_not_in_its_opening():
    from bricksnap.lab.validate import grip_lines

    # 98460's clip (a fence's) is empty out to 4.75 LDU round its line and solid from 5: the
    # circle of GRIP_R (5.5) is in the clip; one at 4.75 would be in the opening and find no grip
    assert len(grip_lines("98460.dat")) == 1


def test_a_stored_grip_is_served_only_under_the_key_it_was_found_under(tmp_path, monkeypatch):
    import json

    from bricksnap.lab import validate

    monkeypatch.setenv("BRICKSNAP_LAB_CACHE", str(tmp_path))
    monkeypatch.setattr(validate, "_GRIPS", {})

    def grips() -> list:
        validate._GRIPS.clear()
        return [[x.round(1).tolist(), d.round(3).tolist()] for x, d in validate.grip_lines(key)]

    key = "60897.dat"
    real = grips()
    stored = tmp_path / "grips" / f"{key}.json"
    found = json.loads(stored.read_text())
    assert found["grips"] and [d for _, d in real] == [[0.0, 1.0, 0.0]]
    wrong = [[[0.0, 4.0, 15.0], [1.0, 0.0, 0.0]]]

    stored.write_text(json.dumps({"key": found["key"], "grips": wrong}))
    assert grips() == wrong  # under today's key the stored grip is used: no search
    stored.write_text(json.dumps(wrong))  # stored with no key (as before it had one)
    assert grips() == real
    for part in ("library", "solid", "search"):  # another library, solid or search code
        stale = {**found["key"], part: "another"}
        stored.write_text(json.dumps({"key": stale, "grips": wrong}))
        assert grips() == real, part
    stored.write_text(json.dumps({"key": found["key"], "grips": wrong}))
    monkeypatch.setattr(validate, "GRIP_TURN", 30.0)  # any number of the search changed
    assert grips() == real


@pytest.mark.parametrize("angle", [0, 30, 45, 90])
def test_a_clip_on_a_handle_is_fitted_at_any_angle_about_it(angle):
    text, _, _ = tube_on_handle(-angle)  # turned up from straight out
    r = check(text)
    assert clips_fitted(r) == 1 and all_fitted(r), r.text()


# ---- the constructions style needs ----------------------------------------------------------


def bar_between(a: np.ndarray, b: np.ndarray, key: str, length: float, colour: int = 1) -> str:
    """A bar part (its length down its own y) centred between two points, along them."""
    R = frame([0, 1, 0], b - a, [1, 0, 0], [1, 0, 0] if abs((b - a)[0]) < 1e-6 else [0, 0, 1])
    return line(colour, (a + b) / 2 - R @ np.array([0, length / 2, 0]), R, key)


def strut_on_23443() -> str:
    """Clip plates (60897) on side studs grip the handles of two Bar Tubes with Handle (23443);
    a Bar 4L between the tubes; the grips 5 studs across and 3 bricks up (36 degrees)."""
    from bricksnap.lab.place import place

    text = BASE
    for args in (
        ("3005.dat", 4, 1, 1),
        ("87087.dat", 4, 2, 1),  # 3: the low end, its stud on its side
        ("3005.dat", 4, 1, 6),
    ):
        text += place(text, args[0], args[1], args[2], stud=args[3]).line + "\n"
    for key in ("3005.dat",) * 4 + ("3024.dat",) * 2 + ("87087.dat",):
        n = len(text.splitlines())
        text += place(text, key, 4, n, stud=1).line + "\n"
    high = len(text.splitlines())
    text += place(text, "60897.dat", 72, 3, stud=2, turn=2).line + "\n"  # the clip up
    text += place(text, "60897.dat", 72, high, stud=2).line + "\n"  # the clip down
    grips = []
    for n in (high + 1, high + 2):
        p = placed(text, n)
        c = next(c for c in p.part.others if c.kind == "clip")
        grips.append((p.to_world(c.pos), p.m @ c.axis))
    handle = np.array([-0.25, 0.0, 2.1])  # 23443's handle: along its own z; its bore along -y
    mouths = []
    for (o, g), (o2, _) in zip(grips, grips[::-1], strict=True):
        R = frame([0, 0, 1], g, [0, -1, 0], o2 - o)
        text += line(15, o - R @ handle, R, "23443.dat")
        mouths.append(o - R @ handle + R @ np.array([0, -30.0, 0]))
    return text + bar_between(mouths[0], mouths[1], "30374.dat", 80)


def strut_on_11090(gap: float = 0.0) -> str:
    """Two handle plates 5 studs apart and 3 bricks up, an 11090 clipped on each, its bore
    toward the other, a Bar 4L between the bores (pushed ``gap`` LDU off the line)."""
    text = BASE + HANDLE
    text += "".join(f"1 4 0 {-32 - 24 * k} 50 1 0 0 0 1 0 0 0 1 3004.dat\n" for k in range(3))
    text += "1 72 0 -88 50 1 0 0 0 1 0 0 0 1 48336.dat\n"  # 6: the high handle
    (lo, ld), (hi, hd) = handle_middle(text, 2), handle_middle(text, 6)
    mouths = []
    for (m, d), other in (((lo, ld), hi), ((hi, hd), lo)):
        R = frame([0, 0, 1], d, [0, 1, 0], other - m)
        text += line(15, m, R, "11090.dat")
        mouths.append(m + R @ np.array([0, 30.0, 0]))
    off = np.array([gap, 0, 0])
    return text + bar_between(mouths[0] + off, mouths[1] + off, "30374.dat", 80)


BLADE = [  # flat and along x; clip plates at x 0 and 200, their grips along the blade's y
    ("60897.dat", 0, 0),
    ("3710.dat", 50, 0),
    ("3710.dat", 130, 0),
    ("3024.dat", 180, 0),
    ("60897.dat", 200, 0),
    ("3460.dat", 70, -8),
    ("3623.dat", 180, -8),
    ("4162.dat", 70, -16),
    ("63864.dat", 180, -16),
]


def blade_strut(lift: float = 0.0) -> str:
    """A blade: 1-wide plates on edge, tiled, a clip plate under each end, on two handles
    (48336) 8 studs across and 5 bricks up (the clips 200 LDU apart, 37 degrees); the high
    handle plate raised ``lift`` LDU."""
    text = "1 7 0 -8 0 0 0 1 0 1 0 -1 0 0 4282.dat\n"  # a 2 x 16 plate along z
    text += "1 72 0 -16 -150 1 0 0 0 1 0 0 0 1 48336.dat\n"  # 2: the low handle
    text += "".join(f"1 4 0 {-32 - 24 * k} 10 1 0 0 0 1 0 0 0 1 3004.dat\n" for k in range(5))
    text += f"1 72 0 {-136 - lift} 10 1 0 0 0 1 0 0 0 1 48336.dat\n"  # 8: the high handle
    (a, _), (b, _) = handle_middle(text, 2), handle_middle(text, 8)
    R = frame([0, 1, 0], [-1, 0, 0], [1, 0, 0], b - a)
    pos = a - R @ np.array([0, 4.0, -20])
    return text + "".join(line(15, pos + R @ np.array([x, y, 0.0]), R, k) for k, x, y in BLADE)


def rail(shift: float = 10.0) -> str:
    """A Bar 6L (63965a: from y -104 to 16 in its own frame, a thick stop from -6 to 0)
    lying in two horizontal clip plates (61252) 4 studs apart, its middle between them, moved
    ``shift`` LDU along itself (at 10 the clips grip it at its own y -94 and -14)."""
    text = BASE + (
        "1 72 -30 -16 -50 1 0 0 0 1 0 0 0 1 61252.dat\n"
        "1 72 50 -16 -50 1 0 0 0 1 0 0 0 1 61252.dat\n"
    )
    R = frame([0, 1, 0], [1, 0, 0], [1, 0, 0], [0, 1, 0])
    mid = np.array([10.0, -14.5, -70])  # between the two grips
    return text + line(0, mid - R @ np.array([0, -44.0 - shift, 0]), R, "63965a.dat")


def leg(drop: float = 0.0) -> str:
    """A leg: a Bar 3L standing in a clip tile (15712) on the side of a brick, under a plate."""
    from bricksnap.lab.place import place

    text = BASE
    text += place(text, "3005.dat", 4, 1, stud=12).line + "\n"
    text += place(text, "87087.dat", 4, 2, stud=1).line + "\n"  # 3: its side stud faces -z
    text += place(text, "3022.dat", 15, 3, stud=1, socket=1).line + "\n"  # 4: the plate
    text += place(text, "15712.dat", 72, 3, stud=2).line + "\n"  # 5: the clip tile
    return text + f"1 0 -10 {-74 + drop} -53.5 1 0 0 0 1 0 0 0 1 87994.dat\n"


def aerial() -> str:
    """A lever (4592 with 4593) and a Bar 3L standing in an open stud (85861)."""
    from bricksnap.lab.place import place

    text = BASE + place(BASE, "4592.dat", 72, 1, stud=12).line + "\n"
    p = placed(text, 2)
    text += line(0, p.pos, p.m, "4593.dat")
    text += "1 14 30 -16 30 1 0 0 0 1 0 0 0 1 85861.dat\n"
    return text + "1 1 30 -76 30 1 0 0 0 1 0 0 0 1 87994.dat\n"


def test_a_bar_strut_between_two_bar_tubes_with_handle():
    r = check(strut_on_23443())
    assert all_fitted(r), r.text()
    assert clips_fitted(r) == 2 and tubes_fitted(r) == 2
    # broken: the strut 3 LDU off the tubes' line goes into their walls
    text = strut_on_23443().splitlines()
    t = text[-1].split()
    t[4] = str(float(t[4]) + 3)
    r = check("\n".join([*text[:-1], " ".join(t)]) + "\n")
    assert tubes_fitted(r) == 0 and not all_fitted(r), r.text()


def test_a_bar_strut_between_two_bar_tubes_with_clip():
    r = check(strut_on_11090())
    assert not r.problems and not held_only(r) and not r.unchecked, r.text()
    assert clips_fitted(r) == 2 and tubes_fitted(r) == 2
    r = check(strut_on_11090(gap=3))
    assert r.problems and tubes_fitted(r) < 2, r.text()


def test_a_blade_strut_on_two_handles():
    r = check(blade_strut())
    assert all_fitted(r), r.text()
    assert clips_fitted(r) == 2
    r = check(blade_strut(lift=8))  # the high handle a plate higher: its clip misses it
    assert clips_fitted(r) == 1 and not all_fitted(r), r.text()


def test_a_rail_in_two_clips():
    r = check(rail())
    assert all_fitted(r) and clips_fitted(r) == 2, r.text()
    r = check(rail(shift=0))  # the stop in a clip: that grip is not a fit
    assert clips_fitted(r) == 1, r.text()


def test_a_leg_in_a_clip_tile():
    r = check(leg())
    assert all_fitted(r) and clips_fitted(r) == 1, r.text()
    r = check(leg(drop=-60))  # pulled 60 up: its lower end above the clip, out of it
    assert r.problems and clips_fitted(r) == 0, r.text()


def test_an_aerial_on_a_lever_and_in_an_open_stud():
    r = check(aerial())
    assert not r.problems, r.text()
    # the bar in the open stud is tested for fit; the lever is a hinge, known by name only
    assert any("as a bar in an open stud" in i.text for i in r.fits), r.text()
    assert any("hinge" in i.text for i in r.unchecked), r.text()


# ---- the builder's clip and strut tools (guide mode) ------------------------------------------


@pytest.fixture
def work(tmp_path):
    import json

    (tmp_path / "config.json").write_text(json.dumps({"mode": "tools", "guide": True}))
    return tmp_path


def use(work, name: str, args: dict) -> str:
    from bricksnap.lab import tools

    handler = {"clip": tools._clip_tool, "strut": tools._strut_tool}[name]
    return "\n".join(b["text"] for b in handler(work, args))


def model(work) -> str:
    return (work / "model.ldr").read_text()


def test_the_clip_and_strut_tools_are_offered_with_the_guide_only(work, tmp_path):
    import json

    from bricksnap.lab import tools

    names = [t["name"] for t in tools.tools_for(work)]
    assert "clip" in names and "strut" in names
    off = tmp_path / "off"
    off.mkdir()
    (off / "config.json").write_text(json.dumps({"mode": "tools"}))
    assert tools.tools_for(off) == tools.TOOLS


def test_the_clip_tool_puts_a_clip_plate_on_a_handle(work):
    (work / "model.ldr").write_text(BASE + HANDLE)
    said = use(work, "clip", {"part": "60897", "colour": 15, "onto": 2})
    assert said.startswith("Added line 3: 60897.dat clipped on the bar of line 2"), said
    assert "The checker: lines 2 and 3: tested for fit." in said
    r = check(model(work))
    assert clips_fitted(r) == 1 and not r.problems, r.text()


@pytest.mark.parametrize("angle", [0, 30, 45, 90])
def test_the_clip_tool_puts_11090_on_a_handle_at_an_angle(work, angle):
    (work / "model.ldr").write_text(BASE + HANDLE)
    said = use(work, "clip", {"part": "11090", "colour": 15, "onto": 2, "angle": angle})
    assert "lines 2 and 3: tested for fit" in said and "Its bore opens at" in said, said
    assert "a bar in it 3.5 to 10 LDU deep" in said
    r = check(model(work))
    assert clips_fitted(r) == 1 and all_fitted(r), r.text()


def test_the_clip_tool_refuses_in_plain_words(work):
    (work / "model.ldr").write_text(BASE + HANDLE)
    said = use(work, "clip", {"part": "4085c", "colour": 15, "onto": 2})
    assert said.startswith("ERROR:") and "Clips it measures: 60897" in said, said
    assert "4085a" not in said
    said = use(work, "clip", {"part": "60897", "colour": 15, "onto": 1})
    assert said.startswith("ERROR:") and "has no bar or handle the checker can find" in said
    said = use(work, "clip", {"part": "60897", "colour": 15, "onto": 2, "which": 3})
    assert said.startswith("ERROR:") and "which is 1 to 1" in said
    for bad in (
        {"which": 0},
        {"onto": 0},
        {"colour": -1},
        {"angle": float("nan")},
        {"angle": float("inf")},
        {"angle": "up"},
        {"slide": float("nan")},
    ):
        said = use(work, "clip", {"part": "60897", "colour": 15, "onto": 2, **bad})
        assert said.startswith("ERROR:") and "Traceback" not in said, (bad, said)
    assert model(work) == BASE + HANDLE  # nothing was added


def test_the_clip_tool_reports_a_clash_as_the_checker_finds_it(work):
    (work / "model.ldr").write_text(BASE + HANDLE)
    use(work, "clip", {"part": "60897", "colour": 15, "onto": 2})
    said = use(work, "clip", {"part": "60897", "colour": 15, "onto": 2})  # the same spot again
    assert "But it finds a problem with the new line" in said and "PROBLEM:" in said, said
    (work / "model.ldr").write_text(BASE + HANDLE)
    said = use(work, "clip", {"part": "15712", "colour": 15, "onto": 2, "slide": 500})
    assert said.startswith("Added line 3: 15712.dat") and "slide went past the bar's end" in said


def test_the_strut_tool_builds_the_strut_built_by_hand(work):
    hand = strut_on_11090()
    handles = "\n".join(hand.splitlines()[:6]) + "\n"  # the plate, the handles and the bricks
    (work / "model.ldr").write_text(handles)
    said = use(work, "strut", {"onto": [2, 6], "colour": 15})
    assert "a Bar 4L between them" in said and "63.2 LDU apart" in said, said
    made = model(work).splitlines()[6:]
    for a, b in zip(made, hand.splitlines()[6:], strict=True):
        # the same parts in the same places (a tube may be turned half round its own clip's
        # line, which is the same joint); the bar exactly the same
        x = np.array([float(v) for v in a.split()[2:14]])
        y = np.array([float(v) for v in b.split()[2:14]])
        assert a.split()[-1] == b.split()[-1] and np.allclose(x[:3], y[:3], atol=0.01), (a, b)
    assert made[-1].split()[2:] == hand.splitlines()[-1].split()[2:] or np.allclose(
        [float(v) for v in made[-1].split()[2:14]],
        [float(v) for v in hand.splitlines()[-1].split()[2:14]],
        atol=0.01,
    )
    r = check(model(work))
    assert clips_fitted(r) == 2 and tubes_fitted(r) == 2 and not r.problems, r.text()


def test_the_clip_tool_finds_the_handle_of_a_bar_tube(work):
    # 23443's handle has no primitive: the tool finds it in the part's shape, as the checker
    (work / "model.ldr").write_text("1 7 0 -6 0 1 0 0 0 1 0 0 0 1 23443.dat\n")
    said = use(work, "clip", {"part": "60897", "colour": 15, "onto": 1, "angle": 90})
    assert "lines 1 and 2: tested for fit" in said, said


def two_handles(apart: float, side: float = 0.0) -> str:
    """Two 2540 handles on 2 x 4 bricks facing each other, their bars ``apart`` LDU across and
    the second ``side`` LDU along its bar (the review's cases)."""
    tz = -30 - apart - 30
    return (
        "1 7 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 14 0 -32 -10 1 0 0 0 1 0 0 0 1 2540.dat\n"
        f"1 7 {side} -24 {tz} 1 0 0 0 1 0 0 0 1 3001.dat\n"
        f"1 14 {side} -32 {tz + 10} -1 0 0 0 1 0 0 0 -1 2540.dat\n"
    )


def follow(work, said: str, line_no: int) -> None:
    """Move line ``line_no`` (and the brick under it, the line before) as the advice says."""
    m = re.search(r"Move line (\d+) by \(([-0-9. ]+)\)", said)
    assert m and int(m.group(1)) == line_no, said
    move = np.array([float(v) for v in m.group(2).split()])
    lines = model(work).splitlines()
    for n in (line_no - 1, line_no):
        t = lines[n - 1].split()
        t[2:5] = [f"{float(v) + d:g}" for v, d in zip(t[2:5], move, strict=True)]
        lines[n - 1] = " ".join(t)
    (work / "model.ldr").write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize(
    "apart, side",
    [(20, 0), (40, 0), (114, 0), (134, 0), (100, 20), (100, 40)],
)
def test_the_strut_tool_refuses_and_its_advice_closes_the_strut(work, apart, side):
    # bars 20 apart (the tubes would cross), 40 apart, bores 54 or 74 apart (in by 3, which
    # the checker does not count), one handle 20 or 40 along its bar: nothing is added, and
    # moving the second handle as the advice says lets strut build a fitted strut
    text = two_handles(apart, side)
    (work / "model.ldr").write_text(text)
    said = use(work, "strut", {"onto": [2, 4], "colour": 4})
    assert said.startswith("ERROR:") and model(work) == text, said
    follow(work, said, 4)
    said = use(work, "strut", {"onto": [2, 4], "colour": 4})
    assert said.startswith("Added lines 5 and 6"), said
    r = check(model(work))
    assert clips_fitted(r) == 2 and tubes_fitted(r) == 2, r.text()


def test_the_strut_tool_refuses_bars_that_are_not_parallel(work):
    text = two_handles(100).replace(
        "-1 0 0 0 1 0 0 0 -1 2540.dat", "-0.9397 0 -0.342 0 1 0 0.342 0 -0.9397 2540.dat"
    )  # the second handle turned 20 degrees
    (work / "model.ldr").write_text(text)
    said = use(work, "strut", {"onto": [2, 4], "colour": 4})
    assert said.startswith("ERROR:") and "20 degrees apart" in said and model(work) == text


def test_the_strut_tool_refuses_a_bar_past_the_bores_stop(work):
    # bars 90 apart: bores 30 apart, a Bar 3L would be 15 into each, past the stop at 10
    (work / "model.ldr").write_text(two_handles(90))
    said = use(work, "strut", {"onto": [2, 4], "colour": 4})
    assert said.startswith("ERROR:") and "30.0 LDU apart" in said, said


@pytest.mark.parametrize("apart, bar", [(100, "Bar 3L"), (113, "Bar 3L"), (120, "Bar 4L")])
def test_the_strut_tools_range_is_the_checkers(work, apart, bar):
    # bores 40, 53 and 60 apart: a bar in each by 10, 3.5 and 10 (BORE_IN), each fitted
    (work / "model.ldr").write_text(two_handles(apart))
    said = use(work, "strut", {"onto": [2, 4], "colour": 4})
    assert f"a {bar} between them" in said, said
    r = check(model(work))
    assert tubes_fitted(r) == 2 and not r.problems, r.text()


# ---- what a clip may carry -----------------------------------------------------------------

TABLE = """1 7 -10 -60 -50 1 0 0 0 1 0 0 0 1 87994.dat
1 14 -10 -34 -30 1 0 0 0 1 0 0 0 1 60897.dat
1 7 -10 -60 50 1 0 0 0 1 0 0 0 1 87994.dat
1 14 -10 -34 30 -1 0 0 0 1 0 0 0 -1 60897.dat
1 7 10 -60 -50 1 0 0 0 1 0 0 0 1 87994.dat
1 14 10 -34 -30 1 0 0 0 1 0 0 0 1 60897.dat
1 7 10 -60 50 1 0 0 0 1 0 0 0 1 87994.dat
1 14 10 -34 30 -1 0 0 0 1 0 0 0 -1 60897.dat
1 1 0 -42 0 0 0 1 0 1 0 -1 0 0 3020.dat
"""  # the review's table: a 2 x 4 plate on four clip plates, each on a bar leg


def table(bricks: int) -> str:
    return TABLE + "".join(
        f"1 4 0 {-66 - 24 * k} 0 0 0 1 0 1 0 -1 0 0 3001.dat\n" for k in range(bricks)
    )


WING = """1 7 0 -24 0 1 0 0 0 1 0 0 0 1 3003.dat
1 7 0 -48 0 1 0 0 0 1 0 0 0 1 3003.dat
1 7 0 -72 0 1 0 0 0 1 0 0 0 1 3003.dat
1 14 0 -80 -10 1 0 0 0 1 0 0 0 1 2540.dat
1 4 0 -79.5 -50 -1 0 0 0 1 0 0 0 -1 61252.dat
"""  # the review's wing: a 61252 on a handle, out from a stack of bricks


def loads(report) -> list[list[int]]:
    return [i.lines for i in report.warnings if i.kind == "held by clips"]


def test_a_table_on_clip_held_legs_is_told_a_clip_holds_no_load():
    # twelve 2 x 4 bricks on four clips: 236,800 LDU^3 each, more than LOAD_PER_GRIP (one
    # 2 x 4 brick, 76,800); three bricks (64,000 each) and the plate alone are not told
    r = check(table(12))
    assert len(loads(r)) == 1 and "17 only by clips, carrying more than a strut" in r.summary()
    assert "the checker cannot judge whether clips will carry this much" in r.text()
    assert not loads(check(table(3))) and not loads(check(table(0)))


def test_a_wing_held_out_on_one_clip_is_told_and_a_mirror_is_not():
    # a 1 x 8 plate 110 LDU out from one clip: 25,600 LDU^3 times 110, more than LOAD_ONE_GRIP;
    # a 1 x 1 plate on the clip plate itself is a mirror, a detail
    r = check(WING + "1 1 0 -87.5 -120 0 0 1 0 1 0 -1 0 0 3460.dat\n")
    assert loads(r) == [[5, 6]], r.text()
    r = check(WING + "1 1 0 -87.5 -50 1 0 0 0 1 0 0 0 1 3024.dat\n")
    assert not loads(r), r.text()


def test_struts_rails_blades_and_legs_on_clips_are_not_told():
    for model in (strut_on_23443(), strut_on_11090(), blade_strut(), rail(), leg()):
        assert not loads(check(model)), check(model).text()
