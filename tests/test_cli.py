"""Tests for the ``bricksnap`` command, run through ``main([...])``.

The AI designer and the viewer server are always replaced by fakes: these tests never start
a model run or a web server.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

from bricksnap.bench import Row
from bricksnap.catalog import load_catalog
from bricksnap.checks import check
from bricksnap.cli import main
from bricksnap.designer.runner import TOOL_PREFIX, DesignerRun
from bricksnap.export import PartLine
from bricksnap.pipeline import create_project, rebuild, render_compare
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Placement, Report

STUDS = "8"
# Adds a second, separate block on the ground in a corner of the pawn's grid (10 x 10 x 26
# at 8 studs; the pawn stands on x and y = 2 to 7), so the build is in two pieces and fails
# its checks. (Stage 1 removed three plates so the top floated; the make-buildable pass now
# props up a floating part, but it never joins two objects that each stand on the ground.)
SPLIT = [{"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 1, 2]}, "color": 4}]
PAINT = [{"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [9, 9, 2]}, "color": 4}]
# Four paint operations that each change something (different heights, different colours).
PAINT_4 = [
    {
        "op": "paint",
        "shape": {"type": "box", "min": [0, 0, 3 * i], "max": [9, 9, 3 * i + 2]},
        "color": color,
    }
    for i, color in enumerate((4, 1, 14, 2))
]


@pytest.fixture(scope="module")
def built_pawn(tmp_path_factory, pawn_path) -> Path:
    """A built pawn project, made once; tests copy it with ``pawn_copy``."""
    base = tmp_path_factory.mktemp("base")
    project = create_project(pawn_path, studs=int(STUDS), directory=base)
    rebuild(project)
    render_compare(project)
    return project.path


@pytest.fixture
def pawn_copy(built_pawn, tmp_path) -> Path:
    dest = tmp_path / "work" / "pawn"
    shutil.copytree(built_pawn, dest)
    return dest


@pytest.fixture
def in_projects(built_pawn, tmp_path, monkeypatch) -> Path:
    """Run from tmp_path with a built pawn at ./projects/pawn; returns that folder."""
    dest = tmp_path / "projects" / "pawn"
    shutil.copytree(built_pawn, dest)
    monkeypatch.chdir(tmp_path)
    return dest


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    return code, captured.out, captured.err


def log_length(project_path: Path) -> int:
    return len(json.loads((project_path / "design.json").read_text(encoding="utf-8"))["log"])


# ---- new ----------------------------------------------------------------------------------


def test_new_makes_and_builds_a_project_and_says_what_to_do_next(capsys, tmp_path, pawn_path):
    code, out, err = run(capsys, "new", str(pawn_path), "--studs", STUDS, "--dir", str(tmp_path))
    assert code == 0, out + err
    folder = tmp_path / "pawn"
    for name in ("project.json", "design.npz", "build.json", "build.ldr", "renders/compare.png"):
        assert (folder / name).is_file(), name
    assert 'Made the project "pawn"' in out
    assert str(folder) in out
    assert "8 studs (64 mm)" in out
    assert "one connected piece" in out
    assert "OK:" in out  # the report text itself
    assert str(folder / "renders" / "compare.png") in out
    assert str(folder / "build.ldr") in out
    assert "BrickLink Studio" in out
    assert f"bricksnap view {folder}" in out
    assert "bricksnap design" in out
    assert out.rstrip().splitlines()[-1].strip()  # ends with the next steps, not blank
    assert err == ""


def test_new_defaults_to_projects_folder_and_suggests_bare_name(
    capsys, tmp_path, pawn_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(capsys, "new", str(pawn_path), "--studs", STUDS)
    assert code == 0
    assert (tmp_path / "projects" / "pawn" / "build.json").is_file()
    assert "Folder: projects/pawn" in out
    assert "bricksnap view pawn\n" in out
    assert "projects/pawn/renders/compare.png" in out


def test_new_passes_name_up_and_hollow_through(capsys, tmp_path, pawn_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(
        capsys,
        "new",
        str(pawn_path),
        "--studs",
        STUDS,
        "--name",
        "My Pawn",
        "--up",
        "z",
        "--hollow",
    )
    assert code == 0
    meta = json.loads((tmp_path / "projects" / "my-pawn" / "project.json").read_text())
    assert meta["name"] == "My Pawn"
    assert meta["up"] == "z"
    assert meta["hollow"] is True
    assert "hollow inside" in out
    # the project can be reopened by its name as typed
    code, out, _ = run(capsys, "check", "My Pawn")
    assert code == 0
    assert "OK:" in out


def test_new_with_missing_model_file(capsys, tmp_path):
    code, out, err = run(
        capsys, "new", str(tmp_path / "nothing.stl"), "--studs", STUDS, "--dir", str(tmp_path)
    )
    assert code == 2
    assert err.startswith("Error: ")
    assert "nothing.stl" in err
    assert not (tmp_path / "nothing").exists()


def test_new_with_unsupported_file_type(capsys, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("not a model", encoding="utf-8")
    code, _, err = run(capsys, "new", str(notes), "--studs", STUDS, "--dir", str(tmp_path))
    assert code == 2
    assert err.startswith("Error: ")
    assert "STL" in err
    assert not (tmp_path / "notes").exists()


def test_new_with_flat_model(capsys, tmp_path):
    flat = tmp_path / "sheet.stl"
    trimesh.Trimesh(
        vertices=np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [10, 10, 0]], dtype=float),
        faces=np.array([[0, 1, 2], [1, 3, 2]]),
        process=False,
    ).export(flat)
    code, _, err = run(capsys, "new", str(flat), "--studs", STUDS, "--dir", str(tmp_path))
    assert code == 2
    assert err.startswith("Error: ")
    assert "flat" in err
    assert not (tmp_path / "sheet").exists()


def test_new_with_size_out_of_range(capsys, tmp_path, pawn_path):
    code, _, err = run(capsys, "new", str(pawn_path), "--studs", "2", "--dir", str(tmp_path))
    assert code == 2
    assert "between 4 and 96" in err


def test_new_into_a_folder_that_is_a_file(capsys, tmp_path, pawn_path):
    afile = tmp_path / "afile"
    afile.write_text("not a folder", encoding="utf-8")
    code, _, err = run(capsys, "new", str(pawn_path), "--studs", STUDS, "--dir", str(afile))
    assert code == 2
    assert err.startswith("Error: ")
    assert str(afile) in err


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root can write anywhere"
)
def test_new_into_a_folder_that_cannot_be_written(capsys, tmp_path, pawn_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        code, _, err = run(capsys, "new", str(pawn_path), "--studs", STUDS, "--dir", str(locked))
    finally:
        locked.chmod(0o700)
    assert code == 2
    assert err.startswith("Error: ")
    assert str(locked) in err


def test_new_refuses_to_overwrite_a_project(capsys, tmp_path, pawn_path):
    args = ("new", str(pawn_path), "--studs", STUDS, "--dir", str(tmp_path))
    assert run(capsys, *args)[0] == 0
    code, _, err = run(capsys, *args)
    assert code == 2
    assert "already holds a project" in err


@pytest.mark.parametrize(
    "extra, expected",
    [([], "--studs"), (["--studs", "lots"], "invalid int value"), (["--up", "w"], "--up")],
)
def test_new_with_bad_arguments(capsys, pawn_path, extra, expected):
    code, out, err = run(capsys, "new", str(pawn_path), *extra)
    assert code == 2
    assert err.startswith("Error: ")
    assert expected in err
    assert "bricksnap --help" in err


# ---- finding a project --------------------------------------------------------------------


def test_bare_name_is_found_under_projects(capsys, in_projects):
    code, out, _ = run(capsys, "check", "pawn")
    assert code == 0
    assert out.startswith("OK:")


def test_path_to_project_works_from_anywhere(capsys, pawn_copy, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert run(capsys, "check", str(pawn_copy))[0] == 0


def test_folder_that_is_not_a_project(capsys, tmp_path):
    (tmp_path / "holiday").mkdir()
    code, out, err = run(capsys, "build", str(tmp_path / "holiday"))
    assert code == 2
    assert err.startswith("Error: ")
    assert "not a BrickSnap project" in err
    assert out == ""


def test_unknown_project_name(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "build", "dragon")
    assert code == 2
    assert "Cannot find a project called 'dragon'" in err
    assert "projects/dragon" in err


def test_damaged_project_file(capsys, pawn_copy):
    (pawn_copy / "project.json").write_text("{not json", encoding="utf-8")
    code, _, err = run(capsys, "check", str(pawn_copy))
    assert code == 2
    assert "damaged" in err


@pytest.mark.parametrize(
    "file, content, command",
    [
        ("project.json", b"[]", "build"),
        ("project.json", b"[]", "check"),
        ("project.json", b"\xff\xfe", "check"),
        ("build.json", b"{nope", "check"),
        ("build.json", b"{nope", "export"),
        ("build.json", b"{nope", "render"),
        ("build.json", b'{"shape": [1, 2]}', "check"),
        ("design.npz", b"junk", "build"),
        ("design.npz", b"junk", "ops"),
        ("design.npz", b"junk", "render"),
        ("design.npz", b"", "build"),
        ("design.json", b'{"details": 5}', "build"),
        ("design.json", b'{"details": [{"nonsense": 1}]}', "build"),
    ],
)
def test_damaged_files_in_a_project(capsys, pawn_copy, file, content, command):
    (pawn_copy / file).write_bytes(content)
    extra = [json.dumps(PAINT)] if command == "ops" else []
    code, out, err = run(capsys, command, str(pawn_copy), *extra)
    assert code == 2, out + err
    assert err.startswith("Error: ")
    assert "damaged" in err
    assert file in err
    if file == "build.json":
        assert "bricksnap build" in err


def test_name_too_long_to_be_a_file(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "check", "x" * 300)
    assert code == 2
    assert err.startswith("Error: Cannot find a project")


# ---- build and check ----------------------------------------------------------------------


def test_build_writes_everything_and_returns_0_when_ok(capsys, pawn_copy):
    for name in ("build.json", "build.ldr", "renders/compare.png"):
        (pawn_copy / name).unlink()
    code, out, _ = run(capsys, "build", str(pawn_copy))
    assert code == 0
    for name in ("build.json", "build.ldr", "renders/compare.png"):
        assert (pawn_copy / name).is_file(), name
    assert 'Rebuilt "pawn"' in out
    assert "OK:" in out
    assert "compare.png" in out


def test_build_returns_1_when_the_build_fails_its_checks(capsys, pawn_copy):
    assert run(capsys, "ops", str(pawn_copy), json.dumps(SPLIT))[0] == 0
    code, out, _ = run(capsys, "build", str(pawn_copy))
    assert code == 1
    assert "NOT BUILDABLE" in out
    assert "do NOT hold together" in out
    report = Project(pawn_copy).load_build().report
    assert report is not None and report.ok is False


def test_check_returns_1_for_a_failing_build_and_refreshes_the_report(capsys, pawn_copy):
    build = Project(pawn_copy).load_build()
    assert build.report is not None
    build.report.ok = True
    build.report.text = "stale"
    build.parts = build.parts[: len(build.parts) // 2] + build.parts[-3:]  # break it
    Project(pawn_copy).save_build(build)
    code, out, _ = run(capsys, "check", str(pawn_copy))
    assert code == 1
    assert out.startswith("NOT BUILDABLE")
    saved = Project(pawn_copy).load_build().report
    assert saved is not None and saved.ok is False and saved.text != "stale"


def test_check_keeps_which_design_the_build_came_from(capsys, pawn_copy):
    project = Project(pawn_copy)
    made_from = project.load_build().design_id
    assert made_from and project.build_is_current()
    code, out, _ = run(capsys, "check", str(pawn_copy))
    assert code == 0
    assert "edited since" not in out
    assert Project(pawn_copy).load_build().design_id == made_from


def test_check_says_when_the_design_was_edited_after_the_build(capsys, pawn_copy):
    assert run(capsys, "ops", str(pawn_copy), json.dumps(SPLIT))[0] == 0  # edit, no rebuild
    assert not Project(pawn_copy).build_is_current()
    code, out, _ = run(capsys, "check", str(pawn_copy))
    assert code == 0  # the old build is still a good build
    assert "edited since these bricks were built" in out
    assert not Project(pawn_copy).build_is_current()  # a check never makes it look fresh


def test_check_before_any_build(capsys, tmp_path, pawn_path):
    project = create_project(pawn_path, studs=int(STUDS), directory=tmp_path)
    code, _, err = run(capsys, "check", str(project.path))
    assert code == 2
    assert "has not been built yet" in err


# ---- render and export --------------------------------------------------------------------


def test_render_writes_the_default_picture(capsys, pawn_copy):
    (pawn_copy / "renders" / "compare.png").unlink()
    code, out, _ = run(capsys, "render", str(pawn_copy))
    assert code == 0
    assert (pawn_copy / "renders" / "compare.png").is_file()
    assert str(pawn_copy / "renders" / "compare.png") in out


def test_render_to_another_file(capsys, pawn_copy, tmp_path):
    out_file = tmp_path / "pictures" / "pawn.png"
    code, out, _ = run(capsys, "render", str(pawn_copy), "--out", str(out_file))
    assert code == 0
    assert out_file.read_bytes().startswith(b"\x89PNG")
    assert str(out_file) in out
    assert sorted(p.name for p in (pawn_copy / "renders").iterdir()) == ["compare.png"]


def test_render_refuses_a_non_png_file(capsys, pawn_copy, tmp_path):
    code, _, err = run(capsys, "render", str(pawn_copy), "--out", str(tmp_path / "pawn.jpg"))
    assert code == 2
    assert ".png" in err


def test_render_to_a_place_that_cannot_be_written(capsys, pawn_copy, tmp_path):
    afile = tmp_path / "afile"
    afile.write_text("not a folder", encoding="utf-8")
    code, _, err = run(capsys, "render", str(pawn_copy), "--out", str(afile / "pawn.png"))
    assert code == 2
    assert err.startswith("Error: ")
    assert "afile" in err
    # the temporary picture is not left behind
    assert sorted(p.name for p in (pawn_copy / "renders").iterdir()) == ["compare.png"]


def test_export_writes_the_ldraw_file(capsys, pawn_copy):
    (pawn_copy / "build.ldr").unlink()
    code, out, _ = run(capsys, "export", str(pawn_copy))
    assert code == 0
    text = (pawn_copy / "build.ldr").read_text(encoding="utf-8")
    assert text.startswith("0 pawn\n")
    assert sum(line.startswith("1 ") for line in text.splitlines()) == len(
        Project(pawn_copy).load_build().parts
    )
    assert str(pawn_copy / "build.ldr") in out


def test_export_before_any_build(capsys, tmp_path, pawn_path):
    project = create_project(pawn_path, studs=int(STUDS), directory=tmp_path)
    code, _, err = run(capsys, "export", str(project.path))
    assert code == 2
    assert "bricksnap build" in err


# ---- ops ----------------------------------------------------------------------------------


def test_ops_from_a_file(capsys, pawn_copy, tmp_path):
    ops_file = tmp_path / "edits.json"
    ops_file.write_text(json.dumps(PAINT), encoding="utf-8")
    build_before = (pawn_copy / "build.json").read_text()
    code, out, _ = run(capsys, "ops", str(pawn_copy), str(ops_file))
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("1. Done. ")
    assert "Saved the design (1 of 1 operations applied)." in out
    assert "bricksnap build" in out  # tells the user the bricks are not rebuilt yet
    assert log_length(pawn_copy) == 1
    assert (Project(pawn_copy).load_design().colors[:, :, :3] == 4).any()
    assert (pawn_copy / "build.json").read_text() == build_before


def test_ops_from_standard_input(capsys, pawn_copy, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(PAINT)))
    code, out, _ = run(capsys, "ops", str(pawn_copy), "-")
    assert code == 0
    assert out.startswith("1. Done. ")
    assert log_length(pawn_copy) == 1


def test_ops_typed_on_the_command_line_and_wrapped_forms(capsys, pawn_copy):
    assert run(capsys, "ops", str(pawn_copy), json.dumps(PAINT[0]))[0] == 0
    assert run(capsys, "ops", str(pawn_copy), json.dumps({"ops": SPLIT}))[0] == 0
    assert log_length(pawn_copy) == 2


def test_ops_with_build_rebuilds(capsys, pawn_copy):
    code, out, _ = run(capsys, "ops", str(pawn_copy), json.dumps(PAINT), "--build")
    assert code == 0
    assert "OK:" in out
    build = Project(pawn_copy).load_build()
    assert any(p.color == 4 for p in build.parts)


def test_ops_with_build_returns_1_when_the_result_fails(capsys, pawn_copy):
    code, out, _ = run(capsys, "ops", str(pawn_copy), json.dumps(SPLIT), "--build")
    assert code == 1
    assert "NOT BUILDABLE" in out


def test_ops_that_are_rejected_do_not_save_and_return_1(capsys, pawn_copy):
    bad = [
        {
            "op": "paint",
            "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]},
            "color": 99999,
        }
    ]
    design_before = (pawn_copy / "design.npz").read_bytes()
    code, out, _ = run(capsys, "ops", str(pawn_copy), json.dumps(bad))
    assert code == 1
    assert out.startswith("1. ")
    assert "99999" in out
    assert "not saved" in out
    assert (pawn_copy / "design.npz").read_bytes() == design_before
    assert log_length(pawn_copy) == 0


def test_ops_mixed_applied_and_rejected(capsys, pawn_copy):
    ops = PAINT + [{"op": "explode"}]
    code, out, _ = run(capsys, "ops", str(pawn_copy), json.dumps(ops))
    assert code == 1
    assert "1. Done. " in out
    assert "\n2. " in out
    assert "1 of 2 operations applied" in out
    assert log_length(pawn_copy) == 1


@pytest.mark.parametrize(
    "text, expected",
    [
        ('[{"op": paint}]', "not valid JSON"),
        ("[]", "is empty"),
        ("5", "should be a list"),
        ("   ", "it is empty"),
    ],
)
def test_ops_with_bad_input_in_a_file(capsys, pawn_copy, tmp_path, text, expected):
    ops_file = tmp_path / "edits.json"
    ops_file.write_text(text, encoding="utf-8")
    code, out, err = run(capsys, "ops", str(pawn_copy), str(ops_file))
    assert code == 2
    assert err.startswith("Error: ")
    assert expected in err
    assert log_length(pawn_copy) == 0


def test_ops_bad_json_on_standard_input(capsys, pawn_copy, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{oops"))
    code, _, err = run(capsys, "ops", str(pawn_copy), "-")
    assert code == 2
    assert "standard input" in err
    assert "not valid JSON" in err


def test_ops_file_that_does_not_exist(capsys, pawn_copy, tmp_path):
    code, _, err = run(capsys, "ops", str(pawn_copy), str(tmp_path / "missing.json"))
    assert code == 2
    assert "Cannot find the file" in err


def test_ops_file_that_is_not_text(capsys, pawn_copy, tmp_path):
    binary = tmp_path / "edits.json"
    binary.write_bytes(b"\xff\xfe\x00\x81")
    code, _, err = run(capsys, "ops", str(pawn_copy), str(binary))
    assert code == 2
    assert "not a text file" in err


def test_ops_long_list_typed_on_the_command_line(capsys, pawn_copy):
    typed = json.dumps(PAINT_4)
    assert len(typed) > 255  # longer than a file name can be
    code, out, _ = run(capsys, "ops", str(pawn_copy), typed)
    assert code == 0, out
    assert "4 of 4 operations applied" in out
    assert log_length(pawn_copy) == 4


def test_ops_inline_text_that_is_also_a_file_name_reads_the_file(
    capsys, pawn_copy, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "[x]").write_text(json.dumps(PAINT_4[:2]), encoding="utf-8")
    code, out, _ = run(capsys, "ops", str(pawn_copy), "[x]")
    assert code == 0
    assert "2 of 2 operations applied" in out


def test_ops_file_with_a_byte_order_mark(capsys, pawn_copy, tmp_path):
    ops_file = tmp_path / "edits.json"
    ops_file.write_bytes(b"\xef\xbb\xbf" + json.dumps(PAINT).encode("utf-8"))
    code, out, err = run(capsys, "ops", str(pawn_copy), str(ops_file))
    assert code == 0, err
    assert out.startswith("1. Done. ")


def test_ops_standard_input_with_a_byte_order_mark(capsys, pawn_copy, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("﻿" + json.dumps(PAINT)))
    code, out, err = run(capsys, "ops", str(pawn_copy), "-")
    assert code == 0, err
    assert out.startswith("1. Done. ")


# ---- design (with a fake designer) --------------------------------------------------------


class FakeDesigner:
    def __init__(self, capsys, result: DesignerRun, ops: list | None = None) -> None:
        self.capsys = capsys
        self.result = result
        self.ops = ops
        self.calls: list[tuple[Project, dict]] = []
        self.said_before_start = ""

    def __call__(self, project: Project, **options) -> DesignerRun:
        self.said_before_start = self.capsys.readouterr().out
        self.calls.append((project, options))
        if self.ops is not None:  # edit the design like the AI would, without rebuilding
            from bricksnap.catalog import load_catalog
            from bricksnap.design import apply_ops

            design = project.load_design()
            apply_ops(design, self.ops, load_catalog())
            project.save_design(design)
        return self.result


def _transcript(project_path: Path) -> Path:
    path = project_path / "designer" / "20260101T000000Z.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    return path


def test_design_warns_first_then_reports_and_rebuilds(capsys, pawn_copy, monkeypatch):
    transcript = _transcript(pawn_copy)
    fake = FakeDesigner(
        capsys,
        DesignerRun(
            ok=True,
            transcript=transcript,
            # a real run records the names as the model's stream gives them, with a prefix
            tools_called=[
                TOOL_PREFIX + name for name in ("describe", "render", "apply_ops", "render")
            ],
            turns=6,
            final_text="Painted the base red.\nIt now reads as a chess piece.",
        ),
        ops=PAINT,
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy))
    assert code == 0
    before = fake.said_before_start
    assert "sends pictures" in before
    assert "AI provider" in before
    assert "Nothing else in BrickSnap sends anything" in before
    assert fake.calls[0][0].path == pawn_copy
    assert fake.calls[0][1] == {}  # runner defaults are used when no option is given
    assert "after 6 turns" in out
    assert "4 times: describe (1), render (2), apply_ops (1)" in out
    assert "mcp__" not in out
    assert "  Painted the base red.\n  It now reads as a chess piece." in out
    assert "Rebuilding from the final design" in out
    assert "The build is valid afterwards" in out
    assert str(transcript) in out
    # the build now reflects the AI's edit
    assert any(p.color == 4 for p in Project(pawn_copy).load_build().parts)


def test_design_passes_options_through(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(
        capsys,
        "design",
        str(pawn_copy),
        "--instruction",
        "Make the head round",
        "--model",
        "some-model",
        "--effort",
        "low",
    )
    assert code == 0
    assert fake.calls[0][1] == {
        "instruction": "Make the head round",
        "model": "some-model",
        "effort": "low",
    }
    assert "did not use any of its tools" in out
    assert "Rebuilding" not in out  # nothing changed, so the saved build is reported
    assert "The build is valid afterwards" in out


def test_design_that_fails_returns_1(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(
        capsys, DesignerRun(ok=False, error="Claude Code is not installed on this computer.")
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy))
    assert code == 1
    assert "did not finish: Claude Code is not installed" in out


def test_design_that_leaves_a_broken_build_returns_1(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(
        capsys, DesignerRun(ok=True, turns=3, tools_called=["apply_ops"]), ops=SPLIT
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy))
    assert code == 1
    assert "NOT valid afterwards" in out
    assert "NOT BUILDABLE" in out


def test_design_on_a_folder_that_is_not_a_project_never_starts(capsys, tmp_path, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    (tmp_path / "empty").mkdir()
    code, out, err = run(capsys, "design", str(tmp_path / "empty"))
    assert code == 2
    assert fake.calls == []
    assert "sends pictures" not in out


def test_design_interrupted(capsys, pawn_copy, monkeypatch):
    def interrupted(project, **options):
        raise KeyboardInterrupt

    monkeypatch.setattr("bricksnap.designer.runner.run_designer", interrupted)
    code, _, err = run(capsys, "design", str(pawn_copy))
    assert code == 130
    assert "Stopped" in err


def test_design_rebuilds_when_check_made_an_old_build_look_new(capsys, pawn_copy, monkeypatch):
    # The design is edited but not rebuilt; 'check' then re-saves the old (good) build.
    assert run(capsys, "ops", str(pawn_copy), json.dumps(SPLIT))[0] == 0
    assert run(capsys, "check", str(pawn_copy))[0] == 0
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))  # changes nothing
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy))
    assert code == 1
    assert "NOT valid afterwards" in out
    assert "NOT BUILDABLE" in out
    report = Project(pawn_copy).load_build().report
    assert report is not None and report.ok is False


def test_design_rebuilds_when_the_build_file_time_is_in_the_future(capsys, pawn_copy, monkeypatch):
    # A clock that is stepped back leaves build.json with a time later than the design save.
    build_file = pawn_copy / "build.json"
    future = build_file.stat().st_mtime_ns + 3600 * 10**9
    os.utime(build_file, ns=(future, future))
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=2), ops=SPLIT)
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy))
    assert code == 1
    assert "Rebuilding from the final design" in out
    assert "NOT valid afterwards" in out


def test_design_does_not_mention_a_record_that_was_never_written(capsys, pawn_copy, monkeypatch):
    missing = pawn_copy / "designer" / "20260101T000000Z.jsonl"
    fake = FakeDesigner(
        capsys, DesignerRun(ok=False, error="Claude Code is not installed.", transcript=missing)
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy))
    assert code == 1
    assert "full record" not in out
    assert str(missing) not in out


# ---- view (with a fake server) ------------------------------------------------------------


def test_view_serves_the_project(capsys, in_projects, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "bricksnap.viewserver.serve",
        lambda path, port, open_browser: calls.append((Path(path), port, open_browser)),
    )
    assert run(capsys, "view", "pawn", "--port", "9123", "--no-open")[0] == 0
    assert calls == [(Path("projects/pawn"), 9123, False)]
    assert run(capsys, "view", "pawn")[0] == 0
    assert calls[1][1:] == (8765, True)


def test_view_reports_server_problems_plainly(capsys, pawn_copy, monkeypatch):
    def busy(path, port, open_browser):
        raise ProjectError("Port 8765 is already in use. Try another with --port.")

    monkeypatch.setattr("bricksnap.viewserver.serve", busy)
    code, _, err = run(capsys, "view", str(pawn_copy))
    assert code == 2
    assert err.startswith("Error: Port 8765 is already in use")


@pytest.mark.parametrize("port", ["99999", "-1", "eighty"])
def test_view_with_a_port_out_of_range(capsys, pawn_copy, monkeypatch, port):
    calls = []
    monkeypatch.setattr("bricksnap.viewserver.serve", lambda *a, **k: calls.append(a))
    code, _, err = run(capsys, "view", str(pawn_copy), "--port", port, "--no-open")
    assert code == 2
    assert err.startswith("Error: ")
    assert "65535" in err
    assert calls == []


def test_view_reports_a_system_error_plainly(capsys, pawn_copy, monkeypatch):
    def denied(path, port, open_browser):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("bricksnap.viewserver.serve", denied)
    code, _, err = run(capsys, "view", str(pawn_copy), "--port", "80", "--no-open")
    assert code == 2
    assert err.startswith("Error: ")
    assert "Permission denied" in err


# ---- the command itself -------------------------------------------------------------------


def test_no_command_prints_help_and_returns_2(capsys):
    code, out, _ = run(capsys)
    assert code == 2
    for command in (
        "new",
        "build",
        "check",
        "render",
        "export",
        "bench",
        "ops",
        "design",
        "view",
    ):
        assert command in out


def test_help_returns_0(capsys):
    code, out, _ = run(capsys, "--help")
    assert code == 0
    assert "usage: bricksnap" in out


def test_unknown_command(capsys):
    code, _, err = run(capsys, "paint")
    assert code == 2
    assert err.startswith("Error: ")


def test_module_runs_as_a_program():
    result = subprocess.run(
        [sys.executable, "-m", "bricksnap.cli", "build", "no-such-project-here"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert result.stderr.startswith("Error: Cannot find a project")
    assert "Traceback" not in result.stderr


# ---- stage 2: notes and weak spots in new and build ---------------------------------------
# The make-buildable and finishing passes and the renderer are written by others, so these
# tests replace pipeline.rebuild and pipeline.render_compare with fakes that save a Build
# made by hand. They pass whether or not those modules exist yet.

PNG = b"\x89PNG\r\n\x1a\n"
NOTES = [
    "Added a 2 x 4 plate under the tail at x=3, y=8, z=6 so it holds on.",
    "Could not fit a slope at x=1, y=0, z=12; left the studs there.",
]


@pytest.fixture(scope="module")
def unbuilt_pawn(tmp_path_factory, pawn_path) -> Path:
    """A pawn project with a design but no build, made once; copy it with ``bare_pawn``."""
    return create_project(pawn_path, studs=int(STUDS), directory=tmp_path_factory.mktemp("u")).path


@pytest.fixture
def bare_pawn(unbuilt_pawn, tmp_path) -> Path:
    dest = tmp_path / "work" / "pawn"
    shutil.copytree(unbuilt_pawn, dest)
    return dest


def columns_build(notes: list[str] | None = None) -> Build:
    """A good build with eight weak spots: eight columns of three 1 x 1 bricks, each on one
    stud of a 2 x 8 brick. The report is made by the real checks."""
    parts = [Placement("3007", 15, 0, 0, 0)]
    for x in (0, 2, 4, 6):
        for y in (0, 1):
            parts += [Placement("3005", 4, x, y, z) for z in (3, 6, 9)]
    build = Build(shape=(8, 2, 12), parts=parts, notes=list(notes or []))
    build.report = check(build, load_catalog())
    return build


def report_build(report: Report, notes: list[str] | None = None) -> Build:
    return Build(
        shape=(1, 1, 3),
        parts=[Placement("3005", 4, 0, 0, 0)],
        report=report,
        notes=list(notes or []),
    )


def fake_pipeline(monkeypatch, build: Build) -> list[dict]:
    """Make rebuild save ``build`` and render_compare write a tiny picture; returns the
    render calls."""
    renders: list[dict] = []

    def rebuild(project, *, catalog=None):
        build.design_id = project.load_design().fingerprint()
        project.save_build(build)
        return build

    def render_compare(project, *, catalog=None, name=None, rough=False, views=None):
        out = project.renders_dir / (name or ("compare-rough.png" if rough else "compare.png"))
        out.write_bytes(PNG)
        renders.append({"name": name, "rough": rough})
        return out

    monkeypatch.setattr("bricksnap.pipeline.rebuild", rebuild)
    monkeypatch.setattr("bricksnap.pipeline.render_compare", render_compare)
    return renders


def test_build_prints_the_notes_before_the_report(capsys, bare_pawn, monkeypatch):
    fake_pipeline(monkeypatch, columns_build(NOTES))
    code, out, _ = run(capsys, "build", str(bare_pawn))
    assert code == 0
    heading = out.index("What the software changed by itself:")
    assert out.index(f"  - {NOTES[0]}\n  - {NOTES[1]}\n") > heading
    assert heading < out.index("Check report:") < out.index("OK: 25 parts")


def test_build_without_notes_has_no_notes_heading(capsys, bare_pawn, monkeypatch):
    fake_pipeline(monkeypatch, columns_build([]))
    code, out, _ = run(capsys, "build", str(bare_pawn))
    assert code == 0
    assert "changed by itself" not in out


def test_build_shows_three_weak_spots_and_says_check_lists_them_all(capsys, bare_pawn, monkeypatch):
    build = columns_build()
    spots = build.report.weak_spots if build.report else []
    assert len(spots) == 8
    fake_pipeline(monkeypatch, build)
    code, out, _ = run(capsys, "build", str(bare_pawn))
    assert code == 0
    assert "8 weak spots to strengthen" in out
    for spot in spots[:3]:
        assert f"- {spot}\n" in out
    for spot in spots[3:]:
        assert spot not in out
    assert f"- and 5 more weak spots; 'uv run bricksnap check {bare_pawn}' lists them all." in out
    # check prints every one of them
    code, out, _ = run(capsys, "check", str(bare_pawn))
    assert code == 0
    for spot in spots:
        assert f"- {spot}\n" in out
    assert "more weak spots;" not in out


def test_new_shows_notes_and_only_three_weak_spots(capsys, tmp_path, pawn_path, monkeypatch):
    build = columns_build(NOTES)
    spots = build.report.weak_spots if build.report else []
    fake_pipeline(monkeypatch, build)
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(capsys, "new", str(pawn_path), "--studs", STUDS)
    assert code == 0
    assert out.index("What the software changed by itself:") < out.index("Check report:")
    assert f"  - {NOTES[1]}" in out
    assert spots[2] in out and spots[3] not in out
    assert "- and 5 more weak spots; 'uv run bricksnap check pawn' lists them all." in out


def test_build_with_more_weak_spots_than_the_report_lists(capsys, bare_pawn, monkeypatch):
    spots = [f"Weak spot number {i} at x={i}, y=0, z=3." for i in range(1, 11)]
    text = "\n".join(
        [
            "NOT BUILDABLE: 40 parts; it would tip over.",
            "It would tip over: widen the base.",
            "14 weak spots to strengthen (they do not fail the checks on their own):",
            *(f"- {s}" for s in spots),
            "- and 4 less serious weak spots not listed.",
        ]
    )
    report = Report(ok=False, part_count=40, weak_spots=spots, text=text)
    fake_pipeline(monkeypatch, report_build(report))
    code, out, _ = run(capsys, "build", str(bare_pawn))
    assert code == 1
    assert "It would tip over: widen the base." in out  # the problems are all kept
    assert "Weak spot number 3 " in out and "Weak spot number 4 " not in out
    assert "not listed" not in out
    assert "- and 11 more weak spots; " in out
    assert "lists the 10 most serious." in out


def test_build_with_three_weak_spots_shows_them_all(capsys, bare_pawn, monkeypatch):
    spots = ["First.", "Second.", "Third."]
    text = "OK: 9 parts in one connected piece; it stands.\n3 weak spots to strengthen:\n"
    text += "\n".join(f"- {s}" for s in spots)
    fake_pipeline(monkeypatch, report_build(Report(ok=True, weak_spots=spots, text=text)))
    code, out, _ = run(capsys, "build", str(bare_pawn))
    assert code == 0
    assert "- First.\n- Second.\n- Third.\n" in out
    assert "more weak spot" not in out


def test_one_more_weak_spot_is_singular(capsys, bare_pawn, monkeypatch):
    spots = ["A.", "B.", "C.", "D."]
    text = "OK: 9 parts.\n4 weak spots to strengthen:\n" + "\n".join(f"- {s}" for s in spots)
    fake_pipeline(monkeypatch, report_build(Report(ok=True, weak_spots=spots, text=text)))
    code, out, _ = run(capsys, "build", str(bare_pawn))
    assert "- and 1 more weak spot; " in out
    assert "- D." not in out


# ---- stage 2: render --rough --------------------------------------------------------------


def test_render_rough_draws_three_rows_into_its_own_file(capsys, bare_pawn, monkeypatch):
    renders = fake_pipeline(monkeypatch, columns_build())
    code, out, _ = run(capsys, "render", str(bare_pawn), "--rough")
    assert code == 0
    assert renders == [{"name": "compare-rough.png", "rough": True}]
    assert str(bare_pawn / "renders" / "compare-rough.png") in out
    assert "Middle row: the plain conversion" in out


def test_render_rough_to_another_file(capsys, bare_pawn, monkeypatch, tmp_path):
    renders = fake_pipeline(monkeypatch, columns_build())
    target = tmp_path / "pics" / "rough.png"
    code, out, _ = run(capsys, "render", str(bare_pawn), "--rough", "--out", str(target))
    assert code == 0
    assert renders[0]["rough"] is True
    assert target.read_bytes() == PNG
    assert not (bare_pawn / "renders" / ".render-out.png").exists()


def test_render_without_rough_asks_for_two_rows(capsys, bare_pawn, monkeypatch):
    renders = fake_pipeline(monkeypatch, columns_build())
    code, out, _ = run(capsys, "render", str(bare_pawn))
    assert code == 0
    assert renders == [{"name": "compare.png", "rough": False}]
    assert "Middle row" not in out


def test_render_rough_says_the_bottom_row_is_the_design_before_any_build(
    capsys, bare_pawn, monkeypatch
):
    fake_pipeline(monkeypatch, columns_build())  # bare_pawn has no build.json
    code, out, _ = run(capsys, "render", str(bare_pawn), "--rough")
    assert code == 0
    assert "Bottom row: the design, not built into bricks yet." in out
    assert f"uv run bricksnap build {bare_pawn}" in out
    assert "the brick version" not in out
    code, out, _ = run(capsys, "render", str(bare_pawn))
    assert code == 0
    assert "Bottom row: the design, not built into bricks yet." in out
    assert "the brick version" not in out


def test_render_rough_after_a_build_says_the_bottom_row_is_the_bricks(
    capsys, pawn_copy, monkeypatch
):
    fake_pipeline(monkeypatch, columns_build())
    code, out, _ = run(capsys, "render", str(pawn_copy), "--rough")
    assert code == 0
    assert "Bottom row: the brick version as it is now." in out
    assert "not built into bricks yet" not in out


def test_render_rough_with_a_damaged_base_design(capsys, pawn_copy):
    (pawn_copy / "design.base.npz").write_text("junk", encoding="utf-8")
    (pawn_copy / "build.rough.json").unlink(missing_ok=True)
    code, _, err = run(capsys, "render", str(pawn_copy), "--rough")
    assert code == 2
    assert err.startswith("Error: ")
    assert "design.base.npz" in err and "is damaged" in err
    assert "pickle" not in err
    # the plain picture does not need the base design
    assert run(capsys, "render", str(pawn_copy))[0] == 0


def test_render_rough_without_a_base_design(capsys, pawn_copy):
    (pawn_copy / "design.base.npz").unlink()
    code, _, err = run(capsys, "render", str(pawn_copy), "--rough")
    assert code == 2
    assert "has no base design yet" in err


def test_render_rough_with_the_real_renderer(capsys, pawn_copy):
    """Through the real pipeline and renderer: three rows, so a taller picture."""
    from PIL import Image

    code, out, err = run(capsys, "render", str(pawn_copy), "--rough")
    assert code == 0, err
    rough = pawn_copy / "renders" / "compare-rough.png"
    plain = pawn_copy / "renders" / "compare.png"
    assert (pawn_copy / "build.rough.json").is_file()
    with Image.open(rough) as three, Image.open(plain) as two:
        assert three.height > two.height


# ---- stage 2: export ----------------------------------------------------------------------


def _line(part, name, colour, colour_name, quantity, bl_id="", bl_colour=None) -> PartLine:
    return PartLine(
        part=part,
        bricklink_id=bl_id or part,
        name=name,
        colour=colour,
        colour_name=colour_name,
        bricklink_colour=bl_colour,
        quantity=quantity,
    )


LINES = [
    _line("3007", "Brick 2 x 8", 15, "White", 1, bl_colour=1),
    _line("3005", "Brick 1 x 1", 4, "Red", 24, bl_colour=5),
    _line("99999", "unknown part", 4, "Red", 2, bl_id="-"),
]


@pytest.fixture
def fake_export(monkeypatch):
    """Replace bricksnap.export's functions; returns the projects write_exports was given."""
    calls: list[Project] = []

    def write_exports(project, catalog=None):
        calls.append(project)
        (project.path / "parts.csv").write_text("Part\n", encoding="utf-8")
        (project.path / "wanted_list.xml").write_text("<INVENTORY/>", encoding="utf-8")
        return {
            "parts": project.path / "parts.csv",
            "wanted_list": project.path / "wanted_list.xml",
        }

    monkeypatch.setattr("bricksnap.export.write_exports", write_exports)
    monkeypatch.setattr("bricksnap.export.parts_list", lambda build, catalog: list(LINES))
    monkeypatch.setattr(
        "bricksnap.export.unlisted", lambda lines: [ln for ln in lines if ln.part == "99999"]
    )
    return calls


