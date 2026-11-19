"""Tests for bricksnap.ldraw: Build to LDraw text.

The real LDraw library is not needed: the bounding boxes below were measured once by expanding
each part file through all its sub-files (tools/catalog/ldraw_geom.py) and are hard-coded.
"""

from __future__ import annotations

import itertools
import math

import pytest

from bricksnap.catalog import Catalog, Colour, Part
from bricksnap.ldraw import (
    GENERATOR_LINE,
    ROTATION_MATRICES,
    format_number,
    placement_to_ldraw,
    to_ldraw,
)
from bricksnap.types import Build, Placement

ROTS = (0, 90, 180, 270)

# Whole-part bounding boxes (studs included) in each part's own LDraw coordinates, from the
# real LDraw library. Y points down, so min[1] is the top (the stud tops, where there are
# studs). "stud" is how far studs (or anything else) stick up above the body.
REAL_BOXES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "3001": ((-40.0, -4.0, -20.0), (40.0, 24.0, 20.0)),  # brick 2 x 4
    "3024": ((-10.0, -4.0, -10.0), (10.0, 8.0, 10.0)),  # plate 1 x 1
    "3040b": ((-10.0, -4.0, -30.0), (10.0, 24.0, 10.0)),  # slope 45 2 x 1, origin on stud
    "3665b": ((-10.0, -4.0, -30.0), (10.0, 24.0, 10.0)),  # inverted slope 45 2 x 1
    "4286": ((-10.0, -4.0, -50.0), (10.0, 24.0, 10.0)),  # slope 33 3 x 1, origin on stud
    "54200": ((-10.0, -15.6, -10.0), (10.0, 0.0, 10.0)),  # cheese slope, origin on bottom
    "85984": ((-20.0, -15.6, -10.0), (20.0, 0.0, 10.0)),  # cheese slope 1 x 2
    "11477": ((-10.0, -16.00006098, -20.0), (10.0, 0.0, 20.0)),  # curved slope, origin bottom
}
STUD_HEIGHT = {"3001": 4.0, "3024": 4.0, "3040b": 4.0, "3665b": 4.0, "4286": 4.0}
# LDraw models the cheese slopes 15.6 LDU tall (flattened top) instead of 16.
TOP_SLACK = {"54200": 0.4, "85984": 0.4, "11477": 0.001}


def _transform_box(lo, hi, position, matrix):
    """Bounding box of a box's eight corners after LDraw's  p' = M p + position."""
    a, b, c, d, e, f, g, h, i = matrix
    pts = []
    for x, y, z in itertools.product((lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2])):
        pts.append(
            (
                a * x + b * y + c * z + position[0],
                d * x + e * y + f * z + position[1],
                g * x + h * y + i * z + position[2],
            )
        )
    mins = tuple(min(p[k] for p in pts) for k in range(3))
    maxs = tuple(max(p[k] for p in pts) for k in range(3))
    return mins, maxs


def _cell_box(catalog: Catalog, p: Placement):
    """The LDraw box the contract says the part must occupy."""
    w, d, h = catalog.footprint(p)
    lo = (20.0 * p.x, -8.0 * (p.z + h), 20.0 * p.y)
    hi = (20.0 * (p.x + w), -8.0 * p.z, 20.0 * (p.y + d))
    return lo, hi


def _parse(text: str):
    """Parse type-1 lines back into (colour, position, matrix, file)."""
    out = []
    for line in text.splitlines():
        tok = line.split()
        if tok and tok[0] == "1":
            assert len(tok) == 15, line
            nums = [float(t) for t in tok[2:14]]
            out.append((int(tok[1]), tuple(nums[0:3]), tuple(nums[3:12]), tok[14]))
    return out


def _mini_catalog(*parts: Part) -> Catalog:
    return Catalog(parts, [Colour(code=4, name="Red", rgb=(201, 26, 9), bricklink_id=5)])


def _part(
    pid: str, sx: int, sz: int, h: int, body_min, body_max, ldraw_file: str | None = None
) -> Part:
    return Part(
        id=pid,
        ldraw_file=ldraw_file or f"{pid}.dat",
        bricklink_id=pid,
        name=f"Test part {pid}",
        kind="brick",
        sx=sx,
        sz=sz,
        h=h,
        studs_top=(),
        antistuds_bottom=True,
        colours=frozenset({4}),
        body_min=body_min,
        body_max=body_max,
    )


