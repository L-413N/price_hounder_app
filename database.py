# database.py
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Iterable

DB_PATH = os.getenv("DB_PATH", "database.sqlite3")

# Базовый интервал проверки (часы), если не задан в самой записи продукта
DEFAULT_CHECK_INTERVAL_HOURS = int(os.getenv("DEFAULT_CHECK_INTERVAL_HOURS", "6"))

# Лестница бэкоффа по числу подряд неудач (fail_count)
# 1-я неудача -> +1ч, затем +3ч, +6ч, +12ч, +24ч, далее всегда +24ч
FAIL_BACKOFF_HOURS = [1, 3, 6, 12, 24]

# Печатаем «инициализирована» только 1 раз за процесс
_INIT_PRINTED = False


def _connect() -> sqlite3.Connection:
    """
    Возвращает соединение с включёнными настройками для параллельной записи.
    """
    con = sqlite3.connect(DB_PATH, isolation_level=None, timeout=5.0)  # autocommit, 5s busy timeout на connect
    con.row_factory = sqlite3.Row
    # Важные PRAGMA (на каждое соединение)
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA synchronous = NORMAL;")
    con.execute("PRAGMA busy_timeout = 5000;")      # 5s ожидания при блокировке
    con.execute("PRAGMA temp_store = MEMORY;")
    con.execute("PRAGMA cache_size = -2000;")       # ~2MB page cache в памяти
    return con


def _table_has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    cur = con.execute(f"PRAGMA table_info({table});")
    return any(row["name"] == column for row in cur.fetchall())


