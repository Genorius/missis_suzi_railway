import os
import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    health_check_interval=30,
)
r = redis.Redis(connection_pool=_pool)

def is_authorized(user_id: int) -> bool:
    return r.hget(f"user:{user_id}", "authorized") == "1"

def authorize_user(user_id: int, order_id: str, code: str = None, phone: str = None) -> None:
    mapping = {"authorized": "1", "order_id": str(order_id)}
    if code:
        mapping["code"] = code
    if phone:
        mapping["phone"] = phone
    r.hset(f"user:{user_id}", mapping=mapping)

def get_user_field(user_id: int, key: str):
    return r.hget(f"user:{user_id}", key)

def get_order_id(user_id: int):
    return get_user_field(user_id, "order_id")

def clear_auth(user_id: int):
    r.delete(f"user:{user_id}")
