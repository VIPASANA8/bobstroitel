from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from cash.antifraud import cancelled_after_payment
from cash.fiat_orders import LOST_ANSWER_SECONDS
from cash.fiat_reconciliation import daily_fiat_reconciliation
from online.alerts import AlertNotifier
from online.catalogue import CASH_USDT
from online.schema import (
    cash_fiat_events, cash_fiat_orders, cash_withdrawals, poker_tables, table_runtimes,
)


logger = logging.getLogger(__name__)
# Trader requisites are payment data. A week is long enough to settle a dispute
# and short enough that a stolen backup is not a card dump.
REQUISITES_RETENTION = timedelta(days=7)


class CashWatchdog:
    """Turns the CASH numbers into one alert each, and one more when they clear.

    Findings live in memory: after a restart a standing problem alerts once
    more, which is the safe direction to be wrong in.
    """

    def __init__(
        self, sessions, *, poller=None, chain=None, fiat=None, notifier=None,
        interval_seconds: float = 60.0, stall_seconds: float = 300.0,
        housekeeping_seconds: float = 3600.0, now=None,
    ):
        self.sessions = sessions
        self.poller = poller
        self.chain = chain
        self.fiat = fiat
        self.notifier = notifier or AlertNotifier()
        self.interval_seconds = interval_seconds
        self.stall_seconds = stall_seconds
        self.housekeeping_seconds = housekeeping_seconds
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.open_findings: dict[str, str] = {}
        self.last_check_at: datetime | None = None
        self.purged_requisites = 0
        self._next_check_at = 0.0
        self._next_housekeeping_at = 0.0
        self._reconciliation: dict[str, str] = {}

    async def maybe_check(self) -> None:
        if time.monotonic() < self._next_check_at:
            return
        self._next_check_at = time.monotonic() + self.interval_seconds
        await self.check()

    async def check(self) -> dict[str, str]:
        if time.monotonic() >= self._next_housekeeping_at:
            self._next_housekeeping_at = time.monotonic() + self.housekeeping_seconds
            await self._housekeeping()
        findings = await self.findings()
        for key, text in findings.items():
            if key not in self.open_findings:
                await self.notifier.send(
                    "poker8_cash_alert", f"🚨 Poker8 CASH: {text}", {"finding": key, "detail": text},
                )
        for key, text in self.open_findings.items():
            if key not in findings:
                await self.notifier.send(
                    "poker8_cash_alert_cleared", f"✅ Poker8 CASH: снято — {text}",
                    {"finding": key, "detail": text},
                )
        self.open_findings = findings
        self.last_check_at = self.now()
        return findings

    async def findings(self) -> dict[str, str]:
        now = self.now()
        findings: dict[str, str] = {}
        feeds = (("poller", "поллер партнёра", self.poller), ("chain", "TRC20-наблюдатель", self.chain))
        for key, title, feed in feeds:
            if feed is None:
                continue
            if feed.poisoned:
                findings[f"{key}-poisoned"] = f"{title} остановлен на нечитаемых данных: {feed.last_error}"
            elif feed.leader:
                last = feed.last_success_at
                idle = None if last is None else (now - last).total_seconds()
                if idle is None or idle > self.stall_seconds:
                    findings[f"{key}-stalled"] = (
                        f"{title} не завершал опрос успешно "
                        + ("ни разу" if idle is None else f"{int(idle)} с")
                    )
        async with self.sessions() as session:
            review = await session.scalar(select(func.count()).select_from(cash_fiat_events).where(
                cash_fiat_events.c.status == "review_required",
            ))
            stuck = await session.scalar(select(func.count()).select_from(cash_fiat_orders).where(
                cash_fiat_orders.c.status == "requesting",
                cash_fiat_orders.c.created_at < now - timedelta(seconds=LOST_ANSWER_SECONDS),
            ))
            clarifying = await session.scalar(select(func.count()).select_from(cash_fiat_orders).where(
                cash_fiat_orders.c.status.in_(("clarifying", "review_required")),
            ))
            unknown = await session.scalar(select(func.count()).select_from(cash_withdrawals).where(
                cash_withdrawals.c.status == "unknown",
            ))
            flagged = await cancelled_after_payment(session, since=now - timedelta(days=1))
            paused = await session.scalar(select(func.count()).select_from(
                table_runtimes.join(poker_tables, poker_tables.c.id == table_runtimes.c.table_id)
            ).where(
                poker_tables.c.asset == CASH_USDT,
                poker_tables.c.status == "open",
                table_runtimes.c.phase == "paused",
            ))
        if review:
            findings["fiat-events-review"] = f"событий партнёра на разборе: {review}"
        if stuck:
            findings["fiat-orders-requesting"] = f"заявок зависло в requesting: {stuck}"
        if clarifying:
            findings["fiat-orders-attention"] = f"заявок ждут оператора: {clarifying}"
        if unknown:
            findings["withdrawals-unknown"] = f"выводов в состоянии unknown: {unknown}"
        if paused:
            findings["cash-tables-paused"] = f"CASH-столов остановлено: {paused}"
        for user_id, cancellations in flagged.items():
            findings[f"cancel-after-paid-{user_id}"] = (
                f"пользователь {user_id}: {cancellations} отмен после «я оплатил» за сутки"
            )
        return findings | self._reconciliation

    async def _housekeeping(self) -> None:
        try:
            today = self.now().date()
            self._reconciliation = {}
            for day in (today, today - timedelta(days=1)):
                report = await daily_fiat_reconciliation(self.sessions, day)
                if not report["balanced"]:
                    self._reconciliation[f"reconciliation-{day.isoformat()}"] = (
                        f"сверка за {day.isoformat()} не сходится: "
                        f"{report['mismatches'][0]['reason']}"
                    )
            if self.fiat is not None:
                self.purged_requisites += await self.fiat.purge_requisites(
                    self.now() - REQUISITES_RETENTION,
                )
        except Exception:
            logger.exception("poker8 cash watchdog housekeeping failed")
