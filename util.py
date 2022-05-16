import os
import re
import yaml
import pywal
import procs
import subprocess
from itertools import chain
from typing import Tuple, Iterable, Dict, Union, TypedDict
from libqtile.core.manager import Qtile
from libqtile.window import Window
from libqtile.backend.x11.xcbq import Window as XWindow
from libqtile.group import _Group
from libqtile.command import lazy
from libqtile.lazy import LazyCall
from libqtile.layout.base import Layout
from libqtile.layout.tree import TreeTab
from libqtile.config import Group
import templates
from color import complement, add_hashtag


class ScreenDict(TypedDict):
    _primary: str
    screens: Dict[str, Dict[str, int]]


in_debug_mode = os.environ.get("QTILE_DEBUG_MODE", "off") == "on"
group_dict = {name: Group(name) for name in "123456789abcdef"}
groups = sorted([g for g in group_dict.values()], key=lambda g: g.name)
laptop_display = "eDP-1"


def _get_screens_helper(lines: Iterable[str]) -> ScreenDict:
    d: ScreenDict = {"_primary": "", "screens": {}}
    for line in lines:
        if not line or line.startswith("Screen ") or "disconnected" in line or line.startswith(" "):
            continue
        is_primary = "primary" in line
        m = re.match(
            r"(?P<monitor>\S+)\s+connected\s+(primary\s+)?(?P<width>\d+)x(?P<height>\d+)+(?P<xoffset>\d+)+(?P<yoffset>\d+)",
            line,
        )
        if not m:
            raise ValueError(f"cannot parse line '{line}'")
        mon = m.group("monitor")
        data = {name: int(m.group(name)) for name in ("width", "height", "xoffset", "yoffset")}
        data["is_primary"] = is_primary
        d["screens"][mon] = data
        if is_primary:
            d["_primary"] = mon
    return d


def get_screens() -> ScreenDict:
    import subprocess

    cmd = ["xrandr"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    lines = [line.decode("utf-8") for line in p.communicate()[0].split(b"\n") if line]
    screens = _get_screens_helper(lines)

    return screens


screens = get_screens()
res = [{"width": s["width"], "height": s["height"]} for s in screens["screens"].values()]
num_screens = len(screens["screens"])


def is_laptop_connected() -> bool:
    return laptop_display in screens["screens"]


class RingBuffer:
    def __init__(self, size: int, default=None):
        self.size = size
        self.buffer = [default] * size
        self.pointer = -1
        self.data_length = 0
        self.nr_of_pops = 0

    def __len__(self):
        return self.data_length

    def add(self, el):
        self.data_length = min(self.data_length + 1, self.size)
        self.pointer = (self.pointer + 1) % self.size
        if el is not None:
            self.buffer[self.pointer] = el
            self.nr_of_pops = 0

    def backward(self):
        if self.data_length <= 1:
            return None
        self.data_length -= 1
        self.pointer = (self.pointer - 1) % self.size
        el = self.buffer[self.pointer]
        self.nr_of_pops += 1
        return el

    def forward(self):
        if not self.nr_of_pops:
            return None
        self.nr_of_pops -= 1
        self.add(None)
        return self.buffer[self.pointer]

    def __repr__(self):
        return str(self.buffer)


group_history = RingBuffer(100)


def go_to_group(group):
    @lazy.function
    def f(qtile: Qtile):
        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        if group.name:
            group_history.add(group)
        qtile.cmd_to_screen(screen)
        qtile.groups_map[group.name].cmd_toscreen()

    return f


def get_group_and_screen_idx(qtile: Qtile, offset: int) -> Tuple[_Group, int]:
    group = qtile.current_group.name
    idx = (int(group, 16) - 1 + offset) % len(groups)
    next_group = groups[idx].name
    screen = 0 if num_screens == 1 or next_group < "a" else 1
    return qtile.groups_map[next_group], screen


def next_group() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile):
        global group_history
        g, s = get_group_and_screen_idx(qtile, +1)
        group_history.add(g)
        qtile.cmd_to_screen(s)
        g.cmd_toscreen()

    return f


def prev_group() -> LazyCall:
    @lazy.function
    def f(qtile):
        global group_history
        g, s = get_group_and_screen_idx(qtile, -1)
        group_history.add(g)
        qtile.cmd_to_screen(s)
        g.cmd_toscreen()

    return f


def history_back() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile):
        group = group_history.backward()
        if not group:
            return

        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        qtile.cmd_to_screen(screen)
        qtile.groups_map[group.name].cmd_toscreen()

    return f


