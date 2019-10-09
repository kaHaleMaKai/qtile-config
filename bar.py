from libqtile import bar, widget
from widgets.capslocker import CapsLockIndicator
import util
import color

settings = dict(
    background=None,
    borderwidth=0,
    foreground=color.BRIGHT_GRAY,
)

# battery = widget.BatteryIcon()
# cpu_graph = widget.CPUGraph()


def space():
    return widget.Spacer(length=10)


def get_bar(screen_idx):
    is_primary = screen_idx == 0

    prompt = widget.Prompt(
        name=f"prompt-{screen_idx}",
        prompt="» ",
        fontsize=11,
        padding=10,
        **settings
    )
    task_list = widget.TaskList(highlight_method="block", border=color.DARK_ORANGE, **settings)
    clock = widget.Clock(format='%Y-%m-%d %H:%M', **settings)
    caps_lock = CapsLockIndicator(send_notifications=is_primary, **settings)
    layout = widget.CurrentLayoutIcon(scale=0.7, **settings)
    # net = widget.Net(interface="enp0s25")
    notify = widget.Notify(**settings)
    volume = widget.Volume(
        cardid=0,
        device=None,
        theme_path="/usr/share/icons/HighContrast/256x256",
        volume_app="pavucontrol",
        **settings
    )

    group_settings = {
        "highlight_method": "block",
        "active": color.BRIGHT_ORANGE,
        "this_screen_border": color.DARK_BLUE_GRAY,
        "this_current_screen_border": color.MID_BLUE_GRAY,
        "hide_unused": False
    }
    if len(util.res) == 2:
        if is_primary:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "123456789"], **settings, **group_settings)
        else:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "abcdef"], **settings, **group_settings)
    else:
        group_box = widget.GroupBox(**settings, **group_settings)

    widgets = [group_box, prompt, task_list]
    if is_primary:
        widgets.append(widget.Systray(icon_size=18, **settings))

    widgets.extend((
        space(),
        # cpu_graph,
        # net,
        notify,
        volume,
        caps_lock,
        # battery,
        clock,
        layout,
    ))

    return bar.Bar(
        widgets=widgets,
        size=22,
        opacity=0.9
    )
