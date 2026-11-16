"""Tests for bricksnap.seed.load_seed: formats, orientation, scale, colour and bad input."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import trimesh
import trimesh.visual
from PIL import Image

from bricksnap.seed import MAX_STUDS, MIN_STUDS, SUPPORTED, _sample_texture, load_seed
from bricksnap.types import DEFAULT_COLOUR, Seed, SeedError

ALL_FORMATS = ("stl", "obj", "glb", "gltf", "3mf", "ply")
Z_UP = ("stl", "3mf", "ply")
Y_UP = ("obj", "glb", "gltf")


def srgb(linear_255: float) -> int:
    """What a glTF linear 0..255 value looks like on screen (sRGB 0..255)."""
    v = linear_255 / 255.0
    s = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return int(round(s * 255))


def box_mesh(size=(10.0, 20.0, 30.0)) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=size)


def export(mesh_or_scene, tmp_path, name: str):
    path = tmp_path / name
    mesh_or_scene.export(str(path))
    return path


def write_ascii_stl(path, triangles) -> None:
    facets = []
    for tri in triangles:
        corners = "".join(f"vertex {x} {y} {z}\n" for x, y, z in tri)
        facets.append(f"facet normal 0 0 0\nouter loop\n{corners}endloop\nendfacet\n")
    path.write_text("solid t\n" + "".join(facets) + "endsolid t\n")


TETRA = [
    [(0, 0, 0), (4, 0, 0), (0, 2, 0)],
    [(0, 0, 0), (0, 2, 0), (0, 0, 1)],
    [(0, 0, 0), (0, 0, 1), (4, 0, 0)],
    [(4, 0, 0), (0, 0, 1), (0, 2, 0)],
]


# ---- the sample model -----------------------------------------------------------------------


def test_pawn_loads_upright_scaled_and_at_origin(pawn_path):
    seed = load_seed(pawn_path, studs=16)
    assert isinstance(seed, Seed)
    assert seed.source == "pawn.stl"
    assert seed.vertices.dtype == np.float64 and seed.vertices.shape[1] == 3
    assert seed.faces.dtype == np.int64 and seed.faces.shape[1] == 3
    np.testing.assert_allclose(seed.vertices.min(axis=0), 0.0, atol=1e-12)
    # 30 x 30 x 42.5 mm, Z-up: the height is the longest side and becomes 16 studs
    np.testing.assert_allclose(seed.extent_mm, [30 / 42.5 * 128, 30 / 42.5 * 128, 128.0])
    assert seed.face_colors is None
    # the file holds 2496 facets, 96 of them zero-area; they are dropped
    assert len(seed.faces) == 2400
    assert seed.faces.max() < len(seed.vertices)
    # every vertex is used by some face
    assert len(np.unique(seed.faces)) == len(seed.vertices)


@pytest.mark.parametrize("studs", [MIN_STUDS, 7, 16, 48, MAX_STUDS])
def test_longest_side_is_exactly_studs_times_8mm(pawn_path, studs):
    seed = load_seed(pawn_path, studs=studs)
    assert seed.extent_mm.max() == pytest.approx(studs * 8.0, abs=1e-9)
    assert seed.vertices.min() >= 0.0


def test_numpy_integer_studs_are_accepted(pawn_path):
    studs: Any = np.int64(10)
    seed = load_seed(pawn_path, studs=studs)
    assert seed.extent_mm.max() == pytest.approx(80.0)


# ---- formats and default orientation -------------------------------------------------------


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_every_supported_format_loads_with_its_default_up_axis(tmp_path, fmt):
    path = export(box_mesh(), tmp_path, f"box.{fmt}")
    seed = load_seed(path, studs=12)
    scale = 96.0 / 30.0
    if fmt in Z_UP:
        expected = np.array([10.0, 20.0, 30.0]) * scale
    else:  # Y-up: file y (20) becomes height, file z (30) becomes depth
        expected = np.array([10.0, 30.0, 20.0]) * scale
    np.testing.assert_allclose(seed.extent_mm, expected, rtol=1e-6)
    np.testing.assert_allclose(seed.vertices.min(axis=0), 0.0, atol=1e-9)
    assert len(seed.faces) == 12
    assert seed.source == f"box.{fmt}"


def test_supported_list_matches_contract():
    assert set(SUPPORTED) == {f".{f}" for f in ALL_FORMATS}


def test_extension_case_does_not_matter(tmp_path):
    path = export(box_mesh(), tmp_path, "box.stl")
    upper = path.rename(tmp_path / "BOX.STL")
    seed = load_seed(upper, studs=12)
    assert seed.extent_mm[2] == pytest.approx(96.0)  # still treated as Z-up


def test_y_up_file_front_faces_minus_y(tmp_path):
    """In a Y-up file the front faces +Z; after loading it must face -y (y = 0 is the front)."""
    mesh = box_mesh((10.0, 10.0, 10.0))
    nose = trimesh.creation.cone(radius=2.0, height=10.0)  # points along +Z
    nose.apply_translation((0.0, 0.0, 5.0))
    model = trimesh.util.concatenate([mesh, nose])
    seed = load_seed(export(model, tmp_path, "nose.glb"), studs=8)
    tip = seed.vertices[np.argmin(seed.vertices[:, 1])]
    # the nose tip is the only point at the very front, and it is centred in x and z
    assert np.sum(np.isclose(seed.vertices[:, 1], 0.0)) == 1
    assert tip[0] == pytest.approx(seed.extent_mm[0] / 2, abs=1e-6)
    assert tip[2] == pytest.approx(seed.extent_mm[2] / 2, abs=1e-6)
    assert seed.extent_mm[1] == pytest.approx(64.0)  # depth (box + nose) is the longest side


@pytest.mark.parametrize(
    "up, mapping",
    [
        ("z", lambda x, y, z: (x, y, z)),
        ("y", lambda x, y, z: (x, -z, y)),
        ("x", lambda x, y, z: (y, z, x)),
        ("Y", lambda x, y, z: (x, -z, y)),
    ],
)
def test_up_override_maps_axes_as_documented(tmp_path, up, mapping):
    path = tmp_path / "tetra.stl"
    write_ascii_stl(path, TETRA)
    seed = load_seed(path, studs=8, up=up)
    original = np.array(sorted({v for tri in TETRA for v in tri}), dtype=float)
    mapped = np.array([mapping(*v) for v in original], dtype=float)
    mapped -= mapped.min(axis=0)
    mapped *= 64.0 / (mapped.max(axis=0) - mapped.min(axis=0)).max()
    got = np.unique(np.round(seed.vertices, 9), axis=0)  # STL repeats corners per triangle
    want = np.unique(np.round(mapped, 9), axis=0)
    np.testing.assert_allclose(got, want, atol=1e-9)


def test_up_override_applies_to_y_up_formats_too(tmp_path):
    path = export(box_mesh(), tmp_path, "box.glb")
    seed = load_seed(path, studs=12, up="z")
    np.testing.assert_allclose(seed.extent_mm, np.array([10.0, 20.0, 30.0]) * 3.2, rtol=1e-6)


# ---- scenes ---------------------------------------------------------------------------------


def test_scene_is_flattened_with_every_transform(tmp_path):
    scene = trimesh.Scene()
    scene.add_geometry(box_mesh((2.0, 2.0, 2.0)), node_name="a", geom_name="a")
    moved = np.eye(4)
    moved[:3, 3] = (10.0, 0.0, 0.0)
    scene.add_geometry(box_mesh((2.0, 2.0, 2.0)), node_name="b", geom_name="b", transform=moved)
    seed = load_seed(export(scene, tmp_path, "two.glb"), studs=12)
    assert len(seed.faces) == 24
    # x runs from -1 to 11 in the file: 12 mm, scaled to 96 mm
    np.testing.assert_allclose(seed.extent_mm, [96.0, 16.0, 16.0], rtol=1e-6)
    # the gap between the boxes (x from 1 to 9) holds no vertex
    xs = seed.vertices[:, 0] / 8.0  # back to file millimetres
    assert not np.any((xs > 2.0 + 1e-6) & (xs < 10.0 - 1e-6))


def test_scene_with_one_geometry_used_by_two_nodes(tmp_path):
    scene = trimesh.Scene()
    geom = box_mesh((2.0, 2.0, 2.0))
    scene.add_geometry(geom, node_name="a", geom_name="shared")
    up = np.eye(4)
    up[:3, 3] = (0.0, 6.0, 0.0)  # file +y is up for GLB
    scene.graph.update(
        frame_to="b", frame_from=scene.graph.base_frame, matrix=up, geometry="shared"
    )
    seed = load_seed(export(scene, tmp_path, "inst.glb"), studs=8)
    assert len(seed.faces) == 24
    # two 2 mm boxes, y from -1 to 1 and 5 to 7: 8 mm tall, scaled to 64 mm
    np.testing.assert_allclose(seed.extent_mm, [16.0, 16.0, 64.0], rtol=1e-6)


def test_mirrored_node_keeps_its_triangles_facing_out(tmp_path):
    """A mirroring transform flips the winding; the loader flips it back, so the mirrored
    copy is not inside out (voxelize relies on outward winding)."""
    scene = trimesh.Scene()
    scene.add_geometry(box_mesh((2.0, 2.0, 2.0)), geom_name="a")
    mirror = np.diag([-1.0, 1.0, 1.0, 1.0])
    mirror[0, 3] = 5.0
    scene.add_geometry(box_mesh((2.0, 2.0, 2.0)), geom_name="b", transform=mirror)
    seed = load_seed(export(scene, tmp_path, "mirror.glb"), studs=8)
    whole = trimesh.Trimesh(seed.vertices, seed.faces, process=False)
    parts = whole.split(only_watertight=False)
    assert len(parts) == 2
    assert all(part.volume > 0 for part in parts)


def test_rotation_in_a_scene_transform_is_applied(tmp_path):
    scene = trimesh.Scene()
    turn = trimesh.transformations.rotation_matrix(np.pi / 2, (0, 0, 1))  # about file z
    scene.add_geometry(box_mesh((10.0, 2.0, 2.0)), transform=turn)
    seed = load_seed(export(scene, tmp_path, "turned.glb"), studs=10)
    # the long side now lies along file y, which is up for GLB
    np.testing.assert_allclose(seed.extent_mm, [16.0, 16.0, 80.0], rtol=1e-6)


# ---- colour ---------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_uncoloured_file_has_no_face_colors(tmp_path, fmt):
    seed = load_seed(export(box_mesh(), tmp_path, f"plain.{fmt}"), studs=8)
    assert seed.face_colors is None


def test_per_face_colours_from_ply(tmp_path):
    mesh = box_mesh()
    colours = np.zeros((12, 4), dtype=np.uint8)
    colours[:, 3] = 255
    colours[:6, :3] = (200, 30, 30)
    colours[6:, :3] = (20, 40, 220)
    mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=colours)
    seed = load_seed(export(mesh, tmp_path, "faces.ply"), studs=8)
    assert seed.face_colors is not None
    assert seed.face_colors.dtype == np.uint8 and seed.face_colors.shape == (12, 3)
    assert sorted(map(tuple, np.unique(seed.face_colors, axis=0).tolist())) == [
        (20, 40, 220),
        (200, 30, 30),
    ]
    assert (seed.face_colors == (200, 30, 30)).all(axis=1).sum() == 6


def test_per_vertex_colours_average_over_each_face(tmp_path):
    vertices = np.array([[0, 0, 0], [8, 0, 0], [0, 8, 0], [0, 0, 8]], dtype=float)
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    vc = np.array(
        [[255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 255, 255], [90, 90, 90, 255]], dtype=np.uint8
    )
    mesh = trimesh.Trimesh(vertices, faces, vertex_colors=vc, process=False)
    seed = load_seed(export(mesh, tmp_path, "vc.ply"), studs=8)
    assert seed.face_colors is not None
    expected = np.round(vc[faces, :3].astype(float).mean(axis=1)).astype(np.uint8)
    got = {tuple(c) for c in seed.face_colors.tolist()}
    assert got == {tuple(c) for c in expected.tolist()}


def test_obj_vertex_colours_are_used_as_written(tmp_path):
    mesh = trimesh.creation.icosphere(1)
    mesh.visual.vertex_colors = np.tile([30, 200, 30, 255], (len(mesh.vertices), 1))
    seed = load_seed(export(mesh, tmp_path, "green.obj"), studs=8)
    assert seed.face_colors is not None
    assert (seed.face_colors == (30, 200, 30)).all()


def test_gltf_vertex_colours_are_converted_from_linear(tmp_path):
    mesh = trimesh.creation.icosphere(1)
    mesh.visual.vertex_colors = np.tile([30, 200, 30, 255], (len(mesh.vertices), 1))
    seed = load_seed(export(mesh, tmp_path, "green.glb"), studs=8)
    assert seed.face_colors is not None
    assert (seed.face_colors == (srgb(30), srgb(200), srgb(30))).all()


def test_gltf_material_base_colour_per_mesh(tmp_path):
    """A scene of meshes with one flat material each (like a low-poly model)."""
    scene = trimesh.Scene()
    for i, factor in enumerate([(255, 0, 0, 255), (28, 0, 0, 255), (130, 92, 11, 255)]):
        mesh = box_mesh((2.0, 2.0, 2.0))
        mesh.apply_translation((3.0 * i, 0.0, 0.0))
        material = trimesh.visual.material.PBRMaterial(baseColorFactor=factor)
        mesh.visual = trimesh.visual.TextureVisuals(material=material)
        scene.add_geometry(mesh, geom_name=f"part{i}")
    seed = load_seed(export(scene, tmp_path, "parts.glb"), studs=8)
    assert seed.face_colors is not None and seed.face_colors.shape == (36, 3)
    found = {tuple(c) for c in seed.face_colors.tolist()}
    assert found == {(255, 0, 0), (srgb(28), 0, 0), (srgb(130), srgb(92), srgb(11))}
    # each mesh keeps its own colour: the left-most faces are the first material's
    left = seed.vertices[seed.faces].mean(axis=1)[:, 0] < 16.0
    assert (seed.face_colors[left] == (255, 0, 0)).all()


def test_material_without_any_colour_counts_as_uncoloured(tmp_path):
    mesh = box_mesh()
    mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial())
    seed = load_seed(export(mesh, tmp_path, "bare.glb"), studs=8)
    assert seed.face_colors is None


def test_scene_mixing_coloured_and_uncoloured_meshes(tmp_path, catalog):
    scene = trimesh.Scene()
    red = box_mesh((2.0, 2.0, 2.0))
    red.visual = trimesh.visual.ColorVisuals(red, face_colors=np.tile([200, 0, 0, 255], (12, 1)))
    plain = box_mesh((2.0, 2.0, 2.0))
    plain.apply_translation((5.0, 0.0, 0.0))
    scene.add_geometry(red, geom_name="red")
    scene.add_geometry(plain, geom_name="plain")
    seed = load_seed(export(scene, tmp_path, "mixed.glb"), studs=8)
    assert seed.face_colors is not None and seed.face_colors.shape == (24, 3)
    grey = catalog.colours[DEFAULT_COLOUR].rgb
    found = {tuple(c) for c in seed.face_colors.tolist()}
    assert found == {(srgb(200), 0, 0), grey}


def quadrant_texture() -> Image.Image:
    image = Image.new("RGB", (2, 2))
    image.putpixel((0, 0), (255, 0, 0))  # top-left: v near 1, u near 0
    image.putpixel((1, 0), (0, 255, 0))  # top-right
    image.putpixel((0, 1), (0, 0, 255))  # bottom-left: v near 0
    image.putpixel((1, 1), (255, 255, 0))  # bottom-right
    return image


def textured_quad_strip(factor=(102, 102, 102, 255), image=None) -> trimesh.Trimesh:
    """Four separate triangles whose UV centroids fall in the four texture quadrants."""
    vertices, faces, uv = [], [], []
    centres = [(0.25, 0.75), (0.75, 0.75), (0.25, 0.25), (0.75, 0.25)]
    for i, (u, v) in enumerate(centres):
        base = len(vertices)
        vertices += [(4.0 * i, 0, 0), (4.0 * i + 3, 0, 0), (4.0 * i, 3, 0)]
        faces.append((base, base + 1, base + 2))
        uv += [(u - 0.1, v - 0.1), (u + 0.1, v - 0.1), (u, v + 0.2)]
    vertices.append((0.0, 0.0, 5.0))  # give the model some height: one extra triangle
    faces.append((0, 1, len(vertices) - 1))
    uv.append((0.25, 0.75))
    mesh = trimesh.Trimesh(np.array(vertices), np.array(faces), process=False)
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=quadrant_texture() if image is None else image, baseColorFactor=factor
    )
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.array(uv), material=material)
    return mesh


QUADRANTS = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 0]]


@pytest.mark.parametrize("fmt", ["glb", "gltf", "obj"])
def test_texture_is_sampled_at_each_face_uv_centroid(tmp_path, fmt):
    # glTF: a white colour factor leaves the texture as it is. OBJ: trimesh writes the factor
    # as the diffuse colour Kd 0.4 next to the texture; an MTL diffuse next to a texture is an
    # exporter default, so it is ignored
    factor = (255, 255, 255, 255) if fmt != "obj" else (102, 102, 102, 255)
    mesh = textured_quad_strip(factor=factor)
    seed = load_seed(export(mesh, tmp_path, f"tex.{fmt}"), studs=8, up="z")
    assert seed.face_colors is not None and seed.face_colors.shape == (5, 3)
    assert seed.face_colors.tolist() == QUADRANTS  # faces come out in file order
    if fmt == "obj":
        assert "Kd 0.4" in (tmp_path / "material.mtl").read_text()


@pytest.mark.parametrize("fmt", ["glb", "gltf"])
def test_gltf_colour_factor_tints_the_texture(tmp_path, fmt):
    """glTF multiplies the texture by baseColorFactor (in linear light)."""
    white = Image.new("RGB", (4, 4), (255, 255, 255))
    mesh = textured_quad_strip(factor=(255, 0, 0, 255), image=white)
    seed = load_seed(export(mesh, tmp_path, f"tint.{fmt}"), studs=8, up="z")
    assert seed.face_colors is not None
    assert (seed.face_colors == (255, 0, 0)).all()
    # a grey factor darkens each texel as a viewer does: linear 102/255 times the colour
    seed = load_seed(export(textured_quad_strip(), tmp_path, f"grey.{fmt}"), studs=8, up="z")
    assert seed.face_colors is not None
    assert seed.face_colors.tolist() == [[srgb(102 * c / 255) for c in rgb] for rgb in QUADRANTS]


def write_gltf_with_material(tmp_path, material: dict | None, vertex_rgba) -> Any:
    """An icosphere with COLOR_0 written by trimesh, then given a material as Blender does."""
    import json

    mesh = trimesh.creation.icosphere(1)
    mesh.visual.vertex_colors = np.tile(vertex_rgba, (len(mesh.vertices), 1))
    path = tmp_path / "painted.gltf"
    mesh.export(str(path))
    data = json.loads(path.read_text())
    if material is not None:
        data["materials"] = [material]
        data["meshes"][0]["primitives"][0]["material"] = 0
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize(
    "material, factor",
    [
        ({"pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1]}}, (1.0, 1.0, 1.0)),
        ({"pbrMetallicRoughness": {"metallicFactor": 0}}, (1.0, 1.0, 1.0)),  # no factor: white
        ({"name": "bare"}, (1.0, 1.0, 1.0)),
        ({"pbrMetallicRoughness": {"baseColorFactor": [0.5, 1, 0.2, 1]}}, (0.5, 1.0, 0.2)),
    ],
)
def test_gltf_vertex_colours_next_to_a_material(tmp_path, material, factor):
    """Vertex-painted glTF files from Blender always carry a material too. COLOR_0 multiplies
    the material's base colour (both linear)."""
    path = write_gltf_with_material(tmp_path, material, [30, 200, 30, 255])
    seed = load_seed(path, studs=8)
    assert seed.face_colors is not None
    expected = tuple(srgb(v * f) for v, f in zip((30, 200, 30), factor, strict=True))
    assert (seed.face_colors == expected).all()


