import redis
from config import REDIS_URL

r = redis.from_url(REDIS_URL)

def is_authorized(user_id):
    return r.get(f"user:{user_id}") == b"1"

def save_authorization(user_id):
    r.set(f"user:{user_id}", "1", ex=3600 * 24)