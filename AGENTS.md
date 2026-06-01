# Agent Notes

- Project name in WSL: `browser-command-center`.
- Main WSL path: `/home/zerro/project/browser-command-center`.
- Runtime requirement: Node.js 18+.
- Browser requirement: Chrome/Chromium available via `BROWSER_BRIDGE_CHROME` or a common Linux path.
- Before changing runtime behavior, run `npm run doctor` and `node --check` on edited JS files.
- Do not commit or copy `chrome-profile/`; it can contain local browser session data.
- Kwork-specific helper flows live in `browser-kwork.js`.
- Kwork cover assets live in `covers/`.
