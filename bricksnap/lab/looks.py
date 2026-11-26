"""How a model looks, measured against official sets (research prototype, EXPERIMENTAL).

CONTRACT (tests in tests/test_looks.py)

The study ``docs/research/2026-11-20-what-makes-a-model-look-styled/`` measured, from the
parts' real shapes, what separates official models of recent years from the AI builder's: not
studs (ours show fewer), but flanks of plates stacked flat, almost nothing built sideways, big
plain areas of one colour, and bare Technic holes. This module measures those few things on
one model so the builder (guide mode, the ``check`` tool) and a person (the free-build page)
can see them. Its numbers are advice: nothing here is a problem, blocks ``submit`` or
changes whether a model is clean.

The skin
- Each part file's real surface (``solid.triangles``: the library's triangles with the studs)
  is split across the longest edge until no edge is longer than ``STEP`` (1.4 LDU), one point
  per piece (its centre) with its triangle's normal (sign ignored) and three flags in the
  part's own frame: ``stud`` (on a male stud, or on the part's surface in the stud's 1 x 1
  cell: within 10 LDU of its axis both ways across it, within 1 LDU of its base plane, facing
  the way it points), ``hole`` (within 8 LDU of a Technic pin hole's line, between its ends; a
  hole drawn at one end only is taken as 10 LDU deep; ``pin hole`` connectors on one line are
  one hole) and ``top`` (a face leaning up or down at least 0.35 in the part's frame, in the
  upper half of its box, not a stud: a tile's top, a slope's face). Only points that are the
  nearest of the part's own points in a 1 LDU pixel seen from one of the six axis directions
  are kept, with which directions see them (``vis``): no other point can show in a view of
  the model along an axis.
- These are cached per part file in memory and on disk (``cache_dir()/looks/<file>.v<N>.npz``,
  ``VERSION``, stamped with the library zip's ``stamp``): written to a temporary file named by
  process and thread and moved into place, so two processes can write at once; a file that
  cannot be read, has the wrong stamp, or whose arrays do not agree in length is built again,
  never trusted.
- Five views of the model, orthographic, on pixels of ``PIX`` (2) LDU: from above (front of
  the model at the bottom), front (-z), left (-x), back (+z), right (+x). Each pixel shows the
  nearest point (a z-buffer of points; the first in model order wins a tie). A part turned
  off the axes shows every point it shows any way. Transparent parts are opaque here. Each
  pixel has one kind, the first that applies: transparent (LDConfig alpha below 255), Technic
  hole (a hole flag on a hole nothing fills: no other part's pin, axle or bar-handle connector
  point within 3 LDU of its line, between its ends), studded, curved or sloped (the world
  normal more than 5 degrees from every world axis), smooth flat.

The measures (``measure(report)`` -> ``Looks``; ``report`` is ``validate.check``'s result)
- ``seams_per_stud``: on the four side views, pairs of vertically neighbouring pixels showing
  two different parts that are both flat walls facing the viewer (normal within 5 degrees of
  the view, kind smooth flat) and within 2 LDU in depth: a flush seam between stacked parts.
  Seams per stud (20 LDU) of skin height: seam pairs * 20 / (side pixels * PIX). A brick wall
  four courses high gives 0.60, twelve plates stacked 2.18, a flank of tiles on their side
  none where the tiles are one piece high.
- ``not_upright``: of the parts with studs or a socket underneath, the share whose own up is
  more than 25 degrees from world up (built sideways, upside down or angled).
- ``side_top_faces``: of the side views' skin, the share showing the ``top`` face of a part
  whose own up is not world up (not transparent): tiles and slopes facing outward.
- ``largest_colour`` (and ``largest_colour_name``): the largest one colour's share of the
  skin of the five views; ``colours_5pct``: how many colours hold at least 5% of it;
  ``primary_share``: the share in LDraw 4 red, 1 blue, 14 yellow, 2 green.
- ``patch_coherence``: patches are 4-connected pixels of one colour in one view; the
  area-weighted mean patch (sum of size^2 / sum of size) over the mean skin of one view: 1
  when each view is one colour and the views are the same size (more when they differ);
  0.14 to 0.23 in official models.
- ``open_holes``: Technic holes nothing fills that show at least 12 pixels (48 LDU^2, about
  40% of a hole's mouth) in one of the five views.
- ``plain_bricks``: of the parts, the share whose LDraw description (a leading ~, _ or = left
  out) is a plain brick: "Brick", its size ("1 x 2", "1 x 1 x 3", "2 x 2 x 1 1/3"...), and
  nothing more or "Corner" or "without ..." (``PLAIN_BRICK``).
- ``clips_bars``: of the parts, the share whose description holds "clip" (also "clips"),
  "bar holder", "handle", or the word "bar" or "bars", and does not start with "Technic"
  (``CLIP_BAR``). Parts whose description starts with "Sticker" or "Minifig" are left out of
  both shares, as the parts-list study leaves them out.
- ``studs_showing`` of ``studs`` (``studs_showing_share``): male studs with nothing on them:
  no stud link of the checker to them, and no other part's filled body contains the point 2
  or 6 LDU out along the stud, nor has it under its underside (the stud points into the
  part's own up within 25 degrees, the point is in one of its columns, below the column's top
  and at most 6 LDU below its filled bottom). Kept in the record; advice only when above the
  official range (ours are below it).

``RANGES``: for each measure the middle half of the official models (25th to 75th
percentile) and the side that needs advice. ``lines(looks)`` gives the HOW IT LOOKS lines
(at most seven): each the number, the official range and, only when it is outside the range
on the side that matters, one plain sentence of what to do; a measure inside the range (or
outside on the harmless side) says so in a few words. ``faces(skin)`` gives the same seams
and sideways share per facing pair of side views (front/back, left/right) with the lines
whose edges make the seams there; given them, ``lines(looks, faces)`` adds to the seams and
the sideways lines, when outside the range, WHERE: the pairs out of range, the first
``WHERE_LINES`` lines making their seams, and the fix in one line (``skin`` facing that way,
on side studs). ``section(looks, faces)`` is the heading and the lines (``measure_where
(report)`` measures both from one skin; the guide-mode check gives them from the first
check on); ``record(looks)`` the numbers for project.json. ``page_lines(record)`` gives three
or four short plain sentences with the official range for the free-build page. ``measure_text
(text)`` checks and measures a model; it never raises and gives None when it cannot measure.

Cost (measured on this machine): with the part files sampled, about 0.3 seconds for the
206-part Cessna and 0.25 to 0.35 for a 250-part block of bricks (``check`` itself, which the
builder has already run, is not counted). Sampling costs the first time a part file is met:
3.6 seconds for the Cessna's 53 part files with an empty cache; the disk cache then holds
about 0.4 MB per part file and a new process reads them in a few milliseconds each.
"""

