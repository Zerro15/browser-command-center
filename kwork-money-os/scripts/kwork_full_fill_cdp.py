#!/usr/bin/env python3
"""Multi-step guarded Windows CDP fill for the first Kwork draft."""

from __future__ import annotations

import argparse
from typing import Any

from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_cdp_fill import fill_fields
from kwork_studio_common import (
    ALLOWED_NEXT_LABELS,
    COVER_SCORES,
    DOM_SNAPSHOT,
    FINAL_BUTTONS,
    FULL_FILL_REPORT,
    SELECTED_COVER,
    SPEC_JSON,
    build_first_kwork_spec,
    ensure_studio_dirs,
    read_json,
    rel,
    write_json,
    write_text,
)
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL, run_check_zerroone


def selected_cover_path():
    data = read_json(COVER_SCORES, {})
    selected = data.get("selected_cover") if isinstance(data, dict) else ""
    return SELECTED_COVER if not selected else SELECTED_COVER.parents[1] / selected.replace("data/kwork_studio/", "")


def spec_values() -> dict[str, str]:
    spec = read_json(SPEC_JSON, {}) or build_first_kwork_spec()
    packages = spec.get("packages", {})
    faq = "\n".join(f"Вопрос: {item.get('q')}\nОтвет: {item.get('a')}" for item in spec.get("faq", []))
    questions = "\n".join(spec.get("buyer_questions", []))
    tags = ", ".join(spec.get("tags", []))
    return {
        "title": spec.get("title", ""),
        "description": spec.get("description", ""),
        "short_hook": spec.get("short_hook", ""),
        "basic_package": package_text(packages.get("basic", {})),
        "standard_package": package_text(packages.get("standard", {})),
        "premium_package": package_text(packages.get("premium", {})),
        "basic_price": str(packages.get("basic", {}).get("price", "")),
        "standard_price": str(packages.get("standard", {}).get("price", "")),
        "premium_price": str(packages.get("premium", {}).get("price", "")),
        "basic_days": str(packages.get("basic", {}).get("days", "")),
        "standard_days": str(packages.get("standard", {}).get("days", "")),
        "premium_days": str(packages.get("premium", {}).get("days", "")),
        "faq": faq,
        "buyer_questions": questions,
        "tags": tags,
        "category": spec.get("category", ""),
        "subcategory": spec.get("subcategory", ""),
    }


def package_text(package: dict[str, Any]) -> str:
    return "\n".join([package.get("name", ""), *(f"- {item}" for item in package.get("includes", []))]).strip()


def field_specs(values: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"name": "title", "value": values["title"], "selectors": ["#editor-title", "#step1-name", "input[name='name']"], "hints": ["Название", "Заголовок"]},
        {"name": "description", "value": values["description"], "selectors": ["#step1-description", ".trumbowyg-editor", "textarea[name='description']"], "hints": ["Описание"]},
        {"name": "basic_package", "value": values["basic_package"], "selectors": ["textarea[name*='package'][name*='1']", "textarea[name*='basic']", "textarea[name*='economy']"], "hints": ["Базовый", "Эконом"]},
        {"name": "standard_package", "value": values["standard_package"], "selectors": ["textarea[name*='package'][name*='2']", "textarea[name*='standard']"], "hints": ["Стандарт"]},
        {"name": "premium_package", "value": values["premium_package"], "selectors": ["textarea[name*='package'][name*='3']", "textarea[name*='premium']", "textarea[name*='business']"], "hints": ["Бизнес", "Премиум"]},
        {"name": "basic_price", "value": values["basic_price"], "selectors": ["input[name*='price'][name*='1']", "input[name*='economy'][name*='price']"], "hints": ["Цена", "Эконом", "Базовый"]},
        {"name": "standard_price", "value": values["standard_price"], "selectors": ["input[name*='price'][name*='2']", "input[name*='standard'][name*='price']"], "hints": ["Цена", "Стандарт"]},
        {"name": "premium_price", "value": values["premium_price"], "selectors": ["input[name*='price'][name*='3']", "input[name*='premium'][name*='price']", "input[name*='business'][name*='price']"], "hints": ["Цена", "Бизнес", "Премиум"]},
        {"name": "basic_days", "value": values["basic_days"], "selectors": ["input[name*='day'][name*='1']", "input[name*='duration'][name*='1']"], "hints": ["Срок", "дней", "Базовый"]},
        {"name": "standard_days", "value": values["standard_days"], "selectors": ["input[name*='day'][name*='2']", "input[name*='duration'][name*='2']"], "hints": ["Срок", "дней", "Стандарт"]},
        {"name": "premium_days", "value": values["premium_days"], "selectors": ["input[name*='day'][name*='3']", "input[name*='duration'][name*='3']"], "hints": ["Срок", "дней", "Премиум"]},
        {"name": "faq", "value": values["faq"], "selectors": ["textarea[name*='faq']", "textarea[name*='question']"], "hints": ["FAQ", "Вопрос", "Ответ"]},
        {"name": "buyer_questions", "value": values["buyer_questions"], "selectors": ["textarea[name*='requirement']", "textarea[name*='buyer']"], "hints": ["Вопросы покупателю", "Требования", "Что нужно"]},
        {"name": "tags", "value": values["tags"], "selectors": ["input[name*='tag']", "textarea[name*='tag']"], "hints": ["Теги", "Ключевые слова"]},
    ]


