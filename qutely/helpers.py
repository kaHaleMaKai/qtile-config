from __future__ import annotations

import asyncio
from typing import Any, Awaitable

from libqtile.lazy import lazy, LazyCall


def lazy_coro(f: Awaitable[Any], *args: Any, **kwargs: Any) -> LazyCall:
    return lazy.function(
        lambda qtile: qtile.call_soon(asyncio.create_task, f(qtile, *args, **kwargs))
    )
