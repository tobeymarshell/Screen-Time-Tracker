"""System optimization utilities: RAM trimming, background CPU offloading, temp & cache cleanup."""

import ctypes
from ctypes import wintypes
import os
import shutil
import subprocess
import time
from typing import Tuple
import psutil

from .win32 import (
    user32,
    kernel32,
    psapi,
    shell32,
    SHQUERYRBINFO,
)

SYSTEM_IGNORE_PROCESSES = {
    "explorer.exe", "dwm.exe", "audiodg.exe", "system", "registry",
    "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "svchost.exe", "fontdrvhost.exe", "winlogon.exe", "spoolsv.exe",
    "textinputhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "searchhost.exe", "taskmgr.exe", "screentime.exe", "python.exe", "pythonw.exe"
}

def clean_temp_files(max_age_hours: int = 24) -> int:
    """Deletes temp files older than max_age_hours without traversing symlinks."""
    freed = 0
    temp_dir = os.environ.get("TEMP")
    cutoff = time.time() - (max_age_hours * 3600)
    if not temp_dir or not os.path.exists(temp_dir):
        return 0

    for item in os.listdir(temp_dir):
        try:
            item_path = os.path.join(temp_dir, item)
            if os.path.islink(item_path):
                continue
            if os.path.getmtime(item_path) > cutoff:
                continue
            if os.path.isdir(item_path):
                sz = 0
                for root_dir, _, files in os.walk(item_path):
                    for f in files:
                        fp = os.path.join(root_dir, f)
                        if not os.path.islink(fp):
                            try:
                                sz += os.path.getsize(fp)
                            except Exception:
                                pass
                shutil.rmtree(item_path, ignore_errors=True)
                freed += sz
            else:
                freed += os.path.getsize(item_path)
                os.remove(item_path)
        except Exception:
            pass
    return freed

def empty_recycle_bin() -> int:
    """Queries and empties the Windows Recycle Bin without UI prompts."""
    freed = 0
    try:
        rb_info = SHQUERYRBINFO()
        rb_info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        if shell32.SHQueryRecycleBinW(None, ctypes.byref(rb_info)) == 0:
            freed = rb_info.i64Size
        shell32.SHEmptyRecycleBinW(None, None, 7)
    except Exception:
        pass
    return freed

def flush_dns():
    """Flushes Windows DNS cache in the background."""
    try:
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        ipconfig_exe = os.path.join(sys_root, "System32", "ipconfig.exe")
        if os.path.exists(ipconfig_exe):
            subprocess.Popen([ipconfig_exe, "/flushdns"], creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

def trim_working_sets():
    """Calls EmptyWorkingSet across accessible non-self processes to reclaim RAM."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.pid != os.getpid():
                handle = kernel32.OpenProcess(0x0100 | 0x0400, False, proc.pid)
                if handle:
                    psapi.EmptyWorkingSet(handle)
                    kernel32.CloseHandle(handle)
        except Exception:
            pass

def offload_background_cpu(fg_pid: int = 0) -> int:
    """Sets background/idle processes to BELOW_NORMAL_PRIORITY_CLASS to prioritize active foreground work."""
    cpu_offloaded = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pid = proc.pid
            if pid == os.getpid() or pid == fg_pid:
                continue
            pname = (proc.info['name'] or "").lower()
            if pname in SYSTEM_IGNORE_PROCESSES:
                continue
            if proc.nice() == psutil.NORMAL_PRIORITY_CLASS:
                proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                cpu_offloaded += 1
        except Exception:
            pass
    return cpu_offloaded

def run_system_cleanup() -> Tuple[int, int, int]:
    """Runs complete system optimization: returns (ram_freed, disk_freed, cpu_offloaded)."""
    ram_before = psutil.virtual_memory().available
    freed_disk = clean_temp_files(24) + empty_recycle_bin()
    flush_dns()
    trim_working_sets()

    # Determine current foreground window PID to protect from throttling
    fg_pid = 0
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        pid_box = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_box))
        fg_pid = pid_box.value

    cpu_offloaded = offload_background_cpu(fg_pid=fg_pid)
    time.sleep(0.5)
    ram_after = psutil.virtual_memory().available
    ram_freed = max(0, ram_after - ram_before)

    return ram_freed, freed_disk, cpu_offloaded
