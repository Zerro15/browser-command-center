#!/usr/bin/env python3
"""Check whether visible Playwright Chromium can be used from WSL."""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from _common import REPORTS, ROOT, ensure_dir
from account_guard import active_browser_profile_path


REPORT_PATH = REPORTS / "playwright_gui_diagnostics_report.md"
TEST_URL = "https://example.com"


@dataclass
class GuiDiagnostics:
    running_in_wsl: bool = False
    display: str = ""
    wayland_display: str = ""
    xdg_runtime_dir: str = ""
    wslg_available: bool = False
    headless_false_support: bool = False
    profile_path: str = ""
    profile_writable: bool = False
    playwright_import_ok: bool = False
    browser_executable_path: str = "unknown"
    current_user: str = ""
    cwd: str = ""
    gui_available: bool = False
    headed_launch_success: bool = False
    browser_window_expected: bool = False
    browser_process_started: bool = False
    reason_if_not_visible: str = ""
    next_fix: str = ""
    opened_url: str = "not_opened"
    final_url: str = "not_opened"
    page_title: str = "not_opened"
    warnings: list[str] = field(default_factory=list)


def bool_text(value: bool) -> str:
    return str(bool(value)).lower()


def detect_wsl() -> bool:
    try:
        text = Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        text = ""
    return "microsoft" in text or "wsl" in text or bool(os.environ.get("WSL_DISTRO_NAME"))


def profile_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        marker = path / ".gui-diagnostics-marker"
        marker.write_text(datetime.now().isoformat(timespec="seconds") + "\n", encoding="utf-8")
        return marker.exists()
    except Exception:
        return False


def collect_check() -> GuiDiagnostics:
    result = GuiDiagnostics()
    result.running_in_wsl = detect_wsl()
    result.display = os.environ.get("DISPLAY", "")
    result.wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    result.xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "")
    result.wslg_available = Path("/mnt/wslg").exists()
    result.current_user = getpass.getuser()
    result.cwd = str(Path.cwd())
    profile = active_browser_profile_path()
    result.profile_path = str(profile)
    result.profile_writable = profile_writable(profile)
    try:
        from playwright.sync_api import sync_playwright

        result.playwright_import_ok = True
        with sync_playwright() as playwright:
            result.browser_executable_path = playwright.chromium.executable_path
    except Exception as error:
        result.warnings.append(f"Playwright import/executable check failed: {error}")
    result.headless_false_support = bool(
        result.playwright_import_ok
        and result.running_in_wsl
        and result.profile_writable
        and (result.display or result.wayland_display)
    )
    result.gui_available = bool(result.headless_false_support and result.wslg_available)
    if result.gui_available:
        result.reason_if_not_visible = "none"
        result.next_fix = "run npm run money:gui-open-test and confirm the visible Chromium window"
    elif not result.running_in_wsl:
        result.reason_if_not_visible = "not running in WSL"
        result.next_fix = "run from the real WSL project, not the Windows/Codex temp folder"
    elif not result.wslg_available:
        result.reason_if_not_visible = "/mnt/wslg is missing"
        result.next_fix = "enable WSLg or run from a Windows session with GUI support"
    elif not (result.display or result.wayland_display):
        result.reason_if_not_visible = "DISPLAY/WAYLAND_DISPLAY are empty"
        result.next_fix = "restart WSL/WSLg or export a valid display before launching Playwright"
    elif not result.playwright_import_ok:
        result.reason_if_not_visible = "Playwright is not importable in the venv"
        result.next_fix = "install Playwright into kwork-money-os/.venv and install Chromium"
    elif not result.profile_writable:
        result.reason_if_not_visible = ".browser-profile-zerroone is not writable"
        result.next_fix = "fix WSL project/profile permissions"
    else:
        result.reason_if_not_visible = "unknown GUI preflight failure"
        result.next_fix = "inspect reports/playwright_gui_diagnostics_report.md and WSLg logs"
    return result