# ---- placement_to_ldraw ----------------------------------------------------------------------


def test_worked_example_rot0(catalog):
    pos, m = placement_to_ldraw(Placement("3001", 4, 0, 0, 0, rot=0), catalog)
    assert pos == (40, -24, 20)
    assert m == (1, 0, 0, 0, 1, 0, 0, 0, 1)


def test_worked_example_rot90(catalog):
    pos, m = placement_to_ldraw(Placement("3001", 4, 0, 0, 0, rot=90), catalog)
    assert pos == (20, -24, 40)
    assert m == (0, 0, -1, 0, 1, 0, 1, 0, 0)


def test_matrices_match_contract_table():
    assert ROTATION_MATRICES[0] == (1, 0, 0, 0, 1, 0, 0, 0, 1)
    assert ROTATION_MATRICES[90] == (0, 0, -1, 0, 1, 0, 1, 0, 0)
    assert ROTATION_MATRICES[180] == (-1, 0, 0, 0, 1, 0, 0, 0, -1)
    assert ROTATION_MATRICES[270] == (0, 0, 1, 0, 1, 0, -1, 0, 0)


@pytest.mark.parametrize("rot", ROTS)
def test_matrix_sends_part_axes_where_catalogue_says(rot):
    """Part X goes along grid +x, +y, -x, -y for 0, 90, 180, 270 (grid y is LDraw Z)."""
    m = ROTATION_MATRICES[rot]
    part_x_image = (m[0], m[3], m[6])  # first column
    part_z_image = (m[2], m[5], m[8])  # third column
    expected_x = {0: (1, 0, 0), 90: (0, 0, 1), 180: (-1, 0, 0), 270: (0, 0, -1)}[rot]
    expected_z = {0: (0, 0, 1), 90: (-1, 0, 0), 180: (0, 0, -1), 270: (1, 0, 0)}[rot]
    assert part_x_image == expected_x
    assert part_z_image == expected_z
    assert (m[1], m[4], m[7]) == (0, 1, 0)  # vertical untouched: a rotation, not a flip


@pytest.mark.parametrize("rot", ROTS)
def test_matrices_agree_with_local_to_cell(catalog, rot):
    """The stud at part offset (dx, dz) lands on the cell local_to_cell reports."""
    p = Placement("3002", 4, 5, 6, 0, rot=rot)  # 3 x 2 brick, asymmetric
    pos, m = placement_to_ldraw(p, catalog)
    part = catalog.parts["3002"]
    for dx, dz in part.studs_top:
        # stud centre in the part's own coordinates (origin at the centre of the top face)
        sx = -10.0 * part.sx + 20 * dx + 10
        sz = -10.0 * part.sz + 20 * dz + 10
        wx = m[0] * sx + m[2] * sz + pos[0]
        wz = m[6] * sx + m[8] * sz + pos[2]
        gx, gy = catalog.local_to_cell(p, dx, dz)
        assert (wx, wz) == (20 * gx + 10, 20 * gy + 10)


@pytest.mark.parametrize("pid", sorted(REAL_BOXES))
@pytest.mark.parametrize("rot", ROTS)
def test_real_geometry_lands_on_cells(catalog, pid, rot):
    """The real part, moved by (position, matrix), covers exactly its cells."""
    p = Placement(pid, 71, 3, 5, 7, rot=rot)
    pos, m = placement_to_ldraw(p, catalog)
    lo, hi = _transform_box(*REAL_BOXES[pid], pos, m)
    want_lo, want_hi = _cell_box(catalog, p)
    # across: exact
    assert lo[0] == pytest.approx(want_lo[0], abs=1e-9)
    assert hi[0] == pytest.approx(want_hi[0], abs=1e-9)
    assert lo[2] == pytest.approx(want_lo[2], abs=1e-9)
    assert hi[2] == pytest.approx(want_hi[2], abs=1e-9)
    # bottom: exact, so the part sits on whatever is below it
    assert hi[1] == pytest.approx(want_hi[1], abs=1e-9)
    # top: studs stick up above the cells; cheese slopes are a hair short of two plates
    top = lo[1] + STUD_HEIGHT.get(pid, 0.0)
    assert top - want_lo[1] == pytest.approx(0.0, abs=TOP_SLACK.get(pid, 0.0) + 1e-9)


