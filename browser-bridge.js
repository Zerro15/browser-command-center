#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn, spawnSync } = require('node:child_process');

const ROOT = __dirname;
const STATE_PATH = path.join(ROOT, 'state.json');
const TELEGRAM_SEND_STATE_PATH = path.join(ROOT, '.telegram-send-state.json');
const DEFAULT_PORT = 9222;
const DEFAULT_KEEP_TAB_PATTERNS = ['mail.google.com', 'web.telegram.org'];
const DEFAULT_CLOSE_TAB_PATTERNS = ['chrome://newtab/', 'kadrof.ru', 'yonote.ru'];
const DEFAULT_CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const LINUX_CHROME_CANDIDATES = [
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/snap/bin/chromium',
  '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
  '/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe',
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function loadState() {
  if (!fs.existsSync(STATE_PATH)) {
    return {};
  }

  try {
    return JSON.parse(fs.readFileSync(STATE_PATH, 'utf8'));
  } catch {
    return {};
  }
}

function saveState(state) {
  fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2), 'utf8');
}

function loadJsonFile(filePath, fallback = {}) {
  if (!fs.existsSync(filePath)) {
    return fallback;
  }

  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function saveJsonFile(filePath, value) {
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), 'utf8');
}

function makeTelegramSendKey(peer, text) {
  return `${peer || 'unknown'}\n${text}`;
}

function parseListArg(args, name, fallback = []) {
  const value = parseStringArg(args, name, null);
  if (value === null) {
    return fallback;
  }
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function matchesAnyPattern(value, patterns) {
  const haystack = (value || '').toLowerCase();
  return patterns.some((pattern) => haystack.includes(pattern.toLowerCase()));
}

function getChromePath() {
  const candidates = [
    process.env.BROWSER_BRIDGE_CHROME,
    ...(process.platform === 'win32'
      ? [
          DEFAULT_CHROME_PATH,
          'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
          'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
        ]
      : LINUX_CHROME_CANDIDATES),
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  throw new Error('Chrome/Chromium executable not found. Set BROWSER_BRIDGE_CHROME or install google-chrome-stable/chromium.');
}

function isWindowsExecutable(executablePath) {
  return /\.exe$/i.test(executablePath) || /^[A-Za-z]:\\/.test(executablePath);
}

function toBrowserPath(localPath, executablePath) {
  if (!isWindowsExecutable(executablePath)) {
    return localPath;
  }

  const result = spawnSync('wslpath', ['-w', localPath], { encoding: 'utf8' });
  if (result.status !== 0 || !result.stdout.trim()) {
    throw new Error(`Unable to convert WSL path for Windows browser: ${localPath}`);
  }
  return result.stdout.trim();
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

async function fetchJsonWithMethod(url, method) {
  const response = await fetch(url, { method });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.text();
}

async function waitForDebugger(port, timeoutMs = 15000) {
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    try {
      const version = await fetchJson(`http://127.0.0.1:${port}/json/version`);
      return version;
    } catch {
      await sleep(250);
    }
  }

  throw new Error(`Chrome remote debugging did not start on port ${port}`);
}

function parseJsonArg(args, name, fallback = null) {
  const prefix = `${name}=`;
  const token = args.find((item) => item.startsWith(prefix));
  if (!token) {
    return fallback;
  }
  return JSON.parse(token.slice(prefix.length));
}

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

function parseNumberArg(args, name, fallback) {
  const value = parseStringArg(args, name, null);
  if (value === null) {
    return fallback;
  }
  return Number(value);
}

class CdpClient {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.events = [];
  }

  async connect() {
    this.ws = new WebSocket(this.webSocketUrl);

    await new Promise((resolve, reject) => {
      const onOpen = () => {
        cleanup();
        resolve();
      };

      const onError = (error) => {
        cleanup();
        reject(error);
      };

      const cleanup = () => {
        this.ws.removeEventListener('open', onOpen);
        this.ws.removeEventListener('error', onError);
      };

      this.ws.addEventListener('open', onOpen);
      this.ws.addEventListener('error', onError);
    });

    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (typeof message.id === 'number') {
        const pending = this.pending.get(message.id);
        if (!pending) {
          return;
        }
        this.pending.delete(message.id);
        if (message.error) {
          pending.reject(new Error(message.error.message || 'CDP error'));
        } else {
          pending.resolve(message.result || {});
        }
        return;
      }

      this.events.push(message);
    });

    this.ws.addEventListener('close', () => {
      for (const pending of this.pending.values()) {
        pending.reject(new Error('WebSocket closed'));
      }
      this.pending.clear();
    });
  }

  async send(method, params = {}) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
    });
  }

  async close() {
    if (!this.ws) {
      return;
    }
    this.ws.close();
    await sleep(50);
  }
}

async function getTargets(port) {
  return fetchJson(`http://127.0.0.1:${port}/json/list`);
}

async function closeTarget(port, targetId) {
  return fetchText(`http://127.0.0.1:${port}/json/close/${encodeURIComponent(targetId)}`);
}

async function getTarget(port, targetId) {
  const targets = await getTargets(port);
  if (targetId) {
    const match = targets.find((item) => item.id === targetId);
    if (!match) {
      throw new Error(`Target not found: ${targetId}`);
    }
    return match;
  }

  const page = targets.find((item) => item.type === 'page');
  if (!page) {
    throw new Error('No page target found');
  }
  return page;
}

async function withClient(port, targetId, action) {
  const target = await getTarget(port, targetId);
  const client = new CdpClient(target.webSocketDebuggerUrl);
  await client.connect();

  try {
    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('DOM.enable');
    return await action(client, target);
  } finally {
    await client.close();
  }
}

async function getRootNode(client) {
  const { root } = await client.send('DOM.getDocument', { depth: -1, pierce: true });
  return root.nodeId;
}

async function querySelector(client, selector) {
  const rootNodeId = await getRootNode(client);
  const { nodeId } = await client.send('DOM.querySelector', { nodeId: rootNodeId, selector });
  if (!nodeId) {
    throw new Error(`Selector not found: ${selector}`);
  }
  return nodeId;
}

async function clickSelector(client, selector) {
  const nodeId = await querySelector(client, selector);
  const { model } = await client.send('DOM.getBoxModel', { nodeId });
  const quad = model.content;
  const x = (quad[0] + quad[2] + quad[4] + quad[6]) / 4;
  const y = (quad[1] + quad[3] + quad[5] + quad[7]) / 4;

  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'left', buttons: 1 });
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 });
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', buttons: 1, clickCount: 1 });
}

async function focusSelector(client, selector) {
  const expression = `
    (() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return { ok: false, error: 'Selector not found' };
      el.focus();
      return { ok: true };
    })()
  `;
  const { result } = await client.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (!result.value || !result.value.ok) {
    throw new Error(result.value?.error || `Unable to focus selector: ${selector}`);
  }
}

async function typeText(client, text) {
  await client.send('Input.insertText', { text });
}

async function mouseClickAt(client, x, y) {
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'left', buttons: 0 });
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 });
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1 });
}