def history_forward() -> LazyCall:
    @lazy.function
    def f(qtile: Qtile):
        group = group_history.forward()
        if not group:
            return

        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        qtile.cmd_to_screen(screen)
        qtile.groups_map[group.name].cmd_toscreen()

    return f


def move_window_to_offset_group(offset: int) -> LazyCall:

    if not offset:
        raise ValueError("offset must not be 0")

    @lazy.function
    def f(qtile: Qtile):
        current = qtile.current_group.name
        next, _ = get_group_and_screen_idx(qtile, offset)
        # if (offset < 0 and next.name < current) or (offset > 0 and next.name > current):
        qtile.current_window.togroup(next.name)

    return f


@lazy.function
def spawncmd(qtile: Qtile):
    screen = qtile.current_screen.index
    command = "zsh -c '%s'"
    return qtile.cmd_spawncmd(widget=f"prompt-{screen}", command=command)


@lazy.function
def grow_right_or_shrink_left(qtile: Qtile):
    width = qtile.current_screen.width
    win: Window = qtile.current_window
    right_margin = win.y + win.width
    if right_margin < width:
        qtile.current_layout.grow_right()
        return
    # for w in qtile.current_group.windows:


def move_to_screen(dest_screen):
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

    return f


def go_to_screen(dest_screen):
    if num_screens == 1:
        return lambda *args, **kwargs: None

    @lazy.function
    def f(qtile):
        idx = qtile.current_screen.index
        if dest_screen == idx:
            return
        qtile.cmd_to_screen(dest_screen)

    return f


def get_wal_colors():
    yaml_file = os.path.join(pywal.colors.CACHE_DIR, "colors.yml")
    if not os.path.exists(yaml_file):
        wallpaper = os.path.expanduser("~/.wallpaper")
        colors = pywal.colors.get(wallpaper)
        pywal.export.every(colors)
    else:
        with open(yaml_file, "r") as f:
            colors = yaml.load(f.read(), Loader=yaml.BaseLoader)
    # all_colors = ["#" + complement(c, 0.4) if 1 < i < 9 else c for i, c in enumerate(colors["colors"].values())]
    all_colors = colors["colors"].values()
    return {
        "colors": all_colors,
        "bg": colors["special"]["background"],
        "fg": colors["special"]["foreground"],
        "cursor": colors["special"]["cursor"],
    }


def get_default_vars(**overrides):
    default_vars = {
        "defaults": {
            "num_screens": num_screens,
            "res": res,
            "in_debug_mode": in_debug_mode,
        },
        "wal": get_wal_colors(),
    }
    default_vars.update(**overrides)
    return default_vars


def render_dunstrc(**overrides) -> None:
    if not in_debug_mode:
        templates.render(
            "dunstrc",
            "~/.config/dunst",
            keep_comments=False,
            keep_empty=False,
            overrides=get_default_vars(**overrides),
        )


def render_picom_config(**overrides) -> None:
    if not in_debug_mode:
        templates.render(
            "picom.conf",
            "~/.config",
            keep_empty=True,
            overrides=get_default_vars(**overrides),
        )


def render_terminalrc(**overrides) -> None:
    if not in_debug_mode:
        colors = get_wal_colors(**overrides)
        templates.render(
            "terminalrc",
            "~/.config/xfce4/terminal",
            keep_empty=True,
            overrides=get_default_vars(**colors),
        )


def restart_qtile(qtile: Qtile) -> None:
    print("restarting qtile")
    print("running feh")
    procs.feh()
    print("setting opacities")
    for group in qtile.groups:
        for window in group.windows:
            try:
                window.opacity = window._full_opacity
            except AttributeError:
                pass
    print("executing cmd_restart")
    qtile.cmd_restart()
    render_dunstrc()
    render_picom_config()
    render_terminalrc()
    procs.resume_dunst()


@lazy.function
def start_distraction_free_mode(qtile: Qtile) -> None:
    procs.pause_dunst()


@lazy.function
def stop_distraction_free_mode(qtile: Qtile) -> None:
    procs.resume_dunst()
    procs.dunstify("including distractions again")


@lazy.function
def update_path(qtile: Qtile) -> None:
    path_file = os.path.join(os.path.expanduser("$"), ".config", "zsh", "path")
    tmp_file = "/tmp/zsh-export-path"
    subprocess.run(
        f"/usr/bin/zsh -c 'source {path_file}'",
        shell=True,
        env={"QTILE_EXPORT_PATH": tmp_file},
    )
    with open(tmp_file, "r") as f:
        path_env = f.read()
    if path_env.strip():
        os.environ["PATH"] = path_env.strip()


@lazy.function
def lock_screen(qtile: Qtile) -> None:
    procs.screensaver_cmd()
    procs.resume_dunst()
