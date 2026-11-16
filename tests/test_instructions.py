"""Tests for bricksnap.instructions: the instruction booklet (HTML and PDF)."""

from __future__ import annotations

import base64
import html
import io
import json
import re
import struct
import time
import zlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

from bricksnap import instructions as I
from bricksnap import render as R
from bricksnap.checks import check
from bricksnap.export import parts_list
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Placement

RED, BLUE, YELLOW, GREY = 4, 1, 14, 72


# ---- helpers -------------------------------------------------------------------------------


def make_project(tmp_path: Path, build: Build | None, catalog, name: str = "test model") -> Project:
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "project.json").write_text(json.dumps({"name": name, "seed": "seed.stl"}))
    project = Project(folder)
    if build is not None:
        build.report = check(build, catalog)
        project.save_build(build)
    return project


def base_4x4(colour: int = GREY) -> list[Placement]:
    """Two layers of 2x4 bricks crossing each other: a solid 4 x 4 block, 6 plates tall."""
    return [
        Placement("3001", colour, 0, 0, 0, 0, 1),
        Placement("3001", colour, 0, 2, 0, 0, 1),
        Placement("3001", colour, 0, 0, 3, 90, 1),
        Placement("3001", colour, 2, 0, 3, 90, 1),
    ]


def small_tower() -> Build:
    parts = base_4x4()
    parts += [
        Placement("3003", RED, 0, 0, 6, 0, 2),
        Placement("3003", RED, 2, 2, 6, 0, 2),
        Placement("3020", BLUE, 0, 0, 9, 90, 3),
        Placement("3024", YELLOW, 3, 3, 9, 0, 3),
    ]
    return Build((4, 4, 10), parts)


def hidden_in_the_middle() -> Build:
    """Step 2 is a layer of plates with a 1x1 plate in the middle, capped in the same step."""
    parts = base_4x4()
    parts += [
        Placement("3024", YELLOW, 1, 1, 6, 0, 2),  # index 4: the hidden one
        Placement("3710", GREY, 0, 0, 6, 0, 2),
        Placement("3710", GREY, 0, 3, 6, 0, 2),
        Placement("3023b", GREY, 0, 1, 6, 90, 2),
        Placement("3023b", GREY, 3, 1, 6, 90, 2),
        Placement("3024", GREY, 2, 1, 6, 0, 2),
        Placement("3023b", GREY, 1, 2, 6, 0, 2),
        Placement("3022", RED, 1, 1, 7, 0, 2),  # the cap
    ]
    return Build((4, 4, 8), parts)


def corner_behind_walls() -> Build:
    """Step 2 is a tall wall with a column behind it (the column only shows from the back);
    step 3 is one brick in the back left corner, behind both."""
    parts = base_4x4()
    for z in (6, 9, 12):
        parts.append(Placement("3010", RED, 0, 2, z, 0, 2))  # a wall along x, in front of it
        parts.append(Placement("3005", RED, 1, 3, z, 0, 2))  # a column to its right
    parts.append(Placement("3005", BLUE, 0, 3, 6, 0, 3))  # index 10: the corner brick
    return Build((4, 4, 15), parts)


def hidden_on_the_back_page() -> Build:
    """6 x 4 base; step 2 a tall wall along the front; step 3 a layer behind the wall, seen
    only from the back, with three plates at the model's own left (x 0 to 1) under a cap.
    Those three are hidden in both views (indices 10, 11, 12)."""
    parts = [Placement("3009", GREY, 0, y, 0, 0, 1) for y in range(4)]
    parts += [Placement("3001", GREY, x, 0, 3, 90, 1) for x in (0, 2, 4)]
    parts += [Placement("3009", RED, 0, 0, z, 0, 2) for z in (6, 9, 12)]
    parts += [
        Placement("3024", YELLOW, 0, 2, 6, 0, 3),
        Placement("3024", YELLOW, 1, 2, 6, 0, 3),
        Placement("3023b", YELLOW, 0, 1, 6, 0, 3),
        Placement("3666", BLUE, 0, 3, 6, 0, 3),
        Placement("3020", BLUE, 2, 1, 6, 0, 3),
        Placement("3022", GREY, 0, 1, 7, 0, 3),
    ]
    return Build((6, 4, 15), parts)


def split_between_sides() -> Build:
    """A tall wall across the middle; step 2 puts one brick in front of it (seen only from
    the front, index 8) and one behind it (seen only from the back, index 9)."""
    parts = base_4x4()
    parts += [Placement("3010", RED, 0, 2, z, 0, 1) for z in (6, 9, 12, 15)]
    parts += [Placement("3005", BLUE, 1, 0, 6, 0, 2), Placement("3005", YELLOW, 2, 3, 6, 0, 2)]
    return Build((4, 4, 18), parts)


