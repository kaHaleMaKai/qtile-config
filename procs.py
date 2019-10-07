import os
import subprocess


class Proc:

    def __init__(self, name, *args, **kwargs):
        if "default_arg" in kwargs and "default_args" in kwargs:
            raise ValueError("specify either of 'default_arg' or 'default_args'")
        if "default_arg" in kwargs:
            self.default_args = (kwargs["default_arg"],)
        elif "default_args" in kwargs:
            self.default_args = kwargs["default_args"]
        else:
            self.default_args = ()
        self._stop = kwargs.get("stop", lambda *args, **kwargs: None)
        self.name = name
        self.args = args

    def __getitem__(self, *args):
        return Proc(self.name, *self.args, *args, stop=self._stop, default_args=self.default_args)

    def __call__(self, *args):
        return self.run(*args)

    def get_args(self, *args):
        extra_args = args if args else self.default_args
        return (self.name, *self.args, *extra_args)  # NOQA

    def run(self, *args):
        proc_args = self.get_args(*args)
        try:
            print("running '%s'" % " ".join(proc_args))
            return subprocess.Popen(proc_args)
        except Exception as e:
            print("error while trying to start program '%s'" % " ".join(proc_args))
            print(e)

    def stop(self):
        self._stop()

    def __str__(self):
        args = (*self.args, *self.default_args)
        if args:
            return f"$({self.name} %s)" % " ".join(args)
        else:
            return f"$({self.name})"

    def __repr__(self):
        return str(self)


feh = Proc("feh", "--bg-fill", default_arg=os.path.expanduser("~/.wallpaper"))
setxkbmap = Proc("setxkbmap", default_args=("de", "deadacute"))
unclutter = Proc("unclutter", "-root")
xcompmgr = Proc("xcompmgr")
xfce4_power_manager = Proc("xfce4-power-manager")
screensaver = Proc("cinnamon-screensaver")
screensaver_cmd = Proc("cinnamon-screensaver-command", default_arg="--lock")
xss_lock = Proc("xss-lock", "-l", "-v", "--", default_args=(screensaver_cmd.get_args()))
volti = Proc("volti")
shiftred = Proc("shiftred", default_arg="load-config")
network_manager = Proc("nm-applet")
rofi_pass = Proc("rofi-pass")
toggle_unclutter = Proc("toggle-unclutter")
opacity = Proc("transset", "--actual")
rofi = Proc("rofi", "-i", "-show")
rofi_pass = Proc("rofi-pass")
terminal = Proc("xfce4-terminal", default_args=["-e", "zsh"])
rofimoji = Proc("rofimoji")
volume = Proc("configure-volume")
