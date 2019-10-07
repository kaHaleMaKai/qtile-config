import os
from libqtile.config import EzKey
from libqtile.command import lazy
import procs
from util import prev_group, next_group, spawncmd, res

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
if "QTILE_MOD_KEY" in os.environ:
    mod_abbrev = modifier_keys.get(os.environ["QTILE_MOD_KEY"], default_mod_key)
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
        else:
            cmds = [args]

        li = []
        for cmd in cmds:
            if isinstance(cmd, procs.Proc):
                action = lazy.spawn(cmd.get_args())
            elif isinstance(cmd, str):
                action = lazy.spawn(cmd)
            else:
                action = cmd
            li.append(action)
        return li


keys = KeyList({
    "M-<Left>":        prev_group(),
    "M-<Right>":       next_group(),
    "M-C-<Left>":      lazy.prev_screen(),
    "M-C-<Right>":     lazy.next_screen(),
    "M-p":             lazy.screen.toggle_group(),
    "M-S-p":           lazy.group.focus_back(),
    "M-h":             lazy.layout.left(),
    "M-l":             lazy.layout.right(),
    "M-j":             lazy.layout.down(),
    "M-k":             lazy.layout.up(),
    "M-S-j":           lazy.layout.shuffle_down(),
    "M-S-k":           lazy.layout.shuffle_up(),
    "M-S-l":           lazy.layout.increase_ratio(),
    "M-S-h":           lazy.layout.decrease_ratio(),
    "M-z":             lazy.window.toggle_fullscreen(),
    "M-n":             lazy.window.toggle_minimize(),
    "M-t":             lazy.window.toggle_floating(),
    "M-<space>":       lazy.next_layout(),
    "M-S-<space>":     lazy.prev_layout(),
    "M-C-<space>":     lazy.layout.rotate(),
    "M-S-<Return>":    lazy.layout.toggle_split(),
    "M-S-<period>":    lazy.window.kill(),
    "M-S-r":           lazy.restart(),
    "M-S-q":           lazy.shutdown(),
    "M-r":             spawncmd,
    "M-<Return>":      procs.terminal,
    "M-S-<Left>":      procs.shiftred["r-"],
    "M-S-<Right>":     procs.shiftred["r+"],
    "M-S-<Down>":      procs.shiftred["b-"],
    "M-S-<Up>":        procs.shiftred["b+"],
    "M-S-0":           procs.shiftred["4200:.8"],
    "M-0":             procs.shiftred["5100:1"],
    "M-C-0":           procs.shiftred["6500:1"],
    "M-<Prior>":       procs.opacity["--dec", "0.025"],
    "M-<Next>":        procs.opacity["--inc", "0.025"],
    "M-<plus>":        procs.rofi["window"],
    "M-<numbersign>":  procs.rofi["combi"],
    "M-<F10>":         procs.rofi_pass["rofi-pass"],
    "M-<udiaeresis>":  procs.rofimoji,
    "M-S-u":           procs.toggle_unclutter,
    "M-C-l":           procs.screensaver_cmd,
    "<XF86AudioMute>": procs.volume["--toggle"],
    "<XF86AudioLowerVolume>": procs.volume["--down"],
    "<XF86AudioRaiseVolume>": procs.volume["--up"],
})
