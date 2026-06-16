"""Configuration loader for the Yandex Direct to Google Sheets template."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    yandex_direct_token: str
    yandex_client_login: str
    google_service_account_json: str
    spreadsheet_id: str
    date_from: str
    date_to: str
    mock_mode: bool = True


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(env_path: Path | None = None) -> AppConfig:
    if env_path is None:
        env_path = Path.cwd() / ".env"
    load_dotenv(env_path)
    return AppConfig(
        yandex_direct_token=os.environ.get("YANDEX_DIRECT_TOKEN", ""),
        yandex_client_login=os.environ.get("YANDEX_CLIENT_LOGIN", ""),
        google_service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        spreadsheet_id=os.environ.get("SPREADSHEET_ID", ""),
        date_from=os.environ.get("DATE_FROM", ""),
        date_to=os.environ.get("DATE_TO", ""),
        mock_mode=bool_env("MOCK_MODE", True),
    )


def missing_required(config: AppConfig) -> list[str]:
    if config.mock_mode:
        return []
    checks = {
        "YANDEX_DIRECT_TOKEN": config.yandex_direct_token,
        "YANDEX_CLIENT_LOGIN": config.yandex_client_login,
        "GOOGLE_SERVICE_ACCOUNT_JSON": config.google_service_account_json,
        "SPREADSHEET_ID": config.spreadsheet_id,
    }
    return [name for name, value in checks.items() if not value or value == "..."]
