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
kwork-money-os/.browser-profile-zerroone
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

## Kwork Account Guard

Target Kwork account for working flows is `ZerroOne`.

The guard reads only public username signals from Playwright Chromium: the current `/user/<username>` URL and visible public profile links. It does not read email, phone, passwords, cookies, tokens, local storage, or session files.

Config:

```text
config/kwork_account_guard.yaml
```

Default policy:
- `expected_username`: `ZerroOne`;
- `browser_profile_path`: `.browser-profile-zerroone`;
- `fallback_browser_profile_path`: `.browser-profile`;
- `allowed_usernames`: `ZerroOne`, `bogdanmashenin`;
- `bogdanmashenin` is known, but not the target account;
- if detected username is `bogdanmashenin`, guard status is `mismatch` and action is `stop_for_confirmation`;
- unknown username stops browser automation;
- usernames outside `allowed_usernames` are blocked.

When Account Guard is not `ok`, browser flows stop before profile fill, kwork draft fill, and Lead Radar browser scan. Daily dry-run and offline triage can still run because they do not act through a live Kwork account.

Manual account switch helper:

```bash
.venv/bin/python scripts/manual_kwork_login.py --account ZerroOne --hold
```

It opens Playwright Chromium with `.browser-profile-zerroone`, prints `detected_username`, leaves the browser open for manual login/switch to `ZerroOne`, then checks again after Enter or the configured wait. Do not save passwords to files, and do not automate account switching.

More explicit login wizard:

```bash
.venv/bin/python scripts/manual_kwork_login.py --account ZerroOne --login-page --wait-login --hold
```

Use this when `.browser-profile-zerroone` is not logged in. Log in manually in the opened Playwright Chromium window, not in Yandex Browser. If the detected username is not `ZerroOne`, Account Guard stops automation before profile fill, kwork draft fill, Lead Radar browser scans, or any final action. Credentials, cookies, passwords, phone, and SMS codes are not entered or saved by scripts.

Final actions remain manual-only always: profile save, publish, moderation, proposals, messages, order actions, withdrawal, phone/SMS, delete, and confirmations.

## Dedicated ZerroOne Browser Profile

Kwork Money OS uses a dedicated Playwright Chromium profile for the target account:

```text
.browser-profile-zerroone/
```

The legacy profile can still exist:

```text
.browser-profile/
```

Use `.browser-profile-zerroone` for `ZerroOne` only. Do not copy cookies, session files, passwords, tokens, or credentials from `.browser-profile` into the new profile. If `.browser-profile` is logged in as `bogdanmashenin`, that is expected legacy state and must not be used for target automation.

If `.browser-profile-zerroone` is empty or `login_detected=false`, run:

```bash
.venv/bin/python scripts/manual_kwork_login.py --account ZerroOne --login-page --wait-login --hold
```

Log in manually in the opened Chromium window. The scripts do not enter login, password, phone, SMS, or credentials automatically and do not write them to project files. If the detected username is not `ZerroOne`, Account Guard stops profile fill, kwork draft fill, and Lead Radar browser scans.

## How To Login ZerroOne Into Playwright Chromium

Run from `kwork-money-os`:

```bash
.venv/bin/python scripts/manual_kwork_login.py --account ZerroOne --login-page --wait-login --hold --diagnose
```

The wizard opens the dedicated Playwright Chromium profile `.browser-profile-zerroone` and, when needed, opens the Kwork login page. Complete login manually in that Chromium window only. A login in Yandex Browser does not count for Playwright Chromium.

After the manual wait, the wizard checks login and public username up to 12 times. `detected_username=ZerroOne` means `account_guard_status=ok`; any other username or `unknown` stops automation. The script never writes credentials, never types login/password/SMS/phone, and never clicks final buttons.

## Fix Playwright Login For ZerroOne

The main workflow uses Playwright Chromium with the persistent profile:

```text
.browser-profile-zerroone/
```

Do not use Yandex Browser or a normal Chrome profile for the Kwork Money OS workflow. Do not copy cookies, session files, passwords, local storage, or tokens from any other browser. Log in once manually inside Playwright Chromium, then let `.browser-profile-zerroone` persist the session.

Open the login page and diagnose the profile:

```bash
.venv/bin/python scripts/kwork_login_diagnostics.py --account ZerroOne --profile .browser-profile-zerroone --open-login --hold
```

