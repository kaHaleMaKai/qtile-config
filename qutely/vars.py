from __future__ import annotations

from typing import Any
from qutely.display import (
    is_only_laptop,
    is_light_theme,
    num_screens,
    res,
    get_wal_colors,
)
from qutely.debug import in_debug_mode

laptop_screen = "eDP1"

_config = {
    "dunstrc": {
        "font": "Hack",
        "fontsize": 9 if is_only_laptop(laptop_screen) else 11,
        "icon_path": "/usr/share/icons/HighContrast/16x16",
        "width": [120, 250],
        "height": 400,
        "offset": [20, 50],
        "urgency": {
            "low": {"bg": "#323200", "fg": "#e0e000", "frame": "#a0a000", "timeout": "5"},
            "normal": {"bg": "#301000", "frame": "#e37000", "fg": "#ff8000", "timeout": "30"},
            "critical": {"bg": "#600000", "frame": "#980000", "fg": "#ff6060", "timeout": "0"},
        },
    },
    "compositor": {
        "menu_opacity": 0.98,
        "shadow": True,
        "shadow_radius": 10,
        "shadow_offset": -5,
        "shadow_opacity": 0.3,
        "fading": True,
        "fade_in_step": 0.06,
        "backend": "glx",
        "vsync": "drm",
        "shadow_excludes": [
            {"name": "Notification"},
            {"class": "Conkey"},
            {"class": "Notify-osd", "op": "?="},
            {"class": "Cairo-clock"},
            {"var": "QTILE_INTERNAL:32c", "value": 1},
            {"class": "Dunst"},
        ],
    },
    "terminalrc": {"bg": "#0d0d00"},
    "kitty.conf": {"font": {"family": "Hack", "size": 9 if is_only_laptop(laptop_screen) else 8}},
}

_config["compton.conf"] = _config["picom.conf"] = _config["compositor"]


def get_light_colors() -> dict[str, str | list[str]]:
    return {
        "bg": "#fffffe",
        "fg": "#000001",
        "colors": [
            "#000000",
            "#cd0000",
            "#00cd00",
            "#cdcd00",
            "#0000cd",
            "#cd00cd",
            "#00cdcd",
            "#e5e5e5",
            "#7f7f7f",
            "#ff0000",
            "#00ff00",
            "#ffff00",
            "#5c5cff",
            "#ff00ff",
            "#00ffff",
            "#ffffff",
        ],
    }


def get_defaults() -> dict[str, Any]:
    default_vars = {
        "defaults": {
            "num_screens": num_screens,
            "res": res,
            "in_debug_mode": in_debug_mode,
        },
        "wal": get_light_colors() if is_light_theme else get_wal_colors(),
    }
    return default_vars


def get_config(key: str) -> dict[str, Any]:
    sub_config = _config[key.replace(".j2", "")]
    return sub_config | get_defaults()
