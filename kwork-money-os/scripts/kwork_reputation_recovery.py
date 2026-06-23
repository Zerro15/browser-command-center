#!/usr/bin/env python3
"""Offline reputation recovery and safe order filter reports.

This module never opens Kwork and never sends messages/proposals. It prepares
manual-only decision reports for a low-reputation recovery phase.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from kwork_studio_common import QUICK_PROPOSALS_REPORT, write_text


KWORKS_JSON = DATA / "kwork_profile_audit" / "all_kworks_list.json"
REPUTATION_REPORT = REPORTS / "reputation_recovery_report.md"
SAFE_ORDER_REPORT = REPORTS / "safe_order_filter_report.md"
CLARIFICATION_TEMPLATES = REPORTS / "client_clarification_templates.md"
KWORK_RISK_AUDIT_REPORT = REPORTS / "kwork_risk_audit_report.md"
TOMORROW_PLAN = REPORTS / "tomorrow_kwork_action_plan.md"

CURRENT_RATING = "≈2.5"
HAS_BAD_REVIEW = True

HARD_BLOCK_PATTERNS = [
    r"капч|captcha",
    r"обход защит|обойти защит|bypass",
    r"спам|рассылк",
    r"массов(ая|ые|о).*регистрац",
    r"накрутк",
    r"закрыт(ые|ых).*данн",
    r"чуж(ие|их).*аккаунт",
    r"срочно.*копе|за копейки",
    r"взлом|ddos|ддос|\bчит(ы|ер|ерство)?\b",
]

SAFE_TOPICS = [
    "minecraft",
    "excel",
    "csv",
    "google sheets",
    "google таблиц",
    "telegram",
    "уведомлен",
    "docker",
    "linux",
]


@dataclass
class Proposal:
    title: str
    price: str
    deadline: str
    risk: str
    text: str
    questions: list[str]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_kworks() -> list[dict[str, Any]]:
    if not KWORKS_JSON.exists():
        return []
    payload = json.loads(KWORKS_JSON.read_text(encoding="utf-8"))
    return list(payload.get("unique_kworks") or [])


def parse_quick_proposals() -> list[Proposal]:
    if not QUICK_PROPOSALS_REPORT.exists():
        return []
    text = QUICK_PROPOSALS_REPORT.read_text(encoding="utf-8")
    sections = re.split(r"\n##\s+\d+\.\s+", text)
    proposals: list[Proposal] = []
    for section in sections[1:]:
        lines = section.splitlines()
        title = norm(lines[0]) if lines else ""
        price = ""
        deadline = ""
        risk = ""
        questions: list[str] = []
        in_questions = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- suggested_price:"):
                price = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- suggested_deadline:"):
                deadline = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- risk:"):
                risk = stripped.split(":", 1)[1].strip()
            elif stripped == "### Questions To Ask":
                in_questions = True
            elif in_questions and stripped.startswith("- "):
                questions.append(stripped[2:].strip())
            elif in_questions and stripped.startswith("```"):
                in_questions = False
        proposals.append(Proposal(title=title, price=price, deadline=deadline, risk=risk, text=section, questions=questions[:3]))
    return proposals


def risk_hits(text: str) -> list[str]:
    return [pattern for pattern in HARD_BLOCK_PATTERNS if re.search(pattern, text, re.I)]


def safe_topic_hit(text: str) -> bool:
    lower = text.lower()
    return any(topic in lower for topic in SAFE_TOPICS)


def classify_order(proposal: Proposal) -> tuple[str, str, bool, str, list[str]]:
    # Do not scan the generated proposal body here: it intentionally contains
    # safety disclaimers like "закрытые данные не беру", which are not project
    # requirements and should not make a safe lead look dangerous.
    combined = f"{proposal.title}\n{proposal.risk}\n" + "\n".join(proposal.questions)
    hits = risk_hits(combined)
    missing = list(proposal.questions)
    if hits:
        return "DO_NOT_TAKE", "Найдены hard-risk маркеры: " + ", ".join(hits[:3]), False, "do_not_reply", missing
    if "no major risk keywords detected" not in proposal.risk.lower() and proposal.risk:
        return "MEDIUM", f"Есть риск-сигнал в quick report: {proposal.risk}", True, "clarification_first", missing
    if safe_topic_hit(combined):
        return "LOW", "Похоже на понятную техническую задачу с проверяемым результатом.", True, "simple_confident", missing
    return "MEDIUM", "Тема не выглядит серой, но для слабой репутации нужны уточнения до отклика.", True, "clarification_first", missing


def classify_kwork(item: dict[str, Any]) -> tuple[str, str, str]:
    title = norm(item.get("title"))
    lower = title.lower()
    price_value = int(re.sub(r"\D", "", str(item.get("price") or "0")) or "0")
    status = norm(item.get("status"))
    if "ai" in lower or "интеграци" in lower or "api" in lower or "crm" in lower:
        return "HIGH", "Широкое обещание: легко получить недопонимание по объёму.", "SIMPLIFY"
    if "мини-сайт" in lower or "личный кабинет" in lower:
        return "HIGH", "Слишком широкий scope для восстановления рейтинга.", "DO_NOT_PROMOTE_NOW"
    if "парсер" in lower:
        return "MEDIUM", "Парсеры часто упираются в капчи/защиты и ожидания клиента.", "REWRITE_DESCRIPTION"
    if "браузерную автоматизацию" in lower:
        return "MEDIUM", "Нужно явно запретить обходы защит, капчи и массовые действия.", "REWRITE_DESCRIPTION"
    if "minecraft" in lower:
        return "LOW", "Простая проверяемая услуга, если ограничить scope.", "KEEP"
    if "telegram" in lower and "google" in lower:
        return "LOW", "Понятный результат: заявка -> таблица; важно не обещать CRM под ключ.", "KEEP"
    if price_value >= 9000 and "черновик" in status.lower():
        return "MEDIUM", "Для слабой репутации высокая цена требует очень чёткого scope.", "SIMPLIFY"
    if price_value <= 1200:
        return "LOW", "Малый чек подходит для восстановления доверия, если scope узкий.", "KEEP"
    return "MEDIUM", "Нужна ручная проверка scope, цены и критериев готовности.", "SIMPLIFY"


def write_reputation_report() -> None:
    lines = [
        "# Reputation Recovery Report",
        "",
        f"- generated_at: `{now()}`",
        f"- mode: `offline_manual_only`",
        f"- kwork_state_changed: `false`",
        f"- proposals_sent: `false`",
        "",
        "## Current Risk",
        "",
        f"- рейтинг пользователя: `{CURRENT_RATING}`",
        f"- есть плохой отзыв: `{str(HAS_BAD_REVIEW).lower()}`",
        "- риск следующего плохого отзыва: `high`",
        "- нельзя брать сложные и расплывчатые заказы.",
        "- цель сейчас: `один маленький хороший отзыв`, а не максимальный доход.",
        "",
        "## What To Sell Now",
        "",
        "1. Minecraft сервер — простые настройки.",
        "2. Python/Excel/CSV — маленькие правки.",
        "3. Google Sheets automation — простые таблицы/уведомления.",
        "4. Telegram notifications — простые уведомления.",
        "5. Docker/Linux deploy — только простые запуски по инструкции.",
        "",
        "## What NOT To Sell Now",
        "",
        "- большие CRM;",
        "- сложные интеграции;",
        "- “под ключ” без ТЗ;",
        "- парсеры с капчей;",
        "- обходы защит;",
        "- спам/массовые регистрации;",
        "- всё, где клиент сам не понимает, чего хочет;",
        "- всё, что нельзя проверить за 1–2 часа.",
        "",
        "## Rules Before Taking Any Order",
        "",
        "- задача понятна;",
        "- можно выполнить за 1–2 дня;",
        "- есть доступы/данные;",
        "- результат можно проверить;",
        "- цена не слишком маленькая для объёма;",
        "- нет серых требований.",
    ]
    write_text(REPUTATION_REPORT, "\n".join(lines))


def write_safe_order_filter() -> list[tuple[Proposal, str, bool]]:
    proposals = parse_quick_proposals()
    lines = [
        "# Safe Order Filter Report",
        "",
        f"- generated_at: `{now()}`",
        "- mode: `offline_manual_only`",
        "- messages_sent: `false`",
        "- proposals_sent: `false`",
        "",
    ]
    decisions: list[tuple[Proposal, str, bool]] = []
    for index, proposal in enumerate(proposals, start=1):
        risk_level, reason, should_reply, reply_type, missing = classify_order(proposal)
        decisions.append((proposal, risk_level, should_reply))
        lines.extend(
            [
                f"## {index}. {proposal.title}",
                "",
                f"- title: {proposal.title}",
                f"- price: {proposal.price or 'not visible'}",
                f"- deadline: {proposal.deadline or 'not visible'}",
                f"- risk_level: `{risk_level}`",
                f"- why_safe_or_risky: {reason}",
                f"- missing_questions: {', '.join(missing) if missing else 'уточнить критерии готовности'}",
                f"- should_reply: `{str(should_reply).lower()}`",
                f"- recommended_reply_type: `{reply_type}`",
                "",
            ]
        )
    if not proposals:
        lines.append("- no quick proposals available; run `npm run money:quick-proposals` first.")
    write_text(SAFE_ORDER_REPORT, "\n".join(lines))
    return decisions


def write_clarification_templates() -> None:
    templates = {
        "Minecraft server": (
            "Здравствуйте! Могу помочь с настройкой Minecraft сервера. Чтобы точно оценить объём и не сделать лишнего, уточните, пожалуйста: "
            "версию Minecraft, тип сервера (Vanilla/Paper/Forge/Fabric), где запускаем сервер, нужны ли моды/плагины и сколько игроков планируется. "
            "Если задача укладывается в базовую настройку, сделаю аккуратно и передам короткую инструкцию."
        ),
        "Python / Excel / CSV": (
            "Здравствуйте! Могу помочь с небольшой правкой Python/Excel/CSV. Чтобы не раздувать задачу, пришлите пример входного файла, какой результат должен получиться и 2–3 тестовых строки. "
            "Если объём небольшой и результат можно быстро проверить, возьму в работу."
        ),
        "Google Sheets": (
            "Здравствуйте! Могу помочь с Google Таблицей или простой автоматизацией. Уточните, пожалуйста, какие колонки нужны, откуда берутся данные, как часто обновлять и как понять, что результат готов. "
            "Сложные CRM/API лучше отделить в отдельный этап, чтобы не рисковать качеством."
        ),
        "Telegram bot": (
            "Здравствуйте! Могу сделать простой Telegram-сценарий, если задача чёткая. Уточните, какие вопросы бот должен задавать, куда отправлять результат, нужна ли Google Таблица и где бот будет запускаться. "
            "Спам, накрутки и обходы ограничений не беру."
        ),
        "Docker / Linux deploy": (
            "Здравствуйте! Могу помочь с простым запуском на Linux/Docker. Уточните ОС сервера, что уже установлено, как проверяем успешный запуск и нужны ли systemd/Docker/.env. "
            "Перед началом лучше зафиксировать одну проверяемую цель, чтобы результат был понятным."
        ),
    }
    lines = [
        "# Client Clarification Templates",
        "",
        f"- generated_at: `{now()}`",
        "- purpose: `manual copy-paste only`",
        "- messages_sent: `false`",
        "",
    ]
    for title, text in templates.items():
        lines.extend([f"## {title}", "", "```text", text, "```", ""])
    write_text(CLARIFICATION_TEMPLATES, "\n".join(lines))


def write_kwork_risk_audit() -> tuple[str, list[dict[str, Any]]]:
    kworks = load_kworks()
    lines = [
        "# Kwork Risk Audit Report",
        "",
        f"- generated_at: `{now()}`",
        f"- source: `{KWORKS_JSON.relative_to(ROOT)}`",
        "- mode: `offline_read_only`",
        "- kwork_state_changed: `false`",
        "",
        "| # | Title | Status | Price | Risk | Recommendation | Reason |",
        "|---|-------|--------|-------|------|----------------|--------|",
    ]
    ranked: list[tuple[int, dict[str, Any], str, str, str]] = []
    weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    for index, item in enumerate(kworks, start=1):
        risk, reason, recommendation = classify_kwork(item)
        ranked.append((weight.get(risk, 0), item, risk, reason, recommendation))
        lines.append(
            f"| {index} | {norm(item.get('title')).replace('|', '/')} | {norm(item.get('status'))} | "
            f"{norm(item.get('price')) or '?'} | `{risk}` | `{recommendation}` | {reason.replace('|', '/')} |"
        )
    ranked.sort(key=lambda row: (-row[0], norm(row[1].get("title"))))
    worst = norm(ranked[0][1].get("title")) if ranked else "not_available"
    lines.extend(
        [
            "",
            "## Highest Risk Kwork",
            "",
            f"- title: `{worst}`",
            f"- risk_level: `{ranked[0][2] if ranked else 'not_available'}`",
            f"- recommendation: `{ranked[0][4] if ranked else 'not_available'}`",
            f"- reason: {ranked[0][3] if ranked else 'No local kworks snapshot available.'}",
        ]
    )
    write_text(KWORK_RISK_AUDIT_REPORT, "\n".join(lines))
    return worst, kworks


def update_tomorrow_plan() -> None:
    block = """## Reputation Recovery Plan

