#!/usr/bin/env python3
"""Guarded Windows CDP fill flows for Kwork profile and first kwork setup.

This script may fill safe text fields, but it never clicks save, publish,
moderation, send, order, withdrawal, phone, delete, or confirmation buttons.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from account_optimizer_common import PROFILE_SETTINGS_URL
from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL, run_check_zerroone


PROFILE_PATH = DATA / "profile" / "profile_optimized.json"
FIRST_OFFER_PATH = DATA / "offers" / "first_money_offer.json"
FACTORY_OFFER_PATH = DATA / "offers" / "factory" / "telegram_leads_bot.json"
PROFILE_REPORT_PATH = REPORTS / "profile_fill_cdp_report.md"
KWORK_REPORT_PATH = REPORTS / "kwork_fill_cdp_report.md"

USER_NEXT_PROFILE = "Проверь поля глазами. Если всё правильно — только пользователь вручную нажимает сохранение."
USER_NEXT_KWORK = "Проверь кворк глазами. Если всё правильно — только пользователь вручную решает, сохранять или отправлять на модерацию."

SENSITIVE_RE = "cookie|token|csrf|password|passwd|secret|session|phone|sms|email"


@dataclass
class FillReport:
    target: str
    report_path: Path
    browser_mode: str = "windows_cdp"
    cdp_connected: str = "false"
    detected_username: str = "unknown"
    login_detected: str = "unknown"
    account_guard_status: str = "not_checked"
    account_guard_action: str = "not_checked"
    persistence_confirmed: str = "false"
    final_url: str = "not_opened"
    page_title: str = "unknown"
    phone_verification_detected: bool = False
    kwork_title: str = ""
    fields_found: list[str] = field(default_factory=list)
    fields_filled: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    final_buttons_blocked: bool = False
    final_buttons: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    user_next_step: str = ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def joined(value: Any) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                q = item.get("q", "")
                a = item.get("a", "")
                parts.append(f"Вопрос: {q}\nОтвет: {a}".strip())
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {joined(item)}" for key, item in value.items())
    return "" if value is None else str(value)


def load_profile_values() -> dict[str, str]:
    profile = read_json(PROFILE_PATH)
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
    return {
        "headline": profile.get("headline", ""),
        "profile_details": profile_details,
    }


def package_text(name: str, package: dict[str, Any]) -> str:
    includes = "\n".join(f"- {item}" for item in package.get("includes", []))
    return "\n".join(part for part in [package.get("name", name), includes] if part)


def load_kwork_values() -> dict[str, str]:
    offer = read_json(FIRST_OFFER_PATH)
    factory = read_json(FACTORY_OFFER_PATH)
    merged = {**factory, **offer}
    title = merged.get("title") or "Сделаю Telegram-бота для заявок с записью в Google Таблицу"
    faq = merged.get("faq") or merged.get("FAQ") or []
    questions = merged.get("buyer_questions") or []
    tags = merged.get("tags") or []
    economy = merged.get("economy_package") or merged.get("packages", {}).get("economy", {})
    standard = merged.get("standard_package") or merged.get("packages", {}).get("standard", {})
    premium = merged.get("premium_package") or merged.get("packages", {}).get("business", {})
    return {
        "title": title,
        "description": merged.get("full_description") or merged.get("short_description") or "",
        "short_description": merged.get("short_description") or "",
        "economy_description": package_text("Базовый", economy),
        "standard_description": package_text("Стандарт", standard),
        "premium_description": package_text("Бизнес", premium),
        "economy_price": str(economy.get("price_from") or merged.get("price_economy") or merged.get("starting_price") or 3000),
        "standard_price": str(standard.get("price_from") or merged.get("price_standard") or merged.get("recommended_price") or 5500),
        "premium_price": str(premium.get("price_from") or merged.get("price_premium") or merged.get("premium_price") or 9000),
        "economy_days": str(economy.get("days") or merged.get("delivery_days_economy") or 3),
        "standard_days": str(standard.get("days") or merged.get("delivery_days_standard") or 4),
        "premium_days": str(premium.get("days") or merged.get("delivery_days_premium") or 7),
        "faq": joined(faq),
        "buyer_questions": joined(questions),
        "tags": ", ".join(str(item) for item in tags),
    }


def field_specs(target: str, values: dict[str, str]) -> list[dict[str, Any]]:
    if target == "profile":
        return [
            {
                "name": "headline",
                "value": values.get("headline", ""),
                "selectors": ["textarea[name='profession']", "input[name='profession']", "input[name*='headline']", "input[name*='position']"],
                "hints": ["Специализация", "Заголовок", "Профессия", "headline", "position"],
            },
            {
                "name": "profile_details",
                "value": values.get("profile_details", ""),
                "selectors": ["textarea[name='details']", "textarea[name*='description']", "textarea[name*='about']"],
                "hints": ["Навыки", "О себе", "Описание", "details", "about"],
            },
        ]
    return [
        {"name": "title", "value": values.get("title", ""), "selectors": ["#editor-title", "#step1-name", "input[name='name']", "textarea[name='name']"], "hints": ["Название", "Заголовок", "name"]},
        {"name": "description", "value": values.get("description", ""), "selectors": ["#step1-description", ".trumbowyg-editor", "textarea[name='description']"], "hints": ["Описание", "description"]},
        {"name": "economy_description", "value": values.get("economy_description", ""), "selectors": ["textarea[name*='package'][name*='1']", "textarea[name*='economy']"], "hints": ["Эконом", "Базовый", "Первый пакет"]},
        {"name": "standard_description", "value": values.get("standard_description", ""), "selectors": ["textarea[name*='package'][name*='2']", "textarea[name*='standard']"], "hints": ["Стандарт", "Второй пакет"]},
        {"name": "premium_description", "value": values.get("premium_description", ""), "selectors": ["textarea[name*='package'][name*='3']", "textarea[name*='premium']", "textarea[name*='business']"], "hints": ["Бизнес", "Премиум", "Третий пакет"]},
        {"name": "economy_price", "value": values.get("economy_price", ""), "selectors": ["input[name*='price'][name*='1']", "input[name*='economy'][name*='price']"], "hints": ["Цена", "Эконом", "Базовый"]},
        {"name": "standard_price", "value": values.get("standard_price", ""), "selectors": ["input[name*='price'][name*='2']", "input[name*='standard'][name*='price']"], "hints": ["Цена", "Стандарт"]},
        {"name": "premium_price", "value": values.get("premium_price", ""), "selectors": ["input[name*='price'][name*='3']", "input[name*='premium'][name*='price']", "input[name*='business'][name*='price']"], "hints": ["Цена", "Бизнес", "Премиум"]},
        {"name": "faq", "value": values.get("faq", ""), "selectors": ["textarea[name*='faq']", "textarea[name*='question']"], "hints": ["FAQ", "Вопрос", "Ответ"]},
        {"name": "buyer_questions", "value": values.get("buyer_questions", ""), "selectors": ["textarea[name*='requirement']", "textarea[name*='buyer']", "textarea[name*='question']"], "hints": ["Вопросы покупателю", "Требования", "Что нужно"]},
        {"name": "tags", "value": values.get("tags", ""), "selectors": ["input[name*='tag']", "textarea[name*='tag']"], "hints": ["Теги", "tags", "Ключевые слова"]},
    ]


def fill_fields(page, specs: list[dict[str, Any]]) -> dict[str, list[str]]:
    return page.evaluate(
        """({specs, sensitiveReSource}) => {
          const sensitiveRe = new RegExp(sensitiveReSource, 'i');
          const fieldsFound = [];
          const fieldsFilled = [];
          const missing = [];
          const visible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && !el.disabled && !el.readOnly;
          };
          const textOf = (el) => [
            el.id || '',
            el.name || '',
            el.placeholder || '',
            el.getAttribute('aria-label') || '',
            el.getAttribute('data-name') || '',
            el.closest('label') ? el.closest('label').innerText || '' : '',
            el.parentElement ? el.parentElement.innerText || '' : '',
          ].join(' ').replace(/\\s+/g, ' ').trim();
          const safe = (el) => !sensitiveRe.test([el.id, el.name, el.type, el.placeholder].join(' '));
          const setValue = (el, value) => {
            el.scrollIntoView({block: 'center', inline: 'nearest'});
            el.focus();
            if (el.isContentEditable) {
              el.innerText = value || '';
            } else {
              el.value = value || '';
            }
            el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value || ''}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
          };
          const all = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea, [contenteditable="true"]'))
            .filter(visible).filter(safe);
          const used = new Set();
          for (const spec of specs) {
            const value = spec.value || '';
            if (!value.trim()) {
              missing.push(spec.name + ':empty_value');
              continue;
            }
            let target = null;
            for (const selector of spec.selectors || []) {
              const items = Array.from(document.querySelectorAll(selector)).filter(visible).filter(safe).filter((el) => !used.has(el));
              if (items.length) {
                target = items[0];
                break;
              }
            }
            if (!target) {
              const hints = (spec.hints || []).map((item) => String(item).toLowerCase());
              target = all.find((el) => !used.has(el) && hints.some((hint) => textOf(el).toLowerCase().includes(hint))) || null;
            }
            if (!target) {
              missing.push(spec.name);
              continue;
            }
            fieldsFound.push(spec.name);
            setValue(target, value);
            used.add(target);
            fieldsFilled.push(spec.name);
          }
          return {fieldsFound, fieldsFilled, missing};
        }""",
        {"specs": specs, "sensitiveReSource": SENSITIVE_RE},
    )


def open_profile_tab(page) -> bool:
    """Open the profile tab without touching account/email/password fields."""
    try:
        if bool(
            page.evaluate(
                """() => {
                  const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                  };
                  const items = Array.from(document.querySelectorAll('.k-tabs__item, [role="tab"]'))
                    .filter(visible)
                    .filter((el) => (el.innerText || '').replace(/\\s+/g, ' ').trim() === 'Профиль');
                  if (items.length !== 1) return false;
                  items[0].setAttribute('data-cdp-profile-tab', 'true');
                  return true;
                }"""
            )
        ):
            page.locator("[data-cdp-profile-tab='true']").click(timeout=2500)
            page.wait_for_timeout(1200)
            return True
        return False
    except Exception:
        return False


def page_has_account_credentials(page) -> bool:
    try:
        data = page.evaluate(
            """() => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              return {
                email: Array.from(document.querySelectorAll('input[type="email"]')).filter(visible).length,
                password: Array.from(document.querySelectorAll('input[type="password"]')).filter(visible).length
              };
            }"""
        )
    except Exception:
        return False
    return int(data.get("email") or 0) > 0 or int(data.get("password") or 0) > 0


def write_report(report: FillReport) -> None:
    ensure_dir(report.report_path.parent)
    lines = [
        f"# Kwork CDP {report.target.title()} Fill Report",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- browser_mode: `{report.browser_mode}`",
        f"- cdp_connected: `{report.cdp_connected}`",
        f"- login_detected: `{report.login_detected}`",
        f"- detected_username: `{report.detected_username}`",
        f"- expected_username: `{EXPECTED_ACCOUNT}`",
        f"- account_guard_status: `{report.account_guard_status}`",
        f"- account_guard_action: `{report.account_guard_action}`",
        f"- persistence_confirmed: `{report.persistence_confirmed}`",
        f"- final_url: `{report.final_url}`",
        f"- page_title: `{report.page_title}`",
        f"- phone_verification_detected: `{str(report.phone_verification_detected).lower()}`",
        f"- kwork_title: `{report.kwork_title or 'n/a'}`",
        f"- fields_found: `{', '.join(report.fields_found) if report.fields_found else 'none'}`",
        f"- fields_filled: `{', '.join(report.fields_filled) if report.fields_filled else 'none'}`",
        f"- missing_fields: `{', '.join(report.missing_fields) if report.missing_fields else 'none'}`",
        f"- final_buttons_blocked: `{str(report.final_buttons_blocked).lower()}`",
        f"- final_buttons: `{', '.join(report.final_buttons) if report.final_buttons else 'none'}`",
        f"- user_next_step: `{report.user_next_step}`",
        "",
        "## Screenshots",
        *(f"- `{item}`" for item in report.screenshots),
        "",
        "## Warnings",
        *(f"- {item}" for item in report.warnings),
        "",
        "## Safety",
        "- Guarded Windows CDP fill only.",
        "- Uses only the dedicated ZerroOne Windows profile.",
        "- Does not use the legacy WSL profile or normal browser cookies.",
        "- Does not read cookies, local storage, passwords, tokens, phone, SMS, or credentials.",
        "- Does not click save, publish, moderation, send, order, withdrawal, phone, delete, or confirmation buttons.",
    ]
    report.report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def ensure_cdp_guard(report: FillReport) -> bool:
    check = run_check_zerroone(restart_check=True)
    report.cdp_connected = str(check.cdp_connected).lower()
    report.detected_username = check.detected_username
    report.login_detected = check.login_detected
    report.account_guard_status = check.account_guard_status
    report.account_guard_action = check.account_guard_action
    report.persistence_confirmed = str(check.persistence_confirmed).lower()
    if not check.cdp_connected:
        report.warnings.append("CDP connection failed; fill stopped.")
        return False
    if check.detected_username.lower() != EXPECTED_ACCOUNT.lower():
        report.warnings.append(f"Detected username is {check.detected_username}; expected {EXPECTED_ACCOUNT}. Fill stopped.")
        return False
    if check.account_guard_status != "ok":
        report.warnings.append(f"Account Guard is {check.account_guard_status}; fill stopped.")
        return False
    if not check.persistence_confirmed:
        report.warnings.append("Windows CDP persistence is not confirmed; fill stopped.")
        return False
    return True


def run_fill(target: str) -> FillReport:
    report = FillReport(
        target=target,
        report_path=PROFILE_REPORT_PATH if target == "profile" else KWORK_REPORT_PATH,
        user_next_step=USER_NEXT_PROFILE if target == "profile" else USER_NEXT_KWORK,
    )
    if not ensure_cdp_guard(report):
        write_report(report)
        print(report.report_path)
        return report

    values = load_profile_values() if target == "profile" else load_kwork_values()
    report.kwork_title = values.get("title", "") if target == "kwork" else ""
    url = PROFILE_SETTINGS_URL if target == "profile" else DEFAULT_DRAFT_URL

    with open_kwork_browser_session(mode="windows_cdp", account=EXPECTED_ACCOUNT, start_url=MANAGE_KWORKS_URL, keep_open=True) as session:
        session.open(url)
        diag = session.refresh_diagnostics()
        report.final_url = diag.current_url
        report.page_title = diag.page_title
        report.cdp_connected = str(diag.cdp_connected).lower()
        report.login_detected = diag.login_detected
        report.detected_username = diag.detected_username
        report.account_guard_status = diag.account_guard_status
        report.account_guard_action = diag.account_guard_action
        report.phone_verification_detected = bool(
            "new_phone_verify=1" in report.final_url or PHONE_VERIFICATION_RE.search(session.visible_text())
        )
        if diag.account_guard_status != "ok" or report.phone_verification_detected:
            report.warnings.append("Guard or phone verification stopped fill before field changes.")
        elif target == "profile" and not open_profile_tab(session.page):
            report.warnings.append("Profile tab was not found uniquely; account settings fields were not touched.")
        elif target == "profile" and page_has_account_credentials(session.page):
            report.warnings.append("Visible account credential fields detected after tab switch; profile fill stopped.")
        else:
            result = fill_fields(session.page, field_specs(target, values))
            report.fields_found = result.get("fieldsFound", [])
            report.fields_filled = result.get("fieldsFilled", [])
            report.missing_fields = result.get("missing", [])
            session.page.wait_for_timeout(800)
        report.final_buttons = session.find_blocked_buttons()
        report.final_buttons_blocked = bool(report.final_buttons)
        shot = session.screenshot(f"{target}-fill-cdp")
        if shot:
            report.screenshots.append(shot)
    write_report(report)
    print(report.report_path)
    print(f"browser_mode={report.browser_mode}")
    print(f"cdp_connected={report.cdp_connected}")
    print(f"login_detected={report.login_detected}")
    print(f"detected_username={report.detected_username}")
    print(f"account_guard_status={report.account_guard_status}")
    print(f"persistence_confirmed={report.persistence_confirmed}")
    print(f"phone_verification_detected={str(report.phone_verification_detected).lower()}")
    print(f"fields_found={', '.join(report.fields_found) if report.fields_found else 'none'}")
    print(f"fields_filled={', '.join(report.fields_filled) if report.fields_filled else 'none'}")
    print(f"missing_fields={', '.join(report.missing_fields) if report.missing_fields else 'none'}")
    print(f"final_buttons_blocked={str(report.final_buttons_blocked).lower()}")
    print(f"final_buttons={', '.join(report.final_buttons) if report.final_buttons else 'none'}")
    print(f"user_next_step={report.user_next_step}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded Windows CDP fill without final buttons")
    parser.add_argument("--target", choices=["profile", "kwork"], required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_fill(args.target)


if __name__ == "__main__":
    main()
