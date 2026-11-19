// BrickSnap 3D viewer. Plain ES module, no build step. Served by bricksnap/viewserver.py.
//
// Reads /project/project.json, /project/build.json (Build.to_json in bricksnap/types.py),
// /catalog/parts.json and /catalog/colours.json, and draws every part by its catalogue kind:
// slopes as wedges, round parts as cylinders, cones tapering, everything else as a box; studs
// wherever the catalogue says. Each shape is one shared unit geometry, scaled, turned and
// moved per part with instancing, so a build of thousands of parts stays quick.
// Grid conventions (docs/ARCHITECTURE.md): a cell is 8 x 8 x 3.2 mm, x right, y back, z up.
// Footprints, stud positions and slope directions follow bricksnap/catalog/__init__.py
// (footprint, local_to_cell, low_side and the rotation table there).
//
// Before and after: when the project keeps a plain conversion (/project/build.rough.json, which
// /project-files.json says exists) that differs from build.json, the page shows two views,
// "Plain conversion" and "Designed", side by side (one above the other on a narrow screen).
// They are two rectangles of one canvas, drawn by one renderer with one camera and one set of
// lights, ground and grid: each view's model is its own group, shown only while its rectangle
// is drawn. So turning either view turns both, and geometry and materials are shared. The step
// slider acts on the designed build. project.json's brief is shown in a panel beside them.
//
// Versions (bricksnap/versions.py): when /project-files.json lists versions, two choosers say
// what each view shows. The left view ("rough" in the code) shows the plain conversion or any
// version, the right view ("designed") any version; the current version is drawn from
// build.json itself, so it follows a rebuild live. The step slider, the header, the brief and
// the right-hand title follow the right view. Without versions the page is as before.
//
// Look inside: a clipping plane on the model's materials (never the ground or grid) cuts both
// views open along one axis; at 0 nothing is cut.
//
// Any text that comes from the files goes into the page with textContent, never innerHTML.
//
// A part with "face" (front, right, back or left; absent means "top") lies on its side, as
// bricksnap/ldraw.py places it: it keeps clear the column of three cells at its (x, y, z),
// its bottom against the back of that column (the face of the brick behind it), its centre on
// that brick's side stud (5.6 mm above the column's bottom), its top pointing out of the face.
// It has no stud on top; a round plate's stud points outwards.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const CELL = { x: 8, y: 8, z: 3.2 }; // millimetres
const GAP = 0.4; // mm left between neighbouring parts so each one stands out
const GAP_Z = 0.2;
const STUD_R = 2.4; // stud diameter 4.8 mm
const STUD_H = 1.7;
const LIP_MM = 1.6; // the low edge of a real slope brick stands 4 LDU (1.6 mm) tall
const ROUND_SEGMENTS = 32; // a multiple of 4, so a round part touches its cells' sides
const CONE_TOP = 0.68; // a cone's top diameter, as a share of its base (a stud fits on it)
const DISH_BOTTOM = 0.55; // a dish's foot diameter, as a share of its rim
const CURVE_STEPS = 10; // straight pieces in a curved slope's profile
const FALLBACK_RGB = '#9BA19D';
const OUTLINE_MM = 0.7; // thickness of the highlight around the current step's parts
const HIGHLIGHT = '#ff3d7f';
const POLL_MS = 2000;
const SKY_HAZE = 0xdcecf8; // close to the page's sky gradient near the horizon
const FIT_MARGIN = 0.88; // the framed model reaches this far towards the view's edges (NDC)
const BOX_MARGIN = 0.99; // and the box around it (often empty at its corners) inside the view
const VIEW_DIR = new THREE.Vector3(0.55, -1, 0.7).normalize(); // from the model to the camera
// A part lying on a face: the grid direction its top points to (types.FACE_OUT), and how high
// above the bottom of its column the side stud it sits on is (10 LDU below a brick's top).
const FACE_OUT = { front: [0, -1], right: [1, 0], back: [0, 1], left: [-1, 0] };
const SIDE_STUD_MM = 3 * CELL.z - 10 * 0.4;

// low_side in the part's own axes -> (x, z) direction in those axes
const SIDES = { '+x': [1, 0], '-x': [-1, 0], '+z': [0, 1], '-z': [0, -1] };
const SLOPE_KINDS = new Set(['slope', 'curved_slope', 'slope_inverted']);
const ROUND_KINDS = new Set(['round_brick', 'round_plate', 'round_tile']);

const $ = (id) => document.getElementById(id);

// Where the project's files are. ``bricksnap view`` serves them under /project/; the web app
// (bricksnap/webapp.py) serves this page for one of many projects and says where in <body>.
const PROJECT_URL = document.body.dataset.projectFiles || '/project';
const FILES_LIST_URL = document.body.dataset.projectList || '/project-files.json';

// ---- state exposed to tests --------------------------------------------------------------

const state = {
  ready: false,
  partCount: 0,
  visibleCount: 0,
  step: 0, // the step being shown; equal to maxStep when showing everything
  maxStep: 0,
  showingAll: true,
  highlightCount: 0, // parts outlined as new in the current step
  buildVersion: 0, // goes up each time a new build.json is drawn
  roughVersion: 0, // goes up each time build.rough.json changes (drawn, or gone)
  notes: [], // the build's notes as shown under the verdict
  brief: null, // the designer's brief as shown, or null when there is none
  error: null,
  versions: [], // the project's versions, as /project-files.json lists them (oldest first)
  current: null, // the current version's number, or null
  choice: { left: null, right: null }, // what each view draws: 'rough', a version number, or null
};
window.__bricksnap = state;

// ---- three.js scene ---------------------------------------------------------------------

const container = $('view');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.localClippingEnabled = true; // "look inside" clips the model's materials only
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(40, 1, 1, 20000);
camera.up.set(0, 0, 1); // z is up
camera.position.set(150, -250, 180);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = false;
controls.screenSpacePanning = true;
controls.addEventListener('change', requestRender);
let userMoved = false; // the person has turned, zoomed or moved the view since it was framed
controls.addEventListener('start', () => {
  userMoved = true;
});

const hemi = new THREE.HemisphereLight(0xffffff, 0xb8a888, 1.6);
hemi.position.set(0, 0, 1); // sky above (z up)
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0005;
sun.shadow.normalBias = 0.4;
scene.add(sun);
scene.add(sun.target);

const fill = new THREE.DirectionalLight(0xffffff, 0.6);
scene.add(fill);
scene.add(fill.target);

const groundMat = new THREE.MeshLambertMaterial({ color: 0xe9e4d4 });
const ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), groundMat);
ground.receiveShadow = true;
scene.add(ground);
let grid = null;

// Shared unit geometries: every instance is a scaled, turned and moved copy.
const studGeo = new THREE.CylinderGeometry(STUD_R, STUD_R, STUD_H, 20);
studGeo.rotateX(Math.PI / 2); // cylinder axis along z

// Materials, shared by both views and every rebuild: one per colour (made on first use), and
// one each for the edge lines, the current step's edge lines and its outline.
const materialCache = new Map(); // LDraw colour code -> material
const edgeMat = new THREE.LineBasicMaterial({ color: 0x1b1b1b, transparent: true, opacity: 0.45 });
const newEdgeMat = new THREE.LineBasicMaterial({ color: HIGHLIGHT });
const outlineMat = new THREE.MeshBasicMaterial({ color: HIGHLIGHT, side: THREE.BackSide });

// The two views. Each draws its build into its own group; both groups sit at the same place
// on the same grid, and only the group of the view being drawn is visible.
const FRAME_PX = 3; // the border drawn round each view when both builds are shown
function makeView(name, label) {
  const group = new THREE.Group();
  scene.add(group);
  return {
    name,
    label,
    group,
    drawn: null, // see drawBuild
    partsJson: null, // the build's "parts" as JSON text, to tell whether the two builds differ
    pane: $(`pane-${name}`),
    count: $(`${name}Count`),
    rect: null, // where it is drawn, in CSS pixels from the canvas's top left; null: all of it
    lastRender: null, // the camera it was last drawn with (see renderViews)
  };
}
const views = { rough: makeView('rough', 'Plain conversion'), designed: makeView('designed', 'Designed') };
let compareActive = false; // both builds are there and differ: two views
let show = 'both'; // which of them the person chose to see: 'both', 'rough' or 'designed'

/** The views drawn now, left to right (or top to bottom). */
function shownViews() {
  if (!compareActive || show === 'designed') return [views.designed];
  if (show === 'rough') return [views.rough];
  return [views.rough, views.designed];
}

let fitted = null; // {box, portrait}: what placeCamera last framed (see fitView)
let renderQueued = false;
function requestRender() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    renderViews();
  });
}

// What each renderer.render call of the last frame drew, recorded by the scene itself as the
// call ends (so every call counts, wherever it comes from): which views' groups were
// visible, the canvas area and scissor box used, the camera and its shape, and the draw
// calls and triangles it took (shadows included). See state.inspect's ``frame``.
renderer.info.autoReset = false; // renderViews resets the counts once per frame
let frame = [];
const counted = { calls: 0, triangles: 0 };
scene.onAfterRender = (r, s, cam) => {
  const info = r.info.render;
  const viewport = r.getViewport(new THREE.Vector4());
  const scissor = r.getScissor(new THREE.Vector4());
  const e = cam.projectionMatrix.elements;
  frame.push({
    groups: Object.values(views)
      .filter((v) => v.group.visible)
      .map((v) => v.name),
    canvas: r.getSize(new THREE.Vector2()).toArray(),
    viewport: viewport.toArray(),
    scissor: r.getScissorTest() ? scissor.toArray() : null,
    aspect: e[5] / e[0],
    camera: cam.uuid,
    calls: info.calls - counted.calls,
    triangles: info.triangles - counted.triangles,
  });
  counted.calls = info.calls;
  counted.triangles = info.triangles;
};

/** Draw each shown view into its rectangle of the canvas, all with the one camera. */
function renderViews() {
  const size = renderer.getSize(new THREE.Vector2());
  const list = shownViews();
  const aspect = camera.aspect;
  renderer.info.reset();
  frame = [];
  counted.calls = 0;
  counted.triangles = 0;
  for (const v of Object.values(views)) v.lastRender = null;
  if (compareActive) {
    renderer.setScissorTest(false);
    renderer.clear(); // nothing stays where a view was before the person hid it
  }
  for (const v of list) {
    for (const w of Object.values(views)) w.group.visible = w === v;
    const r = v.rect;
    if (r) {
      const bottom = size.y - r.y - r.height; // WebGL counts from the bottom
      renderer.setViewport(r.x, bottom, r.width, r.height);
      renderer.setScissor(r.x, bottom, r.width, r.height);
      renderer.setScissorTest(true);
      camera.aspect = r.width / r.height;
      camera.updateProjectionMatrix();
    } else {
      renderer.setScissorTest(false);
      renderer.setViewport(0, 0, size.x, size.y);
    }
    renderer.render(scene, camera);
    v.lastRender = { id: camera.uuid, position: camera.position.toArray(), target: controls.target.toArray() };
  }
  renderer.setScissorTest(false);
  renderer.setViewport(0, 0, size.x, size.y);
  if (camera.aspect !== aspect) {
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
  }
}

