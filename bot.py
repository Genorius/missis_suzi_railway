from aiogram import Bot, Dispatcher, F, Router, types, html
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
import os

from utils import get_order_by_bot_code_or_phone, get_status_text, get_track_text, get_orders, save_review_to_crm
from auth_db import save_user_auth, get_order_id_by_user_id
from keyboards import get_main_keyboard, get_orders_keyboard, get_stars_keyboard

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
PORT = int(os.environ.get("PORT", 8080))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class AuthState(StatesGroup):
    waiting_for_code = State()
    waiting_for_review = State()

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await message.answer("👋 Привет! Я Missis S’Uzi. Чтобы узнать о вашем заказе — пришлите код или номер телефона 📦")
    await state.set_state(AuthState.waiting_for_code)

@router.message(AuthState.waiting_for_code)
async def process_auth(message: Message, state: FSMContext):
    user_input = message.text.strip()
    order = get_order_by_bot_code_or_phone(user_input)
    if order:
        save_user_auth(message.from_user.id, order["id"])
        await message.answer("✅ Готово! Теперь вы можете управлять заказом:", reply_markup=get_main_keyboard())
        await state.clear()
    else:
        count = int((await state.get_data()).get("fail_count", 0)) + 1
        await state.update_data(fail_count=count)
        if count >= 3:
            await message.answer("Очень жаль, что не получается войти 😔 Наверняка есть веская причина, и я обязательно с этим разберусь!\n\nНажмите, пожалуйста, кнопку <b>Поддержка</b> — и я сразу начну искать способ Вам помочь 🤍")
            await notify_admin_about_failed_auth(message)
        else:
            await message.answer("❌ Увы, я не нашла заказ по этому коду или номеру телефона. Попробуйте ещё раз — я рядом ❤️")

async def notify_admin_about_failed_auth(message: Message):
    text = f"❗️ Клиент не смог авторизоваться:\n<code>{html.quote(message.text)}</code>\nTelegram: @{message.from_user.username or 'нет'} / {message.from_user.id}"
    await bot.send_message(chat_id=ADMIN_USERNAME, text=text)

@router.callback_query(F.data == "status")
async def status_handler(callback: types.CallbackQuery):
    order_id = get_order_id_by_user_id(callback.from_user.id)
    text = get_status_text(order_id) if order_id else "⚠️ Не найден заказ, попробуйте снова авторизоваться."
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "track")
async def track_handler(callback: types.CallbackQuery):
    order_id = get_order_id_by_user_id(callback.from_user.id)
    text = get_track_text(order_id) if order_id else "⚠️ Не найден заказ, попробуйте снова авторизоваться."
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "orders")
async def orders_handler(callback: types.CallbackQuery):
    await callback.message.answer("Что показать?", reply_markup=get_orders_keyboard())
    await callback.answer()

@router.callback_query(F.data.in_(["orders_active", "orders_past"]))
async def show_orders(callback: types.CallbackQuery):
    active = callback.data == "orders_active"
    await callback.message.answer(get_orders(active=active))
    await callback.answer()

@router.callback_query(F.data == "rate")
async def rate_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Оцените, пожалуйста, как прошёл ваш заказ ⭐️", reply_markup=get_stars_keyboard())
    await state.set_state(AuthState.waiting_for_review)
    await callback.answer()

@router.callback_query(F.data.startswith("⭐"))
async def handle_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = callback.data
    await callback.message.answer(f"Спасибо за вашу оценку: {rating} ⭐️ А хотите оставить пару слов? Мне правда важно это услышать 🫶 Просто напишите сюда 💬")
    await callback.answer()

@router.message(AuthState.waiting_for_review)
async def save_review(message: Message, state: FSMContext):
    order_id = get_order_id_by_user_id(message.from_user.id)
    if order_id:
        save_review_to_crm(order_id, message.text)
        await message.answer("💌 Спасибо! Я всё прочитала и учту обязательно 🤍")
    else:
        await message.answer("⚠️ Не удалось определить заказ. Попробуйте позже.")
    await state.clear()

@router.callback_query(F.data == "support")
async def support_handler(callback: types.CallbackQuery):
    await callback.message.answer("Напишите, пожалуйста, с чем нужна помощь — я передам всё нашему заботливому специалисту 🤍")
    await bot.send_message(chat_id=ADMIN_USERNAME, text="📬 Клиент обратился в поддержку:\n" + callback.message.text)
    await callback.answer()

# Webhook и сервер
async def webhook_handler(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def ping(request):
    return web.Response(text="pong")

async def on_startup(app):
    webhook_url = os.getenv("WEBHOOK_URL")
    await bot.set_webhook(webhook_url)
    print("🚀 on_startup вызван")
    print(f"✅ Вебхук установлен: {webhook_url}")

app = web.Application()
app.router.add_post("/webhook", webhook_handler)
app.router.add_get("/ping", ping)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    print("✅ Bot is starting manually on aiohttp...")
    web.run_app(app, host="0.0.0.0", port=PORT)