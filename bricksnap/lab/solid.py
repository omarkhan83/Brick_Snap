"""Parts as real solids, for the movement check (research prototype).

CONTRACT (tests in tests/test_moving.py)

The filled bodies of ``ldraw_lib`` are rough on purpose (hollow undersides count as solid,
studs are left out, walls thinner than 2 LDU go missing). What moves needs better: a stud in
a door's path stops the door, and a door corner swinging 1.5 LDU into its jamb jams it. This
module gives each part its real shape:

- ``triangles(key)``: the part's triangles in its own frame WITH its studs (the stud
  primitives' own triangles, which ``ldraw_lib`` leaves out of the body).
- ``surface(key)``: points on that surface, no two neighbours more than ``STEP`` LDU apart
  (every triangle split across its longest edge until no edge is longer), cached in memory.
- ``solid(key)``: the part as voxels of ``CELL`` LDU (coarser only for parts so big that the
  grid would pass ``MAX_CELLS``), filled by casting rays through every voxel centre along
  x, y and z and counting how often each crosses the surface: a voxel is solid when at least
  two of the three rays say it is inside (LDraw parts are not always closed surfaces, so one
  direction alone can be wrong). ``Solid.deep`` is the solid shrunk by one voxel in each of
  the six axis directions: a point is DEEP inside when it and the points ``CELL`` LDU from it
  along each axis are solid. Grids are cached on disk under the lab cache.
- ``Solid.inside(points, deep=True)``: which points (in the part's frame) are inside.
- ``stud_core_inside(key, base, d)``: does a stud with its base at ``base`` pointing along
  ``d`` (the part's frame) go into the part's solid plastic: any point of its core
  (``STUD_CORE_R`` round its axis, or a smaller ``radius``, ``STUD_CORE_H`` up it) DEEP
  inside. A stud that only grazes the part (less than about 1 LDU) does not.
- ``drawn_inside(key, points)``: which points are inside the part's DRAWN surface (nine fixed
  skew rays each, 5 of 9 crossing an odd number of triangles): slower than the solid, and
  free of what its fill can add.
- ``stud_middle_blocked(key, base, d)``: would a stud's middle be in the part's plastic (at
  one of ``STUD_MIDDLE_H``, its axis point or ``STUD_MIDDLE_OF_6`` of 6 points on the ring
  ``STUD_MIDDLE_R`` round it inside the drawn surface)? The solid only picks which studs to
  try (``STUD_MIDDLE_OF_12``). What ``place.sockets`` asks of each socket it offers.

What it guarantees, for a part whose cells are ``h`` LDU (``CELL``, 0.5, for every ordinary
part; coarser only for parts so big the grid would pass ``MAX_CELLS``: about 1 to 1.2 LDU
for a large baseplate, 2.4 for a 52-stud hull): a point less than ``h / 2`` inside is never
deep inside, one more than ``1.5 h`` inside always is. With the movement check's steps (no
surface point moves more than 0.5 LDU between two) and its surface points (at most
``STEP`` LDU apart, tested both ways round), every interference deeper than ``2 h`` is
seen (``GUARANTEE`` = 1 LDU, 0.4 mm, at 0.5 LDU cells; 2.4 LDU against a large baseplate;
4.8 against the hull) and none shallower than ``h / 2``. Measured at 0.5 LDU cells on
doors swinging their far corner into a jamb (tests/test_moving.py), the change from free
to blocked comes between 0.5 and 0.75 LDU. A cache file that cannot be read, or whose
fields are not a proper grid, is built again.

Whether two placed parts are in each other's way (``interference``, ``in_the_way``; used by
the checker to confirm an overlap its rough filled bodies report): the voxel centres of the
smaller grid that are inside both parts' solids are the SHARED piece, and its depth is how
far its deepest voxel is from the nearest voxel that is not shared (half the thickness of
the thickest shared piece). The two are in each other's way when that depth reaches
``((ha + hb) / 2 + REAL_MARGIN) / 2``, where ``ha`` and ``hb`` are the two grids' cells: the
shared piece is at least ``REAL_MARGIN`` (1 LDU) thicker than the film that two surfaces
which only touch can share through the voxels alone (half a cell from each side). At
ordinary 0.5 LDU cells that is a piece at least three voxels (1.5 LDU) thick in every
direction (depth 0.75; the depths that occur are 0.5, 0.71, 0.87, 1.0 ...). Why this number:
a stud seated in its socket shares nothing (measured: depth 0), parts that only touch
along a face, at a bracket's flange or under a curved slope's stepped underside share a film
(0.5 at most, on the 77 such pairs in the six official sets of experiment 3), and a part
pushed 2 LDU or more into another shares a piece at least 2 LDU thick (depth 1.0; 4 LDU,
half a plate, gives 2.0: an ordinary wall or top is 4 LDU thick, so a plate's thickness
pushed in gives the same). Interference thinner than 1.5 LDU (0.6 mm) is not seen.
"""

