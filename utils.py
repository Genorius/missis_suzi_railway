import re
from typing import Optional

def normalize_phone(phone: str) -> Optional[str]:
    if not phone:
        return None
    p = re.sub(r"[^0-9+]", "", phone)
    if p.startswith('8') and len(p) == 11:
        p = '+7' + p[1:]
    elif p.startswith('7') and len(p) == 11:
        p = '+' + p
    elif len(p) == 10 and not p.startswith('+'):
        p = '+7' + p
    if re.fullmatch(r"\d{5,9}", p or ""):
        return None
    if not re.match(r"^\+\d{10,15}$", p):
        return None
    return p

def is_probably_phone(text: str) -> bool:
    digits = re.sub(r"\D", "", text or "")
    return len(digits) >= 10

def extract_stars_from_callback(data: str) -> Optional[int]:
    m = re.match(r"star:(\d)", data or "")
    if not m:
        return None
    val = int(m.group(1))
    return val if 1 <= val <= 5 else None

def human_status(code: str) -> str:
    mapping = {
        "new": "принят",
        "processing": "в обработке",
        "assembling": "сборка",
        "shipped": "отправлен",
        "delivered": "доставлен",
        "cancelled": "отменён",
        "complete": "завершён",
    }
    return mapping.get((code or "").lower(), code or "неизвестно")
