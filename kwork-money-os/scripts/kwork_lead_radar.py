#!/usr/bin/env python3
"""Read-only Kwork project radar with local proposal drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from _common import DATA, REPORTS, ROOT, ensure_dir
from account_optimizer_common import FINAL_ACTION_WORDS, PROJECTS_URL, redact_text
from browser_rpa_bridge import KworkRpaBridge, PROFILE_DIR, RpaReport


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
REPO_ROOT = ROOT.parent
LEADS_DIR = DATA / "leads"
LEADS_JSONL = LEADS_DIR / "kwork_leads.jsonl"
PROPOSALS_DIR = LEADS_DIR / "proposals"
REPORT_PATH = REPORTS / "lead_radar_report.md"
MAX_CARDS_PER_TOPIC = 8
MAX_DETAIL_PAGES = 10
BROWSER_ENGINE = "Playwright Chromium"
BROWSER_PROFILE_PATH = str(PROFILE_DIR)
LOGIN_GUIDANCE = (
    "login_detected is not true in Playwright Chromium. Yandex Browser login does not count here. "
    "Use `npm run money:lead-radar -- --preview --hold`, log in manually in the opened Chromium window, "
    "do not save passwords to files, then rerun Lead Radar."
)

TOPICS = [
    "Telegram бот",
    "бот для заявок",
    "Google Sheets",
    "автоматизация",
    "Python скрипт",
    "Docker",
    "парсер",
    "CRM",
    "отчёты",
    "API интеграция",
]

GOOD_PATTERNS = [
    (re.compile(r"telegram|телеграм|бот", re.I), 16, "Telegram bot scope"),
    (re.compile(r"google\s*sheets|google таблиц|гугл таблиц|таблиц", re.I), 12, "Google Sheets fit"),
    (re.compile(r"python|скрипт|автоматизац|api|webhook|docker|парсер|отч[её]т|crm", re.I), 10, "Python/simple automation fit"),
    (re.compile(r"заявк|форма|уведомлен|администратор|лид", re.I), 10, "lead/request workflow"),
    (re.compile(r"нужно|требуется|сделать|добавить|настроить|интегра", re.I), 8, "actionable wording"),
]

RISK_PATTERNS = [
    (re.compile(r"капч|captcha|обход|антибот|бан|блокиров", re.I), 45, "captcha/bypass risk"),
    (re.compile(r"спам|массов(ая|ые|о)|рассылк|регистрац|накрут", re.I), 45, "spam or mass-action risk"),
    (re.compile(r"чуж(ой|ие)|аккаунт|личн(ый|ые) кабинет|плат[её]ж|банк|вывод средств", re.I), 30, "third-party account/payment access"),
    (re.compile(r"срочно|за час|сегодня|немедленно", re.I), 15, "rush timing risk"),
    (re.compile(r"парсинг.*(обход|блокиров|капч)|закрыт(ые|ого) данн", re.I), 35, "unsafe parsing requirement"),
]


@dataclass
class LeadRecord:
    lead_id: str
    topic: str
    title: str
    url: str
    buyer_username: str
    budget: str
    deadline: str
    category: str
    project_text: str
    proposals_count: str
    posted_time: str
    match_score: int
    risk_score: int
    recommended_price: int
    recommended_deadline: str
    why_match: list[str] = field(default_factory=list)
    why_risky: list[str] = field(default_factory=list)
    generated_proposal_draft: str = ""
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class RadarStatus:
    mode: str
    hold: bool = False
    project_root: str = ""
    git_commit: str = ""
    browser_engine: str = BROWSER_ENGINE
    browser_profile_path: str = BROWSER_PROFILE_PATH
    mode_explanation: str = ""
    login_detected: str = "unknown"
    phone_verification_detected: bool = False
    topics_scanned: list[str] = field(default_factory=list)
    leads_found: int = 0
    leads_saved: int = 0
    proposal_drafts_written: int = 0
    lead_radar_exit_code: int = 0
    lead_radar_status: str = "success"
    lead_radar_error_summary: str = "none"
    lead_radar_stdout_tail: str = "n/a: direct script execution"
    lead_radar_stderr_tail: str = "n/a: direct script execution"
    used_cached_leads: str = "no"
    fallback_to_offline_triage: str = "no"
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)

    def action(self, message: str) -> None:
        self.actions.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


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


def validate_root(status: RadarStatus) -> None:
    git_root = Path(run_git(["rev-parse", "--show-toplevel"]))
    status.project_root = str(git_root)
    status.git_commit = run_git(["rev-parse", "HEAD"])
    if git_root != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong git root: {git_root}. Expected: {EXPECTED_REPO_ROOT}")
    if REPO_ROOT != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong script root: {REPO_ROOT}. Expected: {EXPECTED_REPO_ROOT}")
    status.action(f"validated WSL project root: {git_root}")


def require_run_approval(mode: str, approved: bool) -> None:
    if mode == "run" and not approved:
        raise SystemExit("Lead Radar --run requires --approve. It is still read-only and never sends proposals.")


def explain_mode(mode: str) -> str:
    if mode == "dry-run":
        return "No browser opens; validates local wiring and may find 0 projects."
    if mode == "preview":
        return "Opens visible Playwright Chromium with .browser-profile, checks login, takes screenshots, and does not write lead data."
    return "Read-only collection in visible Playwright Chromium with .browser-profile; writes local lead/proposal drafts and never sends anything."


def search_url(topic: str) -> str:
    query = quote_plus(topic)
    return f"{PROJECTS_URL}?keyword={query}"


def stable_id(*parts: str) -> str:
    text = "\n".join(part for part in parts if part)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:14]
    return f"lead-{digest}"


def parse_money(text: str) -> int | None:
    candidates = []
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:[\s.]\d{3})+|\d{3,6})\s*(?:₽|руб|р\.|RUB)?", text, re.I):
        value = int(re.sub(r"\D", "", match.group(1)))
        if 300 <= value <= 500000:
            candidates.append(value)
    return max(candidates) if candidates else None


def parse_count(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(?:предлож|отклик|заяв)", text, re.I)
    return int(match.group(1)) if match else None


def parse_deadline_days(text: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:дн|день|дня|дней)", text, re.I)
    return int(match.group(1)) if match else None


def clean_text(value: Any, limit: int = 1400) -> str:
    return redact_text(value, limit)


def score_lead(topic: str, title: str, text: str, budget_text: str, proposals_text: str, deadline_text: str) -> tuple[int, int, int, str, list[str], list[str]]:
    combined = f"{topic}\n{title}\n{text}"
    match_score = 0
    risk_score = 0
    why_match = []
    why_risky = []

    for pattern, points, reason in GOOD_PATTERNS:
        if pattern.search(combined):
            match_score += points
            why_match.append(reason)

    budget = parse_money(f"{budget_text}\n{text}")
    if budget is None:
        recommended_price = 5500
        why_risky.append("budget not visible")
        risk_score += 5
    elif 3000 <= budget <= 9000:
        recommended_price = min(max(round(budget / 500) * 500, 3000), 9000)
        match_score += 15
        why_match.append("budget is in 3000-9000 RUB range")
    elif budget < 3000:
        recommended_price = 3000
        risk_score += 20
        why_risky.append("budget is below recommended floor")
    else:
        recommended_price = min(max(round(budget * 0.8 / 500) * 500, 5500), 12000)
        match_score += 4
        why_match.append("budget can support a scoped first stage")

    proposals_count = parse_count(f"{proposals_text}\n{text}")
    if proposals_count is not None and proposals_count > 20:
        risk_score += 15
        why_risky.append("many visible proposals")

    deadline_days = parse_deadline_days(f"{deadline_text}\n{text}")
    if deadline_days is not None:
        if 2 <= deadline_days <= 7:
            match_score += 7
            why_match.append("small practical deadline")
            recommended_deadline = f"{deadline_days} дн."
        elif deadline_days < 2:
            risk_score += 12
            why_risky.append("deadline looks too tight")
            recommended_deadline = "3-4 дн."
        else:
            recommended_deadline = "4-7 дн."
    else:
        recommended_deadline = "3-5 дн."

    if len(text.strip()) < 90:
        risk_score += 20
        why_risky.append("brief or vague project text")
    elif len(text.strip()) > 180:
        match_score += 8
        why_match.append("project has enough detail to scope safely")

    for pattern, points, reason in RISK_PATTERNS:
        if pattern.search(combined):
            risk_score += points
            why_risky.append(reason)

    match_score = max(0, min(match_score, 100))
    risk_score = max(0, min(risk_score, 100))
    if not why_match:
        why_match.append("general automation keywords only")
    if not why_risky:
        why_risky.append("no major risk keywords detected")
    return match_score, risk_score, recommended_price, recommended_deadline, why_match, why_risky


def generate_proposal(lead: LeadRecord) -> str:
    greeting = f"Здравствуйте, {lead.buyer_username}!" if lead.buyer_username else "Здравствуйте!"
    questions = [
        "какие точные поля/данные нужно обработать или собрать?",
        "какой результат считать готовым для проверки?",
        "есть ли пример входных данных, таблицы или текущего процесса?",
        "где должен запускаться результат: локально, на VPS или пока достаточно кода с инструкцией?",
    ]
    if "telegram" in lead.project_text.lower() or "телеграм" in lead.project_text.lower():
        plan = [
            "уточню сценарий и поля заявки",
            "соберу минимальный рабочий бот/скрипт",
            "добавлю уведомление или запись в таблицу, если это входит в задачу",
            "передам README с запуском и простой проверкой результата",
        ]
    elif "docker" in lead.project_text.lower():
        plan = [
            "разберу текущий запуск и зависимости",
            "подготовлю Dockerfile или compose-файл",
            "проверю запуск на тестовой команде",
            "оставлю короткую инструкцию для повторного старта",
        ]
    else:
        plan = [
            "уточню входные данные и критерий готовности",
            "сделаю небольшой Python-скрипт или интеграцию под первый рабочий сценарий",
            "проверю на тестовом примере",
            "передам результат с инструкцией и ограничениями",
        ]
    return "\n".join(
        [
            greeting,
            "",
            "Могу взять задачу как небольшой понятный этап без лишних обещаний. Предлагаю такой план:",
            *(f"- {item};" for item in plan),
            "",
            f"Ориентир по цене: {lead.recommended_price} ₽.",
            f"Ориентир по сроку: {lead.recommended_deadline}.",
            "",
            "Чтобы точно оценить объём, уточните, пожалуйста:",
            *(f"- {item}" for item in questions[:4]),
            "",
            "Если задача включает спам, обход капчи, работу с чужими аккаунтами или платёжными данными, такую часть я не беру.",
        ]
    ).strip()


def extract_project_cards(bridge: KworkRpaBridge, topic: str) -> list[dict[str, str]]:
    if not bridge.available:
        return []
    try:
        raw_cards = bridge.page.evaluate(
            """({topic, limit}) => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const labelOf = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
              const selectors = [
                'article', '.project-card', '.want-card', '.order-card', '.card',
                '[class*="project"]', '[class*="want"]', '[data-project-id]', 'li'
              ];
              const nodes = Array.from(document.querySelectorAll(selectors.join(','))).filter(visible);
              const cards = [];
              for (const el of nodes) {
                const text = labelOf(el);
                if (text.length < 40) continue;
                const links = Array.from(el.querySelectorAll('a[href]'));
                const projectLink = links.find((a) => /\\/projects\\//.test(a.href)) || links[0];
                const titleEl = el.querySelector('h1,h2,h3,a,[class*="title"]');
                const userLink = links.find((a) => /\\/user\\//.test(a.href));
                cards.push({
                  topic,
                  title: labelOf(titleEl || projectLink || el).slice(0, 180),
                  url: projectLink ? projectLink.href : location.href,
                  buyer_username: userLink ? labelOf(userLink).slice(0, 80) : '',
                  text: text.slice(0, 2500)
                });
                if (cards.length >= limit) break;
              }
              return cards;
            }""",
            {"topic": topic, "limit": MAX_CARDS_PER_TOPIC},
        )
    except Exception as error:
        bridge.report.warn(f"project card extraction failed for {topic}: {error}")
        return []
    return [dict(item) for item in raw_cards]


def build_lead(topic: str, raw: dict[str, str]) -> LeadRecord:
    title = clean_text(raw.get("title") or topic, 180)
    url = str(raw.get("url") or "")
    project_text = clean_text(raw.get("text") or title, 1600)
    budget_match = re.search(r"((?:от\s*)?\d[\d\s.]{2,}\s*(?:₽|руб|р\.|RUB)?)", project_text, re.I)
    budget = budget_match.group(1).strip() if budget_match else ""
    deadline_match = re.search(r"(\d{1,2}\s*(?:дн|день|дня|дней))", project_text, re.I)
    deadline = deadline_match.group(1).strip() if deadline_match else ""
    proposals_match = re.search(r"(\d{1,3}\s*(?:предлож|отклик|заяв)[^\n,;]*)", project_text, re.I)
    proposals_count = proposals_match.group(1).strip() if proposals_match else ""
    category_match = re.search(r"(Разработка|Telegram|Python|Docker|CRM|Автоматизация|Парсинг|Отч[её]ты)[^\n]{0,80}", project_text, re.I)
    category = clean_text(category_match.group(0), 120) if category_match else ""
    posted_match = re.search(r"((?:сегодня|вчера|\d+\s*(?:мин|час|дн)[^\n,;]*назад))", project_text, re.I)
    posted_time = posted_match.group(1).strip() if posted_match else ""
    match_score, risk_score, price, rec_deadline, why_match, why_risky = score_lead(topic, title, project_text, budget, proposals_count, deadline)
    lead = LeadRecord(
        lead_id=stable_id(url, title, project_text[:300]),
        topic=topic,
        title=title,
        url=url,
        buyer_username=clean_text(raw.get("buyer_username") or "", 80),
        budget=budget,
        deadline=deadline,
        category=category,
        project_text=project_text,
        proposals_count=proposals_count,
        posted_time=posted_time,
        match_score=match_score,
        risk_score=risk_score,
        recommended_price=price,
        recommended_deadline=rec_deadline,
        why_match=why_match,
        why_risky=why_risky,
    )
    lead.generated_proposal_draft = generate_proposal(lead)
    return lead


def merge_existing_leads(new_leads: list[LeadRecord]) -> list[LeadRecord]:
    existing: dict[str, dict[str, Any]] = {}
    if LEADS_JSONL.exists():
        for line in LEADS_JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            existing[str(item.get("lead_id") or stable_id(str(item.get("url", "")), str(item.get("title", ""))))] = item
    for lead in new_leads:
        existing[lead.lead_id] = asdict(lead)
    return [LeadRecord(**item) for item in existing.values()]


def write_outputs(leads: list[LeadRecord]) -> tuple[int, int]:
    ensure_dir(LEADS_DIR)
    ensure_dir(PROPOSALS_DIR)
    merged = merge_existing_leads(leads)
    with LEADS_JSONL.open("w", encoding="utf-8") as handle:
        for lead in sorted(merged, key=lambda item: (-item.match_score, item.risk_score, item.title)):
            handle.write(json.dumps(asdict(lead), ensure_ascii=False) + "\n")
    proposal_count = 0
    for lead in leads:
        proposal_path = PROPOSALS_DIR / f"{lead.lead_id}.md"
        proposal_path.write_text(
            "\n".join(
                [
                    f"# Proposal Draft: {lead.title}",
                    "",
                    f"- lead_id: `{lead.lead_id}`",
                    f"- url: `{lead.url}`",
                    f"- match_score: `{lead.match_score}`",
                    f"- risk_score: `{lead.risk_score}`",
                    f"- recommended_price: `{lead.recommended_price}`",
                    f"- recommended_deadline: `{lead.recommended_deadline}`",
                    "",
                    "## Draft",
                    "",
                    lead.generated_proposal_draft,
                    "",
                    "## Safety",
                    "- Draft is local only.",
                    "- Nothing was sent to Kwork.",
                    "- Phone/SMS/withdrawal/publish/send actions remain manual-only.",
                ]
            ).rstrip()
            + "\n",
            encoding="utf-8",
        )
        proposal_count += 1
    return len(merged), proposal_count


def scan_projects(status: RadarStatus, mode: str) -> list[LeadRecord]:
    if mode == "dry-run":
        status.action("dry-run: browser was not opened and no Kwork pages were scanned")
        return []
    report = RpaReport(mode=f"lead-radar:{mode}", target_url=PROJECTS_URL, title="Kwork Lead Radar Browser Report")
    leads_by_id: dict[str, LeadRecord] = {}
    with KworkRpaBridge(report) as bridge:
        bridge.open(PROJECTS_URL)
        bridge.wait_and_screenshot("lead-radar-open")
        login_state = bridge.detect_login_state()
        status.login_detected = "true" if login_state is True else "false" if login_state is False else "unknown"
        if bridge.detect_phone_verification_required("lead-radar-phone-stop"):
            status.phone_verification_detected = True
            status.warn("phone verification detected before project scan; stopped browser scan")
            status.screenshots.extend(report.screenshots)
            if getattr(status, "hold", False):
                bridge.hold_open()
            return []
        if login_state is not True:
            status.warn(LOGIN_GUIDANCE)
            report.next_safe_command = "npm run money:lead-radar -- --preview --hold"
            print(LOGIN_GUIDANCE)
            status.screenshots.extend(report.screenshots)
            if getattr(status, "hold", False):
                bridge.hold_open()
            return []

        for topic in TOPICS:
            status.topics_scanned.append(topic)
            bridge.open(search_url(topic))
            bridge.wait_and_screenshot(f"lead-radar-{slug(topic)}")
            if bridge.detect_phone_verification_required("lead-radar-phone-stop"):
                status.phone_verification_detected = True
                status.warn("phone verification detected during scan; stopped browser scan")
                break
            blocked = bridge.find_blocked_buttons()
            if blocked:
                status.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
            for raw in extract_project_cards(bridge, topic):
                lead = build_lead(topic, raw)
                leads_by_id[lead.lead_id] = lead
            if mode == "preview" and len(leads_by_id) >= 12:
                status.action("preview limit reached after collecting visible project cards")
                break

        if mode == "run" and leads_by_id:
            detail_checked = 0
            for lead in list(leads_by_id.values()):
                if detail_checked >= MAX_DETAIL_PAGES:
                    break
                if not lead.url or "/projects/" not in lead.url:
                    continue
                bridge.open(lead.url)
                bridge.wait_and_screenshot(f"lead-radar-detail-{lead.lead_id}")
                if bridge.detect_phone_verification_required("lead-radar-phone-stop"):
                    status.phone_verification_detected = True
                    status.warn("phone verification detected on project detail; stopped detail scan")
                    break
                try:
                    detail_text = bridge.page.locator("body").inner_text(timeout=1500)
                except Exception:
                    detail_text = ""
                if detail_text:
                    refreshed = build_lead(lead.topic, {**asdict(lead), "text": detail_text, "title": lead.title, "url": lead.url})
                    leads_by_id[lead.lead_id] = refreshed
                detail_checked += 1

        status.screenshots.extend(report.screenshots)
        status.actions.extend(report.actions)
        status.warnings.extend(report.warnings)
        if getattr(status, "hold", False):
            bridge.hold_open()
    return sorted(leads_by_id.values(), key=lambda item: (-item.match_score, item.risk_score, item.title))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", "-", value.lower(), flags=re.I).strip("-")[:48] or "topic"


def write_report(status: RadarStatus, leads: list[LeadRecord]) -> None:
    ensure_dir(REPORT_PATH.parent)
    top_leads = sorted(leads, key=lambda item: (-item.match_score, item.risk_score, item.title))[:10]
    lines = [
        "# Kwork Lead Radar Report",
        "",
        f"Started at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"Mode: `{status.mode}`",
        "",
        "## Status",
        f"- project_root: `{status.project_root}`",
        f"- git_commit: `{status.git_commit}`",
        f"- browser_engine: `{status.browser_engine}`",
        f"- browser_profile_path: `{status.browser_profile_path}`",
        f"- mode_explanation: `{status.mode_explanation}`",
        f"- login_detected: `{status.login_detected}`",
        f"- phone_verification_detected: `{str(status.phone_verification_detected).lower()}`",
        f"- lead_radar_exit_code: `{status.lead_radar_exit_code}`",
        f"- lead_radar_status: `{status.lead_radar_status}`",
        f"- lead_radar_error_summary: `{status.lead_radar_error_summary}`",
        f"- lead_radar_stdout_tail: `{status.lead_radar_stdout_tail}`",
        f"- lead_radar_stderr_tail: `{status.lead_radar_stderr_tail}`",
        f"- used_cached_leads: `{status.used_cached_leads}`",
        f"- fallback_to_offline_triage: `{status.fallback_to_offline_triage}`",
        f"- topics_scanned: `{len(status.topics_scanned)}`",
        f"- leads_found: `{status.leads_found}`",
        f"- leads_saved_total: `{status.leads_saved}`",
        f"- proposal_drafts_written: `{status.proposal_drafts_written}`",
        "",
        "## Outputs",
        f"- leads_jsonl: `{LEADS_JSONL.relative_to(ROOT)}`",
        f"- proposal_drafts: `{PROPOSALS_DIR.relative_to(ROOT)}`",
        f"- report: `{REPORT_PATH.relative_to(ROOT)}`",
        "",
        "## Top Leads",
    ]
    if top_leads:
        for lead in top_leads:
            lines.append(f"- `{lead.match_score}/{lead.risk_score}` {lead.title} | {lead.recommended_price} ₽ | {lead.recommended_deadline} | {lead.url}")
    else:
        lines.append("- No leads collected in this run.")
    lines.extend(
        [
            "",
            "## Safety",
            "- Lead Radar uses Playwright Chromium with the local `.browser-profile`; it does not use Yandex Browser.",
            "- A Yandex Browser login is separate and does not count as `login_detected` for this tool.",
            "- Read-only scan only; proposal buttons and message/send controls are never clicked.",
            "- Draft replies are local files only and are not submitted to Kwork.",
            "- Phone/SMS/withdrawal/account switching/publish/moderation/final submit actions remain manual-only.",
            "- Runtime lead data is ignored by git and blocked by the private checker.",
            "",
            "## Actions",
            *(f"- {item}" for item in status.actions),
            "",
            "## Warnings",
            *(f"- {item}" for item in status.warnings),
            "",
            "## Screenshots",
            *(f"- `{item}`" for item in status.screenshots),
        ]
    )
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def classify_radar_status(status: RadarStatus, leads: list[LeadRecord], mode: str) -> None:
    status.lead_radar_exit_code = 0
    status.used_cached_leads = "no"
    status.fallback_to_offline_triage = "no"
    if mode == "dry-run":
        status.lead_radar_status = "success"
        status.lead_radar_error_summary = "dry-run completed without opening a browser"
    elif status.phone_verification_detected:
        status.lead_radar_status = "soft_stop"
        status.lead_radar_error_summary = "phone verification detected; browser scan stopped safely"
    elif status.login_detected != "true":
        status.lead_radar_status = "soft_stop"
        status.lead_radar_error_summary = "login is required in Playwright Chromium"
    elif not leads:
        status.lead_radar_status = "soft_stop"
        status.lead_radar_error_summary = "no leads found; handled as an expected empty scan"
    else:
        status.lead_radar_status = "success"
        status.lead_radar_error_summary = "leads collected and report written"


def mark_radar_failed(status: RadarStatus, error: BaseException) -> None:
    status.lead_radar_exit_code = 1
    status.lead_radar_status = "failed"
    status.lead_radar_error_summary = f"{type(error).__name__}: {error}"
    status.used_cached_leads = "no"
    status.fallback_to_offline_triage = "no"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--preview", action="store_true")
    group.add_argument("--run", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode = "dry-run" if args.dry_run else "preview" if args.preview else "run"
    status = RadarStatus(mode=mode, hold=bool(args.hold), mode_explanation=explain_mode(mode))
    leads: list[LeadRecord] = []
    try:
        require_run_approval(mode, args.approve)
        validate_root(status)
        leads = scan_projects(status, mode)
        status.leads_found = len(leads)
        if mode == "run" and leads:
            status.leads_saved, status.proposal_drafts_written = write_outputs(leads)
        elif mode == "run":
            ensure_dir(LEADS_DIR)
            ensure_dir(PROPOSALS_DIR)
            status.leads_saved = sum(1 for _ in LEADS_JSONL.open("r", encoding="utf-8")) if LEADS_JSONL.exists() else 0
            status.proposal_drafts_written = 0
        else:
            ensure_dir(LEADS_DIR)
            ensure_dir(PROPOSALS_DIR)
            status.leads_saved = sum(1 for _ in LEADS_JSONL.open("r", encoding="utf-8")) if LEADS_JSONL.exists() else 0
            status.proposal_drafts_written = 0
        classify_radar_status(status, leads, mode)
        write_report(status, leads)
        print(REPORT_PATH)
    except Exception as error:
        mark_radar_failed(status, error)
        status.warn(status.lead_radar_error_summary)
        try:
            write_report(status, leads)
        except Exception as report_error:
            print(f"Unable to write Lead Radar failure report: {report_error}", file=sys.stderr)
        print(status.lead_radar_error_summary, file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
