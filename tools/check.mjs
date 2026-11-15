// Pre-push check: node tools/check.mjs
// Confirms the app's inline script still parses and that every local file the page refers to exists.
// It does not test behaviour; see "Verifying a change" in AGENTS.md.
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const problems = [];

const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
if (!scripts.length) problems.push('index.html has no inline script');
for (const m of scripts) {
  const line = html.slice(0, m.index).split('\n').length;
  try {
    new vm.Script(m[1], { filename: 'index.html', lineOffset: line - 1 });
  } catch (e) {
    problems.push(`script does not parse: ${e.message}\n${String(e.stack).split('\n').slice(0, 3).join('\n')}`);
  }
}

const refs = new Set([...html.matchAll(/(?:sample-photos|sample-models)\/[\w./-]+\.\w+/g)].map(m => m[0]));
for (const r of refs) if (!existsSync(join(root, r))) problems.push(`missing file referenced by index.html: ${r}`);

if (problems.length) {
  console.error('CHECK FAILED\n' + problems.join('\n'));
  process.exit(1);
}
console.log(`check passed: ${scripts.length} script parsed, ${refs.size} referenced files found`);
