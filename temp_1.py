import asyncio
import random
from playwright.async_api import async_playwright

# === 🔑 НАСТРОЙКИ ПРОКСИ (Proxy6 Mobile) ===
PROXY_IP = "91.198.218.98"
PROXY_PORT = "8000"
PROXY_USERNAME = "mgtMWq"
PROXY_PASSWORD = "dQGA1d"

PRODUCT_URL = "https://www.ozon.ru/product/rozhkovaya-poluavtomaticheskaya-kofemashina-s-kapuchinatorom-xiaomi-scishare-s1181-belaya-2272648319/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

async def parse_ozon_product(url):
    user_agent = random.choice(USER_AGENTS)

    proxy_config = {
        "server": f"http://{PROXY_IP}:{PROXY_PORT}",
        "username": PROXY_USERNAME,
        "password": PROXY_PASSWORD,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            proxy=proxy_config,
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
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080",
            ],
        )

        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": random.randint(1200, 1920), "height": random.randint(800, 1080)},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers=HEADERS,
            ignore_https_errors=True,
            storage_state=None,
            bypass_csp=True,
        )

        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
        """)

        # Очищаем куки и кэш
        await context.clear_cookies()

        print(f"🚀 Открываю Ozon через мобильный прокси Proxy6 ({PROXY_IP})...")
        try:
            # Сначала загружаем пустую страницу
            await page.goto("about:blank")
            await asyncio.sleep(1)

            # Теперь целевую страницу
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Ждём и скроллим
            await asyncio.sleep(random.uniform(2, 4))
            await page.mouse.wheel(0, 500)

            # Проверяем содержимое — нет ли Cloudflare
            content = await page.content()
            if "fab_chlg_" in content or "Доступ ограничен" in content:
                print("❌ Обнаружена блокировка Cloudflare — сохраняю скриншот для анализа")
                await page.screenshot(path="cloudflare_block.png", full_page=True)
                await browser.close()
                return

            # Парсим название
            title = None
            selectors = [
                "h1",
                "div[data-widget='webProductHeading'] h1",
                "div#productHeading h1",
            ]
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        title = await el.inner_text()
                        if title.strip():
                            break
                except:
                    continue

            # Парсим цену
            price = None
            price_selectors = [
                "span[data-widget='webPrice'] span:first-child",
                "div[data-widget='webPrice'] span:first-child",
                "span[style*='font-size: 24px']",
                "span[style*='font-size: 32px']",
            ]
            for sel in price_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        clean = "".join(filter(str.isdigit, text))
                        if clean:
                            price = int(clean)
                            break
                except:
                    continue

            print("\n" + "="*60)
            print("📦 РЕЗУЛЬТАТ ПАРСИНГА")
            print("="*60)
            print(f"📌 Название: {title or 'Не найдено'}")
            print(f"💰 Цена: {price} ₽" if price else "💰 Цена: Не найдена")

            await page.screenshot(path="ozon_success.png", full_page=True)
            print("✅ Скриншот сохранён: ozon_success.png")

            # Проверяем IP через браузер
            try:
                ip_js = await page.evaluate("""
                    fetch('https://api.ipify.org?format=json')
                        .then(r => r.json())
                        .then(data => data.ip)
                        .catch(() => 'Не удалось определить')
                """)
                print(f"🌐 IP через браузер: {ip_js}")
            except Exception as e:
                print(f"🌐 Не удалось получить IP через JS: {e}")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await page.screenshot(path="error_screenshot.png", full_page=True)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(parse_ozon_product(PRODUCT_URL))