"""Tests for the studio: its shapes (bricksnap/design.py), its pictures (bricksnap/render.py),
its tools and server (bricksnap/designer/studio_tools.py, studio_server.py), the passes
(bricksnap/designer/studio.py) and comparing versions with the judge (judge.judge_versions).

No test starts a real AI session: a pass is played by a fake that calls the real tools, and
one test runs the real session code against a fake ``claude`` executable.
"""

from __future__ import annotations

import base64
import copy
import io
import json
import os
import random
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import anyio
import numpy as np
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client
from PIL import Image
from test_design import _mutations, schema_valid

from bricksnap import versions
from bricksnap.design import (
    CLEAR_OP,
    OP_SCHEMA,
    OPS,
    apply_ops,
    cleared,
    replay,
    shape_mask,
    studio_op_schema,
    validate_op,
)
from bricksnap.designer import judge, studio
from bricksnap.designer.judge_server import Judging
from bricksnap.designer.runner import DesignerRun
from bricksnap.designer.studio_tools import (
    STUDIO_TOOL_NAMES,
    Session,
    call_tool,
    load_plan,
    outline_match,
    tool_definitions,
)
from bricksnap.pipeline import create_project, rebuild
from bricksnap.project import Project, ProjectError
from bricksnap.render import render_design, render_section, view_frame, zoom_box
from bricksnap.types import EMPTY, FINISH_SLOPED, Design

GREY, RED, BLUE = 71, 4, 1


def grid(shape=(10, 10, 12)) -> Design:
    return Design(colors=np.full(shape, EMPTY, dtype=np.int16))


def layer(mask: np.ndarray, axis: int, k: int) -> np.ndarray:
    index: list[Any] = [slice(None)] * 3
    index[axis] = k
    return mask[tuple(index)]


CYL = {"type": "cylinder", "axis": "z", "min": [0, 0, 0], "max": [5, 5, 2]}


# ---- shapes --------------------------------------------------------------------------------


def test_cylinder_fills_its_box_with_a_round_cross_section():
    m = shape_mask(CYL, (10, 10, 12), grid())
    assert m[:, :, 3:].sum() == 0 and m[6:].sum() == 0
    for k in range(3):  # 6 by 6: every cell but one in each corner
        sl = layer(m, 2, k)[:6, :6]
        assert sl.sum() == 32
        assert not sl[0, 0] and not sl[5, 5] and sl[0, 1] and sl[2, 0]
    # it touches the middle of every side of its box, and is symmetric
    sl = layer(m, 2, 0)[:6, :6]
    assert np.array_equal(sl, sl[::-1]) and np.array_equal(sl, sl.T)
    # one and two studs across are full; along x the cross-section is in y and z
    one = shape_mask({**CYL, "max": [0, 0, 2]}, (10, 10, 12), grid())
    assert one.sum() == 3
    two = shape_mask({**CYL, "max": [1, 1, 0]}, (10, 10, 12), grid())
    assert two.sum() == 4
    along_x = shape_mask(
        {"type": "cylinder", "axis": "x", "min": [2, 0, 0], "max": [4, 3, 9]}, (10, 10, 12), grid()
    )
    assert along_x[:2].sum() == 0 and along_x[5:].sum() == 0
    assert all(np.array_equal(layer(along_x, 0, 2), layer(along_x, 0, k)) for k in (3, 4))
    assert not along_x[2, 0, 0] and along_x[2, 0, 5] and along_x[2, 1, 0]


def test_cone_narrows_evenly_to_its_narrow_end():
    cone = {"type": "cone", "axis": "z", "min": [0, 0, 0], "max": [5, 5, 5], "narrow_end": "max"}
    m = shape_mask(cone, (10, 10, 12), grid())
    widths = [int(layer(m, 2, k).any(axis=1).sum()) for k in range(6)]
    assert widths == [6, 6, 4, 4, 2, 2]  # in steps of two, centred, ending two across
    down = shape_mask({**cone, "narrow_end": "min"}, (10, 10, 12), grid())
    assert np.array_equal(down[:, :, :6], m[:, :, 5::-1])
    odd = shape_mask({**cone, "max": [4, 4, 4]}, (10, 10, 12), grid())
    assert [int(layer(odd, 2, k).sum()) for k in range(5)][-1] == 1  # an odd width ends in one
    half = shape_mask({**cone, "narrow_size": 0.5}, (10, 10, 12), grid())
    assert int(layer(half, 2, 5).any(axis=1).sum()) == 4  # half of six, kept centred
    same = shape_mask({**cone, "narrow_size": 1}, (10, 10, 12), grid())
    assert np.array_equal(same, shape_mask({**CYL, "max": [5, 5, 5]}, (10, 10, 12), grid()))
    flat = shape_mask({**cone, "max": [5, 5, 0]}, (10, 10, 12), grid())
    assert flat.sum() == 32  # one layer long: the wide end


def test_studio_shapes_need_the_conversion(catalog):
    d = grid()
    (r,) = apply_ops(d, [{"op": "add", "shape": CYL, "color": RED}], catalog)
    assert not r.applied and 'Unknown shape type "cylinder"' in r.message
    assert '"box"' in r.message and "cone" not in r.message  # the first way's words, unchanged
    with pytest.raises(ValueError):
        validate_op({"op": "add", "shape": CYL, "color": RED}, catalog)
    validate_op({"op": "add", "shape": CYL, "color": RED}, catalog, studio=True)
    (r,) = apply_ops(d, [{"op": "add", "shape": CYL, "color": RED}], catalog, reference=grid())
    assert r.applied and r.cells_changed == 96
    assert "cylinder along z filling [0, 0, 0]..[5, 5, 2]" in r.message


