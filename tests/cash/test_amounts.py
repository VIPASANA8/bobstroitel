import pytest

from cash.amounts import (
    MAX_MICROS, micros_to_units, micros_to_usdt,
    units_to_micros, usdt_to_micros,
)


def test_usdt_and_cash_are_two_denominations_of_the_same_amount():
    assert usdt_to_micros("1") == units_to_micros("10") == 1_000_000
    assert micros_to_units(usdt_to_micros("10.01")) == "100.1"
    assert micros_to_usdt(units_to_micros("100")) == "10"
    assert micros_to_units(usdt_to_micros("0.000001")) == "0.00001"
    assert micros_to_usdt(usdt_to_micros("0")) == "0"


@pytest.mark.parametrize("value", [
    "-1", "NaN", "Infinity", "1e2", "1,00", " 1", "1 ",
    "0.0000001", "", ".1", "+1", 1.1, 1, True, None,
    "9223372036854.775808",
])
def test_usdt_parser_rejects_ambiguous_or_inexact_input(value):
    with pytest.raises(ValueError):
        usdt_to_micros(value)


def test_cash_unit_precision_and_bigint_boundary():
    with pytest.raises(ValueError):
        units_to_micros("0.000001")
    assert usdt_to_micros(micros_to_usdt(MAX_MICROS)) == MAX_MICROS
    assert units_to_micros(micros_to_units(MAX_MICROS)) == MAX_MICROS
    for value in (-1, True, 1.5, MAX_MICROS + 1):
        with pytest.raises(ValueError):
            micros_to_usdt(value)