def test_3001_full_box_matches_contract_example(catalog):
    """The contract's hard-coded 3001 box: x -40..40, y -4..24, z -20..20, studs included."""
    for rot in ROTS:
        p = Placement("3001", 4, 2, 1, 3, rot=rot)
        pos, m = placement_to_ldraw(p, catalog)
        lo, hi = _transform_box((-40, -4, -20), (40, 24, 20), pos, m)
        want_lo, want_hi = _cell_box(catalog, p)
        assert (lo[0], lo[1] + 4, lo[2]) == pytest.approx(want_lo)
        assert hi == pytest.approx(want_hi)


@pytest.mark.parametrize("pid", sorted({"3001", "3005", "3024", "3020", "3034", "3009", "3068b"}))
@pytest.mark.parametrize("rot", ROTS)
def test_plain_parts_use_centre_of_top_face(catalog, pid, rot):
    p = Placement(pid, 4, 2, 3, 6, rot=rot)
    w, d, h = catalog.footprint(p)
    pos, _ = placement_to_ldraw(p, catalog)
    assert pos == (20 * (p.x + w / 2), -8 * (p.z + h), 20 * (p.y + d / 2))


@pytest.mark.parametrize("pid", sorted(set(REAL_BOXES) | {"87087", "4733", "6143", "14769"}))
@pytest.mark.parametrize("rot", ROTS)
def test_catalogue_body_box_lands_on_cells(catalog, pid, rot):
    """Using the catalogue's own body boxes, every odd-origin part fills its cells."""
    part = catalog.parts[pid]
    p = Placement(pid, 71, 1, 2, 4, rot=rot)
    pos, m = placement_to_ldraw(p, catalog)
    lo, hi = _transform_box(part.body_min, part.body_max, pos, m)
    want_lo, want_hi = _cell_box(catalog, p)
    for k in (0, 2):
        assert lo[k] == pytest.approx(want_lo[k], abs=0.01)
        assert hi[k] == pytest.approx(want_hi[k], abs=0.01)
    assert hi[1] == pytest.approx(want_hi[1], abs=1e-9)
    assert lo[1] == pytest.approx(want_lo[1], abs=0.41)


def test_odd_origin_positions_are_known_values(catalog):
    """Spot values worked out by hand from the body boxes (cell (0, 0, 0))."""
    # 45-degree slope 3040b: origin at the centre of its stud cell, which is at part Z max
    assert placement_to_ldraw(Placement("3040b", 4, 0, 0, 0), catalog)[0] == (10, -24, 30)
    assert placement_to_ldraw(Placement("3040b", 4, 0, 0, 0, rot=90), catalog)[0] == (10, -24, 10)
    assert placement_to_ldraw(Placement("3040b", 4, 0, 0, 0, rot=180), catalog)[0] == (10, -24, 10)
    assert placement_to_ldraw(Placement("3040b", 4, 0, 0, 0, rot=270), catalog)[0] == (30, -24, 10)
    # cheese slope: origin on the bottom face, which sits on the cell floor
    assert placement_to_ldraw(Placement("54200", 4, 0, 0, 0), catalog)[0] == (10, 0, 10)
    assert placement_to_ldraw(Placement("54200", 4, 2, 3, 5), catalog)[0] == (50, -40, 70)
    # 3 x 1 slope 4286
    assert placement_to_ldraw(Placement("4286", 4, 0, 0, 0), catalog)[0] == (10, -24, 50)
    assert placement_to_ldraw(Placement("4286", 4, 0, 0, 0, rot=270), catalog)[0] == (50, -24, 10)


def test_slop_in_body_box_does_not_leak_into_position(catalog):
    """6143 is modelled 40.002 LDU wide; the position must still be a clean number."""
    pos, _ = placement_to_ldraw(Placement("6143", 4, 0, 0, 0), catalog)
    assert pos == (20, -24, 20)


def test_slop_tolerance_keeps_trusting_an_offset_body_box():
    """A box a hair wider than its cells is still trusted, so an off-centre origin is honoured.

    The origin sits 5 LDU outside the box, so falling back to "origin in the middle of the
    footprint" would give x = 20 instead of the right -5.
    """
    sloppy = _part("sloppy", 2, 1, 3, (4.999, 0.0, -10.0), (45.001, 24.0, 10.0))
    pos, _ = placement_to_ldraw(Placement("sloppy", 4, 0, 0, 0), _mini_catalog(sloppy))
    assert pos == (-5, -24, 10)


