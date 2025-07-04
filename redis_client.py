
import redis
import os

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

def is_authorized(user_id):
    return r.exists(f"user:{user_id}")

def authorize_user(user_id, code_or_phone):
    r.set(f"user:{user_id}", 1)
    r.set(f"user:{user_id}:code", code_or_phone)
    r.set(f"user:{user_id}:phone", code_or_phone)
    return True

def get_user_context(user_id, key):
    return r.get(f"user:{user_id}:{key}")