from __future__ import annotations

import contextlib
import os
import pickle
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from bricksnap.lab.ldraw_lib import Library, cache_dir, library

CELL = 0.5
MAX_CELLS = 6_000_000
STEP = 1.5
GUARANTEE = 1.0
REAL_MARGIN = 1.0  # LDU of shared material, beyond the voxels' own error, that is a clash
VERSION = 2
_JITTER = np.array([0.0137, 0.0071, 0.0113])
_LOCK = threading.Lock()
_SOLIDS: dict[str, Solid] = {}
_SURFACES: dict[str, np.ndarray] = {}
_TRIS: dict[str, np.ndarray] = {}


@dataclass
class Solid:
    lo: np.ndarray  # corner of voxel (0, 0, 0)
    h: float
    full: np.ndarray  # (nx, ny, nz) bool
    deep: np.ndarray
    _near: dict | None = None  # LDU -> the solid grown by that much (padded), made when asked

    def near(self, ldu: float) -> tuple[np.ndarray, int]:
        """The solid grown by ``ldu`` LDU in every direction, and how many voxels of padding
        it has on each side."""
        if self._near is None:
            self._near = {}
        if ldu not in self._near:
            from scipy import ndimage

            k = int(np.ceil(ldu / self.h))
            grown = np.pad(self.full, k)
            r = np.arange(-k, k + 1)
            ball = (r[:, None, None] ** 2 + r[None, :, None] ** 2 + r[None, None, :] ** 2) <= k * k
            self._near[ldu] = (ndimage.binary_dilation(grown, structure=ball), k)
        return self._near[ldu]

    def lookup(self, grid: np.ndarray, pad: int, local: np.ndarray) -> np.ndarray:
        idx = np.floor((local - self.lo) / self.h).astype(np.int64) + pad
        shape = np.array(grid.shape)
        ok = np.all((idx >= 0) & (idx < shape), axis=1)
        out = np.zeros(len(local), dtype=bool)
        if ok.any():
            i = idx[ok]
            out[ok] = grid[i[:, 0], i[:, 1], i[:, 2]]
        return out

    def inside(self, pts: np.ndarray, deep: bool = True) -> np.ndarray:
        pts = np.asarray(pts, dtype=float).reshape(-1, 3)
        grid = self.deep if deep else self.full
        if not len(pts) or not grid.size:
            return np.zeros(len(pts), dtype=bool)
        idx = np.floor((pts - self.lo) / self.h).astype(np.int64)
        shape = np.array(grid.shape)
        ok = np.all((idx >= 0) & (idx < shape), axis=1)
        out = np.zeros(len(pts), dtype=bool)
        if ok.any():
            i = idx[ok]
            out[ok] = grid[i[:, 0], i[:, 1], i[:, 2]]
        return out

    def box(self) -> tuple[np.ndarray, np.ndarray]:
        return self.lo, self.lo + np.array(self.full.shape) * self.h


