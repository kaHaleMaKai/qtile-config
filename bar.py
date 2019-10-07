from libqtile import bar, widget
from widgets.capslocker import CapsLockIndicator
import util

settings = dict(
    background=None,
    borderwidth=0,
)

# battery = widget.BatteryIcon()
# cpu_graph = widget.CPUGraph()


def get_bar(screen_idx):
    is_primary = screen_idx == 0

    prompt = widget.Prompt(name=f"prompt-{screen_idx}", prompt="» ", font="Hack", padding=10)
    task_list = widget.TaskList()
    clock = widget.Clock(format='%Y-%m-%d %H:%M')
    caps_lock = CapsLockIndicator(send_notifications=is_primary)
    layout = widget.CurrentLayoutIcon(scale=0.7)
    # net = widget.Net(interface="enp0s25")
    notify = widget.Notify()
    volume = widget.Volume(
        cardid=0,
        device=None,
        theme_path="/usr/share/icons/HighContrast/256x256",
        fontsize=12,
        volume_app="pavucontrol"
    )

    if len(util.res) == 2:
        if is_primary:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "123456789"])
        else:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "abcdef"])
    else:
        group_box = widget.GroupBox()

    widgets = [group_box, prompt, task_list]
    if is_primary:
        widgets.append(widget.Systray())

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
