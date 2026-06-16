#!/usr/bin/env python3
"""Open a dedicated Windows-visible Chrome/Edge profile and connect via CDP."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import CONFIG, REPORTS, ROOT, ensure_dir, load_yaml
from account_guard import evaluate_account_guard, normalize_username


REPORT_PATH = REPORTS / "windows_visible_browser_cdp_report.md"
SCREENSHOT_DIR = REPORTS / "screenshots"
TEST_URL = "https://example.com"
KWORK_LOGIN_URL = "https://kwork.ru/login"
MANAGE_KWORKS_URL = "https://kwork.ru/manage_kworks"
EXPECTED_ACCOUNT = "ZerroOne"
DEFAULT_PORT = 9223


@dataclass
class CdpAttempt:
    index: int
    login_detected: str
    detected_username: str
    account_guard_status: str
    final_url: str
    page_title: str


@dataclass
class CdpReport:
    mode: str
    windows_browser_found: bool = False
    browser_executable: str = "unknown"
    user_data_dir: str = "unknown"
    remote_debugging_port: int = 0
    cdp_connected: bool = False
    opened_url: str = "not_opened"
    final_url: str = "not_opened"
    page_title: str = "not_opened"
    visible_window_expected: bool = False
    account: str = EXPECTED_ACCOUNT
    login_detected: str = "unknown"
    detected_username: str = "unknown"
    account_guard_status: str = "not_checked"
    account_guard_action: str = "not_checked"
    persistence_confirmed: bool = False
    browser_process_started: bool = False
    attempts_count: int = 0
    screenshots: list[str] = field(default_factory=list)
    error_summary: str = "none"
    next_step: str = "not_checked"
    attempts: list[CdpAttempt] = field(default_factory=list)
    foreground_policy: str = "normal"
    background_mode: bool = False
    brought_to_front_count: int = 0


def ps_json(command: str) -> Any:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"PowerShell exited {result.returncode}")
    text = result.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def windows_info() -> dict[str, Any]:
    ps = r"""
$candidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$browser = $null
foreach ($item in $candidates) {
  if ($item -and (Test-Path -LiteralPath $item)) { $browser = $item; break }
}
$local = $env:LOCALAPPDATA
$profile = Join-Path $local "KworkMoneyOS\ChromeProfiles\ZerroOne"
New-Item -ItemType Directory -Force -Path $profile | Out-Null
[pscustomobject]@{
  browser = $browser
  localAppData = $local
  profile = $profile
  user = $env:USERNAME
} | ConvertTo-Json -Compress
"""
    data = ps_json(ps)
    if not isinstance(data, dict):
        raise RuntimeError("PowerShell did not return Windows browser info")
    return data


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def choose_port(start: int) -> int:
    port = int(start)
    while port < start + 50:
        if not is_port_open(port):
            return port
        port += 1
    raise RuntimeError(f"No free localhost CDP port found from {start}")


def existing_cdp_port(start: int) -> int | None:
    for port in range(int(start), int(start) + 50):
        if wait_cdp(port, timeout_seconds=1):
            return port
    return None


def wait_cdp(port: int, timeout_seconds: int = 25) -> bool:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.5)
    return False


def launch_windows_browser(
    executable: str,
    profile: str,
    port: int,
    url: str,
    background: bool = False,
    no_focus: bool = False,
    minimized: bool = False,
) -> None:
    args = [
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        url,
    ]
    args_json = json.dumps(args)
    exe_json = json.dumps(executable)
    window_style = "Minimized" if background or minimized or no_focus else "Normal"
    ps = f"""
