"""The tools the AI builder gets, and what each call does (research prototype).

CONTRACT (tests in tests/test_lab.py; served over MCP by ``mcp_server``)

A work folder holds one session's model and everything the tools save:
- ``config.json``: ``{"mode": "tools" | "blind", "max_checks": int, "guide": bool}`` (written
  by ``run``; a folder without "guide" has it off).
- ``model.ldr``: the model being built. ``place``, ``add`` and ``remove`` change it; ``submit``
  replaces it. Its line numbers are the ones every tool and report uses. A removed part
  becomes a comment line ("0 removed: ..."), so the other lines keep their numbers.
- ``attempts/attempt-NNN.ldr``, ``-report.txt`` and ``.png``: each ``check`` or ``submit``.
- ``looks/``, ``parts/``, ``modules/``: the pictures of ``look``, ``part_info`` and
  ``modules``.
- ``reference/*.png``: pictures of what to build (shown by ``reference``).
- ``calls.jsonl``: one line per call (tool, short arguments, whether it failed, seconds).
- ``playbook.json`` (guide mode): the last playbook ``playbook`` returned (``{"kind",
  "parts", "playbook"}``, its title).

``TOOLS`` (mode "tools"): search_parts, part_info, place, add, fill, mirror, remove,
remove_box, model, check, look, submit, modules, place_module, joint, and reference when the
folder has reference pictures.

Guide mode (``"guide": true`` in config.json, mode "tools" only; see ``guide``): the same
tools plus ``playbook`` (before reference): with ``{"kind", "parts"}`` the guide's playbook
of that kind nearest that size (``guide.playbook``; a kind is also read from a word such as
"car" or "house"), saying which it chose and why; with ``{}`` the kinds, one line each; with
``{"table": true}`` the parts by job. And ``place``, for a part whose studs no longer point
up or down once placed (a plate on side studs), adds its studs in the model's coordinates,
numbered, with the way each points and whether it is taken. With the guide off, every tool
list and every reply is exactly what it was before guide mode existed.

What moves (``joints``, ``modules``, ``movement``): ``modules`` lists the proven moving modules
(with one name: the module's card and a picture of it at rest and opened); ``place_module``
puts one in by connection in the same three ways as ``place`` and appends its parts and its
joint line; ``joint`` declares a joint for two parts the builder placed itself, accepted only
when ``movement.confirm`` confirms its line (a Technic pin or a wheel pin, about the axis
the library records for it; anything else is refused: use a module); ``look`` with
``"open"`` (``{"joint name": degrees}`` or ``"all"``: each as far as the check says it goes)
draws the model with those joints opened, carrying what rides on them. Every check's report
has the movement verdict (``validate``).

``BLIND_TOOLS`` (mode "blind"): submit only (accepted once; it says only that the model was
saved), and reference when there are reference pictures.

``call_tool(folder, name, args)`` returns content blocks (``{"type": "text"}``,
``{"type": "image", "media_type": "image/png", "data": base64}``). It never raises: a bad
call comes back as one text block starting "ERROR:" that says what to fix. Text has the
work folder's path, e-mail addresses and the home folder removed (``runner.redact``).
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import math
import re
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

MAX_IMAGE_BYTES = 400_000
DEFAULT_MAX_CHECKS = 25

_COORDS = (
    "LDraw units (LDU): a stud is 20 LDU across, a plate 8 LDU tall, a brick 24. y points "
    "DOWN (up is -y) and the ground is y = 0; the front of the model is the -z side; seen "
    "from the front, +x is to the right."
)

_SEARCH = {
    "name": "search_parts",
    "description": (
        "Find parts in the LDraw library (about 5,600 official, current, plain parts: no "
        "printed or sticker versions, no assemblies) by plain words, such as 'leaf', 'wing 2 "
        "x 4 left', 'plate 2 x 2 with wheel pins', 'curved slope 4 x 1', 'brick 1 x 1 with "
        "stud on side', or by a part number ('3001'). Returns up to `limit` parts (default "
        "15), best first, one per line: the file name to use; its description; its category; "
        "its size in studs (x) by studs (z) by plates (height) of its body; its studs (how "
        "many, on top or on which side, and for up to 8 top studs their x,z positions); open "
        "stud rings underneath; other connectors found in its geometry (pin holes, axle "
        "holes, clips, hinges, wheel pins...); and where its origin is relative to its body. "
        "Search again with other words if the part you want is not there: LDraw names parts "
        "its own way ('Slope Brick Curved', 'Wing', 'Plate ... with Wheel Pins')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Plain words or a part number."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 40, "default": 15},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

_PART_INFO = {
    "name": "part_info",
    "description": (
        "Everything about one part, in its own coordinates (" + _COORDS + "). Input: "
        '{"part": "3001.dat"}. Returns: its description and category; its size; where its '
        "origin is and the box its body spans from the origin; its studs, NUMBERED (the "
        "numbers place uses), each with its position and the way it points (up, or -z for a "
        "stud on the front side...); its sockets underneath, NUMBERED, each with the position "
        "where a stud's base goes (a socket is a stud cell of its underside, or an open tube "
        "or ring); other connectors its geometry has (pin and axle holes, clips, hinges, wheel "
        "pins: named and located, never checked); and a picture of the part from above with "
        "the stud numbers and its origin marked, and from below.\n"
        'With {"line": n} instead: the part on line n of the model, with its studs and sockets '
        "in the MODEL's coordinates (same numbers), each stud marked when a part already sits "
        "on it; use this to pick a stud on a part that is turned."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "part": {"type": "string", "description": "File name, e.g. 3001.dat."},
            "line": {"type": "integer", "minimum": 1, "description": "A line of the model."},
        },
        "additionalProperties": False,
    },
}

_PLACE = {
    "name": "place",
    "description": (
        "Add one part to the model by naming how it connects; the tool computes its position "
        "and rotation exactly and appends the LDraw line. Three ways:\n"
        '1. On a stud: {"part", "colour", "line": n, "stud": k, "socket": j, "turn": t}: '
        "socket j of the new part (default 1) goes onto stud k of the part on line n. The new "
        "part's up is the way that stud points, so on a side stud the new part stands out "
        "sideways with its underside against the side.\n"
        '2. Under a socket: {"part", "colour", "line": n, "under_socket": j, "own_stud": '
        'k, "turn": t}: stud k of the new part (default 1) goes into socket j of the part on '
        "line n, so the new part hangs underneath it.\n"
        '3. On the ground: {"part", "colour", "line": 0, "x": x, "z": z, "turn": t}: '
        "the part stands on the ground (lowest point at y = 0) with its origin above (x, z).\n"
        "turn (0 to 3) is quarter turns of the new part about its own up axis, clockwise seen "
        "from its top, counted in the model's frame: on an upward stud, turn 0 means the "
        "unturned rotation 1 0 0 0 1 0 0 0 1 whatever the rotation of the part below; on a "
        "side stud, turn 0 is the part tipped over the shortest way. Stud and socket "
        "numbers are the ones part_info "
        "lists. Returns: the new line's number and text, the box its body now spans and which way "
        "its own x axis points, what it connects to, and any problem "
        "the checker finds with it (overlaps, a stud that misses). A placement with a problem "
        "is still added: remove it or fix it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "part": {"type": "string"},
            "colour": {"type": "integer", "description": "LDraw colour code."},
            "line": {
                "type": "integer",
                "minimum": 0,
                "description": "The part to attach to; 0 for the ground.",
            },
            "stud": {"type": "integer", "minimum": 1},
            "socket": {"type": "integer", "minimum": 1, "default": 1},
            "under_socket": {"type": "integer", "minimum": 1},
            "own_stud": {"type": "integer", "minimum": 1, "default": 1},
            "turn": {"type": "integer", "minimum": 0, "maximum": 3, "default": 0},
            "x": {"type": "number"},
            "z": {"type": "number"},
        },
        "required": ["part", "colour", "line"],
        "additionalProperties": False,
    },
}

_ADD = {
    "name": "add",
    "description": (
        "Append LDraw lines to the model yourself, by position (" + _COORDS + "). Input: "
        '{"ldraw": "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\\n0 STEP"}: part lines '
        "'1 colour x y z a b c d e f g h i file.dat' (the nine numbers are the rotation "
        "matrix, row by row) and '0 STEP' lines. Use place when you can; use this for a part "
        "place cannot attach (clips, bars, pins, hinges) or for a step line. Returns the new "
        "lines' numbers and what the checker finds about them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"ldraw": {"type": "string"}},
        "required": ["ldraw"],
        "additionalProperties": False,
    },
}

_REMOVE = {
    "name": "remove",
    "description": (
        'Remove parts from the model: {"lines": [12, 13]}. Each becomes a comment, so every '
        "other line keeps its number. Returns what was removed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lines": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 1}
        },
        "required": ["lines"],
        "additionalProperties": False,
    },
}

_MODEL = {
    "name": "model",
    "description": "The model as it is now: every line with its number. Input: {}.",
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}

_CHECK = {
    "name": "check",
    "description": (
        "Check the whole model and see it. Input: {}. Saves it as the next attempt and "
        "returns: a summary line (parts, kinds, problems); every problem, naming the line, "
        "the part and its position, what is wrong and, when it can, what would fix it "
        "(overlaps, studs off the grid or not pressed home, loose parts and what is under "
        "them, parts below the ground, a model that would tip over, unknown parts); "
        "warnings; joints it cannot confirm (clips, bars, pins...); how every part is held; "
        "and one picture with three views: from the front-left above, from the back-right "
        "above, and straight from the front. There is a limit on how many checks a session "
        "has; the reply says how many are left."
    ),
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}

_LOOK = {
    "name": "look",
    "description": (
        'Another view of the model as it is now. Input: {"latitude": degrees above the '
        'horizon (-90 to 90; negative looks from below), "longitude": degrees around (0 from '
        "the front, 90 from the right, 180 from the back, 270 from the left)}; optionally "
        '"open": {"joint name": degrees} or "all" (each as far as the check says it goes) to '
        "see joints opened. Returns one picture; the model is not changed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "latitude": {"type": "number", "minimum": -90, "maximum": 90},
            "longitude": {"type": "number"},
            "open": {
                "anyOf": [
                    {"type": "object", "additionalProperties": {"type": "number"}},
                    {"type": "string", "enum": ["all"]},
                ]
            },
        },
        "required": ["latitude", "longitude"],
        "additionalProperties": False,
    },
}

_SUBMIT = {
    "name": "submit",
    "description": (
        "Replace the whole model with this LDraw text and check it, exactly as check does "
        '(same report, same picture, counts as a check). Input: {"ldraw": "..."}: part '
        "lines '1 colour x y z a b c d e f g h i file.dat' and '0 STEP' lines. Line numbers in "
        "the reply are the lines of the text you sent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"ldraw": {"type": "string"}},
        "required": ["ldraw"],
        "additionalProperties": False,
    },
}

_SUBMIT_BLIND = {
    "name": "submit",
    "description": (
        'Hand in your finished model as LDraw text: {"ldraw": "..."} with part lines '
        "'1 colour x y z a b c d e f g h i file.dat' and '0 STEP' lines. You can do this "
        "once; the reply only confirms that it was saved."
    ),
    "input_schema": _SUBMIT["input_schema"],
}

_REFERENCE = {
    "name": "reference",
    "description": "The reference pictures of what to build. Input: {}. Returns the pictures.",
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}

_BOX = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 3,
    "maxItems": 3,
}

_REMOVE_BOX = {
    "name": "remove_box",
    "description": (
        'Remove every part in a box, to clear a region you will rebuild. Input: {"min": [x, '
        'y, z], "max": [x, y, z], "unit": "ldu" (default) or "studs", "mode": '
        '"centre" (default) | "inside" | "touching"}. With unit "studs", x and z '
        'count studs (20 LDU) and y counts plates (8 LDU), still with y down. mode: "centre" '
        'removes parts whose middle is in the box, "inside" only parts wholly inside it, '
        '"touching" every part that reaches into it. Removed lines become comments, so other '
        "lines keep their numbers. Returns the lines removed and which parts are now loose."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "min": _BOX,
            "max": _BOX,
            "unit": {"type": "string", "enum": ["ldu", "studs"], "default": "ldu"},
            "mode": {
                "type": "string",
                "enum": ["centre", "inside", "touching"],
                "default": "centre",
            },
        },
        "required": ["min", "max"],
        "additionalProperties": False,
    },
}

_FILL = {
    "name": "fill",
    "description": (
        "Fill a box with ordinary bricks and plates, interlocked so they hold together (chosen "
        "by BrickSnap's solver): the quick way to make a chassis, a wall, a core or a body "
        'block. Input: {"at": [x, y, z], "size": [studs in x, studs in z, plates up], '
        '"colour": c, "top": "studs" (default) or "tiles" (a smooth top), '
        '"hollow": false (default) or true (walls one stud thick, open top and bottom)}. '
        '"at" is the box\'s corner with the smallest x and z, at its BOTTOM, in LDU: y is the '
        "height the box stands on (0 on the ground, or the top of the part below it), and the "
        "box goes up from there. x and z must be multiples of 10; to sit on studs, the box's "
        "edges lie halfway between studs, so its corner is a stud's x and z minus 10. A brick "
        "is 3 plates. Returns the lines added, the studs left free on top (for place), and "
        "what the checker says about the new parts."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "at": _BOX,
            "size": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1},
                "minItems": 3,
                "maxItems": 3,
            },
            "colour": {"type": "integer"},
            "top": {"type": "string", "enum": ["studs", "tiles"], "default": "studs"},
            "hollow": {"type": "boolean", "default": False},
        },
        "required": ["at", "size", "colour"],
        "additionalProperties": False,
    },
}

_MIRROR = {
    "name": "mirror",
    "description": (
        'Copy parts to the other side of the model\'s middle plane, x = 0 (or x = "plane_x"): '
        '{"lines": [12, 13, 20], "plane_x": 0}. A part that is its own mirror image (most '
        "bricks, plates, slopes, round parts) is copied as the same part, turned to match. A "
        "left or right part (a wing, a wedge) is copied as its other-hand version when the "
        "library has one whose name differs only by Left/Right, and the reply names it. "
        "Any other part is refused, with the reason: build that side yourself. A part lying "
        "across the plane is not copied. Returns the new lines and what the checker says "
        "about them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lines": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 1},
            "plane_x": {"type": "number", "default": 0},
        },
        "required": ["lines"],
        "additionalProperties": False,
    },
}

_MODULES = {
    "name": "modules",
    "description": (
        "The proven moving modules (wheels, door and lid hinges, turntables). {} lists them; "
        '{"name": n} gives one\'s card and a picture at rest and opened.'
    ),
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    },
}

_PLACE_MODULE = {
    "name": "place_module",
    "description": (
        "Put a module in by connection, as place does: its anchor (the side that stays) goes "
        "on a stud, under a socket, or on the ground (then the whole module's lowest point, the "
        "tyres for wheels, is at y = 0); turn as for place. Appends its parts and a joint line "
        '(\'0 !BRICKSNAP JOINT ...\'). Extra: "name" (one word), "moving_colour". Returns the '
        "lines, which way it opens, and the movement verdict."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "module": {"type": "string"},
            "colour": {"type": "integer"},
            "line": {"type": "integer", "minimum": 0},
            "stud": {"type": "integer", "minimum": 1},
            "socket": {"type": "integer", "minimum": 1},
            "under_socket": {"type": "integer", "minimum": 1},
            "own_stud": {"type": "integer", "minimum": 1},
            "turn": {"type": "integer", "minimum": 0, "maximum": 3},
            "x": {"type": "number"},
            "z": {"type": "number"},
            "name": {"type": "string"},
            "moving_colour": {"type": "integer"},
        },
        "required": ["module", "colour", "line"],
        "additionalProperties": False,
    },
}

_JOINT = {
    "name": "joint",
    "description": (
        "Declare a joint for two parts you placed (a wheel on a wheel pin, a part turning on a "
        'Technic pin): {"name", "kind": "swing"|"spin"|"wheel", "fixed": [the one part that '
        "stays], "
        '"moving": [the one part that turns, and a wheel\'s tyre], "at": [x, y, z] and "axis": '
        '[dx, dy, dz] (its turning line), "min"/"max" degrees for a swing (as placed is 0; '
        "positive turns by the right-hand rule about axis, y down)}. Accepted only when that "
        "line is the pin's own; clips, bars, hinges and balls cannot be confirmed yet (use a "
        "module). What is built on the moving part rides with it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "kind": {"type": "string", "enum": ["swing", "spin", "wheel"]},
            "fixed": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            "moving": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            "at": _BOX,
            "axis": _BOX,
            "min": {"type": "number"},
            "max": {"type": "number"},
        },
        "required": ["name", "kind", "fixed", "moving", "at", "axis"],
        "additionalProperties": False,
    },
}

TOOLS = [
    _SEARCH,
    _PART_INFO,
    _PLACE,
    _ADD,
    _FILL,
    _MIRROR,
    _REMOVE,
    _REMOVE_BOX,
    _MODEL,
    _CHECK,
    _LOOK,
    _SUBMIT,
    _MODULES,
    _PLACE_MODULE,
    _JOINT,
]
BLIND_TOOLS = [_SUBMIT_BLIND]

_PLAYBOOK = {
    "name": "playbook",
    "description": (
        "How set designers build one kind of subject at one size (from a study of official "
        'sets). {"kind": "vehicle", "parts": 100} returns the playbook of that kind nearest '
        "that many parts (what core to build first, how to make it strong, how the outside "
        "attaches, what moves, in what order) and says which it chose and why. {} lists the "
        'kinds, one line each. {"table": true} returns the parts sorted by job (side-stud '
        "bricks, brackets, curved slopes, clips and bars, hinges...) with their numbers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "description": "vehicle, hollow, creature, plant or machine",
            },
            "parts": {"type": "integer", "minimum": 1, "description": "About how many parts."},
            "table": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    },
}


def tools_for(folder: Path) -> list[dict[str, Any]]:
    cfg = _config(folder)
    base = BLIND_TOOLS if cfg.get("mode") == "blind" else TOOLS
    if cfg.get("guide") is True and base is TOOLS:
        base = [*base, _PLAYBOOK]
    if _references(folder):
        base = [*base, _REFERENCE]
    return base


# ---- the folder ---------------------------------------------------------------------------


def _config(folder: Path) -> dict[str, Any]:
    try:
        data = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _references(folder: Path) -> list[Path]:
    ref = folder / "reference"
    if not ref.is_dir():
        return []
    return sorted(p for p in ref.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))


def _model(folder: Path) -> str:
    try:
        return (folder / "model.ldr").read_text(encoding="utf-8")
    except OSError:
        return ""


def _save_model(folder: Path, text: str) -> None:
    from bricksnap.designer.runner import redact

    text = redact(text)
    if text and not text.endswith("\n"):
        text += "\n"
    tmp = folder / "model.ldr.tmp"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(folder / "model.ldr")


def _attempts(folder: Path) -> list[Path]:
    """The checks made in the session (attempt 0, the starting model, is not one of them)."""
    return sorted(p for p in (folder / "attempts").glob("attempt-*.ldr") if p.stem != "attempt-000")


def _png(img: Image.Image) -> bytes:
    def encode(im: Image.Image) -> bytes:
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    data = encode(img)
    scale = 1.0
    current = img
    while len(data) > MAX_IMAGE_BYTES and scale > 0.3:
        scale *= 0.85
        size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        current = img.convert("RGB").resize(size, Image.Resampling.LANCZOS).quantize(colors=192)
        data = encode(current)
    return data


def _image_block(path: Path) -> dict[str, Any]:
    with Image.open(path) as im:
        data = _png(im.copy())
    return {"type": "image", "media_type": "image/png", "data": base64.b64encode(data).decode()}


def _text(t: str) -> dict[str, Any]:
    return {"type": "text", "text": t}


def _error(t: str) -> list[dict[str, Any]]:
    return [_text("ERROR: " + t)]


def _scrub(text: str, folder: Path) -> str:
    from bricksnap.designer.runner import redact

    for form in sorted({str(folder.absolute()), str(folder.resolve())}, key=len, reverse=True):
        text = text.replace(form, "the work folder")
    return redact(text)


def _numbered(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return "(the model is empty)"
    return "\n".join(f"{i:3}: {line}" for i, line in enumerate(lines, 1))


# ---- tools --------------------------------------------------------------------------------


def _search(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.search import load_index

    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return _error("query must be some words, such as 'plate 1 x 2 with clip'.")
    limit = args.get("limit", 15)
    if not isinstance(limit, int) or not 1 <= limit <= 40:
        return _error("limit must be a whole number from 1 to 40.")
    hits = load_index().search(query[:200], limit)
    lines = [f"{i}. {h.line()}" for i, h in enumerate(hits, 1)]
    head = f"Parts for '{query[:200]}', best first (sizes: studs in x by studs in z by plates):"
    return [_text(head + "\n" + "\n".join(lines))]


def _f(v: float) -> str:
    from bricksnap.lab.ldraw_lib import fmt

    return fmt(round(float(v), 1))


def part_text(name: str) -> tuple[str, str]:
    """(file name, the text part_info returns) for a part; raises KeyError when unknown."""
    from bricksnap.lab.ldraw_lib import direction_word, library, origin_note
    from bricksnap.lab.place import sockets
    from bricksnap.lab.search import exclusion_reason
    from bricksnap.lab.validate import numbered_studs

    lib = library()
    found = lib.resolve(name) or lib.resolve(name + ".dat")
    if found is None or found[0] != "part":
        raise KeyError(name)
    key = found[1]
    part = lib.part(key)
    w, d, h = part.size()
    out = [f"{key}: {part.description} (category {part.header.category})"]
    why = exclusion_reason(key, part.description, part.header.org, part.header.category)
    if why:
        out.append(
            f"Note: this file is {why} in the library's terms; it can be used, but prefer a "
            "plain current part."
        )
    out.append(
        f"Size: {_f(w)} studs (x) by {_f(d)} studs (z) by {_f(h)} plates (height) of its body."
    )
    out.append("Origin: " + origin_note(part) + ". (y points down: smaller y is higher.)")
    studs = numbered_studs(part)
    if studs:
        out.append(f"Studs ({len(studs)}), numbered for place (stud base position, way it points):")
        if len(studs) > 60:
            out.append("  (only the first 60 are listed; the numbering continues row by row)")
        for n, s in enumerate(studs[:60], 1):
            out.append(
                f"  stud {n}: at ({', '.join(_f(v) for v in s.pos)}) pointing "
                f"{direction_word(s.axis)}"
            )
    else:
        out.append("Studs: none.")
    socks = sockets(part)
    if socks:
        out.append(
            f"Sockets underneath ({len(socks)}), numbered for place (where a stud's base goes):"
        )
        if len(socks) > 60:
            out.append("  (only the first 60 are listed)")
        for n, s in enumerate(socks[:60], 1):
            kind = " (an open tube or ring: takes a stud inside it)" if s.kind == "tube" else ""
            out.append(f"  socket {n}: at ({', '.join(_f(v) for v in s.pos)}){kind}")
    else:
        out.append("Sockets underneath: none found (it cannot sit on studs).")
    others = part.others
    if others:
        out.append("Other connectors (named from its geometry, never checked):")
        for c in others[:30]:
            out.append(
                f"  {c.kind} at ({', '.join(_f(v) for v in c.pos)}), axis {direction_word(c.axis)}"
            )
    words = [w for w in part.other_joint_words() if w not in {c.kind for c in others}]
    if words:
        out.append("Its name says it also joins by: " + ", ".join(words) + " (not checked).")
    return key, "\n".join(out)


def _part_info(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab import picture
    from bricksnap.lab.search import close_names

    if args.get("line") is not None:
        if args.get("part") is not None:
            return _error("give part or line, not both.")
        return _placed_info(folder, args["line"])
    name = args.get("part")
    if not isinstance(name, str) or not name.strip():
        return _error("part must be a file name such as 3001.dat (or line, a line of the model).")
    try:
        key, text = part_text(name.strip())
    except KeyError:
        close = ", ".join(close_names(name)) or "none"
        return _error(f"there is no part '{name[:60]}'. Close names: {close}. Use search_parts.")
    blocks = [_text(text)]
    out = folder / "parts" / (re.sub(r"[^a-z0-9._-]", "_", key) + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not out.exists():
            picture.part_sheet(key, out)
        blocks.append(_image_block(out))
    except picture.PictureError as e:
        blocks.append(_text(f"(No picture: {e})"))
    return blocks


def _placed_info(folder: Path, line: Any) -> list[dict[str, Any]]:
    """part_info for the part on a line of the model: its studs and sockets where they are
    in the model, numbered as always, with the studs already taken marked."""
    from bricksnap.lab.ldraw_lib import direction_word, fmt
    from bricksnap.lab.place import sockets
    from bricksnap.lab.validate import check, numbered_studs

    if not isinstance(line, int) or isinstance(line, bool):
        return _error("line must be a line number.")
    text = _model(folder)
    report = check(text)
    placed = next((p for p in report.placed if p.line == line), None)
    if placed is None:
        n = len(text.splitlines())
        return _error(f"line {line} is not a part the checker can read (the model has {n} lines).")
    part = placed.part
    taken: dict[int, int] = {}
    for link in report.links:
        if link.holder == line:
            for k in link.studs:
                taken[k] = link.held
    out = [
        f"Line {line}: {placed.key} {part.description}, at {' '.join(fmt(v) for v in placed.pos)} "
        f"with rotation {' '.join(fmt(v) for v in placed.m.ravel())}.",
        "Positions below are in the model's coordinates (" + _COORDS + ")",
    ]
    studs = numbered_studs(part)
    if studs:
        out.append(f"Studs ({len(studs)}):")
        for n, s in enumerate(studs[:80], 1):
            w = placed.to_world(s.pos)
            d = placed.m @ s.axis
            mark = f"  (taken: line {taken[n]} sits on it)" if n in taken else ""
            out.append(
                f"  stud {n}: at ({', '.join(_f(v) for v in w)}) pointing {direction_word(d)}{mark}"
            )
    else:
        out.append("Studs: none.")
    socks = sockets(part)
    if socks:
        out.append(f"Sockets underneath ({len(socks)}):")
        for n, sk in enumerate(socks[:80], 1):
            w = placed.to_world(sk.pos)
            kind = " (open tube or ring)" if sk.kind == "tube" else ""
            out.append(f"  socket {n}: at ({', '.join(_f(v) for v in w)}){kind}")
    for c in part.others[:20]:
        w = placed.to_world(c.pos)
        out.append(
            f"  {c.kind} at ({', '.join(_f(v) for v in w)}), axis "
            f"{direction_word(placed.m @ c.axis)}"
        )
    return [_text("\n".join(out))]


def _near_a_joint(text: str, report: Any, lines: list[int]) -> bool:
    """Whether any of these lines belongs to a joint, rides on one, or stands where what turns
    could reach it (inside the ball round the joint's line that its moving parts sweep)."""
    from bricksnap.lab.movement import _sides, plan
    from bricksnap.lab.validate import _world_bbox

    try:
        groups, _ = plan(text, report)
    except Exception:  # an unreadable joint: let the full check say so
        return True
    by_line = {p.line: p for p in report.placed}
    wanted = [by_line[n] for n in lines if n in by_line]
    for g in groups:
        ride = set(_sides(report, g.fixed, g.moving).riders) | g.fixed | g.moving
        if ride & set(lines):
            return True
        radius = 0.0
        for n in ride:
            if n in by_line:
                lo, hi = _world_bbox(by_line[n], 2.0)
                for c in (lo, hi):
                    radius = max(radius, float(np.linalg.norm(c - g.at)))
        for p in wanted:
            lo, hi = _world_bbox(p, 2.0)
            centre, half = (lo + hi) / 2, float(np.linalg.norm(hi - lo)) / 2
            if float(np.linalg.norm(centre - g.at)) - half <= radius:
                return True
    return False


def _report_for(text: str, lines: list[int] | None) -> Any:
    """The checker's report. With ``lines`` (the parts a call just added), the movement check
    runs only when they belong to, ride on or stand near a joint; else always."""
    from bricksnap.lab import movement
    from bricksnap.lab.joints import parse
    from bricksnap.lab.ldraw_lib import library
    from bricksnap.lab.validate import check

    if lines is None:
        return check(text)
    joints, errors = parse(text)
    report = check(text, movement=False)
    if (joints or errors) and (errors or _near_a_joint(text, report, lines)):
        movement.apply(text, report, library())
    return report


def _quick(
    folder: Path, text: str, lines: list[int], brief: bool = False, report: Any = None
) -> str:
    """What the checker says about these lines in this model (``brief``: problems in full,
    connections as a count, for a group of many new lines)."""
    report = report if report is not None else _report_for(text, lines)
    wanted = set(lines)
    out = []
    held = [x for x in report.links if x.held in wanted or x.holder in wanted]
    if brief:
        inner = [x for x in held if x.held in wanted and x.holder in wanted]
        outer = [x for x in held if (x.held in wanted) != (x.holder in wanted)]
        others = sorted({x.holder if x.held in wanted else x.held for x in outer})
        studs = sum(len(x.studs) for x in outer)
        out.append(
            f"- {len(inner)} connections among the new parts; {len(outer)} with the rest of the "
            f"model ({studs} studs), to "
            + (f"lines {', '.join(map(str, others[:30]))}" if others else "nothing")
        )
    else:
        for x in held:
            studs = f"{len(x.studs)} stud{'s' if len(x.studs) != 1 else ''}"
            out.append(
                f"- line {x.held} is held by {studs} of line {x.holder}"
                + (f" ({x.how})" if x.how != "on top" else "")
            )
    issues = [
        i for i in report.issues if wanted & set(i.lines) and i.kind != "held by unchecked joints"
    ]
    for i in issues[:25]:
        out.append(f"- {i.severity.upper()}: {i.text}")
    if len(issues) > 25:
        out.append(f"- ... and {len(issues) - 25} more; check shows them all.")
    on_ground = not any(i.kind == "ground" for i in report.issues)
    ground = [g for g in report.grounded if g in wanted and on_ground]
    if brief and len(ground) > 3:
        out.append(f"- {len(ground)} of them stand on the ground")
    else:
        for g in ground:
            out.append(f"- line {g} stands on the ground")
    if not out:
        out.append("- not connected to anything yet")
    return "\n".join(out)


def _append(folder: Path, new_lines: list[str]) -> tuple[str, list[int]]:
    text = _model(folder)
    lines = text.splitlines()
    first = len(lines) + 1
    lines.extend(new_lines)
    text = "\n".join(lines) + "\n"
    _save_model(folder, text)
    return text, list(range(first, first + len(new_lines)))


def _where_args(args: dict[str, Any]) -> dict[str, Any]:
    """The arguments place and place_module share, checked: whole numbers stay whole (1.5
    quarter turns is refused, not cut down), coordinates are ordinary numbers."""
    colour = _whole(args, "colour", None, 0, 0x2FFFFFF)
    line = _whole(args, "line", None, 0)
    if colour is None or line is None:
        raise ValueError("colour and line are needed.")
    return {
        "colour": colour,
        "line": line,
        "stud": _whole(args, "stud", None, 1),
        "socket": _whole(args, "socket", 1, 1),
        "under_socket": _whole(args, "under_socket", None, 1),
        "own_stud": _whole(args, "own_stud", 1, 1),
        "turn": _whole(args, "turn", 0, 0, 3),
        "x": _coord(args, "x"),
        "z": _coord(args, "z"),
    }


def _place(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.place import PlaceError, place

    part = args.get("part")
    if not isinstance(part, str) or not part.strip():
        return _error("part must be a file name such as 3001.dat.")
    try:
        where = _where_args(args)
        result = place(_model(folder), part.strip(), **where)
    except (PlaceError, ValueError) as e:
        return _error(str(e))
    text, numbers = _append(folder, [result.line])
    sideways = ""
    if _config(folder).get("guide") is True:
        sideways = _sideways_studs(text, numbers[0])
    return [
        _text(
            f"Added as line {numbers[0]}: {result.line}\n{result.note}\nWhat the checker says "
            f"about it:\n{_quick(folder, text, numbers)}{sideways}"
        )
    ]


def _sideways_studs(text: str, line: int) -> str:
    """Guide mode only: for a part placed so that its studs no longer point up (a panel's
    plate on side studs), its studs in the model, numbered for place, with the way each
    points and whether it is free; empty for any other part."""
    from bricksnap.lab.ldraw_lib import direction_word
    from bricksnap.lab.validate import check, numbered_studs

    report = check(text, movement=False)
    placed = next((p for p in report.placed if p.line == line), None)
    if placed is None:
        return ""
    studs = numbered_studs(placed.part)
    if not studs or abs(float((placed.m @ studs[0].axis)[1])) > 0.5:
        return ""
    taken = {k for link in report.links if link.holder == line for k in link.studs}
    out = [f"\nIts studs now (numbered for place on line {line}):"]
    for n, s in enumerate(studs[:24], 1):
        w = placed.to_world(s.pos)
        out.append(
            f"  stud {n}: at ({', '.join(_f(v) for v in w)}) pointing "
            f"{direction_word(placed.m @ s.axis)}" + ("  (taken)" if n in taken else "  (free)")
        )
    if len(studs) > 24:
        out.append(f"  ... and {len(studs) - 24} more: part_info with this line lists them all.")
    return "\n".join(out)


def _add(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    ldraw = args.get("ldraw")
    if not isinstance(ldraw, str) or not ldraw.strip():
        return _error("ldraw must be LDraw text: part lines and 0 STEP lines.")
    new = [ln.strip() for ln in ldraw.strip().splitlines() if ln.strip()]
    if len(new) > 400:
        return _error("add at most 400 lines at a time.")
    text, numbers = _append(folder, new)
    parts = [n for n, ln in zip(numbers, new, strict=True) if ln.startswith("1 ")]
    head = (
        f"Added lines {numbers[0]} to {numbers[-1]}."
        if len(numbers) > 1
        else f"Added line {numbers[0]}."
    )
    if not parts:
        return [_text(head)]
    return [_text(head + "\nWhat the checker says about them:\n" + _quick(folder, text, parts))]


def _remove(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    lines_arg = args.get("lines")
    if (
        not isinstance(lines_arg, list)
        or not lines_arg
        or not all(isinstance(n, int) and not isinstance(n, bool) for n in lines_arg)
    ):
        return _error("lines must be a list of line numbers, such as [12, 13].")
    lines = _model(folder).splitlines()
    bad = [n for n in lines_arg if not 1 <= n <= len(lines)]
    if bad:
        return _error(f"there is no line {bad[0]} (the model has {len(lines)} lines).")
    done = []
    for n in sorted(set(lines_arg)):
        if lines[n - 1].startswith("0 removed:"):
            continue
        done.append(f"line {n}: {lines[n - 1]}")
        lines[n - 1] = "0 removed: " + lines[n - 1]
    _save_model(folder, "\n".join(lines) + "\n")
    return [_text("Removed " + ("; ".join(done) if done else "nothing (already removed)") + ".")]


def _model_tool(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [_text(_numbered(_model(folder)))]


def _check_text(folder: Path, text: str, label: str) -> list[dict[str, Any]]:
    from bricksnap.lab import picture
    from bricksnap.lab.validate import check

    cfg = _config(folder)
    limit = int(cfg.get("max_checks", DEFAULT_MAX_CHECKS))
    done = len(_attempts(folder))
    if done >= limit:
        return _error(
            f"this session has used all {limit} checks. Stop here and say in a few lines what "
            "you built and what you would still change."
        )
    n = done + 1
    adir = folder / "attempts"
    adir.mkdir(parents=True, exist_ok=True)
    stem = adir / f"attempt-{n:03d}"
    from bricksnap.designer.runner import redact

    text = redact(text)
    stem.with_suffix(".ldr").write_text(text, encoding="utf-8")
    report = check(text)
    body = report.text()
    left = limit - n
    body = f"Attempt {n} ({label}). Checks left after this one: {left}.\n\n" + body
    (adir / f"attempt-{n:03d}-report.txt").write_text(body + "\n", encoding="utf-8")
    blocks = [_text(body)]
    png = adir / f"attempt-{n:03d}.png"
    try:
        if report.placed:
            picture.model_sheet(text, png, title=f"Attempt {n}: {report.summary()}")
            if png.exists():
                blocks.append(_image_block(png))
    except picture.PictureError as e:
        blocks.append(_text(f"(No picture: {e})"))
    return blocks


def start_model(folder: Path, text: str) -> str:
    """Begin the session with ``text`` as the model (``--start``): it is saved as the model
    and checked as attempt 0, which does not count as one of the session's checks. A model
    whose last line is not ``0 STEP`` gets one, so what is added later is a step of its own.
    Returns the report's summary line."""
    from bricksnap.lab import picture
    from bricksnap.lab.validate import check

    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip().upper() != "0 STEP":
        lines.append("0 STEP")
    text = "\n".join(lines) + "\n"
    _save_model(folder, text)
    adir = folder / "attempts"
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "attempt-000.ldr").write_text(_model(folder), encoding="utf-8")
    report = check(_model(folder))
    body = "Attempt 0 (the model you start from).\n\n" + report.text()
    (adir / "attempt-000-report.txt").write_text(body + "\n", encoding="utf-8")
    if report.placed:
        with contextlib.suppress(picture.PictureError):
            picture.model_sheet(text, adir / "attempt-000.png", title="Start: " + report.summary())
    return report.summary()


def _check(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    text = _model(folder)
    if not text.strip():
        return _error("the model is empty: add parts with place or add first.")
    return _check_text(folder, text, "the model as built")


def _look(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab import picture

    lat, lon = args.get("latitude"), args.get("longitude")
    if not isinstance(lat, int | float) or not isinstance(lon, int | float) or not -90 <= lat <= 90:
        return _error("latitude (-90 to 90) and longitude (degrees) must be numbers.")
    text = _model(folder)
    if not any(ln.startswith("1 ") for ln in text.splitlines()):
        return _error("the model has no parts yet.")
    if args.get("open") is not None:
        try:
            text = _opened_for_look(text, args["open"])
        except ValueError as e:
            return _error(str(e))
    ldir = folder / "looks"
    ldir.mkdir(parents=True, exist_ok=True)
    out = ldir / f"look-{len(list(ldir.glob('look-*.png'))) + 1:03d}.png"
    try:
        picture.view(text, out, float(lat), float(lon))
    except picture.PictureError as e:
        return _error(str(e))
    return [_image_block(out)]


def _opened_for_look(text: str, want: Any) -> str:
    from bricksnap.lab.joints import opened, parse
    from bricksnap.lab.movement import open_angles

    joints, _ = parse(text)
    if not joints:
        raise ValueError("the model has no joints to open (put one in with place_module).")
    names = ", ".join(j.name for j in joints)
    if want == "all":
        angles = open_angles(text)  # each only as far as the check says it goes
    elif isinstance(want, dict) and want:
        by = {j.name.lower(): j for j in joints}
        angles = {}
        for k, v in want.items():
            j = by.get(str(k).lower())
            if j is None:
                raise ValueError(f"there is no joint '{str(k)[:40]}'. The joints are: {names}.")
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                raise ValueError(f"the angle for '{j.name}' must be a number of degrees.")
            if not j.turns_freely and not j.low - 1e-6 <= v <= j.high + 1e-6:
                raise ValueError(f"'{j.name}' {j.words()}; give an angle in that range.")
            angles[j.name] = float(v)
    else:
        raise ValueError(f'open is {{"joint name": degrees}} or "all". The joints are: {names}.')
    return opened(text, angles)


def _modules(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab import modules, picture

    name = args.get("name")
    if name is None:
        out = [
            "The proven moving modules (put one in with place_module; ask for one by name "
            "for its parts and a picture):"
        ]
        for m in modules.MODULES.values():
            out.append(
                f"- {m.name}: {m.title}. It {m.range_words()}. Attaches: {m.attach}. "
                f"Moves: {m.moves}. Size: {modules.size_words(m)}."
            )
        return [_text("\n".join(out))]
    if not isinstance(name, str) or name.strip().lower() not in modules.MODULES:
        return _error(
            f"there is no module '{str(name)[:40]}'. The modules are: {', '.join(modules.MODULES)}."
        )
    m = modules.MODULES[name.strip().lower()]
    blocks = [_text(modules.card(m))]
    out = folder / "modules" / f"{m.name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not out.exists():
            modules.module_sheet(m.name, out)
        blocks.append(_image_block(out))
    except picture.PictureError as e:
        blocks.append(_text(f"(No picture: {e})"))
    return blocks


def _place_module(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.modules import place_module
    from bricksnap.lab.place import PlaceError

    module = args.get("module")
    if not isinstance(module, str) or not module.strip():
        return _error("module must be a module's name; modules lists them.")
    name = args.get("name")
    if name is not None and not isinstance(name, str):
        return _error("name must be one word, such as left-door.")
    try:
        where = _where_args(args)
        mc = _whole(args, "moving_colour", None, 0, 0x2FFFFFF)
        result = place_module(_model(folder), module, **where, joint_name=name, moving_colour=mc)
    except (PlaceError, ValueError) as e:
        return _error(str(e))
    text, numbers = _append(folder, result.lines)
    report = _report_for(text, None)
    j = result.joint
    parts = numbers[:-1]
    shown = "\n".join(f"  line {n}: {ln}" for n, ln in zip(numbers, result.lines, strict=True))
    return [
        _text(
            f"Added the module as lines {numbers[0]} to {numbers[-1]}: its parts, then its joint "
            f"'{j.name}' on line {numbers[-1]} (FIXED {', '.join(map(str, j.fixed))}; MOVING "
            f"{', '.join(map(str, j.moving))}; it {j.words()}).\n{shown}\n{result.note}\n"
            f"What the checker says about it:\n{_quick(folder, text, parts, report=report)}"
            + _movement_lines(report)
        )
    ]


def _movement_lines(report: Any) -> str:
    if not report.movement:
        return ""
    return "\nMOVEMENT:\n" + "\n".join("- " + x for x in report.movement)


def _joint(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.joints import NAME, Joint, joint_line, parse
    from bricksnap.lab.validate import check

    name = args.get("name")
    if not isinstance(name, str) or not NAME.match(name.strip().replace(" ", "-")):
        return _error("name must be one word of letters, digits, - and _, such as tail-flap.")
    name = name.strip().replace(" ", "-")
    kind = str(args.get("kind", "")).lower()
    if kind not in ("swing", "spin", "wheel"):
        return _error('kind is "swing", "spin" or "wheel".')
    lists = {}
    for key in ("fixed", "moving"):
        v = args.get(key)
        if (
            not isinstance(v, list)
            or not v
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in v)
        ):
            return _error(f"{key} must be a list of line numbers, such as [12].")
        lists[key] = sorted(set(v))
    if set(lists["fixed"]) & set(lists["moving"]):
        return _error("a line cannot be both fixed and moving.")
    try:
        at = np.array(_numbers(args.get("at"), 3, "at"))
        axis = np.array(_numbers(args.get("axis"), 3, "axis"))
    except ValueError as e:
        return _error(str(e))
    if float(np.linalg.norm(axis)) < 1e-6:
        return _error("axis must not be [0, 0, 0].")
    low = high = 0.0
    if kind == "swing":
        lo, hi = args.get("min"), args.get("max")
        if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in (lo, hi)):
            return _error("a swing needs min and max, in degrees (the parts as placed are at 0).")
        assert isinstance(lo, int | float) and isinstance(hi, int | float)
        low, high = float(lo), float(hi)
        if not -360 <= low <= 0 <= high <= 360 or high - low <= 0:
            return _error(
                "min must be from -360 to 0 and max from 0 to 360, not both 0 (the parts as "
                "placed are at 0)."
            )
    text = _model(folder)
    if name.lower() in {j.name.lower() for j in parse(text)[0]}:
        return _error(f"there is already a joint called '{name}'.")
    report = check(text, movement=False)
    by_line = {p.line: p for p in report.placed}
    for n in lists["fixed"] + lists["moving"]:
        if n not in by_line:
            return _error(f"line {n} is not a part of the model.")
    j = Joint(
        name,
        kind.upper(),
        at,
        axis / np.linalg.norm(axis),
        lists["fixed"],
        lists["moving"],
        low,
        high,
    )
    from bricksnap.lab.ldraw_lib import library
    from bricksnap.lab.movement import confirm

    why = confirm(j, report, library())
    if why:
        return _error(
            f"the joint is not accepted: {why}. A module (modules) is proven and "
            "needs no confirming."
        )
    text, numbers = _append(folder, [joint_line(j)])
    return [
        _text(
            f"Added the joint '{name}' as line {numbers[0]}: {joint_line(j)}"
            + (_movement_lines(_report_for(text, None)) or "\n(The checker could not read it.)")
        )
    ]


def _submit(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    ldraw = args.get("ldraw")
    if not isinstance(ldraw, str) or not ldraw.strip():
        return _error("ldraw must be the whole model as LDraw text.")
    text = "\n".join(ln.rstrip() for ln in ldraw.strip().splitlines()) + "\n"
    if _config(folder).get("mode") == "blind":
        final = folder / "final.ldr"
        if final.exists():
            return _error("the model has already been handed in; a session hands in once.")
        if not any(ln.split()[:1] == ["1"] for ln in text.splitlines()):
            return _error("there are no part lines (lines starting with 1) in what you sent.")
        from bricksnap.designer.runner import redact

        final.write_text(redact(text), encoding="utf-8")
        _save_model(folder, text)
        return [_text("Saved. Your model has been handed in.")]
    _save_model(folder, text)
    return _check_text(folder, text, "submitted as a whole file")


def _reference(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    refs = _references(folder)
    if not refs:
        return _error("there are no reference pictures in this session.")
    blocks: list[dict[str, Any]] = [_text(f"{len(refs)} reference picture(s) of what to build:")]
    for p in refs[:6]:
        blocks.append(_image_block(p))
    return blocks


MAX_COORD = 100_000


def _numbers(v: Any, n: int, what: str) -> list[float]:
    if (
        not isinstance(v, list)
        or len(v) != n
        or not all(isinstance(x, int | float) and not isinstance(x, bool) for x in v)
    ):
        raise ValueError(f"{what} must be a list of {n} numbers.")
    if not all(math.isfinite(x) and abs(x) <= MAX_COORD for x in v):
        raise ValueError(f"{what} must be ordinary numbers between -{MAX_COORD} and {MAX_COORD}.")
    return [float(x) for x in v]


def _whole(
    args: dict[str, Any], key: str, default: Any = None, lo: int = 0, hi: int = 1_000_000
) -> Any:
    """A whole-number argument (or its default): refused when it is not one, is not finite,
    or is out of range, rather than cut down."""
    v = args.get(key, default)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise ValueError(f"{key} must be a whole number.")
    if float(v) != int(v):
        raise ValueError(f"{key} must be a whole number, not {v:g}.")
    if not lo <= int(v) <= hi:
        raise ValueError(f"{key} must be from {lo} to {hi}.")
    return int(v)


def _coord(args: dict[str, Any], key: str) -> float:
    v = args.get(key, 0.0)
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise ValueError(f"{key} must be a number.")
    if abs(v) > MAX_COORD:
        raise ValueError(f"{key} must be between -{MAX_COORD} and {MAX_COORD}.")
    return float(v)


def _loose_after(text: str) -> str:
    from bricksnap.lab.validate import check

    report = check(text)
    loose = [i for i in report.problems if i.kind == "loose"]
    if not loose:
        return "Nothing is loose now."
    lines = sorted({n for i in loose for n in i.lines})
    shown = ", ".join(map(str, lines[:40])) + (
        f" and {len(lines) - 40} more" if len(lines) > 40 else ""
    )
    return f"Now loose ({len(lines)} parts): lines {shown}. Remove them too, or hold them again."


def _remove_box(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.edit import parts_in_box

    try:
        lo = np.array(_numbers(args.get("min"), 3, "min"))
        hi = np.array(_numbers(args.get("max"), 3, "max"))
    except ValueError as e:
        return _error(str(e))
    unit = args.get("unit", "ldu")
    mode = args.get("mode", "centre")
    if unit not in ("ldu", "studs") or mode not in ("centre", "inside", "touching"):
        return _error('unit is "ldu" or "studs"; mode is "centre", "inside" or "touching".')
    if unit == "studs":
        scale = np.array([20.0, 8.0, 20.0])
        lo, hi = lo * scale, hi * scale
    text = _model(folder)
    found = parts_in_box(text, lo, hi, mode)
    if not found:
        return [_text("No part is in that box (nothing was removed).")]
    lines = text.splitlines()
    for p in found:
        lines[p.line - 1] = "0 removed: " + lines[p.line - 1]
    text = "\n".join(lines) + "\n"
    _save_model(folder, text)
    kinds: dict[str, int] = {}
    for p in found:
        kinds[p.key] = kinds.get(p.key, 0) + 1
    shown = ", ".join(str(p.line) for p in found[:60]) + (
        f" and {len(found) - 60} more" if len(found) > 60 else ""
    )
    what = ", ".join(f"{n} x {k}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))
    box = " to ".join("(" + ", ".join(fmt_n(v) for v in c) + ")" for c in (lo, hi))
    return [
        _text(
            f"Removed {len(found)} parts in the box {box} (LDU): lines {shown} ({what}).\n"
            + _loose_after(text)
        )
    ]


def fmt_n(v: float) -> str:
    from bricksnap.lab.ldraw_lib import fmt

    return fmt(round(float(v), 1))


def _fill(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.edit import EditError, fill

    try:
        at = _numbers(args.get("at"), 3, "at")
        size = args.get("size")
        if (
            not isinstance(size, list)
            or len(size) != 3
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in size)
        ):
            raise ValueError("size must be three whole numbers: studs in x, studs in z, plates up.")
        colour = args.get("colour")
        if not isinstance(colour, int) or isinstance(colour, bool):
            raise ValueError("colour must be an LDraw colour code.")
        hollow = args.get("hollow", False)
        if not isinstance(hollow, bool):
            raise ValueError("hollow is true or false.")
        result = fill(
            (at[0], at[1], at[2]),
            (size[0], size[1], size[2]),
            colour,
            top=str(args.get("top", "studs")),
            hollow=hollow,
        )
    except (ValueError, EditError) as e:
        return _error(str(e))
    text, numbers = _append(folder, result.lines)
    parts = [n for n, ln in zip(numbers, result.lines, strict=True) if ln.startswith("1 ")]
    free = result.free_studs
    if free:
        ys = sorted({s[1] for s in free})
        xs = sorted({s[0] for s in free})
        zs = sorted({s[2] for s in free})
        studs = (
            f"{len(free)} studs free on top, at y {', '.join(fmt_n(y) for y in ys)}: x "
            f"{fmt_n(xs[0])} to {fmt_n(xs[-1])}, z {fmt_n(zs[0])} to {fmt_n(zs[-1])} (every 20 "
            "LDU). Use part_info with one of these lines to place on them."
        )
    else:
        studs = "No studs on top (a smooth top)."
    head = (
        f"Added {result.parts} parts as lines {parts[0]} to {parts[-1]} (with 0 STEP lines "
        "between the solver's steps)."
    )
    notes = (" " + " ".join(result.notes)) if result.notes else ""
    return [
        _text(
            f"{head}{notes}\n{studs}\nWhat the checker says about them:\n"
            + _quick(folder, text, parts, brief=True)
        )
    ]


def _mirror(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab.edit import mirror

    lines = args.get("lines")
    if (
        not isinstance(lines, list)
        or not lines
        or not all(isinstance(n, int) and not isinstance(n, bool) for n in lines)
    ):
        return _error("lines must be a list of line numbers, such as [12, 13].")
    plane = args.get("plane_x", 0)
    if not isinstance(plane, int | float) or isinstance(plane, bool) or not math.isfinite(plane):
        return _error("plane_x must be a number.")
    if len(lines) > 400:
        return _error("mirror at most 400 lines at a time.")
    from bricksnap.lab.joints import parse

    for j in parse(_model(folder))[0]:
        mine = sorted(set(lines) & set(j.fixed + j.moving))
        if mine:
            other = {"door-hinge-left": "door-hinge-right", "door-hinge-right": "door-hinge-left"}
            hint = (
                f" (the other hand of {j.module} is {other[j.module]})" if j.module in other else ""
            )
            return _error(
                f"line {mine[0]} is part of the joint '{j.name}'"
                + (f" (the module {j.module})" if j.module else "")
                + ": mirror copies parts, not joints, and would leave the copy unable to turn. "
                "Put the other side in with place_module" + hint + " (or joint, for parts you "
                "joined yourself), and mirror the rest."
            )
    results = mirror(_model(folder), lines, float(plane))
    new = [r.new_line for r in results if r.new_line]
    notes = [r.note for r in results]
    if not new:
        return [_text("Nothing was copied:\n" + "\n".join("- " + n for n in notes[:60]))]
    text, numbers = _append(folder, [*new, "0 STEP"])
    added = numbers[:-1]
    shown = notes if len(notes) <= 30 else notes[:30] + [f"... and {len(notes) - 30} more"]
    return [
        _text(
            f"Added {len(added)} mirrored parts as lines {added[0]} to {added[-1]}, then a "
            "0 STEP.\n"
            + "\n".join("- " + n for n in shown)
            + "\nWhat the checker says about them:\n"
            + _quick(folder, text, added, brief=True)
        )
    ]


def _playbook(folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
    from bricksnap.lab import guide

    kind, parts, table = args.get("kind"), args.get("parts"), args.get("table", False)
    if not isinstance(table, bool):
        return _error('table must be true or false, as in {"table": true}.')
    if table:
        if kind is not None or parts is not None:
            return _error('ask for the table on its own: {"table": true}.')
        return [_text("Parts by job (LDraw part numbers):\n\n" + guide.parts_table())]
    listing = "\n".join(f"- {k}: {line}" for k, line in guide.kinds().items())
    if kind is None and parts is None:
        return [
            _text(
                "The kinds of subject the playbooks cover (call playbook with one, and about "
                'how many parts, e.g. {"kind": "vehicle", "parts": 100}):\n' + listing
            )
        ]
    if not isinstance(kind, str) or not kind.strip():
        return _error(
            'say the kind of subject, e.g. {"kind": "creature", "parts": 100}. The kinds:\n'
            + listing
        )
    found = guide.kind_of(kind)
    if found is None:
        return _error(
            f"there is no playbook for '{kind[:40]}'. Choose the nearest of these kinds:\n"
            + listing
        )
    if parts is None:
        return _error(f'say about how many parts too, e.g. {{"kind": "{found}", "parts": 100}}.')
    if not isinstance(parts, int) or isinstance(parts, bool) or not 1 <= parts <= 100_000:
        return _error("parts must be a whole number of parts, such as 100.")
    title, body, why = guide.playbook(found, parts)
    named = "" if found == kind.strip().lower() else f"'{kind[:40]}' is read as {found}. "
    with contextlib.suppress(OSError):
        record = {"kind": found, "parts": parts, "playbook": title}
        (folder / "playbook.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
    return [_text(f"Playbook: {title}. {named}{why}\n\n{body}")]


_HANDLERS = {
    "search_parts": _search,
    "part_info": _part_info,
    "place": _place,
    "add": _add,
    "remove": _remove,
    "model": _model_tool,
    "check": _check,
    "look": _look,
    "submit": _submit,
    "reference": _reference,
    "remove_box": _remove_box,
    "fill": _fill,
    "mirror": _mirror,
    "modules": _modules,
    "place_module": _place_module,
    "joint": _joint,
    "playbook": _playbook,
}


def call_tool(folder: Path, name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    """Answer one tool call (see the contract). Never raises."""
    started = time.monotonic()
    allowed = {t["name"] for t in tools_for(folder)}
    if name not in allowed:
        blocks = _error(
            f"there is no tool '{name[:40]}' here. The tools are: {', '.join(sorted(allowed))}."
        )
    else:
        try:
            blocks = _HANDLERS[name](folder, dict(args or {}))
        except Exception as e:  # never a traceback to the model
            (folder / "errors.log").open("a", encoding="utf-8").write(traceback.format_exc() + "\n")
            blocks = _error(
                f"the tool failed inside ({type(e).__name__}: {str(e)[:200]}). Try again "
                "differently."
            )
    for b in blocks:
        if b.get("type") == "text":
            b["text"] = _scrub(str(b["text"]), folder)
    _log(folder, name, args, blocks, time.monotonic() - started)
    return blocks


def _log(folder: Path, name: str, args: Any, blocks: list[dict[str, Any]], seconds: float) -> None:
    short = {
        k: (v if not isinstance(v, str) or len(v) < 120 else v[:117] + "...")
        for k, v in dict(args or {}).items()
    }
    err = len(blocks) == 1 and str(blocks[0].get("text", "")).startswith("ERROR:")
    record = {
        "tool": name,
        "args": short,
        "error": err,
        "seconds": round(seconds, 2),
        "time": time.time(),
    }
    try:
        with (folder / "calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(_scrub(json.dumps(record), folder) + "\n")
    except OSError:
        pass
