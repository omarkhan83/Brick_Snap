"""The studio's tools: what each pass of ``bricksnap.designer.studio`` can call.

The studio runs several clean-room sessions, each with one job and only the tools that job
needs. The tools are defined here once, independent of how the model is run, in the shape
of ``bricksnap.designer.tools.TOOLS``; ``studio_server`` serves the subset one pass may use.

CONTRACT (tests go in tests/test_studio.py)

``STUDIO_TOOL_NAMES``: describe, render, measure, brief, plan, apply_ops, rebuild, critique.
``tool_definitions(tools, ops) -> list[dict]``: the definitions (``{"name", "description",
"input_schema"}``) of ``tools``, in that order; apply_ops offers only the operations in
``ops`` (``bricksnap.design.studio_op_schema``).

``Session(project_path, tools, ops)``: one pass's tools for one project. ``.call(name, args)``
returns content blocks as ``tools.call_tool`` does and never raises: a tool the pass does not
have, an operation it may not use, or bad arguments come back as one text block starting
"ERROR:" that says what to fix. Every text is scrubbed of the project's path, e-mail
addresses and the home folder (``tools._scrub``). State lives in the project folder, except
whether ``render`` has been called in this session (``critique`` needs that).
``call_tool(project_path, name, args, tools=..., ops=...)`` is one call in a new Session.

- describe (no arguments): the designer's describe text (``tools._describe``) with two more
  sections after the brief: PLAN (the construction plan, or that there is none) and THE
  CONVERSION (its cell count, bounding box, colours and layer-by-layer extent: the numbers
  to plan against and to copy from with the "seed" shape). When the design is empty it
  says so and that rebuild needs cells first.
- render ``{"views", "conversion", "section", "zoom"}``, all optional: one picture and a text
  saying how to read it. Rows: the seed; the conversion, cell by cell, when ``"conversion":
  true`` (always when the design is empty); the current build (or the design when there is
  no build; left out when the design is empty). ``"section": {"axis": "x"|"y"|"z", "at": n}``
  instead draws a cut-through (``render.render_section``) of the current build beside the
  same cut through the conversion. ``"zoom": {"min": [...], "max": [...]}`` or ``{"region":
  name}`` draws the rows of the views at a larger scale, cut down to that box
  (``render.render_zoom``). section and zoom do not go together.
- measure (no arguments): how the design compares with the conversion, as information (the
  plan may change the shape on purpose): the outline match seen from the front, the right
  and the top in percent (cells seen along each axis, shared / either), the cells both
  have, and the largest patches where the design has cells the conversion lacks and where
  it lacks cells the conversion has, each with its cell count, coordinate ranges and the
  plan's region it falls in; for missing cells, whether they are a hollow sealed inside the
  design. Then each planned region's cells in the design and in the conversion.
- brief: ``tools`` brief, unchanged.
- plan ``{"scale", "regions", "interior"}``: the construction plan, saved to
  ``<project>/studio/plan.json``. ``scale``: text. ``regions``: 1 to ``MAX_REGIONS`` items
  ``{"name", "min", "max", "make", "colour", "finish", "note"?}`` (a unique short name, a
  box in the grid, the shape that will make it: one of the studio's shapes, the colour, the
  finish word). ``interior``: null, or ``{"name", "min", "max", "wall", "openings",
  "contents"}`` (the hollow, at least one plate above the ground; wall thickness in studs,
  at least 1). Every problem comes back in one ERROR and nothing is saved. The reply
  repeats the plan with, for each region, how many cells the conversion has in its box.
- apply_ops ``{"ops": [...]}``: ``tools`` apply_ops with the conversion as reference, so
  the studio's shapes work; an operation the pass may not use rejects the whole call
  before anything is applied, naming what this pass may do.
- rebuild (no arguments): ``tools`` rebuild, followed by the outline match line of measure.
  An empty design is refused (add cells first).
- critique ``{"verdict": "good"|"problems", "problems": [...], "summary"}``: the critic's
  report, saved to ``<project>/studio/critique.json``. Each problem is ``{"where",
  "min", "max", "problem", "change"}``: where in words (a plan region's name when one fits),
  the box it concerns, what is wrong as seen in the pictures, what to change. "good" takes
  no problems; "problems" takes 1 to ``MAX_PROBLEMS``, most important first. Refused until
  render has been called in this session.

Implementation notes
--------------------
- The conversion is the project's base design (``Project.load_design(base=True)``), the
  Design voxelised from the seed and never edited.
- Outline match counts cells, not pixels: seen from the front, a column (x, z) is covered
  when any cell along y is filled. So it agrees with the numbers on the pictures' axes and
  is exact; ``bench.outline_match`` (pixels of the seed mesh against a build) answers a
  different question, how faithful a finished build is, and is used by the judge.
- Patches are 6-connected groups of cells (``scipy.ndimage.label``); groups smaller than
  ``MIN_PATCH`` cells are only counted. A patch is named after the region holding most of
  its cells ("mostly in" when not all).
- The critique file is replaced by each call; the studio moves it aside after the session.
"""

from __future__ import annotations

import base64
import contextlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from bricksnap.design import OPS, STUDIO_SHAPE_TYPES, studio_op_schema
from bricksnap.designer import tools as T
from bricksnap.project import Project, ProjectError
from bricksnap.types import FINISH_NAMES, PLATES_PER_BRICK, write_text_atomic

STUDIO_DIR = "studio"
PLAN_FILE = "plan.json"
CRITIQUE_FILE = "critique.json"
STUDIO_TOOL_NAMES = (
    "describe",
    "render",
    "measure",
    "brief",
    "plan",
    "apply_ops",
    "rebuild",
    "critique",
)
MAX_REGIONS = 12
MAX_PROBLEMS = 5
MIN_PATCH = 3
MAX_PATCHES = 5
NAME_LIMIT = 30
PLAN_LIMITS = {"scale": 1200, "note": 300, "openings": 400, "contents": 400}
CRITIQUE_LIMITS = {"where": 80, "problem": 400, "change": 400, "summary": 800}
SECTION_PX = 20
ZOOM_TARGET_PX = 900  # a zoomed view is drawn about this wide or tall, at most
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")


def studio_dir(project: Project) -> Path:
    d = project.path / STUDIO_DIR
    d.mkdir(exist_ok=True)
    return d


