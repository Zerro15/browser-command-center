# Kwork Money OS Agent Notes

- Work only with public Kwork data unless the user has manually logged in through the visible browser.
- Never accept or request Kwork passwords through argv, logs, state, JSON, or markdown.
- Never publish kworks, send messages, edit the live profile, delete anything, or save live changes without explicit approval.
- Default every browser operation to dry-run unless the command says `--execute --approve`.
- Do not bypass captcha, rate limits, login walls, or platform protections.
- Market scan must be small and polite: low limits, delay between requests, public pages only.
- Generated offers are drafts; run `check_offer.py` before using them.
- Browser filling must stop before publication and print `Проверь и нажми сам`.
