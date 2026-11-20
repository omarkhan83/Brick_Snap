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
- Joints the geometry cannot confirm: when a part joins by clips, bars, pins, axles, hinges,
  ball joints or wheel pins (from its primitives or its name) and touches another part with
  no stud connection between them, the pair is listed as "not checked" and counts as joined
  when deciding what is loose. An axle or a bar handle counts along its whole length
  (``Connector.points``), other connectors at their own place. An axle the library draws
  with axle-hole primitives (``ldraw_lib``) joins only when its line runs along a hole of
  the other part (parallel within ``AXLE_DEG`` degrees, within ``AXLE_LDU`` LDU, the hole's
  reach and the axle's length sharing ``AXLE_IN`` LDU): an axle through a wheel turned
  across it is an overlap, and a bush beyond the axle's end is not on it. A "Bar
  Tube" is a tube a bar goes into (a clip), not a bar. Also listed as "not checked" joints:
  - a bar in a hollow (``_bar_in``): an open stud (``ldraw_lib.OPEN_STUD``; its hollow is the
    stud, 4 LDU from base to tip), an open tube, an axle hole (a round brick's middle), a
    pin hole or the hollow end of a pin. All of these must hold:
    1. In: from 1 LDU outside one end of the hollow inwards the other part's real solid is
       on the axis without a break, and nowhere inside the hollow reaches the ring
       ``BAR_RING`` LDU round it (no thicker than a bar, 4 LDU in radius), for at least the
       hollow's depth (an open stud's 4; ``BAR_DEPTH`` for a longer hollow) less
       ``BAR_PLAY`` (1 LDU, as a stud may sit 1 LDU short of home). A bar in by 2 LDU or
       floating above the hollow is not held.
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
- What is loose: groups of parts with no path of connections to a part on the ground
  (y = 0 at its lowest point, within ``GROUND_TOL``), each with what is below it and how far;
  groups that stand on the ground but are not joined to the rest (a warning); parts below the
  ground; no part on the ground at all.
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
- The NOT CHECKED section lists the joints (the first ``MAX_OTHERS``, then a count of the
  rest by kind) and then, never cut, the line naming the parts held only through them.

Rough by design (and the report says so once): the filled body misses walls thinner than
about 2 LDU and treats side holes as solid (an overlap it misses is not looked for on the
real shapes); interference thinner than 1.5 LDU is not reported; joints other than studs
are never confirmed (a bar's grip in its hollow is not judged); whether a connection is
strong (one stud or eight) is listed but not judged.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

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
DETAIL_PARTS = 40  # up to this many parts, the report says what holds each one
MAX_PROBLEMS = 40
MAX_OTHERS = 25
UP = np.array([0.0, -1.0, 0.0])

ROUGH_NOTE = (
    "(The overlap check is rough: it fills each part's hollow underside, so arches, overhangs "
    "and parts that go into one another can give false alarms; joints other than studs are "
    "never confirmed.)"
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
    severity: str  # "problem", "warning", "not checked"
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
            tail = "no problems: every part is held, nothing overlaps, and it stands."
            if held is not None:
                m = len(held.lines)
                tail = (
                    f"no problems: every part is held ({m} of them only by joints the checker "
                    "cannot confirm), nothing overlaps, and it stands."
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
                "NOT CHECKED (joints the checker cannot confirm; make sure each is a real one):"
            )
            out.extend(f"- {x.text}" for x in joints[:MAX_OTHERS])
            if len(joints) > MAX_OTHERS:
                kinds: dict[str, int] = {}
                for x in joints[MAX_OTHERS:]:
                    m = re.search(r": a (.+?) joint, which|join by a (.+?), which", x.text)
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
            if len(self.placed) <= DETAIL_PARTS:
                for p in self.placed:
                    held = by_held.get(p.line, [])
                    if not held:
                        continue
                    desc = "; ".join(
                        f"{len(x.studs)} stud{'s' if len(x.studs) != 1 else ''} of line "
                        f"{x.holder}" + (f" ({x.how})" if x.how != "on top" else "")
                        for x in held
                    )
                    out.append(f"- line {p.line} is held by {desc}")
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
            if self.stand_text:
                out.append("- " + self.stand_text)
        if self.placed and (self.problems or self.warnings):
            out.append("")
            out.append(ROUGH_NOTE)
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
    kind: str  # "open stud", "tube", "axle hole", "pin hole", "pin"
    p0: np.ndarray  # one end of its axis (world)
    p1: np.ndarray  # the other end


def _hollows(p: Placed, connectors: list[Connector]) -> list[_Hollow]:
    """The hollows among ``connectors`` of ``p`` that a bar can go into, each with the two
    ends of its axis: an open stud from its base to its tip (4 LDU), an open tube from its
    open end to its closed one, a hole or a pin's bore along the primitive's own reach."""
    out: list[_Hollow] = []
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
                out.append(
                    _Hollow(
                        c.kind,
                        p.to_world(c.pos + a * c.axis),
                        p.to_world(c.pos + b * c.axis),
                    )
                )
    order = ("open stud", "axle hole", "pin", "pin hole", "tube")
    return sorted(out, key=lambda h: order.index(h.kind))


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
        on = sb.inside(local, deep=False)
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
        on_out = sb.inside(held.to_local(line), deep=False)
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


def _held_bar(a: Placed, b: Placed, held: dict[int, np.ndarray]) -> tuple[str, np.ndarray] | None:
    """A bar of b in a hollow of a, or of a in b (see ``_bar_in``); the bar's line and the
    hollow's axis go into ``held``."""
    for holder, bar in ((a, b), (b, a)):
        got = _bar_in(holder, bar)
        if got is not None:
            held[bar.line] = got[1]
            return got
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
        # an axle or a handle along its whole length; other connectors at their own place
        w = p.to_world(c.points() if c.kind in ("axle", "bar handle") else c.pos[None, :])
        if region is not None:
            gap = np.maximum(np.maximum(region[0] - w, w - region[1]), 0)
            if float(np.linalg.norm(gap, axis=1).min()) <= 8:
                ends.add(end)
        elif q.part.inside(
            q.to_local((w[:, None, :] + _NEAR[None]).reshape(-1, 3)), tol=-0.5
        ).any():
            ends.add(end)
    families = {_GEO_END[c.kind].rstrip("+-") for c in p.part.others if c.kind in _GEO_END}
    desc = p.part.description.lower()
    for word in p.part.name_joint_words():
        end = _NAME_END.get(word)
        if word == "bar" and "bar tube" in desc:
            end = "bar-"  # a "Bar Tube" is a tube a bar goes into, not a bar
        if end is None or end.rstrip("+-") in families:
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
    checked_groups = _Groups([p.line for p in placed])
    stud_problem_pairs: set[tuple[int, int]] = set()
    bar_held: dict[int, np.ndarray] = {}  # parts held as a bar in a hollow -> its axis
    pin_holes: dict[tuple[float, ...], int] = {}  # (part, hole) -> the part whose stud is in it
    slight: list[tuple[Placed, Placed, int, str]] = []  # slight overlaps: (a, b, issue, text)
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
                    bar = h.joint
                    if h.joint[0] != "stud in a pin hole":
                        bar_held[held.line] = h.joint[1]
            if good:
                linked = True
                hows = {h.how for h in good}
                report.links.append(
                    Link(holder.line, held.line, [h.stud for h in good], ", ".join(sorted(hows)))
                )
                groups.join(holder.line, held.line)
                checked_groups.join(holder.line, held.line)
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
            elif joint:
                report.issues.append(
                    Issue(
                        "not checked",
                        "joint",
                        [a.line, b.line],
                        f"{short(a)} and {short(b)}: a {' or '.join(joint[:3])} joint, which the "
                        f"checker cannot confirm (they share about {int(round(vol, -1))} LDU^3 "
                        "where one goes into the other). Counted as joined.",
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
            elif (
                min(a.line, b.line),
                max(a.line, b.line),
            ) not in stud_problem_pairs and _really_overlap(a, b):
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
            report.issues.append(
                Issue(
                    "not checked",
                    "joint",
                    [a.line, b.line],
                    f"{short(a)} and {short(b)}: a {bar[0]} joint, which the checker cannot "
                    + (
                        "confirm (the stud points along the hole's axis). "
                        if bar[0].startswith("stud")
                        else "confirm (the bar is on the hollow's axis, in far enough and no "
                        "thicker than a bar). "
                    )
                    + "Counted as joined.",
                )
            )
            groups.join(a.line, b.line)
            joint_pairs.add((a.line, b.line))
        # joints that cannot be checked
        words = [] if linked or (a.line, b.line) in joint_pairs else _joint_words(a, b, None)
        if words and (_touches(a, b) or _touches(b, a)):
            report.issues.append(
                Issue(
                    "not checked",
                    "joint",
                    [a.line, b.line],
                    f"{short(a)} and {short(b)} touch where they can join by a "
                    f"{' or '.join(words[:3])}, which the checker cannot confirm. Counted as "
                    "joined.",
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
    for comp in sorted(loose, key=lambda c: c[0]):
        report.issues.append(
            Issue("problem", "loose", comp, _loose_text(comp, placed, by_line, bottom_pts, lab))
        )
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
    only_unchecked: list[int] = []
    for comp in checked_groups.groups():
        if gset & set(comp):
            continue
        if any(set(comp) <= set(c) for c in loose):
            continue
        only_unchecked.extend(comp)
    if only_unchecked:
        n = len(only_unchecked)
        report.issues.append(
            Issue(
                "not checked",
                "held by unchecked joints",
                sorted(only_unchecked),
                f"{_lines(only_unchecked).capitalize()} {'is' if n == 1 else 'are'} joined to "
                "what stands on the ground only through those joints.",
            )
        )

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
    return report


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
