"""Check a model written as LDraw text and say what is wrong (research prototype).

CONTRACT (tests in tests/test_lab.py)

``check(text, lib=None) -> Report``; ``Report.text()`` is what the AI reads.

Input: LDraw text. Type 1 lines (``1 colour x y z a b c d e f g h i file.dat``, any rotation
matrix) are parts; ``0 STEP`` separates steps; other ``0`` lines are comments; lines of types
2 to 5 are drawing lines and are ignored with a warning; ``0 FILE`` (several models in one
file) is not supported. Line numbers are the lines of the text as given, counting from 1.

What it reports, each item naming the line number, the part and its position:
- Lines that are not valid (too few numbers, a number that is not one, a matrix that is not
  a rotation, a mirrored part) and part files that do not exist (with close names from the
  index), sub-parts and primitives used as parts, old numbers ("~Moved to"), colours that
  are not in LDConfig.ldr, and colour 16/24 (they have no colour of their own).
- Overlaps: the filled bodies of two parts (``ldraw_lib``: hollow undersides count as solid,
  arch spans and overhangs stay open) share more than a small volume. Under ``SMALL_OVERLAP``
  LDU^3 (and under ``SMALL_SHARE`` of the smaller part) it is a warning; when either part
  joins by pins, axles, bars or clips (they go into other parts) it is a joint "not checked"
  (below). Otherwise it is a problem only when the parts' REAL shapes confirm it
  (``solid.in_the_way``: they share a piece of material at least 1.5 LDU thick, which a
  seated stud and parts that only touch never do, and a part pushed 2 LDU or more into
  another always does); the filled body is a column too wide at a bracket's flange or under
  a curved slope's stepped underside, and parts that only touch there are not an overlap.
  Only the pairs the filled bodies flag are measured on the real shapes. The same part
  twice in the same place is always an overlap problem, whatever joints it has.
- Connections: part A holds part B when a stud of A reaches into B's filled body pointing
  into B's underside (B's own "up" against the stud), with the stud's base at B's bottom
  (within ``SEAT_TOL`` LDU) and on B's stud grid (the centres of its stud cells, within
  ``GRID_TOL`` LDU; ``stud_grid``: ``Part.socket_phase``, except that a part with no top
  studs whose box is not whole studs, such as a curved slope with a cutout, takes its grid
  from the end of its box that is on the grid round its origin), or when a stud of A sits in
  an open tube or ring of B (the stud in the centre tube of a 2 x 2 brick, a plant leaf's
  ring). Any orientation works: studs on the side of a part are checked the same way. A stud
  that reaches into B in any other way is a problem, with the reason: off B's grid (by how
  much, and where to move B to), not pressed home (the gap), pushed in too far, or into B's
  side or top.
- Joints other than studs: when a part joins by clips, bars, pins, axles, hinges, ball
  joints or wheel pins (from its primitives or its name) and touches another part with no
  stud connection between them, the pair counts as joined when deciding what is loose, and
  is listed as tested for fit or known by name only (see "Two kinds of joint" below). An
  axle counts along its whole length (``Connector.points``),
  a bar handle along its bar (``_handle_bars``: a handle is drawn with a primitive at each
  end of its bar, and the bar runs through the middle of each one's reach), other connectors
  at their own place. A named joint excuses only what the joint needs (``_joint_clash``):
  the pair's real shapes are measured as any overlap is, leaving out the joint's room
  (``JOINT_ROOM``: a cylinder round each receptacle's line, 2 LDU past its ends: a pin hole,
  an axle hole, a wheel hole, a clip, a hinge, a ball socket, never the pin or axle that goes
  in; round a handle's bar; for a wheel known only by name round its round axis; for a tyre
  on a wheel the tyre's own round box; for a turntable the round box of each half). Outside
  the room (everywhere, for a joint known only by name) they may still share a piece less
  than ``JOINT_SNUG_DEPTH`` deep and ``JOINT_SNUG_VOL`` LDU^3 in all, as the library's shapes
  of parts made to go together do (a giant torso's arm on its pin shares 1 LDU deep and
  about 250 LDU^3). More than that is an overlap problem saying so: two bar tubes 2 LDU
  apart, a brick with a pin pushed 2 LDU too far into a Technic brick, a wheel pushed through
  its tyre, two wheels-with-tyres 10 LDU apart. A clip joins a handle or a bar part only
  within ``CLIP_REACH`` LDU of its bar (a clip 12 LDU above a handle, or a Bar 3L standing
  12 LDU beside a clip, is not joined); a clip round a bar the rough bodies do not reach is
  joined when its grip holds (``_could_grip``). A part's own clip does not stop its name
  making it a bar, a bar tube or a handle (3628, 4735, 48729, 11090).
  A wheel's line (``_wheel_lines``) is its wheel, axle or pin hole if one is at least
  ``HOLE_SHORT`` LDU long, else its round axis (``_round_axis``): from its box when two sides
  are equal, else from its real shape when that is a body of revolution about one of the
  part's axes (``_body_axis``: spokes and all; 364 of the library's 382 wheels and tyres).
  A wheel pin joins a wheel only on that line, parallel within ``AXLE_DEG`` and within
  ``AXLE_LDU``, and in as far as the shorter of the pin and the hole (half the wheel's width
  when the line is its round axis) less ``WHEEL_PLAY`` (``_wheel_on_pin``; the library's own
  motorcycle 30187c01 has its wheel 1.5 LDU short). A tyre sits on a wheel only on the
  wheel's round axis (or a hole off it), over all but ``TYRE_PLAY`` LDU of the narrower one's
  width; two parts that are each a wheel with its tyre are not a tyre on a wheel
  (``_tyre_on_wheel``). A wheel with no line at all (18 of the library's knobbly tyres and
  odd wheels) is judged as before, by nearness. A tyre need only be round the pin's line by
  ``WHEEL_IN``, so a wheel slid off its pin with its tyre still round the pin hangs on the
  tyre (a stated limit). The clip's room takes in most of a 1 x 1 clip plate, so a handle
  pressed into a small clip plate is not caught; the clip, bar-handle, wheel-hole, tyre and
  turntable rooms are upper bounds that no test pins down (loosened, no test fails). The
  library's assemblies (its shortcuts) that name such a joint are a standing guard
  (``tests/test_lab_assemblies.py``). An axle the library draws
  with axle-hole primitives (``ldraw_lib``) joins only when its line runs along a hole of
  the other part (parallel within ``AXLE_DEG`` degrees, within ``AXLE_LDU`` LDU, the hole's
  reach and the axle's length sharing ``AXLE_IN`` LDU): an axle through a wheel turned
  across it is an overlap, and a bush beyond the axle's end is not on it. A "Bar
  Tube" is a tube a bar goes into (a clip), not a bar. Also listed as "not checked" joints:
  - a bar in a hollow (``_bar_in``): an open stud (``ldraw_lib.OPEN_STUD``; its hollow is the
    stud, 4 LDU from base to tip), an open tube, an axle hole (a round brick's middle), a
    pin hole or the hollow end of a pin (a through hole the library draws as one primitive
    at each face is one hole, end to end: a Technic brick's is 20 LDU deep). All of these
    must hold:
    1. In: from 1 LDU outside one end of the hollow inwards the other part's real solid is
       there without a break (on the axis, or as a tube of bar size round it: 6 of 8 points
       ``BAR_TUBE`` LDU out, a bar end the library draws hollow), and nowhere inside the
       hollow reaches the ring ``BAR_RING`` LDU round it (no thicker than a bar, 4 LDU in
       radius), for at least the hollow's depth (an open stud's 4; ``BAR_DEPTH`` for a
       longer hollow) less ``BAR_PLAY`` (1 LDU, as a stud may sit 1 LDU short of home).
       A bar in by 2 LDU or floating above the hollow is not held.
    2. Along the axis: from the bar's inner end outwards for ``BAR_LEAN`` LDU, while it is
       still a bar (it fills fewer than 3 of 8 points of the ring), the middle of its
       cross-section is within ``BAR_OFF`` of the axis and its line leans less than
       ``BAR_DEG`` degrees (measured to about a degree on the 0.5 LDU voxels).
    3. Nothing else: the real shapes share no more than touching outside the hollow's own
       space (the cylinder of ``BAR_RING`` round the axis between the hollow's two ends). So a
       bar comes in through an open end: one driven through a brick's top into the tube
       below, or past the bottom of a jumper's 4 LDU stud, goes through material and is an
       overlap or a stud problem, never a joint.
    4. Not on into another part: a part held only as a bar in a hollow whose bar goes on
       past the hollow and 1.5 LDU or more into a third part's real solid (a bar down a round
       brick's middle and on into the plate below) makes that a problem, even when the
       filled bodies' overlap was only slight (``_bar_goes_on``).
    A claw, a lamp post's bar, a plant stem through round plates, the solid tube under a
    1 x 2 plate in a jumper's open stud are such joints; a pin or a stud (6 in radius) is
    not, nor a bar beside the hollow, leaning, or in too short. A bar in a Technic pin hole
    (6 in radius) has 1.5 to 2 LDU of play all round: it is listed as a joint, called "a
    loose fit".
  - a stud in a Technic pin hole, pointing along the hole's axis (within ``AXLE_DEG``) with
    its base within ``AXLE_LDU`` LDU of it and within 2 LDU of the hole's reach. A pin hole
    takes one stud: a second stud in the same hole (from its other end) is a stud problem.
  A bar or a stud on no such axis is checked as before (a stud problem, an overlap, loose).
- Two kinds of joint (other than studs). A joint TESTED FOR FIT is one whose position the
  checker has measured: the one part is in the other where and as far as it should be (the
  same kind of test a stud gets; grip is judged for neither). Each is an item of severity
  "fit" (``Report.fits``, lines [the part that holds, the part held], text "line N (part)
  is held ..."), not in NOT CHECKED: (``_fit_of``, ``_fit_issue``)
  - a wheel on a wheel pin: the pin on the wheel's line (a hole of at least ``HOLE_SHORT``,
    else the axis of its round box: two sides within ``BOX_ROUND``) and in as far as the
    shorter of pin and hole (half the wheel's width on a box's axis) less ``WHEEL_PLAY``
    (``_wheel_pin_fit``); never a tyre on the pin (the pin is in the wheel, not its tyre),
    and never a wheel whose line comes only from its real shape (``_body_axis``: good enough
    to accept the joint, not to measure its fit);
  - a tyre on a wheel: the tyre's round box on the wheel's (or on a hole of it at least
    ``HOLE_SHORT`` long), over all but ``TYRE_PLAY`` of the narrower width (``_tyre_fit``);
  - an axle the library draws with axle-hole primitives, along an axle or pin hole, the two
    sharing ``AXLE_IN`` (``_axle_fit``);
  - a Technic pin in a pin hole: on the hole's line and in as far as the shorter of the pin
    half and the hole (a through hole drawn at each face is one hole) less ``PIN_PLAY``
    (``_pin_fit``; a full pin's other half, which the library does not draw as a pin, is
    taken from its box: ``_pin_halves``);
  - a bar in a hollow (``_bar_fits``, as above; a "Bar Tube" such as 23443 or 11090, which
    the library draws with no primitive for its bore, gets one from its real shape:
    ``_tube_hollows``) and a stud in a Technic pin hole;
  - a clip on a bar or a handle (``_clip_fit``): the bar (a handle's, ``_handle_bars``, or a
    bar part's long axis, ``_bar_lines``) along the clip's grip (``grip_lines``, found per
    clip in the part's real shape, with or without a clip primitive) within ``CLIP_DEG``
    degrees, and at the bar's point nearest the grip the grip holds (``_grip_holds``): the
    bar bar-thick, the clip closed round it (``GRIP_RING`` of 12 points on a circle of
    ``GRIP_R``, more than half; none at 3 LDU) there and ``GRIP_HALF`` either side, which
    also keeps the grip off the bar's end. On a bar the library does not draw (23443's
    handle) the grip's own line is measured. Any angle about the bar's line is a fit;
  each on the line within ``AXLE_DEG`` degrees and ``AXLE_LDU`` LDU. Every other joint is
  KNOWN BY NAME ONLY (severity "not checked", the NOT CHECKED section): a clip with no closed
  grip (the thick U-clip 4085c) or not round its bar, hinge halves, finger hinges, ball and
  socket, a
  turntable outside a
  proven module, a wheel or tyre whose line comes from its shape or that has none, an axle
  or pin the library does not draw as one (or that misses the measure), a tyre touching a
  wheel pin, and anything judged by nearness. A joint tested for fit holds a part as a stud
  link does: it is listed under HOW IT HOLDS TOGETHER ("line 2 is held on the wheel pin of
  line 1 (in 12 LDU, 6 asked)") and counts as confirmed in ``held_only_item``; the report
  then says once that fit is tested and grip is not (``FIT_NOTE``).
- What is loose: groups of parts with no path of connections to a part on the ground
  (y = 0 at its lowest point, within ``GROUND_TOL``), each with what is below it and how far;
  groups that stand on the ground but are not joined to the rest (a warning); parts below the
  ground; no part on the ground at all. A single small loose part (filled body no more than
  ``SUNK_SMALL`` LDU^3) whose words would only be "There is no part under it", "It rests on
  ... but no stud goes into it" or "lowering it would not hold it either", and whose real
  shape goes into a held part (not loose) by no more than ``WAY_OUT`` LDU, says so instead:
  "It is sunk N LDU into line M: it is inside that part, not on it", with the move along one
  of the six axes that takes it out (``_way_out``). It is looked for only against the
  ``SUNK_NEAR`` held neighbours whose filled bodies it overlaps most, with no joint, bar or
  stud problem between them and no pin, axle or hole in either (those go into one another
  by design: the library may only lack the joint), for the first ``SUNK_LOOKS`` such parts
  of a check, with at most 2 + ``WAY_TRIES`` real-shape measurements each; words that name a
  real move onto studs are kept. Parts that reach the ground only through clip grips tested
  for fit and carry more than a strut, a rail, an aerial or a mirror (``clip_loads``: more
  than ``LOAD_PER_GRIP`` per clip, or held out on one clip beyond ``LOAD_ONE_GRIP``) get a
  warning naming them and a word in the summary: a clip holds a strut or a rail, and the
  checker cannot judge whether clips will carry more. Three official models trip it (75075,
  31066, 40379: their designers carry weight on several clips); it was kept on purpose, for
  every model, as a warning that never becomes a problem: it is not a false alarm to fix.
- Whether it stands: the centre of the filled bodies (taken as the centre of mass) must lie
  over the convex outline of what touches the ground.
- What moves (``movement.apply``): when the model has joint lines (``joints``), whether each
  moving thing can really move (tied shut, something in its way, wheels that rub, a model on
  wheels that does not rest on them), as problems of kind "movement", and one line per joint
  in a MOVEMENT section. A model without joint lines gets no movement findings; its report
  is the one it got before joints existed except for deliberate changes: a turntable's
  top and base (both named "Turntable") are a "not checked" joint, as a tyre on its wheel
  is, instead of an overlap problem; and since 2026-11-20 (experiment 3 of the study of real
  sets) overlaps are confirmed on the real shapes, bars in hollows, axles and studs in pin
  holes are joints, and cutout parts take their grid as above.
  ``check(text, movement=False)`` leaves this out (used to find what rides on a joint).
- A summary line: "N parts of M kinds, K problems ...". With no problems it says so in one
  line ("every part is held, nothing overlaps, and it stands"; when some parts are held
  only through joints the checker cannot confirm, "every part is held (N of them only by
  joints the checker cannot confirm)"); with joints it also says how many move freely, and
  how many problems are about movement.
- The NOT CHECKED section lists the joints known by name only (the first ``MAX_OTHERS``,
  then a count of the rest by kind) and then, never cut, the line naming the parts held only
  through them (``held_only_item``); "N joints not checked" counts them alone. Stud links
  and joints tested for fit count as confirmed; so do the joints inside a proven
  module: a joint line that names the module, whose parts ``modules.verify`` accepts as the
  module's parts in the module's places, and whose movement verdict is not a problem
  (``movement.apply`` puts the item again with those modules' parts joined). A module that
  is refused or cannot move, a joint the builder declared, and every joint when the check
  runs with ``movement=False`` or the model has no joint lines, count as unconfirmed.

Rough by design (and the report says so once): the filled body misses walls thinner than
about 2 LDU and treats side holes as solid (an overlap it misses is not looked for on the
real shapes); interference thinner than 1.5 LDU is not reported; joints known by name only
are never confirmed, and no joint's grip is judged (a bar's in its hollow, a pin's in its
hole, a stud's in its socket); whether a connection is strong (one stud or eight) is listed
but not judged.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

from bricksnap.lab.ldraw_lib import (
    OPEN_STUD,
    Connector,
    Library,
    Part,
    direction_word,
    fmt,
    library,
    norm_name,
)

SMALL_OVERLAP = 400.0  # LDU^3; a 1 x 1 plate is 3200
SMALL_SHARE = 0.10
IGNORE_OVERLAP = 100.0
SEAT_TOL = 1.0
GRID_TOL = 1.5
GROUND_TOL = 1.5
SUNK_SMALL = 10000.0  # LDU^3 (filled body): a part this small may be told it is sunk
SUNK_LOOKS = 8  # loose parts per check that are looked at for being sunk into another
SUNK_NEAR = 2  # held neighbours (most shared filled volume first) each is measured against
WAY_TRIES = 4  # real-shape measurements spent on finding that way out
WAY_OUT = 8  # LDU: how far the checker looks for the way out of a part sunk into another
DETAIL_PARTS = 40  # up to this many parts, the report says what holds each one
MAX_PROBLEMS = 40
MAX_OTHERS = 25
UP = np.array([0.0, -1.0, 0.0])

ROUGH_NOTE = (
    "(The overlap check is rough: it fills each part's hollow underside, so arches, overhangs "
    "and parts that go into one another can give false alarms; joints known by name only are "
    "never confirmed.)"
)
FIT_NOTE = (
    "(Joints tested for fit are measured, as studs are, for where and how far one part goes "
    "into the other; how firmly any joint grips is not judged.)"
)


@dataclass
class Placed:
    line: int
    colour: int
    pos: np.ndarray
    m: np.ndarray
    file: str  # as written
    key: str  # resolved file name, "3001.dat"
    part: Part
    step: int
    inv: np.ndarray = field(default_factory=lambda: np.eye(3))

    def to_local(self, pts: np.ndarray) -> np.ndarray:
        return (np.asarray(pts) - self.pos) @ self.inv.T

    def to_world(self, pts: np.ndarray) -> np.ndarray:
        return np.asarray(pts) @ self.m.T + self.pos

    def dir_local(self, d: np.ndarray) -> np.ndarray:
        v = self.inv @ d
        n = float(np.linalg.norm(v))
        return v / n if n > 1e-12 else v

    def label(self, colours: dict[int, str] | None = None) -> str:
        colour = ""
        if colours and self.colour in colours:
            colour = f", {colours[self.colour].lower()}"
        where = " ".join(fmt(v) for v in self.pos)
        return f"line {self.line} ({self.key} {self.part.description}{colour}, at {where})"


@dataclass
class Issue:
    severity: str  # "problem", "warning", "not checked", "fit" (a joint tested for fit)
    kind: str
    lines: list[int]
    text: str


@dataclass
class Link:
    holder: int  # line whose studs go in
    held: int  # line that takes them
    studs: list[int]  # stud numbers on the holder (1-based, as part_info numbers them)
    how: str  # "on top", "sideways", "underneath", "in a tube"


@dataclass
class Report:
    placed: list[Placed] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    grounded: list[int] = field(default_factory=list)
    stands: bool | None = None
    stand_text: str = ""
    lines_total: int = 0
    colours: dict[int, str] = field(default_factory=dict)
    movement: list[str] = field(default_factory=list)  # one line per joint
    moving_ok: int = 0  # joints that move freely
    reach: dict = field(default_factory=dict)  # joint name -> (low, high) degrees, or None

    @property
    def problems(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "problem"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def unchecked(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "not checked"]

    @property
    def fits(self) -> list[Issue]:
        """The joints tested for fit (see the contract): they hold a part as a stud does."""
        return [i for i in self.issues if i.severity == "fit"]

    @property
    def ok(self) -> bool:
        return not self.problems and bool(self.placed)

    def summary(self) -> str:
        n = len(self.placed)
        kinds = len({p.key for p in self.placed})
        k = len(self.problems)
        head = f"{n} part{'s' if n != 1 else ''} of {kinds} kind{'s' if kinds != 1 else ''}"
        if not n:
            return head + ": there is nothing to check (no part lines)."
        if not k:
            held = next((i for i in self.unchecked if i.kind == "held by unchecked joints"), None)
            loads = [i for i in self.warnings if i.kind == "held by clips"]
            notes = []
            if held is not None:
                notes.append(f"{len(held.lines)} of them only by joints the checker cannot confirm")
            if loads:
                c = sum(len(i.lines) for i in loads)
                notes.append(f"{c} only by clips, carrying more than a strut")
            tail = (
                f"no problems: every part is held ({'; '.join(notes)}), nothing overlaps, and "
                "it stands."
                if notes
                else "no problems: every part is held, nothing overlaps, and it stands."
            )
            extra = []
            if self.warnings:
                extra.append(
                    f"{len(self.warnings)} warning{'s' if len(self.warnings) != 1 else ''}"
                )
            if self.unchecked:
                extra.append(
                    f"{len(self.unchecked)} joint{'s' if len(self.unchecked) != 1 else ''} "
                    "not checked"
                )
            if self.movement:
                tail = tail[:-1] + f"; {_moves(self.moving_ok, len(self.movement))}."
            return f"{head}, {tail}" + (f" ({', '.join(extra)})" if extra else "")
        parts = [f"{k} problem{'s' if k != 1 else ''}"]
        moving = sum(1 for i in self.problems if i.kind == "movement")
        if moving:
            parts[0] += f" ({moving} about what moves)"
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning{'s' if len(self.warnings) != 1 else ''}")
        if self.unchecked:
            parts.append(
                f"{len(self.unchecked)} joint{'s' if len(self.unchecked) != 1 else ''} not checked"
            )
        return f"{head}, " + ", ".join(parts) + "."

    def text(self, connections: bool = True) -> str:
        """The report in words. A big model (more than ``DETAIL_PARTS`` parts) gets a summary
        of how it holds together instead of one line per part, and long lists of problems,
        warnings and unchecked joints are cut short with a count of the rest."""
        out = ["SUMMARY: " + self.summary()]

        def section(title: str, items: list[Issue], limit: int, numbered: bool) -> None:
            if not items:
                return
            out.append("")
            out.append(title)
            for k, x in enumerate(items[:limit], 1):
                out.append(f"{k}. {x.text}" if numbered else f"- {x.text}")
            if len(items) > limit:
                rest = items[limit:]
                kinds: dict[str, int] = {}
                for x in rest:
                    kinds[x.kind] = kinds.get(x.kind, 0) + 1
                what = ", ".join(f"{n} {k}" for k, n in kinds.items())
                out.append(
                    f"... and {len(rest)} more ({what}); fix those above and check again to "
                    "see them."
                )

        section("PROBLEMS (fix these):", self.problems, MAX_PROBLEMS, True)
        section("WARNINGS:", self.warnings, MAX_OTHERS, False)
        # the joints, cut short when long; the line saying which parts hang on them only is
        # never cut
        joints = [i for i in self.unchecked if i.kind != "held by unchecked joints"]
        held_only = [i for i in self.unchecked if i.kind == "held by unchecked joints"]
        if joints or held_only:
            out.append("")
            out.append(
                "NOT CHECKED (joints known by name only: the checker has not measured the fit; "
                "make sure each is a real one):"
            )
            out.extend(f"- {x.text}" for x in joints[:MAX_OTHERS])
            if len(joints) > MAX_OTHERS:
                kinds: dict[str, int] = {}
                for x in joints[MAX_OTHERS:]:
                    m = re.search(r": a (.+?) joint, known|join by a (.+?), known", x.text)
                    word = (m.group(1) or m.group(2)).split(" or ")[0] if m else "other"
                    kinds[word] = kinds.get(word, 0) + 1
                what = ", ".join(
                    f"{n} {w}" for w, n in sorted(kinds.items(), key=lambda kv: -kv[1])
                )
                out.append(
                    f"... and {len(joints) - MAX_OTHERS} more joints of the same sort ({what})."
                )
            out.extend(f"- {x.text}" for x in held_only)
        if self.movement:
            out.append("")
            out.append("MOVEMENT (each joint: what turns and whether it can):")
            out.extend("- " + x for x in self.movement)
        if self.placed and connections:
            out.append("")
            out.append("HOW IT HOLDS TOGETHER:")
            ground = [f"line {g}" for g in self.grounded]
            if len(ground) > 12:
                ground = ground[:12] + [f"and {len(ground) - 12} more"]
            out.append("- on the ground: " + (", ".join(ground) if ground else "nothing"))
            by_held: dict[int, list[Link]] = {}
            for link in self.links:
                by_held.setdefault(link.held, []).append(link)
            fit_held: dict[int, list[str]] = {}  # joints tested for fit: what follows "is held"
            for x in self.fits:
                fit_held.setdefault(x.lines[1], []).append(x.text.split(" is held ", 1)[1])
            if len(self.placed) <= DETAIL_PARTS:
                for p in self.placed:
                    held = by_held.get(p.line, [])
                    if not held and p.line not in fit_held:
                        continue
                    desc = "; ".join(
                        [
                            "by "
                            + f"{len(x.studs)} stud{'s' if len(x.studs) != 1 else ''} of line "
                            f"{x.holder}" + (f" ({x.how})" if x.how != "on top" else "")
                            for x in held
                        ]
                        + fit_held.get(p.line, [])
                    )
                    out.append(f"- line {p.line} is held {desc}")
            else:
                held_parts = len(by_held)
                studs = sum(len(x.studs) for x in self.links)
                side = sum(1 for x in self.links if "sideways" in x.how or "underneath" in x.how)
                out.append(
                    f"- {held_parts} parts are held by studs: {len(self.links)} connections, "
                    f"{studs} studs in all"
                    + (f", {side} of them sideways or upside down" if side else "")
                    + ". (part_info with a line number shows what holds one part.)"
                )
                single = [
                    p.line
                    for p in self.placed
                    if p.line in by_held and sum(len(x.studs) for x in by_held[p.line]) == 1
                ]
                if single:
                    shown = ", ".join(map(str, single[:30]))
                    more = f" and {len(single) - 30} more" if len(single) > 30 else ""
                    out.append(
                        f"- held by a single stud ({len(single)} parts; fine for a detail, weak "
                        f"for anything that carries others): lines {shown}{more}"
                    )
                if self.fits:
                    shown_fits = [x.text for x in self.fits[:MAX_OTHERS]]
                    more = (
                        f"; and {len(self.fits) - MAX_OTHERS} more"
                        if len(self.fits) > MAX_OTHERS
                        else ""
                    )
                    out.append(
                        f"- held on joints tested for fit ({len(self.fits)}): "
                        + "; ".join(shown_fits)
                        + more
                    )
            if self.stand_text:
                out.append("- " + self.stand_text)
        if self.placed and (self.problems or self.warnings):
            out.append("")
            out.append(ROUGH_NOTE)
        if self.fits:
            if not (self.placed and (self.problems or self.warnings)):
                out.append("")
            out.append(FIT_NOTE)
        return "\n".join(out)


# ---- parsing --------------------------------------------------------------------------------


def _is_rotation(m: np.ndarray) -> tuple[bool, float]:
    det = float(np.linalg.det(m))
    ortho = np.allclose(m.T @ m, np.eye(3), atol=0.01)
    return ortho, det


def parse(text: str, lib: Library, report: Report) -> list[Placed]:
    from bricksnap.lab.search import close_names, load_index

    placed: list[Placed] = []
    step = 0
    colours = report.colours
    lines = text.splitlines()
    report.lines_total = len(lines)
    drawing = []
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s:
            continue
        tok = s.split()
        if tok[0] == "0":
            word = tok[1].upper() if len(tok) > 1 else ""
            if word == "STEP":
                step += 1
            elif word in ("FILE", "NOFILE"):
                report.issues.append(
                    Issue(
                        "problem",
                        "format",
                        [n],
                        f"Line {n}: '0 {tok[1]}' starts another model in the same file; that is "
                        "not supported here. Write one flat model: only part lines and 0 STEP.",
                    )
                )
            continue
        if tok[0] in ("2", "3", "4", "5"):
            drawing.append(n)
            continue
        if tok[0] != "1":
            report.issues.append(
                Issue(
                    "problem",
                    "format",
                    [n],
                    f"Line {n} is not an LDraw line (it starts with '{_cut(tok[0])}'): a part "
                    "line starts with 1, a comment with 0.",
                )
            )
            continue
        if len(tok) < 15:
            report.issues.append(
                Issue(
                    "problem",
                    "format",
                    [n],
                    f"Line {n} has {len(tok) - 1} items after the 1; a part line needs 14: colour, "
                    "x y z, the nine numbers of the rotation matrix, and the file name.",
                )
            )
            continue
        try:
            colour = int(tok[1], 0)
        except ValueError:
            report.issues.append(
                Issue(
                    "problem",
                    "format",
                    [n],
                    f"Line {n}: the colour '{_cut(tok[1])}' is not a number.",
                )
            )
            continue
        try:
            nums = [float(v) for v in tok[2:14]]
        except ValueError:
            bad = next(v for v in tok[2:14] if not _is_float(v))
            report.issues.append(
                Issue(
                    "problem",
                    "format",
                    [n],
                    f"Line {n}: '{_cut(bad)}' is not a number (the 12 items after the colour are "
                    "x y z and the rotation matrix).",
                )
            )
            continue
        name = " ".join(tok[14:])
        found = lib.resolve(name)
        if found is None and not norm_name(name).endswith(".dat"):
            found = lib.resolve(name + ".dat")
            if found is not None:
                report.issues.append(
                    Issue(
                        "warning",
                        "format",
                        [n],
                        f"Line {n}: write the file name with .dat: {name}.dat.",
                    )
                )
        if found is None:
            close = close_names(name)
            idx = load_index()
            spaced = re.sub(r"(\d)\s*x\s*(\d)", r"\1 x \2", norm_name(name).removesuffix(".dat"))
            spaced = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-wyz])", " ", spaced)
            if re.search(r"[a-z]{3,}", spaced):
                close = [h.name for h in idx.search(spaced, 3)] + close
            close = list(dict.fromkeys(close))[:5]
            hint = "; ".join(
                f"{c} ({idx.by_name[c]['description']})" for c in close if c in idx.by_name
            )
            report.issues.append(
                Issue(
                    "problem",
                    "unknown part",
                    [n],
                    f"Line {n}: there is no part '{_cut(name)}' in the library."
                    + (f" Close names: {hint}." if hint else "")
                    + " Use search_parts to find the part you mean.",
                )
            )
            continue
        kind, key = found
        if kind != "part":
            report.issues.append(
                Issue(
                    "problem",
                    "not a part",
                    [n],
                    f"Line {n}: '{_cut(name)}' is a "
                    f"{'sub-part' if kind == 'subpart' else 'primitive'} "
                    "(a piece of some part's drawing), not a part you can build with.",
                )
            )
            continue
        part = lib.part(key)
        m = np.array(nums[3:12]).reshape(3, 3)
        pos = np.array(nums[0:3])
        ortho, det = _is_rotation(m)
        where = " ".join(fmt(v) for v in pos)
        if not ortho:
            report.issues.append(
                Issue(
                    "problem",
                    "matrix",
                    [n],
                    f"Line {n} ({key} at {where}): the nine numbers "
                    f"{' '.join(fmt(v) for v in nums[3:12])} are not a rotation (each row must "
                    "have "
                    "length 1 and the rows must be at right angles; a real part cannot be "
                    "stretched). Upright is 1 0 0 0 1 0 0 0 1.",
                )
            )
            if abs(det) < 1e-6:
                continue
        elif det < 0:
            report.issues.append(
                Issue(
                    "problem",
                    "mirrored",
                    [n],
                    f"Line {n} ({key} at {where}): the matrix mirrors the part (its determinant is "
                    "-1); a real part cannot be mirrored. For a left/right pair use the part's "
                    "left or right version.",
                )
            )
        desc = part.description
        if desc.startswith("~Moved to"):
            report.issues.append(
                Issue(
                    "warning",
                    "moved",
                    [n],
                    f"Line {n}: {key} is an old number; the library says '{desc}'. It is drawn, "
                    "but use the new number.",
                )
            )
        if colour in (16, 24):
            report.issues.append(
                Issue(
                    "warning",
                    "colour",
                    [n],
                    f"Line {n} ({key}): colour {colour} means 'the colour of the enclosing model' "
                    "and is drawn grey or black; give the part a real colour.",
                )
            )
        elif colours and colour not in colours and not 0x2000000 <= colour <= 0x2FFFFFF:
            report.issues.append(
                Issue(
                    "warning",
                    "colour",
                    [n],
                    f"Line {n} ({key}): {colour} is not an LDraw colour code.",
                )
            )
        inv = np.linalg.inv(m)
        placed.append(Placed(n, colour, pos, m, name, key, part, step, inv))
    if drawing:
        report.issues.append(
            Issue(
                "warning",
                "format",
                drawing[:5],
                f"Line{'s' if len(drawing) > 1 else ''} {', '.join(map(str, drawing[:8]))}"
                f"{' ...' if len(drawing) > 8 else ''}: drawing lines (types 2 to 5) are ignored; "
                "only parts (type 1) count.",
            )
        )
    return placed


def _is_float(v: str) -> bool:
    try:
        float(v)
    except ValueError:
        return False
    return True


def _cut(text: str, n: int = 60) -> str:
    text = re.sub(r"[\x00-\x1f]", " ", text)
    return text if len(text) <= n else text[: n - 3] + "..."


# ---- geometry helpers -----------------------------------------------------------------------


def numbered_studs(part: Part) -> list[Connector]:
    """The part's studs in the order part_info numbers them: those on top first, row by row
    from the front (-z) and left to right (-x to +x); then the others by direction."""
    top = sorted(part.top_studs(), key=lambda s: (round(s.pos[2], 1), round(s.pos[0], 1), s.pos[1]))
    rest = [s for s in part.studs if s.axis[1] >= -0.99]
    rest.sort(
        key=lambda s: (
            direction_word(s.axis),
            round(s.pos[1], 1),
            round(s.pos[2], 1),
            round(s.pos[0], 1),
        )
    )
    return top + rest


def _perp(d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    u = np.cross(d, a)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return u, v


def _stud_probe(base: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Points 2 LDU up a stud: its centre and four points 4 LDU out from it."""
    u, v = _perp(d)
    c = base + 2 * d
    return np.array([c, c + 4 * u, c - 4 * u, c + 4 * v, c - 4 * v])