def hidden_on_a_new_part() -> Build:
    """Step 2: a red 2x4 brick (index 5) with a yellow 1x1 plate (index 6) on it, closed in
    by plates and capped, all in the same step: the plate stands only on the new brick."""
    parts = base_4x4()
    parts.append(Placement("3001", GREY, 0, 2, 6, 0, 1))  # the back half, 3 plates up
    parts += [
        Placement("3001", RED, 0, 0, 6, 0, 2),
        Placement("3024", YELLOW, 1, 1, 9, 0, 2),
        Placement("3710", RED, 0, 0, 9, 0, 2),
        Placement("3024", RED, 0, 1, 9, 0, 2),
        Placement("3024", RED, 2, 1, 9, 0, 2),
        Placement("3024", RED, 3, 1, 9, 0, 2),
        Placement("3710", GREY, 0, 2, 9, 0, 2),
        Placement("3020", BLUE, 0, 0, 10, 0, 2),
    ]
    return Build((4, 4, 11), parts)


def sections(html_text: str, cls: str) -> list[str]:
    """The text of every <section class="page CLS"> in order."""
    parts = re.split(r'(?=<section class="page )', html_text)
    return [p for p in parts if p.startswith(f'<section class="page {cls}"')]


def pictures(section: str, cls: str) -> list[Image.Image]:
    """The pictures of one class in a piece of the HTML, decoded."""
    srcs = re.findall(rf'<img class="{cls}"[^>]*src="data:image/png;base64,([^"]+)"', section)
    return [Image.open(io.BytesIO(base64.b64decode(s))).convert("RGB") for s in srcs]


def scale_of(shape, view: str, size: tuple[int, int]) -> int:
    """The pixels a stud at which ``view`` of a grid of ``shape`` is ``size`` (no labels)."""
    for s in range(3, 129):
        f = R.view_frame(shape, view, px_per_stud=s, labels=False)
        if (f.width, f.height) == size:
            return s
    raise AssertionError(f"no scale draws {view} of {shape} at {size}")


def same_drawing(picture: Image.Image, expected: Image.Image, owner: np.ndarray) -> float:
    """Mean colour difference over the inside of the parts (away from outlines and the
    yellow line), where the booklet draws exactly what the renderer draws."""
    inside = ndimage.binary_erosion(owner >= 0, iterations=1)
    edges = np.zeros(owner.shape, dtype=bool)
    edges[:, 1:] |= owner[:, 1:] != owner[:, :-1]
    edges[1:, :] |= owner[1:, :] != owner[:-1, :]
    inside &= ~ndimage.binary_dilation(edges, iterations=4)
    a = np.asarray(picture, dtype=np.int64)[inside]
    b = np.asarray(expected, dtype=np.int64)[inside]
    assert len(a) > 200
    return float(np.abs(a - b).mean())


def near_halo(im: Image.Image) -> np.ndarray:
    a = np.asarray(im, dtype=np.int64)
    return (np.abs(a - np.asarray(I.HALO)) <= 12).all(axis=2)


def pdf_pages(pdf: bytes) -> list[Image.Image]:
    """The page pictures stored in one of our PDFs, decoded (each is PNG image data)."""
    out = []
    pattern = rb"/Width (\d+) /Height (\d+) .*?/Length (\d+) >>\nstream\n"
    for m in re.finditer(pattern, pdf):
        w, h, n = (int(g) for g in m.groups())
        data = pdf[m.end() : m.end() + n]

        def chunk(kind: bytes, body: bytes) -> bytes:
            return (
                struct.pack(">I", len(body))
                + kind
                + body
                + struct.pack(">I", zlib.crc32(kind + body))
            )

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", data)
            + chunk(b"IEND", b"")
        )
        out.append(Image.open(io.BytesIO(png)).convert("RGB"))
    return out


# ---- files and errors ----------------------------------------------------------------------


def test_writes_html_and_pdf_into_the_project(tmp_path, catalog):
    project = make_project(tmp_path, small_tower(), catalog)
    out = I.make_instructions(project, catalog)
    assert out == {
        "html": project.path / "instructions.html",
        "pdf": project.path / "instructions.pdf",
    }
    assert out["html"].stat().st_size > 1000 and out["pdf"].stat().st_size > 1000
    leftovers = [p.name for p in project.path.iterdir() if "tmp" in p.name]
    assert leftovers == []


