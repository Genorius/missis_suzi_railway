import os
import logging
import requests
import telebot
from telebot import types
from flask import Flask, request
import redis

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_TELEGRAM_ID')
WEBHOOK_BASE_URL = os.getenv('WEBHOOK_URL')

if TELEGRAM_TOKEN is None:
    logging.error("Missing TELEGRAM_TOKEN environment variable")
    raise RuntimeError("TELEGRAM_TOKEN is not set")

if ADMIN_ID is None:
    logging.warning("ADMIN_TELEGRAM_ID is not set. Support messages will not be sent.")
else:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        # If not an integer, perhaps it's a username (starting with @)
        # In that case, support messages may not work properly without an ID.
        logging.error("ADMIN_TELEGRAM_ID is not a valid ID. It should be an integer Telegram ID.")
        ADMIN_ID = None

if WEBHOOK_BASE_URL is None:
    logging.error("Missing WEBHOOK_URL environment variable")
    raise RuntimeError("WEBHOOK_URL is not set")

# Other environment variables for CRM access
CRM_URL = os.getenv('CRM_URL')
CRM_API_KEY = os.getenv('CRM_API_KEY')
if not CRM_URL or not CRM_API_KEY:
    logging.warning("CRM_URL or CRM_API_KEY not set. Bot might not function properly without CRM access.")

# Initialize bot and Redis
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
redis_url = os.getenv('REDIS_URL')
if not redis_url:
    logging.error("Missing REDIS_URL environment variable")
    raise RuntimeError("REDIS_URL is not set")
try:
    redis_client = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    logging.error(f"Failed to connect to Redis: {e}")
    raise

# In-memory dictionary to track support mode state for users
support_mode = {}

# Helper function to normalize phone numbers
def normalize_phone_number(phone: str) -> str:
    # Remove spaces, hyphens, parentheses, etc., keep only digits and plus
    raw = phone.strip()
    import re
    cleaned = re.sub(r'[^0-9+]', '', raw)
    if not cleaned:
        return cleaned
    if cleaned[0] == '+':
        # If in format +..., assume correct international format
        if cleaned.startswith('+8'):
            # Replace +8 with +7 for Russian numbers starting incorrectly with +8
            cleaned = '+7' + cleaned[2:]
        return cleaned
    # If no plus, handle typical Russian formats
    if cleaned[0] == '8' and len(cleaned) == 11:
        cleaned = '+7' + cleaned[1:]
    elif len(cleaned) == 10:
        cleaned = '+7' + cleaned
    elif cleaned[0] == '7' and len(cleaned) == 11:
        cleaned = '+' + cleaned
    else:
        cleaned = '+' + cleaned
    return cleaned

# Prepare main menu keyboard
def get_main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("📦 Статус отправления", "🔢 Трек-номер")
    keyboard.row("🗂 Мои заказы", "💬 Поддержка")
    return keyboard

# /start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    # Check if user is already authorized
    phone = redis_client.get(f"user:{chat_id}:phone")
    if phone:
        logging.info(f"User {chat_id} already authorized (phone {phone}). Sending menu.")
        welcome_back_text = "С возвращением! Вы уже авторизованы."
        bot.send_message(chat_id, welcome_back_text, reply_markup=get_main_menu())
    else:
        logging.info(f"User {chat_id} started bot. Awaiting authorization.")
        welcome_text = ("Я — бот Missis S’Uzi. Помогаю следить за заказами и быть на связи, если что-то понадобится.\n"
                        "Для начала пришлите, пожалуйста, ваш уникальный код или номер телефона 📦")
        bot.send_message(chat_id, welcome_text)
        # Menu keyboard will be shown after successful authorization

# Handler for shared contact (phone number)
@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    chat_id = message.chat.id
    phone = redis_client.get(f"user:{chat_id}:phone")
    if phone:
        logging.info(f"User {chat_id} sent a contact but is already authorized. Ignoring.")
        return
    contact = message.contact
    if not contact or not contact.phone_number:
        logging.info(f"User {chat_id} sent contact with no phone number.")
        return
    phone_number = normalize_phone_number(contact.phone_number)
    if not phone_number:
        bot.send_message(chat_id, "Не удалось прочитать номер из контакта. Пожалуйста, введите номер телефона вручную.")
        return
    # Authorize using the provided phone number
    authorize_by_phone(chat_id, phone_number)

