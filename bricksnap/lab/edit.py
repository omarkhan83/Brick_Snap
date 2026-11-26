"""Editing a model in bulk: clear a box, fill a box, mirror lines, turn a group (research
prototype).

CONTRACT (tests in tests/test_lab.py; ``turn`` in tests/test_lab_turn.py)

Coordinates are the model's LDraw coordinates (LDU; y points down, the ground is y = 0).

``parts_in_box(text, lo, hi, mode="centre") -> list[Placed]``
- The parts of the model (lines the checker can read) in the box from corner ``lo`` to
  corner ``hi``. ``mode`` "centre": the centre of the part's body box is in the box (the
  default: a part mostly inside goes, a neighbour that only reaches in stays); "inside": its
  whole body box is in the box (within 1 LDU); "touching": its body box meets the box.

``fill(text, at, size, colour, top="studs", hollow=False) -> Filled``
- Ordinary bricks and plates that fill a box, interlocked so they hold together, chosen by
  BrickSnap's own solver (``bricksnap.layout.solve`` on a ``Design`` of ``size`` cells: studs
  in x, studs in z, plates up) and written by ``bricksnap.ldraw.placement_to_ldraw``, then
  moved so the box's corner with the smallest x and z, at its bottom, is ``at`` (LDU;
  ``at`` y is the bottom of the box, normally the top of what it stands on; the box goes up
  from there). x and z of ``at`` must be multiples of 10 (whole or half studs): to sit on a
  part's studs the box's edges must lie halfway between studs, so a corner is a stud's x
  and z minus 10.
- ``top="tiles"``: the top layer is plates turned into tiles of the same size; a plate with
  no tile of its size (2 x 6, 2 x 8) is covered by two tiles side by side, and only one
  that cannot be stays a plate (the reply says so). The solver is made to give the
  top layer plates of their own by colouring that layer differently while it solves.
- ``hollow=True``: only walls one stud thick around the outside (open top and bottom);
  needs at least 3 by 3 studs.
- Steps: the solver's steps, each ending in ``0 STEP``.
- ``Filled``: the lines, the studs left free on top (positions), notes.

``centre_x(text) -> (text, shift)``
- The model moved along x so the middle of its parts' bodies is at x = 0 (the plane
  ``mirror`` uses), by a multiple of 10 LDU so that every stud grid stays a stud grid;
  only the x of part lines changes, and the x of each joint line's axis point
  (``joints.shifted``). Returns the moved text and the shift.

``mirror(text, lines, plane_x=0.0) -> list[Mirrored]``
- For each line, a copy on the other side of the plane x = ``plane_x``. A part is its own
  mirror image when its geometry mirrored about a plane through its body (across its own x
  or its own z) matches itself (``matches``: at least 93% of the filled-body sample points
  land inside the other and every stud lands on a stud); then the copy is the same part
  with a new position and rotation (still a rotation: nothing is mirrored in the file). A
  part that is not: the part whose description is the same with "Left" and "Right" swapped
  is looked up and used when its geometry matches the mirror image; otherwise the line is
  refused with the reason. A part lying across the plane whose copy would land on itself is
  not copied.

``turn(text, lines, axis, quarter, about=None, then_move=None, onto=None) -> Turned``
- The parts on ``lines`` (part lines the checker can read; none in a joint) turned together
  as one rigid piece by ``quarter`` (0 to 3) quarter turns about the model's ``axis`` ("x",
  "y", "z"; ``quarter_turns``: the right-hand rule with y down, so about x one turn tips up to
  -z, about z up to +x, about y it is ``place``'s turn) through ``about`` (default the middle
  of the box their bodies span), then moved by ``then_move`` (LDU), or instead by the move
  that puts socket ``own_socket`` (default 1, ``place.sockets``) of the group's line
  ``own_line`` (default its first) on stud ``stud`` of ``line`` outside the group (``onto``),
  as ``place`` puts a socket on a stud; refused, naming the quarter turns that would do, when
  after the turn that socket does not face the way the stud points. Every part gets the same
  rotation and move, keeps its line number, colour and name; every other line is unchanged.
- The model is then checked (``validate.check``, no movement). Refused (``EditError``, in
  plain words, nothing returned) when a part of the group and one outside it would share space
  (a problem of kind "overlap", or a "stud" problem other than a gap), saying which lines,
  where the group would be and the checker's words, or when the group would reach below the
  ground; also when it would move nothing.
- ``Turned``: the new text, the group's lines, the rotation and move (each point p goes to
  r p + t), the box the group's bodies now span, the way its up now points, a sentence saying
  how it was turned, and the checker's report.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from bricksnap.lab.ldraw_lib import Library, Part, fmt, library
from bricksnap.lab.place import ldraw_line
from bricksnap.lab.validate import Placed, Report, parse

S = np.diag([-1.0, 1.0, 1.0])  # the mirror x -> -x
MATCH = 0.93


def _placed(text: str, lib: Library) -> list[Placed]:
    report = Report(colours=lib.colours())
    return parse(text, lib, report)


def world_box(p: Placed) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = p.part.bbox_min, p.part.bbox_max
    corners = np.array(
        [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
    )
    w = p.to_world(corners)
    return w.min(0), w.max(0)


# ---- clearing a box -----------------------------------------------------------------------


def parts_in_box(
    text: str, lo: np.ndarray, hi: np.ndarray, mode: str = "centre", lib: Library | None = None
) -> list[Placed]:
    lib = lib or library()
    lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
    out = []
    for p in _placed(text, lib):
        a, b = world_box(p)
        if mode == "inside":
            ok = bool(np.all(a >= lo - 1) and np.all(b <= hi + 1))
        elif mode == "touching":
            ok = bool(np.all(a < hi) and np.all(b > lo))
        else:
            c = (a + b) / 2
            ok = bool(np.all(c >= lo) and np.all(c <= hi))
        if ok:
            out.append(p)
    return out


# ---- filling a box ------------------------------------------------------------------------


@dataclass
class Filled:
    lines: list[str] = field(default_factory=list)
    free_studs: list[tuple[float, float, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    parts: int = 0


class EditError(ValueError):
    pass


def fill(
    at: tuple[float, float, float],
    size: tuple[int, int, int],
    colour: int,
    top: str = "studs",
    hollow: bool = False,
) -> Filled:
    from bricksnap.catalog import load_catalog
    from bricksnap.layout import solve
    from bricksnap.ldraw import placement_to_ldraw
    from bricksnap.types import EMPTY, Design

    x0, y0, z0 = (float(v) for v in at)
    w, d, h = (int(v) for v in size)
    if not (1 <= w <= 32 and 1 <= d <= 32 and 1 <= h <= 48):
        raise EditError(
            "size is studs in x (1 to 32), studs in z (1 to 32) and plates up (1 to 48)."
        )
    if abs(x0 / 10 - round(x0 / 10)) > 1e-6 or abs(z0 / 10 - round(z0 / 10)) > 1e-6:
        raise EditError(
            "the corner's x and z must be multiples of 10: a box sitting on studs has its "
            "edges halfway between studs, so its corner is a stud's x and z minus 10."
        )
    if top not in ("studs", "tiles"):
        raise EditError('top is "studs" or "tiles".')
    if hollow and (w < 3 or d < 3):
        raise EditError("a hollow box needs at least 3 by 3 studs (walls one stud thick).")
    catalog = load_catalog()
    colours = np.full((w, d, h), EMPTY, dtype=np.int16)
    colours[:] = colour
    if hollow:
        colours[1:-1, 1:-1, :] = EMPTY
    stand_in = 71 if colour != 71 else 72
    if top == "tiles":
        colours[:, :, h - 1][colours[:, :, h - 1] != EMPTY] = stand_in
    build = solve(Design(colors=colours), catalog)
    out = Filled()
    tiles: dict[tuple[int, int], Any] = {}
    for t in catalog.of_kind("tile"):  # the first of a size is the plain one (3069b, not 2412b)
        tiles.setdefault((t.sx, t.sz), t)
    kept_plates = 0
    lib = library()
    step = None
    for pl in build.parts:
        if step is not None and pl.step != step:
            out.lines.append("0 STEP")
        step = pl.step
        part = catalog.parts[pl.part]
        name = part.ldraw_file
        (px, py, pz), m = placement_to_ldraw(pl, catalog)
        pos = np.array([px + x0, py + y0, pz + z0])
        mat = np.array(m, dtype=float).reshape(3, 3)
        if top == "tiles" and pl.z == h - 1 and part.kind == "plate":
            pieces = _tiles_for(part.sx, part.sz, tiles)
            if pieces:
                # tiles share the plate's origin (the centre of the top face); a plate with
                # no tile of its size is covered by two tiles side by side along its length
                for tile, centre in pieces:
                    out.lines.append(
                        ldraw_line(colour, pos + mat @ np.array([centre, 0.0, 0.0]), mat, tile)
                    )
                continue
            kept_plates += 1
        out.lines.append(ldraw_line(colour, pos, mat, name))
        if pl.z + catalog.footprint(pl)[2] == h:
            lp = lib.part(name)
            for s in lp.top_studs():
                wpos = mat @ s.pos + pos
                out.free_studs.append(
                    (round(float(wpos[0]), 1), round(float(wpos[1]), 1), round(float(wpos[2]), 1))
                )
    if out.lines:
        out.lines.append("0 STEP")
    out.parts = len(build.parts)
    if kept_plates:
        out.notes.append(
            f"{kept_plates} top plate(s) have no tile of their size, so they stay plates."
        )
    return out


def _tiles_for(sx: int, sz: int, tiles: dict[tuple[int, int], Any]) -> list[tuple[str, float]]:
    """Tiles covering a plate of sx by sz studs: (file, centre along its x in LDU)."""
    if (sx, sz) in tiles:
        return [(tiles[(sx, sz)].ldraw_file, 0.0)]
    for first in (4, 3, 2):
        rest = sx - first
        if rest > 0 and (first, sz) in tiles and (rest, sz) in tiles:
            a = -10.0 * sx + 10.0 * first
            b = 10.0 * sx - 10.0 * rest
            return [(tiles[(first, sz)].ldraw_file, a), (tiles[(rest, sz)].ldraw_file, b)]
    return []


# ---- mirroring ----------------------------------------------------------------------------


def _local_mirror(axis: str) -> np.ndarray:
    return np.diag([-1.0, 1.0, 1.0]) if axis == "x" else np.diag([1.0, 1.0, -1.0])


def _mirror_points(pts: np.ndarray, axis: str, c: float) -> np.ndarray:
    out = np.array(pts, dtype=float, copy=True)
    k = 0 if axis == "x" else 2
    out[:, k] = 2 * c - out[:, k]
    return out


def matches(a: Part, b: Part, axis: str, c: float) -> bool:
    """True when part b is part a mirrored across the plane (its own) ``axis`` = c."""
    pa, _ = a.samples()
    pb, _ = b.samples()
    if not len(pa) or not len(pb):
        return False
    if b.inside(_mirror_points(pa, axis, c), tol=0.0).mean() < MATCH:
        return False
    if a.inside(_mirror_points(pb, axis, c), tol=0.0).mean() < MATCH:
        return False
    sa = np.array([s.pos for s in a.studs]) if a.studs else np.zeros((0, 3))
    sb = np.array([s.pos for s in b.studs]) if b.studs else np.zeros((0, 3))
    if len(sa) != len(sb):
        return False
    if len(sa):
        ma = _mirror_points(sa, axis, c)
        dist = np.linalg.norm(ma[:, None, :] - sb[None, :, :], axis=2).min(1)
        if dist.max() > 1.5:
            return False
    return True


def mirror_of(part: Part, lib: Library) -> tuple[Part, str, float] | None:
    """(the part that is ``part``'s mirror image, axis, c) or None. ``part`` itself when it
    is its own mirror image; else its Left/Right counterpart when the geometry agrees."""
    candidates = [part]
    desc = part.description
    if re.search(r"\b(left|right)\b", desc, re.I):
        swapped = re.sub(
            r"\b(left|right)\b",
            lambda m: (
                {"left": "right", "right": "left"}[m.group(0).lower()].capitalize()
                if m.group(0)[0].isupper()
                else {"left": "right", "right": "left"}[m.group(0).lower()]
            ),
            desc,
            flags=re.I,
        )
        from bricksnap.lab.search import load_index

        for e in load_index().entries:
            if e["description"].lower() == swapped.lower():
                candidates.append(lib.part(e["name"]))
    for b in candidates:
        for axis in ("x", "z"):
            k = 0 if axis == "x" else 2
            c = float(part.bbox_min[k] + b.bbox_max[k]) / 2
            c = round(c * 2) / 2
            if matches(part, b, axis, c):
                return b, axis, c
    return None


@dataclass
class Mirrored:
    line: int
    new_line: str | None
    note: str


def mirror(
    text: str, lines: list[int], plane_x: float = 0.0, lib: Library | None = None
) -> list[Mirrored]:
    lib = lib or library()
    by_line = {p.line: p for p in _placed(text, lib)}
    out: list[Mirrored] = []
    for n in lines:
        p = by_line.get(n)
        if p is None:
            out.append(
                Mirrored(n, None, f"line {n} is not a part line the checker can read; not copied.")
            )
            continue
        found = mirror_of(p.part, lib)
        if found is None:
            out.append(
                Mirrored(
                    n,
                    None,
                    f"line {n} ({p.key} {p.part.description}) is not its own mirror image and "
                    "the library has no part with Left and Right swapped in its name that "
                    "matches; build that side yourself.",
                )
            )
            continue
        b, axis, c = found
        lm = _local_mirror(axis)
        m2 = S @ p.m @ lm
        k = np.zeros(3)
        k[0 if axis == "x" else 2] = 2 * c
        t2 = S @ p.pos + np.array([2 * plane_x, 0.0, 0.0]) + S @ p.m @ k
        if (
            np.allclose(t2, p.pos, atol=0.5)
            and np.allclose(m2, p.m, atol=1e-6)
            and b.name == p.part.name
        ):
            out.append(
                Mirrored(
                    n, None, f"line {n} lies across the plane and is its own copy; not copied."
                )
            )
            continue
        new = ldraw_line(p.colour, t2, m2, b.name)
        what = (
            "its own mirror image"
            if b.name == p.part.name
            else f"mirrored as {b.name} ({b.description})"
        )
        out.append(
            Mirrored(
                n,
                new,
                f"line {n} ({p.key}): {what}, at {' '.join(fmt(v) for v in np.round(t2, 3))}",
            )
        )
    return out


def centre_x(text: str, lib: Library | None = None) -> tuple[str, float]:
    lib = lib or library()
    placed = _placed(text, lib)
    if not placed:
        return text, 0.0
    boxes = [world_box(p) for p in placed]
    lo = min(float(a[0]) for a, _ in boxes)
    hi = max(float(b[0]) for _, b in boxes)
    shift = -round((lo + hi) / 2 / 10) * 10.0
    if shift == 0:
        return text, 0.0
    out = []
    for raw in text.splitlines():
        tok = raw.split()
        if len(tok) >= 15 and tok[0] == "1":
            try:
                tok[2] = fmt(float(tok[2]) + shift)
                raw = " ".join(tok)
            except ValueError:
                pass
        out.append(raw)
    from bricksnap.lab.joints import shifted

    return shifted("\n".join(out) + "\n", shift), shift


# ---- turning a group ----------------------------------------------------------------------

_QUARTER_ABOUT = {
    "x": np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]]),
    "y": np.array([[0, 0, 1.0], [0, 1.0, 0], [-1.0, 0, 0]]),
    "z": np.array([[0, -1.0, 0], [1.0, 0, 0], [0, 0, 1.0]]),
}
MAX_GROUP = 400


def quarter_turns(axis: str, k: int) -> np.ndarray:
    """``k`` quarter turns about the model's ``axis`` by the right-hand rule (y down): about x,
    one turn tips up (-y) to -z; about y, +x goes to -z (place's ``turn``, clockwise seen from
    above); about z, up goes to +x. Whole numbers."""
    return np.linalg.matrix_power(_QUARTER_ABOUT[axis], k % 4)


@dataclass
class Turned:
    text: str  # the model with the group's lines rewritten
    lines: list[int]  # the group's part lines, in order
    r: np.ndarray  # the rotation: each point p of the group goes to r @ p + t
    t: np.ndarray
    lo: np.ndarray  # the box the group's bodies span now
    hi: np.ndarray
    up_now: str  # the way the group's up (-y) now points
    how: str  # a sentence: about what point it turned, or which socket is on which stud
    report: Report


def turn(
    text: str,
    lines: list[int],
    axis: str,
    quarter: int,
    about: Sequence[float] | None = None,
    then_move: Sequence[float] | None = None,
    onto: dict[str, int] | None = None,
    lib: Library | None = None,
) -> Turned:
    from bricksnap.lab.joints import parse as parse_joints
    from bricksnap.lab.ldraw_lib import direction_word
    from bricksnap.lab.validate import check

    lib = lib or library()
    if axis not in _QUARTER_ABOUT:
        raise EditError('axis is "x", "y" or "z": the model axis to turn the group about.')
    if quarter not in (0, 1, 2, 3):
        raise EditError("quarter_turns is 0, 1, 2 or 3.")
    if then_move is not None and onto is not None:
        raise EditError(
            "give onto (the tool works out the move) or then_move (you give it), not both."
        )
    group = list(dict.fromkeys(lines))
    if not group:
        raise EditError("name the lines of the group, such as [12, 13, 14].")
    if len(group) > MAX_GROUP:
        raise EditError(f"turn at most {MAX_GROUP} lines at a time.")
    rows = text.splitlines()
    by_line = {p.line: p for p in _placed(text, lib)}
    for n in group:
        if not 1 <= n <= len(rows):
            raise EditError(f"there is no line {n} (the model has {len(rows)} lines).")
        if n not in by_line:
            raise EditError(
                f"line {n} is not a part the checker can read ('{rows[n - 1][:50]}'): name only "
                "part lines."
            )
    for j in parse_joints(text)[0]:
        mine = sorted(set(group) & set(j.fixed + j.moving))
        if mine:
            raise EditError(
                f"line {mine[0]} is part of the joint '{j.name}': turn moves parts, not joints. "
                "Turn the group without it, then put the moving part in again."
            )
    parts = [by_line[n] for n in group]
    boxes = [world_box(p) for p in parts]
    lo0 = np.min([a for a, _ in boxes], axis=0)
    hi0 = np.max([b for _, b in boxes], axis=0)
    r = quarter_turns(axis, quarter)
    centre = np.array(about, dtype=float) if about is not None else (lo0 + hi0) / 2
    t = centre - r @ centre
    ways = ("one quarter turn", "two quarter turns", "three quarter turns")
    turned = f"{ways[quarter - 1]} about {axis}" if quarter else "no turn"
    how = f"{turned}, about the point ({_pt(centre)})" + (
        " (the middle of its box)" if about is None else ""
    )
    if onto is not None:
        t, how = _onto(by_line, group, r, onto, turned)
    elif then_move is not None:
        move = np.array(then_move, dtype=float)
        t = t + move
        how += f", then moved by ({_pt(move)})"
    if quarter == 0 and not np.any(np.abs(t) > 1e-9):
        raise EditError("that moves nothing: give quarter_turns, then_move or onto.")
    new_rows = list(rows)
    for p in parts:
        name = " ".join(rows[p.line - 1].split()[14:])
        new_rows[p.line - 1] = ldraw_line(p.colour, r @ p.pos + t, r @ p.m, name)
    new_text = "\n".join(new_rows) + "\n"
    report = check(new_text, movement=False)
    mine = set(group)
    now = [world_box(p) for p in report.placed if p.line in mine]
    lo = np.min([a for a, _ in now], axis=0)
    hi = np.max([b for _, b in now], axis=0)
    into = [  # sharing space: an overlap, or a stud that hits a part instead of a socket
        i
        for i in report.problems
        if (i.kind == "overlap" or (i.kind == "stud" and "not pressed home" not in i.text))
        and len(mine & set(i.lines)) == 1
        and len(set(i.lines)) == 2
    ]
    if into:
        first = into[0]
        a = next(n for n in first.lines if n in mine)
        b = next(n for n in first.lines if n not in mine)
        more = f", and {len(into) - 1} more such" if len(into) > 1 else ""
        raise EditError(
            f"Not turned: so turned, the group (now x {_span(lo[0], hi[0])}, y "
            f"{_span(lo[1], hi[1])}, z {_span(lo[2], hi[2])}) would go into the rest of the "
            f"model: its line {a} into line {b} ({by_line[b].key} "
            f"{by_line[b].part.description}){more}. The checker: {first.text} The model is "
            "unchanged: turn it the other way, move it clear, or press it on another stud."
        )
    low = float(hi[1])  # y points down: the group's lowest point
    if low > 0.5:
        raise EditError(
            f"Not turned: so turned, the group would reach {fmt(round(low, 1))} LDU below the "
            "ground (y = 0). The model is unchanged: move it up (then_move with a negative y) "
            "or turn it the other way."
        )
    up_now = direction_word(r @ np.array([0.0, -1.0, 0.0]))
    return Turned(new_text, group, r, t, lo, hi, up_now, how, report)


def _pt(v: np.ndarray) -> str:
    return ", ".join(fmt(round(float(x), 1) + 0.0) for x in v)


def _span(a: float, b: float) -> str:
    return f"{fmt(round(float(a), 1) + 0.0)}..{fmt(round(float(b), 1) + 0.0)}"


def _onto(
    by_line: dict[int, Placed],
    group: list[int],
    r: np.ndarray,
    onto: dict[str, int],
    turned: str,
) -> tuple[np.ndarray, str]:
    """The move that puts a socket of one of the group's parts, after the turn, on a stud of
    the model (as ``place`` puts a socket on a stud), and the sentence saying so."""
    from bricksnap.lab.ldraw_lib import direction_word
    from bricksnap.lab.place import sockets
    from bricksnap.lab.validate import numbered_studs

    line, stud = onto.get("line"), onto.get("stud")
    own_line = onto.get("own_line", group[0])
    own_socket = onto.get("own_socket", 1)
    if not isinstance(line, int) or not isinstance(stud, int):
        raise EditError('onto needs "line" and "stud": the stud of the model to press it on.')
    if line in group:
        raise EditError(f"line {line} is in the group: press the group onto a part outside it.")
    if own_line not in group:
        raise EditError(f"own_line {own_line} is not one of the group's lines.")
    target = by_line.get(line)
    if target is None:
        raise EditError(f"line {line} is not a part the checker can read.")
    studs = numbered_studs(target.part)
    if not 1 <= stud <= len(studs):
        raise EditError(
            f"line {line} ({target.key}) has {len(studs)} studs, numbered 1 to {len(studs)}; "
            f"there is no stud {stud}."
        )
    own = by_line[own_line]
    socks = sockets(own.part)
    if not 1 <= own_socket <= len(socks):
        raise EditError(
            f"line {own_line} ({own.key}) has {len(socks)} sockets, numbered 1 to {len(socks)}; "
            f"there is no socket {own_socket}."
        )
    s = studs[stud - 1]
    base = target.to_world(s.pos)
    d = target.m @ s.axis
    d = d / np.linalg.norm(d)
    takes = r @ own.m @ np.array([0.0, -1.0, 0.0])  # the way a stud in the socket points
    if float(np.dot(takes, d)) < 0.99:
        now = own.m @ np.array([0.0, -1.0, 0.0])
        fits = [
            f"{k} about {ax}"
            for ax in ("x", "y", "z")
            for k in (1, 2, 3)
            if float(np.dot(quarter_turns(ax, k) @ now, d)) > 0.99
        ]
        if float(np.dot(now, d)) > 0.99:
            fits = ["0 (it faces that way as it is)"]
        raise EditError(
            f"with {turned}, socket {own_socket} of line {own_line} takes a stud pointing "
            f"{direction_word(takes)}, but stud {stud} of line {line} points "
            f"{direction_word(d)}. The quarter turns that face it that way: "
            + (", ".join(fits) if fits else "none (the part is not square to the model's axes)")
            + "."
        )
    sock = own.m @ socks[own_socket - 1].pos + own.pos  # the socket before the turn
    t = base - r @ sock
    how = (
        f"{turned}, and socket {own_socket} of line {own_line} pressed on stud {stud} of line "
        f"{line}"
    )
    return t, how
