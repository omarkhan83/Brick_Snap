"""Measure, from a model's LDraw file and the parts' real geometry, what an eye reads as an old
or a modern LEGO model: studs left showing, slab sides and plate seams, parts built sideways,
thin members, the palette as seen, glazing, size and density.

usage:
  uv run python -I style_measures.py OUT.json MODEL.ldr [MODEL2.ldr ...]
      one compact line per model; every number to OUT.json
  uv run python -I style_measures.py --pictures DIR MODEL.ldr [...]
      also a labelled picture per model (DIR/<name>.png): the five views coloured by kind of
      skin (top row) and in the parts' own colours with part outlines (bottom row)
  uv run python -I style_measures.py --table OUT.json TABLE.md
      the table of all models, the medians of each group, the measures ranked by how far
      official models are from AI builds, the Cessna against the official vehicles
  uv run python -I style_measures.py --sanity DIR
      hand-made test models (written to DIR) and their numbers

Each MODEL is one flat LDraw file (an AI build, or an official set flattened by the earlier
study's ``exp_flatten.py``). Parts and stud links come from the checker
(``validate.check`` without the movement check, which inside the builder's own check is
already done). Every measure is the same
computation on every model, deterministic (no randomness; ties are broken by point order).

One source of truth: the skin below and the measures the builder is shown (plate seams,
not upright, top faces of sideways parts, the colour shares and patches, open Technic holes,
studs showing) are computed by ``bricksnap.lab.looks``, which this script imports; the script
adds the study's other measures on the same skin. Moving them there changed no number of the
table (checked against the earlier run, byte for byte).

THE SKIN (shared by measures 1, 2, 3, 5, 6 and the Technic holes of 4)
- Each part's real surface: its library triangles WITH its studs (``solid.triangles``), split
  across the longest edge until no edge is longer than ``STEP`` (1.4 LDU); one sample point per
  piece (its centre), carrying the normal of its triangle (sign ignored: LDraw winding is not
  used) and three flags, all in the part's own frame and cached per part file:
  * stud: the point is on a male stud primitive, or on the part's surface within the stud's
    cell (within 10 LDU of the stud's axis in both directions across it, within 1 LDU of its
    base plane, facing the way the stud points). So a stud's whole 1 x 1 cell counts as
    studded, and a jumper plate's margin does not. Hollow (open) studs count as studs, and so
    does a single 1 x 1 round plate used as a light: the geometry cannot tell intent.
  * hole: the point is in a Technic pin hole's opening or bore (within 8 LDU of the hole's
    line, between its two ends; a hole drawn at one end only is taken as 10 LDU deep). Holes
    are the library's ``pin hole`` primitives, two at the ends of one through hole being one.
  * top face: the part's own top or a face that leans up in the part's frame (its normal is at
    least 0.35 up or down in the part's frame) in the upper half of the part's box, and not a
    stud: a tile's top, a slope's or curved slope's face.
- Five views, orthographic, on a grid of ``PIX`` (2 LDU, ten pixels to a stud): from above
  (looking down, front of the model at the bottom of the picture), front (from -z, LDraw's
  front), back (+z), left (-x) and right (+x). Each pixel shows the nearest sample point
  (a z-buffer of points). A sixth view from below is used only for the slab thickness. Together
  the five views are "the visible skin"; areas are in square studs (400 LDU^2).
- Each skin pixel has one kind, the first that applies: transparent (the part's colour has
  alpha below 255 in LDConfig; a transparent part is treated as opaque, what is behind it is
  not seen), Technic hole (a hole flag on a hole nothing fills: no other part's pin, axle or
  bar handle connector point within 3 LDU of its line between its ends), studded (stud flag),
  curved or sloped (the world normal is more than 5 degrees from every world axis), smooth
  flat (everything else: a tile's top, a brick's side, the bare top of a part without studs).
- Rough: points, not triangles, so a surface seen nearly edge-on can leave a pixel empty and
  show a point behind it (a few pixels per model; the pictures show them as specks); inside
  surfaces of a part (a brick's hollow underside) are sampled too and only hidden by the
  z-buffer. A curved surface's facets within 5 degrees of an axis (at a curve's crest) read as flat.

THE MEASURES
1. Studs left showing.
   a. Count: of all male studs of all parts, the share with nothing on them: the checker links
      no part to it (``Report.links``: the stud is seated in a socket, tube or ring), and no
      other part's filled body (``Part.inside``: hollow undersides count as solid) contains the
      point 2 LDU up the stud or 2 LDU above its top (6 LDU from its base), and neither point
      is under another part: the stud points into that part's underside (its own up, within 25
      degrees), and the point is in one of its filled-body columns at most 6 LDU below the
      column's bottom (a stud under the hollow high end of a curved slope, which the checker
      does not link and the filled body leaves open).
      Overall, per 100 parts, and by the way the stud points in the world: up (within 25
      degrees of up), down, sideways (within 25 degrees of level), angled. ``single_stud_
      details``: showing studs on parts with one stud and a body of at most 1 x 1 stud (round
      plates, studs used as lights or eyes); counted in the total and also given apart.
   b. Area: of the skin seen from above, of the side skin (the four side views together) and of
      the whole visible skin, the share of each kind: studded, smooth flat, curved or sloped,
      transparent, Technic hole.
2. Slab sides and steps.
   a. ``side_flat_wall``: share of the side skin that is flat and faces the viewer (normal
      within 5 degrees of the view's direction; not transparent, not studded): the vertical
      wall of a brick, plate or tile. ``side_curved`` is the curved or sloped share.
   b. ``seams_per_stud``: horizontal seams on the side skin: two vertically adjacent side-view
      pixels that show two different parts, both flat walls facing the viewer and within 2 LDU
      in depth (a flush joint between stacked parts). Seams per stud (20 LDU) of skin height,
      averaged over the side skin: total seam pixels * 20 / (side skin pixels * PIX). A plain
      brick wall gives 20/24 = 0.83, plates stacked with bare edges 2.5, a tiled flank 0.
   c. ``steps_per_100_studs2``: staircase edges, from above: two neighbouring pixels of the top
      view whose surfaces differ in height by 6 to 50 LDU (a plate to about two bricks), the
      lower one studded (a studded tread). Length of such edges in studs, per 100 studs^2 of
      the top view's skin, and ``step_edge_share``: that length over the top view's outline
      length (the perimeter of its covered area): how much of the model's edges, seen from
      above, are stairs.
3. Built sideways.
   a. ``facing``: of the stud parts (studs or a socket underneath), the share whose own up is
      up, sideways, down or angled in the world (``exp_measures.facing``); ``built_sideways``
      is all but up.
   b. ``side_top_faces``: share of the side skin that is the top face (above) of a part whose
      own up is not world up: tiles, slopes and curved slopes facing outward, what a modern
      smooth flank is made of. Also given for the whole skin.
4. Thin things.
   a. Members: a part is a long member when its body's longest side is at least 3 times its
      middle side and at least 40 LDU (two studs): bars, antennas, 1 x 4 plates and bricks,
      Technic beams and axles (stickers and parts under 1 LDU thick are left out). It is free
      when its middle is clear (none of four probe points 2 LDU beyond its body above, below and
      on both sides at the middle of its length is inside another part's filled body: a strut
      or a leg between two ends) or one end sticks out (the same four probes at an eighth of its
      length from that end and one 3 LDU beyond the end are all clear: an antenna, a tail).
      Counted (and per 100 parts); for free members the thickness (the body's smallest side)
      as classes: bar-thin (6.5 LDU or less: bars, antennas, whips), plate or axle (up to 12.5:
      a plate or tile on edge or flat, an axle, a half-thick Technic beam), thick (more:
      1-wide bricks, full beams); the median thickness in LDU and the median of length over
      thickness.
   b. Slabs: the views from above and from below on the same grid; a pixel's thickness is the
      lowest surface's height below the highest (rough by up to half a plate: the lowest
      surface seen is a hollow underside's rim or inside). Overhang pixels are those whose
      lowest surface is at least 24 LDU above the model's lowest point; thin overhang is at
      most 40 LDU (5 plates) thick; regions of at least 9 studs^2 of thin overhang are slabs
      (wings, roofs, a car's bonnet). Area in studs^2, share of the top view, area-weighted
      median thickness in plates.
   c. ``technic_holes_visible``: holes (lines) nothing fills that show at least 12 pixels
      (48 LDU^2, about 40% of a hole's mouth) in one of the five views.
5. Palette as seen. By skin pixels of the five views: each colour's share (top six named);
   ``colours_5pct``: colours holding at least 5%; ``primary_share``: share in LDraw 4 red,
   1 blue, 14 yellow, 2 green; ``classic_palette_share``: the primaries with white, black and
   the old greys (7, 8), the palette of sets before about 2004; ``old_grey_share_of_greys``:
   of the grey skin, the share in the old greys (7, 8) against the bluish greys (71, 72) that
   replaced them; ``side_colour_edges_horizontal``: of the colour edges on the side skin
   (neighbouring pixels of two colours), the share that are horizontal lines (stripes from
   stacking parts of different colours; a wedge or curved colour boundary gives both kinds);
   ``trans_share``; patches: 4-connected pixels of one colour in
   one view; ``patch_mean_studs2``: the area-weighted mean patch size (sum of size^2 / sum of
   size, so specks do not drag it down) in studs^2, and ``patch_coherence``: that over the
   mean skin area of one view (1 when each view is one patch).
6. Glazing. Transparent parts: count, their share of the skin, and of those parts the share
   that are glazing elements (description: windscreen, window, glass, canopy, cockpit, panel,
   pane, door) against ordinary bricks, plates, slopes, tiles and rounds cast transparent; the
   same split by skin area.
7. Size and density. Parts; kinds of part; colours (by part); the model's box in studs (20 LDU
   each way, height too), ``parts_per_stud3`` (parts per cubic stud of the box); ``small_
   share``: stud parts whose footprint (body extent in its own x and z, rounded to whole studs)
   is 1 x 1 or 1 x 2 (as ``exp_measures`` measures it).
8. Outline. ``outline_on_axis``: of the silhouette edges of the five views, the share whose
   direction (from the gradient of the covered area smoothed over 1 pixel) is within 10
   degrees of level or upright: a boxy, stepped outline against angled and curved ones.
   Rough: a stair-stepped diagonal with steps under about 4 pixels (8 LDU, a plate) reads
   partly as diagonal; larger steps read as boxy.

Cost: the skin dominates (sampling each part file once, then a z-buffer per view); the other
measures are small. Times are measured and written per model (``seconds``).
"""

