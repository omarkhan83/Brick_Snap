"""Edit operations on a Design. This is the only way the AI designer or a person changes it.

CONTRACT (tests go in tests/test_design.py)

One operation is a small JSON object. Stage 1 has three operations and two shapes:

    {"op": "add",    "shape": {...}, "color": 4}   fill EMPTY cells inside the shape
    {"op": "remove", "shape": {...}}               empty the filled cells inside the shape
    {"op": "paint",  "shape": {...}, "color": 4}   recolour the filled cells inside the shape

    {"type": "box", "min": [x, y, z], "max": [x, y, z]}             both corners inclusive
    {"type": "ellipsoid", "center": [x, y, z], "radius": [rx, ry, rz]}

Coordinates are grid cells: x and y count studs, z counts plates. Box corners are integers.
Ellipsoid centre and radius may be fractional; a cell with integer index (x, y, z) is inside
when ((x-cx)/rx)^2 + ((y-cy)/ry)^2 + ((z-cz)/rz)^2 <= 1. Each radius must be at least 0.5.

``apply_ops(design, ops, catalog) -> list[OpResult]``
- Operations are applied in order. Each is either applied (it changes ``design`` in place
  and is appended to ``design.log`` exactly as given) or rejected (nothing changes). A
  rejected operation does not stop later ones.
- Shapes are clipped to the grid. A shape that lies entirely outside it is rejected, and the
  message states the valid ranges (0..nx-1, 0..ny-1, 0..nz-1).
- ``color`` must be a colour code in the catalogue; otherwise the operation is rejected and
  the message lists the valid codes with their names.
- An unknown ``op`` or shape ``type``, a missing field, a wrong type or length, a non-finite
  number, or a box whose min exceeds its max is rejected with a message that says exactly
  what to fix.
- A ``remove`` that would leave the Design completely empty is rejected.
- An operation that would change no cells is reported with ``applied=False`` and a message
  saying why (for example "every cell in that box is already empty") and is not logged.
- Messages are read by an AI model: be specific, include the numbers, never a traceback.
- ``OpResult.cells_changed`` is the number of cells whose colour changed.

``replay(base, log, catalog) -> Design`` returns a copy of ``base`` with every operation in
``log`` applied; replaying a Design's log on its base reproduces it exactly.

``shape_mask(shape, grid_shape) -> bool array`` is public so later stages and the designer
tools can reuse it. It raises ValueError (with the same clear messages) on a malformed shape.

``OP_SCHEMA`` is a JSON Schema for one operation, used in the designer's tool definition.
Keep it and the validation in ``apply_ops`` in agreement.

STAGE 2 ADDITIONS TO THE CONTRACT

Three more operations and one more option. Everything above still holds.

    {"op": "set_finish", "shape": {...}, "finish": "smooth"}
        What the top of the filled cells inside the shape should be: "studs" (the default),
        "smooth" (tiles) or "sloped" (a slope part where the surface steps down). The words
        are ``bricksnap.types.FINISH_NAMES``. It only matters on cells with nothing above
        them, but it may be set on any filled cell. ``cells_changed`` is the number of cells
        whose finish changed; if none would change the operation is not applied and the
        message says why.

    {"op": "place_detail", "part": "98138", "color": 0, "at": [x, y, z], "rot": 0}
        Stand a small part on free studs. ``at`` is the minimum-corner cell of what the part
        covers (as in ``Placement``), so z is the level directly above the cells it stands
        on. ``rot`` (0, 90, 180 or 270; default 0) turns it as the table in
        ``bricksnap/catalog/__init__.py`` says; for a slope the message of a successful
        placement says which way its slanted face runs down (``Catalog.low_side``).
        Rejected, with a message that says exactly what to fix, when:
        - the part is not one of ``Catalog.detail_parts()`` (list the ids and names);
        - the part is not made in that colour (list the colours it is made in);
        - a cell it would cover is outside the grid, is filled, or is taken by another
          detail (say which cell, and that a detail stands in empty cells);
        - a cell of its bottom layer has no filled cell directly below it (say which).
        Applied: appended to ``design.details``; ``cells_changed`` is 0 and
        ``OpResult.applied`` is True.

    {"op": "remove_detail", "at": [x, y, z]}
        Removes the detail that covers that cell. Rejected if there is none there.

    "mirror": true
        Optional on every operation. The operation is also applied to the mirror image
        across the model's left-right middle, the plane x = nx / 2 (voxelize centres the
        seed there), so cell x maps to nx - 1 - x. For add, remove, paint and set_finish the
        shape and its mirror image are applied as one operation (a cell in both counts
        once). For place_detail a second detail is placed at the mirrored position, turned
        so that it is the mirror image (a slope facing +x becomes one facing -x); if the two
        would overlap, or the detail lies on the middle, only one is placed. Both must be
        valid or neither is placed. For remove_detail both are removed (at least one must
        exist). The log keeps the operation as given, with its "mirror" field.

Details follow the grid, so they never dangle:
- ``add`` that fills a cell a detail stands in removes that detail;
- ``remove`` that empties a cell directly below a detail removes that detail.
The operation's message says so ("this also removed the Black Tile, Round 1 x 1 at x=…").
``replay`` reproduces details exactly, like everything else.

``OP_SCHEMA`` covers the new operations and the "mirror" field and stays self-contained.
The ``part`` enum lists ``Catalog.detail_parts()`` ids; put each part's name and size in the
description so the model can choose.

Implementation notes
--------------------
- Validation is strict and mirrors ``OP_SCHEMA``: unknown fields are rejected (with a "did you
  mean" hint for near misses such as "colour" or "centre"), and ``remove`` takes no
  ``color``. Whole numbers may be written as ``3`` or ``3.0`` (JSON Schema's "integer" allows
  both); booleans are never numbers.
- ``OP_SCHEMA`` is self-contained (no ``$ref``) so it can be embedded anywhere inside a tool's
  input schema. Its colour ``enum`` lists the shipped catalogue's codes; ``apply_ops`` checks
  against the catalogue it is given.
- The ellipsoid test allows a tolerance of 1e-9 so that cells exactly on the surface stay
  inside despite floating-point rounding (for example centre 1.4, radius 0.6, cell 2).
- A shape lying entirely outside the grid gives an all-False ``shape_mask`` (not an error);
  ``apply_ops`` rejects it with the valid ranges. This includes an ellipsoid whose bounding
  box overlaps the grid but which itself misses it (a ball just beyond a corner or edge).
- Whole numbers of 10**15 or more are shown in messages in scientific notation ("1.23e+29").
  A box corner with more digits than Python will write as text (4300 by default) is
  rejected as far too large, because the log could not be saved with it.
- Cells that are added or removed get the default finish (studs); ``paint`` keeps finishes.
- ``design.log`` receives a plain-JSON copy of each applied operation (same keys and values;
  tuples become lists and numpy numbers become Python numbers) so the log always saves.
- ``validate_op(op, catalog)`` is exposed for tools that want to check an operation without
  applying it; it raises ValueError with the same message ``apply_ops`` would report.
- Messages do not name the operation's position; ``OpResult.index`` carries it.
- ``replay`` raises ValueError if an operation in the log cannot be applied to the base, since
  that means the log does not belong to that base.

Stage 2 implementation notes
- ``OPS`` lists every operation, ``SHAPE_OPS`` the four that take a shape, ``ROTATIONS`` the
  allowed ``rot`` values. "rot" and "mirror" are the only optional fields; an unknown field
  message names the required fields and then the optional ones. Hints also catch common
  other words ("rotation" for "rot", "position" for "at", "symmetric" for "mirror", "tiles"
  for "smooth", the op "mirror"), and a part id written as a number is pointed back to text.
- ``set_finish`` changes only ``design.finish``. Its message also says how many of the
  changed cells have nothing directly above them (where the finish will show), so the model
  learns when it marked buried cells.
- "mirror" on a shape operation builds the shape's mask on the whole grid and ORs in the mask
  flipped along x. The grid is symmetric under the mirror, so this equals clipping the
  mirrored shape. The message names the mirrored shape ("and its mirror image, the box
  [6, 1, 3]..[7, 2, 4]") or says the shape is its own mirror image. Without "mirror" the
  cells, counts and messages are exactly those of stage 1.
- The mirrored detail is found by trying the four rotations at the mirrored minimum corner
  and keeping one whose cells (``Catalog.cells``) are the mirror image of the first
  detail's cells and whose ``Catalog.low_side`` is mirrored (dx negated). One whose
  ``Catalog.stud_cells`` are also mirrored is preferred; among equals the first detail's
  own rot wins (so a symmetric part keeps its rot), then the lowest rot. The exception is a
  part whose body (``Part.body_min``/``body_max``) reaches more than 1 LDU past its
  footprint along its own Z, such as the clip of 60897: for it the turn (360 - rot) % 360
  wins, because every shipped detail part is the same on both sides of its own Z axis, so
  that turn is its mirror image (the clip points the other way along x). A part lopsided
  along its own X could not be mirrored by any turn; none is shipped. If the two would
  share any cell (including a detail on the middle) only the first is placed and the
  message says so, with the x that would centre it when one exists (after removing the
  first). If no rotation is a mirror image the operation is rejected; no part in the
  shipped catalogue does that.
- For ``place_detail`` a missing, unknown or malformed colour lists only the colours that
  part is made in, not the whole catalogue. An unknown op naming a detail and a removing
  verb (delete, erase, clear, unplace) is pointed to "remove_detail".
- A rejected ``place_detail`` adds, when the top of the model under the part is flat and
  the part would fit there, the ``"at"`` that would work ("so "at": [1, 0, 3] would fit"),
  or says that the top under it is not flat.
- Dangling details: after ``add``, a detail goes when any cell it covers was just filled;
  after ``remove``, when any cell directly below its bottom layer was just emptied. Only
  cells the operation changed are looked at, so a detail that was already odd (an unknown
  part id loaded from a file) is left alone. ``paint`` and ``set_finish`` never remove
  details.
- ``remove_detail`` removes the first detail in ``design.details`` that covers the cell.
  When nothing is there, the message lists up to 12 details with the cells they cover.
- Detail names in messages are "<colour name> <part name> (<part id>)", positions are
  minimum corners written "x=…, y=…, z=…", and spans "x=3..4".
- ``OP_SCHEMA`` gives the full shape and colour descriptions only in "add"; "remove",
  "paint", "set_finish" and "place_detail" carry the same rules without descriptions. Each
  operation's "mirror" is a bare boolean; the top-level description explains it once. The
  "part" description lists every detail part with its size along x by y at rot 0 and its
  height, and the "rot" description says which way a slope runs down at each turn (both
  are worked out from the catalogue). The schema cannot say which colours a part is made in;
  ``apply_ops`` rejects a pair that does not exist and lists the colours that do.

STAGE 4 ADDITION TO THE CONTRACT: sideways parts
``place_detail`` takes one more optional field, ``"face"``: "top" (the default, everything
above unchanged), or "front", "right", "back" or "left" (``bricksnap.types.FACES``). With a
face the part lies flat against that face of the model, its top pointing outwards, pushed
onto the side stud of a brick (87087) that the solver puts directly behind it:

    {"op": "place_detail", "part": "98138", "color": 0, "at": [3, 0, 9], "face": "front"}

``at`` is then the lowest cell of the column of three empty cells the part keeps clear,
and the three cells directly behind that column (one cell further in, against
``FACE_OUT[face]``) are the brick's. Rejected, with a message saying what would work, when:
- the part may not face sideways (``Catalog.can_face_sideways``: a one-stud, one-plate
  detail; list the parts that may), or ``rot`` is not 0 (turning a one-stud part about its
  stud changes nothing);
- z is not a multiple of 3 (the side-stud brick sits in a brick course; name the two nearest
  that are);
- a cell of the column is outside the grid, filled, or taken by another detail;
- a cell behind the column is outside the grid or empty (say which cells are missing);
- the side-stud brick is not made in the colour it would take from the cells behind
  (``catalog.brick_colour``; say which colours it is made in);
- the column is not open to the outside (a hollow inside the model);
- the three cells behind are not one colour (name them, and give the paint op that would
  make them the colour the brick would take);
- the brick would be held by nothing: no filled cell other than another sideways detail's
  brick lies directly above or below the run of such bricks it would be in
  (``buildable.side_brick_held``);
- another sideways detail is already held by the same brick.
An upright detail is now also rejected when a cell it covers is not open to the outside.
The success message names the colour of the brick behind, which shows around the edges of
a round part.
A rejection adds, where one exists, the nearest ``"at"`` along that line or at the nearest
brick course that would work. Applied: appended to ``design.details`` with its ``face``.

- "mirror": true on a sideways detail places its mirror image across x = nx / 2 with the
  face mirrored: front and back stay, left and right swap; the same "only one when they
  overlap" and "both or neither" rules hold.
- Dangling: after ``add``, a sideways detail goes when a cell of its column is now filled;
  after ``remove``, when a cell behind its column is now empty.
- ``remove_detail`` finds a sideways detail by any cell of its column. Messages name a
  sideways detail with its face ("... at x=3, y=0, z=9, on the front face").
- ``OP_SCHEMA`` gains the "face" property of place_detail, with its rule in a short
  description; unknown-field messages list the optional fields "rot", "face" and "mirror".
"""

