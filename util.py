# import re
# import subprocess
from libqtile.command import lazy


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
    if len(res) == 1:
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
    if len(res) == 1:
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
    return qtile.cmd_spawncmd(widget=f"prompt-{screen}")


def move_to_screen(dest_screen):
    if len(res) == 1:
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
    if len(res) == 1:
        return lambda *args, **kwargs: None

    @lazy.function
    def f(qtile):
        idx = qtile.current_screen.index
        if dest_screen == idx:
            return
        qtile.cmd_to_screen(dest_screen)

    return f
