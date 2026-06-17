#!/usr/bin/env python3
"""Resolve Kwork subcategory with guarded Windows CDP.

The script may click only category/subcategory dropdown controls and matching
subcategory options. It never saves, publishes, submits to moderation, or sends
anything.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_category_resolver import score_subcategory
from kwork_studio_common import SUBCATEGORY_RESOLVER_REPORT, ensure_studio_dirs, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, run_check_zerroone


SEARCH_ATTEMPTS = ["бот", "Telegram", "чат", "скрипт", "автоматизация", "разработка"]
PREFERRED_MANUAL = ["Боты", "Чат-боты", "Telegram-боты", "Скрипты", "Автоматизация"]
BAD_OPTION_RE = re.compile(r"политика|персональн|обработк[аи]\s+пд|пользовательск|помощь|баланс|заказы|кворки", re.I)


@dataclass
class OptionCandidate:
    label: str
    score: float
    source: str
    index: int


def collect_state(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const selects = Array.from(document.querySelectorAll('select')).map((select, index) => ({
            index,
            id: select.id || '',
            name: select.name || '',
            className: String(select.className || ''),
            value: select.value || '',
            visible: visible(select),
            selectedText: norm(Array.from(select.selectedOptions || []).map((item) => item.textContent || '').join(' ')),
            options: Array.from(select.options || []).map((option, optionIndex) => ({
              optionIndex,
              value: option.value || '',
              text: norm(option.textContent || ''),
              selected: option.selected
            })).filter((item) => item.text && !/^выберите/i.test(item.text))
          }));
          const widgets = Array.from(document.querySelectorAll('.chosen-container, .select2, [role="combobox"], [aria-haspopup="listbox"], .kwork-save-step__field, .field')).map((el, index) => ({
            index,
            tag: el.tagName,
            className: String(el.className || '').slice(0, 120),
            text: norm(el.innerText || el.textContent || '').slice(0, 220),
            visible: visible(el)
          })).filter((item) => item.visible);
          const visibleOptions = Array.from(document.querySelectorAll('[role="option"], .chosen-results li, .select2-results__option, .ui-menu-item, .dropdown-menu li'))
            .filter(visible)
            .map((el, index) => ({index, text: norm(el.innerText || el.textContent || ''), tag: el.tagName, className: String(el.className || '').slice(0, 100), source: 'dropdown'}))
            .filter((item) => item.text && item.text.length <= 140);
          return {
            pageUrl: location.href,
            bodyText: norm(document.body ? document.body.innerText : '').slice(0, 5000),
            selects,
            widgets,
            visibleOptions
          };
        }"""
    )


def ensure_parent_category(page) -> list[str]:
    return page.evaluate(
        """() => {
          const changed = [];
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const parent = document.querySelector('select.js-category_parent')
            || Array.from(document.querySelectorAll('select')).find((select) => {
              const joined = ((select.name || '') + ' ' + String(select.className || '')).toLowerCase();
              return joined.includes('category_parent') || Array.from(select.options || []).some((option) => norm(option.textContent) === 'Разработка и IT');
            });
          if (!parent) return changed;
          const option = Array.from(parent.options || []).find((item) => norm(item.textContent) === 'Разработка и IT');
          if (!option) return changed;
          if (parent.value !== option.value) {
            parent.value = option.value;
            parent.dispatchEvent(new Event('input', {bubbles: true}));
            parent.dispatchEvent(new Event('change', {bubbles: true}));
            parent.dispatchEvent(new CustomEvent('changed', {bubbles: true}));
            if (window.jQuery) window.jQuery(parent).trigger('chosen:updated').trigger('change');
            changed.push('category:Разработка и IT');
          } else {
            changed.push('category_already:Разработка и IT');
          }
          return changed;
        }"""
    )


def category_current_value(state: dict[str, Any]) -> str:
    for select in state.get("selects", []):
        joined = f"{select.get('name', '')} {select.get('className', '')}".lower()
        if "category_parent" in joined or "js-category_parent" in joined:
            return select.get("selectedText") or select.get("value") or "unknown"
    text = state.get("bodyText", "")
    return "Разработка и IT" if "Разработка и IT" in text else "unknown"


def subcategory_field_found(state: dict[str, Any]) -> bool:
    for select in state.get("selects", []):
        joined = f"{select.get('name', '')} {select.get('className', '')}".lower()
        if "category_id" in joined or "category_sub" in joined or "subcategory" in joined:
            return True
    return any("рубри" in item.get("text", "").lower() or "подкат" in item.get("text", "").lower() for item in state.get("widgets", []))


