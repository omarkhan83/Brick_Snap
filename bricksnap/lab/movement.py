"""The movement check: can each thing that should move really move? (research prototype)

CONTRACT (tests in tests/test_moving.py)

``apply(text, report, lib)`` is called by ``validate.check`` at the end of every check. It
reads the model's joints (``joints.parse``) and adds to the report problems (``Issue``
severity "problem", kind "movement"), warnings, one line per joint for the MOVEMENT
section (``report.movement``), how far each joint really goes (``report.reach``: name ->
(low, high) in degrees, or None when it cannot move), and the count of joints that move
(``report.moving_ok``). A model with no joint lines gets nothing from it. (Its report
differs from the one before joints existed in one way: ``validate`` learnt that a
turntable's top and base go into one another by design, so a turntable is a "not checked"
joint there rather than an overlap problem; ``validate``'s own later fixes are its own.)

Geometry: every comparison uses the parts' real shapes WITH their studs (``solid``): a part
is in the way of another when a point of one's real surface is DEEP inside the other's
solid (``solid.GUARANTEE``: every interference deeper than 1 LDU is seen, none shallower
than 0.25 LDU).

Which joints act together (a GROUP): joints whose lines coincide (axes parallel within
``COAXIAL_DEG`` degrees, lines within ``COAXIAL_LDU``) and whose moving sides are joined to
each other act as one hinge: two lid hinges under one lid, a door on a lower and an upper
hinge brick. A hinge pair placed by hand without a joint line (a module's two parts in the
module's places) counts too, so long as a declared joint is on its line. The group is
checked once, its range is what all its joints allow, and ``opened`` turns it once. A
hinge whose line is NOT the group's but which holds the same panel to what stays is
reported as such ("these two hinges do not turn about the same line").

What rides on a group (``riders``): its moving parts, the tyres on its wheels, and every
part joined to them by studs or by a joint the checker cannot confirm, without passing
through its fixed parts or anything standing on the ground (which stays); contacts
touching the group's own parts other than by studs are left out (they are what turns).
Each part goes to the side it is fewer connections away from.

What it reports, naming lines and parts:
- Joint lines that cannot be read; a joint naming a line that is not a part.
- A MODULE joint whose parts are not the module as built (``modules.verify``).
- A joint the builder declared (no MODULE) is accepted only when its turning line can be
  confirmed from the parts (``confirm``): exactly one FIXED part and one MOVING part (plus,
  for a wheel, the tyres on it), not held together by studs, joined by a Technic pin (the
  hinge brick's pin is one) or a wheel pin the checker sees, and every such pin or hole
  where they meet turns about the line given, read from the axis the library records for
  it, within ``AXIS_DEG`` degrees and ``AXIS_LDU`` LDU. A clip, a bar or handle, a finger
  hinge, a ball joint or an axle where they meet is refused in one sentence: the checker
  cannot yet confirm how it turns, so use a module. Otherwise a problem says why, and the
  joint is not checked further.
- Tied: studs (or a joint the checker cannot confirm) holding what moves to what stays,
  including the moving part straight onto the fixed one; or a hinge on another line that
  rides with the group and is the only thing joining part of what rides, standing on the
  ground, to the rest ("the hinge on lines 7, 8 holds the same parts, and these two hinges
  do not turn about the same line").
- A swing: the moving side is turned in steps small enough that no point of it moves more
  than ``ARC`` LDU between two steps (and never more than ``MAX_STEP`` degrees), from 0 to
  each end of the range; at each step every moving surface point is tested against every
  part that stays and every surface point of those parts against the moving parts, and a
  moving point more than ``GROUND_DEPTH`` LDU below the ground (y > 0) stops it too.
  Points already deep inside at rest are left out for that pair (what already goes into
  one another), and for the joint's own two halves the points within the fit radius
  (``KNUCKLE_R``, or a module's own) of the axis. It reports how far it opens.
- A spin or a wheel (all the way round): what it sweeps is the solid of revolution of the
  moving parts' real surfaces, slab by slab (``SLAB`` LDU) along the axis; a part that
  stays is in the way when a surface point of it is more than ``TURN_TOL`` LDU inside it,
  with turning material on both sides of the point along the axis (a face that only
  touches a wheel's end is not in the way). Wheels that hit "rub".
- Wheels: a ROAD wheel has a level axle (within ``LEVEL``) and its tread (the moving parts
  reaching furthest from the axle) within ``SPARE_CLEAR`` LDU of the ground. A wheel whose
  axle is not level and that touches the ground "lies on its side". A level wheel more
  than ``SPARE_CLEAR`` LDU clear of the ground is a spare: it turns, carries nothing, and
  nothing is asked of it. With road wheels, every part touching the ground must ride on a
  wheel joint (a part that looks like a wheel or tyre with no joint is named as such), and
  each road wheel's tread must touch the ground. When all the road wheels are on one axle
  line, another support touching the ground is expected (a trailer's stand, a
  wheelbarrow's legs): a warning says so, not a problem. A spin's moving parts, and a
  wheel's beyond the tyres' tolerance, must not go below the ground as they turn.
- When a joint is free: "'door' (door-hinge-left, lines 12, 13): swings from 0 to 90
  degrees with nothing in the way; 4 parts move with it (lines 13, 20 to 22)".

The grip of a joint (whether a clip holds its bar, whether a hinge holds a lid up) is
never judged: a module's joint is the parts' designed use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from bricksnap.lab import solid as solids
from bricksnap.lab.joints import Joint, parse
from bricksnap.lab.ldraw_lib import fmt

if TYPE_CHECKING:
    from bricksnap.lab.ldraw_lib import Library
    from bricksnap.lab.validate import Placed, Report

ARC = 0.5  # LDU the farthest moving point may travel between two steps of a swing
MAX_STEP = 2.0  # degrees
COARSE = 8  # fine steps in one coarse step
RING = 2.0  # LDU: the rings a body's surface passes through, for skipping far points
GROUND_DEPTH = 1.0
SLAB = 1.0
TURN_TOL = 1.0
KNUCKLE_R = 10.0
AXIS_DEG = 3.0
AXIS_LDU = 1.5
COAXIAL_DEG = 0.5
COAXIAL_LDU = 1.0
LEVEL = 0.05
SPARE_CLEAR = 8.0
GROUND_TOL = 1.5
MAX_NAMED = 4
_CONFIRMED = {"pin", "pin hole", "wheel pin", "wheel hole"}
"""Connector kinds whose turning line the library records and which were checked right: a
Technic pin (and the hinge brick's pin), a pin hole, a wheel pin, a wheel hole."""
_NOT_YET = {
    "clip": "a clip",
    "bar handle": "a bar or handle",
    "hinge": "a finger hinge",
    "ball": "a ball joint",
    "ball socket": "a ball joint",
    "axle": "an axle",
    "axle hole": "an axle",
}


@dataclass
class Verdict:
    joint: Joint
    ok: bool
    riders: list[int] = field(default_factory=list)
    reach: tuple[float, float] | None = None
    text: str = ""
    group: list[Joint] = field(default_factory=list)
    road: bool = False  # a wheel that carries the model


# ---- the graph of what holds what ------------------------------------------------------------


def _graph(report: Report, own: set[int]) -> dict[int, dict[int, str]]:
    adj: dict[int, dict[int, str]] = {p.line: {} for p in report.placed}
    for link in report.links:
        if link.holder in adj and link.held in adj:
            n = len(link.studs)
            how = f"{n} stud{'s' if n != 1 else ''}"
            adj[link.holder][link.held] = how
            adj[link.held][link.holder] = how
    for a, b in _unchecked_pairs(report):
        if a in own or b in own or a not in adj or b not in adj:
            continue
        adj[a].setdefault(b, "a joint the checker cannot confirm")
        adj[b].setdefault(a, "a joint the checker cannot confirm")
    return adj


def _unchecked_pairs(report: Report) -> list[tuple[int, int]]:
    return [
        (i.lines[0], i.lines[1])
        for i in report.issues
        if i.severity == "not checked" and i.kind == "joint" and len(i.lines) == 2
    ]


def _distances(adj: dict[int, dict[int, str]], start: set[int], wall: set[int]) -> dict[int, int]:
    dist = {s: 0 for s in start if s in adj}
    todo = list(dist)
    while todo:
        nxt = []
        for a in todo:
            for b in adj[a]:
                if b in dist or b in wall:
                    continue
                dist[b] = dist[a] + 1
                nxt.append(b)
        todo = nxt
    return dist


@dataclass
class _Sides:
    riders: list[int]
    tied: list[tuple[int, int | None, int | None, str]]  # (part, moving nb, fixed nb, how)


def _sides(report: Report, fixed: set[int], moving: set[int]) -> _Sides:
    """Which parts move with the joint: whatever is joined to its moving parts, whether or not
    it touches the ground (the ground stops a movement only by being in its way)."""
    adj = _graph(report, fixed | moving)
    stays = fixed
    dm = _distances(adj, moving, stays)
    df = _distances(adj, stays, moving)
    inf = math.inf
    ride = sorted(p for p in dm if dm[p] < df.get(p, inf))
    side_m = set(ride)
    side_f = {p for p in df if df[p] < dm.get(p, inf)}
    tied: list[tuple[int, int | None, int | None, str]] = []
    for p in sorted(dm):
        if p in df and dm[p] == df[p]:
            nm = next((b for b in sorted(adj[p]) if b in side_m), None)
            nf = next((b for b in sorted(adj[p]) if b in side_f), None)
            tied.append((p, nm, nf, ""))
    if not tied:
        for a in ride:
            for b, how in sorted(adj[a].items()):
                if b in side_f:
                    tied.append((a, None, b, how))
    return _Sides(ride, tied)


# ---- groups: joints that turn together --------------------------------------------------------


@dataclass
class Group:
    joints: list[Joint]
    at: np.ndarray
    axis: np.ndarray
    fixed: set[int]
    moving: set[int]
    low: float
    high: float
    implicit: list[Joint] = field(default_factory=list)  # hand-placed module pairs on the line

    @property
    def lead(self) -> Joint:
        return self.joints[0]


def coaxial(a: Joint, b: Joint) -> int:
    """+1 or -1 when the two joints turn about the same line (the sign: same or opposite
    direction), else 0."""
    d = float(np.dot(a.axis, b.axis))
    if abs(d) < math.cos(math.radians(COAXIAL_DEG)):
        return 0
    rel = b.at - a.at
    off = float(np.linalg.norm(rel - np.dot(rel, a.axis) * a.axis))
    return (1 if d > 0 else -1) if off <= COAXIAL_LDU else 0


def module_pairs(report: Report, taken: set[int]) -> list[Joint]:
    """Two-part modules placed by hand (their parts in the module's places), as joints."""
    from bricksnap.lab import modules

    out: list[Joint] = []
    by_key: dict[str, list[Placed]] = {}
    for p in report.placed:
        by_key.setdefault(p.key, []).append(p)
    for mod in modules.MODULES.values():
        if len(mod.parts) != 2:
            continue
        fpart, mpart = mod.parts
        for f in by_key.get(fpart.file, []):
            if f.line in taken:
                continue
            rot = f.m @ modules._matrix(fpart.m).T
            pos = f.pos - rot @ np.array(fpart.pos, dtype=float)
            want_pos = rot @ np.array(mpart.pos, dtype=float) + pos
            want_m = rot @ modules._matrix(mpart.m)
            for m in by_key.get(mpart.file, []):
                if m.line in taken or m.line == f.line:
                    continue
                if np.linalg.norm(m.pos - want_pos) <= modules.POS_TOL and (
                    np.abs(m.m - want_m).max() <= modules.ROT_TOL
                ):
                    j = mod.joint(f"lines-{f.line}-{m.line}")
                    j.at = rot @ j.at + pos
                    j.axis = rot @ j.axis
                    j.fixed, j.moving = [f.line], [m.line]
                    out.append(j)
                    taken |= {f.line, m.line}
                    break
    return out


def _tyres(report: Report, joint: Joint) -> list[int]:
    """Tyres sitting on the moving parts of a wheel joint (they turn with it), listed or not."""
    by_line = {p.line: p for p in report.placed}

    def is_tyre(n: int) -> bool:
        return n in by_line and by_line[n].part.description.lower().startswith("tyre")

    rims = {n for n in joint.moving if not is_tyre(n)}
    out = {n for n in joint.moving if is_tyre(n)}
    for a, b in _unchecked_pairs(report):
        for x, y in ((a, b), (b, a)):
            if x in rims and is_tyre(y) and y not in joint.fixed:
                out.add(y)
    return sorted(out)


def make_groups(report: Report, joints: list[Joint]) -> tuple[list[Group], dict[str, Group]]:
    """The groups of the given (valid) joints, in the order of their first joint."""
    taken = {n for j in joints for n in j.fixed + j.moving}
    extra = module_pairs(report, set(taken))
    groups: list[Group] = []
    of: dict[str, Group] = {}
    for j in joints:
        if j.name.lower() in of:
            continue
        moving = set(j.moving) | (set(_tyres(report, j)) if j.kind == "WHEEL" else set())
        g = Group([j], j.at, j.axis, set(j.fixed), moving, j.low, j.high)
        of[j.name.lower()] = g
        groups.append(g)
        if j.turns_freely:
            continue
        grew = True
        while grew:
            grew = False
            pool = [c for c in joints if c.name.lower() not in of] + [
                c for c in extra if c not in g.implicit
            ]
            for c in pool:
                if c.turns_freely:
                    continue
                sign = coaxial(j, c)
                if not sign:
                    continue
                adj = _graph(report, g.fixed | g.moving | set(c.fixed) | set(c.moving))
                reach = _distances(adj, g.moving, g.fixed | set(c.fixed))
                if not any(m in reach for m in c.moving):
                    continue
                g.fixed |= set(c.fixed)
                g.moving |= set(c.moving)
                lo, hi = (c.low, c.high) if sign > 0 else (-c.high, -c.low)
                g.low, g.high = max(g.low, lo), min(g.high, hi)
                if c in extra:
                    g.implicit.append(c)
                else:
                    g.joints.append(c)
                    of[c.name.lower()] = g
                grew = True
    return groups, of


def plan(text: str, report: Report | None = None) -> tuple[list[Group], dict[str, Group]]:
    """The model's groups (for ``joints.opened``), from its valid joints."""
    from bricksnap.lab.validate import check

    report = report or check(text, movement=False)
    joints, _ = parse(text)
    lines = {p.line for p in report.placed}
    ok = [j for j in joints if set(j.fixed + j.moving) <= lines]
    return make_groups(report, ok)


def riders(text: str, joint: Joint, report: Report | None = None) -> list[int]:
    """The lines that turn with the joint (its group's moving parts and what rides on them)."""
    from bricksnap.lab.validate import check

    report = report or check(text, movement=False)
    groups, of = plan(text, report)
    g = of.get(joint.name.lower())
    if g is None:
        return list(joint.moving)
    return _sides(report, g.fixed, g.moving).riders


# ---- geometry about an axis -------------------------------------------------------------------


def _basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    u = axis / np.linalg.norm(axis)
    a = np.array([1.0, 0, 0]) if abs(u[0]) < 0.9 else np.array([0, 0, 1.0])
    e1 = np.cross(u, a)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)  # a turn by +t takes e1 toward e2
    return u, e1, e2


