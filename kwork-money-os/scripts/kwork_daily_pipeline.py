#!/usr/bin/env python3
"""Daily no-phone lead pipeline for Kwork Money OS.

Pipeline stages:
1. Optional read-only Lead Radar browser scan in run mode.
2. Offline Lead Triage from saved JSONL.
3. Local daily dashboard report with top proposals.

The script never sends proposals, never clicks final Kwork actions, and keeps
phone/SMS/withdrawal/publish/message flows manual-only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from _common import DATA, REPORTS, ROOT, ensure_dir


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
REPO_ROOT = ROOT.parent
SCRIPTS = ROOT / "scripts"
LEADS_JSONL = DATA / "leads" / "kwork_leads.jsonl"
SHORTLIST_DIR = DATA / "leads" / "shortlist"
LEAD_RADAR_REPORT = REPORTS / "lead_radar_report.md"
LEAD_SHORTLIST_REPORT = REPORTS / "lead_shortlist.md"
TOP5_REPORT = REPORTS / "top_5_proposals.md"
PIPELINE_REPORT = REPORTS / "daily_lead_pipeline_report.md"

MANUAL_ONLY_ACTIONS = [
    "phone verification",
    "SMS code",
    "withdrawal setup",
    "proposal sending",
    "client messages",
    "kwork publication",
    "moderation submission",
    "profile save",
    "order accept/cancel/confirm",
    "delete/confirm flows",
]

BLOCKED_ACTIONS = [
    "Предложить услугу",
    "Отправить",
    "Отправить сообщение",
    "Опубликовать",
    "На модерацию",
    "Сохранить профиль",
    "Принять заказ",
    "Отменить заказ",
    "Подтвердить действие",
    "Удалить",
]


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def command_text(self) -> str:
        return " ".join(self.command)


@dataclass
class PipelineStatus:
    started_at: str
    mode: str
    hold: bool = False
    git_commit: str = ""
    login_detected: str = "not_checked"
    phone_verification_detected: str = "not_checked"
    leads_found: int = 0
    leads_after_dedup: int = 0
    high_risk_filtered: int = 0
    safe_shortlist_count: int = 0
    top_5: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    commands: list[CommandResult] = field(default_factory=list)


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
    remote = run_git(["remote", "get-url", "origin"])
    if git_root != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong git root: {git_root}. Expected: {EXPECTED_REPO_ROOT}")
    if REPO_ROOT != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong script root: {REPO_ROOT}. Expected: {EXPECTED_REPO_ROOT}")
    if remote != "git@github.com:Zerro15/browser-command-center.git":
        raise SystemExit(f"Wrong origin remote: {remote}")
    return run_git(["rev-parse", "HEAD"])


def run_command(command: list[str], *, allow_failure: bool = False) -> CommandResult:
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    command_result = CommandResult(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    if result.returncode != 0 and not allow_failure:
        raise SystemExit(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return command_result


def read_report_field(path: Path, field: str, default: str = "unknown") -> str:
    if not path.exists():
        return default
    pattern = re.compile(rf"-\s*{re.escape(field)}:\s*`?([^`\n]+)`?", re.I)
    match = pattern.search(path.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else default


def parse_int(value: str, default: int = 0) -> int:
    match = re.search(r"-?\d+", str(value))
    return int(match.group(0)) if match else default


def parse_triage_stdout(stdout: str) -> dict[str, int | list[dict[str, str]]]:
    values: dict[str, int | list[dict[str, str]]] = {
        "input_leads": 0,
        "deduplicated_projects": 0,
        "removed_high_risk": 0,
        "shortlist_count": 0,
        "top_5": [],
    }
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"input_leads", "deduplicated_projects", "removed_high_risk", "shortlist_count"}:
            values[key] = parse_int(value)
        elif re.fullmatch(r"top\d+", key):
            parts = [part.strip() for part in value.split(" | ")]
            if len(parts) >= 5:
                top_items = values["top_5"]
                assert isinstance(top_items, list)
                top_items.append(
                    {
                        "score": parts[0],
                        "price": parts[1],
                        "deadline": parts[2],
                        "title": parts[3],
                        "url": parts[4],
                    }
                )
    return values


def run_lead_radar(status: PipelineStatus) -> None:
    command = [sys.executable, str(SCRIPTS / "kwork_lead_radar.py"), "--run", "--approve"]
    if status.hold:
        command.append("--hold")
    result = run_command(command, allow_failure=True)
    status.commands.append(result)
    if not result.ok:
        status.warnings.append("Lead Radar returned a non-zero exit code; continuing offline triage from saved leads if available.")

    status.login_detected = read_report_field(LEAD_RADAR_REPORT, "login_detected", "unknown")
    status.phone_verification_detected = read_report_field(LEAD_RADAR_REPORT, "phone_verification_detected", "unknown")
    status.leads_found = parse_int(read_report_field(LEAD_RADAR_REPORT, "leads_found", "0"))


def run_lead_triage(status: PipelineStatus) -> None:
    if not LEADS_JSONL.exists():
        raise SystemExit(f"Saved Lead Radar JSONL is required for triage: {LEADS_JSONL}")
    command = [
        sys.executable,
        str(SCRIPTS / "kwork_lead_triage.py"),
        "--input",
        str(LEADS_JSONL),
        "--top",
        "10",
    ]
    result = run_command(command)
    status.commands.append(result)
    parsed = parse_triage_stdout(result.stdout)
    status.leads_found = status.leads_found or int(parsed["input_leads"])
    status.leads_after_dedup = int(parsed["deduplicated_projects"])
    status.high_risk_filtered = int(parsed["removed_high_risk"])
    status.safe_shortlist_count = int(parsed["shortlist_count"])
    top_items = parsed["top_5"]
    assert isinstance(top_items, list)
    status.top_5 = top_items[:5]


def write_daily_report(status: PipelineStatus) -> None:
    ensure_dir(REPORTS)
    blocked_confirmed = [f"{action}: blocked/not clicked" for action in BLOCKED_ACTIONS]
    lines = [
        "# Daily Lead Pipeline Report",
        "",
        f"- started_at: `{status.started_at}`",
        f"- mode: `{status.mode}`",
        f"- git_commit: `{status.git_commit}`",
        f"- login_detected: `{status.login_detected}`",
        f"- phone_verification_detected: `{status.phone_verification_detected}`",
        f"- leads_found: `{status.leads_found}`",
        f"- leads_after_dedup: `{status.leads_after_dedup}`",
        f"- high_risk_filtered: `{status.high_risk_filtered}`",
        f"- safe_shortlist_count: `{status.safe_shortlist_count}`",
        f"- proposal_files_path: `{SHORTLIST_DIR.relative_to(ROOT)}`",
        f"- top_5_report: `{TOP5_REPORT.relative_to(ROOT)}`",
        "",
        "## Top 5",
    ]
    if status.top_5:
        for index, item in enumerate(status.top_5, start=1):
            lines.append(
                f"{index}. [{item['title']}]({item['url']}) | {item['price']} | {item['deadline']} | score `{item['score']}`"
            )
    else:
        lines.append("- No safe top proposals are ready from the saved leads.")

    lines.extend(
        [
            "",
            "## What Is Ready After Phone",
            f"- Review `{LEAD_SHORTLIST_REPORT.relative_to(ROOT)}`.",
            f"- Copy-paste only from `{TOP5_REPORT.relative_to(ROOT)}` after phone verification is completed manually.",
            f"- Draft cards are in `{SHORTLIST_DIR.relative_to(ROOT)}`.",
            "- Re-check each buyer/project manually before sending anything.",
            "",
            "## Manual Only Actions",
            *(f"- {action}" for action in MANUAL_ONLY_ACTIONS),
            "",
            "## Blocked Actions Confirmed",
            *(f"- {action}" for action in blocked_confirmed),
            "",
            "## Commands",
            *(
                f"- `{command.command_text()}` -> exit `{command.returncode}`"
                for command in status.commands
            ),
            "",
            "## Warnings",
        ]
    )
    if status.warnings:
        lines.extend(f"- {warning}" for warning in status.warnings)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Safety",
            "- Dry-run mode never opens a browser.",
            "- Run mode uses Lead Radar read-only, then Lead Triage offline.",
            "- No proposals/messages were sent by this pipeline.",
            "- `Предложить услугу`, send, publish, moderation, save, phone/SMS, withdrawal, order and delete/confirm flows remain manual-only.",
            "- If phone verification is detected, the pipeline records it and continues only with offline triage from saved leads.",
        ]
    )
    PIPELINE_REPORT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the safe daily Kwork lead pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--run", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode = "dry-run" if args.dry_run else "run"
    if mode == "run" and not args.approve:
        raise SystemExit("--run requires --approve. The pipeline is still read-only/no-send.")

    status = PipelineStatus(
        started_at=datetime.now().isoformat(timespec="seconds"),
        mode=mode,
        hold=bool(args.hold),
        git_commit=validate_root(),
    )

    if mode == "run":
        run_lead_radar(status)
    else:
        status.login_detected = "not_checked_dry_run"
        status.phone_verification_detected = "not_checked_dry_run"
        if not LEADS_JSONL.exists():
            raise SystemExit(f"Dry-run requires saved leads: {LEADS_JSONL}")

    run_lead_triage(status)
    write_daily_report(status)

    print(f"daily_pipeline_report={PIPELINE_REPORT}")
    print(f"mode={status.mode}")
    print(f"login_detected={status.login_detected}")
    print(f"phone_verification_detected={status.phone_verification_detected}")
    print(f"leads_found={status.leads_found}")
    print(f"leads_after_dedup={status.leads_after_dedup}")
    print(f"high_risk_filtered={status.high_risk_filtered}")
    print(f"safe_shortlist_count={status.safe_shortlist_count}")
    print(f"top_5_report={TOP5_REPORT}")
    for index, item in enumerate(status.top_5, start=1):
        print(f"top{index}={item['score']} | {item['price']} | {item['deadline']} | {item['title']} | {item['url']}")


if __name__ == "__main__":
    main()
