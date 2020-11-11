import os
import math
import psutil
import sqlite3
from libqtile import bar, widget
from libqtile.widget.base import Mirror
from libqtile.widget.generic_poll_text import GenPollText as _GenPollText
from widgets.capslocker import CapsLockIndicator
from widgets.checkclock_widget import CheckclockWidget
import datetime
import util
import color
import procs
import re
from pathlib import Path
import dbus


settings = dict(
    background=None,
    borderwidth=0,
    foreground=color.BRIGHT_GRAY,
)


class ArrowGraph(_GenPollText):

    defaults = [
        ("colors", ("005000", "909000", "e00000"), "4-tuple of colors to use for graph"),
        ("max", 100, "maximum value for graph (greater values will be clipped)"),
        ("use_diff", False, "if True, then display (current - last) value, else only current"),
        ("up_first", True, "if True, display up-arrow first, then down-arrow")
    ]

    def __init__(self, **config):
        super().__init__(**config)
        self.add_defaults(ArrowGraph.defaults)
        self.colors = tuple(color.hex_to_dec(c) for c in self.colors)
        if self.use_diff:
            self.up = 0
            self.down = 0
            self.poll()

    def span(self, text, color):
        return f"<span foreground='#{color}'>{text}</span>"

    def poll(self):
        up, down = super().poll()
        if self.use_diff:
            up_value = (up - self.up) / self.update_interval
            down_value = (down - self.down) / self.update_interval
            self.up, self.down = up, down
        else:
            up_value = up
            down_value = down
        up_color = color.gradient(value=up_value, max_value=self.max, colors=self.colors)
        down_color = color.gradient(value=down_value, max_value=self.max, colors=self.colors)
        if self.up_first:
            arrows = self.span("🠩", up_color), self.span("🠫", down_color)
        else:
            arrows = self.span("🠫", down_color), self.span("🠩", up_color)
        return "<tt><big>{}{}</big></tt>".format(*arrows)


class DotGraph(_GenPollText):

    defaults = [
        ("colors", ("00b800", "c0c000", "b80000"), "4-tuple of colors to use for graph"),
        ("max", 100, "maximum value for graph (greater values will be clipped)"),
        ("graph_length", 4, "number of previous plus current values to be displayed")
    ]
    previous_dots = [0x40, 0x40 + 0x4, 0x40 + 0x4 + 0x2, 0x40 + 0x4 + 0x2 + 0x1]
    current_dots = [0x80, 0x80 + 0x20, 0x80 + 0x20 + 0x10, 0x80 + 0x20 + 0x10 + 0x8]

    def __init__(self, **config):
        super().__init__(**config)
        self.add_defaults(DotGraph.defaults)
        self.graph_length *= 2
        self.values = (0,) * self.graph_length
        self.colors = tuple(color.hex_to_dec(c) for c in self.colors)

    def single_dot(self, prev, cur):
        p = self.normalize(prev)
        c = self.normalize(cur)
        return chr(ord("\u2800") + self.previous_dots[p] + self.current_dots[c])

    def normalize(self, value):
        return max(0, min(3, math.floor(value * len(self.colors) / self.max)))

    def as_dots(self, *values):
        dots = "".join(self.single_dot(*values[i:i+2]) for i in range(0, self.graph_length-1, 2))
        avg = sum(values)/len(values)
        c = color.gradient(value=avg, max_value=self.max, colors=self.colors, scaling=1.2)
        return f"<tt><span foreground='#{c}'>{dots}</span></tt>"

    def poll(self):
        polled_value = super().poll()
        self.values = (*self.values[1:], polled_value)
        return self.as_dots(*self.values)


def space():
    return widget.Spacer(length=10)


def get_num_procs():
    number = sum(1 for _ in psutil.process_iter())
    c = color.gradient(value=number-250, max_value=200,
                       colors=(color.hex_to_dec(color.BRIGHT_GREEN),
                               color.hex_to_dec(color.BRIGHT_ORANGE),
                               color.hex_to_dec(color.BRIGHT_RED)))
    return f"<span foreground='#{c}'>{number}</span>"


def get_net_throughput():
    net = psutil.net_io_counters(pernic=True)
    ethernet_name = "enp0s31f6"
    wifi_name = "wlp4s0"
    up = net[ethernet_name].bytes_sent + net[wifi_name].bytes_sent
    down = net[ethernet_name].bytes_recv + net[wifi_name].bytes_recv
    return up, down


def notify_checkclock_pause(is_paused: bool, _: str):
    p = "pause" if is_paused else "resume"
    procs.dunstify(f"{p} checkclock")


paused_text = "<big>⏸</big>"
checkclock_id = "--replace=840431"
checkclock_args = dict(
        update_interval=5,
        paused_text=paused_text,
        time_format="%k:%M",
        paused_color=color.MID_ORANGE,
        active_color=color.RED,
        default_text=paused_text,
        pause_button=3,
        done_color=color.GREEN,
        almost_done_color=color.YELLOW,
        working_days="Tue-Fri",
        avg_working_time=(7*3600 + 45*60),
        hooks={
            "on_rollover": lambda _: procs.dunstify(checkclock_id, f"🔄 checkclock"),
            },
        )
checkclock_args.update(settings)

if util.in_debug_mode:
    checkclock_args["db_path"] = "/tmp/checkclock.sqlite"

checkclock_widget = CheckclockWidget(**checkclock_args)

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
        fontsize=12,
        padding=10,
        cursor_color=color.MID_ORANGE,
        cursorblink=0.8,
        foreground=color.MID_ORANGE,
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
        widgets.append(checkclock_widget)
        widgets.append(widget.Systray(icon_size=18, padding=8, **settings))
    else:
        widgets.append(checkclock_widget.new_companion())

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


    def run_htop(qtile):
        qtile.cmd_spawn(["xfce4-terminal", "-e", "htop"])


    cpu_graph = DotGraph(func=psutil.cpu_percent, max=100, update_interval=1,
            mouse_callbacks={"Button1": run_htop}, **settings)
    widgets.append(cpu_graph)

    net_graph = ArrowGraph(func=get_net_throughput, max=(1 << 20), update_interval=1,
            use_diff=True, up_first=False, **settings)
    widgets.append(net_graph)

    num_procs = widget.GenPollText(func=get_num_procs, update_interval=2)
    widgets.append(num_procs)

    clock = widget.Clock(format=' %Y-%m-%d %H:%M', **settings)
    widgets.append(clock)
    layout = widget.CurrentLayoutIcon(scale=0.7, **settings)
    widgets.append(layout)

    return bar.Bar(
        widgets=widgets,
        size=26,
        opacity=0.9
    )