from __future__ import annotations

import difflib
import json
import math
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np

from bricksnap.buildable import outside_air, side_brick_held
from bricksnap.catalog import Catalog, Part, brick_colour, load_catalog
from bricksnap.types import (
    EMPTY,
    FACE_OUT,
    FACES,
    FINISH_NAMES,
    FINISH_STUDS,
    Design,
    Detail,
    Placement,
)

OPS = ("add", "remove", "paint", "set_finish", "place_detail", "remove_detail")
SHAPE_OPS = ("add", "remove", "paint", "set_finish")
"""Operations that act on the cells inside a shape."""
SHAPE_TYPES = ("box", "ellipsoid")
ROTATIONS = (0, 90, 180, 270)
MIN_RADIUS = 0.5
_EPS = 1e-9
_AXES = ("x", "y", "z")

_OP_FIELDS = {
    "add": ("op", "shape", "color", "mirror"),
    "remove": ("op", "shape", "mirror"),
    "paint": ("op", "shape", "color", "mirror"),
    "set_finish": ("op", "shape", "finish", "mirror"),
    "place_detail": ("op", "part", "color", "at", "rot", "face", "mirror"),
    "remove_detail": ("op", "at", "mirror"),
}
_OPTIONAL_FIELDS = ("rot", "face", "mirror")
_SHAPE_FIELDS = {
    "box": ("type", "min", "max"),
    "ellipsoid": ("type", "center", "radius"),
}
# Field names a writer may reach for instead of ours; used only for "did you mean" hints.
_FIELD_SYNONYMS = {
    "rotation": "rot",
    "rotate": "rot",
    "angle": "rot",
    "position": "at",
    "pos": "at",
    "cell": "at",
    "location": "at",
    "where": "at",
    "symmetric": "mirror",
    "mirrored": "mirror",
    "symmetry": "mirror",
    "part_id": "part",
    "id": "part",
    "detail": "part",
    "side": "face",
    "facing": "face",
    "direction": "face",
    "orientation": "face",
}
_FACE_SYNONYMS = {
    "up": "top",
    "upright": "top",
    "forward": "front",
    "-y": "front",
    "+y": "back",
    "+x": "right",
    "-x": "left",
    "rear": "back",
}
_FACE_MIRROR = {"top": "top", "front": "front", "back": "back", "left": "right", "right": "left"}
_FINISH_SYNONYMS = {
    "tile": "smooth",
    "tiles": "smooth",
    "tiled": "smooth",
    "flat": "smooth",
    "slope": "sloped",
    "slopes": "sloped",
    "stud": "studs",
    "studded": "studs",
}
_FINISH_MEANING = {
    "studs": "plain studs on top",
    "smooth": "tiles on top",
    "sloped": "a slope part where the surface steps down",
}
_FINISH_HELP = (
    '"studs" (the default), "smooth" (tiles on top) or "sloped" (a slope part where the '
    "surface steps down)"
)
_OP_HELP = (
    '"add" (fill empty cells), "remove" (empty filled cells), "paint" (recolour filled cells), '
    '"set_finish" (studs, smooth or sloped tops), "place_detail" (stand a small part on the '
    'model) or "remove_detail" (take one off)'
)
_DETAIL_EXAMPLE = '{"op": "place_detail", "part": "98138", "color": 0, "at": [3, 0, 9]}'
_MIRROR_HELP = (
    '"mirror" is not an operation: add "mirror": true to any operation to do the same to '
    "the mirror image across the left-right middle as well."
)
_DIRECTIONS = {
    (0, -1): "the front (-y)",
    (0, 1): "the back (+y)",
    (1, 0): "the right (+x)",
    (-1, 0): "the left (-x)",
}
_BOX_EXAMPLE = '{"type": "box", "min": [0, 0, 0], "max": [3, 3, 2]}'
_ELLIPSOID_EXAMPLE = '{"type": "ellipsoid", "center": [4, 4, 6], "radius": [2, 2, 3]}'
_SHAPE_HELP = (
    f'"box" (for example {_BOX_EXAMPLE}) or "ellipsoid" (for example {_ELLIPSOID_EXAMPLE})'
)


# ---- the schema ---------------------------------------------------------------------------


def _build_schema() -> dict[str, Any]:
    catalog = load_catalog()
    codes = sorted(catalog.colours)
    names = ", ".join(f"{c} {catalog.colours[c].name}" for c in codes)

    def triple(item: dict[str, Any], description: str) -> dict[str, Any]:
        return {
            "type": "array",
            "items": item,
            "minItems": 3,
            "maxItems": 3,
            "description": description,
        }

    box = {
        "type": "object",
        "description": "Every cell from min to max, both corners included.",
        "properties": {
            "type": {"const": "box"},
            "min": triple(
                {"type": "integer"}, "Lowest corner [x, y, z] in whole cells (inclusive)."
            ),
            "max": triple(
                {"type": "integer"},
                "Highest corner [x, y, z] in whole cells (inclusive). Each value must be at "
                "least the matching min.",
            ),
        },
        "required": ["type", "min", "max"],
        "additionalProperties": False,
    }
    ellipsoid = {
        "type": "object",
        "description": (
            "Cells (x, y, z) with ((x-cx)/rx)^2 + ((y-cy)/ry)^2 + ((z-cz)/rz)^2 <= 1. "
            "Centre and radius may be fractional. Remember z counts plates: a sphere that "
            "looks round needs rz about 2.5 times rx."
        ),
        "properties": {
            "type": {"const": "ellipsoid"},
            "center": triple({"type": "number"}, "Centre [cx, cy, cz] in cells."),
            "radius": triple(
                {"type": "number", "minimum": MIN_RADIUS},
                "Radius [rx, ry, rz] in cells, each at least 0.5.",
            ),
        },
        "required": ["type", "center", "radius"],
        "additionalProperties": False,
    }
    shape = {
        "description": (
            "The cells the operation acts on. x and y count studs, z counts plates "
            "(a brick is 3 plates); z = 0 is the ground and the front is at y = 0. "
            "Parts of the shape outside the grid are ignored."
        ),
        "anyOf": [box, ellipsoid],
    }
    color = {
        "type": "integer",
        "enum": codes,
        "description": f"LDraw colour code from the parts table: {names}.",
    }
    # The full descriptions appear once (in "add"); later copies carry only the rules, to
    # keep the schema small, since it is sent to the model with every call.
    same_shape = {**_bare(shape), "description": "A shape, as for add."}
    same_color = {**_bare(color), "description": "A colour code, as for add."}
    mirror = {"type": "boolean"}

    def operation(name: str, description: str, props: dict[str, Any]) -> dict[str, Any]:
        props = {"op": {"const": name}, **props, "mirror": mirror}
        return {
            "type": "object",
            "description": description,
            "properties": props,
            "required": [f for f in _OP_FIELDS[name] if f not in _OPTIONAL_FIELDS],
            "additionalProperties": False,
        }

    details = catalog.detail_parts()
    slope = next((p for p in details if p.slope), None)
    turns = ""
    if slope is not None:
        ways = [
            _direction_word(catalog.low_side(Placement(slope.id, 0, 0, 0, 0, r))) for r in ROTATIONS
        ]
        turns = (
            f" A slope that runs down towards {ways[0]} at rot 0 runs down towards {ways[1]} "
            f"at 90, {ways[2]} at 180 and {ways[3]} at 270."
        )
    part = {
        "type": "string",
        "enum": [p.id for p in details],
        "description": "Detail part id. The detail parts " + _parts_text(catalog),
    }
    at = triple(
        {"type": "integer"},
        "Minimum-corner cell [x, y, z] the part covers; z is the level directly above the "
        "filled cells it stands on.",
    )
    rot = {
        "type": "integer",
        "enum": list(ROTATIONS),
        "description": "Quarter turns in degrees; 0 if left out." + turns,
    }
    sideways = ", ".join(p.id for p in catalog.sideways_parts())
    face = {
        "type": "string",
        "enum": list(FACES),
        "description": (
            '"top" if left out: the part stands on studs. "front", "right", "back" or "left": '
            "it lies flat against that face of the model, held by a side stud (one-stud, "
            f'one-plate parts only: {sideways}; rot 0). Then "at" is the lowest of the '
            "three empty cells in front of the face, z is a multiple of 3, and the three "
            "cells behind them must be filled."
        ),
    }
    finish = {
        "type": "string",
        "enum": list(FINISH_NAMES),
        "description": (
            "studs: the default. smooth: tiles, no studs. sloped: a slope part where the "
            "surface steps down beside the cell. It shows only on cells with nothing above."
        ),
    }

    return {
        "title": "Edit operation",
        "description": (
            "One edit to the Design grid. add fills empty cells, remove empties filled cells, "
            "paint recolours filled cells, set_finish says what the tops of filled cells "
            "should be, place_detail stands a small part on free studs, remove_detail takes "
            'one off. Any operation may add "mirror": true to do the same to the mirror image '
            "across the left-right middle as well (cell x becomes nx-1-x)."
        ),
        "type": "object",
        "required": ["op"],
        "anyOf": [
            operation(
                "add",
                "Fill the EMPTY cells inside the shape with a colour.",
                {"shape": shape, "color": color},
            ),
            operation("remove", "Empty the filled cells inside the shape.", {"shape": same_shape}),
            operation(
                "paint",
                "Recolour the filled cells inside the shape.",
                {"shape": same_shape, "color": same_color},
            ),
            operation(
                "set_finish",
                "Set what the top of the filled cells inside the shape should be.",
                {"shape": same_shape, "finish": finish},
            ),
            operation(
                "place_detail",
                "Stand a small part in empty cells directly on top of filled cells. The part "
                "must be made in the colour.",
                {"part": part, "color": same_color, "at": at, "rot": rot, "face": face},
            ),
            operation(
                "remove_detail",
                "Remove the detail part that covers a cell.",
                {"at": {**_bare(at), "description": "Any cell the detail covers."}},
            ),
        ],
    }


