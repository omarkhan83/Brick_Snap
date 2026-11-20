"""Tests for bricksnap/pieces.py: a model file that looks like several separate pieces.

False alarms are worse than misses, so every sample model and every sample project's source
must be found to be one object, and so must the single objects the review built (a halo, a
table, a tree, blocks over a slab, double-sided and unwelded spheres). The other cases are
built here with trimesh.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh
from PIL import Image

from bricksnap import pieces as P
from bricksnap.pieces import find_pieces, parse_choice, resolve
from bricksnap.pipeline import (
    create_project,
    load_project_seed,
    rebuild,
    render_compare,
    rough_build,
)
from bricksnap.project import Project, ProjectError
from bricksnap.seed import load_mesh, load_seed
from bricksnap.types import SeedError

REPO = Path(__file__).resolve().parent.parent
SAMPLES = sorted(
    [p for p in (REPO / "samples" / "models").iterdir() if p.suffix != ".md"]
    + list((REPO / "samples" / "projects").glob("*/seed.*"))
)


def _box(size, at=(0, 0, 0)) -> trimesh.Trimesh:
    m = trimesh.creation.box(extents=size)
    m.apply_translation(np.asarray(at, dtype=float) + np.asarray(size, dtype=float) / 2)
    return m


def _ball(radius, at, subdivisions=2) -> trimesh.Trimesh:
    m = trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius)
    m.apply_translation(at)
    return m


def _stl(path: Path, *meshes: trimesh.Trimesh) -> Path:
    joined: Any = trimesh.util.concatenate(list(meshes))
    joined.export(path)
    return path


def _kit(tmp_path: Path) -> Path:
    """Three pieces apart on a print bed (z up): a bar 40 long, a ball 16 across and a
    block 20 x 20 x 9, all standing on z = 0."""
    return _stl(
        tmp_path / "kit.stl",
        _box((40, 20, 10)),
        _ball(8, (8, 45, 8)),
        _box((20, 20, 9), at=(60, 0, 0)),
    )


def _signed_volume(vertices: np.ndarray, faces: np.ndarray) -> float:
    tri = vertices[faces]
    return float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)


# ---- no false alarms ------------------------------------------------------------------------


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_sample_model_is_taken_for_several_pieces(path: Path) -> None:
    found = find_pieces(path)
    assert not found.several and found.count == 1, found.pieces
    assert found.to_json(16)["pieces"] == []


def _halo(tmp_path: Path) -> Path:
    ring: Any = trimesh.creation.annulus(r_min=6, r_max=9, height=1)
    ring.apply_translation((10, 10, 70))
    return _stl(tmp_path / "halo.stl", _box((20, 20, 60)), ring)


def _table(tmp_path: Path) -> Path:
    legs = [_box((5, 5, 68), (x, y, 0)) for x in (0, 95) for y in (0, 55)]
    return _stl(tmp_path / "table.stl", _box((100, 60, 4), (0, 0, 70)), *legs)


def _tree(tmp_path: Path) -> Path:
    """A trunk with 300 separate, overlapping leaves in a dense crown over it."""
    rng = np.random.default_rng(0)
    leaves = [
        _ball(
            3, (50 + rng.uniform(-18, 18), 50 + rng.uniform(-18, 18), 80 + rng.uniform(-12, 12)), 1
        )
        for _ in range(300)
    ]
    return _stl(tmp_path / "tree.stl", _box((10, 10, 70), (45, 45, 0)), *leaves)


def _hovering(tmp_path: Path) -> Path:
    blocks = [_box((20, 20, 20), (x, y, 6)) for x in (10, 70) for y in (10, 70)]
    return _stl(tmp_path / "hover.stl", _box((100, 100, 5)), *blocks)


def _double_sided(tmp_path: Path) -> Path:
    s = _ball(50, (0, 0, 0), 5)  # 20,480 faces, each written twice
    faces = np.vstack([s.faces, s.faces[:, ::-1]])
    trimesh.Trimesh(s.vertices, faces, process=False).export(tmp_path / "double.stl")
    return tmp_path / "double.stl"


def _unwelded(tmp_path: Path) -> Path:
    s = _ball(50, (0, 0, 0), 6)  # 81,920 faces sharing no vertex
    loose = s.vertices[s.faces].reshape(-1, 3)
    faces = np.arange(len(loose)).reshape(-1, 3)
    trimesh.Trimesh(loose, faces, process=False).export(tmp_path / "unwelded.stl")
    return tmp_path / "unwelded.stl"


@pytest.mark.parametrize(
    "make", [_halo, _table, _tree, _hovering, _double_sided, _unwelded], ids=lambda f: f.__name__
)
def test_one_object_is_one_piece(tmp_path: Path, make: Any) -> None:
    found = find_pieces(make(tmp_path))
    assert not found.several, [p.size for p in found.pieces]


def test_one_object_made_of_overlapping_meshes_is_one_piece(tmp_path: Path) -> None:
    head = _ball(10, (0, 0, 30))
    eyes = [_ball(2, (4, -9, 33)), _ball(2, (-4, -9, 33))]  # pushed into the head
    body = _box((16, 12, 22), at=(-8, -6, 0))
    wheels = [_ball(4, (x, -7, 3)) for x in (-6, 6)]  # against the body
    hat = _box((14, 14, 4), at=(-7, -7, 40))  # resting on the head
    assert not find_pieces(_stl(tmp_path / "figure.stl", head, *eyes, body, *wheels, hat)).several


def test_details_floating_beside_a_figure_are_asked_about(tmp_path: Path) -> None:
    """Pinned as the question the rule knowingly asks: one island is one piece."""
    figure = _box((20, 20, 60))
    left, right = _box((15, 6, 5), at=(40, 0, 45)), _box((15, 6, 5), at=(-35, 0, 45))
    found = find_pieces(_stl(tmp_path / "figure.stl", figure, left, right))
    assert found.several and len(found.everything) == 3
    assert np.allclose(found.pieces[0].size, (20, 20, 60))


def test_a_sparse_tree_of_separate_leaf_clusters_is_asked_about(tmp_path: Path) -> None:
    trunk = _box((6, 6, 60), (27, 27, 0))
    clusters = [_ball(6, (x, y, 70)) for x, y in ((0, 0), (60, 0), (0, 60), (60, 60))]
    found = find_pieces(_stl(tmp_path / "sparse.stl", trunk, *clusters))
    assert found.several and len(found.everything) == 5


@pytest.mark.parametrize("rise", [0, 1, 3, 6, 10])
def test_five_blocks_in_a_row_are_five_pieces_whatever_their_heights(
    tmp_path: Path, rise: float
) -> None:
    parts = [_box((30, 30, 20), at=(42 * i, 0, rise * i)) for i in range(5)]
    found = find_pieces(_stl(tmp_path / "row.stl", *parts))
    assert found.several and len(found.everything) == 5
    for n in range(1, 6):
        assert len(load_seed(tmp_path / "row.stl", studs=8, piece=n).faces) == 12
    raised = [_box((30, 30, 20), at=(42 * i, 0, 0)) for i in range(4)]
    raised.append(_box((30, 30, 20), at=(168, 0, 6)))
    assert len(find_pieces(_stl(tmp_path / "raised.stl", *raised)).everything) == 5


def test_tiny_bits_on_the_ground_are_not_offered_and_are_left_out(tmp_path: Path) -> None:
    path = _stl(
        tmp_path / "bits.stl",
        _box((50, 20, 10)),
        _box((40, 20, 10), at=(0, 40, 0)),
        _box((3, 3, 3), at=(80, 0, 0)),  # under a tenth of the longest piece
        _box((2, 2, 2), at=(80, 40, 0)),
    )
    found = find_pieces(path)
    assert found.several and found.count == 2 and found.small_bits == 2
    assert any("2 small bits" in line for line in found.lines(10))
    alone = load_seed(path, studs=10, piece=1)
    assert len(alone.faces) == 12
    together = load_seed(path, studs=10)
    assert len(together.faces) == 48


def test_flat_islands_are_not_pieces(tmp_path: Path) -> None:
    sheets = trimesh.Trimesh(
        np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [20, 0, 0], [30, 0, 0], [20, 10, 0]], float),
        np.array([[0, 1, 2], [3, 4, 5]]),
        process=False,
    )
    path = tmp_path / "sheets.stl"
    sheets.export(path)
    assert not find_pieces(path).several  # and load_seed then says it is flat, as before
    with pytest.raises(SeedError, match="flat"):
        load_seed(path, studs=8)
    path = _stl(tmp_path / "one-and-a-sheet.stl", _box((20, 20, 20)), sheets)
    assert not find_pieces(path).several


def test_a_scatter_is_not_a_kit(tmp_path: Path) -> None:
    rng = np.random.default_rng(2)
    many = [_box((3, 3, 3), at=(x * 6, y * 6, 0)) for x in range(9) for y in range(9)]
    found = find_pieces(_stl(tmp_path / "grid.stl", *many))
    assert not found.several and found.reason == "scatter"  # 81 islands
    assert found.note() == (
        "grid.stl has 81 separate parts seen from above, too many to be a kit; they are "
        "built together."
    )
    forty = [_box((20, 20, 10), at=(30 * (i % 7), 30 * (i // 7), 0)) for i in range(40)]
    assert len(find_pieces(_stl(tmp_path / "forty.stl", *forty)).everything) == 40
    pts = rng.uniform(0, 100, (27000, 3))
    tri = np.stack([pts, pts + [0.1, 0, 0], pts + [0, 0.1, 0.1]], axis=1)
    dust = trimesh.Trimesh(tri.reshape(-1, 3), np.arange(81000).reshape(-1, 3), process=False)
    dust.export(tmp_path / "dust.stl")
    found = find_pieces(tmp_path / "dust.stl")
    assert not found.several
    assert len(json.dumps(found.to_json(16))) < 400


def test_dust_is_not_a_kit(tmp_path: Path) -> None:
    rng = np.random.default_rng(5)
    specks = [
        _box((0.5, 0.5, 0.5), at=rng.uniform(0, 200, 3)) for _ in range(P.MAX_SMALL_BITS + 50)
    ]
    two = [_box((30, 30, 10), at=(0, 0, 0)), _box((30, 30, 10), at=(250, 250, 0))]
    found = find_pieces(_stl(tmp_path / "dust.stl", *two, *specks))
    assert not found.several and found.reason == "dust" and found.note() is not None
    few = find_pieces(_stl(tmp_path / "few.stl", *two, *specks[:20]))
    assert few.several and few.small_bits == 20


def test_the_grid_gets_coarser_when_the_samples_would_be_too_many(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bricksnap.pieces import _islands

    kit = _kit(tmp_path)
    vertices, faces, _, _, _ = load_mesh(kit)
    xy = vertices[faces][:, :, :2]
    lo, hi = vertices.min(axis=0)[:2], vertices.max(axis=0)[:2]
    _, _, fine = _islands(xy, lo, hi)
    monkeypatch.setattr(P, "SAMPLES", 2_000)
    labels, _, coarse = _islands(xy, lo, hi)
    assert coarse > fine * 4 and labels.shape[1] < P.GRID / 4
    monkeypatch.setattr(P, "SAMPLES", 40_000_000)
    monkeypatch.setattr(P, "MAX_FILLS", 0)  # no filling allowed at any size but the coarsest
    _, _, filled = _islands(xy, lo, hi)
    assert filled > fine


# ---- finding the pieces ---------------------------------------------------------------------


def test_separate_pieces_are_found_and_numbered_by_longest_side(tmp_path: Path) -> None:
    found = find_pieces(_kit(tmp_path))
    assert found.several and found.count == 3
    sizes = [p.size for p in found.pieces]
    assert np.allclose(sizes[0], (40, 20, 10))
    assert np.allclose(sizes[1], (20, 20, 9))  # 20 long, before the ball 16 across
    assert np.allclose(sizes[2], (16, 16, 16), atol=0.01)
    assert np.allclose(found.whole, (80, 53, 16))
    assert found.pieces[0].box == ((0.0, 0.0, 0.0), (40.0, 20.0, 10.0))


def test_a_long_rod_is_the_largest(tmp_path: Path) -> None:
    found = find_pieces(
        _stl(tmp_path / "rod.stl", _box((100, 3, 3)), _box((30, 30, 30), (0, 20, 0)))
    )
    assert found.several
    assert np.allclose(found.pieces[0].size, (100, 3, 3))
    assert max(found.within(1, 20)) == pytest.approx(20)
    assert "the largest piece would be about 20 studs long" in found.lines(20)[1]


def test_twelve_plates_close_together_and_diagonal_bars_are_found(tmp_path: Path) -> None:
    plates = [_box((45, 45, 10), (i * 48, j * 48, 0)) for i in range(4) for j in range(3)]
    found = find_pieces(_stl(tmp_path / "plates.stl", *plates))
    assert found.several and found.count == 12 and found.more == 0
    bars: Any = trimesh.util.concatenate([_box((100, 8, 8)), _box((100, 8, 8), (0, 14, 0))])
    bars.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 4, (0, 0, 1)))
    bars.export(tmp_path / "diagonal.stl")
    assert find_pieces(tmp_path / "diagonal.stl").count == 2


def test_at_most_a_dozen_are_offered(tmp_path: Path) -> None:
    parts = [_box((30 - i, 10, 5), (0, i * 15, 0)) for i in range(15)]
    found = find_pieces(_stl(tmp_path / "fifteen.stl", *parts))
    assert found.several and found.count == 12 and found.more == 3
    assert [p.size[0] for p in found.pieces] == [30 - i for i in range(12)]
    assert any("...and 3 smaller pieces, numbered 13 to 15" in line for line in found.lines(20))
    with pytest.raises(SeedError, match="no piece 13"):
        resolve(13, found)
    assert resolve(14, found, any_piece=True) == 14  # the command line takes any piece
    fourteenth = load_seed(tmp_path / "fifteen.stl", studs=8, piece=14)
    assert len(fourteenth.faces) == 12
    # piece 14 is the box 17 long and 10 deep: alone, 8 studs (64 mm) along its 17
    assert np.allclose(np.ptp(fourteenth.vertices, axis=0)[:2], (64, 64 * 10 / 17))


def test_a_scene_of_several_nodes_is_found_too(tmp_path: Path) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(_box((30, 10, 10)), node_name="slide")
    scene.add_geometry(_box((20, 10, 10)), node_name="frame", transform=_moved(0, 0, 40))
    scene.add_geometry(_box((20, 10, 10)), node_name="copy", transform=_moved(40, 0, 40))
    path = tmp_path / "parts.glb"
    scene.export(path)
    found = find_pieces(path)  # GLB is y-up: the file's x and z are the ground
    assert found.count == 3
    assert np.allclose(found.pieces[0].size, (30, 10, 10))


def test_a_mirrored_node_built_alone_still_faces_outward(tmp_path: Path) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(_box((30, 10, 10)), node_name="left")
    mirror = np.diag([-1.0, 1.0, 1.0, 1.0])
    mirror[0, 3] = -20.0
    scene.add_geometry(_box((20, 10, 10)), node_name="mirrored", transform=mirror)
    path = tmp_path / "mirrored.glb"
    scene.export(path)
    found = find_pieces(path)
    assert found.count == 2 and np.allclose(found.pieces[1].size, (20, 10, 10))
    seed = load_seed(path, studs=8, piece=2)
    assert len(seed.faces) == 12 and _signed_volume(seed.vertices, seed.faces) > 0


def test_one_stl_mesh_holding_several_shells(tmp_path: Path) -> None:
    path = _stl(tmp_path / "shells.stl", _box((10, 10, 10)), _box((10, 10, 10), at=(30, 0, 0)))
    loaded: Any = trimesh.load(path)
    assert len(loaded.faces) == 24  # one mesh in the file
    found = find_pieces(path)
    assert found.count == 2
    # equal pieces: in the order of their smallest corner, x first
    assert found.pieces[0].box[0][0] == 0 and found.pieces[1].box[0][0] == 30


def test_numbering_follows_the_up_axis(tmp_path: Path) -> None:
    # side by side along x in a z-up file: two pieces; seen along x they cover each other
    path = _stl(tmp_path / "row.stl", _box((10, 10, 30)), _box((10, 10, 20), at=(30, 0, 0)))
    assert find_pieces(path).count == 2
    assert not find_pieces(path, up="x").several


def test_sizes_in_studs_the_json_and_the_words(tmp_path: Path) -> None:
    found = find_pieces(_kit(tmp_path), name="my kit.stl")
    assert found.source == "my kit.stl"
    assert found.within(1, 20) == (10.0, 5.0, 2.5)  # 80 across is 20 studs
    assert found.alone(1, 20) == (20.0, 10.0, 5.0)
    data = found.to_json(20)
    assert data["count"] == 3 and data["several"] is True and data["studs"] == 20
    assert data["more"] == 0 and data["small_bits"] == 0 and data["source"] == "my kit.stl"
    assert [p["number"] for p in data["pieces"]] == [1, 2, 3]
    assert data["pieces"][0]["within"] == [10.0, 5.0, 2.5]
    assert all(p["colour"].startswith("#") and len(p["colour"]) == 7 for p in data["pieces"])
    lines = found.lines(20)
    assert lines[0].startswith("my kit.stl looks like 3 separate pieces")
    assert "about 10 studs long; built alone it would be 20" in lines[1]
    assert lines[3].strip() == (
        "Piece 1: 10 x 5 x 2.5 in the whole layout, 20 x 10 x 5 alone (the largest)"
    )
    assert not any("coarse" in line for line in lines)


def test_the_picture_numbers_the_pieces_from_above(tmp_path: Path) -> None:
    found = find_pieces(_kit(tmp_path))
    out = tmp_path / "pieces.png"
    found.save_picture(out)
    picture = Image.open(out).convert("RGB")
    assert picture.width <= P.PICTURE_SIZE[0] and picture.height <= P.PICTURE_SIZE[1]
    grid = np.asarray(picture)
    rows = {}
    for number in (1, 2, 3):
        mine = (grid == np.array(P._colour(number))).all(axis=2)
        assert mine.sum() > 200, number
        rows[number] = np.nonzero(mine.any(axis=1))[0].mean()
    assert rows[3] < rows[1]  # front at the bottom: the ball (at the back) is higher up


def test_numbers_never_overlap_or_leave_the_picture(tmp_path: Path) -> None:
    wide = _box((300, 10, 5))  # as wide as the layout
    small = [_box((32, 4, 4), at=(8 + 40 * i, 20, 0)) for i in range(7)]
    tall = [_box((3, 3, 31), at=(5 + 15 * i, 40, 0)) for i in range(4)]
    found = find_pieces(_stl(tmp_path / "crowd.stl", wide, *small, *tall))
    assert found.several and found.count == 12
    picture = found.picture()
    shown = np.zeros((picture.height, picture.width), dtype=np.int32)
    places = P._place_labels(shown, 0, picture.width, picture.height)  # nothing to place
    assert places == {}
    from bricksnap.pieces import _draw

    _draw(found)  # draws without error
    plan_places = _labels_of(found)
    r = P._LABEL_R
    centres = [c for c, _ in plan_places.values()]
    assert len(centres) == 12
    for x, y in centres:
        assert r <= x <= picture.width - r and r <= y <= picture.height - r
    for a in range(len(centres)):
        for b in range(a + 1, len(centres)):
            (x1, y1), (x2, y2) = centres[a], centres[b]
            assert (x1 - x2) ** 2 + (y1 - y2) ** 2 >= (2 * r) ** 2


def _labels_of(found: Any) -> dict:
    """The label places ``_draw`` uses, worked out the same way."""
    captured: dict = {}
    real = P._place_labels

    def spy(*args: Any) -> dict:
        captured.update(real(*args))
        return captured

    P._place_labels = spy  # ty: ignore[invalid-assignment]
    try:
        found.picture()
    finally:
        P._place_labels = real
    return captured


def test_the_search_is_fast_on_many_loose_triangles(tmp_path: Path) -> None:
    rng = np.random.default_rng(3)
    n = 300_000
    p = rng.uniform(0, 100, (n, 3))
    tri = np.stack([p, p + rng.normal(0, 0.5, (n, 3)), p + rng.normal(0, 0.5, (n, 3))], axis=1)
    from bricksnap.pieces import _search

    started = time.time()
    found = _search(tri.reshape(-1, 3), np.arange(3 * n).reshape(-1, 3))
    assert time.time() - started < 10
    assert not found.several


# ---- keeping one piece ----------------------------------------------------------------------


@pytest.mark.parametrize("studs", [8, 21])
def test_one_piece_comes_out_as_a_file_of_that_piece_alone(tmp_path: Path, studs: int) -> None:
    kit = _kit(tmp_path)
    alone = _stl(tmp_path / "ball.stl", _ball(8, (8, 45, 8)))
    got = load_seed(kit, studs=studs, piece=3)
    want = load_seed(alone, studs=studs)
    assert got.faces.shape == want.faces.shape
    assert np.allclose(got.vertices.min(axis=0), want.vertices.min(axis=0), atol=1e-9)
    assert np.allclose(got.vertices.max(axis=0), want.vertices.max(axis=0), atol=1e-9)
    # the same triangles, the same way round (not turned inside out)
    assert np.allclose(got.vertices[got.faces], want.vertices[want.faces], atol=1e-9)
    assert _signed_volume(got.vertices, got.faces) == pytest.approx(
        _signed_volume(want.vertices, want.faces)
    )
    assert _signed_volume(got.vertices, got.faces) > 0


def test_a_piece_is_found_again_by_its_box(tmp_path: Path) -> None:
    kit = _kit(tmp_path)
    found = find_pieces(kit)
    by_box = load_seed(kit, studs=10, piece_box=found.pieces[1].box)
    assert np.allclose(
        np.ptp(by_box.vertices, axis=0), np.ptp(load_seed(kit, studs=10, piece=2).vertices, axis=0)
    )
    with pytest.raises(SeedError, match="cannot be found in the file any more"):
        load_seed(kit, studs=10, piece_box=((0, 0, 0), (41, 20, 10)))
    with pytest.raises(SeedError, match="damaged"):
        load_seed(kit, studs=10, piece_box="nonsense")


def test_a_piece_keeps_its_colours(tmp_path: Path) -> None:
    red, blue = _box((20, 10, 10)), _box((10, 10, 10), at=(40, 0, 0))
    both: Any = trimesh.util.concatenate([red, blue])
    colours = np.array([[200, 0, 0, 255]] * 12 + [[0, 0, 200, 255]] * 12, dtype=np.uint8)
    path = tmp_path / "coloured.ply"
    trimesh.Trimesh(both.vertices, both.faces, face_colors=colours, process=False).export(path)
    seed = load_seed(path, studs=8, piece=2)
    assert seed.face_colors is not None and len(seed.face_colors) == len(seed.faces) == 12
    assert (seed.face_colors == [0, 0, 200]).all()


def test_a_piece_the_file_does_not_have_is_a_plain_error(tmp_path: Path, pawn_path: Path) -> None:
    with pytest.raises(SeedError, match="3 pieces to choose from, numbered 1 to 3"):
        load_seed(_kit(tmp_path), studs=8, piece=4)
    with pytest.raises(SeedError, match="looks like one object"):
        load_seed(pawn_path, studs=8, piece=2)
    with pytest.raises(SeedError, match="by its number"):
        load_seed(pawn_path, studs=8, piece="2")  # ty: ignore[invalid-argument-type]
    whole = load_seed(pawn_path, studs=8)
    one = load_seed(pawn_path, studs=8, piece=1)
    assert np.array_equal(whole.vertices, one.vertices)


@pytest.mark.parametrize("bad", ["0", "-1", "two", "", "1.5", "²", "١", "1e3", True, 0, 2.0, None])
def test_choices_are_read_plainly(bad: Any) -> None:
    with pytest.raises(SeedError, match="Choose which piece"):
        parse_choice(bad)


def test_good_choices(tmp_path: Path) -> None:
    assert parse_choice("largest") == "largest"
    assert parse_choice(" ALL ") == "all"
    assert parse_choice("3") == 3 and parse_choice(2) == 2
    found = find_pieces(_kit(tmp_path))
    assert resolve("largest", found) == 1
    assert resolve("all", found) is None
    assert resolve(3, found) == 3
    with pytest.raises(SeedError, match="no piece 4"):
        resolve(4, found)


# ---- the project keeps the piece ------------------------------------------------------------


def test_a_project_keeps_its_piece_for_every_later_step(tmp_path: Path) -> None:
    from bricksnap import versions

    kit = _kit(tmp_path)
    project = create_project(kit, studs=12, directory=tmp_path / "p", piece=3)
    assert project.meta["piece"] == 3 and project.piece == 3
    assert project.meta["piece_box"] == [list(c) for c in find_pieces(kit).pieces[2].box]
    seed = load_project_seed(Project(project.path))
    assert len(seed.faces) == find_pieces(kit).pieces[2].faces
    # the build, the pictures and the plain conversion all come from that piece
    filled = np.argwhere(project.load_design(base=True).colors >= 0)
    span = filled.max(axis=0) - filled.min(axis=0) + 1
    assert span[0] >= 11 and span[1] >= 11  # a ball 12 across (the whole kit is 12 x 8)
    rebuild(project)
    render_compare(project)
    rough_build(project)
    versions.record(project, "converted", "first")
    project.meta["studs"] = 20  # built again at another size: still the same piece
    project.save_meta()
    bigger = load_project_seed(Project(project.path))
    assert bigger.faces.shape == seed.faces.shape
    assert bigger.vertices.max(axis=0).max() == pytest.approx(20 * 8)
    versions.restore(project, 1)
    again = Project(project.path)
    assert again.meta["piece"] == 3 and again.meta["piece_box"] == project.meta["piece_box"]


def test_a_changed_rule_or_file_is_a_plain_error_not_the_whole_layout(tmp_path: Path) -> None:
    project = create_project(_kit(tmp_path), studs=8, directory=tmp_path / "p", piece=2)
    project.meta["piece_box"] = [[0, 0, 0], [1, 1, 1]]
    project.save_meta()
    with pytest.raises(SeedError, match="Make the project again"):
        load_project_seed(Project(project.path))


@pytest.mark.parametrize("bad", ["2", 2.0, True, 0, -1, [2]])
def test_a_damaged_piece_record_is_a_plain_error(tmp_path: Path, bad: Any) -> None:
    project = create_project(_kit(tmp_path), studs=8, directory=tmp_path / "p", piece=2)
    project.meta["piece"] = bad
    project.save_meta()
    with pytest.raises(ProjectError, match="damaged"):
        load_project_seed(Project(project.path))


def test_a_piece_without_its_box_is_damaged(tmp_path: Path) -> None:
    project = create_project(_kit(tmp_path), studs=8, directory=tmp_path / "p", piece=2)
    del project.meta["piece_box"]
    project.save_meta()
    with pytest.raises(ProjectError, match="damaged"):
        load_project_seed(Project(project.path))


def test_a_whole_file_project_has_no_piece(tmp_path: Path, pawn_path: Path) -> None:
    project = create_project(pawn_path, studs=8, directory=tmp_path / "p")
    assert "piece" not in project.meta and project.piece is None and project.piece_box is None
    project = create_project(pawn_path, studs=8, directory=tmp_path / "q", piece=1)
    assert "piece" not in project.meta  # a one-object file is built whole


def _moved(x: float, y: float, z: float) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m
