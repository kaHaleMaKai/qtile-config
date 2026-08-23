from __future__ import annotations

from libqtile.config import DropDown, ScratchPad


def get_scratchpads() -> list[ScratchPad]:
    return [
        ScratchPad(
            "signal_scratchpad",
            [
                DropDown(
                    "signal",
                    ["signal-desktop"],
                    opacity=1,
                    on_focus_lost_hide=False,
                    x=0.05,
                    y=0,
                    width=0.9,
                    height=0.9,
                ),
            ],
            single=True,
        ),
        ScratchPad(
            "ding_scratchpad",
            [
                DropDown(
                    "ding",
                    ["ding"],
                    opacity=1,
                    on_focus_lost_hide=True,
                    x=0.05,
                    y=0,
                    width=0.9,
                    height=0.9,
                ),
            ],
            single=True,
        ),
        ScratchPad(
            "telegram_scratchpad",
            [
                DropDown(
                    "telegram",
                    ["telegram-desktop"],
                    opacity=1,
                    on_focus_lost_hide=True,
                    x=0.05,
                    y=0,
                    width=0.9,
                    height=0.9,
                ),
            ],
            single=True,
        ),
        ScratchPad(
            "neochat_scratchpad",
            [
                DropDown(
                    "neochat",
                    ["neochat"],
                    opacity=1,
                    on_focus_lost_hide=True,
                    x=0.05,
                    y=0,
                    width=0.9,
                    height=0.9,
                ),
            ],
            single=True,
        ),
    ]
