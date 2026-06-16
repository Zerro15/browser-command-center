#!/usr/bin/env python3
"""Preview or upload selected cover through guarded Windows CDP."""

from __future__ import annotations

import argparse

from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_studio_common import COVER_SCORES, COVER_UPLOAD_REPORT, SELECTED_COVER, ensure_studio_dirs, read_json, rel, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL, run_check_zerroone


def selected_cover_path():
    data = read_json(COVER_SCORES, {})
    selected = data.get("selected_cover") if isinstance(data, dict) else ""
    return SELECTED_COVER if not selected else SELECTED_COVER.parents[1] / selected.replace("data/kwork_studio/", "")


def run(mode: str) -> None:
    ensure_studio_dirs()
    check = run_check_zerroone(restart_check=True)
    uploaded = False
    warnings = []
    cover = selected_cover_path()
    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=MANAGE_KWORKS_URL,
        keep_open=True,
        background=(mode == "preview"),
        no_focus=(mode == "preview"),
        minimized=(mode == "preview"),
    ) as session:
        session.open(DEFAULT_DRAFT_URL)
        diag = session.refresh_diagnostics()
        phone = bool("new_phone_verify=1" in diag.current_url or PHONE_VERIFICATION_RE.search(session.visible_text()))
        if not check.persistence_confirmed or check.account_guard_status != "ok" or diag.account_guard_status != "ok" or phone:
            warnings.append("guard/persistence/phone check stopped cover action")
        elif mode == "upload":
            if not cover.exists():
                warnings.append(f"selected cover missing: {cover}")
            else:
                try:
                    file_inputs = session.page.locator("input[type='file']")
                    if file_inputs.count() < 1:
                        warnings.append("file input not found on current kwork step")
                    else:
                        file_inputs.first.set_input_files(str(cover))
                        uploaded = True
                        session.page.wait_for_timeout(1200)
                except Exception as error:
                    warnings.append(f"cover upload failed safely: {error}")
        final_buttons = session.find_blocked_buttons()
        shot = session.screenshot(f"cover-{mode}-cdp")
    lines = [
        "# Kwork Cover CDP Report",
        "",
        f"- mode: `{mode}`",
        "- browser_mode: `windows_cdp`",
        f"- cdp_connected: `{str(diag.cdp_connected).lower()}`",
        f"- detected_username: `{diag.detected_username}`",
        f"- account_guard_status: `{diag.account_guard_status}`",
        f"- persistence_confirmed: `{str(check.persistence_confirmed).lower()}`",
        f"- selected_cover: `{rel(cover)}`",
        f"- cover_uploaded: `{str(uploaded).lower()}`",
        f"- phone_verification_detected: `{str(phone).lower()}`",
        f"- final_buttons_blocked: `{str(bool(final_buttons)).lower()}`",
        f"- final_buttons: `{', '.join(final_buttons) if final_buttons else 'none'}`",
        f"- foreground_policy: `{diag.foreground_policy}`",
        f"- background_mode: `{str(diag.background_mode).lower()}`",
        f"- brought_to_front_count: `{diag.brought_to_front_count}`",
        f"- screenshot: `{shot}`",
        f"- user_next_step: `Окно готово для проверки, открой его вручную на панели задач.`",
        "",
        "## Warnings",
        *(f"- {item}" for item in warnings),
        "",
        "## Safety",
        "- No save/moderation/publish/send buttons clicked.",
    ]
    write_text(COVER_UPLOAD_REPORT, "\n".join(lines))
    print(COVER_UPLOAD_REPORT)
    print(f"mode={mode}")
    print(f"cover_uploaded={str(uploaded).lower()}")
    print(f"final_buttons_blocked={str(bool(final_buttons)).lower()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preview", "upload"], required=True)
    run(parser.parse_args().mode)


if __name__ == "__main__":
    main()
