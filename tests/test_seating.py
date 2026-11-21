"""Tests for where the model sits on the grid (bricksnap/pipeline.py "the model sits where its
build comes out best", bricksnap/seed.py ``seated``/``seatings``, and the seated grid in
bricksnap/voxelize.py)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

import bricksnap.pipeline as pipeline
from bricksnap.bench import VIEWS, outline_match
from bricksnap.catalog import load_catalog
from bricksnap.connect import lone_links
from bricksnap.project import Project
from bricksnap.render import silhouette
from bricksnap.seed import _centring, load_seed, seated, seatings
from bricksnap.types import Seed
from bricksnap.voxelize import voxelize

MODELS = Path(__file__).resolve().parent.parent / "samples" / "models"
S = 8.0  # one stud, mm


def make(path: Path, *, studs: int, tmp: Path, name: str = "m", **kw) -> Project:
    return pipeline.create_project(path, studs=studs, name=name, directory=tmp, **kw)


def built(project: Project, catalog):
    build = pipeline.rebuild(project, catalog=catalog)
    seed, design = pipeline.load_project_seed(project), project.load_design()
    match = [outline_match(seed, build, catalog, v, design.seed_offset) for v in VIEWS]
    return build, match


def _stl(path: Path, *meshes: trimesh.Trimesh) -> Path:
    joined = trimesh.util.concatenate(list(meshes))
    assert isinstance(joined, trimesh.Trimesh)
    joined.export(path)
    return path


def figure_seed() -> Seed:
    """A standing figure 12 studs tall (the review's 'figure:d=2.4,gap=4'): two round legs 2.4
    studs across, their axes 4 studs apart, a body 7.2 x 3.2 studs over both, and a head;
    placed as ``load_seed`` places a model (from 0, centred in whole studs)."""
    h = 12 * S
    zl, zb = 0.45 * h, 0.8 * h
    parts = []
    for cx in (2.0, 6.0):
        leg = trimesh.creation.cylinder(radius=2.4 * S / 2, height=zl + 1.0, sections=96)
        leg.apply_translation([cx * S, 2 * S, (zl + 1.0) / 2])
        parts.append(leg)
    parts.append(trimesh.creation.box(bounds=[[0.4 * S, 0.4 * S, zl], [7.6 * S, 3.6 * S, zb]]))
    head = trimesh.creation.icosphere(subdivisions=3, radius=3.4 * S / 2)
    head.apply_translation([4 * S, 2 * S, zb + 1.5 * S])
    parts.append(head)
    mesh = trimesh.util.concatenate(parts)
    assert isinstance(mesh, trimesh.Trimesh)
    v = np.asarray(mesh.vertices, float)
    v = v - v.min(axis=0)
    v[:, :2] += _centring(v.max(axis=0)[:2])
    return Seed(vertices=v, faces=np.asarray(mesh.faces))


# ---- the bottle, the reason for all this ---------------------------------------------------


def test_the_bottle_at_twelve_studs_sits_where_its_body_is_three_studs_across(catalog, tmp_path):
    """Today's seating (centred) makes the bottle's body a column 2 x 2 studs where the model
    is 2.85 to 3.3 across, 96 cells hang on one part, and its outline matches 70.5% from the
    front, 73.7% from the side and 71.9% from above. Half a stud over in x and y the body is
    3 x 3, nothing of 40 cells or more hangs on one part, and every view is above 80%. Each
    seating is measured on its finished build, and the sentence gives the chosen seating's
    numbers first and today's after."""
    measured = {}
    real = pipeline._seat_measures

    def spy(seed, design, fused, cat):
        measured[seed.seat] = got = real(seed, design, fused, cat)
        return got

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pipeline, "_seat_measures", spy)
        project = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path)
    assert project.seat == (1, 1)
    assert project.meta["seat"] == [1, 1]
    design = project.load_design()
    for z in range(0, 18):  # the body, where the model is over 3 studs across
        level = design.filled[:, :, z]
        assert level.any(axis=1).sum() == 3 and level.any(axis=0).sum() == 3, z
    build, match = built(project, catalog)
    assert len(build.parts) == measured[(1, 1)]["parts"]  # measured finished, as built
    shown = lambda m: "/".join(str(round(100 * v)) for v in m)  # noqa: E731
    assert build.notes[0] == (
        "When this project was made the model was set half a stud over in x and y on the grid: "
        f"its outline matched {shown(match)}% that way against "
        f"{shown(measured[(0, 0)]['match'])}%."
    )
    assert shown(measured[(0, 0)]["match"]) == "70/74/72"
    assert all(m >= 0.80 for m in match), match
    assert max((ln.cells for ln in lone_links(build, catalog)), default=0) < 40
    # mirror-symmetric model, mirror-symmetric fill, both ways
    f = design.filled
    assert np.array_equal(f, f[::-1]) and np.array_equal(f, f[:, ::-1])


