"""Putting a clip on a bar, and a strut between two bars: the builder's ``clip`` and ``strut``
tools (guide mode only; ``tools``). Thin members (struts, rails, aerials) at an angle are what
a builder cannot place by hand: the matrix has to turn a clip's grip onto a bar's line.

CONTRACT
- ``clip(text, part, colour, onto, which, angle, slide)``: the LDraw line that puts ``part``
  (a part with a clip the checker measures: one with a closed grip, ``validate.grip_lines``)
  with its grip on bar ``which`` (1 = the first) of line ``onto``'s part (``validate._bar_lines``: a
  handle's bar, or a bar part's long axis), at ``slide`` LDU along the bar from the bar's
  middle, turned ``angle`` degrees about the bar's line. At angle 0 the part points up (away
  from the ground; a bar standing upright: towards -z), and the angle turns it about the bar
  by the right-hand rule. Where the grip is in the part's own frame comes from its shape
  (``grip_line``: the bar's place where the clip is round it, nearest the primitive). The
  result says where the part now points and, for a bar tube with a clip (11090), the line of
  its bore: where a bar pushed into it would run. It never changes a model; ``ClipError``
  says in plain words why a part cannot be clipped there.
- ``strut(text, onto_a, onto_b, colour, which_a, which_b)``: an 11090 on each of the two bars,
  each turned so its bore faces the other, and the bar (``BARS``) whose length closes the
  distance between the bores: in each by ``BORE_IN`` (from the hollow's least depth to its
  full 10 LDU). When none closes it, ``ClipError`` gives the distance, the distances the bars
  close and how far to move one end.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

BARS = (("87994.dat", 60.0, "Bar 3L"), ("30374.dat", 80.0, "Bar 4L"))  # straight, no stop
BORE_IN = (3.5, 10.0)  # LDU a bar end is in a bar tube's bore: the checker's fit (3 is not
# enough on its 0.5 LDU cells) to the bore's stop
TUBE_MOUTH = 30.0  # LDU from 11090's grip to its bore's mouth
TUBE = "11090.dat"  # Bar Tube with Clip: its clip at its origin, its bore from y 30 to 20


class ClipError(ValueError):
    """Why a part cannot be clipped where it was asked to go."""


@dataclass
class Clipped:
    line: str  # the LDraw line
    pos: np.ndarray
    m: np.ndarray
    grip: np.ndarray  # the grip's middle, world
    along: np.ndarray  # the bar's direction, world
    points: np.ndarray  # which way the part points from the bar, world
    bore: tuple[np.ndarray, np.ndarray] | None  # a bar tube's bore: (mouth, inward), world
    clamped: bool = False  # slide went past the bar's end and was cut to it


def _frame(a_local, a_world, b_local, b_world) -> np.ndarray:
    def basis(a, b):
        a = np.asarray(a, float) / np.linalg.norm(a)
        b = np.asarray(b, float) - (np.asarray(b, float) @ a) * a
        b = b / np.linalg.norm(b)
        return np.stack([a, b, np.cross(a, b)], 1)

    return basis(a_world, b_world) @ basis(a_local, b_local).T


def grip_line(key: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Where a clip part grips a bar, in its own frame (its first grip): the checker's own
    ``validate.grip_lines``, so the tool places a clip where the checker measures it."""
    from bricksnap.lab.validate import grip_lines

    grips = grip_lines(key)
    return grips[0] if grips else None


def _parse(text: str):  # type: ignore[no-untyped-def]
    from bricksnap.lab.ldraw_lib import library
    from bricksnap.lab.validate import Report, parse

    lib = library()
    return {p.line: p for p in parse(text, lib, Report(colours=lib.colours()))}, lib


_AXES: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}


