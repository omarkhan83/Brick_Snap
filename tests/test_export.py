from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from dataclasses import replace

import numpy as np
import pytest

from bricksnap.catalog import Catalog, Part
from bricksnap.export import (
    CSV_HEADER,
    PartLine,
    parts_list,
    to_csv,
    to_wanted_list,
    unlisted,
    write_exports,
)
from bricksnap.pipeline import create_project, rebuild
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Placement

RED, BLUE, BLACK = 4, 1, 0
UNKNOWN_COLOUR_CODE = 9999


def build_of(*parts: tuple[str, int]) -> Build:
    return Build(
        shape=(40, 40, 40),
        parts=[Placement(part=p, color=c, x=i % 40, y=0, z=0) for i, (p, c) in enumerate(parts)],
    )


def read_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def items(xml: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml)
    assert root.tag == "INVENTORY"
    out = []
    for item in root:
        assert item.tag == "ITEM"
        out.append({child.tag: child.text or "" for child in item})
    return out


BASE_LINE = PartLine(
    part="3001",
    bricklink_id="3001",
    name="Brick 2 x 4",
    colour=RED,
    colour_name="Red",
    bricklink_colour=5,
    quantity=1,
)


def line(**changes) -> PartLine:
    return replace(BASE_LINE, **changes)


def differing_ids(catalog: Catalog) -> list[Part]:
    return [p for p in catalog.parts.values() if p.bricklink_id != p.id]


# ---- parts_list ---------------------------------------------------------------------------


def test_counts_add_up_to_the_number_of_parts(catalog):
    build = build_of(*[("3001", RED)] * 5, *[("3001", BLUE)] * 2, ("3024", RED), ("3005", RED))
    lines = parts_list(build, catalog)
    assert sum(ln.quantity for ln in lines) == len(build.parts) == 9
    counts = {(ln.part, ln.colour): ln.quantity for ln in lines}
    assert counts == {("3001", RED): 5, ("3001", BLUE): 2, ("3024", RED): 1, ("3005", RED): 1}
    assert len(lines) == len(counts)  # one line per (part, colour)


def test_lines_carry_catalogue_names_and_bricklink_ids(catalog):
    (ln,) = parts_list(build_of(("3001", RED)), catalog)
    assert ln.name == catalog.parts["3001"].name
    assert ln.colour_name == catalog.colours[RED].name
    assert ln.bricklink_colour == catalog.colours[RED].bricklink_id
    assert ln.bricklink_id == "3001"


def test_empty_build_gives_no_lines(catalog):
    lines = parts_list(build_of(), catalog)
    assert lines == []
    assert read_csv(to_csv(lines)) == [list(CSV_HEADER), ["Total", "", "", "", "", "", "0"]]
    assert items(to_wanted_list(lines)) == []


def test_sorted_by_kind_in_catalogue_order_then_part_then_colour(catalog):
    kinds = list(dict.fromkeys(p.kind for p in catalog.parts.values()))
    # bricks, plates, tiles, a slope and an unknown part, given in a jumbled order; part-id
    # order alone would put the tile 2431 first and the brick 3622 after the plates
    build = build_of(
        ("3070b", BLUE),
        ("zz-mystery", RED),
        ("3039", RED),
        ("3024", RED),
        ("3622", RED),
        ("2431", RED),
        ("3005", BLUE),
        ("3020", RED),
        ("3001", RED),
        ("3005", RED),
        ("3024", BLACK),
    )
    lines = parts_list(build, catalog)
    got = [(ln.part, ln.colour) for ln in lines]
    assert got == [
        ("3001", RED),
        ("3005", BLUE),
        ("3005", RED),
        ("3622", RED),
        ("3020", RED),
        ("3024", BLACK),
        ("3024", RED),
        ("2431", RED),
        ("3070b", BLUE),
        ("3039", RED),
        ("zz-mystery", RED),
    ]
    ranks = [kinds.index(catalog.parts[p].kind) for p, _ in got[:-1]]
    assert ranks == sorted(ranks)


def test_sorting_is_stable_whatever_the_build_order(catalog):
    pairs = [("3001", RED), ("3024", BLUE), ("3070b", RED), ("3005", BLACK), ("3024", RED)] * 3
    first = parts_list(build_of(*pairs), catalog)
    second = parts_list(build_of(*reversed(pairs)), catalog)
    assert first == second
    assert to_csv(first) == to_csv(second)
    assert to_wanted_list(first) == to_wanted_list(second)