def _save_current_build(project_path: Path) -> None:
    project = Project(project_path)
    build = columns_build()
    build.design_id = project.load_design().fingerprint()
    project.save_build(build)


def test_export_writes_the_lists_and_says_how_to_buy(capsys, bare_pawn, fake_export):
    _save_current_build(bare_pawn)
    code, out, err = run(capsys, "export", str(bare_pawn))
    assert code == 0, err
    assert [p.path for p in fake_export] == [bare_pawn]
    assert (bare_pawn / "build.ldr").is_file()
    assert str(bare_pawn / "build.ldr") in out
    assert str(bare_pawn / "parts.csv") in out
    assert str(bare_pawn / "wanted_list.xml") in out
    assert "27 parts of 3 different kinds" in out
    assert "Wanted, then Upload" in out
    assert "paste it" in out
    assert "2 parts are not on the wanted list" in out
    assert "  - 2 x Red unknown part (part 99999)" in out
    assert "edited since" not in out


def test_export_with_every_part_listed(capsys, bare_pawn, fake_export, monkeypatch):
    monkeypatch.setattr("bricksnap.export.unlisted", lambda lines: [])
    _save_current_build(bare_pawn)
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert code == 0
    assert "Every part is on the wanted list." in out
    assert "not on the wanted list" not in out


