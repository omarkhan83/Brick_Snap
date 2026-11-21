"""Art direction in guide mode: the brief before building, the critique before finishing
(research prototype, EXPERIMENTAL).

CONTRACT (tests in tests/test_art_direction.py; used by ``tools`` only in guide mode)

The style guide (``style``) asks the builder to work as an art director: write an art
direction before the first part and judge its own pictures before it finishes. Two tools
carry that, and this module answers them and keeps what they say in ``art.json`` in the
work folder.

- ``BRIEF`` (the tool ``brief``): the eight lines of the guide's section (a): ``scale``,
  ``colours`` (a list of ``{"code", "job", "share"}``), ``pattern``, ``shapes`` (three to
  five ``{"shape", "part"}``), ``sideways``, ``thin``, ``studs``, ``glass`` (glass and
  stance); ``why_more`` (why more than three body colours) and ``reason`` (why a brief that
  exists is changed). It checks form only: all eight there; every colour code in the
  library's colours (never 16 or 24); every shape's part named by at least one LDraw number
  and every number named a part in the library; at most three body colours besides black,
  the greys and the transparent ones unless ``why_more`` says why; a reason for a change.
  A bad brief is an "ERROR:" naming everything that is wrong at once. A good one is stored
  (every version, with its reason, how many parts were in when it was written, the colours'
  names and values) and the reply is two lines saying what it commits the builder to.
- ``SUBMIT`` (``submit`` in guide mode) hands in, in two steps. ``{}`` returns the hand-in
  sheet: the three views of the model as it stands, the brief's eight lines, the facts
  (``facts``) and the ten questions of section (d); it does not use a check. ``{"critique":
  {...}}`` (``style.CRITIQUE_KEYS``, each ``{"answer": "yes" | "no", "note"}``) answers
  that sheet; a critique with no sheet of the model as it now stands gets the sheet
  instead and is not recorded. A "no" needs a note of at least ``NOTE_WORDS`` words: without
  one it is refused once, naming the question. The first critique with a "no", while checks
  remain, is recorded and answered "rebuild those regions, then hand in again" (once per
  session); later ones are accepted with their "no"s. Answers missing or not yes or no are
  an "ERROR:" naming them. ``{"ldraw": ...}`` replaces the whole model and checks it as
  ``submit`` always did (a critique sent with it is not recorded); before a brief it is
  treated as ``add``.
- ``place`` in guide mode also takes ``{"parts": [...]}``: up to ``MAX_BATCH`` placements
  done in turn by the ordinary ``place``, the reply listing each, stopping at the first that
  fails (``PLACE``).
- ``call(folder, name, args, handler)``: answers one tool call in guide mode. The first
  ``place``, ``add``, ``fill``, ``place_module`` or ``submit`` with ldraw before any brief
  is refused once, with a sentence saying to write the brief first (a builder that insists
  goes on, and the record says it built without one). Whatever the tool and whatever its
  reply, a call after which ``model.ldr`` differs is a change; a critique given before a
  change is marked as such. When about half the parts asked for are in, the next ``check``
  reply ends with the brief's eight lines and a question (once; advice, no refusal).
- ``seed(folder, brief, from_run)``: a change run starts with the model's brief, carried
  over (version 1, marked as carried); a new version needs a reason as any change does.
- ``facts(folder)``: what can be counted on the model as it stands: parts against parts
  asked for, its size in studs, its colours against the brief's, colours over 5% the brief
  does not name, body colours used, the glass, and the HOW IT LOOKS lines (``looks``). The
  colours are as the five views of ``looks`` see them; when the model cannot be measured,
  by bulk (every part's box).
- ``playbook_kind(folder, found)`` and ``playbook_style(folder, word, kind)``: the playbook's
  kind made precise by the subject's words (a vehicle that flies is an aircraft), and the
  style guide's section (c) for it, with the sentence saying which governs what; the
  sections chosen are added to playbook.json as "style".
- ``record(folder)``: what session.json keeps: ``brief`` (the last, or null), ``briefs``
  (every version: n, brief, reason, carried, parts_before), ``built_without_brief``,
  ``critique`` (the last: answers with their questions, the facts, ``changed_after``,
  ``unexplained``), ``critiques`` (how many), ``first_no`` (the first critique's "no"s when
  it was sent back), ``ended_without_critique`` and ``art`` (true: the record has these).
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bricksnap.lab import style

STATE_FILE = "art.json"
GATED = ("place", "add", "fill", "place_module", "clip", "strut")
FIELD_CHARS = 600
NOTE_WORDS = 3
MAX_BATCH = 40
OTHER_COLOUR_SHARE = 0.05
_TEXT_KEYS = ("scale", "pattern", "sideways", "thin", "studs", "glass")
_PART_NUMBER = re.compile(r"(?<![\w.])(\d{3,6}[a-z]{0,2}\d{0,2}(?:p[a-z0-9]+)?)(?:\.dat)?(?![\w])")

OUT_OF_CHECKS = (
    "this session has used all {limit} checks. Hand in now: submit {{}} shows the model "
    "beside your brief; answer its questions with submit's critique, then write your "
    "closing words."
)

Blocks = list[dict[str, Any]]


def _brief_description() -> str:
    lines = "\n".join(f'- "{key}" ({title}): {what}' for key, title, what in style.brief_lines())
    return (
        "Your art direction, written before you place the first part, once you have found "
        "the parts that make the subject's signature shapes (from the style guide). Eight "
        "lines, each plain words:\n" + lines + "\n"
        '"colours" is a list of {"code": LDraw colour code, "job": where it goes, "share": '
        'about how much of what is seen, e.g. "70%"}; "shapes" is a list of three to five '
        '{"shape": what it is, "part": the part that makes it, by its LDraw number}. At most '
        "three body colours besides black, the greys and the transparent ones, unless "
        '"why_more" says why. Call it again to change the brief on purpose, with "reason": '
        "every version is kept. Returns two lines saying what the brief commits you to."
    )


def _question_list() -> str:
    return "\n".join(f'- "{k}": {q}' for k, q in style.questions())


def _submit_description() -> str:
    return (
        "Hand in the finished model, in two steps. First {}: it shows the model as it stands "
        "from three sides beside your brief, with what can be counted on it (colours, size, "
        "parts, glass, how it looks) and ten questions; it does not use a check. Then "
        '{"critique": {"outline": {"answer": "yes"}, "studs": {"answer": "no", "note": "what '
        'you rebuilt, or why it stays"}, ...}}, answering every question about that sheet. '
        + style.critique_intro()
        + " The ten questions:\n"
        + _question_list()
        + '\nEach needs "yes" or "no"; each "no" needs a note of a few words. If you change '
        "the model after the sheet, ask for a new one. Instead, "
        '{"ldraw": "..."} replaces the whole model with this LDraw text and checks it, exactly '
        "as check does (counts as a check); use that only when rewriting everything is "
        "easier than fixing it."
    )


_ANSWER = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "enum": ["yes", "no"]},
        "note": {"type": "string"},
    },
    "required": ["answer"],
    "additionalProperties": False,
}

BRIEF: dict[str, Any] = {
    "name": "brief",
    "description": _brief_description(),
    "input_schema": {
        "type": "object",
        "properties": {
            "scale": {"type": "string"},
            "colours": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "job": {"type": "string"},
                        "share": {"type": "string"},
                    },
                    "required": ["code", "job"],
                    "additionalProperties": False,
                },
            },
            "pattern": {"type": "string"},
            "shapes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"shape": {"type": "string"}, "part": {"type": "string"}},
                    "required": ["shape", "part"],
                    "additionalProperties": False,
                },
            },
            "sideways": {"type": "string"},
            "thin": {"type": "string"},
            "studs": {"type": "string"},
            "glass": {"type": "string"},
            "why_more": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": list(style.BRIEF_KEYS),
        "additionalProperties": False,
    },
}

SUBMIT: dict[str, Any] = {
    "name": "submit",
    "description": _submit_description(),
    "input_schema": {
        "type": "object",
        "properties": {
            "critique": {
                "type": "object",
                "properties": {k: _ANSWER for k in style.CRITIQUE_KEYS},
                "additionalProperties": False,
            },
            "ldraw": {"type": "string"},
        },
        "additionalProperties": False,
    },
}


def place_tool(base: dict[str, Any]) -> dict[str, Any]:
    """Guide mode's ``place``: the ordinary one, which also takes a list of placements."""
    out = copy.deepcopy(base)
    one = copy.deepcopy(base["input_schema"]["properties"])
    out["description"] = (
        base["description"] + "\n"
        f'4. Many at once: {{"parts": [{{...}}, {{...}}]}}, up to {MAX_BATCH} placements '
        "of the kinds above, done in turn; each new part takes the next line number, so a "
        "later one may stand on an earlier one. The reply lists each; it stops at the first "
        "that fails, and the ones before it stay."
    )
    props = out["input_schema"]["properties"]
    props["parts"] = {
        "type": "array",
        "maxItems": MAX_BATCH,
        "items": {"type": "object", "properties": one, "additionalProperties": False},
    }
    out["input_schema"].pop("required", None)
    return out


