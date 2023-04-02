import os
import re
import math
import psutil
import sqlite3
from typing import Optional, Any, TYPE_CHECKING, Callable
from libqtile import bar

if TYPE_CHECKING:
    from libqtile import widget
else:
    from qtile_extras import widget
from libqtile.widget.base import Mirror
from libqtile.widget.generic_poll_text import GenPollText as _GenPollText
from libqtile.scratchpad import ScratchPad
from libqtile.log_utils import logger
from qutely.widgets.capslocker import CapsLockIndicator

from qutely.widgets.checkclock_widget import CheckclockWidget
from qutely.widgets.check_and_warn import CheckAndWarnWidget, CheckState

# from widgets.contextmenu import ContextMenu, SpawnedMenu
import datetime
from qutely import util, color, procs
from pathlib import Path

PARTITIONS = {
    "/": "G",
    "/home": "G",
    "/tmp": "G",
    "/var": "G",
    "/boot": "M",
    "/boot/efi": "M",
    "/var/lib/docker": "G",
}

# import dbus_next

if util.is_light_theme:
    background = color.WHITE
    mid_color = color.BRIGHT_GRAY
    foreground = color.DARK_GRAY
    bar_bg = background
else:
    background = None
    mid_color = color.DARK_GRAY
    foreground = color.BRIGHT_GRAY
    bar_bg = "#000000ff"


settings = dict(
    background=background,
    borderwidth=0,
    foreground=foreground,
)


def proc_fn(*args: str, shell: bool = False) -> Callable[[], None]:
    from libqtile import qtile

    cmd_args = (["xfce4-terminal", "-e"]) if shell else []
    cmd_args += args

    def run() -> None:
        qtile.cmd_spawn(cmd_args)

    return run


