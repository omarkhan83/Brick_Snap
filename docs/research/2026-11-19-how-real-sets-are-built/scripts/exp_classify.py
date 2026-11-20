"""Experiment 3: sort every PROBLEM the checker raised on an official set by its cause.

usage: uv run python -I exp_classify.py OUT.json CHECK1.json FLAT1.ldr [CHECK2.json FLAT2.ldr ...]

Causes: (i) the checker is wrong about a real, legal construction; (ii) the model file is
drawn imprecisely by its author; (iii) a part our library lacks or reads badly; (iv) cannot
tell. The rules below were written after looking at examples of each (pictures and
positions; see experiments.md), and each rule names the construction. Anything no rule
covers is printed as UNSORTED so that it is looked at by hand, and the decisions taken by hand
are the entries of ``BY_HAND`` (set, first line, second line) -> (cause, construction).

Overlap rules use two measurements made by exp_check_sets.py: ``thin``, the thinnest side of
the box the checker gives for the shared volume (minus its 2 LDU margin on each side), and
``real``, how deep the parts' real shapes (with studs) go into each other (0 when they only
touch; an ordinary stud joint measures up to 3 LDU, because a stud's surface sits inside the
voxels of the socket around it).

Loose groups take the cause of what should have held them: the stud or overlap problem that
names one of their parts, or a joint between one of their parts and the rest that the
checker does not recognise (``LOOSE_BY_PART`` / ``BY_HAND``).
"""

from __future__ import annotations

import collections
import json
import re
import sys

from bricksnap.lab.ldraw_lib import library

LIB = library()

def desc(key: str) -> str:
    return LIB.part(key).description if key else ""


def has_open_stud(key: str) -> bool:
    return any(s.prim.startswith("stud2") or s.prim in ("stud6", "stud6a", "studa") for s in LIB.part(key).studs)


def bar_like(key: str) -> bool:
    d = desc(key).lower()
    return bool(re.search(r"\bbar\b|antenna|claw|prong|tooth|lightsaber|plume|horn|whip|hose", d))


def is_axle_read_as_hole(key: str) -> bool:
    p = LIB.part(key)
    d = p.description.lower()
    return d.startswith("technic axle") and any(c.kind == "axle hole" for c in p.others)


def whole_box(key: str) -> bool:
    p = LIB.part(key)
    span = p.bbox_max - p.bbox_min
    return all(abs(v / 20 - round(v / 20)) < 0.05 and v > 1 for v in (span[0], span[2]))