/** Where each shown view is drawn: inside its pane's border, in canvas pixels. */
function measurePanes() {
  const c = renderer.domElement.getBoundingClientRect();
  for (const v of Object.values(views)) {
    v.rect = null;
    if (!compareActive || !shownViews().includes(v)) continue;
    const p = v.pane.getBoundingClientRect();
    v.rect = {
      x: p.left - c.left + FRAME_PX,
      y: p.top - c.top + FRAME_PX,
      width: Math.max(1, p.width - 2 * FRAME_PX),
      height: Math.max(1, p.height - 2 * FRAME_PX),
    };
  }
}

/** Fit the canvas, the panes and the camera's shape to the page. ``keepView``: the layout
 * changed because the person picked what to show, so a view they have moved stays put. */
function resize(keepView = false) {
  const w = Math.max(1, container.clientWidth);
  const h = Math.max(1, container.clientHeight);
  renderer.setSize(w, h, false);
  measurePanes();
  const first = shownViews()[0].rect; // the views are the same size
  camera.aspect = first ? first.width / first.height : w / h;
  camera.updateProjectionMatrix();
  // A new shape of view frames the model again, unless the person has moved the view; turning
  // a phone between portrait and landscape always does, as it changes which side limits it
  // (keeping the angle the person turned it to). Picking what to show never moves a view
  // the person has moved, though one view alone is wide and two side by side are tall.
  const portrait = camera.aspect < 1;
  if (fitted && keepView && userMoved) fitted.portrait = portrait;
  else if (fitted && (!userMoved || fitted.portrait !== portrait)) placeCamera(frameDir());
  requestRender();
}
const resizeObserver = new ResizeObserver(() => resize());
for (const el of [container, views.rough.pane, views.designed.pane]) resizeObserver.observe(el);
resize();

// ---- part shapes --------------------------------------------------------------------------
//
// Every shape is a unit geometry filling the cube -0.5..0.5 on each axis, drawn scaled to
// the part's cells. A wedge's slanted face runs down towards local +X; the instance matrix
// turns local +X to the part's low side on the grid.

const shapeCache = new Map(); // key -> {key, type, geo, edges, top, bottom, slant}

/** Unique vertex positions of a geometry whose z is (about) ``z``. */
function ringAt(geo, z) {
  const pos = geo.getAttribute('position');
  const seen = new Map();
  for (let i = 0; i < pos.count; i++) {
    if (Math.abs(pos.getZ(i) - z) > 1e-4) continue;
    const x = pos.getX(i);
    const y = pos.getY(i);
    seen.set(`${x.toFixed(4)},${y.toFixed(4)}`, [x, y, z]);
  }
  return [...seen.values()];
}

/** Sum of the outward normals (weighted by area) of the faces that are neither flat nor upright. */
function slantNormal(geo) {
  const pos = geo.getAttribute('position');
  const index = geo.getIndex();
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  const n = new THREE.Vector3();
  const sum = new THREE.Vector3();
  const count = index ? index.count : pos.count;
  for (let i = 0; i < count; i += 3) {
    const [ia, ib, ic] = index ? [index.getX(i), index.getX(i + 1), index.getX(i + 2)] : [i, i + 1, i + 2];
    a.fromBufferAttribute(pos, ia);
    b.fromBufferAttribute(pos, ib);
    c.fromBufferAttribute(pos, ic);
    n.subVectors(c, b).cross(a.clone().sub(b)); // three.js's own winding: (c - b) x (a - b)
    const len = n.length();
    if (len < 1e-9) continue;
    const nz = Math.abs(n.z / len);
    if (nz > 0.05 && nz < 0.995) sum.add(n);
  }
  return sum.lengthSq() > 1e-12 ? sum : null;
}

/** A prism: the polygon ``profile`` ([x, z] points, counter-clockwise) swept along y. */
function prismGeometry(profile) {
  const pts = profile.filter((p, i) => {
    const q = profile[(i + 1) % profile.length];
    return Math.hypot(p[0] - q[0], p[1] - q[1]) > 1e-6;
  });
  const v = [];
  const tri = (p, q, r) => v.push(...p, ...q, ...r);
  const at = (p, y) => [p[0], y, p[1]];
  for (let i = 1; i + 1 < pts.length; i++) {
    tri(at(pts[0], -0.5), at(pts[i], -0.5), at(pts[i + 1], -0.5)); // faces -y
    tri(at(pts[0], 0.5), at(pts[i + 1], 0.5), at(pts[i], 0.5)); // faces +y
  }
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const q = pts[(i + 1) % pts.length];
    tri(at(p, -0.5), at(q, 0.5), at(q, -0.5));
    tri(at(p, -0.5), at(p, 0.5), at(q, 0.5));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
  geo.computeVertexNormals(); // not indexed, so every face keeps its own flat normal
  return geo;
}

/** The wedge profile in the x-z plane; ``s`` is the slanted share of the length, ``lip``
 * the low edge's share of the height. */
function wedgeProfile(type, s, lip) {
  const lo = -0.5;
  const hi = 0.5;
  if (type === 'inverted') {
    // upside down: flat top, the underside cut away towards -x and running down to +x
    return [[lo, hi - lip], [lo + s, lo], [hi, lo], [hi, hi], [lo, hi]];
  }
  const profile = [[lo, lo], [hi, lo], [hi, lo + lip]];
  if (type === 'curved') {
    // gentle near the top, steeper towards the lip, like the real curved slope
    const c = 0.35;
    for (let i = 1; i < CURVE_STEPS; i++) {
      const t = 1 - i / CURVE_STEPS;
      profile.push([hi - s + s * t, hi - (1 - lip) * (c * t + (1 - c) * t * t)]);
    }
  }
  profile.push([hi - s, hi], [lo, hi]);
  return profile;
}

function makeShapeGeometry(shape) {
  switch (shape.type) {
    case 'wedge':
    case 'curved':
    case 'inverted':
      return prismGeometry(wedgeProfile(shape.type, shape.s, shape.lip));
    case 'cylinder':
    case 'cone':
    case 'dish': {
      const top = shape.type === 'cone' ? CONE_TOP : 1;
      const bottom = shape.type === 'dish' ? DISH_BOTTOM : 1;
      const geo = new THREE.CylinderGeometry(0.5 * top, 0.5 * bottom, 1, ROUND_SEGMENTS);
      geo.rotateX(Math.PI / 2); // axis along z, top at +z
      return geo;
    }
    default:
      return new THREE.BoxGeometry(1, 1, 1);
  }
}

/** The shared geometry, edge lines and measurements for a shape, made once. */
function shapeGeometry(shape) {
  let g = shapeCache.get(shape.key);
  if (g) return g;
  const geo = makeShapeGeometry(shape);
  const edgeGeo = new THREE.EdgesGeometry(geo, 25);
  g = {
    key: shape.key,
    type: shape.type,
    s: shape.s ?? null, // a wedge's slanted share of its length
    geo,
    edges: edgeGeo.getAttribute('position').array.slice(),
    top: ringAt(geo, 0.5),
    bottom: ringAt(geo, -0.5),
    slant: shape.dir ? slantNormal(geo) : null,
  };
  edgeGeo.dispose();
  shapeCache.set(shape.key, g);
  return g;
}

/** How a catalogue part is drawn: {key, type, ...}. */
function shapeFor(part) {
  if (SLOPE_KINDS.has(part.kind) && part.lowSide) {
    const [lx, lz] = SIDES[part.lowSide];
    const along = lx !== 0 ? 0 : 1; // which own axis the slope runs along
    const length = along === 0 ? part.sx : part.sz;
    const heightMm = part.h * CELL.z;
    const inverted = part.kind === 'slope_inverted';
    // Full height over the rows with studs, slanted over the rest; upside down, it stands on
    // the rows the catalogue says take studs from below (bottom_cells), cut away over the rest.
    const rows = new Set((inverted ? part.bottomCells : part.studs).map((c) => c[along]));
    let slanted = length - rows.size;
    if (slanted <= 0 || (inverted && rows.size === 0)) {
      // nothing to go by (no data, or studs on every row): use the slope's angle
      const angle = THREE.MathUtils.clamp(part.angle, 5, 85);
      slanted = Math.round((heightMm - LIP_MM) / Math.tan(THREE.MathUtils.degToRad(angle)) / CELL.x);
    }
    const s = THREE.MathUtils.clamp(slanted, 1, length) / length;
    const lip = Math.min(0.5, LIP_MM / heightMm);
    const type = inverted ? 'inverted' : part.kind === 'curved_slope' ? 'curved' : 'wedge';
    return { key: `${type}:${s.toFixed(4)}:${lip.toFixed(4)}`, type, s, lip, dir: [lx, lz] };
  }
  if (ROUND_KINDS.has(part.kind)) return { key: 'cylinder', type: 'cylinder' };
  if (part.kind === 'cone') return { key: 'cone', type: 'cone' };
  if (part.kind === 'dish') return { key: 'dish', type: 'dish' };
  return { key: 'box', type: 'box' };
}

// ---- catalogue ----------------------------------------------------------------------------

let partsById = new Map();
let colourByCode = new Map();

function loadCatalogue(partsJson, coloursJson) {
  partsById = new Map();
  for (const p of partsJson) {
    const sx = Number(p.sx) || 1;
    const sz = Number(p.sz) || 1;
    let studs = p.studs_top;
    if (studs === undefined || studs === 'all') {
      studs = [];
      for (let dx = 0; dx < sx; dx++) for (let dz = 0; dz < sz; dz++) studs.push([dx, dz]);
    }
    const slope = p.slope && typeof p.slope === 'object' ? p.slope : null;
    const part = {
      sx,
      sz,
      h: Number(p.h_plates) || 1,
      studs: Array.isArray(studs) ? studs.map(([a, b]) => [Number(a), Number(b)]) : [],
      name: String(p.name || p.id),
      kind: typeof p.kind === 'string' ? p.kind : 'brick',
      lowSide: slope && Object.hasOwn(SIDES, slope.low_side) ? slope.low_side : null,
      angle: (slope && Number(slope.angle_deg)) || 45,
      bottomCells: Array.isArray(p.bottom_cells) ? p.bottom_cells.filter(Array.isArray).map(([a, b]) => [Number(a), Number(b)]) : [],
    };
    part.shape = shapeFor(part);
    partsById.set(String(p.id), part);
  }
  colourByCode = new Map();
  for (const c of coloursJson) {
    colourByCode.set(Number(c.ldraw_code), {
      rgb: typeof c.rgb === 'string' && /^#[0-9a-fA-F]{6}$/.test(c.rgb) ? c.rgb : FALLBACK_RGB,
      transparent: Boolean(c.transparent),
      name: typeof c.name === 'string' && c.name ? c.name.replaceAll('_', ' ') : `Colour ${c.ldraw_code}`,
    });
  }
}

