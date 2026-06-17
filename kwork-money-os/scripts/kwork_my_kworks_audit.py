#!/usr/bin/env python3
"""Read-only audit of current ZerroOne Kworks through Windows CDP."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from browser_session import open_kwork_browser_session
from kwork_studio_common import (
    MY_KWORKS_AUDIT_JSON,
    MY_KWORKS_AUDIT_REPORT,
    ensure_studio_dirs,
    rel,
    write_json,
    write_text,
)
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL, run_check_zerroone


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
          const anchors = Array.from(document.querySelectorAll('a[href*="/edit"], a[href*="/kworks/"], a[href*="/user/"]')).filter(visible);
          const cards = [];
          const seen = new Set();
          for (const anchor of anchors) {
            const root = anchor.closest('[class*="card"], [class*="item"], [class*="kwork"], tr, li, .row') || anchor.parentElement;
            const text = norm(root?.innerText || anchor.innerText || '');
            const title = norm(anchor.innerText || '').slice(0, 180);
            const href = anchor.href || anchor.getAttribute('href') || '';
            if (!text || text.length < 8 || seen.has(href + title)) continue;
            seen.add(href + title);
            const statusMatch = text.match(/(черновик|на модерации|активн|опубликован|приостанов|отклон|пауза)/i);
            const priceMatch = text.match(/(\\d[\\d\\s]{2,8})\\s*(₽|руб)/i);
            cards.push({
              title,
              url: href,
              status: statusMatch ? statusMatch[1] : 'unknown',
              price: priceMatch ? priceMatch[0] : '',
              text: text.slice(0, 1600),
              cover_present: !!root?.querySelector?.('img'),
            });
          }
          return cards.slice(0, 30);
        }"""
    )


def score_item(item: dict[str, Any]) -> dict[str, Any]:
    text = "\n".join([str(item.get("title", "")), str(item.get("text", ""))]).lower()
    title = str(item.get("title", ""))
    cover = bool(item.get("cover_present"))
    title_score = 80 if 35 <= len(title) <= 85 else 55
    if "telegram" in text or "бот" in text:
        title_score += 10
    cover_score = 82 if cover else 35
    devops_fit = 40
    for word in ["deploy", "деплой", "docker", "linux", "api", ".env", "инструкц", "сервер"]:
        if word in text:
            devops_fit += 8
    buyer_clarity = 45
    for word in ["заяв", "таблиц", "инструкц", "google", "telegram", "python"]:
        if word in text:
            buyer_clarity += 7
    trust = 45 + (15 if cover else 0) + (15 if "инструкц" in text else 0) + (10 if "без" in text else 0)
    marketing = int((title_score + cover_score + buyer_clarity + min(devops_fit, 100) + min(trust, 100)) / 5)
    missing = []
    if not cover:
        missing.append("cover")
    if not title:
        missing.append("title")
    if "таблиц" not in text and "google" not in text:
        missing.append("specific outcome")
    if "инструкц" not in text and "deploy" not in text and "деплой" not in text:
        missing.append("handoff/deploy trust block")
    competition_risk = "medium" if marketing >= 65 else "high"
    if marketing >= 82 and not missing:
        verdict = "READY_FOR_TRAFFIC"
    elif "category" in missing:
        verdict = "NEEDS_CATEGORY_FIX"
    elif not cover:
        verdict = "REGENERATE_COVER"
    elif title_score < 70:
        verdict = "REWRITE_TITLE"
    elif missing:
        verdict = "IMPROVE_PACKAGES"
    else:
        verdict = "KEEP"
    recommendations = []
    if not cover:
        recommendations.append("Добавить сильную обложку: крупный заголовок, схема чат -> таблица -> сервер, без реальных логотипов.")
    if title_score < 75:
        recommendations.append("Сделать title конкретнее: результат + Telegram + Google Таблица.")
    if "инструкц" not in text:
        recommendations.append("Добавить доверие: README, .env.example, запуск polling/webhook, инструкция проверки.")
    if "docker" not in text and "linux" not in text:
        recommendations.append("DevOps-усиление оставить в premium/доп. опции: Docker/Linux/VPS/logging.")
    if "спам" in text or "обход" in text or "накрут" in text:
        recommendations.append("Убрать серые темы: спам, обходы, накрутка, капча.")
    return {
        "marketing_score": max(0, min(marketing, 100)),
        "cover_score": max(0, min(cover_score, 100)),
        "title_score": max(0, min(title_score, 100)),
        "trust_score": max(0, min(trust, 100)),
        "devops_fit_score": max(0, min(devops_fit, 100)),
        "buyer_clarity_score": max(0, min(buyer_clarity, 100)),
        "competition_risk": competition_risk,
        "verdict": verdict,
        "missing_fields": missing,
        "recommendations": recommendations or ["Оставить как есть и проверить глазами перед трафиком."],
    }


