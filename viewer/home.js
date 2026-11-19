// BrickSnap web app: the home page. The projects as cards, newest first, and the form that
// makes a new one from a model file. Text from the server goes in with textContent.

import { JobView, NOT_ANSWERING, TOKEN, appState, el, getJson, plural, refusal, sleep } from './app.js';

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
  const pic = el('div', { className: 'pic' });
  if (p.picture) {
    pic.append(el('img', { src: p.picture, alt: `Picture of ${p.name}: the model beside its bricks`, loading: 'lazy' }));
  } else {
    pic.append(el('span', { className: 'none', text: 'No picture yet' }));
  }
  const badges = el('div', { className: 'badges' });
  if (p.job) badges.append(el('span', { className: 'badge busy', text: 'Working on it…' }));
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
    $('cards').replaceChildren(...list.projects.map(card));
  }
  // A new model that is being made (started here or before this page was opened).
  for (const job of list.jobs) {
    if (job.kind === 'new' && !followed.has(job.id) && !uploading) followNew(job.id);
  }
  anyActive = list.jobs.length > 0;
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

function followNew(id, view = null) {
  followed.add(id);
  const v = view || new JobView(newJobs, { nextStep: openButton, onDone: () => loadProjects() });
  if (view) {
    view.nextStep = openButton;
    view.onDone = () => loadProjects();
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

// ---- start ----

(async () => {
  await loadProjects();
  appState.ready = true;
  for (;;) {
    await sleep(anyActive ? 2000 : 10000);
    await loadProjects();
  }
})();
