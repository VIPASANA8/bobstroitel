from dataclasses import dataclass


class CashAccessDenied(ValueError):
    pass


#: Which sessions may reach money, per mode. A dev profile and a guest are
#: identities nobody can be held to; they are fine against pretend money and
#: never against real money, so the rule is written once, here, rather than at
#: each of the four call sites.
IDENTITIES = {
    "mock": frozenset({"telegram", "dev", "guest"}),
    "production": frozenset({"telegram"}),
}


def ensure_cash_access(
    mode: str, auth_method: str, telegram_user_id: int | None = None,
    allowlist: tuple[int, ...] = (),
) -> None:
    """Validate the server-owned mode and session provenance for the CASH APIs."""
    try:
        allowed = IDENTITIES[mode]
    except KeyError:
        raise CashAccessDenied("cash access is disabled") from None
    if auth_method not in allowed:
        raise CashAccessDenied("cash access requires a verified identity")
    if mode == "production" and not (type(telegram_user_id) is int and telegram_user_id > 0):
        raise CashAccessDenied("cash access requires a verified Telegram identity")
    if allowlist and telegram_user_id not in allowlist:
        raise CashAccessDenied("cash access is restricted by the pilot allowlist")


@dataclass(frozen=True)
class CashOperator:
    id: str
    telegram_user_id: int
    tenant_id: str | None
    role: str

    def can_mutate(self) -> bool:
        return self.role in {"operator", "admin"}

    def can_access(self, tenant_id: str | None) -> bool:
        return self.role == "admin" or (tenant_id is not None and tenant_id == self.tenant_id)
