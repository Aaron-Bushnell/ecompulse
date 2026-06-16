#!/usr/bin/env python3
"""
竞品监控 — Competitor Tracker (Entry Point)

Double-click to launch the tkinter GUI, or use command line for headless mode:
    python main.py                  # Launch GUI
    python main.py --crawl          # Headless one-shot crawl
    python main.py --export         # Export existing data to Excel + CSV, then exit
"""

import argparse, sys
from pathlib import Path

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _cmd_crawl():
    """Headless one-shot crawl for competitor products."""
    from ecompulse.core.crawler import crawl_all
    from ecompulse.core.database import ProductDatabase
    from ecompulse.core.exporter import export_to_excel, export_to_csv

    db = ProductDatabase()

    import time
    start = time.time()
    print("Starting crawl...")
    products = crawl_all(log_func=print)
    elapsed = time.time() - start

    new_cnt, upd_cnt, price_chg, hashes = db.upsert_products(products)
    db.mark_inactive(hashes)
    db.record_run([], len(products), new_cnt, upd_cnt, price_chg, elapsed)

    print(f"\nDone: {len(products)} products "
          f"(new={new_cnt}, updated={upd_cnt}, price_changed={price_chg}) "
          f"in {elapsed:.1f}s")

    # Build price_changes dict for export
    price_changes = _build_price_changes(db, hashes)

    all_products = db.export_all()
    xp = export_to_excel(all_products, new_hashes=set(), price_changes=price_changes)
    cp = export_to_csv(all_products)
    print(f"Excel: {xp}")
    print(f"CSV:   {cp}")


def _cmd_export():
    """Export existing DB data without crawling."""
    from ecompulse.core.database import ProductDatabase
    from ecompulse.core.exporter import export_to_excel, export_to_csv

    db = ProductDatabase()
    products = db.export_all()
    if not products:
        print("No data in database.")
        return
    xp = export_to_excel(products, new_hashes=set(), price_changes={})
    cp = export_to_csv(products)
    print(f"Excel: {xp}")
    print(f"CSV:   {cp}")


def _build_price_changes(db, hashes):
    """Build {product_hash: (old_price, new_price)} from recent price_history."""
    price_changes = {}
    for h in hashes:
        history = db.get_price_history(h, limit=1)
        if history:
            old_price = history[0]["price"]
            # Get current price from DB
            products = db.export_all()
            for p in products:
                if p.get("product_hash") == h:
                    new_price = p.get("current_price")
                    if new_price is not None and old_price is not None:
                        price_changes[h] = (old_price, new_price)
                    break
    return price_changes


def main():
    parser = argparse.ArgumentParser(description="竞品监控 — Competitor Tracker")
    parser.add_argument("--crawl", action="store_true",
                        help="采集竞品数据")
    parser.add_argument("--export", action="store_true",
                        help="导出已有数据到 Excel + CSV")
    args = parser.parse_args()

    if args.crawl:
        _cmd_crawl()
    elif args.export:
        _cmd_export()
    else:
        from ecompulse.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
