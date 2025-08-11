
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

def _normalize_phone(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    plus = s.startswith("+")
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return ""
    if plus:
        return "+" + digits
    if digits.startswith("8") and len(digits) >= 11:
        return "+7" + digits[1:]
    return digits

def _orders_by_bot_code(code: str) -> list:
    data = crm_get("orders", {"filter[customFields][bot_code]": code, "limit": 20})
    orders = data.get("orders", []) or []
    return [o for o in orders if ((o.get("customFields") or {}).get("bot_code") == code)]

def _customers_by_phone(phone: str) -> list:
    data = crm_get("customers", {"filter[phone]": phone, "limit": 20})
    customers = data.get("customers", []) or []
    if customers:
        return customers
    data = crm_get("customers", {"filter[name]": phone, "limit": 20})
    return data.get("customers", []) or []

def _orders_by_customer_id(customer_id: int) -> list:
    data = crm_get("orders", {"filter[customerId]": customer_id, "limit": 20})
    return data.get("orders", []) or []

def pick_order_by_code_or_phone(code_or_phone: str):
    if code_or_phone:
        by_code = _orders_by_bot_code(code_or_phone)
        if by_code:
            by_code.sort(key=lambda o: o.get("createdAt") or "", reverse=True)
            return by_code[0]
    phone = _normalize_phone(code_or_phone)
    if phone:
        customers = _customers_by_phone(phone)
        if customers:
            customer = customers[0]
            cid = customer.get("id")
            if cid:
                orders = _orders_by_customer_id(cid)
                if orders:
                    orders.sort(key=lambda o: o.get("createdAt") or "", reverse=True)
                    for o in orders:
                        cust = o.get("customer") or {}
                        if cust.get("id") == cid:
                            return o
    return None

def get_order_by_id(order_id: int):
    data = crm_get(f"orders/{order_id}", {"by": "id"})
    return data.get("order") or {}

def save_telegram_id_for_order(order_id: int, telegram_id: int, site: str | None = None):
    payload = {"order": {"customFields": {"telegram_id": str(telegram_id)}}}
    params = {"apiKey": API_KEY, "by": "id"}
    if site:
        params["site"] = site
    r = requests.post(f"{CRM_URL}/api/v5/orders/{order_id}/edit", params=params, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()

def get_order_status_text_by_id(order_id: int):
    o = get_order_by_id(order_id)
    if not o:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    status = o.get("statusComment") or o.get("status") or "Статус не указан"
    num = o.get("number", "—")
    return f"📦 Заказ #{num}\nСтатус: {status}"

def _extract_track(o: dict) -> str | None:
    d = (o or {}).get("delivery") or {}
    cf = (o or {}).get("customFields") or {}
    candidates = []
    for key in ("number", "trackNumber", "trackingNumber", "track_number", "tracking_number"):
        candidates.append(d.get(key))
    data = d.get("data") or {}
    for key in ("number", "trackNumber", "trackingNumber", "track_number", "tracking_number", "barcode"):
        candidates.append(data.get(key))
    tracks = d.get("tracks") or []
    if isinstance(tracks, list):
        for t in tracks:
            for key in ("number", "trackNumber", "trackingNumber", "code"):
                candidates.append((t or {}).get(key))
    for key in ("track", "track_number", "tracking_number", "ttn", "awb", "awb_number"):
        candidates.append(cf.get(key))
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None

def get_tracking_number_text_by_id(order_id: int):
    o = get_order_by_id(order_id)
    if not o:
        return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"
    track_num = _extract_track(o)
    num = o.get("number", "—")
    if track_num:
        return f"🎯 Заказ #{num}\nВаш трек-номер: {track_num}\nОтследить: https://www.cdek.ru/ru/tracking?order_id={track_num}"
    return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"

def get_orders_list_text_by_customer_id(customer_id: int):
    if not customer_id:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    orders = _orders_by_customer_id(customer_id)
    if not orders:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    out = ["📋 Ваши заказы:"]
    for o in orders:
        out.append(f"— #{o.get('number')} ({o.get('statusComment') or o.get('status') or 'Без статуса'})")
    return "\n".join(out)

def save_review_by_order_id(order_id: int, review_text: str):
    o = get_order_by_id(order_id)
    site = o.get("site")
    payload = {"order": {"customFields": {"comments": review_text}}}
    params = {"apiKey": API_KEY, "by": "id"}
    if site:
        params["site"] = site
    r = requests.post(f"{CRM_URL}/api/v5/orders/{order_id}/edit", params=params, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()