from __future__ import annotations

import collections
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

# The skin and the measures the builder sees come from the engine: one source of truth.
from bricksnap.lab import looks
from bricksnap.lab.looks import (
    CURVED,
    FLAT,
    HOLE,
    KINDS,
    PIX,
    SIDES,
    STUDDED,
    TRANS,
    VIEWS,
)
from bricksnap.lab.looks import View as Skin
from bricksnap.lab.ldraw_lib import Library, library
from bricksnap.lab.validate import Placed, check

CLASSIC = {4, 1, 14, 2, 15, 0, 7, 8}  # the primaries, white, black, and the greys before 2004
GLAZING = re.compile(r"windscreen|windshield|window|glass|canopy|cockpit|panel|pane\b|door", re.I)
BELOW = ("below", 1, -1, 0, 1, 2, -1)


def load(path: str, lib: Library):
    """The checker's report (without the movement check): its placed parts and stud links."""
    return check(open(path, encoding="utf-8", errors="replace").read(), lib, movement=False)


def measure(path: str, lib: Library, pictures: str | None = None) -> dict:
    t0 = time.perf_counter()
    secs: dict[str, float] = {}
    rep = load(path, lib)
    placed: list[Placed] = rep.placed
    cfg = looks.colours(lib)
    n = len(placed)
    name = name_of(path)
    out: dict = dict(name=name, path=path, group=group_of(path), parts=n, content=content_of(path))
    secs["checker (already done inside check)"] = time.perf_counter() - t0
    if not n:
        return out
    t = time.perf_counter()
    for p in placed:
        looks.part_points(p.key, lib)
    secs["sample parts (first time per part file)"] = time.perf_counter() - t

    t = time.perf_counter()
    sk = looks.skin(placed, lib, extra_views=(BELOW,))
    skins: dict[str, Skin] = sk.views
    W = sk.points
    stud = sk.stud
    secs["five views and below"] = time.perf_counter() - t

    t = time.perf_counter()
    lk = looks.measure_skin(rep, sk)
    out["looks"] = looks.record(lk)
    secs["the builder's measures (looks.measure_skin)"] = time.perf_counter() - t

    t = time.perf_counter()
    five = [skins[v[0]] for v in VIEWS]
    side = [skins[s] for s in SIDES]

    def kind_shares(ss: list[Skin]) -> dict:
        tot = sum(int((s.kind > 0).sum()) for s in ss) or 1
        return {KINDS[k - 1]: round(sum(int((s.kind == k).sum()) for s in ss) / tot, 3) for k in range(1, 6)}

    area = PIX * PIX / 400
    out["skin_area_studs2"] = round(sum(int((s.kind > 0).sum()) for s in five) * area, 1)
    out["skin_above"] = kind_shares([skins["above"]])
    out["skin_sides"] = kind_shares(side)
    out["skin_all"] = kind_shares(five)
    side_px = sum(int((s.kind > 0).sum()) for s in side) or 1
    out["side_flat_wall"] = round(sum(int(s.wall.sum()) for s in side) / side_px, 3)
    out["side_curved"] = out["skin_sides"]["curved or sloped"]
    # 2b seams (looks)
    out["seams_per_stud"] = lk.seams_per_stud
    # 2c steps
    A = skins["above"]
    ys = A.depth
    st = A.owner >= 0
    studpx = np.where(st, stud[np.where(st, A.owner, 0)], False)
    edges = 0
    for ax in (0, 1):
        y1 = ys[:-1, :] if ax == 0 else ys[:, :-1]
        y2 = ys[1:, :] if ax == 0 else ys[:, 1:]
        s1 = studpx[:-1, :] if ax == 0 else studpx[:, :-1]
        s2 = studpx[1:, :] if ax == 0 else studpx[:, 1:]
        with np.errstate(invalid="ignore"):
            drop = np.abs(y1 - y2)
            lower_studded = np.where(y1 > y2, s1, s2)  # larger y is lower
            edges += int(((drop >= 6) & (drop <= 50) & lower_studded).sum())
    top_px = int(st.sum()) or 1
    perim = int((st[:-1, :] != st[1:, :]).sum() + (st[:, :-1] != st[:, 1:]).sum()) or 1
    out["steps_per_100_studs2"] = round(edges * PIX / 20 / (top_px * area) * 100, 2)
    out["step_edge_share"] = round(edges / perim, 3)
    # 3 sideways (looks for the two the builder sees)
    stud_parts = looks.stud_parts(placed)
    fc = collections.Counter(facing_dir(p.m @ np.array([0.0, -1.0, 0.0])) for p in (placed[i] for i in stud_parts))
    tot = len(stud_parts) or 1
    out["facing"] = {k: round(fc[k] / tot, 3) for k in ("up", "sideways", "down", "angled")}
    out["built_sideways"] = lk.not_upright
    out["side_top_faces"] = lk.side_top_faces
    all_px = sum(int((s.kind > 0).sum()) for s in five) or 1
    out["skin_top_faces_of_sideways"] = round(sum(int(s.sidetop.sum()) for s in five) / all_px, 3)
    secs["skin measures"] = time.perf_counter() - t

    # 1a studs showing (count; looks.studs)
    t = time.perf_counter()
    boxes = [looks.world_box(p) for p in placed]
    sts = looks.studs(rep)
    showing = sts.showing
    if len(showing):
        dirs = [facing_dir(d) for d in sts.way]
        byd = {}
        for k in ("up", "sideways", "down", "angled"):
            m = np.array([x == k for x in dirs])
            byd[k] = {"studs": int(m.sum()), "showing": int((m & showing).sum()),
                      "share": round(float((m & showing).sum() / m.sum()), 3) if m.sum() else None}
        out["studs"] = lk.studs
        out["studs_showing"] = lk.studs_showing
        out["studs_showing_share"] = lk.studs_showing_share
        out["studs_showing_per_100_parts"] = round(100 * float(showing.sum()) / n, 1)
        out["studs_by_direction"] = byd
        out["single_stud_details_showing"] = int((showing & sts.single).sum())
    else:
        out.update(studs=0, studs_showing=0, studs_showing_share=None, studs_showing_per_100_parts=0.0)
    secs["studs showing (count)"] = time.perf_counter() - t

    # 4a members
    t = time.perf_counter()
    members, free = [], []
    for i, p in enumerate(placed):
        if not p.part.has_body():
            continue
        lo_l, hi_l = p.part.bbox_min, p.part.bbox_max
        sz = hi_l - lo_l
        o = np.argsort(sz)
        a, b, c = sz[o]
        if c < 40 or c < 3 * b or a < 1 or p.part.description.lstrip("~").startswith("Sticker"):
            continue
        members.append(i)
        ctr = (lo_l + hi_l) / 2
        ax_l, ax_m, ax_t = o[2], o[1], o[0]
        def clear(pr: list) -> bool:
            wp = p.to_world(np.array(pr))
            for j, qp in enumerate(placed):
                if j == i:
                    continue
                blo, bhi = boxes[j]
                inb = np.all((wp >= blo - 1) & (wp <= bhi + 1), axis=1)
                if inb.any() and qp.part.inside(qp.to_local(wp[inb])).any():
                    return False
            return True

        def around(at: float) -> list:
            pr = []
            for axis, half in ((ax_t, a / 2 + 2), (ax_m, b / 2 + 2)):
                for s2 in (-1, 1):
                    q = ctr.copy()
                    q[ax_l] += at
                    q[axis] += s2 * half
                    pr.append(q)
            return pr

        def cap(sgn: int) -> np.ndarray:
            q = ctr.copy()
            q[ax_l] += sgn * (c / 2 + 3)
            return q

        is_free = clear(around(0.0)) or any(clear(around(sgn * (c / 2 - c / 8)) + [cap(sgn)]) for sgn in (-1, 1))
        if is_free:
            free.append((i, float(a), float(c)))
    th = [a for _, a, _ in free]
    out["members"] = len(members)
    out["free_members"] = len(free)
    out["free_members_per_100_parts"] = round(100 * len(free) / n, 1)
    out["free_member_classes"] = {
        "bar-thin": sum(1 for a in th if a <= 6.5),
        "plate or axle": sum(1 for a in th if 6.5 < a <= 12.5),
        "thick": sum(1 for a in th if a > 12.5)}
    out["free_member_bar_share"] = round(out["free_member_classes"]["bar-thin"] / len(free), 3) if free else None
    out["free_member_median_thickness"] = round(float(np.median(th)), 1) if th else None
    out["free_member_median_slenderness"] = round(float(np.median([c / max(a, 1) for _, a, c in free])), 1) if free else None
    secs["members"] = time.perf_counter() - t

    # 4b slabs
    t = time.perf_counter()
    B = skins["below"]
    ground = float(W[:, 1].max())
    both = (A.owner >= 0) & (B.owner >= 0)
    ytop = A.depth
    ybot = -B.depth
    with np.errstate(invalid="ignore"):
        thick = np.where(both, ybot - ytop, np.nan)
        thin_over = both & (ground - ybot >= 24) & (thick <= 40)
    lab, nl = ndimage.label(thin_over)
    min_px = 9 / area
    slab = np.zeros_like(thin_over)
    if nl:
        sizes = ndimage.sum(thin_over, lab, index=np.arange(1, nl + 1))
        keep = np.nonzero(sizes >= min_px)[0] + 1
        slab = np.isin(lab, keep)
    out["slab_area_studs2"] = round(float(slab.sum()) * area, 1)
    out["slab_share_of_above"] = round(float(slab.sum()) / top_px, 3)
    out["slab_median_plates"] = round(float(np.median(thick[slab])) / 8, 2) if slab.any() else None
    # 4c holes visible (looks)
    out["technic_holes"] = sk.holes
    out["technic_holes_filled"] = len(sk.filled)
    out["technic_holes_visible"] = lk.open_holes
    secs["slabs and holes"] = time.perf_counter() - t

    # 5 palette, 6 glazing
    t = time.perf_counter()
    shares = looks.colour_shares(sk)
    out["palette"] = [[cfg.get(c, (str(c),))[0], c, round(v, 3)] for c, v in sorted(shares.items(), key=lambda x: -x[1])[:6]]
    out["colours_seen"] = len(shares)
    out["colours_5pct"] = lk.colours_5pct
    out["primary_share"] = lk.primary_share
    out["classic_palette_share"] = round(sum(v for c, v in shares.items() if c in CLASSIC), 3)
    g = sum(shares.get(c, 0) for c in (7, 8, 71, 72))
    out["old_grey_share_of_greys"] = round(sum(shares.get(c, 0) for c in (7, 8)) / g, 3) if g > 0 else None
    # colour edges on the side skin: horizontal (a stripe from stacking) against all
    hor = ver = 0
    for s in side:
        c = s.colour
        hor += int(((c[:-1] != c[1:]) & (c[:-1] >= 0) & (c[1:] >= 0)).sum())
        ver += int(((c[:, :-1] != c[:, 1:]) & (c[:, :-1] >= 0) & (c[:, 1:] >= 0)).sum())
    out["side_colour_edges_horizontal"] = round(hor / (hor + ver), 3) if hor + ver else None
    # 8 outline: the silhouette of each of the five views, its edge direction from the
    # gradient of the covered area smoothed over 1 pixel
    on_axis = total = 0.0
    for s in five:
        mask = s.owner >= 0
        cov = ndimage.gaussian_filter(mask.astype(float), 1.0)
        gy, gx = np.gradient(cov)
        edge = mask ^ ndimage.binary_erosion(mask)
        ok = np.hypot(gy[edge], gx[edge]) > 1e-3
        ang = np.degrees(np.arctan2(np.abs(gy[edge]), np.abs(gx[edge])))  # 0 to 90
        on_axis += float(((np.minimum(ang, 90 - ang) <= 10) & ok).sum())
        total += float(ok.sum())
    out["outline_on_axis"] = round(on_axis / total, 3) if total else None
    out["trans_share"] = round(sum(v for c, v in shares.items() if cfg.get(c, ("", 0, False))[2]), 3)
    out["patch_coherence"] = lk.patch_coherence
    out["patch_mean_studs2"] = round(looks.patch_coherence(sk) * all_px / 5 * area, 2)
    trans_p = [cfg.get(p.colour, ("", (0, 0, 0), False))[2] for p in placed]
    tp = [i for i in range(n) if trans_p[i]]
    gl = [i for i in tp if GLAZING.search(placed[i].part.description)]
    trans_px = collections.Counter()
    for s in five:
        ok = (s.kind == TRANS)
        for i, v in zip(*np.unique(s.part[ok], return_counts=True)):
            trans_px[int(i)] += int(v)
    tpx = sum(trans_px.values())
    out["trans_parts"] = len(tp)
    out["trans_glazing_parts_share"] = round(len(gl) / len(tp), 3) if tp else None
    out["trans_glazing_area_share"] = round(sum(trans_px[i] for i in gl) / tpx, 3) if tpx else None
    # 7 size
    wlo = np.min([b[0] for b in boxes], axis=0)
    whi = np.max([b[1] for b in boxes], axis=0)
    dims = (whi - wlo) / 20
    out["size_studs"] = [round(float(x), 1) for x in dims]  # x, y (height), z
    out["parts_per_stud3"] = round(n / max(1e-9, float(np.prod(np.maximum(dims, 0.4)))), 3)
    out["kinds"] = len({p.key for p in placed})
    out["colours_by_part"] = len({p.colour for p in placed})
    small = 0
    for i in stud_parts:
        span = placed[i].part.bbox_max - placed[i].part.bbox_min
        fx, fz = max(1, round(span[0] / 20)), max(1, round(span[2] / 20))
        small += sorted((fx, fz)) in ([1, 1], [1, 2])
    out["small_share"] = round(small / tot, 3)
    secs["palette, glazing, size"] = time.perf_counter() - t
    secs["total"] = time.perf_counter() - t0
    out["seconds"] = {k: round(v, 3) for k, v in secs.items()}
    out["sample_points"] = int(len(W))
    if pictures:
        draw(out, skins, cfg, os.path.join(pictures, name + ".png"))
    return out


