"""
Internship Tracker - Crawler Engine
Supports both direct API calls and browser-based crawling.

Crawlers for 10 companies:
  美团/腾讯/百度/网易/小红书/快手/拼多多 → API
  哔哩哔哩 → Browser intercepts API (needs CSRF cookie)
  阿里巴巴/字节跳动 → Browser intercepts signed API
"""

import requests, json, time, re, sys
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime

from internship_tracker.core.config import (
    API_ENDPOINTS, BUSINESS_KEYWORDS, TECH_KEYWORDS,
    DEFAULT_PAGE_SIZE, DEFAULT_MAX_PAGES, REQUEST_DELAY,
    COMPANIES,
)


class BaseCrawler:
    """Shared utilities for all crawlers."""

    def set_options(self, search_terms=None, city=""):
        terms, seen = [], set()
        for t in (search_terms or []):
            c = str(t).strip()
            if c and c not in seen:
                terms.append(c); seen.add(c)
        self.search_terms = terms
        self.city_filter = str(city or "").strip()
        return self

    @property
    def search_keyword(self):
        return " ".join(getattr(self, "search_terms", []))

    @staticmethod
    def is_business_job(title, category=""):
        text = f"{title}_{category}"
        is_biz = any(kw in text for kw in BUSINESS_KEYWORDS)
        is_tech = any(kw in text for kw in TECH_KEYWORDS)
        if is_tech and not is_biz:
            return False
        return is_biz

    @staticmethod
    def normalize_job(company, title, category, sub_category,
                      location, department, job_type, jd, url, publish_time=""):
        return {
            "company": company, "title": title, "category": category,
            "sub_category": sub_category, "location": location,
            "department": department, "type": job_type,
            "publish_time": BaseCrawler._fmt_time(publish_time),
            "jd": jd, "url": url,
        }

    @staticmethod
    def join_value(value):
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v)
        if isinstance(value, dict):
            return value.get("i18n") or value.get("zh_cn") or value.get("name") or ""
        return str(value or "")

    @staticmethod
    def _fmt_time(value):
        if value in (None, ""):
            return ""
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        t = str(value).strip()
        if t.isdigit():
            return BaseCrawler._fmt_time(int(t))
        return t[:16]


def _ensure_local_deps():
    base = Path(__file__).resolve().parents[1]
    for name in (".deps", ".deps314"):
        d = base / name
        if d.exists() and str(d) not in sys.path:
            sys.path.insert(0, str(d))


# ======================================================================
# API-based crawlers
# ======================================================================

class MeituanCrawler(BaseCrawler):
    """美团 — Direct API."""

    def crawl(self, log_func=print):
        company = "美团"
        cfg = API_ENDPOINTS["meituan"]
        all_raw, results = [], []

        for page in range(1, DEFAULT_MAX_PAGES + 1):
            payload = dict(cfg["list_payload"])
            payload["page"] = {"pageNo": page, "pageSize": 20}
            if self.search_keyword:
                payload["keywords"] = self.search_keyword
            try:
                r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
                jobs = r.json().get("data", {}).get("list", [])
                if not jobs: break
                all_raw.extend(jobs)
                log_func(f"  [{company}] Page {page}: +{len(jobs)} jobs")
                if len(jobs) < 20: break
                time.sleep(REQUEST_DELAY)
            except Exception as e:
                log_func(f"  [{company}] Page {page} error: {e}")
                break

        log_func(f"  [{company}] Total raw: {len(all_raw)}")
        filtered = [j for j in all_raw if self.is_business_job(j.get("name", ""), j.get("jobFamily", ""))]
        log_func(f"  [{company}] Business jobs: {len(filtered)}")

        for job in filtered:
            try:
                cities = ", ".join(c.get("name","") for c in job.get("cityList", []))
                depts = ", ".join(d.get("name","") for d in job.get("department", []))
                jd_parts = []
                for label, key in [("【岗位职责】","jobDuty"), ("【岗位要求】","jobRequirement"), ("【岗位亮点】","highLight")]:
                    if job.get(key): jd_parts.append(f"{label}\n{job[key]}")
                results.append(self.normalize_job(
                    company=company, title=job.get("name",""),
                    category=job.get("jobFamily",""), sub_category=job.get("jobFamilyGroup",""),
                    location=cities, department=depts, job_type="日常实习",
                    jd="\n\n".join(jd_parts),
                    url=f"https://zhaopin.meituan.com/web/position/detail?jobUnionId={job.get('jobUnionId','')}",
                    publish_time=job.get("firstPostTime") or job.get("refreshTime"),
                ))
            except Exception as e:
                log_func(f"  [{company}] Parse error: {e}")
        return results


