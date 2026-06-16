# Setup

## 1. Create environment

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

## 2. Mock check

```bash
.venv/bin/python src/main.py --mock
.venv/bin/python -m unittest discover tests
```

Mock mode does not call Yandex Direct API or Google Sheets API.

## 3. Real API preparation

The client should provide:

```env
YANDEX_DIRECT_TOKEN=...
YANDEX_CLIENT_LOGIN=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
SPREADSHEET_ID=...
```

Do not request account passwords, SMS codes, browser cookies, or payment access.

## 4. Scheduling

Use cron or Task Scheduler after a successful manual run. See `src/scheduler.py` for an example cron line.
