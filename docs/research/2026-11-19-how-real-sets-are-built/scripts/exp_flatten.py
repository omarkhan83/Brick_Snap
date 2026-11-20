"""Flatten a multi-part LDraw file (.mpd, .ldr) into one flat list of part lines for the
free builds' checker (experiments 2 and 3 of the study of real sets).

usage: uv run python -I exp_flatten.py MODEL.mpd OUT.ldr [--start NAME] [--drop REGEX]
                                       [--keep-minifigs]

Reads MODEL.mpd as untrusted text (data only, nothing in it is run) and writes OUT.ldr and
OUT.json (where each written line came from, and what was left out).

What it does
- Sub-models: every ``0 FILE`` block is a sub-model, except blocks whose header says they are
  a part (``0 !LDRAW_ORG`` without "Model": parts embedded by the file's author). A part line
  that names a sub-model is replaced by that sub-model's lines, each multiplied by the
  reference's matrix (rotation and position), recursively. A sub-model that refers to itself
  (a loop) is not followed.
- Step order: the sub-model's own steps are written where its parent first uses it, followed
  by the parent's step; ``0 STEP`` and ``0 ROTSTEP`` end a step. This is the order a builder
  follows (the same unrolling as ``omr_analyse.py``).
- Colour: 16 means "the colour of the line that placed me": it is replaced by the colour of
  the enclosing reference, all the way up. If colour 16 reaches the top it stays 16 (the
  checker then warns). 24 (edge colour) is treated the same way. Any other code is kept.
- ``--start NAME``: begin from that sub-model instead of the first one (e.g. one figure of a
  pair). ``--drop REGEX``: leave out sub-models whose name matches (case-insensitive).
- Minifigures: left out by default (as the study did), at the level of a sub-model whose name
  contains "minifig", or of a figure's own body part (library description "Minifig Torso",
  "Arm", "Hand", "Hips", "Leg", "Head", "Hair"). Other parts named "Minifig ..." (claws,
  horns, shields, plumes, handlebars) are kept: sets use them as building elements. Figures
  kept in their own sub-models are left out with ``--start`` or ``--drop``.
  ``--keep-minifigs`` keeps everything.
- Parts the library does not have: an embedded part named "<set> - <part>.dat" is replaced
  by the library's <part>.dat when it has one, and a printed variant the library lacks
  (87079p0s) by its plain part, since a print does not change the shape; OUT.json lists
  every such substitution. Anything else is written unchanged, so the checker reports it.
- The ground: LDraw's up is -y. The whole model is moved in y so that its lowest point (from
  the library's bounding boxes of the parts) is at y = 0, which is where the checker expects
  the ground. Nothing else is moved.
"""

from __future__ import annotations

import json
import re
import sys

import numpy as np

from bricksnap.lab.ldraw_lib import library


def parse_mpd(path: str):
    files: dict[str, list[str]] = {}
    kind: dict[str, str] = {}
    order: list[str] = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if line.upper().startswith("0 FILE "):
                cur = line[7:].strip().lower()
                if cur not in files:
                    order.append(cur)
                files[cur] = []
                kind[cur] = "model"
                continue
            if line.upper().startswith("0 NOFILE"):
                cur = None
                continue
            if cur is None:
                if "__main__" not in files:
                    order.append("__main__")
                    files["__main__"] = []
                    kind["__main__"] = "model"
                cur = "__main__"
            m = re.match(r"0 !LDRAW_ORG\s+(\S+)", line, re.I)
            if m and "model" not in m.group(1).lower():
                kind[cur] = "part"
            files[cur].append(line)
    return files, kind, order


