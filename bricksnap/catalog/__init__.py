"""The parts and colours table, and the geometry rules for placing a part on the grid.

``parts.json`` and ``colours.json`` next to this file are the data; ``SOURCES.md`` says where
each value came from. Everything else in BrickSnap asks this module what a part covers, where
its studs are, and which colours it really exists in.

Rotation
--------
A part's own axes are LDraw's: X to the right, Z to the back, with ``sx`` studs along X and
``sz`` studs along Z. ``Placement.rot`` turns the part about the vertical axis:

==== ============================ =======================
rot  part X points along          part Z points along
==== ============================ =======================
0    grid +x                      grid +y
90   grid +y                      grid -x
180  grid -x                      grid -y
270  grid -y                      grid +x
==== ============================ =======================

``Placement.(x, y, z)`` is always the minimum-corner cell of what the part covers, whatever
the rotation. ``local_to_cell`` turns a stud offset inside the part into a grid cell.

STAGE 4 ADDITION TO THE CONTRACT: sideways parts
A part with ``Placement.face`` other than "top" lies on its side, its top pointing out of
that face of the model, pushed onto the side stud of a brick directly behind it (see
``Placement`` in ``bricksnap/types.py``). This module says:

- ``Part.studs_side``: the side studs of a part, from ``studs_side`` in ``parts.json``, as
  (direction in the part's own axes, "+x", "-x", "+z" or "-z"; height of the stud's centre
  below the top of the body, in LDU). 87087 has one, "-z", 10 LDU below its top; 4733 has
  four.
- ``Catalog.side_stud_faces(p)``: the faces ("front", "right", "back", "left") of an upright
  placed part that carry a side stud, turned by ``rot`` exactly as the rotation table says.
  At rot 0 the part's -Z points along grid -y, so 87087's stud faces "front" at rot 0,
  "right" at 90, "back" at 180 and "left" at 270. A sideways part has none.
- ``Catalog.can_face_sideways(part_id)`` and ``sideways_parts()``: the detail parts that may
  lie on their side: one stud wide and deep, one plate thick, gripping studs underneath, with
  a body no bigger than its footprint (98138, 3070b and 6141 in the shipped table; not the
  clip 60897, whose clip sticks out).
- ``footprint`` of a sideways part is (1, 1, 3) and ``cells`` the column of three cells it
  keeps clear; ``stud_cells`` of a sideways part is empty (its stud, if it has one, points
  sideways and holds nothing).
- ``SIDE_STUD_BRICK`` (87087) is the brick the solver pins behind a sideways part;
  ``side_stud_brick(face, colour, x, y, z)`` is that brick at (x, y, z), turned so its side
  stud points to ``face``, and ``side_stud_exists(colour)`` whether it is made in a colour.
- ``brick_colour(colours)``: the colour the side-stud brick behind a sideways part takes from
  the three cells it covers (bottom first): the most common of them, the middle one on a tie.

STAGE 4 ADDITION TO THE CONTRACT: inverted slopes
An inverted slope (kind "slope_inverted": 3665b, 3660b, 4287c) is full at the top, with a stud
on every cell, and slanted underneath: its underside reaches the bottom of the part only under
its full row, the cells ``bottom_cells`` in ``parts.json`` name, and rises towards its thin
edge, on the side opposite ``low_side`` (``low_side`` is where its slanted face runs down
to, as for any slope; the thin edge points the other way).
- ``Part.bottom_cells``: those cells, as (dx, dz) offsets in the part's own axes.
- ``Catalog.grip_cells(p)``: the grid cells where a placed part grips the studs under it:
  every footprint cell of a part whose whole underside takes studs (``antistuds_bottom``),
  only the full row of an inverted slope, none for anything else (11477, a sideways part).
  ``grips_at(p, x, y)`` says the same of one cell. ``bricksnap.connect`` holds a part on a
  stud only where it grips.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from bricksnap.types import FACE_OUT, Placement

_HERE = Path(__file__).parent

TILING_KINDS = ("brick", "plate")
"""Kinds the layout solver fills volume with."""

DETAIL_KINDS = (
    "round_tile",
    "round_plate",
    "round_brick",
    "cone",
    "dish",
    "tile",
    "slope",
    "curved_slope",
    "detail",
)
"""Kinds a ``place_detail`` edit may put on free studs."""

SLOPE_KINDS = ("slope", "curved_slope", "slope_inverted")

_SIDES = {"+x": (1, 0), "-x": (-1, 0), "+z": (0, 1), "-z": (0, -1)}

SIDE_STUD_BRICK = "87087"
"""The brick with a stud on one side that holds a sideways part."""

SIDEWAYS_COLUMN = 3
"""Cells tall: the column a sideways part keeps clear (one brick course)."""

_FACE_OF = {step: face for face, step in FACE_OUT.items()}


def _turn(lx: int, lz: int, rot: int) -> tuple[int, int]:
    """A direction in a part's own axes (X, Z) as a grid direction (dx, dy) at ``rot``."""
    rot %= 360
    if rot == 0:
        return lx, lz
    if rot == 90:
        return -lz, lx
    if rot == 180:
        return -lx, -lz
    if rot == 270:
        return lz, -lx
    raise ValueError(f"rot must be 0, 90, 180 or 270, not {rot}")


