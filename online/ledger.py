from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Mapping

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import play_accounts, play_entries, play_transactions, table_seats


ASSET = "PLAY"
FAUCET_OWNER = ("system", "play_faucet", "faucet")


class InsufficientPlayBalance(ValueError):
    """Raised when a protected play account would become negative."""


@dataclass(frozen=True)
class LedgerResult:
    transaction_id: str
    idempotency_key: str
    available_units: int


class PlayLedger:
    ASSET = ASSET

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def ensure_faucet(self, *, session: AsyncSession | None = None) -> str:
        async def operation(db: AsyncSession) -> str:
            account = await self._ensure_account(db, *FAUCET_OWNER)
            return account["id"]

        return await self._run(operation, session)

    async def ensure_user_wallet(
        self, user_id: str, *, session: AsyncSession | None = None
    ) -> str:
        async def operation(db: AsyncSession) -> str:
            account = await self._ensure_account(db, "user", user_id, "wallet")
            return account["id"]

        return await self._run(operation, session)

    async def available_units(self, user_id: str, *, session: AsyncSession | None = None) -> int:
        async def operation(db: AsyncSession) -> int:
            account = await self._find_account(db, "user", user_id, "wallet")
            return int(account["balance_units"]) if account else 0

        return await self._run(operation, session)

    async def grant(
        self, user_id: str, amount_units: int, idempotency_key: str, *, session: AsyncSession | None = None
    ) -> LedgerResult:
        self._positive(amount_units)
        return await self._transfer(
            kind="faucet_grant",
            reference_type="user",
            reference_id=user_id,
            idempotency_key=idempotency_key,
            entries=[FAUCET_OWNER, ("user", user_id, "wallet")],
            amounts=[-amount_units, amount_units],
            available_owner=("user", user_id, "wallet"),
            session=session,
        )

    async def reserve_buy_in(
        self, user_id: str, table_id: str, amount_units: int, idempotency_key: str, *, session: AsyncSession | None = None
    ) -> LedgerResult:
        self._positive(amount_units)
        return await self._transfer(
            kind="buy_in",
            reference_type="table",
            reference_id=table_id,
            idempotency_key=idempotency_key,
            entries=[("user", user_id, "wallet"), ("table", table_id, "escrow")],
            amounts=[-amount_units, amount_units],
            available_owner=("user", user_id, "wallet"),
            session=session,
        )

    async def add_on(
        self, user_id: str, table_id: str, amount_units: int, idempotency_key: str, *, session: AsyncSession | None = None
    ) -> LedgerResult:
        self._positive(amount_units)
        return await self._transfer(
            kind="add_on",
            reference_type="table",
            reference_id=table_id,
            idempotency_key=idempotency_key,
            entries=[("user", user_id, "wallet"), ("table", table_id, "escrow")],
            amounts=[-amount_units, amount_units],
            available_owner=("user", user_id, "wallet"),
            session=session,
        )

    async def fund_system_seat(
        self,
        system_player_id: str,
        table_id: str,
        amount_units: int,
        idempotency_key: str,
        *,
        session: AsyncSession | None = None,
    ) -> LedgerResult:
        self._positive(amount_units)
        return await self._transfer(
            kind="faucet_grant",
            reference_type="table",
            reference_id=table_id,
            idempotency_key=idempotency_key,
            entries=[FAUCET_OWNER, ("system", system_player_id, "escrow")],
            amounts=[-amount_units, amount_units],
            available_owner=("system", system_player_id, "escrow"),
            session=session,
        )

    async def release_system_seat(
        self,
        system_player_id: str,
        table_id: str,
        idempotency_key: str,
        *,
        session: AsyncSession | None = None,
    ) -> LedgerResult:
        async def operation(db: AsyncSession) -> LedgerResult:
            existing = await self._existing_result(db, idempotency_key, FAUCET_OWNER)
            if existing:
                return existing
            account = await self._find_account(db, "system", system_player_id, "escrow", lock=True)
            amount = int(account["balance_units"]) if account else 0
            if amount <= 0:
                return LedgerResult("", idempotency_key, 0)
            return await self._transfer_in_session(
                db,
                kind="return",
                reference_type="table",
                reference_id=table_id,
                idempotency_key=idempotency_key,
                entries=[("system", system_player_id, "escrow"), FAUCET_OWNER],
                amounts=[-amount, amount],
                available_owner=FAUCET_OWNER,
            )

        return await self._run(operation, session)

    async def transaction_exists(
        self, idempotency_key: str, *, session: AsyncSession | None = None
    ) -> bool:
        """Whether this exact operation has already been posted.

        Callers that also mutate state of their own need this: the ledger call
        alone silently becomes a no-op on a replay, so a caller that updates a
        stack regardless would add chips no money backs.
        """
        async def operation(db: AsyncSession) -> bool:
            row = (
                await db.execute(
                    select(play_transactions.c.id).where(
                        play_transactions.c.idempotency_key == idempotency_key
                    )
                )
            ).first()
            return row is not None

        return await self._run(operation, session)

    async def reconcile_system_escrow(
        self,
        system_player_id: str,
        amount_units: int,
        idempotency_key: str,
        *,
        session: AsyncSession | None = None,
    ) -> LedgerResult:
        """Return escrow a bot's seat no longer accounts for back to the faucet.

        Releases used to be suppressed by a reused idempotency key, so escrow
        kept chips the seat had stopped claiming. A release drains the account
        whole, which clears the excess by itself -- but only for a bot that ever
        gets released, and one sitting on a large stack may never bust. This
        settles the difference for those without waiting.

        Deliberately partial and explicit about the amount: the caller has
        already compared escrow against stack_units, and stack_units is the
        side the game plays from.
        """
        self._positive(amount_units)
        return await self._transfer(
            kind="return",
            reference_type="system_player",
            reference_id=system_player_id,
            idempotency_key=idempotency_key,
            entries=[("system", system_player_id, "escrow"), FAUCET_OWNER],
            amounts=[-amount_units, amount_units],
            available_owner=("system", system_player_id, "escrow"),
            session=session,
        )

    async def return_stack(
        self, user_id: str, table_id: str, idempotency_key: str, *, amount_units: int | None = None,
        session: AsyncSession | None = None
    ) -> LedgerResult:
        async def operation(db: AsyncSession) -> LedgerResult:
            available_owner = ("user", user_id, "wallet")
            existing = await self._existing_result(db, idempotency_key, available_owner)
            if existing:
                return existing
            account = await self._find_account(db, "table", table_id, "escrow", lock=True)
            amount = int(account["balance_units"]) if amount_units is None else int(amount_units)
            if amount < 0:
                raise ValueError("amount_units cannot be negative")
            if account and amount > int(account["balance_units"]):
                raise InsufficientPlayBalance("insufficient table escrow")
            if amount <= 0:
                return LedgerResult("", idempotency_key, await self._balance(db, *available_owner))
            return await self._transfer_in_session(
                db,
                kind="return",
                reference_type="table",
                reference_id=table_id,
                idempotency_key=idempotency_key,
                entries=[("table", table_id, "escrow"), ("user", user_id, "wallet")],
                amounts=[-amount, amount],
                available_owner=("user", user_id, "wallet"),
            )

        return await self._run(operation, session)

    async def settle_hand(
        self,
        hand_id: str,
        escrow_deltas: Mapping[tuple[str, str], int],
        *,
        session: AsyncSession | None = None,
    ) -> LedgerResult:
        entries = [(owner_kind, owner_id, "escrow") for owner_kind, owner_id in escrow_deltas]
        amounts = [int(value) for value in escrow_deltas.values()]
        if sum(amounts) != 0:
            raise ValueError("hand settlement must be balanced")
        return await self._transfer(
            kind="settlement",
            reference_type="hand",
            reference_id=hand_id,
            idempotency_key=f"settlement:{hand_id}",
            entries=entries,
            amounts=amounts,
            available_owner=entries[0] if entries else FAUCET_OWNER,
            session=session,
        )

    async def settle_hand_transfers(
        self,
        hand_id: str,
        transfers: Mapping[tuple[str, str, str], int],
        *,
        session: AsyncSession | None = None,
    ) -> LedgerResult:
        """Post a balanced terminal hand using explicit wallet/escrow accounts."""
        amounts = [int(value) for value in transfers.values()]
        if not transfers or sum(amounts) != 0:
            raise ValueError("hand settlement must be balanced")
        nonzero = [(entry, amount) for entry, amount in zip(transfers, amounts) if amount]
        if not nonzero:
            async def operation(db: AsyncSession) -> LedgerResult:
                owner = next(iter(transfers))
                return LedgerResult("", f"settlement:{hand_id}", await self._balance(db, *owner))

            return await self._run(operation, session)
        entries = [entry for entry, _ in nonzero]
        amounts = [amount for _, amount in nonzero]
        return await self._transfer(
            kind="settlement",
            reference_type="hand",
            reference_id=hand_id,
            idempotency_key=f"settlement:{hand_id}",
            entries=entries,
            amounts=amounts,
            available_owner=entries[0],
            session=session,
        )

    async def table_escrow_units(self, table_id: str, *, session: AsyncSession | None = None) -> int:
        """What the table's shared escrow account actually holds."""
        async def operation(db: AsyncSession) -> int:
            account = await self._find_account(db, "table", table_id, "escrow")
            return int(account["balance_units"]) if account else 0

        return await self._run(operation, session)

    async def cover_escrow_shortfall(
        self, table_id: str, amount_units: int, idempotency_key: str, *, session: AsyncSession | None = None
    ) -> LedgerResult:
        """Top the table's escrow up from the faucet so a settled hand can pay.

        Only ever needed when chips committed to a running hand have already
        left the escrow -- a seat cleared mid-hand takes its whole stack back
        to the wallet, the pot included. The players still owed are paid in
        full and the difference is the house's, which is where a shortfall of
        play money belongs; the alternative is a hand that cannot settle, and
        a table that hangs on it forever.
        """
        self._positive(amount_units)
        return await self._transfer(
            # play_transactions.kind is a CHECK constraint of five values, and
            # this is one of them in every sense that matters: play money
            # entering the system from the faucet. The idempotency key
            # ("shortfall:<hand>") is what names it in the journal, and the
            # integrity event beside it carries the numbers.
            kind="faucet_grant",
            reference_type="table",
            reference_id=table_id,
            idempotency_key=idempotency_key,
            entries=[FAUCET_OWNER, ("table", table_id, "escrow")],
            amounts=[-amount_units, amount_units],
            available_owner=("table", table_id, "escrow"),
            session=session,
        )

    async def escrow_balances(self, table_id: str, *, session: AsyncSession | None = None) -> list[int]:
        """Return all balances participating in a table's escrow conservation check."""
        async def operation(db: AsyncSession) -> list[int]:
            owners: list[tuple[str, str, str]] = [("table", table_id, "escrow")]
            seats = (
                await db.execute(
                    select(table_seats.c.user_id, table_seats.c.system_player_id)
                    .where(table_seats.c.table_id == table_id)
                )
            ).all()
            for user_id, system_player_id in seats:
                if user_id:
                    owners.append(("user", user_id, "wallet"))
                if system_player_id:
                    owners.append(("system", system_player_id, "escrow"))
            balances = []
            for owner_kind, owner_id, account_kind in owners:
                balances.append(await self._balance(db, owner_kind, owner_id, account_kind))
            return balances

        return await self._run(operation, session)

    async def journal(
        self,
        owner_kind: str,
        owner_id: str,
        *,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[dict[str, object]]:
        async def operation(db: AsyncSession) -> list[dict[str, object]]:
            rows = (
                await db.execute(
                    select(
                        play_transactions,
                        play_entries.c.id.label("entry_id"),
                        play_entries.c.amount_units,
                    )
                    .join(play_entries, play_entries.c.transaction_id == play_transactions.c.id)
                    .join(play_accounts, play_accounts.c.id == play_entries.c.account_id)
                    .where(
                        play_accounts.c.owner_kind == owner_kind,
                        play_accounts.c.owner_id == owner_id,
                    )
                    .order_by(desc(play_transactions.c.created_at))
                    .limit(max(1, min(limit, 100)) * 2)
                )
            ).mappings().all()
            return [
                {
                    "transaction_id": row["id"],
                    "entry_id": row["entry_id"],
                    "kind": row["kind"],
                    "idempotency_key": row["idempotency_key"],
                    "reference_type": row["reference_type"],
                    "reference_id": row["reference_id"],
                    "status": row["status"],
                    "amount_units": row["amount_units"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows[: max(1, min(limit, 100))]
            ]

        return await self._run(operation, session)

    async def _transfer(
        self,
        *,
        kind: str,
        reference_type: str,
        reference_id: str,
        idempotency_key: str,
        entries: list[tuple[str, str, str]],
        amounts: list[int],
        available_owner: tuple[str, str, str],
        session: AsyncSession | None,
    ) -> LedgerResult:
        async def operation(db: AsyncSession) -> LedgerResult:
            return await self._transfer_in_session(
                db,
                kind=kind,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                entries=entries,
                amounts=amounts,
                available_owner=available_owner,
            )

        return await self._run(operation, session)

    async def _transfer_in_session(
        self,
        session: AsyncSession,
        *,
        kind: str,
        reference_type: str,
        reference_id: str,
        idempotency_key: str,
        entries: list[tuple[str, str, str]],
        amounts: list[int],
        available_owner: tuple[str, str, str],
    ) -> LedgerResult:
        if len(entries) != len(amounts) or not entries or sum(amounts) != 0:
            raise ValueError("ledger entries must be non-empty and balanced")
        existing = await self._existing_result(session, idempotency_key, available_owner)
        if existing:
            return existing

        keys = list(dict.fromkeys(entries))
        accounts = [await self._ensure_account(session, *key) for key in keys]
        ordered_ids = sorted(account["id"] for account in accounts)
        locked_accounts = (
            await session.execute(
                select(play_accounts)
                .where(play_accounts.c.id.in_(ordered_ids))
                .order_by(play_accounts.c.id)
                .with_for_update()
            )
        ).mappings().all()
        account_by_id = {account["id"]: account for account in locked_accounts}
        accounts = [account_by_id[account["id"]] for account in accounts]
        by_key = {key: account for key, account in zip(keys, accounts)}
        for key, amount in zip(entries, amounts):
            account = by_key[key]
            new_balance = int(account["balance_units"]) + amount
            if account["account_kind"] != "faucet" and new_balance < 0:
                raise InsufficientPlayBalance("insufficient play balance")
        transaction_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        await session.execute(play_transactions.insert().values(
            id=transaction_id,
            kind=kind,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            status="pending",
            created_at=now,
        ))
        for key, amount in zip(entries, amounts):
            account = by_key[key]
            await session.execute(play_entries.insert().values(
                id=uuid.uuid4().hex,
                transaction_id=transaction_id,
                account_id=account["id"],
                amount_units=amount,
                created_at=now,
            ))
            await session.execute(
                update(play_accounts)
                .where(play_accounts.c.id == account["id"])
                .values(balance_units=int(account["balance_units"]) + amount)
            )
        await session.execute(
            update(play_transactions)
            .where(play_transactions.c.id == transaction_id)
            .values(status="posted", posted_at=now)
        )
        return LedgerResult(
            transaction_id,
            idempotency_key,
            await self._balance(session, *available_owner),
        )

    async def _ensure_account(
        self, session: AsyncSession, owner_kind: str, owner_id: str, account_kind: str
    ):
        account = await self._find_account(session, owner_kind, owner_id, account_kind, lock=True)
        if account:
            return account
        await session.execute(play_accounts.insert().values(
            id=uuid.uuid4().hex,
            owner_kind=owner_kind,
            owner_id=owner_id,
            account_kind=account_kind,
            balance_units=0,
        ))
        return await self._find_account(session, owner_kind, owner_id, account_kind, lock=True)

    async def _find_account(
        self,
        session: AsyncSession,
        owner_kind: str,
        owner_id: str,
        account_kind: str,
        *,
        lock: bool = False,
    ):
        query = select(play_accounts).where(
            play_accounts.c.owner_kind == owner_kind,
            play_accounts.c.owner_id == owner_id,
            play_accounts.c.account_kind == account_kind,
        )
        if lock:
            query = query.with_for_update()
        return (await session.execute(query)).mappings().first()

    async def _balance(self, session: AsyncSession, owner_kind: str, owner_id: str, account_kind: str) -> int:
        account = await self._find_account(session, owner_kind, owner_id, account_kind)
        return int(account["balance_units"]) if account else 0

    async def _existing_result(
        self, session: AsyncSession, idempotency_key: str, available_owner: tuple[str, str, str]
    ) -> LedgerResult | None:
        existing = (
            await session.execute(
                select(play_transactions).where(
                    play_transactions.c.idempotency_key == idempotency_key
                )
            )
        ).mappings().first()
        if not existing:
            return None
        return LedgerResult(
            existing["id"],
            idempotency_key,
            await self._balance(session, *available_owner),
        )

    async def _run(self, operation: Callable[[AsyncSession], Awaitable], session: AsyncSession | None):
        if session is not None:
            return await operation(session)
        async with self.session_factory() as db:
            async with db.begin():
                return await operation(db)

    @staticmethod
    def _positive(amount_units: int) -> None:
        if amount_units <= 0:
            raise ValueError("amount_units must be positive")
