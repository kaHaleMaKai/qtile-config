from __future__ import annotations

import os
import re
import math
import shutil
import psutil
import asyncio
import subprocess
from enum import Enum
from typing import Optional, Any, TYPE_CHECKING, Callable, override
from libqtile import bar
from libqtile.command.base import expose_command
from libqtile.utils import add_signal_receiver
from dbus_fast import Message, MessageType, BusType, Variant
from dbus_fast.aio import MessageBus

if TYPE_CHECKING:
    from libqtile import widget
else:
    from qtile_extras import widget
from qtile_extras.widget.decorations import BorderDecoration
from libqtile.widget.base import Mirror, ThreadPoolText
from libqtile.widget.generic_poll_text import GenPollText as _GenPollText
from libqtile.scratchpad import ScratchPad
from libqtile.log_utils import logger
from qutely.widgets.capslocker import CapsLockIndicator

from qutely.widgets.checkclock_widget import CheckclockWidget
from qutely.widgets.check_and_warn import CheckAndWarnWidget, CheckState

# from widgets.contextmenu import ContextMenu, SpawnedMenu
import datetime
from qutely import util, color, procs
from qutely.display import sync_get_xrandr_output
from pathlib import Path

BAR_HEIGHT = 26
IFACES = ["wlan0", "usb0", "eth0", "vpn0", "tailscale0"]
MAIN_VPN = "tailscale0"
# MAIN_VPN = "openconnect-piam"

PARTITIONS = {
    "/": "M",
    "/home": "M",
    "/tmp": "M",
    "/opt": "M",
    "/var": "M",
    "/home/lars/git": "M",
    "/home/lars/local": "M",
    "/var/cache": "M",
    "/var/log": "M",
}

# import dbus_next

if util.is_light_theme:
    background = color.WHITE
    mid_color = color.BRIGHT_GRAY
    foreground = color.DARK_GRAY
    BAR_BG = background
else:
    background = None
    mid_color = color.DARK_GRAY
    foreground = color.BRIGHT_GRAY
    BAR_BG = "#000000ff"


settings = dict(
    background=background,
    borderwidth=0,
    foreground=foreground,
)


def proc_fn(*args: str, shell: bool = False) -> Callable[[], None]:
    from libqtile import qtile

    cmd_args = (["kitty"]) if shell else []
    cmd_args += args

    def run() -> None:
        qtile.cmd_spawn(cmd_args)

    return run


class Urgency(Enum):
    LOW = 0
    NORMAL = 1
    CRITICAL = 2


class Notifier:
    IFACE = "org.freedesktop.Notifications"
    PATH = "/org/freedesktop/Notifications"
    METHOD = "Notify"
    SIGNATURE = "susssasa{sv}i"

    def __init__(
        self,
        bus: MessageBus,
        id: int,
        app: str,
        default_img: Path | None,
        low_timeout: int,
        normal_timeout: int,
        critical_timeout: int,
    ) -> None:
        self.bus = bus
        self.id = id
        self.app = app
        self.default_img = default_img
        self.timeouts = {
            Urgency.LOW: low_timeout,
            Urgency.NORMAL: normal_timeout,
            Urgency.CRITICAL: critical_timeout,
        }

    async def send(
        self,
        title: str,
        msg: str,
        img: Path | None = None,
        urgency: Urgency = Urgency.NORMAL,
    ) -> None:
        img_path = img or self.default_img
        img_string = str(img_path) if img_path else ""
        msg = Message(
            destination=self.IFACE,
            path=self.PATH,
            interface=self.IFACE,
            member=self.METHOD,
            signature=self.SIGNATURE,
            body=[
                self.app,
                self.id,
                img_string,
                title,
                msg,
                [],
                {"urgency": Variant("u", urgency.value)},
                self.timeouts[urgency],
            ],
        )
        res = await self.bus.call(msg)
        if res.message_type is not MessageType.METHOD_RETURN:
            logger.warn(f"could not send notification: {title!r}, {msg!r}")

    def sync_send(
        self,
        title: str,
        msg: str,
        img: Path | None = None,
        urgency: Urgency = Urgency.NORMAL,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            logger.exception("could not send message synchronously", e)
            return
        _ = asyncio.run_coroutine_threadsafe(self.send(title, msg, img, urgency), loop)

    @classmethod
    async def of(
        cls,
        id: int,
        app: str,
        session: bool = True,
        default_img: Path | None = None,
        low_timeout: int = 1000,
        normal_timeout: int = 3000,
        critical_timeout: int = -1,
    ) -> Notifier:
        t = BusType.SESSION if session else BusType.SYSTEM
        bus = await MessageBus(bus_type=t).connect()
        return cls(
            bus, id, app, default_img, low_timeout, normal_timeout, critical_timeout
        )

    @classmethod
    def sync_of(
        cls,
        id: int,
        app: str,
        session: bool = True,
        default_img: Path | None = None,
        low_timeout: int = 1000,
        normal_timeout: int = 3000,
        critical_timeout: int = -1,
    ) -> Notifier:
        task = asyncio.create_task(
            cls.of(
                id,
                app,
                session,
                default_imt,
                low_timeout,
                normal_timeout,
                critical_timeout,
            )
        )
        return task.result()


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
                    and (
                        (g.windows or g.screen) or g.name in self.always_visible_groups
                    )
                ]
        else:
            if self.visible_groups:
                return [
                    g
                    for g in groups
                    if g.label
                    and (
                        g.name in self.visible_groups
                        or g.name in self.always_visible_groups
                    )
                ]
            else:
                return [g for g in self.qtile.groups if g.label]


