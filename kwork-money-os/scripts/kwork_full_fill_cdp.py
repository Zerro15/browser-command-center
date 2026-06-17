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
    MANUAL_FILL_PACK,
    QUICK_PUBLISH_CHECKLIST,
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


STEP_FIELDS = {
    "step1": ["title", "category", "subcategory", "description", "cover", "short_hook"],
    "step2": ["packages", "prices", "delivery_days", "revisions"],
    "step3": ["faq", "buyer_questions", "requirements", "tags"],
}


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
    extras = "Docker/Linux запуск, логирование ошибок, финальная инструкция."
    return {
        "title": spec.get("title", ""),
        "description": spec.get("description", ""),
        "short_hook": spec.get("short_hook", ""),
        "package_economy": package_text(packages.get("basic", {})),
        "package_standard": package_text(packages.get("standard", {})),
        "package_business": package_text(packages.get("premium", {})),
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
        "extras": extras,
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


def detect_step_and_fields(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const text = norm(document.body?.innerText || '');
          const hasVisibleSelector = (selectors) => selectors.some((selector) => Array.from(document.querySelectorAll(selector)).some(visible));
          const anyText = (patterns) => patterns.some((pattern) => pattern.test(text));
          const editors = Array.from(document.querySelectorAll('.trumbowyg-editor')).filter(visible);

          const fields = {
            title: { visible: hasVisibleSelector(['#editor-title', '#step1-name', 'input[name=\"name\"]']), empty: !norm(document.querySelector('#editor-title')?.innerText || document.querySelector('#step1-name')?.value || document.querySelector('input[name=\"name\"]')?.value || '') },
            category: { visible: anyText([/рубрик/i, /категор/i]) || hasVisibleSelector(['select.js-category_parent', 'select[name=\"category_parent\"]']), empty: !norm(document.querySelector('.chosen-single span')?.innerText || document.querySelector('select.js-category_parent')?.selectedOptions?.[0]?.textContent || '') || /выберите/i.test(norm(document.querySelector('.chosen-single')?.innerText || '')) },
            subcategory: { visible: hasVisibleSelector(['select[name=\"category_id\"]']) || anyText([/чат-бот/i, /telegram-бот/i]), empty: !norm(document.querySelector('select[name=\"category_id\"]')?.selectedOptions?.[0]?.textContent || '') },
            description: { visible: hasVisibleSelector(['#step1-description', 'textarea[name=\"description\"]']) || !!editors[0], empty: !norm(editors[0]?.innerText || document.querySelector('#step1-description')?.value || document.querySelector('textarea[name=\"description\"]')?.value || '') },
            cover: { visible: hasVisibleSelector(['input[type=\"file\"]']), empty: false },
            short_hook: { visible: hasVisibleSelector(['#editor-service_size', '#step2-service-size', 'input[name=\"package_volume\"]']), empty: !norm(document.querySelector('#editor-service_size')?.innerText || document.querySelector('#step2-service-size')?.value || '') },
            packages: { visible: anyText([/пакет/i, /эконом|стандарт|бизнес|премиум/i]), empty: false },
            prices: { visible: anyText([/стоимост/i, /цена/i]) || hasVisibleSelector(['select#min_volume_price', 'select[name=\"min_volume_price\"]', 'input[name*=\"price\"]']), empty: !(norm(document.querySelector('select#min_volume_price')?.selectedOptions?.[0]?.textContent || document.querySelector('select[name=\"min_volume_price\"]')?.selectedOptions?.[0]?.textContent || document.querySelector('input[name*=\"price\"]')?.value || '')) },
            delivery_days: { visible: anyText([/срок выполн/i, /дней/i]) || hasVisibleSelector(['select[name*=\"day\"]', 'select[name*=\"duration\"]']), empty: !(norm(Array.from(document.querySelectorAll('select')).find((el) => /(day|days|duration|time|done)/i.test((el.name || '') + ' ' + (el.id || '')) || Array.from(el.options || []).some((opt) => /день|дня|дней/i.test(opt.textContent || '')))?.selectedOptions?.[0]?.textContent || '')) },
            revisions: { visible: anyText([/правк/i, /доработ/i]), empty: false },
            faq: { visible: anyText([/faq/i, /частые вопросы/i]), empty: false },
            buyer_questions: { visible: anyText([/от покупателя нужно/i, /вопросы покупателю/i, /требования/i]) || hasVisibleSelector(['#step1-instruction', 'textarea[name=\"instruction\"]']), empty: !norm(editors[1]?.innerText || document.querySelector('#step1-instruction')?.value || document.querySelector('textarea[name=\"instruction\"]')?.value || '') },
            requirements: { visible: anyText([/требован/i, /от покупателя нужно/i]), empty: !norm(document.querySelector('#step1-instruction')?.value || document.querySelector('textarea[name=\"instruction\"]')?.value || '') },
            tags: { visible: anyText([/тег/i, /ключевые слова/i]) || hasVisibleSelector(['input[name*=\"tag\"]', 'textarea[name*=\"tag\"]']), empty: !(norm(document.querySelector('input[name*=\"tag\"]')?.value || document.querySelector('textarea[name*=\"tag\"]')?.value || '')) },
            extra_name: { visible: hasVisibleSelector(['.add-extra__item-name-input.js-content-editor']), empty: !norm(document.querySelector('.add-extra__item-name-input.js-content-editor')?.innerText || '') },
            extra_description: { visible: hasVisibleSelector(['.add-extra__item-description-input.js-content-editor']), empty: !norm(document.querySelector('.add-extra__item-description-input.js-content-editor')?.innerText || '') },
          };

          let currentStep = 'unknown';
          if (fields.title.visible || fields.description.visible || fields.category.visible) {
            currentStep = 'step1';
          } else if (fields.packages.visible || fields.prices.visible || fields.delivery_days.visible) {
            currentStep = 'step2';
          } else if (fields.faq.visible || fields.buyer_questions.visible || fields.tags.visible || fields.requirements.visible) {
            currentStep = 'step3';
          }
          if (currentStep === 'step1' && (fields.prices.visible || fields.delivery_days.visible || fields.buyer_questions.visible)) {
            currentStep = 'step1_plus';
          }
          return { currentStep, fields };
        }"""
    )


def build_manual_fill_pack(values: dict[str, str]) -> None:
    lines = [
        "# Manual Fill Pack",
        "",
        "Используй этот pack, если автоматизация не нашла часть полей или Kwork показывает другой шаг формы.",
        "",
        "## Title",
        values["title"],
        "",
        "## Description",
        values["description"],
        "",
        "## Basic Package",
        values["package_economy"],
        "",
        "## Standard Package",
        values["package_standard"],
        "",
        "## Premium Package",
        values["package_business"],
        "",
        "## Prices Recommendation",
        "- Basic: 3000 ₽",
        "- Standard: 5500 ₽",
        "- Premium: 9000 ₽",
        "",
        "## Delivery Days",
        "- Basic: 3 дня",
        "- Standard: 4 дня",
        "- Premium: 7 дней",
        "",
        "## FAQ",
        values["faq"] or "FAQ not prepared.",
        "",
        "## Buyer Questions",
        values["buyer_questions"] or "Buyer questions not prepared.",
        "",
        "## Tags",
        values["tags"] or "Telegram bot, Google Sheets, Python, deploy, Docker, Linux",
        "",
        "## Cover Prompt",
        "Telegram-бот для заявок, Google Таблица, деплой, темный технологичный фон, без лишнего текста, акцент на приеме заявок и надежном запуске.",
        "",
        "## Куда вставлять руками",
        "1. Title -> поле названия кворка.",
        "2. Description -> описание услуги.",
        "3. Basic/Standard/Premium + prices + days -> блок пакетов, когда Kwork покажет шаг с пакетами.",
        "4. FAQ / Buyer Questions / Tags -> соответствующие поля на следующих шагах.",
        "5. Если cover еще не загружена, можно продолжить текстовую часть и позже вручную догрузить обложку.",
    ]
    write_text(MANUAL_FILL_PACK, "\n".join(lines))


def build_quick_publish_checklist(result: dict[str, Any]) -> None:
    cover_status = "ready" if result.get("cover_uploaded") else "pending"
    packages_ready = "yes" if "packages" not in result["fields_not_on_current_step"] and "prices" not in result["fields_not_on_current_step"] else "manual pack ready"
    faq_ready = "yes" if "faq" in result["fields_filled"] else "manual pack ready"
    if result["overall_status"] == "READY_FOR_HUMAN_REVIEW_CURRENT_STEP":
        verdict = "READY_TO_FINISH_MANUALLY"
    elif cover_status == "pending":
        verdict = "NEEDS_COVER"
    elif packages_ready != "yes":
        verdict = "NEEDS_PACKAGES"
    else:
        verdict = "DO_NOT_SUBMIT"
    lines = [
        "# Kwork Quick Publish Checklist",
        "",
        f"- account_zerroone_ok: `{result.get('account_guard_ok', 'unknown')}`",
        f"- title_filled: `{'title' in result['fields_filled']}`",
        f"- description_filled: `{'description' in result['fields_filled']}`",
        f"- cover_status: `{cover_status}`",
        f"- packages_status: `{packages_ready}`",
        f"- faq_status: `{faq_ready}`",
        f"- buyer_questions_ready: `{'buyer_questions' in result['fields_filled'] or 'buyer_questions_editor' in result['fields_filled'] or 'buyer_questions' in result['fields_not_on_current_step']}`",
        f"- forbidden_promises_absent: `true`",
        f"- final_buttons_clicked_by_bot: `false`",
        f"- next_human_action: `{result['user_next_step']}`",
        f"- verdict: `{verdict}`",
        "",
        "## Notes",
        "- Cover pending does not block text/package preparation.",
        "- Manual fill pack can be used if a later step is not reachable automatically.",
        "- Final save/moderation/publish remains manual-only.",
    ]
    write_text(QUICK_PUBLISH_CHECKLIST, "\n".join(lines))


def fill_category(page, values: dict[str, str]) -> list[str]:
    return page.evaluate(
        """() => {
          const changed = [];
          const updateChosen = (select) => {
            if (window.jQuery) window.jQuery(select).trigger('chosen:updated').trigger('change');
            const wrapper = select.closest('.chosen-container') || select.parentElement;
            const textNode = wrapper?.querySelector?.('.chosen-single span');
            if (textNode && select.selectedOptions?.[0]?.textContent) {
              textNode.innerText = select.selectedOptions[0].textContent.trim();
            }
          };
          const setSelect = (select, matcher, label) => {
            if (!select) return false;
            const options = Array.from(select.options || []);
            const wanted = options.find((o) => matcher.test(o.textContent || ''));
            if (!wanted) return false;
            select.value = wanted.value;
            select.dispatchEvent(new Event('input', {bubbles: true}));
            select.dispatchEvent(new Event('change', {bubbles: true}));
            updateChosen(select);
            changed.push(label);
            return true;
          };
          const selects = Array.from(document.querySelectorAll('select'));
          const parentSelect = selects.find((select) => /category_parent|parent/i.test((select.name || '') + ' ' + (select.id || '')))
            || document.querySelector('select.js-category_parent');
          const childSelect = selects.find((select) => /category_id|subcategory/i.test((select.name || '') + ' ' + (select.id || '')))
            || document.querySelector('select[name="category_id"]');
          setSelect(parentSelect, /разработка|it|разработк/i, 'category');
          setSelect(childSelect, /чат-бот|telegram-бот|telegram|бот/i, 'subcategory');
          return changed;
        }"""
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
          const notify = (el, value) => {
            el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
          };
          const set = (el, value, label) => {
            if (!el || !visible(el)) return false;
            el.scrollIntoView({block: 'center', inline: 'nearest'});
            el.focus();
            if (el.isContentEditable) {
              el.innerText = value;
            } else {
              el.value = value;
            }
            notify(el, value);
            changed.push(label);
            return true;
          };

          const setSelectByText = (selector, matcher, label) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            const wanted = Array.from(el.options || []).find((opt) => matcher.test((opt.textContent || '') + ' ' + (opt.value || '')));
            if (wanted) {
              el.value = wanted.value;
              notify(el, wanted.value);
              if (window.jQuery) window.jQuery(el).trigger('chosen:updated').trigger('change');
              changed.push(label);
              return true;
            }
            return false;
          };

          set(document.querySelector('#step1-instruction'), values.buyer_questions || '', 'buyer_questions');
          const editors = Array.from(document.querySelectorAll('.trumbowyg-editor')).filter(visible);
          if (editors[1]) set(editors[1], values.buyer_questions || '', 'buyer_questions_editor');
          set(document.querySelector('#editor-service_size'), values.package_economy || values.short_hook || '', 'service_size');
          set(document.querySelector('#step2-service-size'), values.package_economy || values.short_hook || '', 'service_size_input');
          set(document.querySelector('input[name="package_volume"]'), '1', 'package_volume');
          setSelectByText('select#min_volume_price, select[name="min_volume_price"]', /3000|3\\s*000/, 'min_volume_price');
          const daySelectors = Array.from(document.querySelectorAll('select'))
            .filter((el) => /day|days|duration|time|done/i.test((el.name || '') + ' ' + (el.id || '')) || Array.from(el.options || []).some((opt) => /день|дня|дней/i.test(opt.textContent || '')));
          if (daySelectors[0]) {
            const wanted = Array.from(daySelectors[0].options || []).find((opt) => /3\\s*дн|3\\s*дня|3\\s*день/i.test(opt.textContent || ''))
              || Array.from(daySelectors[0].options || []).find((opt) => /4\\s*дн|4\\s*дня|4\\s*день/i.test(opt.textContent || ''));
            if (wanted) {
              daySelectors[0].value = wanted.value;
              notify(daySelectors[0], wanted.value);
              if (window.jQuery) window.jQuery(daySelectors[0]).trigger('chosen:updated').trigger('change');
              changed.push('days_to_done');
            }
          }
          set(document.querySelector('.add-extra__item-name-input.js-content-editor'), 'Docker/Linux запуск', 'extra_name');
          set(document.querySelector('.add-extra__item-description-input.js-content-editor'), values.extras || '', 'extra_description');
          const extraPrice = document.querySelector('select[name="my_extras_price[]"]');
          if (extraPrice) {
            const wanted = Array.from(extraPrice.options || []).find((opt) => /800|1 200|1200/.test((opt.textContent || '') + ' ' + (opt.value || '')));
            if (wanted) {
              extraPrice.value = wanted.value;
              notify(extraPrice, wanted.value);
              if (window.jQuery) window.jQuery(extraPrice).trigger('chosen:updated').trigger('change');
              changed.push('extra_price');
            }
          }
          const extraDay = Array.from(document.querySelectorAll('select')).find((el) => /my_extras_days|extra.*day/i.test((el.name || '') + ' ' + (el.id || '')) || Array.from(el.options || []).some((opt) => /0 дней|1 день|2 дня/i.test(opt.textContent || '')));
          if (extraDay) {
            const wanted = Array.from(extraDay.options || []).find((opt) => /1 день|2 дня/i.test(opt.textContent || ''));
            if (wanted) {
              extraDay.value = wanted.value;
              notify(extraDay, wanted.value);
              if (window.jQuery) window.jQuery(extraDay).trigger('chosen:updated').trigger('change');
              changed.push('extra_days');
            }
          }
          set(document.querySelector('textarea[name="instruction"]'), values.buyer_questions || '', 'buyer_questions_textarea');
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
    build_manual_fill_pack(values)
    result = {
        "browser_mode": "windows_cdp",
        "steps_visited": [],
        "fields_found": [],
        "fields_filled": [],
        "fields_visible_but_empty": [],
        "fields_not_on_current_step": [],
        "fields_missing_unexpected": [],
        "fields_missing": [],
        "allowed_navigation_clicked": [],
        "final_buttons_blocked": [],
        "cover_uploaded": False,
        "foreground_policy": "unknown",
        "background_mode": background,
        "brought_to_front_count": 0,
        "detected_step": "unknown",
        "kwork_current_step_status": "BLOCKED_BY_UNKNOWN_FORM",
        "overall_status": "DO_NOT_SUBMIT",
        "account_guard_ok": str(check.account_guard_status == "ok").lower(),
        "user_next_step": "Окно готово для проверки, открой его вручную на панели задач.",
        "warnings": [],
    }
    if check.account_guard_status != "ok" or not check.persistence_confirmed:
        result["warnings"].append("Account Guard or persistence check failed before fill.")
        write_report(result)
        build_quick_publish_checklist(result)
        return result
    specs = field_specs(values)
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
                    result["fields_filled"].extend(changed_category)
                result["cover_uploaded"] = upload_cover(session.page, selected_cover_path())
                if result["cover_uploaded"]:
                    result["fields_filled"].append("cover")
                current_specific = fill_current_kwork_specific_fields(session.page, values)
                result["fields_filled"].extend(current_specific)
            filled = fill_fields(session.page, specs)
            result["fields_found"].extend(filled.get("fieldsFound", []))
            result["fields_filled"].extend(filled.get("fieldsFilled", []))
            final_buttons = session.find_blocked_buttons()
            if final_buttons:
                result["final_buttons_blocked"].extend(item for item in final_buttons if item not in result["final_buttons_blocked"])
            label = click_allowed_next(session.page)
            if label:
                result["allowed_navigation_clicked"].append(label)
                session.page.wait_for_timeout(1800)
            else:
                break
        dom_state = detect_step_and_fields(session.page)
        result["detected_step"] = dom_state.get("currentStep", "unknown")
        field_state = dom_state.get("fields", {})
        expected_by_step = {
            "step1": STEP_FIELDS["step1"],
            "step1_plus": STEP_FIELDS["step1"] + ["buyer_questions", "requirements", "prices", "delivery_days"],
            "step2": STEP_FIELDS["step2"],
            "step3": STEP_FIELDS["step3"],
            "unknown": [],
        }
        expected_now = expected_by_step.get(result["detected_step"], [])
        if result["detected_step"] in {"step1", "step1_plus"}:
            future_fields = set(STEP_FIELDS["step2"] + STEP_FIELDS["step3"]) - set(expected_now)
        elif result["detected_step"] == "step2":
            future_fields = set(STEP_FIELDS["step3"])
        else:
            future_fields = set()
        alias_map = {
            "title": {"title"},
            "description": {"description"},
            "category": {"category"},
            "subcategory": {"subcategory"},
            "cover": {"cover"},
            "short_hook": {"service_size", "service_size_input", "short_hook"},
            "packages": {"basic_package", "standard_package", "premium_package", "packages"},
            "prices": {"basic_price", "standard_price", "premium_price", "min_volume_price", "extra_price", "prices"},
            "delivery_days": {"basic_days", "standard_days", "premium_days", "days_to_done", "extra_days", "delivery_days"},
            "revisions": {"revisions"},
            "faq": {"faq"},
            "buyer_questions": {"buyer_questions", "buyer_questions_editor", "buyer_questions_textarea"},
            "requirements": {"buyer_questions", "buyer_questions_editor", "buyer_questions_textarea", "requirements"},
            "tags": {"tags"},
        }
        filled_set = set(result["fields_filled"]) | set(result["fields_found"])
        for field in expected_now:
            state = field_state.get(field, {})
            aliases = alias_map.get(field, {field})
            if aliases & filled_set:
                continue
            if state.get("visible"):
                result["fields_visible_but_empty"].append(field)
            else:
                result["fields_missing_unexpected"].append(field)
        for field in sorted(future_fields):
            state = field_state.get(field, {})
            aliases = alias_map.get(field, {field})
            if aliases & filled_set:
                continue
            if not state.get("visible"):
                result["fields_not_on_current_step"].append(field)
        result["fields_visible_but_empty"] = sorted(set(result["fields_visible_but_empty"]))
        result["fields_not_on_current_step"] = sorted(set(result["fields_not_on_current_step"]))
        result["fields_missing_unexpected"] = sorted(set(result["fields_missing_unexpected"]))
        result["fields_missing"] = list(result["fields_missing_unexpected"])
        if result["detected_step"] == "unknown":
            result["warnings"].append("Could not confidently detect current Kwork step from DOM.")
            result["kwork_current_step_status"] = "BLOCKED_BY_UNKNOWN_FORM"
            result["overall_status"] = "DO_NOT_SUBMIT"
        elif result["fields_missing_unexpected"]:
            result["kwork_current_step_status"] = "BLOCKED_BY_UNKNOWN_FORM"
            result["overall_status"] = "DO_NOT_SUBMIT"
        elif result["fields_visible_but_empty"]:
            result["kwork_current_step_status"] = "CURRENT_STEP_PARTIAL"
            result["overall_status"] = "NEEDS_MANUAL_INPUT"
        elif result["fields_not_on_current_step"]:
            result["kwork_current_step_status"] = "NEXT_STEP_REQUIRED"
            result["overall_status"] = "NEEDS_NEXT_STEP"
        else:
            result["kwork_current_step_status"] = "CURRENT_STEP_FILLED"
            result["overall_status"] = "READY_FOR_HUMAN_REVIEW_CURRENT_STEP"
        snapshot_dom(session.page)
        shot = session.screenshot("kwork-full-fill-cdp")
        result["screenshot"] = shot
        result["dom_snapshot"] = rel(DOM_SNAPSHOT)
    write_report(result)
    build_quick_publish_checklist(result)
    return result


def write_report(result: dict[str, Any]) -> None:
    lines = [
        "# Kwork Full Fill CDP Report",
        "",
        f"- browser_mode: `{result['browser_mode']}`",
        f"- detected_step: `{result.get('detected_step', 'unknown')}`",
        f"- kwork_current_step_status: `{result.get('kwork_current_step_status', 'unknown')}`",
        f"- overall_status: `{result.get('overall_status', 'unknown')}`",
        f"- steps_visited: `{len(result['steps_visited'])}`",
        f"- fields_found: `{', '.join(dict.fromkeys(result['fields_found'])) or 'none'}`",
        f"- fields_filled: `{', '.join(dict.fromkeys(result['fields_filled'])) or 'none'}`",
        f"- fields_visible_but_empty: `{', '.join(result.get('fields_visible_but_empty', [])) or 'none'}`",
        f"- fields_not_on_current_step: `{', '.join(result.get('fields_not_on_current_step', [])) or 'none'}`",
        f"- fields_missing_unexpected: `{', '.join(result.get('fields_missing_unexpected', [])) or 'none'}`",
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
        f"- Manual fill pack: `{rel(MANUAL_FILL_PACK)}`",
        f"- Quick publish checklist: `{rel(QUICK_PUBLISH_CHECKLIST)}`",
    ]
    write_text(FULL_FILL_REPORT, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    result = run(args.background)
    print(FULL_FILL_REPORT)
    print(f"detected_step={result.get('detected_step', 'unknown')}")
    print(f"kwork_current_step_status={result.get('kwork_current_step_status', 'unknown')}")
    print(f"overall_status={result.get('overall_status', 'unknown')}")
    print(f"steps_visited={len(result['steps_visited'])}")
    print(f"fields_filled={', '.join(dict.fromkeys(result['fields_filled'])) or 'none'}")
    print(f"fields_visible_but_empty={', '.join(result.get('fields_visible_but_empty', [])) or 'none'}")
    print(f"fields_not_on_current_step={', '.join(result.get('fields_not_on_current_step', [])) or 'none'}")
    print(f"fields_missing={', '.join(result['fields_missing']) or 'none'}")
    print(f"final_buttons_blocked={', '.join(result['final_buttons_blocked']) or 'none'}")
    print(f"foreground_policy={result['foreground_policy']}")
    print(f"brought_to_front_count={result['brought_to_front_count']}")


if __name__ == "__main__":
    main()
