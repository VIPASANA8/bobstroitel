"""The login door is the only one anyone can knock on without a session."""
import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from online.ratelimit import RateLimited, WindowLimiter, caller


def test_a_window_lets_the_limit_through_and_then_stops():
    limiter = WindowLimiter(limit=3, seconds=60)
    for tick in range(3):
        limiter.check("1.2.3.4", now=tick)
    with pytest.raises(RateLimited) as refused:
        limiter.check("1.2.3.4", now=3)
    assert refused.value.status_code == 429
    # The caller is told when to come back rather than left guessing.
    assert int(refused.value.headers["Retry-After"]) > 0
    # ...and once the window has rolled past, they are let in again.
    limiter.check("1.2.3.4", now=61)


def test_one_caller_never_throttles_another():
    """The whole reason the client address has to be the real one.

    Behind a proxy every request carries the proxy's address, so a limiter that
    counted that would have one visitor locking out everybody at once.
    """
    limiter = WindowLimiter(limit=1, seconds=60)
    limiter.check("1.1.1.1", now=0)
    limiter.check("2.2.2.2", now=0)
    with pytest.raises(RateLimited):
        limiter.check("1.1.1.1", now=0)


def test_the_client_is_read_from_the_proxy_header_when_there_is_one():
    def request(headers, client="10.0.0.9"):
        return SimpleNamespace(headers=headers, client=SimpleNamespace(host=client))

    # The last entry, because it is the only one our own proxy wrote. Taking
    # the first would let a caller choose their own rate-limit key by sending
    # a header, and pick a new one every request.
    assert caller(request({"x-forwarded-for": "203.0.113.7, 10.0.0.1"})) == "10.0.0.1"
    assert caller(request({"x-forwarded-for": "spoofed, spoofed, 198.51.100.4"})) == "198.51.100.4"
    assert caller(request({})) == "10.0.0.9"
    assert caller(SimpleNamespace(headers={}, client=None)) == "unknown"
    # A header long enough to be a memory attack is cut down to size.
    assert len(caller(request({"x-forwarded-for": "9" * 500}))) == 64


@pytest.mark.parametrize("limit,seconds", [(0, 60), (3, 0), (-1, -1)])
def test_a_limit_has_to_mean_something(limit, seconds):
    with pytest.raises(ValueError, match="positive count and window"):
        WindowLimiter(limit=limit, seconds=seconds)


def test_the_login_endpoints_are_the_ones_behind_it():
    from app.routers import auth

    source = (auth.__file__ and open(auth.__file__, encoding="utf-8").read()) or ""
    assert source.count("_throttle(request)") == 2
    for name in ("telegram_login", "guest_login"):
        assert f"async def {name}" in source


def test_each_app_counts_for_itself():
    """Module-level state would be shared by every app in the process.

    In production that is one app and the distinction never shows. In a test
    run it is dozens, and counts leaking between them refuse a login nobody
    made -- which is exactly how this file's first version hung the suite.
    """
    from app.routers.auth import LOGIN_LIMIT, _throttle

    def app_with_its_own_state():
        state = SimpleNamespace()
        return SimpleNamespace(
            app=SimpleNamespace(state=state), headers={"x-forwarded-for": "203.0.113.7"},
            client=None,
        )

    first = app_with_its_own_state()
    for _ in range(LOGIN_LIMIT):
        _throttle(first)
    with pytest.raises(HTTPException) as refused:
        _throttle(first)
    assert refused.value.status_code == 429
    # A different app instance starts from zero, same caller and all.
    _throttle(app_with_its_own_state())
