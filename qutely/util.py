from __future__ import annotations

import os
import sys
import re
import math
from enum import Enum
from qutely import procs, templates
import asyncio
from asyncio.subprocess import create_subprocess_exec as new_proc
import aiofiles
import subprocess
import psutil
from itertools import chain
from pathlib import Path
from typing import Iterable, TypedDict, Any, cast, Awaitable, TYPE_CHECKING
from libqtile import hook
from libqtile.core.manager import Qtile
from libqtile.backend.x11.window import Window, XWindow
from libqtile.group import _Group
from libqtile.lazy import lazy, LazyCall
from libqtile.config import Group
from libqtile.scratchpad import ScratchPad
from libqtile.log_utils import logger
from qutely.floating_rules import onscreen_floaters

# import qtile_mutable_scratch as mut_scratch
from qutely.color import complement, add_hashtag
from qutely.display import is_light_theme, num_screens, THEME_BG_KEY
from qutely.vars import get_kitty_font_size, set_kitty_font_size

TERM_SUPPLY_CLASS = "kitty-term-supply"
TERM_CLASS = "kitty"
TERM_GROUP = ""
TERM_ATTRIBUTE = "IS_KITTY_SUPPLY"
NVIM_SERVER_CACHE_DIR = Path("~/.cache/nvim/servers").expanduser()
LAPTOP_SCREEN = "eDP-1"


class ScreenDict(TypedDict):
    _primary: str
    screens: dict[str, dict[str, int]]


class TerminalSupportStatus(Enum):
    NOT_INITIALIZED = 0
    SUPPORT = 1
    IN_USE = 2


def on_reload(f: Any) -> Any:
    return hook.subscribe.user("custom_reload", f)


# vim: 0xe7c5 or 0xe62b
# postgres: 0xf703,
# python: 0xe73cf
# java: 0xe738
group_labels: dict[
    str, dict[str, int | dict[str, int | dict[re.Pattern[str], int]]]
] = {
    "role": {},
    "class": {
        "firefox": {
            "regexes": {
                re.compile(r"\(Meeting\).*Microsoft Teams.*Firefox"): 0xF447,
                re.compile(
                    r"^https://teams.microsoft.com.*Microsoft Teams.*Firefox"
                ): 0xF7C8,
            },
            "default": 0xE745,
        },
        # "firefox": 0xE745,  # 0xf269,
        "xfce4-terminal": 0xE795,
        TERM_CLASS: {
            "default": 0xf489,
            "regexes": {
                re.compile("^[^@]+@.*:"): 0xF1E6,
                re.compile("^psql@"): 0xF0204,
            },
        },
        "vivaldi-stable": {
            "regexes": {
                re.compile(r"\(Meeting\).*Microsoft Teams.*Vivaldi"): 0xF447,
            },
            "default": 0xF7C8,  # 0xe744,  # 0xf57d,
        },
        "teams-for-linux": {
            "regexes": {
                re.compile(r"\(Meeting\).*Microsoft Teams.*Vivaldi"): 0xf02bb,
            },
            "default": 0xF7C8,  # 0xe744,  # 0xf57d,
        },
        "thunderbird": 0xe744,
        "ding": 0xF405,
        "thunderbird-default": 0xF6ED,
        "dbeaver": 0xF472,
        "org.remmina.remmina": 0xE62A,  # 0xf17a,
        "pavucontrol": 0xF028,
        "nextcloud": 0xF0C2,
        "wpsoffice": 0xF9EA,  # 0xf00b,
        "signal": 0xE712,
        "gimp": 0xF48F,
        "scribus": 0xF040,
        "qbittorent": 0xEAC2,
        "keepassxc": 0xF21B,
        "draw.io": 0xF03E,
        "jetbrains-idea-ce": 0xE7B5,
        "virtualbox manager": 0xE707,
        "evince": 0xF411,
        "bitwarden": 0xF21B,
        "wireshark": 0xF739,
        "zoom": 0xF03D,
        "arandr": 0xF109,
        "awiwi": 0xE006,  # 0xF02D,  # 0xE2A2,
        "opensnitch-ui": 0xF490,
        "onedrivegui": 0xF0C2,
        "chromium": 0xE743,
    },
    "name": {
        "vim": 0xE7C5,
        "psql": 0xF703,
        "ipython": 0xE235,  # 0xe73c,
    },
}

