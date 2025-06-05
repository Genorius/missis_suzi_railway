from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiohttp import web
import os

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("👋 Привет! Я Missis S’Uzi. Чтобы узнать о вашем заказе — пришлите код или номер телефона 📦")

async def webhook_handler(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def ping(request):
    return web.Response(text="pong")

async def on_startup(app):
    webhook_url = os.getenv("WEBHOOK_URL")
    await bot.set_webhook(webhook_url)
    print("🚀 on_startup вызван")
    print(f"✅ Вебхук установлен: {webhook_url}")

app = web.Application()
app.router.add_post("/webhook", webhook_handler)
app.router.add_get("/ping", ping)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    print("✅ Bot is starting manually on aiohttp...")
    web.run_app(app, host="0.0.0.0", port=PORT)