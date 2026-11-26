// BrickSnap web app: the page of a model the AI built from parts (a "free build";
// bricksnap/lab/freebuild.py, bricksnap/webapp.py). EXPERIMENTAL.
//
// The model turning under a slider (twelve pictures round it), what the checker says, the
// AI's own notes, "Ask for a change" with the same kind of agreement as the AI designer's,
// "Polish it" (an outside eye's fixes, then one change; lab/critic.py) and what the outside
// eye asked of a polished run, the downloads, the earlier runs, and the bin. Text from the server, the person and the AI
// goes in with textContent, never innerHTML.

import { FREE_DEFAULT_MODEL, FREE_MODELS, JobView, NOT_ANSWERING, appState, el, freeModelName, freePolishTimeAndCost, freeTimeAndCost, getJson, outsideEye, plural, postJson, refusal, sleep } from './app.js';

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
  const moves = Array.isArray(info.moves) ? info.moves.map(String) : [];
  $('moves').replaceChildren(...moves.map((text) => el('li', { text })));
  $('movesBox').hidden = !moves.length;
  const opened = typeof info.opened === 'string' ? info.opened : '';
  $('openedLink').hidden = !opened;
  if (opened) $('openedLink').href = opened;
  const looks = Array.isArray(info.looks_lines) ? info.looks_lines.map(String) : [];
  $('looks').replaceChildren(...looks.map((text) => el('li', { text })));
  $('looksBox').hidden = !looks.length;
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

// ---- the art direction and the critique (a run made with the guide; lab/art.py) ----

const BRIEF_FIRST = [
  ['scale', 'Scale'],
  ['colours', 'Colours'],
  ['pattern', 'Pattern'],
];
const BRIEF_MORE = [
  ['shapes', 'Shapes'],
  ['sideways', 'Built sideways'],
  ['thin', 'Kept thin'],
  ['studs', 'Studs'],
  ['glass', 'Glass and stance'],
  ['why_more', 'Why more colours'],
];

function colourItem(c) {
  const value = /^#[0-9A-Fa-f]{6}$/.test(String(c.value || '')) ? c.value : '#cccccc';
  const trans = /^trans/i.test(String(c.name || ''));
  const swatch = el('span', { className: `swatch${trans ? ' trans' : ''}`, 'aria-hidden': 'true' });
  swatch.style.backgroundColor = value;
  const share = c.share ? `, ${c.share}` : '';
  return el('li', { className: 'colour' }, [
    swatch,
    el('span', {}, [
      document.createTextNode(`${c.name || 'Colour'} `),
      el('span', { className: 'code', text: `(${c.code})` }),
      document.createTextNode(`: ${c.job || ''}${share}`),
    ]),
  ]);
}

function briefRows(brief, which) {
  const rows = [];
  for (const [k, words] of which) {
    const v = brief[k];
    if (v === undefined || v === null || v === '') continue;
    let dd;
    if (k === 'colours' && Array.isArray(v)) dd = el('dd', {}, [el('ul', {}, v.map(colourItem))]);
    else if (k === 'shapes' && Array.isArray(v)) dd = el('dd', {}, [el('ul', {}, v.map((s) => el('li', { text: `${s.shape}: ${s.part}` })))]);
    else dd = el('dd', { text: String(v) });
    rows.push(el('dt', { text: words }), dd);
  }
  return rows;
}

// What happened to the brief in this run, in plain words.
function briefStory(info) {
  const s = info.brief_story;
  if (!info.brief) {
    return info.built_without_brief
      ? 'The AI wrote no art direction for this run: it built without one.'
      : 'The AI wrote no art direction for this run.';
  }
  const said = [];
  if (s && s.carried) {
    said.push(s.carried_from ? `Carried over from run ${s.carried_from}, when the model was built; the change was built to it.` : 'Carried over from the run the model was built in.');
  } else if (s && typeof s.parts_before === 'number' && s.parts_before > 0) {
    said.push(`Written after ${plural(s.parts_before, 'part')} were already in.`);
  } else {
    said.push('Written before the first part: the look it then built to.');
  }
  if (s && s.versions > 1) {
    const changed = s.versions - 1;
    said.push(`Changed ${changed === 1 ? 'once' : `${changed} times`}${s.last_reason ? `; the last reason: “${s.last_reason}”` : ''}. This is the last version.`);
  }
  return said.join(' ');
}

