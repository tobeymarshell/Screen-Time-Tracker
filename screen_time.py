import ctypes
from ctypes import wintypes
import os, sys, time, sqlite3, argparse, threading, subprocess, json, shutil, hashlib
from datetime import datetime, timedelta, date
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import psutil
import winreg

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32    = ctypes.windll.gdi32
psapi    = ctypes.windll.psapi
shell32  = ctypes.windll.shell32
dnsapi   = ctypes.windll.dnsapi

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
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.CreateRoundRectRgn.restype = wintypes.HRGN

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetTickCount.restype = wintypes.DWORD
kernel32.GetTickCount64.restype = ctypes.c_ulonglong
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]; kernel32.CreateMutexW.restype = wintypes.HANDLE
psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
psapi.EmptyWorkingSet.restype = wintypes.BOOL
dnsapi.DnsFlushResolverCache.restype = wintypes.BOOL

def flush_dns():
    """Flushes Windows DNS resolver cache using Win32 dnsapi and ipconfig fallback."""
    try:
        if dnsapi.DnsFlushResolverCache():
            return True
    except Exception: pass
    try:
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        ipconfig_exe = os.path.join(sys_root, "System32", "ipconfig.exe")
        if os.path.exists(ipconfig_exe):
            res = subprocess.run([ipconfig_exe, "/flushdns"], creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
            return res.returncode == 0
    except Exception: pass
    return False

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

# ─────────── Professional Dark Glass Palette ───────────
BG          = "#0D0D11"   # Deep ambient dark
CARD_BG     = "#18181D"   # Primary elevated surface
CARD_BORDER = "#26262F"   # Hairline card border
HOVER_BG    = "#22222B"   # Interactive button / row hover
FG          = "#F5F5F7"   # High-contrast primary text
MUTED       = "#8E8E9A"   # Secondary label text
MUTED_DARK  = "#5C5C68"   # Subtle metadata text
ACCENT      = "#0A84FF"   # Signature vibrant blue
TRACK_BG    = "#25252E"   # Progress bar background
SUCCESS     = "#30D158"   # Emerald success green

COLORS      = ["#0A84FF", "#30D158", "#FF9F0A", "#BF5AF2", "#64D2FF", "#FF375F", "#FFD60A", "#5E5CE6"]
FONT_MAIN   = "Segoe UI Variable Display"
FONT_TEXT   = "Segoe UI Variable Text"

# ─────────── Helpers & Formatting ───────────
def format_app_name(raw_name):
    """Transforms raw executable names into clean, professional app titles."""
    if not raw_name: return "Unknown"
    name = raw_name.lower().replace(".exe", "")
    known = {
        "code": "VS Code",
        "chrome": "Google Chrome",
        "brave": "Brave Browser",
        "msedge": "Microsoft Edge",
        "firefox": "Firefox",
        "windowsterminal": "Terminal",
        "cmd": "Command Prompt",
        "powershell": "PowerShell",
        "explorer": "File Explorer",
        "spotify": "Spotify",
        "discord": "Discord",
        "slack": "Slack",
        "telegram": "Telegram",
        "whatsapp": "WhatsApp",
        "steam": "Steam",
        "notepad": "Notepad",
        "devenv": "Visual Studio",
        "pycharm64": "PyCharm",
        "sublime_text": "Sublime Text",
        "screentime": "Screen Time",
        "python": "Python",
        "pythonw": "Python",
        "desktop": "Home Screen",
    }
    return known.get(name, name.replace("_", " ").replace("-", " ").title())

def round_rect(canvas, x1, y1, x2, y2, r, fill, outline=""):
    """Draws a smooth rounded rectangle on a Canvas."""
    r = min(r, max(1, abs(x2 - x1) // 2), max(1, abs(y2 - y1) // 2))
    canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, fill=fill, outline=outline)
    canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")
    canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="")

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

_MUTEX_HANDLES = []
def try_acquire_mutex(name):
    h = kernel32.CreateMutexW(None, True, name)
    if not h: return None
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(h); return None
    _MUTEX_HANDLES.append(h)
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
    # Privacy fix: store empty string for window_title
    conn.execute("INSERT INTO sessions (app_name, window_title, start_time, end_time, duration_seconds) VALUES (?,?,?,?,?)",
        (app, "", datetime.fromtimestamp(start).isoformat(timespec="seconds"),
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
    elapsed_ms = kernel32.GetTickCount64() - lii.dwTime
    return max(0.0, elapsed_ms / 1000.0)

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
    # Privacy fix: window titles are intentionally redacted and not captured
    return ""

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
class AppRow(tk.Canvas):
    def __init__(self, master, app, dur, mx, idx, **kwargs):
        super().__init__(master, bg=BG, height=56, highlightthickness=0, **kwargs)
        self.app, self.dur, self.mx, self.idx = app, dur, max(1, mx), idx
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
        if w < 20: return
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
        if len(title) > 22: title = title[:20] + "…"
        self.create_text(58, 27, text=title, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="w")
        
        # Duration label on the right
        dur_str = format_duration(self.dur)
        self.create_text(w - 18, 27, text=dur_str, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="e")
        
        # Percentage tag
        pct = int((self.dur / self.mx) * 100)
        self.create_text(w - 95, 27, text=f"{pct}%", fill=MUTED, font=(FONT_MAIN, 9), anchor="e")
        
        # Modern Progress Bar
        bar_x1 = 250
        bar_x2 = w - 130
        bar_w = bar_x2 - bar_x1
        if bar_w > 20:
            bw = max(int(bar_w * (self.dur / self.mx)), 6)
            self.create_line(bar_x1, 27, bar_x2, 27, width=8, fill=TRACK_BG, capstyle=tk.ROUND)
            self.create_line(bar_x1, 27, bar_x1 + bw, 27, width=8, fill=accent_color, capstyle=tk.ROUND)

class Dashboard:
    def __init__(self, window, db_path):
        self.window, self.db_path = window, str(db_path)
        self.selected_date = date.today()
        self.week_offset = 0 
        self.weekly_bars = [] 

        self.window.overrideredirect(True) 
        self.window.geometry("860x780")
        self.window.configure(bg=BG); self.window.minsize(780, 700)
        self.window.attributes("-topmost", True); self.window.after(100, lambda: self.window.attributes("-topmost", False))
        
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
        self.refresh()

    def next_week(self):
        if self.week_offset > 0:
            self.week_offset -= 1
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
            finally: conn.close()
        except sqlite3.Error: return
        
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
            
        self.draw_bars(top); 
        self.draw_weekly(weekly, start_date)
        self.status.config(text=f"Updated {datetime.now():%H:%M:%S}")

    def draw_bars(self, data):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        if not data:
            tk.Label(self.scrollable_frame, text="No activity recorded for this day", bg=BG, fg=MUTED, font=(FONT_MAIN, 11)).pack(pady=40)
            return
            
        mx = max(v for _, v in data) or 1
        
        for i, (app, dur) in enumerate(data):
            row = AppRow(self.scrollable_frame, app, dur, mx, i)
            row.pack(fill="x", pady=4)

    def draw_weekly(self, data, start_date):
        c = self.weekly; c.delete("all"); c.update_idletasks()
        self.weekly_bars = [] 
        
        width = c.winfo_width()
        if width < 100: width = 780 
        
        days = [start_date + timedelta(days=i) for i in range(7)]
        values = {d.isoformat(): 0 for d in days}
        for day, secs in data:
            if day in values: values[day] = secs
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
    W, H = 290, 195 
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
        for txt, cmd, tip in [("⚡", self.do_cleanup, "Free RAM, Clean Temp & Flush DNS"), 
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
            
            icon_lbl = tk.Label(row, bg=CARD_BG)
            icon_lbl.pack(side="left", padx=(0, 8))
            
            name_lbl = tk.Label(row, text="", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 9, "bold"), anchor="w")
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

        for drag_target in (header, title_frame, title_lbl):
            drag_target.bind("<ButtonPress-1>", start_drag)
            drag_target.bind("<B1-Motion>", do_drag)
            drag_target.bind("<ButtonRelease-1>", stop_drag)

        def bind_all(w):
            w.bind("<Button-3>", self._popup)
            for ch in w.winfo_children(): bind_all(ch)
        bind_all(self.card)

    def show_popup(self, ram_str, disk_str):
        if self.cleanup_popup:
            try: self.cleanup_popup.destroy()
            except Exception: pass

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
        px = self.root.winfo_x()
        py = max(20, self.root.winfo_y() - 80 - 12)
        popup.geometry(f"340x80+{px}+{py}")
        
        head = tk.Frame(popup, bg=CARD_BG)
        head.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(head, text="⚡ System Optimized", bg=CARD_BG, fg=SUCCESS, font=(FONT_MAIN, 11, "bold")).pack(side="left")
        
        stats = tk.Label(popup, text=f"RAM: {ram_str}  •  Disk: {disk_str}", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 9))
        stats.pack(anchor="w", padx=14, pady=(0, 4))

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
        ram_before = psutil.virtual_memory().available
        freed_disk = 0
        
        # 1. Clean temp files that are at least 24 hours old (skip junctions/symlinks)
        temp_dir = os.environ.get('TEMP')
        cutoff = time.time() - 86400  # 24 hours
        if temp_dir and os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                try:
                    item_path = os.path.join(temp_dir, item)
                    if os.path.islink(item_path):
                        continue
                    mtime = os.path.getmtime(item_path)
                    if mtime > cutoff:
                        continue  # Keep files younger than 24 hours
                    if os.path.isdir(item_path):
                        sz = 0
                        for root_dir, _, files in os.walk(item_path):
                            for f in files:
                                fp = os.path.join(root_dir, f)
                                if not os.path.islink(fp):
                                    try: sz += os.path.getsize(fp)
                                    except Exception: pass
                        shutil.rmtree(item_path, ignore_errors=True)
                        freed_disk += sz
                    else:
                        freed_disk += os.path.getsize(item_path)
                        os.remove(item_path)
                except Exception: pass

        try:
            rb_info = SHQUERYRBINFO(); rb_info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
            if shell32.SHQueryRecycleBinW(None, ctypes.byref(rb_info)) == 0: freed_disk += rb_info.i64Size
            shell32.SHEmptyRecycleBinW(None, None, 7)
        except Exception: pass

        flush_dns()

        # Flush working sets across running processes to reclaim RAM safely without closing applications
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.pid != os.getpid(): 
                        handle = kernel32.OpenProcess(0x0100 | 0x0400, False, proc.pid)
                        if handle:
                            psapi.EmptyWorkingSet(handle)
                            kernel32.CloseHandle(handle)
                except Exception: pass
        except Exception: pass

        time.sleep(0.5)
        ram_after = psutil.virtual_memory().available
        ram_freed = max(0, ram_after - ram_before)

        self.root.after(0, lambda: self.show_popup(format_bytes(ram_freed), format_bytes(freed_disk)))

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
        
        # Max 5 retries (0.5s total) to avoid blocking the GUI thread on startup
        for i in range(5):
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
                        
                        rgn = gdi32.CreateRoundRectRgn(0, 0, self.W + 1, self.H + 1, 20, 20)
                        user32.SetWindowRgn(self.hwnd, rgn, True)
                        
                        self.root.attributes("-alpha", 0.95)
                        self.embedded = True
                        return
            except Exception: pass
            time.sleep(0.1)
        self._pin_top_right()

    def _popup(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=CARD_BG, fg=FG, activebackground=ACCENT, activeforeground="#FFFFFF")
        m.add_command(label="⚡ Free Memory, Clean Temp & Flush DNS", command=self.do_cleanup)
        m.add_command(label="↻ Refresh Data", command=self.refresh_data)
        m.add_command(label="↗ Open Dashboard", command=self.open_dashboard)
        m.add_separator()
        m.add_command(label="✕ Quit", command=self.quit)
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
                clean_name = format_app_name(app)
                
                color_idx = int(hashlib.md5(app.encode()).hexdigest(), 16) % len(COLORS)
                bg_color = COLORS[color_idx]
                letter = clean_name[0].upper() if clean_name else "?"
                
                for w in icon_lbl.winfo_children(): w.destroy()
                
                c = tk.Canvas(icon_lbl, bg=CARD_BG, width=20, height=20, highlightthickness=0)
                c.pack()
                round_rect(c, 0, 0, 20, 20, 6, bg_color)
                c.create_text(10, 10, text=letter, fill="#FFFFFF", font=(FONT_MAIN, 9, "bold"))
                icon_lbl.config(image="")
                
                display = clean_name if len(clean_name) <= 15 else clean_name[:13] + "…"
                name_lbl.config(text=display)
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
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if getattr(sys, 'frozen', False):
            cmd = f'"{sys.executable}" both'
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            if not pythonw.exists(): pythonw = Path(sys.executable)
            cmd = f'"{pythonw}" "{Path(__file__).resolve()}" both'
        winreg.SetValueEx(key, "ScreenTimeTracker", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        log("[startup] Registered in HKCU Run key")
    except Exception as e:
        log(f"[startup] Failed to add to registry: {e}")

    # Clean legacy VBScript from Startup folder if present
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            legacy_vbs = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "ScreenTimeTracker.vbs"
            if legacy_vbs.exists():
                legacy_vbs.unlink()
                log("[startup] Cleaned legacy VBScript from Startup")
    except Exception: pass

    # Clean legacy entries from StartupApproved in Registry
    try:
        sk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder", 0, winreg.KEY_ALL_ACCESS)
        for old_name in ("ScreenTimeTracker.vbs", "ScreenTime.exe"):
            try: winreg.DeleteValue(sk, old_name)
            except FileNotFoundError: pass
        winreg.CloseKey(sk)
    except Exception: pass

# ─────────── Self Tests ───────────
def run_self_tests():
    print("[TEST] Running ScreenTime self-tests...")
    
    # 1. Formatting helpers
    assert format_duration(0) == "0m"
    assert format_duration(3665) == "1h 1m"
    assert format_duration(3665, short=True) == "1h01"
    assert "KB" in format_bytes(1024)
    assert format_app_name("code.exe") == "VS Code"
    assert format_app_name("chrome.exe") == "Google Chrome"
    assert format_app_name("windowsterminal.exe") == "Terminal"
    
    # 2. 64-bit Tick count idle check
    idle = get_idle_seconds()
    assert isinstance(idle, float) and idle >= 0.0, f"Invalid idle seconds: {idle}"
    
    # 3. Privacy fix: window title must be stored as empty string
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    t0 = 1700000000
    save_session(conn, "code.exe", "SuperSecretDoc.txt - VS Code", t0, t0 + 100)
    row = conn.execute("SELECT app_name, window_title, duration_seconds FROM sessions").fetchone()
    assert row[0] == "code.exe", f"Expected code.exe, got {row[0]}"
    assert row[1] == "", f"Window title was not redacted! Got: {row[1]}"
    assert row[2] == 100, f"Expected 100 duration, got {row[2]}"
    conn.close()

    # 4. Mutex isolation
    test_mutex_name = f"ScreenTime_SelfTest_{os.getpid()}"
    m1 = try_acquire_mutex(test_mutex_name)
    assert m1 is not None, "Failed to acquire first mutex instance"
    m2 = try_acquire_mutex(test_mutex_name)
    assert m2 is None, "Duplicate mutex was improperly acquired!"

    # 5. EmptyWorkingSet ctypes prototype
    assert psapi.EmptyWorkingSet.argtypes == [wintypes.HANDLE]
    assert psapi.EmptyWorkingSet.restype == wintypes.BOOL

    # 6. DNS flush
    assert flush_dns() is True

    print("[TEST] All self-tests passed successfully!")

# ─────────── Entry Point ───────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", nargs="?", default="both", choices=["track", "widget", "dashboard", "both", "startup", "test"])
    p.add_argument("--db", help="Custom DB"); p.add_argument("--idle", type=int, default=60); p.add_argument("--pinned", action="store_true")
    args = p.parse_args()
    db_path = Path(args.db) if args.db else get_db_path()

    if args.mode == "test":
        run_self_tests()
        return

    if args.mode == "startup":
        install_startup()
        return

    if getattr(sys, 'frozen', False) and args.mode == "both":
        install_startup()

    if args.mode == "track":
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"): return
        run_tracker(db_path, idle_threshold=args.idle)
    elif args.mode == "widget": 
        if not try_acquire_mutex("ScreenTimeTracker_Widget"): return
        open_widget(db_path, force_pinned=args.pinned)
    elif args.mode == "dashboard": 
        if not try_acquire_mutex("ScreenTimeTracker_Dashboard"): return
        open_dashboard(None, db_path)
    else:
        # Mode: both
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"): return
        if not try_acquire_mutex("ScreenTimeTracker_Widget"): return
        stop = threading.Event()
        t = threading.Thread(target=run_tracker, daemon=True, args=(db_path,), kwargs={"idle_threshold": args.idle, "stop_event": stop})
        t.start()
        try: open_widget(db_path, force_pinned=args.pinned)
        finally: stop.set(); t.join(timeout=2)

if __name__ == "__main__":
    main()