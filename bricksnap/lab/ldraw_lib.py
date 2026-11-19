"""Read LDraw parts straight from the library zip (research prototype; see ``__init__``).

CONTRACT (tests in tests/test_lab.py)

``Library(zip_path=None)`` opens the LDraw library zip (default
``~/.cache/bricksnap/ldraw/leocad-library.zip``, or ``$BRICKSNAP_LDRAW_ZIP``) and reads from
it directly; nothing is unpacked.

- ``resolve(name)`` -> ``("part", key)``, ``("subpart", key)``, ``("primitive", key)`` or
  None. Names are matched without regard to case or slash direction, as LDraw does: a part
  is looked up in ``parts/`` (``s/`` for sub-parts), then in ``p/`` (with ``48/`` and ``8/``).
- ``header(key)`` -> ``Header``: description, ``!LDRAW_ORG`` type, ``!CATEGORY`` (or the first
  word of the description, the LDraw convention when there is none), ``!KEYWORDS``.
- ``part(name)`` -> ``Part``, the part resolved to its triangles in its own frame by following
  every type-1 reference through parts, ``s/``, ``p/``, ``p/48/`` and ``p/8/`` with its
  matrix. Type 3 and type 4 lines are its surface; lines (types 2 and 5) are ignored. BFC
  winding is not needed and is ignored.

Connectors, from the geometry only
- Every reference to a stud primitive gives a connector: position (the primitive's origin)
  and direction, in the part's own frame. Male studs (``MALE_STUD``: ``stud``, ``stud2``
  (open), ``studa``, ``stud6``/``stud10``/``stud15`` (round parts), ``stud-logo*``... read from
  ``ldraw/p/``) are kind "stud"; their direction is the way the stud points out of the part
  (the primitive's -y). A stud pointing up in the part's frame is "on top"; any other way is
  "on the side" (or "underneath").
- Underside tubes are kind "tube": open tubes (``stud4*``, ``stud16*``, ``stud18a``,
  ``stud21a``, ``stud22a``, ``stud2s*``, ``stud23*``) take a stud inside them; solid ones
  (``stud3*``, ``stud12``) do not. Each records its open end (``end``).
- Other connectors are named and located, never checked: Technic pins (``connect*``,
  ``confric*``), pin holes (``peghole*``, ``npeghol*``, ``connhol*``, ``beamhol*``), axles
  (``axle``), axle holes (``axlehole``, ``axlehol*``, ``axl?hole``...), clips (``clip*``),
  click hinges (``clh*``, ``h1``, ``h2``, ``arm*``), ball joints (``joint8ball``,
  ``joint8socket*``), wheel pins and holes (``wpin*``, ``wpinhol*``), bar handles
  (``phandle*``). Their axis is the primitive's y axis. Bars have no primitive (they are
  plain cylinders), so a bar is only known from the part's name.
- A connector primitive found inside another connector primitive is not counted again, and
  connectors of the same kind at the same place are counted once.

The filled body (rough, for the checks)
- The body is the surface without the male studs. It is described by columns on a 2 LDU
  grid in the part's frame (column centres at odd coordinates, so they never lie on the
  usual edges at multiples of 2): for each column, the topmost and lowest surface crossing
  its centre. A column is then filled from its top down to the deepest bottom it is
  enclosed by on all four sides (the lowest of the four directional maxima), so the hollow
  underside of a brick counts as solid while the open span of an arch or the space under an
  overhanging slope stays empty. ``inside(points)`` tests points against this; ``samples()``
  gives points that fill it, each with the volume it stands for.
- This misses walls thinner than about 2 LDU and anything a single top/bottom per column
  cannot describe (a hollow seen from the side, such as a pin hole: it counts as solid).

Parsed parts are cached as pickles under ``~/.cache/bricksnap/lab/parts/`` (or
``$BRICKSNAP_LAB_CACHE``), keyed by the zip's size and time and ``CACHE_VERSION``.
"""

from __future__ import annotations

import contextlib
import math
import os
import pickle
import re
import threading
import zipfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

CACHE_VERSION = 7
GRID = 2.0  # column spacing in LDU

