#!/usr/bin/env python3
"""Safely insert one prepared Kwork reply draft without sending it."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from account_optimizer_common import (
    INBOX_URL,
    add_mode_args,
    build_plan_report,
    parse_mode,
    read_json,
    require_run_approval,
    strict_login_gate,
)
from _common import DATA, REPORTS
from browser_rpa_bridge import KworkRpaBridge, RpaReport


DRAFTS_JSON = DATA / "replies" / "reply_drafts.json"
REPORT_PATH = REPORTS / "reply_fill_report.md"
PLAN_PATH = REPORTS / "reply_fill_plan.md"


def load_draft(path: Path, draft_id: str) -> dict[str, Any]:
    data = read_json(path, {})
    drafts = data.get("drafts", []) if isinstance(data, dict) else data
    for draft in drafts:
        if str(draft.get("id")) == draft_id:
            return draft
    raise SystemExit(f"Draft id not found: {draft_id}")


def fill_reply_box(bridge: KworkRpaBridge, text: str) -> bool:
    bridge.report.hash_value("reply_draft", text)
    if not bridge.available:
        return False
    try:
        result = bridge.page.evaluate(
            """(text) => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const labelOf = (el) => [
                el.getAttribute('placeholder'),
                el.getAttribute('aria-label'),
                el.name,
                el.id,
                el.closest('label') ? el.closest('label').innerText : ''
              ].filter(Boolean).join(' ').toLowerCase();
              const candidates = Array.from(document.querySelectorAll('textarea, [contenteditable="true"]'))
                .filter(visible)
                .filter((el) => /сообщ|ответ|message|reply|напис/i.test(labelOf(el) + ' ' + (el.innerText || '')));
              const fallback = Array.from(document.querySelectorAll('textarea, [contenteditable="true"]')).filter(visible);
              const fields = candidates.length ? candidates : fallback;
              if (fields.length !== 1) {
                return {ok: false, count: fields.length};
              }
              const field = fields[0];
              field.scrollIntoView({block: 'center'});
              field.focus();
              if (field.isContentEditable) {
                field.innerText = text;
              } else {
                field.value = text;
              }
              field.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
              field.dispatchEvent(new Event('change', {bubbles: true}));
              return {ok: true, count: 1};
            }""",
            text,
        )
    except Exception as error:
        bridge.report.warn(f"reply field fill failed: {error}")
        return False
    if result.get("ok"):
        bridge.report.action(f"filled reply draft field ({len(text)} chars)")
        return True
    bridge.report.warn(f"reply field ambiguous or missing; candidates: {result.get('count')}")
    return False


def run_filler(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    drafts_path = Path(args.drafts)
    if mode == "dry-run":
        build_plan_report(
            PLAN_PATH,
            "Kwork Reply Fill Plan",
            mode,
            [
                f"Read draft id {args.draft_id} from {drafts_path}.",
                "Open the dialog URL only in preview/run.",
                "Require login_detected == true.",
                "Fill one reply text field only in --run --approve.",
                "Never click Send.",
            ],
        )
        print(PLAN_PATH)
        return
    require_run_approval(mode, args.approve, "Kwork reply draft filling")
    draft = load_draft(drafts_path, args.draft_id)
    dialog_url = args.dialog_url or draft.get("dialog_url") or INBOX_URL
    reply = str(draft.get("reply_draft") or "")
    if not reply.strip():
        raise SystemExit(f"Draft {args.draft_id} has empty reply_draft")

    report = RpaReport(mode=f"reply-fill:{mode}", target_url=dialog_url, title="Kwork Reply Fill Report")
    with KworkRpaBridge(report) as bridge:
        bridge.open(dialog_url)
        bridge.wait_and_screenshot("reply-fill-before")
        bridge.collect_fields()
        if not strict_login_gate(bridge, REPORT_PATH):
            if args.hold:
                bridge.hold_open()
            print(REPORT_PATH)
            return
        if mode == "run":
            fill_reply_box(bridge, reply)
            bridge.wait_and_screenshot("reply-fill-after")
            report.next_safe_command = "manual review in visible browser; user sends manually"
        else:
            report.next_safe_command = f"python scripts/fill_reply_draft.py --draft-id {args.draft_id} --run --approve --hold"
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        report.write(REPORT_PATH)
        if args.hold:
            bridge.hold_open()
    print(REPORT_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-id", required=True)
    parser.add_argument("--drafts", default=str(DRAFTS_JSON))
    parser.add_argument("--dialog-url", default=None)
    add_mode_args(parser)
    run_filler(parser.parse_args())


if __name__ == "__main__":
    main()
