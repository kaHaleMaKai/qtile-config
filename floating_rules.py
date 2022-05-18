import re
from libqtile.config import Match
from libqtile.layout import Floating
from typing import Iterable

rules = {
    "wm_class": [
        "confirm",
        "dialog",
        "download",
        "error",
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
        re.compile("^Polkit-gnome-authentication-agent.*"),
    ],
    "wm_name": [
        "pinentry",
        "Event Tester",
        "TbSync account manager",
    ],
    "role": [
        "AlarmWindow",
        "pop-up",
    ],
}


def generate_floating_rules(rules: dict[str, Iterable[str]]) -> Iterable[Match]:
    yield from Floating.default_float_rules
    for key in ("wm_class", "role"):
        for item in rules[key]:
            yield Match(**{key: item})

    # if "wm_name" in rules:
    #     for item in rules["wm_name"]:
    #         yield Match(func=lambda win: win.)


def get_floating_rules() -> list[Match]:
    return list(generate_floating_rules(rules))
