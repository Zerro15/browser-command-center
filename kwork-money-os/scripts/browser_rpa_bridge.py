#!/usr/bin/env python3
"""Safe visible-browser RPA helpers for Kwork.

This module uses Playwright with a persistent headed browser profile. It never
clicks publish, moderation, send, delete, or profile-save buttons.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from _common import CONFIG, DATA, REPORTS, ROOT, ensure_dir, load_json, load_yaml, require_manual_approval


PROFILE_DIR = ROOT / ".browser-profile"
SCREENSHOT_DIR = REPORTS / "screenshots"
REPORT_PATH = REPORTS / "browser_fill_report.md"
AUTOPILOT_REPORT_PATH = REPORTS / "autopilot_report.md"
KWORK_HOME_URL = "https://kwork.ru/"
DEFAULT_DRAFT_URL = "https://kwork.ru/new"
DEFAULT_PROFILE_URL = "https://kwork.ru/settings"
LOGIN_REQUIRED_MESSAGE = "Войдите вручную в открытом браузере"
LOGIN_UNKNOWN_MESSAGE = "Не удалось определить вход в Kwork; поля не заполнялись"
PLAYWRIGHT_INSTALL_COMMAND = (
    "python -m venv .venv && "
    ".venv/bin/python -m pip install playwright && "
    ".venv/bin/python -m playwright install chromium"
)
os.environ.setdefault("PW_TEST_SCREENSHOT_NO_FONTS_READY", "1")
BLOCKED_BUTTON_RE = re.compile(
    r"опубликовать|на модерацию|сохранить|submit|send|publish|delete|"
    r"отправить сообщение|отправить|удалить|принять заказ|отменить заказ|подтвердить действие",
    re.I,
)
SENSITIVE_FIELD_RE = re.compile(r"cookie|token|csrf|password|passwd|secret|session", re.I)


@dataclass
class RpaReport:
    mode: str
    target_url: str
    title: str = "Browser Fill Report"
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    warnings: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    fields_seen: list[str] = field(default_factory=list)
    value_hashes: dict[str, str] = field(default_factory=dict)
    browser_opened: bool = False
    current_url: str = ""
    login_detected: str = "unknown"
    next_safe_command: str = ""

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def action(self, message: str) -> None:
        self.actions.append(message)

    def hash_value(self, name: str, value: Any) -> None:
        text = "" if value is None else str(value)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.value_hashes[name] = f"sha256:{digest} len:{len(text)}"

    def write(self, path: Path = REPORT_PATH) -> None:
        ensure_dir(path.parent)
        lines = [
            f"# {self.title}",
            "",
            f"Mode: `{self.mode}`",
            f"Target URL: `{self.target_url}`",
            f"browser_opened: `{str(self.browser_opened).lower()}`",
            f"current_url: `{self.current_url or 'unknown'}`",
            f"login_detected: `{self.login_detected}`",
            f"next_safe_command: `{self.next_safe_command or 'none'}`",
            f"Started at: `{self.started_at}`",
            "",
            "## Actions",
            *(f"- {item}" for item in self.actions),
            "",
            "## Warnings",
            *(f"- {item}" for item in self.warnings),
            "",
            "## Screenshots",
            *(f"- `{item}`" for item in self.screenshots),
            "",
            "## Fields Seen",
            *(f"- {item}" for item in self.fields_seen[:80]),
            "",
            "## Value Hashes",
            *(f"- {name}: `{digest}`" for name, digest in self.value_hashes.items()),
            "",
            "## Safety",
            "- Passwords, cookies, tokens, and client messages are not written by this report.",
            "- Publish/send/save-profile buttons are never clicked by this bridge.",
        ]
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        tmp_path.replace(path)


def load_offer(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return load_json(path)
    text = path.read_text(encoding="utf-8")
    return {
        "service_id": path.stem,
        "title": first_heading(text) or path.stem,
        "short_description": section(text, "Short Description"),
        "full_description": section(text, "Full Description"),
        "extras": list_from_section(text, "Extras"),
        "buyer_questions": list_from_section(text, "Buyer Questions"),
        "tags": [item.strip() for item in section(text, "Tags").split(",") if item.strip()],
    }


def load_profile(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return load_json(path)
    text = path.read_text(encoding="utf-8")
    return {
        "positioning": section(text, "Positioning"),
        "about": section(text, "About"),
        "services": list_from_section(text, "Services"),
        "trust": list_from_section(text, "Why Trust"),
        "tech_stack": [item.strip() for item in section(text, "Tech Stack").split(",") if item.strip()],
    }


def first_heading(text: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else None


def section(text: str, name: str) -> str:
    pattern = rf"^##\s+{re.escape(name)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, re.M)
    return match.group(1).strip() if match else ""


def list_from_section(text: str, name: str) -> list[str]:
    return [
        line.strip()[2:].strip()
        for line in section(text, name).splitlines()
        if line.strip().startswith("- ")
    ]


def compact(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return "" if value is None else str(value)


def load_selectors() -> dict[str, Any]:
    return load_yaml(CONFIG / "selectors.yaml")


def load_approval_gates() -> dict[str, Any]:
    return load_yaml(CONFIG / "approval_gates.yaml")


def write_plan(path: Path, plan: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    safe_plan = {
        **plan,
        "values": {
            key: f"sha256:{hashlib.sha256(compact(value).encode('utf-8')).hexdigest()} len:{len(compact(value))}"
            for key, value in plan.get("values", {}).items()
        },
    }
    path.write_text(yaml.safe_dump(safe_plan, allow_unicode=True, sort_keys=False), encoding="utf-8")


def import_playwright(report: RpaReport):
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        return sync_playwright, PlaywrightTimeoutError
    except Exception as error:  # pragma: no cover - environment dependent
        message = (
            "Playwright не установлен или недоступен. Установите его через .venv: "
            f"{PLAYWRIGHT_INSTALL_COMMAND}. Исходная ошибка: {error}"
        )
        report.warn(message)
        report.next_safe_command = PLAYWRIGHT_INSTALL_COMMAND
        report.write()
        raise SystemExit(message)


class KworkRpaBridge:
    def __init__(self, report: RpaReport, selectors: dict[str, Any] | None = None):
        self.report = report
        self.selectors = selectors or load_selectors()
        self.sync_playwright = None
        self.timeout_error = Exception
        self.playwright = None
        self.context = None
        self.page = None
        self.stopped = False

    def __enter__(self):
        sync_playwright, timeout_error = import_playwright(self.report)
        if not sync_playwright:
            return self
        self.sync_playwright = sync_playwright
        self.timeout_error = timeout_error
        self.playwright = sync_playwright().start()
        ensure_dir(PROFILE_DIR)
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1440, "height": 1000},
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.report.browser_opened = True
            self.report.current_url = self.page.url
            self.report.action(f"opened visible Chromium persistent profile: {PROFILE_DIR}")
        except Exception as error:
            self.report.warn(f"Unable to open headed Playwright browser: {error}")
            self.playwright.stop()
            self.playwright = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

    @property
    def available(self) -> bool:
        return self.page is not None

    def hold_open(self) -> None:
        if not self.available:
            return
        print("Браузер оставлен открытым для проверки. Нажмите Enter в терминале, чтобы закрыть.")
        input()

    def open(self, url: str) -> None:
        if not self.available:
            return
        try:
            self.page.goto(url, wait_until="commit", timeout=15_000)
            self.page.wait_for_timeout(1200)
            self.report.current_url = self.page.url
            self.report.action(f"opened page: {self.page.url}")
        except Exception as error:
            self.report.warn(f"Unable to open page: {error}")
            try:
                self.report.current_url = self.page.url
            except Exception:
                pass

    def screenshot(self, name: str) -> None:
        if not self.available:
            return
        ensure_dir(SCREENSHOT_DIR)
        path = SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True, timeout=15_000)
            self.report.screenshots.append(str(path.relative_to(ROOT)))
        except Exception as error:
            self.report.warn(f"Unable to take screenshot {name}: {error}")
            self._screenshot_cdp(path, name)

    def _screenshot_cdp(self, path: Path, name: str) -> None:
        if not self.context or not self.page:
            return
        try:
            client = self.context.new_cdp_session(self.page)
            result = client.send(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": False},
            )
            path.write_bytes(base64.b64decode(result["data"]))
            self.report.screenshots.append(str(path.relative_to(ROOT)))
            self.report.action(f"captured {name} screenshot via CDP fallback")
        except Exception as error:
            self.report.warn(f"Unable to take CDP fallback screenshot {name}: {error}")

    def collect_fields(self) -> None:
        if not self.available:
            return
        try:
            self.page.set_default_timeout(2000)
            fields = self.page.locator("input, textarea, select, [contenteditable='true']")
            count = min(fields.count(), 100)
        except Exception as error:
            self.report.warn(f"Unable to inspect fields: {error}")
            return
        seen = []
        for index in range(count):
            item = fields.nth(index)
            try:
                label = item.evaluate(
                    """(el) => {
                      const label = el.labels && el.labels[0] ? el.labels[0].innerText : '';
                      return [label, el.getAttribute('name'), el.id, el.getAttribute('placeholder'), el.getAttribute('aria-label')]
                        .filter(Boolean).join(' | ').replace(/\\s+/g, ' ').trim();
                    }"""
                )
                if label and not SENSITIVE_FIELD_RE.search(label):
                    seen.append(label[:180])
            except Exception:
                continue
        self.report.fields_seen = sorted(set(seen))

    def detect_login_state(self) -> bool | None:
        if not self.available:
            self.report.login_detected = "unknown"
            return None
        try:
            url = self.page.url.lower()
            self.report.current_url = self.page.url
            if "login" in url or "signin" in url:
                self.report.login_detected = "false"
                return False
            state = self.page.evaluate(
                """() => {
                  const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                  };
                  const visible = (selector) => Array.from(document.querySelectorAll(selector)).some(isVisible);
                  if (visible('input[type="password"]')) return false;
                  const loggedInSelectors = [
                    'a[href*="/logout"]',
                    'a[href*="/inbox"]',
                    'a[href*="/manage_orders"]',
                    'a[href*="/manage_kworks"]',
                    'a[href*="/settings"]'
                  ];
                  if (loggedInSelectors.some(visible)) return true;
                  const text = document.body ? document.body.innerText : '';
                  if (/(Войти|Регистрация|Зарегистрироваться)/i.test(text)) return false;
                  if (/(Сообщения|Заказы|Мои кворки|Баланс|Профиль)/i.test(text)) return true;
                  return null;
                }"""
            )
            if state is True:
                self.report.login_detected = "true"
                return True
            if state is False:
                self.report.login_detected = "false"
                return False
            self.report.login_detected = "unknown"
            return None
        except Exception as error:
            self.report.warn(f"Unable to determine login state: {error}")
            self.report.login_detected = "unknown"
            return None

    def is_login_required(self) -> bool:
        return self.detect_login_state() is False

    def ensure_logged_in_or_stop(self) -> bool:
        state = self.detect_login_state()
        if state is False:
            self.report.warn(LOGIN_REQUIRED_MESSAGE)
            print(LOGIN_REQUIRED_MESSAGE)
            if sys.stdin.isatty():
                input("После входа нажмите Enter, чтобы продолжить безопасную проверку...")
                state = self.detect_login_state()
                return state is True
            return False
        if state is None:
            self.report.warn(LOGIN_UNKNOWN_MESSAGE)
            return False
        return True

    def find_blocked_buttons(self) -> list[str]:
        if not self.available:
            return []
        try:
            self.page.set_default_timeout(2000)
            buttons = self.page.locator("button, input[type='submit'], a, [role='button']")
            count = min(buttons.count(), 150)
        except Exception as error:
            self.report.warn(f"Unable to inspect action buttons: {error}")
            return []
        labels = []
        for index in range(count):
            try:
                text = buttons.nth(index).inner_text(timeout=250).strip()
            except Exception:
                text = ""
            if text and BLOCKED_BUTTON_RE.search(text):
                labels.append(text[:80])
        return sorted(set(labels))

    def blocked_texts(self) -> list[str]:
        cfg = self.selectors.get("kwork", {})
        values = []
        values.extend(cfg.get("blocked_buttons", []))
        values.extend(cfg.get("publish_buttons", []))
        return sorted({str(item).strip() for item in values if str(item).strip()})

    def assert_no_blocked_click(self, text: str) -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        lower_value = value.lower()
        for blocked in self.blocked_texts():
            if blocked.lower() in lower_value or lower_value in blocked.lower():
                self.report.warn(f"blocked click skipped: {value}")
                return False
        if BLOCKED_BUTTON_RE.search(value):
            self.report.warn(f"blocked click skipped: {value}")
            return False
        return True

    def _find_click_target(self, text: str) -> dict[str, Any]:
        if not self.available:
            return {"count": 0}
        return self.page.evaluate(
            """(text) => {
              const wanted = text.trim().toLowerCase();
              const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const labelOf = (el) => (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '')
                .replace(/\\s+/g, ' ').trim();
              const all = Array.from(document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"]'))
                .filter(isVisible)
                .map((el) => ({el, label: labelOf(el)}))
                .filter((item) => item.label && item.label.toLowerCase().includes(wanted));
              const exact = all.filter((item) => item.label.toLowerCase() === wanted);
              const matches = exact.length ? exact : all;
              if (matches.length !== 1) return {count: matches.length, labels: matches.slice(0, 5).map((item) => item.label)};
              const id = `autopilot-${Date.now()}-${Math.random().toString(16).slice(2)}`;
              matches[0].el.setAttribute('data-autopilot-click-id', id);
              return {count: 1, id, label: matches[0].label};
            }""",
            text,
        )

    def click_text_safe(self, text_candidates: list[str] | tuple[str, ...] | str) -> bool:
        candidates = [text_candidates] if isinstance(text_candidates, str) else list(text_candidates)
        for text in candidates:
            if not self.assert_no_blocked_click(text):
                continue
            try:
                target = self._find_click_target(text)
                count = int(target.get("count") or 0)
                if count > 1:
                    self.report.warn(f"ambiguous click skipped for '{text}': {target.get('labels', [])}")
                    return False
                if count == 0:
                    continue
                before_url = self.page.url
                self.page.locator(f"[data-autopilot-click-id='{target['id']}']").click(timeout=2000)
                self.page.wait_for_timeout(800)
                self.report.current_url = self.page.url
                self.report.action(f"clicked text safely: {target.get('label', text)}")
                if self.page.url and "kwork.ru" not in self.page.url:
                    self.report.warn(f"unexpected navigation after click: {before_url} -> {self.page.url}")
                    self.stopped = True
                    return False
                return True
            except Exception as error:
                self.report.warn(f"safe text click failed for '{text}': {error}")
                return False
        self.report.warn(f"safe text click target not found: {', '.join(str(item) for item in candidates)}")
        return False

    def click_role_safe(self, role: str, name_candidates: list[str] | tuple[str, ...] | str) -> bool:
        candidates = [name_candidates] if isinstance(name_candidates, str) else list(name_candidates)
        for name in candidates:
            if not self.assert_no_blocked_click(name):
                continue
            try:
                locator = self.page.get_by_role(role, name=re.compile(re.escape(str(name)), re.I))
                count = locator.count()
                if count > 1:
                    self.report.warn(f"ambiguous role click skipped for {role} '{name}': {count} matches")
                    return False
                if count == 0:
                    continue
                before_url = self.page.url
                locator.first.click(timeout=2000)
                self.page.wait_for_timeout(800)
                self.report.current_url = self.page.url
                self.report.action(f"clicked role safely: {role} {name}")
                if self.page.url and "kwork.ru" not in self.page.url:
                    self.report.warn(f"unexpected navigation after role click: {before_url} -> {self.page.url}")
                    self.stopped = True
                    return False
                return True
            except Exception as error:
                self.report.warn(f"safe role click failed for {role} '{name}': {error}")
                return False
        self.report.warn(f"safe role click target not found: {role} {candidates}")
        return False

    def close_popups_safe(self) -> None:
        cfg = self.selectors.get("kwork", {})
        for text in cfg.get("safe_cookie_buttons", []):
            if self.click_text_safe(str(text)):
                self.report.action(f"closed popup/banner via safe text: {text}")

    def choose_category_safe(self, category: str, subcategory_candidates: list[str]) -> bool:
        selected = False
        if category:
            selected = self.click_text_safe(category)
            if selected:
                self.page.wait_for_timeout(500)
        sub_selected = self.click_text_safe(subcategory_candidates)
        if not selected:
            self.report.warn(f"category not selected: {category}")
        if not sub_selected:
            self.report.warn(f"subcategory not selected: {', '.join(subcategory_candidates)}")
        return bool(selected or sub_selected)

    def wait_and_screenshot(self, name: str) -> None:
        if self.available:
            self.page.wait_for_timeout(1000)
        self.screenshot(name)

    def fill_text(self, field_name: str, value: Any, hints: list[str], selectors: list[str] | None = None, required: bool = False) -> bool:
        text = compact(value)
        self.report.hash_value(field_name, text)
        if not text:
            self.report.warn(f"empty value skipped: {field_name}")
            return False
        if not self.available:
            return False

        for hint in hints:
            if self._try_fill_locator(self.page.get_by_label(re.compile(re.escape(hint), re.I)), text, field_name, f"label:{hint}"):
                return True
            if self._try_fill_locator(self.page.get_by_placeholder(re.compile(re.escape(hint), re.I)), text, field_name, f"placeholder:{hint}"):
                return True
            if self._try_fill_hint_js(hint, text, field_name):
                return True

        for selector in selectors or []:
            if self._try_fill_locator(self.page.locator(selector).first, text, field_name, f"selector:{selector}"):
                return True

        message = f"field not found: {field_name}"
        if required:
            self.report.warn(f"required {message}")
        else:
            self.report.warn(message)
        return False

    def _try_fill_locator(self, locator, text: str, field_name: str, source: str) -> bool:
        try:
            if locator.count() < 1:
                return False
            target = locator.first
            target.scroll_into_view_if_needed(timeout=1000)
            target.fill(text, timeout=1500)
            self.report.action(f"filled {field_name} via {source} ({len(text)} chars)")
            return True
        except Exception:
            return False

    def _try_fill_hint_js(self, hint: str, text: str, field_name: str) -> bool:
        try:
            result = self.page.evaluate(
                """({hint, text}) => {
                  const wanted = hint.toLowerCase();
                  const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                  };
                  const labelOf = (el) => {
                    if (el.labels && el.labels.length) return Array.from(el.labels).map((x) => x.innerText).join(' ');
                    if (el.id) {
                      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                      if (label) return label.innerText;
                    }
                    return '';
                  };
                  const fields = Array.from(document.querySelectorAll('input,textarea,select,[contenteditable="true"]')).filter(visible);
                  const found = fields.find((el) => [labelOf(el), el.name, el.id, el.placeholder, el.getAttribute('aria-label')]
                    .filter(Boolean).join(' ').toLowerCase().includes(wanted));
                  if (!found) return false;
                  found.scrollIntoView({block: 'center'});
                  found.focus();
                  if (found.isContentEditable) found.innerText = text;
                  else found.value = text;
                  found.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
                  found.dispatchEvent(new Event('change', {bubbles: true}));
                  return true;
                }""",
                {"hint": hint, "text": text},
            )
            if result:
                self.report.action(f"filled {field_name} via hint-js:{hint} ({len(text)} chars)")
                return True
        except Exception:
            return False
        return False

    def upload_file(self, field_name: str, file_path: Path, selectors: list[str]) -> bool:
        self.report.hash_value(field_name, str(file_path))
        if not file_path.exists():
            self.report.warn(f"file not found: {file_path}")
            return False
        if not self.available:
            return False
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if locator.count() < 1:
                    continue
                locator.set_input_files(str(file_path), timeout=2000)
                self.report.action(f"uploaded {field_name} via {selector}")
                return True
            except Exception:
                continue
        self.report.warn(f"file input not found: {field_name}")
        return False


def package_text(package: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Цена от: {package.get('price_from', '')}",
            f"Срок: {package.get('days', '')} дн.",
            "Состав:",
            *[f"- {item}" for item in package.get("includes", [])],
        ]
    ).strip()


def faq_text(items: list[dict[str, Any]]) -> str:
    lines = []
    for item in items:
        lines.append(f"Q: {item.get('q', '')}\nA: {item.get('a', '')}")
    return "\n\n".join(lines)


def build_offer_values(offer: dict[str, Any]) -> dict[str, Any]:
    packages = offer.get("packages") or {}
    return {
        "title": offer.get("title", ""),
        "short_description": offer.get("short_description", ""),
        "full_description": offer.get("full_description", ""),
        "package_economy": package_text(packages.get("economy", {})),
        "package_standard": package_text(packages.get("standard", {})),
        "package_business": package_text(packages.get("business", {})),
        "extras": "\n".join(f"- {item}" for item in offer.get("extras", [])),
        "faq": faq_text(offer.get("FAQ", [])),
        "buyer_questions": "\n".join(f"- {item}" for item in offer.get("buyer_questions", [])),
        "tags": ", ".join(offer.get("tags", [])),
    }


def fill_offer_fields(bridge: KworkRpaBridge, offer: dict[str, Any], banner: Path | None = None) -> None:
    values = build_offer_values(offer)
    cfg = bridge.selectors.get("kwork", {})
    fields = cfg.get("fields", {})
    bridge.fill_text("title", values["title"], cfg.get("title_hints", []), fields.get("title", []), required=True)
    bridge.fill_text("short_description", values["short_description"], cfg.get("short_description_hints", []), fields.get("short_description", []))
    bridge.fill_text("full_description", values["full_description"], cfg.get("description_hints", []), fields.get("full_description", []), required=True)
    package_hints = cfg.get("package_hints", {})
    for key in ("economy", "standard", "business"):
        bridge.fill_text(f"package_{key}", values[f"package_{key}"], package_hints.get(key, []), fields.get(f"package_{key}", []))
    bridge.fill_text("extras", values["extras"], cfg.get("extras_hints", []), fields.get("extras", []))
    bridge.fill_text("faq", values["faq"], cfg.get("faq_hints", []), fields.get("faq", []))
    bridge.fill_text("buyer_questions", values["buyer_questions"], cfg.get("buyer_questions_hints", []), fields.get("buyer_questions", []))
    bridge.fill_text("tags", values["tags"], cfg.get("tags_hints", []), fields.get("tags", []))
    if banner:
        bridge.upload_file("cover", banner, list((cfg.get("file_inputs") or {}).values()))


def fill_profile_fields(bridge: KworkRpaBridge, profile: dict[str, Any]) -> None:
    cfg = bridge.selectors.get("profile", {})
    fields = cfg.get("fields", {})
    bridge.fill_text("positioning", profile.get("positioning", ""), cfg.get("positioning_hints", []), fields.get("positioning", []))
    bridge.fill_text("about", profile.get("about", ""), cfg.get("about_hints", []), fields.get("about", []), required=True)
    bridge.fill_text("services", "\n".join(profile.get("services", [])), cfg.get("services_hints", []), fields.get("services", []))
    bridge.fill_text("trust", "\n".join(profile.get("trust", [])), cfg.get("trust_hints", []), fields.get("trust", []))
    bridge.fill_text("tech_stack", ", ".join(profile.get("tech_stack", [])), cfg.get("tech_stack_hints", []), fields.get("tech_stack", []))


def run_draft(args: argparse.Namespace) -> None:
    offer_path = Path(args.offer)
    offer = load_offer(offer_path)
    banner = Path(args.banner) if args.banner else None
    draft_url = args.draft_url or DEFAULT_DRAFT_URL
    values = build_offer_values(offer)

    plan_path = DATA / "offers" / f"{offer_path.stem}.rpa-plan.yaml"
    if args.mode == "dry-run":
        write_plan(
            plan_path,
            {
                "mode": args.mode,
                "target_url": draft_url,
                "offer": str(offer_path),
                "banner": str(banner) if banner else None,
                "values": values,
            },
        )
        print(plan_path)
        return

    url = KWORK_HOME_URL if args.mode == "preview" else draft_url
    report = RpaReport(mode=args.mode, target_url=url)
    for key, value in values.items():
        report.hash_value(key, value)

    if args.mode == "fill-draft":
        require_manual_approval("Kwork draft filling", args.approve)

    with KworkRpaBridge(report) as bridge:
        bridge.open(url)
        bridge.screenshot("draft-before")
        bridge.collect_fields()
        login_ok = bridge.ensure_logged_in_or_stop()
        if args.mode == "preview":
            if login_ok:
                report.next_safe_command = (
                    f"python scripts/fill_kwork_draft.py --offer {offer_path} --fill-draft --approve"
                )
            else:
                report.next_safe_command = f"python scripts/fill_kwork_draft.py --offer {offer_path} --preview"
                bridge.write_stop_report()
        elif login_ok:
            fill_offer_fields(bridge, offer, banner)
            bridge.screenshot("draft-after")
            report.next_safe_command = "manual review in visible browser; automation will not save or publish"
        else:
            report.next_safe_command = f"python scripts/fill_kwork_draft.py --offer {offer_path} --preview"
            bridge.write_stop_report()
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        report.write()
        print(REPORT_PATH)
        if getattr(args, "hold", False):
            bridge.hold_open()
    if args.mode == "fill-draft":
        print("Проверь и нажми сам")


def run_profile(args: argparse.Namespace) -> None:
    profile_path = Path(args.profile)
    profile = load_profile(profile_path)
    url = args.profile_url or DEFAULT_PROFILE_URL
    report = RpaReport(mode=args.mode, target_url=url)
    for key in ("positioning", "about", "services", "trust", "tech_stack"):
        report.hash_value(key, profile.get(key, ""))
    plan_path = DATA / "profile" / f"{profile_path.stem}.rpa-plan.yaml"
    if args.mode == "dry-run":
        write_plan(plan_path, {"mode": args.mode, "target_url": url, "profile": str(profile_path), "values": profile})
        report.write()
        print(plan_path)
        print(REPORT_PATH)
        return

    if args.mode == "fill-profile":
        require_manual_approval("Kwork profile filling", args.approve)

    with KworkRpaBridge(report) as bridge:
        bridge.open(url)
        bridge.screenshot("profile-before")
        bridge.collect_fields()
        login_ok = bridge.ensure_logged_in_or_stop()
        if not login_ok:
            bridge.write_stop_report()
        if args.mode == "fill-profile" and login_ok:
            fill_profile_fields(bridge, profile)
            bridge.screenshot("profile-after")
        blocked = bridge.find_blocked_buttons()
        if blocked:
            report.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
        report.write()
        print(REPORT_PATH)
        if getattr(args, "hold", False):
            bridge.hold_open()
    if args.mode == "fill-profile":
        print("Проверь и нажми сам")


def _write_stop_report(self: KworkRpaBridge) -> None:
    self.screenshot("login-required")
    self.report.write()


KworkRpaBridge.write_stop_report = _write_stop_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["draft", "profile"], required=True)
    parser.add_argument("--mode", choices=["dry-run", "preview", "fill-draft", "fill-profile"], required=True)
    parser.add_argument("--offer")
    parser.add_argument("--profile")
    parser.add_argument("--draft-url")
    parser.add_argument("--profile-url")
    parser.add_argument("--banner")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()

    if args.target == "draft":
        if not args.offer:
            raise SystemExit("--offer is required for draft target")
        run_draft(args)
    else:
        if not args.profile:
            raise SystemExit("--profile is required for profile target")
        run_profile(args)


if __name__ == "__main__":
    main()