def bar_axes(key: str) -> list[tuple[np.ndarray, np.ndarray]]:
    """The bars of a part the library draws with no handle primitive (23443's handle), found
    in its real shape: lines along its own axes, a whole LDU apart, where for 6 LDU or more
    its solid fills 10 of 12 points 2 LDU round the line and none at ``GRIP_R`` (a bar 4 LDU
    in radius); each as its two ends, in the part's own frame."""
    if key in _AXES:
        return _AXES[key]
    from bricksnap.lab import solid
    from bricksnap.lab.ldraw_lib import library
    from bricksnap.lab.validate import GRIP_R, _clip_ring

    part = library().part(key)
    sol = solid.solid(key)
    lo, hi = part.bbox_min, part.bbox_max
    found = []
    for k in range(3):
        d = np.eye(3)[k]
        a, b = [j for j in range(3) if j != k]
        for x in np.arange(math.ceil(lo[a]), hi[a] + 0.01, 1.0):
            for y in np.arange(math.ceil(lo[b]), hi[b] + 0.01, 1.0):
                run: list[float] = []
                for t in [*np.arange(lo[k], hi[k] + 0.01, 1.0), None]:
                    ok = False
                    if t is not None:
                        c = np.zeros(3)
                        c[k], c[a], c[b] = t, x, y
                        ok = _clip_ring(sol, c, d, 2.0) >= 10 and not _clip_ring(sol, c, d, GRIP_R)
                    if ok:
                        run.append(float(t if t is not None else 0.0))
                        continue
                    if len(run) >= 7:
                        e0, e1 = np.zeros(3), np.zeros(3)
                        e0[k], e0[a], e0[b] = run[0], x, y
                        e1[k], e1[a], e1[b] = run[-1], x, y
                        found.append((e0, e1))
                    run = []
    # neighbours one LDU apart are one bar: the middle of each bunch, its longest reach
    bunches: list[list[tuple[np.ndarray, np.ndarray]]] = []
    for e0, e1 in found:
        mid = (e0 + e1) / 2
        for b in bunches:
            f0, f1 = b[0]
            same_way = abs(float(np.dot(e1 - e0, f1 - f0))) > 0.99 * float(
                np.linalg.norm(e1 - e0) * np.linalg.norm(f1 - f0)
            )
            if same_way and float(np.linalg.norm(mid - (f0 + f1) / 2)) <= 3:
                b.append((e0, e1))
                break
        else:
            bunches.append([(e0, e1)])
    bars: list[tuple[np.ndarray, np.ndarray]] = []
    for b in bunches:
        d = (b[0][1] - b[0][0]) / float(np.linalg.norm(b[0][1] - b[0][0]))
        centre = np.mean([(e0 + e1) / 2 for e0, e1 in b], axis=0)
        ts = [float(np.dot(e - centre, d)) for e0, e1 in b for e in (e0, e1)]
        bars.append((centre + min(ts) * d, centre + max(ts) * d))
    _AXES[key] = bars
    return bars


def _target(text: str, onto: int, which: int):  # type: ignore[no-untyped-def]
    from bricksnap.lab.validate import _bar_lines

    placed, lib = _parse(text)
    q = placed.get(onto)
    if q is None:
        raise ClipError(f"line {onto} is not a part of the model.")
    bars = _bar_lines(q) or [(q.to_world(e0), q.to_world(e1)) for e0, e1 in bar_axes(q.key)]
    if not bars:
        raise ClipError(
            f"line {onto} ({q.key} {q.part.description}) has no bar or handle the checker can "
            "find: clip onto a handle (2540, 48336, 60478, 18649, 26047, 23443) or a bar "
            "(87994, 30374, 63965a)."
        )
    if not 1 <= which <= len(bars):
        raise ClipError(
            f"line {onto} has {len(bars)} bar{'s' if len(bars) != 1 else ''} or handle"
            f"{'s' if len(bars) != 1 else ''}: which is 1 to {len(bars)}."
        )
    return q, bars[which - 1], lib


CLIPS_THAT_WORK = "60897 (vertical), 61252, 11476, 63868 (horizontal), 15712 (a tile), 11090"


def clip(
    text: str,
    part: str,
    colour: int,
    onto: int,
    which: int = 1,
    angle: float = 0.0,
    slide: float = 0.0,
) -> Clipped:
    """See the contract."""
    from bricksnap.lab.ldraw_lib import norm_name
    from bricksnap.lab.place import ldraw_line
    from bricksnap.lab.validate import GRIP_HALF, Placed, _tube_hollows

    if not (math.isfinite(angle) and math.isfinite(slide)):
        raise ClipError("angle and slide must be ordinary numbers.")
    if not isinstance(colour, int) or colour < 0:
        raise ClipError("colour must be an LDraw colour code, 0 or more.")
    if onto < 1 or which < 1:
        raise ClipError("onto is a line number and which is 1 or more.")
    key = norm_name(part)
    if not key.endswith(".dat"):
        key += ".dat"
    q, (e0, e1), lib = _target(text, onto, which)
    if lib.resolve(key) is None:
        raise ClipError(f"there is no part {part[:40]} in the library.")
    grip = grip_line(key)
    if grip is None:
        raise ClipError(
            f"{key} ({lib.part(key).description}) has no clip the checker can measure (a clip "
            f"closed round a bar). Clips it measures: {CLIPS_THAT_WORK}. A thick U-clip "
            "(4085c) is only counted as joined."
        )
    length = float(np.linalg.norm(e1 - e0))
    u = (e1 - e0) / length
    want = length / 2 + slide
    t = min(max(want, GRIP_HALF), length - GRIP_HALF)
    middle = e0 + t * u
    up = np.array([0.0, -1.0, 0.0])
    if abs(float(up @ u)) > 0.99:
        up = np.array([0.0, 0.0, -1.0])
    up = up - (up @ u) * u
    up /= np.linalg.norm(up)
    a = math.radians(angle)
    points = math.cos(a) * up + math.sin(a) * np.cross(u, up)
    gx, gd = grip
    p = lib.part(key)
    centre = (p.bbox_min + p.bbox_max) / 2 - gx
    out = centre - (centre @ gd) * gd  # from the grip towards the part's middle
    if float(np.linalg.norm(out)) < 1e-6:
        out = np.cross(gd, [1.0, 0, 0]) if abs(gd[0]) < 0.9 else np.cross(gd, [0, 1.0, 0])
    R = _frame(gd, u, out, points)
    pos = middle - R @ gx
    placed = Placed(0, colour, pos, R, key, key, p, 0)
    bores = _tube_hollows(placed)
    bore = None
    if bores:
        h = bores[0]
        d = h.p1 - h.p0
        bore = (h.p0, d / np.linalg.norm(d))
    clamped = abs(t - want) > 1e-6
    return Clipped(ldraw_line(colour, pos, R, key), pos, R, middle, u, points, bore, clamped)


