"""Unit tests for competitor tracker core modules (no network needed)."""
import sys
import tempfile
import shutil
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from internship_tracker.core.scrapers.base import BaseScraper
from internship_tracker.core.database import ProductDatabase
from internship_tracker.core.config import PLATFORMS


class TestBaseScraper:
    """Tests for BaseScraper filtering and normalization."""

    def test_is_target_product_ok(self):
        assert BaseScraper.is_target_product("Wireless Headphones", 99.99) is True
        assert BaseScraper.is_target_product("USB Cable", 12.49) is True

    def test_is_target_product_cheap(self):
        """Products below $1 should be excluded."""
        assert BaseScraper.is_target_product("Cheap Item", 0.50) is False

    def test_is_target_product_accessory(self):
        """Products with '配件' in title should be excluded."""
        assert BaseScraper.is_target_product("手机配件套装", 5.00) is False

    def test_is_target_product_no_price(self):
        """Products with no price should still pass (price unknown)."""
        assert BaseScraper.is_target_product("Some Product", None) is True

    def test_normalize_product(self):
        p = BaseScraper.normalize_product(
            platform="amazon",
            product_title="Test Headphones",
            category="Electronics",
            shop_name="TestShop",
            current_price=99.99,
            original_price=129.99,
            currency="USD",
            sales_volume=100,
            review_count=50,
            rating=4.5,
            sku_id="B0TEST001",
            listing_date="2025-11-15",
            product_url="https://amazon.com/dp/B0TEST001",
        )
        assert p["platform"] == "amazon"
        assert p["product_title"] == "Test Headphones"
        assert p["current_price"] == 99.99
        assert p["original_price"] == 129.99
        assert p["currency"] == "USD"
        assert p["sales_volume"] == 100
        assert p["review_count"] == 50
        assert p["rating"] == 4.5
        assert p["sku_id"] == "B0TEST001"
        assert p["listing_date"] == "2025-11-15"
        assert p["product_url"] == "https://amazon.com/dp/B0TEST001"
        assert p["stock_status"] == "in_stock"

    def test_join_value(self):
        assert BaseScraper.join_value(["北京", "上海"]) == "北京, 上海"
        assert BaseScraper.join_value({"name": "字节"}) == "字节"
        assert BaseScraper.join_value("北京") == "北京"


class TestProductDatabase:
    """Tests for ProductDatabase: schema, upsert, price change detection."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        self.db = ProductDatabase(db_path=self.db_path)

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_product(self, platform="amazon", sku="B0TEST001",
                      title="Test Product", price=99.99):
        return {
            "platform": platform,
            "sku_id": sku,
            "product_title": title,
            "current_price": price,
            "original_price": 129.99,
            "currency": "USD",
            "sales_volume": 100,
            "review_count": 50,
            "rating": 4.5,
            "category": "Electronics",
            "shop_name": "TestShop",
            "location": "",
            "stock_status": "in_stock",
            "listing_date": "2025-11-15",
            "product_url": f"https://amazon.com/dp/{sku}",
            "image_url": "",
        }

    # ---- Schema tests ----

    def test_product_database_init(self):
        """Verify products and price_history tables are created."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "products" in tables
        assert "price_history" in tables
        assert "crawl_runs" in tables
        assert "settings" in tables

    def test_hash_deterministic(self):
        h1 = ProductDatabase.compute_product_hash("amazon", "B0TEST001")
        h2 = ProductDatabase.compute_product_hash("amazon", "B0TEST001")
        assert h1 == h2
        assert len(h1) == 32

    def test_hash_different_platform(self):
        h1 = ProductDatabase.compute_product_hash("amazon", "B0TEST001")
        h2 = ProductDatabase.compute_product_hash("shopee", "B0TEST001")
        assert h1 != h2

    # ---- Upsert tests ----

    def test_upsert_new_product(self):
        """Insert a new product; verify new_count=1."""
        new, upd, pc, hashes = self.db.upsert_products(
            [self._make_product()])
        assert new == 1
        assert upd == 0
        assert pc == 0
        assert len(hashes) == 1
        assert len(self.db.get_all_active_products()) == 1

    def test_upsert_update_no_price_change(self):
        """Update same product with same price; upd=1, pc=0."""
        prod = self._make_product()
        self.db.upsert_products([prod])
        # Second upsert with same price
        new, upd, pc, _ = self.db.upsert_products([prod])
        assert new == 0
        assert upd == 1
        assert pc == 0  # price unchanged

    def test_price_change_detection(self):
        """Insert product, change price, verify pc=1 and price_history."""
        prod = self._make_product(price=99.99)
        self.db.upsert_products([prod])

        # Change price
        prod["current_price"] = 89.99
        new, upd, pc, _ = self.db.upsert_products([prod])

        assert new == 0
        assert upd == 1
        assert pc == 1  # price changed!

        # Verify price_history has 1 record with OLD price
        history = self.db.get_price_history(
            ProductDatabase.compute_product_hash("amazon", "B0TEST001"))
        assert len(history) == 1
        assert history[0]["price"] == 99.99  # old price recorded

        # Verify product now has new price
        products = self.db.get_all_active_products()
        assert products[0]["current_price"] == 89.99

    def test_mark_inactive(self):
        """Insert 2 products, mark 1 as inactive, verify only 1 active."""
        p1 = self._make_product(sku="SKU001")
        p2 = self._make_product(sku="SKU002")
        self.db.upsert_products([p1, p2])

        # Simulate: only SKU001 appears in next crawl
        h1 = ProductDatabase.compute_product_hash("amazon", "SKU001")
        self.db.mark_inactive({h1})

        active = self.db.get_all_active_products()
        assert len(active) == 1
        assert active[0]["sku_id"] == "SKU001"

    def test_record_run(self):
        t = self.db.record_run(["amazon"], 10, 5, 3, 2, 30.5)
        assert t is not None
        history = self.db.get_run_history()
        assert len(history) == 1
        assert history[0]["price_changes"] == 2

    def test_settings(self):
        self.db.set_setting("k", "v")
        assert self.db.get_setting("k") == "v"
        assert self.db.get_setting("nx", "d") == "d"

    def test_export_all(self):
        self.db.upsert_products([self._make_product()])
        exported = self.db.export_all()
        assert len(exported) == 1
        assert exported[0]["platform"] == "amazon"
        assert "product_hash" in exported[0]


class TestConfig:
    """Tests for platform configuration."""

    def test_platforms(self):
        assert len(PLATFORMS) == 4
        assert PLATFORMS["amazon"]["name"] == "Amazon"
        assert PLATFORMS["amazon"]["currency"] == "USD"
        assert PLATFORMS["shopee"]["currency"] == "TWD"

    def test_platform_enabled(self):
        for key in PLATFORMS:
            assert PLATFORMS[key].get("enabled") is True