def test_export_one_part_not_listed_is_singular(capsys, bare_pawn, fake_export, monkeypatch):
    one = _line("99999", "unknown part", 4, "Red", 1, bl_id="-")
    monkeypatch.setattr("bricksnap.export.parts_list", lambda build, catalog: [one])
    monkeypatch.setattr("bricksnap.export.unlisted", lambda lines: [one])
    _save_current_build(bare_pawn)
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert "1 part of 1 different kind " in out
    assert "Buy it by hand" in out  # it is the only part, so there is nothing to upload
    # with another part that can go on the wanted list
    listed = _line("3005", "Brick 1 x 1", 4, "Red", 2, bl_colour=5)
    monkeypatch.setattr("bricksnap.export.parts_list", lambda build, catalog: [listed, one])
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert "1 part is not on the wanted list" in out
    assert "Add it by hand" in out


def test_export_warns_when_the_design_changed_after_the_build(capsys, bare_pawn, fake_export):
    Project(bare_pawn).save_build(columns_build())  # records no design, so it is out of date
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert code == 0
    assert "the design has been edited since these bricks were built" in out
    assert f"bricksnap build {bare_pawn}" in out


def test_export_with_the_real_lists(capsys, bare_pawn):
    """The real bricksnap.export, once it exists (skipped while it is still a stub)."""
    _save_current_build(bare_pawn)
    try:
        code, out, err = run(capsys, "export", str(bare_pawn))
    except NotImplementedError:
        pytest.skip("bricksnap.export is not written yet")
    assert code == 0, err
    assert (bare_pawn / "parts.csv").is_file() and (bare_pawn / "wanted_list.xml").is_file()
    assert "25 parts of 2 different kinds" in out


