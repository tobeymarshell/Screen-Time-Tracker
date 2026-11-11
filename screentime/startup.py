"""Windows Registry and Startup registration management."""

import os
from pathlib import Path
import sys
import winreg

def install_startup():
    """Registers application in HKCU Run key and removes legacy shortcuts."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        if getattr(sys, 'frozen', False):
            cmd = f'"{sys.executable}" both'
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            if not pythonw.exists():
                pythonw = Path(sys.executable)
            cmd = f'"{pythonw}" "{Path(__file__).resolve().parent.parent / "screen_time.py"}" both'
        winreg.SetValueEx(key, "ScreenTimeTracker", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        try:
            if sys.stdout is not None:
                print("[startup] Registered in HKCU Run key", flush=True)
        except Exception:
            pass
    except Exception as e:
        try:
            if sys.stdout is not None:
                print(f"[startup] Failed to add to registry: {e}", flush=True)
        except Exception:
            pass

    # Clean legacy VBScript from Startup folder if present
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            legacy_vbs = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "ScreenTimeTracker.vbs"
            if legacy_vbs.exists():
                legacy_vbs.unlink()
    except Exception:
        pass
