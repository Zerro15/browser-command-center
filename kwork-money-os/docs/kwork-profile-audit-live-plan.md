# Kwork Profile Audit Live Collector Plan

## Summary

Add a small read-only live collector for created Kworks. The collector will use the dedicated Windows CDP browser profile for `ZerroOne`, open only the "My Kworks" page, collect visible kwork metadata, and write local-only reports for the offline auditor. It must never mutate Kwork state.

Command:

```bash
npm run money:kwork-profile-audit-live
```

## Scope

Open:

```text
https://kwork.ru/manage_kworks
```

Collect visible read-only fields when available:

- title;
- status;
- category;
- subcategory;
- price;
- cover present true/false;
- URL;
- visible warnings, moderation notes, or action-required labels.

Do not attempt to fully edit or submit a kwork. Do not open dangerous controls unless a future implementation can prove the page is read-only and no mutation action can occur.

## Guard Requirements

Before collecting data, the command must confirm:

- `detected_username=ZerroOne` case-insensitive;
- `account_guard_status=ok`;
- `persistence_confirmed=true`;
- Windows CDP connected to the dedicated Kwork Money OS profile;
- normal user browser cookies, passwords, local storage, tokens, and credentials are not read or copied.

If any guard check fails, stop and write a local report with status `STOPPED_BY_GUARD`.

## Stop Conditions

Stop without collecting or clicking further if the page shows:

- wrong account;
- unknown account;
- login required;
- phone or SMS requirement;
- captcha;
- block page;
- action-required interstitial;
- withdrawal prompt;
- any state-changing confirmation.

## Forbidden Actions

The collector must not:

- click `Сохранить`;
- click `На модерацию`;
- click `Опубликовать`;
- click `Отправить`;
- click `Предложить услугу`;
- click `Принять заказ`;
- click `Подтвердить`;
- click `Удалить`;
- pause, resume, delete, publish, moderate, or save any kwork;
- send proposals;
- send client messages;
- accept or cancel orders;
- enter login/password/SMS;
- change phone;
- configure withdrawal.

Any action that changes Kwork state remains manual-only.

## Outputs

Local-only outputs:

```text
reports/kwork_profile_audit_live_report.md
data/kwork_profile_audit/live_kworks_snapshot.json
```

The JSON snapshot should be consumed by the existing offline command:

```bash
npm run money:kwork-profile-audit
```

The report should include:

- browser_opened;
- cdp_connected;
- detected_username;
- account_guard_status;
- persistence_confirmed;
- collection_status;
- kworks_collected;
- stopped_reason;
- mutation_buttons_detected;
- final_buttons_clicked;
- kwork_state_changed;
- proposals_sent;
- messages_sent;
- screenshot path if safe.

## Acceptance Criteria

- `browser_opened` may be `true`.
- `kwork_state_changed` must be `false`.
- `final_buttons_clicked` must be `false`.
- `proposals_sent` must be `false`.
- `messages_sent` must be `false`.
- Wrong/unknown account stops before collection.
- Login/phone/SMS/captcha/block pages stop the flow.
- The generated local snapshot can be used by the offline audit report.
- Private checker passes and no runtime reports/snapshots are committed.

## Minimal Implementation Path

1. Add a new runner `scripts/kwork_profile_audit_live.py`.
2. Reuse existing Windows CDP/session and Account Guard helpers.
3. Open `manage_kworks` in background/no-focus mode.
4. Extract visible kwork cards/rows using DOM text and links only.
5. Write local JSON and markdown report.
6. Keep scoring and copy recommendations in `scripts/kwork_profile_audit.py`.
7. Add npm script `money:kwork-profile-audit-live`.
8. Run checks without clicking final buttons.