def test_catalogue_defaults_to_the_shipped_one(tmp_path, catalog):
    project = make_project(tmp_path, small_tower(), catalog)
    out = I.make_instructions(project)
    assert out["html"].exists()


def test_no_build_is_a_plain_error(tmp_path, catalog):
    project = make_project(tmp_path, None, catalog)
    with pytest.raises(ProjectError, match="built"):
        I.make_instructions(project, catalog)
    assert not (project.path / "instructions.html").exists()


def test_unreadable_build_is_a_plain_error(tmp_path, catalog):
    project = make_project(tmp_path, None, catalog)
    project.build_path.write_text("{ not json")
    with pytest.raises(ProjectError, match="build"):
        I.make_instructions(project, catalog)


def test_a_build_that_fails_its_checks_is_refused(tmp_path, catalog):
    b = small_tower()
    b.parts.append(Placement("3005", RED, 3, 0, 12, 0, 4))  # floating in the air
    b.shape = (4, 4, 15)
    project = make_project(tmp_path, b, catalog)
    with pytest.raises(ProjectError, match="check report"):
        I.make_instructions(project, catalog)
    assert not (project.path / "instructions.html").exists()
    assert not (project.path / "instructions.pdf").exists()


def test_the_checks_are_run_again_not_trusted(tmp_path, catalog):
    b = small_tower()
    b.parts.append(Placement("3005", RED, 3, 0, 12, 0, 4))
    b.shape = (4, 4, 15)
    project = make_project(tmp_path, small_tower(), catalog)
    b.report = check(small_tower(), catalog)  # a stale report that says all is well
    project.save_build(b)
    with pytest.raises(ProjectError, match="check report"):
        I.make_instructions(project, catalog)


# ---- the HTML booklet ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def tower_booklet(tmp_path_factory, catalog):
    tmp = tmp_path_factory.mktemp("tower")
    project = make_project(tmp, small_tower(), catalog, name='Tom\'s <b>"tower"</b> & co')
    out = I.make_instructions(project, catalog)
    return project, out["html"].read_text(encoding="utf-8"), out["pdf"].read_bytes()


def test_html_is_one_self_contained_page(tower_booklet):
    _, text, _ = tower_booklet
    lower = text.lower()
    assert lower.startswith("<!doctype html>")
    assert "<script" not in lower and "javascript:" not in lower
    assert "http://" not in lower and "https://" not in lower
    assert "<link" not in lower and "@import" not in lower and "url(" not in lower
    srcs = re.findall(r'src="([^"]*)"', text)
    assert srcs and all(s.startswith("data:image/png;base64,") for s in srcs)
    assert "break-after: page" in text or "page-break-after: always" in text


def test_html_escapes_all_text(tower_booklet):
    _, text, _ = tower_booklet
    assert "<b>" not in text
    assert "Tom&#x27;s &lt;b&gt;&quot;tower&quot;&lt;/b&gt; &amp; co" in text


def test_cover_has_name_picture_counts_and_the_trademark_line(tower_booklet):
    _, text, _ = tower_booklet
    cover = sections(text, "cover")
    assert len(cover) == 1
    c = cover[0]
    assert "&lt;b&gt;&quot;tower&quot;" in c
    assert "8 parts" in c and "3 steps" in c
    assert c.count("<img") == 1
    assert I.DISCLAIMER in text.replace("&#x27;", "'")
    assert I.DISCLAIMER == (
        "LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or "
        "endorse this project."
    )


def test_cover_picture_is_the_finished_model(tower_booklet, catalog):
    _, text, _ = tower_booklet
    (hero,) = pictures(sections(text, "cover")[0], "hero")
    b = small_tower()  # already in its smallest grid
    s = scale_of(b.shape, "iso", hero.size)
    expected, owner = R.render_build_map(b, catalog, "iso", px_per_stud=s, labels=False)
    assert same_drawing(hero, expected, owner) < 3
    assert (owner >= 0).sum() > 0.2 * owner.size


def test_parts_pages_list_every_part_like_the_parts_list(tower_booklet, catalog):
    _, text, _ = tower_booklet
    pages = sections(text, "parts")
    assert pages
    found = re.findall(
        r'<li class="part" data-part="([^"]+)" data-colour="(-?\d+)" data-quantity="(\d+)">',
        "".join(pages),
    )
    expected = [
        (ln.part, str(ln.colour), str(ln.quantity)) for ln in parts_list(small_tower(), catalog)
    ]
    assert found == expected
    joined = "".join(pages)
    for ln in parts_list(small_tower(), catalog):
        assert ln.name in joined and ln.colour_name in joined
    assert joined.count('<img class="part"') == len(expected)


