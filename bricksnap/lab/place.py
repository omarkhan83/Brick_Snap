"""Place a part by naming a connection instead of computing coordinates (research prototype).

CONTRACT (tests in tests/test_lab.py)

Numbering (the same everywhere: ``part_info``, the checker's report, here):
- Studs: ``validate.numbered_studs``: those pointing up first, row by row from the front
  (-z) and from left to right (-x to +x); then the others (side studs and studs underneath),
  by the direction they point.
- Sockets (``sockets(part)``): the places under a part where a stud can go in, in the part's
  own frame: every centre of a stud cell (the part's stud grid) where the checker would
  accept a stud pointing up, in the same row order; then every open tube or ring that is not
  already one of those (the tube in the middle of a 2 x 2 brick, the rings of a plant leaf).
  A socket is a point on the part's underside: where the base of the stud goes. Which
  sockets there are, and their numbers, come from ``Part.socket_phase``'s grid; each grid
  socket then sits on the nearest cell of the grid the checker seats studs on
  (``validate.stud_grid``), which differs only for a part with no top studs whose box is
  not whole studs (a curved slope with a cutout): placed with ``place``, such a part passes
  the check. Last, a socket must be one the part's REAL shape takes a stud in: the middle of
  a stud pointing up from it (``solid.stud_core_inside`` within ``SOCKET_CORE_R`` of its
  axis) is not in plastic. The filled body calls the corners of a radar dish's (4740) domed
  underside sockets, and they are not; a rib or wall that only touches a stud's side (most
  undersides grip a stud so) leaves a socket a socket.
  ``sockets(part, real=False)`` leaves that last test out (``Part.has_sockets`` uses it).
  The answer is kept in memory per part; the real test costs one solid per part, built once
  and kept on disk by ``solid`` (0.03 to 0.4 s for ordinary parts).

``place(text, part, colour, line, ...)`` -> ``Placement`` (the finished LDraw line and a
sentence saying what was done), or raises ``PlaceError`` in plain words. ``text`` is the
model so far (line numbers are its lines). Three ways:
- On a stud: ``line`` and ``stud`` k: the new part's socket ``socket`` (default 1) goes onto
  stud k of that line. The new part's "up" is the stud's direction, so a part placed on a
  side stud stands out sideways from it, its underside against the side.
- Under a socket: ``line`` and ``under_socket`` j: the new part's own stud ``own_stud``
  (default 1) goes into socket j of that line, so the new part hangs under it.
- On the ground: ``line`` 0 with ``x`` and ``z``: the part stands on the ground (its lowest
  point at y = 0) with its origin above (x, z).
``turn`` is a number of quarter turns (0 to 3) of the new part about its own vertical axis,
clockwise as seen from its top, counted in the MODEL's frame, not the frame of the part it
attaches to: on a stud pointing up, turn 0 gives the new part the unturned rotation
``1 0 0 0 1 0 0 0 1`` whatever the rotation of the part below; on a side stud, turn 0 is the
new part tipped over the shortest way so that its top faces along the stud. The socket used
turns with the part. The rotation matrix comes out exact (whole numbers for quarter turns and
axis-aligned studs).
When another quarter turn would join more studs between the new part and that line (counted
by the checker's own stud test, both ways), the note ends with one sentence saying so ("Turn 2
would catch 4 side studs; this catches 1."); what is placed does not change.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bricksnap.lab.ldraw_lib import Connector, Library, Part, fmt, library
from bricksnap.lab.validate import (
    _perp,
    _stud_probe,
    numbered_studs,
    stud_grid,
)

QUARTER = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
"""One quarter turn clockwise seen from above (LDraw: y points down)."""


class PlaceError(ValueError):
    pass


@dataclass
class Socket:
    pos: np.ndarray  # where a stud's base goes, in the part's frame
    kind: str  # "grid" or "tube"


@dataclass
class Placement:
    line: str
    note: str
    pos: np.ndarray
    m: np.ndarray


_REAL_SOCKETS: dict[str, list[Socket]] = {}
SOCKET_CORE_R = 2.5  # LDU: a socket is false only when a stud's middle would be in plastic


def sockets(part: Part, real: bool = True) -> list[Socket]:
    """The part's sockets, numbered from 1 in this order (see the contract)."""
    if not real:
        return _sockets(part)
    if part.name not in _REAL_SOCKETS:
        from bricksnap.lab import solid

        up = np.array([0.0, -1.0, 0.0])
        _REAL_SOCKETS[part.name] = [
            s
            for s in _sockets(part)
            if not solid.stud_core_inside(part.name, s.pos, up, radius=SOCKET_CORE_R)
        ]
    return [Socket(s.pos.copy(), s.kind) for s in _REAL_SOCKETS[part.name]]


