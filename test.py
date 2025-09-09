import asyncio
from mp_parser import parse_product, ProductInfo

async def main():
    url = "https://www.ozon.ru/product/rozhkovaya-poluavtomaticheskaya-kofemashina-s-kapuchinatorom-xiaomi-scishare-s1181-belaya-2272648319/"
    result: ProductInfo = await parse_product(url)
    print(f"✅ {result.title}")
    print(f"💰 {result.price} {result.currency}")
    if result.error:
        print(f"❌ {result.error}")

if __name__ == "__main__":
    asyncio.run(main())