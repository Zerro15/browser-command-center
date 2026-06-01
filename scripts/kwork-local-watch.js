#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { commandHandlers, loadState, saveState } = require(path.join(__dirname, '..', 'browser-bridge.js'));

const ROOT = path.join(__dirname, '..');
const DEFAULT_INTERVAL_MS = 5 * 60 * 1000;

function argValue(name, fallback = null) {
  const prefix = `${name}=`;
  const token = process.argv.slice(2).find((item) => item.startsWith(prefix));
  return token ? token.slice(prefix.length) : fallback;
}

function hasFlag(name) {
  return process.argv.slice(2).includes(name);
}

function quote(value) {
  return `"${String(value).replace(/\\/g, '/').replace(/"/g, '\\"')}"`;
}

function hash(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex').slice(0, 16);
}

function compact(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

function timestamp() {
  return new Date().toLocaleString('ru-RU', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

async function ensureBridge() {
  const state = loadState();
  const port = Number(state.port || 9222);
  try {
    const response = await fetch(`http://127.0.0.1:${port}/json/version`);
    if (response.ok) return;
  } catch {
    // Start below.
  }

  const result = spawnSync(process.execPath, ['browser-bridge.js', 'start'], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(`Unable to start browser bridge: ${result.stderr || result.stdout}`);
  }
}

async function runBridge(command, args = []) {
  const handler = commandHandlers[command];
  if (!handler) {
    throw new Error(`Unknown bridge command: ${command}`);
  }

  const writes = [];
  const originalLog = console.log;
  const originalWrite = process.stdout.write;
  console.log = (...items) => {
    writes.push(items.join(' '));
  };
  process.stdout.write = (chunk, ...args) => {
    writes.push(String(chunk));
    if (typeof args.at(-1) === 'function') args.at(-1)();
    return true;
  };

  try {
    await handler(args);
  } finally {
    console.log = originalLog;
    process.stdout.write = originalWrite;
  }

  return writes.join('\n').trim();
}

async function inspectPage(url, source) {
  const js = "(() => { const text = document.body ? document.body.innerText : ''; const links = Array.from(document.querySelectorAll('a[href]')).map((a) => ({ text: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 140), href: a.href })).filter((item) => item.text).slice(0, 30); const chatMatch = text.match(/Чат\\s*(\\d+)/i); const orderHints = (text.match(/(нов\\S*|сообщ\\S*|заказ\\S*|треб\\S* ответа|арбитраж|просроч\\S*)/gi) || []).slice(0, 20); return { url: location.href, title: document.title, chatCount: chatMatch ? Number(chatMatch[1]) : null, hints: orderHints, sample: text.slice(0, 2500), links }; })()";

  const created = JSON.parse(await runBridge('new-page', ['url=about:blank']));
  await runBridge('open', [`target=${created.id}`, `url=${url}`]);
  await new Promise((resolve) => setTimeout(resolve, 2500));
  const jsonText = await runBridge('eval', [`target=${created.id}`, `js=${js}`]);
  try {
    return JSON.parse(jsonText);
  } catch (error) {
    throw new Error(`Unable to parse ${source} inspect output: ${error.message}`);
  }
}

function summarizeInbox(data) {
  const text = compact(data.sample);
  const snippets = [];
  const messageMatch = text.match(/(?:Чат\s*\d+)?(.{0,180}(?:сообщ|написал|диалог|чат).{0,180})/i);
  if (messageMatch) snippets.push(compact(messageMatch[1]).slice(0, 220));
  for (const link of data.links.slice(0, 5)) {
    snippets.push(link.text);
  }
  return {
    title: data.title,
    chatCount: data.chatCount,
    hints: data.hints,
    snippets: [...new Set(snippets.filter(Boolean))].slice(0, 5),
    digest: hash(`${data.chatCount}|${data.hints.join('|')}|${data.links.map((x) => x.text).join('|')}|${text.slice(0, 800)}`),
  };
}

function summarizeOrders(data) {
  const text = compact(data.sample);
  const important = [];
  for (const pattern of [
    /нов\S* заказ.{0,160}/i,
    /треб\S* ответа.{0,160}/i,
    /в работе.{0,160}/i,
    /просроч\S*.{0,160}/i,
    /арбитраж.{0,160}/i,
  ]) {
    const match = text.match(pattern);
    if (match) important.push(compact(match[0]));
  }
  return {
    title: data.title,
    hints: data.hints,
    snippets: [...new Set([...important, ...data.links.slice(0, 5).map((x) => x.text)].filter(Boolean))].slice(0, 6),
    digest: hash(`${data.hints.join('|')}|${data.links.map((x) => x.text).join('|')}|${text.slice(0, 1000)}`),
  };
}

async function checkOnce() {
  await ensureBridge();

  const inbox = await inspectPage('https://kwork.ru/inbox', 'kwork-watch:inbox');
  const orders = await inspectPage('https://kwork.ru/manage_orders', 'kwork-watch:orders');

  const current = {
    checkedAt: new Date().toISOString(),
    inbox: summarizeInbox(inbox),
    orders: summarizeOrders(orders),
  };

  const state = loadState();
  const previous = state.kworkLocalWatch || null;
  const changed = Boolean(previous)
    && (previous.inbox?.digest !== current.inbox.digest || previous.orders?.digest !== current.orders.digest);

  state.kworkLocalWatch = current;
  saveState(state);

  const lines = [
    `[${timestamp()}] Kwork watch`,
    `inbox: chat=${current.inbox.chatCount ?? 'n/a'} digest=${current.inbox.digest}`,
    `orders: digest=${current.orders.digest}`,
  ];

  if (!previous) {
    lines.push('baseline saved');
  } else if (changed) {
    lines.push('\u0007CHANGE DETECTED: open Kwork inbox/orders');
  } else {
    lines.push('no changes');
  }

  if (changed || hasFlag('--verbose')) {
    if (current.inbox.snippets.length) lines.push(`inbox snippets: ${current.inbox.snippets.join(' | ')}`);
    if (current.orders.snippets.length) lines.push(`orders snippets: ${current.orders.snippets.join(' | ')}`);
  }

  process.stdout.write(`${lines.join('\n')}\n`);
  return changed;
}

async function main() {
  const once = hasFlag('--once');
  const intervalMs = Math.max(30_000, Number(argValue('interval', DEFAULT_INTERVAL_MS)));

  if (once) {
    await checkOnce();
    return;
  }

  process.stdout.write(`Kwork local watch started. interval=${intervalMs}ms. Stop with Ctrl+C.\n`);
  while (true) {
    try {
      await checkOnce();
    } catch (error) {
      process.stdout.write(`[${timestamp()}] watch error: ${error.message || String(error)}\n`);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
