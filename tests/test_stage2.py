"""Stage 2 from end to end: a model goes in, and what comes out looks designed and still holds.

These go through the same pipeline the command line and the AI designer's tools use. Each
module's own test file checks its details; these check that the pieces work together.
"""

from __future__ import annotations

import pathlib
import re

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


@pytest.mark.parametrize(
    "studs",
    [
        pytest.param(12, marks=pytest.mark.thorough),
        16,
        pytest.param(24, marks=pytest.mark.thorough),
    ],
)
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


def _visible(filled: np.ndarray) -> np.ndarray:
    """Filled cells next to air that can be reached from the four sides or the top (worked
    out here by a flood fill of its own, not by the module under test)."""
    from scipy import ndimage

    nx, ny, nz = filled.shape
    empty = np.ones((nx + 2, ny + 2, nz + 1), dtype=bool)
    empty[1:-1, 1:-1, :-1] = ~filled
    labels, _ = ndimage.label(empty)
    outside = np.isin(labels, np.unique(labels[0]))  # the x = -1 face is all padding
    air = np.zeros((nx + 2, ny + 2, nz + 2), dtype=bool)
    air[:, :, 1:] = outside  # below z = 0 is the table, not air
    near = np.zeros(filled.shape, dtype=bool)
    for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        near |= air[1 + dx : 1 + dx + nx, 1 + dy : 1 + dy + ny, 1 + dz : 1 + dz + nz]
    return filled & near


@pytest.mark.parametrize("name", ["pineapple", "spaceship", "hat"])
def test_the_worst_weak_spots_of_thin_samples_are_cured(tmp_path, catalog, name):
    """At 16 studs the pineapple's crown, the spaceship's rear engine pods and the hat's
    brim each hang on a single stud or part. The make-buildable pass gives them a second
    hold: the heaviest load of a fresh layout is lower than without its weak-spot phase,
    the model is still one piece, and the pass's guarantees hold."""
    import time

    import networkx as nx

    from bricksnap.buildable import make_buildable
    from bricksnap.connect import connection_graph, lone_links
    from bricksnap.layout import solve

    def heaviest(design) -> int:
        links = lone_links(solve(design, catalog), catalog)
        return max((ln.cells for ln in links), default=0)

    project = create_project(f"samples/models/{name}.glb", studs=16, directory=tmp_path)
    design = project.load_design(base=True)
    before = design.fingerprint()
    without = make_buildable(design, catalog, max_sturdy_solves=0)
    t = time.perf_counter()
    result = make_buildable(design, catalog)
    assert time.perf_counter() - t < 10
    assert design.fingerprint() == before
    out = result.design
    assert heaviest(out) < heaviest(without.design)
    assert nx.number_connected_components(connection_graph(solve(out, catalog), catalog)) == 1
    assert result.pieces_after == 1
    # nothing emptied, no visible cell recoloured, every change in the masks and in a note
    assert not (design.filled & ~out.filled).any()
    assert np.array_equal(result.added, out.filled & ~design.filled)
    assert np.array_equal(result.recoloured, design.filled & (out.colors != design.colors))
    assert not (result.recoloured & _visible(design.filled)).any()
    assert result.added.sum() > without.added.sum()
    assert any("hang on" in n or "hangs on" in n for n in result.notes)
    places = []  # the first place each note of an added cell names: x=a to b, y=c, z=d to e
    for note in result.notes:
        if note.startswith(("Filled", "Added")):
            spans = re.findall(r"([xyz])=(\d+)(?: to (\d+))?", note)[:3]
            places.append([(int(a), int(b or a)) for _, a, b in spans])
    for cell in np.argwhere(result.added).tolist():
        assert any(
            all(lo <= v <= hi for v, (lo, hi) in zip(cell, p, strict=True)) for p in places
        ), cell


# ---- the weak-spot phase, after review ---------------------------------------------------------

_SAMPLE_RUNS: dict[tuple[str, int], tuple] = {}


def _phase_off_and_on(name: str, studs: int, tmp_path_factory, catalog) -> tuple:
    """(Design, make_buildable without the weak-spot phase, with it) for a sample model,
    computed once per module."""
    from bricksnap.buildable import make_buildable

    key = (name, studs)
    if key not in _SAMPLE_RUNS:
        directory = tmp_path_factory.mktemp(f"{name}{studs}")
        model = next(pathlib.Path("samples/models").glob(f"{name}.*"))
        project = create_project(model, studs=studs, directory=directory)
        design = project.load_design(base=True)
        off = make_buildable(design, catalog, max_sturdy_solves=0)
        on = make_buildable(design, catalog)
        _SAMPLE_RUNS[key] = (design, off, on)
    return _SAMPLE_RUNS[key]


def _heavy_limit(design) -> float:
    return max(12.0, min(40.0, design.filled.sum() / 10))


