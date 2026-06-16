"""Build normalized Google Sheets rows from Yandex Direct statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


KEYWORD_HEADERS = [
    "Дата от",
    "Дата до",
    "Запрос",
    "Показы",
    "Клики",
    "Конверсии",
    "CTR",
    "Отказы",
    "Расход",
    "CPA",
    "CPC",
]

CAMPAIGN_HEADERS = [
    "Дата",
    "День недели",
    "Кампания",
    "Тип кампании",
    "Показы",
    "Клики",
    "CTR",
    "Отказы",
    "Конверсии",
    "CR",
    "Расход",
    "Стоимость конверсии",
    "CPC",
]


@dataclass(frozen=True)
class ReportTable:
    title: str
    headers: list[str]
    rows: list[list[Any]]


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def money(value: float) -> float:
    return round(float(value or 0), 2)


def weekday_name(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return ""
    names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return names[parsed.weekday()]


def build_keyword_rows(stats: list[dict[str, Any]], date_from: str, date_to: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in stats:
        impressions = int(item.get("impressions", 0) or 0)
        clicks = int(item.get("clicks", 0) or 0)
        conversions = int(item.get("conversions", 0) or 0)
        cost = money(float(item.get("cost", 0) or 0))
        rows.append(
            [
                date_from,
                date_to,
                item.get("query", ""),
                impressions,
                clicks,
                conversions,
                safe_divide(clicks, impressions),
                safe_divide(float(item.get("bounces", 0) or 0), clicks),
                cost,
                money(cost / conversions) if conversions else 0.0,
                money(cost / clicks) if clicks else 0.0,
            ]
        )
    return rows


def build_campaign_rows(stats: list[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in stats:
        impressions = int(item.get("impressions", 0) or 0)
        clicks = int(item.get("clicks", 0) or 0)
        conversions = int(item.get("conversions", 0) or 0)
        cost = money(float(item.get("cost", 0) or 0))
        stat_date = str(item.get("date", ""))
        rows.append(
            [
                stat_date,
                weekday_name(stat_date),
                item.get("campaign", ""),
                item.get("campaign_type", ""),
                impressions,
                clicks,
                safe_divide(clicks, impressions),
                safe_divide(float(item.get("bounces", 0) or 0), clicks),
                conversions,
                safe_divide(conversions, clicks),
                cost,
                money(cost / conversions) if conversions else 0.0,
                money(cost / clicks) if clicks else 0.0,
            ]
        )
    return rows


def build_report(keyword_stats: list[dict[str, Any]], campaign_stats: list[dict[str, Any]], date_from: str, date_to: str) -> list[ReportTable]:
    return [
        ReportTable("Ключевые слова", KEYWORD_HEADERS, build_keyword_rows(keyword_stats, date_from, date_to)),
        ReportTable("Кампании", CAMPAIGN_HEADERS, build_campaign_rows(campaign_stats)),
    ]


def mock_keyword_stats() -> list[dict[str, Any]]:
    return [
        {"query": "купить услугу", "impressions": 1200, "clicks": 84, "conversions": 6, "bounces": 18, "cost": 3150.75},
        {"query": "автоматизация отчета", "impressions": 640, "clicks": 52, "conversions": 4, "bounces": 9, "cost": 1880.2},
    ]


def mock_campaign_stats() -> list[dict[str, Any]]:
    return [
        {"date": "2026-06-15", "campaign": "Search Brand", "campaign_type": "Поиск", "impressions": 1800, "clicks": 132, "conversions": 9, "bounces": 21, "cost": 4820.5},
        {"date": "2026-06-15", "campaign": "RSYA Retarget", "campaign_type": "РСЯ", "impressions": 3200, "clicks": 96, "conversions": 5, "bounces": 30, "cost": 2750.0},
    ]
