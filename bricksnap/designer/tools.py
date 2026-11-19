"""The designer's five tools, defined once and independent of how the model is run.

The MCP server (for headless Claude Code) and, later, the API runner both read ``TOOLS`` and
call ``call_tool``. Nothing here knows about MCP or about any particular model.

CONTRACT (tests go in tests/test_designer_tools.py)

``TOOLS``: a list of exactly four dicts ``{"name", "description", "input_schema"}`` in this
order: describe, render, apply_ops, rebuild. Descriptions are written for the model: say
what the tool returns, when to use it, and the coordinate conventions (x and y count studs,
z counts plates, a brick is 3 plates, z = 0 is the ground, the front is at y = 0).
``input_schema`` is JSON Schema; ``apply_ops`` embeds ``bricksnap.design.OP_SCHEMA``.

``call_tool(project_path, name, args) -> list[dict]`` returns content blocks:
``{"type": "text", "text": ...}`` and ``{"type": "image", "media_type": "image/png",
"data": <base64 string>}``. It never raises for bad input from the model: an unknown tool
or bad arguments come back as a text block starting "ERROR:" that says what to fix. Each
call opens the project from disk, so state lives only in the project folder.

- describe (no arguments): text only. Grid size and what the units mean; how many cells are
  filled and their bounding box; the colours in use with name, code and cell count; every
  colour available (code and name); the build's part count by kind and the full check
  report text (or a note that there is no build yet); the brief if there is one; how many
  edits have been applied.
- render ``{"views": [...]}`` (optional; default front, right, top, iso): one image, the
  comparison sheet from ``bricksnap.pipeline.render_compare`` (seed on top, current build
  below, same scale), plus a text block explaining how to read it (which row is which, what
  the axis numbers mean).
- apply_ops ``{"ops": [...]}``: applies the operations with ``bricksnap.design.apply_ops``,
  saves the design, and returns one line per operation (applied or rejected and why),
  ending with a reminder that nothing is visible until ``rebuild`` is called.
- rebuild (no arguments): runs ``bricksnap.pipeline.rebuild`` and returns the report text.

STAGE 2 ADDITIONS TO THE CONTRACT

``TOOLS`` now has five entries, in this order: describe, render, brief, apply_ops, rebuild.

- brief ``{"object", "features", "plan", "colours", "finish"}``: the designer's decisions,
  written down before it edits, saved as ``project.meta["brief"]`` (``Project.save_meta``)
  and shown to the person.
    object    one sentence: what this is and which way it faces
    features  two to four strings: what makes it recognisable at this size
    plan      a few sentences: what to exaggerate, simplify or drop
    colours   one to six colour codes from the catalogue: the palette
    finish    one sentence: where it should be smooth, sloped or studded, and why
  Bad input (a missing field, an unknown colour code, too many features) comes back as an
  "ERROR:" block saying what to fix, and nothing is saved. A later call replaces the brief.
  The reply repeats the saved brief in plain words.
- apply_ops refuses to run until the project has a brief: "ERROR: write the brief first
  (call brief) ...". A project that already has one from an earlier run does not need
  another.
- describe also reports: the brief; how many cells are marked smooth and how many sloped;
  the detail parts (name, colour, position), or that there are none; every detail part that
  may be placed (id, name, size in cells, whether it has a stud on top, how many colours it
  is made in); and the build's notes (what the make-buildable and finishing passes did or
  could not do), each on its own line.
- rebuild returns the build's notes before the check report, under a line that says they
  are changes the software made by itself.
- render is unchanged: seed on top, current build below.
- The apply_ops description explains the stage 2 operations (set_finish, place_detail,
  remove_detail, the "mirror" option) with one example each; the schema comes from
  ``bricksnap.design.OP_SCHEMA`` as before.

STAGE 4 ADDITION TO THE CONTRACT: sideways parts

- The apply_ops description says, with one example, that a one-stud, one-plate detail may
  lie flat on a face (``"face"`` in place_detail, see ``bricksnap.design``).
- describe: a sideways detail's line ends with the face it is on, and with "NOT BUILT" when
  the current build left it off (the build's notes say why); a detail part that may
  lie on a face (``Catalog.can_face_sideways``) says so in the list of detail parts; a
  sideways detail stands on nothing, so it does not count as covering the cell under its
  column when describe counts where a finish shows.

Implementation notes
--------------------
- ``describe`` also lists the filled cells layer by layer (consecutive plates with the same
  outline are merged into one line), so the model can read coordinates as text and not only
  off the pictures, and it says when the design has edits that have not been rebuilt yet.
- A build is "out of date" when it was not made from the design as it is now
  (``Project.build_is_current`` compares the Design's fingerprint, which covers cells, finish
  and details, with the one the Build recorded); ``render`` says so in its text, because the
  bottom row then still shows the old build.
- ``render`` with the default views writes ``renders/compare.png`` through
  ``pipeline.render_compare``; other views go to ``renders/compare-<views>.png`` through
  ``render.compare_sheet`` with the same inputs. A PNG over ``MAX_IMAGE_BYTES`` is reduced to
  an adaptive palette, and then scaled down, until it fits (a compare sheet of a typical
  model is far smaller than that).
- Every failure inside a tool (a missing project, an unreadable project.json, a solver
  error) becomes an "ERROR:" text block in plain words; no traceback reaches the model. When
  the problem is one the model's tools cannot fix (no project, no design), the text says so.
- No text sent to the model holds the project's absolute path (it normally contains the home
  folder and user name): it is replaced by "the project folder", and ``runner.redact`` then
  hides e-mail addresses and the home folder.
- ``render`` loads the seed once to know whether the picture has a seed row; when the seed
  cannot be loaded the text says the picture has one row, the build.
- ``describe`` puts what matters first and the reference lists last: grid and bounding box,
  brief, build and check report, the software's notes, the layers, colours in use (each
  marked when it is not in the brief's palette), finish marks and details, the edit count,
  then the finish words, the detail parts and the colours available. For each finish word
  it gives the number of cells, their bounding box and how many of them have nothing above
  (no filled cell and no detail), since a finish shows only there. Each detail part line
  gives its size as x by y at rot 0, its height in plates, its studs, which way a slope's
  face runs down at rot 0 (``Catalog.low_side``), how many colours it is made in and which
  of the brief's palette colours it is made in. The grid section gives the left-right
  middle and the cell pairing that "mirror" uses.
- brief is strict: every field is required, unknown fields are rejected (with a hint for
  near misses such as "colors"), texts must be non-empty strings of limited length
  (``BRIEF_LIMITS``), colour codes are whole numbers in the catalogue (3.0 counts as 3,
  booleans never do), each listed once. Every problem is listed in one reply, so one retry
  can fix them all. The saved brief is a plain dict with exactly the five fields (texts
  stripped, codes as ints). The reply also names the colours in the design that are not in
  the palette, so the model can act on them.
- A project "has a brief" when ``project.meta["brief"]`` is a non-empty string (an older
  free-text brief) or a non-empty dict. Without a design, apply_ops reports the missing
  design (which the model cannot fix) rather than asking for a brief.
- apply_ops lines: place_detail and remove_detail say "applied." with the operation's own
  message (they change no cells); set_finish says on how many cells the finish changed.
- A ``project.json`` that is valid JSON but not an object is treated as unreadable.
- The left-right middle in ``describe`` is given in cell indices, the numbers box corners and
  shape centres use: (nx - 1) / 2, which is the cell in the middle for an odd width and lies
  between two cells (x = 4.5 for nx = 10) for an even one. A shape centred there is its own
  mirror image.
- An ``OSError`` (a file that could not be read or written) is reported from its reason and
  the file's place in the project folder ("File exists: the project folder/renders"), never
  from ``str(e)``, which prints the whole path. As a second line of defence ``_scrub`` also
  replaces the project path and the home folder in the escaped form ``repr`` gives them
  (doubled backslashes, escaped control characters).
- Names the model sent and that an error repeats (unknown argument names, an unknown tool or
  view, unknown brief fields) are each cut to 40 characters, and at most ``MAX_ECHOED`` of
  them are listed, followed by "and N more", so an error stays short however much was sent.
- Part counts by kind use plain words (``_KIND_WORDS``): "round tiles", "dishes", "clip or
  jumper plates" (the catalogue kind "detail"), never the catalogue's identifiers.
"""

