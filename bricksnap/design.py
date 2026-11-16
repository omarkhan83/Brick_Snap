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
(Stage 2 is being built by the lead's agent; until this line is removed, what follows is
not in the code yet.)

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

from bricksnap.catalog import Catalog, load_catalog
from bricksnap.types import EMPTY, FINISH_STUDS, Design

OPS = ("add", "remove", "paint")
SHAPE_TYPES = ("box", "ellipsoid")
MIN_RADIUS = 0.5
_EPS = 1e-9
_AXES = ("x", "y", "z")

_OP_FIELDS = {
    "add": ("op", "shape", "color"),
    "remove": ("op", "shape"),
    "paint": ("op", "shape", "color"),
}
_SHAPE_FIELDS = {
    "box": ("type", "min", "max"),
    "ellipsoid": ("type", "center", "radius"),
}
_OP_HELP = (
    '"add" (fill empty cells), "remove" (empty filled cells) or "paint" (recolour filled cells)'
)
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

    def operation(name: str, description: str, with_color: bool) -> dict[str, Any]:
        props: dict[str, Any] = {"op": {"const": name}, "shape": shape}
        required = ["op", "shape"]
        if with_color:
            props["color"] = color
            required.append("color")
        return {
            "type": "object",
            "description": description,
            "properties": props,
            "required": required,
            "additionalProperties": False,
        }

    return {
        "title": "Edit operation",
        "description": (
            "One edit to the Design grid. add fills empty cells, remove empties filled cells, "
            "paint recolours filled cells."
        ),
        "type": "object",
        "required": ["op", "shape"],
        "anyOf": [
            operation("add", "Fill the EMPTY cells inside the shape with a colour.", True),
            operation("remove", "Empty the filled cells inside the shape.", False),
            operation("paint", "Recolour the filled cells inside the shape.", True),
        ],
    }


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
        hint = _hint(key, allowed) if isinstance(key, str) else ""
        takes = ", ".join(f'"{f}"' for f in allowed)
        raise _OpError(
            f"{what} has an unexpected field {_show(key)}.{hint} "
            f"It takes exactly these fields: {takes}."
        )


def _triple_field(shape: dict, name: str, what: str, whole: bool) -> tuple:
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


def _parse_color(op: dict, name: str, catalog: Catalog) -> int:
    if "color" not in op:
        raise _OpError(
            f'"{name}" needs a "color": an LDraw colour code from the catalogue. '
            f"Valid codes: {_colour_list(catalog)}."
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
            f"{suggestion} Valid codes: {_colour_list(catalog)}."
        )
    if code not in catalog.colours:
        raise _OpError(
            f"Colour {_int_text(code)} is not in the catalogue. "
            f"Valid codes: {_colour_list(catalog)}."
        )
    return code


def _parse_op(op: Any, catalog: Catalog) -> tuple[str, dict, int | None]:
    if not isinstance(op, dict):
        raise _OpError(
            "Each operation must be an object such as "
            f'{{"op": "add", "shape": {_BOX_EXAMPLE}, "color": 4}}, but this one is {_show(op)}.'
        )
    if "op" not in op:
        raise _OpError(f'The operation is missing "op". Use {_OP_HELP}.')
    name = op["op"]
    if not isinstance(name, str) or name not in OPS:
        hint = _hint(name, OPS) if isinstance(name, str) else ""
        raise _OpError(f"Unknown op {_show(name)}.{hint} Use {_OP_HELP}.")
    what = f'The "{name}" operation'
    if name == "remove" and "color" in op:
        raise _OpError(
            '"remove" does not take a "color" (removed cells become empty). '
            'Delete the "color" field, or use "paint" to recolour cells.'
        )
    _check_fields(op, _OP_FIELDS[name], what)
    if "shape" not in op:
        raise _OpError(f'"{name}" needs a "shape", for example {_BOX_EXAMPLE}.')
    _parse_shape(op["shape"])
    color = _parse_color(op, name, catalog) if name != "remove" else None
    return name, op["shape"], color


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


def _apply_one(design: Design, op: Any, catalog: Catalog) -> tuple[bool, int, str]:
    """Apply one operation. Returns (applied, cells_changed, message); raises _OpError."""
    name, shape, color = _parse_op(op, catalog)
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
    colors = design.colors[region.slices]
    finish = design.finish[region.slices]
    filled = colors != EMPTY
    clip_note = (
        f" Part of the shape lay outside the grid ({_ranges(grid)}) and was ignored."
        if region.clipped
        else ""
    )

    if name == "add":
        assert color is not None
        change = region.mask & ~filled
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
        verb = f"Added {n} cell{'s' if n != 1 else ''} of {_colour_name(catalog, color)}"
    elif name == "remove":
        change = region.mask & filled
        n = int(change.sum())
        if n == 0:
            return False, 0, f"Nothing to remove: every cell inside that {where} is already empty."
        total = int(np.count_nonzero(design.colors != EMPTY))
        if n == total:
            raise _OpError(
                f"That would remove all {n} filled cells and leave the design completely "
                "empty, so it was not done. Remove a smaller region."
            )
        colors[change] = EMPTY
        finish[change] = FINISH_STUDS
        verb = f"Removed {n} cell{'s' if n != 1 else ''}"
    else:
        assert color is not None
        inside = region.mask & filled
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
    design.log.append(_plain(op))
    return True, n, f"{verb} inside the {where}.{clip_note}"


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
