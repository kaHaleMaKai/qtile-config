import re
from pathlib import Path
from libqtile.config import Screen, Drag, Click, Match, ScratchPad, DropDown
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


if not is_light_theme:
    from qutely.opacity import add_opacity
from qutely.bar import get_bar


NUMBER_OF_TERMINALS = 4

groups = util.groups[:]
groups.extend([
    ScratchPad(
        "signal_scratchpad",
        [
            DropDown(
                "signal",
                ["signal-desktop"],
                opacity=1,
                on_focus_lost_hide=False,
                x=0.05,
                y=0,
                width=0.9,
                height=0.9,
                ),
            ],
        single=True,
        ),

    ScratchPad(
        "ding_scratchpad",
        [
            DropDown(
                "ding",
                ["ding"],
                opacity=1,
                on_focus_lost_hide=True,
                x=0.05,
                y=0,
                width=0.9,
                height=0.9,
                ),
            ],
        single=True,
        ),

    ScratchPad(
        "telegram_scratchpad",
        [
            DropDown(
                "telegram",
                ["telegram-desktop"],
                opacity=1,
                on_focus_lost_hide=True,
                x=0.05,
                y=0,
                width=0.9,
                height=0.9,
                ),
            ],
        single=True,
        ),

    ScratchPad(
        "neochat_scratchpad",
        [
            DropDown(
                "neochat",
                ["neochat"],
                opacity=1,
                on_focus_lost_hide=True,
                x=0.05,
                y=0,
                width=0.9,
                height=0.9,
                ),
            ],
        single=True,
        ),
])

matcher = {
    "c": [Match(wm_class="Vivaldi-stable"), Match(wm_class="teams-for-linux")],
    "e": [
        Match(wm_class="Evolution"),
        Match(wm_class="Thunderbird"),
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


@hook.subscribe.startup_complete
async def autostart_once() -> None:
    logger.info("running startup_once")
    ps = [
        procs.xss_lock,
    ]
    await Proc.await_many(*ps)


@hook.subscribe.startup
async def autostart() -> None:
    logger.info("running startup")
    ps = [procs.resume_dunst]
    if not in_debug_mode:
        ps.extend(
            [
                procs.start_custom_session,
                util.render_dunstrc(),
                util.render_kitty_config(),
                util.spawn_terminal(),
                # util.render_terminalrc(),
                # util.render_picom_config(),
            ]
        )
    # if is_light_theme:
    #     ps.append(procs.stop_picom)
    # else:
    #     ps.append(procs.start_picom)
    await Proc.await_many(*ps)


# @hook.subscribe.screen_change
# async def screen_change(event):
#     from libqtile import qtile

#     await util.reload_qtile(qtile)


def handle_floating_windows(window: Window) -> None:
    if not window or not window.name:
        return

    role = window.window.get_wm_window_role()
    name = window.name
    class_ = window.get_wm_class()[1].lower()
    if name.startswith("chrome-extension://") and name.endswith(
        " is sharing a window."
    ):
        window.enable_floating()
    elif role == "InvitationsDialog":
        window.floating = False

    if dim := floating_dimensions.get(class_):
        window.width, window.height = dim
        window.center()


@hook.subscribe.client_new
def handle_floating_for_new_clients(window: Window) -> None:
    handle_floating_windows(window)
    from libqtile import qtile

    for win in qtile.current_group.windows:
        if win.floating:
            win.bring_to_front()


@hook.subscribe.client_killed
def cycle_to_next_client_or_empty_group(window: Window) -> None:
    current_group = window.qtile.current_group
    if len(current_group.windows) > 1 or window not in current_group.windows:
        return
    if len(current_group.windows) <= 1:
        current_group.set_label(None)
    if current_group.name in ("1", "f"):
        return
    qtile = window.qtile
    g, s = util.get_group_and_screen_idx(qtile, -1, skip_invisible=True)
    if g.name > current_group.name:
        g, s = qtile.groups_map["1"], 0
    util.group_history.backward()
    util.group_history.add(g)
    qtile.to_screen(s)
    g.toscreen()


@hook.subscribe.setgroup
def move_sticky_windows():
    from libqtile import qtile

    for w, _, _ in util.sticky_windows:
        w.togroup(qtile.current_group.name)
    window: Window | None = qtile.current_window
    if window:
        window.focus()


@hook.subscribe.client_name_updated
@hook.subscribe.client_managed
@hook.subscribe.client_focus
def set_group_icon(window: Window | None) -> None:
    if window is None:
        from libqtile import qtile

        qtile.current_group.set_label(None)
    else:
        util.set_group_label_from_window_class(window)

# @hook.subscribe.user("custom_reload")
# def setup_all_group_icons() -> None:
#     hook.subscribe.startup_complete(hook.subscribe.restart(util.setup_all_group_icons))
