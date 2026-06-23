#!/usr/bin/env python3
"""Build a local Kwork Money OS operator dashboard.

The dashboard is offline-only. It reads local reports/artifacts and writes
local-only Markdown/HTML summaries for manual work after phone verification.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from _common import CONFIG, DATA, REPORTS, ROOT, ensure_dir, load_yaml
from account_guard import browser_profile_paths, load_account_guard_config


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
REPO_ROOT = ROOT.parent
DAILY_REPORT = REPORTS / "daily_lead_pipeline_report.md"
TOP5_REPORT = REPORTS / "top_5_proposals.md"
BEST_REPORT = REPORTS / "best_lead_of_day.md"
BEST_PROPOSAL = DATA / "leads" / "best_lead_of_day_proposal.md"
DELIVERY_KIT = DATA / "delivery" / "best_lead_yandex_direct_sheets"
TEMPLATE_README = ROOT / "templates" / "yandex_direct_sheets_exporter" / "README.md"
DASHBOARD_MD = REPORTS / "operator_dashboard.md"
DASHBOARD_HTML = REPORTS / "operator_dashboard.html"
TEMPLATE_PATH = ROOT / "templates" / "yandex_direct_sheets_exporter"
PORTFOLIO_DIR = DATA / "portfolio"
PORTFOLIO_INDEX = PORTFOLIO_DIR / "portfolio_index.md"
PORTFOLIO_CHECKLIST = PORTFOLIO_DIR / "portfolio_upload_checklist.md"
OFFER_FACTORY_DIR = DATA / "offers" / "factory"
OFFER_FACTORY_REPORT = REPORTS / "offer_factory_report.md"
ORDER_EXECUTOR_REPORT = REPORTS / "order_executor_report.md"
POST_PHONE_REPORT = REPORTS / "post_phone_readiness_report.md"
ACCOUNT_SWITCH_REPORT = REPORTS / "account_switch_report.md"
LOGIN_DIAGNOSTICS_REPORT = REPORTS / "kwork_login_diagnostics_report.md"
WINDOWS_CDP_REPORT = REPORTS / "windows_visible_browser_cdp_report.md"
PROFILE_FILL_CDP_REPORT = REPORTS / "profile_fill_cdp_report.md"
KWORK_FILL_CDP_REPORT = REPORTS / "kwork_fill_cdp_report.md"
KWORK_STUDIO_REPORT = REPORTS / "kwork_studio_report.md"
KWORK_COMPETITOR_SCAN_REPORT = REPORTS / "kwork_competitor_scan_report.md"
KWORK_COVER_STUDIO_REPORT = REPORTS / "kwork_cover_studio_report.md"
KWORK_COVER_PROMPT_REPORT = REPORTS / "kwork_cover_prompt_studio_report.md"
KWORK_COVER_INBOX_REPORT = REPORTS / "kwork_cover_inbox_report.md"
KWORK_COVER_SELECTION_REPORT = REPORTS / "kwork_cover_selection_report.md"
KWORK_COVER_PROCESSED_REPORT = REPORTS / "kwork_cover_processed_report.md"
KWORK_COVER_UPLOAD_REPORT = REPORTS / "kwork_cover_upload_report.md"
KWORK_FULL_FILL_CDP_REPORT = REPORTS / "kwork_full_fill_cdp_report.md"
KWORK_MARKETING_QA_REPORT = REPORTS / "kwork_marketing_qa_report.md"
KWORK_PROFILE_AUDIT_LIVE_REPORT = REPORTS / "kwork_profile_audit_live_report.md"
KWORK_PROFILE_AUDIT_REPORT = REPORTS / "kwork_profile_audit_report.md"
KWORK_INVENTORY_REPORT = REPORTS / "kwork_inventory_report.md"
KWORK_ALL_LIST_REPORT = REPORTS / "kwork_all_kworks_list.md"
PREPARED_ORDERS_DIR = DATA / "orders" / "prepared"
OFFER_FACTORY_ORDER = [
    "telegram_leads_bot.json",
    "google_sheets_automation.json",
    "docker_project_launch.json",
    "ai_assistant_basic.json",
    "python_parser_basic.json",
]

MANUAL_ONLY = [
    "Phone/SMS verification is manual-only.",
    "Send proposals only manually after phone verification.",
    "Do not automate `Предложить услугу` or `Отправить`.",
    "Publication/moderation stays manual-only.",
    "Withdrawal setup stays manual-only.",
    "Do not save profile or click final confirmation/delete/order buttons automatically.",
]


@dataclass
class DashboardData:
    daily: dict[str, str]
    best: dict[str, str]
    post_phone: dict[str, str]
    account_switch: dict[str, str]
    login_diagnostics: dict[str, str]
    windows_cdp: dict[str, str]
    profile_fill_cdp: dict[str, str]
    kwork_fill_cdp: dict[str, str]
    kwork_studio: dict[str, str]
    competitor_scan: dict[str, str]
    cover_studio: dict[str, str]
    cover_prompt: dict[str, str]
    cover_inbox: dict[str, str]
    cover_selection: dict[str, str]
    cover_processed: dict[str, str]
    cover_upload: dict[str, str]
    full_fill_cdp: dict[str, str]
    marketing_qa: dict[str, str]
    profile_audit_live: dict[str, str]
    profile_audit: dict[str, str]
    kwork_inventory: dict[str, str]
    kwork_all_list: dict[str, str]
    top5: list[str]
    proposal_text: str
    proposal_price: str
    proposal_deadline: str
    proposal_questions: list[str]
    delivery_files: list[str]
    delivery_questions: list[str]
    delivery_steps: list[str]
    template_summary: str
    portfolio_cases: list[str]
    portfolio_checklist: list[str]
    offer_factory: list[str]
    recommended_first_offer: str
    order_executor_status: str
    latest_order_workspace: str
    order_executor_checklist: list[str]
    git_commit: str


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
    if not path.exists():
        raise SystemExit(f"Required dashboard input is missing: {path}")
    return path.read_text(encoding="utf-8")


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"-\s+([^:]+):\s+`?([^`\n]+)`?", line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def parse_top5(text: str) -> list[str]:
    items: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        heading = re.match(r"##\s+(\d+)\.\s+(.+)", line)
        if heading:
            if current:
                items.append(current)
            current = {"position": heading.group(1), "title": heading.group(2).strip()}
            continue
        if current is None:
            continue
        if line.startswith("- Ссылка:"):
            current["url"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Цена:"):
            current["price"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Срок:"):
            current["deadline"] = line.split(":", 1)[1].strip()
    if current:
        items.append(current)

    formatted: list[str] = []
    for item in items[:5]:
        title = item.get("title", "Untitled")
        url = item.get("url", "")
        price = item.get("price", "price unknown")
        deadline = item.get("deadline", "deadline unknown")
        prefix = item.get("position", "?")
        if url:
            formatted.append(f"{prefix}. [{title}]({url}) | {price} | {deadline}")
        else:
            formatted.append(f"{prefix}. {title} | {price} | {deadline}")
    return formatted


def parse_proposal(text: str) -> tuple[str, str, str, list[str]]:
    price = ""
    deadline = ""
    for line in text.splitlines():
        if line.startswith("- price:"):
            price = line.split(":", 1)[1].strip()
        elif line.startswith("- deadline:"):
            deadline = line.split(":", 1)[1].strip()
    match = re.search(r"```text\n(.*?)\n```", text, re.S)
    proposal = match.group(1).strip() if match else text.strip()
    questions = re.findall(r"^\d+\.\s+(.+)$", proposal, re.M)
    if not questions:
        questions = re.findall(r"^-\s+(.+\?)$", proposal, re.M)
    return proposal, price, deadline, questions[:3]


def parse_delivery_questions() -> list[str]:
    text = read_optional(DELIVERY_KIT / "QUESTIONS_BEFORE_START.md")
    return [match.group(1).strip() for match in re.finditer(r"^\d+\.\s+(.+)$", text, re.M)][:8]


def parse_delivery_steps() -> list[str]:
    text = read_optional(DELIVERY_KIT / "RUN_INSTRUCTION.md")
    steps: list[str] = []
    if "templates/yandex_direct_sheets_exporter/" in text:
        steps.append("Use `templates/yandex_direct_sheets_exporter/` as a public-safe starter.")
    if "src/main.py --mock" in text:
        steps.append("Run mock mode before real API work: `.venv/bin/python src/main.py --mock`.")
    if "unittest discover tests" in text:
        steps.append("Run template tests before handoff: `.venv/bin/python -m unittest discover tests`.")
    steps.append("Configure `.env` locally with client-provided API placeholders only.")
    return steps


def parse_portfolio_cases(text: str) -> list[str]:
    cases: list[str] = []
    for line in text.splitlines():
        match = re.match(r"-\s+\[(.+?)\]\((.+?)\)\s+-\s+(.+)", line)
        if match:
            title, path, summary = match.groups()
            cases.append(f"{title} (`{path}`) - {summary}")
    return cases[:3]


def parse_numbered_items(text: str, limit: int = 10) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^\d+\.\s+(.+)$", text, re.M)][:limit]


def load_offer_factory() -> tuple[list[str], str]:
    items: list[str] = []
    recommended_first = ""
    for filename in OFFER_FACTORY_ORDER:
        path = OFFER_FACTORY_DIR / filename
        if not path.exists():
            continue
        offer = json.loads(path.read_text(encoding="utf-8"))
        title = offer.get("title", path.stem)
        prices = (
            f"{offer.get('price_economy', '?')}/"
            f"{offer.get('price_standard', '?')}/"
            f"{offer.get('price_premium', '?')} ₽"
        )
        days = (
            f"{offer.get('delivery_days_economy', '?')}/"
            f"{offer.get('delivery_days_standard', '?')}/"
            f"{offer.get('delivery_days_premium', '?')} days"
        )
        recommended = "yes" if offer.get("recommended_for_new_account") else "review"
        items.append(f"{title} (`{filename}`) - {prices}, {days}, new_account: {recommended}")
        if not recommended_first:
            recommended_first = title
    return items, recommended_first


def latest_prepared_order_workspace() -> str:
    if not PREPARED_ORDERS_DIR.exists():
        return ""
    workspaces = sorted(
        (path for path in PREPARED_ORDERS_DIR.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )
    if not workspaces:
        return ""
    return str(workspaces[-1].relative_to(ROOT))


def order_executor_status() -> tuple[str, str, list[str]]:
    workspace = latest_prepared_order_workspace()
    status = "ready" if workspace and ORDER_EXECUTOR_REPORT.exists() else "not_built"
    checklist = [
        "Confirm the Kwork order manually before starting paid work.",
        "Agree scope, price, deadline, and acceptance criteria manually.",
        "Ask only for client-created API tokens/accesses; never ask for passwords.",
        "Keep real `.env`, tokens, cookies, screenshots, and client data out of git.",
        "Send handoff/messages manually only when allowed.",
    ]
    return status, workspace or "none", checklist


def collect_data() -> DashboardData:
    git_commit = validate_root()
    daily_text = read_text(DAILY_REPORT)
    best_text = read_text(BEST_REPORT)
    post_phone_text = read_optional(POST_PHONE_REPORT)
    account_switch_text = read_optional(ACCOUNT_SWITCH_REPORT)
    login_diagnostics_text = read_optional(LOGIN_DIAGNOSTICS_REPORT)
    windows_cdp_text = read_optional(WINDOWS_CDP_REPORT)
    profile_fill_cdp_text = read_optional(PROFILE_FILL_CDP_REPORT)
    kwork_fill_cdp_text = read_optional(KWORK_FILL_CDP_REPORT)
    kwork_studio_text = read_optional(KWORK_STUDIO_REPORT)
    competitor_scan_text = read_optional(KWORK_COMPETITOR_SCAN_REPORT)
    cover_studio_text = read_optional(KWORK_COVER_STUDIO_REPORT)
    cover_prompt_text = read_optional(KWORK_COVER_PROMPT_REPORT)
    cover_inbox_text = read_optional(KWORK_COVER_INBOX_REPORT)
    cover_selection_text = read_optional(KWORK_COVER_SELECTION_REPORT)
    cover_processed_text = read_optional(KWORK_COVER_PROCESSED_REPORT)
    cover_upload_text = read_optional(KWORK_COVER_UPLOAD_REPORT)
    full_fill_cdp_text = read_optional(KWORK_FULL_FILL_CDP_REPORT)
    marketing_qa_text = read_optional(KWORK_MARKETING_QA_REPORT)
    profile_audit_live_text = read_optional(KWORK_PROFILE_AUDIT_LIVE_REPORT)
    profile_audit_text = read_optional(KWORK_PROFILE_AUDIT_REPORT)
    kwork_inventory_text = read_optional(KWORK_INVENTORY_REPORT)
    kwork_all_list_text = read_optional(KWORK_ALL_LIST_REPORT)
    top5_text = read_text(TOP5_REPORT)
    proposal_text_raw = read_text(BEST_PROPOSAL)
    template_readme = read_text(TEMPLATE_README)
    portfolio_index = read_text(PORTFOLIO_INDEX)
    portfolio_checklist = read_text(PORTFOLIO_CHECKLIST)
    offer_factory, recommended_first_offer = load_offer_factory()
    order_status, latest_workspace, order_checklist = order_executor_status()
    proposal, price, deadline, questions = parse_proposal(proposal_text_raw)
    delivery_files = sorted(path.name for path in DELIVERY_KIT.glob("*") if path.is_file()) if DELIVERY_KIT.exists() else []
    return DashboardData(
        daily=parse_fields(daily_text),
        best=parse_fields(best_text),
        post_phone=parse_fields(post_phone_text),
        account_switch=parse_fields(account_switch_text),
        login_diagnostics=parse_fields(login_diagnostics_text),
        windows_cdp=parse_fields(windows_cdp_text),
        profile_fill_cdp=parse_fields(profile_fill_cdp_text),
        kwork_fill_cdp=parse_fields(kwork_fill_cdp_text),
        kwork_studio=parse_fields(kwork_studio_text),
        competitor_scan=parse_fields(competitor_scan_text),
        cover_studio=parse_fields(cover_studio_text),
        cover_prompt=parse_fields(cover_prompt_text),
        cover_inbox=parse_fields(cover_inbox_text),
        cover_selection=parse_fields(cover_selection_text),
        cover_processed=parse_fields(cover_processed_text),
        cover_upload=parse_fields(cover_upload_text),
        full_fill_cdp=parse_fields(full_fill_cdp_text),
        marketing_qa=parse_fields(marketing_qa_text),
        profile_audit_live=parse_fields(profile_audit_live_text),
        profile_audit=parse_fields(profile_audit_text),
        kwork_inventory=parse_fields(kwork_inventory_text),
        kwork_all_list=parse_fields(kwork_all_list_text),
        top5=parse_top5(top5_text),
        proposal_text=proposal,
        proposal_price=price,
        proposal_deadline=deadline,
        proposal_questions=questions,
        delivery_files=delivery_files,
        delivery_questions=parse_delivery_questions(),
        delivery_steps=parse_delivery_steps(),
        template_summary=template_readme.split("## What It Does", 1)[0].strip(),
        portfolio_cases=parse_portfolio_cases(portfolio_index),
        portfolio_checklist=parse_numbered_items(portfolio_checklist, limit=8),
        offer_factory=offer_factory,
        recommended_first_offer=recommended_first_offer,
        order_executor_status=order_status,
        latest_order_workspace=latest_workspace,
        order_executor_checklist=order_checklist,
        git_commit=git_commit,
    )


def value(data: dict[str, str], key: str, default: str = "unknown") -> str:
    return data.get(key, default)


def first_real(default: str, *items: str) -> str:
    placeholders = {"", "unknown", "not_checked", "not_checked_dry_run", "none"}
    for item in items:
        if str(item).strip() not in placeholders:
            return item
    return default


def build_markdown(data: DashboardData) -> str:
    best_title = value(data.best, "project_title")
    guard_config = load_account_guard_config()
    guard_config_raw = load_yaml(CONFIG / "kwork_account_guard.yaml")
    browser_mode = str(guard_config_raw.get("browser_mode") or "wsl_playwright")
    active_path, fallback_path = browser_profile_paths(guard_config)
    guard_detected = first_real(
        "not_checked",
        value(data.windows_cdp, "detected_username", ""),
        value(data.account_switch, "detected_username_after", ""),
        value(data.login_diagnostics, "final_detected_username", ""),
        value(data.post_phone, "detected_username", ""),
        value(data.daily, "detected_username", ""),
    )
    guard_expected = value(data.post_phone, "expected_username", value(data.daily, "expected_username", guard_config.expected_username))
    guard_allowed = value(data.post_phone, "allowed_usernames", value(data.daily, "allowed_usernames", ", ".join(guard_config.allowed_usernames)))
    guard_status = first_real(
        "not_checked",
        value(data.windows_cdp, "account_guard_status", ""),
        value(data.account_switch, "account_guard_status", ""),
        value(data.login_diagnostics, "account_guard_status", ""),
        value(data.post_phone, "account_guard_status", ""),
        value(data.daily, "account_guard_status", ""),
    )
    guard_action = first_real(
        "not_checked",
        value(data.windows_cdp, "account_guard_action", ""),
        value(data.account_switch, "account_guard_action", ""),
        value(data.login_diagnostics, "account_guard_action", ""),
        value(data.post_phone, "account_guard_action", ""),
        value(data.daily, "account_guard_action", ""),
    )
    guard_message = first_real(
        "not_checked",
        value(data.windows_cdp, "error_summary", ""),
        value(data.account_switch, "account_guard_message", ""),
        value(data.login_diagnostics, "account_guard_message", ""),
        value(data.post_phone, "account_guard_message", ""),
        value(data.daily, "account_guard_message", ""),
    )
    active_browser_profile = first_real(
        str(active_path),
        value(data.account_switch, "active_browser_profile_path", ""),
        value(data.login_diagnostics, "profile_path", ""),
        value(data.post_phone, "active_browser_profile_path", ""),
        value(data.daily, "active_browser_profile_path", ""),
    )
    fallback_browser_profile = first_real(
        str(fallback_path),
        value(data.account_switch, "fallback_browser_profile_path", ""),
        value(data.post_phone, "fallback_browser_profile_path", ""),
        value(data.daily, "fallback_browser_profile_path", ""),
    )
    lines = [
        "# Kwork Operator Dashboard",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- git_commit: `{data.git_commit}`",
        "",
        "## Current Status",
        f"- login_detected: `{value(data.daily, 'login_detected')}`",
        f"- browser_mode: `{browser_mode}`",
        f"- active_browser_profile_path: `{active_browser_profile}`",
        f"- fallback_browser_profile_path: `{fallback_browser_profile}`",
        f"- detected_username: `{guard_detected}`",
        f"- account_guard_status: `{guard_status}`",
        f"- login_persistence_confirmed: `{value(data.login_diagnostics, 'persistence_confirmed', 'not_checked')}`",
        f"- windows_cdp_connected: `{value(data.windows_cdp, 'cdp_connected', 'not_checked')}`",
        f"- windows_cdp_persistence_confirmed: `{value(data.windows_cdp, 'persistence_confirmed', 'not_checked')}`",
        f"- post_phone_browser_mode: `{value(data.post_phone, 'browser_mode', 'not_checked')}`",
        f"- post_phone_cdp_connected: `{value(data.post_phone, 'cdp_connected', 'not_checked')}`",
        f"- profile_fill_cdp_status: `{value(data.profile_fill_cdp, 'account_guard_status', 'not_checked')}`",
        f"- kwork_fill_cdp_status: `{value(data.kwork_fill_cdp, 'account_guard_status', 'not_checked')}`",
        f"- kwork_studio_status: `{value(data.kwork_studio, 'verdict', 'not_checked')}`",
        f"- competitor_scan_status: `{value(data.competitor_scan, 'status', 'not_checked')}`",
        f"- selected_cover: `{value(data.cover_studio, 'selected_cover', 'not_checked')}`",
        f"- human_cover_prompts: `{value(data.cover_prompt, 'prompts_count', 'not_checked')}`",
        f"- cover_inbox_images_count: `{value(data.cover_inbox, 'images_count', 'not_checked')}`",
        f"- processed_cover: `{value(data.cover_processed, 'processed_file', 'not_checked')}`",
        f"- kwork_full_fill_status: `{value(data.full_fill_cdp, 'fields_filled', 'not_checked')}`",
        f"- marketing_qa_score: `{value(data.marketing_qa, 'score', 'not_checked')}`",
        f"- marketing_qa_verdict: `{value(data.marketing_qa, 'verdict', 'not_checked')}`",
        f"- profile_audit_live_status: `{value(data.profile_audit_live, 'data_collection_status', 'not_checked')}`",
        f"- profile_audit_live_kworks_count: `{value(data.profile_audit_live, 'kworks_collected', 'not_checked')}`",
        f"- profile_audit_latest_verdict: `{value(data.profile_audit, 'verdict', value(data.profile_audit_live, 'data_collection_status', 'not_checked'))}`",
        f"- inventory_total_kworks: `{value(data.kwork_inventory, 'total_current', 'not_checked')}`",
        f"- inventory_added: `{value(data.kwork_inventory, 'added', 'not_checked')}`",
        f"- inventory_missing_now: `{value(data.kwork_inventory, 'missing_now', 'not_checked')}`",
        f"- inventory_changed: `{value(data.kwork_inventory, 'changed', 'not_checked')}`",
        f"- inventory_weakest_kwork: `{value(data.kwork_inventory, 'weakest_kwork', 'not_checked')}`",
        f"- all_kworks_collection_status: `{value(data.kwork_all_list, 'collection_status', 'not_checked')}`",
        f"- all_kworks_collected_unique: `{value(data.kwork_all_list, 'collected_unique', 'not_checked')}`",
        f"- foreground_policy: `{value(data.full_fill_cdp, 'foreground_policy', value(data.competitor_scan, 'foreground_policy', 'not_checked'))}`",
        f"- phone_verification_detected: `{value(data.daily, 'phone_verification_detected')}`",
        f"- post_phone_verification_detected: `{value(data.post_phone, 'phone_verification_detected', 'not_checked')}`",
        f"- leads_found: `{value(data.daily, 'leads_found')}`",
        f"- safe_shortlist_count: `{value(data.daily, 'safe_shortlist_count')}`",
        f"- best_lead_of_day: {best_title}",
        f"- portfolio_pack_status: `ready ({len(data.portfolio_cases)} demo cases)`",
        f"- offer_factory_status: `ready ({len(data.offer_factory)} offers)`",
        f"- order_executor_status: `{data.order_executor_status}`",
        "",
        "## Kwork Account Guard",
        f"- expected_username: `{guard_expected}`",
        f"- active_browser_profile_path: `{active_browser_profile}`",
        f"- fallback_browser_profile_path: `{fallback_browser_profile}`",
        f"- detected_username: `{guard_detected}`",
        f"- allowed_usernames: `{guard_allowed}`",
        f"- account_guard_status: `{guard_status}`",
        f"- account_guard_action: `{guard_action}`",
        f"- account_guard_message: `{guard_message}`",
        "- warning: Профиль, кворки и отклики готовить только для ZerroOne. Перед публикацией убедись, что работаешь в нужном аккаунте.",
        "- if_mismatch: automation stops before profile fill, kwork draft fill, and browser lead scan; switch account manually in Playwright Chromium.",
        "",
        "## Windows Visible Browser CDP",
        f"- browser_mode: `{browser_mode}`",
        f"- report: `{WINDOWS_CDP_REPORT.relative_to(ROOT)}`",
        f"- windows_browser_found: `{value(data.windows_cdp, 'windows_browser_found', 'not_checked')}`",
        f"- browser_executable: `{value(data.windows_cdp, 'browser_executable', 'not_checked')}`",
        f"- user_data_dir: `{value(data.windows_cdp, 'user_data_dir', 'not_checked')}`",
        f"- remote_debugging_port: `{value(data.windows_cdp, 'remote_debugging_port', 'not_checked')}`",
        f"- cdp_connected: `{value(data.windows_cdp, 'cdp_connected', 'not_checked')}`",
        f"- visible_window_expected: `{value(data.windows_cdp, 'visible_window_expected', 'not_checked')}`",
        f"- detected_username: `{value(data.windows_cdp, 'detected_username', 'not_checked')}`",
        f"- account_guard_status: `{value(data.windows_cdp, 'account_guard_status', 'not_checked')}`",
        f"- persistence_confirmed: `{value(data.windows_cdp, 'persistence_confirmed', 'not_checked')}`",
        f"- next_step: `{value(data.windows_cdp, 'next_step', 'not_checked')}`",
        "- mode: dedicated Windows Chrome/Edge profile for ZerroOne only; no cookies are copied from normal browsers.",
        "- production_note: when `browser_mode=windows_cdp`, the legacy WSL `.browser-profile-zerroone` login state is diagnostic only and is not the blocker for CDP readiness.",
        "",
        "## ZerroOne Login Diagnostics",
        f"- report: `{LOGIN_DIAGNOSTICS_REPORT.relative_to(ROOT)}`",
        f"- login_wait_mode: `{value(data.login_diagnostics, 'login_wait_mode', 'not_checked')}`",
        f"- timeout_minutes: `{value(data.login_diagnostics, 'timeout_minutes', 'not_checked')}`",
        f"- poll_interval_seconds: `{value(data.login_diagnostics, 'poll_interval_seconds', 'not_checked')}`",
        f"- attempts_count: `{value(data.login_diagnostics, 'attempts_count', 'not_checked')}`",
        f"- last_url: `{value(data.login_diagnostics, 'last_url', 'not_checked')}`",
        f"- last_title: `{value(data.login_diagnostics, 'last_title', 'not_checked')}`",
        f"- final_detected_username: `{value(data.login_diagnostics, 'final_detected_username', 'not_checked')}`",
        f"- login_detected: `{value(data.login_diagnostics, 'login_detected', 'not_checked')}`",
        f"- account_guard_status: `{value(data.login_diagnostics, 'account_guard_status', 'not_checked')}`",
        f"- persistence_confirmed: `{value(data.login_diagnostics, 'persistence_confirmed', 'not_checked')}`",
        f"- next_manual_step: `{value(data.login_diagnostics, 'next_fix', 'not_checked')}`",
        "- mode: manual login only inside Playwright Chromium; no cookies are copied from normal browsers.",
        "",
        "## Account Switch",
        f"- report: `{ACCOUNT_SWITCH_REPORT.relative_to(ROOT)}`",
        f"- expected_username: `{value(data.account_switch, 'expected_username', guard_config.expected_username)}`",
        f"- active_browser_profile_path: `{value(data.account_switch, 'active_browser_profile_path', str(active_path))}`",
        f"- fallback_browser_profile_path: `{value(data.account_switch, 'fallback_browser_profile_path', str(fallback_path))}`",
        f"- wrong_profile_backup_path: `{value(data.account_switch, 'wrong_profile_backup_path', 'none')}`",
        f"- detected_username_before: `{value(data.account_switch, 'detected_username_before', 'not_checked')}`",
        f"- detected_username_after: `{value(data.account_switch, 'detected_username_after', 'not_checked')}`",
        f"- account_guard_status: `{value(data.account_switch, 'account_guard_status', 'not_checked')}`",
        f"- account_guard_action: `{value(data.account_switch, 'account_guard_action', 'not_checked')}`",
        "- mode: manual login/switch only; no credentials, SMS, save, publish, or send actions are automated.",
        "",
        "## Post-Phone Readiness",
        f"- report: `{POST_PHONE_REPORT.relative_to(ROOT)}`",
        f"- login_detected: `{value(data.post_phone, 'login_detected', 'not_checked')}`",
        f"- browser_mode: `{value(data.post_phone, 'browser_mode', 'not_checked')}`",
        f"- cdp_connected: `{value(data.post_phone, 'cdp_connected', 'not_checked')}`",
        f"- windows_cdp_user_data_dir: `{value(data.post_phone, 'windows_cdp_user_data_dir', 'not_checked')}`",
        f"- windows_cdp_port: `{value(data.post_phone, 'windows_cdp_port', 'not_checked')}`",
        f"- windows_cdp_final_url: `{value(data.post_phone, 'windows_cdp_final_url', 'not_checked')}`",
        f"- username: `{value(data.post_phone, 'username', 'not_checked')}`",
        f"- active_browser_profile_path: `{value(data.post_phone, 'active_browser_profile_path', str(active_path))}`",
        f"- fallback_browser_profile_path: `{value(data.post_phone, 'fallback_browser_profile_path', str(fallback_path))}`",
        f"- detected_username: `{value(data.post_phone, 'detected_username', 'not_checked')}`",
        f"- expected_username: `{value(data.post_phone, 'expected_username', guard_config.expected_username)}`",
        f"- account_guard_status: `{value(data.post_phone, 'account_guard_status', 'not_checked')}`",
        f"- account_guard_action: `{value(data.post_phone, 'account_guard_action', 'not_checked')}`",
        f"- phone_verification_detected: `{value(data.post_phone, 'phone_verification_detected', 'not_checked')}`",
        f"- create_kwork_accessible: `{value(data.post_phone, 'create_kwork_accessible', 'not_checked')}`",
        f"- seller_profile_accessible: `{value(data.post_phone, 'seller_profile_accessible', 'not_checked')}`",
        f"- can_continue_profile_setup: `{value(data.post_phone, 'can_continue_profile_setup', 'not_checked')}`",
        f"- can_continue_kwork_draft: `{value(data.post_phone, 'can_continue_kwork_draft', 'not_checked')}`",
        "- mode: read-only preview; no save/publish/send/final buttons are clicked.",
        "",
        "## CDP Fill Without Final Buttons",
        f"- profile_report: `{PROFILE_FILL_CDP_REPORT.relative_to(ROOT)}`",
        f"- profile_browser_mode: `{value(data.profile_fill_cdp, 'browser_mode', 'not_checked')}`",
        f"- profile_detected_username: `{value(data.profile_fill_cdp, 'detected_username', 'not_checked')}`",
        f"- profile_account_guard_status: `{value(data.profile_fill_cdp, 'account_guard_status', 'not_checked')}`",
        f"- profile_fields_filled: `{value(data.profile_fill_cdp, 'fields_filled', 'not_checked')}`",
        f"- profile_final_buttons_blocked: `{value(data.profile_fill_cdp, 'final_buttons_blocked', 'not_checked')}`",
        f"- profile_next_manual_action: `{value(data.profile_fill_cdp, 'user_next_step', 'not_checked')}`",
        f"- kwork_report: `{KWORK_FILL_CDP_REPORT.relative_to(ROOT)}`",
        f"- kwork_browser_mode: `{value(data.kwork_fill_cdp, 'browser_mode', 'not_checked')}`",
        f"- kwork_detected_username: `{value(data.kwork_fill_cdp, 'detected_username', 'not_checked')}`",
        f"- kwork_account_guard_status: `{value(data.kwork_fill_cdp, 'account_guard_status', 'not_checked')}`",
        f"- kwork_title: `{value(data.kwork_fill_cdp, 'kwork_title', 'not_checked')}`",
        f"- kwork_fields_filled: `{value(data.kwork_fill_cdp, 'fields_filled', 'not_checked')}`",
        f"- kwork_final_buttons_blocked: `{value(data.kwork_fill_cdp, 'final_buttons_blocked', 'not_checked')}`",
        f"- kwork_next_manual_action: `{value(data.kwork_fill_cdp, 'user_next_step', 'not_checked')}`",
        "- safety: CDP fill may populate safe fields, but never clicks save, publish, moderation, send, proposal, phone, withdrawal, delete, or confirmation buttons.",
        "",
        "## Kwork Production Studio",
        f"- studio_report: `{KWORK_STUDIO_REPORT.relative_to(ROOT)}`",
        f"- selected_kwork_title: `{value(data.kwork_studio, 'selected_kwork_title', 'not_checked')}`",
        f"- selected_positioning: `{value(data.kwork_studio, 'selected_positioning', 'not_checked')}`",
        f"- competitor_scan_report: `{KWORK_COMPETITOR_SCAN_REPORT.relative_to(ROOT)}`",
        f"- competitor_scan_status: `{value(data.competitor_scan, 'status', 'not_checked')}`",
        f"- competitors_count: `{value(data.competitor_scan, 'competitors_count', 'not_checked')}`",
        f"- cover_report: `{KWORK_COVER_STUDIO_REPORT.relative_to(ROOT)}`",
        f"- selected_cover: `{value(data.cover_studio, 'selected_cover', 'not_checked')}`",
        f"- human_prompt_report: `{KWORK_COVER_PROMPT_REPORT.relative_to(ROOT)}`",
        f"- prompt_count: `{value(data.cover_prompt, 'prompts_count', 'not_checked')}`",
        f"- inbox_report: `{KWORK_COVER_INBOX_REPORT.relative_to(ROOT)}`",
        f"- inbox_images_count: `{value(data.cover_inbox, 'images_count', 'not_checked')}`",
        f"- valid_inbox_images_count: `{value(data.cover_inbox, 'valid_images_count', 'not_checked')}`",
        f"- selection_report: `{KWORK_COVER_SELECTION_REPORT.relative_to(ROOT)}`",
        f"- selected_original: `{value(data.cover_selection, 'selected_original', 'not_checked')}`",
        f"- processed_report: `{KWORK_COVER_PROCESSED_REPORT.relative_to(ROOT)}`",
        f"- processed_cover: `{value(data.cover_processed, 'processed_file', 'not_checked')}`",
        f"- cover_upload_report: `{KWORK_COVER_UPLOAD_REPORT.relative_to(ROOT)}`",
        f"- cover_upload_attempted: `{value(data.cover_upload, 'upload_attempted', value(data.cover_upload, 'cover_uploaded', 'not_checked'))}`",
        f"- cover_upload_success: `{value(data.cover_upload, 'upload_success', 'not_checked')}`",
        f"- full_fill_report: `{KWORK_FULL_FILL_CDP_REPORT.relative_to(ROOT)}`",
        f"- full_fill_fields_filled: `{value(data.full_fill_cdp, 'fields_filled', 'not_checked')}`",
        f"- full_fill_fields_missing: `{value(data.full_fill_cdp, 'fields_missing', 'not_checked')}`",
        f"- full_fill_final_buttons_blocked: `{value(data.full_fill_cdp, 'final_buttons_blocked', 'not_checked')}`",
        f"- marketing_qa_report: `{KWORK_MARKETING_QA_REPORT.relative_to(ROOT)}`",
        f"- marketing_qa_score: `{value(data.marketing_qa, 'score', 'not_checked')}`",
        f"- marketing_qa_verdict: `{value(data.marketing_qa, 'verdict', 'not_checked')}`",
        f"- foreground_policy: `{value(data.full_fill_cdp, 'foreground_policy', value(data.competitor_scan, 'foreground_policy', 'not_checked'))}`",
        f"- brought_to_front_count: `{value(data.full_fill_cdp, 'brought_to_front_count', value(data.competitor_scan, 'brought_to_front_count', 'not_checked'))}`",
        f"- next_manual_step: `{value(data.marketing_qa, 'next_manual_step', value(data.full_fill_cdp, 'user_next_step', 'not_checked'))}`",
        "",
        "## Kwork Profile Audit",
        f"- live_report: `{KWORK_PROFILE_AUDIT_LIVE_REPORT.relative_to(ROOT)}`",
        f"- offline_report: `{KWORK_PROFILE_AUDIT_REPORT.relative_to(ROOT)}`",
        f"- live_status: `{value(data.profile_audit_live, 'data_collection_status', 'not_checked')}`",
        f"- found_kworks_count: `{value(data.profile_audit_live, 'kworks_collected', 'not_checked')}`",
        f"- latest_audit_verdict: `{value(data.profile_audit, 'verdict', value(data.profile_audit_live, 'data_collection_status', 'not_checked'))}`",
        f"- account_guard_status: `{value(data.profile_audit_live, 'account_guard_status', 'not_checked')}`",
        f"- final_buttons_clicked: `{value(data.profile_audit_live, 'final_buttons_clicked', 'not_checked')}`",
        f"- kwork_state_changed: `{value(data.profile_audit_live, 'kwork_state_changed', 'not_checked')}`",
        f"- next_manual_action: `{first_real('review generated audit and edit Kwork manually only', value(data.profile_audit_live, 'stopped_reason', ''))}`",
        "- mode: live collector is read-only; offline audit prepares recommendations and replacement text.",
        "",
        "## Kwork Inventory",
        f"- report: `{KWORK_INVENTORY_REPORT.relative_to(ROOT)}`",
        f"- total_kworks: `{value(data.kwork_inventory, 'total_current', 'not_checked')}`",
        f"- added: `{value(data.kwork_inventory, 'added', 'not_checked')}`",
        f"- missing_now: `{value(data.kwork_inventory, 'missing_now', 'not_checked')}`",
        f"- changed: `{value(data.kwork_inventory, 'changed', 'not_checked')}`",
        f"- unchanged: `{value(data.kwork_inventory, 'unchanged', 'not_checked')}`",
        f"- weakest_kwork: `{value(data.kwork_inventory, 'weakest_kwork', 'not_checked')}`",
        f"- next_manual_action: `{value(data.kwork_inventory, 'next_manual_action', 'run money:kwork-inventory, then review report manually')}`",
        "- mode: inventory is read-only and treats disappeared kworks as `missing_now`, not deleted.",
        "",
        "## Kwork List All",
        f"- report: `{KWORK_ALL_LIST_REPORT.relative_to(ROOT)}`",
        f"- collected_unique: `{value(data.kwork_all_list, 'collected_unique', 'not_checked')}`",
        f"- active_ui_count: `{value(data.kwork_all_list, 'active_ui_count', 'not_checked')}`",
        f"- drafts_ui_count: `{value(data.kwork_all_list, 'drafts_ui_count', 'not_checked')}`",
        f"- all_ui_count: `{value(data.kwork_all_list, 'all_ui_count', 'not_checked')}`",
        f"- collection_status: `{value(data.kwork_all_list, 'collection_status', 'not_checked')}`",
        "- mode: simple read-only export of visible Kwork list tabs.",
        "",
        "## Best Lead",
        f"- title: {best_title}",
        f"- url: {value(data.best, 'url')}",
        f"- buyer: {value(data.best, 'buyer')}",
        f"- recommended_price: {value(data.best, 'recommended_price')}",
        f"- deadline: {value(data.best, 'recommended_deadline')}",
        f"- verdict: {value(data.best, 'verdict')}",
        f"- risks: {extract_section_summary(read_text(BEST_REPORT), 'Risks')}",
        f"- why_best: {extract_section_summary(read_text(BEST_REPORT), 'Why This Lead Is Best')}",
        "",
        "## Top 5 Proposals",
        *(f"- {item}" for item in data.top5),
        "",
        "## Copy-Paste Proposal",
        f"- price: {data.proposal_price}",
        f"- deadline: {data.proposal_deadline}",
        "",
        "```text",
        data.proposal_text,
        "```",
        "",
        "### Client Questions",
        *(f"- {question}" for question in data.proposal_questions),
        "",
        "## Delivery Kit",
        f"- path: `{DELIVERY_KIT.relative_to(ROOT)}`",
        "",
        "### Files",
        *(f"- {item}" for item in data.delivery_files),
        "",
        "### What Is Ready",
        "- Client README, questions, tech plan, run instructions, checklist, final report template.",
        "- Google Sheets structure and Yandex Direct API notes.",
        "- Placeholder `.env` guidance with no real tokens.",
        "",
        "### What To Ask Client",
        *(f"- {question}" for question in data.delivery_questions),
        "",
        "### How To Execute",
        *(f"- {step}" for step in data.delivery_steps),
        "",
        "## Starter Template",
        f"- path: `{TEMPLATE_PATH.relative_to(ROOT)}`",
        "- mock mode: `.venv/bin/python src/main.py --mock`",
        "- tests: `.venv/bin/python -m unittest discover tests`",
        "- credentials needed from client: `YANDEX_DIRECT_TOKEN`, `YANDEX_CLIENT_LOGIN`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `SPREADSHEET_ID`.",
        "",
        "## Portfolio Pack",
        f"- status: `ready ({len(data.portfolio_cases)} demo cases)`",
        f"- index: `{PORTFOLIO_INDEX.relative_to(ROOT)}`",
        "- usage: manual profile/portfolio preparation only; not fake reviews or fake commercial orders.",
        "",
        "### Demo Cases",
        *(f"- {item}" for item in data.portfolio_cases),
        "",
        "### Manual Upload Checklist",
        *(f"- {item}" for item in data.portfolio_checklist),
        "",
        "## Offer Factory",
        f"- status: `ready ({len(data.offer_factory)} public-safe offers)`",
        f"- path: `{OFFER_FACTORY_DIR.relative_to(ROOT)}`",
        f"- report: `{OFFER_FACTORY_REPORT.relative_to(ROOT)}`",
        f"- recommended_first_offer: {data.recommended_first_offer or 'unknown'}",
        "- publication: manual-only after phone verification; do not automate final buttons.",
        "",
        "### Factory Offers",
        *(f"- {item}" for item in data.offer_factory),
        "",
        "## Order Executor",
        f"- status: `{data.order_executor_status}`",
        f"- latest_prepared_workspace: `{data.latest_order_workspace}`",
        f"- report: `{ORDER_EXECUTOR_REPORT.relative_to(ROOT)}`",
        "- mode: offline-only workspace generator; it does not accept orders or send messages.",
        "",
        "### After Getting An Order",
        *(f"- {item}" for item in data.order_executor_checklist),
        "",
        "## Manual-Only Checklist",
        *(f"- {item}" for item in MANUAL_ONLY),
        "",
        "## Safety",
        "- Dashboard is local-only and offline.",
        "- It does not send proposals or click Kwork buttons.",
        "- Runtime reports, proposal text, screenshots, and lead JSONL must not be committed.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def extract_section_summary(text: str, heading: str, limit: int = 3) -> str:
    pattern = re.compile(rf"##\s+{re.escape(heading)}\n(.*?)(?:\n##\s+|\Z)", re.S)
    match = pattern.search(text)
    if not match:
        return "unknown"
    items = [line.strip("- ").strip() for line in match.group(1).splitlines() if line.strip().startswith("-")]
    return "; ".join(items[:limit]) if items else "none"


def build_html(markdown: str) -> str:
    body_lines: list[str] = []
    in_code = False
    code_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("```"):
            if in_code:
                body_lines.append(f"<pre>{html.escape(chr(10).join(code_lines))}</pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("# "):
            body_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            body_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            body_lines.append(f"<p class=\"item\">{html.escape(line[2:])}</p>")
        elif not line.strip():
            body_lines.append("")
        else:
            body_lines.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"ru\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "<title>Kwork Operator Dashboard</title>",
            "<style>",
            "body{font-family:Georgia,'Times New Roman',serif;margin:0;background:#f6f0e6;color:#1f2a24;line-height:1.5}",
            "main{max-width:980px;margin:0 auto;padding:32px 20px 56px}",
            "h1{font-size:42px;margin:0 0 20px}h2{margin-top:34px;border-top:2px solid #d3c2a3;padding-top:18px}h3{margin-top:22px}",
            ".item{background:#fffaf0;border:1px solid #e0d1b5;border-radius:10px;padding:10px 12px;margin:8px 0}",
            "pre{white-space:pre-wrap;background:#18221d;color:#f8f2df;border-radius:14px;padding:18px;overflow:auto}",
            "code{background:#efe3cd;padding:2px 5px;border-radius:5px}",
            "</style>",
            "</head>",
            "<body><main>",
            *body_lines,
            "</main></body></html>",
        ]
    )


def write_dashboard() -> None:
    ensure_dir(REPORTS)
    data = collect_data()
    markdown = build_markdown(data)
    DASHBOARD_MD.write_text(markdown, encoding="utf-8")
    DASHBOARD_HTML.write_text(build_html(markdown), encoding="utf-8")
    print(f"operator_dashboard_md={DASHBOARD_MD}")
    print(f"operator_dashboard_html={DASHBOARD_HTML}")
    print(f"best_lead={value(data.best, 'project_title')}")
    print(f"login_detected={value(data.daily, 'login_detected')}")
    guard_config = load_account_guard_config()
    active_path, fallback_path = browser_profile_paths(guard_config)
    print(
        "active_browser_profile_path="
        + first_real(
            str(active_path),
            value(data.post_phone, "active_browser_profile_path", ""),
            value(data.account_switch, "active_browser_profile_path", ""),
            value(data.daily, "active_browser_profile_path", ""),
        )
    )
    print(
        "fallback_browser_profile_path="
        + first_real(
            str(fallback_path),
            value(data.post_phone, "fallback_browser_profile_path", ""),
            value(data.account_switch, "fallback_browser_profile_path", ""),
            value(data.daily, "fallback_browser_profile_path", ""),
        )
    )
    print(
        "detected_username="
        + (
            first_real(
                "not_checked",
                value(data.windows_cdp, "detected_username", ""),
                value(data.account_switch, "detected_username_after", ""),
                value(data.login_diagnostics, "final_detected_username", ""),
                value(data.post_phone, "detected_username", ""),
                value(data.daily, "detected_username", ""),
            )
        )
    )
    print(
        "account_guard_status="
        + (
            first_real(
                "not_checked",
                value(data.windows_cdp, "account_guard_status", ""),
                value(data.account_switch, "account_guard_status", ""),
                value(data.login_diagnostics, "account_guard_status", ""),
                value(data.post_phone, "account_guard_status", ""),
                value(data.daily, "account_guard_status", ""),
            )
        )
    )
    print(f"login_persistence_confirmed={value(data.login_diagnostics, 'persistence_confirmed', 'not_checked')}")
    print(f"windows_cdp_connected={value(data.windows_cdp, 'cdp_connected', 'not_checked')}")
    print(f"windows_cdp_persistence_confirmed={value(data.windows_cdp, 'persistence_confirmed', 'not_checked')}")
    print(f"phone_verification_detected={value(data.daily, 'phone_verification_detected')}")
    print(f"post_phone_verification_detected={value(data.post_phone, 'phone_verification_detected', 'not_checked')}")
    print(f"safe_shortlist_count={value(data.daily, 'safe_shortlist_count')}")
    print(f"offer_factory_count={len(data.offer_factory)}")
    print(f"order_executor_status={data.order_executor_status}")
    print(f"latest_order_workspace={data.latest_order_workspace}")
    print("sent=false")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="Build local operator dashboard")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.build:
        raise SystemExit("Use --build to generate the local dashboard.")
    write_dashboard()


if __name__ == "__main__":
    main()
