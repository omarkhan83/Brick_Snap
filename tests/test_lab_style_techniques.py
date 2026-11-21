"""Every technique the builder's style guide teaches (bricksnap/lab/style.md), built the way the
builder builds it, and what the checker (bricksnap/lab/validate.py) says about it.

For each technique: one small construction on a base plate, put together through the code
behind the ``place`` tool (bricksnap/lab/place.py) wherever ``place`` can do it, and by a raw
LDraw line (what the ``add`` tool takes) only where it cannot; each raw line says why. Each
construction must pass the check with no problems and every part held, and a plainly wrong
version of it (half a stud off, a plate too high, pushed into its neighbour) must be caught.

Where the checker or ``place`` gets one wrong, the test stays, marked ``xfail(strict=True)``
with the checker's own words, so that the day it is fixed the mark has to come off.

Left out on purpose: thin members joined by a clip on a bar or a bar in a hole (clips, bars,
bar tubes, handles, struts, rails, aerials), which are tested elsewhere.

Geometry comes from the parts' own data (``part_info``'s studs and sockets); where how two
parts go together is not in their studs, it comes from the library's own assembled shortcut
(3937c01: hinge base and top at the same place). They need the LDraw parts library and skip
without it. No AI session is started.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from bricksnap.lab import ldraw_lib
from bricksnap.lab.modules import place_module
from bricksnap.lab.place import PlaceError, ldraw_line, place, sockets
from bricksnap.lab.validate import Report, check, numbered_studs

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)

HELD = "no problems: every part is held"


# ---- building the way the builder does ---------------------------------------------------------


def ground(part: str, colour: int = 71, x: float = 0, z: float = 0, turn: int = 0) -> str:
    """The ``place`` tool with line 0: a part standing on the ground."""
    return place("", part, colour, 0, x=x, z=z, turn=turn).line


def on(text: str, part: str, colour: int, line: int, **where) -> str:  # type: ignore[no-untyped-def]
    """The ``place`` tool: the model with one more part, attached by connection."""
    return text + "\n" + place(text, part, colour, line, **where).line


def raw(text: str, new: str) -> str:
    """The ``add`` tool: a line the builder writes by hand."""
    return text + "\n" + new


def moved(text: str, n: int, dx: float = 0, dy: float = 0, dz: float = 0) -> str:
    """The model with line n moved (the wrong versions)."""
    lines = text.splitlines()
    t = lines[n - 1].split()
    for k, d in ((2, dx), (3, dy), (4, dz)):
        t[k] = ldraw_lib.fmt(round(float(t[k]) + d, 3))
    lines[n - 1] = " ".join(t)
    return "\n".join(lines)


def last(text: str) -> int:
    return len(text.splitlines())


def turned_about_y(degrees: float) -> np.ndarray:
    """A turn about the vertical, clockwise seen from above (as ``place``'s quarter turns)."""
    a = math.radians(degrees)
    return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])


def stud_world(text: str, line: int, stud: int) -> np.ndarray:
    """Where stud k of a line's part is in the model (its base)."""
    t = text.splitlines()[line - 1].split()
    pos = np.array([float(v) for v in t[2:5]])
    m = np.array([float(v) for v in t[5:14]]).reshape(3, 3)
    part = ldraw_lib.library().part(t[14])
    return m @ numbered_studs(part)[stud - 1].pos + pos


BASE = "3036.dat"  # Plate 6 x 8: studs x -70..70 by z -50..50, numbered row by row from the front


def b(x: float, z: float) -> int:
    """The number of the base plate's stud at (x, z)."""
    return int((x + 70) / 20) + 1 + 8 * int((z + 50) / 20)


def base() -> str:
    return ground(BASE)


@dataclass
class Case:
    right: str
    wrong: dict[str, str] = field(default_factory=dict)  # what is wrong -> the model
    how: str = "place only"  # or which lines are raw, and why


def held(r: Report) -> bool:
    return not r.problems and HELD in r.summary()


def said(r: Report) -> str:
    return r.text(connections=False)


# ---- (b) 1: caps on upward studs -----------------------------------------------------------------

