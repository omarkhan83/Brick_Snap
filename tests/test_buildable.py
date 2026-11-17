"""Tests for the make-buildable pass (bricksnap/buildable.py).

Each shape is a small version of something that comes loose in real designs: a nose, a
muzzle, whiskers, eyes or a bill in their own colour on a face; two colours meeting on a
vertical plane; a sheet one plate thin; a part hanging in the air. "Pieces" are counted
straight from bricksnap.connect, independently of the module under test.
"""

from __future__ import annotations

import time

import networkx as nx
import numpy as np
import pytest
import shapes
from scipy import ndimage

from bricksnap.buildable import BuildableResult, make_buildable
from bricksnap.connect import connection_graph, lone_links, occupancy
from bricksnap.layout import solve
from bricksnap.types import EMPTY, FINISH_SMOOTH, FINISH_STUDS, Design, Detail

WHITE, BLACK, RED, PINK, GREY, ORANGE, YELLOW, BROWN = 15, 0, 4, 5, 71, 25, 14, 70


# ---- helpers ----------------------------------------------------------------------------------


def grid(shape: tuple[int, int, int]) -> np.ndarray:
    return np.full(shape, EMPTY, dtype=np.int16)


def piece_count(build, catalog) -> int:
    return nx.number_connected_components(connection_graph(build, catalog))


def visible(filled: np.ndarray) -> np.ndarray:
    """Filled cells next to air reachable from the sides or the top (written independently
    of the module: label the empty space of a grid padded on the sides and the top)."""
    nx_, ny_, nz_ = filled.shape
    empty = np.ones((nx_ + 2, ny_ + 2, nz_ + 1), dtype=bool)
    empty[1:-1, 1:-1, :-1] = ~filled
    labels, _ = ndimage.label(empty)
    outside = np.isin(labels, np.unique(labels[0]))  # the x = -1 face is all padding
    air = np.zeros((nx_ + 2, ny_ + 2, nz_ + 2), dtype=bool)
    air[:, :, 1:] = outside  # index 0 is below z = 0: the table, not air
    near = np.zeros(filled.shape, dtype=bool)
    for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        near |= air[1 + dx : 1 + dx + nx_, 1 + dy : 1 + dy + ny_, 1 + dz : 1 + dz + nz_]
    return filled & near


def run(design: Design, catalog, **kw) -> BuildableResult:
    """make_buildable, with every promise of the contract that holds for any input checked."""
    before = design.copy()
    result = make_buildable(design, catalog, **kw)
    # the input is never modified
    assert np.array_equal(design.colors, before.colors)
    assert design.fingerprint() == before.fingerprint()
    assert design.log == before.log
    out = result.design
    assert out is not design
    assert out.shape == design.shape
    # nothing emptied; the masks say exactly what changed
    assert not (design.filled & ~out.filled).any(), "a filled cell was emptied"
    assert np.array_equal(result.added, out.filled & ~design.filled)
    assert np.array_equal(result.recoloured, design.filled & (out.colors != design.colors))
    assert not (result.recoloured & visible(design.filled)).any(), "a visible cell changed colour"
    # finish: added cells get studs, everything else is kept; notes of the Design are kept
    assert out.finish is not None and design.finish is not None
    assert (out.finish[result.added] == FINISH_STUDS).all()
    assert np.array_equal(out.finish[~result.added], design.finish[~result.added])
    assert out.details == design.details
    assert out.regions == design.regions
    assert out.log == design.log
    assert out.seed_offset == design.seed_offset
    # the build is the solver's build of the returned Design, and covers it exactly
    again = solve(out, catalog, seed=kw.get("seed", 0))
    assert again.parts == result.build.parts
    occ, collisions, out_of_bounds, unknown = occupancy(result.build, catalog)
    assert not collisions and not out_of_bounds and not unknown
    assert np.array_equal(occ >= 0, out.filled)
    # piece counts
    assert result.pieces_before == piece_count(
        solve(design, catalog, seed=kw.get("seed", 0)), catalog
    )
    assert result.pieces_after == piece_count(result.build, catalog)
    assert result.pieces_after <= result.pieces_before
    for note in result.notes:
        assert note and "Traceback" not in note and "np." not in note
    return result


def assert_unchanged(design: Design, result: BuildableResult) -> None:
    assert not result.recoloured.any() and not result.added.any()
    assert result.notes == []
    assert result.design.fingerprint() == design.fingerprint()
    assert result.pieces_before == result.pieces_after


def cells(mask: np.ndarray) -> set[tuple[int, int, int]]:
    return {(int(x), int(y), int(z)) for x, y, z in np.argwhere(mask)}


def assert_every_addition_is_needed(result: BuildableResult, catalog) -> None:
    """Taking away any touching group of added cells gives more pieces."""
    groups, n = ndimage.label(result.added, structure=np.ones((3, 3, 3)))
    for k in range(1, n + 1):
        trial = result.design.copy()
        trial.colors[groups == k] = EMPTY
        without = piece_count(solve(trial, catalog), catalog)
        where = sorted(cells(groups == k))
        assert without > result.pieces_after, f"the added cells {where} hold nothing"


# ---- shapes -------------------------------------------------------------------------------------


def nose_on_head() -> Design:
    """A white head (y = 1 to 6) with a dark pink nose stuck on its front face."""
    c = grid((8, 7, 12))
    c[:, 1:, :] = WHITE
    c[3:5, 0, 6:9] = PINK
    return Design(colors=c)


def two_colours() -> Design:
    """A thick block, white on the left and red on the right, meeting on the plane x = 3|4."""
    c = grid((8, 4, 9))
    c[:4] = WHITE
    c[4:] = RED
    return Design(colors=c)


def mushroom() -> Design:
    """A red cap 10 x 10 studs, one plate thin, on a white stem 2 x 2 studs."""
    c = grid((10, 10, 10))
    c[4:6, 4:6, 0:9] = WHITE
    c[:, :, 9] = RED
    return Design(colors=c)


def table() -> Design:
    """A table top 12 x 6 studs, one plate thin, on four legs at its corners."""
    c = grid((12, 6, 10))
    for x in (0, 11):
        for y in (0, 5):
            c[x, y, 0:9] = BROWN
    c[:, :, 9] = BROWN
    return Design(colors=c)


def floating_bar() -> Design:
    """A white block with a red bar hanging in the air five plates above it."""
    c = grid((6, 6, 14))
    c[:, :, 0:6] = WHITE
    c[:, 2, 11] = RED
    return Design(colors=c)


