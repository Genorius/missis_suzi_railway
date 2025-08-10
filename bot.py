    import os
    import asyncio
    from typing import List, Dict, Any, Optional

    from aiogram import Bot, Dispatcher, types
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
    from aiogram.dispatcher import FSMContext
    from aiogram.dispatcher.filters.state import State, StatesGroup
    from aiogram.utils.executor import start_webhook
    from aiogram import F

    from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT, ADMIN_CHAT_ID, USE_WEBHOOK
    from keyboards import start_keyboard, main_keyboard, orders_nav, stars_keyboard
    from redis_client import is_authorized, authorize_user, get_order_id, get_user_field, clear_auth, allow_request, cache_orders, get_cached_orders
    from utils import normalize_phone, is_probably_phone, extract_stars_from_callback, human_status
    from crm import fetch_orders_by_bot_code, fetch_orders_by_phone, get_order_by_id, patch_order_comment

    # States
    class AuthStates(StatesGroup):
        waiting_input = State()

    class SupportStates(StatesGroup):
        waiting_message = State()

    bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(bot, storage=MemoryStorage())

    async def guard_rate_limit(event) -> bool:
        user_id = getattr(event.from_user, "id", None)
        return allow_request(user_id) if user_id else True

    @dp.message_handler(commands=["start", "help"])
    async def cmd_start(message: types.Message, state: FSMContext):
        await message.answer(
            "👋 Привет! Это Missis S’Uzi — я помогу со статусом отправления, трек‑номером и заказами.
"
            "Для доступа к функциям — авторизуйтесь.",
            reply_markup=start_keyboard()
        )

    @dp.callback_query_handler(lambda c: c.data == "auth_start")
    async def cb_auth_start(callback: types.CallbackQuery, state: FSMContext):
        if not await guard_rate_limit(callback):
            await callback.answer("Слишком часто. Попробуйте чуть позже.", show_alert=False)
            return
        await callback.message.answer("Введите ваш <b>bot_code</b> или номер телефона (в любом формате).")
        await AuthStates.waiting_input.set()
        await callback.answer()

    @dp.message_handler(state=AuthStates.waiting_input)
    async def auth_process(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()
        user_id = message.from_user.id

        # phone?
        orders: List[Dict[str, Any]] = []
        phone_norm = None
        if is_probably_phone(text):
            phone_norm = normalize_phone(text)
            if not phone_norm:
                await message.answer("Не смог распознать номер. Введите, пожалуйста, корректный номер.")
                return
            orders = await fetch_orders_by_phone(phone_norm)
        else:
            # treat as bot_code
            code = text
            orders = await fetch_orders_by_bot_code(code)

        if not orders:
            await message.answer("Не нашла заказов по этим данным. Проверьте и отправьте ещё раз.")
            return

        # Выбираем последний «активный» или просто последний по списку
        # (упрощённо — RetailCRM обычно сортирует по дате)
        order = orders[0]
        order_id = str(order.get("id") or order.get("externalId") or order.get("number"))

        authorize_user(user_id, order_id, code=text if not phone_norm else None, phone=phone_norm)
        await state.finish()
        await message.answer("Готово! Доступ открыт ✅", reply_markup=main_keyboard())

    @dp.callback_query_handler(lambda c: c.data == "status")
    async def cb_status(callback: types.CallbackQuery, state: FSMContext):
        if not await guard_rate_limit(callback):
            await callback.answer()
            return
        user_id = callback.from_user.id
        if not is_authorized(user_id):
            await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=start_keyboard())
            await callback.answer()
            return
        order_id = get_order_id(user_id)
        order = await get_order_by_id(order_id)
        if not order:
            await callback.message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
            await callback.answer()
            return
        status = human_status(order.get("status") or "unknown")
        num = order.get("number") or order.get("externalId") or order.get("id")
        await callback.message.answer(f"📦 Заказ #{num}
Статус: <b>{status}</b>")
        await callback.answer()

    @dp.callback_query_handler(lambda c: c.data == "track")
    async def cb_track(callback: types.CallbackQuery, state: FSMContext):
        if not await guard_rate_limit(callback):
            await callback.answer()
            return
        user_id = callback.from_user.id
        if not is_authorized(user_id):
            await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=start_keyboard())
            await callback.answer()
            return
        order_id = get_order_id(user_id)
        order = await get_order_by_id(order_id)
        if not order:
            await callback.message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
            await callback.answer()
            return
        delivery = order.get("delivery") or {}
        track = (delivery.get("number") or "").strip()
        if track:
            await callback.message.answer(f"🔎 Трек‑номер: <code>{track}</code>")
        else:
            await callback.message.answer("Пока без трек‑номера — как только появится, я сразу подскажу. 🤍")
        await callback.answer()

    async def list_user_orders(user_id: int) -> List[Dict[str, Any]]:
        # кэш из Redis
        cached = get_cached_orders(user_id)
        if cached:
            return cached
        # иначе ищем по телефону из профиля, потом по коду
        phone = get_user_field(user_id, "phone")
        code = get_user_field(user_id, "code")
        orders: List[Dict[str, Any]] = []
        if phone:
            orders = await fetch_orders_by_phone(phone)
        if not orders and code:
            orders = await fetch_orders_by_bot_code(code)
        if orders:
            # лёгкий кэш
            try:
                cache_orders(user_id, orders, ttl=60)
            except Exception:
                pass
        return orders

    @dp.callback_query_handler(lambda c: c.data == "orders")
    async def cb_orders(callback: types.CallbackQuery, state: FSMContext):
        if not await guard_rate_limit(callback):
            await callback.answer("Слишком часто. Попробуйте чуть позже.", show_alert=False)
            return

        user_id = callback.from_user.id
        if not is_authorized(user_id):
            await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=start_keyboard())
            await callback.answer()
            return

        orders = await list_user_orders(user_id)
        if not orders:
            await callback.message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
            await callback.answer()
            return

        if len(orders) <= 5:
            text = "📋 Ваши заказы:\n\n"
            for o in orders:
                num = o.get("number") or o.get("externalId") or o.get("id")
                status = o.get("status") or "unknown"
                text += f"• #{num} — {status}\n"
            await callback.message.answer(text)
            await callback.answer()
            return

        await show_orders_pagination(callback.message, orders, page=0)
        await callback.answer()

    async def show_orders_pagination(message: types.Message, orders: List[Dict[str, Any]], page: int = 0):
        per_page = 5
        total_pages = (len(orders) + per_page - 1) // per_page
        page_orders = orders[page*per_page:(page+1)*per_page]
        text = "📋 Ваши заказы:\n\n"
        for i, order in enumerate(page_orders, 1):
            num = order.get("number") or order.get("externalId") or order.get("id")
            status = order.get("status") or "unknown"
            text += f"{i}. #{num} - {status}\n"
        text += f"\nСтраница {page+1} из {total_pages}"
        await message.answer(text, reply_markup=orders_nav(page, total_pages))

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("orders_page:"))
    async def cb_orders_page(callback: types.CallbackQuery):
        if not await guard_rate_limit(callback):
            await callback.answer()
            return
        user_id = callback.from_user.id
        orders = await list_user_orders(user_id)
        if not orders:
            await callback.answer()
            return
        try:
            page = int(callback.data.split(":", 1)[1])
        except Exception:
            page = 0
        await show_orders_pagination(callback.message, orders, page=page)
        await callback.answer()

    @dp.callback_query_handler(lambda c: c.data == "support")
    async def cb_support(callback: types.CallbackQuery, state: FSMContext):
        if not await guard_rate_limit(callback):
            await callback.answer()
            return
        if not is_authorized(callback.from_user.id):
            await callback.message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=start_keyboard())
            await callback.answer()
            return
        await callback.message.answer("Опишите, пожалуйста, вопрос. Я передам сообщение в поддержку.")
        await SupportStates.waiting_message.set()
        await callback.answer()

    @dp.message_handler(state=SupportStates.waiting_message, content_types=types.ContentTypes.ANY)
    async def support_collect(message: types.Message, state: FSMContext):
        if ADMIN_CHAT_ID:
            user = message.from_user
            header = f"Заявка в поддержку от @{user.username or 'без_username'} (id {user.id}):"
            try:
                if message.content_type == types.ContentType.TEXT:
                    await bot.send_message(ADMIN_CHAT_ID, f"{header}\n\n{message.text}")
                else:
                    # форвард для нетекста
                    await message.forward(ADMIN_CHAT_ID)
            except Exception:
                pass
        await state.finish()
        await message.answer("Ваше сообщение передала администратору. Он ответит вам в ближайшее время.")

    # Отзыв (звёзды + опциональный комментарий)
    class ReviewStates(StatesGroup):
        waiting_comment = State()
        last_order_id = State()

    @dp.message_handler(commands=["review"])
    async def cmd_review(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        if not is_authorized(user_id):
            await message.answer("Пожалуйста, сначала авторизуйтесь.", reply_markup=start_keyboard())
            return
        order_id = get_order_id(user_id)
        if not order_id:
            await message.answer("📦 Пока нет активных заказов. Я всё проверила 🤍")
            return
        await state.update_data(order_id=order_id)
        await message.answer("Оцените, пожалуйста, заказ.", reply_markup=stars_keyboard())

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("star:"))
    async def cb_stars(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        if not is_authorized(user_id):
            await callback.answer()
            return
        val = extract_stars_from_callback(callback.data)
        data = await state.get_data()
        order_id = data.get("order_id") or get_order_id(user_id)
        await callback.message.answer("Будем рады, если оставите отзыв — нам важно ваше мнение 💬😊\nНапишите пару слов ответным сообщением.")
        await ReviewStates.waiting_comment.set()
        await state.update_data(order_id=order_id, stars=val)
        await callback.answer()

    @dp.message_handler(state=ReviewStates.waiting_comment)
    async def review_comment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_id = data.get("order_id")
        stars = data.get("stars")
        comment = (message.text or "").strip()
        full_comment = f"Оценка: {stars}\nКомментарий: {comment}" if stars else comment
        ok = await patch_order_comment(order_id, full_comment)
        await state.finish()
        if ok:
            await message.answer("Спасибо! Отзыв сохранён. 🤍")
        else:
            await message.answer("Не смогла сохранить отзыв из‑за технической ошибки, но уже передала сигнал. Попробуйте позже.")

    # ====== RUNNER ======
    WEBHOOK_PATH = "/telegram"

    async def on_startup(dp: Dispatcher):
        if USE_WEBHOOK and WEBHOOK_URL:
            await bot.set_webhook(WEBHOOK_URL.rstrip('/') + WEBHOOK_PATH)

    async def on_shutdown(dp: Dispatcher):
        try:
            await bot.delete_webhook()
        except Exception:
            pass

    def main():
        if USE_WEBHOOK and WEBHOOK_URL:
            start_webhook(
                dispatcher=dp,
                webhook_path=WEBHOOK_PATH,
                on_startup=on_startup,
                on_shutdown=on_shutdown,
                skip_updates=True,
                host="0.0.0.0",
                port=int(os.getenv("PORT", 8080)),
            )
        else:
            from aiogram import executor
            executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)

    if __name__ == "__main__":
        main()
