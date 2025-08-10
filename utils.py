import re

def normalize_phone(phone: str) -> str:
    # Keep only digits, allow + at start
    p = re.sub(r"[^0-9+]", "", phone or "")
    # Convert leading 8 to +7 (RU common)
    if p.startswith("8") and len(p) in (11, 12):
        p = "+7" + p[1:]
    if p.startswith("7") and len(p) == 11:
        p = "+" + p
    if p and not p.startswith("+"):
        # if it's clearly a phone (10-12 digits), prepend +
        digits = re.sub(r"\D", "", p)
        if 10 <= len(digits) <= 12:
            p = "+" + digits
    return p

def is_probably_phone(text: str) -> bool:
    digits = re.sub(r"\D", "", text or "")
    return len(digits) >= 10

def extract_stars_from_callback(data: str) -> int | None:
    m = re.match(r"star:(\d)", data or "")
    if not m:
        return None
    val = int(m.group(1))
    return val if 1 <= val <= 5 else None