@dataclass
class _StudHit:
    stud: int  # 1-based number on the holder
    ok: bool
    how: str
    reason: str = ""
    move: np.ndarray | None = None  # world move of the held part that would fix it
    # not a stud joint but one the checker cannot confirm: a bar of the held part in this
    # open stud, or this stud in a pin hole of the held part (what to call it, and the two
    # ends of the hollow's axis, world)
    joint: tuple[str, np.ndarray] | None = None


# ---- a bar in a hollow ------------------------------------------------------------------------

# Where a bar can go in, by connector: (what the report calls it, how far along its axis the
# hollow is looked at, in LDU from the connector's own reach). An open stud's hollow is the
# stud itself (0.5 to 3.5 LDU out from its base); an open tube's is the tube (0.5 to 3.5 LDU
# in from its end); a hole's or a pin's is the primitive's own reach, 1 LDU more at each end.
_HOLLOW_WORDS = {
    "bar tube": "bar in a bar tube",
    "open stud": "bar in an open stud",
    "tube": "bar in a tube",
    "axle hole": "bar in an axle hole",
    "pin hole": "bar in a pin hole (a loose fit)",
    "pin": "bar in a pin's end",
}
AXLE_DEG = 5.0
AXLE_LDU = 1.5
AXLE_IN = 0.5  # LDU the hole's own reach and the axle's length must share
AXLE_HOLE_PRIM = re.compile(r"^axl")  # axle-hole primitives (an axle drawn as one)
BAR_RING = 5.0  # LDU: a bar is 4 LDU in radius; nothing of the held part may be this far out
BAR_TUBE = 3.0  # LDU: a bar drawn as a tube fills a ring of this radius round the axis
BAR_OFF = 1.0  # LDU: the middle of the bar's cross-section may be this far from the axis
BAR_DEG = 4.0  # degrees a bar may lean from the hollow's axis (measured to about 1)
BAR_PLAY = 1.0  # LDU a bar may stop short of a hollow's full depth (as a stud's SEAT_TOL)
BAR_DEPTH = 4.0  # LDU: the depth asked of a longer hollow (an open stud's own depth)
BAR_LEAN = 16.0  # LDU of the bar, from the hollow's inner end outwards, that must be centred
_RING = np.array([[math.cos(a), math.sin(a)] for a in np.linspace(0, 2 * math.pi, 8, False)])
_DISC = np.array(  # a cross-section round the axis, on a 0.5 LDU grid out to 5.5 LDU
    [
        [x, y]
        for x in np.arange(-5.25, 5.3, 0.5)
        for y in np.arange(-5.25, 5.3, 0.5)
        if x * x + y * y <= 5.5 * 5.5
    ]
)


