#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { runFlowContent } = require(path.join(__dirname, '..', 'browser-flow.js'));

const ROOT = path.join(__dirname, '..');
const UPDATE = path.join(ROOT, 'scripts', 'profit-update-current-kwork.js');
const SCROLL_SAVE = path.join(ROOT, 'scripts', 'scroll-to-kwork-save.js');
const COVER_DIR = path.join(ROOT, 'covers-profit');

const jobs = [
  ['40740429', '40740429-telegram-ai-bot.png'],
  ['45979524', '45979524-python-parser.png'],
  ['46004001', '46004001-api-webhook.png'],
  ['45587052', '45587052-code-fix.png'],
  ['27194497', '27194497-web-tool.png'],
  ['51213619', '51213619-sheets-telegram.png'],
  ['51213975', '51213975-excel-csv.png'],
  ['51214672', '51214672-browser-automation.png'],
];

function quote(value) {
  return `"${String(value).replace(/\\/g, '/').replace(/"/g, '\\"')}"`;
}

async function runJob(id, coverFile) {
  const flow = [
    'new-page url="about:blank"',
    `open url=${quote(`https://kwork.ru/edit?id=${id}`)}`,
    'wait ms=2500',
    `eval file=${quote(UPDATE)}`,
    `set-files selector=${quote("input[type=file][name='first-kwork-photo[]']")} file=${quote(path.join(COVER_DIR, coverFile))}`,
    'wait ms=1800',
    `eval file=${quote(UPDATE)}`,
    `eval file=${quote(SCROLL_SAVE)}`,
    'click selector=".js-save-kwork"',
    'wait ms=9000',
    'info',
  ].join('\n');

  const result = await runFlowContent(flow, { source: `profit-kwork:${id}` });
  const publicUrlMatch = result.output.match(/"url":\s*"([^"]+)"/g);
  const lastUrl = publicUrlMatch ? publicUrlMatch.at(-1).replace(/^"url":\s*"|"$/g, '') : null;
  return { id, coverFile, lastUrl, output: result.output };
}

(async () => {
  const summary = [];
  for (const [id, coverFile] of jobs) {
    const result = await runJob(id, coverFile);
    summary.push({ id: result.id, coverFile: result.coverFile, lastUrl: result.lastUrl });
    process.stdout.write(`${JSON.stringify(summary.at(-1))}\n`);
  }
  process.stdout.write(`${JSON.stringify({ ok: true, summary }, null, 2)}\n`);
})().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
