# 跨境电商竞品数据监控系统 — Competitor Tracker

基于 Playwright + SQLite 的多平台跨境电商竞品价格监控桌面工具。

双击运行，选择平台，点「开始采集」即可。自动检测价格变动、新品上架、商品下架，结果存 SQLite 数据库并导出带颜色高亮的 Excel 报表。

## 核心功能

- **多平台采集**：Amazon / Shopee / Lazada / Temu（可通过 `config.py` 扩展）
- **双模采集**：优先 API 直连（快），部分平台用浏览器自动抓取（Playwright）
- **价格变动检测**：自动对比历史价格，变动商品写入 `price_history` 表
- **新品上架标记**：首次发现的商品自动标记为"新品上架"
- **下架检测**：未出现在本次采集中的商品自动标记为"已下架"
- **4 Sheet Excel 报表**：
  - 全部商品（涨价红 ↑ / 降价绿 ↓ / 新品黄 ⭐ 颜色高亮）
  - 新品上架（仅本轮新发现商品）
  - 价格变动明细（旧价→新价 / 涨跌额 / 涨跌幅%）
  - 统计概览（各平台商品数 / 涨跌分布 / 缺货统计）
- **CSV 导出**：UTF-8 BOM 编码，兼容中文 Excel
- **定时采集**：可设置每天 / 每 12h / 每 6h 自动运行
- **桌面 GUI**：基于 tkinter 的本地界面，无需浏览器

## 快速开始

### 方式一：直接运行 EXE（推荐，无需 Python）

从 [Releases](../../releases) 下载 `竞品监控.zip`，解压后双击 `竞品监控.exe`。

### 方式二：从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器（部分平台需要）
playwright install chromium

# 3. 启动 GUI
python main.py
```

### 命令行模式

```bash
# 无 GUI 单次采集
python main.py --crawl

# 导出已有数据
python main.py --export
```

## 平台覆盖

| 平台 | 采集方式 | 货币 | 状态 |
|------|---------|------|------|
| Amazon | API / Browser | USD | 🚧 Mock 爬虫 |
| Shopee | Browser | TWD | 📋 待实现 |
| Lazada | Browser | THB | 📋 待实现 |
| Temu | Browser | USD | 📋 待实现 |

## 数据存储

- **Windows**: `%LOCALAPPDATA%\实习岗位采集器\`
- **macOS/Linux**: `~/.local/share/internship-tracker/`

主要文件：
- `data/tracker_app/jobs.db` — 商品数据库（SQLite，含 `products` + `price_history` 表）
- `competitor-products_*.xlsx` — 最近一次 Excel 导出（4 Sheet，含颜色高亮）
- `competitor-products_*.csv` — 最近一次 CSV 导出（UTF-8 BOM）

卸载时上述数据目录**不会**被自动删除，避免误删历史记录。

## 配置

编辑 `internship_tracker/core/config.py` 可自定义：
- 启用/禁用平台（`PLATFORMS` dict）
- 修改采集速率（`DEFAULT_MAX_PAGES` / `REQUEST_DELAY`）
- 商品类目过滤（`PRODUCT_CATEGORY_FILTERS`）

## 打包 EXE

```bash
pip install pyinstaller
python build_exe.py
```

输出在 `dist/竞品监控/` 目录。

## 项目架构

```
competitor_tracker/core/
├── config.py          # 平台配置 + 过滤规则
├── database.py        # ProductDatabase (SQLite: products + price_history)
├── crawler.py         # 采集编排 (crawl_all → get_scraper)
├── exporter.py        # 4 Sheet Excel + CSV 导出
└── scrapers/
    ├── base.py        # BaseScraper 基类
    ├── amazon_scraper.py  # Amazon 平台爬虫
    └── __init__.py    # 爬虫注册表 + get_scraper 工厂
```

## 依赖

- Python >= 3.10
- requests, openpyxl, playwright（仅浏览器模式）
- tkinter（Python 自带）

## 常见问题

**Q: 为什么平台爬虫显示"待实现"？**
A: 当前版本包含 Amazon Mock 爬虫用于测试。真实平台爬虫将在后续版本中陆续添加。你也可以在 `scrapers/` 目录下自行添加。

**Q: 如何添加新平台？**
A: 1) 在 `config.py` 的 `PLATFORMS` 中注册；2) 在 `scrapers/` 下新建爬虫类继承 `BaseScraper`；3) 在 `scrapers/__init__.py` 中注册。

**Q: 价格变动检测如何工作？**
A: 每次采集时对比 `current_price`，如变化则自动向 `price_history` 表写入旧价格记录。Excel 报表中涨价显示红色、降价显示绿色。

## 贡献

欢迎 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)
