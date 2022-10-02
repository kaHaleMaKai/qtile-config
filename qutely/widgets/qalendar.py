import os
import re
import pytz
import random
import locale
import shutil
import sqlite3
import datetime
from enum import Enum
from pathlib import Path
from typing import (Union, Optional, Sequence, Generator, List,
        Any, Dict, Set, FrozenSet, Tuple, Callable)


MaybeString = Optional[str]
MaybeDate = Optional[datetime.date]
MaybeDateTime = Optional[datetime.datetime]
Date = datetime.date
DateTime = datetime.datetime
DtLike = Union[Date, DateTime]
MaybeAttendees = Optional[Sequence[Attendee]]
TimeZone = datetime.tzinfo
TZ_EUROPE_BERLIN = pytz.timezone("Europe/Berlin")


def format_time(dt: DateTime) -> str:
    return dt.strftime('%H:%M')


def format_dt(dt: DateTime) -> str:
    return dt.strftime("%F %H:%M")


def to_monday(dt: DtLike) -> Date:
    res = dt - datetime.timedelta(days=dt.weekday())
    if isinstance(dt, DateTime):
        return res.date()  # type: ignore
    else:
        return res


def get_week_interval(dt1: DtLike, dt2: DtLike) -> int:
    d1 = to_monday(dt1)
    d2 = to_monday(dt2)
    return (d2 - d1).days // 7


def to_utc(date: Date) -> DateTime:
    dt = datetime.datetime.fromordinal(date.toordinal())
    return TZ_EUROPE_BERLIN.localize(dt).astimezone(pytz.utc)


