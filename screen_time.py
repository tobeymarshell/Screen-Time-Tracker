import ctypes
from ctypes import wintypes
import os, sys, time, sqlite3, argparse, threading, subprocess, json, shutil, hashlib, gc
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
user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.CloseDesktop.argtypes = [wintypes.HANDLE]; user32.CloseDesktop.restype = wintypes.BOOL
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]; user32.SetThreadDesktop.restype = wintypes.BOOL

def attach_input_desktop():
    try:
        hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            user32.CloseDesktop(hdesk)
    except Exception: pass

gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.CreateRoundRectRgn.restype = wintypes.HRGN

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetTickCount.restype = wintypes.DWORD
kernel32.GetTickCount64.restype = ctypes.c_ulonglong
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]; kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
psapi.EmptyWorkingSet.restype = wintypes.BOOL
dnsapi.DnsFlushResolverCache.restype = wintypes.BOOL

def trim_memory():
    try:
        gc.collect()
        psapi.EmptyWorkingSet(kernel32.GetCurrentProcess())
    except Exception: pass

def flush_dns():
    try:
        if dnsapi.DnsFlushResolverCache(): return True
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
BG          = "#0D0D11"   
CARD_BG     = "#18181D"   
CARD_BORDER = "#26262F"   
HOVER_BG    = "#22222B"   
FG          = "#F5F5F7"   
MUTED       = "#8E8E9A"   
MUTED_DARK  = "#5C5C68"   
ACCENT      = "#0A84FF"   
TRACK_BG    = "#25252E"   
SUCCESS     = "#30D158"   

COLORS      = ["#0A84FF", "#30D158", "#FF9F0A", "#BF5AF2", "#64D2FF", "#FF375F", "#FFD60A", "#5E5CE6"]
FONT_MAIN   = "Segoe UI Variable Display"
FONT_TEXT   = "Segoe UI Variable Text"

def format_app_name(raw_name):
    if not raw_name: return "Unknown"
    name = raw_name.lower().replace(".exe", "")
    known = {
        "code": "VS Code", "chrome": "Google Chrome", "brave": "Brave Browser",
        "msedge": "Microsoft Edge", "firefox": "Firefox", "windowsterminal": "Terminal",
        "cmd": "Command Prompt", "powershell": "PowerShell", "explorer": "File Explorer",
        "spotify": "Spotify", "discord": "Discord", "slack": "Slack", "telegram": "Telegram",
        "whatsapp": "WhatsApp", "steam": "Steam", "notepad": "Notepad", "devenv": "Visual Studio",
        "pycharm64": "PyCharm", "sublime_text": "Sublime Text", "screentime": "Screen Time",
        "python": "Python", "pythonw": "Python", "desktop": "Home Screen",
    }
    return known.get(name, name.replace("_", " ").replace("-", " ").title())

def round_rect(canvas, x1, y1, x2, y2, r, fill, outline="", width=1, tag=None):
    r = min(r, max(1, abs(x2 - x1) // 2), max(1, abs(y2 - y1) // 2))
    tags = (tag,) if tag else ()
    canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="", tags=tags)
    canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="", tags=tags)
    if outline:
        canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_line(x1+r, y1, x2-r, y1, fill=outline, width=width, tags=tags)
        canvas.create_line(x2, y1+r, x2, y2-r, fill=outline, width=width, tags=tags)
        canvas.create_line(x1+r, y2, x2-r, y2, fill=outline, width=width, tags=tags)
        canvas.create_line(x1, y1+r, x1, y2-r, fill=outline, width=width, tags=tags)