def test_the_choice_is_the_same_on_a_second_run(tmp_path):
    a = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path / "a")
    b = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path / "b")
    assert a.seat == b.seat
    assert a.load_design().fingerprint() == b.load_design().fingerprint()
    assert a.meta["seat_note"] == b.meta["seat_note"]


# ---- when nothing is tried -----------------------------------------------------------------


def _same_as_today(path: Path, studs: int, tmp: Path, catalog, monkeypatch) -> None:
    chosen = make(path, studs=studs, tmp=tmp / "chosen", name="x")
    with monkeypatch.context() as m:
        m.setattr(pipeline, "SEAT_STUDS", 0)  # nothing is ever tried
        today = make(path, studs=studs, tmp=tmp / "today", name="x")
    assert chosen.seat == (0, 0)
    assert "seat" not in chosen.meta and "seat_note" not in chosen.meta
    assert (chosen.path / "project.json").read_bytes() == (today.path / "project.json").read_bytes()
    assert chosen.load_design().fingerprint() == today.load_design().fingerprint()
    a, b = pipeline.rebuild(chosen, catalog=catalog), pipeline.rebuild(today, catalog=catalog)
    assert a.parts == b.parts and a.notes == b.notes


def test_a_box_with_whole_stud_sides_is_built_once_as_today(catalog, tmp_path, monkeypatch):
    box = trimesh.creation.box(bounds=[[0, 0, 0], [4 * S, 3 * S, 9.6 * 2]])
    path = _stl(tmp_path / "box.stl", box)
    seed = load_seed(path, studs=4)
    assert seatings(seed, 4) == [(0, 0)]
    calls = []
    real = pipeline._seat_measures
    monkeypatch.setattr(pipeline, "_seat_measures", lambda *a: calls.append(1) or real(*a))
    _same_as_today(path, 4, tmp_path, catalog, monkeypatch)
    assert calls == []  # not built more than once


def test_a_model_over_the_limit_is_built_as_today(catalog, tmp_path, monkeypatch):
    """The bottle would move at 12 studs; made over the limit, it is not even tried."""
    monkeypatch.setattr(pipeline, "SEAT_STUDS", 11)
    calls = []
    real = pipeline._seat_measures
    monkeypatch.setattr(pipeline, "_seat_measures", lambda *a: calls.append(1) or real(*a))
    _same_as_today(MODELS / "bottle.glb", 12, tmp_path, catalog, monkeypatch)
    assert calls == []


@pytest.mark.parametrize("studs", [12, 16])
def test_the_size_asked_for_is_never_exceeded(tmp_path, studs):
    """The spaceship is 'studs' long front to back and a little under that from side to side:
    half a stud over in x would make its grid one cell wider than asked for."""
    seed = load_seed(MODELS / "spaceship.glb", studs=studs)
    assert all(sx == 0 for sx, _ in seatings(seed, studs))
    project = make(MODELS / "spaceship.glb", studs=studs, tmp=tmp_path)
    design = project.load_design()
    m = design.seed_offset
    body = design.filled[m[0] : design.shape[0] - m[0], m[1] : design.shape[1] - m[1]]
    assert body.shape[0] <= studs and body.shape[1] <= studs


