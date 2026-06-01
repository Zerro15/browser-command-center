#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { runFlowContent } = require(path.join(__dirname, '..', 'browser-flow.js'));

const ROOT = path.join(__dirname, '..');
const UPDATE = path.join(ROOT, 'scripts', 'profit-update-current-kwork.js');
const SCROLL_SAVE = path.join(ROOT, 'scripts', 'scroll-to-kwork-save.js');

const ids = [
  '51213284',
  '40740429',
  '45979524',
  '46004001',
  '45587052',
  '27194497',
  '51213619',
  '51213975',
  '51214672',
];

function quote(value) {
  return `"${String(value).replace(/\\/g, '/').replace(/"/g, '\\"')}"`;
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

  let result = await runFlowContent(firstFlow, { source: `profit-price-fix:${id}:first` });
  let urlMatches = result.output.match(/"url":\s*"([^"]+)"/g);
  let lastUrl = urlMatches ? urlMatches.at(-1).replace(/^"url":\s*"|"$/g, '') : null;

  if (lastUrl && lastUrl.includes('/edit?')) {
    const secondFlow = [
      `eval file=${quote(SCROLL_SAVE)}`,
      'click selector=".js-save-kwork"',
      'wait ms=10000',
      'info',
    ].join('\n');
    const secondResult = await runFlowContent(secondFlow, { source: `profit-price-fix:${id}:second` });
    result = { output: `${result.output}\n${secondResult.output}` };
  }

  urlMatches = result.output.match(/"url":\s*"([^"]+)"/g);
  const titleMatches = result.output.match(/"title":\s*"([^"]+)"/g);
  return {
    id,
    title: titleMatches ? titleMatches.at(-1).replace(/^"title":\s*"|"$/g, '') : null,
    url: urlMatches ? urlMatches.at(-1).replace(/^"url":\s*"|"$/g, '') : null,
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
