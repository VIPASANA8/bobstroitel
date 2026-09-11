"""The operator panel: a menu of buttons, and what it takes to decide."""
import pytest

from cash.access import CashOperator
from cash.admin import OperatorAccessDenied
from online.opsbot import OpsBot


ADMIN = CashOperator("op-1", 8010868263, None, "admin")
REVIEWER = CashOperator("op-2", 5, "tenant", "reviewer")

QUEUE = {
    "withdrawals": [{
        "id": "w-1", "status": "reserved", "user_id": "u-1",
        "amount_micros": 5_000_000, "destination_address": "TAddr",
    }],
    "payment_reviews": [{
        "id": "p-1", "status": "review_required", "amount_micros": 1_000_000,
        "tx_hash": "0xabc", "deposit_id": None, "tenant_id": "tenant",
    }],
}


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

    async def audit(self, operator, limit=100):
        return [{"action": "approve", "target_id": "w-0", "reason": "проверено"}]

    async def user(self, operator, identifier):
        return {
            "id": "u-1", "telegram_user_id": 42, "display_name": "Игрок", "hold": None,
            "balances": {
                "available": {"usdt": "5", "units": "50"},
                "escrow": {"usdt": "0", "units": "0"},
                "withdrawal": {"usdt": "0", "units": "0"},
            },
        }

    async def approve_withdrawal(self, target, operator, *, reason, key):
        self.calls.append(("approve", target, reason, key, operator.role))
        return {"status": "approved"}


def _bot():
    return OpsBot(FakeAdmin(), None)


def _keyboard(screen):
    return screen[-1]


def _labels(keyboard):
    return [button["text"] for row in (keyboard or []) for button in row]


def _data(keyboard):
    return [button["callback_data"] for row in (keyboard or []) for button in row]


@pytest.mark.anyio
async def test_the_panel_opens_on_a_menu_of_buttons(anyio_backend):
    how, text, keyboard = (await _bot().message(ADMIN, "/start"))[0]
    assert how == "send"
    assert "Панель оператора" in text
    # Every way on is a button, not a command somebody has to already know.
    assert _data(keyboard) == [
        "nav:economy", "nav:referrals", "nav:partner",
        "nav:money", "nav:queue", "ask:user", "ask:order", "nav:recon", "nav:audit",
    ]
    assert "Очередь (2)" in " ".join(_labels(keyboard))


@pytest.mark.anyio
async def test_navigation_redraws_the_same_message(anyio_backend):
    bot = _bot()
    for where, expected in (("nav:money", "Деньги"), ("nav:audit", "решения"),
                            ("nav:queue", "Очередь")):
        how, text, keyboard = (await bot.callback(ADMIN, where))[0]
        assert how == "edit", where
        assert expected in text
        # And every screen leads back, so nothing is a dead end.
        assert "nav:main" in _data(keyboard)


@pytest.mark.anyio
async def test_the_queue_splits_by_kind_and_deals_the_cards(anyio_backend):
    bot = _bot()
    _, _, keyboard = (await bot.callback(ADMIN, "nav:queue"))[0]
    assert _data(keyboard)[:2] == ["q:withdrawal", "q:payment"]

    screen = await bot.callback(ADMIN, "q:withdrawal")
    assert screen[0][0] == "edit"
    # The card is its own message, because it carries its own buttons.
    assert screen[1][0] == "send"
    assert _data(screen[1][2]) == ["approve:w-1", "reject:w-1"]


@pytest.mark.anyio
async def test_a_decision_needs_a_reason_and_a_confirmation(anyio_backend):
    bot = _bot()
    assert "причину" in (await bot.callback(ADMIN, "approve:w-1"))[0][1]
    assert bot.admin.calls == []
    # A too-short reason is not one.
    assert "от 3 до 500" in (await bot.message(ADMIN, "ok"))[0][1]
    assert bot.admin.calls == []

    asked = (await bot.message(ADMIN, "проверено по выписке"))[0]
    assert "Подтвердить" in asked[1] and "confirm:" in _data(asked[2])
    assert bot.admin.calls == []

    done = (await bot.callback(ADMIN, "confirm:"))[0]
    action, target, reason, key, role = bot.admin.calls[0]
    assert (action, target, reason, role) == ("approve", "w-1", "проверено по выписке", "admin")
    assert key, "the idempotency key travels with the decision"
    assert "approved" in done[1]