def test_a_seated_axis_grows_the_grid_by_the_cell_it_needs(catalog):
    seed = load_seed(MODELS / "bottle.glb", studs=12)
    plain, moved = voxelize(seed, catalog), voxelize(seated(seed, (1, 1)), catalog)
    assert moved.shape[0] == plain.shape[0] + 1 and moved.shape[1] == plain.shape[1] + 1
    assert moved.seed_offset == plain.seed_offset
    # a hand-made seed with more offset than slack, not seated, is still moved to 0
    loose = Seed(vertices=seed.vertices + [4.0, 4.0, 0.0], faces=seed.faces)
    assert voxelize(loose, catalog).shape == plain.shape


def test_a_whole_stud_side_is_never_seated():
    box = trimesh.creation.box(bounds=[[0, 0, 0], [4 * S, 3.5 * S, 8.0]])
    seed = Seed(vertices=np.asarray(box.vertices, float), faces=np.asarray(box.faces))
    assert seatings(seed, 4) == [(0, 0), (0, 1)]
    with pytest.raises(ValueError):
        seated(seed, (1, 0))


# ---- the rule ------------------------------------------------------------------------------


def _m(match, sturdy=(5, 2, 10), loose=0, parts=100, fused=0):
    """Measures of one seating: outline per view; sturdiness as ``connect.sturdiness``
    (largest load in parts, lone links, sum of loads); loose parts; parts; fused sections."""
    return {"match": list(match), "sturdy": sturdy, "loose": loose, "parts": parts, "fused": fused}


def test_another_seating_is_taken_only_when_it_is_better_in_every_way():
    today = _m([0.80, 0.80, 0.80])
    good = _m([0.83, 0.82, 0.80])
    assert pipeline.better_seat({(0, 0): today, (1, 0): good}) == (1, 0)
    # less sturdy: a largest load two parts higher, or one higher with more lone links
    for worse in ((7, 2, 10), (6, 3, 10)):
        assert pipeline.better_seat({(0, 0): today, (1, 0): _m(good["match"], worse)}) == (0, 0)
    # one part higher with no more lone links is layout luck; a lower load is sturdier,
    # however many lone links it has
    for fine in ((6, 2, 30), (4, 9, 40)):
        assert pipeline.better_seat({(0, 0): today, (1, 0): _m(good["match"], fine)}) == (1, 0)
    # loose parts
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m(good["match"], loose=1)}) == (0, 0)
    # one view worse by more than a point, though the mean is better
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m([0.85, 0.85, 0.789])}) == (0, 0)
    # one view worse by less than a point is allowed
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m([0.85, 0.85, 0.795])}) == (1, 0)
    # the mean better by less than a point
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m([0.805, 0.81, 0.80])}) == (0, 0)
    # the best of several, not the first that qualifies
    better = _m([0.86, 0.85, 0.80])
    assert pipeline.better_seat({(0, 0): today, (0, 1): good, (1, 1): better}) == (1, 1)


def test_a_seating_that_joins_more_of_the_model_is_refused():
    """Two legs a stud apart filled into one block: better outline, sturdier, refused."""
    today = _m([0.78, 0.72, 0.74], fused=0)
    block = _m([0.87, 0.94, 0.89], (0, 0, 0), fused=13)
    assert pipeline.better_seat({(0, 0): today, (1, 1): block}) == (0, 0)


def test_a_seating_that_keeps_apart_what_today_joins_is_favoured():
    """It is not refused for a loss of up to 5 points in one view, and needs no gain on the
    mean beyond what its extra parts ask; among several, the one that joins fewest wins."""
    today = _m([0.80, 0.80, 0.80], fused=6)
    apart = _m([0.81, 0.78, 0.81], fused=0)  # one view 2 points down, mean the same
    assert pipeline.better_seat({(0, 0): today, (1, 1): apart}) == (1, 1)
    far_down = _m([0.84, 0.74, 0.84], fused=0)  # one view 6 points down: too much
    assert pipeline.better_seat({(0, 0): today, (1, 1): far_down}) == (0, 0)
    worse_mean = _m([0.79, 0.78, 0.80], fused=0)
    assert pipeline.better_seat({(0, 0): today, (1, 1): worse_mean}) == (0, 0)
    likelier = _m([0.90, 0.90, 0.90], fused=4)
    assert pipeline.better_seat({(0, 0): today, (1, 1): apart, (0, 1): likelier}) == (1, 1)


