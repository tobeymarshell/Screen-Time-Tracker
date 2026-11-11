"""Command-line interface and test runner for ScreenTime Tracker."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import sys
import threading
import psutil

from .win32 import (
    try_acquire_mutex,
    get_idle_seconds,
)
from .storage import (
    get_db_path,
    init_db,
    save_session,
    query_daily_total,
    query_top_apps,
    query_daily_totals_range,
)
from .tracker import run_tracker
from .startup import install_startup
from .ui.theme import (
    format_app_name,
    format_duration,
    format_bytes,
)
from .ui.widget import open_widget
from .ui.dashboard import open_dashboard

def run_self_tests():
    """Executes assert-based verification across formatting, database, and process APIs."""
    print("[TEST] Running ScreenTime self-tests...")

    # 1. Formatting helpers
    assert format_duration(0) == "0m"
    assert format_duration(3665) == "1h 1m"
    assert format_duration(3665, short=True) == "1h01"
    assert format_duration(45) == "0m"
    assert "KB" in format_bytes(1024)
    assert "MB" in format_bytes(1024 * 1024 * 5)
    assert format_app_name("code.exe") == "VS Code"
    assert format_app_name("chrome.exe") == "Google Chrome"
    assert format_app_name("windowsterminal.exe") == "Terminal"
    assert format_app_name("") == "Unknown"

    # 2. 64-bit Tick count idle check
    idle = get_idle_seconds()
    assert isinstance(idle, float) and idle >= 0.0, f"Invalid idle seconds: {idle}"

    # 3. Database operations & Query Polymorphism (date vs str)
    conn = sqlite3.connect(":memory:")
    init_db(conn)

    indices = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
    assert "idx_sessions_day" in indices, "idx_sessions_day index was not created"

    t0 = 1700000000
    test_d = datetime.fromtimestamp(t0).date()
    test_d_str = test_d.isoformat()

    # Edge cases: empty app, zero duration
    save_session(conn, "", "Doc", t0, t0 + 100)
    save_session(conn, "code.exe", "Doc", t0, t0)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0

    # Valid sessions
    save_session(conn, "code.exe", "SuperSecretDoc.txt - VS Code", t0, t0 + 120)
    save_session(conn, "chrome.exe", "Web Page", t0 + 120, t0 + 240)

    # Privacy check: window title must be empty string
    rows = conn.execute("SELECT app_name, window_title, duration_seconds FROM sessions").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == "code.exe" and rows[0][1] == "" and rows[0][2] == 120
    assert rows[1][0] == "chrome.exe" and rows[1][1] == "" and rows[1][2] == 120

    # Query with date object
    assert query_daily_total(conn, test_d) == 240
    top = query_top_apps(conn, test_d)
    assert len(top) == 2
    assert top[0][1] == 120

    # Query with str object
    assert query_daily_total(conn, test_d_str) == 240
    top_str = query_top_apps(conn, test_d_str)
    assert len(top_str) == 2

    # Query range with both date and str
    rng_d = query_daily_totals_range(conn, test_d, test_d)
    assert len(rng_d) == 1 and rng_d[0][1] == 240
    rng_s = query_daily_totals_range(conn, test_d_str, test_d_str)
    assert len(rng_s) == 1 and rng_s[0][1] == 240

    conn.close()

    # 4. Mutex isolation
    test_mutex_name = f"ScreenTime_SelfTest_{os.getpid()}"
    m1 = try_acquire_mutex(test_mutex_name)
    assert m1 is not None, "Failed to acquire first mutex instance"
    m2 = try_acquire_mutex(test_mutex_name)
    assert m2 is None, "Duplicate mutex was improperly acquired!"

    # 5. Process priority manipulation check
    self_proc = psutil.Process(os.getpid())
    orig_nice = self_proc.nice()
    try:
        self_proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        assert self_proc.nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS
    finally:
        self_proc.nice(orig_nice)

    print("[TEST] All self-tests passed successfully!")

def main():
    """Main CLI entry point for ScreenTime Tracker."""
    p = argparse.ArgumentParser(description="ScreenTime Tracker & Desktop Widget")
    p.add_argument("mode", nargs="?", default="both", choices=["track", "widget", "dashboard", "both", "startup", "test"])
    p.add_argument("--db", help="Path to custom database")
    p.add_argument("--idle", type=int, default=60, help="Idle threshold in seconds (default: 60)")
    p.add_argument("--pinned", action="store_true", help="Force widget floating pinned mode")
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
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"):
            return
        run_tracker(db_path, idle_threshold=args.idle)
    elif args.mode == "widget":
        if not try_acquire_mutex("ScreenTimeTracker_Widget"):
            return
        open_widget(db_path, force_pinned=args.pinned)
    elif args.mode == "dashboard":
        if not try_acquire_mutex("ScreenTimeTracker_Dashboard"):
            return
        open_dashboard(None, str(db_path))
    else:
        # Mode: both
        if not try_acquire_mutex("ScreenTimeTracker_Tracker"):
            return
        if not try_acquire_mutex("ScreenTimeTracker_Widget"):
            return
        stop = threading.Event()
        t = threading.Thread(
            target=run_tracker,
            daemon=True,
            args=(db_path,),
            kwargs={"idle_threshold": args.idle, "stop_event": stop}
        )
        t.start()
        try:
            open_widget(db_path, force_pinned=args.pinned)
        finally:
            stop.set()
            t.join(timeout=2)
