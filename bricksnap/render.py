"""Pictures of a seed, a Design or a Build, drawn with numpy and Pillow only (no GPU).

These pictures are how the AI designer sees the model and how people compare before and
after, so two things matter above all: the seed and the build are drawn from the SAME
viewpoint at the SAME scale and position so they can be compared directly, and a reader can
read grid coordinates off the picture.

CONTRACT (tests go in tests/test_render.py)

Views (``VIEWS``)
- "front": looking from -y towards +y. Picture right is +x, picture up is +z.
- "right": looking from +x towards -x. Picture right is +y, up is +z.
- "back":  looking from +y towards -y. Picture right is -x, up is +z.
- "left":  looking from -x towards +x. Picture right is -y, up is +z.
- "top":   looking straight down. Picture right is +x, picture up is +y (front at the bottom).
- "iso":   a three-quarter view from the front right and above (azimuth about 35 degrees,
           elevation about 30 degrees), orthographic, with correct hiding of far parts.

Scale: one stud is ``px_per_stud`` pixels wide; one plate is 0.4 of that tall (true
proportions: 3.2 mm against 8 mm). All views of the same grid have the same scale.

Labels (the five straight-on views, when ``labels=True``): a margin with tick marks and
numbers so cell coordinates can be read directly. Along a stud axis, number every 2 studs
(every 5 above 40 studs). Along z, mark every brick course (3 plates) and number it in
PLATES (0, 3, 6, ...), since edits are given in plates. Print the axis letter and its
direction (for example "x ->", "<- x" in the back view, "z ^"). Numbers must match the cell
index of the cell at that tick, including in the mirrored views.

``render_build(build, catalog, view, px_per_stud=16, labels=True, upto_step=None)``
- Each part is drawn in its catalogue colour with a thin darker outline, so individual parts
  can be told apart. Nearer parts hide farther ones. Parts farther from the viewer are
  slightly darker, so depth reads. Exposed studs may be drawn as small bumps.
- ``upto_step``: draw only parts whose step is at most this (for instruction pictures).
- In "iso", draw each part as a box with a lighter top and darker sides, outlined.

``render_design(design, catalog, view, px_per_stud=16, labels=True)``: the same, cell by cell.

``render_seed(seed, view, grid_shape, seed_offset=(0, 0, 0), px_per_stud=16, labels=True)``
- Draws the mesh itself (z-buffered, flat-shaded with a fixed light, in its own colours or
  light grey) placed in the same grid as the Design made from it, so that it lines up
  pixel-for-pixel with ``render_design`` and ``render_build`` of that grid.

``contact_sheet(items, columns=3, title=None)``: lays out (caption, image) pairs in a grid
with captions.

``compare_sheet(seed, design, build, catalog, views=("front", "right", "top", "iso"),
px_per_stud=16)``: one picture with the seed's views in the top row and the build's (or,
when ``build`` is None, the design's) in the bottom row, each column one view, captioned.
``seed`` may be None, in which case there is one row.

All functions return ``PIL.Image.Image`` in RGB with a light background. Output is
deterministic: the same input gives identical pixels. Speed: a compare sheet for a
5,000-part build in under 5 seconds.

STAGE 2 ADDITIONS TO THE CONTRACT: real part shapes, and the rough build

Parts are no longer all boxes. In every view a part is drawn by its catalogue ``kind``:
- "slope", "curved_slope": a wedge. Full height over the stud cells, and over the slanted
  cells a face running from full height down to a low lip (about half a plate) at the low
  edge, in the direction ``Catalog.low_side(placement)``. Seen from the side the slanted
  outline must be visible against the background; seen from above the slanted face is
  drawn a little lighter or darker than a flat top so it can be told from one, with no
  studs on it. A curved slope may be drawn as a straight wedge.
- "slope_inverted": the wedge upside down (full at the top, cut away underneath).
- "tile": flat, no studs (this already follows from its stud cells; keep it true).
- "round_brick", "round_plate", "round_tile", "dish", "cone": round in the top view and in
  "iso" (a cylinder, or for a cone a tapering one; twelve sides or more). In the side views
  a cone tapers; the others may keep a rectangular outline.
- every other kind: a box, as before.
Detail parts need nothing special: they are ordinary Placements in the Build.

``compare_sheet(seed, design, build, catalog, views=..., px_per_stud=16, rough=None)``
- ``rough`` is an optional second Build: the plain conversion, before any design work. When
  given, the sheet has three rows, captioned "seed", "rough" and "build", in that order,
  same views, same scale, lined up. Without it the sheet is exactly as before.

``silhouette(obj, catalog, view, grid_shape=None, seed_offset=(0, 0, 0), px_per_stud=8)
-> bool array [rows, cols]``
- True where the picture of ``obj`` (a Seed, a Design or a Build) covers the pixel, drawn
  without labels in the same frame as the render functions, so the silhouettes of a seed
  and of the Build made from it can be compared pixel for pixel. ``grid_shape`` and
  ``seed_offset`` are needed for a Seed (as in ``render_seed``) and ignored otherwise.
  Used by the scorecard to measure how closely a build's outline matches its seed.

STAGE 4 ADDITIONS TO THE CONTRACT: instruction pictures

For the instruction booklet (``bricksnap.instructions``):
- ``render_build(..., upto_step=k, highlight_step=k)``: parts of step ``k`` as usual, parts
  of earlier steps pale (blended most of the way to the background, outlines kept);
- a second three-quarter view, "iso_back", from the back left and above, the mirror image
  of "iso" about the model's centre;
- ``render_part(part_id, colour, catalog, px_per_stud=24) -> Image``: one part alone on a
  light background, three-quarter view, in its real shape;
- ``visible_parts(build, catalog, view, upto_step=None) -> set[int]``: the indices of the
  parts of which at least a few pixels show in that view.
None of this changes any picture the renderer draws today.

STAGE 4 ADDITION TO THE CONTRACT: sideways parts
A part with ``Placement.face`` other than "top" (a Build part, or a Design detail) is drawn
lying on its side in its column of three cells, exactly where ``bricksnap.ldraw`` puts it:
its bottom against the brick behind the column, centred on the side stud (10 LDU below the
top of the column), reaching 8 LDU (0.4 stud) out of the face, its top pointing out of
that face. In the view named by its face it is seen face-on in its real outline (a round
tile or round plate as a disc one stud across, a 1 x 1 tile as a square); in the other side
views and from the top it is a thin edge; in both three-quarter views it is a disc or slab
in its real place. A round plate on its side carries its stud, pointing outwards. It has no
stud on top in the stud grid. Every other part, and every picture without a sideways part,
is drawn exactly as before.

Implementation notes
--------------------
- Every view is an affine map from continuous grid coordinates (x and y in studs, z in
  plates) to (picture column, picture row, depth in mm). ``view_frame`` returns that map
  as a :class:`Frame`; it depends only on the grid shape, the view, the scale and whether
  there are labels, which is what makes the seed, the Design and the Build line up.
  Pixel (col, row) samples the scene at its centre (col + 0.5, row + 0.5).
- Image size: the drawing area is ``round(n * px_per_stud)`` pixels per stud axis and
  ``round(nz * 0.4 * px_per_stud)`` along z. Around it is a pad of
  ``ceil(px_per_stud / 4) + 2`` pixels (room for the studs on top), or, with labels, label
  margins (see ``Frame``). Number spacing grows (2, 5, 10, ... studs; 3, 6, 15, ... plates)
  when the numbers would otherwise overlap at small scales.
- Builds and Designs are both reduced to a "scene": a grid saying which group (a part, or a
  single Design cell) fills each cell, plus where exposed studs stand. Straight-on views
  take the first filled cell along each line of sight; "iso" and seeds go through a small
  z-buffered triangle rasteriser. Outlines are drawn wherever the group changes, so parts
  (or Design cells) are told apart.
- Shaped parts (slopes, inverted slopes, round parts, cones, dishes; in a Design, detail
  parts of those kinds) leave the cell grid and become triangles in the scene, placed from
  ``Catalog.footprint``, ``Catalog.stud_cells`` and ``Catalog.low_side``. In straight views
  they are rasterised and composited with the cells by depth (the cells' nearest face), so
  everything behind a slanted face shows above it; in "iso" they join the box faces, with
  faces turned away from the viewer left out. Their studs come from the same stud grid as
  every other part. A part whose rotation is not a quarter turn is drawn as a box.
- Wedges: a prism of a (run, height) profile across the part. A slope is full height over
  its stud rows and falls to a lip of ``SLOPE_LIP`` (half a plate) at the low edge; a slope
  with no studs (cheese slope, 1x2 x 2/3) falls over its whole depth. A curved slope is a
  curve of ``CURVE_SEGMENTS`` facets, steep at the lip and flat at the top. An inverted
  slope is full height over the one row at its low side and cut away underneath the rest,
  from the bottom of that row up to a lip under the top at the far edge.
- Round parts: lathes of ``ROUND_SIDES`` facets, ``ROUND_GAP`` narrower than the
  footprint, with a profile per kind (``_LATHE_PROFILES``): straight cylinders, a cone
  tapering to the width of its stud above a short foot, a dish that domes from a short rim.
- Shading of shaped faces. Straight views: a face square to the viewer has exactly the
  colour a box face would; seen from the side a face that tilts up is lighter (by up to
  0.3) and one that tilts down darker, and round sides darken a little towards their rim;
  seen from above a slanted face is darker the steeper it is and darkens further (by up to
  0.3) from its high edge to its low edge, so the direction it falls in can be read. "iso":
  a blend of the box face shades weighted by the face direction, with tilted faces a little
  lighter. Outlines: in straight views faces square to the viewer, and round sides seen from
  the side, outline with the part (a wedge seen from the side outlines like a box); other
  faces outline on their own, so the crease between a flat top and a slanted face shows.
  In "iso" every face outlines on its own, as the box faces do.
- ``compare_sheet`` with ``rough``: title "Seed (top row), rough conversion (middle row)
  and build (bottom row)" (or without the seed, "Rough conversion (top row) and build
  (bottom row)"); captions "rough - <view>". Without ``rough`` nothing changes.
- ``silhouette`` leaves studs out: they are not part of the outline a seed describes, and
  with them even a perfect box build would not match its box seed in the side views. It
  draws in the same frame as ``render_*`` with ``labels=False``; ``px_per_stud`` is
  applied as given.
- Studs: small bumps in side views, rings in the top view, short octagonal posts in "iso".
  Design cells show studs where their finish is "studs" and nothing sits on them. A stud
  under the cut-away end of an inverted slope counts as uncovered (only the slope's full
  row covers the studs under it); the depth test against the wedge then decides what of it
  shows, as for any stud behind a shaped part.
- Speed: the rasteriser keeps the nearest triangle per pixel with ``np.fmin.at`` (ties to
  the lower triangle index, as before); ``compare_sheet`` makes each Build's or Design's
  scene once for all its views, and draws a rough that is the build object itself once;
  straight views leave out shaped parts that cannot show (behind an identical part in line
  with them, or behind box cells), which changes no pixel. Measured on a busy 16-core
  machine: a 5,000-part compare sheet with rough takes under 1 second for typical builds
  and about 2 seconds when every part is a 2x2 dish; the slowest case found, 5,000 2x2
  round bricks in one flat layer (pictures over 2,000 pixels wide), about 2.5 seconds.
- Colours not in the catalogue are drawn magenta so they stand out. Parts with an unknown
  part id, or outside the grid, are not drawn (the checks report them).
- Depth darkening: up to ``DEPTH_FADE`` in straight views and the gentler
  ``ISO_DEPTH_FADE`` in "iso" for Builds and Designs (iso also has face shading). Seeds
  are not faded in "iso", where their flat shading already shows the shape.
- The smallest scale is 3 pixels per stud: below that a plate is under 1.2 pixels tall and
  rows are sampled at pixel centres, so some one-plate parts would not be drawn at all.
- Sideways parts are always shaped parts (``_sideways_mesh``): the part upright in a 1 x 1
  x 1 box (a lathe for round kinds, a box otherwise, plus a stud of 12 by 4 LDU when it has
  one), turned so its top points to -y, moved onto the back of the column at the stud's
  height, then turned about the column's centre to its face. Their shape key includes the
  face, so "identical part in line" never confuses an upright part with a sideways one.
- ``label_texts`` lists every text in the label margins (with the tick it belongs to);
  the pictures draw exactly that list.

Implementation notes for stage 4
- ``VIEWS`` is unchanged (the six views every older caller and test walks through);
  ``ALL_VIEWS`` adds "iso_back", and ``ISO_VIEWS`` names the two three-quarter views. Every
  function that takes a view accepts "iso_back", seeds and Designs included.
- "iso_back" is "iso" with the whole scene turned half a turn about the vertical line
  through the grid's centre (cell (x, y, z) to (nx - 1 - x, ny - 1 - y, z), shaped parts'
  triangles and normals likewise). Its picture is therefore exactly the "iso" picture of
  the Build turned round, same size, same shading and the same light; ``view_frame`` gives
  the matching map from the grid's own coordinates. A seed is drawn the same way.
- Highlighting changes colours only after the picture is shaded and before outlines are
  drawn: every pixel that belongs to a part of an earlier step is blended ``PALE`` (0.7)
  of the way to the background. Its shading, depth fade and studs stay readable, and its
  outlines are drawn from the pale colour, so they stay (fainter than those of the new
  parts). Parts of the step itself, and later ones that ``upto_step`` lets in, are drawn
  exactly as without highlighting. Without ``highlight_step`` the drawing code path is the
  one used before stage 4, so no existing picture changes (tests compare bytes).
- ``part_map(build, catalog, view, upto_step=None, px_per_stud=8, labels=False)`` gives,
  for every pixel of the picture ``render_build`` draws with the same arguments, the index
  into ``build.parts`` of the part it shows (-1 for background and margins), so a caller
  can mark parts on the picture. ``part_pixels(build, catalog, view, upto_step=None,
  px_per_stud=8) -> {index: pixels}`` counts those pixels per part (its studs and outline
  included, labels off). ``render_build_map`` returns the picture and its part map from
  one drawing, for callers that need both; ``part_pixels_views(build, catalog, views,
  upto_step=None, px_per_stud=8)`` gives ``part_pixels`` for several views from one
  scene (the booklet measures both three-quarter views of every step, and making the
  scene is a third of that work). ``visible_parts`` is the parts with at least
  ``min_pixels``
  (default 4) of them: at 8 pixels a stud that is a sliver about a tenth of the top of a
  1x1 plate. Indices are always those of ``build.parts``, also with ``upto_step``.
- ``render_part`` draws the part at rot 0 in a grid exactly its own size, "iso", without
  labels, so parts of different sizes come out at the same scale. An unknown part id is a
  plain ``ValueError``; a colour not in the catalogue is drawn magenta, as everywhere.

STUDIO ADDITION TO THE CONTRACT: cut-through views and zooms (tests in tests/test_studio.py)
- ``render_section(obj, catalog, axis, at, px_per_stud=16, labels=True)``: a Build or a Design
  cut open at cell ``at`` across ``axis``, seen in ``SECTION_VIEWS`` (x from the +x side,
  keeping x <= at; y from the front, keeping y >= at; z from above, keeping z <= at), with
  that view's numbered axes. The cut face is drawn in full colour and everything beyond it
  ``SECTION_SHADE`` darker, so a hollow reads at a glance. Cells are cut one by one; a shaped
  part is kept whole when its middle is on the kept side, else left out. A bad axis or an
  ``at`` outside the grid is a ``ValueError``.
- ``zoom_box(picture, frame, lo, hi)`` cuts a picture down to the cells ``lo`` .. ``hi`` (with
  room for studs); in a labelled straight view the left and bottom margins come along, so
  the numbers still read. ``render_zoom(obj, catalog, view, lo, hi, px_per_stud=32,
  grid_shape=None, seed_offset=...)`` draws a seed, Build or Design and zooms it.
None of this changes any picture drawn before.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bricksnap.catalog import SIDE_STUD_BRICK, Catalog
from bricksnap.connect import occupancy
from bricksnap.types import (
    CELL_MM,
    EMPTY,
    FACE_OUT,
    FINISH_STUDS,
    PLATE_MM,
    STUD_MM,
    Build,
    Design,
    Placement,
    Seed,
)

VIEWS = ("front", "right", "back", "left", "top", "iso")
STRAIGHT_VIEWS = VIEWS[:5]
ISO_VIEWS = ("iso", "iso_back")
ALL_VIEWS = VIEWS + ("iso_back",)
PALE = 0.7  # how far parts of earlier steps are blended towards the background

BACKGROUND = (246, 246, 243)
GRID_LINE = (232, 232, 227)
INK = (60, 60, 60)
SEED_GREY = (200, 200, 200)
UNKNOWN_RGB = (255, 0, 255)

PLATE_RATIO = PLATE_MM / STUD_MM  # 0.4
STUD_RADIUS = 0.3  # studs, 4.8 mm diameter
STUD_HEIGHT = 1.7 / PLATE_MM  # plates
DEPTH_FADE = 0.25  # how much darker the far side of the grid is drawn
ISO_DEPTH_FADE = 0.15  # the same in "iso", where the face shading already shows shape
ISO_AZIMUTH = 35.0
ISO_ELEVATION = 30.0

# (axis along picture right, flipped?, axis along picture up, flipped?, depth axis, depth flipped?)
# "flipped" means the coordinate runs from the far end of the grid (n - g instead of g).
_AXES: dict[str, tuple[int, bool, int, bool, int, bool]] = {
    "front": (0, False, 2, False, 1, False),
    "right": (1, False, 2, False, 0, True),
    "back": (0, True, 2, False, 1, True),
    "left": (1, True, 2, False, 0, False),
    "top": (0, False, 1, False, 2, True),
}
_AXIS_NAMES = "xyz"


# ---- frames ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """Where a view puts the grid on the picture.

    ``project`` maps continuous grid coordinates (x, y in studs, z in plates; a cell
    ``(i, j, k)`` spans ``[i, i+1] x [j, j+1] x [k, k+1]``) to picture (column, row) in pixels
    and depth in millimetres (larger is farther from the viewer).
    """

    view: str
    grid_shape: tuple[int, int, int]
    px_per_stud: int
    width: int  # whole picture
    height: int
    left: int  # drawing area: columns [left, left + area_width), rows [top, top + area_height)
    top: int
    area_width: int
    area_height: int
    labels: bool
    matrix: tuple[tuple[float, float, float], ...]  # 3x3, grid -> (col, row, depth)
    offset: tuple[float, float, float]
    camera: tuple[tuple[float, float, float], ...]  # world (mm) right, up, towards viewer
    depth_range_mm: float  # depth of the whole grid along the line of sight

    def project(self, points) -> np.ndarray:
        """(n, 3) grid coordinates -> (n, 3) array of (column, row, depth_mm)."""
        p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        return p @ np.asarray(self.matrix).T + np.asarray(self.offset)

    def cell_center(self, x: float, y: float, z: float) -> tuple[float, float]:
        """Picture (column, row) of the centre of cell (x, y, z)."""
        col, row, _ = self.project([[x + 0.5, y + 0.5, z + 0.5]])[0]
        return float(col), float(row)

    @property
    def straight(self) -> bool:
        return self.view not in ISO_VIEWS


def _vec3(v) -> tuple[float, float, float]:
    return float(v[0]), float(v[1]), float(v[2])


def _mat3(m) -> tuple[tuple[float, float, float], ...]:
    return tuple(_vec3(r) for r in m)


def _check_view(view: str) -> None:
    if view not in ALL_VIEWS:
        raise ValueError(f'Unknown view "{view}". Choose one of: {", ".join(ALL_VIEWS)}.')


def _check_scale(px_per_stud: int) -> None:
    # below 3 a plate (0.4 stud) is under 1.2 pixels tall and some plates would vanish
    if not isinstance(px_per_stud, (int, np.integer)) or px_per_stud < 3:
        raise ValueError(
            f"The picture scale must be a whole number of pixels per stud, 3 or more "
            f"(got {px_per_stud!r})."
        )


def _check_shape(grid_shape) -> tuple[int, int, int]:
    try:
        nx, ny, nz = (int(v) for v in grid_shape)
    except (TypeError, ValueError):
        raise ValueError(
            f"The grid size must be three whole numbers, not {grid_shape!r}."
        ) from None
    if min(nx, ny, nz) < 1:
        raise ValueError(
            f"The grid must be at least one cell in every direction, not {grid_shape}."
        )
    return nx, ny, nz


def _pad(s: int) -> int:
    return math.ceil(s / 4) + 2


def _font(s: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = int(min(13, max(9, round(0.7 * s))))
    return _font_of_size(size)


_FONTS: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _font_of_size(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if size not in _FONTS:
        _FONTS[size] = ImageFont.load_default(size=size)
    return _FONTS[size]


def _text_size(font, text: str) -> tuple[int, int]:
    x0, y0, x1, y1 = font.getbbox(text)
    return int(math.ceil(x1 - min(0, x0))), int(math.ceil(y1))


def _iso_camera() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    az, el = math.radians(ISO_AZIMUTH), math.radians(ISO_ELEVATION)
    towards = np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    right = np.array([math.cos(az), math.sin(az), 0.0])
    up = np.cross(towards, right)
    return right, up, towards


_STRAIGHT_CAMERA = {
    "front": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "right": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "back": ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "left": ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),
    "top": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
}


def _axis_scale(axis: int, s: int) -> float:
    """Pixels per grid unit along a grid axis."""
    return s * (PLATE_RATIO if axis == 2 else 1.0)


def axis_ticks(frame: Frame) -> dict[str, list[tuple[int, float]]]:
    """The labelled ticks of a straight-on view: {"u": [(cell index, column)], "v": [...]}.

    "u" runs along the bottom edge (picture right), "v" along the left edge (picture up);
    the positions are the picture column (for "u") or row (for "v") of the centre of the cell
    whose index is printed there. Iso views have no ticks.
    """
    if not frame.straight:
        return {"u": [], "v": []}
    ua, _, va, _, _, _ = _AXES[frame.view]
    font = _font(frame.px_per_stud)
    out: dict[str, list[tuple[int, float]]] = {}
    for key, axis in (("u", ua), ("v", va)):
        n = frame.grid_shape[axis]
        step = _label_step(axis, n, frame.px_per_stud, font, horizontal=key == "u")
        out[key] = [(i, _cell_pos(frame, key, axis, i)) for i in range(0, n, step)]
    return out


def _cell_pos(frame: Frame, key: str, axis: int, i: int) -> float:
    g = [0.5, 0.5, 0.5]
    g[axis] = i + 0.5
    col, row, _ = frame.project([g])[0]
    return float(col if key == "u" else row)


def _label_step(axis: int, n: int, s: int, font, *, horizontal: bool) -> int:
    pitch = _axis_scale(axis, s)
    if axis == 2:
        candidates = [3, 6, 15, 30, 60, 150, 300, 600]
    else:
        base = 2 if n <= 40 else 5
        candidates = [c for c in (2, 5, 10, 20, 25, 50, 100, 200, 500) if c >= base]
    widest = str(max(0, n - 1))
    tw, th = _text_size(font, widest)
    need = (tw + 4) if horizontal else (th + 2)
    for c in candidates:
        if c * pitch >= need:
            return c
    return candidates[-1]


def view_frame(
    grid_shape: tuple[int, int, int], view: str, *, px_per_stud: int = 16, labels: bool = True
) -> Frame:
    """The frame (picture size and grid-to-picture map) used for this grid and view."""
    _check_view(view)
    _check_scale(px_per_stud)
    nx, ny, nz = _check_shape(grid_shape)
    s = int(px_per_stud)
    n = (nx, ny, nz)
    pad = _pad(s)
    if view in ISO_VIEWS:
        right, up, towards = _iso_camera()
        k = s / STUD_MM
        cell = np.asarray(CELL_MM)
        corners = np.array(
            [[a, b, c] for a in (0, nx) for b in (0, ny) for c in (0, nz + STUD_HEIGHT)],
            dtype=np.float64,
        )
        mm = corners * cell
        cols = k * (mm @ right)
        rows = -k * (mm @ up)
        depth = -(mm @ towards)
        area_w = int(math.ceil(cols.max() - cols.min()))
        area_h = int(math.ceil(rows.max() - rows.min()))
        left = top = pad
        matrix = np.stack([k * right * cell, -k * up * cell, -towards * cell])
        offset = np.array([left - cols.min(), top - rows.min(), -depth.min()])
        if view == "iso_back":
            # the iso picture of the grid turned half a turn: (x, y, z) -> (nx - x, ny - y, z)
            turn = np.diag([-1.0, -1.0, 1.0])
            offset = matrix @ np.array([nx, ny, 0.0]) + offset
            matrix = matrix @ turn
            right, up, towards = (turn @ v for v in (right, up, towards))
        return Frame(
            view=view,
            grid_shape=n,
            px_per_stud=s,
            width=area_w + 2 * pad,
            height=area_h + 2 * pad,
            left=left,
            top=top,
            area_width=area_w,
            area_height=area_h,
            labels=False,
            matrix=_mat3(matrix),
            offset=_vec3(offset),
            camera=_mat3([right, up, towards]),
            depth_range_mm=float(depth.max() - depth.min()),
        )

    ua, uflip, va, vflip, da, dflip = _AXES[view]
    su, sv = _axis_scale(ua, s), _axis_scale(va, s)
    area_w = int(round(n[ua] * su))
    area_h = int(round(n[va] * sv))
    if labels:
        font = _font(s)
        _, th = _text_size(font, "0123456789")
        vw, _ = _text_size(font, str(n[va] - 1))
        uw, _ = _text_size(font, str(n[ua] - 1))
        axis_w, _ = _text_size(font, f"{_AXIS_NAMES[va]} ^")
        left = max(vw + 9, axis_w + 2, uw // 2 + 2) + 2
        top = max(pad, th + 6)
        bottom = 6 + th + 4 + th + 4
        right_m = max(pad, uw // 2 + 3)
    else:
        left = top = right_m = bottom = pad
    matrix = np.zeros((3, 3))
    offset = np.zeros(3)
    # picture column: left + su * (g or n - g)
    matrix[0, ua] = -su if uflip else su
    offset[0] = left + (su * n[ua] if uflip else 0.0)
    # picture row: top + sv * (n - g)  (up is towards smaller rows)
    matrix[1, va] = sv if vflip else -sv
    offset[1] = top + (0.0 if vflip else sv * n[va])
    dmm = CELL_MM[da]
    matrix[2, da] = -dmm if dflip else dmm
    offset[2] = dmm * n[da] if dflip else 0.0
    cam = _STRAIGHT_CAMERA[view]
    return Frame(
        view=view,
        grid_shape=n,
        px_per_stud=s,
        width=left + area_w + right_m,
        height=top + area_h + bottom,
        left=left,
        top=top,
        area_width=area_w,
        area_height=area_h,
        labels=labels,
        matrix=_mat3(matrix),
        offset=_vec3(offset),
        camera=_mat3(cam),
        depth_range_mm=float(n[da] * dmm),
    )


# ---- scenes ------------------------------------------------------------------------------


@dataclass
class _Scene:
    """Which group fills each cell, where exposed studs stand, and each group's colour.

    Parts with a real shape (slopes, round parts) are not in ``cells``: they are triangles in
    ``shape_*``, drawn by the rasteriser and composited with the cells by depth.
    """

    cells: np.ndarray  # int32 [nx, ny, nz]: group index or -1
    studs: np.ndarray  # int32 [nx, ny, nz + 1]: group of the stud standing in that cell, or -1
    rgb: np.ndarray  # (groups, 3) float64
    shape_tris: np.ndarray = field(default_factory=lambda: np.zeros((0, 3, 3)))  # grid coords
    shape_group: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    shape_face: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    shape_normal: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))  # mm, outward
    shape_round: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))  # round side
    # the shaped parts themselves: which part each triangle belongs to, and per part a key
    # for its shape (same part id and rotation), its minimum corner and its footprint
    shape_inst: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    inst_key: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    inst_pos: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int64))
    inst_size: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int64))


# ---- real part shapes --------------------------------------------------------------------

WEDGE_KINDS = ("slope", "curved_slope", "slope_inverted")
ROUND_KINDS = ("round_brick", "round_plate", "round_tile", "dish", "cone")
ROUND_SIDES = 24
ROUND_GAP = 0.02  # studs: round parts are a hair narrower than their footprint
SLOPE_LIP = 0.5  # plates: the height of the low edge of a slope
CURVE_SEGMENTS = 6
STUD_DIAMETER_LDU = 12.0  # a stud on a part lying on its side is drawn in its real size
STUD_HEIGHT_LDU = 4.0
# (height fraction, radius fraction) from the bottom up
_LATHE_PROFILES: dict[str, tuple[tuple[float, float], ...]] = {
    "round_brick": ((0.0, 1.0), (1.0, 1.0)),
    "round_plate": ((0.0, 1.0), (1.0, 1.0)),
    "round_tile": ((0.0, 1.0), (1.0, 1.0)),
    "dish": ((0.0, 1.0), (0.35, 1.0), (0.75, 0.78), (1.0, 0.45)),
    "cone": ((0.0, 1.0), (0.12, 1.0), (1.0, 0.62)),  # the top is as wide as the stud on it
}


@dataclass(frozen=True)
class _Mesh:
    """Triangles of one part in its own box (minimum corner at 0), grid units."""

    tris: np.ndarray  # (n, 3, 3)
    face: np.ndarray  # (n,) which flat (or smoothly curved) face of the part each belongs to
    normal: np.ndarray  # (n, 3) outward unit normals in millimetres
    faces: int  # number of distinct faces
    round_side: np.ndarray  # (n,) bool: part of the curved side of a round part


def _mesh(tris: list, face: list[int], centre, round_faces: tuple[int, ...] = ()) -> _Mesh:
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    cell = np.asarray(CELL_MM)
    mm = t * cell
    n = np.cross(mm[:, 1] - mm[:, 0], mm[:, 2] - mm[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    ok = length[:, 0] > 1e-12
    n = n / np.where(length > 1e-12, length, 1.0)
    out = mm.mean(axis=1) - np.asarray(centre, dtype=np.float64) * cell
    n = np.where(((n * out).sum(axis=1) < 0)[:, None], -n, n)
    f = np.asarray(face, dtype=np.int64)
    side = np.isin(f, np.asarray(round_faces, dtype=np.int64))
    faces = int(f.max()) + 1 if len(f) else 0
    return _Mesh(tris=t[ok], face=f[ok], normal=n[ok], faces=faces, round_side=side[ok])


def _prism(poly: list[tuple[float, float]], tags: list[int], to_xyz, width: float, centre) -> _Mesh:
    """Extrude a convex (t, z) polygon across ``width``; ``to_xyz(t, z, c)`` places a point.

    ``tags[k]`` names the face made by the edge from point k to point k + 1, so that the
    facets of a curve share one face.
    """
    tris: list = []
    face: list[int] = []
    m = len(poly)
    for cap, c in ((0, 0.0), (1, width)):
        pts = [to_xyz(t, z, c) for t, z in poly]
        for k in range(1, m - 1):
            tris.append([pts[0], pts[k], pts[k + 1]])
            face.append(cap)
    for k in range(m):
        (t0, z0), (t1, z1) = poly[k], poly[(k + 1) % m]
        a, b = to_xyz(t0, z0, 0.0), to_xyz(t1, z1, 0.0)
        c, d = to_xyz(t1, z1, width), to_xyz(t0, z0, width)
        tris += [[a, b, c], [a, c, d]]
        face += [2 + tags[k]] * 2
    return _mesh(tris, face, centre)


def _wedge_mesh(catalog: Catalog, p: Placement, kind: str) -> _Mesh | None:
    try:
        low = catalog.low_side(p)
    except ValueError:
        return None
    if low is None or (low[0] != 0) == (low[1] != 0):
        return None
    w, d, h = catalog.footprint(p)
    axis = 0 if low[0] != 0 else 1
    inverted = kind == "slope_inverted"
    length, width = (w, d) if axis == 0 else (d, w)
    # t runs from the thin end of the profile (t = 0) to the full-height end (t = length).
    # A slope is thin at its low side; an inverted slope is thin on the side opposite.
    thin_sign = -low[axis] if inverted else low[axis]

    def to_xyz(t: float, z: float, c: float) -> tuple[float, float, float]:
        a = length - t if thin_sign > 0 else t
        return (a, c, z) if axis == 0 else (c, a, z)

    lip = min(SLOPE_LIP, h / 2)
    if inverted:
        full = 1 if length > 1 else 0
        poly = [(length - full, 0.0), (length, 0.0), (length, h), (0.0, h), (0.0, h - lip)]
        tags = list(range(len(poly)))
    else:
        rows = []
        for sx, sy in catalog.stud_cells(p):
            a = (sx - p.x) if axis == 0 else (sy - p.y)
            rows.append(length - 1 - a if thin_sign > 0 else a)
        run = min(rows) if rows else length
        poly = [(0.0, 0.0), (length, 0.0), (length, float(h))]
        tags = [0, 1, 2]
        if run < length:
            poly.append((float(run), float(h)))
            tags.append(3)
        if kind == "curved_slope" and run > 0:
            curve = []
            for k in range(1, CURVE_SEGMENTS):
                u = 1.0 - k / CURVE_SEGMENTS  # from the top of the curve down
                curve.append((run * u, lip + (h - lip) * (1.0 - (1.0 - u) ** 2)))
            poly += curve
            tags += [4] * len(curve)
            tags[-1 - len(curve)] = 4  # the edge into the curve is part of it
        poly.append((0.0, lip))
        tags.append(5)
    centre = (w / 2, d / 2, h / 2)
    return _prism(poly, tags, to_xyz, float(width), centre)


def _lathe_mesh(w: int, d: int, h: int, kind: str) -> _Mesh:
    profile = _LATHE_PROFILES[kind]
    r0 = min(w, d) / 2 - ROUND_GAP
    cx, cy = w / 2, d / 2
    ang = (np.arange(ROUND_SIDES) + 0.5) * (2 * math.pi / ROUND_SIDES)
    cos, sin = np.cos(ang), np.sin(ang)
    rings = [
        np.stack([cx + rf * r0 * cos, cy + rf * r0 * sin, np.full(ROUND_SIDES, zf * h)], axis=1)
        for zf, rf in profile
    ]
    tris: list = []
    face: list[int] = []
    nxt = np.roll(np.arange(ROUND_SIDES), -1)
    for band in range(len(rings) - 1):
        lo, hi = rings[band], rings[band + 1]
        for j in range(ROUND_SIDES):
            k = nxt[j]
            tris += [[lo[j], lo[k], hi[k]], [lo[j], hi[k], hi[j]]]
            face += [2 + band] * 2
    for cap, ring in ((0, rings[0]), (1, rings[-1])):
        mid = np.array([cx, cy, ring[0, 2]])
        for j in range(ROUND_SIDES):
            tris.append([mid, ring[j], ring[nxt[j]]])
            face.append(cap)
    return _mesh(tris, face, (cx, cy, h / 2), tuple(range(2, 1 + len(rings))))


def _open_underneath(catalog: Catalog, p: Placement) -> list[tuple[int, int]]:
    """The footprint cells of an inverted slope whose bottom is cut away, so that a stud
    under them is not covered (the drawing decides what of it shows). Matches
    ``_wedge_mesh``: only the row at the low side is full height down to the bottom."""
    part = catalog.parts.get(p.part)
    if part is None or part.kind != "slope_inverted":
        return []
    try:
        low = catalog.low_side(p)
        w, d, _ = catalog.footprint(p)
    except ValueError:
        return []
    if low is None or (low[0] != 0) == (low[1] != 0):
        return []
    axis = 0 if low[0] != 0 else 1
    length = (w, d)[axis]
    full = 0 if low[axis] < 0 else length - 1
    return [
        (p.x + i, p.y + j)
        for i in range(w)
        for j in range(d)
        if length == 1 or (i, j)[axis] != full
    ]


def _box_tris(lo, hi) -> tuple[list, list[int]]:
    """The twelve triangles of a box from corner ``lo`` to ``hi``, two per face (faces 0-5)."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    quads = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    tris: list = []
    face: list[int] = []
    for f, (a, b, cc, d) in enumerate(quads):
        tris += [[c[a], c[b], c[cc]], [c[a], c[cc], c[d]]]
        face += [f, f]
    return tris, face


