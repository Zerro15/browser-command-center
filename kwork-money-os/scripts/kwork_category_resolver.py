#!/usr/bin/env python3
"""Resolve and select Kwork category/subcategory through guarded Windows CDP."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_studio_common import CATEGORY_RESOLVER_REPORT, FINAL_BUTTONS, ensure_studio_dirs, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, run_check_zerroone


CATEGORY_WORDS = ["разработка", "it", "программирование", "сайты"]
SUBCATEGORY_PRIORITIES = [
    ("боты", 1.0),
    ("чат-боты", 1.0),
    ("telegram-боты", 1.0),
    ("telegram", 0.95),
    ("скрипты", 0.78),
    ("автоматизация", 0.76),
    ("веб-разработка", 0.62),
    ("доработка сайта", 0.52),
    ("другое в разработке и it", 0.5),
]


@dataclass
class Candidate:
    label: str
    selector_hint: str
    score: float
    kind: str


def score_category(label: str) -> float:
    lower = label.lower()
    score = 0.0
    if "разработка" in lower and "it" in lower:
        score = 1.0
    elif any(word in lower for word in CATEGORY_WORDS):
        score = 0.75
    return score


def score_subcategory(label: str) -> float:
    lower = label.lower()
    if any(word in lower for word in ["политика", "персональных", "пд", "пользовательское", "обработка пд"]):
        return 0.0
    best = 0.0
    for phrase, score in SUBCATEGORY_PRIORITIES:
        if phrase in lower:
            best = max(best, score)
    if re.search(r"(^|[^а-яёa-z])(?:бот|боты|бота|чат-бот|чатбот)(?:[^а-яёa-z]|$)", lower, re.I):
        best = max(best, 0.9)
    if "api" in lower or "python" in lower:
        best = max(best, 0.65)
    return best


def collect_candidates(page) -> dict[str, Any]:
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
            visible: visible(select),
            options: Array.from(select.options || []).map((option, optionIndex) => ({
              optionIndex,
              value: option.value || '',
              text: norm(option.textContent || ''),
              selected: option.selected
            })).filter((item) => item.text && !/^выберите/i.test(item.text))
          }));
          const dropdownItems = Array.from(document.querySelectorAll('[role="option"], .chosen-results li, .select2-results__option, li, a, button'))
            .filter(visible)
            .map((el, index) => ({index, text: norm(el.innerText || el.textContent || ''), tag: el.tagName, className: String(el.className || '').slice(0, 80)}))
            .filter((item) => item.text && item.text.length <= 120);
          const chosenText = Array.from(document.querySelectorAll('.chosen-single span, .select2-selection__rendered'))
            .filter(visible)
            .map((el) => norm(el.innerText || el.textContent || ''));
          return {selects, dropdownItems, chosenText};
        }"""
    )


def select_best(page, selected_category: Candidate | None, selected_subcategory: Candidate | None) -> list[str]:
    return page.evaluate(
        """({categoryText, subcategoryText}) => {
          const clicked = [];
          const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const setSelect = (select, wantedText, label) => {
            if (!select || !wantedText) return false;
            const option = Array.from(select.options || []).find((item) => normalize(item.textContent) === normalize(wantedText))
              || Array.from(select.options || []).find((item) => normalize(item.textContent).toLowerCase().includes(normalize(wantedText).toLowerCase()));
            if (!option) return false;
            select.value = option.value;
            select.dispatchEvent(new Event('input', {bubbles: true}));
            select.dispatchEvent(new Event('change', {bubbles: true}));
            select.dispatchEvent(new CustomEvent('changed', {bubbles: true}));
            if (window.jQuery) window.jQuery(select).trigger('chosen:updated').trigger('change');
            const container = select.parentElement?.querySelector?.('.chosen-single span');
            if (container) container.innerText = wantedText;
            clicked.push(label + ':' + wantedText);
            return true;
          };
          const selects = Array.from(document.querySelectorAll('select'));
          const parent = selects.find((select) => /category_parent|parent/i.test((select.name || '') + ' ' + (select.id || '')))
            || document.querySelector('select.js-category_parent')
            || selects.find((select) => Array.from(select.options || []).some((option) => (option.textContent || '').trim() === categoryText));
          const child = selects.find((select) => /category_id|subcategory/i.test((select.name || '') + ' ' + (select.id || '')))
            || document.querySelector('select[name="category_id"]')
            || selects.find((select) => select !== parent && Array.from(select.options || []).some((option) => (option.textContent || '').trim() === subcategoryText));
          setSelect(parent, categoryText, 'category');
          setSelect(child, subcategoryText, 'subcategory');
          return clicked;
        }""",
        {
            "categoryText": selected_category.label if selected_category else "",
            "subcategoryText": selected_subcategory.label if selected_subcategory else "",
        },
    )


