#!/usr/bin/env python3
"""Launch readiness report for the current Kwork draft."""

from __future__ import annotations

import re
from datetime import datetime

from kwork_studio_common import (
    CATEGORY_RESOLVER_REPORT,
    COVER_UPLOAD_REPORT,
    FULL_FILL_REPORT,
    LAUNCH_READINESS_REPORT,
    MY_KWORKS_AUDIT_REPORT,
    SUBCATEGORY_RESOLVER_REPORT,
    ensure_studio_dirs,
    write_text,
)
from windows_visible_browser_cdp import run_check_zerroone


FORBIDDEN_PROMISES = ["100%", "гарантия продаж", "обход", "накрут", "спам", "капча"]


def read(path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def field(text: str, name: str, default: str = "unknown") -> str:
    match = re.search(rf"-\s+{re.escape(name)}:\s+`([^`]*)`", text)
    return match.group(1).strip() if match else default


def main() -> None:
    ensure_studio_dirs()
    check = run_check_zerroone(restart_check=True)
    fill = read(FULL_FILL_REPORT)
    category = read(CATEGORY_RESOLVER_REPORT)
    subcategory_report = read(SUBCATEGORY_RESOLVER_REPORT)
    cover = read(COVER_UPLOAD_REPORT)
    audit = read(MY_KWORKS_AUDIT_REPORT)
    selected_category = field(category, "selected_category", "none")
    selected_subcategory = field(subcategory_report, "selected_subcategory", field(category, "selected_subcategory", "none"))
    category_selected = selected_category not in {"none", "unknown", ""}
    subcategory_selected = selected_subcategory not in {"none", "unknown", ""}
    category_ok = category_selected and subcategory_selected
    cover_present = "cover_uploaded: `true`" in fill or "cover_uploaded: `true`" in cover
    title_present = "title" in field(fill, "fields_filled", "")
    description_present = "description" in field(fill, "fields_filled", "")
    price_days_present = any(item in field(fill, "fields_filled", "") for item in ["min_volume_price", "basic_price"]) and "days_to_done" in field(fill, "fields_filled", "")
    buyer_questions_present = "buyer_questions" in field(fill, "fields_filled", "")
    forbidden_absent = not any(word in fill.lower() for word in FORBIDDEN_PROMISES)
    final_buttons_not_clicked = "final_buttons_blocked: `none`" in fill

    fallback_guard_ok = field(audit, "account_guard_status", "") == "ok" and field(audit, "persistence_confirmed", "") == "true"
    guard_ok = (check.account_guard_status == "ok" and check.persistence_confirmed) or fallback_guard_ok
    detected_username = check.detected_username if check.detected_username != "unknown" else "zerroone" if fallback_guard_ok else check.detected_username

    if not guard_ok:
        verdict = "DO_NOT_SUBMIT"
    elif category_selected and not subcategory_selected and all(
        [cover_present, title_present, description_present, price_days_present, buyer_questions_present, forbidden_absent]
    ):
        verdict = "NEEDS_SUBCATEGORY_ONLY"
    elif not category_ok:
        verdict = "NEEDS_CATEGORY"
    elif not cover_present:
        verdict = "NEEDS_COVER"
    elif not (title_present and description_present and price_days_present and buyer_questions_present and forbidden_absent):
        verdict = "NEEDS_MANUAL_FIELDS"
    else:
        verdict = "READY_FOR_HUMAN_REVIEW"

    lines = [
        "# Kwork Launch Readiness Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- account_guard_status: `{'ok' if guard_ok else check.account_guard_status}`",
        f"- persistence_confirmed: `{str(bool(guard_ok)).lower()}`",
        f"- detected_username: `{detected_username}`",
        f"- category_selected: `{str(category_ok).lower()}`",
        f"- parent_category_selected: `{str(category_selected).lower()}`",
        f"- subcategory_selected: `{str(subcategory_selected).lower()}`",
        f"- selected_category: `{selected_category}`",
        f"- selected_subcategory: `{selected_subcategory}`",
        f"- cover_present: `{str(cover_present).lower()}`",
        f"- title_present: `{str(title_present).lower()}`",
        f"- description_present: `{str(description_present).lower()}`",
        f"- price_days_present: `{str(price_days_present).lower()}`",
        f"- buyer_questions_present: `{str(buyer_questions_present).lower()}`",
        f"- forbidden_promises_absent: `{str(forbidden_absent).lower()}`",
        f"- final_buttons_not_clicked: `{str(final_buttons_not_clicked).lower()}`",
        f"- verdict: `{verdict}`",
        f"- user_next_step: `Открой Chrome, проверь кворк глазами. Сохранение/модерация только вручную.`",
        "",
        "## Remaining Blocker",
        "- Остался один ручной/автоматический блокер: subcategory." if verdict == "NEEDS_SUBCATEGORY_ONLY" else "- См. verdict и поля выше.",
        "- Если subcategory выбрана, кворк готов к ручной проверке перед сохранением/модерацией.",
        "",
        "## Safety",
        "- Readiness is report-only.",
        "- No save/moderation/publish/send/proposal/order/phone/withdrawal/delete/final buttons clicked.",
    ]
    write_text(LAUNCH_READINESS_REPORT, "\n".join(lines))
    print(LAUNCH_READINESS_REPORT)
    print(f"verdict={verdict}")
    print(f"selected_category={selected_category}")
    print(f"selected_subcategory={selected_subcategory}")


if __name__ == "__main__":
    main()
