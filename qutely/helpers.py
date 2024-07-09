from __future__ import annotations

import asyncio
from typing import Any, Awaitable

from libqtile.command import lazy
from libqtile.lazy import LazyCall


def lazy_coro(f: Awaitable[Any], *args: Any, **kwargs: Any) -> LazyCall:
    return lazy.function(
        lambda qtile: qtile.call_soon(asyncio.create_task, f(qtile, *args, **kwargs))
    )