from __future__ import annotations

import contextlib
import math
import os
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage
from scipy.spatial import KDTree

from bricksnap.lab import solid
from bricksnap.lab.ldraw_lib import Library, cache_dir, library

VERSION = 1
STEP = 1.4  # longest edge of a sampled piece, LDU
PIX = 2.0  # LDU per pixel of a view
SELF_PIX = 1.0  # LDU per pixel when a part decides which of its points can be seen
FLAT_COS = math.cos(math.radians(5))
UP_COS = math.cos(math.radians(25))
UP_SIN = math.sin(math.radians(25))
STUDDED, FLAT, CURVED, TRANS, HOLE = 1, 2, 3, 4, 5
KINDS = ["studded", "smooth flat", "curved or sloped", "transparent", "Technic hole"]
PRIMARIES = frozenset({4, 1, 14, 2})
HOLE_SHOWS = 12  # pixels of an open hole's mouth in one view
SEAM_DEPTH = 2.0  # LDU: two walls this close in depth are flush
# view: name, depth axis, depth sign (smaller depth is nearer), u axis, u sign, v axis, v sign
VIEWS: list[tuple[str, int, int, int, int, int, int]] = [
    ("above", 1, 1, 0, 1, 2, -1),
    ("front", 2, 1, 0, 1, 1, 1),
    ("left", 0, 1, 2, -1, 1, 1),
    ("back", 2, -1, 0, -1, 1, 1),
    ("right", 0, -1, 2, 1, 1, 1),
]
SIDES = ("front", "left", "back", "right")

PLAIN_BRICK = re.compile(
    r"^Brick\s+\d+\s+x\s+\d+(\s+x\s+\d+(\s+\d+/\d+)?(/\d+)?)?(\s+(Corner|without\b.*))?$", re.I
)
CLIP_BAR = re.compile(r"clip|bar holder|handle|\bbars?\b", re.I)
NOT_COUNTED = re.compile(r"^(Sticker|Minifig)\b", re.I)


# ---- the official ranges --------------------------------------------------------------------

# The middle half (25th to 75th percentile) of the official models measured in the study
# (docs/research/2026-11-20-what-makes-a-model-look-styled/: 18 official sets of 2015 to 2025
# from the LDraw Official Model Repository, flattened as experiment 2 of the study of real
# sets did), with the side that needs advice ("high": above the range; "low": below it).
SEAMS = (0.26, 0.40, "high")
NOT_UPRIGHT = (0.17, 0.43, "low")
SIDE_TOP_FACES = (0.09, 0.24, "low")
LARGEST_COLOUR = (0.32, 0.53, "high")
COLOURS_5PCT = (4.0, 5.0, "low")
PATCH_COHERENCE = (0.14, 0.23, "high")
PRIMARY_SHARE = (0.0, 0.13, "high")
OPEN_HOLES = (0.0, 2.0, "high")  # 15 of the 18 show none; 2 is their 90th percentile
STUDS_SHOWING = (0.07, 0.16, "high")
# The two parts-list measures: the middle half of the 3,002 official sets of 2015 to 2022 in
# the parts-list study's counts ("Set inventories from the Rebrickable catalogue
# (rebrickable.com), November 2026"), its groups "plain bricks" and "clips, bars and handles";
# ``PLAIN_BRICK`` and ``CLIP_BAR`` follow its definitions with LDraw's descriptions.
PLAIN_BRICKS = (0.014, 0.093, "high")
CLIPS_BARS = (0.032, 0.108, "low")


# ---- per part file: sample points and flags ---------------------------------------------------


@dataclass(frozen=True)
class PartPoints:
    pts: np.ndarray  # (n, 3) float32, in the part's frame
    nrm: np.ndarray  # (n, 3) float32 unit normals, sign arbitrary
    stud: np.ndarray  # (n,) bool
    hole: np.ndarray  # (n,) int32: -1, or the index of the hole line in ``holes``
    top: np.ndarray  # (n,) bool
    vis: np.ndarray  # (n, 6) bool: seen from -x, +x, -y, +y, -z, +z of the part's frame
    holes: np.ndarray  # (k, 8) float: point (3), unit direction (3), tmin, tmax


_POINTS: dict[str, PartPoints] = {}
_LOCK = threading.Lock()


def split_points(tris: np.ndarray, step: float = STEP) -> tuple[np.ndarray, np.ndarray]:
    """Centres of the pieces of each triangle split across its longest edge until no edge is
    longer than ``step``, and the index of the triangle each came from."""
    if not len(tris):
        return np.zeros((0, 3)), np.zeros(0, dtype=np.int64)
    t, ti = tris, np.arange(len(tris))
    pts, idx = [], []
    for _ in range(60):
        e = np.stack(
            [
                np.linalg.norm(t[:, 1] - t[:, 0], axis=1),
                np.linalg.norm(t[:, 2] - t[:, 1], axis=1),
                np.linalg.norm(t[:, 0] - t[:, 2], axis=1),
            ],
            axis=1,
        )
        big = e.max(1) > step
        pts.append(t[~big].mean(1))
        idx.append(ti[~big])
        if not big.any():
            break
        t, ti, e = t[big], ti[big], e[big]
        k = e.argmax(1)
        order = np.stack([k, (k + 1) % 3, (k + 2) % 3], axis=1)
        t = np.take_along_axis(t, order[:, :, None], axis=1)
        mid = (t[:, 0] + t[:, 1]) / 2
        t = np.concatenate(
            [np.stack([t[:, 0], mid, t[:, 2]], 1), np.stack([mid, t[:, 1], t[:, 2]], 1)]
        )
        ti = np.concatenate([ti, ti])
    return np.concatenate(pts), np.concatenate(idx)