@pytest.mark.parametrize(
    ("shape", "words"),
    [
        ({"type": "cylinder", "min": [0, 0, 0], "max": [1, 1, 1]}, ['missing "axis"', '"z"']),
        ({**CYL, "axis": "+z"}, ['Write it as "z"']),
        ({**CYL, "axis": "up"}, ['"axis" must be "x", "y" or "z"']),
        ({**CYL, "min": [0, 0, 0.5]}, ["whole cells", "Use 0 or 1"]),
        ({**CYL, "min": [6, 0, 0]}, ["min is greater than its max", '"min": [5, 0, 0]']),
        ({**CYL, "radius": 2}, ['unexpected field "radius"', '"axis"']),
        ({"type": "cone", "axis": "z", "min": [0, 0, 0], "max": [1, 1, 1]}, ['"narrow_end"']),
        ({**CYL, "type": "cone", "narrow_end": "top"}, ['"min" or "max"']),
        ({**CYL, "type": "cone", "narrow_end": "max", "narrow_size": 2}, ["from 0 to 1"]),
        ({"type": "seed", "min": [0, 0, 0]}, ['missing "max"', '"type": "seed"']),
        ({"type": "sead", "min": [0, 0, 0], "max": [1, 1, 1]}, ['Did you mean "seed"']),
    ],
)
def test_studio_shape_messages_say_what_to_fix(catalog, shape, words):
    (r,) = apply_ops(
        grid(), [{"op": "add", "shape": shape, "color": RED}], catalog, reference=grid()
    )
    assert not r.applied and r.message.startswith("Rejected:")
    for w in words:
        assert w in r.message, r.message


def test_mirror_of_a_cone_along_x_turns_it_round(catalog):
    d = grid((10, 6, 6))
    cone = {"type": "cone", "axis": "x", "min": [0, 0, 0], "max": [3, 3, 3], "narrow_end": "max"}
    (r,) = apply_ops(
        d,
        [{"op": "add", "shape": cone, "color": RED, "mirror": True}],
        catalog,
        reference=grid((10, 6, 6)),
    )
    assert r.applied and "narrow at its min end" in r.message
    assert np.array_equal(d.filled, d.filled[::-1])


@pytest.fixture
def conversion() -> Design:
    ref = grid()
    ref.colors[2:6, 2:6, 0:6] = GREY
    ref.colors[3:5, 2, 4:6] = RED  # a red face on the front
    assert ref.finish is not None
    ref.finish[2:6, 2:6, 5] = FINISH_SLOPED
    return ref


def test_seed_shape_copies_the_conversion(catalog, conversion):
    d = grid()
    d.colors[0, 0, 0] = BLUE
    box = {"type": "seed", "min": [0, 0, 3], "max": [9, 9, 11]}
    (r,) = apply_ops(d, [{"op": "add", "shape": box}], catalog, reference=conversion)
    assert r.applied and r.cells_changed == 48 and "the conversion's own colours" in r.message
    assert np.array_equal(d.colors[:, :, 3:], conversion.colors[:, :, 3:])
    assert d.finish is not None and (d.finish[2:6, 2:6, 5] == FINISH_SLOPED).all()
    (r,) = apply_ops(
        d, [{"op": "paint", "shape": box, "color": BLUE}], catalog, reference=conversion
    )
    assert r.applied and (d.colors[3:5, 2, 4:6] == BLUE).all()
    (r,) = apply_ops(d, [{"op": "paint", "shape": box}], catalog, reference=conversion)
    assert r.applied and (d.colors[3:5, 2, 4:6] == RED).all()  # back to the conversion's colours
    (r,) = apply_ops(
        d, [{"op": "remove", "shape": {**box, "max": [9, 9, 4]}}], catalog, reference=conversion
    )
    assert r.applied and r.cells_changed == 32 and d.colors[0, 0, 0] == BLUE
    (r,) = apply_ops(
        d,
        [
            {
                "op": "add",
                "shape": {"type": "seed", "min": [7, 7, 0], "max": [9, 9, 9]},
                "color": RED,
            }
        ],
        catalog,
        reference=conversion,
    )
    assert not r.applied and "no filled cells inside that box" in r.message


def test_seed_with_mirror_takes_the_conversions_own_cells(catalog, conversion):
    lopsided = conversion.copy()
    lopsided.colors[1, 3, 0] = BLUE  # only on the left
    d = grid()
    op = {
        "op": "add",
        "shape": {"type": "seed", "min": [0, 0, 0], "max": [4, 9, 0]},
        "mirror": True,
    }
    (r,) = apply_ops(d, [op], catalog, reference=lopsided)
    assert r.applied
    assert np.array_equal(d.colors[:, :, 0], lopsided.colors[:, :, 0])  # never EMPTY or flipped


