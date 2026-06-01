#!/usr/bin/env python3
"""Collect a small public Kwork market snapshot for selected niches."""

from __future__ import annotations

import argparse
import html
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

from _common import CONFIG, DATA, ensure_dir, load_yaml, today_slug, write_json


SEARCH_URL = "https://kwork.ru/search?query={query}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 KworkMoneyOS/0.1 public-market-research",
    "Accept-Language": "ru,en;q=0.8",
}


def clean_text(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def parse_public_cards(page_html: str, keyword: str, limit: int) -> list[dict]:
    cards: list[dict] = []
    chunks = re.split(r"(?=<a\b)", page_html)
    seen: set[str] = set()

    for chunk in chunks:
        if "kwork" not in chunk.lower():
            continue
        href_match = re.search(r'href=["\']([^"\']*(?:/kwork/|/projects/|/portfolio/|/user/)[^"\']*)', chunk, re.I)
        title_match = re.search(r'(?:title|alt)=["\']([^"\']{12,160})["\']', chunk, re.I)
        title = clean_text(title_match.group(1)) if title_match else clean_text(chunk)[:160]
        if not title or len(title) < 12:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        text = clean_text(chunk[:4000])
        price_match = re.search(r"(\d[\d\s]{2,})\s*(?:₽|руб|р\.)", text, re.I)
        days_match = re.search(r"(\d{1,2})\s*(?:дн|день|дня|дней)", text, re.I)
        rating_match = re.search(r"([1-5][.,]\d)\s*(?:из\s*5)?", text)
        reviews_match = re.search(r"(\d{1,5})\s*(?:отзыв|оцен)", text, re.I)
        queue_match = re.search(r"(\d{1,3})\s*(?:в\s*очереди|заказ)", text, re.I)

        cards.append(
            {
                "niche": keyword,
                "title": title,
                "url": html.unescape(href_match.group(1)) if href_match else None,
                "price_rub": int(re.sub(r"\D", "", price_match.group(1))) if price_match else None,
                "packages": "visible" if re.search(r"эконом|стандарт|бизнес|пакет", text, re.I) else None,
                "delivery_days": int(days_match.group(1)) if days_match else None,
                "rating": float(rating_match.group(1).replace(",", ".")) if rating_match else None,
                "reviews": int(reviews_match.group(1)) if reviews_match else None,
                "queue": int(queue_match.group(1)) if queue_match else None,
                "raw_signals": text[:500],
            }
        )
        if len(cards) >= limit:
            break
    return cards


def keyword_terms(items: list[dict]) -> list[tuple[str, int]]:
    words: Counter[str] = Counter()
    stop = {"для", "под", "или", "ваш", "вашего", "бот", "сайт", "кворк", "услуги"}
    for item in items:
        for word in re.findall(r"[a-zа-яё0-9]{3,}", item.get("title", "").lower(), flags=re.I):
            if word not in stop:
                words[word] += 1
    return words.most_common(20)


def score_niche(keyword: str, items: list[dict], scoring: dict) -> dict:
    defaults = scoring.get("defaults", {})
    weights = {
        "demand": float(scoring.get("demand_weight", 0.30)),
        "price": float(scoring.get("price_weight", 0.20)),
        "skill_fit": float(scoring.get("my_skill_fit_weight", 0.25)),
        "low_competition": float(scoring.get("competition_weight", 0.15)),
        "speed": float(scoring.get("delivery_complexity_weight", 0.10)),
        "risk": float(scoring.get("risk_weight", 0.20)),
    }
    prices = [item["price_rub"] for item in items if item.get("price_rub")]
    days = [item["delivery_days"] for item in items if item.get("delivery_days")]
    reviews = [item["reviews"] for item in items if item.get("reviews")]
    queue = [item["queue"] for item in items if item.get("queue")]

    demand = min(100, int(defaults.get("demand", 45)) + len(items) * 5 + min(sum(reviews), 200) // 8 + min(sum(queue), 50))
    avg_price = sum(prices) / len(prices) if prices else 3000
    price = max(20, min(100, int(avg_price / 120)))
    low_competition = max(20, 100 - len(items) * 7)
    speed = max(20, 100 - int((sum(days) / len(days)) * 7)) if days else int(defaults.get("speed", 60))
    risk = 45 if re.search(r"ai|openai|парс|scrap|бот", keyword, re.I) else int(defaults.get("risk", 30))

    skill_fit = int(defaults.get("skill_fit", 70))
    for term, value in (scoring.get("skill_fit") or {}).items():
        if term.lower() in keyword.lower():
            skill_fit = max(skill_fit, int(value))

    hot_score = (
        demand * weights["demand"]
        + price * weights["price"]
        + skill_fit * weights["skill_fit"]
        + low_competition * weights["low_competition"]
        + speed * weights["speed"]
        - risk * weights["risk"]
    )
    return {
        "keyword": keyword,
        "hot_score": max(0, min(100, round(hot_score, 1))),
        "demand": demand,
        "price": price,
        "skill_fit": skill_fit,
        "low_competition": low_competition,
        "speed": speed,
        "risk": risk,
        "average_price_rub": round(avg_price, 2) if prices else None,
        "results_seen": len(items),
    }


def scan_keyword(keyword: str, limit: int, offline: bool) -> dict:
    url = SEARCH_URL.format(query=quote_plus(keyword))
    if offline:
        return {"keyword": keyword, "url": url, "items": [], "note": "offline mode: no request made"}

    response = requests.get(url, headers=HEADERS, timeout=20)
    if response.status_code in {403, 429}:
        return {"keyword": keyword, "url": url, "items": [], "note": f"blocked_or_limited_http_{response.status_code}"}
    response.raise_for_status()
    return {"keyword": keyword, "url": url, "items": parse_public_cards(response.text, keyword, limit)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", nargs="*", help="Niches or search phrases")
    parser.add_argument("--keywords-file", default=str(CONFIG / "keywords.yaml"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--offline", action="store_true", help="Create an empty dated report without network calls")
    args = parser.parse_args()

    keyword_config = load_yaml(Path(args.keywords_file))
    keywords = args.keywords or keyword_config.get("niches") or []
    limit = args.limit or int(keyword_config.get("max_results_per_keyword", 8))
    delay = args.delay if args.delay is not None else float(keyword_config.get("request_delay_seconds", 2.0))
    scoring = load_yaml(CONFIG / "scoring.yaml")

    scans = []
    for index, keyword in enumerate(keywords):
        scans.append(scan_keyword(keyword, limit, args.offline))
        if index < len(keywords) - 1 and not args.offline:
            time.sleep(max(delay, 1.5))

    all_items = [item for scan in scans for item in scan.get("items", [])]
    niches = [
        score_niche(scan["keyword"], scan.get("items", []), scoring)
        for scan in scans
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "public Kwork search pages",
        "policy": {
            "public_data_only": True,
            "no_captcha_bypass": True,
            "no_aggressive_scraping": True,
            "private_data_collected": False,
        },
        "keywords": keywords,
        "niche_scores": sorted(niches, key=lambda item: item["hot_score"], reverse=True),
        "keyword_terms": keyword_terms(all_items),
        "repeated_offers": [title for title, count in Counter(item["title"] for item in all_items).items() if count > 1],
        "scans": scans,
    }

    output = ensure_dir(DATA / "market") / f"{today_slug()}.json"
    write_json(output, report)
    print(output)


if __name__ == "__main__":
    main()