async function pressKey(client, key) {
  const keyMap = {
    Enter: { code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 },
    Escape: { code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 },
    Backspace: { code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 },
    Tab: { code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 },
  };
  const extra = keyMap[key] || {};
  await client.send('Input.dispatchKeyEvent', { type: 'keyDown', key, ...extra });
  await client.send('Input.dispatchKeyEvent', { type: 'keyUp', key, ...extra });
}

async function evaluate(client, expression) {
  const { result } = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });

  return result.value;
}

function visibleElementProbeScript(selector) {
  return `
    (() => {
      const nodes = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const match = nodes.find(visible) || nodes[0] || null;
      if (!match) return null;
      const rect = match.getBoundingClientRect();
      return {
        ok: true,
        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
      };
    })()
  `;
}

async function setNativeValue(client, selector, value, clear = true) {
  const expression = `
    (() => {
      const selector = ${JSON.stringify(selector)};
      const value = ${JSON.stringify(value)};
      const clear = ${clear ? 'true' : 'false'};
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const el = Array.from(document.querySelectorAll(selector)).find(visible) || document.querySelector(selector);
      if (!el) return { ok: false, error: 'Selector not found' };

      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.focus();

      const fire = (target, event) => target.dispatchEvent(event);
      if (el.isContentEditable) {
        if (clear) {
          const range = document.createRange();
          range.selectNodeContents(el);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          document.execCommand('delete');
        }
        fire(el, new InputEvent('beforeinput', {
          bubbles: true,
          cancelable: true,
          inputType: 'insertText',
          data: value,
        }));
        document.execCommand('insertText', false, value);
        fire(el, new InputEvent('input', {
          bubbles: true,
          inputType: 'insertText',
          data: value,
        }));
      } else if ('value' in el) {
        const proto = Object.getPrototypeOf(el);
        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
        if (descriptor && descriptor.set) {
          descriptor.set.call(el, clear ? value : el.value + value);
        } else {
          el.value = clear ? value : el.value + value;
        }
        fire(el, new InputEvent('input', {
          bubbles: true,
          inputType: 'insertText',
          data: value,
        }));
      } else {
        return { ok: false, error: 'Element is not editable' };
      }

      fire(el, new Event('change', { bubbles: true }));
      const rect = el.getBoundingClientRect();
      return {
        ok: true,
        selector,
        text: (el.innerText || el.value || '').slice(0, 500),
        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
      };
    })()
  `;

  const result = await evaluate(client, expression);
  if (!result || !result.ok) {
    throw new Error(result?.error || `Unable to set value for selector: ${selector}`);
  }
  return result;
}

async function clearNativeValue(client, selector) {
  const result = await evaluate(client, `
    (() => {
      const selector = ${JSON.stringify(selector)};
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const el = Array.from(document.querySelectorAll(selector)).find(visible) || document.querySelector(selector);
      if (!el) return { ok: false, error: 'Selector not found' };

      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.focus();

      const fire = (target, event) => target.dispatchEvent(event);
      if (el.isContentEditable) {
        const range = document.createRange();
        range.selectNodeContents(el);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand('delete');
        fire(el, new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward' }));
      } else if ('value' in el) {
        const proto = Object.getPrototypeOf(el);
        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
        if (descriptor && descriptor.set) {
          descriptor.set.call(el, '');
        } else {
          el.value = '';
        }
        fire(el, new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward' }));
      } else {
        return { ok: false, error: 'Element is not editable' };
      }

      fire(el, new Event('change', { bubbles: true }));
      return { ok: true, selector };
    })()
  `);

  if (!result || !result.ok) {
    throw new Error(result?.error || `Unable to clear value for selector: ${selector}`);
  }
  return result;
}

async function setFileInput(client, selector, files) {
  const probe = await evaluate(client, visibleElementProbeScript(selector));
  if (!probe || !probe.ok) {
    throw new Error(`Visible file input not found for selector: ${selector}`);
  }
  const nodeId = await querySelector(client, selector);
  await client.send('DOM.setFileInputFiles', { nodeId, files });
  await evaluate(client, `
    (() => {
      const visible = (node) => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const el = Array.from(document.querySelectorAll(${JSON.stringify(selector)})).find(visible) || document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, composed: true }));
      el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true, composed: true }));
      return true;
    })()
  `);
}

async function findTelegramSendButton(client) {
  return evaluate(client, `
    (() => {
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const buttons = Array.from(document.querySelectorAll('button.btn-send, button[class*="btn-send"], .btn-send-container button'))
        .filter(visible)
        .map((el) => {
          const rect = el.getBoundingClientRect();
          return {
            cls: el.className || '',
            text: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim(),
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          };
        });
      return buttons[0] ? { ok: true, ...buttons[0] } : { ok: false, error: 'Telegram send button not found' };
    })()
  `);
}

async function clickTelegramSendButton(client) {
  const button = await findTelegramSendButton(client);
  if (!button || !button.ok) {
    throw new Error(button?.error || 'Telegram send button not found');
  }
  await mouseClickAt(client, button.x, button.y);
  return button;
}

async function prepareTelegramDocumentAttach(client) {
  await evaluate(client, `
    (() => {
      const input = document.querySelector('input[type="file"]');
      if (input) {
        try {
          input.value = '';
        } catch {}
      }
      const attach = document.querySelector('attach-menu-button.attach-file');
      if (!attach) return { ok: false, error: 'Telegram attach button not found' };
      attach.click();
      return { ok: true };
    })()
  `);
  await sleep(250);

  const documentItem = await evaluate(client, `
    (() => {
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const textOf = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
      const candidates = Array.from(document.querySelectorAll('.btn-menu-item, button, span, div'))
        .filter(visible);
      const match = candidates.find((el) => textOf(el) === 'Document');
      if (!match) return { ok: false, error: 'Telegram Document menu item not found' };
      const rect = match.getBoundingClientRect();
      return { ok: true, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    })()
  `);
  if (!documentItem || !documentItem.ok) {
    throw new Error(documentItem?.error || 'Telegram Document menu item not found');
  }
  await mouseClickAt(client, documentItem.x, documentItem.y);
  await sleep(250);
  return { ok: true };
}

async function findTelegramSendFileButton(client) {
  return evaluate(client, `
    (() => {
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const textOf = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
      const match = Array.from(document.querySelectorAll('button, [role="button"], span, div'))
        .filter(visible)
        .find((el) => textOf(el) === 'SEND');
      if (!match) return { ok: false, error: 'Telegram SEND button not found in file preview' };
      const rect = match.getBoundingClientRect();
      return { ok: true, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    })()
  `);
}