def facing_dir(d: np.ndarray) -> str:
    up = float(-d[1])
    if up > math.cos(math.radians(25)):
        return "up"
    if up < -math.cos(math.radians(25)):
        return "down"
    if abs(up) < math.sin(math.radians(25)):
        return "sideways"
    return "angled"


def name_of(path: str) -> str:
    """A project's folder name, the earlier study's folder/file, or the file's own name."""
    p = Path(path)
    if p.name == "model.ldr":
        return p.parent.name
    if group_of(path) == "ai-study":
        return f"{p.parent.name}/{p.stem}"
    return p.stem


def content_of(path: str) -> str:
    """A fingerprint of the model's part lines (the same build saved twice has the same one)."""
    import hashlib

    lines = [" ".join(ln.split()) for ln in open(path, encoding="utf-8", errors="replace") if ln.strip().startswith("1 ")]
    return hashlib.sha1("\n".join(lines).encode()).hexdigest()[:12]


def group_of(path: str) -> str:
    if "/projects/" in path and "/research/" not in path:
        return "ai-free"
    if "ai-as-the-builder" in path:
        return "ai-study"
    if "/official/" in path:
        return "official"
    if "/extra/" in path:
        return "official-extra"
    return "other"


# ---- pictures -----------------------------------------------------------------------------

