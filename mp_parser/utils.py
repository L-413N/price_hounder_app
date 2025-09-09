import random
from collections import defaultdict
from typing import Dict, List

# Глобальные счётчики
FAILED_ATTEMPTS = defaultdict(int)
MAX_FAILED_ATTEMPTS_PER_URL = 10

def clean_url(url: str) -> str:
    return url.strip()

def get_random_proxy(proxy_list: List[Dict]) -> Dict:
    return random.choice(proxy_list)

def is_permanent_failure(url: str) -> bool:
    return FAILED_ATTEMPTS[url] > MAX_FAILED_ATTEMPTS_PER_URL

def record_failure(url: str):
    FAILED_ATTEMPTS[url] += 1