def two_objects() -> Design:
    c = grid((10, 4, 6))
    c[0:4] = WHITE
    c[6:10] = RED
    return Design(colors=c)


def cat_face() -> Design:
    """A light grey muzzle one stud proud of a white face, and a pink nose on the muzzle."""
    c = grid((10, 8, 15))
    c[:, 2:, :] = WHITE
    c[3:7, 1, 4:8] = GREY
    c[4:6, 0, 6:8] = PINK
    return Design(colors=c)


def whiskers() -> Design:
    """Black whiskers one plate thin, three studs long, sticking out of both cheeks."""
    c = grid((12, 6, 12))
    c[3:9, :, :] = WHITE
    for z in (5, 7):
        c[0:3, 1, z] = BLACK
        c[9:12, 1, z] = BLACK
    return Design(colors=c)


def duck_bill() -> Design:
    """An orange bill two studs long and two plates tall on a yellow face."""
    c = grid((8, 8, 12))
    c[:, 2:, :] = YELLOW
    c[2:6, 0:2, 4:6] = ORANGE
    return Design(colors=c)


def eyes() -> Design:
    """Two black eyes one stud deep and one plate tall, standing proud of a white face."""
    c = grid((10, 7, 12))
    c[:, 1:, :] = WHITE
    c[2, 0, 8] = BLACK
    c[7, 0, 8] = BLACK
    return Design(colors=c)


def nose_on_ledge_top() -> Design:
    """A pink nose whose lower row sits in front of the top row of a white ledge on the face:
    the ledge cell behind it has air above, so it can be seen and cannot be recoloured."""
    c = grid((10, 8, 15))
    c[:, 3:, :] = WHITE
    c[3:7, 1:3, 4:8] = WHITE
    c[4:6, 0, 7:9] = PINK
    return Design(colors=c)


def whisker_on_top_edge() -> Design:
    """A whisker on the top layer of a head: the cheek cell it touches has air above it."""
    c = grid((9, 4, 6))
    c[3:9, :, :] = WHITE
    c[0:3, 1, 5] = BLACK
    return Design(colors=c)


def block_in_hollow() -> Design:
    """A closed white box with a red block floating in the middle of its hollow inside."""
    c = grid((8, 8, 14))
    c[:] = WHITE
    c[1:7, 1:7, 3:11] = EMPTY
    c[3:5, 3:5, 6:9] = RED
    return Design(colors=c)


def sphere_cat(diameter: int = 16, hollow: int = 0) -> Design:
    """A round head with a grey muzzle, a pink nose on it and two eyes, all in front of it."""
    head = shapes.sphere(diameter, WHITE)
    if hollow:
        head = shapes.hollowed(head, hollow)
    nx_, ny_, nz_ = head.shape
    c = grid((nx_, ny_ + 2, nz_))
    c[:, 2:, :] = head.colors
    cx, zc = nx_ // 2, nz_ // 2

    def front(x: int, z: int) -> int:
        return int(np.nonzero(c[x, :, z] != EMPTY)[0][0])

    for x in range(cx - 2, cx + 2):
        for z in range(zc - 4, zc - 1):
            c[x, front(x, z) - 1, z] = GREY
    for x in range(cx - 1, cx + 1):
        for z in range(zc - 2, zc):
            c[x, front(x, z) - 1, z] = PINK
    for x in (cx - 2, cx + 1):
        y = front(x, zc + 1) - 1
        c[x, y, zc + 1 : zc + 3] = BLACK
    return Design(colors=c)


# ---- recolouring hidden cells -----------------------------------------------------------------


def test_nose_in_its_own_colour_on_the_front_of_a_head(catalog):
    design = nose_on_head()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.added.any()
    # the hidden cells directly behind the nose, in the nose's levels, now carry its colour
    assert cells(result.recoloured) <= {(x, 1, z) for x in (3, 4) for z in (6, 7, 8)}
    assert (result.design.colors[result.recoloured] == PINK).all()
    assert len(result.notes) == 1
    note = result.notes[0]
    assert note.startswith("Recoloured") and "Dark Pink" in note
    assert "x=3 to 4, y=1, z=6 to 8" in note and "x=3 to 4, y=0, z=6 to 8" in note


def test_two_colours_meeting_on_a_vertical_plane(catalog):
    design = two_colours()
    # the loose repair alone (once joined, the white block hangs on one part, and the
    # weak-spot phase recolours a few more hidden cells on the other side of the plane)
    result = run(design, catalog, max_sturdy_solves=0)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.added.any()
    changed = cells(result.recoloured)
    assert changed, "something must be recoloured"
    # only cells touching the other colour, and few of them (the plane has 16 hidden cells)
    assert all(x == 3 for x, _, _ in changed) or all(x == 4 for x, _, _ in changed)
    assert len(changed) <= 16
    assert "held from inside" in result.notes[0]


def test_cat_muzzle_and_nose_on_a_face(catalog):
    design = cat_face()
    result = run(design, catalog)
    assert result.pieces_before == 3 and result.pieces_after == 1
    assert not result.added.any()
    colours = set(result.design.colors[result.recoloured].tolist())
    assert colours <= {GREY, PINK} and GREY in colours
    # the nose holds on through hidden muzzle cells, the muzzle through hidden face cells
    assert all(y in (1, 2) for _, y, _ in cells(result.recoloured))
    assert any("Dark Pink" in n for n in result.notes)
    assert any("Light Bluish Grey" in n for n in result.notes)


def test_whiskers_one_plate_thin_out_of_the_cheeks(catalog):
    design = whiskers()
    result = run(design, catalog)
    assert result.pieces_before == 5 and result.pieces_after == 1
    assert not result.added.any()
    # one hidden cheek cell at the root of each whisker is enough
    assert cells(result.recoloured) == {(x, 1, z) for x in (3, 8) for z in (5, 7)}
    assert (result.design.colors[result.recoloured] == BLACK).all()


def test_duck_bill_on_a_face(catalog):
    design = duck_bill()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.added.any()
    assert all(y == 2 for _, y, _ in cells(result.recoloured))
    assert (result.design.colors[result.recoloured] == ORANGE).all()


def test_eyes_one_stud_deep_on_a_face(catalog):
    design = eyes()
    result = run(design, catalog)
    assert result.pieces_before == 3 and result.pieces_after == 1
    assert cells(result.recoloured) == {(2, 1, 8), (7, 1, 8)}
    assert not result.added.any()


def test_round_head_with_muzzle_nose_and_eyes(catalog):
    for hollow in (0, 2):
        design = sphere_cat(16, hollow)
        result = run(design, catalog)
        assert result.pieces_before > 1
        assert result.pieces_after == 1, result.notes
        assert not result.added.any()


