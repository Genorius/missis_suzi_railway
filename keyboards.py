from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статус отправления", callback_data="status")],
        [InlineKeyboardButton(text="Трек-номер", callback_data="track")],
        [InlineKeyboardButton(text="Мои заказы", callback_data="orders")],
        [InlineKeyboardButton(text="Оценить заказ", callback_data="rate")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ])

def get_orders_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Активные заказы", callback_data="orders_active")],
        [InlineKeyboardButton(text="Прошлые заказы", callback_data="orders_past")]
    ])

def get_stars_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐1", callback_data="star:1"),
            InlineKeyboardButton(text="⭐2", callback_data="star:2"),
            InlineKeyboardButton(text="⭐3", callback_data="star:3"),
            InlineKeyboardButton(text="⭐4", callback_data="star:4"),
            InlineKeyboardButton(text="⭐5", callback_data="star:5"),
        ]
    ])
