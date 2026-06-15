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
- send proposals automatically;
- publish automatically;
- change the live profile without approval.
- click publish, moderation, send, delete, or profile-save buttons.

## Setup

Run commands from:

```bash
cd /home/zerro/projects/browser-command-center/kwork-money-os
```

The Python virtualenv lives inside Kwork Money OS, not at the repository root:

```bash
.venv/bin/python -m pip install requests PyYAML playwright
.venv/bin/python -m playwright install chromium
```

Use `.venv/bin/python scripts/...` from this directory for Python commands.

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
- phone verification, SMS code entry, withdrawal settings, account switching, and moderation submission.

If Kwork redirects to `https://kwork.ru/seller?new_phone_verify=1`, automation pauses. Phone numbers, SMS/calls, payout details, account switching, moderation, publication, and final confirmations stay manual-only.

Passwords must never be passed through argv, logs, state files, JSON, or markdown.

Even with `--approve`, the RPA bridge does not click:
- `Опубликовать`;
- `На модерацию`;
- `Сохранить профиль`;
- `Сохранить`;
- `Отправить сообщение`;
- `Отправить`;
- `Удалить`;
- `Принять заказ`;
- `Отменить заказ`;
- `Подтвердить действие`.

## Kwork Account Optimizer + Reply Assistant

All browser scripts support the same safe modes:

```bash
--dry-run    # no browser, writes a plan
--preview    # opens visible browser, reads/screenshots only
--run --approve --hold
```

The `--run --approve` mode may fill safe text fields, but final save/send/publish/delete/order buttons are still blocked and left for manual review.

Account audit:

```bash
python3 scripts/kwork_account_audit.py --dry-run
python3 scripts/kwork_account_audit.py --preview --hold
```

Profile optimization:

```bash
python3 scripts/generate_profile_optimization.py --run --approve
python3 scripts/fill_profile_optimized.py --preview --hold
python3 scripts/fill_profile_optimized.py --run --approve --hold
```

Kwork offer audit and local optimized drafts:

```bash
python3 scripts/optimize_existing_kworks.py --preview --hold
python3 scripts/optimize_existing_kworks.py --run --approve
```

Reply assistant and safe reply filler:

```bash
python3 scripts/kwork_reply_assistant.py --preview --hold
python3 scripts/fill_reply_draft.py --draft-id draft-xxxxxxxxxx --run --approve --hold
```

Money plan:

```bash
python3 scripts/account_money_plan.py --run --approve
```

Lead Radar, read-only project discovery and local proposal drafts:

```bash
npm run money:lead-radar -- --dry-run
npm run money:lead-radar -- --preview --hold
npm run money:lead-radar -- --run --approve --hold
```

`--dry-run` does not open a browser and can find `0` projects. It only validates local wiring and writes a local report.

`--preview --hold` opens a visible Playwright Chromium window with the persistent profile `kwork-money-os/.browser-profile`, checks `login_detected`, and leaves the browser open for manual review.

`--run --approve --hold` performs the read-only project collection, scoring, and local proposal draft generation. It writes local files only and still never submits anything.

Lead Radar uses Playwright Chromium, not Yandex Browser. If you are logged in through Yandex Browser, that does not count for Playwright Chromium. If `login_detected` is false, run `npm run money:lead-radar -- --preview --hold`, log in manually in the opened Chromium window, and do not save passwords, cookies, SMS codes, or credentials to project files.

Lead Radar scans visible project cards by safe topics, scores them, and writes local drafts only. It never clicks `Предложить услугу`, never sends proposals or messages, never publishes kworks, and stops if phone verification is detected.

Lead Radar local outputs:

```text
data/leads/kwork_leads.jsonl
data/leads/proposals/
reports/lead_radar_report.md
```

These files stay local and are ignored because project text, buyer names, and proposal drafts should not be pushed.

New outputs:

```text
reports/account_audit.md
reports/kwork_offers_audit.md
reports/reply_drafts.md
reports/account_money_plan.md
reports/lead_radar_report.md
data/profile/profile_optimized.json
data/leads/
data/offers/optimized/
data/replies/reply_drafts.json
```

## Безопасность перед git push

This repository can be public, so generated account artifacts must stay local.
Do not push:
- `reports/account_audit.md`;
- `reports/kwork_offers_audit.md`;
- `reports/account_money_plan.md`;
- `reports/lead_radar_report.md`;
- `reports/reply_drafts.md`;
- `reports/autopilot_report.md`;
- `reports/browser_fill_report.md`;
- `data/profile/profile_optimized.json`;
- `data/leads/`;
- `data/offers/optimized/` generated files, except `example_offer.json`;
- `data/replies/`;
- `.browser-profile/`, `.auth/`, `.venv/`, screenshots, cookies, state files, and `.env`.

Public-safe examples live in:
- `reports/account_audit.example.md`;
- `reports/account_money_plan.example.md`;
- `reports/reply_drafts.example.md`;
- `data/profile/profile_optimized.example.json`;
- `data/offers/optimized/example_offer.json`.

Before every push, run from the repository root:

```bash
git status --short --ignored
npm run money:check-private
```

The local runtime profile is `kwork-money-os/.browser-profile/`.
Screenshots are stored in `kwork-money-os/reports/screenshots/`.
Private generated strategy and account reports are in `kwork-money-os/reports/`.
Private generated leads and proposal drafts are in `kwork-money-os/data/leads/`.

Final Kwork actions are always manual:
- Profile Filler may fill text fields, but it does not click `Сохранить профиль`.
- Reply Assistant may prepare drafts, but it does not click `Отправить`.
- Offer tools may prepare local drafts, but they do not click `Опубликовать`, `На модерацию`, `Сохранить`, or `Удалить`.
- Orders are never accepted, cancelled, or confirmed automatically.
- Phone/SMS verification, withdrawal details, account switching, publication, moderation, and delete/confirm flows are not automated.
- Lead Radar may prepare local proposal drafts, but it does not click `Предложить услугу`, `Отправить`, or any final proposal/message button.
