"""UI package for Screen Time Tracker."""

from .dashboard import Dashboard, open_dashboard
from .widget import DesktopWidget, open_widget
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
    SUCCESS,
    COLORS,
    FONT_MAIN,
    FONT_TEXT,
    round_rect,
    format_app_name,
    format_duration,
    format_bytes,
)

__all__ = [
    "Dashboard",
    "open_dashboard",
    "DesktopWidget",
    "open_widget",
    "BG",
    "CARD_BG",
    "CARD_BORDER",
    "HOVER_BG",
    "FG",
    "MUTED",
    "MUTED_DARK",
    "ACCENT",
    "TRACK_BG",
    "SUCCESS",
    "COLORS",
    "FONT_MAIN",
    "FONT_TEXT",
    "round_rect",
    "format_app_name",
    "format_duration",
    "format_bytes",
]
