#!/usr/bin/env python3
"""Read-only Windows CDP previews for Kwork working flows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from _common import REPORTS, ROOT, ensure_dir
from account_optimizer_common import PROFILE_SETTINGS_URL
from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL


REPORT_PATH = REPORTS / "cdp_preview_report.md"
PROJECTS_URL = "https://kwork.ru/projects"


TARGETS = {
    "profile": PROFILE_SETTINGS_URL,
    "kwork": DEFAULT_DRAFT_URL,
    "lead-radar": PROJECTS_URL,
    "daily-leads": PROJECTS_URL,
}


@dataclass
class PreviewResult:
    target: str
    url: str
    final_url: str = ""
    page_title: str = "unknown"
    browser_mode: str = "windows_cdp"
    cdp_connected: str = "false"
    login_detected: str = "unknown"
    detected_username: str = "unknown"
    account_guard_status: str = "not_checked"
    account_guard_action: str = "not_checked"
    phone_verification_detected: bool = False
    blocked_buttons_visible: list[str] | None = None
    screenshot: str = ""
    next_safe_command: str = "not_checked"


def write_report(result: PreviewResult, diagnostics) -> None:
    ensure_dir(REPORT_PATH.parent)
    blocked = result.blocked_buttons_visible or []
    lines = [
        "# Kwork Windows CDP Preview Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- target: `{result.target}`",
        f"- browser_mode: `{result.browser_mode}`",
        f"- cdp_connected: `{result.cdp_connected}`",
        f"- browser_executable: `{diagnostics.browser_executable}`",
        f"- user_data_dir: `{diagnostics.user_data_dir}`",
        f"- remote_debugging_port: `{diagnostics.remote_debugging_port}`",
        f"- opened_url: `{result.url}`",
        f"- final_url: `{result.final_url}`",
        f"- page_title: `{result.page_title}`",
        f"- login_detected: `{result.login_detected}`",
        f"- detected_username: `{result.detected_username}`",
        f"- expected_username: `{EXPECTED_ACCOUNT}`",
        f"- account_guard_status: `{result.account_guard_status}`",
        f"- account_guard_action: `{result.account_guard_action}`",
        f"- phone_verification_detected: `{str(result.phone_verification_detected).lower()}`",
        f"- blocked_buttons_visible: `{', '.join(blocked) if blocked else 'none'}`",
        f"- screenshot: `{result.screenshot or 'none'}`",
        f"- next_safe_command: `{result.next_safe_command}`",
        "",
        "## Safety",
        "- Read-only Windows CDP preview only.",
        "- Uses the dedicated Windows profile for ZerroOne, not the user's normal browser.",
        "- Does not read cookies, passwords, tokens, local storage, or credentials.",
        "- Does not type login/password/SMS and does not click save/publish/send/final buttons.",
        "- Fill commands require separate confirmation and are intentionally not executed by this preview.",
    ]
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_preview(target: str) -> PreviewResult:
    url = TARGETS[target]
    result = PreviewResult(target=target, url=url)
    with open_kwork_browser_session(mode="windows_cdp", account=EXPECTED_ACCOUNT, start_url=MANAGE_KWORKS_URL) as session:
        session.open(url)
        diag = session.refresh_diagnostics()
        blocked = session.find_blocked_buttons()
        result.final_url = diag.current_url
        result.page_title = diag.page_title
        result.cdp_connected = str(diag.cdp_connected).lower()
        result.login_detected = diag.login_detected
        result.detected_username = diag.detected_username
        result.account_guard_status = diag.account_guard_status
        result.account_guard_action = diag.account_guard_action
        result.phone_verification_detected = bool(
            "new_phone_verify=1" in result.final_url or PHONE_VERIFICATION_RE.search(session.visible_text())
        )
        result.blocked_buttons_visible = blocked
        result.screenshot = session.screenshot(f"cdp-preview-{target}")
        if diag.account_guard_status == "ok":
            result.next_safe_command = "manual review; fill/send/save/publish still require separate human confirmation"
        else:
            result.next_safe_command = "stop: switch/login to ZerroOne in dedicated Windows CDP profile"
        write_report(result, diag)
    print(REPORT_PATH)
    print(f"target={result.target}")
    print(f"browser_mode={result.browser_mode}")
    print(f"cdp_connected={result.cdp_connected}")
    print(f"login_detected={result.login_detected}")
    print(f"detected_username={result.detected_username}")
    print(f"account_guard_status={result.account_guard_status}")
    print(f"account_guard_action={result.account_guard_action}")
    print(f"phone_verification_detected={str(result.phone_verification_detected).lower()}")
    print(f"final_url={result.final_url}")
    print(f"blocked_buttons_visible={', '.join(result.blocked_buttons_visible or []) or 'none'}")
    print(f"next_safe_command={result.next_safe_command}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe read-only Windows CDP previews for Kwork Money OS")
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_preview(args.target)


if __name__ == "__main__":
    main()
