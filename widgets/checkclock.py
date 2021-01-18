import os
import re
try:
    import dbus  # type: ignore  # no stub present
    has_dbus = True
except ImportError:
    has_dbus = False
import sqlite3
import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Generator, Callable, Any, Dict
from enum import Enum


MaybeConnection = Optional[sqlite3.Connection]


def normalize_color(color: str) -> str:
    return color[1:] if color.startswith("#") else color


def as_time_tuple(seconds: int) -> Tuple[int, int, int]:
    if seconds < 0:
        raise ValueError(f"bad argument. expected: seconds >= 0. got: {seconds}")
    seconds = int(seconds)
    s = seconds % 60
    rem = seconds // 60
    m = rem % 60
    h = rem // 60
    return (h, m, s)


def as_hours_and_minutes(seconds: int) -> str:
    s = "" if seconds > 0 else "-"
    h, m, _ = as_time_tuple(abs(seconds))
    return f"{s}{h}:{m:02}"


def as_time(seconds: int) -> datetime.time:
    return datetime.time(*as_time_tuple(int(seconds)))


def as_datetime(date: str, time: str) -> datetime.datetime:
    string = f"{date} {time}"
    return datetime.datetime.fromisoformat(string)


def as_delta(seconds: int) -> datetime.timedelta:
    return datetime.timedelta(seconds=seconds)


def get_previous_date(days_back: int) -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=days_back)


# class ScreenSaverCheck:

#     def __init__(self, screen_saver: ScreenSaver = ScreenSaver.UNKNOWN):
#         self.screen_saver = screen_saver

#     @staticmethod
#     def deduce_screen_saver():
#         screensaver_list = ['org.gnome.ScreenSaver',
#                             'org.cinnamon.ScreenSaver',
#                             'org.kde.screensaver',
#                             'org.freedesktop.ScreenSaver']

#         session_bus = dbus.SessionBus()
#         for screen_saver in ScreenSaver:
#             if screen_saver == ScreenSaver.UNKNOWN:
#                 continue
#             try:
#                 name = f"org.{screen_saver.name.lower()}.ScreenSaver"
#                 object_path = '/{0}'.format(name.replace('.', '/'))
#                 get_object = session_bus.get_object(name, object_path)
#                 get_interface = dbus.Interface(get_object, name)
#                 status = bool(get_interface.GetActive())
#                 print(status)
#             except dbus.exceptions.DBusException:
#                 pass


class Weekday(Enum):
    MON = 1
    TUE = 2
    WED = 3
    THU = 4
    FRI = 5
    SAT = 6
    SUN = 7

    @classmethod
    def parse(cls, value: str) -> List["Weekday"]:
        value = value.upper()
        weekdays = set()
        for split in re.split(r"\s*,\s*|(?<![-\s])\s+(?![-\s])", value):
            days = [d_ for d in re.split(r"\s*-\s*", split) if (d_ := d.strip())]
            if not days:
                continue
            if len(days) == 1:
                day = cls[days[0]]
                weekdays.add(day)
            elif len(days) > 2:
                raise ValueError(f"bad weekday range: {days}")
            else:
                start, end = days
                idx0 = cls[start].value
                idx1 = cls[end].value
                for i in range(min(idx0, idx1), max(idx0, idx1)+1):
                    weekdays.add(cls(i))
        result = sorted(weekdays, key=lambda k: k.value)
        if not result:
            raise ValueError("parsed result is empty")
        return result

    def is_same_day(self, date: datetime.date) -> bool:
        return date.isoweekday() == self.value