def open_test(result: GuiDiagnostics, hold: bool) -> GuiDiagnostics:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            result.browser_process_started = True
            result.headed_launch_success = True
            result.browser_window_expected = True
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            result.opened_url = TEST_URL
            page.goto(TEST_URL, wait_until="load", timeout=20_000)
            result.final_url = page.url
            result.page_title = page.title()
            if result.gui_available:
                result.next_fix = "if the user saw the Chromium window, run npm run money:login-zerroone"
            write_report(result)
            print("Visible Chromium test window opened with https://example.com.")
            if hold:
                if sys.stdin.isatty():
                    input("Confirm you can see Chromium, then press Enter to close...")
                else:
                    print("stdin is non-interactive; holding the test window for 10 minutes or until Ctrl+C.")
                    time.sleep(600)
            browser.close()
    except KeyboardInterrupt:
        result.warnings.append("Open-test interrupted by user/Ctrl+C.")
    except Exception as error:
        result.headed_launch_success = False
        result.browser_window_expected = False
        result.reason_if_not_visible = f"headed Chromium launch failed: {error}"
        result.next_fix = "fix WSLg/DISPLAY/Playwright Chromium before running Kwork login"
        result.warnings.append(result.reason_if_not_visible)
    result.gui_available = bool(result.gui_available and result.headed_launch_success)
    if result.headed_launch_success and result.next_fix.startswith("run npm run money:gui-open-test"):
        result.next_fix = "if the user saw the Chromium window, run npm run money:login-zerroone"
    write_report(result)
    return result


def write_report(result: GuiDiagnostics) -> None:
    ensure_dir(REPORT_PATH.parent)
    lines = [
        "# Playwright GUI Diagnostics Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- running_in_wsl: `{bool_text(result.running_in_wsl)}`",
        f"- DISPLAY: `{result.display or 'empty'}`",
        f"- WAYLAND_DISPLAY: `{result.wayland_display or 'empty'}`",
        f"- XDG_RUNTIME_DIR: `{result.xdg_runtime_dir or 'empty'}`",
        f"- /mnt/wslg: `{bool_text(result.wslg_available)}`",
        f"- headless_false_support: `{bool_text(result.headless_false_support)}`",
        f"- profile_path: `{result.profile_path}`",
        f"- profile_writable: `{bool_text(result.profile_writable)}`",
        f"- playwright_import_ok: `{bool_text(result.playwright_import_ok)}`",
        f"- browser_executable_path: `{result.browser_executable_path}`",
        f"- current_user: `{result.current_user}`",
        f"- cwd: `{result.cwd}`",
        f"- gui_available: `{bool_text(result.gui_available)}`",
        f"- wslg_available: `{bool_text(result.wslg_available)}`",
        f"- headed_launch_success: `{bool_text(result.headed_launch_success)}`",
        f"- browser_window_expected: `{bool_text(result.browser_window_expected)}`",
        f"- browser_process_started: `{bool_text(result.browser_process_started)}`",
        f"- opened_url: `{result.opened_url}`",
        f"- final_url: `{result.final_url}`",
        f"- page_title: `{result.page_title}`",
        f"- reason_if_not_visible: `{result.reason_if_not_visible or 'none'}`",
        f"- next_fix: `{result.next_fix or 'none'}`",
        "",
        "## Warnings",
        *(f"- {item}" for item in result.warnings),
        "",
        "## Safety",
        "- This diagnostic opens only https://example.com in --open-test mode.",
        "- It does not open Kwork, read cookies, log in, type credentials, or click final buttons.",
    ]
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_check() -> GuiDiagnostics:
    result = collect_check()
    write_report(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose visible Playwright Chromium support in WSL")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--open-test", action="store_true")
    parser.add_argument("--hold", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.check and not args.open_test:
        raise SystemExit("Use --check or --open-test.")
    result = run_check()
    if args.open_test:
        result = open_test(result, hold=args.hold)
    print(REPORT_PATH)
    print(f"gui_available={bool_text(result.gui_available)}")
    print(f"wslg_available={bool_text(result.wslg_available)}")
    print(f"headed_launch_success={bool_text(result.headed_launch_success)}")
    print(f"browser_window_expected={bool_text(result.browser_window_expected)}")
    print(f"browser_process_started={bool_text(result.browser_process_started)}")
    print(f"reason_if_not_visible={result.reason_if_not_visible or 'none'}")
    print(f"next_fix={result.next_fix or 'none'}")


if __name__ == "__main__":
    main()
