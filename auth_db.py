import redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL)

def save_user_auth(user_id, order_id):
    r.set(f"user:{user_id}", order_id)

def get_order_id_by_user_id(user_id):
    order_id = r.get(f"user:{user_id}")
    return order_id.decode() if order_id else None