@dataclass
class _Hollow:
    kind: str  # "open stud", "tube", "axle hole", "pin hole", "pin", "bar tube"
    p0: np.ndarray  # one end of its axis (world)
    p1: np.ndarray  # the other end


def _hollows(p: Placed, connectors: list[Connector]) -> list[_Hollow]:
    """The hollows among ``connectors`` of ``p`` that a bar can go into, each with the two
    ends of its axis: an open stud from its base to its tip (4 LDU), an open tube from its
    open end to its closed one, a hole or a pin's bore along the primitive's own reach (a
    through hole drawn as one primitive at each face is one hole, end to end)."""
    out: list[_Hollow] = []
    holes: list[_Hollow] = []  # in the part's own frame until merged
    for c in connectors:
        if c.kind == "stud" and OPEN_STUD.match(c.prim):
            base = p.to_world(c.pos)
            tip = p.to_world(c.pos + 4.0 * c.axis)
            out.append(_Hollow("open stud", base, tip))
        elif c.kind == "tube" and c.open and c.end is not None:
            if float(np.linalg.norm(c.pos - c.end)) > 1e-9:
                out.append(_Hollow("tube", p.to_world(c.end), p.to_world(c.pos)))
        elif c.kind in ("axle hole", "pin hole", "pin"):
            a, b = c.along
            if b - a > 1e-9:
                holes.append(_Hollow(c.kind, c.pos + a * c.axis, c.pos + b * c.axis))
    # a through hole is drawn as one primitive at each face: holes of one kind on one line
    # are one hole, from the first end to the last
    while holes:
        h = holes.pop(0)
        d = (h.p1 - h.p0) / float(np.linalg.norm(h.p1 - h.p0))
        same = [
            g
            for g in holes
            if g.kind == h.kind
            and abs(float(np.dot(d, (g.p1 - g.p0) / float(np.linalg.norm(g.p1 - g.p0))))) > 0.999
            and all(
                float(np.linalg.norm((q - h.p0) - float(np.dot(q - h.p0, d)) * d)) < 0.5
                for q in (g.p0, g.p1)
            )
        ]
        holes = [g for g in holes if not any(g is x for x in same)]
        ts = [float(np.dot(q - h.p0, d)) for g in (h, *same) for q in (g.p0, g.p1)]
        out.append(_Hollow(h.kind, p.to_world(h.p0 + min(ts) * d), p.to_world(h.p0 + max(ts) * d)))
    order = ("open stud", "axle hole", "pin", "pin hole", "tube")
    return sorted(out, key=lambda h: order.index(h.kind))


_TUBES: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}


def _tube_hollows(p: Placed) -> list[_Hollow]:
    """The bore of a part its name calls a "Bar Tube" (23443 with a handle, 11090 with a clip:
    the library draws no primitive for it), found in its real shape: along each of its own
    axes, through the middle of its box, from an end inwards while the axis is empty and a
    wall stands round it (6 of 8 points 5 LDU out solid), from within 2 LDU of the end to the
    first solid on the axis; at least ``BAR_DEPTH`` deep. A bar in it is judged as in any
    hollow (``_bar_fits``)."""
    if "bar tube" not in p.part.description.lower():
        return []
    if p.key not in _TUBES:
        from bricksnap.lab import solid

        sol = solid.solid(p.key)
        lo, hi = p.part.bbox_min, p.part.bbox_max
        mid = (lo + hi) / 2
        found: list[tuple[np.ndarray, np.ndarray]] = []
        for k in range(3):
            u, v = np.eye(3)[[j for j in range(3) if j != k]]
            for start, step in ((hi[k], -0.5), (lo[k], 0.5)):
                inside = []
                t = start
                while (step < 0 and t > lo[k]) or (step > 0 and t < hi[k]):
                    x = mid.copy()
                    x[k] = t
                    ring = x + 5.0 * (_RING[:, 0:1] * u + _RING[:, 1:2] * v)
                    empty = not sol.inside(x[None, :], deep=False).any()
                    wall = int(sol.inside(ring, deep=False).sum()) >= 6
                    if not empty or (not wall and inside):
                        break
                    if wall:
                        inside.append(t)
                    elif abs(t - start) > 2:
                        break
                    t += step
                if inside and abs(inside[-1] - inside[0]) >= BAR_DEPTH:
                    a, b = mid.copy(), mid.copy()
                    a[k], b[k] = start, inside[-1]
                    found.append((a, b))
        _TUBES[p.key] = found
    return [_Hollow("bar tube", p.to_world(a), p.to_world(b)) for a, b in _TUBES[p.key]]


def _bar_fits(h: _Hollow, held: Placed) -> bool:
    """Is a bar of ``held`` in hollow ``h``, coming in at one of its ends (see ``_bar_in``)?"""
    from bricksnap.lab import solid

    sb = solid.solid(held.key)
    axis = h.p1 - h.p0
    length = float(np.linalg.norm(axis))
    if length < 1e-9:
        return False
    d = axis / length
    u, v = _perp(d)
    ring = _RING[:, 0:1] * u + _RING[:, 1:2] * v
    need = min(length, BAR_DEPTH) - BAR_PLAY
    for start, sign in ((h.p1, -1.0), (h.p0, 1.0)):
        # from 1 LDU outside this end (the bar comes in from outside) inwards to the far end;
        # coming in through a closed end means going through the part's material, which the
        # real shapes then show (``_bar_in``)
        t_in = np.arange(-1.0, length + 0.01, 0.5)
        pts = start + sign * np.outer(t_in, d)  # going in
        local = held.to_local(pts)
        # the bar is there when it is on the axis, or when it is a tube of bar size round it
        # (6 of 8 points BAR_TUBE out from the axis inside it, as a bar end drawn hollow)
        on = sb.inside(local, deep=False) | (
            sb.inside(held.to_local((pts[:, None, :] + BAR_TUBE * ring).reshape(-1, 3)), deep=False)
            .reshape(len(pts), len(_RING))
            .sum(1)
            >= 6
        )
        thick = sb.inside(
            held.to_local((pts[:, None, :] + BAR_RING * ring).reshape(-1, 3)), deep=False
        )
        wide = thick.reshape(len(pts), len(_RING)).any(1)
        k = 0
        while k < len(on) and on[k]:
            k += 1
        within = (t_in >= 0) & (np.arange(len(t_in)) < k)  # its stretch inside the hollow
        # thicker than a bar anywhere inside, leaving half a voxel's play at the mouth (where
        # what the bar belongs to may sit on the hollow's rim)
        if wide[within & (t_in >= 0.75)].any():
            continue  # thicker than a bar somewhere inside the hollow
        if not within.any():
            continue
        depth = float(t_in[within].max())
        if depth < need - 1e-9:
            continue  # not in far enough (or floating above the hollow)
        # along the hollow's axis: from its inner end outwards for BAR_LEAN LDU, as long as
        # the held part is on the axis and still a bar (not its wider body, which fills most
        # of the ring round the axis), the middle of its cross-section stays within
        # BAR_OFF of the axis and its line leans no more than BAR_DEG from it
        t_out = np.arange(0.0, BAR_LEAN + 0.01, 0.5)
        line = start + sign * np.outer(depth - t_out, d)
        on_out = sb.inside(held.to_local(line), deep=False) | (
            sb.inside(
                held.to_local((line[:, None, :] + BAR_TUBE * ring).reshape(-1, 3)), deep=False
            )
            .reshape(len(line), len(_RING))
            .sum(1)
            >= 6
        )
        ring_in = sb.inside(
            held.to_local((line[:, None, :] + BAR_RING * ring).reshape(-1, 3)), deep=False
        ).reshape(len(line), len(_RING))
        n = 0
        while n < len(line) and on_out[n] and int(ring_in[n].sum()) < 3:
            n += 1
        disc = _DISC[:, 0:1] * u + _DISC[:, 1:2] * v  # (m, 3)
        cut = sb.inside(
            held.to_local((line[:n, None, :] + disc[None]).reshape(-1, 3)), deep=False
        ).reshape(n, len(_DISC))
        # the bar's very end (the first half LDU) is left out: its face is cut obliquely
        some = cut.sum(1) > 0
        some[:1] = False
        mids_all = np.array([_DISC[c].mean(0) for c in cut[some]]).reshape(-1, 2)
        if len(mids_all) and float(np.linalg.norm(mids_all, axis=1).max()) > BAR_OFF:
            continue  # off the axis
        # the lean, from whole cross-sections only
        full = some & (cut.sum(1) >= 0.8 * max(int(cut.sum(1).max()) if n else 0, 1))
        mids = np.array([_DISC[c].mean(0) for c in cut[full]]).reshape(-1, 2)
        if len(mids) >= 9:  # 4 LDU or more of bar to measure a lean on
            tt = t_out[:n][full] - t_out[:n][full].mean()
            slope = (tt @ (mids - mids.mean(0))) / float(tt @ tt)
            if float(np.linalg.norm(slope)) > math.tan(math.radians(BAR_DEG)):
                continue  # leaning
        return True
    return False


def _bar_goes_on(bar: Placed, other: Placed, ends: np.ndarray) -> bool:
    """Does the bar of ``bar``, held in a hollow whose axis runs between ``ends``, go on past
    an end of that hollow into ``other``: 1.5 LDU or more of its line, where it is still
    bar-thin, deep inside ``other``'s real solid?"""
    from bricksnap.lab import solid

    sb, so = solid.solid(bar.key), solid.solid(other.key)
    d = ends[1] - ends[0]
    n = float(np.linalg.norm(d))
    if n < 1e-9:
        return False
    d = d / n
    u, v = _perp(d)
    ring = _RING[:, 0:1] * u + _RING[:, 1:2] * v
    t = np.arange(0.5, 30.01, 0.5)
    for end, sign in ((ends[1], 1.0), (ends[0], -1.0)):
        line = end + sign * np.outer(t, d)
        thin = sb.inside(bar.to_local(line), deep=True) & ~sb.inside(
            bar.to_local((line[:, None, :] + BAR_RING * ring).reshape(-1, 3)), deep=False
        ).reshape(len(line), len(_RING)).any(1)
        into = thin & so.inside(other.to_local(line), deep=True)
        run = 0
        for k in range(len(line)):
            if not thin[k] and not into[k]:
                break  # the bar ends (or widens): stop looking
            run = run + 1 if into[k] else 0
            if run >= 4:
                return True
    return False


def _held_bar(
    a: Placed, b: Placed, held: dict[int, np.ndarray]
) -> tuple[str, np.ndarray, int, int] | None:
    """A bar of b in a hollow of a, or of a in b (see ``_bar_in``): its name, the hollow's
    axis, the hollow's line and the bar's line; the bar's line and the hollow's axis go into
    ``held``."""
    for holder, bar in ((a, b), (b, a)):
        got = _bar_in(holder, bar)
        if got is not None:
            held[bar.line] = got[1]
            return (*got, holder.line, bar.line)
    return None


