#!/usr/bin/env python3
"""Read-only post-phone readiness check for Kwork Money OS."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from _common import REPORTS, ROOT, ensure_dir
from account_optimizer_common import PROFILE_SETTINGS_URL, SELLER_PROFILE_URL
from account_guard import apply_account_guard_to_report, evaluate_account_guard
from browser_rpa_bridge import (
    DEFAULT_DRAFT_URL,
    KWORK_HOME_URL,
    PHONE_VERIFICATION_RE,
    KworkRpaBridge,
    RpaReport,
)


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
EXPECTED_USERNAME = "ZerroOne"
REPO_ROOT = ROOT.parent
REPORT_PATH = REPORTS / "post_phone_readiness_report.md"
SCREENSHOT_ROOT = REPORTS / "screenshots"

MANUAL_ONLY = [
    "Profile save is manual-only.",
    "Kwork publication and moderation are manual-only.",
    "Proposal sending and messages are manual-only.",
    "Order acceptance/cancellation is manual-only.",
    "Phone/SMS and withdrawal setup stay manual-only.",
    "Final submit/save/publish/send/delete buttons must not be clicked by automation.",
]


@dataclass
class PageCheck:
    name: str
    url: str
    final_url: str = ""
    title: str = ""
    login_detected: str = "unknown"
    phone_verification_detected: bool = False
    accessible: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReadinessStatus:
    git_commit: str = ""
    login_detected: str = "unknown"
    username: str = "unknown"
    active_browser_profile_path: str = ""
    fallback_browser_profile_path: str = ""
    detected_username: str = "unknown"
    expected_username: str = EXPECTED_USERNAME
    allowed_usernames: str = ""
    account_guard_status: str = "not_checked"
    account_guard_action: str = "not_checked"
    account_guard_message: str = ""
    phone_verification_detected: bool = False
    create_kwork_accessible: bool = False
    seller_profile_accessible: bool = False
    can_continue_profile_setup: bool = False
    can_continue_kwork_draft: bool = False
    profile_ready_to_save_manually: bool = False
    kwork_draft_ready_to_continue: bool = False
    screenshots: list[str] = field(default_factory=list)
    pages: list[PageCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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


def apply_guard(status: ReadinessStatus, bridge: KworkRpaBridge) -> None:
    result = evaluate_account_guard(bridge.detect_public_username())
    apply_account_guard_to_report(bridge.report, result)
    status.username = result.detected_username
    status.active_browser_profile_path = bridge.report.active_browser_profile_path
    status.fallback_browser_profile_path = bridge.report.fallback_browser_profile_path
    status.detected_username = result.detected_username
    status.expected_username = result.expected_username
    status.allowed_usernames = ", ".join(result.allowed_usernames)
    status.account_guard_status = result.account_guard_status
    status.account_guard_action = result.account_guard_action
    status.account_guard_message = result.account_guard_message
    if not result.ok:
        bridge.report.warn(result.account_guard_message)
        status.warnings.append(result.account_guard_message)
        bridge.wait_and_screenshot("post-phone-account-guard-stop")


def page_has_kwork_form(bridge: KworkRpaBridge) -> bool:
    if not bridge.available:
        return False
    try:
        data = bridge.page.evaluate(
            """() => {
              const text = document.body ? document.body.innerText : '';
              const fields = Array.from(document.querySelectorAll('input, textarea, select, [contenteditable="true"]'))
                .filter((el) => {
                  const rect = el.getBoundingClientRect();
                  const style = getComputedStyle(el);
                  return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                }).length;
              return {text, fields};
            }"""
        )
    except Exception:
        return False
    text = str(data.get("text") or "")
    field_count = int(data.get("fields") or 0)
    if PHONE_VERIFICATION_RE.search(text):
        return False
    return field_count > 0 and bool(re.search(r"кворк|назван|описан|стоим|рубри", text, re.I))


def check_page(bridge: KworkRpaBridge, name: str, url: str) -> PageCheck:
    item = PageCheck(name=name, url=url)
    bridge.open(url)
    item.final_url = bridge.page.url if bridge.available else ""
    item.login_detected = bridge.report.login_detected
    login_state = bridge.detect_login_state()
    item.login_detected = bridge.report.login_detected
    item.phone_verification_detected = bridge.detect_phone_verification_required()
    try:
        item.title = bridge.page.title()[:160] if bridge.available else ""
    except Exception:
        item.title = ""
    if name == "create_kwork":
        item.accessible = bool(login_state is True and not item.phone_verification_detected and page_has_kwork_form(bridge))
    elif name == "profile_settings":
        item.accessible = bool(login_state is True and not item.phone_verification_detected)
    elif name == "seller_profile":
        item.accessible = bool(not item.phone_verification_detected and "404" not in item.title.lower())
    else:
        item.accessible = bool(login_state is True and not item.phone_verification_detected)
    blocked = bridge.find_blocked_buttons()
    if blocked:
        item.warnings.append(f"blocked final/action buttons visible and not clicked: {', '.join(blocked)}")
    bridge.wait_and_screenshot(f"post-phone-{name}")
    return item


def write_report(status: ReadinessStatus) -> None:
    ensure_dir(REPORT_PATH.parent)
    lines = [
        "# Post-Phone Kwork Readiness Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- git_commit: `{status.git_commit}`",
        f"- login_detected: `{status.login_detected}`",
        f"- username: `{status.username}`",
        f"- active_browser_profile_path: `{status.active_browser_profile_path or 'unknown'}`",
        f"- fallback_browser_profile_path: `{status.fallback_browser_profile_path or 'unknown'}`",
        f"- detected_username: `{status.detected_username}`",
        f"- expected_username: `{status.expected_username}`",
        f"- allowed_usernames: `{status.allowed_usernames or 'unknown'}`",
        f"- account_guard_status: `{status.account_guard_status}`",
        f"- account_guard_action: `{status.account_guard_action}`",
        f"- account_guard_message: `{status.account_guard_message or 'none'}`",
        f"- phone_verification_detected: `{str(status.phone_verification_detected).lower()}`",
        f"- create_kwork_accessible: `{str(status.create_kwork_accessible).lower()}`",
        f"- seller_profile_accessible: `{str(status.seller_profile_accessible).lower()}`",
        f"- can_continue_profile_setup: `{str(status.can_continue_profile_setup).lower()}`",
        f"- can_continue_kwork_draft: `{str(status.can_continue_kwork_draft).lower()}`",
        f"- profile_ready_to_save_manually: `{str(status.profile_ready_to_save_manually).lower()}`",
        f"- kwork_draft_ready_to_continue: `{str(status.kwork_draft_ready_to_continue).lower()}`",
        f"- screenshots_path: `{SCREENSHOT_ROOT.relative_to(ROOT)}`",
        "",
        "## Pages Checked",
    ]
    for page in status.pages:
        lines.extend(
            [
                f"- {page.name}: accessible={str(page.accessible).lower()} login={page.login_detected} phone={str(page.phone_verification_detected).lower()} url=`{page.final_url}`",
            ]
        )
        for warning in page.warnings:
            lines.append(f"  - warning: {warning}")
    lines.extend(
        [
            "",
            "## Screenshots",
            *(f"- `{item}`" for item in status.screenshots),
            "",
            "## Warnings",
            *(f"- {item}" for item in status.warnings),
            "",
            "## Manual-Only Actions",
            *(f"- {item}" for item in MANUAL_ONLY),
            "",
            "## Safety",
            "- Read-only/preview check only.",
            "- Account Guard stops profile/kwork/lead browser work unless detected_username matches expected_username.",
            "- No profile save, publish, moderation, send, order, phone/SMS, withdrawal, or delete actions were clicked.",
            "- Username detection uses public profile/navigation links only; email, password, cookies, tokens, and session state are not read into the report.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_preview(hold: bool) -> ReadinessStatus:
    status = ReadinessStatus(git_commit=validate_root())
    report = RpaReport(mode="post-phone-readiness:preview", target_url=KWORK_HOME_URL, title="Post-Phone Kwork Readiness")
    with KworkRpaBridge(report) as bridge:
        checks = [
            ("home", KWORK_HOME_URL),
            ("profile_settings", PROFILE_SETTINGS_URL),
            ("seller_profile", SELLER_PROFILE_URL),
            ("create_kwork", DEFAULT_DRAFT_URL),
        ]
        for name, url in checks:
            item = check_page(bridge, name, url)
            status.pages.append(item)
            status.phone_verification_detected = status.phone_verification_detected or item.phone_verification_detected
            if name == "home":
                status.login_detected = item.login_detected
                apply_guard(status, bridge)
            elif status.login_detected != "true" and item.login_detected == "true":
                status.login_detected = "true"
            if status.username == "unknown":
                apply_guard(status, bridge)
        status.screenshots = list(report.screenshots)
        status.warnings = list(report.warnings)
        by_name = {item.name: item for item in status.pages}
        status.create_kwork_accessible = by_name.get("create_kwork", PageCheck("", "")).accessible
        status.seller_profile_accessible = by_name.get("seller_profile", PageCheck("", "")).accessible
        account_guard_ok = status.account_guard_status == "ok"
        status.can_continue_profile_setup = (
            by_name.get("profile_settings", PageCheck("", "")).accessible
            and not status.phone_verification_detected
            and account_guard_ok
        )
        status.can_continue_kwork_draft = status.create_kwork_accessible and not status.phone_verification_detected and account_guard_ok
        status.profile_ready_to_save_manually = status.can_continue_profile_setup
        status.kwork_draft_ready_to_continue = status.can_continue_kwork_draft
        write_report(status)
        report.write(REPORTS / "post_phone_readiness_bridge_report.md")
        if hold:
            bridge.hold_open()
    print(REPORT_PATH)
    print(f"login_detected={status.login_detected}")
    print(f"username={status.username}")
    print(f"active_browser_profile_path={status.active_browser_profile_path}")
    print(f"fallback_browser_profile_path={status.fallback_browser_profile_path}")
    print(f"detected_username={status.detected_username}")
    print(f"expected_username={status.expected_username}")
    print(f"account_guard_status={status.account_guard_status}")
    print(f"account_guard_action={status.account_guard_action}")
    print(f"phone_verification_detected={str(status.phone_verification_detected).lower()}")
    print(f"create_kwork_accessible={str(status.create_kwork_accessible).lower()}")
    print(f"seller_profile_accessible={str(status.seller_profile_accessible).lower()}")
    print(f"can_continue_profile_setup={str(status.can_continue_profile_setup).lower()}")
    print(f"can_continue_kwork_draft={str(status.can_continue_kwork_draft).lower()}")
    print(f"profile_ready_to_save_manually={str(status.profile_ready_to_save_manually).lower()}")
    print(f"kwork_draft_ready_to_continue={str(status.kwork_draft_ready_to_continue).lower()}")
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--hold", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.preview:
        raise SystemExit("Use --preview for the read-only post-phone readiness check.")
    run_preview(args.hold)


if __name__ == "__main__":
    main()