def _sideways_mesh(catalog: Catalog, p: Placement) -> _Mesh | None:
    """A one-stud, one-plate part lying on its side in its column of three cells, its top
    pointing out of ``p.face``, its bottom against the brick behind and centred on the side
    stud (as ``bricksnap.ldraw`` places it)."""
    part = catalog.parts[p.part]
    if p.face not in FACE_OUT or (part.sx, part.sz, part.h) != (1, 1, 1):
        return None
    # the part upright in a 1 x 1 x 1 box (studs and plates): body, and a stud on top if any
    round_faces: tuple[int, ...] = ()
    if part.kind in ROUND_KINDS:
        body = _lathe_mesh(1, 1, 1, part.kind)
        tris = [t for t in body.tris]
        face = body.face.tolist()
        round_faces = tuple(sorted(set(body.face[body.round_side].tolist())))
        faces = body.faces
    else:
        tris, face = _box_tris((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        faces = 6
    if part.studs_top:
        stud = _lathe_mesh(1, 1, 1, "round_tile")
        for t, f in zip(stud.tris, stud.face.tolist(), strict=True):
            if f == 0:  # its bottom lies on the part's top
                continue
            scaled = np.asarray(t, dtype=np.float64).copy()
            scaled[:, :2] = 0.5 + (scaled[:, :2] - 0.5) * (STUD_DIAMETER_LDU / 20.0)
            scaled[:, 2] = 1.0 + scaled[:, 2] * (STUD_HEIGHT_LDU / 8.0)
            tris.append(scaled)
            face.append(faces + f)
        round_faces += (faces + 2,)
    pts = np.asarray(tris, dtype=np.float64).reshape(-1, 3)
    # upright millimetres, centred across, z up from the part's bottom
    up_x = (pts[:, 0] - 0.5) * CELL_MM[0]
    up_y = (pts[:, 1] - 0.5) * CELL_MM[1]
    up_z = pts[:, 2] * CELL_MM[2]
    # on the front face: its top towards -y, its bottom on the back of the column, centred
    # on the stud, which is the side-stud height below the top of the column
    stud_mm = 3 * CELL_MM[2] - catalog.side_stud_height(SIDE_STUD_BRICK) * CELL_MM[2] / 8.0
    fx = up_x / CELL_MM[0] + 0.5
    fy = 1.0 - up_z / CELL_MM[1]
    fz = (stud_mm + up_y) / CELL_MM[2]
    # turned about the column's centre to the face wanted
    dx, dy = fx - 0.5, fy - 0.5
    turn = {"front": (dx, dy), "right": (-dy, dx), "back": (-dx, -dy), "left": (dy, -dx)}
    tx, ty = turn[p.face]
    out = np.stack([tx + 0.5, ty + 0.5, fz], axis=1).reshape(-1, 3, 3)
    centre = out.reshape(-1, 3).min(axis=0) / 2 + out.reshape(-1, 3).max(axis=0) / 2
    if part.studs_top:  # the centre of the body alone, so the stud's faces point outwards
        body_n = len(tris) - sum(1 for f in face if f >= faces)
        flat = out[:body_n].reshape(-1, 3)
        centre = flat.min(axis=0) / 2 + flat.max(axis=0) / 2
    return _mesh(list(out), face, centre, round_faces)


def _part_mesh(catalog: Catalog, p: Placement, cache: dict) -> _Mesh | None:
    """The triangles of a part with a real shape, or None for a part drawn as a box."""
    part = catalog.parts.get(p.part)
    if part is not None and p.face != "top":
        key = (p.part, p.rot % 360, p.face)
        if key not in cache:
            cache[key] = _sideways_mesh(catalog, p)
        return cache[key]
    if part is None or part.kind not in WEDGE_KINDS + ROUND_KINDS:
        return None
    key = (p.part, p.rot % 360)
    if key not in cache:
        if part.kind in WEDGE_KINDS:
            cache[key] = _wedge_mesh(catalog, p, part.kind)
        else:
            w, d, h = catalog.footprint(p)
            cache[key] = _lathe_mesh(w, d, h, part.kind)
    return cache[key]


class _ShapeCollector:
    """Gathers the triangles of shaped parts for a scene."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.cache: dict = {}
        self.tris: list[np.ndarray] = []
        self.group: list[np.ndarray] = []
        self.face: list[np.ndarray] = []
        self.normal: list[np.ndarray] = []
        self.round_side: list[np.ndarray] = []
        self.faces = 0
        self.keys: dict[tuple[str, int, str], int] = {}
        self.inst: list[np.ndarray] = []
        self.inst_key: list[int] = []
        self.inst_pos: list[tuple[int, int, int]] = []
        self.inst_size: list[tuple[int, int, int]] = []

    def add(self, p: Placement, group: int) -> bool:
        """Add the part if it has a real shape; False when it is drawn as a box."""
        mesh = _part_mesh(self.catalog, p, self.cache)
        if mesh is None:
            return False
        self.tris.append(mesh.tris + np.array([p.x, p.y, p.z], dtype=np.float64))
        self.group.append(np.full(len(mesh.tris), group, dtype=np.int64))
        self.face.append(mesh.face + self.faces)
        self.normal.append(mesh.normal)
        self.round_side.append(mesh.round_side)
        self.faces += mesh.faces
        self.inst.append(np.full(len(mesh.tris), len(self.inst_key), dtype=np.int64))
        self.inst_key.append(self.keys.setdefault((p.part, p.rot % 360, p.face), len(self.keys)))
        self.inst_pos.append((p.x, p.y, p.z))
        self.inst_size.append(self.catalog.footprint(p))
        return True

    def into(self, scene: _Scene) -> _Scene:
        if self.tris:
            scene.shape_tris = np.concatenate(self.tris)
            scene.shape_group = np.concatenate(self.group)
            scene.shape_face = np.concatenate(self.face)
            scene.shape_normal = np.concatenate(self.normal)
            scene.shape_round = np.concatenate(self.round_side)
            scene.shape_inst = np.concatenate(self.inst)
            scene.inst_key = np.asarray(self.inst_key, dtype=np.int64)
            scene.inst_pos = np.asarray(self.inst_pos, dtype=np.int64).reshape(-1, 3)
            scene.inst_size = np.asarray(self.inst_size, dtype=np.int64).reshape(-1, 3)
        return scene


def _palette(catalog: Catalog, codes: np.ndarray) -> np.ndarray:
    out = np.empty((len(codes), 3), dtype=np.float64)
    for i, code in enumerate(codes.tolist()):
        c = catalog.colours.get(int(code))
        out[i] = c.rgb if c is not None else UNKNOWN_RGB
    return out


def _build_scene(build: Build, catalog: Catalog, upto_step: int | None) -> _Scene:
    if upto_step is not None:
        build = Build(shape=build.shape, parts=[p for p in build.parts if p.step <= upto_step])
    shape = _check_shape(build.shape)
    occ, _, out_of_bounds, _ = occupancy(build, catalog)
    nx, ny, nz = shape
    studs = np.full((nx, ny, nz + 1), -1, dtype=np.int32)
    cells = occ.astype(np.int32)
    shapes = _ShapeCollector(catalog)
    skip = set(out_of_bounds)
    # which cells cover a stud standing under them: all filled cells but the cut-away
    # bottom of an inverted slope
    covers = occ >= 0
    for i, p in enumerate(build.parts):
        if i in skip:
            continue
        for x, y in _open_underneath(catalog, p):
            if 0 <= x < nx and 0 <= y < ny and 0 <= p.z < nz and occ[x, y, p.z] == i:
                covers[x, y, p.z] = False
    for i, p in enumerate(build.parts):
        part = catalog.parts.get(p.part)
        if part is None or i in skip:
            continue
        if shapes.add(p, i):
            region = cells[catalog.cells(p)]
            region[region == i] = -1
        if not part.studs_top:
            continue
        top = p.z + part.h
        try:
            stud_cells = catalog.stud_cells(p)
        except ValueError:  # a rotation that is not a quarter turn: the checks report it
            continue
        for x, y in stud_cells:
            inside = 0 <= x < nx and 0 <= y < ny and occ[x, y, top - 1] == i
            if inside and (top >= nz or not covers[x, y, top]):
                studs[x, y, top] = i
    codes = np.array([p.color for p in build.parts], dtype=np.int64)
    rgb = _palette(catalog, codes) if len(codes) else np.zeros((0, 3))
    return shapes.into(_Scene(cells=cells, studs=studs, rgb=rgb))


def _design_scene(design: Design, catalog: Catalog) -> _Scene:
    colors = design.colors.astype(np.int64)
    nx, ny, nz = _check_shape(colors.shape)
    filled = colors != EMPTY
    cells = np.full(colors.shape, -1, dtype=np.int32)
    count = int(filled.sum())
    cells[filled] = np.arange(count, dtype=np.int32)
    codes = colors[filled]
    finish = design.finish if design.finish is not None else np.zeros(colors.shape, np.uint8)
    studded = filled & (finish == FINISH_STUDS)
    groups: list[np.ndarray] = [codes]
    # detail parts sit in empty cells on top of the Design
    extra_codes: list[int] = []
    placed: list[tuple[Placement, int]] = []
    for d in design.details:
        if d.part not in catalog.parts:
            continue
        p = Placement(d.part, d.color, d.x, d.y, d.z, d.rot % 360, face=d.face)
        w, dd, h = catalog.footprint(p)
        if d.x < 0 or d.y < 0 or d.z < 0 or d.x + w > nx or d.y + dd > ny or d.z + h > nz:
            continue
        region = cells[catalog.cells(p)]
        if (region >= 0).any():
            continue
        region[...] = count + len(extra_codes)
        placed.append((p, count + len(extra_codes)))
        extra_codes.append(int(d.color))
    if extra_codes:
        groups.append(np.array(extra_codes, dtype=np.int64))
    all_codes = np.concatenate(groups)
    uniq, inverse = np.unique(all_codes, return_inverse=True)
    rgb = _palette(catalog, uniq)[inverse] if len(all_codes) else np.zeros((0, 3))
    studs = np.full((nx, ny, nz + 1), -1, dtype=np.int32)
    # cells that cover a stud under them: all filled cells but the cut-away bottom of an
    # inverted slope detail
    occupied = cells >= 0
    for p, _ in placed:
        for x, y in _open_underneath(catalog, p):
            occupied[x, y, p.z] = False
    above_free = np.ones(colors.shape, dtype=bool)
    above_free[:, :, :-1] = ~occupied[:, :, 1:]
    has = studded & above_free
    xs, ys, zs = np.nonzero(has)
    studs[xs, ys, zs + 1] = cells[xs, ys, zs]
    # detail parts carry their own studs, and those with a real shape leave the cell grid
    shapes = _ShapeCollector(catalog)
    for p, g in placed:
        top = p.z + catalog.footprint(p)[2]
        try:
            stud_cells = catalog.stud_cells(p)
        except ValueError:
            stud_cells = []
        for x, y in stud_cells:
            if top >= nz or not occupied[x, y, top]:
                studs[x, y, top] = g
        if shapes.add(p, g):
            cells[catalog.cells(p)] = -1
    return shapes.into(_Scene(cells=cells, studs=studs, rgb=rgb))


# ---- straight-on views -------------------------------------------------------------------


def _to_view_axes(arr: np.ndarray, view: str) -> np.ndarray:
    """Reorder an [x, y, z] array to [u, v, depth], depth 0 nearest the viewer."""
    ua, uflip, va, vflip, da, dflip = _AXES[view]
    out = np.transpose(arr, (ua, va, da))
    if uflip:
        out = out[::-1, :, :]
    if vflip:
        out = out[:, ::-1, :]
    if dflip:
        out = out[:, :, ::-1]
    return out


def _first_hit(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For an [u, v, depth] group array: the nearest group and its depth index (or -1, inf)."""
    hit = arr >= 0
    first = np.argmax(hit, axis=2)
    ids = np.take_along_axis(arr, first[:, :, None], axis=2)[:, :, 0]
    anyhit = hit.any(axis=2)
    ids = np.where(anyhit, ids, -1)
    depth = np.where(anyhit, first.astype(np.float64), np.inf)
    return ids, depth


def _shade_depth(depth_mm: np.ndarray, frame: Frame, strength: float) -> np.ndarray:
    rng = max(frame.depth_range_mm, 1e-9)
    return 1.0 - strength * np.clip(np.nan_to_num(depth_mm, posinf=0.0) / rng, 0.0, 1.0)


def _render_scene_straight(scene: _Scene, frame: Frame) -> tuple[np.ndarray, np.ndarray]:
    """Colour (H, W, 3) float and group (H, W) int arrays of a straight-on view."""
    view = frame.view
    ua, _, va, _, da, _ = _AXES[view]
    s = frame.px_per_stud
    nu, nv = frame.grid_shape[ua], frame.grid_shape[va]
    su, sv = _axis_scale(ua, s), _axis_scale(va, s)
    depth_mm_per_cell = CELL_MM[da]

    cells = _to_view_axes(scene.cells, view)
    ids2, depth2 = _first_hit(cells)
    if view == "top":
        # the highest stud of each column; it shows unless something stands above its top
        stud_view = _to_view_axes(scene.studs[:, :, 1:], view)  # cell k holds the stud on k
        stud_top, stud_dep = _first_hit(stud_view)
    else:
        sv_arr = _to_view_axes(scene.studs, view)  # [u, v (0..nz), depth]
        sids2, sdepth2 = _first_hit(sv_arr)

    cols = np.arange(frame.width, dtype=np.float64) + 0.5
    rows = np.arange(frame.height, dtype=np.float64) + 0.5
    uf = (cols - frame.left) / su
    vf = nv - (rows - frame.top) / sv
    ui = np.floor(uf).astype(np.int64)
    vi = np.floor(vf).astype(np.int64)
    ufrac = uf - ui
    vfrac = vf - vi
    u_ok = (ui >= 0) & (ui < nu)
    uix = np.where(u_ok, ui, nu)  # nu -> padding (empty)

    ids_p = np.full((nu + 1, nv + 2), -1, dtype=np.int64)
    ids_p[:nu, :nv] = ids2
    dep_p = np.full((nu + 1, nv + 2), np.inf)
    dep_p[:nu, :nv] = depth2
    v_cell_ok = (vi >= 0) & (vi < nv)
    vix = np.where(v_cell_ok, vi, nv + 1)
    group = ids_p[uix[None, :], vix[:, None]]
    depth = dep_p[uix[None, :], vix[:, None]]
    dmm = depth_mm_per_cell
    rgb_table = np.vstack([scene.rgb, np.full((1, 3), BACKGROUND, dtype=np.float64)])
    base = rgb_table[group]
    # depth used for the fade: the centre of the cell, as for a whole cell
    depth_mm = np.where(np.isfinite(depth), (depth + 0.5) * dmm, np.inf)
    near = depth * dmm  # the face nearest the viewer
    shaped = _shapes_straight(scene, frame, depth2)
    if shaped is not None:
        s_id, s_depth, s_rgb = shaped
        win = s_depth < near
        group = np.where(win, s_id, group)
        base = np.where(win[:, :, None], s_rgb, base)
        depth_mm = np.where(win, s_depth + 0.5 * dmm, depth_mm)
        near = np.where(win, s_depth, near)
    stud_px = np.zeros(group.shape, dtype=bool)
    if view == "top":
        st_p = np.full((nu + 1, nv + 2), -1, dtype=np.int64)
        st_p[:nu, :nv] = stud_top
        sdp_p = np.full((nu + 1, nv + 2), np.inf)
        sdp_p[:nu, :nv] = stud_dep
        sg = st_p[uix[None, :], vix[:, None]]
        sd = sdp_p[uix[None, :], vix[:, None]]
        stud_here = (sg >= 0) & ((sd - STUD_HEIGHT) * dmm < near)
        r2 = (ufrac[None, :] - 0.5) ** 2 + (vfrac[:, None] - 0.5) ** 2
        ring = stud_here & (r2 <= STUD_RADIUS**2) & (r2 > (STUD_RADIUS * 0.72) ** 2)
        disc = stud_here & (r2 <= (STUD_RADIUS * 0.72) ** 2)
        stud_px = ring | disc
    else:
        sid_p = np.full((nu + 1, nv + 2), -1, dtype=np.int64)
        sid_p[:nu, : nv + 1] = sids2
        sdep_p = np.full((nu + 1, nv + 2), np.inf)
        sdep_p[:nu, : nv + 1] = sdepth2
        v_stud_ok = (vi >= 0) & (vi <= nv)
        vsx = np.where(v_stud_ok, vi, nv + 1)
        sg = sid_p[uix[None, :], vsx[:, None]]
        sd = sdep_p[uix[None, :], vsx[:, None]]
        in_shape = (np.abs(ufrac - 0.5) < STUD_RADIUS)[None, :] & (vfrac < STUD_HEIGHT)[:, None]
        stud_px = in_shape & (sg >= 0) & ((sd + 0.5 - STUD_RADIUS) * dmm < near)
    group = np.where(stud_px, sg, group)
    base = np.where(stud_px[:, :, None], rgb_table[np.where(stud_px, sg, -1)], base)
    depth_mm = np.where(stud_px, (sd + 0.5) * dmm, depth_mm)

    shade = _shade_depth(depth_mm, frame, DEPTH_FADE)
    color = base * shade[:, :, None]
    if view == "top":
        color = np.where(disc[:, :, None], _lighten(color, 0.18), color)
        color = np.where(ring[:, :, None], color * 0.78, color)
    else:
        color = np.where(stud_px[:, :, None], _lighten(color, 0.12), color)
    bg = group < 0
    color[bg] = BACKGROUND
    _grid_lines(color, bg, frame)
    return color, group


def _straight_face_rgb(rgb: np.ndarray, normal: np.ndarray, facing: np.ndarray, view: str):
    """Colour of the faces of shaped parts in a straight-on view, before the depth fade.

    Faces square to the viewer keep the part's colour exactly, like a box part. Seen from
    above, a slanted face is darker the steeper it is (and, see ``_shapes_straight``, darker
    still towards its low edge); seen from the side, a face that tilts up is lighter and one
    that tilts down darker, and curved sides darken towards their rim.
    """
    out = rgb.copy()
    tilted = facing <= 0.999
    if view == "top":
        out[tilted] = rgb[tilted] * (0.6 + 0.3 * facing[tilted, None])
        return out
    up = normal[:, 2]
    f = 0.75 + 0.25 * facing
    c = rgb * f[:, None]
    c = np.where((up > 0.01)[:, None], _lighten(c, 0.3 * np.clip(up, 0, 1)[:, None]), c)
    c = np.where((up < -0.01)[:, None], c * (1.0 + 0.35 * np.clip(up, -1, 0))[:, None], c)
    out[tilted] = c[tilted]
    return out


def _hidden_parts(scene: _Scene, view: str, box_depth: np.ndarray) -> np.ndarray:
    """Shaped parts that certainly do not show in a straight-on view, so need not be drawn.

    A part is hidden (a) behind an identical part (same id and rotation) at the same place in
    the picture and nearer the viewer, which covers exactly the same pixels; or (b) when box
    cells nearer than its nearest face fill every cell of its rectangle in the picture.
    ``box_depth`` [u, v] is the depth index of the nearest box cell (inf where none).
    Leaving these parts out changes no pixel; it keeps walls of round parts fast.
    """
    m = len(scene.inst_key)
    hidden = np.zeros(m, dtype=bool)
    if m == 0:
        return hidden
    ua, uflip, va, vflip, da, dflip = _AXES[view]
    n = scene.cells.shape
    pos, size = scene.inst_pos, scene.inst_size

    def span(axis: int, flip: bool) -> tuple[np.ndarray, np.ndarray]:
        lo, hi = pos[:, axis], pos[:, axis] + size[:, axis]
        return (n[axis] - hi, n[axis] - lo) if flip else (lo, hi)

    u0, u1 = span(ua, uflip)
    v0, v1 = span(va, vflip)
    d0, _ = span(da, dflip)
    # (a) identical parts in a line along the view: all but the nearest are hidden
    order = np.lexsort((d0, v0, u0, scene.inst_key))
    k, uu, vv, dd = scene.inst_key[order], u0[order], v0[order], d0[order]
    starts = np.ones(m, dtype=bool)
    starts[1:] = (k[1:] != k[:-1]) | (uu[1:] != uu[:-1]) | (vv[1:] != vv[:-1])
    first = np.maximum.accumulate(np.where(starts, np.arange(m), 0))
    hidden[order] = dd > dd[first]
    # (b) a part with box cells in front of all of it
    for i in np.nonzero(~hidden)[0].tolist():
        block = box_depth[u0[i] : u1[i], v0[i] : v1[i]]
        if block.size and block.max() < d0[i]:
            hidden[i] = True
    return hidden


def _shapes_straight(scene: _Scene, frame: Frame, box_depth: np.ndarray | None = None):
    """Rasterise the shaped parts of a straight-on view.

    Returns (outline group, depth in mm or inf, colour before the depth fade) per pixel, or
    None when there are no shaped parts. Faces square to the viewer, and the curved side of a
    round part seen from the side, take the part's group, so they outline like a box; other
    faces get a group of their own, so the crease between a flat top and a slanted face (or
    the rim of a cone seen from above) is outlined.
    """
    if len(scene.shape_tris) == 0:
        return None
    towards = np.asarray(frame.camera[2], dtype=np.float64)
    facing = scene.shape_normal @ towards
    keep = facing > 1e-6
    if box_depth is not None:
        keep &= ~_hidden_parts(scene, frame.view, box_depth)[scene.shape_inst]
    tris = scene.shape_tris[keep]
    groups = scene.shape_group[keep]
    facing = facing[keep]
    plain = facing > 0.999
    if frame.view != "top":  # the side of a round part outlines like a box from the side
        plain = plain | scene.shape_round[keep]
    ids = np.where(plain, groups, len(scene.rgb) + scene.shape_face[keep])
    if len(ids) == 0:
        return None
    rgb = _straight_face_rgb(scene.rgb[groups], scene.shape_normal[keep], facing, frame.view)
    pic = frame.project(tris.reshape(-1, 3)).reshape(-1, 3, 3)
    index, zbuf = _rasterise(pic, frame.width, frame.height)
    hit = index >= 0
    safe = np.where(hit, index, 0)
    colour = rgb[safe]
    if frame.view == "top":
        # a slanted face darkens from its high edge down to its low edge, so the direction
        # it falls in can be read from above
        top = np.full(len(scene.rgb), -np.inf)
        bottom = np.full(len(scene.rgb), np.inf)
        np.maximum.at(top, groups, tris[:, :, 2].max(axis=1))
        np.minimum.at(bottom, groups, tris[:, :, 2].min(axis=1))
        g = groups[safe]
        z = frame.grid_shape[2] - zbuf / CELL_MM[2]  # height of the surface at the pixel
        frac = np.clip((top[g] - z) / np.maximum(top[g] - bottom[g], 1e-9), 0.0, 1.0)
        slanted = hit & (facing[safe] <= 0.999)
        colour = np.where(slanted[:, :, None], colour * (1.0 - 0.3 * frac)[:, :, None], colour)
    return np.where(hit, ids[safe], -1), zbuf, colour


def _lighten(color: np.ndarray, amount: float | np.ndarray) -> np.ndarray:
    return color + (255.0 - color) * amount


def _grid_lines(color: np.ndarray, bg: np.ndarray, frame: Frame) -> None:
    """Faint lines in empty space at every stud and every brick course."""
    ua, _, va, _, _, _ = _AXES[frame.view]
    for key, axis in (("u", ua), ("v", va)):
        n = frame.grid_shape[axis]
        step = 3 if axis == 2 else 1
        for i in range(0, n + 1, step):
            g = [0.0, 0.0, 0.0]
            g[axis] = float(i)
            col, row, _ = frame.project([g])[0]
            if key == "u":
                c = int(math.floor(col))
                c = min(c, frame.left + frame.area_width - 1)
                lo, hi = frame.top, frame.top + frame.area_height
                sel = bg[lo:hi, c]
                color[lo:hi, c][sel] = GRID_LINE
            else:
                r = int(math.floor(row))
                r = min(r, frame.top + frame.area_height - 1)
                lo, hi = frame.left, frame.left + frame.area_width
                sel = bg[r, lo:hi]
                color[r, lo:hi][sel] = GRID_LINE


# ---- triangle rasteriser -----------------------------------------------------------------

_CHUNK = 600_000


def _rasterise(tris: np.ndarray, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    """Z-buffer triangles given in picture space (n, 3, [col, row, depth]).

    Returns (index of the nearest triangle per pixel or -1, its depth or inf). Pixels are
    sampled at their centres; ties go to the lower triangle index.
    """
    index = np.full(height * width, -1, dtype=np.int64)
    zbuf = np.full(height * width, np.inf)
    if len(tris) == 0:
        return index.reshape(height, width), zbuf.reshape(height, width)
    u = tris[:, :, 0]
    v = tris[:, :, 1]
    d = tris[:, :, 2]
    area = (u[:, 1] - u[:, 0]) * (v[:, 2] - v[:, 0]) - (u[:, 2] - u[:, 0]) * (v[:, 1] - v[:, 0])
    c0 = np.maximum(np.ceil(u.min(axis=1) - 0.5), 0).astype(np.int64)
    c1 = np.minimum(np.floor(u.max(axis=1) - 0.5), width - 1).astype(np.int64)
    r0 = np.maximum(np.ceil(v.min(axis=1) - 0.5), 0).astype(np.int64)
    r1 = np.minimum(np.floor(v.max(axis=1) - 0.5), height - 1).astype(np.int64)
    w = c1 - c0 + 1
    h = r1 - r0 + 1
    keep = (np.abs(area) > 1e-12) & (w > 0) & (h > 0)
    idx = np.nonzero(keep)[0]
    if len(idx) == 0:
        return index.reshape(height, width), zbuf.reshape(height, width)
    # barycentric weights as linear functions of the pixel position: b_i = A_i*x + B_i*y + C_i
    ia = 1.0 / area[idx]
    ui, vi, di = u[idx], v[idx], d[idx]
    coeff = []
    for i in range(3):
        j, k = (i + 1) % 3, (i + 2) % 3
        a = (vi[:, j] - vi[:, k]) * ia
        b = (ui[:, k] - ui[:, j]) * ia
        c = (ui[:, j] * vi[:, k] - ui[:, k] * vi[:, j]) * ia
        coeff.append((a, b, c))
    da = sum(coeff[i][0] * di[:, i] for i in range(3))
    db = sum(coeff[i][1] * di[:, i] for i in range(3))
    dc = sum(coeff[i][2] * di[:, i] for i in range(3))
    lowest = np.empty(height * width, dtype=np.int64)  # scratch: lowest winning index
    counts = (w[idx] * h[idx]).astype(np.int64)
    ends = np.cumsum(counts)
    starts = ends - counts
    t0 = 0
    n = len(idx)
    while t0 < n:
        limit = starts[t0] + _CHUNK
        t1 = int(np.searchsorted(ends, limit, side="right"))
        t1 = max(t1, t0 + 1)
        sel = np.arange(t0, t1)
        cnt = counts[sel]
        tot = int(cnt.sum())
        local_t = np.repeat(sel, cnt)
        k = np.arange(tot, dtype=np.int64) - np.repeat(starts[sel] - starts[t0], cnt)
        ww = w[idx][local_t]
        px = c0[idx][local_t] + k % ww
        py = r0[idx][local_t] + k // ww
        fx = px + 0.5
        fy = py + 0.5
        inside = np.ones(tot, dtype=bool)
        for a, b, c in coeff:
            inside &= a[local_t] * fx + b[local_t] * fy + c[local_t] >= -1e-9
        lt = local_t[inside]
        pix = py[inside] * width + px[inside]
        dep = da[lt] * fx[inside] + db[lt] * fy[inside] + dc[lt]
        tri = idx[lt]
        # the nearest sample of this chunk per pixel wins if it is strictly nearer than what
        # earlier (lower-numbered) triangles left; among equally near ones the lowest index
        before = zbuf[pix]
        np.fmin.at(zbuf, pix, dep)  # fmin: a NaN depth never wins
        win = (dep == zbuf[pix]) & (dep < before)
        if win.any():
            wp, wt = pix[win], tri[win]
            lowest[wp] = np.iinfo(np.int64).max
            np.minimum.at(lowest, wp, wt)
            index[wp] = lowest[wp]
        t0 = t1
    return index.reshape(height, width), zbuf.reshape(height, width)


def _quads_to_tris(quads: np.ndarray) -> np.ndarray:
    """(n, 4, 3) quads -> (2n, 3, 3) triangles, the two halves of quad i at 2i and 2i+1."""
    a = quads[:, [0, 1, 2], :]
    b = quads[:, [0, 2, 3], :]
    return np.stack([a, b], axis=1).reshape(-1, 3, 3)


# ---- iso view of a scene -----------------------------------------------------------------

_FACE_TOP, _FACE_FRONT, _FACE_RIGHT, _FACE_STUD = 0, 1, 2, 3
_FACE_SHADE = {_FACE_TOP: None, _FACE_FRONT: 0.86, _FACE_RIGHT: 0.68}


def _render_scene_iso(scene: _Scene, frame: Frame) -> tuple[np.ndarray, np.ndarray]:
    cells = scene.cells
    filled = cells >= 0
    nx, ny, nz = cells.shape
    quads: list[np.ndarray] = []
    groups: list[np.ndarray] = []
    colours: list[np.ndarray] = []

    def add(mask: np.ndarray, corners: np.ndarray, face: int) -> None:
        xs, ys, zs = np.nonzero(mask)
        if len(xs) == 0:
            return
        base = np.stack([xs, ys, zs], axis=1).astype(np.float64)
        quads.append(base[:, None, :] + corners[None, :, :])
        g = cells[xs, ys, zs].astype(np.int64)
        groups.append(g * 4 + face)
        rgb = scene.rgb[g]
        shade = _FACE_SHADE[face]
        colours.append(_lighten(rgb, 0.12) if shade is None else rgb * shade)

    free_above = np.ones_like(filled)
    free_above[:, :, :-1] = ~filled[:, :, 1:]
    free_front = np.ones_like(filled)
    free_front[:, 1:, :] = ~filled[:, :-1, :]
    free_right = np.ones_like(filled)
    free_right[:-1, :, :] = ~filled[1:, :, :]
    add(
        filled & free_above,
        np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=np.float64),
        _FACE_TOP,
    )
    add(
        filled & free_front,
        np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], dtype=np.float64),
        _FACE_FRONT,
    )
    add(
        filled & free_right,
        np.array([[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 1]], dtype=np.float64),
        _FACE_RIGHT,
    )
    tris = [_quads_to_tris(q) for q in quads]
    tri_group = [np.repeat(g, 2) for g in groups]
    tri_rgb = [np.repeat(c, 2, axis=0) for c in colours]

    # studs: short octagonal posts
    sx, sy, sz = np.nonzero(scene.studs >= 0)
    if len(sx):
        g = scene.studs[sx, sy, sz].astype(np.int64)
        ang = (np.arange(8) + 0.5) * (2 * math.pi / 8)
        ring = np.stack([STUD_RADIUS * np.cos(ang), STUD_RADIUS * np.sin(ang)], axis=1)
        centre = np.stack([sx + 0.5, sy + 0.5, sz.astype(np.float64)], axis=1)
        top_z = centre[:, 2] + STUD_HEIGHT
        # top: fan of 6 triangles
        fan = np.array([[0, i, i + 1] for i in range(1, 7)])
        ring_top = np.concatenate(
            [
                centre[:, None, :2] + ring[None, :, :],
                np.broadcast_to(top_z[:, None, None], (len(sx), 8, 1)),
            ],
            axis=2,
        )
        top_tris = ring_top[:, fan, :].reshape(-1, 3, 3)
        ring_bot = ring_top.copy()
        ring_bot[:, :, 2] = centre[:, None, 2]
        side_quads = np.stack(
            [
                ring_bot,
                np.roll(ring_bot, -1, axis=1),
                np.roll(ring_top, -1, axis=1),
                ring_top,
            ],
            axis=2,
        ).reshape(-1, 4, 3)
        side_tris = _quads_to_tris(side_quads)
        base = scene.rgb[g]
        tris += [top_tris, side_tris]
        tri_group += [np.repeat(g * 4 + _FACE_STUD, 6), np.repeat(g * 4 + _FACE_STUD, 16)]
        # side j faces the direction half-way between corners j and j+1; light from the left
        side_dir = ang + math.pi / 8
        side_shade = 0.62 + 0.3 * np.cos(side_dir - math.radians(200))
        side_col = base[:, None, :] * np.repeat(side_shade, 2)[None, :, None]
        tri_rgb += [np.repeat(_lighten(base, 0.2), 6, axis=0), side_col.reshape(-1, 3)]

    # shaped parts: their own triangles, the faces turned away from the viewer left out
    if len(scene.shape_tris):
        towards = np.asarray(frame.camera[2], dtype=np.float64)
        keep = scene.shape_normal @ towards > 1e-6
        g = scene.shape_group[keep]
        tris.append(scene.shape_tris[keep])
        tri_group.append(4 * len(scene.rgb) + scene.shape_face[keep])
        tri_rgb.append(_iso_face_rgb(scene.rgb[g], scene.shape_normal[keep]))

    return _draw_tris(tris, tri_group, tri_rgb, frame, depth_fade=ISO_DEPTH_FADE)