def _bar_in(
    holder: Placed, held: Placed, connectors: list[Connector] | None = None
) -> tuple[str, np.ndarray] | None:
    """Is a bar of ``held`` in a hollow of ``holder`` (an open stud, an open tube, an axle
    hole, a pin hole, the hollow end of a pin)? See the contract. In short: from 1 LDU outside
    one end of the hollow inwards the held part is on the axis without a break, nowhere inside
    the hollow reaching the ring ``BAR_RING`` round the axis (no thicker than a bar), for at
    least the hollow's depth (``BAR_DEPTH`` for a longer one) less ``BAR_PLAY``; from its
    inner end outwards for ``BAR_LEAN`` LDU, while it is still a bar, the middle of its
    cross-section stays within ``BAR_OFF`` of the axis and its line within ``BAR_DEG`` of it;
    and the real shapes share nothing more than touching outside the hollow's own space (the
    cylinder of ``BAR_RING`` round the axis between the hollow's two ends), so a bar that
    comes in through a closed end, or goes on into the part's material, is no joint. Returns
    what the report calls the joint and the two ends of the hollow's axis (world), or None."""
    from bricksnap.lab import solid

    hollows = _hollows(holder, holder.part.connectors if connectors is None else connectors)
    hollows += _tube_hollows(holder)
    if not hollows:
        return None
    blo, bhi = solid.solid(held.key).box()
    for h in hollows:
        local = held.to_local(np.array([h.p0, h.p1, (h.p0 + h.p1) / 2]))
        if not np.any(np.all((local >= blo - 2) & (local <= bhi + 2), axis=1)):
            continue
        if not _bar_fits(h, held):
            continue
        ends = np.array([h.p0, h.p1])
        if _really_overlap(holder, held, ends):
            continue  # it fits the hollow but goes on into the part's material
        return _HOLLOW_WORDS[h.kind], ends
    return None


_GRIDS: dict[str, tuple[float, float]] = {}


def stud_grid(part: Part) -> tuple[float, float]:
    """x and z (mod 20) of the centres of the stud cells a stud must sit on, in the part's
    own frame. ``Part.socket_phase`` (by which ``place`` numbers sockets), except for a part
    with no studs on top whose box is not whole studs along x or z (a curved slope with a
    cutout, a slope with an overhang): the library draws parts on the stud grid round their
    origin, so along that axis its cells line up with the end of its box that is on that
    grid (a multiple of 10 LDU from the origin), not with the end the cutout or the overhang
    moves; when both ends or neither are, ``socket_phase`` stands."""
    got = _GRIDS.get(part.name)
    if got is not None:
        return got
    phase = list(part.socket_phase())
    if part.has_body() and not part.top_studs():
        lo, hi = part.bbox_min, part.bbox_max
        for k, axis in ((0, 0), (1, 2)):
            span = float(hi[axis] - lo[axis])
            if abs(span / 20 - round(span / 20)) < 0.05:
                continue
            ends = [
                round(float(e + sign * 10) % 20 * 2) / 2 % 20
                for e, sign in ((lo[axis], 1), (hi[axis], -1))
                if abs(e / 10 - round(e / 10)) < 0.05
            ]
            if len(ends) == 1:
                phase[k] = ends[0]
    got = (phase[0], phase[1])
    _GRIDS[part.name] = got
    return got


def _stud_hits(a: Placed, b: Placed) -> list[_StudHit]:
    """What each stud of ``a`` does to ``b``."""
    out: list[_StudHit] = []
    studs = numbered_studs(a.part)
    if not studs or not b.part.has_body():
        return out
    phase = stud_grid(b.part)
    for k, s in enumerate(studs, 1):
        base_w = a.to_world(s.pos)
        d_w = a.m @ s.axis
        d_w /= np.linalg.norm(d_w)
        base_b = b.to_local(base_w)
        d_b = b.dir_local(d_w)
        how = _how(d_w)
        # a stud inside an open tube or ring of b
        in_tube = False
        for t in b.part.tubes:
            if not t.open or t.end is None:
                continue
            if float(np.dot(d_b, t.axis)) > -0.98:
                continue
            off = base_b - t.end
            along = float(np.dot(off, t.axis))
            across = float(np.linalg.norm(off - along * t.axis))
            if across < GRID_TOL and abs(along) <= SEAT_TOL + 0.5:
                in_tube = True
                break
        if in_tube:
            out.append(_StudHit(k, True, "in a tube" if how == "on top" else how + ", in a tube"))
            continue
        probe = _stud_probe(base_b, d_b)
        inside = b.part.inside(probe, tol=0.25)
        if not inside.any():
            continue
        # a bar of b in this open stud, or in another hollow of a it goes on into
        joint = _bar_in(a, b) if OPEN_STUD.match(s.prim) else None
        if joint is None and float(np.dot(d_b, UP)) < 0.98:
            joint = _stud_in_pin_hole(base_w, d_w, b)
        if joint is not None:
            out.append(_StudHit(k, False, how, joint=joint))
            continue
        if float(np.dot(d_b, UP)) >= 0.98 and not b.part.has_sockets():
            out.append(
                _StudHit(
                    k,
                    False,
                    how,
                    f"push into line {b.line}, which has no sockets underneath (it cannot sit "
                    "on studs), so the two parts collide",
                )
            )
            continue
        if float(np.dot(d_b, UP)) < 0.98:
            out.append(
                _StudHit(
                    k,
                    False,
                    how,
                    f"push into the side or top of line {b.line} (that part is not turned to take "
                    "a stud there: a stud goes into the underside of a part)",
                )
            )
            continue
        bottoms = [b.part.bottom_at(float(p[0]), float(p[2])) for p in probe]
        bottoms = [x for x in bottoms if x is not None]
        bottom = max(bottoms) if bottoms else float(base_b[1])
        dy = float(base_b[1]) - bottom  # >0: the stud's base is below b's bottom (a gap)
        ox = ((float(base_b[0]) - phase[0] + 10) % 20) - 10
        oz = ((float(base_b[2]) - phase[1] + 10) % 20) - 10
        if abs(ox) > GRID_TOL or abs(oz) > GRID_TOL:
            move = b.m @ np.array([ox, 0.0, oz])
            out.append(
                _StudHit(
                    k,
                    False,
                    how,
                    f"miss the stud grid of line {b.line}: {fmt(abs(ox))} LDU off in "
                    f"that part's x and {fmt(abs(oz))} LDU off in its z (a stud cell is 20 LDU; 10 "
                    "is half a stud), so they hit a wall instead of a socket",
                    move,
                )
            )
            continue
        if dy < -SEAT_TOL:
            move = d_w * (-dy)
            out.append(
                _StudHit(
                    k,
                    False,
                    how,
                    f"go {fmt(-dy)} LDU too far into line {b.line} (the parts overlap)",
                    move,
                )
            )
            continue
        if dy > SEAT_TOL:
            move = -d_w * dy
            out.append(
                _StudHit(
                    k,
                    False,
                    how,
                    f"are not pressed home into line {b.line}: there is a gap of {fmt(dy)} LDU",
                    move,
                )
            )
            continue
        if not b.part.is_socket(float(base_b[0]), float(base_b[2]), float(base_b[1])):
            out.append(
                _StudHit(
                    k,
                    False,
                    how,
                    f"press against the underside of line {b.line} where it has no socket (no "
                    "flat hollow for a stud there)",
                )
            )
            continue
        out.append(_StudHit(k, True, how))
    return out


def _stud_in_pin_hole(base: np.ndarray, d: np.ndarray, b: Placed) -> tuple[str, np.ndarray] | None:
    """Is a stud (its base and direction, world) in a pin hole of b: pointing along the
    hole's axis (within ``AXLE_DEG`` degrees), its base within ``AXLE_LDU`` LDU of the
    axis and within 2 LDU of the hole's own reach? A stud fits a Technic pin hole."""
    cos = math.cos(math.radians(AXLE_DEG))
    for h in b.part.others:
        if h.kind != "pin hole":
            continue
        ax = b.m @ h.axis
        if abs(float(np.dot(d, ax))) < cos:
            continue
        w = base - b.to_world(h.pos)
        t = float(np.dot(w, ax))
        lo, hi = sorted(h.along)
        if lo - 2 <= t <= hi + 2 and float(np.linalg.norm(w - t * ax)) <= AXLE_LDU:
            return "stud in a pin hole", np.array([base, base + 4 * d])
    return None


def _pin_hole_key(b: Placed, base: np.ndarray, d: np.ndarray) -> tuple[float, ...]:
    """Which hole of b a stud (base, direction, world) is in: the hole's line in b's frame
    (a through hole is drawn as one primitive at each face; both are the same hole)."""
    a = b.dir_local(d)
    k = int(np.argmax(np.abs(a)))
    if a[k] < 0:
        a = -a
    p = b.to_local(base)
    p = p - float(np.dot(p, a)) * a
    return (*np.round(p).tolist(), *np.round(a, 1).tolist())


def _how(d_w: np.ndarray) -> str:
    if d_w[1] < -0.98:
        return "on top"
    if d_w[1] > 0.98:
        return "underneath"
    return "sideways"


def _world_bbox(p: Placed, grow: float) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = p.part.bbox_min.copy(), p.part.bbox_max.copy()
    if p.part.studs:
        sp = np.array([s.pos for s in p.part.studs])
        lo = np.minimum(lo, sp.min(0) - 6)
        hi = np.maximum(hi, sp.max(0) + 6)
    corners = np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )
    w = p.to_world(corners)
    return w.min(0) - grow, w.max(0) + grow


def _really_overlap(a: Placed, b: Placed, bar_axis: np.ndarray | None = None) -> bool:
    """The rough filled bodies of a and b overlap: do their real shapes (``solid``, with
    studs) go into each other deeper than touching or a seated stud does? With ``bar_axis``
    (the two ends of a hollow's axis that a bar of one is in), what they share within
    ``BAR_RING`` LDU of that axis is the bar's fit in its hollow and does not count."""
    from bricksnap.lab import solid

    keep = None if bar_axis is None else (bar_axis[0], bar_axis[1], BAR_RING)
    return solid.in_the_way((a.key, a.pos, a.m), (b.key, b.pos, b.m), apart=keep)


def _overlap(a: Placed, b: Placed) -> tuple[float, np.ndarray | None]:
    """Volume of a inside b (LDU^3) and the world box of the shared points."""
    pts, w = a.part.samples()
    if not len(pts):
        return 0.0, None
    world = a.to_world(pts)
    inside = b.part.inside(b.to_local(world))
    if not inside.any():
        return 0.0, None
    shared = world[inside]
    return float(w[inside].sum()), np.array([shared.min(0) - 2, shared.max(0) + 2])


# Each joint has two ends that fit each other. A part's ends come from its connector
# primitives (only those near the other part) or, for a family its geometry does not show,
# from its name.
_GEO_END = {
    "pin": "pin+",
    "pin hole": "pin-",
    "axle": "axle+",
    "axle hole": "axle-",
    "wheel pin": "wheel+",
    "wheel hole": "wheel-",
    "clip": "bar-",
    "bar handle": "bar+",
    "hinge": "hinge",
    "ball": "ball+",
    "ball socket": "ball-",
}
_NAME_END = {
    "bar": "bar+",
    "bars": "bar+",
    "handle": "bar+",
    "handles": "bar+",
    "antenna": "bar+",
    "lever": "bar+",
    "clip": "bar-",
    "clips": "bar-",
    "flag": "bar-",
    "tyre": "tyre",
    "tire": "tyre",
    "wheel": "rim",
    "wheels": "rim",
    "pin": "pin+",
    "pins": "pin+",
    "axle": "axle+",
    "axles": "axle+",
    "hinge": "hinge",
    "click": "hinge",
    "ball": "ball+",
    "towball": "ball+",
    "socket": "ball-",
    "turntable": "turntable",
}
_FITS = [
    ("pin+", "pin-"),
    ("axle+", "axle-"),
    ("axle+", "pin-"),
    ("pin+", "axle-"),
    ("wheel+", "wheel-"),
    ("wheel+", "rim"),
    ("tyre", "rim"),
    ("tyre", "wheel-"),
    ("wheel+", "tyre"),
    ("bar+", "bar-"),
    ("hinge", "hinge"),
    ("ball+", "ball-"),
    ("turntable", "turntable"),
]
_END_WORDS = {
    "pin": "Technic pin",
    "axle": "axle",
    "wheel": "wheel pin",
    "tyre": "tyre on a wheel",
    "bar": "bar in a clip",
    "hinge": "hinge",
    "ball": "ball joint",
    "turntable": "turntable",
}
_NEAR = np.array(
    [[0, 0, 0], [8, 0, 0], [-8, 0, 0], [0, 8, 0], [0, -8, 0], [0, 0, 8], [0, 0, -8]], dtype=float
)


def _ends(p: Placed, q: Placed, region: np.ndarray | None) -> set[str]:
    """The joint ends of p that could meet q: its connectors within 8 LDU of q (or of
    ``region``), and the ends its name gives for families its geometry does not show."""
    ends: set[str] = set()
    for c in p.part.others:
        end = _GEO_END.get(c.kind)
        if end is None:
            continue
        # an axle along its whole length, a handle along its bar (not along the primitive's
        # own axis, which is across the bar); other connectors at their own place
        if c.kind == "bar handle":
            w = np.concatenate(
                [np.linspace(e0, e1, 9) for e0, e1 in _handle_bars(p)]
                or [p.to_world(c.pos[None, :])]
            )
        else:
            w = p.to_world(c.points() if c.kind == "axle" else c.pos[None, :])
        if region is not None:
            gap = np.maximum(np.maximum(region[0] - w, w - region[1]), 0)
            if float(np.linalg.norm(gap, axis=1).min()) <= 8:
                ends.add(end)
        elif q.part.inside(
            q.to_local((w[:, None, :] + _NEAR[None]).reshape(-1, 3)), tol=-0.5
        ).any():
            ends.add(end)
    geo_ends = {_GEO_END[c.kind] for c in p.part.others if c.kind in _GEO_END}
    families = {e.rstrip("+-") for e in geo_ends}
    desc = p.part.description.lower()
    for word in p.part.name_joint_words():
        end = _NAME_END.get(word)
        if word == "bar" and "bar tube" in desc:
            end = "bar-"  # a "Bar Tube" is a tube a bar goes into, not a bar
        if end is None:
            continue
        if end.startswith("bar") and end not in geo_ends:
            pass  # a clip of its own does not make a part's bar, bar tube or handle not one
        elif end.rstrip("+-") in families:
            continue
        if end == "rim" and not desc.startswith("wheel"):
            continue  # "Plate with Wheel Pins" is not a wheel
        if end in ("pin+", "axle+") and families:
            continue  # its pins and axles would be in its geometry
        ends.add(end)
    return ends


def _joint_words(a: Placed, b: Placed, region: np.ndarray | None) -> list[str]:
    """The joints other than studs that may join a and b: one end on each part that fit each
    other (a pin and a pin hole, a bar and a clip, a tyre and a wheel...), each near the other
    part (near ``region``, where they overlap, when given)."""
    ea, eb = _ends(a, b, region), _ends(b, a, region)
    found = []
    for x, y in _FITS:
        if (x in ea and y in eb) or (y in ea and x in eb):
            if x == "axle+" and not any(
                _axle_in_hole(p, q) for p, q in ((a, b), (b, a)) if x in _ends(p, q, region)
            ):
                continue
            if x == "wheel+" and not any(
                _wheel_on_pin(p, q) for p, q in ((a, b), (b, a)) if x in _ends(p, q, region)
            ):
                continue  # a wheel pin must be in the wheel's hole, on its line
            if x == "tyre" and not any(
                _tyre_on_wheel(p, q) for p, q in ((a, b), (b, a)) if x in _ends(p, q, region)
            ):
                continue  # a tyre must sit round its wheel, on its line
            if x == "bar+" and not _clip_at_bar(a, b):
                continue  # a clip must be at a handle's bar, not just near the handle
            word = _END_WORDS[x.rstrip("+-")]
            if word not in found:
                found.append(word)
    return found