def test_recolours_only_what_the_parts_use(catalog):
    # the first try gives all 16 hidden cells of the plane the red; parts that join the two
    # colours need only some of them, and the rest are given back their own colour
    result = run(two_colours(), catalog)
    assert 0 < int(result.recoloured.sum()) < 16


# ---- thickening, supports, cells beside ---------------------------------------------------------


def test_wide_cap_one_plate_thin_on_a_narrow_stem(catalog):
    design = mushroom()
    result = run(design, catalog)
    assert result.pieces_before > 1 and result.pieces_after == 1
    assert not result.recoloured.any()
    added = cells(result.added)
    assert added
    # only directly beneath the cap, in its colour; the top surface is as designed
    assert all(z == 8 for _, _, z in added)
    assert (result.design.colors[result.added] == RED).all()
    assert np.array_equal(result.design.colors[:, :, 9], design.colors[:, :, 9])
    assert any("one plate thin" in n and f"Added {len(added)} Red cells" in n for n in result.notes)


def test_table_whose_top_is_one_plate_thin(catalog):
    design = table()
    result = run(design, catalog)
    assert result.pieces_before > 1 and result.pieces_after == 1
    added = cells(result.added)
    assert added and all(z == 8 for _, _, z in added)
    assert (result.design.colors[result.added] == BROWN).all()
    assert any("under the sheet" in n and "z=8" in n for n in result.notes)


def test_bar_floating_above_the_model(catalog):
    design = floating_bar()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    added = cells(result.added)
    # one column under the middle of the bar, from its underside down to the block
    assert len({(x, y) for x, y, _ in added}) == 1
    (x, y) = {(x, y) for x, y, _ in added}.pop()
    assert y == 2 and x in (2, 3)
    assert sorted(z for _, _, z in added) == list(range(6, 11))
    assert (result.design.colors[result.added] == RED).all()
    assert len(result.notes) == 1 and "column of 5 Red cells" in result.notes[0]
    assert "hung in the air" in result.notes[0]


def test_support_inside_a_hollow_is_hidden(catalog):
    design = block_in_hollow()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    added = cells(result.added)
    assert added and all(1 <= x <= 6 and 1 <= y <= 6 and 3 <= z <= 5 for x, y, z in added)
    assert not (visible(result.design.filled) & result.added).any()
    assert "hidden inside the model" in result.notes[0]


def test_support_column_avoids_a_detail_part(catalog):
    design = floating_bar()
    design.details.append(Detail(part="3070b", color=BLACK, x=2, y=2, z=6))
    design.details.append(Detail(part="3070b", color=BLACK, x=3, y=2, z=6))
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert not result.added[2:4, 2, 6].any()


def test_nose_on_the_top_edge_of_a_ledge_gets_a_clamp(catalog):
    # the ledge cell behind the nose's lower row can be seen (air above it), so nothing can
    # be recoloured; one white cell under the nose, beside the ledge, holds it
    design = nose_on_ledge_top()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.recoloured.any()
    (cell,) = cells(result.added)
    assert cell in {(4, 0, 6), (5, 0, 6)}
    assert result.design.colors[cell] == WHITE
    assert "reaches across under it" in result.notes[0]


def test_nose_on_the_top_edge_of_a_ledge_reaches_over_it(catalog):
    # as above, with detail parts standing where a clamp would go: two cells beside the
    # nose's upper row, resting on the ledge, join it
    design = nose_on_ledge_top()
    design.details.append(Detail(part="3070b", color=BLACK, x=4, y=0, z=6))
    design.details.append(Detail(part="3070b", color=BLACK, x=5, y=0, z=6))
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.recoloured.any()
    assert cells(result.added) == {(4, 1, 8), (5, 1, 8)}
    assert (result.design.colors[result.added] == PINK).all()
    assert "reaches over the model's studs" in result.notes[0]


# ---- what is reported, not repaired -------------------------------------------------------------


def test_no_tall_post_in_view_under_a_feature_stuck_on_a_face(catalog):
    # a nose on the top edge of a head, with a foot of the model far below it: a column
    # down to the foot would join it, but a feature stuck on a face does not hang in the air
    # and a tall post in front of the face is no repair; one white cell under it (a clamp)
    # holds it instead
    c = grid((8, 7, 10))
    c[:, 1:, :] = WHITE
    c[:, 0, 0] = WHITE
    c[3:5, 0, 9] = PINK
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.recoloured.any()
    assert len(cells(result.added)) == 1 and not result.added[:, 0, :8].any()
    assert not any("column" in n for n in result.notes)
    # with no room for the clamp, nothing joins it, and it is reported
    c[3:5, 1, 8] = EMPTY
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 2
    assert not result.added.any() and not result.recoloured.any()
    assert result.notes[0].startswith("Still loose: the Dark Pink part at x=3 to 4, y=0, z=9")


def test_two_separate_objects_are_reported_not_bridged(catalog):
    design = two_objects()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 2
    assert not result.recoloured.any() and not result.added.any()
    assert result.design.fingerprint() == design.fingerprint()
    assert len(result.notes) == 1
    assert "separate object" in result.notes[0] and "x=6 to 9" in result.notes[0]


def test_a_visible_cell_is_never_recoloured_to_join_a_piece(catalog):
    design = whisker_on_top_edge()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert result.design.colors[3, 1, 5] == WHITE
    assert not result.recoloured.any()
    assert cells(result.added) == {(2, 1, 4)}  # a clamp under its root, not a recolour
    # with the cheek cell under the clamp's place gone, nothing can hold it
    design.colors[3, 1, 4] = EMPTY
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 2
    assert result.design.colors[3, 1, 5] == WHITE
    assert result.design.fingerprint() == design.fingerprint()
    note = result.notes[0]
    assert note.startswith("Still loose: the Black part at x=0 to 2, y=1, z=5")
    assert "can be seen" in note


def test_still_loose_comes_first_in_the_notes(catalog):
    c = nose_on_head().colors
    c = np.concatenate([np.full((3, 7, 12), EMPTY, dtype=np.int16), c], axis=0)
    c[0:3, 3, 11] = BLACK  # a whisker on the top edge of the head, cannot be held
    c[3, 3, 10] = EMPTY  # (a notch under the cheek cell it touches: no room for a clamp)
    result = run(Design(colors=c), catalog)
    assert result.pieces_after == 2
    assert result.notes[0].startswith("Still loose")
    assert any(n.startswith("Recoloured") for n in result.notes[1:])


