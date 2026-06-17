#!/usr/bin/env python3
"""Prepare 3-5 quick proposal drafts from saved Kwork leads.

Offline only. This script never opens Kwork and never sends proposals.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from _common import DATA, ROOT
from kwork_lead_triage import (
    DEFAULT_INPUT,
    TOP5_REPORT,
    deduplicate,
    load_leads,
    triage_lead,
)
from kwork_studio_common import QUICK_PROPOSALS_REPORT, write_text


EXTRA_SKIP_PATTERNS = [
    re.compile(r"клиент|лидоген|лидогенерац|поиск клиентов", re.I),
    re.compile(r"инвестиц|крипт|форекс|ставк|казино|беттинг", re.I),
]


def choose_items():
    leads = deduplicate(load_leads(DEFAULT_INPUT))
    triaged = [triage_lead(lead) for lead in leads]
    safe = []
    for item in triaged:
        combined = "\n".join([item.lead.title, item.lead.project_text, item.lead.category])
        if not item.lead.is_project_url or item.high_risk:
            continue
        if any(pattern.search(combined) for pattern in EXTRA_SKIP_PATTERNS):
            continue
        if item.verdict == "SKIP":
            continue
        safe.append(item)
    ranked = sorted(safe, key=lambda item: (-item.final_score, item.lead.risk_score, item.lead.title))
    top = [item for item in ranked if item.verdict == "SEND_AFTER_PHONE"][:5]
    if len(top) < 3:
        top = (top + [item for item in ranked if item not in top])[:5]
    return top[:5]


def write_report(items) -> None:
    lines = [
        "# Quick Proposals Today",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- project_root: `{ROOT.parent}`",
        f"- source_jsonl: `{DEFAULT_INPUT}`",
        f"- top5_reference_report: `{TOP5_REPORT}`",
        f"- proposals_prepared: `{len(items)}`",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lead = item.lead
        lines.extend(
            [
                f"## {index}. {lead.title}",
                "",
                f"- title: {lead.title}",
                f"- url: {lead.url}",
                f"- budget: {lead.budget or 'not visible'}",
                f"- deadline: {lead.deadline or lead.recommended_deadline}",
                f"- why_match: {', '.join(lead.why_match[:4]) or 'general automation fit'}",
                f"- risk: {', '.join((item.high_risk_reasons or lead.why_risky)[:3]) or 'no major risk keywords detected'}",
                f"- suggested_price: {lead.recommended_price} ₽",
                f"- suggested_deadline: {lead.recommended_deadline}",
                "",
                "### Questions To Ask",
                *(f"- {question}" for question in item.questions[:3]),
                "",
                "```text",
                item.proposal,
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Safety",
            "- Offline only: no Kwork browser actions were performed.",
            "- No proposal/message was sent.",
            "- `Предложить услугу`, `Отправить`, publish and moderation remain manual-only.",
        ]
    )
    write_text(QUICK_PROPOSALS_REPORT, "\n".join(lines))


def main() -> None:
    items = choose_items()
    if not items:
        raise SystemExit(f"No safe leads available in {DEFAULT_INPUT}")
    write_report(items)
    print(QUICK_PROPOSALS_REPORT)
    print(f"proposals_prepared={len(items)}")
    for index, item in enumerate(items, start=1):
        print(
            f"proposal{index}={item.final_score} | {item.lead.recommended_price} ₽ | "
            f"{item.lead.recommended_deadline} | {item.lead.title}"
        )


if __name__ == "__main__":
    main()
