"""Tests for the scorecard (bricksnap/bench.py)."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from bricksnap import pipeline
from bricksnap.bench import (
    VIEWS,
    Row,
    compare,
    format_table,
    load_rows,
    load_scorecard,
    outline_match,
    run_bench,
    shaped_share,
    weak_spot_count,
)
from bricksnap.checks import check
from bricksnap.layout import solve
from bricksnap.project import Project
from bricksnap.render import silhouette
from bricksnap.seed import load_seed
from bricksnap.types import EMPTY, Build, Placement, Seed
from bricksnap.voxelize import voxelize

GREY = 71
RED, YELLOW, BLUE = 4, 14, 1


def P(part: str, x: int, y: int, z: int, rot: int = 0, color: int = GREY) -> Placement:
    return Placement(part=part, color=color, x=x, y=y, z=z, rot=rot)


def towers(n: int, tiled: int = 0) -> list[Placement]:
    """A 2x8 plate on the ground with a tower of three 1x1 bricks on each of its first ``n``
    studs and a 1x1 tile on each of the ``tiled`` studs after them. Each tower hangs on a
    single stud, so each one is a weak spot of its own: ``n`` weak spots."""
    cells = [(x, y) for x in range(8) for y in range(2)]
    parts = [P("3034", 0, 0, 0)]
    for i, (x, y) in enumerate(cells[:n]):
        for k in range(3):
            parts.append(P("3005", x, y, 1 + 3 * k, color=RED if i % 2 else YELLOW))
    parts += [P("3070b", x, y, 1, color=BLUE) for x, y in cells[n : n + tiled]]
    return parts


def write_box(path: Path, extents=(64.0, 32.0, 19.2)) -> Path:
    trimesh.creation.box(extents=extents).export(path)
    return path


def write_wedge(path: Path) -> Path:
    mesh = trimesh.creation.box(extents=(40.0, 24.0, 20.0))
    top = mesh.vertices[:, 2] > 0
    mesh.vertices[top, 0] *= 0.01  # the top edge pinched to a ridge: a roof shape
    mesh.export(path)
    return path


def write_flat(path: Path) -> Path:
    square = trimesh.Trimesh(
        vertices=[[0, 0, 0], [40, 0, 0], [40, 40, 0], [0, 40, 0]], faces=[[0, 1, 2], [0, 2, 3]]
    )
    square.export(path)
    return path


# ---- shaped ---------------------------------------------------------------------------------


def test_shaped_is_zero_for_plain_bricks(catalog):
    build = Build(
        shape=(4, 2, 6), parts=[P("3001", 0, 0, 0), P("3003", 0, 0, 3), P("3003", 2, 0, 3)]
    )
    assert shaped_share(build, catalog) == 0.0


def test_shaped_is_one_for_a_fully_tiled_top(catalog):
    build = Build(shape=(4, 2, 4), parts=[P("3001", 0, 0, 0), P("87079", 0, 0, 3)])
    assert shaped_share(build, catalog) == 1.0


def test_a_slope_counts_its_slanted_cell_and_not_its_stud_cell(catalog):
    # 3040b at rot 0 covers (0, 0) and (0, 1); its stud is on (0, 1), the high side
    slope = P("3040b", 0, 0, 0)
    assert catalog.stud_cells(slope) == [(0, 1)]
    alone = Build(shape=(1, 2, 3), parts=[slope])
    assert shaped_share(alone, catalog) == 0.5
    # a tile on the stud cell: now both upward-facing cells are shaped, so the half
    # counted above was the slanted cell
    tiled = Build(shape=(1, 2, 4), parts=[slope, P("3070b", 0, 1, 3)])
    assert shaped_share(tiled, catalog) == 1.0
    # a plate on the stud cell: the slanted cell still counts, the plate's stud does not
    plated = Build(shape=(1, 2, 4), parts=[slope, P("3024", 0, 1, 3)])
    assert shaped_share(plated, catalog) == 0.5


def test_a_turned_slope_counts_the_right_cell(catalog):
    slope = P("3040b", 0, 0, 0, rot=180)  # stud now on (0, 0), slanted cell (0, 1)
    assert catalog.stud_cells(slope) == [(0, 0)]
    build = Build(shape=(1, 2, 4), parts=[slope, P("3070b", 0, 0, 3)])
    assert shaped_share(build, catalog) == 1.0
    build = Build(shape=(1, 2, 4), parts=[slope, P("3024", 0, 0, 3)])
    assert shaped_share(build, catalog) == 0.5


def test_cheese_slopes_and_detail_parts_are_shaped(catalog):
    # 2x2 brick: a cheese slope, a round plate (it has a stud, but it is a detail part)
    # and a cone on three of its studs; the fourth stud is bare
    build = Build(
        shape=(2, 2, 6),
        parts=[P("3003", 0, 0, 0), P("54200", 0, 0, 3), P("6141", 1, 0, 3), P("59900", 0, 1, 3)],
    )
    assert shaped_share(build, catalog) == 0.75


def test_inverted_slopes_and_side_stud_bricks_have_plain_tops(catalog):
    build = Build(shape=(2, 2, 3), parts=[P("3665b", 0, 0, 0), P("87087", 1, 0, 0)])
    assert shaped_share(build, catalog) == 0.0


def test_shaped_of_an_empty_build_is_zero(catalog):
    assert shaped_share(Build(shape=(3, 3, 3)), catalog) == 0.0


def test_only_cells_with_nothing_above_count(catalog):
    # a 2x2 plate with a 1x1 tile on one stud: three bare studs and one tile on top
    build = Build(shape=(2, 2, 2), parts=[P("3022", 0, 0, 0), P("3070b", 0, 0, 1)])
    assert shaped_share(build, catalog) == 0.25


def test_a_top_under_an_overhang_still_faces_up(catalog):
    # "nothing above" means nothing directly above: a 2x2 plate with a 2x2 tile one plate
    # higher (an empty layer between) shows four bare studs and four tile cells
    build = Build(shape=(2, 2, 3), parts=[P("3022", 0, 0, 0), P("3068b", 0, 0, 2)])
    assert shaped_share(build, catalog) == 0.5


# ---- outline match --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def box_case(tmp_path_factory, catalog):
    """A box seed, its Design, and an exact build of it in 1x1 plates."""
    path = write_box(tmp_path_factory.mktemp("box") / "box.stl")
    seed = load_seed(path, studs=8)
    design = voxelize(seed, catalog)
    xs, ys, zs = np.nonzero(design.colors != EMPTY)
    parts = [P("3024", int(x), int(y), int(z)) for x, y, z in zip(xs, ys, zs, strict=True)]
    return seed, design, Build(shape=design.shape, parts=parts)


def test_a_box_and_its_build_match_almost_perfectly(box_case, catalog):
    seed, design, build = box_case
    for view in ("front", "right", "top"):
        assert outline_match(seed, build, catalog, view, design.seed_offset) > 0.97
    solved = solve(design, catalog)
    for view in ("front", "right", "top"):
        assert outline_match(seed, solved, catalog, view, design.seed_offset) > 0.97


def test_half_a_build_matches_about_half(box_case, catalog):
    seed, design, build = box_case
    xs = [p.x for p in build.parts]
    middle = (min(xs) + max(xs) + 1) // 2
    half = Build(shape=build.shape, parts=[p for p in build.parts if p.x < middle])
    assert outline_match(seed, half, catalog, "front", design.seed_offset) == pytest.approx(
        0.5, abs=0.05
    )
    assert outline_match(seed, half, catalog, "top", design.seed_offset) == pytest.approx(
        0.5, abs=0.05
    )
    # seen from the side the half hides nothing
    assert outline_match(seed, half, catalog, "right", design.seed_offset) > 0.97


def test_a_build_bigger_than_the_model_matches_less(box_case, catalog):
    # the box build plus a row of plates in front of it: everything the model covers is
    # still covered, but the build covers more, and that must cost
    seed, design, build = box_case
    front_y = min(p.y for p in build.parts) - 1
    assert front_y >= 0
    extra = [
        P("3024", p.x, front_y, p.z)
        for p in build.parts
        if p.y == front_y + 1  # one plate in front of each plate of the front face
    ]
    bigger = Build(shape=build.shape, parts=build.parts + extra)
    a = silhouette(seed, catalog, "top", grid_shape=build.shape, seed_offset=design.seed_offset)
    b = silhouette(bigger, catalog, "top")
    assert (a & ~b).sum() <= 0.03 * a.sum()  # the model's outline lies inside the build's
    match = outline_match(seed, bigger, catalog, "top", design.seed_offset)
    assert match == pytest.approx(a.sum() / b.sum(), abs=0.02)
    assert match < 0.85
    # seen from the front the extra row hides behind nothing new
    assert outline_match(seed, bigger, catalog, "front", design.seed_offset) > 0.97


def test_the_views_are_front_right_top():
    assert VIEWS == ("front", "right", "top")


def test_outline_match_with_nothing_on_either_side(catalog):
    seed = Seed(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64))
    empty = Build(shape=(3, 3, 3))
    assert outline_match(seed, empty, catalog, "front", (0, 0, 0)) == 1.0


def test_outline_match_with_an_empty_build(box_case, catalog):
    seed, design, build = box_case
    empty = Build(shape=build.shape)
    assert outline_match(seed, empty, catalog, "top", design.seed_offset) == 0.0


# ---- weak spots ----------------------------------------------------------------------------


def test_weak_spots_are_counted_beyond_the_ten_the_report_lists(catalog):
    build = Build(shape=(8, 2, 10), parts=towers(16))
    report = check(build, catalog)
    assert len(report.weak_spots) == 10  # the report lists only the ten most serious
    assert weak_spot_count(report) == 16
    few = check(Build(shape=(8, 2, 10), parts=towers(4)), catalog)
    assert weak_spot_count(few) == len(few.weak_spots) == 4
    one = check(Build(shape=(8, 2, 10), parts=towers(1)), catalog)
    assert weak_spot_count(one) == 1
    none = check(Build(shape=(8, 2, 1), parts=towers(0)), catalog)
    assert weak_spot_count(none) == 0


# ---- running --------------------------------------------------------------------------------


def no_private_paths(text: str, tmp_path: Path) -> None:
    assert str(tmp_path) not in text
    assert str(Path.home()) not in text


def test_one_bad_model_never_stops_the_run(tmp_path, catalog):
    models = tmp_path / "models"
    models.mkdir()
    write_wedge(models / "a_roof.stl")
    (models / "b_broken.stl").write_bytes(b"solid nonsense\nthis is not an stl\n\x00\x01")
    write_flat(models / "c_flat.stl")
    (models / "readme.md").write_text("not a model", encoding="utf-8")
    out = tmp_path / "out"

    rows = run_bench(models, out, studs=5, catalog=catalog)

    assert [r.name for r in rows] == ["a_roof", "b_broken", "c_flat"]
    roof, broken, flat = rows
    assert roof.error == ""
    assert roof.ok and roof.loose == 0 and roof.pieces == 1
    assert roof.parts > 0 and roof.rough_parts > 0
    assert roof.part_types >= 1 and roof.colours == 1
    assert 0.0 <= roof.shaped <= 1.0 and 0.0 <= roof.rough_shaped <= 1.0
    assert roof.match_top > 0.9 and roof.match_front > 0.5 and roof.match_right > 0.5
    assert roof.seconds > 0
    assert (out / "a_roof.png").is_file()
    assert (out / "projects" / "a-roof" / "build.json").is_file()

    for bad in (broken, flat):
        assert bad.error
        assert asdict(bad) == asdict(Row(bad.name, error=bad.error))
        assert not (out / f"{bad.name}.png").exists()
    assert "b_broken.stl" in broken.error
    assert "flat" in flat.error

    saved = json.loads((out / "scorecard.json").read_text(encoding="utf-8"))
    assert saved["studs"] == 5
    assert [r["name"] for r in saved["rows"]] == ["a_roof", "b_broken", "c_flat"]
    assert load_rows(out / "scorecard.json") == rows
    md = (out / "scorecard.md").read_text(encoding="utf-8")
    assert md.startswith("# BrickSnap scorecard: 3 models at 5 studs\n")
    assert "| a_roof" in md and "failed" in md
    assert "c_flat:" in md  # the problems are listed under the table
    for text in (md, json.dumps(saved)):
        no_private_paths(text, tmp_path)


def test_the_pawn_at_8_studs(tmp_path, pawn_path, catalog):
    out = tmp_path / "out"
    rows = run_bench(pawn_path.parent, out, studs=8, catalog=catalog, names=["pawn"])
    assert len(rows) == 1
    pawn = rows[0]
    assert pawn.error == ""
    assert pawn.ok and pawn.loose == 0
    assert pawn.parts > 20 and pawn.rough_parts > 20
    for value in (pawn.match_front, pawn.match_right, pawn.match_top):
        assert 0.6 < value <= 1.0
    project = Project(out / "projects" / "pawn")
    assert pawn.weak_spots == weak_spot_count(check(project.load_build(), catalog))
    picture = out / "pawn.png"
    assert picture.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # running again replaces the old project instead of failing on it
    again = run_bench(pawn_path.parent, out, studs=8, catalog=catalog, names=["pawn"])
    assert again[0].error == ""
    assert {**asdict(again[0]), "seconds": 0} == {**asdict(pawn), "seconds": 0}


def expected_row(project: Project, build: Build, catalog) -> Row:
    """The Row for a benched project, worked out again by other means than run_bench."""
    report = check(build, catalog)
    rough = pipeline.rough_build(project, catalog=catalog)
    seed = pipeline.load_project_seed(project)
    offset = project.load_design().seed_offset
    return Row(
        project.name,
        ok=report.ok,
        parts=len(build.parts),
        loose=len(report.loose),
        pieces=report.components,
        weak_spots=weak_spot_count(report),
        part_types=len({p.part for p in build.parts}),
        colours=len({p.color for p in build.parts}),
        shaped=round(shaped_share(build, catalog), 4),
        rough_parts=len(rough.parts),
        rough_shaped=round(shaped_share(rough, catalog), 4),
        match_front=round(outline_match(seed, build, catalog, "front", offset), 4),
        match_right=round(outline_match(seed, build, catalog, "right", offset), 4),
        match_top=round(outline_match(seed, build, catalog, "top", offset), 4),
        notes=len(build.notes),
    )


def test_each_number_comes_from_the_saved_project(tmp_path, catalog):
    # the wedge is not the same seen from the front and from the side, so a swap shows
    models = tmp_path / "models"
    models.mkdir()
    write_wedge(models / "roof.stl")
    out = tmp_path / "out"
    (row,) = run_bench(models, out, studs=5, catalog=catalog)
    project = Project(out / "projects" / "roof")
    build = project.load_build()
    expected = expected_row(project, build, catalog)
    assert {**asdict(row), "seconds": 0.0} == asdict(expected)
    assert row.match_front != row.match_right


def test_each_field_holds_its_own_measurement(tmp_path, catalog, monkeypatch):
    # a build made by hand, so every number is known: a 2x8 plate with twelve towers of
    # three 1x1 bricks (twelve weak spots, more than the report lists), 1x1 tiles on three
    # of the four studs left, and one tile floating over the last (one loose part, two
    # pieces)
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "box.stl")
    floating = P("3070b", 7, 1, 5, color=BLUE)
    made = Build(shape=(8, 2, 10), parts=towers(12, tiled=3) + [floating])
    made.notes = ["one", "two"]

    def fake_rebuild(project, **kw):
        return made

    monkeypatch.setattr(pipeline, "rebuild", fake_rebuild)
    out = tmp_path / "out"
    (row,) = run_bench(models, out, studs=6, catalog=catalog)
    assert row.error == ""
    assert not row.ok and row.loose == 1 and row.pieces == 2
    assert row.parts == 1 + 12 * 3 + 3 + 1
    assert row.part_types == 3  # plate, brick, tile
    assert row.colours == 4  # grey, red, yellow, blue
    assert row.weak_spots == 12
    assert row.notes == 2
    # tops: 12 towers, 3 tiles, the bare stud under the floating tile, the floating tile
    assert row.shaped == round(4 / 17, 4)
    project = Project(out / "projects" / "box")
    rough = pipeline.rough_build(project, catalog=catalog)
    assert row.rough_parts == len(rough.parts) != row.parts
    assert row.rough_shaped == round(shaped_share(rough, catalog), 4) != row.shaped
    assert {**asdict(row), "seconds": 0.0} == asdict(expected_row(project, made, catalog))


def test_seconds_count_loading_and_building_but_not_the_rest(tmp_path, catalog, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "box.stl")
    import time

    clock = [1000.0]
    monkeypatch.setattr(time, "perf_counter", lambda: clock[0])

    def slow(function, seconds):
        def run(*args, **kwargs):
            clock[0] += seconds
            return function(*args, **kwargs)

        return run

    monkeypatch.setattr(pipeline, "create_project", slow(pipeline.create_project, 2.0))
    monkeypatch.setattr(pipeline, "rebuild", slow(pipeline.rebuild, 5.25))
    monkeypatch.setattr(pipeline, "rough_build", slow(pipeline.rough_build, 100.0))
    monkeypatch.setattr(pipeline, "render_compare", slow(pipeline.render_compare, 1000.0))
    (row,) = run_bench(models, tmp_path / "out", studs=4, catalog=catalog)
    assert row.error == "" and row.picture_error == ""
    assert row.seconds == 7.25


def test_the_picture_shows_model_plain_conversion_and_build(tmp_path, catalog):
    from PIL import Image

    models = tmp_path / "models"
    models.mkdir()
    write_wedge(models / "roof.stl")
    out = tmp_path / "out"
    run_bench(models, out, studs=5, catalog=catalog)
    project = Project(out / "projects" / "roof")
    three = pipeline.render_compare(project, catalog=catalog, rough=True, name="three.png")
    two = pipeline.render_compare(project, catalog=catalog, rough=False, name="two.png")
    with Image.open(out / "roof.png") as saved, Image.open(three) as a, Image.open(two) as b:
        assert saved.size == a.size != b.size
        assert np.array_equal(np.asarray(saved), np.asarray(a))


def test_names_pick_models_and_a_missing_name_is_reported(tmp_path, catalog):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "box.stl")
    write_wedge(models / "roof.stl")
    rows = run_bench(models, tmp_path / "out", studs=5, catalog=catalog, names=["roof", "dragon"])
    assert [r.name for r in rows] == ["roof", "dragon"]
    assert rows[0].error == ""
    assert "no model file called dragon" in rows[1].error


def test_two_files_with_the_same_name(tmp_path, catalog):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "box.stl")
    write_box(models / "box.obj")
    rows = run_bench(models, tmp_path / "out", studs=5, catalog=catalog)
    assert [r.name for r in rows] == ["box", "box"]
    assert rows[0].error == ""
    assert "also called box" in rows[1].error
    # comparing the run with itself finds nothing, though one "box" built and one did not
    assert compare(rows, rows).strip() == "No change."


def test_two_names_that_make_the_same_folder(tmp_path, catalog):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "a b.stl")
    write_wedge(models / "a-b.stl")
    out = tmp_path / "out"
    rows = run_bench(models, out, studs=5, catalog=catalog)
    assert [r.name for r in rows] == ["a b", "a-b"]
    first, second = rows
    assert first.error == "" and first.ok
    assert "same project folder" in second.error and "a b.stl" in second.error
    assert asdict(second) == asdict(Row("a-b", error=second.error))
    assert not (out / "a-b.png").exists()
    # the folder holds the model that was built, not the one left out
    assert Project(out / "projects" / "a-b").meta["name"] == "a b"


def test_a_fault_inside_bricksnap_is_reported_plainly(tmp_path, catalog, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "a.stl")
    write_box(models / "b.stl")
    from bricksnap import pipeline

    real = pipeline.rebuild

    def flaky(project, **kw):
        if project.name == "a":
            raise RuntimeError(f"cannot open {Path.home() / 'secret' / 'thing.txt'}")
        return real(project, **kw)

    monkeypatch.setattr(pipeline, "rebuild", flaky)
    rows = run_bench(models, tmp_path / "out", studs=5, catalog=catalog)
    assert rows[0].parts == 0
    assert "while building it" in rows[0].error
    assert "fault in BrickSnap, not in the model" in rows[0].error
    assert "thing.txt" in rows[0].error
    no_private_paths(rows[0].error, tmp_path)
    assert rows[1].error == "" and rows[1].ok


def test_a_failed_picture_keeps_the_numbers(tmp_path, catalog, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "box.stl")
    from bricksnap import pipeline

    def broken(*args, **kwargs):
        raise ValueError("no paint")

    monkeypatch.setattr(pipeline, "render_compare", broken)
    out = tmp_path / "out"
    rows = run_bench(models, out, studs=5, catalog=catalog)
    assert rows[0].ok and rows[0].parts > 0
    # a missing picture is not a failed build: ``error`` stays empty, so everything that
    # reads ``error`` as "could not be built" (the command, compare, the table) agrees
    assert rows[0].error == ""
    assert rows[0].picture_error.startswith("It was built and measured, but the picture could")
    assert "no paint" in rows[0].picture_error
    assert "| box" in format_table(rows) and "failed" not in format_table(rows)
    assert "total (1 of 1 built)" in format_table(rows)
    md = (out / "scorecard.md").read_text(encoding="utf-8")
    assert "Problems:" in md and "- box: It was built and measured" in md
    assert load_rows(out / "scorecard.json") == rows
    assert compare(rows, rows).strip() == "No change."


def test_an_older_picture_is_removed_when_the_model_now_fails(tmp_path, catalog):
    models = tmp_path / "models"
    models.mkdir()
    write_box(models / "box.stl")
    out = tmp_path / "out"
    run_bench(models, out, studs=5, catalog=catalog)
    assert (out / "box.png").exists()
    (models / "box.stl").write_bytes(b"broken")
    rows = run_bench(models, out, studs=5, catalog=catalog)
    assert rows[0].error
    assert not (out / "box.png").exists()
    assert not (out / "projects" / "box").exists()


def test_a_missing_models_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="Cannot find the folder of test models"):
        run_bench(tmp_path / "nowhere", tmp_path / "out")


# ---- reading a saved scorecard --------------------------------------------------------------


def test_load_rows_round_trips_and_is_forgiving(tmp_path):
    rows = [Row("cat", ok=True, parts=110, shaped=0.25, match_top=0.9), Row("duck", error="bad")]
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps({"studs": 16, "rows": [asdict(r) for r in rows]}), "utf-8")
    assert load_scorecard(path) == (16, rows)

    old = [
        {"name": "cat", "parts": 120, "shaped": 1, "something_new": [1, 2]},
        {"name": "duck", "parts": "many", "ok": 1, "error": None},
        {"parts": 3},
        "pawn",
    ]
    path.write_text(json.dumps(old), encoding="utf-8")
    studs, loaded = load_scorecard(path)
    assert studs is None
    assert loaded == [Row("cat", parts=120, shaped=1.0), Row("duck")]
    assert isinstance(loaded[0].shaped, float)


@pytest.mark.parametrize(
    "content, words",
    [("{nope", "not valid JSON"), ('{"rows": 3}', "no list of rows"), ("7", "no list of rows")],
)
def test_load_rows_explains_a_damaged_file(tmp_path, content, words):
    path = tmp_path / "scorecard.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=words):
        load_rows(path)


# ---- the table ------------------------------------------------------------------------------


def test_format_table(tmp_path):
    rows = [
        Row(
            "cat",
            ok=True,
            parts=110,
            pieces=1,
            weak_spots=2,
            part_types=12,
            colours=3,
            shaped=0.254,
            rough_parts=150,
            rough_shaped=0.0,
            match_front=0.997,
            match_right=0.81,
            match_top=1.0,
            notes=1,
            seconds=3.14159,
        ),
        Row("duck", parts=80, loose=3, pieces=2, shaped=0.001, seconds=1.0),
        Row("broken", error="The file is damaged."),
    ]
    text = format_table(rows)
    lines = text.splitlines()
    table = [line for line in lines if line.startswith("|")]
    assert len(table) == 2 + 3 + 1
    assert len({len(line) for line in table}) == 1  # the columns line up
    assert "model" in table[0] and "shaped" in table[0] and "front" in table[0]
    cat = table[2]
    assert "yes" in cat and "110" in cat and "25%" in cat and "3.1" in cat
    assert "99%" in cat and "100%" in cat and "0%" in cat  # 99.7% is not shown as 100%
    duck = table[3]
    assert " no " in duck and "1%" in duck  # 0.1% is not shown as 0%
    assert "failed" in table[4]
    total = table[5]
    assert "total (2 of 3 built)" in total
    assert "1 of 2" in total and "190" in total and "4.1" in total
    assert "Key:" in text


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def test_format_table_puts_each_field_in_its_column():
    built = Row(
        "cat",
        ok=True,
        parts=110,
        loose=2,
        pieces=3,
        weak_spots=51,
        part_types=12,
        colours=4,
        shaped=0.25,
        rough_parts=150,
        rough_shaped=0.05,
        match_front=0.61,
        match_right=0.72,
        match_top=0.83,
        notes=7,
        seconds=8.5,
    )
    other = Row(
        "duck",
        parts=90,
        loose=1,
        pieces=6,
        weak_spots=9,
        part_types=13,
        colours=5,
        shaped=0.35,
        rough_parts=160,
        rough_shaped=0.15,
        match_front=0.41,
        match_right=0.52,
        match_top=0.63,
        notes=3,
        seconds=1.5,
    )
    # a failed row with numbers in it: they must not count in the totals
    failed = replace(other, name="broken", error="damaged")
    table = [line for line in format_table([built, other, failed]).splitlines() if "|" in line]
    head = cells(table[0])
    assert head == [
        "model",
        "buildable",
        "parts",
        "loose",
        "pieces",
        "weak",
        "kinds",
        "colours",
        "shaped",
        "rough parts",
        "rough shaped",
        "front",
        "right",
        "top",
        "notes",
        "secs",
    ]
    rows = {cells(line)[0]: dict(zip(head, cells(line), strict=True)) for line in table[2:]}
    assert rows["cat"] == {
        "model": "cat",
        "buildable": "yes",
        "parts": "110",
        "loose": "2",
        "pieces": "3",
        "weak": "51",
        "kinds": "12",
        "colours": "4",
        "shaped": "25%",
        "rough parts": "150",
        "rough shaped": "5%",
        "front": "61%",
        "right": "72%",
        "top": "83%",
        "notes": "7",
        "secs": "8.5",
    }
    assert rows["duck"]["buildable"] == "no" and rows["duck"]["weak"] == "9"
    assert rows["broken"]["buildable"] == "failed"
    assert set(list(rows["broken"].values())[2:]) == {"-"}
    total = rows["total (2 of 3 built)"]
    assert total == {
        "model": "total (2 of 3 built)",
        "buildable": "1 of 2",
        "parts": "200",
        "loose": "3",
        "pieces": "",
        "weak": "60",
        "kinds": "",
        "colours": "",
        "shaped": "30%",
        "rough parts": "310",
        "rough shaped": "10%",
        "front": "51%",
        "right": "62%",
        "top": "73%",
        "notes": "10",
        "secs": "10.0",
    }


def test_format_table_with_no_rows():
    assert "No models" in format_table([])


# ---- comparing ------------------------------------------------------------------------------


def test_compare_with_no_change():
    rows = [Row("cat", ok=True, parts=110, shaped=0.25, match_front=0.9, seconds=3.0)]
    later = [Row("cat", ok=True, parts=110, shaped=0.2501, match_front=0.9002, seconds=9.0)]
    assert compare(rows, later).strip() == "No change."


def test_compare_says_what_changed_and_whether_it_is_better():
    old = [
        Row("cat", ok=False, parts=120, loose=3, pieces=2, shaped=0.10, match_front=0.80),
        Row("duck", ok=True, parts=80, match_top=0.90),
        Row("hat", ok=True, parts=50),
    ]
    new = [
        Row("cat", ok=True, parts=110, loose=0, pieces=1, shaped=0.30, match_front=0.85),
        Row("duck", ok=True, parts=85, match_top=0.85),
        Row("hat", ok=True, parts=50),
    ]
    lines = compare(old, new).strip().splitlines()
    assert len(lines) == 2  # hat did not change
    cat, duck = lines
    assert cat.startswith("cat: ")
    assert "became buildable (better)" in cat
    assert "loose parts went down from 3 to 0 (better)" in cat
    assert "parts went down from 120 to 110;" in cat
    assert "shaped share of the top went up from 10.0% to 30.0%" in cat
    assert "front outline match went up from 80.0% to 85.0% (closer, better)" in cat
    assert duck.startswith("duck: ")
    assert "parts went up from 80 to 85;" in duck
    assert "top outline match went down from 90.0% to 85.0% (less close, worse)" in duck


def test_compare_weak_spots():
    old = [Row("cat", ok=True, parts=110, weak_spots=18), Row("car", ok=True, weak_spots=25)]
    new = [Row("cat", ok=True, parts=110, weak_spots=11), Row("car", ok=True, weak_spots=51)]
    assert compare(old, new).strip().splitlines() == [
        "cat: weak spots went down from 18 to 11 (better).",
        "car: weak spots went up from 25 to 51 (worse).",
    ]


@pytest.mark.parametrize("before, after", [(0.0005, 0.0006), (0.0054, 0.0055), (0.8125, 0.8126)])
def test_compare_never_shows_a_change_as_the_same_number(before, after):
    for key in ("shaped", "match_front", "match_right", "match_top"):
        old = [Row("cat", ok=True, parts=5, **{key: before})]
        new = [Row("cat", ok=True, parts=5, **{key: after})]
        text = compare(old, new).strip()
        if text != "No change.":
            numbers = text.split(" from ")[1].split(" (")[0].rstrip(".").split(" to ")
            assert numbers[0] != numbers[1], text


def test_compare_shows_the_numbers_it_compared():
    text = compare([Row("cat", parts=5, shaped=0.0005)], [Row("cat", parts=5, shaped=0.0006)])
    assert text.strip() == "cat: the shaped share of the top went up from 0.0% to 0.1%."


def test_compare_pairs_rows_of_the_same_name_in_order():
    rows = [Row("box", ok=True, parts=7, pieces=1), Row("box", error="Another file is box")]
    assert compare(rows, rows).strip() == "No change."
    fewer = compare(rows, rows[:1]).strip()
    assert fewer == "box: in the saved scorecard but not in this run."


def test_compare_does_not_judge_the_part_count():
    text = compare([Row("cat", parts=100)], [Row("cat", parts=120)])
    assert text.strip() == "cat: parts went up from 100 to 120."


def test_compare_worse_cases():
    old = [Row("cat", ok=True, parts=110), Row("duck", ok=True, loose=0, parts=9)]
    new = [Row("cat", ok=False, parts=110, loose=2), Row("duck", error="The file is damaged.")]
    cat, duck = compare(old, new).strip().splitlines()
    assert "is no longer buildable (worse)" in cat
    assert "loose parts went up from 0 to 2 (worse)" in cat
    assert duck == "duck: it could be built before, but now it fails (worse): The file is damaged."


def test_compare_failures_and_models_that_come_and_go():
    old = [Row("cat", error="bad"), Row("duck", error="bad"), Row("gone", ok=True, parts=4)]
    new = [Row("cat", ok=True, parts=110), Row("duck", error="worse"), Row("fresh", parts=3)]
    lines = compare(old, new).strip().splitlines()
    assert lines == [
        "cat: it failed before and now it builds (better): 110 parts, buildable, 0 loose.",
        "fresh: new, it is not in the saved scorecard.",
        "gone: in the saved scorecard but not in this run.",
    ]


def test_compare_reads_a_saved_file(tmp_path):
    rows = [Row("cat", ok=True, parts=110, shaped=0.25)]
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps({"studs": 16, "rows": [asdict(r) for r in rows]}), "utf-8")
    assert compare(load_rows(path), rows).strip() == "No change."
