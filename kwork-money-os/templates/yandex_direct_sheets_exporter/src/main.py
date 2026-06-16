"""Entrypoint for the Yandex Direct to Google Sheets exporter template."""

from __future__ import annotations

import argparse

from config import load_config, missing_required
from google_sheets_client import GoogleSheetsClient
from report_builder import build_report
from scheduler import default_date_range
from yandex_direct_client import YandexDirectClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock data and do not call external APIs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.mock:
        config = type(config)(**{**config.__dict__, "mock_mode": True})
    missing = missing_required(config)
    if missing:
        raise SystemExit(f"Missing required config values: {', '.join(missing)}")

    date_from = config.date_from
    date_to = config.date_to
    if not date_from or not date_to:
        date_from, date_to = default_date_range()

    direct = YandexDirectClient(config)
    sheets = GoogleSheetsClient(config)
    tables = build_report(
        keyword_stats=direct.fetch_keyword_stats(),
        campaign_stats=direct.fetch_campaign_stats(),
        date_from=date_from,
        date_to=date_to,
    )
    sheets.write_tables(tables)
    print(f"Prepared {sum(len(table.rows) for table in tables)} rows across {len(tables)} sheets.")


if __name__ == "__main__":
    main()
