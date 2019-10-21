import psutil
import math
from libqtile import bar, widget
from widgets.capslocker import CapsLockIndicator
import util
import color

settings = dict(
    background=None,
    borderwidth=0,
    foreground=color.BRIGHT_GRAY,
)


class DotGraph(widget.GenPollText):

    defaults = [
        ("colors", ("00b800", "40b800", "b0b000", "b80000"), "4-tuple of colors to use for graph"),
        ("max", 100, "maximum value for graph (greater values will be clipped)"),
        ("graph_length", 4, "number of previous plus current values to be displayed")
    ]
    previous_dots = [0x40, 0x40 + 0x4, 0x40 + 0x4 + 0x2, 0x40 + 0x4 + 0x2 + 0x1]
    current_dots = [0x80, 0x80 + 0x20, 0x80 + 0x20 + 0x10, 0x80 + 0x20 + 0x10 + 0x8]

    def __init__(self, **config):
        super().__init__(**config)
        self.add_defaults(DotGraph.defaults)
        print(self.graph_length)
        self.graph_length *= 2
        self.values = (0,) * self.graph_length
        # self.dot_values = (f"<span foreground='{self.colors[0]}'>\u28c0</span>",) * self.graph_length
        self.colors = [c if c.startswith("#") else f"#{c}" for c in self.colors]

    def single_dot(self, prev, cur):
        return chr(ord("\u2800") + self.previous_dots[prev] + self.current_dots[cur])

    def as_dots(self, *values):
        dots = "".join(self.single_dot(*values[i:i+2]) for i in range(0, self.graph_length-1, 2))
        avg = round(sum(values)/len(values))
        color = self.colors[avg]
        # return f"<span foreground='{color}'>{dots}</span>"
        return f"<tt><span foreground='{color}'>{dots}</span></tt>"

    def poll(self):
        polled_value = super().poll()
        val = max(0, min(3, math.floor(polled_value * 4 / self.max)))
        self.values = (*self.values[1:], val)
        # FIXME for performance reasons
        # self.dot_values = (*self.dot_values[1:], self.to_dot(*self.values[-2:]))
        # text = "".join(self.dot_values)
        # text = "".join(self.to_dot(*self.values[i:i+2]) for i in range(0, self.graph_length-1, 2))
        # return f"<tt>{text}</tt>"
        return self.as_dots(*self.values)


def space():
    return widget.Spacer(length=10)


def get_num_procs():
    number = sum(1 for _ in psutil.process_iter())
    if number < 300:
        c = color.BRIGHT_GREEN
    elif number < 400:
        c = color.BRIGHT_ORANGE
    else:
        c = color.BRIGHT_RED
    return f"<span foreground='#{c}'>{number}</span>"


def get_bar(screen_idx):
    is_primary = screen_idx == 0
    widgets = []

    group_settings = {
        "highlight_method": "block",
        "active": color.BRIGHT_ORANGE,
        "inactive": color.DARK_GRAY,
        "this_screen_border": color.DARK_BLUE_GRAY,
        "this_current_screen_border": color.MID_BLUE_GRAY,
        "hide_unused": False,
        "urgent_border": color.BRIGHT_RED,
        "disable_drag": True,
    }
    if util.num_screens > 1:
        if is_primary:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "123456789"], **settings, **group_settings)
        else:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "abcdef"], **settings, **group_settings)
    else:
        group_box = widget.GroupBox(**settings, **group_settings)
    widgets.append(group_box)

    if util.num_screens > 1:
        current_screen = widget.CurrentScreen(
            active_text="✔",
            inactive_text="",
            active_color=color.BRIGHT_ORANGE,
            inactive_color=color.BLACK,
            **settings
        )
        widgets.append(current_screen)

    prompt_args = settings.copy()
    prompt_args.update(
        name=f"prompt-{screen_idx}",
        prompt="» ",
        fontsize=11,
        padding=10,
        foreground=color.MID_BLUE_GRAY,
    )
    prompt = widget.Prompt(**prompt_args)
    widgets.append(prompt)

    task_args = settings.copy()
    task_args.update(
        highlight_method="block",
        border=color.DARK_ORANGE,
        foreground=color.BRIGHT_GRAY,
    )
    task_list = widget.TaskList(**task_args)
    widgets.append(task_list)

    if is_primary:
        widgets.append(widget.Systray(icon_size=18, padding=8, **settings))

    widgets.append(space())

    volume = widget.Volume(
        cardid=0,
        device=None,
        theme_path="/usr/share/icons/HighContrast/256x256",
        volume_app="pavucontrol",
        **settings
    )
    widgets.append(volume)
    caps_lock = CapsLockIndicator(send_notifications=is_primary, **settings)
    widgets.append(caps_lock)

    cpu_graph = DotGraph(func=psutil.cpu_percent, max=100, update_interval=1, **settings)
    widgets.append(cpu_graph)

    num_procs = widget.GenPollText(func=get_num_procs, update_interval=2)
    widgets.append(num_procs)

    clock = widget.Clock(format='%Y-%m-%d %H:%M', **settings)
    widgets.append(clock)
    layout = widget.CurrentLayoutIcon(scale=0.7, **settings)
    widgets.append(layout)

    return bar.Bar(
        widgets=widgets,
        size=23,
        opacity=0.9
    )
