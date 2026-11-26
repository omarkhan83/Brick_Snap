// BrickSnap web app: the home page. One prompt bar at the top that lets the AI build a model
// from parts (a "free build", experimental) from words, pictures and a 3D model; the person's
// models as cards below it, free builds first and newest first; and, folded away, the older
// form that turns a 3D model file into bricks. Text from the server goes in with textContent.

import { FREE_DEFAULT_MODEL, FREE_MODELS, JobView, freeEstimate, freePolishEstimate, freePolishTimeAndCost, NOT_ANSWERING, TOKEN, appState, el, freeTimeAndCost, getJson, plural, postJson, refusal, sleep } from './app.js';

const MAX_UPLOAD_MB = 60;
const SUFFIXES = ['.stl', '.obj', '.glb', '.gltf', '.3mf', '.ply'];
const $ = (id) => document.getElementById(id);

const form = $('newForm');
const fileInput = $('model');
const studs = $('studs');
const goBtn = $('go');
const formMsg = $('formMsg');
const newJobs = $('newJobs');
const followed = new Set(); // job ids shown on this page
let anyActive = false;
let uploading = false; // a file is being sent from this page; its job is followed when it starts

// ---- the size ----

function showSize() {
  const n = Number(studs.value);
  $('studsOut').textContent = `${n} studs`;
  const cm = (n * 0.8).toFixed(1);
  $('studsHint').textContent =
    `About ${cm} cm along its longest side.` + (n > 48 ? ' Big models have many more parts and take longer to make.' : '');
}
studs.addEventListener('input', showSize);
showSize();

// ---- the list ----

function card(p) {
  const free = p.kind === 'free';
  const pic = el('div', { className: 'pic' });
  if (p.picture) {
    const alt = free ? `Picture of ${p.name}, built by the AI from parts` : `Picture of ${p.name}: the model beside its bricks`;
    pic.append(el('img', { src: p.picture, alt, loading: 'lazy' }));
  } else {
    pic.append(el('span', { className: 'none', text: p.job ? 'The AI is building it…' : 'No picture yet' }));
  }
  const badges = el('div', { className: 'badges' });
  if (p.job) badges.append(el('span', { className: 'badge busy', text: 'Working on it…' }));
  if (free) {
    if (p.problem) badges.append(el('span', { className: 'badge bad', text: 'Damaged' }));
    else if (p.valid === true) badges.append(el('span', { className: 'badge ok', text: 'Checked: no problems' }));
    else if (typeof p.problems === 'number' && p.problems > 0) badges.append(el('span', { className: 'badge bad', text: plural(p.problems, 'problem') }));
    else if (!p.job) badges.append(el('span', { className: 'badge', text: 'Not built yet' }));
    badges.append(el('span', { className: 'badge exp', text: 'Experimental' }));
    const body = el('div', { className: 'body' }, [
      el('h3', { className: 'pname', text: p.name }),
      el('p', { className: 'facts', text: [typeof p.parts === 'number' ? plural(p.parts, 'part') : null, 'Built by the AI, part by part'].filter(Boolean).join(' · ') }),
      p.problem ? el('p', { className: 'facts', text: p.problem }) : null,
      badges,
    ]);
    const link = el('a', { className: 'open', href: `/p/${encodeURIComponent(p.project)}` }, [pic, body]);
    return el('li', { className: 'pcard free', dataset: { project: p.project, kind: 'free' } }, [link]);
  }
  if (p.problem) badges.append(el('span', { className: 'badge bad', text: 'Damaged' }));
  else if (p.valid === true) badges.append(el('span', { className: 'badge ok', text: 'Holds together' }));
  else if (p.valid === false) badges.append(el('span', { className: 'badge bad', text: 'Needs work' }));
  else badges.append(el('span', { className: 'badge', text: 'Not built yet' }));
  const facts = [];
  if (typeof p.parts === 'number') facts.push(plural(p.parts, 'part'));
  if (typeof p.studs === 'number') facts.push(`${p.studs} studs`);
  const body = el('div', { className: 'body' }, [
    el('h3', { className: 'pname', text: p.name }),
    facts.length ? el('p', { className: 'facts', text: facts.join(' · ') }) : null,
    p.problem ? el('p', { className: 'facts', text: p.problem }) : null,
    badges,
  ]);
  const link = el('a', { className: 'open', href: `/p/${encodeURIComponent(p.project)}` }, [pic, body]);
  return el('li', { className: 'pcard', dataset: { project: p.project } }, [link]);
}