def _bare(schema: Any) -> Any:
    """A copy of a schema without its descriptions."""
    if isinstance(schema, dict):
        return {k: _bare(v) for k, v in schema.items() if k != "description"}
    if isinstance(schema, list):
        return [_bare(v) for v in schema]
    return schema


def _direction_word(direction: tuple[int, int] | None) -> str:
    if direction is None:
        return "nowhere"
    return _DIRECTIONS.get(direction, f"({direction[0]}, {direction[1]})")


def _rot0_down(catalog: Catalog, part: Part) -> tuple[int, int] | None:
    return catalog.low_side(Placement(part.id, 0, 0, 0, 0, 0))


def _common_down(catalog: Catalog, parts: list[Part]) -> tuple[int, int] | None:
    """The direction every slope among ``parts`` runs down towards at rot 0, if they agree."""
    ways = {_rot0_down(catalog, p) for p in parts if p.slope}
    ways.discard(None)
    return ways.pop() if len(ways) == 1 else None


def _part_line(catalog: Catalog, part: Part, common_down: tuple[int, int] | None = None) -> str:
    """'98138 Tile 1 x 1 Round with Groove (1x1, 1 plate)', for lists the model reads.

    The size is cells along x by y at rot 0. A slope says which way it runs down at rot 0,
    unless that is ``common_down`` (said once for the whole list).
    """
    plates = f"{part.h} plate{'s' if part.h != 1 else ''}"
    extra = ""
    if part.slope:
        down = _rot0_down(catalog, part)
        extra = ", slope"
        if down != common_down:
            extra = f", slope down towards {_direction_word(down)} at rot 0"
    return f"{part.id} {part.name} ({part.sx}x{part.sz}, {plates}{extra})"


def _parts_text(catalog: Catalog) -> str:
    """Every detail part, with what the sizes mean, for the schema and for messages."""
    details = catalog.detail_parts()
    common = _common_down(catalog, details)
    slopes = f"; slopes run down towards {_direction_word(common)} at rot 0" if common else ""
    lines = "; ".join(_part_line(catalog, p, common) for p in details)
    return f"(size in cells along x by y at rot 0, then height in plates{slopes}): {lines}."


OP_SCHEMA: dict[str, Any] = _build_schema()


@dataclass
class OpResult:
    index: int  # position of the operation in the list that was passed in
    op: str  # the operation name as given ("" if missing)
    applied: bool
    cells_changed: int
    message: str


class _OpError(ValueError):
    """A problem with an operation, worded for the model or person who wrote it."""


# ---- formatting helpers -------------------------------------------------------------------


_LONG_INT = 10**15  # whole numbers this large or larger are shown in scientific notation
_BIG_MARK = "\x00"


