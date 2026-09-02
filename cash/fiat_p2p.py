from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


CASE8_MIN_MICROS = 20_000_000
CASE8_MAX_MICROS = 1_000_000_000
MICROS_PER_USDT_CENT = 10_000


def usdt_micros_to_case8_amount(amount_micros: int) -> int:
    if type(amount_micros) is not int or not CASE8_MIN_MICROS <= amount_micros <= CASE8_MAX_MICROS:
        raise ValueError("fiat P2P amount must be between 20 and 1000 USDT")
    if amount_micros % MICROS_PER_USDT_CENT:
        raise ValueError("CASE8 partner amount requires whole USDT cents")
    return amount_micros // MICROS_PER_USDT_CENT


def quote_with_fee(requested_micros: int, fee_bps: int) -> tuple[int, int]:
    """Poker8 charges its deposit fee on top of what the user is credited.

    The partner only accepts whole USDT cents, so the charge rounds up to one
    and the rounding lands in the fee, never in the user's balance.
    """
    if type(requested_micros) is not int or requested_micros <= 0:
        raise ValueError("fiat P2P amount must be a positive integer of micros")
    if type(fee_bps) is not int or not 0 <= fee_bps <= 1_000:
        raise ValueError("the deposit fee must be between 0 and 10 percent")
    charged = -(-requested_micros * (10_000 + fee_bps) // 10_000)
    charged = -(-charged // MICROS_PER_USDT_CENT) * MICROS_PER_USDT_CENT
    return charged, charged - requested_micros


@dataclass(frozen=True)
class PartnerOrder:
    partner_order_id: int
    fiat_kopecks: int
    requisites: str
    expires_at: datetime
    trader_username: str | None = None


@dataclass(frozen=True)
class PartnerEvent:
    event_id: int
    partner_order_id: int
    status: str
    detail: str | None = None


class PartnerProtocolError(ValueError):
    pass


def _pick(raw: dict[str, Any], upper: str, lower: str) -> Any:
    return raw[upper] if upper in raw else raw.get(lower)


def _integer(raw: dict[str, Any], upper: str, lower: str) -> int:
    value = _pick(raw, upper, lower)
    if isinstance(value, bool):
        raise PartnerProtocolError(f"invalid partner field {upper}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PartnerProtocolError(f"invalid partner field {upper}") from exc
    if str(parsed) != str(value) and not isinstance(value, int):
        raise PartnerProtocolError(f"invalid partner field {upper}")
    return parsed


def _kopecks(raw: dict[str, Any], upper: str, lower: str) -> int:
    """Partner ``Amount`` is RUB with kopecks after a comma: ``1850,75``."""
    value = _pick(raw, upper, lower)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise PartnerProtocolError(f"invalid partner field {upper}")
    match = re.fullmatch(r"([0-9]{1,12})(?:[.,]([0-9]{1,2}))?", str(value).strip().replace(" ", ""))
    if match is None:
        raise PartnerProtocolError(f"invalid partner field {upper}")
    whole, fraction = match.groups()
    return int(whole) * 100 + int((fraction or "").ljust(2, "0"))


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PartnerProtocolError("invalid partner expiry")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PartnerProtocolError("invalid partner expiry") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class Case8PartnerClient:
    """Pinned CASE8 transport with mandatory CA verification."""

    def __init__(
        self, base_url: str, token: str, *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not base_url.startswith("https://") or not token:
            raise ValueError("CASE8 partner requires an HTTPS URL and token")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Token": token},
            verify=True,
            transport=transport,
            timeout=httpx.Timeout(35, connect=5),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_order(self, amount_micros: int, currency: str) -> PartnerOrder | None:
        if currency != "RUB":
            raise ValueError("the first fiat P2P pilot supports RUB only")
        response = await self._client.post("/order", params={
            "amount": usdt_micros_to_case8_amount(amount_micros),
            "currency": currency,
        }, timeout=5)
        if response.status_code == 204:
            return None
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict):
            raise PartnerProtocolError("invalid partner order payload")
        requisites = _pick(raw, "Method", "method")
        if not isinstance(requisites, str) or not requisites.strip():
            raise PartnerProtocolError("invalid partner field Method")
        username = _pick(raw, "Username", "username")
        if username is not None and not isinstance(username, str):
            raise PartnerProtocolError("invalid partner field Username")
        return PartnerOrder(
            partner_order_id=_integer(raw, "ID", "id"),
            fiat_kopecks=_kopecks(raw, "Amount", "amount"),
            requisites=requisites,
            expires_at=_utc(_pick(raw, "Expires", "expires")),
            trader_username=username,
        )

    async def me(self) -> dict[str, Any]:
        """Health and business data; ``Fee`` is the partner's commission snapshot."""
        response = await self._client.get("/me", timeout=5)
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict):
            raise PartnerProtocolError("invalid partner /me payload")
        return raw

    # ponytail: no retry on /order or /notify. POST /order is not idempotent, so
    # a retry can buy a second trader order; the user simply presses again.
    async def notify(self, partner_order_id: int, *, cancel: bool) -> None:
        response = await self._client.post("/notify", params={
            "order_id": partner_order_id,
            "cancel": str(cancel).lower(),
        }, timeout=5)
        response.raise_for_status()

    async def poll_events(self, offset: int) -> tuple[list[PartnerEvent], int]:
        response = await self._client.get("/events", params={"offset": offset}, timeout=35)
        if response.status_code == 204:
            return [], offset
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise PartnerProtocolError("invalid partner events payload")

        events = []
        next_offset = offset
        for raw in payload:
            if not isinstance(raw, dict):
                raise PartnerProtocolError("invalid partner event")
            event_id = _integer(raw, "ID", "id")
            order_id = _integer(raw, "OrderID", "order_id")
            status = _pick(raw, "Status", "status")
            if status in {"WaitingUser", "WaitingTrader"}:
                event = None
            elif status == "Expired":
                event = PartnerEvent(event_id, order_id, "expired")
            elif status == "Clarifying":
                detail = _pick(raw, "Reason", "reason") or _pick(raw, "Message", "message")
                event = PartnerEvent(event_id, order_id, "clarifying", detail)
            elif status in {"CanceledByUser", "CanceledByTrader", "CanceledBySupport"}:
                event = PartnerEvent(event_id, order_id, "cancelled", status)
            elif status in {"CompletedByTrader", "CompletedBySupport"}:
                event = PartnerEvent(event_id, order_id, "completed")
            else:
                raise PartnerProtocolError(f"unknown partner event status: {status!r}")
            next_offset = max(next_offset, event_id)
            if event is not None:
                events.append(event)
        return events, next_offset


class MockCase8Partner:
    def __init__(self, *, rub_per_usdt: int = 90):
        if type(rub_per_usdt) is not int or rub_per_usdt <= 0:
            raise ValueError("mock RUB rate must be a positive integer")
        self._rate = rub_per_usdt
        self._next_order = 1
        self._next_event = 1
        self._orders: dict[int, dict[str, Any]] = {}
        self._events: list[PartnerEvent] = []

    async def create_order(self, amount_micros: int, currency: str) -> PartnerOrder:
        if currency != "RUB":
            raise ValueError("the first fiat P2P pilot supports RUB only")
        usdt_micros_to_case8_amount(amount_micros)
        order_id = self._next_order
        self._next_order += 1
        self._orders[order_id] = {"amount_micros": amount_micros, "finished": False}
        return PartnerOrder(
            partner_order_id=order_id,
            fiat_kopecks=amount_micros * self._rate // 10_000,
            requisites=f"4276 **** **** {1000 + order_id:04d}",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            trader_username="mock_trader",
        )

    async def me(self) -> dict[str, Any]:
        return {"ID": 0, "Title": "mock trader", "Fee": 0, "Deposit": 0}

    async def notify(self, partner_order_id: int, *, cancel: bool) -> None:
        order = self._orders.get(partner_order_id)
        if order is None:
            raise LookupError("unknown mock partner order")
        if order["finished"]:
            return
        order["finished"] = True
        self._events.append(PartnerEvent(
            self._next_event, partner_order_id,
            "cancelled" if cancel else "completed",
            "CanceledByUser" if cancel else None,
        ))
        self._next_event += 1

    async def poll_events(self, offset: int) -> tuple[list[PartnerEvent], int]:
        events = [event for event in self._events if event.event_id > offset]
        return events, max([offset, *(event.event_id for event in events)])
