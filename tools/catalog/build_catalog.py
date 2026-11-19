"""Build parts.json and colours.json from the downloaded sources.

Usage:
  python3 -I build_catalog.py <ldraw_root> <rebrickable_csv_dir> <web_dir> <out_dir>

  ldraw_root          directory containing LDConfig.ldr, parts/, p/  (from complete.zip)
  rebrickable_csv_dir colors.csv, parts.csv, elements.csv (gunzipped)
  web_dir             bl_colors.html (BrickLink colour guide), setdb_colors.html
                      (merlinsbricks.com/colors), bl_parts/<id>.html (BrickLink catalog pages)
  out_dir             where parts.json / colours.json / build_report.json are written
"""

import csv
import html
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_part import analyze  # noqa: E402
from ldraw_geom import Library  # noqa: E402

# (ldraw stem, rebrickable part_num, kind, what the request listed)
PARTS = [
    ("3005", "3005", "brick", "3005"),
    ("3004", "3004", "brick", "3004"),
    ("3622", "3622", "brick", "3622"),
    ("3010", "3010", "brick", "3010"),
    ("3009", "3009", "brick", "3009"),
    ("3008", "3008", "brick", "3008"),
    ("3003", "3003", "brick", "3003"),
    ("3002", "3002", "brick", "3002"),
    ("3001", "3001", "brick", "3001"),
    ("2456", "2456", "brick", "2456"),
    ("3007", "3007", "brick", "3007"),
    ("3024", "3024", "plate", "3024"),
    ("3023b", "3023", "plate", "3023"),
    ("3623", "3623", "plate", "3623"),
    ("3710", "3710", "plate", "3710"),
    ("3666", "3666", "plate", "3666"),
    ("3460", "3460", "plate", "3460"),
    ("3022", "3022", "plate", "3022"),
    ("3021", "3021", "plate", "3021"),
    ("3020", "3020", "plate", "3020"),
    ("3795", "3795", "plate", "3795"),
    ("3034", "3034", "plate", "3034"),
    ("3070b", "3070b", "tile", "3070b"),
    ("3069b", "3069b", "tile", "3069b"),
    ("63864", "63864", "tile", "63864"),
    ("2431", "2431", "tile", "2431"),
    ("6636", "6636", "tile", "6636"),
    ("4162", "4162", "tile", "4162"),
    ("3068b", "3068b", "tile", "3068b"),
    ("26603", "26603", "tile", "26603"),
    ("87079", "87079", "tile", "87079"),
    ("3040b", "3040b", "slope", "3040b"),
    ("3039", "3039", "slope", "3039"),
    ("54200", "54200", "slope", "54200"),
    ("85984", "85984", "slope", "85984"),
    ("3665b", "3665", "slope_inverted", "3665"),
    ("3660b", "3660", "slope_inverted", "3660"),
    ("4287c", "4287c", "slope_inverted", "4287"),
    ("4286", "4286", "slope", "4286"),
    ("11477", "11477", "curved_slope", "11477"),
    ("6141", "6141", "round_plate", "4073"),
    ("98138", "98138", "round_tile", "98138"),
    ("3062b", "3062b", "round_brick", "3062b"),
    ("6143", "3941", "round_brick", "3941"),
    ("59900", "59900", "cone", "4589"),
    ("4740", "4740", "dish", "4740"),
    ("87087", "87087", "side_stud", "87087"),
    ("4733", "4733", "side_stud", "4733"),
    ("2412b", "2412b", "tile", "2412b"),
    ("60897", "60897", "detail", "plate 1x1 with clip"),
    ("15573", "15573", "detail", "15573 or 3794"),
    ("14769", "14769", "round_tile", "14769"),
]

# Footprint overrides where a protrusion is not part of the stud grid footprint.
FOOTPRINT_OVERRIDE = {
    "60897": (
        (-10.0, -10.0),
        (10.0, 10.0),
        "footprint is the 1x1 plate; the clip protrudes to z=-24.03",
    ),
}

