"""
Competitor Tracker - Amazon Mock Scraper
Placeholder implementation returning simulated product data.
"""

import time

from internship_tracker.core.scrapers.base import BaseScraper


class AmazonScraper(BaseScraper):
    """Amazon platform scraper (mock — no real HTTP requests yet)."""

    def crawl(self, log_func=print):
        """
        Return 3 simulated products for development/testing.

        Args:
            log_func: callback for progress messages.

        Returns:
            List[dict] of normalized products.
        """
        log_func("  [Amazon] Starting mock crawl (no network)...")

        # Build 3 mock products covering different stock/price scenarios
        mock_raw = [
            {
                "sku_id": "B0TEST001",
                "product_title": "Test Wireless Headphones",
                "current_price": 99.99,
                "original_price": 129.99,
                "currency": "USD",
                "sales_volume": 1520,
                "review_count": 89,
                "rating": 4.5,
                "stock_status": "in_stock",
                "listing_date": "2025-11-15",
                "product_url": "https://www.amazon.com/dp/B0TEST001",
                "category": "Electronics",
                "shop_name": "AudioPro Official",
                "image_url": "",
            },
            {
                "sku_id": "B0TEST002",
                "product_title": "Test USB-C Charging Cable (2-Pack)",
                "current_price": 12.49,
                "original_price": 15.99,
                "currency": "USD",
                "sales_volume": 8520,
                "review_count": 1203,
                "rating": 4.2,
                "stock_status": "in_stock",
                "listing_date": "2025-08-03",
                "product_url": "https://www.amazon.com/dp/B0TEST002",
                "category": "Electronics",
                "shop_name": "CableDirect",
                "image_url": "",
            },
            {
                "sku_id": "B0TEST003",
                "product_title": "Test Bluetooth Speaker Portable",
                "current_price": 34.50,
                "original_price": 34.50,
                "currency": "USD",
                "sales_volume": 320,
                "review_count": 47,
                "rating": 4.0,
                "stock_status": "low_stock",
                "listing_date": "2026-03-01",
                "product_url": "https://www.amazon.com/dp/B0TEST003",
                "category": "Electronics",
                "shop_name": "SoundWave",
                "image_url": "",
            },
        ]

        results = []
        for item in mock_raw:
            # Apply the is_target_product filter (respects min_price/max_price)
            if not self.is_target_product(item["product_title"], item["current_price"]):
                continue

            if self.min_price is not None and item["current_price"] < self.min_price:
                continue
            if self.max_price is not None and item["current_price"] > self.max_price:
                continue

            results.append(self.normalize_product(
                platform="amazon",
                product_title=item["product_title"],
                category=item["category"],
                shop_name=item["shop_name"],
                location="",
                stock_status=item["stock_status"],
                current_price=item["current_price"],
                original_price=item["original_price"],
                currency=item["currency"],
                sales_volume=item["sales_volume"],
                review_count=item["review_count"],
                rating=item["rating"],
                sku_id=item["sku_id"],
                listing_date=item["listing_date"],
                product_url=item["product_url"],
                image_url=item["image_url"],
            ))

        time.sleep(0.2)  # simulate brief network delay
        log_func(f"  [Amazon] 模拟采集完成，发现 {len(results)} 件商品")
        return results
