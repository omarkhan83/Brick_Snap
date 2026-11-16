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
from bricksnap.connect import connection_graph, occupancy
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
    result = run(design, catalog)
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


def test_nose_on_the_top_edge_of_a_ledge_reaches_over_it(catalog):
    # the ledge cell behind the nose's lower row can be seen (air above it), so nothing can
    # be recoloured; two cells beside the nose's upper row, resting on the ledge, join it
    design = nose_on_ledge_top()
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
    # and a tall post in front of the face is no repair; it is reported instead
    c = grid((8, 7, 10))
    c[:, 1:, :] = WHITE
    c[:, 0, 0] = WHITE
    c[3:5, 0, 9] = PINK
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
        lambda: shapes.hollowed(shapes.sphere(12)),
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
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == result.pieces_before == 3
    loose = [n for n in result.notes if n.startswith("Still loose")]
    assert len(loose) == 1
    assert loose[0].startswith("Still loose: the Black part at x=0 to 4, y=1, z=5")
    assert "can be seen" in loose[0]
    assert "in its own colour" not in loose[0]


def test_a_sheet_lying_on_the_ground_is_not_told_to_stand_on_something(catalog):
    # a base plate 12 x 12 studs, one plate thin, on the ground under a tower
    c = grid((12, 12, 10))
    c[:, :, 0] = GREY
    c[4:8, 4:8, 1:10] = WHITE
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
    (note,) = result.notes
    assert "above the Red part" in note and "up to the model" in note
    assert "under" not in note


def test_a_column_under_a_piece_that_touches_the_model_says_so(catalog):
    # a red cell beside the top edge of a white block (the white cell it touches can be
    # seen), over a white ledge two plates below: a short column down to the ledge holds it
    c = grid((9, 5, 4))
    c[0:6, :, :] = WHITE
    c[6:9, :, 0] = WHITE
    c[6, 2, 3] = RED
    design = Design(colors=c)
    result = run(design, catalog)
    assert result.pieces_after == 1
    assert cells(result.added) == {(6, 2, 1), (6, 2, 2)}
    (note,) = result.notes
    assert "under the Red part" in note and "only at its side" in note
    assert "hung in the air" not in note
