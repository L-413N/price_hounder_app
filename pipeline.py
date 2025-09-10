# pipeline.py
import os
import asyncio
import logging
from typing import Iterable, List, Optional

from mp_parser import parse_product
from database import (
    init_db,
    save_price_snapshot,
    schedule_fail,
    get_last_price_and_checked,
)

# ---------------- Логирование ----------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pipeline")

# Ограничение параллелизма внутри процесса
CONCURRENCY = int(os.getenv("CONCURRENCY", "3"))
_semaphore = asyncio.Semaphore(CONCURRENCY)

# Порог для предупреждения (в процентах), 0 = отключено
PRICE_CHANGE_ALERT_PCT = float(os.getenv("PRICE_CHANGE_ALERT_PCT", "0"))

# Инициализируем БД один раз за процесс
_init_done = False
def _ensure_db_once() -> None:
    global _init_done
    if not _init_done:
        init_db()
        _init_done = True


async def parse_and_save_to_db(url: str, user_id: Optional[int] = None) -> bool:
    """
    Асинхронная корутина:
      - парсит карточку товара,
      - логирует дельту цены (если есть предыдущая),
      - сохраняет снэпшот цены при успехе,
      - планирует бэкофф при неудаче.
    Возвращает True при успехе, False при неудаче.
    Параметр user_id принят для совместимости с тестами; в БД сейчас не используется.
    """
    _ensure_db_once()

    print(f"🔍 Начинаю парсинг: {url}")
    async with _semaphore:
        info = await parse_product(url)

    if info is not None:
        # Посмотрим, что было до этого
        prev = get_last_price_and_checked(info.url)
        prev_price = prev[0] if prev else None

        if isinstance(prev_price, int):
            diff = info.price - prev_price
            if prev_price > 0:
                pct = (diff / prev_price) * 100.0
            else:
                pct = 0.0
            arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
            logger.info(
                f"💰 Изменение цены: {arrow} {abs(diff)} ₽ ({pct:+.2f}%) — {info.title}"
            )
            # Предупреждение при превышении порога
            if PRICE_CHANGE_ALERT_PCT > 0 and abs(pct) >= PRICE_CHANGE_ALERT_PCT and diff != 0:
                logger.warning(
                    f"⚡ Существенное изменение цены ({pct:+.2f}%) для {info.url}"
                )
        else:
            logger.info(f"🆕 Первая фиксация цены: {info.price} ₽ — {info.title}")

        # Сохраняем снэпшот и планирование
        save_price_snapshot(info.url, info.price, currency="₽", title=info.title)
        return True
    else:
        schedule_fail(url)
        return False


async def run_batch(urls: Iterable[str], user_id: Optional[int] = None) -> List[bool]:
    """
    Удобный батч-раннер: принимает коллекцию URL, возвращает список флагов успеха.
    """
    tasks = [asyncio.create_task(parse_and_save_to_db(u, user_id=user_id)) for u in urls]
    results = await asyncio.gather(*tasks)
    return list(results)


def run_cli(urls: List[str]) -> None:
    """
    Синхронная точка входа для запуска из командной строки.
    """
    _ensure_db_once()
    asyncio.run(run_batch(urls))


if __name__ == "__main__":
    # Пример:
    #   python pipeline.py "https://www.ozon.ru/product/..." "https://www.ozon.ru/product/..."
    import sys
    if len(sys.argv) < 2:
        print("Укажите хотя бы один URL товара Ozon в аргументах.")
        sys.exit(1)
    run_cli(sys.argv[1:])
