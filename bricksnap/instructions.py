"""Build to instruction booklet: one page per building step, made from our own steps and
our own pictures. No other program is needed.

CONTRACT (tests go in tests/test_instructions.py)

``make_instructions(project, catalog=None) -> dict[str, Path]``
- Reads the project's saved Build and writes two files into the project folder, returning
  ``{"html": path, "pdf": path}``: ``instructions.html``, one self-contained page (pictures
  embedded, no scripts, nothing fetched from anywhere, all text escaped), laid out so that
  printing it from a browser gives one step per sheet; and ``instructions.pdf``, the same
  content as A4 pages. Raises ``ProjectError`` in plain words when there is no build, or
  when the build does not pass its checks (a booklet for a model that falls apart helps
  nobody; the message says to look at the check report).
- Both are written with a temporary file moved into place, like every other project file.

What the booklet holds, in this order
1. A cover: the project's name, a picture of the finished model, how many parts and how
   many steps, and the line "LEGO® is a trademark of the LEGO Group, which does not sponsor,
   authorize, or endorse this project."
2. The parts: every (part, colour) pair in the Build with a small picture of the part in
   that colour, its name, its part number and how many are needed (the same lines, in the
   same order, as ``bricksnap.export.parts_list``).
3. One section per building step, in step order:
   - the step number out of the total;
   - the parts to add in this step, each with its small picture and how many;
   - a picture of the model as it stands after the step, in which this step's parts are
     drawn in full colour and everything built before is drawn pale, so the eye goes to
     what is new. It is drawn from whichever three-quarter view shows the most of this
     step's parts (front right or back left, from above); when that view changes from the
     previous step the page says "Turn the model round";
   - when a part of this step cannot be seen in either view (it is enclosed, or under an
     overhang), a line saying which part and where it goes in words ("under the head, at
     the front").
4. A last page: the finished model from four sides.

Pictures come from ``bricksnap.render``, which gains for this (STAGE 4 additions to its
contract, tests in tests/test_render.py):
- ``render_build(..., upto_step=k, highlight_step=k)``: parts of step ``k`` as usual, parts
  of earlier steps pale (blended most of the way to the background, outlines kept);
- a second three-quarter view, "iso_back", from the back left and above, the mirror image
  of "iso" about the model's centre;
- ``render_part(part_id, colour, catalog, px_per_stud=24) -> Image``: one part alone on a
  light background, three-quarter view, in its real shape;
- ``visible_parts(build, catalog, view, upto_step=None) -> set[int]``: the indices of the
  parts of which at least a few pixels show in that view.
None of this changes any picture the renderer draws today.

Other
- Deterministic: the same Build gives byte-identical HTML, and identical PDF pages.
- Speed: a 200-step build in under 30 seconds; the HTML for it under 15 MB.
- The model's scale is the same on every step page, so the model does not jump about as
  the pages are turned.
"""

from __future__ import annotations

from pathlib import Path

from bricksnap.catalog import Catalog
from bricksnap.project import Project


def make_instructions(project: Project, catalog: Catalog | None = None) -> dict[str, Path]:
    raise NotImplementedError