MALE_STUD = re.compile(
    r"^(stud|studa|stud2|stud2a|stud6|stud6a|stud9|stud10|stud13|stud15|stud17|stud17a|"
    r"stud26|studel|studh|studhl|studhr|studp01|studx|studxa|stud-logo\d?|stud2-logo\d?)$"
)
OPEN_TUBE = re.compile(
    r"^(stud4[a-z0-9]*|stud16[a-z]*|stud18a|stud21a|stud22a|stud2s[a-z0-9]*|stud23d?)$"
)
SOLID_TUBE = re.compile(r"^(stud3a?|stud12)$")
OTHER_CONNECTORS: list[tuple[str, re.Pattern[str]]] = [
    ("pin", re.compile(r"^(connect\d*|confric\d*)$")),
    ("pin hole", re.compile(r"^(peghole\d*|npeghol\w*|connhol\w*|beamhol\w*)$")),
    ("axle", re.compile(r"^(axle|axles)$")),
    ("axle hole", re.compile(r"^(axlehole|axlehol\d+|axl\dhole|axl\dhol\d+)$")),
    ("clip", re.compile(r"^clip\d+$")),
    ("hinge", re.compile(r"^(clh\d+[a-z]*|h[12]|arm[123])$")),
    ("ball", re.compile(r"^joint8ball$")),
    ("ball socket", re.compile(r"^joint8socket\d$")),
    ("wheel pin", re.compile(r"^wpin\d*[a-z]*$")),
    ("wheel hole", re.compile(r"^wpinhol[e2]$")),
    ("bar handle", re.compile(r"^phandle\d$")),
]

# Words in a part's description that say it joins by something other than studs (bars have
# no primitive, so the name is all we have). Used to mark contacts as "not checked".
OTHER_JOINT_WORDS = re.compile(
    r"\b(clip|clips|bar|bars|handle|pin|pins|axle|axles|hinge|technic|wheel|wheels|tyre|tire|"
    r"ball|socket|towball|joint|rotor|propeller|turntable|hole|holes|lever|antenna|flag|"
    r"holder|minifig|figure|chain|hose|string|tap|joiner|connector|click|rotation|swivel)\b",
    re.I,
)


# The words that make a part with no connector primitive count as joining by something
# other than studs (bars, tyres, handles... are plain shapes in the library).
NAME_JOINT_WORDS = re.compile(
    r"\b(clip|clips|bar|bars|handle|handles|tyre|tire|wheel|wheels|hinge|pin|pins|axle|axles|"
    r"ball|socket|towball|antenna|flag|chain|hose|string|joint|rotor|propeller|turntable|lever|"
    r"click|swivel)\b",
    re.I,
)


def zip_path() -> Path:
    env = os.environ.get("BRICKSNAP_LDRAW_ZIP")
    return (
        Path(env) if env else Path.home() / ".cache" / "bricksnap" / "ldraw" / "leocad-library.zip"
    )


