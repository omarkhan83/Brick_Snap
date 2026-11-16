"""Design to Build: choose real parts so that the model holds together.

CONTRACT (tests go in tests/test_layout.py)

``solve(design, catalog, seed=0) -> Build``

What must be true of the result
- Every filled cell of the Design is covered by exactly one part, and every cell a part
  covers is a filled cell of the part's colour. Empty cells stay empty.
- Only parts of kind "brick" (3 cells tall) and "plate" (1 cell tall) are used, in
  (part, colour) pairs for which ``catalog.exists`` is true. If no part at all exists in a
  cell's colour, use the 1x1 of the right height anyway (the checks will flag it); never
  raise for a Design that is merely awkward.
- The parts form ONE piece connected through studs whenever the Design allows it
  (``bricksnap.connect.connection_graph`` defines "connected"; parts side by side in a layer
  do not hold each other). This is the whole point: the prototype's scan-order merge left
  840 of 920 bricks unattached on a solid 20x20x20 box.
- ``Placement.step`` is set (1-based): bottom layer first, no more than about 8 parts per
  step, parts in a step adjacent to each other where possible, and a step never contains
  parts from two different heights.
- Deterministic for a given ``seed``. ``Build.report`` is left as None (the caller runs the
  checks). This module may use ``bricksnap.connect`` but not ``bricksnap.checks``.

Method (see "Layout" in docs/ARCHITECTURE.md)
1. Courses. Split z into courses of three cells: course k is z = 3k..3k+2. A column cell
   (x, y) is a brick cell in course k when all three of its cells are filled with one
   colour; otherwise each of its filled cells is a plate cell in its own layer.
2. Tile each layer (the brick cells of a course are one layer; each plate level is one
   layer) with rectangles from the catalogue (1x1, 1x2, 1x3, 1x4, 1x6, 1x8, 2x2, 2x3, 2x4,
   2x6, 2x8, either direction), one colour per part. Place the most constrained free cell
   first (fewest free same-colour neighbours), not in scan order. Score each candidate
   rectangle that covers that cell:
     + its area
     + a large bonus for every DIFFERENT part directly below that it sits on (bridging)
     + a bonus for sitting on anything at all rather than hanging over a gap
     - a penalty for each of its edges that lies directly above an edge between two parts
       in the layer below (a seam running up through layers is what makes towers)
     + a small bonus for the layer's preferred direction, which alternates between layers
   Parts in the layer above matter too once they exist, but layers are tiled bottom-up.
3. Repair. Build the connection graph. While more than one piece remains: pick a place
   where two pieces touch, tear up the parts in a small window there (in that layer and the
   one above), and re-tile the window rewarding parts that join different pieces. Give up
   after a bounded number of attempts and leave the remaining loose parts for the checks to
   report; do not loop forever.

Quality bar, enforced by tests
- Zero loose parts on solid and hollow boxes, cylinders and spheres at several sizes
  (tests/test_acceptance.py has the exact list).
- In a solid box no more than a third of the bricks are 1x1 or 1x2.
- Speed: a 34,000-cell solid model in under 20 seconds; a 16-stud model in about a second.

STAGE 3 ADDITION TO THE CONTRACT: sturdiness
(Being built by the lead's agent; until this line is removed, what follows is not in the
code yet.)
A build can be one piece and still fragile: a whole section held by one part, or by one
stud. Once the model is one piece, the solver also makes it sturdy, as far as the Design
allows.

- Words. Give the connection graph a "ground" node joined to every part at z = 0. A *lone
  link* is a part (not on the ground) whose removal would cut other parts off from the
  ground, or a joint between two parts that is a group's only connection and engages a
  single stud. Its *load* is the number of parts it would cut off. This is what
  ``bricksnap.checks`` reports as weak spots; work it out here from ``bricksnap.connect``
  (this module still may not import ``bricksnap.checks``).
- Goal. Lower, in this order of importance: the largest load; the number of lone links
  whose load is 3 or more; the sum of the loads. Never raise the number of pieces, never
  change which cells are covered or their colours, use only bricks and plates in pairs that
  exist. Keep a change only if it improves those three numbers in that order.
- Seams. Where two regions of one colour meet on a vertical plane through several layers (a
  head against a body), parts cross that plane in at least every second layer wherever the
  cells allow a part to cross.
- Bounded and deterministic, like the rest of the solver. Speed: no more than twice the
  time the solver took before on the sample models at 16 studs, and the 34,000-cell solid
  box still well under 20 seconds.
- Tests must include: a head against a body (two boxes of one colour sharing a face six
  studs wide and four bricks tall, the head standing on nothing else): parts cross the
  shared plane in at least half the layers, and no lone link carries more than a quarter of
  the head; a tower on a wide base; a T shape; a hundred random blobs (never more pieces,
  the same cells covered, the largest load never higher than without this step); the
  step still numbers building steps correctly.
- Measured on the scorecard (``uv run bricksnap bench`` against samples/scorecard.json): weak
  spots fall on the cat, the car and the knight, no model gains a loose part, and the part
  count rises by no more than three in a hundred overall.

Implementation notes
--------------------
Connectivity is tracked on *columns*: a column is a maximal vertical run of filled cells at
one (x, y). Bricks and plates always start and end on cell boundaries and have studs and
anti-studs over their whole footprint, so two vertically adjacent filled cells are always
either in the same part or in two parts that hold each other. A column is therefore always
one piece, and a part joins every column it covers. The build is one piece exactly when the
columns, joined by the parts, are one piece. A union-find over columns gives that cheaply
while tiling (a cell not yet tiled still belongs to its column, which is what lets a part
be "held from above" by a layer not yet placed); repair recounts pieces with scipy's
connected components over the columns each part covers.

The best any layout can do is bounded by the pieces of the design itself when vertically
adjacent cells and side-by-side cells of one colour are joined (the "floor"); repair stops
as soon as it reaches it.

Before tiling, brick cells are turned into plates where that is the only way to join two
parts of the design: a group of plate cells that can reach the rest only sideways through
a brick (a one-plate shelf on a wall, the rim of a cone's base) makes the bricks beside it,
and one cell further in, into plates, so one plate can span both.

Tiling scores candidates as the contract describes, plus a dominant bonus for every extra
piece (union-find root) a part joins, and a larger penalty for a part that *seals* a small
piece: after it, none of that piece's cells are left to tile, so no later part can ever
reach it (a part made only of cells with nothing above or below, for instance). The
penalty applies only while the piece is under half of what it could join, so the last part
of a complete model is not penalised. The seam penalty counts only edges with a free cell
of the same colour across them (other edges are there whatever is chosen), and a part is
penalised for each cell beside it that it would leave with no free neighbour (a future
1x1). The anchor order puts "needy" cells first: cells of a small piece whose last cells to
tile are all in this layer, fewest joinable neighbours first.

Repair looks for two side-by-side cells of one colour that belong to different pieces. It
tears up the parts of that layer in a window around them (and, for wider windows, the
layers directly below and above), forces a part across the pair, re-tiles the rest and
keeps the result if the number of pieces went down. If no such single change helps, a
join that leaves the count unchanged (it attached the loose part but cut another one off)
is followed at once by repairs of the parts it cut off, up to ``REPAIR_DEPTH`` changes in a
chain, and the chain is kept only if together they lower the count; otherwise all of it is
undone. If no join works at a brick seam, the window's bricks are turned into three layers
of plates (which can be staggered where one brick course cannot, such as a single-course
wall longer than 8 studs) and tried again. Every change goes through a journal so it can be
undone exactly; attempts, re-tilings and parts placed are bounded, so the solver always
ends, in a few seconds even for a large model with a part that can never join.

A brick layer that comes out with many small parts is tiled again with the other preferred
direction and with the cells taken in the opposite order, and the best tiling is kept, so
odd-sized boxes do not fill up with 1x1s and 1x2s.

Building steps grow from one part through parts beside it. A part that touches no part of
its height joins the nearest step of that height with room, and a part whose neighbours
all have steps already joins one of those steps if it has room.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import chain

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from bricksnap.catalog import Catalog
from bricksnap.types import EMPTY, PLATES_PER_BRICK, Build, Design, Placement

# score weights
W_AREA = 1.0
W_MERGE = 40.0  # per extra separate piece a part joins
W_SEAL = 400.0  # the part closes off a small piece that no later part can reach
W_BELOW = 2.5  # per different part directly below (or above, when it exists)
W_SUPPORT = 2.0  # sits on (or hangs from) something at all
W_SEAM = 1.5  # per unit of the part's outline lying on a seam below / above
W_DIR = 0.6  # long side along the layer's preferred direction
W_TRAP = 3.0  # per same-colour cell beside the part that it would leave with no free neighbour
W_JITTER = 0.05  # seeded noise to break ties differently per seed

MAX_PARTS_PER_STEP = 8
SMALL_SHARE = 0.25  # a brick layer with more small parts than this is tiled both ways
DEMOTE_ROUNDS = 4

REPAIR_WINDOWS = (
    (0, False),
    (1, False),
    (1, True),
    (3, False),
    (3, True),
    (5, True),
)  # (radius, 3 layers)
REPAIR_RADII = (0, 1, 3)  # for turning bricks into plates
REPAIR_FORCED_TRIES = 3
REPAIR_FORCED_TRIES_SMALL = 6  # when the window has at most SMALL_WINDOW cells
SMALL_WINDOW = 16
REPAIR_MAX_ATTEMPTS = 400
REPAIR_RETRIES = 3
REPAIR_TILE_BUDGET = 1500  # re-tilings allowed in repair, plus one per 10 filled cells
REPAIR_PLACE_BUDGET = 10000  # parts placed in repair, plus one per 5 filled cells
LOOKAHEAD_NEUTRAL = 12  # joins that leave the count unchanged followed up, per seam
LOOKAHEAD_MOVES = 8  # follow-up repairs tried after each
REPAIR_DEPTH = 2  # changes that may be chained before the count has to drop

Key = tuple[str, int]  # ("b", z0) for a brick layer, ("p", z) for a plate layer
Cell = tuple[int, int]
Move = tuple[int, Cell, Cell, str]  # (z, a, b, "join" | "demote")


@dataclass(slots=True)
class _Part:
    kind: str  # "brick" | "plate"
    part: str
    rot: int
    color: int
    x: int
    y: int
    z: int
    w: int
    d: int
    h: int
    segs: tuple[int, ...]  # columns this part covers


class _UF:
    """Union-find over columns."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, a: int) -> int:
        parent = self.parent
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(self, a: int, b: int) -> int:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if ra < rb:
            ra, rb = rb, ra
        self.parent[ra] = rb
        return rb

    def copy(self) -> _UF:
        out = _UF(0)
        out.parent = list(self.parent)
        return out

    def roots(self) -> np.ndarray:
        p = np.asarray(self.parent, dtype=np.int64)
        while True:
            q = p[p]
            if np.array_equal(q, p):
                return p
            p = q