from __future__ import annotations

import base64
import contextlib
import difflib
import io
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from bricksnap.design import OP_SCHEMA
from bricksnap.project import Project, ProjectError
from bricksnap.types import FINISH_NAMES, FINISH_STUDS, PLATES_PER_BRICK, Placement

DEFAULT_VIEWS = ("front", "right", "top", "iso")
ALL_VIEWS = ("front", "right", "back", "left", "top", "iso")
MAX_OPS_PER_CALL = 100
MAX_IMAGE_BYTES = 400_000

BRIEF_FIELDS = ("object", "features", "plan", "colours", "finish")
MIN_FEATURES = 2
MAX_FEATURES = 4
MAX_PALETTE = 6
BRIEF_LIMITS = {"object": 300, "feature": 160, "plan": 1500, "finish": 400}
"""Most characters allowed in each text of the brief (``feature`` is per feature)."""

_COORDS = (
    "Coordinates: every position is a grid cell [x, y, z]. x counts studs from left to right "
    "as seen from the front; y counts studs from the front (y = 0) towards the back; z counts "
    "PLATES upwards from the ground (z = 0 is the bottom layer). A brick is 3 plates tall, so "
    "one cell is 2.5 times wider than it is tall."
)

_BRIEF_FIELD_HELP = (
    '"object" (one sentence: what it is and which way it faces), "features" (2 to 4 short '
    'strings), "plan" (a few sentences), "colours" (1 to 6 colour codes) and "finish" (one '
    "sentence)"
)