def option_candidates(state: dict[str, Any]) -> list[OptionCandidate]:
    items: list[OptionCandidate] = []
    for select in state.get("selects", []):
        joined = f"{select.get('name', '')} {select.get('className', '')}".lower()
        is_sub = "category_id" in joined or "category_sub" in joined or "subcategory" in joined
        if not is_sub:
            continue
        for option in select.get("options", []):
            score = score_subcategory(option.get("text", ""))
            if score:
                items.append(OptionCandidate(option["text"], score, "select", int(option.get("optionIndex", 0))))
    for item in state.get("visibleOptions", []):
        text = item.get("text", "")
        if BAD_OPTION_RE.search(text):
            continue
        if item.get("source") == "generic_link":
            continue
        score = score_subcategory(text)
        if score:
            items.append(OptionCandidate(text, score, item.get("source", "visible_option"), int(item.get("index", 0))))
    return sorted({(item.label, item.source): item for item in items}.values(), key=lambda item: (-item.score, item.label))[:8]


def open_dropdown_and_search(page) -> dict[str, Any]:
    return page.evaluate(
        """async ({queries}) => {
          const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const events = [];
          const childSelect = Array.from(document.querySelectorAll('select')).find((select) => {
            const joined = ((select.name || '') + ' ' + (select.id || '') + ' ' + String(select.className || '')).toLowerCase();
            return joined.includes('category_id') || joined.includes('category_sub') || joined.includes('subcategory');
          });
          const clickNear = (el, label) => {
            if (!el) return false;
            try {
              el.scrollIntoView({block: 'center'});
              el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
              el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
              el.click();
              events.push(label);
              return true;
            } catch (_) { return false; }
          };
          if (childSelect) {
            const wrapper = childSelect.nextElementSibling || childSelect.parentElement?.querySelector?.('.chosen-container, .select2, [role="combobox"]');
            clickNear(wrapper || childSelect, 'clicked_subcategory_widget');
          }
          for (const widget of Array.from(document.querySelectorAll('.chosen-container, .select2, [role="combobox"], [aria-haspopup="listbox"]')).filter(visible)) {
            const text = norm(widget.innerText || widget.textContent || '');
            if (/выберите|подкат|рубри|катег/i.test(text) || !text) clickNear(widget, 'clicked_visible_dropdown');
          }
          await sleep(1200);
          const attempts = [];
          for (const query of queries) {
            const search = Array.from(document.querySelectorAll('input[type="search"], .chosen-search input, .select2-search__field, input'))
              .filter(visible)
              .find((input) => !/username|password|email|phone/i.test((input.name || '') + ' ' + (input.id || '') + ' ' + (input.placeholder || '')));
            if (!search) {
              attempts.push({query, result: 'search_input_not_found'});
              continue;
            }
            search.focus();
            search.value = query;
            search.dispatchEvent(new InputEvent('input', {bubbles: true, data: query, inputType: 'insertText'}));
            search.dispatchEvent(new Event('change', {bubbles: true}));
            search.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true, key: query.slice(-1) || 'т'}));
            attempts.push({query, result: 'typed'});
            await sleep(800);
            const visibleOptions = Array.from(document.querySelectorAll('[role="option"], .chosen-results li, .select2-results__option, .ui-menu-item, .dropdown-menu li'))
              .filter(visible)
              .map((el) => norm(el.innerText || el.textContent || ''))
              .filter(Boolean)
              .slice(0, 20);
            if (visibleOptions.length) {
              attempts[attempts.length - 1].visibleOptions = visibleOptions;
              break;
            }
          }
          return {events, attempts};
        }""",
        {"queries": SEARCH_ATTEMPTS},
    )


def select_candidate(page, candidate: OptionCandidate) -> list[str]:
    return page.evaluate(
        """({label}) => {
          const clicked = [];
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const childSelect = Array.from(document.querySelectorAll('select')).find((select) => {
            const joined = ((select.name || '') + ' ' + String(select.className || '')).toLowerCase();
            return joined.includes('category_id') || joined.includes('category_sub') || joined.includes('subcategory');
          });
          if (childSelect) {
            const option = Array.from(childSelect.options || []).find((item) => norm(item.textContent) === label)
              || Array.from(childSelect.options || []).find((item) => norm(item.textContent).toLowerCase().includes(label.toLowerCase()));
            if (option) {
              childSelect.value = option.value;
              childSelect.dispatchEvent(new Event('input', {bubbles: true}));
              childSelect.dispatchEvent(new Event('change', {bubbles: true}));
              if (window.jQuery) window.jQuery(childSelect).trigger('chosen:updated').trigger('change');
              clicked.push('select:' + label);
              return clicked;
            }
          }
          const optionEl = Array.from(document.querySelectorAll('[role="option"], .chosen-results li, .select2-results__option, .ui-menu-item, .dropdown-menu li'))
            .filter(visible)
            .find((el) => norm(el.innerText || el.textContent || '') === label)
            || Array.from(document.querySelectorAll('[role="option"], .chosen-results li, .select2-results__option, .ui-menu-item, .dropdown-menu li'))
              .filter(visible)
              .find((el) => norm(el.innerText || el.textContent || '').toLowerCase().includes(label.toLowerCase()));
          if (optionEl) {
            optionEl.click();
            clicked.push('visible_option:' + label);
          }
          return clicked;
        }""",
        {"label": candidate.label},
    )


