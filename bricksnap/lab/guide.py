"""The set designers' guide, as the AI builder reads it (research prototype, EXPERIMENTAL).

CONTRACT (tests in tests/test_guide.py)

The guide comes from the study ``docs/research/2026-11-19-how-real-sets-are-built/``. Its text
lives in two places with the same bytes: the study's ``guide.md`` (the record of the study)
and ``bricksnap/lab/guide.md`` (what the builder is given at run time, inside the package so
it ships with it). A test holds them equal: a change to what the builder is told is made to
both in the same commit, so the study always shows what was tested.

The reader finds its parts by their headings, and a test fails when one goes missing:
``## Rules for any subject`` (the twelve numbered rules), ``## Playbooks`` (``### <Kind>, <N>
parts``, two sizes for each of six kinds), ``## Parts by job`` (a table, then the paragraph
"Sizes that fit"). Everything before the rules is the words (``words()``).

- ``rules(evidence=False)``: the twelve rules as a numbered list, one line each; without
  ``evidence`` the bracketed sources ("[10 of 10]", "[36 models]") are left out, which is
  how the builder's instructions carry them (the figures in the sentences stay).
- ``kinds()``: ``{kind: one line}`` for the six kinds: vehicle, aircraft, hollow, creature,
  plant, machine (``KIND_LINES``, which must name every kind the file has).
- ``kind_of(word)``: a kind from a word the builder might use ("car", "plane", "house",
  "animal", "flower", "technic"...); None when there is none. ``refine(kind, words)``: a
  vehicle whose subject's words say it flies is an aircraft.
- ``playbook(kind, parts)``: ``(title, text, why)``: the playbook of that kind whose size is
  nearest ``parts`` on a ratio scale (so 200 parts is the dividing line between 100 and
  400), with a sentence saying which was chosen and why. Raises ``KeyError`` for a kind the
  guide has not.
- ``parts_table()``: the parts-by-job table and the sizes that fit.
- ``SYSTEM_PROMPT`` handling: ``system_prompt(base)`` turns the builder's standing
  instructions (``prompt.md``) into the guide-mode ones: the working order rewritten as one
  method (the core chosen for the subject, with side studs where skin attaches; the skin as
  panels pressed on sideways; what sticks out last; ``playbook`` called once at the start,
  and named in the closing words), a paragraph on making a panel with ``place``, the rules,
  one sentence on what the checker cannot confirm, and the vehicle's lift-off roof added to
  the section on things that move. Every place it changes must be found exactly once in
  ``base`` (``ValueError`` otherwise), so a change to ``prompt.md`` cannot silently leave
  the guide-mode instructions saying two things. The result then gains the art direction
  of the style guide (``style.system_prompt``: the brief, the rules of finish, the
  critique).
"""

from __future__ import annotations

import math
import re
from functools import cache
from pathlib import Path

GUIDE_FILE = Path(__file__).parent / "guide.md"
RULES_HEADING = "## Rules for any subject"
PLAYBOOKS_HEADING = "## Playbooks"
TABLE_HEADING = "## Parts by job"
SIZES_MARK = "**Sizes that fit.**"
_PLAYBOOK = re.compile(r"^### (.+), (\d+) parts\s*$", re.M)
_EVIDENCE = re.compile(r"\s*\[[^\]]*\]")

KIND_LINES = {
    "vehicle": "a car, truck, train or boat: a base as long as the vehicle, side units, end "
    "faces as panels, wheels last",
    "aircraft": "a plane, helicopter or spaceship: a 2-stud core of side-stud bricks with skins, "
    "the wing one long locked plate course, gear and struts last",
    "hollow": "a building, room, house or box with an inside: a plate, walls one stud thick, "
    "a lid that lifts off",
    "creature": "an animal, character, figure or sculpture: a block of side-stud bricks with "
    "a panel on each face, a head of its own",
    "plant": "a potted plant or flowers: a pot, a spine of bars or axles, leaves and petals "
    "on clips",
    "machine": "a machine or framed model that works (gears, an arm, steering): a block of "
    "beams and pins round what moves",
}

_WORDS = {
    "vehicle": "vehicle car truck lorry van bus train tram locomotive boat ship tractor bike "
    "motorbike motorcycle tank digger excavator",
    "aircraft": "aircraft plane aeroplane airplane jet helicopter glider biplane seaplane "
    "airliner cessna fighter rocket spaceship spacecraft shuttle drone",
    "hollow": "hollow building house home room shop castle tower church cabin hut shed box "
    "chest interior diorama station garage",
    "creature": "creature animal character figure sculpture person people bird cat dog fish "
    "owl duck dinosaur dragon robot bust head face statue",
    "plant": "plant flower flowers tree bonsai bouquet succulent cactus pot leaf leaves",
    "machine": "machine frame framed technic crane mechanism gearbox engine arm",
}