def load_plan(project: Project) -> dict[str, Any] | None:
    """The saved construction plan, or None when there is none (or it cannot be read)."""
    try:
        data = json.loads((project.path / STUDIO_DIR / PLAN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("regions"), list) else None


def load_critique(project: Project) -> dict[str, Any] | None:
    try:
        data = json.loads((project.path / STUDIO_DIR / CRITIQUE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("verdict") in ("good", "problems") else None


# ---- definitions --------------------------------------------------------------------------

_TRIPLE = {
    "type": "array",
    "items": {"type": "integer"},
    "minItems": 3,
    "maxItems": 3,
}


def _corner(text: str) -> dict[str, Any]:
    return {**_TRIPLE, "description": text}


_RENDER_DESCRIPTION = (
    "Show the model as one picture. Rows, top to bottom: the seed (the original 3D model); the "
    'conversion (the seed turned into cells by software, cell by cell) when "conversion" is '
    "true or the design is still empty; the current build, part by part (the design cell by "
    "cell before the first rebuild). Every row uses the same viewpoints and scale, so they "
    "line up. Straight views have numbered axes: x and y in studs, z in plates numbered at "
    "every brick (0, 3, 6, ...). Views: front (picture right is +x), right (seen from +x; "
    "picture right is +y, towards the back), back, left, top (picture right is +x, picture "
    "up is +y, so the front is at the bottom) and iso (three-quarter view from the front "
    'right, no numbers). "section" cuts the model open instead: {"axis": "y", "at": 3} '
    "leaves out everything in front of y = 3 and shows the cut from the front, the current "
    "build on the left and the conversion cut the same way on the right; a cut across x is "
    "seen from the +x side (it keeps x = at and everything at smaller x), a cut across z from "
    "above (it keeps z = at and everything below). Farther cells are drawn darker, so a "
    'hollow shows as a darker or empty area. "zoom": {"min": [x, y, z], "max": [x, y, z]} or '
    '{"region": "head"} draws the chosen views larger, cut down to that box (cells in front '
    "of it still show). The picture shows the last rebuild: call rebuild to see your edits. "
    + T._COORDS
)


def _definitions(ops: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    base = {t["name"]: t for t in T.TOOLS}
    colours = T._colour_codes()
    defs: dict[str, dict[str, Any]] = {}
    defs["describe"] = {
        "name": "describe",
        "description": (
            "Describe the design and the build as text, most important first: the grid and "
            "the bounding box of the filled cells; the brief; the construction plan with its "
            "regions; the conversion (the seed converted cell by cell: its size, colours and "
            "extent layer by layer, the numbers to plan against and to copy from); the build's "
            "parts and check report; what the software changed by itself; the design layer by "
            "layer, its colours, finish marks and details. Last come the finish words, the "
            "detail parts and the colours you may use. " + T._COORDS
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    }
    defs["render"] = {
        "name": "render",
        "description": _RENDER_DESCRIPTION,
        "input_schema": {
            "type": "object",
            "properties": {
                "views": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(T.ALL_VIEWS)},
                    "minItems": 1,
                    "maxItems": len(T.ALL_VIEWS),
                    "uniqueItems": True,
                    "description": "Which views to draw, left to right. Default: front, "
                    "right, top, iso (front and right with a section, ignored there).",
                },
                "conversion": {
                    "type": "boolean",
                    "description": "Add a row with the conversion. Default false.",
                },
                "section": {
                    "type": "object",
                    "properties": {
                        "axis": {"type": "string", "enum": ["x", "y", "z"]},
                        "at": {"type": "integer", "minimum": 0},
                    },
                    "required": ["axis", "at"],
                    "additionalProperties": False,
                    "description": "A cut-through at this cell along this axis.",
                },
                "zoom": {
                    "type": "object",
                    "properties": {
                        "min": _corner("Lowest corner [x, y, z] of the box to zoom on."),
                        "max": _corner("Highest corner [x, y, z] (inclusive)."),
                        "region": {"type": "string", "description": "A region of the plan."},
                    },
                    "additionalProperties": False,
                    "description": 'A box ("min" and "max") or a plan region ("region").',
                },
            },
            "additionalProperties": False,
        },
    }
    defs["measure"] = {
        "name": "measure",
        "description": (
            "Compare the current design with the conversion, in numbers: how well their "
            "outlines match seen from the front, the right and the top (percent of the cells "
            "seen from that side); the largest patches where the design has cells the "
            "conversion lacks, and where it lacks cells the conversion has, each with its "
            "size, coordinates and the plan's region; and each region's cells in both. It "
            "measures the design as edited, without a rebuild. A difference is not a "
            "mistake: the plan may exaggerate or drop things on purpose. " + T._COORDS
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    }
    defs["brief"] = base["brief"]
    region = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": NAME_LIMIT,
                "description": "A short unique name, such as head or left ear.",
            },
            "min": _corner("Lowest corner [x, y, z] of the region's box."),
            "max": _corner("Highest corner [x, y, z] of the region's box (inclusive)."),
            "make": {
                "type": "string",
                "enum": list(STUDIO_SHAPE_TYPES),
                "description": "The shape that will make it (seed: copied from the conversion).",
            },
            "colour": {"type": "integer", "enum": colours, "description": "Its main colour."},
            "finish": {
                "type": "string",
                "enum": list(FINISH_NAMES),
                "description": "Its main finish.",
            },
            "note": {
                "type": "string",
                "maxLength": PLAN_LIMITS["note"],
                "description": "Optional: anything the next passes must know about it.",
            },
        },
        "required": ["name", "min", "max", "make", "colour", "finish"],
        "additionalProperties": False,
    }
    interior = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": NAME_LIMIT},
            "min": _corner("Lowest corner [x, y, z] of the hollow space."),
            "max": _corner("Highest corner [x, y, z] of the hollow space (inclusive)."),
            "wall": {
                "type": "integer",
                "minimum": 1,
                "description": "Wall thickness around it, in studs (at least 1).",
            },
            "openings": {
                "type": "string",
                "minLength": 1,
                "maxLength": PLAN_LIMITS["openings"],
                "description": "Where one sees in: doors, windows (transparent or open).",
            },
            "contents": {
                "type": "string",
                "minLength": 1,
                "maxLength": PLAN_LIMITS["contents"],
                "description": "What stands inside: seats, a table, a figure's place.",
            },
        },
        "required": ["name", "min", "max", "wall", "openings", "contents"],
        "additionalProperties": False,
    }
    defs["plan"] = {
        "name": "plan",
        "description": (
            "Record the construction plan the next passes build from: your scale decisions, "
            "the model broken into named regions (each a box in grid cells with the shape that "
            "will make it, its colour and finish), and the interior, or null when the object "
            "has no inside a person would look for. Saved with the project and shown by "
            "describe; a later call replaces it. Returns the plan with the conversion's cell "
            'count in each region\'s box, or "ERROR:" with everything to fix (then nothing is '
            "saved). " + T._COORDS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scale": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": PLAN_LIMITS["scale"],
                    "description": "Proportions and scale: what to enlarge, shrink or drop.",
                },
                "regions": {
                    "type": "array",
                    "items": region,
                    "minItems": 1,
                    "maxItems": MAX_REGIONS,
                },
                "interior": {
                    "anyOf": [interior, {"type": "null"}],
                    "description": "The inside a person would look for, or null.",
                },
            },
            "required": ["scale", "regions", "interior"],
            "additionalProperties": False,
        },
    }
    apply_ops = dict(base["apply_ops"])
    apply_ops["description"] = _apply_ops_description(ops)
    apply_ops["input_schema"] = {
        **base["apply_ops"]["input_schema"],
        "properties": {
            "ops": {
                **base["apply_ops"]["input_schema"]["properties"]["ops"],
                "items": studio_op_schema(ops),
            }
        },
    }
    defs["apply_ops"] = apply_ops
    defs["rebuild"] = base["rebuild"]
    problem = {
        "type": "object",
        "properties": {
            "where": {
                "type": "string",
                "minLength": 1,
                "maxLength": CRITIQUE_LIMITS["where"],
                "description": "Where, in words; a region's name from the plan when one fits.",
            },
            "min": _corner("Lowest corner [x, y, z] of the box the problem is in."),
            "max": _corner("Highest corner [x, y, z] of that box (inclusive)."),
            "problem": {
                "type": "string",
                "minLength": 1,
                "maxLength": CRITIQUE_LIMITS["problem"],
                "description": "What is wrong, as seen in the pictures.",
            },
            "change": {
                "type": "string",
                "minLength": 1,
                "maxLength": CRITIQUE_LIMITS["change"],
                "description": "What to change, concretely.",
            },
        },
        "required": ["where", "min", "max", "problem", "change"],
        "additionalProperties": False,
    }
    defs["critique"] = {
        "name": "critique",
        "description": (
            'Give your report: "good" when nothing would clearly improve the model, or '
            f'"problems" with 1 to {MAX_PROBLEMS} problems, most important first, each saying '
            "where (in words and as a box of cells), what is wrong and what to change; and a "
            "summary of a few sentences. Call render first. Returns the report as recorded, "
            'or "ERROR:" with everything to fix. Calling it again replaces the report. ' + T._COORDS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["good", "problems"]},
                "problems": {
                    "type": "array",
                    "items": problem,
                    "maxItems": MAX_PROBLEMS,
                    "description": 'Most important first; empty or left out for "good".',
                },
                "summary": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": CRITIQUE_LIMITS["summary"],
                },
            },
            "required": ["verdict", "summary"],
            "additionalProperties": False,
        },
    }
    return defs


