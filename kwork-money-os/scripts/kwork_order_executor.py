#!/usr/bin/env python3
"""Prepare local execution workspaces for future Kwork orders.

This tool is offline-only. It does not open Kwork, accept orders, send
messages, publish offers, or click any final action buttons.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir, slugify


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
REPO_ROOT = ROOT.parent
OFFER_FACTORY = DATA / "offers" / "factory"
BEST_PROPOSAL = DATA / "leads" / "best_lead_of_day_proposal.md"
BEST_REPORT = REPORTS / "best_lead_of_day.md"
TEMPLATES = ROOT / "templates"
YANDEX_DIRECT_TEMPLATE = TEMPLATES / "yandex_direct_sheets_exporter"
PREPARED_ROOT = DATA / "orders" / "prepared"
ORDER_REPORT = REPORTS / "order_executor_report.md"

MANUAL_ONLY = [
    "Accepting Kwork orders is manual-only.",
    "Sending messages and proposals is manual-only.",
    "Phone/SMS verification is manual-only.",
    "Publishing, moderation, profile save, and withdrawal setup are manual-only.",
    "Do not store real tokens, passwords, cookies, sessions, or client private data in git.",
]


@dataclass
class OrderSource:
    source_type: str
    source_path: str
    title: str
    url: str
    buyer: str
    price: str
    deadline: str
    summary: str
    questions: list[str]
    scope: list[str]
    risks: list[str]
    forbidden_scope: list[str]
    is_yandex_direct_sheets: bool


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
        raise SystemExit(f"Missing required input: {path}")
    return path.read_text(encoding="utf-8")


def parse_report_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"-\s+([^:]+):\s+`?([^`\n]+)`?", line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def extract_section_items(text: str, heading: str, limit: int = 12) -> list[str]:
    pattern = re.compile(rf"##\s+{re.escape(heading)}\n(.*?)(?:\n##\s+|\Z)", re.S)
    match = pattern.search(text)
    if not match:
        return []
    items = [line.strip("- ").strip() for line in match.group(1).splitlines() if line.strip().startswith("-")]
    return items[:limit]


def parse_proposal_questions(text: str) -> list[str]:
    proposal_match = re.search(r"## Final Proposal Text\n\n(.*?)(?:\n##\s+|\Z)", text, re.S)
    proposal = proposal_match.group(1) if proposal_match else text
    numbered = re.findall(r"^\d+\.\s+(.+\?)$", proposal, re.M)
    return numbered[:3] or extract_section_items(text, "3 Clarifying Questions", limit=3)


def is_yandex_direct_sheets(title: str, text: str = "") -> bool:
    haystack = f"{title}\n{text}".lower()
    return (
        ("яндекс" in haystack or "yandex" in haystack)
        and ("direct" in haystack or "директ" in haystack)
        and ("google" in haystack or "таблиц" in haystack or "sheets" in haystack)
    )


def workspace_slug(source: OrderSource) -> str:
    if source.is_yandex_direct_sheets:
        return "yandex_direct_sheets"
    raw = source.title
    if source.source_type == "offer":
        raw = Path(source.source_path).stem
    return slugify(raw)[:80]


def load_best_lead() -> OrderSource:
    report_text = read_text(BEST_REPORT)
    proposal_text = read_text(BEST_PROPOSAL)
    fields = parse_report_fields(report_text)
    title = fields.get("project_title", "Best lead")
    return OrderSource(
        source_type="best_lead",
        source_path=str(BEST_REPORT.relative_to(ROOT)),
        title=title,
        url=fields.get("url", ""),
        buyer=fields.get("buyer", "unknown"),
        price=fields.get("recommended_price", ""),
        deadline=fields.get("recommended_deadline", ""),
        summary="Prepared from Best Lead of Day. This is a local execution plan only; no Kwork order is accepted.",
        questions=parse_proposal_questions(report_text),
        scope=extract_section_items(report_text, "Execution Plan", limit=8),
        risks=extract_section_items(report_text, "Risks", limit=8),
        forbidden_scope=[
            "asking for passwords",
            "storing real API tokens in git",
            "using private account data without explicit client consent",
            "bypassing platform/API limits",
        ],
        is_yandex_direct_sheets=is_yandex_direct_sheets(title, report_text + proposal_text),
    )


def load_offer(path: Path) -> OrderSource:
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"Offer not found: {path}")
    offer: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    title = str(offer.get("title", path.stem))
    questions = [str(item) for item in offer.get("buyer_questions", [])]
    checklist = [str(item) for item in offer.get("delivery_checklist", [])]
    risks = [str(item) for item in offer.get("risk_notes", [])]
    forbidden = [str(item) for item in offer.get("forbidden_scope", [])]
    return OrderSource(
        source_type="offer",
        source_path=str(path.relative_to(ROOT)),
        title=title,
        url="",
        buyer="future_client",
        price=f"{offer.get('price_standard', offer.get('price_economy', 'TBD'))} ₽",
        deadline=f"{offer.get('delivery_days_standard', offer.get('delivery_days_economy', 'TBD'))} days",
        summary=str(offer.get("short_description", "")),
        questions=questions[:8],
        scope=checklist[:10],
        risks=risks[:8],
        forbidden_scope=forbidden[:10],
        is_yandex_direct_sheets=is_yandex_direct_sheets(title, str(offer.get("full_description", ""))),
    )


def required_inputs() -> list[tuple[str, Path, bool]]:
    return [
        ("offer factory", OFFER_FACTORY, OFFER_FACTORY.exists() and any(OFFER_FACTORY.glob("*.json"))),
        ("best lead proposal", BEST_PROPOSAL, BEST_PROPOSAL.exists()),
        ("best lead report", BEST_REPORT, BEST_REPORT.exists()),
        ("templates", TEMPLATES, TEMPLATES.exists()),
    ]


def dry_run() -> None:
    validate_root()
    print("Kwork Order Executor dry-run")
    print("mode=offline_only")
    for label, path, ok in required_inputs():
        print(f"{label}: {'ok' if ok else 'missing'} ({path})")
    print("")
    print("Can generate:")
    print("- prepared workspace from Best Lead of Day")
    print("- prepared workspace from one Offer Factory JSON")
    print("- local report at reports/order_executor_report.md")
    print("")
    print("Safety:")
    for item in MANUAL_ONLY:
        print(f"- {item}")
    print("sent=false")


def md_list(items: list[str], fallback: str = "To be clarified with client.") -> str:
    values = items or [fallback]
    return "\n".join(f"- {item}" for item in values)


def write_file(path: Path, text: str, created: list[str], workspace: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    created.append(str(path.relative_to(workspace)))


def env_example_for(source: OrderSource) -> str:
    if source.is_yandex_direct_sheets:
        return """