async function getTelegramChatSnapshot(client, limit = 20) {
  return evaluate(client, `
    (() => {
      const normalize = (value) => (value || '').replace(/[\\uE000-\\uF8FF]/g, '').replace(/\\s+/g, ' ').trim();
      const cleanMessage = (value) => normalize(value).replace(/\\s*\\d{1,2}:\\d{2}\\s*$/, '').trim();
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0';
      };
      const activePeer = normalize(
        Array.from(document.querySelectorAll('.chat-info .peer-title, .chat .peer-title, .topbar .peer-title'))
          .filter(visible)
          .map((el) => el.innerText || el.textContent || '')
          .find(Boolean)
      );
      const composer = Array.from(document.querySelectorAll('.input-message-input[contenteditable="true"]')).find(visible) || document.querySelector('.input-message-input[contenteditable="true"]');
      const messages = Array.from(document.querySelectorAll('.bubble.is-in, .bubble.is-out'))
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          const textNode = el.querySelector('.translatable-message, .message');
          const text = cleanMessage(textNode ? textNode.innerText || textNode.textContent || '' : el.innerText || el.textContent || '');
          if (!text || rect.width <= 0 || rect.height <= 0 || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return null;
          const isOutgoing = /\\bis-out\\b/i.test(el.className || '');
          const time = normalize(el.querySelector('.time, .message-time, [class*="time"]')?.innerText || '');
          return { direction: isOutgoing ? 'out' : 'in', time, text: text.slice(0, 4000) };
        })
        .filter(Boolean)
        .slice(-${Number(limit) || 20});
      const controls = Array.from(document.querySelectorAll('button, .chat-input-control-button, [role="button"]'))
        .map((button) => {
          const rect = button.getBoundingClientRect();
          const text = normalize(button.innerText || button.textContent || '');
          const style = getComputedStyle(button);
          if (!text || rect.width <= 0 || rect.height <= 0 || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return null;
          if (!/START|Unblock|JOIN|Open Chat|Only Premium|Frozen|Send Message|Message/i.test(text)) return null;
          return { text, visible: true };
        })
        .filter(Boolean);
      const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'))
        .filter((input) => input.files && input.files.length)
        .map((input) => Array.from(input.files).map((file) => ({
          name: file.name,
          size: file.size,
          type: file.type || '',
        })))
        .flat();
      return {
        url: location.href,
        activePeer,
        composerText: composer ? composer.innerText : '',
        controls,
        messages,
        fileInputs,
        bodyTail: document.body ? document.body.innerText.slice(-2000) : ''
      };
    })()
  `);
}

async function getTelegramInboxSnapshot(client, limit = 20) {
  return evaluate(client, `
    (() => {
      const normalize = (value) => (value || '').replace(/[\\uE000-\\uF8FF]/g, '').replace(/\\s+/g, ' ').trim();
      const seen = new Set();
      return Array.from(document.querySelectorAll('a.chatlist-chat, a.row.row-clickable[href^="#"], a.row.row-clickable[href*="/k/#"]'))
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          if (rect.width <= 0 || rect.height <= 0 || style.display === 'none' || style.visibility === 'hidden') return null;
          if (rect.bottom < 0 || rect.top > window.innerHeight) return null;
          if (rect.width < 200) return null;
          const text = normalize(el.innerText || el.textContent || '');
          if (!text) return null;
          const title = normalize(el.querySelector('.peer-title, .user-title, .row-title')?.innerText || '');
          const subtitle = normalize(el.querySelector('.row-subtitle, .dialog-subtitle')?.innerText || '');
          const time = normalize(el.querySelector('.message-time, .row-title-right')?.innerText || '');
          const key = el.href || title || text;
          if (seen.has(key)) return null;
          seen.add(key);
          return {
            title,
            subtitle,
            time,
            text: text.slice(0, 800),
            href: el.href || '',
            rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) }
          };
        })
        .filter(Boolean)
        .slice(0, ${Number(limit) || 20});
    })()
  `);
}

async function clickByText(client, text, exact = false, tag = '') {
  const expression = `
    (() => {
      const wanted = ${JSON.stringify(text)}.trim();
      const exact = ${exact ? 'true' : 'false'};
      const tag = ${JSON.stringify(tag)}.trim().toLowerCase();
      const baseSelector = 'a,button,[role="button"],input[type="button"],input[type="submit"],summary,span,div';
      const nodes = Array.from(document.querySelectorAll(tag ? tag : baseSelector));
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      };
      const clickable = (el) => {
        if (['a', 'button', 'summary'].includes(el.tagName.toLowerCase())) return true;
        if (el.getAttribute('role') === 'button') return true;
        if (el.onclick) return true;
        if ((el.className || '').toString().includes('login-js')) return true;
        const style = getComputedStyle(el);
        return style.cursor === 'pointer';
      };
      const textOf = (el) => (el.innerText || el.value || el.getAttribute('aria-label') || el.textContent || '').replace(/\\s+/g, ' ').trim();
      const match = nodes.find((el) => {
        if (!visible(el) || !clickable(el)) return false;
        const value = textOf(el);
        return exact ? value === wanted : value.toLowerCase().includes(wanted.toLowerCase());
      });
      if (!match) return { ok: false, error: 'Element not found' };
      match.scrollIntoView({ block: 'center', inline: 'center' });
      const rect = match.getBoundingClientRect();
      return {
        ok: true,
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
        text: textOf(match),
        tag: match.tagName.toLowerCase()
      };
    })()
  `;
  const result = await evaluate(client, expression);
  if (!result || !result.ok) {
    throw new Error(result?.error || `Visible element not found for text: ${text}`);
  }

  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: result.x, y: result.y, button: 'left', buttons: 1 });
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: result.x, y: result.y, button: 'left', buttons: 1, clickCount: 1 });
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: result.x, y: result.y, button: 'left', buttons: 1, clickCount: 1 });
  return result;
}

async function listClickableElements(client, limit = 20) {
  return evaluate(client, `
    (() => {
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      };
      const clickable = (el) => {
        if (['a', 'button', 'summary'].includes(el.tagName.toLowerCase())) return true;
        if (el.getAttribute('role') === 'button') return true;
        if (el.onclick) return true;
        if ((el.className || '').toString().includes('login-js')) return true;
        const style = getComputedStyle(el);
        return style.cursor === 'pointer';
      };
      const textOf = (el) => (el.innerText || el.value || el.getAttribute('aria-label') || el.textContent || '').replace(/\\s+/g, ' ').trim();
      return Array.from(document.querySelectorAll('a,button,[role="button"],input[type="button"],input[type="submit"],summary,span,div'))
        .filter((el) => visible(el) && clickable(el))
        .map((el, index) => ({
          index,
          tag: el.tagName.toLowerCase(),
          text: textOf(el).slice(0, 120),
          id: el.id || '',
          name: el.getAttribute('name') || '',
          classes: Array.from(el.classList || []).slice(0, 6).join('.'),
          href: el.getAttribute('href') || ''
        }))
        .filter((item) => item.text || item.id || item.name)
        .slice(0, ${Math.max(1, limit)});
    })()
  `);
}