@dataclass
class _Polar:
    a: np.ndarray
    r: np.ndarray
    th: np.ndarray


def _polar(w: np.ndarray, at: np.ndarray, basis: tuple) -> _Polar:  # type: ignore[type-arg]
    u, e1, e2 = basis
    rel = w - at
    return _Polar(rel @ u, np.hypot(rel @ e1, rel @ e2), np.arctan2(rel @ e2, rel @ e1))


def _world(p: _Polar, t: np.ndarray | float, at: np.ndarray, basis: tuple) -> np.ndarray:  # type: ignore[type-arg]
    u, e1, e2 = basis
    th = p.th + t
    return (
        at + np.outer(p.a, u) + (p.r * np.cos(th))[:, None] * e1 + (p.r * np.sin(th))[:, None] * e2
    )


def _corners(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )


class _Body:
    """A part's real shape in the world: its solid, its box, and (when asked) its surface."""

    def __init__(self, p: Placed, lib: Library) -> None:
        self.p = p
        self.lib = lib
        self.solid = solids.solid(p.key, lib)
        lo, hi = self.solid.box() if self.solid.full.size else (p.part.bbox_min, p.part.bbox_max)
        self.box_w = p.to_world(_corners(lo, hi))
        self._surf: np.ndarray | None = None

    @property
    def surf_w(self) -> np.ndarray:
        if self._surf is None:
            self._surf = self.p.to_world(solids.surface(self.p.key, self.lib))
        return self._surf