# Text message handler
@bot.message_handler(content_types=['text'])
def text_handler(message):
    chat_id = message.chat.id
    text = message.text.strip()
    # If user is in support mode (awaiting a support message)
    if support_mode.get(chat_id):
        # If user pressed a menu command instead of typing a support message, cancel support mode
        if text in ["📦 Статус отправления", "🔢 Трек-номер", "🗂 Мои заказы", "💬 Поддержка"]:
            support_mode.pop(chat_id, None)
            # Continue processing this message as a normal command
        else:
            logging.info(f"Forwarding support message from user {chat_id} to admin.")
            if ADMIN_ID:
                try:
                    bot.forward_message(ADMIN_ID, chat_id, message.message_id)
                    # Optionally, send a note to admin with user info
                    user = message.from_user
                    admin_note = (f"Сообщение от пользователя {user.first_name} "
                                  f"{user.last_name or ''} (@{user.username or 'без username'}, id {chat_id}):")
                    bot.send_message(ADMIN_ID, admin_note)
                except Exception as e:
                    logging.error(f"Failed to forward message to admin: {e}")
                bot.send_message(chat_id, "Сообщение отправлено администратору, ожидайте ответа.")
            else:
                bot.send_message(chat_id, "Сервис поддержки недоступен.")
                logging.error("ADMIN_ID not set, cannot forward support message.")
            support_mode.pop(chat_id, None)
            return

    # If not authorized yet, interpret text as code or phone
    phone = redis_client.get(f"user:{chat_id}:phone")
    if not phone:
        input_data = text
        normalized_input = normalize_phone_number(input_data)
        if normalized_input and (normalized_input[0] == '+' or len(normalized_input) >= 10):
            authorize_by_phone(chat_id, normalized_input)
        elif input_data.isdigit():
            authorize_by_code(chat_id, input_data)
        else:
            bot.send_message(chat_id, "Пожалуйста, отправьте ваш код или номер телефона для авторизации.")
        return

    # User is authorized and not in support mode, handle menu commands
    if text == "📦 Статус отправления":
        logging.info(f"User {chat_id} requested order status.")
        send_order_status(chat_id)
    elif text == "🔢 Трек-номер":
        logging.info(f"User {chat_id} requested tracking number.")
        send_tracking_number(chat_id)
    elif text == "🗂 Мои заказы":
        logging.info(f"User {chat_id} requested list of orders.")
        send_all_orders(chat_id)
    elif text == "💬 Поддержка":
        logging.info(f"User {chat_id} entered support mode.")
        support_mode[chat_id] = True
        bot.send_message(chat_id, "Напишите ваше сообщение, и я передам его администратору.")
    else:
        logging.info(f"User {chat_id} sent an unknown command: {text}")
        bot.send_message(chat_id, "Неизвестная команда. Пожалуйста, используйте меню ниже.")