def test_negative_zero_is_never_returned():
    """A position that rounds to zero from below comes back as 0.0, never -0.0."""
    corner = _part("corner", 1, 1, 1, (0.0004, 0.0, 0.0), (20.0004, 8.0, 20.0))
    pos, _ = placement_to_ldraw(Placement("corner", 4, 0, 0, 0), _mini_catalog(corner))
    assert pos == (0, -8, 0)
    assert all(math.copysign(1.0, v) == 1.0 for v in (pos[0], pos[2])), pos
    text = to_ldraw(Build((1, 1, 1), [Placement("corner", 4, 0, 0, 0)]), _mini_catalog(corner))
    assert "-0" not in text.splitlines()[-1].split()


def test_part_sticking_out_keeps_its_main_body_on_the_cell():
    """A body box much bigger than the footprint (a clip) falls back to the origin convention."""
    clip = _part("clip", 1, 1, 1, (-10.0, 0.0, -24.03), (10.0, 8.0, 10.0))
    cat = _mini_catalog(clip)
    for rot, expect in ((0, (30, -8, 50)), (90, (30, -8, 50))):
        pos, _ = placement_to_ldraw(Placement("clip", 4, 1, 2, 0, rot=rot), cat)
        assert pos == expect


def test_offset_origin_synthetic_part():
    """A part whose origin is far from the centre of its top face is still placed right."""
    odd = _part("odd", 2, 1, 3, (5.0, -30.0, 100.0), (45.0, -6.0, 120.0))
    cat = _mini_catalog(odd)
    for rot in ROTS:
        p = Placement("odd", 4, 7, 2, 9, rot=rot)
        pos, m = placement_to_ldraw(p, cat)
        lo, hi = _transform_box(odd.body_min, odd.body_max, pos, m)
        assert (lo, hi) == (
            pytest.approx(_cell_box(cat, p)[0]),
            pytest.approx(_cell_box(cat, p)[1]),
        )


def test_part_without_body_box_uses_standard_origin():
    """A hand-built Part left with the dataclass's empty box is placed like a plain part."""
    bare = Part(
        id="bare",
        ldraw_file="bare.dat",
        bricklink_id="bare",
        name="b",
        kind="brick",
        sx=2,
        sz=1,
        h=3,
        studs_top=(),
        antistuds_bottom=True,
        colours=frozenset({4}),
    )
    cat = _mini_catalog(bare)
    assert placement_to_ldraw(Placement("bare", 4, 0, 0, 0), cat)[0] == (20, -24, 10)
    assert placement_to_ldraw(Placement("bare", 4, 0, 0, 0, rot=90), cat)[0] == (10, -24, 20)
    assert placement_to_ldraw(Placement("bare", 4, 3, 1, 2), cat)[0] == (80, -40, 30)


def test_body_height_far_from_cells_falls_back_to_standard_origin():
    """A box much taller than the part (something hanging below) keeps the top on the cells."""
    hang = _part("hang", 1, 1, 1, (-10.0, 0.0, -10.0), (10.0, 20.0, 10.0))
    pos, _ = placement_to_ldraw(Placement("hang", 4, 0, 0, 2), _mini_catalog(hang))
    assert pos == (10, -24, 10)


def test_rot_360_is_rot_0(catalog):
    a = placement_to_ldraw(Placement("3001", 4, 0, 0, 0, rot=0), catalog)
    b = placement_to_ldraw(Placement("3001", 4, 0, 0, 0, rot=360), catalog)
    assert a == b


def test_bad_rotation_is_rejected_in_plain_words(catalog):
    with pytest.raises(ValueError, match="0, 90, 180 or 270"):
        placement_to_ldraw(Placement("3001", 4, 0, 0, 0, rot=45), catalog)


def test_unknown_part_is_rejected_by_name(catalog):
    with pytest.raises(ValueError, match="9999x"):
        placement_to_ldraw(Placement("9999x", 4, 0, 0, 0), catalog)


# ---- format_number ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, text",
    [
        (0, "0"),
        (0.0, "0"),
        (-0.0, "0"),
        (40.0, "40"),
        (-24, "-24"),
        (12.5, "12.5"),
        (-0.4, "-0.4"),
        (20.0004, "20"),
        (20.0006, "20.001"),
        (1 / 3, "0.333"),
        (-15.6, "-15.6"),
        (1e-9, "0"),
        (-1e-9, "0"),
    ],
)
def test_format_number(value, text):
    assert format_number(value) == text


