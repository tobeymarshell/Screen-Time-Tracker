import ctypes
from ctypes import wintypes
import os, sys, time, sqlite3, argparse, threading, subprocess, json, shutil, hashlib
from datetime import datetime, timedelta, date
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import winreg  # NEW: Used for self-installing to startup

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi    = ctypes.windll.psapi
shell32  = ctypes.windll.shell32

# ── signatures ──
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]; user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]; user32.FindWindowExW.restype = wintypes.HWND
user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]; user32.SetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]; user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]; user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]; user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]; user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsZoomed.argtypes = [wintypes.HWND]; user32.IsZoomed.restype = wintypes.BOOL
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]; user32.GetAncestor.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_size_t
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetTickCount.restype = wintypes.DWORD
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]; kernel32.CreateMutexW.restype = wintypes.HANDLE

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]

class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]
shell32.SHQueryRecycleBinW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(SHQUERYRBINFO)]
shell32.SHQueryRecycleBinW.restype = ctypes.c_long
shell32.SHEmptyRecycleBinW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
shell32.SHEmptyRecycleBinW.restype = ctypes.c_long

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ALREADY_EXISTS = 183

# ─────────── Theme Colors ───────────
BG        = "#11111b" 
CARD_BG   = "#181825" 
FG        = "#cdd6f4" 
ACCENT    = "#89b4fa" 
MUTED     = "#6c7086" 
TRACK_BG  = "#313244" 
COLORS    = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7", "#94e2d5", "#fab387", "#f5c2e7"]

FONT_MAIN = "Segoe UI Variable Display"

# ─────────── helpers ───────────
def data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    p = Path(base) / "ScreenTimeTracker"; p.mkdir(parents=True, exist_ok=True); return p

def get_db_path(): return data_dir() / "tracker.db"

def load_pos():
    try:
        with open(data_dir() / "pos.json", "r") as f:
            d = json.load(f)
            return int(d.get("x")), int(d.get("y"))
    except Exception: return None, None

def save_pos(x, y):
    try:
        with open(data_dir() / "pos.json", "w") as f:
            json.dump({"x": int(x), "y": int(y)}, f)
    except Exception: pass

def log(msg):
    try:
        if sys.stdout is not None: print(msg, flush=True)
    except Exception: pass

def format_duration(seconds, short=False):
    seconds = max(0, int(seconds)); h, m = seconds // 3600, (seconds % 3600) // 60
    if h > 0: return f"{h}h {m}m" if not short else f"{h}h{m:02d}"
    return f"{m}m"

def format_bytes(b):
    if b < 1024 * 1024: return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024: return f"{b / (1024 * 1024):.1f} MB"
    else: return f"{b / (1024 * 1024 * 1024):.2f} GB"

def try_acquire_mutex(name):
    h = kernel32.CreateMutexW(None, True, name)
    if not h: return None
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(h); return None
    return h

# ─────────── DB & Queries ───────────
def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, app_name TEXT NOT NULL,
        window_title TEXT, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time)")
    conn.commit()

def save_session(conn, app, title, start, end):
    dur = int(end - start)
    if dur < 1 or not app: return
    conn.execute("INSERT INTO sessions (app_name, window_title, start_time, end_time, duration_seconds) VALUES (?,?,?,?,?)",
        (app, title or "", datetime.fromtimestamp(start).isoformat(timespec="seconds"),
         datetime.fromtimestamp(end).isoformat(timespec="seconds"), dur))
    conn.commit()

def run_tracker(db_path, idle_threshold=60, poll_interval=1.0, stop_event=None):
    conn = sqlite3.connect(str(db_path)); init_db(conn)
    current_app, current_title, session_start = None, "", None
    try:
        while stop_event is None or not stop_event.is_set():
            now, idle = time.time(), get_idle_seconds()
            if idle >= idle_threshold:
                if current_app and session_start is not None:
                    idle_began = now - idle
                    if idle_began > session_start:
                        save_session(conn, current_app, current_title, session_start, idle_began)
                current_app, session_start = None, None
            else:
                hwnd = user32.GetForegroundWindow()
                class_name = ctypes.create_unicode_buffer(256)
                if hwnd: user32.GetClassNameW(hwnd, class_name, 256)
                if class_name.value in ("Progman", "WorkerW"):
                    app, title = "Desktop", "Home Screen"
                else:
                    app, title = get_foreground_process_name(), get_foreground_window_title()

                if app != current_app:
                    if current_app and session_start is not None:
                        save_session(conn, current_app, current_title, session_start, now)
                    current_app, current_title, session_start = app, title, now
                else: current_title = title
            time.sleep(poll_interval)
    except KeyboardInterrupt: pass
    finally:
        if current_app and session_start is not None:
            save_session(conn, current_app, current_title, session_start, time.time())
        conn.close()

