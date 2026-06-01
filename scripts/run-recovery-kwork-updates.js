#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { runFlowContent } = require(path.join(__dirname, '..', 'browser-flow.js'));

const ROOT = path.join(__dirname, '..');
const UPDATE = path.join(ROOT, 'scripts', 'recovery-update-current-kwork.js');
const SCROLL_SAVE = path.join(ROOT, 'scripts', 'scroll-to-kwork-save.js');

const defaultIds = [
  '45587052',
  '51213975',
  '45979524',
  '51213619',
  '40740429',
];

const ids = process.argv.slice(2).filter((id) => /^\d+$/.test(id));
if (!ids.length) ids.push(...defaultIds);

function quote(value) {
  return `"${String(value).replace(/\\/g, '/').replace(/"/g, '\\"')}"`;
}

function lastMatch(output, key) {
  const matches = output.match(new RegExp(`"${key}":\\s*"([^"]+)"`, 'g'));
  return matches ? matches.at(-1).replace(new RegExp(`^"${key}":\\s*"|"$`, 'g'), '') : null;
}

async function runJob(id) {
  const firstFlow = [
    'new-page url="about:blank"',
    `open url=${quote(`https://kwork.ru/edit?id=${id}`)}`,
    'wait ms=3000',
    `eval file=${quote(UPDATE)}`,
    'wait ms=1500',
    `eval file=${quote(UPDATE)}`,
    `eval file=${quote(SCROLL_SAVE)}`,
    'click selector=".js-save-kwork"',
    'wait ms=10000',
    'info',
  ].join('\n');

  let result = await runFlowContent(firstFlow, { source: `recovery-kwork:${id}:first` });
  let url = lastMatch(result.output, 'url');

  if (url && url.includes('/edit?')) {
    const secondFlow = [
      `eval file=${quote(SCROLL_SAVE)}`,
      'click selector=".js-save-kwork"',
      'wait ms=10000',
      'info',
    ].join('\n');
    const second = await runFlowContent(secondFlow, { source: `recovery-kwork:${id}:second` });
    result = { output: `${result.output}\n${second.output}` };
    url = lastMatch(result.output, 'url');
  }

  return {
    id,
    title: lastMatch(result.output, 'title'),
    url,
  };
}

(async () => {
  const summary = [];
  for (const id of ids) {
    const item = await runJob(id);
    summary.push(item);
    process.stdout.write(`${JSON.stringify(item)}\n`);
  }
  process.stdout.write(`${JSON.stringify({ ok: true, summary }, null, 2)}\n`);
})().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