class TencentCrawler(BaseCrawler):
    """腾讯 — Direct API. FIXED: expanded business_fids from [3,5,6] to [2,3,4,5,6]."""

    def crawl(self, log_func=print):
        company = "腾讯"
        cfg = API_ENDPOINTS["tencent"]
        results = []
        # FIXED: [3,5,6] → [2,3,4,5,6] covering 设计/产品/项目/市场/职能
        business_fids = cfg.get("business_fids", [3, 5, 6])
        fast_search = bool(getattr(self, "search_terms", []))
        seen_post_ids = set()

        log_func(f"  [{company}] Categories: {business_fids}")
        for fid in business_fids:
            for page in range(1, DEFAULT_MAX_PAGES + 1):
                payload = {
                    "pageSize": 20, "pageIndex": page,
                    "categoryId": str(fid),
                    "projectMappingIdList": [2, 104],
                }
                if self.search_keyword:
                    payload["keyword"] = self.search_keyword
                try:
                    r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
                    data = r.json().get("data", {})
                    posts = data.get("list") or data.get("positionList") or []
                    if not posts: break

                    for p in posts:
                        title = p.get("name") or p.get("positionTitle", "")
                        if not self.is_business_job(title): continue
                        post_id = p.get("postId") or f"{title}_{p.get('workCities','')}"
                        if post_id in seen_post_ids: continue
                        seen_post_ids.add(post_id)

                        jd_text = p.get("description", "")
                        if not fast_search and not jd_text and p.get("postId"):
                            try:
                                dr = requests.get(cfg["detail"],
                                    params={"postId": p["postId"]}, headers=cfg["headers"], timeout=15)
                                jd_text = dr.json().get("data", {}).get("description", "")
                                time.sleep(0.1)
                            except Exception: pass

                        results.append(self.normalize_job(
                            company=company, title=title,
                            category=p.get("categoryName","") or str(p.get("positionFamily","")),
                            sub_category="",
                            location=p.get("workCityName","") or p.get("workCities",""),
                            department=p.get("bgName","") or p.get("bgs",""),
                            job_type=p.get("projectMappingName","") or p.get("projectName","") or p.get("recruitLabelName","实习"),
                            jd=jd_text,
                            url=f"https://join.qq.com/post_detail.html?pid={p.get('postId','')}",
                            publish_time=p.get("publishTime") or p.get("updateTime") or p.get("lastUpdateTime"),
                        ))

                    log_func(f"  [{company}] FID {fid} Page {page}: +{len(posts)}")
                    if len(posts) < 20: break
                    time.sleep(REQUEST_DELAY)
                except Exception as e:
                    log_func(f"  [{company}] FID {fid} Page {page} error: {e}")
                    break

        log_func(f"  [{company}] Total: {len(results)}")
        return results