def _shared(
    a: tuple[str, np.ndarray, np.ndarray],
    b: tuple[str, np.ndarray, np.ndarray],
    lib: Library | None,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """The voxels two placed parts' real solids share: (their indices in the sampled grid,
    their centres in the world, that grid's cell, the depth ``needed``); empty when none."""
    none = np.zeros((0, 3), dtype=np.int64), np.zeros((0, 3))
    sa, sb = solid(a[0], lib), solid(b[0], lib)
    if sa.full.size and sb.full.size and sb.full.size * sa.h**3 < sa.full.size * sb.h**3:
        a, b, sa, sb = b, a, sb, sa  # sample the smaller grid
    ha, hb = sa.h, sb.h
    needed = ((ha + hb) / 2 + REAL_MARGIN) / 2
    if not sa.full.size or not sb.full.size:
        return (*none, ha, needed)
    inv_a = np.linalg.inv(a[2])
    blo, bhi = sb.box()
    corners = np.array(
        [[x, y, z] for x in (blo[0], bhi[0]) for y in (blo[1], bhi[1]) for z in (blo[2], bhi[2])]
    )
    world = corners @ b[2].T + b[1]
    local = (world - a[1]) @ inv_a.T
    shape = np.array(sa.full.shape)
    i0 = np.clip(np.floor((local.min(0) - sa.lo) / ha).astype(np.int64) - 1, 0, shape)
    i1 = np.clip(np.ceil((local.max(0) - sa.lo) / ha).astype(np.int64) + 1, 0, shape)
    sub = sa.full[i0[0] : i1[0], i0[1] : i1[1], i0[2] : i1[2]]
    if not sub.any():
        return (*none, ha, needed)
    idx = np.argwhere(sub)
    pts = sa.lo + (idx + i0 + 0.5) * ha
    w = pts @ a[2].T + a[1]
    inb = sb.inside((w - b[1]) @ np.linalg.inv(b[2]).T, deep=False)
    if not inb.any():
        return (*none, ha, needed)
    return idx[inb], w[inb], ha, needed


def shared_points(
    a: tuple[str, np.ndarray, np.ndarray],
    b: tuple[str, np.ndarray, np.ndarray],
    lib: Library | None = None,
) -> np.ndarray:
    """The world centres of the voxels two placed parts' real solids share (0.5 LDU cells)."""
    return _shared(a, b, lib)[1]


def interference(
    a: tuple[str, np.ndarray, np.ndarray],
    b: tuple[str, np.ndarray, np.ndarray],
    lib: Library | None = None,
    apart: tuple[np.ndarray, np.ndarray, float] | list | None = None,
) -> tuple[float, float, float]:
    """How far the real solids of two placed parts go into each other.

    ``a`` and ``b`` are (key, position, rotation matrix) as on a part line. Returns
    ``(depth, volume, needed)``: ``depth`` is how far the deepest shared voxel is from the
    nearest voxel that is not shared (half the thickness of the thickest shared piece, in
    LDU), ``volume`` the shared volume (LDU^3), and ``needed`` the depth at which the two
    really are in each other's way (see the contract: ``in_the_way``). ``apart``, (p, q, r):
    shared voxels inside the cylinder of radius r round the segment from p to q (world),
    between its two ends, are left out; a list of such cylinders leaves out what is inside
    any of them."""
    hit, w, ha, needed = _shared(a, b, lib)
    if not len(hit):
        return 0.0, 0.0, needed
    from scipy import ndimage

    cylinders = [] if apart is None else apart if isinstance(apart, list) else [apart]
    if cylinders:
        wh = w
        far = np.ones(len(hit), dtype=bool)
        for p0, p1, r in cylinders:
            seg = np.asarray(p1, dtype=float) - p0
            ww = wh - p0
            t = ww @ seg / max(float(seg @ seg), 1e-12)
            far &= (t < 0) | (t > 1) | (np.linalg.norm(ww - np.outer(t, seg), axis=1) > r)
        hit = hit[far]
        if not len(hit):
            return 0.0, 0.0, needed
    lo, hi = hit.min(0), hit.max(0) + 1
    mask = np.zeros(tuple(hi - lo + 2), dtype=bool)
    mask[tuple((hit - lo + 1).T)] = True
    depth = float(ndimage.distance_transform_edt(mask).max()) * ha
    return depth, float(len(hit)) * ha**3, needed


def in_the_way(
    a: tuple[str, np.ndarray, np.ndarray],
    b: tuple[str, np.ndarray, np.ndarray],
    lib: Library | None = None,
    apart: tuple[np.ndarray, np.ndarray, float] | list | None = None,
) -> bool:
    """True when two placed parts' real solids go into each other deeper than touching or
    a seated stud does (see the contract)."""
    depth, _, needed = interference(a, b, lib, apart)
    return depth >= needed - 1e-9


STUD_CORE_R = 5.0  # LDU: a stud is 6 in radius; its core this far out is what must be free
STUD_CORE_H = (0.75, 3.5)  # LDU up the stud (it is 4 tall) that must be free
STUD_MIDDLE_R = 2.5  # LDU: the ring round a stud's axis that ``stud_middle_blocked`` tries
STUD_MIDDLE_H = (0.75, 2.1, 3.5)  # LDU up the stud where its middle is tried
STUD_MIDDLE_OF_6 = 2  # ring points of 6 inside the drawn surface that block a socket
STUD_MIDDLE_OF_12 = 3  # ring points of 12 deep in the solid that make a socket worth trying


def stud_core_inside(
    key: str,
    base: np.ndarray,
    d: np.ndarray,
    lib: Library | None = None,
    radius: float = STUD_CORE_R,
) -> bool:
    """Does a stud (its base and unit direction in the part's own frame) go into the part's
    real solid plastic? (See the contract.) ``radius``: how far out from its axis the core
    is tested (rings at 2.5 LDU and at ``radius``)."""
    d = np.asarray(d, dtype=float)
    a = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    u = np.cross(d, a)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    ang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    ring = np.outer(np.cos(ang), u) + np.outer(np.sin(ang), v)
    pts = []
    for h in np.linspace(STUD_CORE_H[0], STUD_CORE_H[1], 4):
        c = np.asarray(base, dtype=float) + h * d
        pts.append(c[None, :])
        for r in sorted({2.5, radius}):
            pts.append(c + r * ring)
    return bool(solid(key, lib).inside(np.concatenate(pts), deep=True).any())


_RAYS = np.random.default_rng(5).normal(size=(9, 3))
_RAYS /= np.linalg.norm(_RAYS, axis=1)[:, None]  # nine skew directions, fixed


def drawn_inside(key: str, pts: np.ndarray, lib: Library | None = None) -> np.ndarray:
    """Which points (the part's frame) are inside the part's DRAWN surface: rays from each in
    nine fixed skew directions, each counting how often it crosses the part's triangles; a
    point is inside when at least 5 of the 9 cross an odd number of times. Slower than the
    voxel solid, and free of what the solid's fill can add (a thin column no triangle draws)."""
    tris = triangles(key, lib)
    pts = np.asarray(pts, dtype=float).reshape(-1, 3)
    out = np.zeros(len(pts), dtype=bool)
    if not len(tris) or not len(pts):
        return out
    a, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    for k, p in enumerate(pts):
        votes = 0
        s_ = p - a
        q = np.cross(s_, e1)
        for d in _RAYS:
            h = np.cross(d, e2)
            det = np.einsum("ij,ij->i", e1, h)
            ok = np.abs(det) > 1e-12
            inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
            u = inv * np.einsum("ij,ij->i", s_, h)
            v = inv * (q @ d)
            t = inv * np.einsum("ij,ij->i", e2, q)
            votes += int(np.sum(ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9))) % 2
            if votes >= 5:
                break
        out[k] = votes >= 5
    return out


