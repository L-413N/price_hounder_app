import asyncio
import random
import logging
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from tqdm.asyncio import tqdm

# === 🔑 ПУЛ ПРОКСИ ===
PROXY_POOL = [
    {
        "server": "http://91.198.218.98:8000",
        "username": "mgtMWq",
        "password": "dQGA1d",
        "name": "Proxy-1"
    },
    {
        "server": "http://45.129.6.59:8000",  # ← ЗАМЕНИТЕ НА ВАШ ВТОРОЙ ПРОКСИ
        "username": "W92JQn",             # ← ЗАМЕНИТЕ
        "password": "w9XVRo",             # ← ЗАМЕНИТЕ
        "name": "Proxy-2"
    },
        {
        "server": "http://45.129.5.145:8000",      # ← Замените на IP:PORT вашего ТРЕТЬЕГО прокси
        "username": "WgS3cy",                       # ← Логин третьего прокси
        "password": "Co4hFb",                       # ← Пароль третьего прокси
        "name": "Proxy-3"                          # ← Уникальное имя для логов
    },
]

# === 🎯 СПИСОК ЦЕЛЕВЫХ СТРАНИЦ ===
PRODUCT_URLS = [
    "https://www.ozon.ru/product/apple-planshet-ipad-10th-gen-wi-fi-10-9-64-gb-rozovyy-758702973/?at=46tRM1m5QIL6J14Nuzmwvmxiyr6GqGsXG2k6KF9Ayjm9",
    "https://www.ozon.ru/product/samsung-planshet-galaxy-tab-s10-fe-sm-x620-wi-fi-rostest-eac-13-10-8-gb-128-gb-goluboy-1992879788/?at=RltyjLRWkhYQzWgns03nmDMf6kA9mSwEvwkNsE6J89Q",
    "https://www.ozon.ru/product/oneplus-planshet-pad-2-globalnaya-versiya-12-1-256-gb-svetlo-seryy-2259894750/?at=GRt2KM04pFKwY1Zwt5D3Yo3SrlP1ori3DO9G6FmO22L",
    "https://www.ozon.ru/product/igrovaya-konsol-playstation-5-slim-blu-ray-1316509567",
    "https://www.ozon.ru/product/playstation-5-dualsense-midnight-black-besprovodnoy-geympad-267455622/?at=oZt6jzBYLcWXA2vBuD4J9o2HnA4LKoCzYWg5OF1n1JYQ",
    "https://www.ozon.ru/product/stayler-dyson-hs08-airwrap-vinca-blue-topaz-533818-01-1856921641/?at=28t0PwR3JCQAq7yGHDGzlzOhBl66YJSvm6V3ZIRQ4X5o",
    "https://www.ozon.ru/product/podveska-1843054678/",
    "https://www.ozon.ru/product/zerkalo-dlya-makiyazha-2102305299/",
    "https://www.ozon.ru/product/zerkalo-krugloe-kosmeticheskoe-dlya-makiyazha-nastolnoe-s-podsvetkoy-led-2669875041/"

]

# === 🧠 User-Agent и заголовки ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# === ⚙️ Настройки ===
MAX_RETRIES = 5
MAX_CONCURRENT_TASKS = 3  # Теперь можно 3 — у вас 3 прокси!
PAGE_LOAD_TIMEOUT = 60000
ELEMENT_WAIT_TIMEOUT = 15000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def is_cloudflare_active(page):
    content = await page.content()
    cloudflare_triggers = [
        "Пожалуйста, включите JavaScript для продолжения",
        "Нам нужно убедиться, что вы не робот",
        "Please, enable JavaScript to continue",
        "We need to make sure that you are not a robot",
        "Checking your browser",
        "Just a moment...",
    ]
    return any(trigger in content for trigger in cloudflare_triggers)

