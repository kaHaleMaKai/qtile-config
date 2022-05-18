import os
import shutil
import random
import datetime
from typing import Generator, List, Any, Union
from procs import dunstify
from pathlib import Path
from libqtile.widget.base import ThreadPoolText, ORIENTATION_HORIZONTAL
from libqtile.widget.textbox import TextBox
from .checkclock import (
    Checkclock,
    normalize_color,
    as_time,
    as_hours_and_minutes,
    get_previous_date,
)


class CheckclockWidget(ThreadPoolText):

    orientations = ORIENTATION_HORIZONTAL
    defaults = [
        ("db_path", "~/.config/qtile/checkclock.sqlite", "path to the sqlite db"),
        ("paused_text", "paused", "text to show when paused"),
        ("time_format", "%H:%M", "strftime-like format for checkclock time"),
        ("active_color", "#ffffff", "color of text in active state"),
        ("paused_color" "#808080", "color of paused text"),
        ("pause_button", 1, "mouse button to toggle pause"),
        ("done_color", "#00ff00", "color of text when work is done"),
        ("almost_done_color", "#ffff00", "color of text when work is almost done"),
        (
            "pause_function",
            None,
            "function to call when toggling the pause state. "
            "receives arguments (is_paused: bool, value: str)",
        ),
        ("avg_working_time", 8 * 60 * 60, "number of seconds to work per day"),
        (
            "min_working_time",
            10 * 60,
            "minimum number of seconds per day to consider a date as a working day",
        ),
        (
            "working_days",
            "Mon-Fri",
            "textual representation of working days, e.g. Mon-Fri, Tue,Wed-Sat",
        ),
        (
            "hooks",
            None,
            "dict of callbacks. keys: on_duration_update, on_tick, on_pause, on_resume, on_rollover. "
            + "all expect a Callable[[int], Any] as value. They receive the then current duration value.",
        ),
    ]

    def __init__(self, **config):
        super().__init__("", **config)
        self.add_defaults(CheckclockWidget.defaults)
        self.db_path = Path(os.path.expanduser(self.db_path))
        hooks = config.get("hooks") if config.get("hooks") else {}
        self.checkclock = Checkclock(
            tick_length=self.update_interval,
            path=self.db_path,
            avg_working_time=self.avg_working_time,
            min_duration=self.min_working_time,
            working_days=self.working_days,
            **hooks,
        )
        self.active_color = normalize_color(self.active_color)
        self.done_color = normalize_color(self.done_color)
        self.almost_done_color = normalize_color(self.almost_done_color)
        self.paused_color = normalize_color(self.paused_color)
        self.pause_button = int(self.pause_button)
        self.companions: List[TextBox] = []
        self.id = random.randint(1000000, 10 * 1000000 - 1)

    def new_companion(self) -> TextBox:
        box = TextBox(text=self.text)
        self.companions.append(box)
        return box

    def format_time(self, duration: int) -> str:
        seconds = duration % 60
        rem = duration // 60
        minutes = rem % 60
        hours = rem // 60
        return datetime.time(hours, minutes, seconds).strftime(self.time_format).strip()

    def cmd_toggle_paused(self) -> None:
        self.checkclock.toggle_paused()
        value = self.poll(tick=not self.checkclock.paused)
        if self.pause_function:
            self.pause_function(
                self.checkclock.paused, self.format_time(self.checkclock.duration)
            )
        self.update(text=value)

    def update(self, text: str) -> None:
        super().update(text=text)
        for companion in self.companions:
            companion.text = text

    def button_press(self, x: int, y: int, button: int) -> None:
        if button == self.pause_button:
            self.cmd_toggle_paused()
        elif button in (1, 3):
            self.cmd_show_schedule()

    def span(self, text: str, color: str) -> str:
        return f"<span foreground='#{color}'>{text}</span>"

    def poll(self, tick: bool = True) -> str:
        duration = self.checkclock.get_value(tick=tick)
        if duration == Checkclock.paused_state:
            return self.span(self.paused_text, self.paused_color)
        if duration == Checkclock.not_working_state:
            return self.span("✖", self.paused_color)
        if duration >= self.avg_working_time:
            color = self.done_color
        elif duration >= self.avg_working_time - self.min_working_time:
            color = self.almost_done_color
        else:
            color = self.active_color
        return self.span(self.format_time(duration), color)

    def format_schedule(self, days_back: int) -> Generator[str, None, None]:
        if not days_back:
            for start, end in self.checkclock.merge_durations(0):
                diff = end - start
                time = as_time(int(diff.total_seconds())).strftime("%k:%M")
                time_range = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}: {time}"
                yield time_range
        else:
            for start, end, duration in self.checkclock.get_backlog(days_back):  # type: ignore[assignment]
                time = as_time(duration).strftime("%k:%M")
                time_range = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}: {time}"
                yield time_range

    @staticmethod
    def get_monday() -> datetime.date:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        return monday

    def get_color(self, duration: int) -> str:
        return "green" if duration >= self.checkclock.avg_working_time else "red"

    @staticmethod
    def format_msg(data: Any, color: str, bold: bool = False) -> str:
        msg = [f'<span foreground="{color}">']
        if bold:
            msg.append("<b>")
        msg.append(str(data))
        if bold:
            msg.append("</b>")
        msg.append("</span>")
        return "".join(msg)

    def cmd_show_schedule(self, num_weeks: Union[str, int] = 0) -> None:
        total_duration: List[int] = []
        monday = self.get_monday() - datetime.timedelta(days=int(num_weeks) * 7)
        num_days = datetime.date.today() - monday
        msg = [""]
        schedule_dates = list(self.checkclock.get_dates_from_schedule())
        for i in range(num_days.days, -1, -1):
            if i > 0 and get_previous_date(i) in schedule_dates:
                self.checkclock.compact(days_back=i)
            min_duration = 0 if not i else self.min_working_time
            duration = self.checkclock.get_duration_from_backlog(
                days_back=i, min_duration=min_duration
            )
            if duration is None:
                continue
            total_duration.append(duration)
            schedule = "\n".join(" " + x for x in self.format_schedule(days_back=i))
            if not schedule:
                continue
            color = self.get_color(duration)
            table_date = get_previous_date(i).strftime("%a, %Y-%m-%d")
            msg.append(
                self.format_msg(
                    f"{table_date}: {as_hours_and_minutes(duration)}", color, bold=True
                )
            )
            if not i:
                msg.append(schedule)
            else:
                msg.append("")
        msg.append("=" * 24)
        # FIXME don't restrict this to 5 max, but implement something else
        exp_duration = self.avg_working_time * min(5, len(self.checkclock.working_days))
        diff = sum(total_duration) - exp_duration * int(num_weeks)
        formatted_diff = as_hours_and_minutes(diff)
        color = "green" if diff >= 0 else "red"
        msg.append(f"<b>total balance:</b> {self.format_msg(formatted_diff, color=color)}")
        dunstify.run(f"--replace={self.id}", "balance", "\n".join(msg))
