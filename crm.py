
import os
import logging
import requests

API_KEY = os.getenv("CRM_API_KEY", "pDUAhKJaZZlSXnWtSberXS6PCwfiGP4D")
CRM_URL = os.getenv("CRM_URL", "https://valentinkalinovski.retailcrm.ru")
BOT_CODE_FIELD = os.getenv("CRM_BOT_CODE_FIELD", "bot_code")  # можно переопределить код поля

def _log_http_error(prefix: str, resp: requests.Response):
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    logging.error("%s: status=%s url=%s response=%s", prefix, resp.status_code, resp.url, body)

def crm_get(endpoint, params=None):
    url = f"{CRM_URL}/api/v5/{endpoint}"
    params = params or {}
    params["apiKey"] = API_KEY
    r = requests.get(url, params=params, timeout=20)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        _log_http_error("CRM GET failed", r)
        raise
    return r.json()

def crm_post(endpoint, payload=None, params=None):
    url = f"{CRM_URL}/api/v5/{endpoint}"
    params = params or {}
    params["apiKey"] = API_KEY
    r = requests.post(url, params=params, json=payload or {}, timeout=20)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        _log_http_error("CRM POST failed", r)
        raise
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
    # используем настраиваемый код поля из ENV CRM_BOT_CODE_FIELD
    field_code = BOT_CODE_FIELD or "bot_code"
    data = crm_get("orders", {f"filter[customFields][{field_code}]": code, "limit": 20})
    orders = data.get("orders", []) or []
    # дополнительная проверка по exact match
    out = []
    for o in orders:
        cf = (o.get("customFields") or {})
        if str(cf.get(field_code, "")).strip() == str(code).strip():
            out.append(o)
    return out

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
    params = {"by": "id"}
    if site:
        params["site"] = site
    try:
        return crm_post(f"orders/{order_id}/edit", payload, params=params)
    except requests.HTTPError as e:
        if site:
            return crm_post(f"orders/{order_id}/edit", payload, params={"by": "id"})
        raise

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
        return f"🎯 Заказ #{num}\\nВаш трек-номер: {track_num}\\nОтследить: https://www.cdek.ru/ru/tracking?order_id={track_num}"
    return "📦 Трек-номер пока не присвоен, но я дам знать, как только он появится 🤍"

def get_order_status_text_by_id(order_id: int):
    o = get_order_by_id(order_id)
    if not o:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    status = o.get("statusComment") or o.get("status") or "Статус не указан"
    num = o.get("number", "—")
    return f"📦 Заказ #{num}\\nСтатус: {status}"

def get_orders_list_text_by_customer_id(customer_id: int):
    if not customer_id:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    orders = _orders_by_customer_id(customer_id)
    if not orders:
        return "📦 Пока нет активных заказов. Я всё проверила 🤍"
    out = ["📋 Ваши заказы:"]
    for o in orders:
        out.append(f"— #{o.get('number')} ({o.get('statusComment') or o.get('status') or 'Без статуса'})")
    return "\\n".join(out)

def save_review_by_order_id(order_id: int, review_text: str):
    o = get_order_by_id(order_id)
    site = o.get("site")
    payload = {"order": {"customFields": {"comments": review_text}}}
    params = {"by": "id"}
    if site:
        params["site"] = site
    try:
        return crm_post(f"orders/{order_id}/edit", payload, params=params)
    except requests.HTTPError:
        return crm_post(f"orders/{order_id}/edit", payload, params={"by": "id"})

def debug_probe(value: str) -> dict:
    by_code = _orders_by_bot_code(value)
    by_code_first = None
    if by_code:
        o = by_code[0]
        by_code_first = {
            "id": o.get("id"),
            "number": o.get("number"),
            "site": o.get("site"),
            "bot_code": ((o.get("customFields") or {}).get(BOT_CODE_FIELD)),
        }

    norm_phone = _normalize_phone(value)
    customers = _customers_by_phone(norm_phone) if norm_phone else []
    first_customer = customers[0] if customers else None
    first_c_brief = None
    if first_customer:
        first_c_brief = {
            "id": first_customer.get("id"),
            "firstName": first_customer.get("firstName"),
            "lastName": first_customer.get("lastName"),
        }

    orders_by_c = _orders_by_customer_id(first_customer.get("id")) if first_customer and first_customer.get("id") else []
    first_order = orders_by_c[0] if orders_by_c else None
    first_o_brief = None
    if first_order:
        first_o_brief = {
            "id": first_order.get("id"),
            "number": first_order.get("number"),
            "site": first_order.get("site"),
        }

    picked = None
    if by_code:
        picked = f"#{by_code[0].get('number')} (id={by_code[0].get('id')})"
    elif first_order:
        picked = f"#{first_order.get('number')} (id={first_order.get('id')})"

    return {
        "input": value,
        "normalized_phone": norm_phone,
        "by_code": {"count": len(by_code), "first": by_code_first},
        "by_phone": {
            "customers_count": len(customers),
            "first_customer": first_c_brief,
            "orders_count": len(orders_by_c),
            "first_order": first_o_brief,
        },
        "picked": picked,
    }