After manual login, open `https://kwork.ru/user/ZerroOne` in that Chromium window, return to the terminal, and press Enter. Then verify persistence without touching final actions:

```bash
.venv/bin/python scripts/kwork_login_diagnostics.py --account ZerroOne --profile .browser-profile-zerroone --check-only --restart-check
```

The report is local-only:

```text
reports/kwork_login_diagnostics_report.md
```

Continue with read-only post-phone/dashboard checks only when the diagnostics report shows:

```text
detected_username: ZerroOne
account_guard_status: ok
persistence_confirmed: true
```

If `login_detected=true` but username is still unknown, the guard reports `unknown_logged_in`; open the public profile page `https://kwork.ru/user/ZerroOne` in Playwright Chromium and rerun diagnostics. If `login_detected=false`, finish manual login in Playwright Chromium. Final actions remain manual-only.

## ZerroOne Long Poll Login

Use this as the main manual login path when `.browser-profile-zerroone` is not authenticated:

```bash
npm run money:login-zerroone
```

Equivalent direct command from `kwork-money-os`:

```bash
.venv/bin/python scripts/manual_kwork_login.py --account ZerroOne --login-page --poll-until-login --timeout-minutes 30
```

This opens visible Playwright Chromium with `.browser-profile-zerroone`, opens the Kwork login page, and waits up to 30 minutes while checking every 5 seconds. The only manual step is entering login/password/SMS in that Playwright Chromium window. Do not use Yandex Browser or a normal Chrome profile for this workflow.

The script does not type credentials, does not read passwords, does not copy cookies from any browser, and does not save credentials to files. It only checks public session signals, account menu/profile links, current URL/title, and safe read-only access such as `manage_kworks`.

Success means both are true:

```text
detected_username=ZerroOne
persistence_confirmed=true
```

If another username is detected, the wizard stops with Account Guard `blocked`. If the 30-minute timeout expires, it stops with `unknown` and asks to finish manual login in Playwright Chromium. Final actions remain blocked: profile save, publish, moderation, proposal/message send, order actions, withdrawal, phone/SMS, delete, and confirmations.

## Playwright GUI Diagnostics

Before trying to log in to `ZerroOne`, verify that headed Playwright Chromium is actually visible from WSL:

```bash
npm run money:gui-check
npm run money:gui-open-test
```

`money:gui-check` inspects WSL/WSLg environment variables, `/mnt/wslg`, Playwright Chromium availability, current user, cwd, and `.browser-profile-zerroone` write access. `money:gui-open-test` opens only `https://example.com` in visible Chromium with `headless=False` and keeps it open for confirmation.

If the test Chromium window is visible, then run:

```bash
npm run money:login-zerroone
```

If the window is not visible, Kwork login through Playwright is not possible yet. Fix WSLg/GUI first; logging in through Yandex Browser or a normal Chrome window does not count. Do not transfer cookies, local storage, passwords, tokens, or session files from any normal browser.

The GUI diagnostics report is local-only:

```text
reports/playwright_gui_diagnostics_report.md
```

`money:login-zerroone` includes a GUI preflight and stops before opening Kwork if visible Chromium is unavailable.

## Windows Visible Browser CDP Mode

Use this fallback when WSLg/Playwright technically launches Chromium but the window is not visible on the Windows desktop. This mode opens a separate visible Windows Chrome or Edge window and connects Playwright to it through Chrome DevTools Protocol (CDP).

First test with a harmless page:

```bash
npm run money:win-browser-test
```

This opens only `https://example.com` in a dedicated Windows browser profile. It does not open Kwork, does not log in, and does not touch cookies.

If the Windows Chrome/Edge test window is visible, use:

```bash
npm run money:win-login-zerroone
```

The dedicated Windows profile is under the current Windows user's local app data, for example:

```text
%LOCALAPPDATA%\KworkMoneyOS\ChromeProfiles\ZerroOne
```

This is not the user's normal browser profile. Do not copy cookies, local storage, passwords, tokens, or session files from Yandex/Chrome/Edge into it. The script does not read cookies or passwords and does not type login, password, phone, or SMS. The user enters credentials manually in the visible Windows Chrome/Edge window.

After login, check persistence:

```bash
npm run money:win-check-zerroone
```

Continue automation only if the local report shows:

```text
cdp_connected: true
detected_username: ZerroOne
account_guard_status: ok
persistence_confirmed: true
```

