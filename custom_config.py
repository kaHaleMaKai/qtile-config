import re
import subprocess
from libqtile.config import Screen, Group, Drag, Click, Match
from libqtile.command import lazy
from libqtile.core.manager import Qtile
from libqtile import hook, layout
from libqtile.window import Window
from libqtile.backend.x11.xcbq import Window as XWindow


from typing import List  # noqa: F401

# custom imports – parts of config

import procs
import color
from floating_rules import get_floating_rules
from keys import keys, mod_key
from opacity import add_opacity, partial_opacities  # NOQA
from bar import get_bar
import util


heidi_group = util.group_dict["d"]
groups = util.groups

matcher = {
    "c": Match(wm_class=["Vivaldi-stable"]),
    heidi_group.name: Match(wm_class=["heidi.sql"]),
    "e": Match(wm_class=["Evolution", "Thunderbird", "thunderbird"]),
    "f": Match(wm_class=[re.compile("Firefox.*")]),
}
for g, match in matcher.items():
    util.group_dict[g].matches.append(match)

for group in util.groups:
    keys.add_keys({
        f"M-{group.name}": util.go_to_group(group),
        f"M-S-{group.name}": lazy.window.togroup(group.name),
    })

layout_settings = {}
layout_settings["border_width"] = 0

treetab_bg = "101000"
treetab_settings = {
    "fontsize": 12,
    "previous_on_rm": True,
    "active_fg": color.BRIGHT_ORANGE,
    "active_bg": treetab_bg,
    "bg_color": treetab_bg,
    "inactive_bg": treetab_bg,
    "inactive_fg": color.DARK_ORANGE,
    "panel_width": 100,
    "section_fg": color.DARK_GRAY,
    "sections": ["default"],
    "padding_left": 0,
    "padding_x": 0,
    "padding_y": 0,
    "section_padding": 0,
    "margin_left": 0,
    "margin_y": 0,
    "section_top": 0,
    "section_bottom": 0,
    "section_padding": 0,
    "section_left": 0,
    "opacity": partial_opacities["class"]["xfce4-terminal"],
}

layouts = [
    layout.Bsp(border_focus=color.BLACK, border_normal=color.BLACK, **layout_settings),
    # layout.MonadTall(**layout_settings),
    # layout.MonadWide(**layout_settings),
    # layout.Columns(insert_position=1, **layout_settings),
    # layout.Matrix(insert_position=1, **layout_settings),
    # layout.RatioTile(**layout_settings),
    # layout.Tile(**layout_settings),
    # layout.VerticalTile(**layout_settings),
    # layout.Zoomy(columnwidth=450, **layout_settings),
    layout.Max(**layout_settings),
    layout.TreeTab(**layout_settings, **treetab_settings),
]

widget_defaults = dict(
    font='sans',
    fontsize=12,
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
    procs.bluetooth()
    procs.xfce4_power_manager()
    if not util.in_debug_mode:
        procs.screensaver()
        procs.polkit_agent()
        procs.xss_lock()
        procs.shiftred()
        procs.systemctl("dunst")
        procs.systemctl("compton")
        util.render_dunstrc()
        util.render_compton_conf()
        util.render_terminalrc()
        procs.nextcloud_sync()
        procs.kde_connect()
        # procs.signal_desktop()
    procs.setxkbmap()


@hook.subscribe.screen_change
def screen_change(qtile: Qtile, event):
    util.restart_qtile(qtile)


@hook.subscribe.client_new
def minimize_window(window: Window):
    cls = window.window.get_wm_class()
    for entry in cls:
        if entry == "heidisql.exe":
            if window.name in (None, ""):
                window.cmd_toggle_minimize()
                return
            elif window.name in ("Export grid rows", "Search and replace text",):
                res = util.res[-1]
                x = int(res["width"]/3)
                y = int(res["height"]/3)
                window.hints["max_width"] = window.hints["min_width"] = x
                window.hints["max_height"] = window.hints["min_height"] = y
                window.update_hints()
                window.cmd_set_size_floating(w=x, h=y)
                window.cmd_set_position_floating(x=x, y=y)
                qtile: Qtile = window.qtile
                window.cmd_togroup(heidi_group.name)
                window.cmd_focus()


previous_window_class = None


@hook.subscribe.client_focus
def copy_intellij_clipboard(window: Window):
    global previous_window_class
    cls = window.window.get_wm_class()[1].lower()
    if cls is previous_window_class:
        return

    intellij = 'intellij'
    if cls != intellij and previous_window_class != intellij:
        previous_window_class = cls
        return
    if previous_window_class == intellij:
        from_display = 11
        to_display = 0
    else:
        from_display = 0
        to_display = 11
    from_cmd = f"xclip -selection c -o -display :{from_display}".split(" ")
    to_cmd = f"xclip -selection c -i -display :{to_display}".split(" ")
    from_proc = subprocess.Popen(from_cmd, stdout=subprocess.PIPE)
    to_proc = subprocess.run(to_cmd, stdin=from_proc.stdout)
    from_proc.wait()
    previous_window_class = cls
