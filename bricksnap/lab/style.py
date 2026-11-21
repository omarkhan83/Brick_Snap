"""The style guide, as the AI builder reads it in guide mode (research prototype, EXPERIMENTAL).

CONTRACT (tests in tests/test_art_direction.py)

The style guide comes from the study ``docs/research/2026-11-20-what-makes-a-model-look-styled/``.
Its text lives in two places with the same bytes: the study's ``style-guide.md`` (the record
of the study) and ``bricksnap/lab/style.md`` (what the builder is given at run time). A test
holds them equal: change both in the same commit, so the study always shows what was tested.

The reader finds its parts by their headings, and a test fails when one goes missing:
``## (a) Before you build`` (the eight lines of the art direction, numbered), ``## (b) Rules
of finish`` (thirteen numbered rules), ``## (c) By kind of subject`` (five sections, each
starting with a bold name: Aircraft, Car, Creature or character, Building, Object) and
``## (d) A critique`` (ten numbered questions after a sentence on how to answer them). The
bracketed evidence marks ("[D B]", "[S; writers' opinion]") are left out of everything the
builder is given, as the structural guide's sources are.

- ``brief_lines()``: the eight lines of (a), ``(key, title, what to write)``, in order; the
  keys are ``BRIEF_KEYS``.
- ``rules()``: the thirteen rules of (b), one line each.
- ``subjects()``: ``{name: text}`` for the five sections of (c).
- ``subject_for(kind, words)``: the sections of (c) for a playbook kind ("vehicle",
  "aircraft", "hollow", "creature", "plant", "machine") and the subject's words, with a
  sentence saying which was chosen and why: an aircraft is Aircraft; a vehicle is Aircraft
  or Car by its words (both when the words do not say), a creature is Creature or
  character, a hollow thing is Building (Object for a box or a chest), a machine is Car when
  its words name a car, else Object, and a plant is Object.
- ``questions()``: the ten questions of (d), ``(key, question)``, in order; the keys are
  ``CRITIQUE_KEYS``. ``critique_intro()``: the sentence before them.
- ``system_prompt(text, session)``: the guide-mode instructions (``guide.system_prompt``'s
  result) made into one method: the tool lines on place, add and submit say how to spend
  turns and how to hand in, and name ``brief``; the working order is replaced by one in the
  order things must happen (subject and features, playbook, the parts for the signature
  shapes, the brief, building, checking, handing in with the critique); a section "# Art
  direction" (scale, colours, the hand-in, which part of the guides governs what, and the
  thirteen rules of finish) comes before "# When the subject moves"; the closing section on
  what makes a model look designed is left out (the rules of finish say it), and so are the
  sections for starting from a model and for a change unless the session is one
  (``session``: "first", "start" or "change"). Every place it changes must be found exactly
  once (``ValueError`` otherwise).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

STYLE_FILE = Path(__file__).parent / "style.md"
BRIEF_HEADING = "## (a) Before you build"
RULES_HEADING = "## (b) Rules of finish"
SUBJECTS_HEADING = "## (c) By kind of subject"
CRITIQUE_HEADING = "## (d) A critique"
_EVIDENCE = re.compile(r"\s*\[[^\]]*\]")
_SUBJECT = re.compile(r"^\*\*([^*]+?)\.\*\*", re.M)

BRIEF_KEYS = ("scale", "colours", "pattern", "shapes", "sideways", "thin", "studs", "glass")
CRITIQUE_KEYS = (
    "outline",
    "shapes",
    "studs",
    "flat_sides",
    "colours",
    "divisions",
    "thin",
    "no_technic",
    "glass",
    "stance",
)
SUBJECT_NAMES = ("Aircraft", "Car", "Creature or character", "Building", "Object")

_AIRCRAFT = (
    "plane aeroplane airplane aircraft jet jetliner airliner helicopter glider biplane "
    "seaplane floatplane cessna fighter bomber drone airship spaceship spacecraft shuttle "
    "starfighter rocket"
)
_CAR = (
    "car cars truck lorry van bus coach jeep suv taxi racer racecar roadster coupe "
    "hatchback sedan saloon limousine pickup tractor supercar hypercar buggy kart "
    "motorbike motorcycle bike scooter"
)
_BOX = "box chest crate case cabinet"


@cache
def text() -> str:
    return STYLE_FILE.read_text(encoding="utf-8")


def _section(heading: str) -> str:
    t = text()
    start = t.find("\n" + heading)
    if start < 0:
        raise ValueError(f"the style guide has no heading '{heading}'")
    start = t.index("\n", start + 1)
    end = t.find("\n## ", start)
    return t[start : len(t) if end < 0 else end].strip("\n")


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", _EVIDENCE.sub("", s)).strip()


def _numbered(block: str) -> list[str]:
    items: list[str] = []
    for line in block.splitlines():
        if re.match(r"^\d+\. ", line):
            items.append(line.strip())
        elif line.strip() and items and not line.startswith(("#", "**")):
            items[-1] += " " + line.strip()
    return items


def brief_lines() -> list[tuple[str, str, str]]:
    """The eight lines of the art direction: (key, title, what to write)."""
    out = []
    for key, item in zip(BRIEF_KEYS, _numbered(_section(BRIEF_HEADING)), strict=True):
        m = re.match(r"^\d+\. \*\*(.+?):\*\* (.*)$", _plain(item))
        if not m:
            raise ValueError(f"the style guide's line of the art direction is unreadable: {item}")
        out.append((key, m.group(1), m.group(2)))
    return out


def rules() -> str:
    """The thirteen rules of finish, one line each, without the evidence marks."""
    return "\n".join(_plain(r) for r in _numbered(_section(RULES_HEADING)))


@cache
def subjects() -> dict[str, str]:
    block = _section(SUBJECTS_HEADING)
    heads = list(_SUBJECT.finditer(block))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(block)
        body = block[m.start() : end].strip()
        out[m.group(1)] = "\n".join(_plain(ln) for ln in body.splitlines() if ln.strip())
    return out


def _says(words: str, names: str) -> bool:
    w = re.sub(r"[^a-z ]", " ", words.lower()).split()
    known = names.split()
    return any(t in known or t.rstrip("s") in known for t in w)


def subject_for(kind: str, words: str = "") -> tuple[list[str], str]:
    """The sections of (c) for a playbook kind and the subject's words, and why."""
    if kind == "aircraft":
        return ["Aircraft"], "An aircraft, so: Aircraft."
    if kind == "vehicle":
        if _says(words, _AIRCRAFT):
            return ["Aircraft"], "The subject flies, so: Aircraft."
        if _says(words, _CAR):
            return ["Car"], "The subject is a road vehicle, so: Car."
        return (
            ["Aircraft", "Car"],
            "The words do not say whether it flies or drives, so both: take what fits.",
        )
    if kind == "creature":
        return ["Creature or character"], "A creature or character, so: Creature or character."
    if kind == "hollow":
        if _says(words, _BOX):
            return ["Object"], "A box or chest is an object, so: Object."
        return ["Building"], "A hollow thing with an inside is built like a building, so: Building."
    if kind == "machine" and _says(words, _CAR):
        return ["Car"], "A machine that is a car, so: Car."
    what = "a machine" if kind == "machine" else "a plant"
    return ["Object"], f"The guide has no section for {what}; Object is the nearest."


