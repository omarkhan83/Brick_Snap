"""A small library of proven moving modules, and putting one into a model (research prototype).

CONTRACT (tests in tests/test_moving.py)

A module is a handful of real parts in fixed places relative to each other, split into a
fixed side and a moving side, with one joint (``joints.Joint``): what kind (WHEEL: turns
freely and the model rests on it; SPIN: turns freely; SWING: turns between two angles),
about which line, and how far. Every module is written in the frame of its ANCHOR, its
first part, which is on the fixed side and is the part that attaches to the model.

Where every number comes from (never from memory): the parts were found with the lab's own
search, and their geometry read from the LDraw library: a wheel pin's position and length
from the ``wpin2``/``wpin2a`` primitives and the plate's own triangles; a wheel's hole from
its triangles (which face is open, how deep); a hinge's axis from the cylinders its file is
drawn with; how two parts go together from the library's own assembled shortcuts where the
library has one (``4624c01``: wheel and tyre at the same place; ``6014bc01``: the tyre 6 LDU
along the wheel's -z; ``3937c01``: hinge base and top at the same place; ``3680c01`` and
``3403c01``: turntable base and top at the same place). Each module's ``official`` says it.

A module is PROVEN (``tests/test_moving.py``, where the library and LeoCAD are present)
when: its parts exist; the checker passes it on its own at rest apart from the expected
"not checked" joint; its moving side clears its fixed side over the whole stated range
(the movement check's sweep); its LDraw text opens in LeoCAD as real parts; and its
pictures at rest and at both ends of its range have been looked at by a person or agent.
The grip of the joint itself (that a wheel stays on its pin, that a hinge holds its top)
is taken from how the parts are designed to be used, not proven by geometry.

``MODULES``: name -> ``Module``. ``module_text(name, colour)``: the module alone, standing on
the ground (lowest point at y = 0), with its joint line, as a model file.
``place_module(text, name, colour, line, ...)`` -> ``ModulePlacement``: the module's lines
(its parts, then its joint line) to append to ``text``, attached by connection exactly as
``place.place`` attaches its anchor (on a stud of a line, under a socket of a line, or on the
ground at (x, z), turned in quarter turns in the model's frame); on the ground the whole
module's lowest point goes to y = 0 (the tyres, for wheels). Raises ``PlaceError``.
``verify(joint, by_line)`` -> None, or why the parts a MODULE joint names are not that module
(other files, or not in the module's places relative to its anchor, or another axis, or
more range than the module has; a turntable's joint may be written as a SWING of at most
-180 to 180 degrees, to limit it to part of a turn).
``turn`` turns the whole module the same way whichever way it is attached (an anchor that
sits turned inside its module, like the lid hinge's, is turned to match), and every
placement's note says, in the model's own directions, which way a hinge's panel is built and
which way opening moves it (or which way a wheel's or turntable's axle points).
``measure(module)`` and ``size_words(module)``: its sizes measured from its parts' real
shapes (studs across, plates tall; for wheels the tyres' diameter and how high the anchor's
top stands); the cards and the ``modules`` list quote only these. x and z must be ordinary
numbers within ``MAX_COORD``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from bricksnap.lab.joints import Joint, joint_line
from bricksnap.lab.ldraw_lib import Library, fmt, library
from bricksnap.lab.place import QUARTER, PlaceError, _clean, ldraw_line, place

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
WHEEL_ON_RIGHT = (0.0, 0.0, -1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0)
"""A wheel on a pin pointing +x: the wheel's open (inner) face, its +z, faces -x."""
WHEEL_ON_LEFT = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0)
"""A wheel on a pin pointing -x: its inner face, its +z, faces +x."""
QUARTER_Y = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0)
"""A quarter turn about +y (LDraw's right-hand rule): +x goes to -z."""
HALF_Y = (-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0)
"""A half turn about the vertical."""
POS_TOL = 0.6
MAX_COORD = 100_000
ROT_TOL = 0.02


