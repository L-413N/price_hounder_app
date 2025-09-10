# mp_parser/core.py
import os
import asyncio
import random
import json
import logging
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Совместимость с разными версиями playwright-stealth
try:
    from playwright_stealth import stealth_async as _stealth_async   # v1.x
    _STEALTH_MODE = "v1"
except Exception:
    try:
        from playwright_stealth import Stealth as _Stealth           # v2.x
        _stealth = _Stealth()
        _STEALTH_MODE = "v2"
    except Exception:
        _STEALTH_MODE = "none"

from .models import ProductInfo
from .config import (
    USER_AGENTS, HEADERS, PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, MAX_RETRIES, DELAY_RANGE,
    BLOCK_RESOURCES, TIMEZONE_ID, HEADLESS,
    HOMEPAGE_URL, HOMEPAGE_WARMUP, REFERER_ON_PRODUCT_GOTO, NAVIGATION_WAIT_UNTIL,
    PERSIST_COOKIES, STATE_DIR
)
from .utils import (
    clean_url, record_failure, record_success, FAILED_ATTEMPTS,
    parse_price_from_text, ensure_dir
)
from .proxy_manager import proxy_manager

logger = logging.getLogger("mp_parser")


async def _apply_stealth(context=None, page=None) -> None:
    if _STEALTH_MODE == "v1" and page is not None:
        try:
            await _stealth_async(page)
        except Exception as e:
            logger.debug(f"stealth v1 failed: {e}")
    elif _STEALTH_MODE == "v2" and context is not None:
        try:
            await _stealth.apply_stealth_async(context)
        except Exception as e:
            logger.debug(f"stealth v2 failed: {e}")
    else:
        logger.debug("Stealth plugin not available — continuing without it.")


async def _humanize(page) -> None:
    try:
        await page.mouse.move(random.randint(100, 800), random.randint(100, 600), steps=random.randint(8, 20))
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await page.mouse.move(random.randint(200, 1000), random.randint(200, 700), steps=random.randint(8, 20))
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await page.mouse.wheel(0, random.randint(500, 1500))
        await asyncio.sleep(random.uniform(0.4, 0.9))
    except Exception:
        pass


async def _extract_title(page) -> Optional[str]:
    try:
        h1 = await page.query_selector("h1")
        if h1:
            txt = await h1.inner_text()
            return (txt or "").strip()
    except Exception:
        pass
    return None


