"""Build to shopping lists: a parts list and a BrickLink wanted list.

CONTRACT (tests go in tests/test_export.py)

``parts_list(build, catalog) -> list[PartLine]``
- One line per (part, colour) pair in the Build with how many there are. Sorted by part
  kind in catalogue order, then part id, then colour code, so the output is stable.
- A part or colour that is not in the catalogue still gets a line (name "unknown part" or
  "unknown colour", empty BrickLink fields) so nothing is silently dropped.

``to_csv(lines) -> str``
- Header ``Part,BrickLink ID,Name,Colour,LDraw colour,BrickLink colour ID,Quantity`` and one
  row per line, written with the ``csv`` module (names contain commas), ending in a newline.
  A last row ``Total,,,,,,<number of parts>``.

``to_wanted_list(lines) -> str``
- BrickLink's wanted-list upload format (https://www.bricklink.com/help.asp?helpID=207):
  one ``INVENTORY`` element holding one ``ITEM`` per line with ``ITEMTYPE`` P, ``ITEMID``
  (the part's BrickLink id, which is not always the LDraw id), ``COLOR`` (the BrickLink
  colour id) and ``MINQTY``. No XML declaration line. Text is escaped.
- Lines without a BrickLink part id or colour id are left out, and returned by
  ``unlisted(lines)`` so the caller can tell the user which parts to add by hand.

``write_exports(project, catalog=None) -> dict[str, Path]``
- Reads the project's saved Build and writes ``parts.csv`` and ``wanted_list.xml`` in the
  project folder (with ``bricksnap.types.write_text_atomic``). Returns
  ``{"parts": path, "wanted_list": path}``. Raises ``ProjectError`` when there is no build.

Check the element names against the help page above before relying on memory, and say in
the implementation notes what you checked.

Implementation notes
--------------------
- What was checked: on 2026-11-15 BrickLink's help page "Wanted List, Mass Upload"
  (https://www.bricklink.com/help.asp?helpID=207, marked "under construction" by BrickLink)
  was fetched and read. It says: the file starts with ``<INVENTORY>`` and ends with
  ``</INVENTORY>``; each ``<ITEM>`` must hold ``ITEMTYPE`` (P for a part) and ``ITEMID`` (the
  catalogue Item No.); ``COLOR`` is a colour ID from BrickLink's colour guide; ``MINQTY`` is
  optional, a whole number greater than 0; other optional fields are MAXPRICE, QTYFILLED,
  CONDITION, REMARKS, NOTIFY, WANTEDSHOW and WANTEDLISTID; "A wanted list in BrickLink XML
  format can not have an XML declaration"; text may not contain HTML tags or a bare
  ampersand (use ``&lt;``, ``&gt;``, ``&amp;``). Its sample uses upper-case tag names, one
  tag per line. The page links to no separate XML format reference. Nothing was uploaded:
  that needs a BrickLink account (see the task file).
- Only ITEMTYPE, ITEMID, COLOR and MINQTY are written. CONDITION (new or used) and the
  other optional fields are left for the user to choose on BrickLink.
- If two catalogue parts ever share one BrickLink id and colour, their lines are merged into
  one ITEM with the quantities added, so the upload never holds the same item twice. With
  the current catalogue every BrickLink id is used by one part only, so this does not
  happen and there is exactly one ITEM per listed line.
- The XML is made with ``xml.etree.ElementTree`` (which escapes ``&``, ``<`` and ``>``),
  indented two spaces, one tag per line, ending in a newline.
- The CSV uses ``\\n`` line endings (not the csv module's default ``\\r\\n``), so text-mode
  writing does not double them on Windows; spreadsheet programs and the csv module read
  either. An unknown BrickLink colour id is an empty cell.
- Kinds are ordered by where each kind first appears in the catalogue (brick, plate,
  tile, slope, ...). Parts that are not in the catalogue come after all known kinds.
- A known part in an unknown colour keeps its BrickLink part id; only its colour fields are
  "unknown colour" and empty. An unknown part keeps the colour it was given.
- ``parts_list`` raises a plain-language ``ValueError`` naming the part's position when a
  placement's part id is not text or its colour is not a whole number (``None``, a word,
  ``True``, ``4.9``). A whole number of another type (``4.0``, a numpy integer) is accepted
  and stored as an ``int``; a fractional colour is never rounded or cut off.
- ``write_exports`` turns every unreadable build.json into a ``ProjectError`` with a plain
  message saying to build again: bad JSON, missing fields, a bad part or colour value, or a
  file that cannot be opened (for example a folder by that name). Nothing is written then.
- A Build with no parts, or with only parts that cannot be listed, still gets a
  ``wanted_list.xml``: an ``INVENTORY`` element with no ``ITEM`` in it, because the contract
  asks for one ``ITEM`` per listed line and for both files to be written. BrickLink's help
  page says an upload must hold one or more ``ITEM`` elements, so such a file has nothing
  to upload; the caller (the ``export`` command) should say so rather than send the user to
  BrickLink. The help page also says that uploading an item already on a wanted list adds
  the quantities, so uploading the same file twice doubles the list.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path

from bricksnap.catalog import Catalog, load_catalog
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Placement, write_text_atomic

UNKNOWN_PART = "unknown part"
UNKNOWN_COLOUR = "unknown colour"

CSV_HEADER = (
    "Part",
    "BrickLink ID",
    "Name",
    "Colour",
    "LDraw colour",
    "BrickLink colour ID",
    "Quantity",
)


@dataclass(frozen=True)
class PartLine:
    part: str  # catalogue id (the LDraw file stem)
    bricklink_id: str  # "" when unknown
    name: str
    colour: int  # LDraw colour code
    colour_name: str
    bricklink_colour: int | None
    quantity: int


def _where(p: Placement) -> str:
    return f"x={p.x}, y={p.y}, z={p.z}"


def _key(p: Placement) -> tuple[str, int]:
    """The (part id, colour code) of a placement, or a plain-language ValueError."""
    if not isinstance(p.part, str):
        raise ValueError(f"The part at {_where(p)} has no proper part name ({p.part!r}).")
    colour = p.color
    if isinstance(colour, Integral) and not isinstance(colour, bool):
        return p.part, int(colour)
    if isinstance(colour, float) and colour.is_integer():
        return p.part, int(colour)
    raise ValueError(
        f"The part at {_where(p)} has colour {colour!r}, but an LDraw colour code "
        "is a whole number."
    )


def parts_list(build: Build, catalog: Catalog) -> list[PartLine]:
    counts = Counter(_key(p) for p in build.parts)
    kind_rank: dict[str, int] = {}
    for part in catalog.parts.values():
        kind_rank.setdefault(part.kind, len(kind_rank))
    unknown_rank = len(kind_rank)

    def order(key: tuple[str, int]) -> tuple[int, str, int]:
        part_id, colour = key
        part = catalog.parts.get(part_id)
        return (kind_rank[part.kind] if part else unknown_rank, part_id, colour)

    lines = []
    for part_id, colour in sorted(counts, key=order):
        part = catalog.parts.get(part_id)
        col = catalog.colours.get(colour)
        lines.append(
            PartLine(
                part=part_id,
                bricklink_id=part.bricklink_id if part else "",
                name=part.name if part else UNKNOWN_PART,
                colour=colour,
                colour_name=col.name if col else UNKNOWN_COLOUR,
                bricklink_colour=col.bricklink_id if col else None,
                quantity=counts[(part_id, colour)],
            )
        )
    return lines


def to_csv(lines: list[PartLine]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for line in lines:
        writer.writerow(
            (
                line.part,
                line.bricklink_id,
                line.name,
                line.colour_name,
                line.colour,
                "" if line.bricklink_colour is None else line.bricklink_colour,
                line.quantity,
            )
        )
    writer.writerow(("Total", "", "", "", "", "", sum(line.quantity for line in lines)))
    return out.getvalue()


def _listed(line: PartLine) -> bool:
    return bool(line.bricklink_id) and line.bricklink_colour is not None


def to_wanted_list(lines: list[PartLine]) -> str:
    wanted: dict[tuple[str, int], int] = {}  # insertion order follows the parts list
    for line in lines:
        if _listed(line):
            assert line.bricklink_colour is not None
            key = (line.bricklink_id, line.bricklink_colour)
            wanted[key] = wanted.get(key, 0) + line.quantity
    root = ET.Element("INVENTORY")
    for (item_id, colour), quantity in wanted.items():
        item = ET.SubElement(root, "ITEM")
        ET.SubElement(item, "ITEMTYPE").text = "P"
        ET.SubElement(item, "ITEMID").text = item_id
        ET.SubElement(item, "COLOR").text = str(colour)
        ET.SubElement(item, "MINQTY").text = str(quantity)
    ET.indent(root, space="  ")
    # encoding="unicode" never writes an XML declaration
    return ET.tostring(root, encoding="unicode", short_empty_elements=False) + "\n"


def unlisted(lines: list[PartLine]) -> list[PartLine]:
    return [line for line in lines if not _listed(line)]


def write_exports(project: Project, catalog: Catalog | None = None) -> dict[str, Path]:
    if catalog is None:
        catalog = load_catalog()
    try:
        lines = parts_list(project.load_build(), catalog)
    except ProjectError:
        raise
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ProjectError(
            f"The saved build in {project.path} cannot be read. Run 'bricksnap build' again."
        ) from exc
    paths = {"parts": project.path / "parts.csv", "wanted_list": project.path / "wanted_list.xml"}
    write_text_atomic(paths["parts"], to_csv(lines))
    write_text_atomic(paths["wanted_list"], to_wanted_list(lines))
    return paths
