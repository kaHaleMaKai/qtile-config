_rules = {
    "wmclass": [
        'confirm',
        'dialog',
        'download',
        'error',
        'file_progress',
        'notification',
        'splash',
        'toolbar',
        'ssh-askpass',  # ssh-askpass
        "Arandr",
        "Gpick",
        "Kruler",
        "MessageWin",
        "Sxiv",
        "Wpa_gui",
        "pinentry",
        "veromix",
        "MPlayer",
        "pinentry",
        "Gimp",
        "Shutter",
        "xtightvncviewer",
    ],
    'wname':   [
        'pinentry',
        'Event Tester',
    ],
    "role":  [
        "AlarmWindow",
        "pop-up",
    ]
}


def get_floating_rules():
    return [{k: v} for k, vs in _rules.items() for v in vs]
