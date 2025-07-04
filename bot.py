
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from redis_client import is_authorized, authorize_user
from crm import get_order_by_bot_code, get_orders_by_phone, get_order_status, get_tracking_number

import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Кнопки
menu_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📦 Статус отправления")],
    [KeyboardButton(text="📮 Трек-номер")],
    [KeyboardButton(text="📋 Мои заказы")],
    [KeyboardButton(text="🆘 Поддержка")]
], resize_keyboard=True)

@dp.message(lambda message: message.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
    "👋 Привет!\n"
    "Я — бот Missis S’Uzi.\n"
    "Помогаю следить за заказами и быть на связи, если что-то понадобится.\n\n"
    "Для начала пришлите, пожалуйста, ваш уникальный код или номер телефона 📦"
)

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text.strip()

    if not is_authorized(user_id):
        if authorize_user(user_id, user_input):
            await message.answer("Код принят! Добро пожаловать 🤍", reply_markup=menu_keyboard)
        else:
            await message.answer("Код не найден. Попробуйте ещё раз или напишите нам 📨")
        return

    if user_input == "📦 Статус отправления":
        status = get_order_status(user_id)
        await message.answer(f"Статус заказа: {status if status else 'Не удалось определить'} 📦")

    elif user_input == "📮 Трек-номер":
        track = get_tracking_number(user_id)
        if track:
            await message.answer(f"📦 Трек-номер: {track}")
        else:
            await message.answer("Трек-номер пока не присвоен. Как только он появится — сразу сообщим!")

    elif user_input == "📋 Мои заказы":
        orders = get_orders_by_phone(user_id)
        if not orders:
            await message.answer("Заказы не найдены.")
        else:
            text = "Ваши заказы:
" + "\n".join([f"• {o['number']} — {o['status']}" for o in orders])
            await message.answer(text)

    elif user_input == "🆘 Поддержка":
        support_message = f"Сообщение от клиента #{user_id}: {message.text}"
        await bot.send_message(ADMIN_TELEGRAM_ID, support_message)
        await message.answer("Мы уже на связи и скоро ответим вам 💬")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.debug(f"Webhook установлен: {WEBHOOK_URL}")

def main():
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    dp.startup.register(on_startup)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
