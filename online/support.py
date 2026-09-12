"""Support tickets: a player writes from the site or the bot, every operator
gets a card in the admin bot, and one answer flips the card for all of them.

Nothing here moves money. A finance ticket only points at the deposit, ₽
order or withdrawal it is about; the operator still decides on it in the
queue, with a reason and an audit entry, like before.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging
from uuid import uuid4

from sqlalchemy import func, select, update

from cash.access import CashOperator
from cash.amounts import kopecks_to_rub, micros_to_usdt
from cash.ids import human_id, partner_number
from cash.wallet import WalletService, status_ru
from online.schema import (
    cash_deposits, cash_fiat_orders, cash_operators, cash_withdrawals, support_messages,
    support_tickets, tenants, users,
)
from online.telegram import chat_username, edit_reply_markup, send_message, send_photo


logger = logging.getLogger("poker8.support")

TOPICS = {"finance": "Финансы", "support": "Поддержка"}
#: How many a player may have waiting at once. Enough for a real problem,
#: too few to be a broadcast channel.
MAX_OPEN = 3
MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

#: What the ticket is about, in the picker and on the card.
REFERENCE_KINDS = {"deposit": "Пополнение USDT", "fiat_order": "Пополнение ₽", "withdrawal": "Вывод"}


class SupportError(ValueError):
    pass


def short_id(ticket_id: str) -> str:
    return ticket_id[:6].upper()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def operator_keyboard(ticket_id: str, answered: bool, closed: bool = False) -> dict:
    """The buttons under an operator's copy of a player's message."""
    if closed:
        return {"inline_keyboard": [[{"text": "🔒 Тикет закрыт", "callback_data": "tnone:"}]]}
    if answered:
        return {"inline_keyboard": [
            [{"text": "✍️ Ответить", "callback_data": f"treply:{ticket_id}"},
             {"text": "Закрыть тикет", "callback_data": f"tclose:{ticket_id}"}],
            [{"text": "✅ Сообщение доставлено", "callback_data": "tnone:"}],
        ]}
    return {"inline_keyboard": [[
        {"text": "✍️ Ответить", "callback_data": f"treply:{ticket_id}"},
        {"text": "❌ Не отвечено", "callback_data": "tnone:"},
    ]]}


def player_keyboard(ticket_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "Ответить на сообщение", "callback_data": f"tk:r:{ticket_id}"},
        {"text": "Закрыть", "callback_data": f"tk:c:{ticket_id}"},
    ]]}


class SupportService:
    def __init__(self, session_factory, *, admin_token: str | None,
                 player_tokens: dict[str, str] | None = None) -> None:
        self.sessions = session_factory
        self.admin_token = admin_token or None
        #: tenant slug → the players' bot token, where answers are delivered.
        self.player_tokens = {slug: token for slug, token in (player_tokens or {}).items() if token}
        # ponytail: in-process, like the panel's own prompts. A player who
        # pressed "Ответить" in the bot and then restarted the server presses
        # it again.
        self.awaiting_reply: dict[int, str] = {}

    # --- what the site reads ---------------------------------------------------

    async def tickets(self, user_id: str, *, closed: bool = False) -> list[dict]:
        async with self.sessions() as session:
            where = support_tickets.c.status == "closed" if closed else support_tickets.c.status != "closed"
            rows = (await session.execute(
                select(support_tickets).where(support_tickets.c.user_id == user_id, where)
                .order_by(support_tickets.c.updated_at.desc()).limit(50)
            )).mappings().all()
            return [await self._ticket_payload(session, row) for row in rows]

    async def ticket(self, user_id: str, ticket_id: str) -> dict | None:
        async with self.sessions() as session:
            row = await self._ticket(session, ticket_id)
            if row is None or row["user_id"] != user_id:
                return None
            payload = await self._ticket_payload(session, row)
            messages = (await session.execute(
                select(support_messages).where(support_messages.c.ticket_id == ticket_id)
                .order_by(support_messages.c.created_at.asc(), support_messages.c.id.asc())
            )).mappings().all()
        payload["messages"] = [{
            "id": m["id"], "author": m["author"], "text": m["text"],
            "has_photo": bool(m["photo_file_id"]), "created_at": m["created_at"].isoformat(),
        } for m in messages]
        return payload

    async def references(self, user_id: str) -> list[dict]:
        """The player's own deposits, ₽ orders and withdrawals, newest first,
        for the "which one is this about" picker -- the history's own rows."""
        rows = await WalletService(self.sessions).operations(user_id, limit=30)
        return [{**row, "label": REFERENCE_KINDS[row["kind"]], "amount": (
            f"{row['fiat_rub']} ₽" if row["fiat_rub"] else f"{row['amount_usdt']} USDT"
        )} for row in rows]

    # --- what the player does --------------------------------------------------

    async def open(self, *, user_id: str, tenant_id: str, topic: str, text: str,
                   reference_kind: str | None = None, reference_id: str | None = None,
                   photo: bytes | None = None, photo_type: str | None = None) -> dict:
        if topic not in TOPICS:
            raise SupportError("неизвестная тема обращения")
        text = _clean_text(text)
        if reference_kind is not None and reference_kind not in REFERENCE_KINDS:
            raise SupportError("неизвестный тип заявки")
        if topic != "finance":
            reference_kind = reference_id = None
        _check_photo(photo, photo_type)
        now = _now()
        ticket_id = uuid4().hex
        async with self.sessions() as session:
            async with session.begin():
                open_count = (await session.execute(
                    select(func.count()).select_from(support_tickets).where(
                        support_tickets.c.user_id == user_id,
                        support_tickets.c.status != "closed",
                    ))).scalar_one()
                if open_count >= MAX_OPEN:
                    raise SupportError(f"у вас уже {MAX_OPEN} открытых обращения — дождитесь ответа")
                if reference_id and not await self._reference_belongs(
                        session, user_id, reference_kind, reference_id):
                    raise SupportError("заявка не найдена")
                await session.execute(support_tickets.insert().values(
                    id=ticket_id, user_id=user_id, tenant_id=tenant_id, topic=topic,
                    reference_kind=reference_kind, reference_id=reference_id,
                    status="open", created_at=now, updated_at=now,
                ))
                message_id = await self._add_message(session, ticket_id, "user", text, now)
        await self._deliver_to_operators(ticket_id, message_id, photo, photo_type)
        return (await self.ticket(user_id, ticket_id)) or {"id": ticket_id}

    async def user_reply(self, *, user_id: str, ticket_id: str, text: str,
                         photo: bytes | None = None, photo_type: str | None = None) -> dict:
        """From the site or from the bot -- either way the photo is bytes."""
        text = _clean_text(text, allow_empty=photo is not None)
        _check_photo(photo, photo_type)
        now = _now()
        async with self.sessions() as session:
            async with session.begin():
                row = await self._ticket(session, ticket_id)
                if row is None or row["user_id"] != user_id:
                    raise SupportError("обращение не найдено")
                if row["status"] == "closed":
                    raise SupportError("обращение закрыто — откройте новое")
                message_id = await self._add_message(session, ticket_id, "user", text, now)
                await session.execute(update(support_tickets).where(
                    support_tickets.c.id == ticket_id).values(status="open", updated_at=now))
        await self._deliver_to_operators(ticket_id, message_id, photo, photo_type)
        return (await self.ticket(user_id, ticket_id)) or {"id": ticket_id}

    async def close(self, ticket_id: str, *, user_id: str | None = None,
                    operator: CashOperator | None = None) -> dict:
        """Either side may end it. The other side is told."""
        now = _now()
        async with self.sessions() as session:
            async with session.begin():
                row = await self._ticket(session, ticket_id)
                if row is None or (user_id is not None and row["user_id"] != user_id):
                    raise SupportError("обращение не найдено")
                if operator is not None and not operator.can_access(row["tenant_id"]):
                    raise SupportError("обращение не найдено")
                if row["status"] == "closed":
                    return dict(row)
                await session.execute(update(support_tickets).where(
                    support_tickets.c.id == ticket_id
                ).values(status="closed", updated_at=now, closed_at=now))
                cards = await self._cards(session, ticket_id)
                player = await self._player(session, row)
        await self._redraw_cards(cards, operator_keyboard(ticket_id, True, closed=True))
        if operator is not None and player:
            await send_message(
                player["token"], player["telegram_user_id"],
                f"Обращение #{short_id(ticket_id)} закрыто поддержкой. "
                "Если вопрос остался — напишите новое.",
            )
        return {**dict(row), "status": "closed"}

    # --- what the operator does ------------------------------------------------

    async def open_for_operator(self, operator: CashOperator, *, limit: int = 10) -> list[dict]:
        """Tickets waiting on an answer, oldest first, for the panel's list."""
        async with self.sessions() as session:
            rows = (await session.execute(
                select(support_tickets).where(support_tickets.c.status != "closed")
                .order_by(support_tickets.c.updated_at.asc()).limit(50)
            )).mappings().all()
            rows = [row for row in rows if operator.can_access(row["tenant_id"])][:limit]
            cards = []
            for row in rows:
                last = (await session.execute(
                    select(support_messages).where(
                        support_messages.c.ticket_id == row["id"],
                        support_messages.c.author == "user",
                    ).order_by(support_messages.c.created_at.desc()).limit(1)
                )).mappings().first()
                cards.append({
                    "id": row["id"], "status": row["status"],
                    "text": await self._card_text(session, row, last["text"] if last else ""),
                    "keyboard": operator_keyboard(row["id"], row["status"] == "answered"),
                })
        return cards

    async def operator_reply(self, operator: CashOperator, ticket_id: str, text: str) -> str:
        """Record the answer, hand it to the player, and flip every card."""
        text = _clean_text(text)
        now = _now()
        async with self.sessions() as session:
            async with session.begin():
                row = await self._ticket(session, ticket_id)
                if row is None or not operator.can_access(row["tenant_id"]):
                    raise SupportError("обращение не найдено")
                if row["status"] == "closed":
                    raise SupportError("обращение уже закрыто")
                await self._add_message(session, ticket_id, "operator", text, now,
                                        operator_id=operator.id)
                await session.execute(update(support_tickets).where(
                    support_tickets.c.id == ticket_id).values(status="answered", updated_at=now))
                cards = await self._cards(session, ticket_id)
                player = await self._player(session, row)
        await self._redraw_cards(cards, operator_keyboard(ticket_id, True))
        delivered = False
        if player:
            delivered = await send_message(
                player["token"], player["telegram_user_id"],
                f"<b>Ответ поддержки по обращению #{short_id(ticket_id)}</b>\n\n{escape(text)}",
                reply_markup=player_keyboard(ticket_id), parse_mode="HTML",
            ) is not None
        return ("✅ Ответ доставлен игроку в бот и на сайт." if delivered
                else "✅ Ответ сохранён — игрок увидит его на сайте (в бот доставить не удалось).")

    # --- the players' bot ------------------------------------------------------

    async def ticket_for_telegram(self, telegram_user_id: int, ticket_id: str) -> dict | None:
        async with self.sessions() as session:
            row = await self._ticket(session, ticket_id)
            if row is None:
                return None
            user = (await session.execute(select(users.c.telegram_user_id).where(
                users.c.id == row["user_id"]))).scalar_one_or_none()
        return dict(row) if user == telegram_user_id else None

    # --- internals -------------------------------------------------------------

    async def _ticket(self, session, ticket_id: str):
        return (await session.execute(
            select(support_tickets).where(support_tickets.c.id == ticket_id))).mappings().first()

    async def _ticket_payload(self, session, row) -> dict:
        last = (await session.execute(
            select(support_messages.c.author, support_messages.c.text, support_messages.c.created_at)
            .where(support_messages.c.ticket_id == row["id"])
            .order_by(support_messages.c.created_at.desc(), support_messages.c.id.desc()).limit(1)
        )).mappings().first()
        return {
            "id": row["id"], "short_id": short_id(row["id"]), "topic": row["topic"],
            "topic_label": TOPICS[row["topic"]], "status": row["status"],
            "reference_kind": row["reference_kind"], "reference_id": row["reference_id"],
            "reference_label": REFERENCE_KINDS.get(row["reference_kind"] or ""),
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat(),
            "last_author": last["author"] if last else None,
            "last_text": last["text"] if last else "",
        }

    async def _add_message(self, session, ticket_id: str, author: str, text: str, now: datetime,
                           *, operator_id: str | None = None) -> str:
        message_id = uuid4().hex
        await session.execute(support_messages.insert().values(
            id=message_id, ticket_id=ticket_id, author=author, operator_id=operator_id,
            text=text, cards_json=[], created_at=now,
        ))
        return message_id

    async def _reference_belongs(self, session, user_id: str, kind: str | None, ref_id: str) -> bool:
        table = {"deposit": cash_deposits, "fiat_order": cash_fiat_orders,
                 "withdrawal": cash_withdrawals}.get(kind or "")
        if table is None:
            return False
        return (await session.execute(select(table.c.id).where(
            table.c.id == ref_id, table.c.user_id == user_id))).scalar_one_or_none() is not None

    async def _player(self, session, row) -> dict | None:
        """Where the answer goes: the player's chat, on their tenant's bot."""
        found = (await session.execute(
            select(users.c.telegram_user_id, tenants.c.slug)
            .join(tenants, tenants.c.id == row["tenant_id"])
            .where(users.c.id == row["user_id"]))).mappings().first()
        if found is None:
            return None
        token = self.player_tokens.get(found["slug"])
        if not token:
            return None
        return {"telegram_user_id": found["telegram_user_id"], "token": token}

    async def _cards(self, session, ticket_id: str) -> list[dict]:
        rows = (await session.execute(select(support_messages.c.cards_json).where(
            support_messages.c.ticket_id == ticket_id))).scalars().all()
        return [card for cards in rows for card in (cards or [])]

    async def _redraw_cards(self, cards: list[dict], keyboard: dict) -> None:
        if not self.admin_token:
            return
        for card in cards:
            await edit_reply_markup(self.admin_token, card["chat_id"], card["message_id"], keyboard)

    async def _card_text(self, session, row, text: str) -> str:
        user = (await session.execute(
            select(users.c.telegram_user_id, users.c.display_name, users.c.username)
            .where(users.c.id == row["user_id"]))).mappings().first()
        tg_id = user["telegram_user_id"] if user else "?"
        name = escape(user["display_name"] if user else "Игрок")
        handle = f"@{escape(user['username'])}" if user and user["username"] else "без @username"
        when = row["created_at"].astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M")
        lines = [
            f"🎫 <b>Обращение #{short_id(row['id'])}</b> — {TOPICS[row['topic']]}",
            "",
            f"👤 <b>Игрок:</b> <a href=\"tg://user?id={tg_id}\">{name}</a> · {handle}",
            f"🆔 <b>Telegram:</b> <code>{tg_id}</code>",
            f"🔑 <b>ID игрока:</b> <code>{escape(row['user_id'])}</code>",
            f"🕒 <b>Время:</b> {when} UTC",
        ]
        reference = await self._reference_line(session, row)
        if reference:
            lines += ["", reference]
        lines += ["", "💬 <b>Сообщение:</b>", escape(text) if text else "<i>(только изображение)</i>"]
        return "\n".join(lines)

    async def _reference_line(self, session, row) -> str | None:
        """The deposit, ₽ order or withdrawal a finance ticket points at."""
        kind, ref_id = row["reference_kind"], row["reference_id"]
        if not kind or not ref_id:
            return None
        table = {"fiat_order": cash_fiat_orders, "deposit": cash_deposits,
                 "withdrawal": cash_withdrawals}[kind]
        item = (await session.execute(select(table).where(table.c.id == ref_id))).mappings().first()
        if item is None:
            return f"📎 <b>{REFERENCE_KINDS[kind]}:</b> <code>{human_id(kind, ref_id)}</code>"
        if kind == "fiat_order":
            partner = partner_number(item["partner_order_id"]) or "не присвоен"
            amount = (kopecks_to_rub(item["fiat_kopecks"]) + " ₽" if item["fiat_kopecks"]
                      else micros_to_usdt(item["requested_micros"]) + " USDT")
            fields = [
                f"₽ <b>Пополнение картой</b> · {amount} · {status_ru('fiat_order', item['status'])}",
                f"🧾 <b>Ордер партнёра:</b> <code>{escape(str(partner))}</code>",
            ]
        elif kind == "deposit":
            fields = [
                f"₮ <b>Пополнение USDT</b> · {micros_to_usdt(item['expected_micros'])} USDT"
                f" · {status_ru('deposit', item['status'])}",
                f"🔗 <b>Адрес {escape(item['network'])}:</b> <code>{escape(item['destination_address'])}</code>",
            ]
        else:
            payout = (kopecks_to_rub(item["quote_kopecks"]) + " ₽" if item["quote_kopecks"]
                      else micros_to_usdt(item["amount_micros"]) + " USDT")
            fields = [
                f"💸 <b>Вывод</b> · {payout} · {escape(item['network'])} · {status_ru('withdrawal', item['status'])}",
                f"🔗 <b>Куда:</b> <code>{escape(item['destination_address'])}</code>",
            ]
        fields.append(f"🗂 <b>Покерокуб ID:</b> <code>{human_id(kind, ref_id)}</code>")
        return "\n".join(fields)

    async def _ensure_username(self, ticket_id: str) -> None:
        """A handle is recorded at login, and a player on an older session has
        not logged in since that started. Their bot knows it: ask once."""
        async with self.sessions() as session:
            row = await self._ticket(session, ticket_id)
            if row is None:
                return
            user = (await session.execute(select(users.c.id, users.c.username).where(
                users.c.id == row["user_id"]))).mappings().first()
            if user is None or user["username"]:
                return
            player = await self._player(session, row)
        if not player:
            return
        handle = await chat_username(player["token"], player["telegram_user_id"])
        if not handle:
            return
        async with self.sessions() as session:
            async with session.begin():
                await session.execute(update(users).where(users.c.id == user["id"])
                                      .values(username=handle))

    async def _deliver_to_operators(self, ticket_id: str, message_id: str,
                                    photo: bytes | None, photo_type: str | None) -> None:
        """One card per operator. The first photo upload yields a file_id the
        rest are sent with, and every landing spot is remembered."""
        if not self.admin_token:
            logger.warning("poker8_support_no_admin_bot", extra={"ticket_id": ticket_id})
            return
        await self._ensure_username(ticket_id)
        async with self.sessions() as session:
            row = await self._ticket(session, ticket_id)
            message = (await session.execute(select(support_messages).where(
                support_messages.c.id == message_id))).mappings().first()
            operators = (await session.execute(select(cash_operators).where(
                cash_operators.c.active.is_(True),
                cash_operators.c.role.in_(["operator", "admin"]),
            ))).mappings().all()
            text = await self._card_text(session, row, message["text"])
        keyboard = operator_keyboard(ticket_id, False)
        file_id = message["photo_file_id"]
        payload: bytes | str | None = file_id or photo
        cards = []
        for op in operators:
            operator = CashOperator(op["id"], op["telegram_user_id"], op["tenant_id"], op["role"])
            if not operator.can_access(row["tenant_id"]):
                continue
            chat_id = op["telegram_user_id"]
            if payload is not None:
                # A caption is capped at 1024 characters; the rest of a long
                # message follows as text of its own, under the same buttons.
                sent = await send_photo(self.admin_token, chat_id, payload, text[:1000],
                                        reply_markup=keyboard, parse_mode="HTML",
                                        filename=f"image.{PHOTO_TYPES.get(photo_type or '', 'jpg')}")
                if sent is not None:
                    sent, file_id = sent[0], (sent[1] or file_id)
                    payload = file_id or payload
            else:
                sent = await send_message(self.admin_token, chat_id, text,
                                          reply_markup=keyboard, parse_mode="HTML")
            if sent is not None:
                cards.append({"chat_id": chat_id, "message_id": sent})
        if not cards:
            logger.warning("poker8_support_undelivered", extra={"ticket_id": ticket_id})
        async with self.sessions() as session:
            async with session.begin():
                await session.execute(update(support_messages).where(
                    support_messages.c.id == message_id
                ).values(cards_json=cards, photo_file_id=file_id or None))


def _clean_text(text: str, *, allow_empty: bool = False) -> str:
    text = (text or "").strip()
    if not text and not allow_empty:
        raise SupportError("напишите сообщение")
    if len(text) > 2000:
        raise SupportError("сообщение не длиннее 2000 символов")
    return text


def _check_photo(photo: bytes | None, photo_type: str | None) -> None:
    if photo is None:
        return
    if photo_type not in PHOTO_TYPES:
        raise SupportError("изображение только JPG, PNG или WEBP")
    if len(photo) > MAX_PHOTO_BYTES:
        raise SupportError("изображение не больше 5 МБ")
    if not photo:
        raise SupportError("пустое изображение")
