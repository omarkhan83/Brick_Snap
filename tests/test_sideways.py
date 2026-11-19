"""End to end: round-tile eyes lying on the front of the sample cat's head (stage 4, sideways
parts). The cat is made and rebuilt once for the module (a few seconds)."""

from __future__ import annotations

import numpy as np
import pytest

from bricksnap import render as R
from bricksnap.connect import connection_graph
from bricksnap.design import apply_ops
from bricksnap.export import parts_list
from bricksnap.instructions import plan_steps, where_words
from bricksnap.ldraw import SIDEWAYS_MATRICES, format_number, placement_to_ldraw
from bricksnap.pipeline import create_project, rebuild
from bricksnap.types import Build

CAT = "samples/models/cat.glb"
# the cat at 16 studs: the face of its head is at y = 4 from z = 18 up; the eyes go in the
# column in front of it, y = 3, at the brick course z = 18..20, x = 5 and its mirror x = 8.
# The cells behind them are painted the face's colour first (they are partly black), so the
# eyes read as round. White round tiles go on the right side of the head (x = 9, cells in
# front at x = 10) and, mirrored, on its left.
FACE = {"type": "box", "min": [5, 4, 18], "max": [5, 4, 20]}
EYES = {"op": "place_detail", "part": "98138", "color": 0, "at": [5, 3, 18], "face": "front"}
CHEEK = {"op": "place_detail", "part": "98138", "color": 15, "at": [10, 5, 21], "face": "right"}


@pytest.fixture(scope="module")
def cat(tmp_path_factory, catalog):
    project = create_project(CAT, studs=16, directory=tmp_path_factory.mktemp("cat"))
    design = project.load_design()
    ops = [
        {"op": "paint", "shape": FACE, "color": 72, "mirror": True},
        {**EYES, "mirror": True},
        {**CHEEK, "mirror": True},
    ]
    results = apply_ops(design, ops, catalog)
    project.save_design(design)
    build = rebuild(project, catalog=catalog)
    return project, design, results, build


def test_the_eyes_are_placed_on_the_face(cat):
    _, design, results, _ = cat
    assert all(r.applied for r in results), [r.message for r in results]
    assert "a Dark Bluish Grey (72) brick with a stud on its side" in results[1].message
    assert [(d.x, d.y, d.z, d.face) for d in design.details] == [
        (5, 3, 18, "front"),
        (8, 3, 18, "front"),
        (10, 5, 21, "right"),
        (3, 5, 21, "left"),
    ]


def test_the_build_holds_with_two_side_stud_bricks_and_two_sideways_eyes(cat, catalog):
    _, _, _, build = cat
    assert build.report is not None and build.report.ok, build.report.text
    assert build.report.loose == []
    bricks = [i for i, p in enumerate(build.parts) if p.part == "87087"]
    eyes = [i for i, p in enumerate(build.parts) if p.part == "98138"]
    assert len(bricks) == 4 and len(eyes) == 4
    assert sorted((build.parts[i].x, build.parts[i].y, build.parts[i].z) for i in bricks) == [
        (4, 5, 21),
        (5, 4, 18),
        (8, 4, 18),
        (9, 5, 21),
    ]
    rots = {(build.parts[i].x, build.parts[i].z): build.parts[i].rot for i in bricks}
    assert rots == {(5, 18): 0, (8, 18): 0, (9, 21): 90, (4, 21): 270}
    g = connection_graph(build, catalog)
    for i in eyes:
        p = build.parts[i]
        assert p.rot == 0 and (p.face, p.color) in (("front", 0), ("right", 15), ("left", 15))
        (holder,) = list(g.adj[i])
        assert holder in bricks and g.edges[i, holder]["studs"] == 1
        assert p.step > build.parts[holder].step


def test_the_ldraw_file_and_the_parts_list_have_them(cat, catalog):
    project, _, _, build = cat
    text = project.ldraw_path.read_text(encoding="utf-8")
    eyes = [p for p in build.parts if p.part == "98138"]
    for p in eyes:
        position, matrix = placement_to_ldraw(p, catalog)
        assert matrix == SIDEWAYS_MATRICES[p.face]
        numbers = " ".join(format_number(v) for v in (*position, *matrix))
        assert f"1 {p.color} {numbers} 98138.dat" in text
    assert text.count("87087.dat") == 4
    lines = {(line.part, line.colour): line.quantity for line in parts_list(build, catalog)}
    assert lines[("98138", 0)] == 2 and lines[("98138", 15)] == 2
    assert sum(q for (part, _), q in lines.items() if part == "87087") == 4