def test_the_catalogue_has_parts_whose_bricklink_id_differs(catalog):
    ids = {p.id: p.bricklink_id for p in differing_ids(catalog)}
    for ldraw_id in ("3023b", "3070b", "3069b", "3068b", "3062b", "3040b"):
        assert ldraw_id in ids
        assert ids[ldraw_id] == ldraw_id[:-1]


def test_part_exported_under_its_bricklink_id(catalog):
    parts = differing_ids(catalog)
    build = build_of(*[(p.id, next(iter(sorted(p.colours)))) for p in parts])
    lines = parts_list(build, catalog)
    by_part = {ln.part: ln for ln in lines}
    for p in parts:
        assert by_part[p.id].bricklink_id == p.bricklink_id
    xml_ids = {it["ITEMID"] for it in items(to_wanted_list(lines))}
    assert xml_ids == {p.bricklink_id for p in parts}
    assert not xml_ids & {p.id for p in parts}
    rows = read_csv(to_csv(lines))[1:-1]
    assert {(r[0], r[1]) for r in rows} == {(p.id, p.bricklink_id) for p in parts}


def test_unknown_part_and_colour_get_a_line(catalog):
    build = build_of(("zz-mystery", RED), ("3001", UNKNOWN_COLOUR_CODE), ("3001", RED))
    lines = parts_list(build, catalog)
    assert len(lines) == 3
    by_key = {(ln.part, ln.colour): ln for ln in lines}
    mystery = by_key[("zz-mystery", RED)]
    assert (mystery.name, mystery.bricklink_id) == ("unknown part", "")
    assert mystery.colour_name == catalog.colours[RED].name
    odd = by_key[("3001", UNKNOWN_COLOUR_CODE)]
    assert (odd.colour_name, odd.bricklink_colour) == ("unknown colour", None)
    assert odd.name == catalog.parts["3001"].name

    assert unlisted(lines) == [odd, mystery]  # in parts-list order
    rows = read_csv(to_csv(lines))
    assert ["zz-mystery", "", "unknown part", mystery.colour_name, str(RED), "5", "1"] in rows
    assert ["3001", "3001", odd.name, "unknown colour", "9999", "", "1"] in rows
    wanted = items(to_wanted_list(lines))
    assert wanted == [{"ITEMTYPE": "P", "ITEMID": "3001", "COLOR": "5", "MINQTY": "1"}]


# ---- CSV ----------------------------------------------------------------------------------


def test_csv_header_rows_and_total(catalog):
    build = build_of(*[("3001", RED)] * 3, ("3024", BLUE))
    lines = parts_list(build, catalog)
    text = to_csv(lines)
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\r" not in text
    assert (
        text.splitlines()[0]
        == "Part,BrickLink ID,Name,Colour,LDraw colour,BrickLink colour ID,Quantity"
    )
    rows = read_csv(text)
    assert len(rows) == len(lines) + 2
    assert rows[-1] == ["Total", "", "", "", "", "", "4"]
    assert text.splitlines()[-1] == "Total,,,,,,4"
    assert sum(int(r[6]) for r in rows[1:-1]) == 4
    red = catalog.colours[RED]
    assert rows[1] == [
        "3001",
        "3001",
        catalog.parts["3001"].name,
        red.name,
        str(RED),
        str(red.bricklink_id),
        "3",
    ]


def test_names_with_commas_and_quotes_survive_the_csv_round_trip():
    awkward = [
        line(name='Brick 2 x 4, "special", with "quotes"', colour_name='Red, "dark"'),
        line(part="x,1", bricklink_id='9"9', name="Line\nbreak", quantity=4),
    ]
    rows = read_csv(to_csv(awkward))
    assert rows[1][:4] == ["3001", "3001", 'Brick 2 x 4, "special", with "quotes"', 'Red, "dark"']
    assert rows[2][:3] == ["x,1", '9"9', "Line\nbreak"]
    assert rows[-1] == ["Total", "", "", "", "", "", "5"]
    assert all(len(r) == 7 for r in rows)


# ---- wanted list --------------------------------------------------------------------------


