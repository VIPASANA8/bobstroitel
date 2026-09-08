import json

from admin_bot.client import CashAdminClient
from admin_bot.economy import economy_message, partner_message, referral_message


class Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self):
        return self.body


def test_admin_client_reads_referral_and_partner_reports():
    urls = []

    def opener(request, timeout):
        urls.append(request.full_url)
        return Response({})

    client = CashAdminClient("https://poker.example", "secret", opener=opener)
    client.referrals(1001, 500)
    client.partner(1001)

    assert urls == [
        "https://poker.example/api/cash-admin/referrals?limit=500",
        "https://poker.example/api/cash-admin/partner",
    ]


def referral_report():
    return {
        "totals_usdt": {"pending": "3.5", "available": "12", "reversed": "1"},
        "settlements": [
            {"source": "poker", "status": "available", "amount_micros": 2_000_000},
            {"source": "cube", "status": "pending", "amount_micros": 1_500_000},
            {"source": "cube", "status": "reversed", "amount_micros": 1_000_000},
        ],
        "largest_groups": [
            {"referrer_id": "alice", "invited": 7},
            {"referrer_id": "bob", "invited": 3},
        ],
    }


def partner_report():
    return {
        "shares": [{"effective_from": "2026-09-01", "share_bps": 2500}],
        "settlements": [
            {
                "period_kind": "month", "period_start": "2026-09-01", "period_end": "2026-09-30",
                "gross_micros": 100_000_000, "referral_cost_micros": 10_000_000,
                "adjustment_micros": -5_000_000, "net_micros": 85_000_000,
                "carryover_after_micros": 0, "amount_micros": 21_250_000, "posted": True,
            },
            {
                "period_kind": "week", "period_start": "2026-09-01", "period_end": "2026-09-07",
                "gross_micros": 30_000_000, "referral_cost_micros": 2_000_000,
                "adjustment_micros": 0, "net_micros": 28_000_000,
                "carryover_after_micros": 0, "amount_micros": 7_000_000, "posted": False,
            },
        ],
        "adjustments": [],
    }


def test_referral_card_uses_plain_language_and_keeps_source_totals():
    text = referral_message(referral_report())
    assert "В ожидании: <b>3.5 USDT</b>" in text
    assert "Доступно к выплате: <b>12 USDT</b>" in text
    assert "♠️ POKER: <b>2 USDT</b>" in text
    assert "🎲 CUBE: <b>1.5 USDT</b>" in text
    assert "alice" in text and "приглашено 7" in text
    assert "RevShare" not in text


def test_partner_card_never_counts_report_only_period_as_paid():
    text = partner_message(partner_report())
    assert "Текущая доля: <b>75/25</b>" in text
    assert "BOOSTER: <b>21.25 USDT</b>" in text
    assert "RICK: <b>63.75 USDT</b>" in text
    assert "Закрытых платёжных периодов: 1" in text


def test_economy_card_uses_game_accounts_and_partner_total():
    text = economy_message(
        referral_report(), partner_report(),
        {"cube_house_micros": 40_000_000, "poker_house_micros": 12_500_000},
    )
    assert "CUBE: <b>40 USDT</b>" in text
    assert "POKER: <b>12.5 USDT</b>" in text
    assert "BOOSTER: <b>21.25 USDT</b> (25%)" in text
    assert "Начислено и не отменено: 15.5 USDT" in text
    assert "reversed: 1 USDT" in text
