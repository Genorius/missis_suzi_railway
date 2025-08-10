import logging
from typing import List, Dict, Any

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT, USE_WEBHOOK, ADMIN_CHAT_ID
from utils import normalize_phone, human_status
from crm import fetch_orders_by_bot_code, fetch_orders_by_phone, get_order_by_id, patch_order_comment

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("missis_suzi_bot")

# In-memory auth (для простоты и стабильного старта)
AUTH: Dict[int, Dict[str, str]] = {}

# Safety check for token
if not TELEGRAM_BOT_TOKEN or ":" not in TELEGRAM_BOT_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN пустой/неверный. Задайте корректный токен в переменных окружения.")

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

class AuthStates(StatesGroup):
    waiting_input = State()

class SupportStates(StatesGroup):
    waiting_message = State()

class ReviewStates(StatesGroup):
    waiting_stars = State()
    waiting_comment = State()

WEBHOOK_PATH = "/telegram"  # фиксированный путь вебхука

def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Авторизоваться", callback_data="auth_start")
    ]])

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статус отправления", callback_data="status")],
        [InlineKeyboardButton(text="Трек-номер", callback_data="track")],
        [InlineKeyboardButton(text="Мои заказы", callback_data="orders")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")],
    ])

def kb_stars() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text="★", callback_data="star:1"),
        InlineKeyboardButton(text="★★", callback_data="star:2"),
        InlineKeyboardButton(text="★★★", callback_data="star:3"),
        InlineKeyboardButton(text="★★★★", callback_data="star:4"),
        InlineKeyboardButton(text="★★★★★", callback_data="star:5"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])

@dp.message_handler(commands=["start", "help"])
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "👋 Привет! Это Missis S’Uzi — я помогу со статусом отправления, трек‑номером и заказами.\n"
        "Для доступа к функциям — авторизуйтесь.",
        reply_markup=kb_start()
    )

@dp.callback_query_handler(lambda c: c.data == "auth_start")
async def cb_auth_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ваш <b>bot_code</b> или номер телефона.")
    await AuthStates.waiting_input.set()
    await callback.answer()

@dp.message_handler(state=AuthStates.waiting_input)
async def cb_auth_input(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    orders: List[Dict[str, Any]] = []

    phone = normalize_phone(text)
    if phone:
        orders = await fetch_orders_by_phone(phone)
    else:
        orders = await fetch_orders_by_bot_code(text)

    if not orders:
        await message.answer("Не нашла заказов по этим данным. Проверьте и отправьте ещё раз.")
        return

    order = orders[0]
    order_id = str(order.get("id") or order.get("externalId") or order.get("number"))

    AUTH[message.from_user.id] = {"order_id": order_id, "phone": phone or "", "code": "" if phone else text}

    await state.finish()
    await message.answer("Готово! Доступ открыт ✅", reply_markup=kb_main())

def _need_auth(user_id: int) -> bool:
    return user_id not in AUTH

@dp.callback_query_handler(lambda c: c.data == "status")
async def cb_status(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if _need_auth(uid):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=kb_start())
        return await callback.answer()

    order_id = AUTH[uid]["order_id"]
    order = await get_order_by_id(order_id)
    if not order:
        await callback.message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
        return await callback.answer()

    status = human_status(order.get("status") or "unknown")
    num = order.get("number") or order.get("externalId") or order.get("id")
    await callback.message.answer(f"📦 Заказ #{num}\nСтатус: <b>{status}</b>")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "track")
async def cb_track(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if _need_auth(uid):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=kb_start())
        return await callback.answer()

    order_id = AUTH[uid]["order_id"]
    order = await get_order_by_id(order_id)
    if not order:
        await callback.message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
        return await callback.answer()

    delivery = order.get("delivery") or {}
    track = (delivery.get("number") or "").strip()
    if track:
        await callback.message.answer(f"🔎 Трек‑номер: <code>{track}</code>")
    else:
        await callback.message.answer("Пока без трек‑номера — как только появится, я сразу подскажу. 🤍")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "orders")
