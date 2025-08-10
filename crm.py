import requests
import os

API_KEY = os.getenv("CRM_API_KEY", "pDUAhKJaZZlSXnWtSberXS6PCwfiGP4D")
CRM_URL = os.getenv("CRM_URL", "https://valentinkalinovski.retailcrm.ru")

# Запрос к API
def crm_get(endpoint, params=None):
    url = f"{CRM_URL}/api/v5/{endpoint}"
    if params is None:
        params = {}
    params["apiKey"] = API_KEY
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

# Найти заказ по bot_code или телефону
def pick_order_by_code_or_phone(code_or_phone, telegram_id=None):
    params = {"customFields[bot_code]": code_or_phone}
    orders = crm_get("orders", params).get("orders", [])

    if not orders and code_or_phone.startswith("+"):
        params = {"customer[phone]": code_or_phone}
        orders = crm_get("orders", params).get("orders", [])

    if not orders and telegram_id:
        params = {"customFields[telegram_id]": telegram_id}
        orders = crm_get("orders", params).get("orders", [])

    return orders[0] if orders else None

# Получить текст статуса
def get_order_status_text(telegram_id):
    params = {"customFields[telegram_id]": telegram_id}
    orders = crm_get("orders", params).get("orders", [])
    if not orders:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    status = orders[0].get("statusComment", "Статус не указан")
    return f"📦 Статус вашего заказа: {status}"

# Получить трек-номер
def get_tracking_number_text(telegram_id):
    params = {"customFields[telegram_id]": telegram_id}
    orders = crm_get("orders", params).get("orders", [])
    if not orders:
        return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"
    delivery = orders[0].get("delivery", {})
    track_num = delivery.get("number")
    if track_num:
        return f"🎯 Ваш трек-номер: {track_num}\nОтследить: https://www.cdek.ru/ru/tracking?order_id={track_num}"
    else:
        return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"

# Получить список заказов
def get_orders_list_text(telegram_id):
    params = {"customFields[telegram_id]": telegram_id}
    orders = crm_get("orders", params).get("orders", [])
    if not orders:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    result = "📋 Ваши заказы:\n"
    for o in orders:
        result += f"— #{o.get('number')} ({o.get('statusComment', 'Без статуса')})\n"
    return result.strip()

# Сохранить отзыв
def save_review(telegram_id, review_text):
    params = {"customFields[telegram_id]": telegram_id}
    orders = crm_get("orders", params).get("orders", [])
    if not orders:
        return False
    order_id = orders[0].get("id")
    url = f"{CRM_URL}/api/v5/orders/{order_id}/edit"
    payload = {
        "by": "id",
        "site": orders[0]["site"],
        "apiKey": API_KEY,
        "order": {
            "customFields": {
                "comments": review_text
            }
        }
    }
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return True
