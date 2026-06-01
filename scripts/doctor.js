#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

const chromeCandidates = [
  process.env.BROWSER_BRIDGE_CHROME,
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/snap/bin/chromium',
  '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
  '/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

function commandVersion(command, args = ['--version']) {
  const result = spawnSync(command, args, { encoding: 'utf8' });
  if (result.status !== 0 || (!(result.stdout || result.stderr) && result.error)) {
    return null;
  }
  return (result.stdout || result.stderr || '').trim();
}

const nodeVersion = commandVersion(process.execPath, ['--version']);
const chromePath = chromeCandidates.find((candidate) => fs.existsSync(candidate));

const checks = {
  node: {
    ok: Boolean(nodeVersion),
    version: nodeVersion,
    install: 'Ubuntu: sudo apt update && sudo apt install -y nodejs npm',
  },
  chrome: {
    ok: Boolean(chromePath),
    path: chromePath || null,
    install: 'Ubuntu: install google-chrome-stable or chromium, or set BROWSER_BRIDGE_CHROME=/path/to/browser',
  },
  covers: {
    ok: fs.existsSync('covers'),
    path: 'covers',
    install: 'Regenerate/copy cover PNG files into ./covers if missing.',
  },
};

console.log(JSON.stringify(checks, null, 2));

if (!Object.values(checks).every((check) => check.ok)) {
  process.exitCode = 1;
}
