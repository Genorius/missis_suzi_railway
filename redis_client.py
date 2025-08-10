import time
import redis
from typing import Optional
from config import REDIS_URL, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

if REDIS_URL:
    r = redis.from_url(REDIS_URL, decode_responses=True, health_check_interval=30)
else:
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
    try:
        return r.hget(f"user:{user_id}", "authorized") == "1"
    except redis.RedisError:
        return False

def authorize_user(user_id: int, order_id: str, code: str = None, phone: str = None) -> None:
    mapping = {"authorized": "1", "order_id": str(order_id)}
    if code:
        mapping["code"] = code
    if phone:
        mapping["phone"] = phone
    try:
        pipe = r.pipeline()
        pipe.hset(f"user:{user_id}", mapping=mapping)
        pipe.expire(f"user:{user_id}", 86400)  # 24 hours TTL
        pipe.execute()
    except redis.RedisError:
        pass

def get_user_field(user_id: int, key: str) -> Optional[str]:
    try:
        return r.hget(f"user:{user_id}", key)
    except redis.RedisError:
        return None

def get_order_id(user_id: int) -> Optional[str]:
    return get_user_field(user_id, "order_id")

def clear_auth(user_id: int) -> None:
    try:
        r.delete(f"user:{user_id}")
    except redis.RedisError:
        pass

def allow_request(user_id: int, limit: int = 3, window_sec: int = 1) -> bool:
    key = f"rl:{user_id}:{int(time.time() // window_sec)}"
    try:
        pipe = r.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, window_sec)
        count, _ = pipe.execute()
        return int(count) <= limit
    except redis.RedisError:
        return True

def cache_orders(user_id: int, orders: list, ttl: int = 60) -> None:
    try:
        key = f"orders:{user_id}"
        r.set(key, str(orders), ex=ttl)
    except redis.RedisError:
        pass

def get_cached_orders(user_id: int) -> Optional[list]:
    try:
        data = r.get(f"orders:{user_id}")
        if not data:
            return None
        # naive eval-safe parse: replace single quotes to double and use json if possible
        import json
        try:
            return json.loads(data.replace("'", '"'))
        except Exception:
            return None
    except redis.RedisError:
        return None