async def _extract_price_dom(page) -> Optional[int]:
    selectors = [
        "[data-widget='webPrice'] span",
        "[data-widget='webPrice']",
        "[data-widget='pdpSale']",
        "div:has(> span:has-text('₽')) span",
        "span:has-text('₽')",
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if not el:
                continue
            text = (await el.inner_text()) or ""
            price = parse_price_from_text(text)
            if price:
                return price
        except Exception:
            continue
    return None


async def _extract_price_jsonld(page) -> Optional[int]:
    try:
        scripts = await page.query_selector_all("script[type='application/ld+json']")
        for s in scripts:
            try:
                raw = await s.inner_text()
                data = json.loads(raw)
                cand = None
                if isinstance(data, list):
                    cand = next((d for d in data if isinstance(d, dict) and d.get("@type") == "Product"), None)
                elif isinstance(data, dict) and data.get("@type") == "Product":
                    cand = data
                if not cand:
                    continue
                offers = cand.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price_str = offers.get("price") or offers.get("lowPrice")
                if price_str:
                    return parse_price_from_text(str(price_str))
            except Exception:
                continue
    except Exception:
        pass
    return None


async def parse_product(url: str, retry_count: int = 0, last_proxy_name: Optional[str] = None) -> Optional[ProductInfo]:
    url = clean_url(url)

    # выбор прокси (здоровый + не тот же)
    proxy = proxy_manager.choose_proxy(exclude=[last_proxy_name] if last_proxy_name else None)
    proxy_name = proxy.get("name") if proxy else "NO_PROXY"
    logger.info(f"🚀 Начинаю парсинг товара: {url} (попытка {retry_count + 1})")
    logger.info(f"🌐 Выбран прокси: {proxy_name}")

    ua = random.choice(USER_AGENTS)
    locale = HEADERS.get("Accept-Language", "ru-RU").split(",")[0].strip()

    proxy_kwargs = None
    if proxy and proxy.get("server"):
        proxy_kwargs = {"server": proxy["server"], "username": proxy.get("username"), "password": proxy.get("password")}

    ensure_dir(STATE_DIR)
    state_path = os.path.join(STATE_DIR, f"{proxy_name}.json") if proxy_name else None
    storage_state_arg = state_path if (state_path and os.path.exists(state_path)) else None

    try:
        async with async_playwright() as pw:
            width = random.randint(1200, 1366)
            height = random.randint(720, 900)
            browser = await pw.chromium.launch(
                headless=HEADLESS,
                proxy=proxy_kwargs,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    f"--window-size={width},{height}",
                    "--lang=ru-RU",
                ],
            )

            context = await browser.new_context(
                user_agent=ua,
                locale=locale,
                timezone_id=TIMEZONE_ID,
                viewport={"width": width, "height": height},
                device_scale_factor=1.0,
                java_script_enabled=True,
                extra_http_headers=HEADERS,
                storage_state=storage_state_arg,
            )

            if BLOCK_RESOURCES:
                await context.route("**/*", lambda route, request: (
                    asyncio.create_task(route.abort())
                    if request.resource_type in {"media", "websocket"}
                    else asyncio.create_task(route.continue_())
                ))

            page = await context.new_page()

            await _apply_stealth(context=context, page=page)

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
            """)

            if HOMEPAGE_WARMUP:
                try:
                    await page.goto(HOMEPAGE_URL, wait_until=NAVIGATION_WAIT_UNTIL, timeout=PAGE_LOAD_TIMEOUT)
                    await asyncio.sleep(random.uniform(0.8, 1.6))
                    await _humanize(page)
                    if state_path:
                        await context.storage_state(path=state_path)
                except Exception as e:
                    logger.debug(f"Домашняя страница прогрев не удался: {e}")

            goto_kwargs = {"wait_until": NAVIGATION_WAIT_UNTIL, "timeout": PAGE_LOAD_TIMEOUT}
            if REFERER_ON_PRODUCT_GOTO:
                goto_kwargs["referer"] = HOMEPAGE_URL

            resp = await page.goto(url, **goto_kwargs)
            if resp and (resp.status >= 500 or resp.status in (403, 429)):
                logger.warning(f"⚠️ Неподходящий статус {resp.status} для {url} (прокси: {proxy_name}). Повторная попытка...")
                record_failure(url)
                proxy_manager.report_failure(proxy_name)
                await context.close()
                await browser.close()
                await asyncio.sleep(random.uniform(*DELAY_RANGE))
                if retry_count + 1 >= MAX_RETRIES:
                    return None
                return await parse_product(url, retry_count + 1, last_proxy_name=proxy_name)

            await asyncio.sleep(random.uniform(1.2, 2.2))
            await _humanize(page)

            title = await _extract_title(page)
            price = await _extract_price_dom(page)
            if price is None:
                price = await _extract_price_jsonld(page)

            attempts = FAILED_ATTEMPTS.get(url, 0)
            captcha_rate = attempts / max(1, retry_count + 1)
            logger.debug(f"captcha_rate={captcha_rate:.3f} attempts={attempts} retry={retry_count}")

            if price is not None:
                record_success(url)
                proxy_manager.report_success(proxy_name)
                logger.info(f"✅ Успешно спарсено: {(title or '').strip()} — {price} ₽ (через {proxy_name})")
                if state_path:
                    try:
                        await context.storage_state(path=state_path)
                    except Exception:
                        pass
                await context.close()
                await browser.close()
                return ProductInfo(url=url, title=title or "", price=price)

            logger.warning(f"⚠️ Цена не найдена для {url} (прокси: {proxy_name})")
            record_failure(url)
            proxy_manager.report_failure(proxy_name)
            await context.close()
            await browser.close()
            if retry_count + 1 >= MAX_RETRIES:
                return None
            await asyncio.sleep(random.uniform(*DELAY_RANGE))
            return await parse_product(url, retry_count + 1, last_proxy_name=proxy_name)

    except PlaywrightTimeoutError as e:
        logger.warning(f"⏳ Timeout при загрузке {url}: {e}")
        record_failure(url)
        proxy_manager.report_failure(proxy_name)
        if retry_count + 1 >= MAX_RETRIES:
            return None
        await asyncio.sleep(random.uniform(*DELAY_RANGE))
        return await parse_product(url, retry_count + 1, last_proxy_name=proxy_name)

    except Exception as e:
        logger.exception(f"💥 Ошибка при парсинге {url}: {e}")
        record_failure(url)
        proxy_manager.report_failure(proxy_name)
        if retry_count + 1 >= MAX_RETRIES:
            return None
        await asyncio.sleep(random.uniform(*DELAY_RANGE))
        return await parse_product(url, retry_count + 1, last_proxy_name=proxy_name)