let lastList = '';
function showProjects(list) {
  const key = JSON.stringify(list.projects);
  $('loading').hidden = true;
  const none = list.projects.length === 0;
  $('empty').hidden = !none;
  $('grid').classList.toggle('empty', none);
  $('models').hidden = none && followed.size > 0;
  if (key !== lastList) {
    lastList = key;
    const free = list.projects.filter((p) => p.kind === 'free');
    const other = list.projects.filter((p) => p.kind !== 'free');
    $('cards').replaceChildren(...[...free, ...other].map(card)); // each newest first
  }
  // A new model that is being made (started here or before this page was opened).
  for (const job of list.jobs) {
    if (job.kind === 'new' && !followed.has(job.id) && !uploading) followNew(job.id);
    if (job.kind === 'free' && !followed.has(job.id) && !freeSending) followFree(job.id);
  }
  anyActive = list.jobs.length > 0;
  showLimits(list.limits || []);
}

async function loadProjects() {
  const answer = await getJson('/api/projects');
  if (answer.status === 200 && answer.data) {
    showProjects(answer.data);
    if (formMsg.textContent === NOT_ANSWERING) formMsg.textContent = '';
  } else {
    $('loading').hidden = true;
    formMsg.textContent = NOT_ANSWERING;
  }
}

// ---- making a new model ----

function openButton(job) {
  if (job.state !== 'done' || !job.result || !job.result.project) return null;
  const link = el('a', {
    className: 'button primary',
    href: `/p/${encodeURIComponent(job.result.project)}`,
    text: 'Open your model',
  });
  return el('div', { className: 'next' }, [link]);
}

// ---- a file that holds several separate pieces ----

function studsText(n) {
  return n >= 10 ? String(Math.round(n)) : String(Number(n.toFixed(1)));
}

function dims(size) {
  return `${size.map(studsText).join(' × ')} studs`;
}

/** What a new model shows while it waits for the person to choose which piece to build. */
function choosePiece(job) {
  const info = job.pieces || { count: 0, more: 0, small_bits: 0, pieces: [], studs: 0, source: '' };
  const pieces = Array.isArray(info.pieces) ? info.pieces : [];
  const first = pieces[0];
  const longest = first ? Math.max(...first.within) : 0;
  const total = pieces.length + (info.more || 0);
  const msg = el('p', { className: 'formmsg', id: 'piecesMsg', role: 'alert' });
  const radio = (value, id, checked) => el('input', { type: 'radio', name: `piece-${job.id}`, value, id, checked });
  const options = pieces.map((p) => {
    const id = `piece-${job.id}-${p.number}`;
    const swatch = el('span', { className: 'swatch', 'aria-hidden': 'true' });
    swatch.style.background = /^#[0-9a-f]{6}$/.test(p.colour || '') ? p.colour : '#999';
    return el('label', { className: 'way piece', for: id }, [
      radio(String(p.number), id, p.number === 1),
      el('span', {}, [
        el('strong', {}, [swatch, document.createTextNode(p.number === 1 ? `Piece 1 alone, the largest` : `Piece ${p.number} alone`)]),
        el('span', { className: 'wayline', text: `Built on its own: ${dims(p.alone)}.` }),
      ]),
    ]);
  });
  const allId = `piece-${job.id}-all`;
  options.push(
    el('label', { className: 'way piece', for: allId }, [
      radio('all', allId, false),
      el('span', {}, [
        el('strong', { text: 'Everything together, as it is' }),
        el('span', {
          className: 'wayline',
          text: `All ${total} pieces in one model, ${info.studs} studs across${longest ? `: the largest piece about ${studsText(longest)} studs long` : ''}.`,
        }),
      ]),
    ]),
  );
  const extras = [];
  if (info.more) extras.push(`There ${info.more === 1 ? 'is 1 smaller piece' : `are ${info.more} smaller pieces`}, built only with everything together.`);
  if (info.small_bits) extras.push(`${plural(info.small_bits, 'small bit')} ${info.small_bits === 1 ? 'is' : 'are'} left out when one piece is built alone.`);
  const build = el('button', { type: 'button', className: 'primary', id: 'piecesGo', text: 'Build it' });
  const cancel = el('button', { type: 'button', className: 'quiet', id: 'piecesCancel', text: 'Cancel, build nothing' });
  const box = el('div', { className: 'pieces', id: 'pieces' }, [
    el('h3', { text: `This file looks like ${total} separate pieces` }),
    el('p', {
      className: 'lead',
      text: `${info.source || 'This file'} looks like pieces laid out side by side, like the parts of a kit set out for 3D printing, rather than one object. Built all together at ${info.studs} studs, the largest piece would be about ${studsText(longest)} studs long; built alone, it would be ${info.studs}.`,
    }),
    job.picture
      ? el('img', { className: 'pieces-pic', src: job.picture, alt: 'The file seen from above, each piece in its own colour with its number on it.' })
      : null,
    el('fieldset', { className: 'ways' }, [el('legend', { text: 'What should BrickSnap build? The numbers match the picture.' }), ...options]),
    extras.length ? el('p', { className: 'hint-line', text: extras.join(' ') }) : null,
    el('p', {
      className: 'hint-line',
      id: 'piecesSide',
      text: 'If the picture shows the pieces from the side rather than from above, the file probably lies on its side: press “Cancel”, choose “Which way is up in the file” under “More choices”, and send it again.',
    }),
    el('div', { className: 'row' }, [build, cancel]),
    el('p', {
      className: 'hint-line',
      text: `BrickSnap waits ${info.wait_minutes === 60 || !info.wait_minutes ? 'an hour' : `${info.wait_minutes} minutes`} for your answer; after that, choose the file again.`,
    }),
    msg,
  ]);
  async function send(body) {
    build.disabled = true;
    cancel.disabled = true;
    msg.textContent = '';
    const answer = await postJson(`/api/jobs/${encodeURIComponent(job.id)}/choose`, body);
    if (answer.status !== 200) {
      build.disabled = false;
      cancel.disabled = false;
      msg.textContent = refusal(answer);
      appState.message = msg.textContent;
    }
  }
  build.addEventListener('click', () => {
    const chosen = box.querySelector(`input[name="piece-${job.id}"]:checked`);
    const value = chosen ? chosen.value : '1';
    send({ piece: value === 'all' ? 'all' : Number(value) });
  });
  cancel.addEventListener('click', () => send({ cancel: true }));
  return box;
}

