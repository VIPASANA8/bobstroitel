from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import hands, integrity_events, play_accounts, poker_tables, table_runtimes, table_seats


logger = logging.getLogger(__name__)
ACTIVE_SEAT_STATES = ("seated", "held", "leaving")
# Critical monitoring is for fresh runtime failures. Historical nonterminal
# rows remain visible to forensic audits but must not create perpetual alerts.
ORPHAN_HAND_ALERT_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class EscrowMismatch:
    table_id: str
    code: str
    expected_units: int
    actual_units: int
    participant_id: str | None = None

    @property
    def fingerprint(self) -> str:
        return "|".join(
            (self.table_id, self.code, self.participant_id or "", str(self.expected_units), str(self.actual_units))
        )

    def payload(self) -> dict[str, object]:
        return {
            "table_id": self.table_id,
            "code": self.code,
            "participant_id": self.participant_id,
            "expected_units": self.expected_units,
            "actual_units": self.actual_units,
            "difference_units": self.expected_units - self.actual_units,
        }


class EscrowIntegrityMonitor:
    """Detect and report ledger/seat-stack mismatches without mutating balances."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        interval_seconds: float | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.interval_seconds = max(5.0, float(interval_seconds or os.getenv("POKER8_ESCROW_CHECK_INTERVAL_SECONDS", "30")))
        self.webhook_url = webhook_url if webhook_url is not None else os.getenv("POKER8_ESCROW_ALERT_WEBHOOK_URL", "")
        self.telegram_bot_token = os.getenv("POKER8_ALERT_TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("POKER8_ALERT_TELEGRAM_CHAT_ID", "")
        self._next_check_at = 0.0
        self._open_fingerprints: set[str] = set()
        self.last_check_at: datetime | None = None
        self.last_check_duration_ms: float | None = None
        self.last_finding_count = 0
        self.last_error: str | None = None

    async def maybe_check(self) -> None:
        now = time.monotonic()
        if now < self._next_check_at:
            return
        self._next_check_at = now + self.interval_seconds
        await self.check()

    async def check(self) -> list[EscrowMismatch]:
        started = time.perf_counter()
        findings: list[EscrowMismatch] = []
        try:
            async with self.session_factory() as session:
                table_ids = (await session.execute(select(poker_tables.c.id))).scalars().all()
                for table_id in table_ids:
                    findings.extend(await self._table_findings(session, table_id))

                current = {finding.fingerprint: finding for finding in findings}
                opened = [finding for fingerprint, finding in current.items() if fingerprint not in self._open_fingerprints]
                resolved = self._open_fingerprints.difference(current)
                for finding in opened:
                    await self._record(session, "escrow_stack_mismatch", finding.payload())
                    logger.error("poker8_escrow_stack_mismatch", extra=finding.payload())
                for fingerprint in resolved:
                    table_id, code, participant_id, expected, actual = fingerprint.split("|", 4)
                    payload = {
                        "table_id": table_id,
                        "code": code,
                        "participant_id": participant_id or None,
                        "expected_units": int(expected),
                        "actual_units": int(actual),
                    }
                    await self._record(session, "escrow_stack_mismatch_resolved", payload)
                    logger.info("poker8_escrow_stack_mismatch_resolved", extra=payload)
                self._open_fingerprints = set(current)

            for finding in opened:
                await self._send_alert(finding.payload())
            return findings
        except Exception as error:
            self.last_error = str(error)
            raise
        finally:
            self.last_check_at = datetime.now(timezone.utc)
            self.last_check_duration_ms = round((time.perf_counter() - started) * 1000, 2)
            self.last_finding_count = len(findings)

    async def _table_findings(self, session: AsyncSession, table_id: str) -> list[EscrowMismatch]:
        seats = (
            await session.execute(
                select(table_seats).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.state.in_(ACTIVE_SEAT_STATES),
                )
            )
        ).mappings().all()
        accounts = (
            await session.execute(
                select(play_accounts).where(
                    (play_accounts.c.owner_kind == "table")
                    & (play_accounts.c.owner_id == table_id)
                    & (play_accounts.c.account_kind == "escrow")
                )
            )
        ).mappings().all()
        table_escrow = int(accounts[0]["balance_units"]) if accounts else 0
        expected_table_escrow = sum(
            int(seat["stack_units"]) for seat in seats if seat["occupant_kind"] == "user"
        )
        findings: list[EscrowMismatch] = []
        if table_escrow != expected_table_escrow:
            findings.append(EscrowMismatch(
                table_id, "table_user_escrow", expected_table_escrow, table_escrow
            ))

        for seat in seats:
            if seat["occupant_kind"] != "system" or not seat["system_player_id"]:
                continue
            account = (
                await session.execute(
                    select(play_accounts.c.balance_units).where(
                        play_accounts.c.owner_kind == "system",
                        play_accounts.c.owner_id == seat["system_player_id"],
                        play_accounts.c.account_kind == "escrow",
                    )
                )
            ).scalar_one_or_none()
            actual = int(account or 0)
            expected = int(seat["stack_units"])
            if actual != expected:
                findings.append(EscrowMismatch(
                    table_id, "system_player_escrow", expected, actual, seat["system_player_id"]
                ))
        runtime_hand_id = (
            await session.execute(
                select(table_runtimes.c.private_state_json["hand_id"].as_string())
                .where(table_runtimes.c.table_id == table_id)
            )
        ).scalar_one_or_none()
        orphaned_hands = (
            await session.execute(
                select(hands.c.id).where(
                    hands.c.table_id == table_id,
                    hands.c.terminal == False,
                    hands.c.started_at >= datetime.now(timezone.utc) - ORPHAN_HAND_ALERT_WINDOW,
                )
            )
        ).scalars().all()
        for hand_id in orphaned_hands:
            if hand_id != runtime_hand_id:
                findings.append(EscrowMismatch(
                    table_id, "orphaned_nonterminal_hand", 0, 1, hand_id
                ))
        return findings

    async def _record(self, session: AsyncSession, event_type: str, payload: dict[str, object]) -> None:
        await session.execute(integrity_events.insert().values(
            id=uuid.uuid4().hex,
            table_id=str(payload["table_id"]),
            event_type=event_type,
            public_payload_json=payload,
        ))
        await session.commit()

    async def _send_alert(self, payload: dict[str, object]) -> None:
        body = json.dumps({"event": "poker8_escrow_stack_mismatch", **payload}).encode("utf-8")

        def post_webhook() -> None:
            request = urllib.request.Request(
                self.webhook_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                response.read(1)

        def post_telegram() -> None:
            telegram_body = json.dumps({
                "chat_id": self.telegram_chat_id,
                "text": (
                    "Poker8: критическая рассинхронизация escrow\\n"
                    f"Стол: {payload['table_id']}\\n"
                    f"Тип: {payload['code']}\\n"
                    f"Ожидалось: {payload['expected_units']}\\n"
                    f"Фактически: {payload['actual_units']}"
                ),
            }).encode("utf-8")
            request = urllib.request.Request(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                data=telegram_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                response.read(1)

        deliveries = []
        if self.webhook_url:
            deliveries.append(post_webhook)
        if self.telegram_bot_token and self.telegram_chat_id:
            deliveries.append(post_telegram)
        for delivery in deliveries:
            try:
                await asyncio.to_thread(delivery)
            except Exception:
                logger.exception("poker8_escrow_alert_delivery_failed", extra={"table_id": payload["table_id"]})
