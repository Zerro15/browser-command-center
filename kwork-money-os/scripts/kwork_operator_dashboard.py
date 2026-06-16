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

from _common import DATA, REPORTS, ROOT, ensure_dir


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


def build_markdown(data: DashboardData) -> str:
    best_title = value(data.best, "project_title")
    lines = [
        "# Kwork Operator Dashboard",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- git_commit: `{data.git_commit}`",
        "",
        "## Current Status",
        f"- login_detected: `{value(data.daily, 'login_detected')}`",
        f"- phone_verification_detected: `{value(data.daily, 'phone_verification_detected')}`",
        f"- post_phone_verification_detected: `{value(data.post_phone, 'phone_verification_detected', 'not_checked')}`",
        f"- leads_found: `{value(data.daily, 'leads_found')}`",
        f"- safe_shortlist_count: `{value(data.daily, 'safe_shortlist_count')}`",
        f"- best_lead_of_day: {best_title}",
        f"- portfolio_pack_status: `ready ({len(data.portfolio_cases)} demo cases)`",
        f"- offer_factory_status: `ready ({len(data.offer_factory)} offers)`",
        f"- order_executor_status: `{data.order_executor_status}`",
        "",
        "## Post-Phone Readiness",
        f"- report: `{POST_PHONE_REPORT.relative_to(ROOT)}`",
        f"- login_detected: `{value(data.post_phone, 'login_detected', 'not_checked')}`",
        f"- username: `{value(data.post_phone, 'username', 'not_checked')}`",
        f"- phone_verification_detected: `{value(data.post_phone, 'phone_verification_detected', 'not_checked')}`",
        f"- create_kwork_accessible: `{value(data.post_phone, 'create_kwork_accessible', 'not_checked')}`",
        f"- seller_profile_accessible: `{value(data.post_phone, 'seller_profile_accessible', 'not_checked')}`",
        f"- can_continue_profile_setup: `{value(data.post_phone, 'can_continue_profile_setup', 'not_checked')}`",
        f"- can_continue_kwork_draft: `{value(data.post_phone, 'can_continue_kwork_draft', 'not_checked')}`",
        "- mode: read-only preview; no save/publish/send/final buttons are clicked.",
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
