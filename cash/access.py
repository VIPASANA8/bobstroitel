from dataclasses import dataclass


class CashAccessDenied(ValueError):
    pass


def ensure_cash_access(mode: str, auth_method: str) -> None:
    """Validate the server-owned mode and session provenance for future CASH APIs."""
    if mode != "mock":
        raise CashAccessDenied("cash access is disabled")
    if auth_method not in {"telegram", "dev", "guest"}:
        raise CashAccessDenied("cash access requires a verified test identity")


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
