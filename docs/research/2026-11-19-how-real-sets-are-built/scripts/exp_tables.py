"""Experiment 2: turn the JSON of exp_measures.py into Markdown tables and group medians.

usage: python -I exp_tables.py MEASURES.json [MEASURES2.json ...]

Prints one table per file (one row per model) and, per file, the median of each column.
"""

from __future__ import annotations

import json
import statistics as st
import sys

COLS = [
    ("Parts", lambda m: m["parts"]),
    ("Kinds", lambda m: m["kinds"]),
    ("Colours", lambda m: m["colours"]),
    ("Sideways", lambda m: m["facing"]["sideways"] * 100),
    ("Down", lambda m: m["facing"]["down"] * 100),
    ("Side, 1st third", lambda m: m["facing_first_third"]["sideways"] * 100),
    ("Side, last third", lambda m: m["facing_last_third"]["sideways"] * 100),
    ("1x1/1x2", lambda m: m["small_share"] * 100),
    ("Mean footprint", lambda m: m["mean_footprint"]),
    ("Seams uncovered", lambda m: (m["uncovered_share"] or 0) * 100),
    ("Uncovered /100 parts", lambda m: m["uncovered_per_100_parts"]),
    ("Parts holding a section", lambda m: 100 * m["hanging_holders"] / m["parts"]),
    ("Largest section", lambda m: m["largest_hanging"]),
    ("Sections of 5+", lambda m: m["hanging_5plus"]),
    ("1st quarter height pct", lambda m: m["first_quarter_height_pct"]),
    ("1st quarter distance pct", lambda m: m["first_quarter_distance_pct"]),
    ("Mirrored", lambda m: m["mirror_share"] * 100),
]
PCT = {"Sideways", "Down", "Side, 1st third", "Side, last third", "1x1/1x2", "Seams uncovered", "Mirrored",
       "Parts holding a section"}


def fmt(name: str, v) -> str:
    if v is None:
        return "-"
    if name in PCT:
        return f"{v:.0f}%"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.1f}"
    return f"{v:.0f}"


def main(argv: list[str]) -> None:
    for path in argv:
        rows = [m for m in json.load(open(path)) if "crash" not in m]
        print(f"\n### {path.rsplit('/', 1)[-1]} ({len(rows)} models)\n")
        print("| Model | " + " | ".join(c for c, _ in COLS) + " |")
        print("|---|" + "---:|" * len(COLS))
        for m in rows:
            print(f"| {m['name']} | " + " | ".join(fmt(c, f(m)) for c, f in COLS) + " |")
        print("| **median** | " + " | ".join(fmt(c, st.median(f(m) for m in rows)) for c, f in COLS) + " |")
        print("\nFirst quarter of the lines, by kind of part (share of those parts):")
        for m in rows:
            fq = ", ".join(f"{k} {v:.0%}" for k, v in list(m["first_quarter"].items())[:4])
            print(f"- {m['name']}: {fq}")


if __name__ == "__main__":
    main(sys.argv[1:])
