import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


class AdminAPIError(RuntimeError):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status


class CashAdminClient:
    def __init__(self, base_url, api_key, *, opener=urlopen):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.opener = opener

    def request(self, method, path, actor_id, *, body=None, idempotency_key=None):
        payload = None if body is None else json.dumps(body).encode()
        headers = {
            "Accept": "application/json", "Content-Type": "application/json",
            "X-Cash-Admin-Key": self.api_key,
            "X-Cash-Operator-Telegram-Id": str(actor_id),
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(f"{self.base_url}{path}", data=payload, headers=headers, method=method)
        attempts = 3 if method == "GET" or idempotency_key else 1
        for attempt in range(attempts):
            try:
                with self.opener(request, timeout=20) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except HTTPError as exc:
                raw = exc.read().decode(errors="replace")
                try:
                    detail = json.loads(raw).get("detail", raw)
                except json.JSONDecodeError:
                    detail = raw
                if exc.code not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                    raise AdminAPIError(exc.code, str(detail)) from exc
            except (URLError, TimeoutError, OSError) as exc:
                if attempt == attempts - 1:
                    reason = getattr(exc, "reason", str(exc))
                    raise AdminAPIError(0, f"backend unavailable: {reason}") from exc
            time.sleep(2**attempt)

    def me(self, actor_id):
        return self.request("GET", "/api/cash-admin/me", actor_id)

    def queue(self, actor_id):
        return self.request("GET", "/api/cash-admin/queue", actor_id)

    def audit(self, actor_id):
        return self.request("GET", "/api/cash-admin/audit?limit=20", actor_id)

    def user(self, actor_id, identifier):
        from urllib.parse import quote
        return self.request("GET", f"/api/cash-admin/users/{quote(str(identifier), safe='')}", actor_id)

    def fiat_order(self, actor_id, identifier):
        from urllib.parse import quote
        return self.request(
            "GET", "/api/cash-admin/fiat-orders/" + quote(str(identifier), safe=""), actor_id,
        )

    def reconciliation(self, actor_id, day=None):
        from urllib.parse import quote
        path = "/api/cash-admin/reconciliation"
        if day:
            path += "?day=" + quote(str(day), safe="")
        return self.request("GET", path, actor_id)

    def decide(self, actor_id, action, target_id, body, *, key=None):
        routes = {
            "approve": f"/api/cash-admin/withdrawals/{target_id}/approve",
            "reject": f"/api/cash-admin/withdrawals/{target_id}/reject",
            "execute": f"/api/cash-admin/withdrawals/{target_id}/execute-mock",
            "resolve_withdrawal": f"/api/cash-admin/withdrawals/{target_id}/resolve",
            "resolve_payment": f"/api/cash-admin/payment-events/{target_id}/resolve",
            "resolve_fiat_event": f"/api/cash-admin/fiat-events/{target_id}/resolve",
            "close_fiat_order": f"/api/cash-admin/fiat-orders/{target_id}/close",
            "freeze_user": f"/api/cash-admin/users/{target_id}/freeze",
            "release_user": f"/api/cash-admin/users/{target_id}/unfreeze",
        }
        if action not in routes:
            raise ValueError("unknown operator action")
        return self.request("POST", routes[action], actor_id, body=body,
                            idempotency_key=key or uuid4().hex)