def _axle_in_hole(p: Placed, q: Placed) -> bool:
    """Can an axle of p be in a hole of q? True unless p's axles are all ones the library
    draws with axle-hole primitives (``ldraw_lib``: a part named "Technic Axle ..."): those
    must run along an axle hole or pin hole of q, their lines parallel within
    ``AXLE_DEG`` degrees and within ``AXLE_LDU`` LDU of each other, the hole's own reach
    and the axle's length sharing ``AXLE_IN`` LDU or more (an axle that misses its hole, or
    ends before it, is not a joint)."""
    drawn = [c for c in p.part.others if c.kind == "axle"]
    if not drawn or any(not AXLE_HOLE_PRIM.match(c.prim) for c in drawn):
        return True
    holes = [c for c in q.part.others if c.kind in ("axle hole", "pin hole")]
    cos = math.cos(math.radians(AXLE_DEG))
    for c in drawn:
        d = p.m @ c.axis
        o = p.to_world(c.pos)
        lo, hi = sorted(c.along)
        for h in holes:
            hd = q.m @ h.axis
            if abs(float(np.dot(d, hd))) < cos:
                continue
            w = q.to_world(h.pos) - o
            t = float(np.dot(w, d))
            if float(np.linalg.norm(w - t * d)) > AXLE_LDU:
                continue
            # the hole's own reach, along the axle, must overlap the axle's length
            ha = sorted(t + float(np.dot(hd, d)) * np.array(h.along))
            if min(hi, ha[1]) - max(lo, ha[0]) >= AXLE_IN:
                return True
    return False


# ---- joints tested for fit -------------------------------------------------------------------

PIN_PLAY = 2.0  # LDU a Technic pin may stop short of the shorter of itself and its hole (75892: 2)


def _share_on_line(
    o1: np.ndarray,
    d1: np.ndarray,
    r1: tuple[float, float],
    o2: np.ndarray,
    d2: np.ndarray,
    r2: tuple[float, float],
) -> float | None:
    """How much two lines' reaches share when they run along each other (parallel within
    ``AXLE_DEG``, within ``AXLE_LDU``: the test of ``_lines_meet``); None when they do not."""
    if abs(float(np.dot(d1, d2))) < math.cos(math.radians(AXLE_DEG)):
        return None
    w = o2 - o1
    t = float(np.dot(w, d1))
    if float(np.linalg.norm(w - t * d1)) > AXLE_LDU:
        return None
    a1 = sorted(r1)
    a2 = sorted(t + float(np.dot(d2, d1)) * np.array(r2))
    return min(a1[1], a2[1]) - max(a1[0], a2[0])


def _wheel_pin_fit(p: Placed, q: Placed) -> tuple[float, float] | None:
    """A wheel pin of p measured in q's wheel (the deep test of ``_wheel_pin_in``): in a hole
    at least ``HOLE_SHORT`` long, else on the axis of a round box (``_box_axis``) with half
    the wheel's width as its hub: (how far it is in, how far it must be); None when it is
    not, or nothing can be measured: a pin known by name, a wheel whose line comes only from
    its real shape (``_body_axis``: good enough to accept the joint, not to measure its fit),
    or q a tyre (the pin is in the wheel, not in its tyre)."""
    pins = [c for c in p.part.others if c.kind == "wheel pin"]
    if not pins or ("tyre" in q.part.name_joint_words() and not _both_wheel_and_tyre(q)):
        return None
    lines, hub = _measured_holes(q), 1.0
    box = _box_axis(q)
    if not lines and box is not None:  # no hole: its box's axis, with half its width as hub
        lines, hub = [(box[0], box[1], box[2])], 0.5
    best = None
    for c in pins:
        for o, d, r in lines:
            got = _share_on_line(p.to_world(c.pos), p.m @ c.axis, c.along, o, d, r)
            need = min(abs(c.along[1] - c.along[0]), abs(r[1] - r[0]) * hub) - WHEEL_PLAY
            if got is not None and got >= need and (best is None or got - need > best[0] - best[1]):
                best = (got, need)
    return best


def _measured_holes(q: Placed) -> list[tuple[np.ndarray, np.ndarray, tuple[float, float]]]:
    """q's wheel, axle and pin holes at least ``HOLE_SHORT`` long, as lines (world)."""
    return [
        (q.to_world(c.pos), q.m @ c.axis, c.along)
        for c in q.part.others
        if c.kind in ("wheel hole", "axle hole", "pin hole")
        and abs(c.along[1] - c.along[0]) >= HOLE_SHORT
    ]


def _tyre_fit(tyre: Placed, wheel: Placed) -> tuple[float, float] | None:
    """A tyre measured round its wheel (``_tyre_on_wheel``), both axes from their boxes (the
    wheel's from a hole at least ``HOLE_SHORT`` long when its box is not round): (how much of
    the wheel's width it covers, how much it must); None when it does not, or when an axis
    comes only from the real shape (``_body_axis``: good enough to accept the joint, not to
    measure its fit)."""
    words = tyre.part.name_joint_words()
    if "tyre" not in words or _both_wheel_and_tyre(tyre):
        return None
    ax = _box_axis(tyre)
    box = _box_axis(wheel)
    lines = [(box[0], box[1], box[2])] if box is not None else _measured_holes(wheel)
    if ax is None or not lines:
        return None
    width = abs(ax[2][1] - ax[2][0])
    best = None
    for o, d, r in lines:
        got = _share_on_line(ax[0], ax[1], ax[2], o, d, r)
        need = max(WHEEL_IN, min(width, abs(r[1] - r[0])) - TYRE_PLAY - 0.5)
        if got is not None and got >= need and (best is None or got > best[0]):
            best = (got, need)
    return best


def _axle_fit(p: Placed, q: Placed) -> float | None:
    """An axle of p measured along a hole of q (``_axle_in_hole``: only an axle the library
    draws with axle-hole primitives is measured): how far it is in; None otherwise."""
    drawn = [c for c in p.part.others if c.kind == "axle"]
    if not drawn or any(not AXLE_HOLE_PRIM.match(c.prim) for c in drawn):
        return None
    best = None
    for c in drawn:
        for h in q.part.others:
            if h.kind not in ("axle hole", "pin hole"):
                continue
            got = _share_on_line(
                p.to_world(c.pos), p.m @ c.axis, c.along, q.to_world(h.pos), q.m @ h.axis, h.along
            )
            if got is not None and got >= AXLE_IN and (best is None or got > best):
                best = got
    return best


def _pin_halves(p: Placed) -> list:
    """The Technic pin halves of p as connectors. The library draws a full pin (3673, 2780)
    with a pin primitive for one half only: a part with one pin connector, no axle, no wider
    than a pin across (a 16 LDU box) and reaching 8 LDU or more on the other side gets that
    other half too, as long as it reaches (a 3/4 pin's other half is 10 LDU)."""
    pins = [c for c in p.part.others if c.kind == "pin"]
    if len(pins) != 1 or any(c.kind == "axle" for c in p.part.others):
        return pins
    c = pins[0]
    lo, hi = sorted(c.along)
    corners = np.array(
        [
            [x, y, z]
            for x in (p.part.bbox_min[0], p.part.bbox_max[0])
            for y in (p.part.bbox_min[1], p.part.bbox_max[1])
            for z in (p.part.bbox_min[2], p.part.bbox_max[2])
        ]
    )
    along = (corners - c.pos) @ c.axis
    across = np.linalg.norm((corners - c.pos) - np.outer(along, c.axis), axis=1)
    reach = min(float(along.max()), hi - lo)
    if reach >= 8 and lo < 0 <= hi + 1e-9 and float(across.max()) <= 12:
        return [c, replace(c, along=(0.0, reach))]
    return pins


def _pin_fit(p: Placed, q: Placed) -> tuple[float, float] | None:
    """A Technic pin of p measured in a pin hole of q: on the hole's line (parallel within
    ``AXLE_DEG``, within ``AXLE_LDU``) and in as far as the shorter of the pin and the hole
    (a through hole drawn at each face is one hole, end to end: ``_hollows``) less
    ``PIN_PLAY``: (how far it is in, how far it must be); None otherwise. A pin the library
    draws with one primitive for one half (a full Technic pin) is measured for that half."""
    holes = _hollows(q, [c for c in q.part.others if c.kind == "pin hole"])
    best = None
    for c in _pin_halves(p):
        for h in holes:
            length = float(np.linalg.norm(h.p1 - h.p0))
            if length < 1e-9:
                continue
            got = _share_on_line(
                p.to_world(c.pos),
                p.m @ c.axis,
                c.along,
                h.p0,
                (h.p1 - h.p0) / length,
                (0.0, length),
            )
            need = min(abs(c.along[1] - c.along[0]), length) - PIN_PLAY
            if got is not None and got >= need and (best is None or got > best[0]):
                best = (got, need)
    return best


def _fit_issue(fit: tuple[int, int, str], by_line: dict[int, Placed]) -> Issue:
    """The report's item for a joint tested for fit: lines [the one that holds, the one held];
    its text is "line N (part) is held ..." (``Report.text`` lists what follows "is held"
    under HOW IT HOLDS TOGETHER)."""
    holder, held, how = fit
    p = by_line[held]
    return Issue("fit", "joint", [holder, held], f"line {held} ({p.key}) is held {how}")


def _fit_of(a: Placed, b: Placed, words: list[str]) -> tuple[int, int, str] | None:
    """Is a named joint between a and b one the checker has measured, a part in the other
    where and as far as it should be (see the contract: "tested for fit")? Then (the line
    that holds, the line held, the words after "is held"); None for a joint known by name
    only."""
    for word in words:
        for p, q in ((a, b), (b, a)):
            if word == "wheel pin":
                got = _wheel_pin_fit(p, q)
                if got is not None:
                    return (
                        p.line,
                        q.line,
                        (
                            f"on the wheel pin of line {p.line} (in {fmt(round(got[0], 1))} LDU, "
                            f"{fmt(round(got[1], 1))} asked)"
                        ),
                    )
            elif word == "tyre on a wheel":
                got = _tyre_fit(p, q)
                if got is not None:
                    return (
                        q.line,
                        p.line,
                        (
                            f"round the wheel line {q.line} (over {fmt(round(got[0], 1))} LDU, "
                            f"{fmt(round(got[1], 1))} asked)"
                        ),
                    )
            elif word == "axle":
                got_a = _axle_fit(p, q)
                if got_a is not None:
                    return (
                        p.line,
                        q.line,
                        (f"on the axle of line {p.line} (in {fmt(round(got_a, 1))} LDU)"),
                    )
            elif word == "bar in a clip":
                tube = _bar_in(p, q, [])  # a bar in a bar tube (``_tube_hollows``)
                if tube is not None:
                    return (
                        p.line,
                        q.line,
                        (
                            f"as a {tube[0]} of line {p.line} (on the hollow's axis, in far enough "
                            "and no thicker than a bar)"
                        ),
                    )
                got_c = _clip_fit(p, q)
                if got_c is not None:
                    return (
                        p.line,
                        q.line,
                        (
                            f"by the clip of line {p.line} round its bar (its point "
                            f"{fmt(round(got_c, 1))} LDU from the bar's line)"
                        ),
                    )
            elif word == "Technic pin":
                got = _pin_fit(p, q)
                if got is not None:
                    return (
                        p.line,
                        q.line,
                        (
                            f"on the Technic pin of line {p.line} (in {fmt(round(got[0], 1))} LDU, "
                            f"{fmt(round(got[1], 1))} asked)"
                        ),
                    )
    return None


# ---- what a named joint needs, and nothing more ---------------------------------------------

JOINT_ROOM = {  # LDU round a receptacle's line (the hole, the clip) where its joint may share
    "pin hole": 8.0,
    "axle hole": 7.0,
    "wheel hole": 8.0,
    "clip": 11.5,  # a clip primitive's point is up to 7.3 from its bar, plus the bar's 4
    "hinge": 10.0,
    "ball socket": 9.0,
    "bar handle": 6.0,  # round the handle's bar (``_handle_bars``), when the clip has no primitive
}
CLIP_REACH = 7.5  # LDU a clip primitive's point may be from the bar it holds
CLIP_DEG = 5.0  # degrees the bar may lean from the grip's direction
GRIP_HALF = 2.0  # LDU either side of the grip's middle where bar and clip must both be
GRIP_R = 5.5  # LDU: the circle round the bar's line where the clip is and the bar is not
GRIP_VERSION = 1  # the grips found (``grip_lines``) are kept on disk under this version
GRIP_RING = 7  # of 12 points on that circle the clip must fill: more than half, a closed grip
BAR_BOX = 13.0  # LDU: a bar part's box is no wider than this across (a bar with a stop: 12)
JOINT_SNUG_DEPTH = 1.5  # LDU: a joint known only by name may share a piece less deep than this
JOINT_SNUG_VOL = 1000.0  # LDU^3: and less than this much in all
WHEEL_IN = 2.0  # LDU a tyre and its wheel must share along their axis
BOX_ROUND = 0.6  # LDU: a round part's box has two sides this nearly equal (its diameter)
HOLE_SHORT = 4.0  # LDU: a hole primitive shorter than this does not give a wheel's line
BODY_ROUND = 0.8  # seen along its axis, a body of revolution fills this share of its rim
BODY_OUT = 0.12  # and has no more than this share of its shadow outside that circle
BODY_SIDES = 2.0  # LDU: and its outline's two sides differ by no more than this
TYRE_PLAY = 6.0  # LDU a tyre may sit off its wheel along their axis
WHEEL_PLAY = 2.0  # LDU a wheel may sit short of home on its pin (official 30187c01: 1.5)


def _round_axis(p: Placed) -> tuple[np.ndarray, np.ndarray, tuple[float, float], float] | None:
    """A round part's axis from its box (two equal sides are its diameter, the third its
    width), else from its real shape (``_body_axis``): the centre (world), the direction
    (world), its reach along it from the centre, and its radius; None when neither says."""
    box = _box_axis(p)
    if box is not None:
        return box
    body = _body_axis(p.key)
    if body is None:
        return None
    centre, k, reach, radius = body
    return p.to_world(centre), p.m @ np.eye(3)[k], reach, radius


def _box_axis(p: Placed) -> tuple[np.ndarray, np.ndarray, tuple[float, float], float] | None:
    """A round part's axis from its box alone: two sides equal within ``BOX_ROUND`` LDU are
    its diameter, the third (differing by more) its width; as ``_round_axis``."""
    span = p.part.bbox_max - p.part.bbox_min
    for k in range(3):
        o = [j for j in range(3) if j != k]
        if abs(span[o[0]] - span[o[1]]) <= BOX_ROUND and abs(span[k] - span[o[0]]) > BOX_ROUND:
            centre = p.to_world((p.part.bbox_min + p.part.bbox_max) / 2)
            d = p.m @ np.eye(3)[k]
            return centre, d, (-span[k] / 2, span[k] / 2), float(span[o[0]] / 2)
    return None


_BODY_AXES: dict[str, tuple[np.ndarray, int, tuple[float, float], float] | None] = {}