@pytest.mark.anyio
async def test_going_back_to_the_menu_drops_a_half_made_decision(anyio_backend):
    bot = _bot()
    await bot.callback(ADMIN, "approve:w-1")
    await bot.callback(ADMIN, "nav:main")
    assert "устарело" in (await bot.callback(ADMIN, "confirm:"))[0][1]
    assert bot.admin.calls == []


@pytest.mark.anyio
async def test_asking_for_a_player_waits_for_the_id(anyio_backend):
    bot = _bot()
    how, text, keyboard = (await bot.callback(ADMIN, "ask:user"))[0]
    assert how == "edit" and "ID игрока" in text
    assert _data(keyboard) == ["nav:main"]

    card = (await bot.message(ADMIN, "u-1"))[0]
    assert "Игрок" in card[1]
    assert "freeze:u-1" in _data(card[2])


@pytest.mark.anyio
async def test_a_reviewer_reads_and_does_not_touch(anyio_backend):
    bot = _bot()
    cards = await bot.callback(REVIEWER, "q:withdrawal")
    assert cards[1][2] is None, "no buttons for a role that may not press them"
    assert "reviewer" in (await bot.callback(REVIEWER, "approve:w-1"))[0][1]
    assert bot.admin.calls == []
    assert "глобального админа" in (await bot.callback(REVIEWER, "nav:money"))[0][1]


@pytest.mark.anyio
async def test_a_stale_button_says_so_instead_of_failing(anyio_backend):
    bot = _bot()
    assert "устарела" in (await bot.callback(ADMIN, "approve:"))[0][1]
    assert bot.admin.calls == []


@pytest.mark.anyio
async def test_the_reconciliation_screen_asks_for_a_real_day(anyio_backend):
    """The sweep takes a date, not None -- the HTTP route in front of the same
    service defaults to today, and so does the button."""
    seen = []

    class Recon(FakeAdmin):
        async def fiat_reconciliation(self, operator, day):
            seen.append(day)
            return {
                "day": str(day), "balanced": True, "mismatches": [],
                "orders": {"count": 0, "charged_rub": "0,00",
                           "credited_usdt": "0", "fee_usdt": "0"},
                "ledger": {"credited_usdt": "0", "fee_usdt": "0", "clearing_usdt": "0"},
                "balances": {"clearing_usdt": "0", "fee_usdt": "0"},
            }

    bot = OpsBot(Recon(), None)
    how, _text, keyboard = (await bot.callback(ADMIN, "nav:recon"))[0]
    assert how == "edit" and _data(keyboard) == ["nav:main"]
    assert seen and hasattr(seen[0], "isoformat"), seen


class Money(FakeAdmin):
    """Records the two decisions that were missing from the panel."""

    async def queue(self, operator):
        return {"withdrawals": [
            {"id": "w-crypto", "status": "approved", "user_id": "u-1", "network": "TRC20",
             "amount_micros": 5_000_000, "destination_address": "TAddr"},
            {"id": "w-rub", "status": "approved", "user_id": "u-2", "network": "P2P_RUB",
             "amount_micros": 5_000_000, "destination_address": "+79990000000"},
        ]}

    async def settle_p2p_withdrawal(self, target, operator, *, fiat_kopecks, reason, key):
        self.calls.append(("settle", target, fiat_kopecks, reason, key))
        return {"status": "confirmed"}

    async def settle_trc20_withdrawal(self, target, operator, *, tx_hash, reason, key):
        self.calls.append(("txsettle", target, tx_hash, reason, key))
        return {"status": "submitted"}

    async def adjust_balance(self, identifier, operator, *, amount_micros, reason, key):
        self.calls.append(("adjust", identifier, amount_micros, reason, key))
        return {"status": "начислено" if amount_micros > 0 else "списано"}


