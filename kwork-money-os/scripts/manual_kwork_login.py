#!/usr/bin/env python3
"""Open Kwork in the persistent visible browser for manual login."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime

from _common import REPORTS, ROOT, ensure_dir
from account_guard import (
    apply_account_guard_to_report,
    browser_profile_paths,
    evaluate_account_guard,
    load_account_guard_config,
    normalize_username,
)
from browser_rpa_bridge import KWORK_HOME_URL, REPORT_PATH, SCREENSHOT_DIR, KworkRpaBridge, RpaReport


SWITCH_REPORT_PATH = REPORTS / "account_switch_report.md"
KWORK_LOGIN_URL = "https://kwork.ru/login"
MANAGE_KWORKS_URL = "https://kwork.ru/manage_kworks"
MANUAL_LOGIN_MESSAGE = (
    "ВНИМАНИЕ: войди вручную именно в ZerroOne в открытом Chromium. "
    "Не используй Яндекс.Браузер. "
    "После входа открой страницу https://kwork.ru/user/ZerroOne, "
    "потом вернись в терминал и нажми Enter. "
    "Не входи в bogdanmashenin или 3va_Marz."
)
MANUAL_ONLY = [
    "Switch Kwork account manually in Playwright Chromium.",
    "Do not pass login/password/SMS through scripts, argv, files, or reports.",
    "Do not save profile automatically.",
    "Do not publish kworks or submit moderation automatically.",
    "Do not click `Предложить услугу`, send proposals, or send messages automatically.",
    "Do not change phone/SMS/withdrawal settings automatically.",
]


@dataclass
class SwitchSnapshot:
    label: str
    login_detected: str
    active_browser_profile_path: str
    fallback_browser_profile_path: str
    detected_username: str
    expected_username: str
    account_guard_status: str
    account_guard_action: str
    account_guard_message: str
    phone_verification_detected: str
    current_url: str
    wrong_profile_backup_path: str = ""


@dataclass
class LoginAttempt:
    index: int
    login_detected: str
    detected_username: str
    account_guard_status: str
    account_guard_action: str
    current_url: str
    title: str
    manage_kworks_accessible: bool = False


def snapshot(label: str, bridge: KworkRpaBridge, expected_username: str) -> SwitchSnapshot:
    bridge.detect_login_state()
    guard = evaluate_account_guard(
        bridge.detect_public_username(expected_username),
        expected_username=expected_username,
        login_detected=bridge.report.login_detected,
    )
    apply_account_guard_to_report(bridge.report, guard)
    phone_detected = bridge.detect_phone_verification_required(f"manual-switch-phone-stop-{label}")
    return SwitchSnapshot(
        label=label,
        login_detected=bridge.report.login_detected,
        active_browser_profile_path=bridge.report.active_browser_profile_path,
        fallback_browser_profile_path=bridge.report.fallback_browser_profile_path,
        detected_username=guard.detected_username,
        expected_username=guard.expected_username,
        account_guard_status=guard.account_guard_status,
        account_guard_action=guard.account_guard_action,
        account_guard_message=guard.account_guard_message,
        phone_verification_detected=str(phone_detected).lower(),
        current_url=bridge.page.url if bridge.available else "unknown",
        wrong_profile_backup_path=os.environ.get("KWORK_WRONG_PROFILE_BACKUP_PATH", ""),
    )


def page_title(bridge: KworkRpaBridge) -> str:
    if not bridge.available:
        return "unknown"
    try:
        return str(bridge.page.title() or "unknown").strip()[:180]
    except Exception:
        return "unknown"


def print_login_attempt(attempt: LoginAttempt, total: int) -> None:
    print(
        f"login_wait_attempt={attempt.index}/{total} "
        f"login_detected={attempt.login_detected} "
        f"detected_username={attempt.detected_username} "
        f"account_guard_status={attempt.account_guard_status} "
        f"manage_kworks_accessible={str(attempt.manage_kworks_accessible).lower()} "
        f"url={attempt.current_url} "
        f"title={attempt.title}"
    )


def check_manage_kworks_access(bridge: KworkRpaBridge) -> bool:
    if not bridge.available or not bridge.context:
        return False
    page = None
    try:
        page = bridge.context.new_page()
        page.goto(MANAGE_KWORKS_URL, wait_until="commit", timeout=12_000)
        page.wait_for_timeout(800)
        return "/login" not in page.url.lower() and "login" not in page.url.lower()
    except Exception as error:
        bridge.report.warn(f"Unable to check manage_kworks access: {error}")
        return False
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def wait_for_login_detection(
    bridge: KworkRpaBridge,
    expected_username: str,
    attempts_count: int = 12,
    delay_seconds: int = 5,
) -> tuple[SwitchSnapshot, list[LoginAttempt]]:
    attempts: list[LoginAttempt] = []
    final_snapshot = snapshot("wait-0", bridge, expected_username)
    max_attempts = max(1, attempts_count)
    delay = max(1, delay_seconds)
    for index in range(1, max_attempts + 1):
        bridge.open(f"https://kwork.ru/user/{expected_username}")
        final_snapshot = snapshot(f"wait-{index}", bridge, expected_username)
        attempt = LoginAttempt(
            index=index,
            login_detected=final_snapshot.login_detected,
            detected_username=final_snapshot.detected_username,
            account_guard_status=final_snapshot.account_guard_status,
            account_guard_action=final_snapshot.account_guard_action,
            current_url=final_snapshot.current_url,
            title=page_title(bridge),
            manage_kworks_accessible=check_manage_kworks_access(bridge),
        )
        attempts.append(attempt)
        print_login_attempt(attempt, max_attempts)
        if final_snapshot.account_guard_status == "ok" and final_snapshot.detected_username == expected_username:
            break
        if final_snapshot.detected_username not in ("unknown", expected_username):
            break
        if index < max_attempts:
            time.sleep(delay)
    return final_snapshot, attempts


def poll_until_login(
    bridge: KworkRpaBridge,
    expected_username: str,
    timeout_minutes: int,
    poll_interval_seconds: int,
) -> tuple[SwitchSnapshot, list[LoginAttempt]]:
    attempts: list[LoginAttempt] = []
    deadline = time.monotonic() + max(1, timeout_minutes) * 60
    interval = max(1, poll_interval_seconds)
    final_snapshot = snapshot("poll-0", bridge, expected_username)
    print("=" * 86)
    print(
        f"Войди вручную именно в {expected_username} в открытом Chromium. "
        f"Не используй обычный браузер. Скрипт сам ждёт до {timeout_minutes} минут "
        f"и проверяет вход каждые {interval} секунд."
    )
    print("Скрипт не вводит логин, пароль, SMS и не нажимает final buttons.")
    print("=" * 86)
    while time.monotonic() <= deadline:
        final_snapshot = snapshot(f"poll-{len(attempts) + 1}", bridge, expected_username)
        manage_accessible = check_manage_kworks_access(bridge)
        if final_snapshot.account_guard_status != "ok" and manage_accessible:
            bridge.open(f"https://kwork.ru/user/{expected_username}")
            final_snapshot = snapshot(f"poll-profile-{len(attempts) + 1}", bridge, expected_username)
        attempt = LoginAttempt(
            index=len(attempts) + 1,
            login_detected=final_snapshot.login_detected,
            detected_username=final_snapshot.detected_username,
            account_guard_status=final_snapshot.account_guard_status,
            account_guard_action=final_snapshot.account_guard_action,
            current_url=final_snapshot.current_url,
            title=page_title(bridge),
            manage_kworks_accessible=manage_accessible,
        )
        attempts.append(attempt)
        print_login_attempt(attempt, max(1, int(timeout_minutes * 60 / interval)))
        if final_snapshot.account_guard_status == "ok" and final_snapshot.detected_username == expected_username:
            return final_snapshot, attempts
        if final_snapshot.detected_username not in ("unknown", expected_username):
            bridge.wait_and_screenshot("manual-poll-account-blocked")
            return final_snapshot, attempts
        time.sleep(interval)
    final_snapshot = snapshot("poll-timeout", bridge, expected_username)
    return final_snapshot, attempts


def next_manual_step_for(final: SwitchSnapshot) -> str:
    if final.account_guard_status == "ok":
        return "run read-only post-phone readiness/dashboard before any manual final action"
    if final.detected_username == "unknown":
        return "finish login in Playwright Chromium profile .browser-profile-zerroone as ZerroOne"
    return f"switch manually from {final.detected_username} to ZerroOne in Playwright Chromium"


def write_switch_report(
    before: SwitchSnapshot,
    after: SwitchSnapshot | None,
    report: RpaReport,
    login_page_opened: bool = False,
    attempts: list[LoginAttempt] | None = None,
    login_wait_mode: str = "hold",
    timeout_minutes: int | None = None,
    poll_interval_seconds: int | None = None,
    persistence_confirmed: bool = False,
    last_url: str = "",
    last_title: str = "",
) -> None:
    ensure_dir(SWITCH_REPORT_PATH.parent)
    final = after or before
    attempts = attempts or []
    lines = [
        "# Kwork Account Switch Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- expected_username: `{final.expected_username}`",
        f"- active_browser_profile_path: `{final.active_browser_profile_path}`",
        f"- fallback_browser_profile_path: `{final.fallback_browser_profile_path}`",
        f"- wrong_profile_backup_path: `{final.wrong_profile_backup_path or 'none'}`",
        f"- login_page_opened: `{str(login_page_opened).lower()}`",
        f"- login_wait_mode: `{login_wait_mode}`",
        f"- timeout_minutes: `{timeout_minutes if timeout_minutes is not None else 'not_set'}`",
        f"- poll_interval_seconds: `{poll_interval_seconds if poll_interval_seconds is not None else 'not_set'}`",
        f"- attempts_count: `{len(attempts)}`",
        f"- last_url: `{last_url or final.current_url}`",
        f"- last_title: `{last_title or 'unknown'}`",
        f"- detected_username_before: `{before.detected_username}`",
        f"- detected_username_after: `{final.detected_username}`",
        f"- final_detected_username: `{final.detected_username}`",
        f"- detected_username_attempts: `{', '.join(item.detected_username for item in attempts) or 'not_checked'}`",
        f"- login_detected: `{final.login_detected}`",
        f"- account_guard_status: `{final.account_guard_status}`",
        f"- account_guard_action: `{final.account_guard_action}`",
        f"- account_guard_message: `{final.account_guard_message}`",
        f"- persistence_confirmed: `{str(persistence_confirmed).lower()}`",
        f"- phone_verification_detected: `{final.phone_verification_detected}`",
        "- create_kwork_accessible: `not_checked_in_switch_flow`",
        "- can_continue_profile_setup: `not_checked_in_switch_flow`",
        "- can_continue_kwork_draft: `not_checked_in_switch_flow`",
        f"- screenshots_path: `{SCREENSHOT_DIR.relative_to(ROOT)}`",
        f"- next_manual_step: `{next_manual_step_for(final)}`",
        "",
        "## Detected Username Attempts",
        *((
            f"- attempt {item.index}: login_detected=`{item.login_detected}`, "
            f"detected_username=`{item.detected_username}`, "
            f"account_guard_status=`{item.account_guard_status}`, "
            f"manage_kworks_accessible=`{str(item.manage_kworks_accessible).lower()}`, "
            f"url=`{item.current_url}`, title=`{item.title}`"
        ) for item in attempts),
        *([] if attempts else ["- not_checked: `wait-login loop was not run`"]),
        "",
        "## Before",
        f"- login_detected: `{before.login_detected}`",
        f"- active_browser_profile_path: `{before.active_browser_profile_path}`",
        f"- fallback_browser_profile_path: `{before.fallback_browser_profile_path}`",
        f"- detected_username: `{before.detected_username}`",
        f"- account_guard_status: `{before.account_guard_status}`",
        f"- account_guard_action: `{before.account_guard_action}`",
        f"- current_url: `{before.current_url}`",
        "",
        "## After",
    ]
    if after:
        lines.extend(
            [
                f"- login_detected: `{after.login_detected}`",
                f"- active_browser_profile_path: `{after.active_browser_profile_path}`",
                f"- fallback_browser_profile_path: `{after.fallback_browser_profile_path}`",
                f"- detected_username: `{after.detected_username}`",
                f"- account_guard_status: `{after.account_guard_status}`",
                f"- account_guard_action: `{after.account_guard_action}`",
                f"- current_url: `{after.current_url}`",
            ]
        )
    else:
        lines.append("- not_checked: `hold was not requested`")
    lines.extend(
        [
            "",
            "## Screenshots",
            *(f"- `{item}`" for item in report.screenshots),
            "",
            "## Manual-Only Actions",
            *(f"- {item}" for item in MANUAL_ONLY),
            "",
            "## Safety",
            "- This flow only opens Playwright Chromium with the configured target account profile and reads public username signals.",
            "- It does not copy cookies/session data from fallback or legacy profiles.",
            "- It does not enter passwords, SMS codes, phone numbers, cookies, tokens, or credentials.",
            "- It does not click profile save, publish, moderation, send, proposal, withdrawal, order, delete, or confirmation buttons.",
        ]
    )
    SWITCH_REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def print_guard_state(prefix: str, report: RpaReport) -> None:
    print(f"{prefix}_login_detected={report.login_detected}")
    print(f"{prefix}_detected_username={report.detected_username}")
    print(f"{prefix}_expected_username={report.expected_username}")
    print(f"{prefix}_account_guard_status={report.account_guard_status}")
    print(f"{prefix}_account_guard_action={report.account_guard_action}")


def print_manual_login_banner(account: str) -> None:
    line = "=" * 86
    print(line)
    print(MANUAL_LOGIN_MESSAGE.replace("ZerroOne", account))
    print("Скрипт не вводит логин, пароль, SMS и не нажимает final buttons.")
    print(line)


def wait_for_manual_switch(bridge: KworkRpaBridge, seconds: int, account: str) -> None:
    if sys.stdin.isatty():
        print_manual_login_banner(account)
        bridge.hold_open()
        return
    print_manual_login_banner(account)
    print(
        f"Нужно вручную переключиться на {account} в открытом Chromium. "
        f"Жду {max(1, seconds)} секунд и затем проверю username повторно. "
        "Для ожидания Enter в обычном терминале используйте --wait-seconds 0."
    )
    time.sleep(max(1, seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Playwright Chromium for manual Kwork login/account switch")
    parser.add_argument("--account", default="ZerroOne", help="Expected Kwork public username; currently intended for ZerroOne")
    parser.add_argument("--hold", action="store_true", help="Keep Chromium open so the user can switch to ZerroOne manually")
    parser.add_argument("--login-page", action="store_true", help="Open the Kwork login page when the target profile is not logged in")
    parser.add_argument("--wait-login", action="store_true", help="After the manual wait, poll login/username detection up to 12 times")
    parser.add_argument("--diagnose", action="store_true", help="Run login diagnostics/restart check after the manual wait loop")
    parser.add_argument("--poll-until-login", action="store_true", help="Poll the visible Chromium session until ZerroOne login is detected")
    parser.add_argument("--timeout-minutes", type=int, default=30, help="Maximum minutes for --poll-until-login")
    parser.add_argument("--poll-interval-seconds", type=int, default=5, help="Seconds between --poll-until-login checks")
    parser.add_argument("--wait-seconds", type=int, default=90, help="Fallback wait when --hold runs without interactive stdin")
    parser.add_argument("--wait-attempts", type=int, default=12, help="Number of login detection attempts after manual wait")
    parser.add_argument("--wait-delay-seconds", type=int, default=5, help="Delay between login detection attempts")
    args = parser.parse_args()

    config = load_account_guard_config()
    account = normalize_username(args.account)
    if account != config.expected_username:
        raise SystemExit(
            f"--account must match configured expected_username `{config.expected_username}`. "
            f"Got `{args.account}`."
        )
    active_path, fallback_path = browser_profile_paths(config)
    report = RpaReport(mode="manual-login", target_url=KWORK_HOME_URL)
    login_page_opened = False
    login_attempts: list[LoginAttempt] = []
    with KworkRpaBridge(report) as bridge:
        bridge.open(KWORK_HOME_URL)
        before = snapshot("before", bridge, account)
        if before.login_detected != "true":
            bridge.open(KWORK_LOGIN_URL)
            login_page_opened = True
            print_manual_login_banner(account)
        elif before.account_guard_status != "ok":
            print(f"Нужно вручную переключиться на {account} в открытом Chromium.")
        report.next_safe_command = (
            f"switch/login manually to {account} in Chromium, then rerun the intended safe flow"
        )
        bridge.wait_and_screenshot("manual-account-switch-before")
        report.write()
        write_switch_report(before, None, report, login_page_opened=login_page_opened)
        print(REPORT_PATH)
        print(SWITCH_REPORT_PATH)
        print(f"active_browser_profile_path={active_path}")
        print(f"fallback_browser_profile_path={fallback_path}")
        print_guard_state("before_hold", report)
        after = None
        persistence_confirmed = False
        if args.poll_until_login:
            after, login_attempts = poll_until_login(
                bridge,
                account,
                timeout_minutes=args.timeout_minutes,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            bridge.wait_and_screenshot("manual-poll-account-switch-after")
            report.write()
            write_switch_report(
                before,
                after,
                report,
                login_page_opened=login_page_opened,
                attempts=login_attempts,
                login_wait_mode="poll_until_login",
                timeout_minutes=args.timeout_minutes,
                poll_interval_seconds=args.poll_interval_seconds,
                last_url=login_attempts[-1].current_url if login_attempts else after.current_url,
                last_title=login_attempts[-1].title if login_attempts else page_title(bridge),
            )
            print_guard_state("after_poll", report)
        elif args.hold:
            wait_for_manual_switch(bridge, args.wait_seconds, account)
            if args.wait_login:
                after, login_attempts = wait_for_login_detection(
                    bridge,
                    account,
                    attempts_count=args.wait_attempts,
                    delay_seconds=args.wait_delay_seconds,
                )
            else:
                after = snapshot("after", bridge, account)
            bridge.wait_and_screenshot("manual-account-switch-after")
            report.write()
            write_switch_report(
                before,
                after,
                report,
                login_page_opened=login_page_opened,
                attempts=login_attempts,
                last_url=login_attempts[-1].current_url if login_attempts else after.current_url,
                last_title=login_attempts[-1].title if login_attempts else page_title(bridge),
            )
            print_guard_state("after_hold", report)
        if after and after.account_guard_status == "ok":
            print("account_switch_ready=true")
        elif after:
            print("account_switch_ready=false")
    if args.diagnose or args.poll_until_login:
        from argparse import Namespace
        from kwork_login_diagnostics import run_diagnostics, write_report

        diagnostic = run_diagnostics(
            Namespace(
                account=account,
                profile=".browser-profile-zerroone",
                open_login=False,
                hold=False,
                check_only=True,
                restart_check=True,
            )
        )
        if args.poll_until_login:
            diagnostic.login_wait_mode = "poll_until_login"
            diagnostic.timeout_minutes = str(args.timeout_minutes)
            diagnostic.poll_interval_seconds = str(args.poll_interval_seconds)
            diagnostic.attempts_count = len(login_attempts)
            if login_attempts:
                diagnostic.last_url = login_attempts[-1].current_url
                diagnostic.last_title = login_attempts[-1].title
            diagnostic.final_detected_username = diagnostic.detected_username
            write_report(diagnostic)
        print(f"diagnostics_report={REPORTS / 'kwork_login_diagnostics_report.md'}")
        print(f"diagnostics_detected_username={diagnostic.detected_username}")
        print(f"diagnostics_account_guard_status={diagnostic.account_guard_status}")
        print(f"persistence_confirmed={str(diagnostic.persistence_confirmed).lower()}")
        persistence_confirmed = diagnostic.persistence_confirmed
        if after:
            write_switch_report(
                before,
                after,
                report,
                login_page_opened=login_page_opened,
                attempts=login_attempts,
                login_wait_mode="poll_until_login" if args.poll_until_login else "hold",
                timeout_minutes=args.timeout_minutes if args.poll_until_login else None,
                poll_interval_seconds=args.poll_interval_seconds if args.poll_until_login else None,
                persistence_confirmed=persistence_confirmed,
                last_url=login_attempts[-1].current_url if login_attempts else after.current_url,
                last_title=login_attempts[-1].title if login_attempts else "unknown",
            )
        if args.poll_until_login:
            if after and after.detected_username not in ("unknown", account):
                raise SystemExit(2)
            if diagnostic.persistence_confirmed and diagnostic.detected_username == account:
                raise SystemExit(0)
            if diagnostic.detected_username not in ("unknown", account):
                raise SystemExit(2)
            raise SystemExit(3)


if __name__ == "__main__":
    main()
