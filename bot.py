
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from crm import (
    pick_order_by_code_or_phone,
    get_order_by_id,
    get_order_status_text_by_id,
    get_tracking_number_text_by_id,
    get_orders_list_text_by_customer_id,
    save_review_by_order_id,
    save_telegram_id_for_order,
    clear_telegram_id_for_order
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class AuthStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_review = State()
    waiting_support_message = State()

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Статус отправления", callback_data="status")],
        [InlineKeyboardButton(text="🎯 Трек-номер", callback_data="track")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="orders")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ])

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я Missis S'Uzi — помогу узнать статус вашего заказа.\n"
        "Введите, пожалуйста, ваш bot_code или номер телефона 🤍"
    )
    await state.set_state(AuthStates.waiting_for_code)

@dp.message(Command("logout"))
async def logout_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вышли из авторизации. Введите bot_code или номер телефона, чтобы продолжить 🤍")
    await state.set_state(AuthStates.waiting_for_code)

@dp.message(Command("debug"))
async def debug_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(f"debug:\nstate={await state.get_state()}\norder_id={data.get('order_id')}\ncustomer_id={data.get('customer_id')}")

@dp.message(StateFilter(AuthStates.waiting_for_code))
async def process_auth(message: types.Message, state: FSMContext):
    code_or_phone = (message.text or "").strip()
    order = pick_order_by_code_or_phone(code_or_phone)
    if not order:
        await message.answer(
            "❌ Не удалось найти заказ по введённым данным. Проверьте bot_code или телефон и попробуйте снова."
        )
        return

    try:
        save_telegram_id_for_order(order["id"], message.from_user.id, site=order.get("site"))
    except Exception as e:
        logging.warning("Save telegram_id failed: %s", e)

    await state.update_data(order_id=order["id"], customer_id=(order.get("customer") or {}).get("id"))
    # Завершаем состояние, но сохраняем данные
    await state.set_state(None)

    await message.answer("✅ Авторизация успешна! Что хотите узнать?", reply_markup=get_main_keyboard())

async def ensure_authorized(callback: types.CallbackQuery, state: FSMContext) -> bool:
    data = await state.get_data()
    if not data.get("order_id"):
        await callback.message.answer(
            "Чтобы продолжить, пожалуйста, введите ваш bot_code или номер телефона 🤍"
        )
        await state.set_state(AuthStates.waiting_for_code)
        await callback.answer()
        return False
    return True

@dp.callback_query(F.data == "status")
async def order_status_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_authorized(callback, state):
        return
    data = await state.get_data()
    order_id = data["order_id"]
    text = get_order_status_text_by_id(order_id)
    await callback.message.answer(text, reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "track")
async def tracking_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_authorized(callback, state):
        return
    data = await state.get_data()
    order_id = data["order_id"]
    text = get_tracking_number_text_by_id(order_id)
    await callback.message.answer(text, reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "orders")
async def orders_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_authorized(callback, state):
        return
    data = await state.get_data()
    customer_id = data.get("customer_id")
    if customer_id:
        text = get_orders_list_text_by_customer_id(customer_id)
    else:
        o = get_order_by_id(data["order_id"])
        status = o.get("statusComment") or o.get("status") or "Без статуса"
        text = f"📋 Ваши заказы:\n— #{o.get('number')} ({status})"
    await callback.message.answer(text, reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_authorized(callback, state):
        return
    await state.set_state(AuthStates.waiting_support_message)
    await callback.message.answer(
        "💬 Напишите, пожалуйста, ваш вопрос одним сообщением — я всё передам администратору 🤍",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.message(StateFilter(AuthStates.waiting_support_message))
async def support_message_receiver(message: types.Message, state: FSMContext):
    uname = f"@{message.from_user.username}" if message.from_user.username else f"id {message.from_user.id}"
    await bot.send_message(ADMIN_ID, f"🆘 Запрос поддержки от {uname}:\n{message.text}")
    await message.answer("Спасибо! Передала сообщение. Мы ответим как можно скорее 🤍",
                         reply_markup=get_main_keyboard())
    await state.set_state(None)

@dp.message(StateFilter(AuthStates.waiting_for_review))
async def review_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id:
        save_review_by_order_id(order_id, message.text)
    await message.answer("Спасибо за ваш отзыв! Нам важно ваше мнение 💬😊", reply_markup=get_main_keyboard())
    await state.set_state(None)

@dp.message(Command("unlink"))
async def unlink_handler(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Команда доступна только администратору.")
        return
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("Нет выбранного заказа в сессии.")
        return
    try:
        clear_telegram_id_for_order(order_id)
        await message.answer("Привязка telegram_id к заказу очищена.")
    except Exception as e:
        await message.answer(f"Ошибка при очистке привязки: {e}")

async def on_startup(app):
    url = WEBHOOK_URL
    if not url.endswith(WEBHOOK_PATH):
        url = url.rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(url)

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
