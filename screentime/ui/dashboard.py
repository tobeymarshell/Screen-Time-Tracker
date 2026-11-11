"""Analytics Dashboard window, weekly breakdown charts, and application list."""

from datetime import date, datetime, timedelta
import hashlib
import os
import sqlite3
import tkinter as tk
from tkinter import ttk

from ..storage import (
    open_db_readonly,
    query_daily_total,
    query_top_apps,
    query_daily_totals_range,
)
from ..win32 import user32, gdi32
from .theme import (
    BG,
    CARD_BG,
    CARD_BORDER,
    HOVER_BG,
    FG,
    MUTED,
    MUTED_DARK,
    ACCENT,
    TRACK_BG,
    COLORS,
    FONT_MAIN,
    round_rect,
    format_app_name,
    format_duration,
)

class AppRow(tk.Canvas):
    def __init__(self, master, app, dur, mx, idx, total=0, **kwargs):
        super().__init__(master, bg=BG, height=56, highlightthickness=0, **kwargs)
        self.app, self.dur, self.mx, self.idx = app, dur, max(1, mx), idx
        self.total = total if total > 0 else self.mx
        self.display_name = format_app_name(self.app)
        self.is_hovered = False

        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self.is_hovered = True
        self.draw()

    def on_leave(self, e):
        self.is_hovered = False
        self.draw()

    def draw(self, event=None):
        w = self.winfo_width()
        if w < 20:
            return
        self.delete("all")

        bg_col = HOVER_BG if self.is_hovered else CARD_BG
        round_rect(self, 0, 0, w, 56, 12, bg_col, CARD_BORDER)

        color_idx = int(hashlib.md5(self.app.encode()).hexdigest(), 16) % len(COLORS)
        accent_color = COLORS[color_idx]
        letter = self.display_name[0].upper() if self.display_name else "?"

        # App Icon Badge
        round_rect(self, 14, 12, 44, 42, 8, accent_color)
        self.create_text(29, 27, text=letter, fill="#FFFFFF", font=(FONT_MAIN, 13, "bold"))

        # App Title
        title = self.display_name
        if len(title) > 22:
            title = title[:20] + "…"
        self.create_text(58, 27, text=title, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="w")

        # Duration label on the right
        dur_str = format_duration(self.dur)
        self.create_text(w - 18, 27, text=dur_str, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="e")

        # Percentage tag (relative to total daily screen time)
        pct = int((self.dur / self.total) * 100)
        self.create_text(w - 95, 27, text=f"{pct}%", fill=MUTED, font=(FONT_MAIN, 9), anchor="e")

        # Progress Bar
        bar_x1 = 250
        bar_x2 = w - 130
        bar_w = bar_x2 - bar_x1
        if bar_w > 20:
            bw = max(int(bar_w * (self.dur / self.mx)), 6)
            self.create_line(bar_x1, 27, bar_x2, 27, width=8, fill=TRACK_BG, capstyle=tk.ROUND)
            self.create_line(bar_x1, 27, bar_x1 + bw, 27, width=8, fill=accent_color, capstyle=tk.ROUND)

