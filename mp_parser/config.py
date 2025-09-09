import os
from typing import List, Dict

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ⚙️ Настройки
PAGE_LOAD_TIMEOUT = 60000
ELEMENT_WAIT_TIMEOUT = 15000
MAX_RETRIES = 3
DELAY_RANGE = (5, 8)

# 🔑 Прокси
PROXY_POOL = [
    {"server": "http://91.198.218.98:8000", "username": "mgtMWq", "password": "dQGA1d", "name": "Proxy-1"},
    {"server": "http://45.129.6.59:8000", "username": "W92JQn", "password": "w9XVRo", "name": "Proxy-2"},
    {"server": "http://45.129.5.145:8000", "username": "WgS3cy", "password": "Co4hFb", "name": "Proxy-3"},
]