@cache
def text() -> str:
    return GUIDE_FILE.read_text(encoding="utf-8")


def _section(heading: str, until: str | None) -> str:
    t = text()
    start = t.find("\n" + heading + "\n")
    if start < 0:
        raise ValueError(f"the guide has no heading '{heading}'")
    start += 1
    end = len(t) if until is None else t.find("\n" + until, start + len(heading))
    if end < 0:
        raise ValueError(f"the guide has no heading '{until}' after '{heading}'")
    return t[start + len(heading) : end].strip("\n")


def words() -> str:
    """Everything before the rules: the title, the note on what it rests on, the words."""
    t = text()
    return t[: t.index("\n" + RULES_HEADING + "\n")].strip()


def _unwrap(block: str) -> list[str]:
    """Numbered items, each joined into one line."""
    items: list[str] = []
    for line in block.splitlines():
        if re.match(r"^\d+\. ", line):
            items.append(line.strip())
        elif line.strip() and items:
            items[-1] += " " + line.strip()
    return items


def rules(evidence: bool = False) -> str:
    items = _unwrap(_section(RULES_HEADING, "## "))
    if not evidence:
        items = [re.sub(r"\s+", " ", _EVIDENCE.sub("", item)).strip() for item in items]
    return "\n".join(items)


@cache
def _playbooks() -> dict[str, dict[int, tuple[str, str]]]:
    block = _section(PLAYBOOKS_HEADING, TABLE_HEADING)
    heads = list(_PLAYBOOK.finditer(block))
    out: dict[str, dict[int, tuple[str, str]]] = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(block)
        title = f"{m.group(1)}, {m.group(2)} parts"
        body = block[m.end() : end].strip()
        kind = m.group(1).split()[0].strip(",").lower()
        out.setdefault(kind, {})[int(m.group(2))] = (title, body)
    return out


def kinds() -> dict[str, str]:
    return {k: KIND_LINES.get(k, "") for k in _playbooks()}


def sizes(kind: str) -> list[int]:
    return sorted(_playbooks()[kind])


def kind_of(word: str) -> str | None:
    w = re.sub(r"[^a-z ]", " ", word.lower()).split()
    books = _playbooks()
    for token in w:
        if token in books:
            return token
        for kind, names in _WORDS.items():
            if kind in books and (token in names.split() or token.rstrip("s") in names.split()):
                return kind
    return None


def refine(kind: str, words: str) -> str:
    """A vehicle whose words say it flies is an aircraft; any other kind stays."""
    if kind == "vehicle" and kind_of(words) == "aircraft":
        return "aircraft"
    return kind


def playbook(kind: str, parts: int) -> tuple[str, str, str]:
    """The playbook of ``kind`` nearest ``parts`` (on a ratio scale), and why it was chosen."""
    books = _playbooks()[kind]
    have = sorted(books)
    best = min(have, key=lambda n: (abs(math.log(max(parts, 1) / n)), n))
    title, body = books[best]
    if parts == best:
        why = f"It is the {kind} playbook for {best} parts."
    elif parts < have[0]:
        why = (
            f"You asked for about {parts:,} parts; the smallest {kind} playbook is for {best}: "
            "keep its core and order, and leave out what there is no room for."
        )
    elif parts > have[-1] * 2:
        why = (
            f"You asked for about {parts:,} parts, far more than the largest {kind} playbook "
            f"({best}): keep its core and order, and repeat or enlarge its units."
        )
    else:
        sizes_ = " and ".join(str(n) for n in have)
        why = (
            f"You asked for about {parts:,} parts; of the {kind} playbooks ({sizes_} parts), "
            f"{best} is the nearer in proportion."
        )
    return title, body, why


def parts_table() -> str:
    return _section(TABLE_HEADING, None).strip()


# ---- the guide-mode instructions --------------------------------------------------------

OLD_STEP_1 = (
    "1. Decide what the subject is and what makes it recognisable at this size: two to four "
    "features (a silhouette, a face, wheels, wings, a colour pattern). If there are reference "
    "pictures, call reference first and study them.\n"
)
NEW_STEP_1 = (
    "1. Decide what the subject is and what makes it recognisable at this size: two to four "
    "features (a silhouette, a face, wheels, wings, a colour pattern). If there are reference "
    "pictures, call reference first and study them. Then call playbook once, with the kind "
    "of subject and about how many parts: it says how set designers build that kind of thing "
    "at that size. Follow it unless the subject needs otherwise.\n"
)

