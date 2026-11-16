"""The designer's four tools, defined once and independent of how the model is run.

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

Implementation notes
--------------------
- ``describe`` also lists the filled cells layer by layer (consecutive plates with the same
  outline are merged into one line), so the model can read coordinates as text and not only
  off the pictures, and it says when the design has edits that have not been rebuilt yet.
- A build is "out of date" when ``design.npz`` was written after ``build.json``; ``render``
  says so in its text, because the bottom row then still shows the old build.
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
"""

from __future__ import annotations

import base64
import contextlib
import io
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from bricksnap.design import OP_SCHEMA
from bricksnap.project import Project, ProjectError
from bricksnap.types import PLATES_PER_BRICK

DEFAULT_VIEWS = ("front", "right", "top", "iso")
ALL_VIEWS = ("front", "right", "back", "left", "top", "iso")
MAX_OPS_PER_CALL = 100
MAX_IMAGE_BYTES = 400_000

_COORDS = (
    "Coordinates: every position is a grid cell [x, y, z]. x counts studs from left to right "
    "as seen from the front; y counts studs from the front (y = 0) towards the back; z counts "
    "PLATES upwards from the ground (z = 0 is the bottom layer). A brick is 3 plates tall, so "
    "one cell is 2.5 times wider than it is tall."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "describe",
        "description": (
            "Describe the current design and build as text. Returns: the grid size and valid "
            "coordinate ranges; how many cells are filled and their bounding box; the filled "
            "area layer by layer; the colours in use (name, code, cell count); every colour "
            "you may use (code and name); the parts in the current build by kind; the full "
            "check report (loose parts, whether it stands, weak spots with coordinates); the "
            "brief if there is one; and how many edits have been applied. Call it first, and "
            "again whenever you need exact numbers. " + _COORDS
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
        "name": "apply_ops",
        "description": (
            "Edit the design with a list of operations, applied in order. add fills EMPTY "
            "cells inside a shape with a colour; remove empties the filled cells inside a "
            "shape; paint recolours the filled cells inside a shape. A shape is a box "
            '{"type": "box", "min": [x, y, z], "max": [x, y, z]} with both corners '
            'included, or an ellipsoid {"type": "ellipsoid", "center": [x, y, z], "radius": '
            "[rx, ry, rz]}. Colours are codes from describe. Returns one line per operation: "
            "applied (with how many cells changed) or rejected and why; a rejected operation "
            "changes nothing and does not stop the others, so later operations in the same call "
            "still run on the design as it then is. A remove that would leave the design "
            "completely empty is rejected: to start over, first remove everything except the "
            "cells you will keep (for example the feet), add the new shapes, then remove what "
            "is left over. Each part is one colour, so a feature in its own colour that "
            "touches the body only at its side comes loose; painting a stud or two of hidden "
            "cells behind it in the same colour lets its parts reach into the body and hold. Put "
            f"related edits in one call (at most {MAX_OPS_PER_CALL}). Edits are saved at once "
            "but are NOT visible in render "
            "until you call rebuild. " + _COORDS + " Example: a 2-stud-wide, 1-brick-tall "
            'block at the front left of the ground is {"op": "add", "shape": {"type": "box", '
            '"min": [0, 0, 0], "max": [1, 1, 2]}, "color": 4}.'
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
            "Turn the current design into real bricks and plates, check the result, and "
            "return the check report: the part count, whether everything is connected in one "
            "piece that reaches the ground, whether it stands, and weak spots in plain words "
            "with coordinates (x and y in studs, z in plates). Call it after apply_ops and "
            "before render. If the report says parts are loose or the model does not stand, "
            "fix that first."
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
        keys = ", ".join(sorted(str(k) for k in args))
        return f"{name} takes no arguments, but got: {keys}. Call it with an empty object {{}}."
    return None


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


def _describe(project: Project) -> list[dict[str, Any]]:
    catalog = _catalog()
    design = project.load_design()
    nx, ny, nz = design.shape
    filled = design.filled
    out: list[str] = []

    out.append(f"Project: {project.name}")
    out.append("")
    out.append("GRID")
    out.append(
        f"{nx} x {ny} x {nz} cells: x from 0 to {nx - 1}, y from 0 to {ny - 1}, "
        f"z from 0 to {nz - 1}."
    )
    out.append(_COORDS)
    out.append(
        "One cell is 8 mm wide, 8 mm deep and 3.2 mm tall. The grid has empty room around and "
        "above the model so that you can add to it."
    )
    out.append("")

    out.append("FILLED CELLS")
    count = int(filled.sum())
    if count:
        xs, ys, zs = np.nonzero(filled)
        out.append(
            f"{count} filled cells. Bounding box: x {_span(int(xs.min()), int(xs.max()))}, "
            f"y {_span(int(ys.min()), int(ys.max()))}, z {_span(int(zs.min()), int(zs.max()))} "
            f"({int(xs.max() - xs.min() + 1)} studs wide, {int(ys.max() - ys.min() + 1)} studs "
            f"deep, {int(zs.max() - zs.min() + 1)} plates tall, which is about "
            f"{(zs.max() - zs.min() + 1) / PLATES_PER_BRICK:.1f} bricks)."
        )
        out.append("Layer by layer (the extent of the filled cells in each plate):")
        out.extend(_layers(filled))
    else:
        out.append("No cells are filled.")
    out.append("")

    out.append("COLOURS IN USE")
    codes, counts = np.unique(design.colors[filled], return_counts=True)
    for code, n in sorted(zip(codes.tolist(), counts.tolist(), strict=True), key=lambda t: -t[1]):
        out.append(f"  {_colour_label(catalog, int(code))}: {_plural(int(n), 'cell')}")
    if not len(codes):
        out.append("  none")
    out.append("")

    out.append("COLOURS AVAILABLE (code: name)")
    out.append(
        "  "
        + ", ".join(
            f"{c.code}: {c.name}" for c in sorted(catalog.colours.values(), key=lambda c: c.code)
        )
    )
    out.append("")

    out.append("BUILD")
    if project.has_build():
        build = project.load_build()
        kinds: Counter[str] = Counter()
        for p in build.parts:
            part = catalog.parts.get(p.part)
            kinds[part.kind if part else "unknown part"] += 1
        by_kind = ", ".join(f"{_plural(n, k)}" for k, n in kinds.most_common())
        out.append(f"{_plural(len(build.parts), 'part')}: {by_kind or 'none'}.")
        if _build_out_of_date(project):
            out.append(
                "The design has edits that are not built yet: call rebuild to see them. The "
                "parts and report below are from the previous rebuild."
            )
        out.append("Check report:")
        out.append(build.report.text if build.report else "(no check report saved)")
    else:
        out.append("There is no build yet. Call rebuild to make one.")
    out.append("")

    brief = project.meta.get("brief")
    out.append("BRIEF")
    out.append(str(brief) if brief else "No brief has been written for this project.")
    out.append("")

    out.append("EDITS")
    out.append(f"{_plural(len(design.log), 'edit operation')} applied since the original design.")
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
    unknown = sorted(str(k) for k in args if k != "views")
    if unknown:
        return _error(
            f"render does not take {', '.join(unknown)}. Its only (optional) argument is "
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
            f"unknown view {', '.join(repr(v) for v in bad)}. Choose from {', '.join(ALL_VIEWS)}."
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


def _apply_ops(project: Project, args: dict[str, Any]) -> list[dict[str, Any]]:
    unknown = sorted(str(k) for k in args if k != "ops")
    if unknown:
        return _error(
            f'apply_ops does not take {", ".join(unknown)}. Its only argument is "ops", a list '
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
        if r.applied:
            lines.append(
                f"{r.index + 1}. {what}: applied, {_plural(r.cells_changed, 'cell')} changed."
                + (f" {r.message}" if r.message else "")
            )
        else:
            lines.append(f"{r.index + 1}. {what}: not applied. {r.message}")
    lines.append("")
    lines.append(
        f"{len(applied)} of {len(results)} operations applied; the design now has "
        f"{int(design.filled.sum())} filled cells and {_plural(len(design.log), 'edit')} in its "
        "log."
    )
    lines.append("Nothing is visible in render until you call rebuild.")
    return [_text("\n".join(lines))]


def _rebuild(project: Project) -> list[dict[str, Any]]:
    from bricksnap import pipeline

    catalog = _catalog()
    build = pipeline.rebuild(project, catalog=catalog)
    kinds: Counter[str] = Counter()
    for p in build.parts:
        part = catalog.parts.get(p.part)
        kinds[part.kind if part else "unknown part"] += 1
    by_kind = ", ".join(_plural(n, k) for k, n in kinds.most_common())
    report = build.report.text if build.report else "(the checks produced no report)"
    return [
        _text(
            f"Rebuilt: {_plural(len(build.parts), 'part')} ({by_kind or 'none'}).\n"
            f"{report}\nCall render to see the result."
        )
    ]


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
        return _error(f"there is no tool called {name!r}. The tools are {', '.join(TOOL_NAMES)}.")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return _error(f"the arguments to {name} must be a JSON object, for example {{}}.")
    try:
        project = Project(project_path)
    except ProjectError as e:
        return _error(str(e) + _CANNOT_FIX)
    except Exception:  # project.json is not valid JSON, not UTF-8, unreadable ...
        return _error(
            "the project's settings file (project.json) could not be read, so the project "
            "cannot be opened." + _CANNOT_FIX
        )
    try:
        if name == "describe":
            problem = _check_no_args(name, args)
            return _error(problem) if problem else _describe(project)
        if name == "render":
            return _render(project, args)
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
    except Exception as e:  # never hand a traceback to the model
        reason = str(e) or type(e).__name__
        return _error(f"{name} could not finish: {reason}")


__all__ = ["DEFAULT_VIEWS", "TOOLS", "TOOL_NAMES", "call_tool"]
