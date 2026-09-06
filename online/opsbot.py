"""The operator panel: a menu of inline buttons, on the bot built for it.

Typed commands were a list somebody had to already know. This is the shape the
job actually has -- a screen with what is waiting on it, and buttons that lead
somewhere. One message is the panel and it redraws itself; only queue cards,
which each carry their own buttons, arrive as messages of their own.

Every decision still ends up at `CashAdminService`: that is what writes the
reason into the audit log and enforces what a role may touch. Nothing here
moves money on its own, and nothing skips the reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from uuid import uuid4

from sqlalchemy import select

from admin_bot.formatting import (
    fiat_order_message, queue_messages, reconciliation_message, user_card,
)
from cash.access import CashOperator
from cash.admin import OperatorAccessDenied
from cash.amounts import kopecks_to_rub, micros_to_usdt, usdt_to_micros
from online.schema import cash_operators


#: What the queue calls each kind, and what an operator calls it.
KINDS = {
    "withdrawal": "💸 Выводы",
    "payment": "🔎 Платежи",
    "fiat_order": "₽ Заявки",
    "fiat_event": "₽ События",
}
BACK = [{"text": "⬅️ Меню", "callback_data": "nav:main"}]
CANCEL = [{"text": "Отмена", "callback_data": "nav:main"}]

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
    "settle": ("settle_p2p_withdrawal", {}),
    "credit_user": ("adjust_balance", {"sign": 1}),
    "debit_user": ("adjust_balance", {"sign": -1}),
    "freeze": ("freeze_user", {}),
    "unfreeze": ("release_user", {}),
}
#: What has to be asked for before the reason, and how to ask for it.
EXTRA_STEP = {
    "confirmed": "tx_hash", "bindcredit": "order_id", "settle": "fiat_kopecks",
    "credit_user": "amount", "debit_user": "amount",
}
PROMPTS = {
    "tx_hash": "Пришлите проверенный reference транзакции",
    "order_id": "Пришлите ID заявки Poker8 или «-», если он уже известен",
    "reason": "Пришлите причину решения (от 3 до 500 символов)",
    "user": "Пришлите ID игрока или его telegram-номер",
    "order": "Пришлите номер заявки — наш или партнёрский",
    "fiat_kopecks": "Пришлите сумму в рублях, которую отправили: например 1815,50",
    "amount": "Пришлите сумму в USDT: например 25.50",
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


def _rub_to_kopecks(text: str) -> int | None:
    """«1815,50», «1815.5» или «1815» в копейки, или None если это не сумма."""
    cleaned = text.replace(" ", "").replace(",", ".")
    whole, _, fraction = cleaned.partition(".")
    if not whole.isdigit() or (fraction and not fraction.isdigit()) or len(fraction) > 2:
        return None
    kopecks = int(whole) * 100 + int(fraction.ljust(2, "0") or 0)
    return kopecks or None


def _usdt_to_micros(text: str) -> int | None:
    try:
        micros = usdt_to_micros(text.replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return micros or None


def _card_buttons(kind: str, target_id: str, status: str, row: dict) -> list | None:
    if kind == "withdrawal" and status == "reserved":
        return [[{"text": "✅ Разрешить", "callback_data": f"approve:{target_id}"},
                 {"text": "🚫 Отклонить", "callback_data": f"reject:{target_id}"}]]
    if kind == "withdrawal" and status == "approved":
        # A RUB payout is sent by a person, so the only thing to record is that
        # they sent it, and how much. The mock rail is for the crypto one.
        if row.get("network") == "P2P_RUB":
            return [[{"text": "💸 Записать выплату", "callback_data": f"settle:{target_id}"}]]
        return [[{"text": "Mock success", "callback_data": f"success:{target_id}"},
                 {"text": "Mock unknown", "callback_data": f"unknown:{target_id}"},
                 {"text": "Mock failure", "callback_data": f"failure:{target_id}"}]]
    if kind == "withdrawal" and status == "unknown":
        return [[{"text": "Подтвердить по сверке", "callback_data": f"confirmed:{target_id}"},
                 {"text": "Выплаты не было", "callback_data": f"unpaid:{target_id}"}]]
    if kind == "withdrawal" and status == "submitted":
        return [[{"text": "Подтвердить по сверке", "callback_data": f"confirmed:{target_id}"}]]
    if kind == "payment":
        return [[{"text": "✅ Зачислить", "callback_data": f"credit:{target_id}"},
                 {"text": "🚫 Отклонить", "callback_data": f"payreject:{target_id}"}]]
    if kind == "fiat_event":
        return [[{"text": "Привязать и зачислить", "callback_data": f"bindcredit:{target_id}"},
                 {"text": "🚫 Отклонить", "callback_data": f"fiatreject:{target_id}"}]]
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
        #: Screens that are waiting to be told an id rather than a decision.
        self.awaiting: dict[int, str] = {}

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

    # --- what arrives --------------------------------------------------------

    async def message(self, operator: CashOperator, text: str) -> list[tuple[str, str, list | None]]:
        """A typed message: either an answer the panel asked for, or /start."""
        text = text.strip()
        if text in {"/start", "/admin", "/menu", "/help"}:
            self._forget(operator)
            return [("send", *await self._main(operator))]
        waiting = self.awaiting.get(operator.telegram_user_id)
        if waiting:
            self.awaiting.pop(operator.telegram_user_id, None)
            return [("send", *await self._lookup(operator, waiting, text))]
        pending = self.pending.get(operator.telegram_user_id)
        if pending:
            return [("send", *self._fill(pending, text))]
        return [("send", *await self._main(operator))]

    async def callback(self, operator: CashOperator, data: str) -> list[tuple[str, str, list | None]]:
        """A button. Navigation redraws the panel; a decision starts a prompt."""
        head, _, rest = data.partition(":")
        if head == "nav":
            self._forget(operator)
            return await self._navigate(operator, rest)
        if head == "q":
            return await self._queue_cards(operator, rest)
        if head == "confirm":
            return [("edit", *await self._decide(operator))]
        if head == "ask":
            if not operator.can_mutate() and rest not in {"user", "order"}:
                return [("edit", "🚫 Роль reviewer только читает", [BACK])]
            self.awaiting[operator.telegram_user_id] = rest
            return [("edit", PROMPTS.get(rest, "Пришлите значение"), [CANCEL])]
        if head in ACTIONS:
            return [("edit", *self._begin(operator, head, rest))]
        return []

    def _forget(self, operator: CashOperator) -> None:
        self.pending.pop(operator.telegram_user_id, None)
        self.awaiting.pop(operator.telegram_user_id, None)

    # --- screens -------------------------------------------------------------

    async def _navigate(self, operator: CashOperator, where: str):
        if where == "money":
            return [("edit", await self._money(operator), [BACK])]
        if where == "queue":
            return [("edit", *await self._queue(operator))]
        if where == "audit":
            rows = await self.admin.audit(operator, limit=20)
            body = "\n".join(
                f"• {escape(row['action'])} <code>{escape(row['target_id'])}</code>"
                f" — {escape(row['reason'])}" for row in rows
            ) or "Журнал пуст"
            return [("edit", "🧾 <b>Последние решения</b>\n\n" + body, [BACK])]
        if where == "recon":
            # The service sweeps one day and wants that day; the HTTP route in
            # front of it defaults to today the same way.
            today = datetime.now(timezone.utc).date()
            report = await self.admin.fiat_reconciliation(operator, today)
            return [("edit", reconciliation_message(report), [BACK])]
        return [("edit", *await self._main(operator))]

    async def _main(self, operator: CashOperator):
        waiting = len(queue_messages(await self.admin.queue(operator)))
        text = (
            "🛠 <b>Панель оператора</b>\n"
            f"Роль: <b>{escape(operator.role)}</b>\n\n"
            + (f"В очереди ждёт решений: <b>{waiting}</b>" if waiting else "Очередь пуста.")
        )
        keyboard = [
            [{"text": "💰 Деньги", "callback_data": "nav:money"},
             {"text": f"📋 Очередь ({waiting})", "callback_data": "nav:queue"}],
            [{"text": "👤 Игрок", "callback_data": "ask:user"},
             {"text": "₽ Заявка", "callback_data": "ask:order"}],
            [{"text": "📊 Сверка за сегодня", "callback_data": "nav:recon"},
             {"text": "🧾 Аудит", "callback_data": "nav:audit"}],
        ]
        return text, keyboard

    async def _money(self, operator: CashOperator) -> str:
        try:
            summary = await self.admin.overview(operator)
        except OperatorAccessDenied:
            return "Сводка по деньгам — только для глобального админа."
        money = lambda label, micros: f"{label}: <b>{micros_to_usdt(micros)}</b> USDT"
        return "\n".join([
            "💰 <b>Деньги</b>",
            f"Игроков: <b>{summary['players']}</b> · под холдом: <b>{summary['frozen']}</b>",
            money("На балансах", summary["available_micros"]),
            money("В игре", summary["escrow_micros"]),
            money("Ждёт вывода", summary["withdrawal_micros"]),
            "",
            f"🎲 CUBE за сутки: <b>{summary['cube_rounds_day']}</b> раундов, "
            f"результат {micros_to_usdt(summary['cube_result_day_micros'])} USDT",
            money("Касса кубика", summary["cube_house_micros"]),
        ])

    async def _queue(self, operator: CashOperator):
        items = queue_messages(await self.admin.queue(operator))
        counts: dict[str, int] = {}
        for kind, *_ in items:
            counts[kind] = counts.get(kind, 0) + 1
        if not counts:
            return "📋 <b>Очередь</b>\n\nПусто — разбирать нечего.", [BACK]
        rows = [
            [{"text": f"{KINDS.get(kind, kind)} ({count})", "callback_data": f"q:{kind}"}]
            for kind, count in counts.items()
        ]
        return "📋 <b>Очередь</b>\n\nВыберите, что разбирать.", rows + [BACK]

    async def _queue_cards(self, operator: CashOperator, kind: str):
        queue = await self.admin.queue(operator)
        # The rendered card says what a person needs to read; the row behind it
        # says which rail this is, and that decides which buttons belong on it.
        rows = {row["id"]: row for row in queue.get("withdrawals", [])}
        items = [item for item in queue_messages(queue) if item[0] == kind]
        if not items:
            return [("edit", "Здесь уже пусто.", [BACK])]
        # The list is redrawn in place; the cards follow as their own messages,
        # because each carries the buttons that belong to it.
        screen = [("edit", f"{KINDS.get(kind, kind)}: <b>{len(items)}</b>", [BACK])]
        # ponytail: the oldest ten. A phone is not a console, and the operator
        # API is where a backlog that does not fit gets worked through.
        for _kind, target, status, body in items[:10]:
            buttons = (_card_buttons(kind, target, status, rows.get(target, {}))
                       if operator.can_mutate() else None)
            screen.append(("send", body, buttons))
        return screen

    async def _lookup(self, operator: CashOperator, what: str, value: str):
        """The id the panel asked for came back."""
        try:
            if what == "user":
                user = await self.admin.user(operator, value)
                keyboard = [BACK]
                if operator.can_mutate():
                    held = bool(user.get("hold"))
                    keyboard = [
                        [{"text": "➕ Начислить", "callback_data": f"credit_user:{user['id']}"},
                         {"text": "➖ Списать", "callback_data": f"debit_user:{user['id']}"}],
                        [{"text": "Разморозить" if held else "Заморозить",
                          "callback_data": f"{'unfreeze' if held else 'freeze'}:{user['id']}"}],
                        BACK,
                    ]
                return user_card(user), keyboard
            order = await self.admin.fiat_order(operator, value)
            return fiat_order_message(order), [BACK]
        except (OperatorAccessDenied, ValueError, KeyError) as exc:
            return f"🚫 {escape(str(exc)) or 'не найдено'}", [BACK]

    # --- decisions -----------------------------------------------------------

    def _begin(self, operator: CashOperator, verb: str, target_id: str):
        if not target_id:
            return "Кнопка устарела — откройте очередь заново.", [BACK]
        if not operator.can_mutate():
            return "🚫 Роль reviewer только читает", [BACK]
        action, body = ACTIONS[verb]
        step = EXTRA_STEP.get(verb, "reason")
        self.pending[operator.telegram_user_id] = Pending(action, target_id, dict(body), step)
        return PROMPTS[step], [CANCEL]

    def _fill(self, pending: Pending, text: str):
        """Whatever was typed while a decision waited for its details."""
        if pending.step == "fiat_kopecks":
            kopecks = _rub_to_kopecks(text)
            if kopecks is None:
                return PROMPTS["fiat_kopecks"], [CANCEL]
            pending.body["fiat_kopecks"] = kopecks
            pending.step = "reason"
            return f"Записываем {kopecks_to_rub(kopecks)} ₽. " + PROMPTS["reason"], [CANCEL]
        if pending.step == "amount":
            micros = _usdt_to_micros(text)
            if micros is None:
                return PROMPTS["amount"], [CANCEL]
            pending.body["amount_micros"] = micros * pending.body.pop("sign", 1)
            pending.step = "reason"
            moved = "Начисляем" if pending.body["amount_micros"] > 0 else "Списываем"
            return (f"{moved} {micros_to_usdt(micros)} USDT. " + PROMPTS["reason"], [CANCEL])
        if pending.step == "order_id":
            if text != "-" and (not text or len(text) > 64):
                return PROMPTS["order_id"], [CANCEL]
            pending.body["order_id"] = None if text == "-" else text
            pending.step = "reason"
            return PROMPTS["reason"], [CANCEL]
        if pending.step == "tx_hash":
            if not text or len(text) > 128:
                return PROMPTS["tx_hash"], [CANCEL]
            pending.body["tx_hash"] = text
            pending.step = "reason"
            return PROMPTS["reason"], [CANCEL]
        if not 3 <= len(text) <= 500:
            return "Причина должна содержать от 3 до 500 символов", [CANCEL]
        pending.body["reason"] = text
        pending.step = "confirm"
        return (
            f"Подтвердить <b>{escape(pending.action)}</b> для "
            f"<code>{escape(pending.target_id)}</code>?\nПричина: {escape(text)}",
            [[{"text": "✅ Подтвердить", "callback_data": "confirm:"},
              {"text": "Отмена", "callback_data": "nav:main"}]],
        )

    async def _decide(self, operator: CashOperator):
        pending = self.pending.get(operator.telegram_user_id)
        if not pending or pending.step != "confirm":
            return "Подтверждение устарело — откройте очередь заново.", [BACK]
        try:
            result = await self._apply(operator, pending)
        except (OperatorAccessDenied, ValueError) as exc:
            # The service refused. The half-filled decision goes with it, so the
            # next confirmation is a fresh one rather than a retry of a refusal.
            self.pending.pop(operator.telegram_user_id, None)
            return f"🚫 {escape(str(exc))}", [BACK]
        self.pending.pop(operator.telegram_user_id, None)
        status = (result or {}).get("status") or (
            "заморожен" if (result or {}).get("held") else "разморожен"
        )
        return f"✅ Новый статус: <b>{escape(str(status))}</b>", [
            [{"text": "📋 В очередь", "callback_data": "nav:queue"}], BACK,
        ]

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
        if pending.action == "settle_p2p_withdrawal":
            return await self.admin.settle_p2p_withdrawal(
                target, operator, fiat_kopecks=body["fiat_kopecks"], reason=reason, key=key)
        if pending.action == "adjust_balance":
            return await self.admin.adjust_balance(
                target, operator, amount_micros=body["amount_micros"], reason=reason, key=key)
        if pending.action == "close_fiat_order":
            return await self.admin.close_fiat_order(target, operator, reason=reason, key=key)
        if pending.action == "freeze_user":
            return await self.admin.freeze_user(target, operator, reason=reason, key=key)
        if pending.action == "release_user":
            return await self.admin.release_user(target, operator, reason=reason, key=key)
        raise ValueError("неизвестное действие")
