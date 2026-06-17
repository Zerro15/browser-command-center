# Browser Command Center

Локальный CLI для управления Chrome через Chrome DevTools Protocol и запуска site-specific сценариев.

Это уже слой ближе к цели "работать с сайтами по промпту":

- запуск отдельного браузерного профиля;
- открытие URL;
- список вкладок;
- клик по CSS-селектору;
- клик по видимому тексту;
- ввод текста в поле по CSS-селектору;
- заполнение поля по подсказке `label`/`placeholder`/`name`;
- список кнопок и список полей на странице;
- нажатие клавиши;
- выполнение JS на странице;
- скриншот страницы.
- сценарии из нескольких шагов через `browser-flow`.
- prompt-like слой через `browser-prompt`.
- site-specific слой для отдельных сайтов, сейчас есть модуль `kwork.ru` через `browser-kwork`.

Быстрый старт:

```powershell
cd C:\Users\Bogdan\browser-bridge
.\browser-bridge.cmd start
.\browser-bridge.cmd new-page url=https://example.com
.\browser-bridge.cmd info
```

Сценарии:

```powershell
cd C:\Users\Bogdan\browser-bridge
.\browser-flow.cmd template
.\browser-flow.cmd run file=C:\Users\Bogdan\browser-bridge\flows\example-flow.txt
.\browser-prompt.cmd compile prompt="open kwork seller, list buttons"
.\browser-prompt.cmd run prompt="open kwork seller, list buttons, screenshot"
.\\browser-kwork.cmd open-seller
.\\browser-kwork.cmd inspect
```

Примеры:

```powershell
.\browser-bridge.cmd start
.\browser-bridge.cmd list
.\browser-bridge.cmd new-page url=https://kwork.ru/seller
.\browser-bridge.cmd info
.\\browser-bridge.cmd list-buttons
.\\browser-bridge.cmd list-fields
.\\browser-bridge.cmd click-text text=Войти
.\\browser-bridge.cmd fill hint=email text=mail@example.com
.\browser-bridge.cmd click selector=.login-button
.\browser-bridge.cmd type selector=input[name=email] text=mail@example.com clear=true
.\browser-bridge.cmd press key=Enter
.\browser-bridge.cmd eval js="(() => document.title)()"
.\browser-bridge.cmd screenshot
```

Замечания:

- Используется отдельный профиль `browser-bridge\chrome-profile`, чтобы не ломать основной браузер.
- Для сложных сайтов селекторы иногда надо уточнять через `eval`.
- Если сайт защищается от автоматизации, этот мост не гарантирует успех, но это уже намного лучше, чем кликать по координатам.
- `browser-flow` нужен как переход к режиму "ты даёшь текстовую инструкцию, локальный runner делает шаги по сайту".
- `browser-prompt` нужен как первый слой перевода короткого запроса в browser-flow, чтобы и я, и ты могли работать через один и тот же мост командами из терминала.
- `browser-kwork` нужен для типовых сценариев на Kwork без ручной сборки шагов каждый раз; другие сайты можно добавлять отдельными модулями рядом с ним.

## Kwork MVP Money-Now Flow

Когда цель не "идеальная система", а быстрый старт на Kwork, используй MVP-поток:

```bash
cd /home/zerro/projects/browser-command-center/kwork-money-os
.venv/bin/python scripts/kwork_full_fill_cdp.py --background
```

Что делает этот режим:

- заполняет текущий безопасный шаг формы кворка без `Сохранить`, `На модерацию`, `Опубликовать`, `Отправить`;
- пишет step-aware report в `kwork-money-os/reports/kwork_full_fill_cdp_report.md`;
- если Kwork не показывает пакеты/FAQ/теги на текущем шаге, это считается `fields_not_on_current_step`, а не ошибкой;
- создаёт local-only copy-paste pack в `kwork-money-os/data/kwork_studio/manual_fill_pack.md`, чтобы быстро закончить руками, если поле не найдено;
- создаёт local-only чеклист `kwork-money-os/reports/kwork_quick_publish_checklist.md`.

Быстрые офлайн-отклики:

```bash
cd /home/zerro/projects/browser-command-center/kwork-money-os
npm run money:quick-proposals
```

- Команда берёт уже сохранённые лиды и готовит 3-5 коротких откликов в `kwork-money-os/reports/quick_proposals_today.md`.
- Ничего не отправляется автоматически.

Cover workflow остаётся human-in-the-loop:

- если inbox с картинками пустой, это не блокирует работу с текстами и пакетами;
- статус cover можно добить позже вручную по prompt-файлу;
- все final buttons и отправка откликов остаются manual-only.

## Kwork Launch Tools

Для подготовки первого кворка к ручной проверке:

```bash
cd /home/zerro/projects/browser-command-center/kwork-money-os
npm run money:kwork-auto-category-cdp
npm run money:best-cover-prompt
npm run money:my-kworks-audit-cdp
npm run money:kwork-launch-readiness-cdp
npm run money:today-action-pack
```

- `money:kwork-auto-category-cdp` выбирает только category/subcategory, если уверенность достаточная.
- `money:best-cover-prompt` пишет один лучший prompt для ChatGPT image generation в `data/kwork_studio/best_cover_prompt_for_chatgpt.md`.
- `money:my-kworks-audit-cdp` read-only анализирует видимые кворки аккаунта и даёт рекомендации по title, cover, trust, DevOps и ясности для покупателя.
- `money:kwork-launch-readiness-cdp` проверяет, готов ли текущий кворк к ручному review.
- `money:today-action-pack` собирает category, cover prompt, audit, readiness и quick proposals в один локальный отчёт.

Все команды используют guarded Windows CDP / ZerroOne session. Они не нажимают `Сохранить`, `На модерацию`, `Опубликовать`, `Отправить`, `Предложить услугу`, order actions, phone/SMS, withdrawal или delete.
