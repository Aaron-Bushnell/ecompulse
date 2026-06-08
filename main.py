#!/usr/bin/env python3
"""
实习岗位采集器 — Internship Tracker (Entry Point)

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
    """Headless one-shot crawl."""
    from internship_tracker.core.crawler import crawl_all
    from internship_tracker.core.database import JobDatabase
    from internship_tracker.core.exporter import export_to_excel, export_to_csv

    db = JobDatabase()
    companies = list(db.get_stats().keys())  # default: all enabled via crawl_all

    import time
    start = time.time()
    print("Starting crawl...")
    jobs = crawl_all(log_func=print)
    elapsed = time.time() - start

    new_cnt, upd_cnt, hashes = db.upsert_jobs(jobs)
    db.record_run([], len(jobs), new_cnt, upd_cnt, elapsed)

    print(f"\nDone: {len(jobs)} jobs (new={new_cnt}, updated={upd_cnt}) in {elapsed:.1f}s")

    all_jobs = db.export_all()
    xp = export_to_excel(all_jobs, hashes)
    cp = export_to_csv(all_jobs)
    print(f"Excel: {xp}")
    print(f"CSV:   {cp}")


def _cmd_export():
    """Export existing DB data without crawling."""
    from internship_tracker.core.database import JobDatabase
    from internship_tracker.core.exporter import export_to_excel, export_to_csv

    db = JobDatabase()
    jobs = db.export_all()
    if not jobs:
        print("No data in database.")
        return
    xp = export_to_excel(jobs, set())
    cp = export_to_csv(jobs)
    print(f"Excel: {xp}")
    print(f"CSV:   {cp}")


def main():
    parser = argparse.ArgumentParser(description="实习岗位采集器")
    parser.add_argument("--crawl", action="store_true", help="Headless one-shot crawl")
    parser.add_argument("--export", action="store_true", help="Export existing data to Excel+CSV")
    args = parser.parse_args()

    if args.crawl:
        _cmd_crawl()
    elif args.export:
        _cmd_export()
    else:
        from internship_tracker.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
