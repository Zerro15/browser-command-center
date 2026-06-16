# Yandex Direct to Google Sheets Exporter

Public-safe starter template for exporting Yandex Direct statistics into Google Sheets.

This template is intentionally safe by default:
- no real tokens;
- no credentials;
- no client data;
- no browser cookies;
- no Kwork account data;
- tests use mock data only.

The client must provide their own Yandex Direct API access and Google service account access. Do not ask for account passwords, SMS codes, browser cookies, or payment access.

## What It Does

- Reads configuration from `.env`.
- Builds report rows for:
  - keyword statistics;
  - campaign statistics.
- Provides safe skeleton clients for Yandex Direct API and Google Sheets API.
- Supports mock mode so the report builder and tests can run without real APIs.
- Can be run manually or scheduled by cron/Task Scheduler.

## Quick Start

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python src/main.py --mock
```

`--mock` does not call external APIs. It only builds sample rows and prints what would be written to Google Sheets.

## Real API Mode

Fill `.env` with client-provided placeholders:

```env
YANDEX_DIRECT_TOKEN=...
YANDEX_CLIENT_LOGIN=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
SPREADSHEET_ID=...
```

Then implement the API request details in:
- `src/yandex_direct_client.py`;
- `src/google_sheets_client.py`.

## Safety

Never commit `.env`, service account JSON, tokens, client reports, or exported spreadsheet data.