const UNKNOWN_PART = { sx: 1, sz: 1, h: 3, studs: [], name: 'unknown part', kind: 'unknown', shape: { key: 'box', type: 'box' } };

function normRot(rot) {
  return ((Math.round(Number(rot) || 0) % 360) + 360) % 360;
}

/** (w, d, h): cells covered along grid x, grid y and z. Same as Catalog.footprint. */
function footprint(part, rot) {
  return rot % 180 === 0 ? [part.sx, part.sz, part.h] : [part.sz, part.sx, part.h];
}

/** Offset inside the footprint of stud (dx, dz) in the part's own axes. Same as local_to_cell. */
function localToCell(part, rot, dx, dz) {
  switch (rot) {
    case 0:
      return [dx, dz];
    case 90:
      return [part.sz - 1 - dz, dx];
    case 180:
      return [part.sx - 1 - dx, part.sz - 1 - dz];
    case 270:
      return [dz, part.sx - 1 - dx];
    default:
      return null;
  }
}

/** A direction (x, z) in the part's own axes as a grid direction (x, y). Same as low_side. */
function ownToGrid([lx, lz], rot) {
  switch (rot) {
    case 0:
      return [lx, lz];
    case 90:
      return [-lz, lx];
    case 180:
      return [-lx, -lz];
    case 270:
      return [lz, -lx];
    default:
      return null;
  }
}

// For tests: the same answers as Catalog.footprint and Catalog.stud_cells in Python.
state.geometry = {
  footprint(partId, rot) {
    const part = partsById.get(String(partId));
    return part ? footprint(part, normRot(rot)) : null;
  },
  studCells(partId, rot, x, y) {
    const part = partsById.get(String(partId));
    if (!part) return null;
    return part.studs.map(([dx, dz]) => {
      const c = localToCell(part, normRot(rot), dx, dz);
      return c ? [x + c[0], y + c[1]] : null;
    });
  },
};

// ---- drawing a build --------------------------------------------------------------------

/** Empty a view's group, freeing what only it used (shared geometry and materials stay). */
function disposeDrawn(view) {
  const shared = new Set([studGeo, ...[...shapeCache.values()].map((g) => g.geo)]);
  for (const obj of [...view.group.children]) {
    view.group.remove(obj);
    if (obj.geometry && !shared.has(obj.geometry)) obj.geometry.dispose();
    if (obj.isInstancedMesh) obj.dispose();
  }
  view.drawn = null;
  view.partsJson = null;
}

/** The one material for a colour, made the first time it is needed. */
function materialFor(code) {
  let mat = materialCache.get(code);
  if (mat) return mat;
  const colour = colourByCode.get(code) || { rgb: FALLBACK_RGB, transparent: false };
  const opts = { color: new THREE.Color(colour.rgb) };
  if (colour.transparent) Object.assign(opts, { transparent: true, opacity: 0.55, depthWrite: false });
  mat = new THREE.MeshLambertMaterial(opts);
  materialCache.set(code, mat);
  if (cutOn()) cutMaterial(mat, true);
  return mat;
}

/** Sorted ascending array -> number of entries <= value. */
function upperBound(sorted, value) {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] <= value) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

const Z_AXIS = new THREE.Vector3(0, 0, 1);

/** Draw ``build`` into ``view``'s group (the designed view also sets the page's counts). */
function drawBuild(build, view) {
  disposeDrawn(view);
  const modelGroup = view.group;
  const all = Array.isArray(build.parts) ? build.parts : [];
  // Anything in "parts" that is not an object (null, a number, a list) cannot be a part.
  const raw = [];
  all.forEach((p, index) => {
    if (p !== null && typeof p === 'object' && !Array.isArray(p)) raw.push({ p, index });
  });
  // Normalise every placement and work out its box and shape once.
  const parts = raw.map(({ p, index }) => {
    const part = partsById.get(String(p.part)) || UNKNOWN_PART;
    const rot = normRot(p.rot);
    // lying on a face: it keeps clear a column of three cells (Catalog.footprint)
    const out = typeof p.face === 'string' && Object.hasOwn(FACE_OUT, p.face) ? FACE_OUT[p.face] : null;
    const [w, d, h] = out ? [1, 1, 3] : footprint(part, rot);
    const x = Number(p.x) || 0;
    const y = Number(p.y) || 0;
    const z = Number(p.z) || 0;
    const code = Number(p.color);
    let shape = part.shape;
    const dir = shape.dir && !out ? ownToGrid(shape.dir, rot) : null;
    if (shape.dir && !dir) shape = { key: 'box', type: 'box' }; // a turn the table does not know
    const id = String(p.part);
    return { index, id, part, rot, w, d, h, x, y, z, code, shape, dir, out, face: out ? p.face : 'top', step: Math.max(0, Number(p.step) || 0) };
  });
  // Stable sort by step so "parts with step <= N" is always a prefix.
  parts.sort((a, b) => a.step - b.step || a.index - b.index);

  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const pos = new THREE.Vector3();
  const scl = new THREE.Vector3();

  // The part's unit shape scaled to its cells (less the gap), turned so a wedge runs down
  // towards its low side, and moved into place. ``grow`` mm is added on every side.
  const outward = new THREE.Vector3();
  const partMatrix = (p, grow = 0) => {
    if (p.out) {
      // on its side: its own height (one plate) is its thickness out of the face, from the
      // back of its column; across, it is one stud wide and centred on the side stud
      const t = p.part.h * CELL.z;
      const [ox, oy] = p.out;
      pos.set(
        (p.x + 0.5) * CELL.x + ox * (t / 2 - CELL.x / 2),
        (p.y + 0.5) * CELL.y + oy * (t / 2 - CELL.y / 2),
        p.z * CELL.z + SIDE_STUD_MM,
      );
      q.setFromUnitVectors(Z_AXIS, outward.set(ox, oy, 0));
      scl.set(CELL.x - GAP + 2 * grow, CELL.y - GAP + 2 * grow, t - GAP_Z + 2 * grow);
      return m.compose(pos, q, scl);
    }
    pos.set((p.x + p.w / 2) * CELL.x, (p.y + p.d / 2) * CELL.y, (p.z + p.h / 2) * CELL.z);
    const wx = p.w * CELL.x - GAP + 2 * grow;
    const wy = p.d * CELL.y - GAP + 2 * grow;
    const wz = p.h * CELL.z - GAP_Z + 2 * grow;
    if (p.dir) {
      q.setFromAxisAngle(Z_AXIS, Math.atan2(p.dir[1], p.dir[0]));
      if (p.dir[0] !== 0) scl.set(wx, wy, wz);
      else scl.set(wy, wx, wz);
    } else {
      q.identity();
      scl.set(wx, wy, wz);
    }
    return m.compose(pos, q, scl);
  };

  // Group by colour and shape. Each group keeps parts and studs in step order.
  const groups = new Map();
  for (const p of parts) {
    const key = `${p.code}|${p.shape.key}`;
    let g = groups.get(key);
    if (!g) {
      g = { code: p.code, shape: shapeGeometry(p.shape), parts: [], studs: [] };
      groups.set(key, g);
    }
    g.parts.push(p);
    if (p.out) {
      // a round plate on its side: its one stud points out of the face
      if (p.part.studs.length) {
        const [ox, oy] = p.out;
        const reach = CELL.x / 2 - p.part.h * CELL.z - STUD_H / 2;
        const sq = new THREE.Quaternion().setFromUnitVectors(Z_AXIS, new THREE.Vector3(ox, oy, 0));
        g.studs.push({ step: p.step, x: (p.x + 0.5) * CELL.x - ox * reach, y: (p.y + 0.5) * CELL.y - oy * reach, z: p.z * CELL.z + SIDE_STUD_MM, q: sq });
      }
    } else if (p.rot === 0 || p.rot === 90 || p.rot === 180 || p.rot === 270) {
      const top = (p.z + p.h) * CELL.z - GAP_Z / 2 + STUD_H / 2;
      for (const [dx, dz] of p.part.studs) {
        const cell = localToCell(p.part, p.rot, dx, dz);
        if (!cell) continue;
        g.studs.push({ step: p.step, x: (p.x + cell[0] + 0.5) * CELL.x, y: (p.y + cell[1] + 0.5) * CELL.y, z: top });
      }
    }
  }

  const meshes = [];
  for (const g of groups.values()) {
    const mat = materialFor(g.code);
    const colour = colourByCode.get(g.code) || { rgb: FALLBACK_RGB, transparent: false };
    const body = new THREE.InstancedMesh(g.shape.geo, mat, g.parts.length);
    g.parts.forEach((p, i) => body.setMatrixAt(i, partMatrix(p)));
    body.instanceMatrix.needsUpdate = true;
    body.castShadow = !colour.transparent;
    body.receiveShadow = true;
    body.frustumCulled = false;
    modelGroup.add(body);
    const bodySteps = g.parts.map((p) => p.step);

    let studs = null;
    let studSteps = [];
    if (g.studs.length) {
      studs = new THREE.InstancedMesh(studGeo, mat, g.studs.length);
      scl.set(1, 1, 1);
      g.studs.forEach((s, i) => {
        pos.set(s.x, s.y, s.z);
        if (s.q) q.copy(s.q);
        else q.identity();
        studs.setMatrixAt(i, m.compose(pos, q, scl));
      });
      studs.instanceMatrix.needsUpdate = true;
      studs.castShadow = !colour.transparent;
      studs.receiveShadow = true;
      studs.frustumCulled = false;
      modelGroup.add(studs);
      studSteps = g.studs.map((s) => s.step);
    }
    meshes.push({ body, bodySteps, bodyParts: g.parts, shape: g.shape, studs, studSteps });
  }

  // Thin dark edges on every part, in step order so a draw range shows a prefix. A part's
  // edges are its shape's edge lines, moved like its body; edgeStart[i] is where part i's
  // begin (in vertices), and edgeStart[parts.length] is the total.
  const edgeStart = new Uint32Array(parts.length + 1);
  parts.forEach((p, i) => {
    edgeStart[i + 1] = edgeStart[i] + shapeGeometry(p.shape).edges.length / 3;
  });
  const edgePositions = new Float32Array(edgeStart[parts.length] * 3);
  const v = new THREE.Vector3();
  parts.forEach((p, i) => {
    const unit = shapeGeometry(p.shape).edges;
    partMatrix(p);
    let o = edgeStart[i] * 3;
    for (let k = 0; k < unit.length; k += 3) {
      v.set(unit[k], unit[k + 1], unit[k + 2]).applyMatrix4(m);
      edgePositions[o++] = v.x;
      edgePositions[o++] = v.y;
      edgePositions[o++] = v.z;
    }
  });
  const edgeGeo = new THREE.BufferGeometry();
  edgeGeo.setAttribute('position', new THREE.BufferAttribute(edgePositions, 3));
  const edges = new THREE.LineSegments(edgeGeo, edgeMat);
  edges.frustumCulled = false;
  modelGroup.add(edges);

  // The current step's edges in the highlight colour: a second geometry sharing the same
  // vertices, whose draw range picks out that step's parts. Drawn after the dark edges.
  const newEdgeGeo = new THREE.BufferGeometry();
  newEdgeGeo.setAttribute('position', edgeGeo.getAttribute('position'));
  newEdgeGeo.setDrawRange(0, 0);
  const newEdges = new THREE.LineSegments(newEdgeGeo, newEdgeMat);
  newEdges.frustumCulled = false;
  newEdges.renderOrder = 1;
  modelGroup.add(newEdges);

  // Highlight: a slightly larger copy of each new part's shape drawn inside-out behind it,
  // which shows as a thick coloured outline. One instanced mesh per shape.
  const outlines = new Map();
  for (const p of parts) {
    const o = outlines.get(p.shape.key);
    if (o) o.capacity += 1;
    else outlines.set(p.shape.key, { capacity: 1, mesh: null });
  }
  for (const [key, o] of outlines) {
    o.mesh = new THREE.InstancedMesh(shapeCache.get(key).geo, outlineMat, o.capacity);
    o.mesh.count = 0;
    o.mesh.frustumCulled = false;
    modelGroup.add(o.mesh);
  }

  const steps = parts.map((p) => p.step);
  view.drawn = {
    parts,
    steps,
    meshes,
    edges,
    newEdges,
    edgeStart,
    outlines,
    highlightParts: 0,
    partMatrix,
    skipped: all.length - raw.length,
  };
  view.partsJson = JSON.stringify(all);
  if (view === views.designed) {
    state.partCount = parts.length;
    state.maxStep = parts.length ? parts[parts.length - 1].step : 0;
  }
  return view.drawn;
}

