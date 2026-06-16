#!/usr/bin/env python3
"""Diagnose Playwright Chromium login persistence for the target Kwork account."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import REPORTS, ROOT, ensure_dir
from account_guard import (
    apply_account_guard_to_report,
    evaluate_account_guard,
    load_account_guard_config,
    normalize_profile_path_value,
    normalize_username,
    resolve_browser_profile_path,
)
from browser_rpa_bridge import KWORK_HOME_URL, SCREENSHOT_DIR, KworkRpaBridge, RpaReport


REPORT_PATH = REPORTS / "kwork_login_diagnostics_report.md"
KWORK_LOGIN_URL = "https://kwork.ru/login"
MANAGE_KWORKS_URL = "https://kwork.ru/manage_kworks"


@dataclass
class DiagnosticPage:
    name: str
    opened_url: str
    final_url: str = "unknown"
    page_title: str = "unknown"
    login_detected: str = "unknown"
    detected_username: str = "unknown"
    account_guard_status: str = "not_checked"
    confidence: str = "none"
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticResult:
    account: str
    profile_path: Path
    profile_exists: bool = False
    profile_writable: bool = False
    persistent_context_used: bool = False
    marker_file: str = ""
    marker_write_ok: bool = False
    opened_url: str = "unknown"
    final_url: str = "unknown"
    page_title: str = "unknown"
    login_detected: str = "unknown"
    detected_username: str = "unknown"
    expected_username: str = "unknown"
    account_guard_status: str = "not_checked"
    account_guard_action: str = "not_checked"
    account_guard_message: str = ""
    detection_methods_results: list[DiagnosticPage] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    restart_check_requested: bool = False
    persistence_confirmed: bool = False
    restart_before_username: str = "unknown"
    restart_after_username: str = "unknown"
    restart_before_login_detected: str = "unknown"
    restart_after_login_detected: str = "unknown"
    next_fix: str = ""


def resolve_profile_arg(value: str) -> Path:
    normalized = normalize_profile_path_value(value, ".browser-profile-zerroone")
    return resolve_browser_profile_path(normalized, ".browser-profile-zerroone")


def mark_profile_writable(profile_path: Path) -> tuple[bool, str]:
    ensure_dir(profile_path)
    marker = profile_path / ".kwork-money-os-profile-marker"
    try:
        marker.write_text(datetime.now().isoformat(timespec="seconds") + "\n", encoding="utf-8")
        return marker.exists(), str(marker.relative_to(ROOT))
    except Exception:
        return False, str(marker)


def page_title(bridge: KworkRpaBridge) -> str:
    if not bridge.available:
        return "unknown"
    try:
        return str(bridge.page.title() or "unknown").strip()[:180]
    except Exception:
        return "unknown"


def confidence_for(account: str, page: DiagnosticPage) -> str:
    expected = normalize_username(account)
    detected_matches = page.detected_username.lower() == expected.lower()
    if detected_matches and page.login_detected == "true":
        return "high"
    if (
        detected_matches
        and not page.signals.get("is_login_page")
        and not page.signals.get("is_404")
        and (
            str(page.signals.get("current_profile_username")).lower() == expected.lower()
            or page.signals.get("seller_title_expected")
            or page.signals.get("text_expected_mentions")
        )
    ):
        return "high_profile_page"
    if page.login_detected == "true" and page.detected_username == "unknown":
        return "logged_in_username_unknown"
    return "none"


def check_page(bridge: KworkRpaBridge, name: str, url: str, account: str) -> DiagnosticPage:
    bridge.open(url)
    bridge.detect_login_state()
    signals = bridge.collect_public_username_signals(account)
    username = bridge.detect_public_username(account)
    guard = evaluate_account_guard(username, expected_username=account, login_detected=bridge.report.login_detected)
    apply_account_guard_to_report(bridge.report, guard)
    item = DiagnosticPage(
        name=name,
        opened_url=url,
        final_url=bridge.page.url if bridge.available else "unknown",
        page_title=page_title(bridge),
        login_detected=bridge.report.login_detected,
        detected_username=username,
        account_guard_status=guard.account_guard_status,
        signals=signals,
    )
    item.confidence = confidence_for(account, item)
    bridge.wait_and_screenshot(f"login-diagnostics-{name}")
    return item


def logged_in_mismatch(result: DiagnosticResult) -> DiagnosticPage | None:
    expected = normalize_username(result.account).lower()
    for item in result.detection_methods_results:
        if (
            item.login_detected == "true"
            and item.detected_username != "unknown"
            and item.detected_username.lower() != expected
        ):
            return item
    return None


def summarize(result: DiagnosticResult) -> None:
    mismatch = logged_in_mismatch(result)
    if mismatch:
        guard = evaluate_account_guard(
            mismatch.detected_username,
            expected_username=result.account,
            login_detected=mismatch.login_detected,
        )
        result.detected_username = guard.detected_username
        result.login_detected = mismatch.login_detected
        result.final_url = mismatch.final_url
        result.page_title = mismatch.page_title
        result.account_guard_status = guard.account_guard_status
        result.account_guard_action = guard.account_guard_action
        result.account_guard_message = guard.account_guard_message
        return
    best = next(
        (
            item
            for item in result.detection_methods_results
            if (
                item.detected_username.lower() == result.account.lower()
                and item.confidence == "high"
                and item.login_detected == "true"
            )
        ),
        None,
    )
    if best:
        result.detected_username = result.account
        result.login_detected = best.login_detected
        result.final_url = best.final_url
        result.page_title = best.page_title
        result.account_guard_status = "ok"
        result.account_guard_action = "continue"
        result.account_guard_message = f"Detected target account {result.account} with {best.confidence} confidence."
        return
    latest = result.detection_methods_results[-1] if result.detection_methods_results else None
    if latest:
        result.detected_username = latest.detected_username
        result.login_detected = latest.login_detected
        result.final_url = latest.final_url
        result.page_title = latest.page_title
        guard = evaluate_account_guard(
            latest.detected_username,
            expected_username=result.account,
            login_detected=latest.login_detected,
        )
        result.account_guard_status = guard.account_guard_status
        result.account_guard_action = guard.account_guard_action
        result.account_guard_message = guard.account_guard_message


def write_report(result: DiagnosticResult) -> None:
    ensure_dir(REPORT_PATH.parent)
    if result.persistence_confirmed:
        next_fix = "persistence confirmed; run read-only post-phone readiness/dashboard before any setup"
    elif result.account_guard_status == "profile_page_match":
        next_fix = (
            f"public profile page for {result.account} is reachable, but login is not confirmed; "
            "finish manual login in Playwright Chromium, then rerun diagnostics with --restart-check"
        )
    elif result.account_guard_status in {"unknown", "unknown_logged_in"}:
        next_fix = (
            f"finish manual login in Playwright Chromium, open https://kwork.ru/user/{result.account}, "
            "then rerun diagnostics with --restart-check"
        )
    else:
        next_fix = "switch Playwright Chromium profile to the expected account; do not copy cookies from other browsers"
    result.next_fix = next_fix

    lines = [
        "# Kwork Login Diagnostics Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- profile_path: `{result.profile_path}`",
        f"- profile_exists: `{str(result.profile_exists).lower()}`",
        f"- profile_writable: `{str(result.profile_writable).lower()}`",
        f"- persistent_context_used: `{str(result.persistent_context_used).lower()}`",
        f"- marker_file: `{result.marker_file or 'none'}`",
        f"- marker_write_ok: `{str(result.marker_write_ok).lower()}`",
        f"- opened_url: `{result.opened_url}`",
        f"- final_url: `{result.final_url}`",
        f"- page_title: `{result.page_title}`",
        f"- login_detected: `{result.login_detected}`",
        f"- detected_username: `{result.detected_username}`",
        f"- expected_username: `{result.expected_username}`",
        f"- account_guard_status: `{result.account_guard_status}`",
        f"- account_guard_action: `{result.account_guard_action}`",
        f"- account_guard_message: `{result.account_guard_message or 'none'}`",
        f"- restart_check_requested: `{str(result.restart_check_requested).lower()}`",
        f"- persistence_confirmed: `{str(result.persistence_confirmed).lower()}`",
        f"- restart_before_login_detected: `{result.restart_before_login_detected}`",
        f"- restart_before_username: `{result.restart_before_username}`",
        f"- restart_after_login_detected: `{result.restart_after_login_detected}`",
        f"- restart_after_username: `{result.restart_after_username}`",
        f"- screenshots_path: `{SCREENSHOT_DIR.relative_to(ROOT)}`",
        f"- next_fix: `{result.next_fix}`",
        "",
        "## Detection Methods Results",
    ]
    for item in result.detection_methods_results:
        lines.extend(
            [
                f"- {item.name}:",
                f"  - opened_url: `{item.opened_url}`",
                f"  - final_url: `{item.final_url}`",
                f"  - page_title: `{item.page_title}`",
                f"  - login_detected: `{item.login_detected}`",
                f"  - detected_username: `{item.detected_username}`",
                f"  - account_guard_status: `{item.account_guard_status}`",
                f"  - confidence: `{item.confidence}`",
                f"  - current_profile_username: `{item.signals.get('current_profile_username', 'unknown')}`",
                f"  - header_candidates: `{', '.join(item.signals.get('header_candidates') or []) or 'none'}`",
                f"  - visible_link_candidates: `{', '.join(item.signals.get('visible_link_candidates') or []) or 'none'}`",
                f"  - is_login_page: `{item.signals.get('is_login_page')}`",
                f"  - is_404: `{item.signals.get('is_404')}`",
                f"  - text_expected_mentions: `{item.signals.get('text_expected_mentions')}`",
                f"  - seller_title_expected: `{item.signals.get('seller_title_expected')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Screenshots",
            *(f"- `{item}`" for item in result.screenshots),
            "",
            "## Safety",
            "- Uses Playwright Chromium persistent context with the configured profile path.",
            "- Does not read cookies, local storage, passwords, tokens, SMS codes, or browser credentials.",
            "- Does not copy cookies from Yandex/Chrome/legacy profiles.",
            "- Does not click save, publish, moderation, proposal, message, order, withdrawal, phone, SMS, delete, or confirmation buttons.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_browser_checks(
    result: DiagnosticResult,
    open_login: bool,
    hold: bool,
    restart_label: str = "initial",
) -> None:
    report = RpaReport(mode=f"login-diagnostics:{restart_label}", target_url=KWORK_HOME_URL)
    with KworkRpaBridge(report, profile_dir=result.profile_path) as bridge:
        result.persistent_context_used = bool(bridge.context is not None and bridge.available)
        start_url = KWORK_LOGIN_URL if open_login else KWORK_HOME_URL
        result.opened_url = start_url
        pages = [("login" if open_login else "home", start_url)]
        if not open_login:
            pages.append(("manage_kworks", MANAGE_KWORKS_URL))
        pages.append(("target_profile", f"https://kwork.ru/user/{result.account}"))
        for name, url in pages:
            result.detection_methods_results.append(check_page(bridge, name, url, result.account))
        result.screenshots.extend(report.screenshots)
        summarize(result)
        report.write(REPORTS / "kwork_login_diagnostics_bridge_report.md")
        if hold:
            print(
                f"Войди вручную именно в {result.account} в этом Chromium. "
                f"После входа открой https://kwork.ru/user/{result.account} и нажми Enter в терминале."
            )
            bridge.hold_open()
            result.detection_methods_results.append(
                check_page(bridge, "after_hold_target_profile", f"https://kwork.ru/user/{result.account}", result.account)
            )
            result.screenshots.extend(report.screenshots)
            summarize(result)


def run_diagnostics(args: argparse.Namespace) -> DiagnosticResult:
    account = normalize_username(args.account)
    config = load_account_guard_config()
    if account == "unknown":
        account = config.expected_username
    profile_path = resolve_profile_arg(args.profile)
    result = DiagnosticResult(account=account, expected_username=account, profile_path=profile_path)
    result.profile_exists = profile_path.exists()
    result.marker_write_ok, result.marker_file = mark_profile_writable(profile_path)
    result.profile_exists = profile_path.exists()
    result.profile_writable = result.marker_write_ok

    if not args.check_only or args.restart_check:
        run_browser_checks(result, open_login=args.open_login, hold=args.hold, restart_label="before_restart")
    else:
        run_browser_checks(result, open_login=False, hold=False, restart_label="check_only")

    if args.restart_check:
        result.restart_check_requested = True
        result.restart_before_username = result.detected_username
        result.restart_before_login_detected = result.login_detected
        before_ok = result.detected_username == account and result.account_guard_status == "ok"
        run_browser_checks(result, open_login=False, hold=False, restart_label="after_restart")
        result.restart_after_username = result.detected_username
        result.restart_after_login_detected = result.login_detected
        result.persistence_confirmed = bool(
            before_ok and result.detected_username == account and result.account_guard_status == "ok"
        )

    write_report(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Kwork Playwright Chromium login persistence")
    parser.add_argument("--account", default="ZerroOne")
    parser.add_argument("--profile", default=".browser-profile-zerroone")
    parser.add_argument("--open-login", action="store_true")
    parser.add_argument("--hold", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--restart-check", action="store_true")
    return parser.parse_args()


def main() -> None:
    result = run_diagnostics(parse_args())
    print(REPORT_PATH)
    print(f"profile_path={result.profile_path}")
    print(f"profile_exists={str(result.profile_exists).lower()}")
    print(f"profile_writable={str(result.profile_writable).lower()}")
    print(f"persistent_context_used={str(result.persistent_context_used).lower()}")
    print(f"login_detected={result.login_detected}")
    print(f"detected_username={result.detected_username}")
    print(f"expected_username={result.expected_username}")
    print(f"account_guard_status={result.account_guard_status}")
    print(f"account_guard_action={result.account_guard_action}")
    print(f"persistence_confirmed={str(result.persistence_confirmed).lower()}")
    print(f"next_fix={result.next_fix}")


if __name__ == "__main__":
    main()