class BaiduCrawler(BaseCrawler):
    """百度 — Direct API."""

    def crawl(self, log_func=print):
        company = "百度"
        cfg = API_ENDPOINTS["baidu"]
        results = []

        for page in range(1, DEFAULT_MAX_PAGES + 1):
            payload = {"recruitType": "INTERN", "pageSize": 20, "curPage": page,
                       "keyWord": "", "workLocation": "", "postType": "", "projectId": ""}
            if self.search_keyword: payload["keyWord"] = self.search_keyword
            try:
                r = requests.post(cfg["list"], data=payload, headers=cfg["headers"], timeout=15)
                data = r.json()
                if data.get("status") not in ("success", "ok"):
                    log_func(f"  [{company}] API status: {data.get('status')}")
                    break
                jobs = data.get("data", {}).get("list", [])
                if not jobs: break

                for j in jobs:
                    title = j.get("name", "")
                    if not self.is_business_job(title, j.get("postType", "")): continue
                    jd_parts = []
                    if j.get("workContent"): jd_parts.append(f"【岗位职责】\n{j['workContent']}")
                    if j.get("serviceCondition"): jd_parts.append(f"【岗位要求】\n{j['serviceCondition']}")
                    jd = "\n\n".join(jd_parts) or j.get("description","") or j.get("serviceCondition","")
                    results.append(self.normalize_job(
                        company=company, title=title,
                        category=j.get("postType",""), sub_category=j.get("secondPostType",""),
                        location=j.get("workPlace",""),
                        department=j.get("orgName","") or j.get("bgShortName",""),
                        job_type=j.get("projectType","") or "实习", jd=jd,
                        url=f"https://talent.baidu.com/jobs/detail?jobId={j.get('postId','')}",
                        publish_time=j.get("publishDate") or j.get("updateDate"),
                    ))
                log_func(f"  [{company}] Page {page}: +{len(jobs)}")
                if len(jobs) < 20: break
                time.sleep(REQUEST_DELAY)
            except Exception as e:
                log_func(f"  [{company}] Page {page} error: {e}")
                break

        log_func(f"  [{company}] Total: {len(results)}")
        return results


class NeteaseCrawler(BaseCrawler):
    """网易 — Direct API."""

    def crawl(self, log_func=print):
        company = "网易"
        cfg = API_ENDPOINTS["netease"]
        results = []

        for page in range(1, DEFAULT_MAX_PAGES + 1):
            payload = {"pageNum": page, "pageSize": 20, "recruitType": "intern",
                       "keyWord": "", "workCity": ""}
            try:
                r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
                jobs = r.json().get("data", {}).get("list", [])
                if not jobs: break
                for j in jobs:
                    title = j.get("name", "")
                    cat = j.get("firstPostTypeName", "")
                    if not self.is_business_job(title, cat): continue
                    jd_parts = []
                    if j.get("description"): jd_parts.append(f"【岗位职责】\n{j['description']}")
                    if j.get("requirement"): jd_parts.append(f"【岗位要求】\n{j['requirement']}")
                    results.append(self.normalize_job(
                        company=company, title=title, category=cat, sub_category="",
                        location=", ".join(j.get("workPlaceNameList", [])),
                        department=j.get("firstDepName", ""), job_type="实习",
                        jd="\n\n".join(jd_parts),
                        url=j.get("beeUrl") or "https://hr.163.com/",
                        publish_time=j.get("publishTime") or j.get("updateTime"),
                    ))
                log_func(f"  [{company}] Page {page}: +{len(jobs)}")
                if len(jobs) < 20: break
                time.sleep(REQUEST_DELAY)
            except Exception as e:
                log_func(f"  [{company}] Page {page} error: {e}")
                break

        log_func(f"  [{company}] Total: {len(results)}")
        return results