# multiplier and added white for faces looking along +z, -z, -y, +y, +x, -x; the box faces
# of the cell scene use the same values (lighter top, front 0.86, right side 0.68)
_ISO_LIGHT = {
    "up": (0.88, 0.12),
    "down": (0.5, 0.0),
    "front": (0.86, 0.0),
    "back": (0.6, 0.0),
    "right": (0.68, 0.0),
    "left": (0.6, 0.0),
}


def _iso_face_rgb(rgb: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Face shading of shaped parts in "iso": a blend of the box face shades by direction,
    with tilted faces a little lighter so a slope stands out from both top and front."""
    nx_, ny_, nz_ = normal[:, 0], normal[:, 1], normal[:, 2]
    parts = (
        (np.clip(nz_, 0, None), "up"),
        (np.clip(-nz_, 0, None), "down"),
        (np.clip(-ny_, 0, None), "front"),
        (np.clip(ny_, 0, None), "back"),
        (np.clip(nx_, 0, None), "right"),
        (np.clip(-nx_, 0, None), "left"),
    )
    mul = np.zeros(len(normal))
    add = np.zeros(len(normal))
    for weight, key in parts:
        m, a = _ISO_LIGHT[key]
        mul += weight**2 * m
        add += weight**2 * a
    tilted = (np.abs(normal).max(axis=1) < 0.999) & (nz_ > 0.01)
    add = add + np.where(tilted, 0.1 * nz_, 0.0)
    mul = mul * (1.0 - np.where(tilted, 0.1 * nz_, 0.0))
    return rgb * mul[:, None] + 255.0 * add[:, None]


def _draw_tris(
    tris: list[np.ndarray],
    tri_group: list[np.ndarray],
    tri_rgb: list[np.ndarray],
    frame: Frame,
    *,
    depth_fade: float,
) -> tuple[np.ndarray, np.ndarray]:
    if tris:
        all_tris = np.concatenate(tris).astype(np.float64)
        groups = np.concatenate(tri_group).astype(np.int64)
        rgb = np.concatenate(tri_rgb).astype(np.float64)
    else:
        all_tris = np.zeros((0, 3, 3))
        groups = np.zeros(0, dtype=np.int64)
        rgb = np.zeros((0, 3))
    pic = frame.project(all_tris.reshape(-1, 3)).reshape(-1, 3, 3)
    index, zbuf = _rasterise(pic, frame.width, frame.height)
    hit = index >= 0
    safe = np.where(hit, index, 0)
    if len(groups):
        group = np.where(hit, groups[safe], -1)
        color = rgb[safe]
    else:
        group = np.full(index.shape, -1, dtype=np.int64)
        color = np.zeros(index.shape + (3,))
    if depth_fade:
        color = color * _shade_depth(np.where(hit, zbuf, 0.0), frame, depth_fade)[:, :, None]
    color[~hit] = BACKGROUND
    if frame.straight:
        _grid_lines(color, ~hit, frame)
    return color, group


# ---- outlines, labels, finishing --------------------------------------------------------


def _outline(color: np.ndarray, group: np.ndarray) -> np.ndarray:
    """Darken a one-pixel line wherever the group changes (between parts, and around them)."""
    g = group
    edge = np.zeros(g.shape, dtype=bool)
    filled = g >= 0
    edge[:, 1:] |= (g[:, 1:] != g[:, :-1]) & filled[:, 1:]
    edge[1:, :] |= (g[1:, :] != g[:-1, :]) & filled[1:, :]
    edge[:, :-1] |= filled[:, :-1] & ~filled[:, 1:]
    edge[:-1, :] |= filled[:-1, :] & ~filled[1:, :]
    out = color.copy()
    c = color[edge]
    dark = c.max(axis=1) < 80  # black, dark brown, dark green: a lighter line shows better
    c_out = np.where(dark[:, None], c + (255.0 - c) * 0.4, c * 0.55)
    out[edge] = c_out
    return out


def _to_image(color: np.ndarray) -> Image.Image:
    arr = np.clip(np.rint(color), 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


@dataclass(frozen=True)
class Label:
    """One piece of text in the label margin of a straight-on view."""

    text: str
    kind: str  # "u" / "v": a number at a tick; "u-axis" / "v-axis": an axis title
    x: float  # where the text is drawn (top-left corner, as given to Pillow)
    y: float
    at: int | None  # picture column ("u") or row ("v") of the tick it labels; None for titles


def label_texts(frame: Frame) -> list[Label]:
    """Every text printed in the margins of this view, in drawing order (none in iso or
    without labels). Numbers are the cell indices from ``axis_ticks``, z in plates."""
    if not frame.labels or not frame.straight:
        return []
    font = _font(frame.px_per_stud)
    ua, uflip, va, _, _, _ = _AXES[frame.view]
    x_lo, x_hi = frame.left, frame.left + frame.area_width - 1
    y_hi = frame.top + frame.area_height - 1
    _, th = _text_size(font, "0123456789")
    ticks = axis_ticks(frame)
    out: list[Label] = []
    for i, pos in ticks["u"]:
        p = int(math.floor(pos))
        text = str(i)
        tw, _ = _text_size(font, text)
        out.append(Label(text, "u", p - tw / 2 + 0.5, y_hi + 7, p))
    for i, pos in ticks["v"]:
        p = int(math.floor(pos))
        text = str(i)
        tw, _ = _text_size(font, text)
        out.append(Label(text, "v", x_lo - 9 - tw, p - th / 2 - 1, p))
    uname = _AXIS_NAMES[ua]
    utext = f"<- {uname}" if uflip else f"{uname} ->"
    tw, _ = _text_size(font, utext)
    out.append(Label(utext, "u-axis", (x_lo + x_hi) / 2 - tw / 2, y_hi + 7 + th + 4, None))
    vtext = f"{_AXIS_NAMES[va]} ^"
    out.append(Label(vtext, "v-axis", 2, max(1, frame.top - th - 5), None))
    return out


def _draw_labels(img: Image.Image, frame: Frame) -> None:
    if not frame.labels or not frame.straight:
        return
    draw = ImageDraw.Draw(img)
    font = _font(frame.px_per_stud)
    ua, _, va, _, _, _ = _AXES[frame.view]
    x_lo, x_hi = frame.left, frame.left + frame.area_width - 1
    y_lo, y_hi = frame.top, frame.top + frame.area_height - 1
    # frame lines along the bottom and left of the drawing area
    draw.line([(x_lo - 1, y_hi + 1), (x_hi, y_hi + 1)], fill=INK)
    draw.line([(x_lo - 1, y_lo), (x_lo - 1, y_hi + 1)], fill=INK)
    # minor ticks every cell, and every brick course on z
    for key, axis in (("u", ua), ("v", va)):
        for i in range(frame.grid_shape[axis]):
            pos = _cell_pos(frame, key, axis, i)
            p = int(math.floor(pos))
            length = 4 if (axis == 2 and i % 3 == 0) else 2
            if key == "u":
                draw.line([(p, y_hi + 2), (p, y_hi + 1 + length)], fill=INK)
            else:
                draw.line([(x_lo - 1 - length, p), (x_lo - 2, p)], fill=INK)
    labels = label_texts(frame)
    # long ticks at the numbered cells
    for lab in labels:
        if lab.kind == "u" and lab.at is not None:
            draw.line([(lab.at, y_hi + 2), (lab.at, y_hi + 6)], fill=INK)
        elif lab.kind == "v" and lab.at is not None:
            draw.line([(x_lo - 7, lab.at), (x_lo - 2, lab.at)], fill=INK)
    for lab in labels:
        draw.text((lab.x, lab.y), lab.text, fill=INK, font=font)


def _finish(color: np.ndarray, group: np.ndarray, frame: Frame) -> Image.Image:
    img = _to_image(_outline(color, group))
    _draw_labels(img, frame)
    return img


def _render_scene(scene: _Scene, frame: Frame) -> Image.Image:
    color, group = _scene_pixels(scene, frame)
    return _finish(color, group, frame)


def _scene_pixels(scene: _Scene, frame: Frame) -> tuple[np.ndarray, np.ndarray]:
    """Colour (H, W, 3) and group (H, W) arrays of a scene in any view, before outlines."""
    if frame.straight:
        return _render_scene_straight(scene, frame)
    if frame.view == "iso_back":
        return _render_scene_iso(_turned_scene(scene), _iso_twin(frame))
    return _render_scene_iso(scene, frame)


def _iso_twin(frame: Frame) -> Frame:
    """The "iso" frame that draws a turned-round scene for an "iso_back" frame."""
    return view_frame(frame.grid_shape, "iso", px_per_stud=frame.px_per_stud, labels=False)


def _turned_scene(scene: _Scene) -> _Scene:
    """The scene turned half a turn about the vertical line through the grid's centre."""
    nx, ny, _ = scene.cells.shape
    tris = scene.shape_tris.copy()
    tris[..., 0] = nx - tris[..., 0]
    tris[..., 1] = ny - tris[..., 1]
    normal = scene.shape_normal * np.array([-1.0, -1.0, 1.0])
    pos = scene.inst_pos.copy()
    if len(pos):
        pos[:, 0] = nx - pos[:, 0] - scene.inst_size[:, 0]
        pos[:, 1] = ny - pos[:, 1] - scene.inst_size[:, 1]
    return _Scene(
        cells=np.ascontiguousarray(scene.cells[::-1, ::-1, :]),
        studs=np.ascontiguousarray(scene.studs[::-1, ::-1, :]),
        rgb=scene.rgb,
        shape_tris=tris,
        shape_group=scene.shape_group,
        shape_face=scene.shape_face,
        shape_normal=normal,
        shape_round=scene.shape_round,
        shape_inst=scene.shape_inst,
        inst_key=scene.inst_key,
        inst_pos=pos,
        inst_size=scene.inst_size,
    )


def _pixel_owner(scene: _Scene, group: np.ndarray, frame: Frame) -> np.ndarray:
    """(H, W) index into the scene's groups (a Build's kept parts) of the part that each
    pixel shows, or -1 for the background. Decodes the group numbers the drawing uses:
    shaped faces are numbered after the parts, and "iso" numbers box faces 4 to a part."""
    n = len(scene.rgb)
    face_part = np.full(int(scene.shape_face.max()) + 1 if len(scene.shape_face) else 0, -1)
    face_part[scene.shape_face] = scene.shape_group
    per_part = 1 if frame.straight else 4
    owner = np.full(group.shape, -1, dtype=np.int64)
    boxes = (group >= 0) & (group < per_part * n)
    owner[boxes] = group[boxes] // per_part
    faces = group >= per_part * n
    owner[faces] = face_part[group[faces] - per_part * n]
    return owner


# ---- public API ----------------------------------------------------------------------------


def render_build(
    build: Build,
    catalog: Catalog,
    view: str,
    *,
    px_per_stud: int = 16,
    labels: bool = True,
    upto_step: int | None = None,
    highlight_step: int | None = None,
) -> Image.Image:
    """A picture of a Build from one view (see the module docstring).

    With ``highlight_step`` the parts of earlier steps are drawn pale."""
    if highlight_step is None:
        frame = view_frame(build.shape, view, px_per_stud=px_per_stud, labels=labels)
        return _render_scene(_build_scene(build, catalog, upto_step), frame)
    return render_build_map(
        build,
        catalog,
        view,
        px_per_stud=px_per_stud,
        labels=labels,
        upto_step=upto_step,
        highlight_step=highlight_step,
    )[0]


def render_build_map(
    build: Build,
    catalog: Catalog,
    view: str,
    *,
    px_per_stud: int = 16,
    labels: bool = True,
    upto_step: int | None = None,
    highlight_step: int | None = None,
) -> tuple[Image.Image, np.ndarray]:
    """``render_build`` and ``part_map`` of the same picture, drawn once."""
    frame = view_frame(build.shape, view, px_per_stud=px_per_stud, labels=labels)
    scene = _build_scene(build, catalog, upto_step)
    color, group = _scene_pixels(scene, frame)
    owner = _pixel_owner(scene, group, frame)
    idx, kept = _kept(build, upto_step)
    if highlight_step is not None:
        steps = np.array([p.step for p in kept], dtype=np.int64)
        pale = owner >= 0
        pale[pale] = steps[owner[pale]] < highlight_step
        bg = np.asarray(BACKGROUND, dtype=np.float64)
        color[pale] = color[pale] + (bg - color[pale]) * PALE
    return _finish(color, group, frame), np.asarray(idx + [-1], dtype=np.int64)[owner]


def _kept(build: Build, upto_step: int | None) -> tuple[list[int], list[Placement]]:
    """The indices and parts ``_build_scene`` draws, in its order."""
    idx = [i for i, p in enumerate(build.parts) if upto_step is None or p.step <= upto_step]
    return idx, [build.parts[i] for i in idx]


def part_map(
    build: Build,
    catalog: Catalog,
    view: str,
    upto_step: int | None = None,
    *,
    px_per_stud: int = 8,
    labels: bool = False,
) -> np.ndarray:
    """(H, W) array the size of ``render_build`` with the same arguments: the index into
    ``build.parts`` of the part each pixel shows (its studs included), or -1."""
    frame = view_frame(build.shape, view, px_per_stud=px_per_stud, labels=labels)
    scene = _build_scene(build, catalog, upto_step)
    _, group = _scene_pixels(scene, frame)
    owner = _pixel_owner(scene, group, frame)
    idx = np.asarray(_kept(build, upto_step)[0] + [-1], dtype=np.int64)
    return idx[owner]  # owner -1 picks the -1 at the end


def part_pixels(
    build: Build,
    catalog: Catalog,
    view: str,
    upto_step: int | None = None,
    *,
    px_per_stud: int = 8,
) -> dict[int, int]:
    """How many pixels of the picture (no labels) each part covers, by index into
    ``build.parts``; parts that do not show at all are left out."""
    m = part_map(build, catalog, view, upto_step, px_per_stud=px_per_stud)
    counts = np.bincount(m[m >= 0], minlength=len(build.parts))
    return {i: int(c) for i, c in enumerate(counts.tolist()) if c > 0}


def part_pixels_views(
    build: Build,
    catalog: Catalog,
    views: Sequence[str],
    upto_step: int | None = None,
    *,
    px_per_stud: int = 8,
) -> dict[str, dict[int, int]]:
    """``part_pixels`` for each of ``views``, in that order, with the scene made once."""
    scene = _build_scene(build, catalog, upto_step)
    idx = np.asarray(_kept(build, upto_step)[0] + [-1], dtype=np.int64)
    out: dict[str, dict[int, int]] = {}
    for view in views:
        frame = view_frame(build.shape, view, px_per_stud=px_per_stud, labels=False)
        _, group = _scene_pixels(scene, frame)
        m = idx[_pixel_owner(scene, group, frame)]
        counts = np.bincount(m[m >= 0], minlength=len(build.parts))
        out[view] = {i: int(c) for i, c in enumerate(counts.tolist()) if c > 0}
    return out


def visible_parts(
    build: Build,
    catalog: Catalog,
    view: str,
    upto_step: int | None = None,
    *,
    px_per_stud: int = 8,
    min_pixels: int = 4,
) -> set[int]:
    """Indices into ``build.parts`` of the parts of which at least ``min_pixels`` show."""
    counts = part_pixels(build, catalog, view, upto_step, px_per_stud=px_per_stud)
    return {i for i, c in counts.items() if c >= min_pixels}


def render_part(part_id: str, colour: int, catalog: Catalog, px_per_stud: int = 24) -> Image.Image:
    """One part alone on a light background, three-quarter view, in its real shape."""
    part = catalog.parts.get(part_id)
    if part is None:
        raise ValueError(f'There is no part "{part_id}" in the parts table.')
    _check_scale(px_per_stud)
    one = Build((part.sx, part.sz, part.h), [Placement(part_id, colour, 0, 0, 0, 0, 1)])
    return render_build(one, catalog, "iso", px_per_stud=px_per_stud, labels=False)


def render_design(
    design: Design, catalog: Catalog, view: str, *, px_per_stud: int = 16, labels: bool = True
) -> Image.Image:
    """A picture of a Design from one view, cell by cell."""
    frame = view_frame(design.shape, view, px_per_stud=px_per_stud, labels=labels)
    return _render_scene(_design_scene(design, catalog), frame)


def render_seed(
    seed: Seed,
    view: str,
    grid_shape: tuple[int, int, int],
    *,
    seed_offset: tuple[int, int, int] = (0, 0, 0),
    px_per_stud: int = 16,
    labels: bool = True,
) -> Image.Image:
    """A picture of the seed mesh, placed in the grid of the Design made from it."""
    frame = view_frame(grid_shape, view, px_per_stud=px_per_stud, labels=labels)
    color, group = _seed_pixels(seed, frame, seed_offset)
    return _finish(color, group, frame)


def _seed_pixels(
    seed: Seed, frame: Frame, seed_offset: tuple[int, int, int]
) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.asarray(seed.vertices, dtype=np.float64).reshape(-1, 3)
    faces = np.asarray(seed.faces, dtype=np.int64).reshape(-1, 3)
    if len(faces) and (faces.min() < 0 or faces.max() >= len(vertices)):
        raise ValueError("The model's faces refer to corners that do not exist.")
    off = np.asarray(seed_offset, dtype=np.float64).reshape(3)
    grid = vertices / np.asarray(CELL_MM) + off
    if frame.view == "iso_back":  # the iso picture of the seed turned round, as for scenes
        nx, ny, _ = frame.grid_shape
        grid = np.column_stack([nx - grid[:, 0], ny - grid[:, 1], grid[:, 2]])
        vertices = vertices * np.array([-1.0, -1.0, 1.0])
        frame = _iso_twin(frame)
    tri_grid = grid[faces]  # (m, 3, 3)
    tri_mm = vertices[faces]
    normal = np.cross(tri_mm[:, 1] - tri_mm[:, 0], tri_mm[:, 2] - tri_mm[:, 0])
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    normal = normal / np.where(length > 0, length, 1.0)
    right, up, towards = (np.asarray(c, dtype=np.float64) for c in frame.camera)
    facing = normal @ towards
    normal = np.where(facing[:, None] < 0, -normal, normal)
    light = -0.35 * right + 0.6 * up + 0.72 * towards
    light /= np.linalg.norm(light)
    lambert = np.clip(normal @ light, 0.0, 1.0)
    shade = 0.38 + 0.62 * lambert
    if seed.face_colors is not None and len(seed.face_colors) == len(faces):
        base = np.asarray(seed.face_colors, dtype=np.float64).reshape(-1, 3)[:, :3]
    else:
        base = np.broadcast_to(np.asarray(SEED_GREY, dtype=np.float64), (len(faces), 3))
    rgb = base * shade[:, None]
    groups = np.zeros(len(faces), dtype=np.int64)
    return _draw_tris(
        [tri_grid], [groups], [rgb], frame, depth_fade=DEPTH_FADE if frame.straight else 0.0
    )


def silhouette(
    obj: Seed | Design | Build,
    catalog: Catalog,
    view: str,
    grid_shape: tuple[int, int, int] | None = None,
    seed_offset: tuple[int, int, int] = (0, 0, 0),
    px_per_stud: int = 8,
) -> np.ndarray:
    """Bool array [rows, cols]: True where the picture of ``obj`` covers the pixel.

    Drawn without labels, in the same frame as the render functions. Studs are left out
    (see the implementation notes).
    """
    if isinstance(obj, Seed):
        if grid_shape is None:
            raise ValueError(
                "To outline the model, say how big the grid it sits in is (grid_shape)."
            )
        frame = view_frame(grid_shape, view, px_per_stud=px_per_stud, labels=False)
        _, group = _seed_pixels(obj, frame, seed_offset)
        return group >= 0
    if isinstance(obj, Build):
        scene = _build_scene(obj, catalog, None)
        shape = obj.shape
    elif isinstance(obj, Design):
        scene = _design_scene(obj, catalog)
        shape = obj.shape
    else:
        raise ValueError("An outline can be made of a seed, a Design or a Build only.")
    frame = view_frame(shape, view, px_per_stud=px_per_stud, labels=False)
    scene.studs[...] = -1
    _, group = _scene_pixels(scene, frame)
    return group >= 0


def contact_sheet(
    items: Sequence[tuple[str, Image.Image]], *, columns: int = 3, title: str | None = None
) -> Image.Image:
    """Lay out (caption, picture) pairs in a grid, each with its caption above it."""
    items = list(items)
    if not items:
        raise ValueError("There are no pictures to put on the sheet.")
    if columns < 1:
        raise ValueError(f"A sheet needs at least one column, not {columns}.")
    columns = min(columns, len(items))
    rows = math.ceil(len(items) / columns)
    font = _font_of_size(13)
    title_font = _font_of_size(16)
    gap = 12
    _, cap_h = _text_size(font, "Ag")
    cap_h += 6
    col_w = [0] * columns
    row_h = [0] * rows
    for i, (caption, im) in enumerate(items):
        r, c = divmod(i, columns)
        tw, _ = _text_size(font, caption)
        col_w[c] = max(col_w[c], im.width, tw)
        row_h[r] = max(row_h[r], im.height + cap_h)
    title_h = 0
    if title:
        _, tth = _text_size(title_font, title)
        title_h = tth + 12
    width = gap + sum(w + gap for w in col_w)
    if title:
        width = max(width, _text_size(title_font, title)[0] + 2 * gap)
    height = gap + title_h + sum(h + gap for h in row_h)
    sheet = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((gap, gap), title, fill=(20, 20, 20), font=title_font)
    xs = [gap + sum(w + gap for w in col_w[:c]) for c in range(columns)]
    ys = [gap + title_h + sum(h + gap for h in row_h[:r]) for r in range(rows)]
    for i, (caption, im) in enumerate(items):
        r, c = divmod(i, columns)
        x, y = xs[c], ys[r]
        draw.text((x, y), caption, fill=(40, 40, 40), font=font)
        sheet.paste(im.convert("RGB"), (x, y + cap_h))
    return sheet


def compare_sheet(
    seed: Seed | None,
    design: Design,
    build: Build | None,
    catalog: Catalog,
    *,
    views: Sequence[str] = ("front", "right", "top", "iso"),
    px_per_stud: int = 16,
    rough: Build | None = None,
) -> Image.Image:
    """The seed's views above the build's (or the design's) views, one column per view.

    With ``rough`` (the plain conversion) there is a row for it between the two."""
    views = tuple(views)
    items, title = _compare_items(
        seed, design, build, catalog, views=views, px_per_stud=px_per_stud, rough=rough
    )
    return contact_sheet(items, columns=len(views), title=title)


def _compare_items(
    seed: Seed | None,
    design: Design,
    build: Build | None,
    catalog: Catalog,
    *,
    views: Sequence[str],
    px_per_stud: int,
    rough: Build | None,
) -> tuple[list[tuple[str, Image.Image]], str]:
    """The captioned pictures of a comparison sheet, row by row, and its title."""
    views = list(views)
    if not views:
        raise ValueError("Choose at least one view for the comparison picture.")
    for v in views:
        _check_view(v)
    items: list[tuple[str, Image.Image]] = []
    if seed is not None:
        for v in views:
            im = render_seed(
                seed,
                v,
                design.shape,
                seed_offset=design.seed_offset,
                px_per_stud=px_per_stud,
            )
            items.append((f"seed - {v}", im))
    # each Build's scene is made once for all its views, and a rough that is the build
    # itself is drawn once
    drawn: dict[int, list[Image.Image]] = {}

    def build_pictures(b: Build) -> list[Image.Image]:
        if id(b) not in drawn:
            scene = _build_scene(b, catalog, None)
            drawn[id(b)] = [
                _render_scene(scene, view_frame(b.shape, v, px_per_stud=px_per_stud)) for v in views
            ]
        return drawn[id(b)]

    if rough is not None:
        items += [(f"rough - {v}", im) for v, im in zip(views, build_pictures(rough), strict=True)]
    if build is not None:
        items += [(f"build - {v}", im) for v, im in zip(views, build_pictures(build), strict=True)]
    else:
        scene = _design_scene(design, catalog)
        for v in views:
            im = _render_scene(scene, view_frame(design.shape, v, px_per_stud=px_per_stud))
            items.append((f"design - {v}", im))
    what = "build" if build is not None else "design"
    if rough is not None:
        if seed is not None:
            title = f"Seed (top row), rough conversion (middle row) and {what} (bottom row)"
        else:
            title = f"Rough conversion (top row) and {what} (bottom row)"
    elif seed is not None:
        title = f"Seed (top row) and {what} (bottom row)"
    else:
        title = what.capitalize()
    return items, title


# ---- the studio: cut-through views and zooms -------------------------------------------------

SECTION_SHADE = 0.45  # how much darker what lies beyond the cut face is drawn
SECTION_VIEWS = {"x": "right", "y": "front", "z": "top"}
"""The view a cut-through along each axis is seen in: across x from the +x side (picture
right is +y), across y from the front, across z from above."""


def _kept_range(axis: int, at: int, n: int) -> tuple[float, float]:
    """The continuous range along ``axis`` that a cut at cell ``at`` keeps: the cell itself
    and everything beyond it, seen from the view in ``SECTION_VIEWS``."""
    if axis == 1:  # seen from the front: keep the cut cell and what lies behind it
        return float(at), float(n)
    return 0.0, float(at + 1)  # x seen from +x, z seen from above: the cell and what is below


def _cut_scene(scene: _Scene, axis: int, lo: float, hi: float) -> _Scene:
    """``scene`` with only the cells, studs and shaped parts between ``lo`` and ``hi`` along
    ``axis`` (continuous coordinates)."""
    n = scene.cells.shape
    cells = scene.cells.copy()
    studs = scene.studs.copy()
    index = np.arange(n[axis])
    gone = (index < lo) | (index >= hi)
    sel: list = [slice(None)] * 3
    sel[axis] = gone
    cells[tuple(sel)] = -1
    if axis == 2:  # a stud stands in the layer above the cell it is on
        studs[:, :, int(hi) + 1 :] = -1
        studs[:, :, : int(lo) + 1] = -1
    else:
        studs[tuple(sel)] = -1
    out = _Scene(cells=cells, studs=studs, rgb=scene.rgb)
    if len(scene.inst_key):
        centre = scene.inst_pos[:, axis] + scene.inst_size[:, axis] / 2.0
        keep = (centre >= lo) & (centre <= hi)
        renumber = np.cumsum(keep) - 1
        tri_keep = keep[scene.shape_inst]
        out.shape_tris = scene.shape_tris[tri_keep]
        out.shape_group = scene.shape_group[tri_keep]
        out.shape_face = scene.shape_face[tri_keep]
        out.shape_normal = scene.shape_normal[tri_keep]
        out.shape_round = scene.shape_round[tri_keep]
        out.shape_inst = renumber[scene.shape_inst[tri_keep]]
        out.inst_key = scene.inst_key[keep]
        out.inst_pos = scene.inst_pos[keep]
        out.inst_size = scene.inst_size[keep]
    return out


def render_section(
    obj: Build | Design,
    catalog: Catalog,
    axis: str,
    at: int,
    *,
    px_per_stud: int = 16,
    labels: bool = True,
) -> Image.Image:
    """A cut-through of a Build or a Design at cell ``at`` along ``axis`` ("x", "y", "z").

    Everything on the near side of the cut is left out and the rest is drawn from the view in
    ``SECTION_VIEWS``, so the picture shows the cut face at ``at`` in full colour and, through
    any hollow, what lies beyond it, drawn ``SECTION_SHADE`` darker. Parts that
    cross the cut are cut with it, cell by cell; a shaped part (a slope, a round part) is
    kept whole when its middle lies on the kept side and left out otherwise. The axes are
    numbered as in the matching straight view.
    """
    if axis not in SECTION_VIEWS:
        raise ValueError(f'A cut runs across "x", "y" or "z", not {axis!r}.')
    a = _AXIS_NAMES.index(axis)
    shape = _check_shape(obj.shape)
    if not 0 <= at < shape[a]:
        raise ValueError(f"A cut across {axis} must be at a cell from 0 to {shape[a] - 1}.")
    if isinstance(obj, Build):
        scene = _build_scene(obj, catalog, None)
    elif isinstance(obj, Design):
        scene = _design_scene(obj, catalog)
    else:
        raise ValueError("A cut can be made of a Design or a Build only.")
    frame = view_frame(shape, SECTION_VIEWS[axis], px_per_stud=px_per_stud, labels=labels)
    lo, hi = _kept_range(a, at, shape[a])
    color, group = _scene_pixels(_cut_scene(scene, a, lo, hi), frame)
    _, face = _scene_pixels(_cut_scene(scene, a, float(at), float(at + 1)), frame)
    beyond = (group >= 0) & (face < 0)
    color = color.copy()
    color[beyond] = color[beyond] * (1.0 - SECTION_SHADE)
    return _finish(color, group, frame)


def zoom_box(
    picture: Image.Image,
    frame: Frame,
    lo: Sequence[int],
    hi: Sequence[int],
) -> Image.Image:
    """The part of ``picture`` (drawn in ``frame``) that shows the cells ``lo`` .. ``hi``
    (both corners included), with room for studs on top. In a straight view drawn with
    labels, the left and bottom margins are kept beside the crop, so its numbers still give
    the cell indices along both edges."""
    xs = (lo[0], hi[0] + 1)
    ys = (lo[1], hi[1] + 1)
    zs = (lo[2], hi[2] + 1 + STUD_HEIGHT)
    corners = [[x, y, z] for x in xs for y in ys for z in zs]
    cols, rows, _ = frame.project(corners).T
    pad = max(2, frame.px_per_stud // 4)
    c0 = max(int(math.floor(cols.min())) - pad, 0)
    c1 = min(int(math.ceil(cols.max())) + pad, picture.width)
    r0 = max(int(math.floor(rows.min())) - pad, 0)
    r1 = min(int(math.ceil(rows.max())) + pad, picture.height)
    if not (frame.straight and frame.labels):
        return picture.crop((c0, r0, c1, r1))
    bottom = frame.top + frame.area_height
    c0 = max(c0, frame.left)
    r1 = min(r1, bottom)
    body_w, body_h = c1 - c0, r1 - r0
    margin_h = picture.height - bottom
    out = Image.new("RGB", (frame.left + body_w, body_h + margin_h), BACKGROUND)
    out.paste(picture.crop((0, r0, frame.left, r1)), (0, 0))
    out.paste(picture.crop((c0, r0, c1, r1)), (frame.left, 0))
    out.paste(picture.crop((0, bottom, frame.left, picture.height)), (0, body_h))
    out.paste(picture.crop((c0, bottom, c1, picture.height)), (frame.left, body_h))
    return out


def render_zoom(
    obj: Seed | Build | Design,
    catalog: Catalog,
    view: str,
    lo: Sequence[int],
    hi: Sequence[int],
    *,
    px_per_stud: int = 32,
    grid_shape: tuple[int, int, int] | None = None,
    seed_offset: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """``view`` of a seed, Build or Design at ``px_per_stud``, cut down to the cells ``lo`` ..
    ``hi`` (``zoom_box``). Everything in the view is drawn, also what lies in front of the
    box. A seed needs ``grid_shape`` and ``seed_offset`` as in ``render_seed``."""
    if isinstance(obj, Seed):
        if grid_shape is None:
            raise ValueError("To zoom on the model, say how big the grid it sits in is.")
        shape = _check_shape(grid_shape)
        picture = render_seed(
            obj, view, shape, seed_offset=seed_offset, px_per_stud=px_per_stud, labels=True
        )
    elif isinstance(obj, Build):
        shape = _check_shape(obj.shape)
        picture = render_build(obj, catalog, view, px_per_stud=px_per_stud)
    else:
        shape = _check_shape(obj.shape)
        picture = render_design(obj, catalog, view, px_per_stud=px_per_stud)
    frame = view_frame(shape, view, px_per_stud=px_per_stud, labels=view not in ISO_VIEWS)
    return zoom_box(picture, frame, lo, hi)
