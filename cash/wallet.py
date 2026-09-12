from sqlalchemy import select

from cash.amounts import kopecks_to_rub, micros_to_units, micros_to_usdt
from cash.ids import human_id, partner_number
from online.schema import (
    cash_accounts, cash_deposits, cash_entries, cash_fiat_orders, cash_transactions,
    cash_withdrawals,
)


class WalletService:
    def __init__(self, session_factory):
        self.sessions = session_factory

    async def get(self, user_id: str):
        async with self.sessions() as session:
            accounts = (await session.execute(select(
                cash_accounts.c.kind, cash_accounts.c.balance_micros
            ).where(cash_accounts.c.user_id == user_id))).all()
            journal = (await session.execute(select(
                cash_transactions.c.id, cash_transactions.c.scope, cash_transactions.c.kind,
                cash_transactions.c.reference_id,
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

    async def operations(self, user_id: str, *, limit: int = 100):
        """Every deposit, ₽ order and withdrawal the player ever asked for --
        the cancelled and the expired included -- newest first.

        The ledger only knows the ones that moved money; a player asking
        "where is my deposit" is asking about one that did not.
        """
        limit = max(1, min(limit, 100))
        async with self.sessions() as session:
            deposits = (await session.execute(select(cash_deposits).where(
                cash_deposits.c.user_id == user_id
            ).order_by(cash_deposits.c.created_at.desc()).limit(limit))).mappings().all()
            orders = (await session.execute(select(cash_fiat_orders).where(
                cash_fiat_orders.c.user_id == user_id
            ).order_by(cash_fiat_orders.c.created_at.desc()).limit(limit))).mappings().all()
            withdrawals = (await session.execute(select(cash_withdrawals).where(
                cash_withdrawals.c.user_id == user_id
            ).order_by(cash_withdrawals.c.created_at.desc()).limit(limit))).mappings().all()
        rows = [_deposit_row(row) for row in deposits]
        rows += [_fiat_order_row(row) for row in orders]
        rows += [_withdrawal_row(row) for row in withdrawals]
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return [{**row, "created_at": row["created_at"].isoformat(),
                 "updated_at": row["updated_at"].isoformat()} for row in rows[:limit]]


#: What each state is called to the player. The keys are the check
#: constraints in online/schema.py, so a new state shows up here as its raw
#: name until it is given one.
STATUS_RU = {
    "deposit": {
        "created": "ожидает перевода", "awaiting_transfer": "ожидает перевода",
        "confirmed": "перевод получен", "credited": "зачислено", "expired": "истекла",
        "cancelled": "отменена", "review_required": "на проверке",
    },
    "fiat_order": {
        "requesting": "ищем трейдера", "unavailable": "трейдер не найден",
        "awaiting_user": "ожидает оплаты", "waiting_trader": "ждём трейдера",
        "clarifying": "уточнение платежа", "credited": "зачислено", "expired": "истекла",
        "cancelled": "отменена", "review_required": "на проверке",
    },
    "withdrawal": {
        "requested": "создан", "reserved": "на рассмотрении", "approved": "одобрен",
        "sending": "отправляется", "submitted": "отправлен", "confirmed": "выплачен",
        "rejected": "отклонён", "cancelled": "отменён", "unknown": "на сверке",
    },
}
#: The states where the money actually moved.
SETTLED = {"credited", "confirmed"}


def status_ru(kind: str, status: str) -> str:
    return STATUS_RU.get(kind, {}).get(status, status)


def mask(value: str | None) -> str | None:
    """A card, a phone or an address with its middle hidden: enough to tell
    which one it was, not enough to pay into. Only the first «·»-separated
    part is the number; a bank name and a holder stay readable."""
    if not value:
        return value
    head, sep, tail = value.partition(" · ")
    number = head.strip()
    shown = number[:1] + "****" if len(number) <= 6 else number[:2] + "****" + number[-4:]
    return shown + (sep + tail if sep else "")


def _deposit_row(row) -> dict:
    return {
        "id": row["id"], "number": human_id("deposit", row["id"]),
        "kind": "deposit", "status": row["status"],
        "status_label": status_ru("deposit", row["status"]),
        "settled": row["status"] in SETTLED,
        "amount_micros": row["expected_micros"], "amount_usdt": micros_to_usdt(row["expected_micros"]),
        "fiat_rub": None, "network": row["network"],
        "requisites": mask(row["destination_address"]), "partner_order_id": None,
        "tx_hash": None, "detail": None,
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _fiat_order_row(row) -> dict:
    return {
        "id": row["id"], "number": human_id("fiat_order", row["id"]),
        "kind": "fiat_order", "status": row["status"],
        "status_label": status_ru("fiat_order", row["status"]),
        "settled": row["status"] in SETTLED,
        "amount_micros": row["requested_micros"], "amount_usdt": micros_to_usdt(row["requested_micros"]),
        "fiat_rub": kopecks_to_rub(row["fiat_kopecks"]) if row["fiat_kopecks"] else None,
        "network": "P2P_RUB", "requisites": mask(row["requisites"]),
        "partner_order_id": partner_number(row["partner_order_id"]),
        "tx_hash": None, "detail": row["detail"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _withdrawal_row(row) -> dict:
    kopecks = row["fiat_kopecks"] or row["quote_kopecks"]
    return {
        "id": row["id"], "number": human_id("withdrawal", row["id"]),
        "kind": "withdrawal", "status": row["status"],
        "status_label": status_ru("withdrawal", row["status"]),
        "settled": row["status"] in SETTLED,
        "amount_micros": -row["amount_micros"], "amount_usdt": micros_to_usdt(row["amount_micros"]),
        "fiat_rub": kopecks_to_rub(kopecks) if kopecks else None,
        "network": row["network"], "requisites": mask(row["destination_address"]),
        "partner_order_id": None, "tx_hash": row["tx_hash"], "detail": row["detail"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }
