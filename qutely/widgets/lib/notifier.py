import random
import subprocess as sub
from typing import Any, Callable, Optional, Union, cast


MaybeString = Optional[str]
MaybeInt = Optional[int]


class Notifier:
    low = "low"
    normal = "normal"
    critical = "critical"

    def notify(self, summary: str, msg: str, level: str = "normal", *params: Any) -> None:
        ...


class Dunstify:
    def __init__(
        self,
        low_timeout: MaybeInt = None,
        normal_timeout: MaybeInt = None,
        critical_timeout: MaybeInt = None,
        app: MaybeString = None,
    ) -> None:
        self.ids = dict(
            zip(
                [Notifier.low, Notifier.normal, Notifier.critical],
                [random.randint(10000000, 99999999) for x in range(3)],
            )
        )
        self.timeouts = {
            Notifier.low: low_timeout,
            Notifier.normal: normal_timeout,
            Notifier.critical: critical_timeout,
        }
        self.app = app

    def notify(self, summary: str, msg: str, level: str = Notifier.normal, *params: Any) -> None:
        timeout: Optional[float]
        level = level if level in (Notifier.low, Notifier.normal, Notifier.critical) else Notifier.normal
        id = self.ids[level]
        timeout = self.timeouts[level]
        msg_ = msg % params if params else msg
        args = ["dunstify", "-r", str(id), "-u", level]
        if timeout:
            args.extend(["-t", str(timeout)])
        if self.app:
            args.extend(["-a", self.app])
        args.extend([summary, msg_])
        sub.run(args, timeout=2, text=True, shell=False)
