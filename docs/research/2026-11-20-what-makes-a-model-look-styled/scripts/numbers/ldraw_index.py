"""Index the LDraw parts library's headers: name, "moved to", and Rebrickable/BrickLink keywords.

usage: uv run --project <repo> python -I ldraw_index.py LDRAW_ZIP OUT.json

Reads only the header lines of each ldraw/parts/*.dat (not s/), as data.
"""
import json
import re
import sys
import zipfile

Z = zipfile.ZipFile(sys.argv[1])
out = {}
for n in Z.namelist():
    low = n.lower()
    if not low.endswith(".dat") or "/parts/" not in low or "/parts/s/" in low:
        continue
    stem = low.rsplit("/", 1)[-1][:-4]
    head = Z.read(n)[:3000].decode("utf-8", "replace").splitlines()
    name = head[0][2:].strip() if head and head[0].startswith("0") else ""
    moved = None
    m = re.match(r"~?moved to\s+(\S+)", name, re.I)
    if m:
        moved = m.group(1).lower().removesuffix(".dat")
    rb, bl = [], []
    for line in head[1:40]:
        if line.upper().startswith("0 !KEYWORDS"):
            for kw in line[11:].split(","):
                kw = kw.strip()
                m = re.match(r"rebrickable\s+(\S+)", kw, re.I)
                if m:
                    rb.append(m.group(1))
                m = re.match(r"bricklink\s+(\S+)", kw, re.I)
                if m:
                    bl.append(m.group(1))
    alias = None
    if name.startswith("=") or name.startswith("_"):
        for line in head[1:]:
            if line.startswith("1 "):
                alias = line.split()[-1].lower().replace("\\", "/").removesuffix(".dat")
                break
    out[stem] = dict(name=name, moved=moved, rb=rb, bl=bl, alias=alias)
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "part files;", sum(1 for v in out.values() if v["rb"]), "with a Rebrickable keyword")
