#!/usr/bin/env python3
"""Safely fill optimized Kwork profile fields without saving."""

from __future__ import annotations

import argparse
from pathlib import Path

from account_optimizer_common import (
    PROFILE_SETTINGS_URL,
    add_mode_args,
    build_plan_report,
    parse_mode,
    read_json,
    require_run_approval,
    strict_login_gate,
)
from _common import DATA, REPORTS
from account_guard import apply_account_guard_to_report, evaluate_account_guard
from browser_rpa_bridge import KworkRpaBridge, RpaReport


PROFILE_PATH = DATA / "profile" / "profile_optimized.json"
REPORT_PATH = REPORTS / "profile_optimized_fill_report.md"
PLAN_PATH = REPORTS / "profile_optimized_fill_plan.md"


def joined(value) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                q = item.get("q", "")
                a = item.get("a", "")
                parts.append(f"Q: {q}\nA: {a}".strip())
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return "" if value is None else str(value)


def fill_optimized_fields(bridge: KworkRpaBridge, profile: dict) -> None:
    profile_details = "\n\n".join(
        part.strip()
        for part in [
            profile.get("about", ""),
            "Что делаю:\n" + "\n".join(f"- {item}" for item in profile.get("skills", [])),
            "Как работаю:\n" + joined(profile.get("trust_blocks", [])),
            "Коротко для клиента:\n" + profile.get("buyer_friendly_description", ""),
        ]
        if part and part.strip()
    )
    field_specs = [
        (
            "headline",
            profile.get("headline", ""),
            ["Специализация", "Заголовок", "Профессия", "headline", "position"],
            ["textarea[name='profession']", "input[name='profession']", "input[name*='headline']", "input[name*='position']"],
        ),
        (
            "profile_details",
            profile_details,
            ["Навыки, опыт, специализация", "О себе", "Описание", "details"],
            ["textarea[name='details']", "textarea[name*='description']", "textarea[name*='about']"],
        ),
    ]
    for name, value, hints, selectors in field_specs:
        bridge.fill_text(name, value, hints, selectors)


def open_profile_settings_tab(bridge: KworkRpaBridge) -> bool:
    if not bridge.available:
        return False
    try:
        target = bridge.page.evaluate(
            """() => {
              const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const tabs = Array.from(document.querySelectorAll('.k-tabs__item'))
                .filter(isVisible)
                .filter((el) => (el.innerText || '').replace(/\\s+/g, ' ').trim() === 'Профиль');
              if (tabs.length !== 1) return {count: tabs.length};
              tabs[0].setAttribute('data-kwork-profile-tab', 'true');
              return {count: 1};
            }"""
        )
        if int(target.get("count") or 0) != 1:
            bridge.report.warn(f"profile settings tab not uniquely found: {target.get('count')}")
            return False
        bridge.page.locator("[data-kwork-profile-tab='true']").click(timeout=2000)
        bridge.page.wait_for_timeout(1000)
        bridge.report.action("opened settings profile tab safely")
        return True
    except Exception as error:
        bridge.report.warn(f"unable to open settings profile tab: {error}")
        return False


def run_filler(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    profile_path = Path(args.profile)
    if mode == "dry-run":
        build_plan_report(
            PLAN_PATH,
            "Kwork Optimized Profile Fill Plan",
            mode,
            [
                f"Read profile JSON from {profile_path}.",
                f"Open settings page {args.profile_url}.",
                "Require login_detected == true.",
                "Fill text fields only in --run --approve.",
                "Do not click Save Profile or any final button.",
            ],
        )
        print(PLAN_PATH)
        return
    require_run_approval(mode, args.approve, "Optimized profile filling")
    profile = read_json(profile_path, {})
    report = RpaReport(mode=f"profile-optimized:{mode}", target_url=args.profile_url, title="Kwork Optimized Profile Fill Report")
    with KworkRpaBridge(report) as bridge:
        bridge.open(args.profile_url)
        if not strict_login_gate(bridge, REPORT_PATH):
            if args.hold:
                bridge.hold_open()
            print(REPORT_PATH)
            return
        guard = evaluate_account_guard(
            bridge.detect_public_username(),
            login_detected=bridge.report.login_detected,
        )
        apply_account_guard_to_report(report, guard)
        if not guard.ok:
            report.warn(guard.account_guard_message)
            report.next_safe_command = "manual account switch in Playwright Chromium to ZerroOne, then rerun profile flow"
            bridge.wait_and_screenshot("profile-optimized-account-guard-stop")
            report.write(REPORT_PATH)
            if args.hold:
                bridge.hold_open()
            print(REPORT_PATH)
            return
        open_profile_settings_tab(bridge)
        bridge.wait_and_screenshot("profile-optimized-before")
        bridge.collect_fields()
        if mode == "run":
            fill_optimized_fields(bridge, profile)
            bridge.wait_and_screenshot("profile-optimized-after")
            report.next_safe_command = "manual review in visible browser; user saves profile manually"
        else:
            report.next_safe_command = "python scripts/fill_profile_optimized.py --run --approve --hold"
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        report.write(REPORT_PATH)
        if args.hold:
            bridge.hold_open()
    print(REPORT_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=str(PROFILE_PATH))
    parser.add_argument("--profile-url", default=PROFILE_SETTINGS_URL)
    add_mode_args(parser)
    run_filler(parser.parse_args())


if __name__ == "__main__":
    main()
