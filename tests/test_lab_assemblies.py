"""The LDraw library's own assembled parts (its "shortcuts": a wheel with its tyre, a turntable,
a hinge, a torso with arms on pins) as a standing guard on the free-build checker's joints.

Each shortcut lists 2 to 6 real parts in the places the library puts them, so each is a
model whose joints are right by definition. ``library_assemblies.json`` names those whose
check on 2026-11-20 (before the joint rules were tightened) listed a joint the checker names
(a tyre on a wheel, a wheel pin, a turntable, a hinge, a clip or bar, a ball, a Technic pin
or axle), with whether that check found no problem. The test holds that none of them makes
the check raise, and that none that had no problem gains one. The models are read from the
library at test time: no library geometry is kept in the repository.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from bricksnap.lab import ldraw_lib

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(),
    reason=f"the lab's tests read the LDraw parts library, which is not on this machine "
    f"({ldraw_lib.zip_path()}); the rest of BrickSnap does not need it",
)

EXPECTED = Path(__file__).parent / "library_assemblies.json"
STAND_IN = ["4", "1", "2", "14", "5", "3"]  # colours for colour 16/24, which a model may not use


def assembly(lib: ldraw_lib.Library, key: str) -> str:
    """The shortcut ``key`` as a model: its part lines, lifted so that it stands on y = 0."""
    rows = []
    for line in lib.text("part", key).splitlines():
        t = line.split()
        if len(t) >= 15 and t[0] == "1":
            got = lib.resolve(" ".join(t[14:]))
            assert got is not None and got[0] == "part", line
            rows.append((t[1], [float(v) for v in t[2:14]], got[1]))
    low = -1e9
    for _, nums, sub in rows:
        p = lib.part(sub)
        m, pos = np.array(nums[3:12]).reshape(3, 3), np.array(nums[0:3])
        lo, hi = p.bbox_min, p.bbox_max
        c = np.array(
            [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        )
        low = max(low, float((c @ m.T + pos)[:, 1].max()))
    out = []
    for k, (colour, nums, sub) in enumerate(rows):
        nums = list(nums)
        nums[1] -= low
        colour = STAND_IN[k % 6] if colour in ("16", "24") else colour
        out.append("1 " + colour + " " + " ".join(f"{v:.6g}" for v in nums) + " " + sub)
    return "\n".join(out) + "\n"


def test_the_librarys_assemblies_keep_their_joints():
    from bricksnap.lab.validate import check

    lib = ldraw_lib.library()
    expected = json.loads(EXPECTED.read_text())
    assert len(expected) > 150
    gained, raised = [], []
    for key, had_no_problem in expected.items():
        if not re.fullmatch(r"[\w.-]+\.dat", key) or lib.resolve(key) is None:
            continue  # an older or newer library without this shortcut
        try:
            report = check(assembly(lib, key))
        except Exception as e:  # noqa: BLE001 - every failure is collected and shown
            raised.append(f"{key}: {type(e).__name__}: {e}")
            continue
        if had_no_problem and report.problems:
            gained.append(f"{key}: {report.problems[0].text[:200]}")
    assert not raised, "\n".join(raised)
    assert not gained, "\n".join(gained)