The CDP report is local-only:

```text
reports/windows_visible_browser_cdp_report.md
```

Final actions remain manual-only: profile save, publish, moderation, proposal/message send, order actions, withdrawal, phone/SMS, delete, and confirmations.

## Windows CDP Production Browser Mode

Use Windows CDP as the primary browser backend after `money:win-login-zerroone` succeeds. This mode uses the dedicated visible Windows Chrome/Edge profile:

```text
%LOCALAPPDATA%\KworkMoneyOS\ChromeProfiles\ZerroOne
```

It does not use Yandex Browser, does not use the normal Chrome/Edge profile, does not copy cookies, and does not read credentials, local storage, passwords, or tokens. The legacy WSL profile `.browser-profile-zerroone` can still exist, but when `browser_mode=windows_cdp` it is diagnostic only and should not block ZerroOne work.

Check the dedicated Windows profile:

```bash
npm run money:win-check-zerroone
```

Run read-only post-phone readiness through Windows CDP:

```bash
npm run money:post-phone-cdp
```

Preview the profile and first-kwork pages without filling or saving:

```bash
npm run money:profile-preview-cdp
npm run money:kwork-preview-cdp
```

Read-only lead entrypoints:

```bash
npm run money:lead-radar-cdp
npm run money:daily-leads-cdp
```

Continue only when reports show:

```text
browser_mode: windows_cdp
cdp_connected: true
login_detected: true
detected_username: ZerroOne
account_guard_status: ok
```

The CDP preview reports are local-only:

```text
reports/post_phone_readiness_report.md
reports/cdp_preview_report.md
reports/operator_dashboard.md
reports/operator_dashboard.html
```

Even in Windows CDP mode, final actions remain manual-only: profile save, publish, moderation, proposal/message send, order actions, withdrawal, phone/SMS, delete, and confirmations.

## CDP Fill Without Final Buttons

After Windows CDP login is confirmed, the setup flows can fill safe fields in the dedicated Windows Chrome/Edge profile and then stop for manual review:

```bash
npm run money:profile-fill-cdp
npm run money:kwork-fill-cdp
```

`money:profile-fill-cdp` opens Kwork profile settings through Windows CDP, reads local `data/profile/profile_optimized.json`, fills safe profile text fields when Account Guard is `ok`, and stops before saving. It writes:

```text
reports/profile_fill_cdp_report.md
```

`money:kwork-fill-cdp` opens the new kwork form through Windows CDP, prepares the first Telegram bot offer from local public-safe offer data, fills safe title/description/package/FAQ/question/tag fields when selectors are available, and stops before save/moderation/publication. It writes:

```text
reports/kwork_fill_cdp_report.md
```

If Windows Chrome was closed, the CDP tools reopen the dedicated profile automatically:

```text
%LOCALAPPDATA%\KworkMoneyOS\ChromeProfiles\ZerroOne
```

Before any fill, scripts must confirm:

```text
cdp_connected: true
detected_username: ZerroOne
account_guard_status: ok
persistence_confirmed: true
```

The hard final-button blocker records visible final buttons but does not click them:

```text
Сохранить профиль, Сохранить, Опубликовать, На модерацию, Отправить,
Предложить услугу, Принять заказ, Подтвердить, Удалить,
Настроить вывод, Привязать телефон
```

Manual next step after fill: review the page visually in the dedicated Windows Chrome window. Only the user may decide to save the profile, save the kwork draft, or submit moderation. The scripts still do not enter passwords, SMS, phone data, withdrawal details, messages, proposals, or final confirmations.

## Kwork Production Studio

Production Studio prepares a stronger first kwork without publishing it:

```bash
npm run money:kwork-studio-cdp
npm run money:kwork-competitor-scan-cdp
npm run money:cover-studio
npm run money:kwork-marketing-qa
```

It creates local-only strategy/spec/cover/QA artifacts under:

```text
data/kwork_studio/
reports/kwork_studio_report.md
reports/kwork_competitor_scan_report.md
reports/kwork_cover_studio_report.md
reports/kwork_marketing_qa_report.md
```

The selected first kwork is DevOps-strengthened: Telegram bot for requests, Google Sheets, `.env`, launch instructions, webhook/polling notes, Docker/Linux deploy in Premium, and no unsafe claims about spam, captcha bypass, mass registration, or guaranteed sales.