function followNew(id, view = null) {
  followed.add(id);
  $('older').open = true; // a model being made from a file shows where its form is
  const v = view || new JobView(newJobs, { nextStep: openButton, onDone: () => loadProjects(), choose: choosePiece });
  if (view) {
    view.nextStep = openButton;
    view.onDone = () => loadProjects();
    view.choose = choosePiece;
  }
  v.follow(id);
}

function problem(text) {
  formMsg.textContent = text;
  appState.message = text;
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  problem('');
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    problem('Choose a 3D model file first.');
    fileInput.focus();
    return;
  }
  const dot = file.name.lastIndexOf('.');
  const suffix = dot >= 0 ? file.name.slice(dot).toLowerCase() : '';
  if (!SUFFIXES.includes(suffix)) {
    problem(`BrickSnap cannot open ${file.name}. Please choose a 3D model file: STL, OBJ, GLB, GLTF, 3MF or PLY.`);
    return;
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    problem(
      `The file is too large: BrickSnap takes model files of up to ${MAX_UPLOAD_MB} MB. Save a simpler version of the model in your 3D program (fewer triangles) and try again.`,
    );
    return;
  }
  if (file.size === 0) {
    problem(`${file.name} is empty. Choose another file.`);
    return;
  }
  const data = new FormData();
  data.append('studs', studs.value);
  data.append('name', $('name').value);
  if ($('hollow').checked) data.append('hollow', '1');
  if ($('up').value) data.append('up', $('up').value);
  data.append('model', file, file.name);

  goBtn.disabled = true;
  uploading = true;
  const view = new JobView(newJobs);
  view.sending(0);
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/projects');
  xhr.setRequestHeader('X-BrickSnap-Token', TOKEN);
  xhr.responseType = 'json';
  xhr.upload.onprogress = (ev) => {
    if (ev.lengthComputable) view.sending(ev.loaded / ev.total);
  };
  xhr.onload = () => {
    goBtn.disabled = false;
    uploading = false;
    const answer = { status: xhr.status, data: xhr.response };
    if (xhr.status === 202 && xhr.response && xhr.response.job) {
      form.reset();
      showSize();
      followNew(xhr.response.job, view);
      loadProjects();
    } else {
      view.remove();
      problem(refusal(answer));
    }
  };
  xhr.onerror = () => {
    goBtn.disabled = false;
    uploading = false;
    view.remove();
    problem(NOT_ANSWERING);
  };
  xhr.send(data);
});

