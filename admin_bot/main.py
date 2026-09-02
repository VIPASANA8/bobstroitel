from dataclasses import dataclass, field
from html import escape
import json
import logging
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from admin_bot.client import AdminAPIError, CashAdminClient
from admin_bot.config import BotConfig
from admin_bot.formatting import fiat_order_message, queue_messages


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("poker8.cash_admin_bot")


@dataclass
class Pending:
    action: str
    target_id: str
    body: dict = field(default_factory=dict)
    step: str = "reason"
    key: str = field(default_factory=lambda: uuid4().hex)


class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}"

    def call(self, method, **payload):
        request = Request(f"{self.base}/{method}", data=urlencode(payload).encode(), method="POST")
        with urlopen(request, timeout=70) as response:
            result = json.loads(response.read())
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram API error"))
        return result["result"]

    def send(self, chat_id, text, keyboard=None):
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if keyboard:
            payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
        return self.call("sendMessage", **payload)


class OperatorBot:
    def __init__(self, config):
        self.telegram = Telegram(config.telegram_token)
        self.api = CashAdminClient(config.api_base_url, config.api_key)
        self.pending = {}

    def run(self):
        offset = 0
        while True:
            try:
                updates = self.telegram.call("getUpdates", offset=offset, timeout=60,
                                             allowed_updates=json.dumps(["message", "callback_query"]))
                for update in updates:
                    offset = update["update_id"] + 1
                    self.handle(update)
            except Exception:
                log.exception("polling failed")
                time.sleep(2)

    def handle(self, update):
        callback = update.get("callback_query")
        message = update.get("message") or (callback or {}).get("message")
        actor = (callback or message or {}).get("from") or (callback or {}).get("from")
        if callback:
            actor = callback.get("from")
        if not message or not actor:
            return
        chat_id = message["chat"]["id"]
        actor_id = actor["id"]
        try:
            identity = self.api.me(actor_id)
            if callback:
                self.telegram.call("answerCallbackQuery", callback_query_id=callback["id"])
                self.handle_callback(chat_id, actor_id, callback.get("data", ""), identity)
            else:
                self.handle_message(chat_id, actor_id, message.get("text", ""), identity)
        except AdminAPIError as exc:
            self.telegram.send(chat_id, f"🚫 {escape(str(exc))}")

    def handle_message(self, chat_id, actor_id, text, identity):
        text = text.strip()
        if text in {"/start", "/help"}:
            self.telegram.send(
                chat_id,
                f"Poker8 CASH control\nРоль: <b>{escape(identity['role'])}</b>\n"
                "/queue — очередь решений\n/audit — последние действия\n"
                "/user ID — кошелёк и операции пользователя\n"
                "/order ID — заявка RUB P2P по локальному или партнёрскому номеру",
            )
            return
        if text == "/queue":
            self.show_queue(chat_id, actor_id, identity)
            return
        if text == "/audit":
            rows = self.api.audit(actor_id)
            rendered = "\n".join(
                f"• {escape(row['action'])} <code>{escape(row['target_id'])}</code> — {escape(row['reason'])}"
                for row in rows
            ) or "Журнал пуст"
            self.telegram.send(chat_id, rendered)
            return
        if text.startswith("/user "):
            user = self.api.user(actor_id, text.split(maxsplit=1)[1])
            balances = user["balances"]
            self.telegram.send(
                chat_id,
                f"👤 <b>{escape(user['display_name'])}</b> <code>{escape(user['id'])}</code>\n"
                f"Telegram: <code>{user['telegram_user_id']}</code>\n"
                f"Доступно: {escape(balances['available']['usdt'])} USDT / "
                f"{escape(balances['available']['units'])} CASH\n"
                f"За столами: {escape(balances['escrow']['usdt'])} USDT\n"
                f"В выводе: {escape(balances['withdrawal']['usdt'])} USDT",
            )
            return
        if text.startswith("/order "):
            self.telegram.send(
                chat_id, fiat_order_message(self.api.fiat_order(actor_id, text.split(maxsplit=1)[1])),
            )
            return
        pending = self.pending.get(actor_id)
        if not pending:
            self.telegram.send(chat_id, "Неизвестная команда. Используйте /queue")
            return
        if pending.step == "order_id":
            if text != "-" and (not text or len(text) > 64):
                self.telegram.send(chat_id, "Введите ID заявки Poker8 или «-»")
                return
            pending.body["order_id"] = None if text == "-" else text
            pending.step = "reason"
            self.telegram.send(chat_id, "Укажите причину решения (минимум 3 символа)")
            return
        if pending.step == "tx_hash":
            if not text or len(text) > 128:
                self.telegram.send(chat_id, "Введите корректный reference транзакции")
                return
            pending.body["tx_hash"] = text
            pending.step = "reason"
            self.telegram.send(chat_id, "Укажите причину решения (минимум 3 символа)")
            return
        if len(text) < 3 or len(text) > 500:
            self.telegram.send(chat_id, "Причина должна содержать от 3 до 500 символов")
            return
        pending.body["reason"] = text
        pending.step = "confirm"
        self.telegram.send(
            chat_id,
            f"Подтвердить <b>{escape(pending.action)}</b> для <code>{escape(pending.target_id)}</code>?\n"
            f"Причина: {escape(text)}",
            [[{"text": "✅ Подтвердить", "callback_data": "confirm"},
              {"text": "Отмена", "callback_data": "cancel"}]],
        )

    def show_queue(self, chat_id, actor_id, identity):
        items = queue_messages(self.api.queue(actor_id))
        if not items:
            self.telegram.send(chat_id, "Очередь пуста")
            return
        for kind, target_id, status, text in items:
            keyboard = None
            if identity["role"] == "reviewer":
                keyboard = None
            elif kind == "withdrawal" and status == "reserved":
                keyboard = [[{"text": "Разрешить", "callback_data": f"approve:{target_id}"},
                             {"text": "Отклонить", "callback_data": f"reject:{target_id}"}]]
            elif kind == "withdrawal" and status == "approved":
                keyboard = [[{"text": "Mock success", "callback_data": f"success:{target_id}"},
                             {"text": "Mock unknown", "callback_data": f"unknown:{target_id}"},
                             {"text": "Mock failure", "callback_data": f"failure:{target_id}"}]]
            elif kind == "withdrawal" and status == "unknown":
                keyboard = [[{"text": "Подтвердить по сверке", "callback_data": f"confirmed:{target_id}"},
                             {"text": "Выплаты не было", "callback_data": f"unpaid:{target_id}"}]]
            elif kind == "withdrawal" and status == "submitted":
                keyboard = [[{"text": "Подтвердить по сверке", "callback_data": f"confirmed:{target_id}"}]]
            elif kind == "payment":
                keyboard = [[{"text": "Зачислить", "callback_data": f"credit:{target_id}"},
                             {"text": "Отклонить", "callback_data": f"payreject:{target_id}"}]]
            elif kind == "fiat_event":
                keyboard = [[{"text": "Привязать и зачислить", "callback_data": f"bindcredit:{target_id}"},
                             {"text": "Отклонить", "callback_data": f"fiatreject:{target_id}"}]]
            elif kind == "fiat_order" and status in {"requesting", "clarifying", "review_required"}:
                keyboard = [[{"text": "Закрыть заявку", "callback_data": f"fiatclose:{target_id}"}]]
            self.telegram.send(chat_id, text, keyboard)

    def handle_callback(self, chat_id, actor_id, data, _identity):
        if data == "cancel":
            self.pending.pop(actor_id, None)
            self.telegram.send(chat_id, "Отменено")
            return
        if data == "confirm":
            pending = self.pending.get(actor_id)
            if not pending or pending.step != "confirm":
                self.telegram.send(chat_id, "Подтверждение устарело. Откройте /queue заново")
                return
            result = self.api.decide(actor_id, pending.action, pending.target_id,
                                     pending.body, key=pending.key)
            self.pending.pop(actor_id, None)
            self.telegram.send(chat_id, f"✅ Новый статус: <b>{escape(result['status'])}</b>")
            return
        try:
            verb, target_id = data.split(":", 1)
        except ValueError:
            return
        mapping = {
            "approve": ("approve", {}), "reject": ("reject", {}),
            "success": ("execute", {"outcome": "success"}),
            "unknown": ("execute", {"outcome": "unknown"}),
            "failure": ("execute", {"outcome": "failure"}),
            "confirmed": ("resolve_withdrawal", {"decision": "confirmed"}),
            "unpaid": ("resolve_withdrawal", {"decision": "rejected", "tx_hash": None}),
            "credit": ("resolve_payment", {"decision": "credit"}),
            "payreject": ("resolve_payment", {"decision": "reject"}),
            "bindcredit": ("resolve_fiat_event", {"decision": "credit"}),
            "fiatreject": ("resolve_fiat_event", {"decision": "reject"}),
            "fiatclose": ("close_fiat_order", {}),
        }
        if verb not in mapping:
            return
        action, body = mapping[verb]
        step = {"confirmed": "tx_hash", "bindcredit": "order_id"}.get(verb, "reason")
        self.pending[actor_id] = Pending(action, target_id, body, step)
        prompt = {
            "tx_hash": "Введите проверенный reference транзакции",
            "order_id": "Введите ID заявки Poker8 или «-», если он уже известен",
        }.get(step, "Укажите причину решения")
        self.telegram.send(chat_id, prompt)


if __name__ == "__main__":
    OperatorBot(BotConfig.from_env()).run()
