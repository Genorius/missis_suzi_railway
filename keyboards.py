from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def start_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Авторизоваться", callback_data="auth_start")],
    ])
    return kb

def main_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статус отправления", callback_data="status")],
        [InlineKeyboardButton(text="Трек-номер", callback_data="track")],
        [InlineKeyboardButton(text="Мои заказы", callback_data="orders")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")],
    ])
    return kb

def orders_nav(page: int, total_pages: int) -> InlineKeyboardMarkup:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="← Назад", callback_data=f"orders_page:{page-1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="Вперёд →", callback_data=f"orders_page:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[row] if row else [])

def stars_keyboard() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text="★", callback_data="star:1"),
        InlineKeyboardButton(text="★★", callback_data="star:2"),
        InlineKeyboardButton(text="★★★", callback_data="star:3"),
        InlineKeyboardButton(text="★★★★", callback_data="star:4"),
        InlineKeyboardButton(text="★★★★★", callback_data="star:5"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])
