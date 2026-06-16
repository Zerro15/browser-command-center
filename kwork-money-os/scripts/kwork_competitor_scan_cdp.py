#!/usr/bin/env python3
"""Read-only Windows CDP competitor scan for Kwork Production Studio."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from browser_session import open_kwork_browser_session
from kwork_studio_common import COMPETITOR_REPORT, COMPETITORS_JSON, ensure_studio_dirs, rel, write_json, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT


QUERY = "telegram bot google sheets python docker"
SEARCH_URL = f"https://kwork.ru/search?query={quote_plus(QUERY)}"
BLOCK_RE = re.compile(r"captcha|капча|подтвердите|проверка безопасности|доступ ограничен", re.I)


def analyze_card(item: dict) -> dict:
    text = f"{item.get('title','')} {item.get('text','')}".lower()
    strengths = []
    weaknesses = []
    if "telegram" in text or "телеграм" in text:
        strengths.append("mentions Telegram")
    if "google" in text or "таблиц" in text:
        strengths.append("mentions Google Sheets/table result")
    if "docker" in text or "linux" in text or "сервер" in text:
        strengths.append("has DevOps/deploy angle")
    if not item.get("has_cover"):
        weaknesses.append("cover not detected")
    if len(item.get("title", "")) < 25:
        weaknesses.append("title may be too generic")
    return {
        **item,
        "strengths": strengths or ["clear marketplace positioning"],
        "weaknesses": weaknesses or ["unknown differentiation"],
    }


def main() -> None:
    ensure_studio_dirs()
    competitors: list[dict] = []
    status = "success"
    warning = "none"
    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=SEARCH_URL,
        background=True,
        no_focus=True,
        minimized=True,
    ) as session:
        session.open(SEARCH_URL)
        text = session.visible_text()
        if BLOCK_RE.search(text):
            status = "soft_stop"
            warning = "captcha_or_security_check_detected"
        else:
            raw = session.page.evaluate(
                """() => {
                  const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                  };
                  const cards = Array.from(document.querySelectorAll('a[href*="/kwork/"], .card, .kw-card, [class*="card"]'))
                    .filter(visible)
                    .slice(0, 30)
                    .map((el) => {
                      const link = el.matches('a') ? el : el.querySelector('a[href*="/kwork/"]');
                      const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                      const title = (link ? link.innerText : '').replace(/\\s+/g, ' ').trim() || text.split(' ').slice(0, 12).join(' ');
                      const priceMatch = text.match(/(?:от\\s*)?[0-9\\s]+\\s*₽/);
                      return {
                        title: title.slice(0, 140),
                        url: link ? link.href : '',
                        text: text.slice(0, 600),
                        price: priceMatch ? priceMatch[0].replace(/\\s+/g, ' ').trim() : 'unknown',
                        has_cover: !!el.querySelector('img'),
                        rating_or_count: (text.match(/[0-9]+(?:\\.[0-9]+)?\\s*(?:отзыв|заказ|★)/i) || ['unknown'])[0]
                      };
                    })
                    .filter((item) => item.title || item.text);
                  const uniq = [];
                  const seen = new Set();
                  for (const item of cards) {
                    const key = item.url || item.title;
                    if (!seen.has(key)) { seen.add(key); uniq.push(item); }
                  }
                  return uniq.slice(0, 20);
                }"""
            )
            competitors = [analyze_card(item) for item in raw]
            if not competitors:
                status = "soft_stop"
                warning = "no_visible_competitor_cards"
        diag = session.refresh_diagnostics()
        screenshot = session.screenshot("competitor-scan-cdp")
        repeated_words = sorted(
            {
                word
                for item in competitors
                for word in re.findall(r"[A-Za-zА-Яа-я]{5,}", item.get("title", "").lower())
                if word not in {"kwork", "сделаю", "telegram"}
            }
        )[:20]
    output = {
        "status": status,
        "query": QUERY,
        "competitors_count": len(competitors),
        "competitors": competitors,
        "repeated_words": repeated_words if competitors else [],
        "what_to_do_better": [
            "Сделать title с конкретным результатом: заявки + Google Таблица + мини-админка.",
            "Добавить DevOps-доверие: .env, инструкция, Docker/Linux в Premium.",
            "Не обещать CRM/продажи/обходы, держать фокус на безопасном MVP.",
        ],
    }
    write_json(COMPETITORS_JSON, output)
    lines = [
        "# Kwork Competitor Scan CDP Report",
        "",
        f"- status: `{status}`",
        f"- warning: `{warning}`",
        f"- browser_mode: `windows_cdp`",
        f"- cdp_connected: `{str(diag.cdp_connected).lower()}`",
        f"- detected_username: `{diag.detected_username}`",
        f"- account_guard_status: `{diag.account_guard_status}`",
        f"- foreground_policy: `{diag.foreground_policy}`",
        f"- background_mode: `{str(diag.background_mode).lower()}`",
        f"- brought_to_front_count: `{diag.brought_to_front_count}`",
        f"- competitors_count: `{len(competitors)}`",
        f"- competitors_json: `{rel(COMPETITORS_JSON)}`",
        f"- screenshot: `{screenshot}`",
        "",
        "## Insights",
        *(f"- {item}" for item in output["what_to_do_better"]),
        "",
        "## Competitors",
        *(f"- {item.get('title','untitled')} | {item.get('price','unknown')} | cover={item.get('has_cover')} | {item.get('url','')}" for item in competitors[:20]),
        "",
        "## Safety",
        "- Read-only scan. No buy/order/message/proposal/final buttons clicked.",
    ]
    write_text(COMPETITOR_REPORT, "\n".join(lines))
    print(COMPETITOR_REPORT)
    print(f"status={status}")
    print(f"competitors_count={len(competitors)}")
    print(f"foreground_policy={diag.foreground_policy}")
    print(f"brought_to_front_count={diag.brought_to_front_count}")


if __name__ == "__main__":
    main()