# BrickLink colour names (as in the BrickLink colour guide) we want.
SOLID_COLOURS = [
    "White",
    "Black",
    "Red",
    "Blue",
    "Yellow",
    "Green",
    "Light Bluish Gray",
    "Dark Bluish Gray",
    "Reddish Brown",
    "Tan",
    "Dark Tan",
    "Orange",
    "Dark Red",
    "Dark Blue",
    "Lime",
    "Bright Pink",
    "Dark Pink",
    "Medium Azure",
    "Dark Azure",
    "Bright Light Orange",
    "Dark Green",
    "Sand Green",
    "Olive Green",
    "Medium Nougat",
    "Nougat",
    "Light Nougat",
    "Dark Orange",
    "Dark Brown",
    "Bright Light Yellow",
    "Medium Blue",
    "Bright Light Blue",
    "Sand Blue",
    "Dark Purple",
    "Medium Lavender",
    "Lavender",
    "Bright Green",
]
TRANS_ALWAYS = ["Trans-Clear"]
TRANS_CANDIDATES = [
    "Trans-Red",
    "Trans-Light Blue",
    "Trans-Yellow",
    "Trans-Orange",
    "Trans-Dark Blue",
    "Trans-Green",
]
N_EXTRA_TRANS = 3
CURRENT_YEAR_MIN = 2025  # Rebrickable colors.csv y2 must reach this to count as current


def r3(v):
    return round(v + 0.0, 3)


# ---------------------------------------------------------------- colours
def parse_ldconfig(path):
    out = {}
    prev = ""
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(
            r"0 !COLOUR (\S+)\s+CODE\s+(\d+)\s+VALUE (#[0-9A-Fa-f]{6})\s+EDGE (\S+)(.*)", ln
        )
        if m:
            legoid = None
            lm = re.search(r"LEGOID\s+(.+)", prev)
            if lm:
                legoid = lm.group(1).strip()
            rest = m.group(5)
            out[int(m.group(2))] = {
                "name": m.group(1),
                "rgb": m.group(3).upper(),
                "edge": m.group(4),
                "alpha": int(re.search(r"ALPHA (\d+)", rest).group(1)) if "ALPHA" in rest else None,
                "material": rest.strip(),
                "legoid": legoid,
            }
        prev = ln
    return out