def critique_intro() -> str:
    block = _section(CRITIQUE_HEADING)
    return _plain(block.split("\n1. ")[0])


def questions() -> list[tuple[str, str]]:
    """The ten questions of the critique: (key, question)."""
    items = [re.sub(r"^\d+\. ", "", _plain(q)) for q in _numbered(_section(CRITIQUE_HEADING))]
    return list(zip(CRITIQUE_KEYS, items, strict=True))


# ---- the guide-mode instructions --------------------------------------------------------

# The tool lines that change in guide mode: how to spend turns (place one at a time, add
# many lines, mirror halves), and what submit and brief do.
OLD_PLACE_LAST = (
    "Use place for every part that connects by studs, including sideways onto side studs.\n"
)
NEW_PLACE_LAST = (
    "Use place for a part whose seat you want worked out (on a turned part, sideways onto "
    "side studs); give it a list of placements to do several in one call.\n"
)
OLD_ADD = (
    "Use it only for what place cannot attach (clips, bars, pins, hinges, and parts you "
    "deliberately position by coordinates).\n"
)
NEW_ADD = (
    "Use it for what place cannot attach (clips, bars, pins, hinges) and for regular runs "
    "whose positions you can work out (a course of plates, a row of tiles), many lines in one "
    "call. Build one half and copy it with mirror.\n"
)
OLD_SUBMIT_TOOL = (
    "- submit replaces the whole model with a file you write and checks it. Use it only when "
    "rewriting everything is easier than fixing it.\n"
)
NEW_SUBMIT_TOOL = (
    "- brief records your art direction before you build (see Art direction), and a change "
    "to it, with your reason.\n"
    "- submit hands in the finished model: with {} it shows the model beside your brief, with "
    "what can be counted and ten questions; with a critique it answers them. With ldraw it "
    "instead replaces the whole model with a file you write and checks it: use that only "
    "when rewriting everything is easier than fixing it.\n"
)

