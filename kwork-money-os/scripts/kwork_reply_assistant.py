#!/usr/bin/env python3
"""Read-only Kwork reply assistant that prepares local reply drafts."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

from account_optimizer_common import (
    INBOX_URL,
    ORDERS_URL,
    PROJECTS_URL,
    add_mode_args,
    append_safety_section,
    build_plan_report,
    load_services,
    parse_mode,
    require_run_approval,
    stable_id,
    strict_login_gate,
    write_json_output,
    write_markdown,
)
from _common import DATA, REPORTS
from browser_rpa_bridge import KworkRpaBridge, RpaReport


REPORT_PATH = REPORTS / "reply_drafts.md"
JSON_PATH = DATA / "replies" / "reply_drafts.json"
PLAN_PATH = REPORTS / "reply_assistant_plan.md"


SOURCE_URLS = {
    "inbox": INBOX_URL,
    "projects": PROJECTS_URL,
    "orders": ORDERS_URL,
}


KEYWORDS = {
    "telegram": ["telegram", "телеграм", "бот", "заявк"],
    "sheets": ["google sheets", "таблиц", "excel", "csv", "лист"],
    "parser": ["парсер", "парсинг", "собрать", "данные"],
    "docker": ["docker", "докер", "сервер", "деплой", "запуск"],
    "ai": ["ai", "ии", "gpt", "openai", "нейрон"],
    "api": ["api", "webhook", "интеграц", "crm"],
}


def collect_visible_items(bridge: KworkRpaBridge, max_items: int) -> list[dict[str, str]]:
    if not bridge.available:
        return []
    try:
        raw = bridge.page.evaluate(
            """(maxItems) => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              return Array.from(document.querySelectorAll('article, .card, .conversation, .project-card, .order-card, li, tr'))
                .filter(visible)
                .map((el) => {
                  const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                  const link = el.querySelector('a[href]');
                  return {text, href: link ? link.href : location.href};
                })
                .filter((item) => item.text.length > 20)
                .slice(0, maxItems);
            }""",
            max_items,
        )
    except Exception:
        return []
    items = []
    for item in raw:
        text = str(item.get("text", ""))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        items.append({"id": stable_id("draft", digest), "text": text, "url": str(item.get("href") or "")})
    return items


def detect_need(text: str) -> str:
    lower = text.lower()
    matches = []
    for name, words in KEYWORDS.items():
        if any(word in lower for word in words):
            matches.append(name)
    return ", ".join(matches) if matches else "unclear"


def pick_service(need: str, services: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not services:
        return None
    lower = need.lower()
    for service in services:
        haystack = " ".join(
            [
                str(service.get("id", "")),
                str(service.get("name", "")),
                str(service.get("positioning", "")),
                " ".join(str(item) for item in service.get("skills", [])),
            ]
        ).lower()
        if any(part and part in haystack for part in lower.split(", ")):
            return service
    return services[0]


def complexity(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["срочно", "crm", "платеж", "личный кабинет", "много", "сложно", "интеграций"]):
        return "high"
    if any(word in lower for word in ["api", "webhook", "docker", "деплой", "таблиц", "парсер"]):
        return "medium"
    return "low"


def price_range(service: dict[str, Any] | None, level: str) -> str:
    if not service:
        return "1500-3000 руб. после уточнения"
    packages = service.get("packages") or {}
    economy = (packages.get("economy") or {}).get("price_from", 1500)
    standard = (packages.get("standard") or {}).get("price_from", max(int(economy) * 2, 3000))
    business = (packages.get("business") or {}).get("price_from", max(int(standard) * 2, 7000))
    if level == "low":
        return f"{economy}-{standard} руб."
    if level == "medium":
        return f"{standard}-{business} руб."
    return f"от {business} руб., лучше разбить на этапы"


def build_reply(item: dict[str, str], services: list[dict[str, Any]]) -> dict[str, Any]:
    text = item["text"]
    need = detect_need(text)
    service = pick_service(need, services)
    level = complexity(text)
    should_reply = "no" if need == "unclear" and level == "high" else "yes"
    service_name = service.get("name", "небольшая автоматизация") if service else "небольшая автоматизация"
    questions = [
        "Какой результат должен получиться в конце?",
        "Есть ли пример данных, ссылка или скриншот текущего процесса?",
        "Какие доступы или токены уже готовы, и можно ли сначала сделать маленький тестовый этап?",
    ]
    reply = (
        "Здравствуйте. Могу помочь, если задача сводится к небольшому понятному результату. "
        f"По описанию похоже на: {service_name}. "
        "Чтобы точно оценить, напишите, пожалуйста: что должно работать в конце, какие входные данные есть, "
        "и есть ли пример похожего результата. После этого предложу короткий первый этап и цену."
    )
    return {
        "id": item["id"],
        "dialog_url": item.get("url", ""),
        "client_summary_redacted": f"Найдены признаки темы: {need}. Полный текст клиента не сохранялся.",
        "detected_need": need,
        "recommended_service": service_name,
        "complexity": level,
        "suggested_price_range": price_range(service, level),
        "questions_to_ask": questions,
        "reply_draft": reply,
        "upsell_opportunity": "После маленького первого этапа предложить деплой, инструкцию или интеграцию с таблицей/API.",
        "should_reply": should_reply,
        "reason": "Подходит для короткого уточняющего ответа без спама." if should_reply == "yes" else "Слишком мутно или рискованно без дополнительных деталей.",
        "source_fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def write_drafts_report(mode: str, report: RpaReport, drafts: list[dict[str, Any]]) -> None:
    lines = [
        "# Kwork Reply Drafts",
        "",
        f"Mode: `{mode}`",
        f"login_detected: `{report.login_detected}`",
        "",
        "## Drafts",
    ]
    if not drafts:
        lines.append("- Подходящие диалоги/заявки не найдены или страница не дала карточки для анализа.")
    for draft in drafts:
        lines.extend(
            [
                f"### {draft['id']}",
                f"- client_summary_redacted: {draft['client_summary_redacted']}",
                f"- detected_need: {draft['detected_need']}",
                f"- recommended_service: {draft['recommended_service']}",
                f"- complexity: {draft['complexity']}",
                f"- suggested_price_range: {draft['suggested_price_range']}",
                f"- questions_to_ask: {'; '.join(draft['questions_to_ask'])}",
                f"- reply_draft: {draft['reply_draft']}",
                f"- upsell_opportunity: {draft['upsell_opportunity']}",
                f"- should_reply: {draft['should_reply']}",
                f"- reason: {draft['reason']}",
                f"- dialog_url: `{draft['dialog_url']}`",
            ]
        )
    lines.extend(["", "## Screenshots", *(f"- `{item}`" for item in report.screenshots)])
    append_safety_section(lines)
    write_markdown(REPORT_PATH, lines)


def run_assistant(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    if mode == "dry-run":
        build_plan_report(
            PLAN_PATH,
            "Kwork Reply Assistant Plan",
            mode,
            [
                "Open selected read-only message/request pages only in preview/run.",
                "Require login_detected == true.",
                "Prepare local reply drafts in reports/reply_drafts.md and data/replies/reply_drafts.json.",
                "Never click Send or mass-reply controls.",
            ],
        )
        print(PLAN_PATH)
        return
    require_run_approval(mode, args.approve, "Kwork reply assistant run")
    urls = SOURCE_URLS if args.source == "all" else {args.source: SOURCE_URLS[args.source]}
    report = RpaReport(mode=f"reply-assistant:{mode}", target_url=", ".join(urls.values()), title="Kwork Reply Assistant")
    drafts: list[dict[str, Any]] = []
    services = load_services()
    with KworkRpaBridge(report) as bridge:
        bridge.open(INBOX_URL)
        if not strict_login_gate(bridge, REPORT_PATH):
            if args.hold:
                bridge.hold_open()
            print(REPORT_PATH)
            return
        for name, url in urls.items():
            bridge.open(url)
            bridge.wait_and_screenshot(f"reply-assistant-{name}")
            items = collect_visible_items(bridge, args.max_items)
            for item in items:
                drafts.append(build_reply(item, services))
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        write_json_output(JSON_PATH, {"drafts": drafts})
        write_drafts_report(mode, report, drafts)
        if args.hold:
            bridge.hold_open()
    print(REPORT_PATH)
    print(JSON_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["inbox", "projects", "orders", "all"], default="all")
    parser.add_argument("--max-items", type=int, default=10)
    add_mode_args(parser)
    run_assistant(parser.parse_args())


if __name__ == "__main__":
    main()
