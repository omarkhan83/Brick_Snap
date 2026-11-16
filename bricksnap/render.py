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
  (or Design cells) are told apart. Slopes and other shaped parts are drawn as the boxes
  of cells they cover.
- Studs: small bumps in side views, rings in the top view, short octagonal posts in "iso".
  Design cells show studs where their finish is "studs" and nothing sits on them.
- Colours not in the catalogue are drawn magenta so they stand out. Parts with an unknown
  part id, or outside the grid, are not drawn (the checks report them).
- Depth darkening: up to ``DEPTH_FADE`` in straight views and the gentler
  ``ISO_DEPTH_FADE`` in "iso" for Builds and Designs (iso also has face shading). Seeds
  are not faded in "iso", where their flat shading already shows the shape.
- The smallest scale is 3 pixels per stud: below that a plate is under 1.2 pixels tall and
  rows are sampled at pixel centres, so some one-plate parts would not be drawn at all.
- ``label_texts`` lists every text in the label margins (with the tick it belongs to);
  the pictures draw exactly that list.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bricksnap.catalog import Catalog
from bricksnap.connect import occupancy
from bricksnap.types import (
    CELL_MM,
    EMPTY,
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
        return self.view != "iso"


def _vec3(v) -> tuple[float, float, float]:
    return float(v[0]), float(v[1]), float(v[2])


def _mat3(m) -> tuple[tuple[float, float, float], ...]:
    return tuple(_vec3(r) for r in m)


def _check_view(view: str) -> None:
    if view not in VIEWS:
        raise ValueError(f'Unknown view "{view}". Choose one of: {", ".join(VIEWS)}.')


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
    if view == "iso":
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
    """Which group fills each cell, where exposed studs stand, and each group's colour."""

    cells: np.ndarray  # int32 [nx, ny, nz]: group index or -1
    studs: np.ndarray  # int32 [nx, ny, nz + 1]: group of the stud standing in that cell, or -1
    rgb: np.ndarray  # (groups, 3) float64


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
    skip = set(out_of_bounds)
    for i, p in enumerate(build.parts):
        part = catalog.parts.get(p.part)
        if part is None or i in skip or not part.studs_top:
            continue
        top = p.z + part.h
        for x, y in catalog.stud_cells(p):
            inside = 0 <= x < nx and 0 <= y < ny and occ[x, y, top - 1] == i
            if inside and (top >= nz or occ[x, y, top] < 0):
                studs[x, y, top] = i
    codes = np.array([p.color for p in build.parts], dtype=np.int64)
    rgb = _palette(catalog, codes) if len(codes) else np.zeros((0, 3))
    return _Scene(cells=occ.astype(np.int32), studs=studs, rgb=rgb)


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
    for d in design.details:
        if d.part not in catalog.parts:
            continue
        p = Placement(part=d.part, color=d.color, x=d.x, y=d.y, z=d.z, rot=d.rot % 180)
        w, dd, h = catalog.footprint(p)
        if d.x < 0 or d.y < 0 or d.z < 0 or d.x + w > nx or d.y + dd > ny or d.z + h > nz:
            continue
        region = cells[catalog.cells(p)]
        if (region >= 0).any():
            continue
        region[...] = count + len(extra_codes)
        extra_codes.append(int(d.color))
    if extra_codes:
        groups.append(np.array(extra_codes, dtype=np.int64))
    all_codes = np.concatenate(groups)
    uniq, inverse = np.unique(all_codes, return_inverse=True)
    rgb = _palette(catalog, uniq)[inverse] if len(all_codes) else np.zeros((0, 3))
    studs = np.full((nx, ny, nz + 1), -1, dtype=np.int32)
    above_free = np.ones(colors.shape, dtype=bool)
    above_free[:, :, :-1] = cells[:, :, 1:] < 0
    has = studded & above_free
    xs, ys, zs = np.nonzero(has)
    studs[xs, ys, zs + 1] = cells[xs, ys, zs]
    return _Scene(cells=cells, studs=studs, rgb=rgb)


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
        # a stud stands on the topmost cell of each column, in the cell above it
        stud_view = _to_view_axes(scene.studs[:, :, 1:], view)  # cell k holds the stud on k
        stud_top = np.take_along_axis(
            stud_view, np.minimum(depth2, cells.shape[2] - 1).astype(np.int64)[:, :, None], axis=2
        )[:, :, 0]
        stud_top = np.where(np.isfinite(depth2), stud_top, -1)
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
    stud_px = np.zeros(group.shape, dtype=bool)
    if view == "top":
        st_p = np.full((nu + 1, nv + 2), -1, dtype=np.int64)
        st_p[:nu, :nv] = stud_top
        stud_here = st_p[uix[None, :], vix[:, None]] >= 0
        r2 = (ufrac[None, :] - 0.5) ** 2 + (vfrac[:, None] - 0.5) ** 2
        ring = stud_here & (r2 <= STUD_RADIUS**2) & (r2 > (STUD_RADIUS * 0.72) ** 2)
        disc = stud_here & (r2 <= (STUD_RADIUS * 0.72) ** 2)
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
        stud_px = in_shape & (sg >= 0) & (sd < depth)
        group = np.where(stud_px, sg, group)
        depth = np.where(stud_px, sd, depth)

    depth_mm = np.where(np.isfinite(depth), (depth + 0.5) * depth_mm_per_cell, np.inf)
    shade = _shade_depth(depth_mm, frame, DEPTH_FADE)
    rgb_table = np.vstack([scene.rgb, np.full((1, 3), BACKGROUND, dtype=np.float64)])
    color = rgb_table[group] * shade[:, :, None]
    if view == "top":
        color = np.where(disc[:, :, None], _lighten(color, 0.18), color)
        color = np.where(ring[:, :, None], color * 0.78, color)
    else:
        color = np.where(stud_px[:, :, None], _lighten(color, 0.12), color)
    bg = group < 0
    color[bg] = BACKGROUND
    _grid_lines(color, bg, frame)
    return color, group


def _lighten(color: np.ndarray, amount: float) -> np.ndarray:
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
        order = np.lexsort((tri, dep, pix))
        pix, dep, tri = pix[order], dep[order], tri[order]
        first = np.ones(len(pix), dtype=bool)
        first[1:] = pix[1:] != pix[:-1]
        pix, dep, tri = pix[first], dep[first], tri[first]
        better = dep < zbuf[pix]
        zbuf[pix[better]] = dep[better]
        index[pix[better]] = tri[better]
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

    return _draw_tris(tris, tri_group, tri_rgb, frame, depth_fade=ISO_DEPTH_FADE)


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
    if frame.straight:
        color, group = _render_scene_straight(scene, frame)
    else:
        color, group = _render_scene_iso(scene, frame)
    return _finish(color, group, frame)


# ---- public API ----------------------------------------------------------------------------


def render_build(
    build: Build,
    catalog: Catalog,
    view: str,
    *,
    px_per_stud: int = 16,
    labels: bool = True,
    upto_step: int | None = None,
) -> Image.Image:
    """A picture of a Build from one view (see the module docstring)."""
    frame = view_frame(build.shape, view, px_per_stud=px_per_stud, labels=labels)
    return _render_scene(_build_scene(build, catalog, upto_step), frame)


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
    vertices = np.asarray(seed.vertices, dtype=np.float64).reshape(-1, 3)
    faces = np.asarray(seed.faces, dtype=np.int64).reshape(-1, 3)
    if len(faces) and (faces.min() < 0 or faces.max() >= len(vertices)):
        raise ValueError("The model's faces refer to corners that do not exist.")
    off = np.asarray(seed_offset, dtype=np.float64).reshape(3)
    grid = vertices / np.asarray(CELL_MM) + off
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
    color, group = _draw_tris(
        [tri_grid], [groups], [rgb], frame, depth_fade=DEPTH_FADE if frame.straight else 0.0
    )
    return _finish(color, group, frame)


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
) -> Image.Image:
    """The seed's views above the build's (or the design's) views, one column per view."""
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
    for v in views:
        if build is not None:
            im = render_build(build, catalog, v, px_per_stud=px_per_stud)
            items.append((f"build - {v}", im))
        else:
            im = render_design(design, catalog, v, px_per_stud=px_per_stud)
            items.append((f"design - {v}", im))
    what = "build" if build is not None else "design"
    title = f"Seed (top row) and {what} (bottom row)" if seed is not None else what.capitalize()
    return contact_sheet(items, columns=len(views), title=title)
