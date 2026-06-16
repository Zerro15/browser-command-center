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
    phone_verification_detected: bool = False
    create_kwork_accessible: bool = False
    seller_profile_accessible: bool = False
    can_continue_profile_setup: bool = False
    can_continue_kwork_draft: bool = False
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


def detect_username(bridge: KworkRpaBridge) -> str:
    if not bridge.available:
        return "unknown"
    try:
        candidates = bridge.page.evaluate(
            """() => {
              const values = [];
              for (const link of Array.from(document.querySelectorAll('a[href*="/user/"]'))) {
                try {
                  const url = new URL(link.href, location.href);
                  const match = url.pathname.match(/^\\/user\\/([^/?#]+)/);
                  if (match && match[1]) values.push(decodeURIComponent(match[1]));
                } catch (_) {}
              }
              const current = location.pathname.match(/^\\/user\\/([^/?#]+)/);
              if (current && current[1]) values.push(decodeURIComponent(current[1]));
              return Array.from(new Set(values)).slice(0, 20);
            }"""
        )
    except Exception:
        candidates = []
    for candidate in candidates:
        if candidate == EXPECTED_USERNAME:
            return candidate
    return candidates[0] if candidates else "unknown"


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
        f"- phone_verification_detected: `{str(status.phone_verification_detected).lower()}`",
        f"- create_kwork_accessible: `{str(status.create_kwork_accessible).lower()}`",
        f"- seller_profile_accessible: `{str(status.seller_profile_accessible).lower()}`",
        f"- can_continue_profile_setup: `{str(status.can_continue_profile_setup).lower()}`",
        f"- can_continue_kwork_draft: `{str(status.can_continue_kwork_draft).lower()}`",
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
                status.username = detect_username(bridge)
            elif status.login_detected != "true" and item.login_detected == "true":
                status.login_detected = "true"
            if status.username == "unknown":
                status.username = detect_username(bridge)
        status.screenshots = list(report.screenshots)
        status.warnings = list(report.warnings)
        by_name = {item.name: item for item in status.pages}
        status.create_kwork_accessible = by_name.get("create_kwork", PageCheck("", "")).accessible
        status.seller_profile_accessible = by_name.get("seller_profile", PageCheck("", "")).accessible
        status.can_continue_profile_setup = by_name.get("profile_settings", PageCheck("", "")).accessible and not status.phone_verification_detected
        status.can_continue_kwork_draft = status.create_kwork_accessible and not status.phone_verification_detected
        write_report(status)
        report.write(REPORTS / "post_phone_readiness_bridge_report.md")
        if hold:
            bridge.hold_open()
    print(REPORT_PATH)
    print(f"login_detected={status.login_detected}")
    print(f"username={status.username}")
    print(f"phone_verification_detected={str(status.phone_verification_detected).lower()}")
    print(f"create_kwork_accessible={str(status.create_kwork_accessible).lower()}")
    print(f"seller_profile_accessible={str(status.seller_profile_accessible).lower()}")
    print(f"can_continue_profile_setup={str(status.can_continue_profile_setup).lower()}")
    print(f"can_continue_kwork_draft={str(status.can_continue_kwork_draft).lower()}")
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