def _middle_points(
    base: np.ndarray, d: np.ndarray, n: int, heights: tuple[float, ...] = STUD_MIDDLE_H
) -> list[np.ndarray]:
    """For each height up a stud: the point on its axis, then n points on the ring
    ``STUD_MIDDLE_R`` round it."""
    d = np.asarray(d, dtype=float)
    a = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    u = a - (a @ d) * d
    u /= np.linalg.norm(u)
    v = np.cross(d, u)  # for a stud pointing up: u along x, v along z
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = STUD_MIDDLE_R * (np.outer(np.cos(ang), u) + np.outer(np.sin(ang), v))
    return [
        np.vstack([c[None, :], c + ring])
        for c in (np.asarray(base, dtype=float) + h * d for h in heights)
    ]


def stud_middle_blocked(
    key: str, base: np.ndarray, d: np.ndarray, lib: Library | None = None
) -> bool:
    """Would the middle of a stud (its base and unit direction in the part's frame) be in the
    part's plastic? At one of ``STUD_MIDDLE_H`` up the stud, its axis point or
    ``STUD_MIDDLE_OF_6`` of 6 points on the ring ``STUD_MIDDLE_R`` round it are inside the
    part's DRAWN surface (``drawn_inside``). The voxel solid only picks which studs to try
    (the axis point or ``STUD_MIDDLE_OF_12`` of 12 ring points deep inside it, at one of 4
    heights through ``STUD_CORE_H``), so a column its fill adds where nothing is drawn never
    blocks a socket, and a single rib at a stud's side does not either."""
    so = solid(key, lib)
    if not any(
        (hit := so.inside(pts, deep=True))[0] or int(hit[1:].sum()) >= STUD_MIDDLE_OF_12
        for pts in _middle_points(base, d, 12, tuple(np.linspace(*STUD_CORE_H, 4)))
    ):
        return False
    for pts in _middle_points(base, d, 6):
        hit = drawn_inside(key, pts, lib)
        if hit[0] or int(hit[1:].sum()) >= STUD_MIDDLE_OF_6:
            return True
    return False