/** Show the designed build's parts with step <= n (all of them when showAll), outlining step
 * n. The plain conversion always shows all its parts. */
function applyStep(n, showAll) {
  const drawn = views.designed.drawn;
  if (!drawn) return;
  const max = state.maxStep;
  if (max <= 0) showAll = true;
  n = showAll ? max : Math.min(Math.max(1, Math.round(n)), max);
  const limit = showAll ? Infinity : n;
  for (const g of drawn.meshes) {
    g.body.count = upperBound(g.bodySteps, limit);
    if (g.studs) g.studs.count = upperBound(g.studSteps, limit);
  }
  const visible = upperBound(drawn.steps, limit);
  const starts = drawn.edgeStart;
  drawn.edges.geometry.setDrawRange(0, starts[visible]);

  for (const o of drawn.outlines.values()) o.mesh.count = 0;
  let k = 0;
  if (!showAll) {
    const first = upperBound(drawn.steps, n - 1);
    for (let i = first; i < visible; i++) {
      const p = drawn.parts[i];
      const mesh = drawn.outlines.get(p.shape.key).mesh;
      mesh.setMatrixAt(mesh.count++, drawn.partMatrix(p, OUTLINE_MM));
      k++;
    }
    for (const o of drawn.outlines.values()) o.mesh.instanceMatrix.needsUpdate = true;
    drawn.newEdges.geometry.setDrawRange(starts[first], starts[visible] - starts[first]);
  } else {
    drawn.newEdges.geometry.setDrawRange(0, 0);
  }
  drawn.highlightParts = k;

  state.step = n;
  state.showingAll = showAll;
  state.visibleCount = visible;
  state.highlightCount = k;
  updateStepUi(k);
  requestRender();
}

/** Grid direction (dx, dy) a wedge's slanted face runs down, read off the drawn geometry. */
function downhill(shape, world) {
  if (!shape.slant) return null;
  const n = shape.slant.clone().applyMatrix3(new THREE.Matrix3().getNormalMatrix(world));
  // A face looking up runs down the way it leans; one looking down (an inverted slope's
  // underside) runs down the other way.
  const sign = Math.sign(n.z) || 1;
  const hx = sign * n.x;
  const hy = sign * n.y;
  const len = Math.hypot(hx, hy);
  if (len < 1e-9) return null;
  return [Math.round(hx / len) + 0, Math.round(hy / len) + 0];
}

const DIAGONAL = [Math.SQRT1_2, Math.SQRT1_2];

/** The cached shape whose geometry ``mesh`` really draws (measured from, not assumed). */
function drawnShape(mesh) {
  for (const g of shapeCache.values()) if (g.geo === mesh.geometry) return g;
  return null;
}

/** How a flat face (its ring of unit-shape points, taken into the world by ``world``) is
 * outlined: {points: its corners on the rim, diagonal: mm from the face's centre to its rim
 * along the grid diagonal (1, 1)}. A circle of radius r gives r, a square of half-width r
 * gives r x 1.41. Null when the face is only an edge or a point. */
function faceRim(ring, world) {
  const v = new THREE.Vector3();
  const pts = ring.map(([x, y, z]) => {
    v.set(x, y, z).applyMatrix4(world);
    return [v.x, v.y];
  });
  if (pts.length < 3) return null;
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  if (Math.max(...xs) - Math.min(...xs) < 1e-3 || Math.max(...ys) - Math.min(...ys) < 1e-3) return null;
  // the rim's corners in order round the centre (a cap's own centre point is not one)
  const rim = pts
    .filter(([x, y]) => Math.hypot(x - cx, y - cy) > 1e-3)
    .sort((a, b) => Math.atan2(a[1] - cy, a[0] - cx) - Math.atan2(b[1] - cy, b[0] - cx));
  let best = Infinity;
  const [dx, dy] = DIAGONAL;
  for (let i = 0; i < rim.length; i++) {
    const [ax, ay] = rim[i];
    const [bx, by] = rim[(i + 1) % rim.length];
    // centre + t * d = a + u * (b - a), with 0 <= u <= 1 and t > 0
    const ex = bx - ax;
    const ey = by - ay;
    const det = ex * dy - ey * dx;
    if (Math.abs(det) < 1e-12) continue;
    const t = (ex * (ay - cy) - ey * (ax - cx)) / det;
    const u = (dx * (ay - cy) - dy * (ax - cx)) / det;
    if (t > 0 && u >= -1e-9 && u <= 1 + 1e-9) best = Math.min(best, t);
  }
  return { points: rim.length, diagonal: Number.isFinite(best) ? best : null };
}

/** The unit shape's triangles, as flat [x, y, z, ...] arrays of 9 numbers. */
function shapeTriangles(shape) {
  if (shape.triangles) return shape.triangles;
  const pos = shape.geo.getAttribute('position');
  const index = shape.geo.getIndex();
  const count = index ? index.count : pos.count;
  const out = [];
  for (let i = 0; i < count; i += 3) {
    const tri = [];
    for (let k = 0; k < 3; k++) {
      const j = index ? index.getX(i + k) : i + k;
      tri.push(pos.getX(j), pos.getY(j), pos.getZ(j));
    }
    out.push(tri);
  }
  shape.triangles = out;
  return out;
}

/** The farthest (mm) any of the given world points lies from the shape drawn with ``world``. */
function gapToSurface(shape, world, points) {
  const tris = shapeTriangles(shape).map((t) => {
    const [a, b, c] = [0, 3, 6].map((o) => new THREE.Vector3(t[o], t[o + 1], t[o + 2]).applyMatrix4(world));
    return new THREE.Triangle(a, b, c);
  });
  const p = new THREE.Vector3();
  const q = new THREE.Vector3();
  let worst = 0;
  for (let i = 0; i < points.length; i += 3) {
    p.set(points[i], points[i + 1], points[i + 2]);
    let nearest = Infinity;
    for (const t of tris) {
      t.closestPointToPoint(p, q);
      nearest = Math.min(nearest, q.distanceTo(p));
      if (nearest < 1e-4) break;
    }
    worst = Math.max(worst, nearest);
  }
  return worst;
}

const probeMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }));
probeMesh.matrixAutoUpdate = false;
const probeRay = new THREE.Raycaster();

/** For an upright wedge: how high (mm above its bottom) the drawn top surface is near the
 * start of the slanted run, in its middle, and near its end at the lip, found by casting a
 * ray straight down onto the drawn part. */
function slopeHeights(shape, world, bottom, top) {
  if ((shape.type !== 'wedge' && shape.type !== 'curved') || shape.s === null) return null;
  probeMesh.geometry = shape.geo;
  probeMesh.matrixWorld.copy(world);
  const v = new THREE.Vector3();
  const heights = [0.02, 0.5, 0.98].map((f) => {
    v.set(0.5 - shape.s + shape.s * f, 0, 0).applyMatrix4(world);
    probeRay.set(new THREE.Vector3(v.x, v.y, top + 10), new THREE.Vector3(0, 0, -1));
    const hit = probeRay.intersectObject(probeMesh, false)[0];
    return hit ? hit.point.z - bottom : null;
  });
  probeMesh.geometry = null;
  return { high: heights[0], mid: heights[1], low: heights[2] };
}