def zoned(timestamp: str, tz: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(timestamp)
    if tz == "floating":
        return TZ_EUROPE_BERLIN.localize(dt)
    timezone = pytz.timezone(tz)
    return pytz.utc.localize(dt).astimezone(timezone)

def from_zdate(date: str) -> DateTime:
    return datetime.datetime.strptime(date, "%Y%m%dT%H%M%SZ")


class Weekday(Enum):
    MON = 0
    TUE = 1
    WED = 2
    THU = 3
    FRI = 4
    SAT = 5
    SUN = 6

    @classmethod
    def for_name(cls, prefix: str) -> "Weekday":
        for day in cls:
            if day.name.startswith(prefix[:3]):
                return day
        raise ValueError(f"wrong prefix for weekday. prefix '{prefix}' unknown")

    @classmethod
    def for_datetime(cls, dt: Union[Date, DateTime]) -> "Weekday":
        return cls(dt.weekday())


class Recurrence:

    def __init__(self, recurrence_id: int, recurrence_id_tz: str) -> None:
        self.id = recurrence_id
        self.tz = pytz.timezone(recurrence_id_tz) if recurrence_id_tz else pytz.utc

    def __bool__(self) -> bool:
        return bool(self.id)


class RecurrenceRule:

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

    rule_query = """
    SELECT
      cal_id,
      item_id,
      icalString
    FROM
      cal_recurrence
    WHERE
      icalString LIKE 'RRULE:%'
    """

    split_pattern = re.compile(";")

    freq: Optional[str]
    days: Set[Weekday]
    interval: int
    dom: Optional[int]
    month: Optional[int]
    until: Optional[DateTime]

    def __init__(self, cal_id: str, item_id: str, rule_dict: Dict[str, Any]) -> None:
        self.event_id = item_id
        self.cal_id = cal_id
        for key in ("freq", "dom", "month", "until"):
            setattr(self, key, rule_dict.get(key))
        self.interval = rule_dict.get("interval", 1)
        self.days = {day for day in rule_dict.get("days", [])}

    def __str__(self) -> str:
        return f"<Rule[{self.freq}]>"

    def __repr__(self) -> str:
        return str(self)

    def matches(self, event: "Event", compare_dt: DateTime) -> bool:
        if self.until and compare_dt > self.until.astimezone(event.start.tzinfo):
            return False
        w = Weekday.for_datetime(compare_dt)
        if self.freq == self.WEEKLY:
            if w not in self.days:
                return False
            if self.interval == 1:
                return True
            return get_week_interval(compare_dt, event.start) % self.interval == 0
        elif self.freq == self.MONTHLY:
            # not implemented
            return False
        elif self.freq == self.YEARLY:
            if self.dom:
                if compare_dt.day != self.dom:
                    return False
                return not self.month or compare_dt.month == self.month
        return False


    @classmethod
    def parse_rule(cls, rule: str) -> Dict[str, Any]:
        splits = cls.split_pattern.split(rule[6:])
        d = {}
        for split in splits:
            k, v = split.split("=")
            if k == "FREQ":
                d["freq"] = v.lower()
            elif k == "BYDAY":
                days = [Weekday.for_name(day) for day in v.split(",")]
                d["days"] = days
            elif k == "INTERVAL":
                d["interval"] = int(v)
            elif k == "BYMONTHDAY":
                d["dom"] = int(v)
            elif k == "BYMONTH":
                d["month"] = int(v)
            elif k == "UNTIL":
                d["until"] = from_zdate(v)
        return d

    @classmethod
    def get_all_rules(cls, con: sqlite3.Connection) -> Generator["RecurrenceRule", None, None]:
        cursor = con.execute(cls.rule_query)
        for row in cursor:
            cal_id = row["cal_id"]
            item_id = row["item_id"]
            rule = cls.parse_rule(row["icalString"].strip())
            args = {"cal_id": cal_id, "item_id": item_id, "rule_dict": rule}
            yield cls(**args)


class TbProperties:

    def __init__(self, desc: MaybeString, busy: MaybeString, meeting_status: MaybeString,
            response_type: MaybeString) -> None:
        self.desc = desc
        self.busy = busy
        self.meeting_status = meeting_status
        self.response_type = response_type

    def __bool__(self) -> bool:
        return bool(self.desc)


class Attendee:

    def __init__(self, name: str) -> None:
        self.name = name


class TbAttendee(Attendee):

    def __init__(self, name: str, mail: MaybeString) -> None:
        super().__init__(name)
        self.mail = mail

    def __bool__(self) -> bool:
        return bool(self.name)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Attendee[{self.name}]>"

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if type(self) != type(other):
            return False
        return self.name == other.name and self.mail == other.mail

    def __hash__(self) -> int:
        return hash(self.name) + hash(self.mail)


class CalendarStatus(Enum):

    CONFIRMED = 0
    TENTATIVE = 1
    CANCELLED = 2
    NONE = 3

    @classmethod
    def by_name(cls, name: MaybeString) -> "CalendarStatus":
        if not name:
            return cls.NONE
        return cls[name]


class MeetingType(Enum):

    NORMAL = 0
    PERSONAL = 1
    TEAMS = 2
    ZOOM = 3


class Event:

    def __init__(self, id: str, start: DateTime, end: DateTime,
            title: str, status: CalendarStatus, cal_id: MaybeString = None,
            attendees: Optional[Sequence[Attendee]] = None) -> None:
        self.id = id
        self.cal_id = cal_id
        self.start = start
        self.end = end
        self.title = title
        self.status = status
        self.attendees: FrozenSet[Attendee]
        if attendees:
            self.attendees = frozenset(attendees)
        else:
            self.attendees = frozenset()
        diff = self.end - self.start
        self.whole_day = diff.days >= 1 and diff.seconds == 0
        self.more_days = self.whole_day and diff.days > 1
        self.same_day = diff.days == 0

    def format_duration(self) -> str:
        if self.same_day:
            time = f"{self.start.date()} {format_time(self.start)}-{format_time(self.end)}"
        elif self.more_days:
            time = f"{self.start.date()} - {self.end.date()}"
        elif self.whole_day:
            time = f"{self.start.date()}"
        else:
            time = f"{format_dt(self.start)} - {format_dt(self.end)}"
        return time

    def __eq__(self, other: Any) -> bool:
        if not other:
            return False
        if self is other:
            return True
        if type(self) != type(other):
            return False
        for attr in ("id", "cal_id", "start", "end", "title", "attendees"):
            if getattr(self, attr, None) != getattr(other, attr, None):
                return False
        return True

    def __hash__(self) -> int:
        hash_value = 0

        for attr in ("id", "cal_id", "start", "end", "title"):
            hash_value += hash(getattr(self, attr)) % 17 + 31

        return hash_value

    def __str__(self) -> str:
        return f"""<{type(self).__name__}["{self.title}", time={self.format_duration()}]>"""

    def __repr__(self) -> str:
        return str(self)

    def with_date(self, date: Date, *args, **kwargs) -> "Event":
        diff = (self.end - self.start).days
        s = datetime.datetime.combine(date, self.start.time())
        end_date = date + datetime.timedelta(days=diff)
        e = datetime.datetime.combine(end_date, self.end.time())
        start = self.start.tzinfo.localize(s)
        end = self.start.tzinfo.localize(e)
        ev = type(self)(self.id, start, end, self.title, self.status, self.cal_id, *args, **kwargs)
        return ev

    def full_list(self) -> str:
        msg = []
        msg.append(f"=== {self.title} ===")
        msg.append(f"  time: {self.format_duration()}")
        if self.attendees:
            msg.append("  attendees:")
            for attendee in self.attendees:
                msg.append(f"    * {attendee.name} ({attendee.mail})")
        return "\n".join(msg)


class EventSource:

    def __init__(self, name: str, *args: Any, **kwargs: Dict[str, Any]) -> None:
        self.name = name

    def get_events(self, start_date: MaybeDate = None, end_date: MaybeDate = None) -> Sequence[Event]: ...


class TbEvent(Event):

    teams_link_pattern = re.compile("https://teams.microsoft.com/[-/a-zA-Z0-9%?&_.=]+")

    def __init__(self, id: str, start: DateTime, end: DateTime, title: str,
            status: CalendarStatus, cal_id: str, recurrence: Recurrence,
            rule: Optional[RecurrenceRule] = None, attendees: MaybeAttendees = None,
            properties: Optional[TbProperties] = None) -> None:
        self.cal_id: str
        super().__init__(id, start, end, title, status, cal_id, attendees=attendees)
        self.recurrence = recurrence
        self.recurrence_rule = rule
        if properties:
            self.desc = properties.desc
            self.properties = properties
        else:
            self.desc = ""
            self.properties = None
        self.video_link = self.get_video_link(self.desc)
        self.meeting_type: MeetingType
        if self.video_link:
            if "microsoft" in self.video_link:
                self.meeting_type = MeetingType.TEAMS
            else:
                self.meeting_type = MeetingType.ZOOM
        else:
            self.meeting_type = MeetingType.NORMAL


    def with_date(self, date: Date, *args, **kwargs) -> "Event":
        kwargs = {"recurrence": self.recurrence,
                "rule": self.recurrence_rule}
        return super().with_date(date, **kwargs)

    @classmethod
    def get_video_link(cls, desc: str) -> MaybeString:
        if not desc:
            return None
        m = cls.teams_link_pattern.search(desc)
        if m:
            return m.group()


class TbEventSource(EventSource):

    query_by_time = """
    SELECT
      cal_id,
      id,
      DATETIME(ev.event_start/1000000, 'unixepoch') AS start,
      DATETIME(ev.event_end/1000000, 'unixepoch') AS end,
      ev.event_start_tz,
      ev.event_end_tz,
      title,
      ical_status AS state,
      recurrence_id,
      recurrence_id_tz
    FROM
      cal_events AS ev
    WHERE
      title IS NOT NULL
      AND (
          (DATETIME(event_start/1000000, 'unixepoch') <= ?
           AND DATETIME(event_end/1000000, 'unixepoch') >= ?)
          OR (DATETIME(event_start/1000000, 'unixepoch') >= ?
              AND DATETIME(event_start/1000000, 'unixepoch') <= ?)
          OR (DATETIME(event_end/1000000, 'unixepoch') >= ?
              AND DATETIME(event_end/1000000, 'unixepoch') <= ?)
      )
    ORDER BY
      DATETIME(event_start/1000000, 'unixepoch')
    """

    query_by_id = """
    SELECT
      cal_id,
      id,
      DATETIME(ev.event_start/1000000, 'unixepoch') AS start,
      DATETIME(ev.event_end/1000000, 'unixepoch') AS end,
      ev.event_start_tz,
      ev.event_end_tz,
      ev.title,
      ical_status AS state,
      recurrence_id,
      recurrence_id_tz
    FROM
      cal_events AS ev
    WHERE
      cal_id = ?
      AND id = ?
      AND title IS NOT NULL
    ORDER BY
      DATETIME(event_start/1000000, 'unixepoch')
    """

    deleted_query = """
    SELECT
      cal_id,
      id,
      DATETIME(time_deleted/1000000, 'unixepoch', 'localtime') AS ts,
      recurrence_id
    FROM
      cal_deleted_items
    """

    attendee_query = """
    SELECT
      icalString
    FROM
      cal_attendees
    WHERE
      cal_id = ?
      AND item_id = ?
    """

    properties_query = """
    SELECT
      key, value
    FROM
      cal_properties
    WHERE
      cal_id = ?
      AND item_id = ?
    """

    cn_pattern = re.compile("(?:CN=)(?P<name>.*?)(?=;)")
    mailto_pattern = re.compile("(?:mailto:)(?P<mail>.*?)(?=(;|$))")

    def __init__(self, name: str, profile_name: str) -> None:
        super().__init__(name)
        self.dir = Path(os.path.expanduser("~"), ".thunderbird", f"{profile_name}.default", "calendar-data")

    def create_tmp_file(self, file: str) -> Path:
        tmp_file = Path("/tmp") / f"qtile-calendar-{file}-{random.randint(1000000, 9999999)}.sqlite"
        shutil.copy(self.dir / file, tmp_file)
        return tmp_file

    def get_connection(self, path: Path) -> sqlite3.Connection:
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        return con

    def get_deleted_events(self):
        tmp_file = self.create_tmp_file("deleted.sqlite")
        items = {}
        try:
            with self.get_connection(tmp_file) as con:
                for row in con.execute(self.deleted_query):
                    items[(row["cal_id"], row["id"])] = {k: row[k] for k in row.keys()}
        finally:
            tmp_file.unlink()
        return items

    def get_attendees(self, cal_id: str, item_id: str, con: sqlite3.Connection) -> Generator["TbAttendee", None, None]:
        cursor = con.execute(self.attendee_query, [cal_id, item_id])
        for row in cursor:
            ical_string = row["icalString"]
            if ical_string:
                text = "".join(s.strip() for s in ical_string.split("\n"))
                m_name = self.cn_pattern.search(text)
                m_mail = self.mailto_pattern.search(text)
                name = m_name.group("name") if m_name else None
                mail = m_mail.group("mail") if m_mail else None
                yield TbAttendee(name, mail)

    def get_properties(self, cal_id: str, item_id: str, con: sqlite3.Connection) -> Optional[TbProperties]:
        cursor = con.execute(self.properties_query, [cal_id, item_id])
        data = { row["key"]: row["value"] for row in cursor}
        kwargs = {
            "desc": data.get("DESCRIPTION"),
            "busy": data.get("X-EAS-BUSYSTATE"),
            "meeting_status": data.get("X-EAS-MEETINGSTATUS"),
            "response_type": data.get("X-EAS-RESPONSETYPE"),
        }
        return TbProperties(**kwargs)

    def get_events(self, start_date: MaybeDate = None, end_date: MaybeDate = None) -> Sequence[Event]:
        deleted_events = self.get_deleted_events()
        deleted = lambda e: (e.cal_id, e.id) in deleted_events and (not e.recurrence or deleted_events[e]["recurrence_id"] != e.recurrence.id)
        tmp_file = self.create_tmp_file("local.sqlite")
        if not start_date:
            start_date = datetime.date.today()
        if not end_date:
            end_date = start_date + datetime.timedelta(days=1)
        try:
            with self.get_connection(tmp_file) as con:
                return sorted((event for event in self.load_all(start_date, end_date, con) if not deleted(event)), key=lambda e: e.start)
        finally:
            tmp_file.unlink()

    def load_all(cls, start_date: Date, end_date: Date, con: sqlite3.Connection) -> Generator["Event", None, None]:
        yield from cls.load_non_recurring_events(start_date, end_date, con)
        yield from cls.load_recurring_events(start_date, end_date, con)

    @staticmethod
    def exhaust_rows(rows: Sequence[sqlite3.Row]) -> sqlite3.Row:
        if len(rows) == 1:
            return rows[0]
        rs = [r for r in rows if any(r["title"].startswith(p) for p in ("WG:", "FW:", "Abgesagt:"))]
        if rs:
            return rs[0]
        else:
            return rows[0]

    def load_recurring_events(self, start_date: Date, end_date: Date,
            con: sqlite3.Connection) -> Generator["Event", None, None]:
        diff = (end_date - start_date).days
        weekdays = [Weekday.for_datetime(start_date + datetime.timedelta(days=i)) for i in range(diff+1)]
        for rule in RecurrenceRule.get_all_rules(con):
            cursor = con.execute(self.query_by_id, [rule.cal_id, rule.event_id])
            row = self.exhaust_rows(cursor.fetchall())
            event = self.from_row(row, con, rule)
            if event.start.date() > end_date:
                continue
            start_dt = datetime.datetime.fromordinal(start_date.toordinal()).astimezone(TZ_EUROPE_BERLIN)
            if rule.matches(event, compare_dt=start_dt):
                yield event.with_date(start_date)

    def from_row(self, row: sqlite3.Row, con: sqlite3.Connection, rule: Optional[RecurrenceRule] = None) -> "Event":
        recurrence = Recurrence(row["recurrence_id"], row["recurrence_id_tz"])
        state: MaybeString
        if "ical_status" in row:
            state = row["ical_status"]
        elif "state" in row:
            state = row["state"]
        else:
            state = None
        cal_id = row["cal_id"]
        item_id = row["id"]
        start_tz = row["event_start_tz"]
        end_tz = row["event_end_tz"]
        attendees = tuple(self.get_attendees(cal_id, item_id, con))
        properties = self.get_properties(cal_id, item_id, con)
        args = dict(
            id=row["id"],
            cal_id=row["cal_id"],
            start=zoned(row["start"], start_tz),
            end=zoned(row["end"], end_tz),
            title=row["title"],
            status=CalendarStatus.by_name(state),
            recurrence=recurrence,
            rule=rule,
            attendees=attendees,
            properties=properties,
        )
        event = TbEvent(**args)
        return event

    def load_non_recurring_events(self, start_date: Date, end_date: Date,
            con: sqlite3.Connection) -> Generator["Event", None, None]:
        start = to_utc(start_date)
        end = to_utc(end_date)
        cursor = con.execute(self.query_by_time, [start, end] * 3)
        for row in cursor:
            yield self.from_row(row, con)


class Calendar:

    def __init__(self, start: int = 0, end: int = 1,
            only_upcoming: bool = True,
            on_event_added: Optional[Callable[[Event], None]] = None,
            on_event_modified: Optional[Callable[[Event, Event], None]] = None,
            on_event_deleted: Optional[Callable[[Event], None]] = None,
            timezone: datetime.tzinfo = TZ_EUROPE_BERLIN
            ) -> None:
        self.sources: List[EventSource] = []
        self.date = datetime.date.today()
        self._start = start
        self._end = end
        self.on_event_added = on_event_added
        self.on_event_modified = on_event_modified
        self.on_event_deleted = on_event_deleted
        self._events: List[Event] = []
        self.only_upcoming = only_upcoming
        self.timezone = timezone

    @property
    def events(self) -> Sequence[Event]:
        fn = self._now_filter()
        return [e for e in self._events if fn(e)]

    @property
    def start(self) -> Date:
        return datetime.date.today() + datetime.timedelta(days=self._start)

    @property
    def end(self) -> Date:
        return datetime.date.today() + datetime.timedelta(days=self._end)

    @start.setter
    def start(self, val: int) -> None:
        if val != self._start:
            self._start = val
            self.update_events()

    @end.setter
    def end(self, val: int) -> None:
        if val != self._end:
            self._end = val
            self.update_events()

    def add_source(self, source: EventSource) -> None:
        self.sources.append(source)

    def _now_filter(self) -> Callable[[Event], bool]:
        now = self.timezone.localize(datetime.datetime.now())
        if self.only_upcoming:
            return lambda e: e.end > now
        else:
            return lambda _: True

    def get_all_events(self, start_date: MaybeDate = None, end_date: MaybeDate = None) -> Generator[Event, None, None]:
        for source in self.sources:
            for event in source.get_events(start_date, end_date):
                yield event

    def _load_events(self, fire_hooks: bool = False) -> List[Event]:
        prev_events = self._events
        prev_dict = {e: e for e in self._events}
        dates = {"start_date": self.start, "end_date": self.end}
        fn = self._now_filter()
        events = [e for s in self.sources for e in s.get_events(**dates) if fn(e)]
        sort_fn = lambda e: e.start
        new_events = sorted((e for e in events if e not in prev_events), key=sort_fn)
        if fire_hooks and self.on_event_added:
            for e in new_events:
                self.on_event_added(e)

        if fire_hooks and self.on_event_modified:
            old_events = sorted((e for e in events if e in prev_events), key=sort_fn)
            for e in old_events:
                if prev_dict[e] != e:
                    self.on_event_modified(prev_dict[e], e)
        for e in events:
            prev_dict[e] = e
        return sorted((e for e in prev_dict.values() if self.in_range(e)), key=sort_fn)

    def update_events(self) -> None:
        self._events = self._load_events(fire_hooks=True)

    def in_range(self, event: Event) -> bool:
        start = event.start.date()
        end = event.end.date()
        return (self.start <= start < self.end
                or self.start <= end < self.end
                or (start < self.start and end >= self.end))

    def __iter__(self) -> Generator[Event, None, None]:
        return sorted

    def short_list(self) -> str:
        events = [(event.title, event.format_duration()) for event in self.events]
        max_len = max(len(el[0]) for el in events)
        return "\n".join(f"{ev[0]:{max_len}} –  {ev[1]}" for ev in events)

    def full_list(self) -> str:
        return "\n\n".join(event.full_list() for event in self.events)
