"""
Internship Tracker - SQLite Database Layer
Handles job storage, history tracking, and incremental diff.
"""

import sqlite3, hashlib, json
from datetime import datetime
from pathlib import Path
from internship_tracker.core.config import DB_PATH


class JobDatabase:
    """SQLite database for storing and comparing job listings."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_hash TEXT UNIQUE NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT,
                    sub_category TEXT,
                    location TEXT,
                    department TEXT,
                    job_type TEXT,
                    publish_time TEXT,
                    jd TEXT,
                    url TEXT,
                    first_seen TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
                CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(job_hash);
                CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);

                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_time TEXT NOT NULL,
                    companies TEXT,
                    total_found INTEGER DEFAULT 0,
                    new_jobs INTEGER DEFAULT 0,
                    updated_jobs INTEGER DEFAULT 0,
                    duration_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            # Auto-migrate: add publish_time if missing
            cols = [row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
            if "publish_time" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN publish_time TEXT")

    @staticmethod
    def compute_hash(company, title, location):
        key = f"{company}_{title}_{location}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def upsert_jobs(self, jobs):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_count, updated_count = 0, 0
        current_hashes = set()

        with self._connect() as conn:
            for job in jobs:
                job_hash = self.compute_hash(
                    job.get("company",""), job.get("title",""), job.get("location",""))
                current_hashes.add(job_hash)

                existing = conn.execute(
                    "SELECT id FROM jobs WHERE job_hash = ?", (job_hash,)).fetchone()

                if existing:
                    conn.execute("""
                        UPDATE jobs SET category=?, sub_category=?, department=?,
                        job_type=?, publish_time=?, jd=?, url=?,
                        last_updated=?, is_active=1
                        WHERE job_hash=?
                    """, (job.get("category",""), job.get("sub_category",""),
                          job.get("department",""), job.get("type",""),
                          job.get("publish_time",""), job.get("jd",""),
                          job.get("url",""), now, job_hash))
                    updated_count += 1
                else:
                    conn.execute("""
                        INSERT INTO jobs
                        (job_hash, company, title, category, sub_category,
                         location, department, job_type, publish_time, jd, url,
                         first_seen, last_updated, is_active)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                    """, (job_hash, job.get("company",""), job.get("title",""),
                          job.get("category",""), job.get("sub_category",""),
                          job.get("location",""), job.get("department",""),
                          job.get("type",""), job.get("publish_time",""),
                          job.get("jd",""), job.get("url",""), now, now))
                    new_count += 1

        return new_count, updated_count, current_hashes

    def mark_inactive(self, active_hashes, companies=None):
        hashes_list = list(active_hashes)
        if not hashes_list: return
        with self._connect() as conn:
            ph = ",".join("?" * len(hashes_list))
            if companies:
                cp = ",".join("?" * len(companies))
                conn.execute(f"UPDATE jobs SET is_active=0 WHERE job_hash NOT IN ({ph}) AND company IN ({cp})",
                             hashes_list + list(companies))
            else:
                conn.execute(f"UPDATE jobs SET is_active=0 WHERE job_hash NOT IN ({ph})", hashes_list)

    def get_new_jobs_since(self, since_time):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM jobs WHERE first_seen > ? ORDER BY company, category, title",
                (since_time,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_active_jobs(self):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM jobs WHERE is_active=1 ORDER BY company, category, title"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_jobs_by_company(self, company):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM jobs WHERE company=? AND is_active=1 ORDER BY category, title",
                (company,)).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self):
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
            companies = conn.execute("SELECT COUNT(DISTINCT company) FROM jobs").fetchone()[0]
            last_run = conn.execute("SELECT run_time FROM crawl_runs ORDER BY id DESC LIMIT 1").fetchone()
            return {"total_jobs": total, "active_jobs": active, "companies": companies,
                    "last_run": last_run[0] if last_run else "从未运行"}

    def record_run(self, companies, total_found, new_jobs, updated_jobs, duration):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO crawl_runs (run_time, companies, total_found, new_jobs, updated_jobs, duration_seconds)
                VALUES (?,?,?,?,?,?)
            """, (now, ",".join(companies), total_found, new_jobs, updated_jobs, duration))
        return now

    def get_run_history(self, limit=10):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_new_jobs_from_last_run(self):
        with self._connect() as conn:
            last_run = conn.execute(
                "SELECT run_time FROM crawl_runs ORDER BY id DESC LIMIT 1 OFFSET 1").fetchone()
            if not last_run:
                return self.get_all_active_jobs()
            return self.get_new_jobs_since(last_run[0])

    def export_all(self):
        jobs = self.get_all_active_jobs()
        return [{
            "company": j["company"], "title": j["title"],
            "category": j["category"] or "", "sub_category": j["sub_category"] or "",
            "location": j["location"] or "", "department": j["department"] or "",
            "type": j["job_type"] or "", "publish_time": j["publish_time"] or "",
            "first_seen": j["first_seen"], "last_updated": j["last_updated"],
            "jd": j["jd"] or "", "url": j["url"] or "",
        } for j in jobs]

    def get_setting(self, key, default=None):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                         (key, str(value)))
