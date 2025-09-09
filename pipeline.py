# pipeline.py
import asyncio
from mp_parser import parse_product
from database import add_product_to_monitoring
from mp_parser.config import PROXY_POOL

# Ограничиваем одновременные задачи
MAX_CONCURRENT_TASKS = len(PROXY_POOL)  # или len(PROXY_POOL) + 1
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

async def parse_and_save_to_db(url: str, user_id: int = 0) -> bool:
    async with semaphore:  # ← ОГРАНИЧИВАЕМ ПАРАЛЛЕЛИЗМ
        print(f"🔍 Начинаю парсинг: {url}")
        product = await parse_product(url)

        if product.error:
            print(f"❌ Ошибка парсинга: {product.error}")
            return False

        if not product.price:
            print("❌ Цена не найдена — товар не добавлен в мониторинг.")
            return False

        success = add_product_to_monitoring(product, user_id)
        return success