def test_more_parts_must_buy_more_likeness():
    """p per cent more parts asks for 1 + p / 10 points more on the mean; fewer or as many
    parts, the 1 point."""
    today = _m([0.80, 0.80, 0.80], parts=100)
    # 30% more parts needs 4 points: 3.9 is not enough, 4.1 is
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m([0.839] * 3, parts=130)}) == (0, 0)
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m([0.841] * 3, parts=130)}) == (1, 0)
    # fewer parts: 1 point is enough
    assert pipeline.better_seat({(0, 0): today, (1, 0): _m([0.811] * 3, parts=60)}) == (1, 0)


def test_the_pawn_at_sixteen_studs_stays_where_it_was(tmp_path):
    """Half a stud over in x and y its outline is 2 to 4 points better, but it needs 283 parts
    against 185 (53% more, so it would need 6.3 points): it stays."""
    project = make(MODELS / "pawn.stl", studs=16, tmp=tmp_path)
    assert project.seat == (0, 0) and "seat" not in project.meta


def test_one_axis_never_decides_against_its_twin_within_a_point():
    """When the best seating is half a stud over on one axis and the other axis comes within
    a point of it, whether or not that one qualifies, neither decides."""
    today = _m([0.80, 0.80, 0.80])
    side = _m([0.85, 0.85, 0.85])
    near = _m([0.845, 0.845, 0.845], loose=1)  # does not qualify, but is within a point
    assert pipeline.better_seat({(0, 0): today, (1, 0): side, (0, 1): side}) == (0, 0)
    assert pipeline.better_seat({(0, 0): today, (1, 0): side, (0, 1): near}) == (0, 0)
    far = _m([0.83, 0.83, 0.83])  # 2 points behind: the best one-axis seating decides
    assert pipeline.better_seat({(0, 0): today, (1, 0): side, (0, 1): far}) == (1, 0)
    both = _m([0.83, 0.83, 0.83])
    tie = {(0, 0): today, (1, 0): side, (0, 1): side, (1, 1): both}
    assert pipeline.better_seat(tie) == (1, 1)  # (1, 1) qualifies: it is taken
    assert pipeline.better_seat({**tie, (1, 1): _m(both["match"], loose=1)}) == (0, 0)


def test_the_teapot_turned_a_quarter_sits_the_same_way_turned(tmp_path):
    """Usually, not always, true (the layout can differ when the model is turned); true of
    the teapot at 12 studs, which moves half a stud in y, and turned a quarter, in x."""
    mesh = trimesh.load(MODELS / "teapot.glb", force="mesh")
    assert isinstance(mesh, trimesh.Trimesh)
    path = tmp_path / "teapot.glb"
    mesh.export(path)
    turned = mesh.copy()
    # glTF is y up: a quarter turn about the model's up axis is about y in the file
    turned.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    turned_path = tmp_path / "turned.glb"
    turned.export(turned_path)
    a = make(path, studs=12, tmp=tmp_path / "a")
    b = make(turned_path, studs=12, tmp=tmp_path / "b")
    assert a.seat == (0, 1)
    assert b.seat == (1, 0)


# ---- the reviewer's cases, built ------------------------------------------------------------

H = 12 * S  # the shapes below are 12 'studs' tall before ``load_seed`` scales them


def _cyl(d, cx, cy, z0, z1, sections=96, rot=0.0):
    c = trimesh.creation.cylinder(radius=d * S / 2, height=z1 - z0, sections=sections)
    if rot:
        c.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rot), [0, 0, 1]))
    c.apply_translation([cx * S, cy * S, (z0 + z1) / 2])
    return c


def _square(d, cx, cy, z0, z1, rot):
    return _cyl(d / np.cos(np.pi / 4), cx, cy, z0, z1, sections=4, rot=rot)