def query_daily_total(conn, target_date):
    return conn.execute("SELECT COALESCE(SUM(duration_seconds),0) FROM sessions WHERE substr(start_time,1,10) = ?",
                        (target_date.isoformat(),)).fetchone()[0]

def query_top_apps(conn, target_date):
    return conn.execute("SELECT app_name, SUM(duration_seconds) AS total FROM sessions "
                        "WHERE substr(start_time,1,10) = ? GROUP BY app_name ORDER BY total DESC",
                        (target_date.isoformat(),)).fetchall()

def query_daily_totals_range(conn, start_date, end_date):
    return conn.execute("SELECT substr(start_time,1,10) AS day, SUM(duration_seconds) FROM sessions "
                        "WHERE substr(start_time,1,10) >= ? AND substr(start_time,1,10) <= ? "
                        "GROUP BY day ORDER BY day", (start_date.isoformat(), end_date.isoformat())).fetchall()

def open_db_readonly(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)

def get_idle_seconds():
    lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(lii)): return 0.0
    return ((kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0

def get_foreground_process_name():
    hwnd = user32.GetForegroundWindow()
    if not hwnd: return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value: return None
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h: return None
    try:
        buf = ctypes.create_unicode_buffer(1024); size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally: kernel32.CloseHandle(h)
    return None

def get_foreground_window_title():
    hwnd = user32.GetForegroundWindow()
    if not hwnd: return ""
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0: return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value

def is_foreground_fullscreen():
    hwnd = user32.GetForegroundWindow()
    if not hwnd: return False
    class_name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_name, 256)
    if class_name.value in ("Progman", "WorkerW", "Shell_TrayWnd"): return False
    if user32.IsZoomed(hwnd): return False
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)): return False
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh

