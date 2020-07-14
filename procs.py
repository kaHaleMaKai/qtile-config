import os
import subprocess


class Proc:

    timeout = 2

    def __init__(self, *args, name=None, default_args=None, default_arg=None, stop=None, bg=False, shell=False):
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
            default_args = (default_arg, )
        else:
            default_args = tuple(default_args)
        return Proc(
            *self.args, *args,
            stop=stop if stop else self._stop,
            default_args=default_args
        )

    def __getitem__(self, *args):
        return self.derive(*args)

    def __call__(self, *args):
        if self.bg:
            return self.run_in_bg(*args)
        else:
            return self.run(*args)

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

    def run(self, *args, timeout=None):
        proc_args = self.get_args(*args)
        timeout = timeout if timeout is not None else self.timeout
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


feh = Proc("feh", "--bg-fill", default_arg=os.path.expanduser("~/.wallpaper"))
setxkbmap = Proc("setxkbmap", default_args=("de", "deadacute"), shell=True)
unclutter = Proc("unclutter", "-root", "-idle", default_arg="3", bg=True)
polkit_agent = Proc("/usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1", bg=True)
xcompmgr = Proc("xcompmgr", bg=True)
compton = Proc("compton", bg=True)
xfce4_power_manager = Proc("xfce4-power-manager", bg=True)
screensaver = Proc("cinnamon-screensaver", bg=True)
screensaver_cmd = Proc("cinnamon-screensaver-command", default_arg="--lock", name="lock cmd")
xss_lock = Proc("xss-lock", "-l", "-v", "--", default_args=(screensaver_cmd.get_args()), bg=True)
volti = Proc("volti", bg=True)
shiftred = Proc("shiftred", default_arg="load-config")
network_manager = Proc("nm-applet", bg=True)
rofi_pass = Proc("rofi-pass")
toggle_unclutter = Proc("toggle-unclutter")
opacity = Proc("transset", "--actual")
rofi = Proc("rofi", "-i", "-show")
rofi_pass = Proc("rofi-pass")
terminal = Proc("xfce4-terminal", default_args=["-e", "zsh"])
rofimoji = Proc("rofimoji")
volume = Proc("configure-volume")
systemctl = Proc("systemctl", "--user", "restart")
pause_dunst = Proc("killall", "-SIGUSR1", "dunst")
resume_dunst = Proc("killall", "-SIGUSR2", "dunst")
dunstify = Proc("dunstify")
bluetooth = Proc("blueman-applet", bg=True)
