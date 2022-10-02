import sqlite3
import pytest
import checkclock as cc
import datetime
from pathlib import Path
from freezegun import freeze_time
import locale
locale.setlocale(locale.LC_ALL, '')


def acc_and_inc():
    acc = []

    def inc(duration: int) -> None:
        acc.append(duration)

    return acc, inc


def get_yesterday() -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=1)


@pytest.fixture
def yesterday() -> datetime.date:
    return get_yesterday()


@pytest.fixture
def today() -> datetime.date:
    return datetime.date.today()


def test_noprmalize_color():
    c0 = "ffffff"
    c1 = "#ffffff"
    assert cc.normalize_color(c0) == c0
    assert cc.normalize_color(c1) == c0


def test_as_time_tuple():
    assert cc.as_time_tuple(0) == (0, 0, 0)
    assert cc.as_time_tuple(1) == (0, 0, 1)
    assert cc.as_time_tuple(61) == (0, 1, 1)
    assert cc.as_time_tuple(123) == (0, 2, 3)
    assert cc.as_time_tuple(3600 + 60 + 1) == (1, 1, 1)
    assert cc.as_time_tuple(49 * 3600 + 60 + 2) == (49, 1, 2)
    with pytest.raises(ValueError):
        cc.as_time_tuple(-1)


def test_as_hours_and_minutes():
    assert cc.as_hours_and_minutes(1) == "0:00"
    assert cc.as_hours_and_minutes(61) == "0:01"
    assert cc.as_hours_and_minutes(3600 + 10*60 + 17) == "1:10"
    assert cc.as_hours_and_minutes(37 * 3600 + 10*60 + 17) == "37:10"
    assert cc.as_hours_and_minutes(-(37 * 3600 + 10*60 + 17)) == "-37:10"


def test_as_time():
    assert cc.as_time(0) == datetime.time(second=0)
    assert cc.as_time(1) == datetime.time(second=1)
    assert cc.as_time(61) == datetime.time(minute=1, second=1)
    assert cc.as_time(2*3600 + 61) == datetime.time(hour=2, minute=1, second=1)
    with pytest.raises(ValueError):
        assert cc.as_time(24 * 3600)


def test_as_datetime():
    assert cc.as_datetime("2020-10-20", "12:34:45") == datetime.datetime.fromisoformat("2020-10-20 12:34:45")


def test_as_delta():
    val = 123456
    assert cc.as_delta(val) == datetime.timedelta(seconds=val)


def test_get_previous_date():
    assert cc.get_previous_date(0) == datetime.date.today()
    assert cc.get_previous_date(1) == (datetime.date.today() - datetime.timedelta(1))


class repeat:

    def __init__(self, *fns):
        if fns:
            self.fns = fns
        else:
            self.fns = ()

    def __call__(self):
        for fn in self.fns:
            fn()

    def __mul__(self, val: int):
        for i in range(val):
            self()

    def __rmul__(self, val: int):
        return self * val


class MemoryCheckclock(cc.Checkclock):

    def __init__(self, *args, **kwargs):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        super().__init__(*args, **kwargs)

    def get_connection(self):
        return self.con


def fixed(date: datetime.date):
    return freeze_time(date.isoformat())


def new_checkclock(tmp_path, date=None, *args, **kwargs):
    path = tmp_path / "test.sqlite"
    date = date if date else get_yesterday()
    new_kwargs = {**kwargs}
    new_kwargs.setdefault("working_days", "Mon-Sun")
    with fixed(date):
        checkclock = MemoryCheckclock(tick_length=1, path=path, avg_working_time=2,
                *args, **new_kwargs)
        checkclock.toggle_paused()
        assert checkclock.duration == 0
    return checkclock


@pytest.fixture
def checkclock(tmp_path):
    return new_checkclock(tmp_path)


def test_get_dates_from_schedule(checkclock: MemoryCheckclock, today, yesterday):
    with fixed(yesterday):
        2 * repeat(checkclock.tick)
        assert checkclock.duration == 2 * checkclock.tick_length
        assert list(checkclock.get_dates_from_schedule()) == []
    with fixed(today):
        assert list(checkclock.get_dates_from_schedule()) == [yesterday]


def test_next_day(checkclock: MemoryCheckclock, today, yesterday):
    with fixed(yesterday):
        assert checkclock.get_duration_from_db() == 0
        checkclock.tick()
        assert checkclock.duration == checkclock.tick_length
        checkclock.tick()
        assert checkclock.duration == 2 * checkclock.tick_length
        assert checkclock.get_duration_from_db() == 2

    with fixed(today):
        assert checkclock.today == yesterday
        checkclock.tick()
        assert checkclock.today == today
        assert checkclock.duration == checkclock.tick_length
        assert checkclock.get_duration_from_db() == 1


def test_get_balance(checkclock: MemoryCheckclock, today, yesterday):
    with fixed(yesterday) as ft:
        checkclock.tick()
        ft.tick()
        assert checkclock.duration == checkclock.tick_length
        63 * repeat(checkclock.tick, ft.tick)
        assert checkclock.duration == 64 * checkclock.tick_length
        assert checkclock.get_balance(days_back=0, min_duration=0) == 62

    with fixed(today) as ft:
        assert checkclock.today == yesterday
        4 * repeat(checkclock.tick, ft.tick)
        assert checkclock.today == today
        assert checkclock.duration == 4 * checkclock.tick_length
        assert checkclock.get_balance(days_back=0, min_duration=0) == 2
        assert checkclock.get_balance(days_back=1, min_duration=0) == 62


def test_hooks(tmp_path, yesterday):
    acc, inc = acc_and_inc()
    with fixed(yesterday):
        assert len(acc) == 0
        checkclock = new_checkclock(tmp_path, on_duration_update=inc)
        checkclock.tick()
        print(checkclock.working_days)
        assert acc[-1] == checkclock.tick_length
        19 * repeat(checkclock.tick)
        assert acc[-1] == 20 * checkclock.tick_length


def test_work_after_weekend(tmp_path, yesterday, today):
    acc, inc = acc_and_inc()
    work_day = today.strftime("%a")
    with fixed(yesterday):
        checkclock = new_checkclock(tmp_path, date=yesterday, working_days=work_day, on_duration_update=inc)
        wd = checkclock.working_days
        assert len(wd) == 1
        assert cc.Weekday.parse(work_day) == wd
        assert len(acc) == 1
        checkclock.tick()
        assert checkclock.duration == 0
        assert not checkclock.work_today
        assert checkclock.get_value(tick=False) == cc.Checkclock.not_working_state

    with fixed(today):
        # this automatically changes the state to working
        assert checkclock.get_value() != cc.Checkclock.not_working_state
        assert checkclock.work_today
        assert checkclock.work_today
        assert checkclock.duration == 1
        assert checkclock.work_today