def test_clear_and_replay(catalog, conversion):
    design = conversion.copy()
    apply_ops(
        design,
        [
            {
                "op": "paint",
                "shape": {"type": "box", "min": [0, 0, 0], "max": [9, 9, 0]},
                "color": BLUE,
            }
        ],
        catalog,
    )
    empty = cleared(design)
    assert not empty.filled.any() and empty.details == [] and empty.log[-1] == CLEAR_OP
    assert empty.skin is not None and np.array_equal(empty.skin, design.skin)
    ops = [
        {"op": "add", "shape": CYL, "color": RED},
        {"op": "add", "shape": {"type": "seed", "min": [0, 0, 3], "max": [9, 9, 9]}},
    ]
    assert all(r.applied for r in apply_ops(empty, ops, catalog, reference=conversion))
    again = replay(conversion, empty.log, catalog)
    assert again.fingerprint() == empty.fingerprint()
    with pytest.raises(ValueError):  # "clear" is the program's, never an edit
        validate_op(CLEAR_OP, catalog, studio=True)


def test_the_first_ways_schema_is_unchanged_and_the_studios_lists_only_its_ops():
    text = json.dumps(OP_SCHEMA)
    assert "cylinder" not in text and "seed" not in text
    outline = studio_op_schema(("add", "remove", "paint"))
    names = {v["properties"]["op"]["const"] for v in outline["anyOf"]}
    assert names == {"add", "remove", "paint"}
    assert "place_detail" not in json.dumps(outline)
    surface = studio_op_schema(("paint", "set_finish", "place_detail", "remove_detail"))
    paint = next(v for v in surface["anyOf"] if v["properties"]["op"]["const"] == "paint")
    assert "LDraw colour code" in json.dumps(paint)  # the first op with a colour describes it
    with pytest.raises(ValueError):
        studio_op_schema(("explode",))


STUDIO_VALID = [
    {"op": "add", "shape": CYL, "color": RED},
    {
        "op": "add",
        "shape": {
            "type": "cone",
            "axis": "y",
            "min": [0, 0, 0],
            "max": [3, 5, 2],
            "narrow_end": "min",
            "narrow_size": 0.5,
        },
        "color": GREY,
    },
    {"op": "add", "shape": {"type": "seed", "min": [0, 0, 0], "max": [9, 9, 9]}},
    {"op": "paint", "shape": {"type": "seed", "min": [0, 0, 0], "max": [9, 9, 9]}, "mirror": True},
    {"op": "remove", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}},
    {
        "op": "set_finish",
        "shape": {"type": "seed", "min": [0, 0, 0], "max": [9, 9, 9]},
        "finish": "sloped",
    },
]


def test_studio_schema_agrees_with_validation(catalog):
    rng = random.Random(7)
    disagreements = []
    accepted = 0
    for op in STUDIO_VALID:
        assert schema_valid(op, studio_op_schema())
        validate_op(op, catalog, studio=True)
    for _ in range(3000):
        op = _mutations(rng, copy.deepcopy(rng.choice(STUDIO_VALID)))
        try:
            validate_op(op, catalog, studio=True)
            ok, message = True, ""
        except ValueError as err:
            ok, message = False, str(err)
        accepted += ok
        in_schema = schema_valid(op, studio_op_schema())
        if ok and not in_schema:
            disagreements.append(("validation accepts, schema rejects", op))
        # the schema cannot say min <= max or narrow_size <= 1
        if in_schema and not ok and not re.search(r"greater than its max|from 0 to 1", message):
            disagreements.append(("schema accepts, validation rejects", op, message))
    assert not disagreements, disagreements[:3]
    assert accepted > 100


# ---- pictures ------------------------------------------------------------------------------


def hollow_box() -> Design:
    d = grid((8, 8, 9))
    d.colors[1:7, 1:7, 0:9] = RED
    d.colors[2:6, 2:6, 3:6] = EMPTY  # a sealed room with a floor three plates thick
    return d


def test_section_shows_the_cut_face_and_shades_what_lies_beyond(catalog):
    d = hollow_box()
    picture = np.asarray(render_section(d, catalog, "y", 3, labels=False))
    frame = view_frame(d.shape, "front", labels=False)
    wall = frame.cell_center(1, 3, 4)  # the cut through the left wall
    room = frame.cell_center(3, 3, 4)  # inside the room: the back wall, beyond the cut
    c_wall = picture[int(wall[1]), int(wall[0])].astype(int)
    c_room = picture[int(room[1]), int(room[0])].astype(int)
    assert c_wall.sum() > c_room.sum() * 1.5
    whole = np.asarray(render_design(d, catalog, "front", labels=False))
    assert not np.array_equal(whole, picture)  # the outside face is gone
    top = np.asarray(render_section(d, catalog, "z", 4, labels=False))
    assert top.shape == np.asarray(render_design(d, catalog, "top", labels=False)).shape
    with pytest.raises(ValueError):
        render_section(d, catalog, "w", 1)
    with pytest.raises(ValueError):
        render_section(d, catalog, "x", 8)


def test_zoom_keeps_the_numbered_margins(catalog):
    d = hollow_box()
    frame = view_frame(d.shape, "front", px_per_stud=32)
    full = render_design(d, catalog, "front", px_per_stud=32)
    crop = zoom_box(full, frame, (1, 0, 0), (2, 7, 2))
    assert crop.width < full.width and crop.height < full.height
    assert crop.width >= frame.left + 2 * 32  # the left margin and two studs
    assert np.array_equal(
        np.asarray(crop)[:, : frame.left][-5:], np.asarray(full)[-5:, : frame.left]
    )


# ---- the tools -----------------------------------------------------------------------------

