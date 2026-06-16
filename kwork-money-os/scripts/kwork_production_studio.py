#!/usr/bin/env python3
"""Local Kwork Production Studio: choose and prepare the first serious kwork."""

from __future__ import annotations

from kwork_studio_common import (
    SPEC_JSON,
    SPEC_MD,
    STUDIO_REPORT,
    build_first_kwork_spec,
    ensure_studio_dirs,
    markdown_for_spec,
    rel,
    write_json,
    write_text,
)


POSITIONING_OPTIONS = [
    {
        "name": "Telegram-бот для заявок + Google Таблица",
        "score": 92,
        "why": "самый понятный результат, быстрый delivery, легко показать ценность",
    },
    {
        "name": "DevOps-настройка проекта: Docker, Linux, деплой",
        "score": 78,
        "why": "сильный DevOps-наклон, но для первого заказа выглядит чуть сложнее",
    },
    {
        "name": "Автоматизация бизнеса: Python, таблицы, уведомления",
        "score": 84,
        "why": "широко, но менее конкретно, чем Telegram+Sheets",
    },
]


def main() -> None:
    ensure_studio_dirs()
    spec = build_first_kwork_spec()
    payload = {
        "positioning_options": POSITIONING_OPTIONS,
        "selected_spec": spec,
        "success_criteria": [
            "понятный результат для клиента",
            "DevOps-усиление без завышенных обещаний",
            "пакеты 3000/5500/9000 ₽",
            "без серых сценариев и обходов",
            "готово для human review, не для автопубликации",
        ],
    }
    write_json(SPEC_JSON, spec)
    write_text(SPEC_MD, markdown_for_spec(spec))
    lines = [
        "# Kwork Production Studio Report",
        "",
        f"- selected_kwork_title: `{spec['title']}`",
        f"- selected_positioning: `{spec['selected_positioning']}`",
        f"- spec_json: `{rel(SPEC_JSON)}`",
        f"- spec_md: `{rel(SPEC_MD)}`",
        f"- verdict: `READY_FOR_COVER_AND_FILL`",
        "",
        "## Positioning Options",
        *(f"- {item['name']}: score={item['score']} | {item['why']}" for item in POSITIONING_OPTIONS),
        "",
        "## Why This Wins",
        *(f"- {item}" for item in spec["why_selected"]),
        "",
        "## Manual-Only",
        "- Save, moderation, publication, proposals, messages, orders, phone/SMS, withdrawal, and delete actions remain manual-only.",
    ]
    write_text(STUDIO_REPORT, "\n".join(lines))
    print(STUDIO_REPORT)
    print(f"selected_kwork_title={spec['title']}")
    print(f"spec_json={SPEC_JSON}")
    print("verdict=READY_FOR_COVER_AND_FILL")


if __name__ == "__main__":
    main()
