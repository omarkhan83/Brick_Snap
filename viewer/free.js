// BrickSnap web app: the page of a model the AI built from parts (a "free build";
// bricksnap/lab/freebuild.py, bricksnap/webapp.py). EXPERIMENTAL.
//
// The model turning under a slider (twelve pictures round it), what the checker says, the
// AI's own notes, "Ask for a change" with the same kind of agreement as the AI designer's,
// the downloads, the earlier runs, and the bin. Text from the server, the person and the AI
// goes in with textContent, never innerHTML.

import { JobView, NOT_ANSWERING, appState, el, getJson, plural, postJson, refusal, sleep } from './app.js';

const $ = (id) => document.getElementById(id);
const project = document.body.dataset.project;
const api = `/api/p/${encodeURIComponent(project)}`;
const POLL_BUSY_MS = 2000;
const POLL_IDLE_MS = 8000;
const VIEW_WORDS = [
  'from the front-left',
  'from the front, a little to the left',
  'from the front, a little to the right',
  'from the front-right',
  'from the right, a little to the front',
  'from the right, a little to the back',
  'from the back-right',
  'from the back, a little to the right',
  'from the back, a little to the left',
  'from the back-left',
  'from the left, a little to the back',
  'from the left, a little to the front',
];
const DOWNLOADS = {
  'model.ldr': ['The model', 'model.ldr', 'opens in BrickLink Studio, LeoCAD or LDView'],
  'parts.csv': ['The parts list', 'parts.csv', 'opens in Excel, LibreOffice or any spreadsheet program'],
  'report.txt': ["The checker's report", 'report.txt', 'what the checker found, part by part'],
};
const RUN_WORDS = { first: 'First build', change: 'Your change', imported: 'Brought in' };

let info = null;
let following = null;
let frames = [];
let frame = 0;

const img = $('turn');
const slider = $('turnSlider');
const message = $('actMsg');

function say(text, bad = true) {
  message.textContent = text;
  message.classList.toggle('bad', bad);
  appState.message = text;
}

function busy() {
  return Boolean(info && info.job && (info.job.state === 'running' || info.job.state === 'waiting'));
}

// ---- the turning model ----

function showFrame(k) {
  if (!frames.length) return;
  frame = ((k % frames.length) + frames.length) % frames.length;
  img.src = frames[frame];
  slider.value = String(frame);
  const words = frames.length === 12 ? VIEW_WORDS[frame] : '';
  $('turnSays').textContent = `View ${frame + 1} of ${frames.length}${words ? `, ${words}` : ''}. Drag the slider, or use the arrow keys.`;
  img.alt = `${(info && info.name) || 'The model'}, ${words || `view ${frame + 1}`}`;
}

// The first picture, put on the page by the server, shows before anything else has loaded.
const first = document.body.dataset.first;
if (first) {
  frames = [first];
  img.hidden = false;
  img.src = first;
}

function showTurntable() {
  const list = (info && Array.isArray(info.turntable) ? info.turntable : []).map(String);
  const none = $('noPicture');
  if (list.join('|') !== frames.join('|')) {
    frames = list;
    for (const url of frames) new Image().src = url; // fetch them all now, so turning is smooth
    if (frames.length) showFrame(Math.min(frame, frames.length - 1));
  }
  slider.max = String(Math.max(frames.length - 1, 0));
  img.hidden = frames.length === 0;
  $('turnControls').hidden = frames.length < 2;
  $('turnSays').hidden = frames.length < 2;
  if (!frames.length) {
    none.hidden = false;
    none.textContent = busy()
      ? 'The AI is building the model. Its pictures appear here when it is done.'
      : (info && info.picture_problem) || 'There are no pictures of this model yet.';
  } else {
    none.hidden = true;
  }
}

slider.addEventListener('input', () => showFrame(Number(slider.value)));
$('turnLeft').addEventListener('click', () => showFrame(frame - 1));
$('turnRight').addEventListener('click', () => showFrame(frame + 1));
$('turnBox').addEventListener('keydown', (e) => {
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    e.preventDefault();
    showFrame(frame + (e.key === 'ArrowRight' ? 1 : -1));
  }
});

// ---- what the checker says ----

function showChecker() {
  const chips = [];
  if (typeof info.parts === 'number') chips.push(el('span', { className: 'badge', text: plural(info.parts, 'part') }));
  if (typeof info.kinds === 'number') chips.push(el('span', { className: 'badge', text: `${plural(info.kinds, 'kind')} of part` }));
  if (info.valid === true) chips.push(el('span', { className: 'badge ok', id: 'verdict', text: 'Checked: no problems' }));
  else if (typeof info.problems === 'number' && info.problems > 0) chips.push(el('span', { className: 'badge bad', id: 'verdict', text: plural(info.problems, 'problem') }));
  if (typeof info.unchecked === 'number' && info.unchecked > 0) {
    chips.push(el('span', { className: 'badge exp', text: `${plural(info.unchecked, 'joint')} not checked` }));
  }
  $('chips').replaceChildren(...chips);
  $('checkSummary').textContent = info.summary
    ? `${info.summary[0].toUpperCase()}${info.summary.slice(1)}`
    : busy()
      ? 'The checker looks at the model when the AI has built it.'
      : 'There is no model to check yet.';
  $('report').textContent = info.report || '';
  $('reportBox').hidden = !info.report;
}

