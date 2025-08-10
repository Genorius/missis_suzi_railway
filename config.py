import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "8080"))

CRM_URL = os.getenv("CRM_URL", "").rstrip("/")
CRM_API_KEY = os.getenv("CRM_API_KEY", "")

REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # required for support relay

USE_WEBHOOK = os.getenv("USE_WEBHOOK", "1") == "1"