// For tests: what is drawn right now, in world millimetres after every transform, so it can
// be compared with the Python catalogue. Only instances currently shown are listed. Each
// entry is the axis-aligned box {min: [x, y, z], max: [x, y, z]} the instance covers. A body
// also says which part it is (part, entry: its index in build.json's "parts"), its catalogue
// kind, the shape drawn (box, wedge, curved, inverted, cylinder, cone, dish), the x-y extent
// of its top and bottom faces ({min: [x, y], max: [x, y]}, null when the face is only an
// edge or a point), ``topRim`` and ``bottomRim`` (see faceRim: how round the face is), for
// wedges ``downhill``: the grid direction [dx, dy] the slanted face runs down, worked out
// from the drawn faces (compare with Catalog.low_side), and ``edges``: how many line ends
// its dark edge lines have, and ``face``: "top", or the face a part lying on its side points
// out of. Outlines (the current step's highlight) give their box,
// ``topRim`` and ``downhill`` in the same way.
// With {detail: true}, slower measurements are added to each body: ``edgeBox`` (the box its
// edge lines cover), ``edgeGap`` (the farthest, in mm, any edge line end lies from the drawn
// body) and, for upright wedges, ``slope`` (see slopeHeights).
// ndc: where the shown model falls in the view, -1..1 on each axis being inside it.
// meshCount: the three.js objects drawing the model (instancing keeps it small).
// camera: {position, target}, where the camera is and the point it looks at.
// All of the above is the designed build. ``views`` gives the same for each view, as
// {rough, designed}: each with ``label``, ``shown`` (drawn on the page now), ``partCount``,
// bodies, studs, outlines, ndc, meshCount, ``rect`` (where it is drawn, in page pixels, or
// null when it is not shown), ``camera`` (the camera it was last drawn with: {id, position,
// target}, null when not shown), and the ids of the ``materials`` and ``geometries`` its
// parts are drawn with (so the tests can see the two views share them). ``sharedCamera`` is
// true when every shown view was last drawn with the one camera, from the same place.
// ``compare`` is {active: two views are possible, show: 'both', 'rough' or 'designed'}.
state.inspect = (options = {}) => {
  const detail = Boolean(options && options.detail);
  scene.updateMatrixWorld(true);
  camera.updateMatrixWorld(true);
  const designed = inspectView(views.designed, detail);
  const out = { ...designed, camera: { position: camera.position.toArray(), target: controls.target.toArray() } };
  const shown = shownViews();
  const c = renderer.domElement.getBoundingClientRect();
  out.views = {};
  for (const v of Object.values(views)) {
    const own = v === views.designed ? designed : inspectView(v, detail);
    const isShown = shown.includes(v);
    const r = v.rect || (isShown ? { x: 0, y: 0, width: c.width, height: c.height } : null);
    const meshes = v.drawn ? v.drawn.meshes : [];
    out.views[v.name] = {
      label: v.label,
      shown: isShown,
      partCount: v.drawn ? v.drawn.parts.length : 0,
      ...own,
      rect: r && { x: c.left + r.x, y: c.top + r.y, width: r.width, height: r.height },
      camera: isShown ? v.lastRender : null,
      materials: [...new Set(meshes.map((g) => g.body.material.uuid))],
      geometries: [...new Set(meshes.map((g) => g.body.geometry.uuid))],
    };
  }
  const drawnWith = shown.map((v) => v.lastRender);
  out.sharedCamera = drawnWith.every(
    (r) => r && r.id === camera.uuid && r.position.every((x, i) => x === drawnWith[0].position[i]),
  );
  out.compare = { active: compareActive, show };
  // Each renderer.render call of the last frame, as recorded while it drew; areas in page
  // pixels, as [x, y, width, height] from the top left like ``rect``.
  const toPage = (b, canvas) => b && [c.left + b[0], c.top + canvas[1] - b[1] - b[3], b[2], b[3]];
  out.frame = frame.map((ps) => ({
    ...ps,
    viewport: toPage(ps.viewport, ps.canvas),
    scissor: toPage(ps.scissor, ps.canvas),
  }));
  return out;
};

// For tests: draw every shown view ``n`` times, waiting for each frame to finish, and give
// the average milliseconds a frame took.
state.timeFrames = (n = 10) => {
  const gl = renderer.getContext();
  const pixel = new Uint8Array(4);
  const finish = () => gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  renderViews();
  finish();
  const start = performance.now();
  for (let i = 0; i < n; i++) {
    renderViews();
    finish();
  }
  return (performance.now() - start) / Math.max(1, n);
};

/** What one view draws now (see state.inspect). */
function inspectView(view, detail) {
  const drawn = view.drawn;
  const out = { bodies: [], studs: [], outlines: [], highlightEdgeParts: 0, outlineColour: null, ndc: null, meshCount: 0 };
  if (!drawn) return out;
  const order = new Map(drawn.parts.map((p, i) => [p, i]));
  out.meshCount = view.group.children.length;
  camera.updateMatrixWorld(true);
  const m = new THREE.Matrix4();
  const box = new THREE.Box3();
  const whole = new THREE.Box3();
  const v = new THREE.Vector3();
  const aabb = (mesh, i) => {
    if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
    mesh.getMatrixAt(i, m);
    m.premultiply(mesh.matrixWorld);
    box.copy(mesh.geometry.boundingBox).applyMatrix4(m);
    return { min: box.min.toArray(), max: box.max.toArray() };
  };
  const extent = (ring) => {
    const lo = [Infinity, Infinity];
    const hi = [-Infinity, -Infinity];
    for (const [x, y, z] of ring) {
      v.set(x, y, z).applyMatrix4(m);
      lo[0] = Math.min(lo[0], v.x);
      lo[1] = Math.min(lo[1], v.y);
      hi[0] = Math.max(hi[0], v.x);
      hi[1] = Math.max(hi[1], v.y);
    }
    if (!ring.length || (hi[0] - lo[0] < 1e-3 && hi[1] - lo[1] < 1e-3)) return null;
    if (hi[0] - lo[0] < 1e-3 || hi[1] - lo[1] < 1e-3) return null; // only an edge
    return { min: lo, max: hi };
  };
  for (const g of drawn.meshes) {
    const colour = `#${g.body.material.color.getHexString()}`;
    for (let i = 0; i < g.body.count; i++) {
      const entry = { ...aabb(g.body, i), colour, step: g.bodySteps[i] };
      whole.union(box);
      const p = g.bodyParts[i];
      Object.assign(entry, {
        part: p.id,
        entry: p.index,
        kind: p.part.kind,
        face: p.face,
        shape: g.shape.type,
        top: extent(g.shape.top),
        bottom: extent(g.shape.bottom),
        topRim: faceRim(g.shape.top, m),
        bottomRim: faceRim(g.shape.bottom, m),
        downhill: downhill(g.shape, m),
      });
      const k = order.get(p);
      const ends = drawn.edges.geometry.getAttribute('position').array.subarray(drawn.edgeStart[k] * 3, drawn.edgeStart[k + 1] * 3);
      entry.edges = ends.length / 3;
      if (detail) {
        const eb = new THREE.Box3().setFromArray(ends);
        entry.edgeBox = { min: eb.min.toArray(), max: eb.max.toArray() };
        entry.edgeGap = gapToSurface(g.shape, m, ends);
        entry.slope = slopeHeights(g.shape, m, entry.min[2], entry.max[2]);
      }
      out.bodies.push(entry);
    }
    if (g.studs) {
      for (let i = 0; i < g.studs.count; i++) {
        out.studs.push({ ...aabb(g.studs, i), colour, step: g.studSteps[i] });
        whole.union(box);
      }
    }
  }
  for (const o of drawn.outlines.values()) {
    const shape = drawnShape(o.mesh);
    for (let i = 0; i < o.mesh.count; i++) {
      const entry = aabb(o.mesh, i);
      out.outlines.push({ ...entry, topRim: shape && faceRim(shape.top, m), downhill: shape && downhill(shape, m) });
    }
  }
  out.outlineColour = `#${outlineMat.color.getHexString()}`;
  // parts whose highlight edges are drawn: the draw range covers exactly theirs
  const range = drawn.newEdges.geometry.drawRange;
  for (let i = 0; i < drawn.parts.length; i++) {
    const a = drawn.edgeStart[i];
    const b = drawn.edgeStart[i + 1];
    if (range.count > 0 && a >= range.start && b <= range.start + range.count) out.highlightEdgeParts += 1;
  }
  if (!whole.isEmpty()) {
    const ndc = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
    for (let c = 0; c < 8; c++) {
      v.set(c & 1 ? whole.max.x : whole.min.x, c & 2 ? whole.max.y : whole.min.y, c & 4 ? whole.max.z : whole.min.z);
      v.project(camera);
      ndc.minX = Math.min(ndc.minX, v.x);
      ndc.maxX = Math.max(ndc.maxX, v.x);
      ndc.minY = Math.min(ndc.minY, v.y);
      ndc.maxY = Math.max(ndc.maxY, v.y);
    }
    out.ndc = ndc;
  }
  return out;
};

// ---- camera, ground and lights fitted to the model --------------------------------------

let fittedFor = '';
let modelBox = null; // the box round the parts of the shown builds, before any margin

/** The 8 corners of a box, as a flat [x, y, z, x, y, z, ...] array. */
function boxCorners(box) {
  const out = [];
  for (let c = 0; c < 8; c++) {
    out.push(c & 1 ? box.max.x : box.min.x, c & 2 ? box.max.y : box.min.y, c & 4 ? box.max.z : box.min.z);
  }
  return out;
}

/** Where the points (a flat x, y, z array) land in the view with the camera ``dist`` from
 * ``target`` along ``dir``: their NDC extent, or null when one is behind the camera. */
function projectedExtent(points, target, dist, dir) {
  camera.position.copy(target).addScaledVector(dir, dist);
  camera.lookAt(target);
  camera.updateMatrixWorld(true);
  const ext = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  const v = new THREE.Vector3();
  for (let i = 0; i < points.length; i += 3) {
    v.set(points[i], points[i + 1], points[i + 2]).applyMatrix4(camera.matrixWorldInverse);
    if (v.z > -1e-3 * dist) return null;
    v.applyMatrix4(camera.projectionMatrix);
    ext.minX = Math.min(ext.minX, v.x);
    ext.maxX = Math.max(ext.maxX, v.x);
    ext.minY = Math.min(ext.minY, v.y);
    ext.maxY = Math.max(ext.maxY, v.y);
  }
  return ext;
}

const within = (e, margin) => e && Math.max(-e.minX, e.maxX) <= margin && Math.max(-e.minY, e.maxY) <= margin;

/** The shortest distance from ``target`` at which the model's own corners are inside
 * FIT_MARGIN and the corners of its box (never smaller than 4 x 4 x 3 cells) inside BOX_MARGIN. */
function fitDistance(fit, target, radius, dir) {
  const fits = (d) =>
    within(projectedExtent(fit.corners, target, d, dir), BOX_MARGIN) &&
    within(projectedExtent(fit.points, target, d, dir), FIT_MARGIN);
  let lo = radius * 0.05;
  let hi = radius * 4 + target.distanceTo(fit.box.getCenter(new THREE.Vector3()));
  for (let i = 0; i < 40 && !fits(hi); i++) hi *= 2;
  for (let i = 0; i < 30; i++) {
    const mid = (lo + hi) / 2;
    if (fits(mid)) hi = mid;
    else lo = mid;
  }
  return hi;
}

/** From the point looked at towards the camera, as the view is now. */
function currentViewDir() {
  const dir = camera.position.clone().sub(controls.target);
  return dir.lengthSq() > 1e-9 ? dir.normalize() : VIEW_DIR.clone();
}

/** The direction to frame the model from: the person's own, once they have turned the view. */
function frameDir() {
  return userMoved ? currentViewDir() : VIEW_DIR;
}

/** Put the camera as close to the model as it can be while seeing all of it, looking along
 * ``dir`` (from the model towards the camera). */