class ArrowGraph(_GenPollText):
    defaults = [
        (
            "colors",
            ("005000", "909000", "f08080"),
            "4-tuple of colors to use for graph",
        ),
        ("max", 100, "maximum value for graph (greater values will be clipped)"),
        (
            "use_diff",
            False,
            "if True, then display (current - last) value, else only current",
        ),
        ("up_first", True, "if True, display up-arrow first, then down-arrow"),
    ]

    def __init__(self, **config):
        super().__init__(**config)
        self.add_defaults(ArrowGraph.defaults)
        self.colors = tuple(color.hex_to_dec(c) for c in self.colors)
        self.up = 0
        self.down = 0
        if self.use_diff:
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
        up_color = color.gradient(
            value=up_value, max_value=self.max, colors=self.colors
        )
        down_color = color.gradient(
            value=down_value, max_value=self.max, colors=self.colors
        )
        if self.up_first:
            arrows = self.span("🠩", up_color), self.span("🠫", down_color)
        else:
            arrows = self.span("🠫", down_color), self.span("🠩", up_color)
        return "<tt><big>{}{}</big></tt>".format(*arrows)


class DotGraph(_GenPollText):
    defaults = [
        (
            "colors",
            ("00b800", "c0c000", "b80000"),
            "4-tuple of colors to use for graph",
        ),
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
            self.single_dot(*values[i : i + 2])
            for i in range(0, self.graph_length - 1, 2)
        )
        avg = sum(values) / len(values)
        c = color.gradient(
            value=avg, max_value=self.max, colors=self.colors, scaling=1.2
        )
        return f"<tt><span foreground='#{c}'>{dots}</span></tt>"

    def poll(self):
        polled_value = super().poll()
        self.values = (*self.values[1:], polled_value)
        return self.as_dots(*self.values)


def space():
    return widget.Spacer(length=14, background=background)


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