TILES = ["3070b", "3069b", "63864", "2431", "6636", "4162", "3068b", "87079"]
CURVED = ["11477", "15068", "50950", "61678", "93273", "88930", "93606"]


def cap(part: str) -> Case:
    t = on(base(), part + ".dat", 15, 1, stud=b(-70, -50))
    return Case(t, {"half a stud off": moved(t, 2, dx=10), "a plate too high": moved(t, 2, dy=-8)})


# ---- (b) 3: skins on side studs ------------------------------------------------------------------


def skin_on(carrier: str, studs: list[int], skin: str, finish: str, finish_turn: int = 0) -> Case:
    """A carrier on the base's front row, a plate pressed onto its side studs (the flank built
    flat, turned and pressed on), and a tile or curved slope on that plate's studs."""
    t = on(base(), carrier, 4, 1, stud=b(-30, -50))
    t = on(t, skin, 15, 2, stud=studs[0])
    t = on(t, finish, 72, 3, stud=1, turn=finish_turn)
    return Case(t, {"skin pushed into the carrier": moved(t, 3, dz=4)})


def skin_on_two(carrier: str, skin: str, finish: str) -> Case:
    """Two carriers with one side stud each, side by side; one skin held by both."""
    t = on(base(), carrier, 4, 1, stud=b(-30, -50))
    t = on(t, carrier, 4, 1, stud=b(-10, -50))
    t = on(t, skin, 15, 2, stud=2)
    t = on(t, finish, 72, 4, stud=1)
    return Case(t, {"skin half a stud off": moved(t, 4, dx=10)})


def bracket_skin(bracket: str, carry: str, skin: str, finish: str, pair: bool = False) -> Case:
    """A bracket on a brick at the base's front edge (a flange that hangs down must clear the
    base), a plate on the bracket's side studs, a tile on the plate."""
    t = on(base(), carry, 4, 1, stud=b(-30, -50))
    t = on(t, bracket, 14, 2, stud=1)
    br = [3]
    if pair:
        t = on(t, carry, 4, 1, stud=b(-10, -50))
        t = on(t, bracket, 14, last(t), stud=1)
        br.append(last(t))
    side = next(k for k, s in enumerate(numbered_studs(_part(bracket)), 1) if s.axis[1] > -0.5)
    t = on(t, skin, 15, br[0], stud=side)
    sk = last(t)
    t = on(t, finish, 72, sk, stud=1)
    return Case(t, {"skin pushed into the bracket": moved(t, sk, dz=4)})


def _part(name: str) -> ldraw_lib.Part:
    return ldraw_lib.library().part(name)


def two_carriers() -> Case:
    """One 1 x 3 skin across a 1 x 2 brick with two side studs and a 1 x 1 brick with one."""
    t = on(base(), "11211.dat", 4, 1, stud=b(-70, -50))  # x -80..-40
    t = on(t, "87087.dat", 4, 1, stud=b(-30, -50))  # x -40..-20
    t = on(t, "3623.dat", 15, 2, stud=3)  # 1 x 3 plate on the side studs of both
    t = on(t, "63864.dat", 72, 4, stud=1)  # 1 x 3 tile
    return Case(t, {"skin half a stud off": moved(t, 4, dx=10)})


def aircraft_body() -> Case:
    """A 2-stud core of two 1 x 4 side-stud bricks back to back, a 1 x 4 plate pressed on each
    side with a 1 x 4 tile on it, two curved slopes 2 x 2 on top."""
    t = on(base(), "30414.dat", 72, 1, stud=b(-50, -10))  # studs face -z
    t = on(t, "30414.dat", 72, 1, stud=b(10, 10), turn=2)  # studs face +z
    t = on(t, "3710.dat", 15, 2, stud=5)  # skin on the front
    t = on(t, "2431.dat", 15, 4, stud=1)
    # the back brick is turned 2: on its side studs turn 0 lays the plate the other way along
    # x, so that it would catch one stud only; turn 2 lines it up with the brick
    t = on(t, "3710.dat", 15, 3, stud=5, turn=2)  # skin on the back
    t = on(t, "2431.dat", 15, 6, stud=1, turn=2)
    t = on(t, "15068.dat", 15, 2, stud=1)  # curved top
    t = on(t, "15068.dat", 15, 2, stud=3)
    return Case(t, {"skin pushed into the core": moved(t, 4, dz=4)})


