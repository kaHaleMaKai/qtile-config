import re
from libqtile.config import Screen, Group, Drag, Click, Match
from libqtile.command import lazy
from libqtile import hook, layout

from typing import List  # noqa: F401

# custom imports – parts of config

import procs
import color
from floating_rules import get_floating_rules
from key_config import keys, mod_key
from opacity import add_opacity  # NOQA
from bar import get_bar
import util


group_dict = {name: Group(name) for name in "123456789abcdef"}
groups = sorted([g for g in group_dict.values()], key=lambda g: g.name)

matcher = {
    "c": Match(title=[re.compile(".*(Mattermost|WhatsApp).*")]),
    "e": Match(wm_class=["Evolution", "Thunderbird"]),
    "f": Match(wm_class=[re.compile("Firefox.*")]),
}
for g, match in matcher.items():
    group_dict[g].matches.append(match)

for group in groups:
    keys.add_keys({
        f"M-{group.name}": util.go_to_group(group),
        f"M-S-{group.name}": lazy.window.togroup(group.name),
    })

layout_settings = {}
layout_settings["border_width"] = 0

layouts = [
    layout.Bsp(border_focus=color.BLACK, border_normal=color.BLACK, **layout_settings),
    layout.MonadTall(**layout_settings),
    layout.MonadWide(**layout_settings),
    layout.Columns(insert_position=1, **layout_settings),
    layout.Matrix(insert_position=1, **layout_settings),
    layout.RatioTile(**layout_settings),
    layout.Tile(**layout_settings),
    layout.VerticalTile(**layout_settings),
    layout.Zoomy(columnwidth=450, **layout_settings),
    layout.TreeTab(**layout_settings),
]

widget_defaults = dict(
    font='sans',
    fontsize=10,
    padding=3,
)
extension_defaults = widget_defaults.copy()

screens = [Screen(top=get_bar(idx)) for idx in range(util.num_screens)]

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
    procs.unclutter()
    procs.network_manager()
    procs.xfce4_power_manager()
    if not util.in_debug_mode:
        procs.setxkbmap()
        procs.screensaver()
        procs.xss_lock()
        procs.shiftred()
        procs.systemctl("dunst")
        procs.systemctl("compton")
        util.render_dunstrc()
        util.render_compton_conf()
        util.render_terminalrc()


@hook.subscribe.screen_change
def screen_change(qtile, event):
    util.restart_qtile(qtile)


@hook.subscribe.client_new
def minimize_window(window):
    cls = window.window.get_wm_class()
    for entry in cls:
        if entry == "heidisql.exe":
            window.togroup("d")
            name = window.window.get_name()
            if name in (None, ""):
                window.cmd_toggle_minimize()
                return
            transient = window.window.get_wm_transient_for()
            print(transient)
            if transient:
                res = util.res[-1]
                window.floating = True
                window.tweak_float(w=500, h=300, x=res["width"]/3, y=res["height"]/3)
