
import os
import requests

API_KEY = os.getenv("CRM_API_KEY", "pDUAhKJaZZlSXnWtSberXS6PCwfiGP4D")
CRM_URL = os.getenv("CRM_URL", "https://valentinkalinovski.retailcrm.ru")

def crm_get(endpoint, params=None):
    url = f"{CRM_URL}/api/v5/{endpoint}"
    params = params or {}
    params["apiKey"] = API_KEY
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def crm_post(endpoint, payload=None, params=None):
    url = f"{CRM_URL}/api/v5/{endpoint}"
    params = params or {"apiKey": API_KEY}
    r = requests.post(url, params=params, json=payload or {}, timeout=20)
    r.raise_for_status()
    return r.json()

def pick_order_by_code_or_phone(code_or_phone: str):
    # 1) bot_code
    orders = crm_get("orders", {"customFields[bot_code]": code_or_phone}).get("orders", [])
    if orders:
        return orders[0]
    # 2) phone
    if code_or_phone and (code_or_phone[0].isdigit() or code_or_phone.startswith("+")):
        orders = crm_get("orders", {"customer[phone]": code_or_phone}).get("orders", [])
        if orders:
            return orders[0]
    return None

def get_order_by_id(order_id: int):
    data = crm_get(f"orders/{order_id}", {"by": "id"})
    return data.get("order") or {}

def save_telegram_id_for_order(order_id: int, telegram_id: int, site: str | None = None):
    payload = {"by": "id", "order": {"customFields": {"telegram_id": str(telegram_id)}}}
    if site:
        payload["site"] = site
    crm_post(f"orders/{order_id}/edit", payload)

def clear_telegram_id_for_order(order_id: int):
    payload = {"by": "id", "order": {"customFields": {"telegram_id": ""}}}
    crm_post(f"orders/{order_id}/edit", payload)

def get_order_status_text_by_id(order_id: int):
    o = get_order_by_id(order_id)
    if not o:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    status = o.get("statusComment") or o.get("status") or "Статус не указан"
    num = o.get("number", "—")
    return f"📦 Заказ #{num}\nСтатус: {status}"

def get_tracking_number_text_by_id(order_id: int):
    o = get_order_by_id(order_id)
    if not o:
        return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"
    delivery = o.get("delivery") or {}
    # Основное поле
    track_num = delivery.get("number")
    # Фоллбеки
    if not track_num:
        track_num = delivery.get("trackNumber") or delivery.get("track_number")
    if not track_num:
        tracks = delivery.get("tracks") or []
        if isinstance(tracks, list) and tracks:
            first = tracks[0] or {}
            track_num = first.get("number") or first.get("trackNumber")
    num = o.get("number", "—")
    if track_num:
        return f"🎯 Заказ #{num}\nВаш трек-номер: {track_num}\nОтследить: https://www.cdek.ru/ru/tracking?order_id={track_num}"
    return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"

def get_orders_list_text_by_customer_id(customer_id: int):
    if not customer_id:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    orders = crm_get("orders", {"customer[id]": customer_id}).get("orders", [])
    if not orders:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    out = ["📋 Ваши заказы:"]
    for o in orders:
        out.append(f"— #{o.get('number')} ({o.get('statusComment') or o.get('status') or 'Без статуса'})")
    return "\n".join(out)

def save_review_by_order_id(order_id: int, review_text: str):
    o = get_order_by_id(order_id)
    site = o.get("site")
    payload = {"by": "id", "order": {"customFields": {"comments": review_text}}}
    if site:
        payload["site"] = site
    crm_post(f"orders/{order_id}/edit", payload)
