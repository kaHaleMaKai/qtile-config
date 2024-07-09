from __future__ import annotations

import os
import sys
import json
import yaml
import pywal
from pathlib import Path
from typing import TypedDict, Any, Iterable, NamedTuple
from libqtile.log_utils import logger
from asyncio.subprocess import create_subprocess_exec as new_proc, PIPE
from qutely.helpers import lazy_coro


THEME_BG_KEY = "QTILE_LIGHT_THEME"


class ScreensDict(TypedDict):
    _primary: PhysicalScreen
    screens: dict[str, VirtualScreen]


class VirtualScreen(NamedTuple):
    width: int
    height: int
    min_width: int
    max_width: int
    min_height: int
    max_height: int
    primary: PhysicalScreen | None
    connected: list[PhysicalScreen]
    in_use: list[PhysicalScreen]
    disconnected: list[PhysicalScreen]
    all_used: bool
    by_name: dict[str, PhysicalScreen]
    num_screens: int


class PhysicalScreen(NamedTuple):
    name: str
    width: int
    height: int
    xoffset: int
    yoffset: int
    is_primary: bool
    is_connected: bool
    is_used: bool
    rotation: str
    reflection: str
    mm_width: int
    mm_height: int


def _parse_device(dev: dict[str, Any]) -> PhysicalScreen:
    return PhysicalScreen(
        name=dev["device_name"],
        is_connected=dev["is_connected"],
        is_primary=dev["is_primary"],
        rotation=dev["rotation"],
        reflection=dev["reflection"],
        width=dev.get("resolution_width", 0),
        height=dev.get("resolution_height", 0),
        mm_width=dev.get("dimension_width", 0),
        mm_height=dev.get("dimension_height", 0),
        xoffset=dev.get("offset_width", 0),
        yoffset=dev.get("offset_height", 0),
        is_used=dev.get("resolution_width", 0) > 0,
    )


def parse_xrandr(input: str) -> VirtualScreen:
    v_screen = json.loads(input)["screens"][0]
    screens = [_parse_device(d) for d in v_screen["devices"]]
    connected = [s for s in screens if s.is_connected]
    disconnected = [s for s in screens if not s.is_connected]
    in_use = [s for s in connected if s.is_used]
    primary: PhysicalScreen | None
    if p := [s for s in connected if s.is_primary]:
        primary = p[0]
    else:
        primary = None
    all_used = set(connected) == set(in_use)

    return VirtualScreen(
        min_width=v_screen["minimum_width"],
        max_width=v_screen["maximum_width"],
        width=v_screen["current_width"],
        min_height=v_screen["minimum_height"],
        max_height=v_screen["maximum_height"],
        height=v_screen["current_height"],
        connected=connected,
        disconnected=disconnected,
        primary=primary,
        by_name={s.name: s for s in screens},
        in_use=in_use,
        all_used=all_used,
        num_screens=len(in_use),
    )


def sync_get_xrandr_output() -> VirtualScreen:
    from subprocess import Popen as new_proc, PIPE

    proc = new_proc(args=["xrandr"], stdout=PIPE, stderr=PIPE, text=True)
    stdout, stderr = proc.communicate()
    jc = new_proc(args=["jc", "--xrandr"], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True)
    stdout, stderr = jc.communicate(input=stdout)
    return parse_xrandr(stdout)


async def get_xrandr_output() -> VirtualScreen:
    proc = await new_proc("xrandr", stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    jc = await new_proc("jc", "--xrandr", stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await jc.communicate(input=stdout)
    return parse_xrandr(stdout.decode())


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
    v_screen = sync_get_xrandr_output()
    return name in v_screen.by_name


def is_only_laptop(name: str) -> bool:
    v_screen = sync_get_xrandr_output()
    return len(v_screen.in_use) == 1 and v_screen.in_use[0].name == name


if "config" in sys.modules.keys() or os.environ.get("TEST_QTILE_FROM_CLI"):
    screen = sync_get_xrandr_output()
    res = [{"width": s.width, "height": s.height} for s in screen.in_use]
    num_screens = len(screen.in_use)


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
