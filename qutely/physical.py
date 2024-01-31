from __future__ import annotations

from typing import TypedDict


class PhysicalScreen(TypedDict):
    width: int
    height: int


def get_physical_screens() -> dict[str, PhysicalScreen]:
    import gi

    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    screens: dict[str, PhysicalScreen] = {}

    gdkdsp = Gdk.Display.get_default()
    for i in range(gdkdsp.get_n_monitors()):
        monitor = gdkdsp.get_monitor(i)
        scale = monitor.get_scale_factor()
        geo = monitor.get_geometry()
        name = monitor.get_model()
        screen: PhysicalScreen = {
            "width": geo.width * scale,
            "height": geo.height * scale,
        }
        screens[name] = screen

    return screens


def is_laptop(name: str) -> bool:
    return name in get_physical_screens()


def is_only_laptop(name: str) -> bool:
    screens = get_physical_screens()
    return name in screens and len(screens) == 1
