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
  joins by pins, axles, bars or clips (they go into other parts) it is a warning that says so.
- Connections: part A holds part B when a stud of A reaches into B's filled body pointing
  into B's underside (B's own "up" against the stud), with the stud's base at B's bottom
  (within ``SEAT_TOL`` LDU) and on B's stud grid (the centres of its stud cells, within
  ``GRID_TOL`` LDU), or when a stud of A sits in an open tube or ring of B (the stud in the
  centre tube of a 2 x 2 brick, a plant leaf's ring). Any orientation works: studs on the
  side of a part are checked the same way. A stud that reaches into B in any other way is a
  problem, with the reason: off B's grid (by how much, and where to move B to), not pressed
  home (the gap), pushed in too far, or into B's side or top.
- Joints the geometry cannot confirm: when a part joins by clips, bars, pins, axles, hinges,
  ball joints or wheel pins (from its primitives or its name) and touches another part with
  no stud connection between them, the pair is listed as "not checked" and counts as joined
  when deciding what is loose.
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
  is the one it got before joints existed except for one deliberate change: a turntable's
  top and base (both named "Turntable") are a "not checked" joint, as a tyre on its wheel
  is, instead of an overlap problem.
  ``check(text, movement=False)`` leaves this out (used to find what rides on a joint).
- A summary line: "N parts of M kinds, K problems ...". With no problems it says so in one
  line; with joints it also says how many move freely, and how many problems are about
  movement.

Rough by design (and the report says so once): the filled body misses walls thinner than
about 2 LDU and treats side holes as solid; overlaps near arches, overhangs and parts that go
into one another can be false alarms; joints other than studs are never confirmed; whether a
connection is strong (one stud or eight) is listed but not judged.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from bricksnap.lab.ldraw_lib import (
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
            tail = "no problems: every part is held, nothing overlaps, and it stands."
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
        section(
            "NOT CHECKED (joints the checker cannot confirm; make sure each is a real one):",
            self.unchecked,
            MAX_OTHERS,
            False,
        )
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


def _stud_hits(a: Placed, b: Placed) -> list[_StudHit]:
    """What each stud of ``a`` does to ``b``."""
    out: list[_StudHit] = []
    studs = numbered_studs(a.part)
    if not studs or not b.part.has_body():
        return out
    phase = b.part.socket_phase()
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
        w = p.to_world(c.pos)
        if region is not None:
            gap = np.maximum(np.maximum(region[0] - w, w - region[1]), 0)
            if float(np.linalg.norm(gap)) <= 8:
                ends.add(end)
        elif q.part.inside(q.to_local(w + _NEAR), tol=-0.5).any():
            ends.add(end)
    families = {_GEO_END[c.kind].rstrip("+-") for c in p.part.others if c.kind in _GEO_END}
    desc = p.part.description.lower()
    for word in p.part.name_joint_words():
        end = _NAME_END.get(word)
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
            word = _END_WORDS[x.rstrip("+-")]
            if word not in found:
                found.append(word)
    return found


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
    for a, b in pairs:
        linked = False
        for holder, held in ((a, b), (b, a)):
            hits = _stud_hits(holder, held)
            good = [h for h in hits if h.ok]
            bad = [h for h in hits if not h.ok]
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
            base = (
                f"{lab(a)} and {lab(b)} occupy the same space: about {int(round(vol, -1))} LDU^3, "
                f"{share:.0%} of the smaller part, {where}."
            )
            if joint:
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
            elif vol < SMALL_OVERLAP and share < SMALL_SHARE:
                report.issues.append(
                    Issue("warning", "overlap", [a.line, b.line], "Slight overlap: " + base)
                )
            elif (min(a.line, b.line), max(a.line, b.line)) not in stud_problem_pairs:
                report.issues.append(
                    Issue(
                        "problem",
                        "overlap",
                        [a.line, b.line],
                        base + " Move one of them so they only touch.",
                    )
                )
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
