import redis
from config import REDIS_URL

r = redis.from_url(REDIS_URL)

def is_authorized(user_id):
    return r.get(f"user:{user_id}") == b"1"

def save_authorization(user_id):
    r.set(f"user:{user_id}", "1", ex=3600 * 24)

def save_user_context(order_id, phone):
    r.set("order_id", order_id)
    if phone:
        r.set("phone", phone)

def get_user_order():
    return r.get("order_id").decode("utf-8") if r.get("order_id") else None

def get_user_phone():
    return r.get("phone").decode("utf-8") if r.get("phone") else None