@dataclass
class _Layer:
    """Everything the tiler needs about one layer while it fills a region of it."""

    key: Key
    kind: str
    z0: int
    h: int
    col: np.ndarray  # int16 [nx, ny] colour of each cell at z0
    free: np.ndarray  # bool [nx, ny] cells still to cover
    root: np.ndarray  # int64 [nx, ny] piece (union-find root) of each region cell
    rrem: dict[int, int]  # cells not yet covered by any part, per piece of the region
    rsize: dict[int, int]  # cells in all, per piece of the region
    same_x: np.ndarray  # bool [nx-1, ny] cell and its +x neighbour have one colour
    same_y: np.ndarray  # bool [nx, ny-1]
    below: list[list[int]]  # part index under each cell, -1 for none
    above: list[list[int]]  # part index over each cell, -1 for none
    seam_x: np.ndarray  # int [nx-1, ny] count of part edges below/above between x and x+1
    seam_y: np.ndarray  # int [nx, ny-1] the same between y and y+1
    pref: int  # 0: long side along x preferred, 1: along y
    rev: bool  # among equally constrained cells, take the last one in scan order


def _seams(occ2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a, b = occ2[:-1, :], occ2[1:, :]
    sx = (a >= 0) & (b >= 0) & (a != b)
    c, d = occ2[:, :-1], occ2[:, 1:]
    sy = (c >= 0) & (d >= 0) & (c != d)
    return sx, sy


_SIDE = (
    ((slice(None, -1), slice(None), slice(None)), (slice(1, None), slice(None), slice(None))),
    ((slice(None), slice(None, -1), slice(None)), (slice(None), slice(1, None), slice(None))),
)


class _Solver:
    def __init__(self, design: Design, catalog: Catalog, seed: int) -> None:
        self.cat = catalog
        self.colors = np.asarray(design.colors, dtype=np.int16)
        self.nx, self.ny, self.nz = (int(v) for v in self.colors.shape)
        self.filled = self.colors != EMPTY
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed % 2**63)
        nx, ny, nz = self.nx, self.ny, self.nz
        self.ncourse = (nz + PLATES_PER_BRICK - 1) // PLATES_PER_BRICK
        self.brick = np.zeros((nx, ny, self.ncourse), dtype=bool)
        for k in range(self.ncourse):
            z = 3 * k
            if z + 2 < nz:
                c = self.colors[:, :, z]
                self.brick[:, :, k] = (
                    self.filled[:, :, z]
                    & (self.colors[:, :, z + 1] == c)
                    & (self.colors[:, :, z + 2] == c)
                )
        self._columns()
        self.rem = self.seg_len.astype(np.int64)  # cells of each column not covered yet
        self.tiles_done = 0
        self.tile_budget = 0
        self.placed = 0
        self.place_budget = 0
        self.occ = np.full((nx, ny, nz), -1, dtype=np.int32)
        self.parts: list[_Part | None] = []
        self._log: list[tuple] = []  # journal of changes, so they can be undone
        self._shape_cache: dict[tuple[str, int], list[tuple[int, int, str, int]]] = {}
        self._kind_shapes = {k: self._shapes_of_kind(k) for k in ("brick", "plate")}
        spans = [max(w, d) for k in self._kind_shapes.values() for w, d, _, _ in k]
        self.span = max(spans) if spans else 1
        n_ub, ub = self._seg_components(mixed=True)
        self.floor = n_ub  # fewest pieces any layout can have
        ub_cells = np.bincount(ub, weights=self.seg_len, minlength=n_ub) if self.nseg else ub
        self.ub_size = ub_cells[ub].astype(np.int64).tolist()  # per column
        self._demote_slabs()
        self._demote_for_joins()

    # ---- set-up -----------------------------------------------------------------------------

    def _columns(self) -> None:
        f = self.filled
        starts = f.copy()
        starts[:, :, 1:] &= ~f[:, :, :-1]
        seg = np.full(f.shape, -1, dtype=np.int32)
        n = int(starts.sum())
        seg[starts] = np.arange(n, dtype=np.int32)
        for z in range(1, self.nz):
            cont = f[:, :, z] & ~starts[:, :, z]
            seg[:, :, z] = np.where(cont, seg[:, :, z - 1], seg[:, :, z])
        self.seg = seg
        self.nseg = n
        self.seg_len = np.bincount(seg[f], minlength=n) if n else np.zeros(0, dtype=np.int64)

    def _brick_cells(self) -> np.ndarray:
        """bool [nx, ny, nz]: the cell is part of a brick cell of its course."""
        return np.repeat(self.brick, PLATES_PER_BRICK, axis=2)[:, :, : self.nz]

    def _seg_components(self, mixed: bool) -> tuple[int, np.ndarray]:
        """Pieces of columns joined by side-by-side cells of one colour.

        With ``mixed`` False, a brick cell and a plate cell beside it are not joined (no
        part can cover both as long as the brick stays a brick).
        """
        if self.nseg == 0:
            return 0, np.zeros(0, dtype=np.int64)
        f, c, seg = self.filled, self.colors, self.seg
        br = self._brick_cells()
        rows, cols = [], []
        for lo, hi in _SIDE:
            m = f[lo] & f[hi] & (c[lo] == c[hi])
            if not mixed:
                m &= br[lo] == br[hi]
            rows.append(seg[lo][m])
            cols.append(seg[hi][m])
        r, q = np.concatenate(rows), np.concatenate(cols)
        g = coo_matrix((np.ones(len(r)), (r, q)), shape=(self.nseg, self.nseg))
        n, labels = connected_components(g, directed=False)
        return int(n), labels.astype(np.int64)

    def _demote_slabs(self) -> None:
        """Turn one-course-thick slabs of bricks into plates before tiling.

        A brick whose column is exactly its own course (nothing directly above or below)
        is held only by the part it is in. A floor or ceiling one brick thick, or a model one
        brick tall, therefore falls apart as bricks, but three staggered layers of plates
        hold it together. A same-colour patch of brick cells in a course is turned into
        plates when it has such a cell that is not next to a cell whose column does go on
        up or down, unless the whole patch is one part.
        """
        for k in range(self.ncourse):
            z = 3 * k
            if z + 2 >= self.nz:
                continue
            bricks = self.brick[:, :, k]
            if not bricks.any():
                continue
            no = np.zeros_like(bricks)
            below = self.filled[:, :, z - 1] if z > 0 else no
            above = self.filled[:, :, z + 3] if z + 3 < self.nz else no
            ext = bricks & (below | above)
            confined = bricks & ~ext
            if not confined.any():
                continue
            col = self.colors[:, :, z]
            demote = np.zeros_like(bricks)
            for c in np.unique(col[confined]).tolist():
                labels, n = ndimage.label(bricks & (col == c))
                for i in range(1, n + 1):
                    patch = labels == i
                    if not (patch & confined).any():
                        continue
                    pext = patch & ext
                    if pext.any():
                        near = pext | (ndimage.binary_dilation(pext) & patch)
                        if not (patch & confined & ~near).any():
                            continue
                    elif self._one_part(patch, c):
                        continue
                    demote |= patch
            self.brick[:, :, k] &= ~demote

    def _demote_for_joins(self) -> None:
        """Turn bricks into plates where a plate must reach sideways into them.

        Columns are grouped into the pieces they could form while every brick stays a brick.
        Where that gives more pieces than the design allows, every group but the largest of
        its kind is beside a brick that some plate has to share: that brick, and the brick
        one further in (so a long plate can reach across a deep shelf), become plates.
        """
        f, c, seg = self.filled, self.colors, self.seg
        for _ in range(DEMOTE_ROUNDS):
            n, g = self._seg_components(mixed=False)
            if n <= self.floor:
                return
            size = np.bincount(g, weights=self.seg_len, minlength=n)
            ub_of = np.zeros(n, dtype=np.int64)
            _, ub = self._seg_components(mixed=True)
            ub_of[g] = ub
            keep = np.zeros(n, dtype=bool)
            best: dict[int, int] = {}
            for i in np.argsort(-size, kind="stable").tolist():
                best.setdefault(int(ub_of[i]), i)
            keep[list(best.values())] = True
            br = self._brick_cells()
            gc = np.where(f, g[np.maximum(seg, 0)], -1)
            demote = np.zeros(self.brick.shape, dtype=bool)
            for axis, (lo, hi) in enumerate(_SIDE):
                m = f[lo] & f[hi] & (c[lo] == c[hi]) & (br[lo] != br[hi])
                m &= ~keep[np.maximum(gc[lo], 0)] | ~keep[np.maximum(gc[hi], 0)]
                xs, ys, zs = np.nonzero(m)
                lo_is_brick = br[lo][m]
                bx = np.where(lo_is_brick, xs, xs + (axis == 0))
                by = np.where(lo_is_brick, ys, ys + (axis == 1))
                demote[bx, by, zs // 3] = True
            if not demote.any():
                return
            for k in range(self.ncourse):
                d = demote[:, :, k]
                if not d.any():
                    continue
                col = self.colors[:, :, 3 * k]
                bk = self.brick[:, :, k]
                for colour in np.unique(col[d]).tolist():
                    dd = d & (col == colour)
                    d |= ndimage.binary_dilation(dd) & bk & (col == colour)
            self.brick &= ~demote

    def _one_part(self, patch: np.ndarray, colour: int) -> bool:
        xs, ys = np.nonzero(patch)
        w, d = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        if w * d != int(patch.sum()):
            return False
        return any((sw, sd) == (w, d) for sw, sd, _, _ in self.shapes("brick", colour))

    def _shapes_of_kind(self, kind: str) -> list[tuple[int, int, str, int]]:
        out: list[tuple[int, int, str, int]] = []
        for p in self.cat.of_kind(kind):
            if len(p.studs_top) != p.sx * p.sz or not p.antistuds_bottom:
                continue
            out.append((p.sx, p.sz, p.id, 0))
            if p.sx != p.sz:
                out.append((p.sz, p.sx, p.id, 90))
        out.sort(key=lambda t: (-t[0] * t[1], -t[0], t[2]))
        return out

    def shapes(self, kind: str, colour: int) -> list[tuple[int, int, str, int]]:
        """(w, d, part, rot) for every footprint that really exists in this colour."""
        key = (kind, colour)
        got = self._shape_cache.get(key)
        if got is None:
            got, seen = [], set()
            for w, d, pid, rot in self._kind_shapes[kind]:
                if (w, d) in seen or not self.cat.exists(pid, colour):
                    continue
                seen.add((w, d))
                got.append((w, d, pid, rot))
            if (1, 1) not in seen:  # no real 1x1 in this colour: use one anyway, checks flag it
                ones = [t for t in self._kind_shapes[kind] if t[0] == 1 and t[1] == 1]
                if ones:
                    got.append(ones[0])
            self._shape_cache[key] = got
        return got

    # ---- layers -----------------------------------------------------------------------------

    @staticmethod
    def layer_h(key: Key) -> int:
        return PLATES_PER_BRICK if key[0] == "b" else 1

    def layer_mask(self, key: Key) -> np.ndarray:
        kind, z0 = key
        if kind == "b":
            return self.brick[:, :, z0 // 3]
        return self.filled[:, :, z0] & ~self.brick[:, :, z0 // 3]

    def course_keys(self, k: int) -> list[Key]:
        z = 3 * k
        keys: list[Key] = [("p", z), ("b", z)]
        keys += [("p", zz) for zz in (z + 1, z + 2) if zz < self.nz]
        return keys

    def all_keys(self) -> list[Key]:
        return [key for k in range(self.ncourse) for key in self.course_keys(k)]

    def neighbour_keys(self, key: Key) -> list[Key]:
        """The layers holding the cells directly below and directly above ``key``."""
        out: list[Key] = []
        for z in (key[1] - 1, key[1] + self.layer_h(key)):
            if 0 <= z < self.nz:
                for k in (("p", z), ("b", z - z % 3)):
                    if k != key and k not in out:
                        out.append(k)
        return out

    # ---- journal ----------------------------------------------------------------------------

    def _add(self, p: _Part) -> int:
        idx = len(self.parts)
        self.parts.append(p)
        self.occ[p.x : p.x + p.w, p.y : p.y + p.d, p.z : p.z + p.h] = idx
        self.rem[list(p.segs)] -= p.h
        self._log.append(("add", idx))
        return idx

    def _remove(self, idxs: list[int]) -> list[_Part]:
        saved = []
        for i in idxs:
            p = self.parts[i]
            assert p is not None
            saved.append(p)
            self.occ[p.x : p.x + p.w, p.y : p.y + p.d, p.z : p.z + p.h] = -1
            self.rem[list(p.segs)] += p.h
            self.parts[i] = None
            self._log.append(("rm", i, p))
        return saved

    def _set_brick(self, k: int, new: np.ndarray) -> None:
        self._log.append(("brick", k, self.brick[:, :, k].copy()))
        self.brick[:, :, k] = new

    def _rollback(self, mark: int) -> None:
        """Undo every change made since the journal had ``mark`` entries."""
        log = self._log
        while len(log) > mark:
            e = log.pop()
            if e[0] == "add":
                p = self.parts.pop()
                assert p is not None and e[1] == len(self.parts)
                self.occ[p.x : p.x + p.w, p.y : p.y + p.d, p.z : p.z + p.h] = -1
                self.rem[list(p.segs)] += p.h
            elif e[0] == "rm":
                _, i, p = e
                self.parts[i] = p
                self.occ[p.x : p.x + p.w, p.y : p.y + p.d, p.z : p.z + p.h] = i
                self.rem[list(p.segs)] -= p.h
            else:
                self.brick[:, :, e[1]] = e[2]

    # ---- union-find -------------------------------------------------------------------------

    def _components(self) -> tuple[int, np.ndarray]:
        """(pieces, piece of every column) for the parts placed now.

        A piece is named by its lowest column index, as :class:`_UF` would name it.
        """
        multi = [p.segs for p in self.parts if p is not None and len(p.segs) > 1]
        if multi:
            lens = np.fromiter(map(len, multi), dtype=np.int64, count=len(multi))
            flat = np.fromiter(chain.from_iterable(multi), dtype=np.int64, count=int(lens.sum()))
            first = np.repeat(flat[np.cumsum(lens) - lens], lens)
        else:
            flat = first = np.zeros(0, dtype=np.int64)
        graph = coo_matrix(
            (np.ones(len(flat), dtype=np.int32), (first, flat)), shape=(self.nseg, self.nseg)
        )
        n, labels = connected_components(graph, directed=False)
        lowest = np.unique(labels, return_index=True)[1]
        return int(n), lowest[labels].astype(np.int64)

    def build_uf(self) -> _UF:
        uf = _UF(0)
        uf.parent = self._components()[1].tolist() if self.nseg else []
        return uf

    def piece_count(self, uf: _UF | None = None) -> int:
        if self.nseg == 0:
            return 0
        if uf is None:
            return self._components()[0]
        return int(np.unique(uf.roots()).size)

    # ---- tiling -----------------------------------------------------------------------------

    def _context(
        self, key: Key, region: np.ndarray, uf: _UF, pref: int | None, rev: bool = False
    ) -> _Layer:
        kind, z0 = key
        h = self.layer_h(key)
        col = self.colors[:, :, z0]
        root = np.full((self.nx, self.ny), -1, dtype=np.int64)
        rrem: dict[int, int] = {}
        rsize: dict[int, int] = {}
        if region.any():
            roots_all = uf.roots()
            segs = self.seg[:, :, z0][region]
            rts = roots_all[segs]
            root[region] = rts
            uniq = np.unique(rts)
            rem = np.bincount(roots_all, weights=self.rem, minlength=self.nseg)[uniq]
            size = np.bincount(roots_all, weights=self.seg_len, minlength=self.nseg)[uniq]
            for r, a, b in zip(uniq.tolist(), rem.tolist(), size.tolist(), strict=True):
                rrem[r] = int(a)
                rsize[r] = int(b)
        below = self.occ[:, :, z0 - 1] if z0 > 0 else np.full((self.nx, self.ny), -1, np.int32)
        top = z0 + h
        above = self.occ[:, :, top] if top < self.nz else np.full((self.nx, self.ny), -1, np.int32)
        bx, by = _seams(below)
        ax, ay = _seams(above)
        seam_x = bx.astype(np.int64) + ax
        seam_y = by.astype(np.int64) + ay
        layer_index = z0 // 3 if kind == "b" else z0
        return _Layer(
            key=key,
            kind="brick" if kind == "b" else "plate",
            z0=z0,
            h=h,
            col=col,
            free=region.copy(),
            root=root,
            rrem=rrem,
            rsize=rsize,
            same_x=col[:-1, :] == col[1:, :],
            same_y=col[:, :-1] == col[:, 1:],
            below=below.tolist(),
            above=above.tolist(),
            seam_x=seam_x,
            seam_y=seam_y,
            pref=(layer_index + self.seed) % 2 if pref is None else pref,
            rev=rev,
        )

    @staticmethod
    def _free_nbrs(L: _Layer) -> np.ndarray:
        """Free same-colour neighbours of every cell of the layer."""
        f = L.free
        n = np.zeros(f.shape, dtype=np.int16)
        n[1:, :] += f[:-1, :] & L.same_x
        n[:-1, :] += f[1:, :] & L.same_x
        n[:, 1:] += f[:, :-1] & L.same_y
        n[:, :-1] += f[:, 1:] & L.same_y
        return n

    def _anchor(self, L: _Layer, n: np.ndarray) -> tuple[int, int]:
        """The free cell to cover next: the most constrained one.

        Cells of a small piece whose last cells to tile are all in this layer come first
        ("needy" cells): a part placed now is their last chance to join anything, so they
        must not be boxed in by parts chosen for easier cells. Among them, the ones with the
        fewest free neighbours that are not needy (the cells that could join them) go first.
        """
        key = np.where(L.free, n, 99)
        roots, counts = np.unique(L.root[L.free], return_counts=True)
        needy = [
            r
            for r, c in zip(roots.tolist(), counts.tolist(), strict=True)
            if L.rrem[r] == c * L.h and 2 * L.rsize[r] < self.ub_size[r]
        ]
        if needy:
            nm = np.isin(L.root, needy) & L.free
            live = L.free & ~nm
            ln = np.zeros(live.shape, dtype=np.int16)
            ln[1:, :] += live[:-1, :] & L.same_x
            ln[:-1, :] += live[1:, :] & L.same_x
            ln[:, 1:] += live[:, :-1] & L.same_y
            ln[:, :-1] += live[:, 1:] & L.same_y
            key = np.where(nm, ln * 5 + n, key + 25)
        key = key.ravel()
        flat = key.size - 1 - int(np.argmin(key[::-1])) if L.rev else int(np.argmin(key))
        return flat // self.ny, flat % self.ny

    def _candidates(
        self,
        L: _Layer,
        n: np.ndarray,
        ax: int,
        ay: int,
        must: tuple[int, int] | None = None,
    ) -> list[tuple[float, int, int, int, int, str, int]]:
        """Every rectangle covering (ax, ay) that fits, with its score, best first.

        ``n`` is :meth:`_free_nbrs` of the layer as it is now.
        """
        nx, ny, span = self.nx, self.ny, self.span
        c = int(L.col[ax, ay])
        x_lo, x_hi = max(0, ax - span + 1), min(nx, ax + span)
        y_lo, y_hi = max(0, ay - span + 1), min(ny, ay + span)
        ok = L.free[x_lo:x_hi, y_lo:y_hi] & (L.col[x_lo:x_hi, y_lo:y_hi] == c)
        sat = np.zeros((ok.shape[0] + 1, ok.shape[1] + 1), dtype=np.int32)
        sat[1:, 1:] = ok.cumsum(0).cumsum(1)
        S = sat.tolist()
        # cells beside a candidate whose only free neighbour it takes are left as 1x1s
        ex0, ex1 = max(0, x_lo - 1), min(nx, x_hi + 1)
        ey0, ey1 = max(0, y_lo - 1), min(ny, y_hi + 1)
        win = (slice(ex0, ex1), slice(ey0, ey1))
        trap = (L.free[win] & (L.col[win] == c) & (n[win] == 1)).astype(np.int32)
        tyc = np.zeros((trap.shape[0], trap.shape[1] + 1), dtype=np.int32)
        tyc[:, 1:] = trap.cumsum(1)
        txc = np.zeros((trap.shape[0] + 1, trap.shape[1]), dtype=np.int32)
        txc[1:, :] = trap.cumsum(0)
        TY, TX = tyc.tolist(), txc.tolist()
        # seams below/above that an edge of the candidate would continue; only edges with a
        # free same-colour cell across count, since the others are there whatever is chosen
        fc = L.free[win] & (L.col[win] == c)
        sx = L.seam_x[ex0 : ex1 - 1, ey0:ey1] * (fc[:-1, :] & fc[1:, :])
        sy = L.seam_y[ex0:ex1, ey0 : ey1 - 1] * (fc[:, :-1] & fc[:, 1:])
        syc = np.zeros((sx.shape[0], sx.shape[1] + 1), dtype=np.int64)
        syc[:, 1:] = sx.cumsum(1)
        sxc = np.zeros((sy.shape[0] + 1, sy.shape[1]), dtype=np.int64)
        sxc[1:, :] = sy.cumsum(0)
        SY, SX = syc.tolist(), sxc.tolist()
        roots = L.root[x_lo:x_hi, y_lo:y_hi].tolist()
        below, above = L.below, L.above
        rrem, rsize, ub_size, h = L.rrem, L.rsize, self.ub_size, L.h
        shapes = self.shapes(L.kind, c)
        jitter = self.rng.random(len(shapes) * span * span).tolist() if W_JITTER else None
        out: list[tuple[float, int, int, int, int, str, int]] = []
        ji = 0
        for w, d, pid, rot in shapes:
            area = w * d
            long_dir = 0 if w > d else (1 if d > w else -1)
            dir_bonus = W_DIR if long_dir == L.pref else 0.0
            for ox in range(w):
                x0 = ax - ox
                x1 = x0 + w
                if x0 < x_lo or x1 > x_hi:
                    continue
                lx0, lx1 = x0 - x_lo, x1 - x_lo
                for oy in range(d):
                    y0 = ay - oy
                    y1 = y0 + d
                    if y0 < y_lo or y1 > y_hi:
                        continue
                    ly0, ly1 = y0 - y_lo, y1 - y_lo
                    if S[lx1][ly1] - S[lx0][ly1] - S[lx1][ly0] + S[lx0][ly0] != area:
                        continue
                    if must is not None and not (x0 <= must[0] < x1 and y0 <= must[1] < y1):
                        continue
                    rs: set[int] = set()
                    bs: set[int] = set()
                    us: set[int] = set()
                    for i in range(lx0, lx1):
                        rs.update(roots[i][ly0:ly1])
                        bs.update(below[x_lo + i][y0:y1])
                        us.update(above[x_lo + i][y0:y1])
                    bs.discard(-1)
                    us.discard(-1)
                    seam = 0
                    if x0 > ex0:
                        row = SY[x0 - 1 - ex0]
                        seam += row[y1 - ey0] - row[y0 - ey0]
                    if x1 < ex1:
                        row = SY[x1 - 1 - ex0]
                        seam += row[y1 - ey0] - row[y0 - ey0]
                    if y0 > ey0:
                        j = y0 - 1 - ey0
                        seam += SX[x1 - ex0][j] - SX[x0 - ex0][j]
                    if y1 < ey1:
                        j = y1 - 1 - ey0
                        seam += SX[x1 - ex0][j] - SX[x0 - ex0][j]
                    trapped = 0
                    if x0 > 0:
                        row = TY[x0 - 1 - ex0]
                        trapped += row[y1 - ey0] - row[y0 - ey0]
                    if x1 < nx:
                        row = TY[x1 - ex0]
                        trapped += row[y1 - ey0] - row[y0 - ey0]
                    if y0 > 0:
                        j = y0 - 1 - ey0
                        trapped += TX[x1 - ex0][j] - TX[x0 - ex0][j]
                    if y1 < ny:
                        j = y1 - ey0
                        trapped += TX[x1 - ex0][j] - TX[x0 - ex0][j]
                    left = -area * h
                    size = 0
                    for r in rs:
                        left += rrem[r]
                        size += rsize[r]
                    if left <= 0 and 2 * size < ub_size[r]:  # seals off a small piece
                        join = -W_SEAL
                    else:
                        join = W_MERGE * (len(rs) - 1)
                    score = (
                        W_AREA * area
                        + join
                        + W_BELOW * (len(bs) + len(us))
                        + (W_SUPPORT if bs or us else 0.0)
                        - W_SEAM * seam
                        - W_TRAP * trapped
                        + dir_bonus
                    )
                    if jitter is not None:
                        score += W_JITTER * jitter[ji % len(jitter)]
                        ji += 1
                    out.append((score, w, d, x0, y0, pid, rot))
        out.sort(key=lambda t: -t[0])
        return out

    def _place(self, L: _Layer, uf: _UF, cand: tuple[float, int, int, int, int, str, int]) -> int:
        _, w, d, x0, y0, pid, rot = cand
        x1, y1 = x0 + w, y0 + d
        segs = tuple(int(s) for s in np.unique(self.seg[x0:x1, y0:y1, L.z0]))
        colour = int(L.col[x0, y0])
        idx = self._add(_Part(L.kind, pid, rot, colour, x0, y0, L.z0, w, d, L.h, segs))
        self.placed += 1
        L.free[x0:x1, y0:y1] = False
        here = sorted(set(L.root[x0:x1, y0:y1].ravel().tolist()))
        left = sum(L.rrem.pop(r) for r in here) - w * d * L.h
        size = sum(L.rsize.pop(r) for r in here)
        new = here[0]
        if len(here) > 1:  # L.root is kept current, so joining its roots is enough
            for r in here[1:]:
                new = uf.union(new, r)
            L.root[np.isin(L.root, here)] = new
        L.rrem[new] = left
        L.rsize[new] = size
        return idx

    def tile(
        self,
        key: Key,
        region: np.ndarray,
        uf: _UF,
        force: tuple[tuple[int, int], tuple[int, int], int] | None = None,
        pref: int | None = None,
        rev: bool = False,
    ) -> bool:
        """Cover ``region`` of layer ``key`` with parts. Returns False if ``force`` is impossible.

        ``force = (a, b, rank)`` makes the first part the rank-th best one covering both a and
        b; when that is impossible nothing is placed.
        """
        self.tiles_done += 1
        L = self._context(key, region, uf, pref, rev)
        if force is not None:
            (ax, ay), must, rank = force
            cands = self._candidates(L, self._free_nbrs(L), ax, ay, must=must)
            if rank >= len(cands):
                return False
            self._place(L, uf, cands[rank])
        while L.free.any():
            n = self._free_nbrs(L)
            ax, ay = self._anchor(L, n)
            cands = self._candidates(L, n, ax, ay)
            if not cands:
                raise ValueError(
                    f"The parts table has no 1x1 {L.kind} at all, so the cell at "
                    f"({ax}, {ay}, {L.z0}) cannot be covered."
                )
            self._place(L, uf, cands[0])
        return True

    def _small_parts(self, key: Key, n0: int) -> tuple[int, int]:
        """(1x1 and 1x2 parts, all parts) placed since the part list had ``n0`` entries."""
        new = [p for p in self.parts[n0:] if p is not None]
        return sum(1 for p in new if p.w * p.d <= 2), len(new)

    def tile_layer(self, key: Key, region: np.ndarray, uf: _UF) -> _UF:
        """Tile a whole layer during the first pass; returns the union-find to carry on with.

        A brick layer that comes out with many 1x1s and 1x2s is tiled again with the other
        preferred direction and with the cells taken in the opposite order, and the tiling
        with the fewest pieces, then the fewest small parts, then the fewest parts wins.
        """
        if key[0] != "b":
            self.tile(key, region, uf)
            return uf
        mark, n0 = len(self._log), len(self.parts)
        state = self.rng.bit_generator.state
        first = (key[1] // 3 + self.seed) % 2
        ways = [(first, False), (1 - first, False), (first, True), (1 - first, True)]
        best: tuple[tuple[int, int, int], int] | None = None
        for i, (pref, rev) in enumerate(ways):
            self.rng.bit_generator.state = state
            trial = uf.copy()
            self.tile(key, region, trial, pref=pref, rev=rev)
            small, total = self._small_parts(key, n0)
            score = (self.piece_count(trial), small, total)
            if best is None or score < best[0]:
                best = (score, i)
            if small <= SMALL_SHARE * total and best[1] == i:
                return trial
            if i == len(ways) - 1 and best[1] == i:
                return trial
            self._rollback(mark)
        assert best is not None
        pref, rev = ways[best[1]]
        self.rng.bit_generator.state = state
        self.tile(key, region, uf, pref=pref, rev=rev)
        return uf

    # ---- editing helpers for repair ---------------------------------------------------------

    def _layer_parts_in_box(self, key: Key, x0: int, x1: int, y0: int, y1: int) -> list[int]:
        z0 = key[1]
        kind = "brick" if key[0] == "b" else "plate"
        ids = np.unique(self.occ[max(0, x0) : x1, max(0, y0) : y1, z0])
        out = []
        for i in ids.tolist():
            if i < 0:
                continue
            p = self.parts[i]
            if p is not None and p.z == z0 and p.kind == kind:
                out.append(int(i))
        return out

    def _footprint_mask(self, saved: list[_Part]) -> np.ndarray:
        m = np.zeros((self.nx, self.ny), dtype=bool)
        for p in saved:
            m[p.x : p.x + p.w, p.y : p.y + p.d] = True
        return m

    # ---- repair -----------------------------------------------------------------------------

    def _seam_pairs(self, roots: np.ndarray) -> list[tuple[int, tuple[int, int], tuple[int, int]]]:
        """Side-by-side cells of one colour and height in different pieces, most promising first.

        Returned as ``(z, a, b)``. Two brick cells of one course are listed once, at the
        course's bottom z.
        """
        size = np.bincount(roots, weights=self.seg_len, minlength=self.nseg)
        found: list[tuple[float, int, tuple[int, int], tuple[int, int]]] = []
        for z in range(self.nz):
            f = self.filled[:, :, z]
            if not f.any():
                continue
            comp = np.where(f, roots[np.maximum(self.seg[:, :, z], 0)], -1)
            col = self.colors[:, :, z]
            brick = self.brick[:, :, z // 3]
            for axis in (0, 1):
                lo = (slice(None, -1), slice(None)) if axis == 0 else (slice(None), slice(None, -1))
                hi = (slice(1, None), slice(None)) if axis == 0 else (slice(None), slice(1, None))
                hit = f[lo] & f[hi] & (col[lo] == col[hi]) & (comp[lo] != comp[hi])
                if z % 3:
                    hit &= ~(brick[lo] & brick[hi])
                for x, y in zip(*np.nonzero(hit), strict=True):
                    x, y = int(x), int(y)
                    bx, by = (x + 1, y) if axis == 0 else (x, y + 1)
                    small = min(size[comp[x, y]], size[comp[bx, by]])
                    found.append((float(small), z, (x, y), (bx, by)))
        found.sort()
        return [(z, a, b) for _, z, a, b in found]

    def _key_of(self, z: int, cell: tuple[int, int]) -> Key:
        if self.brick[cell[0], cell[1], z // 3]:
            return ("b", z - z % 3)
        return ("p", z)

    def _window(self, a: tuple[int, int], b: tuple[int, int], r: int) -> tuple[int, int, int, int]:
        return (
            min(a[0], b[0]) - r,
            max(a[0], b[0]) + r + 1,
            min(a[1], b[1]) - r,
            max(a[1], b[1]) + r + 1,
        )

    def _moves(self, roots: np.ndarray, only: set[int] | None = None) -> list[Move]:
        """Repairs worth trying: joins first, then turning bricks into plates.

        With ``only``, just the seams where one side belongs to one of those pieces.
        """
        joins: list[Move] = []
        demotes: list[Move] = []
        for z, a, b in self._seam_pairs(roots):
            if only is not None:
                ra = int(roots[self.seg[a[0], a[1], z]])
                rb = int(roots[self.seg[b[0], b[1], z]])
                if ra not in only and rb not in only:
                    continue
            ka, kb = self._key_of(z, a), self._key_of(z, b)
            if ka == kb:
                joins.append((z, a, b, "join"))
            if ka[0] == "b" or kb[0] == "b":
                demotes.append((z, a, b, "demote"))
        return joins + demotes

    def _join(self, key: Key, a: Cell, b: Cell, r: int, three: bool, rank: int) -> bool | None:
        """Re-tile a window around a and b with the rank-th best part across them first.

        With ``three`` the layers directly below and above are torn up in the same window
        and re-tiled after. Returns None when this window or rank does not apply (nothing is
        changed then, or the caller rolls back).
        """
        box = self._window(a, b, r)
        idxs = self._layer_parts_in_box(key, *box)
        if not idxs:
            return None
        cells = sum(p.w * p.d for i in idxs if (p := self.parts[i]) is not None)
        limit = REPAIR_FORCED_TRIES_SMALL if cells <= SMALL_WINDOW else REPAIR_FORCED_TRIES
        if rank >= limit:
            return None
        keys = [key] + (self.neighbour_keys(key) if three else [])
        removed = {k: self._remove(self._layer_parts_in_box(k, *box)) for k in keys}
        uf = self.build_uf()
        if not self.tile(key, self._footprint_mask(removed[key]), uf, force=(a, b, rank)):
            return None
        for k in keys[1:]:
            if removed[k]:
                self.tile(k, self._footprint_mask(removed[k]), uf)
        return True

    def _demote(self, z: int, a: Cell, b: Cell, r: int, zj: int) -> bool | None:
        """Turn the bricks of a window into three layers of plates, then re-tile them.

        Plates can be staggered where one brick course cannot (a single-course wall longer
        than 8 studs), and a plate can join a brick cell to a plate cell beside it. The
        part across a and b is forced in the plate layer ``zj``.
        """
        k = z // 3
        zb = 3 * k
        box = self._window(a, b, r)
        idxs = self._layer_parts_in_box(("b", zb), *box)
        if not idxs:
            return None
        demoted = self._footprint_mask(self._remove(idxs))
        self._set_brick(k, self.brick[:, :, k] & ~demoted)
        plate_keys: list[Key] = [("p", zz) for zz in range(zb, min(zb + 3, self.nz))]
        more = {pk: self._remove(self._layer_parts_in_box(pk, *box)) for pk in plate_keys}
        uf = self.build_uf()
        for pk in plate_keys:
            m = (demoted | self._footprint_mask(more[pk])) & self.layer_mask(pk)
            if pk[1] != zj or not self.tile(pk, m, uf, force=(a, b, 0)):
                self.tile(pk, m, uf)
        return True

    def _configs(self, move: Move) -> list[tuple]:
        z, a, b, mode = move
        if mode == "join":
            return [
                (r, three, rank)
                for r, three in REPAIR_WINDOWS
                for rank in range(REPAIR_FORCED_TRIES_SMALL)
            ]
        k = z // 3
        both = bool(self.brick[a[0], a[1], k] and self.brick[b[0], b[1], k])
        joins = [3 * k + 1, 3 * k, 3 * k + 2] if both else [z]
        return [(r, zj) for r in REPAIR_RADII for zj in joins if zj < self.nz]

    def _try_move(self, move: Move, pieces: int, depth: int) -> bool:
        """Apply one repair; keep it if the build ends with fewer than ``pieces`` pieces.

        With ``depth`` > 0, a change that leaves the count unchanged is followed by repairs on
        the pieces it cut off (with ``depth - 1``), and the chain is kept only if together the
        changes help; otherwise all of it is undone.
        """
        z, a, b, mode = move
        key = self._key_of(z, a)
        roots0 = self.build_uf().roots() if depth > 0 else None
        seg_a = int(self.seg[a[0], a[1], z])
        neutral = 0
        skip_window: set[tuple] = set()
        tried: set[tuple] = set()
        for cfg in self._configs(move):
            if self.out_of_budget():
                return False
            if mode == "join":
                r, three, rank = cfg
                if (r, three) in skip_window:
                    continue
                box = self._window(a, b, r)
                sig = (frozenset(self._layer_parts_in_box(key, *box)), three, rank)
                if sig in tried:
                    continue
                tried.add(sig)
            mark = len(self._log)
            done = self._join(key, a, b, *cfg) if mode == "join" else self._demote(z, a, b, *cfg)
            if done is None:
                self._rollback(mark)
                if mode == "join":
                    skip_window.add(cfg[:2])
                continue
            got = self.piece_count()
            if got < pieces:
                return True
            if got == pieces and roots0 is not None and neutral < LOOKAHEAD_NEUTRAL:
                neutral += 1
                if self._follow_up(roots0, seg_a, pieces, depth - 1):
                    return True
            self._rollback(mark)
        return False

    def _follow_up(self, roots0: np.ndarray, seg_a: int, pieces: int, depth: int) -> bool:
        """After a change that joined ``seg_a``'s piece but cut others off, repair those."""
        roots1 = self.build_uf().roots()
        size0 = np.bincount(roots0, minlength=self.nseg)
        size1 = np.bincount(roots1, minlength=self.nseg)
        pairs = np.unique(np.stack([roots1, roots0]), axis=1)
        n_old = np.bincount(pairs[0], minlength=self.nseg)
        same = (n_old[roots1] == 1) & (size1[roots1] == size0[roots0])
        only = set(np.unique(roots1[~same]).tolist()) - {int(roots1[seg_a])}
        if not only:
            return False
        for m in self._moves(roots1, only)[:LOOKAHEAD_MOVES]:
            if self._try_move(m, pieces, depth):
                return True
        return False

    def out_of_budget(self) -> bool:
        return self.tiles_done >= self.tile_budget or self.placed >= self.place_budget

    def repair(self) -> None:
        """Join pieces until the floor is reached or no repair helps; always ends.

        Each kept change lowers the number of pieces. Repairs that need two changes are only
        tried when no single change helps. A repair that failed is tried again (at most
        ``REPAIR_RETRIES`` times) only after the build has changed since, and only after
        every repair not yet tried.
        """
        failed: dict[tuple[Move, int], tuple[int, int]] = {}
        attempts = 0
        cells = int(self.filled.sum())
        self.tile_budget = self.tiles_done + REPAIR_TILE_BUDGET + cells // 10
        self.place_budget = self.placed + REPAIR_PLACE_BUDGET + cells // 5
        while attempts < REPAIR_MAX_ATTEMPTS and not self.out_of_budget():
            self._log.clear()
            uf = self.build_uf()
            pieces = self.piece_count(uf)
            if pieces <= self.floor:
                return
            moves = self._moves(uf.roots())
            progressed = False
            for depth in range(REPAIR_DEPTH + 1):
                todo: list[tuple[int, int, Move]] = []
                for order, m in enumerate(moves):
                    seen = failed.get((m, depth))
                    if seen is not None and (seen[0] <= pieces or seen[1] >= REPAIR_RETRIES):
                        continue
                    todo.append((0 if seen is None else 1, order, m))
                todo.sort(key=lambda t: t[:2])
                for _, _, m in todo:
                    attempts += 1
                    if self._try_move(m, pieces, depth):
                        progressed = True
                        break
                    failed[(m, depth)] = (pieces, failed.get((m, depth), (0, 0))[1] + 1)
                    if attempts >= REPAIR_MAX_ATTEMPTS or self.out_of_budget():
                        return
                if progressed:
                    break
            if not progressed:
                return

    # ---- whole solve ------------------------------------------------------------------------

    def solve(self) -> list[_Part]:
        uf = _UF(self.nseg)
        for key in self.all_keys():
            region = self.layer_mask(key).copy()
            if region.any():
                uf = self.tile_layer(key, region, uf)
        self._log.clear()
        self.repair()
        self._log.clear()
        return [p for p in self.parts if p is not None]


def _gap(p: _Part, q: _Part) -> int:
    """Cells between two footprints (0 when they touch side by side or overlap)."""
    gx = max(p.x - (q.x + q.w), q.x - (p.x + p.w), 0)
    gy = max(p.y - (q.y + q.d), q.y - (p.y + p.d), 0)
    return gx + gy


def _assign_steps(parts: list[_Part], shape: tuple[int, int, int]) -> list[int]:
    """Building steps for ``parts``, which must be sorted by (z, plates first, y, x).

    Bottom first; a step holds parts of one height and one kind only, at most
    ``MAX_PARTS_PER_STEP`` of them, grown outwards from one part through parts that touch it
    side by side. A part that touches no other part of its height and kind joins the nearest
    step of that height with room, so curved shapes, where plates stand alone among bricks,
    do not end up with one part per step; a part whose neighbours all have steps already
    joins one of those steps if it has room. The next step starts next to the previous one
    when it can.
    """
    nx, ny, _ = shape
    steps = [0] * len(parts)
    groups: dict[tuple[int, int], list[int]] = {}
    for i, p in enumerate(parts):
        groups.setdefault((p.z, 0 if p.kind == "plate" else 1), []).append(i)
    step = 0
    for gkey in sorted(groups):
        idxs = groups[gkey]  # already in (y, x) order, as indices grow
        grid = np.full((nx, ny), -1, dtype=np.int64)
        for i in idxs:
            p = parts[i]
            grid[p.x : p.x + p.w, p.y : p.y + p.d] = i
        adj: dict[int, set[int]] = {i: set() for i in idxs}
        for lo, hi in ((grid[:-1, :], grid[1:, :]), (grid[:, :-1], grid[:, 1:])):
            hit = (lo >= 0) & (hi >= 0) & (lo != hi)
            for u, v in zip(lo[hit].tolist(), hi[hit].tolist(), strict=True):
                adj[u].add(v)
                adj[v].add(u)
        left = set(idxs)
        frontier: set[int] = set()  # parts touching ones already given a step
        size: dict[int, int] = {}  # parts in each step of this height
        while left:
            nearby = frontier & left
            start = min(nearby) if nearby else min(left)
            if adj[start] and not adj[start] & left:
                # every part beside it already has a step: join one of those that has room
                room = [(size[steps[u]], steps[u]) for u in adj[start]]
                room = [t for t in room if t[0] < MAX_PARTS_PER_STEP]
                if room:
                    s = min(room)[1]
                    steps[start] = s
                    size[s] += 1
                    left.discard(start)
                    continue
            step += 1
            group = [start]
            left.discard(start)
            queue = deque([start])
            while len(group) < MAX_PARTS_PER_STEP:
                if not queue:  # nothing beside the step is left
                    # a part that touches no part of its height can never be beside the others
                    # in its step, so it joins the nearest step instead of standing alone
                    lone_group = not any(adj[u] for u in group)
                    near = [
                        (min(_gap(parts[u], parts[v]) for u in group), v)
                        for v in left
                        if lone_group or not adj[v]
                    ]
                    if not near:
                        break
                    v = min(near)[1]
                    group.append(v)
                    left.discard(v)
                    queue.append(v)
                    continue
                for v in sorted(adj[queue.popleft()] & left):
                    if len(group) == MAX_PARTS_PER_STEP:
                        break
                    group.append(v)
                    left.discard(v)
                    queue.append(v)
            for u in group:
                steps[u] = step
                frontier |= adj[u]
            size[step] = len(group)
    return steps


def solve(design: Design, catalog: Catalog, *, seed: int = 0) -> Build:
    solver = _Solver(design, catalog, seed)
    parts = solver.solve()
    parts.sort(key=lambda p: (p.z, 0 if p.kind == "plate" else 1, p.y, p.x))
    steps = _assign_steps(parts, design.shape)
    placements = [
        Placement(part=p.part, color=p.color, x=p.x, y=p.y, z=p.z, rot=p.rot, step=s)
        for p, s in zip(parts, steps, strict=True)
    ]
    order = sorted(range(len(placements)), key=lambda i: (placements[i].step, i))
    return Build(shape=design.shape, parts=[placements[i] for i in order])
