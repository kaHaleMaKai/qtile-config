from libqtile import hook


opacity_class_map = {
    "xfce4-terminal":        0.92,
    "evolution":             0.97,
    "gajim":                 0.97,
    "jetbrains-idea-ce":     0.97,
    "jetbrains-pycharm-ce":  0.97,
    "dbeaver":               0.97,
    "spotify":               0.97,
    "code":                  0.97,
}


@hook.subscribe.client_new
def add_opacity(window):
    cls = window.window.get_wm_class()
    for key, val in opacity_class_map.items():
        for entry in cls:
            if key == entry.lower():
                window.cmd_opacity(val)
                return