def tri_normals(tris: np.ndarray) -> np.ndarray:
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return np.where(ln > 1e-12, n / np.maximum(ln, 1e-12), np.array([0.0, 1.0, 0.0]))


def hole_lines(part: Any) -> np.ndarray:
    """Pin holes as lines (k, 8): connectors on one line (parallel, within 1 LDU) are one."""
    found: list[tuple[np.ndarray, np.ndarray, list[float]]] = []
    for c in part.connectors:
        if c.kind != "pin hole":
            continue
        d = c.axis / np.linalg.norm(c.axis)
        for p0, d0, ts in found:
            if abs(float(d0 @ d)) > 0.99 and np.linalg.norm(np.cross(c.pos - p0, d0)) < 1.0:
                ts.append(float((c.pos - p0) @ d0))
                break
        else:
            found.append((c.pos, d, [0.0]))
    rows = []
    for p0, d, ts in found:
        lo, hi = min(ts), max(ts)
        if hi - lo < 1.0:  # drawn at one end only: its axis points into the part
            hi = lo + 10.0
        rows.append([*p0, *d, lo, hi])
    return np.array(rows, dtype=float).reshape(-1, 8)


def self_visible(pts: np.ndarray, pix: float = SELF_PIX) -> np.ndarray:
    """(n, 6): whether each point is the nearest of the part's own points in its pixel of
    ``pix`` LDU seen from each axis direction (the first in order wins a tie)."""
    out = np.zeros((len(pts), 6), dtype=bool)
    if not len(pts):
        return out
    for k, (ax, sign) in enumerate(((0, -1), (0, 1), (1, -1), (1, 1), (2, -1), (2, 1))):
        a, b = (q for q in range(3) if q != ax)
        d = -sign * pts[:, ax]  # seen from the sign side: nearer is smaller
        i = np.floor((pts[:, a] - pts[:, a].min()) / pix).astype(np.int64)
        j = np.floor((pts[:, b] - pts[:, b].min()) / pix).astype(np.int64)
        idx = j * (int(i.max()) + 1) + i
        buf = np.full(int(idx.max()) + 1, np.inf)
        np.minimum.at(buf, idx, d)
        win = np.nonzero(d <= buf[idx])[0]
        first = np.full(len(buf), -1, dtype=np.int64)
        first[idx[win[::-1]]] = win[::-1]
        out[first[first >= 0], k] = True
    return out


def build_points(key: str, lib: Library) -> PartPoints:
    part = lib.part(key)
    body = lib.triangles(key)
    full = solid.triangles(key, lib)
    studt = full[len(body) :]
    pb, ib = split_points(body)
    ps, is_ = split_points(studt)
    nb = tri_normals(body)[ib] if len(body) else np.zeros((0, 3))
    ns = tri_normals(studt)[is_] if len(studt) else np.zeros((0, 3))
    cell = np.zeros(len(pb), dtype=bool)
    studs = part.studs
    if studs and len(pb):
        # each stud's cell: across its axis (u, w) within 10, along it (a, scaled by 10)
        # within 1 LDU: a Chebyshev distance of 10 in (u, w, 10 a)
        for axis in sorted({tuple(np.round(s.axis, 3)) for s in studs}):
            ax = np.array(axis)
            r = solid._rot_from_down(ax)
            e1, e2 = r @ np.array([1.0, 0, 0]), r @ np.array([0, 0, 1.0])
            group = np.array([s.pos for s in studs if tuple(np.round(s.axis, 3)) == axis])
            sc = np.stack([group @ e1, group @ e2, (group @ ax) * 10], 1)
            facing_ok = np.abs(nb @ ax) >= 0.9
            if not facing_ok.any():
                continue
            q = pb[facing_ok]
            qc = np.stack([q @ e1, q @ e2, (q @ ax) * 10], 1)
            dist, _ = KDTree(sc).query(qc, k=1, p=np.inf, distance_upper_bound=10.0001)
            cell[np.nonzero(facing_ok)[0][np.isfinite(dist)]] = True
    pts = np.concatenate([pb, ps]).astype(np.float32)
    nrm = np.concatenate([nb, ns]).astype(np.float32)
    stud = np.concatenate([cell, np.ones(len(ps), dtype=bool)])
    holes = hole_lines(part)
    hole = np.full(len(pts), -1, dtype=np.int32)
    for k, row in enumerate(holes):
        p0, d, lo, hi = row[:3], row[3:6], row[6], row[7]
        rel = pts - p0
        t = rel @ d
        rad = np.linalg.norm(rel - np.outer(t, d), axis=1)
        hole[(rad < 8) & (t >= lo - 0.5) & (t <= hi + 0.5)] = k
    mid = (part.bbox_min[1] + part.bbox_max[1]) / 2
    top = (np.abs(nrm[:, 1]) >= 0.35) & (pts[:, 1] <= mid) & ~stud
    vis = self_visible(pts)
    keep = vis.any(1)
    return PartPoints(pts[keep], nrm[keep], stud[keep], hole[keep], top[keep], vis[keep], holes)


def _cache_file(key: str) -> Path:
    safe = re.sub(r"[^a-z0-9._-]", "_", key.lower())
    return cache_dir() / "looks" / f"{safe}.v{VERSION}.npz"


_FIELDS = ("pts", "nrm", "stud", "hole", "top", "vis", "holes")