def _colour_codes() -> list[int]:
    from bricksnap.catalog import load_catalog

    return sorted(load_catalog().colours)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "describe",
        "description": (
            "Describe the current design and build as text, most important first: the grid "
            "size, valid coordinate ranges and bounding box of the filled cells; the brief; "
            "the parts in the current build by kind and the full check report (loose parts, "
            "whether it stands, weak spots with coordinates); what the software changed or "
            "could not do by itself in the last rebuild; the filled area layer by layer; the "
            "colours in use (name, code, cell count); where cells are marked smooth or "
            "sloped; the detail parts placed; and how many edits have been applied. Last come "
            "reference lists: the finish words, every detail part you may place (id, name, "
            "size, height, studs, which way a slope faces, colours) and every colour you may "
            "use (code and name). Call it first, and again whenever you need exact "
            "numbers. " + _COORDS
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "render",
        "description": (
            "Show the model as one picture: the seed (the original 3D model) in the top row "
            "and the current build in the bottom row, drawn from the same viewpoints at the "
            "same scale so they can be compared directly. Each straight-on view has numbered "
            "axes: x and y in studs, z in plates, numbered at every brick (0, 3, 6, ...), and "
            "one faint grid line per stud and per plate. Views: front (picture right is +x), "
            "right (looking at the +x side; picture right is +y, towards the back), back "
            "(picture right is -x), left (picture right is -y), top (looking down; picture "
            "right is +x, picture up is +y, so the front is at the bottom) and iso (a "
            "three-quarter view from the front right, without numbers). The picture shows "
            "the last rebuild: call rebuild first to see your edits. " + _COORDS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "views": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(ALL_VIEWS)},
                    "minItems": 1,
                    "maxItems": len(ALL_VIEWS),
                    "uniqueItems": True,
                    "description": "Which views to draw, left to right. Default: "
                    + ", ".join(DEFAULT_VIEWS)
                    + ".",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "brief",
        "description": (
            "Write down your decisions before you edit: what the object is, what makes it "
            "recognisable at this size, your plan, your palette, and where the surface "
            "should be smooth, sloped or studded. The person reads the brief, it is saved "
            "with the project, and describe shows it near the top every time, so judge each "
            "edit against it. apply_ops refuses to run until the project has a brief. Call "
            "brief after you have looked (describe and render) and before your first "
            "apply_ops; call it again to replace the brief if your plan changes. Returns the "
            'saved brief, or "ERROR:" with everything to fix (then nothing is saved).'
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": BRIEF_LIMITS["object"],
                    "description": "One sentence: what this is and which way it faces.",
                },
                "features": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": BRIEF_LIMITS["feature"],
                    },
                    "minItems": MIN_FEATURES,
                    "maxItems": MAX_FEATURES,
                    "description": (
                        "Two to four short phrases: what makes it recognisable at this size."
                    ),
                },
                "plan": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": BRIEF_LIMITS["plan"],
                    "description": "A few sentences: what to exaggerate, simplify or drop.",
                },
                "colours": {
                    "type": "array",
                    "items": {"type": "integer", "enum": _colour_codes()},
                    "minItems": 1,
                    "maxItems": MAX_PALETTE,
                    "uniqueItems": True,
                    "description": "One to six colour codes from describe: the palette.",
                },
                "finish": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": BRIEF_LIMITS["finish"],
                    "description": (
                        "One sentence: where it should be smooth, sloped or studded, and why."
                    ),
                },
            },
            "required": list(BRIEF_FIELDS),
            "additionalProperties": False,
        },
    },
    {
        "name": "apply_ops",
        "description": (
            "Edit the design with a list of operations, applied in order. Write the brief "
            "first: apply_ops refuses to run until the project has one. Returns one line per "
            "operation: applied, or rejected and why; a rejected operation changes nothing "
            "and does not stop the others, so later operations in the same call still run "
            "on the design as it then is.\n"
            "Cell edits, each on a shape: add fills EMPTY cells with a colour; remove empties "
            "filled cells; paint recolours filled cells; set_finish marks what the top of the "
            'filled cells should be: "studs" (the default), "smooth" (tiles) or "sloped" (a '
            "slope where the surface steps down). A shape is a box "
            '{"type": "box", "min": [x, y, z], "max": [x, y, z]} with both corners '
            'included, or an ellipsoid {"type": "ellipsoid", "center": [x, y, z], "radius": '
            '[rx, ry, rz]}. Colours are codes from describe. Example: {"op": "add", "shape": '
            '{"type": "box", "min": [0, 0, 0], "max": [1, 1, 2]}, "color": 4} is a 2-stud-wide, '
            "1-brick-tall red block at the front left of the ground.\n"
            "Finish: the software chooses tiles and slopes itself from the finish marks; you "
            "never place them, except as details. A finish shows only on cells with nothing "
            'above them. Example: {"op": "set_finish", "shape": {"type": "box", "min": [2, 0, '
            '11], "max": [7, 3, 11]}, "finish": "smooth"}.\n'
            "Details: place_detail stands one small part from describe's detail list in "
            'EMPTY cells directly above filled ones. "at" is its lowest corner cell (its '
            "smallest x, y and z), so its z is one above the top filled cell it stands on. "
            '"rot" is 0, 90, 180 or 270; describe says which way each slope faces at rot 0. '
            "Example, a black round tile as an eye on top of the filled cell [3, 0, 11]: "
            '{"op": "place_detail", "part": "98138", "color": 0, "at": [3, 0, 12], "rot": 0}. '
            "remove_detail removes the detail covering a cell: "
            '{"op": "remove_detail", "at": [3, 0, 12]}. Details follow the grid: filling a '
            "detail's cell or emptying the cell below it removes the detail. A one-stud, "
            'one-plate detail can instead lie flat on a face with "face": "front", "right", '
            '"back" or "left": "at" is then the lowest of three empty cells in front of the '
            "face (z a multiple of 3), the three cells behind must be filled, and a brick with "
            "a stud on its side goes there to hold it. Example, an eye on a face whose front "
            'cells are at y = 1: {"op": "place_detail", "part": "98138", "color": 0, "at": '
            '[3, 0, 9], "face": "front"}. The three cells behind must be one colour; the brick '
            "takes it and shows around a round tile's edges, so keep them the face's colour, "
            "not the eye's.\n"
            'Mirror: add "mirror": true to any operation to apply it also to its mirror image '
            "across the model's left-right middle (cell x pairs with cell nx - 1 - x; describe "
            'gives nx). Example: {"op": "paint", "shape": {"type": "box", "min": [2, 3, 30], '
            '"max": [3, 4, 33]}, "color": 25, "mirror": true} paints both ears.\n'
            "A remove that would leave the design completely empty is rejected: to start "
            "over, first remove everything except the cells you will keep (for example the "
            "feet), add the new shapes, then remove what is left over. Each part is one "
            "colour, so a feature in its own colour that touches the body only at its side "
            "comes loose; painting a stud or two of hidden cells behind it in the same colour "
            "lets its parts reach into the body and hold. Put related edits in one call (at "
            f"most {MAX_OPS_PER_CALL}). Edits are saved at once but are NOT visible in render "
            "until you call rebuild. " + _COORDS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ops": {
                    "type": "array",
                    "items": OP_SCHEMA,
                    "minItems": 1,
                    "maxItems": MAX_OPS_PER_CALL,
                    "description": "The operations, applied in order.",
                }
            },
            "required": ["ops"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rebuild",
        "description": (
            "Turn the current design into real bricks and plates, finish it (tiles, slopes, "
            "details), check the result, and return: the part count; what the software "
            "changed or could not do by itself (it may, for example, thicken a thin sheet or "
            "skip a slope; your saved design is not changed by this); and the check report: "
            "whether everything is connected in one piece that reaches the ground, whether it "
            "stands, and weak spots in plain words with coordinates (x and y in studs, z in "
            "plates). Call it after apply_ops and before render. If the report says parts are "
            "loose or the model does not stand, fix that first."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

TOOL_NAMES = tuple(t["name"] for t in TOOLS)


# ---- helpers ------------------------------------------------------------------------------


def _text(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _error(text: str) -> list[dict[str, Any]]:
    return [_text("ERROR: " + text)]


def _catalog():
    from bricksnap.catalog import load_catalog

    return load_catalog()


def _span(lo: int, hi: int) -> str:
    return str(lo) if lo == hi else f"{lo} to {hi}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# Catalogue part kinds in plain words (one, many). A kind not listed here is shown with its
# underscores as spaces and a plain English plural.
_KIND_WORDS = {
    "round_tile": ("round tile", "round tiles"),
    "round_brick": ("round brick", "round bricks"),
    "round_plate": ("round plate", "round plates"),
    "curved_slope": ("curved slope", "curved slopes"),
    "slope_inverted": ("inverted slope", "inverted slopes"),
    "side_stud": ("brick with side studs", "bricks with side studs"),
    "detail": ("clip or jumper plate", "clip or jumper plates"),
    "dish": ("dish", "dishes"),
}


def _kind_count(n: int, kind: str) -> str:
    """ "3 round tiles", "1 dish", "2 dishes": a count of parts of one catalogue kind."""
    one, many = _KIND_WORDS.get(kind, (None, None))
    if one is None or many is None:
        one = kind.replace("_", " ")
        many = one + ("es" if one.endswith(("s", "sh", "ch", "x")) else "s")
    return f"{n} {one if n == 1 else many}"


def _count_by_kind(build, catalog) -> str:
    """The build's parts counted by kind, most common first, or "none"."""
    kinds: Counter[str] = Counter()
    for p in build.parts:
        part = catalog.parts.get(p.part)
        kinds[part.kind if part else "unknown part"] += 1
    return ", ".join(_kind_count(n, k) for k, n in kinds.most_common()) or "none"


def _bbox(mask: np.ndarray) -> str:
    """ "x a to b, y c to d, z e to f" for the True cells of a non-empty [x, y, z] mask."""
    xs, ys, zs = np.nonzero(mask)
    return (
        f"x {_span(int(xs.min()), int(xs.max()))}, y {_span(int(ys.min()), int(ys.max()))}, "
        f"z {_span(int(zs.min()), int(zs.max()))}"
    )


def _build_out_of_date(project: Project) -> bool:
    """True when there is a build and it was not made from the design as it is now."""
    if not project.has_build() or not project.has_design():
        return False
    try:
        return not project.build_is_current()
    except Exception:  # a damaged file is reported by whichever tool reads it next
        return False


def _colour_label(catalog, code: int) -> str:
    colour = catalog.colours.get(int(code))
    return f"{colour.name} ({code})" if colour else f"unknown colour ({code})"


def _check_no_args(name: str, args: dict[str, Any]) -> str | None:
    if args:
        keys = _names(args)
        return f"{name} takes no arguments, but got: {keys}. Call it with an empty object {{}}."
    return None


MAX_ECHOED = 5  # names the model sent that are repeated back in one error, at most


def _clip(text: str, limit: int = 40) -> str:
    """``text`` on one line and at most ``limit`` characters (cut ones end in "...")."""
    text = " ".join(text.split("\n"))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _names(names: Any) -> str:
    """Names the model sent (argument names, a tool name), sorted, each shortened, and at
    most ``MAX_ECHOED`` of them followed by "and N more", so that an error stays short
    however much was sent."""
    shown = sorted(_clip(str(n)) for n in names)
    text = ", ".join(shown[:MAX_ECHOED])
    if len(shown) > MAX_ECHOED:
        text += f" and {len(shown) - MAX_ECHOED} more"
    return text


def _show(value: Any, limit: int = 40) -> str:
    """A short, safe rendering of a value the model sent (never fails, even on huge numbers)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value) if -(10**15) < value < 10**15 else "a very large number"
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else "a number that is not finite"
    if isinstance(value, str):
        return '"' + _clip(value, limit) + '"'
    if isinstance(value, list | tuple):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return "a value of an unexpected kind"


def _whole(value: Any) -> int | None:
    """``value`` as an int when it is a whole number (3 or 3.0, never a boolean)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


_SIDE_WORDS = {
    (0, -1): "-y (the front)",
    (0, 1): "+y (the back)",
    (1, 0): "+x (the right)",
    (-1, 0): "-x (the left)",
}


def _slope_words(catalog, part_id: str, rot: int = 0) -> str | None:
    """Which way a slope's face runs down as placed, in words; None for other parts."""
    try:
        side = catalog.low_side(Placement(part=part_id, color=0, x=0, y=0, z=0, rot=int(rot)))
    except Exception:  # an unknown part or a rotation that is not a right angle
        return None
    return _SIDE_WORDS.get(side) if side else None


# ---- the brief ----------------------------------------------------------------------------

_BRIEF_ALIASES = {
    "colors": "colours",
    "color": "colours",
    "colour": "colours",
    "palette": "colours",
    "feature": "features",
    "subject": "object",
    "what": "object",
    "finishes": "finish",
    "surface": "finish",
    "plans": "plan",
}


def _field_hint(key: str) -> str:
    if len(key) > 40:  # nothing that long is a misspelt field name
        return ""
    guess = _BRIEF_ALIASES.get(key.lower())
    if guess is None:
        close = difflib.get_close_matches(key.lower(), BRIEF_FIELDS, n=1, cutoff=0.6)
        guess = close[0] if close else None
    return f' (did you mean "{guess}"?)' if guess else ""


def _check_text(value: Any, name: str, limit: int, what: str, problems: list[str]) -> str:
    if not isinstance(value, str):
        problems.append(f'"{name}" must be text ({what}), not {_show(value)}.')
        return ""
    text = value.strip()
    if not text:
        problems.append(f'"{name}" is empty; write {what}.')
    elif len(text) > limit:
        problems.append(
            f'"{name}" has {len(text)} characters; keep it to {limit} or fewer ({what}).'
        )
    return text


def _parse_brief(args: dict[str, Any], catalog) -> tuple[dict[str, Any] | None, list[str]]:
    """The brief to save, or None and every problem found, each worded for the model."""
    problems: list[str] = []
    extra = [key for key in args if key not in BRIEF_FIELDS]
    for key in extra[:MAX_ECHOED]:
        problems.append(f"{_show(str(key))} is not a field of the brief{_field_hint(str(key))}.")
    if len(extra) > MAX_ECHOED:
        problems.append(
            f"and {len(extra) - MAX_ECHOED} more fields that are not part of the brief (send "
            "only " + ", ".join(f'"{f}"' for f in BRIEF_FIELDS) + ")."
        )
    missing = [f for f in BRIEF_FIELDS if f not in args]
    if missing:
        problems.append("missing: " + ", ".join(f'"{f}"' for f in missing) + ".")

    brief: dict[str, Any] = {}
    if "object" in args:
        brief["object"] = _check_text(
            args["object"],
            "object",
            BRIEF_LIMITS["object"],
            "one sentence: what this is and which way it faces",
            problems,
        )
    if "features" in args:
        raw = args["features"]
        if isinstance(raw, str):
            problems.append(
                f'"features" must be a list of {MIN_FEATURES} to {MAX_FEATURES} short '
                'strings, for example ["big pointed ears", "long curled tail"], not one string.'
            )
        elif not isinstance(raw, list):
            problems.append(
                f'"features" must be a list of {MIN_FEATURES} to {MAX_FEATURES} short '
                f"strings, not {_show(raw)}."
            )
        else:
            if not MIN_FEATURES <= len(raw) <= MAX_FEATURES:
                problems.append(
                    f'"features" has {len(raw)}; give {MIN_FEATURES} to {MAX_FEATURES}: only '
                    "what makes the object recognisable at this size."
                )
            feats = []
            for i, item in enumerate(raw[: MAX_FEATURES * 4], start=1):
                feats.append(
                    _check_text(
                        item,
                        f"features item {i}",
                        BRIEF_LIMITS["feature"],
                        "a short phrase",
                        problems,
                    )
                )
            brief["features"] = feats
    if "plan" in args:
        brief["plan"] = _check_text(
            args["plan"],
            "plan",
            BRIEF_LIMITS["plan"],
            "a few sentences: what to exaggerate, simplify or drop",
            problems,
        )
    if "colours" in args:
        raw = args["colours"]
        if isinstance(raw, int | float) and not isinstance(raw, bool):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            problems.append(
                f'"colours" must be a list of 1 to {MAX_PALETTE} colour codes from describe, '
                f"for example [15, 0, 4], not {_show(raw)}."
            )
        else:
            if len(raw) > MAX_PALETTE:
                problems.append(
                    f'"colours" has {len(raw)} codes; choose at most {MAX_PALETTE}. Few '
                    "colours with strong contrast read best."
                )
            codes: list[int] = []
            unknown: list[str] = []
            for item in raw[: MAX_PALETTE * 4]:
                code = _whole(item)
                if code is None or code not in catalog.colours:
                    unknown.append(_show(item))
                elif code in codes:
                    problems.append(f'"colours" lists {code} twice; give each code once.')
                else:
                    codes.append(code)
            if unknown:
                problems.append(
                    f'"colours" has {", ".join(unknown)}, which '
                    + ("is not a colour code" if len(unknown) == 1 else "are not colour codes")
                    + " in the catalogue. Use the codes listed under COLOURS AVAILABLE in "
                    "describe."
                )
            brief["colours"] = codes
    if "finish" in args:
        brief["finish"] = _check_text(
            args["finish"],
            "finish",
            BRIEF_LIMITS["finish"],
            "one sentence: where it should be smooth, sloped or studded, and why",
            problems,
        )
    if problems:
        return None, problems
    return {f: brief[f] for f in BRIEF_FIELDS}, []


def _has_brief(project: Project) -> bool:
    brief = project.meta.get("brief")
    if isinstance(brief, str):
        return bool(brief.strip())
    return isinstance(brief, dict) and bool(brief)


def _brief_lines(brief: Any, catalog) -> list[str]:
    """The brief in plain words, one item per line."""
    if isinstance(brief, str):
        return [brief.strip()]
    if not isinstance(brief, dict):
        return [str(brief)]
    lines: list[str] = []
    if brief.get("object"):
        lines.append(f"What it is: {brief['object']}")
    features = brief.get("features")
    if isinstance(features, list) and features:
        lines.append("What makes it recognisable:")
        lines.extend(f"  - {f}" for f in features)
    elif features:
        lines.append(f"What makes it recognisable: {features}")
    if brief.get("plan"):
        lines.append(f"Plan: {brief['plan']}")
    colours = brief.get("colours")
    if isinstance(colours, list) and colours:
        names = [
            _colour_label(catalog, code) if (code := _whole(c)) is not None else _show(c)
            for c in colours
        ]
        lines.append("Palette: " + ", ".join(names))
    if brief.get("finish"):
        lines.append(f"Finish: {brief['finish']}")
    for key, value in brief.items():  # anything else someone wrote into project.json
        if key not in BRIEF_FIELDS and value:
            lines.append(f"{key}: {value}")
    return lines or ["(the saved brief is empty)"]


def _palette(project: Project) -> list[int]:
    """The brief's colour codes, or [] when there is no brief with colours."""
    brief = project.meta.get("brief")
    if not isinstance(brief, dict) or not isinstance(brief.get("colours"), list):
        return []
    return [c for c in (_whole(v) for v in brief["colours"]) if c is not None]


def _brief(project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = _catalog()
    brief, problems = _parse_brief(args, catalog)
    if brief is None:
        return _error(
            "the brief was not saved. Fix these and call brief again with all five fields:\n"
            + "\n".join(f"- {p}" for p in problems)
        )
    replaced = _has_brief(project)
    project.meta["brief"] = brief
    project.save_meta()
    lines = [
        ("Brief replaced. " if replaced else "Brief saved. ")
        + "The person can read it, and describe shows it near the top from now on.",
        "",
        *_brief_lines(brief, catalog),
    ]
    if project.has_design():
        with contextlib.suppress(Exception):  # the reply is still useful without this
            design = project.load_design()
            codes, counts = np.unique(design.colors[design.filled], return_counts=True)
            outside = [
                f"{_colour_label(catalog, int(c))} on {_plural(int(n), 'cell')}"
                for c, n in sorted(
                    zip(codes.tolist(), counts.tolist(), strict=True), key=lambda t: -t[1]
                )
                if int(c) not in brief["colours"]
            ]
            if outside:
                lines.append("")
                lines.append(
                    "Colours in the design now that are not in this palette: "
                    + "; ".join(outside)
                    + ". Paint them with palette colours, or add them to the palette if "
                    "they should stay."
                )
    lines.append("")
    lines.append(
        "Next: edit with apply_ops and judge each change against this brief. Call brief "
        "again to replace it if your plan changes."
    )
    return [_text("\n".join(lines))]


# ---- describe -----------------------------------------------------------------------------


def _layers(filled: np.ndarray) -> list[str]:
    """One line per run of plates whose filled outline is the same."""
    lines: list[str] = []
    nz = filled.shape[2]
    runs: list[tuple[int, int, str]] = []
    for z in range(nz):
        layer = filled[:, :, z]
        if not layer.any():
            key = ""
        else:
            xs, ys = np.nonzero(layer)
            key = (
                f"x {_span(int(xs.min()), int(xs.max()))}, "
                f"y {_span(int(ys.min()), int(ys.max()))}, {_plural(int(layer.sum()), 'cell')}"
            )
        if runs and runs[-1][2] == key and runs[-1][1] == z - 1:
            runs[-1] = (runs[-1][0], z, key)
        else:
            runs.append((z, z, key))
    top = max((r[1] for r in runs if r[2]), default=-1)
    for lo, hi, key in runs:
        if not key:
            if lo <= top:
                lines.append(f"  z {_span(lo, hi)}: empty")
            continue
        each = " each" if hi > lo else ""
        lines.append(f"  z {_span(lo, hi)}: {key}{each}")
    if top < nz - 1:
        lines.append(f"  z {_span(top + 1, nz - 1)}: empty (room to build upwards)")
    return lines


def _detail_cells(design, catalog) -> np.ndarray:
    """Boolean [x, y, z] array: True where a placed detail part stands. A detail on a face
    stands on nothing, so it is left out."""
    taken = np.zeros(design.shape, dtype=bool)
    for d in design.details:
        if d.face != "top":
            continue
        with contextlib.suppress(Exception):  # an unknown part takes no cells we can know
            p = Placement(part=d.part, color=d.color, x=d.x, y=d.y, z=d.z, rot=d.rot)
            sx, sy, sz = catalog.cells(p)
            taken[
                max(sx.start, 0) : max(sx.stop, 0),
                max(sy.start, 0) : max(sy.stop, 0),
                max(sz.start, 0) : max(sz.stop, 0),
            ] = True
    return taken


def _finish_lines(design, catalog) -> list[str]:
    filled = design.filled
    covered = np.zeros_like(filled)
    covered[:, :, :-1] = filled[:, :, 1:] | _detail_cells(design, catalog)[:, :, 1:]
    exposed = filled & ~covered
    lines: list[str] = []
    for word, value in FINISH_NAMES.items():
        if value == FINISH_STUDS:
            continue
        marked = filled & (design.finish == value)
        n = int(marked.sum())
        if not n:
            lines.append(f"  {word}: no cells")
            continue
        shows = int((marked & exposed).sum())
        lines.append(
            f"  {word}: {_plural(n, 'cell')} ({_bbox(marked)}); {shows} of them "
            f"{'has' if shows == 1 else 'have'} nothing above, so the finish shows there"
        )
    return lines


def _details_lines(design, catalog, build=None) -> list[str]:
    if not design.details:
        return ["  none"]
    lines = []
    for d in design.details:
        part = catalog.parts.get(d.part)
        name = f"{part.name} ({d.part})" if part else f"unknown part {d.part}"
        line = f"  {name}, {_colour_label(catalog, d.color)}, at [{d.x}, {d.y}, {d.z}], rot {d.rot}"
        side = _slope_words(catalog, d.part, d.rot)
        if side:
            line += f", slopes down to {side}"
        if d.face != "top":
            line += f", on the {d.face} face (held by a side stud)"
            built = build is None or any(
                (p.part, p.color, p.x, p.y, p.z, p.face) == (d.part, d.color, d.x, d.y, d.z, d.face)
                for p in build.parts
            )
            if not built:
                line += "; NOT BUILT: the rebuild left it off (its note says why)"
        lines.append(line)
    return lines


def _studs_words(part) -> str:
    cells = part.sx * part.sz
    n = len(part.studs_top)
    if n == 0:
        return "no stud on top"
    if n >= cells:
        return "stud on top" if cells == 1 else "studs on top"
    return f"stud on {n} of its {cells} cells"


def _detail_part_lines(catalog, palette: list[int]) -> list[str]:
    lines = []
    for part in catalog.detail_parts():
        bits = [
            f"{part.sx} x {part.sz} cells",
            _plural(part.h, "plate"),
            _studs_words(part),
        ]
        side = _slope_words(catalog, part.id, 0)
        if side:
            bits.append(f"slopes down to {side}")
        if catalog.can_face_sideways(part.id):
            bits.append("may lie on a face")
        made = f"{len(part.colours)} colours"
        if palette:
            lacking = [str(c) for c in palette if c not in part.colours]
            if not lacking:
                made += ", all of your palette"
            elif len(lacking) == len(palette):
                made += ", none of your palette"
            else:
                made += ", all of your palette but " + ", ".join(lacking)
        bits.append(made)
        lines.append(f"  {part.id} {part.name}: " + ", ".join(bits))
    return lines


def _middle_words(nx: int) -> str:
    """Where the left-right middle of an ``nx``-wide grid is, in cell indices (the numbers
    that box corners and shape centres use): the mirror x -> nx - 1 - x keeps it fixed."""
    centre = f"{(nx - 1) / 2:g}"
    between = f"lies between cells {nx // 2 - 1} and {nx // 2}"
    where = f"is cell {centre}" if nx % 2 else between
    return (
        f"The left-right middle {where} (x = {centre} as a shape centre): "
        f'"mirror" pairs cell x with cell {nx - 1} - x.'
    )


def _describe(project: Project) -> list[dict[str, Any]]:
    catalog = _catalog()
    design = project.load_design()
    nx, ny, nz = design.shape
    filled = design.filled
    palette = _palette(project)
    count = int(filled.sum())
    out: list[str] = []

    out.append(f"Project: {project.name}")
    out.append("")
    out.append("GRID")
    out.append(
        f"{nx} x {ny} x {nz} cells: x from 0 to {nx - 1}, y from 0 to {ny - 1}, "
        f"z from 0 to {nz - 1}. " + _COORDS
    )
    out.append(
        "One cell is 8 mm wide, 8 mm deep and 3.2 mm tall. The grid has empty room around and "
        "above the model so that you can add to it. " + _middle_words(nx)
    )
    if count:
        xs, ys, zs = np.nonzero(filled)
        out.append(
            f"{count} filled cells. Bounding box: {_bbox(filled)} "
            f"({int(xs.max() - xs.min() + 1)} studs wide, {int(ys.max() - ys.min() + 1)} studs "
            f"deep, {int(zs.max() - zs.min() + 1)} plates tall, which is about "
            f"{(zs.max() - zs.min() + 1) / PLATES_PER_BRICK:.1f} bricks)."
        )
    else:
        out.append("No cells are filled.")
    out.append("")

    out.append("BRIEF")
    if _has_brief(project):
        out.extend(_brief_lines(project.meta.get("brief"), catalog))
    else:
        out.append(
            "No brief has been written for this project. Call brief (object, features, plan, "
            "colours, finish) before your first apply_ops; apply_ops refuses until there is one."
        )
    out.append("")

    out.append("BUILD")
    build = project.load_build() if project.has_build() else None
    if build is not None:
        out.append(f"{_plural(len(build.parts), 'part')}: {_count_by_kind(build, catalog)}.")
        if _build_out_of_date(project):
            out.append(
                "The design has edits that are not built yet: call rebuild to see them. The "
                "parts, report and notes below are from the previous rebuild."
            )
        out.append("Check report:")
        out.append(build.report.text if build.report else "(no check report saved)")
        out.append("")
        out.append(
            "WHAT THE SOFTWARE DID BY ITSELF in that rebuild (not your edits; your saved "
            "design is not changed by these)"
        )
        out.extend(f"- {n}" for n in build.notes) if build.notes else out.append("- nothing")
    else:
        out.append("There is no build yet. Call rebuild to make one.")
    out.append("")

    if count:
        out.append("LAYER BY LAYER (the extent of the filled cells in each plate)")
        out.extend(_layers(filled))
        out.append("")

    out.append("COLOURS IN USE")
    codes, counts = np.unique(design.colors[filled], return_counts=True)
    for code, n in sorted(zip(codes.tolist(), counts.tolist(), strict=True), key=lambda t: -t[1]):
        mark = " (not in the brief's palette)" if palette and int(code) not in palette else ""
        out.append(f"  {_colour_label(catalog, int(code))}: {_plural(int(n), 'cell')}{mark}")
    if not len(codes):
        out.append("  none")
    out.append("")

    out.append("FINISH MARKS (every other filled cell has studs on top)")
    out.extend(_finish_lines(design, catalog))
    out.append("DETAILS PLACED")
    current = build if build is not None and not _build_out_of_date(project) else None
    out.extend(_details_lines(design, catalog, current))
    out.append("")

    out.append("EDITS")
    out.append(f"{_plural(len(design.log), 'edit operation')} applied since the original design.")
    out.append("")

    out.append("FINISH WORDS (for set_finish)")
    out.append(
        '  "studs" (the default), "smooth" (tiles), "sloped" (a slope where the surface steps '
        "down). The software picks the tiles and slopes."
    )
    out.append(
        "DETAIL PARTS (for place_detail. id name: size as x by y cells at rot 0, height, "
        "studs, for a slope which way its face runs down at rot 0, how many colours it is "
        "made in)"
    )
    out.extend(_detail_part_lines(catalog, palette))
    out.append("COLOURS AVAILABLE (code: name)")
    out.append(
        "  "
        + ", ".join(
            f"{c.code}: {c.name}" for c in sorted(catalog.colours.values(), key=lambda c: c.code)
        )
    )
    return [_text("\n".join(out))]


# ---- render -------------------------------------------------------------------------------


def _png_bytes(img: Image.Image) -> bytes:
    """PNG bytes of ``img``, reduced until they fit in ``MAX_IMAGE_BYTES``."""

    def encode(im: Image.Image) -> bytes:
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    data = encode(img)
    if len(data) <= MAX_IMAGE_BYTES:
        return data
    img = img.convert("RGB")
    current = img.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    data = encode(current)
    scale = 1.0
    while len(data) > MAX_IMAGE_BYTES and scale > 0.3:
        scale *= 0.8
        size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        current = img.resize(size, Image.Resampling.LANCZOS).quantize(
            colors=128, method=Image.Quantize.MEDIANCUT
        )
        data = encode(current)
    return data


def _render(project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
    unknown = [k for k in args if k != "views"]
    if unknown:
        return _error(
            f"render does not take {_names(unknown)}. Its only (optional) argument is "
            f'"views", a list chosen from {", ".join(ALL_VIEWS)}.'
        )
    views = args.get("views", list(DEFAULT_VIEWS))
    if views is None:
        views = list(DEFAULT_VIEWS)
    if (
        not isinstance(views, list)
        or not views
        or not all(isinstance(v, str) for v in views)
        or len(views) > len(ALL_VIEWS)
    ):
        return _error(
            f'"views" must be a list of 1 to {len(ALL_VIEWS)} view names chosen from '
            f'{", ".join(ALL_VIEWS)}, for example ["front", "right"].'
        )
    bad = [v for v in views if v not in ALL_VIEWS]
    if bad:
        return _error(
            f"unknown view {', '.join(_show(v) for v in bad)}. Choose from {', '.join(ALL_VIEWS)}."
        )
    if len(set(views)) != len(views):
        return _error('"views" lists the same view twice. Give each view once.')

    from bricksnap import pipeline

    catalog = _catalog()
    try:  # loading a seed takes milliseconds; it tells us whether the picture has its row
        seed = pipeline.load_project_seed(project)
    except Exception:  # a picture without the seed row is better than no picture
        seed = None
    if tuple(views) == DEFAULT_VIEWS:
        path = pipeline.render_compare(project, catalog=catalog)
    else:
        from bricksnap.render import compare_sheet

        design = project.load_design()
        build = project.load_build() if project.has_build() else None
        path = project.renders_dir / f"compare-{'-'.join(views)}.png"
        compare_sheet(seed, design, build, catalog, views=views).save(path)

    with Image.open(path) as im:
        im.load()
        data = _png_bytes(im)

    current = (
        "build, part by part (each part has a thin dark outline)."
        if project.has_build()
        else "design, cell by cell (there is no build yet; call rebuild)."
    )
    if seed is not None:
        rows = (
            "- Top row: the seed, the original 3D model, placed in the same grid as the build. "
            "Bottom row: the current " + current
        )
    else:
        rows = (
            "- The picture has one row: the current " + current + " The original 3D model "
            "(the seed) could not be loaded, so it is not shown and you cannot compare against "
            "it; rely on describe and the brief instead."
        )
    lines = [
        "How to read the picture:",
        rows,
        "- Each column is one view, named in its caption: " + ", ".join(views) + ".",
        "- front: picture right is +x, up is +z. right: seen from the +x side, picture right "
        "is +y (towards the back). back: picture right is -x. left: picture right is -y. "
        "top: seen from above, picture right is +x and picture up is +y (the front, y = 0, is "
        "at the bottom). iso: three-quarter view from the front right and above, no numbers.",
        "- The numbers along the edges are cell indices: x and y in studs, z in plates, with z "
        "numbered at every brick (0, 3, 6, ...). Each faint grid line is one stud or one plate. "
        "A cell is drawn 2.5 times wider than it is tall, as in real bricks.",
    ]
    if _build_out_of_date(project):
        lines.append(
            "- NOTE: you have edited the design since the last rebuild. The bottom row still "
            "shows the previous build. Call rebuild, then render, to see your edits."
        )
    return [
        {"type": "image", "media_type": "image/png", "data": base64.b64encode(data).decode()},
        _text("\n".join(lines)),
    ]


# ---- apply_ops and rebuild ----------------------------------------------------------------

_NO_CELL_OPS = ("place_detail", "remove_detail")


def _apply_ops(project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
    if not _has_brief(project):
        if not project.has_design():
            raise ProjectError("no design")  # reported as a problem the model cannot fix
        return _error(
            f"write the brief first (call brief) with {_BRIEF_FIELD_HELP}. apply_ops changes "
            "nothing until the project has a brief. Nothing was applied."
        )
    unknown = [k for k in args if k != "ops"]
    if unknown:
        return _error(
            f'apply_ops does not take {_names(unknown)}. Its only argument is "ops", a list '
            'of operations such as {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], '
            '"max": [1, 1, 2]}, "color": 4}.'
        )
    if "ops" not in args:
        return _error(
            'apply_ops needs "ops": a list of operations such as {"op": "paint", "shape": '
            '{"type": "box", "min": [0, 0, 0], "max": [1, 1, 2]}, "color": 4}.'
        )
    ops = args["ops"]
    if isinstance(ops, dict):
        ops = [ops]
    if not isinstance(ops, list) or not ops:
        return _error('"ops" must be a non-empty list of operations (JSON objects).')
    if len(ops) > MAX_OPS_PER_CALL:
        return _error(
            f'"ops" has {len(ops)} operations; send at most {MAX_OPS_PER_CALL} per call. '
            "Nothing was applied."
        )

    from bricksnap.design import apply_ops

    catalog = _catalog()
    design = project.load_design()
    results = apply_ops(design, ops, catalog)
    applied = [r for r in results if r.applied]
    if applied:
        project.save_design(design)
    lines = []
    for r in results:
        what = r.op or "operation"
        extra = f" {r.message}" if r.message else ""
        if not r.applied:
            lines.append(f"{r.index + 1}. {what}: not applied. {r.message}")
        elif what in _NO_CELL_OPS:
            lines.append(f"{r.index + 1}. {what}: applied.{extra}")
        elif what == "set_finish":
            lines.append(
                f"{r.index + 1}. {what}: applied, finish changed on "
                f"{_plural(r.cells_changed, 'cell')}.{extra}"
            )
        else:
            lines.append(
                f"{r.index + 1}. {what}: applied, {_plural(r.cells_changed, 'cell')} changed."
                + extra
            )
    lines.append("")
    lines.append(
        f"{len(applied)} of {len(results)} operations applied; the design now has "
        f"{int(design.filled.sum())} filled cells, {_plural(len(design.details), 'detail')} "
        f"and {_plural(len(design.log), 'edit')} in its log."
    )
    lines.append("Nothing is visible in render until you call rebuild.")
    return [_text("\n".join(lines))]


def _rebuild(project: Project) -> list[dict[str, Any]]:
    from bricksnap import pipeline

    catalog = _catalog()
    build = pipeline.rebuild(project, catalog=catalog)
    report = build.report.text if build.report else "(the checks produced no report)"
    lines = [f"Rebuilt: {_plural(len(build.parts), 'part')} ({_count_by_kind(build, catalog)})."]
    if build.notes:
        lines.append(
            "Changes the software made by itself while building (not your edits; your saved "
            "design is not changed by these):"
        )
        lines.extend(f"- {n}" for n in build.notes)
    else:
        lines.append("The software made no changes by itself while building.")
    lines.append("Check report:")
    lines.append(report)
    lines.append("Call render to see the result.")
    return [_text("\n".join(lines))]


# ---- entry point --------------------------------------------------------------------------


_CANNOT_FIX = (
    " This is a problem with the project itself, and none of your tools can fix it. Stop and "
    "say so in your reply."
)


def _scrub(text: str, project_path: Path) -> str:
    """``text`` without the project's absolute path, e-mail addresses or the home folder."""
    from bricksnap.designer.runner import redact

    forms = {str(project_path.absolute())}
    with contextlib.suppress(OSError):
        forms.add(str(project_path.resolve()))
    # Python's error messages show a file name with repr(), which doubles each backslash
    # (every Windows path) and escapes control characters; hide that form too.
    forms |= {repr(form)[1:-1] for form in forms}
    for form in sorted(forms, key=len, reverse=True):
        if Path(form).is_absolute() and len(form) > 1:
            text = text.replace(form, "the project folder")
    return redact(text)


def call_tool(project_path: str | Path, name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(project_path)
    blocks = _call(path, name, args)
    return [
        {**b, "text": _scrub(str(b.get("text", "")), path)} if b.get("type") == "text" else b
        for b in blocks
    ]


def _call(project_path: Path, name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    if name not in TOOL_NAMES:
        return _error(
            f"there is no tool called {_show(name)}. The tools are {', '.join(TOOL_NAMES)}."
        )
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return _error(f"the arguments to {name} must be a JSON object, for example {{}}.")
    unreadable = (
        "the project's settings file (project.json) could not be read, so the project "
        "cannot be opened." + _CANNOT_FIX
    )
    try:
        project = Project(project_path)
    except ProjectError as e:
        return _error(str(e) + _CANNOT_FIX)
    except Exception:  # project.json is not valid JSON, not UTF-8, unreadable ...
        return _error(unreadable)
    if not isinstance(project.meta, dict):
        return _error(unreadable)
    try:
        if name == "describe":
            problem = _check_no_args(name, args)
            return _error(problem) if problem else _describe(project)
        if name == "render":
            return _render(project, args)
        if name == "brief":
            return _brief(project, args)
        if name == "apply_ops":
            return _apply_ops(project, args)
        problem = _check_no_args(name, args)
        return _error(problem) if problem else _rebuild(project)
    except ProjectError as e:
        if not project.has_design():
            return _error(
                "the project has no design yet, so there is nothing to work on." + _CANNOT_FIX
            )
        if not project.has_build():
            return _error("there is no build yet. Call rebuild first.")
        return _error(str(e))
    except OSError as e:  # a file could not be read or written
        return _error(f"{name} could not finish: {_os_reason(e, project_path)}")
    except Exception as e:  # never hand a traceback to the model
        reason = str(e) or type(e).__name__
        return _error(f"{name} could not finish: {reason}")


def _os_reason(e: OSError, project_path: Path) -> str:
    """What went wrong with a file, built from the reason and the file's place in the project
    folder (or only its name), never from ``str(e)``, which shows the whole path."""
    if not e.strerror:
        return str(e) or type(e).__name__
    names = [_file_words(f, project_path) for f in (e.filename, e.filename2) if f is not None]
    return e.strerror + (": " + " and ".join(names) if names else "")


def _file_words(filename: Any, project_path: Path) -> str:
    """ "the project folder/renders" for a file in the project, else the file's name alone."""
    try:
        path = Path(os.fsdecode(filename))
    except (TypeError, ValueError):
        return "a file"
    for base in (project_path.absolute(), project_path.resolve()):
        with contextlib.suppress(ValueError, OSError):
            rel = path.absolute().relative_to(base).as_posix()
            return "the project folder" + ("" if rel == "." else "/" + rel)
    return path.name or "a file"


__all__ = ["DEFAULT_VIEWS", "TOOLS", "TOOL_NAMES", "call_tool"]
