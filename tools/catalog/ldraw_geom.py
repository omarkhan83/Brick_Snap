"""Minimal LDraw part expander (no third-party deps).

Fully expands a part file through all type-1 sub-file references, applying
transforms and BFC winding (CERTIFY CW/CCW, INVERTNEXT, negative determinants).
Collects every vertex of line types 2/3/4 and the two endpoints of type 5, so
the bounding box excludes nothing. Male stud primitives are also recorded
(position + up direction) so stud positions come from geometry.
"""

import os
import re

# Male (upward-facing on the part) stud primitives in p/. Underside tubes
# (stud3*, stud4*, stud16*, stud18a, stud21a, stud22a, stud23*, stud2s*) are
# deliberately NOT here.
MALE_STUD_RE = re.compile(
    r"^(stud|studa|stud2|stud2a|stud6|stud6a|stud9|stud10|stud13|stud15|stud17|stud17a|"
    r"stud26|studel|studh|studhl|studhr|studp01|stud-logo\d?|stud2-logo\d?)\.dat$"
)
UNDERSIDE_TUBE_RE = re.compile(
    r"^(stud3a?|stud4[a-z0-9]*|stud16[a-z]*|stud18a|stud21a|stud22a|stud23d?|stud2s\w*|stud12)\.dat$"
)

IDENT = (1, 0, 0, 0, 1, 0, 0, 0, 1)


def mat_mul(a, b):
    return tuple(
        sum(a[r * 3 + k] * b[k * 3 + c] for k in range(3)) for r in range(3) for c in range(3)
    )


def mat_vec(a, v):
    return (
        a[0] * v[0] + a[1] * v[1] + a[2] * v[2],
        a[3] * v[0] + a[4] * v[1] + a[5] * v[2],
        a[6] * v[0] + a[7] * v[1] + a[8] * v[2],
    )


def det3(a):
    return (
        a[0] * (a[4] * a[8] - a[5] * a[7])
        - a[1] * (a[3] * a[8] - a[5] * a[6])
        + a[2] * (a[3] * a[7] - a[4] * a[6])
    )