YANDEX_DIRECT_TOKEN=...
YANDEX_CLIENT_LOGIN=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
SPREADSHEET_ID=...
REPORT_DATE_FROM=YYYY-MM-DD
REPORT_DATE_TO=YYYY-MM-DD
DRY_RUN=true
"""
    return """
PROJECT_NAME=...
CLIENT_CONTACT=...
API_TOKEN_PLACEHOLDER=...
GOOGLE_SPREADSHEET_ID=...
DRY_RUN=true
"""


def build_workspace(source: OrderSource) -> tuple[Path, list[str], list[str]]:
    validate_root()
    workspace = PREPARED_ROOT / f"{date.today().isoformat()}_{workspace_slug(source)}"
    ensure_dir(workspace)
    created: list[str] = []
    missing_inputs = [
        "manual Kwork order confirmation",
        "client-approved scope",
        "client-created API tokens/accesses if integration is needed",
        "test data without private secrets",
    ]

    write_file(
        workspace / "00_README.md",
        f"""
# Prepared Order Workspace

- source_type: `{source.source_type}`
- source_path: `{source.source_path}`
- title: {source.title}
- buyer: {source.buyer}
- url: {source.url or "not applicable"}
- recommended_price: {source.price or "TBD"}
- recommended_deadline: {source.deadline or "TBD"}
- status: `prepared_not_accepted`

This workspace is for offline preparation only. It does not mean the order has been accepted, started, or messaged on Kwork.
""",
        created,
        workspace,
    )
    write_file(
        workspace / "01_CLIENT_QUESTIONS.md",
        f"""
# Client Questions

Ask only after the order is manually confirmed and communication is allowed.

{md_list(source.questions)}

Do not ask for passwords. Ask for client-created API tokens, service account access, or test data only when required for the agreed scope.
""",
        created,
        workspace,
    )
    write_file(
        workspace / "02_SCOPE_AND_LIMITS.md",
        f"""
# Scope And Limits

## Proposed Scope

{md_list(source.scope)}

## Limits

{md_list(source.forbidden_scope, fallback="No unsafe or unclear work without manual review.")}

## Manual Confirmation Required

{md_list(MANUAL_ONLY)}
""",
        created,
        workspace,
    )
    write_file(
        workspace / "03_TECH_PLAN.md",
        f"""
# Tech Plan

## Summary

{source.summary}

## Steps

{md_list(source.scope)}

## Access Handling

- Use placeholders in files.
- Keep real tokens in a local `.env` only after client provides them safely.
- Never commit real credentials, cookies, sessions, phone numbers, or private client data.
""",
        created,
        workspace,
    )
    write_file(
        workspace / "04_TASK_CHECKLIST.md",
        f"""
# Task Checklist

- Confirm order manually on Kwork before starting paid work.
- Confirm scope, price, deadline, and acceptance criteria.
- Collect only required API tokens/accesses from the client.
- Build the smallest working version first.
- Test with mock or safe test data.
- Prepare final delivery report and handoff notes.
- Ask client to verify results manually.
""",
        created,
        workspace,
    )
    write_file(
        workspace / "05_ACCEPTANCE_CRITERIA.md",
        f"""
# Acceptance Criteria

- Client can run or verify the prepared workflow using the provided instructions.
- Required outputs are generated on test or client-approved data.
- No secrets are stored in git or public files.
- Known limits and next steps are documented.
- Final delivery includes README, checklist, and report template.
""",
        created,
        workspace,
    )
    write_file(
        workspace / "06_DELIVERY_REPORT_TEMPLATE.md",
        f"""
