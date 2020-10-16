import os
import dbus
import sqlite3
import datetime
from procs import dunstify
from pathlib import Path
from libqtile.widget.base import ThreadedPollText, _TextBox, ORIENTATION_HORIZONTAL
from typing import Optional


def as_time_tuple(seconds: int):
    seconds = int(seconds)
    s = seconds % 60
    rem = seconds // 60
    m = rem % 60
    h = rem // 60
    return (h, m, s)


def as_hours_and_minutes(seconds: int):
    h, m, _ = as_time_tuple(seconds)
    return f"{h}:{m:02}"


def as_time(seconds):
    return datetime.time(*as_time_tuple(int(seconds)))


def as_datetime(date: str, time: str):
    string = f"{date} {time}"
    return datetime.datetime.fromisoformat(string)


def as_delta(seconds: int):
    return datetime.timedelta(seconds=seconds)


def get_previous_date(days_back: int):
    return datetime.date.today() - datetime.timedelta(days=days_back)


class Checkclock:

    """
    screensaver_list = ['org.gnome.ScreenSaver',
                        'org.cinnamon.ScreenSaver',
                        'org.kde.screensaver',
                        'org.freedesktop.ScreenSaver']

    for each in screensaver_list:
        try:
            object_path = '/{0}'.format(each.replace('.', '/'))
            get_object = session_bus.get_object(each, object_path)
            get_interface = dbus.Interface(get_object, each)
            status = bool(get_interface.GetActive())
            print(status)
        except dbus.exceptions.DBusException:
            pass
    """

    def __init__(self, tick_length: int, path: Path, avg_working_time: int = 8*60*60):
        proxy_object = dbus.SessionBus().get_object("org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver")
        self.dbus_method = dbus.Interface(proxy_object, "org.cinnamon.ScreenSaver").GetActive
        self.path = path
        self.tick_length = tick_length
        self.today = self.get_today()
        self.avg_working_time = avg_working_time
        if not self.path.parent.exists():
            self.path.mkdir(parents=True, exists_ok=True)
        if not self.path.exists():
            con = self.get_connection()
            with con:
                con.execute("CREATE TABLE schedule (date DATE, time TIME, duration INTEGER)")
                con.execute("CREATE INDEX date_idx ON schedule (date)")
                con.execute("CREATE TABLE paused (state bool)")
                con.execute("CREATE TABLE backlog (date DATE, start TIME, end TIME, duration INTEGER)")
                con.execute("CREATE INDEX date_backlog_idx ON backlog (date)")
                con.execute("CREATE TABLE balance (date DATE, seconds_worked INTEGER)")
                con.execute("CREATE UNIQUE INDEX date_balance_idx ON balance (date)")
                con.execute("INSERT INTO paused VALUES (true)")
            self.paused = True
            self.duration = 0
        else:
            self.duration = self.get_duration_from_db()
            self.paused = self.get_paused_state_from_db()

    def get_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.row_factory = sqlite3.Row
        return con

    def get_today(self):
        return datetime.date.today().strftime("%F")

    def get_duration_from_db(self):
        con = self.get_connection()
        with con:
            cur = con.cursor()
            cur.execute("SELECT Coalesce(Sum(duration), 0) AS duration FROM schedule WHERE date = date('now', 'localtime')")
            row = cur.fetchone()
            duration = row["duration"]
        return duration

    def get_paused_state_from_db(self) -> bool:
        con = self.get_connection()
        with con:
            cur = con.cursor()
            return bool(cur.execute("SELECT state FROM paused").fetchone()["state"])

    def tick(self):
        con = self.get_connection()
        with con:
            con.execute("INSERT INTO schedule (date, time, duration) VALUES (date('now', 'localtime'), time('now', 'localtime'), ?)",
                    [self.tick_length])
        today = self.get_today()
        if self.today == today:
            self.duration += self.tick_length
        else:
            self.today = today
            self.duration = self.tick_length
            min_duration = min(60, self.tick_length)
            for date in self.get_dates_from_schedule():
                days_back = (datetime.date.today() - datetime.date.fromisoformat(date)).days
                self.compact(merge_threshold=self.tick_length, min_duration=min_duration, days_back=days_back, con=con)

    def get_dates_from_schedule(self):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT distinct date from schedule")
        for row in cur:
            yield row["date"]

    def toggle_paused(self):
        con = self.get_connection()
        with con:
            con.execute("UPDATE paused SET state = NOT state")
        self.paused = not self.paused

    def is_screensaver_active(self):
        return bool(self.dbus_method())

    def get_value(self, tick=True):
        if self.paused:
            return -1
        if self.is_screensaver_active():
            return self.duration
        if tick:
            self.tick()
        return self.duration

    def get_balance(self, days_back: int = 0):
        if not days_back:
            query = """
                SELECT
                  SUM(duration) AS secs
                FROM
                  schedule
                WHERE
                  date = date('now', 'localtime')
                """
            params = []
        else:
            query = """
                SELECT
                  seconds_worked as secs
                FROM
                  balance
                WHERE
                  date = ?
                """
            params = [get_previous_date(days_back)]

        con = self.get_connection()
        with con:
            rows = con.execute(query, params)
            if not rows.rowcount:
                return 0
            if (x := rows.fetchone()) and (diff := x[0]):
                return diff - self.avg_working_time
            return 0

    def merge_durations(self, days_back:int, con: Optional[sqlite3.Connection] = None):
        merge_threshold = as_delta(self.tick_length)
        min_duration = min(self.tick_length, 60)
        if not con:
            con = self.get_connection()
        cur = con.cursor()
        prev_duration = None

        offset = f"-{days_back} days"
        for row in cur.execute("SELECT date, time, duration FROM schedule WHERE date = date('now', ?, 'localtime')", [offset]):
            start = as_datetime(row["date"], row["time"])
            end = start + as_delta(row["duration"])
            if not prev_duration:
                prev_duration = (start, end)
                continue

            prev_start, prev_end = prev_duration
            duration = as_delta(row["duration"])

            if prev_end + merge_threshold >= start:
                merged_end = max(prev_end, end)
                prev_duration = (prev_start, merged_end)
            else:
                if (prev_end - prev_start).total_seconds() > min_duration:
                    yield prev_duration
                prev_duration = (start, end)
        if prev_duration and (prev_duration[1] - prev_duration[0]).total_seconds() > min_duration:
            yield prev_duration


    def compact(self, days_back: int, con: Optional[sqlite3.Connection] = None):
        if days_back <= 0:
            raise ValueError(f"bad number for days_back. got: {days_back}. expected: days_back >= 1")

        date = get_previous_date(days_back)
        backlog_sql = """
        INSERT INTO backlog (date, start, end, duration)
        VALUES (?, ?, ?, ?)
        """
        deletion_query = """
        DELETE FROM schedule
        WHERE
          date = ?
        """
        balance_query = """
        INSERT INTO balance (date, seconds_worked)
        SELECT
          date,
          Sum(duration)
        FROM
          backlog
        WHERE
          date = ?
        """
        if not con:
            con = self.get_connection()
        for start, end in self.merge_durations(days_back):
            duration = int((end - start).total_seconds())
            con.execute(backlog_sql, [date, start.strftime("%T"), end.strftime("%T"), duration])
        con.execute(balance_query, [date])
        con.execute(deletion_query, [date])
        con.commit()

    def get_backlog(self, days_back: int):
        if not days_back:
            raise ValueError(f"bad argument for days_back. expteded: days_back > 0. got: {days_back}")
        date = get_previous_date(days_back)
        query = """
        SELECT
          start,
          end,
          duration
        FROM
          backlog
        WHERE
          date = ?
        """
        con = self.get_connection()
        for start, end, duration in con.execute(query, [date]):
            yield start, end, duration