Full multi-step fill through Windows CDP:

```bash
npm run money:kwork-full-fill-cdp
npm run money:kwork-full-fill-cdp-bg
```

The background variant asks Windows Chrome/Edge to launch minimized/no-focus where possible and reports:

```text
foreground_policy
background_mode
brought_to_front_count
```

Target is `brought_to_front_count=0` for scan/preview/studio and no forced foreground during fill. At the end, review manually from the Windows taskbar.

Cover tools:

```bash
npm run money:cover-preview-cdp
npm run money:cover-upload-cdp
```

`cover-upload-cdp` may attach the selected local PNG if the file input is visible, but it never clicks save, moderation, publish, send, proposal, order, phone, withdrawal, delete, or confirmation buttons.

## Human-In-The-Loop ChatGPT Cover Workflow

Codex does not automate ChatGPT UI. It does not open `chatgpt.com`, paste prompts, wait for image generation, or download ChatGPT outputs. The user generates covers manually, then Kwork Money OS validates and uploads the selected local file.

1. Generate copy-paste prompts:

```bash
npm run money:cover-prompt-studio
```

Outputs:

```text
data/kwork_studio/cover_prompts_for_chatgpt.md
data/kwork_studio/cover_prompts_for_chatgpt.json
reports/kwork_cover_prompt_studio_report.md
```

2. Copy prompts into ChatGPT manually and save PNG/JPG/WebP outputs here:

```text
data/kwork_studio/covers/inbox/
```

3. Check inbox images:

```bash
npm run money:cover-inbox-check
```

4. Select one file:

```bash
npm run money:cover-select -- --file cover_01.png
```

If exactly one valid image is in inbox, this can also be used:

```bash
npm run money:cover-select -- --interactive
```

5. Process selected cover for Kwork:

```bash
npm run money:cover-process-selected
```

Expected processed file:

```text
data/kwork_studio/covers/processed/selected_cover_kwork.png
```

6. Upload through guarded Windows CDP:

```bash
npm run money:cover-upload-cdp
```

The upload command checks `ZerroOne`, Account Guard, and persistence first. It never clicks `Сохранить`, `На модерацию`, `Опубликовать`, `Отправить`, proposal/order/phone/withdrawal/delete/confirmation buttons. Final review and save/moderation decisions are manual-only.

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

`--preview --hold` opens a visible Playwright Chromium window with the configured target profile `kwork-money-os/.browser-profile-zerroone`, checks `login_detected`, and leaves the browser open for manual review.

`--run --approve --hold` performs the read-only project collection, scoring, and local proposal draft generation. It writes local files only and still never submits anything.

Lead Radar uses Playwright Chromium, not Yandex Browser. If you are logged in through Yandex Browser, that does not count for Playwright Chromium. If `login_detected` is false, run `.venv/bin/python scripts/manual_kwork_login.py --account ZerroOne --hold`, log in manually in the opened Chromium window, and do not save passwords, cookies, SMS codes, or credentials to project files.

Lead Radar also checks Kwork Account Guard. If Playwright Chromium is logged in as `bogdanmashenin` or any non-target account, it stops before scanning projects and writes `account_guard_status` to `reports/lead_radar_report.md`. Switch manually to `ZerroOne` in Chromium before running browser collection.

Lead Radar scans visible project cards by safe topics, scores them, and writes local drafts only. It never clicks `Предложить услугу`, never sends proposals or messages, never publishes kworks, and stops if phone verification is detected.

Lead Radar local outputs:

```text
data/leads/kwork_leads.jsonl
data/leads/proposals/
reports/lead_radar_report.md
```

These files stay local and are ignored because project text, buyer names, and proposal drafts should not be pushed.

Lead Triage, offline shortlist from saved Lead Radar results:

```bash
npm run money:lead-triage
.venv/bin/python scripts/kwork_lead_triage.py --input data/leads/kwork_leads.jsonl --top 10
```

Lead Triage does not open Kwork and does not use a browser. It reads the local `data/leads/kwork_leads.jsonl`, deduplicates projects, removes high-risk work such as captcha/bypass/spam/mass registration/payment/account-access requests, recalculates realistic first-account prices, and writes a local shortlist.

Lead Triage local outputs:

```text
data/leads/shortlist/
reports/lead_shortlist.md
reports/top_5_proposals.md
```

