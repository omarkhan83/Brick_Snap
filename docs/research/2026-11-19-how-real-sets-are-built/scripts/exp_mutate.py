"""Does the checker still catch what is really wrong? A mutation run (after experiment 3).

usage: uv run python -I exp_mutate.py OUT.json MODEL1.ldr [MODEL2.ldr ...]
                                      [--parts N] [--seed S] [--workers W]
                                      [--only CLASS,...] [--code DIR]

For each model (a flattened official set from exp_flatten.py, or an AI build), it picks N
parts by lot (``--seed``, the same pick every run, so two versions of the checker are given
the very same mutations) and makes one mutation at a time, each a model of its own:

- ``move x4`` ... ``move z20``: the part moved 4, 8 or 20 LDU along +x, up (-y) or +z.
- ``sink 4``, ``sink 8``: the part moved 4 or 8 LDU down (+y), into what is below it.
- ``turn``: the part turned a quarter turn about the vertical line through the middle of its
  body (in place).
- ``copy``: a second copy of the part's line, in the same place, added at the end.
- ``remove``: a part that others stand on turned into a comment (picked by lot among the
  parts with another part whose body's box starts within 1 LDU above the top of its box and
  overlaps it by more than 4 LDU in x and in z; boxes from the library, so that every version
  of the checker is given the same removals).

A mutation is CAUGHT when the checker's problems on the mutated model include one that the
unmutated model's report does not have (compared by kind and the lines it names) and that
names the mutated line (the copy's line for ``copy``; any new problem for ``remove``); a
"loose" problem counts only when it makes loose a part that was not loose before (in a set
the checker already calls partly loose, removing or moving a part of that loose group only
changes the group's make-up, which is not a catch). ``caught_strict`` counts any new problem
naming the line, loose or not (the stricter reading favours a checker that already calls
much of a model loose; the two readings together are the fair comparison). It
writes every mutation's result (and the new problems' texts) to OUT.json and prints, per
class, how many were made and how many caught. Run it once with each version of the checker
(the same arguments) and compare the two files by mutation id.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import random
import sys
from pathlib import Path

import numpy as np

MOVES = [
    (f"move {a}{d}", v)
    for d in (4, 8, 20)
    for a, v in (
        ("x", np.array([d, 0.0, 0.0])),
        ("y", np.array([0.0, -d, 0.0])),
        ("z", np.array([0.0, 0.0, d])),
    )
]
QUARTER = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])


def _num(v: float) -> str:
    r = round(float(v), 4)
    return str(int(r)) if r == int(r) else f"{r:.4f}".rstrip("0").rstrip(".")


def _part_line(tok: list[str], pos: np.ndarray, m: np.ndarray) -> str:
    return " ".join(
        ["1", tok[1], *(_num(v) for v in pos), *(_num(v) for v in m.ravel()), *tok[14:]]
    )


def _keys(report) -> set[tuple[str, tuple[int, ...]]]:
    return {(i.kind, tuple(sorted(i.lines))) for i in report.problems}


def _world_box(p) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = p.part.bbox_min, p.part.bbox_max
    c = np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )
    w = p.to_world(c)
    return w.min(0), w.max(0)


def mutations(name: str, text: str, n_parts: int, seed: int, only: set[str] | None = None):
    from bricksnap.lab.validate import check

    lines = text.splitlines()
    base = check(text, movement=False)
    part_lines = [p.line for p in base.placed]
    rng = random.Random(f"{seed}-{name}")
    picked = sorted(rng.sample(part_lines, min(n_parts, len(part_lines))))
    by_line = {p.line: p for p in base.placed}
    out = []
    for ln in picked:
        p = by_line[ln]
        tok = lines[ln - 1].split()
        for label, d in MOVES + [
            ("sink 4", np.array([0.0, 4.0, 0.0])),
            ("sink 8", np.array([0.0, 8.0, 0.0])),
        ]:
            new = list(lines)
            new[ln - 1] = _part_line(tok, p.pos + d, p.m)
            out.append((label, ln, ln, "\n".join(new)))
        lo, hi = p.part.bbox_min, p.part.bbox_max
        centre = p.to_world((lo + hi) / 2)
        m2 = QUARTER @ p.m
        pos2 = centre + QUARTER @ (p.pos - centre)
        new = list(lines)
        new[ln - 1] = _part_line(tok, pos2, m2)
        out.append(("turn", ln, ln, "\n".join(new)))
        new = list(lines) + [lines[ln - 1]]
        out.append(("copy", ln, len(new), "\n".join(new)))
    boxes = {p.line: _world_box(p) for p in base.placed}
    holders = sorted(
        a
        for a, (alo, ahi) in boxes.items()
        if any(
            b != a
            and abs(bhi[1] - alo[1]) <= 1.0
            and min(ahi[0], bhi[0]) - max(alo[0], blo[0]) > 4
            and min(ahi[2], bhi[2]) - max(alo[2], blo[2]) > 4
            for b, (blo, bhi) in boxes.items()
        )
    )
    for ln in sorted(rng.sample(holders, min(n_parts, len(holders)))):
        new = list(lines)
        new[ln - 1] = "0 removed: " + lines[ln - 1]
        out.append(("remove", ln, None, "\n".join(new)))
    if only:
        out = [m for m in out if m[0] in only or m[0].split()[0] in only]
    return base, out


def _run_one(args):
    name, label, ln, watch, text, base_keys, base_loose = args
    from bricksnap.lab.validate import check

    try:
        r = check(text, movement=False)
    except Exception as e:  # a crash is a finding: record it
        return dict(model=name, cls=label, line=ln, caught=None, crash=f"{type(e).__name__}: {e}")
    new = [i for i in r.problems if (i.kind, tuple(sorted(i.lines))) not in base_keys]
    if watch is not None:
        new = [i for i in new if watch in i.lines]
    strict = bool(new)
    # a loose group counts only when it makes a part loose that was not loose before (a
    # group that was already loose, falsely or not, only changes its make-up)
    new = [i for i in new if i.kind != "loose" or set(i.lines) - base_loose]
    return dict(
        model=name,
        cls=label,
        line=ln,
        caught=bool(new),
        caught_strict=strict,
        new=[f"{i.kind}: {i.text[:300]}" for i in new[:3]],
    )


def main(argv: list[str]) -> None:
    n_parts, seed, workers = 12, 1, 8
    only: set[str] | None = None
    paths = []
    k = 1
    while k < len(argv):
        a = argv[k]
        if a == "--parts":
            n_parts = int(argv[k + 1])
            k += 2
        elif a == "--seed":
            seed = int(argv[k + 1])
            k += 2
        elif a == "--code":
            # another version of bricksnap first on the path (spawned workers get this path)
            sys.path.insert(0, argv[k + 1])
            k += 2
        elif a == "--only":
            only = set(argv[k + 1].split(","))
            k += 2
        elif a == "--workers":
            workers = int(argv[k + 1])
            k += 2
        else:
            paths.append(a)
            k += 1
    jobs = []
    for path in paths:
        name = path.rsplit("/", 2)[-2] + "/" + path.rsplit("/", 1)[-1].removesuffix(".ldr")
        text = Path(path).read_text()
        base, muts = mutations(name, text, n_parts, seed, only)
        keys = _keys(base)
        loose = {ln for i in base.problems if i.kind == "loose" for ln in i.lines}
        print(f"{name}: {base.summary()}  {len(muts)} mutations", flush=True)
        jobs += [(name, label, ln, watch, t, keys, loose) for label, ln, watch, t in muts]
    # spawn, not fork: a forked worker would share the parts library's open zip file
    with mp.get_context("spawn").Pool(workers) as pool:
        results = pool.map(_run_one, jobs, chunksize=4)
    Path(argv[0]).write_text(json.dumps(results, indent=1))
    classes = sorted({r["cls"] for r in results}, key=lambda c: (c.split()[0], len(c), c))
    print(f"\n{'class':10s} {'made':>5s} {'caught':>7s}")
    for c in classes:
        rs = [r for r in results if r["cls"] == c]
        print(f"{c:10s} {len(rs):5d} {sum(1 for r in rs if r['caught']):7d}")
    crashes = [r for r in results if r.get("crash")]
    if crashes:
        print(f"{len(crashes)} crashes, e.g. {crashes[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
