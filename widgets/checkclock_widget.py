import os
import shutil
import datetime
from typing import Generator, List
from procs import dunstify
from pathlib import Path
from libqtile.widget.base import ThreadedPollText, ORIENTATION_HORIZONTAL
from libqtile.widget.textbox import TextBox
from .checkclock import Checkclock, normalize_color, as_time, as_hours_and_minutes, get_previous_date


class CheckclockWidget(ThreadedPollText):

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
            ("pause_function", None, "function to call when toggling the pause state. "
                "receives arguments (is_paused: bool, value: str)"),
            ("avg_working_time", 8*60*60, "number of seconds to work per day"),
            ("working_days", "Mon-Fri", "textual representation of working days, e.g. Mon-Fri, Tue,Wed-Sat"),
    ]

    def __init__(self, **config):
        super().__init__(**config)
        self.add_defaults(CheckclockWidget.defaults)
        self.db_path = Path(os.path.expanduser(self.db_path))
        self.checkclock = Checkclock(tick_length=self.update_interval, path=self.db_path, avg_working_time=self.avg_working_time,
                working_days=self.working_days)
        self.active_color = normalize_color(self.active_color)
        self.done_color = normalize_color(self.done_color)
        self.almost_done_color = normalize_color(self.almost_done_color)
        self.paused_color = normalize_color(self.paused_color)
        self.pause_button = int(self.pause_button)
        self.companions: List[TextBox] = []

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
            self.pause_function(self.checkclock.paused, self.format_time(self.checkclock.duration))
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
        elif duration >= self.avg_working_time + 30*60:
            color = self.almost_done_color
        else:
            color = self.active_color
        return self.span(self.format_time(duration), color)

    def format_schedule(self, days_back: int) -> Generator[str, None, None]:
        if not days_back:
            for start, end in self.checkclock.merge_durations(0):
                diff = end - start
                time = as_time(diff.total_seconds()).strftime("%k:%M")
                time_range = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}: {time}"
                yield time_range
        else:
            for start, end, duration in self.checkclock.get_backlog(days_back):
                time = as_time(duration).strftime("%k:%M")
                time_range = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}: {time}"
                yield time_range

    def cmd_show_schedule(self) -> None:
        total_diff = as_hours_and_minutes(sum(self.checkclock.get_balance(days_back=i) for i in range(30)))

        msg = [""]
        num_days = 5
        schedule_dates = list(self.checkclock.get_dates_from_schedule())
        for i in range(num_days, -1, -1):
            if i > 0 and get_previous_date(i) in schedule_dates:
                prev_date = get_previous_date(days_back=i).isoformat()
                db_copy = self.db_path.with_suffix(f".copy-{prev_date}.sqlite")
                shutil.copy2(src=self.db_path, dst=db_copy, follow_symlinks=True)
                self.checkclock.compact(days_back=i)
            diff = self.checkclock.get_balance(days_back=i)
            if not diff:
                continue
            schedule = "\n".join(" " + x for x in self.format_schedule(days_back=i))
            color = "green" if diff >= 0 else "red"
            msg.append(f'<span foreground="{color}"><b>{get_previous_date(i)}: {as_hours_and_minutes(diff)}</b></span>')
            msg.append(schedule)
            if i > 0:
                msg.append("-" * 5)
        msg.append("=" * 24)
        msg.append(f"<b>total balance</b>: {total_diff}")
        dunstify.run("balance", "\n".join(msg))
