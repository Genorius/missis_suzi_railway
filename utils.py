
import requests
import os

CRM_URL = os.getenv("CRM_URL")
API_KEY = os.getenv("CRM_API_KEY")

def get_order_by_bot_code_or_phone(code):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}

    # 🔍 Поиск по bot_code
    params_code = {
        "customFields[bot_code]": code,
        "limit": 20
    }
    r1 = requests.get(url, headers=headers, params=params_code)
    if r1.ok:
        data = r1.json()
        orders = data.get("orders", [])
        if orders:
            order = orders[0]
            return {"id": order["id"], "number": order["number"]}

    # 📞 Поиск по номеру телефона
    params_phone = {
        "customer[phone]": code,
        "limit": 20
    }
    r2 = requests.get(url, headers=headers, params=params_phone)
    if r2.ok:
        data = r2.json()
        orders = data.get("orders", [])
        if orders:
            order = orders[0]
            return {"id": order["id"], "number": order["number"]}

    return None