def triangles(key: str, lib: Library | None = None) -> np.ndarray:
    """The part's triangles (n, 3, 3) with its studs, in its own frame."""
    with _LOCK:
        if key in _TRIS:
            return _TRIS[key]
    lib = lib or library()
    body = lib.triangles(key)
    parts = [body]
    part = lib.part(key)
    for c in part.studs:
        found = lib.resolve(c.prim + ".dat")
        if found is None:
            continue
        tris = lib._raw(*found).tris
        if not len(tris):
            continue
        m = _rot_from_down(c.axis)
        parts.append(tris @ m.T + c.pos)
    out = np.concatenate(parts) if len(parts) > 1 else body
    with _LOCK:
        if len(_TRIS) > 300:
            _TRIS.clear()
        _TRIS[key] = out
    return out


def _rot_from_down(axis: np.ndarray) -> np.ndarray:
    """A rotation taking (0, -1, 0), the way a stud primitive points, to ``axis``."""
    a = np.array([0.0, -1.0, 0.0])
    b = np.asarray(axis, dtype=float)
    b = b / np.linalg.norm(b)
    c = float(np.dot(a, b))
    if c > 1 - 1e-9:
        return np.eye(3)
    if c < -1 + 1e-9:
        return np.diag([1.0, -1.0, -1.0])
    v = np.cross(a, b)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * (1 / (1 + c))


def sample_triangles(tris: np.ndarray, step: float = STEP) -> np.ndarray:
    """Points on the triangles, none farther than ``step`` from its neighbours: every
    triangle is split across its longest edge until no edge is longer than ``step``, and
    the corners are the points (so a long thin sliver gives a row of points, not a grid)."""
    if not len(tris):
        return np.zeros((0, 3))
    out = [tris.reshape(-1, 3)]
    t = tris
    for _ in range(40):
        e = np.stack(
            [
                np.linalg.norm(t[:, 1] - t[:, 0], axis=1),
                np.linalg.norm(t[:, 2] - t[:, 1], axis=1),
                np.linalg.norm(t[:, 0] - t[:, 2], axis=1),
            ],
            axis=1,
        )
        big = e.max(1) > step
        if not big.any():
            break
        t, e = t[big], e[big]
        k = e.argmax(1)
        # rotate each triangle so that its longest edge is from corner 0 to corner 1
        idx = np.stack([k, (k + 1) % 3, (k + 2) % 3], axis=1)
        t = np.take_along_axis(t, idx[:, :, None], axis=1)
        mid = (t[:, 0] + t[:, 1]) / 2
        out.append(mid)
        t = np.concatenate(
            [np.stack([t[:, 0], mid, t[:, 2]], 1), np.stack([mid, t[:, 1], t[:, 2]], 1)]
        )
    return np.unique(np.round(np.concatenate(out), 2), axis=0)


