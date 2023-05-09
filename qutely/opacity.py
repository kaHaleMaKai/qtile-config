from libqtile import hook
from libqtile.backend.x11.window import Window
from libqtile.log_utils import logger
from qutely.util import is_light_theme, TERM_CLASS, TERM_SUPPLY_CLASS

full_opacities = {
    "class": {
        "msgcompose",
        "confirm",
        "dialog",
        "download",
        "error",
        "file_progress",
        "notification",
        "splash",
        "toolbar",
        "ssh-askpass",
        "arandr",
        "gpick",
        "kruler",
        "messagewin",
        "sxiv",
        "wpa_gui",
        "pinentry",
        "veromix",
        "mplayer",
        "pinentry",
        "gimp",
        "shutter",
        "xtightvncviewer",
        "kazam",
        "vivaldi-stable",
        "scribus",
    },
    "role": {
        "gtkfilechooserdialog",
        "alarmwindow",
        "pop-up",
    },
    "name": {
        "pinentry",
        "event tester",
        "tbsync account manager",
        "calendar - mozilla thunderbird",
    },
    "type": set(),
}

partial_opacities = {
    "class": {
        "xfce4-terminal": 0.92,
        TERM_CLASS: 0.92,
        TERM_SUPPLY_CLASS: 0.92,
        "awiwi": 0.92,
        "neovide": 0.92,
        "thunderbird": 0.97,
        "gajim": 0.97,
        "jetbrains-idea-ce": 0.97,
        "jetbrains-pycharm-ce": 0.97,
        "dbeaver": 0.97,
        "spotify": 0.97,
        "code": 0.97,
        "microsoft teams - preview": 0.97,
    },
    "role": {},
    "name": {},
    "type": {},
}


def set_opacities(window: Window, dim: bool = True, overwrite: bool = False) -> None:
    if hasattr(window, "_full_opacity") and not overwrite:
        return
    window._full_opacity = window.opacity
    if dim:
        window._dimmed_opacity = window._full_opacity * 0.93
        window._dimmable = True
    else:
        window._dimmed_opacity = 1.0
        window._dimmable = False


previous_window = None


def get_specs(window: Window):
    classes = window.window.get_wm_class()
    name = window.window.get_name()
    role = window.window.get_wm_window_role()
    type = window.window.get_wm_type()
    classes = (None, None) if classes is None else [c.lower() for c in classes]
    name = None if name is None else name.lower()
    role = None if role is None else role.lower()
    type = None if type is None else type.lower()

    return *classes, name, role, type


def get_opacity_spec(window: Window, cls=None, name=None, role=None, type=None):
    if cls or name or role or type:
        cls0, cls1 = ("", cls) if cls else (None, None)
    else:
        cls0, cls1, name, role, type = get_specs(window)

    try:
        has_full_opacity = (
            name in full_opacities["name"]
            or role in full_opacities["role"]
            or type in full_opacities["type"]
            or cls0 in full_opacities["class"]
            or cls1 in full_opacities["class"]
        )
        if has_full_opacity:
            return {"full": True, "value": 1.0}
    except IndexError as e:
        logger.warn(e)
        return {"full": True, "value": 1.0}

    opacity = partial_opacities["name"].get(name)
    if opacity is None:
        c = partial_opacities["class"]
        opacity = c.get(cls0, c.get(cls1))
        if opacity is None:
            opacity = partial_opacities["role"].get(role)
            if opacity is None:
                opacity = partial_opacities["type"].get(type)
    return {"full": False, "value": opacity if opacity is not None else 1.0}


def has_full_opacity(window: Window):
    return get_opacity_spec(window)["full"]


@hook.subscribe.client_new
def add_opacity(window: Window):
    opacity_spec = get_opacity_spec(window)
    if opacity_spec["full"]:
        set_opacities(window, dim=False)
        return

    opacity = opacity_spec["value"]
    if opacity:
        window.opacity = opacity
    set_opacities(window)


@hook.subscribe.client_focus
def reset_opacity(window: Window):
    global previous_window

    if window is previous_window:
        return

    try:
        window.opacity = window._full_opacity
    except AttributeError:
        set_opacities(window)

    if previous_window:
        try:
            previous_window.opacity = previous_window._dimmed_opacity
        except AttributeError:
            set_opacities(previous_window)
            previous_window.opacity = previous_window._dimmed_opacity
    previous_window = window


@hook.subscribe.client_name_updated
def make_calendar_opacque(window: Window):
    if window.window.get_wm_class()[1] != "thunderbird":
        return
    op = get_opacity_spec(window)
    window.opacity = op["value"]
    set_opacities(window, dim=not op["full"], overwrite=True)