// ---- the AI's notes: paragraphs, "- " lists and **bold**, all as text ----

function inline(text) {
  const parts = String(text).split('**');
  return parts.map((t, i) => (i % 2 ? el('strong', { text: t }) : document.createTextNode(t)));
}

function showNotes() {
  const text = (info && info.notes) || '';
  $('notesCard').hidden = !text;
  const blocks = [];
  for (const para of text.split(/\n\s*\n/)) {
    const lines = para.split('\n').map((l) => l.trim()).filter(Boolean);
    let list = null;
    for (const line of lines) {
      if (/^[-*] /.test(line)) {
        if (!list) {
          list = el('ul');
          blocks.push(list);
        }
        list.append(el('li', {}, inline(line.slice(2))));
      } else {
        list = null;
        blocks.push(el('p', {}, inline(line.replace(/^#+\s*/, ''))));
      }
    }
  }
  $('aiNotes').replaceChildren(...blocks);
}

// ---- downloads ----

let shownFiles = '';
function showDownloads() {
  const files = info && info.files ? info.files : {};
  const names = Object.keys(DOWNLOADS).filter((f) => files[f]);
  const key = JSON.stringify(names.map((f) => files[f]));
  if (key === shownFiles) return;
  shownFiles = key;
  const box = $('downloads');
  if (!names.length) {
    box.replaceChildren(el('p', { className: 'muted small', text: 'Nothing to download yet.' }));
    return;
  }
  const links = names.map((f) => {
    const [label, file, what] = DOWNLOADS[f];
    const a = el('a', { href: files[f], className: 'file', text: `${label} (${file})`, title: what });
    a.setAttribute('download', `${project}-${file}`);
    return a;
  });
  box.replaceChildren(
    el('div', { className: 'files' }, links),
    el('details', { className: 'about-files' }, [
      el('summary', { text: 'What are these files?' }),
      el('ul', {}, names.map((f) => el('li', { text: `${DOWNLOADS[f][0]} (${DOWNLOADS[f][1]}): ${DOWNLOADS[f][2]}` }))),
    ]),
  );
}

// ---- runs ----

function minutes(seconds) {
  if (typeof seconds !== 'number') return '';
  const m = Math.max(1, Math.round(seconds / 60));
  return plural(m, 'minute');
}

let shownRuns = '';
function showRuns() {
  const runs = (info && Array.isArray(info.runs) ? info.runs : []).slice().reverse();
  const key = JSON.stringify([runs, info && info.current_run, busy()]);
  if (key === shownRuns) return;
  shownRuns = key;
  $('runsCard').hidden = runs.length === 0;
  const items = runs.map((r) => {
    const pic = r.picture
      ? el('img', { src: r.picture, alt: '', loading: 'lazy', width: 96, height: 72 })
      : el('span', { className: 'vnopic', 'aria-hidden': 'true' });
    const now = r.n === info.current_run;
    const facts = [];
    if (r.has_model) facts.push(plural(r.parts, 'part'));
    if (r.clean === true) facts.push('no problems');
    else if (typeof r.problems === 'number' && r.problems > 0) facts.push(plural(r.problems, 'problem'));
    if (!r.has_model) facts.push('made no model');
    else if (r.ok === false) facts.push('stopped before it finished');
    const time = minutes(r.seconds);
    if (time) facts.push(time);
    const head = el('span', { className: 'vname' }, [
      el('span', { className: 'vn', text: String(r.n) }),
      el('span', { className: 'vlabel', text: RUN_WORDS[r.kind] || r.kind }),
    ]);
    const parts = [
      pic,
      el('span', { className: 'vtext' }, [
        head,
        r.words ? el('span', { className: 'rwords', text: `“${r.words}”` }) : null,
        el('span', { className: 'vfacts' }, [now ? el('span', { className: 'badge ok vnow', text: 'In use' }) : null, document.createTextNode(facts.join(' · '))]),
      ]),
    ];
    if (!now && r.has_model) {
      const use = el('button', { type: 'button', className: 'quiet usebtn', text: 'Use this one', dataset: { n: String(r.n) } });
      use.disabled = busy();
      use.onclick = () => {
        if (!window.confirm(`Bring back run ${r.n}? The model as it is now stays in the list, so you can come back to it.`)) return;
        start('use', { run: r.n });
      };
      parts.push(use);
    }
    return el('li', { className: `run${now ? ' now' : ''}`, dataset: { n: String(r.n) } }, parts);
  });
  $('runs').replaceChildren(...items);
}

// ---- what next, and asking for a change ----

let pendingWords = null;
const confirmBox = $('changeConfirm');
const understood = $('changeUnderstood');
const startBtn = $('changeStart');

function showNextStep() {
  const box = $('nextStep');
  const old = box.querySelector('#askText');
  const kept = old ? old.value : null;
  const hadFocus = old && document.activeElement === old;
  const parts = [];
  if (!info) {
    parts.push(el('p', { text: 'Loading…' }));
  } else if (busy()) {
    parts.push(el('p', { text: 'The AI is working on this model. Its progress is below; the pictures change by themselves when it is done.' }));
  } else if (info.problem) {
    parts.push(el('p', { text: info.problem }));
  } else {
    const built = typeof info.parts === 'number' && info.parts > 0;
    let lead;
    if (!built) lead = 'The AI did not finish a model here. Say again what to build, and it tries once more.';
    else if (info.valid) lead = 'The checker found no problems. Download the model for BrickLink Studio below, or ask the AI for a change in your own words.';
    else lead = 'The checker found problems (see its report). Ask the AI to fix them, or for any other change, in your own words.';
    parts.push(el('p', { text: lead }));
    const input = el('input', {
      type: 'text',
      id: 'askText',
      maxLength: 2000,
      autocomplete: 'off',
      placeholder: built ? (info.valid ? 'For example: make the roof blue' : 'For example: fix the problems the checker found') : (info.words || 'What should it build?'),
    });
    input.setAttribute('aria-label', 'The change you want, in your own words');
    const ask = el('button', { type: 'button', className: 'primary', id: 'askBtn', text: 'Ask for a change…' });
    const go = () => {
      const text = input.value.trim();
      if (!text) {
        say('Type the change you want first, for example “make the roof blue”.');
        input.focus();
        return;
      }
      openConfirm(text);
    };
    ask.onclick = go;
    input.onkeydown = (e) => {
      if (e.key === 'Enter') go();
    };
    parts.push(el('div', { className: 'ask' }, [input, ask]));
  }
  box.replaceChildren(...parts);
  const fresh = box.querySelector('#askText');
  if (fresh && kept !== null) {
    fresh.value = kept;
    if (hadFocus) fresh.focus();
  }
}

function openConfirm(words) {
  if (busy()) return;
  pendingWords = words;
  say('');
  understood.checked = false;
  startBtn.disabled = true;
  $('changeWhat').replaceChildren(
    document.createTextNode('Your change, as the AI will get it: '),
    el('span', { className: 'quote', id: 'changeQuote', text: `“${words}”` }),
    document.createTextNode('. The AI makes that change and keeps the rest of the model as it is.'),
  );
  confirmBox.hidden = false;
  confirmBox.scrollIntoView({ block: 'nearest' });
  understood.focus();
}

function closeConfirm() {
  confirmBox.hidden = true;
  const opener = $('askBtn');
  if (opener) opener.focus();
}

understood.addEventListener('change', () => {
  startBtn.disabled = !understood.checked || busy();
});
$('changeCancel').addEventListener('click', closeConfirm);
confirmBox.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeConfirm();
});
startBtn.addEventListener('click', async () => {
  if (!understood.checked || !pendingWords) return;
  confirmBox.hidden = true;
  await start('change', { words: pendingWords, understood: true, understood_runs: 1 });
  const input = $('askText');
  if (input && following) input.value = '';
});

// ---- actions ----

async function start(action, body) {
  say('');
  for (const b of document.querySelectorAll('main button')) b.disabled = true;
  const answer = await postJson(`${api}/${action}`, body);
  if (answer.status === 202 && answer.data && answer.data.job) {
    await refresh();
    followJob(answer.data.job);
  } else {
    say(refusal(answer));
    await refresh(true);
  }
}

$('actDelete').addEventListener('click', async () => {
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
});

function followJob(id) {
  if (following === id) return;
  following = id;
  $('appJob').replaceChildren();
  const view = new JobView($('appJob'), { onDone: () => refresh(true) });
  view.follow(id);
}

// ---- keeping the page up to date ----

let shownInfo = '';
function render(force = false) {
  const key = JSON.stringify(info);
  if (key === shownInfo && !force) return;
  shownInfo = key;
  if (info) {
    $('freeName').textContent = info.name;
    $('asked').hidden = !info.words;
    $('asked').textContent = info.words ? `Asked for: “${info.words}”` : '';
    document.title = `${info.name} - BrickSnap`;
    showChecker();
  }
  showTurntable();
  showNotes();
  showDownloads();
  showRuns();
  showNextStep();
  const off = busy() || !info;
  $('actDelete').disabled = off;
  startBtn.disabled = off || !understood.checked;
  $('changeCancel').disabled = false;
}

async function refresh(force = false) {
  const answer = await getJson(api);
  if (answer.status === 200 && answer.data) {
    info = answer.data;
    appState.info = info;
    if (appState.message === NOT_ANSWERING) say('');
    if (info.job && (info.job.state === 'running' || info.job.state === 'waiting')) followJob(info.job.id);
  } else if (answer.status === 404) {
    info = null;
    say('This model is no longer here: it may have been moved to the bin. Go back to your models.');
  } else {
    say(NOT_ANSWERING);
  }
  render(force);
}

(async () => {
  await refresh();
  appState.ready = true;
  for (;;) {
    await sleep(busy() ? POLL_BUSY_MS : POLL_IDLE_MS);
    await refresh();
  }
})();
