import re
from typing import Iterable
from libqtile.config import Match
from libqtile.layout import Floating
from libqtile.backend.x11.window import Window, XWindow


ZOOM_PATTERN = re.compile("^join.*action")

rules = {
    "wm_class": [
        "confirm",
        "dialog",
        "download",
        "error",
        "feh-modal",
        "file_progress",
        "notification",
        "splash",
        "toolbar",
        "ssh-askpass",
        "Arandr",
        "Gpick",
        "Kruler",
        "MessageWin",
        "Sxiv",
        "Wpa_gui",
        "pinentry",
        "veromix",
        "MPlayer",
        "pinentry",
        "Gimp",
        "Shutter",
        "xtightvncviewer",
        "kazam",
        "Msgcompose",
        "Xfce4-power-manager-settings",
        re.compile("^Polkit-gnome-authentication-agent.*"),
        "fontforge",
        "OneDriveGUI",
        "wpp",
        "Nm-connection-editor",
        "Blueman-manager",
        "PanGPUI",
        "Nextcloud",
    ],
    "wm_name": [
        "pinentry",
        "Event Tester",
        "TbSync account manager",
    ],
    "role": [
        "AlarmWindow",
        "pop-up",
        "filterlist",
    ],
}

onscreen_floaters = {
    "opensnitch-ui": {"type": "diaglog"},
    "PanGPUI": None,
    "OneDriveGUI": None,
    "Nextcloud": None,
}


def identify_floating(window: Window) -> bool:
    if not (classes := window.get_wm_class()):
        return
    cls_name, cls = [c.lower() for c in classes]

    if cls == "zoom":
        return bool(ZOOM_PATTERN.match(cls_name))
    return False


floating_dimensions = {
    "nm-openconnect-auth-dialog": (700, 800),
    "arandr": (600, 600),
}


def generate_floating_rules(rules: dict[str, Iterable[str]]) -> Iterable[Match]:
    yield from Floating.default_float_rules
    for key in ("wm_class", "role"):
        for item in rules[key]:
            yield Match(**{key: item})


def get_floating_rules() -> list[Match]:
    return list(generate_floating_rules(rules))