function placeCamera(dir = VIEW_DIR) {
  const { box, points } = fitted;
  camera.updateProjectionMatrix();
  const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 20);
  const target = box.getCenter(new THREE.Vector3());
  const halfV = THREE.MathUtils.degToRad(camera.fov / 2);
  const right = new THREE.Vector3();
  const up = new THREE.Vector3();
  let dist = fitDistance(fitted, target, radius, dir);
  // In perspective the near end of the model looks bigger, so its picture is off-centre:
  // move the point looked at until the picture sits in the middle, then fit again.
  for (let pass = 0; pass < 4; pass++) {
    const e = projectedExtent(points, target, dist, dir);
    const cx = (e.minX + e.maxX) / 2;
    const cy = (e.minY + e.maxY) / 2;
    if (Math.abs(cx) < 0.01 && Math.abs(cy) < 0.01) break;
    const halfH = Math.tan(halfV) * dist;
    right.setFromMatrixColumn(camera.matrixWorld, 0);
    up.setFromMatrixColumn(camera.matrixWorld, 1);
    target.addScaledVector(right, cx * halfH * camera.aspect).addScaledVector(up, cy * halfH);
    dist = fitDistance(fitted, target, radius, dir);
  }
  fitted.portrait = camera.aspect < 1;
  camera.position.copy(target).addScaledVector(dir, dist);
  camera.near = Math.max(0.5, dist / 100);
  camera.far = dist * 40;
  camera.updateProjectionMatrix();
  // Fade the far ground into the sky so there is no hard edge at the horizon.
  scene.fog = new THREE.Fog(SKY_HAZE, dist * 1.6, dist * 7);
  controls.target.copy(target);
  controls.update();
  requestRender();
}

function fitView(build) {
  // The model's box in millimetres: what the parts cover (studs included), or the build's
  // grid when there are no parts. Never smaller than 4 x 4 x 3 cells, so a single part is
  // not blown up to fill the screen. With two views, the box round both builds, so they are
  // framed alike and can be compared at the same scale, whichever of them is shown.
  const box = new THREE.Box3();
  // The corners the camera must keep in view: for each (x, y) grid corner of any part, its
  // lowest and highest point. Far fewer than every part's eight corners, and enough, since
  // the points between them on that vertical line are in view when both ends are.
  const columns = new Map();
  const framed = (compareActive ? [views.rough, views.designed] : [views.designed])
    .filter((v) => v.drawn)
    .flatMap((v) => v.drawn.parts);
  if (framed.length) {
    for (const p of framed) {
      const top = (p.z + p.h) * CELL.z + (p.part.studs.length ? STUD_H : 0);
      const bottom = p.z * CELL.z;
      box.expandByPoint(new THREE.Vector3(p.x * CELL.x, p.y * CELL.y, bottom));
      box.expandByPoint(new THREE.Vector3((p.x + p.w) * CELL.x, (p.y + p.d) * CELL.y, top));
      for (const cx of [p.x, p.x + p.w]) {
        for (const cy of [p.y, p.y + p.d]) {
          const k = `${cx},${cy}`;
          const col = columns.get(k);
          if (col) {
            col[2] = Math.min(col[2], bottom);
            col[3] = Math.max(col[3], top);
          } else columns.set(k, [cx * CELL.x, cy * CELL.y, bottom, top]);
        }
      }
    }
  } else {
    let [nx, ny, nz] = [0, 0, 0];
    if (Array.isArray(build.shape) && build.shape.length === 3) [nx, ny, nz] = build.shape.map((n) => Number(n) || 0);
    box.set(new THREE.Vector3(0, 0, 0), new THREE.Vector3(nx * CELL.x, ny * CELL.y, nz * CELL.z));
  }
  modelBox = box.clone(); // the parts themselves, for "look inside"
  const least = new THREE.Vector3(4 * CELL.x, 4 * CELL.y, 3 * CELL.z);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  const half = size.max(least).multiplyScalar(0.5);
  box.set(centre.clone().sub(half), centre.clone().add(half));
  if (box.min.z < 0) box.translate(new THREE.Vector3(0, 0, -box.min.z)); // stays on the ground
  box.getCenter(centre);
  const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 20);

  // Ground: a big plane just under z = 0, with a faint stud grid under the model.
  const span = radius * 80;
  ground.scale.set(span, span, 1);
  ground.position.set(centre.x, centre.y, -0.05);
  if (grid) {
    scene.remove(grid);
    grid.geometry.dispose();
    grid.material.dispose();
  }
  const cells = Math.max(box.max.x - box.min.x, box.max.y - box.min.y) / CELL.x;
  const gridCells = Math.ceil(cells / 2) * 2 + 8;
  grid = new THREE.GridHelper(gridCells * CELL.x, gridCells, 0xc9c2ad, 0xd9d3c0);
  grid.rotation.x = Math.PI / 2; // GridHelper lies in x-z; turn it into x-y
  grid.position.set(Math.round(centre.x / CELL.x) * CELL.x, Math.round(centre.y / CELL.y) * CELL.y, 0);
  scene.add(grid);

  // Sun from the front-left, high; fill from the back-right.
  sun.position.set(centre.x - radius * 1.2, centre.y - radius * 1.8, centre.z + radius * 2.6);
  sun.target.position.copy(centre);
  const sc = sun.shadow.camera;
  sc.left = -radius * 1.6;
  sc.right = radius * 1.6;
  sc.top = radius * 1.6;
  sc.bottom = -radius * 1.6;
  sc.near = 1;
  sc.far = radius * 8;
  sc.updateProjectionMatrix();
  fill.position.set(centre.x + radius * 2, centre.y + radius * 2, centre.z + radius);
  fill.target.position.copy(centre);

  // Camera: framed again only when the model's box changes. Once the person has turned the
  // view, it keeps looking from their angle: only the distance and the point looked at change.
  const key = [...box.min.toArray(), ...box.max.toArray()].map((n) => n.toFixed(2)).join(',');
  if (key !== fittedFor) {
    fittedFor = key;
    const corners = boxCorners(box);
    const points = [];
    for (const [x, y, lo, hi] of columns.values()) points.push(x, y, lo, x, y, hi);
    fitted = { box, corners, points: points.length ? points : corners, portrait: camera.aspect < 1 };
    placeCamera(frameDir());
  }
  requestRender();
}

// ---- page text ----------------------------------------------------------------------------

const slider = $('step');
const prevBtn = $('prev');
const nextBtn = $('next');
const allBtn = $('all');
const stepLabel = $('stepLabel');
const NOTES_OPEN_UP_TO = 3; // more notes than this are folded away behind a summary line

function setNotice(text) {
  const el = $('notice');
  el.textContent = text || '';
  el.hidden = !text;
}

// ---- the two views and the brief ------------------------------------------------------------

const compareBox = $('compare');
const chooseBox = $('choose');
const viewbar = $('viewbar');
const pickLeft = $('pickLeft');
const pickRight = $('pickRight');
const stepsFor = $('stepsFor');
const hint = $('hint');
const HINT_ONE = hint.textContent; // as index.html writes it
const HINT_BOTH = 'Drag either view to turn both · scroll to zoom · right-drag to move';

const plural = (n) => `${n} ${n === 1 ? 'part' : 'parts'}`;

/** Lay the page out for one view or two, as the builds and the person's choice say
 * (``picked``: the person just picked what to show; see resize). */
function showCompare(picked = false) {
  container.classList.toggle('compare', compareActive);
  compareBox.hidden = !compareActive;
  views.rough.pane.hidden = !compareActive || show === 'designed';
  views.designed.pane.hidden = compareActive && show === 'rough';
  for (const v of Object.values(views)) v.count.textContent = plural(v.drawn ? v.drawn.parts.length : 0);
  for (const b of compareBox.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.show === show));
  stepsFor.hidden = !compareActive || show === 'designed';
  hint.textContent = compareActive && show === 'both' ? HINT_BOTH : HINT_ONE;
  chooseBox.hidden = state.versions.length === 0;
  viewbar.hidden = compareBox.hidden && chooseBox.hidden;
  resize(picked);
  requestRender();
}

for (const b of compareBox.querySelectorAll('button')) {
  b.addEventListener('click', () => {
    show = b.dataset.show;
    showCompare(true);
  });
}

/** Put a title, what is under it and the Show button's word on one view. */
function setTag(view, title, what, button) {
  view.label = title;
  const tag = $(view === views.rough ? 'roughTag' : 'designedTag');
  tag.querySelector('.pane-title').textContent = title;
  tag.querySelector('.pane-what').textContent = what;
  document.querySelector(`#compare button[data-show="${view.name}"]`).textContent = button;
}

/** Without versions, the right-hand view is "Designed" once the AI designer has written a
 * brief; before that it is "Finished": BrickSnap's own finishing pass (tiles and slopes) on
 * the plain conversion. */
function nameDesignedView(designed) {
  const [title, what] = designed
    ? ['Designed', 'What BrickSnap made of it · ']
    : ['Finished', 'BrickSnap’s own finishing: tiles and slopes · '];
  setTag(views.designed, title, what, title);
  $('stepsFor').textContent = `The steps are for the ${title.toLowerCase()} build.`;
}

/** [title, what is under it, the Show button's word] for what a view draws (see sources). */
function describeSource(src) {
  if (src === 'rough') return ['Plain conversion', 'What a plain converter makes · ', 'Plain conversion'];
  const v = src === 'live' ? versionByN(state.current) : versionByN(src);
  if (src === 'live' && !(v && liveIsKept(v))) return ['The model now', 'Not kept as a version yet · ', 'Now'];
  if (!v) return ['', '', ''];
  return [v.label, `Version ${v.n}${v.n === state.current ? ' (in use)' : ''} · `, `Version ${v.n}`];
}

// On a narrow screen the two views are one above the other: the choosers and the Show
// buttons then say "Top" and "Bottom" instead of "Left" and "Right".
const narrow = window.matchMedia('(max-width: 700px)');
narrow.addEventListener('change', () => nameViews());

/** The titles over the two views, as the choosers say. */
function nameViews() {
  if (!state.versions.length) {
    setTag(views.rough, 'Plain conversion', 'What a plain converter makes · ', 'Plain conversion');
    nameDesignedView(Boolean(state.brief));
    return;
  }
  const sides = narrow.matches ? ['Top', 'Bottom'] : ['Left', 'Right'];
  for (const [i, el] of document.querySelectorAll('#choose .pick-side').entries()) el.textContent = sides[i];
  if (sources.left !== null) {
    const [title, what] = describeSource(sources.left);
    setTag(views.rough, title, what, sides[0]);
  }
  const [title, what, word] = describeSource(sources.right);
  setTag(views.designed, title, what, sides[1]);
  $('stepsFor').textContent = word === 'Now' ? 'The steps are for the model now.' : `The steps are for ${word.toLowerCase()}.`;
}

