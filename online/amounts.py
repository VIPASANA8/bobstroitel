from decimal import Decimal, ROUND_HALF_UP


SCALE = Decimal("100")


def to_units(value: Decimal | str | int | float) -> int:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * SCALE)


def from_units(value: int) -> Decimal:
    return (Decimal(value) / SCALE).quantize(Decimal("0.01"))