# Authorization helpers
def authorize_by_code(chat_id, code):
    if not CRM_URL or not CRM_API_KEY:
        logging.error("CRM_URL or CRM_API_KEY not configured. Cannot authorize by code.")
        bot.send_message(chat_id, "Сервис недоступен, попробуйте позже.")
        return
    try:
        response = requests.get(f"{CRM_URL}/api/v5/orders",
                                params={"filter[customFields][bot_code]": code, "apiKey": CRM_API_KEY})
        data = response.json()
    except Exception as e:
        logging.error(f"Error requesting CRM for code {code}: {e}")
        bot.send_message(chat_id, "Произошла ошибка при подключении к сервису. Попробуйте позже.")
        return
    if not data.get("success"):
        logging.error(f"CRM response for code {code} was not successful: {data}")
        bot.send_message(chat_id, "Произошла ошибка на сервере. Попробуйте позже.")
        return
    orders = data.get("orders")
    if not orders:
        logging.info(f"No orders found for code {code}.")
        bot.send_message(chat_id, "Код не найден. Пожалуйста, проверьте и попробуйте ещё раз, либо введите номер телефона.")
        return
    order = orders[0]
    # Extract phone from order data
    phone_number = None
    if order.get("phone"):
        phone_number = order["phone"]
    elif order.get("customer") and order["customer"].get("phones"):
        phones_list = order["customer"]["phones"]
        if phones_list and isinstance(phones_list, list):
            phone_entry = phones_list[0]
            phone_number = phone_entry.get("number") if isinstance(phone_entry, dict) else str(phone_entry)
    if phone_number:
        phone_number = normalize_phone_number(phone_number)
    else:
        logging.warning(f"Phone number not found in order data for code {code}.")
        phone_number = ""
    # Save auth data in Redis
    redis_client.set(f"user:{chat_id}:phone", phone_number if phone_number else "unknown")
    redis_client.set(f"user:{chat_id}:current_order", order.get("number") or "")
    logging.info(f"User {chat_id} authorized via code {code}. Phone: {phone_number}, Order: {order.get('number')}")
    # Send welcome and menu
    bot.send_message(chat_id, "Код принят! Добро пожаловать ❤️", reply_markup=get_main_menu())

def authorize_by_phone(chat_id, phone_number):
    if not CRM_URL or not CRM_API_KEY:
        logging.error("CRM_URL or CRM_API_KEY not configured. Cannot authorize by phone.")
        bot.send_message(chat_id, "Сервис недоступен, попробуйте позже.")
        return
    try:
        response = requests.get(f"{CRM_URL}/api/v5/orders",
                                params={"filter[phone]": phone_number, "apiKey": CRM_API_KEY})
        data = response.json()
    except Exception as e:
        logging.error(f"Error requesting CRM for phone {phone_number}: {e}")
        bot.send_message(chat_id, "Произошла ошибка при подключении к сервису. Попробуйте позже.")
        return
    if not data.get("success"):
        logging.error(f"CRM response for phone {phone_number} was not successful: {data}")
        bot.send_message(chat_id, "Произошла ошибка на сервере. Попробуйте позже.")
        return
    orders = data.get("orders")
    if not orders:
        logging.info(f"No orders found for phone {phone_number}.")
        bot.send_message(chat_id, "Заказы с этим номером телефона не найдены. Пожалуйста, проверьте номер или используйте уникальный код из заказа.")
        return
    # Determine latest order (by ID)
    latest_order = max(orders, key=lambda o: o.get("id", 0))
    redis_client.set(f"user:{chat_id}:phone", phone_number)
    redis_client.set(f"user:{chat_id}:current_order", latest_order.get("number") or "")
    logging.info(f"User {chat_id} authorized via phone {phone_number}. Current order: {latest_order.get('number')}")
    bot.send_message(chat_id, "Номер телефона подтверждён! Добро пожаловать ❤️", reply_markup=get_main_menu())

# Functions to handle menu actions
def send_order_status(chat_id):
    order_number = redis_client.get(f"user:{chat_id}:current_order")
    if not order_number:
        logging.warning(f"No current order for user {chat_id} when requesting status.")
        bot.send_message(chat_id, "Не удалось получить текущий заказ.")
        return
    if not CRM_URL or not CRM_API_KEY:
        bot.send_message(chat_id, "Сервис недоступен, попробуйте позже.")
        return
    try:
        response = requests.get(f"{CRM_URL}/api/v5/orders",
                                params={"filter[numbers][]": order_number, "apiKey": CRM_API_KEY})
        data = response.json()
    except Exception as e:
        logging.error(f"Error requesting CRM for order {order_number}: {e}")
        bot.send_message(chat_id, "Не получилось узнать статус. Попробуйте позже.")
        return
    if not data.get("success"):
        logging.error(f"CRM response for order {order_number} was not successful: {data}")
        bot.send_message(chat_id, "Произошла ошибка при получении статуса. Попробуйте позже.")
        return
    orders = data.get("orders")
    if not orders:
        logging.info(f"No data returned for order {order_number}.")
        bot.send_message(chat_id, "Статус заказа недоступен.")
        return
    order = orders[0]
    # Prefer delivery statusName if available
    status_text = order.get("delivery", {}).get("data", {}).get("statusName")
    if status_text:
        bot.send_message(chat_id, f"Статус заказа: {status_text} 📦")
    else:
        internal_status = order.get("status")
        if internal_status:
            bot.send_message(chat_id, f"Статус заказа: {internal_status}")
        else:
            bot.send_message(chat_id, "Статус заказа не найден.")

