#!/usr/bin/env python3
"""Offline/read-only Kwork profile audit report skeleton.

This runner does not open a browser and does not touch Kwork. It documents the
audit contract and summarizes any already-saved local kwork audit data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from kwork_studio_common import FINAL_BUTTONS, read_json, rel, write_text


REPORT_PATH = REPORTS / "kwork_profile_audit_report.md"
LIVE_SNAPSHOT_JSON = DATA / "kwork_profile_audit" / "live_kworks_snapshot.json"
LIVE_REPORT = REPORTS / "kwork_profile_audit_live_report.md"
LOCAL_MY_KWORKS_JSON = DATA / "kwork_studio" / "my_kworks_audit.json"
LOCAL_MY_KWORKS_REPORT = REPORTS / "my_kworks_audit_report.md"
MARKETING_QA_REPORT = REPORTS / "kwork_marketing_qa_report.md"
LAUNCH_READINESS_REPORT = REPORTS / "kwork_launch_readiness_report.md"


@dataclass(frozen=True)
class AuditDimensions:
    title: str = "title"
    category: str = "category"
    subcategory: str = "subcategory"
    status: str = "status"
    cover: str = "cover"
    description: str = "description"
    price: str = "price"
    delivery_time: str = "delivery_time"
    extras: str = "extras"
    faq: str = "faq"
    buyer_questions: str = "buyer_questions"


def existing_report_summary(path: Path) -> str:
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.startswith("- verdict:") or line.startswith("- score:")]
    return "; ".join(lines[:4]) or f"exists, {len(text)} chars"


def score_local_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "")
    text = "\n".join([title, str(item.get("text") or "")]).lower()
    cover_present = bool(item.get("cover_present"))
    price_present = bool(item.get("price"))
    has_specific_result = any(word in text for word in ["заяв", "таблиц", "google", "telegram", "бот", "python"])
    has_trust = any(word in text for word in ["инструкц", "деплой", "docker", "linux", ".env", "провер"])
    has_risk = any(word in text for word in ["спам", "обход", "капч", "взлом", "накрут"])

    title_score = 90 if 25 <= len(title) <= 90 else 45
    cover_score = 85 if cover_present else 25
    description_score = 82 if has_specific_result else 45
    price_score = 80 if price_present else 40
    trust_score = 85 if has_trust else 50
    safety_score = 90 if not has_risk else 10
    status_score = 75 if item.get("status") else 40
    score = round(
        title_score * 0.18
        + cover_score * 0.16
        + description_score * 0.18
        + price_score * 0.12
        + trust_score * 0.16
        + safety_score * 0.14
        + status_score * 0.06
    )

    blockers = []
    if not title:
        blockers.append("missing title")
    if not cover_present:
        blockers.append("missing cover")
    if not has_specific_result:
        blockers.append("unclear buyer outcome")
    if has_risk:
        blockers.append("unsafe/risky wording")

    verdict = "READY_FOR_MANUAL_REVIEW"
    if has_risk:
        verdict = "MUST_FIX_BEFORE_PUBLICATION"
    elif blockers:
        verdict = "NEEDS_IMPROVEMENT"

    return {
        "score": min(score, 100),
        "title_score": title_score,
        "cover_score": cover_score,
        "description_score": description_score,
        "price_score": price_score,
        "trust_score": trust_score,
        "devops_fit_score": trust_score,
        "verdict": verdict,
        "good": [
            "Есть конкретный buyer outcome." if has_specific_result else "Можно усилить конкретику результата.",
            "Обложка найдена." if cover_present else "Обложка не найдена в локальном снимке.",
            "Есть блок доверия/запуска." if has_trust else "Нужно добавить доверие: инструкция, запуск, ограничения.",
        ],
        "blockers": blockers or ["major blockers not detected in local snapshot"],
        "replace_texts": {
            "title": "Сделаю Telegram-бота для заявок с Google Таблицей и запуском",
            "description": "Усилить первый экран: результат, стек, что получает клиент, что нужно от клиента, ограничения.",
            "buyer_questions": "Добавить 3-5 вопросов про сценарий заявки, Google Таблицу, доступы/API, запуск и критерии готовности.",
            "faq": "Добавить FAQ про сроки, доступы, деплой, поддержку и безопасные ограничения.",
        },
        "extras": [
            "Docker/Linux запуск на VPS",
            "Расширенный сценарий заявки",
            "Логирование и инструкция диагностики",
        ],
        "cover_improvement": "Крупный результат в 3-5 слов, схема чат -> таблица -> сервер, без мелкого текста и серых обещаний.",
        "recommended_price": "3000-9000 ₽ depending on scope",
        "recommended_deadline": "3-7 дней",
        "next_similar_kwork": "Автоматизация Google Таблицы / CSV-отчёта на Python",
    }


def load_local_items() -> list[dict[str, Any]]:
    live_payload = read_json(LIVE_SNAPSHOT_JSON, {})
    live_items = live_payload.get("kworks") if isinstance(live_payload, dict) else []
    if live_items:
        return [item for item in live_items if isinstance(item, dict)]
    payload = read_json(LOCAL_MY_KWORKS_JSON, {})
    items = payload.get("kworks") if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)]


def build_report() -> str:
    ensure_dir(REPORTS)
    dimensions = AuditDimensions()
    local_items = load_local_items()
    lines: list[str] = [
        "# Kwork Profile Audit Report",
        "",
        f"- project_root: `{ROOT}`",
        "- mode: `offline_read_only_skeleton`",
        "- browser_opened: `false`",
        "- kwork_state_changed: `false`",
        "- final_buttons_clicked: `false`",
        f"- output: `{rel(REPORT_PATH)}`",
        "",
        "## Data Collection Status",
        "",
        f"- local_my_kworks_json: `{rel(LOCAL_MY_KWORKS_JSON)}`",
        f"- live_snapshot_json: `{rel(LIVE_SNAPSHOT_JSON)}`",
        f"- live_snapshot_exists: `{str(LIVE_SNAPSHOT_JSON.exists()).lower()}`",
        f"- live_report_exists: `{str(LIVE_REPORT.exists()).lower()}`",
        f"- local_my_kworks_json_exists: `{str(LOCAL_MY_KWORKS_JSON.exists()).lower()}`",
        f"- local_my_kworks_report_exists: `{str(LOCAL_MY_KWORKS_REPORT.exists()).lower()}`",
        f"- local_items_loaded: `{len(local_items)}`",
        f"- launch_readiness_summary: `{existing_report_summary(LAUNCH_READINESS_REPORT)}`",
        f"- marketing_qa_summary: `{existing_report_summary(MARKETING_QA_REPORT)}`",
        "",
        "This skeleton does not collect live Kwork data yet. Live collection should be implemented as a separate read-only CDP step guarded by Account Guard, with no save/publish/send/moderation clicks.",
        "",
        "## Audit Dimensions",
        "",
    ]
    for value in dimensions.__dict__.values():
        lines.append(f"- `{value}`")

    lines.extend(
        [
            "",
            "## Scoring Contract",
            "",
            "- score_range: `0-100`",
            "- good: what is already strong enough for buyer trust",
            "- sales_blockers: what reduces conversion or moderation safety",
            "- must_fix_before_publication: required edits before manual save/moderation",
            "- replacement_texts: improved title, description, buyer questions, FAQ",
            "- extras: safe paid add-ons to increase order value",
            "- cover_improvements: concrete visual direction for manual cover work",
            "- price_and_deadline: realistic recommendation for a new account",
            "- next_similar_kwork: one adjacent offer to create next",
            "",
            "## Local Kwork Snapshots",
            "",
        ]
    )

    if not local_items:
        lines.extend(
            [
                "- status: `NO_LOCAL_KWORK_SNAPSHOTS`",
                "- todo: run a future read-only collector that opens `manage_kworks`, extracts visible kwork cards/forms, and writes local JSON for this offline auditor.",
                "- fallback: use `reports/kwork_launch_readiness_report.md` and `reports/kwork_marketing_qa_report.md` for the current first-kwork readiness.",
                "",
            ]
        )
    else:
        for index, item in enumerate(local_items, start=1):
            scored = score_local_item(item)
            lines.extend(
                [
                    f"### {index}. {item.get('title') or 'Untitled'}",
                    "",
                    f"- status: `{item.get('status', 'unknown')}`",
                    f"- url: `{item.get('url', '')}`",
                    f"- price: `{item.get('price') or 'unknown'}`",
                    f"- cover_present: `{str(bool(item.get('cover_present'))).lower()}`",
                    f"- score: `{scored['score']}`",
                    f"- verdict: `{scored['verdict']}`",
                    "",
                    "#### What Is Good",
                    *(f"- {line}" for line in scored["good"]),
                    "",
                    "#### What Blocks Sales",
                    *(f"- {line}" for line in scored["blockers"]),
                    "",
                    "#### Texts To Replace",
                    *(f"- {key}: {value}" for key, value in scored["replace_texts"].items()),
                    "",
                    "#### Extras To Add",
                    *(f"- {line}" for line in scored["extras"]),
                    "",
                    f"#### Cover Improvement\n\n- {scored['cover_improvement']}",
                    "",
                    f"#### Price And Deadline\n\n- price: `{scored['recommended_price']}`\n- deadline: `{scored['recommended_deadline']}`",
                    "",
                    f"#### Next Similar Kwork\n\n- {scored['next_similar_kwork']}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Dangerous Actions Blocked",
            "",
            *(f"- `{button}`" for button in FINAL_BUTTONS),
            "- `Отправить сообщение`",
            "- `Отменить заказ`",
            "- `phone/SMS/withdrawal/account switching`",
            "",
            "## Safety",
            "",
            "- This command is offline/read-only.",
            "- It does not open Kwork.",
            "- It does not save, publish, moderate, send proposals, send messages, accept orders, change phone/SMS, configure withdrawal, delete, or confirm anything.",
            "- Any live Kwork-changing action remains manual-only and must be performed by the user.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    write_text(REPORT_PATH, report)
    print(REPORT_PATH)
    print("mode=offline_read_only_skeleton")
    print("browser_opened=false")
    print("final_buttons_clicked=false")


if __name__ == "__main__":
    main()
