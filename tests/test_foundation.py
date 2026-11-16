"""Tests for the shared pieces every module relies on: types, catalogue, connection rules."""

from __future__ import annotations

import numpy as np

from bricksnap.connect import connection_graph, occupancy
from bricksnap.project import Project, slug
from bricksnap.types import EMPTY, Build, Design, Detail, Placement, Report


def test_design_round_trip(tmp_path):
    colors = np.full((4, 3, 6), EMPTY, dtype=np.int16)
    colors[1:3, :, :3] = 4
    d = Design(colors=colors, seed_offset=(2, 2, 0))
    d.details.append(Detail(part="98138", color=0, x=1, y=0, z=3))
    d.log.append(
        {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 1, 1]}, "color": 4}
    )
    d.save(tmp_path / "d.npz", tmp_path / "d.json")
    e = Design.load(tmp_path / "d.npz", tmp_path / "d.json")
    assert np.array_equal(e.colors, d.colors) and e.seed_offset == (2, 2, 0)
    assert e.details == d.details and e.log == d.log
    assert e.shape == (4, 3, 6) and int(e.filled.sum()) == 2 * 3 * 3
    c = d.copy()
    c.colors[0, 0, 0] = 1
    assert d.colors[0, 0, 0] == EMPTY


def test_build_round_trip(tmp_path):
    b = Build(
        shape=(4, 4, 6),
        parts=[Placement("3001", 4, 0, 0, 0, rot=0, step=1)],
        report=Report(ok=True, text="fine"),
    )
    b.save(tmp_path / "b.json")
    assert Build.load(tmp_path / "b.json") == b


def test_catalogue_geometry(catalog):
    brick = Placement("3001", 4, 2, 3, 0)  # 2x4 brick: 4 studs along its own X
    assert catalog.footprint(brick) == (4, 2, 3)
    turned = Placement("3001", 4, 2, 3, 0, rot=90)
    assert catalog.footprint(turned) == (2, 4, 3)
    assert sorted(catalog.stud_cells(turned)) == [(x, y) for x in (2, 3) for y in (3, 4, 5, 6)]
    part, rot = catalog.find("plate", 1, 4)
    assert part.kind == "plate" and {part.sx, part.sz} == {1, 4} and rot == 90
    assert catalog.exists("3001", 4) and not catalog.exists("3001", 99999)
    assert catalog.nearest_colour((250, 5, 5)) == 4


def test_connection_rules(catalog):
    # two 2x4 bricks side by side do not hold each other; a third laid across them joins them
    parts = [Placement("3001", 4, 0, 0, 0), Placement("3001", 4, 4, 0, 0)]
    build = Build(shape=(8, 2, 6), parts=list(parts))
    occ, collisions, oob, unknown = occupancy(build, catalog)
    assert not collisions and not oob and not unknown and (occ >= 0).sum() == 2 * 4 * 2 * 3
    assert connection_graph(build, catalog).number_of_edges() == 0
    build.parts.append(Placement("3001", 4, 2, 0, 3))
    g = connection_graph(build, catalog)
    assert sorted(g.edges()) == [(0, 2), (1, 2)] and g[0][2]["studs"] == 4


def test_collisions_and_bounds(catalog):
    build = Build(
        shape=(4, 2, 3),
        parts=[
            Placement("3001", 4, 0, 0, 0),
            Placement("3003", 4, 3, 0, 0),
            Placement("3005", 4, 9, 9, 0),
            Placement("nope", 4, 0, 0, 0),
        ],
    )
    _, collisions, oob, unknown = occupancy(build, catalog)
    # parts that stick out of the grid are reported as out of bounds, not as collisions
    assert collisions == [] and oob == [1, 2]
    assert unknown == [3]


def test_project_folder(tmp_path, pawn_path):
    p = Project.create(tmp_path / "pawn", pawn_path, studs=16, name="Pawn")
    assert p.seed_path.exists() and p.meta["studs"] == 16 and p.name == "Pawn"
    d = Design(colors=np.zeros((2, 2, 3), dtype=np.int16))
    p.save_design(d, base=True)
    assert Project(tmp_path / "pawn").load_design(base=True).shape == (2, 2, 3)
    assert slug("My Cat! (v2)") == "my-cat-v2"