def test_one_section_per_step_in_order_with_its_parts(tower_booklet, catalog):
    _, text, _ = tower_booklet
    steps = sections(text, "step")
    assert len(steps) == 3
    b = small_tower()
    for k, sec in enumerate(steps, start=1):
        assert f'<span class="num">{k}</span>' in sec
        assert "of 3" in sec
        found = re.findall(
            r'<li class="add" data-part="([^"]+)" data-colour="(-?\d+)" data-quantity="(\d+)">',
            sec,
        )
        lines = parts_list(Build(b.shape, [p for p in b.parts if p.step == k]), catalog)
        assert found == [(ln.part, str(ln.colour), str(ln.quantity)) for ln in lines]
        assert sec.count('<img class="part"') == len(lines)
        assert sec.count('<img class="model"') == 1


def test_each_step_picture_shows_that_step_new_and_the_rest_pale(tower_booklet, catalog):
    """The picture is the model after the step in the planned view: this step's parts in
    full colour with a yellow line round them, earlier ones pale, later ones not there."""
    _, text, _ = tower_booklet
    b = small_tower()  # already in its smallest grid
    plans = I.plan_steps(b, catalog)
    for plan, sec in zip(plans, sections(text, "step"), strict=True):
        (pic,) = pictures(sec, "model")
        s = scale_of(b.shape, plan.view, pic.size)
        expected, owner = R.render_build_map(
            b,
            catalog,
            plan.view,
            px_per_stud=s,
            labels=False,
            upto_step=plan.step,
            highlight_step=plan.step,
        )
        assert same_drawing(pic, expected, owner) < 3, plan.number
        # the same picture without the earlier parts pale is clearly different (step 1 has
        # no earlier parts)
        plain = R.render_build(b, catalog, plan.view, px_per_stud=s, labels=False)
        if plan.number > 1:
            assert same_drawing(pic, plain, owner) > 6, plan.number
        new = np.isin(owner, plan.parts)
        halo = near_halo(pic)
        assert halo.sum() > 50
        line = max(2, round(s / 9))  # the yellow line's width at this scale
        assert not (halo & ~ndimage.binary_dilation(new, iterations=line + 2)).any()


def test_the_model_is_the_same_size_on_every_step_page(tower_booklet):
    _, text, _ = tower_booklet
    sizes = re.findall(r'<img class="model" width="(\d+)" height="(\d+)"', text)
    assert len(sizes) == 3 and len(set(sizes)) == 1


def test_last_page_shows_the_model_from_four_sides(tower_booklet):
    _, text, _ = tower_booklet
    last = sections(text, "finished")
    assert len(last) == 1
    assert last[0].count("<img") == 4
    for words in ("front", "back", "left", "right"):
        assert words in last[0].lower()
    assert text.rstrip().endswith("</html>")
    assert text.index('class="page finished"') > text.rindex('class="page step"')


def test_last_page_pictures_are_the_four_sides(tower_booklet, catalog):
    _, text, _ = tower_booklet
    last = sections(text, "finished")[0]
    captions = re.findall(r"<figcaption>([^<]*)</figcaption>", last)
    assert captions == [caption for _, caption in I.FOUR_SIDES]
    pics = pictures(last, "side")
    b = small_tower()
    for (view, _), pic in zip(I.FOUR_SIDES, pics, strict=True):
        s = scale_of(b.shape, view, pic.size)
        expected, owner = R.render_build_map(b, catalog, view, px_per_stud=s, labels=False)
        assert same_drawing(pic, expected, owner) < 3, view
    arrays = [np.asarray(p, dtype=np.int64) for p in pics]
    for i in range(4):
        for j in range(i + 1, 4):
            same_size = arrays[i].shape == arrays[j].shape
            assert not same_size or np.abs(arrays[i] - arrays[j]).mean() > 3


# ---- choosing the view, and hidden parts ---------------------------------------------------


def test_plan_has_one_entry_per_step(catalog):
    plan = I.plan_steps(small_tower(), catalog)
    assert [s.number for s in plan] == [1, 2, 3]
    assert [s.step for s in plan] == [1, 2, 3]
    assert plan[0].parts == [0, 1, 2, 3]
    assert all(s.view in ("iso", "iso_back") for s in plan)
    assert plan[0].turn is False
    assert plan[0].hidden == [] and plan[0].words == []


