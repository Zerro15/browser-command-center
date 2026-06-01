#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { loadState, saveState } = require(path.join(__dirname, 'browser-bridge.js'));
const { runFlowContent, redactFlowLine } = require(path.join(__dirname, 'browser-flow.js'));

const KWORK_URL = 'https://kwork.ru/';
const KWORK_SELLER_URL = 'https://kwork.ru/seller';
const KWORK_EDIT_URL = 'https://kwork.ru/edit?id=';
const COVER_INPUT_SELECTOR = "input[type=file][name='first-kwork-photo[]']";
const SCROLL_TO_COVER_SCRIPT = path.join(__dirname, 'scripts', 'scroll-to-cover.js');

function parseStringArg(args, name, fallback = null) {
  const prefix = `${name}=`;
  const token = args.find((item) => item.startsWith(prefix));
  return token ? token.slice(prefix.length) : fallback;
}

function quoteValue(value) {
  return `"${String(value).replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/"/g, '\\"')}"`;
}

async function runNamedFlow(flow, source) {
  return runFlowContent(flow, { source });
}

function parseApproval(args) {
  return parseStringArg(args, 'approve', 'false').toLowerCase() === 'true';
}

function requireApproval(args, action) {
  if (!parseApproval(args)) {
    throw new Error(`${action} requires approve=true after manual review`);
  }
}

function requireDangerConfirmation(args, action) {
  const confirmed = parseStringArg(args, 'danger-confirm-publish', 'false').toLowerCase() === 'true';
  if (!confirmed) {
    throw new Error(`${action} is blocked. Use the visible browser manually after review.`);
  }
}

function buildEditUrl(id) {
  const trimmed = String(id || '').trim();
  if (!/^\d+$/.test(trimmed)) {
    throw new Error('id must be numeric, e.g. id=40740429');
  }
  return `${KWORK_EDIT_URL}${trimmed}`;
}

async function commandOpenSeller() {
  const flow = `new-page url="about:blank"\nopen url=${quoteValue(KWORK_SELLER_URL)}\nwait ms=2500\ninfo\nlist-buttons\nscreenshot`;
  const result = await runNamedFlow(flow, 'browser-kwork:open-seller');
  process.stdout.write(result.output);
}

async function commandOpenHome() {
  const flow = `new-page url="about:blank"\nopen url=${quoteValue(KWORK_URL)}\nwait ms=2500\ninfo\nlist-buttons\nscreenshot`;
  const result = await runNamedFlow(flow, 'browser-kwork:open-home');
  process.stdout.write(result.output);
}

async function commandInspect() {
  const flow = `info\nlist-buttons\nlist-fields\nscreenshot`;
  const result = await runNamedFlow(flow, 'browser-kwork:inspect');
  process.stdout.write(result.output);
}

async function commandOpenOrders() {
  const flow = [
    'new-page url="about:blank"',
    `open url=${quoteValue('https://kwork.ru/manage_orders')}`,
    'wait ms=2500',
    'info',
    'list-buttons',
    'list-fields',
    'screenshot',
  ].join('\n');
  const result = await runNamedFlow(flow, 'browser-kwork:open-orders');
  process.stdout.write(result.output);
}

async function commandOpenChat() {
  const flow = [
    'new-page url="about:blank"',
    `open url=${quoteValue('https://kwork.ru/inbox')}`,
    'wait ms=2500',
    'info',
    'list-buttons',
    'list-fields',
    'screenshot',
  ].join('\n');
  const result = await runNamedFlow(flow, 'browser-kwork:open-chat');
  process.stdout.write(result.output);
}

async function commandOpenKworks() {
  const flow = [
    'new-page url="about:blank"',
    `open url=${quoteValue('https://kwork.ru/manage_kworks')}`,
    'wait ms=2500',
    'info',
    'list-buttons',
    'list-fields',
    'screenshot',
  ].join('\n');
  const result = await runNamedFlow(flow, 'browser-kwork:open-kworks');
  process.stdout.write(result.output);
}

async function commandListMyKworks() {
  const js = `(() => {
    const cards = Array.from(document.querySelectorAll('div[data-kwork-id]'));
    return cards.map((c) => {
      const id = c.getAttribute('data-kwork-id');
      const a = Array.from(c.querySelectorAll('a[href]')).find((x) => (x.innerText || '').trim().length > 0);
      const title = (a ? a.innerText : c.innerText).replace(/\\s+/g, ' ').trim().slice(0, 120);
      return { id, title, href: a ? a.href : null };
    });
  })()`;

  const flow = [
    'info',
    `eval js=${quoteValue(js)}`,
  ].join('\n');
  const result = await runNamedFlow(flow, 'browser-kwork:list-my-kworks');
  process.stdout.write(result.output);
}

async function commandEdit(args) {
  const id = parseStringArg(args, 'id', null);
  if (!id) {
    throw new Error('edit requires id=<kworkId>');
  }
  const url = buildEditUrl(id);

  const flow = [
    'new-page url="about:blank"',
    `open url=${quoteValue(url)}`,
    'wait ms=2500',
    `eval file=${quoteValue(SCROLL_TO_COVER_SCRIPT)}`,
    'screenshot',
    'list-fields',
  ].join('\n');

  const result = await runNamedFlow(flow, 'browser-kwork:edit');
  process.stdout.write(result.output);
}