# ---- (b) 4: rounded underside --------------------------------------------------------------------


def inverted(part: str, socket: int, turn: int = 0) -> Case:
    """A body plate on a pillar two bricks tall, overhanging; the inverted curved slope hangs
    under the overhang by its own studs (``place`` under a socket)."""
    t = on(base(), "3003.dat", 72, 1, stud=b(-70, -50))
    t = on(t, "3003.dat", 72, 2, stud=1)
    t = on(t, "3034.dat", 15, 3, stud=1)  # 2 x 8 plate, x -80..80, z -60..-20
    t = on(t, part + ".dat", 15, 4, under_socket=socket, turn=turn)
    return Case(t, {"half a stud off": moved(t, 5, dx=10)})


# ---- (b) 5: taper in plan ------------------------------------------------------------------------

WEDGES = [  # (right, left): the right one goes on the left so the cuts face out
    ("24307", "24299"),
    ("43722b", "43723b"),
    ("41769b", "41770b"),
    ("65426", "65429"),
]


def _first_socket_at(part: str, x: float, z: float) -> int:
    for k, s in enumerate(sockets(_part(part)), 1):
        if abs(s.pos[0] - x) < 1.5 and abs(s.pos[2] - z) < 1.5:
            return k
    raise AssertionError(f"{part} has no socket near ({x}, {z})")


def wedge_pair(right: str, left: str, stacked: bool) -> Case:
    """A right and a left wedge plate side by side on the base, their straight edges meeting
    at x = 0 (each on its own studs); stacked: a 2 x 4 plate over the seam on top of both."""
    r, lf = right + ".dat", left + ".dat"
    rz = max(s.pos[2] for s in sockets(_part(r)) if s.kind == "grid")
    lz = max(s.pos[2] for s in sockets(_part(lf)) if s.kind == "grid")
    # each wedge's back socket on its straight-edge column, on the base's row z = 30
    t = on(base(), r, 4, 1, stud=b(-10, 30), socket=_first_socket_at(r, 10, rz))
    t = on(t, lf, 4, 1, stud=b(10, 30), socket=_first_socket_at(lf, -10, lz))
    wrong = {"pushed into its neighbour": moved(t, 3, dx=-4)}
    if stacked:
        # 2 x 4 plate turned 1 (long along z), its first socket on the right wedge's last
        # stud: it lies over both wedges' stud columns (x -10 and 10)
        rs = len(numbered_studs(_part(r)))
        t = on(t, "3020.dat", 15, 2, stud=rs, turn=1)
        wrong = {"the plate over the seam half a stud off": moved(t, 4, dz=10)}
    return Case(t, wrong)


# ---- (b) 6: a sweep ------------------------------------------------------------------------------


def sweep() -> Case:
    """A 2 x 6 plate carrying a triangular tile and an angled tile, ending against a wedge plate."""
    t = on(base(), "3795.dat", 4, 1, stud=b(-70, -10))  # 2 x 6 plate, x -80..40, z -20..20
    t = on(t, "35787.dat", 15, 2, stud=1)  # triangular 2 x 2 at its left end
    t = on(t, "22385.dat", 15, 2, stud=3, turn=1)  # angled 3 x 2 along x
    t = on(t, "41770b.dat", 15, 1, stud=b(50, -10), turn=1)  # the wedge plate beyond its end
    return Case(t, {"tile half a stud off": moved(t, 3, dx=10)})


# ---- (b) 8: a tile or plate seen on edge, held by a side stud ------------------------------------


