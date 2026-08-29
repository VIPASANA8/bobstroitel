from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(tmp_path_factory, name, module):
    port = _free_port()
    database = tmp_path_factory.mktemp(name) / "online.sqlite3"
    env = os.environ.copy()
    env.update({
        "POKER8_ENV": "development",
        "POKER8_COORDINATOR_ENABLED": "1",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
        "POKER8_DEV_PROFILES": "101:Dev Player,202:Observer",
    })
    log_path = database.with_suffix(".log")
    log_handle = log_path.open("w+", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", str(port)],
        cwd=os.getcwd(), env=env, stdout=log_handle, stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        # Six bot-only rooms seeding into one sqlite process: on a cold cache
        # the app has taken past 30s to answer, and a browser suite that fails
        # for that reason teaches people to ignore it.
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"{base_url}/", timeout=1, trust_env=False)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        else:
            log_handle.flush()
            raise RuntimeError(f"E2E server did not start (exit={process.poll()}): {log_path.read_text()[-4000:]}")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log_handle.close()


@pytest.fixture(scope="session")
def online_server(tmp_path_factory):
    yield from _serve(tmp_path_factory, "e2e", "tests.e2e.server:app")


@pytest.fixture(scope="session")
def spectator_server(tmp_path_factory):
    """Every bot active, so the lobby seeds its real 4/5/6-player rooms."""
    yield from _serve(tmp_path_factory, "e2e-spectator", "tests.e2e.server_all_bots:app")
