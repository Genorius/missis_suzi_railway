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
    print("📡 Ответ по телефону:", r2.status_code, r2.text)
    if r2.ok:
        for order in r2.json().get("orders", []):
            phone = order.get("customer", {}).get("phones", [{}])[0].get("number", "")
            print(f"📞 Проверка телефона в заказе: {phone}")
            if code in phone:
                return {"id": order["id"], "number": order["number"]}

    return None

def get_status_text(order_id):
    url = f"{CRM_URL}/api/v5/orders/{order_id}"
    headers = {"X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers)
    if r.ok:
        order = r.json().get("order", {})
        items = order.get("items", [])
        product_list = "\n".join([f"• {item['offer']['name']}" for item in items]) or "—"
        status = order.get("statusComment") or "Статус уточняется"
        return f"📦 Ваш заказ:\n{product_list}\n\nТекущий статус: {status}"
    return "⚠️ Не удалось получить информацию о заказе. Попробуйте позже."

def get_track_text(order_id):
    url = f"{CRM_URL}/api/v5/orders/{order_id}"
    headers = {"X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers)
    if r.ok:
        order = r.json().get("order", {})
        track = order.get("delivery", {}).get("number")
        if track:
            return (
                f"🚚 Трек-номер: {track}\n"
                f"Проверить можно тут: https://www.cdek.ru/tracking?order_id={track}"
            )
        else:
            return "📭 Пока трек-номер ещё не присвоен — как только он появится, я сразу расскажу!"
    return "⚠️ Не удалось получить информацию о заказе. Попробуйте позже."

def get_orders(active=True):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers)
    if r.ok:
        orders = r.json().get("orders", [])
        result = []
        for o in orders:
            status = o.get("status", "")
            if active and status in ["complete", "cancelled"]:
                continue
            if not active and status not in ["complete", "cancelled"]:
                continue
            result.append(f"• Заказ {o['number']} от {o['createdAt'][:10]} — {o.get('statusComment') or 'без комментария'}")
        if result:
            return "\n".join(result)
        return "📦 Пока нет активных заказов. Я всё проверила 🤍" if active else "📦 Пока нет завершённых заказов. Как только появятся — расскажу ✨"
    return "⚠️ Не удалось загрузить список заказов."