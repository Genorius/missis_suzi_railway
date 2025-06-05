import os
import requests

API_KEY = os.getenv("CRM_API_KEY")
CRM_URL = os.getenv("CRM_URL")

def get_order_by_bot_code_or_phone(code: str):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}

    print("📡 Ищем заказ по коду:", code)
    print("🔐 API_KEY:", API_KEY)
    print("🌐 CRM_URL:", CRM_URL)

    # Сначала проверим, не похоже ли это на номер телефона
    is_phone = code.strip().startswith("+") or code.strip().isdigit()

    if is_phone:
        params = {
            "customer[phone]": code,
            "limit": 50,
        }
    else:
        params = {
            "customFields[bot_code]": code,
            "limit": 50,
        }

    response = requests.get(url, headers=headers, params=params)
    print("📥 Ответ CRM:", response.status_code, response.text)

    if response.ok:
        orders = response.json().get("orders", [])
        for order in orders:
            if not is_phone:
                # Проверка, что bot_code в заказе точно совпадает
                if order.get("customFields", {}).get("bot_code") != code:
                    continue
            return {"id": order["id"], "number": order["number"]}

    return None