def test_wanted_list_parses_and_holds_exactly_the_listed_items(catalog):
    build = build_of(*[("3001", RED)] * 4, ("3023b", BLUE), ("3070b", BLACK), ("zz-mystery", RED))
    lines = parts_list(build, catalog)
    xml = to_wanted_list(lines)
    assert not xml.lstrip().startswith("<?xml")
    assert "<?" not in xml
    assert xml.startswith("<INVENTORY>")
    assert xml.endswith("</INVENTORY>\n")
    listed = [ln for ln in lines if ln not in unlisted(lines)]
    assert items(xml) == [
        {
            "ITEMTYPE": "P",
            "ITEMID": ln.bricklink_id,
            "COLOR": str(ln.bricklink_colour),
            "MINQTY": str(ln.quantity),
        }
        for ln in listed
    ]
    assert [it["ITEMID"] for it in items(xml)] == ["3001", "3023", "3070"]
    # every child element is in the order BrickLink's sample uses
    for item in ET.fromstring(xml):
        assert [c.tag for c in item] == ["ITEMTYPE", "ITEMID", "COLOR", "MINQTY"]


def test_wanted_list_escapes_text():
    xml = to_wanted_list([line(bricklink_id="A&B<1>")])
    assert "A&amp;B&lt;1&gt;" in xml
    assert "A&B" not in xml
    assert items(xml)[0]["ITEMID"] == "A&B<1>"


def test_wanted_list_merges_lines_that_share_a_bricklink_item():
    lines = [
        line(part="3665a", bricklink_id="3665", quantity=2),
        line(part="3665b", bricklink_id="3665", quantity=3),
        line(part="3665b", bricklink_id="3665", colour=BLUE, bricklink_colour=7, quantity=1),
    ]
    assert items(to_wanted_list(lines)) == [
        {"ITEMTYPE": "P", "ITEMID": "3665", "COLOR": "5", "MINQTY": "5"},
        {"ITEMTYPE": "P", "ITEMID": "3665", "COLOR": "7", "MINQTY": "1"},
    ]


def test_unlisted_is_lines_missing_either_bricklink_id():
    good = line()
    no_part = line(part="zz", bricklink_id="")
    no_colour = line(bricklink_colour=None)
    assert unlisted([good, no_part, no_colour]) == [no_part, no_colour]
    assert unlisted([good]) == []
    assert len(items(to_wanted_list([good, no_part, no_colour]))) == 1


def test_a_whole_catalogue_build_exports(catalog):
    """Every part in every colour it comes in: all listed, BrickLink-sized numbers."""
    pairs = [(p.id, c) for p in catalog.parts.values() for c in sorted(p.colours)]
    lines = parts_list(build_of(*pairs), catalog)
    assert len(lines) == len(pairs)
    assert unlisted(lines) == []
    wanted = items(to_wanted_list(lines))
    assert len(wanted) == len(pairs)
    assert all(int(it["MINQTY"]) >= 1 and int(it["COLOR"]) >= 0 for it in wanted)


# ---- write_exports ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_pawn(tmp_path_factory, pawn_path) -> Project:
    project = create_project(pawn_path, studs=8, directory=tmp_path_factory.mktemp("export"))
    rebuild(project)
    return project


def test_write_exports_writes_both_files(built_pawn, catalog):
    paths = write_exports(built_pawn, catalog)
    assert paths == {
        "parts": built_pawn.path / "parts.csv",
        "wanted_list": built_pawn.path / "wanted_list.xml",
    }
    build = built_pawn.load_build()
    rows = read_csv(paths["parts"].read_text(encoding="utf-8"))
    assert rows[0] == list(CSV_HEADER)
    assert rows[-1][0] == "Total"
    assert int(rows[-1][6]) == len(build.parts) > 0
    assert sum(int(r[6]) for r in rows[1:-1]) == len(build.parts)
    wanted = items(paths["wanted_list"].read_text(encoding="utf-8"))
    lines = parts_list(build, catalog)
    assert len(wanted) == len(lines) - len(unlisted(lines))
    assert sum(int(it["MINQTY"]) for it in wanted) + sum(
        ln.quantity for ln in unlisted(lines)
    ) == len(build.parts)
    # no temporary files left behind
    assert not [p for p in built_pawn.path.iterdir() if p.name.endswith(".tmp")]


def test_write_exports_uses_the_shipped_catalogue_by_default(built_pawn, catalog):
    paths = write_exports(built_pawn)
    expected = to_csv(parts_list(built_pawn.load_build(), catalog))
    assert paths["parts"].read_text(encoding="utf-8") == expected


def test_write_exports_before_any_build(tmp_path, pawn_path):
    project = create_project(pawn_path, studs=8, directory=tmp_path)
    with pytest.raises(ProjectError, match="not been built yet. Run 'bricksnap build'"):
        write_exports(project)
    assert not (project.path / "parts.csv").exists()
    assert not (project.path / "wanted_list.xml").exists()