group_labels["class"]["firefox-nightly"] = group_labels["class"]["firefox"]
group_labels["class"][TERM_SUPPLY_CLASS] = group_labels["class"][TERM_CLASS]
group_labels["class"]["thunderbird-default"] = group_labels["class"]["thunderbird"]

group_dict = {name: Group(name) for name in "123456789abcdef"}
groups = sorted([g for g in group_dict.values()], key=lambda g: g.name)
empty_group = Group("")
groups.append(empty_group)
# mutscr = mut_scratch.MutableScratch()
# hook.subscribe.startup_complete(mutscr.qtile_startup)


class RingBuffer:
    def __init__(self, size: int, default: Any = None, no_repeat: bool = False) -> None:
        self.size = size
        self.buffer = [default] * size
        self.pointer = -1
        self.data_length = 0
        self.nr_of_pops = 0
        self.no_repeat = no_repeat

    def __len__(self) -> int:
        return self.data_length

    def add(self, el: Any) -> None:
        if self.no_repeat and self.current == el:
            return
        self.data_length = min(self.data_length + 1, self.size)
        self.pointer = (self.pointer + 1) % self.size
        if el is not None:
            self.current = el
            self.nr_of_pops = 0

    def backward(self) -> Any:
        if self.data_length <= 1:
            return None
        self.data_length -= 1
        self.pointer = (self.pointer - 1) % self.size
        el = self.current
        self.nr_of_pops += 1
        return el

    def forward(self) -> Any:
        if not self.nr_of_pops:
            return None
        self.nr_of_pops -= 1
        self.add(None)
        return self.current

    @property
    def current(self) -> Any:
        return self.buffer[self.pointer]

    @current.setter
    def current(self, el: Any) -> None:
        self.buffer[self.pointer] = el

    def __repr__(self) -> str:
        return str(self.buffer)


group_history = RingBuffer(100, no_repeat=True)


def go_to_group(group: Group) -> LazyCall:
    @lazy.function
    def f(qtile: Qtile) -> None:
        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        if group.name:
            group_history.add(group)
        qtile.to_screen(screen)
        qtile.groups_map[group.name].toscreen()

    return f


def get_group_and_screen_idx(
    qtile: Qtile, offset: int, skip_invisible: bool = False
) -> tuple[_Group, int]:
    if offset < -1 or offset > 1:
        raise ValueError(
            f"wrong value supportetd. expected: offset in (-1, 0, 1). got: {offset}"
        )
    if skip_invisible or not offset:
        return _get_group_and_screen_idx_dynamic(qtile, offset)
    else:
        return _get_group_and_screen_idx_static(qtile, offset)


def _get_group_and_screen_idx_static(qtile: Qtile, offset: int) -> tuple[_Group, int]:
    group = qtile.current_group
    for _ in range(2):
        if offset > 0:
            group = group.get_next_group()
        else:
            group = group.get_previous_group()
        if group.name:
            break
    return group, group.screen


def sign(x: int) -> int:
    return int(math.copysign(1, x))


def _get_group_and_screen_idx_dynamic(qtile: Qtile, offset: int) -> tuple[_Group, int]:
    current_group = qtile.current_group
    orig_group = current_group
    skip_empty = not bool(current_group.windows)
    next_group = current_group
    for i in range(3):
        if i == 2:
            skip_empty = False
            next_group = orig_group
        if offset < 0:
            next_group = next_group.get_previous_group(skip_empty)
            if not skip_empty and not next_group.windows:
                neighbour = next_group.get_previous_group(skip_empty=True)
                next_group = neighbour.get_next_group(skip_empty=False)
        else:
            next_group = next_group.get_next_group(skip_empty)
        if next_group.name:
            break
    if offset > 0 and next_group.name < orig_group.name < "f":
        next_group = qtile.groups_map["f"]
    elif offset < 0:
        if orig_group.name == "1":
            next_group = qtile.groups_map["f"]
        elif orig_group.name == "f":
            next_group = qtile.groups_map["e"]

    screen = 0 if num_screens == 1 or next_group.name < "a" else 1
    return next_group, screen


def next_group() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile):
        global group_history
        g, s = get_group_and_screen_idx(qtile, +1, skip_invisible=True)
        group_history.add(g)
        qtile.to_screen(s)
        g.toscreen()

    return f


