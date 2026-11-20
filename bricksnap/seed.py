"""Load a 3D model file and turn it into a Seed: oriented, scaled, and placed on the grid.

CONTRACT (see tests/test_seed.py)

``load_seed(path, studs=N, up=None, piece=None, piece_box=None) -> Seed``

- Reads .stl, .obj, .glb, .gltf, .3mf and .ply with trimesh. A file holding several meshes
  (a scene) is flattened into one mesh with every transform applied. Any other extension
  raises SeedError naming the formats that are supported.
- Up axis. By default STL, 3MF and PLY are Z-up and OBJ, GLB and glTF are Y-up with the
  front facing +Z. ``up`` ("x", "y" or "z") overrides the default. The result always has
  z up and the front facing -y:
      up == "z": (x, y, z) -> (x, y, z)
      up == "y": (x, y, z) -> (x, -z, y)
      up == "x": (x, y, z) -> (y, z, x)
- Scale uniformly so the longest side of the bounding box is exactly ``studs * 8`` mm.
  ``studs`` must be 4..96.
- Place it standing on z = 0 and centred, in x and in y, in the smallest whole number of
  studs that holds it: a model 9.7 studs wide spans x = 0.15 to 9.85 studs, not 0 to 9.7.
  So the bounding box's minimum corner is (sx, sy, 0) with 0 <= sx, sy < 4 mm, and it is
  exactly (0, 0, 0) along any side that is a whole number of studs (within 1e-6 of a stud).
  Centring matters because a model that is symmetric left to right must come out symmetric
  in the grid: the same fraction of a cell at both edges.
- Degenerate (zero-area) triangles are dropped.
- ``piece`` or ``piece_box``: keep only one piece of a file that looks like several separate
  pieces (``bricksnap.pieces.keep_piece``, whose contract says how a piece is found and
  which errors it raises), before turning, scaling and centring, so the piece comes out
  exactly as a file holding only that piece would. Both None: the whole file.
- ``load_mesh(path, up=None) -> (vertices, faces, face colours or None, name, axis)``: the
  file read, flattened and cleaned (every check above except the flat model), not yet
  turned or scaled, with the up axis to turn it by. ``load_seed`` and ``bricksnap.pieces``
  both start from it.
- ``face_colors`` is an (m, 3) uint8 RGB array when the model carries colour: per-face
  colours, per-vertex colours (a face takes the mean of its corners), a texture (sampled at
  each face's UV centroid), or a base colour per material. It is None when the file has no
  colour information (do not return trimesh's default grey as if it were a colour).
- Raises SeedError, with a message a non-programmer can act on, when: the file is missing,
  unreadable or corrupt; it contains no triangles; any coordinate is NaN or infinite; or the
  model has zero size along any axis (a flat model cannot be built from bricks; the
  prototype hung forever on exactly this input, so there must be a test for it).

Implementation notes
--------------------
- Files are read with ``process=False`` so trimesh does not merge, drop or reorder anything
  behind our back; the clean-up (NaN check, degenerate triangles, unused vertices) is done
  here. A triangle counts as degenerate when its area is below ``1e-12`` times the square of
  the model's largest bounding-box side (so it works at any unit scale).
- Placing: the model is moved to start at (0, 0, 0) and scaled, then moved along x and y
  by half of (the next whole number of studs minus its side), unless the side is within
  1e-6 of a stud of a whole number of studs. z is never moved: the model stands on z = 0.
- Scenes are flattened node by node through ``scene.graph.nodes_geometry``, so a mesh used by
  several nodes appears once per node. Non-triangle geometry (point clouds, lines) is ignored.
- A node whose transform mirrors (negative determinant) has its triangles' order of corners
  reversed, so a mirrored copy still faces outward (voxelize relies on the winding).
- Colour, per mesh:
  1. glTF (a PBR material): base colour = the texture pixel under each face's mean UV (UVs
     outside 0..1 wrap, as glTF's default "repeat" does), else white; times
     ``baseColorFactor``; times the face's mean ``COLOR_0`` vertex colour. The product is
     taken in linear light and converted to sRGB as a viewer shows it (texture pixels are
     sRGB, factor and vertex colours linear, by the glTF specification). A white factor and
     white vertex colours leave a texture's pixels exactly as they are. With no texture,
     no factor and no vertex colours the mesh has no colour.
  2. OBJ/MTL (a simple material): the texture (``map_Kd``) when it loads, else the diffuse
     colour ``Kd`` as written. A ``Kd`` next to a texture is ignored: in practice it is an
     exporter default (trimesh writes grey 102, Blender's OBJ exporter writes 0.8), not a
     tint the author chose. A material with no ``Kd`` and no texture has no colour.
  3. Explicit per-face or per-vertex colours (PLY, OBJ vertex colours, glTF ``COLOR_0``
     without a material). glTF vertex colours are linear and are converted to sRGB; other
     formats' vertex colours are used as written.
  4. 3MF: trimesh drops 3MF colours, so ``3D/3dmodel.model`` is read again for its
     ``basematerials`` (display colours) and ``colorgroup`` resources and each triangle's
     ``pid``/``p1``/``p2``/``p3`` (falling back to the object's ``pid``/``pindex``). A face
     takes the mean of its corners' colours. The colours are matched to trimesh's meshes by
     identical vertices and faces. References to missing groups or indices are ignored.
  trimesh's own fallbacks are never taken for colour: the 2 x 2 placeholder image of grey
  (100, 100, 100) it gives UVs that have no image (and writes out when exporting them), and
  its default grey 102 when that sits next to the placeholder or no ``Kd`` was written.
  Alpha is ignored.
- When some meshes of a scene have colour and others do not, the uncoloured ones get the RGB
  of the catalogue's default colour (``DEFAULT_COLOUR``) so the array covers every face.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from bricksnap.types import DEFAULT_COLOUR, STUD_MM, Seed, SeedError

SUPPORTED = (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply")
MIN_STUDS, MAX_STUDS = 4, 96

_Z_UP = (".stl", ".3mf", ".ply")
_GLTF = (".glb", ".gltf")
_AXIS_WORDS = ("side to side", "front to back", "top to bottom")
_DEGENERATE_REL = 1e-12
_FLAT_REL = 1e-9
_WHOLE_STUD = 1e-6  # studs; a side this close to a whole number of studs is not centred

Mesh = tuple[np.ndarray, np.ndarray, np.ndarray | None]  # vertices, faces, face colours


def load_seed(
    path: str | Path,
    *,
    studs: int,
    up: str | None = None,
    piece: int | None = None,
    piece_box: Any = None,
) -> Seed:
    """Load a model file as a Seed: z up, front facing -y, longest side ``studs * 8`` mm.

    With ``piece`` (1, 2, ...) or ``piece_box`` only that piece of the file is kept
    (``bricksnap.pieces.keep_piece``)."""
    studs = _check_studs(studs)
    vertices, faces, colours, name, axis = load_mesh(path, up)
    if piece is not None or piece_box is not None:
        from bricksnap.pieces import keep_piece

        vertices, faces, colours = keep_piece(
            vertices, faces, colours, axis, name, piece=piece, box=piece_box
        )

    vertices = _orient(vertices, axis)
    extent = vertices.max(axis=0) - vertices.min(axis=0)
    longest = float(extent.max())
    thin = [i for i in range(3) if extent[i] <= _FLAT_REL * longest]
    if thin:
        which = " or ".join(_AXIS_WORDS[i] for i in thin)
        raise SeedError(
            f"The model in {name} is flat: it has no thickness from {which}, so it cannot be "
            "built from bricks. Give it some thickness in your 3D program, or check that "
            "the file holds the whole model, and try again."
        )

    scale = studs * STUD_MM / longest
    vertices = (vertices - vertices.min(axis=0)) * scale
    vertices = np.maximum(vertices, 0.0)  # remove -0.0 and rounding below zero
    vertices[:, :2] += _centring(vertices.max(axis=0)[:2])
    return Seed(vertices=vertices, faces=faces, face_colors=colours, source=name)


def load_mesh(
    path: str | Path, up: str | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, str, str]:
    """The file's triangles, read, flattened and cleaned but not yet oriented or scaled:
    (vertices, faces, face colours or None, the file's name, the up axis to orient by).
    Raises SeedError for every problem ``load_seed`` names, except a flat model."""
    path = Path(path)
    name = path.name or str(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        kinds = ", ".join(e.lstrip(".").upper() for e in SUPPORTED)
        shown = f"'{path.suffix}' files" if path.suffix else "files without an extension"
        raise SeedError(
            f"BrickSnap cannot open {shown} ({name}). Please use one of these 3D model "
            f"formats: {kinds}."
        )
    axis = _check_up(up, ext)
    if not path.exists():
        raise SeedError(f"Could not find the file {name}. Check the name and the folder.")
    if not path.is_file():
        raise SeedError(f"{name} is a folder, not a 3D model file.")

    loaded = _read(path, ext, name)
    known = _threemf_colours(path, loaded) if ext == ".3mf" else {}
    vertices, faces, colours = _flatten(loaded, ext, known)

    if len(faces) == 0:
        raise SeedError(
            f"{name} contains no triangles, so there is no shape to build. It may be empty, "
            "or hold only points or lines. Export the model as a solid mesh and try again."
        )
    if not np.isfinite(vertices).all():
        raise SeedError(
            f"{name} is damaged: some of its points have no valid position. Try repairing "
            "or re-exporting the model in your 3D program."
        )

    vertices, faces, colours = _drop_degenerate(vertices, faces, colours)
    if len(faces) == 0:
        raise SeedError(
            f"{name} contains no usable triangles: every triangle in it has zero area. "
            "Export the model as a solid mesh and try again."
        )
    return vertices, faces, colours, name, axis


# ---- argument checks ------------------------------------------------------------------------


def _check_studs(studs: Any) -> int:
    if isinstance(studs, bool) or not isinstance(studs, int | np.integer):
        raise SeedError(
            f"The size must be a whole number of studs between {MIN_STUDS} and {MAX_STUDS}, "
            f"not {studs!r}."
        )
    if not MIN_STUDS <= int(studs) <= MAX_STUDS:
        raise SeedError(
            f"The size must be between {MIN_STUDS} and {MAX_STUDS} studs (you asked for "
            f"{int(studs)}). One stud is 8 mm, so that is {MIN_STUDS * 8} mm to "
            f"{MAX_STUDS * 8} mm along the longest side."
        )
    return int(studs)


def _check_up(up: str | None, ext: str) -> str:
    if up is None:
        return "z" if ext in _Z_UP else "y"
    axis = str(up).strip().lower()
    if axis not in ("x", "y", "z"):
        raise SeedError(f"The up direction must be x, y or z, not {up!r}.")
    return axis


# ---- reading --------------------------------------------------------------------------------


def _read(path: Path, ext: str, name: str) -> Any:
    import trimesh  # imported here: it is slow to import and only this step needs it

    try:
        return trimesh.load(str(path), file_type=ext.lstrip("."), process=False)
    except Exception as exc:  # trimesh raises many kinds of errors for bad files
        raise SeedError(
            f"Could not read {name}. The file may be damaged, or it may not really be a "
            f"{ext.lstrip('.').upper()} file. Try exporting it again from your 3D program."
        ) from exc


def _flatten(loaded: Any, ext: str, known: dict[int, np.ndarray] | None = None) -> Mesh:
    """One (vertices, faces, face colours) from a Trimesh or a Scene, transforms applied.

    ``known`` maps ``id(mesh)`` to face colours found outside trimesh (3MF)."""
    import trimesh

    known = known or {}

    def colours_of(geom: Any) -> np.ndarray | None:
        return known[id(geom)] if id(geom) in known else _colours(geom, ext)

    meshes: list[Mesh] = []
    if isinstance(loaded, trimesh.Scene):
        for node in loaded.graph.nodes_geometry:
            transform, geom_name = loaded.graph[node]
            geom = loaded.geometry.get(geom_name)
            if not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                continue
            verts = np.asarray(geom.vertices, dtype=np.float64)
            faces = np.asarray(geom.faces, dtype=np.int64)
            matrix = np.asarray(transform, dtype=np.float64)
            verts = verts @ matrix[:3, :3].T + matrix[:3, 3]
            if np.linalg.det(matrix[:3, :3]) < 0:  # a mirror turns the mesh inside out
                faces = faces[:, ::-1]
            meshes.append((verts, faces, colours_of(geom)))
    elif isinstance(loaded, trimesh.Trimesh) and len(loaded.faces) > 0:
        meshes.append(
            (
                np.asarray(loaded.vertices, dtype=np.float64),
                np.asarray(loaded.faces, dtype=np.int64),
                colours_of(loaded),
            )
        )
    if not meshes:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), None

    vertices, faces, colours = [], [], []
    offset = 0
    any_colour = any(c is not None for _, _, c in meshes)
    fallback = np.asarray(_default_rgb(), dtype=np.uint8) if any_colour else None
    for verts, fcs, cols in meshes:
        vertices.append(verts)
        faces.append(fcs + offset)
        offset += len(verts)
        if fallback is not None:
            colours.append(cols if cols is not None else np.tile(fallback, (len(fcs), 1)))
    return (
        np.concatenate(vertices, axis=0),
        np.concatenate(faces, axis=0),
        np.concatenate(colours, axis=0) if colours else None,
    )


def _default_rgb() -> tuple[int, int, int]:
    from bricksnap.catalog import load_catalog

    colour = load_catalog().colours.get(DEFAULT_COLOUR)
    return colour.rgb if colour is not None else (160, 165, 169)


# ---- colour ---------------------------------------------------------------------------------

_PLACEHOLDER_RGB = (100, 100, 100)  # trimesh's 2 x 2 stand-in image for UVs with no image
_TRIMESH_GREY = (102, 102, 102)  # trimesh's default material colour


def _srgb_from_linear(values: np.ndarray) -> np.ndarray:
    """Linear 0..1 to sRGB 0..255 (uint8)."""
    v = np.clip(values, 0.0, 1.0)
    s = np.where(v <= 0.0031308, 12.92 * v, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    return np.clip(np.round(s * 255.0), 0, 255).astype(np.uint8)


def _linear_from_srgb(rgb: np.ndarray) -> np.ndarray:
    """sRGB 0..255 to linear 0..1."""
    s = np.asarray(rgb, dtype=np.float64) / 255.0
    return np.where(s <= 0.04045, s / 12.92, np.power((s + 0.055) / 1.055, 2.4))


def _colours(mesh: Any, ext: str) -> np.ndarray | None:
    """(m, 3) uint8 RGB for one mesh's faces, or None when it carries no colour."""
    visual = getattr(mesh, "visual", None)
    if visual is None:
        return None
    n_faces = len(mesh.faces)
    kind = getattr(visual, "kind", None)
    if kind == "texture":
        return _material_colours(mesh, visual, n_faces)
    if kind == "face":
        rgb = np.asarray(visual.face_colors)[:, :3]
        return rgb.astype(np.uint8) if len(rgb) == n_faces else None
    if kind == "vertex":
        mean = _mean_vertex_colour(mesh, visual.vertex_colors)
        if mean is None:
            return None
        if ext in _GLTF:
            return _srgb_from_linear(mean / 255.0)
        return np.clip(np.round(mean), 0, 255).astype(np.uint8)
    return None


def _mean_vertex_colour(mesh: Any, colours: Any) -> np.ndarray | None:
    """The mean of each face's corner colours (RGB, 0..255 floats), or None."""
    if colours is None:
        return None
    vc = np.asarray(colours)
    if vc.ndim != 2 or vc.shape[1] < 3 or len(vc) != len(mesh.vertices):
        return None
    if np.issubdtype(vc.dtype, np.floating) and vc[:, :3].max(initial=0.0) <= 1.0:
        vc = vc * 255.0  # some loaders keep float colours in 0..1
    return vc[:, :3].astype(np.float64)[np.asarray(mesh.faces)].mean(axis=1)


def _is_placeholder(image: Any) -> bool:
    try:
        if tuple(image.size) != (2, 2):
            return False
        return bool((np.asarray(image.convert("RGB")) == _PLACEHOLDER_RGB).all())
    except Exception:  # not an image we can read: not the placeholder either
        return False


def _material_colours(mesh: Any, visual: Any, n_faces: int) -> np.ndarray | None:
    material = getattr(visual, "material", None)
    uv = getattr(visual, "uv", None)
    has_uv = uv is not None and len(uv) == len(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if material is not None and hasattr(material, "baseColorFactor"):
        return _pbr_colours(mesh, visual, material, uv if has_uv else None, faces)
    if material is None:
        return None

    # OBJ / MTL: texture, else the diffuse colour Kd as written
    image = getattr(material, "image", None)
    placeholder = image is not None and _is_placeholder(image)
    if image is not None and not placeholder and has_uv:
        return _sample_texture(image, np.asarray(uv, dtype=np.float64), faces)
    diffuse = getattr(material, "diffuse", None)
    if diffuse is None:
        return None
    rgb = np.clip(np.round(np.asarray(diffuse, dtype=np.float64).ravel()[:3]), 0, 255)
    is_default = tuple(int(v) for v in rgb) == _TRIMESH_GREY
    written = "kd" in (getattr(material, "kwargs", None) or {})
    if is_default and (placeholder or not written):
        return None  # trimesh's fallback grey, not a colour the file holds
    return np.tile(rgb.astype(np.uint8), (n_faces, 1))


def _pbr_colours(
    mesh: Any, visual: Any, material: Any, uv: Any, faces: np.ndarray
) -> np.ndarray | None:
    """glTF: texture (or white) x baseColorFactor x COLOR_0, in linear light, as sRGB."""
    image = getattr(material, "baseColorTexture", None)
    placeholder = image is not None and _is_placeholder(image)
    texture = None
    if image is not None and not placeholder and uv is not None:
        texture = _sample_texture(image, np.asarray(uv, dtype=np.float64), faces)

    factor = getattr(material, "baseColorFactor", None)
    tint = None
    if factor is not None:  # linear RGB(A), 0..255 in trimesh
        tint = np.asarray(factor, dtype=np.float64).ravel()[:3] / 255.0
        if placeholder and texture is None and tuple(np.round(tint * 255)) == _TRIMESH_GREY:
            tint = None  # trimesh's placeholder material, written out as it was
    attributes = getattr(visual, "vertex_attributes", None) or {}
    vertex = _mean_vertex_colour(mesh, attributes.get("color"))
    if vertex is not None:
        vertex = vertex / 255.0
        tint = vertex if tint is None else tint[None, :] * vertex

    if texture is None and tint is None:
        return None  # a material with no texture and no colour of its own
    n_faces = len(faces)
    multiplier = np.broadcast_to(np.ones(3) if tint is None else tint, (n_faces, 3))
    if texture is None:
        return _srgb_from_linear(multiplier)
    tinted = _srgb_from_linear(_linear_from_srgb(texture) * multiplier)
    untouched = (multiplier == 1.0).all(axis=1)  # keep white-tinted pixels bit for bit
    return np.where(untouched[:, None], texture, tinted)


def _sample_texture(image: Any, uv: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """The texture pixel under each face's mean UV (v points up, as trimesh stores it)."""
    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = pixels.shape[:2]
    centre = uv[faces].mean(axis=1)
    centre = np.where(np.isfinite(centre), centre, 0.0)
    inside = (centre >= 0.0) & (centre <= 1.0)
    centre = np.where(inside, centre, np.mod(centre, 1.0))
    px = np.clip(np.floor(centre[:, 0] * width), 0, width - 1).astype(np.int64)
    py = np.clip(np.floor((1.0 - centre[:, 1]) * height), 0, height - 1).astype(np.int64)
    return pixels[py, px].copy()


# ---- 3MF colours ----------------------------------------------------------------------------


def _threemf_colours(path: Path, loaded: Any) -> dict[int, np.ndarray]:
    """Face colours of a 3MF's meshes, keyed by ``id(mesh)`` of trimesh's meshes."""
    import trimesh

    try:
        objects = _read_3mf_colours(path)
    except Exception:  # colour is optional; trimesh has already read the shape
        return {}
    if not objects:
        return {}
    if isinstance(loaded, trimesh.Scene):
        meshes = [
            (name, g) for name, g in loaded.geometry.items() if isinstance(g, trimesh.Trimesh)
        ]
    elif isinstance(loaded, trimesh.Trimesh):
        meshes = [(None, loaded)]
    else:
        return {}
    found: dict[int, np.ndarray] = {}
    for name, geom in meshes:
        verts = np.asarray(geom.vertices, dtype=np.float64)
        faces = np.asarray(geom.faces, dtype=np.int64)
        matches = [
            o
            for o in objects
            if o[2].shape == faces.shape
            and o[1].shape == verts.shape
            and np.array_equal(o[2], faces)
            and np.allclose(o[1], verts, rtol=1e-12, atol=0.0)
        ]
        named = [o for o in matches if o[0] == name]
        if named:
            colours = named[0][3]
        elif matches and all(_same(o[3], matches[0][3]) for o in matches):
            colours = matches[0][3]
        else:
            continue  # no match, or identical shapes with different colours: unsure
        if colours is not None:
            found[id(geom)] = colours
    return found


def _same(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and np.array_equal(a, b))


def _read_3mf_colours(
    path: Path,
) -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray | None]]:
    """(name, vertices, faces, face RGB or None) of every mesh object in a 3MF file, or an
    empty list when the file has no colour resources."""
    import zipfile
    from xml.etree import ElementTree  # expat: no external entities, expansion limited

    with zipfile.ZipFile(path) as archive:
        model = next((n for n in archive.namelist() if "3d/3dmodel.model" in n.lower()), None)
        if model is None:
            return []
        data = archive.read(model)
    if b"basematerials" not in data and b"colorgroup" not in data:
        return []
    root = ElementTree.fromstring(data)

    groups: dict[str, np.ndarray] = {}
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local not in ("basematerials", "colorgroup"):
            continue
        is_base = local == "basematerials"
        child, attribute = ("base", "displaycolor") if is_base else ("color", "color")
        colours = [_hex_rgb(c.get(attribute, "")) for c in element.iterfind(f".//{{*}}{child}")]
        groups[element.get("id", "")] = np.asarray(colours, dtype=np.float64).reshape(-1, 3)

    objects = []
    names: set[str] = set()
    for obj in root.iterfind(".//{*}object"):
        name = obj.get("name", obj.get("id", ""))  # as trimesh names its meshes
        mesh = obj.find("{*}mesh")
        if mesh is None:
            continue
        verts = [
            (float(v.get("x", 0)), float(v.get("y", 0)), float(v.get("z", 0)))
            for v in mesh.iterfind(".//{*}vertex")
        ]
        rows = [t.attrib for t in mesh.iterfind(".//{*}triangle")]
        faces = np.asarray(
            [(int(t["v1"]), int(t["v2"]), int(t["v3"])) for t in rows], dtype=np.int64
        ).reshape(-1, 3)
        rgb = _triangle_colours(rows, obj.get("pid"), obj.get("pindex"), groups)
        unique_name = name if name not in names else ""  # trimesh renames repeated names
        objects.append((unique_name, np.asarray(verts).reshape(-1, 3), faces, rgb))
        names.add(name)
    if all(o[3] is None for o in objects):
        return []
    return objects


def _triangle_colours(
    rows: list[Any], object_pid: str | None, object_index: str | None, groups: dict
) -> np.ndarray | None:
    """Mean corner colour of each triangle (uint8), or None when no triangle has one."""
    fallback = np.asarray(_default_rgb(), dtype=np.float64)
    out = np.tile(fallback, (len(rows), 1))
    any_colour = False
    for i, t in enumerate(rows):
        pid = t.get("pid", object_pid)
        group = groups.get(pid) if pid is not None else None
        if group is None or len(group) == 0:
            continue
        first = t.get("p1", object_index if "pid" not in t else None)
        if first is None:
            continue
        try:
            corners = [int(first), int(t.get("p2", first)), int(t.get("p3", first))]
        except ValueError:
            continue
        if min(corners) < 0 or max(corners) >= len(group):
            continue
        out[i] = group[corners].mean(axis=0)
        any_colour = True
    if not any_colour:
        return None
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def _hex_rgb(text: str) -> tuple[int, int, int]:
    """'#RRGGBB' or '#RRGGBBAA' to (r, g, b)."""
    t = text.strip().lstrip("#")
    if len(t) not in (6, 8):
        raise ValueError(f"not a colour: {text!r}")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)