def test_two_legs_a_stud_apart_are_not_fused_into_one_block(tmp_path):
    """The review's figure-rd-3.0-gap1.0 at 12 studs: two round legs 3 across, 1 apart.
    Half a stud over in x and y both half-covered cells of the gap fill and the legs come out
    one block 7 wide for 13 levels (outline 8 to 21 points better, and sturdier): refused."""
    d, gap = 3.0, 1.0
    zl, zb = 0.45 * H, 0.8 * H
    c0 = d / 2 + 0.3
    c1 = c0 + d + gap
    legs = [_cyl(d, c, 2, 0, zl + 1) for c in (c0, c1)]
    body = trimesh.creation.box(
        bounds=[[0, (2 - 1.7) * S, zl], [(c1 + d / 2 + 0.3) * S, (2 + 1.7) * S, zb]]
    )
    head = trimesh.creation.icosphere(subdivisions=3, radius=1.5 * S)
    head.apply_translation([(c0 + c1) / 2 * S, 2 * S, zb + 1.3 * S])
    path = _stl(tmp_path / "figure.stl", *legs, body, head)
    seed = load_seed(path, studs=12)
    fused: list[int] = []
    voxelize(seated(seed, (1, 1)), load_catalog(), fused=fused)
    assert sum(fused) >= 10  # the block: one more section per level, for its legs' height
    project = make(path, studs=12, tmp=tmp_path)
    assert project.seat == (0, 0)
    joined: list[int] = []
    voxelize(pipeline.load_project_seed(project), load_catalog(), fused=joined)
    assert sum(joined) == 0


def test_a_column_one_stud_across_is_not_taken_for_sturdy(tmp_path):
    """The review's col-round-1.0 at 16 studs: today a 2 x 2 column with one weak spot; half
    a stud over in x and y a 1 x 1 column 40 plates tall, every level a lone link, which the
    old measure read as sturdier (no section of 40 cells can hang on one stud). Refused."""
    path = _stl(tmp_path / "column.stl", _cyl(1.0, 0, 0, 0, H))
    project = make(path, studs=16, tmp=tmp_path)
    assert project.seat == (0, 0)
    f = project.load_design().filled
    level = f[:, :, 20]
    assert level.any(axis=1).sum() == 2 and level.any(axis=0).sum() == 2


def test_the_bottle_at_eight_studs_becomes_a_column_two_studs_across(tmp_path):
    """Today a 1 x 1 stick (63.5/63.8/61.5%, 16 weak spots); half a stud over in x and y a
    2 x 2 column (78.6/78.6/79.5%, one weak spot), which the old measure refused for its one
    section of 64 cells."""
    project = make(MODELS / "bottle.glb", studs=8, tmp=tmp_path)
    assert project.seat == (1, 1)
    f = project.load_design().filled
    level = f[:, :, 6]
    assert level.any(axis=1).sum() >= 2 and level.any(axis=0).sum() >= 2


@pytest.mark.parametrize(
    "name, studs",
    [("mushroom-2.0", 8), ("col-diamond-3.0", 16)],
)
def test_a_model_the_same_after_a_quarter_turn_does_not_come_out_lopsided(tmp_path, name, studs):
    """The review's two lopsided cases: the mushroom on a stem 2 across at 8 studs came out
    with a cap 5 x 6, and the column 3 wide turned 45 degrees at 16 studs lopsided too,
    because half a stud over on one axis won by a hair over the other."""
    if name.startswith("mushroom"):
        z = 0.6 * H
        cap = [(0.0, z), (4.0 * S, z)]
        for k in range(1, 13):
            a = k * np.pi / 24
            cap.append((4.0 * S * np.cos(a), z + (H - z) * np.sin(a)))
        cap.append((0.0, H))
        dome = trimesh.creation.revolve(np.array(cap), sections=96)
        if dome.volume < 0:
            dome.invert()
        dome.apply_translation([4 * S, 4 * S, 0])
        meshes = [_cyl(2.0, 4, 4, 0.0, z + 1.0), dome]
    else:
        meshes = [_square(3.0, 0, 0, 0, H, 0.0)]
    path = _stl(tmp_path / f"{name}.stl", *meshes)
    project = make(path, studs=studs, tmp=tmp_path)
    assert project.seat in ((0, 0), (1, 1))
    f = project.load_design().filled
    m = project.load_design().seed_offset
    body = f[m[0] : f.shape[0] - m[0], m[1] : f.shape[1] - m[1]]
    assert np.array_equal(body, body.transpose(1, 0, 2))  # the same turned a quarter


