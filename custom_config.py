import re
from libqtile.config import Screen, Group, Drag, Click, Match
from libqtile.command import lazy
from libqtile import hook, layout

from typing import List  # noqa: F401

# custom imports – parts of config

import procs
from floating_rules import get_floating_rules
from key_config import keys, mod_key
from opacity import add_opacity  # NOQA
from bar import get_bar
from util import num_screens, go_to_group


group_dict = {name: Group(name) for name in "123456789abcdef"}
groups = sorted([g for g in group_dict.values()], key=lambda g: g.name)

matcher = {
    "c": Match(title=[re.compile(".*(Mattermost|WhatsApp).*")]),
    "e": Match(wm_class=["Evolution"]),
    "f": Match(wm_class=[re.compile("Firefox.*")]),
}
for g, match in matcher.items():
    group_dict[g].matches.append(match)

for group in groups:
    keys.add_keys({
        f"M-{group.name}": go_to_group(group),
        f"M-S-{group.name}": lazy.window.togroup(group.name),
    })

layouts = [
    layout.Bsp(border_width=0),
    layout.MonadTall(border_width=0),
    layout.MonadWide(border_width=0),
    layout.Columns(border_width=0, insert_position=1),
    layout.Matrix(border_width=0, insert_position=1),
    layout.RatioTile(border_width=0),
    layout.Tile(border_width=0),
    layout.VerticalTile(border_width=0),
    layout.Zoomy(columnwidth=450),
    layout.TreeTab(border_width=0),
]

widget_defaults = dict(
    font='sans',
    fontsize=10,
    padding=3,
)
extension_defaults = widget_defaults.copy()

screens = [Screen(top=get_bar(idx)) for idx in range(num_screens)]

# Drag floating layouts.
mouse = [
    Drag([mod_key], "Button1", lazy.window.set_position(),
         start=lazy.window.get_position()),
    Drag([mod_key], "Button3", lazy.window.set_size_floating(),
         start=lazy.window.get_size()),
    Click([mod_key], "Button2", lazy.window.bring_to_front())
]

dgroups_key_binder = None
dgroups_app_rules = []  # type: List
main = None
follow_mouse_focus = True
bring_front_click = False
cursor_warp = True
floating_layout = layout.Floating(float_rules=get_floating_rules())
auto_fullscreen = True
focus_on_window_activation = "smart"
wmname = "LG3D"


@hook.subscribe.startup_once
def autostart():
    print("auto-starting commands")
    procs.feh()
    procs.setxkbmap()
    procs.unclutter()
    procs.xcompmgr()
    procs.network_manager()
    procs.xfce4_power_manager()
    procs.screensaver()
    procs.xss_lock()
    procs.shiftred()


@hook.subscribe.screen_change
def screen_change(qtile, event):
    procs.feh()
    qtile.cmd_restart()