async def extract_price(page):
    price_selectors = [
        "[data-widget='webPrice'] span:nth-child(1)",
        "span[data-widget='webSale']",
        "span[data-widget='price']",
        "div[data-widget='webPrice'] > span:first-child",
    ]

    for selector in price_selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=5000)
            if element:
                text = await element.inner_text()
                price_str = "".join(filter(str.isdigit, text))
                if price_str:
                    return int(price_str)
        except Exception:
            continue
    return None

async def parse_ozon_product(url, retry_count=0):
    if retry_count >= MAX_RETRIES:
        logger.error(f"❌ Превышено максимальное количество попыток для {url}.")
        return {"url": url, "title": None, "price": None, "proxy_used": None, "error": "Max retries exceeded"}

    # Выбираем случайный прокси из пула
    proxy_config = random.choice(PROXY_POOL)
    proxy_name = proxy_config["name"]
    logger.info(f"🌐 Использую прокси: {proxy_name} для {url}")

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={
                    "server": proxy_config["server"],
                    "username": proxy_config["username"],
                    "password": proxy_config["password"],
                },
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--window-size=1920,1080",
                ],
            )

            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),  # Ротация UA
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                extra_http_headers=HEADERS,
                ignore_https_errors=True,
            )

            page = await context.new_page()

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
                window.chrome = {runtime: {}};
                Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
            """)

            logger.debug(f"🌐 Открываю страницу: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)

            await asyncio.sleep(random.uniform(2, 4))
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1)

            if await is_cloudflare_active(page):
                logger.warning(f"⚠️ Cloudflare CAPTCHA на {url} (прокси: {proxy_name}). Повторная попытка...")
                await asyncio.sleep(random.uniform(5, 10))
                return await parse_ozon_product(url, retry_count + 1)

            try:
                await page.wait_for_selector("h1", timeout=ELEMENT_WAIT_TIMEOUT)
            except PlaywrightTimeoutError:
                logger.warning(f"⏳ Заголовок не найден на {url} (прокси: {proxy_name}). Повтор...")
                await asyncio.sleep(random.uniform(5, 10))
                return await parse_ozon_product(url, retry_count + 1)

            title_element = await page.query_selector("h1")
            title = await title_element.inner_text() if title_element else None
            price = await extract_price(page)

            logger.info(f"✅ Успешно через {proxy_name}: {title or 'Без названия'} — {price} ₽")

            await page.screenshot(path=f"result_{hash(url) % 10000}.png")

            # 👇 ЗАДЕРЖКА МЕЖДУ ТОВАРАМИ — КРИТИЧНО ДЛЯ БЕЗОПАСНОСТИ!
            await asyncio.sleep(random.uniform(5, 8))

            return {
                "url": url,
                "title": title,
                "price": price,
                "proxy_used": proxy_name,
                "error": None
            }

    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге {url} через {proxy_name}: {e}")
        await asyncio.sleep(random.uniform(5, 10))
        return await parse_ozon_product(url, retry_count + 1)

    finally:
        if browser:
            await browser.close()

async def main():
    logger.info("🏁 Начало массового парсинга с ротацией прокси...")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def parse_with_semaphore(url):
        async with semaphore:
            return await parse_ozon_product(url)

    tasks = [parse_with_semaphore(url) for url in PRODUCT_URLS]
    results = await tqdm.gather(*tasks, desc="📊 Парсинг товаров")

    with open("products_data.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    logger.info("🎉 Массовый парсинг завершён!")
    logger.info(f"💾 Результаты сохранены в products_data.json")

    print("\n" + "="*80)
    print("📈 ОТЧЁТ ПО ПАРСИНГУ (с указанием прокси)")
    print("="*80)
    for res in results:
        status = "✅" if res["price"] else "❌"
        proxy = res.get("proxy_used", "N/A")
        print(f"{status} [{proxy}] {res['title'] or 'Неизвестно'} — {res['price'] or 'Цена не найдена'} ₽")

if __name__ == "__main__":
    asyncio.run(main())