import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest
from sqlalchemy import insert

from online.auth import AuthService, AuthenticationError
from online.schema import tenants


NOW = 1_770_000_000


def signed_init_data(user_id=55, name="Марта", token="token-a", auth_date=NOW, **extra_user_fields):
    user = {"id": user_id, "first_name": name, **extra_user_fields}
    pairs = {
        "query_id": "AAE",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
        "auth_date": str(auth_date),
    }
    check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


@pytest.fixture
def auth_service(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants), [
                {"id": "t1", "slug": "poker8", "name": "Poker8"},
                {"id": "t2", "slug": "partner-b", "name": "Partner B"},
            ])
            await session.commit()

    import asyncio
    asyncio.run(seed())
    return AuthService(
        db_session_factory,
        {"poker8": "token-a", "partner-b": "token-b"},
        now=lambda: NOW,
    )


@pytest.mark.anyio
async def test_valid_init_data_creates_one_global_user(auth_service):
    first = await auth_service.authenticate("poker8", signed_init_data())
    second = await auth_service.authenticate(
        "partner-b", signed_init_data(token="token-b")
    )
    assert first.user_id == second.user_id
    assert first.auth_method == second.auth_method == "telegram"
    assert second.acquisition_tenant_slug == "poker8"
    assert second.access_tenant_slug == "partner-b"


@pytest.mark.anyio
async def test_wrong_bot_signature_is_rejected(auth_service):
    with pytest.raises(AuthenticationError, match="signature"):
        await auth_service.authenticate("partner-b", signed_init_data())


@pytest.mark.anyio
async def test_expired_init_data_is_rejected(auth_service):
    with pytest.raises(AuthenticationError, match="expired"):
        await auth_service.authenticate("poker8", signed_init_data(auth_date=1))


@pytest.mark.anyio
async def test_display_name_is_first_name_only_never_username(auth_service):
    """A handle reads as a login, not a player, at the table.

    It also broke avatar initials: avatarInitials() splits on whitespace, so
    an "@handle" display name rendered as a single "@" for its initial.
    """
    result = await auth_service.authenticate(
        "poker8", signed_init_data(name="Артём", username="handle99", last_name="K")
    )
    assert result.display_name == "Артём"


@pytest.mark.anyio
async def test_display_name_falls_back_to_telegram_id_without_a_first_name(auth_service):
    result = await auth_service.authenticate(
        "poker8", signed_init_data(user_id=777, name=None, username="handle99")
    )
    assert result.display_name == "777"
