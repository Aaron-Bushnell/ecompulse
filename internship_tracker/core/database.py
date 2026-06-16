"""
Competitor Tracker - SQLite Database Layer
Handles product storage, price history tracking, and incremental diff.
"""

import sqlite3
import hashlib
from datetime import datetime

from internship_tracker.core.config import DB_PATH


class ProductDatabase:
    """SQLite database for storing and comparing competitor products."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ==================================================================
    # Schema Initialization
    # ==================================================================

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_hash    TEXT UNIQUE NOT NULL,
                    platform        TEXT NOT NULL,
                    product_title   TEXT NOT NULL,
                    current_price   REAL,
                    original_price  REAL,
                    currency        TEXT DEFAULT 'USD',
                    sales_volume    INTEGER DEFAULT 0,
                    review_count    INTEGER DEFAULT 0,
                    rating          REAL,
                    sku_id          TEXT NOT NULL,
                    category        TEXT,
                    shop_name       TEXT,
                    location        TEXT,
                    stock_status    TEXT DEFAULT 'in_stock',
                    listing_date    TEXT,
                    product_url     TEXT,
                    image_url       TEXT,
                    first_seen      TEXT NOT NULL,
                    last_updated    TEXT NOT NULL,
                    is_active       INTEGER DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_products_platform ON products(platform);
                CREATE INDEX IF NOT EXISTS idx_products_hash ON products(product_hash);
                CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku_id);
                CREATE INDEX IF NOT EXISTS idx_products_first_seen ON products(first_seen);
                CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock_status);

                CREATE TABLE IF NOT EXISTS price_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_hash    TEXT NOT NULL,
                    price           REAL NOT NULL,
                    currency        TEXT,
                    recorded_at     TEXT NOT NULL,
                    FOREIGN KEY (product_hash) REFERENCES products(product_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_price_history_hash
                    ON price_history(product_hash);
                CREATE INDEX IF NOT EXISTS idx_price_history_time
                    ON price_history(recorded_at);

                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_time          TEXT NOT NULL,
                    platforms         TEXT,
                    total_found       INTEGER DEFAULT 0,
                    new_products      INTEGER DEFAULT 0,
                    updated_products  INTEGER DEFAULT 0,
                    price_changes     INTEGER DEFAULT 0,
                    duration_seconds  REAL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

            # Auto-migrate: add price_changes column if missing from older schema
            cols = [row[1] for row in
                    conn.execute("PRAGMA table_info(crawl_runs)").fetchall()]
            if "price_changes" not in cols:
                conn.execute(
                    "ALTER TABLE crawl_runs ADD COLUMN price_changes INTEGER DEFAULT 0")

    # ==================================================================
    # Hashing
    # ==================================================================

    @staticmethod
    def compute_product_hash(platform, sku_id):
        """MD5 fingerprint: platform + SKU is the natural unique key."""
        key = f"{platform}_{sku_id}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    # ==================================================================
    # Core Upsert with Price-Change Detection (Section 3.2)
    # ==================================================================

    def upsert_products(self, products):
        """
        Insert or update products. Detects price changes and records history.

        For each product:
          - If product_hash is new: INSERT (new_count++)
          - If product_hash exists:
              * Always UPDATE all fields (updated_count++)
              * If current_price changed vs DB: INSERT into price_history
                with the OLD price, then price_changed_count++

        Args:
            products: List[dict] in normalize_product() format.

        Returns:
            (new_cnt, updated_cnt, price_changed_cnt, current_hashes)
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_count = 0
        updated_count = 0
        price_changed_count = 0
        current_hashes = set()

        with self._connect() as conn:
            for prod in products:
                product_hash = self.compute_product_hash(
                    prod.get("platform", ""),
                    prod.get("sku_id", ""),
                )
                current_hashes.add(product_hash)

                existing = conn.execute(
                    "SELECT id, current_price FROM products WHERE product_hash = ?",
                    (product_hash,)
                ).fetchone()

                if existing:
                    # --- EXISTING product: UPDATE all fields ---
                    old_price = existing[1]  # DB value before update
                    new_price = prod.get("current_price")

                    conn.execute("""
                        UPDATE products SET
                            product_title = ?, current_price = ?,
                            original_price = ?, currency = ?,
                            sales_volume = ?, review_count = ?, rating = ?,
                            category = ?, shop_name = ?, location = ?,
                            stock_status = ?, listing_date = ?,
                            product_url = ?, image_url = ?,
                            last_updated = ?, is_active = 1
                        WHERE product_hash = ?
                    """, (
                        prod.get("product_title", ""),
                        new_price,
                        prod.get("original_price"),
                        prod.get("currency", "USD"),
                        prod.get("sales_volume", 0),
                        prod.get("review_count", 0),
                        prod.get("rating"),
                        prod.get("category", ""),
                        prod.get("shop_name", ""),
                        prod.get("location", ""),
                        prod.get("stock_status", "in_stock"),
                        prod.get("listing_date", ""),
                        prod.get("product_url", ""),
                        prod.get("image_url", ""),
                        now,
                        product_hash,
                    ))
                    updated_count += 1

                    # --- Price change detection ---
                    # Only triggers when BOTH values are non-None and differ
                    if (old_price is not None and new_price is not None
                            and float(old_price) != float(new_price)):
                        conn.execute("""
                            INSERT INTO price_history
                                (product_hash, price, currency, recorded_at)
                            VALUES (?, ?, ?, ?)
                        """, (
                            product_hash,
                            old_price,  # record the OLD price as the history point
                            prod.get("currency", "USD"),
                            now,
                        ))
                        price_changed_count += 1

                else:
                    # --- NEW product: INSERT ---
                    conn.execute("""
                        INSERT INTO products (
                            product_hash, platform, product_title,
                            current_price, original_price, currency,
                            sales_volume, review_count, rating,
                            sku_id, category, shop_name, location,
                            stock_status, listing_date,
                            product_url, image_url,
                            first_seen, last_updated, is_active
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, 1
                        )
                    """, (
                        product_hash,
                        prod.get("platform", ""),
                        prod.get("product_title", ""),
                        prod.get("current_price"),
                        prod.get("original_price"),
                        prod.get("currency", "USD"),
                        prod.get("sales_volume", 0),
                        prod.get("review_count", 0),
                        prod.get("rating"),
                        prod.get("sku_id", ""),
                        prod.get("category", ""),
                        prod.get("shop_name", ""),
                        prod.get("location", ""),
                        prod.get("stock_status", "in_stock"),
                        prod.get("listing_date", ""),
                        prod.get("product_url", ""),
                        prod.get("image_url", ""),
                        now,
                        now,
                    ))
                    new_count += 1

        return new_count, updated_count, price_changed_count, current_hashes

    # ==================================================================
    # Mark Inactive (down-listing detection -- fully preserved)
    # ==================================================================

    def mark_inactive(self, active_hashes, platforms=None):
        """Mark products not in this crawl as is_active=0 (delisted)."""
        hashes_list = list(active_hashes)
        if not hashes_list:
            return
        with self._connect() as conn:
            ph = ",".join("?" * len(hashes_list))
            if platforms:
                pp = ",".join("?" * len(platforms))
                conn.execute(
                    f"UPDATE products SET is_active=0 "
                    f"WHERE product_hash NOT IN ({ph}) AND platform IN ({pp})",
                    hashes_list + list(platforms),
                )
            else:
                conn.execute(
                    f"UPDATE products SET is_active=0 "
                    f"WHERE product_hash NOT IN ({ph})",
                    hashes_list,
                )

    # ==================================================================
    # Run History
    # ==================================================================

    def record_run(self, platforms, total_found, new_products,
                   updated_products, price_changes, duration):
        """Record a crawl run including price_changes counter."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO crawl_runs
                    (run_time, platforms, total_found, new_products,
                     updated_products, price_changes, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, ",".join(platforms) if platforms else "",
                  total_found, new_products, updated_products,
                  price_changes, duration))
        return now

    def get_run_history(self, limit=10):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ==================================================================
    # Query Methods
    # ==================================================================

    def get_all_active_products(self):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM products WHERE is_active=1 "
                "ORDER BY platform, category, product_title"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_products_by_platform(self, platform):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM products WHERE platform=? AND is_active=1 "
                "ORDER BY category, product_title",
                (platform,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_new_products_since(self, since_time):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM products WHERE first_seen > ? "
                "ORDER BY platform, category, product_title",
                (since_time,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_price_history(self, product_hash, limit=30):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM price_history WHERE product_hash = ? "
                "ORDER BY recorded_at DESC LIMIT ?",
                (product_hash, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self):
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0]
            platforms = conn.execute(
                "SELECT COUNT(DISTINCT platform) FROM products").fetchone()[0]
            out_of_stock = conn.execute(
                "SELECT COUNT(*) FROM products "
                "WHERE is_active=1 AND stock_status='out_of_stock'").fetchone()[0]
            last_run = conn.execute(
                "SELECT run_time FROM crawl_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return {
                "total_products": total,
                "active_products": active,
                "platforms": platforms,
                "out_of_stock": out_of_stock,
                "last_run": last_run[0] if last_run else "Never",
            }

    def export_all(self):
        """Export all active products as flat dicts for Excel/CSV."""
        products = self.get_all_active_products()
        return [{
            "platform": p["platform"],
            "product_title": p["product_title"],
            "category": p["category"] or "",
            "shop_name": p["shop_name"] or "",
            "location": p["location"] or "",
            "stock_status": p["stock_status"] or "",
            "current_price": p["current_price"],
            "original_price": p["original_price"],
            "currency": p["currency"] or "USD",
            "sales_volume": p["sales_volume"] or 0,
            "review_count": p["review_count"] or 0,
            "rating": p["rating"],
            "sku_id": p["sku_id"] or "",
            "listing_date": p["listing_date"] or "",
            "product_url": p["product_url"] or "",
            "first_seen": p["first_seen"],
            "last_updated": p["last_updated"],
            "product_hash": p["product_hash"],
        } for p in products]

    # ==================================================================
    # Settings (unchanged from JobDatabase)
    # ==================================================================

    def get_setting(self, key, default=None):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )


# ==================================================================
# Backward-compatible alias
# (main.py/gui.py still import JobDatabase; will be migrated in later steps)
# ==================================================================
JobDatabase = ProductDatabase
