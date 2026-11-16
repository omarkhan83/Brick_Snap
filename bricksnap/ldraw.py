"""Build to LDraw text (.ldr), the standard file other LEGO tools open.

CONTRACT (tests go in tests/test_ldraw.py)

LDraw facts: units are LDU; one stud pitch is 20 LDU and one plate is 8 LDU tall; LDraw's Y
axis points DOWN; a standard part's origin is the centre of its top face (the top of the
body, underneath the studs).

``placement_to_ldraw(placement, catalog) -> (position, matrix)``
- A grid point (x, y, z) maps to LDraw (20x, -8z, 20y). A part covering w x d x h cells from
  minimum-corner cell (x0, y0, z0), with (w, d, h) from ``catalog.footprint``, must occupy
  the LDraw box  X 20*x0 .. 20*(x0+w),  Y -8*(z0+h) .. -8*z0,  Z 20*y0 .. 20*(y0+d).
- ``matrix`` is the nine numbers a b c d e f g h i of the LDraw line (row-major 3x3). It
  rotates the part about the vertical axis according to ``Placement.rot`` exactly as the
  table in ``bricksnap/catalog/__init__.py`` says (part X along grid +x for 0, grid +y for
  90, and so on), remembering that grid +y is LDraw +Z and grid +x is LDraw +X:
      rot   0: 1 0 0  0 1 0  0 0 1
      rot  90: 0 0 -1  0 1 0  1 0 0
      rot 180: -1 0 0  0 1 0  0 0 -1
      rot 270: 0 0 1  0 1 0  -1 0 0
- ``position`` is chosen so that the part's body box (``Part.body_min`` .. ``Part.body_max``,
  in the part's own LDraw coordinates), after rotation by ``matrix``, has its minimum corner
  at the minimum corner of the LDraw box above. Do NOT assume the origin is the centre of
  the top face: that holds for plain bricks and plates but not for every part (cheese
  slopes have their origin on the bottom face, 45-degree slopes at the centre of their stud
  cell). For a plain part the result equals
      (20 * (x0 + w / 2), -8 * (z0 + h), 20 * (y0 + d / 2)).
  Example: part 3001 (2x4 brick: sx=4, sz=2, h=3) at cell (0, 0, 0): rot 0 gives position
  (40, -24, 20); rot 90 gives position (20, -24, 40).

``to_ldraw(build, catalog, title="BrickSnap model", author="BrickSnap") -> str``
- Header: "0 <title>", "0 Name: <file-safe title>.ldr", "0 Author: <author>", then a line
  crediting the generator. Then one type-1 line per part:
      1 <colour> <x> <y> <z> <a> <b> <c> <d> <e> <f> <g> <h> <i> <ldraw_file>
  Numbers are written without a trailing ".0" when whole, otherwise with at most three
  decimals.
- Parts are ordered by (step, z, y, x). When steps are assigned (any step > 0) a line
  "0 STEP" follows the last part of each step. With no steps assigned there are no STEP
  lines.
- Lines end with "\n" and the text ends with a newline. Title and author are sanitised to
  one line.
- A part id that is not in the catalogue raises ValueError naming it.

Tests should include the two worked examples above, a round trip in which the text is parsed
back and every part's position and matrix match, and that the bounding box of the real part
geometry transformed by (position, matrix) equals the cells the part covers (the test may
hard-code 3001's LDraw bounding box: x -40..40, y -4..24, z -20..20, studs included).

Implementation notes
--------------------
How the position is chosen, axis by axis (identical to the "minimum corner" rule whenever the
body box is exactly as big as the cells, which is true of every tiling part):

- Across (LDraw X and Z): the CENTRE of the rotated body box is put at the centre of the
  cells. When the box's size matches the cells this is the same as matching minimum corners,
  and it is immune to tiny modelling slop (6143 and 14769 are 40.002 LDU wide; matching the
  minimum corner would write positions like 20.001). When the box is clearly bigger or smaller
  than the cells along an axis (a clip or bar sticking out, as on 60897), the box cannot
  describe the cells, so along that axis the part's own origin is assumed to be the middle of
  its footprint, which is LDraw's convention for those parts.
- Up and down (LDraw Y): the BOTTOM of the body (``body_max[1]``, because Y points down) is
  put on the bottom of the cells, -8*z0. A part sits on the studs below it, so its underside
  is what must be exact. This matters for cheese slopes (54200, 85984): LDraw models them
  15.6 LDU tall with a flattened top and the origin on the bottom face, so matching the top
  instead would leave them floating 0.4 LDU above the part they stand on. When the body's
  height is clearly not the part's height (more than the same 0.5 LDU off: something hanging
  below the body, or a hand-built Part left with the dataclass's empty default box), the box
  cannot describe the cells, so the standard origin is assumed: the top of the body on the top
  of the cells, y = -8*(z0+h).

The title line: a title whose first word is an LDraw meta-command (STEP, FILE, NOFILE, BFC,
Name:, ...) or that starts with "!" or "//" would be read as that command, so it is written as
"0 Model: <title>" instead. The Name line is still made from the title itself.
"""

