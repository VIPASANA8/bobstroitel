from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(tmp_path_factory, name, module, env_overrides=None):
    port = _free_port()
    database = tmp_path_factory.mktemp(name) / "online.sqlite3"
    env = os.environ.copy()
    env.update({
        "POKER8_ENV": "development",
        "POKER8_COORDINATOR_ENABLED": "1",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
        "POKER8_DEV_PROFILES": "101:Dev Player,202:Observer",
    })
    env.update(env_overrides or {})
    log_path = database.with_suffix(".log")
    log_handle = log_path.open("w+", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "tests.e2e.run_server", module, "--host", "127.0.0.1", "--port", str(port)],
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


@pytest.fixture(scope="session")
def cash_server(tmp_path_factory):
    raw_url = os.environ.get("POKER8_CASH_TEST_DATABASE_URL", "")
    url = make_url(raw_url) if raw_url else None
    if url is None or not (
        url.drivername == "postgresql+psycopg"
        and url.host in {"localhost", "127.0.0.1", "::1"}
        and url.port == 5433 and url.database == "poker8_test"
        and not url.query
    ):
        pytest.fail("Set POKER8_CASH_TEST_DATABASE_URL to the local postgres_test service")

    schema = "cash_e2e_" + uuid4().hex
    bounded_url = url.update_query_dict({"connect_timeout": "5"})
    admin_url = bounded_url.render_as_string(hide_password=False)
    engine = create_engine(admin_url)
    schema_created = False
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        schema_url = bounded_url.update_query_dict({"options": f"-csearch_path={schema}"})
        yield from _serve(tmp_path_factory, "e2e-cash", "tests.e2e.server:app", {
            "POKER8_CASH_MODE": "mock",
            "POKER8_DATABASE_URL": schema_url.render_as_string(hide_password=False),
        })
    finally:
        if not schema.startswith("cash_e2e_") or len(schema) != 41:
            raise RuntimeError("unsafe cash E2E schema cleanup target")
        if schema_created:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