# ---- what reads the seat -------------------------------------------------------------------


def test_an_old_project_without_a_seat_is_built_and_measured_as_before(catalog, tmp_path):
    project = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path)
    meta = json.loads((project.path / "project.json").read_text())
    del meta["seat"], meta["seat_note"]
    (project.path / "project.json").write_text(json.dumps(meta))
    old = Project(project.path)
    assert old.seat == (0, 0) and old.seat_note is None
    seed = pipeline.load_project_seed(old)
    assert np.array_equal(seed.vertices, load_seed(MODELS / "bottle.glb", studs=12).vertices)
    old.save_design(voxelize(seed, catalog), base=True)
    build, match = built(old, catalog)
    assert not build.notes[0].startswith("When this project was made")
    assert [round(m, 4) for m in match] == [0.7048, 0.7374, 0.7194]  # today's numbers


def test_a_seated_project_lines_up_with_its_model(catalog, tmp_path):
    """The outline match, the comparison picture and the designer's pictures all draw the seed
    through ``load_project_seed``: seated, its silhouette and the build's agree; drawn
    unseated (half a stud off), they agree less."""
    project = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path)
    build, _ = built(project, catalog)
    design = project.load_design()
    seed = pipeline.load_project_seed(project)
    assert seed.seat == (1, 1)
    unseated = load_seed(project.seed_path, studs=12)
    for view in VIEWS:
        b = silhouette(build, catalog, view)
        a = silhouette(seed, catalog, view, grid_shape=build.shape, seed_offset=design.seed_offset)
        off = silhouette(
            unseated, catalog, view, grid_shape=build.shape, seed_offset=design.seed_offset
        )
        here = (a & b).sum() / (a | b).sum()
        there = (off & b).sum() / (off | b).sum()
        assert here >= 0.8 and here > there, (view, here, there)
    picture = pipeline.render_compare(project, catalog=catalog)
    assert picture.exists()


def test_a_chosen_piece_of_a_file_is_seated_and_found_again(tmp_path):
    """Two separate round columns 3.2 studs across in one file: piece 1 alone is made as a
    project, seated, and loading it again gives that piece in that seating."""
    a = trimesh.creation.cylinder(radius=1.6 * S, height=12 * S, sections=96)
    a.apply_translation([0, 0, 6 * S])
    b = trimesh.creation.cylinder(radius=1.0 * S, height=8 * S, sections=96)
    b.apply_translation([8 * S, 0, 4 * S])
    path = _stl(tmp_path / "two.stl", a, b)
    project = make(path, studs=12, tmp=tmp_path / "p", piece=1)
    assert project.piece == 1 and project.seat == (1, 1)
    seed = pipeline.load_project_seed(project)
    alone = load_seed(path, studs=12, piece=1)
    assert np.allclose(seed.vertices[:, :2], alone.vertices[:, :2] + 4.0)
    assert np.array_equal(seed.vertices[:, 2], alone.vertices[:, 2])


# ---- what the reviewer's broken copies showed nothing caught --------------------------------


def _counting(monkeypatch) -> list[int]:
    calls: list[int] = []
    real = pipeline._seat_measures
    monkeypatch.setattr(pipeline, "_seat_measures", lambda *a: calls.append(1) or real(*a))
    return calls


def test_the_limit_is_sixteen_studs_and_no_more(tmp_path, monkeypatch):
    """At 16 studs the bottle moves; at 17 nothing is tried."""
    assert pipeline.SEAT_STUDS == 16
    assert make(MODELS / "bottle.glb", studs=16, tmp=tmp_path / "a").seat == (1, 1)
    calls = _counting(monkeypatch)
    assert make(MODELS / "bottle.glb", studs=17, tmp=tmp_path / "b").seat == (0, 0)
    assert calls == []