class VpnStatus(ThreadPoolText):
    UP_SYMBOL = f"<span foreground='#{color.MID_GRAY}'></span>  "
    CONNECTED_MSG = "vpn connected "
    DISCONNECTED_MSG = "vpn disconnected "
    VPN_IS_ACTIVE_PATTERN = re.compile(r"ipv4.addresses:.*[0-9.]+/[0-9]+$")

    defaults = [
        ("vpn", None, "name of the VPN to monitor"),
    ]

    notifier: Notifier | None

    def __init__(self, **config):
        ThreadPoolText.__init__(self, "", **config)
        self.add_defaults(VpnStatus.defaults)
        self.notifier = None

    def notify(self, title: str, msg: str, urgency: Urgency) -> None:
        if not self.notifier:
            return
        self.notifier.sync_send(title=title, msg=msg, urgency=urgency)

    def _on_vpn_change(self, signal: Message) -> None:
        state, reason = signal.body
        if state == 5 and reason == 1:
            self.update(self.UP_SYMBOL)
            self.notify("VPN", self.CONNECTED_MSG, Urgency.NORMAL)
        else:
            self.update("")
            if state == 7:
                self.notify("VPN", self.DISCONNECTED_MSG, Urgency.NORMAL)

    def _on_tailscale_change(self, signal: Message) -> None:
        state, reason = signal.body
        if state == 5 and reason == 1:
            self.update(self.UP_SYMBOL)
            self.notify("VPN", self.CONNECTED_MSG, Urgency.NORMAL)
        else:
            self.update("")
            if state == 7:
                self.notify("VPN", self.DISCONNECTED_MSG, Urgency.NORMAL)

    async def _config_async(self):
        self.notifier = await Notifier.of(
            app="VPN",
            id=123654,
            default_img=Path("/home/lars/images/penguin-sigil.png"),
        )
        subscribe = await add_signal_receiver(
            self._on_vpn_change,
            session_bus=False,
            signal_name="VpnStateChanged",
            dbus_interface="org.freedesktop.NetworkManager.VPN.Connection",
        )

    def poll(self) -> str:
        p = subprocess.Popen(
            ("nmcli", "con", "show", self.vpn),
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
        )
        try:
            output, _ = p.communicate(timeout=5)
            if (
                not p.returncode
                and output
                and self.VPN_IS_ACTIVE_PATTERN.search(output)
            ):
                return self.UP_SYMBOL
        except TimeoutError:
            p.kill(timeout=5)
        return ""


def get_tailscale_state() -> str:
    p = subprocess.Popen(("tailscale", "status"), stderr=None, stdout=None)
    rc = p.wait()
    # tailscale active -> rc=0, else rc=1
    if not rc:
        return f"<span foreground='#{color.MID_GRAY}'></span>  "
    else:
        return ""


def get_net_throughput():
    net = psutil.net_io_counters(pernic=True)
    up = sum(net_dev.bytes_sent for dev in IFACES if (net_dev := net.get(dev, 0)))
    down = sum(net_dev.bytes_recv for dev in IFACES if (net_dev := net.get(dev, 0)))
    return up, down


class BorgBackupWidget(CheckAndWarnWidget):
    firefox_profile: str | None

    borg_state_msgs = {
        CheckState.OK: "has finished",
        CheckState.WARN: "required",
        CheckState.ERROR: "has encountered an error",
        CheckState.IN_PROGRESS: "has started",
    }

    defaults = [
        ("firefox_profile", None, "name of the firefox profile"),
    ]

    notifier: Notifier | None

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.add_defaults(BorgBackupWidget.defaults)
        self.cache_file = Path("/home/lars/.cache/backup-with-borg-state")
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir()
        self.notifier = None

    async def _config_async(self) -> None:
        self.notifier = await Notifier.of(
            app="Borg", id=123655, default_img=Path("/home/lars/images/borg-backup.png")
        )

    def check(self) -> CheckState:
        if not self.cache_file.exists():
            return CheckState.WARN
        mtime = self.cache_file.lstat().st_mtime
        dt = datetime.datetime.fromtimestamp(mtime)
        if dt.date() < datetime.date.today():
            return CheckState.WARN
        with self.cache_file.open("r") as f:
            text = f.read().strip()
        if text in ("in-progress", "pruning", "compacting"):
            return CheckState.IN_PROGRESS
        elif text == "success":
            return CheckState.OK
        else:
            return CheckState.ERROR

    def notify(self, title: str, msg: str, urgency: Urgency) -> None:
        if not self.notifier:
            return
        self.notifier.sync_send(title=title, msg=msg, urgency=urgency)

    def run(self) -> None:
        self.notify("borg", "starting backup", Urgency.NORMAL)
        if self.firefox_profile:
            try:
                ff = Path.home() / ".mozilla/firefox"
                places_bk = ff / "places"
                places_bk.mkdir(exist_ok=True)
                bk_filename = datetime.date.today().strftime("places.sqlite-%F")
                src = ff / f"{self.firefox_profile}/places.sqlite"
                dest = places_bk / bk_filename
                _ = shutil.copy(src, dest)
            except Exception as e:
                logger.exception("could not copy firefox profile", e)
        procs._borg_backup()
        self.update(text=self.poll(state=CheckState.IN_PROGRESS))

    @expose_command()
    def reset(self) -> None:
        if self.cache_file.exists():
            self.cache_file.unlink()

    def on_state_changed(self, current: Optional[CheckState], next: CheckState) -> None:
        if current == next or not current:
            return
        urgency = Urgency.CRITICAL if next is CheckState.ERROR else Urgency.NORMAL
        self.notify("borg", self.borg_state_msgs[next], urgency)


