import os
import subprocess
import asyncio
from abc import ABC, abstractmethod
from random import randint
from functools import wraps
from asyncio.subprocess import (
    create_subprocess_exec as new_proc,
    create_subprocess_shell as new_shell,
    PIPE,
    Process,
)
from typing import Awaitable, Optional, Iterable, TypedDict, Union, Any

from libqtile.log_utils import logger


Number = Union[int, float]
MaybeInt = Optional[int]
MaybeNumber = Optional[int]
MaybeStr = Optional[str]


class ProcMsg(TypedDict):
    cmd: str
    msg: MaybeStr
    rc: MaybeInt
    duration: Number


class Dunstifier:

    low_urgency = "low"
    normal_urgency = "normal"
    high_urgency = "critical"

    def __init__(
        self,
        name: MaybeStr = None,
        id: MaybeInt = None,
        timeout: MaybeNumber = None,
        replace: bool = True,
    ) -> None:
        self.id = id or randint(1_000_000, 10_000_000)
        self.name = name
        self.timeout = timeout
        self.replace = replace

    async def debug(
        self,
        msg: str,
        title: MaybeStr = None,
        timeout: MaybeNumber = None,
        replace: Optional[bool] = None,
    ) -> None:
        await self.send(msg, self.low_urgency, title, timeout, replace)

    async def info(
        self,
        msg: str,
        title: MaybeStr = None,
        timeout: MaybeNumber = None,
        replace: Optional[bool] = None,
    ) -> None:
        await self.send(msg, self.normal_urgency, title, timeout, replace)

    async def error(
        self,
        msg: str,
        title: MaybeStr = None,
        timeout: MaybeNumber = None,
        replace: Optional[bool] = None,
    ) -> None:
        await self.send(msg, self.high_urgency, title, timeout, replace)

    async def send(
        self,
        msg: str,
        urgency: str,
        title: MaybeStr = None,
        timeout: MaybeNumber = None,
        replace: Optional[bool] = None,
    ) -> None:
        title = title or self.name or ""
        cmd = [
            "dunstify",
            "-u",
            urgency,
        ]
        replace_ = self.replace if replace is None else replace
        if replace_:
            cmd.extend(["-r", str(self.id)])
        cmd.extend([title, msg])
        timeout = timeout or self.timeout
        if timeout:
            # convert timeout to milliseconds
            cmd.extend(["-t", str(timeout * 1000)])
        proc = await new_proc(*cmd)
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
            if proc.returncode is None:
                await asyncio.wait_for(proc.terminate(), timeout=10)
        except asyncio.TimeoutError:
            logger.error(f"timed out while calling dunstify with msg '{msg}'")

    async def close(self) -> None:
        proc = await new_proc("dunstify", "-C", str(self.id))
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
            if proc.returncode is None:
                await asyncio.wait_for(proc.terminate(), timeout=10)
        except asyncio.TimeoutError:
            logger.error(f"timed out while calling dunstify --close with id {self.id}")