def run() -> dict[str, Any]:
    ensure_studio_dirs()
    check = run_check_zerroone(restart_check=True)
    result: dict[str, Any] = {
        "category_candidates": [],
        "subcategory_candidates": [],
        "selected_category": "none",
        "selected_subcategory": "none",
        "confidence_score": 0.0,
        "clicked_elements": [],
        "final_buttons_blocked": [],
        "needs_manual_review": True,
        "status": "NOT_RUN",
        "warnings": [],
        "screenshot": "",
    }
    if check.account_guard_status != "ok" or not check.persistence_confirmed:
        result["status"] = "BLOCKED_BY_ACCOUNT_GUARD"
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
            result["status"] = "BLOCKED_BY_GUARD_OR_PHONE"
            result["warnings"].append("Guard or phone verification stopped category resolver.")
        else:
            raw = collect_candidates(session.page)
            categories, subcategories = parse_candidates(raw)
            categories = sorted(categories, key=lambda item: (-item.score, item.label))[:5]
            subcategories = sorted(subcategories, key=lambda item: (-item.score, item.label))[:5]
            if categories and categories[0].score >= 0.65 and not subcategories:
                result["clicked_elements"].extend(select_best(session.page, categories[0], None))
                session.page.wait_for_timeout(1800)
                raw = collect_candidates(session.page)
                more_categories, subcategories = parse_candidates(raw)
                if more_categories:
                    categories = sorted(more_categories, key=lambda item: (-item.score, item.label))[:5]
                subcategories = sorted(subcategories, key=lambda item: (-item.score, item.label))[:5]
            result["category_candidates"] = [candidate.__dict__ for candidate in categories]
            result["subcategory_candidates"] = [candidate.__dict__ for candidate in subcategories]
            selected_category = categories[0] if categories else None
            selected_subcategory = subcategories[0] if subcategories else None
            result["selected_category"] = selected_category.label if selected_category else "none"
            result["selected_subcategory"] = selected_subcategory.label if selected_subcategory else "none"
            confidence = min(selected_category.score if selected_category else 0.0, selected_subcategory.score if selected_subcategory else 0.0)
            result["confidence_score"] = round(confidence, 2)
            if confidence >= 0.65 and selected_category and selected_subcategory:
                for item in select_best(session.page, selected_category, selected_subcategory):
                    if item not in result["clicked_elements"]:
                        result["clicked_elements"].append(item)
                result["needs_manual_review"] = False
                result["status"] = "SELECTED"
                session.page.wait_for_timeout(1200)
            else:
                result["status"] = "NEEDS_MANUAL_CATEGORY_REVIEW"
                result["needs_manual_review"] = True
            result["final_buttons_blocked"] = session.find_blocked_buttons()
        result["screenshot"] = session.screenshot("kwork-category-resolver")
    write_report(result)
    return result


def parse_candidates(raw: dict[str, Any]) -> tuple[list[Candidate], list[Candidate]]:
    categories: list[Candidate] = []
    subcategories: list[Candidate] = []
    for select in raw.get("selects", []):
        hint = f"select#{select.get('id') or select.get('name') or select.get('index')}"
        joined = f"{select.get('id', '')} {select.get('name', '')} {select.get('className', '')}".lower()
        for option in select.get("options", []):
            label = option.get("text", "")
            if "category_parent" in joined or "parent" in joined or "js-category_parent" in joined:
                score = score_category(label)
                if score:
                    categories.append(Candidate(label, hint, score, "category"))
            else:
                score = score_subcategory(label)
                if score:
                    subcategories.append(Candidate(label, hint, score, "subcategory"))
    return categories, subcategories


def write_report(result: dict[str, Any]) -> None:
    lines = [
        "# Kwork Category Resolver Report",
        "",
        f"- status: `{result['status']}`",
        f"- selected_category: `{result['selected_category']}`",
        f"- selected_subcategory: `{result['selected_subcategory']}`",
        f"- confidence_score: `{result['confidence_score']}`",
        f"- clicked_elements: `{', '.join(result['clicked_elements']) or 'none'}`",
        f"- final_buttons_blocked: `{', '.join(result['final_buttons_blocked']) or 'none'}`",
        f"- needs_manual_review: `{str(result['needs_manual_review']).lower()}`",
        f"- screenshot: `{result.get('screenshot', '')}`",
        "",
        "## Category Candidates",
        "```json",
        json.dumps(result["category_candidates"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Subcategory Candidates",
        "```json",
        json.dumps(result["subcategory_candidates"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Warnings",
        *(f"- {item}" for item in result["warnings"]),
        "",
        "## Safety",
        "- Only category/subcategory controls are changed.",
        "- No save/moderation/publish/send/proposal/order/phone/withdrawal/delete/final buttons clicked.",
    ]
    write_text(CATEGORY_RESOLVER_REPORT, "\n".join(lines))


def main() -> None:
    result = run()
    print(CATEGORY_RESOLVER_REPORT)
    print(f"status={result['status']}")
    print(f"selected_category={result['selected_category']}")
    print(f"selected_subcategory={result['selected_subcategory']}")
    print(f"confidence_score={result['confidence_score']}")
    print(f"needs_manual_review={str(result['needs_manual_review']).lower()}")


if __name__ == "__main__":
    main()
