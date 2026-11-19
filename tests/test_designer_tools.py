"""Tests for the designer's five tools (bricksnap/designer/tools.py)."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from bricksnap import design as design_module
from bricksnap.design import OP_SCHEMA
from bricksnap.designer import tools
from bricksnap.designer.tools import TOOLS, call_tool
from bricksnap.pipeline import create_project, rebuild
from bricksnap.project import Project
from bricksnap.types import FINISH_SLOPED, FINISH_SMOOTH, Detail

NOT_A_DICT: Any = ["x"]
NONE: Any = None

BRIEF = {
    "object": "A chess pawn, standing upright; it looks the same from every side.",
    "features": ["a round head", "a wide flared base"],
    "plan": "Keep the head round and make the neck a stud narrower so the head reads.",
    "colours": [71, 0],
    "finish": "Smooth on the head so it looks polished; studs elsewhere.",
}


ONE_ADD = {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]}, "color": 4}

_DEFAULT: Any = object()


def with_brief(path: Path, brief: Any = _DEFAULT) -> Path:
    project = Project(path)
    project.meta["brief"] = dict(BRIEF) if brief is _DEFAULT else brief
    project.save_meta()
    return path


@pytest.fixture(scope="module")
def _base_project(tmp_path_factory, pawn_path: Path, catalog) -> Path:
    root = tmp_path_factory.mktemp("designer-tools")
    project = create_project(pawn_path, studs=8, directory=root, catalog=catalog)
    rebuild(project, catalog=catalog)
    return project.path


@pytest.fixture
def bare_path(_base_project: Path, tmp_path: Path) -> Path:
    """A built project with no brief."""
    dest = tmp_path / "pawn"
    shutil.copytree(_base_project, dest)
    return dest


@pytest.fixture
def project_path(bare_path: Path) -> Path:
    """A built project with a brief, so apply_ops runs."""
    return with_brief(bare_path)


@pytest.fixture
def unbuilt_path(tmp_path: Path, pawn_path: Path, catalog) -> Path:
    return create_project(pawn_path, studs=6, directory=tmp_path, catalog=catalog).path


def text_of(blocks: list[dict]) -> str:
    return "\n".join(b["text"] for b in blocks if b["type"] == "text")


def assert_error(blocks: list[dict], *fragments: str) -> None:
    assert len(blocks) == 1 and blocks[0]["type"] == "text", blocks
    text = blocks[0]["text"]
    assert text.startswith("ERROR:"), text
    for f in fragments:
        assert f in text, (f, text)


# ---- the tool definitions -------------------------------------------------------------------


def test_exactly_five_tools_in_order():
    assert [t["name"] for t in TOOLS] == ["describe", "render", "brief", "apply_ops", "rebuild"]
    assert tools.TOOL_NAMES == ("describe", "render", "brief", "apply_ops", "rebuild")
    for t in TOOLS:
        assert set(t) == {"name", "description", "input_schema"}
        assert t["input_schema"]["type"] == "object"
        assert len(t["description"]) > 80


def test_brief_schema_matches_the_contract(catalog):
    schema = next(t for t in TOOLS if t["name"] == "brief")["input_schema"]
    assert list(schema["properties"]) == ["object", "features", "plan", "colours", "finish"]
    assert schema["required"] == ["object", "features", "plan", "colours", "finish"]
    assert schema["additionalProperties"] is False
    feats = schema["properties"]["features"]
    assert (feats["minItems"], feats["maxItems"]) == (2, 4)
    colours = schema["properties"]["colours"]
    assert (colours["minItems"], colours["maxItems"]) == (1, 6)
    assert colours["items"]["enum"] == sorted(catalog.colours)


def test_apply_ops_description_teaches_the_stage_2_operations():
    d = next(t for t in TOOLS if t["name"] == "apply_ops")["description"]
    for fragment in (
        '"op": "set_finish"',
        '"op": "place_detail"',
        '"op": "remove_detail"',
        '"mirror": true',
        '"smooth"',
        '"sloped"',
        "EMPTY cells directly above filled ones",
        "lowest corner cell",
        "nothing above",
        "never place them, except as details",
        "brief",
    ):
        assert fragment in d, fragment
    # every example operation in the description is valid JSON and passes the schema's shape
    examples = []
    start = d.find('{"op"')
    while start != -1:
        depth, end = 0, start
        while True:
            depth += {"{": 1, "}": -1}.get(d[end], 0)
            if depth == 0:
                break
            end += 1
        examples.append(json.loads(d[start : end + 1]))
        start = d.find('{"op"', end)
    ops = {e["op"] for e in examples}
    assert {"add", "set_finish", "place_detail", "remove_detail", "paint"} <= ops
    assert any(e.get("mirror") is True for e in examples)
    from bricksnap.catalog import load_catalog

    cat = load_catalog()
    for e in examples:  # each example is an operation the design module accepts
        design_module.validate_op(e, cat)
    # the example detail part really is a detail part made in black
    assert "98138" in {p.id for p in cat.detail_parts()} and cat.exists("98138", 0)


def test_describe_and_rebuild_descriptions_mention_the_new_parts():
    describe = next(t for t in TOOLS if t["name"] == "describe")["description"]
    assert "brief" in describe and "detail part" in describe and "smooth" in describe
    rebuild_d = next(t for t in TOOLS if t["name"] == "rebuild")["description"]
    assert "by itself" in rebuild_d


def test_descriptions_state_the_coordinate_conventions():
    for name in ("describe", "render", "apply_ops"):
        d = next(t for t in TOOLS if t["name"] == name)["description"]
        assert "studs" in d and "PLATES" in d.upper()
        assert "y = 0" in d and "z = 0" in d and "3 plates" in d


def test_apply_ops_schema_embeds_op_schema():
    schema = next(t for t in TOOLS if t["name"] == "apply_ops")["input_schema"]
    assert schema["required"] == ["ops"]
    assert schema["properties"]["ops"]["items"] == OP_SCHEMA


def test_tool_definitions_are_plain_json():
    json.loads(json.dumps(TOOLS))


# ---- dispatch and bad input ------------------------------------------------------------------


def test_unknown_tool_is_an_error(project_path: Path):
    assert_error(call_tool(project_path, "explode", {}), "explode", "describe", "rebuild")


def test_missing_project_is_an_error(tmp_path: Path):
    assert_error(call_tool(tmp_path / "nowhere", "describe", {}), "not a BrickSnap project")


def test_arguments_must_be_an_object(project_path: Path):
    assert_error(call_tool(project_path, "describe", NOT_A_DICT), "JSON object")


def test_none_arguments_count_as_empty(project_path: Path):
    assert not text_of(call_tool(project_path, "describe", NONE)).startswith("ERROR")


def test_project_file_that_is_not_an_object_is_an_error(project_path: Path):
    (project_path / "project.json").write_text("[1, 2]")
    for name in tools.TOOL_NAMES:
        assert_error(call_tool(project_path, name, {}), "project.json", "none of your tools")


@pytest.mark.parametrize("name", ["describe", "rebuild"])
def test_no_argument_tools_reject_arguments(project_path: Path, name: str):
    assert_error(call_tool(project_path, name, {"verbose": True}), "no arguments", "verbose")


def test_internal_failure_becomes_plain_error(project_path: Path, monkeypatch):
    from bricksnap import pipeline

    def broken(*a, **k):
        raise RuntimeError("the solver ran out of bricks")

    monkeypatch.setattr(pipeline, "rebuild", broken)
    blocks = call_tool(project_path, "rebuild", {})
    assert_error(blocks, "rebuild could not finish", "ran out of bricks")
    assert "Traceback" not in blocks[0]["text"]


# ---- describe ----------------------------------------------------------------------------------


def test_describe_reports_everything(bare_path: Path, catalog):
    project_path = bare_path
    blocks = call_tool(project_path, "describe", {})
    assert [b["type"] for b in blocks] == ["text"]
    text = blocks[0]["text"]
    project = Project(project_path)
    design = project.load_design()
    nx, ny, nz = design.shape
    assert f"{nx} x {ny} x {nz} cells" in text
    assert f"x from 0 to {nx - 1}" in text and f"z from 0 to {nz - 1}" in text
    assert f"{int(design.filled.sum())} filled cells" in text
    assert "Bounding box: x" in text
    assert "LAYER BY LAYER" in text and "z 0" in text
    # colours in use, with name, code and count
    assert "Light Bluish Grey (71):" in text
    # every catalogue colour, by code and name
    for c in catalog.colours.values():
        assert f"{c.code}: {c.name}" in text
    build = project.load_build()
    assert f"{len(build.parts)} parts" in text
    assert build.report is not None and build.report.text in text
    assert "No brief" in text and "Call brief" in text
    assert "0 edit operations applied" in text
    # stage 2: finish marks, details, the parts that may be placed, the finish words
    assert "smooth:" in text and "sloped:" in text
    assert "DETAILS PLACED\n  none" in text
    for part in catalog.detail_parts():
        assert f"  {part.id} {part.name}: {part.sx} x {part.sz} cells" in text
    assert '"studs"' in text and '"smooth"' in text and '"sloped"' in text
    nx = project.load_design().shape[0]
    assert f"cell {nx - 1} - x" in text
    assert tools._middle_words(nx) in text


@pytest.mark.parametrize(
    ("nx", "words"),
    [
        (
            10,
            "The left-right middle lies between cells 4 and 5 (x = 4.5 as a shape centre): "
            '"mirror" pairs cell x with cell 9 - x.',
        ),
        (
            11,
            'The left-right middle is cell 5 (x = 5 as a shape centre): "mirror" pairs cell x '
            "with cell 10 - x.",
        ),
        (
            1,
            'The left-right middle is cell 0 (x = 0 as a shape centre): "mirror" pairs cell x '
            "with cell 0 - x.",
        ),
    ],
)
def test_the_middle_is_stated_in_cell_indices(nx: int, words: str):
    assert tools._middle_words(nx) == words


def test_a_shape_centred_on_the_stated_middle_is_its_own_mirror_image(project_path: Path):
    needs_op("set_finish")  # "mirror" arrives together with the stage 2 operations
    text = text_of(call_tool(project_path, "describe", {}))
    nx, ny, nz = Project(project_path).load_design().shape
    assert nx % 2 == 0  # the even case is the one that was half a cell off
    assert f"x = {(nx - 1) / 2:g} as a shape centre" in text
    op = {
        "op": "add",
        "shape": {
            "type": "ellipsoid",
            "center": [(nx - 1) / 2, ny // 2, nz - 3],
            "radius": [1.2, 1.2, 2],
        },
        "color": 0,
        "mirror": True,
    }
    before = Project(project_path).load_design()
    reply = text_of(call_tool(project_path, "apply_ops", {"ops": [op]}))
    assert "its own mirror image" in reply, reply
    changed = Project(project_path).load_design().colors != before.colors
    assert changed.any() and (changed == changed[::-1, :, :]).all()


def test_describe_without_build_says_so(unbuilt_path: Path):
    text = text_of(call_tool(unbuilt_path, "describe", {}))
    assert "There is no build yet" in text and "rebuild" in text


def test_describe_shows_brief_and_edit_count(project_path: Path):
    with_brief(project_path, "A chess pawn; keep the round head.")
    call_tool(
        project_path,
        "apply_ops",
        {
            "ops": [
                {
                    "op": "add",
                    "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]},
                    "color": 4,
                }
            ]
        },
    )
    text = text_of(call_tool(project_path, "describe", {}))
    assert "A chess pawn; keep the round head." in text
    assert "1 edit operation applied" in text
    assert "Red (4): 1 cell" in text
    assert "not built yet" in text


def test_layers_merge_identical_plates():
    import numpy as np

    filled = np.zeros((4, 4, 6), dtype=bool)
    filled[0:2, 0:2, 0:3] = True
    filled[1, 1, 3] = True
    lines = tools._layers(filled)
    assert lines[0] == "  z 0 to 2: x 0 to 1, y 0 to 1, 4 cells each"
    assert lines[1] == "  z 3: x 1, y 1, 1 cell"
    assert lines[2].startswith("  z 4 to 5: empty")


def top_cell(design) -> tuple[int, int, int]:
    """The highest filled cell (x, y, z) of a design."""
    xs, ys, zs = np.nonzero(design.filled)
    i = int(zs.argmax())
    return int(xs[i]), int(ys[i]), int(zs[i])


def add_notes(path: Path, notes: list[str]) -> None:
    data = json.loads((path / "build.json").read_text())
    data["notes"] = notes
    (path / "build.json").write_text(json.dumps(data))


def test_describe_puts_what_matters_first(project_path: Path):
    add_notes(project_path, ["Thickened the sheet at x 1, y 2, z 3 to three plates."])
    text = text_of(call_tool(project_path, "describe", {}))
    order = [
        "GRID",
        "Bounding box",
        "BRIEF",
        "What it is:",
        "Check report:",
        "WHAT THE SOFTWARE DID BY ITSELF",
        "Thickened the sheet",
        "LAYER BY LAYER",
        "COLOURS IN USE",
        "FINISH MARKS",
        "DETAILS PLACED",
        "EDITS",
        "FINISH WORDS",
        "DETAIL PARTS",
        "COLOURS AVAILABLE",
    ]
    positions = [text.index(h) for h in order]
    assert positions == sorted(positions), list(zip(order, positions, strict=True))


def test_describe_shows_a_structured_brief(project_path: Path):
    text = text_of(call_tool(project_path, "describe", {}))
    assert "What it is: A chess pawn, standing upright" in text
    assert "  - a round head\n  - a wide flared base" in text
    assert "Plan: Keep the head round" in text
    assert "Palette: Light Bluish Grey (71), Black (0)" in text
    assert "Finish: Smooth on the head" in text
    assert "No brief" not in text


def test_describe_marks_colours_outside_the_palette(project_path: Path):
    with_brief(project_path, {**BRIEF, "colours": [0, 4]})
    text = text_of(call_tool(project_path, "describe", {}))
    line = next(ln for ln in text.splitlines() if ln.startswith("  Light Bluish Grey (71):"))
    assert "not in the brief's palette" in line
    # detail parts say which palette colours they are not made in
    assert "all of your palette" in text


def test_describe_names_the_palette_colours_a_detail_part_lacks(project_path: Path, catalog):
    # 4740 (the dish) is made in Black (0) but not in Medium Nougat (84)
    assert 0 in catalog.parts["4740"].colours and 84 not in catalog.parts["4740"].colours
    with_brief(project_path, {**BRIEF, "colours": [0, 84]})
    text = text_of(call_tool(project_path, "describe", {}))
    line = next(ln for ln in text.splitlines() if ln.startswith("  4740 "))
    assert line.endswith(", all of your palette but 84"), line
    # a part made in both says so, and one made in neither says that
    line = next(ln for ln in text.splitlines() if ln.startswith("  3040b "))
    assert line.endswith(", all of your palette"), line
    with_brief(project_path, {**BRIEF, "colours": [84, 379]})
    text = text_of(call_tool(project_path, "describe", {}))
    line = next(ln for ln in text.splitlines() if ln.startswith("  60897 "))
    assert line.endswith(", none of your palette"), line


def test_describe_lists_the_build_notes_each_on_its_own_line(project_path: Path):
    notes = [
        "Thickened the tail at x 11, y 6, z 9 to 10 from one plate to three so it holds.",
        "Could not put a slope on the left ear at x 4, y 5, z 27.",
    ]
    add_notes(project_path, notes)
    lines = text_of(call_tool(project_path, "describe", {})).splitlines()
    for n in notes:
        assert f"- {n}" in lines


def test_describe_says_when_the_software_did_nothing(project_path: Path):
    add_notes(project_path, [])
    text = text_of(call_tool(project_path, "describe", {}))
    assert "WHAT THE SOFTWARE DID BY ITSELF" in text and "\n- nothing" in text


def test_describe_counts_finish_marks_and_where_they_show(project_path: Path):
    project = Project(project_path)
    design = project.load_design()
    x, y, z = top_cell(design)
    assert design.finish is not None
    design.finish[:] = 0
    design.finish[x, y, z] = FINISH_SMOOTH
    design.finish[x, y, z - 1] = FINISH_SMOOTH  # covered by the cell above: does not show
    design.finish[x, y, 0] = FINISH_SLOPED
    project.save_design(design)
    text = text_of(call_tool(project_path, "describe", {}))
    assert (
        f"  smooth: 2 cells (x {x}, y {y}, z {z - 1} to {z}); 1 of them has nothing above" in text
    )
    assert f"  sloped: 1 cell (x {x}, y {y}, z 0); 0 of them have nothing above" in text


def test_describe_lists_details_and_slope_direction(project_path: Path, catalog):
    project = Project(project_path)
    design = project.load_design()
    x, y, z = top_cell(design)
    assert design.finish is not None
    design.finish[:] = 0
    design.finish[x, y, z] = FINISH_SMOOTH
    design.details = [
        Detail(part="98138", color=0, x=x, y=y, z=z + 1),
        Detail(part="54200", color=4, x=x, y=y, z=z + 2, rot=180),
    ]
    project.save_design(design)
    text = text_of(call_tool(project_path, "describe", {}))
    assert (
        f"  Tile 1 x 1 Round with Groove (98138), Black (0), at [{x}, {y}, {z + 1}], rot 0\n"
        in text
    )
    assert (
        f"(54200), Red (4), at [{x}, {y}, {z + 2}], rot 180, slopes down to +y (the back)" in text
    )
    # the detail stands on the smooth cell, so that finish does not show
    assert "smooth: 1 cell" in text and "0 of them have nothing above" in text
    # the reference list gives each slope's direction at rot 0
    line = next(ln for ln in text.splitlines() if ln.startswith("  54200 "))
    assert "2 plates" in line and "no stud on top" in line and "slopes down to -y" in line
    assert f"{len(catalog.parts['54200'].colours)} colours" in line
    # a slope with a stud on only part of its top says how many
    line = next(ln for ln in text.splitlines() if ln.startswith("  3040b "))
    assert "stud on 1 of its 2 cells" in line, line
    line = next(ln for ln in text.splitlines() if ln.startswith("  4286 "))
    assert "stud on 1 of its 3 cells" in line, line
    # a one-cell part with its stud, and a part with studs on every cell
    line = next(ln for ln in text.splitlines() if ln.startswith("  6141 "))
    assert ", stud on top," in line, line
    line = next(ln for ln in text.splitlines() if ln.startswith("  6143 "))
    assert ", studs on top," in line, line


def test_describe_survives_a_detail_of_an_unknown_part(project_path: Path):
    project = Project(project_path)
    design = project.load_design()
    design.details = [Detail(part="nope", color=999, x=0, y=0, z=0, rot=45)]
    project.save_design(design)
    text = text_of(call_tool(project_path, "describe", {}))
    assert "unknown part nope, unknown colour (999), at [0, 0, 0], rot 45" in text


# ---- brief -------------------------------------------------------------------------------------


def test_brief_saves_and_repeats_it(bare_path: Path):
    blocks = call_tool(bare_path, "brief", dict(BRIEF))
    text = text_of(blocks)
    assert not text.startswith("ERROR"), text
    assert text.startswith("Brief saved.")
    assert "What it is: A chess pawn" in text and "  - a wide flared base" in text
    assert "Palette: Light Bluish Grey (71), Black (0)" in text
    assert "apply_ops" in text
    assert Project(bare_path).meta["brief"] == BRIEF


def test_brief_is_cleaned_before_saving(bare_path: Path):
    messy = {**BRIEF, "object": "  A pawn.  ", "colours": [71.0, 0], "features": [" a ", "b"]}
    call_tool(bare_path, "brief", messy)
    saved = Project(bare_path).meta["brief"]
    assert saved["object"] == "A pawn."
    assert saved["colours"] == [71, 0] and all(type(c) is int for c in saved["colours"])
    assert saved["features"] == ["a", "b"]
    assert list(saved) == ["object", "features", "plan", "colours", "finish"]


def test_a_later_brief_replaces_the_first(project_path: Path):
    text = text_of(call_tool(project_path, "brief", {**BRIEF, "colours": [15]}))
    assert text.startswith("Brief replaced.")
    assert Project(project_path).meta["brief"]["colours"] == [15]


def test_brief_names_design_colours_outside_the_palette(bare_path: Path):
    text = text_of(call_tool(bare_path, "brief", {**BRIEF, "colours": [4]}))
    assert "not in this palette: Light Bluish Grey (71) on" in text
    text = text_of(call_tool(bare_path, "brief", dict(BRIEF)))
    assert "not in this palette" not in text


def test_brief_works_without_a_design(tmp_path: Path):
    folder = tmp_path / "nodesign"
    folder.mkdir()
    (folder / "project.json").write_text(json.dumps({"name": "x", "seed": "seed.stl"}))
    assert call_tool(folder, "brief", dict(BRIEF))[0]["text"].startswith("Brief saved.")


@pytest.mark.parametrize(
    ("change", "fragments"),
    [
        ({"object": None}, ['missing: "object"']),
        ({"features": ["one"]}, ['"features" has 1; give 2 to 4']),
        ({"features": ["a", "b", "c", "d", "e"]}, ['"features" has 5; give 2 to 4']),
        ({"features": "ears and tail"}, ['"features" must be a list', "not one string"]),
        ({"features": ["ears", ""]}, ['"features item 2" is empty']),
        ({"features": ["ears", 3]}, ['"features item 2" must be text', "not 3"]),
        ({"colours": [999]}, ["999", "not a colour code", "COLOURS AVAILABLE"]),
        ({"colours": [0, 1, 2, 4, 5, 10, 14]}, ['"colours" has 7 codes; choose at most 6']),
        ({"colours": []}, ['"colours" must be a list of 1 to 6']),
        ({"colours": [0, 0]}, ["lists 0 twice"]),
        ({"colours": [True]}, ["true", "not a colour code"]),
        ({"colours": [4.5]}, ["4.5", "not a colour code"]),
        ({"colours": ["red"]}, ['"red"', "not a colour code"]),
        ({"colours": [10**5000]}, ["a very large number"]),
        ({"colours": "red"}, ['"colours" must be a list']),
        ({"plan": "   "}, ['"plan" is empty']),
        ({"plan": "x" * 2000}, ['"plan" has 2000 characters']),
        ({"finish": {"a": 1}}, ['"finish" must be text', "not an object"]),
        ({"colors": [0]}, ['"colors" is not a field', 'did you mean "colours"']),
        ({"subject": "a pawn"}, ['did you mean "object"']),
    ],
)
def test_bad_brief_is_an_error_and_saves_nothing(bare_path: Path, change: dict, fragments):
    args = {k: v for k, v in {**BRIEF, **change}.items() if v is not None}
    stamp = (bare_path / "project.json").read_bytes()
    blocks = call_tool(bare_path, "brief", args)
    assert_error(blocks, "the brief was not saved", *fragments)
    assert (bare_path / "project.json").read_bytes() == stamp


def test_bad_brief_lists_every_problem_at_once(bare_path: Path):
    blocks = call_tool(bare_path, "brief", {"features": ["x"], "colours": [999]})
    text = blocks[0]["text"]
    assert 'missing: "object", "plan", "finish"' in text
    assert '"features" has 1' in text and "999" in text
    assert text.count("\n- ") == 3


@pytest.mark.parametrize(
    "args",
    [
        {"object": float("nan")},
        {"features": [[["deep"]]] * 3},
        {"colours": [float("inf"), -(10**30), None, {}, []]},
        {"features": list(range(1000)), "colours": list(range(1000))},
        {"object": "x" * 100_000},
        {"": ""},
        {**BRIEF, "k" * 200_000: 1},
        {**BRIEF, **{f"k{i}": i for i in range(5000)}},
    ],
    ids=[
        "nan",
        "nested",
        "odd-colours",
        "long-lists",
        "long-text",
        "empty-key",
        "long-key",
        "many-keys",
    ],
)
def test_strange_brief_input_never_raises(bare_path: Path, args: dict):
    stamp = (bare_path / "project.json").read_bytes()
    blocks = call_tool(bare_path, "brief", args)
    assert_error(blocks, "the brief was not saved")
    assert len(blocks[0]["text"]) < 3000
    assert (bare_path / "project.json").read_bytes() == stamp


def test_many_unknown_brief_fields_are_summed_up(bare_path: Path):
    args = {**BRIEF, **{f"extra{i}": i for i in range(9)}}
    text = call_tool(bare_path, "brief", args)[0]["text"]
    assert '"extra0" is not a field of the brief' in text
    assert "and 4 more fields that are not part of the brief" in text
    assert '"extra8"' not in text


LONG = "z" * 200_000
MANY = {f"k{i}": i for i in range(5000)}


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("describe", {LONG: 1}),
        ("describe", MANY),
        ("rebuild", {LONG: 1}),
        ("render", {LONG: 1}),
        ("render", MANY),
        ("render", {"views": [LONG]}),
        ("apply_ops", {"ops": [ONE_ADD], LONG: 1}),
        ("apply_ops", {"ops": [ONE_ADD], **MANY}),
        (LONG, {}),
    ],
    ids=[
        "describe-long",
        "describe-many",
        "rebuild-long",
        "render-long",
        "render-many",
        "render-long-view",
        "apply-long",
        "apply-many",
        "long-tool-name",
    ],
)
def test_echoed_names_are_kept_short(project_path: Path, name: str, args: dict):
    stamp = (project_path / "design.npz").stat().st_mtime_ns
    blocks = call_tool(project_path, name, args)
    assert_error(blocks)
    assert len(blocks[0]["text"]) < 1000, len(blocks[0]["text"])
    assert (project_path / "design.npz").stat().st_mtime_ns == stamp


# ---- apply_ops needs a brief -------------------------------------------------------------------


def test_apply_ops_refuses_without_a_brief(bare_path: Path):
    stamp = (bare_path / "design.npz").stat().st_mtime_ns
    blocks = call_tool(bare_path, "apply_ops", {"ops": [ONE_ADD]})
    assert_error(
        blocks, "write the brief first (call brief)", '"object"', '"colours"', "Nothing was applied"
    )
    assert (bare_path / "design.npz").stat().st_mtime_ns == stamp
    assert Project(bare_path).load_design().log == []


def test_apply_ops_runs_once_the_brief_is_written(bare_path: Path):
    call_tool(bare_path, "brief", dict(BRIEF))
    assert "1 of 1 operations applied" in text_of(
        call_tool(bare_path, "apply_ops", {"ops": [ONE_ADD]})
    )


def test_a_brief_from_an_earlier_run_counts_even_as_plain_text(bare_path: Path):
    with_brief(bare_path, "A pawn; keep the round head.")
    assert "1 of 1 operations applied" in text_of(
        call_tool(bare_path, "apply_ops", {"ops": [ONE_ADD]})
    )


@pytest.mark.parametrize("empty", ["", "   ", {}, None, 0, []])
def test_an_empty_brief_does_not_count(bare_path: Path, empty):
    with_brief(bare_path, empty)
    assert_error(call_tool(bare_path, "apply_ops", {"ops": [ONE_ADD]}), "write the brief first")


# ---- stage 2 operations through apply_ops ------------------------------------------------------


def needs_op(name: str) -> None:
    if name not in design_module.OPS:
        pytest.skip(f'bricksnap.design does not have the "{name}" operation yet')


def test_set_finish_through_apply_ops(project_path: Path):
    needs_op("set_finish")
    design = Project(project_path).load_design()
    x, y, z = top_cell(design)
    op = {
        "op": "set_finish",
        "shape": {"type": "box", "min": [x, y, z], "max": [x, y, z]},
        "finish": "smooth",
    }
    text = text_of(call_tool(project_path, "apply_ops", {"ops": [op]}))
    assert text.startswith("1. set_finish: applied, finish changed on 1 cell."), text
    after = Project(project_path).load_design()
    assert after.finish is not None and int(after.finish[x, y, z]) == FINISH_SMOOTH
    described = text_of(call_tool(project_path, "describe", {}))
    assert "smooth: 1 cell" in described and "1 of them has nothing above" in described


def test_place_and_remove_detail_through_apply_ops(project_path: Path):
    needs_op("place_detail")
    needs_op("remove_detail")
    design = Project(project_path).load_design()
    x, y, z = top_cell(design)
    place = {"op": "place_detail", "part": "98138", "color": 0, "at": [x, y, z + 1], "rot": 0}
    text = text_of(call_tool(project_path, "apply_ops", {"ops": [place]}))
    assert text.startswith("1. place_detail: applied."), text
    assert "0 cells changed" not in text and "1 detail and" in text
    described = text_of(call_tool(project_path, "describe", {}))
    assert f"(98138), Black (0), at [{x}, {y}, {z + 1}], rot 0" in described
    remove = {"op": "remove_detail", "at": [x, y, z + 1]}
    text = text_of(call_tool(project_path, "apply_ops", {"ops": [remove]}))
    assert text.startswith("1. remove_detail: applied."), text
    assert "DETAILS PLACED\n  none" in text_of(call_tool(project_path, "describe", {}))


def test_mirror_through_apply_ops(project_path: Path):
    needs_op("set_finish")  # "mirror" arrives together with the stage 2 operations
    design = Project(project_path).load_design()
    nx, _, nz = design.shape
    op = {
        "op": "add",
        "shape": {"type": "box", "min": [0, 0, nz - 1], "max": [0, 0, nz - 1]},
        "color": 4,
        "mirror": True,
    }
    text = text_of(call_tool(project_path, "apply_ops", {"ops": [op]}))
    assert text.startswith("1. add: applied, 2 cells changed."), text
    after = Project(project_path).load_design()
    assert after.colors[0, 0, nz - 1] == 4 and after.colors[nx - 1, 0, nz - 1] == 4


# ---- render ------------------------------------------------------------------------------------


def decode_png(block: dict) -> Image.Image:
    assert block["type"] == "image" and block["media_type"] == "image/png"
    return Image.open(io.BytesIO(base64.b64decode(block["data"])))


def test_render_returns_compare_sheet_and_explanation(project_path: Path):
    blocks = call_tool(project_path, "render", {})
    assert [b["type"] for b in blocks] == ["image", "text"]
    img = decode_png(blocks[0])
    assert img.width > 400 and img.height > 300
    assert (project_path / "renders" / "compare.png").exists()
    text = blocks[1]["text"]
    assert "Top row" in text and "Bottom row" in text
    assert "front, right, top, iso" in text
    assert "plates" in text and "studs" in text
    assert "NOTE" not in text


def test_render_custom_views(project_path: Path):
    default = decode_png(call_tool(project_path, "render", {})[0])
    blocks = call_tool(project_path, "render", {"views": ["front"]})
    img = decode_png(blocks[0])
    assert img.width < default.width
    assert "front." in blocks[1]["text"]
    assert (project_path / "renders" / "compare-front.png").exists()


def test_render_without_build_draws_design(unbuilt_path: Path):
    blocks = call_tool(unbuilt_path, "render", {"views": ["top"]})
    decode_png(blocks[0])
    assert "there is no build yet" in blocks[1]["text"]


def test_render_warns_when_build_is_out_of_date(project_path: Path):
    call_tool(
        project_path,
        "apply_ops",
        {
            "ops": [
                {
                    "op": "add",
                    "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]},
                    "color": 4,
                }
            ]
        },
    )
    assert "NOTE" in call_tool(project_path, "render", {"views": ["front"]})[1]["text"]
    call_tool(project_path, "rebuild", {})
    assert "NOTE" not in call_tool(project_path, "render", {"views": ["front"]})[1]["text"]


@pytest.mark.parametrize(
    ("args", "fragment"),
    [
        ({"views": ["sideways"]}, "unknown view"),
        ({"views": []}, "list of 1 to"),
        ({"views": "front"}, "list of 1 to"),
        ({"views": ["front", "front"]}, "twice"),
        ({"view": ["front"]}, "does not take view"),
    ],
)
def test_render_bad_arguments(project_path: Path, args: dict, fragment: str):
    assert_error(call_tool(project_path, "render", args), fragment)


def test_large_picture_is_shrunk(monkeypatch):
    import numpy as np

    rng = np.random.default_rng(0)
    noisy = Image.fromarray(rng.integers(0, 256, (600, 800, 3), dtype=np.uint8))
    monkeypatch.setattr(tools, "MAX_IMAGE_BYTES", 150_000)
    data = tools._png_bytes(noisy)
    assert len(data) <= 150_000
    Image.open(io.BytesIO(data)).verify()


def test_small_picture_is_untouched():
    img = Image.new("RGB", (100, 80), (200, 10, 10))
    data = tools._png_bytes(img)
    assert Image.open(io.BytesIO(data)).size == (100, 80)


# ---- apply_ops ---------------------------------------------------------------------------------


def test_apply_ops_reports_each_op_and_saves(project_path: Path, catalog):
    before = Project(project_path).load_design()
    ops = [
        {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [20, 20, 2]}, "color": 4},
        {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]}, "colour": 4},
        {"op": "remove", "shape": {"type": "box", "min": [500, 500, 500], "max": [501, 501, 501]}},
    ]
    blocks = call_tool(project_path, "apply_ops", {"ops": ops})
    text = text_of(blocks)
    lines = text.splitlines()
    assert lines[0].startswith("1. paint: applied,") and "cells changed" in lines[0]
    assert lines[1].startswith("2. add: not applied.") and '"color"' in lines[1]
    assert lines[2].startswith("3. remove: not applied.")
    assert "1 of 3 operations applied" in text
    assert text.rstrip().endswith("Nothing is visible in render until you call rebuild.")
    after = Project(project_path).load_design()
    assert len(after.log) == 1
    bottom = after.colors[:, :, 0:3]
    assert (bottom[bottom != -1] == 4).all()
    assert (before.filled == after.filled).all()


def test_apply_ops_with_nothing_applied_does_not_save(project_path: Path):
    design_file = project_path / "design.npz"
    stamp = design_file.stat().st_mtime_ns
    op = {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": 999}
    text = text_of(call_tool(project_path, "apply_ops", {"ops": [op]}))
    assert "0 of 1 operations applied" in text
    assert design_file.stat().st_mtime_ns == stamp


def test_apply_ops_accepts_a_single_op_object(project_path: Path):
    op = {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]}, "color": 4}
    assert "1 of 1 operations applied" in text_of(call_tool(project_path, "apply_ops", {"ops": op}))


@pytest.mark.parametrize(
    ("args", "fragment"),
    [
        ({}, 'needs "ops"'),
        ({"ops": []}, "non-empty list"),
        ({"ops": "add a box"}, "non-empty list"),
        ({"ops": [{}], "dry_run": True}, "does not take dry_run"),
    ],
)
def test_apply_ops_bad_arguments(project_path: Path, args: dict, fragment: str):
    assert_error(call_tool(project_path, "apply_ops", args), fragment)


def test_apply_ops_too_many(project_path: Path):
    op = {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]}, "color": 4}
    blocks = call_tool(project_path, "apply_ops", {"ops": [op] * (tools.MAX_OPS_PER_CALL + 1)})
    assert_error(blocks, "at most", "Nothing was applied")
    assert Project(project_path).load_design().log == []


def test_apply_ops_handles_non_dict_ops(project_path: Path):
    text = text_of(call_tool(project_path, "apply_ops", {"ops": ["paint it red", 3]}))
    lines = text.splitlines()
    assert lines[0].startswith("1. operation: not applied."), lines
    assert lines[1].startswith("2. operation: not applied."), lines
    assert "0 of 2 operations applied" in text


# ---- rebuild -----------------------------------------------------------------------------------


def test_rebuild_writes_build_and_returns_report(project_path: Path):
    op = {"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 2]}, "color": 4}
    call_tool(project_path, "apply_ops", {"ops": [op]})
    os.utime(project_path / "build.json", ns=(0, 0))
    text = text_of(call_tool(project_path, "rebuild", {}))
    build = Project(project_path).load_build()
    assert text.startswith(f"Rebuilt: {len(build.parts)} parts")
    assert build.report is not None and build.report.text in text
    assert any(p.color == 4 for p in build.parts)
    assert (project_path / "build.ldr").exists()
    assert "render" in text


def test_rebuild_puts_the_software_notes_before_the_report(project_path: Path, monkeypatch):
    from bricksnap import pipeline

    real = pipeline.rebuild
    notes = ["Thickened the sheet at x 1 to 3, y 2, z 4 to three plates.", "Added a support."]

    def with_notes(project, *, catalog=None):
        build = real(project, catalog=catalog)
        build.notes = list(notes)
        project.save_build(build)
        return build

    monkeypatch.setattr(pipeline, "rebuild", with_notes)
    text = text_of(call_tool(project_path, "rebuild", {}))
    lines = text.splitlines()
    header = next(i for i, ln in enumerate(lines) if "made by itself" in ln)
    assert lines[header + 1 : header + 3] == [f"- {n}" for n in notes]
    assert text.index("made by itself") < text.index("Check report:")
    build = Project(project_path).load_build()
    assert build.report is not None and text.index(build.report.text) > text.index(notes[1])


def test_rebuild_without_notes_says_the_software_changed_nothing(project_path: Path, monkeypatch):
    from bricksnap import pipeline

    real = pipeline.rebuild

    def without_notes(project, *, catalog=None):
        build = real(project, catalog=catalog)
        build.notes = []
        return build

    monkeypatch.setattr(pipeline, "rebuild", without_notes)
    text = text_of(call_tool(project_path, "rebuild", {}))
    assert "made no changes by itself" in text


def test_part_kinds_are_counted_in_plain_words(catalog):
    for kind in {p.kind for p in catalog.parts.values()}:
        for n in (1, 2):
            words = tools._kind_count(n, kind)
            assert "_" not in words and not words.endswith(("dishs", "details")), words
    assert tools._kind_count(1, "round_tile") == "1 round tile"
    assert tools._kind_count(2, "round_tile") == "2 round tiles"
    assert tools._kind_count(2, "dish") == "2 dishes"
    assert tools._kind_count(1, "detail") == "1 clip or jumper plate"
    assert tools._kind_count(3, "brick") == "3 bricks"
    assert tools._kind_count(2, "side_stud") == "2 bricks with side studs"
    assert tools._kind_count(2, "new_kind") == "2 new kinds"
    assert tools._kind_count(2, "box") == "2 boxes"


def test_describe_counts_special_parts_in_plain_words(project_path: Path, catalog):
    from bricksnap.types import Placement

    project = Project(project_path)
    build = project.load_build()
    build.parts.extend(
        [
            Placement(part="4740", color=0, x=0, y=0, z=40),
            Placement(part="4740", color=0, x=2, y=0, z=40),
            Placement(part="60897", color=0, x=4, y=0, z=40),
            Placement(part="98138", color=0, x=5, y=0, z=40),
        ]
    )
    project.save_build(build)
    line = next(
        ln
        for ln in text_of(call_tool(project_path, "describe", {})).splitlines()
        if " parts: " in ln
    )
    assert "2 dishes" in line and "1 clip or jumper plate" in line and "1 round tile" in line
    assert "_" not in line and "detail" not in line, line


def test_rebuild_through_the_real_finishing_pass(project_path: Path):
    """No fakes: set_finish and place_detail go through bricksnap.design, and rebuild runs the
    real make-buildable and finishing passes."""
    needs_op("place_detail")
    design = Project(project_path).load_design()
    nx, ny, nz = design.shape
    x, y, z = top_cell(design)
    ops = [
        {
            "op": "set_finish",
            "shape": {"type": "box", "min": [0, 0, 0], "max": [nx - 1, ny - 1, nz - 1]},
            "finish": "smooth",
        },
        {"op": "place_detail", "part": "98138", "color": 0, "at": [x, y, z + 1], "rot": 0},
    ]
    assert "2 of 2 operations applied" in text_of(
        call_tool(project_path, "apply_ops", {"ops": ops})
    )
    text = text_of(call_tool(project_path, "rebuild", {}))
    first = text.splitlines()[0]
    assert "tiles" in first and "1 round tile" in first and "round_tile" not in first, first
    build = Project(project_path).load_build()
    assert build.notes and any(p.part == "98138" for p in build.parts)
    assert text.index(f"- {build.notes[0]}") < text.index("Check report:")
    described = text_of(call_tool(project_path, "describe", {}))
    assert "The design has edits that are not built yet" not in described
    assert f"- {build.notes[0]}" in described


def test_rebuild_without_design_is_an_error(tmp_path: Path):
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / "project.json").write_text(json.dumps({"name": "x", "seed": "seed.stl"}))
    assert_error(call_tool(folder, "rebuild", {}), "no design yet")


# ---- what error text tells the model -----------------------------------------------------------


@pytest.mark.parametrize("name", ["describe", "render", "apply_ops", "rebuild"])
def test_missing_design_error_hides_the_path_and_says_it_cannot_be_fixed(tmp_path: Path, name: str):
    folder = tmp_path / "projs" / "broken"
    folder.mkdir(parents=True)
    (folder / "project.json").write_text(json.dumps({"name": "x", "seed": "seed.stl"}))
    args = {"ops": [{"op": "remove", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 0, 0]}}]}
    blocks = call_tool(folder, name, args if name == "apply_ops" else {})
    assert_error(blocks, "no design yet", "none of your tools can fix")
    text = blocks[0]["text"]
    assert str(tmp_path) not in text and "projs" not in text
    assert "bricksnap new" not in text  # advice the model cannot act on


def test_os_error_hides_the_path(project_path: Path):
    shutil.rmtree(project_path / "renders", ignore_errors=True)
    (project_path / "renders").write_text("not a folder")
    blocks = call_tool(project_path, "render", {"views": ["front"]})
    assert_error(blocks, "render could not finish", "the project folder")
    assert str(project_path) not in blocks[0]["text"]


@pytest.mark.parametrize("folder", ["back\\slash proj", "tab\tproj", "quote's proj"])
def test_os_error_hides_a_path_that_python_shows_escaped(project_path: Path, folder: str):
    odd = project_path.parent / folder
    project_path.rename(odd)
    shutil.rmtree(odd / "renders", ignore_errors=True)
    (odd / "renders").write_text("not a folder")
    blocks = call_tool(odd, "render", {"views": ["front"]})
    assert_error(blocks, "render could not finish", "the project folder")
    text = blocks[0]["text"]
    assert str(odd.parent) not in text and repr(str(odd.parent))[1:-1] not in text, text
    assert folder not in text and repr(folder)[1:-1] not in text, text


def test_scrub_hides_escaped_forms_of_the_project_and_home_folders(tmp_path: Path, monkeypatch):
    home = tmp_path / "Pat\\Example"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    project = home / "projects" / "cat\tthing"
    for shown in (str(project), repr(str(project))[1:-1]):
        assert tools._scrub(f"could not write {shown}/renders", project) == (
            "could not write the project folder/renders"
        )
    elsewhere = home / "other"
    for shown in (str(elsewhere), repr(str(elsewhere))[1:-1]):
        assert tools._scrub(f"in {shown}", project) == "in ~/other"


def test_missing_project_error_hides_the_path(tmp_path: Path):
    blocks = call_tool(tmp_path / "nowhere", "describe", {})
    assert_error(blocks, "not a BrickSnap project")
    assert str(tmp_path) not in blocks[0]["text"]


@pytest.mark.parametrize("content", [b"{nope", b"\xff\xfe\x00"], ids=["not-json", "not-utf8"])
def test_unreadable_project_file_is_an_error(project_path: Path, content: bytes):
    (project_path / "project.json").write_bytes(content)
    for name in tools.TOOL_NAMES:
        blocks = call_tool(project_path, name, {})
        assert_error(blocks, "project.json", "none of your tools can fix")
        assert str(project_path) not in blocks[0]["text"]


def test_text_output_hides_email_addresses(project_path: Path):
    project = Project(project_path)
    project.meta["brief"] = "A pawn for pat@example.org."
    project.save_meta()
    text = text_of(call_tool(project_path, "describe", {}))
    assert "pat@example.org" not in text and "A pawn for <account email>." in text


def test_brief_reply_hides_paths_and_email_addresses(bare_path: Path):
    where = str(bare_path.resolve())
    args = {**BRIEF, "plan": f"Mail pat@example.org the file in {where}/notes."}
    for name, a in (("brief", args), ("describe", {})):
        text = text_of(call_tool(bare_path, name, a))
        assert "pat@example.org" not in text and where not in text, name
        assert "<account email>" in text and "the project folder/notes" in text, name


@pytest.mark.parametrize("views", [None, ["front"]], ids=["default-views", "custom-views"])
def test_render_without_seed_says_there_is_one_row(project_path: Path, views):
    args = {} if views is None else {"views": views}
    two_rows = decode_png(call_tool(project_path, "render", args)[0])
    Project(project_path).seed_path.unlink()
    blocks = call_tool(project_path, "render", args)
    one_row = decode_png(blocks[0])
    assert one_row.height < two_rows.height
    text = blocks[1]["text"]
    assert "Top row" not in text and "Bottom row" not in text
    assert "one row" in text and "could not be loaded" in text


def test_describe_says_when_a_detail_on_a_face_was_not_built(tmp_path, catalog):
    project = create_project("samples/models/cat.glb", studs=12, directory=tmp_path)
    paint = {"type": "box", "min": [3, 4, 12], "max": [3, 4, 14]}
    ops = [
        {"op": "paint", "shape": paint, "color": 71, "mirror": True},
        {
            "op": "place_detail",
            "part": "98138",
            "color": 0,
            "at": [3, 3, 12],
            "face": "front",
            "mirror": True,
        },
    ]
    project.meta["brief"] = "a cat"
    project.save_meta()
    text = text_of(call_tool(project.path, "apply_ops", {"ops": ops}))
    assert "a Light Bluish Grey (71) brick with a stud on its side" in text
    rebuild(project)
    text = text_of(call_tool(project.path, "describe", {}))
    assert text.count("on the front face (held by a side stud); NOT BUILT") == 2
    assert "Left off the Black Tile 1 x 1 Round with Groove (98138) at x=3, y=3, z=12" in text