/** The designer's brief, in a panel beside the views: project.json's, or the brief the
 * version on the right had. A brief from an older project, written as one paragraph, is
 * shown as that paragraph. */
function showBrief(raw) {
  const panel = $('brief');
  const body = $('briefBody');
  const text = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '');
  let brief = null;
  if (text(raw)) brief = { object: text(raw), features: [], plan: '', colours: [], finish: '' };
  else if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    brief = {
      object: text(raw.object),
      features: Array.isArray(raw.features) ? raw.features.map(text).filter(Boolean) : [],
      plan: text(raw.plan),
      colours: Array.isArray(raw.colours) ? raw.colours.filter((c) => Number.isInteger(c)) : [],
      finish: text(raw.finish),
    };
    if (!brief.object && !brief.features.length && !brief.plan && !brief.colours.length && !brief.finish) brief = null;
  }
  state.brief = brief;
  body.replaceChildren();
  panel.hidden = !brief;
  document.body.classList.toggle('has-brief', Boolean(brief));
  if (!brief) return;
  const add = (tag, className, content) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (content !== undefined) el.textContent = content;
    body.append(el);
    return el;
  };
  if (brief.object) add('p', 'brief-object', brief.object);
  if (brief.features.length) {
    add('h3', '', 'What makes it recognisable');
    const list = add('ul', 'brief-features');
    for (const f of brief.features) {
      const li = document.createElement('li');
      li.textContent = f;
      list.append(li);
    }
  }
  if (brief.plan) {
    add('h3', '', 'The plan');
    add('p', 'brief-plan', brief.plan);
  }
  if (brief.colours.length) {
    add('h3', '', 'Colours');
    const list = add('ul', 'swatches');
    for (const code of brief.colours) {
      const colour = colourByCode.get(code);
      const li = document.createElement('li');
      const swatch = document.createElement('span');
      swatch.className = colour ? 'swatch' : 'swatch unknown';
      swatch.style.backgroundColor = colour ? colour.rgb : FALLBACK_RGB;
      const name = document.createElement('span');
      name.className = 'swatch-name';
      name.textContent = colour ? colour.name : `Colour ${code}`;
      li.append(swatch, name);
      list.append(li);
    }
  }
  if (brief.finish) {
    add('h3', '', 'Finish');
    add('p', 'brief-finish', brief.finish);
  }
}

/** build.json's notes (plain sentences from the make-buildable and finishing passes), as a
 * small list under the verdict; folded behind "What the software changed (N)" when long. */
function showNotes(build) {
  const box = $('notes');
  const notes =
    build && Array.isArray(build.notes)
      ? build.notes.filter((n) => typeof n === 'string' && n.trim()).map((n) => n.trim())
      : [];
  const wasOpen = Boolean(box.querySelector('details[open]'));
  box.replaceChildren();
  box.hidden = notes.length === 0;
  state.notes = notes;
  if (!notes.length) return;
  const list = document.createElement('ul');
  for (const n of notes) {
    const li = document.createElement('li');
    li.textContent = n;
    list.append(li);
  }
  const title = `What the software changed`;
  if (notes.length > NOTES_OPEN_UP_TO) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = `${title} (${notes.length})`;
    details.open = wasOpen;
    details.append(summary, list);
    box.append(details);
  } else {
    const head = document.createElement('p');
    head.className = 'notes-title';
    head.textContent = title;
    box.append(head, list);
  }
}

function showHeader(project, build) {
  const name = project && typeof project.name === 'string' && project.name ? project.name : 'Untitled model';
  $('name').textContent = name;
  document.title = `${name} · BrickSnap Viewer`;
  const n = state.partCount;
  $('count').textContent = `${n} ${n === 1 ? 'part' : 'parts'}`;
  const rep = $('report');
  rep.classList.remove('ok', 'bad');
  const report = build ? build.report : null;
  if (!build) {
    rep.textContent = 'Not built yet';
  } else if (!report) {
    rep.textContent = 'Not checked yet';
  } else {
    const first = String(report.text || '').split('\n').find((l) => l.trim()) || (report.ok ? 'Check passed' : 'Check found problems');
    rep.textContent = first.trim();
    rep.classList.add(report.ok ? 'ok' : 'bad');
  }
  showNotes(build);
}

function updateStepUi(outlined) {
  const max = state.maxStep;
  const hasSteps = max > 0 && state.partCount > 0;
  slider.disabled = !hasSteps;
  slider.min = '1';
  slider.max = String(Math.max(1, max));
  slider.value = String(hasSteps ? state.step : 1);
  prevBtn.disabled = !hasSteps || (!state.showingAll && state.step <= 1);
  nextBtn.disabled = !hasSteps || state.showingAll;
  allBtn.disabled = !hasSteps;
  allBtn.setAttribute('aria-pressed', String(state.showingAll));
  if (!state.partCount) stepLabel.textContent = 'No parts yet';
  else if (!hasSteps) stepLabel.textContent = 'All parts (no building steps yet)';
  else if (state.showingAll) stepLabel.textContent = `All ${max} steps`;
  else stepLabel.textContent = `Step ${state.step} of ${max} · ${outlined} new ${outlined === 1 ? 'part' : 'parts'}`;
}

slider.addEventListener('input', () => applyStep(Number(slider.value), false));
prevBtn.addEventListener('click', () => {
  if (state.showingAll) applyStep(state.maxStep, false);
  else applyStep(state.step - 1, false);
});
nextBtn.addEventListener('click', () => {
  if (state.step >= state.maxStep) applyStep(state.maxStep, true);
  else applyStep(state.step + 1, false);
});
allBtn.addEventListener('click', () => applyStep(state.maxStep, true));
window.addEventListener('keydown', (e) => {
  if (e.target instanceof HTMLInputElement && e.target.type !== 'range') return;
  if (e.key === 'ArrowLeft' && !prevBtn.disabled) {
    prevBtn.click();
    e.preventDefault();
  } else if (e.key === 'ArrowRight' && !nextBtn.disabled) {
    nextBtn.click();
    e.preventDefault();
  }
});

// ---- loading and live reload --------------------------------------------------------------

async function fetchText(url) {
  const res = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.text();
}

async function fetchJson(url) {
  const text = await fetchText(url);
  return text === null ? null : JSON.parse(text);
}

let project = null;
let lastBuildText; // undefined until the first poll, then the text (or null when missing)
let lastRoughText; // the same for build.rough.json (null when the project has none)
let lastProjectText; // the same for project.json
let currentBuild = null; // the build.json last read, for the header
let fitBuild = { shape: [8, 8, 3] }; // what fitView frames when there are no parts
let unreadable = 0; // polls in a row that found build.json but could not read it
const UNREADABLE_LIMIT = 2; // say so after this many, not on the first (it may be half-written)
const DRAW_FAILED =
  "The viewer could not draw this build. Run 'bricksnap build' again; if that does not help, tell the BrickSnap developers.";

async function loadProject() {
  try {
    project = (await fetchJson(`${PROJECT_URL}/project.json`)) || project;
  } catch {
    // keep the old name
  }
}

function clearModel() {
  disposeDrawn(views.designed);
  state.partCount = 0;
  state.maxStep = 0;
}

function showNoSteps() {
  state.visibleCount = 0;
  state.highlightCount = 0;
  state.step = 0;
  state.showingAll = true;
  updateStepUi(0);
}

/** build.json exists but is not a readable build, poll after poll. */
async function showUnreadable() {
  state.error = 'build.json cannot be read';
  if (views.designed.drawn) {
    setNotice(
      "The newest build.json cannot be read, so this is still the previous build. Run 'bricksnap build' again.",
    );
    return;
  }
  await loadProject();
  fitView({ shape: [8, 8, 3] });
  setNotice("This project's build.json cannot be read. Run 'bricksnap build' again.");
  showHeader(project, null);
  const rep = $('report');
  rep.textContent = 'Cannot read the build';
  rep.classList.add('bad');
  showNoSteps();
}