# ---- the state -------------------------------------------------------------------------------


def _state(folder: Path) -> dict[str, Any]:
    fresh: dict[str, Any] = {
        "briefs": [],
        "build_refused": False,
        "built_without_brief": False,
        "changes": 0,
        "sheet": None,
        "critiques": [],
        "rebuild_asked": False,
        "midway_done": False,
        "refused": [],
    }
    try:
        data = json.loads((folder / STATE_FILE).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**fresh, **data}
    except (OSError, ValueError):
        pass
    return fresh


def _save(folder: Path, state: dict[str, Any]) -> None:
    tmp = folder / (STATE_FILE + ".tmp")
    tmp.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    tmp.replace(folder / STATE_FILE)


def _text(t: str) -> dict[str, Any]:
    return {"type": "text", "text": t}


def _error(t: str) -> Blocks:
    return [_text("ERROR: " + t)]


def _failed(blocks: Blocks) -> bool:
    return len(blocks) == 1 and str(blocks[0].get("text", "")).startswith("ERROR:")


def _config(folder: Path) -> dict[str, Any]:
    try:
        data = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _model(folder: Path) -> str:
    try:
        return (folder / "model.ldr").read_text(encoding="utf-8")
    except OSError:
        return ""


def _hash(folder: Path) -> str:
    return hashlib.sha256(_model(folder).encode()).hexdigest()


