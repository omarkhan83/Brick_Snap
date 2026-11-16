"""Tests for the designer's four tools (bricksnap/designer/tools.py)."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from bricksnap.design import OP_SCHEMA
from bricksnap.designer import tools
from bricksnap.designer.tools import TOOLS, call_tool
from bricksnap.pipeline import create_project, rebuild
from bricksnap.project import Project

NOT_A_DICT: Any = ["x"]
NONE: Any = None


@pytest.fixture(scope="module")
def _base_project(tmp_path_factory, pawn_path: Path, catalog) -> Path:
    root = tmp_path_factory.mktemp("designer-tools")
    project = create_project(pawn_path, studs=8, directory=root, catalog=catalog)
    rebuild(project, catalog=catalog)
    return project.path


@pytest.fixture
def project_path(_base_project: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "pawn"
    shutil.copytree(_base_project, dest)
    return dest


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


def test_exactly_four_tools_in_order():
    assert [t["name"] for t in TOOLS] == ["describe", "render", "apply_ops", "rebuild"]
    for t in TOOLS:
        assert set(t) == {"name", "description", "input_schema"}
        assert t["input_schema"]["type"] == "object"
        assert len(t["description"]) > 80


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


def test_describe_reports_everything(project_path: Path, catalog):
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
    assert "Layer by layer" in text and "z 0" in text
    # colours in use, with name, code and count
    assert "Light Bluish Grey (71):" in text
    # every catalogue colour, by code and name
    for c in catalog.colours.values():
        assert f"{c.code}: {c.name}" in text
    build = project.load_build()
    assert f"{len(build.parts)} parts" in text
    assert build.report is not None and build.report.text in text
    assert "No brief" in text
    assert "0 edit operations applied" in text


def test_describe_without_build_says_so(unbuilt_path: Path):
    text = text_of(call_tool(unbuilt_path, "describe", {}))
    assert "There is no build yet" in text and "rebuild" in text


def test_describe_shows_brief_and_edit_count(project_path: Path):
    project = Project(project_path)
    project.meta["brief"] = "A chess pawn; keep the round head."
    project.save_meta()
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
