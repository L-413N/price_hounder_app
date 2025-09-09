import requests

def analyze_ip(ip):
    try:
        # Проверяем IP через ipapi.co (бесплатно, без API-ключа)
        url = f"https://ipapi.co/{ip}/json/"
        response = requests.get(url, timeout=10)
        data = response.json()

        print("🔍 АНАЛИЗ IP:", ip)
        print("-" * 50)
        print(f"Страна: {data.get('country_name', '—')} ({data.get('country_code', '—')})")
        print(f"Регион: {data.get('region', '—')}")
        print(f"Город: {data.get('city', '—')}")
        print(f"Провайдер (ASN): {data.get('org', '—')}")
        print(f"Тип IP: {data.get('asn_type', '—')}")
        print(f"Часовой пояс: {data.get('timezone', '—')}")

        asn_type = data.get("asn_type", "").lower()
        if "mobile" in asn_type or "cellular" in asn_type:
            print("\n✅ Это МОБИЛЬНЫЙ IP — Ozon его реже блокирует")
        elif "hosting" in asn_type or "data center" in asn_type:
            print("\n❌ Это ДАТА-ЦЕНТРОВЫЙ IP — Ozon его БЛОКИРУЕТ")
        else:
            print("\n⚠️ Это РЕЗИДЕНТНЫЙ (домашний) IP — может работать, но не гарантировано")

    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")

# Проверяем твой IP
analyze_ip("91.198.218.98")