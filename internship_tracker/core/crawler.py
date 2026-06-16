"""
Competitor Tracker - Crawler Engine
Orchestrates platform-specific scrapers via the scraper registry.

Architecture:
  crawl_all() -> iterates enabled platforms -> get_scraper(key) -> scraper.crawl()
  Each scraper returns List[dict] in the uniform normalize_product() format.
"""

import sys
from pathlib import Path

from internship_tracker.core.config import PLATFORMS
from internship_tracker.core.scrapers import get_scraper


def _ensure_local_deps():
    """Add bundled .deps / .deps314 directories to sys.path for Playwright."""
    base = Path(__file__).resolve().parents[1]
    for name in (".deps", ".deps314"):
        d = base / name
        if d.exists() and str(d) not in sys.path:
            sys.path.insert(0, str(d))


def crawl_platform(platform_key, log_func=print, search_terms=None,
                   min_price=None, max_price=None, category=None):
    """
    Crawl a single platform by key.

    Args:
        platform_key: e.g. "amazon", "shopee"
        log_func: callback for progress messages
        search_terms: optional keywords for product search
        min_price: minimum price filter
        max_price: maximum price filter
        category: product category filter

    Returns:
        List[dict] of normalized products
    """
    try:
        scraper = get_scraper(platform_key)
    except (ValueError, NotImplementedError) as e:
        log_func(f"  [System] {e}")
        return []

    try:
        if hasattr(scraper, "set_options"):
            scraper.set_options(
                search_terms=search_terms,
                min_price=min_price,
                max_price=max_price,
                category=category,
            )
        return scraper.crawl(log_func=log_func)
    except Exception as e:
        log_func(f"  [System] Scraper error for {platform_key}: {e}")
        return []


def crawl_all(selected_platforms=None, log_func=print, search_terms=None,
              min_price=None, max_price=None, category=None):
    """
    Crawl all (or selected) enabled platforms.

    Args:
        selected_platforms: list of platform keys, or None for all enabled
        log_func: callback for progress messages
        search_terms: optional keywords
        min_price: minimum price filter
        max_price: maximum price filter
        category: product category filter

    Returns:
        List[dict] of all normalized products across platforms
    """
    if selected_platforms is None:
        selected_platforms = [
            k for k, v in PLATFORMS.items() if v.get("enabled", True)
        ]

    all_products = []
    for key in selected_platforms:
        if key not in PLATFORMS or not PLATFORMS[key].get("enabled", True):
            continue
        name = PLATFORMS[key]["name"]
        log_func(f"[{name}] Starting...")
        products = crawl_platform(
            key, log_func=log_func, search_terms=search_terms,
            min_price=min_price, max_price=max_price, category=category,
        )
        all_products.extend(products)
        log_func(f"[{name}] Done: {len(products)} products")

    return all_products