KIND_RGB = {0: (255, 255, 255), STUDDED: (226, 80, 40), FLAT: (200, 200, 200), CURVED: (60, 110, 220),
            TRANS: (90, 220, 230), HOLE: (20, 20, 20)}


def draw(m: dict, skins: dict[str, Skin], cfg, out_png: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 15)
        small = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    views = [skins[v[0]] for v in VIEWS]
    wsum = sum(s.kind.shape[1] for s in views)
    hmax = max(s.kind.shape[0] for s in views)
    scale = max(1, min(4, int(2200 / (wsum + 10 * len(views)))))
    gap = 16
    W = sum(s.kind.shape[1] * scale + gap for s in views) + gap
    H = 2 * (hmax * scale + 26) + 120
    img = Image.new("RGB", (max(W, 900), H), "white")
    dr = ImageDraw.Draw(img)
    x = gap
    for s in views:
        h, w = s.kind.shape
        f = 0.55 + 0.45 * s.shade
        a = np.zeros((h, w, 3))
        for k, rgb in KIND_RGB.items():
            a[s.kind == k] = rgb
        lit = np.where((s.kind > 0)[:, :, None], a * f[:, :, None], 255)
        b = np.zeros((h, w, 3))
        for c in np.unique(s.colour):
            b[s.colour == c] = (255, 255, 255) if c < 0 else cfg.get(int(c), ("", (255, 0, 255), False))[1]
        rb = np.where((s.colour >= 0)[:, :, None], b * f[:, :, None], 255)
        edge = np.zeros((h, w), dtype=bool)
        edge[:-1] |= (s.part[:-1] != s.part[1:]) & (s.part[:-1] >= 0)
        edge[:, :-1] |= (s.part[:, :-1] != s.part[:, 1:]) & (s.part[:, :-1] >= 0)
        rb[edge] = rb[edge] * 0.45
        y0 = 30
        for arr in (lit, rb):
            im = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).resize((w * scale, h * scale), Image.NEAREST)
            img.paste(im, (x, y0))
            y0 += hmax * scale + 26
        dr.text((x, 8), {"above": "above (front down)", "front": "front -z", "back": "back +z",
                         "left": "left -x", "right": "right +x"}[s.name], fill="black", font=font)
        x += w * scale + gap
    y = H - 84
    lx = gap
    for k in range(1, 6):
        dr.rectangle([lx, y, lx + 16, y + 16], fill=KIND_RGB[k], outline="black")
        dr.text((lx + 22, y), KINDS[k - 1], fill="black", font=small)
        lx += 40 + int(dr.textlength(KINDS[k - 1], font=small))
    dr.text((lx + 20, y), "top row: kind of skin; bottom row: the parts' colours, part outlines dark; 1 stud = "
            f"{int(20 / PIX * scale)} px", fill="black", font=small)
    sa = m["skin_all"]
    line = (f"{m['name']}: {m['parts']} parts; studs showing {m.get('studs_showing_share') or 0:.0%} of studs; skin "
            f"studded {sa['studded']:.0%}, smooth flat {sa['smooth flat']:.0%}, curved/sloped {sa['curved or sloped']:.0%}, "
            f"trans {sa['transparent']:.0%}; side walls {m['side_flat_wall']:.0%}, seams {m['seams_per_stud']}/stud, "
            f"sideways-part top faces {m['side_top_faces']:.0%} of sides; holes showing {m['technic_holes_visible']}")
    dr.text((gap, y + 30), line, fill="black", font=small)
    img.save(out_png)


