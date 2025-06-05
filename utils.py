import os
import requests

API_KEY = os.getenv("CRM_API_KEY")
CRM_URL = os.getenv("CRM_URL")


def get_order_by_bot_code_or_phone(code):
    url = f"{CRM_URL}/api/v5/orders"
    headers = {"X-API-KEY": API_KEY}

    # Поиск по bot_code
    params_code = {
        "customFields[bot_code]": code,
        "limit": 1,
            }
    r1 = requests.get(url, params=params_code, headers=headers)
    if r1.ok and r1.json().get("orders"):
        order = r1.json()["orders"][0]
        return {"id": order["id"], "number": order["number"]}

    # Поиск по номеру телефона
    params_phone = {
        "customer[phone]": code,
        "limit": 1,
    }
    r2 = requests.get(url, params=params_phone, headers=headers)
    if r2.ok and r2.json().get("orders"):
        order = r2.json()["orders"][0]
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
    status_exclude = ["complete", "cancelled"] if active else ["new", "assembling", "sent"]
    r = requests.get(url, headers=headers)
    if r.ok:
        orders = r.json().get("orders", [])
        result = []
        for o in orders:
            if active and o["status"] in status_exclude:
                continue
            if not active and o["status"] not in status_exclude:
                continue
            result.append(f"• Заказ {o['number']} от {o['createdAt'][:10]} — {o['statusComment'] or 'без комментария'}")
        if result:
            return "\n".join(result)
        return "📦 Пока нет активных заказов. Я всё проверила 🤍" if active else "📦 Пока нет завершённых заказов. Как только появятся — расскажу ✨"
    return "⚠️ Не удалось загрузить список заказов."


def save_review_to_crm(order_id, comment):
    url = f"{CRM_URL}/api/v5/orders/{order_id}/edit"
    headers = {"X-API-KEY": API_KEY}
    payload = {
        "order": {
            "customFields": {
                "comments": comment
            }
        },
        "site": "missis-suzi"
    }
    requests.post(url, headers=headers, json=payload)