def test_a_hollow_model_is_hollow_in_every_seating_tried(catalog, tmp_path, monkeypatch):
    """Every seating tried is converted hollow, as the one kept is."""
    import bricksnap.voxelize as vox

    asked = []
    real = vox.voxelize

    def spy(seed, cat, **kw):
        asked.append((tuple(seed.seat), kw.get("hollow", False)))
        return real(seed, cat, **kw)

    monkeypatch.setattr(vox, "voxelize", spy)
    project = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path, hollow=True)
    assert project.seat == (1, 1)
    assert {s for s, _ in asked} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert all(hollow for _, hollow in asked), asked
    seed = seated(load_seed(MODELS / "bottle.glb", studs=12), (1, 1))
    want = real(seed, catalog, hollow=True)
    assert project.load_design().fingerprint() == want.fingerprint()


def test_a_model_moved_on_one_axis_is_recorded_on_that_axis_and_lines_up(catalog, tmp_path):
    """The teapot at 12 studs sits half a stud over in y only: project.json says [0, 1], and
    the model drawn from the project lines up with its build better than the centred model
    (its x side is a whole number of studs: moved in x it would be damaged)."""
    project = make(MODELS / "teapot.glb", studs=12, tmp=tmp_path)
    assert project.seat == (0, 1) and project.meta["seat"] == [0, 1]
    assert "in y on the grid" in project.meta["seat_note"]
    build, _ = built(project, catalog)
    design = project.load_design()
    plain = load_seed(project.seed_path, studs=12)
    others = [plain]
    for view in ("front", "right"):
        b = silhouette(build, catalog, view)
        ious = []
        for seed in [pipeline.load_project_seed(project), *others]:
            a = silhouette(
                seed, catalog, view, grid_shape=build.shape, seed_offset=design.seed_offset
            )
            ious.append((a & b).sum() / (a | b).sum())
        assert ious[0] >= max(ious[1:]), (view, ious)


@pytest.mark.parametrize("seat", [[2, 0], [1], "yes", [True, False], None])
def test_a_damaged_seat_is_said_plainly_every_way_in(tmp_path, capsys, seat):
    from bricksnap.cli import main
    from bricksnap.project import ProjectError

    project = make(MODELS / "bottle.glb", studs=12, tmp=tmp_path)
    meta = json.loads((project.path / "project.json").read_text())
    meta["seat"] = seat
    (project.path / "project.json").write_text(json.dumps(meta))
    if seat is None:  # null is not "not seated": a damaged record
        with pytest.raises(ProjectError, match="where the model sits on the grid"):
            Project(project.path)
        return
    with pytest.raises(ProjectError, match="where the model sits on the grid"):
        Project(project.path)
    for command in ("check", "versions", "render", "export"):
        code = main([command, str(project.path)])
        out = capsys.readouterr()
        assert code != 0 and "where the model sits on the grid" in out.out + out.err, command


def test_a_whole_stud_side_marked_seated_is_said_plainly_every_way_in(tmp_path, capsys):
    from bricksnap.cli import main
    from bricksnap.project import ProjectError

    box = trimesh.creation.box(bounds=[[0, 0, 0], [4 * S, 3 * S, 9.6 * 2]])
    project = make(_stl(tmp_path / "box.stl", box), studs=4, tmp=tmp_path / "p")
    pipeline.rebuild(project)
    project.meta["seat"], project.meta["seat_note"] = [1, 0], "x"
    project.save_meta()
    opened = Project(project.path)
    with pytest.raises(ProjectError, match="where the model sits on the grid"):
        pipeline.load_project_seed(opened)
    with pytest.raises(ProjectError, match="where the model sits on the grid"):
        pipeline.render_compare(opened)
    for command in ("check", "versions", "render", "export", "instructions"):
        code = main([command, str(project.path)])
        out = capsys.readouterr()
        assert code != 0 and "where the model sits on the grid" in out.out + out.err, command


def test_the_command_line_says_while_it_tries_the_seatings(tmp_path, capsys):
    from bricksnap.cli import main

    main(["new", str(MODELS / "bottle.glb"), "--studs", "12", "--dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Trying 4 ways of setting the model on the grid" in out
    assert "When this project was made the model was set half a stud over in x and y" in out