ORDER_START = "Work in this order:\n"
ORDER_END = "\n\n# How set designers build"
ORDER = (
    "Work in this order:\n"
    "1. Decide what the subject is and what makes it recognisable at this size: two to "
    "four features (a silhouette, a face, wheels, wings, a colour pattern). If there are "
    "reference pictures, call reference first and study them.\n"
    "2. Then call playbook once, with the kind of subject and about how many parts: it "
    "says how set designers build that kind of thing at that size, and what makes that "
    "kind of subject look dated and what to do instead.\n"
    "3. Find the parts that make the subject's signature shapes, and the one key part "
    "that sets the scale (a wheel, an eye, a wing, a windscreen), with search_parts and "
    "part_info.\n"
    "4. Write the art direction and give it with brief, before you place a single part "
    "(see Art direction).\n"
    "5. Build to it, in the order the rules below give. First the core the playbook names "
    "(a base, a block of side-stud bricks, a box of walls, a spine), its joints "
    "overlapped like a brick wall so that no part hangs on a single stud by accident, "
    "with side studs (side-stud bricks or brackets) wherever skin will attach. Then the "
    "body and skin: each shaped face built as a panel and pressed on sideways (see "
    "Panels), rounded with curved slopes, smoothed with tiles. Last, what sticks out, "
    "moves or is fragile.\n"
    "6. Check early, once the core stands, and then after every few parts you add. Fix "
    "the problems the report lists before you add more. Look at every picture as the "
    "person who will judge it, and change what looks wrong, not only what the checker "
    "reports.\n"
    "7. Stop when the check reports no problems and the model looks right, or when the "
    "checks run out. Then hand in: submit {} shows the model beside your brief; answer "
    "its ten questions with submit's critique, and rebuild what you answer no to when you "
    "are asked. Then write your closing words: what the model is, how many parts, which "
    "special parts you chose and why, which playbook you followed and where you departed "
    "from it, and what you would still improve."
)

ART_BEFORE = "# When the subject moves\n"

ART = (
    "# Art direction\n"
    "\n"
    "A model that passes every check and still looks like an old set has failed: how it "
    "looks is what it is judged by. What dates a model is not studs; it is flanks of "
    "stacked plates, nothing built sideways, one flat colour or bright red, blue and "
    "yellow on white, thick members where the real thing is thin, and glass that is a "
    "tinted block.\n"
    "\n"
    "Scale: take the largest scale the parts asked for will pay for, never below the "
    "smallest at which the subject's signature shapes can be made from real parts. Name "
    "its width and what it lets you show that the next size down would not, and spend the "
    "parts on shape and finish, not on hidden filling or an interior nobody sees.\n"
    "\n"
    "Colours: three body colours carry the look; the other colours a model has are small "
    "parts for mechanics, glass, lights and an interior.\n"
    "\n"
    "Handing in: the sheet counts what it can on the model (colours, size, parts, glass) "
    'beside your brief; a "yes" those counts contradict is wrong. A "no" means rebuild '
    "that region, not add parts. The check ends with a section HOW IT LOOKS: treat each "
    "line outside its range as something to fix before you answer the critique.\n"
    "\n"
    "What wins: the person's words, then your brief. The style guide (the rules of finish "
    "below, and the section for your subject that playbook hands you) governs shape, "
    "surface and colour; the set designers' rules and playbook govern strength and the "
    "order of building; where they disagree about how the body is made, the style guide "
    "wins.\n"
    "\n"
    "## Rules of finish\n"
    "\n"
    "{rules}\n"
    "\n"
)

DESIGNED = "# What makes a model look designed rather than stacked\n"
FROM_A_MODEL = "# When you start from a model\n"
A_CHANGE = "# When you are asked for a change\n"


def _swap(base: str, old: str, new: str) -> str:
    if base.count(old) != 1:
        raise ValueError(f"the guide-mode prompt must hold this exactly once: {old[:60]!r}")
    return base.replace(old, new)


def _cut(text_: str, heading: str) -> str:
    """Leave out one section, from its heading to the next top-level heading or the end."""
    start = text_.find(heading)
    if start < 0 or text_.count(heading) != 1:
        raise ValueError(f"the guide-mode prompt must hold this exactly once: {heading!r}")
    end = text_.find("\n# ", start + len(heading))
    return text_[:start] + ("" if end < 0 else text_[end + 1 :])


def system_prompt(text_: str, session: str = "first") -> str:
    """The guide-mode instructions with the art direction added (see the contract).
    ``session``: "first" (a new model), "start" (from a model software made) or "change"."""
    out = text_
    for old, new in (
        (OLD_PLACE_LAST, NEW_PLACE_LAST),
        (OLD_ADD, NEW_ADD),
        (OLD_SUBMIT_TOOL, NEW_SUBMIT_TOOL),
    ):
        out = _swap(out, old, new)
    start = out.find(ORDER_START)
    end = out.find(ORDER_END, start)
    if start < 0 or end < 0 or out.count(ORDER_START) != 1:
        raise ValueError("the guide-mode prompt must hold its working order exactly once")
    out = out[:start] + ORDER + out[end:]
    out = _swap(out, ART_BEFORE, ART.replace("{rules}", rules()) + ART_BEFORE)
    out = _cut(out, DESIGNED)  # the rules of finish say it, and say it the same way
    if session != "start":
        out = _cut(out, FROM_A_MODEL)
    if session != "change":
        out = _cut(out, A_CHANGE)
    return out.rstrip("\n") + "\n"
