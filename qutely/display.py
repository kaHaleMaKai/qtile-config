from __future__ import annotations

import os
import sys
import yaml
import pywal
from pathlib import Path
from typing import TypedDict, Any
from libqtile.log_utils import logger


THEME_BG_KEY = "QTILE_LIGHT_THEME"


class ScreensDict(TypedDict):
    _primary: PhysicalScreen
    screens: dict[str, PhysicalScreen]


class PhysicalScreen(TypedDict):
    width: int
    height: int
    is_primary: bool
    xoffset: int
    yoffset: int


def get_screens() -> ScreensDict:
    import gi  # type: ignore[import]

    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk  # type: ignore[import]

    screens: ScreensDict = {"_primary": {}, "screens": {}}  # type: ignore[typeddict-item]

    gdkdsp = Gdk.Display.get_default()
    for i in range(gdkdsp.get_n_monitors()):
        monitor = gdkdsp.get_monitor(i)
        scale = monitor.get_scale_factor()
        geo = monitor.get_geometry()
        name = monitor.get_model()
        screen: PhysicalScreen = {
            "width": geo.width * scale,
            "height": geo.height * scale,
            "is_primary": monitor.is_primary(),
            "xoffset": geo.x * scale,
            "yoffset": geo.y * scale,
        }
        screens["screens"][name] = screen
        if screen["is_primary"]:
            screens["_primary"] = screen
    logger.error(screens)
    return screens


def is_laptop(name: str) -> bool:
    return name in get_screens()["screens"]


def is_only_laptop(name: str) -> bool:
    screens = get_screens()["screens"]
    return name in screens and len(screens) == 1


if "config" in sys.modules.keys() or os.environ.get("TEST_QTILE_FROM_CLI"):
    screens = get_screens()
    res = [{"width": s["width"], "height": s["height"]} for s in screens["screens"].values()]
    num_screens = len(screens["screens"])


light_theme_marker_file = Path("/tmp/qtile-light-theme")
is_light_theme = os.environ.get(THEME_BG_KEY, "") == "1"
if is_light_theme:
    light_theme_marker_file.touch()
else:
    light_theme_marker_file.unlink(missing_ok=True)


def get_wal_colors() -> dict[str, Any]:
    yaml_file = os.path.join(pywal.colors.CACHE_DIR, "colors.yml")
    if not os.path.exists(yaml_file):
        wallpaper = os.path.expanduser("~/.wallpaper")
        colors = pywal.colors.get(wallpaper)
        pywal.export.every(colors)
    else:
        with open(yaml_file, "r") as f:
            colors = yaml.load(f.read(), Loader=yaml.BaseLoader)
    # all_colors = ["#" + complement(c, 0.4) if 1 < i < 9 else c for i, c in enumerate(colors["colors"].values())]
    all_colors = colors["colors"].values()
    return {
        "colors": all_colors,
        "bg": colors["special"]["background"],
        "fg": colors["special"]["foreground"],
        "cursor": colors["special"]["cursor"],
    }