let shownBrief = '';
function showBrief() {
  const art = info && info.art === true;
  const brief = art && info.brief && typeof info.brief === 'object' ? info.brief : null;
  const key = JSON.stringify(art ? [info.brief, info.brief_story, info.built_without_brief] : null);
  if (key === shownBrief) return;
  shownBrief = key;
  $('artCard').hidden = !art;
  if (!art) {
    $('artBrief').replaceChildren();
    $('artBriefMore').replaceChildren();
    return;
  }
  $('artSays').textContent = briefStory(info);
  $('artBrief').replaceChildren(...(brief ? briefRows(brief, BRIEF_FIRST) : []));
  const more = brief ? briefRows(brief, BRIEF_MORE) : [];
  $('artBriefMore').replaceChildren(...more);
  $('artMore').hidden = more.length === 0;
}

let shownCritique = '';
function showCritique() {
  const art = info && info.art === true;
  const critique = art && info.critique && Array.isArray(info.critique.answers) ? info.critique : null;
  const key = JSON.stringify(art ? [critique, info.first_no, info.critiques] : null);
  if (key === shownCritique) return;
  shownCritique = key;
  $('critiqueCard').hidden = !art;
  const flags = [];
  if (!art) {
    $('critique').replaceChildren();
    $('critiqueFlags').replaceChildren();
    $('factsBox').hidden = true;
    return;
  }
  if (!critique) {
    $('critiqueSays').textContent = 'The run ended without a critique: the AI did not hand the model in with its answers.';
    $('critique').replaceChildren();
    $('critiqueFlags').replaceChildren();
    $('factsBox').hidden = true;
    return;
  }
  const answers = critique.answers.slice();
  const no = answers.filter((a) => a.answer === 'no');
  const ordered = no.concat(answers.filter((a) => a.answer !== 'no')); // the "no"s first
  $('critiqueSays').textContent = `${answers.length - no.length} yes, ${no.length} no.`;
  if (Array.isArray(info.first_no) && info.first_no.length) {
    flags.push(`Its first critique said no to ${plural(info.first_no.length, 'question')}; it was sent back to rebuild, and this is its answer after that.`);
  }
  if (critique.changed_after) flags.push('The model was changed after this critique, so it may not describe the model as it is now.');
  if (Array.isArray(critique.unexplained) && critique.unexplained.length) flags.push(`It gave no real reason for ${plural(critique.unexplained.length, '“no”')}.`);
  for (const m of Array.isArray(critique.mismatches) ? critique.mismatches : []) flags.push(String(m));
  $('critiqueFlags').replaceChildren(...flags.map((f) => el('li', { text: f })));
  const facts = critique.facts && typeof critique.facts === 'object' ? critique.facts : null;
  const factLines = [];
  if (facts) {
    if (typeof facts.parts === 'number') factLines.push(`Parts: ${facts.parts}${facts.parts_wanted ? ` of about ${facts.parts_wanted} asked for` : ''}.`);
    if (facts.size) factLines.push(`Size: ${facts.size.wide} studs wide, ${facts.size.long} long, ${facts.size.high_bricks} bricks high.`);
    if (Array.isArray(facts.colours) && facts.colours.length) factLines.push(`Colours by bulk: ${facts.colours.slice(0, 5).map((c) => `${c.name} ${Math.round(c.share * 100)}%`).join(', ')}.`);
    if (Array.isArray(facts.glass)) factLines.push(`Transparent parts: ${facts.glass.length ? facts.glass.map((g) => `${g.name} (${g.parts})`).join(', ') : 'none'}.`);
    for (const l of Array.isArray(facts.looks) ? facts.looks : []) factLines.push(String(l));
  }
  $('factsBox').hidden = factLines.length === 0;
  $('facts').replaceChildren(...factLines.map((f) => el('li', { text: f })));
  $('critique').replaceChildren(
    ...ordered.map((a) =>
      el('li', { className: a.answer === 'no' ? 'no' : 'yes' }, [
        el('span', { className: 'ans', text: a.answer === 'no' ? 'No' : 'Yes' }),
        el('span', { className: 'q' }, [
          document.createTextNode(a.question || a.key || ''),
          a.note ? el('span', { className: 'note', text: a.note }) : null,
          a.answer === 'no' && !a.note ? el('span', { className: 'note', text: 'It gave no reason.' }) : null,
        ]),
      ]),
    ),
  );
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

// Whether a run had the set designers' guide, and the playbook the builder asked for.
function guideWords(r) {
  if (r.guide === true) {
    const book = r.playbook ? `; playbook it asked for: ${r.playbook}` : '; it asked for no playbook';
    return `Built the way set designers do${book}`;
  }
  if (r.guide === false) return 'Built the usual way (no set designers’ guide)';
  return '';
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
    if (r.model) facts.push(`by ${freeModelName(r.model)}`);
    const polished = r.polish && typeof r.polish === 'object' && Array.isArray(r.polish.fixes) ? r.polish.fixes.length : null;
    const head = el('span', { className: 'vname' }, [
      el('span', { className: 'vn', text: String(r.n) }),
      el('span', { className: 'vlabel', text: polished !== null ? 'Polished' : RUN_WORDS[r.kind] || r.kind }),
    ]);
    let said = r.words ? `“${r.words}”` : '';
    if (polished !== null) said = `The ${polished === 1 ? 'fix' : `${polished} fixes`} an outside eye asked for`;
    const parts = [
      pic,
      el('span', { className: 'vtext' }, [
        head,
        said ? el('span', { className: 'rwords', text: said }) : null,
        guideWords(r) ? el('span', { className: 'rguide', text: guideWords(r) }) : null,
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
const changeModel = $('changeModel');

// ---- what it was built from: the person's pictures and 3D model ----

let shownRefs = '';
function showBuiltFrom() {
  const pics = info && Array.isArray(info.reference_pictures) ? info.reference_pictures.map(String) : [];
  const model = info && info.reference_model && typeof info.reference_model === 'object' ? info.reference_model : null;
  const key = JSON.stringify([pics, model]);
  if (key === shownRefs) return;
  shownRefs = key;
  const items = pics.map((url, k) =>
    el('li', {}, [el('a', { href: url, target: '_blank', rel: 'noopener' }, [el('img', { src: url, alt: `Picture ${k + 1} it was built from` })])]),
  );
  if (model) {
    const figure = el('figure', { className: 'sheet' }, [
      model.sheet ? el('img', { src: String(model.sheet), alt: `The 3D model ${model.name} from five sides` }) : null,
      el('figcaption', { text: `Built from: ${model.name}` }),
    ]);
    items.push(el('li', { className: 'sheet' }, [model.sheet ? el('a', { href: String(model.sheet), target: '_blank', rel: 'noopener' }, [figure]) : figure]));
  }
  $('refPics').replaceChildren(...items);
  $('builtFromTitle').textContent = pics.length && !model ? `Built from ${pics.length === 1 ? 'this picture' : 'these pictures'}` : 'Built from';
  $('builtFrom').hidden = items.length === 0;
}

function changeWords() {
  const size = (info && info.parts) || (info && info.parts_wanted) || 80; // the model's own size
  const model = changeModel.value;
  $('changeTime').textContent = `It is one AI run by ${freeModelName(model)}, starting from the model as it is now. ${freeTimeAndCost(size, model)} You can leave this page while it works.`;
  const refs = (info && Array.isArray(info.reference_pictures) && info.reference_pictures.length) || (info && info.reference_model);
  $('changeSends').textContent = `It sends the words you typed, and the words the model was first built from${refs ? ', with the pictures it was built from,' : ''} to the AI provider, Anthropic, through Claude Code. Nothing else in BrickSnap sends anything off your computer.`;
}
changeModel.addEventListener('change', () => {
  understood.checked = false;
  startBtn.disabled = true;
  changeWords();
});

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
    const polish = el('button', {
      type: 'button',
      className: 'quiet',
      id: 'polishBtn',
      text: 'Polish it…',
      title: 'An outside eye, a separate AI shown only the pictures, lists up to five fixes; then the AI makes them.',
    });
    polish.onclick = openPolish;
    parts.push(el('div', { className: 'ask' }, built ? [input, ask, polish] : [input, ask]));
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
  polishBox.hidden = true;
  understood.checked = false;
  startBtn.disabled = true;
  $('changeWhat').replaceChildren(
    document.createTextNode('Your change, as the AI will get it: '),
    el('span', { className: 'quote', id: 'changeQuote', text: `“${words}”` }),
    document.createTextNode('. The AI makes that change and keeps the rest of the model as it is.'),
  );
  changeModel.value = info && FREE_MODELS[info.model] ? info.model : FREE_DEFAULT_MODEL;
  changeWords();
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
  await start('change', { words: pendingWords, model: changeModel.value, understood: true, understood_runs: 1 });
  const input = $('askText');
  if (input && following) input.value = '';
});

// ---- polishing: an outside eye's fixes, then one change ----

const polishBox = $('polishConfirm');
const polishUnderstood = $('polishUnderstood');
const polishStart = $('polishStart');
const polishModel = $('polishModel');

function polishWords() {
  const size = (info && info.parts) || (info && info.parts_wanted) || 80; // the model's own size
  const model = polishModel.value;
  $('polishTime').textContent = `It is two AI runs by ${freeModelName(model)}. ${freePolishTimeAndCost(size, model)} You can leave this page while it works.`;
  const refs = (info && Array.isArray(info.reference_pictures) && info.reference_pictures.length) || (info && info.reference_model);
  $('polishSends').textContent = `It sends the model's pictures, its art direction and the words it was built from${refs ? ', with the pictures it was built from,' : ''} to the AI provider, Anthropic, through Claude Code: first to the outside eye, then, with its list, to the AI that builds. Nothing else in BrickSnap sends anything off your computer.`;
}
polishModel.addEventListener('change', () => {
  polishUnderstood.checked = false;
  polishStart.disabled = true;
  polishWords();
});

function openPolish() {
  if (busy()) return;
  say('');
  confirmBox.hidden = true;
  polishUnderstood.checked = false;
  polishStart.disabled = true;
  polishModel.value = info && FREE_MODELS[info.model] ? info.model : FREE_DEFAULT_MODEL;
  polishWords();
  polishBox.hidden = false;
  polishBox.scrollIntoView({ block: 'nearest' });
  polishUnderstood.focus();
}

function closePolish() {
  polishBox.hidden = true;
  const opener = $('polishBtn');
  if (opener) opener.focus();
}

polishUnderstood.addEventListener('change', () => {
  polishStart.disabled = !polishUnderstood.checked || busy();
});
$('polishCancel').addEventListener('click', closePolish);
polishBox.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closePolish();
});
polishStart.addEventListener('click', async () => {
  if (!polishUnderstood.checked) return;
  polishBox.hidden = true;
  await start('polish', { model: polishModel.value, understood: true, understood_runs: 2 });
});

// What the outside eye asked of the run shown now (a polished run).
let shownPolish = '';
function showPolish() {
  const p = info && info.polish && typeof info.polish === 'object' ? info.polish : null;
  const key = JSON.stringify(p);
  if (key === shownPolish) return;
  shownPolish = key;
  $('polishCard').hidden = !p;
  if (!p) {
    $('polishList').replaceChildren();
    return;
  }
  const of = typeof p.of_run === 'number' ? ` of run ${p.of_run}` : '';
  $('polishSays').textContent = `An outside eye, a separate AI shown only the pictures${of}, the words, the art direction and how it measured, asked for these fixes, the most visible first. This run is the AI's change to make them.`;
  $('polishList').replaceChildren(outsideEye(p, ''));
}

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
    $('guideNote').hidden = !info.guide;
    $('guideNote').textContent = info.guide
      ? 'Designed first, then built the way set designers do (experimental): an art direction, a core with sides pressed on, a critique of its own pictures. Changes are made the same way.'
      : '';
    document.title = `${info.name} - BrickSnap`;
    showChecker();
  }
  showTurntable();
  showBuiltFrom();
  showPolish();
  showBrief();
  showNotes();
  showCritique();
  showDownloads();
  showRuns();
  showNextStep();
  const off = busy() || !info;
  $('actDelete').disabled = off;
  startBtn.disabled = off || !understood.checked;
  $('changeCancel').disabled = false;
  polishStart.disabled = off || !polishUnderstood.checked;
  $('polishCancel').disabled = false;
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
