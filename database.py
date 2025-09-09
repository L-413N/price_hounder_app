# database.py
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List
from mp_parser.models import ProductInfo

DB_PATH = "price_hounder.db"

def init_db():
    """Создаёт таблицы, если их нет."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            last_price INTEGER,
            currency TEXT DEFAULT '₽',
            last_check DATETIME,
            next_check DATETIME,
            check_interval_hours REAL DEFAULT 6.0,
            captcha_failure_rate REAL DEFAULT 0.0,
            is_active BOOLEAN DEFAULT 1,
            user_id INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована.")

def add_product_to_monitoring(product: ProductInfo, user_id: int = 0) -> bool:
    """Добавляет товар в мониторинг."""
    if not product.title or not product.price:
        print("❌ Не удалось добавить товар: нет названия или цены.")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now = datetime.now()
    next_check = now + timedelta(hours=6)  # начальный интервал — 6 часов

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO products 
            (url, title, last_price, last_check, next_check, check_interval_hours, user_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product.url,
            product.title,
            product.price,
            now,
            next_check,
            6.0,
            user_id,
            True
        ))
        conn.commit()
        print(f"✅ Товар добавлен в мониторинг: {product.title} — {product.price} ₽")
        return True
    except Exception as e:
        print(f"❌ Ошибка при добавлении в БД: {e}")
        return False
    finally:
        conn.close()

def get_products_for_monitoring() -> List[dict]:
    """Возвращает список товаров, готовых к проверке."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now = datetime.now()
    cursor.execute("""
        SELECT id, url, title, last_price, next_check, check_interval_hours, captcha_failure_rate, user_id
        FROM products 
        WHERE is_active = 1 AND next_check <= ?
    """, (now,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "url": row[1],
            "title": row[2],
            "last_price": row[3],
            "next_check": row[4],
            "check_interval_hours": row[5],
            "captcha_failure_rate": row[6],
            "user_id": row[7]
        }
        for row in rows
    ]