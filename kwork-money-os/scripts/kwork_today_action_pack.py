#!/usr/bin/env python3
"""Build today's money action pack from local Kwork reports."""

from __future__ import annotations

import re
from datetime import datetime

from kwork_studio_common import (
    BEST_COVER_PROMPT_MD,
    CATEGORY_RESOLVER_REPORT,
    LAUNCH_READINESS_REPORT,
    MY_KWORKS_AUDIT_REPORT,
    QUICK_PROPOSALS_REPORT,
    SUBCATEGORY_RESOLVER_REPORT,
    TODAY_ACTION_PACK_REPORT,
    ensure_studio_dirs,
    write_text,
)


def read(path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def field(text: str, name: str, default: str = "unknown") -> str:
    match = re.search(rf"-\s+{re.escape(name)}:\s+`([^`]*)`", text)
    return match.group(1).strip() if match else default


def top_quick_proposals(text: str, limit: int = 3) -> list[str]:
    items = []
    for match in re.finditer(r"^##\s+\d+\.\s+(.+)$", text, re.M):
        title = match.group(1).strip()
        tail = text[match.end() : match.end() + 700]
        url = re.search(r"- url:\s+(\S+)", tail)
        price = re.search(r"- suggested_price:\s+(.+)", tail)
        deadline = re.search(r"- suggested_deadline:\s+(.+)", tail)
        items.append(
            f"{title} | {price.group(1).strip() if price else 'price unknown'} | "
            f"{deadline.group(1).strip() if deadline else 'deadline unknown'} | {url.group(1) if url else 'url unknown'}"
        )
        if len(items) >= limit:
            break
    return items


def audit_summary(text: str) -> list[str]:
    summaries = []
    for match in re.finditer(r"^##\s+\d+\.\s+(.+)$", text, re.M):
        title = match.group(1).strip()
        tail = text[match.end() : match.end() + 900]
        verdict = field(tail, "verdict", "unknown")
        score = field(tail, "marketing_score", "unknown")
        summaries.append(f"{title}: {verdict}, marketing_score={score}")
        if len(summaries) >= 5:
            break
    return summaries


def main() -> None:
    ensure_studio_dirs()
    category = read(CATEGORY_RESOLVER_REPORT)
    subcategory = read(SUBCATEGORY_RESOLVER_REPORT)
    readiness = read(LAUNCH_READINESS_REPORT)
    audit = read(MY_KWORKS_AUDIT_REPORT)
    quick = read(QUICK_PROPOSALS_REPORT)
    lines = [
        "# Today Money Action Pack",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## СЕГОДНЯ, ЧТО ДЕЛАТЬ",
        "1. Если subcategory resolver выбрал подкатегорию — проверь её глазами.",
        "2. Если не выбрал — руками выбери ближайшее: Боты / Чат-боты / Telegram-боты / Скрипты / Автоматизация.",
        "3. Сгенерируй обложку по prompt из best_cover_prompt_for_chatgpt.md.",
        "4. Сохрани картинку в covers/inbox.",
        "5. Запусти cover-inbox-check -> cover-select -> cover-process-selected -> cover-upload-cdp.",
        "6. Проверь кворк глазами.",
        "7. Только сам вручную нажимай сохранение/модерацию.",
        "8. Потом вручную отправь 2-3 отклика из quick_proposals_today.md.",
        "",
        "## 1. Auto Category Result",
        f"- status: `{field(category, 'status')}`",
        f"- selected_category: `{field(category, 'selected_category', 'none')}`",
        f"- selected_subcategory: `{field(subcategory, 'selected_subcategory', field(category, 'selected_subcategory', 'none'))}`",
        f"- confidence_score: `{field(category, 'confidence_score', '0')}`",
        f"- subcategory_verdict: `{field(subcategory, 'verdict', 'not_run')}`",
        f"- subcategory_next_step: `{field(subcategory, 'user_next_step', 'run npm run money:kwork-resolve-subcategory-cdp')}`",
        "",
        "## 2. Best Cover Prompt",
        f"- prompt_path: `{BEST_COVER_PROMPT_MD}`",
        "- inbox_path: `/home/zerro/projects/browser-command-center/kwork-money-os/data/kwork_studio/covers/inbox/`",
        "- next_command: `npm run money:cover-inbox-check`",
        "",
        "## 3. My Kworks Audit Summary",
        *(f"- {item}" for item in (audit_summary(audit) or ["audit not available yet"])),
        f"- best_title_candidate: `{field(audit, 'best_title_candidate', 'not available')}`",
        "",
        "## 4. Launch Readiness",
        f"- verdict: `{field(readiness, 'verdict')}`",
        f"- user_next_step: `{field(readiness, 'user_next_step', 'Открой Chrome и проверь вручную.')}`",
        "",
        "## 5. Quick Proposals",
        *(f"- {item}" for item in (top_quick_proposals(quick) or ["quick proposals not available yet"])),
        "",
        "## Safety",
        "- This pack is local/report-only.",
        "- No save/moderation/publish/send/proposal/order/phone/withdrawal/delete/final buttons clicked.",
    ]
    write_text(TODAY_ACTION_PACK_REPORT, "\n".join(lines))
    print(TODAY_ACTION_PACK_REPORT)
    print(f"launch_readiness_verdict={field(readiness, 'verdict')}")
    print(f"quick_proposals_count={len(top_quick_proposals(quick, 10))}")


if __name__ == "__main__":
    main()