def brick_colour(colours: Iterable[int]) -> int:
    """The colour of the side-stud brick behind a sideways part, from the colours of the
    three cells it covers, bottom first: the most common, the middle one on a tie."""
    cs = [int(c) for c in colours]
    best = max(cs, key=lambda c: cs.count(c))
    return best if cs.count(best) > 1 else cs[len(cs) // 2]


@dataclass(frozen=True)
class Part:
    id: str  # our key and the LDraw file stem, e.g. "3001"
    ldraw_file: str  # e.g. "3001.dat"
    bricklink_id: str
    name: str
    kind: str  # brick | plate | tile | slope | slope_inverted | round_brick | round_plate | ...
    sx: int  # studs along the part's X axis
    sz: int  # studs along the part's Z axis
    h: int  # height in plates (a brick is 3)
    studs_top: tuple[tuple[int, int], ...]  # (dx, dz) offsets inside the footprint that have a stud
    antistuds_bottom: bool  # the whole underside accepts studs
    colours: frozenset[int]  # LDraw colour codes this part really exists in
    body_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    body_max: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Bounding box of the part's body (studs excluded) in its own LDraw coordinates, in LDU.
    LDraw's Y points down, so ``body_min[1]`` is the TOP of the body. The LDraw origin is not
    at the same place in every part; use this box, not an assumption, to position a part."""
    slope: dict | None = None  # for slopes: {"low_side": "+x" | "-x" | "+z" | "-z", "angle_deg": n}
    studs_side: tuple[tuple[str, float], ...] = ()
    """Side studs: (direction in the part's own axes, height of the stud's centre below the top
    of the body in LDU), for example (("-z", 10.0),) for 87087."""
    bottom_cells: tuple[tuple[int, int], ...] = ()
    """(dx, dz) offsets inside the footprint where the underside reaches the bottom of the
    part (``bottom_cells`` in ``parts.json``): every cell for a plain part, only the full row
    of an inverted slope (see ``Catalog.grip_cells``)."""


@dataclass(frozen=True)
class Colour:
    code: int  # LDraw colour code
    name: str
    rgb: tuple[int, int, int]
    bricklink_id: int
    transparent: bool = False


class Catalog:
    def __init__(self, parts: Iterable[Part], colours: Iterable[Colour]) -> None:
        self.parts: dict[str, Part] = {p.id: p for p in parts}
        self.colours: dict[int, Colour] = {c.code: c for c in colours}

    # ---- geometry -------------------------------------------------------------------------

    def footprint(self, p: Placement) -> tuple[int, int, int]:
        """(w, d, h): cells covered along grid x, grid y and z. A sideways part covers the
        column of three cells it keeps clear: (1, 1, 3)."""
        part = self.parts[p.part]
        if p.face != "top":
            return 1, 1, SIDEWAYS_COLUMN
        if p.rot % 180 == 0:
            return part.sx, part.sz, part.h
        return part.sz, part.sx, part.h

    def cells(self, p: Placement) -> tuple[slice, slice, slice]:
        """Slices selecting every cell the part covers, for indexing an [x, y, z] array."""
        w, d, h = self.footprint(p)
        return slice(p.x, p.x + w), slice(p.y, p.y + d), slice(p.z, p.z + h)

    def local_to_cell(self, p: Placement, dx: int, dz: int) -> tuple[int, int]:
        """Grid (x, y) of the footprint cell at offset (dx, dz) in the part's own axes."""
        part = self.parts[p.part]
        rot = p.rot % 360
        if rot == 0:
            ox, oy = dx, dz
        elif rot == 90:
            ox, oy = part.sz - 1 - dz, dx
        elif rot == 180:
            ox, oy = part.sx - 1 - dx, part.sz - 1 - dz
        elif rot == 270:
            ox, oy = dz, part.sx - 1 - dx
        else:
            raise ValueError(f"rot must be 0, 90, 180 or 270, not {p.rot}")
        return p.x + ox, p.y + oy

    def stud_cells(self, p: Placement) -> list[tuple[int, int]]:
        """Grid (x, y) of every stud on top of the part. The studs are at z = p.z + h.
        A sideways part has none: its top points sideways."""
        part = self.parts[p.part]
        if p.face != "top":
            return []
        return [self.local_to_cell(p, dx, dz) for dx, dz in part.studs_top]

    def grip_cells(self, p: Placement) -> list[tuple[int, int]]:
        """Grid (x, y) of every cell where the part grips the studs under it, at z = p.z - 1.

        Every footprint cell of a part whose whole underside takes studs
        (``Part.antistuds_bottom``); for an inverted slope, only its ``bottom_cells`` (the full
        row, whose underside reaches the bottom of the part; the rest is cut away by the
        slant); none for any other part, and none for a sideways part.
        """
        part = self.parts[p.part]
        if p.face != "top":
            return []
        if part.antistuds_bottom:
            w, d, _ = self.footprint(p)
            return [(p.x + i, p.y + j) for i in range(w) for j in range(d)]
        if part.kind != "slope_inverted":
            return []
        return [self.local_to_cell(p, dx, dz) for dx, dz in part.bottom_cells]

    def grips_at(self, p: Placement, x: int, y: int) -> bool:
        """Whether the part grips a stud under grid cell (x, y) (see ``grip_cells``)."""
        part = self.parts[p.part]
        if p.face != "top":
            return False
        if part.antistuds_bottom:
            return True
        return part.kind == "slope_inverted" and (x, y) in self.grip_cells(p)

    def side_stud_faces(self, p: Placement) -> list[str]:
        """The faces ("front", "right", "back", "left") of an upright part that carry a side
        stud, turned by ``p.rot``; empty for a part with none, and for a sideways part."""
        part = self.parts[p.part]
        if p.face != "top":
            return []
        out = []
        for side, _ in part.studs_side:
            if side in _SIDES:
                face = _FACE_OF[_turn(*_SIDES[side], p.rot)]
                if face not in out:
                    out.append(face)
        return out

    def side_stud_height(self, part_id: str) -> float:
        """How far below the top of the body the centre of the part's side stud is, in LDU
        (10 for 87087)."""
        part = self.parts[part_id]
        return part.studs_side[0][1] if part.studs_side else 10.0

    def side_stud_brick(self, face: str, colour: int, x: int, y: int, z: int) -> Placement:
        """``SIDE_STUD_BRICK`` at (x, y, z), turned so its side stud points to ``face``."""
        for rot in (0, 90, 180, 270):
            p = Placement(SIDE_STUD_BRICK, int(colour), x, y, z, rot)
            if face in self.side_stud_faces(p):
                return p
        raise ValueError(f"{SIDE_STUD_BRICK} cannot be turned to face {face!r}")

    def side_stud_exists(self, colour: int) -> bool:
        """Whether the side-stud brick is made in this colour."""
        return self.exists(SIDE_STUD_BRICK, colour)

    def can_face_sideways(self, part_id: str) -> bool:
        """Whether a detail part may lie on its side on a side stud: one stud wide and deep,
        one plate thick, gripping studs underneath, its body no bigger than its footprint."""
        part = self.parts.get(part_id)
        if part is None or part.kind not in DETAIL_KINDS:
            return False
        if (part.sx, part.sz, part.h) != (1, 1, 1) or not part.antistuds_bottom:
            return False
        lo, hi = part.body_min, part.body_max
        return all(lo[i] >= -11.0 and hi[i] <= 11.0 for i in (0, 2))

    def sideways_parts(self) -> list[Part]:
        """Detail parts that may lie on their side (``can_face_sideways``), catalogue order."""
        return [p for p in self.detail_parts() if self.can_face_sideways(p.id)]

    def low_side(self, p: Placement) -> tuple[int, int] | None:
        """Grid direction (dx, dy) a slope descends towards as placed, or None for other parts.

        For example (0, -1) means the slanted face runs down towards the front (-y). The
        direction turns with ``Placement.rot`` exactly as the rotation table above says.
        """
        part = self.parts[p.part]
        if not part.slope or part.slope.get("low_side") not in _SIDES:
            return None
        lx, lz = _SIDES[part.slope["low_side"]]
        rot = p.rot % 360
        if rot == 0:
            return lx, lz
        if rot == 90:
            return -lz, lx
        if rot == 180:
            return -lx, -lz
        if rot == 270:
            return lz, -lx
        raise ValueError(f"rot must be 0, 90, 180 or 270, not {p.rot}")

    # ---- lookup ---------------------------------------------------------------------------

    def exists(self, part_id: str, colour: int) -> bool:
        """True if this part is really made in this colour."""
        part = self.parts.get(part_id)
        return part is not None and colour in part.colours

    def of_kind(self, kind: str) -> list[Part]:
        return [p for p in self.parts.values() if p.kind == kind]

    def detail_parts(self) -> list[Part]:
        """Parts a ``place_detail`` edit may use, in catalogue order."""
        return [p for p in self.parts.values() if p.kind in DETAIL_KINDS]

    def find(self, kind: str, w: int, d: int) -> tuple[Part, int] | None:
        """The part of this kind covering w x d cells, and the rot (0 or 90) that does it."""
        for part in self.parts.values():
            if part.kind != kind:
                continue
            if (part.sx, part.sz) == (w, d):
                return part, 0
            if (part.sz, part.sx) == (w, d):
                return part, 90
        return None

    def nearest_colour(
        self, rgb: Iterable[float], allowed: Iterable[int] | None = None, solid_only: bool = True
    ) -> int:
        """LDraw code of the catalogue colour that looks closest to an RGB value (0-255 each).

        Closeness is measured the way eyes judge it (the CIEDE2000 difference, with lightness
        counted half), not in raw RGB, so black snaps to Black rather than Dark Brown and a
        coral red to Red rather than a brown. On an exact tie the colour that comes first in
        the catalogue wins.
        """
        one = np.asarray([float(v) for v in rgb], dtype=np.float64).reshape(1, 3)
        return int(self.nearest_colours(one, allowed=allowed, solid_only=solid_only)[0])

    def nearest_colours(
        self,
        rgb: np.ndarray,
        allowed: Iterable[int] | None = None,
        solid_only: bool = True,
    ) -> np.ndarray:
        """``nearest_colour`` for many colours at once: (n, 3) RGB in, (n,) LDraw codes out."""
        pool = (
            list(self.colours.values()) if allowed is None else [self.colours[c] for c in allowed]
        )
        if solid_only:
            pool = [c for c in pool if not c.transparent]
        if not pool:
            raise ValueError("no colours to choose from")
        codes = np.asarray([c.code for c in pool], dtype=np.int64)
        palette = _rgb_to_lab(np.asarray([c.rgb for c in pool], dtype=np.float64))
        rgb = np.asarray(rgb, dtype=np.float64).reshape(-1, 3)
        out = np.empty(len(rgb), dtype=np.int64)
        shortlist = min(_SHORTLIST, len(pool))
        for start in range(0, len(rgb), _SNAP_CHUNK):
            lab = _rgb_to_lab(rgb[start : start + _SNAP_CHUNK])
            # The exact measure is costly, so it is only worked out for the few palette
            # colours that a cheaper, similar measure puts nearest. The winner is always
            # among those: a test compares this against measuring every colour.
            near = np.argpartition(_rough_difference(lab, palette), shortlist - 1, axis=1)
            near = np.sort(near[:, :shortlist], axis=1)  # catalogue order: first minimum wins
            d = _delta_e(lab[:, None, :], palette[near])
            best = near[np.arange(len(lab)), d.argmin(axis=1)]
            out[start : start + len(lab)] = codes[best]
        return out


_SNAP_CHUNK = 20_000
_SHORTLIST = 12
_K_LIGHTNESS = 2.0
_D65 = np.array([0.95047, 1.0, 1.08883])
_RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)


