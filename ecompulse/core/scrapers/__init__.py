"""
Competitor Tracker - Scraper Registry & Factory

Usage:
    from ecompulse.core.scrapers import get_scraper
    scraper = get_scraper("amazon")
    products = scraper.crawl(log_func=print)
"""

from ecompulse.core.config import PLATFORMS
from ecompulse.core.scrapers.amazon_scraper import AmazonScraper

# Lazy registry: platform_key -> factory lambda (imported at registration time)
_SCRAPER_REGISTRY = {
    "amazon":   lambda: AmazonScraper(),
    # "shopee":   lambda: ShopeeScraper(),       # TODO: step 4
}


def get_scraper(platform_key):
    """
    Factory: return a scraper instance for the given platform key.

    Args:
        platform_key: e.g. "amazon", "shopee", "lazada"

    Returns:
        A BaseScraper subclass instance.

    Raises:
        ValueError: if platform_key is unknown.
        NotImplementedError: if platform is configured but no scraper exists yet.
    """
    if platform_key not in PLATFORMS:
        raise ValueError(
            f"Unknown platform '{platform_key}'. "
            f"Available: {list(PLATFORMS.keys())}"
        )

    factory = _SCRAPER_REGISTRY.get(platform_key)
    if factory is None:
        raise NotImplementedError(
            f"Platform '{platform_key}' is configured but no scraper "
            f"has been implemented yet."
        )

    return factory()


def register_scraper(platform_key, factory):
    """Register a new scraper class/factory at runtime."""
    _SCRAPER_REGISTRY[platform_key] = factory