def fill_category(page, values: dict[str, str]) -> list[str]:
    return page.evaluate(
        """({category, subcategory}) => {
          const changed = [];
          const visible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          for (const select of Array.from(document.querySelectorAll('select')).filter(visible)) {
            const options = Array.from(select.options || []);
            const wanted = options.find((o) => new RegExp(category.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'i').test(o.textContent || ''))
              || options.find((o) => new RegExp('чат|telegram|бот', 'i').test(o.textContent || ''));
            if (wanted) {
              select.value = wanted.value;
              select.dispatchEvent(new Event('change', {bubbles: true}));
              changed.push(select.name || select.id || 'select');
            }
          }
          return changed;
        }""",
        {"category": values["category"], "subcategory": values["subcategory"]},
    )


def fill_current_kwork_specific_fields(page, values: dict[str, str]) -> list[str]:
    return page.evaluate(
        """({values}) => {
          const changed = [];
          const visible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && !el.disabled && !el.readOnly;
          };
          const set = (el, value, label) => {
            if (!el || !visible(el)) return false;
            el.scrollIntoView({block: 'center', inline: 'nearest'});
            el.focus();
            el.value = value;
            el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            changed.push(label);
            return true;
          };
          set(document.querySelector('input[name="package_volume"]'), '1', 'package_volume');
          const price = document.querySelector('select[name="min_volume_price"]');
          if (price && visible(price)) {
            const wanted = Array.from(price.options || []).find((opt) => /3000|3\\s*000/.test(opt.textContent || opt.value || ''));
            if (wanted) {
              price.value = wanted.value;
              price.dispatchEvent(new Event('change', {bubbles: true}));
              changed.push('min_volume_price');
            }
          }
          const extraTextareas = Array.from(document.querySelectorAll('textarea')).filter(visible).filter((el) => (el.value || '').trim().length < 20);
          if (extraTextareas[0]) set(extraTextareas[0], values.short_hook || values.basic_package, 'short_hook_or_package_note');
          return changed;
        }""",
        {"values": values},
    )


def upload_cover(page, cover) -> bool:
    if not cover.exists():
        return False
    try:
        inputs = page.locator("input[type='file']")
        if inputs.count() < 1:
            return False
        inputs.first.set_input_files(str(cover))
        page.wait_for_timeout(1000)
        return True
    except Exception:
        return False


def click_allowed_next(page) -> str:
    return page.evaluate(
        """({allowed, forbidden}) => {
          const visible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const buttons = Array.from(document.querySelectorAll('button, a, input[type="button"], input[type="submit"]')).filter(visible);
          for (const el of buttons) {
            const label = (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
            if (!label) continue;
            if (forbidden.some((item) => label.includes(item))) continue;
            if (allowed.some((item) => label.includes(item))) {
              el.click();
              return label;
            }
          }
          return '';
        }""",
        {"allowed": ALLOWED_NEXT_LABELS, "forbidden": FINAL_BUTTONS},
    )


def snapshot_dom(page) -> None:
    data = page.evaluate(
        """() => Array.from(document.querySelectorAll('input:not([type=hidden]), textarea, [contenteditable=true], select, button, a'))
          .slice(0, 350)
          .map((el, i) => ({
            index: i,
            tag: el.tagName,
            type: el.type || '',
            id: el.id || '',
            name: el.name || '',
            className: String(el.className || '').slice(0, 100),
            text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 160)
          }))"""
    )
    write_json(DOM_SNAPSHOT, data)


