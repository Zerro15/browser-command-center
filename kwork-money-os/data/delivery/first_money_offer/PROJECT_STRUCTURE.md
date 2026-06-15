# Project Structure

Пример минимальной структуры результата:

```text
telegram-leads-bot/
  bot.py
  sheets.py
  requirements.txt
  env.example
  README.md
```

## env.example

```env
BOT_TOKEN=replace_with_botfather_token_locally
ADMIN_CHAT_ID=replace_with_admin_chat_id_locally
GOOGLE_SHEET_ID=replace_with_sheet_id
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json
```

## Google Sheets columns

```text
created_at | name | contact | request_text | telegram_user_id | status
```

## requirements.txt

```text
aiogram>=3.0
gspread>=6.0
google-auth>=2.0
python-dotenv>=1.0
```