# Decisions taken by hand after looking (set, line a, line b): (cause, construction).
JUMPER = "a 1 x 2 part centred on a jumper plate's one stud, so that the stud is between the part's two sockets; the checker says no, and so would a real 1 x 2 plate (its middle has a solid tube), unless the part was meant to rest there unattached: cannot tell which"
IRREGULAR = "a stud under a real socket in an irregular underside (a curved brick's ribs and fillets, a wedge's tapered nose): the checker's socket test wants a flat hollow"
ROUND_EAR = "a 1 x 1 round plate at the centre of a bracket's 2 x 2 side face, between a dish and a hinge stick: on no stud and not centred between four; the file or a technique the checker does not know"
BY_HAND: dict[tuple[str, int, int], tuple[str, str]] = {
    ("40441", 337, 197): ("iv", JUMPER),
    ("40441", 338, 201): ("iv", JUMPER),
    ("40441", 197, 0): ("iv", "follows from: " + JUMPER),
    ("40441", 315, 322): ("i", IRREGULAR),
    ("40441", 316, 323): ("i", IRREGULAR),
    ("40441", 317, 320): ("i", IRREGULAR),
    ("40441", 318, 321): ("i", IRREGULAR),
    ("31072", 42, 105): ("i", IRREGULAR),
    ("31072", 57, 0): ("i", "a clip on a bar handle, turned 15 degrees: the checker's contact test does not see the clip touch the handle (its mirror twin is seen)"),
    ("31072", 2, 0): ("iii", "follows from: an axle (or the axle end of an axle pin) in a hole: the library reads the axle as an axle hole, so the wheels on the ground are not joined to the car"),
    ("75075", 2, 0): ("i", "follows from: a bar (or a part's bar-shaped end) pushed into an open stud (each leg's bar in the open stud of its foot dish)"),
    ("75075", 68, 82): ("iv", ROUND_EAR),
    ("75075", 82, 0): ("iv", "follows from: " + ROUND_EAR),
    ("75075", 87, 0): ("iv", "follows from: " + ROUND_EAR),
    ("75075", 83, 0): ("iv", "follows from: " + ROUND_EAR),
    ("10349", 253, 257): ("i", "a bar through the hollow middle of a round brick: the round brick has no connector the checker reads, so the bar inside it is an overlap"),
    ("10349", 257, 259): ("i", "a bar pushed into the hollow end of a Technic pin: the checker knows pins go into holes, not that a bar goes into a pin"),
    ("10349", 119, 136): ("i", "a three-pronged bar pushed into an axle hole and an open stud: the checker knows no joint between a bar and an axle hole"),
    ("10349", 252, 301): ("i", "a three-pronged bar pushed into an axle hole and an open stud: the checker knows no joint between a bar and an axle hole"),
    ("10349", 263, 264): ("iii", "a shield clipped by the clip on its back: the library records no clip on this part (no primitive, no word in its name), so it cannot join anything"),
    ("31072", 52, 53): ("iii", "a pneumatic T-piece held in two clips by its bar-shaped body: the library records no bar on it, so clip and T-piece are an overlap and the T-piece is loose"),
    ("31072", 53, 54): ("iii", "a steering wheel pushed onto the T-piece's nozzle: neither part records the joint"),
    ("75075", 85, 0): ("iv", "follows from: " + ROUND_EAR),
}
# Parts that join the rest by a joint the checker or the library does not know (for loose
# groups that no stud or overlap problem explains): part -> (cause, construction).
LOOSE_BY_PART: dict[str, tuple[str, str]] = {
    "87994.dat": ("i", "a bar inside a bar tube (23443): the checker reads both as bars from their names, so they cannot join"),
    "75902.dat": ("iii", "a shield clipped by the clip on its back: the library records no clip on this part (no primitive, no word in its name), so it cannot join anything"),
}


def classify(set_name: str, issue: dict, flat_lines: list[str]) -> tuple[str, str]:
    kind = issue["kind"]
    files = issue["files"]
    lines = issue["lines"]
    key = (set_name, lines[0], lines[1] if len(lines) > 1 else 0)
    if key in BY_HAND:
        return BY_HAND[key]
    if kind == "overlap":
        a, b = files
        real = issue.get("real", {})
        depth = real.get("depth", 99)
        m = re.search(r"around x (-?\d+)\.\.(-?\d+), y (-?\d+)\.\.(-?\d+), z (-?\d+)\.\.(-?\d+)", issue["text"])
        v = list(map(int, m.groups())) if m else [0, 99, 0, 99, 0, 99]
        thin = min(v[1] - v[0], v[3] - v[2], v[5] - v[4]) - 4
        if is_axle_read_as_hole(a) or is_axle_read_as_hole(b) or any(
            desc(x).lower().startswith("technic axle pin") for x in (a, b)
        ):
            return "iii", "an axle (or the axle end of an axle pin) in a hole: the library reads the axle as an axle hole, so the checker sees two holes that cannot join"
        if depth == 0:
            return "i", "parts that only touch (a bracket's flange, a stepped or hollow underside, a clip): the rough filled body counts touching as overlap; the real shapes do not meet"
        if depth <= 4 and thin <= 5:
            return "i", "parts that only touch, at a bracket's flange or a stepped underside: the filled body is a column too wide; the real shapes meet only as a seated stud does"
        return "?", f"overlap thin {thin} real depth {depth}"
    if kind == "stud":
        holder, held = files
        reason = issue.get("reason", "")
        off = issue.get("off")
        if ("no sockets" in reason or "side or top" in reason) and has_open_stud(holder) and (
            bar_like(held) or not LIB.part(held).has_sockets()
        ):
            return "i", "a bar (or a part's bar-shaped end) pushed into an open stud"
        if "side or top" in reason and any(c.kind == "pin hole" for c in LIB.part(held).others):
            return "i", "a stud pushed into a Technic pin hole"
        if "side or top" in reason and has_open_stud(holder) and any(c.kind == "axle hole" for c in LIB.part(held).others):
            return "i", "a bar (or a part's bar-shaped end) pushed into an open stud"
        if off and not whole_box(held) and max(off) < 10 and min(off) == 0:
            return "iii", "a part whose sides are not whole studs (a cutout or overhang): the library takes its stud grid from its bounding box, which is off by the cutout"
        return "?", f"stud {reason} {off}"
    return "?", kind