# ---- geometry clean-up ----------------------------------------------------------------------


def _drop_degenerate(vertices: np.ndarray, faces: np.ndarray, colours: np.ndarray | None) -> Mesh:
    """Drop zero-area and out-of-range triangles, then vertices no triangle uses."""
    valid = ((faces >= 0) & (faces < len(vertices))).all(axis=1)
    faces = faces[valid]
    if colours is not None:
        colours = colours[valid]
    if len(faces) == 0:
        return vertices[:0], faces, None if colours is None else colours[:0]
    used = vertices[np.unique(faces)]
    size = float((used.max(axis=0) - used.min(axis=0)).max())
    tri = vertices[faces]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    keep = area2 > 2.0 * _DEGENERATE_REL * size * size
    faces = faces[keep]
    if colours is not None:
        colours = colours[keep]
    unique, inverse = np.unique(faces, return_inverse=True)
    return vertices[unique], inverse.reshape(faces.shape).astype(np.int64), colours


def _centring(extent_mm: np.ndarray) -> np.ndarray:
    """How far (mm) to move a model starting at 0 so it is centred in whole studs, per axis.

    0 along a side within ``_WHOLE_STUD`` of a whole number of studs; otherwise half the
    slack between the side and the next whole number of studs (always under half a stud)."""
    studs = np.asarray(extent_mm, dtype=np.float64) / STUD_MM
    whole = np.abs(studs - np.round(studs)) <= _WHOLE_STUD
    slack = (np.ceil(studs) - studs) * STUD_MM / 2.0
    return np.where(whole, 0.0, slack)


def _orient(vertices: np.ndarray, axis: str) -> np.ndarray:
    x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
    if axis == "y":
        out = np.stack([x, -z, y], axis=1)
    elif axis == "x":
        out = np.stack([y, z, x], axis=1)
    else:
        out = np.stack([x, y, z], axis=1)
    return out + 0.0  # turn any -0.0 into 0.0