def test_gltf_all_white_vertex_colours_leave_the_texture_unchanged():
    """Some exporters write COLOR_0 all white next to a texture; it changes nothing."""
    from bricksnap.seed import _colours

    mesh = textured_quad_strip(factor=(255, 255, 255, 255))
    assert isinstance(mesh.visual, trimesh.visual.TextureVisuals)
    mesh.visual.vertex_attributes["color"] = np.full((len(mesh.vertices), 4), 255, np.uint8)
    got = _colours(mesh, ".glb")
    assert got is not None and got.tolist() == QUADRANTS
    # a red COLOR_0 tints it like the factor does
    red = np.tile([255, 0, 0, 255], (len(mesh.vertices), 1)).astype(np.uint8)
    mesh.visual.vertex_attributes["color"] = red
    got = _colours(mesh, ".glb")
    assert got is not None and got.tolist() == [[c[0], 0, 0] for c in QUADRANTS]


# OBJ files whose colour comes only from trimesh's own fallbacks have no colour

TETRA_OBJ = "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\n"
TETRA_UV_FACES = (
    "vt 0 0\nvt 1 0\nvt 0 1\nf 1/1 3/2 2/3\nf 1/1 2/2 4/3\nf 1/1 4/2 3/3\nf 2/1 3/2 4/3\n"
)
TETRA_FACES = "f 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n"


