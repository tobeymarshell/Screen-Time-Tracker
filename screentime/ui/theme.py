"""Professional dark glass UI theme, palette, and formatting utilities."""

import tkinter as tk

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

def format_app_name(raw_name: str) -> str:
    """Transforms raw executable names into clean, readable app titles."""
    if not raw_name:
        return "Unknown"
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

def round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, fill: str, outline: str = ""):
    """Draws a smooth rounded rectangle on a Tkinter Canvas."""
    r = min(r, max(1, abs(x2 - x1) // 2), max(1, abs(y2 - y1) // 2))
    canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, fill=fill, outline=outline)
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")

def format_duration(seconds: float, short: bool = False) -> str:
    """Formats seconds into human-readable duration strings."""
    seconds = max(0, int(seconds))
    h, m = seconds // 3600, (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m" if not short else f"{h}h{m:02d}"
    return f"{m}m"

def format_bytes(b: float) -> str:
    """Formats byte counts into KB, MB, or GB."""
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    else:
        return f"{b / (1024 * 1024 * 1024):.2f} GB"
