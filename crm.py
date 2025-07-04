import requests
from config import CRM_API_KEY, CRM_URL
from redis_client import get_user_phone, get_user_order, save_user_context

def get_order_by_bot_code(bot_code):
    r = requests.get(f"{CRM_URL}/api/v5/orders", params={
        'apiKey': CRM_API_KEY,
        'customFields[bot_code]': bot_code
    })
    orders = r.json().get("orders", [])
    if orders:
        phone = orders[0].get('customer', {}).get('phones', [{}])[0].get('number')
        save_user_context(orders[0]['id'], phone)
    return orders[0] if orders else None

def get_order_status(user_id):
    order_id = get_user_order()
    if not order_id:
        return "Нет активного заказа"
    r = requests.get(f"{CRM_URL}/api/v5/orders/{order_id}", params={'apiKey': CRM_API_KEY})
    return r.json().get("order", {}).get("status", "неизвестен")

def get_tracking_number(user_id):
    order_id = get_user_order()
    if not order_id:
        return None
    r = requests.get(f"{CRM_URL}/api/v5/orders/{order_id}", params={'apiKey': CRM_API_KEY})
    return r.json().get("order", {}).get("delivery", {}).get("number")

def get_orders_by_phone(user_id=None):
    phone = get_user_phone()
    if not phone:
        return []
    r = requests.get(f"{CRM_URL}/api/v5/orders", params={
        'apiKey': CRM_API_KEY,
        'customer[phones][0][number]': phone
    })
    return r.json().get("orders", [])