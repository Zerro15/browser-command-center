#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ROOT = __dirname;
const { commandHandlers, loadState, saveState } = require(path.join(ROOT, 'browser-bridge.js'));

function parseStringArg(args, name, fallback = null) {
  const prefix = `${name}=`;
  const token = args.find((item) => item.startsWith(prefix));
  return token ? token.slice(prefix.length) : fallback;
}

function parseBooleanArg(args, name, fallback = false) {
  const value = parseStringArg(args, name, null);
  if (value === null) {
    return fallback;
  }
  return value === '1' || value.toLowerCase() === 'true';
}

function parseStepLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) {
    return null;
  }

  const firstSpace = trimmed.indexOf(' ');
  if (firstSpace === -1) {
    return { action: trimmed.toLowerCase(), params: {} };
  }

  const action = trimmed.slice(0, firstSpace).toLowerCase();
  const raw = trimmed.slice(firstSpace + 1);
  const params = {};
  const regex = /(\w+)=("([^"\\]|\\.)*"|'([^'\\]|\\.)*'|[^\s]+)/g;

  for (const match of raw.matchAll(regex)) {
    const key = match[1];
    let value = match[2];
    const quoted = (value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"));
    if (quoted) {
      value = value.slice(1, -1);
      value = decodeQuotedValue(value);
    } else {
      value = value.replace(/\\n/g, '\n');
    }
    params[key] = value;
  }

  return { action, params };
}

function decodeQuotedValue(value) {
  let result = '';
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    if (char !== '\\' || index === value.length - 1) {
      result += char;
      continue;
    }

    const next = value[index + 1];
    index += 1;
    if (next === 'n') result += '\n';
    else if (next === 'r') result += '\r';
    else if (next === 't') result += '\t';
    else result += next;
  }
  return result;
}

