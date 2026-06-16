"""
Internship Tracker - Configuration
Fixed settings for 10 major internet companies + job type filters.
"""

import os
import sys

# Base paths
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get("INTERNSHIP_TRACKER_DATA_DIR"):
    DATA_DIR = os.environ["INTERNSHIP_TRACKER_DATA_DIR"]
elif sys.platform == "win32":
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "实习岗位采集器")
else:
    DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "internship-tracker")

_DB_DIR = os.path.join(DATA_DIR, "data", "tracker_app")
os.makedirs(_DB_DIR, exist_ok=True)
DB_PATH = os.path.join(_DB_DIR, "jobs.db")

# ========== Company Registry ==========
COMPANIES = {
    "meituan":     {"name": "美团",     "crawler": "api_meituan",     "enabled": True},
    "tencent":     {"name": "腾讯",     "crawler": "api_tencent",     "enabled": True},
    "baidu":       {"name": "百度",     "crawler": "api_baidu",       "enabled": True},
    "bilibili":    {"name": "哔哩哔哩", "crawler": "browser_bilibili", "enabled": True},
    "xiaohongshu": {"name": "小红书",   "crawler": "api_xiaohongshu", "enabled": True},
    "kuaishou":    {"name": "快手",     "crawler": "api_kuaishou",    "enabled": True},
    "netease":     {"name": "网易",     "crawler": "api_netease",     "enabled": True},
    "alibaba":     {"name": "阿里巴巴", "crawler": "browser_alibaba",  "enabled": True},
    "bytedance":   {"name": "字节跳动", "crawler": "browser_bytedance","enabled": True},
    "pinduoduo":   {"name": "拼多多",   "crawler": "api_pinduoduo",   "enabled": True},
}

# ========== Job Type Filters ==========
BUSINESS_KEYWORDS = [
    "产品", "运营", "市场", "策划", "商务", "销售", "营销", "品牌", "公关",
    "职能", "人力", "HR", "财务", "行政", "法务", "采购", "供应链",
    "项目管理", "战略", "咨询", "商业分析", "数据分析", "用户研究",
    "内容", "社区", "活动", "增长", "渠道", "投放", "游戏策划",
    "设计", "交互", "视觉",
]

TECH_KEYWORDS = [
    "前端开发", "后端开发", "客户端开发", "Android", "iOS", "Java开发",
    "C++开发", "Python开发", "测试开发", "算法工程师", "机器学习",
    "深度学习", "运维工程师", "安全工程师", "大数据开发", "硬件",
    "嵌入式", "芯片", "射频", "驱动", "内核", "编译器", "FPGA",
]

# ========== API Endpoints ==========
API_ENDPOINTS = {
    "meituan": {
        "list": "https://zhaopin.meituan.com/api/official/job/getJobList",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://zhaopin.meituan.com/web/position",
            "Origin": "https://zhaopin.meituan.com",
        },
        "list_payload": {
            "page": {"pageNo": 1, "pageSize": 20},
            "jobShareType": "1", "keywords": "", "cityList": [], "department": [],
            "jfJgList": [], "jobType": [{"code": "4", "subCode": ["6"]}],
            "typeCode": ["6"], "specialCode": [],
        },
    },
    "tencent": {
        "list": "https://join.qq.com/api/v1/position/searchPosition",
        "detail": "https://join.qq.com/api/v1/jobDetails/getJobDetailsByPostId",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://join.qq.com/",
        },
        "business_fids": [2, 3, 4, 5, 6],
    },
    "baidu": {
        "list": "https://talent.baidu.com/httservice/getPostListNew",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://talent.baidu.com/",
        },
    },
    "bilibili": {
        "list": "https://jobs.bilibili.com/api/srs/position/positionList",
        "detail": "https://jobs.bilibili.com/api/srs/position/positionDetail",
        "campus_url": "https://jobs.bilibili.com/campus/positions",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json", "Content-Type": "application/json",
            "Referer": "https://jobs.bilibili.com/campus",
        },
    },
    "xiaohongshu": {
        "list": "https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json", "Content-Type": "application/json",
            "Referer": "https://job.xiaohongshu.com/campus",
        },
    },
    "kuaishou": {
        "list": "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json", "Content-Type": "application/json",
            "Referer": "https://campus.kuaishou.cn/#/campus/jobs?positionNatureCode=intern",
        },
    },
    "netease": {
        "list": "https://hr.163.com/api/hr163/position/queryPage",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json", "Content-Type": "application/json",
            "Referer": "https://hr.163.com/",
        },
    },
    "alibaba": {
        "page_url": "https://campus-talent.alibaba.com/campus/position?campusType=internship",
        "api_pattern": "position/search",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    },
    "bytedance": {
        "page_url": "https://jobs.bytedance.com/campus/position",
        "api_pattern": "search/job/posts",
        "business_categories": "6704215864629004552,6704215882479962371,6704215913488451847,6709824272505768200,6704215901438216462,6850051244971526414",
        "intern_subjects": "7624086888207862069,7621018569480046853,7194661644654577981,7194661126919358757",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    },
    "pinduoduo": {
        "list": "https://careers.pddglobalhr.com/api/careers/api/recruit/position/train/list",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json", "Content-Type": "application/json",
            "Referer": "https://careers.pddglobalhr.com/campus/intern",
        },
        "search_keywords": ["产品", "运营", "市场", "设计", "商务", "职能", "人力"],
    },
}

# ========== Platform Registry (E-Commerce) ==========
PLATFORMS = {
    "amazon":   {"name": "Amazon",     "scraper": "api",    "enabled": True, "currency": "USD"},
    "shopee":   {"name": "Shopee",     "scraper": "browser","enabled": True, "currency": "TWD"},
    "lazada":   {"name": "Lazada",     "scraper": "browser","enabled": True, "currency": "THB"},
    "temu":     {"name": "Temu",       "scraper": "browser","enabled": True, "currency": "USD"},
}

# Product category filters (placeholder -- replaces BUSINESS_KEYWORDS/TECH_KEYWORDS)
PRODUCT_CATEGORY_FILTERS = [
    "电子产品", "家居", "服装", "运动户外", "美妆", "玩具",
]

# Crawler defaults
DEFAULT_PAGE_SIZE = 10
DEFAULT_MAX_PAGES = 50
REQUEST_DELAY = 0.3
