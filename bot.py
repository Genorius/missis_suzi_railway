import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from crm import (
    pick_order_by_code_or_phone,
    get_order_status_text,
    get_tracking_number_text,
    get_orders_list_text,
    save_review
)

# Логирование
logging.basicConfig(level=logging.INFO)

# Конфиг
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # заменишь на свой

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM
class AuthStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_review = State()

# Кнопки
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Статус отправления", callback_data="status")],
        [InlineKeyboardButton(text="🎯 Трек-номер", callback_data="track")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="orders")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ])

# /start
@dp.message(commands=["start"])
async def start_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "👋 Привет! Я Missis S’Uzi — помогу узнать статус вашего заказа.\n"
        "Введите, пожалуйста, ваш bot_code или номер телефона 🤍"
    )
    await state.set_state(AuthStates.waiting_for_code)

# Авторизация
@dp.message(AuthStates.waiting_for_code)
async def process_auth(message: types.Message, state: FSMContext):
    code_or_phone = message.text.strip()
    order = pick_order_by_code_or_phone(code_or_phone, telegram_id=message.from_user.id)

    if order:
        await state.clear()
        await message.answer("✅ Авторизация успешна! Что хотите узнать?", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Не удалось найти заказ. Проверьте введённые данные и попробуйте снова.")

# Статус
@dp.callback_query(lambda c: c.data == "status")
async def order_status_handler(callback: types.CallbackQuery):
    status_text = get_order_status_text(callback.from_user.id)
    await callback.message.answer(status_text)

# Трек
@dp.callback_query(lambda c: c.data == "track")
async def tracking_handler(callback: types.CallbackQuery):
    track_text = get_tracking_number_text(callback.from_user.id)
    await callback.message.answer(track_text)

# Заказы
@dp.callback_query(lambda c: c.data == "orders")
async def orders_handler(callback: types.CallbackQuery):
    orders_text = get_orders_list_text(callback.from_user.id)
    await callback.message.answer(orders_text)

# Поддержка
@dp.callback_query(lambda c: c.data == "support")
async def support_handler(callback: types.CallbackQuery):
    await callback.message.answer("💬 Пожалуйста, напишите свой вопрос, и мы ответим как можно скорее 🤍")
    await bot.send_message(ADMIN_ID, f"Запрос поддержки от @{callback.from_user.username} (ID {callback.from_user.id})")

# Отзыв
@dp.message(AuthStates.waiting_for_review)
async def review_handler(message: types.Message, state: FSMContext):
    save_review(message.from_user.id, message.text)
    await message.answer("Спасибо за ваш отзыв! Нам важно ваше мнение 💬😊")
    await state.clear()

# Webhook запуск
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
