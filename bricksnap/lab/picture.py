"""Pictures of models and parts, drawn by LeoCAD without a screen (research prototype).

CONTRACT (tests in tests/test_lab.py; the picture tests skip when LeoCAD is not there)

- LeoCAD is ``~/.cache/bricksnap/leocad/squashfs-root/AppRun`` (or ``$BRICKSNAP_LEOCAD``),
  extracted once from ``LeoCAD.AppImage`` beside it when it is missing. It is run under
  ``xvfb-run -a`` with the library zip (``-l``), ``-i out.png -w W -h H``, a camera placed
  with ``--camera-position-ldraw`` and ``--fov 30``. LeoCAD draws unknown file names as
  boxes, so only lines the checker accepted are drawn.
- ``model_sheet(text, out_png)``: one PNG with three views side by side, each labelled: from
  the front-left above, from the back-right above, and straight from the front. "Front" is
  the -z side (LDraw's convention: a part's front faces -z), up is -y. All three views use
  the same camera distance, so they share one scale.
- ``view(text, out_png, latitude, longitude)``: one view; latitude is degrees above the
  horizon, longitude degrees around: 0 from the front (-z), 90 from the right (+x), 180
  from the back, 270 from the left.
- ``turntable(text, out_dir)``: twelve pictures round the model at one height (25 degrees
  above the horizon), ``turn-00.png`` from the front-left and then 30 degrees further round
  each time, all cut to one common box so the model keeps its place and scale (for the web
  app's turning model). At most ``MAX_LEOCADS`` LeoCAD processes draw at once.
- ``part_sheet(name, out_png)``: one part, from the front-left above and from below, with
  its origin (a red cross, "O") and its studs numbered as ``part_info`` numbers them drawn
  on it; LeoCAD's camera is reproduced (a perspective of 30 degrees vertical field of view)
  to place the marks.
- Every picture is drawn on white. Each call returns the path written, or raises
  ``PictureError`` in plain words.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bricksnap.lab.ldraw_lib import Library, fmt, library

FOV = 30.0
RENDER_PX = 900
PANEL_PX = 560
MAX_LEOCADS = 6
"""At most this many LeoCAD processes draw at once."""
TURN_VIEWS = 12
TURN_LATITUDE = 25.0
TURN_START = -45.0
"""The turntable's first view: from the front-left (longitude -45), like the sheet's first."""


class PictureError(RuntimeError):
    pass


def leocad() -> Path:
    env = os.environ.get("BRICKSNAP_LEOCAD")
    if env:
        return Path(env)
    base = Path.home() / ".cache" / "bricksnap" / "leocad"
    app = base / "squashfs-root" / "AppRun"
    if not app.exists():
        image = base / "LeoCAD.AppImage"
        if not image.exists():
            raise PictureError(f"LeoCAD was not found ({image}).")
        image.chmod(0o755)
        subprocess.run(
            [str(image), "--appimage-extract"],
            cwd=base,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if not app.exists():
            raise PictureError("LeoCAD could not be extracted from its AppImage.")
    return app


def available() -> bool:
    try:
        return leocad().exists() and shutil.which("xvfb-run") is not None
    except PictureError:
        return False


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---- what to draw ---------------------------------------------------------------------------


def drawable(text: str, lib: Library | None = None) -> tuple[str, np.ndarray, np.ndarray]:
    """The model's part lines that name real parts with a usable matrix, and the box (min,
    max) around them in world coordinates."""
    lib = lib or library()
    keep: list[str] = []
    boxes: list[np.ndarray] = []
    for raw in text.splitlines():
        tok = raw.split()
        if len(tok) < 15 or tok[0] != "1":
            if tok and tok[0] == "0":
                keep.append(raw.strip())
            continue
        try:
            nums = [float(v) for v in tok[2:14]]
            int(tok[1], 0)
        except ValueError:
            continue
        name = " ".join(tok[14:])
        found = lib.resolve(name) or lib.resolve(name + ".dat")
        if found is None or found[0] != "part":
            continue
        m = np.array(nums[3:12]).reshape(3, 3)
        if abs(np.linalg.det(m)) < 1e-6:
            continue
        part = lib.part(found[1])
        lo, hi = part.bbox_min.copy(), part.bbox_max.copy()
        if part.studs:
            sp = np.array([s.pos for s in part.studs])
            lo, hi = np.minimum(lo, sp.min(0) - 6), np.maximum(hi, sp.max(0) + 6)
        corners = np.array(
            [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        )
        boxes.append(corners @ m.T + np.array(nums[0:3]))
        keep.append(" ".join(tok[:14] + [found[1]]))
    if not boxes:
        return "\n".join(keep) + "\n", np.zeros(3), np.zeros(3)
    allp = np.concatenate(boxes)
    return "\n".join(keep) + "\n", allp.min(0), allp.max(0)


# ---- the camera -----------------------------------------------------------------------------


def camera(
    lo: np.ndarray, hi: np.ndarray, latitude: float, longitude: float
) -> tuple[np.ndarray, np.ndarray]:
    """Camera position and target for a view of the box from (latitude, longitude)."""
    centre = (lo + hi) / 2
    radius = max(float(np.linalg.norm(hi - lo)) / 2, 10.0)
    dist = radius / math.sin(math.radians(FOV / 2)) * 1.05
    la, lo_ = math.radians(latitude), math.radians(longitude)
    direction = np.array(
        [math.sin(lo_) * math.cos(la), -math.sin(la), -math.cos(lo_) * math.cos(la)]
    )
    return centre + direction * dist, centre


def project(points: np.ndarray, eye: np.ndarray, target: np.ndarray, size: int) -> np.ndarray:
    """Pixel positions of world points in a square picture LeoCAD draws from ``eye``."""
    f = target - eye
    f = f / np.linalg.norm(f)
    up = np.array([0.0, -1.0, 0.0])
    if abs(float(np.dot(f, up))) > 0.999:
        up = np.array([0.0, 0.0, 1.0])
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    rel = np.asarray(points) - eye
    depth = rel @ f
    t = math.tan(math.radians(FOV / 2))
    x = (rel @ r) / depth / t
    y = (rel @ u) / depth / t
    return np.stack([(1 + x) * size / 2, (1 - y) * size / 2], axis=1)


def _up_for(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    f = target - eye
    f = f / np.linalg.norm(f)
    return np.array([0.0, 0.0, 1.0]) if abs(float(f[1])) > 0.999 else np.array([0.0, -1.0, 0.0])


def _leocad(ldr: Path, out: Path, eye: np.ndarray, target: np.ndarray, size: int) -> Image.Image:
    up = _up_for(eye, target)
    cmd = [
        "xvfb-run",
        "-a",
        str(leocad()),
        str(ldr),
        "-l",
        str(library().path),
        "-i",
        str(out),
        "-w",
        str(size),
        "-h",
        str(size),
        "--fov",
        str(FOV),
        "--camera-position-ldraw",
        *[fmt(v) for v in (*eye, *target, *up)],
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise PictureError(f"LeoCAD could not draw the picture ({type(e).__name__}).") from e
    if not out.exists():
        raise PictureError(
            "LeoCAD did not draw the picture: " + (proc.stderr or proc.stdout)[-300:]
        )
    with Image.open(out) as im:
        rgba = im.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, rgba).convert("RGB")


def _render_many(
    text: str, views: list[tuple[float, float]], size: int
) -> tuple[list[Image.Image], list[tuple[np.ndarray, np.ndarray]], np.ndarray, np.ndarray]:
    body, lo, hi = drawable(text)
    with tempfile.TemporaryDirectory(prefix="bricksnap-lab-pic-") as tmp:
        ldr = Path(tmp) / "model.ldr"
        ldr.write_text("0 model\n" + body, encoding="utf-8")
        cams = [camera(lo, hi, la, lon) for la, lon in views]

        def one(i: int) -> Image.Image:
            eye, target = cams[i]
            return _leocad(ldr, Path(tmp) / f"v{i}.png", eye, target, size)

        workers = min(len(views), MAX_LEOCADS)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            images = list(pool.map(one, range(len(views))))
    return images, cams, lo, hi


def _trim_box(img: Image.Image, pad: int = 12) -> tuple[int, int, int, int]:
    arr = np.asarray(img.convert("L"))
    ys, xs = np.nonzero(arr < 250)
    if not len(xs):
        return (0, 0, img.width, img.height)
    return (
        max(int(xs.min()) - pad, 0),
        max(int(ys.min()) - pad, 0),
        min(int(xs.max()) + pad + 1, img.width),
        min(int(ys.max()) + pad + 1, img.height),
    )


def _sheet(panels: list[tuple[str, Image.Image]], title: str = "") -> Image.Image:
    font = _font(20)
    small = _font(16)
    head = 44 if title else 0
    label_h = 34
    w = PANEL_PX * len(panels)
    sheet = Image.new("RGB", (w, head + label_h + PANEL_PX), "white")
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((12, 10), title, fill=(30, 30, 30), font=font)
    for i, (label, img) in enumerate(panels):
        x0 = i * PANEL_PX
        d.text((x0 + 10, head + 6), label, fill=(20, 20, 120), font=small)
        im = img.copy()
        im.thumbnail((PANEL_PX - 10, PANEL_PX - 10))
        sheet.paste(
            im, (x0 + (PANEL_PX - im.width) // 2, head + label_h + (PANEL_PX - im.height) // 2)
        )
        if i:
            d.line([(x0, head), (x0, sheet.height)], fill=(210, 210, 210), width=2)
    return sheet


MODEL_VIEWS = [
    ("1: from the front-left, above", 30.0, -45.0),
    ("2: from the back-right, above", 30.0, 135.0),
    ("3: straight from the front (-z side); +x is to the right", 0.0, 0.0),
]


def model_sheet(text: str, out_png: Path, title: str = "") -> Path:
    images, _, _, _ = _render_many(text, [(la, lon) for _, la, lon in MODEL_VIEWS], RENDER_PX)
    # crop all three to one common box size so they keep the same scale
    boxes = [_trim_box(im) for im in images]
    side = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes)
    panels = []
    for (label, _, _), im, b in zip(MODEL_VIEWS, images, boxes, strict=True):
        cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
        crop = Image.new("RGB", (side, side), "white")
        x0, y0 = cx - side // 2, cy - side // 2
        box = (max(x0, 0), max(y0, 0), min(x0 + side, im.width), min(y0 + side, im.height))
        crop.paste(im.crop(box), (box[0] - x0, box[1] - y0))
        panels.append((label, crop))
    _sheet(panels, title).save(out_png)
    return out_png


def view(text: str, out_png: Path, latitude: float, longitude: float, title: str = "") -> Path:
    images, _, _, _ = _render_many(text, [(latitude, longitude)], RENDER_PX)
    im = images[0]
    label = f"latitude {fmt(latitude)}, longitude {fmt(longitude)} (0 front, 90 right, 180 back)"
    _sheet([(label, im.crop(_trim_box(im)))], title).save(out_png)
    return out_png


def turntable(
    text: str,
    out_dir: Path,
    views: int = TURN_VIEWS,
    latitude: float = TURN_LATITUDE,
    size: int = 720,
    prefix: str = "turn",
) -> list[Path]:
    """``views`` pictures round the model at one height, ``prefix-00.png`` (from the
    front-left) onwards, each a step further round to the right. All are cut to one common
    box, so the model keeps its place and scale from one picture to the next."""
    longitudes = [TURN_START + 360.0 * k / views for k in range(views)]
    images, _, _, _ = _render_many(text, [(latitude, lon) for lon in longitudes], RENDER_PX)
    boxes = [_trim_box(im, pad=16) for im in images]
    box = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, im in enumerate(images):
        frame = im.crop(box)
        frame.thumbnail((size, size))
        path = out_dir / f"{prefix}-{k:02d}.png"
        frame.save(path)
        paths.append(path)
    return paths


def part_sheet(name: str, out_png: Path, lib: Library | None = None) -> Path:
    from bricksnap.lab.validate import numbered_studs

    lib = lib or library()
    found = lib.resolve(name) or lib.resolve(name + ".dat")
    if found is None:
        raise PictureError(f"There is no part {name}.")
    part = lib.part(found[1])
    text = f"1 71 0 0 0 1 0 0 0 1 0 0 0 1 {found[1]}\n"
    views = [(35.0, -40.0), (-40.0, -40.0)]
    images, cams, _, _ = _render_many(text, views, RENDER_PX)
    studs = numbered_studs(part)
    font = _font(22)
    panels = []
    for k, (im, (eye, target)) in enumerate(zip(images, cams, strict=True)):
        d = ImageDraw.Draw(im)
        if studs:
            tips = np.array([s.pos + 4 * s.axis for s in studs])
            px = project(tips, eye, target, RENDER_PX)
            to_eye = eye - tips
            for n, (p, s, te) in enumerate(zip(px, studs, to_eye, strict=True), 1):
                if float(np.dot(s.axis, te)) <= 0 and k == 0:
                    continue  # facing away in this view
                if k == 1 and float(np.dot(s.axis, te)) <= 0:
                    continue
                d.text(
                    (p[0] - 7, p[1] - 14),
                    str(n),
                    fill=(0, 0, 160),
                    font=font,
                    stroke_width=3,
                    stroke_fill="white",
                )
        o = project(np.zeros((1, 3)), eye, target, RENDER_PX)[0]
        d.line([(o[0] - 9, o[1]), (o[0] + 9, o[1])], fill=(220, 0, 0), width=3)
        d.line([(o[0], o[1] - 9), (o[0], o[1] + 9)], fill=(220, 0, 0), width=3)
        d.text(
            (o[0] + 6, o[1] + 2),
            "O",
            fill=(220, 0, 0),
            font=font,
            stroke_width=2,
            stroke_fill="white",
        )
        panels.append(im.crop(_trim_box(im, 30)))
    labels = [
        "from the front-left, above (blue numbers: studs)",
        "from the front-left, below (the underside)",
    ]
    title = f"{found[1]}: {part.description}  (red O: the part's origin)"
    _sheet(list(zip(labels, panels, strict=True)), title).save(out_png)
    return out_png
