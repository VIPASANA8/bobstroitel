class CashAccessDenied(ValueError):
    pass


def ensure_cash_access(mode: str, auth_method: str) -> None:
    """Validate the server-owned mode and session provenance for future CASH APIs."""
    if mode != "mock":
        raise CashAccessDenied("cash access is disabled")
    if auth_method not in {"telegram", "dev", "guest"}:
        raise CashAccessDenied("cash access requires a verified test identity")
