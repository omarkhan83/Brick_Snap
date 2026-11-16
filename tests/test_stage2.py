"""Stage 2 from end to end: a model goes in, and what comes out looks designed and still holds.

These go through the same pipeline the command line and the AI designer's tools use. Each
module's own test file checks its details; these check that the pieces work together.
"""

from __future__ import annotations

import numpy as np
import pytest

from bricksnap.design import apply_ops
from bricksnap.pipeline import create_project, rebuild, render_compare, rough_build
from bricksnap.project import Project
from bricksnap.types import EMPTY, FINISH_SLOPED, Report

DUCK = "samples/models/duck.glb"
CAT = "samples/models/cat.glb"
PLAIN = ("brick", "plate")


def kinds(build, catalog) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in build.parts:
        kind = catalog.parts[p.part].kind
        out[kind] = out.get(kind, 0) + 1
    return out


def report_of(build) -> Report:
    assert build.report is not None, "the pipeline always checks what it builds"
    return build.report


def top_cell(design, x: int, y: int) -> int:
    """z of the highest filled cell in a column."""
    return int(np.flatnonzero(design.colors[x, y, :] != EMPTY).max())


@pytest.fixture(scope="module")
def duck(tmp_path_factory, catalog) -> Project:
    project = create_project(DUCK, studs=12, directory=tmp_path_factory.mktemp("duck"))
    rebuild(project, catalog=catalog)
    return project


def test_a_rounded_model_gets_slopes_and_still_holds(duck, catalog):
    design = duck.load_design()
    assert (design.finish == FINISH_SLOPED).sum() > 20, "the duck's rounded top should be marked"
    build = duck.load_build()
    report = report_of(build)
    assert report.ok, report.text
    assert report.loose == []
    found = kinds(build, catalog)
    assert found.get("slope", 0) + found.get("curved_slope", 0) >= 10, found
    text = duck.ldraw_path.read_text()
    assert "3040b.dat" in text or "3039.dat" in text or "54200.dat" in text


def test_the_rough_build_is_plain_and_the_finished_one_is_not(duck, catalog):
    """The rough build is the plain conversion made to hold together (the make-buildable
    pass and the layout, nothing more): bricks and plates only, and no loose parts."""
    rough = rough_build(duck, catalog=catalog)
    assert report_of(rough).ok, report_of(rough).text
    assert report_of(rough).loose == []
    assert set(kinds(rough, catalog)) <= set(PLAIN)
    assert set(kinds(duck.load_build(), catalog)) - set(PLAIN)
    picture = render_compare(duck, catalog=catalog, rough=True)
    assert picture.name == "compare-rough.png" and picture.stat().st_size > 5000


def test_tiles_and_a_detail_asked_for_by_edits_end_up_in_the_build(tmp_path, catalog):
    project = create_project(CAT, studs=12, directory=tmp_path)
    design = project.load_design()
    nx, ny, nz = design.shape
    # the cat's back: find a column in the middle of the body and tile around it
    x, y = nx // 2, ny // 2 + 2
    z = top_cell(design, x, y)
    ops = [
        {
            "op": "set_finish",
            "shape": {"type": "box", "min": [x - 1, y - 2, z], "max": [x, y + 2, z]},
            "finish": "smooth",
            "mirror": True,
        },
        {"op": "place_detail", "part": "98138", "color": 0, "at": [x, y, z + 1]},
    ]
    results = apply_ops(design, ops, catalog)
    assert all(r.applied for r in results), [r.message for r in results]
    project.save_design(design)
    build = rebuild(project, catalog=catalog)
    report = report_of(build)
    assert report.ok, report.text
    found = kinds(build, catalog)
    assert found.get("tile", 0) >= 1, found
    eyes = [p for p in build.parts if p.part == "98138"]
    assert [(p.x, p.y, p.z, p.color) for p in eyes] == [(x, y, z + 1, 0)]
    assert "98138.dat" in project.ldraw_path.read_text()


