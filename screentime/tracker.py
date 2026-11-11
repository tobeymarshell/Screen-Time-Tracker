"""Active foreground application tracker thread."""

import ctypes
from ctypes import wintypes
from pathlib import Path
import sqlite3
import threading
import time
from typing import Optional
import psutil

from .win32 import (
    user32,
    get_idle_seconds,
    get_foreground_process_name,
    get_foreground_window_title,
)
from .storage import (
    init_db,
    save_session,
)

def run_tracker(
    db_path: Path,
    idle_threshold: int = 60,
    poll_interval: float = 1.0,
    stop_event: Optional[threading.Event] = None
):
    """Monitors active foreground window, logs duration, and checkpoints every 60s."""
    conn = sqlite3.connect(str(db_path))
    init_db(conn)
    current_app = None
    current_title = ""
    session_start = None

    try:
        while stop_event is None or not stop_event.is_set():
            now = time.time()
            idle = get_idle_seconds()

            if idle >= idle_threshold:
                if current_app and session_start is not None:
                    idle_began = now - idle
                    if idle_began > session_start:
                        save_session(conn, current_app, current_title, session_start, idle_began)
                current_app, session_start = None, None
            else:
                hwnd = user32.GetForegroundWindow()
                class_name = ctypes.create_unicode_buffer(256)
                if hwnd:
                    user32.GetClassNameW(hwnd, class_name, 256)

                if class_name.value in ("Progman", "WorkerW"):
                    app, title = "Desktop", "Home Screen"
                else:
                    app = get_foreground_process_name()
                    title = get_foreground_window_title()

                if app != current_app:
                    if current_app and session_start is not None:
                        save_session(conn, current_app, current_title, session_start, now)
                    current_app, current_title, session_start = app, title, now

                    # Restore priority if app was previously deprioritized by CPU offloader
                    if hwnd:
                        fg_pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(fg_pid))
                        if fg_pid.value:
                            try:
                                fp = psutil.Process(fg_pid.value)
                                if fp.nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS:
                                    fp.nice(psutil.NORMAL_PRIORITY_CLASS)
                            except Exception:
                                pass
                else:
                    current_title = title
                    # Periodic 60s checkpoint for live widget updating and crash / midnight resiliency
                    if current_app and session_start is not None and (now - session_start >= 60.0):
                        save_session(conn, current_app, current_title, session_start, now)
                        session_start = now

            if stop_event is not None:
                if stop_event.wait(poll_interval):
                    break
            else:
                time.sleep(poll_interval)
    except KeyboardInterrupt:
        pass
    finally:
        if current_app and session_start is not None:
            save_session(conn, current_app, current_title, session_start, time.time())
        conn.close()