class Dashboard:
    def __init__(self, window: tk.Toplevel, db_path: str):
        self.window, self.db_path = window, str(db_path)
        self.selected_date = date.today()
        self.week_offset = 0
        self.weekly_bars = []

        self.window.overrideredirect(True)
        self.window.geometry("860x780")
        self.window.configure(bg=BG)
        self.window.minsize(780, 700)
        self.window.attributes("-topmost", True)
        self.window.after(100, lambda: self.window.attributes("-topmost", False))

        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # ─── Custom Title Bar ───
        title_bar = tk.Frame(self.window, bg=CARD_BG, height=44)
        title_bar.pack(fill="x", side="top")

        def start_drag(e):
            self.drag_x = self.window.winfo_pointerx() - self.window.winfo_x()
            self.drag_y = self.window.winfo_pointery() - self.window.winfo_y()

        def do_drag(e):
            nx = self.window.winfo_pointerx() - self.drag_x
            ny = self.window.winfo_pointery() - self.drag_y
            self.window.geometry(f"+{nx}+{ny}")

        def stop_drag(e):
            hwnd = user32.GetAncestor(self.window.winfo_id(), 2)
            rgn = gdi32.CreateRoundRectRgn(0, 0, self.window.winfo_width() + 1, self.window.winfo_height() + 1, 20, 20)
            user32.SetWindowRgn(hwnd, rgn, True)

        title_bar.bind("<ButtonPress-1>", start_drag)
        title_bar.bind("<B1-Motion>", do_drag)
        title_bar.bind("<ButtonRelease-1>", stop_drag)

        dot = tk.Label(title_bar, text="●", bg=CARD_BG, fg=ACCENT, font=(FONT_MAIN, 9))
        dot.pack(side="left", padx=(18, 6), pady=12)
        title_lbl = tk.Label(title_bar, text="Screen Time Analytics", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 11, "bold"))
        title_lbl.pack(side="left", pady=12)
        for w in (dot, title_lbl):
            w.bind("<ButtonPress-1>", start_drag)
            w.bind("<B1-Motion>", do_drag)
            w.bind("<ButtonRelease-1>", stop_drag)

        close_btn = tk.Label(title_bar, text="✕", bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 11, "bold"), cursor="hand2", padx=18, pady=10)
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self.on_close())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#FFFFFF", bg="#DC2626"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=MUTED, bg=CARD_BG))

        self.window.update_idletasks()
        hwnd = user32.GetAncestor(self.window.winfo_id(), 2)
        rgn = gdi32.CreateRoundRectRgn(0, 0, self.window.winfo_width() + 1, self.window.winfo_height() + 1, 20, 20)
        user32.SetWindowRgn(hwnd, rgn, True)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar", gripcount=0, background=TRACK_BG, darkcolor=BG, lightcolor=BG, troughcolor=BG, bordercolor=BG, arrowcolor=BG, width=8)
        style.map("Vertical.TScrollbar", background=[('active', MUTED)])

        # ─── Hero Summary Card ───
        hero_card = tk.Frame(self.window, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
        hero_card.pack(fill="x", padx=30, pady=(16, 0))

        hero_inner = tk.Frame(hero_card, bg=CARD_BG)
        hero_inner.pack(fill="x", padx=24, pady=18)

        left_hero = tk.Frame(hero_inner, bg=CARD_BG)
        left_hero.pack(side="left")

        self.date_lbl = tk.Label(left_hero, text="Today", font=(FONT_MAIN, 13, "bold"), bg=CARD_BG, fg=MUTED)
        self.date_lbl.pack(anchor="w")

        self.total = tk.Label(left_hero, text="—", font=(FONT_MAIN, 46, "bold"), bg=CARD_BG, fg=FG)
        self.total.pack(anchor="w")

        self.sub_total = tk.Label(left_hero, text="Total Active Screen Time", font=(FONT_MAIN, 9), bg=CARD_BG, fg=MUTED_DARK)
        self.sub_total.pack(anchor="w")

        nav_frame = tk.Frame(hero_inner, bg=CARD_BG)
        nav_frame.pack(side="right", anchor="center")

        def make_btn(parent, text, cmd, is_primary=False):
            btn_bg = ACCENT if is_primary else HOVER_BG
            btn_fg = "#FFFFFF" if is_primary else FG
            b = tk.Button(parent, text=text, command=cmd, bg=btn_bg, fg=btn_fg, relief="flat",
                          padx=13, pady=6, font=(FONT_MAIN, 9, "bold"), bd=0, cursor="hand2",
                          activebackground=ACCENT, activeforeground="#FFFFFF")
            b.pack(side="left", padx=4)
            return b

        make_btn(nav_frame, "‹ Prev Week", self.prev_week)
        make_btn(nav_frame, "Today", self.go_today, is_primary=True)
        make_btn(nav_frame, "Next Week ›", self.next_week)
        make_btn(nav_frame, "↻", self.refresh)

        # ─── Chart Card ───
        chart_card = tk.Frame(self.window, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
        chart_card.pack(fill="x", padx=30, pady=(14, 0))

        chart_head = tk.Frame(chart_card, bg=CARD_BG)
        chart_head.pack(fill="x", padx=20, pady=(14, 0))
        self.chart_title = tk.Label(chart_head, text="Weekly Activity", font=(FONT_MAIN, 12, "bold"), bg=CARD_BG, fg=FG)
        self.chart_title.pack(side="left")
        self.chart_hint = tk.Label(chart_head, text="Click a bar to view daily breakdown", font=(FONT_MAIN, 9), bg=CARD_BG, fg=MUTED_DARK)
        self.chart_hint.pack(side="right")

        self.weekly = tk.Canvas(chart_card, bg=CARD_BG, highlightthickness=0, height=135)
        self.weekly.pack(fill="x", padx=15, pady=(6, 14))
        self.weekly.bind("<Button-1>", self.on_weekly_click)

        # ─── Top Apps List ───
        apps_header = tk.Frame(self.window, bg=BG)
        apps_header.pack(fill="x", padx=34, pady=(16, 8))
        self.apps_title = tk.Label(apps_header, text="Top Applications", font=(FONT_MAIN, 13, "bold"), bg=BG, fg=FG)
        self.apps_title.pack(side="left")

        list_container = tk.Frame(self.window, bg=BG)
        list_container.pack(side="top", fill="both", expand=True, padx=30, pady=(0, 10))

        self.canvas = tk.Canvas(list_container, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ─── Footer Status ───
        footer = tk.Frame(self.window, bg=BG)
        footer.pack(side="bottom", fill="x", padx=35, pady=(0, 12))
        self.status = tk.Label(footer, text="", font=(FONT_MAIN, 9), bg=BG, fg=MUTED_DARK)
        self.status.pack(side="left")

        self.window.after(150, self.refresh)
        self.auto_refresh_job = self.window.after(30_000, self.auto_refresh)

    def on_close(self):
        self.window.after_cancel(self.auto_refresh_job)
        self.window.destroy()

    def go_today(self):
        self.selected_date = date.today()
        self.week_offset = 0
        self.refresh()

    def prev_week(self):
        self.week_offset += 1
        self.selected_date -= timedelta(weeks=1)
        self.refresh()

    def next_week(self):
        if self.week_offset > 0:
            self.week_offset -= 1
            self.selected_date = min(date.today(), self.selected_date + timedelta(weeks=1))
            self.refresh()

    def on_weekly_click(self, event):
        for x1, y1, x2, y2, bar_date in self.weekly_bars:
            if x1 <= event.x <= x2 and 0 <= event.y <= 135:
                self.selected_date = bar_date
                self.refresh()
                return

    def auto_refresh(self):
        self.refresh()
        self.auto_refresh_job = self.window.after(30_000, self.auto_refresh)

    def refresh(self):
        if not os.path.exists(self.db_path):
            self.total.config(text="—")
            return
        try:
            conn = open_db_readonly(self.db_path)
            today = date.today()
            days_since_sunday = (today.weekday() + 1) % 7
            current_sunday = today - timedelta(days=days_since_sunday)

            start_date = current_sunday - timedelta(weeks=self.week_offset)
            end_date = start_date + timedelta(days=6)

            try:
                total = query_daily_total(conn, self.selected_date)
                top = query_top_apps(conn, self.selected_date)
                weekly = query_daily_totals_range(conn, start_date, end_date)
            finally:
                conn.close()
        except sqlite3.Error:
            return

        self.total.config(text=format_duration(total))

        if self.selected_date == date.today():
            self.date_lbl.config(text="Today", fg=MUTED)
            self.apps_title.config(text="Top Applications Today")
        else:
            self.date_lbl.config(text=self.selected_date.strftime("%A, %b %d"), fg=ACCENT)
            self.apps_title.config(text=f"Top Applications on {self.selected_date.strftime('%b %d')}")

        if self.week_offset == 0:
            self.chart_title.config(text="This Week (Sun - Sat)")
        else:
            self.chart_title.config(text=f"Week of {start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}")

        self.draw_bars(top, total)
        self.draw_weekly(weekly, start_date)
        self.status.config(text=f"Updated {datetime.now():%H:%M:%S}")

    def draw_bars(self, data, total=0):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not data:
            tk.Label(self.scrollable_frame, text="No activity recorded for this day", bg=BG, fg=MUTED, font=(FONT_MAIN, 11)).pack(pady=40)
            return

        mx = max(v for _, v in data) or 1
        for i, (app, dur) in enumerate(data):
            row = AppRow(self.scrollable_frame, app, dur, mx, i, total=total)
            row.pack(fill="x", pady=4)

    def draw_weekly(self, data, start_date):
        c = self.weekly
        c.delete("all")
        c.update_idletasks()
        self.weekly_bars = []

        width = c.winfo_width()
        if width < 100:
            width = 780

        days = [start_date + timedelta(days=i) for i in range(7)]
        values = {d.isoformat(): 0 for d in days}
        for day, secs in data:
            if day in values:
                values[day] = secs
        mx = max(values.values()) or 1
        cw = width / len(days)
        bw = min(cw * 0.45, 38)

        yb = 100
        c.create_line(15, yb, width - 15, yb, fill=CARD_BORDER, width=1)

        for i, d in enumerate(days):
            x = i * cw + (cw - bw) / 2
            secs = values[d.isoformat()]
            is_selected = (d == self.selected_date)
            is_today = (d == date.today())

            if is_selected:
                fill_color, text_color, font_style = ACCENT, "#FFFFFF", (FONT_MAIN, 9, "bold")
            elif is_today:
                fill_color, text_color, font_style = FG, FG, (FONT_MAIN, 9, "bold")
            else:
                fill_color, text_color, font_style = TRACK_BG, MUTED, (FONT_MAIN, 9)

            if secs == 0:
                c.create_oval(x + bw/2 - 3, yb - 3, x + bw/2 + 3, yb + 3, fill=CARD_BORDER, outline="")
            else:
                h = max(int(65 * (secs / mx)), 8)
                round_rect(c, x, yb - h, x + bw, yb, 6, fill_color)

            c.create_text(x + bw/2, yb + 16, text=d.strftime("%a"), fill=text_color, font=font_style)
            if secs > 0:
                c.create_text(x + bw/2, yb - h - 12, text=format_duration(secs, short=True), fill=text_color, font=(FONT_MAIN, 8, "bold" if is_selected else "normal"))

            self.weekly_bars.append((x - 4, 0, x + bw + 4, yb + 25, d))

def open_dashboard(parent, db_path: str, dash_ref=None):
    """Opens or raises the Screen Time Analytics dashboard."""
    if parent:
        if dash_ref and dash_ref[0] is not None and dash_ref[0].winfo_exists():
            dash_ref[0].lift()
            dash_ref[0].focus_force()
            return
        window = tk.Toplevel(parent)
        Dashboard(window, db_path)
        if dash_ref is not None:
            dash_ref[0] = window
    else:
        window = tk.Tk()
        Dashboard(window, db_path)
        window.mainloop()
