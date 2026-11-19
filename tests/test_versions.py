"""Tests for bricksnap.versions: keeping, listing and bringing back versions of a project."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bricksnap import versions
from bricksnap.catalog import load_catalog
from bricksnap.design import apply_ops
from bricksnap.pipeline import create_project, rebuild, render_card
from bricksnap.project import Project, ProjectError

BRIEF = {"object": "A chess pawn.", "features": ["a round head"], "plan": "Keep it."}
PAINT = [
    {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [40, 40, 2]}, "color": 4}
]


@pytest.fixture(scope="module")
def built_pawn(tmp_path_factory, pawn_path) -> Path:
    project = create_project(pawn_path, studs=8, directory=tmp_path_factory.mktemp("versions"))
    rebuild(project)
    render_card(project)
    return project.path


@pytest.fixture
def pawn(built_pawn, tmp_path) -> Project:
    dest = tmp_path / "pawn"
    shutil.copytree(built_pawn, dest)
    return Project(dest)


def repaint(project: Project) -> None:
    design = project.load_design()
    results = apply_ops(design, PAINT, load_catalog())
    assert all(r.applied for r in results), [r.message for r in results]
    project.save_design(design)
    rebuild(project)


def test_a_project_starts_with_no_versions(pawn):
    assert versions.versions(pawn) == [] and versions.current(pawn) is None
    with pytest.raises(ProjectError, match="no version 1"):
        versions.version_dir(pawn, 1)


def test_recording_keeps_the_design_the_build_and_a_picture(pawn):
    n = versions.record(pawn, "converted", "Plain conversion, finished")
    assert n == 1 and versions.current(pawn) == 1
    (only,) = versions.versions(pawn)
    build = pawn.load_build()
    assert (only.n, only.kind, only.label, only.note) == (
        1,
        "converted",
        "Plain conversion, finished",
        "",
    )
    assert only.parts == len(build.parts) and only.valid is True and only.brief is None
    assert only.design_id == pawn.load_design().fingerprint() and only.created.endswith("Z")
    folder = versions.version_dir(pawn, 1)
    assert folder == pawn.path / "versions" / "0001"
    assert (folder / "build.json").read_bytes() == pawn.build_path.read_bytes()
    assert (folder / "design.npz").is_file() and (folder / "design.json").is_file()
    assert (folder / "card.png").read_bytes() == (pawn.renders_dir / "card.png").read_bytes()


def test_recording_the_same_state_again_adds_nothing(pawn):
    assert versions.record(pawn, "converted", "First") == 1
    rebuild(pawn)  # building again gives the same build
    assert versions.record(pawn, "manual", "Built again") == 1
    assert [v.label for v in versions.versions(pawn)] == ["First"]


def test_a_change_makes_a_new_version_and_numbers_are_never_reused(pawn):
    versions.record(pawn, "converted", "First")
    repaint(pawn)
    assert versions.record(pawn, "manual", "Red base", note="painted by hand") == 2
    assert [(v.n, v.kind, v.note) for v in versions.versions(pawn)] == [
        (1, "converted", ""),
        (2, "manual", "painted by hand"),
    ]
    shutil.rmtree(pawn.path / "versions" / "0002")
    assert [v.n for v in versions.versions(pawn)] == [1]  # a version whose folder is gone
    assert versions.current(pawn) is None
    pawn.meta["brief"] = BRIEF
    pawn.save_meta()
    assert versions.record(pawn, "designed", "Again") == 3


def test_a_new_brief_alone_is_a_new_version(pawn):
    versions.record(pawn, "converted", "First")
    pawn.meta["brief"] = BRIEF
    pawn.save_meta()
    assert versions.record(pawn, "designed", "With a brief") == 2
    assert versions.versions(pawn)[1].brief == BRIEF


def test_recording_needs_a_build_made_from_the_design(pawn, tmp_path):
    design = pawn.load_design()
    assert all(r.applied for r in apply_ops(design, PAINT, load_catalog()))
    pawn.save_design(design)  # the build is now older than the design
    with pytest.raises(ProjectError, match="build the project first"):
        versions.record(pawn, "manual", "Stale")
    pawn.build_path.unlink()
    with pytest.raises(ProjectError, match="build the project first"):
        versions.record(pawn, "manual", "No build")
    with pytest.raises(ValueError, match="unknown kind"):
        versions.record(pawn, "sketch", "x")
    assert versions.versions(pawn) == []


def test_restoring_brings_back_design_build_brief_and_picture(pawn):
    versions.record(pawn, "converted", "First")
    first_design = pawn.load_design().fingerprint()
    first_build = pawn.build_path.read_bytes()
    first_card = (pawn.renders_dir / "card.png").read_bytes()
    repaint(pawn)
    render_card(pawn)
    pawn.meta["brief"] = BRIEF
    pawn.save_meta()
    versions.record(pawn, "designed", "Red base")
    assert pawn.load_design().fingerprint() != first_design

    build = versions.restore(pawn, 1)
    again = Project(pawn.path)
    assert again.load_design().fingerprint() == first_design
    assert again.build_path.read_bytes() == first_build and build == again.load_build()
    assert again.build_is_current() and "brief" not in again.meta
    assert (again.renders_dir / "card.png").read_bytes() == first_card
    assert " 4 " not in again.ldraw_path.read_text()  # the LDraw file is the old build's
    assert versions.current(again) == 1 and len(versions.versions(again)) == 2

    versions.restore(again, 2)
    again = Project(pawn.path)
    assert again.meta["brief"] == BRIEF and versions.current(again) == 2
    assert " 4 " in again.ldraw_path.read_text()
    assert versions.record(again, "designed", "Nothing new") == 2  # restoring added nothing
    with pytest.raises(ProjectError, match="no version 9"):
        versions.restore(again, 9)


def test_a_damaged_index_is_no_versions_and_recording_starts_after_what_is_there(pawn):
    versions.record(pawn, "converted", "First")
    (pawn.path / "versions" / "index.json").write_text("{not json")
    assert versions.versions(pawn) == [] and versions.current(pawn) is None
    assert versions.record(pawn, "converted", "Again") == 2  # folder 0001 is not overwritten
    index = json.loads((pawn.path / "versions" / "index.json").read_text())
    assert index["current"] == 2 and [e["n"] for e in index["versions"]] == [2]
