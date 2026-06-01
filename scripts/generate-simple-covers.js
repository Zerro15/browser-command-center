#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const OUT = path.join(__dirname, '..', 'covers-new');
const WIDTH = 660;
const HEIGHT = 440;

const covers = [
  { file: 'openai-api.png', bg: [14, 28, 54], accent: [38, 208, 124], second: [86, 160, 255] },
  { file: 'google-sheets-automation.png', bg: [20, 67, 43], accent: [58, 201, 116], second: [245, 190, 80] },
  { file: 'excel-csv-processing.png', bg: [42, 55, 74], accent: [87, 196, 255], second: [255, 214, 102] },
  { file: 'browser-automation.png', bg: [50, 38, 78], accent: [178, 115, 255], second: [255, 130, 91] },
];

function crcTable() {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[n] = c >>> 0;
  }
  return table;
}

const CRC = crcTable();

function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) {
    c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const name = Buffer.from(type);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([name, data])), 0);
  return Buffer.concat([length, name, data, checksum]);
}

function writePixel(buf, x, y, color) {
  if (x < 0 || y < 0 || x >= WIDTH || y >= HEIGHT) return;
  const rowStart = y * (WIDTH * 3 + 1) + 1;
  const offset = rowStart + x * 3;
  buf[offset] = color[0];
  buf[offset + 1] = color[1];
  buf[offset + 2] = color[2];
}

function mix(a, b, t) {
  return [
    Math.round(a[0] * (1 - t) + b[0] * t),
    Math.round(a[1] * (1 - t) + b[1] * t),
    Math.round(a[2] * (1 - t) + b[2] * t),
  ];
}

function rect(buf, x, y, w, h, color) {
  for (let yy = y; yy < y + h; yy += 1) {
    for (let xx = x; xx < x + w; xx += 1) {
      writePixel(buf, xx, yy, color);
    }
  }
}

function circle(buf, cx, cy, r, color) {
  const rr = r * r;
  for (let y = cy - r; y <= cy + r; y += 1) {
    for (let x = cx - r; x <= cx + r; x += 1) {
      if ((x - cx) * (x - cx) + (y - cy) * (y - cy) <= rr) {
        writePixel(buf, x, y, color);
      }
    }
  }
}

function makePng(spec) {
  const raw = Buffer.alloc(HEIGHT * (WIDTH * 3 + 1));
  for (let y = 0; y < HEIGHT; y += 1) {
    raw[y * (WIDTH * 3 + 1)] = 0;
    for (let x = 0; x < WIDTH; x += 1) {
      const t = (x / WIDTH) * 0.7 + (y / HEIGHT) * 0.3;
      writePixel(raw, x, y, mix(spec.bg, [spec.bg[0] + 28, spec.bg[1] + 28, spec.bg[2] + 28], t));
    }
  }

  rect(raw, 44, 58, 572, 324, mix(spec.bg, [255, 255, 255], 0.08));
  rect(raw, 68, 82, 524, 10, spec.accent);
  rect(raw, 68, 116, 250, 34, spec.second);
  rect(raw, 68, 174, 420, 18, mix(spec.accent, [255, 255, 255], 0.2));
  rect(raw, 68, 214, 360, 18, mix(spec.second, [255, 255, 255], 0.2));
  rect(raw, 68, 254, 290, 18, mix(spec.accent, [255, 255, 255], 0.35));
  circle(raw, 516, 236, 82, mix(spec.accent, spec.second, 0.45));
  circle(raw, 516, 236, 46, mix(spec.bg, [255, 255, 255], 0.18));
  rect(raw, 448, 328, 96, 14, spec.accent);
  rect(raw, 448, 352, 144, 14, spec.second);

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(WIDTH, 0);
  ihdr.writeUInt32BE(HEIGHT, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 0 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

fs.mkdirSync(OUT, { recursive: true });
for (const cover of covers) {
  fs.writeFileSync(path.join(OUT, cover.file), makePng(cover));
}

console.log(JSON.stringify({ ok: true, out: OUT, files: covers.map((cover) => cover.file) }, null, 2));
