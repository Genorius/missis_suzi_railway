import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
API_KEY = os.getenv("API_KEY")
CRM_URL = os.getenv("CRM_URL")