from __future__ import annotations

from bricksnap.catalog import Catalog, Part
from bricksnap.types import LDU_PER_PLATE, LDU_PER_STUD, Build, Placement

GENERATOR_LINE = "0 Generated by BrickSnap (https://www.ldraw.org file format)"

ROTATION_MATRICES: dict[int, tuple[int, ...]] = {
    0: (1, 0, 0, 0, 1, 0, 0, 0, 1),
    90: (0, 0, -1, 0, 1, 0, 1, 0, 0),
    180: (-1, 0, 0, 0, 1, 0, 0, 0, -1),
    270: (0, 0, 1, 0, 1, 0, -1, 0, 0),
}
"""Row-major LDraw matrices for each ``Placement.rot`` (see the catalogue's rotation table)."""

_SIZE_TOLERANCE_LDU = 0.5
"""How far a body box may differ from the cells' size and still be trusted for centring."""

_DEFAULT_TITLE = "BrickSnap model"
_DEFAULT_AUTHOR = "BrickSnap"


def _part(catalog: Catalog, part_id: str) -> Part:
    part = catalog.parts.get(part_id)
    if part is None:
        raise ValueError(
            f"The part '{part_id}' is not in BrickSnap's parts table, "
            "so it cannot be written to the LDraw file."
        )
    return part


def _matrix(rot: int) -> tuple[int, ...]:
    matrix = ROTATION_MATRICES.get(rot % 360)
    if matrix is None:
        raise ValueError(f"A part's rotation must be 0, 90, 180 or 270 degrees, not {rot}.")
    return matrix


def _clean(value: float) -> float:
    """Round to three decimals and turn -0.0 into 0.0."""
    return round(value, 3) + 0.0


