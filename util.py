# import re
# import subprocess
import os
import yaml
import pywal
import procs
from libqtile.command import lazy
import templates
from color import complement, add_hashtag


in_debug_mode = os.environ.get("QTILE_DEBUG_MODE", "off") == "on"


def get_resolutions():
    import re
    import subprocess
    cmd = ['xrandr']
    cmd2 = ['grep', '*']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(cmd2, stdin=p.stdout, stdout=subprocess.PIPE)
    p.stdout.close()

    lines = p2.communicate()[0].split()
    resolutions = []
    for res in lines[::2]:
        w, h = re.sub("_.*", "", res.decode("utf-8")).split("x")
        resolutions.append({"width": w, "height": h})
    return resolutions


res = get_resolutions()
num_screens = len(res)


def go_to_group(group):

    @lazy.function
    def f(qtile):
        if len(qtile.screens) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        qtile.cmd_to_screen(screen)
        qtile.groups_map[group.name].cmd_toscreen()

    return f


def next_group():
    if num_screens == 1:
        return lazy.screen.next_group()

    groups = [ch for ch in "123456789abcdef"]

    @lazy.function
    def f(qtile):
        group = qtile.current_group.name
        idx = groups.index(group)
        next_group = groups[(idx+1) % len(groups)]
        screen = 0 if next_group < "a" else 1
        qtile.cmd_to_screen(screen)
        qtile.groups_map[next_group].cmd_toscreen()

    return f


def prev_group():
    if num_screens == 1:
        return lazy.screen.prev_group()

    groups = [ch for ch in "123456789abcdef"]

    @lazy.function
    def f(qtile):
        group = qtile.current_group.name
        idx = groups.index(group)
        prev_group = groups[(idx-1) % len(groups)]
        screen = 0 if prev_group < "a" else 1
        qtile.cmd_to_screen(screen)
        qtile.groups_map[prev_group].cmd_toscreen()

    return f


@lazy.function
def spawncmd(qtile):
    screen = qtile.current_screen.index
    command = "zsh -c '%s'"
    return qtile.cmd_spawncmd(widget=f"prompt-{screen}", command=command)


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
    return {
        "colors": colors["colors"].values(),
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


def restart_qtile(qtile):
    procs.feh()
    qtile.cmd_restart()
    render_dunstrc()
    render_compton_conf()
    render_terminalrc()
