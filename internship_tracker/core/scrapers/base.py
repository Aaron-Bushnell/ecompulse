"""
Competitor Tracker - Base Scraper
Shared utilities for all platform scrapers.
"""

from datetime import datetime


class BaseScraper:
    """Shared utilities for all e-commerce platform scrapers."""

    def set_options(self, search_terms=None, min_price=None, max_price=None,
                    category=None, currency="USD"):
        """Configure scraper filters before crawling."""
        terms, seen = [], set()
        for t in (search_terms or []):
            c = str(t).strip()
            if c and c not in seen:
                terms.append(c)
                seen.add(c)
        self.search_terms = terms
        self.min_price = min_price
        self.max_price = max_price
        self.category_filter = category
        self.currency_filter = currency
        return self

    @property
    def search_keyword(self):
        return " ".join(getattr(self, "search_terms", []))

    @staticmethod
    def is_target_product(title, price=None):
        """
        Filter products for competitor monitoring.

        Excludes:
          - Products with price below $1 (likely accessories/bundles/errors)
          - Products whose title contains '配件' (accessories placeholder)
        """
        # Exclude dirt-cheap items
        if price is not None:
            try:
                if float(price) < 1.0:
                    return False
            except (ValueError, TypeError):
                pass

        # Exclude accessories
        if "配件" in (title or ""):
            return False

        return True

    @staticmethod
    def normalize_product(platform, product_title, category="",
                          shop_name="", location="", stock_status="in_stock",
                          current_price=None, original_price=None,
                          currency="USD", sales_volume=0, review_count=0,
                          rating=None, sku_id="", listing_date="",
                          product_url="", image_url=""):
        """Map raw scraped fields to uniform product dict."""
        return {
            "platform": platform,
            "product_title": product_title,
            "category": category,
            "shop_name": shop_name,
            "location": location,
            "stock_status": stock_status,
            "current_price": current_price,
            "original_price": original_price,
            "currency": currency,
            "sales_volume": sales_volume,
            "review_count": review_count,
            "rating": rating,
            "sku_id": sku_id,
            "listing_date": BaseScraper._fmt_time(listing_date),
            "product_url": product_url,
            "image_url": image_url,
        }

    @staticmethod
    def join_value(value):
        """Flatten list/dict/string values to a comma-joined string."""
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v)
        if isinstance(value, dict):
            return value.get("i18n") or value.get("zh_cn") or value.get("name") or ""
        return str(value or "")

    @staticmethod
    def _fmt_time(value):
        """Normalize timestamps to YYYY-MM-DD format."""
        if value in (None, ""):
            return ""
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        t = str(value).strip()
        if t.isdigit():
            return BaseScraper._fmt_time(int(t))
        return t[:16]