def test_out_of_solves_returns_the_input_and_says_so(catalog):
    design = nose_on_head()
    result = run(design, catalog, max_solves=1)
    assert result.pieces_before == result.pieces_after == 2
    assert result.design.fingerprint() == design.fingerprint()
    assert "ran out of attempts" in result.notes[0]


# ---- nothing to do ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: shapes.box(6, 4, 2, WHITE),
        lambda: shapes.striped(shapes.box(6, 6, 4)),
        lambda: shapes.hollowed(shapes.sphere(14)),
    ],
    ids=["box", "striped-box", "hollow-sphere"],
)
def test_a_model_that_needs_nothing_is_returned_unchanged(make, catalog):
    design = make()
    result = run(design, catalog)
    assert result.pieces_before == 1
    assert_unchanged(design, result)


def test_eyes_set_into_the_face_need_nothing(catalog):
    c = grid((10, 7, 12))
    c[:, :, :] = WHITE
    c[2, 0, 8] = BLACK  # in the face's own surface, with white above and below
    c[7, 0, 8] = BLACK
    design = Design(colors=c)
    assert_unchanged(design, run(design, catalog))


def test_empty_design_is_returned_unchanged(catalog):
    design = Design(colors=grid((4, 4, 3)))
    result = run(design, catalog)
    assert result.pieces_before == 0
    assert_unchanged(design, result)


# ---- keeps the Design's notes, determinism, speed ------------------------------------------------


def test_keeps_finish_details_regions_log_and_offset(catalog):
    design = floating_bar()
    assert design.finish is not None
    design.finish[:, :, 5] = FINISH_SMOOTH  # the block's top, where the column will stand
    design.finish[:, 2, 11] = FINISH_SMOOTH
    design.details.append(Detail(part="3070b", color=BLACK, x=0, y=0, z=6))
    design.regions["bar"] = {"type": "box", "min": [0, 2, 11], "max": [5, 2, 11]}
    design.log.append({"op": "add", "shape": design.regions["bar"], "color": RED})
    design.seed_offset = (1, 2, 0)
    result = run(design, catalog)  # run() checks every one of these
    assert result.added.any() and result.pieces_after == 1


def test_deterministic_for_a_seed(catalog):
    for make in (cat_face, table):
        a = make_buildable(make(), catalog, seed=3)
        b = make_buildable(make(), catalog, seed=3)
        assert a.design.fingerprint() == b.design.fingerprint()
        assert a.notes == b.notes
        assert a.build.parts == b.build.parts


def test_sixteen_stud_model_is_quick(catalog):
    design = sphere_cat(16, hollow=2)
    t = time.perf_counter()
    result = make_buildable(design, catalog)
    assert time.perf_counter() - t < 10
    assert result.pieces_after == 1


def hollow_two_colour_box() -> Design:
    """A closed box 14 studs square and 19 plates tall, walls one stud thick, dark pink for
    x < 4 and white beyond: the two colours meet on a vertical plane through walls that can
    be seen on both sides, so nothing hidden can be recoloured to join them."""
    c = grid((14, 14, 19))
    c[:] = WHITE
    c[1:13, 1:13, 1:18] = EMPTY
    c[:4][c[:4] != EMPTY] = PINK
    return Design(colors=c)


def test_a_model_that_cannot_be_joined_does_not_take_long(catalog, monkeypatch):
    # every solve the layout cannot bring together costs seconds; the pass must stop
    # trying once a repair makes things no better, not climb through every rung
    import bricksnap.layout

    real = bricksnap.layout.solve
    calls = []

    def counted(design, catalog, *, seed=0):
        calls.append(1)
        return real(design, catalog, seed=seed)

    monkeypatch.setattr(bricksnap.layout, "solve", counted)
    design = hollow_two_colour_box()
    t = time.perf_counter()
    result = make_buildable(design, catalog)
    assert time.perf_counter() - t < 10
    assert len(calls) <= 4
    assert result.pieces_after <= result.pieces_before
    assert result.notes and result.notes[0].startswith("Still loose")


# ---- needless additions, pieces away from the main one, true reasons -----------------------------


def test_no_column_is_added_where_another_repair_already_holds_the_piece(catalog):
    # a white block with, along its side, black - grey (two plates tall) - black; the last
    # black cell sticks out past the block. Once the grey reaches over both black cells, a
    # column from the ground up to the outer black cell holds nothing
    c = grid((8, 8, 8))
    c[0:6, 0:6, :] = WHITE
    c[4, 6, 3] = BLACK
    c[5, 6, 3:5] = GREY
    c[6, 6, 3] = BLACK
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert not result.added[6, 6, 0:3].any()
    assert not any("column" in n for n in result.notes)
    assert_every_addition_is_needed(result, catalog)


def split_egg() -> Design:
    """An egg 8 studs wide, 6 deep and 8 plates tall with a small hollow inside, grey at
    the back and black at the front: the two halves meet on a vertical plane."""
    w, d, h = 8, 6, 8
    x, y, z = np.meshgrid(np.arange(w) + 0.5, np.arange(d) + 0.5, np.arange(h) + 0.5, indexing="ij")
    egg = ((x - w / 2) / (w / 2)) ** 2 + ((y - d / 2) / (d / 2)) ** 2 + ((z - h / 2) / (h / 2)) ** 2
    inside = egg <= 1
    inside[3:5, 2:4, 3:5] = False
    c = grid((w + 6, d + 6, h + 6))
    c[3 : 3 + w, 3 : 3 + d, :h][inside] = GREY
    c[:, 6:][c[:, 6:] != EMPTY] = BLACK
    return Design(colors=c)


def test_columns_a_fresh_layout_does_not_need_are_taken_away(catalog):
    # recolouring joins the halves but leaves a few grey bits loose in that solve; columns
    # to the ground hold them there, yet once the columns are in place the layout no longer
    # needs them: the result must not keep added cells that hold nothing
    design = split_egg()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert_every_addition_is_needed(result, catalog)
    assert not any("column" in n for n in result.notes)


def test_a_feature_on_a_second_object_is_joined_to_that_object(catalog):
    # a white block, and apart from it a red block with a dark pink nose on its front
    c = grid((20, 7, 12))
    c[0:8, 1:, :] = WHITE
    c[12:20, 1:, 0:9] = RED
    c[15:17, 0, 4:7] = PINK
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_before == 3 and result.pieces_after == 2
    assert not result.added.any()
    assert cells(result.recoloured) <= {(x, 1, z) for x in (15, 16) for z in (4, 5, 6)}
    assert (result.design.colors[result.recoloured] == PINK).all()
    assert not any(n.startswith("Still loose") for n in result.notes)
    separate = [n for n in result.notes if "separate object" in n]
    assert len(separate) == 1 and "x=12 to 19" in separate[0]