class Library:
    def __init__(self, root):
        self.root = root  # directory containing parts/ and p/
        self.index = {}
        for sub in ("parts", "p"):
            base = os.path.join(root, sub)
            for dp, _dn, fns in os.walk(base):
                for fn in fns:
                    full = os.path.join(dp, fn)
                    rel = os.path.relpath(full, base).replace(os.sep, "/").lower()
                    self.index.setdefault((sub, rel), full)
        self.cache = {}
        self.missing = set()

    def find(self, name):
        key = name.strip().replace("\\", "/").lower()
        for sub in ("parts", "p"):
            if (sub, key) in self.index:
                return self.index[(sub, key)]
        return None

    def read(self, name):
        path = self.find(name)
        if path is None:
            self.missing.add(name)
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()

    def header(self, name):
        lines = self.read(name) or []
        out = {
            "description": lines[0][2:].strip() if lines else "",
            "keywords": [],
            "category": None,
        }
        for ln in lines[:60]:
            t = ln.strip()
            if t.startswith("0 !KEYWORDS"):
                out["keywords"] += [
                    k.strip() for k in t[len("0 !KEYWORDS") :].split(",") if k.strip()
                ]
            elif t.startswith("0 !CATEGORY"):
                out["category"] = t[len("0 !CATEGORY") :].strip()
            elif t.startswith("0 !LDRAW_ORG"):
                out["ldraw_org"] = t[len("0 !LDRAW_ORG") :].strip()
        return out

    def flatten(self, name):
        """Return dict with tris (CCW-normalised where certified), points, studs, tubes
        in the file's local coordinates."""
        key = name.strip().replace("\\", "/").lower()
        if key in self.cache:
            return self.cache[key]
        lines = self.read(name)
        res = {
            "tris": [],
            "points": [],
            "studs": [],
            "tubes": [],
            "refs": set(),
            "uncertified": False,
        }
        self.cache[key] = res  # guard against recursion
        if lines is None:
            return res
        winding = None  # 'CCW' / 'CW' / None (uncertified)
        certified = False
        invert_next = False
        for ln in lines:
            parts = ln.split()
            if not parts:
                continue
            lt = parts[0]
            if lt == "0":
                if len(parts) >= 2 and parts[1] == "BFC":
                    toks = parts[2:]
                    if "NOCERTIFY" in toks:
                        certified = False
                        winding = None
                    if "CERTIFY" in toks:
                        certified = True
                        winding = "CCW"
                    if "CW" in toks and certified:
                        winding = "CW"
                    if "CCW" in toks and certified:
                        winding = "CCW"
                    if "INVERTNEXT" in toks:
                        invert_next = True
                continue
            try:
                nums = [float(x) for x in parts[1:]]
            except ValueError:
                # type 1 last token is file name
                nums = None
            if lt == "1":
                vals = [float(x) for x in parts[2:14]]
                sub = " ".join(parts[14:])
                x, y, z = vals[0:3]
                m = tuple(vals[3:12])
                subname = os.path.basename(sub.replace("\\", "/")).lower()
                res["refs"].add(sub.replace("\\", "/").lower())
                child = self.flatten(sub)
                flip = (det3(m) < 0) != invert_next
                invert_next = False
                if not certified or child["uncertified"]:
                    res["uncertified"] = True

                def tf(p):
                    q = mat_vec(m, p)
                    return (q[0] + x, q[1] + y, q[2] + z)

                if MALE_STUD_RE.match(subname):
                    up = mat_vec(m, (0.0, -1.0, 0.0))
                    res["studs"].append(
                        {"prim": subname, "pos": (x, y, z), "up": up, "tris_from": len(res["tris"])}
                    )
                if UNDERSIDE_TUBE_RE.match(subname):
                    res["tubes"].append({"prim": subname, "pos": (x, y, z)})
                for s in child["studs"]:
                    up = mat_vec(m, s["up"])
                    res["studs"].append({"prim": s["prim"], "pos": tf(s["pos"]), "up": up})
                for s in child["tubes"]:
                    res["tubes"].append({"prim": s["prim"], "pos": tf(s["pos"])})
                is_stud = bool(MALE_STUD_RE.match(subname))
                for t in child["tris"]:
                    a, b, c = tf(t[0]), tf(t[1]), tf(t[2])
                    tri = (a, c, b) if flip else (a, b, c)
                    res["tris"].append((tri[0], tri[1], tri[2], t[3] or is_stud))
                for p in child["points"]:
                    res["points"].append((tf(p[0]), p[1] or is_stud))
                continue
            invert_next = False
            if nums is None:
                continue
            if lt == "2" and len(nums) >= 7:
                pts = [tuple(nums[1:4]), tuple(nums[4:7])]
                res["points"] += [(p, False) for p in pts]
            elif lt == "5" and len(nums) >= 7:
                # only the two real endpoints; control points are not geometry
                pts = [tuple(nums[1:4]), tuple(nums[4:7])]
                res["points"] += [(p, False) for p in pts]
            elif lt == "3" and len(nums) >= 10:
                a, b, c = tuple(nums[1:4]), tuple(nums[4:7]), tuple(nums[7:10])
                if winding == "CW":
                    a, b, c = a, c, b
                res["tris"].append((a, b, c, False))
                res["points"] += [(a, False), (b, False), (c, False)]
            elif lt == "4" and len(nums) >= 13:
                a, b, c, d = (
                    tuple(nums[1:4]),
                    tuple(nums[4:7]),
                    tuple(nums[7:10]),
                    tuple(nums[10:13]),
                )
                if winding == "CW":
                    a, b, c, d = a, d, c, b
                res["tris"].append((a, b, c, False))
                res["tris"].append((a, c, d, False))
                res["points"] += [(a, False), (b, False), (c, False), (d, False)]
            if not certified:
                res["uncertified"] = True
        return res


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]}