def _ensure_schema(con: sqlite3.Connection) -> None:
    # Таблица продуктов
    con.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            last_price INTEGER,
            currency TEXT,
            last_check TEXT,
            next_check TEXT,
            check_interval_hours INTEGER,
            fail_count INTEGER
        );
    """)

    # Миграции на случай старой схемы
    if not _table_has_column(con, "products", "currency"):
        con.execute("ALTER TABLE products ADD COLUMN currency TEXT;")
    if not _table_has_column(con, "products", "last_check"):
        con.execute("ALTER TABLE products ADD COLUMN last_check TEXT;")
    if not _table_has_column(con, "products", "next_check"):
        con.execute("ALTER TABLE products ADD COLUMN next_check TEXT;")
    if not _table_has_column(con, "products", "check_interval_hours"):
        con.execute("ALTER TABLE products ADD COLUMN check_interval_hours INTEGER;")
    if not _table_has_column(con, "products", "fail_count"):
        con.execute("ALTER TABLE products ADD COLUMN fail_count INTEGER;")

    # Индексы
    con.execute("CREATE INDEX IF NOT EXISTS idx_products_next_check ON products(next_check);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_products_url ON products(url);")

    # История цен
    con.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            currency TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id, created_at);")


def init_db() -> None:
    """
    Инициализация схемы и одноразовый вывод статуса.
    """
    global _INIT_PRINTED
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _connect() as con:
        _ensure_schema(con)
    if not _INIT_PRINTED:
        print("База данных инициализирована.")
        _INIT_PRINTED = True


def _now_iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.utcnow()).isoformat(timespec="seconds")


def _calc_next_check_on_success(base_hours: Optional[int]) -> str:
    hours = base_hours if (isinstance(base_hours, int) and base_hours > 0) else DEFAULT_CHECK_INTERVAL_HOURS
    return _now_iso(datetime.utcnow() + timedelta(hours=hours))


def _calc_next_check_on_fail(fail_count: int) -> str:
    idx = min(max(fail_count - 1, 0), len(FAIL_BACKOFF_HOURS) - 1)
    hours = FAIL_BACKOFF_HOURS[idx]
    return _now_iso(datetime.utcnow() + timedelta(hours=hours))


def _get_product_by_url(con: sqlite3.Connection, url: str) -> Optional[sqlite3.Row]:
    cur = con.execute("SELECT * FROM products WHERE url = ?;", (url,))
    return cur.fetchone()


def _insert_product(con: sqlite3.Connection, url: str, title: Optional[str]) -> int:
    con.execute(
        "INSERT OR IGNORE INTO products (url, title, check_interval_hours, fail_count) VALUES (?, ?, ?, 0);",
        (url, title, DEFAULT_CHECK_INTERVAL_HOURS),
    )
    row = _get_product_by_url(con, url)
    return int(row["id"])


def upsert_product(url: str, title: Optional[str] = None) -> int:
    with _connect() as con:
        _ensure_schema(con)
        row = _get_product_by_url(con, url)
        if row is None:
            pid = _insert_product(con, url, title)
            return pid
        else:
            if title and (row["title"] or "") != title:
                con.execute("UPDATE products SET title = ? WHERE id = ?;", (title, row["id"]))
            return int(row["id"])


def save_price_snapshot(url: str, price: int, currency: str = "₽", title: Optional[str] = None) -> None:
    """
    Сохраняет снэпшот цены, обновляет last_price/last_check/next_check, сбрасывает fail_count.
    """
    with _connect() as con:
        _ensure_schema(con)

        row = _get_product_by_url(con, url)
        if row is None:
            _insert_product(con, url, title)
            row = _get_product_by_url(con, url)
        pid = int(row["id"])

        # История
        con.execute(
            "INSERT INTO price_history (product_id, price, currency) VALUES (?, ?, ?);",
            (pid, price, currency)
        )

        base = row["check_interval_hours"] if row and row["check_interval_hours"] else DEFAULT_CHECK_INTERVAL_HOURS
        con.execute("""
            UPDATE products
               SET title = COALESCE(?, title),
                   last_price = ?,
                   currency = ?,
                   last_check = ?,
                   next_check = ?,
                   fail_count = 0
             WHERE id = ?;
        """, (
            title,
            price,
            currency,
            _now_iso(),
            _calc_next_check_on_success(base),
            pid
        ))


def schedule_fail(url: str) -> None:
    """
    Фиксирует неудачу: инкрементирует fail_count и назначает next_check с бэкоффом.
    """
    with _connect() as con:
        _ensure_schema(con)
        row = _get_product_by_url(con, url)
        if row is None:
            _insert_product(con, url, None)
            row = _get_product_by_url(con, url)

        pid = int(row["id"])
        current_fail = int(row["fail_count"] or 0) + 1
        next_check = _calc_next_check_on_fail(current_fail)

        con.execute("""
            UPDATE products
               SET fail_count = ?,
                   last_check = ?,
                   next_check = ?
             WHERE id = ?;
        """, (current_fail, _now_iso(), next_check, pid))


def set_check_interval_hours(url: str, hours: int) -> None:
    """
    Позволяет вручную задать интервал проверки для конкретного URL.
    """
    if hours <= 0:
        raise ValueError("hours must be positive")
    with _connect() as con:
        _ensure_schema(con)
        row = _get_product_by_url(con, url)
        if row is None:
            _insert_product(con, url, None)
            row = _get_product_by_url(con, url)
        pid = int(row["id"])
        con.execute("UPDATE products SET check_interval_hours = ? WHERE id = ?;", (hours, pid))


def get_last_price_and_checked(url: str) -> Optional[Tuple[Optional[int], Optional[str]]]:
    """
    Для отладки: вернуть последнюю цену и время проверки.
    """
    with _connect() as con:
        row = _get_product_by_url(con, url)
        if row is None:
            return None
        return (row["last_price"], row["last_check"])


def get_products_for_monitoring(limit: Optional[int] = None) -> List[str]:
    """
    Возвращает URL, которые нужно мониторить сейчас:
    - next_check IS NULL (ещё не проверяли) ИЛИ
    - next_check <= now.
    """
    with _connect() as con:
        _ensure_schema(con)
        sql = """
            SELECT url
              FROM products
             WHERE next_check IS NULL
                OR next_check <= datetime('now')
             ORDER BY next_check ASC
        """
        if isinstance(limit, int) and limit > 0:
            sql += f" LIMIT {int(limit)}"
        cur = con.execute(sql)
        return [row["url"] for row in cur.fetchall()]


# ===== Хелперы для истории цен (удобно для отладки/экспорта) =====

def get_price_history(url: str, limit: Optional[int] = None) -> List[Tuple[str, int, Optional[str]]]:
    """
    Возвращает историю (created_at, price, currency) по URL (новые сверху).
    """
    with _connect() as con:
        row = _get_product_by_url(con, url)
        if row is None:
            return []
        pid = int(row["id"])
        sql = "SELECT created_at, price, currency FROM price_history WHERE product_id = ? ORDER BY created_at DESC"
        if isinstance(limit, int) and limit > 0:
            sql += f" LIMIT {int(limit)}"
        cur = con.execute(sql, (pid,))
        return [(r["created_at"], int(r["price"]), r["currency"]) for r in cur.fetchall()]


def export_price_history_csv(urls: Iterable[str], outfile: str = "price_history.csv") -> str:
    """
    Экспортирует историю цен по списку URL в CSV: url,created_at,price,currency
    Возвращает путь к файлу.
    """
    import csv
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "created_at", "price", "currency"])
        for u in urls:
            for created_at, price, currency in get_price_history(u):
                writer.writerow([u, created_at, price, currency or ""])
    return outfile