def prev_group() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile) -> None:
        global group_history
        g, s = get_group_and_screen_idx(qtile, -1, skip_invisible=True)
        group_history.add(g)
        qtile.to_screen(s)
        g.toscreen()

    return f


def history_back() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile) -> None:
        group = group_history.backward()
        if not group:
            return

        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        qtile.to_screen(screen)
        qtile.groups_map[group.name].toscreen()

    return f


def history_forward() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile) -> None:
        group = group_history.forward()
        if not group:
            return

        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        qtile.to_screen(screen)
        qtile.groups_map[group.name].toscreen()

    return f


def move_window_to_group(name: str) -> LazyCall:
    @lazy.function
    def f(qtile: Qtile) -> None:
        if not (window := qtile.current_window):
            return
        label = qtile.current_group.label
        window.togroup(name)

        if not qtile.current_group.current_window:
            qtile.current_group.set_label(None)
        else:
            set_group_label_from_window_class(window)
        dest_group = qtile.groups_map[name]
        dest_group.set_label(label)

    return f


def move_window_to_offset_group(offset: int) -> LazyCall:
    if not offset:
        raise ValueError("offset must not be 0")

    @lazy.function
    def f(qtile: Qtile) -> None:
        current_group = qtile.current_group
        next, _ = get_group_and_screen_idx(qtile, offset)
        label = current_group.label
        window = qtile.current_window
        window.togroup(next.name)

        if not current_group.current_window:
            current_group.set_label(None)
        else:
            set_group_label_from_window_class(window)

        next.set_label(label)

    return f


@lazy.function
def spawncmd(qtile: Qtile) -> None:
    screen = qtile.current_screen.index
    command = "zsh -c '%s'"
    qtile.cmd_spawncmd(widget=f"prompt-{screen}", command=command)


@lazy.function
def grow_right_or_shrink_left(qtile: Qtile) -> None:
    width = qtile.current_screen.width
    win: Window = qtile.current_window
    right_margin = win.y + win.width
    if right_margin < width:
        qtile.current_layout.grow_right()
        return
    # for w in qtile.current_group.windows:


def move_to_screen(dest_screen: str) -> LazyCall:
    if num_screens == 1:
        return lambda *args, **kwargs: None

    @lazy.function
    def f(qtile):
        idx = qtile.current_screen.index
        if dest_screen == idx:
            return
        other_screen = qtile.screens[dest_screen]
        g = other_screen.group.name
        qtile.current_window.togroup(g)
        qtile.to_screen(dest_screen)

    return f


def go_to_screen(dest_screen: str) -> LazyCall:
    if num_screens == 1:
        return lambda *args, **kwargs: None

    @lazy.function
    def f(qtile):
        idx = qtile.current_screen.index
        if dest_screen == idx:
            return
        qtile.to_screen(dest_screen)

    return f


async def reload_nvim_colors(is_light_theme: bool) -> None:
    servers = [server for server in NVIM_SERVER_CACHE_DIR.iterdir() if server.is_file()]
    bg = "light" if is_light_theme else "dark"
    keys = f":silent call ReloadColors({{'theme': '{bg}', 'force': v:true}})<CR>"
    tasks = [
        new_proc("nvim", "--server", str(server), "--remote-keys", keys, close_fds=True)
        for server in servers
    ]
    await asyncio.gather(*tasks)


async def render_dunstrc() -> bool:
    return await templates.render(
        "dunstrc",
        "~/.config/dunst",
        keep_comments=False,
        keep_empty=False,
    )


async def render_compton_config() -> bool:
    return await templates.render(
        "compton.conf",
        "~/.config",
        keep_empty=True,
    )


async def render_picom_config() -> bool:
    return await templates.render(
        "picom.conf",
        "~/.config",
        keep_empty=True,
    )


async def increase_kitty_font_size(*_) -> None:
    await render_kitty_config(1)


async def decrease_kitty_font_size(*_) -> None:
    await render_kitty_config(-1)


async def render_kitty_config(font_size_inc: int = 0) -> bool:
    if font_size_inc:
        current_size = get_kitty_font_size()
        new_size = current_size + font_size_inc
        if not new_size:
            return
        set_kitty_font_size(new_size)
    has_changed = await templates.render(
        "kitty.conf",
        "~/.config/kitty",
        keep_empty=True,
        comment_start="#",
    )
    if has_changed:
        from libqtile import qtile

        qtile.call_soon(reload_kitty_config)
    return has_changed