BRIEF = {
    "object": "A chess pawn, standing upright.",
    "features": ["a round head", "a wide base"],
    "plan": "A clean base and a round head.",
    "colours": [GREY, RED],
    "finish": "Studs everywhere.",
}
PLAN = {
    "scale": "Keep the conversion's size.",
    "regions": [
        {
            "name": "base",
            "min": [1, 1, 0],
            "max": [7, 7, 2],
            "make": "cylinder",
            "colour": GREY,
            "finish": "studs",
        },
        {
            "name": "head",
            "min": [2, 2, 9],
            "max": [6, 6, 14],
            "make": "seed",
            "colour": RED,
            "finish": "studs",
            "note": "Copied.",
        },
    ],
    "interior": None,
}


@pytest.fixture(scope="module")
def _pawn(tmp_path_factory, pawn_path: Path, catalog) -> Path:
    root = tmp_path_factory.mktemp("studio")
    project = create_project(pawn_path, studs=6, directory=root, catalog=catalog)
    rebuild(project, catalog=catalog)
    return project.path


@pytest.fixture
def pawn(_pawn: Path, tmp_path: Path) -> Project:
    dest = tmp_path / "pawn"
    shutil.copytree(_pawn, dest)
    return Project(dest)


def texts(blocks: list[dict]) -> str:
    return "\n".join(b.get("text", "") for b in blocks if b["type"] == "text")


def test_tool_definitions_follow_the_pass():
    defs = tool_definitions(("render", "measure", "critique"))
    assert [d["name"] for d in defs] == ["render", "measure", "critique"]
    full = {d["name"]: d for d in tool_definitions()}
    assert tuple(full) == STUDIO_TOOL_NAMES
    outline = tool_definitions(("apply_ops",), ("add", "remove", "paint"))[0]
    text = json.dumps(outline)
    assert "place_detail" not in text and "set_finish" not in text and "cylinder" in text
    with pytest.raises(ValueError):
        tool_definitions(("explode",))


def test_a_pass_cannot_use_what_it_was_not_given(pawn: Project):
    critic = Session(pawn.path, ("render", "measure", "critique"), ())
    out = texts(critic.call("apply_ops", {"ops": []}))
    assert out.startswith("ERROR: there is no tool called") and "render, measure, critique" in out
    pawn.meta["brief"] = BRIEF
    pawn.save_meta()
    outline = Session(pawn.path, ("apply_ops",), ("add", "remove", "paint"))
    before = pawn.load_design().fingerprint()
    ops = [
        {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [8, 8, 0]}, "color": RED},
        {"op": "place_detail", "part": "98138", "color": 0, "at": [4, 4, 13]},
    ]
    out = texts(outline.call("apply_ops", {"ops": ops}))
    assert (
        out.startswith("ERROR: this pass may not use place_detail") and "Nothing was applied" in out
    )
    assert pawn.load_design().fingerprint() == before
    out = texts(outline.call("apply_ops", {"ops": [CLEAR_OP]}))
    assert out.startswith("ERROR: this pass may not use clear")


def test_plan_is_checked_saved_and_described(pawn: Project):
    s = Session(pawn.path, ("describe", "plan"), ())
    bad = {
        "scale": "",
        "regions": [
            {
                "name": "head",
                "min": [0, 0, 0],
                "max": [99, 1, 1],
                "make": "blob",
                "colour": 9999,
                "finish": "shiny",
            },
            {
                "name": "Head",
                "min": [3, 0, 0],
                "max": [1, 1, 1],
                "make": "box",
                "colour": RED,
                "finish": "studs",
                "extra": 1,
            },
        ],
        "interior": {
            "name": "room",
            "min": [1, 1, 0],
            "max": [2, 2, 2],
            "wall": 0,
            "openings": "a door",
            "contents": "a chair",
        },
    }
    out = texts(s.call("plan", bad))
    assert out.startswith("ERROR: the plan was not saved")
    for words in (
        '"scale" is empty',
        "outside the grid",
        '"make" must be one of',
        '"colour"',
        '"finish" must be one of',
        "already has this name",
        "min is greater than max",
        '"extra"',
        "needs a floor",
        '"wall"',
    ):
        assert words in out, words
    assert load_plan(pawn) is None
    out = texts(s.call("plan", PLAN))
    assert out.startswith("Plan saved.") and "base: " in out
    assert re.search(r"head: \d+ cells", out)
    assert load_plan(pawn) == PLAN  # saved exactly as sent
    described = texts(s.call("describe", {}))
    assert (
        "PLAN (" in described
        and "base: x 1 to 7, y 1 to 7, z 0 to 2; made as cylinder" in described
    )
    assert "Interior: none planned." in described
    assert "THE CONVERSION" in described and "Layer by layer:" in described
    assert described.index("BRIEF") < described.index("PLAN (") < described.index("BUILD")


def test_measure_reports_differences_by_region(pawn: Project, catalog):
    write_plan(pawn)
    design = pawn.load_design()
    apply_ops(
        design,
        [
            {
                "op": "add",
                "shape": {"type": "box", "min": [0, 0, 15], "max": [1, 1, 17]},
                "color": RED,
            },
            {"op": "remove", "shape": {"type": "box", "min": [0, 0, 0], "max": [8, 8, 0]}},
        ],
        catalog,
    )
    pawn.save_design(design)
    out = texts(call_tool(pawn.path, "measure", {}))
    assert "Outline match with the conversion" in out and "front " in out
    assert "12 cells at x 0 to 1, y 0 to 1, z 15 to 17 (outside every planned region)" in out
    assert re.search(r"cells at x \d+ to \d+, y \d+ to \d+, z 0 \(in region \"base\"\)", out)
    assert "base (x 1 to 7, y 1 to 7, z 0 to 2): design" in out
    m = outline_match(design.filled, pawn.load_design(base=True).filled)
    assert set(m) == {"front", "right", "top"} and all(0 <= v < 100 for v in m.values())


