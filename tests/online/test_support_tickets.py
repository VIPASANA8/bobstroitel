"""A player writes, every operator gets a card, one answer flips them all."""
import asyncio

import pytest

from cash.access import CashOperator
from online import support as support_module
from online.schema import cash_operators, tenants, users
from online.support import SupportError, SupportService


ADMIN = CashOperator("op-1", 111, None, "admin")


class FakeTelegram:
    """Records what would have gone to the Bot API, and hands back ids."""

    def __init__(self):
        self.sent = []      # (token, chat_id, text, keyboard)
        self.photos = []    # (token, chat_id, payload)
        self.edits = []     # (token, chat_id, message_id, keyboard)
        self.next_id = 100

    async def send_message(self, token, chat_id, text, reply_markup=None, parse_mode=None):
        self.next_id += 1
        self.sent.append((token, chat_id, text, reply_markup))
        return self.next_id

    async def send_photo(self, token, chat_id, photo, caption, reply_markup=None,
                         parse_mode=None, filename="image.jpg"):
        self.next_id += 1
        self.photos.append((token, chat_id, photo))
        return self.next_id, "file-abc"

    async def edit_reply_markup(self, token, chat_id, message_id, reply_markup):
        self.edits.append((token, chat_id, message_id, reply_markup))


@pytest.fixture
def telegram(monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(support_module, "send_message", fake.send_message)
    monkeypatch.setattr(support_module, "send_photo", fake.send_photo)
    monkeypatch.setattr(support_module, "edit_reply_markup", fake.edit_reply_markup)
    return fake


@pytest.fixture
def service(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            async with session.begin():
                await session.execute(tenants.insert().values(id="t1", slug="poker8", name="Poker8"))
                await session.execute(users.insert().values(
                    id="u1", telegram_user_id=42, display_name="Игрок", username="maktraxer",
                    acquisition_tenant_id="t1"))
                await session.execute(cash_operators.insert().values(
                    id="op-1", telegram_user_id=111, role="admin"))
                await session.execute(cash_operators.insert().values(
                    id="op-2", telegram_user_id=222, tenant_id="t1", role="operator"))
                await session.execute(cash_operators.insert().values(
                    id="op-3", telegram_user_id=333, tenant_id="t1", role="reviewer"))
    asyncio.run(seed())
    return SupportService(db_session_factory, admin_token="admin-token",
                          player_tokens={"poker8": "player-token"})


def _buttons(keyboard):
    return [button["text"] for row in keyboard["inline_keyboard"] for button in row]


def test_ticket_round_trip(service, telegram):
    ticket = asyncio.run(service.open(
        user_id="u1", tenant_id="t1", topic="support", text="Не зачислился депозит",
        photo=b"\xff\xd8jpeg", photo_type="image/jpeg",
    ))
    # Two operators can act, the reviewer cannot: two cards, both photos, and
    # the second one rides on the file_id the first upload produced.
    assert [chat for _, chat, _ in telegram.photos] == [111, 222]
    assert telegram.photos[0][2] == b"\xff\xd8jpeg" and telegram.photos[1][2] == "file-abc"
    assert ticket["status"] == "open" and ticket["messages"][0]["has_photo"]

    cards = asyncio.run(service.open_for_operator(ADMIN))
    assert len(cards) == 1
    assert _buttons(cards[0]["keyboard"]) == ["✍️ Ответить", "❌ Не отвечено"]
    assert "<code>42</code>" in cards[0]["text"] and "@maktraxer" in cards[0]["text"]

    asyncio.run(service.operator_reply(ADMIN, ticket["id"], "Проверяем, ответим сегодня"))
    # Every copy of the card flips, and the player hears it on their own bot.
    assert [(chat, _buttons(kb)) for _, chat, _, kb in telegram.edits] == [
        (111, ["✍️ Ответить", "Закрыть тикет", "✅ Сообщение доставлено"]),
        (222, ["✍️ Ответить", "Закрыть тикет", "✅ Сообщение доставлено"]),
    ]
    token, chat, text, keyboard = telegram.sent[-1]
    assert (token, chat) == ("player-token", 42) and "Проверяем" in text
    assert _buttons(keyboard) == ["Ответить на сообщение", "Закрыть"]

    thread = asyncio.run(service.ticket("u1", ticket["id"]))
    assert thread["status"] == "answered"
    assert [m["author"] for m in thread["messages"]] == ["user", "operator"]

    asyncio.run(service.close(ticket["id"], operator=ADMIN))
    assert asyncio.run(service.tickets("u1")) == []
    assert asyncio.run(service.tickets("u1", closed=True))[0]["status"] == "closed"
    with pytest.raises(SupportError):
        asyncio.run(service.user_reply(user_id="u1", ticket_id=ticket["id"], text="ещё"))


def test_open_tickets_are_capped(service, telegram):
    for _ in range(support_module.MAX_OPEN):
        asyncio.run(service.open(user_id="u1", tenant_id="t1", topic="support", text="вопрос"))
    with pytest.raises(SupportError):
        asyncio.run(service.open(user_id="u1", tenant_id="t1", topic="support", text="ещё один"))


def test_finance_ticket_refuses_somebody_elses_order(service, telegram):
    with pytest.raises(SupportError):
        asyncio.run(service.open(user_id="u1", tenant_id="t1", topic="finance", text="где деньги",
                                 reference_kind="fiat_order", reference_id="not-mine"))