def _read_cache(path: Path, stamp: str) -> PartPoints | None:
    """The cached points, or None when the file is missing, damaged, stale or inconsistent."""
    try:
        with np.load(path, allow_pickle=False) as data:
            if str(data["stamp"]) != stamp:
                return None
            got = {k: np.asarray(data[k]) for k in _FIELDS}
    except Exception:  # any unreadable or damaged file is built again
        return None
    n = len(got["pts"])
    ok = (
        got["pts"].shape == (n, 3)
        and got["nrm"].shape == (n, 3)
        and got["vis"].shape == (n, 6)
        and all(got[k].shape == (n,) for k in ("stud", "hole", "top"))
        and got["holes"].ndim == 2
        and got["holes"].shape[1] == 8
        and bool(np.all(np.isfinite(got["pts"])))
        and bool(np.all(got["hole"] < len(got["holes"])))
    )
    if not ok:
        return None
    return PartPoints(
        got["pts"].astype(np.float32),
        got["nrm"].astype(np.float32),
        got["stud"].astype(bool),
        got["hole"].astype(np.int32),
        got["top"].astype(bool),
        got["vis"].astype(bool),
        got["holes"].astype(float),
    )


def _write_cache(path: Path, stamp: str, pp: PartPoints) -> None:
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
        with tmp.open("wb") as f:
            np.savez(f, stamp=np.array(stamp), **{k: getattr(pp, k) for k in _FIELDS})
        os.replace(tmp, path)


def part_points(key: str, lib: Library | None = None) -> PartPoints:
    """A part file's sample points (see the contract), from memory, the disk cache, or built."""
    with _LOCK:
        if key in _POINTS:
            return _POINTS[key]
    lib = lib or library()
    path = _cache_file(key)
    got = _read_cache(path, lib.stamp)
    if got is None:
        got = build_points(key, lib)
        _write_cache(path, lib.stamp, got)
    with _LOCK:
        if len(_POINTS) > 400:
            _POINTS.clear()
        _POINTS[key] = got
    return got


# ---- colours -----------------------------------------------------------------------------------

_LDCONFIG: dict[int, tuple[str, tuple[int, int, int], bool]] = {}


def colours(lib: Library | None = None) -> dict[int, tuple[str, tuple[int, int, int], bool]]:
    """LDraw colour code -> (name, rgb, transparent) from LDConfig.ldr."""
    if not _LDCONFIG:
        lib = lib or library()
        try:
            text = lib._zip.read("ldraw/LDConfig.ldr").decode("utf-8", errors="replace")
        except KeyError:
            return {}
        pat = re.compile(r"\s*0\s+!COLOUR\s+(\S+)\s+CODE\s+(\d+)\s+VALUE\s+#([0-9A-Fa-f]{6})")
        for line in text.splitlines():
            m = pat.match(line)
            if m:
                a = re.search(r"ALPHA\s+(\d+)", line)
                h = m.group(3)
                rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                trans = bool(a and int(a.group(1)) < 255)
                _LDCONFIG[int(m.group(2))] = (m.group(1).replace("_", " "), rgb, trans)
    return _LDCONFIG


# ---- the skin ----------------------------------------------------------------------------------


@dataclass
class View:
    name: str
    owner: np.ndarray  # (h, w) global point index, or -1
    depth: np.ndarray  # (h, w), NaN where empty
    kind: np.ndarray  # (h, w): 0 empty, or STUDDED... HOLE
    part: np.ndarray  # (h, w) index in ``placed``, or -1
    colour: np.ndarray  # (h, w) LDraw colour, or -1
    wall: np.ndarray  # (h, w) smooth flat and facing the viewer
    sidetop: np.ndarray  # (h, w) the top face of a part whose up is not world up
    shade: np.ndarray  # (h, w) |normal . view direction|


@dataclass
class Skin:
    placed: list[Any]
    views: dict[str, View]
    points: np.ndarray  # (N, 3) world
    normals: np.ndarray  # (N, 3) world
    owner: np.ndarray  # (N,) index in ``placed``
    stud: np.ndarray  # (N,)
    hole: np.ndarray  # (N,) hole index in its part, or -1
    hole_open: np.ndarray  # (N,) on a hole nothing fills
    upright: np.ndarray  # (len(placed),) the part's own up is world up
    filled: set[tuple[int, int]]  # (placed index, hole index) of filled holes
    holes: int  # hole lines in all parts


def is_up(m: np.ndarray) -> bool:
    """Whether a part's own up (-y) is within 25 degrees of world up."""
    return float(-(m @ np.array([0.0, -1.0, 0.0]))[1]) > UP_COS


def _filled_holes(placed: list[Any], pps: list[PartPoints]) -> set[tuple[int, int]]:
    plugs = []
    for i, p in enumerate(placed):
        pts = [c.points() for c in p.part.connectors if c.kind in ("pin", "axle", "bar handle")]
        if pts:
            plugs.append((i, p.to_world(np.concatenate(pts))))
    out: set[tuple[int, int]] = set()
    if not plugs:
        return out
    for i, (p, pp) in enumerate(zip(placed, pps, strict=True)):
        for k, row in enumerate(pp.holes):
            w0 = p.to_world(row[None, :3])[0]
            wd = p.m @ row[3:6]
            for j, q in plugs:
                if j == i:
                    continue
                rel = q - w0
                t = rel @ wd
                r = np.linalg.norm(rel - np.outer(t, wd), axis=1)
                if np.any((r < 3) & (t >= row[6] - 1) & (t <= row[7] + 1)):
                    out.add((i, k))
                    break
    return out