class Checkclock:

    paused_state = -1
    not_working_state = -2

    def __init__(self,
            tick_length: int,
            path: Path,
            avg_working_time: int = 8*60*60,
            working_days: str = "Mon-Fri",
            ro: bool = False,
            on_duration_update: Optional[Callable[[int], Any]] = None,
            on_tick: Optional[Callable[[int], Any]] = None,
            on_pause: Optional[Callable[[int], Any]] = None,
            on_resume: Optional[Callable[[int], Any]] = None,
            on_rollover: Optional[Callable[[int], Any]] = None,
            ) -> None:

        self.working_days = Weekday.parse(working_days)
        self.work_today = self.check_work_today()
        if has_dbus:
            proxy_object = dbus.SessionBus().get_object("org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver")
            self.dbus_method = dbus.Interface(proxy_object, "org.cinnamon.ScreenSaver").GetActive
        else:
            self.dbus_method = lambda: False
        self.path = path
        self.tick_length = tick_length
        self.today = datetime.date.today()
        self.avg_working_time = avg_working_time
        self.ro = ro
        self._duration = 0

        self.hooks: Dict[Callable[[Any, ...], Any]] = {}
        if on_duration_update:
            self.hooks["on_duration_update"] = on_duration_update
        if on_tick:
            self.hooks["on_tick"] = on_tick
        if on_pause:
            self.hooks["on_pause"] = on_pause
        if on_resume:
            self.hooks["on_resume"] = on_resume
        if on_rollover:
            self.hooks["on_rollover"] = on_rollover

        if not self.path.exists():
            self.init_db()
            self.paused = True
            self.duration = 0
        else:
            self.duration = self.get_duration_from_db()
            self.paused = self.get_paused_state_from_db()

    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, duration: int) -> None:
        self._duration = duration
        self.call_hook("on_duration_update", duration)

    def init_db(self) -> None:
        if not self.path.parent.exists():
            self.path.mkdir(parents=True, exist_ok=True)
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

    def get_connection(self) -> sqlite3.Connection:
        uri = f"{self.path.as_uri()}?mode=ro" if self.ro else self.path.as_uri()
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        return con

    def get_duration_from_db(self, con: MaybeConnection = None) -> int:
        con = con or self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT Coalesce(Sum(duration), 0) AS duration FROM schedule WHERE date = ?",
                [datetime.date.today()])
        row = cur.fetchone()
        return row["duration"]

    def get_paused_state_from_db(self, con: MaybeConnection = None) -> bool:
        con = con or self.get_connection()
        with con:
            cur = con.cursor()
            return bool(cur.execute("SELECT state FROM paused").fetchone()["state"])

    def tick(self) -> None:
        self.call_hook("on_tick", self.duration)
        con = self.get_connection()
        now = datetime.datetime.now()
        with con:
            con.execute("INSERT INTO schedule (date, time, duration) VALUES (?, ?, ?)",
                    [now.strftime("%F"), now.strftime("%H:%M:%S"), self.tick_length])
            today = datetime.date.today()

            if self.today == today and self.work_today:
                if self.duration % 600 == 0:
                    self.duration = self.get_duration_from_db(con)
                else:
                    self.duration += self.tick_length
            else:
                self.today = today
                self.work_today = self.check_work_today(today)
                if self.work_today:
                    self.duration = self.tick_length
                else:
                    self.call_hook("on_rollover", self.duration)
                    self.duration = 0
                min_duration = min(60, self.tick_length)
                for date in self.get_dates_from_schedule():
                    days_back = (datetime.date.today() - date).days
                    self.compact(days_back=days_back, con=con)

    def call_hook(self, hook: str, *args, **kwargs) -> None:
        if hook in self.hooks:
            self.hooks[hook](*args, **kwargs)

    def check_work_today(self, today: Optional[datetime.date] = None) -> bool:
        t: datetime.date = today if today else datetime.date.today()
        fn: Callable[[Weekday], bool] = lambda w: w.is_same_day(t)
        return any(filter(fn, self.working_days))  # type: ignore  # using more narrow type is OK

    def get_dates_from_schedule(self) -> Generator[datetime.date, None, None]:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT distinct date from schedule WHERE date < ?", [datetime.date.today()])
        for row in cur:
            yield datetime.date.fromisoformat(row["date"])

    def toggle_paused(self) -> None:
        con = self.get_connection()
        with con:
            con.execute("UPDATE paused SET state = NOT state")
        self.paused = not self.paused
        if self.paused:
            self.call_hook("on_pause", self.duration)
        else:
            self.call_hook("on_resume", self.duration)

    def is_screensaver_active(self) -> bool:
        return bool(self.dbus_method())

    def get_value(self, tick: bool = True) -> int:
        if not self.work_today and not self.check_work_today():
            return self.not_working_state
        if self.paused:
            return self.paused_state
        if self.is_screensaver_active():
            return self.duration
        if tick:
            self.tick()
        return self.duration

    def get_balance(self, days_back: int = 0, min_duration: int = 600) -> int:
        if not days_back:
            query = """
                SELECT
                  SUM(duration) AS secs
                FROM
                  schedule
                WHERE
                  date = ?
                GROUP BY
                  `date`
                HAVING
                  SUM(duration) >= ?
                """
            params = [datetime.date.today(), min_duration]
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

    def merge_durations(self, days_back:int,
            con: MaybeConnection = None) -> Generator[Tuple[datetime.date, datetime.date], None, None]:
        merge_threshold = as_delta(self.tick_length)
        min_duration = max(self.tick_length, 60)
        con = con or self.get_connection()
        cur = con.cursor()
        prev_duration = None

        day = get_previous_date(days_back=days_back)
        for row in cur.execute("""SELECT date, time, duration FROM schedule WHERE date = ? ORDER BY time""", [day]):
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


    def compact(self, days_back: int, con: MaybeConnection = None) -> None:
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
        con = con or self.get_connection()
        for start, end in self.merge_durations(days_back):
            duration = int((end - start).total_seconds())
            con.execute(backlog_sql, [date, start.strftime("%T"), end.strftime("%T"), duration])
        con.execute(balance_query, [date])
        con.execute(deletion_query, [date])

    def get_backlog(self, days_back: int) -> Generator[Tuple[datetime.time, datetime.time, int], None, None]:
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
            yield (datetime.time.fromisoformat(start),
                    datetime.time.fromisoformat(end),
                    duration)


class ReadOnlyCheckclock(Checkclock):

    def __init__(self, path: Path, avg_working_time: int = 8*60*60, working_days: str = "Mon-Fri", merge_threshold: int = 5):
        super().__init__(tick_length=merge_threshold, path=path, avg_working_time=avg_working_time, working_days=working_days, ro=True)

    def tick(self) -> None:
        pass

    def get_value(self) -> None:
        return None

    def toggle_paused(self) -> None:
        pass

    def compact(self, days_back: int, con: MaybeConnection = None) -> None:
        pass