# ─────────── Dashboard ───────────
class Dashboard:
    def __init__(self, window, db_path):
        self.window, self.db_path = window, str(db_path)
        self.selected_date = date.today()
        self.week_offset = 0 
        self.weekly_bars = [] 

        self.window.title("Screen Time Tracker")
        self.window.geometry("800x750")
        self.window.configure(bg=BG); self.window.minsize(700, 650)
        self.window.attributes("-topmost", True); self.window.after(100, lambda: self.window.attributes("-topmost", False))
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar", gripcount=0, background=TRACK_BG, darkcolor=CARD_BG, lightcolor=CARD_BG, troughcolor=BG, bordercolor=BG, arrowcolor=FG, width=10)
        style.map("Vertical.TScrollbar", background=[('active', MUTED)])

        header_frame = tk.Frame(self.window, bg=BG)
        header_frame.pack(fill="x", padx=30, pady=(20, 0)) 
        
        self.date_lbl = tk.Label(header_frame, text="Today", font=(FONT_MAIN, 14, "bold"), bg=BG, fg=MUTED)
        self.date_lbl.pack()
        
        self.total = tk.Label(header_frame, text="—", font=(FONT_MAIN, 44, "bold"), bg=BG, fg=ACCENT)
        self.total.pack()

        self.chart_title = tk.Label(self.window, text="This Week (Sun - Sat)", font=(FONT_MAIN, 12, "bold"), bg=BG, fg=FG, anchor="w")
        self.chart_title.pack(fill="x", padx=30, pady=(15, 0))

        chart_container = tk.Frame(self.window, bg=BG)
        chart_container.pack(fill="x", padx=20) 
        
        btn_left = tk.Button(chart_container, text="<", command=self.prev_week, bg=TRACK_BG, fg=FG, relief="flat", padx=10, pady=10, font=(FONT_MAIN, 12, "bold"), activebackground=ACCENT)
        btn_left.pack(side="left", padx=(10, 0))
        
        self.weekly = tk.Canvas(chart_container, bg=BG, highlightthickness=0, height=130)
        self.weekly.pack(side="left", fill="x", expand=True, padx=10)
        self.weekly.bind("<Button-1>", self.on_weekly_click)
        
        btn_right = tk.Button(chart_container, text=">", command=self.next_week, bg=TRACK_BG, fg=FG, relief="flat", padx=10, pady=10, font=(FONT_MAIN, 12, "bold"), activebackground=ACCENT)
        btn_right.pack(side="right", padx=(0, 10))

        footer = tk.Frame(self.window, bg=BG)
        footer.pack(side="bottom", fill="x", padx=30, pady=15)
        
        self.status = tk.Label(footer, text="", font=(FONT_MAIN, 10), bg=BG, fg=MUTED, anchor="w")
        self.status.pack(side="left")
        
        btn_frame = tk.Frame(footer, bg=BG); btn_frame.pack(side="right")
        tk.Button(btn_frame, text="Today", command=self.go_today, bg=TRACK_BG, fg=ACCENT, relief="flat", padx=15, pady=5, font=(FONT_MAIN, 10, "bold")).pack(side="left", padx=8)
        tk.Button(btn_frame, text="Refresh", command=self.refresh, bg=TRACK_BG, fg=FG, relief="flat", padx=15, pady=5, activebackground=ACCENT, activeforeground=BG, font=(FONT_MAIN, 10)).pack(side="left")

        self.apps_title = tk.Label(self.window, text="Top Apps", font=(FONT_MAIN, 16, "bold"), bg=BG, fg=FG, anchor="w")
        self.apps_title.pack(fill="x", padx=30, pady=(15, 5))

        list_frame = tk.Frame(self.window, bg=BG)
        list_frame.pack(side="top", fill="both", expand=True, padx=30, pady=(0, 10))
        
        self.canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.window.after(100, self.refresh)
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
        self.refresh()

    def next_week(self):
        if self.week_offset > 0:
            self.week_offset -= 1
            self.refresh()

    def on_weekly_click(self, event):
        for x1, y1, x2, y2, bar_date in self.weekly_bars:
            if x1 <= event.x <= x2 and 0 <= event.y <= 130:
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
            finally: conn.close()
        except sqlite3.Error: return
        
        self.total.config(text=format_duration(total))
        
        if self.selected_date == date.today():
            self.date_lbl.config(text="Today", fg=MUTED)
            self.apps_title.config(text="Top Apps Today")
        else:
            self.date_lbl.config(text=self.selected_date.strftime("%A, %b %d"), fg=ACCENT)
            self.apps_title.config(text=f"Top Apps on {self.selected_date.strftime('%b %d')}")
            
        if self.week_offset == 0:
            self.chart_title.config(text="This Week (Sun - Sat)")
        else:
            self.chart_title.config(text=f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}")
            
        self.draw_bars(top); 
        self.draw_weekly(weekly, start_date)
        self.status.config(text=f"Updated {datetime.now():%H:%M:%S}")

    def draw_bars(self, data):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        if not data:
            tk.Label(self.scrollable_frame, text="No activity recorded for this day", bg=BG, fg=MUTED, font=(FONT_MAIN, 12)).pack(pady=30)
            return
            
        mx = max(v for _, v in data) or 1
        
        for i, (app, dur) in enumerate(data):
            row = tk.Frame(self.scrollable_frame, bg=BG, pady=4)
            row.pack(fill="x")
            
            color_idx = int(hashlib.md5(app.encode()).hexdigest(), 16) % len(COLORS)
            bg_color = COLORS[color_idx]
            letter = app[0].upper() if app else "?"
            
            icon_canvas = tk.Canvas(row, bg=BG, width=24, height=24, highlightthickness=0)
            icon_canvas.pack(side="left", padx=(0, 10))
            icon_canvas.create_oval(0, 0, 24, 24, fill=bg_color, outline="")
            icon_canvas.create_text(12, 12, text=letter, fill=BG, font=(FONT_MAIN, 10, "bold"))
            
            display_name = app if len(app) <= 22 else app[:20] + "…"
            tk.Label(row, text=display_name, bg=BG, fg=FG, font=(FONT_MAIN, 11), width=24, anchor="w").pack(side="left")
            
            tk.Label(row, text=format_duration(dur), bg=BG, fg=MUTED, font=(FONT_MAIN, 10)).pack(side="right", padx=(10, 0))
            
            canvas_bar = tk.Canvas(row, bg=BG, height=20, highlightthickness=0)
            canvas_bar.pack(side="left", fill="x", expand=True, padx=10)
            self.window.after(10, lambda c=canvas_bar, d=dur, m=mx, idx=i: self.draw_single_bar(c, d, m, idx))

    def draw_single_bar(self, canvas, dur, mx, idx):
        canvas.delete("all")
        w = canvas.winfo_width()
        if w < 10: w = 300
        bw = max(int((w - 10) * dur / mx), 4)
        
        canvas.create_rectangle(0, 4, w, 16, fill=TRACK_BG, outline="")
        canvas.create_rectangle(0, 4, bw, 16, fill=COLORS[idx % len(COLORS)], outline="")

    def draw_weekly(self, data, start_date):
        c = self.weekly; c.delete("all"); c.update_idletasks()
        self.weekly_bars = [] 
        
        width = c.winfo_width()
        if width < 100: width = 600 
        
        days = [start_date + timedelta(days=i) for i in range(7)]
        
        values = {d.isoformat(): 0 for d in days}
        for day, secs in data:
            if day in values: values[day] = secs
        mx = max(values.values()) or 1; cw = width / len(days); bw = cw * 0.5
        
        for i, d in enumerate(days):
            x = i * cw + (cw - bw) / 2; secs = values[d.isoformat()]
            h = int(70 * secs / mx); yb = 95
            
            if d == self.selected_date:
                color, text_color, font_style = ACCENT, FG, (FONT_MAIN, 10, "bold")
            elif d == date.today():
                color, text_color, font_style = ACCENT, FG, (FONT_MAIN, 9, "bold")
            else:
                color, text_color, font_style = TRACK_BG, MUTED, (FONT_MAIN, 9)

            c.create_rectangle(x, yb - h, x + bw, yb, fill=color, outline="")
            c.create_text(x + bw/2, yb + 18, text=d.strftime("%a"), fill=text_color, font=font_style)
            c.create_text(x + bw/2, yb - h - 12, text=format_duration(secs, short=True), fill=text_color, font=(FONT_MAIN, 8))
            
            self.weekly_bars.append((x, 0, x + bw, yb, d))