async function commandUploadCover(args) {
  const id = parseStringArg(args, 'id', null);
  const file = parseStringArg(args, 'file', null);
  if (!id || !file) {
    throw new Error('upload-cover requires id=<kworkId> file=C:\\path\\cover.png');
  }
  requireApproval(args, 'upload-cover saves Kwork changes');

  const url = buildEditUrl(id);
  const flow = [
    'new-page url="about:blank"',
    `open url=${quoteValue(url)}`,
    'wait ms=2500',
    `eval file=${quoteValue(SCROLL_TO_COVER_SCRIPT)}`,
    `set-files selector=${quoteValue(COVER_INPUT_SELECTOR)} file=${quoteValue(file)}`,
    'wait ms=1500',
    `eval file=${quoteValue(SCROLL_TO_COVER_SCRIPT)}`,
    'screenshot',
    'info',
    'screenshot',
    '# STOP: cover selected. Review and save manually in the visible browser.',
  ].join('\n');

  const result = await runNamedFlow(flow, 'browser-kwork:upload-cover');
  process.stdout.write(result.output);
}

async function commandInspectLogin() {
  const flow = [
    'new-page url="about:blank"',
    `open url=${quoteValue(KWORK_URL)}`,
    'wait ms=2500',
    `click-text text=${quoteValue('Вход')}`,
    'wait ms=1500',
    'list-fields',
    'list-buttons',
    'screenshot',
  ].join('\n');
  const result = await runNamedFlow(flow, 'browser-kwork:inspect-login');
  process.stdout.write(result.output);
}

async function commandLogin(args) {
  if (parseStringArg(args, 'email', null) !== null || parseStringArg(args, 'password', null) !== null) {
    throw new Error('login no longer accepts email/password via argv. Run login and enter credentials manually in the visible browser.');
  }

  const steps = [
    'new-page url="about:blank"',
    `open url=${quoteValue(KWORK_URL)}`,
    'wait ms=2500',
    `click-text text=${quoteValue('Вход')}`,
    'wait ms=1500',
  ];

  steps.push('list-fields');
  steps.push('list-buttons');
  steps.push('screenshot');

  const result = await runNamedFlow(steps.join('\n'), 'browser-kwork:login');
  process.stdout.write(result.output);
}

async function commandReply(args) {
  const text = parseStringArg(args, 'text', null);
  const send = parseStringArg(args, 'send', 'false').toLowerCase() === 'true';

  if (!text) {
    throw new Error('reply requires text=<message>');
  }

  const steps = [
    'list-fields',
    `fill hint=${quoteValue('сообщение')} text=${quoteValue(text)}`,
    'wait ms=400',
    'screenshot',
  ];

  const result = await runNamedFlow(steps.join('\n'), 'browser-kwork:reply');
  process.stdout.write(result.output);
  if (send) {
    process.stdout.write('\nReply text prepared. Press Send manually in the visible browser.\n');
  }
}

async function commandState() {
  const state = loadState();
  const view = {
    port: state.port || null,
    browser: state.browser || null,
    lastTarget: state.lastTarget || null,
    lastFlowSource: state.lastFlowSource || null,
    lastFlowRunAt: state.lastFlowRunAt || null,
    lastFlowPreview: state.lastFlowPreview || [],
  };
  process.stdout.write(`${JSON.stringify(view, null, 2)}\n`);
}

async function commandRemember(args) {
  const note = parseStringArg(args, 'note', null);
  if (!note) {
    throw new Error('remember requires note=<text>');
  }

  const state = loadState();
  state.kworkNote = note;
  state.kworkNoteUpdatedAt = new Date().toISOString();
  saveState(state);
  process.stdout.write(`${JSON.stringify({ ok: true, note }, null, 2)}\n`);
}

async function commandSanitizeState() {
  const state = loadState();
  if (Array.isArray(state.lastFlowPreview)) {
    state.lastFlowPreview = state.lastFlowPreview.map(redactFlowLine);
  }
  saveState(state);
  process.stdout.write(`${JSON.stringify({ ok: true, sanitized: true }, null, 2)}\n`);
}

async function commandHelp() {
  process.stdout.write(`browser-kwork commands:
  open-home
  open-seller
  open-orders
  open-chat
  open-kworks
  list-my-kworks
  edit id=<kworkId>
  upload-cover id=<kworkId> file=C:\\path\\cover.png
  inspect
  inspect-login
  login
  reply text="..." [send=false]
  state
  remember note="..."
  sanitize-state
  help

Examples:
  .\\browser-kwork.cmd open-seller
  .\\browser-kwork.cmd open-orders
  .\\browser-kwork.cmd open-chat
  .\\browser-kwork.cmd inspect
  .\\browser-kwork.cmd list-my-kworks
  .\\browser-kwork.cmd edit id=40740429
  .\\browser-kwork.cmd upload-cover id=40740429 file="C:\\Users\\Bogdan\\Documents\\kwork\\cover.png"
  .\\browser-kwork.cmd inspect-login
  .\\browser-kwork.cmd login
  .\\browser-kwork.cmd reply text="Здравствуйте, готов обсудить детали" send=false
`);
}

async function main() {
  const [, , command = 'help', ...args] = process.argv;
  const handlers = {
    'open-home': commandOpenHome,
    'open-seller': commandOpenSeller,
    'open-orders': commandOpenOrders,
    'open-chat': commandOpenChat,
    'open-kworks': commandOpenKworks,
    'list-my-kworks': commandListMyKworks,
    edit: () => commandEdit(args),
    'upload-cover': () => commandUploadCover(args),
    inspect: commandInspect,
    'inspect-login': commandInspectLogin,
    login: () => commandLogin(args),
    reply: () => commandReply(args),
    state: commandState,
    remember: () => commandRemember(args),
    'sanitize-state': commandSanitizeState,
    help: commandHelp,
  };

  const handler = handlers[command];
  if (!handler) {
    throw new Error(`Unknown browser-kwork command: ${command}`);
  }

  await handler();
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exitCode = 1;
});