def test_obj_with_uvs_but_no_material_is_uncoloured(tmp_path):
    path = tmp_path / "uv.obj"
    path.write_text(TETRA_OBJ + TETRA_UV_FACES)
    assert load_seed(path, studs=8).face_colors is None


@pytest.mark.parametrize("uvs", [True, False])
def test_obj_whose_material_file_is_missing_is_uncoloured(tmp_path, uvs):
    path = tmp_path / "missing.obj"
    faces = TETRA_UV_FACES if uvs else TETRA_FACES
    path.write_text("mtllib gone.mtl\n" + TETRA_OBJ + "usemtl m\n" + faces)
    assert load_seed(path, studs=8).face_colors is None


@pytest.mark.parametrize("uvs", [True, False])
def test_obj_material_without_a_diffuse_colour_is_uncoloured(tmp_path, uvs):
    (tmp_path / "nokd.mtl").write_text("newmtl m\nKa 1 1 1\nNs 10\n")
    faces = TETRA_UV_FACES if uvs else TETRA_FACES
    (tmp_path / "nokd.obj").write_text("mtllib nokd.mtl\n" + TETRA_OBJ + "usemtl m\n" + faces)
    assert load_seed(tmp_path / "nokd.obj", studs=8).face_colors is None


@pytest.mark.parametrize("fmt", ["obj", "glb"])
def test_trimesh_placeholder_texture_is_not_a_colour(tmp_path, fmt):
    """trimesh writes a 2 x 2 grey placeholder image (and grey 102) for UVs with no image."""
    mesh = box_mesh()
    rng = np.random.default_rng(0)
    mesh.visual = trimesh.visual.TextureVisuals(uv=rng.random((len(mesh.vertices), 2)))
    seed = load_seed(export(mesh, tmp_path, f"placeholder.{fmt}"), studs=8)
    assert seed.face_colors is None


