// BrickSnap web app (bricksnap/webapp.py): the action bar on the project page, and the
// pieces the home page (home.js) shares with it: talking to the server and showing a job.
//
// The server puts its token in <meta name="bricksnap-token">; every POST carries it in the
// X-BrickSnap-Token header. Text from files, from the person and from the AI goes into the
// page with textContent, never innerHTML.

export const TOKEN = document.querySelector('meta[name="bricksnap-token"]')?.content || '';
const POLL_JOB_MS = 1000;
const POLL_INFO_MS = 2000;

/** The state the tests read. */
export const appState = { ready: false, jobs: {}, info: null, message: '' };
window.__bricksnapApp = appState;

// ---- small helpers -------------------------------------------------------------------------

/** A new element; ``props`` are set as properties (text goes in with textContent). */
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === 'text') node.textContent = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('aria-') || key === 'role' || key === 'for') node.setAttribute(key, value);
    else node[key] = value;
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function plural(n, word) {
  return `${Number(n).toLocaleString('en')} ${n === 1 ? word : `${word}s`}`;
}

/** GET a JSON answer; returns {status, data}; status 0 when the server did not answer. */
export async function getJson(url) {
  try {
    const res = await fetch(url, { cache: 'no-store' });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return { status: res.status, data };
  } catch {
    return { status: 0, data: null };
  }
}

/** POST JSON with the token; returns {status, data}. */
export async function postJson(url, body = {}) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-BrickSnap-Token': TOKEN },
      body: JSON.stringify(body),
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return { status: res.status, data };
  } catch {
    return { status: 0, data: null };
  }
}

export const NOT_ANSWERING =
  'BrickSnap is not answering. Is its window still open? If you closed it, start it again with “uv run bricksnap serve”, then reload this page.';

/** The plain message of a refused request. */
export function refusal(answer) {
  if (answer.status === 0) return NOT_ANSWERING;
  return (answer.data && answer.data.error) || 'That did not work. Reload the page and try again.';
}

function ago(seconds) {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 60) return 'less than a minute ago';
  const m = Math.floor(s / 60);
  if (m < 60) return `${plural(m, 'minute')} ago`;
  return `${plural(Math.floor(m / 60), 'hour')} ago`;
}

// ---- a job and its progress ------------------------------------------------------------------

const WHAT_TO_DO = {
  new: 'Check that the file is a 3D model (STL, OBJ, GLB, GLTF, 3MF or PLY) that opens in your 3D program, then try again.',
  build: 'Try again. If it keeps failing, make the model again from its file on the home page.',
  design:
    'Your model is safe: whatever the designer finished is kept. You can try again. If Claude Code is not signed in on this computer, open Claude Code once, sign in, and then try again.',
  export: 'Build the bricks again, then try once more.',
  instructions:
    'Instructions can only be made for bricks that hold together. Ask the AI designer to fix the model, or build it again, then try once more.',
  restore: 'Your model was left as it was. Reload the page and try again.',
};

const DONE_TITLE = {
  new: 'Your model is ready',
  build: 'The bricks are rebuilt',
  design: 'The AI designer has finished',
  export: 'The parts list and LDraw file are ready',
  instructions: 'The building instructions are ready',
  restore: 'The earlier version is back',
};

/** One job's box: what is happening, newest progress first, and what to do if it failed. */
export class JobView {
  constructor(parent, { onDone = null, nextStep = null } = {}) {
    this.box = el('div', { className: 'job', role: 'status', 'aria-live': 'polite' });
    this.onDone = onDone;
    this.nextStep = nextStep; // (job) => element shown under a finished job, or null
    this.last = '';
    parent.prepend(this.box);
  }

  remove() {
    this.box.remove();
  }

  /** While the browser is still sending the file. */
  sending(fraction) {
    const pct = Math.round(fraction * 100);
    this.box.className = 'job';
    this.box.replaceChildren(
      el('h3', {}, [el('span', { className: 'spinner', 'aria-hidden': 'true' }), el('span', { text: 'Sending the file to BrickSnap' })]),
      el('p', { className: 'leave', text: `${pct}% sent. Please keep this page open until the file has been sent.` }),
    );
  }