// ---- the prompt bar: the AI builds a model from parts (experimental) ----
//
// Words, up to four pictures and one 3D model, all sent together as one form to /api/free.
// The agreement the server requires (understood, understood_runs) is the box under the bar:
// the line above it always says what Build sends, that it is one AI run, which Claude, how
// long it usually takes and what it uses of the subscription; once ticked it is remembered
// in this browser, so later builds start with one press.

const freeForm = $('freeForm');
const freeWords = $('freeWords');
const freeParts = $('freeParts');
const freeGuide = $('freeGuide');
const freePolish = $('freePolish');
const freeModel = $('freeModel');
const freeFiles = $('freeFiles');
const freeDrop = $('freeDrop');
const freeThumbs = $('freeThumbs');
const freeUnderstood = $('freeUnderstood');
const freeGo = $('freeGo');
const freeMsg = $('freeMsg');
const freeJobs = $('freeJobs');
const MAX_PICTURES = 4;
const MAX_PICTURE_MB = 8;
const MAX_PICTURES_MB = 20;
const PICTURE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const PICTURE_SUFFIXES = ['.jpg', '.jpeg', '.png', '.webp'];
const AGREED_KEY = 'bricksnap.freeUnderstood';
let freeSending = false;
const chosen = { pictures: [], model: null }; // File objects, with a preview address each
appState.chosen = chosen;

function suffixOf(name) {
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

function freeProblem(text) {
  freeMsg.textContent = text;
  appState.message = text;
}

function showParts() {
  const n = Number(freeParts.value);
  $('freePartsOut').textContent = `${n} parts`;
  const size =
    n <= 60
      ? 'A small model.'
      : n <= 140
        ? 'A medium model, like a small set.'
        : 'A big model: big models take longer and use more of your subscription.';
  $('freePartsHint').textContent = size;
  showSays();
}

/** The line under the bar: what Build sends and starts, and what it usually costs. */
function showSays() {
  const n = chosen.pictures.length;
  const what = [];
  if (freeWords.value.trim()) what.push('your words');
  if (n) what.push(`your ${n === 1 ? 'picture' : `${n} pictures`}`);
  if (chosen.model) what.push(`pictures of ${chosen.model.file.name} from five sides`);
  const sends = what.length > 1 ? `${what.slice(0, -1).join(', ')} and ${what[what.length - 1]}` : what[0] || 'your words';
  const model = freeModel.value;
  const parts = Number(freeParts.value);
  const e = freeEstimate(parts, model);
  const way = freeGuide.checked ? ', designed first' : '';
  const guess = model !== FREE_DEFAULT_MODEL || e.estimated ? ' (an estimate)' : '';
  $('freeSends').textContent = `Build sends ${sends} to Anthropic through Claude Code; nothing else leaves this computer.`;
  const added = freePolishEstimate(parts, model);
  $('freePolishHint').textContent = `After the build, an outside eye (a separate AI shown only the pictures) lists up to five fixes, and the AI makes them as one change. It roughly doubles the time and the cost: it adds about ${added.minutes[0]} to ${added.minutes[1]} minutes and $${added.dollars[0]} to $${added.dollars[1]} (an estimate).`;
  if (freePolish.checked) {
    const both = freePolishEstimate(parts, model, true);
    $('freeCost').textContent = `Three AI runs by ${FREE_MODELS[model] || model}${way}, then polished once: usually ${both.minutes[0]} to ${both.minutes[1]} minutes, about $${both.dollars[0]} to $${both.dollars[1]} of your Claude subscription (an estimate).`;
    $('freeCostFull').textContent = `${freeTimeAndCost(parts, model)} Then, to polish it: ${freePolishTimeAndCost(parts, model)}`;
    return;
  }
  $('freeCost').textContent = `One AI run by ${FREE_MODELS[model] || model}${way}: usually ${e.minutes[0]} to ${e.minutes[1]} minutes, about $${e.dollars[0]} to $${e.dollars[1]} of your Claude subscription${guess}.`;
  $('freeCostFull').textContent = freeTimeAndCost(parts, model);
}

// ---- which Claude: the person's last choice, unless it is at its usage limit ----

const MODEL_KEY = 'bricksnap.freeModel';
let modelChosenHere = false;
let limited = new Map();

function rememberedModel() {
  try {
    const value = window.localStorage.getItem(MODEL_KEY);
    return FREE_MODELS[value] ? value : FREE_DEFAULT_MODEL;
  } catch {
    return FREE_DEFAULT_MODEL;
  }
}

/** The server's list of models at a usage limit: the bar chooses the other one, and says why. */
function showLimits(list) {
  limited = new Map(list.map((l) => [l.model, l]));
  if (!modelChosenHere) {
    let pick = rememberedModel();
    const at = limited.get(pick);
    if (at && at.other) pick = at.other;
    if (freeModel.value !== pick) {
      freeModel.value = pick;
      showSays();
    }
  }
  showLimitLine();
}

function showLimitLine() {
  const line = $('freeLimit');
  const now = limited.get(freeModel.value);
  const other = [...limited.values()].find((l) => l.other === freeModel.value);
  const until = (l) => (l.until_words ? ` until ${l.until_words}` : '');
  if (now) {
    const instead = now.other ? ` Choose ${now.other_name} under Options.` : '';
    line.textContent = `${now.name} is at its usage limit${until(now)}: a build with it would stop at once.${instead}`;
  } else if (other) {
    line.textContent = `${other.name} is at its usage limit${until(other)}; ${FREE_MODELS[freeModel.value]} is chosen.`;
  } else {
    line.textContent = '';
  }
  line.hidden = !line.textContent;
}

function addFiles(list) {
  freeProblem('');
  for (const file of list) {
    const suffix = suffixOf(file.name);
    if (PICTURE_TYPES.includes(file.type) || PICTURE_SUFFIXES.includes(suffix)) {
      if (chosen.pictures.length >= MAX_PICTURES) {
        freeProblem(`Add at most ${MAX_PICTURES} pictures.`);
        continue;
      }
      if (file.size > MAX_PICTURE_MB * 1024 * 1024) {
        freeProblem(`${file.name} is too large: BrickSnap takes pictures of up to ${MAX_PICTURE_MB} MB each.`);
        continue;
      }
      const total = chosen.pictures.reduce((sum, p) => sum + p.file.size, 0) + file.size;
      if (total > MAX_PICTURES_MB * 1024 * 1024) {
        freeProblem(`The pictures are too large together: at most ${MAX_PICTURES_MB} MB in all.`);
        continue;
      }
      chosen.pictures.push({ file, url: URL.createObjectURL(file) });
    } else if (SUFFIXES.includes(suffix)) {
      if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
        freeProblem(`${file.name} is too large: BrickSnap takes 3D model files of up to ${MAX_UPLOAD_MB} MB.`);
        continue;
      }
      if (chosen.model && chosen.model.file !== file) freeProblem('Only one 3D model can be added; the new one replaces the old one.');
      chosen.model = { file };
    } else {
      freeProblem(`BrickSnap cannot use ${file.name}. Add pictures (JPEG, PNG or WebP) or a 3D model (STL, OBJ, GLB, GLTF, 3MF or PLY).`);
    }
  }
  showThumbs();
}

