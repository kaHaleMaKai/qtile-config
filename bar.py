from libqtile import bar, widget
from widgets.capslocker import CapsLockIndicator

settings = dict(
    background=None,
    borderwidth=0,
)

# battery = widget.BatteryIcon()
# cpu_graph = widget.CPUGraph()


def get_bar(screen_idx, res):
    prompt = widget.Prompt(prompt="» ", font="Hack", padding=10)
    task_list = widget.TaskList()
    clock = widget.Clock(format='%Y-%m-%d %H:%M')
    caps_lock = CapsLockIndicator()
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

    primary = screen_idx == 0
    if len(res) == 2:
        if primary:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "123456789"])
        else:
            group_box = widget.GroupBox(visible_groups=[ch for ch in "abcdef"])
    else:
        group_box = widget.GroupBox()

    args = [group_box, prompt, task_list]
    if primary:
        args.append(widget.Systray())

    args.extend((
        # cpu_graph,
        # net,
        notify,
        volume,
        caps_lock,
        # battery,
        clock,
        layout,
    ))

    return bar.Bar(args, 24)