OLD_STEP_4 = (
    "4. Build the structure first: a sturdy core of bricks and plates that holds everything, "
    "with the joints between parts overlapped like a brick wall so that no part hangs on a "
    "single stud by accident. Build from the ground up. Then add the skin: slopes, curved "
    "slopes, wedges and tiles that give the outer shape and cover studs where the surface "
    "should be smooth. Then the details.\n"
)
NEW_STEP_4 = (
    "4. Build in the order the rules below give. First the core the playbook names (a base, "
    "a block of side-stud bricks, a box of walls, a spine), its joints overlapped like a "
    "brick wall so that no part hangs on a single stud by accident, with side studs "
    "(side-stud bricks or brackets) wherever skin will attach. Then the body and skin: each "
    "shaped face built as a panel and pressed on sideways (see Panels), rounded with curved "
    "slopes, smoothed with tiles. Last, what sticks out, moves or is fragile.\n"
)

OLD_STEP_7 = (
    "7. Stop when the check reports no problems and the model looks right, or when the "
    "checks run out. Then write your closing words: what the model is, how many parts, which "
    "special parts you chose and why, and what you would still improve.\n"
)
NEW_STEP_7 = (
    "7. Stop when the check reports no problems and the model looks right, or when the "
    "checks run out. Then write your closing words: what the model is, how many parts, which "
    "special parts you chose and why, which playbook you followed and where you departed "
    "from it, and what you would still improve.\n"
)

OLD_CHECK_TOOL = (
    'Read the warnings and the "not checked" joints too: the checker measures the fit of '
    "studs, pins, axles, bars and wheels, but counts clips, hinges and ball joints as joined "
    "without proof, so make sure each of those is a real joint.\n"
)
NEW_CHECK_TOOL = (
    'Read the warnings and the "not checked" joints too: the checker measures the fit of '
    "studs (sideways ones included), pins, axles, bars and wheels, but not of a clip on a bar, "
    'a ball joint or a hinge (they are listed as "not checked"), so make each of those a real '
    "fit.\n"
)

PANELS = (
    "# Panels\n"
    "\n"
    "A panel is a plate on its side. Place it with one socket on a side stud, choosing the "
    "socket so that the next one in its row lands on a second side stud beside it: held by "
    "two studs, it cannot spin. On a side stud, turn 0 tips the part over the shortest way; "
    "read the box in the reply to see which way its other rows went. The reply lists the "
    "panel's studs, numbered, and which way they point: place tiles and curved slopes on "
    "them as on any plate (on a face, turns 1 and 3 run a part in opposite directions: read "
    "its box). Two studs sideways are five plates, and the side stud of a side-stud brick is "
    "10 LDU below its top, so such a panel's edges fall half a plate off the core's plate "
    "lines; a bracket's side studs (99780) line up with them.\n"
    "\n"
)

OLD_MOVES = "Other movement (doors, a lid, a turning head) only when the person asks for it"
NEW_MOVES = (
    "A wheel module brings its wheel-pin plate and its wheels together, so it goes in first, "
    "with the base on it (the wheels set the scale), not last as the rules say for wheels. A "
    "roof or lid may simply rest on two studs so that it lifts off: no joint. Other movement "
    "(hinged doors, a hinged lid, a turning head) only when the person asks for it"
)

RULES_BEFORE = "# When the subject moves\n"


def _swap(base: str, old: str, new: str) -> str:
    if base.count(old) != 1:
        raise ValueError(f"prompt.md must hold this exactly once for guide mode: {old[:60]!r}")
    return base.replace(old, new)


def system_prompt(base: str, session: str = "first") -> str:
    """The guide-mode instructions made from the standing ones (see the contract);
    ``session`` ("first", "start" or "change") is passed to ``style.system_prompt``."""
    out = base
    for old, new in (
        (OLD_STEP_1, NEW_STEP_1),
        (OLD_STEP_4, NEW_STEP_4),
        (OLD_STEP_7, NEW_STEP_7),
        (OLD_CHECK_TOOL, NEW_CHECK_TOOL),
        (OLD_MOVES, NEW_MOVES),
    ):
        out = _swap(out, old, new)
    added = (
        "# How set designers build (follow these)\n\n" + rules() + "\n\n" + PANELS + RULES_BEFORE
    )
    from bricksnap.lab import style  # the art direction: the brief, finish, the critique

    return style.system_prompt(_swap(out, RULES_BEFORE, added), session)
