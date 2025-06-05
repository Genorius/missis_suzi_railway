import requests
import os

print("📦 utils.py ИМПОРТИРОВАН — версия от 07.06, фильтр bot_code включён")

CRM_URL = os.getenv("CRM_URL")
API_KEY = os.getenv("CRM_API_KEY")

def get_order_by_bot_code_or_phone(code):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}

    # 1. Поиск по bot_code
    params_code = {
        "customFields[bot_code]": code,
        "limit": 20
    }
    r1 = requests.get(url, headers=headers, params=params_code)
    print("📡 Ответ по bot_code:", r1.status_code, r1.text)
    if r1.ok:
        for order in r1.json().get("orders", []):
            real_code = order.get("customFields", {}).get("bot_code")
            print(f"🔍 Проверка заказа: {order['id']} — bot_code={real_code}")
            if real_code is not None and real_code == code:
                return {"id": order["id"], "number": order["number"]}

    # 2. Поиск по номеру телефона
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