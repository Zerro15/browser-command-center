#!/usr/bin/env python3
"""Shared safe browser session helpers for Kwork Money OS.

The Windows CDP backend connects only to the dedicated Kwork Money OS
Chrome/Edge profile. It must not read cookies, passwords, tokens, local
storage, or connect to the user's normal browser profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from _common import REPORTS, ROOT, ensure_dir
from account_guard import AccountGuardResult, evaluate_account_guard, load_account_guard_config
from browser_rpa_bridge import KworkRpaBridge, RpaReport
from windows_visible_browser_cdp import (
    CdpReport,
    DEFAULT_PORT,
    EXPECTED_ACCOUNT,
    MANAGE_KWORKS_URL,
    detect_login_state as cdp_detect_login_state,
    detect_username as cdp_detect_username,
    prepare_browser,
)


SCREENSHOT_DIR = REPORTS / "screenshots"


@dataclass
class BrowserSessionDiagnostics:
    browser_mode: str
    account: str
    cdp_connected: bool = False
    browser_executable: str = "unknown"
    user_data_dir: str = "unknown"
    remote_debugging_port: int = DEFAULT_PORT
    active_browser_profile_path: str = "unknown"
    fallback_browser_profile_path: str = "unknown"
    current_url: str = "not_opened"
    page_title: str = "unknown"
    login_detected: str = "unknown"
    detected_username: str = "unknown"
    account_guard_status: str = "not_checked"
    account_guard_action: str = "not_checked"
    account_guard_message: str = ""
    screenshots: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class KworkBrowserSession:
    """Open a safe Kwork browser session in WSL Playwright or Windows CDP mode."""

    def __init__(
        self,
        mode: str = "windows_cdp",
        account: str = EXPECTED_ACCOUNT,
        start_url: str = MANAGE_KWORKS_URL,
        title: str = "Kwork Browser Session",
        keep_open: bool = False,
    ) -> None:
        self.mode = mode
        self.account = account
        self.start_url = start_url
        self.title = title
        self.keep_open = keep_open
        self.diagnostics = BrowserSessionDiagnostics(browser_mode=mode, account=account)
        self.bridge: KworkRpaBridge | None = None
        self.bridge_context: Any = None
        self.playwright: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None
        self._created_page = False

    def __enter__(self) -> "KworkBrowserSession":
        if self.mode == "windows_cdp":
            report = CdpReport(mode="browser-session", opened_url=self.start_url, account=self.account)
            if not prepare_browser(report, self.start_url):
                self.diagnostics.browser_executable = report.browser_executable
                self.diagnostics.user_data_dir = report.user_data_dir
                self.diagnostics.remote_debugging_port = report.remote_debugging_port
                self.diagnostics.warnings.append(report.error_summary)
                raise RuntimeError(report.error_summary)
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{report.remote_debugging_port}")
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.context.new_page()
            self._created_page = True
            self.diagnostics.cdp_connected = True
            self.diagnostics.browser_executable = report.browser_executable
            self.diagnostics.user_data_dir = report.user_data_dir
            self.diagnostics.remote_debugging_port = report.remote_debugging_port
            self.open(self.start_url)
            return self
        if self.mode == "wsl_playwright":
            report = RpaReport(mode="browser-session:wsl", target_url=self.start_url, title=self.title)
            self.bridge_context = KworkRpaBridge(report)
            self.bridge = self.bridge_context.__enter__()
            self.page = self.bridge.page
            self.diagnostics.active_browser_profile_path = report.active_browser_profile_path
            self.diagnostics.fallback_browser_profile_path = report.fallback_browser_profile_path
            self.open(self.start_url)
            return self
        raise ValueError(f"Unsupported browser mode: {self.mode}")

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.mode == "windows_cdp":
            if self._created_page and self.page and not self.keep_open:
                try:
                    self.page.close()
                except Exception:
                    pass
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:
                    pass
            return
        if self.bridge_context:
            self.bridge_context.__exit__(exc_type, exc, tb)

    def open(self, url: str) -> None:
        if not self.page:
            raise RuntimeError("Browser session is not open")
        self.page.goto(url, wait_until="commit", timeout=25_000)
        self.page.wait_for_timeout(1200)
        self.refresh_diagnostics()

    def refresh_diagnostics(self) -> BrowserSessionDiagnostics:
        if not self.page:
            return self.diagnostics
        self.diagnostics.current_url = self.page.url
        try:
            self.diagnostics.page_title = self.page.title()
        except Exception:
            self.diagnostics.page_title = "unknown"
        self.diagnostics.login_detected = self.detect_login_state()
        self.diagnostics.detected_username = self.detect_username()
        guard = self.evaluate_guard()
        self.diagnostics.account_guard_status = guard.account_guard_status
        self.diagnostics.account_guard_action = guard.account_guard_action
        self.diagnostics.account_guard_message = guard.account_guard_message
        return self.diagnostics

    def detect_login_state(self) -> str:
        if self.mode == "windows_cdp":
            return cdp_detect_login_state(self.page)
        if self.bridge:
            self.bridge.detect_login_state()
            return self.bridge.report.login_detected
        return "unknown"

    def detect_username(self) -> str:
        if self.mode == "windows_cdp":
            return cdp_detect_username(self.page, self.account)
        if self.bridge:
            return self.bridge.detect_public_username(self.account)
        return "unknown"

    def evaluate_guard(self) -> AccountGuardResult:
        return evaluate_account_guard(
            self.diagnostics.detected_username,
            expected_username=self.account,
            login_detected=self.diagnostics.login_detected,
        )

    def visible_text(self) -> str:
        try:
            return self.page.evaluate("() => document.body ? document.body.innerText : ''") or ""
        except Exception:
            return ""

    def screenshot(self, name: str) -> str:
        ensure_dir(SCREENSHOT_DIR)
        path = SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True, timeout=10_000)
            rel = str(path.relative_to(ROOT))
            self.diagnostics.screenshots.append(rel)
            return rel
        except Exception as error:
            self.diagnostics.warnings.append(f"screenshot failed: {error}")
            return ""

    def find_blocked_buttons(self) -> list[str]:
        blocked = [
            "Опубликовать",
            "На модерацию",
            "Отправить",
            "Сохранить профиль",
            "Сохранить",
            "Предложить услугу",
            "Принять заказ",
            "Отменить заказ",
            "Подтвердить действие",
            "Подтвердить",
            "Удалить",
            "Настроить вывод",
            "Привязать телефон",
        ]
        try:
            return self.page.evaluate(
                """(blocked) => {
                  const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                  };
                  const labels = Array.from(document.querySelectorAll('button, a, input[type="submit"], input[type="button"]'))
                    .filter(visible)
                    .map((el) => (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim())
                    .filter(Boolean);
                  return blocked.filter((word) => labels.some((label) => label.includes(word)));
                }""",
                blocked,
            )
        except Exception:
            return []


def open_kwork_browser_session(
    mode: str = "windows_cdp",
    account: str = EXPECTED_ACCOUNT,
    start_url: str = MANAGE_KWORKS_URL,
    keep_open: bool = False,
):
    """Factory kept small for flow scripts that should not know backend details."""
    config = load_account_guard_config()
    target_account = account or config.expected_username
    return KworkBrowserSession(mode=mode, account=target_account, start_url=start_url, keep_open=keep_open)