def test_obj_explicit_grey_diffuse_is_kept(tmp_path):
    """Kd 0.4 written by the author (no placeholder image next to it) is a real colour."""
    (tmp_path / "grey.mtl").write_text("newmtl m\nKd 0.4 0.4 0.4\n")
    (tmp_path / "grey.obj").write_text("mtllib grey.mtl\n" + TETRA_OBJ + "usemtl m\n" + TETRA_FACES)
    seed = load_seed(tmp_path / "grey.obj", studs=8)
    assert seed.face_colors is not None and (seed.face_colors == (102, 102, 102)).all()


def test_small_real_texture_is_still_used(tmp_path):
    """Only trimesh's exact placeholder is ignored, not every tiny texture."""
    image = Image.new("RGB", (2, 2), (100, 100, 101))
    mesh = textured_quad_strip(factor=(255, 255, 255, 255), image=image)
    seed = load_seed(export(mesh, tmp_path, "tiny.glb"), studs=8, up="z")
    assert seed.face_colors is not None and (seed.face_colors == (100, 100, 101)).all()


# ---- 3MF colours ----------------------------------------------------------------------------


def write_3mf(path, resources: str, objects: str, build: str) -> None:
    import zipfile

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">\n'
        f"<resources>{resources}{objects}</resources><build>{build}</build></model>"
    )
    types = (
        '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
        'package/2006/content-types"><Default Extension="rels" ContentType="application/'
        'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType='
        '"application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats'
        '.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def tetra_object(object_id: int, attrs: str, triangle_attrs: list[str], size: float = 10) -> str:
    corners = [(0, 0, 0), (size, 0, 0), (0, size, 0), (0, 0, size)]
    verts = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in corners)
    tris = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
    rows = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}" {extra}/>'
        for (a, b, c), extra in zip(tris, triangle_attrs, strict=True)
    )
    return (
        f'<object id="{object_id}" type="model" {attrs}><mesh><vertices>{verts}</vertices>'
        f"<triangles>{rows}</triangles></mesh></object>"
    )


