#!/usr/bin/env python3
"""Prepare Kwork Money OS until the manual phone verification stop."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir, load_json
from account_optimizer_common import MANAGE_KWORKS_URL, PROFILE_SETTINGS_URL, SELLER_PROFILE_URL
from browser_rpa_bridge import DEFAULT_DRAFT_URL, KworkRpaBridge, RpaReport, build_offer_values, fill_offer_fields
from fill_profile_optimized import fill_optimized_fields, open_profile_settings_tab
from kwork_autopilot import click_create_kwork_button


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
EXPECTED_USERNAME = "ZerroOne"
PROFILE_PATH = DATA / "profile" / "profile_optimized.json"
OFFER_PATH = DATA / "offers" / "first_money_offer.json"
DELIVERY_DIR = DATA / "delivery" / "first_money_offer"
READY_DIR = DATA / "ready_to_publish" / "first_money_offer"
REPORT_PATH = REPORTS / "pre_phone_setup_report.md"
REPO_ROOT = ROOT.parent

READY_FILES = [
    "01_profile_about.md",
    "02_kwork_title.md",
    "03_kwork_short_description.md",
    "04_kwork_full_description.md",
    "05_packages.md",
    "06_faq.md",
    "07_buyer_questions.md",
    "08_tags.md",
    "09_delivery_checklist.md",
    "10_manual_publish_checklist.md",
    "11_client_first_message_template.md",
    "12_order_start_questions.md",
]

PRIVATE_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\+?\d[\d\s().-]{8,}\d"),
    re.compile(r"(?i)(set-cookie|authorization:|bearer\s+\S+)"),
    re.compile(r"(?i)(password|passwd|secret|session|cookie)\s*[:=]\s*\S+"),
    re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}"),
]


@dataclass
class PrePhoneStatus:
    mode: str
    hold: bool = False
    project_root: str = ""
    git_commit: str = ""
    username_detected: str = "unknown"
    login_detected: str = "unknown"
    profile_prepared: bool = False
    profile_filled_in_browser: bool = False
    first_offer_prepared: bool = False
    first_offer_filled_in_browser: bool = False
    delivery_pack_prepared: bool = False
    ready_to_publish_pack_prepared: bool = False
    phone_verification_detected: bool = False
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    fields_seen: list[str] = field(default_factory=list)

    def action(self, message: str) -> None:
        self.actions.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def validate_root(status: PrePhoneStatus) -> None:
    git_root = Path(run_git(["rev-parse", "--show-toplevel"]))
    status.project_root = str(git_root)
    status.git_commit = run_git(["rev-parse", "HEAD"])
    if git_root != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong git root: {git_root}. Expected: {EXPECTED_REPO_ROOT}")
    if REPO_ROOT != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong script root: {REPO_ROOT}. Expected: {EXPECTED_REPO_ROOT}")
    status.action(f"validated WSL project root: {git_root}")


def require_run_approval(mode: str, approved: bool) -> None:
    if mode == "run" and not approved:
        raise SystemExit("Pre-phone setup --run requires --approve. Final actions remain manual-only.")


def list_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def package_section(name: str, package: dict[str, Any]) -> str:
    includes = package.get("includes", [])
    return "\n".join(
        [
            f"## {name}",
            "",
            f"Цена: от {package.get('price_from')} ₽",
            f"Срок: {package.get('days')} дн.",
            "",
            "Входит:",
            list_lines([str(item) for item in includes]),
        ]
    ).strip()


def faq_section(items: list[dict[str, Any]]) -> str:
    blocks = []
    for item in items:
        blocks.append(f"## {item.get('q', '').strip()}\n\n{item.get('a', '').strip()}".strip())
    return "\n\n".join(blocks)


def profile_about(profile: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "# Profile About",
            profile.get("headline", "").strip(),
            profile.get("about", "").strip(),
            "## Навыки\n\n" + list_lines([str(item) for item in profile.get("skills", [])]),
            "## Как работаю\n\n" + list_lines([str(item) for item in profile.get("trust_blocks", [])]),
            "## Коротко для клиента\n\n" + profile.get("buyer_friendly_description", "").strip(),
            "## Safety\n\nФинальное сохранение профиля выполняется только вручную после проверки текста на странице Kwork.",
        ]
    ).strip() + "\n"


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_ready_to_publish_pack(profile: dict[str, Any], offer: dict[str, Any]) -> list[Path]:
    packages = offer.get("packages") or {}
    faq = offer.get("FAQ") or offer.get("faq") or []
    delivery_checklist = [str(item) for item in offer.get("delivery_checklist", [])]
    buyer_questions = [str(item) for item in offer.get("buyer_questions", [])]
    tags = [str(item) for item in offer.get("tags", [])]
    files = {
        "01_profile_about.md": profile_about(profile),
        "02_kwork_title.md": f"# Kwork Title\n\n{offer.get('title', '').strip()}\n",
        "03_kwork_short_description.md": f"# Kwork Short Description\n\n{offer.get('short_description', '').strip()}\n",
        "04_kwork_full_description.md": f"# Kwork Full Description\n\n{offer.get('full_description', '').strip()}\n",
        "05_packages.md": "\n\n".join(
            [
                "# Packages",
                package_section("Эконом", packages.get("economy", {})),
                package_section("Стандарт", packages.get("standard", {})),
                package_section("Премиум", packages.get("business", {})),
            ]
        ),
        "06_faq.md": "# FAQ\n\n" + faq_section(faq),
        "07_buyer_questions.md": "# Buyer Questions\n\n" + list_lines(buyer_questions),
        "08_tags.md": "# Tags\n\n" + ", ".join(tags),
        "09_delivery_checklist.md": "# Delivery Checklist\n\n" + list_lines(delivery_checklist),
        "10_manual_publish_checklist.md": "\n".join(
            [
                "# Manual Publish Checklist",
                "",
                "- Проверить, что телефон привязан вручную.",
                "- Проверить название, описание, пакеты, FAQ, вопросы покупателю и теги.",
                "- Убедиться, что в тексте нет email, телефона, токенов, cookies и приватных данных.",
                "- Проверить, что не обещаны продажи, обход ограничений, спам или фейковый опыт.",
                "- Нажимать `Сохранить профиль`, `На модерацию` или `Опубликовать` только вручную.",
                "- Не отправлять клиентам сообщения и не принимать заказы через автоматизацию.",
            ]
        ),
        "11_client_first_message_template.md": "\n".join(
            [
                "# Client First Message Template",
                "",
                "Здравствуйте! Спасибо за заказ. Чтобы я сделал бота аккуратно и без лишних переделок, уточните, пожалуйста:",
                "",
                "- какие поля должна собирать заявка;",
                "- кому в Telegram отправлять уведомление;",
                "- нужна ли запись в Google Таблицу;",
                "- каким текстом бот должен отвечать после заявки;",
                "- как будем проверять готовый результат.",
                "",
                "Реальные токены и доступы передавайте только после согласования безопасного способа передачи. В git, screenshots и публичные файлы секреты не добавляются.",
            ]
        ),
        "12_order_start_questions.md": "\n".join(
            [
                "# Order Start Questions",
                "",
                *[f"{index}. {question}" for index, question in enumerate(buyer_questions, start=1)],
                f"{len(buyer_questions) + 1}. Где бот должен запускаться: локально, на VPS или пока только как код с инструкцией?",
                f"{len(buyer_questions) + 2}. Что точно не входит в этот заказ: платежи, CRM, рассылки, сложные интеграции?",
            ]
        ),
    }
    written = []
    for name in READY_FILES:
        path = READY_DIR / name
        write_text(path, files[name])
        written.append(path)
    return written


def assert_public_safe(paths: list[Path]) -> None:
    violations = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(text):
                violations.append(str(path.relative_to(ROOT)))
                break
    if violations:
        raise SystemExit("Public-safe check failed for: " + ", ".join(sorted(set(violations))))


def prepare_offline_materials(status: PrePhoneStatus) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = load_json(PROFILE_PATH) if PROFILE_PATH.exists() else {}
    offer = load_json(OFFER_PATH) if OFFER_PATH.exists() else {}
    status.profile_prepared = bool(profile.get("headline") and profile.get("about"))
    status.first_offer_prepared = bool(offer.get("title") and offer.get("full_description") and offer.get("packages"))
    status.delivery_pack_prepared = DELIVERY_DIR.exists() and any(DELIVERY_DIR.glob("*.md"))
    ready_files = write_ready_to_publish_pack(profile, offer)
    status.ready_to_publish_pack_prepared = all((READY_DIR / name).exists() for name in READY_FILES)
    safe_paths = [OFFER_PATH, *sorted(DELIVERY_DIR.glob("*.md")), *ready_files]
    assert_public_safe(safe_paths)
    status.action(f"prepared public-safe copy-paste pack: {READY_DIR.relative_to(ROOT)}")
    return profile, offer


def extract_username_from_text(text: str) -> str | None:
    if EXPECTED_USERNAME.lower() in text.lower():
        return EXPECTED_USERNAME
    match = re.search(r"/user/([A-Za-z0-9_-]{3,40})", text)
    if match:
        return match.group(1)
    return None


def detect_username_safely(bridge: KworkRpaBridge) -> str:
    if not bridge.available:
        return "unknown"
    try:
        raw = bridge.page.evaluate(
            """() => {
              const parts = [location.href, document.title || ''];
              document.querySelectorAll('a[href*="/user/"], [href*="/user/"]').forEach((el) => {
                parts.push(el.getAttribute('href') || '');
                parts.push((el.innerText || el.textContent || '').trim());
              });
              return parts.join('\\n');
            }"""
        )
        username = extract_username_from_text(str(raw))
        if username:
            return username
    except Exception:
        pass
    return "unknown"


def probe_username_page(bridge: KworkRpaBridge) -> str:
    if not bridge.context or not bridge.available:
        return "unknown"
    profile_page = bridge.page
    bridge.page = bridge.context.new_page()
    try:
        bridge.open(SELLER_PROFILE_URL)
        bridge.wait_and_screenshot("pre-phone-public-profile")
        return detect_username_safely(bridge)
    finally:
        bridge.page = profile_page


def collect_rpa_state(status: PrePhoneStatus, report: RpaReport) -> None:
    status.screenshots = list(dict.fromkeys([*status.screenshots, *report.screenshots]))
    status.fields_seen = list(dict.fromkeys([*status.fields_seen, *report.fields_seen]))[:80]
    status.actions.extend(item for item in report.actions if item not in status.actions)
    status.warnings.extend(item for item in report.warnings if item not in status.warnings)


def probe_first_offer_page(bridge: KworkRpaBridge, status: PrePhoneStatus, offer: dict[str, Any], mode: str) -> None:
    if not bridge.context or not bridge.available:
        status.warn("browser unavailable for first offer probe")
        return
    profile_page = bridge.page
    bridge.page = bridge.context.new_page()
    try:
        bridge.open(MANAGE_KWORKS_URL)
        bridge.wait_and_screenshot("pre-phone-kwork-manage")
        login_state = bridge.detect_login_state()
        if login_state is not True:
            status.warn("login_detected is not true on kwork manage page; offer browser fill skipped")
            return
        bridge.close_popups_safe()
        if bridge.detect_phone_verification_required("pre-phone-kwork-phone-stop"):
            status.phone_verification_detected = True
            return
        click_create_kwork_button(bridge)
        if bridge.detect_phone_verification_required("pre-phone-kwork-phone-stop"):
            status.phone_verification_detected = True
            return
        if DEFAULT_DRAFT_URL not in bridge.page.url:
            bridge.open(DEFAULT_DRAFT_URL)
        if bridge.detect_phone_verification_required("pre-phone-kwork-phone-stop"):
            status.phone_verification_detected = True
            return
        bridge.wait_and_screenshot("pre-phone-kwork-create-mode")
        if mode == "run":
            fill_offer_fields(bridge, offer, None)
            bridge.wait_and_screenshot("pre-phone-kwork-after-fill")
            status.first_offer_filled_in_browser = True
        blocked = bridge.find_blocked_buttons()
        if blocked:
            status.warn(f"blocked action buttons visible and not clicked: {', '.join(blocked)}")
    finally:
        bridge.page = profile_page


def run_browser_phase(status: PrePhoneStatus, profile: dict[str, Any], offer: dict[str, Any]) -> None:
    if status.mode == "dry-run":
        status.action("dry-run: browser was not opened")
        return
    report = RpaReport(mode=f"pre-phone:{status.mode}", target_url=PROFILE_SETTINGS_URL, title="Kwork Pre-Phone Setup Browser Report")
    for key, value in build_offer_values(offer).items():
        report.hash_value(f"offer_{key}", value)
    for key in ("headline", "about", "skills", "trust_blocks", "buyer_friendly_description"):
        report.hash_value(f"profile_{key}", profile.get(key, ""))

    with KworkRpaBridge(report) as bridge:
        bridge.open(PROFILE_SETTINGS_URL)
        bridge.wait_and_screenshot("pre-phone-profile-open")
        login_state = bridge.detect_login_state()
        status.login_detected = "true" if login_state is True else "false" if login_state is False else "unknown"
        if bridge.detect_phone_verification_required("pre-phone-profile-phone-stop"):
            status.phone_verification_detected = True
            collect_rpa_state(status, report)
            if status.mode != "dry-run":
                write_pre_phone_report(status)
            if status.mode != "dry-run":
                maybe_hold(bridge, status)
            return
        if login_state is not True:
            status.warn("login_detected is not true; stopped before profile fill and offer probe")
            bridge.collect_fields()
            collect_rpa_state(status, report)
            if status.mode != "dry-run":
                write_pre_phone_report(status)
            maybe_hold(bridge, status)
            return

        bridge.collect_fields()
        status.username_detected = detect_username_safely(bridge)
        if status.username_detected == "unknown":
            status.username_detected = probe_username_page(bridge)
        open_profile_settings_tab(bridge)
        bridge.wait_and_screenshot("pre-phone-profile-before")
        if status.mode == "run":
            fill_optimized_fields(bridge, profile)
            bridge.wait_and_screenshot("pre-phone-profile-after")
            status.profile_filled_in_browser = True
        else:
            report.next_safe_command = "python scripts/kwork_pre_phone_setup.py --run --approve --hold"

        blocked = bridge.find_blocked_buttons()
        if blocked:
            status.warn(f"blocked profile action buttons visible and not clicked: {', '.join(blocked)}")

        probe_first_offer_page(bridge, status, offer, status.mode)
        collect_rpa_state(status, report)
        maybe_hold(bridge, status)


def maybe_hold(bridge: KworkRpaBridge, status: PrePhoneStatus) -> None:
    if not getattr(status, "hold", False):
        return
    if bridge.available:
        try:
            bridge.page.bring_to_front()
        except Exception:
            pass
        bridge.hold_open()


def bool_word(value: bool) -> str:
    return "yes" if value else "no"


def write_pre_phone_report(status: PrePhoneStatus) -> None:
    ensure_dir(REPORT_PATH.parent)
    next_step = (
        "Manual phone verification in Kwork, then manually review profile/kwork fields and save/publish only by hand."
        if status.phone_verification_detected
        else "Manual review: verify profile fields, first offer materials, and Kwork state before any save/publish action."
    )
    lines = [
        "# Kwork Pre-Phone Setup Report",
        "",
        f"Started at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"Mode: `{status.mode}`",
        "",
        "## Status Dashboard",
        f"- project_root: `{status.project_root}`",
        f"- git_commit: `{status.git_commit}`",
        f"- username_detected: `{status.username_detected}`",
        f"- login_detected: `{status.login_detected}`",
        f"- profile_prepared: `{bool_word(status.profile_prepared)}`",
        f"- profile_filled_in_browser: `{bool_word(status.profile_filled_in_browser)}`",
        f"- first_offer_prepared: `{bool_word(status.first_offer_prepared)}`",
        f"- first_offer_filled_in_browser: `{bool_word(status.first_offer_filled_in_browser)}`",
        f"- delivery_pack_prepared: `{bool_word(status.delivery_pack_prepared)}`",
        f"- ready_to_publish_pack_prepared: `{bool_word(status.ready_to_publish_pack_prepared)}`",
        f"- phone_verification_detected: `{bool_word(status.phone_verification_detected)}`",
        "",
        "## Ready Before Phone",
        "- Profile copy is prepared locally and can be filled into safe text fields.",
        "- First offer JSON, delivery pack, and ready-to-publish copy-paste materials are prepared.",
        "- Browser screenshots and value hashes can support manual review without storing secrets.",
        "",
        "## Manual-Only Before/After Phone",
        "- Phone number, SMS/call verification, withdrawal settings, and account switching.",
        "- `Сохранить профиль`, `Опубликовать`, `На модерацию`, `Отправить`, `Принять заказ`, `Отменить заказ`, `Подтвердить действие`, `Удалить`.",
        "- Client messages, order responses, moderation submission, publish/save/submit/send/delete flows.",
        "",
        "## Next Manual Step",
        f"- {next_step}",
        "",
        "## Actions",
        *(f"- {item}" for item in status.actions),
        "",
        "## Warnings",
        *(f"- {item}" for item in status.warnings),
        "",
        "## Screenshots",
        *(f"- `{item}`" for item in status.screenshots),
        "",
        "## Fields Seen",
        *(f"- {item}" for item in status.fields_seen[:80]),
    ]
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--preview", action="store_true")
    group.add_argument("--run", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode = "dry-run" if args.dry_run else "preview" if args.preview else "run"
    require_run_approval(mode, args.approve)
    status = PrePhoneStatus(mode=mode, hold=bool(args.hold))
    validate_root(status)
    profile, offer = prepare_offline_materials(status)
    run_browser_phase(status, profile, offer)
    write_pre_phone_report(status)
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
