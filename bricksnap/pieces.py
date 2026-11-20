"""Tell when a model file looks like a layout of separate pieces, and keep one piece of it.

CONTRACT (see tests/test_pieces.py)

Some files are not one object but several pieces laid out side by side, such as the parts of
a kit set out on a 3D printer's bed. Built as one model, the size in studs is spread over the
whole layout and every piece comes out small. This module finds such pieces, before anything
is built, so the person can be asked what to build. It is a question, never a verdict.

The rule. Seen from above, the model covers the ground in islands: areas it covers, with
clear ground between them. Every island is a piece unless it is tiny (its longest side under
``TINY``, a tenth, of the longest island's) or flat; a file looks like several pieces when it
has two or more, up to the limits below.
- "Above" is the up axis ``seed.load_seed`` uses (the format's default, or ``up``). Anything
  over or under something else (a halo, a table top on its legs, leaves over a trunk, a car
  body over its wheels, blocks resting on a slab) is in the same island by construction,
  and no piece hides another from above. Islands at different heights are pieces all the
  same: the parts of a real kit do not all start at one level.
- One island is one piece, always. This knowingly makes a question of some single objects:
  a figure with a sizeable detail floating beside it (not above it), a sparse tree of
  separate leaf clusters, letters laid out flat, a ring of beads. That is acceptable because
  the words ask rather than state, "everything together" is one choice away, and a part
  floating beside a body could not be built from bricks anyway.
- Seen from the side, a flat kit gives wrong pieces (a file saved Y-up, as .obj or .glb
  usually are, while the kit lies in its x-y plane). Other axes are not tried by themselves
  (from the side a halo or a table top becomes an island of its own); instead the words say
  that a picture showing the pieces from the side means the file lies on its side, and how
  to say which way is up.
- Flat means no thickness along some axis (under 1e-6 of the model's longest side). Tiny
  and flat islands are the "small bits": not offered, left out when one piece is built
  alone, kept with everything together; the words say how many there are.
- No finding (the file is built whole, with the ordinary errors): fewer than two pieces;
  more than ``MAX_PIECES`` (40: a scatter, not a kit); or more than ``MAX_SMALL_BITS`` (200)
  small bits (dust, not a kit). The last two are told in one plain line (``Pieces.note``).

``find_pieces(path, up=None, name=None) -> Pieces``
- Reads the file as ``seed.load_seed`` does (``seed.load_mesh``: the same formats, clean-up
  and SeedError messages). ``name`` is the file name to use in the words (the person's own,
  when the file was saved under another name).
- ``Pieces.several``: whether there is a finding. ``Pieces.everything``: every piece, numbered
  1, 2, ... by longest side, longest first (ties by box volume, larger first, then by the
  smallest corner, x then y then z, the right way up); without a finding, one piece, the
  whole file. ``Pieces.pieces``: those offered, the first ``OFFERED`` (12); ``Pieces.more``:
  how many come after them; ``Pieces.small_bits``; ``Pieces.note()``.
- Each ``Piece``: ``number``; ``size`` (side to side, front to back, height, in the file's
  units, the right way up); ``box`` (its bounding box in the file's own coordinates,
  ``((x, y, z), (x, y, z))``, which a project keeps to find the piece again); ``faces``.
- ``Pieces.piece(n, any_piece=False)``: piece n among those offered (or, with ``any_piece``,
  any that exists); ``within(n, studs)`` and ``alone(n, studs)``: its size in studs when the
  whole file is built at ``studs``, and when it is built alone.
- ``Pieces.lines(studs)``: the finding in plain sentences with the numbers, ending with the
  hint about a file that lies on its side.
- ``Pieces.to_json(studs)``: ``{"source", "several", "count", "more", "small_bits",
  "studs", "pieces": [{"number", "within", "alone", "faces", "colour"}]}``, sizes in studs to
  tenths, ``colour`` the piece's colour in the picture; at most 12 pieces, whatever the file.
- ``Pieces.picture()`` / ``save_picture(path)``: the islands from above, front at the
  bottom, each offered piece in its colour, other pieces and small bits in grey, at most
  ``PICTURE_SIZE``. Each offered piece's number is drawn on it when the piece holds the
  whole circle, otherwise beside it with a leader line to it; numbers never overlap each
  other and never leave the picture. ``Pieces`` holds no mesh, only this summary and a
  small map for the picture.

``keep_piece(vertices, faces, colours, axis, name, piece=None, box=None)``
- From ``seed.load_mesh``'s arrays, the triangles of one piece, unused vertices dropped, so
  ``seed.load_seed(..., piece=n)`` turns, scales and centres it exactly as a file holding
  only that piece. With ``box`` the piece is the one whose box matches (within 1e-6 of the
  model's longest side); without it, piece number ``piece`` (any piece that exists). Raises
  SeedError when no piece matches the box ("make the project again": the file or the rule
  changed), when there is no such number, and for a number that is not a whole number.
  Without a finding, piece 1 is the whole file, unchanged.

``parse_choice(text) -> "largest" | "all" | int`` reads a choice as typed or sent ("largest",
"all", or a number of 1 or more in the digits 0 to 9) and raises SeedError otherwise.
``resolve(choice, pieces, any_piece=False) -> int | None``: "largest" is 1, "all" None (build
everything), a number must be a piece that is offered (or, with ``any_piece``, that exists).

Implementation notes and the measured bound
-------------------------------------------
- Each triangle's three edges are drawn into an occupancy grid from above, sampled at most
  one cell apart, and every triangle whose footprint covers at least ``FILL_CELLS`` cells is
  filled; the islands are the grid's 8-connected areas, and each triangle belongs to the
  island of its centre's cell (or of a corner's). No welding and no bodies, so double-sided
  and unwelded surfaces are one island. Ground is clear only when it is at least ``CLEAR``
  (5) cells wide, half a percent of the longer side: areas closer than that are one island
  (a sample cat's tail floats a hair's breadth from its body).
- The grid has ``GRID`` (1000) cells along the longer side, coarser only when the edges would
  need more than ``SAMPLES`` (40 million) samples, more than ``MAX_FILLS`` triangles would be
  filled, or more than ``MAX_FILL_PIXELS`` cells. Edge samples are drawn about ``_CHUNK`` at
  a time, in 32-bit steps, so memory stays bounded.
- Measured on this machine (loaded by other work, so times vary by about half):
  1.19 million loose small triangles (59.5 MB STL): load 1.9 to 2.7 s, search 1.3 to 1.6 s.
  1.19 million long thin triangles: load 3.7 s, search 2.7 s, peak memory 1.3 GB, of which
  0.9 GB is the plain load. 1.19 million large overlapping triangles: load 3.5 s, search
  1.3 s, peak 1.2 GB (0.8 GB the load). 250,001 specks each at its own height: load 0.4 s,
  search 0.8 s. A real 2 million-triangle layout (3MF): load 5 to 10 s, search 0.5 to
  1.8 s. So the search costs no more than about one more plain load, and adds at most about
  half a gigabyte to it, for any file inside the upload limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from bricksnap.types import SeedError

TINY = 0.10
MAX_PIECES = 40
MAX_SMALL_BITS = 200
OFFERED = 12
GRID = 1000
CLEAR = 5  # cells: ground between two islands must be at least this wide to be clear
SAMPLES = 40_000_000
FILL_CELLS = 2.0  # a triangle whose footprint covers this many cells is filled
MAX_FILLS = 300_000
MAX_FILL_PIXELS = 50_000_000
PICTURE_SIZE = (400, 280)
_FLAT = 1e-6
_BOX_MATCH = 1e-6
_SLICE = 2_000_000  # edge corners drawn at a time
_CHUNK = 4_000_000  # edge samples drawn at a time

_PALETTE = (
    (201, 26, 9),
    (0, 85, 191),
    (35, 120, 65),
    (242, 205, 55),
    (129, 0, 123),
    (254, 138, 24),
    (5, 157, 158),
    (88, 42, 18),
    (228, 173, 200),
    (75, 159, 74),
    (10, 52, 99),
    (170, 125, 85),
)
_GREY = (175, 178, 180)

Box = tuple[tuple[float, float, float], tuple[float, float, float]]


@dataclass
class Piece:
    number: int
    size: tuple[float, float, float]
    box: Box
    faces: int


@dataclass
class Pieces:
    source: str
    several: bool
    everything: list[Piece]  # every piece in order (at most MAX_PIECES); one without a finding
    whole: tuple[float, float, float]
    small_bits: int = 0
    parts: int = 0
    reason: str = ""
    plan: np.ndarray | None = field(default=None, repr=False)  # the picture's map, see _plan

    @property
    def pieces(self) -> list[Piece]:
        """The pieces offered: the first ``OFFERED``."""
        return self.everything[:OFFERED]

    @property
    def count(self) -> int:
        return len(self.pieces)

    @property
    def more(self) -> int:
        return len(self.everything) - len(self.pieces)

    def piece(self, number: int, any_piece: bool = False) -> Piece:
        """Piece ``number``: one of those offered, or with ``any_piece`` any that exists."""
        limit = len(self.everything) if any_piece else len(self.pieces)
        if not 1 <= number <= limit:
            raise SeedError(_no_such_piece(self.source, number, limit, self.several))
        return self.everything[number - 1]

    def within(self, number: int, studs: int) -> tuple[float, float, float]:
        return _studs(self.piece(number, True).size, studs / max(self.whole))

    def alone(self, number: int, studs: int) -> tuple[float, float, float]:
        size = self.piece(number, True).size
        return _studs(size, studs / max(size))

    def note(self) -> str | None:
        """One plain line when separate parts were seen but are not asked about, else None."""
        if self.reason == "scatter":
            return (
                f"{self.source} has {self.parts} separate parts seen from above, too many to "
                "be a kit; they are built together."
            )
        if self.reason == "dust":
            return (
                f"{self.source} has {self.parts} separate parts and more than "
                f"{MAX_SMALL_BITS} small bits seen from above; they are built together."
            )
        return None

    def to_json(self, studs: int) -> dict[str, Any]:
        return {
            "source": self.source,
            "several": self.several,
            "count": self.count if self.several else 0,
            "more": self.more if self.several else 0,
            "small_bits": self.small_bits,
            "studs": int(studs),
            "pieces": [
                {
                    "number": p.number,
                    "within": list(self.within(p.number, studs)),
                    "alone": list(self.alone(p.number, studs)),
                    "faces": p.faces,
                    "colour": "#{:02x}{:02x}{:02x}".format(*_colour(p.number)),
                }
                for p in self.pieces
            ]
            if self.several
            else [],
        }

    def lines(self, studs: int) -> list[str]:
        """The finding in plain sentences, for the command line."""
        if not self.several:
            return [self.note() or f"{self.source} looks like one object."]
        total = len(self.everything)
        out = [
            f"{self.source} looks like {total} separate pieces laid out side by side, not one "
            "object (like the parts of a kit set out for 3D printing).",
            f"Built all together at {studs} studs, the largest piece would be about "
            f"{_n(max(self.within(1, studs)))} studs long; built alone it would be {studs}.",
            "The pieces, largest first (in studs, side to side x front to back x tall):",
        ]
        for p in self.pieces:
            note = " (the largest)" if p.number == 1 else ""
            out.append(
                f"  Piece {p.number}: {_dims(self.within(p.number, studs))} in the whole "
                f"layout, {_dims(self.alone(p.number, studs))} alone{note}"
            )
        if self.more:
            out.append(
                f"  ...and {_plural(self.more, 'smaller piece')}, numbered {OFFERED + 1} to "
                f"{total}."
            )
        if self.small_bits:
            out.append(
                f"There are also {_plural(self.small_bits, 'small bit')}; they are left out "
                "when one piece is built alone."
            )
        out.append(
            "If the picture shows the pieces from the side rather than from above, the file "
            "probably lies on its side: say which way is up with --up x, --up y or --up z."
        )
        return out

    def picture(self) -> Any:
        return _draw(self)

    def save_picture(self, path: str | Path) -> None:
        self.picture().save(path, format="PNG")


# ---- finding the pieces ---------------------------------------------------------------------


@dataclass
class _Found:
    """Every face's owner: the index of its piece in the full order (0 is the largest), or
    -1 for a small bit; the pieces in order; and the picture's map."""

    several: bool
    owner: np.ndarray
    order: int
    more: int
    small_bits: int
    plan: np.ndarray
    parts: int  # islands that would be pieces, also when there is no finding
    reason: str  # why there is no finding although there are pieces: "scatter", "dust" or ""


