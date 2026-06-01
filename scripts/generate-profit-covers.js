#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'covers-profit');
const TMP = path.join(OUT, '_html');
const W = 825;
const H = 550;

const covers = [
  {
    file: '51213284-openai-api.png',
    kicker: 'AI INTEGRATION',
    title: 'OpenAI GPT',
    subtitle: 'API для сайта, бота и CRM',
    bg: '#101828',
    accent: '#2CE59B',
    second: '#5B8CFF',
  },
  {
    file: '40740429-telegram-ai-bot.png',
    kicker: 'TELEGRAM BOT',
    title: 'AI бот',
    subtitle: 'Заявки, FAQ, продажи',
    bg: '#0B2742',
    accent: '#27B6F6',
    second: '#7EF0C1',
  },
  {
    file: '45979524-python-parser.png',
    kicker: 'PYTHON AUTOMATION',
    title: 'Парсер',
    subtitle: 'Данные, файлы, отчеты',
    bg: '#152238',
    accent: '#FFD166',
    second: '#4DCCBD',
  },
  {
    file: '46004001-api-webhook.png',
    kicker: 'API / WEBHOOK',
    title: 'Интеграции',
    subtitle: 'CRM, Telegram, Sheets',
    bg: '#132A2E',
    accent: '#6EE7B7',
    second: '#F59E0B',
  },
  {
    file: '45587052-code-fix.png',
    kicker: 'CODE RESCUE',
    title: 'Исправлю код',
    subtitle: 'Боты, скрипты, парсеры',
    bg: '#2A1D31',
    accent: '#F472B6',
    second: '#A78BFA',
  },
  {
    file: '27194497-web-tool.png',
    kicker: 'WEB TOOL',
    title: 'Веб-инструмент',
    subtitle: 'Кабинет, форма, панель',
    bg: '#1D2633',
    accent: '#38BDF8',
    second: '#F97316',
  },
  {
    file: '51213619-sheets-telegram.png',
    kicker: 'GOOGLE SHEETS',
    title: 'Sheets + Telegram',
    subtitle: 'Отчеты и уведомления',
    bg: '#123524',
    accent: '#34D399',
    second: '#FBBF24',
  },
  {
    file: '51213975-excel-csv.png',
    kicker: 'DATA CLEANUP',
    title: 'Excel / CSV',
    subtitle: 'Обработка таблиц и баз',
    bg: '#1E293B',
    accent: '#22C55E',
    second: '#60A5FA',
  },
  {
    file: '51214672-browser-automation.png',
    kicker: 'BROWSER TASKS',
    title: 'Автоматизация',
    subtitle: 'Сайты и кабинеты',
    bg: '#241E46',
    accent: '#C084FC',
    second: '#FB7185',
  },
];

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function html(spec) {
  return `<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  html, body { width: ${W}px; height: ${H}px; margin: 0; overflow: hidden; background: #0B1020; }
  body {
    font-family: Inter, Arial, Helvetica, sans-serif;
    color: #fff;
    background:
      radial-gradient(circle at 78% 24%, ${spec.second}66 0, transparent 160px),
      radial-gradient(circle at 18% 86%, ${spec.accent}55 0, transparent 190px),
      linear-gradient(135deg, ${spec.bg}, #0B1020 78%);
  }
  .wrap {
    position: relative;
    width: ${W}px;
    height: ${H}px;
    padding: 42px 46px;
  }
  .grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255,255,255,.055) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.055) 1px, transparent 1px);
    background-size: 44px 44px;
    mask-image: linear-gradient(90deg, #000 0, transparent 78%);
  }
  .panel {
    position: absolute;
    right: 42px;
    top: 54px;
    width: 180px;
    height: 270px;
    border: 1px solid rgba(255,255,255,.18);
    background: rgba(255,255,255,.08);
    border-radius: 22px;
    box-shadow: 0 28px 80px rgba(0,0,0,.28);
  }
  .panel::before, .panel::after {
    content: "";
    position: absolute;
    left: 24px;
    right: 24px;
    height: 14px;
    border-radius: 99px;
    background: ${spec.accent};
  }
  .panel::before { top: 46px; width: 118px; }
  .panel::after { top: 88px; width: 86px; background: ${spec.second}; }
  .node {
    position: absolute;
    right: 90px;
    bottom: 66px;
    width: 124px;
    height: 124px;
    border-radius: 50%;
    background: linear-gradient(135deg, ${spec.accent}, ${spec.second});
    box-shadow: 0 24px 70px ${spec.accent}44;
  }
  .node::after {
    content: "";
    position: absolute;
    inset: 32px;
    border-radius: 50%;
    background: rgba(11,16,32,.42);
    border: 1px solid rgba(255,255,255,.22);
  }
  .kicker {
    position: relative;
    display: inline-block;
    padding: 9px 13px;
    border: 1px solid rgba(255,255,255,.2);
    border-radius: 999px;
    background: rgba(255,255,255,.08);
    color: ${spec.accent};
    font-weight: 800;
    font-size: 15px;
    letter-spacing: .08em;
  }
  h1 {
    position: relative;
    width: 390px;
    margin: 48px 0 0;
    font-size: 58px;
    line-height: .95;
    letter-spacing: 0;
    font-weight: 900;
  }
  .sub {
    position: relative;
    width: 380px;
    margin-top: 24px;
    font-size: 27px;
    line-height: 1.18;
    font-weight: 750;
    color: rgba(255,255,255,.9);
  }
  .bar {
    position: absolute;
    left: 46px;
    right: 46px;
    bottom: 38px;
    height: 12px;
    border-radius: 99px;
    background: linear-gradient(90deg, ${spec.accent}, ${spec.second}, rgba(255,255,255,.3));
  }
</style>
</head>
<body>
  <div class="wrap">
    <div class="grid"></div>
    <div class="panel"></div>
    <div class="node"></div>
    <div class="kicker">${escapeHtml(spec.kicker)}</div>
    <h1>${escapeHtml(spec.title)}</h1>
    <div class="sub">${escapeHtml(spec.subtitle)}</div>
    <div class="bar"></div>
  </div>
</body>
</html>`;
}

function findChrome() {
  const candidates = [
    process.env.BROWSER_BRIDGE_CHROME,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error('Chrome/Chromium executable not found');
}

fs.mkdirSync(TMP, { recursive: true });
const chrome = findChrome();

for (const spec of covers) {
  const htmlPath = path.join(TMP, spec.file.replace(/\.png$/, '.html'));
  const pngPath = path.join(OUT, spec.file);
  fs.writeFileSync(htmlPath, html(spec), 'utf8');
  const result = spawnSync(chrome, [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
    `--window-size=${W},${H}`,
    `--screenshot=${pngPath}`,
    `file://${htmlPath}`,
  ], { encoding: 'utf8' });

  if (result.status !== 0) {
    throw new Error(`Failed to render ${spec.file}: ${result.stderr || result.stdout}`);
  }
}

console.log(JSON.stringify({
  ok: true,
  out: OUT,
  files: covers.map((cover) => cover.file),
}, null, 2));