def test_a_second_object_that_is_a_mushroom_gets_its_cap_thickened(catalog):
    c = grid((18, 10, 10))
    c[0:4, 3:7, 0:6] = WHITE
    c[8:18] = mushroom().colors
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == 2
    assert result.added.any() and all(z == 8 for _, _, z in cells(result.added))
    assert sum("separate object" in n for n in result.notes) == 1
    assert not any(n.startswith("Still loose") for n in result.notes)


def test_loose_parts_that_touch_each_other_get_one_note_with_the_true_reason(catalog):
    # a black whisker five studs long on the top edge of a white head: the layout makes it
    # two parts side by side, and the cheek cell it touches can be seen
    c = grid((11, 4, 6))
    c[5:11, :, :] = WHITE
    c[0:5, 1, 5] = BLACK
    c[5, 1, 4] = EMPTY  # a notch under the cheek cell it touches: no room for a clamp
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == result.pieces_before == 3
    loose = [n for n in result.notes if n.startswith("Still loose")]
    assert len(loose) == 1
    assert loose[0].startswith("Still loose: the Black part at x=0 to 4, y=1, z=5")
    assert "can be seen" in loose[0]
    assert "in its own colour" not in loose[0]


def test_a_sheet_lying_on_the_ground_is_not_told_to_stand_on_something(catalog):
    # a base plate 12 x 12 studs, one plate thin, in a grid one plate tall: nothing can go
    # beneath it or on top of it
    c = grid((12, 12, 1))
    c[:, :, 0] = GREY
    c[4:8, 4:8, 0] = WHITE
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after > 1
    assert len(result.notes) == 1
    note = result.notes[0]
    assert note.startswith("Still loose") and "on the ground" in note
    assert "stand on" not in note


def test_a_column_up_to_the_model_is_described_as_above(catalog):
    # a red bar hanging under the lintel of an arch: the column goes up to the lintel
    c = grid((10, 4, 16))
    c[0:2, :, 0:12] = WHITE
    c[8:10, :, 0:12] = WHITE
    c[:, :, 12:15] = WHITE
    c[4:6, 1, 8] = RED
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert all(z > 8 for _, _, z in cells(result.added))
    # (each pillar hangs on one part of the lintel, which nothing can change: two notes say so)
    (note,) = [n for n in result.notes if not n.startswith("Still hanging")]
    assert "above the Red part" in note and "up to the model" in note
    assert "under" not in note


def test_a_column_under_a_piece_that_touches_the_model_says_so(catalog):
    # a red cell beside the top edge of a white block (the white cell it touches can be
    # seen), over a white ledge two plates below: a short column down to the ledge holds it
    # (a notch under the white cell it touches leaves no room for a clamp)
    c = grid((9, 5, 4))
    c[0:6, :, :] = WHITE
    c[6:9, :, 0] = WHITE
    c[6, 2, 3] = RED
    c[5, 2, 2] = EMPTY
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(6, 2, 1), (6, 2, 2)}
    (note,) = result.notes
    assert "under the Red part" in note and "only at its side" in note
    assert "hung in the air" not in note


# ---- stage 3: partly covered cells, thickening from above, clamps -------------------------------


def whisker_through_an_eye(skin: bool = True) -> Design:
    """A grey whisker one plate thin sticking out of a white head, held only by a black eye
    cell that can be seen (the face is set back one stud there, so air is in front of the
    eye). With ``skin``, the model also passes partly through the white cell under the
    whisker's root, beside the cheek, and through a few cells elsewhere."""
    c = grid((10, 7, 12))
    c[3:9, 1:6, :] = WHITE
    c[3, 1, 7] = BLACK  # the eye: air in front of it at y = 0
    c[0:3, 1, 7] = GREY
    s = grid(c.shape)
    if skin:
        s[2, 1, 6] = WHITE  # under the root, beside the cheek
        s[1, 1, 8] = GREY  # over the whisker, away from anything that holds it
        s[6, 0, 3] = WHITE  # on the face, far from the whisker
    return Design(colors=c, skin=s)


def test_a_partly_covered_cell_holds_a_whisker_that_only_touches_an_eye(catalog):
    design = whisker_through_an_eye()
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.recoloured.any()
    assert cells(result.added) == {(2, 1, 6)}
    assert result.design.colors[2, 1, 6] == WHITE  # the cell's own colour
    (note,) = result.notes
    assert note.startswith("Filled 1 partly covered cell at x=2, y=1, z=6")
    assert "White" in note and "the Light Bluish Grey part at x=0 to 2, y=1, z=7" in note
    assert "less than half a cell" in note


def test_partly_covered_cells_are_filled_in_their_own_colour(catalog):
    design = whisker_through_an_eye()
    assert design.skin is not None
    design.skin[2, 1, 6] = EMPTY
    design.skin[2, 1, 8] = RED  # over the root: beside the head, but red, not white
    design.colors[3, 1, 8] = RED  # and the head is red there (seen from the front)
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(2, 1, 8)}
    assert result.design.colors[2, 1, 8] == RED


def test_partly_covered_cells_are_never_used_when_nothing_is_loose(catalog):
    design = shapes.box(6, 4, 2, WHITE)
    padded = grid((8, 6, 6))
    padded[1:7, 1:5] = design.colors
    skin = grid(padded.shape)
    skin[0, 1:5, 0:6] = WHITE
    skin[1:7, 1:5, 6 - 0 - 1] = EMPTY
    design = Design(colors=padded, skin=skin)
    assert_unchanged(design, run(design, catalog))


def test_a_feature_touching_the_body_only_at_its_side_gets_a_clamp(catalog):
    # the same whisker with no partly covered cells: one white cell under its root, beside
    # the cheek, lets a white part of the head reach across under it
    design = whisker_through_an_eye(skin=False)
    result = run(design, catalog)
    assert result.pieces_before == 2 and result.pieces_after == 1
    assert not result.recoloured.any()
    assert cells(result.added) == {(2, 1, 6)}
    assert result.design.colors[2, 1, 6] == WHITE
    (note,) = result.notes
    assert note.startswith("Added 1 White cell at x=2, y=1, z=6 under the Light Bluish Grey part")
    assert "only at its side" in note and "reaches across" in note


