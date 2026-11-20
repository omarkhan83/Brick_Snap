"""How a model says what moves: joints written as LDraw comment lines (research prototype).

CONTRACT (tests in tests/test_moving.py)

A model stays plain LDraw text that BrickLink Studio, LeoCAD and LDView open unchanged, so a
joint lives in a comment (meta) line, which those programs skip:

    0 !BRICKSNAP JOINT <name> <kind> [<min> <max>] AT <x> <y> <z> AXIS <dx> <dy> <dz>
      FIXED <line> ... MOVING <line> ... [MODULE <module>]

(all on one line). Words are upper or lower case alike.
- ``name``: one word of letters, digits, ``-`` and ``_`` (at most 40), unique in the model.
- ``kind``: ``SWING`` (turns between two angles: a door, a lid; ``min`` and ``max`` in
  degrees, the position the parts are drawn in being 0, with -360 <= min <= 0 <= max <= 360),
  ``SPIN`` (turns freely all the way round: a turntable) or ``WHEEL`` (turns freely, and
  the model rests on it).
- ``AT`` and ``AXIS``: the line it turns about, in the model's coordinates (LDU, y down): a
  point on it and its direction. A positive angle turns the moving side by the right-hand
  rule about ``AXIS`` (with LDraw's axes); a module's joint is written so that opening is
  positive.
- ``FIXED`` and ``MOVING``: the part lines of the joint itself: the parts that stay (a
  hinge's base, the plate with wheel pins) and the parts that turn (the hinge's top, the
  wheels and tyres). Everything held to the moving parts rides with them; the movement check
  works that out (``movement``).
- ``MODULE``: the module it came from (``modules``), or nothing for a joint the builder
  declared itself.

Line numbers are the lines of the file counting from 1, exactly the numbers every tool and
report uses. They keep their meaning because the tools only append lines and turn removed
lines into comments ("0 removed: ..."), never delete them; a joint line is appended after
the parts it names. A removed joint line ("0 removed: 0 !BRICKSNAP JOINT ...") is no joint.

``parse(text) -> (joints, errors)``: the joints, and for each line that starts like a joint
but cannot be read, ``(line number, what is wrong)`` in plain words. Whether the lines a
joint names are real parts is the movement check's business, not the parser's.
``joint_line(joint) -> str`` writes the line (``parse`` reads it back the same).
``rotation(axis, degrees)`` is the rotation matrix; ``turned(text, joint, degrees, lines)``
is the model with ``lines`` turned about the joint's axis (each changed line keeps its line
number); ``opened(text, angles)`` opens several joints at once: ``{name: degrees}``, each
joint turning what rides on it (``movement.riders``), the joints taken in the order they
are written, so a part that rides on two joints is turned by both; joints that act as one
hinge (``movement`` groups) turn once.
``all_open(text)``: ``{name: degrees}`` opening every joint (each swing to the far end of
its range, each spin or wheel an eighth of a turn), for pictures; empty with no joints.
``shifted(text, dx)`` moves every joint's ``AT`` along x (``edit.centre_x`` moves the parts).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from bricksnap.lab.ldraw_lib import fmt

META = "!BRICKSNAP"
KINDS = ("SWING", "SPIN", "WHEEL")
NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_LINES = 400


@dataclass
class Joint:
    name: str
    kind: str  # "SWING", "SPIN", "WHEEL"
    at: np.ndarray
    axis: np.ndarray  # unit
    fixed: list[int]
    moving: list[int]
    low: float = 0.0  # degrees (SWING only)
    high: float = 0.0
    module: str = ""
    line: int = 0  # the joint's own line in the file (0: not in a file yet)
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def turns_freely(self) -> bool:
        return self.kind in ("SPIN", "WHEEL")

    def words(self) -> str:
        """The joint in a few words: "swings 0 to 90 degrees", "turns freely"."""
        if self.turns_freely:
            return "turns freely all the way round"
        return f"swings from {fmt(self.low)} to {fmt(self.high)} degrees"


def is_joint_line(raw: str) -> bool:
    tok = raw.split()
    return (
        len(tok) >= 2
        and tok[0] == "0"
        and tok[1].upper() == META
        and (len(tok) < 3 or tok[2].upper() == "JOINT")
    )


def _numbers(tok: list[str], i: int, n: int, what: str) -> tuple[list[float], int]:
    vals = []
    for k in range(n):
        if i + k >= len(tok):
            raise ValueError(f"{what} needs {n} numbers")
        try:
            v = float(tok[i + k])
        except ValueError:
            raise ValueError(f"'{tok[i + k][:20]}' after {what} is not a number") from None
        if not math.isfinite(v):
            raise ValueError(f"{what} must be ordinary numbers")
        vals.append(v)
    return vals, i + n


def _line_list(tok: list[str], i: int, what: str) -> tuple[list[int], int]:
    out = []
    while i < len(tok) and tok[i].upper() not in ("FIXED", "MOVING", "MODULE", "AT", "AXIS"):
        try:
            n = int(tok[i])
        except ValueError:
            raise ValueError(f"'{tok[i][:20]}' after {what} is not a line number") from None
        if n < 1:
            raise ValueError(f"line numbers after {what} count from 1")
        out.append(n)
        i += 1
    if not out:
        raise ValueError(f"{what} needs at least one line number")
    if len(out) > MAX_LINES:
        raise ValueError(f"{what} names more than {MAX_LINES} lines")
    return out, i


def parse_line(raw: str, number: int = 0) -> Joint:
    """One joint line; raises ValueError in plain words."""
    tok = raw.split()
    if len(tok) < 4 or tok[2].upper() != "JOINT":
        raise ValueError("a joint line is '0 !BRICKSNAP JOINT <name> <kind> ...'")
    name = tok[3]
    if not NAME.match(name):
        raise ValueError(
            f"the name '{name[:40]}' must be one word of letters, digits, - and _ (at most 40)"
        )
    if len(tok) < 5 or tok[4].upper() not in KINDS:
        raise ValueError("after the name comes the kind: SWING, SPIN or WHEEL")
    kind = tok[4].upper()
    i = 5
    low = high = 0.0
    if kind == "SWING":
        (low, high), i = _numbers(tok, i, 2, "SWING")
        if not -360 <= low <= 0 <= high <= 360 or high - low <= 0:
            raise ValueError(
                "SWING needs two angles, the first from -360 to 0 and the second from 0 to "
                "360, not both 0 (the parts are drawn at angle 0)"
            )
    at = axis = None
    fixed: list[int] = []
    moving: list[int] = []
    module = ""
    while i < len(tok):
        word = tok[i].upper()
        if word == "AT":
            vals, i = _numbers(tok, i + 1, 3, "AT")
            at = np.array(vals)
        elif word == "AXIS":
            vals, i = _numbers(tok, i + 1, 3, "AXIS")
            axis = np.array(vals)
        elif word == "FIXED":
            fixed, i = _line_list(tok, i + 1, "FIXED")
        elif word == "MOVING":
            moving, i = _line_list(tok, i + 1, "MOVING")
        elif word == "MODULE":
            if i + 1 >= len(tok) or not NAME.match(tok[i + 1]):
                raise ValueError("MODULE needs the module's name")
            module = tok[i + 1]
            i += 2
        else:
            raise ValueError(f"'{tok[i][:20]}' is not a word a joint line knows")
    if at is None or axis is None:
        raise ValueError("a joint needs AT x y z and AXIS dx dy dz (the line it turns about)")
    n = float(np.linalg.norm(axis))
    if n < 1e-6:
        raise ValueError("AXIS must not be 0 0 0")
    if not fixed or not moving:
        raise ValueError("a joint needs FIXED lines (what stays) and MOVING lines (what turns)")
    both = sorted(set(fixed) & set(moving))
    if both:
        raise ValueError(f"line {both[0]} cannot be both FIXED and MOVING")
    return Joint(name, kind, at, axis / n, fixed, moving, low, high, module, number)


def parse(text: str) -> tuple[list[Joint], list[tuple[int, str]]]:
    joints: list[Joint] = []
    errors: list[tuple[int, str]] = []
    seen: set[str] = set()
    for n, raw in enumerate(text.splitlines(), 1):
        if not is_joint_line(raw):
            continue
        try:
            j = parse_line(raw, n)
        except ValueError as e:
            errors.append((n, str(e)))
            continue
        if j.name.lower() in seen:
            errors.append(
                (n, f"another joint is already called '{j.name}'; give each its own name")
            )
            continue
        seen.add(j.name.lower())
        joints.append(j)
    return joints, errors


def _n(v: float) -> str:
    return fmt(round(float(v), 3))


def joint_line(j: Joint) -> str:
    parts = ["0", META, "JOINT", j.name, j.kind]
    if j.kind == "SWING":
        parts += [_n(j.low), _n(j.high)]
    parts += ["AT", *(_n(v) for v in j.at), "AXIS", *(_n(v) for v in j.axis)]
    parts += ["FIXED", *map(str, j.fixed), "MOVING", *map(str, j.moving)]
    if j.module:
        parts += ["MODULE", j.module]
    return " ".join(parts)


def rotation(axis: np.ndarray, degrees: float) -> np.ndarray:
    """The rotation by ``degrees`` about unit ``axis`` (right-hand rule, LDraw's axes)."""
    u = np.asarray(axis, dtype=float)
    u = u / np.linalg.norm(u)
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    k = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    r = np.eye(3) * c + s * k + (1 - c) * np.outer(u, u)
    r[np.abs(r) < 1e-12] = 0.0
    return r


def turn_part_line(raw: str, r: np.ndarray, at: np.ndarray) -> str:
    """A type 1 line turned by ``r`` about the point ``at`` (other lines unchanged)."""
    tok = raw.split()
    if len(tok) < 15 or tok[0] != "1":
        return raw
    try:
        nums = [float(v) for v in tok[2:14]]
    except ValueError:
        return raw
    pos = np.array(nums[0:3])
    m = np.array(nums[3:12]).reshape(3, 3)
    new_pos = r @ (pos - at) + at
    new_m = r @ m
    vals = [round(float(v), 3) for v in new_pos] + [round(float(v), 6) for v in new_m.ravel()]
    return " ".join([tok[0], tok[1], *(fmt(v) for v in vals), *tok[14:]])


def turned(text: str, joint: Joint, degrees: float, lines: list[int] | set[int]) -> str:
    r = rotation(joint.axis, degrees)
    out = text.splitlines()
    for n in sorted(set(lines)):
        if 1 <= n <= len(out):
            out[n - 1] = turn_part_line(out[n - 1], r, joint.at)
    return "\n".join(out) + "\n"


def opened(text: str, angles: dict[str, float]) -> str:
    """The model with each named joint turned to its angle, carrying what rides on it. Joints
    that act as one hinge (``movement`` groups: on one line, holding the same parts) turn
    once, by the first of them named."""
    from bricksnap.lab.movement import _sides, plan
    from bricksnap.lab.validate import check

    joints, _ = parse(text)
    want = {k.lower(): float(v) for k, v in angles.items()}
    report = check(text, movement=False)
    _, of = plan(text, report)
    out = text
    done: list[object] = []
    for j in joints:
        g = of.get(j.name.lower())
        if j.name.lower() not in want or g is None or any(g is d for d in done):
            continue
        done.append(g)
        ride = _sides(report, g.fixed, g.moving).riders
        if ride:
            # the joint's own axis moves when an earlier joint carried its parts
            out = turned(out, _carried(out, text, j), want[j.name.lower()], ride)
    return out


def _carried(now: str, before: str, j: Joint) -> Joint:
    """The joint with its axis where its first moving part has been carried to (when an
    earlier opened joint turned that part), so a hinge on an opened door turns about its
    new place."""
    try:
        a = before.splitlines()[j.moving[0] - 1].split()
        b = now.splitlines()[j.moving[0] - 1].split()
        pa, ma = np.array([float(v) for v in a[2:5]]), np.array([float(v) for v in a[5:14]])
        pb, mb = np.array([float(v) for v in b[2:5]]), np.array([float(v) for v in b[5:14]])
    except (IndexError, ValueError):
        return j
    ma, mb = ma.reshape(3, 3), mb.reshape(3, 3)
    if np.allclose(pa, pb) and np.allclose(ma, mb):
        return j
    r = mb @ ma.T
    return Joint(
        j.name,
        j.kind,
        r @ (j.at - pa) + pb,
        r @ j.axis,
        j.fixed,
        j.moving,
        j.low,
        j.high,
        j.module,
        j.line,
    )


def all_open(text: str) -> dict[str, float]:
    return {
        j.name: (45.0 if j.turns_freely else (j.high if j.high > 0 else j.low))
        for j in parse(text)[0]
    }


def shifted(text: str, dx: float) -> str:
    """Every joint's AT moved by ``dx`` along x; other lines unchanged."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        if is_joint_line(raw):
            try:
                j = parse_line(raw, n)
            except ValueError:
                out.append(raw)
                continue
            j.at = j.at + np.array([dx, 0.0, 0.0])
            raw = joint_line(j)
        out.append(raw)
    return "\n".join(out) + "\n"
