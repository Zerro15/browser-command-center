#!/usr/bin/env python3
"""Shared safe helpers for Kwork account optimization scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from _common import DATA, REPORTS, ROOT, SERVICES, ensure_dir, load_json, load_yaml, write_json
from browser_rpa_bridge import KWORK_HOME_URL, KworkRpaBridge, RpaReport


PROFILE_SETTINGS_URL = "https://kwork.ru/settings"
SELLER_PROFILE_URL = "https://kwork.ru/user/ZerroOne"
MANAGE_KWORKS_URL = "https://kwork.ru/manage_kworks"
DRAFT_KWORKS_URL = "https://kwork.ru/manage_kworks?status=draft"
PORTFOLIO_URL = "https://kwork.ru/portfolio"
INBOX_URL = "https://kwork.ru/inbox"
PROJECTS_URL = "https://kwork.ru/projects"
ORDERS_URL = "https://kwork.ru/manage_orders"

FINAL_ACTION_WORDS = (
    "Опубликовать",
    "На модерацию",
    "Отправить",
    "Отправить сообщение",
    "Сохранить профиль",
    "Удалить",
    "Принять заказ",
    "Отменить заказ",
    "Подтвердить действие",
)

SECRET_PATTERNS = [
    re.compile(r"(?i)(cookie|token|password|passwd|secret|csrf|session)[\w-]*\s*[:=]\s*\S+"),
    re.compile(r"(?i)(bearer|basic)\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\+?\d[\d\s().-]{8,}\d"),
]


@dataclass
class PageSnapshot:
    name: str
    url: str
    title: str = ""
    text_summary: str = ""
    fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_mode(args: argparse.Namespace) -> str:
    selected = [args.dry_run, args.preview, args.run]
    if sum(bool(item) for item in selected) != 1:
        raise SystemExit("Choose exactly one mode: --dry-run, --preview, or --run")
    return "dry-run" if args.dry_run else "preview" if args.preview else "run"


def add_mode_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")


def require_run_approval(mode: str, approved: bool, action: str) -> None:
    if mode == "run" and not approved:
        raise SystemExit(f"{action} requires --approve. Final save/send/publish actions are still blocked.")


def redact_text(value: Any, limit: int = 700) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return text


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def load_services() -> list[dict[str, Any]]:
    services = []
    for path in sorted(SERVICES.glob("*.yaml")):
        item = load_yaml(path)
        item["_path"] = str(path.relative_to(ROOT))
        item.setdefault("id", path.stem)
        services.append(item)
    return services


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return load_json(path)


def write_markdown(path: Path, lines: list[str]) -> None:
    ensure_dir(path.parent)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_yaml_file(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def append_safety_section(lines: list[str]) -> None:
    lines.extend(
        [
            "",
            "## Safety",
            "- Финальные кнопки save/publish/send/submit/delete не нажимались.",
            "- Cookies, tokens, passwords, env/state/private data не записываются в отчёт.",
            "- Сообщения клиентов сохраняются только как redacted summaries, без полного текста.",
            "- Если login_detected не true или состояние неизвестно, browser-скрипт останавливается.",
        ]
    )


def build_plan_report(path: Path, title: str, mode: str, actions: list[str]) -> None:
    lines = [
        f"# {title}",
        "",
        f"Mode: `{mode}`",
        f"Started at: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Planned Actions",
        *(f"- {item}" for item in actions),
    ]
    append_safety_section(lines)
    write_markdown(path, lines)


def strict_login_gate(bridge: KworkRpaBridge, report_path: Path) -> bool:
    state = bridge.detect_login_state()
    if state is True:
        return True
    if state is False:
        bridge.report.warn("login_detected != true; stopped before account inspection")
    else:
        bridge.report.warn("login state is unknown; unsafe stop before account inspection")
    bridge.wait_and_screenshot("login-gate-stop")
    bridge.report.write(report_path)
    return False


def safe_page_snapshot(bridge: KworkRpaBridge, name: str, url: str) -> PageSnapshot:
    snapshot = PageSnapshot(name=name, url=url)
    bridge.open(url)
    if not bridge.available:
        snapshot.warnings.append("browser unavailable")
        return snapshot
    try:
        bridge.close_popups_safe()
        bridge.collect_fields()
        snapshot.fields = bridge.report.fields_seen[:80]
        snapshot.title = redact_text(bridge.page.title(), 160)
        raw = bridge.page.evaluate(
            """() => {
              const blockedSelectors = [
                'script', 'style', 'noscript', 'input[type="password"]',
                '[data-token]', '[data-session]', '[name*="token" i]',
                '[name*="password" i]', '[name*="csrf" i]'
              ];
              const clone = document.body ? document.body.cloneNode(true) : document.createElement('body');
              blockedSelectors.forEach((selector) => clone.querySelectorAll(selector).forEach((el) => el.remove()));
              return (clone.innerText || '').replace(/\\s+/g, ' ').trim();
            }"""
        )
        snapshot.text_summary = redact_text(raw, 900)
        blocked = bridge.find_blocked_buttons()
        if blocked:
            snapshot.warnings.append(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
    except Exception as error:
        snapshot.warnings.append(f"snapshot failed: {error}")
    bridge.wait_and_screenshot(name)
    return snapshot


def extract_cards_from_page(bridge: KworkRpaBridge, max_items: int = 20) -> list[dict[str, str]]:
    if not bridge.available:
        return []
    try:
        raw_items = bridge.page.evaluate(
            """(maxItems) => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const candidates = Array.from(document.querySelectorAll('article, .card, .js-kwork-card, .kwork-card, .order-card, .project-card, li, tr'))
                .filter(visible)
                .map((el) => (el.innerText || '').replace(/\\s+/g, ' ').trim())
                .filter((text) => text.length > 30)
                .slice(0, maxItems);
              return candidates;
            }""",
            max_items,
        )
    except Exception:
        return []
    items = []
    for text in raw_items:
        summary = redact_text(text, 420)
        items.append({"id": stable_id("item", summary), "summary": summary})
    return items


def write_json_output(path: Path, value: Any) -> None:
    write_json(path, value)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
