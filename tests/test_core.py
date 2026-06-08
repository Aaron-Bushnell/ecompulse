"""Unit tests for core modules (no network needed)."""
import sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from internship_tracker.core.crawler import BaseCrawler
from internship_tracker.core.database import JobDatabase
from internship_tracker.core.config import COMPANIES, BUSINESS_KEYWORDS, TECH_KEYWORDS


class TestFilter:
    def test_business_pass(self):
        assert BaseCrawler.is_business_job("产品经理实习生", "") is True
        assert BaseCrawler.is_business_job("内容运营", "运营") is True
        assert BaseCrawler.is_business_job("品牌营销实习生", "市场") is True
        assert BaseCrawler.is_business_job("HR实习生", "") is True
        assert BaseCrawler.is_business_job("视觉设计实习生", "") is True

    def test_tech_excluded(self):
        assert BaseCrawler.is_business_job("前端开发实习生", "技术") is False
        assert BaseCrawler.is_business_job("算法工程师", "") is False
        assert BaseCrawler.is_business_job("后端开发实习生", "技术") is False
        assert BaseCrawler.is_business_job("Android开发", "") is False

    def test_normalize_job(self):
        j = BaseCrawler.normalize_job(
            "美团", "产品实习生", "产品", "", "北京", "到店", "日常实习",
            "岗位职责...", "https://example.com", "2026-06-01")
        assert j["company"] == "美团"
        assert j["type"] == "日常实习"
        assert j["location"] == "北京"

    def test_join_value(self):
        assert BaseCrawler.join_value(["北京", "上海"]) == "北京, 上海"
        assert BaseCrawler.join_value({"name": "字节"}) == "字节"
        assert BaseCrawler.join_value("北京") == "北京"


class TestDatabase:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db = JobDatabase(db_path=Path(self.tmp) / "test.db")

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hash_deterministic(self):
        h1 = JobDatabase.compute_hash("美团", "产品实习生", "北京")
        h2 = JobDatabase.compute_hash("美团", "产品实习生", "北京")
        assert h1 == h2 and len(h1) == 32

    def test_hash_different(self):
        assert JobDatabase.compute_hash("美团", "产品", "北京") != \
               JobDatabase.compute_hash("美团", "运营", "北京")

    def test_upsert_and_query(self):
        jobs = [{"company": "美团", "title": "产品", "location": "北京",
                 "category": "产品", "type": "实习", "jd": "", "url": ""},
                {"company": "腾讯", "title": "运营", "location": "深圳",
                 "category": "运营", "type": "实习", "jd": "", "url": ""}]
        new, upd, _ = self.db.upsert_jobs(jobs)
        assert new == 2 and upd == 0
        assert len(self.db.get_all_active_jobs()) == 2
        assert len(self.db.get_jobs_by_company("美团")) == 1

    def test_upsert_update(self):
        jobs = [{"company": "美团", "title": "产品", "location": "北京",
                 "category": "产品", "type": "实习", "jd": "v1", "url": ""}]
        self.db.upsert_jobs(jobs)
        jobs[0]["category"] = "产品类"
        new, upd, _ = self.db.upsert_jobs(jobs)
        assert new == 0 and upd == 1

    def test_stats(self):
        self.db.upsert_jobs([{"company": "美团", "title": "产品", "location": "北京",
                              "category": "", "type": "", "jd": "", "url": ""}])
        s = self.db.get_stats()
        assert s["active_jobs"] == 1 and s["companies"] == 1

    def test_record_run(self):
        t = self.db.record_run(["美团"], 10, 5, 5, 30.5)
        assert t is not None
        assert len(self.db.get_run_history()) == 1

    def test_settings(self):
        self.db.set_setting("k", "v")
        assert self.db.get_setting("k") == "v"
        assert self.db.get_setting("nx", "d") == "d"


class TestConfig:
    def test_companies(self):
        assert len(COMPANIES) == 10
        assert COMPANIES["meituan"]["name"] == "美团"

    def test_keywords(self):
        assert "产品" in BUSINESS_KEYWORDS
        assert "运营" in BUSINESS_KEYWORDS
        assert "前端开发" in TECH_KEYWORDS
        assert "算法工程师" in TECH_KEYWORDS