def strut(text: str, onto_a: int, onto_b: int, colour: int, which_a: int = 1, which_b: int = 1):
    """The three lines of a strut (see the contract): an 11090 on each bar, then the bar.
    Refused (``ClipError``, adding nothing) unless the two bars are parallel within
    ``CLIP_DEG`` and level across (their grips on one line square to both), the bores then
    facing along that line, and a bar in ``BARS`` in each bore by ``BORE_IN``; the refusal
    says which line to move or turn, by what vector, so that a second call closes it."""
    from bricksnap.lab.place import ldraw_line
    from bricksnap.lab.validate import CLIP_DEG

    _, (a0, a1), _ = _target(text, onto_a, which_a)
    _, (b0, b1), _ = _target(text, onto_b, which_b)
    ga, gb = (a0 + a1) / 2, (b0 + b1) / 2
    ua, ub = (a1 - a0) / np.linalg.norm(a1 - a0), (b1 - b0) / np.linalg.norm(b1 - b0)
    if abs(float(ua @ ub)) < math.cos(math.radians(CLIP_DEG)):
        off = math.degrees(math.acos(min(1.0, abs(float(ua @ ub)))))
        raise ClipError(
            f"the bars of lines {onto_a} and {onto_b} are {off:.0f} degrees apart: a strut's "
            f"two tubes turn about parallel bars. Turn line {onto_b} so its bar runs along "
            f"({_v(ua)}), then call strut again."
        )
    span = gb - ga
    side = float(span @ ua) * ua  # along the bars: the tubes would not face each other
    across = span - side
    dist = float(np.linalg.norm(across))
    lo, hi = BORE_IN
    reach = 2 * TUBE_MOUTH  # each bore's mouth is this far from its grip
    fits = [
        (length, name, key)
        for key, length, name in BARS
        if length - 2 * hi <= dist - reach <= length - 2 * lo
    ]
    if float(np.linalg.norm(side)) > 0.5 or not fits:
        d = across / dist if dist > 1e-6 else np.cross(ua, [0.0, -1.0, 0.0])
        best = min(
            (abs(length - (lo + hi) - (dist - reach)), length, name) for _, length, name in BARS
        )
        target = best[1] - (lo + hi) + reach  # the grips this far apart: in each by the middle
        move = -side + (target - dist) * d
        raise ClipError(
            f"the bores would be {dist - reach:.1f} LDU apart"
            + (
                f" and {float(np.linalg.norm(side)):.1f} LDU off one line"
                if np.linalg.norm(side) > 0.5
                else ""
            )
            + "; the bars close these distances: "
            + ", ".join(f"{n} {L - 2 * hi:g} to {L - 2 * lo:g}" for _, L, n in BARS)
            + f". Move line {onto_b} by ({_v(move)}) for the {best[2]}, then call strut again."
        )
    length, name, key = fits[0]
    placed = []
    for g, u, there, onto, which in (
        (ga, ua, gb, onto_a, which_a),
        (gb, ub, ga, onto_b, which_b),
    ):
        toward = there - g
        toward = toward - (toward @ u) * u
        up = np.array([0.0, -1.0, 0.0]) if abs(u[1]) < 0.99 else np.array([0.0, 0.0, -1.0])
        up = up - (up @ u) * u
        up /= np.linalg.norm(up)
        angle = math.degrees(math.atan2(float(np.cross(u, up) @ toward), float(up @ toward)))
        placed.append(clip(text, TUBE, colour, onto, which, angle))
    bores = [c.bore for c in placed]
    if bores[0] is None or bores[1] is None:
        raise ClipError(f"{TUBE} has no bore the checker can find.")
    ma, mb = bores[0][0], bores[1][0]
    gap = float(np.linalg.norm(mb - ma))
    d = (mb - ma) / gap
    R = _frame([0, 1, 0], d, [1, 0, 0], [1, 0, 0] if abs(d[0]) < 0.9 else [0, 0, 1])
    bar = ldraw_line(colour, (ma + mb) / 2 - R @ np.array([0, length / 2, 0]), R, key)
    return placed[0], placed[1], bar, name, gap


def _v(v) -> str:  # type: ignore[no-untyped-def]
    return " ".join(f"{round(float(x), 3) + 0.0:g}" for x in v)
