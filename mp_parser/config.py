# mp_parser/config.py
import os
import json
from typing import List, Dict, Tuple
from dotenv import load_dotenv

load_dotenv()

# ===== Браузер и окружение =====
HEADLESS: bool = os.getenv("HEADLESS", "0") == "1"
TIMEZONE_ID: str = os.getenv("TIMEZONE_ID", "Europe/Moscow")
HOMEPAGE_URL: str = os.getenv("HOMEPAGE_URL", "https://www.ozon.ru/")
HOMEPAGE_WARMUP: bool = os.getenv("HOMEPAGE_WARMUP", "1") == "1"
REFERER_ON_PRODUCT_GOTO: bool = os.getenv("REFERER_ON_PRODUCT_GOTO", "1") == "1"
NAVIGATION_WAIT_UNTIL: str = os.getenv("NAVIGATION_WAIT_UNTIL", "networkidle")

# ===== Заголовки/UA =====
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]
HEADERS: Dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": os.getenv("ACCEPT_LANGUAGE", "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

# ===== Таймауты и повторы =====
PAGE_LOAD_TIMEOUT: int = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "60000"))
ELEMENT_WAIT_TIMEOUT: int = int(os.getenv("ELEMENT_WAIT_TIMEOUT_MS", "15000"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
_delay_raw = os.getenv("DELAY_RANGE_SEC", "5,8").split(",")
DELAY_RANGE: Tuple[int, int] = (int(_delay_raw[0]), int(_delay_raw[1]))

# ===== Прокси =====
PROXY_POOL_JSON = os.getenv("PROXY_POOL_JSON", "[]")
try:
    PROXY_POOL: List[Dict] = json.loads(PROXY_POOL_JSON)
    if not isinstance(PROXY_POOL, list):
        PROXY_POOL = []
except json.JSONDecodeError:
    PROXY_POOL = []

# Proxy health/cooldown
MAX_PROXY_FAILS_BEFORE_COOLDOWN: int = int(os.getenv("MAX_PROXY_FAILS_BEFORE_COOLDOWN", "2"))
PROXY_COOLDOWN_SEC: int = int(os.getenv("PROXY_COOLDOWN_SEC", "180"))  # 3 минуты по умолчанию

# ===== Ресурсы =====
BLOCK_RESOURCES: bool = os.getenv("BLOCK_RESOURCES", "0") == "1"

# ===== Персистенция cookies =====
PERSIST_COOKIES: bool = os.getenv("PERSIST_COOKIES", "1") == "1"
STATE_DIR: str = os.getenv("STATE_DIR", ".ozon_state")