def _edit_saved_build(project_path: Path, change) -> None:
    """Save a good, current build, then change its build.json by hand with ``change``."""
    _save_current_build(project_path)
    path = project_path / "build.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_export_with_a_part_and_a_colour_not_in_the_parts_table(capsys, bare_pawn):
    """The real bricksnap.export: an unknown part cannot go into the LDraw file, but the
    lists are still written and the parts that need buying by hand are named."""

    def change(data):
        data["parts"][1]["part"] = "99999"  # a 1 x 1 brick becomes a part nobody knows
        data["parts"][2]["color"] = 999  # and another one gets a colour nobody knows

    _edit_saved_build(bare_pawn, change)
    code, out, err = run(capsys, "export", str(bare_pawn))
    assert code == 1, err
    assert not (bare_pawn / "build.ldr").exists()
    assert "Could not write the LDraw file" in out
    assert "The part '99999' is not in BrickSnap's parts table" in out
    assert (bare_pawn / "parts.csv").is_file() and (bare_pawn / "wanted_list.xml").is_file()
    assert "2 parts are not on the wanted list" in out
    assert "  - 1 x Red unknown part (part 99999)" in out
    assert "  - 1 x Brick 1 x 1 (part 3005) in unknown colour 999" in out
    assert "Wanted, then Upload" in out  # the other parts can still be uploaded


