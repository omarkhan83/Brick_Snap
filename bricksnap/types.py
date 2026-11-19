"""Shared data shapes for BrickSnap. No logic beyond construction and (de)serialisation.

Every module talks to the others only through these types (see docs/ARCHITECTURE.md).
Only the lead's agent changes this file (see AGENTS.md).

Grid conventions
----------------
One cell is one stud wide (x), one stud deep (y) and one PLATE tall (z): 8 x 8 x 3.2 mm.
x runs left to right, y runs front to back (the object's front is at y = 0), z runs up from
the ground (z = 0 is the bottom layer). Arrays are indexed [x, y, z]. A brick is three cells
tall, a plate one.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

STUD_MM = 8.0
PLATE_MM = 3.2
CELL_MM = (STUD_MM, STUD_MM, PLATE_MM)
PLATES_PER_BRICK = 3
LDU_PER_STUD = 20
LDU_PER_PLATE = 8

EMPTY = -1
"""Value of ``Design.colors`` for a cell with nothing in it."""

FINISH_STUDS = 0
FINISH_SMOOTH = 1
FINISH_SLOPED = 2
FINISH_NAMES = {"studs": FINISH_STUDS, "smooth": FINISH_SMOOTH, "sloped": FINISH_SLOPED}
"""The words edit operations and messages use for ``Design.finish`` values."""

FACES = ("top", "front", "right", "back", "left")
"""Which way the top of a part points. "top" is upright, as almost every part is. The other
four are the picture views (``bricksnap.render``) in which the part's top is seen straight
on: "front" points to -y, "right" to +x, "back" to +y, "left" to -x."""
FACE_OUT = {"front": (0, -1), "right": (1, 0), "back": (0, 1), "left": (-1, 0)}
"""The (x, y) step from the model outwards for each sideways face."""

DEFAULT_COLOUR = 71
"""LDraw colour code used when a seed has no colour of its own (Light Bluish Gray)."""


def _triple(values) -> tuple[int, int, int]:
    a, b, c = (int(v) for v in values)
    return a, b, c


def write_text_atomic(path: str | Path, text: str) -> None:
    """Write a text file so that a reader never sees it half written.

    The viewer and the AI designer's tools read project files while other code rewrites
    them, so every project file is written to a temporary file and then moved into place.
    """
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class SeedError(ValueError):
    """The input model cannot be used. The message is written for a non-programmer."""


@dataclass
class Seed:
    """The input model after loading: oriented, scaled, and moved to the origin.

    ``vertices`` are millimetres at the final build size. z is up, the object's front faces
    -y, the model stands on z = 0, and in x and y it is centred in the smallest whole number
    of studs that holds it (so its minimum corner is less than half a stud from 0).
    """

    vertices: np.ndarray  # (n, 3) float64, millimetres
    faces: np.ndarray  # (m, 3) int64 indices into vertices
    face_colors: np.ndarray | None = None  # (m, 3) uint8 RGB, or None when the model has no colour
    source: str = ""  # original file name, for messages

    @property
    def extent_mm(self) -> np.ndarray:
        """Bounding-box size in millimetres, shape (3,)."""
        return self.vertices.max(axis=0) - self.vertices.min(axis=0)


def plain(part: Any) -> dict[str, Any]:
    """A Detail or Placement as a dict for files and fingerprints: ``asdict`` without
    ``face`` when the part is upright."""
    d = asdict(part)
    if d.get("face") == "top":
        del d["face"]
    return d


@dataclass
class Detail:
    """A small part standing on free studs of the Design (eyes, buttons, ear tips, lights).

    (x, y, z) is the minimum-corner cell of what the part covers, exactly as in
    ``Placement``; z is the level directly above the cells it stands on. The cells it covers
    are EMPTY in ``Design.colors``: a detail sits on the model, it is not part of the grid.
    """

    part: str  # catalogue id
    color: int  # LDraw colour code
    x: int
    y: int
    z: int
    rot: int = 0  # degrees, 0 / 90 / 180 / 270
    face: str = "top"  # one of FACES; see "Sideways parts" under Placement


@dataclass
class Design:
    """What the model should look like: a grid of coloured cells plus notes.

    This is the only thing the AI designer and chat edits change.

    ``skin`` lists the cells the model only partly covers: the conversion left them empty
    because the model fills less than half of each, but the model's surface does pass
    through them. Each holds the colour it would have had (EMPTY everywhere else). The
    make-buildable pass may fill one of them to hold a loose feature on, since that moves
    the outline by less than half a cell. Edits never change it, and a cell an edit has
    filled since is simply filled. A Design saved before skin existed loads with none.
    """

    colors: np.ndarray  # int16 [nx, ny, nz]; EMPTY or an LDraw colour code
    finish: np.ndarray | None = None  # uint8 [nx, ny, nz]; FINISH_* for the top of each cell
    seed_offset: tuple[int, int, int] = (0, 0, 0)
    """Cell at which the seed's own first cell sits. The grid is padded so edits have room
    to grow the shape; seed point p (mm) lies in cell floor(p / CELL_MM) + seed_offset. (The
    seed's minimum corner is up to half a stud inside that cell: see ``Seed``.)"""
    details: list[Detail] = field(default_factory=list)
    regions: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )  # name -> shape that defined it
    log: list[dict[str, Any]] = field(default_factory=list)  # every edit op applied, in order
    skin: np.ndarray | None = None  # int16 [nx, ny, nz]; EMPTY, or a partly covered cell's colour

    def __post_init__(self) -> None:
        self.colors = np.asarray(self.colors, dtype=np.int16)
        if self.colors.ndim != 3:
            raise ValueError("Design.colors must be a 3-D array indexed [x, y, z]")
        if self.finish is None:
            self.finish = np.zeros(self.colors.shape, dtype=np.uint8)
        else:
            self.finish = np.asarray(self.finish, dtype=np.uint8)
            if self.finish.shape != self.colors.shape:
                raise ValueError("Design.finish must have the same shape as Design.colors")
        if self.skin is None:
            self.skin = np.full(self.colors.shape, EMPTY, dtype=np.int16)
        else:
            self.skin = np.asarray(self.skin, dtype=np.int16)
            if self.skin.shape != self.colors.shape:
                raise ValueError("Design.skin must have the same shape as Design.colors")
        self.seed_offset = _triple(self.seed_offset)

    @property
    def shape(self) -> tuple[int, int, int]:
        nx, ny, nz = self.colors.shape
        return int(nx), int(ny), int(nz)

    @property
    def filled(self) -> np.ndarray:
        """Boolean array, True where a cell has something in it."""
        return self.colors != EMPTY

    def copy(self) -> Design:
        assert self.finish is not None and self.skin is not None
        return Design(
            colors=self.colors.copy(),
            finish=self.finish.copy(),
            skin=self.skin.copy(),
            seed_offset=self.seed_offset,
            details=[Detail(**asdict(d)) for d in self.details],
            regions=json.loads(json.dumps(self.regions)),
            log=json.loads(json.dumps(self.log)),
        )

    def fingerprint(self) -> str:
        """A short code that changes whenever anything a Build depends on changes.

        It covers the cells, their finish, the detail parts and the skin, not the edit log
        or the region names. A Design with no skin has the same fingerprint as before skin
        existed. A Build records the fingerprint of the Design it was made from
        (``Build.design_id``), which is how we tell whether a Build is up to date.
        """
        assert self.finish is not None
        h = hashlib.sha256()
        h.update(repr((self.shape, self.seed_offset)).encode())
        h.update(np.ascontiguousarray(self.colors).tobytes())
        h.update(np.ascontiguousarray(self.finish).tobytes())
        h.update(json.dumps([plain(d) for d in self.details], sort_keys=True).encode())
        assert self.skin is not None
        if (self.skin != EMPTY).any():
            h.update(b"skin")
            h.update(np.ascontiguousarray(self.skin).tobytes())
        return h.hexdigest()[:16]

    def save(self, npz_path: str | Path, json_path: str | Path | None = None) -> None:
        """Write the arrays to ``npz_path`` and, if given, the notes to ``json_path``."""
        assert self.finish is not None and self.skin is not None
        npz_path = Path(npz_path)
        # numpy adds ".npz" to a name that lacks it, so the temporary name must end in it
        tmp = npz_path.with_name(f".{npz_path.stem}.{os.getpid()}.tmp.npz")
        try:
            np.savez_compressed(
                tmp,
                colors=self.colors,
                finish=self.finish,
                skin=self.skin,
                seed_offset=np.asarray(self.seed_offset, dtype=np.int32),
            )
            os.replace(tmp, npz_path)
        finally:
            tmp.unlink(missing_ok=True)
        if json_path is not None:
            notes = {
                "details": [plain(d) for d in self.details],
                "regions": self.regions,
                "log": self.log,
            }
            write_text_atomic(json_path, json.dumps(notes, indent=1) + "\n")

    @classmethod
    def load(cls, npz_path: str | Path, json_path: str | Path | None = None) -> Design:
        with np.load(npz_path) as data:
            colors = data["colors"]
            finish = data["finish"]
            offset = _triple(data["seed_offset"])
            skin = data["skin"] if "skin" in data.files else None  # older files have none
        notes: dict[str, Any] = {}
        if json_path is not None and Path(json_path).exists():
            notes = json.loads(Path(json_path).read_text(encoding="utf-8"))
        return cls(
            colors=colors,
            finish=finish,
            skin=skin,
            seed_offset=offset,
            details=[Detail(**d) for d in notes.get("details", [])],
            regions=notes.get("regions", {}),
            log=notes.get("log", []),
        )


