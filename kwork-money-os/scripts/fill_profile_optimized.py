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
    field_specs = [
        (
            "display_name_suggestion",
            profile.get("display_name_suggestion", ""),
            ["Имя", "Отображаемое имя", "display name", "name"],
            ["input[name*='name']", "input[name*='username']"],
        ),
        (
            "headline",
            profile.get("headline", ""),
            ["Специализация", "Заголовок", "Профессия", "headline", "position"],
            ["input[name*='headline']", "input[name*='position']", "input[name*='profession']"],
        ),
        (
            "about",
            profile.get("about", ""),
            ["О себе", "Описание", "about", "description"],
            ["textarea[name*='description']", "textarea[name*='about']", "[contenteditable='true']"],
        ),
        (
            "skills",
            ", ".join(profile.get("skills", [])),
            ["Навыки", "Стек", "skills"],
            ["input[name*='skills']", "textarea[name*='skills']"],
        ),
        (
            "short_pitch",
            profile.get("short_pitch", ""),
            ["Кратко", "Слоган", "short", "pitch"],
            ["textarea[name*='short']", "input[name*='short']"],
        ),
        (
            "long_pitch",
            profile.get("long_pitch", ""),
            ["Описание услуг", "Дополнительно", "long", "services"],
            ["textarea[name*='services']", "textarea[name*='details']"],
        ),
        (
            "trust_blocks",
            joined(profile.get("trust_blocks", [])),
            ["Опыт", "Почему", "Довер", "trust"],
            ["textarea[name*='experience']", "textarea[name*='trust']"],
        ),
        (
            "faq",
            joined(profile.get("faq", [])),
            ["FAQ", "Вопросы", "Ответы"],
            ["textarea[name*='faq']"],
        ),
        (
            "buyer_friendly_description",
            profile.get("buyer_friendly_description", ""),
            ["Покупателю", "Клиенту", "buyer"],
            ["textarea[name*='buyer']", "textarea[name*='client']"],
        ),
    ]
    for name, value, hints, selectors in field_specs:
        bridge.fill_text(name, value, hints, selectors)


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
        bridge.wait_and_screenshot("profile-optimized-before")
        bridge.collect_fields()
        if not strict_login_gate(bridge, REPORT_PATH):
            if args.hold:
                bridge.hold_open()
            print(REPORT_PATH)
            return
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
