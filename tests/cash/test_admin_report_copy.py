from admin_bot.formatting import reconciliation_message
from online.opsbot import PROMPTS


def test_reconciliation_copy_is_grouped_and_hides_clearing_jargon():
    report = {
        "balanced": True,
        "day": "2026-09-08",
        "orders": {
            "count": 0,
            "charged_rub": "0,00",
            "credited_usdt": "0",
            "fee_usdt": "0",
        },
        "ledger": {
            "credited_usdt": "0",
            "fee_usdt": "0",
            "clearing_usdt": "0",
        },
        "balances": {
            "clearing_usdt": "-20.2",
            "fee_usdt": "0.2",
        },
        "mismatches": [],
    }

    text = reconciliation_message(report)

    assert "<b>Заявки</b>" in text
    assert "Получено от игроков: <b>0,00 ₽</b>" in text
    assert "<b>USDT</b>" in text
    assert "Расчётный баланс: <b>-20.2 USDT</b>" in text
    assert "Баланс комиссий: <b>0.2 USDT</b>" in text
    assert "clearing" not in text.lower()


def test_order_prompt_names_boostpay():
    assert PROMPTS["order"] == "Пришлите номер заявки — внутренний или BoostPay"