Сегодня/завтра делать:

1. Улучшить Minecraft-кворк, убрать лишние обещания.
2. Отправлять только LOW risk отклики.
3. Перед каждым заказом задавать уточняющие вопросы.
4. Не брать заказы дороже по сложности, чем можешь выполнить.
5. Цель — получить 1 маленький хороший отзыв, а не максимальный доход сразу.

Правило восстановления рейтинга: если задача не проверяется за 1–2 часа или клиент сам не понимает результат, заказ лучше не брать.
"""
    if TOMORROW_PLAN.exists():
        text = TOMORROW_PLAN.read_text(encoding="utf-8")
    else:
        text = "# Tomorrow Kwork Action Plan\n\n"
    if "## Reputation Recovery Plan" in text:
        text = re.sub(r"## Reputation Recovery Plan\n.*?(?=\n## |\Z)", block.rstrip(), text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block.rstrip() + "\n"
    write_text(TOMORROW_PLAN, text)


def run(mode: str) -> None:
    write_reputation_report()
    decisions = write_safe_order_filter()
    write_clarification_templates()
    worst, kworks = write_kwork_risk_audit()
    update_tomorrow_plan()
    safe = [proposal.title for proposal, risk, should in decisions if should and risk == "LOW"]
    blocked = [proposal.title for proposal, risk, should in decisions if not should or risk == "DO_NOT_TAKE"]
    print(REPUTATION_REPORT)
    print(SAFE_ORDER_REPORT)
    print(CLARIFICATION_TEMPLATES)
    print(KWORK_RISK_AUDIT_REPORT)
    print(f"kworks_analyzed={len(kworks)}")
    print(f"safe_orders={len(safe)}")
    print(f"blocked_orders={len(blocked)}")
    print(f"highest_risk_kwork={worst}")
    print(f"mode={mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", "filter"], default="all")
    args = parser.parse_args()
    run(args.mode)


if __name__ == "__main__":
    main()