def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0-255, shape (n, 3)) to CIELAB (D65)."""
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 255.0) / 255.0
    linear = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = linear @ _RGB_TO_XYZ.T / _D65
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack(
        [116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1
    )


def _rough_difference(lab: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """A cheap stand-in for the colour difference (the older CIE94 form, squared), used only
    to shortlist palette colours: (n, 3) against (k, 3) gives (n, k)."""
    c1 = np.hypot(lab[:, 1], lab[:, 2])[:, None]
    c2 = np.hypot(palette[:, 1], palette[:, 2])[None, :]
    d_l = lab[:, None, 0] - palette[None, :, 0]
    d_a = lab[:, None, 1] - palette[None, :, 1]
    d_b = lab[:, None, 2] - palette[None, :, 2]
    d_c = c1 - c2
    d_h2 = np.maximum(d_a**2 + d_b**2 - d_c**2, 0.0)
    c_mean = (c1 + c2) / 2
    d_l = d_l / _K_LIGHTNESS
    return d_l**2 + (d_c / (1 + 0.045 * c_mean)) ** 2 + d_h2 / (1 + 0.015 * c_mean) ** 2


def _colour_difference(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 colour difference between every row of ``lab1`` (n, 3) and of ``lab2`` (k, 3)."""
    return _delta_e(lab1[:, None, :], lab2[None, :, :])


