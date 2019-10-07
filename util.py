import re
import subprocess
from libqtile.command import lazy


def get_resolutions():
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


def go_to_group(res, group):

    @lazy.function
    def f(qtile):
        if len(res) == 2 and group.name in "abcdef":
            screen = 1
        else:
            screen = 0
        print(f"group: {group.name}, screen: {screen}")
        qtile.cmd_to_screen(screen)
        qtile.groups_map[group.name].cmd_toscreen()

    return f


def next_group(res):
    if len(res) == 1:
        return lazy.screen.next_group()

    groups = [ch for ch in "123456789abcdef"]

    @lazy.function
    def f(qtile):
        group = qtile.current_group.name
        idx = groups.index(group)
        next_group = groups[(idx+1) % len(groups)]
        screen = 0 if next_group < "a" else 1
        print(f"group: {group}, screen: {screen}")
        qtile.cmd_to_screen(screen)
        qtile.groups_map[next_group].cmd_toscreen()

    return f


def prev_group(res):
    if len(res) == 1:
        return lazy.screen.prev_group()

    groups = [ch for ch in "123456789abcdef"]

    @lazy.function
    def f(qtile):
        group = qtile.current_group.name
        idx = groups.index(group)
        prev_group = groups[(idx-1) % len(groups)]
        screen = 0 if prev_group < "a" else 1
        print(f"group: {group}, screen: {screen}")
        qtile.cmd_to_screen(screen)
        qtile.groups_map[prev_group].cmd_toscreen()

    return f