def render(
    view: tuple[str, int, int, int, int, int, int],
    pts: np.ndarray,
    sel: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """The z-buffer of one view over the points ``sel``: per pixel the index of the nearest
    point (-1 for none) and its depth."""
    _, da, ds, ua, us, va, vs = view
    u = pts[sel, ua] * us
    v = pts[sel, va] * vs
    d = pts[sel, da] * ds
    umin = min(lo[ua] * us, hi[ua] * us)
    vmin = min(lo[va] * vs, hi[va] * vs)
    w = int(math.ceil(abs(hi[ua] - lo[ua]) / PIX)) + 2
    h = int(math.ceil(abs(hi[va] - lo[va]) / PIX)) + 2
    i = np.clip(((u - umin) / PIX).astype(np.int64) + 1, 0, w - 1)
    j = np.clip(((v - vmin) / PIX).astype(np.int64) + 1, 0, h - 1)
    idx = j * w + i
    buf = np.full(w * h, np.inf)
    np.minimum.at(buf, idx, d)
    win = np.nonzero(d <= buf[idx])[0]
    owner = np.full(w * h, -1, dtype=np.int64)
    owner[idx[win[::-1]]] = sel[win[::-1]]  # the first point in order wins a tie
    return owner.reshape(h, w), buf.reshape(h, w)


def skin(
    placed: list[Any],
    lib: Library | None = None,
    extra_views: tuple[tuple[str, int, int, int, int, int, int], ...] = (),
) -> Skin:
    """The five views (and any ``extra_views``) of the placed parts (see the contract)."""
    lib = lib or library()
    cfg = colours(lib)
    pps = [part_points(p.key, lib) for p in placed]
    counts = np.array([len(pp.pts) for pp in pps], dtype=np.int64)
    start = np.concatenate([[0], np.cumsum(counts)])
    n = len(placed)
    pts = np.concatenate(
        [
            pp.pts @ p.m.T.astype(np.float32) + p.pos.astype(np.float32)
            for pp, p in zip(pps, placed, strict=True)
        ]
    )
    nrm = np.concatenate(
        [pp.nrm @ p.m.T.astype(np.float32) for pp, p in zip(pps, placed, strict=True)]
    )
    owner = np.repeat(np.arange(n), counts)
    stud = np.concatenate([pp.stud for pp in pps])
    top = np.concatenate([pp.top for pp in pps])
    hole = np.concatenate([pp.hole for pp in pps])
    vis = np.concatenate([pp.vis for pp in pps])
    filled = _filled_holes(placed, pps)
    hole_open = hole >= 0
    for i, k in filled:
        s = slice(start[i], start[i + 1])
        hole_open[s] &= hole[s] != k
    trans_p = np.array([cfg.get(p.colour, ("", (0, 0, 0), False))[2] for p in placed])
    colour_p = np.array([p.colour for p in placed])
    upright = np.array([is_up(p.m) for p in placed])
    cols = np.ascontiguousarray(pts.T)  # a column at a time is ten times faster
    lo = cols.min(1) - 1
    hi = cols.max(1) + 1

    def kind_of(o: np.ndarray) -> np.ndarray:
        """The kind of skin at points ``o`` (only the points the views show are classified)."""
        flat = np.abs(nrm[o]).max(-1) >= FLAT_COS
        return np.where(
            trans_p[owner[o]],
            TRANS,
            np.where(hole_open[o], HOLE, np.where(stud[o], STUDDED, np.where(flat, FLAT, CURVED))),
        )

    views: dict[str, View] = {}
    for view in [*VIEWS, *extra_views]:
        cam = np.zeros(3)
        cam[view[1]] = -view[2]  # the way from the model to the camera
        mask = np.zeros(len(pts), dtype=bool)
        for i, p in enumerate(placed):
            c = p.m.T @ cam
            k = int(np.argmax(np.abs(c)))
            s = slice(start[i], start[i + 1])
            mask[s] = vis[s, 2 * k + int(c[k] > 0)] if abs(c[k]) > 0.999 else True
        got, depth = render(view, pts, np.nonzero(mask)[0], lo, hi)
        ok = got >= 0
        o = np.where(ok, got, 0)
        shade = np.where(ok, np.abs(nrm[o, view[1]]), 0)
        kind = np.where(ok, kind_of(o), 0)
        views[view[0]] = View(
            view[0],
            got,
            np.where(ok, depth, np.nan),
            kind,
            np.where(ok, owner[o], -1),
            np.where(ok, colour_p[owner[o]], -1),
            ok & (shade >= FLAT_COS) & (kind == FLAT),
            ok & top[o] & ~upright[owner[o]] & (kind != TRANS),
            shade,
        )
    return Skin(
        placed,
        views,
        pts,
        nrm,
        owner,
        stud,
        hole,
        hole_open,
        upright,
        filled,
        int(sum(len(pp.holes) for pp in pps)),
    )


# ---- the measures ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Looks:
    parts: int
    seams_per_stud: float
    not_upright: float
    side_top_faces: float
    largest_colour: float
    largest_colour_name: str
    colours_5pct: int
    patch_coherence: float
    primary_share: float
    open_holes: int
    plain_bricks: float
    clips_bars: float
    studs: int
    studs_showing: int
    studs_showing_share: float


def seams_per_stud(sk: Skin) -> float:
    side = [sk.views[s] for s in SIDES]
    px = sum(int((v.kind > 0).sum()) for v in side)
    seams = 0
    for v in side:
        a, b = v.part[:-1], v.part[1:]
        flush = np.abs(np.nan_to_num(v.depth[:-1]) - np.nan_to_num(v.depth[1:])) <= SEAM_DEPTH
        seams += int(((a >= 0) & (b >= 0) & (a != b) & v.wall[:-1] & v.wall[1:] & flush).sum())
    return seams * 20 / (px * PIX) if px else 0.0


# the side views in facing pairs, with the way their faces point (``skin``'s "facing")
PAIRS = (
    ("front/back", ("front", "back"), ("-z", "+z")),
    ("left/right", ("left", "right"), ("-x", "+x")),
)
WHERE_LINES = 4  # lines named for a pair's seams


@dataclass(frozen=True)
class Face:
    """One facing pair of side views: its seams per stud, the share of its skin that is the
    face of a sideways tile or slope, and the lines whose edges make most of its seams
    (line number, description, seam pixels), most first."""

    seams: float
    sideways: float
    lines: list[tuple[int, str, int]]


def faces(sk: Skin) -> dict[str, Face]:
    """``seams_per_stud`` and ``side_top_faces`` per facing pair (``PAIRS``), with the lines
    that make the seams."""
    out = {}
    for name, views, _ in PAIRS:
        px = seams = top = 0
        count: dict[int, int] = {}
        for s in views:
            v = sk.views[s]
            a, b = v.part[:-1], v.part[1:]
            flush = np.abs(np.nan_to_num(v.depth[:-1]) - np.nan_to_num(v.depth[1:])) <= SEAM_DEPTH
            m = (a >= 0) & (b >= 0) & (a != b) & v.wall[:-1] & v.wall[1:] & flush
            seams += int(m.sum())
            px += int((v.kind > 0).sum())
            top += int(v.sidetop.sum())
            for i in np.concatenate([a[m], b[m]]).tolist():
                count[i] = count.get(i, 0) + 1
        most = sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))
        named = [(sk.placed[i].line, _desc(sk.placed[i]), n) for i, n in most]
        out[name] = Face(
            seams=round(seams * 20 / (px * PIX), 3) if px else 0.0,
            sideways=round(top / px, 3) if px else 0.0,
            lines=named,
        )
    return out


