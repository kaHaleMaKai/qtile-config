from __future__ import annotations

import asyncio
import shlex
from qutely.procs import Proc
from libqtile.config import EzKey
from libqtile.command.client import InteractiveCommandClient
from libqtile.lazy import lazy, LazyCall
from libqtile.utils import logger
from qutely.debug import in_debug_mode
from qutely.util import (
    prev_group,
    next_group,
    spawncmd,
    go_to_screen,
    move_to_screen,
    restart_qtile,
    reload_qtile,
    move_window_to_offset_group,
    start_distraction_free_mode,
    stop_distraction_free_mode,
    history_back,
    history_forward,
    lock_screen,
    suspend,
    toggle_sticky_window,
    kbd_backlight,
    provide_terminal,
)
from qutely.helpers import lazy_coro

modifier_keys = {
    "M": "M",
    "A": "A",
    "S": "S",
    "C": "C",
    "mod4": "M",
    "mod1": "A",
    "shift": "S",
    "control": "C",
    "super": "M",
    "alt": "A",
    "ctrl": "C",
}

inverse_modifier_keys = {
    "M": "mod4",
    "A": "mod1",
    "S": "shift",
    "C": "control",
}

default_mod_key = "M"
if in_debug_mode:
    mod_abbrev = "A"
else:
    mod_abbrev = default_mod_key
mod_key = inverse_modifier_keys[mod_abbrev]


class KeyList(list):
    def __init__(self, key_dict):
        super().__init__()
        self.add_keys(key_dict)

    def add_keys(self, key_dict, **kwargs):
        d = key_dict.copy()
        d.update(kwargs)
        for k, vs in d.items():
            try:
                self.add_key(k, vs)
            except Exception as e:
                raise ValueError(f"cannot parse key {k=}, {vs=}, {vs.name}") from e

    def add_key(self, k, vs):
        entry = EzKey(self.parse_key(k), *self.as_command(vs))
        self.append(entry)

    def __setitem__(self, k, vs):
        self.add_key(k, vs)

    @staticmethod
    def parse_key(key):
        if key.startswith("M-"):
            return mod_abbrev + key[1:]
        else:
            return key

    @staticmethod
    def as_command(args):
        if isinstance(args, (list, tuple)):
            cmds = args
        elif isinstance(args, dict):
            cmds = []
            for ks, v in args.items():
                if isinstance(ks, tuple):
                    subks = ks
                elif isinstance(ks, str):
                    subks = [ks]
                else:
                    raise TypeError(
                        "wrong type for key. expected: (str, list, tuple). got: %s" % type(ks)
                    )
                for k in subks:
                    cmd = v()
                    if k:
                        cmd.when(layout=k)
                    cmds.append(cmd)
        else:
            cmds = [args]

        li = []
        for cmd in cmds:
            logger.debug(cmd)
            if isinstance(cmd, str):
                action = lazy.spawn(cmd)
            elif isinstance(cmd, LazyCall):
                action = cmd
            elif isinstance(cmd, InteractiveCommandClient):
                action = cmd()
            elif asyncio.iscoroutinefunction(cmd):
                action = lazy_coro(cmd)
            else:
                action = cmd()
            li.append(action)
        return li


@lazy.function
def create_popup(qtile):
    from libqtile.popup import Popup

    popup = Popup(qtile)
    popup.place()
    popup.unhide()


