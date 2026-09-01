from dataclasses import dataclass


class CashAccessDenied(ValueError):
    pass


def ensure_cash_access(
    mode: str, auth_method: str, telegram_user_id: int | None = None,
    allowlist: tuple[int, ...] = (),
) -> None:
    """Validate the server-owned mode and session provenance for future CASH APIs."""
    if mode != "mock":
        raise CashAccessDenied("cash access is disabled")
    if auth_method not in {"telegram", "dev", "guest"}:
        raise CashAccessDenied("cash access requires a verified test identity")
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