def test_export_with_a_part_not_in_the_parts_table_keeps_an_older_ldraw_file(capsys, bare_pawn):
    (bare_pawn / "build.ldr").write_text("0 older\n", encoding="utf-8")
    _edit_saved_build(bare_pawn, lambda data: data["parts"][0].update(part="99999"))
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert code == 1
    assert (bare_pawn / "build.ldr").read_text(encoding="utf-8") == "0 older\n"
    assert "build.ldr was left as it was" in out


@pytest.mark.parametrize("colour", ["red", None, 4.5])
def test_export_with_a_colour_that_is_not_a_number(capsys, bare_pawn, colour):
    _edit_saved_build(bare_pawn, lambda data: data["parts"][0].update(color=colour))
    code, out, err = run(capsys, "export", str(bare_pawn))
    assert code == 2
    assert err.startswith("Error: The build file ")
    assert "is damaged" in err
    assert "LDraw colour code is a whole number" in err  # what is wrong, from export
    assert f"bricksnap build {bare_pawn}" in err
    assert "invalid literal" not in err and "NoneType" not in err
    assert not (bare_pawn / "parts.csv").exists() and not (bare_pawn / "build.ldr").exists()


def test_export_of_a_build_with_no_parts(capsys, bare_pawn):
    _edit_saved_build(bare_pawn, lambda data: data.update(parts=[]))
    code, out, err = run(capsys, "export", str(bare_pawn))
    assert code == 0, err
    assert "has no parts, so there is nothing to buy" in out
    assert "Wanted, then Upload" not in out
    assert "Every part is on the wanted list" not in out


def test_export_where_no_part_can_go_on_the_wanted_list(
    capsys, bare_pawn, fake_export, monkeypatch
):
    monkeypatch.setattr("bricksnap.export.unlisted", lambda lines: list(lines))
    _save_current_build(bare_pawn)
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert code == 0
    assert "Wanted, then Upload" not in out
    assert "None of the parts can go on the BrickLink wanted list" in out
    assert "nothing to upload" in out
    assert "  - 24 x Red Brick 1 x 1 (part 3005)" in out
    assert "Every part is on the wanted list" not in out


def test_export_counts_one_part_in_two_colours_as_two_kinds(
    capsys, bare_pawn, fake_export, monkeypatch
):
    lines = [
        _line("3005", "Brick 1 x 1", 4, "Red", 10, bl_colour=5),
        _line("3005", "Brick 1 x 1", 1, "Blue", 6, bl_colour=7),
    ]
    monkeypatch.setattr("bricksnap.export.parts_list", lambda build, catalog: list(lines))
    _save_current_build(bare_pawn)
    code, out, _ = run(capsys, "export", str(bare_pawn))
    assert code == 0
    assert "16 parts of 2 different kinds" in out


# ---- stage 2: bench -----------------------------------------------------------------------


class FakeBench:
    def __init__(self, rows: list[Row]) -> None:
        self.rows = rows
        self.calls: list[dict] = []
        self.compared: list[tuple[list[Row], list[Row]]] = []

    def run_bench(self, models_dir, out_dir, studs=16, catalog=None, names=None):
        self.calls.append(
            {"models": Path(models_dir), "out": Path(out_dir), "studs": studs, "names": names}
        )
        return [r for r in self.rows if names is None or r.name in names]

    def compare(self, old, new):
        self.compared.append((old, new))
        return "cat: parts went down from 120 to 110."


@pytest.fixture
def bench_dir(tmp_path, monkeypatch) -> Path:
    """Run from tmp_path, which holds samples/models with three (empty) model files."""
    models = tmp_path / "samples" / "models"
    models.mkdir(parents=True)
    for name in ("cat.glb", "duck.glb", "pawn.stl", "README.md"):
        (models / name).write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def use_bench(monkeypatch, rows: list[Row]) -> FakeBench:
    fake = FakeBench(rows)
    monkeypatch.setattr("bricksnap.bench.run_bench", fake.run_bench)
    monkeypatch.setattr("bricksnap.bench.compare", fake.compare)
    monkeypatch.setattr(
        "bricksnap.bench.format_table",
        lambda rows: "| model | parts |\n" + "".join(f"| {r.name} | {r.parts} |\n" for r in rows),
    )
    return fake


GOOD_ROWS = [
    Row("cat", ok=True, parts=110),
    Row("duck", ok=True, parts=80),
    Row("pawn", ok=True, parts=60),
]


def test_bench_runs_every_model_and_prints_the_table(capsys, bench_dir, monkeypatch):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    code, out, err = run(capsys, "bench")
    assert code == 0, err
    assert fake.calls == [
        {"models": Path("samples/models"), "out": Path("bench"), "studs": 16, "names": None}
    ]
    assert "Building 3 test models at 16 studs" in out
    assert "| cat | 110 |" in out
    assert "Nothing to compare with yet; run with --save to keep this result." in out
    assert "bench/scorecard.md" in out
    assert "Result: all 3 models built with no loose parts." in out
    assert not (bench_dir / "samples" / "scorecard.json").exists()


def test_bench_options_are_passed_through(capsys, bench_dir, monkeypatch, tmp_path):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    other = tmp_path / "elsewhere"
    code, out, _ = run(capsys, "bench", "--studs", "12", "--out", str(other), "duck", "cat")
    assert code == 0
    assert fake.calls[0]["studs"] == 12
    assert fake.calls[0]["out"] == other
    assert fake.calls[0]["names"] == ["duck", "cat"]
    assert "Building 2 test models at 12 studs" in out
    assert "| pawn |" not in out


def test_bench_returns_1_when_a_model_has_loose_parts_or_fails(capsys, bench_dir, monkeypatch):
    rows = [
        Row("cat", ok=False, parts=110, loose=3),
        Row("duck", error="The model file duck.glb is damaged."),
        Row("pawn", ok=True, parts=60),
    ]
    use_bench(monkeypatch, rows)
    code, out, _ = run(capsys, "bench")
    assert code == 1
    assert "Could not be built:\n  - duck: The model file duck.glb is damaged." in out
    assert "Result: 2 of 3 models could not be built or have loose parts: cat, duck." in out


def test_bench_ok_false_without_loose_parts_still_returns_0(capsys, bench_dir, monkeypatch):
    use_bench(monkeypatch, [Row("cat", ok=False, parts=110, loose=0)])
    assert run(capsys, "bench", "cat")[0] == 0


def test_bench_save_then_compare(capsys, bench_dir, monkeypatch):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    code, out, _ = run(capsys, "bench", "--save")
    assert code == 0
    saved = json.loads((bench_dir / "samples" / "scorecard.json").read_text(encoding="utf-8"))
    assert saved["studs"] == 16
    assert [r["name"] for r in saved["rows"]] == ["cat", "duck", "pawn"]
    assert saved["rows"][0]["parts"] == 110
    assert "Saved this result as the scorecard" in out
    assert fake.compared == []  # there was nothing to compare with before saving

    code, out, _ = run(capsys, "bench", "cat")
    assert code == 0
    old, new = fake.compared[-1]
    assert [r.name for r in old] == ["cat"]  # only the models that were run
    assert old[0] == Row("cat", ok=True, parts=110)
    assert [r.name for r in new] == ["cat"]
    assert "Compared with the saved scorecard (samples/scorecard.json):" in out
    assert "cat: parts went down from 120 to 110." in out


def test_bench_save_for_some_models_keeps_the_others(capsys, bench_dir, monkeypatch):
    use_bench(monkeypatch, GOOD_ROWS)
    assert run(capsys, "bench", "--save")[0] == 0
    use_bench(monkeypatch, [Row("duck", ok=True, parts=70)])
    assert run(capsys, "bench", "--save", "duck")[0] == 0
    saved = json.loads((bench_dir / "samples" / "scorecard.json").read_text(encoding="utf-8"))
    assert {r["name"]: r["parts"] for r in saved["rows"]} == {"cat": 110, "duck": 70, "pawn": 60}


