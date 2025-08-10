import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from config import CRM_API_KEY, CRM_URL

if not CRM_API_KEY or not CRM_URL:
    raise RuntimeError("CRM_API_KEY/CRM_URL not configured")

HEADERS = {"Content-Type": "application/json"}

class CRMError(Exception):
    pass

async def _get_with_retry(session: aiohttp.ClientSession, path: str, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    url = f"{CRM_URL}{path}"
    last_error = None
    if "apiKey" not in params:
        params = {**params, "apiKey": CRM_API_KEY}
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, headers=HEADERS, timeout=20) as resp:
                if resp.status == 429:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    last_error = "429 Too Many Requests"
                    continue
                if resp.status >= 400:
                    last_error = f"CRM returned {resp.status}"
                    try:
                        _ = await resp.text()
                    except Exception:
                        pass
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = str(e)
            await asyncio.sleep(1 * (attempt + 1))
    raise CRMError(f"CRM request failed after {max_retries} attempts: {last_error}")

async def fetch_orders_by_bot_code(code: str) -> List[Dict[str, Any]]:
    if not code:
        return []
    params_try = [
        {"filter[customFields][bot_code]": code},
        {"customFields[bot_code]": code},
    ]
    async with aiohttp.ClientSession() as s:
        for p in params_try:
            try:
                data = await _get_with_retry(s, "/api/v5/orders", p)
                orders = data.get("orders") or data.get("items") or []
                if orders:
                    return orders
            except CRMError:
                continue
        return []

async def fetch_orders_by_phone(phone: str) -> List[Dict[str, Any]]:
    if not phone:
        return []
    async with aiohttp.ClientSession() as s:
        data = await _get_with_retry(
            s,
            "/api/v5/orders",
            {"filter[customer][phones][]": phone},
        )
        return data.get("orders") or []

async def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    async with aiohttp.ClientSession() as s:
        try:
            data = await _get_with_retry(s, "/api/v5/orders", {"ids[]": order_id})
            orders = data.get("orders") or []
            return orders[0] if orders else None
        except CRMError:
            return None

async def patch_order_comment(order_id: str, comment: str) -> bool:
    url = f"{CRM_URL}/api/v5/orders/{order_id}/edit"
    payload = {
        "order": {"customFields": {"comments": comment}},
        "by": "externalId",
        "apiKey": CRM_API_KEY,
    }
    async with aiohttp.ClientSession() as s:
        try:
            async with s.post(url, json=payload, headers=HEADERS, timeout=20) as resp:
                return resp.status < 400
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False
