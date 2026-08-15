from __future__ import annotations

import asyncio
import sys

from online.asyncio_runner import run


def test_run_uses_selector_loop_for_async_postgres_on_windows():
    async def current_loop_type():
        return type(asyncio.get_running_loop())

    loop_type = run(current_loop_type())

    if sys.platform == "win32":
        assert loop_type is asyncio.SelectorEventLoop