keys = KeyList(
    {
        "M-S-r": lazy_coro(reload_qtile, light_theme=False),
        "M-<Escape>": lazy_coro(reload_qtile, light_theme=True),
        "M-C-r": lazy.function(restart_qtile),
        "M-C-q": lazy.shutdown,
        "M-<Left>": prev_group,
        "M-<Right>": next_group,
        "M-y": move_window_to_offset_group(-1),
        "M-x": move_window_to_offset_group(+1),
        "M-C-<Left>": go_to_screen(0),
        "M-C-<Right>": go_to_screen(1),
        "M-S-y": move_to_screen(0),
        "M-S-x": move_to_screen(1),
        "M-h": lazy.layout.left,
        "M-l": lazy.layout.right,
        "M-j": lazy.layout.down,
        "M-k": lazy.layout.up,
        "M-u": lazy.next_urgent,
        "M-S-h": lazy.layout.shuffle_left,
        "M-S-l": lazy.layout.shuffle_right,
        "M-S-j": lazy.layout.shuffle_down,
        "M-S-k": lazy.layout.shuffle_up,
        "M-C-h": {
            ("bsp", "column"): lazy.layout.grow_left,
            "treetab": lazy.layout.decrease_ratio,
            "monadtall": lazy.layout.shrink_main,
        },
        "M-C-l": {
            ("bsp", "column"): lazy.layout.grow_right,
            "treetab": lazy.layout.increase_ratio,
            "monadtall": lazy.layout.grow_main,
        },
        "M-C-j": lazy.layout.grow_down,
        "M-C-k": lazy.layout.grow_up,
        "M-A-h": lazy.layout.flip_left,
        "M-A-j": lazy.layout.flip_up,
        "M-A-k": lazy.layout.flip_down,
        "M-A-l": lazy.layout.flip_right,
        "M-z": lazy.window.toggle_fullscreen,
        "M-S-z": lazy.hide_show_bar,
        "M-n": lazy.window.toggle_minimize,
        "M-t": lazy.window.toggle_floating,
        "M-S-t": lazy.function(toggle_sticky_window),
        "M-<space>": lazy.next_layout,
        "M-S-<space>": lazy.prev_layout,
        "M-C-<space>": lazy.layout.rotate,
        "M-S-<Return>": lazy.layout.toggle_split,
        "M-S-<period>": lazy.window.kill,
        "M-q": "fakecam toggle",
        "M-S-q": "fakecam choose-background",
        "M-r": "rofi -i -show run",
        "M-S-<F12>": start_distraction_free_mode,
        "M-<F12>": stop_distraction_free_mode,
        "M-p": history_back,
        "M-S-p": history_forward,
        "M-<Return>": provide_terminal,  # "st"
        "M-<minus>": "xdotool key Menu",
        "M-S-<Left>": "shiftred r-",
        "M-S-<Right>": "shiftred r+",
        "M-S-<Down>": lazy.widget["brightness"].brightness_down(),
        "M-S-<Up>": lazy.widget["brightness"].brightness_up(),
        "M-S-0": "shiftred 5100:.8",
        "M-0": "shiftred 5800:1",
        "M-C-0": "shiftred 6500:1",
        "M-<Prior>": "transset --actual --dec 0.025",
        "M-<Next>": "transset --actual --inc 0.025",
        "M-<plus>": "rofi -i -show window",
        "M-S-<plus>": r"rofi-run\ in\ terminal-menu",
        "M-<numbersign>": "rofi -i -show run",
        "M-S-<numbersign>": "rofi-pkill-menu",
        "M-A-f": "ff-history",
        "M-<F8>": "totp",
        "M-<F9>": "rofi-menu",
        "M-<F10>": "rofi-pass",
        "M-S-u": "toggle-unclutter",
        "M-s": "flameshot gui",
        "M-S-s": "flameshot full --clipboard",
        "M-C-s": "kazam",
        "M-C-p": lock_screen,
        "M-C-S-p": suspend,
        "M-C-A-p": "reconfigure-and-hibernate",
        "M-<F1>": "configure-screens laptop",
        "M-<F2>": "configure-screens home",
        "M-<F3>": "configure-screens work",
        "<XF86AudioMute>": "configure-volume --toggle",
        "<XF86AudioLowerVolume>": "configure-volume --down",
        "<XF86AudioRaiseVolume>": "configure-volume --up",
        "<XF86AudioMicMute>": "configure-volume --toggle-mic",
        "S-<XF86AudioMute>": "configure-volume --toggle-mic",
        "S-<XF86AudioLowerVolume>": "configure-volume --down-mic",
        "S-<XF86AudioRaiseVolume>": "configure-volume --up-mic",
        "C-<XF86AudioMute>": "configure-volume --mute-all",
        "M-i": lazy.widget["checkclockwidget"].toggle_paused(),
        "M-S-i": lazy.widget["checkclockwidget"].show_schedule(),
        "M-<F6>": create_popup,
        "M-v": lazy.group["signal_scratchpad"].dropdown_toggle("signal"),
        "M-C-v": lazy.group["zeal_scratchpad"].dropdown_toggle("zeal"),
        "M-S-g": "xdotool key Return",
        "M-o": "dunstctl close",
        "M-S-o": "dunstctl close-all",
        "M-C-o": "dunstctl history-pop",
        "M-C-S-o": "dunstctl context",
        "A-<space>": lazy_coro(kbd_backlight.increase_brightness),
    }
)
