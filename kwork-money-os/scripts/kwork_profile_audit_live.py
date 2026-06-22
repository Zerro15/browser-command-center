#!/usr/bin/env python3
"""Read-only live collector for created Kwork profile kworks via Windows CDP."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from browser_rpa_bridge import PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_profile_audit import score_local_item
from kwork_studio_common import FINAL_BUTTONS, rel, write_json, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL


SNAPSHOT_DIR = DATA / "kwork_profile_audit"
SNAPSHOT_PATH = SNAPSHOT_DIR / "live_kworks_snapshot.json"
REPORT_PATH = REPORTS / "kwork_profile_audit_live_report.md"

STOP_MARKERS = [
    "captcha",
    "капча",
    "подтвердите, что вы не робот",
    "new_phone_verify=1",
    "подтверждение телефона",
    "sms",
    "смс",
    "введите код",
    "войти",
    "регистрация",
    "заблокирован",
    "доступ ограничен",
    "настройте вывод",
]


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def text_has_stop_marker(text: str, url: str) -> str:
    haystack = f"{url}\n{text}".lower()
    if PHONE_VERIFICATION_RE.search(text) or "new_phone_verify=1" in url:
        return "phone_or_sms_required"
    for marker in STOP_MARKERS:
        if marker in haystack:
            if marker in {"войти", "регистрация"} and "manage_kworks" in url:
                continue
            return f"stop_marker:{marker}"
    return ""


def collect_visible_kworks(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """() => {
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const hrefOf = (el) => {
            const link = el?.querySelector?.('a[href]') || (el?.matches?.('a[href]') ? el : null);
            return link ? (link.href || link.getAttribute('href') || '') : '';
          };
          const titleOf = (root) => {
            const candidates = [
              'a[href*="/edit"]',
              'a[href*="/new"]',
              'a[href*="/kwork"]',
              '[class*="title"]',
              'h1', 'h2', 'h3'
            ];
            for (const selector of candidates) {
              const item = root.querySelector?.(selector);
              const text = norm(item?.innerText || item?.textContent || '');
              if (text && text.length >= 5 && text.length <= 180) return text;
            }
            const lines = norm(root.innerText || '').split(/(?<=\\S)\\s{2,}|\\n/).map(norm).filter(Boolean);
            return lines.find((line) => line.length >= 5 && line.length <= 180) || '';
          };
          const roots = Array.from(document.querySelectorAll([
            '[class*="kwork"]',
            '[class*="card"]',
            '[class*="item"]',
            '[class*="row"]',
            'tr',
            'li'
          ].join(','))).filter(visible);
          const seen = new Set();
          const items = [];
          for (const root of roots) {
            const text = norm(root.innerText || root.textContent || '');
            if (text.length < 12) continue;
            const href = hrefOf(root);
            const title = titleOf(root);
            if (!title && !href) continue;
            const key = `${href}|${title}|${text.slice(0, 80)}`;
            if (seen.has(key)) continue;
            seen.add(key);
            const statusMatch = text.match(/(черновик|на модерации|модерац|активн|опубликован|приостанов|пауза|отклон|требует[^\\n]{0,40})/i);
            const priceMatch = text.match(/(\\d[\\d\\s]{2,8})\\s*(₽|руб\\.?)/i);
            const warningMatch = text.match(/(отклон[^\\n]{0,120}|требует[^\\n]{0,120}|модерац[^\\n]{0,120})/i);
            const categoryMatch = text.match(/(Разработка и IT|Дизайн|Тексты|SEO|Маркетинг|Бизнес|Аудио|Видео|Фото|Переводы)/i);
            items.push({
              title,
              status: statusMatch ? statusMatch[1] : 'unknown',
              category: categoryMatch ? categoryMatch[1] : '',
              subcategory: '',
              price: priceMatch ? priceMatch[0] : '',
              cover_present: !!root.querySelector?.('img'),
              url: href,
              visible_warning: warningMatch ? warningMatch[1] : '',
              text: text.slice(0, 2200)
            });
          }
          return items.slice(0, 50);
        }"""
    )


def is_reliable_kwork_item(item: dict[str, Any]) -> bool:
    title = norm(item.get("title")).lower()
    url = norm(item.get("url")).lower()
    status = norm(item.get("status")).lower()
    price = norm(item.get("price"))
    if not title:
        return False
    if not url or url == "unknown":
        return False
    banned_title_markers = [
        "разработка и it",
        "тексты и переводы",
        "seo и трафик",
        "соцсети и маркетинг",
        "обработка звука",
        "аудио, видео",
        "бизнес и жизнь",
        "создать кворк",
        "перейти к урокам",
        "продавайте на kwork",
        "как эффективно зарабатывать",
    ]
    banned_url_markers = ["/categories/", "/kwork_book", "/faq", "/blog", "/projects"]
    if any(marker in title for marker in banned_title_markers):
        return False
    if any(marker in url for marker in banned_url_markers):
        return False
    if "/edit" in url or "edit?id=" in url:
        return True
    if price and status != "unknown":
        return True
    if any(marker in status for marker in ["черновик", "модерац", "актив", "опублик", "отклон", "пауза"]):
        return True
    return False


def page_text_summary(page) -> str:
    text = norm(page.evaluate("() => document.body ? document.body.innerText : ''"))
    return text[:3000]


def build_result() -> dict[str, Any]:
    result: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "windows_cdp_read_only",
        "browser_opened": False,
        "cdp_connected": False,
        "detected_username": "unknown",
        "expected_username": EXPECTED_ACCOUNT,
        "account_guard_status": "not_checked",
        "account_guard_action": "not_checked",
        "persistence_confirmed": False,
        "opened_url": MANAGE_KWORKS_URL,
        "final_url": "not_opened",
        "page_title": "unknown",
        "data_collection_status": "NOT_STARTED",
        "stopped_reason": "",
        "raw_candidates_count": 0,
        "kworks_collected": 0,
        "kworks": [],
        "page_text_summary": "",
        "mutation_buttons_detected": [],
        "kwork_state_changed": False,
        "final_buttons_clicked": False,
        "messages_sent": False,
        "proposals_sent": False,
        "screenshot": "",
        "warnings": [],
    }
    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=MANAGE_KWORKS_URL,
        keep_open=False,
        background=True,
        no_focus=True,
        minimized=True,
    ) as session:
        result["browser_opened"] = True
        diag = session.refresh_diagnostics()
        result["cdp_connected"] = diag.cdp_connected
        result["detected_username"] = diag.detected_username
        result["account_guard_status"] = diag.account_guard_status
        result["account_guard_action"] = diag.account_guard_action
        result["final_url"] = diag.current_url
        result["page_title"] = diag.page_title
        result["mutation_buttons_detected"] = session.find_blocked_buttons()
        result["screenshot"] = session.screenshot("kwork-profile-audit-live")
        result["persistence_confirmed"] = (
            diag.account_guard_status == "ok"
            and diag.detected_username.lower() == EXPECTED_ACCOUNT.lower()
            and diag.login_detected == "true"
        )
        if diag.account_guard_status != "ok" or diag.detected_username.lower() != EXPECTED_ACCOUNT.lower():
            result["data_collection_status"] = "STOPPED_BY_GUARD"
            result["stopped_reason"] = diag.account_guard_message or "account guard is not ok"
            return result
        if diag.login_detected != "true":
            result["data_collection_status"] = "BLOCKED_SAFE"
            result["stopped_reason"] = "login not confirmed"
            return result
        visible = session.visible_text()
        stop_reason = text_has_stop_marker(visible, diag.current_url)
        if stop_reason:
            result["data_collection_status"] = "BLOCKED_SAFE"
            result["stopped_reason"] = stop_reason
            return result
        raw_items = collect_visible_kworks(session.page)
        items = [item for item in raw_items if is_reliable_kwork_item(item)]
        result["raw_candidates_count"] = len(raw_items)
        result["page_text_summary"] = page_text_summary(session.page)
        if not items:
            result["warnings"].append("No reliable kwork cards found; page text summary saved for manual selector improvement.")
            result["data_collection_status"] = "PARTIAL"
        else:
            result["data_collection_status"] = "SUCCESS"
        for item in items:
            item.update(score_local_item(item))
        result["kworks"] = items
        result["kworks_collected"] = len(items)
        if not items and not result["stopped_reason"]:
            result["stopped_reason"] = "no visible kwork cards found"
    return result


def write_report(result: dict[str, Any]) -> None:
    ensure_dir(SNAPSHOT_DIR)
    write_json(SNAPSHOT_PATH, result)
    lines = [
        "# Kwork Profile Audit Live Report",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- mode: `{result['mode']}`",
        f"- browser_opened: `{str(result['browser_opened']).lower()}`",
        f"- cdp_connected: `{str(result['cdp_connected']).lower()}`",
        f"- detected_username: `{result['detected_username']}`",
        f"- expected_username: `{result['expected_username']}`",
        f"- account_guard_status: `{result['account_guard_status']}`",
        f"- account_guard_action: `{result['account_guard_action']}`",
        f"- persistence_confirmed: `{str(result['persistence_confirmed']).lower()}`",
        f"- opened_url: `{result['opened_url']}`",
        f"- final_url: `{result['final_url']}`",
        f"- page_title: `{result['page_title']}`",
        f"- data_collection_status: `{result['data_collection_status']}`",
        f"- raw_candidates_count: `{result.get('raw_candidates_count', 0)}`",
        f"- kworks_collected: `{result['kworks_collected']}`",
        f"- stopped_reason: `{result['stopped_reason'] or 'none'}`",
        f"- mutation_buttons_detected: `{', '.join(result['mutation_buttons_detected']) if result['mutation_buttons_detected'] else 'none'}`",
        f"- final_buttons_clicked: `{str(result['final_buttons_clicked']).lower()}`",
        f"- kwork_state_changed: `{str(result['kwork_state_changed']).lower()}`",
        f"- messages_sent: `{str(result['messages_sent']).lower()}`",
        f"- proposals_sent: `{str(result['proposals_sent']).lower()}`",
        f"- snapshot_json: `{rel(SNAPSHOT_PATH)}`",
        f"- screenshot: `{result['screenshot'] or 'none'}`",
        "",
        "## Safety",
        "- Read-only Windows CDP collector.",
        "- Opens only `https://kwork.ru/manage_kworks`.",
        "- Does not click save, publish, moderation, send, proposal, order, delete, phone, SMS, or withdrawal controls.",
        "- Does not type login, password, SMS, or credentials.",
        "- Any mutation remains manual-only.",
        "",
        "## Found Kworks",
    ]
    if not result["kworks"]:
        lines.extend(["", "- none"])
    for index, item in enumerate(result["kworks"], start=1):
        lines.extend(
            [
                "",
                f"### {index}. {item.get('title') or 'Untitled'}",
                "",
                f"- title: `{item.get('title') or 'Untitled'}`",
                f"- status: `{item.get('status', 'unknown')}`",
                f"- category: `{item.get('category') or 'unknown'}`",
                f"- subcategory: `{item.get('subcategory') or 'unknown'}`",
                f"- price: `{item.get('price') or 'unknown'}`",
                f"- cover_present: `{str(bool(item.get('cover_present'))).lower()}`",
                f"- url: `{item.get('url') or 'unknown'}`",
                f"- visible_warning: `{item.get('visible_warning') or 'none'}`",
                "",
                "#### Per-Kwork Score",
                f"- title_score: `{item.get('title_score', 'not_scored')}`",
                f"- cover_score: `{item.get('cover_score', 'not_scored')}`",
                f"- description_score: `{item.get('description_score', 'not_scored')}`",
                f"- price_score: `{item.get('price_score', 'not_scored')}`",
                f"- trust_score: `{item.get('trust_score', 'not_scored')}`",
                f"- devops_fit_score: `{item.get('devops_fit_score', 'not_scored')}`",
                f"- overall_score: `{item.get('score', item.get('marketing_score', 'not_scored'))}`",
                f"- verdict: `{item.get('verdict', 'not_scored')}`",
                "",
                "#### Recommendations",
                "- what_to_keep: keep clear result, safe scope, and manual-only publication.",
                f"- what_to_rewrite: `{'; '.join(item.get('blockers', item.get('missing_fields', []))) or 'review title/description manually'}`",
                f"- cover_to_regenerate: `{'' if item.get('cover_present') else 'yes - cover missing or not visible'}`",
                "- package_faq_questions_to_improve: add FAQ, buyer questions, safe extras, and exact delivery boundaries if missing.",
                f"- next_similar_kwork: `{item.get('next_similar_kwork', 'Python / Google Sheets automation')}`",
            ]
        )
    lines.extend(["", "## Warnings"])
    if result["warnings"]:
        lines.extend(f"- {item}" for item in result["warnings"])
    else:
        lines.append("- none")
    write_text(REPORT_PATH, "\n".join(lines))


def main() -> None:
    result = build_result()
    write_report(result)
    print(REPORT_PATH)
    print(f"data_collection_status={result['data_collection_status']}")
    print(f"kworks_collected={result['kworks_collected']}")
    print(f"account_guard_status={result['account_guard_status']}")
    print(f"detected_username={result['detected_username']}")
    print(f"final_buttons_clicked={str(result['final_buttons_clicked']).lower()}")
    print(f"kwork_state_changed={str(result['kwork_state_changed']).lower()}")


if __name__ == "__main__":
    main()