def _parts(folder: Path) -> int:
    return sum(1 for ln in _model(folder).splitlines() if ln.startswith("1 "))


def _refuse(state: dict[str, Any], why: str) -> None:
    state["refused"].append({"why": why, "time": time.time()})


def _refused(state: dict[str, Any], why: str) -> bool:
    return any(r.get("why") == why for r in state["refused"])


def _checks_left(folder: Path) -> int:
    cfg = _config(folder)
    limit = int(cfg.get("max_checks", 25))
    done = [p for p in (folder / "attempts").glob("attempt-*.ldr") if p.stem != "attempt-000"]
    return max(0, limit - len(done))


def seed(folder: Path, brief: dict[str, Any], from_run: int | None = None) -> None:
    """Start a change run with the model's brief, carried over as version 1."""
    state = _state(folder)
    state["briefs"] = [
        {
            "n": 1,
            "brief": brief,
            "reason": None,
            "carried": True,
            "from_run": from_run,
            "parts_before": _parts(folder),
            "time": time.time(),
        }
    ]
    _save(folder, state)


# ---- the brief -------------------------------------------------------------------------------


def _colours() -> tuple[dict[int, str], dict[int, str]]:
    from bricksnap.lab.ldraw_lib import library

    lib = library()
    return lib.colours(), lib.colour_values()


def neutral(name: str) -> bool:
    """Black, a grey or a transparent colour: what the guide's colour count leaves out."""
    n = name.lower()
    return n == "black" or "grey" in n or "gray" in n or n.startswith("trans")


