import random
import string
from multiprocessing import Process
from multiprocessing.managers import BaseManager
from tkinter import Tk, Menu
from typing import List, Sequence, Any, Union, Generator, Optional, Callable, Dict


class ContextMenu:

    def __init__(self, app_name: str, min_width: int = 1) -> None:
        self.app_name = app_name
        root = Tk(className=f"qtile-menu-{app_name}")
        # root.geometry("1920x1080+10000+10000")
        root.geometry("1x1+10000+10000")
        root.overrideredirect(True)
        root.option_add('*tearOff', False)
        self.root = root
        self.menu: Optional[Menu] = None
        self.min_width = max(min_width, 1)
        self.is_destroyed = False

    # use Qtile instead of Any
    def clickable_entry(self, fn: Optional[Callable[[Any], None]] = None) -> Callable[[], None]:
        def _fn():
            print("something got clicked")
            if fn:
                fn()
            self.destroy()
        return _fn

    def _label(self, text: str) -> str:
        return f"{text:{self.min_width}}"

    def initialize(self, entries: Union[Dict[str, Any], Sequence[Any]]) -> None:
        self.menu = self._create_menu_helper(self.root, entries)

    def _create_menu_helper(self, parent: Union[Tk, Menu], entries: Union[Dict[str, Any], Sequence[Any]]) -> Menu:
        menu = Menu(parent)
        if isinstance(entries, dict):
            for key, val in entries.items():
                if val is None:
                    menu.activate
                    menu.add_command(label=self._label(key), command=self.clickable_entry())
                elif callable(val):
                    menu.add_command(label=self._label(key), command=self.clickable_entry(val))
                elif isinstance(val, (dict, list, tuple)):
                    submenu = self._create_menu_helper(menu, val)
                    menu.add_cascade(label=self._label(key), menu=submenu)
        elif isinstance(entries, (tuple, list)):
            for entry in entries:
                if not isinstance(entry, str):
                    raise TypeError(f"sequence in contextmenu entries may only contain strings. got {type(entry)}")
                menu.add_command(label=self._label(entry), command=self.clickable_entry())
        return menu

    def destroy(self, *_) -> None:
        print("destroying widgets")
        self.is_destroyed = True
        self.menu.destroy()
        self.root.destroy()
        print("all widgets destroyed")

    def show(self) -> None:
        if not self.menu:
            raise ValueError("menu not yet initialized")

        def show_the_menu():
            x = max(0, self.root.winfo_pointerx() - self.root.winfo_rootx() - 15)
            y = max(0, self.root.winfo_pointery() - self.root.winfo_rooty() - 15)
            self.root.attributes('-alpha', 0)
            self.root.wait_visibility()
            self.root.attributes('-alpha', 0)
            # self.root.geometry("+0+0")
            self.menu.post(x, y)

        for button in (1, 2, 3):
            self.root.bind(f"<Button-{button}>", self.destroy)
        self.root.after(0, show_the_menu)

        print("entering loop")
        self.root.mainloop()
        print("loop done")


class SpawnedMenu:

    def __init__(self, name: str, entries, min_width: int = 1):
        self.name = name
        self.entries = entries
        self.min_width = min_width
        self.proc: Process = None
        self.qtile = None
        self._sep = "_" + random.choices(string.ascii_letters, k=10) + _
        self._flat_entries: Dict[str, Callable[[Any], None]] = {}

    def show(self, qtile=None):

        def _fn():
            menu = ContextMenu(self.name, min_width=self.min_width)
            menu.initialize(self.entries)
            menu.show()

        self.qtile = qtile
        self.stop()
        self.proc = Process(target=_fn, name=self.name, daemon=True, args=())
        self.proc.start()

    def stop(self):
        if self.proc and self.proc.is_alive():
            self.proc.terminate()

    def join(self, timeout: Optional[float] = None) -> Optional[int]:
        if not self.proc:
            return 0
        if self.proc and self.proc.is_alive():
            self.proc.join(timeout=timeout)
        if self.proc.is_alive():
            return None
        return self.proc.exitcode

    def _create_menu_helper(self, parent: Union[Tk, Menu], entries: Union[Dict[str, Any], Sequence[Any]]) -> Menu:
        menu = Menu(parent)
        if isinstance(entries, dict):
            for key, val in entries.items():
                if val is None:
                    menu.activate
                    menu.add_command(label=self._label(key), command=self.clickable_entry())
                elif callable(val):
                    menu.add_command(label=self._label(key), command=self.clickable_entry(val))
                elif isinstance(val, (dict, list, tuple)):
                    submenu = self._create_menu_helper(menu, val)
                    menu.add_cascade(label=self._label(key), menu=submenu)
        elif isinstance(entries, (tuple, list)):
            for entry in entries:
                if not isinstance(entry, str):
                    raise TypeError(f"sequence in contextmenu entries may only contain strings. got {type(entry)}")
                menu.add_command(label=self._label(entry), command=self.clickable_entry())
        return menu


if __name__ == "__main__":
    entries = {
            "a": None,
            "b": lambda: print("hello"),
            "submenu": {
                "d": None,
                "e": lambda: print("bye"),
                "f": None
                },
            "attendees": ["q", "b", "c"]
            }
    # menu = ContextMenu("qalendar", min_width=12)
    # menu.initialize(entries)
    # menu.show()
    menu = SpawnedMenu("qalendar", entries, 12)
    menu.show()
    menu.join()