_BODIES: dict[tuple, _Body] = {}  # type: ignore[type-arg]


def _body(p: Placed, lib: Library) -> _Body:
    key = (p.key, *np.round(p.pos, 4), *np.round(p.m.ravel(), 6))
    b = _BODIES.get(key)
    if b is None:
        if len(_BODIES) > 2000:
            _BODIES.clear()
        b = _BODIES[key] = _Body(p, lib)
    elif b.p is not p:
        b.p = p
    return b


def _span(corners: _Polar, margin: float) -> tuple[float, float] | None:
    """The arc of angles a box covers seen from the axis (start, length), or None when the
    axis passes through or near it (every angle)."""
    if float(corners.r.min()) < 1.0:
        return None
    th = np.sort(np.mod(corners.th, 2 * math.pi))
    gaps = np.diff(np.concatenate([th, [th[0] + 2 * math.pi]]))
    k = int(np.argmax(gaps))
    if gaps[k] < math.pi:  # the box surrounds the axis
        return None
    start = th[(k + 1) % len(th)]
    length = 2 * math.pi - float(gaps[k])
    return float(start - margin), float(length + 2 * margin)


def _in_span(th: np.ndarray, span: tuple[float, float] | None) -> np.ndarray:
    if span is None:
        return np.ones(th.shape, dtype=bool)
    return np.mod(th - span[0], 2 * math.pi) <= span[1]


class _Rings:
    """Which rings (a slab along the axis and a band of distance from it, ``RING`` LDU each,
    grown by one ring each way) a body's surface passes through: a point whose ring is not
    one of them never meets the body as it turns about the axis (its circle would have to
    cross the body's surface)."""

    def __init__(self, p: _Polar) -> None:
        if not len(p.r):
            self.grid = np.zeros((0, 0), dtype=bool)
            self.a0 = self.r0 = 0
            return
        ka = np.floor(p.a / RING).astype(np.int64)
        kr = np.floor(p.r / RING).astype(np.int64)
        self.a0, self.r0 = int(ka.min()) - 1, int(kr.min()) - 1
        g = np.zeros((int(ka.max()) - self.a0 + 2, int(kr.max()) - self.r0 + 2), dtype=bool)
        g[ka - self.a0, kr - self.r0] = True
        grown = g.copy()
        grown[1:, :] |= g[:-1, :]
        grown[:-1, :] |= g[1:, :]
        g2 = grown.copy()
        g2[:, 1:] |= grown[:, :-1]
        g2[:, :-1] |= grown[:, 1:]
        self.grid = g2

    def meets(self, a: np.ndarray, r: np.ndarray) -> np.ndarray:
        if not self.grid.size:
            return np.zeros(len(a), dtype=bool)
        ka = np.floor(a / RING).astype(np.int64) - self.a0
        kr = np.floor(r / RING).astype(np.int64) - self.r0
        ok = (ka >= 0) & (kr >= 0) & (ka < self.grid.shape[0]) & (kr < self.grid.shape[1])
        out = np.zeros(len(a), dtype=bool)
        out[ok] = self.grid[ka[ok], kr[ok]]
        return out


