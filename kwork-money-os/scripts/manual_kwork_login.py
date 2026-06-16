#!/usr/bin/env python3
"""Open Kwork in the persistent visible browser for manual login."""

from __future__ import annotations

import argparse

from account_guard import apply_account_guard_to_report, evaluate_account_guard
from browser_rpa_bridge import KWORK_HOME_URL, REPORT_PATH, KworkRpaBridge, RpaReport


def print_guard_state(prefix: str, report: RpaReport) -> None:
    print(f"{prefix}_login_detected={report.login_detected}")
    print(f"{prefix}_detected_username={report.detected_username}")
    print(f"{prefix}_expected_username={report.expected_username}")
    print(f"{prefix}_account_guard_status={report.account_guard_status}")
    print(f"{prefix}_account_guard_action={report.account_guard_action}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Playwright Chromium for manual Kwork login/account switch")
    parser.add_argument("--hold", action="store_true", help="Keep Chromium open so the user can switch to ZerroOne manually")
    args = parser.parse_args()

    report = RpaReport(mode="manual-login", target_url=KWORK_HOME_URL)
    with KworkRpaBridge(report) as bridge:
        bridge.open(KWORK_HOME_URL)
        bridge.detect_login_state()
        guard = evaluate_account_guard(bridge.detect_public_username())
        apply_account_guard_to_report(report, guard)
        report.next_safe_command = (
            "switch manually to ZerroOne in Chromium, then rerun the intended safe flow"
        )
        report.write()
        print(REPORT_PATH)
        print_guard_state("before_hold", report)
        if args.hold:
            bridge.hold_open()
            bridge.detect_login_state()
            guard = evaluate_account_guard(bridge.detect_public_username())
            apply_account_guard_to_report(report, guard)
            report.write()
            print_guard_state("after_hold", report)


if __name__ == "__main__":
    main()
