"""The CASH cashier moved out of the lobby and into the profile, and the two
kinds of money stopped sharing a history.

The lobby is for picking a table; it shows what is spendable at one and links
to the cashier. Everything that moves money -- deposits, withdrawals, escrow,
pending payouts -- lives behind the profile's CASH-касса tab.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import insert

from app.routers.tables import CASH_MESSAGES_RU, _cash_message
from cash.game import CashRuntimeError
from online.catalogue import CASH_USDT, PLAY
from online.history import HistoryService
from online.schema import hand_players, hands, poker_tables, tenants, users


ROOT = Path(__file__).resolve().parents[2]
LOBBY = (ROOT / "static" / "lobby.html").read_text(encoding="utf-8")
LOBBY_JS = (ROOT / "static" / "lobby.js").read_text(encoding="utf-8")
PROFILE = (ROOT / "static" / "profile.html").read_text(encoding="utf-8")
PROFILE_JS = (ROOT / "static" / "profile.js").read_text(encoding="utf-8")
AUTH_JS = (ROOT / "static" / "auth-client.js").read_text(encoding="utf-8")
CASH_CSS = (ROOT / "static" / "cash-ui.css").read_text(encoding="utf-8")
CASHIER_JS = (ROOT / "static" / "cash-cashier.js").read_text(encoding="utf-8")


def test_a_stale_telegram_launch_falls_back_to_the_session_cookie():
    """initData is captured once, when Telegram opens the Mini App, and the
    server stops accepting it after fifteen minutes. Every page move after that
    re-posted the same blob and the lobby printed "войдите через Telegram" at a
    player who had never left Telegram."""
    assert "/api/auth/telegram" in AUTH_JS
    fallback = AUTH_JS[AUTH_JS.index("if (!response.ok)"):]
    assert "initDataUnsafe?.user?.id" in fallback
    assert "'/api/profile'" in fallback
    # Only for the same person Telegram says is looking -- a wrong bot token
    # has nobody signed in behind it and must still fail loudly.
    assert "Number(existing.telegram_user_id) === Number(telegramId)" in fallback
    assert "throw signIn(" in fallback


def test_the_profile_separates_the_money_from_the_game():
    assert 'id="playModeTab"' in PROFILE and 'id="cashModeTab"' in PROFILE
    assert 'aria-controls="cashSection"' in PROFILE
    # The cashier's own controls sit inside that half of the page.
    cash_half = PROFILE[PROFILE.index('id="cashSection"'):]
    for element_id in ("cashDeposit", "cashWithdraw", "cashHandHistory"):
        assert f'id="{element_id}"' in cash_half, element_id
    # ...and the practice history stays out of it.
    assert 'id="handHistory"' not in cash_half
    assert 'id="ledger"' not in cash_half


def test_the_deposit_sheet_belongs_to_the_phone_and_only_the_phone():
    """CASE8's flow -- pick a rail, then an amount -- is a phone shape: the
    dialog slides up from the bottom edge and stays pinned to it, where the
    thumb is. On a desktop that same rule is a full-width band across a wide
    screen, and the method step does not exist there at all: both rails are
    buttons, each opening its own dialog, centred as they always were."""
    query = "@media (max-width:640px){"
    sheet = CASH_CSS[CASH_CSS.index(query):]
    assert "bottom:0" in sheet and "translateY(100%)" in sheet
    # Nothing pins a dialog to the bottom edge outside that query.
    assert "translateY(100%)" not in CASH_CSS.replace(sheet, "")
    # Desktop keeps the pair of buttons and never reaches the chooser.
    assert 'id="cashFiatDeposit"' in PROFILE
    assert 'window.matchMedia("(max-width: 640px)")' in CASHIER_JS
    assert 'phone.matches ? "depositMethodDialog" : "depositDialog"' in CASHIER_JS


def test_each_tablist_moves_only_its_own_panels():
    """One flat list of every [role="tab"] hid one group's panel whenever the
    other group was used -- and the page now has two groups."""
    assert "document.querySelectorAll('[role=\"tablist\"]').forEach(bindTabs)" in PROFILE_JS
    assert "document.querySelectorAll('[role=\"tab\"]')" not in PROFILE_JS


def test_the_two_histories_are_asked_for_separately():
    assert "/api/profile/hands?limit=20&asset=PLAY" in PROFILE_JS
    assert "/api/profile/hands?limit=20&asset=CASH_USDT" in PROFILE_JS


def test_a_room_can_be_opened_in_either_mode():
    assert 'id="createRoom"' in LOBBY
    assert "/api/lobby/rooms?asset=${asset}" in LOBBY_JS
    assert "/api/lobby/room-levels?asset=${asset}" in LOBBY_JS
    # The CASH lobby used to hide the second entry button outright.
    assert ".cash-mode .entry-secondary{display:none}" not in CASH_CSS


@pytest.mark.parametrize("english", sorted(CASH_MESSAGES_RU))
def test_the_felt_speaks_russian(english):
    """These reach the player verbatim in an alert(); "a cash hand requires 2
    to 6 seated users" is what a table of one actually saw."""
    russian = _cash_message(CashRuntimeError(english))
    assert russian != english
    assert not russian.isascii()


def test_the_engine_keeps_its_own_words():
    """ready() decides whether a seating attempt failed for want of players by
    reading the exception text, so the raise sites stay English."""
    source = (ROOT / "cash" / "game.py").read_text(encoding="utf-8")
    assert '"a cash hand requires 2 to 6 seated users"' in source
    assert "requires 2 to 6" in (ROOT / "app" / "routers" / "tables.py").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_hand_history_keeps_practice_and_cash_apart(db_session_factory):
    """Different money, different list: a practice hand counted in chips must
    never turn up under a balance denominated in USDT."""
    now = datetime.now(timezone.utc)
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(users).values(
            id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
        for table_id, asset in (("play-t", PLAY), ("cash-t", CASH_USDT)):
            await session.execute(insert(poker_tables).values(
                id=table_id, scope="network", asset=asset, name=table_id,
                small_blind_units=50, big_blind_units=100,
                min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.execute(insert(hands).values(
                id=f"h-{table_id}", table_id=table_id, revision_started=1, button_seat=0,
                board_json=[], started_at=now, completed_at=now,
            ))
            await session.execute(insert(hand_players).values(
                hand_id=f"h-{table_id}", participant_id=f"p-{table_id}", user_id="u1",
                seat_no=0, position="BTN", net_units=500, net_micros=250_000,
            ))
        await session.commit()

    history = HistoryService(db_session_factory)
    assert [hand["hand_id"] for hand in await history.last_hands("u1", asset=PLAY)] == ["h-play-t"]
    assert [hand["hand_id"] for hand in await history.last_hands("u1", asset=CASH_USDT)] == ["h-cash-t"]
    assert len(await history.last_hands("u1")) == 2
    # The cash row is only renderable if the exact amount comes with it.
    cash_hand = (await history.last_hands("u1", asset=CASH_USDT))[0]
    assert cash_hand["players"][0]["net_micros"] == 250_000
