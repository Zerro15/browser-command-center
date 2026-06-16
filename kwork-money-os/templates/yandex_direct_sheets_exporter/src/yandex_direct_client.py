"""Safe skeleton for Yandex Direct API access.

The real implementation should use official Yandex Direct API endpoints and
client-provided API tokens. This file never contains real credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import AppConfig
from report_builder import mock_campaign_stats, mock_keyword_stats


@dataclass
class YandexDirectClient:
    config: AppConfig

    def validate(self) -> None:
        if self.config.mock_mode:
            return
        if not self.config.yandex_direct_token or self.config.yandex_direct_token == "...":
            raise ValueError("YANDEX_DIRECT_TOKEN is required for real API mode")
        if not self.config.yandex_client_login or self.config.yandex_client_login == "...":
            raise ValueError("YANDEX_CLIENT_LOGIN is required for real API mode")

    def fetch_keyword_stats(self) -> list[dict]:
        self.validate()
        if self.config.mock_mode:
            return mock_keyword_stats()
        raise NotImplementedError("Implement official Yandex Direct API keyword report request here")

    def fetch_campaign_stats(self) -> list[dict]:
        self.validate()
        if self.config.mock_mode:
            return mock_campaign_stats()
        raise NotImplementedError("Implement official Yandex Direct API campaign report request here")
