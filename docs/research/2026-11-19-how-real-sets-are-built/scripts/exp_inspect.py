"""Look closely at what the checker says about one flattened model (experiment 3).

usage: uv run python -I exp_inspect.py CHECK.json FLAT.ldr [KIND] [--lines 12,40] [--png OUT.png]

Prints each problem (of KIND, or all) with, for every line it names: the part, its
description, colour, position, rotation, which way its "up" points, and the sub-model it came
from (from FLAT.json written by exp_flatten.py). ``--lines`` prints those lines only, and
with ``--png`` draws them alone (and the parts touching them, greyed out is not possible in
LDraw, so they are drawn in their own colours) with ``bricksnap.lab.picture.model_sheet``.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from bricksnap.lab.ldraw_lib import library


def main(argv: list[str]) -> None:
    info = json.load(open(argv[0]))
    flat_path = argv[1]
    flat = open(flat_path).read().splitlines()
    meta = {}
    try:
        fm = json.load(open(flat_path.rsplit(".", 1)[0] + ".json"))
        meta = {m["line"]: m for m in fm.get("lines", [])}
    except OSError:
        pass
    kind = None
    only = None
    png = None
    i = 2
    while i < len(argv):
        if argv[i] == "--lines":
            only = [int(v) for v in argv[i + 1].split(",")]
            i += 2
        elif argv[i] == "--png":
            png = argv[i + 1]
            i += 2
        else:
            kind = argv[i]
            i += 1
    lib = library()

    def show(n: int) -> str:
        tok = flat[n - 1].split()
        if tok[0] != "1":
            return f"  {n}: {flat[n - 1]}"
        found = lib.resolve(tok[14])
        desc = lib.header(found[1]).description if found else "?"
        m = np.array([float(v) for v in tok[5:14]]).reshape(3, 3)
        up = m @ np.array([0, -1.0, 0])
        upw = "up" if up[1] < -0.98 else "DOWN" if up[1] > 0.98 else "sideways " + " ".join(f"{v:+.0f}" for v in up)
        chain = meta.get(n, {}).get("chain", "")
        return (f"  {n}: {tok[14]} [{desc}] c{tok[1]} at {' '.join(tok[2:5])} rot {' '.join(tok[5:14])} "
                f"(up {upw}) from {chain.rsplit('/', 1)[-1]}")

    if only:
        for n in only:
            print(show(n))
        if png:
            from bricksnap.lab.picture import model_sheet

            text = "\n".join(flat[n - 1] for n in only)
            print(model_sheet(text, png))
        return
    for k, x in enumerate(info["issues"], 1):
        if x["severity"] != "problem" or (kind and x["kind"] != kind):
            continue
        print(f"[{x['kind']}] {x['text'][:400]}")
        for n in x["lines"][:6]:
            print(show(n))
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
