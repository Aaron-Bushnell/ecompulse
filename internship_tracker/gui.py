"""
Excel-based tracker GUI for internship positions.
Uses tkinter for native UI experience.
"""

import os, sys, time, json, threading, webbrowser, tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

from internship_tracker.utils.encoding import setup as setup_encoding
setup_encoding()

from internship_tracker.core.config import COMPANIES, DATA_DIR
from internship_tracker.core.crawler import crawl_all
from internship_tracker.core.database import JobDatabase
from internship_tracker.core.exporter import export_to_excel, export_to_csv


class App:
    """Main tkinter application."""

    def __init__(self, root):
        self.root = root
        self.root.title("实习岗位采集器")
        self.root.geometry("960x700")
        self.root.minsize(800, 550)

        self.db = JobDatabase()
        self._crawling = False
        self._scheduled_job_id = None

        self._build_ui()
        self._refresh_stats()
        self._check_schedule()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        # -- Top frame: company selection --
        top = ttk.LabelFrame(self.root, text="选择公司", padding=8)
        top.pack(fill="x", padx=10, pady=(10, 4))

        self._company_vars = {}
        comp_frame = ttk.Frame(top)
        comp_frame.pack(fill="x")
        row = col = 0
        for key, info in COMPANIES.items():
            var = tk.BooleanVar(value=info.get("enabled", True))
            self._company_vars[key] = var
            cb = ttk.Checkbutton(comp_frame, text=info["name"], variable=var)
            cb.grid(row=row, column=col, sticky="w", padx=4, pady=2)
            col += 1
            if col >= 5:
                col = 0
                row += 1

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_frame, text="全选", command=lambda: self._toggle_all(True)).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="取消全选", command=lambda: self._toggle_all(False)).pack(side="left", padx=2)

        # -- Search frame --
        sf = ttk.Frame(top)
        sf.pack(fill="x", pady=(8, 0))
        ttk.Label(sf, text="搜索关键词:").pack(side="left")
        self._search_var = tk.StringVar()
        tk.Entry(sf, textvariable=self._search_var, width=40).pack(side="left", padx=6)

        # -- Action buttons --
        af = ttk.Frame(self.root)
        af.pack(fill="x", padx=10, pady=4)
        self._crawl_btn = ttk.Button(af, text="开始采集", command=self._start_crawl)
        self._crawl_btn.pack(side="left", padx=2)
        ttk.Button(af, text="导出 Excel", command=self._export_excel).pack(side="left", padx=2)
        ttk.Button(af, text="导出 CSV", command=self._export_csv).pack(side="left", padx=2)
        ttk.Button(af, text="打开数据目录", command=lambda: os.startfile(DATA_DIR)).pack(side="left", padx=2)

        self._progress = ttk.Progressbar(af, mode="indeterminate", length=120)
        self._progress.pack(side="right", padx=8)

        # -- Schedule frame --
        sch = ttk.LabelFrame(self.root, text="定时采集", padding=4)
        sch.pack(fill="x", padx=10, pady=4)
        self._schedule_var = tk.StringVar(value=self.db.get_setting("schedule", "off"))
        for text, val in [("关闭", "off"), ("每天 09:00", "daily"),
                          ("每12小时", "12h"), ("每6小时", "6h")]:
            ttk.Radiobutton(sch, text=text, variable=self._schedule_var,
                            value=val, command=self._on_schedule_change).pack(side="left", padx=6)
        self._next_run_label = ttk.Label(sch, text="", foreground="gray")
        self._next_run_label.pack(side="right", padx=8)

        # -- Stats bar --
        self._stats_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self._stats_var, foreground="gray",
                  font=("", 9)).pack(fill="x", padx=14, pady=(0, 2))

        # -- Log area --
        lf = ttk.LabelFrame(self.root, text="采集日志", padding=4)
        lf.pack(fill="both", expand=True, padx=10, pady=4)

        self._log_text = tk.Text(lf, height=12, font=("Consolas", 9), wrap="word",
                                 state="disabled")
        scrollbar = ttk.Scrollbar(lf, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # -- Results tree --
        rf = ttk.LabelFrame(self.root, text="采集结果", padding=4)
        rf.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        columns = ("company", "title", "location", "category", "publish_time")
        self._tree = ttk.Treeview(rf, columns=columns, show="headings", height=8)
        self._tree.heading("company", text="公司")
        self._tree.heading("title", text="岗位名称")
        self._tree.heading("location", text="地点")
        self._tree.heading("category", text="类别")
        self._tree.heading("publish_time", text="上线时间")
        self._tree.column("company", width=80, minwidth=60)
        self._tree.column("title", width=280, minwidth=150)
        self._tree.column("location", width=120, minwidth=80)
        self._tree.column("category", width=100, minwidth=60)
        self._tree.column("publish_time", width=100, minwidth=80)

        tree_scroll = ttk.Scrollbar(rf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_tree_double_click)

    # ==================================================================
    # Actions
    # ==================================================================

    def _toggle_all(self, select):
        for var in self._company_vars.values():
            var.set(select)

    def _selected_companies(self):
        return [k for k, v in self._company_vars.items() if v.get()]

    def _log(self, msg):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _start_crawl(self):
        if self._crawling:
            messagebox.showinfo("提示", "采集任务正在运行中")
            return

        companies = self._selected_companies()
        if not companies:
            messagebox.showwarning("提示", "请至少选择一家公司")
            return

        self._crawling = True
        self._crawl_btn.configure(state="disabled")
        self._progress.start()
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

        # Clear tree
        for item in self._tree.get_children():
            self._tree.delete(item)

        search_text = self._search_var.get().strip()
        search_terms = search_text.split() if search_text else None

        self._stats_var.set("采集中...")

        def _run():
            try:
                start_t = time.time()
                jobs = crawl_all(companies, log_func=self._log, search_terms=search_terms)
                elapsed = time.time() - start_t

                new_cnt, upd_cnt, hashes = self.db.upsert_jobs(jobs)
                self.db.mark_inactive(hashes, companies=companies)
                self.db.record_run(companies, len(jobs), new_cnt, upd_cnt, elapsed)

                self._log(f"\n===== 采集完成 =====")
                self._log(f"共采集: {len(jobs)} 条 (新增 {new_cnt}, 更新 {upd_cnt})")
                self._log(f"耗时: {elapsed:.1f} 秒")

                # Export
                all_jobs = self.db.export_all()
                xlsx_p = export_to_excel(all_jobs, hashes)
                csv_p = export_to_csv(all_jobs)
                self._log(f"Excel: {xlsx_p}")
                self._log(f"CSV:   {csv_p}")

                # Update tree from root thread
                self.root.after(0, lambda: self._fill_tree(all_jobs))
                self.root.after(0, self._refresh_stats)

            except Exception as e:
                self._log(f"\n采集出错: {e}")
                import traceback
                self._log(traceback.format_exc())
            finally:
                self.root.after(0, self._crawl_done)

        threading.Thread(target=_run, daemon=True).start()

    def _crawl_done(self):
        self._crawling = False
        self._crawl_btn.configure(state="normal")
        self._progress.stop()
        self._stats_var.set(f"就绪 - {datetime.now():%H:%M:%S}")

    def _fill_tree(self, jobs):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for j in jobs[:500]:  # limit visible rows
            self._tree.insert("", "end", values=(
                j.get("company",""), j.get("title",""), j.get("location",""),
                j.get("category","") or j.get("sub_category",""),
                j.get("publish_time",""),
            ))

    def _on_tree_double_click(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if values:
            company, title = values[0], values[1]
            jobs = self.db.get_all_active_jobs()
            for j in jobs:
                if j["company"] == company and j["title"] == title:
                    self._show_job_detail(j)
                    return

    def _show_job_detail(self, job):
        win = tk.Toplevel(self.root)
        win.title(f"{job['title']} - {job['company']}")
        win.geometry("600x450")

        txt = tk.Text(win, wrap="word", font=("", 10))
        txt.pack(fill="both", expand=True, padx=6, pady=6)

        info = f"""公司: {job['company']}
岗位: {job['title']}
类别: {job.get('category','')} / {job.get('sub_category','')}
地点: {job.get('location','')}
部门: {job.get('department','')}
类型: {job.get('type','') or job.get('job_type','')}
上线时间: {job.get('publish_time','')}
首次发现: {job.get('first_seen','')}
最后更新: {job.get('last_updated','')}
投递链接: {job.get('url','')}

=== JD 原文 ===
{job.get('jd','')}
"""
        txt.insert("1.0", info)
        txt.configure(state="disabled")

        if job.get("url"):
            ttk.Button(win, text="打开投递链接",
                       command=lambda: webbrowser.open(job["url"])).pack(pady=4)

    def _export_excel(self):
        jobs = self.db.export_all()
        if not jobs:
            messagebox.showinfo("提示", "还没有采集数据")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"internships_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
        if fp:
            export_to_excel(jobs, set(), output_path=fp)
            messagebox.showinfo("提示", f"已导出到:\n{fp}")

    def _export_csv(self):
        jobs = self.db.export_all()
        if not jobs:
            messagebox.showinfo("提示", "还没有采集数据")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"internships_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if fp:
            export_to_csv(jobs, output_path=fp)
            messagebox.showinfo("提示", f"已导出到:\n{fp}")

    def _refresh_stats(self):
        try:
            s = self.db.get_stats()
            self._stats_var.set(
                f"活跃岗位: {s['active_jobs']} | 覆盖公司: {s['companies']} | "
                f"总记录: {s['total_jobs']} | 上次采集: {s['last_run']}"
            )
        except Exception:
            pass

    # ==================================================================
    # Schedule
    # ==================================================================

    def _on_schedule_change(self):
        interval = self._schedule_var.get()
        self.db.set_setting("schedule", interval)
        self._check_schedule()
        self._log(f"定时设置已更新: {interval}")

    def _check_schedule(self):
        interval = self.db.get_setting("schedule", "off")
        self._schedule_var.set(interval)

        # Cancel previous
        if self._scheduled_job_id:
            self.root.after_cancel(self._scheduled_job_id)
            self._scheduled_job_id = None

        if interval == "off":
            self._next_run_label.configure(text="")
            return

        # Simple timer-based scheduling (no extra dependency)
        if interval == "daily":
            ms = 24 * 3600 * 1000
            next_info = "明天 09:00"
        elif interval == "12h":
            ms = 12 * 3600 * 1000
            next_info = "12 小时后"
        elif interval == "6h":
            ms = 6 * 3600 * 1000
            next_info = "6 小时后"
        else:
            return

        self._next_run_label.configure(text=f"下次采集: {next_info}")

        def _run_scheduled():
            if self._crawling:
                self._scheduled_job_id = self.root.after(60000, _run_scheduled)
                return
            self._log(f"[定时] {datetime.now():%H:%M:%S} 开始自动采集...")
            self._start_crawl()
            self._scheduled_job_id = self.root.after(ms, _run_scheduled)

        self._scheduled_job_id = self.root.after(ms, _run_scheduled)

    def on_close(self):
        if self._scheduled_job_id:
            self.root.after_cancel(self._scheduled_job_id)
        self.root.destroy()


def main():
    import tkinter as tk
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)

    # Center window
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    root.mainloop()


if __name__ == "__main__":
    main()
