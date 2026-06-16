# Changelog

## [2.0.0] - 2026-06-16

### 重构
- 全新架构：跨境电商竞品数据监控系统
- 数据库模型：`jobs` 表 → `products` 表（17 个电商字段）
- 采集层：10 个公司爬虫类拆分为 `scrapers/` 子包架构
- `BaseCrawler` → `BaseScraper`，`normalize_job` → `normalize_product`

### 新增
- 价格变动检测：`upsert_products()` 自动对比 `current_price`，变动写入 `price_history` 表
- 4 Sheet Excel 报表：全部商品 / 新品上架 / 价格变动明细 / 统计概览
- 红/绿/黄颜色编码：涨价红 ↑、降价绿 ↓、新品黄 ⭐（优先级：新品 > 价格变动）
- 库存状态监控：`in_stock` / `low_stock` / `out_of_stock` / `pre_order`
- `mark_inactive()` 下架检测机制（完全保留原逻辑）
- `ProductDatabase`：300+ 行重写，含 15 个查询/写入方法
- `BaseScraper.__init__` 默认选项初始化
- `scrapers/__init__.py`：爬虫注册表 + `get_scraper(platform)` 工厂函数
- Amazon Mock 爬虫（3 条模拟商品，支持 `is_target_product` 过滤）

### 删除
- 10 个公司爬虫类（美团/腾讯/百度/哔哩哔哩/小红书/快手/网易/阿里巴巴/字节跳动/拼多多）
- `BUSINESS_KEYWORDS` / `TECH_KEYWORDS` 过滤器
- `is_business_job()` 方法

### 保留
- `mark_inactive()` 下架检测机制
- `_check_schedule()` / `.after()` 定时采集框架
- `export_to_csv()` UTF-8 BOM 编码
- `utils/encoding.py` GBK 终端修复
- `settings` 表 KV 读写

## 1.0.0 (2026-06-08)

- 初始开源发布
- 10 家公司爬虫
- API + 浏览器双模采集
- 非技术岗智能过滤
- SQLite 持久化 + 增量比对
- Excel 导出（含高亮）+ CSV 导出（UTF-8 BOM）
- tkinter GUI
- 定时采集（每天/12h/6h）
- PyInstaller 打包脚本