_OP_WORDS = {
    "add": "add (fill empty cells)",
    "remove": "remove (empty filled cells)",
    "paint": "paint (recolour filled cells)",
    "set_finish": "set_finish (studs, smooth or sloped tops)",
    "place_detail": "place_detail (a small part on the model)",
    "remove_detail": "remove_detail",
}


def _apply_ops_description(ops: tuple[str, ...]) -> str:
    text = (
        "Edit the design with a list of operations, applied in order. Returns one line per "
        "operation: applied, or rejected and why; a rejected operation changes nothing and does "
        "not stop the others. In this pass you may use: "
        + ", ".join(_OP_WORDS[o] for o in ops)
        + ".\n"
    )
    if set(ops) & {"add", "remove", "paint", "set_finish"}:
        text += (
            'Shapes: a box {"type": "box", "min": [x, y, z], "max": [x, y, z]} (both '
            'corners included); an ellipsoid {"type": "ellipsoid", "center": [x, y, z], '
            '"radius": [rx, ry, rz]}; a cylinder, a round column filling a box along "axis": '
            '{"type": "cylinder", "axis": "z", "min": [2, 2, 0], "max": [7, 7, 8]} (each layer '
            "is the ellipse that just fits the box across the axis); a cone, which narrows "
            'evenly towards "narrow_end": {"type": "cone", "axis": "z", "min": [2, 2, 9], '
            '"max": [7, 7, 20], "narrow_end": "max"} ("narrow_size": 0.5 makes the narrow end '
            "half as wide; 0, the default, ends in a point one or two studs across); and a "
            'seed shape, the cells the conversion filled inside a box: {"type": "seed", "min": '
            '[3, 0, 24], "max": [10, 7, 35]}. add with a seed shape and no "color" copies those '
            "cells with the conversion's own colours and finish marks; with a color they all "
            'take it; paint with a seed shape and no "color" gives cells back the conversion\'s '
            "colours. Remember that z counts plates: a column that looks round from the side "
            "needs no change, but a ball needs rz about 2.5 times rx.\n"
            'Example: {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, '
            '2]}, "color": 4} is a 2-stud-wide, 1-brick-tall red block at the front left.\n'
        )
    if "set_finish" in ops:
        text += (
            'set_finish marks what the top of filled cells should be: "studs", "smooth" '
            '(tiles) or "sloped" (a slope where the surface steps down); it shows only on '
            'cells with nothing above. Example: {"op": "set_finish", "shape": {"type": "box", '
            '"min": [2, 0, 11], "max": [7, 3, 11]}, "finish": "smooth"}.\n'
        )
    if "place_detail" in ops:
        text += (
            "place_detail stands one small part from describe's detail list in EMPTY cells "
            'directly above filled ones: "at" is its lowest corner cell, so its z is one above '
            'the top filled cell; "rot" is 0, 90, 180 or 270. Example: {"op": "place_detail", '
            '"part": "98138", "color": 0, "at": [3, 0, 12]}. A one-stud, one-plate detail can '
            'lie flat on a face instead, with "face": "front", "right", "back" or "left": "at" '
            "is then the lowest of three empty cells in front of the face (z a multiple of 3) "
            "and the three cells behind must be filled and one colour, which shows around a "
            'round tile\'s edge. Example, an eye on a face whose front cells are at y = 1: {"op": '
            '"place_detail", "part": "98138", "color": 0, "at": [3, 0, 9], "face": "front"}. '
            'remove_detail removes the detail covering a cell: {"op": "remove_detail", "at": '
            "[3, 0, 12]}.\n"
        )
    text += (
        'Mirror: add "mirror": true to any operation to do the same to its mirror image across '
        "the left-right middle (cell x pairs with cell nx - 1 - x; describe gives nx).\n"
        f"Put related edits in one call (at most {T.MAX_OPS_PER_CALL}). Edits are saved at once "
        "but are NOT visible in render until you call rebuild. " + T._COORDS
    )
    return text


def tool_definitions(
    tools: tuple[str, ...] = STUDIO_TOOL_NAMES, ops: tuple[str, ...] = OPS
) -> list[dict[str, Any]]:
    unknown = [t for t in tools if t not in STUDIO_TOOL_NAMES]
    if unknown:
        raise ValueError(f"unknown studio tools {unknown}; choose from {STUDIO_TOOL_NAMES}")
    defs = _definitions(tuple(ops))
    return [defs[t] for t in tools]