def test_a_clamp_goes_on_top_when_there_is_no_room_under(catalog):
    design = whisker_through_an_eye(skin=False)
    # a detail part stands in the cell under the root, so nothing can be added there
    design.details.append(Detail(part="3070b", color=BLACK, x=2, y=1, z=6))
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert (2, 1, 8) in cells(result.added)
    assert result.design.colors[2, 1, 8] == WHITE
    assert any("on top of the Light Bluish Grey part" in n for n in result.notes)


def test_a_sheet_on_the_ground_is_thickened_from_above(catalog):
    # a base plate 12 x 12 studs, one plate thin, on the ground under a tower: nothing can
    # go beneath it, so a plate goes on top of its loose parts, in its colour
    c = grid((12, 12, 10))
    c[:, :, 0] = GREY
    c[4:8, 4:8, 1:10] = WHITE
    design = Design(colors=c)
    # the loose repair alone (the weak-spot phase then adds white cells beside the tower)
    result = run(design, catalog, max_sturdy_solves=0)
    assert result.pieces_before > 1 and result.pieces_after == 1
    added = cells(result.added)
    assert added and all(z == 1 for _, _, z in added)
    assert (result.design.colors[result.added] == GREY).all()
    assert any(
        "on top of the sheet" in n and "on the ground" in n and "z=1" in n for n in result.notes
    )


def test_a_partly_covered_cell_takes_the_colour_painted_around_it(catalog):
    # a white column stands under the whisker's root, and then the whole head is painted red
    # by an edit; the partly covered cell between the root and the column still remembers
    # the head as white (edits do not change the skin). Filled white, it would be a white
    # cell in a model that has none left.
    from bricksnap.design import apply_ops

    design = whisker_through_an_eye()
    assert design.skin is not None
    design.colors[2, 1, 0:6] = WHITE
    ops = [
        {"op": "paint", "shape": {"type": "box", "min": cell, "max": cell}, "color": RED}
        for cell in np.argwhere(design.colors == WHITE).tolist()
    ]
    assert all(r.applied for r in apply_ops(design, ops, catalog))
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(2, 1, 6)}
    assert result.design.colors[2, 1, 6] == RED
    assert not (result.design.colors == WHITE).any()
    (note,) = result.notes
    assert note.startswith("Filled 1 partly covered cell at x=2, y=1, z=6 Red")
    assert "White" not in note


def test_partly_covered_cells_two_steps_from_the_piece_are_used(catalog):
    # the only partly covered cell touching the whisker is grey, over its root and beside
    # the white head: it cannot hold the whisker by itself. A white one on top of it, beside
    # the head, can: grey on the whisker, white reaching into the head.
    design = whisker_through_an_eye(skin=False)
    assert design.skin is not None
    design.skin[2, 1, 8] = GREY
    design.skin[2, 1, 9] = WHITE
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(2, 1, 8), (2, 1, 9)}
    assert result.design.colors[2, 1, 8] == GREY
    assert result.design.colors[2, 1, 9] == WHITE
    (note,) = result.notes
    assert note.startswith("Filled 2 partly covered cells at x=2, y=1, z=8 to 9")


def test_no_clamp_for_a_piece_with_the_model_above_or_below_it(catalog):
    from bricksnap.buildable import _clamp

    design = whisker_through_an_eye(skin=False)
    c = design.colors
    piece = c == GREY
    target = (c != EMPTY) & ~piece
    nothing = np.zeros(c.shape, dtype=bool)
    assert _clamp(c, piece, target, nothing, c)[0] == {(2, 1, 6): WHITE}
    for z in (6, 8):  # a cell of the model directly under, or on, the whisker's tip
        held = c.copy()
        held[0, 1, z] = WHITE
        assert _clamp(held, piece, (held != EMPTY) & ~piece, nothing, held) == ({}, False)


def mushroom_on_a_sheet() -> Design:
    """A white body on a stem, standing on a white sheet one plate thin on the ground, with a
    few features in other colours and partly covered cells around it (a random test design
    that showed a stray thickening cell)."""
    c = grid((14, 12, 16))
    c[2:9, 3:8, 0] = WHITE  # the sheet on the ground
    c[4:6, 5:7, 1:3] = WHITE  # the stem
    c[3:8, 4:7, 3:7] = WHITE  # the body
    c[7, 5, 3] = BROWN
    c[8, 5, 3] = PINK
    c[1:3, 5, 5] = BLACK
    c[6, 4, 7:9] = GREY
    s = grid(c.shape)
    skin = {
        WHITE: [(1, 4, 0), (2, 4, 3), (3, 6, 1), (3, 7, 1), (3, 7, 4), (4, 3, 1), (4, 7, 4),
                (5, 3, 6), (5, 6, 7), (6, 6, 7), (6, 7, 4), (7, 3, 5), (7, 5, 7), (7, 7, 1),
                (7, 8, 0), (8, 5, 1), (8, 5, 5), (8, 6, 1), (8, 6, 5), (9, 4, 0)],
        BLACK: [(1, 5, 6), (2, 6, 5)],
        BROWN: [(3, 3, 3), (5, 7, 4)],
        GREY: [(3, 3, 4)],
        PINK: [(5, 5, 7), (8, 6, 3)],
    }  # fmt: skip
    for colour, where in skin.items():
        for cell in where:
            s[cell] = colour
    return Design(colors=c, skin=s)


def test_a_thickening_rests_on_the_sheet_not_on_cells_other_repairs_added(catalog):
    # a partly covered cell filled for one loose piece once counted as part of the sheet,
    # and the plate added on top of the sheet stood on it; when the partly covered cell was
    # taken away again, a cell of the plate was left with nothing above or below it
    design = mushroom_on_a_sheet()
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert design.skin is not None
    filled = design.filled
    for x, y, z in cells(result.added & (design.skin == EMPTY)):
        below = z > 0 and filled[x, y, z - 1]
        above = z + 1 < filled.shape[2] and filled[x, y, z + 1]
        assert below or above, (x, y, z)


def test_partly_covered_cells_over_or_under_the_piece_are_tried_alone_first(catalog):
    # two partly covered cells touch the whisker: one under its root, beside the cheek, and
    # one in front of its root. Filled together, the one in front gets in the way of the
    # layout and the whisker stays loose; the one under the root holds it by itself.
    design = whisker_through_an_eye(skin=False)
    assert design.skin is not None
    design.skin[2, 1, 6] = WHITE
    design.skin[2, 0, 7] = WHITE
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(2, 1, 6)}
    assert result.design.colors[2, 1, 6] == WHITE


