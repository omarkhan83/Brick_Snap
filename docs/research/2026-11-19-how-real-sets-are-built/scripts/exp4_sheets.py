"""Experiment 4: one fair comparison sheet of two versions of a model.

    uv run python exp4_sheets.py A.ldr B.ldr OUT.png [VIEWS_DIR]

Draws both models with LeoCAD (``bricksnap.lab.picture``) from the same three cameras: the
face straight on (from the front, -z), three-quarter from the front-left above (30 degrees up,
45 degrees round), and the left side. Each camera is placed from ONE box round both models
together, so the two are drawn from exactly the same place at exactly the same scale; each
view of A and B is then cut to one common frame. The sheet has A on the left and B on the
right, one row per view, on white, each picture labelled only "A" or "B" in small letters.
With VIEWS_DIR, each single picture is also saved there.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from bricksnap.lab import picture

VIEWS = [("front", 0.0, 0.0), ("three-quarter", 30.0, -45.0), ("side", 0.0, 270.0)]
CELL = 620


def render(text: str, lo: np.ndarray, hi: np.ndarray, tmp: Path, tag: str) -> list[Image.Image]:
    body, _, _ = picture.drawable(text)
    ldr = tmp / f"{tag}.ldr"
    ldr.write_text("0 model\n" + body, encoding="utf-8")
    out = []
    for i, (_, la, lon) in enumerate(VIEWS):
        eye, target = picture.camera(lo, hi, la, lon)
        out.append(picture._leocad(ldr, tmp / f"{tag}-{i}.png", eye, target, picture.RENDER_PX))
    return out


def main() -> None:
    a_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    b_text = Path(sys.argv[2]).read_text(encoding="utf-8")
    out = Path(sys.argv[3])
    views_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    _, alo, ahi = picture.drawable(a_text)
    _, blo, bhi = picture.drawable(b_text)
    lo, hi = np.minimum(alo, blo), np.maximum(ahi, bhi)
    with tempfile.TemporaryDirectory(prefix="exp4-") as tmp:
        a_imgs = render(a_text, lo, hi, Path(tmp), "a")
        b_imgs = render(b_text, lo, hi, Path(tmp), "b")
    # one crop square per view, shared by A and B, and one size for every view
    crops = []
    for a, b in zip(a_imgs, b_imgs, strict=True):
        ba, bb = picture._trim_box(a, pad=20), picture._trim_box(b, pad=20)
        crops.append((min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3])))
    side = max(max(c[2] - c[0], c[3] - c[1]) for c in crops)
    font = picture._font(15)
    label_h = 22
    sheet = Image.new("RGB", (2 * CELL, len(VIEWS) * (CELL + label_h)), "white")
    d = ImageDraw.Draw(sheet)
    for row, (c, a, b) in enumerate(zip(crops, a_imgs, b_imgs, strict=True)):
        cx, cy = (c[0] + c[2]) // 2, (c[1] + c[3]) // 2
        x0, y0 = cx - side // 2, cy - side // 2
        for col, (name, img) in enumerate((("A", a), ("B", b))):
            square = Image.new("RGB", (side, side), "white")
            box = (max(x0, 0), max(y0, 0), min(x0 + side, img.width), min(y0 + side, img.height))
            square.paste(img.crop(box), (box[0] - x0, box[1] - y0))
            square = square.resize((CELL, CELL), Image.Resampling.LANCZOS)
            top = row * (CELL + label_h)
            d.text((col * CELL + 8, top + 3), name, fill=(90, 90, 90), font=font)
            sheet.paste(square, (col * CELL, top + label_h))
            if views_dir is not None:
                views_dir.mkdir(parents=True, exist_ok=True)
                square.save(views_dir / f"{name}-{VIEWS[row][0]}.png")
        if row:
            d.line(
                [(0, row * (CELL + label_h)), (2 * CELL, row * (CELL + label_h))],
                fill=(225, 225, 225),
            )
    d.line([(CELL, 0), (CELL, sheet.height)], fill=(225, 225, 225), width=2)
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