# Delivery Report Template

## What Was Done

- TBD after manual order acceptance.

## How To Run

- TBD after implementation.

## What Client Should Check

- Outputs match the agreed acceptance criteria.
- Accesses can be rotated after delivery if needed.

## Limits

{md_list(source.risks, fallback="No major risks documented yet.")}
""",
        created,
        workspace,
    )
    write_file(
        workspace / "07_HANDOFF_MESSAGE.md",
        f"""
# Handoff Message Draft

Здравствуйте!

Подготовил структуру выполнения по задаче: `{source.title}`.

Перед началом работ нужно вручную подтвердить заказ, согласовать объём и безопасно передать только необходимые доступы/API-токены. Пароли не нужны.

После выполнения передам инструкцию запуска, чеклист проверки и краткий отчёт по ограничениям.

Status: draft only, not sent.
""",
        created,
        workspace,
    )
    write_file(
        workspace / "08_RISK_NOTES.md",
        f"""
# Risk Notes

{md_list(source.risks, fallback="No major risks detected in the source.")}

## Always Forbidden

{md_list(source.forbidden_scope, fallback="Unsafe actions require manual review and should be declined if unclear.")}
""",
        created,
        workspace,
    )
    write_file(workspace / ".env.example", env_example_for(source), created, workspace)
    write_file(
        workspace / "project" / "README.md",
        f"""
# Project Workspace

This folder is reserved for implementation files after a real order is manually accepted.

Current source:

- `{source.source_type}`
- `{source.source_path}`

Keep this folder free of real credentials. Use `.env.example` as the only committed-style reference.
""",
        created,
        workspace,
    )

    if source.is_yandex_direct_sheets:
        write_file(
            workspace / "project" / "START_HERE.md",
            f"""
# Start Here

Use the public-safe starter template as the base:

```text
{YANDEX_DIRECT_TEMPLATE.relative_to(ROOT)}
```

Recommended first steps after manual order acceptance:

1. Copy or reference the template locally.
2. Fill `.env` from client-created API access values.
3. Run mock mode before real API calls.
4. Confirm Google Sheets output structure with the client.
""",
            created,
            workspace,
        )
        write_file(
            workspace / "project" / "CLIENT_ACCESS_NEEDED.md",
            """
# Client Access Needed

Do not ask for account passwords.

Ask the client to prepare:

- `YANDEX_DIRECT_TOKEN`;
- `YANDEX_CLIENT_LOGIN`;
- Google service account JSON or shared spreadsheet access;
- `SPREADSHEET_ID`;
- report period and required metrics;
- test account/data confirmation if available.
""",
            created,
            workspace,
        )

    write_report(source, workspace, created, missing_inputs)
    return workspace, created, missing_inputs


def write_report(source: OrderSource, workspace: Path, created: list[str], missing_inputs: list[str]) -> None:
    ensure_dir(REPORTS)
    report = [
        "# Kwork Order Executor Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- source: `{source.source_type}`",
        f"- source_path: `{source.source_path}`",
        f"- generated_workspace_path: `{workspace}`",
        f"- order_status: `not_accepted`",
        f"- kwork_touched: `false`",
        f"- messages_sent: `false`",
        "",
        "## Files Created",
        *(f"- {item}" for item in created),
        "",
        "## Missing Inputs",
        *(f"- {item}" for item in missing_inputs),
        "",
        "## Next Manual Steps",
        "- Complete phone/SMS verification manually if still required.",
        "- Accept or discuss the order manually on Kwork only when ready.",
        "- Send messages manually only after it is allowed and appropriate.",
        "- Collect client-created API tokens/accesses without passwords.",
        "- Keep real `.env` and client data out of git.",
        "",
        "## Safety Status",
        *(f"- {item}" for item in MANUAL_ONLY),
    ]
    ORDER_REPORT.write_text("\n".join(report).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview available inputs without creating a workspace")
    parser.add_argument("--from-best-lead", action="store_true", help="Build workspace from Best Lead of Day")
    parser.add_argument("--offer", help="Build workspace from one Offer Factory JSON")
    parser.add_argument("--build", action="store_true", help="Create the prepared order workspace")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        dry_run()
        return
    if not args.build:
        raise SystemExit("Use --dry-run or --build with --from-best-lead/--offer.")
    if args.from_best_lead and args.offer:
        raise SystemExit("Choose only one source: --from-best-lead or --offer.")
    if args.from_best_lead:
        source = load_best_lead()
    elif args.offer:
        source = load_offer(Path(args.offer))
    else:
        raise SystemExit("Use --from-best-lead or --offer <path> with --build.")
    workspace, created, missing_inputs = build_workspace(source)
    print(f"workspace={workspace}")
    print(f"files_created={len(created)}")
    print(f"missing_inputs={len(missing_inputs)}")
    print(f"report={ORDER_REPORT}")
    print("kwork_touched=false")
    print("messages_sent=false")


if __name__ == "__main__":
    main()
