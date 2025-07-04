import requests
from config import CRM_API_KEY, CRM_URL

def get_order_by_bot_code(bot_code):
    r = requests.get(f"{CRM_URL}/api/v5/orders", params={
        'apiKey': CRM_API_KEY,
        'customFields[bot_code]': bot_code
    })
    orders = r.json().get("orders", [])
    return orders[0] if orders else None

def get_orders_by_phone(phone):
    r = requests.get(f"{CRM_URL}/api/v5/orders", params={
        'apiKey': CRM_API_KEY,
        'customer[phones][0][number]': phone
    })
    return r.json().get("orders", [])

def get_order_status(user_id):
    return "Готовится к отправке 📦"

def get_tracking_number(user_id):
    return ""

def save_feedback(order_id, text):
    requests.post(f"{CRM_URL}/api/v5/orders/{order_id}/edit", params={'apiKey': CRM_API_KEY}, json={
        'order': {'customFields': {'comments': text}}
    })