function removeChosen(item) {
  if (item === chosen.model) chosen.model = null;
  else {
    chosen.pictures = chosen.pictures.filter((p) => p !== item);
    URL.revokeObjectURL(item.url);
  }
  showThumbs();
}

function showThumbs() {
  const items = [...chosen.pictures, ...(chosen.model ? [chosen.model] : [])];
  freeThumbs.hidden = items.length === 0;
  freeThumbs.replaceChildren(
    ...items.map((item) => {
      const isModel = item === chosen.model;
      const pic = el('span', { className: 'tpic' }, [
        isModel ? el('span', { className: 't3d', text: '⬢', 'aria-hidden': 'true' }) : el('img', { src: item.url, alt: `The picture ${item.file.name}` }),
      ]);
      const x = el('button', { type: 'button', className: 'quiet tx', text: '✕', 'aria-label': `Remove ${item.file.name}` });
      x.addEventListener('click', () => removeChosen(item));
      return el('li', { className: `thumb${isModel ? ' model3d' : ''}` }, [pic, el('span', { className: 'tname', text: item.file.name }), x]);
    }),
  );
  freeFiles.value = '';
  showSays();
}

freeFiles.addEventListener('change', () => addFiles(freeFiles.files || []));
for (const kind of ['dragenter', 'dragover']) {
  freeDrop.addEventListener(kind, (e) => {
    e.preventDefault();
    freeDrop.classList.add('dragging');
  });
}
for (const kind of ['dragleave', 'drop']) {
  freeDrop.addEventListener(kind, (e) => {
    e.preventDefault();
    freeDrop.classList.remove('dragging');
  });
}
freeDrop.addEventListener('drop', (e) => addFiles((e.dataTransfer && e.dataTransfer.files) || []));