  problem(message, kind) {
    this.show({ state: 'failed', kind, error: message, progress: [] });
  }

  async follow(id) {
    appState.jobs[id] = 'waiting';
    let misses = 0;
    for (;;) {
      const answer = await getJson(`/api/jobs/${encodeURIComponent(id)}`);
      if (answer.status === 200 && answer.data) {
        misses = 0;
        const job = answer.data;
        this.show(job);
        appState.jobs[id] = job.state;
        if (job.state === 'done' || job.state === 'failed') {
          if (this.onDone) this.onDone(job);
          return job;
        }
      } else if (answer.status === 404) {
        const job = {
          state: 'failed',
          kind: '',
          error: 'BrickSnap no longer knows this job: it was probably restarted. Whatever the job had finished is kept in the project.',
          progress: [],
        };
        this.show(job);
        appState.jobs[id] = 'failed';
        if (this.onDone) this.onDone(job);
        return job;
      } else {
        misses += 1;
        if (misses >= 3) this.show({ state: 'failed', kind: '', error: NOT_ANSWERING, progress: [] });
      }
      await sleep(misses ? 3000 : POLL_JOB_MS);
    }
  }

  show(job) {
    const key = JSON.stringify(job);
    if (key === this.last) return;
    this.last = key;
    const running = job.state === 'waiting' || job.state === 'running';
    this.box.className = `job ${running ? '' : job.state}`.trim();
    this.box.dataset.state = job.state;
    const parts = [];
    if (running) {
      const what = job.what ? job.what[0].toUpperCase() + job.what.slice(1) : 'Working';
      parts.push(el('h3', {}, [el('span', { className: 'spinner', 'aria-hidden': 'true' }), el('span', { text: `Working: ${what}` })]));
      if (job.started) parts.push(el('p', { className: 'when', text: `Started ${ago(job.started)}.` }));
      parts.push(
        el('p', {
          className: 'leave',
          text: 'It is safe to leave this page: the work carries on in the BrickSnap window, and you can come back to see how it went.',
        }),
      );
    } else if (job.state === 'done') {
      parts.push(el('h3', { text: DONE_TITLE[job.kind] || 'Finished' }));
    } else {
      parts.push(el('h3', { text: 'That did not work' }));
      parts.push(el('p', { className: 'error', text: job.error || 'It stopped without saying why.' }));
      const todo = WHAT_TO_DO[job.kind];
      if (todo) parts.push(el('p', { className: 'todo', text: `What to do: ${todo}` }));
    }
    const lines = Array.isArray(job.progress) ? job.progress.slice().reverse() : [];
    if (lines.length) {
      parts.push(el('ul', { className: 'progress', 'aria-label': 'Progress, newest first' }, lines.map((t) => el('li', { text: String(t) }))));
    }
    if (!running && this.nextStep) {
      const next = this.nextStep(job);
      if (next) parts.push(next);
    }
    this.box.replaceChildren(...parts);
  }
}

// ---- the project page's action bar -----------------------------------------------------------

const DOWNLOADS = {
  'build.ldr': ['The brick model', 'opens in BrickLink Studio, LeoCAD or LDView'],
  'parts.csv': ['The parts list', 'opens in Excel, LibreOffice or any spreadsheet program'],
  'wanted_list.xml': [
    'The BrickLink wanted list',
    'to buy the parts: on bricklink.com choose Wanted, then Upload, and paste in what this file holds',
  ],
  'instructions.pdf': ['Building instructions', 'to print, or to read on a screen'],
  'instructions.html': ['Building instructions as a web page', 'the same booklet, to open in your browser'],
  'renders/compare.png': ['A picture', 'your model beside the bricks'],
};

const MINUTES_PER_RUN = [3, 6];