BASE = (
    '<basematerials id="1"><base name="Red" displaycolor="#FF0000"/>'
    '<base name="Blue" displaycolor="#0000FFFF"/></basematerials>'
    '<m:colorgroup id="5"><m:color color="#00FF00"/><m:color color="#FFFF00FF"/></m:colorgroup>'
)


def test_3mf_base_materials_and_colour_groups(tmp_path):
    triangle_attrs = ["", 'pid="1" p1="1"', 'pid="5" p1="0" p2="1" p3="1"', 'p1="1"']
    obj = tetra_object(2, 'pid="1" pindex="0"', triangle_attrs)
    path = tmp_path / "colours.3mf"
    write_3mf(path, BASE, obj, '<item objectid="2"/>')
    seed = load_seed(path, studs=8)
    assert seed.face_colors is not None
    # object default red; blue by triangle; mean of green, yellow, yellow; p1 alone uses the
    # object's group (base materials) with index 1: blue
    assert seed.face_colors.tolist() == [[255, 0, 0], [0, 0, 255], [170, 255, 0], [0, 0, 255]]


def test_3mf_coloured_and_uncoloured_objects_through_components(tmp_path, catalog):
    red = tetra_object(2, 'pid="1" pindex="0"', [""] * 4)
    plain = tetra_object(3, "", [""] * 4)
    group = (
        '<object id="4" type="model"><components>'
        '<component objectid="2"/><component objectid="3" transform="1 0 0 0 1 0 0 0 1 20 0 0"/>'
        "</components></object>"
    )
    path = tmp_path / "parts.3mf"
    write_3mf(path, BASE, red + plain + group, '<item objectid="4"/>')
    seed = load_seed(path, studs=8)
    assert seed.face_colors is not None and len(seed.face_colors) == 8
    left = seed.vertices[seed.faces].mean(axis=1)[:, 0] < seed.extent_mm[0] / 2
    assert (seed.face_colors[left] == (255, 0, 0)).all()
    assert (seed.face_colors[~left] == catalog.colours[DEFAULT_COLOUR].rgb).all()


