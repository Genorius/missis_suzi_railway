import aiohttp
from typing import Dict, Any, List, Optional
from config import CRM_URL, CRM_API_KEY

class CRMError(Exception):
    pass

async def _get(session: aiohttp.ClientSession, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not CRM_URL or not CRM_API_KEY:
        raise CRMError("CRM not configured")
    url = f"{CRM_URL}{path}"
    params = dict(params or {})
    params.setdefault("apiKey", CRM_API_KEY)
    async with session.get(url, params=params, timeout=20) as resp:
        if resp.status >= 400:
            txt = await resp.text()
            raise CRMError(f"GET {path} -> {resp.status}: {txt[:200]}")
        return await resp.json()

async def _post(session: aiohttp.ClientSession, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
    if not CRM_URL or not CRM_API_KEY:
        raise CRMError("CRM not configured")
    url = f"{CRM_URL}{path}"
    async with session.post(url, params={"apiKey": CRM_API_KEY}, json=json_body, timeout=20) as resp:
        if resp.status >= 400:
            txt = await resp.text()
            raise CRMError(f"POST {path} -> {resp.status}: {txt[:200]}")
        return await resp.json()

async def fetch_orders_by_bot_code(code: str) -> List[Dict[str, Any]]:
    if not code:
        return []
    async with aiohttp.ClientSession() as s:
        data = await _get(s, "/api/v5/orders", {"filter[customFields][bot_code]": code})
        return data.get("orders") or []

async def fetch_orders_by_phone(phone: str) -> List[Dict[str, Any]]:
    if not phone:
        return []
    async with aiohttp.ClientSession() as s:
        data = await _get(s, "/api/v5/orders", {"filter[customer][phones][]": phone})
        return data.get("orders") or []

async def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    if not order_id:
        return None
    async with aiohttp.ClientSession() as s:
        data = await _get(s, "/api/v5/orders", {"ids[]": order_id})
        orders = data.get("orders") or []
        return orders[0] if orders else None

async def patch_order_comment(order_id: str, comment: str) -> bool:
    async with aiohttp.ClientSession() as s:
        payload = {"order": {"customFields": {"comments": comment}}, "by": "externalId"}
        try:
            await _post(s, f"/api/v5/orders/{order_id}/edit", payload)
            return True
        except CRMError:
            return False
