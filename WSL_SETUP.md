# Browser Command Center — WSL notes

Проект лежит в WSL здесь:

```bash
cd ~/project/browser-command-center
```

## Быстрый старт

```bash
npm run doctor
./browser-bridge.sh start
./browser-kwork.sh open-kworks
./browser-kwork.sh list-my-kworks
```

## Если нужно докачать зависимости

Минимально нужен Node.js 18+ и Chrome/Chromium.

```bash
sudo apt update
sudo apt install -y nodejs npm
```

Для браузера установи один из вариантов:

```bash
sudo apt install -y chromium-browser
```

или укажи путь вручную:

```bash
export BROWSER_BRIDGE_CHROME=/usr/bin/google-chrome
```

Проверка состояния:

```bash
npm run doctor
```

## Обложки кворков

Готовые PNG лежат в:

```bash
./covers
```

Основные файлы:

- `covers/46004001-smartsender-capi.png`
- `covers/45979524-telegram-docx-csv.png`
- `covers/45587052-stage-1-analysis-plan.png`
- `covers/27194497-cicd-docker-devops.png`