async function listFields(client, limit = 20) {
  return evaluate(client, `
    (() => {
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      };
      const getLabel = (el) => {
        if (el.labels && el.labels.length) {
          return Array.from(el.labels).map((x) => x.innerText.trim()).join(' ');
        }
        const id = el.id;
        if (id) {
          const label = document.querySelector('label[for="' + CSS.escape(id) + '"]');
          if (label) return label.innerText.trim();
        }
        return '';
      };
      return Array.from(document.querySelectorAll('input,textarea,select,[contenteditable="true"]'))
        .filter(visible)
        .map((el, index) => ({
          index,
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || '',
          name: el.getAttribute('name') || '',
          id: el.id || '',
          placeholder: el.getAttribute('placeholder') || '',
          label: getLabel(el),
          ariaLabel: el.getAttribute('aria-label') || ''
        }))
        .slice(0, ${Math.max(1, limit)});
    })()
  `);
}

async function fillFieldByHint(client, hint, value, clear = true) {
  const expression = `
    (() => {
      const wanted = ${JSON.stringify(hint)}.trim().toLowerCase();
      const clear = ${clear ? 'true' : 'false'};
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      };
      const getLabel = (el) => {
        if (el.labels && el.labels.length) {
          return Array.from(el.labels).map((x) => x.innerText.trim()).join(' ');
        }
        const id = el.id;
        if (id) {
          const label = document.querySelector('label[for="' + CSS.escape(id) + '"]');
          if (label) return label.innerText.trim();
        }
        return '';
      };
      const candidates = Array.from(document.querySelectorAll('input,textarea,select,[contenteditable="true"]')).filter(visible);
      const score = (el) => {
        const parts = [
          el.getAttribute('name') || '',
          el.id || '',
          el.getAttribute('placeholder') || '',
          el.getAttribute('aria-label') || '',
          getLabel(el) || ''
        ].map((x) => x.toLowerCase());
        let best = 0;
        for (const part of parts) {
          if (!part) continue;
          if (part === wanted) best = Math.max(best, 100);
          else if (part.includes(wanted)) best = Math.max(best, 50);
        }
        return best;
      };
      const sorted = candidates
        .map((el) => ({ el, score: score(el) }))
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score);
      if (!sorted.length) return { ok: false, error: 'Field not found' };
      const match = sorted[0].el;
      match.scrollIntoView({ block: 'center', inline: 'center' });
      match.focus();
      if (clear) {
        if ('value' in match) match.value = '';
        if (match.isContentEditable) match.innerText = '';
      }
      return {
        ok: true,
        tag: match.tagName.toLowerCase(),
        name: match.getAttribute('name') || '',
        id: match.id || '',
        placeholder: match.getAttribute('placeholder') || '',
        label: getLabel(match) || ''
      };
    })()
  `;

  const result = await evaluate(client, expression);
  if (!result || !result.ok) {
    throw new Error(result?.error || `Field not found for hint: ${hint}`);
  }
  await typeText(client, value);
  return result;
}

async function commandStart(args) {
  const port = Number(parseStringArg(args, 'port', String(DEFAULT_PORT)));
  const userDataDir = parseStringArg(args, 'profile', path.join(ROOT, 'chrome-profile'));
  const chromePath = getChromePath();
  const browserUserDataDir = toBrowserPath(userDataDir, chromePath);

  ensureDir(userDataDir);

  const chromeArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${browserUserDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--new-window',
    'about:blank',
  ];

  const child = spawn(chromePath, chromeArgs, {
    detached: true,
    stdio: 'ignore',
  });
  child.unref();

  const version = await waitForDebugger(port);
  const state = loadState();
  state.port = port;
  state.chromePath = chromePath;
  state.userDataDir = userDataDir;
  state.browserUserDataDir = browserUserDataDir;
  state.browser = version.Browser;
  saveState(state);

  console.log(JSON.stringify({
    ok: true,
    port,
    browser: version.Browser,
    userDataDir,
  }, null, 2));
}

function getPort(args) {
  const argPort = parseStringArg(args, 'port', null);
  if (argPort) {
    return Number(argPort);
  }
  const state = loadState();
  return Number(state.port || DEFAULT_PORT);
}

async function commandList(args) {
  const port = getPort(args);
  const targets = await getTargets(port);
  console.log(JSON.stringify(targets.map((item) => ({
    id: item.id,
    type: item.type,
    title: item.title,
    url: item.url,
  })), null, 2));
}

async function commandNewPage(args) {
  const port = getPort(args);
  const url = parseStringArg(args, 'url', 'about:blank');
  const created = await fetchJsonWithMethod(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, 'PUT');
  const state = loadState();
  state.tabOpenedAt = state.tabOpenedAt || {};
  state.tabOpenedAt[created.id] = new Date().toISOString();
  saveState(state);
  console.log(JSON.stringify({
    id: created.id,
    title: created.title,
    url: created.url,
  }, null, 2));
}

async function commandClosePage(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  if (!targetId) {
    throw new Error('close-page requires target=<id>');
  }

  const targets = await getTargets(port);
  const target = targets.find((item) => item.id === targetId);
  if (!target) {
    throw new Error(`Target not found: ${targetId}`);
  }
  if (target.type !== 'page') {
    throw new Error(`Refusing to close non-page target: ${target.type}`);
  }

  const message = await closeTarget(port, targetId);
  const state = loadState();
  if (state.tabOpenedAt) {
    delete state.tabOpenedAt[targetId];
    saveState(state);
  }
  console.log(JSON.stringify({ ok: true, closed: { id: target.id, title: target.title, url: target.url }, message }, null, 2));
}

async function commandCleanTabs(args) {
  const port = getPort(args);
  const dry = parseBooleanArg(args, 'dry', true);
  const includeUnknown = parseBooleanArg(args, 'includeUnknown', false);
  const olderMinutes = parseNumberArg(args, 'older', parseNumberArg(args, 'olderMinutes', 120));
  const keepPatterns = parseListArg(args, 'keep', DEFAULT_KEEP_TAB_PATTERNS);
  const closePatterns = parseListArg(args, 'close', DEFAULT_CLOSE_TAB_PATTERNS);
  const state = loadState();
  const openedAt = state.tabOpenedAt || {};
  const targets = await getTargets(port);
  const now = Date.now();

  const candidates = targets
    .filter((target) => target.type === 'page')
    .map((target) => {
      const opened = openedAt[target.id] || null;
      const ageMinutes = opened ? Math.floor((now - Date.parse(opened)) / 60000) : null;
      const label = `${target.title || ''}\n${target.url || ''}`;
      const protectedByPattern = matchesAnyPattern(label, keepPatterns);
      const matchedClosePattern = matchesAnyPattern(label, closePatterns);
      const tooOld = ageMinutes !== null && ageMinutes >= olderMinutes;
      const unknownAndAllowed = ageMinutes === null && includeUnknown;
      const shouldClose = !protectedByPattern && (matchedClosePattern || tooOld || unknownAndAllowed);
      return {
        id: target.id,
        title: target.title,
        url: target.url,
        openedAt: opened,
        ageMinutes,
        protected: protectedByPattern,
        reason: protectedByPattern
          ? 'kept by keep pattern'
          : matchedClosePattern
            ? 'matched close pattern'
            : tooOld
              ? `older than ${olderMinutes} minutes`
              : unknownAndAllowed
                ? 'unknown age and includeUnknown=true'
                : 'kept',
        shouldClose,
      };
    });

  const closed = [];
  for (const target of candidates.filter((item) => item.shouldClose)) {
    if (!dry) {
      const message = await closeTarget(port, target.id);
      closed.push({ ...target, message });
      if (state.tabOpenedAt) {
        delete state.tabOpenedAt[target.id];
      }
    } else {
      closed.push(target);
    }
  }

  if (!dry) {
    saveState(state);
  }

  console.log(JSON.stringify({
    ok: true,
    dry,
    closed,
    kept: candidates.filter((item) => !item.shouldClose),
    options: { olderMinutes, includeUnknown, keepPatterns, closePatterns },
  }, null, 2));
}