def test_3mf_without_colour_resources_is_uncoloured(tmp_path):
    path = tmp_path / "plain.3mf"
    write_3mf(path, "", tetra_object(2, "", [""] * 4), '<item objectid="2"/>')
    assert load_seed(path, studs=8).face_colors is None


def test_3mf_with_broken_colour_references_still_loads(tmp_path):
    """A colour index past the end of its group, or a group that does not exist."""
    obj = tetra_object(2, 'pid="1" pindex="7"', ["", 'pid="9" p1="0"', "", ""])
    path = tmp_path / "broken.3mf"
    write_3mf(path, BASE, obj, '<item objectid="2"/>')
    seed = load_seed(path, studs=8)
    assert len(seed.faces) == 4
    assert seed.face_colors is None


def test_texture_sampling_wraps_uvs_outside_0_1():
    image = quadrant_texture()
    faces = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]])
    uv = np.array(
        [
            [1.25, 0.75], [1.25, 0.75], [1.25, 0.75],  # wraps to (0.25, 0.75): red
            [-0.25, -0.75], [-0.25, -0.75], [-0.25, -0.75],  # wraps to (0.75, 0.25): yellow
            [1.0, 1.0], [1.0, 1.0], [1.0, 1.0],  # the very corner stays inside: green
        ]
    )  # fmt: skip
    got = _sample_texture(image, uv, faces)
    assert got.dtype == np.uint8
    assert got.tolist() == [[255, 0, 0], [255, 255, 0], [0, 255, 0]]