def _named(lines: list[tuple[int, str, int]]) -> str:
    """'lines 21, 37 (Plate 1 x 4), 17 (Brick 1 x 2)': the first ``WHERE_LINES``, grouped
    by description in the order met."""
    groups: dict[str, list[int]] = {}
    for line, desc, _ in lines[:WHERE_LINES]:
        groups.setdefault(desc, []).append(line)
    return "lines " + ", ".join(
        ", ".join(str(n) for n in ns) + f" ({d})" for d, ns in groups.items()
    )


def where(lk: Looks, fs: dict[str, Face]) -> tuple[str, str]:
    """Where the seams and the missing sideways faces are: a sentence for each measure that
    is outside its range (empty when it is not), naming the facing pairs out of range, the
    lines that make their seams, and the fix in one line (``skin`` on side studs)."""
    seams = side = ""
    facing = {name: f for name, _, f in PAIRS}
    if outside(lk.seams_per_stud, SEAMS):
        bad = [(n, f) for n, f in fs.items() if f.seams > SEAMS[1] and f.lines]
        bad.sort(key=lambda nf: -nf[1].seams)  # the worst first
        if bad:
            seams = (
                " Where: "
                + "; ".join(f"{n} {f.seams:.2f}, mostly {_named(f.lines)}" for n, f in bad)
                + (". Skin that flank" if len(bad) == 1 else ". Skin those flanks")
                + ": skin with facing "
                + " or ".join(f'"{x}"' for n, _ in bad for x in facing[n])
                + " on side studs; where the core has none, put side-stud bricks or "
                "brackets there first."
            )
    if outside(lk.not_upright, NOT_UPRIGHT) or outside(lk.side_top_faces, SIDE_TOP_FACES):
        bad = [(n, f) for n, f in fs.items() if f.sideways < SIDE_TOP_FACES[0]]
        if bad:
            side = (
                " Where: "
                + "; ".join(f"{n} {_pct(f.sideways)} sideways faces" for n, f in bad)
                + ". Skin those sides: skin with facing "
                + " or ".join(f'"{x}"' for n, _ in bad for x in facing[n])
                + " on side studs (side-stud bricks or brackets in the core first)."
            )
    return seams, side


def side_top_faces(sk: Skin) -> float:
    side = [sk.views[s] for s in SIDES]
    px = sum(int((v.kind > 0).sum()) for v in side)
    return sum(int(v.sidetop.sum()) for v in side) / px if px else 0.0


def stud_parts(placed: list[Any]) -> list[int]:
    """Indexes of the parts with studs or a socket underneath."""
    return [i for i, p in enumerate(placed) if p.part.studs or p.part.has_sockets()]


def not_upright(sk: Skin) -> float:
    sp = stud_parts(sk.placed)
    return sum(1 for i in sp if not sk.upright[i]) / len(sp) if sp else 0.0


def colour_shares(sk: Skin) -> dict[int, float]:
    count: dict[int, int] = {}
    for name, _, _, _, _, _, _ in VIEWS:
        v = sk.views[name]
        cs, ns = np.unique(v.colour[v.colour >= 0], return_counts=True)
        for c, k in zip(cs.tolist(), ns.tolist(), strict=True):
            count[c] = count.get(c, 0) + k
    tot = sum(count.values())
    return {c: k / tot for c, k in count.items()} if tot else {}


def patch_coherence(sk: Skin) -> float:
    sq = total = 0.0
    for name, _, _, _, _, _, _ in VIEWS:
        v = sk.views[name]
        for c in np.unique(v.colour[v.colour >= 0]):
            lab, nl = ndimage.label(v.colour == c)
            if nl:
                sizes = np.bincount(lab.ravel())[1:].astype(float)
                sq += float((sizes**2).sum())
                total += float(sizes.sum())
    return (sq / total) / (total / len(VIEWS)) if total else 0.0


def open_holes(sk: Skin) -> int:
    seen: set[tuple[int, int]] = set()
    for name, _, _, _, _, _, _ in VIEWS:
        v = sk.views[name]
        o = v.owner[v.owner >= 0]
        hk = sk.hole[o]
        sel = (hk >= 0) & sk.hole_open[o]
        keys: dict[tuple[int, int], int] = {}
        for key in zip(sk.owner[o][sel].tolist(), hk[sel].tolist(), strict=True):
            keys[key] = keys.get(key, 0) + 1
        seen |= {k for k, c in keys.items() if c >= HOLE_SHOWS}
    return len(seen)


