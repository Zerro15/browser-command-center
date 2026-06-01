# Browser RPA Bridge

`browser_rpa_bridge.py` is the safe headed Playwright layer for Kwork.

## Principles

- Use a visible Chromium browser, not Android or ROM emulation.
- Use persistent local profile: `kwork-money-os/.browser-profile`.
- Do not accept passwords through argv.
- If Kwork asks for login, stop and let the user log in manually in the visible browser.
- Do not click publish, moderation, send, delete, or profile-save buttons.
- Do not log cookies, tokens, passwords, or private messages.
- Long offer/profile values are logged only as `sha256` plus length.

## Modes

Draft:

```bash
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --dry-run
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --preview
python3 scripts/fill_kwork_draft.py --offer data/offers/telegram-bot-leads.json --fill-draft --approve
```

Profile:

```bash
python3 scripts/fill_profile_draft.py --profile data/profile/profile_draft.json --preview
python3 scripts/fill_profile_draft.py --profile data/profile/profile_draft.json --fill-profile --approve
```

## Reports

- Main report: `reports/browser_fill_report.md`
- Screenshots: `reports/screenshots/`
- Dry-run plans:
  - `data/offers/*.rpa-plan.yaml`
  - `data/profile/*.rpa-plan.yaml`

## Selector Strategy

The bridge tries:

1. label text;
2. placeholder text;
3. generic hint matching across label/name/id/placeholder/aria-label;
4. explicit selectors from `config/selectors.yaml`.

Missing optional fields are reported as warnings. Required title/description/profile-about fields produce stronger warnings but do not click unsafe buttons.

## Safety Boundary

`--approve` allows filling fields in a visible browser. It does not allow publishing, sending messages, deleting, or saving profile changes. Those controls are detected, written to the report as blocked buttons, and left untouched.