The `reports/top_5_proposals.md` file is copy-paste friendly, but proposals remain manual-only. Do not send anything before phone verification is completed manually, and never automate `Предложить услугу`, `Отправить`, messages, phone/SMS, withdrawal, publication, moderation, or order actions.

Daily Lead Pipeline:

```bash
npm run money:daily-leads -- --dry-run
npm run money:daily-leads -- --run --approve --hold
.venv/bin/python scripts/kwork_daily_pipeline.py --dry-run
.venv/bin/python scripts/kwork_daily_pipeline.py --run --approve --hold
```

`money:daily-leads` runs the full safe cycle. In `--dry-run`, it does not open a browser: it checks the saved `data/leads/kwork_leads.jsonl`, runs offline Lead Triage, and updates `reports/lead_shortlist.md`, `reports/top_5_proposals.md`, and `reports/daily_lead_pipeline_report.md`.

In `--run --approve`, it first runs `money:lead-radar` behavior read-only through Playwright Chromium, then runs `money:lead-triage` offline. It does not send proposals, does not click `Предложить услугу`, and does not touch messages, phone/SMS, withdrawal, publication, moderation, or order actions. If phone verification appears, the pipeline records it and continues only with offline triage from already saved leads.

Use the pieces separately when needed:
- `money:lead-radar` collects leads read-only.
- `money:lead-triage` chooses the best leads offline.
- `money:daily-leads` runs the safe daily loop and prepares the top proposals report.

All replies remain manual-only. Until phone verification is completed manually, do not send proposals or messages.

Best Lead of Day:

```bash
npm run money:best-lead
.venv/bin/python scripts/kwork_best_lead_of_day.py
```

Best Lead of Day is an offline analysis step. It reads `data/leads/kwork_leads.jsonl`, `reports/top_5_proposals.md`, and `data/leads/shortlist/`, then chooses one best project using final score, low risk, clear technical fit, realistic first-account price, and 2-7 day delivery fit.

It writes:

```text
reports/best_lead_of_day.md
data/leads/best_lead_of_day_proposal.md
```

These files are local-only. The proposal is not sent automatically. Sending proposals remains manual-only after phone verification is completed manually; do not automate `Предложить услугу`, `Отправить`, messages, phone/SMS, withdrawal, publication, moderation, or order actions.

Kwork Portfolio Pack:

```text
data/portfolio/
```

The portfolio pack contains three public-safe demo cases for the `ZerroOne` profile:
- Telegram bot for lead capture into Google Sheets;
- Yandex Direct statistics export to Google Sheets;
- simple project launch in Docker with client instructions.

These are honest examples, starter templates, and demo projects. They must not be described as fake reviews, paid commercial orders, or completed client work unless that becomes true later. Use wording such as "demo project", "example solution", "starter template", and "ready structure for quick adaptation".

Portfolio upload to Kwork is manual-only. Do not automate portfolio upload, profile save, moderation, publication, proposal sending, phone/SMS verification, withdrawal setup, messages, or order actions.

Kwork Offer Factory:

```text
data/offers/factory/
reports/offer_factory_report.md
```

Offer Factory contains five public-safe Kwork drafts for `ZerroOne`:
- Telegram bot for leads with Google Sheets;
- Google Sheets automation;
- Docker launch for a small Python/Node.js project;
- basic Python parser without captcha or bypass;
- simple AI assistant or chatbot for business.

The JSON drafts include titles, descriptions, packages, prices, delivery times, FAQ, buyer questions, tags, delivery checklists, risk notes, forbidden scope, and portfolio links. They are prepared for manual publication after phone verification, but they are not published automatically.

`reports/offer_factory_report.md` is a local-only report with recommended publishing order, risk, complexity, approximate margin, and readiness notes. Do not commit runtime reports. Publishing, moderation, profile save, `Опубликовать`, `На модерацию`, phone/SMS, withdrawal, proposals, and messages remain manual-only final actions.

Kwork Order Executor:

```bash
npm run money:order-executor -- --dry-run
npm run money:order-executor -- --from-best-lead --build
npm run money:order-executor -- --offer data/offers/factory/telegram_leads_bot.json --build
```

From inside `kwork-money-os`, the same tool can be run directly:

```bash
.venv/bin/python scripts/kwork_order_executor.py --dry-run
.venv/bin/python scripts/kwork_order_executor.py --from-best-lead --build
.venv/bin/python scripts/kwork_order_executor.py --offer data/offers/factory/telegram_leads_bot.json --build
```