@pytest.mark.anyio
async def test_real_money_offers_no_mock_payout_only_the_hash_you_sent(anyio_backend):
    """On the host where CASH is real and no payout provider exists, the crypto
    card asks for the transaction the operator made, never "Mock success"."""
    bot = OpsBot(Money(), None, mock_rails=False)
    cards = await bot.callback(ADMIN, "q:withdrawal")
    crypto, rub = cards[1][2], cards[2][2]
    assert _data(crypto) == ["txsettle:w-crypto"]
    assert _data(rub) == ["settle:w-rub"]

    assert "reference" in (await bot.callback(ADMIN, "txsettle:w-crypto"))[0][1]
    await bot.message(ADMIN, "0xabc123")
    await bot.message(ADMIN, "отправил с холодного кошелька")
    await bot.callback(ADMIN, "confirm:")
    action, target, tx_hash, reason, key = bot.admin.calls[0]
    assert (action, target, tx_hash, reason) == (
        "txsettle", "w-crypto", "0xabc123", "отправил с холодного кошелька")


@pytest.mark.anyio
async def test_a_rub_payout_is_recorded_by_hand_not_mocked(anyio_backend):
    """Nothing automatic sends fiat, so the only thing to record is that a
    person sent it -- and how much, which the mock rail never asks."""
    bot = OpsBot(Money(), None)
    cards = await bot.callback(ADMIN, "q:withdrawal")
    crypto, rub = cards[1][2], cards[2][2]
    assert _data(crypto) == ["success:w-crypto", "unknown:w-crypto", "failure:w-crypto"]
    assert _data(rub) == ["settle:w-rub"]

    assert "рублях" in (await bot.callback(ADMIN, "settle:w-rub"))[0][1]
    # A sum that is not a sum is asked for again rather than sent as zero.
    assert "рублях" in (await bot.message(ADMIN, "около двух тысяч"))[0][1]
    assert bot.admin.calls == []

    assert "1815,50" in (await bot.message(ADMIN, "1815,50"))[0][1]
    await bot.message(ADMIN, "отправил по СБП")
    await bot.callback(ADMIN, "confirm:")
    action, target, kopecks, reason, key = bot.admin.calls[0]
    assert (action, target, kopecks, reason) == ("settle", "w-rub", 181550, "отправил по СБП")
    assert key


@pytest.mark.anyio
@pytest.mark.parametrize("verb,expected", [("credit_user", 25_500_000), ("debit_user", -25_500_000)])
async def test_a_balance_can_be_moved_by_hand_with_a_reason(anyio_backend, verb, expected):
    """The last resort behind every rail -- and it goes through the same
    reason-and-confirm as every other decision."""
    bot = OpsBot(Money(), None)
    assert "USDT" in (await bot.callback(ADMIN, f"{verb}:u-1"))[0][1]
    assert "USDT" in (await bot.message(ADMIN, "двадцать пять"))[0][1]
    assert bot.admin.calls == []

    assert "25.5" in (await bot.message(ADMIN, "25.50"))[0][1]
    asked = (await bot.message(ADMIN, "возврат после инцидента"))[0]
    assert "Подтвердить" in asked[1]
    assert bot.admin.calls == []

    await bot.callback(ADMIN, "confirm:")
    action, identifier, amount, reason, key = bot.admin.calls[0]
    assert (action, identifier, amount, reason) == ("adjust", "u-1", expected, "возврат после инцидента")
    assert key


@pytest.mark.anyio
async def test_the_player_card_offers_both_directions(anyio_backend):
    bot = OpsBot(Money(), None)
    await bot.callback(ADMIN, "ask:user")
    card = (await bot.message(ADMIN, "u-1"))[0]
    assert _data(card[2])[:2] == ["credit_user:u-1", "debit_user:u-1"]