def find_pieces(path: str | Path, up: str | None = None, name: str | None = None) -> Pieces:
    """The pieces of a model file (see the contract)."""
    from bricksnap.seed import _orient, load_mesh

    vertices, faces, _, file_name, axis = load_mesh(path, up)
    turned = _orient(vertices, axis)
    found = _search(turned, faces)
    source = name or file_name
    whole = _triple(turned.max(axis=0) - turned.min(axis=0))
    rlo, rhi, faces_of = _boxes(vertices, faces, found)
    tlo, thi, _ = _boxes(turned, faces, found)
    pieces = [
        Piece(k + 1, _triple(thi[k] - tlo[k]), (_triple(rlo[k]), _triple(rhi[k])), faces_of[k])
        for k in range(found.order)
    ]
    return Pieces(
        source,
        found.several,
        pieces,
        whole,
        found.small_bits,
        found.parts,
        found.reason,
        found.plan,
    )


def _boxes(
    points: np.ndarray, faces: np.ndarray, found: _Found
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Each piece's box (minimum and maximum corners) and its number of triangles."""
    tri = points[faces]
    keep = found.owner >= 0
    owner = found.owner[keep]
    lo = np.full((found.order, 3), np.inf)
    hi = np.full((found.order, 3), -np.inf)
    np.minimum.at(lo, owner, tri[keep].min(axis=1))
    np.maximum.at(hi, owner, tri[keep].max(axis=1))
    counts = np.bincount(owner, minlength=found.order)
    return lo, hi, [int(c) for c in counts]


def _triple(values: np.ndarray) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


def keep_piece(
    vertices: np.ndarray,
    faces: np.ndarray,
    colours: np.ndarray | None,
    axis: str,
    name: str,
    piece: int | None = None,
    box: Any = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Only the triangles of one piece (see the contract), unused vertices dropped."""
    from bricksnap.seed import _orient

    if piece is not None and (isinstance(piece, bool) or not isinstance(piece, int | np.integer)):
        raise SeedError(f"A piece must be given by its number, not {piece!r}.")
    found = _search(_orient(vertices, axis), faces)
    if box is not None:
        wanted = _read_box(box, name)
        size = float((vertices.max(axis=0) - vertices.min(axis=0)).max())
        index = None
        if found.several:
            lo, hi, _ = _boxes(vertices, faces, found)
            close = (np.abs(lo - wanted[0]).max(axis=1) <= _BOX_MATCH * size) & (
                np.abs(hi - wanted[1]).max(axis=1) <= _BOX_MATCH * size
            )
            hits = np.nonzero(close)[0]
            index = int(hits[0]) if len(hits) else None
        if index is None:
            raise SeedError(
                f"The piece of {name} this project builds cannot be found in the file any "
                "more (the file or the way BrickSnap finds pieces has changed). Make the "
                "project again from the file and choose the piece again."
            )
    else:
        number = 1 if piece is None else int(piece)
        count = found.order if found.several else 1
        if not 1 <= number <= count:
            raise SeedError(_no_such_piece(name, number, count, found.several))
        index = number - 1
    keep = found.owner == index
    if keep.all():
        return vertices, faces, colours
    faces = faces[keep]
    if colours is not None:
        colours = colours[keep]
    unique, inverse = np.unique(faces, return_inverse=True)
    return vertices[unique], inverse.reshape(faces.shape).astype(np.int64), colours


def _read_box(box: Any, name: str) -> np.ndarray:
    try:
        wanted = np.asarray(box, dtype=np.float64)
    except (TypeError, ValueError):
        wanted = np.zeros(0)
    if wanted.shape != (2, 3) or not np.isfinite(wanted).all():
        raise SeedError(
            f"This project's record of which piece of {name} it builds is damaged. Make the "
            "project again from the file and choose the piece again."
        )
    return wanted


def _search(turned: np.ndarray, faces: np.ndarray) -> _Found:
    """The rule (see the contract), on vertices already turned the right way up."""

    tri = turned[faces]  # (m, 3, 3)
    lo = turned.min(axis=0)
    hi = turned.max(axis=0)
    longest = float((hi - lo).max())
    labels, island, cell = _islands(tri[:, :, :2], lo[:2], hi[:2])
    n = int(labels.max())
    m = len(faces)
    if n == 0:  # cannot happen for a file with triangles; one island then
        island = np.ones(m, dtype=np.int64)
        n = 1

    # each island's box, the right way up
    ilo = np.full((n + 1, 3), np.inf)
    ihi = np.full((n + 1, 3), -np.inf)
    np.minimum.at(ilo, island, tri.min(axis=1))
    np.maximum.at(ihi, island, tri.max(axis=1))
    present = np.isfinite(ilo[:, 0])
    present[0] = False
    ids = np.nonzero(present)[0]
    size = ihi[ids] - ilo[ids]
    side = size.max(axis=1)
    flat = size.min(axis=1) <= _FLAT * longest
    solid = ~flat
    top = side[solid].max() if solid.any() else 0.0
    is_piece = solid & (side >= TINY * top)
    q = np.nonzero(is_piece)[0]
    small_bits = int(len(ids) - len(q))
    owner_of = np.full(n + 1, -1, dtype=np.int64)
    if len(q) > MAX_PIECES:
        reason = "scatter"
    elif len(q) >= 2 and small_bits > MAX_SMALL_BITS:
        reason = "dust"
    else:
        reason = ""
    if reason or len(q) < 2:
        owner = np.zeros(m, dtype=np.int64)
        plan = _plan(labels, np.where(present, 0, -1), cell)
        return _Found(False, owner, 1, 0, 0, plan, len(q), reason)
    volume = np.prod(size, axis=1)
    order = sorted(
        q.tolist(),
        key=lambda i: (
            -float(f"{side[i]:.9g}"),
            -float(f"{volume[i]:.9g}"),
            *(float(f"{c:.9g}") for c in ilo[ids[i]]),
        ),
    )
    for k, i in enumerate(order):
        owner_of[ids[i]] = k
    owner = owner_of[island]
    plan = _plan(labels, owner_of, cell)
    return _Found(
        True, owner, len(order), max(0, len(order) - OFFERED), small_bits, plan, len(q), ""
    )


def _islands(
    xy: np.ndarray, lo: np.ndarray, hi: np.ndarray
) -> tuple[np.ndarray, np.ndarray, float]:
    """(the grid of island labels from above, rows from the back to the front; every
    triangle's island; the cell size)."""
    from scipy import ndimage

    span = np.maximum(hi - lo, 1e-12)
    cell = float(span.max()) / GRID
    a = xy
    b = np.roll(xy, -1, axis=1)
    reach = np.abs(b - a).max(axis=2)  # (m, 3) longest step of each edge, in file units
    e1, e2 = xy[:, 1] - xy[:, 0], xy[:, 2] - xy[:, 0]
    area = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2.0  # footprint, file units
    total_reach = float(reach.sum())
    for _ in range(64):  # coarser until the samples, the fills and their pixels are bounded
        big = area >= FILL_CELLS * cell * cell
        pixels = float(area[big].sum()) / (cell * cell)
        if (
            total_reach / cell + reach.size <= SAMPLES
            and int(big.sum()) <= MAX_FILLS
            and pixels <= MAX_FILL_PIXELS
        ):
            break
        cell *= 1.5
    cols = int(np.floor(span[0] / cell)) + 1
    rows = int(np.floor(span[1] / cell)) + 1
    grid = np.zeros((rows, cols), dtype=bool)

    def cells(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = np.clip(((points[..., 0] - lo[0]) / cell).astype(np.int64), 0, cols - 1)
        r = np.clip(((hi[1] - points[..., 1]) / cell).astype(np.int64), 0, rows - 1)
        return r, c

    ea = a.reshape(-1, 2)
    eb = b.reshape(-1, 2)
    steps = np.ceil(reach.reshape(-1) / cell).astype(np.int64)  # samples - 1 per edge
    for start in range(0, len(ea), _SLICE):
        r, c = cells(ea[start : start + _SLICE])
        grid[r, c] = True
    long = np.nonzero(steps > 0)[0]
    ends = np.cumsum(steps[long])
    # slices of edges holding at most about _CHUNK samples each, so memory stays small
    cuts = (
        np.searchsorted(ends, np.arange(_CHUNK, int(ends[-1]) + _CHUNK, _CHUNK))
        if len(long)
        else np.zeros(0, dtype=np.int64)
    )
    first_edge = 0
    for cut in [*cuts.tolist(), len(long)]:
        chosen = long[first_edge : cut + 1]
        first_edge = cut + 1
        if len(chosen) == 0:
            continue
        counts = steps[chosen]
        which = np.repeat(chosen, counts)
        first = np.cumsum(counts) - counts
        k = np.arange(int(counts.sum()), dtype=np.float32) - np.repeat(first, counts) + 1
        t = (k / np.repeat(counts, counts).astype(np.float32))[:, None]
        points = ea[which] + t * (eb[which] - ea[which])
        del which, k, t
        r, c = cells(points)
        grid[r, c] = True
        del points, r, c
    if big.any():  # fill the triangles that cover more than a couple of cells
        from PIL import Image, ImageDraw

        canvas = Image.new("1", (cols, rows), 0)
        draw = ImageDraw.Draw(canvas)
        px = (xy[big, :, 0] - lo[0]) / cell
        py = (hi[1] - xy[big, :, 1]) / cell
        for x, y in zip(px.tolist(), py.tolist(), strict=True):
            draw.polygon(list(zip(x, y, strict=True)), fill=1)
        grid |= np.asarray(canvas, dtype=bool)
    # ground narrower than CLEAR cells is not clear: grow every area by half of it, label
    # the grown areas, and keep the labels only where the model covers the ground
    grown = ndimage.binary_dilation(
        grid, structure=np.ones((3, 3), dtype=bool), iterations=CLEAR // 2
    )
    joined, _ = ndimage.label(grown, structure=np.ones((3, 3), dtype=bool))
    labels = np.where(grid, joined, 0)
    r, c = cells(xy.mean(axis=1))
    island = labels[r, c].astype(np.int64)
    missing = np.nonzero(island == 0)[0]
    if len(missing):
        r, c = cells(xy[missing, 0])
        island[missing] = labels[r, c]
    return labels, island, cell


def _plan(labels: np.ndarray, owner_of: np.ndarray, cell: float) -> np.ndarray:
    """The picture's map: per cell, 0 for clear ground, k + 1 for piece k, -1 for a small
    bit; holes inside an outline filled with what surrounds them."""
    from scipy import ndimage

    plan = np.where(labels > 0, owner_of[labels] + 1, 0)
    plan[(labels > 0) & (plan == 0)] = -1
    filled = ndimage.binary_fill_holes(labels > 0)
    holes = filled & (labels == 0)
    if holes.any():
        _, (ri, ci) = ndimage.distance_transform_edt(labels == 0, return_indices=True)
        plan[holes] = plan[ri[holes], ci[holes]]
    return plan.astype(np.int16)


# ---- choosing -------------------------------------------------------------------------------


def parse_choice(text: Any) -> str | int:
    """'largest', 'all' or a piece's number (1 or more), as typed or sent by the page."""
    if isinstance(text, bool):
        raise SeedError(_CHOICE_HELP)
    if isinstance(text, int | np.integer):
        value = int(text)
    elif isinstance(text, str):
        word = text.strip().lower()
        if word in ("largest", "all"):
            return word
        if not word or not all("0" <= ch <= "9" for ch in word) or len(word) > 6:
            raise SeedError(_CHOICE_HELP)
        value = int(word)
    else:
        raise SeedError(_CHOICE_HELP)
    if value < 1:
        raise SeedError(_CHOICE_HELP)
    return value


def resolve(choice: str | int, pieces: Pieces, any_piece: bool = False) -> int | None:
    """What a project keeps: 1 for the largest, None for everything, or a piece's number
    (one of those offered, or with ``any_piece`` any piece that exists)."""
    if choice == "all":
        return None
    if choice == "largest":
        return 1
    number = int(choice)
    pieces.piece(number, any_piece)  # raises SeedError for a number there is no piece for
    return number


_CHOICE_HELP = (
    "Choose which piece to build with 'largest' (the biggest piece alone), 'all' (everything "
    "as it is, all the pieces together) or a piece's number, such as 2."
)


def _no_such_piece(name: str, number: int, count: int, several: bool = True) -> str:
    if not several:
        return (
            f"{name} looks like one object, so there is no piece {number} to build. Build it whole."
        )
    return (
        f"{name} has {count} pieces to choose from, numbered 1 to {count}, so there is no "
        f"piece {number}. Choose one of those numbers, 'largest' or 'all'."
    )


# ---- words and pictures ---------------------------------------------------------------------


def _colour(number: int) -> tuple[int, int, int]:
    """The colour piece ``number`` has in the picture."""
    return _PALETTE[(number - 1) % len(_PALETTE)]


def _studs(size: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    a, b, c = (round(float(s) * scale, 1) for s in size)
    return (a, b, c)


def _n(value: float) -> str:
    """Whole studs from 10 up, tenths below (but no ".0")."""
    return str(int(round(value))) if value >= 10 else f"{value:.1f}".removesuffix(".0")


def _dims(size: tuple[float, float, float]) -> str:
    return " x ".join(_n(s) for s in size)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _draw(found: Pieces) -> Any:
    from PIL import Image, ImageDraw
    from scipy import ndimage

    from bricksnap.render import BACKGROUND, _font_of_size

    plan = found.plan if found.plan is not None else np.ones((1, 1), dtype=np.int16)
    offered = found.count if found.several else 0
    top = int(plan.max()) if plan.size else 0
    palette = np.zeros((top + 2, 3), dtype=np.uint8)  # index = plan value + 1
    palette[0] = _GREY
    palette[1] = BACKGROUND
    for k in range(1, top + 1):
        palette[k + 1] = _colour(k) if k <= offered else _GREY
    if not found.several:
        palette[2:] = _GREY
    rows, cols = plan.shape
    width, height = PICTURE_SIZE
    margin = _LABEL_R * 2 + 6  # room for numbers beside pieces at the edges
    scale = min((width - 2 * margin) / cols, (height - 2 * margin) / rows)
    w, h = max(1, round(cols * scale)), max(1, round(rows * scale))
    grow = int(np.ceil(2.0 / scale))  # so that a thin piece is still a couple of pixels wide
    if grow > 1:
        wider = ndimage.grey_dilation(plan, size=(grow, grow))
        plan = np.where(plan == 0, wider, plan)
    rgb = palette[plan.astype(np.int64) + 1]
    inner = Image.fromarray(rgb, "RGB").resize((w, h), Image.Resampling.BOX)
    picture = Image.new("RGB", (w + 2 * margin, h + 2 * margin), BACKGROUND)
    picture.paste(inner, (margin, margin))
    shown = np.zeros((picture.height, picture.width), dtype=np.int32)  # piece per pixel
    small = Image.fromarray(plan.astype(np.int32)).resize((w, h), Image.Resampling.NEAREST)
    shown[margin : margin + h, margin : margin + w] = np.asarray(small)
    places = _place_labels(shown, offered, picture.width, picture.height)
    pen = ImageDraw.Draw(picture)
    for (x, y), (px, py) in places.values():  # leader lines first, under the numbers
        if (px, py) != (x, y):
            pen.line((px, py, x, y), fill=(30, 30, 30), width=2)
            pen.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(30, 30, 30))
    font = _font_of_size(_LABEL_FONT)
    r = _LABEL_R
    for number, ((x, y), _) in places.items():
        pen.ellipse(
            (x - r, y - r, x + r, y + r), fill=(255, 255, 255), outline=(30, 30, 30), width=2
        )
        pen.text((x, y), str(number), fill=(20, 20, 20), font=font, anchor="mm")
    return picture


_LABEL_R = 16
_LABEL_FONT = 21


def _place_labels(
    shown: np.ndarray, count: int, width: int, height: int
) -> dict[int, tuple[tuple[int, int], tuple[int, int]]]:
    """Where to put each offered piece's number: {number: (centre, the point of the piece a
    leader line goes to)} (the two are equal for a number drawn on its piece). A number goes
    on its piece when the piece holds the whole circle; otherwise beside it, as near as
    there is room, never over another number, never off the picture, and over as little of
    the other pieces as can be found."""
    r = _LABEL_R
    yy, xx = np.mgrid[-r - 2 : r + 3, -r - 2 : r + 3]
    disc = yy**2 + xx**2 <= (r + 2) ** 2
    placed: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}

    def free(x: int, y: int) -> bool:
        if not (r + 2 <= x < width - r - 2 and r + 2 <= y < height - r - 2):
            return False
        return all((x - a) ** 2 + (y - b) ** 2 >= (2 * r + 4) ** 2 for (a, b), _ in placed.values())

    def under(x: int, y: int) -> np.ndarray:
        return shown[y - r - 2 : y + r + 3, x - r - 2 : x + r + 3][disc]

    for number in range(1, count + 1):
        ys, xs = np.nonzero(shown == number)
        if len(xs) == 0:
            continue
        cx, cy = xs.mean(), ys.mean()
        k = int(np.argmin((xs - cx) ** 2 + (ys - cy) ** 2))
        x0, y0 = int(xs[k]), int(ys[k])
        if free(x0, y0) and (under(x0, y0) == number).all():
            placed[number] = ((x0, y0), (x0, y0))
            continue
        best = None
        left, right, top, bottom = xs.min(), xs.max(), ys.min(), ys.max()
        for step in range(1, 12):
            d = r + 4 + (step - 1) * (r + 2)
            candidates = [
                (right + d, y0),
                (left - d, y0),
                (x0, top - d),
                (x0, bottom + d),
                (right + d, top - d),
                (left - d, top - d),
                (right + d, bottom + d),
                (left - d, bottom + d),
            ]
            for x, y in candidates:
                x, y = int(x), int(y)
                if not free(x, y):
                    continue
                cover = int((under(x, y) != 0).sum())
                if best is None or cover < best[0]:
                    best = (cover, x, y)
            if best is not None and best[0] == 0:
                break
        if best is None:  # crowded: the nearest free spot anywhere
            spots = [
                (abs(x - x0) + abs(y - y0), x, y)
                for y in range(r + 2, height - r - 2, 3)
                for x in range(r + 2, width - r - 2, 3)
                if free(x, y)
            ]
            if not spots:
                continue
            _, bx, by = min(spots)
            best = (0, bx, by)
        _, x, y = best
        k = int(np.argmin((xs - x) ** 2 + (ys - y) ** 2))
        placed[number] = ((x, y), (int(xs[k]), int(ys[k])))
    return placed
