#!/usr/bin/env python3
"""Public-username guard for Kwork browser flows.

The guard only reasons about public usernames. It must never read or write
email, password, cookies, tokens, local storage, or browser session state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import unquote, urlparse

from _common import CONFIG, ROOT, load_yaml


DEFAULT_EXPECTED_USERNAME = "ZerroOne"
DEFAULT_ALLOWED_USERNAMES = ["ZerroOne", "bogdanmashenin"]
DEFAULT_BROWSER_PROFILE_PATH = ".browser-profile-zerroone"
DEFAULT_FALLBACK_BROWSER_PROFILE_PATH = ".browser-profile"
DEFAULT_REQUIRE_CONFIRMATION_ON_MISMATCH = True
DEFAULT_BLOCKED_WHEN_MISMATCH = [
    "publish",
    "send_message",
    "send_proposal",
    "save_profile",
    "accept_order",
    "withdrawal",
    "phone_change",
    "delete",
    "moderation_submit",
    "profile_fill",
    "kwork_draft_fill",
]
CONFIG_PATH = CONFIG / "kwork_account_guard.yaml"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{2,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class AccountGuardConfig:
    expected_username: str = DEFAULT_EXPECTED_USERNAME
    browser_profile_path: str = DEFAULT_BROWSER_PROFILE_PATH
    fallback_browser_profile_path: str = DEFAULT_FALLBACK_BROWSER_PROFILE_PATH
    allowed_usernames: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_USERNAMES))
    require_confirmation_on_mismatch: bool = DEFAULT_REQUIRE_CONFIRMATION_ON_MISMATCH
    blocked_when_mismatch: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKED_WHEN_MISMATCH))


@dataclass(frozen=True)
class AccountGuardResult:
    detected_username: str
    expected_username: str
    allowed_usernames: list[str]
    account_guard_status: str
    account_guard_action: str
    account_guard_message: str

    @property
    def ok(self) -> bool:
        return self.account_guard_status == "ok" and self.account_guard_action == "continue"


def _as_list(value: Any, fallback: Sequence[str]) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = list(value)
    elif isinstance(value, str) and value.strip():
        raw_items = [value]
    else:
        raw_items = list(fallback)
    normalized = [normalize_username(item) for item in raw_items]
    return [item for item in normalized if item != "unknown"] or [normalize_username(item) for item in fallback]


def normalize_profile_path_value(value: Any, fallback: str) -> str:
    raw = "" if value is None else str(value).strip().strip("\"'")
    if not raw:
        raw = fallback
    candidate = Path(raw)
    if candidate.is_absolute():
        raw = fallback
        candidate = Path(raw)
    try:
        resolved = (ROOT / candidate).resolve()
        resolved.relative_to(ROOT.resolve())
    except Exception:
        raw = fallback
    return raw.replace("\\", "/").strip("/") or fallback


def resolve_browser_profile_path(value: Any = None, fallback: str = DEFAULT_BROWSER_PROFILE_PATH) -> Path:
    normalized = normalize_profile_path_value(value, fallback)
    return (ROOT / normalized).resolve()


def active_browser_profile_path(config: AccountGuardConfig | None = None) -> Path:
    cfg = config or load_account_guard_config()
    return resolve_browser_profile_path(cfg.browser_profile_path, DEFAULT_BROWSER_PROFILE_PATH)


def fallback_browser_profile_path(config: AccountGuardConfig | None = None) -> Path:
    cfg = config or load_account_guard_config()
    return resolve_browser_profile_path(cfg.fallback_browser_profile_path, DEFAULT_FALLBACK_BROWSER_PROFILE_PATH)


def browser_profile_paths(config: AccountGuardConfig | None = None) -> tuple[Path, Path]:
    cfg = config or load_account_guard_config()
    return active_browser_profile_path(cfg), fallback_browser_profile_path(cfg)


def load_account_guard_config(path=CONFIG_PATH) -> AccountGuardConfig:
    data = load_yaml(path) if path.exists() else {}
    expected = normalize_username(data.get("expected_username", DEFAULT_EXPECTED_USERNAME))
    if expected == "unknown":
        expected = DEFAULT_EXPECTED_USERNAME
    allowed = _as_list(data.get("allowed_usernames"), DEFAULT_ALLOWED_USERNAMES)
    if expected not in allowed:
        allowed.insert(0, expected)
    blocked = data.get("blocked_when_mismatch") or DEFAULT_BLOCKED_WHEN_MISMATCH
    if not isinstance(blocked, list):
        blocked = DEFAULT_BLOCKED_WHEN_MISMATCH
    return AccountGuardConfig(
        expected_username=expected,
        browser_profile_path=normalize_profile_path_value(
            data.get("browser_profile_path"),
            DEFAULT_BROWSER_PROFILE_PATH,
        ),
        fallback_browser_profile_path=normalize_profile_path_value(
            data.get("fallback_browser_profile_path"),
            DEFAULT_FALLBACK_BROWSER_PROFILE_PATH,
        ),
        allowed_usernames=allowed,
        require_confirmation_on_mismatch=bool(
            data.get("require_confirmation_on_mismatch", DEFAULT_REQUIRE_CONFIRMATION_ON_MISMATCH)
        ),
        blocked_when_mismatch=[str(item) for item in blocked],
    )


def normalize_username(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unquote(text).strip().strip("`'\"").strip()
    if not text or text.lower() in {"unknown", "none", "null", "not_checked", "not_checked_dry_run"}:
        return "unknown"
    if EMAIL_RE.match(text):
        return "unknown"

    parsed_path = ""
    try:
        parsed = urlparse(text)
        parsed_path = parsed.path or ""
    except Exception:
        parsed_path = ""
    path_source = parsed_path or text
    match = re.search(r"(?:^|/)user/([^/?#\s]+)", path_source, re.I)
    if match:
        text = match.group(1)

    text = text.strip().lstrip("@").strip("/")
    text = re.split(r"[\s?#/]+", text, maxsplit=1)[0].strip()
    if not text or EMAIL_RE.match(text) or not USERNAME_RE.match(text):
        return "unknown"
    return text


def evaluate_account_guard(
    detected_username: Any,
    expected_username: str | None = None,
    allowed_usernames: Sequence[str] | None = None,
) -> AccountGuardResult:
    config = load_account_guard_config()
    expected = normalize_username(expected_username or config.expected_username)
    allowed = _as_list(allowed_usernames, config.allowed_usernames)
    if expected == "unknown":
        expected = DEFAULT_EXPECTED_USERNAME
    if expected not in allowed:
        allowed.insert(0, expected)

    detected = normalize_username(detected_username)
    if detected == "unknown":
        return AccountGuardResult(
            detected_username=detected,
            expected_username=expected,
            allowed_usernames=allowed,
            account_guard_status="unknown",
            account_guard_action="stop",
            account_guard_message=(
                f"Could not detect public Kwork username. Switch manually to {expected} in Playwright Chromium "
                "and rerun the safe check."
            ),
        )
    if detected not in allowed:
        return AccountGuardResult(
            detected_username=detected,
            expected_username=expected,
            allowed_usernames=allowed,
            account_guard_status="blocked",
            account_guard_action="stop",
            account_guard_message=(
                f"Detected Kwork username {detected} is not in allowed_usernames. Browser automation stopped."
            ),
        )
    if detected == expected:
        return AccountGuardResult(
            detected_username=detected,
            expected_username=expected,
            allowed_usernames=allowed,
            account_guard_status="ok",
            account_guard_action="continue",
            account_guard_message=f"Detected target Kwork account {expected}; safe flow may continue.",
        )
    action = "stop_for_confirmation" if config.require_confirmation_on_mismatch else "stop"
    return AccountGuardResult(
        detected_username=detected,
        expected_username=expected,
        allowed_usernames=allowed,
        account_guard_status="mismatch",
        account_guard_action=action,
        account_guard_message=(
            f"Detected Kwork username {detected}, but target account is {expected}. "
            "Switch account manually in Playwright Chromium before profile, kwork, or lead browser flows."
        ),
    )


def apply_account_guard_to_report(report: Any, result: AccountGuardResult) -> None:
    config = load_account_guard_config()
    active_path, fallback_path = browser_profile_paths(config)
    setattr(report, "detected_username", result.detected_username)
    setattr(report, "expected_username", result.expected_username)
    setattr(report, "allowed_usernames", ", ".join(result.allowed_usernames))
    setattr(report, "account_guard_status", result.account_guard_status)
    setattr(report, "account_guard_action", result.account_guard_action)
    setattr(report, "account_guard_message", result.account_guard_message)
    setattr(report, "active_browser_profile_path", str(active_path))
    setattr(report, "fallback_browser_profile_path", str(fallback_path))


def format_account_guard_report(result: AccountGuardResult) -> list[str]:
    config = load_account_guard_config()
    active_path, fallback_path = browser_profile_paths(config)
    return [
        f"- detected_username: `{result.detected_username}`",
        f"- expected_username: `{result.expected_username}`",
        f"- active_browser_profile_path: `{active_path}`",
        f"- fallback_browser_profile_path: `{fallback_path}`",
        f"- allowed_usernames: `{', '.join(result.allowed_usernames)}`",
        f"- account_guard_status: `{result.account_guard_status}`",
        f"- account_guard_action: `{result.account_guard_action}`",
        f"- account_guard_message: `{result.account_guard_message}`",
    ]