def on_edge(part: str) -> Case:
    """A 1 x 1 brick with a side stud; a 1 x 4 plate or tile on that stud by its end socket,
    turned so its length stands up: a thin fin 8 LDU thick."""
    t = on(base(), "87087.dat", 4, 1, stud=b(-10, -50))
    up = down = ""
    for turn in range(4):
        got = place(t, part, 15, 2, stud=2, socket=1, turn=turn)
        if got.m @ np.array([1.0, 0, 0]) @ np.array([0, -1.0, 0]) > 0.99:
            up, down = got.line, place(t, part, 15, 2, stud=2, socket=1, turn=(turn + 2) % 4).line
    assert up and down
    return Case(
        raw(t, up),
        {"turned down into the base": raw(t, down)},
        how="place (the turn that stands it up found by trying the four)",
    )


# ---- (b) 10: glass -------------------------------------------------------------------------------


def screen(part: str, over: str) -> Case:
    """A moulded windscreen on the base's studs, a plate over the studs it has."""
    t = on(base(), part + ".dat", 47, 1, stud=b(-30, -50))
    t = on(t, over, 72, 2, stud=1)
    return Case(t, {"half a stud off": moved(t, 2, dx=10)})


def panel(part: str, over: str) -> Case:
    t = on(base(), part + ".dat", 47, 1, stud=b(-30, -10))
    t = on(t, over, 72, 2, stud=1)
    return Case(t, {"half a stud off": moved(t, 2, dx=10)})


def hinged_panel() -> Case:
    """Hinge 1 x 2 base (3937) on the base; its top (3938) at the same place, as the library's
    assembled 3937c01 draws the closed hinge (raw: ``place`` cannot join a hinge, and 3938 has
    no socket); a clear panel 1 x 2 x 2 on the top's studs."""
    t = on(base(), "3937.dat", 72, 1, stud=b(-10, -10))
    top = t.splitlines()[1].split()
    top[1], top[-1] = "72", "3938.dat"
    t = raw(t, " ".join(top))
    t = on(t, "87552.dat", 47, 3, stud=1)
    return Case(
        t,
        {
            "the top and its panel a plate too high": moved(moved(t, 3, dy=-8), 4, dy=-8),
            "the top half a stud along its pin": moved(moved(t, 3, dx=10), 4, dx=10),
            "the panel half a stud off": moved(t, 4, dx=10),
        },
        how="raw line for 3938 (a hinge: no socket; same place as 3937, from 3937c01)",
    )


# ---- (b) 11: small detail parts on studs and side studs ------------------------------------------

DETAILS = ["98138", "6141", "85861", "54200", "2412b", "4589", "4740", "25269", "24246"]


# a radar dish takes one stud, in the tube at its centre: its real shape stands on studs at the
# corners of its cell (1.2 LDU deep) and its rim on the studs round a single one, although
# ``place.sockets`` lists three corners as sockets. An official set (21036) puts it on the
# centre stud of a 2 x 2 jumper plate, as here.
CENTRE_ONLY = {"4740": 4}


def detail_on_top(part: str) -> Case:
    if part in CENTRE_ONLY:
        t = on(base(), "87580.dat", 72, 1, stud=b(-10, -10))
        t = on(t, part + ".dat", 25, 2, stud=1, socket=CENTRE_ONLY[part])
        four = on(base(), part + ".dat", 25, 1, stud=b(-10, -10))  # socket 1, as place offers
        return Case(t, {"half a stud off": moved(t, 3, dx=10), "on four studs": four})
    t = on(base(), part + ".dat", 25, 1, stud=b(-10, -10))
    return Case(t, {"half a stud off": moved(t, 2, dx=10)})


SIDE_CARRIER = {1: ("87087.dat", 2), 2: ("11211.dat", 3), 4: ("22885.dat", 3)}


def detail_on_side(part: str) -> Case:
    grid = [s for s in sockets(_part(part + ".dat")) if s.kind == "grid"]
    n = 1 if len(grid) == 1 or part in CENTRE_ONLY else 2 if len(grid) == 2 else 4
    carrier, stud = SIDE_CARRIER[n]
    t = on(base(), carrier, 4, 1, stud=b(-10, -50))
    t = on(t, part + ".dat", 25, 2, stud=stud, socket=CENTRE_ONLY.get(part, 1))
    return Case(t, {"pushed into the carrier": moved(t, 3, dz=4)})