async function commandInfo(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const info = await withClient(port, targetId, async (client, target) => {
    const value = await evaluate(client, `(() => ({
      title: document.title,
      url: location.href,
      readyState: document.readyState,
      textSample: document.body ? document.body.innerText.slice(0, 500) : ''
    }))()`);
    return { id: target.id, ...value };
  });
  console.log(JSON.stringify(info, null, 2));
}

async function commandOpen(args) {
  const port = getPort(args);
  const url = parseStringArg(args, 'url', null);
  const targetId = parseStringArg(args, 'target', null);
  if (!url) {
    throw new Error('open requires url=<value>');
  }

  const info = await withClient(port, targetId, async (client, target) => {
    await client.send('Page.navigate', { url });
    await sleep(1500);
    const value = await evaluate(client, `(() => ({
      title: document.title,
      url: location.href,
      readyState: document.readyState
    }))()`);
    return { id: target.id, ...value };
  });
  console.log(JSON.stringify(info, null, 2));
}

async function commandClick(args) {
  const port = getPort(args);
  const selector = parseStringArg(args, 'selector', null);
  const targetId = parseStringArg(args, 'target', null);
  if (!selector) {
    throw new Error('click requires selector=<css>');
  }

  await withClient(port, targetId, async (client) => {
    await clickSelector(client, selector);
  });
  console.log(JSON.stringify({ ok: true, selector }, null, 2));
}

async function commandClickAt(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const x = parseNumberArg(args, 'x', NaN);
  const y = parseNumberArg(args, 'y', NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new Error('click-at requires numeric x=<value> y=<value>');
  }

  await withClient(port, targetId, async (client) => {
    await mouseClickAt(client, x, y);
  });
  console.log(JSON.stringify({ ok: true, x, y }, null, 2));
}

async function commandClickText(args) {
  const port = getPort(args);
  const text = parseStringArg(args, 'text', null);
  const targetId = parseStringArg(args, 'target', null);
  const exact = parseBooleanArg(args, 'exact', false);
  const tag = parseStringArg(args, 'tag', '');
  if (!text) {
    throw new Error('click-text requires text=<value>');
  }

  const result = await withClient(port, targetId, async (client) => clickByText(client, text, exact, tag));
  console.log(JSON.stringify({ ok: true, ...result }, null, 2));
}

async function commandType(args) {
  const port = getPort(args);
  const selector = parseStringArg(args, 'selector', null);
  const text = parseStringArg(args, 'text', null);
  const targetId = parseStringArg(args, 'target', null);
  const clear = parseBooleanArg(args, 'clear', false);

  if (!selector || text === null) {
    throw new Error('type requires selector=<css> and text=<value>');
  }

  await withClient(port, targetId, async (client) => {
    await focusSelector(client, selector);
    if (clear) {
      await evaluate(client, `(() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) return false;
        if ('value' in el) el.value = '';
        if (el.isContentEditable) el.innerText = '';
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()`);
    }
    await typeText(client, text);
  });

  console.log(JSON.stringify({ ok: true, selector, typed: text.length }, null, 2));
}

async function commandSetText(args) {
  const port = getPort(args);
  const selector = parseStringArg(args, 'selector', null);
  const text = parseStringArg(args, 'text', null);
  const targetId = parseStringArg(args, 'target', null);
  const clear = parseBooleanArg(args, 'clear', true);

  if (!selector || text === null) {
    throw new Error('set-text requires selector=<css> and text=<value>');
  }

  const result = await withClient(port, targetId, async (client) => setNativeValue(client, selector, text, clear));
  console.log(JSON.stringify({ ok: true, typed: text.length, ...result }, null, 2));
}

async function commandFill(args) {
  const port = getPort(args);
  const hint = parseStringArg(args, 'hint', null);
  const text = parseStringArg(args, 'text', null);
  const targetId = parseStringArg(args, 'target', null);
  const clear = parseBooleanArg(args, 'clear', true);
  if (!hint || text === null) {
    throw new Error('fill requires hint=<value> and text=<value>');
  }

  const result = await withClient(port, targetId, async (client) => fillFieldByHint(client, hint, text, clear));
  console.log(JSON.stringify({ ok: true, typed: text.length, ...result }, null, 2));
}

async function commandTelegramOpen(args) {
  const port = getPort(args);
  const username = parseStringArg(args, 'username', parseStringArg(args, 'user', null));
  const targetId = parseStringArg(args, 'target', null);
  if (!username) {
    throw new Error('telegram-open requires username=<telegram username>');
  }

  const cleaned = username.replace(/^@/, '');
  const result = await withClient(port, targetId, async (client, target) => {
    await client.send('Page.navigate', { url: `https://web.telegram.org/k/#@${cleaned}` });
    await sleep(1800);

    let value = await evaluate(client, `(() => ({
      title: document.title,
      url: location.href,
      textSample: document.body ? document.body.innerText.slice(0, 1000) : '',
      hasComposer: Boolean(document.querySelector('.input-message-input[contenteditable="true"]')),
      composerText: document.querySelector('.input-message-input[contenteditable="true"]')?.innerText || '',
      activePeer: Array.from(document.querySelectorAll('.chat-info .peer-title, .chat .peer-title'))
        .map((el) => (el.innerText || '').trim())
        .find(Boolean) || ''
    }))()`);

    if (!value.activePeer || !value.activePeer.toLowerCase().includes(cleaned.toLowerCase().replace(/bot$/, ''))) {
      const searchResult = await evaluate(client, `
        (() => {
          const username = ${JSON.stringify(cleaned)};
          const search = document.querySelector('input.input-search-input, input[type="text"]');
          if (!search) return { ok: false, error: 'Search input not found' };
          search.focus();
          const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(search), 'value');
          if (descriptor && descriptor.set) descriptor.set.call(search, username);
          else search.value = username;
          search.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: username }));
          return { ok: true };
        })()
      `);
      if (searchResult && searchResult.ok) {
        await sleep(1200);
        const match = await evaluate(client, `
          (() => {
            const username = ${JSON.stringify(cleaned)}.toLowerCase();
            const rows = Array.from(document.querySelectorAll('a, .row, [class*="ListItem"]'));
            const visible = (el) => {
              const rect = el.getBoundingClientRect();
              const style = getComputedStyle(el);
              return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const row = rows.find((el) => visible(el) && (el.innerText || '').toLowerCase().includes(username));
            if (!row) return { ok: false, error: 'Telegram search result not found' };
            row.scrollIntoView({ block: 'center', inline: 'center' });
            const rect = row.getBoundingClientRect();
            return { ok: true, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, text: (row.innerText || '').slice(0, 200) };
          })()
        `);
        if (match && match.ok) {
          await mouseClickAt(client, match.x, match.y);
          await sleep(1600);
        }
      }

      value = await evaluate(client, `(() => ({
        title: document.title,
        url: location.href,
        textSample: document.body ? document.body.innerText.slice(0, 1000) : '',
        hasComposer: Boolean(document.querySelector('.input-message-input[contenteditable="true"]')),
        composerText: document.querySelector('.input-message-input[contenteditable="true"]')?.innerText || '',
        activePeer: Array.from(document.querySelectorAll('.chat-info .peer-title, .chat .peer-title'))
          .map((el) => (el.innerText || '').trim())
          .find(Boolean) || ''
      }))()`);
    }

    return value;
  });

  console.log(JSON.stringify({ ok: true, username: cleaned, ...result }, null, 2));
}

