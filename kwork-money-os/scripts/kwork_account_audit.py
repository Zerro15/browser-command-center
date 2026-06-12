#!/usr/bin/env python3
"""Read-only Kwork account audit for profile, offers, and account fit."""

from __future__ import annotations

import argparse
from pathlib import Path

from account_optimizer_common import (
    DRAFT_KWORKS_URL,
    INBOX_URL,
    MANAGE_KWORKS_URL,
    ORDERS_URL,
    PORTFOLIO_URL,
    PROFILE_SETTINGS_URL,
    PROJECTS_URL,
    SELLER_PROFILE_URL,
    add_mode_args,
    append_safety_section,
    build_plan_report,
    load_services,
    parse_mode,
    safe_page_snapshot,
    strict_login_gate,
    write_markdown,
)
from _common import REPORTS
from browser_rpa_bridge import KWORK_HOME_URL, KworkRpaBridge, RpaReport


ACCOUNT_AUDIT_PATH = REPORTS / "account_audit.md"


SAFE_PAGES = [
    ("seller_profile", SELLER_PROFILE_URL, False),
    ("profile_settings", PROFILE_SETTINGS_URL, False),
    ("kwork_list", MANAGE_KWORKS_URL, False),
    ("kwork_drafts", DRAFT_KWORKS_URL, False),
    ("portfolio", PORTFOLIO_URL, False),
    ("inbox_read_only", INBOX_URL, True),
    ("projects_read_only", PROJECTS_URL, True),
    ("orders_read_only", ORDERS_URL, True),
]


def list_names(services: list[dict]) -> list[str]:
    return [str(item.get("name") or item.get("id")) for item in services]


def recommended_services(services: list[dict]) -> list[dict]:
    low_risk = [item for item in services if str(item.get("risk_level", "")).lower() == "low"]
    return (low_risk or services)[:5]


def price_line(service: dict) -> str:
    packages = service.get("packages") or {}
    economy = packages.get("economy") or {}
    standard = packages.get("standard") or {}
    return (
        f"{service.get('name', service.get('id'))}: старт {economy.get('price_from', '1500')} руб., "
        f"стандарт {standard.get('price_from', '3000')} руб."
    )


