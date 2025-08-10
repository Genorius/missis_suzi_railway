import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "8080"))
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "1") == "1"

CRM_URL = os.getenv("CRM_URL", "").rstrip("/")
CRM_API_KEY = os.getenv("CRM_API_KEY", "")

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