def test_bench_does_not_compare_different_sizes(capsys, bench_dir, monkeypatch):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    scorecard = bench_dir / "samples" / "scorecard.json"
    scorecard.write_text(json.dumps({"studs": 24, "rows": [{"name": "cat"}]}), encoding="utf-8")
    code, out, _ = run(capsys, "bench")
    assert code == 0
    assert fake.compared == []
    assert "made at 24 studs and this run is at 16" in out


def test_bench_with_a_damaged_scorecard(capsys, bench_dir, monkeypatch):
    use_bench(monkeypatch, GOOD_ROWS)
    (bench_dir / "samples" / "scorecard.json").write_text("{nope", encoding="utf-8")
    code, out, _ = run(capsys, "bench")
    assert code == 0
    assert "samples/scorecard.json is damaged" in out
    assert "--save to replace it" in out
    assert "Nothing to compare with yet" not in out


@pytest.mark.parametrize(
    "content, reason",
    [
        ('{"studs": 16, "rows": [{"parts": 3}]}', "row 1 has no model name"),
        ('{"studs": 16, "rows": ["cat"]}', "row 1 has no model name"),
        ('{"studs": 16, "rows": [{"name": ""}]}', "row 1 has no model name"),
        ('{"studs": 16, "rows": [{"name": "cat", "parts": "many"}]}', 'row 1 (cat) has "many"'),
        ('{"studs": 16, "rows": [{"name": "cat", "ok": 1}]}', "row 1 (cat) has 1 for ok"),
        ('{"studs": 16, "rows": [{"name": "cat", "parts": true}]}', "row 1 (cat) has true"),
        ('{"studs": 16, "rows": [{"name": "cat", "error": null}]}', "row 1 (cat) has null"),
        ('{"studs": "16", "rows": []}', "the size it was made at is not a whole number"),
        ('{"rows": {"name": "cat"}}', "it holds no list of rows"),
        ("7", "it holds no list of rows"),
        ("<<<<<<< HEAD\n[]\n=======\n[]\n>>>>>>> theirs\n", "it is not valid JSON"),
        (b"\xff\xfe\x00", "it is not a text file"),
    ],
)
def test_bench_scorecard_damage_is_explained_plainly(
    capsys, bench_dir, monkeypatch, content, reason
):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    scorecard = bench_dir / "samples" / "scorecard.json"
    if isinstance(content, bytes):
        scorecard.write_bytes(content)
    else:
        scorecard.write_text(content, encoding="utf-8")
    code, out, err = run(capsys, "bench")
    assert code == 0, err
    assert (
        f"The saved scorecard samples/scorecard.json is damaged and cannot be read: {reason}" in out
    )
    for python_words in ("__init__", "positional", "attribute", "codec", "Expecting"):
        assert python_words not in out
    assert fake.compared == []


def test_bench_scorecard_accepts_whole_numbers_for_shares(capsys, bench_dir, monkeypatch):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    rows = [{"name": "cat", "shaped": 1, "seconds": 2.5, "ok": True}]
    (bench_dir / "samples" / "scorecard.json").write_text(
        json.dumps({"studs": 16, "rows": rows}), encoding="utf-8"
    )
    assert run(capsys, "bench")[0] == 0
    assert fake.compared[0][0] == [Row("cat", ok=True, shaped=1, seconds=2.5)]


def test_bench_save_for_some_models_at_another_size_replaces_the_scorecard(
    capsys, bench_dir, monkeypatch
):
    use_bench(monkeypatch, GOOD_ROWS)
    assert run(capsys, "bench", "--save")[0] == 0
    use_bench(monkeypatch, [Row("duck", ok=True, parts=300)])
    code, out, _ = run(capsys, "bench", "--studs", "24", "--save", "duck")
    assert code == 0
    assert "The old scorecard was made at 16 studs, so it is replaced, not added to." in out
    saved = json.loads((bench_dir / "samples" / "scorecard.json").read_text(encoding="utf-8"))
    assert saved["studs"] == 24
    assert [(r["name"], r["parts"]) for r in saved["rows"]] == [("duck", 300)]


def test_bench_with_no_rows_returns_1(capsys, bench_dir, monkeypatch):
    use_bench(monkeypatch, [])
    code, out, _ = run(capsys, "bench")
    assert code == 1
    assert "Result: 0 of 0 models" in out or "Result: no model" in out
    assert "built with no loose parts" not in out


def test_bench_reads_a_scorecard_that_is_a_bare_list(capsys, bench_dir, monkeypatch):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    rows = [{"name": "cat", "parts": 120, "something_new": 1}]
    (bench_dir / "samples" / "scorecard.json").write_text(json.dumps(rows), encoding="utf-8")
    assert run(capsys, "bench")[0] == 0
    assert fake.compared[0][0] == [Row("cat", parts=120)]


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["bench", "dragon"], "There is no model called dragon in samples/models. The models"),
        (["bench", "--studs", "200"], "between 4 and 96"),
        (["bench", "--models", "nowhere"], "Cannot find the folder of test models nowhere"),
        (["bench", "--studs", "many"], "invalid int value"),
    ],
)
def test_bench_mistakes(capsys, bench_dir, monkeypatch, argv, expected):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    code, _, err = run(capsys, *argv)
    assert code == 2
    assert err.startswith("Error: ")
    assert expected in err
    assert fake.calls == []


def test_bench_lists_the_models_when_a_name_is_wrong(capsys, bench_dir, monkeypatch):
    use_bench(monkeypatch, GOOD_ROWS)
    _, _, err = run(capsys, "bench", "dragon")
    assert "The models are: cat, duck, pawn." in err


def test_bench_with_an_empty_models_folder(capsys, tmp_path, monkeypatch):
    use_bench(monkeypatch, GOOD_ROWS)
    (tmp_path / "empty").mkdir()
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "bench", "--models", "empty")
    assert code == 2
    assert "There are no model files in empty" in err


def test_bench_out_that_is_a_file(capsys, bench_dir, monkeypatch):
    fake = use_bench(monkeypatch, GOOD_ROWS)
    (bench_dir / "bench").write_text("x", encoding="utf-8")
    code, _, err = run(capsys, "bench")
    assert code == 2
    assert "is a file, not a folder" in err
    assert fake.calls == []


# ---- stage 2: the designer's brief --------------------------------------------------------

BRIEF = {
    "object": "A chess pawn, facing the front.",
    "features": ["round head", "wide base"],
    "plan": "Make the head a little bigger.",
    "colours": [15, 0, 99999],
    "finish": "Smooth on the head, studs on the base.",
}


def _write_brief(project: Project, brief) -> None:
    project.meta["brief"] = brief
    project.save_meta()


def test_design_shows_the_brief_before_its_closing_text(capsys, bare_pawn, monkeypatch):
    fake_pipeline(monkeypatch, columns_build())

    def designer(project, **options):
        _write_brief(Project(project.path), BRIEF)  # as the brief tool does, mid-run
        return DesignerRun(ok=True, turns=2, final_text="All done.")

    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    code, out, _ = run(capsys, "design", str(bare_pawn))
    assert code == 0
    brief = out.index("The designer's brief:")
    assert brief < out.index("What the designer said at the end:")
    assert "  What it is: A chess pawn, facing the front.\n" in out
    assert "  What makes it recognisable:\n    - round head\n    - wide base\n" in out
    assert "  The plan: Make the head a little bigger.\n" in out
    assert "  Colours: White, Black, colour 99999\n" in out
    assert "  Surfaces: Smooth on the head, studs on the base.\n" in out


def test_design_without_a_brief_has_no_brief_heading(capsys, bare_pawn, monkeypatch):
    fake_pipeline(monkeypatch, columns_build())
    monkeypatch.setattr(
        "bricksnap.designer.runner.run_designer",
        lambda project, **o: DesignerRun(ok=True, turns=1, final_text="Nothing to do."),
    )
    code, out, _ = run(capsys, "design", str(bare_pawn))
    assert code == 0
    assert "The designer's brief" not in out


def test_design_shows_a_brief_that_is_plain_text(capsys, bare_pawn, monkeypatch):
    fake_pipeline(monkeypatch, columns_build())
    _write_brief(Project(bare_pawn), "Make it look like a pawn.")
    monkeypatch.setattr(
        "bricksnap.designer.runner.run_designer",
        lambda project, **o: DesignerRun(ok=True, turns=1),
    )
    code, out, _ = run(capsys, "design", str(bare_pawn))
    assert code == 0
    assert "The designer's brief:\n  Make it look like a pawn.\n" in out


def test_design_skips_missing_brief_fields(capsys, bare_pawn, monkeypatch):
    fake_pipeline(monkeypatch, columns_build())
    _write_brief(Project(bare_pawn), {"object": "A pawn.", "colours": 4, "features": []})
    monkeypatch.setattr(
        "bricksnap.designer.runner.run_designer",
        lambda project, **o: DesignerRun(ok=True, turns=1),
    )
    code, out, _ = run(capsys, "design", str(bare_pawn))
    assert code == 0
    assert "  What it is: A pawn.\n  Colours: Red\n" in out
    assert "recognisable" not in out and "The plan" not in out


def test_ops_with_build_shows_notes_and_a_short_report(capsys, bare_pawn, monkeypatch):
    build = columns_build(NOTES)
    spots = build.report.weak_spots if build.report else []
    fake_pipeline(monkeypatch, build)
    code, out, _ = run(capsys, "ops", str(bare_pawn), json.dumps(PAINT), "--build")
    assert code == 0
    assert out.index("What the software changed by itself:") < out.index("Check report:")
    assert spots[2] in out and spots[3] not in out
    assert "- and 5 more weak spots; " in out


def test_design_shows_notes_and_a_short_report(capsys, bare_pawn, monkeypatch):
    build = columns_build(NOTES)
    spots = build.report.weak_spots if build.report else []
    fake_pipeline(monkeypatch, build)
    monkeypatch.setattr(
        "bricksnap.designer.runner.run_designer",
        lambda project, **o: DesignerRun(ok=True, turns=1),
    )
    code, out, _ = run(capsys, "design", str(bare_pawn))
    assert code == 0
    notes = out.index("What the software changed by itself:")
    assert notes < out.index("The build is valid afterwards:")
    assert spots[2] in out and spots[3] not in out
    assert "- and 5 more weak spots; " in out


# ---- stage 3: a typed edit ----------------------------------------------------------------

SMOOTH_TOP = [
    {
        "op": "set_finish",
        "shape": {"type": "box", "min": [0, 0, 0], "max": [9, 9, 25]},
        "finish": "smooth",
    }
]


