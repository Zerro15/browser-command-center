#!/usr/bin/env python3
"""Run pragmatic QA checks on a generated offer."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import REPORTS, ensure_dir, load_json


def load_offer(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return load_json(path), text
    title = re.search(r"^#\s+(.+)$", text, re.M)
    return {"title": title.group(1) if title else "", "raw": text}, text


def check(path: Path) -> tuple[list[str], list[str]]:
    offer, text = load_offer(path)
    title = offer.get("title", "")
    errors = []
    warnings = []

    if len(title) > 70:
        warnings.append("title длиннее 70 символов")
    if not re.search(r"результат|получ|рабоч|запуска|готов", text, re.I):
        errors.append("нет понятного результата для клиента")
    if not re.search(r"What Included|what_included|base_scope|Входит|входит", text, re.I):
        errors.append("не описан базовый объем")
    if not re.search(r"What Not Included|what_not_included|not_included|не входит|огранич", text, re.I):
        errors.append("нет ограничений")
    if not re.search(r"Extras|extras|доп", text, re.I):
        errors.append("нет допов")
    if re.search(r"100%\s*(продаж|гарант|результат)|гарантирую продажи|без риска", text, re.I):
        errors.append("есть опасное обещание 100% результата")
    if re.search(r"спам|рассылка без согласия|обход капчи|накрут", text, re.I):
        errors.append("есть риск нарушения правил площадки")
    if re.search(r"price_from:\s*[0-9]{1,3}\b|Цена от:\s*[0-9]{1,3}\b", text):
        warnings.append("цена выглядит слишком низкой")
    if not re.search(r"Buyer Questions|buyer_questions|вопрос", text, re.I):
        errors.append("нет вопросов к клиенту")
    if not re.search(r"Proof|proof|скрин|демо|инструкц|README|лог", text, re.I):
        warnings.append("слабо описано доказательство результата")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("offer")
    args = parser.parse_args()
    path = Path(args.offer)
    errors, warnings = check(path)
    status = "PASS" if not errors else "FAIL"
    lines = [f"# Offer QA: {path.name}", "", f"Status: {status}", ""]
    if errors:
        lines.extend(["## Errors", *(f"- {item}" for item in errors), ""])
    if warnings:
        lines.extend(["## Warnings", *(f"- {item}" for item in warnings), ""])
    if not errors and not warnings:
        lines.append("No issues found.")
    ensure_dir(REPORTS)
    report = REPORTS / f"offer_qa_{path.stem}.md"
    report.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(report)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