def parse_bl_colour_guide(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    pairs = re.findall(r'fullWidth__ZxMxI">([^<]+)</span><span[^>]*idSection[^>]*>(\d+)</span>', t)
    return {html.unescape(n).strip(): int(i) for n, i in pairs}


def parse_setdb(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    rows = {}
    for r in re.findall(r"<tr>(.*?)</tr>", t, re.S):
        c = [
            html.unescape(re.sub("<[^>]+>", "", x)).strip()
            for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        ]
        if len(c) >= 8:
            rows[c[0]] = {
                "name": c[0],
                "bricklink": c[2],
                "lego": c[3],
                "rebrickable": c[4],
                "gobricks": c[5],
                "ldraw": c[6],
                "brickowl": c[7],
            }
    return rows


def lead_int(s):
    m = re.match(r"\s*(\d+)", s or "")
    return int(m.group(1)) if m else None


def norm_name(s):
    return re.sub(r"[\s_\-]+", " ", s).lower().replace("grey", "gray").strip()


# ---------------------------------------------------------------- bricklink parts
def parse_bl_part(path):
    if not os.path.exists(path):
        return None
    t = open(path, encoding="utf-8", errors="replace").read()
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    title = html.unescape(title.group(1)).strip() if title else ""
    if "Not Found" in title or ": Part " not in title:
        return {"exists": False, "title": title}
    m = re.match(r"(.*) : Part (\S+) \| BrickLink", title)
    alt = re.search(r"Alternate Item No: <span[^>]*>([^<]*)</span>", t)
    item = re.search(r"Item No: <span[^>]*>([^<]*)</span>", t)
    return {
        "exists": True,
        "title": title,
        "name": m.group(1) if m else title,
        "item_no": item.group(1).strip() if item else (m.group(2) if m else None),
        "alternates": [a.strip() for a in alt.group(1).split(",") if a.strip()] if alt else [],
    }


# ---------------------------------------------------------------- geometry helpers
OPP = {"+x": "-x", "-x": "+x", "+z": "-z", "-z": "+z"}


def near(a, b, tol=0.6):
    return abs(a - b) <= tol


def main():
    ldroot, rbdir, webdir, outdir = sys.argv[1:5]
    lib = Library(ldroot)
    report = {"warnings": []}

    # ---- colours
    ldc = parse_ldconfig(os.path.join(ldroot, "LDConfig.ldr"))
    blg = parse_bl_colour_guide(os.path.join(webdir, "bl_colors.html"))
    setdb = parse_setdb(os.path.join(webdir, "setdb_colors.html"))
    rbcol = {
        int(r["id"]): r
        for r in csv.DictReader(open(os.path.join(rbdir, "colors.csv"), encoding="utf-8"))
    }

    colour_recs = []
    for blname in SOLID_COLOURS + TRANS_ALWAYS + TRANS_CANDIDATES:
        checks = []
        bl_id = blg.get(blname)
        row = setdb.get(blname)
        if bl_id is None or row is None:
            report["warnings"].append(f"colour {blname}: missing in BL guide or SetDB")
            continue
        sd_bl = lead_int(row["bricklink"])
        ld_code = lead_int(row["ldraw"])
        rb_id = lead_int(row["rebrickable"])
        checks.append(("bl_guide_id == setdb_bl_id", bl_id == sd_bl))
        ld = ldc.get(ld_code)
        rb = rbcol.get(rb_id)
        checks.append(("ldraw code exists in LDConfig", ld is not None))
        checks.append(("rebrickable id exists in colors.csv", rb is not None))
        if rb:
            checks.append(
                ("rebrickable name == bricklink name", norm_name(rb["name"]) == norm_name(blname))
            )
            if ld:
                # RGB agreement between Rebrickable and LDConfig (loose; renders differ)
                a = [int(rb["rgb"][i : i + 2], 16) for i in (0, 2, 4)]
                b = [int(ld["rgb"][1 + i : 3 + i], 16) for i in (0, 2, 4)]
                dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
                checks.append(
                    (
                        f"RGB distance RB vs LDraw = {dist:.0f} (< 90; loose, renders differ)",
                        dist < 90,
                    )
                )
        if ld:
            checks.append(
                ("ldraw name ~ bricklink name", norm_name(ld["name"]) == norm_name(blname))
            )
            # LEGO colour number: SetDB 'LEGO' column vs LDConfig '// LEGOID' comment
            sd_lego = lead_int(row["lego"])
            ld_lego = lead_int(ld["legoid"]) if ld["legoid"] else None
            if sd_lego is not None and ld_lego is not None:
                checks.append(
                    (f"LEGO id SetDB {sd_lego} == LDConfig LEGOID {ld_lego}", sd_lego == ld_lego)
                )
        transparent = bool(ld and ld["alpha"] is not None)
        current = bool(rb and int(rb["y2"] or 0) >= CURRENT_YEAR_MIN)
        colour_recs.append(
            {
                "ldraw_code": ld_code,
                "name": ld["name"] if ld else None,
                "rgb": ld["rgb"] if ld else None,
                "bricklink_id": bl_id,
                "bricklink_name": blname,
                "rebrickable_id": rb_id,
                "rebrickable_name": rb["name"] if rb else None,
                "lego_id": ld["legoid"] if ld else None,
                "transparent": transparent,
                "alpha": ld["alpha"] if ld else None,
                "rebrickable_years": [int(rb["y1"]), int(rb["y2"])] if rb and rb["y1"] else None,
                "current_production": current,
                "checks": {k: v for k, v in checks},
            }
        )

    # ---- elements (real part+colour combinations)
    rb_to_ld = {c["rebrickable_id"]: c["ldraw_code"] for c in colour_recs}
    rbparts = {
        r["part_num"]: r
        for r in csv.DictReader(open(os.path.join(rbdir, "parts.csv"), encoding="utf-8"))
    }
    combos = {}
    for r in csv.DictReader(open(os.path.join(rbdir, "elements.csv"), encoding="utf-8")):
        cid = int(r["color_id"])
        if cid in rb_to_ld:
            combos.setdefault(r["part_num"], set()).add(rb_to_ld[cid])

    # ---- parts
    part_recs = []
    for stem, rbid, kind, asked in PARTS:
        fname = stem + ".dat"
        hdr = lib.header(fname)
        raw = lib.read(fname) or []
        lic = next(
            (l[len("0 !LICENSE") :].strip() for l in raw if l.startswith("0 !LICENSE")), None
        )
        author = next(
            (l[len("0 Author:") :].strip() for l in raw if l.startswith("0 Author:")), None
        )
        g = analyze(lib, fname)
        full, body = g["full"], g["body"]
        if stem in FOOTPRINT_OVERRIDE:
            (fx0, fz0), (fx1, fz1), fnote = FOOTPRINT_OVERRIDE[stem]
        else:
            fx0, fz0, fx1, fz1, fnote = (
                body["min"][0],
                body["min"][2],
                body["max"][0],
                body["max"][2],
                None,
            )
        sx = round((fx1 - fx0) / 20)
        sz = round((fz1 - fz0) / 20)
        if abs((fx1 - fx0) - 20 * sx) > 3 or abs((fz1 - fz0) - 20 * sz) > 3:
            report["warnings"].append(
                f"{stem}: footprint not near stud multiple {fx1 - fx0}x{fz1 - fz0}"
            )
        by0, by1 = body["min"][1], body["max"][1]
        h_ldu = by1 - by0
        hp = h_ldu / 8
        h_plates = int(round(hp)) if abs(hp - round(hp)) < 0.1 else round(hp, 2)

        # origin description
        cx, cz = (fx0 + fx1) / 2, (fz0 + fz1) / 2
        if near(cx, 0) and near(cz, 0):
            xz = "centre of footprint in X/Z"
        else:
            xz = f"X/Z offset from footprint centre: origin is at dx={r3(-cx)}, dz={r3(-cz)} LDU from centre (footprint x {r3(fx0)}..{r3(fx1)}, z {r3(fz0)}..{r3(fz1)})"
        if near(by0, 0):
            yv = f"Y=0 is the top face of the body (body spans y 0..{r3(by1)})"
        elif near(by1, 0):
            yv = f"Y=0 is the BOTTOM face of the body (body spans y {r3(by0)}..0)"
        else:
            yv = f"body spans y {r3(by0)}..{r3(by1)}"
        origin_note = f"{xz}; {yv}"

        # studs
        top, offgrid, side, prims = [], [], [], {}
        for s in g["studs"]:
            ux, uy, uz = s["up"]
            x, y, z = s["pos"]
            cell = [int(math.floor((x - fx0) / 20 + 1e-6)), int(math.floor((z - fz0) / 20 + 1e-6))]
            # stud centre in cell units; on-grid studs sit at i + 0.5
            fc = [(x - fx0) / 20 - 0.5, (z - fz0) / 20 - 0.5]
            on_grid = all(abs(v - round(v)) < 0.03 for v in fc)
            prims[s["prim"]] = prims.get(s["prim"], 0) + 1
            if near(uy, -1, 0.01):
                if near(y, by0, 0.6):
                    if not on_grid:
                        fr = [round(v, 3) for v in fc]
                        if fr not in offgrid:
                            offgrid.append(fr)
                    elif cell not in top:
                        top.append(cell)
                else:
                    report["warnings"].append(
                        f"{stem}: upward stud primitive {s['prim']} at y={y} not on top face (ignored)"
                    )
            elif abs(uy) < 0.01:
                d = ("+x" if ux > 0 else "-x") if abs(ux) > abs(uz) else ("+z" if uz > 0 else "-z")
                cell = [min(max(cell[0], 0), sx - 1), min(max(cell[1], 0), sz - 1)]
                side.append({"dir": d, "cell": cell, "y_ldu": r3(y), "primitive": s["prim"]})
            else:
                report["warnings"].append(f"{stem}: stud with odd orientation {s['up']}")
        top.sort()

        # bottom coverage (outline of geometry within 0.5 LDU of the lowest point)
        f = g["foot"]
        bx0, bz0, bx1, bz1 = f["min"][0], f["min"][2], f["max"][0], f["max"][2]
        if stem in FOOTPRINT_OVERRIDE:
            bx0, bz0, bx1, bz1 = max(bx0, fx0), max(bz0, fz0), min(bx1, fx1), min(bz1, fz1)
        bottom_cells = []
        for ix in range(sx):
            for iz in range(sz):
                cx0, cz0 = fx0 + 20 * ix, fz0 + 20 * iz
                if (
                    bx0 <= cx0 + 2.5
                    and bx1 >= cx0 + 17.5
                    and bz0 <= cz0 + 2.5
                    and bz1 >= cz0 + 17.5
                ):
                    bottom_cells.append([ix, iz])
        has_bottom = len(bottom_cells) == sx * sz

        rec = {
            "id": stem,
            "ldraw_file": fname,
            "bricklink_id": None,
            "rebrickable_id": rbid,
            "name": hdr["description"],
            "kind": kind,
            "sx": sx,
            "sz": sz,
            "h_plates": h_plates,
            "h_ldu": r3(h_ldu),
            "bbox_ldu": {"min": [r3(v) for v in full["min"]], "max": [r3(v) for v in full["max"]]},
            "body_bbox_ldu": {
                "min": [r3(v) for v in body["min"]],
                "max": [r3(v) for v in body["max"]],
            },
            "origin_note": origin_note + (f"; {fnote}" if fnote else ""),
            "studs_top": top,
            "studs_top_offgrid": sorted(offgrid),
            "studs_side": side,
            "stud_primitives": prims,
            "has_bottom_antistuds": has_bottom,
            "bottom_cells": bottom_cells,
        }

        if kind in ("slope", "slope_inverted", "curved_slope"):
            want = "down" if kind == "slope_inverted" else "up"
            cands = [(k, v) for k, v in g["slopes"].items() if k.startswith(want + ":")]
            k, v = max(cands, key=lambda kv: kv[1]["area"])
            d = k.split(":")[1]
            low = d if want == "up" else OPP[d]
            nm = re.search(r"Slope Brick (\d+)", hdr["description"])
            rec["slope"] = {
                "low_side": low,
                "thin_side": d,
                "sloped_face": want,
                "angle_deg": v["mean_angle"],
                "angle_range_deg": [v["min_angle"], v["max_angle"]],
                "nominal_angle_deg_in_ldraw_name": int(nm.group(1)) if nm else None,
                "sloped_area_ldu2": v["area"],
            }
            # sanity: studs must not sit on the low/thin side of a normal slope
            if want == "up" and top:
                axis = 0 if d[1] == "x" else 1
                n = sx if axis == 0 else sz
                for c in top:
                    if (d[0] == "-" and c[axis] == 0 and n > 1) or (
                        d[0] == "+" and c[axis] == n - 1 and n > 1
                    ):
                        report["warnings"].append(f"{stem}: stud on low side? {c} {d}")

        # BrickLink id: LDraw !KEYWORDS "BrickLink X" first, then RB id, then stem, then stripped stem
        kw_bl = [k.split(None, 1)[1] for k in hdr["keywords"] if k.lower().startswith("bricklink ")]
        kw_rb = [
            k.split(None, 1)[1] for k in hdr["keywords"] if k.lower().startswith("rebrickable ")
        ]
        tried = []
        for cand in kw_bl + [rbid, stem, re.sub(r"[a-z]$", "", stem)]:
            if cand in [t[0] for t in tried]:
                continue
            info = parse_bl_part(os.path.join(webdir, "bl_parts", cand + ".html"))
            tried.append((cand, info))
            if info and info.get("exists"):
                rec["bricklink_id"] = info["item_no"]
                rec["bricklink_name"] = info["name"]
                rec["bricklink_alternates"] = info["alternates"]
                break
        rec["bricklink_lookup"] = [
            {
                "tried": c,
                "result": ("found: " + i["name"])
                if i and i.get("exists")
                else (
                    "no primary BrickLink page (HTTP 302 redirect or not found)"
                    if i
                    else "not fetched"
                ),
            }
            for c, i in tried
        ]
        rec["ldraw_keywords_ids"] = {"bricklink": kw_bl, "rebrickable": kw_rb}
        if kw_rb and rbid not in kw_rb:
            report["warnings"].append(f"{stem}: LDraw keyword Rebrickable {kw_rb} != chosen {rbid}")
        rp = rbparts.get(rbid)
        rec["rebrickable_name"] = rp["name"] if rp else None
        if not rp:
            report["warnings"].append(f"{stem}: rebrickable id {rbid} not in parts.csv")
        rec["colours"] = sorted(combos.get(rbid, set()))
        rec["ldraw_license"] = lic
        rec["ldraw_author"] = author
        rec["requested_as"] = asked
        part_recs.append(rec)

    # ---- choose transparent colours by availability; drop non-current solids
    def avail(c):
        return sum(1 for p in part_recs if c["ldraw_code"] in p["colours"])

    for c in colour_recs:
        c["num_parts_available"] = avail(c)
    trans_c = sorted(
        [c for c in colour_recs if c["bricklink_name"] in TRANS_CANDIDATES],
        key=lambda c: -c["num_parts_available"],
    )
    keep_trans = {c["bricklink_name"] for c in trans_c[:N_EXTRA_TRANS]}
    final_colours, dropped = [], []
    for c in colour_recs:
        bn = c["bricklink_name"]
        if bn in TRANS_CANDIDATES and bn not in keep_trans:
            dropped.append(
                (
                    bn,
                    f"transparent candidate not in top {N_EXTRA_TRANS} by availability ({c['num_parts_available']})",
                )
            )
            continue
        if not c["current_production"]:
            dropped.append((bn, f"not current per Rebrickable years {c['rebrickable_years']}"))
            continue
        if not all(c["checks"].values()):
            report["warnings"].append(
                f"colour {bn}: failed checks {[k for k, v in c['checks'].items() if not v]}"
            )
        final_colours.append(c)
    keep_codes = {c["ldraw_code"] for c in final_colours}
    for p in part_recs:
        p["colours"] = [x for x in p["colours"] if x in keep_codes]
    report["dropped_colours"] = dropped

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "parts.json"), "w") as fh:
        json.dump(part_recs, fh, indent=1)
    with open(os.path.join(outdir, "colours.json"), "w") as fh:
        json.dump(final_colours, fh, indent=1)
    report["missing_ldraw_files"] = sorted(lib.missing)
    with open(os.path.join(outdir, "build_report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print(f"parts: {len(part_recs)}  colours: {len(final_colours)}")
    for w in report["warnings"]:
        print("WARN", w)
    for d in dropped:
        print("DROP", d)
    if lib.missing:
        print("MISSING", sorted(lib.missing))


if __name__ == "__main__":
    main()