def surface(key: str, lib: Library | None = None) -> np.ndarray:
    with _LOCK:
        if key in _SURFACES:
            return _SURFACES[key]
    pts = sample_triangles(triangles(key, lib))
    with _LOCK:
        if len(_SURFACES) > 300:
            _SURFACES.clear()
        _SURFACES[key] = pts
    return pts


# ---- voxels ---------------------------------------------------------------------------------


def _crossings(tris: np.ndarray, axis: int, lo: np.ndarray, h: float, shape: tuple) -> np.ndarray:
    """For rays along ``axis`` through every voxel centre: whether each centre has an odd
    number of surface crossings above it (inside, by that ray)."""
    u, v = [k for k in range(3) if k != axis]
    nu, nv, nw = shape[u], shape[v], shape[axis]
    hist = np.zeros((nu, nv, nw + 1), dtype=np.int32)
    A, B, C = tris[:, 0], tris[:, 1], tris[:, 2]
    det = (B[:, v] - C[:, v]) * (A[:, u] - C[:, u]) + (C[:, u] - B[:, u]) * (A[:, v] - C[:, v])
    ok = np.abs(det) > 1e-12
    A, B, C, det = A[ok], B[ok], C[ok], det[ok]
    if not len(A):  # no triangle faces this axis: nothing is inside by these rays
        return np.zeros(tuple(shape), dtype=bool)  # in x, y, z order, as below
    tu = np.stack([A[:, u], B[:, u], C[:, u]], 1)
    tv = np.stack([A[:, v], B[:, v], C[:, v]], 1)
    # centre of voxel i along an axis: lo + (i + 0.5) * h
    iu0 = np.clip(np.ceil((tu.min(1) - lo[u]) / h - 0.5), 0, nu).astype(np.int64)
    iu1 = np.clip(np.floor((tu.max(1) - lo[u]) / h - 0.5), -1, nu - 1).astype(np.int64)
    iv0 = np.clip(np.ceil((tv.min(1) - lo[v]) / h - 0.5), 0, nv).astype(np.int64)
    iv1 = np.clip(np.floor((tv.max(1) - lo[v]) / h - 0.5), -1, nv - 1).astype(np.int64)
    cu = np.maximum(iu1 - iu0 + 1, 0)
    cv = np.maximum(iv1 - iv0 + 1, 0)
    count = cu * cv
    order = np.nonzero(count)[0]
    chunk: list[int] = []
    total = 0

    def flush(sel: list[int]) -> None:
        s = np.array(sel)
        cnt = count[s]
        t = np.repeat(s, cnt)
        k = np.arange(int(cnt.sum())) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        ii = iu0[t] + k // cv[t]
        jj = iv0[t] + k % cv[t]
        pu = lo[u] + (ii + 0.5) * h
        pv = lo[v] + (jj + 0.5) * h
        a, b, c, d = A[t], B[t], C[t], det[t]
        l1 = ((b[:, v] - c[:, v]) * (pu - c[:, u]) + (c[:, u] - b[:, u]) * (pv - c[:, v])) / d
        l2 = ((c[:, v] - a[:, v]) * (pu - c[:, u]) + (a[:, u] - c[:, u]) * (pv - c[:, v])) / d
        l3 = 1 - l1 - l2
        hit = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        w = l1 * a[:, axis] + l2 * b[:, axis] + l3 * c[:, axis]
        bins = np.clip(np.ceil((w - lo[axis]) / h - 0.5), 0, nw).astype(np.int64)
        np.add.at(hist, (ii[hit], jj[hit], bins[hit]), 1)

    for t in order:
        chunk.append(int(t))
        total += int(count[t])
        if total > 2_000_000:
            flush(chunk)
            chunk, total = [], 0
    if chunk:
        flush(chunk)
    above = np.cumsum(hist[:, :, ::-1], axis=2)[
        :, :, ::-1
    ]  # above[..., b] = crossings in bins >= b
    inside = (above[:, :, 1:] % 2) == 1  # centre k has crossings in bins > k above it
    # back to x, y, z order
    perm = [0, 0, 0]
    perm[u], perm[v], perm[axis] = 0, 1, 2
    return np.transpose(inside, perm)