def _body_axis(key: str) -> tuple[np.ndarray, int, tuple[float, float], float] | None:
    """The axis of a part whose real shape is a body of revolution about one of its own axes
    (a wheel, a tyre, whatever its box, spokes and all): seen along that axis its outline's
    two sides are within ``BODY_SIDES`` LDU, its shadow covers ``BODY_ROUND`` of the 2 LDU
    rim of the circle they inscribe and has no more than ``BODY_OUT`` of itself outside it.
    (centre, the axis 0/1/2, reach from the centre, radius), local; None when no axis is
    round."""
    if key in _BODY_AXES:
        return _BODY_AXES[key]
    from bricksnap.lab import solid

    found = None
    sol = solid.solid(key)
    if sol.full.size and sol.full.any():
        idx = [
            np.nonzero(sol.full.any(axis=tuple(j for j in range(3) if j != k)))[0] for k in range(3)
        ]
        lo = np.array([sol.lo[k] + i.min() * sol.h for k, i in enumerate(idx)])
        hi = np.array([sol.lo[k] + (i.max() + 1) * sol.h for k, i in enumerate(idx)])
        best = 0.0
        for k in range(3):
            u, v = [j for j in range(3) if j != k]
            su, sv = hi[u] - lo[u], hi[v] - lo[v]
            if abs(su - sv) > BODY_SIDES:
                continue
            shadow = sol.full.any(axis=k)  # seen along k: indexed (u, v)
            cu, cv, r = (lo[u] + hi[u]) / 2, (lo[v] + hi[v]) / 2, min(su, sv) / 2
            gu = sol.lo[u] + (np.arange(shadow.shape[0]) + 0.5) * sol.h - cu
            gv = sol.lo[v] + (np.arange(shadow.shape[1]) + 0.5) * sol.h - cv
            dist = np.hypot(gu[:, None], gv[None, :])
            ring = (dist <= r) & (dist >= r - 2)
            rim = float((shadow & ring).sum()) / max(1, int(ring.sum()))
            outside = float((shadow & (dist > r + 0.5)).sum()) / max(1, int(shadow.sum()))
            if rim >= BODY_ROUND and outside <= BODY_OUT and rim > best:
                centre = (lo + hi) / 2
                best = rim
                found = (centre, k, (float(lo[k] - centre[k]), float(hi[k] - centre[k])), float(r))
    _BODY_AXES[key] = found
    return found


def _lines_meet(
    o1: np.ndarray,
    d1: np.ndarray,
    r1: tuple[float, float],
    o2: np.ndarray,
    d2: np.ndarray,
    r2: tuple[float, float],
    need: float,
) -> bool:
    """Do two lines (a point, a unit direction, a reach along it) run along each other:
    parallel within ``AXLE_DEG``, within ``AXLE_LDU``, their reaches sharing ``need`` LDU?
    (The test an axle in a hole and a wheel on its pin both use.)"""
    if abs(float(np.dot(d1, d2))) < math.cos(math.radians(AXLE_DEG)):
        return False
    w = o2 - o1
    t = float(np.dot(w, d1))
    if float(np.linalg.norm(w - t * d1)) > AXLE_LDU:
        return False
    a1 = sorted(r1)
    a2 = sorted(t + float(np.dot(d2, d1)) * np.array(r2))
    return min(a1[1], a2[1]) - max(a1[0], a2[0]) >= need


def _wheel_lines(
    p: Placed, whole: bool = False
) -> list[tuple[np.ndarray, np.ndarray, tuple[float, float]]]:
    """The lines a wheel turns about: its wheel holes (or axle or pin holes) at least
    ``HOLE_SHORT`` LDU long, else the axis of its round box or body (``_round_axis``). With
    ``whole`` (a tyre on it), a hole on the round axis reaches the wheel's whole width."""
    holes = [
        (p.to_world(c.pos), p.m @ c.axis, c.along)
        for c in p.part.others
        if c.kind in ("wheel hole", "axle hole", "pin hole")
        and abs(c.along[1] - c.along[0]) >= HOLE_SHORT
    ]
    ax = _round_axis(p) if whole or not holes else None
    if ax is None:
        return holes
    if not whole:
        return [(ax[0], ax[1], ax[2])]
    return [(ax[0], ax[1], ax[2])] + [
        h for h in holes if not _lines_meet(h[0], h[1], h[2], ax[0], ax[1], ax[2], 0.0)
    ]


def _wheel_on_pin(p: Placed, q: Placed) -> bool:
    deep = not ("tyre" in q.part.name_joint_words() and not _both_wheel_and_tyre(q))
    return _wheel_pin_in(p, q, deep)


def _wheel_pin_in(p: Placed, q: Placed, deep: bool) -> bool:
    """Is a wheel pin of p in q's wheel: on the line of its hole (or of its round box), and in
    as far as the shorter of the pin and the hole (or half the wheel's width, for a wheel drawn
    with no hole) less ``WHEEL_PLAY``
    (``_lines_meet``)? A tyre on the wheel need only be round the pin's line, sharing
    ``WHEEL_IN`` LDU of it (``deep`` False): the pin is in the wheel, not in the tyre."""
    pins = [c for c in p.part.others if c.kind == "wheel pin"]
    if not pins:
        return True  # a pin known only by name: nothing to measure
    # a wheel drawn with no hole primitive (or only a short one): its hub is taken as half
    # its width; a wheel with no line at all is judged as before, by nearness
    lines = _wheel_lines(q)
    if not lines:
        return True
    hub = (
        1.0
        if any(
            c.kind in ("wheel hole", "axle hole", "pin hole")
            and abs(c.along[1] - c.along[0]) >= HOLE_SHORT
            for c in q.part.others
        )
        else 0.5
    )
    return any(
        _lines_meet(
            p.to_world(c.pos),
            p.m @ c.axis,
            c.along,
            o,
            d,
            r,
            min(abs(c.along[1] - c.along[0]), abs(r[1] - r[0]) * hub) - WHEEL_PLAY
            if deep
            else WHEEL_IN,
        )
        for c in pins
        for o, d, r in lines
    )


def _both_wheel_and_tyre(p: Placed) -> bool:
    words = p.part.name_joint_words()
    return "tyre" in words and ("wheel" in words or "wheels" in words)


def _tyre_on_wheel(p: Placed, q: Placed) -> bool:
    """Is the tyre p round the wheel q: their round axes on one line (``_lines_meet``), the
    tyre over all but ``TYRE_PLAY`` LDU of the narrower one's width, less 0.5 LDU for the
    real shape's cells (at least ``WHEEL_IN``)?
    Two parts that are each a wheel with its tyre do not make a tyre on a wheel."""
    if _both_wheel_and_tyre(p) and _both_wheel_and_tyre(q):
        return False
    ax = _round_axis(p)
    lines = _wheel_lines(q, whole=True)
    if ax is None or not lines:
        return True  # nothing to measure: judged as before, by nearness
    width = abs(ax[2][1] - ax[2][0])
    return any(
        _lines_meet(
            ax[0],
            ax[1],
            ax[2],
            o,
            d,
            r,
            max(WHEEL_IN, min(width, abs(r[1] - r[0])) - TYRE_PLAY - 0.5),
        )
        for o, d, r in lines
    )


def _handle_bars(p: Placed) -> list[tuple[np.ndarray, np.ndarray]]:
    """The bars of a part's handles, world: a handle is drawn with a handle primitive at each
    end of its bar, and the bar runs through the middle of each one's reach (its
    "attachment"); each primitive is paired with its nearest one."""
    ends = [
        p.to_world(c.pos + c.axis * (sum(c.along) / 2))
        for c in p.part.others
        if c.kind == "bar handle"
    ]
    bars = []
    used: set[int] = set()
    for i, e in enumerate(ends):
        if i in used:
            continue
        others = [j for j in range(len(ends)) if j != i and j not in used]
        if not others:
            bars.append((e, e))  # a single attachment: its own point
            continue
        j = min(others, key=lambda k: float(np.linalg.norm(ends[k] - e)))
        used |= {i, j}
        bars.append((e, ends[j]))
    return bars


def _bar_lines(q: Placed) -> list[tuple[np.ndarray, np.ndarray]]:
    """The bars of q a clip can hold, as segments (world): its handles' bars
    (``_handle_bars``), else, for a part its name calls a bar (a bar, an antenna, a lever)
    with no clip of its own and a box no more than ``BAR_BOX`` LDU across, its box's long
    axis from end to end."""
    bars = _handle_bars(q)
    if bars:
        return bars
    if any(c.kind == "clip" for c in q.part.others):
        return []
    if not any(_NAME_END.get(w) == "bar+" for w in q.part.name_joint_words()):
        return []
    if "bar tube" in q.part.description.lower():
        return []
    lo, hi = q.part.bbox_min, q.part.bbox_max
    span = hi - lo
    k = int(np.argmax(span))
    if sorted(span)[1] > BAR_BOX:
        return []
    c = (lo + hi) / 2
    e0, e1 = c.copy(), c.copy()
    e0[k], e1[k] = lo[k], hi[k]
    return [(q.to_world(e0), q.to_world(e1))]


def _ring_count(part: Placed, centre: np.ndarray, d: np.ndarray, r: float, n: int = 12) -> int:
    """How many of n points on a circle of radius r round ``centre`` (across direction d,
    world) are in ``part``'s real solid."""
    from bricksnap.lab import solid

    u, v = _perp(d)
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    pts = centre + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
    return int(solid.solid(part.key).inside(part.to_local(pts), deep=False).sum())


def _could_grip(p: Placed, q: Placed) -> bool:
    """Is p a clip (a clip primitive, or its name) and q a part with a bar a clip can hold?"""
    if not any(c.kind == "clip" for c in p.part.others) and (
        "clip" not in p.part.name_joint_words()
    ):
        return False
    return bool(_bar_lines(q))


def _grip_holds(p: Placed, q: Placed, x: np.ndarray, u: np.ndarray) -> bool:
    """Does a clip of p grip a bar of q whose centre line runs through x along u (world)? At x
    and ``GRIP_HALF`` to either side, q is bar-thick (its real shape is there, at some of 12
    points 2 LDU round the line, a bar end may be hollow, and at none of 12 at ``GRIP_R``)
    and p is round it (``GRIP_RING`` of 12 points at ``GRIP_R``, none at 3 LDU: a bar pushed
    into the clip's body is not in its grip)."""
    for dt in (-GRIP_HALF, 0.0, GRIP_HALF):
        c = x + dt * u
        if (
            _ring_count(q, c, u, 2.0) == 0
            or _ring_count(q, c, u, GRIP_R) > 0
            or _ring_count(p, c, u, GRIP_R) < GRIP_RING
            or _ring_count(p, c, u, 3.0) > 0
        ):
            return False
    return True


_GRIPS: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}


def _clip_ring(sol, x: np.ndarray, d: np.ndarray, r: float) -> int:  # type: ignore[no-untyped-def]
    """``_ring_count`` on a part's own solid, in its own frame."""
    u, v = _perp(d)
    ang = np.linspace(0, 2 * math.pi, 12, endpoint=False)
    pts = x + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
    return int(sol.inside(pts, deep=False).sum())


def grip_lines(key: str) -> list[tuple[np.ndarray, np.ndarray]]:
    """Where a clip part grips a bar, in its own frame: one (point on the bar's centre line,
    its direction) per clip, found in its real shape. A grip is closed: at the point and
    ``GRIP_HALF`` to either side along the direction, the clip fills ``GRIP_RING`` of 12
    points on a circle of ``GRIP_R`` round the line (more than half of it) and none of 12 at
    3 LDU (room for a bar 4 LDU in radius). For each clip primitive, the closed grip nearest
    its point, on the part's own axes or square to the primitive's axis every 15 degrees
    (most clip round it first, then square with the part's axes); a part its name calls a
    clip with no clip primitive (15712), the best closed grip anywhere in its box along its
    own axes. A clip with no closed grip (the thick U-clip 4085c) has none: it is known by
    name only. The checker (``_clip_fit``) and the builder's ``clip`` tool both use this. What
    the search finds is kept on disk (``cache_dir()/grips``), keyed by the part and by what
    makes a grip: ``GRIP_VERSION``, ``GRIP_R``, ``GRIP_RING`` and ``GRIP_HALF``."""
    if key in _GRIPS:
        return _GRIPS[key]
    import json

    from bricksnap.lab import solid
    from bricksnap.lab.ldraw_lib import cache_dir

    name = re.sub(r"[^a-z0-9._-]", "_", key)  # keyed by what makes a grip, too
    stored = cache_dir() / "grips" / f"{name}.v{GRIP_VERSION}-{GRIP_R}-{GRIP_RING}-{GRIP_HALF}.json"
    try:
        got = json.loads(stored.read_text())
        _GRIPS[key] = [(np.array(x, float), np.array(d, float)) for x, d in got]
        return _GRIPS[key]
    except (OSError, ValueError, TypeError):
        pass
    part = library().part(key)
    sol = solid.solid(key)
    seeds = [(c.pos, c.axis) for c in part.others if c.kind == "clip"]
    if not seeds and "clip" in part.name_joint_words():
        seeds = [((part.bbox_min + part.bbox_max) / 2, None)]
    found = []
    for pos, axis in seeds:
        dirs = [np.eye(3)[k] for k in range(3)]
        if axis is not None:
            a = axis / np.linalg.norm(axis)
            u, v = _perp(a)
            dirs += [math.cos(t) * u + math.sin(t) * v for t in np.radians(np.arange(0, 180, 15))]
            reach = 8.0
        else:
            reach = float(np.max(part.bbox_max - part.bbox_min)) / 2
        best = None
        for d in dirs:
            s1, s2 = _perp(d)
            for p_ in np.arange(-reach, reach + 0.01, 1.0):
                for q_ in np.arange(-reach, reach + 0.01, 1.0):
                    x = pos + p_ * s1 + q_ * s2
                    if _clip_ring(sol, x, d, GRIP_R) < GRIP_RING:
                        continue
                    rings = [
                        _clip_ring(sol, x + t * d, d, GRIP_R) for t in (-GRIP_HALF, 0.0, GRIP_HALF)
                    ]
                    if min(rings) < GRIP_RING:
                        continue
                    if any(
                        _clip_ring(sol, x + t * d, d, 3.0) for t in (-GRIP_HALF, 0.0, GRIP_HALF)
                    ):
                        continue
                    score = (
                        sum(rings),
                        round(float(np.abs(d).max()), 3),
                        -float(np.linalg.norm(x - pos)),
                    )
                    if best is None or score > best[0]:
                        best = (score, x, d / np.linalg.norm(d))
        if best is not None:
            found.append((best[1], best[2]))
    _GRIPS[key] = found
    try:  # the search takes a second or two per part: keep what it found
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text(json.dumps([[x.tolist(), d.tolist()] for x, d in found]))
    except OSError:
        pass
    return found


def _clip_fit(p: Placed, q: Placed) -> float | None:
    """A clip of p measured on a bar of q: how far the clip's grip (``grip_lines``) is from
    the bar's centre line, at the bar's point nearest it; None when it is not a fit. For each
    grip of p: on each bar of q (``_bar_lines``) that runs along the grip's direction within
    ``CLIP_DEG`` degrees, the bar's point nearest the grip's point; when q has no bar the
    checker can find (23443's handle), the grip's own line. There the grip must hold
    (``_grip_holds``: the bar bar-thick, the clip closed round it). Any angle about the bar's
    line is a fit: that is what a clip is for."""
    grips = grip_lines(p.key)
    if not grips:
        return None
    bars = _bar_lines(q)
    cos = math.cos(math.radians(CLIP_DEG))
    best = None
    for gx, gd in grips:
        o = p.to_world(gx)
        d = p.m @ gd
        if not bars:
            if _grip_holds(p, q, o, d):
                best = 0.0
            continue
        for e0, e1 in bars:
            length = float(np.linalg.norm(e1 - e0))
            if length < 1e-6:
                continue
            u = (e1 - e0) / length
            if abs(float(np.dot(u, d))) < cos:
                continue
            x = e0 + float(np.dot(o - e0, u)) * u
            if _grip_holds(p, q, x, u):
                dist = float(np.linalg.norm(o - x))
                best = dist if best is None else min(best, dist)
    return best


def _clip_at_bar(a: Placed, b: Placed) -> bool:
    """Where one part has a clip primitive and the other a bar (a handle's, or a bar part's:
    ``_bar_lines``), a clip primitive must be within ``CLIP_REACH`` LDU of the bar, between
    its ends (a clip primitive's own point is up to 7.3 LDU from the bar it holds in the
    official sets measured). Otherwise there is nothing to measure."""
    for clip, bar in ((a, b), (b, a)):
        clips = [clip.to_world(c.pos) for c in clip.part.others if c.kind == "clip"]
        bars = _bar_lines(bar)
        if not clips or not bars:
            continue
        for e0, e1 in bars:
            d = e1 - e0
            n = float(np.linalg.norm(d))
            for c in clips:
                t = float(np.clip(np.dot(c - e0, d) / (n * n), 0.0, 1.0)) if n > 1e-9 else 0.0
                if float(np.linalg.norm(c - (e0 + t * d))) <= CLIP_REACH:
                    return True
        return False
    return True