# ---- the conversion, the plan and the comparison ---------------------------------------------


def _conversion(project: Project):
    return project.load_design(base=True)


def _region_boxes(plan: dict[str, Any] | None) -> list[tuple[str, list[int], list[int]]]:
    if not plan:
        return []
    out = []
    for r in plan.get("regions", []):
        with contextlib.suppress(KeyError, TypeError, ValueError):
            out.append((str(r["name"]), [int(v) for v in r["min"]], [int(v) for v in r["max"]]))
    return out


def _box_mask(shape: tuple[int, int, int], lo: list[int], hi: list[int]) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    sl = tuple(slice(max(lo[i], 0), max(min(hi[i], shape[i] - 1) + 1, 0)) for i in range(3))
    m[sl] = True
    return m


def _box_words(lo: list[int] | tuple, hi: list[int] | tuple) -> str:
    return (
        f"x {T._span(int(lo[0]), int(hi[0]))}, y {T._span(int(lo[1]), int(hi[1]))}, "
        f"z {T._span(int(lo[2]), int(hi[2]))}"
    )


def _plan_lines(project: Project, plan: dict[str, Any] | None, catalog) -> list[str]:
    out = ["PLAN (the construction plan; each region is a box of cells, both corners included)"]
    if not plan:
        out.append("No construction plan has been recorded.")
        out.append("")
        return out
    if plan.get("scale"):
        out.append(f"Scale: {plan['scale']}")
    for r in plan.get("regions", []):
        with contextlib.suppress(KeyError, TypeError, ValueError):
            line = (
                f"  {r['name']}: {_box_words(r['min'], r['max'])}; made as {r['make']}; "
                f"{T._colour_label(catalog, int(r['colour']))}; finish {r['finish']}"
            )
            if r.get("note"):
                line += f". {r['note']}"
            out.append(line)
    inside = plan.get("interior")
    if isinstance(inside, dict):
        with contextlib.suppress(KeyError, TypeError, ValueError):
            out.append(
                f"Interior: {inside['name']}, hollow at {_box_words(inside['min'], inside['max'])}"
                f", walls {T._plural(int(inside['wall']), 'stud')} thick. Openings: "
                f"{inside['openings']} Inside: {inside['contents']}"
            )
    else:
        out.append("Interior: none planned.")
    out.append("")
    return out


def _conversion_lines(project: Project, catalog, design) -> list[str]:
    base = _conversion(project)
    filled = base.filled
    out = [
        "THE CONVERSION (the seed turned into cells by software: the reference measure compares "
        'with, and what the "seed" shape copies)'
    ]
    if not filled.any():
        out.append("The conversion has no filled cells.")
        out.append("")
        return out
    xs, ys, zs = np.nonzero(filled)
    out.append(
        f"{int(filled.sum())} cells. Bounding box: {T._bbox(filled)} "
        f"({int(xs.max() - xs.min() + 1)} studs wide, {int(ys.max() - ys.min() + 1)} deep, "
        f"{int(zs.max() - zs.min() + 1)} plates tall)."
    )
    codes, counts = np.unique(base.colors[filled], return_counts=True)
    pairs = sorted(zip(codes.tolist(), counts.tolist(), strict=True), key=lambda t: -t[1])
    out.append(
        "Colours: "
        + ", ".join(
            f"{T._colour_label(catalog, int(c))} {T._plural(int(n), 'cell')}" for c, n in pairs
        )
        + "."
    )
    out.append("Layer by layer:")
    out.extend(T._layers(filled))
    if not design.filled.any():
        out.append(
            "The design itself is EMPTY: nothing is built yet. Add the main shapes with "
            "apply_ops; rebuild needs at least one filled cell."
        )
    out.append("")
    return out


def _views_of(mask: np.ndarray) -> dict[str, np.ndarray]:
    return {"front": mask.any(axis=1), "right": mask.any(axis=0), "top": mask.any(axis=2)}


def _percent(a: np.ndarray, b: np.ndarray) -> int:
    either = int((a | b).sum())
    return 100 if either == 0 else round(100 * int((a & b).sum()) / either)


def outline_match(design_filled: np.ndarray, base_filled: np.ndarray) -> dict[str, int]:
    """Percent match of the cells seen from the front, the right and the top."""
    d, b = _views_of(design_filled), _views_of(base_filled)
    return {v: _percent(d[v], b[v]) for v in ("front", "right", "top")}


def _match_line(design_filled: np.ndarray, base_filled: np.ndarray) -> str:
    m = outline_match(design_filled, base_filled)
    return (
        f"Outline match with the conversion (cells seen from each side; 100% is the same "
        f"outline): front {m['front']}%, right {m['right']}%, top {m['top']}%."
    )


def _where(cells: np.ndarray, boxes) -> str:
    """' (in region "head")' for a patch, from the plan's region boxes."""
    best, best_n = None, 0
    total = int(cells.sum())
    for name, lo, hi in boxes:
        n = int((cells & _box_mask(cells.shape, lo, hi)).sum())
        if n > best_n:
            best, best_n = name, n
    if best is None:
        return " (outside every planned region)" if boxes else ""
    return f' (in region "{best}")' if best_n == total else f' (mostly in region "{best}")'


def _patches(mask: np.ndarray) -> tuple[list[np.ndarray], int, int]:
    """The 6-connected groups of ``mask`` with at least MIN_PATCH cells, largest first, and
    how many smaller groups there are and how many cells they hold."""
    from scipy import ndimage

    labels, n = ndimage.label(mask)
    if n == 0:
        return [], 0, 0
    sizes = np.bincount(labels.ravel())[1:]
    order = np.argsort(-sizes, kind="stable")
    big = [labels == (i + 1) for i in order if sizes[i] >= MIN_PATCH]
    small = [int(s) for s in sizes if s < MIN_PATCH]
    return big, len(small), sum(small)