def build_solid(tris: np.ndarray) -> Solid:
    if not len(tris):
        return Solid(np.zeros(3), CELL, np.zeros((0, 0, 0), bool), np.zeros((0, 0, 0), bool))
    pts = tris.reshape(-1, 3)
    lo, hi = pts.min(0), pts.max(0)
    h = CELL
    span = hi - lo + 2 * h
    while float(np.prod(np.ceil(span / h))) > MAX_CELLS:
        h *= 1.25
    lo = lo - h + _JITTER * h
    shape = tuple(int(v) for v in np.ceil((hi - lo) / h) + 2)
    votes = np.zeros(shape, dtype=np.int8)
    for axis in range(3):
        votes += _crossings(tris, axis, lo, h, shape).astype(np.int8)
    full = votes >= 2
    deep = full.copy()
    for axis in range(3):
        for s in (1, -1):
            deep &= np.roll(full, s, axis=axis)
    # np.roll wraps: the outer layer can never be deep
    deep[0, :, :] = deep[-1, :, :] = False
    deep[:, 0, :] = deep[:, -1, :] = False
    deep[:, :, 0] = deep[:, :, -1] = False
    return Solid(lo, h, full, deep)


def _cache_file(key: str, lib: Library) -> Path:
    safe = re.sub(r"[^a-z0-9._-]", "_", key)
    return cache_dir() / "solids" / f"{safe}.v{VERSION}.pkl"


def _from_cache(data: dict) -> Solid | None:  # type: ignore[type-arg]
    """The grid in a cache entry, or None when any field is not what a grid needs."""
    shape = tuple(int(v) for v in data["shape"])
    h = float(data["h"])
    lo = np.asarray(data["lo"], dtype=float).reshape(3)
    if len(shape) != 3 or min(shape) < 0 or not (np.isfinite(h) and h > 0):
        return None
    if not np.all(np.isfinite(lo)):
        return None
    n = int(np.prod(shape))
    fb, db = np.unpackbits(data["full"]), np.unpackbits(data["deep"])
    if len(fb) < n or len(db) < n:
        return None
    return Solid(lo, h, fb[:n].reshape(shape).astype(bool), db[:n].reshape(shape).astype(bool))


def solid(key: str, lib: Library | None = None) -> Solid:
    with _LOCK:
        if key in _SOLIDS:
            return _SOLIDS[key]
    lib = lib or library()
    path = _cache_file(key, lib)
    got: Solid | None = None
    try:
        with path.open("rb") as f:
            data = pickle.load(f)
        if data.get("stamp") == lib.stamp:
            got = _from_cache(data)
    except Exception:  # any unreadable or damaged entry is simply built again
        got = None
    if got is None:
        got = build_solid(triangles(key, lib))
        with contextlib.suppress(OSError):
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            with tmp.open("wb") as f:
                pickle.dump(
                    {
                        "stamp": lib.stamp,
                        "lo": got.lo,
                        "h": got.h,
                        "shape": got.full.shape,
                        "full": np.packbits(got.full),
                        "deep": np.packbits(got.deep),
                    },
                    f,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            os.replace(tmp, path)
    with _LOCK:
        if len(_SOLIDS) > 200:
            _SOLIDS.clear()
        _SOLIDS[key] = got
    return got
