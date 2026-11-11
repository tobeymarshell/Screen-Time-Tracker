"""Desktop Widget with embedded wallpaper mode, drag support, and system boost."""

import ctypes
from ctypes import wintypes
from datetime import date
import hashlib
import os
from pathlib import Path
import sqlite3
import threading
import time
import tkinter as tk

from ..optimizer import run_system_cleanup
from ..storage import (
    load_pos,
    save_pos,
    open_db_readonly,
    query_daily_total,
    query_top_apps,
)
from ..win32 import (
    user32,
    gdi32,
    is_foreground_fullscreen,
)
from .theme import (
    BG,
    CARD_BG,
    CARD_BORDER,
    HOVER_BG,
    FG,
    MUTED,
    MUTED_DARK,
    ACCENT,
    SUCCESS,
    COLORS,
    FONT_MAIN,
    round_rect,
    format_app_name,
    format_duration,
    format_bytes,
)
from .dashboard import open_dashboard

class DesktopWidget:
    W, H = 290, 195
    MARGIN = 24
    DATA_REFRESH_MS = 5000
    VIS_REFRESH_MS = 200

    def __init__(self, root: tk.Tk, db_path: Path, force_pinned: bool = False):
        self.root, self.db_path = root, str(db_path)
        self._hidden = False
        self.embedded = False
        self.hwnd = None
        self.drag_x = 0
        self.drag_y = 0
        self.cleanup_popup = None
        self.dash_ref = [None]

        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", False)
        root.configure(bg=BG)
        root.geometry(f"{self.W}x{self.H}")

        self.card = tk.Frame(root, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
        self.card.pack(fill="both", expand=True)
        self._build()
        root.update_idletasks()

        self.hwnd = user32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()
        user32.ShowWindow(self.hwnd, 0)

        if force_pinned:
            self._pin_top_right()
        else:
            self._embed_desktop()

        self.refresh_data()
        self._tick_data()
        self._tick_visibility()

    def _build(self):
        header = tk.Frame(self.card, bg=CARD_BG)
        header.pack(fill="x", padx=14, pady=(10, 0))

        title_frame = tk.Frame(header, bg=CARD_BG)
        title_frame.pack(side="left")
        tk.Label(title_frame, text="●", bg=CARD_BG, fg=ACCENT, font=(FONT_MAIN, 8)).pack(side="left", padx=(0, 5))
        title_lbl = tk.Label(title_frame, text="Screen Time", font=(FONT_MAIN, 11, "bold"), bg=CARD_BG, fg=FG)
        title_lbl.pack(side="left")

        self.btn_frame = tk.Frame(header, bg=CARD_BG)
        self.btn_frame.pack(side="right")
        for txt, cmd, tip in [("⚡", self.do_cleanup, "Boost CPU, RAM & Clean Temp"),
                              ("↻", self.refresh_data, "Refresh"),
                              ("↗", self.open_dashboard, "Dashboard")]:
            b = tk.Button(self.btn_frame, text=txt, command=cmd, bg=CARD_BG, fg=MUTED, relief="flat",
                          bd=0, activebackground=HOVER_BG, activeforeground=FG,
                          font=(FONT_MAIN, 10, "bold"), padx=5, pady=1, cursor="hand2",
                          highlightthickness=0)
            b.pack(side="left", padx=1)
            b.bind("<Enter>", lambda e, btn=b: btn.config(bg=HOVER_BG, fg=FG))
            b.bind("<Leave>", lambda e, btn=b: btn.config(bg=CARD_BG, fg=MUTED))

        self.total_lbl = tk.Label(self.card, text="—", font=(FONT_MAIN, 30, "bold"), bg=CARD_BG, fg=FG)
        self.total_lbl.pack(pady=(2, 0))
        tk.Label(self.card, text="TODAY'S USAGE", font=(FONT_MAIN, 8, "bold"), bg=CARD_BG, fg=MUTED_DARK).pack(pady=(0, 6))

        self.top_frame = tk.Frame(self.card, bg=CARD_BG)
        self.top_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.app_rows = []
        for _ in range(4):
            row = tk.Frame(self.top_frame, bg=CARD_BG)
            row.pack(fill="x", pady=2)

            icon_canvas = tk.Canvas(row, bg=CARD_BG, width=20, height=20, highlightthickness=0)
            icon_canvas.pack(side="left", padx=(0, 8))

            name_lbl = tk.Label(row, text="", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 9, "bold"), anchor="w")
            name_lbl.pack(side="left")

            dur_lbl = tk.Label(row, text="", bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 9))
            dur_lbl.pack(side="right")

            self.app_rows.append((icon_canvas, name_lbl, dur_lbl))

        def start_drag(e):
            if self.embedded:
                rect = wintypes.RECT()
                user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
                self.drag_x = self.root.winfo_pointerx() - rect.left
                self.drag_y = self.root.winfo_pointery() - rect.top
            else:
                self.drag_x = self.root.winfo_pointerx() - self.root.winfo_x()
                self.drag_y = self.root.winfo_pointery() - self.root.winfo_y()

        def do_drag(e):
            nx = self.root.winfo_pointerx() - self.drag_x
            ny = self.root.winfo_pointery() - self.drag_y
            if self.embedded:
                user32.SetWindowPos(self.hwnd, 0, nx, ny, self.W, self.H, 0x0004 | 0x0010)
            else:
                self.root.geometry(f"+{nx}+{ny}")

        def stop_drag(e):
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            if self.embedded:
                rect = wintypes.RECT()
                user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
                x, y = rect.left, rect.top
            save_pos(x, y)

        for drag_target in (header, title_frame, title_lbl):
            drag_target.bind("<ButtonPress-1>", start_drag)
            drag_target.bind("<B1-Motion>", do_drag)
            drag_target.bind("<ButtonRelease-1>", stop_drag)

        def bind_all(w):
            w.bind("<Button-3>", self._popup)
            for ch in w.winfo_children():
                bind_all(ch)
        bind_all(self.card)

    def show_popup(self, ram_str: str, disk_str: str, closed_apps: list, cpu_throttled: int = 0):
        if self.cleanup_popup:
            try:
                self.cleanup_popup.destroy()
            except Exception:
                pass
        base_height = 80
        app_list_height = min(len(closed_apps) * 18, 72) if closed_apps else 0
        total_height = base_height + app_list_height

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
        px = self.root.winfo_x()
        py = max(20, self.root.winfo_y() - total_height - 12)
        popup.geometry(f"330x{total_height}+{px}+{py}")

        head = tk.Frame(popup, bg=CARD_BG)
        head.pack(fill="x", padx=14, pady=(10, 2))
        title_text = "⚡ System RAM & CPU Boosted" if cpu_throttled else "⚡ System Memory Optimized"
        tk.Label(head, text=title_text, bg=CARD_BG, fg=SUCCESS, font=(FONT_MAIN, 11, "bold")).pack(side="left")

        stats_text = f"RAM: {ram_str}  •  Disk: {disk_str}" + (f"  •  CPU Offloaded: {cpu_throttled} apps" if cpu_throttled else "")
        stats = tk.Label(popup, text=stats_text, bg=CARD_BG, fg=FG, font=(FONT_MAIN, 9))
        stats.pack(anchor="w", padx=14, pady=(0, 4))

        if closed_apps:
            tk.Frame(popup, bg=CARD_BORDER, height=1).pack(fill="x", padx=14, pady=3)
            for app in closed_apps[:3]:
                tk.Label(popup, text=f"• Closed {app} (Prompted to save)", bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 8)).pack(anchor="w", padx=18)
            if len(closed_apps) > 3:
                tk.Label(popup, text=f"...and {len(closed_apps)-3} more", bg=CARD_BG, fg=MUTED_DARK, font=(FONT_MAIN, 8, "italic")).pack(anchor="w", padx=18)

        self.cleanup_popup = popup
        self.root.after(4500, lambda: popup.destroy() if popup.winfo_exists() else None)

    def do_cleanup(self):
        for child in self.btn_frame.winfo_children():
            if child.cget("text") in ("⚡", "✅"):
                child.config(text="✅", fg=SUCCESS)
                self.root.after(2000, lambda: child.config(text="⚡", fg=MUTED))
                break
        threading.Thread(target=self._run_cleanup_async, daemon=True).start()

    def _run_cleanup_async(self):
        ram_freed, freed_disk, cpu_offloaded = run_system_cleanup()
        self.root.after(0, lambda: self.show_popup(format_bytes(ram_freed), format_bytes(freed_disk), [], cpu_throttled=cpu_offloaded))

    def _pin_top_right(self):
        sw = self.root.winfo_screenwidth()
        saved_x, saved_y = load_pos()
        x = saved_x if saved_x is not None else sw - self.W - self.MARGIN
        y = saved_y if saved_y is not None else 150
        self.root.geometry(f"+{x}+{y}")
        self.embedded = False
        user32.SetWindowPos(self.hwnd, 0, x, y, self.W, self.H, 0x0040)
        self.root.deiconify()
        self.root.attributes("-alpha", 0.95)

    def _embed_desktop(self):
        GWL_STYLE = -16
        WS_POPUP = 0x80000000
        WS_CHILD = 0x40000000
        WS_VISIBLE = 0x10000000
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020

        for _ in range(5):
            try:
                progman = user32.FindWindowW("Progman", None)
                if progman:
                    res = ctypes.c_size_t()
                    user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(res))

                    target = [0]
                    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    def cb(h, _):
                        if user32.FindWindowExW(h, 0, "SHELLDLL_DefView", None):
                            w = user32.FindWindowExW(0, h, "WorkerW", None)
                            if w:
                                target[0] = w
                        return True
                    user32.EnumWindows(EnumProc(cb), 0)
                    parent = target[0] or progman

                    style = user32.GetWindowLongW(self.hwnd, GWL_STYLE) & 0xFFFFFFFF
                    new_style = (style | WS_CHILD | WS_VISIBLE) & ~WS_POPUP
                    user32.SetWindowLongW(self.hwnd, GWL_STYLE, ctypes.c_long(new_style & 0xFFFFFFFF).value)

                    if user32.SetParent(self.hwnd, parent):
                        sw = user32.GetSystemMetrics(0)
                        saved_x, saved_y = load_pos()
                        x = saved_x if saved_x is not None else sw - self.W - self.MARGIN
                        y = saved_y if saved_y is not None else 150

                        user32.SetWindowPos(self.hwnd, 0, x, y, self.W, self.H,
                                            SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | 0x0040)

                        rgn = gdi32.CreateRoundRectRgn(0, 0, self.W + 1, self.H + 1, 20, 20)
                        user32.SetWindowRgn(self.hwnd, rgn, True)

                        self.root.attributes("-alpha", 0.95)
                        self.embedded = True
                        return
            except Exception:
                pass
            time.sleep(0.1)
        self._pin_top_right()

    def _popup(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=CARD_BG, fg=FG, activebackground=ACCENT, activeforeground="#FFFFFF")
        m.add_command(label="⚡ Boost CPU, RAM & Clean Temp", command=self.do_cleanup)
        m.add_command(label="↻ Refresh Data", command=self.refresh_data)
        m.add_command(label="↗ Open Dashboard", command=self.open_dashboard)
        m.add_separator()
        m.add_command(label="✕ Quit", command=self.quit)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def open_dashboard(self):
        open_dashboard(self.root, self.db_path, self.dash_ref)

    def quit(self):
        self.root.destroy()

    def refresh_data(self):
        if not os.path.exists(self.db_path):
            self.total_lbl.config(text="—")
            for icon_canvas, name_lbl, dur_lbl in self.app_rows:
                icon_canvas.delete("all")
                name_lbl.config(text="")
                dur_lbl.config(text="")
            return
        try:
            conn = open_db_readonly(self.db_path)
            try:
                total = query_daily_total(conn, date.today())
                top = query_top_apps(conn, date.today())
            finally:
                conn.close()
        except sqlite3.Error:
            return

        self.total_lbl.config(text=format_duration(total))
        top_4 = top[:4]
        for i, (icon_canvas, name_lbl, dur_lbl) in enumerate(self.app_rows):
            icon_canvas.delete("all")
            if i < len(top_4):
                app, dur = top_4[i]
                clean_name = format_app_name(app)

                color_idx = int(hashlib.md5(app.encode()).hexdigest(), 16) % len(COLORS)
                bg_color = COLORS[color_idx]
                letter = clean_name[0].upper() if clean_name else "?"

                round_rect(icon_canvas, 0, 0, 20, 20, 6, bg_color)
                icon_canvas.create_text(10, 10, text=letter, fill="#FFFFFF", font=(FONT_MAIN, 9, "bold"))

                display = clean_name if len(clean_name) <= 15 else clean_name[:13] + "…"
                name_lbl.config(text=display)
                dur_lbl.config(text=format_duration(dur))
            else:
                name_lbl.config(text="")
                dur_lbl.config(text="")

    def _tick_data(self):
        try:
            self.refresh_data()
        finally:
            self.root.after(self.DATA_REFRESH_MS, self._tick_data)

    def _tick_visibility(self):
        try:
            should_hide = is_foreground_fullscreen()
            if should_hide and not self._hidden:
                if self.embedded and self.hwnd:
                    user32.ShowWindow(self.hwnd, 0)
                else:
                    self.root.withdraw()
                self._hidden = True
            elif not should_hide and self._hidden:
                if self.embedded and self.hwnd:
                    user32.ShowWindow(self.hwnd, 4)
                else:
                    self.root.deiconify()
                self._hidden = False
        finally:
            self.root.after(self.VIS_REFRESH_MS, self._tick_visibility)

def open_widget(db_path: Path, force_pinned: bool = False):
    """Initializes and runs the desktop widget main loop."""
    root = tk.Tk()
    DesktopWidget(root, db_path, force_pinned=force_pinned)
    root.mainloop()
