import re

MAX_MICROS = 2**63 - 1
MICROS_PER_USDT = 1_000_000
MICROS_PER_CASH_UNIT = 100_000


def _parse(value: str, digits: int) -> int:
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError("amount must be a plain decimal string")
    match = re.fullmatch(r"([0-9]+)(?:\.([0-9]{1," + str(digits) + r"}))?", value)
    if match is None:
        raise ValueError("invalid amount or excess precision")
    whole, fraction = match.groups()
    result = int(whole) * 10**digits + int((fraction or "").ljust(digits, "0"))
    if result > MAX_MICROS:
        raise ValueError("amount exceeds supported range")
    return result


def _format(value: int, digits: int) -> str:
    if type(value) is not int or not 0 <= value <= MAX_MICROS:
        raise ValueError("micros must be a nonnegative signed-bigint value")
    whole, fraction = divmod(value, 10**digits)
    if not fraction:
        return str(whole)
    return f"{whole}.{fraction:0{digits}d}".rstrip("0")


def usdt_to_micros(value: str) -> int:
    return _parse(value, 6)


def units_to_micros(value: str) -> int:
    return _parse(value, 5)


def micros_to_usdt(value: int) -> str:
    return _format(value, 6)


def micros_to_units(value: int) -> str:
    return _format(value, 5)
