import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CRM_API_KEY = os.getenv("CRM_API_KEY")
CRM_URL = os.getenv("CRM_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "123456"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # добавлено для webhook