async function commandTelegramSend(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const text = parseStringArg(args, 'text', null);
  const dry = parseBooleanArg(args, 'dry', false);
  const confirm = parseBooleanArg(args, 'confirm', false);
  const force = parseBooleanArg(args, 'force', false);
  if (text === null) {
    throw new Error('telegram-send requires text=<message>');
  }

  const result = await withClient(port, targetId, async (client) => {
    const selector = '.input-message-input[contenteditable="true"]';
    const before = await getTelegramChatSnapshot(client, 12);
    const sendKey = makeTelegramSendKey(before.activePeer, text);
    const sendState = loadJsonFile(TELEGRAM_SEND_STATE_PATH, { sent: {} });
    const previous = sendState.sent[sendKey];
    if (previous && !force) {
      return {
        skipped: true,
        sent: false,
        warning: 'Duplicate message blocked; use force=true to send again',
        previous,
        before,
      };
    }

    const currentDraft = (before.composerText || '').trim();
    if (currentDraft && currentDraft !== text.trim() && !force) {
      return {
        skipped: true,
        sent: false,
        warning: 'Composer already has text; not overwriting draft. Use force=true to replace it.',
        before,
      };
    }

    const blockingControl = before.controls.find((control) =>
      /Unblock|Only Premium|Frozen|JOIN|Open Chat/i.test(control.text)
    );
    if (blockingControl && !force) {
      return {
        skipped: true,
        sent: false,
        warning: `Blocking Telegram control is visible: ${blockingControl.text}`,
        before,
      };
    }

    if (dry || !confirm) {
      return {
        skipped: true,
        sent: false,
        warning: dry
          ? 'Dry run: message preview only; composer was not changed'
          : 'Message preview only; pass confirm=true to send',
        before,
        preview: { peer: before.activePeer, text },
      };
    }

    const prepared = await setNativeValue(client, selector, text, true);
    const preparedSnapshot = await getTelegramChatSnapshot(client, 12);

    const preparedBlockingControl = preparedSnapshot.controls.find((control) =>
      /Unblock|Only Premium|Frozen|JOIN|Open Chat/i.test(control.text)
    );
    if (preparedBlockingControl && !force) {
      return {
        skipped: true,
        sent: false,
        warning: `Blocking Telegram control is visible: ${preparedBlockingControl.text}`,
        prepared,
        before,
        after: preparedSnapshot,
      };
    }

    const button = await clickTelegramSendButton(client);

    let status = null;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await sleep(800);
      status = await evaluate(client, `(() => {
        const composer = document.querySelector(${JSON.stringify(selector)});
        return {
          composerText: composer ? composer.innerText : '',
          bodyTail: document.body ? document.body.innerText.slice(-2000) : ''
        };
      })()`);
      if (!status.composerText || !status.composerText.includes(text.slice(0, Math.min(20, text.length)))) {
        break;
      }
    }

    const after = await getTelegramChatSnapshot(client, 12);
    const sent = !status.composerText || !status.composerText.includes(text.slice(0, Math.min(20, text.length)));
    const output = {
      prepared,
      sent,
      warning: sent ? null : 'Message remains in composer; not retrying to avoid duplicate sends',
      before,
      after,
      ...status,
    };

    if (sent) {
      sendState.sent[sendKey] = {
        at: new Date().toISOString(),
        peer: before.activePeer,
        text: text.slice(0, 500),
      };
      saveJsonFile(TELEGRAM_SEND_STATE_PATH, sendState);
    }

    return output;
  });

  console.log(JSON.stringify({ ok: true, typed: text.length, ...result }, null, 2));
}

async function commandTelegramSendFile(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const file = parseStringArg(args, 'file', null);
  const caption = parseStringArg(args, 'caption', '');
  const confirm = parseBooleanArg(args, 'confirm', false);
  if (!file) {
    throw new Error('telegram-send-file requires file=<path>');
  }

  const resolved = path.resolve(file);
  if (!fs.existsSync(resolved)) {
    throw new Error(`File not found: ${resolved}`);
  }

  const result = await withClient(port, targetId, async (client) => {
    const before = await getTelegramChatSnapshot(client, 12);
    await prepareTelegramDocumentAttach(client);
    await setFileInput(client, 'input[type="file"]', [resolved]);
    await sleep(1200);
    if (caption) {
      await setNativeValue(client, '.input-message-input[contenteditable="true"]', caption, true);
      await sleep(300);
    }

    const prepared = await getTelegramChatSnapshot(client, 12);
    const hasFile = prepared.fileInputs.some((item) => item.name === path.basename(resolved));

    if (!confirm) {
      return {
        skipped: true,
        sent: false,
        before,
        after: prepared,
        warning: 'File prepared only; pass confirm=true to send',
      };
    }

    const sendButton = await findTelegramSendFileButton(client);
    if (!sendButton || !sendButton.ok) {
      throw new Error(sendButton?.error || 'Telegram SEND button not found in file preview');
    }
    await mouseClickAt(client, sendButton.x, sendButton.y);
    await sleep(1200);
    const after = await getTelegramChatSnapshot(client, 12);
    const sent = after.messages.length > before.messages.length || !after.fileInputs.some((item) => item.name === path.basename(resolved));
    return {
      sent,
      before,
      prepared,
      after,
      sendButton,
      hadPreparedFile: hasFile,
      warning: sent ? null : 'File input accepted the file, but Telegram UI did not confirm send',
    };
  });

  console.log(JSON.stringify({ ok: true, file: resolved, ...result }, null, 2));
}

async function commandTelegramChat(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const limit = parseNumberArg(args, 'limit', 20);
  const result = await withClient(port, targetId, async (client) => getTelegramChatSnapshot(client, limit));
  console.log(JSON.stringify({ ok: true, ...result }, null, 2));
}

