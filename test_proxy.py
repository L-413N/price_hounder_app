# test_proxy.py
import asyncio
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth  # ← ИСПРАВЛЕНО: stealth вместо stealth_async

# === 🔑 Прокси ===
PROXY = {
    "server": "http://91.198.218.98:8000",
    "username": "mgtMWq",
    "password": "dQGA1d"
}

# === 🧠 User-Agent и заголовки ===
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-CH-UA": '"Chromium";v="124", "Microsoft Edge";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

async def test_proxy():
    print("🚀 Запускаем тест прокси в Docker...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy=PROXY,
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
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ],
        )

        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers=HEADERS,
            ignore_https_errors=True,
        )

        page = await context.new_page()

        # 👤 Применяем stealth (синхронная функция!)
        await stealth.stealth(page)  # ← ИСПРАВЛЕНО: await stealth(page)

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

        # 👤 Имитация поведения: заходим на главную
        print("🏠 Имитация: заходим на главную страницу Ozon...")
        await page.goto("https://www.ozon.ru", wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(2, 5))

        # Случайное движение мыши + клик
        await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.mouse.click(300, 50)
        await asyncio.sleep(random.uniform(1, 2))

        # 🎯 Переходим на страницу товара
        TEST_PRODUCT_URL = "https://www.ozon.ru/product/rozhkovaya-poluavtomaticheskaya-kofemashina-s-kapuchinatorom-xiaomi-scishare-s1181-belaya-2272648319/"
        print(f"🛍️ Переходим на страницу товара: {TEST_PRODUCT_URL}")
        await page.goto(TEST_PRODUCT_URL, wait_until="domcontentloaded")

        await asyncio.sleep(random.uniform(2, 4))
        await page.mouse.wheel(0, 800)
        await asyncio.sleep(1)

        # 🎯 Проверяем заголовок
        title_element = await page.query_selector("h1")
        title = await title_element.inner_text() if title_element else "Не найдено"
        print(f"✅ Успешно! Заголовок товара: {title}")

        # Проверяем IP
        ip = await page.evaluate("""
            fetch('https://api.ipify.org?format=json')
                .then(r => r.json())
                .then(d => d.ip)
                .catch(() => 'Не удалось определить')
        """)
        print(f"🌐 IP через прокси: {ip}")

        # 📸 Сохраняем скриншот
        await page.screenshot(path="debug.png")
        print("📸 Скриншот сохранён: debug.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_proxy())