freeParts.addEventListener('input', showParts);
freeWords.addEventListener('input', showSays);
freeModel.addEventListener('change', () => {
  modelChosenHere = true;
  try {
    window.localStorage.setItem(MODEL_KEY, freeModel.value);
  } catch {
    // remembered for this page only
  }
  showSays();
  showLimitLine();
});
freeGuide.addEventListener('change', showSays);
freePolish.addEventListener('change', showSays);
try {
  freeUnderstood.checked = window.localStorage.getItem(AGREED_KEY) === '1';
} catch {
  freeUnderstood.checked = false;
}
freeUnderstood.addEventListener('change', () => {
  try {
    if (freeUnderstood.checked) window.localStorage.setItem(AGREED_KEY, '1');
    else window.localStorage.removeItem(AGREED_KEY);
  } catch {
    // remembered for this page only
  }
});
freeModel.value = rememberedModel();
showParts();

function freeOpenButton(job) {
  const project = job.result && job.result.project ? job.result.project : job.project;
  if (!project || (job.state !== 'done' && !(job.result && job.result.project))) return null;
  const link = el('a', { className: 'button primary', href: `/p/${encodeURIComponent(project)}`, text: 'See what the AI built' });
  return el('div', { className: 'next' }, [link]);
}

function followFree(id, view = null) {
  followed.add(id);
  const v = view || new JobView(freeJobs, { nextStep: freeOpenButton, onDone: () => loadProjects() });
  v.follow(id);
}

/** Wait until the new model's page can be opened (its folder is made as the job starts). */
async function openWhenReady(project) {
  for (let k = 0; k < 50; k++) {
    const answer = await getJson('/api/projects');
    if (answer.status === 200 && answer.data && answer.data.projects.some((p) => p.project === project)) {
      window.location.href = `/p/${encodeURIComponent(project)}`;
      return true;
    }
    await sleep(200);
  }
  return false;
}

freeForm.addEventListener('submit', (e) => {
  e.preventDefault();
  if (freeSending) return;
  freeProblem('');
  const words = freeWords.value.trim();
  if (!words && !chosen.pictures.length && !chosen.model) {
    freeProblem('Say what to build first, for example “a small red fire truck”, or add a picture or a 3D model of it.');
    freeWords.focus();
    return;
  }
  if (!freeUnderstood.checked) {
    freeProblem('Tick “I understand…” under the bar first: Build starts a paid AI run with your Claude Code login.');
    freeUnderstood.focus();
    return;
  }
  const data = new FormData();
  data.append('words', words);
  data.append('parts', freeParts.value);
  data.append('model', freeModel.value);
  data.append('guide', freeGuide.checked ? 'true' : 'false');
  data.append('polish', freePolish.checked ? 'true' : 'false');
  const name = $('freeName').value.trim();
  if (name) data.append('name', name);
  data.append('understood', 'true');
  data.append('understood_runs', freePolish.checked ? '3' : '1');
  for (const p of chosen.pictures) data.append('picture', p.file, p.file.name);
  if (chosen.model) data.append('model_file', chosen.model.file, chosen.model.file.name);

  freeSending = true;
  freeGo.disabled = true;
  const view = new JobView(freeJobs);
  if (chosen.pictures.length || chosen.model) view.sending(0);
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/free');
  xhr.setRequestHeader('X-BrickSnap-Token', TOKEN);
  xhr.responseType = 'json';
  xhr.upload.onprogress = (ev) => {
    if (ev.lengthComputable && (chosen.pictures.length || chosen.model)) view.sending(ev.loaded / ev.total);
  };
  xhr.onload = async () => {
    freeSending = false;
    freeGo.disabled = false;
    const answer = { status: xhr.status, data: xhr.response };
    if (xhr.status === 202 && xhr.response && xhr.response.job) {
      followFree(xhr.response.job, view);
      view.box.scrollIntoView({ block: 'nearest' });
      if (!(await openWhenReady(xhr.response.project))) loadProjects();
    } else {
      view.remove();
      freeProblem(refusal(answer));
    }
  };
  xhr.onerror = () => {
    freeSending = false;
    freeGo.disabled = false;
    view.remove();
    freeProblem(NOT_ANSWERING);
  };
  xhr.send(data);
});

// ---- start ----

(async () => {
  await loadProjects();
  appState.ready = true;
  for (;;) {
    await sleep(anyActive ? 2000 : 10000);
    await loadProjects();
  }
})();
