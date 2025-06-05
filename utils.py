import aiohttp
from config import API_KEY, CRM_URL

headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}

async def get_order_by_bot_code_or_phone(code):
    if code.startswith("+") or code.isdigit():
        query = f'{CRM_URL}/api/v5/orders?customer[phone]={code}'
    else:
        query = f'{CRM_URL}/api/v5/orders?customFields[bot_code]={code}'

    async with aiohttp.ClientSession() as session:
        async with session.get(query, headers=headers) as response:
            data = await response.json()
            return data.get("orders", [None])[0]

async def get_status_text(order_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRM_URL}/api/v5/orders/{order_id}", headers=headers) as resp:
            data = await resp.json()
            status = data["order"].get("status", "Неизвестно")
            return f"📦 Текущий статус: <b>{status}</b>"

async def get_track_text(order_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRM_URL}/api/v5/orders/{order_id}", headers=headers) as resp:
            data = await resp.json()
            delivery = data["order"].get("delivery", {})
            number = delivery.get("number")
            if number:
                return f"🔍 Трек-номер: <b>{number}</b>\nОтследить: https://cdek.ru/tracking"
            return "⏳ Трек-номер ещё не присвоен, но мы обязательно сообщим вам!"

async def get_orders(order_id):
    return f"📋 Это ваш заказ: #{order_id}"

async def save_review_to_crm(order_id, stars, comment=None):
    payload = {
        "order": {
            "customFields": {
                "rating": stars,
                "comments": comment or ""
            }
        }
    }
    async with aiohttp.ClientSession() as session:
        await session.post(f"{CRM_URL}/api/v5/orders/{order_id}/edit", json=payload, headers=headers)