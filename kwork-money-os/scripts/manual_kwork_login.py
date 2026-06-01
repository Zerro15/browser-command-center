#!/usr/bin/env python3
"""Open Kwork in the persistent visible browser for manual login."""

from __future__ import annotations

from browser_rpa_bridge import KWORK_HOME_URL, REPORT_PATH, KworkRpaBridge, RpaReport


def main() -> None:
    report = RpaReport(mode="manual-login", target_url=KWORK_HOME_URL)
    with KworkRpaBridge(report) as bridge:
        bridge.open(KWORK_HOME_URL)
        bridge.detect_login_state()
        report.next_safe_command = (
            "python scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --preview --hold"
        )
        report.write()
        print(REPORT_PATH)
        bridge.hold_open()


if __name__ == "__main__":
    main()