# ---- (b) 13: a part turned on one stud -----------------------------------------------------------


def turned_on_one_stud(part: str, jumper: str, degrees: float) -> str:
    """A jumper on the base, a 1 x 1 brick at its front right; a 1 x 2 plate or tile on the
    jumper's one stud by its end socket, turned ``degrees`` about that stud (raw: ``place``
    takes quarter turns only)."""
    t = on(base(), jumper, 72, 1, stud=b(-10, 10))  # x -20..20, z 0..20, its stud at (0, 10)
    t = on(t, "3005.dat", 4, 1, stud=b(10, -10))  # 1 x 1 brick, x 0..20, z -20..0
    base_w = stud_world(t, 2, 1)
    m = turned_about_y(degrees)
    sock = sockets(_part(part))[0].pos
    return raw(t, ldraw_line(15, base_w - m @ sock, m, part))


# ---- (b) 13 and (a): half-stud offsets with jumper plates ----------------------------------------


def jumper(jump: str, part: str, socket: int) -> Case:
    t = on(base(), jump, 72, 1, stud=b(-10, -10))
    t = on(t, part, 15, 2, stud=1, socket=socket)
    return Case(t, {"back on the base's grid": moved(t, 3, dx=10)})


# ---- (c) car: a wheel arch over a wheel from the proven modules ----------------------------------


def car(arch: str) -> tuple[str, int]:
    """Two large-wheel modules on the ground 6 studs apart, a 2 x 8 chassis plate along z on
    them, the arch on the chassis's studs over the front right wheel. Returns the model and
    the arch's line."""
    t = "\n".join(place_module("", "wheels-large", 71, 0, x=0, z=-60, joint_name="front").lines)
    back = place_module(t, "wheels-large", 71, 0, x=0, z=60, joint_name="back")
    t += "\n" + "\n".join(back.lines)
    # 2 x 8 along z, from z -80 to 80: its socket at its own (70, -10) on the front plate's stud
    sock = _first_socket_at("3034.dat", 70, -10)
    t = on(t, "3034.dat", 72, 1, stud=1, turn=1, socket=sock)
    chassis = last(t)
    # the arch's inner row on the chassis's right column (x 10), centred on the front wheel
    target = next(
        k for k in range(1, 17) if np.allclose(stud_world(t, chassis, k)[[0, 2]], [10, -70])
    )
    t = on(t, arch + ".dat", 4, chassis, stud=target, turn=3)
    return t, last(t)


def car_case(arch: str) -> Case:
    t, a = car(arch)
    return Case(t, {"the arch a plate lower, into the tyre": moved(t, a, dy=8)})


# ---- (c) creature, building, object, aircraft tail -----------------------------------------------


def eye() -> Case:
    """A black round tile on a white round plate on a brick: a pupil with a white ring."""
    t = on(base(), "3005.dat", 4, 1, stud=b(-10, -10))
    t = on(t, "6141.dat", 15, 2, stud=1)
    t = on(t, "98138.dat", 0, 3, stud=1)
    return Case(t, {"the pupil a plate too high": moved(t, 4, dy=-8)})


def claw(part: str) -> Case:
    t = on(base(), "3005.dat", 4, 1, stud=b(-10, -50))  # front row: the tooth points out
    t = on(t, part + ".dat", 15, 2, stud=1, turn=0)
    return Case(t, {"half a stud off": moved(t, 3, dx=10)})


def masonry_wall() -> Case:
    """Two courses of a wall one stud thick: 1 x 2 bricks and masonry bricks, joints staggered."""
    t = on(base(), "3004.dat", 71, 1, stud=b(-70, -10))
    t = on(t, "98283.dat", 71, 1, stud=b(-30, -10))
    t = on(t, "3004.dat", 71, 1, stud=b(10, -10))
    t = on(t, "98283.dat", 71, 2, stud=2)  # over the first joint
    t = on(t, "98283.dat", 71, 3, stud=2)  # over the second
    return Case(t, {"a masonry brick half a stud off": moved(t, 5, dx=10)})


