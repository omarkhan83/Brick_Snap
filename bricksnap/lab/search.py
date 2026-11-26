"""Find parts by plain words (research prototype; see ``__init__``).

CONTRACT (tests in tests/test_lab.py)

``load_index()`` returns the index of the official, current, plain parts, building it the
first time (a few minutes, in parallel) and caching it as ``index.json`` under the lab
cache. ``python -m bricksnap.lab.search --build`` builds it ahead of time;
``python -m bricksnap.lab.search "wing 2 x 4 left"`` searches from the command line.

What is left out, and how each kind is recognised (``exclusion_reason``):
- "moved": the description starts with "~Moved to" (an old number kept as a pointer).
- "not for listing": any other description starting with "~" (LDraw's mark for sub-
  assemblies and parts not meant to be listed, such as "~Train Base ... Type 1").
- "alias": the description starts with "=" (the same part under another number).
- "physical colour": the description starts with "_" (a part fixed to one colour).
- "third party": the description starts with "|" (non-LEGO elements in the library).
- "shortcut": ``!LDRAW_ORG Shortcut`` (assemblies of several parts, such as a wheel with its
  tyre or a minifig torso with arms, and every sticker shortcut). They are real files LeoCAD
  draws, but they are not one part.
- "obsolete": "Obsolete" in the description or the category.
- "sticker": the description or category says "Sticker".
- "patterned": the description says "Pattern", or the file name is a number followed by
  "p" and a pattern code (``3001p11``, ``3068bpx1``).
- "other system": the first word is Duplo, Primo, Quatro, Scala, Modulex, Znap, Clikits,
  Fabuland, Belville or Mursten (not System bricks).

``search(query, limit=15)`` ranks by word overlap: description words count most, then the
category, then the keywords; "2 x 4" sizes are matched as a size (either order); a query
whose words appear in order in the description gets a bonus; every query word missing from a
part costs a lot; extra words in a long description cost a little, so the plain part comes
before its variants. A part number in the query ("3001") finds that part first. A few
words LDraw does not use are mapped to the words it does (``SYNONYMS``: wing -> wedge, tire ->
tyre, ...).

Each result (``Hit``) carries the file name, description, category, size in studs by studs
by plates (x by z by height of the body), the studs (how many, where) and other connectors,
and where its origin is relative to its body.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bricksnap.lab.ldraw_lib import (
    Library,
    cache_dir,
    direction_word,
    fmt,
    origin_note,
    parse_header,
    stud_summary,
    zip_path,
)

INDEX_VERSION = 4
NON_SYSTEM = {
    "duplo",
    "primo",
    "quatro",
    "scala",
    "modulex",
    "znap",
    "clikits",
    "fabuland",
    "belville",
    "mursten",
}
# LDraw's "u" numbers are parts with no known official number yet: they cannot be ordered or
# looked up by number, and a builder on 26 November had to warn the owner about one (u9251).
_UNOFFICIAL_NUMBER = re.compile(r"^u\d+[a-z]?\d*\.dat$")
_PATTERN_NAME = re.compile(r"^[a-z]*\d+[a-z]*p[a-z0-9]{2,4}(c\d\d)?\.dat$")

SYNONYMS: dict[str, list[str]] = {
    "wing": ["wing", "wedge"],
    "tire": ["tyre"],
    "tyre": ["tyre"],
    "colour": ["colour"],
    "color": ["colour"],
    "rim": ["rim", "wheel"],
    "roof": ["roof", "slope"],
    "holder": ["holder"],
    "bracket": ["bracket"],
    "curve": ["curved"],
    "curved": ["curved"],
    "angled": ["angled"],
    "inverted": ["inverted"],
    "window": ["window"],
    "glass": ["glass"],
    "lamp": ["lamp", "light"],
    "light": ["light", "lamp"],
}
# Words LDraw does not use, rewritten into the words it does. The query is searched as typed
# and as rewritten; each part keeps its best score.
REWRITES: list[tuple[str, str]] = [
    (r"\bcheese( slope)?\b", "slope 31 1 x 1 x 0.667"),
    (r"\bjumper( plate)?\b", "plate 1 x 2 with 1 centre stud"),
    (r"\bwheel ?holder\b", "wheel pin"),
    (r"\bwheels? holder\b", "wheel pins"),
    (r"\bcenter\b", "centre"),
    (r"\bsnot\b", "brick with stud on side"),
    (r"\bheadlight brick\b", "brick 1 x 1 with headlight"),
    (r"\bgrille tile\b", "tile grille"),
    (r"\bwedge plate\b", "wing"),
    (r"\blightsaber\b", "bar 4l lightsaber blade"),
    (r"\bwheels? (for|on) (a )?wheel (pin|holder)s?\b", "wheel rim notched hole wheel holding pin"),
    (r"\bwheel pin wheels?\b", "wheel rim notched hole wheel holding pin"),
]
_IRREGULAR = {"leaves": "leaf", "wheels": "wheel", "studs": "stud", "axes": "axle"}
_STOP = {"with", "and", "for", "the", "a", "of", "on", "in", "to"}


def _dims(text: str) -> tuple[str, list[tuple[str, ...]]]:
    """The text with sizes such as '2 x 4' or '1 x 1 x 2/3' taken out, and those sizes."""
    dims: list[tuple[str, ...]] = []
    num = r"\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?"

    def take(m: re.Match[str]) -> str:
        dims.append(tuple(" ".join(g.split()) for g in m.groups() if g))
        return " "

    rest = re.sub(rf"({num})\s*x\s*({num})(?:\s*x\s*({num}))?", take, text.lower())
    return rest, dims


def _word(w: str) -> str:
    w = _IRREGULAR.get(w, w)
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.isdigit():
        w = w[:-1]
    return w


def words(text: str) -> tuple[list[str], list[tuple[str, ...]]]:
    rest, dims = _dims(text)
    ws = [_word(w) for w in re.findall(r"[a-z]+|\d+(?:\.\d+)?", rest)]
    return ws, dims


# ---- exclusions -----------------------------------------------------------------------------


def exclusion_reason(name: str, description: str, org: str, category: str) -> str | None:
    d = description.strip()
    if d.startswith("~Moved to"):
        return "moved"
    if d.startswith("~"):
        return "not for listing"
    if d.startswith("="):
        return "alias"
    if d.startswith("_"):
        return "physical colour"
    if d.startswith("|"):
        return "third party"
    if org.lower() == "shortcut":
        return "shortcut"
    if "obsolete" in d.lower() or category.lower() == "obsolete":
        return "obsolete"
    if "sticker" in d.lower() or "sticker" in category.lower():
        return "sticker"
    if "pattern" in d.lower() or _PATTERN_NAME.match(name):
        return "patterned"
    if _UNOFFICIAL_NUMBER.match(name):
        return "unofficial number"
    first = d.split()[0].lower() if d.split() else ""
    if first in NON_SYSTEM:
        return "other system"
    return None


# ---- building -------------------------------------------------------------------------------


def _summarise(lib: Library, key: str) -> dict[str, Any]:
    part = lib.part(key, columns=False)
    w, d, h = part.size()
    top = part.top_studs()
    side = [s for s in part.studs if s.axis[1] >= -0.99]
    others: dict[str, int] = {}
    for c in part.others:
        others[c.kind] = others.get(c.kind, 0) + 1
    return {
        "name": key,
        "description": part.description,
        "category": part.header.category,
        "keywords": part.header.keywords,
        "size": [round(w, 2), round(d, 2), round(h, 2)],
        "studs": len(part.studs),
        "stud_text": stud_summary(part),
        "top_studs": [[round(float(s.pos[0]), 1), round(float(s.pos[2]), 1)] for s in top][:64],
        "side_studs": [
            {
                "pos": [round(float(v), 1) for v in s.pos],
                "points": direction_word(s.axis),
            }
            for s in side
        ][:32],
        "tubes": len(part.tubes),
        "open_tubes": sum(1 for t in part.tubes if t.open),
        "others": others,
        "origin": origin_note(part),
        "missing": part.missing,
        "triangles": part.tri_count,
    }


def _work(args: tuple[str, list[str]]) -> list[dict[str, Any]]:
    path, keys = args
    lib = Library(path)
    out = []
    for key in keys:
        try:
            out.append(_summarise(lib, key))
        except Exception as e:  # a broken file must not stop the index
            out.append({"name": key, "error": f"{type(e).__name__}: {e}"})
    return out


def index_file() -> Path:
    return cache_dir() / "index.json"


def build_index(workers: int | None = None, progress: bool = False) -> dict[str, Any]:
    lib = Library()
    keys = sorted(k for k in lib.parts if "/" not in k)
    excluded: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    kept: list[str] = []
    for key in keys:
        h = parse_header(lib.text("part", key))
        why = exclusion_reason(key, h.description, h.org, h.category)
        if why:
            excluded[why] = excluded.get(why, 0) + 1
            if len(examples.setdefault(why, [])) < 4:
                examples[why].append(f"{key}: {h.description}")
        else:
            kept.append(key)
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    chunks = [kept[i :: workers * 4] for i in range(workers * 4)]
    entries: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for n, result in enumerate(pool.map(_work, [(str(lib.path), c) for c in chunks]), 1):
            entries.extend(result)
            if progress:
                print(f"  {n}/{len(chunks)} chunks", file=sys.stderr, flush=True)
    entries.sort(key=lambda e: e["name"])
    errors = [e for e in entries if "error" in e]
    entries = [e for e in entries if "error" not in e]
    stats = {
        "files_in_parts": len(keys),
        "indexed": len(entries),
        "excluded": excluded,
        "excluded_examples": examples,
        "errors": len(errors),
        "error_examples": errors[:5],
        "with_studs": sum(1 for e in entries if e["studs"]),
        "with_top_studs": sum(1 for e in entries if e["top_studs"]),
        "with_side_studs": sum(1 for e in entries if e["side_studs"]),
        "with_tubes": sum(1 for e in entries if e["tubes"]),
        "with_other_connectors": sum(1 for e in entries if e["others"]),
        "other_connector_kinds": _count_kinds(entries),
        "with_no_connector_found": sum(
            1 for e in entries if not e["studs"] and not e["tubes"] and not e["others"]
        ),
        "with_missing_files": sum(1 for e in entries if e["missing"]),
    }
    data = {"version": INDEX_VERSION, "stamp": lib.stamp, "stats": stats, "parts": entries}
    path = index_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)
    return data


def _count_kinds(entries: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in entries:
        for k in e["others"]:
            out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


_INDEX: Index | None = None


def load_index(build: bool = True) -> Index:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    path = index_file()
    data = None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        st = zip_path().stat()
        stamp_ok = str(data.get("stamp", "")).startswith(f"{st.st_size}-{int(st.st_mtime)}-")
        if data.get("version") != INDEX_VERSION or not stamp_ok:
            data = None
    except (OSError, ValueError):
        data = None
    if data is None:
        if not build:
            raise FileNotFoundError("The parts index has not been built yet.")
        data = build_index()
    _INDEX = Index(data)
    return _INDEX


# ---- searching ------------------------------------------------------------------------------


@dataclass
class Hit:
    entry: dict[str, Any]
    score: float

    @property
    def name(self) -> str:
        return self.entry["name"]

    def line(self) -> str:
        e = self.entry
        w, d, h = e["size"]
        parts = [
            f"{e['name']}: {e['description']}",
            f"category {e['category']}",
            f"{_n(w)} x {_n(d)} studs x {_n(h)} plates (x by z by height)",
            e["stud_text"],
        ]
        if e["top_studs"] and len(e["top_studs"]) <= 8:
            parts[-1] += " at " + " ".join(f"({fmt(x)},{fmt(z)})" for x, z in e["top_studs"])
        for s in e["side_studs"][:4]:
            parts.append(
                f"side stud at ({', '.join(fmt(v) for v in s['pos'])}) pointing {s['points']}"
            )
        if e["open_tubes"]:
            parts.append(f"{e['open_tubes']} open stud ring(s)/tube(s) underneath")
        if e["others"]:
            parts.append("also: " + ", ".join(f"{n} {k}" for k, n in e["others"].items()))
        parts.append(e["origin"])
        return "; ".join(parts)


def _n(v: float) -> str:
    return fmt(round(v * 4) / 4) if abs(v * 4 - round(v * 4)) < 0.05 else fmt(round(v, 2))


class Index:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.stats: dict[str, Any] = data["stats"]
        self.entries: list[dict[str, Any]] = data["parts"]
        self.by_name = {e["name"]: e for e in self.entries}
        self._prepared = [self._prepare(e) for e in self.entries]

    @staticmethod
    def _prepare(e: dict[str, Any]) -> dict[str, Any]:
        dw, dd = words(e["description"])
        cw, _ = words(e["category"])
        kw, _ = words(" ".join(e["keywords"]))
        return {
            "desc": dw,
            "desc_set": set(dw),
            "cat": set(cw),
            "kw": set(kw),
            "dims": dd,
            "flat": " " + " ".join(dw) + " ",
        }

    def search(self, query: str, limit: int = 15) -> list[Hit]:
        """The best ``limit`` parts for ``query``: the query as typed and each rewriting of
        it in LDraw's words (``REWRITES``) are scored, and each part keeps its best score."""
        variants = [query]
        low = query.lower()
        for pattern, replacement in REWRITES:
            if re.search(pattern, low):
                variants.append(re.sub(pattern, replacement, low))
        best: dict[str, Hit] = {}
        for i, v in enumerate(dict.fromkeys(variants)):
            for hit in self._search(v):
                if i:  # a rewriting is a guess: a small step below the words as typed
                    hit.score -= 0.5
                old = best.get(hit.name)
                if old is None or hit.score > old.score:
                    best[hit.name] = hit
        hits = sorted(best.values(), key=lambda h: (-h.score, h.entry["name"]))
        return hits[: max(1, limit)]

    def _search(self, query: str) -> list[Hit]:
        q = query.strip().lower()
        qn = q.removesuffix(".dat")
        qwords, qdims = words(q)
        qwords = [w for w in qwords if w not in _STOP]
        hits: list[Hit] = []
        for e, p in zip(self.entries, self._prepared, strict=True):
            score = 0.0
            name = e["name"].removesuffix(".dat")
            if qn == name:
                score += 30
            elif re.fullmatch(r"[a-z]*\d+[a-z0-9]*", qn) and name.startswith(qn):
                score += 12
            matched = 0
            for w in qwords:
                alts = [_word(a) for s in SYNONYMS.get(w, [w]) for a in s.split()]
                alts = list(dict.fromkeys([w, *alts]))
                if any(a in p["desc_set"] for a in alts):
                    score += 3.0 if w in p["desc_set"] else 2.5
                    matched += 1
                elif any(a in p["cat"] for a in alts):
                    score += 2.0
                    matched += 1
                elif any(a in p["kw"] for a in alts):
                    score += 1.5
                    matched += 1
                elif len(w) >= 4 and any(d.startswith(w) for d in p["desc_set"]):
                    score += 1.0
                    matched += 1
                else:
                    score -= 2.5
            # sizes: each size in the query is matched to a different size of the part
            free = list(p["dims"])
            for qd in qdims:
                pick, s_best = None, (-3.0 if p["dims"] else -1.5)
                for k, d in enumerate(free):
                    if d[:2] == qd[:2]:
                        s = 4.0
                        if len(qd) > 2:
                            s += 1.0 if len(d) > 2 and d[2] == qd[2] else -1.0
                        elif len(d) > 2:
                            s -= 0.5  # "brick 2 x 4" is the plain brick, not "2 x 4 x 3"
                    elif d[:2] == qd[:2][::-1]:
                        s = 3.0
                    else:
                        continue
                    if s > s_best:
                        pick, s_best = k, s
                if pick is not None:
                    free.pop(pick)
                score += s_best
            if qwords and matched == 0 and score < 10:
                continue
            phrase = " " + " ".join(qwords) + " "
            if len(qwords) > 1 and phrase in p["flat"]:
                score += 3.0
            if qwords and p["desc"] and p["desc"][0] == qwords[0]:
                score += 1.0
            extra = sum(1 for w in p["desc"] if w not in _STOP) - matched
            score -= 0.25 * max(extra, 0) + 0.5 * len(free)
            # between variants, the current one: "without", "old", "type 1" lose a little
            if p["desc_set"] & {"without", "old"} and not set(qwords) & {"without", "old"}:
                score -= 0.3
            score -= 0.002 * math.log1p(e["triangles"])  # ties: the simpler part
            hits.append(Hit(e, score))
        return hits


def search(query: str, limit: int = 15) -> list[Hit]:
    return load_index().search(query, limit)


def close_names(name: str, n: int = 5) -> list[str]:
    """Indexed part names close to ``name`` (for unknown file names)."""
    import difflib

    index = load_index()
    base = name.strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    if not base.endswith(".dat"):
        base += ".dat"
    names = list(index.by_name)
    close = difflib.get_close_matches(base, names, n=n, cutoff=0.6)
    stem = re.match(r"[a-z]*\d+", base)
    if stem:
        close += [k for k in names if k.startswith(stem.group(0)) and k not in close][:n]
    return close[:n]


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m bricksnap.lab.search")
    ap.add_argument("query", nargs="*")
    ap.add_argument("--build", action="store_true", help="(re)build the index")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args(argv)
    if args.build:
        data = build_index(progress=True)
        print(json.dumps(data["stats"], indent=1))
    index = load_index()
    if args.stats:
        print(json.dumps(index.stats, indent=1))
    if args.query:
        for i, hit in enumerate(index.search(" ".join(args.query), args.limit), 1):
            print(f"{i:2}. [{hit.score:5.1f}] {hit.line()}")


if __name__ == "__main__":
    main()
