class DepositReconciler:
    def __init__(self, deposits):
        self.deposits = deposits

    async def run_once(self):
        from sqlalchemy import select
        from online.schema import cash_payment_events
        from cash.trc20 import TransferEvent

        await self.deposits.expire_due()
        async with self.deposits.sessions() as session:
            rows = (await session.execute(select(cash_payment_events).where(
                cash_payment_events.c.status == "observed"
            ).order_by(cash_payment_events.c.created_at))).mappings().all()
        for row in rows:
            await self.deposits.observe(TransferEvent(
                provider=row["provider"], external_event_id=row["external_event_id"],
                tx_hash=row["tx_hash"], event_index=row["event_index"], network=row["network"],
                token_contract=row["token_contract"], destination_address=row["destination_address"],
                amount_micros=row["amount_micros"], occurred_at=row["occurred_at"],
            ))
        return len(rows)
