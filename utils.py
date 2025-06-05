
import os
import requests

CRM_URL = os.getenv("CRM_URL")
API_KEY = os.getenv("CRM_API_KEY")

def get_order_by_bot_code_or_phone(code):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}

    print("📡 Проверка кода:", code)

    params_code = {
        "customFields[bot_code]": code,
        "limit": 20
    }
    r1 = requests.get(url, headers=headers, params=params_code)
    print("🔍 Ответ по bot_code:", r1.status_code, r1.text)
    if r1.ok and r1.json().get("orders"):
        order = r1.json()["orders"][0]
        return {"id": order["id"], "number": order["number"]}

    params_phone = {
        "customer[phone]": code,
        "limit": 20
    }
    r2 = requests.get(url, headers=headers, params=params_phone)
    print("📞 Ответ по телефону:", r2.status_code, r2.text)
    if r2.ok and r2.json().get("orders"):
        order = r2.json()["orders"][0]
        return {"id": order["id"], "number": order["number"]}

    print("❌ Заказ не найден.")
    return None
