"""
Competitor Tracker GUI for e-commerce product monitoring.
Uses tkinter for native UI experience.
"""

import os, sys, time, threading, webbrowser, tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

from internship_tracker.utils.encoding import setup as setup_encoding
setup_encoding()

from internship_tracker.core.config import PLATFORMS, DATA_DIR
from internship_tracker.core.crawler import crawl_all
from internship_tracker.core.database import ProductDatabase
from internship_tracker.core.exporter import export_to_excel, export_to_csv


class App:
    """Main tkinter application for competitor product monitoring."""

    def __init__(self, root):
        self.root = root
        self.root.title("竞品监控 — Competitor Tracker")
        self.root.geometry("1024x720")
        self.root.minsize(900, 580)

        self.db = ProductDatabase()
        self._crawling = False
        self._scheduled_job_id = None
        self._last_price_changes = {}  # cached for export

        self._build_ui()
        self._refresh_stats()
        self._check_schedule()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        # -- Top frame: platform selection --
        top = ttk.LabelFrame(self.root, text="选择平台", padding=8)
        top.pack(fill="x", padx=10, pady=(10, 4))

        self._platform_vars = {}
        plat_frame = ttk.Frame(top)
        plat_frame.pack(fill="x")
        row = col = 0
        for key, info in PLATFORMS.items():
            var = tk.BooleanVar(value=info.get("enabled", True))
            self._platform_vars[key] = var
            cb = ttk.Checkbutton(plat_frame, text=info["name"], variable=var)
            cb.grid(row=row, column=col, sticky="w", padx=4, pady=2)
            col += 1
            if col >= 5:
                col = 0
                row += 1

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_frame, text="全选",
                   command=lambda: self._toggle_all(True)).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="取消全选",
                   command=lambda: self._toggle_all(False)).pack(side="left", padx=2)

        # -- Search frame --
        sf = ttk.Frame(top)
        sf.pack(fill="x", pady=(8, 0))
        ttk.Label(sf, text="搜索关键词:").pack(side="left")
        self._search_var = tk.StringVar()
        tk.Entry(sf, textvariable=self._search_var, width=40).pack(side="left", padx=6)

        # -- Action buttons --
        af = ttk.Frame(self.root)
        af.pack(fill="x", padx=10, pady=4)
        self._crawl_btn = ttk.Button(af, text="开始采集",
                                     command=self._start_crawl)
        self._crawl_btn.pack(side="left", padx=2)
        ttk.Button(af, text="导出 Excel",
                   command=self._export_excel).pack(side="left", padx=2)
        ttk.Button(af, text="导出 CSV",
                   command=self._export_csv).pack(side="left", padx=2)
        ttk.Button(af, text="打开数据目录",
                   command=lambda: os.startfile(DATA_DIR)).pack(side="left", padx=2)

        self._progress = ttk.Progressbar(af, mode="indeterminate", length=120)
        self._progress.pack(side="right", padx=8)

        # -- Schedule frame (fully preserved) --
        sch = ttk.LabelFrame(self.root, text="定时采集", padding=4)
        sch.pack(fill="x", padx=10, pady=4)
        self._schedule_var = tk.StringVar(
            value=self.db.get_setting("schedule", "off"))
        for text, val in [("关闭", "off"), ("每天 09:00", "daily"),
                          ("每12小时", "12h"), ("每6小时", "6h")]:
            ttk.Radiobutton(sch, text=text, variable=self._schedule_var,
                            value=val,
                            command=self._on_schedule_change).pack(
                side="left", padx=6)
        self._next_run_label = ttk.Label(sch, text="", foreground="gray")
        self._next_run_label.pack(side="right", padx=8)

        # -- Stats bar --
        self._stats_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self._stats_var, foreground="gray",
                  font=("", 9)).pack(fill="x", padx=14, pady=(0, 2))

        # -- Log area --
        lf = ttk.LabelFrame(self.root, text="采集日志", padding=4)
        lf.pack(fill="both", expand=True, padx=10, pady=4)

        self._log_text = tk.Text(lf, height=10, font=("Consolas", 9),
                                 wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(lf, orient="vertical",
                                  command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # -- Results tree --
        rf = ttk.LabelFrame(self.root, text="采集结果", padding=4)
        rf.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        columns = ("platform", "product_title", "sku_id",
                   "current_price", "sales_volume", "stock_status")
        self._tree = ttk.Treeview(rf, columns=columns, show="headings",
                                  height=8)
        self._tree.heading("platform", text="平台")
        self._tree.heading("product_title", text="商品名称")
        self._tree.heading("sku_id", text="SKU ID")
        self._tree.heading("current_price", text="价格")
        self._tree.heading("sales_volume", text="销量")
        self._tree.heading("stock_status", text="库存状态")
        self._tree.column("platform", width=80, minwidth=60)
        self._tree.column("product_title", width=300, minwidth=180)
        self._tree.column("sku_id", width=140, minwidth=100)
        self._tree.column("current_price", width=80, minwidth=60)
        self._tree.column("sales_volume", width=70, minwidth=50)
        self._tree.column("stock_status", width=80, minwidth=60)

        tree_scroll = ttk.Scrollbar(rf, orient="vertical",
                                    command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_tree_double_click)

    # ==================================================================
    # Actions
    # ==================================================================

    def _toggle_all(self, select):
        for var in self._platform_vars.values():
            var.set(select)

    def _selected_platforms(self):
        return [k for k, v in self._platform_vars.items() if v.get()]

    def _log(self, msg):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _start_crawl(self):
        if self._crawling:
            messagebox.showinfo("提示", "采集任务正在运行中")
            return

        platforms = self._selected_platforms()
        if not platforms:
            messagebox.showwarning("提示", "请至少选择一个平台")
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
                products = crawl_all(platforms, log_func=self._log,
                                     search_terms=search_terms)
                elapsed = time.time() - start_t

                # 4-tuple: new, updated, price_changed, hashes
                new_cnt, upd_cnt, price_chg, hashes = \
                    self.db.upsert_products(products)
                self.db.mark_inactive(hashes, platforms=platforms)
                self.db.record_run(platforms, len(products),
                                   new_cnt, upd_cnt, price_chg, elapsed)

                self._log(f"\n===== 采集完成 =====")
                self._log(f"共采集: {len(products)} 件商品 "
                          f"(新增 {new_cnt}, 更新 {upd_cnt}, "
                          f"价格变动 {price_chg})")
                self._log(f"耗时: {elapsed:.1f} 秒")

                # Build price_changes dict for export
                pc_dict = self._build_price_changes(hashes)
                self._last_price_changes = pc_dict

                # Export
                all_products = self.db.export_all()
                xlsx_p = export_to_excel(
                    all_products, new_hashes=set(),
                    price_changes=pc_dict)
                csv_p = export_to_csv(all_products)
                self._log(f"Excel: {xlsx_p}")
                self._log(f"CSV:   {csv_p}")

                # Update tree from root thread
                self.root.after(0, lambda: self._fill_tree(all_products))
                self.root.after(0, self._refresh_stats)

            except Exception as e:
                self._log(f"\n采集出错: {e}")
                import traceback
                self._log(traceback.format_exc())
            finally:
                self.root.after(0, self._crawl_done)

        threading.Thread(target=_run, daemon=True).start()

    def _build_price_changes(self, hashes):
        """Build {product_hash: (old_price, new_price)} from price_history."""
        pc = {}
        for h in hashes:
            history = self.db.get_price_history(h, limit=1)
            if not history:
                continue
            old_price = history[0]["price"]
            # Look up current price from active products
            for p in self.db.export_all():
                if p.get("product_hash") == h:
                    new_price = p.get("current_price")
                    if new_price is not None and old_price is not None:
                        pc[h] = (old_price, new_price)
                    break
        return pc

    def _crawl_done(self):
        self._crawling = False
        self._crawl_btn.configure(state="normal")
        self._progress.stop()
        self._stats_var.set(f"就绪 - {datetime.now():%H:%M:%S}")

    def _fill_tree(self, products):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for p in products[:2000]:  # increased limit for products
            stock_label = {
                "in_stock": "有库存", "low_stock": "低库存",
                "out_of_stock": "缺货", "pre_order": "预售",
            }.get(p.get("stock_status", ""), p.get("stock_status", ""))
            self._tree.insert("", "end", values=(
                p.get("platform", ""),
                p.get("product_title", ""),
                p.get("sku_id", ""),
                f"{p.get('currency', 'USD')} {p.get('current_price', '')}",
                p.get("sales_volume", 0),
                stock_label,
            ))

    def _on_tree_double_click(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if values:
            platform, title, sku = values[0], values[1], values[2]
            products = self.db.get_all_active_products()
            for p in products:
                if (p["platform"] == platform
                        and p["product_title"] == title
                        and p["sku_id"] == sku):
                    self._show_product_detail(p)
                    return

    def _show_product_detail(self, product):
        win = tk.Toplevel(self.root)
        win.title(f"{product['product_title']} - {product['platform']}")
        win.geometry("640x480")

        txt = tk.Text(win, wrap="word", font=("", 10))
        txt.pack(fill="both", expand=True, padx=6, pady=6)

        rating_str = f"{product.get('rating', '')} / 5" if product.get(
            'rating') is not None else "N/A"
        stock_map = {"in_stock": "有库存", "low_stock": "低库存",
                     "out_of_stock": "缺货", "pre_order": "预售"}
        stock_label = stock_map.get(product.get("stock_status", ""),
                                    product.get("stock_status", ""))

        info = f"""平台: {product['platform']}
商品标题: {product['product_title']}
SKU ID: {product.get('sku_id', '')}
类目: {product.get('category', '')}
店铺: {product.get('shop_name', '')}
当前价格: {product.get('currency', 'USD')} {product.get('current_price', '')}
原价: {product.get('currency', 'USD')} {product.get('original_price', '')}
销量: {product.get('sales_volume', 0)}
评价数: {product.get('review_count', 0)}
评分: {rating_str}
库存状态: {stock_label}
上架日期: {product.get('listing_date', '')}
首次监控: {product.get('first_seen', '')}
最后更新: {product.get('last_updated', '')}
商品链接: {product.get('product_url', '')}
"""
        txt.insert("1.0", info)
        txt.configure(state="disabled")

        if product.get("product_url"):
            ttk.Button(win, text="打开商品链接",
                       command=lambda: webbrowser.open(
                           product["product_url"])).pack(pady=4)

    def _export_excel(self):
        products = self.db.export_all()
        if not products:
            messagebox.showinfo("提示", "还没有采集数据")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"competitor_products_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
        if fp:
            export_to_excel(products, new_hashes=set(),
                            price_changes=self._last_price_changes,
                            output_path=fp)
            messagebox.showinfo("提示", f"已导出到:\n{fp}")

    def _export_csv(self):
        products = self.db.export_all()
        if not products:
            messagebox.showinfo("提示", "还没有采集数据")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"competitor_products_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if fp:
            export_to_csv(products, output_path=fp)
            messagebox.showinfo("提示", f"已导出到:\n{fp}")

    def _refresh_stats(self):
        try:
            s = self.db.get_stats()
            # Count today's price changes from price_history
            today = datetime.now().strftime("%Y-%m-%d")
            pc_today = 0
            try:
                with self.db._connect() as conn:
                    pc_today = conn.execute(
                        "SELECT COUNT(*) FROM price_history "
                        "WHERE recorded_at >= ?", (today + " 00:00:00",)
                    ).fetchone()[0]
            except Exception:
                pass

            self._stats_var.set(
                f"活跃商品: {s['active_products']} | "
                f"监控平台: {s['platforms']} | "
                f"缺货: {s['out_of_stock']} | "
                f"今日价格变动: {pc_today} 件 | "
                f"上次采集: {s['last_run']}"
            )
        except Exception:
            pass

    # ==================================================================
    # Schedule (fully preserved — no changes from original)
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
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.mainloop()


if __name__ == "__main__":
    main()
