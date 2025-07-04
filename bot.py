import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.executor import start_webhook
from config import TELEGRAM_TOKEN, ADMIN_TELEGRAM_ID, WEBHOOK_URL
from crm import get_order_by_bot_code, get_orders_by_phone, get_order_status, get_tracking_number
from redis_client import is_authorized, save_authorization
import re

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

WELCOME_MSG = """👋 Привет!
Я — бот Missis S’Uzi.
Помогаю следить за заказами и быть на связи, если что-то понадобится.
Для начала пришлите, пожалуйста, ваш уникальный код или номер телефона 📦"""

def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📦 Статус отправления", "🔢 Трек-номер")
    kb.add("🗂 Мои заказы")
    kb.add(KeyboardButton("💬 Поддержка"))
    return kb

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer(WELCOME_MSG)

@dp.message_handler(lambda message: message.text == "💬 Поддержка")
async def support_handler(message: types.Message):
    await bot.send_message(
        ADMIN_TELEGRAM_ID,
        f"""Сообщение от клиента #{message.from_user.id}:
{message.text}"""
    )
    await message.answer("Сообщение передано! Мы скоро ответим 🤍")

@dp.message_handler(lambda message: True)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if not is_authorized(user_id):
        if re.match(r"^\+?\d{10,15}$", text):
            orders = get_orders_by_phone(text)
            if orders:
                save_authorization(user_id)
                await message.answer("Вы авторизованы по номеру телефона ☎️", reply_markup=main_keyboard())
            else:
                await message.answer("Не найден заказ с этим номером. Попробуйте ещё раз.")
        else:
            order = get_order_by_bot_code(text)
            if order:
                save_authorization(user_id)
                await message.answer("Код принят! Добро пожаловать 🤍", reply_markup=main_keyboard())
            else:
                await message.answer("Неверный код. Уточните у администратора.")
        return

    if text == "📦 Статус отправления":
        status = get_order_status(user_id)
        await message.answer(f"Статус заказа: {status}")
    elif text == "🔢 Трек-номер":
        track = get_tracking_number(user_id)
        if track:
            await message.answer(f"📦 Трек-номер: {track}\n[Отследить](https://www.cdek.ru/ru/tracking)", parse_mode="Markdown")
        else:
            await message.answer("Трек-номер пока не присвоен. Как только он появится — сразу сообщим!")
    elif text == "🗂 Мои заказы":
        orders = get_orders_by_phone(user_id=user_id)
        if not orders:
            await message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
        else:
            msg = "\n".join([f"• {o['number']} — {o['status']}" for o in orders])
            await message.answer(f"Ваши заказы:\n{msg}")
    else:
        await message.answer("Выберите команду из меню или напишите нам 💬")

async def on_startup(dp):
    print(f"[DEBUG] Устанавливаю webhook: {WEBHOOK_URL}")
    result = await bot.set_webhook(WEBHOOK_URL)
    print(f"[DEBUG] Webhook установлен: {result}")

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == "__main__":
    start_webhook(
        dispatcher=dp,
        webhook_path="",
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host="0.0.0.0",
        port=8000,
    )