@dataclass(frozen=True)
class ModulePart:
    file: str
    pos: tuple[float, float, float]
    m: tuple[float, ...]
    side: str  # "fixed" or "moving"
    role: str  # "main" (takes colour), "moving" (takes moving_colour), "tyre" (black)


@dataclass(frozen=True)
class Module:
    name: str
    title: str
    purpose: str
    kind: str  # "WHEEL", "SPIN", "SWING"
    low: float
    high: float
    at: tuple[float, float, float]
    axis: tuple[float, float, float]
    parts: tuple[ModulePart, ...]
    attach: str  # how it attaches, in words
    moves: str  # what moves and how, in words
    official: str  # the official way these parts go together, and where it was read
    moving_default: int | None = None  # colour of "moving" parts when none is given
    fit_radius: float = 10.0  # its own two sides are made to fit round each other this near
    panel: tuple[float, float, float] | None = None  # a hinge: the way its panel is built
    notes: tuple[str, ...] = field(default_factory=tuple)

    def joint(self, name: str = "") -> Joint:
        return Joint(
            name or self.name,
            self.kind,
            np.array(self.at, dtype=float),
            np.array(self.axis, dtype=float) / np.linalg.norm(self.axis),
            [1 + k for k, p in enumerate(self.parts) if p.side == "fixed"],
            [1 + k for k, p in enumerate(self.parts) if p.side == "moving"],
            self.low,
            self.high,
            self.name,
        )

    def range_words(self) -> str:
        if self.kind == "SWING":
            return f"swings from {fmt(self.low)} to {fmt(self.high)} degrees"
        return "turns freely all the way round"


def _wheel_pair(rim: str, tyre: str, tyre_off: float) -> tuple[ModulePart, ...]:
    return (
        ModulePart("4600.dat", (0, 0, 0), IDENTITY, "fixed", "main"),
        ModulePart(rim, (-30, 5, 0), WHEEL_ON_LEFT, "moving", "moving"),
        ModulePart(tyre, (-30 - tyre_off, 5, 0), WHEEL_ON_LEFT, "moving", "tyre"),
        ModulePart(rim, (30, 5, 0), WHEEL_ON_RIGHT, "moving", "moving"),
        ModulePart(tyre, (30 + tyre_off, 5, 0), WHEEL_ON_RIGHT, "moving", "tyre"),
    )


_WHEEL_PIN = (
    "the plate's wheel pins are 4 LDU in radius and reach from x = 22 to x = 34 at y = 5 "
    "(the wpin2 primitive and the plate's triangles); the wheel's hole is open on its +z face, "
    "so the wheel goes on with that face against the end of the pin's fillet at x = 22 and its "
    "centre 8 LDU further out, at x = 30"
)

MODULES: dict[str, Module] = {}


def _add(m: Module) -> None:
    MODULES[m.name] = m