def comparison_lines(design, base, plan: dict[str, Any] | None) -> list[str]:
    """measure's text: the design against the conversion (see the contract)."""
    from bricksnap.buildable import outside_air

    d, b = design.filled, base.filled
    boxes = _region_boxes(plan)
    out = [
        "HOW THE DESIGN COMPARES WITH THE CONVERSION (information, not errors: the plan may "
        "change the shape on purpose)"
    ]
    if not d.any():
        out.append("The design is empty, so there is nothing to compare yet.")
        return out
    out.append(_match_line(d, b))
    out.append(
        f"Cells: the design has {int(d.sum())}, the conversion {int(b.sum())}, both "
        f"{int((d & b).sum())}."
    )
    out.append(f"Design: {T._bbox(d)}. Conversion: {T._bbox(b) if b.any() else 'empty'}.")
    air = outside_air(d)
    for title, mask, missing in (
        ("Where the design has cells the conversion lacks (largest first):", d & ~b, False),
        ("Where the conversion has cells the design lacks (largest first):", b & ~d, True),
    ):
        out.append(title)
        big, k, cells = _patches(mask)
        if not big and not k:
            out.append("  nowhere")
        for i, patch in enumerate(big[:MAX_PATCHES], start=1):
            line = f"  {i}. {T._plural(int(patch.sum()), 'cell')} at {T._bbox(patch)}"
            line += _where(patch, boxes)
            if missing:
                sealed = int((patch & ~air).sum())
                if sealed == int(patch.sum()):
                    line += "; a hollow sealed inside the design"
                elif sealed:
                    line += f"; {sealed} of them are a hollow sealed inside the design"
            out.append(line)
        rest = len(big) - MAX_PATCHES
        if rest > 0:
            word = "patch" if rest == 1 else "patches"
            out.append(f"  and {rest} smaller {word} of {MIN_PATCH} cells or more")
        if k:
            out.append(
                f"  and {T._plural(k, 'scattered group')} of 1 or 2 cells "
                f"({T._plural(cells, 'cell')})"
            )
    if boxes:
        out.append("Each planned region (cells inside its box):")
        for name, lo, hi in boxes:
            m = _box_mask(d.shape, lo, hi)
            dn, bn, both = int((d & m).sum()), int((b & m).sum()), int((d & b & m).sum())
            either = int(((d | b) & m).sum())
            share = 100 if either == 0 else round(100 * both / either)
            out.append(
                f"  {name} ({_box_words(lo, hi)}): design {dn}, conversion {bn}, shared {both} "
                f"({share}% of the cells either has there)"
            )
    return out


# ---- the plan and the critique: checking what the model sent ---------------------------------


def _check_box(
    item: dict[str, Any], label: str, grid: tuple[int, int, int], problems: list[str]
) -> tuple[list[int], list[int]] | None:
    corners = []
    for key in ("min", "max"):
        value = item.get(key)
        whole = [T._whole(v) for v in value] if isinstance(value, list) else []
        if len(whole) != 3 or any(w is None for w in whole):
            problems.append(f'{label}: "{key}" must be three whole numbers [x, y, z].')
            return None
        corners.append([int(w) for w in whole if w is not None])
    lo, hi = corners
    bad = [a for i, a in enumerate("xyz") if lo[i] > hi[i]]
    if bad:
        problems.append(
            f"{label}: min is greater than max along {', '.join(bad)}; each min must be at "
            "most the matching max."
        )
        return None
    outside = [
        f"{a} {lo[i]} to {hi[i]} (the grid has {a} 0 to {grid[i] - 1})"
        for i, a in enumerate("xyz")
        if lo[i] < 0 or hi[i] > grid[i] - 1
    ]
    if outside:
        problems.append(f"{label}: the box goes outside the grid: {'; '.join(outside)}.")
        return None
    return lo, hi


def _check_words(
    item: dict[str, Any], key: str, label: str, limit: int, problems: list[str], need: bool = True
) -> str:
    if key not in item:
        if need:
            problems.append(f'{label}: "{key}" is missing.')
        return ""
    return T._check_text(item[key], f"{label} {key}", limit, "a short text", problems)


def _unknown(item: dict[str, Any], allowed: tuple[str, ...], label: str, problems: list[str]):
    extra = [k for k in item if k not in allowed]
    if extra:
        problems.append(
            f"{label} has {', '.join(T._show(str(k)) for k in extra[: T.MAX_ECHOED])}, which "
            "it does not take. It takes " + ", ".join(f'"{a}"' for a in allowed) + "."
        )


_REGION_FIELDS = ("name", "min", "max", "make", "colour", "finish", "note")
_INTERIOR_FIELDS = ("name", "min", "max", "wall", "openings", "contents")


def _parse_plan(args: dict[str, Any], grid, catalog) -> tuple[dict[str, Any] | None, list[str]]:
    problems: list[str] = []
    _unknown(args, ("scale", "regions", "interior"), "The plan", problems)
    missing = [f for f in ("scale", "regions", "interior") if f not in args]
    if missing:
        problems.append(
            "missing: " + ", ".join(f'"{m}"' for m in missing) + ' ("interior" may be null).'
        )
    plan: dict[str, Any] = {"scale": "", "regions": [], "interior": None}
    if "scale" in args:
        plan["scale"] = T._check_text(
            args["scale"],
            "scale",
            PLAN_LIMITS["scale"],
            "what to enlarge, shrink or drop",
            problems,
        )
    raw = args.get("regions")
    if "regions" in args and (not isinstance(raw, list) or not 1 <= len(raw) <= MAX_REGIONS):
        problems.append(f'"regions" must be a list of 1 to {MAX_REGIONS} regions.')
    elif isinstance(raw, list):
        seen: set[str] = set()
        for i, item in enumerate(raw, start=1):
            label = f"region {i}"
            if not isinstance(item, dict):
                problems.append(f"{label} must be an object with {', '.join(_REGION_FIELDS[:6])}.")
                continue
            name = _check_words(item, "name", label, NAME_LIMIT, problems)
            if name:
                label = f'region {i} ("{T._clip(name)}")'
                if not _NAME.match(name):
                    problems.append(
                        f"{label}: a name uses letters, digits, spaces, - and _ only, and starts "
                        "with a letter or digit."
                    )
                elif name.lower() in seen:
                    problems.append(f"{label}: another region already has this name.")
                seen.add(name.lower())
            _unknown(item, _REGION_FIELDS, label, problems)
            box = _check_box(item, label, grid, problems)
            make = item.get("make")
            if make not in STUDIO_SHAPE_TYPES:
                problems.append(
                    f'{label}: "make" must be one of {", ".join(STUDIO_SHAPE_TYPES)}, not '
                    f"{T._show(make)}."
                )
            code = T._whole(item.get("colour"))
            if code is None or code not in catalog.colours:
                problems.append(
                    f'{label}: "colour" must be a colour code from describe, not '
                    f"{T._show(item.get('colour'))}."
                )
            finish = item.get("finish")
            if finish not in FINISH_NAMES:
                problems.append(
                    f'{label}: "finish" must be one of {", ".join(FINISH_NAMES)}, not '
                    f"{T._show(finish)}."
                )
            note = _check_words(item, "note", label, PLAN_LIMITS["note"], problems, need=False)
            if box and code is not None:
                entry = {
                    "name": name,
                    "min": box[0],
                    "max": box[1],
                    "make": make,
                    "colour": code,
                    "finish": finish,
                }
                if note:
                    entry["note"] = note
                plan["regions"].append(entry)
    inside = args.get("interior")
    if inside is not None and "interior" in args:
        if not isinstance(inside, dict):
            problems.append(
                '"interior" must be null or an object with ' + ", ".join(_INTERIOR_FIELDS) + "."
            )
        else:
            label = "the interior"
            _unknown(inside, _INTERIOR_FIELDS, label, problems)
            name = _check_words(inside, "name", label, NAME_LIMIT, problems)
            box = _check_box(inside, label, grid, problems)
            if box and box[0][2] < 1:
                problems.append(
                    f"{label}: the hollow starts at z = {box[0][2]}; it needs a floor under it, so "
                    "start it at z = 1 or higher (z = 3 gives a floor one brick thick)."
                )
                box = None
            wall = T._whole(inside.get("wall"))
            if wall is None or wall < 1:
                problems.append(
                    f'{label}: "wall" is the wall thickness in studs, a whole number of at least '
                    f"1, not {T._show(inside.get('wall'))}."
                )
            openings = _check_words(inside, "openings", label, PLAN_LIMITS["openings"], problems)
            contents = _check_words(inside, "contents", label, PLAN_LIMITS["contents"], problems)
            if box and wall is not None:
                plan["interior"] = {
                    "name": name,
                    "min": box[0],
                    "max": box[1],
                    "wall": wall,
                    "openings": openings,
                    "contents": contents,
                }
    if problems:
        return None, problems
    return plan, []


