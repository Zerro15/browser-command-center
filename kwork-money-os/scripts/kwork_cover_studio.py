#!/usr/bin/env python3
"""Generate local-only Kwork cover concepts and simple PNG previews."""

from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

from kwork_studio_common import COVER_PROMPTS, COVER_REPORT, COVER_SCORES, COVERS_DIR, ensure_studio_dirs, rel, write_json, write_text


WIDTH = 880
HEIGHT = 560


CONCEPTS = [
    {
        "id": "telegram_sheets_devops_01",
        "title": "BOT + SHEETS",
        "subtitle": "REQUESTS TO GOOGLE SHEETS",
        "palette": [(16, 42, 67), (31, 101, 163), (37, 196, 132), (246, 248, 250)],
        "style": "clean DevOps style",
        "score": 91,
        "why": "самый понятный результат и хороший DevOps-trust",
    },
    {
        "id": "telegram_sheets_devops_02",
        "title": "LEADS TO SHEETS",
        "subtitle": "TELEGRAM BOT + SETUP",
        "palette": [(22, 28, 36), (68, 180, 122), (239, 196, 92), (250, 250, 244)],
        "style": "Telegram bot + Google Sheets",
        "score": 87,
        "why": "хорошо продаёт бизнес-результат, выглядит просто и надёжно",
    },
    {
        "id": "telegram_sheets_devops_03",
        "title": "PYTHON AUTOMATION",
        "subtitle": "API + DOCKER + LINUX",
        "palette": [(20, 24, 31), (53, 88, 170), (255, 184, 77), (240, 245, 255)],
        "style": "minimal premium tech",
        "score": 84,
        "why": "сильный tech vibe, но менее конкретно для первого заказа",
    },
]

FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, concept: dict) -> None:
    """Write a valid PNG with modern geometric layout using only stdlib."""
    bg, accent, green, light = concept["palette"]
    pixels = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            t = x / WIDTH
            shade = 0.72 + 0.28 * t
            r = int(bg[0] * shade + accent[0] * (1 - shade) * 0.35)
            g = int(bg[1] * shade + accent[1] * (1 - shade) * 0.35)
            b = int(bg[2] * shade + accent[2] * (1 - shade) * 0.35)
            if 90 < x < 790 and 80 < y < 470:
                r = min(255, r + 8)
                g = min(255, g + 8)
                b = min(255, b + 8)
            if abs((x - 670) ** 2 + (y - 155) ** 2 - 70**2) < 600:
                r, g, b = green
            if 110 < x < 620 and 340 < y < 356:
                r, g, b = green
            if 110 < x < 420 and 380 < y < 394:
                r, g, b = light
            if 70 < x < 810 and 58 < y < 64:
                r, g, b = accent
            row.append([r, g, b])
        pixels.append(row)
    draw_text(pixels, 108, 160, concept["title"], 9, light)
    draw_text(pixels, 112, 255, concept["subtitle"], 4, green)
    draw_text(pixels, 112, 415, "PYTHON API DOCKER", 4, light)
    raw = b"".join(bytes([0]) + b"".join(bytes(pixel) for pixel in row) for row in pixels)
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(raw, 6))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def draw_text(pixels: list[list[list[int]]], x: int, y: int, text: str, scale: int, color: tuple[int, int, int]) -> None:
    cursor = x
    for char in text.upper():
        glyph = FONT.get(char, FONT[" "])
        width = len(glyph[0])
        for gy, line in enumerate(glyph):
            for gx, bit in enumerate(line):
                if bit != "1":
                    continue
                for sy in range(scale):
                    py = y + gy * scale + sy
                    if py < 0 or py >= HEIGHT:
                        continue
                    for sx in range(scale):
                        px = cursor + gx * scale + sx
                        if 0 <= px < WIDTH:
                            pixels[py][px] = [color[0], color[1], color[2]]
        cursor += (width + 1) * scale


def write_svg(path: Path, concept: dict) -> None:
    bg, accent, green, light = ["#%02x%02x%02x" % tuple(color) for color in concept["palette"]]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1"><stop offset="0" stop-color="{bg}"/><stop offset="1" stop-color="{accent}"/></linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect x="70" y="60" width="740" height="430" rx="34" fill="{bg}" opacity="0.54" stroke="{accent}" stroke-width="3"/>
  <circle cx="675" cy="155" r="72" fill="none" stroke="{green}" stroke-width="12"/>
  <path d="M625 157 L660 190 L728 115" fill="none" stroke="{green}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="110" y="190" fill="{light}" font-family="Arial, sans-serif" font-size="62" font-weight="800">{concept['title']}</text>
  <text x="112" y="252" fill="{green}" font-family="Arial, sans-serif" font-size="34" font-weight="700">{concept['subtitle']}</text>
  <text x="112" y="335" fill="{light}" font-family="Arial, sans-serif" font-size="28">Python / API / .env / Docker</text>
  <rect x="112" y="365" width="500" height="16" rx="8" fill="{green}"/>
  <rect x="112" y="404" width="310" height="14" rx="7" fill="{light}" opacity="0.82"/>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    ensure_studio_dirs()
    prompts = ["# Kwork Cover Prompts", ""]
    scores = []
    for index, concept in enumerate(CONCEPTS, start=1):
        png = COVERS_DIR / f"cover_telegram_sheets_devops_0{index}.png"
        svg = COVERS_DIR / f"cover_telegram_sheets_devops_0{index}.svg"
        write_png(png, concept)
        write_svg(svg, concept)
        prompt = (
            f"Commercial Kwork cover, {concept['style']}, headline '{concept['title']}', "
            f"subtitle '{concept['subtitle']}', modern premium tech, readable large typography, "
            "Telegram bot, Google Sheets, Python API, Docker/Linux deployment vibe, no official logos, no hype promises."
        )
        negative = "childish cartoon, clutter, tiny text, official logos, guaranteed income, spam, captcha bypass"
        prompts.extend(
            [
                f"## {index}. {concept['style']}",
                f"- prompt: {prompt}",
                f"- negative_prompt: {negative}",
                f"- cover_text: {concept['title']} / {concept['subtitle']}",
                f"- composition: dark card, large headline, trust checkmark, DevOps line",
                f"- why_sell: {concept['why']}",
                "",
            ]
        )
        scores.append(
            {
                "id": concept["id"],
                "png": rel(png),
                "svg": rel(svg),
                "readability": min(100, concept["score"] + 3),
                "differentiation": concept["score"] - 4,
                "trust": concept["score"],
                "service_fit": concept["score"] + 2,
                "ctr_potential": concept["score"] - 2,
                "total_score": concept["score"],
                "why": concept["why"],
            }
        )
    write_text(COVER_PROMPTS, "\n".join(prompts))
    write_json(COVER_SCORES, {"selected_cover": scores[0]["png"], "mode": "local_png_stdlib", "scores": scores})
    report = [
        "# Kwork Cover Studio Report",
        "",
        "- mode: `prompt_only + local_png_stdlib`",
        f"- selected_cover: `{scores[0]['png']}`",
        f"- cover_prompts: `{rel(COVER_PROMPTS)}`",
        f"- cover_scores: `{rel(COVER_SCORES)}`",
        "- note: PNG previews are generated without external APIs; SVG files contain readable text layout.",
        "",
        "## Scores",
        *(f"- {item['id']}: score={item['total_score']} | {item['why']} | `{item['png']}`" for item in scores),
    ]
    write_text(COVER_REPORT, "\n".join(report))
    print(COVER_REPORT)
    print(f"selected_cover={scores[0]['png']}")
    print("covers_created=3")


if __name__ == "__main__":
    main()
