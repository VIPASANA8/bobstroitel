from __future__ import annotations

import uuid
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
        raise ValueError("CASE8 amount requires whole USDT cents")
    return amount_micros // MICROS_PER_USDT_CENT


def quote_with_fee(requested_micros: int, fee_bps: int) -> tuple[int, int]:
    """Poker8 charges its deposit fee on top of what the user is credited.

    pservice only accepts whole USDT cents, so the charge rounds up to one and
    the rounding lands in the fee, never in the user's balance.
    """
    if type(requested_micros) is not int or requested_micros <= 0:
        raise ValueError("fiat P2P amount must be a positive integer of micros")
    if type(fee_bps) is not int or not 0 <= fee_bps <= 1_000:
        raise ValueError("the deposit fee must be between 0 and 10 percent")
    charged = -(-requested_micros * (10_000 + fee_bps) // 10_000)
    charged = -(-charged // MICROS_PER_USDT_CENT) * MICROS_PER_USDT_CENT
    return charged, charged - requested_micros


class PartnerProtocolError(ValueError):
    pass


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PartnerProtocolError("invalid pservice timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PartnerProtocolError("invalid pservice timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_utc(value: Any) -> datetime | None:
    return None if value is None else _utc(value)


# --- pservice /api/v1: the layer Poker8 actually integrates with ---------------
#
# The old `/order,/me,/events` + X-Token protocol was pservice's *own* client to
# the raw trader network (docs/case8-p2p-partner-contract.md, "Live inspection").
# Poker8 consumes pservice's REST API instead: create a payment, poll its status,
# credit CASH on completion. There is no event stream to us -- pservice owns the
# partner events; we read one order at a time.

#: Deterministic namespace so one Poker8 user maps to one stable pservice UUID.
_USER_NS = uuid.UUID("0b7b8d2a-8f4e-5c31-9a20-9b6f0e6d5c44")

#: pservice OrderStatus (domain/enums/order_status.py) -> our coarse state.
#: Every non-terminal status lands in the active set the one-open-order index
#: guards; FAILED goes to review_required so a person confirms nothing is owed.
PSERVICE_STATUS = {
    0: "requesting",       # CREATED
    1: "requesting",       # REQUEST_SENT
    2: "expired",          # REQUEST_EXPIRED
    3: "awaiting_user",    # TRADER_FOUND -- requisites are available
    4: "waiting_trader",   # USER_CONFIRMED
    5: "cancelled",        # USER_CANCELLED
    6: "waiting_trader",   # AWAITING_RESULT
    7: "credited",         # COMPLETED -- the only status that moves money
    8: "review_required",  # FAILED
    9: "cancelled",        # CANCELLED
    10: "clarifying",      # CLARIFYING
}
COMPLETED_STATUS = 7


@dataclass(frozen=True)
class PservicePayment:
    """What POST /api/v1/payments returns."""

    order_id: str
    status: int
    expires_at: datetime | None


@dataclass(frozen=True)
class PserviceOrderStatus:
    """What GET /api/v1/payments/{order_id} returns, as much as we use."""

    status: int
    fiat_kopecks: int | None
    requisites: str | None
    trader_username: str | None
    expires_at: datetime | None
    detail: str | None

    @property
    def local_status(self) -> str:
        try:
            return PSERVICE_STATUS[self.status]
        except KeyError:
            raise PartnerProtocolError(f"unknown pservice status {self.status!r}") from None


def _order_status_from(raw: dict[str, Any]) -> PserviceOrderStatus:
    if not isinstance(raw, dict) or "status" not in raw:
        raise PartnerProtocolError("invalid pservice order status payload")
    status = raw.get("status")
    if type(status) is not int:
        raise PartnerProtocolError("pservice status must be an integer")
    fiat = raw.get("fiat_amount_with_commission")
    if fiat is not None and type(fiat) is not int:
        raise PartnerProtocolError("pservice fiat amount must be integer minor units")
    return PserviceOrderStatus(
        status=status,
        fiat_kopecks=fiat,
        requisites=(raw.get("trader_info") or None),
        trader_username=(raw.get("trader_tg") or None),
        expires_at=_optional_utc(raw.get("expires_at")),
        detail=(raw.get("error_reason") or None),
    )


def is_internal_url(url: str) -> bool:
    """True for a target that never leaves the host's private network.

    A Docker service name has no dot; loopback and RFC1918 addresses are private
    by definition. Plain http is acceptable to exactly these, because the
    transport is a bridge network on one machine, never the public internet.
    Everything with a public hostname must still be HTTPS.
    """
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost",) or "." not in host:
        return True
    if host.startswith(("127.", "10.", "192.168.")):
        return True
    if host.startswith("172."):
        second = host.split(".")[1] if host.count(".") >= 1 else ""
        return second.isdigit() and 16 <= int(second) <= 31
    return False


class PserviceClient:
    """pservice REST transport. Verifies TLS; a self-signed endpoint is refused."""

    def __init__(self, base_url: str, service_key: str, *,
                 transport: httpx.AsyncBaseTransport | None = None):
        if not service_key:
            raise ValueError("pservice requires a service key")
        # Public targets must be HTTPS; an internal service on a private bridge
        # network may be plain http, which is how pservice is reached on-host.
        if not base_url.startswith("https://") and not (
            base_url.startswith("http://") and is_internal_url(base_url)
        ):
            raise ValueError("pservice requires HTTPS unless the target is internal")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/api/v1",
            headers={"X-Service-Key": service_key},
            verify=True, transport=transport,
            timeout=httpx.Timeout(15, connect=5),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_payment(self, *, amount_micros: int, currency: str,
                             client_payment_id: str, user_id: str) -> PservicePayment:
        if currency != "RUB":
            raise ValueError("the first fiat P2P pilot supports RUB only")
        cents = usdt_micros_to_case8_amount(amount_micros)
        body = {
            "cases_payment_intent_id": str(uuid.uuid4()),
            "client_payment_id": client_payment_id,
            "user_id": str(uuid.uuid5(_USER_NS, user_id)),
            "amount_usdt": cents,
            "currency": currency,
        }
        response = await self._client.post("/payments", json=body)
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict) or "order_id" not in raw or "status" not in raw:
            raise PartnerProtocolError("invalid pservice create payload")
        return PservicePayment(
            order_id=str(raw["order_id"]),
            status=int(raw["status"]),
            expires_at=_optional_utc(raw.get("expires_at")),
        )

    async def order_status(self, order_id: str) -> PserviceOrderStatus:
        response = await self._client.get(f"/payments/{order_id}")
        response.raise_for_status()
        return _order_status_from(response.json())

    async def confirm(self, order_id: str) -> None:
        (await self._client.post(f"/orders/{order_id}/confirm")).raise_for_status()

    async def cancel(self, order_id: str) -> None:
        (await self._client.post(f"/orders/{order_id}/cancel")).raise_for_status()

    async def business(self) -> dict[str, Any]:
        """Read-only health and commission snapshot for the poller warm-up."""
        response = await self._client.get("/admin/partner/business")
        response.raise_for_status()
        return response.json()


class MockPservice:
    """In-process pservice for development and tests: a full order lifecycle.

    Mirrors the status enum, not a happy path. An order is CREATED, a trader is
    found on the first status read, the user confirms, and the next read
    completes it. Cancellation is explicit; `_force_status` drives the rest.
    """

    def __init__(self, *, rub_per_usdt: int = 90):
        if type(rub_per_usdt) is not int or rub_per_usdt <= 0:
            raise ValueError("mock RUB rate must be a positive integer")
        self._rate = rub_per_usdt
        self._orders: dict[str, dict[str, Any]] = {}

    async def create_payment(self, *, amount_micros: int, currency: str,
                             client_payment_id: str, user_id: str) -> PservicePayment:
        if currency != "RUB":
            raise ValueError("the first fiat P2P pilot supports RUB only")
        usdt_micros_to_case8_amount(amount_micros)
        order_id = str(uuid.uuid4())
        self._orders[order_id] = {
            "status": 0, "amount_micros": amount_micros,
            "fiat_kopecks": amount_micros * self._rate // 10_000,
            "requisites": f"4276 **** **** {len(self._orders) + 1000:04d}",
        }
        return PservicePayment(order_id=order_id, status=0,
                               expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))

    async def order_status(self, order_id: str) -> PserviceOrderStatus:
        order = self._orders.get(order_id)
        if order is None:
            raise PartnerProtocolError("unknown pservice order")
        if order["status"] == 0:            # CREATED -> TRADER_FOUND
            order["status"] = 3
        elif order["status"] in (4, 6):     # confirmed -> COMPLETED
            order["status"] = COMPLETED_STATUS
        found = order["status"] == 3
        return PserviceOrderStatus(
            status=order["status"],
            fiat_kopecks=order["fiat_kopecks"],
            requisites=order["requisites"] if found else None,
            trader_username="@mock_trader" if found else None,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            detail=None,
        )

    async def confirm(self, order_id: str) -> None:
        self._orders[order_id]["status"] = 4   # USER_CONFIRMED

    async def cancel(self, order_id: str) -> None:
        self._orders[order_id]["status"] = 9   # CANCELLED

    async def business(self) -> dict[str, Any]:
        return {"id": 0, "title": "mock", "fee": 0, "deposit": 0}

    def _force_status(self, order_id: str, status: int) -> None:
        self._orders[order_id]["status"] = status
