#!/usr/bin/env python3
"""Shared helpers for local-only Kwork Production Studio artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir


STUDIO_DIR = DATA / "kwork_studio"
COVERS_DIR = STUDIO_DIR / "covers"
SPEC_JSON = STUDIO_DIR / "first_kwork_spec.json"
SPEC_MD = STUDIO_DIR / "first_kwork_spec.md"
COMPETITORS_JSON = STUDIO_DIR / "competitors.json"
COVER_PROMPTS = STUDIO_DIR / "cover_prompts.md"
COVER_SCORES = STUDIO_DIR / "cover_scores.json"
SELECTED_COVER = COVERS_DIR / "cover_telegram_sheets_devops_01.png"
STUDIO_REPORT = REPORTS / "kwork_studio_report.md"
COMPETITOR_REPORT = REPORTS / "kwork_competitor_scan_report.md"
COVER_REPORT = REPORTS / "kwork_cover_studio_report.md"
COVER_UPLOAD_REPORT = REPORTS / "kwork_cover_upload_report.md"
FULL_FILL_REPORT = REPORTS / "kwork_full_fill_cdp_report.md"
MARKETING_QA_REPORT = REPORTS / "kwork_marketing_qa_report.md"
DOM_SNAPSHOT = STUDIO_DIR / "last_kwork_form_dom_snapshot.json"
MANUAL_FILL_PACK = STUDIO_DIR / "manual_fill_pack.md"
QUICK_PUBLISH_CHECKLIST = REPORTS / "kwork_quick_publish_checklist.md"
QUICK_PROPOSALS_REPORT = REPORTS / "quick_proposals_today.md"
BEST_COVER_PROMPT_MD = STUDIO_DIR / "best_cover_prompt_for_chatgpt.md"
BEST_COVER_PROMPT_JSON = STUDIO_DIR / "best_cover_prompt_for_chatgpt.json"
BEST_COVER_PROMPT_REPORT = REPORTS / "best_cover_prompt_report.md"
CATEGORY_RESOLVER_REPORT = REPORTS / "kwork_category_resolver_report.md"
SUBCATEGORY_RESOLVER_REPORT = REPORTS / "kwork_subcategory_resolver_report.md"
MY_KWORKS_AUDIT_JSON = STUDIO_DIR / "my_kworks_audit.json"
MY_KWORKS_AUDIT_REPORT = REPORTS / "my_kworks_audit_report.md"
LAUNCH_READINESS_REPORT = REPORTS / "kwork_launch_readiness_report.md"
TODAY_ACTION_PACK_REPORT = REPORTS / "today_money_action_pack.md"


FINAL_BUTTONS = [
    "Сохранить профиль",
    "Сохранить",
    "Опубликовать",
    "На модерацию",
    "Отправить",
    "Предложить услугу",
    "Принять заказ",
    "Подтвердить",
    "Удалить",
    "Настроить вывод",
    "Привязать телефон",
]

ALLOWED_NEXT_LABELS = ["Далее", "Продолжить", "Следующий шаг"]


@dataclass(frozen=True)
class StudioPaths:
    studio_dir: Path = STUDIO_DIR
    covers_dir: Path = COVERS_DIR
    spec_json: Path = SPEC_JSON
    spec_md: Path = SPEC_MD
    competitors_json: Path = COMPETITORS_JSON
    cover_prompts: Path = COVER_PROMPTS
    cover_scores: Path = COVER_SCORES
    selected_cover: Path = SELECTED_COVER


def ensure_studio_dirs() -> None:
    ensure_dir(STUDIO_DIR)
    ensure_dir(COVERS_DIR)
    ensure_dir(REPORTS)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return {} if fallback is None else fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_first_kwork_spec() -> dict[str, Any]:
    return {
        "generated_at": now(),
        "selected_positioning": "Telegram-бот для заявок + Google Таблица + DevOps-запуск",
        "why_selected": [
            "Понятный результат для малого бизнеса: заявки приходят в Telegram и таблицу.",
            "Реалистично выполнить новому аккаунту без фейкового опыта.",
            "DevOps-усиление повышает доверие: .env, инструкция, Docker/Linux в старшем пакете.",
            "Не требует серых схем, капчи, спама, массовых регистраций или доступа к платежам.",
        ],
        "title": "Сделаю Telegram-бота для заявок с Google Таблицей и мини-админкой",
        "short_hook": "Бот принимает заявки, пишет их в Google Таблицу и передаётся с понятной инструкцией запуска.",
        "category": "Разработка и IT",
        "subcategory": "Чат-боты / Telegram-боты",
        "description": (
            "Сделаю аккуратного Telegram-бота для приёма заявок: пользователь отвечает на вопросы, "
            "администратор получает уведомление, а данные сохраняются в Google Таблицу. "
            "В проекте будет понятная структура, .env.example без секретов, инструкция запуска и проверочный сценарий.\n\n"
            "DevOps-часть: объясню запуск через polling или webhook, подготовлю переменные окружения, "
            "добавлю базовое логирование ошибок. В расширенном пакете можно подготовить Docker/Linux запуск на VPS.\n\n"
            "Не делаю спам-рассылки, обходы ограничений, капчи, массовые регистрации, сложные CRM и платежи в рамках этого кворка."
        ),
        "packages": {
            "basic": {
                "name": "Бот + Google Таблица",
                "price": 3000,
                "days": 3,
                "includes": [
                    "сценарий заявки до 4 полей",
                    "уведомление администратору",
                    "запись в Google Таблицу",
                    ".env.example без секретов",
                    "короткая инструкция проверки",
                ],
            },
            "standard": {
                "name": "Бот + таблица + запуск",
                "price": 5500,
                "days": 4,
                "includes": [
                    "сценарий до 6 полей",
                    "кнопки и понятные сообщения",
                    "Google Sheets интеграция",
                    "инструкция запуска polling/webhook",
                    "проверочная тестовая заявка",
                ],
            },
            "premium": {
                "name": "Бот + Docker/Linux deploy",
                "price": 9000,
                "days": 7,
                "includes": [
                    "расширенный сценарий заявок",
                    "Dockerfile или docker-compose",
                    "базовая настройка Linux/VPS",
                    "логирование ошибок",
                    "финальный отчёт и чеклист запуска",
                ],
            },
        },
        "faq": [
            {"q": "Что нужно для старта?", "a": "Сценарий заявки, список полей, Telegram bot token после заказа и доступ к Google Таблице."},
            {"q": "Можно ли без деплоя?", "a": "Да, в Basic можно получить код, таблицу и инструкцию для ручного запуска."},
            {"q": "Делаете рассылки?", "a": "Нет. Кворк про приём заявок и уведомления, не про спам или массовые сообщения."},
            {"q": "Можно Docker?", "a": "Да, Docker/Linux запуск входит в Premium или обсуждается отдельным этапом."},
        ],
        "buyer_questions": [
            "Какие поля должна собирать заявка?",
            "Кому отправлять уведомления в Telegram?",
            "Нужна ли Google Таблица или достаточно уведомления администратору?",
            "Нужен запуск на вашем VPS/Linux или достаточно инструкции?",
            "Каким сообщением бот должен отвечать после заявки?",
        ],
        "tags": ["Telegram bot", "Google Sheets", "Python", "aiogram", "Docker", "Linux", "автоматизация", "бот для заявок"],
        "portfolio_block": "Демо-кейс: Telegram-бот для заявок с записью в Google Таблицу и понятной структурой проекта.",
        "forbidden_phrases": [
            "100% гарантия продаж",
            "обход блокировок",
            "массовая рассылка",
            "накрутка",
            "любой функционал за час",
        ],
        "do_not_promise": [
            "сложную CRM в базовом пакете",
            "платежи без отдельного согласования",
            "обход ограничений Telegram/Kwork/Google",
            "хранение приватных данных без процесса",
        ],
    }


def markdown_for_spec(spec: dict[str, Any]) -> str:
    packages = spec.get("packages", {})
    lines = [
        "# First Kwork Production Spec",
        "",
        f"- title: `{spec.get('title')}`",
        f"- category: `{spec.get('category')}`",
        f"- subcategory: `{spec.get('subcategory')}`",
        f"- selected_positioning: `{spec.get('selected_positioning')}`",
        "",
        "## Short Hook",
        spec.get("short_hook", ""),
        "",
        "## Description",
        spec.get("description", ""),
        "",
        "## Packages",
    ]
    for key, package in packages.items():
        lines.extend(
            [
                f"### {key}: {package.get('name')}",
                f"- price: {package.get('price')} ₽",
                f"- days: {package.get('days')}",
                *(f"- {item}" for item in package.get("includes", [])),
                "",
            ]
        )
    lines.extend(
        [
            "## FAQ",
            *(f"- Q: {item.get('q')} A: {item.get('a')}" for item in spec.get("faq", [])),
            "",
            "## Buyer Questions",
            *(f"- {item}" for item in spec.get("buyer_questions", [])),
            "",
            "## Tags",
            ", ".join(spec.get("tags", [])),
            "",
            "## Safety",
            "- Final save/moderation/publish is manual-only.",
            "- No spam, bypass, captcha, mass registration, or grey automation.",
        ]
    )
    return "\n".join(lines)


def safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:80] or "item"
