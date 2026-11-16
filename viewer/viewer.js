// BrickSnap 3D viewer. Plain ES module, no build step. Served by bricksnap/viewserver.py.
//
// Reads /project/project.json, /project/build.json (Build.to_json in bricksnap/types.py),
// /catalog/parts.json and /catalog/colours.json, and draws every part as a box with studs.
// Grid conventions (docs/ARCHITECTURE.md): a cell is 8 x 8 x 3.2 mm, x right, y back, z up.
// Footprints and stud positions follow bricksnap/catalog/__init__.py (footprint, local_to_cell).
//
// Any text that comes from the files goes into the page with textContent, never innerHTML.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const CELL = { x: 8, y: 8, z: 3.2 }; // millimetres
const GAP = 0.4; // mm left between neighbouring parts so each one stands out
const GAP_Z = 0.2;
const STUD_R = 2.4; // stud diameter 4.8 mm
const STUD_H = 1.7;
const FALLBACK_RGB = '#9BA19D';
const OUTLINE_MM = 0.7; // thickness of the highlight around the current step's parts
const HIGHLIGHT = '#ff3d7f';
const POLL_MS = 2000;
const SKY_HAZE = 0xdcecf8; // close to the page's sky gradient near the horizon

const $ = (id) => document.getElementById(id);

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
  error: null,
};
window.__bricksnap = state;

// ---- three.js scene ---------------------------------------------------------------------

const container = $('view');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(40, 1, 1, 20000);
camera.up.set(0, 0, 1); // z is up
camera.position.set(150, -250, 180);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = false;
controls.screenSpacePanning = true;
controls.addEventListener('change', requestRender);

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

// Shared unit geometries: every instance is a scaled and moved copy.
const boxGeo = new THREE.BoxGeometry(1, 1, 1);
const studGeo = new THREE.CylinderGeometry(STUD_R, STUD_R, STUD_H, 20);
studGeo.rotateX(Math.PI / 2); // cylinder axis along z

const modelGroup = new THREE.Group();
scene.add(modelGroup);

let fitted = null; // {centre, radius, portrait}: what placeCamera last framed (see fitView)
let renderQueued = false;
function requestRender() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    renderer.render(scene, camera);
  });
}

function resize() {
  const w = Math.max(1, container.clientWidth);
  const h = Math.max(1, container.clientHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  // Turning a phone or tablet between portrait and landscape changes which side limits the
  // view, so frame the model again.
  if (fitted && fitted.portrait !== camera.aspect < 1) placeCamera();
  requestRender();
}
new ResizeObserver(resize).observe(container);
resize();

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
    partsById.set(String(p.id), {
      sx,
      sz,
      h: Number(p.h_plates) || 1,
      studs: Array.isArray(studs) ? studs.map(([a, b]) => [Number(a), Number(b)]) : [],
      name: String(p.name || p.id),
    });
  }
  colourByCode = new Map();
  for (const c of coloursJson) {
    colourByCode.set(Number(c.ldraw_code), {
      rgb: typeof c.rgb === 'string' && /^#[0-9a-fA-F]{6}$/.test(c.rgb) ? c.rgb : FALLBACK_RGB,
      transparent: Boolean(c.transparent),
    });
  }
}

const UNKNOWN_PART = { sx: 1, sz: 1, h: 3, studs: [], name: 'unknown part' };

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

let drawn = null; // what is in modelGroup now; see drawBuild

function disposeDrawn() {
  if (!drawn) return;
  for (const obj of [...modelGroup.children]) {
    modelGroup.remove(obj);
    if (obj.geometry && obj.geometry !== boxGeo && obj.geometry !== studGeo) obj.geometry.dispose();
    if (obj.material) obj.material.dispose();
    if (obj.isInstancedMesh) obj.dispose();
  }
  drawn = null;
}