class _Swing:
    """Turn the moving bodies through a range and find the first angle where they meet a
    body that stays, or the ground."""

    def __init__(
        self,
        at: np.ndarray,
        axis: np.ndarray,
        moving: list[_Body],
        still: list[_Body],
        own_moving: set[int],
        own_fixed: set[int],
        fit: float,
    ) -> None:
        self.at, self.basis = at, _basis(axis)
        self.moving, self.own_m, self.own_f, self.fit = moving, own_moving, own_fixed, fit
        self.mp = [_polar(b.surf_w, at, self.basis) for b in moving]
        self.rmax = max((float(p.r.max()) for p in self.mp if len(p.r)), default=1.0)
        alla = np.concatenate([p.a for p in self.mp]) if self.mp else np.zeros(1)
        self.arange = (float(alla.min()) - 2, float(alla.max()) + 2)
        self.still = []
        for b in still:
            c = _polar(b.box_w, at, self.basis)
            centre = b.box_w.mean(0)
            half = float(np.linalg.norm(b.box_w.max(0) - b.box_w.min(0))) / 2
            cp = _polar(centre[None, :], at, self.basis)
            if c.a.max() < self.arange[0] or c.a.min() > self.arange[1]:
                continue
            if float(cp.r[0]) - half > self.rmax + 2:
                continue
            self.still.append((b, c))

    def _first(
        self,
        pts: _Polar,
        target: _Body,
        rings: _Rings,
        dt: float,
        limit: int,
        sign: float,
        near_axis_out: bool,
    ) -> int:
        """The first step k (the turn (k + 1) * dt, times ``sign``) at which a point of
        ``pts``, turned, is deep inside ``target`` at rest; ``limit`` if none before it.
        First on coarse steps (``COARSE`` times longer) against the target grown by more
        than half a coarse step, then on the fine steps around each coarse step that came
        near."""
        if not len(pts.r) or limit <= 0:
            return limit
        tc = _polar(target.box_w, self.at, self.basis)
        keep = rings.meets(pts.a, pts.r)
        if near_axis_out:
            keep &= pts.r >= self.fit
        if not keep.any():
            return limit
        a, r, th = pts.a[keep], pts.r[keep], pts.th[keep]
        inv, pos = target.p.inv, target.p.pos
        u, e1, e2 = self.basis
        m0, mu, m1, m2 = inv @ (self.at - pos), inv @ u, inv @ e1, inv @ e2
        base = m0[None, :] + a[:, None] * mu[None, :]

        def local(i: np.ndarray, t: np.ndarray) -> np.ndarray:
            ang = th[i] + sign * t
            return base[i] + (r[i] * np.cos(ang))[:, None] * m1 + (r[i] * np.sin(ang))[:, None] * m2

        sol = target.solid
        allidx = np.arange(len(r))
        rest = sol.lookup(sol.deep, 0, local(allidx, np.zeros(len(r))))
        live = allidx[~rest]
        if not len(live):
            return limit
        grown, pad = sol.near(COARSE * ARC / 2 + 1.0)
        span = _span(tc, 0.05 + COARSE * dt)
        ncoarse = limit // COARSE + 2
        tcs = np.arange(ncoarse) * COARSE * dt  # coarse turns: 0, C dt, 2 C dt ...
        flagged_i: list[np.ndarray] = []
        flagged_j: list[np.ndarray] = []
        chunk = max(1, 300_000 // len(live))
        for j0 in range(0, ncoarse, chunk):
            tt = tcs[j0 : j0 + chunk]
            ang = th[live][:, None] + sign * tt[None, :]
            ok = _in_span(ang, span)
            if not ok.any():
                continue
            ii, jj = np.nonzero(ok)
            near = sol.lookup(grown, pad, local(live[ii], tt[jj]))
            flagged_i.append(live[ii[near]])
            flagged_j.append(jj[near] + j0)
        if not flagged_i:
            return limit
        fi = np.concatenate(flagged_i)
        fj = np.concatenate(flagged_j)
        if not len(fi):
            return limit
        order = np.argsort(fj, kind="stable")
        fi, fj = fi[order], fj[order]
        best = limit
        offs = np.arange(-COARSE, COARSE + 1)
        start = 0
        step = max(1, 200_000 // len(offs))
        while start < len(fj):
            if (fj[start] - 1) * COARSE > best:
                break
            stop = min(len(fj), start + step)
            ii = np.repeat(fi[start:stop], len(offs))
            kk = (np.repeat(fj[start:stop], len(offs)) * COARSE + np.tile(offs, stop - start)) - 1
            good = (kk >= 0) & (kk < best)
            ii, kk = ii[good], kk[good]
            if len(ii):
                hit = sol.lookup(sol.deep, 0, local(ii, (kk + 1) * dt))
                if hit.any():
                    best = min(best, int(kk[hit].min()))
            start = stop
        return best

    def run(self, sign: int, end: float) -> tuple[float, list[tuple[int, int]], bool]:
        """(how far it turns, in degrees; the (moving line, still line) pairs that meet at
        the first hit; whether the ground stopped it)."""
        dt = min(math.radians(MAX_STEP), ARC / max(self.rmax, 1.0))
        n = max(1, math.ceil(math.radians(end) / dt))
        dt = math.radians(end) / n
        self.step_ldu = dt * max(self.rmax, 1.0)
        ts = np.arange(1, n + 1) * dt
        best = n
        hits: dict[int, list[tuple[int, int]]] = {}
        still_polar = {sb.p.line: _polar(sb.surf_w, self.at, self.basis) for sb, _ in self.still}
        still_rings = {n: _Rings(p) for n, p in still_polar.items()}
        moving_rings = [_Rings(p) for p in self.mp]
        for mb, mp, mr in zip(self.moving, self.mp, moving_rings, strict=True):
            for sb, _ in self.still:
                own = mb.p.line in self.own_m and sb.p.line in self.own_f
                sr = still_rings[sb.p.line]
                k = self._first(mp, sb, sr, dt, min(best + 1, n), sign, own)
                k2 = self._first(still_polar[sb.p.line], mb, mr, dt, min(k + 1, n), -sign, own)
                k = min(k, k2)
                if k <= best and k < n:
                    best = k
                    hits.setdefault(k, []).append((mb.p.line, sb.p.line))
        ground = False
        u, e1, e2 = self.basis
        rr_k = math.hypot(e1[1], e2[1])
        if rr_k > 1e-9:
            phi = math.atan2(e2[1], e1[1])
            total = n * dt
            for mp in self.mp:
                if not len(mp.r):
                    continue
                # y(t) = y0 + r k cos(th + sign t - phi): when does it pass GROUND_DEPTH?
                y0 = self.at[1] + mp.a * u[1]
                amp = mp.r * rr_k
                with np.errstate(divide="ignore", invalid="ignore"):
                    c = (GROUND_DEPTH - y0) / amp
                can = (amp > 1e-9) & (c < 1) & (c > -1)
                if not can.any():
                    continue
                alpha = np.arccos(c[can])
                psi = mp.th[can] - phi
                x = np.mod(psi + math.pi, 2 * math.pi) - math.pi
                now = np.abs(x) < alpha  # already below the ground at rest: not this joint's doing
                if sign > 0:
                    t = np.mod(-alpha - psi, 2 * math.pi)
                else:
                    t = np.mod(psi - alpha, 2 * math.pi)
                t = t[~now]
                if not len(t):
                    continue
                first = float(t.min())
                if first <= total:
                    k = max(0, math.ceil(first / dt) - 1)
                    if k <= best and k < n:
                        if k < best:
                            hits = {}
                        best = k
                        ground = True
        if best >= n:
            return end, [], False
        reached = math.degrees(float(ts[best - 1])) if best > 0 else 0.0
        found = hits.get(best, [])
        return reached, found, ground and not found


class _Envelope:
    """What turns all the way round sweeps (see the contract)."""

    def __init__(
        self,
        at: np.ndarray,
        axis: np.ndarray,
        moving: list[_Body],
        still: list[_Body],
        own_fixed: set[int],
        fit: float,
    ) -> None:
        self.at, self.basis, self.own_f, self.fit = at, _basis(axis), own_fixed, fit
        self.reach: np.ndarray = np.zeros(0)
        self.owner: np.ndarray = np.zeros(0, dtype=np.int64)
        self.k0 = 0
        self.still = still
        pols = [(b.p.line, _polar(b.surf_w, at, self.basis)) for b in moving]
        pols = [(n, p) for n, p in pols if len(p.r)]
        if not pols:
            return
        ks = [np.floor(p.a / SLAB).astype(np.int64) for _, p in pols]
        k0 = int(min(k.min() for k in ks)) - 4
        k1 = int(max(k.max() for k in ks)) + 4
        size = k1 - k0 + 1
        per = np.full((len(pols), size), -np.inf)
        for i, ((_, p), k) in enumerate(zip(pols, ks, strict=True)):
            np.maximum.at(per[i], k - k0, p.r)
        widened = per.copy()
        widened[:, 1:] = np.maximum(widened[:, 1:], per[:, :-1])
        widened[:, :-1] = np.maximum(widened[:, :-1], per[:, 1:])
        self.reach = widened.max(0)
        self.owner = np.array([n for n, _ in pols])[widened.argmax(0)]
        self.k0 = k0
        self.radius = float(np.max(self.reach[np.isfinite(self.reach)]))

    def hits(self) -> list[tuple[int, int, float]]:
        if not len(self.reach):
            return []
        off = int(round(2 * TURN_TOL / SLAB))
        size = len(self.reach)
        found = []
        for b in self.still:
            c = _polar(b.box_w, self.at, self.basis)
            if c.a.max() < self.k0 * SLAB or c.a.min() > (self.k0 + size) * SLAB:
                continue
            centre = b.box_w.mean(0)
            half = float(np.linalg.norm(b.box_w.max(0) - b.box_w.min(0))) / 2
            if float(_polar(centre[None, :], self.at, self.basis).r[0]) - half > self.radius + 1:
                continue
            p = _polar(b.surf_w, self.at, self.basis)
            k = np.floor(p.a / SLAB).astype(np.int64) - self.k0
            inside = (k - off >= 0) & (k + off < size)
            if not inside.any():
                continue
            k, r = k[inside], p.r[inside]
            lim = np.minimum(np.minimum(self.reach[k - off], self.reach[k]), self.reach[k + off])
            depth = lim - r
            if b.p.line in self.own_f:
                depth[r < self.fit] = -np.inf
            worst = int(np.argmax(depth))
            if depth[worst] > TURN_TOL:
                found.append((int(self.owner[k[worst]]), b.p.line, float(depth[worst])))
        return sorted(found, key=lambda t: -t[2])


# ---- confirming a joint the builder declared ---------------------------------------------------


def confirm(j: Joint, report: Report, lib: Library) -> str | None:
    """None when the joint's turning line is confirmed from its parts (see the contract),
    else why not, in plain words."""
    by_line = {p.line: p for p in report.placed}
    tyres = set(_tyres(report, j)) if j.kind == "WHEEL" else set()
    turning = [n for n in j.moving if n not in tyres]
    if len(j.fixed) != 1 or len(turning) != 1:
        return (
            "a joint you declare names exactly one FIXED part and one MOVING part (the two "
            "parts of the joint itself; for a wheel its tyre may be listed too): what is built "
            "on the moving part rides with it by itself"
        )
    f, m = by_line[j.fixed[0]], by_line[turning[0]]
    for a, b in ((f, m), (m, f)):
        if any({x.holder, x.held} == {a.line, b.line} for x in report.links):
            return (
                f"line {m.line} is held to line {f.line} by studs, and parts held by studs do "
                "not turn"
            )
    pairs = {tuple(sorted(p)) for p in _unchecked_pairs(report)}
    if tuple(sorted((f.line, m.line))) not in pairs:
        return (
            f"no pin or wheel pin joins line {f.line} to line {m.line} (parts held by studs do "
            "not turn)"
        )
    cands = []
    for owner, other in ((f, m), (m, f)):
        osurf = other.to_world(solids.surface(other.key, lib))
        for c in owner.part.others:
            w = owner.to_world(c.pos)
            if float(np.min(np.linalg.norm(osurf - w, axis=1))) > 6:
                continue
            cands.append((c, owner.m @ np.asarray(c.axis, dtype=float), w))
    other_kinds = [c.kind for c, _, _ in cands if c.kind in _NOT_YET]
    if other_kinds:
        return (
            f"the checker cannot yet confirm how {_NOT_YET[other_kinds[0]]} turns: use a module "
            "instead"
        )
    cands = [x for x in cands if x[0].kind in _CONFIRMED]
    if not cands:
        return (
            "the turning line cannot be read from these parts (neither has a pin or wheel pin "
            "the library marks where they meet): use a module instead"
        )
    if j.kind == "WHEEL" and not any(c.kind in ("wheel pin", "wheel hole") for c, _, _ in cands):
        return "a wheel turns on a wheel pin, and these parts meet at none"

    def agrees(ax: np.ndarray, w: np.ndarray) -> bool:
        rel = w - j.at
        off = float(np.linalg.norm(rel - np.dot(rel, j.axis) * j.axis))
        ax = ax / np.linalg.norm(ax)
        return (
            abs(float(np.dot(ax, j.axis))) >= math.cos(math.radians(AXIS_DEG)) and off <= AXIS_LDU
        )

    wrong = [(c, ax, w) for c, ax, w in cands if not agrees(ax, w)]
    if not wrong:
        return None
    c, ax, w = wrong[0]
    ax = ax / np.linalg.norm(ax)
    return (
        f"the line given is not the joint's own: the {c.kind} where these parts meet turns about "
        f"the line through ({', '.join(fmt(round(float(v), 1)) for v in w)}) along "
        f"({', '.join(fmt(round(float(v), 3)) for v in ax)}); give AT on that line and AXIS "
        f"along it (within {fmt(AXIS_DEG)} degrees and {fmt(AXIS_LDU)} LDU)"
    )


# ---- words -----------------------------------------------------------------------------------


def _list_lines(nums: list[int]) -> str:
    nums = sorted(nums)
    if not nums:
        return "no lines"
    runs: list[str] = []
    start = prev = nums[0]
    for n in [*nums[1:], None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        if prev == start:
            runs.append(str(start))
        elif prev == start + 1:
            runs.append(f"{start}, {prev}")
        else:
            runs.append(f"{start} to {prev}")
        if n is not None:
            start = prev = n
    word = "line" if len(nums) == 1 else "lines"
    text = ", ".join(runs)
    if len(text) > 120:
        text = text[:117].rsplit(",", 1)[0] + " ..."
    return f"{word} {text}"


def _who(j: Joint, g: Group | None = None) -> str:
    joints = g.joints if g else [j]
    own = sorted(
        {n for x in joints for n in x.fixed + x.moving} | (g.fixed | g.moving if g else set())
    )
    what = j.module or "declared by the builder"
    names = " and ".join(f"'{x.name}'" for x in joints)
    extra = ""
    if g and (len(g.joints) > 1 or g.implicit):
        n = len(g.joints) + len(g.implicit)
        extra = f", {n} hinges on one line acting as one"
    return f"{names} ({what}, {_list_lines(own)}{extra})"


def _problem(report: Report, lines: list[int], text: str) -> None:
    from bricksnap.lab.validate import Issue

    report.issues.append(Issue("problem", "movement", sorted(set(lines)), text))


# ---- the check -------------------------------------------------------------------------------


def apply(text: str, report: Report, lib: Library) -> None:
    from bricksnap.lab import modules
    from bricksnap.lab.validate import Issue

    joints, errors = parse(text)
    if not joints and not errors:
        return
    for n, why in errors:
        _problem(
            report,
            [n],
            f"Line {n} is a joint line that cannot be read: {why}. The form is '0 "
            "!BRICKSNAP JOINT name SWING 0 90 AT x y z AXIS dx dy dz FIXED lines MOVING "
            "lines' (or SPIN or WHEEL without the two angles).",
        )
    by_line = {p.line: p for p in report.placed}
    lab = lambda p: p.label(report.colours)  # noqa: E731
    texts: dict[str, str] = {}
    oks: dict[str, bool] = {}
    report.reach = {}
    valid: list[Joint] = []
    for j in joints:
        who = _who(j)
        missing = [n for n in j.fixed + j.moving if n not in by_line]
        if missing:
            n = missing[0]
            side = "FIXED" if n in j.fixed else "MOVING"
            _problem(
                report,
                [j.line],
                f"The joint {who} on line {j.line} names line {n} as {side}, but line {n} is "
                "not a part of the model (removed, or not a part line). Remove the joint line "
                "or put the part back.",
            )
            texts[j.name], oks[j.name] = (
                f"{who}: names a line that is not a part (see problems).",
                False,
            )
            continue
        why = modules.verify(j, by_line) if j.module else confirm(j, report, lib)
        if why:
            if j.module:
                msg = (
                    f"The joint {who} on line {j.line} says it is the module '{j.module}', but "
                    f"{why}. Put the module in with place_module rather than by hand."
                )
            else:
                msg = f"The joint {who} on line {j.line} is not accepted: {why}."
            _problem(report, [j.line, *j.fixed, *j.moving], msg)
            texts[j.name], oks[j.name] = f"{who}: not checked (see problems).", False
            continue
        valid.append(j)
    groups, of = make_groups(report, valid)
    verdicts: list[Verdict] = []
    for g in groups:
        verdicts.append(_check_group(g, report, by_line, lab, lib, valid))
    wheels = [v for v in verdicts if v.joint.kind == "WHEEL"]
    if wheels and not any(i.kind == "ground" for i in report.issues):
        _on_wheels(report, wheels, by_line, lab)
    for g, v in zip(groups, verdicts, strict=True):
        for k, j in enumerate(g.joints):
            report.reach[j.name] = v.reach
            oks[j.name] = v.ok
            texts[j.name] = (
                v.text
                if k == 0
                else (
                    f"'{j.name}': on the same line as '{g.lead.name}' and holding the same parts: "
                    "checked with it."
                )
            )
    report.movement = [texts[j.name] for j in joints if j.name in texts]
    report.moving_ok = sum(1 for j in joints if oks.get(j.name))
    _fold_module_joints(report, [v for v in verdicts if v.ok])
    if any(not j.module for j in valid):
        report.issues.append(
            Issue(
                "warning",
                "movement",
                [j.line for j in valid if not j.module],
                "A joint you declared yourself is checked about the line of the pin where its "
                "parts meet; whether that joint grips is not checked.",
            )
        )


def _fold_module_joints(report: Report, verdicts: list[Verdict]) -> None:
    """One "not checked" line per proven module instead of one per contact inside it."""
    from bricksnap.lab.validate import Issue

    for v in verdicts:
        for j in v.group or [v.joint]:
            if not j.module:
                continue
            own = set(j.fixed) | set(j.moving)
            inside = [
                i
                for i in report.issues
                if i.severity == "not checked" and i.kind == "joint" and set(i.lines) <= own
            ]
            if not inside:
                continue
            for i in inside:
                report.issues.remove(i)
            report.issues.append(
                Issue(
                    "not checked",
                    "joint",
                    sorted(own),
                    f"{_list_lines(sorted(own)).capitalize()} are the module '{j.name}' "
                    f"({j.module}): the joints inside it ({len(inside)}) are how its parts are "
                    "designed to go together, counted as joined.",
                )
            )


def _check_group(  # type: ignore[type-arg]
    g: Group, report: Report, by_line: dict, lab: Any, lib: Library, declared: list[Joint]
) -> Verdict:
    from bricksnap.lab import modules

    j = g.lead
    who = _who(j, g)
    the = "The joints" if len(g.joints) > 1 else "The joint"
    sides = _sides(report, g.fixed, g.moving)
    ride = sides.riders
    verb = "turn" if j.turns_freely else "open"
    held = None if sides.tied else _held_by_another_hinge(g, report, sides, declared)
    if held is not None:
        # a hinge on another line whose far half stands on the ground holds the panel
        sides.tied.append((held.moving[0], None, held.fixed[0], "a hinge"))
    if sides.tied:
        texts, lines = [], []
        other = _crossing_hinge(g, report, sides, declared)
        for p, nm, nf, how in sides.tied[:MAX_NAMED]:
            lines.append(p)
            if nf is not None and how:
                texts.append(
                    f"{lab(by_line[p])}, which moves, is joined to {lab(by_line[nf])}, which "
                    f"stays ({how})"
                )
                lines.append(nf)
            else:
                bits = []
                if nm is not None:
                    bits.append(f"line {nm}, which moves,")
                if nf is not None:
                    bits.append(f"line {nf}, which stays")
                texts.append(
                    f"{lab(by_line[p])} is joined to " + (" and to ".join(bits) or "both sides")
                )
                lines += [x for x in (nm, nf) if x is not None]
        more = len(sides.tied) - MAX_NAMED
        if other is not None:
            msg = (
                f"{the} {who} cannot {verb}: the hinge on "
                f"{_list_lines(other.fixed + other.moving)} holds the same parts, and these two "
                "hinges do not turn about the same line, so the panel cannot move. Put the "
                "hinges on one line, or use one."
            )
            lines += other.fixed + other.moving
        else:
            msg = (
                f"{the} {who} cannot {verb}: something holds what moves to what stays. "
                + "; ".join(texts)
                + (f"; and {more} more" if more > 0 else "")
                + ". Hold each part to one side only: remove it, or move it so it touches only "
                "the moving side or only the side that stays."
            )
        _problem(report, lines, msg)
        return Verdict(j, False, ride, None, f"{who}: tied shut (see problems).", g.joints)
    if not j.turns_freely and g.high - g.low <= 1e-6:
        _problem(
            report,
            sorted(g.fixed | g.moving),
            f"{the} {who} cannot {verb}: its hinges on this line open opposite ways, so "
            "together they hold the panel still. Turn them all the same way.",
        )
        return Verdict(j, False, ride, None, f"{who}: cannot move (see problems).", g.joints)
    mod = modules.MODULES.get(j.module.lower()) if j.module else None
    fit = mod.fit_radius if mod else KNUCKLE_R
    moving = [_body(by_line[n], lib) for n in ride]
    still = [_body(p, lib) for p in report.placed if p.line not in set(ride)]
    others = len(ride) - len(g.moving)
    carried = (
        f"; {len(ride)} part{'s' if len(ride) != 1 else ''} move with it ({_list_lines(ride)})"
        if others > 0
        else ""
    )
    if j.turns_freely:
        return _check_turning(g, who, moving, still, carried, report, by_line, lab, fit)
    sw = _Swing(g.at, g.axis, moving, still, g.moving, g.fixed, fit)
    reach = [0.0, 0.0]
    blocked = False
    for sign, end in ((1, g.high), (-1, -g.low)):
        if end <= 0:
            continue
        got, hits, ground = sw.run(sign, end)
        reach[0 if sign < 0 else 1] = sign * got
        if got >= end - 1e-6:
            continue
        blocked = True
        full = fmt(sign * end)
        reached = math.floor(got + 1e-6)
        at = math.ceil(got + 1e-6) if got < end else end
        at = max(at, reached + 1)
        if hits:
            names = "; ".join(
                f"line {m} ({by_line[m].key} {by_line[m].part.description}) hits {lab(by_line[s])}"
                for m, s in hits[:MAX_NAMED]
            )
            lines = [x for h in hits for x in h]
        else:
            names = "it would go into the ground (y = 0)"
            lines = list(ride)
        deg = f"{fmt(sign * at)} degree{'s' if at != 1 else ''}"
        head = (
            f"{the} {who} cannot open at all toward {full} degrees: by {deg} "
            if reached <= 0
            else f"{the} {who} opens only to {fmt(sign * reached)} degrees of {full}: by {deg} "
        )
        _problem(
            report,
            lines,
            head + names + ". Move what is in the way, or let the panel stop "
            "there (declare a smaller range).",
        )
    if blocked:
        lo, hi = math.ceil(reach[0] - 1e-6) if reach[0] < 0 else 0, math.floor(reach[1] + 1e-6)
        if lo == 0 and hi == 0:
            return Verdict(
                j, False, ride, None, f"{who}: cannot move at all (see problems).", g.joints
            )
        return Verdict(
            j,
            False,
            ride,
            (lo, hi),
            f"{who}: swings only from {fmt(lo)} to {fmt(hi)} degrees of {fmt(g.low)} to "
            f"{fmt(g.high)} (see problems).",
            g.joints,
        )
    return Verdict(
        j,
        True,
        ride,
        (g.low, g.high),
        f"{who}: swings from {fmt(g.low)} to {fmt(g.high)} degrees with nothing in the "
        f"way{carried}.",
        g.joints,
    )


def _held_by_another_hinge(
    g: Group, report: Report, sides: _Sides, declared: list[Joint]
) -> Joint | None:
    """A hinge on another line (declared or placed by hand) that rides with the group but is
    the only thing joining part of what rides, standing on the ground, to the rest: a panel
    on two hinges that are not in line, the second one's base on the ground."""
    ride = set(sides.riders)
    taken = g.fixed | g.moving | {n for j in declared for n in j.fixed + j.moving}
    pool = [j for j in declared if j not in g.joints] + module_pairs(report, set(taken))
    grounded = set(report.grounded) & ride
    if not grounded:
        return None
    for c in pool:
        if c.kind != "SWING" or coaxial(g.lead, c):
            continue
        if not (set(c.fixed) & ride and set(c.moving) & ride):
            continue
        adj = _graph(report, g.fixed | g.moving | set(c.fixed) | set(c.moving))
        reach = _distances(adj, g.moving, g.fixed)
        if grounded - set(reach):
            return c
    return None


def _crossing_hinge(g: Group, report: Report, sides: _Sides, declared: list[Joint]) -> Joint | None:
    """Another hinge (declared or placed by hand) whose moving part rides with the group and
    whose fixed part stays, on a different line."""
    taken = g.fixed | g.moving | {n for j in declared for n in j.fixed + j.moving}
    pool = [j for j in declared if j not in g.joints] + module_pairs(report, set(taken))
    ride = set(sides.riders) | {t[0] for t in sides.tied}
    for c in pool:
        if c.turns_freely or coaxial(g.lead, c):
            continue
        if set(c.moving) & ride or set(c.fixed) & ride:
            return c
    return None


def _check_turning(
    g: Group,
    who: str,
    moving: list[_Body],
    still: list[_Body],
    carried: str,
    report: Report,
    by_line: dict,
    lab: Any,
    fit: float,
) -> Verdict:  # type: ignore[type-arg]
    j = g.lead
    the = "The joints" if len(g.joints) > 1 else "The joint"
    env = _Envelope(g.at, g.axis, moving, still, g.fixed, fit)
    hit = env.hits()
    if hit:
        names = "; ".join(
            f"{lab(by_line[s])} reaches into the circle line {m} ({by_line[m].key} "
            f"{by_line[m].part.description}) sweeps, by {fmt(round(d, 1))} LDU"
            for m, s, d in hit[:MAX_NAMED]
        )
        lines = [x for h in hit for x in h[:2]]
        if j.kind == "WHEEL":
            _problem(
                report,
                lines,
                f"The wheels of {who} rub as they turn: {names}. Give them "
                "room: move the part they rub, or the wheels, so nothing reaches into their "
                "circle.",
            )
            return Verdict(
                j,
                False,
                [b.p.line for b in moving],
                None,
                f"{who}: the wheels rub (see problems).",
                g.joints,
            )
        _problem(
            report,
            lines,
            f"{the} {who} cannot turn all the way round: {names}. Move "
            "what is in the way, or what turns.",
        )
        return Verdict(
            j,
            False,
            [b.p.line for b in moving],
            None,
            f"{who}: cannot turn all the way round (see problems).",
            g.joints,
        )
    ride = [b.p.line for b in moving]
    below = _turn_below_ground(g, moving, GROUND_TOL if j.kind == "WHEEL" else GROUND_DEPTH)
    if below is not None:
        n, depth = below
        _problem(
            report,
            [n],
            f"{the} {who} cannot turn all the way round: {lab(by_line[n])} would go "
            f"{fmt(round(depth, 1))} LDU into the ground (y = 0) as it turns. Raise it, or what "
            "it turns on.",
        )
        return Verdict(
            j, False, ride, None, f"{who}: cannot turn all the way round (see problems).", g.joints
        )
    if j.kind != "WHEEL":
        return Verdict(
            j,
            True,
            ride,
            (0.0, 360.0),
            f"{who}: turns freely all the way round with nothing in the way{carried}.",
            g.joints,
        )
    v = Verdict(j, True, ride, (0.0, 360.0), "", g.joints)
    level = abs(float(g.axis[1])) <= LEVEL
    low = _tread_low(g, by_line)
    if not level and low > -GROUND_TOL:
        _problem(
            report,
            sorted(g.moving),
            f"The wheel {who} lies on its side: its axle points "
            f"along ({', '.join(fmt(round(float(x), 2)) for x in g.axis)}), not level, so it "
            "cannot roll. Turn it so its axle is level.",
        )
        v.ok = False
        v.text = f"{who}: lies on its side (see problems)."
        return v
    if not level or low < -SPARE_CLEAR:
        v.text = (
            f"{who}: the wheels turn freely all the way round; they are clear of the "
            "ground, so they carry nothing (a spare)."
        )
        return v
    v.road = True
    v.text = f"{who}: the wheels turn freely all the way round{carried}."
    return v


def _turn_below_ground(g: Group, moving: list[_Body], tol: float) -> tuple[int, float] | None:
    """The moving part that would go deepest into the ground as it turns all the way round
    (more than ``tol`` LDU below y = 0), and how deep; points already below it at rest are
    the plain check's business."""
    u, e1, e2 = _basis(g.axis)
    k = math.hypot(e1[1], e2[1])
    worst: tuple[int, float] | None = None
    for b in moving:
        pts = b.surf_w
        if not len(pts):
            continue
        p = _polar(pts, g.at, (u, e1, e2))
        low = g.at[1] + p.a * u[1] + p.r * k  # the lowest each point gets (largest y)
        rest = pts[:, 1]
        deep = np.where(rest <= tol, low, -np.inf)
        i = int(np.argmax(deep))
        if deep[i] > tol and (worst is None or deep[i] > worst[1]):
            worst = (b.p.line, float(deep[i]))
    return worst


def _tread(g: Group, by_line: dict) -> list[int]:  # type: ignore[type-arg]
    reach: dict[int, float] = {}
    for n in g.moving:
        p = by_line[n]
        pts = p.to_world(solids.surface(p.key))
        if not len(pts):
            continue
        rel = pts - g.at
        a = rel @ g.axis
        reach[n] = float(np.linalg.norm(rel - np.outer(a, g.axis), axis=1).max())
    if not reach:
        return []
    top = max(reach.values())
    return [n for n, r in reach.items() if r >= top - 1.5]


def _tread_low(g: Group, by_line: dict) -> float:  # type: ignore[type-arg]
    from bricksnap.lab.validate import _bottom_points

    low = -math.inf
    for n in _tread(g, by_line):
        pts = _bottom_points(by_line[n])
        low = max(low, float(pts[:, 1].max()) if len(pts) else float(by_line[n].pos[1]))
    return low


def _on_wheels(report: Report, wheels: list[Verdict], by_line: dict, lab: Any) -> None:  # type: ignore[type-arg]
    road = [v for v in wheels if v.road]
    if not road:
        return
    riding: set[int] = set()
    for v in wheels:
        riding |= set(v.riders)
    others = [g for g in report.grounded if g not in riding]
    wheelish = [
        g for g in others if by_line[g].part.description.lower().startswith(("tyre", "wheel"))
    ]
    rest = [g for g in others if g not in wheelish]
    if wheelish:
        named = ", ".join(lab(by_line[g]) for g in wheelish[:MAX_NAMED])
        _problem(
            report,
            wheelish,
            f"{named} touch{'es' if len(wheelish) == 1 else ''} the ground like a wheel but "
            f"belong{'s' if len(wheelish) == 1 else ''} to no wheel joint, so the checker cannot "
            "tell that "
            f"{'it turns' if len(wheelish) == 1 else 'they turn'}: put the wheel in with "
            "place_module, or declare its joint with joint.",
        )
    one_axle = all(coaxial(road[0].joint, v.joint) for v in road[1:])
    stand = bool(rest and one_axle)
    if stand:
        from bricksnap.lab.validate import Issue

        named = ", ".join(lab(by_line[g]) for g in rest[:MAX_NAMED])
        more = f" and {len(rest) - MAX_NAMED} more" if len(rest) > MAX_NAMED else ""
        report.issues.append(
            Issue(
                "warning",
                "movement",
                rest,
                f"All its road wheels are on one axle line, so it also stands on {named}{more}: "
                "a stand or legs, as a trailer or a wheelbarrow has. Fine if that is meant.",
            )
        )
        rest = []
    if rest:
        named = ", ".join(lab(by_line[g]) for g in rest[:MAX_NAMED])
        more = f" and {len(rest) - MAX_NAMED} more" if len(rest) > MAX_NAMED else ""
        _problem(
            report,
            rest,
            f"It does not rest on its wheels alone: {named}{more} touch"
            f"{'es' if len(rest) == 1 else ''} the ground too. Raise "
            f"{'it' if len(rest) == 1 else 'them'} (or put the wheels lower) so that only the "
            "wheels touch the ground.",
        )
    for v in road:
        g = Group(
            v.group or [v.joint],
            v.joint.at,
            v.joint.axis,
            set(v.joint.fixed),
            set(v.riders) & set(by_line),
            0,
            0,
        )
        from bricksnap.lab.validate import _bottom_points

        for n in _tread(g, by_line):
            pts = _bottom_points(by_line[n])
            low = float(pts[:, 1].max()) if len(pts) else float(by_line[n].pos[1])
            if low < -GROUND_TOL:
                _problem(
                    report,
                    [n],
                    f"The wheel {lab(by_line[n])} of {_who(v.joint)} does not "
                    f"reach the ground: its lowest point is {fmt(round(-low, 1))} LDU above "
                    "it. Lower the wheels, or raise what holds the model up instead of them.",
                )
    if (
        not stand
        and not rest
        and not wheelish
        and all(
            not any(i.kind == "movement" and set(i.lines) & set(v.riders) for i in report.problems)
            for v in road
        )
    ):
        for v in road:
            if v.ok and v.text.endswith("."):
                v.text = v.text[:-1] + ", and the model rests on its wheels."


def open_angles(text: str, report: Report | None = None) -> dict[str, float]:
    """Every joint opened as far as the check says it goes: a swing to the far end of what
    it really reaches, a spin or wheel an eighth of a turn, a joint that cannot move shut."""
    from bricksnap.lab.validate import check

    report = report or check(text)
    out: dict[str, float] = {}
    for j in parse(text)[0]:
        r = report.reach.get(j.name)
        if r is None:
            continue
        if j.turns_freely:
            out[j.name] = 45.0
        else:
            out[j.name] = r[1] if r[1] > 0 else r[0]
    return out