borg_widget = BorgBackupWidget(
    fontsize=12,
    ok_text="",
    update_interval=10,
    background=background,
    firefox_profile="r3qxgekl.default-nightly",
)


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


class KeyboardLayout(widget.KeyboardLayout):
    def cycle_layouts(self, reverse: bool = False) -> None:
        """set the next layout in the list of configured keyboard layouts as
        new current layout in use

        If the current keyboard layout is not in the list, it will set as new
        layout the first one in the list.
        """

        current_keyboard = self.backend.get_keyboard()
        inc = -1 if reverse else 1
        if current_keyboard in self.configured_keyboards:
            # iterate the list circularly
            next_keyboard = self.configured_keyboards[
                (self.configured_keyboards.index(current_keyboard) + inc)
                % len(self.configured_keyboards)
            ]
        else:
            next_keyboard = self.configured_keyboards[0]

        self.backend.set_keyboard(next_keyboard, self.option)

        self.tick()

    @expose_command()
    def next_layout(self) -> None:
        self.cycle_layouts()

    @expose_command()
    def prev_layout(self) -> None:
        self.cycle_layouts(reverse=True)


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
        "fontsize": 20,
        "markup": True,
    }
    if sync_get_xrandr_output().num_screens > 1:
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
            always_visible_groups=("1", "f"),
            name="groupbox-0",
            padding_x=10,
            **settings,
            **group_settings,
        )
    widgets.append(group_box)

    if sync_get_xrandr_output().num_screens > 1:
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
        configured_keyboards=["de deadacute", "de", "us"],
        display_map={
            "de deadacute": "de",
            "de": "de (no coding)",
            "us": "en",
        },
        foreground=color.MID_GRAY,
    )
    kbd = KeyboardLayout(**kdb_settings)

    chord_settings = settings | {}
    chord = widget.Chord(**chord_settings)
    if is_primary:
        widgets.append(borg_widget)
        # widgets.append(checkclock_widget)
        widgets.append(space())
        widgets.append(kbd)
        widgets.append(chord)

        # widgets.append(widget.StatusNotifier(icon_size=18, padding=8, **settings))
        widgets.append(widget.Systray(icon_size=18, padding=12, **settings))
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

    brightness_settings = {
        "name": "brightness",
        "mode": "popup",
        "border_width": int(BAR_HEIGHT * 0.3),
        "decorations": [
            BorderDecoration(
                color="#ff0000",
                padding_x=10,
            )
        ],
    }
    brightness = widget.BrightnessControl(**brightness_settings, **settings)

    widgets.append(brightness)

    vpn_status = VpnStatus(
        vpn=MAIN_VPN,
        update_interval=300,
        background=background,
    )
    widgets.append(vpn_status)

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
        update_interval=5,
        use_diff=True,
        up_first=False,
        mouse_callbacks={"Button1": proc_fn("bash", "-c", "nmcli n off && nmcli n on")},
        **settings,
    )
    widgets.append(net_graph)

    num_procs = widget.GenPollText(
        func=get_num_procs,
        update_interval=2,
        background=background,
        # mouse_callbacks={"Button3": menu.show}
    )
    widgets.append(num_procs)

    clock = widget.Clock(format=" %Y-%m-%d %H:%M", **settings)
    widgets.append(clock)
    layout = widget.CurrentLayout(scale=0.7, **settings)
    widgets.append(layout)

    return bar.Bar(widgets=widgets, size=BAR_HEIGHT, background=BAR_BG)
