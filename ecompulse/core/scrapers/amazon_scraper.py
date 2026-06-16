"""
Competitor Tracker - Amazon Scraper
Uses Playwright to scrape real Amazon product pages by ASIN.
"""

import re
import time

from ecompulse.core.scrapers.base import BaseScraper


class AmazonScraper(BaseScraper):
    """Amazon platform scraper using Playwright browser automation."""

    # ASINs to scrape (well-known, stable products)
    TARGET_ASINS = [
        "B08N5WRWNW",  # Apple AirTag 4 Pack
        "B09G9D7K6T",  # Kindle Paperwhite
        "B0C6V714YP",  # Echo Dot 5th Gen
    ]

    BASE_URL = "https://www.amazon.com"
    PAGE_TIMEOUT = 30_000    # 30s for page load
    IDLE_WAIT = 3_000        # 3s for dynamic content to render

    # ------------------------------------------------------------------
    # Public crawl entry point
    # ------------------------------------------------------------------

    def crawl(self, log_func=print):
        """
        Scrape Amazon product pages via Playwright.

        Returns:
            List[dict] of normalized products (1 per ASIN).
        """
        log_func(f"  [Amazon] Playwright scraping {len(self.TARGET_ASINS)} ASINs...")

        try:
            raw_items = self._scrape_with_playwright(log_func)
        except Exception as e:
            log_func(f"  [Amazon] Playwright error: {e} — falling back to mock")
            raw_items = []

        # Fall back to mock data if Playwright returned nothing (blocked / CAPTCHA)
        if not raw_items:
            log_func("  [Amazon] Playwright returned 0 products — using mock data")
            raw_items = self._mock_data()

        # --- Map to uniform product model ---
        results = []
        for item in raw_items:
            title = item.get("title", "")
            price = item.get("price")

            if not self.is_target_product(title, price):
                continue
            if self.min_price is not None and (price or 0) < self.min_price:
                continue
            if self.max_price is not None and (price or 0) > self.max_price:
                continue

            results.append(self.normalize_product(
                platform="amazon",
                product_title=title,
                category=item.get("category", ""),
                shop_name=item.get("brand", ""),
                location="",
                stock_status=item.get("stock_status", "in_stock"),
                current_price=price,
                original_price=item.get("original_price"),
                currency="USD",
                sales_volume=item.get("bsr_rank", 0),
                review_count=item.get("review_count", 0),
                rating=item.get("rating"),
                sku_id=item.get("asin", ""),
                listing_date="",
                product_url=item.get("url", ""),
                image_url=item.get("image_url", ""),
            ))

        log_func(f"  [Amazon] 采集完成，发现 {len(results)} 件商品")
        return results

    # ------------------------------------------------------------------
    # Playwright scraping
    # ------------------------------------------------------------------

    @classmethod
    def _scrape_with_playwright(cls, log_func):
        """Launch Playwright, scrape each ASIN, return list of raw item dicts."""
        from playwright.sync_api import sync_playwright
        from ecompulse.core.config import (
            PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS,
        )

        # Build proxy config for Playwright
        proxy_settings = None
        if PROXY_HOST and PROXY_PORT:
            proxy_settings = {"server": f"http://{PROXY_HOST}:{PROXY_PORT}"}
            if PROXY_USER and PROXY_PASS:
                proxy_settings["username"] = PROXY_USER
                proxy_settings["password"] = PROXY_PASS
            log_func(f"  [Amazon] Using proxy: {PROXY_HOST}:{PROXY_PORT}")
        else:
            log_func("  [Amazon] No proxy configured — direct connection")

        items = []
        with sync_playwright() as p:
            # Anti-detection: stealth args + playwright-stealth
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-setuid-sandbox",
                ],
            )

            context_kwargs = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
            }
            if proxy_settings:
                context_kwargs["proxy"] = proxy_settings

            context = browser.new_context(**context_kwargs)

            # Apply playwright-stealth to evade bot detection
            try:
                from playwright_stealth import Stealth
                _stealth = Stealth()
            except ImportError:
                _stealth = None

            page = context.new_page()
            if _stealth:
                _stealth.apply_stealth_sync(page)
                log_func("  [Amazon] Stealth mode enabled")

            for idx, asin in enumerate(cls.TARGET_ASINS):
                url = f"{cls.BASE_URL}/dp/{asin}"
                log_func(f"  [Amazon] [{idx+1}/{len(cls.TARGET_ASINS)}] Loading {url} ...")

                try:
                    page.goto(url, wait_until="domcontentloaded",
                              timeout=cls.PAGE_TIMEOUT)
                    page.wait_for_timeout(cls.IDLE_WAIT)

                    # Bypass Amazon "Click to continue" verification
                    cls._bypass_verification(page, log_func)

                    item = cls._extract_product(page, asin)
                    if item:
                        items.append(item)
                        log_func(
                            f"  [Amazon]   {item.get('title','')[:50]}... "
                            f"price=${item.get('price')}  "
                            f"BSR=#{item.get('bsr_rank','N/A')}"
                        )
                    else:
                        log_func(f"  [Amazon]   Could not extract data (possible CAPTCHA)")
                except Exception as e:
                    log_func(f"  [Amazon]   Page error: {str(e)[:80]}")

                # Brief pause between requests
                if idx < len(cls.TARGET_ASINS) - 1:
                    time.sleep(1.5)

            browser.close()

        if not items:
            log_func("  [Amazon] No products extracted — Amazon may have blocked the request")
        return items

    # ------------------------------------------------------------------
    # Verification bypass
    # ------------------------------------------------------------------

    @staticmethod
    def _bypass_verification(page, log_func):
        """
        Detect and click through Amazon's 'Click to continue' bot-check page.
        """
        # Quick check: is this the verification page?
        body_text = page.locator("body").inner_text()
        if "continue shopping" not in body_text.lower():
            return  # Not a verification page, proceed normally

        log_func("  [Amazon]   Verification page detected, attempting bypass...")

        # Try multiple approaches to click the button
        click_selectors = [
            "input[type='submit']",
            "button[type='submit']",
            "form#a input[type='submit']",
        ]
        clicked = False
        for sel in click_selectors:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(force=True)
                    clicked = True
                    break
            except Exception:
                continue

        # Fallback: click by text content
        if not clicked:
            try:
                page.locator("text=Continue shopping").first.click(timeout=3000)
                clicked = True
            except Exception:
                pass

        if clicked:
            page.wait_for_timeout(8000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            log_func(f"  [Amazon]   Post-verification title: {page.title()[:80]}")
        else:
            log_func("  [Amazon]   Could not click verification button")

    # ------------------------------------------------------------------
    # Page extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_product(page, asin):
        """Extract product data from a loaded Amazon product page."""
        # Quick CAPTCHA check
        if page.locator("form[action*='captcha']").count() > 0:
            return None
        title_el = page.locator("#productTitle")
        if title_el.count() == 0:
            return None

        # ── Title ──
        title = title_el.first.inner_text().strip()

        # ── Price ──
        current_price = None
        original_price = None
        # Try the standard price widget first
        price_whole = page.locator("span.a-price span.a-price-whole").first
        price_fraction = page.locator("span.a-price span.a-price-fraction").first
        if price_whole.count() > 0:
            try:
                whole = price_whole.inner_text().replace(",", "").strip()
                frac = price_fraction.inner_text().strip() if price_fraction.count() > 0 else "00"
                current_price = float(f"{whole}.{frac}")
            except (ValueError, AttributeError):
                pass
        # Fallback: look for aria-hidden price spans
        if current_price is None:
            offscreen = page.locator("span.a-price span.a-offscreen").first
            if offscreen.count() > 0:
                match = re.search(r"[\d,.]+", offscreen.inner_text())
                if match:
                    try:
                        current_price = float(match.group().replace(",", ""))
                    except ValueError:
                        pass
        # List price (original)
        list_price_el = page.locator("span.a-text-price span.a-offscreen").first
        if list_price_el.count() > 0:
            match = re.search(r"[\d,.]+", list_price_el.inner_text())
            if match:
                try:
                    original_price = float(match.group().replace(",", ""))
                except ValueError:
                    pass

        # ── Best Seller Rank ──
        bsr_rank = 0
        bsr_text = page.locator(
            "#detailBullets_feature_div, "
            "#productDetails_detailBullets_sections1, "
            "#productDetails_techSpec_section_1"
        ).first
        if bsr_text.count() > 0:
            text = bsr_text.inner_text()
            # Pattern: "#1,234 in Electronics" or "Best Sellers Rank: #567"
            m = re.search(r"#([\d,]+)\s+in\s+", text)
            if not m:
                m = re.search(r"Best Sellers Rank[:\s]*#([\d,]+)", text)
            if m:
                try:
                    bsr_rank = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # ── Rating ──
        rating = None
        rating_el = page.locator("#acrPopover span.a-icon-alt").first
        if rating_el.count() == 0:
            rating_el = page.locator("span.a-icon-alt").first
        if rating_el.count() > 0:
            m = re.search(r"([\d.]+)\s*out", rating_el.inner_text())
            if m:
                rating = float(m.group(1))

        # ── Review Count ──
        review_count = 0
        reviews_el = page.locator("#acrCustomerReviewText").first
        if reviews_el.count() > 0:
            m = re.search(r"([\d,]+)", reviews_el.inner_text())
            if m:
                review_count = int(m.group(1).replace(",", ""))

        # ── Brand ──
        brand = ""
        brand_el = page.locator("a#bylineInfo").first
        if brand_el.count() > 0:
            brand = brand_el.inner_text().strip()
            brand = re.sub(r"^Visit the\s+", "", brand)
            brand = re.sub(r"\s+Store$", "", brand).strip()

        # ── Category (breadcrumb) ──
        category = ""
        breadcrumb = page.locator("#wayfinding-breadcrumbs_feature_div li a")
        if breadcrumb.count() >= 2:
            cats = [breadcrumb.nth(i).inner_text().strip()
                    for i in range(min(3, breadcrumb.count()))
                    if breadcrumb.nth(i).inner_text().strip()]
            category = " > ".join(cats) if cats else ""

        # ── Image ──
        image_url = ""
        img_el = page.locator("#landingImage").first
        if img_el.count() > 0:
            image_url = img_el.get_attribute("src") or ""

        # ── Stock status ──
        availability = page.locator("#availability span").first
        stock_status = "in_stock"
        if availability.count() > 0:
            avail_text = availability.inner_text().lower()
            if "out of stock" in avail_text or "unavailable" in avail_text:
                stock_status = "out_of_stock"
            elif "only" in avail_text and "left" in avail_text:
                stock_status = "low_stock"

        return {
            "asin": asin,
            "title": title,
            "price": current_price,
            "original_price": original_price or current_price,
            "bsr_rank": bsr_rank,
            "rating": rating,
            "review_count": review_count,
            "brand": brand,
            "category": category,
            "stock_status": stock_status,
            "url": f"{AmazonScraper.BASE_URL}/dp/{asin}",
            "image_url": image_url,
        }

    # ------------------------------------------------------------------
    # Fallback mock data
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_data():
        """Hardcoded mock data — fallback when Amazon blocks scraping."""
        time.sleep(0.1)
        return [
            {
                "asin": "B08N5WRWNW",
                "title": "Apple AirTag 4 Pack",
                "price": 79.99,
                "original_price": 99.00,
                "bsr_rank": 1,
                "rating": 4.8,
                "review_count": 52000,
                "brand": "Apple",
                "category": "Electronics > GPS & Navigation",
                "stock_status": "in_stock",
                "url": "https://www.amazon.com/dp/B08N5WRWNW",
                "image_url": "",
            },
            {
                "asin": "B09G9D7K6T",
                "title": "Kindle Paperwhite (16 GB)",
                "price": 149.99,
                "original_price": 149.99,
                "bsr_rank": 23,
                "rating": 4.7,
                "review_count": 18000,
                "brand": "Amazon",
                "category": "Electronics > eReaders",
                "stock_status": "in_stock",
                "url": "https://www.amazon.com/dp/B09G9D7K6T",
                "image_url": "",
            },
            {
                "asin": "B0C6V714YP",
                "title": "Echo Dot (5th Gen, 2022 release)",
                "price": 49.99,
                "original_price": 49.99,
                "bsr_rank": 5,
                "rating": 4.6,
                "review_count": 32000,
                "brand": "Amazon",
                "category": "Electronics > Smart Speakers",
                "stock_status": "in_stock",
                "url": "https://www.amazon.com/dp/B0C6V714YP",
                "image_url": "",
            },
        ]