def test_measure_names_a_sealed_hollow(catalog, pawn: Project):
    design = pawn.load_design()
    base = pawn.load_design(base=True)
    filled_box = {"type": "box", "min": [1, 1, 0], "max": [7, 7, 8]}
    apply_ops(design, [{"op": "add", "shape": filled_box, "color": GREY}], catalog)
    apply_ops(
        design,
        [{"op": "remove", "shape": {"type": "box", "min": [3, 3, 3], "max": [5, 5, 5]}}],
        catalog,
    )
    pawn.save_design(design)
    hidden = base.filled[3:6, 3:6, 3:6].sum()
    out = texts(call_tool(pawn.path, "measure", {}))
    if hidden >= 3:
        assert "a hollow sealed inside the design" in out


def write_plan(project: Project) -> None:
    project.meta["brief"] = BRIEF
    project.save_meta()
    assert texts(call_tool(project.path, "plan", PLAN)).startswith("Plan saved.")


def decode(blocks: list[dict]) -> Image.Image:
    (image,) = [b for b in blocks if b["type"] == "image"]
    return Image.open(io.BytesIO(base64.b64decode(image["data"])))


def test_render_rows_section_and_zoom(pawn: Project):
    write_plan(pawn)
    s = Session(pawn.path, ("render", "critique"), ())
    normal = s.call("render", {"views": ["front"]})
    assert "Top row: the seed" in texts(normal) and "Bottom row: the current build" in texts(normal)
    three = s.call("render", {"views": ["front"], "conversion": True})
    assert "Middle row: the conversion" in texts(three)
    assert decode(three).height > decode(normal).height
    cut = s.call("render", {"section": {"axis": "z", "at": 4}})
    assert "cut-through at z = 4, seen from the top" in texts(cut)
    assert "Left: the current build. Right: the conversion" in texts(cut)
    zoom = s.call("render", {"zoom": {"region": "HEAD"}, "views": ["front", "iso"]})
    assert "cut down to x 2 to 6, y 2 to 6, z 9 to 14" in texts(zoom)
    for args, words in (
        ({"zoom": {"region": "tail"}}, "The regions are: base, head"),
        ({"zoom": {"min": [0, 0, 0], "max": [99, 0, 0]}}, "outside the grid"),
        ({"section": {"axis": "y", "at": 40}}, "from 0 to 8"),
        ({"section": {"axis": "x", "at": 1}, "zoom": {"region": "head"}}, "not both"),
        ({"views": ["front", "front"]}, "same view twice"),
        ({"colour": True}, 'Its optional arguments are "views"'),
    ):
        out = texts(s.call("render", args))
        assert out.startswith("ERROR:") and words in out, (args, out)
    assert str(pawn.path) not in json.dumps([texts(b) for b in (normal, cut, zoom)])


def test_an_empty_design_shows_the_conversion_and_cannot_be_built(pawn: Project):
    studio._start_empty(pawn)
    s = Session(pawn.path, ("describe", "render", "rebuild", "measure"), ())
    assert "The design itself is EMPTY" in texts(s.call("describe", {}))
    assert "There is no build yet: the design is empty." in texts(s.call("describe", {}))
    out = s.call("render", {"views": ["front"]})
    assert "Bottom row: the conversion" in texts(out) and "no build row yet" in texts(out)
    assert texts(s.call("rebuild", {})).startswith("ERROR: the design is empty")
    assert "nothing to compare yet" in texts(s.call("measure", {}))
    assert not pawn.has_build()


def test_critique_needs_a_look_and_a_well_formed_report(pawn: Project):
    s = Session(pawn.path, ("render", "critique"), ())
    good = {"verdict": "good", "summary": "Fine."}
    assert texts(s.call("critique", good)).startswith("ERROR: look first")
    s.call("render", {"views": ["front"]})
    problem = {
        "where": "head",
        "min": [2, 2, 9],
        "max": [6, 6, 14],
        "problem": "Too small.",
        "change": "Make it two studs wider.",
    }
    for args, words in (
        ({"verdict": "good", "summary": "x", "problems": [problem]}, "takes no problems"),
        ({"verdict": "problems", "summary": "x"}, "lists 1 to 5 problems"),
        ({"verdict": "problems", "summary": "x", "problems": [problem] * 6}, "(it has 6)"),
        ({"verdict": "meh", "summary": ""}, '"verdict" must be'),
        (
            {"verdict": "problems", "summary": "x", "problems": [{**problem, "max": [1, 1, 1]}]},
            "min is greater than max",
        ),
    ):
        out = texts(s.call("critique", args))
        assert out.startswith("ERROR: the report was not recorded") and words in out, out
    out = texts(
        s.call("critique", {"verdict": "problems", "summary": "One.", "problems": [problem]})
    )
    assert out.startswith("Report recorded.") and "1. head (x 2 to 6, y 2 to 6, z 9 to 14)" in out
    saved = json.loads((pawn.path / "studio" / "critique.json").read_text())
    assert saved["problems"][0]["change"] == "Make it two studs wider."


def test_rebuild_reports_the_outline_match(pawn: Project):
    out = texts(call_tool(pawn.path, "rebuild", {}))
    assert out.startswith("Rebuilt:") and "Outline match with the conversion" in out
    assert "front 100%, right 100%, top 100%" in out


# ---- the tool server -----------------------------------------------------------------------


