import random
import datetime
import subprocess as sub
from enum import IntEnum
from typing import Any, Callable, Optional, Union, cast

from libqtile.widget.base import ThreadPoolText, ORIENTATION_HORIZONTAL  # type: ignore[import]

from qutely.widgets.lib.notifier import Notifier


class CheckState(IntEnum):
    OK = 1
    IN_PROGRESS = 2
    WARN = 3
    ERROR = 4

    def is_action_required(self) -> bool:
        return self >= CheckState.WARN


MaybeString = Optional[str]
StateChangeFn = Callable[[Optional[CheckState], CheckState], None]
Proc = sub.Popen[str]
Cmd = Union[str, list[str]]
MaybeInt = Optional[int]


class CheckAndWarnWidget(ThreadPoolText):  # type: ignore[misc]

    orientations = ORIENTATION_HORIZONTAL

    defaults = [
        ("error_text", "️✘", "the error text to display"),
        ("error_color", "#f02020", "color of the error text"),
        ("in_progress_text", "🗘", "the 'in-progress' text to display"),
        ("in_progress_color", "#6060f0", "color of the 'in-progress' text"),
        ("warn_text", "⚠", "the warning text to display in the widget"),
        ("warn_color", "#00ff00", "color of the warning text"),
        ("ok_text", "✔", "the text to display when everything is ok"),
        ("ok_color", "#ff0000", "color of the ok-text"),
        ("update_interval", 60, "number of seconds between checks"),
        ("fontsize", 18, "size of the font"),
    ]

    fontsize: int
    error_color: str
    error_text: str
    warn_color: str
    warn_text: str
    in_progress_color: str
    in_progress_text: str
    ok_color: str
    ok_text: str

    def __init__(self, **config: Any) -> None:

        super().__init__(" ", **config)
        self.add_defaults(CheckAndWarnWidget.defaults)
        self.has_error = False
        self.custom_error_msg: MaybeString = None
        self.error_color = self.normalize_color(self.error_color)
        self.warn_color = self.normalize_color(self.warn_color)
        self.ok_color = self.normalize_color(self.ok_color)
        self.in_progress_color = self.normalize_color(self.in_progress_color)
        self.current_state = CheckState.WARN

    def span(self, text: str, color: str) -> str:
        return f"""<span foreground="#{color}">{text}</span>"""

    @staticmethod
    def normalize_color(color: str) -> str:
        return color[1:] if color.startswith("#") else color

    def check(self) -> CheckState:
        return CheckState.WARN

    def cmd_reset(self) -> None:
        pass

    def run(self) -> None:
        pass

    def on_state_changed(self, current: Optional[CheckState], next: CheckState) -> None:
        pass

    def poll(self, state: Optional[CheckState] = None) -> str:
        state = state or self.check()
        if state != self.current_state:
            self.on_state_changed(self.current_state, state)
            self.current_state = state
        if state is CheckState.OK:
            return self.span(self.ok_text, self.ok_color)
        if state is CheckState.IN_PROGRESS:
            return self.span(self.in_progress_text, self.in_progress_color)
        elif state is CheckState.WARN:
            return self.span(self.warn_text, self.warn_color)
        else:
            return self.span(self.error_text, self.error_color)

    def cmd_run(self) -> None:
        if self.check().is_action_required():
            try:
                self.run()
            except Exception as e:
                print(e)

        self.update(text=self.poll())

    def button_press(self, x: int, y: int, button: int) -> None:
        if button == 1:
            self.cmd_run()
        elif button == 3:
            self.cmd_reset()


# class ProcCheckWidget(CheckAndWarnWidget):

#     defaults = [
#         ("shell", False, "whether to use a shell for the command"),
#         ("timeout", 10 * 60, "timeout in seconds"),
#         ("notifier", None, "Notifier to send out messages"),
#         ("name", None, "name of command. else command is used"),
#     ]

#     shell: bool
#     timeout: float
#     notifier: Optional[Notifier]
#     name: str

#     def __init__(self, cmd: Cmd, **config: Any) -> None:
#         super().__init__(**config)
#         super().add_defaults(ProcCheckWidget.defaults)
#         self.cmd: Cmd = cmd
#         self.proc: Optional[Proc] = None
#         self.start_ts: Optional[datetime.datetime] = None
#         self.name = self.name or self.cmd if isinstance(self.cmd, str) else " ".join(self.cmd)

#     def run(self) -> None:
#         self.proc = sub.Popen(args=self.cmd, stdout=sub.PIPE, stderr=sub.PIPE, shell=self.shell, text=True)
#         self.start_ts = datetime.datetime.now()
#         if self.notifier:
#             self.notifier.notify(summary=self.name, msg="starting process")

#     def check(self) -> CheckState:
#         if not self.proc:
#             return self.current_state
#         now = datetime.datetime.now()
#         rc = self.proc.poll()
#         if rc is None:
#             ts = cast(datetime.datetime, self.start_ts)
#             if now > ts + datetime.timedelta(seconds=self.timeout):
#                 self.proc.kill()
#                 stdout, stderr = self.proc.communicate()
#                 if self.notifier:
#                     self.notifier.notify(
#                         summary=self.name, msg=f"process has timed out after {self.timeout}s", level=Notifier.critical
#                     )
#             return CheckState.ERROR

#         stdout, stderr = self.proc.communicate()
#         self.start_ts = None
#         self.proc = None
#         if self.notifier:
#             if not rc:
#                 self.notifier.notify(summary=self.name, msg="process done ✔")
#             else:
#                 self.notifier.notify(
#                     summary=self.name,
#                     msg=f"process has failed with rc={rc} ✘\nstdout: {stdout}\nstderr: {stderr}",
#                     level=Notifier.critical,
#                 )
#         if not rc:
#             return CheckState.OK
#         else:
#             return CheckState.ERROR
