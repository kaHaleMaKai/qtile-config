from tkinter import Tk, Menu
from multiprocessing import Process, Pipe
from typing import List, Sequence, Any, Union, Generator, Optional, Callable, Dict


MenuEntries = Union[Dict[str, Any], Sequence[Any]]


class ContextMenu:

    def __init__(self, name: str, root: Tk, entries: MenuEntries, min_width: int = 1) -> None:
        self.app_name = name
        self.root = root
        self.menu = self.create_menu(self.root, entries)
        self.min_width = max(min_width, 1)

    def clickable_entry(self, fn: Optional[Callable[[], None]] = None) -> Callable[[], None]:

        def _fn():
            if fn:
                fn()
            self.menu.grid

        return _fn

    def _label(self, text: str) -> str:
        return f"{text:{self.min_width}}"

    def create_menu(self, parent: Union[Tk, Menu], entries: MenuEntries) -> Menu:
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
                if isinstance(entry, str):
                    menu.add_command(label=self._label(entry), command=self.clickable_entry())
                elif isinstance(entry, (list, tuple)):
                    if len(entry) != 2:
                        raise ValueError(f"wrong length of entry. expected: 2. got {len(entry)}")
                    if callable(entry[1]):
                        name, cmd = entry
                        if not isinstance(name, str):
                            raise ValueError(f"wrong type for label. expected: str. got {type(name)}")
                        menu.add_command(label=self._label(name), command=self.clickable_entry(cmd))
                    elif isinstance(entry[1], (list, tuple)):
                        name, more_entries = entry
                        submenu = self._create_menu_helper(menu, more_entries)
                        menu.add_cascade(label=self._label(name), menu=submenu)
        return menu

    def destroy(self, *_) -> None:
        self.root.destroy()

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
        self.root.mainloop()


class ContextRoot:

    def __init__(self) -> None:
        root = Tk(className="qtile-contextmenu-root")
        root.geometry("1x1+10000+10000")
        root.overrideredirect(True)
        root.option_add('*tearOff', False)
        self.root = root
        self.menus: Dict[str, Menu] = {}
        self.min_width = max(min_width, 1)


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

    def clickable_entry(self, fn: Optional[Callable[[], None]] = None) -> Callable[[], None]:
        def _fn():
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
                if isinstance(entry, str):
                    menu.add_command(label=self._label(entry), command=self.clickable_entry())
                elif isinstance(entry, (list, tuple)):
                    if len(entry) != 2:
                        raise ValueError(f"wrong length of entry. expected: 2. got {len(entry)}")
                    if callable(entry[1]):
                        name, cmd = entry
                        if not isinstance(name, str):
                            raise ValueError(f"wrong type for label. expected: str. got {type(name)}")
                        menu.add_command(label=self._label(name), command=self.clickable_entry(cmd))
                    elif isinstance(entry[1], (list, tuple)):
                        name, more_entries = entry
                        submenu = self._create_menu_helper(menu, more_entries)
                        menu.add_cascade(label=self._label(name), menu=submenu)
        return menu

    def destroy(self, *_) -> None:
        self.root.destroy()

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
        self.root.mainloop()


# menu = ContextMenu("qalendar", min_width=12)
# entries = {
#         "a": None,
#         "b": lambda: print("hello"),
#         "submenu": {
#             "d": None,
#             "e": lambda: print("bye"),
#             "f": None
#             },
#         "attendees": ["q", "b", "c"]
#         }
# menu.initialize(entries)
# menu.show()
