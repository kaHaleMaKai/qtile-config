import os
import yaml
import pywal
import procs
import subprocess
from itertools import chain
from typing import Tuple
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


in_debug_mode = os.environ.get("QTILE_DEBUG_MODE", "off") == "on"
group_dict = {name: Group(name) for name in "123456789abcdef"}
groups = sorted([g for g in group_dict.values()], key=lambda g: g.name)


def get_resolutions():
    import re
    import subprocess
    cmd = ['xrandr']
    cmd2 = ['grep', '*']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(cmd2, stdin=p.stdout, stdout=subprocess.PIPE)
    p.stdout.close()

    lines = [line.split()[0] for line in p2.communicate()[0].split(b"\n") if line]
    resolutions = []
    for res in lines:
        w, h = re.sub("_.*", "", res.decode("utf-8")).split("x")
        resolutions.append({"width": int(w), "height": int(h)})

    return resolutions


def is_laptop_connected():
    return filter(lambda r: r["width"] == 1366 and r["height"] == 768,  get_resolutions())


res = get_resolutions()
num_screens = len(res)


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
        next , _ = get_group_and_screen_idx(qtile, offset)
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
            "in_debug_mode": in_debug_mode
        },
        "wal": get_wal_colors(),
    }
    default_vars.update(**overrides)
    return default_vars


def render_dunstrc(**overrides):
    if not in_debug_mode:
        templates.render("dunstrc", "~/.config/dunst", keep_comments=False,
                         keep_empty=False, overrides=get_default_vars(**overrides))


def render_compton_conf(**overrides):
    if not in_debug_mode:
        templates.render("compton.conf", "~/.config", keep_empty=True,
                         overrides=get_default_vars(**overrides))


def render_terminalrc(**overrides):
    if not in_debug_mode:
        colors = get_wal_colors(**overrides)
        templates.render("terminalrc", "~/.config/xfce4/terminal", keep_empty=True,
                         overrides=get_default_vars(**colors))


def restart_qtile(qtile: Qtile):
    procs.feh()
    for group in qtile.groups:
        for window in group.windows:
            try:
                window.opacity = window._full_opacity
            except AttributeError:
                pass
    qtile.cmd_restart()
    render_dunstrc()
    render_compton_conf()
    render_terminalrc()


@lazy.function
def start_distraction_free_mode(qtile: Qtile):
    procs.pause_dunst()


@lazy.function
def stop_distraction_free_mode(qtile: Qtile):
    procs.resume_dunst()
    procs.dunstify("including distractions again")


@lazy.function
def update_path(qtile: Qtile):
    path_file = os.path.join(os.path.expanduser("$"), ".config", "zsh", "path")
    tmp_file = "/tmp/zsh-export-path"
    subprocess.run(f"/usr/bin/zsh -c 'source {path_file}'", shell=True, env={"QTILE_EXPORT_PATH": tmp_file})
    with open(tmp_file, "r") as f:
        path_env = f.read()
    if path_env.strip():
        os.environ["PATH"] = path_env.strip()