function buildArgs(params, extra = {}) {
  const merged = { ...params, ...extra };
  return Object.entries(merged)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${key}=${String(value)}`);
}

function redactFlowLine(line) {
  let result = '';
  let index = 0;
  const sensitiveKeys = new Set(['text', 'body', 'caption', 'subject', 'password', 'email']);

  while (index < line.length) {
    const match = line.slice(index).match(/\b(text|body|caption|subject|password|email)=/i);
    if (!match || match.index === undefined) {
      result += line.slice(index);
      break;
    }

    const keyStart = index + match.index;
    const valueStart = keyStart + match[0].length;
    const key = match[1].toLowerCase();
    result += line.slice(index, valueStart);

    if (!sensitiveKeys.has(key)) {
      index = valueStart;
      continue;
    }

    let valueEnd = valueStart;
    const quote = line[valueStart];
    if (quote === '"' || quote === "'") {
      valueEnd += 1;
      while (valueEnd < line.length) {
        const char = line[valueEnd];
        if (char === '\\') {
          valueEnd += 2;
          continue;
        }
        if (char === quote) {
          valueEnd += 1;
          break;
        }
        valueEnd += 1;
      }
    } else {
      while (valueEnd < line.length && !/\s/.test(line[valueEnd])) {
        valueEnd += 1;
      }
    }

    result += '"[redacted]"';
    index = valueEnd;
  }

  if (/^\s*fill\b/i.test(line)) {
    const hintMatch = result.match(/hint=("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s]+)/i);
    const hintRaw = hintMatch ? hintMatch[1] : '';
    const hint = hintRaw.replace(/^['"]|['"]$/g, '').toLowerCase();
    if (hint.includes('пароль') || hint.includes('password') || hint.includes('почта') || hint.includes('email') || hint.includes('логин')) {
      result = result.replace(/\btext=("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s]+)/i, 'text="[redacted]"');
    }
  }

  return result;
}

async function runBridge(command, params = {}) {
  const handler = commandHandlers[command];
  if (!handler) {
    throw new Error(`Unknown bridge command: ${command}`);
  }

  const args = buildArgs(params);
  const writes = [];
  const originalLog = console.log;

  console.log = (...items) => {
    writes.push(items.join(' '));
  };

  try {
    await handler(args);
  } finally {
    console.log = originalLog;
  }

  return writes.join('\n').trim();
}

function tryParseJson(text) {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function executeStep(step, context) {
  const params = { ...step.params };
  if (context.target && !params.target) {
    params.target = context.target;
  }

  switch (step.action) {
    case 'start':
      return runBridge('start', params);

    case 'new-page': {
      const output = await runBridge('new-page', params);
      const json = tryParseJson(output);
      if (json?.id) {
        context.target = json.id;
      }
      return output;
    }

    case 'target':
      context.target = params.id || params.target || null;
      return JSON.stringify({ ok: true, target: context.target }, null, 2);

    case 'open':
      return runBridge('open', params);

    case 'click':
      return runBridge('click', params);

    case 'click-text':
      return runBridge('click-text', params);

    case 'fill':
      return runBridge('fill', params);

    case 'type':
      return runBridge('type', params);

    case 'press':
      return runBridge('press', params);

    case 'list-buttons':
      return runBridge('list-buttons', params);

    case 'list-fields':
      return runBridge('list-fields', params);

    case 'info':
      return runBridge('info', params);

    case 'eval':
      return runBridge('eval', params);

    case 'set-files':
      return runBridge('set-files', params);

    case 'screenshot':
      return runBridge('screenshot', params);

    case 'wait': {
      const ms = Number(params.ms || params.time || 1000);
      await new Promise((resolve) => setTimeout(resolve, ms));
      return JSON.stringify({ ok: true, waitedMs: ms }, null, 2);
    }

    default:
      throw new Error(`Unknown flow action: ${step.action}`);
  }
}

function renderResult(step, output) {
  const header = `> ${step.action}`;
  return `${header}\n${output}\n`;
}

async function commandRun(args) {
  const filePath = parseStringArg(args, 'file', null);
  const inline = parseStringArg(args, 'steps', null);

  if (!filePath && !inline) {
    throw new Error('run requires file=<path> or steps="<lines>"');
  }

  const content = filePath
    ? fs.readFileSync(path.resolve(filePath), 'utf8')
    : inline;

  const result = await runFlowContent(content, {
    target: parseStringArg(args, 'target', null),
    source: filePath ? path.resolve(filePath) : 'inline',
  });

  process.stdout.write(result.output);
}

async function runFlowContent(content, options = {}) {
  const state = loadState();

  const lines = content.split(/\r?\n/);
  const steps = lines.map(parseStepLine).filter(Boolean);
  const context = {
    target: options.target || state.lastTarget || null,
  };
  const outputs = [];

  for (const step of steps) {
    const output = await executeStep(step, context);
    outputs.push(renderResult(step, output));
  }

  state.lastTarget = context.target || state.lastTarget || null;
  state.lastFlowSource = options.source || 'inline';
  state.lastFlowRunAt = new Date().toISOString();
  state.lastFlowPreview = lines.filter((line) => line.trim()).slice(0, 20).map(redactFlowLine);
  saveState(state);

  return {
    output: outputs.join('\n'),
    target: context.target,
  };
}

async function commandTemplate() {
  process.stdout.write(`start
new-page url=https://example.com
info
list-buttons
# click-text text=Learn more
# list-fields
# fill hint=email text=test@example.com
# press key=Enter
# screenshot out=C:\\Users\\Bogdan\\browser-bridge\\flow-shot.png
`);
}

async function commandHelp() {
  process.stdout.write(`browser-flow commands:
  run file=C:\\path\\flow.txt
  run steps="start\\nnew-page url=https://example.com\\ninfo"
  template
  help

Supported actions inside a flow:
  start
  new-page url=...
  target id=...
  open url=...
  click selector=...
  click-text text=...
  fill hint=... text=...
  type selector=... text=...
  press key=Enter
  list-buttons
  list-fields
  info
  eval js=...
  set-files selector=input[type=file] file=C:\\path\\img.png
  screenshot out=...
  wait ms=1500
`);
}

async function main() {
  const [, , command = 'help', ...args] = process.argv;
  if (command === 'run') {
    await commandRun(args);
    return;
  }
  if (command === 'template') {
    await commandTemplate();
    return;
  }
  await commandHelp();
}

module.exports = {
  parseStepLine,
  runFlowContent,
  redactFlowLine,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message || String(error));
    process.exitCode = 1;
  });
}
