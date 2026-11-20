"""Experiment 3: run the free builds' checker on flattened official sets and sort what it says.

usage: uv run python -I exp_check_sets.py OUT_DIR FLAT1.ldr [FLAT2.ldr ...]

For each flattened model (from exp_flatten.py) it runs ``bricksnap.lab.validate.check`` and
writes OUT_DIR/<name>.report.txt (the checker's own report, in full) and OUT_DIR/<name>.json:
the summary, every issue (severity, kind, lines, text, and the part files of those lines),
the "not checked" joints by the joint words the checker uses, the parts named in no
problem, and the stud links. A crash is recorded with its error and the run goes on.
It prints one line per model and, per problem kind, the most common pairs of parts.
"""

from __future__ import annotations

import collections
import json
import os
import re
import sys
import traceback

import numpy as np

from bricksnap.lab import solid as solids
from bricksnap.lab.validate import check

JOINT_WORDS = ["Technic pin", "axle", "wheel pin", "tyre on a wheel", "bar in a clip", "hinge", "ball joint", "turntable"]


DEPTHS = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)
_AXES = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)


def real_interference(a, b) -> dict:
    """How far the real shapes (with studs) of two placed parts go into each other.

    For each part, the points on its real surface (``solid.surface``) that are inside the
    other part's real solid (``solid.solid``, voxels of 0.5 LDU). A point is counted as at
    least d LDU deep when it AND the six points d LDU from it along the axes are all inside:
    two parts that only touch along a face give no point at 1 LDU, so contact is not counted.
    ``depth`` is the largest d in DEPTHS reached by any point (0 when none reaches 1 LDU),
    ``n`` how many surface points reach 1 LDU, ``box`` where they are."""
    best = 0.0
    hits = []
    for p, q in ((a, b), (b, a)):
        sq = solids.solid(q.key)
        world = p.to_world(solids.surface(p.key))
        local = q.to_local(world)
        ok = sq.inside(local, deep=False)
        for d in DEPTHS:
            if not ok.any():
                break
            for ax in _AXES:
                ok = ok & sq.inside(q.to_local(world + d * ax), deep=False)
            if not ok.any():
                break
            best = max(best, d)
            if d == DEPTHS[0]:
                hits.append(world[ok])
    out: dict = {"depth": best, "n": int(sum(len(h) for h in hits))}
    if hits:
        allp = np.concatenate(hits)
        out["box"] = [[round(float(v)) for v in allp.min(0)], [round(float(v)) for v in allp.max(0)]]
    return out


def main(argv: list[str]) -> None:
    out_dir = argv[0]
    os.makedirs(out_dir, exist_ok=True)
    for path in argv[1:]:
        name = os.path.basename(path).rsplit(".", 1)[0]
        text = open(path).read()
        try:
            r = check(text)
        except Exception as e:  # record the crash and go on
            info = dict(name=name, crash=f"{type(e).__name__}: {e}", trace=traceback.format_exc())
            json.dump(info, open(os.path.join(out_dir, name + ".json"), "w"), indent=1)
            print(f"{name}: CRASH {type(e).__name__}: {e}")
            continue
        open(os.path.join(out_dir, name + ".report.txt"), "w").write(r.text())
        by_line = {p.line: p for p in r.placed}
        issues = []
        for i in r.issues:
            x = dict(severity=i.severity, kind=i.kind, lines=i.lines, text=i.text,
                     files=[by_line[n].key if n in by_line else None for n in i.lines])
            if i.severity == "problem" and i.kind == "overlap" and len(i.lines) == 2:
                x["real"] = real_interference(by_line[i.lines[0]], by_line[i.lines[1]])
            if i.severity == "problem" and i.kind == "stud":
                m = re.search(r"they (miss the stud grid[^;]*?(\d+(?:\.\d+)?) LDU off in that part's x and "
                              r"(\d+(?:\.\d+)?) LDU off in its z|are not pressed home[^:]*: there is a gap of "
                              r"(\S+) LDU|go (\S+) LDU too far|push into the side or top|push into line \d+, which "
                              r"has no sockets|press against the underside)", i.text)
                x["reason"] = m.group(1)[:40] if m else "?"
                if m and m.group(2):
                    x["off"] = [float(m.group(2)), float(m.group(3))]
            issues.append(x)
        joints = collections.Counter()
        for i in r.unchecked:
            if i.kind != "joint":
                continue
            m = re.search(r"by a (.+?), which the checker|: a (.+?) joint, which", i.text)
            words = (m.group(1) or m.group(2)) if m else "?"
            # several words "x or y": count the first, which is the checker's most specific
            joints[words.split(" or ")[0]] += 1
        in_problem = set()
        for i in r.problems:
            in_problem.update(i.lines)
        n = len(r.placed)
        clean = [p.line for p in r.placed if p.line not in in_problem]
        info = dict(
            name=name,
            summary=r.summary(),
            parts=n,
            kinds=len({p.key for p in r.placed}),
            problems=len(r.problems),
            problem_kinds=dict(collections.Counter(i.kind for i in r.problems)),
            warnings=dict(collections.Counter(i.kind for i in r.warnings)),
            unchecked_joints=dict(joints),
            unchecked_other=dict(collections.Counter(i.kind for i in r.unchecked if i.kind != "joint")),
            parts_in_problems=len(in_problem & set(by_line)),
            share_clean=round(len(clean) / n, 3) if n else None,
            stands=r.stands,
            issues=issues,
            links=[dict(holder=k.holder, held=k.held, studs=len(k.studs), how=k.how) for k in r.links],
            grounded=r.grounded,
        )
        json.dump(info, open(os.path.join(out_dir, name + ".json"), "w"), indent=1)
        print(f"{name}: {r.summary()}  clean {info['share_clean']:.0%}  problems {info['problem_kinds']}  "
              f"not checked {info['unchecked_joints']} {info['unchecked_other']}")
        for kind in sorted(info["problem_kinds"]):
            pairs = collections.Counter(
                " + ".join(sorted(f or "?" for f in i["files"][:2]))
                for i in issues if i["severity"] == "problem" and i["kind"] == kind
            )
            print(f"   {kind}: " + "; ".join(f"{k} x{c}" for k, c in pairs.most_common(8)))


if __name__ == "__main__":
    main(sys.argv[1:])