def test_a_feature_stuck_on_the_side_is_held_without_changing_the_saved_design(tmp_path, catalog):
    project = create_project(CAT, studs=12, directory=tmp_path)
    design = project.load_design()
    filled = np.argwhere(design.filled)
    front = int(filled[:, 1].min())
    # a red box one stud deep on the model's front face, in its own colour
    column = filled[filled[:, 1] == front]
    x = int(np.median(column[:, 0]))
    z = int(np.median(column[:, 2]))
    op = {
        "op": "add",
        "shape": {"type": "box", "min": [x, front - 1, z], "max": [x + 1, front - 1, z + 2]},
        "color": 4,
    }
    (result,) = apply_ops(design, [op], catalog)
    assert result.applied, result.message
    project.save_design(design)
    before = project.load_design().fingerprint()
    build = rebuild(project, catalog=catalog)
    report = report_of(build)
    assert report.ok, report.text
    assert report.components == 1
    assert any(p.color == 4 for p in build.parts)
    # the repair happened on a copy: the saved design is exactly what the edit made
    assert project.load_design().fingerprint() == before
    assert project.build_is_current()


@pytest.mark.parametrize("studs", [12, 16, 24])
def test_every_sample_model_builds_with_all_passes(tmp_path, catalog, studs):
    import pathlib

    models = sorted(
        p for p in pathlib.Path("samples/models").iterdir() if p.suffix in (".glb", ".stl")
    )
    assert len(models) >= 11
    for model in models:
        project = create_project(model, studs=studs, directory=tmp_path)
        build = rebuild(project, catalog=catalog)
        report = report_of(build)
        assert report.ok, f"{model.name}: {report.text}"
        assert report.loose == [], model.name
        for p in build.parts:
            assert catalog.exists(p.part, p.color), (model.name, p)


SYMMETRIC = {  # sample models that are mirror images of themselves, and across which axes
    "bottle.glb": (0, 1),
    "car.glb": (0,),
    "cat.glb": (0,),
    "hat.glb": (0, 1),
    "pawn.stl": (0, 1),
    "spaceship.glb": (0,),
    "star.glb": (0, 1),
}


@pytest.mark.parametrize("studs", [12, 16, 24])
def test_a_mirror_symmetric_model_gives_a_mirror_symmetric_design(tmp_path, catalog, studs):
    """The base Design of each symmetric sample model is its own mirror image: its cells,
    their colours and finish, and the partly covered cells (the skin) the make-buildable
    pass may fill."""
    for name, axes in SYMMETRIC.items():
        project = create_project(f"samples/models/{name}", studs=studs, directory=tmp_path)
        design = project.load_design(base=True)
        assert design.finish is not None and design.skin is not None
        assert (design.skin != EMPTY).any(), name
        for axis in axes:
            for grid in (design.colors, design.finish, design.skin):
                assert np.array_equal(grid, np.flip(grid, axis)), (name, studs, axis)


def test_a_colour_painted_away_does_not_come_back_through_partly_covered_cells(tmp_path, catalog):
    """The cat's whiskers, muzzle and paws are Light Bluish Grey; paint every such cell red.
    The make-buildable pass fills partly covered cells beside the whiskers, which remember
    the grey of the conversion (edits do not change the skin): they must come out in the
    colours the model has there now, not in grey."""
    grey, red = 71, 4
    project = create_project(CAT, studs=16, directory=tmp_path)
    design = project.load_design()
    ops = [
        {"op": "paint", "shape": {"type": "box", "min": cell, "max": cell}, "color": red}
        for cell in np.argwhere(design.colors == grey).tolist()
    ]
    assert ops and all(r.applied for r in apply_ops(design, ops, catalog))
    project.save_design(design)
    build = rebuild(project, catalog=catalog)
    report = report_of(build)
    assert report.ok and report.loose == [], report.text
    assert any(n.startswith("Filled") for n in build.notes)
    assert not [p for p in build.parts if p.color == grey]
    assert not [n for n in build.notes if "Light Bluish Grey" in n]


def test_partly_covered_cells_that_hold_nothing_are_taken_away_one_by_one(tmp_path, catalog):
    """The teapot at 24 studs: the tip of the spout, which rises diagonally, is held by
    filling partly covered cells beside it. Four touch it; taking away at once all that the
    build did not lean on leaves it loose (so with only that guess, all four stayed), but
    taking them away one at a time leaves two, which hold it."""
    from bricksnap.buildable import make_buildable

    project = create_project("samples/models/teapot.glb", studs=24, directory=tmp_path)
    design = project.load_design(base=True)
    assert design.skin is not None
    result = make_buildable(design, catalog)
    assert result.pieces_before > 1 and result.pieces_after == 1
    added = result.added
    assert 1 <= added.sum() <= 2
    assert (design.skin[added] != EMPTY).all()