# ---- output -------------------------------------------------------------------------------


def line_for(m: dict) -> str:
    if "crash" in m or "skin_all" not in m:
        return f"{m['name']}: {m.get('crash', 'no parts')}"
    sa = m["skin_all"]
    return (f"{m['name']} [{m['group']}]: {m['parts']} parts {m['kinds']} kinds; studs showing "
            f"{m['studs_showing_share']:.0%} ({m['studs_showing']}/{m['studs']}); skin stud {sa['studded']:.0%} "
            f"flat {sa['smooth flat']:.0%} curved {sa['curved or sloped']:.0%} trans {sa['transparent']:.0%}; "
            f"above stud {m['skin_above']['studded']:.0%}; sides wall {m['side_flat_wall']:.0%} seams "
            f"{m['seams_per_stud']}/stud sidetop {m['side_top_faces']:.0%}; steps {m['steps_per_100_studs2']}; "
            f"sideways {m['built_sideways']:.0%}; free members {m['free_members']} bar {m['free_member_bar_share']}; "
            f"slab {m['slab_median_plates']} pl; holes {m['technic_holes_visible']}; colours>=5% {m['colours_5pct']} "
            f"primary {m['primary_share']:.0%} patch {m['patch_coherence']}; {m['seconds']['total']:.2f}s")