def open_dashboard(parent, db_path, dash_ref=None):
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

# ─────────── Desktop Widget ───────────
class DesktopWidget:
    W, H = 280, 180 
    MARGIN = 24
    DATA_REFRESH_MS = 5000   
    VIS_REFRESH_MS = 200     

    def __init__(self, root, db_path, force_pinned=False):
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

        self.card = tk.Frame(root, bg=CARD_BG, highlightthickness=1, highlightbackground=TRACK_BG)
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
        header = tk.Frame(self.card, bg=CARD_BG); header.pack(fill="x", padx=15, pady=(12, 0))
        title_lbl = tk.Label(header, text="Screen Time", font=(FONT_MAIN, 11, "bold"), bg=CARD_BG, fg=FG)
        title_lbl.pack(side="left")
        
        btns = tk.Frame(header, bg=CARD_BG); btns.pack(side="right")
        for txt, cmd in [("🚀", self.do_cleanup), ("⟳", self.refresh_data), ("⤢", self.open_dashboard)]:
            tk.Button(btns, text=txt, command=cmd, bg=CARD_BG, fg=MUTED, relief="flat",
                      bd=0, activebackground=TRACK_BG, activeforeground=FG,
                      font=(FONT_MAIN, 11), padx=4, pady=0, cursor="hand2", 
                      highlightthickness=0).pack(side="left")

        self.total_lbl = tk.Label(self.card, text="—", font=(FONT_MAIN, 30, "bold"), bg=CARD_BG, fg=ACCENT)
        self.total_lbl.pack()
        tk.Label(self.card, text="today", font=(FONT_MAIN, 9), bg=CARD_BG, fg=MUTED).pack(pady=(0, 8))

        self.top_frame = tk.Frame(self.card, bg=CARD_BG)
        self.top_frame.pack(fill="both", expand=True, padx=15, pady=(0, 12))

        self.app_rows = []
        for _ in range(4): 
            row = tk.Frame(self.top_frame, bg=CARD_BG); row.pack(fill="x", pady=2)
            
            icon_lbl = tk.Label(row, bg=CARD_BG)
            icon_lbl.pack(side="left", padx=(0, 8))
            
            name_lbl = tk.Label(row, text="", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 9), anchor="w")
            name_lbl.pack(side="left")
            
            dur_lbl = tk.Label(row, text="", bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 9))
            dur_lbl.pack(side="right")
            
            self.app_rows.append((icon_lbl, name_lbl, dur_lbl))

        def start_drag(e):
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
            x = self.root.winfo_x(); y = self.root.winfo_y()
            if self.embedded:
                rect = wintypes.RECT()
                user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
                x, y = rect.left, rect.top
            save_pos(x, y)

        header.bind("<ButtonPress-1>", start_drag)
        header.bind("<B1-Motion>", do_drag)
        header.bind("<ButtonRelease-1>", stop_drag)
        title_lbl.bind("<ButtonPress-1>", start_drag)
        title_lbl.bind("<B1-Motion>", do_drag)
        title_lbl.bind("<ButtonRelease-1>", stop_drag)

        def bind_all(w):
            w.bind("<Button-3>", self._popup)
            for ch in w.winfo_children(): bind_all(ch)
        bind_all(self.card)

    def show_popup(self, ram_str, disk_str, closed_apps):
        if self.cleanup_popup: self.cleanup_popup.destroy()
        base_height = 75; app_list_height = min(len(closed_apps) * 18, 80) if closed_apps else 0
        total_height = base_height + app_list_height

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True); popup.attributes("-topmost", True) 
        popup.configure(bg=CARD_BG, highlightthickness=1, highlightbackground=ACCENT)
        px = self.root.winfo_x(); py = self.root.winfo_y() - total_height - 15
        popup.geometry(f"320x{total_height}+{px}+{py}")
        
        tk.Label(popup, text="✅ System Optimized", bg=CARD_BG, fg="#a6e3a1", font=(FONT_MAIN, 11, "bold")).pack(pady=(8, 2))
        tk.Label(popup, text=f"RAM Freed: {ram_str}  |  Disk Freed: {disk_str}", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 9)).pack()

        if closed_apps:
            tk.Frame(popup, bg=TRACK_BG, height=1).pack(fill="x", padx=20, pady=4)
            for app in closed_apps[:4]:
                tk.Label(popup, text=f"• Closed: {app}", bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 8)).pack(anchor="w", padx=30)
            if len(closed_apps) > 4:
                tk.Label(popup, text=f"...and {len(closed_apps)-4} more", bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 8, "italic")).pack(anchor="w", padx=30)

        self.cleanup_popup = popup; self.root.after(5000, popup.destroy)

    def do_cleanup(self):
        for child in self.card.winfo_children()[0].winfo_children()[1].winfo_children():
            if child.cget("text") == "🚀":
                child.config(text="✅", fg="#a6e3a1")
                self.root.after(2500, lambda: child.config(text="🚀", fg=MUTED))
                break

        ram_before = psutil.virtual_memory().available
        freed_disk = 0; closed_apps = []
        
        temp_dir = os.environ.get('TEMP')
        if temp_dir and os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                try:
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isdir(item_path):
                        for root_dir, _, files in os.walk(item_path):
                            for f in files:
                                try: freed_disk += os.path.getsize(os.path.join(root_dir, f))
                                except: pass
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        freed_disk += os.path.getsize(item_path); os.remove(item_path)
                except Exception: pass

        try:
            rb_info = SHQUERYRBINFO(); rb_info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
            if shell32.SHQueryRecycleBinW(None, ctypes.byref(rb_info)) == 0: freed_disk += rb_info.i64Size
            shell32.SHEmptyRecycleBinW(None, None, 7)
        except Exception: pass

        try: subprocess.Popen(["ipconfig", "/flushdns"], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception: pass

        try:
            current_pid = os.getpid()
            ignore_procs = {"explorer.exe", "dwm.exe", "textinputhost.exe", "startmenuexperiencehost.exe",
                            "searchhost.exe", "shellexperiencehost.exe", "runtimebroker.exe", 
                            "python.exe", "pythonw.exe", "screentime.exe"}

            def enum_cb(hwnd, lParam):
                if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) == 0: return True
                class_name = ctypes.create_unicode_buffer(256); user32.GetClassNameW(hwnd, class_name, 256)
                if class_name.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"): return True

                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == current_pid: return True

                h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                if h_process:
                    try:
                        buf = ctypes.create_unicode_buffer(1024); size = wintypes.DWORD(1024)
                        if kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                            proc_name = os.path.basename(buf.value).lower()
                            if proc_name in ignore_procs: return True
                            if proc_name not in closed_apps: closed_apps.append(proc_name)
                    finally: kernel32.CloseHandle(h_process)
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
                return True
            user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(enum_cb), 0)
        except Exception: pass

        try:
            kill_list = ["whatsapp.exe", "telegram.exe", "discord.exe", "slack.exe", "zoom.exe",
                         "wiztree.exe", "wiztree64.exe", "crystaldiskinfo.exe", "onedrive.exe", 
                         "dropbox.exe", "googlebackupandsync.exe", "spotify.exe", "itunes.exe", 
                         "skypeapp.exe", "teams.exe", "yourphone.exe", "gamebar.exe", "widgetservice.exe", 
                         "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "battle.net.exe", 
                         "origin.exe", "msedgewebview2.exe"]
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.pid != os.getpid(): 
                        handle = kernel32.OpenProcess(0x0100 | 0x0400, False, proc.pid)
                        if handle:
                            psapi.EmptyWorkingSet(handle); kernel32.CloseHandle(handle)
                except: pass

            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = proc.info['name'].lower()
                    if name in kill_list:
                        proc.kill()
                        if name not in closed_apps: closed_apps.append(name)
                except: pass
        except Exception: pass

        time.sleep(0.5)
        ram_after = psutil.virtual_memory().available
        ram_freed = max(0, ram_after - ram_before)
        closed_apps = [a for a in closed_apps if "python" not in a and "screentime" not in a]

        self.show_popup(format_bytes(ram_freed), format_bytes(freed_disk), closed_apps)

    def _pin_top_right(self):
        sw = self.root.winfo_screenwidth(); saved_x, saved_y = load_pos()
        x = saved_x if saved_x is not None else sw - self.W - self.MARGIN
        y = saved_y if saved_y is not None else 150
        self.root.geometry(f"+{x}+{y}"); self.embedded = False
        user32.SetWindowPos(self.hwnd, 0, x, y, self.W, self.H, 0x0040) 
        self.root.deiconify(); self.root.attributes("-alpha", 0.95)

    def _embed_desktop(self):
        GA_ROOT = 2; GWL_STYLE = -16
        WS_POPUP = 0x80000000; WS_CHILD = 0x40000000; WS_VISIBLE = 0x10000000
        SWP_NOZORDER = 0x0004; SWP_NOACTIVATE = 0x0010; SWP_FRAMECHANGED = 0x0020
        
        for i in range(300):
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
                            if w: target[0] = w
                        return True
                    user32.EnumWindows(EnumProc(cb), 0)
                    parent = target[0] or progman

                    style = user32.GetWindowLongW(self.hwnd, GWL_STYLE) & 0xFFFFFFFF
                    new_style = (style | WS_CHILD | WS_VISIBLE) & ~WS_POPUP
                    user32.SetWindowLongW(self.hwnd, GWL_STYLE, ctypes.c_long(new_style & 0xFFFFFFFF).value)
                    
                    if user32.SetParent(self.hwnd, parent):
                        sw = user32.GetSystemMetrics(0); saved_x, saved_y = load_pos()
                        x = saved_x if saved_x is not None else sw - self.W - self.MARGIN
                        y = saved_y if saved_y is not None else 150
                        
                        user32.SetWindowPos(self.hwnd, 0, x, y, self.W, self.H, 
                                            SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | 0x0040) 
                        self.root.attributes("-alpha", 0.95)
                        self.embedded = True
                        return
            except Exception: pass
            time.sleep(0.1)
        self._pin_top_right()

    def _popup(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=CARD_BG, fg=FG, activebackground=ACCENT, activeforeground=BG)
        m.add_command(label="🚀 Cleanup", command=self.do_cleanup)
        m.add_command(label="Refresh", command=self.refresh_data)
        m.add_command(label="Open dashboard", command=self.open_dashboard)
        m.add_separator()
        m.add_command(label="Quit (stop tracking)", command=self.quit)
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    def open_dashboard(self):
        open_dashboard(self.root, self.db_path, self.dash_ref)

    def quit(self):
        self.root.destroy()

    def refresh_data(self):
        if not os.path.exists(self.db_path):
            self.total_lbl.config(text="—")
            for icon_lbl, name_lbl, dur_lbl in self.app_rows:
                icon_lbl.config(image=""); name_lbl.config(text=""); dur_lbl.config(text="")
            return
        try:
            conn = open_db_readonly(self.db_path)
            try: total, top = query_daily_total(conn, date.today()), query_top_apps(conn, date.today())
            finally: conn.close()
        except sqlite3.Error: return
        
        self.total_lbl.config(text=format_duration(total))
        top_4 = top[:4]
        for i, (icon_lbl, name_lbl, dur_lbl) in enumerate(self.app_rows):
            if i < len(top_4):
                app, dur = top_4[i]
                
                color_idx = int(hashlib.md5(app.encode()).hexdigest(), 16) % len(COLORS)
                bg_color = COLORS[color_idx]
                letter = app[0].upper() if app else "?"
                
                c = tk.Canvas(icon_lbl, bg=CARD_BG, width=16, height=16, highlightthickness=0)
                c.pack()
                c.create_oval(0, 0, 16, 16, fill=bg_color, outline="")
                c.create_text(8, 8, text=letter, fill=CARD_BG, font=(FONT_MAIN, 8, "bold"))
                icon_lbl.config(image="")
                
                name = app if len(app) <= 16 else app[:14] + "…"
                name_lbl.config(text=name)
                dur_lbl.config(text=format_duration(dur))
            else:
                for w in icon_lbl.winfo_children(): w.destroy()
                name_lbl.config(text=""); dur_lbl.config(text="")

    def _tick_data(self):
        try: self.refresh_data()
        finally: self.root.after(self.DATA_REFRESH_MS, self._tick_data)

    def _tick_visibility(self):
        try:
            should_hide = is_foreground_fullscreen()
            if should_hide and not self._hidden:
                if self.embedded and self.hwnd: user32.ShowWindow(self.hwnd, 0)
                else: self.root.withdraw()
                self._hidden = True
            elif not should_hide and self._hidden:
                if self.embedded and self.hwnd: user32.ShowWindow(self.hwnd, 5)
                else: self.root.deiconify()
                self._hidden = False
        finally:
            self.root.after(self.VIS_REFRESH_MS, self._tick_visibility)