def test_write_exports_with_an_unreadable_build(tmp_path, pawn_path):
    project = create_project(pawn_path, studs=8, directory=tmp_path)
    project.build_path.write_text("{nope", encoding="utf-8")
    with pytest.raises(ProjectError, match="cannot be read. Run 'bricksnap build' again"):
        write_exports(project)
    assert not (project.path / "parts.csv").exists()


def _save_raw_build(project: Project, parts: list[dict]) -> None:
    project.build_path.write_text(
        json.dumps({"shape": [4, 4, 4], "parts": parts}), encoding="utf-8"
    )


def _raw_part(part, color) -> dict:
    return {"part": part, "color": color, "x": 0, "y": 0, "z": 0}


@pytest.mark.parametrize(
    "parts",
    [
        [_raw_part("3001", None)],
        [_raw_part("3001", "red")],
        [_raw_part("3001", 4.9)],
        [_raw_part("3001", True)],
        [_raw_part(77, 4), _raw_part("zz", 4)],
        [_raw_part(["a"], 4)],
    ],
    ids=[
        "no-colour",
        "colour-word",
        "fractional-colour",
        "true-colour",
        "number-part",
        "list-part",
    ],
)
def test_write_exports_with_bad_values_in_the_build(tmp_path, pawn_path, parts):
    project = create_project(pawn_path, studs=8, directory=tmp_path)
    _save_raw_build(project, parts)
    with pytest.raises(ProjectError, match="cannot be read. Run 'bricksnap build' again"):
        write_exports(project)
    assert not (project.path / "parts.csv").exists()
    assert not (project.path / "wanted_list.xml").exists()


def test_write_exports_when_the_build_file_is_a_folder(tmp_path, pawn_path):
    project = create_project(pawn_path, studs=8, directory=tmp_path)
    project.build_path.mkdir()
    with pytest.raises(ProjectError, match="cannot be read. Run 'bricksnap build' again"):
        write_exports(project)
    assert not (project.path / "parts.csv").exists()


@pytest.mark.parametrize("colour", [4.9, 4.5, None, "4", True, float("nan")])
def test_parts_list_rejects_a_colour_that_is_not_a_whole_number(catalog, colour):
    build = Build(shape=(4, 4, 4), parts=[Placement(part="3001", color=colour, x=1, y=2, z=3)])
    with pytest.raises(ValueError, match="x=1, y=2, z=3") as info:
        parts_list(build, catalog)
    assert "whole number" in str(info.value)


def test_parts_list_rejects_a_part_id_that_is_not_text(catalog):
    build = Build(shape=(4, 4, 4), parts=[Placement(part=77, color=RED, x=1, y=2, z=3)])  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="x=1, y=2, z=3"):
        parts_list(build, catalog)


def test_parts_list_accepts_whole_number_colours_of_any_number_type(catalog):
    build = Build(
        shape=(4, 4, 4),
        parts=[
            Placement(part="3001", color=4.0, x=0, y=0, z=0),  # ty: ignore[invalid-argument-type]
            Placement(part="3001", color=np.int64(4), x=1, y=0, z=0),  # ty: ignore[invalid-argument-type]
            Placement(part="3001", color=4, x=2, y=0, z=0),
        ],
    )
    (ln,) = parts_list(build, catalog)
    assert (ln.colour, ln.quantity) == (RED, 3)
    assert type(ln.colour) is int


def test_write_exports_uses_the_catalogue_it_is_given(built_pawn, catalog):
    build = built_pawn.load_build()
    paths = write_exports(built_pawn, Catalog([], []))
    rows = read_csv(paths["parts"].read_text(encoding="utf-8"))[1:-1]
    assert rows and all(r[2] == "unknown part" and r[3] == "unknown colour" for r in rows)
    assert items(paths["wanted_list"].read_text(encoding="utf-8")) == []

    # a catalogue where one part used by the pawn has another name and BrickLink id
    used = build.parts[0].part
    renamed = Catalog(
        [
            replace(p, name="Renamed brick", bricklink_id="RENAMED") if p.id == used else p
            for p in catalog.parts.values()
        ],
        catalog.colours.values(),
    )
    paths = write_exports(built_pawn, renamed)
    rows = read_csv(paths["parts"].read_text(encoding="utf-8"))[1:-1]
    assert {(r[1], r[2]) for r in rows if r[0] == used} == {("RENAMED", "Renamed brick")}
    wanted = items(paths["wanted_list"].read_text(encoding="utf-8"))
    assert "RENAMED" in {it["ITEMID"] for it in wanted}
    write_exports(built_pawn, catalog)  # leave the shared project as the other tests expect