def test_overlapping_parts_collide(catalog):
    build = Build(
        shape=(6, 2, 3), parts=[Placement("3001", 4, 0, 0, 0), Placement("3001", 4, 2, 0, 0)]
    )
    assert occupancy(build, catalog)[1] == [(0, 1)]


def test_design_fingerprint_follows_what_a_build_depends_on():
    colors = np.full((4, 4, 6), EMPTY, dtype=np.int16)
    colors[1:3, 1:3, 0:3] = 4
    design = Design(colors=colors)
    same = design.copy()
    same.log.append({"op": "paint"})  # the log does not change what gets built
    assert same.fingerprint() == design.fingerprint()
    painted = design.copy()
    painted.colors[1, 1, 0] = 1
    assert painted.fingerprint() != design.fingerprint()
    smooth = design.copy()
    assert smooth.finish is not None
    smooth.finish[1, 1, 2] = 1
    assert smooth.fingerprint() != design.fingerprint()


def test_build_remembers_the_design_it_came_from(tmp_path, pawn_path):
    from bricksnap.pipeline import create_project, rebuild

    project = create_project(pawn_path, studs=8, directory=tmp_path)
    assert not project.build_is_current()  # nothing built yet
    build = rebuild(project)
    assert build.design_id == project.load_design().fingerprint()
    assert project.build_is_current()
    design = project.load_design()
    design.colors[design.filled] = 4
    project.save_design(design)
    assert not project.build_is_current()
    rebuild(project)
    assert project.build_is_current()
    # nothing is left behind by the save-then-move writes
    assert not [f.name for f in project.path.iterdir() if ".tmp" in f.name]


def test_a_build_saved_before_design_ids_existed_counts_as_out_of_date(tmp_path, pawn_path):
    from bricksnap.pipeline import create_project, rebuild

    project = create_project(pawn_path, studs=8, directory=tmp_path)
    build = rebuild(project)
    build.design_id = ""
    project.save_build(build)
    assert Build.load(project.build_path).design_id == ""
    assert not project.build_is_current()


def test_low_side_turns_with_the_part_and_agrees_with_the_ldraw_matrix(catalog):
    """The direction a slope descends must be the same in the grid and in the LDraw file."""
    from bricksnap.ldraw import placement_to_ldraw

    slopes = [p for p in catalog.parts.values() if p.slope]
    assert {"3040b", "3039", "54200", "85984"} <= {p.id for p in slopes}
    sides = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
    for part in slopes:
        colour = min(part.colours)
        local = sides[part.slope["low_side"]]
        seen = set()
        for rot in (0, 90, 180, 270):
            p = Placement(part.id, colour, 3, 4, 0, rot=rot)
            low = catalog.low_side(p)
            assert low is not None
            seen.add(low)
            # the rotation matrix of the LDraw line, row by row: a b c / d e f / g h i
            _, nums = placement_to_ldraw(p, catalog)
            world_x = sum(nums[0 + k] * local[k] for k in range(3))
            world_z = sum(nums[6 + k] * local[k] for k in range(3))
            # grid x is LDraw X, grid y is LDraw Z
            assert (round(world_x), round(world_z)) == low, (part.id, rot)
            # the stud cells are on the side away from the low edge
            w, d, _ = catalog.footprint(p)
            for sx_, sy_ in catalog.stud_cells(p):
                assert 3 <= sx_ < 3 + w and 4 <= sy_ < 4 + d
        assert seen == {(1, 0), (-1, 0), (0, 1), (0, -1)}
    assert catalog.low_side(Placement("3001", 4, 0, 0, 0)) is None


def test_slope_studs_sit_on_the_high_side(catalog):
    p = Placement("3040b", 4, 5, 5, 0, rot=0)
    low = catalog.low_side(p)
    assert low is not None
    (stud,) = catalog.stud_cells(p)
    w, d, _ = catalog.footprint(p)
    cells = [(5 + i, 5 + j) for i in range(w) for j in range(d)]
    (slanted,) = [c for c in cells if c != stud]
    # going from the stud cell to the slanted cell is going downhill
    assert (slanted[0] - stud[0], slanted[1] - stud[1]) == low


def test_build_notes_round_trip(tmp_path):
    b = Build(shape=(2, 2, 3), parts=[Placement("3005", 4, 0, 0, 0)], notes=["Added 2 cells."])
    b.save(tmp_path / "b.json")
    assert Build.load(tmp_path / "b.json").notes == ["Added 2 cells."]