Order Executor is an offline preparation tool. It does not open Kwork, accept orders, send messages, send proposals, publish kworks, save the profile, or touch phone/SMS/withdrawal actions. It creates a local workspace under:

```text
data/orders/prepared/
reports/order_executor_report.md
```

Use it after a future order is manually discussed/accepted. It prepares questions, scope limits, tech plan, task checklist, acceptance criteria, handoff draft, risk notes, `.env.example`, and a `project/` starter area. Real tokens, passwords, cookies, screenshots, sessions, and client private data must stay out of Git. `data/orders/prepared/` and `reports/order_executor_report.md` are ignored/local-only.

Post-Phone Readiness:

```bash
npm run money:post-phone -- --preview --hold
.venv/bin/python scripts/kwork_post_phone_readiness.py --preview --hold
```

Post-Phone Readiness is a read-only Playwright Chromium check for the moment after the user manually links a phone on Kwork. It opens Kwork with the persistent `.browser-profile-zerroone`, checks `login_detected`, public username, phone verification stop, seller/profile access, and create-kwork page access.

It writes Account Guard fields into the report: `detected_username`, `expected_username`, `allowed_usernames`, `account_guard_status`, `account_guard_action`, and `account_guard_message`. If detected username is `bogdanmashenin`, `profile_ready_to_save_manually=false` and `kwork_draft_ready_to_continue=false` until the user manually switches Chromium to `ZerroOne`.

It writes local-only reports:

```text
reports/post_phone_readiness_report.md
reports/post_phone_readiness_bridge_report.md
```

It does not fill profile fields, publish kworks, click `Опубликовать`, click `На модерацию`, click `Сохранить профиль`, send proposals/messages, accept orders, touch phone/SMS, or configure withdrawal. Use the report to decide whether it is safe to continue with profile filling or draft preparation; final actions remain manual-only.

Kwork Operator Dashboard:

```bash
npm run money:dashboard
.venv/bin/python scripts/kwork_operator_dashboard.py --build
```

The operator dashboard is built locally from saved reports and artifacts. It collects the daily pipeline status, Post-Phone Readiness, Best Lead of Day, top proposals, copy-paste proposal text, delivery kit, starter template, portfolio pack, Offer Factory, Order Executor status, and manual-only checklist into:

```text
reports/operator_dashboard.md
reports/operator_dashboard.html
```

The dashboard is for manual work after phone verification. It does not open Kwork, send proposals, click `Предложить услугу`, publish, moderate, save profile, handle phone/SMS, or touch withdrawal/order actions. `reports/operator_dashboard.*` are ignored/local-only and must not be committed.

The dashboard shows Kwork Account Guard status and warns: profile, kworks, and proposals should be prepared only for `ZerroOne`; before publication, verify manually that the active account is correct.

New outputs:

```text
reports/account_audit.md
reports/kwork_offers_audit.md
reports/reply_drafts.md
reports/account_money_plan.md
reports/lead_radar_report.md
reports/lead_shortlist.md
reports/top_5_proposals.md
reports/daily_lead_pipeline_report.md
reports/best_lead_of_day.md
reports/operator_dashboard.md
reports/operator_dashboard.html
reports/post_phone_readiness_report.md
reports/post_phone_readiness_bridge_report.md
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
- `reports/lead_shortlist.md`;
- `reports/top_5_proposals.md`;
- `reports/daily_lead_pipeline_report.md`;
- `reports/best_lead_of_day.md`;
- `reports/operator_dashboard.md`;
- `reports/operator_dashboard.html`;
- `reports/post_phone_readiness_report.md`;
- `reports/post_phone_readiness_bridge_report.md`;
- `reports/reply_drafts.md`;
- `reports/autopilot_report.md`;
- `reports/browser_fill_report.md`;
- `data/profile/profile_optimized.json`;
- `data/leads/`;
- `data/offers/optimized/` generated files, except `example_offer.json`;
- `data/replies/`;
- `.browser-profile-zerroone/`, `.browser-profile/`, `.auth/`, `.venv/`, screenshots, cookies, state files, and `.env`.

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

The target local runtime profile is `kwork-money-os/.browser-profile-zerroone/`.
The legacy/fallback runtime profile is `kwork-money-os/.browser-profile/`.
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
