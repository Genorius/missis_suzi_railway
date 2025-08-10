from crm import (
    pick_order_by_code_or_phone,
    get_order_status_text,
    get_tracking_number_text,
    get_orders_list_text,
    save_review
)

# Универсальная функция авторизации
def authorize_user(code_or_phone, telegram_id):
    return pick_order_by_code_or_phone(code_or_phone, telegram_id=telegram_id)

# Получить статус заказа
def fetch_status(telegram_id):
    return get_order_status_text(telegram_id)

# Получить трек-номер
def fetch_track(telegram_id):
    return get_tracking_number_text(telegram_id)

# Получить список заказов
def fetch_orders(telegram_id):
    return get_orders_list_text(telegram_id)

# Сохранить отзыв
def store_review(telegram_id, review_text):
    return save_review(telegram_id, review_text)