async def cb_orders(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if _need_auth(uid):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=kb_start())
        return await callback.answer()

    phone = AUTH[uid].get("phone") or ""
    code = AUTH[uid].get("code") or ""
    orders = []
    if phone:
        orders = await fetch_orders_by_phone(phone)
    if not orders and code:
        orders = await fetch_orders_by_bot_code(code)

    if not orders:
        await callback.message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
        return await callback.answer()

    text = "📋 Ваши заказы:\n\n"
    for o in orders[:10]:
        num = o.get("number") or o.get("externalId") or o.get("id")
        status = o.get("status") or "unknown"
        text += f"• #{num} — {status}\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "support")
async def cb_support(callback: types.CallbackQuery, state: FSMContext):
    if _need_auth(callback.from_user.id):
        await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=kb_start())
        return await callback.answer()
    await callback.message.answer("Опишите, пожалуйста, вопрос. Я передам сообщение в поддержку.")
    await SupportStates.waiting_message.set()
    await callback.answer()

@dp.message_handler(state=SupportStates.waiting_message, content_types=types.ContentTypes.ANY)
async def support_relay(message: types.Message, state: FSMContext):
    if ADMIN_CHAT_ID:
        user = message.from_user
        try:
            header = f"Заявка в поддержку от @{user.username or 'без_username'} (id {user.id}):"
            if message.content_type == types.ContentType.TEXT:
                await bot.send_message(ADMIN_CHAT_ID, f"{header}\n\n{message.text}")
            else:
                await message.forward(ADMIN_CHAT_ID)
        except Exception:
            pass
    await state.finish()
    await message.answer("Ваше сообщение передала администратору. Он ответит вам в ближайшее время.")

# Отзыв
@dp.message_handler(commands=["review"])
async def cmd_review(message: types.Message, state: FSMContext):
    if _need_auth(message.from_user.id):
        return await message.reply("Пожалуйста, сначала авторизуйтесь.", reply_markup=kb_start())
    await message.answer("Оцените, пожалуйста, заказ.", reply_markup=kb_stars())
    await ReviewStates.waiting_stars.set()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("star:"), state=ReviewStates.waiting_stars)
async def cb_stars(callback: types.CallbackQuery, state: FSMContext):
    stars = callback.data.split(":", 1)[1]
    await state.update_data(stars=stars)
    await callback.message.answer("Будем рады, если оставите отзыв — нам важно ваше мнение 💬😊\nНапишите пару слов ответным сообщением.")
    await ReviewStates.waiting_comment.set()
    await callback.answer()

@dp.message_handler(state=ReviewStates.waiting_comment)
async def review_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    stars = data.get("stars") or ""
    uid = message.from_user.id
    order_id = (AUTH.get(uid) or {}).get("order_id")
    comment = (message.text or "").strip()
    full = f"Оценка: {stars}\nКомментарий: {comment}" if stars else comment
    ok = await patch_order_comment(order_id, full)
    await state.finish()
    if ok:
        await message.answer("Спасибо! Отзыв сохранён. 🤍")
    else:
        await message.answer("Не смогла сохранить отзыв из‑за технической ошибки, но уже передала сигнал. Попробуйте позже.")

# Startup / Shutdown
async def on_startup(dp: Dispatcher):
    if USE_WEBHOOK:
        if not WEBHOOK_URL:
            log.error("WEBHOOK_URL пустой. Укажите переменную окружения WEBHOOK_URL.")
            raise SystemExit("WEBHOOK_URL пустой. Укажите переменную окружения WEBHOOK_URL.")
        final_url = WEBHOOK_URL.rstrip('/') + WEBHOOK_PATH
        log.info("Устанавливаю вебхук на: %s", final_url)
        await bot.set_webhook(final_url)

async def on_shutdown(dp: Dispatcher):
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    log.info("Бот остановлен.")

def main():
    if USE_WEBHOOK:
        start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True,
            host="0.0.0.0",
            port=PORT,
        )
    else:
        from aiogram import executor
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)

if __name__ == "__main__":
    main()
