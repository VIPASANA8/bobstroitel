from sqlalchemy import select

from cash.amounts import micros_to_units, micros_to_usdt
from online.schema import cash_accounts, cash_entries, cash_transactions


class WalletService:
    def __init__(self, session_factory):
        self.sessions = session_factory

    async def get(self, user_id: str):
        async with self.sessions() as session:
            accounts = (await session.execute(select(
                cash_accounts.c.kind, cash_accounts.c.balance_micros
            ).where(cash_accounts.c.user_id == user_id))).all()
            journal = (await session.execute(select(
                cash_transactions.c.id, cash_transactions.c.kind, cash_transactions.c.reference_id,
                cash_entries.c.amount_micros, cash_transactions.c.created_at,
            ).join(cash_entries, cash_entries.c.transaction_id == cash_transactions.c.id)
             .join(cash_accounts, cash_accounts.c.id == cash_entries.c.account_id)
             .where(cash_accounts.c.user_id == user_id)
             .order_by(cash_transactions.c.created_at.desc()).limit(100))).mappings().all()
        balances = {kind: sum(value for item_kind, value in accounts if item_kind == kind)
                    for kind in ("available", "escrow", "withdrawal")}
        return {
            **{f"{kind}_usdt": micros_to_usdt(value) for kind, value in balances.items()},
            **{f"{kind}_units": micros_to_units(value) for kind, value in balances.items()},
            "journal": [{**dict(row), "amount_usdt": ("-" if row["amount_micros"] < 0 else "")
                         + micros_to_usdt(abs(row["amount_micros"]))} for row in journal],
        }