def build_audit_lines(mode: str, report: RpaReport, snapshots: list, services: list[dict]) -> list[str]:
    profile = next((item for item in snapshots if item.name == "profile_settings"), None)
    offers = next((item for item in snapshots if item.name == "kwork_list"), None)
    portfolio = next((item for item in snapshots if item.name == "portfolio"), None)
    recs = recommended_services(services)
    profile_fields = profile.fields if profile else []
    offer_text = (offers.text_summary if offers else "").lower()
    portfolio_text = (portfolio.text_summary if portfolio else "").lower()

    empty_fields = []
    if not any("о себе" in item.lower() or "description" in item.lower() for item in profile_fields):
        empty_fields.append("Не найдено явное поле/раздел `О себе` в настройках профиля.")
    if not any("навы" in item.lower() or "skill" in item.lower() for item in profile_fields):
        empty_fields.append("Не найдено явное поле навыков; нужно проверить вручную в браузере.")
    if "портфолио" not in portfolio_text and portfolio:
        empty_fields.append("Портфолио выглядит слабым или пустым по видимому тексту страницы.")

    weak_kworks = []
    if "telegram" not in offer_text.lower() and "телеграм" not in offer_text.lower():
        weak_kworks.append("Добавить или усилить кворк про простого Telegram-бота для заявок.")
    if "excel" not in offer_text.lower() and "csv" not in offer_text.lower():
        weak_kworks.append("Добавить маленький кворк по Excel/CSV или обработке таблиц.")
    if "docker" not in offer_text.lower():
        weak_kworks.append("Добавить понятный кворк по запуску проекта через Docker.")
    if not weak_kworks:
        weak_kworks.append("Кворки есть в нужных направлениях; слабые места надо проверять по заголовкам, ценам и первому экрану.")

    lines = [
        "# Kwork Account Audit",
        "",
        f"Mode: `{mode}`",
        f"login_detected: `{report.login_detected}`",
        f"current_url: `{report.current_url or 'unknown'}`",
        "",
        "## Что сейчас хорошо",
        "- Уже есть техническое позиционирование вокруг Python, Telegram, интеграций и автоматизации.",
        "- Направления услуг подходят для маленьких заказов, где новичку проще получить первые отзывы.",
        "- Есть локальная система черновиков и безопасный browser RPA bridge без автопубликации.",
        "",
        "## Что сейчас плохо в профиле",
        "- Профиль должен быстрее объяснять покупателю результат: что будет готово, за сколько и что нужно от клиента.",
        "- Нужны короткие доверительные блоки без завышенного опыта: стек, формат работы, ограничения и честные сроки.",
        "- Нужно убрать расплывчатость и продавать простую рабочую автоматизацию для бизнеса без лишней воды.",
        "",
        "## Какие поля пустые или требуют ручной проверки",
        *(f"- {item}" for item in (empty_fields or ["Критичных пустых полей по видимой странице не обнаружено; проверь скриншоты вручную."])),
        "",
        "## Что надо переписать",
        "- Заголовок профиля: сделать конкретным, например `Python, Telegram-боты и простая автоматизация бизнеса`.",
        "- Описание: первые 2-3 строки должны продавать понятный результат, а не общий список технологий.",
        "- FAQ и инструкции: добавить входные данные, формат результата, границы работ и что не делается.",
        "",
        "## Какие кворки слабые",
        *(f"- {item}" for item in weak_kworks),
        "",
        "## Какие кворки стоит создать",
        *(f"- {item.get('name', item.get('id'))}: {item.get('positioning', '')}" for item in recs),
        "",
        "## Какие услуги лучше продавать новичку",
        "- Исправление одной ошибки в Python/JS/боте.",
        "- Простой Telegram-бот для заявок.",
        "- Обработка одного Excel/CSV файла.",
        "- Мини-парсер одной страницы.",
        "- Google Sheets уведомление или простая интеграция.",
        "",
        "## Рекомендованные стартовые цены",
        *(f"- {price_line(item)}" for item in recs),
        "",
        "## Лучшие ниши",
        "- Малый бизнес и локальные услуги, которым нужен быстрый бот или уведомления.",
        "- Эксперты и онлайн-школы, которым нужна заявка, таблица или простой AI-ассистент.",
        "- Владельцы небольших проектов, которым нужен Docker-запуск или короткая диагностика.",
        "",
        "## Действия в первую очередь",
        "- Сгенерировать `data/profile/profile_optimized.json` и вручную проверить текст.",
        "- Улучшить 2-3 recovery-кворка с минимальным риском и понятным результатом.",
        "- Подготовить короткие шаблоны ответов для сообщений и заявок.",
        "- Каждый день проверять входящие, отвечать быстро и не брать задачи с мутным ТЗ.",
        "",
        "## Страницы проверены",
    ]
    for snapshot in snapshots:
        summary = "client/private content intentionally not copied" if snapshot.name.endswith("read_only") else snapshot.text_summary
        lines.extend(
            [
                f"### {snapshot.name}",
                f"- URL: `{snapshot.url}`",
                f"- Title: `{snapshot.title or 'unknown'}`",
                f"- Summary: {summary or 'empty/unknown'}",
                *(f"- Warning: {warning}" for warning in snapshot.warnings),
            ]
        )
    lines.extend(["", "## Screenshots", *(f"- `{item}`" for item in report.screenshots)])
    append_safety_section(lines)
    return lines


def run_audit(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    if mode == "dry-run":
        build_plan_report(
            ACCOUNT_AUDIT_PATH,
            "Kwork Account Audit",
            mode,
            [
                "Open visible Chromium with kwork-money-os/.browser-profile only in preview/run.",
                "Require login_detected == true before inspection.",
                "Visit profile, settings, kwork list, drafts, portfolio, inbox/projects/orders read-only.",
                "Write reports/account_audit.md with redacted summaries.",
            ],
        )
        print(ACCOUNT_AUDIT_PATH)
        return

    report = RpaReport(mode=f"account-audit:{mode}", target_url=KWORK_HOME_URL, title="Kwork Account Audit")
    snapshots = []
    with KworkRpaBridge(report) as bridge:
        bridge.open(KWORK_HOME_URL)
        if not strict_login_gate(bridge, ACCOUNT_AUDIT_PATH):
            if args.hold:
                bridge.hold_open()
            print(ACCOUNT_AUDIT_PATH)
            return
        for name, url, private_page in SAFE_PAGES:
            snapshot = safe_page_snapshot(bridge, name, url)
            if private_page:
                snapshot.text_summary = "read-only private page checked; full client text intentionally not copied"
            snapshots.append(snapshot)
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        lines = build_audit_lines(mode, report, snapshots, load_services())
        write_markdown(ACCOUNT_AUDIT_PATH, lines)
        if args.hold:
            bridge.hold_open()
    print(ACCOUNT_AUDIT_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    add_mode_args(parser)
    run_audit(parser.parse_args())


if __name__ == "__main__":
    main()