def test_partly_covered_cells_keep_their_colour_in_a_design_nobody_edited(catalog):
    # straight from the conversion, a partly covered cell's colour is the model's own there,
    # even where no filled cell around it has that colour (a stripe that is only skin)
    design = whisker_through_an_eye(skin=False)
    assert design.skin is not None
    design.colors[2, 1, 0:6] = WHITE
    design.skin[2, 1, 6] = YELLOW
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(2, 1, 6)}
    assert result.design.colors[2, 1, 6] == YELLOW


# ---- stage 3: the worst weak spots --------------------------------------------------------------


def heavy_limit(design: Design) -> float:
    """Cells that must hang on a lone link for it to be heavy (the contract's numbers)."""
    return max(12.0, min(40.0, design.filled.sum() / 10))


def weakness(design: Design, catalog) -> tuple[int, int]:
    """(heaviest load in cells, number of heavy lone links) of a fresh layout of the Design,
    worked out independently of the module: ``connect.lone_links`` on ``layout.solve``."""
    links = lone_links(solve(design, catalog), catalog)
    limit = heavy_limit(design)
    return max((ln.cells for ln in links), default=0), sum(ln.cells >= limit for ln in links)


def crown_on_one_cell(skin: bool = True) -> Design:
    """A white body 6 x 6 studs and two bricks tall, and a white crown as big on top of it,
    joined through ONE cell: everything above hangs on a single stud. With ``skin``, the
    model passes partly through the ring of cells around that one, some white and some
    yellow, as the sample pineapple does between its body and its crown."""
    c = grid((8, 8, 14))
    c[1:7, 1:7, 0:6] = WHITE
    c[3, 3, 6] = WHITE
    c[1:7, 1:7, 7:13] = WHITE
    s = grid(c.shape)
    if skin:
        s[2:5, 2:5, 6] = WHITE
        s[2, 2:5, 6] = YELLOW
        s[3, 3, 6] = EMPTY
    return Design(colors=c, skin=s)


def block_beside_block() -> Design:
    """A red block beside a white one, touching it side by side on the plane x = 3|4 and
    resting on a single white stud: hidden white cells at the seam, behind the red."""
    c = grid((10, 6, 10))
    c[0:4, 1:5, 0:9] = WHITE
    c[4:8, 1:5, 3:9] = RED
    c[4, 1, 0:3] = WHITE
    return Design(colors=c)


def pod_beside_a_hull() -> Design:
    """A grey pod beside a white hull that is a wall one stud thin (every cell of it can be
    seen), touching it only side by side and resting on one white stud."""
    c = grid((8, 10, 10))
    c[2, 0:10, 0:9] = WHITE
    c[3:6, 3:6, 3:9] = GREY
    c[3, 3, 0:3] = WHITE
    return Design(colors=c)


def neck_one_cell_wide() -> Design:
    """A white body and a white head joined by a neck that really is one cell wide: no
    partly covered cell beside it."""
    c = grid((8, 8, 16))
    c[1:7, 1:7, 0:6] = WHITE
    c[3, 3, 6:9] = WHITE
    c[1:7, 1:7, 9:15] = WHITE
    return Design(colors=c)


def test_a_crown_on_one_cell_is_held_by_the_partly_covered_cells_around_it(catalog):
    design = crown_on_one_cell()
    heaviest, heavy = weakness(design, catalog)
    assert heaviest >= 200 and heavy >= 1  # the crown hangs on one stud
    result = run(design, catalog)
    assert result.pieces_before == result.pieces_after == 1
    after, _ = weakness(result.design, catalog)
    assert after < heaviest
    assert result.added.any() and not result.recoloured.any()
    assert design.skin is not None
    # only partly covered cells, each in its own colour, and all in the level of the joint
    assert (design.skin[result.added] != EMPTY).all()
    assert np.array_equal(result.design.colors[result.added], design.skin[result.added])
    assert {z for _, _, z in cells(result.added)} == {6}
    (note,) = result.notes
    assert note.startswith("Filled ") and "partly covered cell" in note
    assert "z=6" in note and "hangs on" in note and "less than half a cell" in note


def test_two_colours_side_by_side_are_held_across_the_seam_by_recolouring(catalog):
    design = block_beside_block()
    heaviest, heavy = weakness(design, catalog)
    assert heaviest >= 90 and heavy >= 1
    result = run(design, catalog)  # run() checks no visible cell changed colour
    assert result.pieces_after == 1
    assert weakness(result.design, catalog)[0] < heaviest
    assert not result.added.any() and result.recoloured.any()
    assert (result.design.colors[result.recoloured] == RED).all()
    # behind the red, at most two studs from the seam
    assert all(x in (2, 3) for x, _, _ in cells(result.recoloured))
    (note,) = result.notes
    assert note.startswith("Recoloured ") and "hidden cell" in note and "Red" in note


def test_a_pod_touching_a_hull_only_side_by_side_gets_one_clamp_cell(catalog):
    design = pod_beside_a_hull()
    heaviest, heavy = weakness(design, catalog)
    assert heaviest >= 45 and heavy >= 1
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert weakness(result.design, catalog)[0] < heaviest
    assert not result.recoloured.any()
    ((x, y, z),) = cells(result.added)
    assert result.design.colors[x, y, z] == WHITE  # the hull's colour
    # directly under or on a cell of the pod, and beside a cell of the hull in that level
    assert GREY in (design.colors[x, y, z + 1], design.colors[x, y, z - 1])
    assert design.colors[x - 1, y, z] == WHITE
    note = result.notes[0]
    assert note.startswith("Added 1 White cell") and "reaches across" in note


def test_a_neck_that_really_is_one_cell_wide_is_left_and_the_note_says_so(catalog):
    design = neck_one_cell_wide()
    heaviest, heavy = weakness(design, catalog)
    assert heaviest >= 180 and heavy >= 1
    result = run(design, catalog)
    assert not result.added.any() and not result.recoloured.any()
    assert result.design.fingerprint() == design.fingerprint()
    assert weakness(result.design, catalog)[0] == heaviest
    (note,) = result.notes  # the links stacked in the neck are one weak spot
    assert "x=3, y=3" in note and "hangs on" in note
    assert "no partly covered cell" in note and "that thin" in note