def run(out_json: str, paths: list[str], pictures: str | None = None) -> list[dict]:
    lib = library()
    rows = []
    for path in paths:
        try:
            m = measure(path, lib, pictures)
        except Exception as e:  # record and go on
            m = dict(name=os.path.basename(path), path=path, crash=f"{type(e).__name__}: {e}")
        rows.append(m)
        print(line_for(m), flush=True)
    json.dump(rows, open(out_json, "w"), indent=1)
    return rows


# ---- the table ----------------------------------------------------------------------------

# (column, label, how to read it from a row)
COLUMNS = [
    ("studs_showing_share", "studs showing (of studs)", lambda m: m.get("studs_showing_share")),
    ("up_studs_showing", "up studs showing", lambda m: (m.get("studs_by_direction") or {}).get("up", {}).get("share")),
    ("studs_showing_per_100_parts", "studs showing / 100 parts", lambda m: m.get("studs_showing_per_100_parts")),
    ("above_studded", "from above: studded", lambda m: m["skin_above"]["studded"]),
    ("above_flat", "from above: smooth flat", lambda m: m["skin_above"]["smooth flat"]),
    ("above_curved", "from above: curved/sloped", lambda m: m["skin_above"]["curved or sloped"]),
    ("skin_studded", "skin: studded", lambda m: m["skin_all"]["studded"]),
    ("skin_flat", "skin: smooth flat", lambda m: m["skin_all"]["smooth flat"]),
    ("skin_curved", "skin: curved/sloped", lambda m: m["skin_all"]["curved or sloped"]),
    ("side_flat_wall", "sides: flat wall", lambda m: m["side_flat_wall"]),
    ("side_curved", "sides: curved/sloped", lambda m: m["side_curved"]),
    ("seams_per_stud", "sides: seams per stud of height", lambda m: m["seams_per_stud"]),
    ("steps_per_100_studs2", "steps per 100 studs2 (above)", lambda m: m["steps_per_100_studs2"]),
    ("step_edge_share", "step edges / outline (above)", lambda m: m["step_edge_share"]),
    ("built_sideways", "stud parts not upright", lambda m: m["built_sideways"]),
    ("side_top_faces", "sides: top faces of sideways parts", lambda m: m["side_top_faces"]),
    ("free_members_per_100_parts", "free members / 100 parts", lambda m: m["free_members_per_100_parts"]),
    ("free_member_bar_share", "free members bar-thin", lambda m: m["free_member_bar_share"]),
    ("free_member_median_thickness", "free member median thickness LDU", lambda m: m["free_member_median_thickness"]),
    ("slab_median_plates", "slab thickness (plates)", lambda m: m["slab_median_plates"]),
    ("technic_holes_visible", "Technic holes showing", lambda m: m["technic_holes_visible"]),
    ("colours_5pct", "colours >= 5% of skin", lambda m: m["colours_5pct"]),
    ("primary_share", "classic primaries (skin)", lambda m: m["primary_share"]),
    ("classic_palette_share", "classic palette (skin)", lambda m: m.get("classic_palette_share")),
    ("old_grey_share_of_greys", "old greys of greys", lambda m: m.get("old_grey_share_of_greys")),
    ("side_colour_edges_horizontal", "side colour edges horizontal", lambda m: m.get("side_colour_edges_horizontal")),
    ("outline_on_axis", "outline on axis", lambda m: m.get("outline_on_axis")),
    ("trans_share", "transparent (skin)", lambda m: m["trans_share"]),
    ("patch_coherence", "colour patch coherence", lambda m: m["patch_coherence"]),
    ("trans_glazing_area_share", "trans skin that is glazing", lambda m: m["trans_glazing_area_share"]),
    ("parts", "parts", lambda m: m["parts"]),
    ("kinds_per_100", "kinds / 100 parts", lambda m: round(100 * m["kinds"] / m["parts"], 1)),
    ("parts_per_stud3", "parts per stud3 of box", lambda m: m["parts_per_stud3"]),
    ("small_share", "1x1 and 1x2 share", lambda m: m["small_share"]),
]
SHORT = {
    "studs_showing_share": "stud%", "up_studs_showing": "up%", "studs_showing_per_100_parts": "st/100",
    "above_studded": "A.st", "above_flat": "A.fl", "above_curved": "A.cu", "skin_studded": "S.st",
    "skin_flat": "S.fl", "skin_curved": "S.cu", "side_flat_wall": "wall", "side_curved": "sd.cu",
    "seams_per_stud": "seam", "steps_per_100_studs2": "step", "step_edge_share": "stepE", "built_sideways": "sidew",
    "side_top_faces": "sdTop", "free_members_per_100_parts": "mem/100", "free_member_bar_share": "bar",
    "free_member_median_thickness": "memT", "slab_median_plates": "slab", "technic_holes_visible": "holes",
    "colours_5pct": "col5", "primary_share": "prim", "classic_palette_share": "clas", "old_grey_share_of_greys": "oldG",
    "side_colour_edges_horizontal": "hEdge", "outline_on_axis": "axOut", "trans_share": "trans", "patch_coherence": "patch",
    "trans_glazing_area_share": "glaz", "parts": "parts", "kinds_per_100": "kind%", "parts_per_stud3": "dens",
    "small_share": "small",
}
VEHICLES = {"31072": "car", "75892": "car", "75895": "car", "76897": "car", "40433": "car", "60067": "helicopter",
            "31045-aircraft": "aircraft", "31066-shuttle": "aircraft"}