async function commandTelegramInbox(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const limit = parseNumberArg(args, 'limit', 20);
  const result = await withClient(port, targetId, async (client) => getTelegramInboxSnapshot(client, limit));
  console.log(JSON.stringify({ ok: true, dialogs: result }, null, 2));
}

async function commandTelegramStatus(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const chatLimit = parseNumberArg(args, 'chat', parseNumberArg(args, 'chatLimit', 8));
  const inboxLimit = parseNumberArg(args, 'inbox', parseNumberArg(args, 'inboxLimit', 12));
  const result = await withClient(port, targetId, async (client) => {
    const pages = await getTargets(port);
    const telegramPages = pages
      .filter((page) => page.type === 'page' && /web\.telegram\.org/i.test(page.url || ''))
      .map((page) => ({
        id: page.id,
        title: page.title,
        url: page.url,
      }));
    const active = await getTelegramChatSnapshot(client, chatLimit);
    const dialogs = await getTelegramInboxSnapshot(client, inboxLimit);
    return {
      active,
      dialogs,
      telegramPages,
      warnings: [
        active.composerText ? 'Active Telegram composer has draft text' : null,
        active.controls.some((control) => /Unblock|Only Premium|Frozen|JOIN|Open Chat/i.test(control.text))
          ? 'Active Telegram chat has a blocking control'
          : null,
      ].filter(Boolean),
    };
  });
  console.log(JSON.stringify({ ok: true, ...result }, null, 2));
}

async function commandTelegramClear(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const result = await withClient(port, targetId, async (client) => {
    const selector = '.input-message-input[contenteditable="true"]';
    const before = await getTelegramChatSnapshot(client, 12);
    const cleared = await clearNativeValue(client, selector);
    const after = await getTelegramChatSnapshot(client, 12);
    return { cleared, before, after };
  });
  console.log(JSON.stringify({ ok: true, ...result }, null, 2));
}

async function commandGmailSend(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const to = parseStringArg(args, 'to', null);
  const subject = parseStringArg(args, 'subject', '');
  const body = parseStringArg(args, 'body', '');
  const confirm = parseBooleanArg(args, 'confirm', false);
  if (!to) {
    throw new Error('gmail-send requires to=<email>');
  }

  const result = await withClient(port, targetId, async (client, target) => {
    if (!/mail\.google\.com/i.test(target.url || '')) {
      throw new Error('gmail-send target must be an open Gmail tab');
    }

    const params = new URLSearchParams({ view: 'cm', fs: '1', to, su: subject, body, tf: 'cm' });
    const composeUrl = `https://mail.google.com/mail/u/0/?${params.toString()}`;
    await client.send('Page.navigate', { url: composeUrl });
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await sleep(500);
      const readyState = await evaluate(client, 'document.readyState');
      if (readyState === 'complete') {
        break;
      }
    }
    await sleep(1500);
    let before = null;
    const expectedBodyPrefix = body.slice(0, Math.min(40, body.length));
    for (let attempt = 0; attempt < 30; attempt += 1) {
      before = await evaluate(client, `(() => ({
        title: document.title,
        text: document.body ? document.body.innerText.slice(0, 3000) : ''
      }))()`);
      if (before.text.includes(to) && (!expectedBodyPrefix || before.text.includes(expectedBodyPrefix))) {
        break;
      }
      await sleep(500);
    }

    if (!confirm) {
      return {
        skipped: true,
        sent: false,
        warning: 'Message composed but not sent; pass confirm=true to send',
        before,
      };
    }

    let sendButton = null;
    for (let attempt = 0; attempt < 25; attempt += 1) {
      sendButton = await evaluate(client, `
        (() => {
          const to = ${JSON.stringify(to)};
          const subject = ${JSON.stringify(subject)};
          const bodyPrefix = ${JSON.stringify(expectedBodyPrefix)};
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const textOf = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
          const composeRoots = Array.from(document.querySelectorAll('div[role="dialog"], form, table, div'))
            .filter(visible)
            .filter((el) => {
              const text = textOf(el);
              if (!text.includes(to)) return false;
              if (subject && !text.includes(subject)) return false;
              if (bodyPrefix && !text.includes(bodyPrefix)) return false;
              return Boolean(el.querySelector('div[role="button"][data-tooltip^="Send"], div[role="button"][aria-label^="Send"]'));
            })
            .sort((a, b) => {
              const ar = a.getBoundingClientRect();
              const br = b.getBoundingClientRect();
              return (ar.width * ar.height) - (br.width * br.height);
            });
          const root = composeRoots[0] || document.body;
          const buttons = Array.from(root.querySelectorAll('div[role="button"][data-tooltip^="Send"], div[role="button"][aria-label^="Send"]'))
            .filter(visible)
            .map((el) => {
              const rect = el.getBoundingClientRect();
              return {
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2,
                text: textOf(el),
                tooltip: el.getAttribute('data-tooltip') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
              };
            });
          return buttons[0] ? { ok: true, ...buttons[0] } : { ok: false, error: 'Visible Send button not found in matching compose' };
        })()
      `);
      if (sendButton && sendButton.ok) {
        break;
      }
      await sleep(500);
    }

    if (!sendButton || !sendButton.ok) {
      throw new Error(sendButton?.error || 'Visible Send button not found');
    }

    await mouseClickAt(client, sendButton.x, sendButton.y);
    await sleep(700);
    const composeStillVisible = await evaluate(client, `
      (() => Boolean(document.body && document.body.innerText.includes(${JSON.stringify(to)}) && document.body.innerText.includes(${JSON.stringify(subject)})))()
    `);
    let domClick = null;
    if (composeStillVisible) {
      domClick = await evaluate(client, `
        (() => {
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const button = Array.from(document.querySelectorAll('div[role="button"][data-tooltip^="Send"], div[role="button"][aria-label^="Send"]')).find(visible);
          if (!button) return { ok: false, error: 'Visible Send button not found for DOM click' };
          button.focus();
          button.click();
          return {
            ok: true,
            text: (button.innerText || button.textContent || '').trim(),
            tooltip: button.getAttribute('data-tooltip') || '',
            ariaLabel: button.getAttribute('aria-label') || ''
          };
        })()
      `);
    }
    await sleep(2500);
    const after = await evaluate(client, `(() => ({
      title: document.title,
      url: location.href,
      text: document.body ? document.body.innerText.slice(0, 1500) : ''
    }))()`);

    const sentUrl = 'https://mail.google.com/mail/u/0/#sent';
    await client.send('Page.navigate', { url: sentUrl });
    await sleep(2500);
    let verification = null;
    const recipientLabel = to.split('@')[0];
    for (let attempt = 0; attempt < 20; attempt += 1) {
      verification = await evaluate(client, `(() => ({
        title: document.title,
        url: location.href,
        text: document.body ? document.body.innerText.slice(0, 5000) : '',
        found: Boolean(document.body && document.body.innerText.includes(${JSON.stringify(subject)}) && (
          document.body.innerText.includes(${JSON.stringify(to)}) ||
          document.body.innerText.includes(${JSON.stringify(recipientLabel)})
        ))
      }))()`);
      if (verification.found) {
        break;
      }
      await sleep(500);
    }

    return { sent: Boolean(verification && verification.found), sendButton, domClick, before, after, verification };
  });

  console.log(JSON.stringify({ ok: true, to, subject, ...result }, null, 2));
}

