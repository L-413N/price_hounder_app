# test_pipeline.py
import asyncio
from pipeline import parse_and_save_to_db
from database import init_db, get_products_for_monitoring

async def main():
    # Инициализируем БД
    init_db()

    # Список тестовых URL
    test_urls = [
        "https://www.ozon.ru/product/rozhkovaya-poluavtomaticheskaya-kofemashina-s-kapuchinatorom-xiaomi-scishare-s1181-belaya-2272648319/",
        "https://www.ozon.ru/product/playstation-5-dualsense-midnight-black-besprovodnoy-geympad-267455622/",
        "https://www.ozon.ru/product/zerkalo-dlya-makiyazha-2102305299/",
        "https://www.ozon.ru/product/podveska-1843054678/",
        "https://www.ozon.ru/product/stayler-dyson-hs08-airwrap-vinca-blue-topaz-533818-01-1856921641/",
    ]

    # 🔥 Запускаем ВСЕ задачи параллельно
    tasks = [parse_and_save_to_db(url, user_id=12345) for url in test_urls]
    results = await asyncio.gather(*tasks)

    # Проверяем, что товары в БД
    print("\n📊 Товары в мониторинге:")
    products = get_products_for_monitoring()
    for p in products:
        print(f"  {p['title']} — {p['last_price']} ₽ (след. проверка: {p['next_check']})")

if __name__ == "__main__":
    asyncio.run(main())