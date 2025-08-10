import aiohttp
from typing import Optional, Dict, Any, List
from config import CRM_API_KEY, CRM_URL

if not CRM_API_KEY or not CRM_URL:
    raise RuntimeError("CRM_API_KEY/CRM_URL not configured")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": CRM_API_KEY,
}

async def _get(session: aiohttp.ClientSession, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{CRM_URL}{path}"
    async with session.get(url, params=params, headers=HEADERS, timeout=20) as resp:
        return await resp.json()

async def _post(session: aiohttp.ClientSession, path: str, json_body: Dict[str, Any], params: Dict[str, Any] = None) -> Dict[str, Any]:
    url = f"{CRM_URL}{path}"
    async with session.post(url, json=json_body, params=params or {}, headers=HEADERS, timeout=20) as resp:
        return await resp.json()

async def fetch_orders_by_bot_code(code: str) -> List[Dict[str, Any]]:
    params_try = [
        {"filter[customFields][bot_code]": code},
        {"customFields[bot_code]": code},
    ]
    async with aiohttp.ClientSession() as s:
        for p in params_try:
            data = await _get(s, "/api/v5/orders", p)
            orders = data.get("orders") or data.get("items") or []
            if orders:
                return orders
        return []

async def fetch_orders_by_phone(phone: str) -> List[Dict[str, Any]]:
    params_try = [
        {"filter[customer][phone]": phone},
        {"customer[phone]": phone},
    ]
    async with aiohttp.ClientSession() as s:
        for p in params_try:
            data = await _get(s, "/api/v5/orders", p)
            orders = data.get("orders") or data.get("items") or []
            if orders:
                return orders
        return []

def _has_bot_code(order: Dict[str, Any]) -> bool:
    cf = (order or {}).get("customFields") or {}
    return bool(cf.get("bot_code"))

def _get_delivery_number(order: Dict[str, Any]) -> Optional[str]:
    return ((order or {}).get("delivery") or {}).get("number")

async def pick_order_by_code_or_phone(code: Optional[str], phone: Optional[str]) -> Optional[Dict[str, Any]]:
    # Priority 1: by bot_code exact match
    if code:
        orders = await fetch_orders_by_bot_code(code)
        for o in orders:
            cf = (o.get("customFields") or {})
            if str(cf.get("bot_code")) == str(code):
                return o
        return None
    # Priority 2: by phone but only orders that have bot_code
    if phone:
        orders = await fetch_orders_by_phone(phone)
        orders_with_code = [o for o in orders if _has_bot_code(o)]
        # choose the most recent by createdAt or id
        def key_func(o):
            return o.get("createdAt") or o.get("updatedAt") or o.get("id") or 0
        orders_with_code.sort(key=key_func, reverse=True)
        return orders_with_code[0] if orders_with_code else None
    return None

async def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    async with aiohttp.ClientSession() as s:
        data = await _get(s, "/api/v5/orders", {"ids[]": order_id})
        orders = data.get("orders") or []
        return orders[0] if orders else None

async def get_order_status_text(order: Dict[str, Any]) -> str:
    if not order:
        return "Не удалось получить статус заказа."
    status = order.get("status") or "unknown"
    num = order.get("number") or order.get("externalId") or order.get("id")
    return f"📦 Заказ #{num}
Статус: {status}"

async def get_tracking_number_text(order: Dict[str, Any]) -> str:
    if not order:
        return "Не удалось получить информацию о доставке."
    track = _get_delivery_number(order)
    if track:
        return f"🚚 Трек-номер: {track}

Отслеживание доступно на сайте СДЭК."
    return "Пока нет трек-номера — как только появится, я сразу подскажу. Всё под контролем 🤍"

async def save_review(order_id: str, stars: int, comment: str = "") -> bool:
    payload = {
        "order": {
            "id": order_id,
            "customFields": {
                "rating": stars,
                "comments": comment or ""
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        data = await _post(s, f"/api/v5/orders/{order_id}/edit", payload, params={"by": "id"})
        return bool(data)
