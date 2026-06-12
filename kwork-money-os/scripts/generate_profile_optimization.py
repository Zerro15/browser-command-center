#!/usr/bin/env python3
"""Generate buyer-friendly Kwork profile optimization JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from account_optimizer_common import (
    add_mode_args,
    build_plan_report,
    load_services,
    parse_mode,
    read_text,
    require_run_approval,
    write_json_output,
)
from _common import DATA, REPORTS


ACCOUNT_AUDIT_PATH = REPORTS / "account_audit.md"
PROFILE_OUTPUT_PATH = DATA / "profile" / "profile_optimized.json"
PLAN_PATH = REPORTS / "profile_optimization_plan.md"


def service_names(services: list[dict]) -> list[str]:
    return [str(item.get("name") or item.get("id")) for item in services]


def collect_skills(services: list[dict]) -> list[str]:
    preferred = [
        "Python",
        "Telegram Bot API",
        "Google Sheets",
        "Docker",
        "Docker Compose",
        "OpenAI API",
        "API/webhook",
        "парсеры",
        "быстрый MVP",
    ]
    seen = set()
    for service in services:
        for skill in service.get("skills", []):
            seen.add(str(skill))
    result = []
    for item in preferred:
        if item in seen or item in {"Google Sheets", "API/webhook", "парсеры", "быстрый MVP"}:
            result.append(item)
    return result


def build_profile(audit_text: str, services: list[dict]) -> dict:
    names = service_names(services)
    skills = collect_skills(services)
    return {
        "display_name_suggestion": "ZerroOne",
        "headline": "Python, Telegram-боты и простая автоматизация для бизнеса",
        "about": (
            "Сделаю простую рабочую автоматизацию для бизнеса без лишней воды: Telegram-бота для заявок, "
            "мини-парсер, обработку Excel/CSV, уведомления из Google Sheets, AI-ассистента или запуск проекта "
            "через Docker. Перед стартом уточняю задачу, входные данные и ожидаемый результат, чтобы не обещать "
            "лишнего и быстро довести маленькую задачу до рабочего состояния."
        ),
        "skills": skills,
        "short_pitch": "Быстро собираю небольшие Python/Telegram/AI-автоматизации с понятным результатом и инструкцией.",
        "long_pitch": (
            "Подхожу для задач, где нужен небольшой, но рабочий инструмент: бот принимает заявки, таблица получает "
            "уведомления, парсер собирает данные с одной страницы, проект запускается через Docker, AI-ассистент "
            "отвечает в одном понятном сценарии. Я заранее уточняю ограничения, не беру серые задачи, не обещаю "
            "обходы капчи, спам или сбор приватных данных."
        ),
        "trust_blocks": [
            "Сначала уточняю входные данные, результат и доступы.",
            "Делаю маленькими проверяемыми шагами: демо, скриншоты, инструкция запуска.",
            "Честно говорю, если задача слишком большая или рискованная для короткого кворка.",
            "Не беру спам, взлом, обход защит и работу с приватными данными без явного согласования.",
        ],
        "faq": [
            {
                "q": "Что нужно для старта?",
                "a": "Коротко опишите задачу, пришлите пример данных или ссылку, и напишите, какой результат хотите получить.",
            },
            {
                "q": "Вы делаете большие CRM и сложные платформы?",
                "a": "Для стартового кворка беру маленький понятный модуль. Большие задачи сначала разбиваем на этапы.",
            },
            {
                "q": "Можно подключить Telegram, Google Sheets или API?",
                "a": "Да, если есть понятный сценарий и доступы. Токены и пароли лучше передавать только после заказа.",
            },
            {
                "q": "Что не делаете?",
                "a": "Не делаю спам, взлом, обход капчи, массовый сбор приватных данных и нарушения правил сервисов.",
            },
        ],
        "portfolio_ideas": [
            "Скриншот Telegram-бота для заявок: пользователь -> администратор.",
            "Пример Google Sheets уведомления: новая строка -> сообщение в Telegram.",
            "Мини-парсер одной страницы с CSV-результатом.",
            "Docker compose запуск маленького проекта одной командой.",
            "AI-бот с одним безопасным бизнес-сценарием и ограничениями.",
        ],
        "buyer_friendly_description": (
            "Если нужна небольшая автоматизация, напишите задачу простыми словами. Я помогу выбрать самый короткий "
            "и безопасный путь: что сделать в первом шаге, сколько это займёт и какие данные нужны."
        ),
        "warnings": [
            "Не писать про 10 лет опыта или крупные команды, если это нельзя подтвердить.",
            "Не обещать рост продаж, обход антибот-защит, парсинг закрытых данных или массовые рассылки.",
            "Не брать заказ без уточнения входных данных, результата и способа проверки.",
            "Текущий аудит использован как источник контекста, но финальный текст нужно проверить руками на странице профиля.",
        ],
        "source_context": {
            "audit_present": bool(audit_text.strip()),
            "services_used": names,
        },
    }


def run_generator(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    audit_path = Path(args.audit)
    output_path = Path(args.output)
    if mode in {"dry-run", "preview"}:
        build_plan_report(
            PLAN_PATH,
            "Kwork Profile Optimization Plan",
            mode,
            [
                f"Read audit from {audit_path}.",
                "Read services/*.yaml.",
                f"Create optimized profile JSON at {output_path} only in --run --approve.",
            ],
        )
        print(PLAN_PATH)
        return
    require_run_approval(mode, args.approve, "Profile optimization generation")
    profile = build_profile(read_text(audit_path), load_services())
    write_json_output(output_path, profile)
    print(output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default=str(ACCOUNT_AUDIT_PATH))
    parser.add_argument("--output", default=str(PROFILE_OUTPUT_PATH))
    add_mode_args(parser)
    run_generator(parser.parse_args())


if __name__ == "__main__":
    main()