def _joint_room(a: Placed, b: Placed, words: list[str]) -> list:
    """Where a named joint's two parts may share material (``JOINT_ROOM``): round the line of
    each receptacle of either part (a pin hole, an axle hole, a wheel hole, a clip, a hinge, a
    ball socket: never round the pin or axle that goes in, which would excuse that whole part),
    2 LDU past its ends; round a handle's bar; for a wheel known only by name, round its round
    box's axis; for a tyre on a wheel, the tyre's own round box."""
    room: list = []
    for p in (a, b):
        for e0, e1 in _handle_bars(p):
            d = e1 - e0
            n = float(np.linalg.norm(d))
            d = d / n if n > 1e-9 else np.zeros(3)
            room.append((e0 - 2 * d, e1 + 2 * d, JOINT_ROOM["bar handle"]))
        for c in p.part.others:
            r = JOINT_ROOM.get(c.kind)
            if r is None or c.kind == "bar handle":
                continue
            lo, hi = sorted(c.along)
            room.append(
                (p.to_world(c.pos + (lo - 2) * c.axis), p.to_world(c.pos + (hi + 2) * c.axis), r)
            )
    if "turntable" in words:  # the two halves turn about one axis: room is their round box
        for p in (a, b):
            ax = _round_axis(p)
            if ax is not None and "turntable" in p.part.name_joint_words():
                lo, hi = ax[2]
                room.append((ax[0] + (lo - 2) * ax[1], ax[0] + (hi + 2) * ax[1], ax[3] + 1))
    for p in (a, b):
        words_p = p.part.name_joint_words()
        round_ = (
            "tyre on a wheel" in words and "tyre" in words_p,
            "wheel pin" in words
            and ("wheel" in words_p or "wheels" in words_p)
            and not any(c.kind == "wheel hole" for c in p.part.others),
        )
        if any(round_):
            ax = _round_axis(p)
            if ax is not None:
                lo, hi = ax[2]
                r = ax[3] + 1 if round_[0] else JOINT_ROOM["wheel hole"]
                room.append((ax[0] + (lo - 2) * ax[1], ax[0] + (hi + 2) * ax[1], r))
    return room


def _tyre_room_is_all(a: Placed, b: Placed) -> bool:
    """For a tyre on a wheel: does the room (the tyre's round box, ``_joint_room``) hold all
    of the tyre? Then it holds all they could share, and there is nothing to measure."""
    return any(
        "tyre" in p.part.name_joint_words()
        and not _both_wheel_and_tyre(p)
        and _round_axis(p) is not None
        for p in (a, b)
    )


def _joint_clash(a: Placed, b: Placed, words: list[str]) -> bool:
    """Do two parts joined by a named joint share more than the joint needs? Their real
    shapes are measured outside the joint's room (``_joint_room``; everywhere when it has
    none, a joint known only by name) as any overlap is, except that a piece less than
    ``JOINT_SNUG_DEPTH`` deep and ``JOINT_SNUG_VOL`` in all is allowed: the library's
    shapes of parts made to go together share that much (an arm's shoulder on its torso)."""
    from bricksnap.lab import solid

    if "bar in a clip" in words and any(_bar_in(p, q, []) for p, q in ((a, b), (b, a))):
        return False  # a bar in a bar tube's bore: ``_bar_in`` has measured what else they share
    if words == ["tyre on a wheel"] and _tyre_room_is_all(a, b):
        return False  # whatever they share is in the tyre, so in its room
    room = _joint_room(a, b, words)
    depth, vol, needed = solid.interference(
        (a.key, a.pos, a.m), (b.key, b.pos, b.m), apart=room or None
    )
    if depth < needed - 1e-9:
        return False
    return depth >= JOINT_SNUG_DEPTH - 1e-9 or vol > JOINT_SNUG_VOL


def _touches(a: Placed, b: Placed) -> bool:
    pts, _ = a.part.samples()
    probe = [pts]
    for c in a.part.others:
        probe.append(c.pos[None, :])
    allp = np.concatenate(probe) if probe else np.zeros((0, 3))
    if not len(allp):
        return False
    world = a.to_world(allp)
    for off in ([0, 0, 0], [4, 0, 0], [-4, 0, 0], [0, 4, 0], [0, -4, 0], [0, 0, 4], [0, 0, -4]):
        if b.part.inside(b.to_local(world + np.array(off, dtype=float)), tol=-0.5).any():
            return True
    return False


def _bottom_points(p: Placed) -> np.ndarray:
    part = p.part
    if part.top is None or part.bottom is None:
        return np.zeros((0, 3))
    ii, jj = np.nonzero(np.isfinite(part.bottom))
    i0, j0 = part.col_origin
    x = (ii + i0) * 2.0 + 1.0
    z = (jj + j0) * 2.0 + 1.0
    local = np.stack([x, part.bottom[ii, jj].astype(float), z], axis=1)
    top = np.stack([x, part.top[ii, jj].astype(float), z], axis=1)
    return p.to_world(np.concatenate([local, top]))


def _hull(points: np.ndarray) -> np.ndarray:
    pts = sorted({(round(float(x), 2), round(float(z), 2)) for x, z in points})
    if len(pts) <= 2:
        return np.array(pts)

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def _outside_by(hull: np.ndarray, p: np.ndarray) -> float:
    """How far point p (x, z) is outside the convex hull (0 or less when inside)."""
    if len(hull) < 3:
        if not len(hull):
            return math.inf
        return float(min(np.linalg.norm(hull - p, axis=1)))
    worst = -math.inf
    n = len(hull)
    for i in range(n):
        a, b = hull[i], hull[(i + 1) % n]
        edge = b - a
        normal = np.array([edge[1], -edge[0]])
        normal /= np.linalg.norm(normal) + 1e-12
        worst = max(worst, float(np.dot(p - a, normal)))
    return worst