def test_the_server_offers_exactly_the_pass_tools(pawn: Project):
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "bricksnap.designer.studio_server",
            str(pawn.path),
            "--tools",
            "render,measure,critique",
            "--ops",
            "",
        ],
    )

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            critique_first = await session.call_tool(
                "critique", {"verdict": "good", "summary": "x"}
            )
            barred = await session.call_tool("apply_ops", {"ops": []})
            await session.call_tool("render", {"views": ["front"]})
            critique = await session.call_tool("critique", {"verdict": "good", "summary": "Fine."})
            return listed.tools, critique_first, barred, critique

    tools, first, barred, critique = anyio.run(go)
    assert [t.name for t in tools] == ["render", "measure", "critique"]
    assert first.is_error and barred.is_error and not critique.is_error
    assert "no tool called" in barred.content[0].text


# ---- the passes ----------------------------------------------------------------------------


class FakePasses:
    """Plays each pass through the real tools, as the AI would. ``script[name]`` is a list of
    (tool, args), or ("fail", that list) for a session that makes the calls and then fails."""

    def __init__(self, script: dict[str, Any]) -> None:
        self.script = script
        self.calls: list[tuple[str, str]] = []

    def __call__(self, project, pass_, message, *, model, effort, on_event=None):
        self.calls.append((pass_.name, message))
        plan = self.script.get(pass_.name, [])
        fail = isinstance(plan, tuple)  # ("fail", calls): make the calls, then fail
        s = Session(project.path, pass_.tools, pass_.ops or OPS)
        for tool, args in plan[1] if fail else plan:
            out = texts(s.call(tool, args))
            assert not out.startswith("ERROR"), (pass_.name, tool, out)
        if fail:
            return DesignerRun(
                ok=False, error="The pass used all its turns (40) before it finished."
            )
        if on_event:
            on_event({"type": "result", "subtype": "success"})
        return DesignerRun(ok=True, turns=len(plan), final_text=f"{pass_.name} done.")


SEED_ALL = {"type": "seed", "min": [0, 0, 0], "max": [8, 8, 20]}
GOOD_SCRIPT: dict[str, Any] = {
    "plan": [("describe", {}), ("render", {}), ("brief", BRIEF), ("plan", PLAN)],
    "outline": [
        ("apply_ops", {"ops": [{"op": "add", "shape": SEED_ALL, "color": GREY}]}),
        ("rebuild", {}),
        ("measure", {}),
    ],
    "refine": [
        (
            "apply_ops",
            {"ops": [{"op": "paint", "shape": {**SEED_ALL, "min": [0, 0, 9]}, "color": RED}]},
        )
    ],
    "surface": [
        ("apply_ops", {"ops": [{"op": "set_finish", "shape": SEED_ALL, "finish": "smooth"}]}),
        ("rebuild", {}),
    ],
    "critic": [
        ("render", {}),
        ("measure", {}),
        (
            "critique",
            {
                "verdict": "problems",
                "summary": "Base too plain.",
                "problems": [
                    {
                        "where": "base",
                        "min": [1, 1, 0],
                        "max": [7, 7, 2],
                        "problem": "Plain grey.",
                        "change": "Paint the bottom plate red.",
                    }
                ],
            },
        ),
    ],
    "fix": [
        (
            "apply_ops",
            {"ops": [{"op": "paint", "shape": {**SEED_ALL, "max": [8, 8, 0]}, "color": RED}]},
        )
    ],
}


def test_a_whole_studio_run_keeps_every_pass_as_a_version(pawn: Project, monkeypatch):
    fake = FakePasses(GOOD_SCRIPT)
    monkeypatch.setattr(studio, "run_pass", fake)
    events: list[dict] = []
    result = studio.run_studio(pawn, on_event=events.append, wish="Make it red.")
    assert result.ok, result.error
    assert [c[0] for c in fake.calls] == ["plan", "outline", "refine", "surface", "critic", "fix"]
    assert "Make it red." in fake.calls[0][1]
    assert "1. base (x 1 to 7, y 1 to 7, z 0 to 2): Plain grey." in fake.calls[5][1]
    assert result.sessions == 6 and result.start_version == 1
    kept = versions.versions(pawn)
    assert [v.kind for v in kept] == ["converted", "pass", "pass", "pass", "pass"]
    assert [v.label for v in kept][1:] == [
        studio.OUTLINE.label,
        studio.REFINE.label,
        studio.SURFACE.label,
        studio.FIX.label,
    ]
    assert all(v.valid for v in kept) and result.version == kept[-1].n == versions.current(pawn)
    assert [r.version for r in result.passes] == [None, 2, 3, 4, None, 5]
    assert all(r.ok and not r.skipped for r in result.passes)
    started = [e for e in events if e.get("event") == "pass_started"]
    assert [e["words"] for e in started][:2] == [
        "Pass 1 of 6: studying the model and planning it",
        "Pass 2 of 6: laying out the main shapes",
    ]
    assert sum(e.get("type") == "result" for e in events) == 6  # the sessions' own events
    assert events[-1] == {"event": "studio_done", "ok": True, "version": 5, "sessions": 6}
    assert (pawn.path / "studio" / "critique-1.json").is_file()
    record = json.loads((pawn.path / "studio" / "run.json").read_text())
    assert record["status"] == "done" and len(record["passes"]) == 6
    design = pawn.load_design()
    assert design.log.count(CLEAR_OP) == 1
    assert replay(pawn.load_design(base=True), design.log, load_catalog_()).fingerprint() == (
        design.fingerprint()
    )
    assert pawn.build_is_current() and (pawn.path / "renders" / "compare.png").is_file()