def edge_line() -> Case:
    """Door-rail plates on the base's front row, their rail standing past the edge: a hairline
    between the base and the tiles above."""
    t = on(base(), "4510.dat", 72, 1, stud=b(-70, -50))
    t = on(t, "32028.dat", 72, 2, stud=1)
    t = on(t, "3069b.dat", 15, 3, stud=1)
    return Case(t, {"the rail plate half a stud off": moved(t, 3, dx=10)})


def tail(part: str) -> Case:
    """The long curved tail part along x on a 4 x 10 plate, its raised back end on a 2 x 2 brick
    (sockets 11 to 14 are 3 plates above the front ones)."""
    t = ground("3030.dat")
    t = on(t, "3003.dat", 72, 1, stud=9)  # x 60..100, z -40..0
    t = on(t, part + ".dat", 15, 1, stud=11, turn=1)
    return Case(t, {"a plate too high": moved(t, 3, dy=-8)})


# ---- the table of constructions ------------------------------------------------------------------

CASES: dict[str, Callable[[], Case]] = {}
for _p in TILES + CURVED:
    CASES[f"cap {_p}"] = lambda p=_p: cap(p)
CASES["skin 11211"] = lambda: skin_on("11211.dat", [3, 4], "3023b.dat", "3069b.dat")
CASES["skin 11211 curved"] = lambda: skin_on("11211.dat", [3, 4], "3023b.dat", "11477.dat", 1)
CASES["skin 30414"] = lambda: skin_on("30414.dat", [5, 6, 7, 8], "3710.dat", "2431.dat")
CASES["skin 22885"] = lambda: skin_on("22885.dat", [3, 4, 5, 6], "3022.dat", "3068b.dat")
CASES["skin 87087 pair"] = lambda: skin_on_two("87087.dat", "3023b.dat", "3069b.dat")
CASES["skin 4070 pair"] = lambda: skin_on_two("4070.dat", "3023b.dat", "3069b.dat")
CASES["skin 99780"] = lambda: bracket_skin("99780.dat", "3004.dat", "3023b.dat", "3069b.dat")
CASES["skin 99781"] = lambda: bracket_skin("99781.dat", "3004.dat", "3023b.dat", "3069b.dat")
CASES["skin 99207"] = lambda: bracket_skin("99207.dat", "3004.dat", "3022.dat", "3068b.dat")
CASES["skin 44728"] = lambda: bracket_skin("44728.dat", "3004.dat", "3022.dat", "3068b.dat")
CASES["skin 36840 pair"] = lambda: bracket_skin(
    "36840.dat", "3005.dat", "3023b.dat", "3069b.dat", pair=True
)
CASES["skin 36841 pair"] = lambda: bracket_skin(
    "36841.dat", "3005.dat", "3023b.dat", "3069b.dat", pair=True
)
CASES["skin across two carriers"] = two_carriers
CASES["aircraft body 4 wide"] = aircraft_body
CASES["inverted 24201"] = lambda: inverted("24201", 5)
CASES["inverted 32803"] = lambda: inverted("32803", 5)
CASES["inverted 13547"] = lambda: inverted("13547", 3, turn=1)  # x -40..40, studs 1 and 2 in
for _r, _l in WEDGES:
    CASES[f"wedges {_r}/{_l}"] = lambda r=_r, lf=_l: wedge_pair(r, lf, False)
    CASES[f"wedges {_r}/{_l} stacked"] = lambda r=_r, lf=_l: wedge_pair(r, lf, True)
CASES["sweep 35787 22385"] = sweep
CASES["on edge plate 3710"] = lambda: on_edge("3710.dat")
CASES["on edge tile 2431"] = lambda: on_edge("2431.dat")
CASES["screen 57783"] = lambda: screen("57783", "3710.dat")
CASES["screen 30841"] = lambda: screen("30841", "3023b.dat")
CASES["screen 18973"] = lambda: screen("18973", "3023b.dat")
CASES["panel 60581"] = lambda: panel("60581", "3710.dat")
CASES["panel 87552"] = lambda: panel("87552", "3023b.dat")
CASES["hinge 3937 3938 panel"] = hinged_panel
for _p in DETAILS:
    CASES[f"detail {_p} on top"] = lambda p=_p: detail_on_top(p)
    CASES[f"detail {_p} on a side stud"] = lambda p=_p: detail_on_side(p)