def _sockets(part: Part) -> list[Socket]:
    out: list[Socket] = []
    if part.has_body():
        px, pz = part.socket_phase()
        lo, hi = part.bbox_min, part.bbox_max
        xs = np.arange(px + 20 * np.floor((lo[0] - px) / 20), hi[0] + 0.01, 20.0)
        zs = np.arange(pz + 20 * np.floor((lo[2] - pz) / 20), hi[2] + 0.01, 20.0)
        up = np.array([0.0, -1.0, 0.0])
        for z in zs:
            for x in xs:
                if not (lo[0] < x < hi[0] and lo[2] < z < hi[2]):
                    continue
                probe_base = np.array([x, 0.0, z])
                bottoms = []
                u, v = _perp(up)
                for p in (
                    probe_base,
                    probe_base + 4 * u,
                    probe_base - 4 * u,
                    probe_base + 4 * v,
                    probe_base - 4 * v,
                ):
                    b = part.bottom_at(float(p[0]), float(p[2]))
                    if b is not None:
                        bottoms.append(b)
                if not bottoms:
                    continue
                base = np.array([x, max(bottoms), z])
                if part.inside(_stud_probe(base, up), tol=0.25).any() and part.is_socket(
                    float(x), float(z), float(base[1])
                ):
                    out.append(Socket(_on_checker_grid(part, base, (px, pz)), "grid"))
    for t in part.tubes:
        if not t.open or t.end is None or t.axis[1] < 0.98:
            continue
        if any(np.linalg.norm(s.pos - t.end) < 2 for s in out):
            continue
        out.append(Socket(t.end.copy(), "tube"))
    return out


def _on_checker_grid(part: Part, base: np.ndarray, phase: tuple[float, float]) -> np.ndarray:
    """A socket found on ``socket_phase``'s grid, moved to the nearest cell of the grid the
    checker seats studs on (``validate.stud_grid``; they differ only for a part with no top
    studs and a cutout or overhang), at the underside there. The sockets keep their numbers."""
    gx, gz = stud_grid(part)
    dx = ((gx - phase[0] + 10) % 20) - 10
    dz = ((gz - phase[1] + 10) % 20) - 10
    if abs(dx) < 1e-9 and abs(dz) < 1e-9:
        return base
    x, z = float(base[0] + dx), float(base[2] + dz)
    u, v = _perp(np.array([0.0, -1.0, 0.0]))
    c = np.array([x, 0.0, z])
    bottoms = [
        b
        for q in (c, c + 4 * u, c - 4 * u, c + 4 * v, c - 4 * v)
        if (b := part.bottom_at(float(q[0]), float(q[2]))) is not None
    ]
    return np.array([x, max(bottoms) if bottoms else float(base[1]), z])