function makeMaterial(colour) {
  const opts = { color: new THREE.Color(colour.rgb) };
  if (colour.transparent) Object.assign(opts, { transparent: true, opacity: 0.55, depthWrite: false });
  return new THREE.MeshLambertMaterial(opts);
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

function drawBuild(build) {
  disposeDrawn();
  const all = Array.isArray(build.parts) ? build.parts : [];
  // Anything in "parts" that is not an object (null, a number, a list) cannot be a part.
  const raw = all.filter((p) => p !== null && typeof p === 'object' && !Array.isArray(p));
  // Normalise every placement and work out its box once.
  const parts = raw.map((p, index) => {
    const part = partsById.get(String(p.part)) || UNKNOWN_PART;
    const rot = normRot(p.rot);
    const [w, d, h] = footprint(part, rot);
    const x = Number(p.x) || 0;
    const y = Number(p.y) || 0;
    const z = Number(p.z) || 0;
    const code = Number(p.color);
    return { index, part, rot, w, d, h, x, y, z, code, step: Math.max(0, Number(p.step) || 0) };
  });
  // Stable sort by step so "parts with step <= N" is always a prefix.
  parts.sort((a, b) => a.step - b.step || a.index - b.index);

  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const pos = new THREE.Vector3();
  const scl = new THREE.Vector3();

  const boxMatrix = (p, grow = 0) => {
    pos.set((p.x + p.w / 2) * CELL.x, (p.y + p.d / 2) * CELL.y, (p.z + p.h / 2) * CELL.z);
    scl.set(
      p.w * CELL.x - GAP + 2 * grow,
      p.d * CELL.y - GAP + 2 * grow,
      p.h * CELL.z - GAP_Z + 2 * grow,
    );
    return m.compose(pos, q, scl);
  };

  // Group by colour. Each group keeps parts and studs in step order.
  const groups = new Map();
  for (const p of parts) {
    let g = groups.get(p.code);
    if (!g) {
      g = { code: p.code, parts: [], studs: [] };
      groups.set(p.code, g);
    }
    g.parts.push(p);
    if (p.rot === 0 || p.rot === 90 || p.rot === 180 || p.rot === 270) {
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
    const colour = colourByCode.get(g.code) || { rgb: FALLBACK_RGB, transparent: false };
    const mat = makeMaterial(colour);
    const body = new THREE.InstancedMesh(boxGeo, mat, g.parts.length);
    g.parts.forEach((p, i) => body.setMatrixAt(i, boxMatrix(p)));
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
        studs.setMatrixAt(i, m.compose(pos, q, scl));
      });
      studs.instanceMatrix.needsUpdate = true;
      studs.castShadow = !colour.transparent;
      studs.receiveShadow = true;
      studs.frustumCulled = false;
      modelGroup.add(studs);
      studSteps = g.studs.map((s) => s.step);
    }
    meshes.push({ body, bodySteps, studs, studSteps });
  }

  // Thin dark edges on every part, in step order so a draw range shows a prefix.
  const edgePositions = new Float32Array(parts.length * 24 * 3);
  const corner = (p, i, j, k) => [
    p.x * CELL.x + GAP / 2 + i * (p.w * CELL.x - GAP),
    p.y * CELL.y + GAP / 2 + j * (p.d * CELL.y - GAP),
    p.z * CELL.z + GAP_Z / 2 + k * (p.h * CELL.z - GAP_Z),
  ];
  const EDGES = [
    [0, 0, 0, 1, 0, 0], [0, 1, 0, 1, 1, 0], [0, 0, 1, 1, 0, 1], [0, 1, 1, 1, 1, 1],
    [0, 0, 0, 0, 1, 0], [1, 0, 0, 1, 1, 0], [0, 0, 1, 0, 1, 1], [1, 0, 1, 1, 1, 1],
    [0, 0, 0, 0, 0, 1], [1, 0, 0, 1, 0, 1], [0, 1, 0, 0, 1, 1], [1, 1, 0, 1, 1, 1],
  ];
  let o = 0;
  for (const p of parts) {
    for (const [a, b, c, d, e, f] of EDGES) {
      edgePositions.set(corner(p, a, b, c), o);
      edgePositions.set(corner(p, d, e, f), o + 3);
      o += 6;
    }
  }
  const edgeGeo = new THREE.BufferGeometry();
  edgeGeo.setAttribute('position', new THREE.BufferAttribute(edgePositions, 3));
  const edges = new THREE.LineSegments(
    edgeGeo,
    new THREE.LineBasicMaterial({ color: 0x1b1b1b, transparent: true, opacity: 0.45 }),
  );
  edges.frustumCulled = false;
  modelGroup.add(edges);

  // The current step's edges in the highlight colour: a second geometry sharing the same
  // vertices, whose draw range picks out that step's parts. Drawn after the dark edges.
  const newEdgeGeo = new THREE.BufferGeometry();
  newEdgeGeo.setAttribute('position', edgeGeo.getAttribute('position'));
  newEdgeGeo.setDrawRange(0, 0);
  const newEdges = new THREE.LineSegments(newEdgeGeo, new THREE.LineBasicMaterial({ color: HIGHLIGHT }));
  newEdges.frustumCulled = false;
  newEdges.renderOrder = 1;
  modelGroup.add(newEdges);

  // Highlight: a slightly larger box drawn inside-out behind the current step's parts,
  // which shows as a thick coloured outline.
  const outline = new THREE.InstancedMesh(
    boxGeo,
    new THREE.MeshBasicMaterial({ color: HIGHLIGHT, side: THREE.BackSide }),
    Math.max(1, parts.length),
  );
  outline.count = 0;
  outline.frustumCulled = false;
  modelGroup.add(outline);

  const steps = parts.map((p) => p.step);
  drawn = { parts, steps, meshes, edges, newEdges, outline, boxMatrix, skipped: all.length - raw.length };
  state.partCount = parts.length;
  state.maxStep = parts.length ? parts[parts.length - 1].step : 0;
}