async def render_terminalrc() -> bool:
    return await templates.render(
        "terminalrc",
        "~/.config/xfce4/terminal",
        keep_empty=True,
    )


def restart_qtile(qtile: Qtile) -> None:
    for group in qtile.groups:
        for window in group.windows:
            try:
                window.opacity = window._full_opacity
            except AttributeError:
                pass
    qtile.cmd_restart()


@lazy.function
def start_distraction_free_mode(qtile: Qtile) -> None:
    procs._pause_dunst()


@lazy.function
def stop_distraction_free_mode(qtile: Qtile) -> None:
    procs._resume_dunst()
    procs._dunstify("including distractions again")


async def reload_qtile(qtile: Qtile, light_theme: bool = False) -> None:
    logger.warn("reloading config (async)")
    path_file = os.path.join("/home", "lars", ".config", "zsh", "path")
    tmp_file = "/tmp/zsh-export-path"
    await procs.Proc(
        f"/usr/bin/zsh -c 'source {path_file}'",
        shell=True,
        env={"QTILE_EXPORT_PATH": tmp_file},
    ).run()
    logger.warn("zsh path_file sourced")
    with open(tmp_file, "r") as f:
        path_env = f.read()
    if path_env.strip():
        os.environ["PATH"] = path_env.strip()
    os.environ[THEME_BG_KEY] = "1" if light_theme else ""
    logger.warn("triggering qtile reload")
    qtile.reload_config()
    logger.warn("qtile.reload_config() done")
    hook.fire("user_custom_reload")
    qtile.call_soon(setup_all_group_icons)
    logger.warn("finished reloading config (async)")
    procs.Proc.await_many(
        render_kitty_config(),
        reload_nvim_colors(light_theme),
        procs.start_custom_session,
        procs.resume_dunst,
    )


@hook.subscribe.screens_reconfigured
async def screens_reconfigured() -> None:
    await render_kitty_config()
    await procs.resume_dunst.run()


async def lock_screen(qtile: Qtile) -> None:
    await procs.resume_dunst.run()
    await procs.screensaver_cmd.run()


async def suspend(qtile: Qtile) -> None:
    await procs.suspend.run()


def reload_kitty_config() -> None:
    for p in psutil.process_iter():
        if p.name() == "kitty":
            p.send_signal(psutil.signal.SIGUSR1)


sticky_windows: list[tuple[Window, _Group, bool]] = []


def stick_win(qtile: Qtile) -> None:
    logger.warn("sticking window")
    global sticky_windows
    sticky_windows.append(
        (qtile.current_window, qtile.current_group, qtile.current_window.floating)
    )
    qtile.current_window.floating = True


def unstick_win(qtile: Qtile) -> None:
    global sticky_windows
    window = qtile.current_window
    if not window or not sticky_windows:
        raise ValueError(f"window is not sticky: {window}")
        return
    idx, group, was_floating = get_sticky_index_and_group(window)
    sticky_windows.pop(idx)
    window.togroup(group.name)
    window.floating = was_floating


def toggle_sticky_window(qtile: Qtile) -> None:
    try:
        unstick_win(qtile)
    except ValueError:
        stick_win(qtile)


def get_sticky_index_and_group(window: Window) -> tuple[int, _Group, bool] | None:
    global sticky_windows
    res = [
        (i, tup[1], tup[2]) for i, tup in enumerate(sticky_windows) if tup[0] == window
    ]
    # FIXME None would break at call site
    if not res:
        return None
    return res[0]


def set_group_label_from_window_class(window: Window) -> None:
    ch: int | None = None
    if window.name:
        name = window.name.split(" ")[0].lower().replace(":", "")
        ch = group_labels["name"].get(name)

    group = window.group
    if not group or not group.name:
        return
    if isinstance(group, ScratchPad):
        group.set_label(None)
        return

    if not ch:
        classes = window.get_wm_class()
        if classes:
            cls = classes[1].lower()
            value = group_labels["class"].get(cls)
            if isinstance(value, int):
                ch = value
            elif isinstance(value, dict):
                if "regexes" in value:
                    for regex, icon in value["regexes"].items():
                        if regex.search(window.name):
                            ch = icon
                            break
                if not ch:
                    ch = value["default"]
    if not ch:
        role = window.get_wm_role()
        if role:
            ch = group_labels["role"].get(role.lower())

    label: str | None
    if ch:
        label = chr(ch)
    else:
        label = None
        msg = f"missing label for window name={window.name!r}, role={window.get_wm_role()!r}, class={window.get_wm_class()!r}"
        logger.warn(msg)
    label = chr(ch) if ch else None
    group.set_label(label)


