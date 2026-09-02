from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from cash.leader_poller import LeaderPoller, PoisonedFeed
from cash.trc20 import TransferEvent
from online.schema import cash_partner_cursors


PROVIDER = "trc20-tron"
NETWORK = "TRC20"
# USDT on TRON mainnet. Anything else arriving at the address is not a deposit,
# and on TRON something else arrives constantly.
MAINNET_USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_DECIMALS = 6
PAGE_SIZE = 200


def _text(row, key, limit=128) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value or len(value) > limit:
        raise PoisonedFeed(f"invalid TRON transfer field {key}")
    return value


class Trc20DepositWatcher(LeaderPoller):
    """Read-only TRC20 deposit watcher. It holds no key and can move nothing.

    It reads *confirmed* transfers of one contract to one address and hands them
    to the same `DepositService.observe` the mock feeds, so matching, the exact
    expected amount, deduplication and the ledger posting are unchanged code.

    `only_confirmed=true` means the transfer is in a solidified TRON block --
    signed by more than two thirds of the super representatives and no longer
    reversible. That, not a confirmation count of our own, is the answer to a
    reorg: an unsolidified transfer is never read, so it can never be credited
    and then vanish.
    """

    lock_key = 8202620

    def __init__(
        self, deposits, *, base_url: str, address: str, contract: str = MAINNET_USDT,
        api_key: str = "", transport=None, idle_seconds: float = 10.0, now=None,
    ):
        super().__init__(deposits.sessions, idle_seconds=idle_seconds, now=now)
        if not base_url.startswith("https://"):
            raise ValueError("the TRON endpoint must be HTTPS")
        if not address or not contract:
            raise ValueError("the watcher needs one address and one token contract")
        self.deposits = deposits
        self.address = address
        self.contract = contract
        self.ignored = 0
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"TRON-PRO-API-KEY": api_key} if api_key else {},
            verify=True, transport=transport, timeout=httpx.Timeout(20, connect=5),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def poll(self) -> bool:
        cursor = await self._cursor()
        rows = await self._fetch(cursor)
        events, latest = self._parse(rows)
        for event in events:
            await self.deposits.observe(event)
        if latest > cursor:
            await self._save_cursor(latest)
        # A full page means the chain is ahead of us; come back without idling.
        return len(rows) >= PAGE_SIZE

    async def _fetch(self, cursor: int) -> list:
        response = await self._client.get(
            f"/v1/accounts/{self.address}/transactions/trc20",
            params={
                "only_confirmed": "true", "only_to": "true",
                "contract_address": self.contract, "min_timestamp": cursor,
                "limit": PAGE_SIZE, "order_by": "block_timestamp,asc",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise PoisonedFeed("invalid TRON transfer page")
        return payload["data"]

    def _parse(self, rows) -> tuple[list[TransferEvent], int]:
        events: list[TransferEvent] = []
        latest = 0
        seen: Counter[str] = Counter()
        for row in rows:
            if not isinstance(row, dict):
                raise PoisonedFeed("invalid TRON transfer")
            timestamp = row.get("block_timestamp")
            if not isinstance(timestamp, int) or timestamp <= 0:
                raise PoisonedFeed("invalid TRON block timestamp")
            latest = max(latest, timestamp)
            token = row.get("token_info")
            token = token if isinstance(token, dict) else {}
            if (
                row.get("type") != "Transfer"
                or row.get("to") != self.address
                or token.get("address") != self.contract
                or token.get("decimals") != USDT_DECIMALS
            ):
                # Anyone can send anything to a public address, and on TRON they
                # do. Only the one contract this watcher is pointed at can ever
                # become a payment event; the rest is counted and dropped.
                self.ignored += 1
                continue
            tx_hash = _text(row, "transaction_id")
            value = row.get("value")
            if not isinstance(value, str) or not value.isdigit():
                raise PoisonedFeed("invalid TRON transfer value")
            index = seen[tx_hash]
            seen[tx_hash] += 1
            events.append(TransferEvent(
                provider=PROVIDER, external_event_id=f"{tx_hash}:{index}", tx_hash=tx_hash,
                event_index=index, network=NETWORK, token_contract=self.contract,
                destination_address=self.address, amount_micros=int(value),
                occurred_at=datetime.fromtimestamp(timestamp / 1000, timezone.utc),
            ))
        return events, latest

    async def _cursor(self) -> int:
        async with self.sessions() as session:
            return await session.scalar(select(cash_partner_cursors.c.offset).where(
                cash_partner_cursors.c.provider == PROVIDER,
            )) or 0

    async def _save_cursor(self, value: int) -> None:
        # Saved inclusively: the boundary millisecond is read again next time and
        # deduplicated by the event key, which is cheaper than losing a transfer
        # that shared a timestamp with the last one.
        async with self.sessions() as session:
            async with session.begin():
                await session.execute(insert(cash_partner_cursors).values(
                    provider=PROVIDER, offset=value, updated_at=self.now(),
                ).on_conflict_do_update(
                    index_elements=["provider"],
                    set_={"offset": value, "updated_at": self.now()},
                ))
