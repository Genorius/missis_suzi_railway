import os
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import TELEGRAM_TOKEN, WEBHOOK_URL, PORT, ADMIN_TELEGRAM_ID
from keyboards import get_main_keyboard, get_stars_keyboard
from redis_client import is_authorized, authorize_user, get_order_id, get_user_field, clear_auth
from utils import normalize_phone, is_probably_phone, extract_stars_from_callback
from crm import pick_order_by_code_or_phone, get_order_by_id, get_order_status_text, get_tracking_number_text, save_review

# --- Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("missis-suzi-bot")

# --- Bot / Dispatcher
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# --- States
class AuthState(StatesGroup):
    waiting_input = State()

class ReviewState(StatesGroup):
    waiting_comment = State()

class SupportState(StatesGroup):
    waiting_message = State()

# --- Helpers
async def ensure_authorized(message: types.Message) -> bool:
    if is_authorized(message.from_user.id):
        return True
    await message.answer(
        "Чтобы продолжить, авторизуйтесь: введите <b>код заказа (bot_code)</b> или <b>номер телефона</b>."
    )
    await dp.fsm.get_context(message.from_user.id, message.chat.id).set_state(AuthState.waiting_input)
    return False

# --- Handlers
@dp.message(commands={"start"})
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Missis S’Uzi подключена.", reply_markup=None)
    if is_authorized(message.from_user.id):
        await message.answer("Готова помочь по вашему заказу. Выберите действие:", reply_markup=get_main_keyboard())
    else:
        await message.answer(

            "Для доступа к статусу, треку и заказам — авторизуйтесь.\n"

            "Введите <b>bot_code</b> или <b>номер телефона</b> (в любом читаемом формате)."

        )

        await state.set_state(AuthState.waiting_input)

@dp.message(AuthState.waiting_input)
async def auth_input(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    code: Optional[str] = None
    phone: Optional[str] = None

    if is_probably_phone(text):
        phone = normalize_phone(text)
    else:
        code = text

    order = await pick_order_by_code_or_phone(code=code, phone=phone)
    if not order:
        await message.answer("Не нашла заказ по этим данным. Проверьте ввод или пришлите другой код/телефон.")
        return

    order_id = order.get("id") or order.get("number") or order.get("externalId")
    authorize_user(message.from_user.id, order_id=str(order_id), code=code, phone=phone)

    await message.answer("Готово! Доступ открыт 🤝", reply_markup=get_main_keyboard())
    await state.clear()

@dp.callback_query(F.data == "status")
async def cb_status(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_authorized(user_id):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.")
        await callback.answer()
        return
    order_id = get_order_id(user_id)
    order = await get_order_by_id(order_id)
    text = await get_order_status_text(order)
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "track")
async def cb_track(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_authorized(user_id):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.")
        await callback.answer()
        return
    order_id = get_order_id(user_id)
    order = await get_order_by_id(order_id)
    text = await get_tracking_number_text(order)
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "orders")
async def cb_orders(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_authorized(user_id):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.")
        await callback.answer()
        return
    order_id = get_order_id(user_id)
    order = await get_order_by_id(order_id)
    if not order:
        await callback.message.answer("Пока нет активных заказов. Я всё проверила 🤍")
    else:
        num = order.get("number") or order.get("externalId") or order.get("id")
        status = order.get("status") or "unknown"
        await callback.message.answer(f"📋 Текущий заказ: #{num}\nСтатус: {status}")
    await callback.answer()

@dp.callback_query(F.data == "rate")
async def cb_rate(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_authorized(user_id):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.")
        await callback.answer()
        return
    await callback.message.answer("Оцените заказ:", reply_markup=get_stars_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("star:"))
async def cb_star(callback: types.CallbackQuery, state: FSMContext):
    stars = extract_stars_from_callback(callback.data)
    if not stars:
        await callback.answer()
        return
    await state.update_data(stars=stars)
    await state.set_state(ReviewState.waiting_comment)
    await callback.message.answer(
        "Спасибо за оценку! 💫 Напишите, пожалуйста, пару слов — это поможет нам стать лучше."
    )
    await callback.answer()

@dp.message(ReviewState.waiting_comment)
async def review_comment(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.answer("Пожалуйста, сначала авторизуйтесь.")
        return
    order_id = get_order_id(user_id)
    data = await state.get_data()
    stars = int(data.get("stars", 0))
    comment = (message.text or "").strip()

    ok = await save_review(order_id, stars, comment)
    if ok:
        await message.answer("Спасибо! Передала ваш отзыв в работу. Нам очень важно ваше мнение 🤍")
    else:
        await message.answer("Не удалось сохранить отзыв. Попробуйте чуть позже.")
    await state.clear()

@dp.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_message)
    await callback.message.answer("Опишите, пожалуйста, вопрос — я передам его напрямую в поддержку.")
    await callback.answer()

@dp.message(SupportState.waiting_message)
async def support_message(message: types.Message, state: FSMContext):
    user = message.from_user
    text = message.text or "(без текста)"
    admin_id = ADMIN_TELEGRAM_ID
    link = f"tg://user?id={user.id}"
    forwarded = (
        f"🆘 Запрос в поддержку\n"
        f"От: {user.full_name} (@{user.username or '—'}, id={user.id})\n"
        f"Профиль: {link}\n\n"
        f"Сообщение:\n{text}"
    )
    if admin_id:
        try:
            await bot.send_message(chat_id=admin_id, text=forwarded)
        except Exception as e:
            logger.exception("Failed to forward support message: %s", e)
    await message.answer("Отправила запрос. Мы свяжемся с вами в Telegram как можно скорее 🤍")
    await state.clear()

# --- AIOHTTP App / Webhook
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL.rstrip('/') + '/webhook')
    logger.info("Webhook установлен: %s", WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

def build_app() -> web.Application:
    app = web.Application()
    # Health check
    async def ping(request):
        return web.Response(text="ok")
    app.router.add_get("/ping", ping)

    # Aiogram webhook
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    app = build_app()
    web.run_app(app, host="0.0.0.0", port=PORT)