def load_catalog_():
    from bricksnap.catalog import load_catalog

    return load_catalog()


def test_a_good_verdict_skips_the_fix(pawn: Project, monkeypatch):
    script = dict(GOOD_SCRIPT)
    script["critic"] = [("render", {}), ("critique", {"verdict": "good", "summary": "Fine."})]
    fake = FakePasses(script)
    monkeypatch.setattr(studio, "run_pass", fake)
    events: list[dict] = []
    result = studio.run_studio(pawn, passes=["plan", "outline"], rounds=2, on_event=events.append)
    assert result.ok and result.sessions == 3
    assert [c[0] for c in fake.calls] == ["plan", "outline", "critic"]
    assert [(r.name, r.skipped) for r in result.passes][3:] == [
        ("fix", True),
        ("critic", True),
        ("fix", True),
    ]
    assert sum(e.get("skipped") is True for e in events) == 3


def test_a_failed_pass_puts_back_the_last_version_that_held(pawn: Project, monkeypatch):
    script = dict(GOOD_SCRIPT)
    script["refine"] = ("fail", GOOD_SCRIPT["refine"])
    monkeypatch.setattr(studio, "run_pass", FakePasses(script))
    events: list[dict] = []
    result = studio.run_studio(pawn, on_event=events.append)
    assert not result.ok and result.restored == 2
    assert "The refine pass did not succeed: The pass used all its turns" in result.error
    assert "put back to version 2" in result.error
    assert [r.name for r in result.passes] == ["plan", "outline", "refine"]
    kept = versions.versions(pawn)
    assert kept[-1].label == studio.REFINE.label + " (stopped part way)"  # what it made is kept
    assert versions.current(pawn) == 2 and pawn.build_is_current()
    assert any(e.get("event") == "restored" and e["version"] == 2 for e in events)


def test_a_failed_pass_that_changed_nothing_puts_back_the_version_before_it(
    pawn: Project, monkeypatch
):
    script = dict(GOOD_SCRIPT)
    script["refine"] = ("fail", [])
    monkeypatch.setattr(studio, "run_pass", FakePasses(script))
    result = studio.run_studio(pawn)
    assert not result.ok and result.restored == 2 and result.passes[-1].version is None
    assert len(versions.versions(pawn)) == 2


def test_a_build_that_does_not_hold_stops_the_studio(pawn: Project, monkeypatch):
    script = dict(GOOD_SCRIPT)
    script["outline"] = [
        (
            "apply_ops",
            {
                "ops": [
                    {
                        "op": "add",
                        "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 2]},
                        "color": RED,
                    },
                    {
                        "op": "add",
                        "shape": {"type": "box", "min": [8, 8, 0], "max": [8, 8, 2]},
                        "color": RED,
                    },
                ]
            },
        )
    ]
    monkeypatch.setattr(studio, "run_pass", FakePasses(script))
    result = studio.run_studio(pawn)
    assert not result.ok and "does not hold together" in result.error
    assert result.restored == 1 and versions.current(pawn) == 1
    assert pawn.meta.get("brief") is None  # version 1 had no brief


def test_a_plan_pass_must_leave_a_plan(pawn: Project, monkeypatch):
    script = dict(GOOD_SCRIPT)
    script["plan"] = [("brief", BRIEF)]
    monkeypatch.setattr(studio, "run_pass", FakePasses(script))
    result = studio.run_studio(pawn)
    assert not result.ok and "without recording both the brief and the plan" in result.error
    assert result.restored == 1 and pawn.load_design().filled.any()


def test_the_list_of_passes_is_checked_first(pawn: Project):
    for passes, rounds, words in (
        (["plan", "dance"], 0, "no pass called"),
        (["plan", "fix"], 0, "needs a critic"),
        (["plan"], 9, "0 to 3 rounds"),
        (["outline"], 0, "must start with the plan pass"),
        ([], 0, "no passes"),
    ):
        with pytest.raises(ValueError, match=words):
            studio.run_studio(pawn, passes=passes, rounds=rounds)
    assert versions.versions(pawn) == []


def test_each_prompt_names_only_tools_its_pass_has():
    common = (studio.PROMPTS_DIR / "common.md").read_text()
    for p in studio.PASSES.values():
        text = studio.prompt_text(p)
        assert text.endswith(common.rstrip() + "\n") and len(text) > len(common) + 500
        own = (studio.PROMPTS_DIR / f"{p.name}.md").read_text()
        named = set(re.findall(r"`([a-z_]+)`", own)) & set(STUDIO_TOOL_NAMES)
        assert named <= set(p.tools), (p.name, named - set(p.tools))


FAKE_CLAUDE = r"""#!{python}
import json, os, sys
argv = sys.argv[1:]
record = {{"argv": argv, "stdin": sys.stdin.read(),
          "mcp": json.load(open(argv[argv.index("--mcp-config") + 1])),
          "prompt": open(argv[argv.index("--system-prompt-file") + 1]).read()}}
json.dump(record, open(os.environ["FAKE_RECORD"], "w"))
print(json.dumps({{"type": "system", "subtype": "init", "tools": [], "apiKeySource": "none",
                  "mcp_servers": [{{"name": "bricksnap", "status": "connected"}}],
                  "model": "claude-x"}}))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
                  "result": "Outline laid out."}}))
"""