# ---- to_ldraw --------------------------------------------------------------------------------


def _sample_build() -> Build:
    return Build(
        shape=(10, 10, 12),
        parts=[
            Placement("3001", 4, 0, 0, 0, rot=0),
            Placement("3001", 1, 4, 2, 0, rot=90),
            Placement("3024", 15, 3, 3, 3),
            Placement("3040b", 14, 6, 0, 3, rot=180),
            Placement("54200", 0, 1, 1, 3, rot=270),
        ],
    )


def test_header(catalog):
    text = to_ldraw(_sample_build(), catalog, title="My Duck", author="Ann")
    lines = text.split("\n")
    assert lines[0] == "0 My Duck"
    assert lines[1] == "0 Name: My Duck.ldr"
    assert lines[2] == "0 Author: Ann"
    assert lines[3] == GENERATOR_LINE
    assert "BrickSnap" in lines[3]
    assert lines[3].startswith("0 ")


def test_default_header(catalog):
    lines = to_ldraw(Build((1, 1, 1)), catalog).splitlines()
    assert lines[:3] == ["0 BrickSnap model", "0 Name: BrickSnap model.ldr", "0 Author: BrickSnap"]


def test_empty_build(catalog):
    text = to_ldraw(Build((1, 1, 1)), catalog)
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert len(text.splitlines()) == 4
    assert _parse(text) == []


def test_line_endings(catalog):
    text = to_ldraw(_sample_build(), catalog)
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert all(line == line.strip() and line for line in text[:-1].split("\n"))


def test_type1_line_format(catalog):
    text = to_ldraw(Build((4, 4, 3), [Placement("3001", 4, 0, 0, 0)]), catalog)
    assert text.splitlines()[-1] == "1 4 40 -24 20 1 0 0 0 1 0 0 0 1 3001.dat"


def test_line_uses_the_parts_ldraw_file_not_its_id():
    """The last field is Part.ldraw_file, which need not be '<id>.dat'."""
    renamed = _part("x", 1, 1, 1, (-10.0, 0.0, -10.0), (10.0, 8.0, 10.0), ldraw_file="abc123.dat")
    text = to_ldraw(Build((1, 1, 1), [Placement("x", 4, 0, 0, 0)]), _mini_catalog(renamed))
    line = text.splitlines()[-1]
    assert line.split()[-1] == "abc123.dat"
    assert line == "1 4 10 -8 10 1 0 0 0 1 0 0 0 1 abc123.dat"


def test_no_trailing_dot_zero_anywhere(catalog):
    text = to_ldraw(_sample_build(), catalog)
    for line in text.splitlines():
        if line.startswith("1 "):
            for tok in line.split()[1:14]:
                assert not tok.endswith(".0"), line
                assert tok != "-0", line
                if "." in tok:
                    assert len(tok.split(".")[1]) <= 3


def test_round_trip(catalog):
    build = _sample_build()
    text = to_ldraw(build, catalog)
    parsed = _parse(text)
    assert len(parsed) == len(build.parts)
    ordered = sorted(build.parts, key=lambda p: (p.step, p.z, p.y, p.x))
    for p, (colour, pos, m, fname) in zip(ordered, parsed, strict=True):
        want_pos, want_m = placement_to_ldraw(p, catalog)
        assert colour == p.color
        assert pos == pytest.approx(want_pos)
        assert m == tuple(float(v) for v in want_m)
        assert fname == catalog.parts[p.part].ldraw_file


def test_round_trip_recovers_cells(catalog):
    """From the text alone (plus the catalogue's body boxes), every part's cells come back."""
    build = _sample_build()
    by_file = {part.ldraw_file: part for part in catalog.parts.values()}
    recovered = set()
    for _colour, pos, m, fname in _parse(to_ldraw(build, catalog)):
        part = by_file[fname]
        lo, hi = _transform_box(part.body_min, part.body_max, pos, m)
        x0, y0, z0 = round(lo[0] / 20), round(lo[2] / 20), round(-hi[1] / 8)
        rot = next(r for r, mm in ROTATION_MATRICES.items() if tuple(map(float, mm)) == m)
        recovered.add((part.id, x0, y0, z0, rot))
    assert recovered == {(p.part, p.x, p.y, p.z, p.rot) for p in build.parts}


