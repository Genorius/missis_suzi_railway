import os
import requests

API_KEY = os.getenv("CRM_API_KEY")
CRM_URL = os.getenv("CRM_URL")

def get_order_by_bot_code_or_phone(code):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}

    print("📡 Ищем заказ по коду:", code)
    print("🔐 API_KEY:", API_KEY)
    print("🌐 CRM_URL:", CRM_URL)

    # Поиск по bot_code
    params_code = {
        "customFields[bot_code]": code,
        "limit": 1
    }
    r1 = requests.get(url, params=params_code, headers=headers)
    print("🔎 Ответ по bot_code:", r1.status_code, r1.text)
    if r1.ok and r1.json().get("orders"):
        order = r1.json()["orders"][0]
        return {"id": order["id"], "number": order["number"]}

    # Поиск по номеру телефона
    params_phone = {
        "customer[phone]": code,
        "limit": 1
    }
    r2 = requests.get(url, params=params_phone, headers=headers)
    print("🔎 Ответ по телефону:", r2.status_code, r2.text)
    if r2.ok and r2.json().get("orders"):
        order = r2.json()["orders"][0]
        return {"id": order["id"], "number": order["number"]}

    return None