def _parse_critique(args: dict[str, Any], grid) -> tuple[dict[str, Any] | None, list[str]]:
    problems: list[str] = []
    _unknown(args, ("verdict", "problems", "summary"), "The report", problems)
    verdict = args.get("verdict")
    if verdict not in ("good", "problems"):
        problems.append(f'"verdict" must be "good" or "problems", not {T._show(verdict)}.')
    summary = _check_words(args, "summary", "the report", CRITIQUE_LIMITS["summary"], problems)
    raw = args.get("problems", [])
    found: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        problems.append('"problems" must be a list.')
        raw = []
    if verdict == "good" and raw:
        problems.append(
            'A "good" verdict takes no problems: leave "problems" out, or make the verdict '
            '"problems".'
        )
    if verdict == "problems" and not 1 <= len(raw) <= MAX_PROBLEMS:
        problems.append(
            f'A "problems" verdict lists 1 to {MAX_PROBLEMS} problems, most important first '
            f"(it has {len(raw)})."
        )
    for i, item in enumerate(raw[: MAX_PROBLEMS * 2], start=1):
        label = f"problem {i}"
        if not isinstance(item, dict):
            problems.append(f"{label} must be an object with where, min, max, problem, change.")
            continue
        _unknown(item, ("where", "min", "max", "problem", "change"), label, problems)
        where = _check_words(item, "where", label, CRITIQUE_LIMITS["where"], problems)
        box = _check_box(item, label, grid, problems)
        what = _check_words(item, "problem", label, CRITIQUE_LIMITS["problem"], problems)
        change = _check_words(item, "change", label, CRITIQUE_LIMITS["change"], problems)
        if box:
            found.append(
                {"where": where, "min": box[0], "max": box[1], "problem": what, "change": change}
            )
    if problems:
        return None, problems
    return {"verdict": verdict, "problems": found, "summary": summary}, []


def critique_words(report: dict[str, Any]) -> str:
    """The critic's report in plain words, as the fix pass reads it."""
    if report.get("verdict") == "good":
        return "The critic found the model good. " + str(report.get("summary", ""))
    lines = []
    for i, p in enumerate(report.get("problems", []), start=1):
        lines.append(
            f"{i}. {p['where']} ({_box_words(p['min'], p['max'])}): {p['problem']} "
            f"Change: {p['change']}"
        )
    if report.get("summary"):
        lines.append(f"Summary: {report['summary']}")
    return "\n".join(lines)


# ---- the session --------------------------------------------------------------------------