def main(argv: list[str]) -> None:
    src, out = argv[0], argv[1]
    start = None
    drop = None
    keep_minifigs = False
    i = 2
    while i < len(argv):
        if argv[i] == "--start":
            start = argv[i + 1].lower()
            i += 2
        elif argv[i] == "--drop":
            drop = re.compile(argv[i + 1], re.I)
            i += 2
        elif argv[i] == "--keep-minifigs":
            keep_minifigs = True
            i += 1
        else:
            raise SystemExit(f"unknown argument {argv[i]}")
    files, kind, order = parse_mpd(src)
    models = {n for n in files if kind[n] == "model"}
    embedded = sorted(n for n in files if kind[n] == "part")
    root = start or order[0]
    if root not in files:
        raise SystemExit(f"no sub-model {root!r}; there are: {', '.join(order)}")
    lib = library()
    desc_cache: dict[str, str | None] = {}

    def desc(name: str) -> str | None:
        if name not in desc_cache:
            found = lib.resolve(name)
            desc_cache[name] = lib.header(found[1]).description if found and found[0] == "part" else None
        return desc_cache[name]

    def is_minifig(name: str) -> bool:
        d = desc(name) or ""
        return bool(re.match(r"minifig (torso|arms?|hands?|hips|legs?|head|hair)\b", d, re.I))

    out_parts: list[dict] = []  # {colour, pos, m, file, chain, step}
    dropped: dict[str, int] = {}
    unknown: dict[str, int] = {}
    substituted: dict[str, int] = {}
    mirrored_refs = 0
    step_no = [0]

    def substitute(ref: str) -> str | None:
        """A library part with the same shape: an embedded copy named "<set> - <part>.dat" is
        the library's <part>.dat when the library has it; a printed or patterned variant
        (87079p0s, 3069bpr0001) is drawn as its plain part (a print does not change shape)."""
        base = ref.replace("\\", "/").rsplit("/", 1)[-1]
        base = re.sub(r"^\S+\s+-\s+", "", base)
        stem = re.sub(r"\.dat$", "", base, flags=re.I)
        cands = [stem, re.sub(r"(pr\d+|p[a-z0-9]{2,4})$", "", stem, flags=re.I),
                 re.sub(r"(pr\d+|p[a-z0-9]{2,4}|c\d\d|d\d\d)+$", "", stem, flags=re.I)]
        for c in cands:
            if c and lib.resolve(c + ".dat") and lib.resolve(c + ".dat")[0] == "part":
                return c + ".dat"
        return None

    def walk(name: str, R0: np.ndarray, t0: np.ndarray, colour0: int, stack: tuple[str, ...]) -> None:
        steps: list[list[tuple]] = [[]]
        for line in files[name]:
            u = line.upper()
            if u.startswith("0 STEP") or u.startswith("0 ROTSTEP"):
                steps.append([])
            elif line.startswith("1 "):
                tok = line.split()
                if len(tok) < 15:
                    continue
                steps[-1].append(tok)
        for st in steps:
            if not st:
                continue
            here = []
            for tok in st:
                c = int(tok[1], 0) if re.fullmatch(r"-?\d+|0x[0-9a-fA-F]+", tok[1]) else 16
                if c in (16, 24):
                    c = colour0
                x, y, z = (float(v) for v in tok[2:5])
                R = np.array([float(v) for v in tok[5:14]]).reshape(3, 3)
                ref = " ".join(tok[14:])
                key = ref.lower().replace("\\", "/")
                Rw = R0 @ R
                tw = R0 @ np.array([x, y, z]) + t0
                if key in models and key not in stack:
                    if not keep_minifigs and "minifig" in key:
                        dropped["sub-model " + key] = dropped.get("sub-model " + key, 0) + 1
                        continue
                    if drop and drop.search(key):
                        dropped["sub-model " + key] = dropped.get("sub-model " + key, 0) + 1
                        continue
                    if np.linalg.det(R) < 0:
                        nonlocal_mirror()
                    walk(key, Rw, tw, c, stack + (key,))
                    continue
                if not keep_minifigs and is_minifig(ref):
                    k = f"{ref} ({desc(ref)})"
                    dropped[k] = dropped.get(k, 0) + 1
                    continue
                if lib.resolve(ref) is None and lib.resolve(ref + ".dat") is None:
                    tag = ref + (" (embedded in the file)" if key in files else "")
                    sub = substitute(ref)
                    if sub:
                        k = f"{tag} -> {sub}"
                        substituted[k] = substituted.get(k, 0) + 1
                        ref = sub
                    else:
                        unknown[tag] = unknown.get(tag, 0) + 1
                here.append(dict(colour=c, pos=tw, m=Rw, file=ref, chain="/".join(stack), step=step_no[0]))
            if here:
                out_parts.extend(here)
                step_no[0] += 1

    def nonlocal_mirror() -> None:
        nonlocal mirrored_refs
        mirrored_refs += 1

    walk(root, np.eye(3), np.zeros(3), 16, (root,))

    # ground: lowest point at y = 0
    lowest = -1e9
    for p in out_parts:
        found = lib.resolve(p["file"]) or lib.resolve(p["file"] + ".dat")
        if not found or found[0] != "part":
            continue
        part = lib.part(found[1])
        lo, hi = part.bbox_min, part.bbox_max
        corners = np.array([[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])])
        w = corners @ p["m"].T + p["pos"]
        lowest = max(lowest, float(w[:, 1].max()))
    shift = -lowest if lowest > -1e9 else 0.0

    def num(v: float) -> str:
        v = round(float(v), 4)
        if v == 0:
            v = 0.0
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"

    lines = [f"0 Flattened from {src.rsplit('/', 1)[-1]} by exp_flatten.py (start {root})"]
    meta = []
    last_step = 0
    for p in out_parts:
        if p["step"] != last_step:
            lines.append("0 STEP")
            last_step = p["step"]
        pos = p["pos"] + np.array([0.0, shift, 0.0])
        lines.append(
            f"1 {p['colour']} " + " ".join(num(v) for v in pos) + " " + " ".join(num(v) for v in p["m"].reshape(-1)) + f" {p['file']}"
        )
        meta.append(dict(line=len(lines), chain=p["chain"], step=p["step"], file=p["file"]))
    with open(out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    info = dict(
        source=src.rsplit("/", 1)[-1],
        start=root,
        parts=len(out_parts),
        steps=step_no[0],
        sub_models=len(models),
        embedded_parts=embedded,
        unknown=unknown,
        substituted=substituted,
        dropped=dropped,
        mirrored_submodel_refs=mirrored_refs,
        y_shift=shift,
        lines=meta,
    )
    with open(out.rsplit(".", 1)[0] + ".json", "w") as fh:
        json.dump(info, fh, indent=1)
    print(f"{info['source']}: {len(out_parts)} parts, {step_no[0]} steps, y shift {shift:g}; "
          f"dropped {dict(list(dropped.items())[:6])}; unknown {unknown}; substituted {substituted}")


if __name__ == "__main__":
    main(sys.argv[1:])