class Proc(ABC):

    default_timeout = 60
    min_timeout = 0.01
    default_dunstifier = Dunstifier(replace=False, name="command has failed")
    rc_timed_out = -1
    rc_error = -2
    timeout_msg = "timed out while waiting for the process to finish. terminating it"

    args: tuple[str, ...]

    def __new__(
        cls,
        *args: str,
        timeout: MaybeInt = None,
        error_title: MaybeStr = None,
        dunstifier: Optional[Dunstifier] = None,
        shell: bool = False,
        bg: bool = False,
        env: Optional[dict[str, str]] = None,
    ) -> "Proc":
        if not dunstifier:
            dunstifier = Dunstifier(replace=False, name=error_title) if error_title else None
        if bg:
            return BackgroundProc(*args, shell=shell, dunstifier=dunstifier, env=env)
        else:
            return AsyncProc(*args, timeout=timeout, shell=shell, dunstifier=dunstifier, env=env)

    @abstractmethod
    def clone(self) -> "Proc":
        return self

    async def run(self) -> None:
        if self.is_running:
            raise ValueError(
                f"process {self} already running. either wait for termination, or call Proc.clone() to get a new instance"
            )
        logger.debug(f"running {self}")
        loop = asyncio.get_running_loop()
        start = loop.time()
        try:
            res = await self._run_async()
            logger.debug(f"proc {self} has returned with rc={res['rc']}")
            duration = loop.time() - start
            res["duration"] = duration
            if res["rc"] == 0:
                logger.debug(
                    f"command 'res['cmd']' finished successfully in {res['duration']:2f}s"
                )
                return
            title: MaybeStr
            if res["rc"] == Proc.rc_timed_out:
                msg = f"command '{res['cmd']}' has timed out after {res['duration']:.2f}s"
                title = "command has timed out"
            else:
                if res["rc"] == Proc.rc_error:
                    rc_msg = "failed"
                else:
                    rc_msg = f"exited with rc={res['rc']}"
                msg = f"command '{res['cmd']}' {rc_msg}. for details, check the log"
                title = None
            await self.dunstifier.error(msg, title=title)
        except Exception as e:
            logger.error(e)
            logger.error(f"command '{res['cmd']}' exited with rc={res['rc']}. {res['msg']}")

    @property
    @abstractmethod
    def is_running(self) -> bool:
        return False

    @property
    def cmd(self) -> str:
        return " ".join(self.args)

    @property
    @abstractmethod
    def returncode(self) -> MaybeInt:
        return None

    @classmethod
    async def await_many(cls, *aws: Union["Proc", Awaitable[Any]]) -> None:

        res = await asyncio.gather(
            *tuple(aw.run() if isinstance(aw, Proc) else aw for aw in aws),
            return_exceptions=True,
        )
        for e in res:
            if isinstance(e, Exception):
                await Proc.default_dunstifier.error(msg=str(e))


class BackgroundProc(Proc):
    def __init__(
        self,
        *args: str,
        shell: bool = False,
        dunstifier: Optional[Dunstifier] = None,
        env: Optional[dict[str, str]] = None,
        **_: Any,
    ) -> None:
        self.args = args
        self._is_running = False
        self._err: MaybeStr = None
        self._rc = 0
        self.dunstifier = dunstifier or Proc.default_dunstifier
        self.shell = shell
        self.proc: Optional[subprocess.Popen[str]] = None
        self.env = env
        logger.debug(f"created {self}")

    def __new__(cls, *args: Any, **kwargs: Any) -> "AsyncProc":
        proc = object.__new__(cls)
        return proc

    def __str__(self) -> str:
        return f"<BackgroundProc['{self.args}', shell={self.shell}]>"

    def clone(self) -> "Proc":
        return BackgroundProc(*self.args, shell=self.shell, dunstifier=self.dunstifier)

    async def _run_async(self) -> ProcMsg:
        if self.shell:
            cmd = " ".join(self.args)
        else:
            cmd = self.args
        try:
            self.proc = subprocess.Popen(cmd, shell=self.shell, text=True, env=self.env)
            self._is_running = True
        except Exception as e:
            self._err = str(e)
            self._rc = Proc.rc_error
        return {"cmd": self.cmd, "msg": self._err, "rc": self.returncode}

    def poll(self) -> MaybeInt:
        return self.proc.poll() if self.proc else None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def returncode(self) -> MaybeInt:
        return self._rc