def run() -> dict[str, Any]:
    ensure_studio_dirs()
    check = run_check_zerroone(restart_check=True)
    result: dict[str, Any] = {
        "category_current_value": "unknown",
        "subcategory_field_found": False,
        "dropdown_opened": False,
        "search_attempts": [],
        "visible_options": [],
        "selected_subcategory": "none",
        "confidence_score": 0.0,
        "clicked_elements": [],
        "final_buttons_blocked": [],
        "verdict": "NOT_RUN",
        "user_next_step": "",
        "warnings": [],
        "screenshot": "",
    }
    if check.account_guard_status != "ok" or not check.persistence_confirmed:
        result["verdict"] = "BLOCKED_BY_ACCOUNT_GUARD"
        result["warnings"].append("Account guard or persistence check failed.")
        write_report(result)
        return result

    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=DEFAULT_DRAFT_URL,
        keep_open=True,
        background=True,
        no_focus=True,
        minimized=True,
    ) as session:
        diag = session.refresh_diagnostics()
        if diag.account_guard_status != "ok" or PHONE_VERIFICATION_RE.search(session.visible_text()):
            result["verdict"] = "BLOCKED_BY_GUARD_OR_PHONE"
            result["warnings"].append("Guard or phone verification stopped subcategory resolver.")
        else:
            result["clicked_elements"].extend(ensure_parent_category(session.page))
            session.page.wait_for_timeout(2200)
            state = collect_state(session.page)
            result["category_current_value"] = category_current_value(state)
            result["subcategory_field_found"] = subcategory_field_found(state)
            before = option_candidates(state)
            if not before:
                search_result = open_dropdown_and_search(session.page)
                result["dropdown_opened"] = bool(search_result.get("events"))
                result["search_attempts"] = search_result.get("attempts", [])
                session.page.wait_for_timeout(1200)
                state = collect_state(session.page)
            candidates = option_candidates(state)
            result["visible_options"] = [item.__dict__ for item in candidates]
            best = candidates[0] if candidates else None
            if best:
                result["selected_subcategory"] = best.label
                result["confidence_score"] = round(best.score, 2)
            if best and best.score >= 0.65:
                result["clicked_elements"] = select_candidate(session.page, best)
                if result["clicked_elements"]:
                    result["verdict"] = "SELECTED"
                    result["user_next_step"] = "Проверь выбранную подкатегорию глазами. Сохранение/модерация только вручную."
                else:
                    result["verdict"] = "NEEDS_MANUAL_SUBCATEGORY_REVIEW"
                    result["user_next_step"] = manual_step()
            else:
                result["verdict"] = "NEEDS_MANUAL_SUBCATEGORY_REVIEW"
                result["user_next_step"] = manual_step()
            result["final_buttons_blocked"] = session.find_blocked_buttons()
        result["screenshot"] = session.screenshot("kwork-subcategory-resolver")
    write_report(result)
    return result


def manual_step() -> str:
    return "Руками выбери ближайшее: " + " / ".join(PREFERRED_MANUAL) + ". Не нажимай сохранение/модерацию до визуальной проверки."


def write_report(result: dict[str, Any]) -> None:
    lines = [
        "# Kwork Subcategory Resolver Report",
        "",
        f"- category_current_value: `{result['category_current_value']}`",
        f"- subcategory_field_found: `{str(result['subcategory_field_found']).lower()}`",
        f"- dropdown_opened: `{str(result['dropdown_opened']).lower()}`",
        f"- selected_subcategory: `{result['selected_subcategory']}`",
        f"- confidence_score: `{result['confidence_score']}`",
        f"- clicked_elements: `{', '.join(result['clicked_elements']) or 'none'}`",
        f"- final_buttons_blocked: `{', '.join(result['final_buttons_blocked']) or 'none'}`",
        f"- verdict: `{result['verdict']}`",
        f"- user_next_step: `{result['user_next_step']}`",
        f"- screenshot: `{result.get('screenshot', '')}`",
        "",
        "## Search Attempts",
        "```json",
        json.dumps(result["search_attempts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Visible Options",
        "```json",
        json.dumps(result["visible_options"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Warnings",
        *(f"- {item}" for item in result["warnings"]),
        "",
        "## Safety",
        "- Only subcategory controls/options are touched.",
        "- No save/moderation/publish/send/proposal/order/phone/withdrawal/delete/final buttons clicked.",
    ]
    write_text(SUBCATEGORY_RESOLVER_REPORT, "\n".join(lines))


def main() -> None:
    result = run()
    print(SUBCATEGORY_RESOLVER_REPORT)
    print(f"subcategory_field_found={str(result['subcategory_field_found']).lower()}")
    print(f"selected_subcategory={result['selected_subcategory']}")
    print(f"confidence_score={result['confidence_score']}")
    print(f"verdict={result['verdict']}")


if __name__ == "__main__":
    main()
