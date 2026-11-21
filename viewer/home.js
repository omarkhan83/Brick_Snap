// BrickSnap web app: the home page. The projects as cards, newest first, the form that
// makes a new one from a model file, and the experimental form that lets the AI build one
// from parts (a "free build"). Text from the server goes in with textContent.

import { JobView, NOT_ANSWERING, TOKEN, appState, el, freeTimeAndCost, getJson, plural, postJson, refusal, sleep } from './app.js';

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
    $('cards').replaceChildren(...list.projects.map(card));
  }
  // A new model that is being made (started here or before this page was opened).
  for (const job of list.jobs) {
    if (job.kind === 'new' && !followed.has(job.id) && !uploading) followNew(job.id);
    if (job.kind === 'free' && !followed.has(job.id) && !freeSending) followFree(job.id);
  }
  anyActive = list.jobs.length > 0;
  showReferences(list.projects);
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

// ---- letting the AI build one from parts (experimental) ----

const freeForm = $('freeForm');
const freeWords = $('freeWords');
const freeParts = $('freeParts');
const freeRef = $('freeRef');
const freeGuide = $('freeGuide');
const freeConfirm = $('freeConfirm');
const freeUnderstood = $('freeUnderstood');
const freeStart = $('freeStart');
const freeGo = $('freeGo');
const freeMsg = $('freeMsg');
const freeJobs = $('freeJobs');
let freeSending = false;

function showParts() {
  const n = Number(freeParts.value);
  $('freePartsOut').textContent = `${n} parts`;
  const size =
    n <= 60
      ? 'A small model.'
      : n <= 140
        ? 'A medium model, like a small set.'
        : 'A big model: big models take longer and use more of your subscription.';
  $('freePartsHint').textContent = `${size} ${freeTimeAndCost(n)}`;
}
freeParts.addEventListener('input', showParts);
showParts();

/** The chooser of ordinary models the AI may be shown, kept up to date with the list. */
let shownRefs = '';
function showReferences(projects) {
  const usable = projects.filter((p) => p.kind !== 'free' && !p.problem && typeof p.parts === 'number');
  const key = JSON.stringify(usable.map((p) => [p.project, p.name]));
  if (key === shownRefs) return;
  shownRefs = key;
  const chosen = freeRef.value;
  freeRef.replaceChildren(
    el('option', { value: '', text: 'No, just from my words' }),
    ...usable.map((p) => el('option', { value: p.project, text: p.name })),
  );
  freeRef.value = usable.some((p) => p.project === chosen) ? chosen : '';
}

function freeProblem(text) {
  freeMsg.textContent = text;
  appState.message = text;
}

function describeFree() {
  const words = freeWords.value.trim();
  $('freeWhat').replaceChildren(
    document.createTextNode('What the AI will build: '),
    el('span', { className: 'quote', id: 'freeQuote', text: `“${words}”` }),
    document.createTextNode(`, about ${freeParts.value} parts${freeGuide.checked ? ', designed first and built the way set designers do' : ''}.`),
  );
  $('freeTime').textContent = `It is one AI run. ${freeTimeAndCost(Number(freeParts.value))} You can leave this page while it works.`;
  const ref = freeRef.value ? freeRef.options[freeRef.selectedIndex].text : '';
  $('freeSends').textContent = ref
    ? `It sends the words you typed and pictures of “${ref}” from five sides to the AI provider, Anthropic, through Claude Code. Nothing else in BrickSnap sends anything off your computer.`
    : 'It sends the words you typed to the AI provider, Anthropic, through Claude Code. Nothing else in BrickSnap sends anything off your computer.';
}

function closeFree() {
  freeConfirm.hidden = true;
  freeUnderstood.checked = false;
  freeStart.disabled = true;
}

// Whatever changes what would be sent takes the agreement back.
for (const input of [freeWords, freeParts, freeRef, freeGuide]) {
  input.addEventListener('input', () => {
    if (!freeConfirm.hidden) {
      freeUnderstood.checked = false;
      freeStart.disabled = true;
      describeFree();
    }
  });
}

freeForm.addEventListener('submit', (e) => {
  e.preventDefault();
  freeProblem('');
  if (!freeWords.value.trim()) {
    freeProblem('Say what to build first, for example “a small red fire truck”.');
    freeWords.focus();
    return;
  }
  describeFree();
  freeUnderstood.checked = false;
  freeStart.disabled = true;
  freeConfirm.hidden = false;
  freeConfirm.scrollIntoView({ block: 'nearest' });
  freeUnderstood.focus();
});
freeUnderstood.addEventListener('change', () => {
  freeStart.disabled = !freeUnderstood.checked || freeSending;
});
$('freeCancel').addEventListener('click', () => {
  closeFree();
  freeGo.focus();
});
freeConfirm.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeFree();
    freeGo.focus();
  }
});

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

freeStart.addEventListener('click', async () => {
  if (!freeUnderstood.checked || freeSending) return;
  const body = {
    words: freeWords.value.trim(),
    parts: Number(freeParts.value),
    understood: true,
    understood_runs: 1,
  };
  const name = $('freeName').value.trim();
  if (name) body.name = name;
  if (freeRef.value) body.reference = freeRef.value;
  if (freeGuide.checked) body.guide = true;
  freeSending = true;
  freeStart.disabled = true;
  freeGo.disabled = true;
  const answer = await postJson('/api/free', body);
  freeSending = false;
  freeGo.disabled = false;
  if (answer.status === 202 && answer.data && answer.data.job) {
    closeFree();
    freeForm.reset();
    showParts();
    const view = new JobView(freeJobs, { nextStep: freeOpenButton, onDone: () => loadProjects() });
    followFree(answer.data.job, view);
    view.box.scrollIntoView({ block: 'nearest' });
    loadProjects();
  } else {
    freeStart.disabled = !freeUnderstood.checked;
    freeProblem(refusal(answer));
  }
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