class RoundedCard(tk.Canvas):
    def __init__(self, master, radius=14, bg_col=CARD_BG, border_col=CARD_BORDER, parent_bg=BG, padding=12, auto_height=True, **kwargs):
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0, **kwargs)
        self.radius = radius
        self.bg_col = bg_col
        self.border_col = border_col
        self.padding = padding
        self.auto_height = auto_height
        self.container = tk.Frame(self, bg=bg_col)
        self.win_id = None
        self._last_req_h = -1
        self.bind("<Configure>", self._on_configure)
        if self.auto_height:
            self.container.bind("<Configure>", self._on_content_configure)

    def _on_content_configure(self, event=None):
        if not self.auto_height: return
        req_h = self.container.winfo_reqheight() + 2 * self.padding
        if req_h > 0 and self._last_req_h != req_h:
            self._last_req_h = req_h
            if self.winfo_height() != req_h:
                self.configure(height=req_h)

    def _on_configure(self, event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10: return
        
        self.delete("bg")
        pad = self.padding
        round_rect(self, 0, 0, w - 1, h - 1, self.radius, self.bg_col, self.border_col, tag="bg")

        cw = max(10, w - 2 * pad)
        ch = max(10, h - 2 * pad)
        if self.win_id is None:
            self.win_id = self.create_window(pad, pad, window=self.container, anchor="nw", width=cw, height=ch)
        else:
            self.coords(self.win_id, pad, pad)
            self.itemconfigure(self.win_id, width=cw, height=ch)

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
    if b <= 0: return "0 B"
    elif b < 1024: return f"{int(b)} B"
    elif b < 1024 * 1024: return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024: return f"{b / (1024 * 1024):.1f} MB"
    else: return f"{b / (1024 * 1024 * 1024):.2f} GB"

def format_speed(b):
    if b <= 0: return "0 B/s"
    elif b < 1024: return f"{int(b)} B/s"
    elif b < 1024 * 1024: return f"{b / 1024:.1f} KB/s"
    elif b < 1024 * 1024 * 1024: return f"{b / (1024 * 1024):.1f} MB/s"
    else: return f"{b / (1024 * 1024 * 1024):.2f} GB/s"

_MUTEX_HANDLES = []
def try_acquire_mutex(name):
    h = kernel32.CreateMutexW(None, True, name)
    if not h: return None
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(h); return None
    _MUTEX_HANDLES.append(h)
    return h

# ─────────── ACCURATE NETWORK COUNTER (FILTERS VIRTUAL ADAPTERS) ───────────
def get_physical_net_io():
    """Calculates network usage ONLY for physical adapters (Ethernet/Wi-Fi), ignoring VirtualBox, WSL, and VPNs."""
    try:
        stats = psutil.net_io_counters(pernic=True)
        if_stats = psutil.net_if_stats()
        total_sent = 0
        total_recv = 0
        for nic, data in stats.items():
            name_lower = nic.lower()
            # Ignore loopback, virtual network interfaces, and pseudo-interfaces
            if any(k in name_lower for k in ["loopback", "vbox", "vmware", "wsl", "vethernet", "tap", "tun", "virtual", "pseudo", "wan miniport", "teredo"]):
                continue
            
            # Only count interfaces that are UP
            if nic in if_stats and if_stats[nic].isup:
                total_sent += data.bytes_sent
                total_recv += data.bytes_recv
        return total_sent, total_recv
    except Exception:
        # Fallback to standard counter if pernic fails
        try:
            net = psutil.net_io_counters()
            return net.bytes_sent, net.bytes_recv
        except Exception:
            return 0, 0

def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-500")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, app_name TEXT NOT NULL,
        window_title TEXT, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time)")
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_network (
        date TEXT PRIMARY KEY,
        bytes_sent INTEGER DEFAULT 0,
        bytes_recv INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_app_network (
        date TEXT NOT NULL,
        app_name TEXT NOT NULL,
        bytes_sent INTEGER DEFAULT 0,
        bytes_recv INTEGER DEFAULT 0,
        PRIMARY KEY (date, app_name))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_app_net_date ON daily_app_network(date)")
    conn.commit()

def save_session(conn, app, title, start, end):
    dur = int(end - start)
    if dur < 1 or not app: return
    conn.execute("INSERT INTO sessions (app_name, window_title, start_time, end_time, duration_seconds) VALUES (?,?,?,?,?)",
        (app, "", datetime.fromtimestamp(start).isoformat(timespec="seconds"),
         datetime.fromtimestamp(end).isoformat(timespec="seconds"), dur))
    conn.commit()

def start_session(conn, app, start_ts):
    if not app: return None
    start_iso = datetime.fromtimestamp(start_ts).isoformat(timespec="seconds")
    cur = conn.cursor()
    cur.execute("INSERT INTO sessions (app_name, window_title, start_time, end_time, duration_seconds) VALUES (?, '', ?, ?, 1)",
                (app, start_iso, start_iso))
    conn.commit()
    return cur.lastrowid

def update_session(conn, session_id, end_ts, start_ts):
    if not session_id: return
    dur = max(1, int(end_ts - start_ts))
    end_iso = datetime.fromtimestamp(end_ts).isoformat(timespec="seconds")
    conn.execute("UPDATE sessions SET end_time = ?, duration_seconds = ? WHERE id = ?",
                 (end_iso, dur, session_id))
    conn.commit()

def delete_session(conn, session_id):
    if not session_id: return
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    except Exception: pass

def save_network_usage(conn, day_str, sent, recv):
    if sent <= 0 and recv <= 0: return
    conn.execute("""
        INSERT INTO daily_network (date, bytes_sent, bytes_recv)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            bytes_sent = bytes_sent + excluded.bytes_sent,
            bytes_recv = bytes_recv + excluded.bytes_recv
    """, (day_str, int(sent), int(recv)))
    conn.commit()

def save_app_network_usage(conn, day_str, app_name, sent, recv):
    if (sent <= 0 and recv <= 0) or not app_name: return
    conn.execute("""
        INSERT INTO daily_app_network (date, app_name, bytes_sent, bytes_recv)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date, app_name) DO UPDATE SET
            bytes_sent = bytes_sent + excluded.bytes_sent,
            bytes_recv = bytes_recv + excluded.bytes_recv
    """, (day_str, app_name, int(sent), int(recv)))
    conn.commit()

def query_daily_network(conn, target_date):
    day_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
    try:
        row = conn.execute("SELECT bytes_sent, bytes_recv FROM daily_network WHERE date = ?", (day_str,)).fetchone()
        if row: return (row[0] or 0, row[1] or 0)
    except sqlite3.OperationalError: pass
    return (0, 0)

def query_monthly_network(conn, year, month):
    prefix = f"{year:04d}-{month:02d}"
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(bytes_sent), 0), COALESCE(SUM(bytes_recv), 0)
            FROM daily_network
            WHERE date >= ? AND date <= ?
        """, (f"{prefix}-01", f"{prefix}-31")).fetchone()
        return (row[0] or 0, row[1] or 0)
    except sqlite3.OperationalError: pass
    return (0, 0)

def query_monthly_network_history(conn, year, month):
    prefix = f"{year:04d}-{month:02d}"
    try:
        return conn.execute("""
            SELECT date, bytes_sent, bytes_recv
            FROM daily_network
            WHERE date >= ? AND date <= ?
            ORDER BY date DESC
        """, (f"{prefix}-01", f"{prefix}-31")).fetchall()
    except sqlite3.OperationalError: pass
    return []

def query_daily_app_network(conn, target_date):
    day_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
    try:
        rows = conn.execute("""
            SELECT app_name, bytes_sent, bytes_recv, (bytes_sent + bytes_recv) AS total_bytes
            FROM daily_app_network
            WHERE date = ?
            ORDER BY total_bytes DESC
        """, (day_str,)).fetchall()
        if rows: return rows
        
        net_row = conn.execute("SELECT bytes_sent, bytes_recv FROM daily_network WHERE date = ?", (day_str,)).fetchone()
        if net_row and ((net_row[0] or 0) > 0 or (net_row[1] or 0) > 0):
            tot_s, tot_r = net_row[0] or 0, net_row[1] or 0
            start_str = day_str
            end_str = (datetime.strptime(day_str, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
            
            top = conn.execute("""
                SELECT app_name, SUM(duration_seconds) AS total
                FROM sessions
                WHERE start_time >= ? AND start_time < ?
                GROUP BY app_name
                ORDER BY total DESC
            """, (start_str, end_str)).fetchall()
            
            if top:
                tot_dur = sum(d for _, d in top) or 1
                seeded_rows = []
                for app, dur in top:
                    ratio = dur / tot_dur
                    s_part = int(tot_s * ratio)
                    r_part = int(tot_r * ratio)
                    if s_part > 0 or r_part > 0:
                        seeded_rows.append((app, s_part, r_part, s_part + r_part))
                if seeded_rows: return seeded_rows
    except sqlite3.OperationalError: pass
    return []

def run_tracker(db_path, idle_threshold=180, poll_interval=1.0, stop_event=None):
    attach_input_desktop()
    conn = sqlite3.connect(str(db_path)); init_db(conn)
    current_app = None
    session_start = None
    current_session_id = None
    transient_grace = 0
    last_loop_time = time.time()
    last_net_flush = time.time()
    accum_sent, accum_recv = 0, 0
    app_accum = {}
    proc_cache = {}
    last_proc_io = {}
    
    last_net_sent, last_net_recv = get_physical_net_io()

    try:
        while stop_event is None or not stop_event.is_set():
            now = time.time()
            dt = now - last_loop_time

            # SLEEP/WAKE FIX: If gap is > 4 seconds, the machine slept. Reset counters to avoid massive data spikes.
            if dt > 4.0:
                if current_session_id and session_start is not None:
                    update_session(conn, current_session_id, last_loop_time, session_start)
                current_app, session_start, current_session_id = None, None, None
                transient_grace = 0
                last_net_sent, last_net_recv = get_physical_net_io()

            last_loop_time = now
            locked = is_workstation_locked()
            idle = get_idle_seconds()
            is_idle = (idle >= idle_threshold)
            if is_idle and is_audio_playing():
                is_idle = False

            ds, dr = 0, 0
            cur_net_sent, cur_net_recv = get_physical_net_io()
            if last_net_sent is not None and last_net_recv is not None:
                ds = max(0, cur_net_sent - last_net_sent)
                dr = max(0, cur_net_recv - last_net_recv)
                
                # SPIKE PROTECTION: Ignore any single-second delta > 50MB (prevents glitches)
                if ds > 50 * 1024 * 1024 or dr > 50 * 1024 * 1024:
                    ds = 0
                    dr = 0
                else:
                    accum_sent += ds
                    accum_recv += dr
                    
            last_net_sent, last_net_recv = cur_net_sent, cur_net_recv

            if ds > 0 or dr > 0:
                proc_deltas = {}
                try:
                    conns = psutil.net_connections(kind="inet")
                    pids = set(c.pid for c in conns if c.pid)
                except Exception:
                    pids = set()

                for pid in pids:
                    try:
                        if pid not in proc_cache:
                            p = psutil.Process(pid)
                            proc_cache[pid] = (p, p.name())
                        else:
                            p, name = proc_cache[pid]

                        io = p.io_counters()
                        prev_io = last_proc_io.get(pid)
                        last_proc_io[pid] = io
                        if prev_io:
                            d_other = max(0, io.other_bytes - prev_io.other_bytes)
                            d_rw = max(0, io.read_bytes - prev_io.read_bytes) + max(0, io.write_bytes - prev_io.write_bytes)
                            d_total = d_other + (d_rw // 2)
                            if d_total > 0:
                                proc_deltas[name] = proc_deltas.get(name, 0) + d_total
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        proc_cache.pop(pid, None)
                        last_proc_io.pop(pid, None)
                    except Exception: pass

                total_proc_delta = sum(proc_deltas.values())
                if total_proc_delta > 0:
                    for app_name, delta in proc_deltas.items():
                        ratio = delta / total_proc_delta
                        app_s = int(ds * ratio)
                        app_r = int(dr * ratio)
                        if app_name not in app_accum: app_accum[app_name] = [0, 0]
                        app_accum[app_name][0] += app_s
                        app_accum[app_name][1] += app_r
                elif current_app and current_app != "Desktop":
                    if current_app not in app_accum: app_accum[current_app] = [0, 0]
                    app_accum[current_app][0] += ds
                    app_accum[current_app][1] += dr
                else:
                    if "System" not in app_accum: app_accum["System"] = [0, 0]
                    app_accum["System"][0] += ds
                    app_accum["System"][1] += dr

            if (now - last_net_flush >= 1.0) and (accum_sent > 0 or accum_recv > 0):
                today_str = date.today().isoformat()
                save_network_usage(conn, today_str, accum_sent, accum_recv)
                accum_sent, accum_recv = 0, 0
                for app_name, (a_sent, a_recv) in list(app_accum.items()):
                    if a_sent > 0 or a_recv > 0:
                        save_app_network_usage(conn, today_str, app_name, a_sent, a_recv)
                app_accum.clear()
                last_net_flush = now

            if locked or is_idle:
                if current_session_id and session_start is not None:
                    cutoff = max(session_start + 1, min(now, (now - idle) + idle_threshold)) if is_idle else now
                    if cutoff > session_start + 1: update_session(conn, current_session_id, cutoff, session_start)
                    else: delete_session(conn, current_session_id)
                current_app, session_start, current_session_id = None, None, None
                transient_grace = 0
            else:
                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    attach_input_desktop()
                    hwnd = user32.GetForegroundWindow()
                class_name = ctypes.create_unicode_buffer(256)
                if hwnd: user32.GetClassNameW(hwnd, class_name, 256)
                if class_name.value in ("Progman", "WorkerW"): detected_app = "Desktop"
                else: detected_app = get_foreground_process_name()

                if detected_app is None:
                    if current_app is not None and transient_grace < 5:
                        transient_grace += 1
                        detected_app = current_app
                    else: detected_app = None
                else: transient_grace = 0

                if detected_app != current_app:
                    if current_session_id and session_start is not None:
                        if now > session_start + 0.5: update_session(conn, current_session_id, now, session_start)
                        else: delete_session(conn, current_session_id)
                    current_app = detected_app
                    if current_app:
                        session_start = now
                        current_session_id = start_session(conn, current_app, session_start)
                    else: session_start, current_session_id = None, None
                else:
                    if current_session_id and session_start is not None:
                        s_day = date.fromtimestamp(session_start)
                        c_day = date.fromtimestamp(now)
                        if c_day != s_day:
                            mid_ts = datetime(s_day.year, s_day.month, s_day.day, 23, 59, 59).timestamp()
                            update_session(conn, current_session_id, mid_ts, session_start)
                            session_start = datetime(c_day.year, c_day.month, c_day.day, 0, 0, 0).timestamp()
                            current_session_id = start_session(conn, current_app, session_start)
                        else: update_session(conn, current_session_id, now, session_start)

            time.sleep(poll_interval)
    except KeyboardInterrupt: pass
    finally:
        if current_session_id and session_start is not None:
            update_session(conn, current_session_id, time.time(), session_start)
        if accum_sent > 0 or accum_recv > 0:
            today_str = date.today().isoformat()
            try:
                save_network_usage(conn, today_str, accum_sent, accum_recv)
                for app_name, (a_sent, a_recv) in app_accum.items():
                    if a_sent > 0 or a_recv > 0:
                        save_app_network_usage(conn, today_str, app_name, a_sent, a_recv)
            except Exception: pass
        conn.close()

def query_daily_total(conn, target_date):
    start_str = target_date.isoformat()
    end_str = (target_date + timedelta(days=1)).isoformat()
    return conn.execute("SELECT COALESCE(SUM(duration_seconds),0) FROM sessions WHERE start_time >= ? AND start_time < ?",
                        (start_str, end_str)).fetchone()[0]

def query_top_apps(conn, target_date):
    start_str = target_date.isoformat()
    end_str = (target_date + timedelta(days=1)).isoformat()
    return conn.execute("SELECT app_name, SUM(duration_seconds) AS total FROM sessions "
                        "WHERE start_time >= ? AND start_time < ? GROUP BY app_name ORDER BY total DESC",
                        (start_str, end_str)).fetchall()

def query_daily_totals_range(conn, start_date, end_date):
    start_str = start_date.isoformat()
    end_str = (end_date + timedelta(days=1)).isoformat()
    return conn.execute("SELECT substr(start_time,1,10) AS day, SUM(duration_seconds) FROM sessions "
                        "WHERE start_time >= ? AND start_time < ? GROUP BY day ORDER BY day", 
                        (start_str, end_str)).fetchall()

def open_db_readonly(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    try: conn.execute("PRAGMA cache_size=-250")
    except Exception: pass
    return conn

def is_workstation_locked():
    try:
        hdesk = user32.OpenInputDesktop(0, False, 1)
        if not hdesk: return True
        user32.CloseDesktop(hdesk)
        return False
    except Exception: return False

def get_idle_seconds():
    lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(lii)): return 0.0
    tick = kernel32.GetTickCount()
    elapsed_ms = (tick - lii.dwTime) & 0xFFFFFFFF
    return max(0.0, elapsed_ms / 1000.0)

def is_audio_playing():
    try:
        from pycaw.pycaw import AudioUtilities
        for s in AudioUtilities.GetAllSessions():
            if s.Process and getattr(s, "State", 0) == 1: return True
    except Exception: pass
    return False

_proc_name_cache = {}
def get_foreground_process_name():
    hwnd = user32.GetForegroundWindow()
    if not hwnd: return None
    class_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buf, 256)
    cname = class_buf.value
    if cname in ("Shell_TrayWnd", "NotifyIconOverflowWindow", "TaskSwitchWnd"): return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value: return None
    pid_val = pid.value
    if pid_val in _proc_name_cache: return _proc_name_cache[pid_val]
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_val)
    if h:
        try:
            buf = ctypes.create_unicode_buffer(1024); size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value)
                if len(_proc_name_cache) > 100: _proc_name_cache.clear()
                _proc_name_cache[pid_val] = name
                return name
        finally: kernel32.CloseHandle(h)
    try:
        name = psutil.Process(pid_val).name()
        if name:
            if len(_proc_name_cache) > 100: _proc_name_cache.clear()
            _proc_name_cache[pid_val] = name
            return name
    except Exception: pass
    return None

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
        
        round_rect(self, 14, 12, 44, 42, 8, accent_color)
        self.create_text(29, 27, text=letter, fill="#FFFFFF", font=(FONT_MAIN, 13, "bold"))
        
        title = self.display_name
        if len(title) > 22: title = title[:20] + "…"
        self.create_text(58, 27, text=title, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="w")
        
        dur_str = format_duration(self.dur)
        self.create_text(w - 18, 27, text=dur_str, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="e")
        
        bar_x1 = 250
        bar_x2 = w - 80
        bar_w = bar_x2 - bar_x1
        if bar_w > 20:
            bw = max(int(bar_w * (self.dur / self.mx)), 6)
            self.create_line(bar_x1, 27, bar_x2, 27, width=8, fill=TRACK_BG, capstyle=tk.ROUND)
            self.create_line(bar_x1, 27, bar_x1 + bw, 27, width=8, fill=accent_color, capstyle=tk.ROUND)

class DataRow(tk.Canvas):
    def __init__(self, master, day_str, sent, recv, mx, idx, is_expanded=False, on_click=None, **kwargs):
        super().__init__(master, bg=BG, height=56, highlightthickness=0, cursor="hand2", **kwargs)
        self.day_str, self.sent, self.recv = day_str, sent, recv
        self.total = sent + recv
        self.mx = max(1, mx)
        self.idx = idx
        self.is_expanded = is_expanded
        self.on_click = on_click
        self.is_hovered = False
        
        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click_event)

    def on_click_event(self, e):
        if self.on_click: self.on_click(self.day_str)

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
        bg_col = HOVER_BG if (self.is_hovered or self.is_expanded) else CARD_BG
        border_col = ACCENT if self.is_expanded else CARD_BORDER
        round_rect(self, 0, 0, w - 1, 55, 12, bg_col, border_col)
        
        badge_col = SUCCESS if self.is_expanded else ACCENT
        round_rect(self, 14, 12, 44, 42, 8, badge_col)
        self.create_text(29, 27, text="⇄", fill="#FFFFFF", font=(FONT_MAIN, 13, "bold"))
        
        try:
            d = datetime.strptime(self.day_str, "%Y-%m-%d").date()
            if d == date.today(): date_display = "Today"
            elif d == date.today() - timedelta(days=1): date_display = "Yesterday"
            else: date_display = d.strftime("%A, %b %d")
        except Exception: date_display = self.day_str
            
        self.create_text(58, 20, text=date_display, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="w")
        sub_text = f"↓ {format_bytes(self.recv)}   ↑ {format_bytes(self.sent)}"
        self.create_text(58, 38, text=sub_text, fill=MUTED, font=(FONT_MAIN, 9), anchor="w")
        
        chevron = "▼" if self.is_expanded else "▶"
        chevron_col = ACCENT if self.is_expanded else MUTED
        self.create_text(w - 20, 27, text=chevron, fill=chevron_col, font=(FONT_MAIN, 10, "bold"), anchor="e")
        total_str = format_bytes(self.total)
        self.create_text(w - 45, 27, text=total_str, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="e")
        
        bar_x1 = 250
        bar_x2 = w - 140
        bar_w = bar_x2 - bar_x1
        if bar_w > 20:
            bw = max(int(bar_w * (self.total / self.mx)), 6)
            self.create_line(bar_x1, 27, bar_x2, 27, width=8, fill=TRACK_BG, capstyle=tk.ROUND)
            self.create_line(bar_x1, 27, bar_x1 + bw, 27, width=8, fill=ACCENT, capstyle=tk.ROUND)

class AppDataRow(tk.Canvas):
    def __init__(self, master, app_name, sent, recv, day_total, idx, **kwargs):
        super().__init__(master, bg=CARD_BG, height=56, highlightthickness=0, **kwargs)
        self.app_name, self.sent, self.recv = app_name, sent, recv
        self.total = sent + recv
        self.day_total = max(1, day_total)
        self.idx = idx
        self.display_name = format_app_name(self.app_name)
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
        round_rect(self, 0, 0, w - 1, 55, 8, bg_col, CARD_BORDER if self.is_hovered else "")

        color_idx = int(hashlib.md5(self.app_name.encode()).hexdigest(), 16) % len(COLORS)
        accent_color = COLORS[color_idx]
        letter = self.display_name[0].upper() if self.display_name else "?"

        round_rect(self, 10, 11, 42, 43, 8, accent_color)
        self.create_text(26, 27, text=letter, fill="#FFFFFF", font=(FONT_MAIN, 11, "bold"))

        title = self.display_name
        if len(title) > 22: title = title[:20] + "…"
        self.create_text(56, 20, text=title, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="w")
        sub_str = f"↓ {format_bytes(self.recv)}  •  ↑ {format_bytes(self.sent)}"
        self.create_text(56, 38, text=sub_str, fill=MUTED, font=(FONT_MAIN, 9), anchor="w")

        total_str = format_bytes(self.total)
        self.create_text(w - 20, 27, text=total_str, fill=FG, font=(FONT_MAIN, 11, "bold"), anchor="e")

        bar_x1 = 250
        bar_x2 = w - 110
        bar_w = bar_x2 - bar_x1
        if bar_w > 20:
            bw = max(int(bar_w * (self.total / self.day_total)), 6)
            self.create_line(bar_x1, 27, bar_x2, 27, width=8, fill=TRACK_BG, capstyle=tk.ROUND)
            self.create_line(bar_x1, 27, bar_x1 + bw, 27, width=8, fill=accent_color, capstyle=tk.ROUND)

class Dashboard:
    def __init__(self, window, db_path):
        self.window, self.db_path = window, str(db_path)
        self.selected_date = date.today()
        self.week_offset = 0 
        self.weekly_bars = [] 
        self.active_tab = "screentime"
        self.expanded_day = date.today().isoformat()
        self.selected_data_date = date.today()
        self._last_size = None
        self.last_scroll_time = 0

        self.window.overrideredirect(True) 
        self.window.geometry("1000x820")
        self.window.configure(bg=BG); self.window.minsize(920, 740)
        self.window.attributes("-topmost", True); self.window.after(100, lambda: self.window.attributes("-topmost", False))
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

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
            if hwnd:
                rgn = gdi32.CreateRoundRectRgn(0, 0, self.window.winfo_width() + 1, self.window.winfo_height() + 1, 20, 20)
                user32.SetWindowRgn(hwnd, rgn, True)

        title_bar.bind("<ButtonPress-1>", start_drag)
        title_bar.bind("<B1-Motion>", do_drag)
        title_bar.bind("<ButtonRelease-1>", stop_drag)

        dot = tk.Label(title_bar, text="●", bg=CARD_BG, fg=ACCENT, font=(FONT_MAIN, 9))
        dot.pack(side="left", padx=(18, 6), pady=12)
        title_lbl = tk.Label(title_bar, text="Screen Time & Data Analytics", bg=CARD_BG, fg=FG, font=(FONT_MAIN, 11, "bold"))
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
        if hwnd:
            rgn = gdi32.CreateRoundRectRgn(0, 0, self.window.winfo_width() + 1, self.window.winfo_height() + 1, 20, 20)
            user32.SetWindowRgn(hwnd, rgn, True)

        def on_window_resize(e):
            if e.widget == self.window:
                w, h = self.window.winfo_width(), self.window.winfo_height()
                if (w, h) != self._last_size:
                    self._last_size = (w, h)
                    hwnd_handle = user32.GetAncestor(self.window.winfo_id(), 2)
                    if hwnd_handle:
                        rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, 20, 20)
                        user32.SetWindowRgn(hwnd_handle, rgn, True)
        self.window.bind("<Configure>", on_window_resize)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar", gripcount=0, background=TRACK_BG, darkcolor=BG, lightcolor=BG, troughcolor=BG, bordercolor=BG, arrowcolor=BG, width=8)
        style.map("Vertical.TScrollbar", background=[('active', MUTED)])

        tab_container = tk.Frame(self.window, bg=BG)
        tab_container.pack(fill="x", padx=30, pady=(14, 0))

        tab_bar = tk.Frame(tab_container, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1)
        tab_bar.pack(side="left")

        self.btn_tab_st = tk.Button(tab_bar, text="⏱  Screen Time", font=(FONT_MAIN, 10, "bold"),
                                    bg=ACCENT, fg="#FFFFFF", relief="flat", bd=0, padx=25, pady=8, cursor="hand2",
                                    activebackground=ACCENT, activeforeground="#FFFFFF",
                                    command=lambda: self.switch_tab("screentime"))
        self.btn_tab_st.pack(side="left")

        self.btn_tab_data = tk.Button(tab_bar, text="🌐  Data Details", font=(FONT_MAIN, 10, "bold"),
                                      bg=CARD_BG, fg=MUTED, relief="flat", bd=0, padx=25, pady=8, cursor="hand2",
                                      activebackground=HOVER_BG, activeforeground=FG,
                                      command=lambda: self.switch_tab("data"))
        self.btn_tab_data.pack(side="left")

        def on_enter_st(e):
            if self.active_tab != "screentime": self.btn_tab_st.config(bg=HOVER_BG, fg=FG)
        def on_leave_st(e):
            if self.active_tab != "screentime": self.btn_tab_st.config(bg=CARD_BG, fg=MUTED)
        def on_enter_data(e):
            if self.active_tab != "data": self.btn_tab_data.config(bg=HOVER_BG, fg=FG)
        def on_leave_data(e):
            if self.active_tab != "data": self.btn_tab_data.config(bg=CARD_BG, fg=MUTED)

        self.btn_tab_st.bind("<Enter>", on_enter_st)
        self.btn_tab_st.bind("<Leave>", on_leave_st)
        self.btn_tab_data.bind("<Enter>", on_enter_data)
        self.btn_tab_data.bind("<Leave>", on_leave_data)

        refresh_all_btn = tk.Button(tab_container, text="↻ Refresh", command=self.refresh_current_tab,
                                    bg=CARD_BG, fg=MUTED, relief="flat", bd=0, padx=15, pady=8,
                                    font=(FONT_MAIN, 10, "bold"), cursor="hand2",
                                    activebackground=HOVER_BG, activeforeground=FG)
        refresh_all_btn.pack(side="right")

        footer = tk.Frame(self.window, bg=BG)
        footer.pack(side="bottom", fill="x", padx=35, pady=(0, 12))
        self.status = tk.Label(footer, text="", font=(FONT_MAIN, 9), bg=BG, fg=MUTED_DARK)
        self.status.pack(side="left")

        self.tab_st_frame = tk.Frame(self.window, bg=BG)
        self.tab_data_frame = tk.Frame(self.window, bg=BG)
        self.tab_st_frame.pack(fill="both", expand=True)

        hero_card = RoundedCard(self.tab_st_frame, radius=16, bg_col=CARD_BG, border_col=CARD_BORDER, parent_bg=BG, padding=12)
        hero_card.pack(fill="x", padx=30, pady=(12, 0))

        hero_inner = tk.Frame(hero_card.container, bg=CARD_BG)
        hero_inner.pack(fill="x", padx=12, pady=8)

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

        chart_card = RoundedCard(self.tab_st_frame, radius=16, bg_col=CARD_BG, border_col=CARD_BORDER, parent_bg=BG, padding=12)
        chart_card.pack(fill="x", padx=30, pady=(14, 0))

        chart_head = tk.Frame(chart_card.container, bg=CARD_BG)
        chart_head.pack(fill="x", padx=8, pady=(4, 0))
        self.chart_title = tk.Label(chart_head, text="Weekly Activity", font=(FONT_MAIN, 12, "bold"), bg=CARD_BG, fg=FG)
        self.chart_title.pack(side="left")
        self.chart_hint = tk.Label(chart_head, text="Click a bar to view daily breakdown", font=(FONT_MAIN, 9), bg=CARD_BG, fg=MUTED_DARK)
        self.chart_hint.pack(side="right")

        self.weekly = tk.Canvas(chart_card.container, bg=CARD_BG, highlightthickness=0, height=135)
        self.weekly.pack(fill="x", padx=8, pady=(6, 4))
        self.weekly.bind("<Button-1>", self.on_weekly_click)

        apps_header = tk.Frame(self.tab_st_frame, bg=BG)
        apps_header.pack(fill="x", padx=34, pady=(16, 8))
        self.apps_title = tk.Label(apps_header, text="Top Applications", font=(FONT_MAIN, 13, "bold"), bg=BG, fg=FG)
        self.apps_title.pack(side="left")

        list_container = tk.Frame(self.tab_st_frame, bg=BG)
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

        data_cards = tk.Frame(self.tab_data_frame, bg=BG)
        data_cards.pack(fill="x", padx=30, pady=(12, 0))
        data_cards.grid_columnconfigure(0, weight=1)
        data_cards.grid_columnconfigure(1, weight=1)

        self.card_selected = RoundedCard(data_cards, radius=16, bg_col=CARD_BG, border_col=CARD_BORDER, parent_bg=BG, padding=16)
        self.card_selected.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        inner_selected = tk.Frame(self.card_selected.container, bg=CARD_BG)
        inner_selected.pack(fill="both", expand=True, padx=10, pady=8)

        self.data_selected_lbl = tk.Label(inner_selected, text="TODAY'S USAGE", font=(FONT_MAIN, 9, "bold"), bg=CARD_BG, fg=MUTED)
        self.data_selected_lbl.pack(anchor="w")
        self.data_selected_total = tk.Label(inner_selected, text="—", font=(FONT_MAIN, 36, "bold"), bg=CARD_BG, fg=FG)
        self.data_selected_total.pack(anchor="w", pady=(2, 4))
        self.data_selected_sub = tk.Label(inner_selected, text="↓ 0 B  •  ↑ 0 B", font=(FONT_MAIN, 9), bg=CARD_BG, fg=MUTED_DARK)
        self.data_selected_sub.pack(anchor="w")

        self.card_month = RoundedCard(data_cards, radius=16, bg_col=CARD_BG, border_col=CARD_BORDER, parent_bg=BG, padding=16)
        self.card_month.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        inner_month = tk.Frame(self.card_month.container, bg=CARD_BG)
        inner_month.pack(fill="both", expand=True, padx=10, pady=8)

        self.data_month_lbl = tk.Label(inner_month, text="THIS MONTH", font=(FONT_MAIN, 9, "bold"), bg=CARD_BG, fg=MUTED)
        self.data_month_lbl.pack(anchor="w")
        self.data_month_total = tk.Label(inner_month, text="—", font=(FONT_MAIN, 36, "bold"), bg=CARD_BG, fg=FG)
        self.data_month_total.pack(anchor="w", pady=(2, 4))
        self.data_month_sub = tk.Label(inner_month, text="↓ 0 B  •  ↑ 0 B", font=(FONT_MAIN, 9), bg=CARD_BG, fg=MUTED_DARK)
        self.data_month_sub.pack(anchor="w")

        data_header = tk.Frame(self.tab_data_frame, bg=BG)
        data_header.pack(fill="x", padx=34, pady=(18, 8))
        tk.Label(data_header, text="Daily Network Breakdown", font=(FONT_MAIN, 13, "bold"), bg=BG, fg=FG).pack(side="left")
        self.data_month_hint = tk.Label(data_header, text="", font=(FONT_MAIN, 9), bg=BG, fg=MUTED_DARK)
        self.data_month_hint.pack(side="right")

        data_list_container = tk.Frame(self.tab_data_frame, bg=BG)
        data_list_container.pack(side="top", fill="both", expand=True, padx=30, pady=(0, 10))

        self.data_canvas = tk.Canvas(data_list_container, bg=BG, highlightthickness=0)
        data_scrollbar = ttk.Scrollbar(data_list_container, orient="vertical", command=self.data_canvas.yview)
        self.data_scrollable_frame = tk.Frame(self.data_canvas, bg=BG)

        self.data_scrollable_frame.bind("<Configure>", lambda e: self.data_canvas.configure(scrollregion=self.data_canvas.bbox("all")))
        self.data_canvas.bind("<Configure>", lambda e: self.data_canvas.itemconfig(self.data_canvas_window, width=e.width))
        self.data_canvas_window = self.data_canvas.create_window((0, 0), window=self.data_scrollable_frame, anchor="nw")

        self.data_canvas.configure(yscrollcommand=data_scrollbar.set)
        self.data_canvas.pack(side="left", fill="both", expand=True)
        data_scrollbar.pack(side="right", fill="y")

        def on_scroll(event):
            self.last_scroll_time = time.time()
            self.data_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.data_canvas.bind("<MouseWheel>", on_scroll)
        self.data_scrollable_frame.bind("<MouseWheel>", on_scroll)

        self.window.bind("<FocusIn>", lambda e: self.refresh_current_tab())
        self.window.after(150, self.refresh)
        self.auto_refresh_job = self.window.after(2000, self.auto_refresh)

    def on_close(self):
        self.window.after_cancel(self.auto_refresh_job)
        self.window.destroy()
        trim_memory()

    def switch_tab(self, tab):
        self.active_tab = tab
        if tab == "screentime":
            self.tab_data_frame.pack_forget()
            self.tab_st_frame.pack(fill="both", expand=True)
            self.btn_tab_st.config(bg=ACCENT, fg="#FFFFFF")
            self.btn_tab_data.config(bg=CARD_BG, fg=MUTED)
            self.refresh()
        else:
            self.tab_st_frame.pack_forget()
            self.tab_data_frame.pack(fill="both", expand=True)
            self.btn_tab_st.config(bg=CARD_BG, fg=MUTED)
            self.btn_tab_data.config(bg=ACCENT, fg="#FFFFFF")
            self.refresh_data_tab()

    def refresh_current_tab(self):
        if self.active_tab == "screentime":
            self.refresh()
        else:
            self.refresh_data_tab()

    def auto_refresh(self): 
        if time.time() - self.last_scroll_time > 3:
            self.refresh_current_tab()
        self.auto_refresh_job = self.window.after(3000, self.auto_refresh)

    def on_day_click(self, day_str):
        try:
            self.selected_data_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        except Exception:
            self.selected_data_date = date.today()
        if self.expanded_day == day_str:
            self.expanded_day = None
        else:
            self.expanded_day = day_str
        self.refresh_data_tab()

    def refresh_data_tab(self):
        if not os.path.exists(self.db_path):
            self.data_selected_total.config(text="—")
            self.data_month_total.config(text="—")
            return
        
        today = date.today()
        month_name = today.strftime("%B %Y").upper()
        self.data_month_lbl.config(text=f"{month_name} USAGE")
        
        try:
            conn = open_db_readonly(self.db_path)
            try:
                sel_sent, sel_recv = query_daily_network(conn, self.selected_data_date)
                month_sent, month_recv = query_monthly_network(conn, today.year, today.month)
                history = query_monthly_network_history(conn, today.year, today.month)
                app_breakdown = {}
                if self.expanded_day:
                    app_breakdown[self.expanded_day] = query_daily_app_network(conn, self.expanded_day)
            finally:
                conn.close()
        except sqlite3.Error:
            return

        sel_total = sel_sent + sel_recv
        month_total = month_sent + month_recv

        sel_str = self.selected_data_date.isoformat() if hasattr(self.selected_data_date, 'isoformat') else str(self.selected_data_date)
        if sel_str == today.isoformat():
            self.data_selected_lbl.config(text="TODAY'S USAGE", fg=MUTED)
        elif sel_str == (today - timedelta(days=1)).isoformat():
            self.data_selected_lbl.config(text="YESTERDAY'S USAGE", fg=ACCENT)
        else:
            self.data_selected_lbl.config(text=f"{self.selected_data_date.strftime('%b %d').upper()} USAGE", fg=ACCENT)

        self.data_selected_total.config(text=format_bytes(sel_total))
        self.data_selected_sub.config(text=f"↓ {format_bytes(sel_recv)} Download  •  ↑ {format_bytes(sel_sent)} Upload")

        self.data_month_total.config(text=format_bytes(month_total))
        self.data_month_sub.config(text=f"↓ {format_bytes(month_recv)} Download  •  ↑ {format_bytes(month_sent)} Upload")
        
        active_days = len(history)
        if active_days > 0:
            avg_bytes = month_total // active_days
            self.data_month_hint.config(text=f"{active_days} active days  •  Avg: {format_bytes(avg_bytes)}/day")
        else:
            self.data_month_hint.config(text="")

        for widget in self.data_scrollable_frame.winfo_children():
            widget.destroy()

        if not history:
            tk.Label(self.data_scrollable_frame,
                     text="No network data recorded yet.\nData will automatically accumulate as the tracker runs.",
                     bg=BG, fg=MUTED, font=(FONT_MAIN, 11), justify="center").pack(pady=40)
            return

        mx = max((s + r) for _, s, r in history) or 1
        for i, (day_str, sent, recv) in enumerate(history):
            is_expanded = (day_str == self.expanded_day)
            row = DataRow(self.data_scrollable_frame, day_str, sent, recv, mx, i, is_expanded=is_expanded, on_click=self.on_day_click)
            row.pack(fill="x", pady=(4, 0 if is_expanded else 4))

            if is_expanded:
                app_rows = app_breakdown.get(day_str, [])
                exp_container = RoundedCard(self.data_scrollable_frame, radius=12, bg_col=CARD_BG, border_col=CARD_BORDER, parent_bg=BG, padding=12)
                exp_container.pack(fill="x", padx=4, pady=(2, 6))

                head_f = tk.Frame(exp_container.container, bg=CARD_BG)
                head_f.pack(fill="x", padx=6, pady=(2, 6))
                
                try:
                    d_obj = datetime.strptime(day_str, "%Y-%m-%d").date()
                    day_name = "Today" if d_obj == today else ("Yesterday" if d_obj == today - timedelta(days=1) else d_obj.strftime("%A, %b %d"))
                except Exception:
                    day_name = day_str

                tk.Label(head_f, text=f"APPLICATION DATA USAGE  •  {day_name.upper()} ({len(app_rows)} Apps)", font=(FONT_MAIN, 9, "bold"), bg=CARD_BG, fg=MUTED).pack(side="left")
                tk.Label(head_f, text=f"Total: {format_bytes(sent + recv)}", font=(FONT_MAIN, 8, "bold"), bg=CARD_BG, fg=ACCENT).pack(side="right")

                if app_rows:
                    day_t = max(1, sent + recv)
                    for a_idx, (app_name, a_sent, a_recv, a_tot) in enumerate(app_rows):
                        a_row = AppDataRow(exp_container.container, app_name, a_sent, a_recv, day_t, a_idx)
                        a_row.pack(fill="x", pady=2)
                else:
                    tk.Label(exp_container.container,
                             text="No per-app data recorded for this day (Real-time per-app tracking active from today).",
                             bg=CARD_BG, fg=MUTED, font=(FONT_MAIN, 9), pady=10).pack()

        self.status.config(text=f"Updated {datetime.now():%H:%M:%S}")

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
        try:
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "dashboard", "--db", str(db_path)]
            else:
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                exe = str(pythonw) if pythonw.exists() else sys.executable
                cmd = [exe, str(Path(__file__).resolve()), "dashboard", "--db", str(db_path)]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            log(f"[widget] dashboard err: {e}")
    else:
        if not try_acquire_mutex("ScreenTimeTracker_Dashboard"): return
        window = tk.Tk()
        dash = Dashboard(window, db_path)
        window._dash_instance = dash
        window.mainloop()

# ─────────── Desktop Widget ───────────
class DesktopWidget:
    W, H = 320, 350
    MARGIN = 24
    DATA_REFRESH_MS = 1000   
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
        self.last_net_sent = None
        self.last_net_recv = None
        self.last_net_time = time.time()
        
        self.last_net_sent, self.last_net_recv = get_physical_net_io()

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
        self.root.after(800, trim_memory)

    def _build(self):
        header = tk.Frame(self.card, bg=CARD_BG)
        header.pack(fill="x", padx=14, pady=(10, 0))

        title_frame = tk.Frame(header, bg=CARD_BG)
        title_frame.pack(side="left")
        tk.Label(title_frame, text="●", bg=CARD_BG, fg=ACCENT, font=(FONT_MAIN, 8)).pack(side="left", padx=(0, 5))
        title_lbl = tk.Label(title_frame, text="Activity", font=(FONT_MAIN, 11, "bold"), bg=CARD_BG, fg=FG)
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

        st_frame = tk.Frame(self.card, bg=CARD_BG)
        st_frame.pack(fill="x", padx=16, pady=(6, 2))

        self.total_lbl = tk.Label(st_frame, text="—", font=(FONT_MAIN, 26, "bold"), bg=CARD_BG, fg=FG)
        self.total_lbl.pack(anchor="w")
        tk.Label(st_frame, text="SCREEN TIME TODAY", font=(FONT_MAIN, 8, "bold"), bg=CARD_BG, fg=MUTED_DARK).pack(anchor="w")

        data_box = RoundedCard(self.card, radius=14, bg_col=HOVER_BG, border_col=CARD_BORDER, parent_bg=CARD_BG, padding=12, auto_height=False)
        data_box.pack(fill="both", expand=True, padx=14, pady=(6, 14))

        inner_data = tk.Frame(data_box.container, bg=HOVER_BG)
        inner_data.pack(fill="both", expand=True)

        data_head = tk.Frame(inner_data, bg=HOVER_BG)
        data_head.pack(fill="x")
        tk.Label(data_head, text="TODAY'S DATA", font=(FONT_MAIN, 8, "bold"), bg=HOVER_BG, fg=MUTED).pack(side="left")
        self.net_month_lbl = tk.Label(data_head, text="Month: —", font=(FONT_MAIN, 8), bg=HOVER_BG, fg=MUTED_DARK)
        self.net_month_lbl.pack(side="right")

        self.net_today_lbl = tk.Label(inner_data, text="—", font=(FONT_MAIN, 20, "bold"), bg=HOVER_BG, fg=FG)
        self.net_today_lbl.pack(anchor="w", pady=(2, 1))

        self.net_sub_lbl = tk.Label(inner_data, text="↓ 0 B  •  ↑ 0 B", font=(FONT_MAIN, 8), bg=HOVER_BG, fg=MUTED)
        self.net_sub_lbl.pack(anchor="w")

        div = tk.Frame(inner_data, bg=CARD_BORDER, height=1)
        div.pack(fill="x", pady=(7, 6))

        speed_head = tk.Frame(inner_data, bg=HOVER_BG)
        speed_head.pack(fill="x")
        dot_speed = tk.Label(speed_head, text="●", bg=HOVER_BG, fg=SUCCESS, font=(FONT_MAIN, 7))
        dot_speed.pack(side="left", padx=(0, 4))
        tk.Label(speed_head, text="LIVE TRAFFIC SPEED", font=(FONT_MAIN, 8, "bold"), bg=HOVER_BG, fg=MUTED).pack(side="left")

        speed_val_frame = tk.Frame(inner_data, bg=HOVER_BG)
        speed_val_frame.pack(fill="x", pady=(3, 0))
        self.speed_down_lbl = tk.Label(speed_val_frame, text="↓ 0 B/s", font=(FONT_MAIN, 11, "bold"), bg=HOVER_BG, fg="#64D2FF")
        self.speed_down_lbl.pack(side="left")
        self.speed_up_lbl = tk.Label(speed_val_frame, text="   ↑ 0 B/s", font=(FONT_MAIN, 11, "bold"), bg=HOVER_BG, fg="#FF9F0A")
        self.speed_up_lbl.pack(side="left")

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

        for drag_target in (header, title_frame, title_lbl, st_frame, self.total_lbl):
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
        
        popup.update_idletasks()
        p_hwnd = user32.GetAncestor(popup.winfo_id(), 2) or popup.winfo_id()
        if p_hwnd:
            p_rgn = gdi32.CreateRoundRectRgn(0, 0, 341, 81, 16, 16)
            user32.SetWindowRgn(p_hwnd, p_rgn, True)
        
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
        
        temp_dir = os.environ.get('TEMP')
        cutoff = time.time() - 86400
        if temp_dir and os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                try:
                    item_path = os.path.join(temp_dir, item)
                    if os.path.islink(item_path): continue
                    mtime = os.path.getmtime(item_path)
                    if mtime > cutoff: continue
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
        now = time.time()
        dt = max(0.1, now - self.last_net_time)
        speed_sent, speed_recv = 0.0, 0.0
        
        cur_net_sent, cur_net_recv = get_physical_net_io()
        if self.last_net_sent is not None and self.last_net_recv is not None:
            d_sent = max(0, cur_net_sent - self.last_net_sent)
            d_recv = max(0, cur_net_recv - self.last_net_recv)
            
            # SPIKE PROTECTION
            if d_sent > 50 * 1024 * 1024 or d_recv > 50 * 1024 * 1024:
                d_sent, d_recv = 0, 0
                
            speed_sent = d_sent / dt
            speed_recv = d_recv / dt
            
        self.last_net_sent = cur_net_sent
        self.last_net_recv = cur_net_recv
        self.last_net_time = now

        if hasattr(self, "speed_down_lbl") and hasattr(self, "speed_up_lbl"):
            self.speed_down_lbl.config(text=f"↓ {format_speed(speed_recv)}")
            self.speed_up_lbl.config(text=f"   ↑ {format_speed(speed_sent)}")

        if not os.path.exists(self.db_path):
            self.total_lbl.config(text="—")
            self.net_today_lbl.config(text="—")
            self.net_sub_lbl.config(text="↓ 0 B  •  ↑ 0 B")
            self.net_month_lbl.config(text="Month: —")
            return
        today = date.today()
        try:
            conn = open_db_readonly(self.db_path)
            try:
                total_screen = query_daily_total(conn, today)
                today_sent, today_recv = query_daily_network(conn, today)
                month_sent, month_recv = query_monthly_network(conn, today.year, today.month)
            finally:
                conn.close()
        except sqlite3.Error:
            return

        self.total_lbl.config(text=format_duration(total_screen))
        today_net = today_sent + today_recv
        month_net = month_sent + month_recv
        
        self.net_today_lbl.config(text=format_bytes(today_net))
        self.net_sub_lbl.config(text=f"↓ {format_bytes(today_recv)}  •  ↑ {format_bytes(today_sent)}")
        self.net_month_lbl.config(text=f"Month: {format_bytes(month_net)}")

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

    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            legacy_vbs = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "ScreenTimeTracker.vbs"
            if legacy_vbs.exists(): legacy_vbs.unlink()
    except Exception: pass

def main():
    attach_input_desktop()
    p = argparse.ArgumentParser()
    p.add_argument("mode", nargs="?", default="both", choices=["track", "widget", "dashboard", "both", "startup", "test"])
    p.add_argument("--db", help="Custom DB"); p.add_argument("--idle", type=int, default=180); p.add_argument("--pinned", action="store_true")
    args = p.parse_args()
    db_path = Path(args.db) if args.db else get_db_path()

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
        open_dashboard(None, db_path)
    else:
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"): return
        if not try_acquire_mutex("ScreenTimeTracker_Widget"): return
        stop = threading.Event()
        t = threading.Thread(target=run_tracker, daemon=True, args=(db_path,), kwargs={"idle_threshold": args.idle, "stop_event": stop})
        t.start()
        try: open_widget(db_path, force_pinned=args.pinned)
        finally: stop.set(); t.join(timeout=2)

if __name__ == "__main__":
    main()