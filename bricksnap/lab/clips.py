"""Putting a clip on a bar, and a strut between two bars: the builder's ``clip`` and ``strut``
tools (guide mode only; ``tools``). Thin members (struts, rails, aerials) at an angle are what
a builder cannot place by hand: the matrix has to turn a clip's grip onto a bar's line.

CONTRACT
- ``clip(text, part, colour, onto, which, angle, slide)``: the LDraw line that puts ``part``
  (a part with a clip the checker measures: a primitive in ``validate.CLIP_GRIP``) with its
  grip on bar ``which`` (1 = the first) of line ``onto``'s part (``validate._bar_lines``: a
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
BORE_IN = (3.0, 10.0)  # LDU a bar end may be in a bar tube's bore (``validate._bar_fits``)
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


def _frame(a_local, a_world, b_local, b_world) -> np.ndarray:
    def basis(a, b):
        a = np.asarray(a, float) / np.linalg.norm(a)
        b = np.asarray(b, float) - (np.asarray(b, float) @ a) * a
        b = b / np.linalg.norm(b)
        return np.stack([a, b, np.cross(a, b)], 1)

    return basis(a_world, b_world) @ basis(a_local, b_local).T


_GRIPS: dict[str, tuple[np.ndarray, np.ndarray] | None] = {}


def grip_line(key: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Where a clip part grips a bar, in its own frame: (a point on the bar's centre line, its
    direction), for its first clip primitive in ``CLIP_GRIP``: the place nearest the
    primitive where a bar 4 LDU in radius would have the clip round it and in none of it
    (``validate._grip_holds``'s ring test on the part alone); None for a part with no such
    clip, or none found."""
    if key in _GRIPS:
        return _GRIPS[key]
    from bricksnap.lab import solid
    from bricksnap.lab.ldraw_lib import library
    from bricksnap.lab.validate import CLIP_GRIP, GRIP_HALF, GRIP_R, GRIP_RING, _perp

    found = None
    part = library().part(key)
    clips = [c for c in part.others if c.kind == "clip" and c.prim in CLIP_GRIP]
    if clips:
        c = clips[0]
        sol = solid.solid(key)

        def ring(x: np.ndarray, d: np.ndarray, r: float) -> int:
            u, v = _perp(d)
            ang = np.linspace(0, 2 * math.pi, 12, endpoint=False)
            pts = x + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
            return int(sol.inside(pts, deep=False).sum())

        a = c.axis / np.linalg.norm(c.axis)
        u, v = _perp(a)
        if CLIP_GRIP[c.prim] == "along":
            dirs = [a]
        else:
            dirs = [math.cos(t) * u + math.sin(t) * v for t in np.radians(np.arange(0, 180, 15))]
        best = None
        for d in dirs:
            s1, s2 = _perp(d)
            for p in np.arange(-8, 8.1, 0.5):
                for q in np.arange(-8, 8.1, 0.5):
                    x = c.pos + p * s1 + q * s2
                    rings = [ring(x + t * d, d, GRIP_R) for t in (-GRIP_HALF, 0.0, GRIP_HALF)]
                    inner = [ring(x + t * d, d, 3.0) for t in (-GRIP_HALF, 0.0, GRIP_HALF)]
                    if min(rings) < GRIP_RING or max(inner) > 0:
                        continue
                    # most clip round it; then square with the part's own axes; then nearest
                    score = (
                        sum(rings),
                        round(float(np.abs(d).max()), 3),
                        -float(np.linalg.norm(x - c.pos)),
                    )
                    if best is None or score > best[0]:
                        best = (score, x, d)
        if best is not None:
            found = (best[1], best[2] / np.linalg.norm(best[2]))
    _GRIPS[key] = found
    return found


def _parse(text: str):  # type: ignore[no-untyped-def]
    from bricksnap.lab.ldraw_lib import library
    from bricksnap.lab.validate import Report, parse

    lib = library()
    return {p.line: p for p in parse(text, lib, Report(colours=lib.colours()))}, lib


def _target(text: str, onto: int, which: int):  # type: ignore[no-untyped-def]
    from bricksnap.lab.validate import _bar_lines

    placed, lib = _parse(text)
    q = placed.get(onto)
    if q is None:
        raise ClipError(f"line {onto} is not a part of the model.")
    bars = _bar_lines(q)
    if not bars:
        raise ClipError(
            f"line {onto} ({q.key} {q.part.description}) has no bar or handle the checker can "
            "find: clip onto a handle (2540, 48336, 60478, 18649, 26047) or a bar (87994, "
            "30374, 63965a)."
        )
    if not 1 <= which <= len(bars):
        raise ClipError(
            f"line {onto} has {len(bars)} bar{'s' if len(bars) != 1 else ''} or handle"
            f"{'s' if len(bars) != 1 else ''}: which is 1 to {len(bars)}."
        )
    return q, bars[which - 1], lib


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

    key = norm_name(part)
    if not key.endswith(".dat"):
        key += ".dat"
    q, (e0, e1), lib = _target(text, onto, which)
    if lib.resolve(key) is None:
        raise ClipError(f"there is no part {part[:40]} in the library.")
    grip = grip_line(key)
    if grip is None:
        raise ClipError(
            f"{key} ({lib.part(key).description}) has no clip the checker measures. Clips "
            "that work: 60897, 4085a (vertical C-clips), 61252, 11476, 63868 (horizontal), "
            "11090 (a bar tube with a clip), 15712's tile clip is measured but cannot be placed "
            "by this tool; the thick U-clip 4085c is only counted as joined."
        )
    length = float(np.linalg.norm(e1 - e0))
    u = (e1 - e0) / length
    t = min(max(length / 2 + slide, GRIP_HALF), length - GRIP_HALF)
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
    return Clipped(ldraw_line(colour, pos, R, key), pos, R, middle, u, points, bore)


def strut(text: str, onto_a: int, onto_b: int, colour: int, which_a: int = 1, which_b: int = 1):
    """The three lines of a strut (see the contract): an 11090 on each bar, then the bar."""
    from bricksnap.lab.place import ldraw_line

    ends = []
    for onto, which, other in ((onto_a, which_a, onto_b), (onto_b, which_b, onto_a)):
        _, (e0, e1), _ = _target(text, onto, which)
        _, (f0, f1), _ = _target(text, other, which_b if onto == onto_a else which_a)
        ends.append(((e0 + e1) / 2, (e1 - e0) / np.linalg.norm(e1 - e0), (f0 + f1) / 2))
    placed = []
    for (mid, u, there), onto, which in zip(
        ends, (onto_a, onto_b), (which_a, which_b), strict=True
    ):
        toward = there - mid
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
    lo, hi = BORE_IN
    for key, length, name in BARS:
        if length - 2 * hi <= gap <= length - 2 * lo:
            d = (mb - ma) / gap
            R = _frame([0, 1, 0], d, [1, 0, 0], [1, 0, 0] if abs(d[0]) < 0.9 else [0, 0, 1])
            bar = ldraw_line(colour, (ma + mb) / 2 - R @ np.array([0, length / 2, 0]), R, key)
            return placed[0], placed[1], bar, name, gap
    spans = ", ".join(f"{n} {L - 2 * hi:g} to {L - 2 * lo:g}" for _, L, n in BARS)
    near = min(
        ((L - 2 * hi) - gap if gap < L - 2 * hi else gap - (L - 2 * lo), n) for _, L, n in BARS
    )
    raise ClipError(
        f"the bores would be {gap:.1f} LDU apart; the bars close these distances: {spans}. "
        f"Move one end by {near[0]:.1f} LDU along the line between them (nearest: the {near[1]})."
    )