def test_texture_in_palette_mode_and_with_alpha():
    rgba = Image.new("RGBA", (1, 1), (10, 20, 30, 0))
    palette = Image.new("P", (1, 1), 1)
    palette.putpalette([0, 0, 0, 40, 50, 60] + [0] * 762)
    faces = np.array([[0, 1, 2]])
    uv = np.full((3, 2), 0.5)
    assert _sample_texture(rgba, uv, faces).tolist() == [[10, 20, 30]]
    assert _sample_texture(palette, uv, faces).tolist() == [[40, 50, 60]]


def test_obj_material_diffuse_colour(tmp_path):
    (tmp_path / "cube.mtl").write_text("newmtl paint\nKd 0.8 0.1 0.1\n")
    corners = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    lines = ["mtllib cube.mtl", *(f"v {x} {y} {z}" for x, y, z in corners), "usemtl paint"]
    lines += ["f 1 3 2", "f 1 2 4", "f 1 4 3", "f 2 3 4"]
    (tmp_path / "cube.obj").write_text("\n".join(lines) + "\n")
    seed = load_seed(tmp_path / "cube.obj", studs=8)
    assert seed.face_colors is not None
    assert (seed.face_colors == (204, 26, 26)).all()


def test_face_colours_follow_dropped_degenerate_faces(tmp_path):
    vertices = np.array([[0, 0, 0], [8, 0, 0], [0, 8, 0], [0, 0, 8], [4, 0, 0]], dtype=float)
    faces = np.array([[0, 2, 1], [0, 1, 4], [0, 1, 3], [0, 3, 2], [1, 2, 3]])  # 2nd is a line
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    colours = np.array([[1, 1, 1, 255], [99, 99, 99, 255], [2, 2, 2, 255],
                        [3, 3, 3, 255], [4, 4, 4, 255]], dtype=np.uint8)  # fmt: skip
    mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=colours)
    seed = load_seed(export(mesh, tmp_path, "deg.ply"), studs=8)
    assert len(seed.faces) == 4
    assert seed.face_colors is not None
    assert seed.face_colors[:, 0].tolist() == [1, 2, 3, 4]
    assert len(seed.vertices) == 4  # the vertex only the line used is gone


# ---- clean-up -------------------------------------------------------------------------------


def test_degenerate_triangles_are_dropped(tmp_path):
    path = tmp_path / "deg.stl"
    write_ascii_stl(
        path,
        TETRA + [[(1, 1, 1), (1, 1, 1), (1, 1, 1)], [(0, 0, 0), (2, 0, 0), (4, 0, 0)]],
    )
    seed = load_seed(path, studs=8)
    assert len(seed.faces) == 4
    tri = seed.vertices[seed.faces]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    assert (area > 0).all()


def test_tiny_model_in_metres_is_not_mistaken_for_degenerate(tmp_path):
    """glTF files are often in metres: a 2 cm model must still load."""
    mesh = trimesh.creation.icosphere(2, radius=0.01)
    seed = load_seed(export(mesh, tmp_path, "small.glb"), studs=10)
    assert len(seed.faces) == len(mesh.faces)
    assert seed.extent_mm.max() == pytest.approx(80.0)


# ---- bad input ------------------------------------------------------------------------------


def assert_plain(message: str) -> None:
    assert "Traceback" not in message and "Exception" not in message
    assert len(message) < 400


def test_flat_model_is_rejected_with_the_word_flat(tmp_path):
    path = tmp_path / "flat.stl"
    write_ascii_stl(
        path, [[(0, 0, 0), (10, 0, 0), (10, 10, 0)], [(0, 0, 0), (10, 10, 0), (0, 10, 0)]]
    )
    with pytest.raises(SeedError, match="flat") as info:
        load_seed(path, studs=16)
    assert "top to bottom" in str(info.value)
    assert "flat.stl" in str(info.value)
    assert_plain(str(info.value))


