import os
import dbus
import sqlite3
import datetime
from pathlib import Path
from libqtile.widget.base import ThreadedPollText, ORIENTATION_HORIZONTAL


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

    def __init__(self, tick_length: int, path: Path):
        proxy_object = dbus.SessionBus().get_object("org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver")
        self.dbus_method = dbus.Interface(proxy_object, "org.cinnamon.ScreenSaver").GetActive
        self.path = path
        self.tick_length = tick_length
        self._dont_tick = False
        self.today = self.get_today()
        if not self.path.parent.exists():
            self.path.mkdir(parents=True, exists_ok=True)
        if not self.path.exists():
            con = self.get_connection()
            with con:
                con.execute("CREATE TABLE schedule (date DATE, time TIME, duration INTEGER)")
                con.execute("CREATE INDEX date_idx ON schedule (date)")
                con.execute("CREATE TABLE paused (state bool)")
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

    def toggle_paused(self):
        con = self.get_connection()
        with con:
            con.execute("UPDATE paused SET state = NOT state")
        self.paused = not self.paused
        self._dont_tick = True

    def is_screensaver_active(self):
        return bool(self.dbus_method())

    def get_value(self):
        if self.paused:
            return -1
        if self.is_screensaver_active():
            return self.duration
        if self._dont_tick:
            self._dont_tick = False
        else:
            self.tick()
        return self.duration

class CheckclockWidget(ThreadedPollText):

    orientations = ORIENTATION_HORIZONTAL
    defaults = [
            ("db_path", "~/.config/qtile/checkclock.sqlite", "path to the sqlite db"),
            ("paused_text", "paused", "text to show when paused"),
            ("time_format", "%H:%M", "strftime-like format for checkclock time"),
            ("foreground", "#ffffff", "foreground color of text"),
            ("paused_color" "#808080", "color of paused text")
    ]

    def __init__(self, **config):
        callbacks = {"Button1": self.toggle_paused}
        super().__init__(mouse_callbacks=callbacks, **config)
        self.add_defaults(CheckclockWidget.defaults)
        db_path = Path(os.path.expanduser(self.db_path))
        self.checkclock = Checkclock(tick_length=self.update_interval, path=db_path)
        self.foreground = self.foreground[1:] if self.foreground.startswith("#") else self.foreground
        self.paused_color = self.paused_color[1:] if self.paused_color.startswith("#") else self.paused_color

    def format_time(self, duration):
        seconds = duration % 60
        rem = duration // 60
        minutes = rem % 60
        hours = rem // 60
        return datetime.time(hours, minutes, seconds).strftime(self.time_format)

    def toggle_paused(self, _):
        self.checkclock.toggle_paused()
        self.poll()

    def span(self, text, color):
        return f"<span foreground='#{color}'>{text}</span>"

    def poll(self):
        duration = self.checkclock.get_value()
        if duration == -1:
            return self.span(self.paused_text, self.paused_color)
        return self.span(self.format_time(duration), self.foreground)
