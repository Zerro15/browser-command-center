#!/usr/bin/env python3
"""Simple read-only exporter for all visible Kwork cards on "My Kworks"."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from browser_rpa_bridge import PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_studio_common import rel, write_json, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL


OUTPUT_DIR = DATA / "kwork_profile_audit"
JSON_PATH = OUTPUT_DIR / "all_kworks_list.json"
REPORT_PATH = REPORTS / "kwork_all_kworks_list.md"
TABS = ["Активные", "Черновики", "Все"]

FORBIDDEN_ACTION_LABELS = [
    "Сохранить",
    "На модерацию",
    "Опубликовать",
    "Отправить",
    "Предложить услугу",
    "Принять заказ",
    "Удалить",
    "Пауза",
    "Приостановить",
    "Редактировать",
]


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_count_from_text(text: str, label: str) -> int | None:
    match = re.search(rf"{re.escape(label)}\s+(\d+)", text, re.I)
    return int(match.group(1)) if match else None


def click_tab(page, label: str) -> bool:
    """Click only top-level text tab/filter controls, never item action icons."""
    return bool(
        page.evaluate(
            """(label) => {
              const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
              const visible = (el) => {
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const candidates = Array.from(document.querySelectorAll('.k-tabs__item, a, button, [role="tab"], [class*="tab"], [class*="filter"]'))
                .filter(visible)
                .filter((el) => {
                  const text = norm(el.innerText || el.textContent || el.getAttribute('aria-label') || '');
                  if (!text) return false;
                  if (!text.toLowerCase().startsWith(label.toLowerCase())) return false;
                  if (text.length > label.length + 12) return false;
                  const href = el.getAttribute('href') || '';
                  if (/delete|remove|pause|edit|moderation|publish|send/i.test(href)) return false;
                  return true;
                });
              const target = candidates[0];
              if (!target) return false;
              target.scrollIntoView({block: 'center', inline: 'center'});
              for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                target.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
              }
              return true;
            }""",
            label,
        )
    )


def scroll_page(page) -> None:
    for _ in range(6):
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(700)
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(400)


def collect_cards(page, tab: str) -> list[dict[str, Any]]:
    return page.evaluate(
        """(tab) => {
          const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const visible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const hrefOf = (root) => {
            const links = Array.from(root.querySelectorAll?.('a[href]') || []);
            const preferred = links.find((a) => /\\/software\\/\\d+|\\/kwork\\/|\\/edit/i.test(a.href || a.getAttribute('href') || ''));
            const link = preferred || links[0];
            return link ? (link.href || link.getAttribute('href') || '') : '';
          };
          const titleOf = (root) => {
            const selectors = ['a[href*="/software/"]', 'a[href*="/kwork/"]', 'a[href*="/edit"]', '[class*="title"]', 'h1', 'h2', 'h3'];
            for (const selector of selectors) {
              const item = root.querySelector?.(selector);
              const text = norm(item?.innerText || item?.textContent || '');
              if (text && text.length >= 5 && text.length <= 180) return text;
            }
            const lines = norm(root.innerText || '').split(/\\n|(?<=\\S)\\s{2,}/).map(norm).filter(Boolean);
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
          const bannedTitle = [
            'разработка и it', 'тексты и переводы', 'seo и трафик', 'соцсети и маркетинг',
            'обработка звука', 'аудио, видео', 'бизнес и жизнь', 'создать кворк',
            'перейти к урокам', 'продавайте на kwork', 'как эффективно зарабатывать'
          ];
          const bannedHref = ['/categories/', '/kwork_book', '/faq', '/blog', '/projects'];
          const seen = new Set();
          const cards = [];
          for (const root of roots) {
            const text = norm(root.innerText || root.textContent || '');
            if (text.length < 20) continue;
            const title = titleOf(root);
            const href = hrefOf(root);
            const lowerTitle = title.toLowerCase();
            const lowerHref = href.toLowerCase();
            if (!title || !href) continue;
            if (bannedTitle.some((marker) => lowerTitle.includes(marker))) continue;
            if (bannedHref.some((marker) => lowerHref.includes(marker))) continue;
            if (!(/\\/software\\/\\d+|\\/kwork\\/|\\/edit/i.test(href) || /просмотры|продажи|заработано|конкуренц/i.test(text))) continue;
            const key = `${tab}|${href}|${title}`;
            if (seen.has(key)) continue;
            seen.add(key);
            const priceMatch = text.match(/(\\d[\\d\\s]{0,8})\\s*(₽|руб\\.?)/i);
            const viewsMatch = text.match(/Просмотры:\\s*(\\d+)/i);
            const salesMatch = text.match(/Продажи:\\s*(\\d+)/i);
            const earnedMatch = text.match(/Заработано:\\s*([\\d\\s]+\\s*₽|\\d+)/i);
            const competitionMatch = text.match(/Конкуренция:\\s*([^\\n]+?)(?:\\s+Здесь|\\s+\\d[\\d\\s]*\\s*₽|$)/i);
            const statusMatch = text.match(/(Активн\\w*|Черновик\\w*|На модерации|Отклон[её]н\\w*|Приостановлен\\w*)/i);
            cards.push({
              tab,
              position: cards.length + 1,
              title,
              status: statusMatch ? statusMatch[1] : tab,
              price: priceMatch ? `${priceMatch[1].trim()} ${priceMatch[2]}` : '',
              views: viewsMatch ? viewsMatch[1] : '',
              sales: salesMatch ? salesMatch[1] : '',
              earned: earnedMatch ? earnedMatch[1].trim() : '',
              competition: competitionMatch ? competitionMatch[1].trim() : '',
              cover_present: !!root.querySelector?.('img'),
              url: href,
              raw_text: text.slice(0, 900)
            });
          }
          return cards;
        }""",
        tab,
    )


def collect_drafts_from_text(page, tab: str) -> list[dict[str, Any]]:
    """Fallback for draft cards that Kwork renders without public kwork links."""
    if tab not in {"Черновики", "Все"}:
        return []
    text = page.evaluate("() => document.body.innerText || ''")
    lines = [norm(line) for line in str(text).splitlines()]
    lines = [line for line in lines if line]
    if "Продолжить заполнение" not in lines:
        return []

    blocked_title_markers = {
        "ФРИЛАНС МАРКЕТПЛЕЙС",
        "Кворки",
        "Заказы",
        "Биржа",
        "Дизайн",
        "Разработка и IT",
        "Тексты и переводы",
        "SEO и трафик",
        "Соцсети и маркетинг",
        "Аудио, видео, съемка",
        "Бизнес и жизнь",
        "Мои кворки",
        "Создать кворк (РУС/EN)",
        "Принимаю заказы",
        "Скрывать кворки на выходные",
        "Активные",
        "Черновики",
        "Все",
        "Черновик",
        "Заполните все поля, чтобы покупатели могли увидеть его в каталоге и сделать заказ.",
        "Продолжить заполнение",
    }
    cards: list[dict[str, Any]] = []
    block: list[str] = []
    for line in lines:
        block.append(line)
        if line != "Продолжить заполнение":
            continue
        price = ""
        for candidate in block:
            if re.fullmatch(r"\d[\d\s]*\s*₽", candidate):
                price = candidate
        candidates = []
        for candidate in block:
            if candidate in blocked_title_markers:
                continue
            if candidate.isdigit() or re.fullmatch(r"\d[\d\s]*\s*₽", candidate):
                continue
            if candidate.startswith("Готовится к публикации"):
                continue
            if candidate.startswith("Внимание!") or candidate.startswith("Ваши кворки"):
                continue
            if len(candidate) < 5 or len(candidate) > 180:
                continue
            candidates.append(candidate)
        title = candidates[-1] if candidates else ""
        if title:
            cards.append(
                {
                    "tab": tab,
                    "position": len(cards) + 1,
                    "title": title,
                    "status": "Черновик",
                    "price": price,
                    "views": "",
                    "sales": "",
                    "earned": "",
                    "competition": "",
                    "cover_present": False,
                    "url": "",
                    "raw_text": " ".join(block[-8:])[:900],
                }
            )
        block = []
    return cards


def merge_cards(primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = list(primary)
    seen = {
        card.get("url") or f"{card.get('title')}|{card.get('price')}|{card.get('status')}"
        for card in cards
    }
    for card in fallback:
        key = card.get("url") or f"{card.get('title')}|{card.get('price')}|{card.get('status')}"
        if key in seen:
            continue
        card = dict(card)
        card["position"] = len(cards) + 1
        cards.append(card)
        seen.add(key)
    return cards


def unique_cards(tab_cards: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for tab in TABS:
        for card in tab_cards.get(tab, []):
            key = card.get("url") or f"{card.get('title')}|{card.get('price')}|{card.get('status')}"
            existing = seen.get(key)
            if existing:
                tabs = set(str(existing.get("tabs", "")).split(", "))
                tabs.add(tab)
                existing["tabs"] = ", ".join(item for item in TABS if item in tabs)
            else:
                item = dict(card)
                item["tabs"] = tab
                seen[key] = item
    return list(seen.values())


def collection_status(ui_counts: dict[str, int | None], tab_cards: dict[str, list[dict[str, Any]]], unique: list[dict[str, Any]]) -> str:
    all_count = ui_counts.get("Все")
    if all_count and len(unique) >= all_count:
        return "FULL_ENOUGH"
    if unique:
        return "PARTIAL"
    return "FAILED_SAFE"


def write_outputs(payload: dict[str, Any]) -> None:
    ensure_dir(OUTPUT_DIR)
    write_json(JSON_PATH, payload)
    lines = [
        "# Все кворки ZerroOne",
        "",
        "## Summary",
        f"- active_ui_count: `{payload['ui_counts'].get('Активные')}`",
        f"- drafts_ui_count: `{payload['ui_counts'].get('Черновики')}`",
        f"- all_ui_count: `{payload['ui_counts'].get('Все')}`",
        f"- collected_unique: `{len(payload['unique_kworks'])}`",
        f"- collection_status: `{payload['collection_status']}`",
        f"- account_guard_status: `{payload['account_guard_status']}`",
        f"- detected_username: `{payload['detected_username']}`",
        f"- final_buttons_clicked: `false`",
        f"- kwork_state_changed: `false`",
        f"- json: `{rel(JSON_PATH)}`",
        "",
    ]
    for tab in TABS:
        lines.extend([f"## {tab}", ""])
        items = payload["tabs"].get(tab, [])
        if not items:
            lines.append("- none")
        for index, item in enumerate(items, start=1):
            lines.append(
                f"{index}. {item['title']} — {item.get('price') or 'цена не видна'} — "
                f"просмотры: {item.get('views') or '?'} — продажи: {item.get('sales') or '?'} — "
                f"конкуренция: {item.get('competition') or '?'}"
            )
        lines.append("")
    lines.extend(
        [
            "## Unique Kworks",
            "",
            "| # | Title | Status/Tab | Price | Views | Sales | Competition |",
            "|---|-------|------------|-------|-------|-------|-------------|",
        ]
    )
    for index, item in enumerate(payload["unique_kworks"], start=1):
        lines.append(
            f"| {index} | {item.get('title', '')} | {item.get('status') or item.get('tabs', '')} / {item.get('tabs', '')} | "
            f"{item.get('price') or ''} | {item.get('views') or ''} | {item.get('sales') or ''} | {item.get('competition') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "- Read-only exporter.",
            "- Only Kwork list tabs may be clicked.",
            "- Edit, pause, delete, save, moderation, publish, send, proposal, order, phone, SMS, and withdrawal controls are not clicked.",
        ]
    )
    write_text(REPORT_PATH, "\n".join(lines))


def run() -> dict[str, Any]:
    with open_kwork_browser_session(
        mode="windows_cdp",
        account=EXPECTED_ACCOUNT,
        start_url=MANAGE_KWORKS_URL,
        keep_open=False,
        background=True,
        no_focus=True,
        minimized=True,
    ) as session:
        diag = session.refresh_diagnostics()
        if diag.account_guard_status != "ok" or diag.detected_username.lower() != EXPECTED_ACCOUNT.lower():
            payload = {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "collection_status": "STOPPED_BY_GUARD",
                "account_guard_status": diag.account_guard_status,
                "detected_username": diag.detected_username,
                "ui_counts": {},
                "tabs": {tab: [] for tab in TABS},
                "unique_kworks": [],
                "warnings": [diag.account_guard_message],
            }
            write_outputs(payload)
            return payload
        text = session.visible_text()
        if PHONE_VERIFICATION_RE.search(text) or "new_phone_verify=1" in diag.current_url:
            payload = {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "collection_status": "BLOCKED_SAFE",
                "account_guard_status": diag.account_guard_status,
                "detected_username": diag.detected_username,
                "ui_counts": {},
                "tabs": {tab: [] for tab in TABS},
                "unique_kworks": [],
                "warnings": ["phone/SMS verification page detected"],
            }
            write_outputs(payload)
            return payload
        ui_counts = {tab: parse_count_from_text(text, tab) for tab in TABS}
        tab_cards: dict[str, list[dict[str, Any]]] = {}
        for tab in TABS:
            clicked = click_tab(session.page, tab)
            session.page.wait_for_timeout(1800 if clicked else 300)
            scroll_page(session.page)
            tab_cards[tab] = merge_cards(
                collect_cards(session.page, tab),
                collect_drafts_from_text(session.page, tab),
            )
        unique = unique_cards(tab_cards)
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "collection_status": collection_status(ui_counts, tab_cards, unique),
            "account_guard_status": diag.account_guard_status,
            "detected_username": diag.detected_username,
            "ui_counts": ui_counts,
            "tabs": tab_cards,
            "unique_kworks": unique,
            "final_buttons_clicked": False,
            "kwork_state_changed": False,
            "warnings": [],
        }
        write_outputs(payload)
        return payload


def main() -> None:
    payload = run()
    print(f"Найдено кворков: {len(payload['unique_kworks'])}")
    print(f"Активные: {len(payload['tabs'].get('Активные', []))}")
    print(f"Черновики: {len(payload['tabs'].get('Черновики', []))}")
    print(f"Все: {len(payload['tabs'].get('Все', []))}")
    print(f"Отчёт: {rel(REPORT_PATH)}")
    for index, item in enumerate(payload["unique_kworks"][:15], start=1):
        print(f"{index}. {item.get('title', 'Untitled')}")


if __name__ == "__main__":
    main()
