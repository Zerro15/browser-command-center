# Client Handoff

## Delivered Files

- `src/main.py` — run entrypoint.
- `src/config.py` — `.env` loader.
- `src/yandex_direct_client.py` — safe Yandex Direct API skeleton.
- `src/google_sheets_client.py` — safe Google Sheets API skeleton.
- `src/report_builder.py` — report row builder and mock data.
- `src/scheduler.py` — scheduling helper examples.
- `tests/test_report_builder.py` — API-free tests.

## Client Responsibilities

- Provide Yandex Direct API token.
- Provide Yandex client login.
- Provide Google service account access.
- Share the target Google spreadsheet with the service account.
- Confirm required columns, periods, and campaign filters.

## What Not To Share

- Passwords.
- SMS codes.
- Browser cookies.
- Payment details.
- Personal/private data not required for the report.

## Acceptance

The first stage is accepted when mock tests pass, real API credentials are configured locally, and the target Google Sheet receives keyword and campaign rows for the agreed period.