function initActions(project) {
  const main = document.querySelector('main');
  const base = `/p/${encodeURIComponent(project)}`;
  const api = `/api/p/${encodeURIComponent(project)}`;
  let info = null;
  let following = null; // the id of the job being shown

  // ---- the parts of the bar ----
  const message = el('p', { id: 'actMsg', className: 'actmsg', role: 'alert' });
  const nextStep = el('div', { id: 'nextStep', className: 'next-step' });
  const jobArea = el('div', { id: 'appJob' });

  const buildBtn = el('button', { type: 'button', className: 'quiet', id: 'actBuild', text: 'Build the bricks again' });
  const exportBtn = el('button', { type: 'button', className: 'quiet', id: 'actExport', text: 'Make the parts list and LDraw file' });
  const instrBtn = el('button', { type: 'button', className: 'quiet', id: 'actInstructions', text: 'Make building instructions' });
  const deleteBtn = el('button', { type: 'button', className: 'danger', id: 'actDelete', text: 'Move to the bin' });
  const downloads = el('div', { className: 'downloads', id: 'downloads' });
  const versionsBox = el('div', { className: 'versions', id: 'versions', hidden: true });

  // the AI confirmation step
  const confirmBox = el('div', { id: 'aiConfirm', className: 'confirm', hidden: true, role: 'dialog', 'aria-labelledby': 'aiConfirmTitle' });
  const bestOf = el('select', { id: 'bestOf' }, [1, 2, 3, 4, 5].map((n) =>
    el('option', { value: String(n), text: n === 1 ? '1 design (quickest)' : `${n} designs, then a judge picks the best` }),
  ));
  const understood = el('input', { type: 'checkbox', id: 'aiUnderstood' });
  const startBtn = el('button', { type: 'button', className: 'primary', id: 'aiStart', text: 'Start the AI designer', disabled: true });
  const cancelBtn = el('button', { type: 'button', className: 'quiet', id: 'aiCancel', text: 'Cancel' });
  const confirmWhat = el('li', { id: 'aiWhat' });
  const confirmRuns = el('li', { id: 'aiRuns' });
  const confirmTime = el('li', { id: 'aiTime' });
  let pendingRequest = null;

  confirmBox.append(
    el('h3', { id: 'aiConfirmTitle', text: 'Before the AI designer starts' }),
    el('ul', {}, [
      confirmWhat,
      el('li', {
        text: 'It sends pictures of your model and a description of it (its size, colours and parts) to the AI provider, Anthropic, through Claude Code. Nothing else in BrickSnap sends anything off your computer.',
      }),
      el('li', { text: 'It uses your own Claude Code login, so it counts towards your Claude subscription.' }),
      confirmRuns,
      confirmTime,
    ]),
    el('div', { className: 'field' }, [el('label', { for: 'bestOf', text: 'How many designs to try' }), bestOf]),
    el('label', { className: 'check' }, [understood, el('span', { text: 'I have read this and want to start the AI designer.' })]),
    el('div', { className: 'row' }, [startBtn, cancelBtn]),
  );

  const bar = el('section', { id: 'actions', className: 'card actions', 'aria-label': 'What you can do with this model' }, [
    el('div', { className: 'topline' }, [
      el('a', { href: '/', id: 'backHome', text: '← All your models' }),
    ]),
    el('h2', { text: 'What next?' }),
    nextStep,
    confirmBox,
    message,
    jobArea,
    versionsBox,
    downloads,
    el('div', { className: 'more-actions' }, [
      el('h3', { text: 'More' }),
      el('div', { className: 'row' }, [buildBtn, exportBtn, instrBtn, deleteBtn]),
    ]),
  ]);
  main.prepend(bar);

  // ---- showing the state ----
  function say(text, bad = true) {
    message.textContent = text;
    message.classList.toggle('bad', bad);
    appState.message = text;
  }

  function busy() {
    return Boolean(info && info.job && (info.job.state === 'running' || info.job.state === 'waiting'));
  }

  function updateButtons() {
    const off = busy() || !info;
    for (const b of [buildBtn, exportBtn, instrBtn, deleteBtn]) b.disabled = off;
    const built = Boolean(info && info.parts !== null && info.parts !== undefined);
    exportBtn.disabled = off || !built;
    instrBtn.disabled = off || !built || info.valid !== true;
    for (const b of nextStep.querySelectorAll('button')) b.disabled = off;
    for (const b of versionsBox.querySelectorAll('#useVersion')) b.disabled = off;
    startBtn.disabled = off || !understood.checked;
    cancelBtn.disabled = false; // closing the confirmation is always possible
  }

  let shownFiles = null;
  function showDownloads() {
    const files = ((info && info.files) || []).filter((f) => DOWNLOADS[f]);
    const key = files.join('|');
    if (key === shownFiles) return; // unchanged: leave the list (and an opened explanation) alone
    shownFiles = key;
    const short = (f) => f.split('/').pop();
    const links = files.map((f) => {
      const [label, what] = DOWNLOADS[f];
      const link = el('a', { href: `${base}/files/${f}`, text: label, className: 'file', title: `${short(f)}: ${what}` });
      link.setAttribute('download', short(f));
      return link;
    });
    const body = links.length
      ? [
          el('div', { className: 'files' }, links),
          el('details', { className: 'about-files' }, [
            el('summary', { text: 'What are these files?' }),
            el('ul', {}, files.map((f) => el('li', { text: `${DOWNLOADS[f][0]} (${short(f)}): ${DOWNLOADS[f][1]}` }))),
          ]),
        ]
      : [el('p', { className: 'muted small', text: 'Nothing to download yet. “Build the bricks again” below makes the files.' })];
    downloads.replaceChildren(el('h3', { text: 'Download' }), ...body);
  }

  function showNextStep() {
    const parts = [];
    const brief = info && info.brief;
    if (!info) {
      parts.push(el('p', { text: 'Loading…' }));
    } else if (busy()) {
      parts.push(el('p', { text: 'BrickSnap is working on this model. The progress is below, and the 3D view updates by itself when it is done.' }));
    } else if (info.problem) {
      parts.push(el('p', { text: info.problem }));
      parts.push(el('button', { type: 'button', className: 'primary', text: 'Build the bricks again', onclick: () => run('build') }));
    } else if (info.parts === null || info.parts === undefined) {
      parts.push(el('p', { text: 'This model has not been built into bricks yet.' }));
      parts.push(el('button', { type: 'button', className: 'primary', text: 'Build the bricks', onclick: () => run('build') }));
    } else if (!info.current) {
      parts.push(el('p', { text: 'The design was changed after these bricks were built, so they are out of date.' }));
      parts.push(el('button', { type: 'button', className: 'primary', text: 'Build the bricks again', onclick: () => run('build') }));
    } else if (!brief) {
      parts.push(
        el('p', {
          text: info.valid
            ? 'Next: let the AI designer make it look designed rather than merely converted. Compare the two views below when it is done.'
            : 'The bricks do not hold together yet. Next: let the AI designer fix and improve the model.',
        }),
      );
      parts.push(el('button', { type: 'button', className: 'primary', id: 'aiOpen', text: 'Start the AI designer…', onclick: () => openConfirm(null) }));
    } else {
      const input = el('input', { type: 'text', id: 'askText', maxLength: 2000, placeholder: 'For example: add a red collar', autocomplete: 'off' });
      input.setAttribute('aria-label', 'The change you want, in your own words');
      const ask = el('button', { type: 'button', className: 'primary', id: 'askBtn', text: 'Ask the designer…' });
      const go = () => {
        const text = input.value.trim();
        if (!text) {
          say('Type the change you want first, for example “add a red collar”.');
          input.focus();
          return;
        }
        openConfirm(text);
      };
      ask.onclick = go;
      input.onkeydown = (e) => {
        if (e.key === 'Enter') go();
      };
      parts.push(el('p', { text: 'Want something changed? Ask the AI designer for it in your own words.' }));
      parts.push(el('div', { className: 'ask' }, [input, ask]));
    }
    // keep a typed request across refreshes
    const old = nextStep.querySelector('#askText');
    const keep = old ? old.value : null;
    const hadFocus = old && document.activeElement === old;
    nextStep.replaceChildren(...parts);
    const fresh = nextStep.querySelector('#askText');
    if (fresh && keep !== null) {
      fresh.value = keep;
      if (hadFocus) fresh.focus();
    }
  }

  // ---- the versions: a strip, newest first; a click shows one in the right-hand view ----
  const KIND_WORDS = { converted: 'Conversion', designed: 'AI design', edit: 'Your change', pass: 'AI design pass', manual: 'By hand' };
  let pending = null; // the version just clicked, until the viewer has drawn it
  const viewer = () => window.__bricksnap || null;

  function showVersions() {
    const list = (info && Array.isArray(info.versions) ? info.versions : []).slice().reverse();
    const now = info ? info.current_version : null;
    versionsBox.hidden = list.length === 0;
    if (!list.length) {
      versionsBox.replaceChildren();
      return;
    }
    const v = viewer();
    const right = v && v.choice ? v.choice.right : now;
    const shownN = pending ?? right ?? now;
    const cards = list.map((x) => {
      const pic = x.picture
        ? el('img', { src: x.picture, alt: '', loading: 'lazy', width: 64, height: 48 })
        : el('span', { className: 'vnopic', 'aria-hidden': 'true' });
      const facts = `${KIND_WORDS[x.kind] || x.kind} · ${plural(x.parts, 'part')}${x.valid ? '' : ' · does not hold'}`;
      const button = el('button', { type: 'button', className: 'vcard', title: x.note ? `${x.label}: ${x.note}` : x.label, dataset: { n: String(x.n) }, 'aria-pressed': String(x.n === shownN) }, [
        pic,
        el('span', { className: 'vtext' }, [
          el('span', { className: 'vname' }, [el('span', { className: 'vn', text: String(x.n) }), el('span', { className: 'vlabel', text: x.label })]),
          el('span', { className: 'vfacts' }, [x.n === now ? el('span', { className: 'badge ok vnow', text: 'In use' }) : null, document.createTextNode(facts)]),
        ]),
      ]);
      button.onclick = async () => {
        pending = x.n;
        render(true);
        const viewerState = viewer();
        if (viewerState && typeof viewerState.choose === 'function') await viewerState.choose('right', x.n);
        pending = null;
        render(true);
      };
      return el('li', {}, [button]);
    });
    const parts = [
      el('h3', { id: 'versionsTitle', text: 'Versions', title: 'Click one to see it in the right-hand 3D view' }),
      el('ol', { className: 'vlist', 'aria-labelledby': 'versionsTitle' }, cards),
    ];
    const picked = list.find((x) => x.n === shownN);
    if (picked && picked.n !== now) {
      const use = el('button', { type: 'button', className: 'primary', id: 'useVersion', text: 'Use this version' });
      use.disabled = busy();
      use.onclick = () => {
        if (!window.confirm(`Go back to version ${picked.n}, “${picked.label}”? The model as it is now stays in the list, so you can come back to it.`)) return;
        start('restore', { version: picked.n });
      };
      parts.push(el('div', { className: 'vuse' }, [el('span', { text: `Version ${picked.n} is in the right-hand view.` }), use]));
    }
    const strip = versionsBox.querySelector('.vlist');
    const scroll = strip ? strip.scrollLeft : 0;
    versionsBox.replaceChildren(...parts);
    versionsBox.querySelector('.vlist').scrollLeft = scroll;
  }

  let shown = '';
  function render(force = false) {
    const v = viewer();
    const key = JSON.stringify([info, pending, v && v.choice ? v.choice.right : null]);
    if (key === shown && !force) return;
    shown = key;
    showNextStep();
    showVersions();
    showDownloads();
    updateButtons();
  }

  // ---- the AI confirmation ----
  function describeRuns() {
    const n = Number(bestOf.value);
    confirmRuns.textContent =
      n === 1
        ? 'It starts 1 AI run.'
        : `It starts ${n + 1} AI runs, one after another: ${n} designs of the model, each on its own copy, and then one judging run that compares them without knowing which is which and picks the best.`;
    confirmTime.textContent =
      n === 1
        ? 'It usually takes several minutes. You can leave this page while it works.'
        : `Each run takes a few minutes, so expect about ${MINUTES_PER_RUN[0] * (n + 1)} to ${MINUTES_PER_RUN[1] * (n + 1)} minutes in all. Your project is only changed at the very end. You can leave this page while it works.`;
  }

  function openConfirm(request) {
    if (busy()) return;
    pendingRequest = request;
    say('');
    understood.checked = false;
    if (request) {
      confirmWhat.replaceChildren(
        document.createTextNode('Your request, as the designer will get it: '),
        el('span', { className: 'quote', id: 'aiQuote', text: `“${request}”` }),
        document.createTextNode('. The designer makes that change and leaves the rest of the model as it is.'),
      );
    } else if (info && info.brief) {
      confirmWhat.textContent = 'This is another full design pass: the designer may change any part of the model.';
    } else {
      confirmWhat.textContent = 'This is a first design of the model: the designer looks at it, writes a plan and improves how it looks.';
    }
    describeRuns();
    confirmBox.hidden = false;
    updateButtons();
    confirmBox.scrollIntoView({ block: 'nearest' });
    understood.focus();
  }

  bestOf.onchange = () => {
    // the number of AI runs is part of what the person agreed to: ask again
    understood.checked = false;
    describeRuns();
    updateButtons();
  };
  understood.onchange = updateButtons;
  function closeConfirm() {
    confirmBox.hidden = true;
    const opener = nextStep.querySelector('#aiOpen, #askBtn');
    if (opener) opener.focus();
  }
  cancelBtn.onclick = closeConfirm;
  confirmBox.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeConfirm();
  });
  startBtn.onclick = async () => {
    if (!understood.checked) return;
    const n = Number(bestOf.value);
    const body = { understood: true, understood_runs: n === 1 ? 1 : n + 1 };
    if (pendingRequest) body.request = pendingRequest;
    if (n > 1) body.best_of = n;
    confirmBox.hidden = true;
    await start('design', body);
  };

  // ---- actions ----
  async function start(action, body = {}) {
    say('');
    for (const b of bar.querySelectorAll('button')) b.disabled = true;
    const answer = await postJson(`${api}/${action}`, body);
    shown = ''; // draw the bar again whatever the answer
    if (answer.status === 202 && answer.data && answer.data.job) {
      await refresh();
      followJob(answer.data.job);
    } else {
      say(refusal(answer));
      await refresh();
    }
  }

  function run(action) {
    return start(action);
  }

  buildBtn.onclick = () => run('build');
  exportBtn.onclick = () => run('export');
  instrBtn.onclick = () => run('instructions');
  deleteBtn.onclick = async () => {
    const name = (info && info.name) || project;
    if (!window.confirm(`Move “${name}” to the bin? Its folder goes into ${(info && info.bin) || 'the .trash folder of your projects folder'}, so nothing is deleted and you can move it back.`)) return;
    const answer = await postJson(`${api}/delete`, {});
    if (answer.status === 200) {
      say(`Moved to the bin: ${answer.data.folder || answer.data.moved_to}. Going back to your models…`, false);
      setTimeout(() => {
        window.location.href = '/';
      }, 1200);
    } else {
      say(refusal(answer));
    }
  };

  function followJob(id) {
    if (following === id) return;
    following = id;
    jobArea.replaceChildren();
    const view = new JobView(jobArea, {
      onDone: () => {
        refresh();
        if (window.__bricksnap && typeof window.__bricksnap.pollNow === 'function') window.__bricksnap.pollNow();
      },
    });
    view.follow(id);
  }

  async function refresh() {
    const answer = await getJson(api);
    if (answer.status === 200 && answer.data) {
      info = answer.data;
      appState.info = info;
      if (appState.message === NOT_ANSWERING) say('');
      if (info.job && (info.job.state === 'running' || info.job.state === 'waiting')) followJob(info.job.id);
    } else if (answer.status === 404) {
      info = null;
      say('This project is no longer here: it may have been moved to the bin. Go back to your models.');
    } else {
      say(NOT_ANSWERING);
    }
    render();
  }

  (async () => {
    await refresh();
    appState.ready = true;
    for (;;) {
      await sleep(POLL_INFO_MS);
      await refresh();
    }
  })();
}

const PROJECT = document.body.dataset.project;
if (PROJECT) initActions(PROJECT);