def _delta_e(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 colour difference between two arrays of CIELAB colours that broadcast
    against each other (last axis 3).

    The standard measure of how different two colours look, with lightness counted half
    (``_K_LIGHTNESS``; the 2:1:1 weighting the textile industry uses). Hue and saturation
    then decide before lightness does, which is how a person picks a brick colour: a coral
    red belongs with Red, not with a brown that happens to be equally light. Plain distance
    in CIELAB is not good enough here: it sends a strong blue to purple.
    """
    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    c_mean = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(c_mean**7 / (c_mean**7 + 25.0**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    grey = (c1p * c2p) == 0
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(grey, 0.0, dh)
    d_l, d_c = l2 - l1, c2p - c1p
    d_h = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh) / 2)
    l_mean, cp_mean = (l1 + l2) / 2, (c1p + c2p) / 2
    h_sum = h1p + h2p
    h_mean = np.where(
        np.abs(h1p - h2p) <= 180, h_sum / 2, np.where(h_sum < 360, h_sum + 360, h_sum - 360) / 2
    )
    h_mean = np.where(grey, h_sum, h_mean)
    t = (
        1
        - 0.17 * np.cos(np.radians(h_mean - 30))
        + 0.24 * np.cos(np.radians(2 * h_mean))
        + 0.32 * np.cos(np.radians(3 * h_mean + 6))
        - 0.20 * np.cos(np.radians(4 * h_mean - 63))
    )
    s_l = 1 + 0.015 * (l_mean - 50) ** 2 / np.sqrt(20 + (l_mean - 50) ** 2)
    s_c = 1 + 0.045 * cp_mean
    s_h = 1 + 0.015 * cp_mean * t
    r_c = 2 * np.sqrt(cp_mean**7 / (cp_mean**7 + 25.0**7))
    r_t = -r_c * np.sin(np.radians(60 * np.exp(-(((h_mean - 275) / 25) ** 2))))
    d_l = d_l / (_K_LIGHTNESS * s_l)
    return np.sqrt(d_l**2 + (d_c / s_c) ** 2 + (d_h / s_h) ** 2 + r_t * (d_c / s_c) * (d_h / s_h))


def _hex_to_rgb(text: str) -> tuple[int, int, int]:
    t = text.lstrip("#")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)


def load_catalog_from(parts_path: Path, colours_path: Path) -> Catalog:
    raw_colours = json.loads(colours_path.read_text(encoding="utf-8"))
    raw_parts = json.loads(parts_path.read_text(encoding="utf-8"))
    colours = [
        Colour(
            code=int(c["ldraw_code"]),
            name=str(c["name"]).replace("_", " "),
            rgb=_hex_to_rgb(c["rgb"]),
            bricklink_id=int(c["bricklink_id"]),
            transparent=bool(c.get("transparent", False)),
        )
        for c in raw_colours
    ]
    known = {c.code for c in colours}
    parts = []
    for p in raw_parts:
        sx, sz = int(p["sx"]), int(p["sz"])
        studs = p.get("studs_top", "all")
        if studs == "all":
            studs = [(dx, dz) for dx in range(sx) for dz in range(sz)]
        h = int(p["h_plates"])
        box = p.get("body_bbox_ldu")
        if box:
            body_min = (float(box["min"][0]), float(box["min"][1]), float(box["min"][2]))
            body_max = (float(box["max"][0]), float(box["max"][1]), float(box["max"][2]))
        else:  # a standard part: origin at the centre of the top face
            body_min = (-10.0 * sx, 0.0, -10.0 * sz)
            body_max = (10.0 * sx, 8.0 * h, 10.0 * sz)
        parts.append(
            Part(
                id=str(p["id"]),
                ldraw_file=p.get("ldraw_file", f"{p['id']}.dat"),
                bricklink_id=str(p.get("bricklink_id", p["id"])),
                name=" ".join(str(p["name"]).split()),
                kind=p["kind"],
                sx=sx,
                sz=sz,
                h=h,
                studs_top=tuple((int(a), int(b)) for a, b in studs),
                antistuds_bottom=bool(p.get("has_bottom_antistuds", True)),
                colours=frozenset(int(c) for c in p["colours"]) & known,
                body_min=body_min,
                body_max=body_max,
                slope=p.get("slope"),
                studs_side=tuple(
                    (str(sd["dir"]), float(sd.get("y_ldu", 10.0))) for sd in p.get("studs_side", [])
                ),
                bottom_cells=tuple((int(a), int(b)) for a, b in p.get("bottom_cells", [])),
            )
        )
    return Catalog(parts, colours)


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    """The catalogue shipped with BrickSnap. Cached; treat it as read-only."""
    return load_catalog_from(_HERE / "parts.json", _HERE / "colours.json")