def send_tracking_number(chat_id):
    order_number = redis_client.get(f"user:{chat_id}:current_order")
    if not order_number:
        logging.warning(f"No current order for user {chat_id} when requesting tracking number.")
        bot.send_message(chat_id, "Не удалось получить текущий заказ.")
        return
    if not CRM_URL or not CRM_API_KEY:
        bot.send_message(chat_id, "Сервис недоступен, попробуйте позже.")
        return
    try:
        response = requests.get(f"{CRM_URL}/api/v5/orders",
                                params={"filter[numbers][]": order_number, "apiKey": CRM_API_KEY})
        data = response.json()
    except Exception as e:
        logging.error(f"Error requesting CRM for order {order_number}: {e}")
        bot.send_message(chat_id, "Не получилось получить трек-номер. Попробуйте позже.")
        return
    if not data.get("success"):
        logging.error(f"CRM response for order {order_number} was not successful: {data}")
        bot.send_message(chat_id, "Произошла ошибка при получении трек-номера. Попробуйте позже.")
        return
    orders = data.get("orders")
    if not orders:
        logging.info(f"No data returned for order {order_number}.")
        bot.send_message(chat_id, "Трек-номер недоступен.")
        return
    order = orders[0]
    track_number = order.get("trackNumber") or order.get("delivery", {}).get("data", {}).get("trackNumber")
    if track_number:
        bot.send_message(chat_id, f"Трек-номер: {track_number}")
    else:
        bot.send_message(chat_id, "Трек-номер пока не присвоен. Как только он появится — сразу сообщим!")

def send_all_orders(chat_id):
    phone = redis_client.get(f"user:{chat_id}:phone")
    if not phone:
        logging.warning(f"No phone found for user {chat_id} when requesting order list.")
        bot.send_message(chat_id, "Не удалось получить список заказов.")
        return
    if not CRM_URL or not CRM_API_KEY:
        bot.send_message(chat_id, "Сервис недоступен, попробуйте позже.")
        return
    try:
        response = requests.get(f"{CRM_URL}/api/v5/orders",
                                params={"filter[phone]": phone, "apiKey": CRM_API_KEY})
        data = response.json()
    except Exception as e:
        logging.error(f"Error requesting CRM for phone {phone}: {e}")
        bot.send_message(chat_id, "Не получилось получить список. Попробуйте позже.")
        return
    if not data.get("success"):
        logging.error(f"CRM response for phone {phone} was not successful: {data}")
        bot.send_message(chat_id, "Произошла ошибка при получении списка заказов.")
        return
    orders = data.get("orders")
    if not orders:
        bot.send_message(chat_id, "У вас пока нет заказов.")
        return
    # Sort orders by ID descending (latest first)
    orders_sorted = sorted(orders, key=lambda o: o.get("id", 0), reverse=True)
    lines = ["Ваши заказы:"]
    for ord in orders_sorted:
        num = ord.get("number") or "(без номера)"
        status = ord.get("status") or ""
        lines.append(f"• {num} — {status}")
    text = "\n".join(lines)
    bot.send_message(chat_id, text)

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def webhook():
    # Parse incoming request from Telegram
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def index():
    return "Missis S'Uzi bot is running!", 200

# Set webhook on startup
bot.remove_webhook()
webhook_url = WEBHOOK_BASE_URL
if not webhook_url.endswith(TELEGRAM_TOKEN):
    webhook_url = webhook_url.rstrip('/') + '/' + TELEGRAM_TOKEN
bot.set_webhook(url=webhook_url)

# Start Flask server
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logging.info(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port)
