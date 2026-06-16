#!/usr/bin/env python3
"""Marketing QA for Kwork Production Studio artifacts."""

from __future__ import annotations

from kwork_studio_common import (
    COMPETITORS_JSON,
    COVER_SCORES,
    FULL_FILL_REPORT,
    MARKETING_QA_REPORT,
    SPEC_JSON,
    ensure_studio_dirs,
    read_json,
    write_text,
)


def report_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def score_spec(spec: dict, cover: dict, competitors: dict, fill_text: str) -> tuple[int, str, list[str]]:
    checks = []
    score = 0
    title = spec.get("title", "")
    description = spec.get("description", "")
    packages = spec.get("packages", {})
    faq = spec.get("faq", [])
    questions = spec.get("buyer_questions", [])
    tags = spec.get("tags", [])

    def add(name: str, ok: bool, points: int):
        nonlocal score
        checks.append(f"{name}: {'ok' if ok else 'missing'} (+{points if ok else 0})")
        if ok:
            score += points

    add("title readable", 25 <= len(title) <= 80, 10)
    add("title concrete result", "заяв" in title.lower() and "таблиц" in title.lower(), 10)
    add("DevOps усиление", any(word in (description + " ".join(tags)).lower() for word in ["docker", "linux", ".env", "deploy", "запуск"]), 12)
    add("safe promises", not any(word in description.lower() for word in ["100%", "обход", "накрут", "спам"]), 10)
    add("packages complete", all(key in packages for key in ["basic", "standard", "premium"]), 12)
    add("FAQ present", len(faq) >= 3, 8)
    add("buyer questions present", len(questions) >= 3, 8)
    add("cover score", int((cover.get("scores") or [{}])[0].get("total_score", 0)) >= 80, 10)
    add("competitor differentiation", bool((competitors.get("what_to_do_better") or [])), 8)
    add("fill has title/description", "title" in fill_text and "description" in fill_text, 8)
    add("pricing sane", packages.get("basic", {}).get("price", 0) >= 2500 and packages.get("premium", {}).get("price", 0) <= 9000, 4)

    if score >= 86:
        verdict = "READY_FOR_HUMAN_REVIEW"
    elif score >= 72 and not (cover.get("scores") or []):
        verdict = "NEEDS_BETTER_COVER"
    elif score >= 72:
        verdict = "NEEDS_BETTER_POSITIONING"
    elif "fields_missing: `none`" not in fill_text and fill_text:
        verdict = "MISSING_REQUIRED_FIELDS"
    else:
        verdict = "DO_NOT_SUBMIT"
    return min(score, 100), verdict, checks


def main() -> None:
    ensure_studio_dirs()
    spec = read_json(SPEC_JSON, {})
    cover = read_json(COVER_SCORES, {})
    competitors = read_json(COMPETITORS_JSON, {})
    fill = report_text(FULL_FILL_REPORT)
    score, verdict, checks = score_spec(spec, cover, competitors, fill)
    lines = [
        "# Kwork Marketing QA Report",
        "",
        f"- score: `{score}`",
        f"- verdict: `{verdict}`",
        f"- selected_title: `{spec.get('title', 'unknown')}`",
        f"- selected_cover: `{cover.get('selected_cover', 'unknown')}`",
        f"- competitors_count: `{competitors.get('competitors_count', 0)}`",
        f"- can_submit_to_moderation: `manual human decision only`",
        f"- next_manual_step: `Проверь страницу, обложку, пакеты и вопросы глазами. Только пользователь решает, сохранять или отправлять на модерацию.`",
        "",
        "## Checklist",
        *(f"- {item}" for item in checks),
        "",
        "## Safety",
        "- QA is offline/read-only and does not click Kwork buttons.",
    ]
    write_text(MARKETING_QA_REPORT, "\n".join(lines))
    print(MARKETING_QA_REPORT)
    print(f"score={score}")
    print(f"verdict={verdict}")


if __name__ == "__main__":
    main()