def test_nothing_behind_the_eyes_was_repainted_at_rebuild(cat):
    _, _, _, build = cat
    assert not [n for n in build.notes if "one brick with a stud on its side" in n]
    assert not [n for n in build.notes if n.startswith("Left off")]


def test_the_front_picture_shows_two_round_eyes(cat, catalog):
    _, _, _, build = cat
    s = 16
    frame = R.view_frame(build.shape, "front", px_per_stud=s, labels=False)
    owner = R.part_map(build, catalog, "front", px_per_stud=s)
    picture = np.asarray(R.render_build(build, catalog, "front", px_per_stud=s, labels=False))
    for x in (5, 8):
        eye = next(
            i
            for i, p in enumerate(build.parts)
            if p.part == "98138" and (p.x, p.face) == (x, "front")
        )
        brick = next(i for i, p in enumerate(build.parts) if p.part == "87087" and p.x == x)

        def at(gx: float, gz: float) -> tuple[int, int]:
            col, row, _ = frame.project([(gx, 3.5, gz)])[0]
            return int(row), int(col)

        # the middle of the tile (on the side stud, 1.75 plates up the column) shows the eye,
        # dark; a corner of its square, outside the circle, shows the brick behind
        centre = at(x + 0.5, 19.75)
        assert owner[centre] == eye
        assert picture[centre].max() < 80
        assert owner[at(x + 0.1, 20.9)] == brick
        # it is round: as wide across as it is tall, about one stud
        rows, cols = np.nonzero(owner == eye)
        assert abs((cols.max() - cols.min()) - (rows.max() - rows.min())) <= 2
        assert s - 3 <= cols.max() - cols.min() + 1 <= s


def test_seen_from_the_side_an_eye_is_a_thin_edge(cat, catalog):
    _, _, _, build = cat
    owner = R.part_map(build, catalog, "right", px_per_stud=16)
    eye = next(
        i for i, p in enumerate(build.parts) if p.part == "98138" and (p.x, p.face) == (8, "front")
    )
    rows, cols = np.nonzero(owner == eye)
    assert len(cols) and cols.max() - cols.min() + 1 <= 16 * 0.4 + 2  # 8 LDU thick
    for view in ("iso", "top"):  # face-on in iso, an edge from above
        assert R.part_pixels(build, catalog, view).get(eye, 0) > 0
    assert R.part_pixels(build, catalog, "iso_back").get(eye, 0) == 0  # behind the head


def test_the_booklet_says_where_an_eye_goes(cat, catalog):
    _, _, _, build = cat
    eye = next(i for i, p in enumerate(build.parts) if p.part == "98138")
    words = where_words(build, catalog, eye)
    assert "pushed onto the stud on the front side of" in words
    plans = plan_steps(build, catalog)
    assert any(eye in plan.parts for plan in plans)


def test_without_its_brick_an_eye_is_left_off_with_a_note(catalog, cat):
    from bricksnap.finish import finish

    project, design, _, build = cat
    plain = Build(
        shape=build.shape,
        parts=[
            p.__class__(**{**p.__dict__, "part": "3005"}) if p.part == "87087" else p
            for p in build.parts
            if p.part != "98138"
        ],
    )
    out = finish(plain, design, catalog)
    assert not [p for p in out.parts if p.part == "98138"]
    assert any("has no stud on that side to hold it" in n for n in out.notes)


def test_a_detail_on_the_right_face_and_its_mirror_on_the_left(cat, catalog):
    _, _, _, build = cat
    for face, view, x in (("right", "right", 10), ("left", "left", 3)):
        i = next(k for k, p in enumerate(build.parts) if p.face == face)
        p = build.parts[i]
        assert (p.x, p.y, p.z, p.color) == (x, 5, 21, 15)
        # face-on in the view it faces: a white disc one stud across
        owner = R.part_map(build, catalog, view, px_per_stud=16)
        rows, cols = np.nonzero(owner == i)
        assert 13 <= cols.max() - cols.min() + 1 <= 16
        assert abs((cols.max() - cols.min()) - (rows.max() - rows.min())) <= 2
        # edge-on from the front, against the head's side
        owner = R.part_map(build, catalog, "front", px_per_stud=16)
        rows, cols = np.nonzero(owner == i)
        assert cols.max() - cols.min() + 1 <= 16 * 0.4 + 2
    assert "pushed onto the stud on the right side of" in where_words(
        build, catalog, next(k for k, p in enumerate(build.parts) if p.face == "right")
    )