class UPowerWidget(widget.UPowerWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._charging = False
        super().__init__(*args, **kwargs)

    @property
    def charging(self) -> bool:
        if not self._charging:
            return False
        fraction = max(b.get("fraction", 0) for b in self.batteries)
        return fraction < 1

    @charging.setter
    def charging(self, charging: bool) -> None:
        self._charging = charging


class GroupBox(widget.GroupBox):

    defaults = [
        (
            "always_visible_groups",
            (),
            "groups that are visible even when hide_unused is set, and group is empty",
        ),
        ("hide_scratchpads", True, "whether to always hide scratchpads"),
    ]

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.add_defaults(GroupBox.defaults)

    @property
    def groups(self) -> list[str]:
        groups = (
            g
            for g in self.qtile.groups
            if not self.hide_scratchpads or not isinstance(g, ScratchPad)
        )
        if self.hide_unused:
            if self.visible_groups:
                return [
                    g
                    for g in groups
                    if g.label
                    and (
                        ((g.windows or g.screen) and g.name in self.visible_groups)
                        or g.name in self.always_visible_groups
                    )
                ]
            else:
                return [
                    g
                    for g in groups
                    if g.label
                    and ((g.windows or g.screen) or g.name in self.always_visible_groups)
                ]
        else:
            if self.visible_groups:
                return [
                    g
                    for g in groups
                    if g.label
                    and (g.name in self.visible_groups or g.name in self.always_visible_groups)
                ]
            else:
                return [g for g in self.qtile.groups if g.label]


class ArrowGraph(_GenPollText):

    defaults = [
        ("colors", ("005000", "909000", "e00000"), "4-tuple of colors to use for graph"),
        ("max", 100, "maximum value for graph (greater values will be clipped)"),
        ("use_diff", False, "if True, then display (current - last) value, else only current"),
        ("up_first", True, "if True, display up-arrow first, then down-arrow"),
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
        ("graph_length", 4, "number of previous plus current values to be displayed"),
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
        dots = "".join(
            self.single_dot(*values[i : i + 2]) for i in range(0, self.graph_length - 1, 2)
        )
        avg = sum(values) / len(values)
        c = color.gradient(value=avg, max_value=self.max, colors=self.colors, scaling=1.2)
        return f"<tt><span foreground='#{c}'>{dots}</span></tt>"

    def poll(self):
        polled_value = super().poll()
        self.values = (*self.values[1:], polled_value)
        return self.as_dots(*self.values)


def space():
    return widget.Spacer(length=10, background=background)


def get_num_procs():
    number = sum(1 for _ in psutil.process_iter())
    c = color.gradient(
        value=number - 250,
        max_value=200,
        colors=(
            color.hex_to_dec(color.BRIGHT_GREEN),
            color.hex_to_dec(color.BRIGHT_ORANGE),
            color.hex_to_dec(color.BRIGHT_RED),
        ),
    )
    return f"<span foreground='#{c}'>{number}</span>"


def get_net_throughput():
    net = psutil.net_io_counters(pernic=True)
    ethernet_name = "enp0s31f6"
    wifi_name = "wlp4s0"
    up = net[ethernet_name].bytes_sent + net[wifi_name].bytes_sent
    down = net[ethernet_name].bytes_recv + net[wifi_name].bytes_recv
    return up, down


class BorgBackupWidget(CheckAndWarnWidget):

    borg_state_msgs = {
        CheckState.OK: "has finished",
        CheckState.WARN: "required",
        CheckState.ERROR: "has encountered an error",
        CheckState.IN_PROGRESS: "has started",
    }

    dunstify_id = 398437

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.cache_file = Path("/home/lars/.cache/backup-with-borg-state")
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir()

    def check(self) -> CheckState:
        if not self.cache_file.exists():
            return CheckState.WARN
        mtime = self.cache_file.lstat().st_mtime
        dt = datetime.datetime.fromtimestamp(mtime)
        if dt.date() < datetime.date.today():
            return CheckState.WARN
        with self.cache_file.open("r") as f:
            text = f.read().strip()
        if text in ("in-progress", "pruning"):
            return CheckState.IN_PROGRESS
        elif text == "success":
            return CheckState.OK
        else:
            return CheckState.ERROR

    def run(self) -> None:
        procs._dunstify("starting borg backup")
        procs._borg_backup()
        self.update(text=self.poll(state=CheckState.IN_PROGRESS))

    def cmd_reset(self) -> None:
        if self.cache_file.exists():
            self.cache_file.unlink()

    def on_state_changed(self, current: Optional[CheckState], next: CheckState) -> None:
        if current == next or not current:
            return
        urgency = "critical" if next is CheckState.ERROR else "normal"
        procs._dunstify(
            f"--replace={self.dunstify_id}",
            "-u",
            urgency,
            "borg backup",
            self.borg_state_msgs[next],
        )


borg_widget = BorgBackupWidget(fontsize=12, ok_text="", update_interval=10, background=background)


def notify_checkclock_pause(is_paused: bool, _: str):
    p = "pause" if is_paused else "resume"
    procs._dunstify(f"{p} checkclock")


paused_text = "<big>⏸</big>"
checkclock_id = "--replace=840431"
checkclock_args = dict(
    background=background,
    update_interval=5,
    paused_text=paused_text,
    time_format="%k:%M",
    paused_color=color.MID_ORANGE,
    active_color=color.RED,
    default_text=paused_text,
    pause_button=3,
    done_color=color.GREEN,
    almost_done_color=color.YELLOW,
    working_days="Mon-Sun",
    # avg_working_time=(7 * 3600 + 45 * 60),
    avg_working_time=4 * 3600,
    hooks={
        "on_rollover": lambda _: procs._dunstify(checkclock_id, "🔄 checkclock"),
    },
)
checkclock_args.update(settings)

db_key = "QTILE_CHECKCLOCK_DB"
if db_key in os.environ:
    checkclock_args["db_path"] = os.environ[db_key]

# checkclock_widget = CheckclockWidget(**checkclock_args)


def get_bar(screen_idx: int):
    is_primary = screen_idx == 0
    widgets = []

    group_settings = {
        "highlight_method": "block",
        "border": color.DARK_ORANGE,
        "border_width": 5,
        "active": color.DARK_ORANGE if util.is_light_theme else color.BRIGHT_ORANGE,
        "inactive": mid_color,
        "this_screen_border": color.DARK_BLUE_GRAY,
        "this_current_screen_border": color.MID_BLUE_GRAY,
        "hide_unused": True,
        "urgent_border": color.BRIGHT_RED,
        "disable_drag": True,
        "font": "Hack Patched",
        "fontsize": 18,
        "markup": True,
    }
    if util.num_screens > 1:
        if is_primary:
            group_box = GroupBox(
                name="groupbox-0",
                visible_groups=[ch for ch in "123456789"],
                **settings,
                always_visible_groups=("1"),
                **group_settings,
            )
        else:
            group_box = GroupBox(
                name="groupbox-1",
                visible_groups=[ch for ch in "abcdef"],
                always_visible_groups=("f"),
                **settings,
                **group_settings,
            )
    else:
        group_box = GroupBox(
            always_visible_groups=("1", "f"), name="groupbox-0", **settings, **group_settings
        )
    widgets.append(group_box)

    if util.num_screens > 1:
        current_screen = widget.CurrentScreen(
            active_text="✔",
            inactive_text="",
            active_color=color.BRIGHT_ORANGE,
            inactive_color=color.WHITE if util.is_light_theme else color.BLACK,
            **settings,
        )
        widgets.append(current_screen)

    # prompt_args = settings.copy()
    # prompt_args.update(
    #     name=f"prompt-{screen_idx}",
    #     prompt="» ",
    #     fontsize=12,
    #     padding=10,
    #     cursor_color=color.MID_ORANGE,
    #     cursorblink=0.8,
    #     foreground=color.MID_ORANGE,
    # )
    # prompt = widget.Prompt(**prompt_args)
    # widgets.append(prompt)

    task_args = settings.copy()
    task_args.update(
        highlight_method="border" if util.is_light_theme else "block",
        border=color.DARK_ORANGE,
        foreground=foreground,
        background=background,
    )
    task_list = widget.TaskList(**task_args)
    widgets.append(task_list)

    kdb_settings = settings | dict(
        configured_keyboards=["de deadacute", "de"],
        display_map={"de deadacute": "de", "de": "de (no coding)"},
        foreground=color.MID_GRAY,
    )
    kbd = widget.KeyboardLayout(**kdb_settings)

    if is_primary:
        widgets.append(borg_widget)
        # widgets.append(checkclock_widget)
        widgets.append(space())
        widgets.append(kbd)

        # widgets.append(widget.StatusNotifier(icon_size=18, padding=8, **settings))
        widgets.append(widget.Systray(icon_size=18, padding=8, **settings))
        for partition, unit in PARTITIONS.items():
            df = widget.DF(
                visible_on_warn=True,
                partition=partition,
                warn_color=color.BRIGHT_ORANGE,
                measure=unit,
                update_interval=5,
            )
            widgets.append(df)
    else:
        # widgets.append(checkclock_widget.new_companion())
        pass

    widgets.append(space())

    battery = UPowerWidget(
        # battery_name="hidpp_battery_0",
        border_charge_colour=color.DARK_GREEN,
        fill_charge=color.BRIGHT_GREEN,
        fill_critical=color.RED,
        fill_normal=color.MID_BLUE_GRAY,
        border_colour=color.DARK_ORANGE,
        border_critical_colour=color.BRIGHT_RED,
        mouse_callbacks={"Button3": proc_fn("xfce4-power-manager", "--customize")},
        **settings,
    )
    widgets.append(battery)
    widgets.append(space())

    volume_settings = settings | dict(
        cardid=0,
        device=None,
        emoji=True,
        fontsize=18,
        font="Ubuntu",
        # theme_path="/usr/share/icons/HighContrast/256x256",
        volume_app="pavucontrol",
        foreground=color.MID_GRAY,
    )
    volume = widget.Volume(**volume_settings)
    widgets.append(volume)

    caps_lock = CapsLockIndicator(send_notifications=is_primary, **settings)
    widgets.append(caps_lock)

    cpu_graph = DotGraph(
        func=psutil.cpu_percent,
        max=100,
        update_interval=1,
        mouse_callbacks={"Button1": proc_fn("htop", shell=True)},
        **settings,
    )
    widgets.append(cpu_graph)

    net_graph = ArrowGraph(
        func=get_net_throughput,
        max=(1 << 20),
        update_interval=1,
        use_diff=True,
        up_first=False,
        **settings,
    )
    widgets.append(net_graph)

    # menu = SpawnedMenu("num_procs", {"a": lambda qtile: print("hello")}, min_width=10)

    num_procs = widget.GenPollText(
        func=get_num_procs,
        update_interval=2,
        background=background,
        # mouse_callbacks={"Button3": menu.show}
    )
    widgets.append(num_procs)

    clock = widget.Clock(format=" %Y-%m-%d %H:%M", **settings)
    widgets.append(clock)
    layout = widget.CurrentLayoutIcon(scale=0.7, **settings)
    widgets.append(layout)

    return bar.Bar(widgets=widgets, size=26, background=bar_bg)
