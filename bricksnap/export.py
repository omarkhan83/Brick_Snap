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
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bricksnap.catalog import Catalog
from bricksnap.project import Project
from bricksnap.types import Build


@dataclass(frozen=True)
class PartLine:
    part: str  # catalogue id (the LDraw file stem)
    bricklink_id: str  # "" when unknown
    name: str
    colour: int  # LDraw colour code
    colour_name: str
    bricklink_colour: int | None
    quantity: int


def parts_list(build: Build, catalog: Catalog) -> list[PartLine]:
    raise NotImplementedError


def to_csv(lines: list[PartLine]) -> str:
    raise NotImplementedError


def to_wanted_list(lines: list[PartLine]) -> str:
    raise NotImplementedError


def unlisted(lines: list[PartLine]) -> list[PartLine]:
    raise NotImplementedError


def write_exports(project: Project, catalog: Catalog | None = None) -> dict[str, Path]:
    raise NotImplementedError
