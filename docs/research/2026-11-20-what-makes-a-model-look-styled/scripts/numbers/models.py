"""Read LDraw model files (our AI builds and the official models) into Rebrickable-numbered tallies.

usage: uv run --project <repo> python -I models.py rb.pkl ldraw_index.json OUT.json  LABEL=PATH [LABEL=PATH ...]

Each PATH is an .ldr or .mpd file, read as untrusted text (data only). Sub-models are expanded
with their multiplicity; colour 16/24 takes the colour of the line that placed it. Sub-models whose
name contains "minifig" are left out. A part file is mapped to a Rebrickable part by, in order:
its own number; the Rebrickable keyword in its LDraw header; its "moved to" target; the number
with a print/pattern/sticker suffix taken off; the number with a trailing letter taken off. Then
prints are folded onto their parent as in the catalogue. Colours: LDraw code = Rebrickable id,
except the few listed in LD2RB (checked name by name against LDConfig.ldr).
"""
import collections
import json
import pickle
import re
import sys

d = pickle.load(open(sys.argv[1], "rb"))
IDX = json.load(open(sys.argv[2]))
OUT = sys.argv[3]
parts, roots = d["parts"], d["roots"]
LD2RB = {43: 41, 41: 43, 38: 57, 57: 182, 256: 0, 326: 158, 330: 326}


def parse(path):
    files, kind, order = {}, {}, []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if line.upper().startswith("0 FILE "):
                cur = line[7:].strip().lower()
                if cur not in files:
                    order.append(cur)
                files[cur], kind[cur] = [], "model"
                continue
            if line.upper().startswith("0 NOFILE"):
                cur = None
                continue
            if cur is None:
                cur = "__main__"
                if cur not in files:
                    order.append(cur)
                    files[cur], kind[cur] = [], "model"
            m = re.match(r"0 !LDRAW_ORG\s+(\S+)", line, re.I)
            if m and "model" not in m.group(1).lower():
                kind[cur] = "part"
            files[cur].append(line)
    return files, kind, order


def flatten(path):
    files, kind, order = parse(path)
    out = collections.Counter()
    desc = {}

    def walk(n, colour, mult, stack):
        for line in files[n]:
            if not line.startswith("1 "):
                continue
            tok = line.split()
            if len(tok) < 15:
                continue
            c = int(tok[1])
            if c in (16, 24):
                c = colour
            ref = " ".join(tok[14:]).lower().replace("\\", "/")
            if ref in files and kind[ref] == "model":
                if "minifig" in ref or ref in stack:
                    continue
                walk(ref, c, mult, stack + (ref,))
            else:
                if ref in files:  # embedded part: remember its own description
                    first = next((x for x in files[ref] if x.startswith("0 ")), "")
                    desc[ref] = first[2:].strip()
                out[(ref, c)] += mult

    walk(order[0], 16, 1, (order[0],))
    return out, desc


SUFFIX = [r"(p[a-z0-9]{2,4})+$", r"pr\d+[a-z]?$", r"(c\d\d)+$", r"(d\d\d)+$", r"(p[a-z0-9]+|pr\d+|c\d\d|d\d\d)+$"]


def to_rb(ref, desc):
    stem = ref.rsplit("/", 1)[-1].removesuffix(".dat")
    stem = re.sub(r"^\d+(-\d+)?\s*-\s*", "", stem)  # "<set> - <part>" embedded copies
    tried = []

    def ok(x):
        return x in parts

    cands = [stem]
    info = IDX.get(stem)
    if info:
        cands += [k.lower() for k in info["rb"]] + info["rb"]
        if info.get("alias"):
            cands.append(info["alias"])
            ai = IDX.get(info["alias"])
            if ai:
                cands += ai["rb"]
        if info["moved"]:
            cands.append(info["moved"])
            mi = IDX.get(info["moved"])
            if mi:
                cands += mi["rb"]
    for rx in SUFFIX:
        s2 = re.sub(rx, "", stem)
        if s2 and s2 != stem:
            cands.append(s2)
    cands.append(re.sub(r"[a-z]$", "", stem))
    for c in cands:
        tried.append(c)
        if ok(c):
            return roots.get(c, c), "mapped"
    name = (info or {}).get("name") or desc.get(ref, "")
    nl = name.lower().lstrip("~_=")
    if nl.startswith("sticker") or nl.startswith("minifig") or nl.startswith("figure ") or "sticker" in nl:
        return None, "sticker_or_minifig"
    return "LD:" + stem, "unmapped:" + name


result = {}
for arg in sys.argv[4:]:
    label, path = arg.split("=", 1)
    tally, desc = flatten(path)
    rb = collections.Counter()
    unm = collections.Counter()
    dropped = 0
    for (ref, c), q in tally.items():
        p, how = to_rb(ref, desc)
        if p is None:
            dropped += q
            continue
        if how.startswith("unmapped"):
            unm[ref + " | " + how[9:]] += q
        rb[(p, LD2RB.get(c, c))] += q
    result[label] = dict(path=path, tally=[[p, c, q] for (p, c), q in rb.items()],
                         unmapped=dict(unm), dropped_sticker_minifig=dropped, total_lines=sum(tally.values()))
json.dump(result, open(OUT, "w"), indent=1)
for k, v in result.items():
    print(f"{k:45s} lines {v['total_lines']:5d} unmapped {sum(v['unmapped'].values()):3d} dropped {v['dropped_sticker_minifig']}")