def fallback_current_form(page) -> list[dict[str, Any]]:
    title = page.evaluate("() => document.querySelector('#editor-title')?.innerText || document.querySelector('input[name=\"name\"]')?.value || ''")
    text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 1600) : ''")
    if not title and not text:
        return []
    return [
        {
            "title": title or "Текущий редактируемый кворк",
            "url": page.url,
            "status": "current_editing_or_draft",
            "price": "",
            "text": text,
            "cover_present": bool(page.locator("input[type='file']").count()),
        }
    ]


def run() -> dict[str, Any]:
    ensure_studio_dirs()
    check = run_check_zerroone(restart_check=True)
    result: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "account_guard_status": check.account_guard_status,
        "persistence_confirmed": check.persistence_confirmed,
        "kworks_count": 0,
        "kworks": [],
        "warnings": [],
        "screenshot": "",
    }
    if check.account_guard_status != "ok" or not check.persistence_confirmed:
        result["warnings"].append("Account guard or persistence check failed.")
        write_outputs(result)
        return result
    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=MANAGE_KWORKS_URL,
        keep_open=True,
        background=True,
        no_focus=True,
        minimized=True,
    ) as session:
        diag = session.refresh_diagnostics()
        if diag.account_guard_status != "ok":
            result["warnings"].append("Browser session guard failed.")
        else:
            items = collect_visible_kworks(session.page)
            if not items:
                try:
                    session.open("https://kwork.ru/new")
                    items = fallback_current_form(session.page)
                except Exception as error:
                    result["warnings"].append(f"fallback current form failed: {error}")
            for item in items:
                item.update(score_item(item))
            result["kworks"] = items
            result["kworks_count"] = len(items)
        result["screenshot"] = session.screenshot("my-kworks-audit")
    write_outputs(result)
    return result


def write_outputs(result: dict[str, Any]) -> None:
    write_json(MY_KWORKS_AUDIT_JSON, result)
    lines = [
        "# My Kworks Audit Report",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- account_guard_status: `{result['account_guard_status']}`",
        f"- persistence_confirmed: `{str(result['persistence_confirmed']).lower()}`",
        f"- kworks_count: `{result['kworks_count']}`",
        f"- json: `{rel(MY_KWORKS_AUDIT_JSON)}`",
        f"- screenshot: `{result.get('screenshot', '')}`",
        "",
    ]
    for index, item in enumerate(result["kworks"], start=1):
        lines.extend(
            [
                f"## {index}. {item.get('title') or 'Untitled'}",
                "",
                f"- status: `{item.get('status', 'unknown')}`",
                f"- url: `{item.get('url', '')}`",
                f"- price: `{item.get('price') or 'unknown'}`",
                f"- cover_present: `{str(bool(item.get('cover_present'))).lower()}`",
                f"- marketing_score: `{item['marketing_score']}`",
                f"- cover_score: `{item['cover_score']}`",
                f"- title_score: `{item['title_score']}`",
                f"- trust_score: `{item['trust_score']}`",
                f"- devops_fit_score: `{item['devops_fit_score']}`",
                f"- buyer_clarity_score: `{item['buyer_clarity_score']}`",
                f"- competition_risk: `{item['competition_risk']}`",
                f"- verdict: `{item['verdict']}`",
                f"- missing_fields: `{', '.join(item['missing_fields']) or 'none'}`",
                "",
                "### Recommendations",
                *(f"- {line}" for line in item["recommendations"]),
                "",
            ]
        )
    lines.extend(
        [
            "## Warnings",
            *(f"- {item}" for item in result["warnings"]),
            "",
            "## Safety",
            "- Read-only audit.",
            "- No delete/pause/save/moderation/publish/send buttons clicked.",
        ]
    )
    write_text(MY_KWORKS_AUDIT_REPORT, "\n".join(lines))


def main() -> None:
    result = run()
    print(MY_KWORKS_AUDIT_REPORT)
    print(f"kworks_count={result['kworks_count']}")
    for index, item in enumerate(result["kworks"], start=1):
        print(f"kwork{index}={item.get('verdict')} | {item.get('marketing_score')} | {item.get('title')}")


if __name__ == "__main__":
    main()