def robust(vals: list[float]) -> tuple[float, float]:
    """Median and spread (interquartile range / 1.349, a standard deviation if normal)."""
    v = np.array(vals, dtype=float)
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return float(med), float((q3 - q1) / 1.349)


def fmtv(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}" if abs(v) < 10 else f"{v:.0f}"
    return str(v)


def table(json_path: str, md_path: str) -> None:
    rows = [m for m in json.load(open(json_path)) if "skin_all" in m]
    seen: dict[str, str] = {}
    order = {"official": 0, "official-extra": 1, "ai-free": 2, "ai-study": 3, "other": 4}
    for m in sorted(rows, key=lambda m: order.get(m["group"], 9)):
        m["name"] = name_of(m["path"])
        c = m.get("content") or content_of(m["path"])
        m["same_as"] = seen.get(c)
        seen.setdefault(c, m["name"])
    # the earlier study's builds that are also in the projects folder count once
    groups = {"official": [m for m in rows if m["group"] == "official"],
              "ai": [m for m in rows if m["group"] in ("ai-free", "ai-study") and not m["same_as"]],
              "ai-free": [m for m in rows if m["group"] == "ai-free"]}
    out = []
    head = ["model", "grp"] + [SHORT[c] for c, _, _ in COLUMNS]
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "---|" * len(head))

    for m in sorted(rows, key=lambda m: (order.get(m["group"], 9), m["name"])):
        if m["same_as"]:
            continue
        out.append("| " + " | ".join([m["name"], m["group"]] + [fmtv(f(m)) for _, _, f in COLUMNS]) + " |")
    dup = [f"{m['name']} = {m['same_as']}" for m in rows if m["same_as"]]
    for g, ms in (("official", groups["official"]), ("ai (all, distinct)", groups["ai"]),
                  ("ai-free", groups["ai-free"]),
                  ("ai-study (not also in projects)", [m for m in groups["ai"] if m["group"] == "ai-study"])):
        meds = []
        for _, _, f in COLUMNS:
            vs = [f(m) for m in ms if f(m) is not None]
            meds.append(fmtv(round(float(np.median(vs)), 3)) if vs else "-")
        out.append("| **median " + g + f" ({len(ms)})** | | " + " | ".join(meds) + " |")
    out.append("")
    out.append("Columns: " + "; ".join(f"{SHORT[c]} = {lab}" for c, lab, _ in COLUMNS))
    out.append("")
    out.append("Left out as the same build (identical part lines) already listed: " + "; ".join(dup))
    out.append("")
    cess = next((m for m in rows if m["name"] == "cessna-172-skyhawk"), None)
    veh = [m for m in rows if m["name"] in VEHICLES]
    for ai_name in ("ai", "ai-free"):
        separation(out, groups["official"], groups[ai_name], ai_name, cess, veh)
    cessna(out, groups["official"], cess, veh)
    open(md_path, "w").write("\n".join(out) + "\n")
    print("\n".join(out))