def test_run_pass_uses_the_clean_room_runner(pawn: Project, tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(FAKE_CLAUDE.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_RECORD", str(record))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-invented")
    run = studio.run_pass(pawn, studio.OUTLINE, "Lay it out.", model="claude-x", effort="low")
    assert run.ok and run.turns == 3 and run.kind == "outline"
    seen = json.loads(record.read_text())
    argv = seen["argv"]
    assert argv[argv.index("--max-turns") + 1] == str(studio.OUTLINE.max_turns)
    assert argv[argv.index("--allowedTools") + 1] == "mcp__bricksnap"
    assert "--strict-mcp-config" in argv and argv[argv.index("--model") + 1] == "claude-x"
    assert seen["stdin"] == "Lay it out."
    server = seen["mcp"]["mcpServers"]["bricksnap"]
    assert server["args"][:3] == [
        "-m",
        "bricksnap.designer.studio_server",
        str(pawn.path.resolve()),
    ]
    assert server["args"][3:] == [
        "--tools",
        ",".join(studio.OUTLINE.tools),
        "--ops",
        "add,remove,paint",
    ]
    assert seen["prompt"] == studio.prompt_text(studio.OUTLINE)
    assert run.transcript is not None and run.transcript.parent == pawn.path / "designer"
    assert run.transcript.name.endswith("-outline.jsonl")


# ---- judging versions ----------------------------------------------------------------------


class FakeJudge:
    def __init__(self, prefer_last: bool = True, ok: bool = True) -> None:
        self.prefer_last, self.ok, self.letters = prefer_last, ok, []

    def __call__(self, folder: Path, letters: list[str], **options) -> DesignerRun:
        self.letters = list(letters)
        if not self.ok:
            return DesignerRun(ok=False, error="The judge did not finish.")
        tools = Judging(folder)
        assert not texts(tools.call("look", {"candidate": "all"})).startswith("ERROR")
        for x in letters:
            assert not texts(tools.call("look", {"candidate": x})).startswith("ERROR")
        order = sorted(letters, reverse=self.prefer_last)
        reply = tools.call(
            "choose",
            {"ranking": order, "reasons": {x: f"Why {x}." for x in order}, "summary": "Clear."},
        )
        assert not texts(reply).startswith("ERROR"), texts(reply)
        return DesignerRun(ok=True)


def two_versions(project: Project, catalog) -> list[int]:
    first = versions.record(project, "converted", "The conversion")
    design = project.load_design()
    apply_ops(
        design,
        [
            {
                "op": "paint",
                "shape": {"type": "box", "min": [0, 0, 0], "max": [8, 8, 2]},
                "color": RED,
            }
        ],
        catalog,
    )
    project.save_design(design)
    rebuild(project, catalog=catalog)
    return [first, versions.record(project, "pass", "Painted")]


def test_judge_versions_shows_them_blind_and_maps_the_ranking_back(
    pawn: Project, catalog, monkeypatch
):
    numbers = two_versions(pawn, catalog)
    fake = FakeJudge()
    monkeypatch.setattr(judge, "run_judge", fake)
    before = pawn.load_design().fingerprint()
    verdict = judge.judge_versions(pawn, numbers)
    assert not verdict.by_measurement and verdict.error == ""
    assert sorted(verdict.letters) == fake.letters == ["A", "B"]
    best = verdict.letters[max(fake.letters)]
    assert verdict.ranking[0] == best and set(verdict.ranking) == set(numbers)
    assert verdict.reasons[best] == f"Why {max(fake.letters)}."
    assert verdict.folder is not None
    setup = json.loads((verdict.folder / "judging" / "judging.json").read_text())
    assert "version" not in json.dumps(setup).lower() and "Painted" not in json.dumps(setup)
    result = json.loads((verdict.folder / "result.json").read_text())
    assert [c["version"] for c in result["candidates"]] == numbers
    assert pawn.load_design().fingerprint() == before and versions.current(pawn) == numbers[1]
    again = judge.judge_versions(pawn, numbers)  # the same deal of letters every time
    assert again.letters == verdict.letters


def test_judge_versions_falls_back_to_measurement(pawn: Project, catalog, monkeypatch):
    numbers = two_versions(pawn, catalog)
    monkeypatch.setattr(judge, "run_judge", FakeJudge(ok=False))
    verdict = judge.judge_versions(pawn, numbers)
    assert verdict.by_measurement and "The judge did not finish" in verdict.error
    assert set(verdict.ranking) == set(numbers) and all(
        "outline" in r for r in verdict.reasons.values()
    )
    with pytest.raises(ValueError):
        judge.judge_versions(pawn, [numbers[0]])
    with pytest.raises(ValueError):
        judge.judge_versions(pawn, [numbers[0], numbers[0]])
    with pytest.raises(ProjectError):
        judge.judge_versions(pawn, [numbers[0], 99])


def test_the_command_line_runs_and_judges(pawn: Project, monkeypatch, capsys):
    monkeypatch.setattr(studio, "run_pass", FakePasses(GOOD_SCRIPT))
    with pytest.raises(SystemExit) as stop:
        studio.main([str(pawn.path), "--passes", "plan,outline", "--rounds", "0"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    assert "== Pass 2 of 2: laying out the main shapes" in out and "kept as version 2" in out
    monkeypatch.setattr(judge, "run_judge", FakeJudge())
    studio.main([str(pawn.path), "--judge", "1", "2"])
    assert "ranking (best first): version" in capsys.readouterr().out