def test_order_is_step_z_y_x(catalog):
    parts = [
        Placement("3024", 1, 2, 0, 1),
        Placement("3024", 2, 1, 0, 1),
        Placement("3024", 3, 0, 1, 1),
        Placement("3024", 4, 5, 5, 0),
        Placement("3024", 5, 0, 0, 2),
    ]
    colours = [c for c, *_ in _parse(to_ldraw(Build((6, 6, 3), parts), catalog))]
    assert colours == [4, 2, 1, 3, 5]


def test_no_step_lines_without_steps(catalog):
    text = to_ldraw(_sample_build(), catalog)
    assert "0 STEP" not in text


def test_step_lines_follow_each_step(catalog):
    parts = [
        Placement("3001", 4, 0, 0, 0, step=1),
        Placement("3001", 4, 0, 2, 0, step=1),
        Placement("3024", 1, 0, 0, 3, step=2),
        Placement("3024", 2, 1, 0, 3, step=3),
        Placement("3024", 3, 2, 0, 3, step=3),
    ]
    lines = to_ldraw(Build((4, 4, 4), list(reversed(parts))), catalog).splitlines()[4:]
    kinds = ["S" if ln == "0 STEP" else ln.split()[1] for ln in lines]
    assert kinds == ["4", "4", "S", "1", "S", "2", "3", "S"]
    assert lines[-1] == "0 STEP"


def test_step_lines_when_only_some_parts_have_a_step(catalog):
    parts = [Placement("3024", 2, 0, 0, 0, step=2), Placement("3024", 1, 1, 0, 0, step=0)]
    lines = to_ldraw(Build((2, 1, 1), parts), catalog).splitlines()[4:]
    kinds = ["S" if ln == "0 STEP" else ln.split()[1] for ln in lines]
    assert kinds == ["1", "S", "2", "S"]


def test_steps_sort_before_height(catalog):
    parts = [Placement("3024", 1, 0, 0, 0, step=2), Placement("3024", 2, 0, 0, 5, step=1)]
    colours = [c for c, *_ in _parse(to_ldraw(Build((1, 1, 6), parts), catalog))]
    assert colours == [2, 1]


def test_title_and_author_are_one_line(catalog):
    text = to_ldraw(
        Build((1, 1, 1)),
        catalog,
        title="Evil\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat",
        author="A\r\nB\tC",
    )
    lines = text.splitlines()
    assert len(lines) == 4
    assert lines[0] == "0 Evil 1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"
    assert lines[2] == "0 Author: A B C"
    assert _parse(text) == []


@pytest.mark.parametrize(
    "title, name",
    [
        ("STEP", "STEP"),
        ("step", "step"),
        ("FILE duck", "FILE duck"),
        ("NOFILE", "NOFILE"),
        ("!LDRAW_ORG Part", "_LDRAW_ORG Part"),
        ("// comment", "__ comment"),
        ("Name: other.ldr", "Name_ other"),
        ("author: someone", "author_ someone"),
        ("ROTSTEP 0 0 0 ABS", "ROTSTEP 0 0 0 ABS"),
        ("BFC INVERTNEXT", "BFC INVERTNEXT"),
        ("PAUSE", "PAUSE"),
        ("LPUB PLI BEGIN IGN", "LPUB PLI BEGIN IGN"),
    ],
)
def test_title_that_is_a_meta_command_stays_a_description(catalog, title, name):
    parts = [Placement("3001", 4, 0, 0, 0, step=1), Placement("3001", 1, 0, 0, 3, step=2)]
    lines = to_ldraw(Build((4, 4, 8), parts), catalog, title=title).splitlines()
    assert lines[0] == f"0 Model: {title}"
    assert lines[1] == f"0 Name: {name}.ldr"
    # One STEP line per step, and nothing between the header and the first part.
    assert lines.count("0 STEP") == 2
    assert lines[4].startswith("1 ")


@pytest.mark.parametrize("title", ["Stepping stone", "Filed duck", "My !duck", "Duck // big"])
def test_ordinary_title_is_not_prefixed(catalog, title):
    lines = to_ldraw(Build((1, 1, 1)), catalog, title=title).splitlines()
    assert lines[0] == f"0 {title}"