/** A JSON object from text, or null when the text is missing or not one. */
function parseObject(text) {
  if (text === null || text === undefined) return null;
  try {
    const value = JSON.parse(text);
    return value !== null && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

// ---- versions: what each view draws ----------------------------------------------------------

let hasRoughFile = false; // /project-files.json names build.rough.json
let leftPick = null; // the person's choice for the left view: null (default), 'rough' or a number
let rightPick = null; // and for the right view: null (the current version) or a number
const sources = { left: null, right: 'live' }; // what is drawn: 'rough', 'live', a number or null
const versionTexts = new Map(); // version number -> its build.json text (a version never changes)
let lastSourcesKey = '';
let lastVersionsKey = '';

function versionByN(n) {
  return typeof n === 'number' ? state.versions.find((v) => v.n === n) || null : null;
}

/** Whether build.json, drawn on the right as "live", is version ``v`` (and not a run that is
 * still changing it). */
function liveIsKept(v) {
  const b = currentBuild;
  if (!b || sources.right !== 'live') return true;
  return b.design_id === v.design_id && Array.isArray(b.parts) && b.parts.length === v.parts;
}

/** A version entry from /project-files.json, checked, or null. */
function cleanVersion(v) {
  if (!v || typeof v !== 'object' || !Number.isInteger(v.n) || v.n < 1) return null;
  if (typeof v.build !== 'string' || !/^versions\/[0-9]{4,}\/build\.json$/.test(v.build)) return null;
  const text = (x) => (typeof x === 'string' ? x : '');
  return {
    n: v.n,
    kind: text(v.kind),
    label: text(v.label) || `Version ${v.n}`,
    note: text(v.note),
    created: text(v.created),
    parts: Number.isInteger(v.parts) ? v.parts : 0,
    valid: v.valid === true,
    design_id: text(v.design_id),
    brief: v.brief && typeof v.brief === 'object' && !Array.isArray(v.brief) ? v.brief : null,
    build: v.build,
  };
}

/** Work out what each view draws from the person's choices and what exists. */
function chooseSources() {
  if (!versionByN(rightPick)) rightPick = null;
  if (typeof leftPick === 'number' && !versionByN(leftPick)) leftPick = null;
  sources.right = rightPick !== null && rightPick !== state.current ? rightPick : 'live';
  if (leftPick === 'rough' && hasRoughFile) sources.left = 'rough';
  else if (typeof leftPick === 'number') sources.left = leftPick;
  else if (hasRoughFile) sources.left = 'rough';
  else {
    // no plain conversion: the version before the one on the right
    const right = sources.right === 'live' ? state.current : sources.right;
    const i = state.versions.findIndex((v) => v.n === right);
    sources.left = i > 0 ? state.versions[i - 1].n : null;
  }
  state.choice = { left: sources.left, right: sources.right === 'live' ? state.current : sources.right };
}

/** The two choosers' lists, newest first, and what they show now. */
function fillChoosers() {
  const option = (value, text) => {
    const o = document.createElement('option');
    o.value = value;
    o.textContent = text;
    return o;
  };
  const name = (v) => `${v.n} · ${v.label}${v.n === state.current ? ' (in use)' : ''}`;
  const newest = [...state.versions].reverse();
  const left = newest.map((v) => option(String(v.n), name(v)));
  if (hasRoughFile) left.unshift(option('rough', 'Plain conversion'));
  const right = newest.map((v) => option(String(v.n), name(v)));
  if (state.current === null) right.unshift(option('live', 'The model now'));
  pickLeft.replaceChildren(...left);
  pickRight.replaceChildren(...right);
  if (sources.left === null) pickLeft.selectedIndex = -1;
  else pickLeft.value = String(sources.left);
  pickRight.value = sources.right === 'live' ? String(state.current ?? 'live') : String(sources.right);
}

pickLeft.addEventListener('change', () => {
  leftPick = pickLeft.value === 'rough' ? 'rough' : Number(pickLeft.value);
  state.pollNow();
});
pickRight.addEventListener('change', () => {
  rightPick = pickRight.value === 'live' ? null : Number(pickRight.value);
  state.pollNow();
});

// For tests and the web app's list of versions: show ``value`` in the ``side`` view ('left'
// or 'right'): a version number, 'rough' (left only) or 'default'. Resolves once it is drawn.
state.choose = async (side, value) => {
  const pick = value === 'default' ? null : value === 'rough' ? 'rough' : Number(value);
  if (side === 'left') leftPick = pick;
  else rightPick = pick === 'rough' ? null : pick;
  await state.pollNow();
};

async function versionText(n) {
  if (versionTexts.has(n)) return versionTexts.get(n);
  const v = versionByN(n);
  const text = v ? await fetchText(`${PROJECT_URL}/${v.build}`) : null;
  if (text !== null) versionTexts.set(n, text);
  return text;
}

// ---- look inside ------------------------------------------------------------------------------

const cutSlider = $('cut');
const cutAxis = $('cutAxis');
const cutSays = $('cutSays');
const cutPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const cutPlanes = [cutPlane];
const CUT_WORDS = { y: 'from the front', x: 'from the side', z: 'from the top' };
const cut = { axis: 'y', amount: 0 };

function cutOn() {
  return cut.amount > 0;
}

/** Clip ``mat`` (or stop clipping it), drawing cut parts from both sides so they read as
 * opened up rather than see-through. */
function cutMaterial(mat, on) {
  const planes = on ? cutPlanes : null;
  const side = mat === outlineMat ? THREE.BackSide : on ? THREE.DoubleSide : THREE.FrontSide;
  if (mat.clippingPlanes !== planes || mat.side !== side) {
    mat.clippingPlanes = planes;
    mat.clipShadows = true;
    mat.side = side;
    mat.needsUpdate = true;
  }
}

/** Place the cut through the model's box and put it on every material the model uses. */
function applyCut() {
  const on = cutOn();
  for (const mat of [...materialCache.values(), edgeMat, newEdgeMat, outlineMat]) cutMaterial(mat, on);
  const box = modelBox || new THREE.Box3(new THREE.Vector3(), new THREE.Vector3(1, 1, 1));
  const t = cut.amount;
  const lo = box.min;
  const hi = box.max;
  if (cut.axis === 'x') cutPlane.set(new THREE.Vector3(-1, 0, 0), hi.x - t * (hi.x - lo.x));
  else if (cut.axis === 'z') cutPlane.set(new THREE.Vector3(0, 0, -1), hi.z - t * (hi.z - lo.z));
  else cutPlane.set(new THREE.Vector3(0, 1, 0), -(lo.y + t * (hi.y - lo.y)));
  cutSays.textContent = on ? `Cut ${Math.round(t * 100)}% of the way, ${CUT_WORDS[cut.axis]}` : 'Off: slide to cut the model open';
  requestRender();
}

state.setCut = (amount, axis = cut.axis) => {
  cut.amount = Math.min(1, Math.max(0, Number(amount) || 0));
  if (Object.hasOwn(CUT_WORDS, axis)) cut.axis = axis;
  cutSlider.value = String(Math.round(cut.amount * 100));
  cutAxis.value = cut.axis;
  applyCut();
};
Object.defineProperty(state, 'cut', {
  enumerable: true,
  get: () => ({
    axis: cut.axis,
    amount: cut.amount,
    plane: cutOn() ? [...cutPlane.normal.toArray(), cutPlane.constant] : null,
    clipped: [...materialCache.values(), edgeMat, newEdgeMat, outlineMat].filter((m) => m.clippingPlanes === cutPlanes).length,
  }),
});
cutSlider.addEventListener('input', () => state.setCut(Number(cutSlider.value) / 100));
cutAxis.addEventListener('change', () => state.setCut(cut.amount, cutAxis.value));

// ---- refreshing ---------------------------------------------------------------------------------

/** Look at build.json, build.rough.json, project.json and the versions, and show whatever
 * changed (in either view). */
async function refresh() {
  const [text, files, projectText] = await Promise.all([
    fetchText(`${PROJECT_URL}/build.json`),
    fetchJson(FILES_LIST_URL),
    fetchText(`${PROJECT_URL}/project.json`),
  ]);
  // Only asked for when it is there, so a project without one causes no failed requests.
  hasRoughFile = Boolean(files && Array.isArray(files.files) && files.files.includes('build.rough.json'));
  const listed = files && Array.isArray(files.versions) ? files.versions.map(cleanVersion).filter(Boolean) : [];
  state.versions = listed;
  state.current = files && Number.isInteger(files.current) && versionByN(files.current) ? files.current : null;
  chooseSources();
  const rightText = sources.right === 'live' ? text : await versionText(sources.right);
  let roughText = null;
  if (sources.left === 'rough') roughText = await fetchText(`${PROJECT_URL}/build.rough.json`);
  else if (sources.left !== null) roughText = await versionText(sources.left);
  const sourcesKey = JSON.stringify(sources);
  const versionsKey = JSON.stringify([state.versions, state.current, hasRoughFile]);
  const sourcesChanged = sourcesKey !== lastSourcesKey || versionsKey !== lastVersionsKey;

  const buildChanged = rightText !== lastBuildText;
  const build = buildChanged ? parseObject(rightText) : currentBuild;
  if (buildChanged && rightText !== null && !build) {
    // Probably caught half-written: the next poll will see the whole file. If it stays
    // unreadable, say so rather than showing "Loading" (or an old build) without a word.
    unreadable += 1;
    if (unreadable === UNREADABLE_LIMIT) await showUnreadable();
    return;
  }
  const roughChanged = roughText !== lastRoughText;
  const projectChanged = projectText !== lastProjectText;
  if (!buildChanged && !roughChanged && !projectChanged && !sourcesChanged) return;
  unreadable = 0;
  lastSourcesKey = sourcesKey;
  lastVersionsKey = versionsKey;
  if (projectChanged) {
    lastProjectText = projectText;
    project = parseObject(projectText) || project; // half-written: keep the old one
  }

  let notice = null; // null: leave the notice as it is
  let keep = null;
  if (buildChanged) {
    lastBuildText = rightText;
    currentBuild = build;
    // Keep the step the person was looking at, if it still exists.
    keep = state.showingAll ? null : state.step;
    state.error = null;
    notice = '';
    fitBuild = build || { shape: [8, 8, 3] };
    if (build) {
      try {
        const drawn = drawBuild(build, views.designed);
        if (!state.partCount) notice = 'This build has no parts in it.';
        if (drawn.skipped) {
          const n = drawn.skipped;
          notice = `${n} ${n === 1 ? 'entry' : 'entries'} in build.json ${n === 1 ? 'is' : 'are'} not a part and ${n === 1 ? 'was' : 'were'} left out.`;
        }
      } catch (err) {
        // Whatever went wrong, the screen and the text must agree: show nothing and say why.
        clearModel();
        fitBuild = { shape: [8, 8, 3] };
        state.error = String(err && err.message ? err.message : err);
        notice = DRAW_FAILED;
      }
    } else {
      clearModel();
      notice = "This project has not been built yet. Run 'bricksnap build' and it will appear here.";
    }
  }
  if (roughChanged) {
    lastRoughText = roughText;
    const rough = parseObject(roughText);
    try {
      if (rough) drawBuild(rough, views.rough);
      else disposeDrawn(views.rough);
    } catch {
      disposeDrawn(views.rough); // the plain conversion is extra: without it, show one view
    }
    state.roughVersion += 1;
  }
  const d = views.designed;
  const r = views.rough;
  // A plain conversion with nothing in it to draw counts as none, like one that cannot be read.
  compareActive = Boolean(d.drawn && r.drawn && r.drawn.parts.length && r.partsJson !== d.partsJson);
  if (state.versions.length) fillChoosers();
  showCompare();
  if (buildChanged || roughChanged) {
    try {
      fitView(fitBuild);
    } catch (err) {
      clearModel();
      state.error = String(err && err.message ? err.message : err);
      notice = DRAW_FAILED;
    }
  }
  if (notice !== null) setNotice(notice);
  showHeader(project, currentBuild);
  const shownVersion = sources.right === 'live' ? null : versionByN(sources.right);
  showBrief(shownVersion ? shownVersion.brief : project ? project.brief : null);
  nameViews();
  applyCut();
  if (buildChanged) {
    if (d.drawn) applyStep(keep ?? state.maxStep, keep === null || keep > state.maxStep);
    else showNoSteps();
    state.buildVersion += 1;
  }
  requestRender();
}

let polling = false;
async function poll() {
  if (polling) return;
  polling = true;
  try {
    await refresh();
  } catch {
    // the server may be restarting; try again next time
  } finally {
    polling = false;
  }
}

// For tests: look at build.json now instead of at the next regular poll; resolves when done.
state.pollNow = async () => {
  while (polling) await new Promise((resolve) => setTimeout(resolve, 20));
  await poll();
};

async function start() {
  try {
    const [partsJson, coloursJson] = await Promise.all([
      fetchJson('/catalog/parts.json'),
      fetchJson('/catalog/colours.json'),
    ]);
    loadCatalogue(partsJson || [], coloursJson || []);
    await refresh();
    // A build.json that cannot be read is looked at again soon, so a truly broken one is
    // reported within a moment instead of after the next regular poll.
    if (unreadable) setTimeout(poll, 400);
  } catch (err) {
    state.error = String(err && err.message ? err.message : err);
    setNotice('The viewer could not load this project. Is the viewer server still running?');
  }
  // Wait for the first frame so a test that sees ready can take a picture straight away.
  requestAnimationFrame(() => {
    renderViews();
    state.ready = true;
  });
  setInterval(poll, POLL_MS);
}

start();