$exe = {exe_json}
$args = ConvertFrom-Json @'
{args_json}
'@
Start-Process -FilePath $exe -ArgumentList $args -WindowStyle {window_style} | Out-Null
[pscustomobject]@{{started=$true}} | ConvertTo-Json -Compress
"""
    ps_json(ps)


def import_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright


def visible_text(page) -> str:
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''") or ""
    except Exception:
        return ""


def detect_login_state(page) -> str:
    url = (page.url or "").lower()
    title = ""
    try:
        title = page.title()
    except Exception:
        title = ""
    text = visible_text(page)
    if "login" in url or "signin" in url or "Вход" in title:
        return "false"
    if any(path in url for path in ("/manage_kworks", "/settings", "/inbox", "/manage_orders")):
        return "true"
    if "Войти" in text and ("Регистрация" in text or "Зарегистрироваться" in text):
        return "false"
    if any(marker in text for marker in ("Сообщения", "Заказы", "Мои кворки", "Баланс")):
        return "true"
    return "unknown"


def detect_username(page, expected: str) -> str:
    login = detect_login_state(page)
    try:
        data = page.evaluate(
            """(expected) => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const usernameFromHref = (href) => {
                try {
                  const url = new URL(href, location.href);
                  const match = url.pathname.match(/^\\/user\\/([^/?#]+)/);
                  return match && match[1] ? decodeURIComponent(match[1]) : '';
                } catch (_) { return ''; }
              };
              const header = Array.from(document.querySelectorAll([
                'header a[href*="/user/"]',
                '.header a[href*="/user/"]',
                '[class*="user-menu"] a[href*="/user/"]',
                '[class*="avatar"] a[href*="/user/"]'
              ].join(','))).filter(visible).map((a) => usernameFromHref(a.href || a.getAttribute('href') || '')).filter(Boolean);
              const current = (location.pathname.match(/^\\/user\\/([^/?#]+)/) || [])[1] || '';
              const text = document.body ? document.body.innerText : '';
              const title = document.title || '';
              const escaped = expected ? expected.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') : '';
              const expectedRe = escaped ? new RegExp('(^|\\\\b|@)' + escaped + '(\\\\b|$)', 'i') : null;
              return {
                current,
                header,
                isLoginPage: /\\/login|\\/signin/i.test(location.pathname),
                is404: /404|страница не найдена|page not found/i.test(title + '\\n' + text),
                expectedVisible: expectedRe ? expectedRe.test(title + '\\n' + text) : false
              };
            }""",
            expected,
        )
    except Exception:
        data = {}
    if login == "true":
        for raw in data.get("header") or []:
            username = normalize_username(raw)
            if username != "unknown":
                return username
    current = normalize_username(data.get("current"))
    if (
        current.lower() == expected.lower()
        and not data.get("isLoginPage")
        and not data.get("is404")
        and data.get("expectedVisible")
    ):
        return expected
    return "unknown"


def screenshot(page, name: str, report: CdpReport) -> None:
    ensure_dir(SCREENSHOT_DIR)
    path = SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True, timeout=10_000)
        report.screenshots.append(str(path.relative_to(ROOT)))
    except Exception:
        pass


def check_page(page, report: CdpReport, expected: str) -> None:
    report.final_url = page.url
    try:
        report.page_title = page.title()
    except Exception:
        report.page_title = "unknown"
    report.login_detected = detect_login_state(page)
    report.detected_username = detect_username(page, expected)
    guard = evaluate_account_guard(
        report.detected_username,
        expected_username=expected,
        login_detected=report.login_detected,
    )
    report.account_guard_status = guard.account_guard_status
    report.account_guard_action = guard.account_guard_action


def open_cdp(report: CdpReport):
    sync_playwright = import_playwright()
    playwright = sync_playwright().start()
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{report.remote_debugging_port}")
    report.cdp_connected = True
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    return playwright, browser, page


def prepare_browser(report: CdpReport, url: str, background: bool = False, no_focus: bool = False, minimized: bool = False) -> bool:
    report.background_mode = bool(background or no_focus or minimized)
    report.foreground_policy = "minimized_no_focus" if report.background_mode else "normal"
    report.brought_to_front_count = 0
    info = windows_info()
    report.browser_executable = str(info.get("browser") or "unknown")
    report.user_data_dir = str(info.get("profile") or "unknown")
    report.windows_browser_found = bool(info.get("browser"))
    if not report.windows_browser_found:
        report.error_summary = "No Windows Chrome/Edge executable found"
        report.next_step = "Install Chrome or Edge, then rerun money:win-browser-test"
        return False
    existing_port = existing_cdp_port(DEFAULT_PORT)
    if existing_port:
        report.remote_debugging_port = existing_port
        report.browser_process_started = True
        report.visible_window_expected = True
        return True
    port = choose_port(DEFAULT_PORT)
    report.remote_debugging_port = port
    launch_windows_browser(
        report.browser_executable,
        report.user_data_dir,
        port,
        url,
        background=background,
        no_focus=no_focus,
        minimized=minimized,
    )
    report.browser_process_started = True
    report.visible_window_expected = True
    if not wait_cdp(port):
        report.error_summary = f"CDP endpoint did not become available on port {port}"
        report.next_step = "Check Windows browser launch/remote debugging permissions"
        return False
    return True


def run_open_test(hold: bool) -> CdpReport:
    report = CdpReport(mode="open-test", opened_url=TEST_URL, account=EXPECTED_ACCOUNT)
    if prepare_browser(report, TEST_URL):
        playwright = browser = None
        try:
            playwright, browser, page = open_cdp(report)
            page.goto(TEST_URL, wait_until="load", timeout=20_000)
            check_page(page, report, EXPECTED_ACCOUNT)
            screenshot(page, "windows-cdp-open-test", report)
            report.error_summary = "none"
            report.next_step = "if the user saw the Windows Chrome/Edge window, run npm run money:win-login-zerroone"
            write_report(report)
            print("Windows visible browser test opened https://example.com.")
            if hold:
                if sys.stdin.isatty():
                    input("Confirm the Windows Chrome/Edge window is visible, then press Enter...")
                else:
                    print("stdin is non-interactive; holding test window for 10 minutes or until Ctrl+C.")
                    time.sleep(600)
        except KeyboardInterrupt:
            report.error_summary = "open-test interrupted"
        except Exception as error:
            report.error_summary = str(error)
            report.next_step = "fix Windows CDP launch/connect before login"
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass
    write_report(report)
    return report


def run_check_zerroone(restart_check: bool = False) -> CdpReport:
    report = CdpReport(mode="check-zerroone", opened_url=f"https://kwork.ru/user/{EXPECTED_ACCOUNT}", account=EXPECTED_ACCOUNT)
    if prepare_browser(report, f"https://kwork.ru/user/{EXPECTED_ACCOUNT}"):
        playwright = browser = None
        try:
            playwright, browser, page = open_cdp(report)
            page.goto(f"https://kwork.ru/user/{EXPECTED_ACCOUNT}", wait_until="commit", timeout=20_000)
            page.wait_for_timeout(1200)
            check_page(page, report, EXPECTED_ACCOUNT)
            screenshot(page, "windows-cdp-check-zerroone", report)
            if restart_check and report.account_guard_status == "ok":
                browser.close()
                playwright.stop()
                if not prepare_browser(report, MANAGE_KWORKS_URL):
                    report.persistence_confirmed = False
                    return report
                playwright, browser, page = open_cdp(report)
                page.goto(MANAGE_KWORKS_URL, wait_until="commit", timeout=20_000)
                page.wait_for_timeout(1200)
                check_page(page, report, EXPECTED_ACCOUNT)
                report.persistence_confirmed = report.account_guard_status == "ok"
            report.next_step = (
                "run read-only post-phone/dashboard checks"
                if report.persistence_confirmed
                else "finish manual ZerroOne login in dedicated Windows browser profile"
            )
            report.error_summary = "none"
        except Exception as error:
            report.error_summary = str(error)
            report.next_step = "fix Windows CDP check before automation"
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass
    write_report(report)
    return report


def run_login_zerroone(hold: bool, timeout_minutes: int = 30, poll_interval: int = 5) -> CdpReport:
    report = CdpReport(mode="login-zerroone", opened_url=KWORK_LOGIN_URL, account=EXPECTED_ACCOUNT)
    if not prepare_browser(report, KWORK_LOGIN_URL):
        write_report(report)
        return report
    playwright = browser = None
    try:
        playwright, browser, page = open_cdp(report)
        page.goto(KWORK_LOGIN_URL, wait_until="commit", timeout=20_000)
        print(
            "Войди вручную именно в ZerroOne в этом отдельном Windows Chrome/Edge окне. "
            "Не используй Яндекс.Браузер. Скрипт будет проверять вход через CDP."
        )
        deadline = time.monotonic() + timeout_minutes * 60
        while time.monotonic() <= deadline:
            check_page(page, report, EXPECTED_ACCOUNT)
            attempt = CdpAttempt(
                index=len(report.attempts) + 1,
                login_detected=report.login_detected,
                detected_username=report.detected_username,
                account_guard_status=report.account_guard_status,
                final_url=report.final_url,
                page_title=report.page_title,
            )
            report.attempts.append(attempt)
            print(
                f"win_cdp_login_attempt={attempt.index} login_detected={attempt.login_detected} "
                f"detected_username={attempt.detected_username} status={attempt.account_guard_status} url={attempt.final_url}"
            )
            write_report(report)
            if report.account_guard_status == "ok":
                break
            if report.detected_username not in ("unknown", EXPECTED_ACCOUNT):
                screenshot(page, "windows-cdp-blocked-account", report)
                report.next_step = "switch to ZerroOne in the dedicated Windows browser profile"
                write_report(report)
                return report
            time.sleep(poll_interval)
        if report.account_guard_status == "ok":
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            report = run_check_zerroone(restart_check=True)
            report.mode = "login-zerroone"
        else:
            report.error_summary = "timeout waiting for manual ZerroOne login"
            report.next_step = "complete manual login in the dedicated Windows Chrome/Edge window and rerun"
    except Exception as error:
        report.error_summary = str(error)
        report.next_step = "fix Windows CDP login flow before automation"
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass
    report.attempts_count = len(report.attempts)  # type: ignore[attr-defined]
    write_report(report)
    return report


def write_report(report: CdpReport) -> None:
    ensure_dir(REPORT_PATH.parent)
    lines = [
        "# Windows Visible Browser CDP Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- mode: `{report.mode}`",
        f"- windows_browser_found: `{str(report.windows_browser_found).lower()}`",
        f"- browser_executable: `{report.browser_executable}`",
        f"- user_data_dir: `{report.user_data_dir}`",
        f"- remote_debugging_port: `{report.remote_debugging_port}`",
        f"- cdp_connected: `{str(report.cdp_connected).lower()}`",
        f"- opened_url: `{report.opened_url}`",
        f"- final_url: `{report.final_url}`",
        f"- page_title: `{report.page_title}`",
        f"- visible_window_expected: `{str(report.visible_window_expected).lower()}`",
        f"- foreground_policy: `{report.foreground_policy}`",
        f"- background_mode: `{str(report.background_mode).lower()}`",
        f"- brought_to_front_count: `{report.brought_to_front_count}`",
        f"- browser_process_started: `{str(report.browser_process_started).lower()}`",
        f"- detected_username: `{report.detected_username}`",
        f"- account_guard_status: `{report.account_guard_status}`",
        f"- account_guard_action: `{report.account_guard_action}`",
        f"- persistence_confirmed: `{str(report.persistence_confirmed).lower()}`",
        f"- attempts_count: `{len(report.attempts)}`",
        f"- error_summary: `{report.error_summary}`",
        f"- next_step: `{report.next_step}`",
        "",
        "## Attempts",
        *((
            f"- attempt {item.index}: login_detected=`{item.login_detected}`, "
            f"detected_username=`{item.detected_username}`, status=`{item.account_guard_status}`, "
            f"url=`{item.final_url}`, title=`{item.page_title}`"
        ) for item in report.attempts),
        "",
        "## Screenshots",
        *(f"- `{item}`" for item in report.screenshots),
        "",
        "## Safety",
        "- Uses a dedicated Windows Chrome/Edge user-data-dir for Kwork Money OS / ZerroOne.",
        "- Does not connect to the user's normal browser profile.",
        "- Does not read cookies, local storage, passwords, tokens, or credentials.",
        "- Does not type login/password/SMS and does not click save/publish/send/final buttons.",
    ]
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windows visible browser CDP bridge for Kwork Money OS")
    parser.add_argument("--open-test", action="store_true")
    parser.add_argument("--login-zerroone", action="store_true")
    parser.add_argument("--check-zerroone", action="store_true")
    parser.add_argument("--hold", action="store_true")
    parser.add_argument("--timeout-minutes", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.open_test:
        report = run_open_test(args.hold)
    elif args.login_zerroone:
        report = run_login_zerroone(args.hold, timeout_minutes=args.timeout_minutes)
    elif args.check_zerroone:
        report = run_check_zerroone(restart_check=True)
    else:
        raise SystemExit("Use --open-test, --login-zerroone, or --check-zerroone.")
    print(REPORT_PATH)
    print(f"windows_browser_found={str(report.windows_browser_found).lower()}")
    print(f"browser_executable={report.browser_executable}")
    print(f"user_data_dir={report.user_data_dir}")
    print(f"remote_debugging_port={report.remote_debugging_port}")
    print(f"cdp_connected={str(report.cdp_connected).lower()}")
    print(f"visible_window_expected={str(report.visible_window_expected).lower()}")
    print(f"opened_url={report.opened_url}")
    print(f"final_url={report.final_url}")
    print(f"detected_username={report.detected_username}")
    print(f"account_guard_status={report.account_guard_status}")
    print(f"persistence_confirmed={str(report.persistence_confirmed).lower()}")
    print(f"error_summary={report.error_summary}")
    print(f"next_step={report.next_step}")


if __name__ == "__main__":
    main()