def cache_dir() -> Path:
    env = os.environ.get("BRICKSNAP_LAB_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "bricksnap" / "lab"


def norm_name(name: str) -> str:
    """LDraw file names compare without case and with either slash."""
    return name.strip().replace("\\", "/").lower()


@dataclass
class Header:
    description: str = ""
    org: str = ""  # !LDRAW_ORG type: Part, Shortcut, Subpart, Primitive...
    category: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class Connector:
    kind: str  # "stud", "tube", "pin", "pin hole", "axle", "axle hole", "clip", ...
    prim: str  # primitive file name without .dat
    pos: np.ndarray  # (3,) in the part's frame
    axis: np.ndarray  # (3,) unit; for studs, the way the stud points out of the part
    end: np.ndarray | None = None  # tubes: the open end
    open: bool = False  # tubes: takes a stud inside

    def transformed(self, m: np.ndarray, t: np.ndarray) -> Connector:
        axis = m @ self.axis
        n = float(np.linalg.norm(axis))
        return Connector(
            self.kind,
            self.prim,
            m @ self.pos + t,
            axis / n if n > 1e-12 else axis,
            None if self.end is None else m @ self.end + t,
            self.open,
        )


@dataclass
class _Raw:
    tris: np.ndarray  # (n, 3, 3)
    cons: list[Connector]
    missing: set[str]


def _disc(radius: float, n: int = 16) -> np.ndarray:
    a = np.linspace(0, 2 * np.pi, n + 1)
    ring = np.stack([radius * np.cos(a), np.zeros_like(a), radius * np.sin(a)], axis=1)
    return np.array([[np.zeros(3), ring[k], ring[k + 1]] for k in range(n)])


_STUD_BASE = _disc(6.0)
"""The disc a stud stands on, in the stud primitive's frame (radius 6, at y = 0)."""


def _classify(base: str) -> tuple[str, bool] | None:
    """(kind, open) for a connector primitive's base name, or None."""
    if MALE_STUD.match(base):
        return ("stud", False)
    if OPEN_TUBE.match(base):
        return ("tube", True)
    if SOLID_TUBE.match(base):
        return ("tube", False)
    for kind, pattern in OTHER_CONNECTORS:
        if pattern.match(base):
            return (kind, False)
    return None


@dataclass
class Part:
    """One part resolved to its geometry, connectors and filled-body columns."""

    name: str  # "3001.dat"
    header: Header
    tri_count: int
    bbox_min: np.ndarray  # of the body (without male studs)
    bbox_max: np.ndarray
    connectors: list[Connector]
    missing: list[str]
    col_origin: tuple[int, int] = (0, 0)  # column (0, 0) has its centre at x = 2*i0 + 1
    top: np.ndarray | None = None  # (nx, nz), NaN where there is no body
    bottom: np.ndarray | None = None  # filled bottom (after the enclosure rule)
    raw_bottom: np.ndarray | None = None  # the lowest surface itself (before that rule)
    _samples: tuple[np.ndarray, np.ndarray] | None = field(default=None, repr=False)
    _n_sockets: int | None = field(default=None, repr=False)

    @property
    def description(self) -> str:
        return self.header.description

    @property
    def studs(self) -> list[Connector]:
        return [c for c in self.connectors if c.kind == "stud"]

    @property
    def tubes(self) -> list[Connector]:
        return [c for c in self.connectors if c.kind == "tube"]

    @property
    def others(self) -> list[Connector]:
        return [c for c in self.connectors if c.kind not in ("stud", "tube")]

    def top_studs(self) -> list[Connector]:
        return [c for c in self.studs if c.axis[1] < -0.99]

    def size(self) -> tuple[float, float, float]:
        """Width (x) and depth (z) in studs, height (y) in plates, of the body."""
        d = self.bbox_max - self.bbox_min
        return (float(d[0] / 20), float(d[2] / 20), float(d[1] / 8))

    def socket_phase(self) -> tuple[float, float]:
        """x and z (mod 20) of the centres of this part's stud cells in its own frame: from
        its body's bounding box when its sides are whole studs (a jumper plate's one stud is
        between two cells), else from its top studs, else from the box anyway."""
        span = self.bbox_max - self.bbox_min
        whole = all(abs(v / 20 - round(v / 20)) < 0.05 and v > 1 for v in (span[0], span[2]))
        top = self.top_studs()
        if top and not whole:
            px, pz = float(top[0].pos[0] % 20), float(top[0].pos[2] % 20)
        else:
            px = float((self.bbox_min[0] + 10) % 20)
            pz = float((self.bbox_min[2] + 10) % 20)
        return (round(px * 2) / 2 % 20, round(pz * 2) / 2 % 20)

    def has_sockets(self) -> bool:
        """True when a stud can go in anywhere underneath (see ``place.sockets``)."""
        if self._n_sockets is None:
            from bricksnap.lab.place import sockets

            self._n_sockets = len(sockets(self))
        return self._n_sockets > 0

    # ---- filled body ----

    def has_body(self) -> bool:
        return self.top is not None and bool(np.isfinite(self.top).any())

    def column_index(
        self, x: np.ndarray, z: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        i = np.floor(x / GRID).astype(np.int64) - self.col_origin[0]
        j = np.floor(z / GRID).astype(np.int64) - self.col_origin[1]
        assert self.top is not None
        ok = (i >= 0) & (j >= 0) & (i < self.top.shape[0]) & (j < self.top.shape[1])
        return np.where(ok, i, 0), np.where(ok, j, 0), ok

    def inside(self, pts: np.ndarray, tol: float = 0.5) -> np.ndarray:
        """Which points (n, 3), in this part's frame, are inside its filled body."""
        pts = np.asarray(pts, dtype=float).reshape(-1, 3)
        if self.top is None or self.bottom is None or not len(pts):
            return np.zeros(len(pts), dtype=bool)
        i, j, ok = self.column_index(pts[:, 0], pts[:, 2])
        t = self.top[i, j]
        b = self.bottom[i, j]
        y = pts[:, 1]
        with np.errstate(invalid="ignore"):
            return ok & (t + tol < y) & (y < b - tol)

    def bottom_at(self, x: float, z: float) -> float | None:
        """The filled body's bottom in the column at (x, z), or None outside the body."""
        if self.bottom is None:
            return None
        i, j, ok = self.column_index(np.array([x]), np.array([z]))
        if not ok[0]:
            return None
        b = float(self.bottom[i[0], j[0]])
        return None if math.isnan(b) else b

    def hollow_above(self, x: float, z: float, y: float, depth: float = 2.5) -> bool:
        """True when the column at (x, z) has no surface between y - depth and y: there is
        room for a stud whose base is at y (a socket), not a solid underside."""
        if self.raw_bottom is None:
            return False
        i, j, ok = self.column_index(np.array([x]), np.array([z]))
        if not ok[0]:
            return True
        rb = float(self.raw_bottom[i[0], j[0]])
        return math.isnan(rb) or rb <= y - depth

    def is_socket(self, x: float, z: float, y: float) -> bool:
        """True when a stud with its base at (x, y, z), pointing up, goes into a socket here:
        there is a hollow above its base, and the underside around it is flat (the filled
        bottom 9 LDU away is level with y, or a wall going at least 6 LDU deeper, wherever the
        body reaches, in at least two directions, one of them level), as under a brick, plate or
        tile; a curved inside (a tyre) or a ledge is not a socket."""
        if not self.hollow_above(x, z, y):
            return False
        level = walls = 0
        for dx, dz in ((9, 0), (-9, 0), (0, 9), (0, -9)):
            b = self.bottom_at(x + dx, z + dz)
            if b is None:
                continue  # past a round or tapered edge
            if abs(b - y) <= 1.5:
                level += 1
            elif b - y >= 6:
                walls += 1  # a wall going down beside it (a bracket's other plate)
            else:
                return False
        return level >= 1 and level + walls >= 2

    def samples(self) -> tuple[np.ndarray, np.ndarray]:
        """Points filling the body on a 4 LDU grid (n, 3) and the volume each stands for."""
        if self._samples is not None:
            return self._samples
        if self.top is None or self.bottom is None:
            self._samples = (np.zeros((0, 3)), np.zeros(0))
            return self._samples
        i0, j0 = self.col_origin
        ii, jj = np.nonzero(np.isfinite(self.top) & np.isfinite(self.bottom))
        keep = ((ii + i0) % 2 == 0) & ((jj + j0) % 2 == 0)
        if not keep.any():  # a part narrower than 4 LDU: use every column
            keep = np.ones(len(ii), dtype=bool)
            area = GRID * GRID
        else:
            area = 4 * GRID * GRID
        ii, jj = ii[keep], jj[keep]
        t = self.top[ii, jj].astype(float)
        b = self.bottom[ii, jj].astype(float)
        h = np.maximum(b - t, 0.0)
        n = np.maximum(1, np.ceil((h - 2) / 4)).astype(np.int64)
        rep = np.repeat(np.arange(len(ii)), n)
        k = np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n)
        y = t[rep] + (k + 0.5) * h[rep] / n[rep]
        x = (ii[rep] + i0) * GRID + GRID / 2
        z = (jj[rep] + j0) * GRID + GRID / 2
        w = area * h[rep] / n[rep]
        self._samples = (np.stack([x, y, z], axis=1), w)
        return self._samples

    def volume(self) -> float:
        return float(self.samples()[1].sum())

    def joins_otherwise(self) -> bool:
        """True when the part has connectors other than studs and tubes, by its geometry or
        its name (bars, for one, are only known by name)."""
        return bool(self.others) or bool(OTHER_JOINT_WORDS.search(self.description))

    def name_joint_words(self) -> list[str]:
        """Joints the part's name names that its geometry does not show (a bar, a tyre)."""
        return sorted({k.lower() for k in NAME_JOINT_WORDS.findall(self.description)})

    def other_joint_words(self) -> list[str]:
        words = {k.lower() for k in OTHER_JOINT_WORDS.findall(self.description)}
        words |= {c.kind for c in self.others}
        return sorted(words)


def _deepen_with_walls(
    tris: np.ndarray, top: np.ndarray, bot: np.ndarray, I0: int, J0: int
) -> None:
    """Walls (near-vertical faces) cross few column centres, so a thin wall can be missed:
    sample them about every LDU and let each sample deepen the bottom of the column it falls
    in (only columns the body already covers)."""
    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    normal = np.cross(e1, e2)
    length = np.linalg.norm(normal, axis=1)
    vertical = (length > 1e-9) & (np.abs(normal[:, 1]) < 0.1 * np.maximum(length, 1e-12))
    W, D = top.shape
    for tri in tris[vertical]:
        edge = max(
            float(np.linalg.norm(tri[1] - tri[0])),
            float(np.linalg.norm(tri[2] - tri[0])),
            float(np.linalg.norm(tri[2] - tri[1])),
        )
        n = int(min(max(math.ceil(edge), 1), 200))
        a, b = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        ok = a + b <= n
        u, v = a[ok] / n, b[ok] / n
        pts = tri[0] + u[:, None] * (tri[1] - tri[0]) + v[:, None] * (tri[2] - tri[0])
        i = np.floor(pts[:, 0] / GRID).astype(np.int64) - I0
        j = np.floor(pts[:, 2] / GRID).astype(np.int64) - J0
        inb = (i >= 0) & (j >= 0) & (i < W) & (j < D)
        i, j, y = i[inb], j[inb], pts[inb, 1]
        has = np.isfinite(top[i, j])
        np.maximum.at(bot, (i[has], j[has]), y[has])


def _columns(
    tris: np.ndarray,
) -> tuple[tuple[int, int], np.ndarray, np.ndarray, np.ndarray] | None:
    """The top and filled bottom of the body in each 2 LDU column (see the contract)."""
    if not len(tris):
        return None
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    det = (b[:, 2] - c[:, 2]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 2] - c[:, 2])
    keep = np.abs(det) > 1e-6
    if not keep.any():
        return None
    tris_all = tris
    tris, det = tris[keep], det[keep]
    xs, zs = tris[:, :, 0], tris[:, :, 2]
    i_lo = np.ceil((xs.min(1) - GRID / 2) / GRID).astype(np.int64)
    i_hi = np.floor((xs.max(1) - GRID / 2) / GRID).astype(np.int64)
    j_lo = np.ceil((zs.min(1) - GRID / 2) / GRID).astype(np.int64)
    j_hi = np.floor((zs.max(1) - GRID / 2) / GRID).astype(np.int64)
    nx = np.maximum(i_hi - i_lo + 1, 0)
    nz = np.maximum(j_hi - j_lo + 1, 0)
    cnt = nx * nz
    has = cnt > 0
    if not has.any():
        return None
    I0, J0 = int(i_lo[has].min()), int(j_lo[has].min())
    W, D = int(i_hi[has].max()) - I0 + 1, int(j_hi[has].max()) - J0 + 1
    top = np.full((W, D), np.inf)
    bot = np.full((W, D), -np.inf)
    order = np.nonzero(has)[0]
    start = 0
    while start < len(order):  # in chunks of about two million candidate columns
        csum = np.cumsum(cnt[order[start:]])
        stop = start + max(1, int(np.searchsorted(csum, 2_000_000)))
        idx = order[start:stop]
        start = stop
        n = cnt[idx]
        rep = np.repeat(np.arange(len(idx)), n)
        off = np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n)
        ti = idx[rep]
        nzr = nz[ti]
        i = i_lo[ti] + off // nzr
        j = j_lo[ti] + off % nzr
        px = i * GRID + GRID / 2
        pz = j * GRID + GRID / 2
        A, B, C = tris[ti, 0], tris[ti, 1], tris[ti, 2]
        d = det[ti]
        l1 = ((B[:, 2] - C[:, 2]) * (px - C[:, 0]) + (C[:, 0] - B[:, 0]) * (pz - C[:, 2])) / d
        l2 = ((C[:, 2] - A[:, 2]) * (px - C[:, 0]) + (A[:, 0] - C[:, 0]) * (pz - C[:, 2])) / d
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        y = l1 * A[:, 1] + l2 * B[:, 1] + l3 * C[:, 1]
        gi, gj = i[inside] - I0, j[inside] - J0
        np.minimum.at(top, (gi, gj), y[inside])
        np.maximum.at(bot, (gi, gj), y[inside])
    exists = np.isfinite(top)
    _deepen_with_walls(tris_all, top, bot, I0, J0)
    # enclosure: the deepest bottom met in each of the four directions, the lowest of those
    # thin or curved rims fall between column centres unevenly: let each column count as
    # wall as deep as its deepest neighbour (3 x 3), for the enclosure only
    from scipy.ndimage import maximum_filter

    b = maximum_filter(np.where(exists, bot, -np.inf), size=3, mode="constant", cval=-np.inf)
    left = np.maximum.accumulate(b, axis=0)
    right = np.maximum.accumulate(b[::-1], axis=0)[::-1]
    front = np.maximum.accumulate(b, axis=1)
    back = np.maximum.accumulate(b[:, ::-1], axis=1)[:, ::-1]
    enclosed = np.minimum(np.minimum(left, right), np.minimum(front, back))
    filled = np.maximum(bot, enclosed)
    top = np.where(exists, top, np.nan).astype(np.float32)
    filled = np.where(exists, filled, np.nan).astype(np.float32)
    raw = np.where(exists, bot, np.nan).astype(np.float32)
    return (I0, J0), top, filled, raw