def test_view_turns_when_the_new_part_only_shows_from_the_back(tmp_path, catalog):
    b = corner_behind_walls()
    assert check(b, catalog).ok
    plan = I.plan_steps(b, catalog)
    # step 2: the column behind the wall shows only from the back, so the model turns;
    # step 3: the corner brick shows only from the back too, so it stays turned
    assert [s.view for s in plan] == ["iso", "iso_back", "iso_back"]
    assert [s.turn for s in plan] == [False, True, False]
    assert plan[1].hidden == [] and plan[2].hidden == []
    project = make_project(tmp_path, b, catalog)
    text = I.make_instructions(project, catalog)["html"].read_text(encoding="utf-8")
    steps = sections(text, "step")
    assert [I.TURN_TEXT in s for s in steps] == [False, True, False]


def test_a_hidden_part_is_described_in_words(tmp_path, catalog):
    b = hidden_in_the_middle()
    assert check(b, catalog).ok
    plan = I.plan_steps(b, catalog)
    # the cap covers the four middle cells: the yellow plate and two grey ones under it
    assert plan[1].hidden == [4, 9, 10]
    assert len(plan[1].words) == 3
    sentence = plan[1].words[0]
    assert "plate 1 x 1" in sentence.lower() and "yellow" in sentence.lower()
    assert "in the middle" in sentence
    assert "under the" in sentence and "plate 2 x 2" in sentence.lower()
    assert "first" in sentence
    assert "step 1" in sentence  # it stands on a brick from step 1
    project = make_project(tmp_path, b, catalog)
    text = I.make_instructions(project, catalog)["html"].read_text(encoding="utf-8")
    step2 = sections(text, "step")[1]
    assert html.escape(sentence) in step2
    # and a small picture of the step with only the hidden part put in
    assert step2.count('<img class="first"') == 1


def test_where_words_name_the_side(catalog):
    b = corner_behind_walls()
    # the corner brick: back left, standing on the base from step 1
    words = I.where_words(b, catalog, 10)
    assert "at the back left" in words
    assert "step 1" in words
    words = I.where_words(b, catalog, 0)  # a brick of the bottom layer, at the front
    assert "at the front" in words and "bottom" in words


# ---- PDF -----------------------------------------------------------------------------------


