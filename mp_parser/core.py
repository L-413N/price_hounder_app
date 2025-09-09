import asyncio
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from .models import ProductInfo
from .config import *
from .utils import *
import logging

# Создаём отдельный логгер для модуля mp_parser
logger = logging.getLogger("mp_parser")
logger.setLevel(logging.INFO)

# Если обработчик ещё не добавлен — добавляем
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

async def is_cloudflare_active(page) -> bool:
    content = await page.content()
    triggers = [
        "Пожалуйста, включите JavaScript",
        "Нам нужно убедиться, что вы не робот",
        "Checking your browser",
    ]
    return any(trigger in content for trigger in triggers)

async def extract_price(page) -> int:
    selectors = [
        "[data-widget='webPrice'] span:nth-child(1)",
        "span[data-widget='webSale']",
        "span[data-widget='price']",
    ]
    for selector in selectors:
        try:
            elem = await page.wait_for_selector(selector, timeout=5000)
            if elem:
                text = await elem.inner_text()
                price_str = "".join(filter(str.isdigit, text))
                return int(price_str) if price_str else None
        except:
            continue
    return None

async def parse_product(url: str, retry_count: int = 0) -> ProductInfo:
    logger.info(f"🚀 Начинаю парсинг товара: {url} (попытка {retry_count + 1})")
    url = clean_url(url)
    if retry_count >= MAX_RETRIES:
        return ProductInfo(url=url, error="Max retries exceeded")

    if is_permanent_failure(url):
        return ProductInfo(url=url, error="Too many CAPTCHA")

    proxy = get_random_proxy(PROXY_POOL)
    logger.info(f"🌐 Выбран прокси: {proxy['name']}")

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={
                    "server": proxy["server"],
                    "username": proxy["username"],
                    "password": proxy["password"],
                },
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ],
            )

            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                extra_http_headers=HEADERS,
            )

            page = await context.new_page()
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
            """)

            # 👤 Имитация поведения
            logger.debug("🏠 Имитация: заходим на главную Ozon...")
            await page.goto("https://www.ozon.ru", wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1, 2))
            await page.mouse.move(300, 200)
            await page.mouse.click(300, 50)
            await asyncio.sleep(1)

            # 🎯 Загрузка товара
            logger.debug(f"🛍️ Переходим на страницу товара: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            await asyncio.sleep(random.uniform(2, 3))
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1)

            # 🛡️ Проверка CAPTCHA
            if await is_cloudflare_active(page):
                logger.warning(f"⚠️ Cloudflare CAPTCHA на {url} (прокси: {proxy['name']}). Повторная попытка...")
                record_failure(url)
                await asyncio.sleep(random.uniform(5, 8))
                return await parse_product(url, retry_count + 1)

            # 📌 Ждём заголовок
            try:
                await page.wait_for_selector("h1", timeout=ELEMENT_WAIT_TIMEOUT)
            except PlaywrightTimeoutError:
                await asyncio.sleep(random.uniform(5, 8))
                return await parse_product(url, retry_count + 1)

            # 🎯 Извлечение данных
            title_elem = await page.query_selector("h1")
            title = await title_elem.inner_text() if title_elem else None
            price = await extract_price(page)

            # ⏱️ Задержка
            if price:
                logger.info(f"✅ Успешно спарсено: {title} — {price} ₽ (через {proxy['name']})")
            else:
                logger.warning(f"⚠️ Цена не найдена для {url}")

            return ProductInfo(
                url=url,
                title=title,
                price=price,
                error=None,
                captcha_rate=FAILED_ATTEMPTS[url] / max(1, retry_count + 1)
            )

    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге {url} через {proxy['name']}: {e}")
        await asyncio.sleep(random.uniform(5, 8))
        return await parse_product(url, retry_count + 1)
    finally:
        if browser:
            await browser.close()