def _under(p: Any, pts: np.ndarray, dirs: np.ndarray) -> np.ndarray:
    """Which stud probes (world points, with the way each stud points) are inside the part's
    filled body or just under its underside (see the contract)."""
    part = p.part
    loc = p.to_local(pts)
    ins = part.inside(loc)
    if part.top is None or part.bottom is None:
        return ins
    i, j, ok = part.column_index(loc[:, 0], loc[:, 2])
    t = part.top[i, j]
    b = part.bottom[i, j]
    up = (dirs @ p.m)[:, 1] < -UP_COS  # the stud's direction in the part's frame
    with np.errstate(invalid="ignore"):
        return ins | (ok & up & (t < loc[:, 1]) & (loc[:, 1] < b + 6))


def world_box(p: Any) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = p.part.bbox_min, p.part.bbox_max
    c = np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )
    w = p.to_world(c)
    return w.min(0), w.max(0)


@dataclass
class Studs:
    pos: np.ndarray  # (n, 3) world base of each stud
    way: np.ndarray  # (n, 3) world direction
    owner: np.ndarray  # (n,) index in placed
    single: np.ndarray  # (n,) on a part with one stud and a 1 x 1 body
    showing: np.ndarray  # (n,) nothing on it


def studs(report: Any) -> Studs:
    """Every male stud of the model and whether it is showing (see the contract)."""
    from bricksnap.lab.validate import numbered_studs

    placed = report.placed
    linked = {(k.holder, s) for k in report.links for s in k.studs}
    pos, way, own, single, held = [], [], [], [], []
    for i, p in enumerate(placed):
        sz = p.part.bbox_max - p.part.bbox_min
        one = len(p.part.studs) == 1 and sz[0] <= 21 and sz[2] <= 21
        for s, c in enumerate(numbered_studs(p.part), 1):
            held.append((p.line, s) in linked)
            pos.append(p.to_world(c.pos[None])[0])
            way.append(p.m @ c.axis)
            own.append(i)
            single.append(one)
    if not pos:
        z = np.zeros(0, dtype=bool)
        return Studs(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, dtype=int), z, z)
    pos_a, way_a, own_a = np.array(pos), np.array(way), np.array(own)
    probes = np.concatenate([pos_a + 2 * way_a, pos_a + 6 * way_a])
    pown = np.concatenate([own_a, own_a])
    pdir = np.concatenate([way_a, way_a])
    covered = np.zeros(len(probes), dtype=bool)
    for i, p in enumerate(placed):
        blo, bhi = world_box(p)
        near = np.all((probes >= blo - 7) & (probes <= bhi + 7), axis=1)
        sel = np.nonzero(near & (pown != i) & ~covered)[0]
        if len(sel):
            covered[sel[_under(p, probes[sel], pdir[sel])]] = True
    cov = covered[: len(pos)] | covered[len(pos) :] | np.array(held)
    return Studs(pos_a, way_a, own_a, np.array(single), ~cov)


def counted(placed: list[Any]) -> list[Any]:
    """The parts the two parts-list shares count: all but stickers and minifigure parts."""
    return [p for p in placed if not NOT_COUNTED.match(_desc(p))]


def _desc(p: Any) -> str:
    return p.part.description.lstrip("~_=").strip()


def plain_bricks(placed: list[Any]) -> float:
    ps = counted(placed)
    return sum(1 for p in ps if PLAIN_BRICK.match(_desc(p))) / len(ps) if ps else 0.0


def clips_bars(placed: list[Any]) -> float:
    ps = counted(placed)
    hits = [
        p for p in ps if CLIP_BAR.search(_desc(p)) and not _desc(p).lower().startswith("technic")
    ]
    return len(hits) / len(ps) if ps else 0.0


def measure_skin(report: Any, sk: Skin) -> Looks:
    cfg = colours()
    shares = colour_shares(sk)
    big = max(shares.items(), key=lambda kv: (kv[1], -kv[0])) if shares else (-1, 0.0)
    st = studs(report)
    placed = report.placed
    return Looks(
        parts=len(placed),
        seams_per_stud=round(seams_per_stud(sk), 3),
        not_upright=round(not_upright(sk), 3),
        side_top_faces=round(side_top_faces(sk), 3),
        largest_colour=round(big[1], 3),
        largest_colour_name=cfg.get(big[0], (str(big[0]),))[0] if shares else "",
        colours_5pct=sum(1 for v in shares.values() if v >= 0.05),
        patch_coherence=round(patch_coherence(sk), 3),
        primary_share=round(float(sum(v for c, v in shares.items() if c in PRIMARIES)), 3),
        open_holes=open_holes(sk),
        plain_bricks=round(plain_bricks(placed), 3),
        clips_bars=round(clips_bars(placed), 3),
        studs=len(st.showing),
        studs_showing=int(st.showing.sum()),
        studs_showing_share=round(float(st.showing.mean()), 3) if len(st.showing) else 0.0,
    )


def measure(report: Any, lib: Library | None = None) -> Looks | None:
    """How the checked model looks; None when it has no parts."""
    if not report.placed:
        return None
    return measure_skin(report, skin(report.placed, lib))


def measure_text(text: str) -> Looks | None:
    """Check ``text`` and measure it; None when it cannot be measured (never raises)."""
    try:
        from bricksnap.lab.validate import check

        return measure(check(text, movement=False))
    except Exception:  # advice only: a model that cannot be measured simply has none
        return None


def record(looks: Looks) -> dict[str, Any]:
    return asdict(looks)


# ---- the words ---------------------------------------------------------------------------------


def _pct(v: float) -> str:
    return f"{round(100 * v)}%"


def _range(r: tuple[float, float, str], pct: bool = True) -> str:
    if pct:
        return f"{_pct(r[0])} to {_pct(r[1])}"
    if r[0] == int(r[0]) and r[1] == int(r[1]):
        return f"{r[0]:g} to {r[1]:g}"
    return f"{r[0]:.2f} to {r[1]:.2f}"


def outside(v: float, r: tuple[float, float, str]) -> bool:
    """Outside the range on the side that needs advice."""
    return v > r[1] if r[2] == "high" else v < r[0]


