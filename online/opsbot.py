"""The operator panel, inside the bot players already talk to.

This is `admin_bot/` moved in rather than rewritten: the same queue, the same
buttons, the same reason-then-confirm before anything moves. What changed is
where it runs. That package is a second process that long-polls the Bot API and
reaches the decisions over HTTP with an operator key -- and the moment the app
took the bot's webhook, a second consumer of the same updates became a thing
that could not work. Here the updates already arrive, and the decision is one
call away instead of one round trip.

Every action still goes through `CashAdminService`, which is what writes the
reason into the audit log and enforces what a role may touch. Nothing here
moves money on its own.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from uuid import uuid4

from sqlalchemy import select

from admin_bot.formatting import (
    fiat_order_message, queue_messages, reconciliation_message, user_card,
)
from cash.access import CashOperator
from cash.admin import OperatorAccessDenied
from cash.amounts import micros_to_usdt
from online.schema import cash_operators


HELP = (
    "🛠 <b>Панель оператора</b>\n"
    "Роль: <b>{role}</b>\n\n"
    "/panel — сводка по деньгам\n"
    "/queue — очередь решений\n"
    "/audit — последние действия\n"
    "/user ID — карточка игрока, заморозка кнопкой\n"
    "/order ID — заявка RUB P2P по нашему или партнёрскому номеру\n"
    "/recon [ГГГГ-ММ-ДД] — сверка RUB за день"
)

#: Which button leads to which decision, and what it already knows.
ACTIONS = {
    "approve": ("approve_withdrawal", {}),
    "reject": ("reject_withdrawal", {}),
    "success": ("execute_mock", {"outcome": "success"}),
    "unknown": ("execute_mock", {"outcome": "unknown"}),
    "failure": ("execute_mock", {"outcome": "failure"}),
    "confirmed": ("resolve_withdrawal", {"decision": "confirmed"}),
    "unpaid": ("resolve_withdrawal", {"decision": "rejected", "tx_hash": None}),
    "credit": ("resolve_payment", {"decision": "credit"}),
    "payreject": ("resolve_payment", {"decision": "reject"}),
    "bindcredit": ("resolve_fiat_event", {"decision": "credit"}),
    "fiatreject": ("resolve_fiat_event", {"decision": "reject"}),
    "fiatclose": ("close_fiat_order", {}),
    "freeze": ("freeze_user", {}),
    "unfreeze": ("release_user", {}),
}
#: What has to be asked for before the reason, and how to ask.
EXTRA_STEP = {"confirmed": "tx_hash", "bindcredit": "order_id"}
PROMPTS = {
    "tx_hash": "Введите проверенный reference транзакции",
    "order_id": "Введите ID заявки Poker8 или «-», если он уже известен",
    "reason": "Укажите причину решения (от 3 до 500 символов)",
}


@dataclass
class Pending:
    action: str
    target_id: str
    body: dict = field(default_factory=dict)
    step: str = "reason"
    #: Fixed when the button is pressed, so a retried confirmation is the same
    #: decision rather than a second one.
    key: str = field(default_factory=lambda: uuid4().hex)


def _buttons(kind: str, target_id: str, status: str) -> list | None:
    if kind == "withdrawal" and status == "reserved":
        return [[{"text": "Разрешить", "callback_data": f"approve:{target_id}"},
                 {"text": "Отклонить", "callback_data": f"reject:{target_id}"}]]
    if kind == "withdrawal" and status == "approved":
        return [[{"text": "Mock success", "callback_data": f"success:{target_id}"},
                 {"text": "Mock unknown", "callback_data": f"unknown:{target_id}"},
                 {"text": "Mock failure", "callback_data": f"failure:{target_id}"}]]
    if kind == "withdrawal" and status == "unknown":
        return [[{"text": "Подтвердить по сверке", "callback_data": f"confirmed:{target_id}"},
                 {"text": "Выплаты не было", "callback_data": f"unpaid:{target_id}"}]]
    if kind == "withdrawal" and status == "submitted":
        return [[{"text": "Подтвердить по сверке", "callback_data": f"confirmed:{target_id}"}]]
    if kind == "payment":
        return [[{"text": "Зачислить", "callback_data": f"credit:{target_id}"},
                 {"text": "Отклонить", "callback_data": f"payreject:{target_id}"}]]
    if kind == "fiat_event":
        return [[{"text": "Привязать и зачислить", "callback_data": f"bindcredit:{target_id}"},
                 {"text": "Отклонить", "callback_data": f"fiatreject:{target_id}"}]]
    if kind == "fiat_order" and status in {"requesting", "clarifying", "review_required"}:
        return [[{"text": "Закрыть заявку", "callback_data": f"fiatclose:{target_id}"}]]
    return None


class OpsBot:
    def __init__(self, admin_service, session_factory) -> None:
        self.admin = admin_service
        self.sessions = session_factory
        # ponytail: in-process, so a half-filled decision does not survive a
        # restart and is not shared across workers. The pilot runs one; the day
        # it runs two this belongs in a table beside the audit log.
        self.pending: dict[int, Pending] = {}

    async def operator(self, telegram_id) -> CashOperator | None:
        """Who this is, according to the table the operator API reads."""
        async with self.sessions() as session:
            row = (await session.execute(select(cash_operators).where(
                cash_operators.c.telegram_user_id == telegram_id,
                cash_operators.c.active.is_(True),
            ))).mappings().first()
        if row is None:
            return None
        return CashOperator(row["id"], row["telegram_user_id"], row["tenant_id"], row["role"])

    # --- messages ------------------------------------------------------------

    async def message(self, operator: CashOperator, text: str) -> list[tuple[str, list | None]]:
        """Answer one command, as (text, keyboard) pairs to send in order."""
        text = text.strip()
        if text in {"/admin", "/help"}:
            return [(HELP.format(role=escape(operator.role)), None)]
        if text == "/panel":
            return [(await self._panel(operator), None)]
        if text == "/queue":
            return await self._queue(operator)
        if text == "/audit":
            rows = await self.admin.audit(operator, limit=20)
            rendered = "\n".join(
                f"• {escape(row['action'])} <code>{escape(row['target_id'])}</code>"
                f" — {escape(row['reason'])}" for row in rows
            ) or "Журнал пуст"
            return [(rendered, None)]
        if text.startswith("/user "):
            user = await self.admin.user(operator, text.split(maxsplit=1)[1])
            keyboard = None
            if operator.can_mutate():
                held = bool(user.get("hold"))
                keyboard = [[{
                    "text": "Разморозить" if held else "Заморозить",
                    "callback_data": f"{'unfreeze' if held else 'freeze'}:{user['id']}",
                }]]
            return [(user_card(user), keyboard)]
        if text.startswith("/order "):
            order = await self.admin.fiat_order(operator, text.split(maxsplit=1)[1])
            return [(fiat_order_message(order), None)]
        if text == "/recon" or text.startswith("/recon "):
            day = text.split(maxsplit=1)[1] if " " in text else None
            return [(reconciliation_message(await self.admin.fiat_reconciliation(operator, day)), None)]
        return await self._continue(operator, text)

    async def _panel(self, operator: CashOperator) -> str:
        try:
            summary = await self.admin.overview(operator)
        except OperatorAccessDenied:
            return "Сводка по деньгам — только для глобального админа."
        money = (
            lambda label, micros: f"{label}: <b>{micros_to_usdt(micros)}</b> USDT"
        )
        return "\n".join([
            "🛠 <b>Сводка</b>",
            f"Игроков: <b>{summary['players']}</b> · под холдом: <b>{summary['frozen']}</b>",
            money("На балансах", summary["available_micros"]),
            money("В игре", summary["escrow_micros"]),
            money("Ждёт вывода", summary["withdrawal_micros"]),
            "",
            f"🎲 CUBE за сутки: <b>{summary['cube_rounds_day']}</b> раундов, "
            f"результат {micros_to_usdt(summary['cube_result_day_micros'])} USDT",
            money("Касса кубика", summary["cube_house_micros"]),
        ])

    async def _queue(self, operator: CashOperator) -> list[tuple[str, list | None]]:
        items = queue_messages(await self.admin.queue(operator))
        if not items:
            return [("Очередь пуста", None)]
        return [
            (body, _buttons(kind, target, status) if operator.can_mutate() else None)
            for kind, target, status, body in items
        ]

    async def _continue(self, operator: CashOperator, text: str) -> list[tuple[str, list | None]]:
        """Whatever was typed while a decision was waiting for its details."""
        pending = self.pending.get(operator.telegram_user_id)
        if not pending:
            return [("Неизвестная команда. /queue — очередь, /panel — сводка", None)]
        if pending.step == "order_id":
            if text != "-" and (not text or len(text) > 64):
                return [("Введите ID заявки Poker8 или «-»", None)]
            pending.body["order_id"] = None if text == "-" else text
            pending.step = "reason"
            return [(PROMPTS["reason"], None)]
        if pending.step == "tx_hash":
            if not text or len(text) > 128:
                return [("Введите корректный reference транзакции", None)]
            pending.body["tx_hash"] = text
            pending.step = "reason"
            return [(PROMPTS["reason"], None)]
        if not 3 <= len(text) <= 500:
            return [("Причина должна содержать от 3 до 500 символов", None)]
        pending.body["reason"] = text
        pending.step = "confirm"
        return [(
            f"Подтвердить <b>{escape(pending.action)}</b> для "
            f"<code>{escape(pending.target_id)}</code>?\nПричина: {escape(text)}",
            [[{"text": "✅ Подтвердить", "callback_data": "confirm"},
              {"text": "Отмена", "callback_data": "cancel"}]],
        )]

    # --- buttons -------------------------------------------------------------

    async def callback(self, operator: CashOperator, data: str) -> list[tuple[str, list | None]]:
        if data == "cancel":
            self.pending.pop(operator.telegram_user_id, None)
            return [("Отменено", None)]
        if data == "confirm":
            return await self._decide(operator)
        verb, _, target_id = data.partition(":")
        if verb not in ACTIONS or not target_id:
            return []
        if not operator.can_mutate():
            return [("🚫 Роль reviewer только читает", None)]
        action, body = ACTIONS[verb]
        step = EXTRA_STEP.get(verb, "reason")
        self.pending[operator.telegram_user_id] = Pending(action, target_id, dict(body), step)
        return [(PROMPTS[step], None)]

    async def _decide(self, operator: CashOperator) -> list[tuple[str, list | None]]:
        pending = self.pending.get(operator.telegram_user_id)
        if not pending or pending.step != "confirm":
            return [("Подтверждение устарело. Откройте /queue заново", None)]
        try:
            result = await self._apply(operator, pending)
        except (OperatorAccessDenied, ValueError) as exc:
            # The service refused. The half-filled decision goes with it, so
            # the next confirmation is a fresh one rather than a retry of a
            # refusal.
            self.pending.pop(operator.telegram_user_id, None)
            return [(f"🚫 {escape(str(exc))}", None)]
        self.pending.pop(operator.telegram_user_id, None)
        status = (result or {}).get("status") or (
            "заморожен" if (result or {}).get("held") else "разморожен"
        )
        return [(f"✅ Новый статус: <b>{escape(str(status))}</b>", None)]

    async def _apply(self, operator: CashOperator, pending: Pending):
        """One decision, on the service that writes the audit entry for it."""
        body, target, key = pending.body, pending.target_id, pending.key
        reason = body.get("reason", "")
        if pending.action == "approve_withdrawal":
            return await self.admin.approve_withdrawal(target, operator, reason=reason, key=key)
        if pending.action == "reject_withdrawal":
            return await self.admin.reject_withdrawal(target, operator, reason=reason, key=key)
        if pending.action == "execute_mock":
            return await self.admin.execute_mock(
                target, operator, outcome=body["outcome"], reason=reason, key=key)
        if pending.action == "resolve_withdrawal":
            return await self.admin.resolve_withdrawal(
                target, operator, decision=body["decision"],
                tx_hash=body.get("tx_hash"), reason=reason, key=key)
        if pending.action == "resolve_payment":
            return await self.admin.resolve_payment(
                target, operator, decision=body["decision"], reason=reason, key=key)
        if pending.action == "resolve_fiat_event":
            return await self.admin.resolve_fiat_event(
                int(target), operator, decision=body["decision"],
                reason=reason, key=key, order_id=body.get("order_id"))
        if pending.action == "close_fiat_order":
            return await self.admin.close_fiat_order(target, operator, reason=reason, key=key)
        if pending.action == "freeze_user":
            return await self.admin.freeze_user(target, operator, reason=reason, key=key)
        if pending.action == "release_user":
            return await self.admin.release_user(target, operator, reason=reason, key=key)
        raise ValueError("неизвестное действие")
