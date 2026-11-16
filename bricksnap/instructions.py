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

Implementation notes
--------------------
- Besides ``make_instructions``: ``plan_steps(build, catalog) -> list[StepPlan]`` (per step:
  its number, the Build's own step value, its parts, their parts-list lines, the view, whether
  to turn, the hidden parts and their sentences, the parts seen only from the other side and
  their sentences, and the new parts the hidden ones stand on), ``where_words(build,
  catalog, index, view="iso")`` (the sentence for one part, as it reads on a page drawn from
  ``view``) and ``page_images(project, catalog)`` (every PDF page as a picture, to look
  at). Nothing else is needed by a front end.
- The checks are run again on the loaded Build (``bricksnap.checks.check``); the report
  saved in build.json is not trusted, since it may be older than the parts. An unreadable
  build.json is a ``ProjectError`` saying to build again. Nothing is written on an error.
- Pages: the cover; the parts, 21 a page in three columns; one page per step; the finished
  model from the front, right, back and left. Steps are numbered 1 to N in the order of the
  Build's own step values. The PDF pages are pictures, A4 at 150 dots per inch (1240 x
  1754 pixels); the HTML has the same pages in the same order (``<section class="page
  ...">``) with real text.
- Step pictures are of the Build moved into the smallest grid that holds it, at one scale
  for the whole booklet and in the same place on every page: the largest scale at which
  both three-quarter views fit the picture area (the page's width, and its height less the
  header and the notes). The step pictures of a booklet together may take no more than
  ``STEP_BUDGET`` pixels (200 pictures of 860 x 780); with more steps than that allows at
  full size the picture area is made smaller, same proportions, which keeps any 200-step
  booklet within the time and size limits however few parts it has a step. The same picture
  goes into the PDF and, as a PNG of 256 colours or fewer, into the HTML. The new parts get
  a yellow line round them (``HALO``, from ``render.render_build_map``) as well as their
  full colour: pale white and full white look alike, a yellow line does not. A faint stud
  grid is drawn on the ground under the model so that gaps between parts standing apart
  (the cat's four feet) can be counted; step 1 says the squares are not a part.
- Seen. A part counts as seen in a view when, drawn at 8 pixels a stud after its step,
  at least 4 of its pixels show and at least a quarter (``SEEN_SHARE``) of what its box
  would show with nothing in front of it. The second rule is mine: by pixels alone, a plate
  of which only an edge shows in a stack (the cat's back, steps 20 and 21) counts as seen,
  and the page then gives no help with it although nobody could tell where it goes.
  ``render.visible_parts`` itself keeps the contract's plain "a few pixels".
- The view (``plan_steps``). The view kept is the one that sees more of the step's parts;
  when both see as many, the view of the step before is kept unless the other shows more
  than ``TURN_AREA`` (twice) the pixels of them, so the model is not turned for nothing.
  The first step starts from the front unless the back wins by the same rule. "Turn the
  model round" is printed when the view differs from the step before, and every step page
  says which side the model is seen from.
- Hidden parts (seen in neither view) each get a sentence from the Build's geometry alone:
  which side of the whole model (thirds of its width and depth); what it stands on (the
  part under most of it, and the step it came in), or "at the bottom", or, when it stands
  on nothing, how high in the model (low down, halfway up, near the top); and what goes on
  top of it, with "Put it in first." when that comes in the same step, or else a part
  beside it. A colour is named only where it tells parts apart. Sides are named as the
  reader sees them in the page's picture: on a page seen from the front, front, back, left
  and right; on a page seen from the back (the model turned round, so its own left is on
  the right of the picture), left and right swap and the model's back is "the side nearest
  you", its front "the far side" ("at the near right", "at the far left"). Sentences are
  listed bottom first; identical ones are printed once with "2x". Beside them a close-up
  shows the model before the step with the hidden parts added, outlined, at the page's
  scale, cropped to about three studs round them (when at least one of them is seen in
  it). A hidden part may stand on a new part of the same step that is not hidden (the
  duck's plate on a slope): such parts, and what they stand on in the step, are drawn too,
  in full colour without the outline, so nothing hangs in the air, and the close-up is
  headed "Build this first" instead of "Put these in first".
- Parts seen from the other side only. The contract asks for words only for parts seen in
  neither view, but a new part that the page's view does not show and the other view does
  (a step whose parts split between the two sides) cannot be built from the page either.
  Such a part gets the same sentence, among the hidden ones, and a second close-up, headed
  with the other view's name ("Seen from the back"), of the model after the step drawn
  from that side with those parts outlined.
- Room for those words is kept at the foot of every step page only when some step has such
  parts: as much as the longest notes need with the text shrunk from 26 down to 18 pixels
  to fit 360, at least 260 for one close-up or 440 for two (stacked at the right), and
  never more than 640. The model picture is smaller on every page then, to keep one scale:
  one long step decides it for the whole booklet (the duck's step 41, ten sentences, takes
  it from 32 to 25 pixels a stud). Notes longer than 640 pixels at the smallest size would
  run off the PDF page; no model so far comes near.
- Part pictures are drawn the way ``render.render_part`` draws them (the part alone at rot
  0, "iso", in a grid exactly its size), but through ``render.render_build_map`` so that
  the background is found from the part map and no part colour is ever mistaken for it;
  then cropped to the part, on the colour of the box they sit in (24 pixels a stud on the
  parts pages; in a step's parts box as large as fits, up to 28, with the part's short name
  under its count, since a 1 x 6 and a 1 x 8 brick look alike when small).
- Short names (step boxes and sentences): the name without the makers' extras ("Tile 1 x 2
  with Groove" is "Tile 1 x 2"), but only where no other part in the parts table goes by
  the shorter name: "Brick 1 x 1 with Stud on 1 Side" stays whole, since "Brick 1 x 1" is
  another part, and the jumper is "Plate 1 x 2 with 1 Centre Stud". Every part's short name
  is different from every other's. Names on the PDF pages are never cut short: smaller
  letters, then a third line.
- Text on the PDF pages is drawn with the font that comes with Pillow, which has little
  beyond plain English letters; a text with others (a project named "Kätzchen") is drawn
  with the first of ``FALLBACK_FONTS`` found on the computer that has them all. Without
  one (Chinese letters, on a computer with no Chinese font) they still show as boxes; the
  HTML is always right. A word too long for its line is broken; the cover's title shrinks
  to fit two lines, down to 48 pixels, and ends in "..." past three; the footer shortens
  the name to fit.
- HTML: one file, a little CSS, no scripts, pictures as ``data:`` PNGs, every text through
  ``html.escape``. For printing, ``@page`` is A4 and each section one sheet: the model
  picture's printed height is one value for the whole booklet, worked out from the tallest
  parts box and notes (so the scale stays the same), and a step section is a column of
  fixed height, so if that estimate is ever short one picture shrinks instead of the page
  spilling onto a second sheet. Checked by printing from headless Chromium: the cat gives
  37 sheets for 37 sections, the pawn 61 for 61, the duck 92 for 92.
- The PDF is written by a small writer here, not Pillow's: Pillow puts the time and the
  temporary file's name into the file and stores pages as JPEG. Each page is one lossless
  image (its PNG data, which PDF reads as compressed with a PNG predictor), so the file is
  byte-identical for the same Build. Its title is the project's name. The text in it is
  part of the pictures; the HTML has the real text. The font is the one that comes with
  Pillow: bold is drawn with a thin outline, and its missing "®" is drawn by hand.
- Speed. Drawing runs in one thread; compressing the PDF pages and the HTML pictures runs
  in ``WORKERS`` (3) threads, in page order, so the files are identical either way.
  Drawing in threads too was tried and was twice as slow (it holds Python's lock most of
  the time). Each step's two measuring pictures come from one scene
  (``render.part_pixels_views``), and the HTML pictures are reduced to 256 colours with
  Pillow's quick octree method (a quarter of the time of median cut; colours move by less
  than 1 in 255 on average). Measured on a 16-core machine: the cat (124 parts, 33 steps)
  2.6 s, HTML 1.1 MB, PDF 2.8 MB; the pawn (294 parts, 58 steps) 4 s, 2.2 MB, 5.2 MB; the
  duck at 16 studs (622 parts, 88 steps) 5.6 s, 3.1 MB, 9.4 MB. The tests' two 200-step
  builds: 1,600 parts in 16.7 s (HTML 10.7 MB, PDF 25.5 MB) and 600 parts, 3 a step, in
  15.5 s (10.1 MB, 22.9 MB); held to one core, 23.4 s and 22.4 s.
"""

from __future__ import annotations

import base64
import html
import io
import math
import os
import re
import struct
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from bricksnap import render as R
from bricksnap.catalog import Catalog, load_catalog
from bricksnap.export import PartLine, parts_list
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Placement, write_text_atomic

DISCLAIMER = (
    "LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or "
    "endorse this project."
)
TURN_TEXT = "Turn the model round"
GRID_NOTE = "The squares on the ground are not a part: they help you count studs."
SIDE_WORDS = {"iso": "Seen from the front", "iso_back": "Seen from the back"}
FIRST_TEXT = "Put these in first"  # the close-up of hidden parts
FIRST_WITH_SUPPORT = "Build this first"  # ... when it also holds new parts they stand on
OTHER_VIEW = {"iso": "iso_back", "iso_back": "iso"}
FOUR_SIDES = (
    ("front", "From the front"),
    ("right", "From the right"),
    ("back", "From the back"),
    ("left", "From the left"),
)

DPI = 150
PAGE_W, PAGE_H = 1240, 1754  # A4, 210 x 297 mm, at 150 dots per inch
MARGIN = 70
MIN_PIXELS = 4  # pixels of a part that must show (at 8 a stud) for it to count as seen
SEEN_SHARE = 0.25  # ... and the share of what it would show if nothing were in front of it
TURN_AREA = 2.0
HALO = (255, 190, 0)
GROUND = (222, 222, 218)  # the faint stud grid on the ground
WHITE = (255, 255, 255)
INK = (25, 25, 25)
SOFT_INK = (95, 95, 95)
BOX = (220, 235, 250)  # the parts box, light blue as in printed instructions
TURN_BOX = (255, 233, 168)
PARTS_PER_PAGE = 21
PARTS_COLUMNS = 3
MAX_PX_PER_STUD = 64
HTML_BOX_PX = 14  # pixels a stud of the part pictures in a step's parts box in the HTML
WORKERS = 3  # threads compressing pages and pictures (drawing stays in one thread)
STEP_BUDGET = 200 * 860 * 780  # pixels of all the step pictures of a booklet together
HTML_PICTURE = (860, 780)  # the most the cover's picture may take in the HTML


# ---- the plan: which parts, which view, what is hidden --------------------------------------


@dataclass
class StepPlan:
    """One step page: what goes in it and how it is shown."""

    number: int  # 1 .. number of steps
    step: int  # the Build's own step value
    parts: list[int]  # indices into build.parts
    lines: list[PartLine]  # the parts to add, as in the parts list
    view: str  # "iso" or "iso_back"
    turn: bool  # the view differs from the step before
    hidden: list[int] = field(default_factory=list)  # parts seen in neither view
    words: list[str] = field(default_factory=list)  # one sentence per hidden part
    # parts not seen in this page's view but seen from the other side, and their sentences
    behind: list[int] = field(default_factory=list)
    behind_words: list[str] = field(default_factory=list)
    # new parts of this step (not hidden) that hidden parts stand on, directly or not
    supports: list[int] = field(default_factory=list)


def plan_steps(build: Build, catalog: Catalog) -> list[StepPlan]:
    """The step pages of a Build, in order (see the implementation notes)."""
    work = _tight(build, catalog)
    geo = _Geometry(work, catalog)
    plans: list[StepPlan] = []
    prev = "iso"

    def measure(value: int) -> dict[str, dict[int, int]]:
        return R.part_pixels_views(work, catalog, R.ISO_VIEWS, upto_step=value)

    def bottom_first(items: list[int]) -> list[int]:  # the order to build them in
        return sorted(items, key=lambda i: (work.parts[i].z, i))

    for (number, value), pixels in zip(
        enumerate(geo.values, start=1), map(measure, geo.values), strict=True
    ):
        idx = [i for i, p in enumerate(work.parts) if p.step == value]
        seen: dict[str, set[int]] = {}
        area: dict[str, int] = {}
        for view in R.ISO_VIEWS:
            pix = pixels[view]
            seen[view] = {i for i in idx if _seen(work, catalog, view, i, pix.get(i, 0))}
            area[view] = sum(pix.get(i, 0) for i in idx)
        other = OTHER_VIEW[prev]
        view = prev
        if len(seen[other]) > len(seen[prev]) or (
            len(seen[other]) == len(seen[prev]) and area[other] > TURN_AREA * area[prev]
        ):
            view = other
        hidden = bottom_first(
            [i for i in idx if i not in seen["iso"] and i not in seen["iso_back"]]
        )
        behind = bottom_first(
            [i for i in idx if i not in seen[view] and i in seen[OTHER_VIEW[view]]]
        )
        plans.append(
            StepPlan(
                number=number,
                step=value,
                parts=idx,
                lines=parts_list(Build(work.shape, [work.parts[i] for i in idx]), catalog),
                view=view,
                turn=number > 1 and view != prev,
                hidden=hidden,
                words=[geo.where(i, view) for i in hidden],
                behind=behind,
                behind_words=[geo.where(i, view) for i in behind],
                supports=geo.supports(hidden),
            )
        )
        prev = view
    return plans


def _plan_notes(plan: StepPlan, build: Build) -> list[str]:
    """The sentences printed on a step page: those of the hidden parts and of the parts
    seen only from the other side, bottom first."""
    pairs = list(zip(plan.hidden, plan.words, strict=True))
    pairs += list(zip(plan.behind, plan.behind_words, strict=True))
    pairs.sort(key=lambda pair: (build.parts[pair[0]].z, pair[0]))
    return [sentence for _, sentence in pairs]


def _seen(build: Build, catalog: Catalog, view: str, i: int, pixels: int) -> bool:
    """Whether enough of part ``i`` shows in a picture at 8 pixels a stud to see where it
    goes: ``MIN_PIXELS``, and ``SEEN_SHARE`` of what its box would show with nothing in
    front of it (a plate showing only an edge in a stack does not count)."""
    w, d, h = catalog.footprint(build.parts[i])
    t = np.abs(np.asarray(R.view_frame((1, 1, 1), view, px_per_stud=8, labels=False).camera[2]))
    # at 8 pixels a stud one pixel is one millimetre: the faces' areas, foreshortened
    full = t[2] * w * d * 64.0 + (t[1] * w + t[0] * d) * h * 8.0 * 3.2
    return pixels >= max(MIN_PIXELS, SEEN_SHARE * full)


def _in_order(fn, items, window: int = 16) -> Iterator:
    """``map(fn, items)`` worked out by a few threads, in order, at most ``window`` ahead.
    Used for compressing (zlib works outside Python's lock); the results, and so the files,
    are exactly those of working one at a time."""
    workers = max(1, min(WORKERS, os.cpu_count() or 1))
    if workers == 1:
        yield from map(fn, items)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending: deque = deque()
        for item in items:
            pending.append(pool.submit(fn, item))
            if len(pending) >= window:
                yield pending.popleft().result()
        while pending:
            yield pending.popleft().result()


def where_words(build: Build, catalog: Catalog, index: int, view: str = "iso") -> str:
    """One sentence saying where part ``index`` of the Build goes, in plain words, with
    its sides named as they are seen in ``view`` (the view of the page it is printed on)."""
    return _Geometry(build, catalog).where(index, view)


def _tight(build: Build, catalog: Catalog) -> Build:
    """The Build moved into the smallest grid that holds it (standing on z = 0)."""
    known = [p for p in build.parts if p.part in catalog.parts]
    if not known:
        return Build(build.shape, list(build.parts))
    lo = [min(p.x for p in known), min(p.y for p in known)]
    hi = [0, 0, 0]
    for p in known:
        w, d, h = catalog.footprint(p)
        hi = [max(hi[0], p.x + w), max(hi[1], p.y + d), max(hi[2], p.z + h)]
    parts = [
        Placement(p.part, p.color, p.x - lo[0], p.y - lo[1], p.z, p.rot, p.step)
        for p in build.parts
    ]
    return Build((hi[0] - lo[0], hi[1] - lo[1], max(hi[2], 1)), parts)


def _part_words(catalog: Catalog, p: Placement, colour: bool = True) -> str:
    """'yellow plate 1 x 1': the name (and colour) as a reader would say them."""
    name = _short_name(catalog, p.part).lower() if p.part in catalog.parts else f"part {p.part}"
    c = catalog.colours.get(p.color)
    return f"{c.name.lower()} {name}" if colour and c else name


_SHORT: dict[int, tuple[Catalog, dict[str, str]]] = {}


def _short_name(catalog: Catalog, part_id: str) -> str:
    """The part's name without the makers' extras ("Tile 1 x 2 with Groove" -> "Tile 1 x 2"),
    as long as no other part in the parts table goes by the shorter name: "Brick 1 x 1 with
    Stud on 1 Side" stays as it is, since "Brick 1 x 1" is another part."""
    hit = _SHORT.get(id(catalog))
    if hit is None or hit[0] is not catalog:
        hit = (catalog, _short_names(catalog))
        _SHORT[id(catalog)] = hit
    part = catalog.parts.get(part_id)
    return hit[1].get(part_id, part.name if part else part_id)


def _short_names(catalog: Catalog) -> dict[str, str]:
    """Every part's short name. Each part tries, shortest first: its name cut at " with ",
    its name without a bracket, a trailing ", ..." or " with Groove", and its full name; it
    keeps the first that is no other part's name and no other part's choice."""
    tries: dict[str, list[str]] = {}
    for pid, part in catalog.parts.items():
        trimmed = re.sub(r" \([^)]*\)", "", part.name).split(", ")[0]
        trimmed = trimmed.replace(" with Groove", "")
        tries[pid] = list(dict.fromkeys([trimmed.split(" with ")[0], trimmed, part.name]))
    full = {part.name: pid for pid, part in catalog.parts.items()}
    pick = dict.fromkeys(tries, 0)
    while True:
        chosen = {pid: tries[pid][k] for pid, k in pick.items()}
        users: dict[str, list[str]] = {}
        for pid, name in chosen.items():
            users.setdefault(name, []).append(pid)
        clash = [
            pid
            for pid, name in chosen.items()
            if len(users[name]) > 1 or full.get(name, pid) != pid
        ]
        clash = [pid for pid in clash if pick[pid] < len(tries[pid]) - 1]
        if not clash:
            return chosen
        for pid in clash:
            pick[pid] += 1


class _Geometry:
    """What touches what in a Build, for saying where a part goes."""

    def __init__(self, build: Build, catalog: Catalog) -> None:
        from bricksnap.connect import occupancy

        self.build = build
        self.catalog = catalog
        self.occ = occupancy(build, catalog)[0]
        self.values = sorted({p.step for p in build.parts})
        self.number = {v: n for n, v in enumerate(self.values, start=1)}
        cells = np.argwhere(self.occ >= 0)
        if len(cells):
            self.lo = cells.min(axis=0)
            self.hi = cells.max(axis=0) + 1
        else:
            self.lo, self.hi = np.zeros(3, int), np.ones(3, int)

    def _name(self, j: int, i: int) -> str:
        """'the brick 2 x 3 from step 14': part ``j`` as seen from the sentence about part
        ``i`` (its colour only when it differs from part ``i``'s)."""
        p, q = self.build.parts[i], self.build.parts[j]
        words = _part_words(self.catalog, q, colour=q.color != p.color)
        if q.step != p.step:
            return f"the {words} from step {self.number[q.step]}"
        if (q.part, q.color) == (p.part, p.color):
            return f"another {words} of this step"
        return f"the {words} of this step"

    def _most(self, values: np.ndarray, allowed) -> int | None:
        """The part covering most of ``values`` (lowest index on a tie), among ``allowed``."""
        v = values[values >= 0]
        v = v[[allowed(int(j)) for j in v]] if len(v) else v
        if not len(v):
            return None
        counts = np.bincount(v)
        return int(np.argmax(counts))

    def supports(self, hidden: list[int]) -> list[int]:
        """The parts of the same step, not themselves in ``hidden``, that the ``hidden``
        parts stand on, directly or through each other: they go in before them."""
        b, cat, occ = self.build, self.catalog, self.occ
        done, out, todo = set(hidden), set(), list(hidden)
        while todo:
            p = b.parts[todo.pop()]
            if p.z == 0 or p.part not in cat.parts:
                continue
            xs, ys, _ = cat.cells(p)
            under = occ[xs, ys, p.z - 1].ravel()
            for j in sorted(set(under[under >= 0].tolist())):
                if b.parts[j].step == p.step and j not in done:
                    done.add(j)
                    out.add(j)
                    todo.append(j)
        return sorted(out)

    def where(self, i: int, view: str = "iso") -> str:
        b, cat, occ = self.build, self.catalog, self.occ
        p = b.parts[i]
        w, d, h = cat.footprint(p)
        nz = occ.shape[2]
        step = p.step

        def earlier_or_now(j: int) -> bool:
            return j != i and b.parts[j].step <= step

        # which side of the whole model, as the reader sees it in the page's picture: from
        # the front (the model's front nearest the reader) or from the back (turned round,
        # so its left is on the right and its back is nearest)
        fx = (p.x + w / 2 - self.lo[0]) / max(1, self.hi[0] - self.lo[0])
        fy = (p.y + d / 2 - self.lo[1]) / max(1, self.hi[1] - self.lo[1])
        across = "left" if fx < 1 / 3 else "right" if fx > 2 / 3 else ""
        depth = "front" if fy < 1 / 3 else "back" if fy > 2 / 3 else ""
        if view == "iso_back":
            across = {"left": "right", "right": "left"}.get(across, "")
            depth = {"front": "far", "back": "near"}.get(depth, "")
        if across and depth:
            side = f"at the {depth} {across}"
        elif depth in ("near", "far"):
            side = "on the side nearest you" if depth == "near" else "at the far side"
        elif depth:
            side = f"at the {depth}"
        elif across:
            side = f"on the {across} side"
        else:
            side = "in the middle"
        bits = [side]
        xs, ys, _ = cat.cells(p)
        below = self._most(occ[xs, ys, p.z - 1].ravel(), earlier_or_now) if p.z > 0 else None
        if below is not None:  # what it stands on says how high it is
            bits.append(f"on {self._name(below, i)}")
        elif p.z == 0:
            bits.append("at the bottom")
        else:  # how high in the model as it stands after this step
            top = max(
                q.z + cat.footprint(q)[2] for q in b.parts if q.step <= step and q.part in cat.parts
            )
            f = p.z / max(1, top)
            bits.append("low down" if f < 1 / 3 else "halfway up" if f < 2 / 3 else "near the top")
        above = None
        if p.z + h < nz:
            above = self._most(occ[xs, ys, p.z + h].ravel(), earlier_or_now)
        if above is not None:
            bits.append(f"under {self._name(above, i)}")
        else:
            beside = self._beside(p, w, d, h, earlier_or_now)
            if beside is not None:
                bits.append(f"next to {self._name(beside, i)}")
        same_kind = [q for q in b.parts if q.step == step and q.part == p.part]
        colour = any(q.color != p.color for q in same_kind)
        sentence = f"The {_part_words(cat, p, colour=colour)} goes {', '.join(bits)}."
        if above is not None and b.parts[above].step == step:
            sentence += " Put it in first."
        return sentence

    def _beside(self, p: Placement, w: int, d: int, h: int, allowed) -> int | None:
        occ = self.occ
        nx, ny, _ = occ.shape
        zs = slice(p.z, p.z + h)
        ring = []
        if p.x > 0:
            ring.append(occ[p.x - 1, p.y : p.y + d, zs].ravel())
        if p.x + w < nx:
            ring.append(occ[p.x + w, p.y : p.y + d, zs].ravel())
        if p.y > 0:
            ring.append(occ[p.x : p.x + w, p.y - 1, zs].ravel())
        if p.y + d < ny:
            ring.append(occ[p.x : p.x + w, p.y + d, zs].ravel())
        if not ring:
            return None
        return self._most(np.concatenate(ring), allowed)


# ---- pictures --------------------------------------------------------------------------------


def _fit_scale(shape: tuple[int, int, int], box: tuple[int, int], top: int) -> int:
    """The largest pixels-a-stud at which the three-quarter view of the grid fits the box."""
    for s in range(top, 2, -1):
        f = R.view_frame(shape, "iso", px_per_stud=s, labels=False)
        if f.width <= box[0] and f.height <= box[1]:
            return s
    return 3


def _picture(
    build: Build,
    catalog: Catalog,
    view: str,
    s: int,
    *,
    upto: int | None = None,
    new: list[int] | None = None,
    background=WHITE,
    ground: bool = False,
) -> Image.Image:
    """A picture of the Build with its background in ``background``; with ``new``, those
    parts are this step's: earlier ones drawn pale and a yellow line round the new ones.
    With ``ground`` a faint stud grid is drawn on the ground under the model, so that the
    gap between parts standing apart can be counted."""
    return _drawn(
        build, catalog, view, s, upto=upto, new=new, background=background, ground=ground
    )[0]


def _drawn(
    build: Build,
    catalog: Catalog,
    view: str,
    s: int,
    *,
    upto: int | None = None,
    new: list[int] | None = None,
    background=WHITE,
    ground: bool = False,
) -> tuple[Image.Image, np.ndarray]:
    """``_picture``, and where in it the ``new`` parts are (bool, H x W)."""
    highlight = None
    if new:
        highlight = build.parts[new[0]].step
    im, owner = R.render_build_map(
        build, catalog, view, px_per_stud=s, labels=False, upto_step=upto, highlight_step=highlight
    )
    a = np.asarray(im).copy()
    mine = np.zeros(owner.shape, dtype=bool)
    if new:
        mine = np.isin(owner, np.asarray(new, dtype=np.int64))
        width = max(2, round(s / 9))
        ring = ndimage.binary_dilation(mine, iterations=width) & ~mine
        a[ring] = HALO
        owner = np.where(ring, 0, owner)
    a[owner < 0] = background
    if ground:
        lines = _ground_grid(build.shape, view, s, im.size)
        a[(owner < 0) & lines] = GROUND
    return Image.fromarray(a, mode="RGB"), mine


def _ground_grid(
    shape: tuple[int, int, int], view: str, s: int, size: tuple[int, int]
) -> np.ndarray:
    """(H, W) bool: the lines between studs on the ground under the grid, in that view."""
    frame = R.view_frame(shape, view, px_per_stud=s, labels=False)
    nx, ny, _ = shape
    layer = Image.new("1", size, 0)
    draw = ImageDraw.Draw(layer)
    width = 1 if s < 30 else 2
    for x in range(nx + 1):
        (c0, r0, _), (c1, r1, _) = frame.project([[x, 0, 0], [x, ny, 0]])
        draw.line([(c0, r0), (c1, r1)], fill=1, width=width)
    for y in range(ny + 1):
        (c0, r0, _), (c1, r1, _) = frame.project([[0, y, 0], [nx, y, 0]])
        draw.line([(c0, r0), (c1, r1)], fill=1, width=width)
    return np.asarray(layer, dtype=bool)


def _close_up(im: Image.Image, mine: np.ndarray, s: int, box: tuple[int, int]) -> Image.Image:
    """The part of a picture around the marked parts, with about three studs round them,
    shrunk to fit the box: a close-up at the page's own scale or smaller, never larger."""
    rows, cols = np.nonzero(mine)
    if not len(rows):
        return _fit(im, box)
    m = 3 * s
    r0, r1 = max(0, int(rows.min()) - m), min(im.height, int(rows.max()) + 1 + m)
    c0, c1 = max(0, int(cols.min()) - m), min(im.width, int(cols.max()) + 1 + m)
    # widen the crop to the box's proportions, so the close-up fills it
    want = box[0] / box[1]
    if (c1 - c0) / (r1 - r0) < want:
        extra = round((r1 - r0) * want) - (c1 - c0)
        c0, c1 = max(0, c0 - extra // 2), min(im.width, c1 + extra - extra // 2)
    else:
        extra = round((c1 - c0) / want) - (r1 - r0)
        r0, r1 = max(0, r0 - extra // 2), min(im.height, r1 + extra - extra // 2)
    return _fit(im.crop((c0, r0, c1, r1)), box)


def _crop(im: Image.Image, background, pad: int = 4) -> Image.Image:
    a = np.asarray(im)
    ink = (a != np.asarray(background, dtype=a.dtype)).any(axis=2)
    if not ink.any():
        return im
    rows, cols = np.nonzero(ink)
    return im.crop(
        (
            max(0, int(cols.min()) - pad),
            max(0, int(rows.min()) - pad),
            min(im.width, int(cols.max()) + 1 + pad),
            min(im.height, int(rows.max()) + 1 + pad),
        )
    )


class _PartPictures:
    """Cropped pictures of single parts, made once each."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.cache: dict[tuple[str, int, int, tuple[int, int, int]], Image.Image] = {}
        self.tags: dict[tuple[str, int, int, str], str] = {}

    def img(self, part: str, colour: int, s: int, background, alt: str) -> str:
        """The HTML picture of a part, encoded once and reused on every page."""
        key = (part, colour, s, alt)
        if key not in self.tags:
            self.tags[key] = _img("part", self.get(part, colour, s, background), alt)
        return self.tags[key]

    def get(self, part: str, colour: int, s: int, background) -> Image.Image:
        key = (part, colour, s, tuple(background))
        if key not in self.cache:
            if part not in self.catalog.parts:
                im = Image.new("RGB", (2 * s, 2 * s), tuple(background))
            else:
                b = Build(
                    (
                        self.catalog.parts[part].sx,
                        self.catalog.parts[part].sz,
                        self.catalog.parts[part].h,
                    ),
                    [Placement(part, colour, 0, 0, 0, 0, 1)],
                )
                im = _crop(_picture(b, self.catalog, "iso", s, background=background), background)
            self.cache[key] = im
        return self.cache[key]


def _fit(im: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Shrink (never enlarge) to fit the box, keeping the proportions."""
    k = min(box[0] / im.width, box[1] / im.height, 1.0)
    if k >= 1.0:
        return im
    return im.resize(
        (max(1, round(im.width * k)), max(1, round(im.height * k))), Image.Resampling.LANCZOS
    )


# ---- the booklet's content -------------------------------------------------------------------


@dataclass
class _Figure:
    """A close-up beside the words of a step page."""

    cls: str  # "first" (hidden parts put in first) or "behind" (seen from the other side)
    caption: str
    picture: Image.Image


@dataclass
class _Step:
    plan: StepPlan
    total: int
    picture: Image.Image  # the model after the step (PDF and HTML)
    notes: list[str]  # the sentences for the parts the picture does not show
    figures: list[_Figure]  # close-ups beside them (none, one or two)


@dataclass
class _Booklet:
    name: str
    build: Build
    lines: list[PartLine]
    cover: Image.Image
    cover_small: Image.Image
    sides: list[tuple[str, Image.Image]]
    plans: list[StepPlan]
    notes_height: int
    model_box: tuple[int, int]


def _load(project: Project, catalog: Catalog) -> Build:
    from bricksnap.checks import check

    try:
        build = project.load_build()
    except ProjectError:
        raise
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ProjectError(
            f"The saved build in {project.path} cannot be read. Run 'bricksnap build' again."
        ) from exc
    report = check(build, catalog)
    if not report.ok:
        raise ProjectError(
            f"The build of {project.name} does not pass its checks, so no instructions were "
            f"made: a model that does not hold together cannot be built from a booklet. Look "
            f"at the check report ('bricksnap check {project.path}') and fix the model first."
        )
    return build


NOTES_MAX = 360  # pixels at the foot of a step page for the words about hidden parts
NOTE_SIZES = (26, 23, 20, 18)


def _note_lines(words: list[str]) -> list[str]:
    """The sentences to print: identical ones once, with how many ("2x ...")."""
    out: list[str] = []
    for sentence in dict.fromkeys(words):
        n = words.count(sentence)
        out.append(f"{n}x  {sentence}" if n > 1 else sentence)
    return out


def _fit_notes(words: list[str], width: int, room: int) -> tuple[int, list[list[str]], int]:
    """The largest text size at which the notes fit ``room``: (size, wrapped lines per
    sentence, height). At the smallest size the height may be more than ``room``."""
    for size in NOTE_SIZES:
        wrapped = [_wrap(s, _font(size), width) for s in _note_lines(words)]
        step = round(size * 1.3)
        height = 40 + sum(len(w) * step + 6 for w in wrapped)
        if height <= room or size == NOTE_SIZES[-1]:
            return size, wrapped, height
    raise AssertionError("unreachable")


def _figure_count(plan: StepPlan) -> int:
    """How many close-ups a step page may have: one for hidden parts, one for parts seen
    only from the other side."""
    return (1 if plan.hidden else 0) + (1 if plan.behind else 0)


def _notes_height(plans: list[StepPlan], build: Build) -> int:
    """Room at the foot of every step page for the words about parts the picture does not
    show, and their close-ups: none when no step has such parts, else what the longest
    notes need (shrunk to fit ``NOTES_MAX`` when they can be, never more than 640 pixels),
    and at least 260 pixels for one close-up or 440 for two."""
    need = 0
    for plan in plans:
        notes = _plan_notes(plan, build)
        if notes:
            _, _, height = _fit_notes(notes, _NOTES_WIDTH, NOTES_MAX)
            need = max(need, 440 if _figure_count(plan) > 1 else 260, height)
    return min(need, 640)


def _model_box(room: tuple[int, int], steps: int) -> tuple[int, int]:
    """The step pictures' area: ``room``, made smaller (same proportions) when the steps'
    pictures together would be more than ``STEP_BUDGET`` pixels, which keeps every
    booklet within the time and size limits whatever its number of parts."""
    most = STEP_BUDGET / max(1, steps)
    if room[0] * room[1] <= most:
        return room
    k = math.sqrt(most / (room[0] * room[1]))
    return int(room[0] * k), int(room[1] * k)


def _booklet(project: Project, catalog: Catalog) -> _Booklet:
    build = _load(project, catalog)
    work = _tight(build, catalog)
    plans = plan_steps(build, catalog)
    notes = _notes_height(plans, work)
    model_top = _MODEL_TOP
    room = (PAGE_W - 2 * MARGIN, PAGE_H - _FOOTER - model_top - notes - 10)
    model_box = _model_box(room, len(plans))
    cover_s = _fit_scale(work.shape, (PAGE_W - 2 * MARGIN, 1050), MAX_PX_PER_STUD)
    side_s = min(
        _fit_scale_straight(work.shape, v, ((PAGE_W - 2 * MARGIN - 40) // 2, 640))
        for v, _ in FOUR_SIDES
    )
    sides = [(caption, _picture(work, catalog, v, side_s)) for v, caption in FOUR_SIDES]
    cover = _picture(work, catalog, "iso", cover_s)
    return _Booklet(
        name=project.name,
        build=work,
        lines=parts_list(build, catalog),
        cover=cover,
        cover_small=_fit(cover, HTML_PICTURE),
        sides=sides,
        plans=plans,
        notes_height=notes,
        model_box=model_box,
    )


def _fit_scale_straight(shape, view: str, box: tuple[int, int]) -> int:
    for s in range(MAX_PX_PER_STUD, 2, -1):
        f = R.view_frame(shape, view, px_per_stud=s, labels=False)
        if f.width <= box[0] and f.height <= box[1]:
            return s
    return 3


_FIGURE_W = 370  # the column of close-ups at the right of a step page's notes


def _figure_slots(notes_height: int, n: int) -> list[tuple[int, int]]:
    """(top, height) of each of ``n`` close-ups stacked in the notes, from its top."""
    if n == 0:
        return []
    gap = 12
    h = (notes_height - 10 - gap * (n - 1)) // n
    return [(k * (h + gap), h) for k in range(n)]


def _steps(book: _Booklet, catalog: Catalog) -> Iterator[_Step]:
    work = book.build
    s = _fit_scale(work.shape, book.model_box, MAX_PX_PER_STUD)
    total = len(book.plans)

    def one(plan: StepPlan) -> _Step:
        picture = _picture(work, catalog, plan.view, s, upto=plan.step, new=plan.parts, ground=True)
        slots = _figure_slots(book.notes_height, _figure_count(plan))
        boxes = [(_FIGURE_W - 20, max(80, h - 60)) for _, h in slots]
        figures: list[_Figure] = []
        if plan.hidden:
            # the model before the step, with the hidden parts and the new parts they
            # stand on (so that nothing hangs in the air), the hidden ones marked
            before = [i for i, p in enumerate(work.parts) if p.step < plan.step]
            keep = before + plan.supports + plan.hidden
            sub = Build(work.shape, [work.parts[i] for i in keep])
            new = list(range(len(keep) - len(plan.hidden), len(keep)))
            counts = R.part_pixels(sub, catalog, plan.view)
            if any(_seen(sub, catalog, plan.view, i, counts.get(i, 0)) for i in new):
                caption = FIRST_WITH_SUPPORT if plan.supports else FIRST_TEXT
                im, mine = _drawn(sub, catalog, plan.view, s, new=new, ground=True)
                figures.append(_Figure("first", caption, _close_up(im, mine, s, boxes[0])))
        if plan.behind:
            other = OTHER_VIEW[plan.view]
            im, mine = _drawn(work, catalog, other, s, upto=plan.step, new=plan.behind, ground=True)
            box = boxes[len(figures)]
            figures.append(_Figure("behind", SIDE_WORDS[other], _close_up(im, mine, s, box)))
        return _Step(plan, total, picture, _plan_notes(plan, work), figures)

    yield from map(one, book.plans)


# ---- PDF pages (pictures) --------------------------------------------------------------------

_FONTS: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
_MODEL_TOP = 490
_NOTES_WIDTH = PAGE_W - 2 * MARGIN - 390  # the words, beside the picture of hidden parts
_FOOTER = 70


AnyFont = ImageFont.FreeTypeFont | ImageFont.ImageFont

# Fonts looked for on the computer (by file name, in the places Pillow knows) when a text
# has letters the font that comes with Pillow lacks (it has little beyond plain English).
FALLBACK_FONTS = (
    "DejaVuSans.ttf",
    "NotoSans-Regular.ttf",
    "LiberationSans-Regular.ttf",
    "FreeSans.ttf",
    "Arial Unicode.ttf",
    "arialuni.ttf",
    "arial.ttf",
    "Arial.ttf",
    "segoeui.ttf",
    "NotoSansCJK-Regular.ttc",
    "msyh.ttc",
    "msgothic.ttc",
    "DroidSansFallbackFull.ttf",
)
_FALLBACK_PATHS: list[str] | None = None
_FALLBACK: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_COVERS: dict[tuple[int, str], bool] = {}
_MISSING = "\U0010fffd"  # a letter no font has: it draws the font's "missing" box


def _font(size: int) -> AnyFont:
    if size not in _FONTS:
        _FONTS[size] = ImageFont.load_default(size=size)
    return _FONTS[size]


def _fallback_fonts() -> list[str]:
    """The files of the fallback fonts found on this computer, in the order tried."""
    global _FALLBACK_PATHS
    if _FALLBACK_PATHS is None:
        found: list[str] = []
        for name in FALLBACK_FONTS:
            try:
                path = str(ImageFont.truetype(name, 12).path)
            except OSError:
                continue
            if path not in found:
                found.append(path)
        _FALLBACK_PATHS = found
    return _FALLBACK_PATHS


def _covers(font: AnyFont, ch: str) -> bool:
    """Whether the font draws the letter itself rather than its "missing" box."""
    if ch.isspace():
        return True
    key = (id(font), ch)
    if key not in _COVERS:
        _COVERS[key] = _glyph(font, ch) != _glyph(font, _MISSING)
    return _COVERS[key]


def _glyph(font: AnyFont, ch: str) -> tuple[tuple[int, int], bytes]:
    """The letter as the font draws it, alone (to compare with the "missing" box)."""
    left, top, right, bottom = (int(v) for v in font.getbbox(ch))
    im = Image.new("L", (max(1, right - left), max(1, bottom - top)), 0)
    ImageDraw.Draw(im).text((-left, -top), ch, font=font, fill=255)
    return im.size, im.tobytes()


def _font_for(text: str, size: int) -> AnyFont:
    """The font that comes with Pillow when it has every letter of ``text``; otherwise the
    first font on the computer that has them all (or else most of them)."""
    plain = _font(size)
    if text.isascii() or all(_covers(plain, ch) for ch in text):
        return plain
    best, best_count = plain, sum(_covers(plain, ch) for ch in text)
    for path in _fallback_fonts():
        if (path, size) not in _FALLBACK:
            _FALLBACK[(path, size)] = ImageFont.truetype(path, size)
        font = _FALLBACK[(path, size)]
        count = sum(_covers(font, ch) for ch in text)
        if count == len(text):
            return font
        if count > best_count:
            best, best_count = font, count
    return best


def _wrap(text: str, font, width: int) -> list[str]:
    """Lines of at most ``width`` pixels, broken between words; a word too long for a
    line is broken where it has to be."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if not line or font.getlength(trial) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
        while font.getlength(line) > width and len(line) > 1:
            cut = len(line) - 1
            while cut > 1 and font.getlength(line[:cut]) > width:
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line:
        lines.append(line)
    return lines


def _fit_name(name: str, width: int, sizes: tuple[int, ...]) -> tuple[int, list[str]]:
    """A part's name in at most two lines of ``width`` at the largest of ``sizes`` that
    allows it; at the smallest in as many lines as it takes. Never cut short."""
    lines: list[str] = []
    for size in sizes:
        lines = _wrap(name, _font_for(name, size), width)
        if len(lines) <= 2:
            return size, lines
    return sizes[-1], lines


def _shorten(text: str, font, width: int) -> str:
    """The text, ending in "..." if that is needed to fit ``width`` pixels."""
    if font.getlength(text) <= width:
        return text
    while text and font.getlength(text + "...") > width:
        text = text[:-1]
    return text.rstrip() + "..."


def _text(
    draw: ImageDraw.ImageDraw, xy, text: str, size: int, fill=INK, bold: bool = False, anchor="la"
) -> None:
    stroke = max(1, size // 48) if bold else 0
    draw.text(
        xy,
        text,
        font=_font_for(text, size),
        fill=fill,
        anchor=anchor,
        stroke_width=stroke,
        stroke_fill=fill,
    )


def _centred_with_mark(
    draw: ImageDraw.ImageDraw, cx: int, y: int, line: str, size: int, fill
) -> None:
    """A centred line of text in which "®" is drawn by hand (a small circled R, raised): the
    font that comes with Pillow has no such sign."""
    font = _font(size)
    pieces = line.split("®")
    mark = round(size * 0.62)
    width = sum(font.getlength(p) for p in pieces) + mark * (len(pieces) - 1)
    x = cx - width / 2
    for k, piece in enumerate(pieces):
        draw.text((x, y), piece, font=font, fill=fill)
        x += font.getlength(piece)
        if k < len(pieces) - 1:
            r = mark * 0.42
            mx, my = x + mark / 2, y + size * 0.3
            draw.ellipse((mx - r, my - r, mx + r, my + r), outline=fill, width=max(1, size // 18))
            draw.text((mx, my), "R", font=_font(max(6, round(size * 0.5))), fill=fill, anchor="mm")
            x += mark


def _paragraph(
    draw, x: int, y: int, text: str, size: int, width: int, fill=INK, gap: float = 1.3
) -> int:
    """Wrapped text; returns the y below it."""
    for line in _wrap(text, _font_for(text, size), width):
        _text(draw, (x, y), line, size, fill)
        y += round(size * gap)
    return y


def _footer(draw, book: _Booklet, page: int, pages: int) -> None:
    tail = f"  -  page {page} of {pages}"
    room = PAGE_W - 2 * MARGIN - int(_font(20).getlength(tail))
    name = _shorten(book.name, _font_for(book.name, 20), room)
    _text(draw, (PAGE_W // 2, PAGE_H - 40), name + tail, 20, SOFT_INK, anchor="mm")


def _new_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
    return im, ImageDraw.Draw(im)


def _paste_centred(page: Image.Image, im: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    page.paste(im, (x0 + (x1 - x0 - im.width) // 2, y0 + (y1 - y0 - im.height) // 2))


def _count_words(book: _Booklet) -> str:
    n_parts = len(book.build.parts)
    n_steps = len(book.plans)
    return (
        f"{n_parts} part{'s' if n_parts != 1 else ''}, {n_steps} step{'s' if n_steps != 1 else ''}"
    )


def _cover_page(book: _Booklet, pages: int) -> Image.Image:
    page, draw = _new_page()
    y = 90
    size, lines = _title_lines(book.name, PAGE_W - 2 * MARGIN)
    for line in lines:
        _text(draw, (PAGE_W // 2, y), line, size, bold=True, anchor="ma")
        y += round(size * 1.19)
    _text(draw, (PAGE_W // 2, y + 10), "Building instructions", 40, SOFT_INK, anchor="ma")
    _paste_centred(
        page,
        _fit(book.cover, (PAGE_W - 2 * MARGIN, 1050)),
        (MARGIN, y + 80, PAGE_W - MARGIN, y + 1150),
    )
    _text(draw, (PAGE_W // 2, 1440), _count_words(book), 48, bold=True, anchor="ma")
    y = 1560
    for line in _wrap(DISCLAIMER, _font(22), PAGE_W - 2 * MARGIN):
        _centred_with_mark(draw, PAGE_W // 2, y, line, 22, SOFT_INK)
        y += 30
    _footer(draw, book, 1, pages)
    return page


def _title_lines(name: str, width: int) -> tuple[int, list[str]]:
    """The cover's title: as large as lets it fit in two lines, down to 48 pixels; a name
    longer than three lines at that size ends in "..." (the HTML has it whole)."""
    lines: list[str] = []
    for size in (84, 72, 60, 48):
        lines = _wrap(name, _font_for(name, size), width)
        if len(lines) <= 2:
            return size, lines
    if len(lines) > 3:
        font, third = _font_for(name, 48), lines[2]
        while third and font.getlength(third + "...") > width:
            third = third[:-1]
        lines = lines[:2] + [third.rstrip() + "..."]
    return 48, lines


def _parts_chunks(lines: list[PartLine]) -> list[list[PartLine]]:
    return [lines[k : k + PARTS_PER_PAGE] for k in range(0, len(lines), PARTS_PER_PAGE)] or [[]]


def _parts_page(
    book: _Booklet,
    chunk: list[PartLine],
    first: bool,
    pics: _PartPictures,
    page_no: int,
    pages: int,
) -> Image.Image:
    page, draw = _new_page()
    _text(draw, (MARGIN, 60), "The parts you need" if first else "More parts", 60, bold=True)
    col_w = (PAGE_W - 2 * MARGIN) // PARTS_COLUMNS
    row_h = 205
    for k, line in enumerate(chunk):
        r, c = divmod(k, PARTS_COLUMNS)
        x = MARGIN + c * col_w
        y = 170 + r * row_h
        draw.rounded_rectangle((x + 6, y, x + col_w - 6, y + row_h - 14), radius=18, fill=BOX)
        pic = _fit(pics.get(line.part, line.colour, 24, BOX), (150, 120))
        page.paste(pic, (x + 16 + (150 - pic.width) // 2, y + 10 + (120 - pic.height) // 2))
        _text(draw, (x + 180, y + 18), f"{line.quantity}x", 44, bold=True)
        size, names = _fit_name(line.name, col_w - 40, (22, 20, 18))
        step = size + 4
        ty = min(y + 136, y + row_h - 20 - step * len(names))
        for t in names:
            _text(draw, (x + 20, ty), t, size)
            ty += step
        _text(draw, (x + 180, y + 76), f"Part {line.part}", 20, SOFT_INK)
        _text(draw, (x + 180, y + 100), line.colour_name, 20, SOFT_INK)
    _footer(draw, book, page_no, pages)
    return page


BOX_NAME_SIZES = (19, 17, 15)  # text sizes for the names in a step's parts box (PDF)
BOX_NAME_W = 118  # the narrowest column of a step's parts box


def _parts_box(lines: list[PartLine], pics: _PartPictures, max_w: int, max_h: int) -> Image.Image:
    """The light blue box of the parts to add, as large as fits: each part's picture, how
    many, and its short name in small letters (a 1 x 6 and a 1 x 8 brick look alike when
    small), never cut: smaller letters or a third line when it is long."""
    pad, gap, qty_h = 16, 22, 50
    fitted = {
        ln.part: _fit_name(_short_name(pics.catalog, ln.part), BOX_NAME_W, BOX_NAME_SIZES)
        for ln in lines
    }
    name_h = max([2 * (BOX_NAME_SIZES[0] + 3)] + [len(t) * (z + 3) for z, t in fitted.values()])
    rows: list[list[tuple[Image.Image, PartLine, int]]] = [[]]
    heights: list[int] = []
    widths: list[int] = []
    total_h = 0
    for s in (28, 24, 20, 16, 13, 10, 8, 6, 4):
        rows = [[]]
        width = 0
        for ln in lines:
            im = pics.get(ln.part, ln.colour, s, BOX)
            w = max(im.width, 118)
            if rows[-1] and width + gap + w > max_w - 2 * pad:
                rows.append([])
                width = 0
            width += (gap if rows[-1] else 0) + w
            rows[-1].append((im, ln, w))
        heights = [max(im.height for im, _, _ in row) + qty_h + name_h for row in rows]
        widths = [sum(w for _, _, w in row) + gap * (len(row) - 1) for row in rows]
        total_h = sum(heights) + 2 * pad + 12 * (len(rows) - 1)
        if total_h <= max_h and max(widths) <= max_w - 2 * pad:
            break
    box = Image.new("RGB", (max(widths) + 2 * pad, total_h), WHITE)
    draw = ImageDraw.Draw(box)
    draw.rounded_rectangle((0, 0, box.width - 1, box.height - 1), radius=22, fill=BOX)
    y = pad
    for row, rh in zip(rows, heights, strict=True):
        x = pad
        for im, ln, w in row:
            base = y + rh - qty_h - name_h
            box.paste(im, (x + (w - im.width) // 2, base - im.height))
            _text(draw, (x + w // 2, base + 4), f"{ln.quantity}x", 40, bold=True, anchor="ma")
            ty = base + qty_h
            size, texts = fitted[ln.part]
            for t in texts:
                _text(draw, (x + w // 2, ty), t, size, SOFT_INK, anchor="ma")
                ty += size + 3
            x += w + gap
        y += rh + 12
    return box


def _turn_arrow(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill) -> None:
    """A round arrow: most of a circle with a head at its end."""
    draw.arc((cx - r, cy - r, cx + r, cy + r), start=-60, end=230, fill=fill, width=max(4, r // 5))
    a = np.radians(-60)
    tip = (cx + r * np.cos(a), cy + r * np.sin(a))
    k = r * 0.55
    draw.polygon(
        [
            (tip[0] + k * 0.9, tip[1] + k * 0.1),
            (tip[0] - k * 0.6, tip[1] - k * 0.5),
            (tip[0] - k * 0.1, tip[1] + k * 0.9),
        ],
        fill=fill,
    )


def _step_page(
    book: _Booklet, st: _Step, pics: _PartPictures, page_no: int, pages: int
) -> Image.Image:
    page, draw = _new_page()
    plan = st.plan
    # the step number, big, and "of N" under it
    _text(draw, (MARGIN, 40), str(plan.number), 190, bold=True)
    num_w = int(_font(190).getlength(str(plan.number))) + 10
    _text(draw, (MARGIN + 4, 260), f"of {st.total}", 40, SOFT_INK)
    left = MARGIN + max(num_w, int(_font(40).getlength(f"of {st.total}"))) + 50
    box = _parts_box(plan.lines, pics, PAGE_W - MARGIN - left, 340)
    page.paste(box, (left, 40))
    # turn the model round, and which side we see it from
    y = 400
    if plan.turn:
        tw = int(_font(40).getlength(TURN_TEXT))
        draw.rounded_rectangle((MARGIN, y, MARGIN + tw + 130, y + 66), radius=18, fill=TURN_BOX)
        _turn_arrow(draw, MARGIN + 50, y + 33, 22, INK)
        _text(draw, (MARGIN + 95, y + 33), TURN_TEXT, 40, bold=True, anchor="lm")
    _text(draw, (PAGE_W - MARGIN, y + 33), SIDE_WORDS[plan.view], 26, SOFT_INK, anchor="rm")
    if plan.number == 1:
        _text(draw, (MARGIN, y + 33), GRID_NOTE, 22, SOFT_INK, anchor="lm")
    # the model, at the booklet's one scale, centred in the same place on every page
    top = _MODEL_TOP
    mw, mh = book.model_box
    _paste_centred(page, st.picture, (MARGIN, top, MARGIN + mw, top + mh))
    # parts the picture does not show: words, and close-ups of them
    if st.notes:
        y0 = top + mh + 10
        size, wrapped, _ = _fit_notes(st.notes, _NOTES_WIDTH, book.notes_height)
        y = y0
        _text(draw, (MARGIN, y), "Hidden in the picture:", 26, bold=True)
        y += 40
        for lines in wrapped:
            for line in lines:
                _text(draw, (MARGIN, y), line, size)
                y += round(size * 1.3)
            y += 6
        fx = PAGE_W - MARGIN - _FIGURE_W
        slots = _figure_slots(book.notes_height, _figure_count(plan))
        for fig, (dy, h) in zip(st.figures, slots, strict=False):
            fy = y0 + dy
            draw.rounded_rectangle(
                (fx, fy, PAGE_W - MARGIN, fy + h), radius=16, outline=HALO, width=4
            )
            _text(draw, (fx + _FIGURE_W // 2, fy + 10), fig.caption, 24, bold=True, anchor="ma")
            _paste_centred(
                page,
                _fit(fig.picture, (_FIGURE_W - 30, h - 62)),
                (fx + 10, fy + 46, PAGE_W - MARGIN - 10, fy + h - 12),
            )
    _footer(draw, book, page_no, pages)
    return page


def _last_page(book: _Booklet, page_no: int, pages: int) -> Image.Image:
    page, draw = _new_page()
    _text(draw, (PAGE_W // 2, 70), "Finished!", 84, bold=True, anchor="ma")
    cell_w = (PAGE_W - 2 * MARGIN) // 2
    cell_h = 700
    for k, (caption, im) in enumerate(book.sides):
        r, c = divmod(k, 2)
        x, y = MARGIN + c * cell_w, 210 + r * (cell_h + 30)
        _text(draw, (x + cell_w // 2, y), caption, 34, SOFT_INK, anchor="ma")
        _paste_centred(
            page, _fit(im, (cell_w - 20, cell_h - 60)), (x, y + 50, x + cell_w, y + cell_h)
        )
    _footer(draw, book, page_no, pages)
    return page


def _page_count(book: _Booklet) -> int:
    return 1 + len(_parts_chunks(book.lines)) + len(book.plans) + 1


def _pages(
    book: _Booklet, catalog: Catalog, pics: _PartPictures
) -> Iterator[tuple[Image.Image, Callable[[], str]]]:
    """Every page in order, made one at a time: (the PDF page's picture, a function giving
    its HTML). Text is drawn here, in one thread; the HTML is made where it is asked for."""
    pages = _page_count(book)
    yield _cover_page(book, pages), lambda: _html_cover(book)
    n = 1
    for k, chunk in enumerate(_parts_chunks(book.lines)):
        n += 1
        yield (
            _parts_page(book, chunk, k == 0, pics, n, pages),
            lambda chunk=chunk, first=k == 0: _html_parts(chunk, first, pics),
        )
    for st in _steps(book, catalog):
        n += 1
        yield _step_page(book, st, pics, n, pages), lambda st=st: _html_step(st, pics)
    yield _last_page(book, pages, pages), lambda: _html_last(book)


def page_images(project: Project, catalog: Catalog | None = None) -> list[Image.Image]:
    """Every page of the PDF as a picture, in order (for looking at the booklet)."""
    catalog = catalog or load_catalog()
    book = _booklet(project, catalog)
    return [page for page, _ in _pages(book, catalog, _PartPictures(catalog))]


# ---- HTML ------------------------------------------------------------------------------------

_CSS = """
@page { size: A4; margin: 10mm; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #191919; background: #e8e8e4; }
.page { background: #fff; width: 190mm; min-height: 277mm; margin: 8mm auto; padding: 8mm;
  break-after: page; page-break-after: always; }
.page:last-child { break-after: auto; page-break-after: auto; }
@media print {
  body { background: #fff; }
  .page { margin: 0; padding: 0; width: auto; min-height: 0; }
  .page.step { height: 275mm; display: flex; flex-direction: column; }
  .page.step .model { flex: 0 1 auto; min-height: 0; object-fit: contain; }
}
h1 { font-size: 40px; text-align: center; margin: 0 0 4px; overflow-wrap: anywhere; }
h2 { font-size: 30px; margin: 0 0 12px; }
.sub { text-align: center; color: #5f5f5f; font-size: 20px; margin: 0; }
.count { text-align: center; font-size: 26px; font-weight: bold; }
.legal { text-align: center; color: #5f5f5f; font-size: 12px; }
img { max-width: 100%; height: auto; }
.hero, .model { display: block; margin: 0 auto; max-height: 170mm; width: auto; }
ul { list-style: none; padding: 0; margin: 0; }
.partlist { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.partlist li { background: #dcebfa; border-radius: 10px; padding: 8px; display: grid;
  grid-template-columns: 90px 1fr; gap: 2px 10px; align-items: center; }
.partlist img { grid-row: span 3; justify-self: center; max-height: 80px; }
.qty { font-size: 26px; font-weight: bold; }
.code { color: #5f5f5f; font-size: 13px; }
.head { display: flex; gap: 24px; align-items: flex-start; }
.num { display: block; font-size: 96px; font-weight: bold; line-height: 1; }
.of { display: block; font-size: 20px; color: #5f5f5f; }
.box { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; background: #dcebfa;
  border-radius: 12px; padding: 10px 14px; }
.box li { text-align: center; }
.box .qty { display: block; }
.box .name { display: block; color: #5f5f5f; font-size: 12px; }
.turn { display: inline-block; background: #ffe9a8; border-radius: 10px; padding: 6px 14px;
  font-size: 24px; font-weight: bold; margin: 10px 0 0; }
.side { color: #5f5f5f; font-size: 15px; text-align: right; margin: 6px 0; }
.note { color: #5f5f5f; font-size: 14px; margin: 6px 0 0; }
.hidden { font-size: 16px; display: flex; gap: 12px; align-items: flex-start; }
.hidden ul { list-style: disc; padding-left: 20px; flex: 1; }
.hidden > div:first-child { flex: 1; }
.hidden .figs { display: flex; flex-direction: column; gap: 8px; flex: 0 0 42%; }
.hidden figure { margin: 0; border: 3px solid #ffbe00; border-radius: 10px; padding: 6px;
  text-align: center; }
.hidden figure img { max-height: 170px; width: auto; }
.sides { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; text-align: center; }
.sides figure { margin: 0; }
.sides img { max-height: 100mm; width: auto; }
"""


def _png(im: Image.Image) -> str:
    """A PNG in 256 colours or fewer: the pictures are flat colours, so this loses little
    and keeps a 200-step booklet small."""
    buf = io.BytesIO()
    im.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(
        buf, "PNG", compress_level=6
    )
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _img(cls: str, im: Image.Image, alt: str) -> str:
    return (
        f'<img class="{cls}" width="{im.width}" height="{im.height}" '
        f'src="{_png(im)}" alt="{html.escape(alt)}">'
    )


def _html_parts(chunk: list[PartLine], first: bool, pics: _PartPictures) -> str:
    out = ['<section class="page parts">']
    out.append(f"<h2>{'The parts you need' if first else 'More parts'}</h2>")
    out.append('<ul class="partlist">')
    for line in chunk:
        alt = f"{line.name}, {line.colour_name}"
        out.append(
            f'<li class="part" data-part="{html.escape(line.part)}" '
            f'data-colour="{line.colour}" data-quantity="{line.quantity}">'
            + pics.img(line.part, line.colour, 16, BOX, alt)
            + f'<span class="qty">{line.quantity}x</span>'
            + f"<span>{html.escape(line.name)}</span>"
            + f'<span class="code">Part {html.escape(line.part)}, '
            + f"{html.escape(line.colour_name)}</span></li>"
        )
    out.append("</ul></section>")
    return "\n".join(out)


def _html_step(st: _Step, pics: _PartPictures) -> str:
    plan = st.plan
    out = ['<section class="page step">', '<div class="head"><div>']
    out.append(f'<span class="num">{plan.number}</span><span class="of">of {st.total}</span></div>')
    out.append('<ul class="box">')
    for line in plan.lines:
        alt = f"{line.quantity} x {line.name}, {line.colour_name}"
        out.append(
            f'<li class="add" data-part="{html.escape(line.part)}" '
            f'data-colour="{line.colour}" data-quantity="{line.quantity}">'
            + pics.img(line.part, line.colour, HTML_BOX_PX, BOX, alt)
            + f'<span class="qty">{line.quantity}x</span>'
            + f'<span class="name">{html.escape(_short_name(pics.catalog, line.part))}</span></li>'
        )
    out.append("</ul></div>")
    if plan.turn:
        out.append(f'<p class="turn">&#8635; {html.escape(TURN_TEXT)}</p>')
    if plan.number == 1:
        out.append(f'<p class="note">{html.escape(GRID_NOTE)}</p>')
    out.append(f'<p class="side">{html.escape(SIDE_WORDS[plan.view])}</p>')
    out.append(_img("model", st.picture, f"The model after step {plan.number}"))
    if st.notes:
        out.append('<div class="hidden"><div><strong>Hidden in the picture:</strong><ul>')
        out += [f"<li>{html.escape(s)}</li>" for s in _note_lines(st.notes)]
        out.append("</ul></div>")
        if st.figures:
            out.append('<div class="figs">')
            for fig in st.figures:
                alt = (
                    "The hidden parts put in first"
                    if fig.cls == "first"
                    else f"The new parts {fig.caption.lower()}"
                )
                out.append(
                    f"<figure><figcaption><strong>{html.escape(fig.caption)}</strong>"
                    f"</figcaption>{_img(fig.cls, fig.picture, alt)}</figure>"
                )
            out.append("</div>")
        out.append("</div>")
    out.append("</section>")
    return "\n".join(out)


def _html_head(book: _Booklet, pics: _PartPictures) -> str:
    name = html.escape(book.name)
    height = _html_model_height(book, pics)
    model = f"@media print {{ .page.step .model {{ max-height: {height}px; }} }}"
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{name}: building instructions</title>",
            f"<style>{_CSS}{model}</style></head><body>",
        ]
    )


_HTML_FIGURE = 215  # CSS pixels a close-up takes in the HTML (picture, caption, frame)


def _html_model_height(book: _Booklet, pics: _PartPictures) -> int:
    """The height (CSS pixels, 96 to the inch) at which every step's picture fits on its
    printed sheet beside the tallest parts box and notes of the booklet: one height for
    all, so the model keeps its scale from page to page. Worked out from the sizes of the
    pictures and generous text sizes; if it is ever short, the page's layout shrinks that
    one picture rather than spill onto a second sheet."""
    sheet, width = 1039, 718  # 275 mm by 190 mm
    box_w = width - 140 - 24 - 28  # beside the step number, inside the box's padding
    worst = 0
    for plan in book.plans:
        row_w, row_h, heights = 0, 0, []
        for ln in plan.lines:
            im = pics.get(ln.part, ln.colour, HTML_BOX_PX, BOX)
            w = max(im.width, 60) + 16
            if row_w and row_w + w > box_w:
                heights.append(row_h)
                row_w, row_h = 0, 0
            row_w += w
            row_h = max(row_h, im.height + 34 + 16)
        heights.append(row_h)
        head = max(140, sum(heights) + 20 + 16 * (len(heights) - 1))
        other = head + 30 + (56 if plan.turn else 0) + (24 if plan.number == 1 else 0)
        notes = _plan_notes(plan, book.build)
        if notes:
            text = 24 + sum(
                19 * (1 + len(s) * 8 // (width * 55 // 100 - 30)) + 4 for s in _note_lines(notes)
            )
            other += max(text, 200, _HTML_FIGURE * _figure_count(plan)) + 20
        worst = max(worst, other)
    return max(300, sheet - worst - 30)


def _html_cover(book: _Booklet) -> str:
    return "\n".join(
        [
            '<section class="page cover">',
            f"<h1>{html.escape(book.name)}</h1>",
            '<p class="sub">Building instructions</p>',
            _img("hero", book.cover_small, f"The finished {book.name}"),
            f'<p class="count">{html.escape(_count_words(book))}</p>',
            f'<p class="legal">{html.escape(DISCLAIMER)}</p>',
            "</section>",
        ]
    )


def _html_last(book: _Booklet) -> str:
    out = ['<section class="page finished"><h1>Finished!</h1><div class="sides">']
    for caption, im in book.sides:
        small = _fit(im, (440, 520))
        out.append(
            f"<figure>{_img('side', small, caption)}"
            f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        )
    out.append("</div></section>")
    return "\n".join(out)


# ---- the PDF file ----------------------------------------------------------------------------


def _png_stream(im: Image.Image) -> bytes:
    """The compressed image data of a PNG of ``im``: what a PDF reads as FlateDecode with
    the PNG predictor."""
    buf = io.BytesIO()
    im.save(buf, "PNG", compress_level=6)
    data = buf.getvalue()
    pos, chunks = 8, []
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        if data[pos + 4 : pos + 8] == b"IDAT":
            chunks.append(data[pos + 8 : pos + 8 + length])
        pos += 12 + length
    return b"".join(chunks)


def _pdf_text(text: str) -> bytes:
    return b"<FEFF" + text.encode("utf-16-be").hex().upper().encode("ascii") + b">"


class _PdfWriter:
    """A minimal PDF: one picture per page, written as it comes."""

    def __init__(self, fh, title: str) -> None:
        self.fh = fh
        self.offsets: dict[int, int] = {}
        self.kids: list[int] = []
        self.next = 4  # 1 catalogue, 2 page list, 3 information
        self.title = title
        fh.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    def _obj(self, num: int, body: bytes, stream: bytes | None = None) -> None:
        self.offsets[num] = self.fh.tell()
        self.fh.write(b"%d 0 obj\n" % num + body)
        if stream is not None:
            self.fh.write(b"\nstream\n" + stream + b"\nendstream")
        self.fh.write(b"\nendobj\n")

    def page(self, im: Image.Image, data: bytes | None = None) -> None:
        """Add a page showing ``im``; ``data`` is ``_png_stream(im)`` if already made."""
        w_pt, h_pt = im.width * 72 / DPI, im.height * 72 / DPI
        image, content, page = self.next, self.next + 1, self.next + 2
        self.next += 3
        if data is None:
            data = _png_stream(im.convert("RGB"))
        self._obj(
            image,
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
            b"/BitsPerComponent 8 /Filter /FlateDecode /DecodeParms << /Predictor 15 /Colors 3 "
            b"/BitsPerComponent 8 /Columns %d >> /Length %d >>"
            % (im.width, im.height, im.width, len(data)),
            data,
        )
        draw = b"q %.2f 0 0 %.2f 0 0 cm /Im0 Do Q" % (w_pt, h_pt)
        self._obj(content, b"<< /Length %d >>" % len(draw), draw)
        self._obj(
            page,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] "
            b"/Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>"
            % (w_pt, h_pt, image, content),
        )
        self.kids.append(page)

    def close(self) -> None:
        kids = b" ".join(b"%d 0 R" % k for k in self.kids)
        self._obj(2, b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(self.kids)))
        self._obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        self._obj(3, b"<< /Title " + _pdf_text(self.title) + b" /Producer (BrickSnap) >>")
        start = self.fh.tell()
        size = self.next
        self.fh.write(b"xref\n0 %d\n0000000000 65535 f \n" % size)
        for num in range(1, size):
            self.fh.write(b"%010d 00000 n \n" % self.offsets[num])
        self.fh.write(
            b"trailer\n<< /Size %d /Root 1 0 R /Info 3 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (size, start)
        )


# ---- the door --------------------------------------------------------------------------------


def make_instructions(project: Project, catalog: Catalog | None = None) -> dict[str, Path]:
    catalog = catalog or load_catalog()
    book = _booklet(project, catalog)
    pics = _PartPictures(catalog)
    paths = {"html": project.path / "instructions.html", "pdf": project.path / "instructions.pdf"}
    tmp = paths["pdf"].with_name(f".{paths['pdf'].name}.{os.getpid()}.tmp")
    pieces = [_html_head(book, pics)]

    def encode(item: tuple[Image.Image, Callable[[], str]]) -> tuple[Image.Image, bytes, str]:
        page, piece = item
        return page, _png_stream(page), piece()

    try:
        with open(tmp, "wb") as fh:
            pdf = _PdfWriter(fh, f"{book.name}: building instructions")
            for page, data, piece in _in_order(encode, _pages(book, catalog, pics)):
                pdf.page(page, data)
                pieces.append(piece)
            pdf.close()
        pieces.append("</body></html>")
        write_text_atomic(paths["html"], "\n".join(pieces) + "\n")
        os.replace(tmp, paths["pdf"])
    finally:
        tmp.unlink(missing_ok=True)
    return paths
