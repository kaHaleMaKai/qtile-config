from __future__ import annotations

import re
from pathlib import Path
from libqtile.config import Screen, Drag, Click, Match
from libqtile.lazy import lazy
from libqtile import hook, layout
from libqtile.backend.x11.window import Window
from libqtile.log_utils import logger

# custom imports – parts of config
from qutely import procs, color, util
from qutely.procs import Proc
from qutely.floating_rules import get_floating_rules, floating_dimensions
from qutely.keys import keys, mod_key
from qutely.opacity import partial_opacities  # NOQA
from qutely.debug import in_debug_mode
from qutely.display import is_light_theme, num_screens
from qutely.scratchpads import get_scratchpads
from qutely.custom_hooks import init_hooks


if not is_light_theme:
    from qutely.opacity import add_opacity
from qutely.bar import get_bar


NUMBER_OF_TERMINALS = 4

groups = util.groups[:]
groups.extend(get_scratchpads())

matcher = {
    "c": [Match(wm_class="Vivaldi-stable"), Match(wm_class="teams-for-linux")],
    "e": [
        Match(wm_class="Org.gnome.Evolution"),
        Match(wm_class="org.gnome.Evolution"),
        Match(wm_class="thunderbird"),
        Match(wm_class="thunderbird-default"),
    ],
    "f": [
        Match(wm_class=re.compile(r".*Firefox.*")),
        Match(title=re.compile(r".*Firefox.*")),
    ],
}
for g, match in matcher.items():
    util.group_dict[g].matches.extend(match)

for group in util.groups:
    if len(group.name) == 1:
        keys.add_keys(
            {
                f"M-{group.name}": util.go_to_group(group),
                f"M-S-{group.name}": util.move_window_to_group(group.name),
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
    "opacity": partial_opacities["class"][util.TERM_CLASS],
}

layouts = [
    layout.Bsp(border_focus=color.BLACK, border_normal=color.BLACK, **layout_settings),
    layout.MonadTall(ratio=0.72, **layout_settings),
    # layout.MonadWide(**layout_settings),
    # layout.Columns(insert_position=1, **layout_settings),
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
wallpaper = Path("~/.wallpaper").expanduser().absolute()

screens = [
    Screen(top=get_bar(idx), wallpaper=str(wallpaper), wallpaper_mode="stretch")
    for idx in range(num_screens)
]

# Drag floating layouts.
mouse = [
    Drag(
        [mod_key],
        "Button1",
        lazy.window.set_position(),
        start=lazy.window.get_position(),
    ),
    Drag(
        [mod_key, "shift"],
        "Button1",
        lazy.window.set_size_floating(),
        start=lazy.window.get_size(),
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
dgroups_app_rules = []
main = None
follow_mouse_focus = True
bring_front_click = False
cursor_warp = True
floating_layout = layout.Floating(float_rules=get_floating_rules(), border_width=0)
auto_fullscreen = False
reconfigure_screens = True
auto_minimize = True
focus_on_window_activation = "smart"
wmname = "LG3D"

init_hooks()