def test_flat_along_depth_is_rejected_too(tmp_path):
    path = tmp_path / "wall.stl"
    write_ascii_stl(
        path, [[(0, 0, 0), (10, 0, 0), (10, 0, 10)], [(0, 0, 0), (10, 0, 10), (0, 0, 10)]]
    )
    with pytest.raises(SeedError, match="flat") as info:
        load_seed(path, studs=16)
    assert "front to back" in str(info.value)


def test_flat_check_happens_after_orientation(tmp_path):
    """A model flat along file z is flat in depth once Y-up is applied."""
    path = tmp_path / "flat.stl"
    write_ascii_stl(
        path, [[(0, 0, 0), (10, 0, 0), (10, 10, 0)], [(0, 0, 0), (10, 10, 0), (0, 10, 0)]]
    )
    with pytest.raises(SeedError, match="front to back"):
        load_seed(path, studs=16, up="y")


def test_missing_file(tmp_path):
    with pytest.raises(SeedError, match="Could not find") as info:
        load_seed(tmp_path / "nothere.stl", studs=16)
    assert "nothere.stl" in str(info.value)
    assert_plain(str(info.value))


def test_folder_instead_of_file(tmp_path):
    folder = tmp_path / "model.stl"
    folder.mkdir()
    with pytest.raises(SeedError, match="folder"):
        load_seed(folder, studs=16)


@pytest.mark.parametrize("name", ["model.fbx", "model.blend", "model"])
def test_unsupported_extension_names_the_supported_formats(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"whatever")
    with pytest.raises(SeedError) as info:
        load_seed(path, studs=16)
    message = str(info.value)
    for fmt in ALL_FORMATS:
        assert fmt.upper() in message
    assert_plain(message)


def test_unsupported_extension_is_reported_even_if_the_file_is_missing(tmp_path):
    with pytest.raises(SeedError, match="STL"):
        load_seed(tmp_path / "gone.fbx", studs=16)


@pytest.mark.parametrize("fmt", ["glb", "ply", "3mf", "gltf"])
def test_corrupt_file_is_reported_plainly(tmp_path, fmt):
    path = tmp_path / f"broken.{fmt}"
    path.write_bytes(bytes(range(256)) * 7)
    with pytest.raises(SeedError) as info:
        load_seed(path, studs=16)
    assert "broken." in str(info.value)
    assert_plain(str(info.value))


@pytest.mark.parametrize("fmt", ["stl", "obj", "ply", "glb"])
def test_empty_file(tmp_path, fmt):
    path = tmp_path / f"empty.{fmt}"
    path.write_bytes(b"")
    with pytest.raises(SeedError):
        load_seed(path, studs=16)


def test_file_with_points_but_no_triangles(tmp_path):
    path = tmp_path / "points.obj"
    path.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\n")
    with pytest.raises(SeedError, match="no triangles"):
        load_seed(path, studs=16)


def test_only_zero_area_triangles(tmp_path):
    path = tmp_path / "lines.stl"
    write_ascii_stl(path, [[(0, 0, 0), (1, 1, 1), (2, 2, 2)], [(0, 0, 0), (0, 0, 0), (5, 0, 1)]])
    with pytest.raises(SeedError, match="zero area"):
        load_seed(path, studs=16)


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
def test_nan_or_infinite_coordinates(tmp_path, bad):
    path = tmp_path / "bad.stl"
    write_ascii_stl(path, TETRA[:3] + [[(4, 0, 0), (0, 0, bad), (0, 2, 0)]])
    with pytest.raises(SeedError, match="damaged") as info:
        load_seed(path, studs=16)
    assert_plain(str(info.value))


@pytest.mark.parametrize("studs", [0, 3, 97, 1000, -5])
def test_studs_out_of_range(pawn_path, studs):
    with pytest.raises(SeedError, match="between 4 and 96"):
        load_seed(pawn_path, studs=studs)


@pytest.mark.parametrize("studs", [16.5, "16", True, None])
def test_studs_must_be_a_whole_number(pawn_path, studs):
    with pytest.raises(SeedError, match="whole number"):
        load_seed(pawn_path, studs=studs)


@pytest.mark.parametrize("up", ["w", "", "-z", "xy"])
def test_bad_up_axis(pawn_path, up):
    with pytest.raises(SeedError, match="x, y or z"):
        load_seed(pawn_path, studs=16, up=up)


def test_seed_error_is_a_value_error(tmp_path):
    with pytest.raises(ValueError):
        load_seed(tmp_path / "x.stl", studs=16)