def setup_all_group_icons() -> None:
    from libqtile import qtile

    for group in qtile.groups_map.values():
        if isinstance(group, ScratchPad) or not group.name:
            continue
        group = cast(_Group, group)
        if group.current_window:
            set_group_label_from_window_class(group.current_window)
        else:
            group.set_label(None)


class KbdBacklight:
    def __init__(self, name: str) -> None:
        # dell::kbd_backlight/brightness
        self.name = name
        self.dev = Path("/sys/class/leds") / name
        self.value = 0
        self.max_value = 0

    async def configure(self) -> None:
        async with aiofiles.open(self.dev / "max_brightness", "r") as f:
            self.max_value = int(await f.read())
        async with aiofiles.open(self.dev / "brightness", "r") as f:
            self.value = int(await f.read())

    async def increase_brightness(self, _: Any = None) -> None:
        if not self.max_value:
            await self.configure()
            # raise ValueError(
            #     "KbdBacklight has not been initialized. Please run configure() first"
            # )
        value = (self.value + 1) % (self.max_value + 1)
        async with aiofiles.open(self.dev / "brightness", "w") as f:
            await f.write(str(value))
        self.value = value


kbd_backlight = KbdBacklight("dell::kbd_backlight")


def get_term_supply_status(window: Window) -> TerminalSupportStatus:
    r = window.window.get_property(TERM_ATTRIBUTE, "CARDINAL", unpack=int)
    if not r:
        return TerminalSupportStatus.NOT_INITIALIZED
    return TerminalSupportStatus.SUPPORT if r[0] else TerminalSupportStatus.IN_USE


def set_term_supply(window: Window, as_supply: bool = True) -> None:
    window.window.set_property(TERM_ATTRIBUTE, int(as_supply), "CARDINAL", 32)


@lazy.function
def provide_terminal(qtile: Qtile) -> None:
    try:
        window = qtile.groups_map[TERM_GROUP].windows[0]
    except IndexError:
        logger.warn(f"no supply terminals available on group {TERM_GROUP}")
        return
    set_term_supply(window, as_supply=False)

    window.togroup(qtile.current_group.name)
    window.focus(warp=True)


async def spawn_terminal() -> None:
    from libqtile import qtile

    if len(qtile.groups_map[TERM_GROUP].windows) < 2:
        await new_proc("kitty", f"--class={TERM_SUPPLY_CLASS}", close_fds=True)


@hook.subscribe.client_new
def send_kitty_to_empty_group(window: Window) -> None:
    if (
        window.get_wm_class()[1] == TERM_SUPPLY_CLASS
        and get_term_supply_status(window) is TerminalSupportStatus.NOT_INITIALIZED
    ):
        set_term_supply(window, as_supply=True)
        window.togroup(TERM_GROUP)


@hook.subscribe.group_window_add
async def add_more_terminals(group: Group, window: Window) -> None:
    if (
        group.name != TERM_GROUP and window.get_wm_class()[1] == TERM_SUPPLY_CLASS
        # and get_term_supply_status(winoow) is TerminalSupportStatus.IN_USE
    ):
        await spawn_terminal()


@hook.subscribe.addgroup
def hide_empty_group(name: str) -> None:
    if not name:
        from libqtile import qtile

        qtile.groups_map[""].set_screen(None)


@hook.subscribe.user("custom_reload")
async def init_more_widgets() -> None:
    await kbd_backlight.configure()


@hook.subscribe.client_new
def bring_floating_to_screen(window: Window) -> None:
    if not window or not window.window or not window.floating:
        return
    if (cls := window.get_wm_class()[1]) not in onscreen_floaters:
        return
    props = onscreen_floaters[cls]
    if props:
        if t := props.get("type") and window.get_wm_type() != "dialog":
            return
    from libqtile import qtile

    if TYPE_CHECKING:
        qtile = cast(Qtile, qtile)

    window.togroup(qtile.current_group.name)
    window.toscreen(qtile.current_screen.index)