class Session:
    """The tools of one pass for one project (see the contract)."""

    def __init__(
        self,
        project_path: str | Path,
        tools: tuple[str, ...] = STUDIO_TOOL_NAMES,
        ops: tuple[str, ...] = OPS,
    ) -> None:
        self.path = Path(project_path)
        self.tools = tuple(tools)
        self.ops = tuple(ops)
        self.looked = False

    def call(self, name: Any, args: Any) -> list[dict[str, Any]]:
        blocks = self._call(name, args)
        return [
            {**b, "text": T._scrub(str(b.get("text", "")), self.path)}
            if b.get("type") == "text"
            else b
            for b in blocks
        ]

    def _call(self, name: Any, args: Any) -> list[dict[str, Any]]:
        if not isinstance(name, str) or name not in self.tools:
            return T._error(
                f"there is no tool called {T._show(name)} in this pass. Its tools are "
                f"{', '.join(self.tools)}."
            )
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return T._error(f"the arguments to {name} must be a JSON object, for example {{}}.")
        try:
            project = Project(self.path)
        except ProjectError as e:
            return T._error(str(e) + T._CANNOT_FIX)
        except Exception:
            return T._error("the project's settings file could not be read." + T._CANNOT_FIX)
        if not isinstance(project.meta, dict):
            return T._error("the project's settings file could not be read." + T._CANNOT_FIX)
        try:
            if name in ("describe", "measure", "rebuild"):
                problem = T._check_no_args(name, args)
                if problem:
                    return T._error(problem)
            if name == "describe":
                return self._describe(project)
            if name == "render":
                return self._render(project, args)
            if name == "measure":
                return self._measure(project)
            if name == "brief":
                return T._brief(project, args)
            if name == "plan":
                return self._plan(project, args)
            if name == "apply_ops":
                return self._apply_ops(project, args)
            if name == "rebuild":
                return self._rebuild(project)
            return self._critique(project, args)
        except ProjectError as e:
            if not project.has_design():
                return T._error(
                    "the project has no design yet, so there is nothing to work on." + T._CANNOT_FIX
                )
            return T._error(str(e))
        except OSError as e:
            return T._error(f"{name} could not finish: {T._os_reason(e, self.path)}")
        except Exception as e:  # never hand a traceback to the model
            return T._error(f"{name} could not finish: {str(e) or type(e).__name__}")

    # ---- the tools ----

    def _describe(self, project: Project) -> list[dict[str, Any]]:
        catalog = T._catalog()
        design = project.load_design()
        extra = _plan_lines(project, load_plan(project), catalog)
        extra += _conversion_lines(project, catalog, design)
        blocks = T._describe(project, before_build=extra)
        if not design.filled.any():
            text = blocks[0]["text"].replace(
                "There is no build yet. Call rebuild to make one.",
                "There is no build yet: the design is empty.",
            )
            blocks = [T._text(text)]
        return blocks

    def _measure(self, project: Project) -> list[dict[str, Any]]:
        design = project.load_design()
        lines = comparison_lines(design, _conversion(project), load_plan(project))
        return [T._text("\n".join(lines))]

    def _plan(self, project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
        catalog = T._catalog()
        design = project.load_design()
        plan, problems = _parse_plan(args, design.shape, catalog)
        if plan is None:
            return T._error(
                "the plan was not saved. Fix these and call plan again with every field:\n"
                + "\n".join(f"- {p}" for p in problems)
            )
        replaced = load_plan(project) is not None
        write_text_atomic(
            studio_dir(project) / PLAN_FILE, json.dumps(plan, indent=1, ensure_ascii=False) + "\n"
        )
        base = _conversion(project)
        lines = [
            ("Plan replaced." if replaced else "Plan saved.") + " The next passes build from it."
        ]
        lines += _plan_lines(project, plan, catalog)[1:-1]
        lines.append("The conversion's cells in each region's box:")
        for name, lo, hi in _region_boxes(plan):
            n = int((base.filled & _box_mask(base.shape, lo, hi)).sum())
            lines.append(f"  {name}: {T._plural(n, 'cell')}")
        return [T._text("\n".join(lines))]

    def _apply_ops(self, project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
        ops = args.get("ops")
        if isinstance(ops, dict):
            ops = [ops]
        if isinstance(ops, list):
            names = [op.get("op") for op in ops if isinstance(op, dict)]
            barred = sorted({str(n) for n in names if n in OPS and n not in self.ops})
            if barred or "clear" in names:
                which = barred or ["clear"]
                return T._error(
                    f"this pass may not use {', '.join(T._clip(w) for w in which)}. It may use "
                    + ", ".join(_OP_WORDS[o] for o in self.ops)
                    + ". Nothing was applied: send the call again without those operations."
                )
        return T._apply_ops(project, args, reference=_conversion(project))

    def _rebuild(self, project: Project) -> list[dict[str, Any]]:
        design = project.load_design()
        if not design.filled.any():
            return T._error(
                "the design is empty, so there is nothing to build. Add the main shapes with "
                "apply_ops first."
            )
        blocks = T._rebuild(project)
        line = _match_line(design.filled, _conversion(project).filled)
        blocks.append(T._text(line + " Call measure to see where they differ."))
        return blocks

    def _critique(self, project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.looked:
            return T._error(
                "look first: call render (the default views, and a section or zoom where you "
                "need one) before you give your report. Nothing was recorded."
            )
        report, problems = _parse_critique(args, project.load_design().shape)
        if report is None:
            return T._error(
                "the report was not recorded. Fix these and call critique again:\n"
                + "\n".join(f"- {p}" for p in problems)
            )
        write_text_atomic(
            studio_dir(project) / CRITIQUE_FILE,
            json.dumps(report, indent=1, ensure_ascii=False) + "\n",
        )
        return [T._text("Report recorded.\n" + critique_words(report))]

    # ---- render ----

    def _render(self, project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
        unknown = [k for k in args if k not in ("views", "conversion", "section", "zoom")]
        if unknown:
            return T._error(
                f"render does not take {T._names(unknown)}. Its optional arguments are "
                '"views", "conversion", "section" and "zoom".'
            )
        problem = _check_views(args.get("views"))
        if problem:
            return T._error(problem)
        conversion = args.get("conversion", False)
        if not isinstance(conversion, bool):
            return T._error('"conversion" must be true or false.')
        if "section" in args and "zoom" in args:
            return T._error('give "section" or "zoom", not both: call render twice.')
        from bricksnap import pipeline

        catalog = T._catalog()
        design = project.load_design()
        base = _conversion(project)
        build = project.load_build() if project.has_build() else None
        if build is not None and build.shape != design.shape:
            build = None
        try:
            seed = pipeline.load_project_seed(project)
        except Exception:
            seed = None
        if "section" in args:
            picture, text = self._section(design, base, build, catalog, args["section"])
        elif "zoom" in args:
            picture, text = self._zoom(
                project, design, base, build, seed, catalog, args["zoom"], args, conversion
            )
        else:
            picture, text = _sheet(design, base, build, seed, catalog, args, conversion)
        if picture is None:
            return T._error(text)
        self.looked = True
        out = project.renders_dir / "studio.png"
        picture.save(out)
        with Image.open(out) as im:
            im.load()
            data = T._png_bytes(im)
        if T._build_out_of_date(project) and design.filled.any():
            text += (
                "\n- NOTE: the design has edits that are not built yet; the build row still "
                "shows the previous build. Call rebuild, then render, to see them."
            )
        return [
            {"type": "image", "media_type": "image/png", "data": base64.b64encode(data).decode()},
            T._text(text),
        ]

    def _section(self, design, base, build, catalog, section: Any):
        from bricksnap.render import SECTION_VIEWS, contact_sheet, render_section

        if not isinstance(section, dict) or set(section) - {"axis", "at"}:
            return None, '"section" must be an object such as {"axis": "y", "at": 3}.'
        axis, at = section.get("axis"), T._whole(section.get("at"))
        if axis not in SECTION_VIEWS:
            return None, f'"section" "axis" must be "x", "y" or "z", not {T._show(axis)}.'
        n = design.shape["xyz".index(axis)]
        if at is None or not 0 <= at < n:
            return None, (
                f'"section" "at" must be a whole number from 0 to {n - 1} (a cell along {axis}), '
                f"not {T._show(section.get('at'))}."
            )
        view = SECTION_VIEWS[axis]
        current = build if build is not None else design
        what = "build" if build is not None else "design"
        items = []
        if design.filled.any():
            items.append(
                (
                    f"{what} - cut at {axis} = {at}, seen from the {_SEEN[axis]}",
                    render_section(current, catalog, axis, at, px_per_stud=SECTION_PX),
                )
            )
        items.append(
            (
                f"conversion - cut at {axis} = {at}, seen from the {_SEEN[axis]}",
                render_section(base, catalog, axis, at, px_per_stud=SECTION_PX),
            )
        )
        kept = {
            "x": f"x = {at} and everything at smaller x",
            "y": f"y = {at} and everything behind it",
            "z": f"z = {at} and everything below it",
        }[axis]
        text = "\n".join(
            [
                "How to read the picture:",
                f"- A cut-through at {axis} = {at}, seen from the {_SEEN[axis]} ({view} view "
                f"axes). It shows {kept}; everything nearer was left out. "
                + ("Left: the current " + what + ". Right: " if design.filled.any() else "")
                + "the conversion, cut the same way, cell by cell.",
                "- The cut face is drawn in full colour; cells farther away are darker, so a "
                "hollow shows as a darker or empty area. Slopes and round parts are kept whole "
                "or left out by where their middle lies.",
                "- The numbers along the edges are cell indices: x and y in studs, z in plates.",
            ]
        )
        return contact_sheet(items, columns=len(items), title=f"Cut at {axis} = {at}"), text

    def _zoom(self, project, design, base, build, seed, catalog, zoom: Any, args, conversion):
        from bricksnap.render import contact_sheet, render_zoom

        if not isinstance(zoom, dict) or set(zoom) - {"min", "max", "region"}:
            return (
                None,
                '"zoom" must be {"min": [x, y, z], "max": [x, y, z]} or {"region": "head"}.',
            )
        if "region" in zoom:
            if "min" in zoom or "max" in zoom:
                return None, 'give "zoom" either a "region" or "min" and "max", not both.'
            boxes = {n.lower(): (n, lo, hi) for n, lo, hi in _region_boxes(load_plan(project))}
            key = str(zoom["region"]).strip().lower()
            if key not in boxes:
                names = ", ".join(n for n, _, _ in boxes.values()) or "none: there is no plan"
                return (
                    None,
                    f"there is no region {T._show(zoom['region'])}. The regions are: {names}.",
                )
            _, lo, hi = boxes[key]
        else:
            problems: list[str] = []
            box = _check_box(zoom, '"zoom"', design.shape, problems)
            if box is None:
                return None, problems[0] if problems else '"zoom" needs "min" and "max".'
            lo, hi = box
        views = args.get("views") or ["front", "right", "top"]
        w = max(hi[0] - lo[0] + 1, hi[1] - lo[1] + 1, 1)
        h = (hi[2] - lo[2] + 1) / PLATES_PER_BRICK * 1.2
        px = int(max(16, min(48, ZOOM_TARGET_PX / max(w, h, 1) / max(len(views), 1) * 1.5)))
        rows: list[tuple[str, Any]] = []
        if seed is not None:
            rows.append(("seed", seed))
        if conversion or not design.filled.any():
            rows.append(("conversion", base))
        if design.filled.any():
            rows.append(("build", build) if build is not None else ("design", design))
        items = []
        for label, obj in rows:
            for v in views:
                im = render_zoom(
                    obj,
                    catalog,
                    v,
                    lo,
                    hi,
                    px_per_stud=px,
                    grid_shape=design.shape,
                    seed_offset=design.seed_offset,
                )
                items.append((f"{label} - {v}", im))
        title = f"Zoom on {_box_words(lo, hi)}"
        text = "\n".join(
            [
                "How to read the picture:",
                "- Rows: "
                + ", ".join(label for label, _ in rows)
                + "; one column per view ("
                + ", ".join(views)
                + f"), drawn {px} pixels per stud and cut down to {_box_words(lo, hi)}.",
                "- Everything in the view is drawn, so cells in front of the box can hide it; "
                "use a section to see inside.",
                "- The numbers along the left and bottom edges are cell indices: x and y in "
                "studs, z in plates.",
            ]
        )
        return contact_sheet(items, columns=len(views), title=title), text


_SEEN = {"x": "+x side", "y": "front", "z": "top"}


def _check_views(views: Any) -> str | None:
    if views is None:
        return None
    if (
        not isinstance(views, list)
        or not views
        or not all(isinstance(v, str) for v in views)
        or len(views) > len(T.ALL_VIEWS)
    ):
        return (
            f'"views" must be a list of 1 to {len(T.ALL_VIEWS)} view names chosen from '
            f'{", ".join(T.ALL_VIEWS)}, for example ["front", "right"].'
        )
    bad = [v for v in views if v not in T.ALL_VIEWS]
    if bad:
        shown = ", ".join(T._show(v) for v in bad)
        return f"unknown view {shown}. Choose from {', '.join(T.ALL_VIEWS)}."
    if len(set(views)) != len(views):
        return '"views" lists the same view twice. Give each view once.'
    return None


def _sheet(design, base, build, seed, catalog, args, conversion) -> tuple[Any, str]:
    """The ordinary picture: seed, conversion (when asked or the design is empty), build."""
    from bricksnap.render import (
        contact_sheet,
        render_build,
        render_design,
        render_seed,
    )

    views = args.get("views") or list(T.DEFAULT_VIEWS)
    empty = not design.filled.any()
    rows: list[str] = []
    items = []
    if seed is not None:
        rows.append("the seed, the original 3D model placed in the same grid")
        for v in views:
            items.append(
                (
                    f"seed - {v}",
                    render_seed(seed, v, design.shape, seed_offset=design.seed_offset),
                )
            )
    if conversion or empty:
        rows.append("the conversion, cell by cell (the seed turned into cells by software)")
        items += [(f"conversion - {v}", render_design(base, catalog, v)) for v in views]
    if not empty:
        if build is not None:
            rows.append("the current build, part by part (each part has a thin dark outline)")
            items += [(f"build - {v}", render_build(build, catalog, v)) for v in views]
        else:
            rows.append("the current design, cell by cell (there is no build yet; call rebuild)")
            items += [(f"design - {v}", render_design(design, catalog, v)) for v in views]
    names = ["Top row", "Middle row", "Bottom row"] if len(rows) == 3 else ["Top row", "Bottom row"]
    if len(rows) == 1:
        names = ["The only row"]
    lines = ["How to read the picture:"]
    for name, row in zip(names, rows, strict=True):
        lines.append(f"- {name}: {row}.")
    if empty:
        lines.append("- The design is empty, so there is no build row yet.")
    lines += [
        "- Each column is one view, named in its caption: " + ", ".join(views) + ".",
        "- front: picture right is +x, up is +z. right: seen from the +x side, picture right is "
        "+y (towards the back). back: picture right is -x. left: picture right is -y. top: seen "
        "from above, picture right is +x and picture up is +y (the front, y = 0, is at the "
        "bottom). iso: three-quarter view from the front right and above, no numbers.",
        "- The numbers along the edges are cell indices: x and y in studs, z in plates, with z "
        "numbered at every brick (0, 3, 6, ...). A cell is drawn 2.5 times wider than it is "
        "tall, as in real bricks.",
    ]
    return contact_sheet(items, columns=len(views)), "\n".join(lines)


def call_tool(
    project_path: str | Path,
    name: str,
    args: dict[str, Any],
    *,
    tools: tuple[str, ...] = STUDIO_TOOL_NAMES,
    ops: tuple[str, ...] = OPS,
) -> list[dict[str, Any]]:
    """One call in a new Session (``critique`` will refuse: nothing has been looked at)."""
    return Session(project_path, tools, ops).call(name, args)


__all__ = [
    "STUDIO_TOOL_NAMES",
    "Session",
    "call_tool",
    "comparison_lines",
    "critique_words",
    "load_critique",
    "load_plan",
    "outline_match",
    "tool_definitions",
]
