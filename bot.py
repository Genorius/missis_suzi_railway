import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import BOT_TOKEN, WEBHOOK_URL, CRM_URL, API_KEY
from redis_client import redis
from utils import get_order_by_bot_code_or_phone, get_status_text, get_track_text, get_orders, save_review_to_crm

print(f"ENV: BOT_TOKEN={BOT_TOKEN[:10]}..., WEBHOOK_URL={WEBHOOK_URL}, CRM_URL={CRM_URL}")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AuthState(StatesGroup):
    waiting_for_code = State()

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Я бот Missis S’Uzi.\n\nПожалуйста, введите ваш код заказа или номер телефона 📱")
    await state.set_state(AuthState.waiting_for_code)

@dp.message_handler(state=AuthState.waiting_for_code)
async def auth_handler(message: types.Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    order = await get_order_by_bot_code_or_phone(code)
    if order:
        redis.set(str(user_id), order['id'])
        await state.finish()
        await message.answer(
            f"✨ Добро пожаловать! Заказ найден:\n<b>{order['number']}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("📦 Статус отправления", callback_data="status")],
                [InlineKeyboardButton("🔍 Трек-номер", callback_data="track")],
                [InlineKeyboardButton("📋 Мои заказы", callback_data="orders")],
                [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
            ])
        )
    else:
        await message.answer("❗️Упс! Заказ не найден. Попробуйте ещё раз.")

@dp.callback_query_handler(lambda c: c.data in ["status", "track", "orders", "support"])
async def callback_handler(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    order_id = redis.get(user_id)

    if not order_id:
        await callback_query.message.answer("🔒 Вы не авторизованы. Пожалуйста, отправьте /start")
        return

    if callback_query.data == "status":
        text = await get_status_text(order_id)
        await callback_query.message.answer(text)
    elif callback_query.data == "track":
        text = await get_track_text(order_id)
        await callback_query.message.answer(text)
    elif callback_query.data == "orders":
        text = await get_orders(order_id)
        await callback_query.message.answer(text)
    elif callback_query.data == "support":
        await callback_query.message.answer("🧑‍💬 Напишите ваш вопрос, и мы обязательно ответим!")

@dp.message_handler()
async def echo_all(message: types.Message):
    print(f"📥 Получено сообщение: {message.text}")
    await message.answer("🟢 Бот получил это сообщение!")

async def on_startup(dp):
    print(f"📡 Устанавливаем webhook: {WEBHOOK_URL}")
    success = await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {success}")
    info = await bot.get_webhook_info()
    print(f"🔍 Webhook Telegram сейчас указывает на: {info.url}")

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path='',
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
    )