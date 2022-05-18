import re
import subprocess
from libqtile.config import Screen, Group, Drag, Click, Match, ScratchPad, DropDown
from libqtile.command import lazy
from libqtile.core.manager import Qtile
from libqtile import hook, layout
from libqtile.backend.x11.window import Window, XWindow
from typing import List, Callable  # noqa: F401

# custom imports – parts of config

import procs
import color
from floating_rules import get_floating_rules
from keys import keys, mod_key
from opacity import add_opacity, partial_opacities  # NOQA
from bar import get_bar
import util


scratchpad = ScratchPad(
    "scratchpad",
    [
        DropDown("signal", ["signal-desktop"], opacity=1, on_focus_lost_hide=True),
    ],
)

groups = util.groups[:]
groups.append(scratchpad)

matcher = {
    "c": [Match(wm_class="Vivaldi-stable")],
    "e": [
        Match(wm_class="Evolution"),
        Match(wm_class="Thunderbird"),
        Match(wm_class="thunderbird"),
    ],
    "f": [
        Match(wm_class=re.compile(r".*Firefox.*")),
        Match(title=re.compile(r".*Firefox Developer Edition\s*")),
    ],
}
for g, match in matcher.items():
    util.group_dict[g].matches.append(match)

for group in util.groups:
    keys.add_keys(
        {
            f"M-{group.name}": util.go_to_group(group),
            f"M-S-{group.name}": lazy.window.togroup(group.name),
        }
    )

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
    layout.MonadTall(ratio=0.68, **layout_settings),
    # layout.MonadWide(**layout_settings),
    layout.Columns(insert_position=1, **layout_settings),
    # layout.Matrix(insert_position=1, **layout_settings),
    # layout.RatioTile(**layout_settings),
    # layout.Tile(**layout_settings),
    # layout.VerticalTile(**layout_settings),
    # layout.Zoomy(columnwidth=450, **layout_settings),
    layout.Max(**layout_settings),
]

widget_defaults = dict(
    font="sans",
    fontsize=12,
    padding=3,
)
extension_defaults = widget_defaults.copy()

screens = [Screen(top=get_bar(idx)) for idx in range(util.num_screens)]

# Drag floating layouts.
mouse = [
    Drag(
        [mod_key],
        "Button1",
        lazy.window.set_position(),
        start=lazy.window.get_position(),
    ),
    Drag(
        [mod_key],
        "Button3",
        lazy.window.set_size_floating(),
        start=lazy.window.get_size(),
    ),
    Click([mod_key], "Button2", lazy.window.bring_to_front()),
]

dgroups_key_binder = None
dgroups_app_rules = []  # type: List
main = None
follow_mouse_focus = True
bring_front_click = False
cursor_warp = True
floating_layout = layout.Floating(float_rules=get_floating_rules(), border_width=0)
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
        procs.screensaver()
        procs.polkit_agent()
        procs.xss_lock()
        procs.shiftred()
        procs.systemctl_user("dunst")
        procs.systemctl_user("picom")
        util.render_dunstrc()
        util.render_picom_config()
        util.render_terminalrc()
        procs.bluetooth()
        procs.nextcloud_sync()
        procs.kde_connect()
    procs.setxkbmap()
    procs.systemctl("start", "mouse.service")


# this hook keeps on firing in xephyr so that qtile
# can't even start up properly
# if not util.in_debug_mode:

# @hook.subscribe.screen_change
# def screen_change(qtile: Qtile, event):
#     util.restart_qtile(qtile)


def handle_floating_windows(window: Window) -> None:
    if not window or not window.name:
        return

    role = window.window.get_wm_window_role()
    name = window.name
    if name.startswith("chrome-extension://") and name.endswith(" is sharing a window."):
        window.cmd_enable_floating()
    elif role == "InvitationsDialog":
        window.floating = False


@hook.subscribe.client_new
def handle_floating_for_new_clients(window: Window) -> None:
    return handle_floating_windows(window)


@hook.subscribe.client_name_updated
def start_teams_meeting(window: Window) -> None:
    if (
        window
        and isinstance(window.name, str)
        and re.search(r"\(Meeting\).*Microsoft Teams.*Vivaldi", window.name)
    ):
        procs.fakecam()
