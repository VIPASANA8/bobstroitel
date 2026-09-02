from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_, or_, select

from cash.amounts import kopecks_to_rub, micros_to_usdt
from cash.fiat_orders import FEE_ACCOUNT, PROVIDER
from online.schema import cash_accounts, cash_entries, cash_fiat_orders, cash_transactions


def _signed(micros: int) -> str:
    return ("-" if micros < 0 else "") + micros_to_usdt(abs(int(micros)))


async def daily_fiat_reconciliation(sessions, day):
    """Compare, order by order, what the user was told with what the ledger posted.

    Independent of the credit path: it reads the orders and the ledger
    separately and only then asks whether they agree.
    """
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    async with sessions() as session:
        orders = (await session.execute(select(cash_fiat_orders).where(
            cash_fiat_orders.c.status == "credited",
            cash_fiat_orders.c.updated_at >= start,
            cash_fiat_orders.c.updated_at < end,
        ).order_by(cash_fiat_orders.c.updated_at))).mappings().all()
        identifiers = [row["id"] for row in orders]
        postings = (await session.execute(
            select(
                cash_transactions.c.reference_id,
                cash_accounts.c.kind,
                cash_accounts.c.reference_id.label("account_reference"),
                cash_entries.c.amount_micros,
            )
            .select_from(cash_transactions)
            .join(cash_entries, cash_entries.c.transaction_id == cash_transactions.c.id)
            .join(cash_accounts, cash_accounts.c.id == cash_entries.c.account_id)
            .where(cash_transactions.c.scope == "fiat-deposit", or_(
                and_(cash_transactions.c.created_at >= start, cash_transactions.c.created_at < end),
                cash_transactions.c.reference_id.in_(identifiers or [""]),
            ))
        )).mappings().all()
        balances = dict((await session.execute(select(
            cash_accounts.c.reference_id, cash_accounts.c.balance_micros,
        ).where(
            cash_accounts.c.kind == "clearing",
            cash_accounts.c.reference_id.in_([PROVIDER, FEE_ACCOUNT]),
        ))).all())

    posted: dict[str, dict[str, int]] = {}
    for row in postings:
        entry = posted.setdefault(row["reference_id"], {"credited": 0, "fee": 0, "clearing": 0})
        if row["kind"] == "available":
            entry["credited"] += row["amount_micros"]
        elif row["account_reference"] == FEE_ACCOUNT:
            entry["fee"] += row["amount_micros"]
        elif row["account_reference"] == PROVIDER:
            entry["clearing"] += row["amount_micros"]

    mismatches = []
    quoted = {"credited": 0, "fee": 0, "kopecks": 0}
    for order in orders:
        quoted["credited"] += order["requested_micros"]
        quoted["fee"] += order["fee_micros"]
        quoted["kopecks"] += order["fiat_kopecks"] or 0
        entry = posted.get(order["id"])
        if entry is None:
            mismatches.append({"order_id": order["id"], "reason": "credited order without a ledger posting"})
            continue
        if entry["credited"] != order["requested_micros"]:
            mismatches.append({
                "order_id": order["id"],
                "reason": f"credited {_signed(entry['credited'])} USDT against a quote of "
                          f"{micros_to_usdt(order['requested_micros'])} USDT",
            })
        if entry["fee"] != order["fee_micros"]:
            mismatches.append({
                "order_id": order["id"],
                "reason": f"fee {_signed(entry['fee'])} USDT against "
                          f"{micros_to_usdt(order['fee_micros'])} USDT on the order",
            })
        if entry["clearing"] != -(order["requested_micros"] + order["fee_micros"]):
            mismatches.append({
                "order_id": order["id"],
                "reason": f"clearing moved {_signed(entry['clearing'])} USDT for a charge of "
                          f"{micros_to_usdt(order['requested_micros'] + order['fee_micros'])} USDT",
            })
    for reference_id in posted.keys() - set(identifiers):
        mismatches.append({
            "order_id": reference_id,
            "reason": "ledger posting whose order was not credited on this day",
        })

    ledger = {name: sum(entry[name] for entry in posted.values())
              for name in ("credited", "fee", "clearing")}
    return {
        "day": day.isoformat(),
        "orders": {
            "count": len(orders),
            "credited_usdt": micros_to_usdt(quoted["credited"]),
            "fee_usdt": micros_to_usdt(quoted["fee"]),
            "charged_rub": kopecks_to_rub(quoted["kopecks"]),
        },
        "ledger": {
            "credited_usdt": _signed(ledger["credited"]),
            "fee_usdt": _signed(ledger["fee"]),
            "clearing_usdt": _signed(ledger["clearing"]),
        },
        "balances": {
            "clearing_usdt": _signed(balances.get(PROVIDER, 0)),
            "fee_usdt": _signed(balances.get(FEE_ACCOUNT, 0)),
        },
        "mismatches": mismatches,
        "balanced": not mismatches,
    }
