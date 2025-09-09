import asyncio
import random
import logging
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from tqdm.asyncio import tqdm
from collections import defaultdict

# === 🔑 ПУЛ ПРОКСИ ===
PROXY_POOL = [
    {
        "server": "http://91.198.218.98:8000",
        "username": "mgtMWq",
        "password": "dQGA1d",
        "name": "Proxy-1"
    },
    {
        "server": "http://45.129.6.59:8000",
        "username": "W92JQn",
        "password": "w9XVRo",
        "name": "Proxy-2"
    },
    {
        "server": "http://45.129.5.145:8000",
        "username": "WgS3cy",
        "password": "Co4hFb",
        "name": "Proxy-3"
    },
]

# === 🎯 СПИСОК ЦЕЛЕВЫХ СТРАНИЦ ===
PRODUCT_URLS = [
    "https://www.ozon.ru/product/apple-planshet-ipad-10th-gen-wi-fi-10-9-64-gb-rozovyy-758702973/?at=46tRM1m5QIL6J14Nuzmwvmxiyr6GqGsXG2k6KF9Ayjm9",
    "  https://www.ozon.ru/product/samsung-planshet-galaxy-tab-s10-fe-sm-x620-wi-fi-rostest-eac-13-10-8-gb-128-gb-goluboy-1992879788/?at=RltyjLRWkhYQzWgns03nmDMf6kA9mSwEvwkNsE6J89Q",
    "  https://www.ozon.ru/product/oneplus-planshet-pad-2-globalnaya-versiya-12-1-256-gb-svetlo-seryy-2259894750/?at=GRt2KM04pFKwY1Zwt5D3Yo3SrlP1ori3DO9G6FmO22L",
    "  https://www.ozon.ru/product/igrovaya-konsol-playstation-5-slim-blu-ray-1316509567  ",
    "https://www.ozon.ru/product/playstation-5-dualsense-midnight-black-besprovodnoy-geympad-267455622/?at=oZt6jzBYLcWXA2vBuD4J9o2HnA4LKoCzYWg5OF1n1JYQ",
    "  https://www.ozon.ru/product/stayler-dyson-hs08-airwrap-vinca-blue-topaz-533818-01-1856921641/?at=28t0PwR3JCQAq7yGHDGzlzOhBl66YJSvm6V3ZIRQ4X5o",
    "  https://www.ozon.ru/product/podveska-1843054678/  ",
    "https://www.ozon.ru/product/zerkalo-dlya-makiyazha-2102305299/  ",
    "https://www.ozon.ru/product/zerkalo-krugloe-kosmeticheskoe-dlya-makiyazha-nastolnoe-s-podsvetkoy-led-2669875041/  ",
    "https://www.ozon.ru/product/skladnaya-massazhnaya-rascheska-s-zerkalom-i-serebristym-remeshkom-2005394462/",
    "https://www.ozon.ru/product/longsliv-1990576530/",
    "https://www.ozon.ru/product/sumka-1892877113/",
    "https://www.ozon.ru/product/24-sht-dlinnye-nakladnye-nogti-shokoladnyy-tsvet-frantsuzskiy-manikyur-s-bantami-i-zhemchugom-1614089483/",
    "https://www.ozon.ru/product/komplekt-chulok-a-1112501074/",
    "https://www.ozon.ru/product/bluzka-teentory-1637762427/?at=DqtDNVDY9ilPrO0MIwyBO16h7B4n62U3YqL63cr1WoYX",
    "https://www.ozon.ru/product/eko-gel-dlya-stirki-tsvetnogo-belya-5-litrov-s-aromatom-tsvetushchaya-sakura-zhidkiy-stiralnyy-1667614503/",
    "https://www.ozon.ru/product/philips-avtomaticheskaya-kofemashina-lattego-ep3246-70-chernyy-487184469/"
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
MAX_CONCURRENT_TASKS = 3
PAGE_LOAD_TIMEOUT = 60000
ELEMENT_WAIT_TIMEOUT = 15000

# Защита от бесконечных CAPTCHA
FAILED_ATTEMPTS = defaultdict(int)
MAX_FAILED_ATTEMPTS_PER_URL = 10

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
    url = url.strip()  # ✅ Очистка URL от пробелов

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
                user_agent=random.choice(USER_AGENTS),
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

            # 🧠 Имитация поведения человека: заходим на главную
            logger.debug("🏠 Имитация: заходим на главную страницу Ozon...")
            await page.goto("https://www.ozon.ru", wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1, 3))

            # Случайное движение мыши + клик
            await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.mouse.click(300, 50)  # клик в шапку сайта
            await asyncio.sleep(random.uniform(0.5, 1))

            # Переходим на целевую страницу
            logger.debug(f"🌐 Открываю страницу: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)

            await asyncio.sleep(random.uniform(2, 4))
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1)

            # Проверка Cloudflare
            if await is_cloudflare_active(page):
                FAILED_ATTEMPTS[url] += 1
                if FAILED_ATTEMPTS[url] > MAX_FAILED_ATTEMPTS_PER_URL:
                    logger.error(f"⛔ Слишком много CAPTCHA для {url}. Пропускаем.")
                    return {"url": url, "title": None, "price": None, "proxy_used": proxy_name, "error": "Too many CAPTCHA"}

                logger.warning(f"⚠️ Cloudflare CAPTCHA на {url} (прокси: {proxy_name}). Повторная попытка...")
                await asyncio.sleep(random.uniform(5, 10))
                return await parse_ozon_product(url, retry_count + 1)

            # Ожидание заголовка
            try:
                await page.wait_for_selector("h1", timeout=ELEMENT_WAIT_TIMEOUT)
            except PlaywrightTimeoutError:
                logger.warning(f"⏳ Заголовок не найден на {url} (прокси: {proxy_name}). Повтор...")
                await asyncio.sleep(random.uniform(5, 10))
                return await parse_ozon_product(url, retry_count + 1)

            # Парсинг данных
            title_element = await page.query_selector("h1")
            title = await title_element.inner_text() if title_element else None
            price = await extract_price(page)

            logger.info(f"✅ Успешно через {proxy_name}: {title or 'Без названия'} — {price} ₽")

            # 👇 ЗАДЕРЖКА МЕЖДУ ТОВАРАМИ
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

    # Промежуточное сохранение
    async def parse_with_semaphore(url):
        async with semaphore:
            result = await parse_ozon_product(url)
            # Сохраняем промежуточный результат
            try:
                with open("partial_results.json", "r", encoding="utf-8") as f:
                    partial = json.load(f)
            except FileNotFoundError:
                partial = []

            partial.append(result)
            with open("partial_results.json", "w", encoding="utf-8") as f:
                json.dump(partial, f, ensure_ascii=False, indent=4)

            return result

    tasks = [parse_with_semaphore(url) for url in PRODUCT_URLS]
    results = await tqdm.gather(*tasks, desc="📊 Парсинг товаров")

    # Финальное сохранение
    with open("products_data.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    logger.info("🎉 Массовый парсинг завершён!")
    logger.info(f"💾 Результаты сохранены в products_data.json")

    # 📊 Отчёт по результатам
    print("\n" + "="*80)
    print("📈 ОТЧЁТ ПО ПАРСИНГУ (с указанием прокси)")
    print("="*80)
    for res in results:
        status = "✅" if res["price"] else "❌"
        proxy = res.get("proxy_used", "N/A")
        print(f"{status} [{proxy}] {res['title'] or 'Неизвестно'} — {res['price'] or 'Цена не найдена'} ₽")

    # 📊 Статистика
    proxy_stats = {}
    problematic_urls = []

    for res in results:
        proxy = res.get("proxy_used")
        if proxy:
            proxy_stats[proxy] = proxy_stats.get(proxy, 0) + 1
        if res["error"]:
            problematic_urls.append(res["url"])

    print("\n" + "="*80)
    print("📊 СТАТИСТИКА")
    print("="*80)
    print("Использование прокси:")
    for proxy, count in proxy_stats.items():
        print(f"  {proxy}: {count} товаров")

    if problematic_urls:
        print(f"\n⚠️ Проблемные URL ({len(problematic_urls)}):")
        for url in problematic_urls:
            print(f"  {url}")
    else:
        print("\n✅ Все товары спарсены успешно!")

if __name__ == "__main__":
    asyncio.run(main())