# Which change to the checker would remove a problem of this construction (by words in its
# label; the first match wins).
FIXES = [
    ("A: confirm a filled-body overlap with the real shapes (solid.py) before calling it a problem",
     ("only touch",)),
    ("B: let a bar go into an open stud, a bar tube, a pin's end, an axle hole or a round brick's middle",
     ("open stud", "bar tube", "hollow end of a Technic pin", "three-pronged bar", "hollow middle of a round brick")),
    ("C: read axles drawn with axle-hole primitives as axles", ("library reads the axle",)),
    ("D: take a part's stud grid from its sockets, not its bounding box", ("bounding box",)),
    ("E: accept a stud in a Technic pin hole", ("Technic pin hole",)),
    ("F: accept a real socket in an irregular underside", ("irregular underside",)),
    ("G: know the clips and bars of parts whose names do not say so", ("shield", "T-piece", "steering wheel")),
    ("H: see a clip on a handle that is turned", ("turned 15 degrees",)),
]


def fix_of(what: str) -> str:
    for name, words in FIXES:
        if any(w in what for w in words):
            return name
    return "none: not the checker's fault, or cannot tell"


def main(argv: list[str]) -> None:
    out = argv[0]
    rows = []
    for k in range(1, len(argv), 2):
        check = json.load(open(argv[k]))
        flat = open(argv[k + 1]).read().splitlines()
        name = check["name"]
        problems = [i for i in check["issues"] if i["severity"] == "problem"]
        causes: list[dict] = []
        pair_causes: list[tuple[set, tuple[str, str]]] = []
        for i in problems:
            if i["kind"] in ("loose", "tips over", "ground", "below ground"):
                continue
            c = classify(name, i, flat)
            causes.append(dict(kind=i["kind"], lines=i["lines"], files=i["files"], cause=c[0], what=c[1]))
            pair_causes.append((set(i["lines"]), c))
        for i in problems:
            if i["kind"] not in ("loose", "tips over", "ground", "below ground"):
                continue
            key = (name, i["lines"][0], 0)
            if key in BY_HAND:
                c = BY_HAND[key]
            else:
                group = set(i["lines"])
                # a problem between a part of the group and a part outside it: that is the
                # joint that should have held the group
                found = [c for pair, c in pair_causes if pair & group and pair - group]
                if not found:
                    for f in i["files"]:
                        if f in LOOSE_BY_PART:
                            found = [LOOSE_BY_PART[f]]
                            break
                c = (found[0][0], "follows from: " + found[0][1]) if found else ("?", "loose: " + i["text"][:200])
            causes.append(dict(kind=i["kind"], lines=i["lines"], files=i["files"], cause=c[0], what=c[1]))
        rows.append(dict(name=name, causes=causes))
        tally = collections.Counter(c["cause"] for c in causes)
        print(f"{name}: {len(causes)} problems; by cause {dict(tally)}")
        for c in causes:
            if c["cause"] == "?":
                print(f"   UNSORTED {c['kind']} lines {c['lines'][:6]} {c['files'][:3]}: {c['what'][:220]}")
    fixes = collections.Counter()
    per_set = collections.defaultdict(collections.Counter)
    for r in rows:
        for c in r["causes"]:
            f = fix_of(c["what"])
            c["fix"] = f
            fixes[f] += 1
            per_set[f][r["name"]] += 1
    print("\nProblems each change would remove (all sets):")
    for f, n in fixes.most_common():
        print(f"  {n:3d}  {f}   {dict(per_set[f])}")
    json.dump(rows, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
