"""
Internship Tracker - Excel & CSV Exporter
Formatted Excel with new-job highlighting + CSV (UTF-8 BOM).
"""

import os, csv
from datetime import datetime
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

from internship_tracker.core.config import DATA_DIR


def export_to_excel(jobs, new_job_hashes, output_path=None):
    """Export to formatted Excel with 3 sheets: all, new, stats."""
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DATA_DIR, f"latest-internship-jobs_{timestamp}.xlsx")

    wb = Workbook()

    # -- Styles --
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style="thin"), right=Side(style="thin"),
                         top=Side(style="thin"), bottom=Side(style="thin"))
    new_fill = PatternFill(start_color="E7F3FF", end_color="E7F3FF", fill_type="solid")
    new_font = Font(name="微软雅黑", bold=True, color="D9001B")
    data_font = Font(name="微软雅黑", size=10)
    data_align = Alignment(vertical="top", wrap_text=True)
    link_font = Font(color="0563C1", underline="single")

    headers = ["岗位状态", "公司", "岗位名称", "岗位大类", "岗位子类",
               "工作地点", "所属部门", "实习类型", "上线时间",
               "首次发现时间", "最后更新时间", "JD 原文", "投递链接"]
    col_widths = [12, 12, 35, 12, 12, 20, 25, 12, 16, 18, 18, 80, 18]

    # -- Sheet 1: All Jobs --
    ws = wb.active
    ws.title = "全部岗位"
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.fill, c.font, c.alignment, c.border = header_fill, header_font, header_align, thin_border

    for ri, job in enumerate(jobs, 2):
        is_new = job.get("job_hash", "") in new_job_hashes
        row = ["新增" if is_new else "已记录",
               job.get("company",""), job.get("title",""),
               job.get("category",""), job.get("sub_category",""),
               job.get("location",""), job.get("department",""),
               job.get("type",""), job.get("publish_time",""),
               job.get("first_seen",""), job.get("last_updated",""),
               job.get("jd",""), job.get("url","")]
        for ci, val in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.font, c.alignment, c.border = data_font, data_align, thin_border
            if is_new:
                c.fill = new_fill
                if ci in (1, 3): c.font = new_font
        uc = ws.cell(row=ri, column=13)
        if job.get("url"): uc.hyperlink, uc.font = job["url"], link_font

    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[_col_letter(i)].width = w
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{_col_letter(len(headers))}{len(jobs)+1}"

    # -- Sheet 2: New Jobs --
    new_jobs = [j for j in jobs if j.get("job_hash","") in new_job_hashes]
    if new_jobs:
        ws2 = wb.create_sheet(title="新增岗位")
        for ci, h in enumerate(headers, 1):
            c = ws2.cell(row=1, column=ci, value=h)
            c.fill, c.font, c.alignment, c.border = header_fill, header_font, header_align, thin_border
        for ri, job in enumerate(new_jobs, 2):
            row = ["新增", job.get("company",""), job.get("title",""),
                   job.get("category",""), job.get("sub_category",""),
                   job.get("location",""), job.get("department",""),
                   job.get("type",""), job.get("publish_time",""),
                   job.get("first_seen",""), job.get("last_updated",""),
                   job.get("jd",""), job.get("url","")]
            for ci, val in enumerate(row, 1):
                c = ws2.cell(row=ri, column=ci, value=val)
                c.font, c.alignment, c.border, c.fill = data_font, data_align, thin_border, new_fill
            uc = ws2.cell(row=ri, column=13)
            if job.get("url"): uc.hyperlink, uc.font = job["url"], link_font
        for i, w in enumerate(col_widths, 1):
            ws2.column_dimensions[_col_letter(i)].width = w
        ws2.row_dimensions[1].height = 28
        ws2.freeze_panes = "A2"

    # -- Sheet 3: Stats --
    ws3 = wb.create_sheet(title="统计")
    for ci, h in enumerate(["指标","数值"], 1):
        c = ws3.cell(row=1, column=ci, value=h)
        c.fill, c.font, c.alignment = header_fill, header_font, header_align

    sd = [("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
          ("全部岗位数", len(jobs)), ("新增岗位数", len(new_jobs)),
          ("已记录岗位数", len(jobs)-len(new_jobs))]
    for comp, cnt in Counter(j.get("company","") for j in jobs).most_common():
        sd.append((comp or "未标明公司", cnt))
    for ri, (k, v) in enumerate(sd, 2):
        ws3.cell(row=ri, column=1, value=k).font = data_font
        ws3.cell(row=ri, column=2, value=v).font = data_font
    ws3.column_dimensions["A"].width = 25
    ws3.column_dimensions["B"].width = 15

    wb.save(output_path)
    return output_path


def export_to_csv(jobs, output_path=None):
    """Export jobs to CSV with UTF-8 BOM for Chinese Excel compatibility."""
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DATA_DIR, f"latest-internships_{ts}.csv")

    headers = ["公司","岗位名称","岗位大类","岗位子类","工作地点",
               "所属部门","实习类型","上线时间","首次发现时间","最后更新时间","JD原文","投递链接"]
    fields  = ["company","title","category","sub_category","location",
               "department","type","publish_time","first_seen","last_updated","jd","url"]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for job in jobs:
            w.writerow([job.get(f, "") for f in fields])
    return output_path


def _col_letter(n):
    s = ""
    while n: n, r = divmod(n-1, 26); s = chr(65+r) + s
    return s
