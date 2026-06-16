#!/usr/bin/env python3
"""Offline Best Lead of Day selector for Kwork Money OS.

Reads saved Lead Radar/Triage artifacts and chooses one best project for
manual review. It never opens a browser and never sends proposals.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from _common import DATA, REPORTS, ROOT, ensure_dir
from kwork_lead_triage import (
    TriagedLead,
    deduplicate,
    load_leads,
    triage_lead,
)


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
REPO_ROOT = ROOT.parent
LEADS_JSONL = DATA / "leads" / "kwork_leads.jsonl"
SHORTLIST_DIR = DATA / "leads" / "shortlist"
TOP5_REPORT = REPORTS / "top_5_proposals.md"
BEST_REPORT = REPORTS / "best_lead_of_day.md"
BEST_PROPOSAL = DATA / "leads" / "best_lead_of_day_proposal.md"

GRAY_OR_UNSAFE_PATTERNS = [
    (re.compile(r"поиск\s+клиент|нужн[ыо]\s+клиент|клиент[ао]в\s+в\s+данн", re.I), "lead-generation/client-acquisition scope"),
    (re.compile(r"инвестиц|доходност|ставк|казино|крипт|форекс|беттинг", re.I), "finance/speculative niche"),
    (re.compile(r"капч|captcha|обход|антибот|спам|массов(ая|ые|о)|накрут|чуж(ой|ие)|плат[её]ж|вывод", re.I), "unsafe/high-risk keyword"),
]

TECH_FIT_PATTERNS = [
    (re.compile(r"python|google\s*sheets|гугл|таблиц|api|яндекс директ|telegram|телеграм|docker|linux|сервер|парсер|crm", re.I), "clear technical fit"),
    (re.compile(r"2-3 дн|3-5 дн|5-7 дн", re.I), "fits 2-7 day delivery window"),
]


@dataclass
class BestCandidate:
    item: TriagedLead
    best_score: int
    top5_position: int | None
    shortlist_card: Path | None
    why_best: list[str]
    extra_risks: list[str]


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def validate_root() -> str:
    git_root = Path(run_git(["rev-parse", "--show-toplevel"]))
    if git_root != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong git root: {git_root}. Expected: {EXPECTED_REPO_ROOT}")
    if REPO_ROOT != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong script root: {REPO_ROOT}. Expected: {EXPECTED_REPO_ROOT}")
    return run_git(["rev-parse", "HEAD"])


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_top5_positions(path: Path) -> dict[str, int]:
    text = read_text(path)
    positions: dict[str, int] = {}
    current_position: int | None = None
    for line in text.splitlines():
        heading = re.match(r"##\s+(\d+)\.", line)
        if heading:
            current_position = int(heading.group(1))
            continue
        link = re.match(r"-\s+Ссылка:\s+(https?://\S+)", line)
        if link and current_position is not None:
            positions[link.group(1).strip()] = current_position
    return positions


def shortlist_cards(path: Path) -> dict[str, Path]:
    cards: dict[str, Path] = {}
    for card in sorted(path.glob("project_*.md")):
        text = read_text(card)
        match = re.search(r"^- url:\s*(https?://\S+)", text, re.M)
        if match:
            cards[match.group(1).strip()] = card
    return cards


def extra_risk_reasons(item: TriagedLead) -> list[str]:
    text = "\n".join([item.lead.title, item.lead.category, item.lead.project_text, " ".join(item.lead.why_risky)])
    reasons = [reason for pattern, reason in GRAY_OR_UNSAFE_PATTERNS if pattern.search(text)]
    return sorted(set(reasons))


def tech_fit_reasons(item: TriagedLead) -> list[str]:
    text = "\n".join([item.lead.title, item.lead.project_text, item.lead.recommended_deadline])
    reasons = [reason for pattern, reason in TECH_FIT_PATTERNS if pattern.search(text)]
    return sorted(set(reasons))


def best_score(item: TriagedLead, top5_position: int | None, extra_risks: list[str]) -> int:
    score = item.final_score
    if item.lead.risk_score == 0:
        score += 12
    if item.verdict == "SEND_AFTER_PHONE":
        score += 10
    if top5_position is not None:
        score += max(0, 8 - top5_position)
    if 2500 <= item.lead.recommended_price <= 9000:
        score += 8
    if re.search(r"2-3 дн|3-5 дн|5-7 дн", item.lead.recommended_deadline):
        score += 6
    score += len(tech_fit_reasons(item)) * 4
    score -= len(extra_risks) * 45
    return score


def build_candidates() -> list[BestCandidate]:
    if not LEADS_JSONL.exists():
        raise SystemExit(f"Lead JSONL not found: {LEADS_JSONL}")
    if not TOP5_REPORT.exists():
        raise SystemExit(f"Top proposals report not found: {TOP5_REPORT}")
    if not SHORTLIST_DIR.exists():
        raise SystemExit(f"Shortlist directory not found: {SHORTLIST_DIR}")

    top5 = parse_top5_positions(TOP5_REPORT)
    cards = shortlist_cards(SHORTLIST_DIR)
    leads = deduplicate(load_leads(LEADS_JSONL))
    candidates: list[BestCandidate] = []
    for lead in leads:
        item = triage_lead(lead)
        if not item.lead.is_project_url or item.high_risk:
            continue
        risks = extra_risk_reasons(item)
        if item.verdict == "SKIP":
            continue
        reasons = [
            f"final_score {item.final_score} with match/risk {item.lead.match_score}/{item.lead.risk_score}",
            f"recommended {item.lead.recommended_price} ₽ for {item.lead.recommended_deadline}",
        ]
        reasons.extend(item.lead.why_match[:4])
        reasons.extend(tech_fit_reasons(item))
        position = top5.get(item.lead.url)
        if position is not None:
            reasons.append(f"already ranked #{position} in top_5_proposals.md")
        candidates.append(
            BestCandidate(
                item=item,
                best_score=best_score(item, position, risks),
                top5_position=position,
                shortlist_card=cards.get(item.lead.url),
                why_best=sorted(set(reasons)),
                extra_risks=risks,
            )
        )
    return sorted(candidates, key=lambda candidate: (-candidate.best_score, -candidate.item.final_score, candidate.item.lead.risk_score))


def proposal_under_limit(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 10].rstrip() + "\n..."


def custom_best_proposal(item: TriagedLead) -> str:
    lead = item.lead
    text = f"{lead.title}\n{lead.project_text}".lower()
    if "яндекс директ" in text and ("google" in text or "таблиц" in text):
        return proposal_under_limit(
            "\n".join(
                [
                    f"Здравствуйте, {lead.buyer_username}!" if lead.buyer_username else "Здравствуйте!",
                    "",
                    "Готов взять задачу по выгрузке статистики Яндекс Директа в Google Sheets за 6000 ₽, срок 3-5 дней.",
                    "",
                    "План:",
                    "- уточню список кампаний, период и финальные колонки для двух вкладок: ключевые слова и кампании;",
                    "- подключу Yandex Direct API и Google Sheets API через безопасные переменные окружения, без паролей в коде;",
                    "- сделаю Python-скрипт для ручного запуска или запуска по расписанию;",
                    "- выгружу метрики в таблицу, добавлю форматирование дат, процентов, расходов и итоговых строк;",
                    "- передам README с настройкой .env, запуском и проверкой результата.",
                    "",
                    "Чтобы точно зафиксировать объём, уточните, пожалуйста:",
                    "1. Доступ к Direct API уже есть, или нужно пройти шаги получения токена?",
                    "2. Таблицу создавать с нуля или писать в уже существующий Spreadsheet ID?",
                    "3. Нужна только ежедневная выгрузка или ещё обновление за выбранный период вручную?",
                    "",
                    "Если потребуется, начну с минимального рабочего варианта и отдельно отмечу ограничения API/квот.",
                ]
            )
        )
    return proposal_under_limit(item.proposal)


def write_best_outputs(best: BestCandidate, git_commit: str) -> None:
    ensure_dir(BEST_REPORT.parent)
    ensure_dir(BEST_PROPOSAL.parent)
    item = best.item
    lead = item.lead
    proposal = custom_best_proposal(item)
    risks = best.extra_risks or item.high_risk_reasons or item.lead.why_risky or ["no major risk keywords detected"]
    lines = [
        "# Best Lead of Day",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- git_commit: `{git_commit}`",
        f"- project_title: {lead.title}",
        f"- url: {lead.url}",
        f"- buyer: {lead.buyer_username or 'not visible'}",
        f"- budget: {lead.budget or 'not visible'}",
        f"- proposals_count: {lead.proposals_count or 'not visible'}",
        f"- match_score: `{lead.match_score}`",
        f"- risk_score: `{lead.risk_score}`",
        f"- final_score: `{item.final_score}`",
        f"- best_score: `{best.best_score}`",
        f"- recommended_price: `{lead.recommended_price} ₽`",
        f"- recommended_deadline: `{lead.recommended_deadline}`",
        f"- verdict: `{item.verdict}`",
        f"- shortlist_card: `{best.shortlist_card.relative_to(ROOT) if best.shortlist_card else 'not found'}`",
        f"- top5_position: `{best.top5_position or 'not in top 5'}`",
        "",
        "## Why This Lead Is Best",
        *(f"- {reason}" for reason in best.why_best),
        "",
        "## Risks",
        *(f"- {risk}" for risk in risks),
        "",
        "## Execution Plan",
        *(f"- {step}" for step in item.execution_plan),
        "",
        "## Final Proposal Text",
        "",
        proposal,
        "",
        "## 3 Clarifying Questions",
        *(f"- {question}" for question in item.questions[:3]),
        "",
        "## Safety",
        "- Offline analysis only.",
        "- No proposal was sent to Kwork.",
        "- Send/manual proposal actions remain manual-only after phone verification.",
        "- Phone/SMS/withdrawal/publish/moderation/message/final buttons were not touched.",
    ]
    BEST_REPORT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    BEST_PROPOSAL.write_text(
        "\n".join(
            [
                f"# Proposal: {lead.title}",
                "",
                f"- url: {lead.url}",
                f"- price: {lead.recommended_price} ₽",
                f"- deadline: {lead.recommended_deadline}",
                f"- verdict: {item.verdict}",
                "",
                "```text",
                proposal,
                "```",
                "",
                "Safety: copy-paste manually only after phone verification. Nothing was sent automatically.",
            ]
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    git_commit = validate_root()
    candidates = build_candidates()
    if not candidates:
        raise SystemExit("No safe best-lead candidates found.")
    best = candidates[0]
    write_best_outputs(best, git_commit)
    item = best.item
    print(f"best_lead_report={BEST_REPORT}")
    print(f"best_lead_proposal={BEST_PROPOSAL}")
    print(f"title={item.lead.title}")
    print(f"url={item.lead.url}")
    print(f"buyer={item.lead.buyer_username or 'not visible'}")
    print(f"final_score={item.final_score}")
    print(f"best_score={best.best_score}")
    print(f"risk_score={item.lead.risk_score}")
    print(f"recommended_price={item.lead.recommended_price}")
    print(f"recommended_deadline={item.lead.recommended_deadline}")
    print(f"verdict={item.verdict}")
    print("sent=false")


if __name__ == "__main__":
    main()
