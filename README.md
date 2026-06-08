# 实习岗位采集器 — Internship Tracker

自动采集 10 家互联网公司非技术实习岗位的桌面工具。

双击运行，选择公司，点「开始采集」即可。结果自动存 SQLite 数据库并导出 Excel / CSV。

## 功能

- **10 家公司**：美团、腾讯、百度、哔哩哔哩、小红书、快手、网易、阿里巴巴、字节跳动、拼多多
- **双模采集**：优先 API 直连（快），部分网站用浏览器自动抓取（Playwright）
- **非技术岗过滤**：自动识别产品/运营/市场/职能/设计等，排除开发/算法岗
- **增量追踪**：自动对比历史数据，标注新增岗位
- **定时采集**：可设置每天/每 12h/每 6h 自动运行
- **多格式导出**：Excel（含高亮）+ CSV（UTF-8 BOM）+ JSON

## 快速开始

### 方式一：直接运行 EXE（推荐，无需 Python）

从 [Releases](../../releases) 下载 `实习岗位采集器.zip`，解压后双击 `实习岗位采集器.exe`。

### 方式二：从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器（部分公司需要）
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

## 公司覆盖

| 公司 | 方式 | 状态 |
|------|------|------|
| 美团 | API | ✅ |
| 腾讯 | API | ✅ |
| 百度 | API | ✅ |
| 网易 | API | ✅ |
| 小红书 | API | ✅ |
| 快手 | API | ✅ |
| 哔哩哔哩 | 浏览器拦截 API | ✅ |
| 阿里巴巴 | 浏览器拦截 API | ⚠️ 岗位较少 |
| 字节跳动 | 浏览器拦截 API | ✅ |
| 拼多多 | API 关键词搜索 | ⚠️ 非技术岗少 |

## 数据存储

- **Windows**: `%LOCALAPPDATA%\实习岗位采集器\`
- **macOS/Linux**: `~/.local/share/internship-tracker/`

主要文件：
- `data/tracker_app/jobs.db` — 历史岗位数据库（SQLite）
- `latest-result.json` — 最近一次采集结果
- `latest-internship-jobs.xlsx` — 最近一次 Excel 导出
- `latest-internships.csv` — 最近一次 CSV 导出

卸载时上述数据目录**不会**被自动删除，避免误删历史记录。

## 配置

编辑 `internship_tracker/core/config.py` 可自定义：
- 启用/禁用公司（`COMPANIES` dict）
- 调整技术岗/非技术岗过滤关键词（`BUSINESS_KEYWORDS` / `TECH_KEYWORDS`）
- 修改采集速率（`DEFAULT_MAX_PAGES` / `REQUEST_DELAY`）

## 打包 EXE

```bash
pip install pyinstaller
python build_exe.py
```

输出在 `dist/实习岗位采集器/` 目录。

## 常见问题

**Q: 为什么阿里巴巴/拼多多岗位少？**
A: 阿里和拼多多的非技术实习岗位本身较少，或 API 返回偏技术岗。这是正常现象。

**Q: 能改成采集技术岗吗？**
A: 编辑 `config.py`，把 `TECH_KEYWORDS` 清空即可。

**Q: 浏览器模式的网站采集慢？**
A: 是的，阿里、字节、B 站需要启动内置 Chromium，每次约 5-10 秒。这是必要的。

## 依赖

- Python >= 3.10
- requests, openpyxl, playwright (仅浏览器模式)
- tkinter (Python 自带)

## 贡献

欢迎 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)