CASES["jumper 15573 half stud"] = lambda: jumper("15573.dat", "3023b.dat", 1)
CASES["jumper 87580 tile centred"] = lambda: jumper("87580.dat", "3068b.dat", 5)
CASES["jumper 87580 half stud"] = lambda: jumper("87580.dat", "3023b.dat", 1)
for _a in ("18974", "98282", "50745"):
    CASES[f"car arch {_a}"] = lambda a=_a: car_case(a)
CASES["creature eye"] = eye
CASES["creature claw 15070"] = lambda: claw("15070")
CASES["creature claw 49668"] = lambda: claw("49668")
CASES["creature 85861"] = lambda: detail_on_top("85861")
CASES["building masonry"] = masonry_wall
CASES["object edge line"] = edge_line
CASES["tail 77180"] = lambda: tail("77180")
CASES["tail 77182"] = lambda: tail("77182")

# where the checker is wrong today: case -> the checker's words (see the module's notes)
FALSE_RESULT: dict[str, str] = {}
WRONG_PASSES: dict[tuple[str, str], str] = {
    ("hinge 3937 3938 panel", "the top and its panel a plate too high"): (
        "4 parts of 4 kinds, no problems: every part is held (2 of them only by joints the "
        "checker cannot confirm), nothing overlaps, and it stands. [A hinge known by name joins "
        "any two hinge parts that touch, wherever they are: lifted up to 16 LDU or moved 16 "
        "LDU across the pin, the top is still 'held'.]"
    ),
}


def _right_params() -> list:  # type: ignore[type-arg]
    return [
        pytest.param(k, marks=pytest.mark.xfail(strict=True, reason=FALSE_RESULT[k]))
        if k in FALSE_RESULT
        else k
        for k in CASES
    ]


def _wrong_params() -> list:  # type: ignore[type-arg]
    out = []
    for k in CASES:
        for what in _WRONGS.get(k, ["*"]):
            key = (k, what)
            out.append(
                pytest.param(
                    k, what, marks=pytest.mark.xfail(strict=True, reason=WRONG_PASSES[key])
                )
                if key in WRONG_PASSES
                else pytest.param(k, what)
            )
    return out


_WRONGS: dict[str, list[str]] = {  # cases whose wrong versions are tested one by one
    "hinge 3937 3938 panel": [
        "the top and its panel a plate too high",
        "the top half a stud along its pin",
        "the panel half a stud off",
    ],
}


@pytest.mark.parametrize("name", _right_params())
def test_the_technique_built_right_passes(name):
    case = CASES[name]()
    r = check(case.right)
    assert held(r), said(r)


@pytest.mark.parametrize("name, what", _wrong_params())
def test_the_technique_built_wrong_is_caught(name, what):
    case = CASES[name]()
    wrongs = case.wrong if what == "*" else {what: case.wrong[what]}
    for w, text in wrongs.items():
        r = check(text)
        assert r.problems, (w, said(r))


# ---- what the table above cannot say in one sentence ---------------------------------------------


@pytest.mark.parametrize("turn", range(4))
@pytest.mark.parametrize("part", [p for pair in WEDGES for p in pair] + ["35787", "22385"])
def test_a_wedge_plate_on_a_full_plate_with_studs_beside_its_cut(part, turn):
    # every cell under the part has a stud, so a stud stands beside each cut edge; it holds
    # nothing there and hits nothing (once "no socket": 41770b, on the real shapes nothing)
    r = check(on(base(), part + ".dat", 4, 1, stud=b(-10, -10), turn=turn))
    assert held(r), said(r)


def test_a_stud_into_solid_plastic_where_there_is_no_socket_is_still_caught():
    # the dish on four studs: its real shape stands on the corner studs
    r = check(detail_on_top("4740").wrong["on four studs"])
    assert any("where it has no socket" in i.text for i in r.problems), said(r)


