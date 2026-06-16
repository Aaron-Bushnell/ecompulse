# 贡献指南

## 添加新公司爬虫

### 1. 注册公司（config.py）

在 `COMPANIES` dict 中添加：

```python
COMPANIES = {
    # ...
    "newco": {"name": "新公司", "crawler": "api_newco", "enabled": True},
}
```

### 2. 添加 API 端点（config.py）

```python
API_ENDPOINTS = {
    # ...
    "newco": {
        "list": "https://careers.newco.com/api/positions",
        "headers": {
            "User-Agent": "Mozilla/5.0 ...",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    },
}
```

### 3. 实现爬虫类（crawler.py）

继承 `BaseCrawler`，实现 `crawl(self, log_func=print)` 方法，返回 list of dict：

```python
class NewCoCrawler(BaseCrawler):
    def crawl(self, log_func=print):
        company = "新公司"
        cfg = API_ENDPOINTS["newco"]
        results = []

        for page in range(1, DEFAULT_MAX_PAGES + 1):
            payload = {"page": page, "size": 20}
            r = requests.post(cfg["list"], json=payload, headers=cfg["headers"], timeout=15)
            jobs = r.json().get("data", {}).get("list", [])
            if not jobs: break

            for j in jobs:
                title = j.get("title", "")
                if not self.is_business_job(title): continue
                results.append(self.normalize_job(
                    company=company, title=title,
                    category=j.get("category", ""), sub_category="",
                    location=j.get("location", ""), department="",
                    job_type="实习", jd=j.get("description", ""),
                    url=f"https://careers.newco.com/jobs/{j['id']}",
                    publish_time=j.get("publishTime"),
                ))
            time.sleep(REQUEST_DELAY)

        log_func(f"  [{company}] Total: {len(results)}")
        return results
```

### 4. 注册到 CRAWLERS（crawler.py 底部）

```python
CRAWLERS = {
    # ...
    "newco": NewCoCrawler,
}
```

### 5. 测试

```bash
python -c "from ecompulse.core.crawler import crawl_company; print(len(crawl_company('newco')))"
```

## API 爬虫 vs 浏览器爬虫

优先选择 **API 爬虫**（快、稳定）。只有在以下情况才用浏览器模式：
- 招聘网站的 API 需要签名/CSRF token
- 前端渲染的动态页面

浏览器爬虫示例参考 `BilibiliBrowserCrawler` 和 `BrowserNetworkCrawler`。

## 代码风格

- 不需要类型注解
- 中文注释可以
- 保持和现有代码风格一致
- 每个爬虫类放在 crawler.py 中