@dataclass(frozen=True)
class Placement:
    """One real part at a position in the grid.

    (x, y, z) is the part's minimum-corner cell, whatever the rotation. With ``rot`` 0 or
    180 the part's LDraw X axis lies along grid x, so it covers ``sx`` cells in x and ``sz``
    cells in y; with ``rot`` 90 or 270 it covers ``sz`` cells in x and ``sx`` cells in y. It
    is ``h`` cells tall. The rotation table is in ``bricksnap/catalog/__init__.py``. Use
    ``Catalog.footprint`` to get (w, d, h); do not recompute it by hand.

    Sideways parts. With ``face`` other than "top" the part is turned so that its top points
    out of that face of the model, and it is pushed onto the side stud of a brick that has
    one (kind "side_stud") directly behind it. Only one-stud parts one plate thick can be
    sideways, and their ``rot`` is 0. (x, y, z) is then the lowest cell of the column of
    three cells it keeps clear: the three cells in front of the side-stud brick, so z is a
    multiple of 3 and the brick is at (x, y) minus ``FACE_OUT[face]``, same z.
    ``Catalog.footprint`` returns (1, 1, 3) for it. A part with face "top" is written to
    files without the field, so files and fingerprints from before sideways parts existed
    stay exactly as they were.
    """

    part: str  # catalogue id, e.g. "3001"
    color: int  # LDraw colour code
    x: int
    y: int
    z: int
    rot: int = 0  # degrees about the vertical axis: 0, 90, 180 or 270
    step: int = 0  # 1-based building step; 0 means not yet assigned
    face: str = "top"  # one of FACES


