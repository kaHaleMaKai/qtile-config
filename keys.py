from libqtile.config import EzKey
from libqtile.command import lazy
from libqtile.lazy import LazyCall
from util import (prev_group, next_group, spawncmd, go_to_screen, move_to_screen, in_debug_mode,
                  restart_qtile, move_window_to_offset_group, start_distraction_free_mode,
                  stop_distraction_free_mode, update_path, is_laptop_connected, history_back, history_forward)

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
            self.add_key(k, vs)

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
                        "wrong type for key. expected: (str, list, tuple). got: %s" %
                        type(ks))
                for k in subks:
                    cmd = v()
                    if k:
                        cmd.when(layout=k)
                    cmds.append(cmd)
        else:
            cmds = [args]

        li = []
        for cmd in cmds:
            if isinstance(cmd, str):
                action = lazy.spawn(cmd)
            elif not isinstance(cmd, LazyCall):
                action = cmd()
            else:
                action = cmd
            li.append(action)
        return li


keys = KeyList({
    "M-<Left>":        prev_group,
    "M-<Right>":       next_group,
    "M-y":             move_window_to_offset_group(-1),
    "M-x":             move_window_to_offset_group(+1),
    "M-h":             lazy.layout.left,
    "M-l":             lazy.layout.right,
    "M-j":             lazy.layout.down,
    "M-k":             lazy.layout.up,
    "M-u":             lazy.next_urgent,
    "M-S-h":           lazy.layout.shuffle_left,
    "M-S-l":           lazy.layout.shuffle_right,
    "M-S-j":           lazy.layout.shuffle_down,
    "M-S-k":           lazy.layout.shuffle_up,
    "M-C-h":           {
        ( "bsp", "column"): lazy.layout.grow_left,
        "treetab": lazy.layout.decrease_ratio
    },
    "M-C-l":           {
        ("bsp", "column"): lazy.layout.grow_right,
        "treetab": lazy.layout.increase_ratio
    },
    "M-C-j":           lazy.layout.grow_down,
    "M-C-k":           lazy.layout.grow_up,
    "M-A-h":           lazy.layout.flip_left,
    "M-A-j":           lazy.layout.flip_up,
    "M-A-k":           lazy.layout.flip_down,
    "M-A-l":           lazy.layout.flip_right,
    "M-z":             lazy.window.toggle_fullscreen,
    "M-S-z":           lazy.hide_show_bar,
    "M-n":             lazy.window.toggle_minimize,
    "M-t":             lazy.window.toggle_floating,
    "M-<space>":       lazy.next_layout,
    "M-S-<space>":     lazy.prev_layout,
    "M-C-<space>":     lazy.layout.rotate,
    "M-S-<Return>":    lazy.layout.toggle_split,
    "M-S-<period>":    lazy.window.kill,
    "M-S-r":           lazy.function(restart_qtile),
    "M-S-q":           lazy.shutdown,
    "M-r":             spawncmd,
    "M-S-<F12>":       start_distraction_free_mode,
    "M-<F12>":         stop_distraction_free_mode,
    "M-p":             history_back,
    "M-S-p":           history_forward,
    "M-<Return>":      "xfce4-terminal -e zsh",
    "M-S-<Left>":      "shiftred r-",
    "M-S-<Right>":     "shiftred r+",
    "M-S-<Down>":      "shiftred b-",
    "M-S-<Up>":        "shiftred b+",
    "M-S-0":           "shiftred 5100:.8",
    "M-0":             "shiftred 5800:1",
    "M-C-0":           "shiftred 6500:1",
    "M-<Prior>":       "transset --actual --dec 0.025",
    "M-<Next>":        "transset --actual --inc 0.025",
    "M-<plus>":        "rofi -i -show window",
    "M-S-<plus>":       r"rofi-run\ in\ terminal-menu",
    "M-<numbersign>":  "rofi -i -show run",
    "M-S-<numbersign>": "rofi-pkill-menu",
    "M-A-f":           "ff-history",
    "M-<F9>":          "rofi-menu",
    "M-<F10>":         "rofi-pass",
    "M-<udiaeresis>":  "rofimoji",
    "M-S-u":           "toggle-unclutter",
    "M-s":             "flameshot gui",
    "M-S-s":           "flameshot launcher",
    "M-C-p":           "cinnamon-screensaver-command --lock",
    "M-<F1>":          "configure-screens small",
    "M-<F2>":          "configure-screens dual-external",
    "M-<F3>":          "configure-screens large",
    "M-<F4>":          "configure-screens 24inch+dual",
    "M-<F5>":          "configure-screens 24inch",
    "<XF86AudioMute>":          "configure-volume --toggle",
    "<XF86AudioLowerVolume>":   "configure-volume --down",
    "<XF86AudioRaiseVolume>":   "configure-volume --up",
    "<XF86AudioMicMute>":       "configure-volume --toggle-mic",
    "S-<XF86AudioMute>":        "configure-volume --toggle-mic",
    "S-<XF86AudioLowerVolume>": "configure-volume --down-mic",
    "S-<XF86AudioRaiseVolume>": "configure-volume --up-mic",
    "C-<XF86AudioMute>":        "configure-volume --mute-all",
    "M-w": update_path,
})

if is_laptop_connected():
    first_key = "Up"
    second_key = "Down"
else:
    first_key = "Left"
    second_key = "Right"

keys[f"M-C-<{first_key}>"] = go_to_screen(0)
keys[f"M-C-<{second_key}>"] = go_to_screen(1)
keys[f"M-A-<{first_key}>"] = move_to_screen(0)
keys[f"M-A-<{second_key}>"] = move_to_screen(1)