def separation(out: list[str], off: list[dict], ai: list[dict], ai_name: str, cess, veh) -> None:
    sep = []
    for c, lab, f in COLUMNS:
        if c in ("parts",):
            continue
        vo = [f(m) for m in off if f(m) is not None]
        va = [f(m) for m in ai if f(m) is not None]
        if len(vo) < 4 or len(va) < 4:
            continue
        mo, so = robust(vo)
        ma, sa = robust(va)
        spread = (so + sa) / 2
        # a measure whose spread is zero in both groups: use the pooled range instead
        if spread <= 1e-9:
            spread = (max(vo + va) - min(vo + va)) / 4 or 1.0
        # how many official models lie beyond the AI median, on the official side
        side = 1 if mo > ma else -1
        overlap = sum(1 for v in vo if (v - ma) * side <= 0) / len(vo)
        cv = f(cess) if cess else None
        vv = [f(m) for m in veh if f(m) is not None]
        mv = float(np.median(vv)) if vv else None
        sep.append((abs(mo - ma) / spread, c, lab, mo, ma, cv, mv, so, overlap))
    sep.sort(key=lambda x: -x[0])
    out.append(f"## Measures ranked by how far official models ({len(off)}) are from AI builds ({ai_name}, {len(ai)})")
    out.append("")
    out.append("Separation = |median official - median AI| / mean of the two groups' spreads (IQR/1.349). "
               "'Official at or past the AI median' = share of official models on the AI side of the AI median.")
    out.append("")
    out.append("| rank | measure | separation | official median | AI median | Cessna | official vehicles median | official at or past AI median |")
    out.append("|---|---|---|---|---|---|---|---|")
    for k, (s, c, lab, mo, ma, cv, mv, so, ov) in enumerate(sep, 1):
        out.append(f"| {k} | {lab} | {s:.2f} | {fmtv(round(mo, 3))} | {fmtv(round(ma, 3))} | {fmtv(cv)} | "
                   f"{fmtv(None if mv is None else round(mv, 3))} | {ov:.0%} |")
    out.append("")


def cessna(out: list[str], off: list[dict], cess, veh) -> None:
    if cess and veh:
        out.append("## The Cessna against the official vehicles")
        out.append("")
        out.append("Vehicles: " + ", ".join(f"{m['name']} ({VEHICLES[m['name']]})" for m in veh) + ". Distance = "
                   "(Cessna - vehicles' median) / the official group's spread.")
        out.append("")
        out.append("| measure | Cessna | vehicles median | vehicles range | distance |")
        out.append("|---|---|---|---|---|")
        dist = []
        for c, lab, f in COLUMNS:
            cv = f(cess)
            vv = [f(m) for m in veh if f(m) is not None]
            vo = [f(m) for m in off if f(m) is not None]
            if cv is None or len(vv) < 3:
                continue
            _, so = robust(vo)
            mv = float(np.median(vv))
            sp = so if so > 1e-9 else ((max(vo) - min(vo)) / 4 or 1.0)
            dist.append(((cv - mv) / sp, lab, cv, mv, min(vv), max(vv)))
        dist.sort(key=lambda x: -abs(x[0]))
        for d, lab, cv, mv, a, b in dist:
            out.append(f"| {lab} | {fmtv(cv)} | {fmtv(round(mv, 3))} | {fmtv(a)} to {fmtv(b)} | {d:+.1f} |")


# ---- sanity models ------------------------------------------------------------------------

I3 = "1 0 0 0 1 0 0 0 1"


def sanity(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    models: dict[str, list[str]] = {}
    # a 6 x 6 plate alone: every stud showing
    models["plate"] = [f"1 15 0 0 0 {I3} 3958.dat"]
    # the same plate covered by nine 2 x 2 tiles: no stud showing, the top all smooth
    models["plate-tiled"] = models["plate"] + [f"1 15 {x} -8 {z} {I3} 3068b.dat" for x in (-40, 0, 40) for z in (-40, 0, 40)]
    # a wall of 1 x 4 bricks, 8 long and 4 courses high, running bond (half bricks at the ends)
    wall = []
    for k in range(4):
        y = -24 * k
        if k % 2 == 0:
            wall += [f"1 4 {x} {y} 0 {I3} 3010.dat" for x in (-40, 40)]
        else:
            wall += [f"1 4 {x} {y} 0 {I3} 3004.dat" for x in (-60, 60)] + [f"1 4 0 {y} 0 {I3} 3010.dat"]
    models["brick-wall"] = wall
    # the same length and height in 1 x 4 plates stacked with bare edges (12 plates high)
    models["plate-stack"] = [f"1 14 {x} {-8 * k} 0 {I3} 3710.dat" for k in range(12) for x in (-40, 40)]
    # a curved-slope roof: a 2 x 4 brick under two 2 x 2 curved slopes
    models["curved-roof"] = [f"1 1 0 0 0 {I3} 3001.dat", f"1 1 -20 0 0 {I3} 15068.dat", f"1 1 20 0 0 {I3} 15068.dat"]
    # a staircase of 2 x 4 plates, each one stud back from the last
    models["plate-stairs"] = [f"1 2 0 {-8 * k} {20 * k} {I3} 3020.dat" for k in range(4)]
    # a row of three Technic bricks 1 x 2 with holes, one hole filled by a pin
    models["technic-bricks"] = [f"1 0 {x} 0 0 {I3} 3700.dat" for x in (-40, 0, 40)] + [
        "1 7 0 10 -10 0 0 1 0 1 0 -1 0 0 3673.dat"]
    paths = []
    for k, v in models.items():
        p = os.path.join(out_dir, k + ".ldr")
        open(p, "w").write("\n".join(v) + "\n")
        paths.append(p)
    rows = run(os.path.join(out_dir, "sanity.json"), paths, out_dir)
    for m in rows:
        if "skin_all" in m:
            print(f"  {m['name']}: studs {m['studs_showing']}/{m['studs']}; above {m['skin_above']}; sides {m['skin_sides']}; "
                  f"wall {m['side_flat_wall']} seams {m['seams_per_stud']} steps {m['steps_per_100_studs2']} "
                  f"({m['step_edge_share']}); holes {m['technic_holes_visible']}/{m['technic_holes']} filled "
                  f"{m['technic_holes_filled']}; members {m['members']} free {m['free_members']}")


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    if argv[0] == "--table":
        table(argv[1], argv[2])
    elif argv[0] == "--sanity":
        sanity(argv[1])
    elif argv[0] == "--pictures":
        d = argv[1]
        os.makedirs(d, exist_ok=True)
        run(os.path.join(d, "pictures.json"), argv[2:], d)
    else:
        run(argv[0], argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
