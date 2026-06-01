# Kwork Money OS

Semi-automatic Kwork earning system on top of `browser-command-center`.

It helps with:
- public market scanning;
- competitor analysis;
- opportunity scoring;
- offer drafts;
- banner prompts;
- QA checks;
- local profile drafts;
- dry-run and approved browser draft filling.
- headed Playwright RPA preview/fill for Kwork drafts and profile drafts.

It does not:
- bypass Kwork protections;
- collect private data;
- store passwords;
- send messages automatically;
- publish automatically;
- change the live profile without approval.
- click publish, moderation, send, delete, or profile-save buttons.

## Setup

Run commands from:

```bash
cd /home/zerro/projects/browser-command-center/kwork-money-os
```

Python dependencies used here are `requests` and `PyYAML`.
For browser RPA, install Playwright and its Chromium browser in the local environment:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

## Market Scan

Small public scan using `config/keywords.yaml`:

```bash
python3 scripts/kwork_market_scan.py
```

Offline smoke run without network:

```bash
python3 scripts/kwork_market_scan.py --offline
```

Results are saved to:

```text
data/market/YYYY-MM-DD.json
```

## Competitors

Use latest market scan:

```bash
python3 scripts/kwork_competitor_scan.py
```

Report:

```text
reports/competitors.md
```

## Generate Kwork Offer

Example:

```bash
python3 scripts/generate_offer.py telegram_bot_leads
```

Outputs:

```text
data/offers/telegram-bot-leads.md
data/offers/telegram-bot-leads.json
```

## Check Offer

```bash
python3 scripts/check_offer.py data/offers/telegram-bot-leads.json
```

Report goes to `reports/`.

## Banner Prompt

```bash
python3 scripts/generate_banner_prompt.py telegram_bot_leads
```

Outputs 3 variants:
- dark tech;
- clean business;
- bright marketplace.

## Profile Draft

```bash
python3 scripts/generate_profile_draft.py
```

This only creates local markdown and JSON in `data/profile/`.

## Fill Kwork Draft

The RPA bridge uses a visible Chromium browser with persistent profile:

```text
kwork-money-os/.browser-profile
```

Manual login flow:

1. Run preview.
2. If Kwork shows login, enter credentials manually in the visible browser.
3. Close nothing, then rerun preview or fill.

Dry-run only, no browser changes:

```bash
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --dry-run
```

Preview page and fields, no data entry:

```bash
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --preview
```

Fill draft fields after manual approval. This does not publish and does not click save/moderation:

```bash
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --fill-draft --approve
```

With an existing draft URL:

```bash
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --draft-url "https://kwork.ru/edit?id=123" --fill-draft --approve
```

With a ready banner image:

```bash
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --banner data/banners/banner.png --fill-draft --approve
```

The script stops before publication and prints: `Проверь и нажми сам`.

## Fill Profile Draft

Preview profile page and fields:

```bash
python3 scripts/fill_profile_draft.py --profile data/profile/profile_draft.json --preview
```

Fill profile fields after manual approval. This does not click profile save:

```bash
python3 scripts/fill_profile_draft.py --profile data/profile/profile_draft.json --fill-profile --approve
```

## Screenshots And Reports

RPA output:

```text
reports/browser_fill_report.md
reports/screenshots/
```

Reports include field names, warnings, screenshot paths, and value hashes only. Long offer/profile text is written as `sha256` plus length, not as raw content.

## Manual Approval Required

Always require manual approval before:
- publishing a kwork;
- sending a message;
- changing the live profile;
- deleting anything;
- saving live kwork changes;
- uploading a banner or file to a live draft.

Passwords must never be passed through argv, logs, state files, JSON, or markdown.

Even with `--approve`, the RPA bridge does not click:
- `Опубликовать`;
- `На модерацию`;
- `Сохранить профиль`;
- `Отправить сообщение`;
- `Отправить`;
- `Удалить`.
