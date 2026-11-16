"""Geometry analysis of one LDraw part: bbox, body bbox, footprint, studs, slope.

Usage (debug): python3 -I analyze_part.py <ldraw_root> <part.dat> [...]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ldraw_geom import Library, bbox  # noqa: E402


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def analyze(lib, fname):
    flat = lib.flatten(fname)
    allpts = [p for p, _ in flat["points"]]
    body_pts = [p for p, s in flat["points"] if not s]
    full = bbox(allpts)
    body = bbox(body_pts)
    ymax = body["max"][1]
    # footprint: outline of the bottom-most geometry (within 0.5 LDU of the lowest point)
    bottom = [p for p in body_pts if p[1] >= ymax - 0.5]
    fb = bbox(bottom)
    # signed volume to fix the normal convention for this mesh
    vol = 0.0
    for a, b, c, _s in flat["tris"]:
        vol += dot(a, cross(b, c)) / 6.0
    sign = 1.0 if vol >= 0 else -1.0
    # sloped faces (non-stud geometry)
    acc = {}
    for a, b, c, s in flat["tris"]:
        if s:
            continue
        n = cross(sub(b, a), sub(c, a))
        area2 = math.sqrt(dot(n, n))
        if area2 < 1e-9:
            continue
        n = (n[0] * sign / area2, n[1] * sign / area2, n[2] * sign / area2)
        h = math.hypot(n[0], n[2])
        if h < 0.1 or abs(n[1]) < 0.1:
            continue
        faces = "up" if n[1] < 0 else "down"  # -Y is up
        # dominant horizontal axis of the outward normal
        if abs(n[0]) >= abs(n[2]):
            d = "+x" if n[0] > 0 else "-x"
        else:
            d = "+z" if n[2] > 0 else "-z"
        ang = math.degrees(math.atan2(h, abs(n[1])))
        k = (faces, d)
        e = acc.setdefault(k, [0.0, 0.0, 0.0, 99.0])
        area = area2 / 2
        e[0] += area
        e[1] += ang * area
        e[2] = max(e[2], ang)
        e[3] = min(e[3], ang)
    slopes = {
        f"{k[0]}:{k[1]}": {
            "area": round(v[0], 1),
            "mean_angle": round(v[1] / v[0], 2),
            "max_angle": round(v[2], 2),
            "min_angle": round(v[3], 2),
        }
        for k, v in acc.items()
    }
    return {
        "full": full,
        "body": body,
        "foot": fb,
        "studs": flat["studs"],
        "tubes": flat["tubes"],
        "refs": sorted(flat["refs"]),
        "volume": vol,
        "slopes": slopes,
        "uncertified": flat["uncertified"],
        "ntris": len(flat["tris"]),
    }


if __name__ == "__main__":
    lib = Library(sys.argv[1])
    for f in sys.argv[2:]:
        r = analyze(lib, f)
        print("==", f, lib.header(f)["description"])
        for k in ("full", "body", "foot"):
            print(" ", k, [round(v, 2) for v in r[k]["min"]], [round(v, 2) for v in r[k]["max"]])
        print("  vol", round(r["volume"]), "uncert", r["uncertified"], "tris", r["ntris"])
        for s in r["studs"]:
            print(
                "  stud", s["prim"], [round(v, 2) for v in s["pos"]], [round(v, 2) for v in s["up"]]
            )
        for s in r["tubes"]:
            print("  tube", s["prim"], [round(v, 2) for v in s["pos"]])
        for k, v in sorted(r["slopes"].items(), key=lambda kv: -kv[1]["area"])[:6]:
            print("  slope", k, v)
        print("  refs", r["refs"][:30])
    if lib.missing:
        print("MISSING", lib.missing)
