#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { loadState } = require(path.join(__dirname, 'browser-bridge.js'));
const { runFlowContent } = require(path.join(__dirname, 'browser-flow.js'));

function parseStringArg(args, name, fallback = null) {
  const prefix = `${name}=`;
  const token = args.find((item) => item.startsWith(prefix));
  return token ? token.slice(prefix.length) : fallback;
}

function quoteValue(value) {
  const normalized = String(value).replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/"/g, '\\"');
  return `"${normalized}"`;
}

function normalizePrompt(text) {
  return text.replace(/\r/g, '\n').trim();
}

function splitPrompt(text) {
  return normalizePrompt(text)
    .split(/\n|;|,(?=(?:[^"]*"[^"]*")*[^"]*$)|\bthen\b|\band then\b|\bпотом\b|\bзатем\b/iu)
    .map((part) => part.trim())
    .filter(Boolean);
}

function detectUrl(text) {
  const direct = text.match(/https?:\/\/\S+/i);
  if (direct) {
    return direct[0];
  }

  const lower = text.toLowerCase();
  if (lower.includes('kwork') && lower.includes('seller')) {
    return 'https://kwork.ru/seller';
  }
  if (lower.includes('kwork')) {
    return 'https://kwork.ru/';
  }
  if (lower.includes('example.com') || lower.includes('example domain')) {
    return 'https://example.com/';
  }
  if (lower.includes('httpbin form') || lower.includes('test form')) {
    return 'https://httpbin.org/forms/post';
  }

  return null;
}

function parseClickText(part) {
  const match = part.match(/(?:click|press|tap|нажми|кликни|нажать)\s+(?:on\s+)?["“]?([^"”]+?)["”]?$/iu);
  return match ? match[1].trim() : null;
}

function parseFill(part) {
  const lower = part.toLowerCase();
  if (!/(fill|type|enter|set|введи|заполни)/iu.test(lower)) {
    return null;
  }

  const eqMatch = part.match(/(?:fill|type|enter|set|введи|заполни)\s+["“]?([^"”=]+?)["”]?\s*=\s*["“]?(.+?)["”]?$/iu);
  if (eqMatch) {
    return { hint: eqMatch[1].trim(), text: eqMatch[2].trim() };
  }

  const withMatch = part.match(/(?:fill|type|enter|set|введи|заполни)\s+["“]?([^"”]+?)["”]?\s+(?:with|as|значение)\s+["“]?(.+?)["”]?$/iu);
  if (withMatch) {
    return { hint: withMatch[1].trim(), text: withMatch[2].trim() };
  }

  return null;
}

function parsePress(part) {
  const match = part.match(/(?:press|key|нажми клавишу|клавиша)\s+([A-Za-z0-9]+)/iu);
  return match ? match[1] : null;
}

function buildFlowFromPrompt(prompt, options = {}) {
  const state = loadState();
  const parts = splitPrompt(prompt);
  const steps = [];
  let hasNavigation = false;
  let startInserted = false;

  for (const part of parts) {
    const lower = part.toLowerCase();

    if (!startInserted && (/(start|launch|open browser|запусти браузер|открой браузер)/iu.test(lower) || (!state.port && detectUrl(part)))) {
      steps.push('start');
      startInserted = true;
    }

    const url = detectUrl(part);
    if (url) {
      steps.push(`new-page url=${quoteValue(url)}`);
      hasNavigation = true;
      continue;
    }

    if (/(list buttons|show buttons|кнопки|покажи кнопки)/iu.test(lower)) {
      steps.push('list-buttons');
      continue;
    }

    if (/(list fields|show fields|поля|покажи поля|формы|show form)/iu.test(lower)) {
      steps.push('list-fields');
      continue;
    }

    if (/(screenshot|screen shot|скрин|снимок)/iu.test(lower)) {
      steps.push('screenshot');
      continue;
    }

    if (/(info|status|what is on the page|что на странице|инфо)/iu.test(lower)) {
      steps.push('info');
      continue;
    }

    const fill = parseFill(part);
    if (fill) {
      steps.push(`fill hint=${quoteValue(fill.hint)} text=${quoteValue(fill.text)}`);
      continue;
    }

    const key = parsePress(part);
    if (key) {
      steps.push(`press key=${key}`);
      continue;
    }

    const clickText = parseClickText(part);
    if (clickText) {
      steps.push(`click-text text=${quoteValue(clickText)}`);
      continue;
    }

    if (/(wait|подожди|жди)/iu.test(lower)) {
      const msMatch = part.match(/(\d{2,5})/);
      const ms = msMatch ? Number(msMatch[1]) : 1500;
      steps.push(`wait ms=${ms}`);
      continue;
    }

    steps.push(`# unparsed: ${part}`);
  }

  if (!steps.length && options.ensureInfo !== false) {
    steps.push('info');
  }

  if (!hasNavigation && !state.lastTarget && options.ensureInfo !== false) {
    if (!startInserted) {
      steps.unshift('start');
    }
    steps.push('info');
  }

  return steps.join('\n');
}

async function commandCompile(args) {
  const prompt = parseStringArg(args, 'prompt', null);
  if (!prompt) {
    throw new Error('compile requires prompt=<text>');
  }
  process.stdout.write(buildFlowFromPrompt(prompt) + '\n');
}

async function commandRun(args) {
  const prompt = parseStringArg(args, 'prompt', null);
  if (!prompt) {
    throw new Error('run requires prompt=<text>');
  }

  const flow = buildFlowFromPrompt(prompt);
  const result = await runFlowContent(flow, {
    source: 'browser-prompt',
  });

  process.stdout.write(`Compiled flow:\n${flow}\n\n`);
  process.stdout.write(result.output);
}

async function commandHelp() {
  process.stdout.write(`browser-prompt commands:
  compile prompt="open kwork seller, list buttons"
  run prompt="open kwork seller, click Login, fill email=test@example.com, screenshot"
  help

Prompt patterns supported:
  open https://example.com
  open kwork seller
  click "Login"
  fill email=test@example.com
  fill "Customer name"=Bogdan
  press Enter
  list buttons
  list fields
  screenshot
  info
`);
}

async function main() {
  const [, , command = 'help', ...args] = process.argv;
  if (command === 'compile') {
    await commandCompile(args);
    return;
  }
  if (command === 'run') {
    await commandRun(args);
    return;
  }
  await commandHelp();
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exitCode = 1;
});