class BilibiliBrowserCrawler(BaseCrawler):
    """哔哩哔哩 — Browser API interception (needs session cookie from browser)."""

    def crawl(self, log_func=print):
        company = "哔哩哔哩"
        cfg = API_ENDPOINTS["bilibili"]
        results = []

        try:
            _ensure_local_deps()
            from playwright.sync_api import sync_playwright
        except Exception as e:
            log_func(f"  [{company}] Playwright unavailable: {e}")
            return results

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                payloads = []

                def on_response(resp):
                    if "position/positionList" not in resp.url: return
                    try:
                        items = resp.json().get("data", {}).get("list", [])
                        if items: payloads.append(items)
                    except Exception: pass

                page.on("response", on_response)
                page.goto(cfg["campus_url"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)
                payloads.clear()
                page.evaluate("""
                    () => {
                        const el = [...document.querySelectorAll('a')]
                            .find(e => (e.innerText || '').includes('实习'));
                        if (el) el.click();
                    }
                """)
                page.wait_for_timeout(3500)
                for page_no in range(2, min(DEFAULT_MAX_PAGES, 8) + 1):
                    clicked = page.evaluate("""
                        (target) => {
                            const el = [...document.querySelectorAll('li.ant-pagination-item,a')]
                                .find(e => (e.innerText || '').trim() === String(target));
                            if (el) { el.click(); return true; }
                            return false;
                        }
                    """, str(page_no))
                    if not clicked: break
                    page.wait_for_timeout(1800)
                browser.close()

            all_jobs = []
            for page_items in payloads:
                all_jobs.extend(page_items)
            log_func(f"  [{company}] Browser API pages: +{len(all_jobs)}")
            for j in all_jobs:
                title = j.get("positionName", "")
                cat = j.get("postCodeName", "")
                if not self.is_business_job(title, cat): continue
                results.append(self.normalize_job(
                    company=company, title=title, category=cat, sub_category="",
                    location=j.get("workLocation", ""), department="",
                    job_type=j.get("positionTypeName", "实习"),
                    jd=j.get("positionDescription", ""),
                    url=f"https://jobs.bilibili.com/campus/positions/{j.get('id','')}",
                    publish_time=j.get("pushTime"),
                ))
        except Exception as e:
            log_func(f"  [{company}] Browser error: {e}")

        log_func(f"  [{company}] Total: {len(results)}")
        return results


class XiaohongshuCrawler(BaseCrawler):
    """小红书 — Direct API."""

    def crawl(self, log_func=print):
        company = "小红书"
        cfg = API_ENDPOINTS["xiaohongshu"]
        results = []

        for page in range(1, DEFAULT_MAX_PAGES + 1):
            payload = {"pageNum": page, "pageSize": 20, "recruitType": "intern",
                       "keyword": "", "workCityList": []}
            if self.search_keyword: payload["keyword"] = self.search_keyword
            try:
                r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
                jobs = r.json().get("data", {}).get("list", [])
                if not jobs: break
                for j in jobs:
                    title = j.get("positionName") or j.get("name", "")
                    if not self.is_business_job(title): continue
                    jd_parts = []
                    if j.get("duty"): jd_parts.append(f"【岗位职责】\n{j['duty']}")
                    if j.get("requirement"): jd_parts.append(f"【岗位要求】\n{j['requirement']}")
                    results.append(self.normalize_job(
                        company=company, title=title,
                        category=j.get("positionTypeName","") or j.get("typeName",""),
                        sub_category="",
                        location=j.get("workplace","") or j.get("workPlace",""),
                        department=j.get("departmentName","") or j.get("depName",""),
                        job_type="实习",
                        jd="\n\n".join(jd_parts) or j.get("description",""),
                        url=f"https://job.xiaohongshu.com/position/{j.get('positionId') or j.get('id','')}",
                        publish_time=j.get("publishTime"),
                    ))
                log_func(f"  [{company}] Page {page}: +{len(jobs)}")
                if len(jobs) < 20: break
                time.sleep(REQUEST_DELAY)
            except Exception as e:
                log_func(f"  [{company}] Page {page} error: {e}")
                break

        log_func(f"  [{company}] Total: {len(results)}")
        return results


class KuaishouApiCrawler(BaseCrawler):
    """快手 — Direct API."""

    def crawl(self, log_func=print):
        company = "快手"
        cfg = API_ENDPOINTS["kuaishou"]
        results = []
        seen_codes = set()

        keywords = getattr(self, "search_terms", []) or [""]
        for kw in keywords:
            for page in range(1, DEFAULT_MAX_PAGES + 1):
                payload = {"pageNo": page, "pageSize": 20, "positionNatureCode": "intern"}
                if kw: payload["name"] = kw
                try:
                    r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
                    jobs = r.json().get("result", {}).get("list", [])
                    if not jobs: break

                    for j in jobs:
                        title = j.get("name", "")
                        cat = j.get("positionCategoryName", "")
                        if not self.is_business_job(title, cat): continue
                        code = j.get("code") or f"{title}_{j.get('workLocationName','')}"
                        if code in seen_codes: continue
                        seen_codes.add(code)

                        jd_parts = []
                        if j.get("description"): jd_parts.append(f"【岗位职责】\n{j['description']}")
                        if j.get("requirement"): jd_parts.append(f"【岗位要求】\n{j['requirement']}")
                        results.append(self.normalize_job(
                            company=company, title=title, category=cat, sub_category="",
                            location=j.get("workLocationName",""),
                            department=j.get("departmentName",""), job_type="实习",
                            jd="\n\n".join(jd_parts),
                            url=f"https://campus.kuaishou.cn/#/campus/job-info/{code}?positionNatureCode=intern",
                            publish_time=j.get("releaseTime") or j.get("updateTime"),
                        ))

                    prefix = f" Keyword '{kw}'" if kw else ""
                    log_func(f"  [{company}]{prefix} Page {page}: +{len(jobs)}")
                    if len(jobs) < 20: break
                    time.sleep(REQUEST_DELAY)
                except Exception as e:
                    log_func(f"  [{company}] Page {page} error: {e}")
                    break

        log_func(f"  [{company}] Total: {len(results)}")
        return results


class PinduoduoCrawler(BaseCrawler):
    """拼多多 — Direct API with keyword search.

    FIXED: The PDD intern API returns mostly technical roles. We now probe
    multiple business keywords to find non-tech positions. If nothing matches,
    we return an empty list (no more dumping raw tech jobs as before).
    """

    def crawl(self, log_func=print):
        company = "拼多多"
        cfg = API_ENDPOINTS["pinduoduo"]
        results = []
        seen_ids = set()
        raw_fallback = []

        search_kws = self.search_terms if self.search_terms else cfg.get("search_keywords", [])
        all_keywords = search_kws if search_kws else [""]

        for kw in all_keywords:
            for page in range(1, DEFAULT_MAX_PAGES + 1):
                payload = {"page": page, "pageSize": 20}
                if kw: payload["name"] = kw
                try:
                    r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
                    jobs = r.json().get("result", {}).get("list", [])
                    if not jobs: break

                    for j in jobs:
                        title = j.get("name", "")
                        cat = j.get("jobName", "")
                        jid = j.get("id") or f"{title}_{j.get('workLocationName','')}"
                        if jid in seen_ids: continue
                        seen_ids.add(jid)

                        jd_parts = []
                        if j.get("jobDuty"): jd_parts.append(f"【岗位职责】\n{j['jobDuty']}")
                        if j.get("jobRequirement"): jd_parts.append(f"【岗位要求】\n{j['jobRequirement']}")
                        normalized = self.normalize_job(
                            company=company, title=title, category=cat, sub_category="",
                            location=j.get("workLocationName","") or j.get("workLocation",""),
                            department="", job_type="实习",
                            jd="\n\n".join(jd_parts),
                            url=f"https://careers.pddglobalhr.com/campus/intern/{j.get('id','')}",
                            publish_time=j.get("releaseTime"),
                        )
                        if self.is_business_job(title, cat):
                            results.append(normalized)
                        else:
                            raw_fallback.append(normalized)

                    prefix = f" Keyword '{kw}'" if kw else ""
                    log_func(f"  [{company}]{prefix} Page {page}: +{len(jobs)}")
                    if len(jobs) < 20: break
                    time.sleep(REQUEST_DELAY)
                except Exception as e:
                    log_func(f"  [{company}] Page {page} error: {e}")
                    break

        # FIXED: no more dumping raw tech jobs. Log clearly if nothing matched.
        if not results and raw_fallback:
            log_func(f"  [{company}] No business-role match from {len(raw_fallback)} listings. "
                     f"PDD may have few non-technical intern positions.")
        log_func(f"  [{company}] Total: {len(results)}")
        return results


class BrowserNetworkCrawler(BaseCrawler):
    """Browser API interception for Alibaba & ByteDance (signed requests).

    FIXED: Alibaba now supports multiple possible API response shapes
    (content.datas, data.list, data.records, result) and automatic
    pagination via clicking next-page buttons.
    """

    BYTE_BUSINESS_CATEGORIES = ",".join([
        "6704215864629004552", "6704215882479962371",
        "6704215913488451847", "6709824272505768200",
        "6704215901438216462", "6850051244971526414",
    ])
    BYTE_INTERN_SUBJECTS = ",".join([
        "7624086888207862069", "7621018569480046853",
        "7194661644654577981", "7194661126919358757",
    ])

    def __init__(self, company_key):
        self.company_key = company_key
        self.company_info = COMPANIES.get(company_key, {})

    def crawl(self, log_func=print):
        company = self.company_info.get("name", self.company_key)
        cfg = API_ENDPOINTS.get(self.company_key, {})

        urls = {
            "alibaba": cfg.get("page_url", "https://campus-talent.alibaba.com/campus/position?campusType=internship"),
            "bytedance": "https://jobs.bytedance.com/campus/position?" + urlencode({
                "keywords": self.search_keyword,
                "category": self.BYTE_BUSINESS_CATEGORIES,
                "location": "", "project": self.BYTE_INTERN_SUBJECTS,
                "type": "", "job_hot_flag": "",
                "current": "1", "limit": "10",
                "functionCategory": "", "tag": "",
            }),
        }
        url = urls.get(self.company_key)
        if not url: return []

        try:
            _ensure_local_deps()
            from playwright.sync_api import sync_playwright
        except Exception as e:
            log_func(f"  [{company}] Playwright unavailable: {e}")
            return []

        results, all_payloads = [], []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={"width": 1920, "height": 1080},
                )

                api_pattern = cfg.get("api_pattern", "position/search" if self.company_key == "alibaba" else "search/job/posts")

                def on_response(resp):
                    if api_pattern not in resp.url: return
                    try:
                        all_payloads.append(resp.json())
                    except Exception: pass

                page.on("response", on_response)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(7000)

                # FIXED: try pagination for Alibaba (click next page buttons)
                if self.company_key == "alibaba":
                    for _ in range(5):
                        try:
                            clicked = page.evaluate("""
                                () => {
                                    const next = document.querySelector(
                                        '[class*="next"], .ant-pagination-next, button[aria-label*="下一页"]'
                                    );
                                    if (next && !next.disabled && !next.classList.contains('ant-pagination-disabled')) {
                                        next.click(); return true;
                                    }
                                    return false;
                                }
                            """)
                            if not clicked: break
                            page.wait_for_timeout(3000)
                        except Exception:
                            break

                browser.close()
        except Exception as e:
            log_func(f"  [{company}] Browser error: {e}")
            return results

        # Parse according to company
        if self.company_key == "alibaba":
            results = self._parse_alibaba(all_payloads, log_func)
        elif self.company_key == "bytedance":
            results = self._parse_bytedance(all_payloads, log_func)

        log_func(f"  [{company}] Total: {len(results)}")
        return results

    def _parse_alibaba(self, payloads, log_func):
        company = self.company_info.get("name", "阿里巴巴")
        results, seen_ids = [], set()

        raw_jobs = []
        for payload in payloads:
            # FIXED: support multiple possible response shapes
            for path in [
                lambda p: p.get("content", {}).get("datas", []),
                lambda p: p.get("data", {}).get("list", []),
                lambda p: p.get("data", {}).get("records", []),
                lambda p: p.get("data", []),
                lambda p: p.get("result", []),
            ]:
                items = path(payload)
                if items:
                    if isinstance(items, list):
                        for item in items:
                            item_id = item.get("id") or item.get("trackId") or item.get("name")
                            if item_id not in seen_ids:
                                seen_ids.add(item_id)
                                raw_jobs.append(item)
                    elif isinstance(items, dict):
                        for item in items.values():
                            if isinstance(item, dict):
                                item_id = item.get("id") or item.get("name")
                                if item_id not in seen_ids:
                                    seen_ids.add(item_id)
                                    raw_jobs.append(item)
                    break

        log_func(f"  [{company}] Raw API items: {len(raw_jobs)}")
        for j in raw_jobs:
            title = j.get("name", "")
            cat = self.join_value(j.get("categoryNames") or j.get("categories"))
            if not self.is_business_job(title, cat): continue
            jd = "\n\n".join(x for x in [j.get("description",""), j.get("requirement","")] if x)
            results.append(self.normalize_job(
                company=company, title=title, category=cat, sub_category="",
                location=self.join_value(j.get("workLocations")),
                department=self.join_value(j.get("departments") or j.get("buNames")),
                job_type="实习", jd=jd,
                url=f"https://campus-talent.alibaba.com/campus/position/{j.get('id','')}",
                publish_time=j.get("publishTime") or j.get("modifyTime"),
            ))
        return results

    def _parse_bytedance(self, payloads, log_func):
        company = self.company_info.get("name", "字节跳动")
        results = []

        raw_jobs = []
        for payload in payloads:
            raw_jobs.extend(payload.get("data", {}).get("job_post_list", []))

        log_func(f"  [{company}] Raw API items: {len(raw_jobs)}")
        for j in raw_jobs:
            title = j.get("title", "")
            cat = self.join_value(j.get("job_category") or j.get("job_category_name"))
            if not self.is_business_job(title, cat): continue
            location = self.join_value(j.get("city_info") or j.get("city_info_list") or j.get("location"))
            subject = self.join_value(j.get("subject") or j.get("recruitment"))
            jd = "\n\n".join(x for x in [j.get("description",""), j.get("requirement","")] if x)
            results.append(self.normalize_job(
                company=company, title=title, category=cat, sub_category=subject,
                location=location, department=self.join_value(j.get("department")),
                job_type="实习", jd=jd,
                url=f"https://jobs.bytedance.com/campus/position/{j.get('id','')}",
                publish_time=j.get("publish_time") or j.get("update_time"),
            ))
        return results


