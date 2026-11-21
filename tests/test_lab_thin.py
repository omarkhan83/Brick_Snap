"""Thin members on clips and bars: the constructions a styled model needs (struts, blades,
rails, aerials, legs), each built from library parts in a small model and checked with every
joint in it tested for fit, then broken one way and seen reported; and the limits of a clip
tested for fit on a bar or a handle, each on both sides.

The geometry is worked out here from the parts themselves (``frame``, ``grip_line``): where a
clip's grip is, where a handle's bar is, which way a bar tube's bore points.
"""

from __future__ import annotations

import math

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