_add(
    Module(
        name="wheels-small",
        title="Small wheels, a pair on one axle line",
        purpose="Wheels for a small car, a cart, a trailer or a toy on wheels: one module is "
        "the front or back axle.",
        kind="WHEEL",
        low=0,
        high=0,
        at=(0, 5, 0),
        axis=(1, 0, 0),
        parts=_wheel_pair("4624.dat", "3641.dat", 0),
        attach="the plate (4600) has 4 studs on top and a ring underneath: hang it under a "
        "chassis plate (under_socket) or stand it on the ground; its wheel line runs along x "
        "(turn 1 or 3 for wheels on a line along z)",
        moves="the two wheels and tyres turn about the line through the wheel pins, 5 LDU "
        "below the plate's top, along the plate's x",
        official="Plate 2 x 2 with 2 Wheel Pins (4600) with Wheel Rim 6.4 x 8 (4624) and Tyre "
        "6/50 x 8 Offset Tread (3641) on each pin, as on the classic Town cars; wheel and tyre "
        "together as the library's 4624c01. " + _WHEEL_PIN + ".",
        moving_default=71,
    )
)
_add(
    Module(
        name="wheels-large",
        title="Large wheels, a pair on one axle line",
        purpose="Wheels for a bigger car or truck: one module is the front or back axle.",
        kind="WHEEL",
        low=0,
        high=0,
        at=(0, 5, 0),
        axis=(1, 0, 0),
        parts=_wheel_pair("6014b.dat", "6015.dat", 6),
        attach="the plate (4600) has 4 studs on top and a ring underneath: hang it under a "
        "chassis plate (under_socket) or stand it on the ground; its wheel line runs along x",
        moves="the two wheels and tyres turn about the line through the wheel pins, 5 LDU "
        "below the plate's top, along the plate's x",
        official="Plate 2 x 2 with 2 Wheel Pins (4600) with Wheel Rim 12 x 11 with Notched "
        "Hole (6014b) and Tyre 12/40 x 11 Wide (6015) on each pin; wheel and tyre together as "
        "the library's 6014bc01 (the tyre 6 LDU along the wheel's -z). " + _WHEEL_PIN + ".",
        moving_default=71,
    )
)
_add(
    Module(
        name="wheel-large-single",
        title="One large wheel on a wheel pin",
        purpose="A single large wheel at one corner, when the body between the wheels is "
        "wide: four of these make a car's wheels (turn 2 for the other side).",
        kind="WHEEL",
        low=0,
        high=0,
        at=(0, 5, 0),
        axis=(1, 0, 0),
        parts=(
            ModulePart("4488.dat", (0, 0, 0), IDENTITY, "fixed", "main"),
            ModulePart("6014b.dat", (30, 5, 0), WHEEL_ON_RIGHT, "moving", "moving"),
            ModulePart("6015.dat", (36, 5, 0), WHEEL_ON_RIGHT, "moving", "tyre"),
        ),
        attach="the plate (4488) has 4 studs on top; hang it under the chassis (under_socket) "
        "with the wheel outside the body; turn 2 puts the wheel on the -x side",
        moves="the wheel and tyre turn about the wheel pin's line, 5 LDU below the plate's "
        "top, along x",
        official="Plate 2 x 2 with 1 Wheel Pin (4488) with Wheel Rim 12 x 11 with Notched Hole "
        "(6014b) and Tyre 12/40 x 11 Wide (6015), as the AI-built car of 19 November used "
        "them; wheel and tyre together as the library's 6014bc01. " + _WHEEL_PIN + ".",
        moving_default=71,
    )
)
_HINGE_BRICK = (
    "Hinge Brick 1 x 4 Base (3831) and Hinge Brick 1 x 4 Top (3830) at the same place, as the "
    "two halves of one hinge brick are always drawn; the axis is the vertical line through "
    "their common origin (both files draw their round knuckle about it, and the top's pin, the "
    "connect2 primitive at (0, 8, 0), points along it)"
)
_add(
    Module(
        name="door-hinge-left",
        title="Door hinge, hinge at the left end of the door",
        purpose="A door that swings open about a vertical line (a car door, a house door, a "
        "cupboard): the hinge is at the door's left end as seen from the side it opens "
        "toward. Build the door on the top half's two studs.",
        kind="SWING",
        low=0,
        high=90,
        at=(0, 0, 0),
        axis=(0, 1, 0),
        panel=(1, 0, 0),
        parts=(
            ModulePart("3831.dat", (0, 0, 0), IDENTITY, "fixed", "main"),
            ModulePart("3830.dat", (0, 0, 0), IDENTITY, "moving", "moving"),
        ),
        attach="the base half (3831) has 2 studs on top and sockets underneath: put it on "
        "the body like a 1 x 2 brick. Nothing that stays may hold the top half (3830): it "
        "must not stand on studs (put tiles under it, or let it stand out over the edge), and "
        "the door is built upward from its 2 studs only",
        moves="the top half and the door on it swing about the vertical line through the "
        "knuckle, opening toward -z (the module's front)",
        official=_HINGE_BRICK + "; the top swings away from the base toward the knuckle side.",
        notes=(
            "The door's own parts must stay clear of the base half and of the body when "
            "it swings: build them on the top half's studs, no wider than the top half "
            "at the hinge end.",
        ),
    )
)
_add(
    Module(
        name="door-hinge-right",
        title="Door hinge, hinge at the right end of the door",
        purpose="A door that swings open about a vertical line, hinged at its right end as "
        "seen from the side it opens toward (the other hand of door-hinge-left). The base "
        "half points into the body at right angles to the door.",
        kind="SWING",
        low=0,
        high=90,
        at=(0, 0, 0),
        axis=(0, -1, 0),
        panel=(0, 0, -1),
        parts=(
            ModulePart("3831.dat", (0, 0, 0), IDENTITY, "fixed", "main"),
            ModulePart("3830.dat", (0, 0, 0), QUARTER_Y, "moving", "moving"),
        ),
        attach="the base half (3831) has 2 studs on top and sockets underneath: put it on "
        "the body like a 1 x 2 brick. Nothing that stays may hold the top half (3830): it "
        "must not stand on studs (put tiles under it, or let it stand out over the edge), and "
        "the door is built upward from its 2 studs only",
        moves="the top half and the door on it swing about the vertical line through the "
        "knuckle, opening toward +x (the door, lying along -z, swings out to the module's "
        "right); at 90 degrees the two halves are in one line",
        official=_HINGE_BRICK + "; here the hinge starts folded a quarter turn and opens back "
        "to straight.",
    )
)
_add(
    Module(
        name="lid-hinge",
        title="Lid hinge, swings up about a level line",
        purpose="A lid, a hood, a bonnet, a tailgate or a hatch that swings up about a level "
        "line: build the panel on the top's two studs, reaching toward -z (the module's "
        "front) from the hinge line.",
        kind="SWING",
        low=0,
        high=90,
        at=(0, 10, 0),
        axis=(-1, 0, 0),
        panel=(0, 0, -1),
        parts=(
            ModulePart("3937.dat", (0, 0, 0), HALF_Y, "fixed", "main"),
            ModulePart("3938.dat", (0, 0, 0), HALF_Y, "moving", "moving"),
        ),
        attach="the base (3937) sits on studs like a 1 x 2 brick (it has no studs of its "
        "own); the panel goes on the top's (3938) two studs and must be held by nothing else",
        moves="the top and the panel on it swing up about the level line along x, 10 LDU "
        "below the top's studs: the -z side rises",
        official="Hinge 1 x 2 Base (3937) and Hinge 1 x 2 Top (3938) at the same place, as the "
        "library's assembled 3937c01 draws them; the axis is the line along x through (0, 10, "
        "0), about which 3937's knuckle cylinders are drawn. The base stands up to y = 2 on its "
        "own +z side and only to y 16 on its -z side, so the top can only tip one way: the "
        "edge over the low side goes down. Both parts are turned half round here so that the "
        "low side is the module's +z and the panel on the -z side rises.",
    )
)
_add(
    Module(
        name="turntable-small",
        title="Turntable 2 x 2, a head or a small turret that turns",
        purpose="Anything that turns about a vertical line: a head on a body, a small turret, "
        "a crane's cab, a rotating sign. Build what turns on the top's four studs.",
        kind="SPIN",
        low=0,
        high=0,
        at=(0, 0, 0),
        axis=(0, -1, 0),
        parts=(
            ModulePart("3680.dat", (0, 0, 0), IDENTITY, "fixed", "main"),
            ModulePart("3679.dat", (0, 0, 0), IDENTITY, "moving", "moving"),
        ),
        attach="the base (3680) sits on studs with the ring underneath (on a 2 x 2 corner of "
        "studs); what turns goes on the top's (3679) four "
        "studs and must be held by nothing else",
        moves="the top and everything on it turn about the vertical line through the centre",
        fit_radius=26.0,
        official="Turntable 2 x 2 Plate Base (3680) and Turntable 2 x 2 Plate Top (3679) at the "
        "same place, as the library's assembled 3680c01 draws them; the axis is the vertical "
        "line through their common origin, the centre of both.",
    )
)
_add(
    Module(
        name="turntable-large",
        title="Turntable 4 x 4, a turret or a cab that turns",
        purpose="A larger part that turns about a vertical line: a tank's turret, a crane's "
        "cab, a big head. Build what turns on the top's twelve studs.",
        kind="SPIN",
        low=0,
        high=0,
        at=(0, 0, 0),
        axis=(0, -1, 0),
        parts=(
            ModulePart("3403.dat", (0, 0, 0), IDENTITY, "fixed", "main"),
            ModulePart("3404.dat", (0, 0, 0), IDENTITY, "moving", "moving"),
        ),
        attach="the base (3403) sits on studs with the rings underneath; what turns goes on "
        "the top's (3404) twelve studs and must be held by nothing else",
        moves="the top and everything on it turn about the vertical line through the centre",
        fit_radius=58.0,
        official="Turntable 4 x 4 Base (3403) and Turntable 4 x 4 Top (3404) at the same place, "
        "as the library's assembled 3403c01 draws them; the axis is the vertical line through "
        "their common origin.",
    )
)


