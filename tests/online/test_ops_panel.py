"""The operator panel in the bot: who it answers, and what it takes to decide."""
import pytest

from cash.access import CashOperator
from cash.admin import OperatorAccessDenied
from online.opsbot import OpsBot


ADMIN = CashOperator("op-1", 8010868263, None, "admin")
REVIEWER = CashOperator("op-2", 5, "tenant", "reviewer")

QUEUE = {"withdrawals": [{
    "id": "w-1", "status": "reserved", "user_id": "u-1",
    "amount_micros": 5_000_000, "destination_address": "TAddr",
}]}


class FakeAdmin:
    """Stands in for CashAdminService and records what it was asked to do."""

    def __init__(self):
        self.calls = []

    async def queue(self, operator):
        return QUEUE

    async def overview(self, operator):
        if operator.role != "admin":
            raise OperatorAccessDenied("admins only")
        return {
            "players": 3, "frozen": 1, "available_micros": 10_000_000,
            "escrow_micros": 2_000_000, "withdrawal_micros": 1_000_000,
            "cube_house_micros": 500_000, "cube_rounds_day": 7,
            "cube_result_day_micros": 250_000,
        }

    async def approve_withdrawal(self, target, operator, *, reason, key):
        self.calls.append(("approve", target, reason, key, operator.role))
        return {"status": "approved"}


def _bot():
    return OpsBot(FakeAdmin(), None)


@pytest.mark.anyio
async def test_a_decision_needs_a_reason_and_a_confirmation(anyio_backend):
    bot = _bot()
    # The queue offers the buttons an admin may press.
    items = await bot.message(ADMIN, "/queue")
    assert items[0][1] == [[
        {"text": "Разрешить", "callback_data": "approve:w-1"},
        {"text": "Отклонить", "callback_data": "reject:w-1"},
    ]]

    assert "причину" in (await bot.callback(ADMIN, "approve:w-1"))[0][0]
    # Nothing has happened yet, and a too-short reason still does not do it.
    assert bot.admin.calls == []
    assert "от 3 до 500" in (await bot.message(ADMIN, "ok"))[0][0]
    assert bot.admin.calls == []

    asked = await bot.message(ADMIN, "проверено по выписке")
    assert "Подтвердить" in asked[0][0] and asked[0][1]
    assert bot.admin.calls == []

    done = await bot.callback(ADMIN, "confirm")
    action, target, reason, key, role = bot.admin.calls[0]
    assert (action, target, reason, role) == ("approve", "w-1", "проверено по выписке", "admin")
    assert key, "the idempotency key travels with the decision"
    assert "approved" in done[0][0]


@pytest.mark.anyio
async def test_cancelling_forgets_the_half_made_decision(anyio_backend):
    bot = _bot()
    await bot.callback(ADMIN, "approve:w-1")
    assert "Отменено" in (await bot.callback(ADMIN, "cancel"))[0][0]
    # And confirming afterwards has nothing to confirm.
    assert "устарело" in (await bot.callback(ADMIN, "confirm"))[0][0]
    assert bot.admin.calls == []


@pytest.mark.anyio
async def test_a_reviewer_reads_and_does_not_touch(anyio_backend):
    bot = _bot()
    items = await bot.message(REVIEWER, "/queue")
    assert items[0][1] is None, "no buttons for a role that may not press them"
    assert "reviewer" in (await bot.callback(REVIEWER, "approve:w-1"))[0][0]
    assert bot.admin.calls == []
    # And the money summary is an admin's view.
    assert "глобального админа" in (await bot.message(REVIEWER, "/panel"))[0][0]


@pytest.mark.anyio
async def test_the_panel_shows_the_money_to_an_admin(anyio_backend):
    panel = (await _bot().message(ADMIN, "/panel"))[0][0]
    assert "10" in panel and "CUBE" in panel and "7" in panel