def _rotated_box(
    part: Part, matrix: tuple[int, ...]
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Minimum and maximum corners of the part's body box after rotation by ``matrix``."""
    lo, hi = part.body_min, part.body_max
    corners = [
        (cx, cy, cz) for cx in (lo[0], hi[0]) for cy in (lo[1], hi[1]) for cz in (lo[2], hi[2])
    ]
    a, b, c, d, e, f, g, h, i = matrix
    moved = [
        (a * x + b * y + c * z, d * x + e * y + f * z, g * x + h * y + i * z) for x, y, z in corners
    ]
    mins = (min(p[0] for p in moved), min(p[1] for p in moved), min(p[2] for p in moved))
    maxs = (max(p[0] for p in moved), max(p[1] for p in moved), max(p[2] for p in moved))
    return mins, maxs


def _centre_axis(lo: float, hi: float, cell_lo: float, cell_hi: float) -> float:
    """Origin coordinate along one horizontal axis (see the implementation notes)."""
    centre = (cell_lo + cell_hi) / 2
    if abs((hi - lo) - (cell_hi - cell_lo)) <= _SIZE_TOLERANCE_LDU:
        return centre - (lo + hi) / 2
    return centre


def placement_to_ldraw(
    placement: Placement, catalog: Catalog
) -> tuple[tuple[float, float, float], tuple[int, ...]]:
    """LDraw position and row-major rotation matrix for one placed part."""
    part = _part(catalog, placement.part)
    matrix = _matrix(placement.rot)
    w, d, h = catalog.footprint(placement)
    (lx, ly, lz), (hx, hy, hz) = _rotated_box(part, matrix)

    x0 = LDU_PER_STUD * placement.x
    z0 = LDU_PER_STUD * placement.y
    bottom = -LDU_PER_PLATE * placement.z

    px = _centre_axis(lx, hx, x0, x0 + LDU_PER_STUD * w)
    pz = _centre_axis(lz, hz, z0, z0 + LDU_PER_STUD * d)
    if abs((hy - ly) - LDU_PER_PLATE * h) <= _SIZE_TOLERANCE_LDU:
        py = bottom - hy
    else:
        py = bottom - LDU_PER_PLATE * h
    return (_clean(px), _clean(py), _clean(pz)), matrix


def format_number(value: float) -> str:
    """LDraw-style number: no trailing '.0' when whole, otherwise at most three decimals."""
    v = _clean(float(value))
    if v == int(v):
        return str(int(v))
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _one_line(text: str, default: str) -> str:
    """Collapse any whitespace (newlines included) to single spaces; drop control characters."""
    printable = "".join(ch if ch.isprintable() else " " for ch in str(text))
    cleaned = " ".join(printable.split())
    return cleaned or default


# First words that LDraw programs read as commands rather than as a description, when they
# start a "0" line: the official meta-commands, the header lines, and common tool extensions.
_META_WORDS = frozenset(
    {
        "STEP", "ROTSTEP", "FILE", "NOFILE", "WRITE", "PRINT", "CLEAR", "PAUSE", "SAVE", "BFC",
        "NAME:", "AUTHOR:", "MLCAD", "LPUB", "PLIST", "GHOST", "GROUP", "BUFEXCHG", "ROTATION",
        "LDCAD", "SYNTH", "TEXMAP", "LEOCAD",
    }
)  # fmt: skip


def _description(title: str) -> str:
    """The title as a plain description, prefixed with "Model: " if it would read as a command."""
    first = title.split(" ", 1)[0].upper()
    if first in _META_WORDS or title.startswith(("!", "//")):
        return f"Model: {title}"
    return title


def _file_safe(title: str) -> str:
    """A file name stem made from the title: letters, digits, spaces, '-', '_' and '.'."""
    stem = "".join(ch if (ch.isascii() and ch.isalnum()) or ch in " -_." else "_" for ch in title)
    stem = " ".join(stem.split()).strip(" .")
    if stem.lower().endswith(".ldr"):
        stem = stem[:-4].rstrip(" .")
    return stem[:80].rstrip(" .") or "model"


def to_ldraw(
    build: Build, catalog: Catalog, *, title: str = _DEFAULT_TITLE, author: str = _DEFAULT_AUTHOR
) -> str:
    """The whole Build as the text of an LDraw .ldr file."""
    title = _one_line(title, _DEFAULT_TITLE)
    author = _one_line(author, _DEFAULT_AUTHOR)
    lines = [
        f"0 {_description(title)}",
        f"0 Name: {_file_safe(title)}.ldr",
        f"0 Author: {author}",
        GENERATOR_LINE,
    ]

    ordered = sorted(build.parts, key=lambda p: (p.step, p.z, p.y, p.x))
    use_steps = any(p.step > 0 for p in ordered)
    for index, p in enumerate(ordered):
        part = _part(catalog, p.part)
        position, matrix = placement_to_ldraw(p, catalog)
        numbers = " ".join(format_number(v) for v in (*position, *matrix))
        lines.append(f"1 {int(p.color)} {numbers} {part.ldraw_file}")
        last_of_step = index == len(ordered) - 1 or ordered[index + 1].step != p.step
        if use_steps and last_of_step:
            lines.append("0 STEP")
    return "\n".join(lines) + "\n"