def designed(project_path: Path) -> Path:
    """Give the project a brief, as a first design run would have."""
    _write_brief(Project(project_path), {**BRIEF, "colours": [15, 0]})
    return project_path


def part_count(project_path: Path) -> int:
    return len(Project(project_path).load_build().parts)


def with_earlier_ops(project_path: Path) -> Path:
    """Leave one operation in the design's log and rebuild, as a first design run would."""
    from bricksnap.design import apply_ops

    project = Project(project_path)
    design = project.load_design()
    # black, higher up than the paints the tests' designers make, so theirs still change
    black = {"op": "paint", "shape": {"type": "box", "min": [0, 0, 15], "max": [9, 9, 17]}}
    apply_ops(design, [{**black, "color": 0}], load_catalog())
    project.save_design(design)
    rebuild(project)
    assert log_length(project_path) == 1
    return project_path


def test_design_takes_the_request_as_a_second_argument(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, _, _ = run(capsys, "design", str(designed(pawn_copy)), "add a red collar")
    assert code == 0
    assert fake.calls[0][1] == {"instruction": "add a red collar"}


def test_design_refuses_a_request_given_twice(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, err = run(
        capsys, "design", str(pawn_copy), "add a red collar", "--instruction", "add a hat"
    )
    assert code == 2
    assert fake.calls == []
    assert "sends pictures" not in out
    assert "Error:" in err and "--instruction" in err and "once" in err


@pytest.mark.parametrize("empty", ["", "   "])
def test_design_refuses_an_empty_request(capsys, pawn_copy, monkeypatch, empty):
    fake = FakeDesigner(capsys, DesignerRun(ok=True))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, _, err = run(capsys, "design", str(pawn_copy), empty)
    assert code == 2
    assert fake.calls == []
    assert "Error:" in err and "empty" in err


def test_a_first_design_says_so_before_it_starts(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    run(capsys, "design", str(pawn_copy))
    assert "first design" in fake.said_before_start
    assert "one change" not in fake.said_before_start


def test_a_first_design_with_a_wish_quotes_it(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    run(capsys, "design", str(pawn_copy), "give it a little blue bow tie")
    before = fake.said_before_start
    assert "first design" in before and '"give it a little blue bow tie"' in before


def test_an_edit_says_so_before_it_starts_and_quotes_the_request(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    run(capsys, "design", str(designed(pawn_copy)), "--instruction", "add a red collar")
    before = fake.said_before_start
    assert "one change" in before and "already designed" in before
    assert '"add a red collar"' in before
    assert "first design" not in before
    assert "sends pictures" in before  # the privacy warning is still given first


def test_a_designed_model_without_a_request_gets_a_full_pass(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    run(capsys, "design", str(designed(pawn_copy)))
    assert "full design pass" in fake.said_before_start
    assert "one change" not in fake.said_before_start


def test_an_edit_reports_what_changed_from_the_project(capsys, pawn_copy, monkeypatch):
    with_earlier_ops(designed(pawn_copy))  # an edit follows a first pass that left a log
    parts_before = part_count(pawn_copy)
    log_before = log_length(pawn_copy)
    fake = FakeDesigner(
        capsys,
        DesignerRun(ok=True, turns=4, kind="edit", final_text="Painted the base red."),
        ops=PAINT_4 + SMOOTH_TOP,
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy), "paint it in stripes")
    assert code == 0
    assert log_length(pawn_copy) == log_before + 5
    summary = out[out.index("What this change did:") :]
    assert "5 edit operations" in summary and "6 edit operations" not in summary
    assert "4 painting" in summary and "1 changing the surface finish" in summary
    assert "5 painting" not in summary  # the earlier paint is not this run's
    assert f"Parts: {parts_before:,} before, {part_count(pawn_copy):,} after." in summary
    assert "The build is valid." in summary
    assert "The brief was kept as it was." in summary
    # the next step offered is another change, not a full pass over the whole model
    after = out[out.index("What to do next:") :]
    assert f'design {pawn_copy} "' in after and "one more change" in after


def test_next_steps_offer_a_full_design_before_there_is_a_brief(capsys, pawn_copy, monkeypatch):
    monkeypatch.setattr(
        "bricksnap.designer.runner.run_designer",
        FakeDesigner(capsys, DesignerRun(ok=True, turns=1)),
    )
    code, out, _ = run(capsys, "design", str(pawn_copy))
    after = out[out.index("What to do next:") :]
    assert "one more change" not in after and "improve how it looks" in after


def test_an_edit_that_breaks_the_build_says_so(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=2, kind="edit"), ops=SPLIT)
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(designed(pawn_copy)), "add a little box")
    assert code == 1
    summary = out[out.index("What this change did:") :]
    assert "1 edit operation (1 adding cells)" in summary
    assert "The build is NOT valid" in summary


def test_an_edit_that_changed_the_brief_says_so(capsys, pawn_copy, monkeypatch):
    designed(pawn_copy)

    def designer(project, **options):
        _write_brief(Project(project.path), {**BRIEF, "colours": [15, 0, 4]})
        return DesignerRun(ok=True, turns=2, kind="edit")

    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    code, out, _ = run(capsys, "design", str(pawn_copy), "make it red")
    assert "The designer updated the brief" in out[out.index("What this change did:") :]


def test_an_edit_without_any_operation_says_no_change_and_why(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(
        capsys,
        DesignerRun(ok=True, turns=2, kind="edit", final_text="The pawn already has a collar."),
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    project = with_earlier_ops(designed(pawn_copy))  # the log is not empty before the run
    code, out, _ = run(capsys, "design", str(project), "add a collar")
    summary = out[out.index("What this change did:") :]
    assert "The designer made no change to the design." in summary
    assert "The pawn already has a collar." in summary
    assert "edit operation" not in summary


def test_an_edit_without_any_operation_or_reason(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=2, kind="edit"))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(designed(pawn_copy)), "add a collar")
    assert code == 0
    summary = out[out.index("What this change did:") :]
    assert "The designer made no change to the design, and it did not say why." in summary


@pytest.mark.parametrize("last_words", ["Let me look at the model first.", ""])
def test_an_edit_whose_run_stopped_before_any_change_says_so(
    capsys, pawn_copy, monkeypatch, last_words
):
    """A run that crashed, timed out or was stopped: its last remark is not a reason."""
    error = "Claude Code stopped with an error (exit code 3): network went away"
    fake = FakeDesigner(
        capsys, DesignerRun(ok=False, turns=1, kind="edit", error=error, final_text=last_words)
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(designed(pawn_copy)), "add a red collar")
    assert code == 1
    summary = out[out.index("What this change did:") :]
    assert "The run stopped before the designer changed anything" in summary
    assert "network went away" in summary
    assert "said why" not in summary and "did not say why" not in summary
    if last_words:
        assert last_words not in summary


def test_an_edit_whose_run_stopped_partway_says_the_change_may_be_unfinished(
    capsys, pawn_copy, monkeypatch
):
    fake = FakeDesigner(
        capsys, DesignerRun(ok=False, turns=3, kind="edit", error="It timed out."), ops=PAINT
    )
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(designed(pawn_copy)), "paint the base red")
    assert code == 1
    summary = out[out.index("What this change did:") :]
    assert "1 edit operation (1 painting)" in summary
    assert "stopped before it finished" in summary and "only partly made" in summary


def test_an_edit_counts_parts_before_from_the_design_not_an_old_build(
    capsys, pawn_copy, monkeypatch
):
    """A saved build made from an older design, or by an older BrickSnap, is not "before"."""
    designed(pawn_copy)
    fresh = part_count(pawn_copy)
    _edit_saved_build(pawn_copy, lambda data: data.update(parts=data["parts"][:3]))
    assert part_count(pawn_copy) == 3
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=2, kind="edit", final_text="No."))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy), "add a collar")
    assert code == 0
    summary = out[out.index("What this change did:") :]
    assert f"Parts: {fresh:,} before, {fresh:,} after." in summary


def test_an_edit_on_a_project_that_was_never_built_counts_parts_before(
    capsys, pawn_copy, monkeypatch
):
    designed(pawn_copy)
    fresh = part_count(pawn_copy)
    (pawn_copy / "build.json").unlink()
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=2, kind="edit"), ops=PAINT)
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy), "paint the base red")
    assert code == 0
    summary = out[out.index("What this change did:") :]
    assert f"Parts: {fresh:,} before, {part_count(pawn_copy):,} after." in summary
    assert "none before" not in summary


def test_an_edit_on_a_project_with_a_damaged_build_still_runs(capsys, pawn_copy, monkeypatch):
    """The build is made again from the design before the run, so a damaged one is replaced."""
    designed(pawn_copy)
    fresh = part_count(pawn_copy)
    (pawn_copy / "build.json").write_text("{nope", encoding="utf-8")
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=2, kind="edit", final_text="No."))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy), "add a collar")
    assert code == 0 and fake.calls
    assert f"Parts: {fresh:,} before, {fresh:,} after." in out


@pytest.mark.parametrize(
    ("words", "suggested"),
    [
        (["add", "a", "red", "collar"], '"add a red collar"'),
        (["make", "it", "-", "smaller"], '"make it - smaller"'),
        (["-smaller"], '--instruction="-smaller"'),
        (["-make", "it", "smaller"], '--instruction="-make it smaller"'),
    ],
)
def test_a_request_typed_without_quotes_is_explained(
    capsys, pawn_copy, monkeypatch, words, suggested
):
    fake = FakeDesigner(capsys, DesignerRun(ok=True))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, err = run(capsys, "design", str(designed(pawn_copy)), *words)
    assert code == 2
    assert fake.calls == [] and "sends pictures" not in out
    assert "Error:" in err and "quotes" in err
    assert f"design {pawn_copy} {suggested}" in err
    assert "usage:" not in err and "unrecognized arguments" not in err


def test_an_unknown_option_to_design_is_still_argparse_s_message(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, _, err = run(capsys, "design", str(pawn_copy), "add a hat", "--studs", "16")
    assert code == 2 and fake.calls == []
    assert "unrecognized arguments: --studs 16" in err


def test_left_over_words_on_another_command_are_still_argparse_s_message(capsys, pawn_copy):
    code, _, err = run(capsys, "check", str(pawn_copy), "now")
    assert code == 2
    assert "Error: unrecognized arguments: now" in err


def test_a_first_design_has_no_change_summary(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1), ops=PAINT)
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy), "make it red")
    assert code == 0
    assert "What this change did:" not in out


# ---- stage 3: design PROJECT --best-of N ---------------------------------------------------


