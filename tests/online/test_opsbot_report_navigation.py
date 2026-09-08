import asyncio

from cash.access import CashOperator
from online.opsbot import OpsBot


class FakeAdmin:
    async def queue(self, operator):
        return {}

    async def referral_report(self, operator, *, limit=100):
        return {
            "totals_usdt": {"pending": "3.5", "available": "12", "reversed": "1"},
            "settlements": [],
            "largest_groups": [],
        }

    async def partner_report(self, operator):
        return {
            "shares": [{"share_bps": 2500}],
            "settlements": [],
            "adjustments": [],
        }


def _bot():
    return OpsBot(FakeAdmin(), None)


def _operator():
    return CashOperator("admin-1", 1001, None, "admin")


def test_start_and_help_show_report_buttons():
    expected = ["📊 Экономика", "👥 Рефералы", "🤝 Партнёр"]
    for command in ("/start", "/help"):
        replies = asyncio.run(_bot().message(_operator(), command))
        _, _, keyboard = replies[0]
        labels = [button["text"] for row in keyboard for button in row]
        assert labels[:3] == expected


def test_report_buttons_open_the_real_reports():
    bot = _bot()
    operator = _operator()

    economy = asyncio.run(bot.callback(operator, "nav:economy"))
    referrals = asyncio.run(bot.callback(operator, "nav:referrals"))
    partner = asyncio.run(bot.callback(operator, "nav:partner"))

    assert "Экономика проекта" in economy[0][1]
    assert "Реферальная программа" in referrals[0][1]
    assert "Партнёр / CUBE" in partner[0][1]
