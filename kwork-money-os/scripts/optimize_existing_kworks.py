#!/usr/bin/env python3
"""Read-only Kwork offers audit and local optimization drafts."""

from __future__ import annotations

import argparse
from pathlib import Path

from account_optimizer_common import (
    MANAGE_KWORKS_URL,
    add_mode_args,
    append_safety_section,
    build_plan_report,
    extract_cards_from_page,
    load_services,
    parse_mode,
    redact_text,
    require_run_approval,
    stable_id,
    strict_login_gate,
    write_json_output,
    write_markdown,
)
from _common import DATA, REPORTS, slugify
from browser_rpa_bridge import KworkRpaBridge, RpaReport


AUDIT_PATH = REPORTS / "kwork_offers_audit.md"
PLAN_PATH = REPORTS / "kwork_offers_optimization_plan.md"
OPTIMIZED_DIR = DATA / "offers" / "optimized"


def pick_service(summary: str, services: list[dict]) -> dict:
    text = summary.lower()
    scored = []
    for service in services:
        score = 0
        haystack = " ".join(
            [
                str(service.get("name", "")),
                str(service.get("positioning", "")),
                " ".join(str(item) for item in service.get("skills", [])),
            ]
        ).lower()
        for word in ("telegram", "телеграм", "bot", "бот", "docker", "excel", "csv", "api", "ai", "парсер", "sheets"):
            if word in text and word in haystack:
                score += 2
        scored.append((score, service))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else services[0]


def package_from_service(service: dict, key: str) -> dict:
    package = ((service.get("packages") or {}).get(key) or {}).copy()
    return {
        "price_from": package.get("price_from", 2500),
        "days": package.get("days", 2),
        "includes": package.get("includes", []),
    }


def optimized_offer(card: dict, services: list[dict]) -> dict:
    summary = card.get("summary", "")
    service = next((item for item in services if str(item.get("id")) == str(card.get("service_id"))), None)
    if service is None:
        service = pick_service(summary, services)
    service_name = str(service.get("name", "Автоматизация"))
    title = f"{service_name} без лишней воды"
    if len(title) > 70:
        title = title[:67].rstrip() + "..."
    return {
        "source_id": card.get("id"),
        "source_summary_redacted": summary,
        "title": title,
        "short_description": str(service.get("positioning", "Сделаю небольшую рабочую автоматизацию под вашу задачу.")),
        "full_description": (
            f"Сделаю понятный рабочий результат по направлению: {service_name}. "
            "Перед стартом уточняю входные данные, ожидаемый результат и ограничения. "
            "Подходит для маленьких задач: быстрый MVP, исправление одного сценария, простая интеграция или автоматизация."
        ),
        "economy_package": package_from_service(service, "economy"),
        "standard_package": package_from_service(service, "standard"),
        "premium_package": package_from_service(service, "business"),
        "extras": service.get("extras", []),
        "faq": [
            {
                "q": "Что нужно прислать?",
                "a": "Описание задачи, пример данных или ссылку, и критерий готового результата.",
            },
            {
                "q": "Можно сделать срочно?",
                "a": "Да, если задача маленькая и понятная. Сначала уточняю объём.",
            },
        ],
        "buyer_questions": [
            "Что должно получиться в конце работы?",
            "Какие входные данные или доступы уже есть?",
            "Есть ли пример похожего результата?",
            "Какие ограничения важно учесть?",
        ],
        "tags": service.get("skills", [])[:8],
        "price_recommendations": {
            "start": package_from_service(service, "economy").get("price_from", 2500),
            "standard": package_from_service(service, "standard").get("price_from", 5000),
            "premium": package_from_service(service, "business").get("price_from", 9000),
            "note": "Для восстановления рейтинга держать первый пакет маленьким и чётким.",
        },
        "category_recommendations": [
            "Программирование",
            "Чат-боты",
            "Автоматизация",
            "Парсинг и обработка данных",
        ],
        "risk_notes": [
            "Не обещать обходы ограничений, капчи, антибот-защит и массовый спам.",
            "Не брать большой проект без разбиения на маленький первый этап.",
            "Публикация и сохранение остаются ручными.",
        ],
    }


