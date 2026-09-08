from types import SimpleNamespace

from admin_bot.main import OperatorBot
from admin_bot.menu import REPORT_KEYBOARD


class FakeTelegram:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None):
        self.sent.append((chat_id, text, keyboard))


class FakeAPI:
    def referrals(self, actor_id, limit=100):
        return {"totals_usdt": {}, "settlements": [], "largest_groups": []}

    def partner(self, actor_id):
        return {"shares": [], "settlements": [], "adjustments": []}


def bot():
    instance = OperatorBot.__new__(OperatorBot)
    instance.telegram = FakeTelegram()
    instance.api = FakeAPI()
    instance.pending = {}
    return instance


def test_help_shows_economy_inline_buttons():
    instance = bot()
    instance.handle_message(10, 1001, "/help", {"role": "admin"})
    assert instance.telegram.sent[-1][2] == REPORT_KEYBOARD
    labels = [button["text"] for row in REPORT_KEYBOARD for button in row]
    assert labels == ["📊 Экономика", "👥 Рефералы", "🤝 Партнёр"]


def test_report_callback_opens_report_and_keeps_navigation_buttons():
    instance = bot()
    instance.handle_callback(10, 1001, "report:economy", {"role": "admin"})
    chat_id, text, keyboard = instance.telegram.sent[-1]
    assert chat_id == 10
    assert "Экономика проекта" in text
    assert keyboard == REPORT_KEYBOARD