def test_the_glass_hinge_is_a_joint_known_by_name_only():
    r = check(hinged_panel().right)
    hinge = [i for i in r.unchecked if i.kind == "joint" and i.lines == [2, 3]]
    assert len(hinge) == 1 and "a hinge joint, known by name only" in hinge[0].text, said(r)
    assert any(i.kind == "held by unchecked joints" and i.lines == [3, 4] for i in r.unchecked)


@pytest.mark.parametrize("arch", ["18974", "98282", "50745"])
def test_a_wheel_under_an_arch_still_turns(arch):
    t, _ = car(arch)
    r = check(t)
    assert len(r.movement) == 2 and r.moving_ok == 2, said(r)
    assert all("turn freely" in m for m in r.movement), r.movement


def test_place_turns_by_quarter_turns_only():
    t = on(base(), "15573.dat", 72, 1, stud=b(-10, 10))
    with pytest.raises(PlaceError, match="quarter turns"):
        half: Any = 0.5  # what a builder asking for an eighth of a turn would send
        place(t, "3023b.dat", 15, 2, stud=1, turn=half)


@pytest.mark.parametrize("part", ["3023b.dat", "3069b.dat"])
def test_a_part_turned_45_degrees_on_one_stud_is_held(part):
    r = check(turned_on_one_stud(part, "15573.dat", -45))  # away from the brick
    assert held(r), said(r)
    assert any(x.held == 4 and len(x.studs) == 1 for x in r.links), said(r)


@pytest.mark.parametrize("part", ["3023b.dat", "3069b.dat"])
@pytest.mark.parametrize("jump", ["15573.dat", "3794b.dat"])
def test_a_part_turned_45_degrees_into_its_neighbour_is_an_overlap(part, jump):
    # its far end into the 1 x 1 brick: a tile's is an overlap; a plate's stud goes into the
    # brick first, a stud problem
    r = check(turned_on_one_stud(part, jump, 45))
    assert any({3, 4} <= set(i.lines) for i in r.problems), said(r)


@pytest.mark.parametrize("part", ["53451.dat", "60849.dat"])
def test_parts_the_guide_names_that_cannot_go_on_a_stud(part):
    # a horn (claws and horns, "Creature") and a hose nozzle ("small parts") have no socket:
    # they join by a peg or a bar, which this file leaves out
    assert sockets(_part(part)) == []
    with pytest.raises(PlaceError, match="has no sockets"):
        place(base(), part, 0, 1, stud=1)


@pytest.mark.xfail(
    strict=True,
    reason="place puts Wing 2 x 4 Right with Chamfer (41769b) 1 LDU off the stud grid: "
    "Part.socket_phase takes its cells from its 39.25 LDU box (whole studs within 1 LDU) "
    "instead of its top studs, so its sockets are at x 11 and -9",
)
def test_place_puts_a_wedge_plate_on_the_stud_grid():
    t = on(base(), "41769b.dat", 4, 1, stud=b(-10, 30))
    for k in range(1, 5):
        x, _, z = stud_world(t, 2, k)
        assert (x + 10) % 20 == pytest.approx(0, abs=0.01), (k, x)


def test_every_part_the_builders_guide_names_is_in_the_library():
    # the style guide's own numbers are checked in tests/test_art_direction.py; these are the
    # numbers of the guide of how real sets are built (bricksnap/lab/guide.md)
    from bricksnap.lab import guide

    text = guide.GUIDE_FILE.read_text(encoding="utf-8")
    named = {
        n
        for group in re.findall(r"\(([^)]*)\)", text)
        for n in re.findall(r"\b(\d{3,6}[a-z]?)\b", group)
        if not re.fullmatch(r"(19|20)\d\d", n)  # a year
    }
    table = [ln for ln in text.splitlines() if ln.startswith("| ")]  # the parts by job
    named |= {n for ln in table for n in re.findall(r"\b(\d{4,6}[a-z]?)\b", ln)}
    assert {"87087", "4600", "3794b", "3937", "64179", "99780", "44728"} <= named
    lib = ldraw_lib.library()
    assert [p for p in sorted(named) if lib.resolve(p + ".dat") is None] == []
