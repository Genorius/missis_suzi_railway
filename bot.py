
import os
import re
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
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
    debug_probe
)

# Logs
logging.basicConfig(level=logging.INFO)
logging.getLogger("aiogram").setLevel(logging.INFO)

# ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

ADMIN_ID_RAW = os.getenv("ADMIN_ID")
def _parse_admin_id(val: str | None):
    if not val:
        return None
    val = val.strip()
    if re.fullmatch(r"-?\d+", val):
        try:
            return int(val)
        except Exception:
            return None
    return None
ADMIN_ID = _parse_admin_id(ADMIN_ID_RAW)

DROP_UPDATES_ON_START = os.getenv("DROP_UPDATES_ON_START", "true").lower() == "true"

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

def _is_admin(user_id: int) -> bool:
    return ADMIN_ID is not None and user_id == ADMIN_ID

async def is_authed(state: FSMContext) -> bool:
    data = await state.get_data()
    return bool(data.get("order_id"))

@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    logging.info("START from %s", message.from_user.id)
    await state.clear()
    await message.answer(
        "👋 Привет! Я Missis S'Uzi — помогу узнать статус вашего заказа.\n"
        "Введите, пожалуйста, ваш bot_code или номер телефона 🤍"
    )
    await state.set_state(AuthStates.waiting_for_code)

@dp.message(Command("ping"))
async def ping_handler(message: types.Message):
    await message.answer("pong ✅")

@dp.message(Command("myid"))
async def myid_handler(message: types.Message):
    await message.answer(f"Ваш chat_id: {message.chat.id}")

# ---------- PROBE: admin-only command ----------
async def _run_probe(message: types.Message, raw_value: str):
    value = (raw_value or "").strip()
    if not value:
        await message.answer("Использование: /probe 7488  или  /probe +7XXXXXXXXXX")
        return
    logging.info("PROBE by %s: %s", message.from_user.id, value)
    try:
        report = debug_probe(value)
    except Exception as e:
        logging.exception("probe failed")
        await message.answer(f"Проверка упала: {e}")
        return

    lines = []
    lines.append("🔎 PROBE-результат:")
    lines.append(f"• Ввод: {report.get('input')}")
    lines.append(f"• Нормализованный телефон: {report.get('normalized_phone') or '—'}")
    by_code = report.get('by_code') or {}
    lines.append(f"• Найдено заказов по bot_code: {by_code.get('count', 0)}")
    first = by_code.get('first')
    if first:
        lines.append(f"   └ первый: id={first.get('id')} №{first.get('number')} site={first.get('site')} bot_code={first.get('bot_code')}")
    by_phone = report.get('by_phone') or {}
    lines.append(f"• Найдено клиентов по телефону: {by_phone.get('customers_count', 0)}")
    fc = by_phone.get('first_customer') or {}
    if fc:
        lines.append(f"   └ первый клиент: id={fc.get('id')} name={(fc.get('firstName') or '')} {(fc.get('lastName') or '')}".strip())
    lines.append(f"• Найдено заказов по customerId: {by_phone.get('orders_count', 0)}")
    fo = by_phone.get('first_order') or {}
    if fo:
        lines.append(f"   └ первый заказ: id={fo.get('id')} №{fo.get('number')} site={fo.get('site')}")
    lines.append(f"• Выбранный заказ: {report.get('picked') or '—'}")
    lines.append("")
    lines.append("Если по коду/телефону ноль результатов: проверьте в CRM, что:")
    lines.append("— код поля именно customFields.bot_code (или задайте CRM_BOT_CODE_FIELD);")
    lines.append("— это именно заказ (а не лид/обращение);")
    lines.append("— телефон в формате +7XXXXXXXXXX;")
    lines.append("— сайт заказа доступен текущему apiKey.")
    await message.answer("\n".join(lines))

@dp.message(Command("probe"))
async def probe_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        await message.answer("Команда доступна только администратору.")
        return
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1] if len(parts) > 1 else ""
    await _run_probe(message, arg)

# Text fallback: "probe <value>"
@dp.message(F.text.regexp(r"^\s*probe\s+(.+)$"))
async def probe_text_handler(message: types.Message, regexp: types.Message):
    if not _is_admin(message.from_user.id):
        return
    m = re.match(r"^\s*probe\s+(.+)$", message.text, flags=re.I)
    if not m:
        return
    await _run_probe(message, m.group(1))

@dp.message(StateFilter(AuthStates.waiting_for_code), F.text)
async def process_auth(message: types.Message, state: FSMContext):
    code_or_phone = (message.text or "").strip()
    logging.info("AUTH attempt from %s: %s", message.from_user.id, code_or_phone)
    if not code_or_phone:
        await message.answer("Введите, пожалуйста, bot_code или номер телефона 🤍")
        return

    await message.answer("Ищу ваш заказ… секунду, пожалуйста 🤍")

    try:
        order = pick_order_by_code_or_phone(code_or_phone)
    except Exception as e:
        logging.exception("Auth CRM error")
        await message.answer("Сейчас не получается подключиться к CRM. Попробуйте ещё раз через минуту 🤍")
        return

    if not order:
        logging.info("AUTH not found for %s", message.from_user.id)
        await message.answer(
            "❌ Не нашла заказ по введённым данным.\n"
            "Проверьте bot_code или введите номер телефона в формате +7XXXXXXXXXX 🤍"
        )
        return

    try:
        save_telegram_id_for_order(order["id"], message.from_user.id, site=order.get("site"))
    except Exception as e:
        logging.warning("Save telegram_id failed: %s", e)

    await state.update_data(order_id=order["id"], customer_id=(order.get("customer") or {}).get("id"))
    await state.set_state(None)

    await message.answer("✅ Авторизация успешна! Что хотите узнать?", reply_markup=get_main_keyboard())

async def ensure_authorized(callback: types.CallbackQuery, state: FSMContext) -> bool:
    if not await is_authed(state):
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

@dp.message(StateFilter(AuthStates.waiting_support_message), F.text)
async def support_message_receiver(message: types.Message, state: FSMContext):
    uname = f"@{message.from_user.username}" if message.from_user.username else f"id {message.from_user.id}"
    if ADMIN_ID is not None:
        try:
            await bot.send_message(ADMIN_ID, f"🆘 Запрос поддержки от {uname}:\n{message.text}")
        except Exception as e:
            logging.warning("Failed to deliver support message to ADMIN_ID=%r: %s", ADMIN_ID, e)
    else:
        logging.warning("ADMIN_ID is invalid or not set (value=%r); skipping admin notification", ADMIN_ID_RAW)
    await message.answer("Спасибо! Передала сообщение. Мы ответим как можно скорее 🤍",
                         reply_markup=get_main_keyboard())
    await state.set_state(None)

# Health endpoint
async def health(request: web.Request):
    return web.json_response({"ok": True})

async def on_startup(app):
    try:
        url = WEBHOOK_URL
        if not url.endswith(WEBHOOK_PATH):
            url = url.rstrip("/") + WEBHOOK_PATH
        await bot.set_webhook(
            url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=DROP_UPDATES_ON_START,
        )
        logging.info("Webhook set to: %s", url)
    except Exception as e:
        logging.exception("Failed to set webhook: %s", e)
        raise

async def on_shutdown(app):
    await bot.delete_webhook()
    try:
        await bot.session.close()
    except Exception as e:
        logging.warning("Failed to close bot session: %s", e)

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/")
    app.router.add_get("/healthz", health)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
