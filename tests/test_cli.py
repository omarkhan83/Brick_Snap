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

from bricksnap.cli import main
from bricksnap.designer.runner import TOOL_PREFIX, DesignerRun
from bricksnap.pipeline import create_project, rebuild, render_compare
from bricksnap.project import Project, ProjectError

STUDS = "8"
# Removes three plates across the whole pawn (grid 10 x 10 x 26 at 8 studs), so the top
# floats free and the build fails its checks.
SPLIT = [{"op": "remove", "shape": {"type": "box", "min": [0, 0, 6], "max": [9, 9, 8]}}]
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
    for command in ("new", "build", "check", "render", "export", "ops", "design", "view"):
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
