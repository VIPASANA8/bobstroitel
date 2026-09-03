"""A payout costs money to send, so the person asking for it pays that cost."""
import pytest

from cash.withdrawals import WithdrawalService


def test_the_fee_must_be_a_nonnegative_integer_of_micros():
    with pytest.raises(ValueError, match="withdrawal fee"):
        WithdrawalService(None, fee_micros=-1)
    with pytest.raises(ValueError, match="withdrawal fee"):
        WithdrawalService(None, fee_micros=1.5)
    assert WithdrawalService(None, fee_micros=0).fee_micros == 0


def test_the_public_projection_separates_the_debit_from_the_payout():
    row = {"id": "w1", "status": "reserved", "network": "TRC20", "destination_address": "T",
           "amount_micros": 5_000_000, "fee_micros": 1_500_000, "tx_hash": None}
    public = WithdrawalService.public(row)
    assert public["amount_usdt"] == "5"       # taken off the wallet
    assert public["fee_usdt"] == "1.5"        # kept by the house
    assert public["payout_usdt"] == "3.5"     # what reaches the chain


def test_the_withdrawal_ceiling_matches_the_deposit_one():
    """Capped lower, the flat fee is charged once per 100 USDT taken out.

    A player who deposited 500 USDT through C2C had to leave in five payouts
    and pay 5 USDT each time. The two bounds move together or the fee stops
    being a fee and becomes a percentage nobody agreed to.
    """
    from cash.deposits import DepositService

    assert WithdrawalService.MAX == DepositService.MAX
