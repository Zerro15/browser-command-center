#!/usr/bin/env python3
"""Scenario autopilot for safe Kwork draft preparation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _common import CONFIG, DATA, ROOT, load_yaml, require_manual_approval
from browser_rpa_bridge import (
    AUTOPILOT_REPORT_PATH,
    DEFAULT_DRAFT_URL,
    KworkRpaBridge,
    RpaReport,
    build_offer_values,
    fill_offer_fields,
    load_offer,
    write_plan,
)


STEPS_PATH = CONFIG / "kwork_autopilot_steps.yaml"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_autopilot_report(report: RpaReport) -> None:
    report.write(AUTOPILOT_REPORT_PATH)


def plan_values(steps: dict[str, Any], offer_path: Path, banner: Path | None, values: dict[str, Any]) -> dict[str, Any]:
    return {
        "open": steps.get("open"),
        "require_login": bool(steps.get("require_login")),
        "close_cookie_banner": steps.get("close_cookie_banner", {}),
        "click": steps.get("click", {}),
        "choose_category": steps.get("choose_category", {}),
        "fill_offer_fields": bool(steps.get("fill_offer_fields")),
        "upload_cover_if_exists": bool(steps.get("upload_cover_if_exists") and banner),
        "offer": str(offer_path),
        "banner": str(banner) if banner else None,
        "values": values,
        "stop_before": steps.get("stop_before", []),
    }


def maybe_save_draft(bridge: KworkRpaBridge, approved: bool) -> None:
    if not approved:
        return
    bridge.report.warn("auto-save draft is disabled by account optimizer safety rules; save manually in browser")


def click_create_kwork_button(bridge: KworkRpaBridge) -> bool:
    if not bridge.available:
        return False
    try:
        bridge.page.wait_for_timeout(2500)
        locator = bridge.page.locator(".js-create-kwork-btn").first
        if locator.count() < 1:
            return False
        label = locator.inner_text(timeout=1000).strip() or "Создать кворк"
        if not bridge.assert_no_blocked_click(label):
            return False
        locator.scroll_into_view_if_needed(timeout=1500)
        locator.click(timeout=3000)
        bridge.page.wait_for_timeout(2500)
        bridge.report.current_url = bridge.page.url
        bridge.report.action("clicked create-kwork button safely via .js-create-kwork-btn")
        return True
    except Exception as error:
        bridge.report.warn(f"safe create-kwork button click failed: {error}")
        return False


def stop_if_phone_verification_required(bridge: KworkRpaBridge) -> bool:
    return bridge.detect_phone_verification_required("phone-verification-required")


def run_autopilot(args: argparse.Namespace) -> None:
    offer_path = Path(args.offer)
    offer = load_offer(offer_path)
    banner = Path(args.banner) if args.banner else None
    steps = load_yaml(STEPS_PATH)
    values = build_offer_values(offer)
    plan_path = DATA / "offers" / f"{offer_path.stem}.autopilot-plan.yaml"

    report = RpaReport(mode=f"autopilot:{args.action}", target_url=str(steps.get("open") or DEFAULT_DRAFT_URL))
    report.title = "Kwork Autopilot Report"
    for key, value in values.items():
        report.hash_value(key, value)

    plan = plan_values(steps, offer_path, banner, values)
    write_plan(plan_path, {"mode": args.mode, **plan})
    report.action(f"wrote autopilot plan: {rel(plan_path)}")

    if args.action == "dry-run":
        write_autopilot_report(report)
        print(plan_path)
        print(AUTOPILOT_REPORT_PATH)
        return

    if args.action == "run":
        require_manual_approval("Kwork autopilot run", args.approve)
    if args.save_draft:
        require_manual_approval("Kwork safe draft save", args.approve)

    with KworkRpaBridge(report) as bridge:
        bridge.open(str(steps.get("open") or DEFAULT_DRAFT_URL))
        bridge.wait_and_screenshot("autopilot-open")
        login_state = bridge.detect_login_state()
        if steps.get("require_login") and login_state is not True:
            report.warn("login_detected is not true; autopilot stopped before clicks/fill")
            bridge.collect_fields()
            bridge.wait_and_screenshot("autopilot-login-gate")
            write_autopilot_report(report)
            print(AUTOPILOT_REPORT_PATH)
            if args.hold:
                bridge.hold_open()
            return

        bridge.collect_fields()
        if args.action == "preview":
            blocked = bridge.find_blocked_buttons()
            if blocked:
                report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
            bridge.wait_and_screenshot("autopilot-preview")
            report.next_safe_command = f"python scripts/kwork_autopilot.py --offer {offer_path} --mode create-kwork --run --approve --hold"
            write_autopilot_report(report)
            print(AUTOPILOT_REPORT_PATH)
            if args.hold:
                bridge.hold_open()
            return

        bridge.close_popups_safe()
        click_steps = list((steps.get("click") or {}).get("text") or [])
        for text in click_steps:
            bridge.click_text_safe(str(text))
            if bridge.stopped:
                write_autopilot_report(report)
                print(AUTOPILOT_REPORT_PATH)
                if args.hold:
                    bridge.hold_open()
                return
        if "manage_kworks" in bridge.page.url:
            click_create_kwork_button(bridge)
            if stop_if_phone_verification_required(bridge):
                report.next_safe_command = "manual phone verification in visible browser; automation will not request calls or enter phone data"
                write_autopilot_report(report)
                print(AUTOPILOT_REPORT_PATH)
                if args.hold:
                    bridge.hold_open()
                return
        if DEFAULT_DRAFT_URL not in bridge.page.url:
            bridge.open(DEFAULT_DRAFT_URL)
        if "manage_kworks" in bridge.page.url:
            click_create_kwork_button(bridge)
        if stop_if_phone_verification_required(bridge):
            report.next_safe_command = "manual phone verification in visible browser; automation will not request calls or enter phone data"
            write_autopilot_report(report)
            print(AUTOPILOT_REPORT_PATH)
            if args.hold:
                bridge.hold_open()
            return
        bridge.wait_and_screenshot("autopilot-create-mode")

        category_cfg = steps.get("choose_category") or {}
        bridge.choose_category_safe(
            str(category_cfg.get("category") or ""),
            [str(item) for item in category_cfg.get("subcategory_candidates", [])],
        )

        if steps.get("fill_offer_fields"):
            fill_offer_fields(bridge, offer, banner if steps.get("upload_cover_if_exists") else None)
        bridge.wait_and_screenshot(str(steps.get("screenshot") or "after-fill"))

        if args.save_draft:
            maybe_save_draft(bridge, args.approve)
            bridge.wait_and_screenshot("after-save-draft")

        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        report.next_safe_command = "manual review in visible browser; automation will not publish/send/delete"
        write_autopilot_report(report)
        print(AUTOPILOT_REPORT_PATH)
        if args.hold:
            bridge.hold_open()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offer", required=True)
    parser.add_argument("--banner")
    parser.add_argument("--mode", choices=["create-kwork"], required=True)
    parser.add_argument("--dry-run", dest="action", action="store_const", const="dry-run")
    parser.add_argument("--preview", dest="action", action="store_const", const="preview")
    parser.add_argument("--run", dest="action", action="store_const", const="run")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")
    parser.add_argument("--save-draft", action="store_true")
    args = parser.parse_args()

    if not args.action:
        raise SystemExit("Choose exactly one action: --dry-run, --preview, or --run")
    run_autopilot(args)


if __name__ == "__main__":
    main()
