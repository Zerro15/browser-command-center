#!/usr/bin/env python3
"""Human-in-the-loop cover bridge for Kwork Money OS.

This script never opens or automates ChatGPT. It only prepares prompts,
checks user-saved images, selects/processes a local cover, and can upload the
processed file to Kwork through the guarded Windows CDP profile.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import REPORTS, ROOT
from browser_rpa_bridge import DEFAULT_DRAFT_URL, PHONE_VERIFICATION_RE
from browser_session import open_kwork_browser_session
from kwork_studio_common import COVERS_DIR, ensure_studio_dirs, rel, write_json, write_text
from windows_visible_browser_cdp import EXPECTED_ACCOUNT, MANAGE_KWORKS_URL, run_check_zerroone


INBOX_DIR = COVERS_DIR / "inbox"
SELECTED_DIR = COVERS_DIR / "selected"
PROCESSED_DIR = COVERS_DIR / "processed"
ARCHIVE_DIR = COVERS_DIR / "archive"
PROMPTS_MD = COVERS_DIR.parent / "cover_prompts_for_chatgpt.md"
PROMPTS_JSON = COVERS_DIR.parent / "cover_prompts_for_chatgpt.json"
SELECTED_JSON = SELECTED_DIR / "selected_cover.json"
PROCESSED_COVER = PROCESSED_DIR / "selected_cover_kwork.png"

PROMPT_REPORT = REPORTS / "kwork_cover_prompt_studio_report.md"
INBOX_REPORT = REPORTS / "kwork_cover_inbox_report.md"
SELECTION_REPORT = REPORTS / "kwork_cover_selection_report.md"
PROCESSED_REPORT = REPORTS / "kwork_cover_processed_report.md"
UPLOAD_REPORT = REPORTS / "kwork_cover_upload_report.md"

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


PROMPTS = [
    {
        "title": "Вариант 1 — Telegram-бот для заявок",
        "main_text": "Telegram-бот для заявок\nGoogle Таблица + деплой",
        "style": "премиальный tech/SaaS стиль, чистый DevOps-интерфейс, не детский",
        "composition": "слева крупный заголовок, справа абстрактные карточки чата, таблицы и сервера, много воздуха",
        "colors": "глубокий navy, белый, бирюзовый, немного зелёного акцента",
        "negative_prompt": "без реальных логотипов Telegram/Google/Docker, без мультяшности, без хаоса, без мелкого текста, без обещаний 100% результата",
        "why_it_sells": "самый конкретный результат: заявки, таблица и запуск; выглядит надёжнее дешёвых кворков",
        "expected_ctr_score": 92,
    },
    {
        "title": "Вариант 2 — Бот для бизнеса",
        "main_text": "Бот для бизнеса\nзаявки • таблица • запуск",
        "style": "коммерческий B2B automation dashboard, аккуратные блоки и метрики",
        "composition": "центральная dashboard-карточка, стрелка от чата к таблице, маленький серверный блок",
        "colors": "тёмный графит, молочный белый, лаймовый и голубой акцент",
        "negative_prompt": "без дешёвых 3D-иконок, без перегруза, без реальных брендов, без слов лучший/гарантия/продажи",
        "why_it_sells": "говорит языком бизнеса: не ботик, а понятный поток заявок",
        "expected_ctr_score": 88,
    },
    {
        "title": "Вариант 3 — Автоматизация заявок",
        "main_text": "Автоматизация заявок\nTelegram + Sheets + DevOps",
        "style": "minimal premium tech, Python/API vibe, clean infrastructure grid",
        "composition": "крупный заголовок, тонкие линии API, абстрактные иконки чата/таблицы/Linux-сервера",
        "colors": "тёмно-синий фон, белый текст, янтарный и cyan акценты",
        "negative_prompt": "без логотипов, без детского стиля, без клипарта, без мелких деталей, без обещаний быстрых денег",
        "why_it_sells": "лучше подчёркивает DevOps-уровень и техническое доверие",
        "expected_ctr_score": 86,
    },
]


@dataclass
class ImageInfo:
    path: Path
    ok: bool
    width: int = 0
    height: int = 0
    kind: str = "unknown"
    size_bytes: int = 0
    reason: str = ""

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0


def ensure_dirs() -> None:
    ensure_studio_dirs()
    for path in [INBOX_DIR, SELECTED_DIR, PROCESSED_DIR, ARCHIVE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def image_size(path: Path) -> tuple[str, int, int]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return "png", *struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            block_len = int.from_bytes(data[i + 2 : i + 4], "big")
            if marker in {0xC0, 0xC2}:
                return "jpeg", int.from_bytes(data[i + 7 : i + 9], "big"), int.from_bytes(data[i + 5 : i + 7], "big")
            i += 2 + block_len
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return "webp", width, height
        return "webp", 0, 0
    return path.suffix.lower().lstrip(".") or "unknown", 0, 0


def scan_inbox() -> list[ImageInfo]:
    ensure_dirs()
    items: list[ImageInfo] = []
    for path in sorted(INBOX_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in VALID_EXTENSIONS:
            continue
        try:
            kind, width, height = image_size(path)
            size = path.stat().st_size
            aspect = width / height if height else 0
            ok = bool(width >= 660 and height >= 440 and 1.35 <= aspect <= 1.8 and size > 0)
            reason = "ok" if ok else "needs 660x440+ horizontal image; regenerate or process manually"
            items.append(ImageInfo(path=path, ok=ok, width=width, height=height, kind=kind, size_bytes=size, reason=reason))
        except Exception as error:
            items.append(ImageInfo(path=path, ok=False, size_bytes=path.stat().st_size, reason=str(error)))
    return items


def write_prompt_studio() -> None:
    ensure_dirs()
    payload = []
    lines = ["# ChatGPT Cover Prompts For Kwork", "", "Codex не открывает ChatGPT UI. Скопируй один промт вручную в ChatGPT.", ""]
    for index, prompt in enumerate(PROMPTS, start=1):
        copy = (
            "Создай горизонтальную обложку для Kwork 1320x880 или минимум 660x440. "
            f"Текст на обложке: {prompt['main_text']}. "
            f"Стиль: {prompt['style']}. Композиция: {prompt['composition']}. "
            f"Цвета: {prompt['colors']}. Услуга: Telegram-бот для заявок, Google Таблица, деплой/инструкция, Python/API/DevOps vibe. "
            f"Negative prompt: {prompt['negative_prompt']}. Сделай коммерчески, чисто, дорого, без перегруза."
        )
        item = {**prompt, "copy_paste_prompt": copy}
        payload.append(item)
        lines.extend(
            [
                f"## Вариант {index} — {prompt['title']}",
                "",
                "Скопируй в ChatGPT:",
                "",
                "```text",
                copy,
                "```",
                "",
                f"- main_text: `{prompt['main_text']}`",
                f"- style: {prompt['style']}",
                f"- composition: {prompt['composition']}",
                f"- colors: {prompt['colors']}",
                f"- negative_prompt: {prompt['negative_prompt']}",
                f"- why_it_sells: {prompt['why_it_sells']}",
                f"- expected_ctr_score: `{prompt['expected_ctr_score']}`",
                "",
            ]
        )
    write_json(PROMPTS_JSON, {"prompts": payload})
    write_text(PROMPTS_MD, "\n".join(lines))
    write_text(
        PROMPT_REPORT,
        "\n".join(
            [
                "# Kwork Cover Prompt Studio Report",
                "",
                f"- prompts_count: `{len(payload)}`",
                f"- prompts_md: `{rel(PROMPTS_MD)}`",
                f"- prompts_json: `{rel(PROMPTS_JSON)}`",
                f"- inbox_path: `{rel(INBOX_DIR)}`",
                "- next_manual_step: `Скопируй промты в ChatGPT вручную, сохрани PNG/JPG/WebP в inbox.`",
                "- safety: ChatGPT UI is not automated.",
            ]
        ),
    )
    print(PROMPT_REPORT)
    print(f"prompts_md={PROMPTS_MD}")
    print(f"inbox_path={INBOX_DIR}")


def write_inbox_report(items: list[ImageInfo]) -> None:
    lines = [
        "# Kwork Cover Inbox Report",
        "",
        f"- inbox_path: `{rel(INBOX_DIR)}`",
        f"- images_count: `{len(items)}`",
        f"- valid_images_count: `{sum(1 for item in items if item.ok)}`",
    ]
    if not items:
        lines.append("- next_manual_step: `Сгенерируй обложки в ChatGPT вручную и сохрани PNG/JPG/WebP в data/kwork_studio/covers/inbox/`")
    lines.extend(["", "## Images"])
    for item in items:
        lines.append(
            f"- `{item.path.name}`: ok={str(item.ok).lower()} {item.width}x{item.height} aspect={item.aspect:.2f} kind={item.kind} size={item.size_bytes} reason={item.reason}"
        )
    write_text(INBOX_REPORT, "\n".join(lines))


def inbox_check() -> list[ImageInfo]:
    items = scan_inbox()
    write_inbox_report(items)
    print(INBOX_REPORT)
    print(f"images_count={len(items)}")
    print(f"valid_images_count={sum(1 for item in items if item.ok)}")
    if not items:
        print("Сгенерируй обложки в ChatGPT вручную и сохрани PNG/JPG/WebP в data/kwork_studio/covers/inbox/")
    return items


def select_cover(file_name: str | None, interactive: bool) -> None:
    items = scan_inbox()
    if interactive and not file_name:
        valid = [item for item in items if item.ok]
        if len(valid) == 1:
            file_name = valid[0].path.name
        else:
            write_text(SELECTION_REPORT, "# Kwork Cover Selection Report\n\n- selected: `false`\n- next_manual_step: `Run npm run money:cover-select -- --file <filename>`")
            print(SELECTION_REPORT)
            print("selected=false")
            return
    if not file_name:
        raise SystemExit("Pass --file <inbox filename> or use --interactive when exactly one valid image exists.")
    source = INBOX_DIR / file_name
    if not source.exists() or source.suffix.lower() not in VALID_EXTENSIONS:
        raise SystemExit(f"Cover not found in inbox: {source}")
    dest = SELECTED_DIR / f"selected_cover_original{source.suffix.lower()}"
    shutil.copy2(source, dest)
    kind, width, height = image_size(dest)
    write_json(SELECTED_JSON, {"source": rel(source), "selected_original": rel(dest), "kind": kind, "width": width, "height": height})
    write_text(
        SELECTION_REPORT,
        "\n".join(
            [
                "# Kwork Cover Selection Report",
                "",
                "- selected: `true`",
                f"- source: `{rel(source)}`",
                f"- selected_original: `{rel(dest)}`",
                f"- size: `{width}x{height}`",
                "- next_manual_step: `npm run money:cover-process-selected`",
            ]
        ),
    )
    print(SELECTION_REPORT)
    print(f"selected_original={dest}")


def copy_png_payload(src: Path, dest: Path) -> bool:
    kind, width, height = image_size(src)
    if kind != "png":
        return False
    shutil.copy2(src, dest)
    return True


def process_selected() -> None:
    ensure_dirs()
    data = json.loads(SELECTED_JSON.read_text(encoding="utf-8")) if SELECTED_JSON.exists() else {}
    selected = data.get("selected_original")
    if not selected:
        raise SystemExit("No selected cover. Run npm run money:cover-select -- --file <filename> first.")
    src = ROOT / selected
    if not src.exists():
        src = SELECTED_DIR / Path(selected).name
    kind, width, height = image_size(src)
    aspect = width / height if height else 0
    ok = width >= 660 and height >= 440 and 1.35 <= aspect <= 1.8
    processed = False
    recommendation = "ready"
    if ok and kind == "png":
        processed = copy_png_payload(src, PROCESSED_COVER)
    elif ok:
        shutil.copy2(src, PROCESSED_DIR / f"selected_cover_kwork{src.suffix.lower()}")
        recommendation = "File is acceptable but not PNG; convert manually to PNG for the exact processed path."
    else:
        recommendation = "Regenerate a horizontal 1320x880 or 660x440+ cover in ChatGPT."
    write_text(
        PROCESSED_REPORT,
        "\n".join(
            [
                "# Kwork Cover Processed Report",
                "",
                f"- source: `{rel(src)}`",
                f"- source_size: `{width}x{height}`",
                f"- source_kind: `{kind}`",
                f"- suitable_for_kwork: `{str(ok).lower()}`",
                f"- processed: `{str(processed).lower()}`",
                f"- processed_file: `{rel(PROCESSED_COVER) if PROCESSED_COVER.exists() else 'none'}`",
                f"- recommendation: `{recommendation}`",
                "- next_manual_step: `npm run money:cover-upload-cdp`" if processed else "- next_manual_step: `Regenerate or convert selected cover, then rerun processing.`",
            ]
        ),
    )
    print(PROCESSED_REPORT)
    print(f"processed={str(processed).lower()}")
    print(f"processed_file={PROCESSED_COVER if PROCESSED_COVER.exists() else 'none'}")


def upload_cdp() -> None:
    ensure_dirs()
    check = run_check_zerroone(restart_check=True)
    attempted = False
    success = False
    warnings = []
    if not PROCESSED_COVER.exists():
        warnings.append(f"Processed cover is missing: {PROCESSED_COVER}")
    with open_kwork_browser_session(mode="windows_cdp", account=EXPECTED_ACCOUNT, start_url=MANAGE_KWORKS_URL, keep_open=True) as session:
        session.open(DEFAULT_DRAFT_URL)
        diag = session.refresh_diagnostics()
        phone = bool("new_phone_verify=1" in diag.current_url or PHONE_VERIFICATION_RE.search(session.visible_text()))
        if check.account_guard_status != "ok" or not check.persistence_confirmed or diag.account_guard_status != "ok" or phone:
            warnings.append("Guard/persistence/phone check stopped upload.")
        elif PROCESSED_COVER.exists():
            attempted = True
            try:
                inputs = session.page.locator("input[type='file']")
                if inputs.count() < 1:
                    warnings.append("Cover file input not found.")
                else:
                    inputs.first.set_input_files(str(PROCESSED_COVER))
                    session.page.wait_for_timeout(1200)
                    success = True
            except Exception as error:
                warnings.append(f"Upload failed safely: {error}")
        final_buttons = session.find_blocked_buttons()
        shot = session.screenshot("human-cover-upload-cdp")
    write_text(
        UPLOAD_REPORT,
        "\n".join(
            [
                "# Kwork Cover Upload Report",
                "",
                f"- selected_file: `{data.get('selected_original', 'unknown') if (data := (json.loads(SELECTED_JSON.read_text(encoding='utf-8')) if SELECTED_JSON.exists() else {})) else 'unknown'}`",
                f"- processed_file: `{rel(PROCESSED_COVER) if PROCESSED_COVER.exists() else 'none'}`",
                f"- upload_attempted: `{str(attempted).lower()}`",
                f"- upload_success: `{str(success).lower()}`",
                f"- detected_username: `{diag.detected_username}`",
                f"- account_guard_status: `{diag.account_guard_status}`",
                f"- persistence_confirmed: `{str(check.persistence_confirmed).lower()}`",
                f"- final_buttons_blocked: `{str(bool(final_buttons)).lower()}`",
                f"- final_buttons: `{', '.join(final_buttons) if final_buttons else 'none'}`",
                f"- screenshot: `{shot}`",
                f"- user_next_step: `Проверь обложку глазами. Сохранение/модерация только вручную.`",
                "",
                "## Warnings",
                *(f"- {item}" for item in warnings),
                "",
                "## Safety",
                "- No save/moderation/publish/send/proposal/order/phone/withdrawal/delete/final buttons clicked.",
            ]
        ),
    )
    print(UPLOAD_REPORT)
    print(f"upload_attempted={str(attempted).lower()}")
    print(f"upload_success={str(success).lower()}")
    print(f"final_buttons_blocked={str(bool(final_buttons)).lower()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prompt-studio")
    sub.add_parser("inbox-check")
    select = sub.add_parser("select")
    select.add_argument("--file")
    select.add_argument("--interactive", action="store_true")
    sub.add_parser("process-selected")
    sub.add_parser("upload-cdp")
    args = parser.parse_args()
    if args.command == "prompt-studio":
        write_prompt_studio()
    elif args.command == "inbox-check":
        inbox_check()
    elif args.command == "select":
        select_cover(args.file, args.interactive)
    elif args.command == "process-selected":
        process_selected()
    elif args.command == "upload-cdp":
        upload_cdp()


if __name__ == "__main__":
    main()