def _int_text(n: int) -> str:
    """``n`` in full, or as "1.23e+29" when it is long (never fails on gigantic integers)."""
    if -_LONG_INT < n < _LONG_INT:
        return str(n)
    # Decimal converts without Python's limit on turning long integers into text.
    mantissa, exponent = format(Decimal(n), ".3g").split("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{exponent}"


def _tame(value: Any) -> Any:
    """``value`` with long integers swapped for marked text, so it can be shown safely."""
    if isinstance(value, dict):
        return {_tame(k): _tame(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_tame(v) for v in value]
    if isinstance(value, int | np.integer) and not isinstance(value, bool):
        n = int(value)
        if not -_LONG_INT < n < _LONG_INT:
            return f"{_BIG_MARK}{_int_text(n)}{_BIG_MARK}"
    return value


def _show(value: Any, limit: int = 60) -> str:
    """A short rendering of a value as the writer of the JSON would recognise it."""
    try:
        tamed = _tame(value)
        try:
            # ensure_ascii=False keeps letters such as "ñ" as written; control characters,
            # the long-integer marker among them, are still escaped.
            text = json.dumps(tamed, default=repr, allow_nan=True, ensure_ascii=False)
            # Long integers were marked as text; show them as bare numbers again.
            text = re.sub(r'"\\u0000([^"\\]*)\\u0000"', r"\1", text)
        except (TypeError, ValueError):
            text = repr(tamed).replace(_BIG_MARK, "")
    except RecursionError:
        kind = {dict: "an object", list: "a list", tuple: "a list"}.get(type(value), "a value")
        text = f"{kind} nested too deeply to show"
    if len(text) <= limit:
        return text
    # Do not leave half an escape such as "\u00" or a lone "\" at the cut.
    cut = re.sub(
        r"(?<!\\)((?:\\\\)*)\\(?:u[0-9a-fA-F]{0,3}|x[0-9a-fA-F]?)?$", r"\1", text[: limit - 3]
    )
    return cut + "..."


def _num(v: float | int) -> str:
    if isinstance(v, int | np.integer):
        return _int_text(int(v))
    f = float(v)
    return str(int(f)) if f.is_integer() and abs(f) < 1e15 else repr(f)


def _vec(values: tuple | list) -> str:
    return "[" + ", ".join(_num(v) for v in values) + "]"


def _ranges(grid_shape: tuple[int, int, int]) -> str:
    nx, ny, nz = grid_shape
    return f"x 0..{nx - 1}, y 0..{ny - 1}, z 0..{nz - 1}"


def _hint(name: str, choices: tuple[str, ...]) -> str:
    match = difflib.get_close_matches(name.lower(), choices, n=1, cutoff=0.6)
    return f' Did you mean "{match[0]}"?' if match else ""


def _colour_list(catalog: Catalog) -> str:
    return ", ".join(f"{c} {catalog.colours[c].name}" for c in sorted(catalog.colours))


def _colour_name(catalog: Catalog, code: int) -> str:
    colour = catalog.colours.get(code)
    return f"{colour.name} ({code})" if colour else f"colour {code}"


# ---- validation ---------------------------------------------------------------------------


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float | np.integer | np.floating) and not isinstance(v, bool)


def _whole(v: Any) -> int | None:
    """``v`` as an int if it is a whole number (3 or 3.0), else None."""
    if not _is_number(v):
        return None
    if isinstance(v, int | np.integer):
        return int(v)
    f = float(v)
    if math.isfinite(f) and f.is_integer():
        return int(f)
    return None


def _too_long_to_save(n: int) -> bool:
    """True if ``n`` has more digits than Python will write as text, so the log could not save."""
    limit = sys.get_int_max_str_digits()
    return bool(limit) and n.bit_length() > 3 * limit and abs(n) >= 10**limit


def _check_fields(obj: dict, allowed: tuple[str, ...], what: str) -> None:
    unknown = [k for k in obj if k not in allowed]
    if unknown:
        key = unknown[0]
        hint = ""
        known = {f for fields in (*_OP_FIELDS.values(), *_SHAPE_FIELDS.values()) for f in fields}
        if isinstance(key, str) and key not in known:  # a field of another operation: no hint
            hint = _hint(key, allowed)
            synonym = _FIELD_SYNONYMS.get(key.lower())
            if not hint and synonym in allowed:
                hint = f' Did you mean "{synonym}"?'
        needed = [f for f in allowed if f not in _OPTIONAL_FIELDS]
        optional = [f for f in allowed if f in _OPTIONAL_FIELDS]
        takes = ", ".join(f'"{f}"' for f in needed)
        if optional:
            words = [f'"{f}"' for f in optional]
            maybe = words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"
            ending = f"It takes these fields: {takes}, and optionally {maybe}."
        else:
            ending = f"It takes exactly these fields: {takes}."
        raise _OpError(f"{what} has an unexpected field {_show(key)}.{hint} {ending}")


def _triple_field(
    shape: dict, name: str, what: str, whole: bool, whole_help: str | None = None
) -> tuple:
    if name not in shape:
        example = _BOX_EXAMPLE if what == "The box" else _ELLIPSOID_EXAMPLE
        raise _OpError(f'{what} is missing "{name}". Write it like this: {example}')
    value = shape[name]
    kind = "whole numbers" if whole else "numbers"
    if not isinstance(value, list | tuple):
        raise _OpError(
            f'"{name}" must be a list of three {kind} [x, y, z], but it is {_show(value)}.'
        )
    if len(value) != 3:
        raise _OpError(
            f'"{name}" must have exactly three {kind} [x, y, z], but it has {len(value)}: '
            f"{_show(value)}."
        )
    out: list[int | float] = []
    for axis, v in zip(_AXES, value, strict=True):
        if not _is_number(v):
            raise _OpError(f'"{name}" {axis} must be a number, but it is {_show(v)}.')
        if isinstance(v, float | np.floating) and not math.isfinite(float(v)):
            raise _OpError(f'"{name}" {axis} is {_show(v)}; it must be a finite number.')
        if whole:
            w = _whole(v)
            if w is None and whole_help is not None:
                raise _OpError(
                    f'"{name}" {axis} is {_num(v)}, but {whole_help} '
                    f"Use {math.floor(float(v))} or {math.ceil(float(v))}."
                )
            if w is None:
                raise _OpError(
                    f'"{name}" {axis} is {_num(v)}, but box corners must be whole cells. '
                    f"Use {math.floor(float(v))} or {math.ceil(float(v))}, or use an ellipsoid "
                    "for fractional positions."
                )
            if _too_long_to_save(w):
                raise _OpError(f'"{name}" {axis} is far too large to be a position in the grid.')
            out.append(w)
        else:
            try:
                out.append(float(v))
            except OverflowError:
                raise _OpError(
                    f'"{name}" {axis} is far too large to be a position or size in the grid.'
                ) from None
    return tuple(out)


def _parse_shape(shape: Any) -> tuple[str, tuple, tuple]:
    """Check a shape and return (type, first triple, second triple)."""
    if not isinstance(shape, dict):
        raise _OpError(
            f'"shape" must be an object such as {_BOX_EXAMPLE}, but it is {_show(shape)}.'
        )
    if "type" not in shape:
        raise _OpError(f'The shape is missing "type". Use {_SHAPE_HELP}.')
    kind = shape["type"]
    if not isinstance(kind, str) or kind not in SHAPE_TYPES:
        hint = _hint(kind, SHAPE_TYPES) if isinstance(kind, str) else ""
        raise _OpError(f"Unknown shape type {_show(kind)}.{hint} Use {_SHAPE_HELP}.")
    what = f"The {kind}"
    _check_fields(shape, _SHAPE_FIELDS[kind], what)
    if kind == "box":
        lo = _triple_field(shape, "min", what, whole=True)
        hi = _triple_field(shape, "max", what, whole=True)
        bad = [a for a, low, high in zip(_AXES, lo, hi, strict=True) if low > high]
        if bad:
            detail = "; ".join(
                f"min {a} = {_num(lo[_AXES.index(a)])} but max {a} = {_num(hi[_AXES.index(a)])}"
                for a in bad
            )
            fixed_lo = [min(a, b) for a, b in zip(lo, hi, strict=True)]
            fixed_hi = [max(a, b) for a, b in zip(lo, hi, strict=True)]
            raise _OpError(
                f"The box min is greater than its max ({detail}). Each min must be less than "
                f'or equal to the matching max; perhaps you meant "min": {_vec(fixed_lo)}, '
                f'"max": {_vec(fixed_hi)}.'
            )
        return kind, lo, hi
    center = _triple_field(shape, "center", what, whole=False)
    radius = _triple_field(shape, "radius", what, whole=False)
    small = [(a, r) for a, r in zip(_AXES, radius, strict=True) if r < MIN_RADIUS]
    if small:
        detail = ", ".join(f"{a} radius is {_num(r)}" for a, r in small)
        raise _OpError(
            f"Every ellipsoid radius must be at least 0.5, but the {detail}. "
            "A radius of 0.5 covers a single cell on that axis."
        )
    return kind, center, radius


def _made_in(catalog: Catalog, part: Part) -> str:
    return ", ".join(
        f"{c} {catalog.colours[c].name}" for c in sorted(part.colours) if c in catalog.colours
    )


def _parse_color(op: dict, name: str, catalog: Catalog, part: Part | None = None) -> int:
    """The checked colour code. For a detail ``part``, a message lists only the colours that
    part is made in, not the whole catalogue."""
    if part is None:
        valid = f"Valid codes: {_colour_list(catalog)}."
    else:
        valid = f"{part.name} ({part.id}) is made in: {_made_in(catalog, part)}."
    if "color" not in op:
        raise _OpError(
            f'"{name}" needs a "color": an LDraw colour code from the catalogue. {valid}'
        )
    value = op["color"]
    code = _whole(value)
    if code is None:
        suggestion = ""
        if isinstance(value, str):
            for c in sorted(catalog.colours):
                if catalog.colours[c].name.lower() == value.strip().lower():
                    suggestion = f" {catalog.colours[c].name} is code {c}."
                    break
        raise _OpError(
            f'"color" must be a whole-number colour code, but it is {_show(value)}.'
            f"{suggestion} {valid}"
        )
    if code not in catalog.colours:
        raise _OpError(f"Colour {_int_text(code)} is not in the catalogue. {valid}")
    return code


def _parse_part(op: dict, catalog: Catalog) -> str:
    details = {p.id: p for p in catalog.detail_parts()}
    listing = f"The detail parts {_parts_text(catalog)}"
    if "part" not in op:
        raise _OpError(
            f'"place_detail" needs a "part": the id of a detail part, written as text. {listing}'
        )
    value = op["part"]
    if _is_number(value):
        n = _whole(value)
        text = _int_text(n) if n is not None else ""
        if text in details:
            raise _OpError(
                f'"part" must be written as text in quotes: "{text}", not the number {text}.'
            )
    if not isinstance(value, str):
        raise _OpError(
            f'"part" must be the id of a detail part written as text, such as "98138", but it '
            f"is {_show(value)}. {listing}"
        )
    if value in details:
        return value
    if value in catalog.parts:
        raise _OpError(
            f'Part "{value}" ({catalog.parts[value].name}) is a building part that the layout '
            f"solver uses, not a detail part. {listing}"
        )
    hint = ""
    lowered = value.strip().lower()
    for p in details.values():
        if lowered in (p.id.lower(), p.name.lower()):
            hint = f' {p.name} is part "{p.id}".'
            break
    if not hint:
        match = difflib.get_close_matches(value.strip(), list(details), n=1, cutoff=0.6)
        if match:
            hint = f' Did you mean "{match[0]}" ({details[match[0]].name})?'
    raise _OpError(f"Unknown detail part {_show(value)}.{hint} {listing}")


def _parse_finish(op: dict) -> int:
    if "finish" not in op:
        raise _OpError(f'"set_finish" needs a "finish": {_FINISH_HELP}.')
    value = op["finish"]
    if not isinstance(value, str):
        hint = ""
        n = _whole(value)
        for word, code in FINISH_NAMES.items():
            if n is not None and n == code:
                hint = f' {n} means "{word}"; write the word.'
        raise _OpError(
            f'"finish" must be one of the words {_FINISH_HELP}, but it is {_show(value)}.{hint}'
        )
    if value in FINISH_NAMES:
        return FINISH_NAMES[value]
    hint = _hint(value, tuple(FINISH_NAMES))
    synonym = _FINISH_SYNONYMS.get(value.strip().lower())
    if synonym:
        hint = f' Did you mean "{synonym}"?'
    raise _OpError(f"Unknown finish {_show(value)}.{hint} Use {_FINISH_HELP}.")


def _parse_at(op: dict, name: str) -> tuple[int, int, int]:
    if "at" not in op:
        if name == "place_detail":
            raise _OpError(
                '"place_detail" needs "at": the minimum-corner cell [x, y, z] the part covers, '
                "with z the level directly above the filled cells it stands on. For example "
                f"{_DETAIL_EXAMPLE}."
            )
        raise _OpError(
            '"remove_detail" needs "at": any cell [x, y, z] the detail covers, for example '
            '{"op": "remove_detail", "at": [3, 0, 9]}.'
        )
    x, y, z = _triple_field(
        op, "at", f'The "{name}" operation', whole=True, whole_help="a cell position is whole."
    )
    return int(x), int(y), int(z)


def _parse_rot(op: dict) -> int:
    if "rot" not in op:
        return 0
    value = op["rot"]
    n = _whole(value)
    if n is not None and n in ROTATIONS:
        return n
    hint = ""
    if n is not None and n % 90 == 0:
        hint = f" {_int_text(n)} degrees is the same turn as {n % 360}; use {n % 360}."
    raise _OpError(
        f'"rot" must be 0, 90, 180 or 270 (degrees, a quarter turn at a time), but it is '
        f"{_show(value)}.{hint}"
    )


def _parse_face(op: dict) -> str:
    if "face" not in op:
        return "top"
    value = op["face"]
    if isinstance(value, str) and value in FACES:
        return value
    hint = ""
    if isinstance(value, str):
        hint = _hint(value, FACES)
        synonym = _FACE_SYNONYMS.get(value.strip().lower())
        if synonym:
            hint = f' Did you mean "{synonym}"?'
    raise _OpError(
        f'"face" must be "top" (the default: standing on studs), or "front", "right", "back" '
        f'or "left" (lying flat against that face of the model), but it is {_show(value)}.'
        f"{hint}"
    )


def _parse_mirror(op: dict) -> bool:
    value = op.get("mirror", False)
    if not isinstance(value, bool):
        raise _OpError(
            f'"mirror" must be true or false, but it is {_show(value)}. Write "mirror": true to '
            'do the same to the mirror image across the left-right middle, or leave "mirror" '
            "out."
        )
    return value


@dataclass
class _Parsed:
    """A checked operation."""

    name: str
    mirror: bool = False
    shape: dict | None = None
    color: int | None = None
    finish: int | None = None
    part: str | None = None
    at: tuple[int, int, int] | None = None
    rot: int = 0
    face: str = "top"


_REMOVE_VERBS = ("delete", "erase", "clear", "unplace", "remov")


def _parse_op(op: Any, catalog: Catalog) -> _Parsed:
    if not isinstance(op, dict):
        raise _OpError(
            "Each operation must be an object such as "
            f'{{"op": "add", "shape": {_BOX_EXAMPLE}, "color": 4}}, but this one is {_show(op)}.'
        )
    if "op" not in op:
        raise _OpError(f'The operation is missing "op". Use {_OP_HELP}.')
    name = op["op"]
    if not isinstance(name, str) or name not in OPS:
        if isinstance(name, str) and name.strip().lower() in ("mirror", "symmetric"):
            raise _OpError(f"Unknown op {_show(name)}. {_MIRROR_HELP}")
        hint = _hint(name, OPS) if isinstance(name, str) else ""
        lowered = name.lower() if isinstance(name, str) else ""
        if "detail" in lowered and any(v in lowered for v in _REMOVE_VERBS):
            hint = ' Did you mean "remove_detail"?'
        raise _OpError(f"Unknown op {_show(name)}.{hint} Use {_OP_HELP}.")
    what = f'The "{name}" operation'
    if name == "remove" and "color" in op:
        raise _OpError(
            '"remove" does not take a "color" (removed cells become empty). '
            'Delete the "color" field, or use "paint" to recolour cells.'
        )
    _check_fields(op, _OP_FIELDS[name], what)
    parsed = _Parsed(name)
    if name in SHAPE_OPS:
        if "shape" not in op:
            raise _OpError(f'"{name}" needs a "shape", for example {_BOX_EXAMPLE}.')
        _parse_shape(op["shape"])
        parsed.shape = op["shape"]
        if name in ("add", "paint"):
            parsed.color = _parse_color(op, name, catalog)
        elif name == "set_finish":
            parsed.finish = _parse_finish(op)
    elif name == "place_detail":
        parsed.part = _parse_part(op, catalog)
        part = catalog.parts[parsed.part]
        parsed.color = _parse_color(op, name, catalog, part)
        if not catalog.exists(parsed.part, parsed.color):
            raise _OpError(
                f"{part.name} ({part.id}) is not made in {_colour_name(catalog, parsed.color)}. "
                f"It is made in: {_made_in(catalog, part)}."
            )
        parsed.at = _parse_at(op, name)
        parsed.rot = _parse_rot(op)
        parsed.face = _parse_face(op)
        if parsed.face != "top":
            if not catalog.can_face_sideways(parsed.part):
                able = "; ".join(f"{q.id} {q.name}" for q in catalog.sideways_parts())
                raise _OpError(
                    f"{part.name} ({part.id}) cannot lie on a face: only a detail one stud wide "
                    f"and one plate thick can, held by a side stud. Those are: {able}. Use one "
                    f'of them, or leave out "face" to stand this part on top.'
                )
            if parsed.rot != 0:
                raise _OpError(
                    f'A part on a face takes "rot": 0 (or no "rot"): it is one stud wide, so '
                    f'turning it about its stud changes nothing. Leave out "rot" for the '
                    f"{part.name} ({part.id}) on the {parsed.face} face."
                )
    else:
        parsed.at = _parse_at(op, name)
    parsed.mirror = _parse_mirror(op)
    return parsed


def validate_op(op: Any, catalog: Catalog) -> None:
    """Raise ValueError, worded for the writer, if ``op`` is not a well-formed operation.

    It does not look at a Design, so it cannot tell whether the operation would change
    anything or whether its shape lies inside the grid.
    """
    _parse_op(op, catalog)


# ---- shapes -------------------------------------------------------------------------------


@dataclass
class _Region:
    """Where a shape meets the grid: a block of the grid and a mask inside that block."""

    slices: tuple[slice, slice, slice]
    mask: np.ndarray  # bool, the shape of the block
    outside: bool  # the shape's bounds lie entirely outside the grid
    clipped: bool  # part of the shape's bounds lay outside the grid
    out_axes: list[str]  # for an outside shape: one line per axis that misses the grid


def _round_bound(rounding: Any, value: float) -> int:
    """``rounding(value)``, with sums that overflowed to infinity kept as huge integers."""
    if math.isfinite(value):
        return int(rounding(value))
    return 10**309 if value > 0 else -(10**309)


def _region(shape: Any, grid_shape: tuple[int, int, int]) -> _Region:
    kind, a, b = _parse_shape(shape)
    if kind == "box":
        lo = [int(v) for v in a]
        hi = [int(v) for v in b]
    else:
        lo = [_round_bound(math.ceil, c - r - _EPS) for c, r in zip(a, b, strict=True)]
        hi = [_round_bound(math.floor, c + r + _EPS) for c, r in zip(a, b, strict=True)]
    out_axes = [
        f"{axis} {_int_text(lo[i])}..{_int_text(hi[i])}"
        for i, axis in enumerate(_AXES)
        if hi[i] < 0 or lo[i] > grid_shape[i] - 1
    ]
    if out_axes:
        empty: tuple[slice, slice, slice] = (slice(0, 0), slice(0, 0), slice(0, 0))
        return _Region(empty, np.zeros((0, 0, 0), dtype=bool), True, True, out_axes)
    clo = [max(lo[i], 0) for i in range(3)]
    chi = [min(hi[i], grid_shape[i] - 1) for i in range(3)]
    clipped = clo != lo or chi != hi
    slices = (
        slice(clo[0], chi[0] + 1),
        slice(clo[1], chi[1] + 1),
        slice(clo[2], chi[2] + 1),
    )
    if kind == "box":
        mask = np.ones([chi[i] - clo[i] + 1 for i in range(3)], dtype=bool)
    else:
        mask = _ellipsoid_mask(clo, chi, a, b)
        if clipped:
            clipped = _ellipsoid_cells_beyond(lo, hi, clo, chi, a, b, grid_shape)
    return _Region(slices, mask, False, clipped, [])


# Most cells looked at beyond the grid to tell whether an ellipsoid really loses any there.
# A bigger ellipsoid is taken to lose some, from its bounds alone.
_BEYOND_LIMIT = 2_000_000


def _ellipsoid_mask(lo: list[int], hi: list[int], center: Any, radius: Any) -> np.ndarray:
    """Cells of the block ``lo..hi`` (inclusive) inside the ellipsoid."""
    x, y, z = (
        (np.arange(lo[i], hi[i] + 1, dtype=np.float64) - center[i]) / radius[i] for i in range(3)
    )
    dist = x[:, None, None] ** 2 + y[None, :, None] ** 2 + z[None, None, :] ** 2
    return dist <= 1.0 + _EPS


def _ellipsoid_cells_beyond(
    lo: list[int],
    hi: list[int],
    clo: list[int],
    chi: list[int],
    center: Any,
    radius: Any,
    grid_shape: tuple[int, int, int],
) -> bool:
    """Whether any cell of the ellipsoid lies outside the grid.

    The part of the bounds ``lo..hi`` outside the grid is cut into up to six slabs, one per
    side; each axis before the slab's own is held to the grid so that no cell is counted
    twice. Cells are tested with the same sum as ``_ellipsoid_mask``, so the answer agrees
    with the cells that ``shape_mask`` would give on a grid big enough to hold the shape.
    """
    slabs: list[tuple[list[int], list[int]]] = []
    for i in range(3):
        for s_lo, s_hi in ((lo[i], -1), (grid_shape[i], hi[i])):
            if s_lo > s_hi:
                continue
            s_from = [clo[j] if j < i else lo[j] for j in range(3)]
            s_to = [chi[j] if j < i else hi[j] for j in range(3)]
            s_from[i], s_to[i] = s_lo, s_hi
            slabs.append((s_from, s_to))
    sizes = [math.prod(max(t - f + 1, 0) for f, t in zip(f3, t3, strict=True)) for f3, t3 in slabs]
    if sum(sizes) > _BEYOND_LIMIT:
        return True
    return any(
        _ellipsoid_mask(f3, t3, center, radius).any()
        for (f3, t3), n in zip(slabs, sizes, strict=True)
        if n
    )


def shape_mask(shape: dict[str, Any], grid_shape: tuple[int, int, int]) -> np.ndarray:
    """Boolean array of ``grid_shape``, True for every cell inside ``shape``.

    Parts of the shape outside the grid are dropped; a shape entirely outside gives an
    all-False array. A malformed shape raises ValueError with a message saying what to fix.
    """
    grid = (int(grid_shape[0]), int(grid_shape[1]), int(grid_shape[2]))
    out = np.zeros(grid, dtype=bool)
    region = _region(shape, grid)
    if not region.outside:
        out[region.slices] = region.mask
    return out


def _describe_shape(shape: dict) -> str:
    if shape["type"] == "box":
        return f"box {_vec(shape['min'])}..{_vec(shape['max'])}"
    return f"ellipsoid centred at {_vec(shape['center'])} with radius {_vec(shape['radius'])}"


# ---- applying -----------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """A JSON-ready copy: same keys and values, tuples as lists, numpy numbers as Python."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    # Convert by kind: .item() would hand back a numpy long double unchanged.
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def _mirror_shape(shape: dict, nx: int) -> dict:
    """The shape's mirror image across the plane x = nx / 2 (cell x becomes nx - 1 - x)."""
    if shape["type"] == "box":
        lo = [_whole(v) for v in shape["min"]]
        hi = [_whole(v) for v in shape["max"]]
        assert lo[0] is not None and hi[0] is not None
        return {
            "type": "box",
            "min": [nx - 1 - hi[0], *lo[1:]],
            "max": [nx - 1 - lo[0], *hi[1:]],
        }
    center = [float(v) for v in shape["center"]]
    return {
        "type": "ellipsoid",
        "center": [nx - 1 - center[0], *center[1:]],
        "radius": list(shape["radius"]),
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def _at(x: int, y: int, z: int) -> str:
    return f"x={_int_text(x)}, y={_int_text(y)}, z={_int_text(z)}"


def _span(lo: int, hi: int) -> str:
    return _int_text(lo) if lo == hi else f"{_int_text(lo)}..{_int_text(hi)}"


def _covers(catalog: Catalog, p: Placement) -> tuple[slice, slice, slice] | None:
    """The cells a detail covers, or None if its part is not in the catalogue."""
    if p.part not in catalog.parts:
        return None
    return catalog.cells(p)


def _box_text(cells: tuple[slice, slice, slice]) -> str:
    xs, ys, zs = cells
    return (
        f"x={_span(xs.start, xs.stop - 1)}, y={_span(ys.start, ys.stop - 1)}, "
        f"z={_span(zs.start, zs.stop - 1)}"
    )


def _as_placement(d: Detail) -> Placement:
    return Placement(d.part, d.color, d.x, d.y, d.z, d.rot, face=d.face)


def _detail_name(catalog: Catalog, part_id: str, color: int) -> str:
    part = catalog.parts.get(part_id)
    colour = catalog.colours.get(color)
    colour_text = colour.name if colour else f"colour {color}"
    return f"{colour_text} {part.name if part else 'part'} ({part_id})"


def _detail_where(catalog: Catalog, p: Placement) -> str:
    face = f", on the {p.face} face" if p.face != "top" else ""
    return f"the {_detail_name(catalog, p.part, p.color)} at {_at(p.x, p.y, p.z)}{face}"


def _behind(p: Placement) -> tuple[int, int, slice]:
    """The cells behind a sideways detail's column: the side-stud brick's (x, y, z span)."""
    ox, oy = FACE_OUT[p.face]
    return p.x - ox, p.y - oy, slice(p.z, p.z + 3)


def _clip_slices(cells: tuple[slice, slice, slice], grid: tuple[int, int, int]) -> tuple:
    return tuple(
        slice(min(max(s.start, 0), n), min(max(s.stop, 0), n))
        for s, n in zip(cells, grid, strict=True)
    )


def _drop_details(design: Design, catalog: Catalog, changed: np.ndarray, *, added: bool) -> str:
    """Remove the details that ``changed`` cells leave dangling; return a sentence about it.

    After an ``add`` (``added``), a detail goes when a cell it stands in is now filled; after
    a ``remove``, when a cell directly below its bottom layer is now empty.
    """
    grid = design.shape
    kept: list[Detail] = []
    gone: list[str] = []
    sideways = False
    for d in design.details:
        cells = _covers(catalog, _as_placement(d))
        hit = False
        if cells is not None:
            xs, ys, zs = cells
            if added:
                hit = bool(changed[_clip_slices(cells, grid)].any())
            elif d.face in FACE_OUT:
                bx, by, bz = _behind(_as_placement(d))
                if 0 <= bx < grid[0] and 0 <= by < grid[1]:
                    hit = bool(changed[bx, by, max(bz.start, 0) : min(bz.stop, grid[2])].any())
            elif 0 < zs.start <= grid[2]:
                xs, ys, _ = _clip_slices(cells, grid)
                hit = bool(changed[xs, ys, zs.start - 1].any())
        if hit:
            gone.append(_detail_where(catalog, _as_placement(d)))
            sideways = sideways or d.face != "top"
        else:
            kept.append(d)
    if not gone:
        return ""
    design.details[:] = kept
    reason = "a cell it stood in is now filled" if added else "a cell it stood on is now empty"
    if sideways and not added:
        reason = "a cell it stood on, or a cell of the brick behind it, is now empty"
    if len(gone) == 1:
        return f" This also removed {gone[0]}, because {reason}."
    reason = "cells they stood in are now filled" if added else "cells they stood on are now empty"
    if sideways and not added:
        reason = "cells they stood on, or cells of the bricks behind them, are now empty"
    return f" This also removed {len(gone)} details, because {reason}: {'; '.join(gone)}."


def _apply_shape_op(design: Design, p: _Parsed, catalog: Catalog) -> tuple[bool, int, str]:
    """add, remove, paint or set_finish. Returns (applied, cells_changed, message)."""
    name, shape, color = p.name, p.shape, p.color
    assert shape is not None
    grid = design.shape
    region = _region(shape, grid)
    where = _describe_shape(shape)
    if region.outside:
        raise _OpError(
            f"That {where} lies entirely outside the grid: its {' and '.join(region.out_axes)} "
            f"misses the grid. Valid cells are {_ranges(grid)}."
        )
    if not region.mask.any() and region.clipped:
        # The bounds overlap the grid on every axis but the shape itself misses it, as when
        # a ball sits just beyond a corner or edge of the grid.
        raise _OpError(
            f"That {where} lies entirely outside the grid: none of its cells are inside the "
            f"grid. Valid cells are {_ranges(grid)}."
        )
    if not region.mask.any():
        raise _OpError(
            f"That {where} is too small to contain any cell: no cell with whole-number "
            "coordinates is inside it. Move the centre onto whole numbers or make a radius "
            "larger."
        )
    assert design.finish is not None
    mask = np.zeros(grid, dtype=bool)
    mask[region.slices] = region.mask
    if p.mirror:
        # The grid is symmetric under the mirror, so mirroring the clipped mask is the same
        # as clipping the mirrored shape.
        image = mask[::-1, :, :]
        if np.array_equal(image, mask):
            where = f"{where} (which is its own mirror image)"
        else:
            twin = _describe_shape(_mirror_shape(shape, grid[0]))
            where = f"{where} and its mirror image, the {twin}"
        mask = mask | image
    colors = design.colors
    finish = design.finish
    filled = colors != EMPTY
    clip_note = (
        f" Part of the shape lay outside the grid ({_ranges(grid)}) and was ignored."
        if region.clipped
        else ""
    )
    extra = ""

    if name == "add":
        assert color is not None
        change = mask & ~filled
        n = int(change.sum())
        if n == 0:
            return (
                False,
                0,
                f'Nothing to add: every cell inside that {where} is already filled. Use "paint" '
                "to recolour filled cells.",
            )
        colors[change] = color
        finish[change] = FINISH_STUDS
        extra = _drop_details(design, catalog, change, added=True)
        verb = f"Added {n} cell{'s' if n != 1 else ''} of {_colour_name(catalog, color)}"
    elif name == "remove":
        change = mask & filled
        n = int(change.sum())
        if n == 0:
            return False, 0, f"Nothing to remove: every cell inside that {where} is already empty."
        total = int(np.count_nonzero(filled))
        if n == total:
            raise _OpError(
                f"That would remove all {n} filled cells and leave the design completely "
                "empty, so it was not done. Remove a smaller region."
            )
        colors[change] = EMPTY
        finish[change] = FINISH_STUDS
        extra = _drop_details(design, catalog, change, added=False)
        verb = f"Removed {n} cell{'s' if n != 1 else ''}"
    elif name == "paint":
        assert color is not None
        inside = mask & filled
        if not inside.any():
            return (
                False,
                0,
                f'Nothing to paint: every cell inside that {where} is empty. "paint" only '
                'recolours filled cells; use "add" to fill empty ones.',
            )
        change = inside & (colors != color)
        n = int(change.sum())
        if n == 0:
            return (
                False,
                0,
                f"Nothing to paint: every filled cell inside that {where} is already "
                f"{_colour_name(catalog, color)}.",
            )
        colors[change] = color
        verb = f"Painted {n} cell{'s' if n != 1 else ''} {_colour_name(catalog, color)}"
    else:
        assert p.finish is not None
        word = next(w for w, code in FINISH_NAMES.items() if code == p.finish)
        inside = mask & filled
        if not inside.any():
            return (
                False,
                0,
                f'Nothing to mark: every cell inside that {where} is empty. "set_finish" only '
                "marks filled cells.",
            )
        change = inside & (finish != p.finish)
        n = int(change.sum())
        if n == 0:
            return (
                False,
                0,
                f'Nothing to mark: every filled cell inside that {where} is already "{word}".',
            )
        finish[change] = p.finish
        verb = f'Marked {_plural(n, "cell")} "{word}" ({_FINISH_MEANING[word]})'
        open_top = np.ones(grid, dtype=bool)
        open_top[:, :, :-1] = ~filled[:, :, 1:]
        k = int((change & open_top).sum())
        if k == n:
            extra = " Each has nothing directly above it, so the finish will show on all of them."
        elif k == 0:
            extra = (
                " None of them has an empty cell directly above it, so this will show only "
                "where the cells above are removed."
            )
        else:
            extra = (
                f" {k} of them {'has' if k == 1 else 'have'} nothing directly above, so the "
                "finish will show there; the others are covered."
            )
    return True, n, f"{verb} inside the {where}.{clip_note}{extra}"


def _detail_problem(design: Design, catalog: Catalog, p: Placement) -> str | None:
    """Why the detail ``p`` cannot stand where it is, or None if it can."""
    grid = design.shape
    cells = catalog.cells(p)
    for axis, s, n in zip(_AXES, cells, grid, strict=True):
        bad = s.start if s.start < 0 else (s.stop - 1 if s.stop > n else None)
        if bad is not None:
            return (
                f"it would cover {_box_text(cells)}, and {axis}={_int_text(bad)} is outside the "
                f"grid. Valid cells are {_ranges(grid)}."
            )
    xs, ys, zs = cells
    filled = np.argwhere(design.colors[cells] != EMPTY)
    if len(filled):
        dx, dy, dz = (int(v) for v in filled[0])
        return (
            f"it would cover {_at(xs.start + dx, ys.start + dy, zs.start + dz)}, which is "
            "filled. A detail stands in empty cells on top of the model: its z is the level "
            "directly above the filled cells it stands on."
        )
    if not outside_air(design.filled)[cells].all():
        return (
            f"it would cover {_box_text(cells)}, which is inside the model, in a space closed "
            "off from the outside, where nobody could put it or see it."
        )
    for other in design.details:
        theirs = _covers(catalog, _as_placement(other))
        if theirs is None:
            continue
        lo = [max(a.start, b.start) for a, b in zip(cells, theirs, strict=True)]
        hi = [min(a.stop, b.stop) for a, b in zip(cells, theirs, strict=True)]
        if all(a < b for a, b in zip(lo, hi, strict=True)):
            return (
                f"{_at(*lo)} is already taken by {_detail_where(catalog, _as_placement(other))}. "
                "Remove that one first with "
                f'{{"op": "remove_detail", "at": [{other.x}, {other.y}, {other.z}]}}, or choose '
                "another place."
            )
    if zs.start == 0:
        return (
            "z=0 is the ground. A detail must stand on the model: its z is the level directly "
            "above the filled cells it stands on."
        )
    below = np.argwhere(design.colors[xs, ys, zs.start - 1] == EMPTY)
    if len(below):
        dx, dy = (int(v) for v in below[0])
        x, y = xs.start + dx, ys.start + dy
        return (
            f"the cell {_at(x, y, zs.start)} of its bottom layer has nothing below it "
            f"({_at(x, y, zs.start - 1)} is empty). A detail must stand on filled cells."
        )
    return None


def _detail_suggestion(design: Design, catalog: Catalog, p: Placement) -> str:
    """A hint at a height where ``p`` would fit, from the top of the model under it."""
    grid = design.shape
    xs, ys, _ = catalog.cells(p)
    if xs.start < 0 or ys.start < 0 or xs.stop > grid[0] or ys.stop > grid[1]:
        return ""
    columns = design.colors[xs, ys, :] != EMPTY
    if not columns.any(axis=2).all():
        return ""
    tops = grid[2] - 1 - np.argmax(columns[:, :, ::-1], axis=2)
    lowest, highest = int(tops.min()), int(tops.max())
    if lowest != highest:
        return (
            f" The top of the model under it is not flat (z={lowest} in some columns, "
            f"z={highest} in others); a detail needs a flat spot."
        )
    z = highest + 1
    if z == p.z:
        return ""
    candidate = Placement(p.part, p.color, p.x, p.y, z, p.rot)
    if _detail_problem(design, catalog, candidate) is not None:
        return ""
    return f' The top of the model there is at z={highest}, so "at": [{p.x}, {p.y}, {z}] would fit.'


def _mirror_placement(catalog: Catalog, p: Placement, nx: int) -> Placement | None:
    """The detail that is the mirror image of ``p`` across x = nx / 2, or None if no turn of
    the part gives one.

    The four turns are tried and the one kept covers the mirror image of ``p``'s cells, runs
    down the mirrored way if it is a slope, and (where possible) has its studs on the mirror
    image of ``p``'s studs. When several turns fit (a symmetric part), ``p``'s own turn wins.
    """
    xs, ys, zs = catalog.cells(p)
    x0 = nx - xs.stop  # the mirror image of the cells xs.start..xs.stop-1
    want_cells = (slice(x0, nx - xs.start), ys, zs)
    down = catalog.low_side(p)
    want_down = None if down is None else (-down[0], down[1])
    want_studs = sorted((nx - 1 - x, y) for x, y in catalog.stud_cells(p))
    exact: list[Placement] = []
    loose: list[Placement] = []
    for rot in ROTATIONS:
        q = Placement(p.part, p.color, x0, p.y, p.z, rot)
        if catalog.cells(q) != want_cells or catalog.low_side(q) != want_down:
            continue
        (exact if sorted(catalog.stud_cells(q)) == want_studs else loose).append(q)
    part = catalog.parts[p.part]
    sticks_out = part.body_max[2] - part.body_min[2] > 20 * part.sz + 1
    # Every detail part is the same on the left and right of its own Z axis, so turning by
    # -rot gives the mirror image. A part that sticks out past its footprint along its own Z
    # (the clip of 60897) must take that turn; a part that does not looks the same either way
    # and keeps its own rot.
    preferred = (360 - p.rot) % 360 if sticks_out else p.rot
    for group in (exact, loose):
        for q in group:
            if q.rot == preferred:
                return q
        if group:
            return group[0]
    return None


def _slope_note(catalog: Catalog, p: Placement, it: str = "Its") -> str:
    down = catalog.low_side(p)
    if down is None:
        return ""
    return f" {it} slanted face runs down towards {_direction_word(down)}."


def _sideways_problem(
    design: Design,
    catalog: Catalog,
    p: Placement,
    ignore: Placement | None = None,
    outside: np.ndarray | None = None,
) -> str | None:
    """Why the sideways detail ``p`` cannot go where it is, or None if it can. ``ignore`` is
    a detail placed with it (its mirror image), counted as already there. ``outside`` is
    ``buildable.outside_air`` of the design, when the caller has it already."""
    grid = design.shape
    cells = catalog.cells(p)
    xs, ys, zs = cells
    for axis, s, n in zip(_AXES, cells, grid, strict=True):
        bad = s.start if s.start < 0 else (s.stop - 1 if s.stop > n else None)
        if bad is not None:
            return (
                f"it keeps clear the column {_box_text(cells)}, and {axis}={_int_text(bad)} is "
                f"outside the grid. Valid cells are {_ranges(grid)}."
            )
    if p.z % 3:
        lo, hi = p.z - p.z % 3, p.z - p.z % 3 + 3
        nearest = f"z={lo} or z={hi}" if hi + 3 <= grid[2] else f"z={lo}"
        return (
            f"z={p.z} is not the bottom of a brick course. A part on a face is held by the "
            "side stud of a brick, and bricks sit in courses of three plates, so z must be a "
            f"multiple of 3: use {nearest}."
        )
    filled = np.argwhere(design.colors[cells] != EMPTY)
    if len(filled):
        dz = int(filled[0][2])
        return (
            f"it keeps clear the column {_box_text(cells)} in front of the {p.face} face, and "
            f"{_at(p.x, p.y, p.z + dz)} is filled. A part on a face needs those three cells "
            "empty, with the model directly behind them."
        )
    if outside is None:
        outside = outside_air(design.filled)
    if not outside[cells].all():
        return (
            f"the column {_box_text(cells)} it keeps clear is inside the model, in a space "
            "closed off from the outside, where nobody could put it or see it."
        )
    others = [d for d in design.details] + ([] if ignore is None else [_detail_of(ignore)])
    for other in others:
        theirs = _covers(catalog, _as_placement(other))
        if theirs is None:
            continue
        lo = [max(a.start, b.start) for a, b in zip(cells, theirs, strict=True)]
        hi = [min(a.stop, b.stop) for a, b in zip(cells, theirs, strict=True)]
        if all(a < b for a, b in zip(lo, hi, strict=True)):
            return (
                f"{_at(*lo)} is already taken by {_detail_where(catalog, _as_placement(other))}. "
                "Remove that one first with "
                f'{{"op": "remove_detail", "at": [{other.x}, {other.y}, {other.z}]}}, or choose '
                "another place."
            )
    bx, by, bz = _behind(p)
    behind = f"x={bx}, y={by}, z={_span(bz.start, bz.stop - 1)}"
    if not (0 <= bx < grid[0] and 0 <= by < grid[1]):
        return (
            f"the cells behind it ({behind}), where the brick that holds it must go, are "
            f"outside the grid. Valid cells are {_ranges(grid)}."
        )
    column = design.colors[bx, by, bz]
    missing = [bz.start + k for k in range(3) if column[k] == EMPTY]
    if missing:
        which = ", ".join(f"z={z}" for z in missing)
        return (
            f"the three cells behind it ({behind}) must all be filled, because a brick with a "
            f"stud on its side goes there to hold it, but {which} "
            f"{'is' if len(missing) == 1 else 'are'} empty."
        )
    paint_op = (
        f'{{"op": "paint", "shape": {{"type": "box", "min": [{bx}, {by}, {bz.start}], '
        f'"max": [{bx}, {by}, {bz.stop - 1}]}}, "color": {{}}}}'
    )
    colour = brick_colour(int(c) for c in column)
    if len(set(int(c) for c in column)) > 1:
        names = ", ".join(
            f"z={bz.start + k} {_colour_name(catalog, int(c))}" for k, c in enumerate(column)
        )
        fix = (
            f"; for example {paint_op.replace('{}', str(colour))}"
            if catalog.side_stud_exists(colour)
            else ""
        )
        return (
            f"the three cells behind it ({behind}) are not one colour ({names}), and the brick "
            "with a stud on its side that holds it is one part, so one colour. Paint them one "
            f"colour first{fix}."
        )
    bricks = {
        (ox, oy, oz.start)
        for other in others
        if other.face in FACE_OUT and other.part in catalog.parts
        for ox, oy, oz in [_behind(_as_placement(other))]
    }
    if (bx, by, bz.start) not in bricks and not side_brick_held(
        design.colors, bricks, (bx, by, bz.start)
    ):
        return (
            f"the brick that would hold it ({behind}) would have nothing directly above or "
            "below it but other bricks holding parts on faces, and a brick is held only "
            "through the parts on and under it, so it would come loose. Choose a place where "
            "the model goes on above or below that brick."
        )
    if not catalog.side_stud_exists(colour):
        brick = catalog.parts.get("87087")
        made = _made_in(catalog, brick) if brick is not None else "no colour"
        return (
            f"the brick with a stud on its side (87087) that would hold it takes the colour of "
            f"the cells behind it ({behind}), {_colour_name(catalog, colour)}, and it is not "
            f"made in that colour. It is made in: {made}. Paint those three cells one of "
            "those colours first."
        )
    for other in others:
        if other.face in FACE_OUT and other.part in catalog.parts:
            ox, oy, oz = _behind(_as_placement(other))
            if (ox, oy, oz.start) == (bx, by, bz.start):
                return (
                    f"the brick behind it ({behind}) already holds "
                    f"{_detail_where(catalog, _as_placement(other))}, and one brick holds one "
                    "part on its side. Choose another brick."
                )
    return None


def _detail_of(p: Placement) -> Detail:
    return Detail(p.part, p.color, p.x, p.y, p.z, p.rot, p.face)


def _sideways_suggestion(design: Design, catalog: Catalog, p: Placement) -> str:
    """The nearest "at" that would work for the sideways detail ``p``: along the line through
    it in the face's direction, at its own brick course or the nearest ones."""
    grid = design.shape
    ox, oy = FACE_OUT[p.face]
    base = p.z - p.z % 3
    zs = [z for z in range(base - 6, base + 10, 3) if 0 <= z <= grid[2] - 3]
    outside = outside_air(design.filled)
    tries = []
    for z in zs:
        for k in range(-max(grid[:2]), max(grid[:2]) + 1):
            tries.append((abs(z - p.z), abs(k), -k, z, p.x + k * ox, p.y + k * oy))
    for _, _, _, z, x, y in sorted(tries):
        if (x, y, z) == (p.x, p.y, p.z) or not (0 <= x < grid[0] and 0 <= y < grid[1]):
            continue
        q = Placement(p.part, p.color, x, y, z, 0, face=p.face)
        if _sideways_problem(design, catalog, q, outside=outside) is None:
            return f' "at": [{x}, {y}, {z}] with "face": "{p.face}" would fit.'
    return ""


def _place_sideways(design: Design, p: _Parsed, catalog: Catalog) -> tuple[bool, int, str]:
    assert p.part is not None and p.color is not None and p.at is not None
    x, y, z = p.at
    first = Placement(p.part, p.color, x, y, z, 0, face=p.face)
    name = _detail_name(catalog, p.part, p.color)
    where = f"The {name} at {_at(x, y, z)} on the {p.face} face"
    problem = _sideways_problem(design, catalog, first)
    if problem is not None:
        hint = _sideways_suggestion(design, catalog, first)
        raise _OpError(f"{where} cannot go there: {problem}{hint}")
    placed = [first]
    note = ""
    if p.mirror:
        nx = design.shape[0]
        twin = Placement(p.part, p.color, nx - 1 - x, y, z, 0, face=_FACE_MIRROR[p.face])
        if catalog.cells(twin) == catalog.cells(first):
            note = (
                " It lies on the left-right middle, so its mirror image would take the same "
                "cells; only one was placed."
            )
        else:
            problem = _sideways_problem(design, catalog, twin, ignore=first)
            if problem is not None:
                raise _OpError(
                    f"{where} would fit, but its mirror image at "
                    f"{_at(twin.x, twin.y, twin.z)} on the {twin.face} face cannot go there: "
                    f"{problem} Nothing was placed. Choose a place whose mirror image is free "
                    'too, or leave out "mirror" to place just one.'
                )
            placed.append(twin)
            note = (
                f" Also placed its mirror image at {_at(twin.x, twin.y, twin.z)} on the "
                f"{twin.face} face."
            )
    for q in placed:
        design.details.append(_detail_of(q))
    bx, by, bz = _behind(first)
    brick = _colour_name(catalog, int(design.colors[bx, by, bz.start]))
    message = (
        f"Placed a {name} at {_at(x, y, z)} on the {p.face} face, keeping clear "
        f"{_box_text(catalog.cells(first))}; a {brick} brick with a stud on its side will hold "
        f"it from x={bx}, y={by}, z={_span(bz.start, bz.stop - 1)} (the colour of the cells "
        f"there), showing around the part's edges.{note} The design now has "
        f"{_plural(len(design.details), 'detail part')}."
    )
    return True, 0, message


def _place_detail(design: Design, p: _Parsed, catalog: Catalog) -> tuple[bool, int, str]:
    assert p.part is not None and p.color is not None and p.at is not None
    if p.face != "top":
        return _place_sideways(design, p, catalog)
    x, y, z = p.at
    first = Placement(p.part, p.color, x, y, z, p.rot)
    name = _detail_name(catalog, p.part, p.color)
    problem = _detail_problem(design, catalog, first)
    if problem is not None:
        hint = _detail_suggestion(design, catalog, first)
        raise _OpError(
            f"The {name} at {_at(x, y, z)} (rot {p.rot}) cannot go there: {problem}{hint}"
        )
    placed = [first]
    note = ""
    if p.mirror:
        twin = _mirror_placement(catalog, first, design.shape[0])
        if twin is None:
            raise _OpError(
                f"No turn of the {name} is the mirror image of it at rot {p.rot}, so it was not "
                'placed. Place each side separately without "mirror".'
            )
        mine, theirs = catalog.cells(first), catalog.cells(twin)
        overlap = all(
            max(a.start, b.start) < min(a.stop, b.stop) for a, b in zip(mine, theirs, strict=True)
        )
        if mine == theirs:
            note = (
                " It lies on the left-right middle, so its mirror image would take the same "
                "cells; only one was placed."
            )
        elif overlap:
            w = mine[0].stop - mine[0].start
            centre = ""
            if (design.shape[0] - w) % 2 == 0:
                centre = (
                    " To have it centred on the middle instead, remove this one and use "
                    f"x={(design.shape[0] - w) // 2}."
                )
            note = (
                f" Its mirror image (at {_at(twin.x, twin.y, twin.z)}, rot {twin.rot}) would "
                f"overlap it, so only one was placed.{centre}"
            )
        else:
            problem = _detail_problem(design, catalog, twin)
            if problem is not None:
                raise _OpError(
                    f"The {name} at {_at(x, y, z)} (rot {p.rot}) would fit, but its mirror image "
                    f"at {_at(twin.x, twin.y, twin.z)} (rot {twin.rot}) cannot go there: "
                    f"{problem} Nothing was placed. Choose a place whose mirror image is free "
                    'too, or leave out "mirror" to place just one.'
                )
            placed.append(twin)
            note = (
                f" Also placed its mirror image at {_at(twin.x, twin.y, twin.z)} (rot "
                f"{twin.rot}), covering {_box_text(theirs)}."
                + _slope_note(catalog, twin, "The mirror image's")
            )
    for q in placed:
        design.details.append(Detail(q.part, q.color, q.x, q.y, q.z, q.rot))
    message = (
        f"Placed a {name} at {_at(x, y, z)} (rot {p.rot}), covering "
        f"{_box_text(catalog.cells(first))}.{_slope_note(catalog, first)}{note} The design now "
        f"has {_plural(len(design.details), 'detail part')}."
    )
    return True, 0, message


def _detail_at(design: Design, catalog: Catalog, cell: tuple[int, int, int]) -> int | None:
    """Index in ``design.details`` of the detail covering ``cell``, or None."""
    for i, d in enumerate(design.details):
        cells = _covers(catalog, _as_placement(d))
        if cells is not None and all(
            s.start <= v < s.stop for s, v in zip(cells, cell, strict=True)
        ):
            return i
    return None


def _details_now(design: Design, catalog: Catalog, limit: int = 12) -> str:
    if not design.details:
        return "The design has no detail parts."
    lines = []
    for d in design.details[:limit]:
        p = _as_placement(d)
        cells = _covers(catalog, p)
        cover = f", covering {_box_text(cells)}" if cells is not None else ""
        lines.append(f"{_detail_where(catalog, p)}{cover}")
    more = len(design.details) - limit
    tail = f"; and {more} more" if more > 0 else ""
    return f"The detail parts now are: {'; '.join(lines)}{tail}."


def _remove_detail(design: Design, p: _Parsed, catalog: Catalog) -> tuple[bool, int, str]:
    assert p.at is not None
    x, y, z = p.at
    found = _detail_at(design, catalog, p.at)
    twin_cell = (design.shape[0] - 1 - x, y, z)
    if not p.mirror:
        if found is None:
            raise _OpError(f"No detail part covers {_at(x, y, z)}. {_details_now(design, catalog)}")
        gone = design.details.pop(found)
        return True, 0, f"Removed {_detail_where(catalog, _as_placement(gone))}."
    twin = _detail_at(design, catalog, twin_cell)
    if found is None and twin is None:
        raise _OpError(
            f"No detail part covers {_at(x, y, z)} or its mirror image {_at(*twin_cell)}. "
            f"{_details_now(design, catalog)}"
        )
    indices = sorted({i for i in (found, twin) if i is not None})
    removed = [_detail_where(catalog, _as_placement(design.details[i])) for i in indices]
    for i in reversed(indices):
        design.details.pop(i)
    if len(removed) == 2:
        message = f"Removed {removed[0]} and its mirror image, {removed[1]}."
    elif found is not None and twin is not None:
        message = (
            f"Removed {removed[0]}. It covers its own mirror image, so there was nothing else "
            "to remove."
        )
    elif found is not None:
        message = (
            f"Removed {removed[0]}. No detail part covers the mirrored cell {_at(*twin_cell)}, "
            "so only one was removed."
        )
    else:
        message = (
            f"No detail part covers {_at(x, y, z)}, but its mirror image did: removed {removed[0]}."
        )
    return True, 0, message


def _apply_one(design: Design, op: Any, catalog: Catalog) -> tuple[bool, int, str]:
    """Apply one operation. Returns (applied, cells_changed, message); raises _OpError."""
    parsed = _parse_op(op, catalog)
    if parsed.name in SHAPE_OPS:
        applied, n, message = _apply_shape_op(design, parsed, catalog)
    elif parsed.name == "place_detail":
        applied, n, message = _place_detail(design, parsed, catalog)
    else:
        applied, n, message = _remove_detail(design, parsed, catalog)
    if applied:
        design.log.append(_plain(op))
    return applied, n, message


def apply_ops(design: Design, ops: list[dict[str, Any]], catalog: Catalog) -> list[OpResult]:
    """Apply ``ops`` to ``design`` in place, in order; see the module docstring."""
    if not isinstance(ops, list | tuple):
        raise ValueError(
            f"apply_ops expects a list of operations, but got {_show(ops)}. Wrap a single "
            "operation in a list: [{...}]."
        )
    results: list[OpResult] = []
    for i, op in enumerate(ops):
        name = op.get("op") if isinstance(op, dict) else None
        label = name if isinstance(name, str) else ""
        try:
            applied, n, message = _apply_one(design, op, catalog)
        except _OpError as err:
            results.append(OpResult(i, label, False, 0, f"Rejected: {err}"))
            continue
        results.append(OpResult(i, label, applied, n, message))
    return results


def replay(base: Design, log: list[dict[str, Any]], catalog: Catalog) -> Design:
    """A copy of ``base`` with every operation in ``log`` applied, in order.

    Raises ValueError if an operation cannot be applied, which means the log was not made
    from this base.
    """
    out = base.copy()
    for i, op in enumerate(log):
        (result,) = apply_ops(out, [op], catalog)
        if not result.applied:
            raise ValueError(
                f"Edit {i + 1} of {len(log)} in the log could not be replayed on the base "
                f"design, so the log does not belong to it. {result.message}"
            )
    return out