class CheckclockWidget(ThreadedPollText):

    orientations = ORIENTATION_HORIZONTAL
    defaults = [
            ("db_path", "~/.config/qtile/checkclock.sqlite", "path to the sqlite db"),
            ("paused_text", "paused", "text to show when paused"),
            ("time_format", "%H:%M", "strftime-like format for checkclock time"),
            ("active_color", "#ffffff", "color of text in active state"),
            ("paused_color" "#808080", "color of paused text"),
            ("pause_button", 1, "mouse button to toggle pause"),
            ("pause_function", None, "function to call when toggling the pause state. "
                "receives arguments (is_paused: bool, value: str)"),
    ]

    def __init__(self, **config):
        super().__init__(**config)
        self.add_defaults(CheckclockWidget.defaults)
        db_path = Path(os.path.expanduser(self.db_path))
        self.checkclock = Checkclock(tick_length=self.update_interval, path=db_path)
        self.active_color = self.active_color[1:] if self.active_color.startswith("#") else self.active_color
        self.paused_color = self.paused_color[1:] if self.paused_color.startswith("#") else self.paused_color
        self.pause_button = int(self.pause_button)

    def format_time(self, duration):
        seconds = duration % 60
        rem = duration // 60
        minutes = rem % 60
        hours = rem // 60
        return datetime.time(hours, minutes, seconds).strftime(self.time_format).strip()

    def cmd_toggle_paused(self):
        self.checkclock.toggle_paused()
        value = self.poll(tick=not self.checkclock.paused)
        if self.pause_function:
            self.pause_function(self.checkclock.paused, self.format_time(self.checkclock.duration))
        self.update(text=value)

    def button_press(self, x, y, button):
        if button == self.pause_button:
            self.cmd_toggle_paused()
        elif button in (1, 3):
            self.show_schedule()

    def span(self, text, color):
        return f"<span foreground='#{color}'>{text}</span>"

    def poll(self, tick=True):
        duration = self.checkclock.get_value(tick=tick)
        if duration == -1:
            return self.span(self.paused_text, self.paused_color)
        return self.span(self.format_time(duration), self.active_color)

    def format_schedule(self, days_back:int):
        if not days_back:
            for start, end in self.checkclock.merge_durations(0):
                diff = end - start
                time = as_time(diff.total_seconds()).strftime("%k:%M")
                time_range = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}: {time}"
                yield time_range
        else:
            for start, end, duration in self.checkclock.get_backlog(days_back):
                time = as_time(duration).strftime("%k:%M")
                start = datetime.time.fromisoformat(start).strftime("%H:%M")
                end = datetime.time.fromisoformat(end).strftime("%H:%M")
                time_range = f"{start} - {end}: {time}"
                yield time_range

    def show_schedule(self):
        total_diff = as_hours_and_minutes(sum(self.checkclock.get_balance(days_back=i) for i in range(30)))

        msg = []
        msg.append("balance")
        msg.append("=" * 32)

        num_days = 3
        schedule_dates = list(self.checkclock.get_dates_from_schedule())
        for i in range(num_days, -1, -1):
            if i > 0 and get_previous_date(i).isoformat() in schedule_dates:
                self.checkclock.compact(days_back=i)
            diff = self.checkclock.get_balance(days_back=i)
            if not diff:
                continue
            schedule = "\n".join(self.format_schedule(days_back=i))
            msg.append(f"{get_previous_date(i)}")
            msg.append(schedule)
            msg.append(f"balance: {as_hours_and_minutes(diff)}")
            if i < num_days:
                msg.append("-" * 32)
        msg.append("=" * 32)
        msg.append(f"total balance: {total_diff}")
        dunstify("\n".join(msg))