class _Groups:
    def __init__(self, items: list[int]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list[list[int]]:
        out: dict[int, list[int]] = {}
        for x in self.parent:
            out.setdefault(self.find(x), []).append(x)
        return [sorted(v) for v in out.values()]


def _lines(nums: list[int]) -> str:
    nums = sorted(nums)
    if len(nums) == 1:
        return f"line {nums[0]}"
    if len(nums) <= 12:
        return "lines " + ", ".join(map(str, nums))
    return "lines " + ", ".join(map(str, nums[:12])) + f" and {len(nums) - 12} more"


def _vec(v: np.ndarray) -> str:
    return " ".join(fmt(round(float(x) * 2) / 2) for x in v)


# ---- the check ------------------------------------------------------------------------------


def _moves(ok: int, n: int) -> str:
    if ok == n:
        return f"{'the joint moves' if n == 1 else f'all {n} joints move'} freely"
    return f"{ok} of {n} joints move freely"


def check(text: str, lib: Library | None = None, movement: bool = True) -> Report:
    lib = lib or library()
    report = Report(colours=lib.colours())
    placed = parse(text, lib, report)
    report.placed = placed
    if not placed:
        return report
    colours = report.colours
    by_line = {p.line: p for p in placed}

    def lab(p: Placed) -> str:
        return p.label(colours)

    def short(p: Placed) -> str:
        return f"line {p.line} ({p.key})"

    joint_pairs: set[tuple[int, int]] = set()

    boxes = {p.line: _world_bbox(p, 2.0) for p in placed}
    pairs = []
    for i, a in enumerate(placed):
        for b in placed[i + 1 :]:
            (alo, ahi), (blo, bhi) = boxes[a.line], boxes[b.line]
            if np.all(alo <= bhi) and np.all(blo <= ahi):
                pairs.append((a, b))

    groups = _Groups([p.line for p in placed])
    stud_problem_pairs: set[tuple[int, int]] = set()
    bar_held: dict[int, np.ndarray] = {}  # parts held as a bar in a hollow -> its axis
    pin_holes: dict[tuple[float, ...], int] = {}  # (part, hole) -> the part whose stud is in it
    slight: list[tuple[Placed, Placed, int, str]] = []  # slight overlaps: (a, b, issue, text)
    # pairs whose filled bodies overlap with no joint or bar between them: where a loose part
    # may be sunk into a held one (``_sunk_words``)
    plain_overlaps: dict[tuple[int, int], float] = {}  # -> the filled bodies' shared volume
    for a, b in pairs:
        linked = False
        bar = None  # a bar-in-a-hollow joint between a and b: (its name, the hollow's axis)
        for holder, held in ((a, b), (b, a)):
            hits = _stud_hits(holder, held)
            good = [h for h in hits if h.ok]
            bad = [h for h in hits if not h.ok and h.joint is None]
            for h in hits:
                if h.joint is not None and h.joint[0] == "stud in a pin hole":
                    s = numbered_studs(holder.part)[h.stud - 1]
                    d_w = holder.m @ s.axis
                    key = (held.line, *_pin_hole_key(held, holder.to_world(s.pos), d_w))
                    if pin_holes.setdefault(key, holder.line) != holder.line:
                        # LEGO's rule: one stud in a pin hole
                        h.joint = None
                        h.reason = (
                            f"go into a Technic pin hole of line {held.line} that already "
                            f"takes a stud of line {pin_holes[key]} from its other end (a pin "
                            "hole takes one stud)"
                        )
                        bad.append(h)
                        continue
                if h.joint is not None and bar is None:
                    bar = (*h.joint, holder.line, held.line)
                    if h.joint[0] != "stud in a pin hole":
                        bar_held[held.line] = h.joint[1]
            if good:
                linked = True
                hows = {h.how for h in good}
                report.links.append(
                    Link(holder.line, held.line, [h.stud for h in good], ", ".join(sorted(hows)))
                )
                groups.join(holder.line, held.line)
            if bad:
                stud_problem_pairs.add((min(a.line, b.line), max(a.line, b.line)))
                first = bad[0]
                studs = ", ".join(str(h.stud) for h in bad[:8])
                fix = ""
                if first.move is not None and not good:
                    target = held.pos + first.move
                    fix = f" Fix: move line {held.line} by ({_vec(first.move)}), to {_vec(target)}."
                elif good:
                    fix = (
                        f" (Line {held.line} is held by {len(good)} other stud(s) of line "
                        f"{holder.line}, so the two parts are not lined up with each other.)"
                    )
                report.issues.append(
                    Issue(
                        "problem",
                        "stud",
                        [holder.line, held.line],
                        f"Stud{'s' if len(bad) > 1 else ''} {studs} of {lab(holder)}: they "
                        f"{first.reason}; {lab(held)} cannot sit there.{fix}",
                    )
                )
        # overlaps
        v1, box1 = _overlap(a, b)
        v2, box2 = _overlap(b, a)
        vol = max(v1, v2)
        box = box1 if v1 >= v2 else box2
        if vol < IGNORE_OVERLAP and not linked:
            plain_overlaps[(a.line, b.line)] = vol  # too little to report; a part may be sunk
        if vol >= IGNORE_OVERLAP and box is not None:
            smaller = max(1.0, min(a.part.volume(), b.part.volume()))
            share = vol / smaller
            where = (
                f"around x {fmt(round(box[0][0]))}..{fmt(round(box[1][0]))}, y "
                f"{fmt(round(box[0][1]))}..{fmt(round(box[1][1]))}, z {fmt(round(box[0][2]))}.."
                f"{fmt(round(box[1][2]))}"
            )
            joint = _joint_words(a, b, box)
            if not joint and bar is None:
                bar = _held_bar(a, b, bar_held)
            base = (
                f"{lab(a)} and {lab(b)} occupy the same space: about {int(round(vol, -1))} LDU^3, "
                f"{share:.0%} of the smaller part, {where}."
            )
            twin = a.key == b.key and bool(
                np.allclose(a.pos, b.pos, atol=0.5) and np.allclose(a.m, b.m, atol=0.01)
            )
            if twin:  # the same part twice in one place: never a joint
                joint, bar = [], None
                joint_pairs.add((a.line, b.line))  # nor anything else that joins them
                report.issues.append(
                    Issue(
                        "problem",
                        "overlap",
                        [a.line, b.line],
                        base + " They are the same part twice in the same place: remove one.",
                    )
                )
            elif joint and _joint_clash(a, b, joint):
                # a named joint does not excuse what else the two share
                joint_pairs.add((a.line, b.line))
                report.issues.append(
                    Issue(
                        "problem",
                        "overlap",
                        [a.line, b.line],
                        base + f" That is more than their {' or '.join(joint[:2])} joint "
                        "needs: move one of them so they only touch where they join.",
                    )
                )
            elif joint:
                fit = _fit_of(a, b, joint)
                report.issues.append(
                    _fit_issue(fit, by_line)
                    if fit is not None
                    else Issue(
                        "not checked",
                        "joint",
                        [a.line, b.line],
                        f"{short(a)} and {short(b)}: a {' or '.join(joint[:3])} joint, known by "
                        f"name only: the checker has not measured the fit (they share about "
                        f"{int(round(vol, -1))} LDU^3 where one goes into the other). Counted "
                        "as joined.",
                    )
                )
                groups.join(a.line, b.line)
                joint_pairs.add((a.line, b.line))
            elif bar is not None:
                if (
                    min(a.line, b.line),
                    max(a.line, b.line),
                ) not in stud_problem_pairs and _really_overlap(a, b, bar[1]):
                    bar = None  # a bar in the hole, but the parts also collide
                    report.issues.append(
                        Issue(
                            "problem",
                            "overlap",
                            [a.line, b.line],
                            base + " Move one of them so they only touch.",
                        )
                    )
            elif vol < SMALL_OVERLAP and share < SMALL_SHARE:
                report.issues.append(
                    Issue("warning", "overlap", [a.line, b.line], "Slight overlap: " + base)
                )
                slight.append((a, b, len(report.issues) - 1, base))
                plain_overlaps[(a.line, b.line)] = vol
            elif (
                min(a.line, b.line),
                max(a.line, b.line),
            ) not in stud_problem_pairs and _really_overlap(a, b):
                plain_overlaps[(a.line, b.line)] = vol
                report.issues.append(
                    Issue(
                        "problem",
                        "overlap",
                        [a.line, b.line],
                        base + " Move one of them so they only touch.",
                    )
                )
        if bar is None and not linked and (a.line, b.line) not in joint_pairs:
            # a bar in a hollow where the rough bodies do not overlap (a thin bar)
            bar = _held_bar(a, b, bar_held)
        if bar is not None and (a.line, b.line) not in joint_pairs:
            holder_ln, held_ln = bar[2], bar[3]
            if bar[0].startswith("stud"):
                how = f"by a stud of line {holder_ln} in its Technic pin hole (on the hole's axis)"
            else:
                how = (
                    f"as a {bar[0]} of line {holder_ln} (on the hollow's axis, in far enough and "
                    "no thicker than a bar)"
                )
            report.issues.append(_fit_issue((holder_ln, held_ln, how), by_line))
            groups.join(a.line, b.line)
            joint_pairs.add((a.line, b.line))
        # joints that cannot be checked
        words = [] if linked or (a.line, b.line) in joint_pairs else _joint_words(a, b, None)
        # a clip round a bar the rough bodies do not reach: the grip itself says it is one
        if (
            not words
            and not linked
            and (a.line, b.line) not in joint_pairs
            and any(_could_grip(p, q) and _clip_fit(p, q) is not None for p, q in ((a, b), (b, a)))
        ):
            words = ["bar in a clip"]
        if words and (_touches(a, b) or _touches(b, a)) and not _joint_clash(a, b, words):
            fit = _fit_of(a, b, words)
            report.issues.append(
                _fit_issue(fit, by_line)
                if fit is not None
                else Issue(
                    "not checked",
                    "joint",
                    [a.line, b.line],
                    f"{short(a)} and {short(b)} touch where they can join by a "
                    f"{' or '.join(words[:3])}, known by name only: the checker has not "
                    "measured the fit. Counted as joined.",
                )
            )
            groups.join(a.line, b.line)

    # a part held only as a bar in a hollow must not go on along that bar into another
    # part: a slight overlap on the line of its hollow (a bar pushed on through a plate's
    # top below the hollow) is measured on the real shapes
    for a, b, k, base in slight:
        if any(
            _bar_goes_on(p, q, bar_held[p.line]) for p, q in ((a, b), (b, a)) if p.line in bar_held
        ):
            report.issues[k] = Issue(
                "problem",
                "overlap",
                [a.line, b.line],
                base + " Move one of them so they only touch.",
            )

    # the ground
    lowest: dict[int, float] = {}
    bottom_pts: dict[int, np.ndarray] = {}
    for p in placed:
        pts = _bottom_points(p)
        bottom_pts[p.line] = pts
        if len(pts):
            lowest[p.line] = float(pts[:, 1].max())
        else:
            lowest[p.line] = float(p.pos[1])
    for p in placed:
        if lowest[p.line] > GROUND_TOL:
            report.issues.append(
                Issue(
                    "problem",
                    "below ground",
                    [p.line],
                    f"{lab(p)} goes {fmt(round(lowest[p.line], 1))} LDU below the ground (y = 0; "
                    f"up is -y). Fix: move it up by {fmt(round(lowest[p.line], 1))} (to y "
                    f"{fmt(round(p.pos[1] - lowest[p.line], 1))}) or move the whole model up.",
                )
            )
    ground_level = 0.0
    grounded = [p.line for p in placed if abs(lowest[p.line]) <= GROUND_TOL]
    if not grounded:
        deepest = max(lowest.values())
        ground_level = deepest
        grounded = [ln for ln, v in lowest.items() if abs(v - deepest) <= GROUND_TOL]
        if deepest < -GROUND_TOL:
            report.issues.append(
                Issue(
                    "problem",
                    "ground",
                    grounded,
                    "Nothing stands on the ground (y = 0): the lowest part "
                    f"({lab(by_line[grounded[0]])}) has its bottom at y "
                    f"{fmt(round(deepest, 1))}. Fix: add {fmt(round(-deepest, 1))} to "
                    "the y of every line, or build down to the ground.",
                )
            )
    report.grounded = grounded

    # what is loose
    gset = set(grounded)
    comps = groups.groups()
    grounded_comps = [c for c in comps if gset & set(c)]
    loose = [c for c in comps if not gset & set(c)]
    main = max(grounded_comps, key=len) if grounded_comps else None
    # a single loose part sunk into a held one (a bar pushed into a solid top): say so, and
    # which way is out, instead of "there is no part under it"
    loose_lines = {ln for c in loose for ln in c}
    looked = 0
    for comp in sorted(loose, key=lambda c: c[0]):
        said = _loose_text(comp, placed, by_line, bottom_pts, lab)
        small = len(comp) == 1 and by_line[comp[0]].part.volume() <= SUNK_SMALL
        if small and looked < SUNK_LOOKS and _sunk_may_apply(said):
            part = by_line[comp[0]]
            near = sorted(
                (
                    (-v, by_line[y if x == part.line else x])
                    for (x, y), v in plain_overlaps.items()
                    if part.line in (x, y)
                    and (y if x == part.line else x) not in loose_lines
                    and (x, y) not in stud_problem_pairs
                    and (x, y) not in joint_pairs
                ),
                key=lambda t: (t[0], t[1].line),
            )[:SUNK_NEAR]
            if near:
                looked += 1
            for _, into in near:
                words = _sunk_words(part, into, lab)
                if words:
                    said = said.split(" There is no part under it.")[0].split(" It rests on")[0]
                    said = said.split(" Its underside is at")[0] + words
                    break
        report.issues.append(Issue("problem", "loose", comp, said))
    for comp in grounded_comps:
        if comp is main:
            continue
        report.issues.append(
            Issue(
                "warning",
                "separate",
                comp,
                f"{_lines(comp).capitalize()} stand{'s' if len(comp) == 1 else ''} on the ground "
                f"but {'is' if len(comp) == 1 else 'are'} not joined to the rest of the model "
                f"(the largest piece starts at line {main[0] if main else '?'}). Join it unless it "
                "is meant to be a separate piece.",
            )
        )
    # held only through joints the checker cannot confirm: one item for all of them
    held_only_item(report, loose)

    # does it stand
    allw = []
    allv = []
    for p in placed:
        pts, w = p.part.samples()
        if len(pts):
            allw.append(p.to_world(pts))
            allv.append(w)
    base_pts = []
    for ln in grounded:
        pts = bottom_pts[ln]
        if len(pts):
            base_pts.append(pts[pts[:, 1] >= ground_level - GROUND_TOL][:, [0, 2]])
    if allw and base_pts and np.concatenate(base_pts).size:
        world = np.concatenate(allw)
        vols = np.concatenate(allv)
        com = (world * vols[:, None]).sum(0) / vols.sum()
        hull = _hull(np.concatenate(base_pts))
        out = _outside_by(hull, com[[0, 2]])
        if out <= 0:
            report.stands = True
            report.stand_text = (
                f"stands: its centre of mass (x {fmt(round(com[0]))}, z {fmt(round(com[2]))}) is "
                "over "
                "what touches the ground."
            )
        else:
            report.stands = False
            report.issues.append(
                Issue(
                    "problem",
                    "tips over",
                    grounded,
                    f"It would tip over: its centre of mass (x {fmt(round(com[0]))}, y "
                    f"{fmt(round(com[1]))}, z {fmt(round(com[2]))}) is {fmt(round(out, 1))} LDU "
                    f"outside the outline of what touches the ground ({_lines(grounded)}). Widen "
                    "the base on that side or move weight back over it.",
                )
            )
    if movement:
        from bricksnap.lab import movement as moves

        moves.apply(text, report, lib)
    clip_loads(report)
    return report


LOAD_PER_GRIP = 76800.0  # LDU^3 (filled bodies) a clip may carry: a 2 x 4 brick's
LOAD_ONE_GRIP = 1_000_000.0  # LDU^4: held out on one clip, volume times its reach from it


def clip_loads(report: Report) -> None:
    """Parts that reach the ground only through clip grips tested for fit, when they are more
    than a strut, a rail, an aerial or a mirror: a warning of kind "held by clips" naming them,
    and the summary says so. Group the parts joined by anything but clip grips; a group that
    is not on the ground that way but is with them hangs on the clips that cross its edge.
    Its load is the filled volume of its parts that are not thin members (a bar, a bar tube,
    a clip with a grip: ``_bar_lines``, ``_tube_hollows``, ``grip_lines``). It is too much
    when each clip carries more than ``LOAD_PER_GRIP`` (a table on clip-held legs), or when
    one clip holds it and its load times its reach from the clip (to the middle of the load,
    across) is more than ``LOAD_ONE_GRIP`` (a wing held out on one clip)."""
    report.issues = [i for i in report.issues if i.kind != "held by clips"]
    by_line = {p.line: p for p in report.placed}
    clip_fits = [i for i in report.fits if "by the clip of line" in i.text]
    if not clip_fits:
        return
    joints = [i for i in report.issues if i.kind == "joint" and len(i.lines) == 2]

    def grouped(with_clips: bool) -> _Groups:
        g = _Groups(list(by_line))
        for link in report.links:
            g.join(link.holder, link.held)
        for i in joints:
            if with_clips or i not in clip_fits:
                g.join(i.lines[0], i.lines[1])
        return g

    ground = set(report.grounded)
    held = [c for c in grouped(True).groups() if ground & set(c)]
    for comp in grouped(False).groups():
        if ground & set(comp) or not any(set(comp) <= set(c) for c in held):
            continue
        cross = [i for i in clip_fits if (i.lines[0] in comp) != (i.lines[1] in comp)]
        load = [
            by_line[n]
            for n in comp
            if not (
                _bar_lines(by_line[n]) or _tube_hollows(by_line[n]) or grip_lines(by_line[n].key)
            )
        ]
        vol = sum(p.part.volume() for p in load)
        if not cross or vol <= 0:
            continue
        too_much = vol / len(cross) > LOAD_PER_GRIP
        if len(cross) == 1:
            i = cross[0]
            clip = by_line[i.lines[0] if i.lines[0] not in comp else i.lines[1]]
            mid = (
                sum(
                    p.to_world((p.part.bbox_min + p.part.bbox_max) / 2) * p.part.volume()
                    for p in load
                )
                / vol
            )
            reach = float(np.linalg.norm((mid - clip.pos)[[0, 2]]))
            too_much = too_much or vol * reach > LOAD_ONE_GRIP
        if too_much:
            lines = sorted(comp)
            report.issues.append(
                Issue(
                    "warning",
                    "held by clips",
                    lines,
                    f"{_lines(lines).capitalize()} reach the ground only through "
                    f"{'a clip' if len(cross) == 1 else f'{len(cross)} clips'}. A clip holds a "
                    "strut or a rail; the checker cannot judge whether clips will carry this "
                    "much. If it has to bear weight, hold it with studs or a pin.",
                )
            )


def held_only_item(
    report: Report, loose: list[list[int]] | None = None, proven: list[list[int]] | None = None
) -> None:
    """Put (or replace, or remove) the one "held by unchecked joints" item: the parts that are
    not loose, yet reach a part on the ground only through joints the checker cannot confirm.
    Stud links count as confirmed, and so does each group of parts in ``proven`` (the parts of
    a module the movement check has proved: ``movement``). ``loose`` defaults to the loose
    problems already in the report."""
    if loose is None:
        loose = [i.lines for i in report.problems if i.kind == "loose"]
    groups = _Groups([p.line for p in report.placed])
    for link in report.links:
        groups.join(link.holder, link.held)
    for fit in report.fits:  # a joint tested for fit holds as a stud does
        groups.join(fit.lines[0], fit.lines[1])
    for own in proven or []:
        for ln in own[1:]:
            if ln in groups.parent and own[0] in groups.parent:
                groups.join(own[0], ln)
    gset = set(report.grounded)
    only: list[int] = []
    for comp in groups.groups():
        if gset & set(comp) or any(set(comp) <= set(c) for c in loose):
            continue
        only.extend(comp)
    report.issues = [i for i in report.issues if i.kind != "held by unchecked joints"]
    if only:
        n = len(only)
        report.issues.append(
            Issue(
                "not checked",
                "held by unchecked joints",
                sorted(only),
                f"{_lines(only).capitalize()} {'is' if n == 1 else 'are'} joined to "
                "what stands on the ground only through those joints.",
            )
        )


_JOINT_KINDS = ("pin", "axle", "pin hole", "axle hole", "wheel pin", "wheel hole", "clip", "hinge")


def _sunk_may_apply(said: str) -> bool:
    """Only where the older words give no move: no part under it, resting on a part with no
    stud going in, or floating over a part with no studs there (never "move it down by N onto
    studs ...", which is a real fix)."""
    return " Fix: move it down by" not in said and (
        " There is no part under it." in said
        or "no stud goes into it" in said
        or "lowering it would not hold it either" in said
    )


def _sunk_words(part: Placed, into: Placed, lab) -> str:  # type: ignore[no-untyped-def]
    """The words for a loose part sunk into a held one, or "" (``_way_out``). Never for a part
    with a pin or an axle, or into a part with a hole one could go into: those go into one
    another by design, and the library may only lack the joint."""
    for p in (part, into):
        if any(c.kind in _JOINT_KINDS for c in p.part.others):
            return ""
    out = _way_out(part, into)
    if out is None:
        return ""
    move, dist = out
    return (
        f" It is sunk {fmt(round(dist, 1))} LDU into {lab(into)}: it is inside that part, not "
        f"on it. Fix: move line {part.line} by ({_vec(move)}), to {_vec(part.pos + move)}, and "
        "attach it."
    )


def _way_out(part: Placed, into: Placed) -> tuple[np.ndarray, float] | None:
    """When the real shapes of ``part`` go into ``into`` (``solid.in_the_way``) by no more than
    ``WAY_OUT`` LDU: the shortest move along one of the six axes after which they only touch,
    as (world move, distance); None otherwise. Along each axis the move to try (to 0.5 LDU)
    takes the part's trailing face (its box) past the far side of the shared voxels, or is
    the shared piece's thickness; shortest first, each try one real-shape measurement, at
    most ``WAY_TRIES`` of them."""
    from bricksnap.lab import solid

    a, b = (part.key, part.pos, part.m), (into.key, into.pos, into.m)
    if not solid.in_the_way(a, b):
        return None
    pts = solid.shared_points(a, b)
    if not len(pts):
        return None
    axes = [UP, -UP] + [np.eye(3)[k] * sgn for k in (0, 2) for sgn in (1.0, -1.0)]
    lo, hi = part.part.bbox_min, part.part.bbox_max
    corners = part.to_world(
        np.array(
            [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        )
    )
    tries = []
    for n, ax in enumerate(axes):
        along = pts @ ax
        # moved along ax, its trailing face must pass the far side of what they share; when
        # its box is not its shape, the shared piece's own thickness is the other guess
        guesses = (along.max() - float((corners @ ax).min()), along.max() - along.min() + 0.5)
        for rank, guess in enumerate(guesses):
            dist = float(np.ceil(guess * 2) / 2)
            if 0 < dist <= WAY_OUT:
                tries.append((rank, dist, n, ax))
    for _, dist, _, ax in sorted(tries, key=lambda t: t[:3])[:WAY_TRIES]:
        if solid.interference((part.key, part.pos + ax * dist, part.m), b)[0] <= 0.5:
            return ax * dist, float(dist)  # out: what they share is a face, a voxel thick
    return None


def _loose_text(comp, placed, by_line, bottom_pts, lab) -> str:  # type: ignore[no-untyped-def]
    first = by_line[comp[0]]
    others = [p for p in placed if p.line not in comp]
    pts = np.concatenate(
        [bottom_pts[ln] for ln in comp if len(bottom_pts[ln])] or [np.zeros((0, 3))]
    )
    who = lab(first) if len(comp) == 1 else f"{_lines(comp)} (from {lab(first)})"
    text = (
        f"Loose: {who} {'is' if len(comp) == 1 else 'are'} not connected to anything that "
        "reaches the ground; nothing holds " + ("it" if len(comp) == 1 else "them") + "."
    )
    if not len(pts) or not others:
        return text
    low_y = float(pts[:, 1].max())
    lo, hi = pts[:, [0, 2]].min(0), pts[:, [0, 2]].max(0)
    best = None
    for o in others:
        opts = bottom_pts[o.line]
        if not len(opts):
            continue
        tops = opts[len(opts) // 2 :]  # the second half are the column tops
        under = tops[
            (tops[:, 0] >= lo[0] - 1)
            & (tops[:, 0] <= hi[0] + 1)
            & (tops[:, 2] >= lo[1] - 1)
            & (tops[:, 2] <= hi[1] + 1)
            & (tops[:, 1] >= low_y - 1)
        ]
        if len(under):
            top_y = float(under[:, 1].min())
            if best is None or top_y < best[1]:
                best = (o, top_y)
    if best is not None:
        gap = best[1] - low_y
        below = best[0]
        studs_there = [
            k
            for k, st in enumerate(numbered_studs(below.part), 1)
            if (below.m @ st.axis)[1] < -0.98
            and lo[0] - 1 <= below.to_world(st.pos)[0] <= hi[0] + 1
            and lo[1] - 1 <= below.to_world(st.pos)[2] <= hi[1] + 1
        ]
        if gap > 0.5:
            text += (
                f" Its underside is at y {fmt(round(low_y, 1))} and the part below it, "
                f"{lab(below)}, has its top at y {fmt(round(best[1], 1))}: it floats "
                f"{fmt(round(gap, 1))} LDU above it."
            )
            if studs_there:
                text += (
                    f" Fix: move it down by {fmt(round(gap, 1))} (add {fmt(round(gap, 1))} to "
                    f"its y) onto stud{'s' if len(studs_there) > 1 else ''} "
                    f"{', '.join(map(str, studs_there[:6]))} of line {below.line}, or attach it "
                    "with place."
                )
            else:
                text += (
                    f" Line {below.line} has no studs under it there, so lowering it would not "
                    "hold it either: attach it to a part with studs (place does this)."
                )
        else:
            text += (
                f" It rests on {lab(best[0])} but no stud goes into it: check that the studs "
                "line up with its sockets (and that the part below has studs there)."
            )
    else:
        text += " There is no part under it."
    return text
