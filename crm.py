
import os
import requests
from redis_client import get_user_context

CRM_API_KEY = os.getenv("CRM_API_KEY")
CRM_BASE_URL = os.getenv("CRM_BASE_URL")

headers = {
    "Content-Type": "application/json",
    "X-Api-Key": CRM_API_KEY
}

def get_order_by_bot_code(bot_code):
    response = requests.get(
        f"{CRM_BASE_URL}/api/v5/orders",
        headers=headers,
        params={"customFields[bot_code]": bot_code}
    )
    orders = response.json().get("orders", [])
    return orders[0] if orders else None

def get_orders_by_phone(user_id):
    phone = get_user_context(user_id, "phone")
    if not phone:
        return []
    response = requests.get(
        f"{CRM_BASE_URL}/api/v5/orders",
        headers=headers,
        params={"customer[phone]": phone}
    )
    return response.json().get("orders", [])

def get_order_status(user_id):
    order = get_order_by_bot_code(get_user_context(user_id, "code"))
    return order["status"] if order else None

def get_tracking_number(user_id):
    order = get_order_by_bot_code(get_user_context(user_id, "code"))
    return order.get("delivery", {}).get("number")