class AsyncProc(Proc):
    def __new__(cls, *args: Any, **kwargs: Any) -> "AsyncProc":
        proc = object.__new__(cls)
        return proc

    def __init__(
        self,
        *args: str,
        timeout: MaybeNumber = None,
        dunstifier: Optional[Dunstifier] = None,
        shell: bool = False,
        env: Optional[dict[str, str]] = None,
        **_: Any,
    ) -> None:
        self.args = args
        self.proc: Optional[Process] = None
        self._timeout = timeout
        self.dunstifier = dunstifier or self.default_dunstifier
        self.shell = shell
        self.env = env

    def clone(self) -> "Proc":
        return BackgroundProc(
            *self.args, shell=self.shell, timeout=self.timeout, dunstifier=self.dunstifier
        )

    def __str__(self) -> str:
        return f"<AsyncProc['{self.args}', shell={self.shell}]>"

    @property
    def timeout(self) -> Number:
        timeout = self._timeout or self.default_timeout
        return self.calc_timeout(timeout)

    @classmethod
    def calc_timeout(cls, timeout: Number) -> Number:
        return timeout if timeout > cls.min_timeout else cls.min_timeout

    @property
    def returncode(self) -> MaybeInt:
        if not self.proc:
            return None
        return self.proc.returncode

    async def _run_async(self) -> ProcMsg:
        if self.shell:
            self.proc = await new_shell(
                " ".join(self.args), stdout=PIPE, stderr=PIPE, env=self.env
            )
        else:
            self.proc = await new_proc(*self.args, stdout=PIPE, stderr=PIPE, env=self.env)
        loop = asyncio.get_running_loop()
        start = loop.time()
        res: ProcMsg = {"cmd": self.cmd, "msg": None, "rc": None}
        try:
            await asyncio.wait_for(self.proc.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            res["msg"] = self.timeout_msg
            res["rc"] = self.rc_timed_out
            return res
        diff = loop.time() - start
        remaining = self.calc_timeout(self.timeout - diff)
        if self.returncode is None:
            try:
                await asyncio.wait_for(self.proc.terminate(), timeout=remaining)
            except asyncio.TimeoutError:
                pass
            res["msg"] = self.timeout_msg
            res["rc"] = self.rc_timed_out
            return res
        res["rc"] = self.returncode
        diff = loop.time() - start
        remaining = self.calc_timeout(self.timeout - diff)
        try:
            stdout, stderr = await asyncio.wait_for(self.proc.communicate(), timeout=remaining)
        except asyncio.TimeoutError:
            res["msg"] = self.timeout_msg
            res["rc"] = self.rc_timed_out
            return res
        if not stdout and not stderr:
            return res
        elif not stdout:
            msg = stderr.decode()
        elif not stderr:
            msg = stdout.decode()
        else:
            msg = "stdout: [{stdout.decode()}]. stderr: [{stderr.decode()}]"
        res["msg"] = msg
        return res

    @property
    def pid(self) -> MaybeInt:
        return self.proc.pid

    def __repr__(self) -> str:
        return str(self)

    @property
    def is_running(self) -> bool:
        if not self.proc:
            return False
        return self.returncode is None


class SyncProc:

    timeout = 2

    def __init__(
        self,
        *args,
        name=None,
        default_args=None,
        default_arg=None,
        stop=None,
        bg=False,
        shell=False,
    ):
        if default_arg and default_args:
            raise ValueError("specify either of 'default_arg' or 'default_args'")
        if default_arg:
            self.default_args = (default_arg,)
        elif default_args:
            self.default_args = tuple(default_args)
        else:
            self.default_args = ()
        self._stop = stop
        self.name = name if name else args[0]
        self.args = args
        self.bg = bg
        self.shell = shell

    def derive(self, *args, name=None, stop=None, default_arg=None, default_args=None):
        if not default_arg and not default_args:
            default_args = self.default_args
        elif default_arg:
            default_args = (default_arg,)
        else:
            default_args = tuple(default_args)
        return SyncProc(
            *self.args,
            *args,
            stop=stop if stop else self._stop,
            default_args=default_args,
        )

    def __getitem__(self, *args):
        return self.derive(*args)

    def __call__(self, *args, **kwargs):
        if self.bg:
            return self.run_in_bg(*args, **kwargs)
        else:
            return self.run(*args, **kwargs)

    def get_args(self, *args):
        extra_args = args if args else self.default_args
        return (*self.args, *extra_args)  # NOQA

    def run_in_bg(self, *args):
        proc_args = self.get_args(*args)
        print(f"running in bg: {proc_args}")
        try:
            subprocess.Popen(proc_args)
        except Exception as e:
            print(f"error while executing backgrounded command {[proc_args]}: {e.message}")

    def run(self, *args, timeout=-1):
        proc_args = self.get_args(*args)
        timeout = timeout if timeout != -1 else self.timeout
        print(f"running {proc_args}")
        try:
            p = subprocess.run(proc_args, timeout=timeout, text=True, shell=self.shell)
        except subprocess.TimeoutExpired as e:
            print(f"timeed out while waiting for command {proc_args}: ", e.message)
            return False
        if not p.returncode:
            return True
        else:
            print(f"got rc={p.returncode} while running command {proc_args}")
            print(f"  stdout: {p.stdout}")
            print(f"  stderr: {p.stderr}")
            return False

    def stop(self):
        self._stop()

    def __str__(self):
        return f"<Proc {self.name}>"

    def __repr__(self):
        return str(self)


_feh = SyncProc("feh", "--bg-fill", default_arg=os.path.expanduser("~/.wallpaper"))
_setxkbmap = SyncProc("setxkbmap", default_args=("de", "deadacute"), shell=True)
_unclutter = SyncProc("unclutter", "-root", "-idle", default_arg="3", bg=True)
_polkit_agent = SyncProc(
    "/usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1", bg=True
)
_picom = SyncProc("picom", bg=True)
_xfce4_power_manager = SyncProc("xfce4-power-manager", bg=True)
_screensaver = SyncProc("cinnamon-screensaver", bg=True)
_screensaver_cmd = SyncProc("/home/lars/bin/lock-screen", name="lock_cmd")
# screensaver_cmd = Proc("cinnamon-screensaver-command", default_arg="--lock", name="lock cmd")
_xss_lock = SyncProc(
    "xss-lock", "-l", "-v", "--", default_args=(_screensaver_cmd.get_args()), bg=True
)
_volti = SyncProc("volti", bg=True)
_shiftred = SyncProc("shiftred", default_arg="load-config")
_network_manager = SyncProc("nm-applet", bg=True)
_rofi_pass = SyncProc("rofi-pass")
_toggle_unclutter = SyncProc("toggle-unclutter")
_opacity = SyncProc("transset", "--actual")
_rofi = SyncProc("rofi", "-i", "-show")
_rofi_pass = SyncProc("rofi-pass")
_terminal = SyncProc("xfce4-terminal", default_args=["-e", "zsh"])
_rofimoji = SyncProc("rofimoji")
_volume = SyncProc("configure-volume")
_systemctl_user = SyncProc("systemctl", "--user", "restart")
_pause_dunst = SyncProc("killall", "-SIGUSR1", "dunst")
_resume_dunst = SyncProc("killall", "-SIGUSR2", "dunst")
_bluetooth = SyncProc("blueman-applet", bg=True)
_nextcloud_sync = SyncProc("nextcloud", bg=True)
_signal_desktop = SyncProc("signal-desktop", bg=True)
_kde_connect = SyncProc("kdeconnect-indicator", bg=True)
_dunstify = SyncProc("dunstify")
_borg_backup = SyncProc("pkexec", "backup-with-borg", "start", bg=True)
_systemctl = SyncProc("pkexec", "systemctl", bg=True)
_fakecam = SyncProc("fakecam", default_args=["start"], bg=True)


feh = Proc("feh", "--bg-fill", os.path.expanduser("~/.wallpaper"))
unclutter = Proc("unclutter", "-root", "-idle", "3", bg=True)
toggle_unclutter = Proc("toggle-unclutter")
network_manager = Proc("nm-applet", bg=True)
xfce4_power_manager = Proc("xfce4-power-manager", bg=True)
screensaver = Proc("cinnamon-screensaver", bg=True)
polkit_agent = Proc("/usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1", bg=True)
screensaver_cmd = Proc("/home/lars/bin/lock-screen")
xss_lock = Proc("xss-lock", "-l", "-v", "--", " ".join(screensaver_cmd.args), bg=True)
shiftred = Proc("shiftred", "load-config")
start_dunst = Proc("systemctl", "--user", "restart", "dunst")
start_picom = Proc("systemctl", "--user", "restart", "picom")
bluetooth = Proc("blueman-applet", bg=True)
nextcloud_sync = Proc("nextcloud", bg=True)
kde_connect = Proc("kdeconnect-indicator", bg=True)
setxkbmap = Proc("setxkbmap", "de", "deadacute", shell=True)
fakecam = Proc("fakecam", "start", bg=True)