# ---- putting a module in --------------------------------------------------------------------


@dataclass
class ModulePlacement:
    lines: list[str]  # the parts' lines, then the joint line
    joint: Joint  # with the line numbers the parts get when appended to the text
    note: str


def _colour_for(p: ModulePart, colour: int, moving_colour: int | None, mod: Module) -> int:
    if p.role == "tyre":
        return 0
    if p.role == "moving":
        if moving_colour is not None:
            return moving_colour
        return mod.moving_default if mod.moving_default is not None else colour
    return colour


def _matrix(m: tuple[float, ...]) -> np.ndarray:
    return np.array(m, dtype=float).reshape(3, 3)


def _lowest(mod: Module, rot: np.ndarray, lib: Library) -> float:
    low = -np.inf
    for p in mod.parts:
        part = lib.part(p.file)
        lo, hi = part.bbox_min, part.bbox_max
        corners = np.array(
            [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
        )
        w = (corners @ _matrix(p.m).T + np.array(p.pos)) @ rot.T
        low = max(low, float(w[:, 1].max()))
    return low


def _get(name: str) -> Module:
    mod = MODULES.get(str(name).strip().lower())
    if mod is None:
        raise PlaceError(
            f"There is no module '{str(name)[:40]}'. The modules are: {', '.join(MODULES)}."
        )
    return mod


def place_module(
    text: str,
    name: str,
    colour: int,
    line: int,
    *,
    stud: int | None = None,
    socket: int = 1,
    under_socket: int | None = None,
    own_stud: int = 1,
    turn: int = 0,
    x: float = 0.0,
    z: float = 0.0,
    joint_name: str | None = None,
    moving_colour: int | None = None,
    lib: Library | None = None,
) -> ModulePlacement:
    from bricksnap.lab.joints import NAME, parse

    lib = lib or library()
    mod = _get(name)
    if turn not in (0, 1, 2, 3):
        raise PlaceError("turn is a number of quarter turns: 0, 1, 2 or 3.")
    existing = {j.name.lower() for j in parse(text)[0]}
    if joint_name is None:
        k = 1
        while f"{mod.name}-{k}" in existing:
            k += 1
        joint_name = f"{mod.name}-{k}"
    joint_name = joint_name.strip().replace(" ", "-")
    if not NAME.match(joint_name):
        raise PlaceError(
            "name must be one word of letters, digits, - and _ (at most 40), such as left-door."
        )
    if joint_name.lower() in existing:
        raise PlaceError(
            f"There is already a joint called '{joint_name}'; give this one its own name."
        )
    for what, v in (("x", x), ("z", z)):
        if not isinstance(v, int | float) or not math.isfinite(v) or abs(v) > MAX_COORD:
            raise PlaceError(
                f"{what} must be an ordinary number between -{MAX_COORD} and {MAX_COORD}."
            )
    anchor = mod.parts[0]
    a_m, a_pos = _matrix(anchor.m), np.array(anchor.pos, dtype=float)
    # the anchor's own quarter turns inside the module: place() counts turns on the anchor,
    # so the module ends up turned exactly ``turn`` quarter turns whichever way it sits
    a_turn = next((k for k in range(4) if np.allclose(np.linalg.matrix_power(QUARTER, k), a_m)), 0)
    if line == 0:
        rot = np.linalg.matrix_power(QUARTER, turn)
        low = _lowest(mod, rot, lib)
        pos = np.array([x, -low, z])
        how = f"stands on the ground with its middle above x {fmt(x)}, z {fmt(z)}"
    else:
        got = place(
            text,
            anchor.file,
            colour,
            line,
            stud=stud,
            socket=socket,
            under_socket=under_socket,
            own_stud=own_stud,
            turn=(turn + a_turn) % 4,
            lib=lib,
        )
        # the module's frame in the model: the anchor's place, less its place in the module
        rot = got.m @ a_m.T
        pos = got.pos - rot @ a_pos
        how = got.note.split(" Its body")[0].replace(anchor.file, f"its anchor {anchor.file}", 1)
        how = re.sub(r", turned \d quarter turns?", "", how)
        if turn:
            how += f", turned {turn} quarter turn{'s' if turn != 1 else ''}"
    if turn and line == 0:
        how += f", turned {turn} quarter turn{'s' if turn != 1 else ''}"
    first = len(text.splitlines()) + 1
    out = []
    for p in mod.parts:
        pw = rot @ np.array(p.pos, dtype=float) + pos
        mw = _clean(rot @ _matrix(p.m))
        out.append(ldraw_line(_colour_for(p, colour, moving_colour, mod), pw, mw, p.file))
    j = mod.joint(joint_name)
    j.at = rot @ j.at + pos
    j.axis = rot @ j.axis
    j.fixed = [first + n - 1 for n in j.fixed]
    j.moving = [first + n - 1 for n in j.moving]
    j.line = first + len(out)
    out.append(joint_line(j))
    note = f"The module {mod.name}: {how.rstrip('.')}." + _where_words(mod, rot, pos, lib)
    return ModulePlacement(out, j, note)


def _dir_word(v: np.ndarray) -> str:
    """The model's own name for a direction: +x (right), -z (front), up..."""
    names = {
        (0, 1): "+x (to the right)",
        (0, -1): "-x (to the left)",
        (1, 1): "down",
        (1, -1): "up",
        (2, 1): "+z (to the back)",
        (2, -1): "-z (to the front)",
    }
    k = int(np.argmax(np.abs(v)))
    if abs(float(v[k])) < 0.9 * float(np.linalg.norm(v)):
        return "a slant (" + ", ".join(fmt(round(float(x), 2)) for x in v / np.linalg.norm(v)) + ")"
    return names[(k, 1 if v[k] > 0 else -1)]


def _where_words(mod: Module, rot: np.ndarray, pos: np.ndarray, lib: Library) -> str:
    """For a hinge: where its moving half is and which way it opens, in the model's own
    directions; for a wheel or turntable, which way its axle points."""
    from bricksnap.lab.joints import rotation

    axis = rot @ np.array(mod.axis, dtype=float)
    axis /= np.linalg.norm(axis)
    if mod.kind != "SWING":
        return f" It turns about a line pointing {_dir_word(axis)}."
    panel = rot @ np.array(mod.panel or (1, 0, 0), dtype=float)
    to = rotation(axis, 30) @ panel - panel
    move = _dir_word(to)
    move = move if move in ("up", "down") else "toward " + move
    return (
        f" Build the panel toward {_dir_word(panel)} from the hinge line, on the moving half's "
        f"studs; opening moves it {move}."
    )


def module_text(name: str, colour: int = 71, lib: Library | None = None) -> str:
    """The module alone on the ground, with its joint line, as a model file."""
    got = place_module("", name, colour, 0, lib=lib)
    return "\n".join(got.lines) + "\n"


def verify(joint: Joint, by_line: dict) -> str | None:  # type: ignore[type-arg]
    mod = MODULES.get(joint.module.lower())
    if mod is None:
        return f"there is no module called '{joint.module}'"
    fixed = [p for p in mod.parts if p.side == "fixed"]
    moving = [p for p in mod.parts if p.side == "moving"]
    if len(joint.fixed) != len(fixed) or len(joint.moving) != len(moving):
        return (
            f"that module has {len(fixed)} fixed and {len(moving)} moving parts, and the joint "
            f"names {len(joint.fixed)} and {len(joint.moving)}"
        )
    pairs = list(zip(joint.fixed + joint.moving, fixed + moving, strict=True))
    for n, p in pairs:
        if by_line[n].key != p.file:
            return f"line {n} is {by_line[n].key}, where the module has {p.file}"
    a = by_line[joint.fixed[0]]
    rot = a.m @ _matrix(fixed[0].m).T
    pos = a.pos - rot @ np.array(fixed[0].pos)
    for n, p in pairs:
        want_pos = rot @ np.array(p.pos) + pos
        want_m = rot @ _matrix(p.m)
        got = by_line[n]
        if np.linalg.norm(got.pos - want_pos) > POS_TOL or np.abs(got.m - want_m).max() > ROT_TOL:
            return (
                f"line {n} is not where the module puts it beside line {joint.fixed[0]} (it "
                f"should be at {' '.join(fmt(round(float(v), 1)) for v in want_pos)})"
            )
    want_axis = rot @ np.array(mod.axis, dtype=float)
    want_axis /= np.linalg.norm(want_axis)
    want_at = rot @ np.array(mod.at, dtype=float) + pos
    rel = joint.at - want_at
    off = float(np.linalg.norm(rel - np.dot(rel, want_axis) * want_axis))
    if float(np.dot(joint.axis, want_axis)) < 0.999 or off > POS_TOL:
        return "its AT and AXIS are not the module's axis"
    # a turntable may be limited to part of a turn (a lorry's fifth wheel)
    if (
        mod.kind == "SPIN"
        and joint.kind == "SWING"
        and joint.low >= -180 - 1e-6
        and joint.high <= 180 + 1e-6
    ):
        return None
    if joint.kind != mod.kind or joint.low < mod.low - 1e-6 or joint.high > mod.high + 1e-6:
        return (
            f"the module {mod.range_words()} as a {mod.kind}, and the joint asks for more "
            "(a joint may only ask for a smaller range than its module)"
        )
    return None


# ---- describing a module --------------------------------------------------------------------


def measure(mod: Module, lib: Library | None = None) -> dict[str, float]:
    """The module's sizes, measured from its parts' real shapes standing on the ground:
    ``x`` and ``z`` across in studs, ``height`` in plates (studs left out), and for wheels
    ``tyre`` (across, in LDU) and ``top`` (how high the anchor's top stands, in LDU)."""
    lib = lib or library()
    got = place_module("", mod.name, 4, 0, lib=lib)
    pts = []
    for ln in got.lines[:-1]:
        tok = ln.split()
        nums = [float(v) for v in tok[2:14]]
        m = np.array(nums[3:12]).reshape(3, 3)
        pts.append(lib.triangles(tok[14]).reshape(-1, 3) @ m.T + np.array(nums[0:3]))
    allp = np.concatenate(pts)
    lo, hi = allp.min(0), allp.max(0)
    out = {
        "x": round(float(hi[0] - lo[0]) / 20, 2),
        "z": round(float(hi[2] - lo[2]) / 20, 2),
        "height": round(float(hi[1] - lo[1]) / 8, 2),
    }
    if mod.kind == "WHEEL":
        j = got.joint
        rel = np.concatenate([pts[n - 1] for n in j.moving]) - j.at
        a = rel @ j.axis
        out["tyre"] = round(2 * float(np.linalg.norm(rel - np.outer(a, j.axis), axis=1).max()), 1)
        out["top"] = round(-float(got.lines[0].split()[3]), 1)
    return out


def size_words(mod: Module, lib: Library | None = None) -> str:
    m = measure(mod, lib)
    text = (
        f"{fmt(m['x'])} studs across in x, {fmt(m['z'])} in z, and {fmt(m['height'])} plates "
        "tall in all (measured from the parts)"
    )
    if "tyre" in m:
        text += (
            f"; the tyres are {fmt(m['tyre'])} LDU across "
            f"({fmt(round(m['tyre'] / 20, 2))} studs), so "
            f"standing on them the plate's top is {fmt(m['top'])} LDU above the ground"
        )
    return text


def card(mod: Module, lib: Library | None = None) -> str:
    """The module's full card, for the ``modules`` tool."""
    lib = lib or library()
    out = [f"{mod.name}: {mod.title}.", mod.purpose, f"Size: {size_words(mod, lib)}."]
    out.append(f"How it attaches: {mod.attach}.")
    out.append(f"What moves: {mod.moves}; it {mod.range_words()}.")
    out.append("Its parts, in the module's own frame (the anchor's frame; y down):")
    for k, p in enumerate(mod.parts, 1):
        desc = lib.part(p.file).description
        anchor = " (the anchor)" if k == 1 else ""
        out.append(
            f"  {k}. {p.file} {desc}: {p.side}{anchor}, at "
            f"({', '.join(fmt(v) for v in p.pos)}), rotation {' '.join(fmt(v) for v in p.m)}"
        )
    axis = ", ".join(fmt(v) for v in mod.axis)
    out.append(
        f"The joint: {mod.kind}, about the line through ({', '.join(fmt(v) for v in mod.at)}) "
        f"along ({axis})."
    )
    out.append(f"How these parts go together: {mod.official}")
    for n in mod.notes:
        out.append(n)
    out.append(
        "The grip of the joint (that it holds) comes from how these parts are designed to be "
        "used; the checker proves only that the moving side is free to move."
    )
    return "\n".join(out)


def opened_angle(mod: Module) -> float:
    """The angle a picture shows the module opened at: the far end of a swing, an eighth of
    a turn for a spin or a wheel."""
    if mod.kind == "SWING":
        return mod.high if mod.high > 0 else mod.low
    return 45.0


def module_sheet(name: str, out_png):  # type: ignore[no-untyped-def]
    """A picture of the module at rest and opened, from the front-left above."""
    from bricksnap.lab import picture
    from bricksnap.lab.joints import opened

    mod = _get(name)
    text = module_text(mod.name, 4)
    angle = opened_angle(mod)
    open_text = opened(text, {mod.name + "-1": angle})
    images = []
    for t in (text, open_text):
        imgs, _, _, _ = picture._render_many(t, [(30.0, -45.0)], picture.RENDER_PX)
        images.append(imgs[0])
    moved = "opened" if mod.kind == "SWING" else "turned"
    labels = ["at rest (0 degrees)", f"{moved} {fmt(angle)} degrees"]
    panels = [(lab, im.crop(picture._trim_box(im))) for lab, im in zip(labels, images, strict=True)]
    picture._sheet(panels, f"{mod.name}: {mod.title}").save(out_png)
    return out_png