def run(background: bool) -> dict[str, Any]:
    ensure_studio_dirs()
    check = run_check_zerroone(restart_check=True)
    values = spec_values()
    result = {
        "browser_mode": "windows_cdp",
        "steps_visited": [],
        "fields_found": [],
        "fields_filled": [],
        "fields_missing": [],
        "allowed_navigation_clicked": [],
        "final_buttons_blocked": [],
        "cover_uploaded": False,
        "foreground_policy": "unknown",
        "background_mode": background,
        "brought_to_front_count": 0,
        "user_next_step": "Окно готово для проверки, открой его вручную на панели задач.",
        "warnings": [],
    }
    if check.account_guard_status != "ok" or not check.persistence_confirmed:
        result["warnings"].append("Account Guard or persistence check failed before fill.")
        write_report(result)
        return result
    specs = field_specs(values)
    remaining = {item["name"] for item in specs}
    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=DEFAULT_DRAFT_URL,
        keep_open=True,
        background=background,
        no_focus=background,
        minimized=background,
    ) as session:
        for step in range(1, 5):
            session.page.wait_for_timeout(1000)
            diag = session.refresh_diagnostics()
            result["foreground_policy"] = diag.foreground_policy
            result["brought_to_front_count"] = diag.brought_to_front_count
            result["steps_visited"].append({"step": step, "url": diag.current_url, "title": diag.page_title})
            if diag.account_guard_status != "ok" or PHONE_VERIFICATION_RE.search(session.visible_text()):
                result["warnings"].append("Guard or phone verification stopped full-fill.")
                break
            if step == 1:
                changed_category = fill_category(session.page, values)
                if changed_category:
                    result["fields_filled"].extend([f"category:{item}" for item in changed_category])
                result["cover_uploaded"] = upload_cover(session.page, selected_cover_path())
                current_specific = fill_current_kwork_specific_fields(session.page, values)
                result["fields_filled"].extend(current_specific)
            visible_specs = [item for item in specs if item["name"] in remaining]
            filled = fill_fields(session.page, visible_specs)
            result["fields_found"].extend(filled.get("fieldsFound", []))
            result["fields_filled"].extend(filled.get("fieldsFilled", []))
            for name in filled.get("fieldsFilled", []):
                remaining.discard(name)
            final_buttons = session.find_blocked_buttons()
            if final_buttons:
                result["final_buttons_blocked"].extend(item for item in final_buttons if item not in result["final_buttons_blocked"])
            label = click_allowed_next(session.page)
            if label:
                result["allowed_navigation_clicked"].append(label)
                session.page.wait_for_timeout(1800)
            else:
                break
        result["fields_missing"] = sorted(remaining)
        snapshot_dom(session.page)
        shot = session.screenshot("kwork-full-fill-cdp")
        result["screenshot"] = shot
        result["dom_snapshot"] = rel(DOM_SNAPSHOT)
    write_report(result)
    return result


def write_report(result: dict[str, Any]) -> None:
    lines = [
        "# Kwork Full Fill CDP Report",
        "",
        f"- browser_mode: `{result['browser_mode']}`",
        f"- steps_visited: `{len(result['steps_visited'])}`",
        f"- fields_found: `{', '.join(dict.fromkeys(result['fields_found'])) or 'none'}`",
        f"- fields_filled: `{', '.join(dict.fromkeys(result['fields_filled'])) or 'none'}`",
        f"- fields_missing: `{', '.join(result['fields_missing']) or 'none'}`",
        f"- allowed_navigation_clicked: `{', '.join(result['allowed_navigation_clicked']) or 'none'}`",
        f"- final_buttons_blocked: `{', '.join(result['final_buttons_blocked']) or 'none'}`",
        f"- cover_uploaded: `{str(result['cover_uploaded']).lower()}`",
        f"- foreground_policy: `{result['foreground_policy']}`",
        f"- background_mode: `{str(result['background_mode']).lower()}`",
        f"- brought_to_front_count: `{result['brought_to_front_count']}`",
        f"- dom_snapshot: `{result.get('dom_snapshot', 'none')}`",
        f"- screenshot: `{result.get('screenshot', 'none')}`",
        f"- user_next_step: `{result['user_next_step']}`",
        "",
        "## Steps",
        *(f"- step {item['step']}: `{item['url']}` | {item['title']}" for item in result["steps_visited"]),
        "",
        "## Warnings",
        *(f"- {item}" for item in result["warnings"]),
        "",
        "## Safety",
        "- No save/moderation/publish/send/proposal/order/phone/withdrawal/delete/final buttons clicked.",
    ]
    write_text(FULL_FILL_REPORT, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    result = run(args.background)
    print(FULL_FILL_REPORT)
    print(f"steps_visited={len(result['steps_visited'])}")
    print(f"fields_filled={', '.join(dict.fromkeys(result['fields_filled'])) or 'none'}")
    print(f"fields_missing={', '.join(result['fields_missing']) or 'none'}")
    print(f"final_buttons_blocked={', '.join(result['final_buttons_blocked']) or 'none'}")
    print(f"foreground_policy={result['foreground_policy']}")
    print(f"brought_to_front_count={result['brought_to_front_count']}")


if __name__ == "__main__":
    main()
