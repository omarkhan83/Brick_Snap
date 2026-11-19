"""Stage 1 acceptance: the "done when" of docs/ROADMAP.md, as tests.

The loose-brick cases are the ones the prototype failed: its scan-order merge left 840 of
920 bricks unattached on a solid 20x20x20 box.
"""

from __future__ import annotations

import time

import numpy as np
import pytest
import shapes

from bricksnap.checks import check
from bricksnap.connect import occupancy
from bricksnap.layout import solve
from bricksnap.types import EMPTY, SeedError

CASES = {
    "box-6x4x4": lambda: shapes.box(6, 4, 4),
    "box-12x12x4": lambda: shapes.box(12, 12, 4),
    "box-20x20x20": lambda: shapes.box(20, 20, 20),
    "cylinder-8x6": lambda: shapes.cylinder(8, 6),
    "cylinder-12x10": lambda: shapes.cylinder(12, 10),
    "cylinder-20x16": lambda: shapes.cylinder(20, 16),
    "sphere-8": lambda: shapes.sphere(8),
    "sphere-16": lambda: shapes.sphere(16),
    "sphere-24": lambda: shapes.sphere(24),
}


def assert_build_matches_design(design, build, catalog, kinds=("brick", "plate")):
    """Every filled cell is covered by exactly one part of its colour; nothing else is."""
    occ, collisions, out_of_bounds, unknown = occupancy(build, catalog)
    assert not collisions, f"{len(collisions)} pairs of parts overlap"
    assert not out_of_bounds, f"{len(out_of_bounds)} parts stick out of the grid"
    assert not unknown, f"{len(unknown)} parts are not real part and colour pairs"
    assert np.array_equal(occ >= 0, design.filled), (
        "the parts do not cover exactly the filled cells"
    )
    part_colour = np.array([p.color for p in build.parts], dtype=np.int16)
    covered = occ >= 0
    assert np.array_equal(part_colour[occ[covered]], design.colors[covered]), (
        "a part has the wrong colour"
    )
    for p in build.parts:
        assert catalog.parts[p.part].kind in kinds
        assert p.step >= 1, "every part needs a building step"


@pytest.mark.parametrize("hollow", [False, True], ids=["solid", "hollow"])
@pytest.mark.parametrize("case", list(CASES))
def test_builds_as_one_connected_piece(case, hollow, catalog):
    design = CASES[case]()
    if hollow:
        design = shapes.hollowed(design)
    build = solve(design, catalog)
    assert_build_matches_design(design, build, catalog)
    report = check(build, catalog)
    assert report.loose == [], report.text
    assert report.components == 1, report.text
    assert report.ok, report.text


def test_two_colours_build_as_one_piece(catalog):
    design = shapes.striped(shapes.cylinder(12, 8))
    build = solve(design, catalog)
    assert_build_matches_design(design, build, catalog)
    assert check(build, catalog).ok


def test_solver_is_deterministic_and_fast(catalog):
    design = shapes.box(20, 20, 20)
    start = time.perf_counter()
    first = solve(design, catalog)
    elapsed = time.perf_counter() - start
    assert elapsed < 20, f"solving 24,000 cells took {elapsed:.1f} s"
    assert solve(design, catalog).parts == first.parts
    small = sum(1 for p in first.parts if catalog.parts[p.part].sx * catalog.parts[p.part].sz <= 2)
    assert small <= len(first.parts) / 3, "too many 1x1 and 1x2 parts in a plain box"


def test_pawn_from_file_to_checked_build(tmp_path, pawn_path, catalog):
    from bricksnap.pipeline import create_project, rebuild, render_compare

    project = create_project(pawn_path, studs=16, directory=tmp_path, catalog=catalog)
    design = project.load_design()
    assert design.filled.any() and design.seed_offset == (2, 2, 0)
    build = rebuild(project, catalog=catalog)
    assert build.report is not None
    assert build.report.ok, build.report.text
    # the finishing pass may swap bricks and plates for tiles and slopes covering the same
    # cells, and for inverted slopes under the overhangs (the pawn's head has some)
    finished = ("brick", "plate", "tile", "slope", "curved_slope", "slope_inverted")
    assert_build_matches_design(design, build, catalog, kinds=finished)
    text = project.ldraw_path.read_text()
    assert text.count("\n1 ") == len(build.parts) and "0 STEP" in text
    picture = render_compare(project, catalog=catalog)
    assert picture.exists() and picture.stat().st_size > 2000


def test_flat_model_is_rejected_not_hung(tmp_path):
    """The prototype looped forever on a model with zero height."""
    from bricksnap.seed import load_seed

    flat = tmp_path / "flat.stl"
    facet = "facet normal 0 0 1\nouter loop\n{}endloop\nendfacet\n"
    tri_a = "vertex 0 0 0\nvertex 10 0 0\nvertex 10 10 0\n"
    tri_b = "vertex 0 0 0\nvertex 10 10 0\nvertex 0 10 0\n"
    flat.write_text(f"solid flat\n{facet.format(tri_a)}{facet.format(tri_b)}endsolid flat\n")
    with pytest.raises(SeedError, match="flat"):
        load_seed(flat, studs=16)


def test_empty_cells_stay_empty(catalog):
    design = shapes.hollowed(shapes.box(12, 12, 6))
    assert (design.colors == EMPTY).any()
    build = solve(design, catalog)
    assert_build_matches_design(design, build, catalog)
