"""Load Rebrickable's catalogue CSVs into one pickle for the style-numbers study.

usage: uv run --project <repo> python -I load_rb.py RB_DIR OUT.pkl

RB_DIR holds the unpacked downloads (sets, themes, inventories, inventory_parts, parts,
part_categories, colors, part_relationships). Every set of every year is loaded: the first
year of a part design is the earliest year it appears in any set. A set's parts list is its
lowest-numbered inventory version, spares left out. Prints and patterns (relationship types
P and T) are folded onto their plain parent part, recursively, so "a part design" is a mould.
"""
import collections
import csv
import pickle
import sys

D, OUT = sys.argv[1], sys.argv[2]


def rows(name):
    with open(f"{D}/{name}.csv", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


parts = {r["part_num"]: (r["name"], r["part_cat_id"]) for r in rows("parts")}
cats = {r["id"]: r["name"] for r in rows("part_categories")}
themes = {r["id"]: (r["name"], r["parent_id"]) for r in rows("themes")}
colors = {int(r["id"]): (r["name"], r["is_trans"] == "True", int(r["y1"] or 0), int(r["y2"] or 0))
          for r in rows("colors")}
sets = {r["set_num"]: (r["name"], int(r["year"]), r["theme_id"], int(r["num_parts"])) for r in rows("sets")}

parent = {}
for r in rows("part_relationships"):
    if r["rel_type"] in ("P", "T"):
        parent[r["child_part_num"]] = r["parent_part_num"]


def root(p):
    k = 0
    while p in parent and k < 8:
        p = parent[p]
        k += 1
    return p


roots = {p: root(p) for p in parts}

inv = {}
for r in rows("inventories"):
    s = r["set_num"]
    if s in sets:
        v = int(r["version"])
        if s not in inv or v < inv[s][1]:
            inv[s] = (r["id"], v)
invid = {i: s for s, (i, v) in inv.items()}

tally = collections.defaultdict(collections.Counter)  # set -> Counter[(root part, colour)]
for r in rows("inventory_parts"):
    s = invid.get(r["inventory_id"])
    if s is None or r["is_spare"] == "True":
        continue
    p = roots.get(r["part_num"], r["part_num"])
    tally[s][(p, int(r["color_id"]))] += int(r["quantity"])

first_year = {}
for s, c in tally.items():
    y = sets[s][1]
    for (p, _col) in c:
        if p not in first_year or y < first_year[p]:
            first_year[p] = y

pickle.dump(dict(parts=parts, cats=cats, themes=themes, colors=colors, sets=sets, roots=roots,
                 tally={s: dict(c) for s, c in tally.items()}, first_year=first_year), open(OUT, "wb"))
print(len(sets), "sets;", len(tally), "with parts;", len(first_year), "part designs with a first year")
