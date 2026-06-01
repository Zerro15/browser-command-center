#!/usr/bin/env python3
"""Analyze market scan output and write a competitor report."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from _common import DATA, REPORTS, ensure_dir, latest_file, load_json, today_slug, write_json


def weak_spots(item: dict) -> list[str]:
    spots = []
    title = item.get("title", "")
    if len(title) < 35:
        spots.append("короткий заголовок без конкретики")
    if not item.get("price_rub"):
        spots.append("цена не видна в сниппете")
    if not item.get("reviews"):
        spots.append("нет видимых отзывов в публичном фрагменте")
    if not item.get("packages"):
        spots.append("пакеты не считываются из публичного фрагмента")
    if "любой" in title.lower() or "качественно" in title.lower():
        spots.append("общая формулировка вместо результата")
    return spots


def differentiators(items: list[dict]) -> list[str]:
    suggestions = [
        "зафиксировать один понятный результат в заголовке",
        "дать базовый объем и честные ограничения",
        "показать стек и формат сдачи результата",
        "добавить вопросы к покупателю, чтобы уменьшить неопределенность",
    ]
    if any(not item.get("packages") for item in items):
        suggestions.append("сделать пакеты economy/standard/business явно различимыми")
    if any(not item.get("delivery_days") for item in items):
        suggestions.append("подчеркнуть предсказуемый срок выполнения")
    return suggestions


def build_report(data: dict) -> tuple[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for scan in data.get("scans", []):
        grouped[scan.get("keyword", "unknown")].extend(scan.get("items", []))

    summary = {}
    lines = [
        "# Competitor report",
        "",
        f"Source: `{data.get('source', 'unknown')}`",
        "",
    ]
    for niche, items in grouped.items():
        titles = [item.get("title", "") for item in items if item.get("title")]
        strongest = sorted(titles, key=lambda value: (len(value), value), reverse=True)[:5]
        spots = {}
        for item in items:
            item_spots = weak_spots(item)
            if item_spots:
                spots[item.get("title", "unknown")] = item_spots
        diff = differentiators(items)
        summary[niche] = {
            "competitors_seen": len(items),
            "strong_titles": strongest,
            "weak_spots": spots,
            "differentiators": diff,
        }
        lines.extend(
            [
                f"## {niche}",
                "",
                f"Competitors seen: {len(items)}",
                "",
                "Strong titles:",
                *(f"- {title}" for title in strongest),
                "",
                "Weak spots:",
                *(f"- {title}: {', '.join(values)}" for title, values in list(spots.items())[:8]),
                "",
                "Differentiation:",
                *(f"- {item}" for item in diff),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n", summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None, help="Market scan JSON. Defaults to latest data/market/*.json")
    args = parser.parse_args()

    source = Path(args.input) if args.input else latest_file(DATA / "market")
    data = load_json(source)
    markdown, summary = build_report(data)
    ensure_dir(REPORTS)
    report_path = REPORTS / "competitors.md"
    report_path.write_text(markdown, encoding="utf-8")
    write_json(DATA / "competitors" / f"{today_slug()}.json", summary)
    print(report_path)


if __name__ == "__main__":
    main()
