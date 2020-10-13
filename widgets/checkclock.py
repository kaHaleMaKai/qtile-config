import os
import dbus
import sqlite3
import datetime
from pathlib import Path
from libqtile.widget.base import ThreadedPollText, _TextBox, ORIENTATION_HORIZONTAL


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
                "receives arguments (is_paused: bool, value: str)")
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

    def span(self, text, color):
        return f"<span foreground='#{color}'>{text}</span>"

    def poll(self, tick=True):
        duration = self.checkclock.get_value(tick=tick)
        if duration == -1:
            return self.span(self.paused_text, self.paused_color)
        return self.span(self.format_time(duration), self.active_color)