def fallback_cards(services: list[dict]) -> list[dict]:
    def score(service: dict) -> tuple[int, int]:
        risk = str(service.get("risk_level", "medium")).lower()
        risk_score = 3 if risk == "low" else 2 if risk == "medium" else 1
        economy = int(((service.get("packages") or {}).get("economy") or {}).get("price_from", 2500))
        price_score = 3 if economy <= 3500 else 2 if economy <= 6000 else 1
        return (risk_score + price_score, -economy)

    ranked = sorted(services, key=score, reverse=True)[:5]
    return [
        {
            "id": stable_id("fallback", str(service.get("id", service.get("name", index)))),
            "service_id": service.get("id"),
            "summary": f"fallback service: {service.get('name', service.get('id'))}. {service.get('positioning', '')}",
        }
        for index, service in enumerate(ranked)
    ]


def write_audit(mode: str, report: RpaReport, cards: list[dict], optimized_paths: list[Path]) -> None:
    lines = [
        "# Kwork Offers Audit",
        "",
        f"Mode: `{mode}`",
        f"login_detected: `{report.login_detected}`",
        "",
        "## Summary",
        f"- Read-only offer cards detected: `{len(cards)}`",
        "- Финальные действия не выполнялись: публикация, сохранение, удаление и модерация заблокированы.",
        "",
        "## Weaknesses To Check",
        "- Заголовок каждого кворка должен обещать один маленький понятный результат.",
        "- В первом пакете лучше держать низкий риск: 1 файл, 1 бот, 1 страница, 1 интеграция.",
        "- Описание должно заранее отсекать спам, обходы защит, мутные доступы и большие обещания.",
        "",
        "## Offer Cards Redacted",
    ]
    if cards:
        for card in cards:
            lines.extend([f"### {card['id']}", f"- Summary: {redact_text(card['summary'], 360)}"])
    else:
        lines.append("- Кворки не удалось извлечь автоматически; проверь скриншоты и страницу вручную.")
    lines.extend(
        [
            "",
            "## Recommended New/Improved Kworks",
            "- Исправлю одну ошибку в Python, JS, боте или парсере.",
            "- Сделаю простого Telegram-бота для заявок.",
            "- Обработаю один Excel/CSV файл или таблицу.",
            "- Сделаю мини-парсер одной страницы на Python.",
            "- Запущу проект через Docker с инструкцией.",
            "",
            "## Optimized Draft Files",
            *(f"- `{path}`" for path in optimized_paths),
            "",
            "## Screenshots",
            *(f"- `{item}`" for item in report.screenshots),
        ]
    )
    append_safety_section(lines)
    write_markdown(AUDIT_PATH, lines)


def run_optimizer(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    if mode == "dry-run":
        build_plan_report(
            PLAN_PATH,
            "Kwork Offers Optimization Plan",
            mode,
            [
                "Open manage kworks page only in preview/run.",
                "Require login_detected == true.",
                "Read visible offer cards without saving, publishing, deleting, or moderation.",
                "Write reports/kwork_offers_audit.md.",
                "Create data/offers/optimized/*.json only in --run --approve.",
            ],
        )
        print(PLAN_PATH)
        return
    require_run_approval(mode, args.approve, "Kwork offer optimization")
    report = RpaReport(mode=f"kwork-offers:{mode}", target_url=args.url, title="Kwork Offers Audit")
    cards = []
    optimized_paths: list[Path] = []
    with KworkRpaBridge(report) as bridge:
        bridge.open(args.url)
        bridge.wait_and_screenshot("kwork-offers-before")
        bridge.collect_fields()
        if not strict_login_gate(bridge, AUDIT_PATH):
            if args.hold:
                bridge.hold_open()
            print(AUDIT_PATH)
            return
        cards = extract_cards_from_page(bridge, args.max_items)
        if mode == "run":
            services = load_services()
            source_cards = cards or fallback_cards(services)
            for card in source_cards:
                offer = optimized_offer(card, services)
                path = OPTIMIZED_DIR / f"{slugify(offer['title'])}-{card['id']}.json"
                write_json_output(path, offer)
                optimized_paths.append(path)
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        bridge.wait_and_screenshot("kwork-offers-after-readonly")
        write_audit(mode, report, cards, optimized_paths)
        if args.hold:
            bridge.hold_open()
    print(AUDIT_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=MANAGE_KWORKS_URL)
    parser.add_argument("--max-items", type=int, default=20)
    add_mode_args(parser)
    run_optimizer(parser.parse_args())


if __name__ == "__main__":
    main()