def test_a_model_with_no_heavy_lone_link_is_returned_unchanged(catalog):
    padded = grid((8, 6, 8))
    padded[1:7, 1:5, 0:6] = WHITE
    skin = grid(padded.shape)
    skin[0, 1:5, 0:6] = WHITE
    skin[1:7, 1:5, 6] = WHITE
    design = Design(colors=padded, skin=skin)
    assert weakness(design, catalog)[1] == 0
    result = run(design, catalog)
    assert_unchanged(design, result)
    assert result.build.parts == solve(design, catalog).parts


def test_the_weak_spot_phase_is_bounded_in_solves(catalog, monkeypatch):
    import bricksnap.layout

    calls = []
    real = bricksnap.layout.solve

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(bricksnap.layout, "solve", counting)
    for budget in (0, 1, 8):
        calls.clear()
        design = crown_on_one_cell()
        result = make_buildable(design, catalog, max_sturdy_solves=budget)
        assert len(calls) <= 1 + budget
        if budget == 0:  # no phase at all: exactly as before this addition
            assert result.design.fingerprint() == design.fingerprint()
            assert result.notes == []
    calls.clear()
    make_buildable(neck_one_cell_wide(), catalog)
    assert len(calls) == 1  # nothing could be tried there, so nothing was solved


def test_weak_spots_are_cured_after_a_loose_piece_is_joined(catalog):
    # the crown on one cell, with a nose loose on the body's front: the pass first joins
    # the nose, then holds the crown
    design = crown_on_one_cell()
    design.colors[3:5, 0, 2:4] = PINK
    heaviest, _ = weakness(design, catalog)
    result = run(design, catalog)
    assert result.pieces_before > 1 and result.pieces_after == 1
    assert weakness(result.design, catalog)[0] < heaviest
    assert any(n.startswith("Recoloured") and "Dark Pink" in n for n in result.notes)
    assert any(n.startswith("Filled") and "hangs on" in n for n in result.notes)


# ---- stage 3, after review: few cells, a bound that binds, time, and what is left ------------


def heads_on_a_bar(*heads: tuple[int, bool]) -> Design:
    """A white bar 6 studs wide and two bricks tall, with white heads standing on it in a row,
    each joined to it through ONE cell (its neck), so that each head hangs on a single stud.
    ``heads`` gives each head's length along y (6 studs wide, 6 plates tall) and whether the
    model passes partly through the ring of cells around its neck, as in crown_on_one_cell.
    Two empty rows lie between heads."""
    length = sum(w for w, _ in heads) + 2 * len(heads)
    c = grid((8, length + 1, 14))
    s = grid(c.shape)
    c[1:7, 1:length, 0:6] = WHITE
    y = 1
    for w, skin in heads:
        mid = y + w // 2
        c[3, mid, 6] = WHITE
        c[1:7, y : y + w, 7:13] = WHITE
        if skin:
            s[2:5, mid - 1 : mid + 2, 6] = WHITE
            s[3, mid, 6] = EMPTY
        y += w + 2
    return Design(colors=c, skin=s)


def counted_solves(monkeypatch) -> list[int]:
    """Count the layout solver's solves from now on (one entry per solve)."""
    import bricksnap.layout

    calls: list[int] = []
    real = bricksnap.layout.solve

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(bricksnap.layout, "solve", counting)
    return calls


def test_the_weak_spot_phase_adds_only_cells_it_needs_beside_the_link(catalog):
    # the crown on one cell, with more partly covered cells far from its neck: on the body's
    # side and on top of the crown. Only cells at the neck may be filled, and each one
    # filled must be needed: without it a fresh layout hangs more on a single link.
    design = crown_on_one_cell()
    assert design.skin is not None
    far = [(0, y, z) for y in range(1, 7) for z in (2, 3)]
    far += [(x, y, 13) for x in (2, 3, 4) for y in (2, 3, 4)]
    for c in far:
        design.skin[c] = WHITE
    heaviest, _ = weakness(design, catalog)
    result = run(design, catalog)
    assert result.pieces_after == 1
    added = cells(result.added)
    assert added and not added & set(far)
    assert all(z == 6 and 2 <= x <= 4 and 2 <= y <= 4 for x, y, z in added), added
    score = weakness(result.design, catalog)
    assert score[0] < heaviest
    for c in sorted(added):
        trial = result.design.copy()
        trial.colors[c] = EMPTY
        assert weakness(trial, catalog) > score, f"the added cell {c} holds nothing"


def test_the_weak_spot_phase_keeps_to_its_solves_when_it_needs_more(catalog, monkeypatch):
    # four heads on single studs, each needing a solve of its own: the bound binds
    calls = counted_solves(monkeypatch)
    design = heads_on_a_bar((6, True), (6, True), (6, True), (6, True))
    make_buildable(design, catalog, max_sturdy_solves=0)
    without = len(calls)
    for budget in (1, 2, 8):
        calls.clear()
        result = make_buildable(design, catalog, max_sturdy_solves=budget)
        assert len(calls) <= without + budget, budget
        if budget < 4:
            assert any("ran out of attempts" in n for n in result.notes), result.notes


def test_the_weak_spot_phase_stops_in_time_when_solves_are_slow(catalog, monkeypatch):
    # every solve "takes" 3 seconds on a clock the test controls: the pass must still end
    # in under 10 seconds, curing what it can in that time, and say it ran out
    import types

    import bricksnap.buildable
    import bricksnap.layout

    clock = [0.0]
    real = bricksnap.layout.solve

    def slow(*args, **kwargs):
        clock[0] += 3.0
        return real(*args, **kwargs)

    monkeypatch.setattr(bricksnap.layout, "solve", slow)
    monkeypatch.setattr(
        bricksnap.buildable, "time", types.SimpleNamespace(perf_counter=lambda: clock[0])
    )
    design = heads_on_a_bar((6, True), (6, True), (6, True))
    result = make_buildable(design, catalog)
    assert clock[0] < 10
    assert result.added.any()  # it had time for one head
    assert any("ran out of attempts" in n for n in result.notes), result.notes


def test_weak_spots_not_reached_say_whether_anything_could_be_tried(catalog):
    # two heads that partly covered cells can hold, and a smaller one on a neck that really
    # is one cell wide. One solve cures one head; the other is not tried for want of
    # solves, and the narrow neck could not have been helped at all: the notes tell apart
    # "run again" from "make it wider".
    design = heads_on_a_bar((6, True), (6, True), (4, False))
    result = run(design, catalog, max_sturdy_solves=1)
    left = [n for n in result.notes if n.startswith("Still hanging")]
    (neck,) = [n for n in left if "x=3, y=19" in n]
    assert "ran out" not in neck and "that thin" in neck
    assert any("ran out of attempts" in n and "x=3, y=19" not in n for n in left), left