@dataclass
class Report:
    """The result of checking a Build. ``text`` says everything in plain words."""

    ok: bool = False
    part_count: int = 0
    collisions: list[tuple[int, int]] = field(default_factory=list)  # pairs of part indices
    out_of_bounds: list[int] = field(default_factory=list)  # part indices
    unknown_parts: list[int] = field(default_factory=list)  # part or colour not in the catalogue
    components: int = 0  # number of separate connected pieces
    loose: list[int] = field(default_factory=list)  # parts not in the largest grounded piece
    grounded: bool = False  # the main piece touches z = 0
    stands: bool = False  # centre of mass is over the ground footprint
    centre_of_mass: tuple[float, float, float] = (0.0, 0.0, 0.0)  # in cells
    weak_spots: list[str] = field(default_factory=list)  # plain-language, with coordinates
    text: str = ""

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["collisions"] = [list(p) for p in self.collisions]
        d["centre_of_mass"] = list(self.centre_of_mass)
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Report:
        d = dict(d)
        d["collisions"] = [tuple(p) for p in d.get("collisions", [])]
        d["centre_of_mass"] = tuple(d.get("centre_of_mass", (0.0, 0.0, 0.0)))
        return cls(**d)


@dataclass
class Build:
    """How the model is made: real parts at real positions, in steps.

    Only the layout solver and the finishing pass create or change a Build.
    """

    shape: tuple[int, int, int]  # grid size (nx, ny, nz) the parts live in
    parts: list[Placement] = field(default_factory=list)
    report: Report | None = None
    design_id: str = ""
    """``Design.fingerprint()`` of the Design this was built from; "" when not recorded."""
    notes: list[str] = field(default_factory=list)
    """What the make-buildable and finishing passes did or could not do, in plain words."""

    def to_json(self) -> dict[str, Any]:
        return {
            "shape": list(self.shape),
            "design_id": self.design_id,
            "notes": list(self.notes),
            "parts": [plain(p) for p in self.parts],
            "report": self.report.to_json() if self.report else None,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Build:
        return cls(
            shape=_triple(d["shape"]),
            parts=[Placement(**p) for p in d["parts"]],
            report=Report.from_json(d["report"]) if d.get("report") else None,
            design_id=str(d.get("design_id", "")),
            notes=[str(n) for n in d.get("notes", [])],
        )

    def save(self, path: str | Path) -> None:
        write_text_atomic(path, json.dumps(self.to_json(), indent=1) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> Build:
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