def open_widget(db_path, force_pinned=False):
    root = tk.Tk(); DesktopWidget(root, db_path, force_pinned=force_pinned); root.mainloop()

# ─────────── Startup Registration ───────────
def install_startup():
    # If running as an EXE (frozen), use the Registry
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ScreenTimeTracker", 0, winreg.REG_SZ, f'"{exe_path}" both')
            winreg.CloseKey(key)
            log("[startup] Added EXE to Registry Run key")
        except Exception as e:
            log(f"[startup] Failed to add to registry: {e}")
    
    # If running as a .py script, use the .vbs method
    else:
        startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        script = Path(__file__).resolve()
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        if not pythonw.exists(): pythonw = Path(sys.executable)
        vbs = startup / "ScreenTimeTracker.vbs"
        vbs.write_text('Set sh = CreateObject("WScript.Shell")\r\n'
                       f'sh.Run """{pythonw}"" ""{script}"" both", 0, False\r\n')
        log("[startup] Created VBS in Startup folder")

# ─────────── Entry Point ───────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", nargs="?", default="both", choices=["track", "widget", "dashboard", "both", "startup"])
    p.add_argument("--db", help="Custom DB"); p.add_argument("--idle", type=int, default=60); p.add_argument("--pinned", action="store_true")
    args = p.parse_args()
    db_path = Path(args.db) if args.db else get_db_path()

    if args.mode == "startup":
        install_startup()
        return

    # If running as an EXE and launching normally, automatically register to startup
    if getattr(sys, 'frozen', False) and args.mode == "both":
        install_startup()

    if args.mode == "track":
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"): return
        run_tracker(db_path, idle_threshold=args.idle)
    elif args.mode == "widget": 
        open_widget(db_path, force_pinned=args.pinned)
    elif args.mode == "dashboard": 
        open_dashboard(None, db_path)
    else:
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"):
            return
        stop = threading.Event()
        t = threading.Thread(target=run_tracker, daemon=True, args=(db_path,), kwargs={"idle_threshold": args.idle, "stop_event": stop})
        t.start()
        try: open_widget(db_path, force_pinned=args.pinned)
        finally: stop.set(); t.join(timeout=2)

if __name__ == "__main__":
    main()