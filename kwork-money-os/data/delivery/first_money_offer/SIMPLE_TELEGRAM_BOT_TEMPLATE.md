# Simple Telegram Bot Template

Этот шаблон показывает безопасную структуру без реальных токенов. Перед передачей клиенту заменить только `env.example`, а секреты хранить в локальном `.env`.

## bot.py

```python
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from sheets import append_lead


BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class LeadForm(StatesGroup):
    name = State()
    contact = State()
    request_text = State()


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext) -> None:
    await state.set_state(LeadForm.name)
    await message.answer("Здравствуйте. Как вас зовут?")


@dp.message(LeadForm.name)
async def ask_contact(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(LeadForm.contact)
    await message.answer("Оставьте контакт для связи.")


@dp.message(LeadForm.contact)
async def ask_request(message: types.Message, state: FSMContext) -> None:
    await state.update_data(contact=message.text.strip())
    await state.set_state(LeadForm.request_text)
    await message.answer("Коротко опишите заявку.")


@dp.message(LeadForm.request_text)
async def finish(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    lead = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "name": data["name"],
        "contact": data["contact"],
        "request_text": message.text.strip(),
        "telegram_user_id": message.from_user.id if message.from_user else "",
        "status": "new",
    }
    append_lead(lead)
    if ADMIN_CHAT_ID:
        await bot.send_message(
            ADMIN_CHAT_ID,
            "Новая заявка:\\n"
            f"Имя: {lead['name']}\\n"
            f"Контакт: {lead['contact']}\\n"
            f"Заявка: {lead['request_text']}",
        )
    await state.clear()
    await message.answer("Заявка получена. Спасибо.")


if __name__ == "__main__":
    dp.run_polling(bot)
```

## sheets.py

```python
import os

import gspread
from google.oauth2.service_account import Credentials


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
COLUMNS = ["created_at", "name", "contact", "request_text", "telegram_user_id", "status"]


def append_lead(lead: dict) -> None:
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    credentials_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sheet_id or not credentials_path:
        return

    credentials = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key(sheet_id).sheet1
    worksheet.append_row([lead.get(column, "") for column in COLUMNS])
```

## requirements.txt

```text
aiogram>=3.0
gspread>=6.0
google-auth>=2.0
python-dotenv>=1.0
```