# ========== Crawler Registry ==========
CRAWLERS = {
    "meituan": MeituanCrawler,
    "tencent": TencentCrawler,
    "baidu": BaiduCrawler,
    "netease": NeteaseCrawler,
    "bilibili": BilibiliBrowserCrawler,
    "xiaohongshu": XiaohongshuCrawler,
    "kuaishou": KuaishouApiCrawler,
    "alibaba": lambda: BrowserNetworkCrawler("alibaba"),
    "bytedance": lambda: BrowserNetworkCrawler("bytedance"),
    "pinduoduo": PinduoduoCrawler,
}


def crawl_company(company_key, log_func=print, search_terms=None, city=""):
    """Crawl a single company by key."""
    crawler_cls = CRAWLERS.get(company_key)
    if not crawler_cls:
        log_func(f"  [System] No crawler for {company_key}")
        return []
    try:
        crawler = crawler_cls()
        if hasattr(crawler, "set_options"):
            crawler.set_options(search_terms=search_terms, city=city)
        return crawler.crawl(log_func=log_func)
    except Exception as e:
        log_func(f"  [System] Crawler error for {company_key}: {e}")
        return []


def crawl_all(selected_companies=None, log_func=print, search_terms=None, city=""):
    """Crawl all or selected companies."""
    if selected_companies is None:
        selected_companies = [k for k, v in COMPANIES.items() if v.get("enabled", True)]

    all_jobs = []
    for key in selected_companies:
        if key not in COMPANIES or not COMPANIES[key].get("enabled", True):
            continue
        name = COMPANIES[key]["name"]
        log_func(f"[{name}] Starting...")
        jobs = crawl_company(key, log_func=log_func, search_terms=search_terms, city=city)
        all_jobs.extend(jobs)
        log_func(f"[{name}] Done: {len(jobs)} jobs")

    return all_jobs