def test_pdf_has_a4_pages_cover_parts_steps_and_last(tower_booklet):
    _, text, pdf = tower_booklet
    assert pdf.startswith(b"%PDF-1.")
    assert pdf.rstrip().endswith(b"%%EOF")
    pages = len(re.findall(rb"/Type /Page\b", pdf))
    html_pages = text.count('<section class="page ')
    assert pages == html_pages == 1 + len(sections(text, "parts")) + 3 + 1
    boxes = re.findall(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", pdf)
    assert len(boxes) == pages
    for w, h in boxes:
        assert abs(float(w) - 595.3) < 1.5 and abs(float(h) - 841.9) < 1.5
    assert b"CreationDate" not in pdf and b"ModDate" not in pdf


def test_pdf_pages_are_the_page_pictures_and_show_each_step(tower_booklet, catalog):
    project, text, pdf = tower_booklet
    pages = pdf_pages(pdf)
    expected = I.page_images(project, catalog)
    assert len(pages) == len(expected)
    for got, want in zip(pages, expected, strict=True):
        assert np.array_equal(np.asarray(got), np.asarray(want))
        ink = (np.asarray(got) < 200).any(axis=2).mean()
        assert ink > 0.005  # not a blank sheet
    # each step page carries that step's picture (found by its yellow line)
    first_step = 1 + len(sections(text, "parts"))
    for k, sec in enumerate(sections(text, "step")):
        (pic,) = pictures(sec, "model")
        page = pages[first_step + k]
        rows, cols = np.nonzero(near_halo(pic))
        prow, pcol = np.nonzero(near_halo(page))
        dy, dx = int(prow.min() - rows.min()), int(pcol.min() - cols.min())
        region = page.crop((dx, dy, dx + pic.width, dy + pic.height))
        diff = np.abs(np.asarray(region, dtype=np.int64) - np.asarray(pic, dtype=np.int64))
        assert diff.mean() < 2, k + 1


def test_both_files_are_deterministic(tmp_path, catalog):
    project = make_project(tmp_path, hidden_in_the_middle(), catalog)
    out = I.make_instructions(project, catalog)
    one = out["html"].read_bytes(), out["pdf"].read_bytes()
    out = I.make_instructions(project, catalog)
    two = out["html"].read_bytes(), out["pdf"].read_bytes()
    assert one == two


def test_page_pictures_are_a4(tmp_path, catalog):
    project = make_project(tmp_path, small_tower(), catalog)
    pages = I.page_images(project, catalog)
    assert len(pages) >= 5
    for im in pages:
        assert im.size == (I.PAGE_W, I.PAGE_H)
        assert im.mode == "RGB"
    # 150 dots per inch: A4 is 210 x 297 mm
    assert abs(I.PAGE_W / I.DPI * 25.4 - 210) < 1 and abs(I.PAGE_H / I.DPI * 25.4 - 297) < 1


# ---- size and speed ------------------------------------------------------------------------


def _bond_layer(z: int) -> list[tuple[str, int, int, int]]:
    """One 16 x 16 layer of 2x4 plates. Layers turn every two, and every other layer is
    shifted by 2 studs (2x2 plates fill the ends), so each plate sits across two below."""
    kind, out = z % 4, []
    for row in range(8):
        if kind % 2 == 0:
            spots = [(4 * k, "3020") for k in range(4)]
        else:
            spots = [(0, "3022"), (14, "3022")] + [(4 * k + 2, "3020") for k in range(3)]
        for along, pid in spots:
            if kind < 2:
                out.append((pid, along, 2 * row, 0))
            else:
                out.append((pid, 2 * row, along, 90 if pid == "3020" else 0))
    return out


def two_hundred_steps() -> Build:
    """A 16 x 16 block of plates in a staggered bond, 8 plates a step, 200 steps."""
    parts: list[Placement] = []
    z = 0
    while len(parts) < 1600:
        for pid, x, y, rot in _bond_layer(z):
            if len(parts) == 1600:
                break
            colour = (GREY, RED, BLUE, YELLOW)[(x // 4 + y // 4 + z) % 4]
            parts.append(Placement(pid, colour, x, y, z, rot, len(parts) // 8 + 1))
        z += 1
    return Build((16, 16, z), parts)


def two_hundred_small_steps() -> Build:
    """600 parts, 3 a step: the same bond, layers of plates and of bricks by turns, in 8
    colours. Few parts a step means big pictures unless the booklet keeps them in check."""
    parts: list[Placement] = []
    z = layer = 0
    while len(parts) < 600:
        brick = layer % 2 == 1
        for pid, x, y, rot in _bond_layer(layer):
            if len(parts) == 600:
                break
            if brick:
                pid = {"3020": "3001", "3022": "3003"}[pid]
            colour = (GREY, RED, BLUE, YELLOW, 2, 25, 15, 0)[(x // 2 + y // 2 + layer) % 8]
            parts.append(Placement(pid, colour, x, y, z, rot, len(parts) // 3 + 1))
        z += 3 if brick else 1
        layer += 1
    return Build((16, 16, z), parts)


@pytest.mark.parametrize(
    "make, n_parts", [(two_hundred_steps, 1600), (two_hundred_small_steps, 600)]
)
def test_a_200_step_booklet_is_quick_and_not_too_big(tmp_path, catalog, make, n_parts):
    b = make()
    assert max(p.step for p in b.parts) == 200 and len(b.parts) == n_parts
    project = make_project(tmp_path, b, catalog)
    report = project.load_build().report
    assert report is not None and report.ok
    start = time.perf_counter()
    out = I.make_instructions(project, catalog)
    elapsed = time.perf_counter() - start
    text = out["html"].read_text(encoding="utf-8")
    size = out["html"].stat().st_size
    print(
        f"200 steps, {n_parts} parts: {elapsed:.1f} s, HTML {size / 1e6:.1f} MB, "
        f"PDF {out['pdf'].stat().st_size / 1e6:.1f} MB"
    )
    assert elapsed < 30, elapsed
    assert size < 15e6, size
    # the step pictures together keep within the booklet's budget, whatever the part count
    sizes = re.findall(r'<img class="model" width="(\d+)" height="(\d+)"', text)
    assert len(sizes) == 200
    assert sum(int(w) * int(h) for w, h in sizes) <= I.STEP_BUDGET


def plate_under_a_tile() -> Build:
    """Step 2: a 2x4 plate between two rows of bricks, with a 2x4 tile on it. Only the
    plate's two short ends show, a sliver, so it counts as hidden."""
    parts = base_4x4()
    parts += [
        Placement("3010", RED, 0, 0, 6, 0, 2),
        Placement("3010", RED, 0, 3, 6, 0, 2),
        Placement("3020", BLUE, 0, 1, 6, 0, 2),  # index 6: the plate
        Placement("87079", YELLOW, 0, 1, 7, 0, 2),  # the tile on it
    ]
    return Build((4, 4, 9), parts)


def test_a_part_showing_only_an_edge_counts_as_hidden(catalog):
    from bricksnap import render as R

    b = plate_under_a_tile()
    assert check(b, catalog).ok
    # a few pixels of it show, so by pixels alone it would count as seen
    for view in ("iso", "iso_back"):
        assert 6 in R.visible_parts(b, catalog, view, upto_step=2)
    plan = I.plan_steps(b, catalog)
    assert plan[1].hidden == [6]
    (sentence,) = plan[1].words
    assert sentence.startswith("The plate 2 x 4 goes in the middle")
    assert "under the yellow tile 2 x 4 of this step" in sentence  # its colour differs
    assert sentence.endswith("Put it in first.")


def test_step_parts_have_their_names_in_the_html(tower_booklet):
    _, text, _ = tower_booklet
    step3 = sections(text, "step")[2]
    assert '<span class="name">Plate 2 x 4</span>' in step3
    assert '<span class="name">Plate 1 x 1</span>' in step3


def test_the_cat_sample_makes_a_booklet(tmp_path, catalog):
    import shutil

    sample = Path(__file__).resolve().parent.parent / "samples" / "projects" / "cat-designed"
    folder = tmp_path / "cat"
    shutil.copytree(sample, folder, ignore=shutil.ignore_patterns("instructions.*"))
    out = I.make_instructions(Project(folder), catalog)
    text = out["html"].read_text(encoding="utf-8")
    build = Project(folder).load_build()
    steps = len({p.step for p in build.parts})
    assert len(sections(text, "step")) == steps == 33
    assert f"{len(build.parts)} parts, 33 steps" in text
    plan = I.plan_steps(build, catalog)
    assert text.count(f"&#8635; {I.TURN_TEXT}") == sum(s.turn for s in plan)
    # every hidden part has its sentence on its page
    for s, sec in zip(plan, sections(text, "step"), strict=True):
        for w in s.words + s.behind_words:
            assert html.escape(w) in sec


# ---- review findings: words on back pages, parts seen from the other side, names, fonts ----


def test_hidden_parts_on_a_back_page_are_placed_as_the_reader_sees_them(catalog):
    """On a page drawn from the back the model's own left is on the right of the picture,
    so the words say right (and near or far, not front or back)."""
    b = hidden_on_the_back_page()
    assert check(b, catalog).ok
    plan = I.plan_steps(b, catalog)
    assert plan[2].view == "iso_back" and plan[2].hidden == [10, 11, 12]
    for sentence in plan[2].words:
        side = sentence.split(",")[0]
        assert "right" in side and "left" not in side, sentence
        assert "front" not in side and "back" not in side, sentence
    # drawn from the back, the plates are on the right half of the picture
    s = 16
    frame = R.view_frame(b.shape, "iso_back", px_per_stud=s, labels=False)
    col = frame.project([[1.0, 2.0, 6.0]])[0][0]
    assert col > frame.width / 2
    # the same part on a front page keeps the front's words
    assert "left" in I.where_words(b, catalog, 10, view="iso").split(",")[0]
    assert I.where_words(b, catalog, 10) == I.where_words(b, catalog, 10, view="iso")


def test_where_words_from_the_back_turn_sides_round(catalog):
    b = corner_behind_walls()
    # the corner brick: back left as seen from the front, so near right from the back
    assert "at the back left" in I.where_words(b, catalog, 10, view="iso")
    words = I.where_words(b, catalog, 10, view="iso_back")
    assert "at the near right" in words
    words = I.where_words(b, catalog, 0, view="iso_back")  # bottom layer, at the front
    assert "at the far side" in words


def test_a_part_seen_only_from_the_other_side_gets_words_and_a_picture(tmp_path, catalog):
    b = split_between_sides()
    assert check(b, catalog).ok
    plan = I.plan_steps(b, catalog)
    step = plan[1]
    assert step.parts == [8, 9]
    assert step.view == "iso" and step.hidden == []
    assert step.behind == [9]
    (sentence,) = step.behind_words
    assert sentence.startswith("The yellow brick 1 x 1") or "brick 1 x 1" in sentence.lower()
    assert "at the back" in sentence
    project = make_project(tmp_path, b, catalog)
    text = I.make_instructions(project, catalog)["html"].read_text(encoding="utf-8")
    sec = sections(text, "step")[1]
    assert html.escape(sentence) in sec
    (pic,) = pictures(sec, "behind")
    assert I.SIDE_WORDS["iso_back"] in sec.split('<img class="behind"')[0].rsplit("<figure>", 1)[1]
    # the picture is from the back, with the brick that is behind the wall marked
    assert near_halo(pic).sum() > 20
    yellow = np.asarray(catalog.colours[YELLOW].rgb, dtype=np.int64)
    a = np.asarray(pic, dtype=np.int64)
    assert ((np.abs(a - yellow) <= 40).all(axis=2)).sum() > 30


def test_the_put_in_first_picture_includes_what_the_hidden_part_stands_on(tmp_path, catalog):
    b = hidden_on_a_new_part()
    assert check(b, catalog).ok
    plan = I.plan_steps(b, catalog)
    assert 6 in plan[1].hidden and 5 not in plan[1].hidden
    assert plan[1].supports == [5]
    project = make_project(tmp_path, b, catalog)
    text = I.make_instructions(project, catalog)["html"].read_text(encoding="utf-8")
    sec = sections(text, "step")[1]
    assert I.FIRST_WITH_SUPPORT in sec and I.FIRST_TEXT not in sec
    (pic,) = pictures(sec, "first")
    red = np.asarray(catalog.colours[RED].rgb, dtype=np.int64)
    a = np.asarray(pic, dtype=np.int64)
    assert ((np.abs(a - red) <= 40).all(axis=2)).sum() > 100  # the new red brick, in full


def test_part_names_in_a_step_tell_the_parts_apart(tmp_path, catalog):
    """Shortened names never become the name of a different, plainer part."""
    parts = base_4x4()
    parts += [
        Placement("3005", RED, 0, 0, 6, 0, 2),
        Placement("87087", RED, 1, 0, 6, 0, 2),
        Placement("4733", RED, 2, 0, 6, 0, 2),
        Placement("3024", RED, 0, 2, 6, 0, 2),
        Placement("60897", RED, 1, 2, 6, 0, 2),
        Placement("3023b", RED, 0, 3, 6, 0, 2),
        Placement("15573", RED, 2, 3, 6, 0, 2),
        Placement("3069b", RED, 2, 1, 6, 0, 2),
    ]
    b = Build((4, 4, 9), parts)
    assert check(b, catalog).ok
    project = make_project(tmp_path, b, catalog)
    text = I.make_instructions(project, catalog)["html"].read_text(encoding="utf-8")
    names = re.findall(r'<span class="name">([^<]*)</span>', sections(text, "step")[1])
    assert len(names) == 8 and len(set(names)) == 8, names
    assert "Tile 1 x 2" in names  # " with Groove" is still left off where nothing is lost
    # over the whole parts table, no two parts share a short name
    shorts = {pid: I._short_name(catalog, pid) for pid in catalog.parts}
    assert len(set(shorts.values())) == len(shorts)
    assert shorts["3665b"] == "Slope Brick 45 2 x 1 Inverted"
    assert shorts["3005"] == "Brick 1 x 1" and shorts["87087"] != "Brick 1 x 1"


@pytest.mark.parametrize("width, sizes", [(118, (19, 17, 15)), (326, (22, 20, 18))])
def test_part_names_on_pdf_pages_are_never_cut(catalog, width, sizes):
    for pid, part in catalog.parts.items():
        for name in (part.name, I._short_name(catalog, pid)):
            size, lines = I._fit_name(name, width, sizes)
            assert size in sizes
            assert "".join(lines).replace(" ", "") == name.replace(" ", ""), (name, lines)
            assert all(I._font_for(t, size).getlength(t) <= width for t in lines), lines


def test_long_words_are_broken_to_fit(catalog):
    font = I._font(40)
    lines = I._wrap("Short " + "x" * 120 + " end", font, 500)
    assert "".join(lines).replace(" ", "") == "Short" + "x" * 120 + "end"
    assert all(font.getlength(t) <= 500 for t in lines)


def test_letters_the_built_in_font_lacks_are_drawn_from_another_font():
    text = "Café Ñandú – Kätzchen"
    plain = I._font(40)
    assert not all(I._covers(plain, ch) for ch in text)  # the font that comes with Pillow
    if not I._fallback_fonts():
        pytest.skip("no font with these letters on this computer")
    font = I._font_for(text, 40)
    assert all(I._covers(font, ch) for ch in text)
    assert I._font_for("Plain words", 40) is plain


def test_a_long_name_stays_on_the_cover_and_in_the_footer(tmp_path, catalog):
    name = "Supercalifragilisticexpialidocious" * 4 + " Kätzchen"
    project = make_project(tmp_path, small_tower(), catalog, name=name)
    pages = I.page_images(project, catalog)
    for page in (pages[0], pages[-1]):
        a = np.asarray(page)
        dark = (a < 200).any(axis=2)
        assert not dark[:, :40].any() and not dark[:, -40:].any()