def _short(v: Any, limit: int = FIELD_CHARS) -> str:
    s = " ".join(str(v).split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def part_numbers(text: str) -> list[str]:
    """The LDraw part numbers (or file names) a piece of text names."""
    return [m.group(1) for m in _PART_NUMBER.finditer(text.lower())]


def _unknown_parts(numbers: list[str]) -> list[str]:
    try:
        from bricksnap.lab.ldraw_lib import library

        lib = library()
    except (OSError, FileNotFoundError):
        return []
    return [n for n in numbers if lib.resolve(n + ".dat") is None]


def check_brief(args: dict[str, Any], names: dict[int, str]) -> tuple[list[str], dict[str, Any]]:
    """What is wrong with a brief (empty when nothing), and the brief as it is kept."""
    wrong: list[str] = []
    kept: dict[str, Any] = {}
    missing = [k for k in _TEXT_KEYS if not isinstance(args.get(k), str) or not args[k].strip()]
    for k in _TEXT_KEYS:
        if k not in missing:
            kept[k] = _short(args[k])
    colours = args.get("colours")
    kept_colours = []
    if not isinstance(colours, list) or not colours:
        missing.append("colours")
    else:
        for c in colours:
            code = c.get("code") if isinstance(c, dict) else None
            job = c.get("job") if isinstance(c, dict) else None
            if not isinstance(code, int) or isinstance(code, bool) or not isinstance(job, str):
                wrong.append(
                    'each colour is {"code": an LDraw colour code, "job": where it goes, '
                    '"share": about how much}'
                )
                break
            if code in (16, 24) or (names and code not in names):
                own = " (16 and 24 have no colour of their own)" if code in (16, 24) else ""
                wrong.append(f"there is no colour {code} in the library{own}")
                continue
            share = c.get("share")
            kept_colours.append(
                {
                    "code": code,
                    "name": names.get(code, ""),
                    "job": _short(job, 200),
                    "share": _short(share, 40) if share is not None else "",
                }
            )
    shapes = args.get("shapes")
    kept_shapes = []
    if not isinstance(shapes, list) or not shapes:
        missing.append("shapes")
    else:
        for s in shapes:
            if (
                not isinstance(s, dict)
                or not str(s.get("shape") or "").strip()
                or not str(s.get("part") or "").strip()
            ):
                wrong.append('each shape is {"shape": what it is, "part": the part that makes it}')
                break
            shape, part = _short(s["shape"], 200), _short(s["part"], 120)
            numbers = part_numbers(part)
            if not numbers:
                wrong.append(
                    f"name the part that makes '{shape[:60]}' by its LDraw number "
                    '(search_parts finds it), as in "curved slope 11477"'
                )
            for n in _unknown_parts(numbers):
                wrong.append(
                    f"there is no part {n} in the library (named for '{shape[:60]}'): "
                    "search_parts finds the real number"
                )
            kept_shapes.append({"shape": shape, "part": part})
        else:
            if not 3 <= len(shapes) <= 5:
                wrong.append(f"give three to five shapes (you gave {len(shapes)})")
    if missing:
        order = [k for k in style.BRIEF_KEYS if k in missing]
        titles = {k: t.lower() for k, t, _ in style.brief_lines()}
        wrong.insert(0, "it has no " + ", no ".join(f'"{k}" ({titles[k]})' for k in order))
    body = [c for c in kept_colours if not neutral(c["name"] or str(c["code"]))]
    why_more = args.get("why_more")
    if len({c["code"] for c in body}) > 3 and not (isinstance(why_more, str) and why_more.strip()):
        listed = ", ".join(f"{c['code']} {c['name']}".strip() for c in body)
        wrong.append(
            f"it has {len(body)} body colours ({listed}); the guide asks for at most three "
            'besides black, the greys and the transparent ones: drop one, or say why in "why_more"'
        )
    kept["colours"] = kept_colours
    kept["shapes"] = kept_shapes
    if isinstance(why_more, str) and why_more.strip():
        kept["why_more"] = _short(why_more)
    return wrong, {k: kept[k] for k in (*style.BRIEF_KEYS, "why_more") if k in kept}


def _colour_words(c: dict[str, Any]) -> str:
    share = f", {c['share']}" if c.get("share") else ""
    return f"{c['code']} {c.get('name') or ''}".strip() + f" ({c['job']}{share})"


def _commits(b: dict[str, Any]) -> str:
    first = (
        f"It commits you to: {b['scale']}; colours "
        f"{'; '.join(_colour_words(c) for c in b['colours'])}; pattern: {b['pattern']}."
    )
    shapes = "; ".join(f"{s['shape']} ({s['part']})" for s in b["shapes"])
    second = (
        f"Build these shapes: {shapes}. Sideways: {b['sideways']}. Thin: {b['thin']}. "
        f"Studs: {b['studs']}. Glass and stance: {b['glass']}."
    )
    return first + "\n" + second


def brief_lines(b: dict[str, Any]) -> str:
    """The brief as its eight lines, for the sheet, the halfway reminder and a change run."""
    shapes = "; ".join(f"{s['shape']} ({s['part']})" for s in b.get("shapes") or [])
    colours = "; ".join(_colour_words(c) for c in b.get("colours") or [])
    values = {**b, "colours": colours, "shapes": shapes}
    out = [f"{title}: {values.get(key, '')}" for key, title, _ in style.brief_lines()]
    if b.get("why_more"):
        out.append(f"Why more colours: {b['why_more']}")
    return "\n".join(out)


def _brief(folder: Path, args: dict[str, Any], state: dict[str, Any]) -> Blocks:
    try:
        names, values = _colours()
    except (OSError, FileNotFoundError):
        names, values = {}, {}
    wrong, kept = check_brief(args, names)
    reason = args.get("reason")
    has_reason = isinstance(reason, str) and reason.strip()
    if state["briefs"] and not has_reason:
        wrong.append('this changes the brief the model has: say why in "reason"')
    if wrong:
        return _error("the brief is not complete: " + "; ".join(wrong) + ".")
    for c in kept["colours"]:
        c["value"] = values.get(c["code"], "")
    n = len(state["briefs"]) + 1
    state["briefs"].append(
        {
            "n": n,
            "brief": kept,
            "reason": _short(reason, 400) if has_reason else None,
            "carried": False,
            "parts_before": _parts(folder),
            "time": time.time(),
        }
    )
    head = f"Brief {n} recorded" + (" (the change and its reason are kept)." if n > 1 else ".")
    return [_text(head + " " + _commits(kept))]


# ---- the facts beside the questions ----------------------------------------------------------


def facts(folder: Path, brief: dict[str, Any] | None) -> dict[str, Any]:
    """What can be counted on the model as it stands (see the contract)."""
    import numpy as np

    from bricksnap.lab.validate import check

    text = _model(folder)
    out: dict[str, Any] = {"parts": _parts(folder), "parts_wanted": _config(folder).get("parts")}
    try:
        report = check(text, movement=False)
        names, _ = _colours()
    except Exception:  # the facts are extras: the hand-in never fails for them
        return out
    bulk: dict[int, float] = {}
    glass: dict[int, int] = {}
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for p in report.placed:
        size = np.maximum(p.part.bbox_max - p.part.bbox_min, 1.0)
        bulk[p.colour] = bulk.get(p.colour, 0.0) + float(np.prod(size))
        corners = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
        box = p.part.bbox_min + corners * (p.part.bbox_max - p.part.bbox_min)
        world = p.to_world(box)
        lo, hi = np.minimum(lo, world.min(axis=0)), np.maximum(hi, world.max(axis=0))
        if names.get(p.colour, "").lower().startswith("trans"):
            glass[p.colour] = glass.get(p.colour, 0) + 1
    seen, looks = _looks(report)
    shares = seen or bulk
    total = sum(shares.values()) or 1.0
    colours: list[dict[str, Any]] = [
        {"code": c, "name": names.get(c, str(c)), "share": round(v / total, 3)}
        for c, v in sorted(shares.items(), key=lambda kv: -kv[1])
    ]
    out["colours"] = colours
    out["colours_by"] = "seen" if seen else "bulk"
    out["glass"] = [
        {"code": c, "name": names.get(c, str(c)), "parts": n} for c, n in sorted(glass.items())
    ]
    if report.placed:
        d = hi - lo
        out["size"] = {
            "wide": round(float(d[0]) / 20, 1),
            "long": round(float(d[2]) / 20, 1),
            "high_bricks": round(float(d[1]) / 24, 1),
        }
    body = [c for c in colours if not neutral(c["name"]) and c["share"] >= 0.01]
    out["body_colours"] = len(body)
    if brief is not None:
        named = {c.get("code") for c in brief.get("colours") or []}
        out["not_in_brief"] = [
            c for c in colours if c["code"] not in named and c["share"] > OTHER_COLOUR_SHARE
        ]
        used = {c["code"] for c in colours}
        out["brief_unused"] = [
            {"code": c["code"], "name": c.get("name", "")}
            for c in brief.get("colours") or []
            if c.get("code") not in used
        ]
    if looks:
        out["looks"] = looks
    return out


def _looks(report: Any) -> tuple[dict[int, float], list[str]]:
    """The colours as the five views see them, and the HOW IT LOOKS lines (``looks``);
    nothing when the model cannot be measured (the hand-in never fails for it)."""
    from bricksnap.lab import looks

    try:
        if not report.placed:
            return {}, []
        sk = looks.skin(report.placed)
        return looks.colour_shares(sk), [
            str(x) for x in looks.lines(looks.measure_skin(report, sk))
        ]
    except Exception:  # advice only
        return {}, []


def _pct(share: float) -> str:
    return f"{round(share * 100)}%"


def facts_text(f: dict[str, Any], brief: dict[str, Any] | None) -> str:
    lines = []
    wanted = f.get("parts_wanted")
    lines.append(
        f"Parts: {f.get('parts', 0)}" + (f" of about {wanted} asked for." if wanted else ".")
    )
    if f.get("size"):
        s = f["size"]
        lines.append(
            f"Size: {s['wide']:g} studs wide (x), {s['long']:g} long (z), {s['high_bricks']:g} "
            "bricks high." + (f" Your brief's scale: {brief['scale']}" if brief else "")
        )
    if f.get("colours"):
        top = ", ".join(f"{c['name']} {c['code']} {_pct(c['share'])}" for c in f["colours"][:6])
        how = (
            "as seen from five sides"
            if f.get("colours_by") == "seen"
            else "by bulk (every part's box; hidden parts count too)"
        )
        lines.append(f"Colours {how}: {top}.")
        if brief:
            said = ", ".join(
                f"{c.get('name') or c['code']} {c['code']}"
                + (f" {c['share']}" if c.get("share") else "")
                for c in brief.get("colours") or []
            )
            lines.append(f"Your brief's colours: {said}.")
        lines.append(f"Body colours used (not black, grey or transparent): {f['body_colours']}.")
        if f.get("not_in_brief"):
            extra = ", ".join(
                f"{c['name']} {c['code']} {_pct(c['share'])}" for c in f["not_in_brief"]
            )
            lines.append(f"Over 5% and not in your brief: {extra}.")
        if f.get("brief_unused"):
            gone = ", ".join(f"{c['name'] or c['code']} {c['code']}" for c in f["brief_unused"])
            lines.append(f"In your brief but not in the model: {gone}.")
        glass = ", ".join(f"{g['name']} {g['code']} ({g['parts']} parts)" for g in f["glass"])
        lines.append(f"Transparent parts: {glass or 'none'}.")
    if f.get("looks"):
        lines.append("HOW IT LOOKS (measured on the model as it stands):")
        lines.extend(f"- {x}" for x in f["looks"])
    return "\n".join(lines)


def mismatches(f: dict[str, Any], brief: dict[str, Any] | None) -> list[str]:
    """Plain sentences where the counted model and the brief disagree (for the page)."""
    out = []
    if brief and f.get("colours"):
        said = ", ".join(
            f"{c.get('name') or c['code']}" + (f" {c['share']}" if c.get("share") else "")
            for c in brief.get("colours") or []
        )
        top = ", ".join(f"{c['name']} {_pct(c['share'])}" for c in f["colours"][:4])
        how = "as seen" if f.get("colours_by") == "seen" else "by bulk"
        if f.get("not_in_brief") or f.get("brief_unused") or f.get("body_colours", 0) > 3:
            out.append(f"The brief said: {said}. The model, {how}: {top}.")
    if f.get("body_colours", 0) > 3:
        out.append(f"The model has {f['body_colours']} body colours; the guide asks for three.")
    wanted, parts = f.get("parts_wanted"), f.get("parts")
    if isinstance(wanted, int) and isinstance(parts, int) and parts < 0.7 * wanted:
        out.append(f"It used {parts} parts of about {wanted} asked for.")
    return out


# ---- handing in ------------------------------------------------------------------------------


def _questions_text() -> str:
    return "\n".join(f"{i}. {k}: {q}" for i, (k, q) in enumerate(style.questions(), 1))


def _last_brief(state: dict[str, Any]) -> dict[str, Any] | None:
    return state["briefs"][-1]["brief"] if state["briefs"] else None


def _sheet(folder: Path, state: dict[str, Any], head: str = "") -> Blocks:
    brief = _last_brief(state)
    counted = facts(folder, brief)
    state["sheet"] = {"changes": state["changes"], "facts": counted, "time": time.time()}
    n = len(state["briefs"])
    said = (
        f"YOUR BRIEF (version {n}):\n{brief_lines(brief)}"
        if brief
        else "YOUR BRIEF: none was written."
    )
    body = (
        (head + "\n\n" if head else "")
        + "HAND-IN SHEET: the model as it stands, from three sides (this does not use a "
        "check).\n\n"
        + said
        + "\n\nWHAT CAN BE COUNTED:\n"
        + facts_text(counted, brief)
        + "\n\nTHE TEN QUESTIONS. "
        + style.critique_intro()
        + "\n"
        + _questions_text()
        + '\n\nAnswer with submit {"critique": {"outline": {"answer": "yes"}, ...}}: each '
        '"yes" or "no", each "no" with a note of a few words (what you rebuilt, or why it '
        'stays). A "yes" that the counts above contradict is wrong.'
    )
    blocks: Blocks = [_text(body)]
    text = _model(folder)
    if any(ln.startswith("1 ") for ln in text.splitlines()):
        from bricksnap.lab import picture
        from bricksnap.lab.tools import _image_block

        out = (
            folder / "handin" / f"sheet-{len(list((folder / 'handin').glob('*.png'))) + 1:02d}.png"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            picture.model_sheet(text, out, title="Hand-in: the model as it stands")
            if out.exists():
                blocks.append(_image_block(out))
        except picture.PictureError as e:
            blocks.append(_text(f"(No picture: {e})"))
    return blocks


def _note_ok(note: str) -> bool:
    return len(re.findall(r"[A-Za-z]{2,}", note)) >= NOTE_WORDS


def _submit(
    folder: Path, args: dict[str, Any], state: dict[str, Any], rewrite: Callable[..., Blocks]
) -> Blocks:
    critique = args.get("critique")
    if args.get("ldraw") is not None:
        blocks = rewrite(folder, {"ldraw": args.get("ldraw")})
        if critique is not None:
            blocks.append(
                _text(
                    "Your critique was not recorded: the model has just been replaced. Hand "
                    "in with submit {} for the sheet of it, then answer."
                )
            )
        return blocks
    if critique is None:
        return _sheet(folder, state)
    sheet = state.get("sheet")
    if not sheet or sheet.get("changes") != state["changes"]:
        head = (
            "Your critique was not recorded: "
            + (
                "the model has changed since its hand-in sheet"
                if sheet
                else "a critique answers the hand-in sheet"
            )
            + ". Here is the sheet of the model as it stands; answer with it in front of you."
        )
        return _sheet(folder, state, head)
    keys = [k for k, _ in style.questions()]
    if not isinstance(critique, dict):
        return _error('critique must be {"outline": {"answer": "yes"}, ...} for the ten questions.')
    unknown = [str(k)[:30] for k in critique if k not in keys]
    missing = [k for k in keys if k not in critique]
    bad = [
        k
        for k in keys
        if k in critique
        and (
            not isinstance(critique[k], dict)
            or str(critique[k].get("answer", "")).strip().lower() not in ("yes", "no")
        )
    ]
    if unknown or missing or bad:
        said = []
        if missing:
            said.append("no answer to " + ", ".join(missing))
        if bad:
            said.append('"answer" must be "yes" or "no" for ' + ", ".join(bad))
        if unknown:
            said.append("there is no question " + ", ".join(unknown))
        return _error(
            "the critique is not complete: " + "; ".join(said) + ".\n" + _questions_text()
        )
    answers = []
    unexplained = []
    for k, q in style.questions():
        a = critique[k]
        answer = str(a.get("answer")).strip().lower()
        note = a.get("note")
        note = _short(note, 400) if isinstance(note, str) and note.strip() else ""
        if answer == "no" and not _note_ok(note):
            unexplained.append(k)
        answers.append({"key": k, "question": q, "answer": answer, "note": note})
    if unexplained and not _refused(state, "unexplained no"):
        _refuse(state, "unexplained no")
        named = "; ".join(f"{k}: {dict(style.questions())[k]}" for k in unexplained)
        return _error(
            f'a "no" needs a note of at least {NOTE_WORDS} words: what you rebuilt (a "no" '
            "means rebuild that region, not add parts), or why it stays. Without one: " + named
        )
    no = [a["key"] for a in answers if a["answer"] == "no"]
    entry = {
        "answers": answers,
        "facts": sheet.get("facts") or {},
        "changed_after": False,
        "unexplained": unexplained,
        "time": time.time(),
    }
    state["critiques"].append(entry)
    yes = len(answers) - len(no)
    if no and not state["rebuild_asked"] and _checks_left(folder) > 0:
        state["rebuild_asked"] = True
        entry["sent_back"] = True
        listed = "; ".join(f"{k}: {dict(style.questions())[k]}" for k in no)
        return [
            _text(
                f"Critique recorded: {yes} yes, {len(no)} no. You answered no to: {listed}. "
                "Rebuild those regions now (a no means rebuild, not add parts), check, then "
                "hand in again with submit {} and a new critique. This is asked once: the "
                "next hand-in is accepted with the no's that remain and their reasons."
            )
        ]
    return [
        _text(
            f"Critique recorded: {yes} yes, {len(no)} no. The model is handed in as it stands: "
            "write your closing words now. (If you change it again, hand in again.)"
        )
    ]


def _changed(state: dict[str, Any]) -> None:
    state["changes"] = int(state.get("changes") or 0) + 1
    if state["critiques"]:
        state["critiques"][-1]["changed_after"] = True


# ---- placing many ----------------------------------------------------------------------------


def _place_many(folder: Path, items: Any, handler: Callable[..., Blocks]) -> Blocks:
    if not isinstance(items, list) or not items:
        return _error('parts must be a list of placements, e.g. [{"part": "3001.dat", ...}].')
    if len(items) > MAX_BATCH:
        return _error(f"place at most {MAX_BATCH} parts in one call.")
    said = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            said.append(f"{i}. ERROR: each placement is an object like a single place call.")
            break
        reply = handler(folder, item)
        text = "\n".join(str(b.get("text", "")) for b in reply if b.get("type") == "text")
        said.append(f"{i}. {text}")
        if _failed(reply):
            said.append(f"Stopped at placement {i}; the {i - 1} before it are in the model.")
            break
    return [_text("\n\n".join(said))]


# ---- one call --------------------------------------------------------------------------------


def _gate(state: dict[str, Any]) -> Blocks | None:
    if state["briefs"] or state["build_refused"]:
        return None
    state["build_refused"] = True
    _refuse(state, "no brief")
    return _error(
        "write the art direction first: call brief with its eight lines (scale, colours, "
        "pattern, shapes, sideways, thin, studs, glass and stance), then build to it. If you "
        "are sure you do not need one, call this again."
    )


def _midway(folder: Path, state: dict[str, Any]) -> Blocks:
    wanted = _config(folder).get("parts")
    if state["midway_done"] or not isinstance(wanted, int) or _parts(folder) * 2 < wanted:
        return []
    state["midway_done"] = True
    brief = _last_brief(state)
    if brief is None:
        return [
            _text(
                f"HALFWAY (about {_parts(folder)} of {wanted} parts are in): you have no "
                "brief. Write one now with brief, and see whether what stands follows it."
            )
        ]
    return [
        _text(
            f"HALFWAY (about {_parts(folder)} of {wanted} parts are in). Your brief:\n"
            + brief_lines(brief)
            + "\nDoes what stands so far follow it? If not, fix it now, while it is cheap."
        )
    ]


def call(
    folder: Path, name: str, args: dict[str, Any], handler: Callable[..., Blocks] | None
) -> Blocks:
    """Answer one tool call in guide mode (see the contract)."""
    state = _state(folder)
    before = _hash(folder)
    building = name in GATED or (name == "submit" and args.get("ldraw") is not None)
    refusal = _gate(state) if building else None
    if refusal is not None:
        blocks = refusal
    elif name == "brief":
        blocks = _brief(folder, args, state)
    elif name == "submit":
        assert handler is not None
        blocks = _submit(folder, args, state, handler)
    elif name == "place" and "parts" in args:
        assert handler is not None
        blocks = _place_many(folder, args.get("parts"), handler)
    else:
        assert handler is not None
        blocks = handler(folder, args)
        if name == "check" and not _failed(blocks):
            blocks = blocks + _midway(folder, state)
    if _hash(folder) != before:  # whatever the tool and whatever its reply
        _changed(state)
        if not state["briefs"]:
            state["built_without_brief"] = True
    _save(folder, state)
    return blocks


# ---- the playbook's kind and style section ---------------------------------------------------


def _subject(folder: Path) -> str:
    return str(_config(folder).get("subject") or "")


def playbook_kind(folder: Path, found: str) -> str:
    from bricksnap.lab import guide

    return guide.refine(found, _subject(folder))


PRECEDENCE = (
    "Which governs what: the structural playbook above governs strength and the order of "
    "building; the style section below governs shape, surface and colour. Where they "
    "disagree about how the body is made, the style section wins."
)


def playbook_style(folder: Path, word: str, kind: str) -> str:
    names, why = style.subject_for(kind, f"{word} {_subject(folder)}")
    sections = style.subjects()
    with contextlib.suppress(OSError, ValueError):
        path = folder / "playbook.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["style"] = names
            path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    body = "\n\n".join(sections[n] for n in names)
    return (
        f"\n\n{PRECEDENCE}\n\nHOW IT SHOULD LOOK (style guide, {' and '.join(names)}). {why} "
        "What makes this kind of subject look dated, and what to do instead:\n\n" + body
    )


# ---- the record --------------------------------------------------------------------------------


def record(folder: Path) -> dict[str, Any]:
    state = _state(folder)
    briefs: list[dict[str, Any]] = [
        {
            "n": b["n"],
            "brief": b["brief"],
            "reason": b.get("reason"),
            "carried": bool(b.get("carried")),
            "from_run": b.get("from_run"),
            "parts_before": b.get("parts_before"),
        }
        for b in state["briefs"]
    ]
    crits = state["critiques"]
    last = crits[-1] if crits else None
    critique = None
    if last is not None:
        critique = {k: last.get(k) for k in ("answers", "facts", "changed_after", "unexplained")}
        critique["mismatches"] = mismatches(
            last.get("facts") or {}, briefs[-1]["brief"] if briefs else None
        )
    first_no = None
    if len(crits) > 1 and crits[0].get("sent_back"):
        first_no = [a["key"] for a in crits[0]["answers"] if a["answer"] == "no"]
    return {
        "art": True,
        "brief": briefs[-1]["brief"] if briefs else None,
        "briefs": briefs,
        "built_without_brief": bool(state.get("built_without_brief")),
        "critique": critique,
        "critiques": len(crits),
        "first_no": first_no,
        "ended_without_critique": critique is None,
    }