class FakeCandidates:
    """Designs candidate N with ``plans[N]`` (operations, or "fail"), like the AI would."""

    def __init__(self, capsys, plans: dict[int, object]) -> None:
        self.capsys = capsys
        self.plans = plans
        self.calls: list[tuple[Path, dict]] = []
        self.said_before_start = ""

    def __call__(self, project: Project, **options) -> DesignerRun:
        from bricksnap.design import apply_ops

        if not self.calls:
            self.said_before_start = self.capsys.readouterr().out
        self.calls.append((project.path, options))
        plan = self.plans.get(int(project.path.name), PAINT)
        if plan == "fail":
            return DesignerRun(ok=False, error="Claude Code is not installed here.")
        assert isinstance(plan, list)
        project.meta["brief"] = {**BRIEF, "object": f"Design {project.path.name}."}
        project.save_meta()
        design = project.load_design()
        apply_ops(design, plan, load_catalog())
        project.save_design(design)
        return DesignerRun(ok=True, turns=4)


class FakeJudgeRun:
    """A judge that looks at every candidate through the real tools and ranks the letters
    in reverse order (or in order)."""

    def __init__(self, prefer_last: bool = True, ok: bool = True) -> None:
        self.prefer_last = prefer_last
        self.ok = ok
        self.calls: list[dict] = []

    def __call__(self, folder: Path, letters: list[str], **options) -> DesignerRun:
        from bricksnap.designer.judge_server import Judging

        self.calls.append({"letters": list(letters), **options})
        tools = Judging(folder)
        for letter in letters:
            tools.call("look", {"candidate": letter})
        order = list(reversed(letters)) if self.prefer_last else list(letters)
        tools.call(
            "choose",
            {
                "ranking": order,
                "reasons": {x: f"Candidate {x} has the clearest head." for x in order},
                "summary": "It was close between the first two.",
            },
        )
        error = "" if self.ok else "The judge did not finish within 20 minutes."
        return DesignerRun(ok=self.ok, error=error)


def fake_judge(prefer_last: bool = True, ok: bool = True) -> FakeJudgeRun:
    return FakeJudgeRun(prefer_last, ok)


RED, BLUE, YELLOW = PAINT, [{**PAINT[0], "color": 1}], [{**PAINT[0], "color": 14}]


def test_best_of_says_how_many_runs_first_then_reports_the_ranking(capsys, pawn_copy, monkeypatch):
    designer = FakeCandidates(capsys, {1: RED, 2: BLUE, 3: YELLOW})
    judge = fake_judge()
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", judge)
    code, out, _ = run(capsys, "design", str(pawn_copy), "--best-of", "3", "--effort", "low")
    assert code == 0, out
    before = designer.said_before_start
    assert "4 AI runs" in before and "3 designs" in before and "one judging run" in before
    assert "sends pictures" in before and "AI provider" in before
    assert "minutes" in before
    assert [p.name for p, _ in designer.calls] == ["1", "2", "3"]
    assert all(o["effort"] == "low" for _, o in designer.calls)
    assert judge.calls[0]["effort"] == "low"

    saved = json.loads((pawn_copy / "candidates" / "result.json").read_text())
    winner = saved["winner"]
    rows = {c["number"]: c for c in saved["candidates"]}
    assert rows[winner]["rank"] == 1
    assert "chosen by the judge" in out.lower()
    assert f"Kept design {winner}" in out
    for n in (1, 2, 3):
        assert f"Design {n} (shown to the judge as {rows[n]['letter']})" in out
        assert f"Candidate {rows[n]['letter']} has the clearest head." in out
    assert "It was close between the first two." in out
    assert "candidates" in out and "result.json" in out
    assert "The build is valid afterwards" in out
    assert Project(pawn_copy).meta["brief"]["object"] == f"Design {winner}."


def test_best_of_1_is_the_same_as_leaving_it_out(capsys, pawn_copy, monkeypatch):
    fake = FakeDesigner(capsys, DesignerRun(ok=True, turns=1))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, _ = run(capsys, "design", str(pawn_copy), "--best-of", "1")
    assert code == 0
    assert len(fake.calls) == 1 and fake.calls[0][0].path == pawn_copy
    assert fake.calls[0][1] == {}
    assert not (pawn_copy / "candidates").exists()
    assert "judge" not in out.lower()


@pytest.mark.parametrize("value", ["0", "6", "-2", "three"])
def test_best_of_out_of_range_is_a_mistake(capsys, pawn_copy, monkeypatch, value):
    fake = FakeDesigner(capsys, DesignerRun(ok=True))
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", fake)
    code, out, err = run(capsys, "design", str(pawn_copy), "--best-of", value)
    assert code == 2 and fake.calls == []
    assert "sends pictures" not in out
    assert "1 to 5" in err


def test_best_of_falls_back_to_measurement_and_says_so(capsys, pawn_copy, monkeypatch):
    designer = FakeCandidates(capsys, {1: RED, 2: BLUE})
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge(ok=False))
    code, out, _ = run(capsys, "design", str(pawn_copy), "--best-of", "2")
    assert code == 0
    assert "chosen by measurement" in out
    assert "did not finish within 20 minutes" in out
    assert "outline" in out


def test_best_of_with_a_failed_design_lists_it(capsys, pawn_copy, monkeypatch):
    designer = FakeCandidates(capsys, {1: "fail", 2: BLUE, 3: YELLOW})
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge())
    code, out, _ = run(capsys, "design", str(pawn_copy), "--best-of", "3")
    assert code == 0
    assert "Design 1 could not be used" in out and "not installed" in out


def test_best_of_with_no_usable_design_returns_1_and_keeps_the_project(
    capsys, pawn_copy, monkeypatch
):
    before = (pawn_copy / "design.npz").read_bytes()
    designer = FakeCandidates(capsys, {1: "fail", 2: SPLIT})
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge())
    code, out, _ = run(capsys, "design", str(pawn_copy), "--best-of", "2")
    assert code == 1
    assert "None of the 2 designs" in out
    assert (pawn_copy / "design.npz").read_bytes() == before


def test_judge_again_is_hidden_and_judges_the_candidates_on_disk(capsys, pawn_copy, monkeypatch):
    designer = FakeCandidates(capsys, {1: RED, 2: BLUE})
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge(prefer_last=True))
    assert run(capsys, "design", str(pawn_copy), "--best-of", "2")[0] == 0
    first = json.loads((pawn_copy / "candidates" / "result.json").read_text())["winner"]
    designer.calls.clear()
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge(prefer_last=False))
    code, out, _ = run(capsys, "design", str(pawn_copy), "--judge-again")
    assert code == 0 and designer.calls == []
    assert "one AI run" in out
    second = json.loads((pawn_copy / "candidates" / "result.json").read_text())["winner"]
    assert {first, second} == {1, 2}
    assert f"Kept design {second}" in out
    assert "--judge-again" not in run(capsys, "design", "--help")[1]


def test_best_of_with_a_typed_change_on_a_designed_model(capsys, pawn_copy, monkeypatch):
    project = Project(pawn_copy)
    project.meta["brief"] = BRIEF
    project.save_meta()
    log_before = log_length(pawn_copy)
    designer = FakeCandidates(capsys, {1: RED, 2: BLUE})
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge())
    code, out, _ = run(capsys, "design", str(pawn_copy), "make the base red", "--best-of", "2")
    assert code == 0, out
    before = designer.said_before_start
    assert "This is one change" in before and '"make the base red"' in before
    assert "3 AI runs" in before
    assert [o.get("instruction") for _, o in designer.calls] == ["make the base red"] * 2
    assert log_length(pawn_copy) == log_before + 1  # the kept design is one change further on
    assert Project(pawn_copy).build_is_current()


def test_judge_again_without_designs_starts_nothing(capsys, pawn_copy, monkeypatch):
    judge = fake_judge()
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", judge)
    code, out, err = run(capsys, "design", str(pawn_copy), "--judge-again")
    assert code == 1 and judge.calls == []
    assert "no designs to judge" in out + err
    assert "AI run" not in out and "to look at" not in out


DIE_AT_MOVE = """
import os, sys
from pathlib import Path
from bricksnap.designer import judge
from bricksnap.project import Project

project, k = Path(sys.argv[1]), int(sys.argv[2])
real, count = judge._move, [0]

def dying(src, dst):
    count[0] += 1
    if count[0] == k:
        os._exit(9)
    real(src, dst)

judge._move = dying
judge._keep(Project(project), project / "candidates" / "2")
"""


def test_opening_a_project_puts_back_a_best_of_that_died_half_way(capsys, pawn_copy, monkeypatch):
    designer = FakeCandidates(capsys, {1: RED, 2: BLUE})
    monkeypatch.setattr("bricksnap.designer.runner.run_designer", designer)
    monkeypatch.setattr("bricksnap.designer.judge.run_judge", fake_judge(prefer_last=False))
    assert run(capsys, "design", str(pawn_copy), "--best-of", "2")[0] == 0
    saved = json.loads((pawn_copy / "candidates" / "result.json").read_text())
    assert saved["winner"] == 1

    def files() -> dict[str, bytes]:
        return {
            str(f.relative_to(pawn_copy)): f.read_bytes()
            for f in sorted(pawn_copy.rglob("*"))
            if f.is_file() and "candidates" not in f.relative_to(pawn_copy).parts
        }

    before = files()
    proc = subprocess.run(
        [sys.executable, "-c", DIE_AT_MOVE, str(pawn_copy), "3"], capture_output=True, timeout=120
    )
    assert proc.returncode == 9  # the process died with design 2 half put in place
    assert files() != before
    code, out, err = run(capsys, "check", str(pawn_copy))
    assert "put back as it was" in err  # a note, kept apart from the command's own output
    assert files() == before


def test_instructions_writes_the_booklet_and_says_where(capsys, pawn_copy):
    code, out, err = run(capsys, "instructions", str(pawn_copy))
    assert code == 0, err
    assert (pawn_copy / "instructions.pdf").stat().st_size > 10_000
    html = (pawn_copy / "instructions.html").read_text(encoding="utf-8")
    assert "<script" not in html.lower()
    steps = len({p.step for p in Project(pawn_copy).load_build().parts})
    assert f"{steps} steps" in out
    assert "instructions.pdf" in out and "instructions.html" in out
    assert "Traceback" not in out + err


def test_instructions_before_any_build(capsys, tmp_path, pawn_path):
    project = create_project(pawn_path, studs=int(STUDS), directory=tmp_path)
    code, out, err = run(capsys, "instructions", str(project.path))
    assert code == 2
    assert "bricksnap build" in err
    assert not (project.path / "instructions.pdf").exists()
    assert "Traceback" not in out + err
