"""The scorecard: build every test model and measure the result, so that we can tell whether
a change made things better. "Measured, not guessed" (docs/VISION.md, principle 6).

CONTRACT (tests go in tests/test_bench.py)

``run_bench(models_dir, out_dir, studs=16, catalog=None, names=None) -> list[Row]``
- For every model file in ``models_dir`` (``.stl``, ``.obj``, ``.glb``, ``.gltf``, ``.3mf``,
  ``.ply``; sorted by name; only those whose stem is in ``names`` when given): make a project
  in ``out_dir/projects/<name>`` with ``bricksnap.pipeline.create_project`` (deleting an
  older one of the same name), build it with ``pipeline.rebuild`` and the rough version with
  ``pipeline.rough_build``, and save the three-row comparison picture
  (``pipeline.render_compare(project, rough=True)``) as ``out_dir/<name>.png``.
- A model that cannot be loaded or built gives a Row with ``error`` set to the plain
  message and the other fields at their defaults. One bad model never stops the run.
- Writes ``out_dir/scorecard.json`` (the rows, plus ``studs``) and ``out_dir/scorecard.md``
  (the table from ``format_table`` under a one-line heading).

``Row`` fields
- ``name``; ``ok`` (the check report's verdict); ``parts``; ``loose`` (must be 0 for a good
  build); ``pieces``; ``weak_spots``; ``part_types`` (distinct part ids); ``colours``
  (distinct colour codes);
- ``shaped``: the share, from 0 to 1, of the build's upward-facing surface that is not plain
  studs: cells whose top is a tile, a slanted face or a detail part, divided by all cells
  that have nothing above them. This is the rough measure of "looks designed";
- ``rough_parts`` and ``rough_shaped``: the same two numbers for the rough build;
- ``match_front``, ``match_right``, ``match_top``: how closely the build's outline matches
  the seed's, from 0 to 1: the area both silhouettes cover divided by the area either
  covers (``bricksnap.render.silhouette`` of the seed and of the Build in the same frame);
- ``notes``: how many notes the make-buildable and finishing passes left;
- ``seconds``: time to build (not counting pictures); ``error``: "" when all went well.

``format_table(rows) -> str``: a Markdown table, one row per model, numbers rounded sensibly
(shares and matches as percentages), with a last line of totals or averages. Readable as
plain text in a terminal.

``compare(old_rows, new_rows) -> str``: one line per model whose ``ok``, ``loose``,
``parts``, ``shaped`` or match values changed, saying what went up or down; "No change." when
nothing did. Used to compare a run against ``samples/scorecard.json``.

Speed: the eleven sample models at 16 studs in under two minutes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bricksnap.catalog import Catalog

MODEL_SUFFIXES = (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply")


@dataclass
class Row:
    name: str
    ok: bool = False
    parts: int = 0
    loose: int = 0
    pieces: int = 0
    weak_spots: int = 0
    part_types: int = 0
    colours: int = 0
    shaped: float = 0.0
    rough_parts: int = 0
    rough_shaped: float = 0.0
    match_front: float = 0.0
    match_right: float = 0.0
    match_top: float = 0.0
    notes: int = 0
    seconds: float = 0.0
    error: str = ""


def run_bench(
    models_dir: str | Path,
    out_dir: str | Path,
    studs: int = 16,
    catalog: Catalog | None = None,
    names: list[str] | None = None,
) -> list[Row]:
    raise NotImplementedError


def format_table(rows: list[Row]) -> str:
    raise NotImplementedError


def compare(old_rows: list[Row], new_rows: list[Row]) -> str:
    raise NotImplementedError