def _state(v: float, r: tuple[float, float, str]) -> str:
    if outside(v, r):
        return ""
    if v < r[0]:
        return "below the range, which is fine"
    if v > r[1]:
        return "above the range, which is fine"
    return "in range"


def lines(looks: Looks, fs: dict[str, Face] | None = None) -> list[str]:
    """The HOW IT LOOKS lines (see the contract): at most seven. With the facing pairs
    (``faces``), the seams and sideways lines also say where (``where``)."""
    out = []
    lk = looks
    at_seams, at_side = where(lk, fs) if fs else ("", "")
    s = _state(lk.seams_per_stud, SEAMS)
    out.append(
        f"Plate seams on the sides: {lk.seams_per_stud:.2f} per stud of height (official "
        f"{_range(SEAMS, False)})"
        + (
            f": {s}."
            if s
            else ". The flanks read as stacked plates: face them with tiles or panels turned "
            "sideways, or use bricks and curved slopes where plates are stacked." + at_seams
        )
    )
    bad = outside(lk.not_upright, NOT_UPRIGHT) or outside(lk.side_top_faces, SIDE_TOP_FACES)
    out.append(
        f"Built sideways: {_pct(lk.not_upright)} of parts with studs are not upright, and "
        f"{_pct(lk.side_top_faces)} of what you see from the sides is the face of a sideways "
        f"tile or slope (official {_range(NOT_UPRIGHT)} of parts, {_range(SIDE_TOP_FACES)} of "
        "the sides)"
        + (
            ". Build the flanks and faces as panels on side studs (brackets, bricks with studs "
            "on the side) covered with tiles and curved slopes." + at_side
            if bad
            else ": in range."
        )
    )
    bad = outside(lk.largest_colour, LARGEST_COLOUR) or outside(lk.patch_coherence, PATCH_COHERENCE)
    out.append(
        f"Colour areas: {lk.largest_colour_name.lower() or 'one colour'} is "
        f"{_pct(lk.largest_colour)} of what you see, patch coherence {lk.patch_coherence:.2f} "
        f"(official {_range(LARGEST_COLOUR)} for the largest colour, coherence "
        f"{_range(PATCH_COHERENCE, False)})"
        + (
            ". Colour comes in big plain areas: break them with trim, stripes, a contrasting "
            "nose, edge or panel."
            if bad
            else ": in range."
        )
    )
    advice = []
    if outside(lk.colours_5pct, COLOURS_5PCT):
        advice.append(
            "Use one or two more colours in smaller amounts (a darker or earthy tone, a grey, "
            "a metallic or transparent accent)."
        )
    if outside(lk.primary_share, PRIMARY_SHARE):
        advice.append("Use fewer bright primaries: official sets now favour other tones.")
    out.append(
        f"Palette: {lk.colours_5pct} colours each cover 5% or more, {_pct(lk.primary_share)} is "
        f"classic red, blue, yellow or green (official {COLOURS_5PCT[0]:g} to "
        f"{COLOURS_5PCT[1]:g} colours, {_range(PRIMARY_SHARE)} classic primaries)"
        + (". " + " ".join(advice) if advice else ": in range.")
    )
    s = _state(lk.open_holes, OPEN_HOLES)
    out.append(
        f"Open Technic holes facing out: {lk.open_holes} (official {_range(OPEN_HOLES, False)})"
        + (
            f": {s}."
            if s
            else ". Turn them inward, cover them, or use bars, axles or smooth beams where "
            "the holes show."
        )
    )
    advice = []
    if outside(lk.plain_bricks, PLAIN_BRICKS):
        advice.append(
            "Shape with slopes, curved slopes, wedges and brackets rather than plain bricks."
        )
    if outside(lk.clips_bars, CLIPS_BARS):
        advice.append(
            "Use clips, bars and handles for thin and angled details (rails, struts, "
            "antennas, mirrors, parts set at an angle)."
        )
    out.append(
        f"Parts: plain bricks are {_pct(lk.plain_bricks)} of the parts, clips, bars and handles "
        f"{_pct(lk.clips_bars)} (official {_range(PLAIN_BRICKS)} and {_range(CLIPS_BARS)})"
        + (". " + " ".join(advice) if advice else ": in range.")
    )
    if outside(lk.studs_showing_share, STUDS_SHOWING):
        out.append(
            f"Studs showing: {_pct(lk.studs_showing_share)} of studs (official "
            f"{_range(STUDS_SHOWING)}). Cover the studs that are not meant to show with tiles."
        )
    return out


SECTION_HEADING = (
    "HOW IT LOOKS (advice, never a problem: measured on views from above and the four sides, "
    "against the middle half of official sets):"
)


def section(looks: Looks | None, fs: dict[str, Face] | None = None) -> str:
    if looks is None:
        return ""
    return SECTION_HEADING + "\n" + "\n".join("- " + ln for ln in lines(looks, fs))


def measure_where(report: Any, lib: Library | None = None) -> tuple[Looks, dict[str, Face]] | None:
    """``measure`` and ``faces`` from one skin; None when the model has no parts."""
    if not report.placed:
        return None
    sk = skin(report.placed, lib)
    return measure_skin(report, sk), faces(sk)


def page_lines(rec: dict[str, Any]) -> list[str]:
    """Short plain sentences, with the official range, for a person (the free-build page)."""
    try:
        return [
            f"Plate seams on the sides: {float(rec['seams_per_stud']):.2f} per stud of height "
            f"(official sets: {_range(SEAMS, False)})",
            f"Built sideways: {_pct(float(rec['not_upright']))} of parts (official sets: "
            f"{_range(NOT_UPRIGHT)})",
            f"Largest colour: {_pct(float(rec['largest_colour']))} of what you see (official "
            f"sets: {_range(LARGEST_COLOUR)})",
            f"Open Technic holes showing: {int(rec['open_holes'])} (official sets: "
            f"{_range(OPEN_HOLES, False)})",
        ]
    except (KeyError, TypeError, ValueError):
        return []