async function commandListButtons(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const limit = parseNumberArg(args, 'limit', 20);
  const items = await withClient(port, targetId, async (client) => listClickableElements(client, limit));
  console.log(JSON.stringify(items, null, 2));
}

async function commandListFields(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const limit = parseNumberArg(args, 'limit', 20);
  const items = await withClient(port, targetId, async (client) => listFields(client, limit));
  console.log(JSON.stringify(items, null, 2));
}

async function commandPress(args) {
  const port = getPort(args);
  const key = parseStringArg(args, 'key', null);
  const targetId = parseStringArg(args, 'target', null);
  if (!key) {
    throw new Error('press requires key=<value>');
  }

  await withClient(port, targetId, async (client) => {
    await pressKey(client, key);
  });
  console.log(JSON.stringify({ ok: true, key }, null, 2));
}

async function commandEval(args) {
  const port = getPort(args);
  const expression = parseStringArg(args, 'js', null);
  const filePath = parseStringArg(args, 'file', null);
  const targetId = parseStringArg(args, 'target', null);
  const finalExpression = filePath
    ? fs.readFileSync(path.resolve(filePath), 'utf8')
    : expression;
  if (!finalExpression) {
    throw new Error('eval requires js=<expression> or file=<path>');
  }

  const value = await withClient(port, targetId, async (client) => evaluate(client, finalExpression));
  console.log(JSON.stringify(value, null, 2));
}

async function commandSetFiles(args) {
  const port = getPort(args);
  const selector = parseStringArg(args, 'selector', null);
  const file = parseStringArg(args, 'file', null);
  const filesJson = parseJsonArg(args, 'files', null);
  const targetId = parseStringArg(args, 'target', null);

  if (!selector) {
    throw new Error('set-files requires selector=<css> and file=<path> or files=[...]');
  }

  let files = [];
  if (Array.isArray(filesJson)) {
    files = filesJson;
  } else if (file) {
    files = [file];
  }

  if (!files.length) {
    throw new Error('set-files requires file=<path> or files=[...]');
  }

  const resolved = files.map((p) => path.resolve(p));
  for (const p of resolved) {
    if (!fs.existsSync(p)) {
      throw new Error(`File not found: ${p}`);
    }
  }

  await withClient(port, targetId, async (client) => {
    await setFileInput(client, selector, resolved);
  });

  console.log(JSON.stringify({ ok: true, selector, files: resolved }, null, 2));
}

async function commandScreenshot(args) {
  const port = getPort(args);
  const targetId = parseStringArg(args, 'target', null);
  const outputPath = parseStringArg(args, 'out', path.join(ROOT, `page-${Date.now()}.png`));

  ensureDir(path.dirname(outputPath));

  await withClient(port, targetId, async (client) => {
    const { data } = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true });
    fs.writeFileSync(outputPath, Buffer.from(data, 'base64'));
  });

  console.log(outputPath);
}

async function commandHelp() {
  console.log(`browser-bridge commands:
  start [port=9222] [profile=C:\\path\\to\\profile]
  list [port=9222]
  new-page url=https://example.com [port=9222]
  close-page target=<id> [port=9222]
  clean-tabs [dry=true] [older=120] [includeUnknown=false] [keep=mail.google.com,web.telegram.org] [close=chrome://newtab/,kadrof.ru,yonote.ru] [port=9222]
  info [target=<id>] [port=9222]
  open url=https://example.com [target=<id>] [port=9222]
  click selector=.btn [target=<id>] [port=9222]
  click-at x=100 y=200 [target=<id>] [port=9222]
  click-text text=Login [exact=false] [tag=button] [target=<id>] [port=9222]
  type selector=input[name=q] text=hello [clear=true] [target=<id>] [port=9222]
  set-text selector=input[name=q] text=hello [clear=true] [target=<id>] [port=9222]
  fill hint=email text=mail@example.com [clear=true] [target=<id>] [port=9222]
  press key=Enter [target=<id>] [port=9222]
  telegram-open username=digitaltenderbot [target=<id>] [port=9222]
  telegram-status [chat=8] [inbox=12] [target=<id>] [port=9222]
  telegram-chat [limit=20] [target=<id>] [port=9222]
  telegram-inbox [limit=20] [target=<id>] [port=9222]
  telegram-clear [target=<id>] [port=9222]
  telegram-send text=/start [confirm=true] [dry=false] [force=false] [target=<id>] [port=9222]
  telegram-send-file file=C:\\path\\cv.pdf [caption=Hello] [confirm=true] [target=<id>] [port=9222]
  gmail-send to=client@example.com subject=Hello body=Message [confirm=false] [target=<gmail-id>] [port=9222]
  list-buttons [limit=20] [target=<id>] [port=9222]
  list-fields [limit=20] [target=<id>] [port=9222]
  eval js=(() => document.title)() [target=<id>] [port=9222]
  eval file=C:\\path\\script.js [target=<id>] [port=9222]
  set-files selector=input[type=file] file=C:\\path\\img.jpg [target=<id>] [port=9222]
  set-files selector=input[type=file] files=["C:\\\\a.png","C:\\\\b.png"] [target=<id>] [port=9222]
  screenshot [out=C:\\path\\page.png] [target=<id>] [port=9222]
  help`);
}

async function main() {
  const [, , command = 'help', ...args] = process.argv;
  const handler = commandHandlers[command];
  if (!handler) {
    throw new Error(`Unknown command: ${command}`);
  }

  await handler(args);
}

const commandHandlers = {
  start: commandStart,
  list: commandList,
  'new-page': commandNewPage,
  'close-page': commandClosePage,
  'clean-tabs': commandCleanTabs,
  info: commandInfo,
  open: commandOpen,
  click: commandClick,
  'click-at': commandClickAt,
  'click-text': commandClickText,
  type: commandType,
  'set-text': commandSetText,
  fill: commandFill,
  press: commandPress,
  'telegram-open': commandTelegramOpen,
  'telegram-status': commandTelegramStatus,
  'telegram-chat': commandTelegramChat,
  'telegram-inbox': commandTelegramInbox,
  'telegram-clear': commandTelegramClear,
  'telegram-send': commandTelegramSend,
  'telegram-send-file': commandTelegramSendFile,
  'gmail-send': commandGmailSend,
  'list-buttons': commandListButtons,
  'list-fields': commandListFields,
  eval: commandEval,
  'set-files': commandSetFiles,
  screenshot: commandScreenshot,
  help: commandHelp,
};

module.exports = {
  commandHandlers,
  parseStringArg,
  parseBooleanArg,
  parseNumberArg,
  parseListArg,
  loadState,
  saveState,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message || String(error));
    process.exitCode = 1;
  });
}
