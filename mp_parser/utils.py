# mp_parser/utils.py
import os
import random
import re
from typing import Dict, Optional, Iterable, List
from .config import PROXY_POOL, MAX_RETRIES

# Глобальное хранилище счётчиков неудач по URL
FAILED_ATTEMPTS: Dict[str, int] = {}

def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def clean_url(url: str) -> str:
    return url.strip()

def record_failure(url: str) -> None:
    url = clean_url(url)
    FAILED_ATTEMPTS[url] = FAILED_ATTEMPTS.get(url, 0) + 1

def record_success(url: str) -> None:
    url = clean_url(url)
    FAILED_ATTEMPTS[url] = 0

def is_permanent_failure(url: str) -> bool:
    return FAILED_ATTEMPTS.get(clean_url(url), 0) >= MAX_RETRIES

def get_random_proxy(exclude: Optional[Iterable[str]] = None) -> Optional[Dict]:
    """
    Выбор случайного прокси. Можно исключить имена (name) из выдачи.
    Возвращает dict: server, username, password, name.
    """
    if not PROXY_POOL:
        return None
    ex: List[str] = list(exclude or [])
    pool = [p for p in PROXY_POOL if p.get("name") not in ex] or PROXY_POOL
    return random.choice(pool)

def parse_price_from_text(text: str) -> Optional[int]:
    """
    '12 345 ₽' -> 12345
    """
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    try:
        return int(digits) if digits else None
    except ValueError:
        return None