def _place(cells) -> str:
    """'x=a to b, y=c, z=d to e', as the notes write a place."""
    a = np.asarray(cells).reshape(-1, 3)
    lo, hi = a.min(axis=0), a.max(axis=0)
    span = [
        str(int(lo[i])) if lo[i] == hi[i] else f"{int(lo[i])} to {int(hi[i])}" for i in range(3)
    ]
    return f"x={span[0]}, y={span[1]}, z={span[2]}"


def _heavy_links(design, catalog, limit: float) -> list[tuple[str, int]]:
    """(place, cells) of every lone link of a fresh layout of the Design carrying at least
    ``limit`` cells (heavy by the input Design's size), worked out here from
    connect.lone_links: a part's cells, or the two cells of a single stud."""
    from bricksnap.connect import lone_links, occupancy
    from bricksnap.layout import solve

    build = solve(design, catalog)
    occ = occupancy(build, catalog)[0]
    out = []
    for ln in lone_links(build, catalog):
        if ln.cells < limit:
            continue
        if ln.joint is None:
            at = np.argwhere(occ == ln.part)
        else:
            lo, hi = ln.joint
            under = np.argwhere((occ[:, :, :-1] == lo) & (occ[:, :, 1:] == hi))
            at = np.concatenate([under, under + [0, 0, 1]])
        out.append((_place(at), ln.cells))
    return out


_SPAN = r"\d+(?: to \d+)?"
_LINK = rf"(?:a single stud|one part, the [A-Za-z ]+? part) at (x={_SPAN}, y={_SPAN}, z={_SPAN})"


@pytest.mark.parametrize("name", [pytest.param("cat", marks=pytest.mark.thorough), "pineapple"])
def test_the_weak_spot_phase_never_leaves_a_finished_model_weaker(tmp_path_factory, catalog, name):
    """Finishing comes after the make-buildable pass. With the weak-spot phase the finished
    build must not hang more on one link, nor by more threads, than without it (the cat at
    24 studs once ended with both front legs on one part each, which finishing alone holds)."""
    from bricksnap.connect import lone_links
    from bricksnap.finish import finish

    design, off, on = _phase_off_and_on(name, 24, tmp_path_factory, catalog)
    limit = _heavy_limit(design)

    def weakness(result) -> tuple[int, int]:
        links = lone_links(finish(result.build, result.design, catalog), catalog)
        return max((ln.cells for ln in links), default=0), sum(ln.cells >= limit for ln in links)

    before, after = weakness(off), weakness(on)
    assert after[0] <= before[0] and after[1] <= before[1], (before, after)


@pytest.mark.parametrize(
    ("name", "studs", "most"),
    [
        ("pineapple", 16, 6),
        ("spaceship", 16, 6),
        ("hat", 16, 6),
        pytest.param("pawn", 12, 15, marks=pytest.mark.thorough),
        ("hat", 12, 15),
    ],
)
def test_the_weak_spot_phase_fills_few_cells_and_only_beside_what_it_cures(
    tmp_path_factory, catalog, name, studs, most
):
    """The phase fills only what the build needs, next to a weak spot a note names: a ring of
    partly covered cells where one or two hold the group changes the outline for nothing
    (the pawn at 12 studs once came out with a straight wall on one side)."""
    design, off, on = _phase_off_and_on(name, studs, tmp_path_factory, catalog)
    phase = np.argwhere(on.design.colors != off.design.colors)
    assert 0 < len(phase) <= most, len(phase)
    places = []
    for note in on.notes:
        for m in re.finditer(_LINK, note):
            spans = re.findall(r"([xyz])=(\d+)(?: to (\d+))?", m.group(1))
            places.append([(int(a), int(b or a)) for _, a, b in spans])
    assert places
    for cell in phase.tolist():
        assert any(
            all(lo - 3 <= v <= hi + 3 for v, (lo, hi) in zip(cell, p, strict=True)) for p in places
        ), cell


@pytest.mark.parametrize(("name", "studs"), [("pineapple", 16), ("hat", 12), ("pineapple", 24)])
def test_notes_about_weak_spots_describe_the_build_that_is_returned(
    tmp_path_factory, catalog, name, studs
):
    """A note says what hangs where in the build the pass returns, not in the build right
    after its own change: no "still hangs" when nothing heavy is left, and no "no longer
    hangs" on a link that, in a fresh layout, still carries as much as before."""
    design, _, on = _phase_off_and_on(name, studs, tmp_path_factory, catalog)
    heavy = _heavy_links(on.design, catalog, _heavy_limit(design))
    if not heavy:
        for note in on.notes:
            for words in ("still hang", "hangs there now", "hang there now", "Still hanging"):
                assert words not in note, note
    for note in on.notes:
        group = re.search(r"\(\d+ parts?, (\d+) cells\)", note)
        cells_before = int(group.group(1)) if group else 0
        for m in re.finditer(r"no longer hangs? on " + _LINK, note):
            for place, n in heavy:
                assert not (place == m.group(1) and n >= cells_before), (note, place, n)
        for m in re.finditer(r"(?:still|now) hangs? on " + _LINK + r",? with (\d+) cells", note):
            assert (m.group(1), int(m.group(2))) in heavy, (note, heavy)
