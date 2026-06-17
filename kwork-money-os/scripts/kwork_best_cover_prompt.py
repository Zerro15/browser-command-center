#!/usr/bin/env python3
"""Write one best human-in-the-loop cover prompt for ChatGPT image generation."""

from __future__ import annotations

from datetime import datetime

from kwork_cover_bridge import INBOX_DIR
from kwork_studio_common import (
    BEST_COVER_PROMPT_JSON,
    BEST_COVER_PROMPT_MD,
    BEST_COVER_PROMPT_REPORT,
    ensure_studio_dirs,
    rel,
    write_json,
    write_text,
)


PROMPT = """Создай горизонтальную обложку для Kwork 1320x880.

Текст на обложке крупно:
Telegram-бот для заявок

Подзаголовок:
Google Таблица + деплой

Стиль: премиальный tech/SaaS/DevOps, чистый коммерческий интерфейс для бизнес-услуги. Не мультяшный, не детский.

Композиция: слева крупный читаемый заголовок, справа схема автоматизации: карточка чата, таблица заявок, серверный блок, линии API-соединения. Много воздуха, аккуратные блоки, dashboard vibe.

Цвета: глубокий navy фон, белый текст, cyan/бирюзовые акценты, немного зелёного. Высокая читаемость.

Смысл: бот принимает заявки, пишет их в таблицу, проект запускается и отдаётся с понятной инструкцией.

Не использовать реальные логотипы Telegram, Google, Docker. Можно использовать абстрактные иконки чата, таблицы, сервера, API, Python/DevOps vibe.

Negative prompt: без хаоса, без мелкого текста, без клипарта, без дешёвых 3D-иконок, без обещаний 100% результата, без слов лучший/гарантия продаж."""


def main() -> None:
    ensure_studio_dirs()
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_size": "1320x880",
        "title_text": "Telegram-бот для заявок",
        "subtitle_text": "Google Таблица + деплой",
        "prompt": PROMPT,
        "inbox_path": str(INBOX_DIR),
        "next_command": "npm run money:cover-inbox-check",
        "safety": "ChatGPT UI is manual-only; Kwork final buttons are manual-only.",
    }
    write_json(BEST_COVER_PROMPT_JSON, payload)
    write_text(
        BEST_COVER_PROMPT_MD,
        "\n".join(
            [
                "# Best Cover Prompt For ChatGPT",
                "",
                "```text",
                PROMPT,
                "```",
                "",
                f"- save_generated_image_to: `{INBOX_DIR}`",
                "- next_command: `npm run money:cover-inbox-check`",
                "- safety: ChatGPT UI is not automated.",
            ]
        ),
    )
    write_text(
        BEST_COVER_PROMPT_REPORT,
        "\n".join(
            [
                "# Best Cover Prompt Report",
                "",
                f"- generated_at: `{payload['generated_at']}`",
                f"- prompt_md: `{rel(BEST_COVER_PROMPT_MD)}`",
                f"- prompt_json: `{rel(BEST_COVER_PROMPT_JSON)}`",
                f"- inbox_path: `{INBOX_DIR}`",
                "- next_command: `npm run money:cover-inbox-check`",
                "- safety: one prompt only; ChatGPT UI remains manual-only.",
            ]
        ),
    )
    print(BEST_COVER_PROMPT_REPORT)
    print("prompt:")
    print(PROMPT)
    print(f"inbox_path={INBOX_DIR}")
    print("next_command=npm run money:cover-inbox-check")


if __name__ == "__main__":
    main()