def _rot_between(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """A rotation taking unit vector a to unit vector b (the shortest one; a half turn about
    x when they are opposite)."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    c = float(np.dot(a, b))
    if c > 1 - 1e-9:
        return np.eye(3)
    if c < -1 + 1e-9:
        axis = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 0, 1.0])
        axis = axis - a * float(np.dot(axis, a))
        axis /= np.linalg.norm(axis)
        return 2 * np.outer(axis, axis) - np.eye(3)
    v = np.cross(a, b)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * (1 / (1 + c))


def _clean(m: np.ndarray) -> np.ndarray:
    r = np.round(m, 6)
    r[np.abs(r) < 1e-9] = 0.0
    return r


def ldraw_line(colour: int, pos: np.ndarray, m: np.ndarray, name: str) -> str:
    nums = [*(round(float(v), 3) for v in pos), *(float(v) for v in _clean(m).ravel())]
    return f"1 {colour} " + " ".join(fmt(v) for v in nums) + f" {name}"


def _model_part(text: str, line: int, lib: Library) -> tuple[Part, np.ndarray, np.ndarray, str]:
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        raise PlaceError(f"There is no line {line} in the model (it has {len(lines)} lines).")
    tok = lines[line - 1].split()
    if len(tok) < 15 or tok[0] != "1":
        raise PlaceError(f"Line {line} is not a part line: '{lines[line - 1][:60]}'.")
    try:
        nums = [float(v) for v in tok[2:14]]
    except ValueError:
        raise PlaceError(f"Line {line} has numbers that cannot be read.") from None
    name = " ".join(tok[14:])
    found = lib.resolve(name) or lib.resolve(name + ".dat")
    if found is None or found[0] != "part":
        raise PlaceError(f"Line {line} names '{name}', which is not a part in the library.")
    return lib.part(found[1]), np.array(nums[0:3]), np.array(nums[3:12]).reshape(3, 3), found[1]


def _new_part(name: str, lib: Library) -> tuple[Part, str]:
    found = lib.resolve(name) or lib.resolve(name + ".dat")
    if found is None:
        raise PlaceError(f"There is no part '{name}' in the library; use search_parts.")
    if found[0] != "part":
        raise PlaceError(f"'{name}' is a piece of another part's drawing, not a part.")
    return lib.part(found[1]), found[1]


def _pick(items: list, k: int, what: str, owner: str) -> object:  # type: ignore[type-arg]
    if not items:
        raise PlaceError(f"{owner} has no {what}s.")
    if not 1 <= k <= len(items):
        raise PlaceError(
            f"{owner} has {len(items)} {what}s, numbered 1 to {len(items)}; there is no {what} {k}."
        )
    return items[k - 1]


def place(
    text: str,
    part: str,
    colour: int,
    line: int,
    *,
    stud: int | None = None,
    socket: int = 1,
    under_socket: int | None = None,
    own_stud: int = 1,
    turn: int = 0,
    x: float = 0.0,
    z: float = 0.0,
    lib: Library | None = None,
) -> Placement:
    lib = lib or library()
    new, new_name = _new_part(part, lib)
    if turn not in (0, 1, 2, 3):
        raise PlaceError("turn is a number of quarter turns: 0, 1, 2 or 3.")
    q = np.linalg.matrix_power(QUARTER, turn)
    turned = f", turned {turn} quarter turn{'s' if turn != 1 else ''}" if turn else ""
    if line == 0:
        m = q
        lo, hi = new.bbox_min, new.bbox_max
        corners = np.array(
            [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
        )
        lowest = float((corners @ m.T)[:, 1].max())
        pos = np.array([x, -lowest, z])
        note = (
            f"{new_name} stands on the ground with its origin above x {fmt(x)}, z {fmt(z)}{turned}."
        )
        return Placement(ldraw_line(colour, pos, m, new_name), note, pos, m)
    target, t_pos, t_m, t_name = _model_part(text, line, lib)
    if abs(abs(np.linalg.det(t_m)) - 1) > 0.01:
        raise PlaceError(f"Line {line} does not have a proper rotation matrix; fix it first.")
    owner = f"Line {line} ({t_name} {target.description})"
    if stud is not None and under_socket is not None:
        raise PlaceError(
            "Give either stud (to put the new part on a stud of that line) or under_socket "
            "(to hang it under a socket of that line), not both."
        )
    if stud is not None:
        s = _pick(numbered_studs(target), stud, "stud", owner)
        assert isinstance(s, Connector)
        sock = _pick(sockets(new), socket, "socket", f"{new_name} ({new.description})")
        assert isinstance(sock, Socket)
        base_w = t_m @ s.pos + t_pos
        d_w = t_m @ s.axis
        d_w = d_w / np.linalg.norm(d_w)
        at = sock.pos

        def pose(qq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            mm = _rot_between(np.array([0.0, -1.0, 0.0]), d_w) @ qq
            return mm, base_w - mm @ at

        note = f"{new_name} socket {socket} is on stud {stud} of line {line}{turned}."
    elif under_socket is not None:
        sock = _pick(sockets(target), under_socket, "socket", owner)
        assert isinstance(sock, Socket)
        s = _pick(numbered_studs(new), own_stud, "stud", f"{new_name} ({new.description})")
        assert isinstance(s, Connector)
        d_w = t_m @ np.array([0.0, -1.0, 0.0])
        hole, own, own_axis = t_m @ sock.pos + t_pos, s.pos, s.axis

        def pose(qq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            mm = (
                _rot_between(np.array([0.0, -1.0, 0.0]), d_w)
                @ qq
                @ _rot_between(own_axis, np.array([0.0, -1.0, 0.0]))
            )
            return mm, hole - mm @ own

        note = f"{new_name} stud {own_stud} is in socket {under_socket} of line {line}{turned}."
    else:
        raise PlaceError(
            "Say where: stud (a stud of that line), under_socket (a socket of that line), or "
            "line 0 with x and z for the ground."
        )
    m, pos = pose(q)
    m = _clean(m)
    note += " " + _where(new, pos, m)
    better = _better_turn(
        (t_name, target, t_pos, t_m),
        (new_name, new),
        [(k, *pose(np.linalg.matrix_power(QUARTER, k))) for k in range(4)],
        turn,
        sideways=stud is not None and abs(float(d_w[1])) < 0.99,
    )
    if better:
        note += " " + better
    return Placement(ldraw_line(colour, pos, m, new_name), note, pos, m)


def _caught(target: tuple, new: tuple, pos: np.ndarray, m: np.ndarray) -> int:  # type: ignore[type-arg]
    """How many studs join the new part, placed at ``pos`` with ``m``, and the target (either
    way), by the checker's own stud test."""
    from bricksnap.lab.validate import Placed, _stud_hits

    t_name, t_part, t_pos, t_m = target
    n_name, n_part = new
    m = _clean(m)
    a = Placed(1, 16, t_pos, t_m, t_name, t_name, t_part, 0, np.linalg.inv(t_m))
    b = Placed(2, 16, pos, m, n_name, n_name, n_part, 0, np.linalg.inv(m))
    return sum(h.ok for h in _stud_hits(a, b)) + sum(h.ok for h in _stud_hits(b, a))


def _better_turn(target: tuple, new: tuple, poses: list, turn: int, sideways: bool) -> str:  # type: ignore[type-arg]
    """A sentence when another quarter turn would catch more studs than the one asked for,
    else ""."""
    counts = {k: _caught(target, new, p, mm) for k, mm, p in poses}
    best = max(counts, key=lambda k: (counts[k], -abs(k - turn)))
    if counts[best] <= counts[turn]:
        return ""
    word = "side studs" if sideways else "studs"
    return f"Turn {best} would catch {counts[best]} {word}; this catches {counts[turn]}."


def _where(part: Part, pos: np.ndarray, m: np.ndarray) -> str:
    """Where the placed part is, in words: the box its body spans and which way its own x
    axis points."""
    lo, hi = part.bbox_min, part.bbox_max
    corners = np.array(
        [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
    )
    w = corners @ m.T + pos
    a, b = w.min(0), w.max(0)
    xdir = m @ np.array([1.0, 0, 0])
    names = {
        (1, 0): "+x",
        (-1, 0): "-x",
        (1, 1): "down (+y)",
        (-1, 1): "up (-y)",
        (1, 2): "+z",
        (-1, 2): "-z",
    }
    k = int(np.argmax(np.abs(xdir)))
    xword = names.get((int(np.sign(xdir[k])), k), "a slant") if abs(xdir[k]) > 0.99 else "a slant"
    return (
        f"Its body now spans x {fmt(round(a[0], 1))}..{fmt(round(b[0], 1))}, y "
        f"{fmt(round(a[1], 1))}..{fmt(round(b[1], 1))}, z "
        f"{fmt(round(a[2], 1))}..{fmt(round(b[2], 1))}; "
        f"its own x axis points along {xword}."
    )