def test_blank_title_and_author_fall_back(catalog):
    lines = to_ldraw(Build((1, 1, 1)), catalog, title=" \n ", author="").splitlines()
    assert lines[0] == "0 BrickSnap model"
    assert lines[1] == "0 Name: BrickSnap model.ldr"
    assert lines[2] == "0 Author: BrickSnap"


@pytest.mark.parametrize(
    "title, name",
    [
        ("duck", "duck.ldr"),
        ("../../etc/passwd", "_.._etc_passwd.ldr"),
        ('a/b\\c:d*e?f"g<h>i|j', "a_b_c_d_e_f_g_h_i_j.ldr"),
        ("café ☕", "caf_ _.ldr"),
        ("model.ldr", "model.ldr"),
        ("...", "model.ldr"),
        ("a" * 79 + " bcd", "a" * 79 + ".ldr"),
        ("a" * 79 + ".bcd", "a" * 79 + ".ldr"),
        ("a" * 200, "a" * 80 + ".ldr"),
    ],
)
def test_name_line_is_file_safe(catalog, title, name):
    lines = to_ldraw(Build((1, 1, 1)), catalog, title=title).splitlines()
    assert lines[1] == f"0 Name: {name}"
    stem = name[: -len(".ldr")]
    assert "/" not in stem and "\\" not in stem and not stem.startswith(".")


def test_unknown_part_in_build_is_named(catalog):
    build = Build((4, 4, 4), [Placement("3001", 4, 0, 0, 0), Placement("nope42", 4, 0, 0, 3)])
    with pytest.raises(ValueError, match="nope42"):
        to_ldraw(build, catalog)


def test_every_catalogue_part_writes(catalog):
    """Every part in the table, in all four rotations, produces a well-formed line."""
    parts = []
    for i, pid in enumerate(sorted(catalog.parts)):
        for j, rot in enumerate(ROTS):
            parts.append(Placement(pid, 71, 10 * j, 10 * i, 0, rot=rot))
    text = to_ldraw(Build((40, 10 * len(catalog.parts), 3), parts), catalog)
    parsed = _parse(text)
    assert len(parsed) == len(parts)
    assert {f for *_, f in parsed} == {p.ldraw_file for p in catalog.parts.values()}


# ---- stage 4: sideways parts ----------------------------------------------------------------


def _apply(position, matrix, point):
    a, b, c, d, e, f, g, h, i = matrix
    x, y, z = point
    return (
        position[0] + a * x + b * y + c * z,
        position[1] + d * x + e * y + f * z,
        position[2] + g * x + h * y + i * z,
    )


@pytest.mark.parametrize("face", ["front", "right", "back", "left"])
def test_a_sideways_tile_lies_on_the_side_stud_of_its_brick(face):
    from bricksnap.catalog import load_catalog
    from bricksnap.types import FACE_OUT

    cat = load_catalog()
    ox, oy = FACE_OUT[face]
    x, y, z = 5, 5, 6
    tile = Placement("98138", 0, x, y, z, face=face)
    brick = cat.side_stud_brick(face, 0, x - ox, y - oy, z)
    tp, tm = placement_to_ldraw(tile, cat)
    bp, bm = placement_to_ldraw(brick, cat)
    # the tile's top points out of the face (its own -Y)
    up = _apply((0, 0, 0), tm, (0, -1, 0))
    assert up == (ox, 0, oy)
    # 87087's stud is on its own -Z face, 10 LDU below its top: turned, it is the tile's
    # bottom centre
    stud = _apply(bp, bm, (0, 10, -10))
    bottom = _apply(tp, tm, (0, 8, 0))
    assert stud == pytest.approx(bottom)
    # the tile's body stays inside its column, against the brick, its top level with the
    # brick's top and 4 LDU above its bottom
    corners = [
        _apply(tp, tm, (cx, cy, cz)) for cx in (-10, 10) for cy in (0, 8) for cz in (-10, 10)
    ]
    xs, ys, zs = zip(*corners, strict=True)
    assert min(xs) >= 20 * x and max(xs) <= 20 * (x + 1)
    assert min(zs) >= 20 * y and max(zs) <= 20 * (y + 1)
    assert (min(ys), max(ys)) == (-8 * (z + 3), -8 * z - 4)
    if face == "front":
        assert tp == (110, -62, 112) and tm == (1, 0, 0, 0, 0, -1, 0, 1, 0)