/** Show parts with step <= n (all of them when showAll), outlining step n. */
function applyStep(n, showAll) {
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
  drawn.edges.geometry.setDrawRange(0, visible * 24);

  let k = 0;
  if (!showAll) {
    const first = upperBound(drawn.steps, n - 1);
    for (let i = first; i < visible; i++) {
      drawn.outline.setMatrixAt(k++, drawn.boxMatrix(drawn.parts[i], OUTLINE_MM));
    }
    drawn.outline.instanceMatrix.needsUpdate = true;
    drawn.newEdges.geometry.setDrawRange(first * 24, k * 24);
  } else {
    drawn.newEdges.geometry.setDrawRange(0, 0);
  }
  drawn.outline.count = k;

  state.step = n;
  state.showingAll = showAll;
  state.visibleCount = visible;
  state.highlightCount = k;
  updateStepUi(k);
  requestRender();
}

// For tests: what is drawn right now, in world millimetres after every transform, so it can
// be compared with the Python catalogue. Only instances currently shown are listed. Each
// entry is the axis-aligned box {min: [x, y, z], max: [x, y, z]} the instance covers.
// ndc: where the shown model falls in the view, -1..1 on each axis being inside it.
state.inspect = () => {
  const out = { bodies: [], studs: [], outlines: [], highlightEdgeParts: 0, outlineColour: null, ndc: null };
  if (!drawn) return out;
  scene.updateMatrixWorld(true);
  camera.updateMatrixWorld(true);
  const m = new THREE.Matrix4();
  const box = new THREE.Box3();
  const whole = new THREE.Box3();
  const aabb = (mesh, i) => {
    if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
    mesh.getMatrixAt(i, m);
    m.premultiply(mesh.matrixWorld);
    box.copy(mesh.geometry.boundingBox).applyMatrix4(m);
    return { min: box.min.toArray(), max: box.max.toArray() };
  };
  for (const g of drawn.meshes) {
    const colour = `#${g.body.material.color.getHexString()}`;
    for (let i = 0; i < g.body.count; i++) {
      out.bodies.push({ ...aabb(g.body, i), colour, step: g.bodySteps[i] });
      whole.union(box);
    }
    if (g.studs) {
      for (let i = 0; i < g.studs.count; i++) {
        out.studs.push({ ...aabb(g.studs, i), colour, step: g.studSteps[i] });
        whole.union(box);
      }
    }
  }
  for (let i = 0; i < drawn.outline.count; i++) out.outlines.push(aabb(drawn.outline, i));
  out.outlineColour = `#${drawn.outline.material.color.getHexString()}`;
  out.highlightEdgeParts = drawn.newEdges.geometry.drawRange.count / 24;
  if (!whole.isEmpty()) {
    const ndc = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
    const v = new THREE.Vector3();
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

/** Put the camera in front of the model, far enough away to see all of it. */
function placeCamera() {
  const { centre, radius } = fitted;
  // The sphere around the model must fit both the height and the width of the view; on a
  // portrait screen the width is the tighter one.
  const halfV = THREE.MathUtils.degToRad(camera.fov / 2);
  const halfH = Math.atan(Math.tan(halfV) * camera.aspect);
  const dist = (radius / Math.sin(Math.min(halfV, halfH))) * 1.05;
  fitted.portrait = camera.aspect < 1;
  // In front (y < 0), a little to the right and above.
  const dir = new THREE.Vector3(0.55, -1, 0.7).normalize();
  camera.position.copy(centre).addScaledVector(dir, dist);
  camera.near = Math.max(0.5, dist / 100);
  camera.far = dist * 40;
  camera.updateProjectionMatrix();
  // Fade the far ground into the sky so there is no hard edge at the horizon.
  scene.fog = new THREE.Fog(SKY_HAZE, dist * 1.6, dist * 7);
  controls.target.copy(centre);
  controls.update();
  requestRender();
}

function fitView(build) {
  let nx = 0;
  let ny = 0;
  let nz = 0;
  if (Array.isArray(build.shape) && build.shape.length === 3) [nx, ny, nz] = build.shape.map(Number);
  if (drawn && drawn.parts.length) {
    for (const p of drawn.parts) {
      nx = Math.max(nx, p.x + p.w);
      ny = Math.max(ny, p.y + p.d);
      nz = Math.max(nz, p.z + p.h);
    }
  }
  nx = Math.max(nx, 4);
  ny = Math.max(ny, 4);
  nz = Math.max(nz, 3);
  const size = new THREE.Vector3(nx * CELL.x, ny * CELL.y, nz * CELL.z);
  const centre = size.clone().multiplyScalar(0.5);
  const radius = Math.max(size.length() / 2, 20);

  // Ground: a big plane just under z = 0, with a faint stud grid under the model.
  const span = radius * 80;
  ground.scale.set(span, span, 1);
  ground.position.set(centre.x, centre.y, -0.05);
  if (grid) {
    scene.remove(grid);
    grid.geometry.dispose();
    grid.material.dispose();
  }
  const gridCells = Math.ceil(Math.max(nx, ny) / 2) * 2 + 8;
  grid = new THREE.GridHelper(gridCells * CELL.x, gridCells, 0xc9c2ad, 0xd9d3c0);
  grid.rotation.x = Math.PI / 2; // GridHelper lies in x-z; turn it into x-y
  grid.position.set(centre.x, centre.y, 0);
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

  // Camera: framed again only when the model's size changes, so a rebuild of the same
  // size keeps the angle the person turned it to.
  const key = `${nx}x${ny}x${nz}`;
  if (key !== fittedFor) {
    fittedFor = key;
    fitted = { centre, radius, portrait: camera.aspect < 1 };
    placeCamera();
  }
  requestRender();
}

// ---- page text ----------------------------------------------------------------------------

const slider = $('step');
const prevBtn = $('prev');
const nextBtn = $('next');
const allBtn = $('all');
const stepLabel = $('stepLabel');

function setNotice(text) {
  const el = $('notice');
  el.textContent = text || '';
  el.hidden = !text;
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
let unreadable = 0; // polls in a row that found build.json but could not read it
const UNREADABLE_LIMIT = 2; // say so after this many, not on the first (it may be half-written)

async function loadProject() {
  try {
    project = (await fetchJson('/project/project.json')) || project;
  } catch {
    // keep the old name
  }
}

function clearModel() {
  disposeDrawn();
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
  if (drawn) {
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

async function refresh() {
  const text = await fetchText('/project/build.json');
  if (text === lastBuildText) return;
  let build = null;
  if (text !== null) {
    try {
      build = JSON.parse(text);
    } catch {
      build = undefined;
    }
    if (build === null || typeof build !== 'object' || Array.isArray(build)) {
      // Probably caught half-written: the next poll will see the whole file. If it stays
      // unreadable, say so rather than showing "Loading" (or an old build) without a word.
      unreadable += 1;
      if (unreadable === UNREADABLE_LIMIT) await showUnreadable();
      return;
    }
  }
  unreadable = 0;
  lastBuildText = text;
  await loadProject();
  // Keep the step the person was looking at, if it still exists.
  const keep = state.showingAll ? null : state.step;
  state.error = null;
  let notice = '';
  if (build) {
    try {
      drawBuild(build);
      fitView(build);
      if (!state.partCount) notice = 'This build has no parts in it.';
      if (drawn.skipped) {
        const n = drawn.skipped;
        notice = `${n} ${n === 1 ? 'entry' : 'entries'} in build.json ${n === 1 ? 'is' : 'are'} not a part and ${n === 1 ? 'was' : 'were'} left out.`;
      }
    } catch (err) {
      // Whatever went wrong, the screen and the text must agree: show nothing and say why.
      clearModel();
      fitView({ shape: [8, 8, 3] });
      state.error = String(err && err.message ? err.message : err);
      notice = "The viewer could not draw this build. Run 'bricksnap build' again; if that does not help, tell the BrickSnap developers.";
    }
  } else {
    clearModel();
    fitView({ shape: [8, 8, 3] });
    notice = "This project has not been built yet. Run 'bricksnap build' and it will appear here.";
  }
  setNotice(notice);
  showHeader(project, build);
  if (drawn) applyStep(keep ?? state.maxStep, keep === null || keep > state.maxStep);
  else showNoSteps();
  state.buildVersion += 1;
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
    renderer.render(scene, camera);
    state.ready = true;
  });
  setInterval(poll, POLL_MS);
}

start();
