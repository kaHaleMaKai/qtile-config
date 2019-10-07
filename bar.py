from libqtile import bar, widget
from widgets.capslocker import CapsLockIndicator
import util

settings = dict(
    background=None,
    borderwidth=0,
    foreground="d0d0d0"
)

# battery = widget.BatteryIcon()
# cpu_graph = widget.CPUGraph()


def get_bar(screen_idx):
    is_primary = screen_idx == 0

    prompt = widget.Prompt(
        name=f"prompt-{screen_idx}",
        prompt="» ",
        fontsize=11,
        padding=10,
        **settings
    )
    task_list = widget.TaskList(highlight_method="block", border="404000", **settings)
    clock = widget.Clock(format='%Y-%m-%d %H:%M', **settings)
    caps_lock = CapsLockIndicator(send_notifications=is_primary, **settings)
    layout = widget.CurrentLayoutIcon(scale=0.7, **settings)
    # net = widget.Net(interface="enp0s25")
    notify = widget.Notify(**settings)
    volume = widget.Volume(
        cardid=0,
        device=None,
        theme_path="/usr/share/icons/HighContrast/256x256",
        fontsize=12,
        volume_app="pavucontrol",
        **settings
    )

    group_settings = {
        "highlight_method": "block",
        "active": "b0b000",
        "this_screen_border": "102a3b",
        "this_current_screen_border": "184062",
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
        widgets.append(widget.Systray(**settings))

    widgets.extend((
        # cpu_graph,
        # net,
        notify,
        volume,
        caps_lock,
        # battery,
        clock,
        layout,
    ))

    return bar.Bar(widgets, 24)