class Library:
    """The LDraw library zip, read in place."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else zip_path()
        if not self.path.is_file():
            raise FileNotFoundError(
                f"The LDraw parts library was not found at {self.path}. Put the LeoCAD library "
                "zip there or set BRICKSNAP_LDRAW_ZIP."
            )
        self._zip = zipfile.ZipFile(self.path)
        self._lock = threading.RLock()
        self.parts: dict[str, str] = {}  # "3001.dat", "s/3001s01.dat" -> zip entry
        self.prims: dict[str, str] = {}  # "stud.dat", "48/1-4cyli.dat" -> zip entry
        for entry in self._zip.namelist():
            low = entry.lower()
            if not low.endswith(".dat"):
                continue
            if low.startswith("ldraw/parts/"):
                self.parts.setdefault(low[len("ldraw/parts/") :], entry)
            elif low.startswith("ldraw/p/"):
                self.prims.setdefault(low[len("ldraw/p/") :], entry)
        st = self.path.stat()
        self.stamp = f"{st.st_size}-{int(st.st_mtime)}-v{CACHE_VERSION}"
        self._prim_cache: dict[str, _Raw] = {}
        self._sub_cache: OrderedDict[str, _Raw] = OrderedDict()
        self._parts: OrderedDict[str, Part] = OrderedDict()
        self._headers: dict[str, Header] = {}

    # ---- files ----

    def resolve(self, name: str) -> tuple[str, str] | None:
        key = norm_name(name)
        if key in self.parts:
            return ("subpart" if key.startswith("s/") else "part", key)
        if key in self.prims:
            return ("primitive", key)
        return None

    def _entry(self, kind: str, key: str) -> str:
        return self.prims[key] if kind == "primitive" else self.parts[key]

    def text(self, kind: str, key: str) -> str:
        with self._lock:
            data = self._zip.read(self._entry(kind, key))
        return data.decode("utf-8", errors="replace")

    def header(self, name: str) -> Header:
        found = self.resolve(name)
        if found is None:
            raise KeyError(name)
        kind, key = found
        cached = self._headers.get(kind + ":" + key)
        if cached is not None:
            return cached
        h = parse_header(self.text(kind, key))
        self._headers[kind + ":" + key] = h
        return h

    # ---- geometry ----

    def _raw(self, kind: str, key: str, depth: int = 0) -> _Raw:
        if kind == "primitive" and key in self._prim_cache:
            return self._prim_cache[key]
        if kind == "subpart" and key in self._sub_cache:
            self._sub_cache.move_to_end(key)
            return self._sub_cache[key]
        raw = self._expand(self.text(kind, key), depth)
        if kind == "primitive":
            self._prim_cache[key] = raw
        elif kind == "subpart":
            self._sub_cache[key] = raw
            while len(self._sub_cache) > 400:
                self._sub_cache.popitem(last=False)
        return raw

    def _expand(self, text: str, depth: int) -> _Raw:
        tris: list[np.ndarray] = []
        own: list[list[float]] = []
        cons: list[Connector] = []
        missing: set[str] = set()
        if depth > 40:
            return _Raw(np.zeros((0, 3, 3)), [], {"(references nested too deeply)"})
        for line in text.splitlines():
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "3" and len(tok) >= 11:
                with contextlib.suppress(ValueError):
                    own.append([float(v) for v in tok[2:11]])
            elif tok[0] == "4" and len(tok) >= 14:
                try:
                    v = [float(x) for x in tok[2:14]]
                except ValueError:
                    continue
                own.append(v[0:9])
                own.append(v[0:3] + v[6:12])
            elif tok[0] == "1" and len(tok) >= 15:
                try:
                    nums = [float(x) for x in tok[2:14]]
                except ValueError:
                    continue
                ref = " ".join(tok[14:])
                found = self.resolve(ref)
                if found is None:
                    missing.add(norm_name(ref))
                    continue
                t = np.array(nums[0:3])
                m = np.array(nums[3:12]).reshape(3, 3)
                ckind, ckey = found
                base = ckey.rsplit("/", 1)[-1].removesuffix(".dat")
                conn = _classify(base) if ckind == "primitive" else None
                if conn is not None:
                    kind, is_open = conn
                    if kind == "stud":
                        local = Connector(kind, base, np.zeros(3), np.array([0.0, -1.0, 0.0]))
                    elif kind == "tube":
                        local = Connector(
                            kind,
                            base,
                            np.zeros(3),
                            np.array([0.0, -1.0, 0.0]),
                            np.array([0.0, -4.0, 0.0]),
                            is_open,
                        )
                    else:
                        local = Connector(kind, base, np.zeros(3), np.array([0.0, 1.0, 0.0]))
                    cons.append(local.transformed(m, t))
                    if kind == "stud":
                        # a male stud is not part of the body, but the surface under it is:
                        # parts leave it open because the stud covers it
                        tris.append(_STUD_BASE @ m.T + t)
                        continue
                child = self._raw(ckind, ckey, depth + 1)
                missing |= child.missing
                if len(child.tris):
                    tris.append(child.tris @ m.T + t)
                if conn is None:
                    cons.extend(c.transformed(m, t) for c in child.cons)
        if own:
            tris.append(np.array(own, dtype=float).reshape(-1, 3, 3))
        all_tris = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
        return _Raw(all_tris, cons, missing)

    def triangles(self, name: str) -> np.ndarray:
        """The body's triangles (n, 3, 3) in the part's frame (male studs left out)."""
        found = self.resolve(name)
        if found is None:
            raise KeyError(name)
        return (
            self._raw(*found).tris
            if found[0] != "part"
            else self._expand(self.text(*found), 0).tris
        )

    def part(self, name: str, columns: bool = True) -> Part:
        """The part, resolved (see the contract). Raises KeyError for an unknown name."""
        found = self.resolve(name)
        if found is None:
            raise KeyError(name)
        kind, key = found
        cache_key = key + ("" if columns else "#nocols")
        with self._lock:
            if cache_key in self._parts:
                self._parts.move_to_end(cache_key)
                return self._parts[cache_key]
            if columns and key in self._parts and self._parts[key].top is not None:
                return self._parts[key]
        part = self._load_cached(key) if columns else None
        if part is None:
            part = self._build(kind, key, columns)
            if columns:
                self._save_cached(key, part)
        with self._lock:
            self._parts[cache_key] = part
            while len(self._parts) > 300:
                self._parts.popitem(last=False)
        return part

    def _build(self, kind: str, key: str, columns: bool) -> Part:
        text = self.text(kind, key)
        header = parse_header(text)
        raw = self._expand(text, 0)
        cons = _dedupe(raw.cons)
        if len(raw.tris):
            pts = raw.tris.reshape(-1, 3)
            lo, hi = pts.min(0), pts.max(0)
        elif cons:
            pts = np.array([c.pos for c in cons])
            lo, hi = pts.min(0), pts.max(0)
        else:
            lo = hi = np.zeros(3)
        part = Part(
            name=key,
            header=header,
            tri_count=len(raw.tris),
            bbox_min=lo,
            bbox_max=hi,
            connectors=cons,
            missing=sorted(raw.missing),
        )
        if columns:
            cols = _columns(raw.tris)
            if cols is not None:
                part.col_origin, part.top, part.bottom, part.raw_bottom = cols
        return part

    def _cache_file(self, key: str) -> Path:
        safe = re.sub(r"[^a-z0-9._-]", "_", key)
        return cache_dir() / "parts" / f"{safe}.pkl"

    def _load_cached(self, key: str) -> Part | None:
        path = self._cache_file(key)
        try:
            with path.open("rb") as f:
                data: dict[str, Any] = pickle.load(f)
        except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError):
            return None
        if data.get("stamp") != self.stamp:
            return None
        part = data.get("part")
        return part if isinstance(part, Part) else None

    def _save_cached(self, key: str, part: Part) -> None:
        path = self._cache_file(key)
        with contextlib.suppress(OSError):
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            part._samples = None
            with tmp.open("wb") as f:
                pickle.dump(
                    {"stamp": self.stamp, "part": part}, f, protocol=pickle.HIGHEST_PROTOCOL
                )
            os.replace(tmp, path)

    def colours(self) -> dict[int, str]:
        """LDraw colour code -> name, from LDConfig.ldr."""
        out: dict[int, str] = {}
        try:
            with self._lock:
                text = self._zip.read("ldraw/LDConfig.ldr").decode("utf-8", errors="replace")
        except KeyError:
            return out
        for line in text.splitlines():
            m = re.match(r"\s*0\s+!COLOUR\s+(\S+)\s+CODE\s+(\d+)", line)
            if m:
                out[int(m.group(2))] = m.group(1).replace("_", " ")
        return out


def _dedupe(cons: list[Connector]) -> list[Connector]:
    seen: set[tuple[Any, ...]] = set()
    out = []
    for c in cons:
        k = (c.kind, *np.round(c.pos, 1).tolist(), *np.round(c.axis, 2).tolist())
        if c.kind not in ("stud", "tube"):
            k = (c.kind, *np.round(c.pos, 0).tolist())
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


def parse_header(text: str) -> Header:
    h = Header()
    first = True
    for line in text.splitlines()[:60]:
        s = line.strip()
        if not s:
            continue
        if first:
            first = False
            if s.startswith("0"):
                h.description = " ".join(s[1:].split())
            continue
        tok = s.split()
        if tok[0] != "0" or len(tok) < 2:
            if tok[0] in "12345":
                break
            continue
        if tok[1] == "!LDRAW_ORG" and len(tok) >= 3:
            h.org = tok[2]
        elif tok[1] == "!CATEGORY" and len(tok) >= 3:
            h.category = " ".join(tok[2:])
        elif tok[1] == "!KEYWORDS":
            h.keywords.extend(k.strip() for k in " ".join(tok[2:]).split(",") if k.strip())
    if not h.category:
        words = h.description.lstrip("~=_| ").split()
        h.category = words[0] if words else ""
    return h


def fmt(v: float) -> str:
    """A number as an LDraw line writes it: no trailing .0, at most three decimals."""
    r = round(float(v), 3)
    if r == 0:
        return "0"
    return str(int(r)) if r == int(r) else f"{r:.3f}".rstrip("0").rstrip(".")


def origin_note(part: Part) -> str:
    """Where the part's origin is relative to its body's bounding box, in words."""
    lo, hi = part.bbox_min, part.bbox_max
    words = []
    centre = (lo + hi) / 2
    if abs(lo[1]) < 0.5:
        vert = "top"
    elif abs(hi[1]) < 0.5:
        vert = "bottom"
    elif abs(centre[1]) < 0.5:
        vert = "middle (vertically)"
    else:
        vert = None
    on_x = abs(centre[0]) < 0.5
    on_z = abs(centre[2]) < 0.5
    if vert in ("top", "bottom") and on_x and on_z:
        words.append(f"origin at the centre of the {vert} face")
    elif vert == "middle (vertically)" and on_x and on_z:
        words.append("origin at the centre of the part")
    else:
        words.append("origin not at the centre of the top face")
    words.append(
        f"body spans x {fmt(lo[0])}..{fmt(hi[0])}, y {fmt(lo[1])}..{fmt(hi[1])}, "
        f"z {fmt(lo[2])}..{fmt(hi[2])} from it"
    )
    return "; ".join(words)


def direction_word(axis: np.ndarray) -> str:
    """'up', 'down', '-x', '+z'... for a unit vector in a part's frame (y points down)."""
    names = [
        ("+x", 0, 1),
        ("-x", 0, -1),
        ("down", 1, 1),
        ("up", 1, -1),
        ("+z", 2, 1),
        ("-z", 2, -1),
    ]
    best = max(names, key=lambda n: axis[n[1]] * n[2])
    if axis[best[1]] * best[2] > 0.99:
        return best[0]
    return "(" + ", ".join(fmt(a) for a in axis) + ")"


def stud_summary(part: Part) -> str:
    """'8 on top', '1 on top, 1 on the side (-z)', 'none' ..."""
    groups: dict[str, int] = {}
    for s in part.studs:
        d = direction_word(s.axis)
        where = "on top" if d == "up" else ("underneath" if d == "down" else f"on the side ({d})")
        groups[where] = groups.get(where, 0) + 1
    if not groups:
        return "no studs"
    return ", ".join(f"{n} {w}" for w, n in groups.items())


_DEFAULT: Library | None = None
_DEFAULT_LOCK = threading.Lock()


def library() -> Library:
    """One shared Library for this process."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = Library()
        return _DEFAULT