def test_colours_snap_the_way_eyes_judge_them(catalog):
    name = {c.code: c.name for c in catalog.colours.values()}
    cases = {
        (0, 0, 0): "Black",
        (20, 20, 20): "Black",
        (255, 255, 255): "White",
        (250, 5, 5): "Red",
        (215, 80, 50): "Red",  # an orange-red car body, not Dark Orange
        (105, 105, 105): "Dark Bluish Grey",
        (128, 128, 128): "Light Bluish Grey",  # a neutral grey stays grey, not Dark Tan
        (160, 160, 160): "Light Bluish Grey",
        (255, 220, 0): "Yellow",
        (20, 80, 200): "Blue",  # not Medium Lilac
        (10, 120, 40): "Green",
        (255, 140, 0): "Orange",
        (255, 192, 203): "Bright Pink",
        (60, 40, 20): "Dark Brown",
        (232, 97, 71): "Red",  # the sample car's coral body: not Nougat, a skin-tone brown
        (210, 180, 140): "Tan",
        (70, 74, 76): "Dark Bluish Grey",
        (240, 200, 60): "Yellow",
    }
    for rgb, want in cases.items():
        assert name[catalog.nearest_colour(rgb)] == want, rgb
    # every catalogue colour snaps to itself, and the batch version agrees with the single one
    solid = [c for c in catalog.colours.values() if not c.transparent]
    batch = catalog.nearest_colours(np.array([c.rgb for c in solid]))
    assert batch.tolist() == [c.code for c in solid]
    assert catalog.nearest_colour(catalog.colours[36].rgb) != 36  # transparent only on request
    assert catalog.nearest_colour(catalog.colours[36].rgb, solid_only=False) in (4, 36)


def test_colour_difference_matches_published_values(monkeypatch):
    """A few of the reference pairs published with the CIEDE2000 formula (Sharma et al.)."""
    from bricksnap.catalog import _colour_difference

    pairs = [
        ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
        ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
        ((50, -1.3802, -84.2814), (50, 0, -82.7485), 1.0000),
        ((50, 2.5, 0), (73, 25, -18), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
        ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
    ]
    import bricksnap.catalog as cat_module

    monkeypatch.setattr(cat_module, "_K_LIGHTNESS", 1.0)  # the published values use 1:1:1
    for a, b, want in pairs:
        got = _colour_difference(np.array([a], dtype=float), np.array([b], dtype=float))[0, 0]
        assert abs(got - want) < 1e-4, (a, b, got)


def test_rough_build_is_the_plain_conversion_and_is_reused(tmp_path, pawn_path):
    from bricksnap.pipeline import create_project, rebuild, rough_build

    project = create_project(pawn_path, studs=8, directory=tmp_path)
    rebuild(project)
    design = project.load_design()
    design.colors[design.filled] = 4  # an edit: the current build changes, the rough one does not
    project.save_design(design)
    rebuild(project)
    rough = rough_build(project)
    assert rough.report is not None and rough.report.ok
    assert {p.color for p in rough.parts} != {4}
    assert rough.design_id == project.load_design(base=True).fingerprint()
    stamp = project.rough_build_path.read_bytes()
    assert rough_build(project).parts == rough.parts
    assert project.rough_build_path.read_bytes() == stamp


def test_the_colour_shortlist_never_changes_the_answer(catalog):
    """nearest_colours measures only a shortlist exactly; it must agree with measuring all."""
    import bricksnap.catalog as cat_module

    rng = np.random.default_rng(11)
    rgb = np.concatenate(
        [
            rng.integers(0, 256, size=(60_000, 3)),
            np.array([c.rgb for c in catalog.colours.values()]),
            np.array([[v, v, v] for v in range(256)]),  # every grey
        ]
    ).astype(np.float64)
    solid = [c for c in catalog.colours.values() if not c.transparent]
    palette = cat_module._rgb_to_lab(np.array([c.rgb for c in solid], dtype=np.float64))
    exact = cat_module._colour_difference(cat_module._rgb_to_lab(rgb), palette).argmin(axis=1)
    want = np.array([c.code for c in solid])[exact]
    assert np.array_equal(catalog.nearest_colours(rgb), want)
