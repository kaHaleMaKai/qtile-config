from __future__ import annotations

from libqtile import hook
from libqtile.log_utils import logger
from libqtile.backend.x11.window import Window

from qutely import procs, util
from qutely.debug import in_debug_mode
from qutely.procs import Proc
from qutely.floating_rules import floating_dimensions


# APPS_THAT_DISABLE_NOTIFICATIONS = {
#     "name": re.compile()
# }


def init_hooks() -> None:
    @hook.subscribe.startup_complete
    async def autostart_once() -> None:
        logger.info("running startup_once")
        ps = [
            procs.xss_lock,
        ]
        await Proc.await_many(*ps)


    @hook.subscribe.startup
    async def autostart() -> None:
        logger.info("running startup")
        ps = [procs.resume_dunst]
        if not in_debug_mode:
            ps.extend([
                procs.start_custom_session,
                util.render_dunstrc(),
                util.render_kitty_config(),
                util.spawn_terminal(),
                # util.render_terminalrc(),
                # util.render_picom_config(),
            ])
        # if is_light_theme:
        #     ps.append(procs.stop_picom)
        # else:
        #     ps.append(procs.start_picom)
        await Proc.await_many(*ps)


    # @hook.subscribe.screen_change
    # async def screen_change(event):
    #     from libqtile import qtile

    #     await util.reload_qtile(qtile)


    def handle_floating_windows(window: Window) -> None:
        if not window or not window.name:
            return

        role = window.window.get_wm_window_role()
        name = window.name
        class_ = window.get_wm_class()[1].lower()
        if name.startswith("chrome-extension://") and name.endswith(
            " is sharing a window."
        ):
            window.enable_floating()
        elif role == "InvitationsDialog":
            window.floating = False

        if window.floating and (dim := floating_dimensions.get(class_)):
            window.width, window.height = dim
            window.center()


    @hook.subscribe.client_new
    def handle_floating_for_new_clients(window: Window) -> None:
        handle_floating_windows(window)

        from libqtile import qtile

        for win in qtile.current_group.windows:
            if win.floating:
                win.bring_to_front()


    @hook.subscribe.client_killed
    def cycle_to_next_client_or_empty_group(window: Window) -> None:
        current_group = window.qtile.current_group
        if len(current_group.windows) > 1 or window not in current_group.windows:
            return
        if len(current_group.windows) <= 1:
            current_group.set_label(None)
        if current_group.name in ("1", "f"):
            return
        qtile = window.qtile
        g, s = util.get_group_and_screen_idx(qtile, -1, skip_invisible=True)
        if g.name > current_group.name:
            g, s = qtile.groups_map["1"], 0
        util.group_history.backward()
        util.group_history.add(g)
        qtile.to_screen(s)
        g.toscreen()


    @hook.subscribe.setgroup
    def move_sticky_windows():
        from libqtile import qtile

        for w, _, _ in util.sticky_windows:
            w.togroup(qtile.current_group.name)
        window: Window | None = qtile.current_window
        if window:
            window.focus()


    @hook.subscribe.client_name_updated
    @hook.subscribe.client_managed
    @hook.subscribe.client_focus
    def set_group_icon(window: Window | None) -> None:
        if window is None:
            from libqtile import qtile

            qtile.current_group.set_label(None)
        else:
            util.set_group_label_from_window_class(window)


    # @hook.subscribe.user("custom_reload")
    # def setup_all_group_icons() -> None:
    #     hook.subscribe.startup_complete(hook.subscribe.restart(util.setup_all_group_icons))
