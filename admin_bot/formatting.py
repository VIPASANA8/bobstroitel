from cash.ids import human_id, partner_number
from html import escape


def _usdt(micros):
    whole, fraction = divmod(int(micros), 1_000_000)
    return str(whole) if not fraction else f"{whole}.{fraction:06d}".rstrip("0")


def _rub(kopecks):
    return "—" if kopecks is None else f"{int(kopecks) // 100},{int(kopecks) % 100:02d}"


def queue_messages(queue):
    messages = []
    for row in queue.get("withdrawals", []):
        messages.append((
            "withdrawal", row["id"], row["status"],
            f"💸 <b>Вывод</b> <code>{human_id('withdrawal', row['id'])}</code>\n"
            f"Статус: <b>{escape(row['status'])}</b>\n"
            f"Пользователь: <code>{escape(row['user_id'])}</code>\n"
            f"Сумма: {_usdt(row['amount_micros'])} USDT\n"
            + (f"К отправке: <b>{_rub(row['quote_kopecks'])} ₽</b>\n" if row.get("quote_kopecks") else "")
            + f"Адрес: <code>{escape(row['destination_address'])}</code>",
        ))
    for row in queue.get("payment_reviews", []):
        messages.append((
            "payment", row["id"], row["status"],
            f"🔎 <b>Платёж на разборе</b> <code>{escape(row['id'])}</code>\n"
            f"Сумма: {_usdt(row['amount_micros'])} USDT\n"
            f"TX: <code>{escape(row['tx_hash'])}</code>\n"
            f"Deposit: <code>{escape(str(row.get('deposit_id') or 'не найден'))}</code>",
        ))
    for row in queue.get("fiat_orders", []):
        messages.append((
            "fiat_order", row["id"], row["status"],
            f"₽ <b>Fiat P2P</b> <code>{human_id('fiat_order', row['id'])}</code>\n"
            f"Статус: <b>{escape(row['status'])}</b>\n"
            f"Пользователь: <code>{escape(row['user_id'])}</code>\n"
            f"Сумма: {_usdt(row['requested_micros'])} USDT / "
            f"{_rub(row.get('fiat_kopecks'))} {escape(row['currency'])}\n"
            f"Ордер партнёра: <code>{escape(partner_number(row.get('partner_order_id')) or 'не создан')}</code>\n"
            f"Детали: {escape(row.get('detail') or '—')}",
        ))
    for row in queue.get("fiat_reviews", []):
        messages.append((
            "fiat_event", str(row["event_id"]), row["status"],
            f"⚠️ <b>Событие P2P на разборе</b> <code>{escape(str(row['event_id']))}</code>\n"
            f"Ордер партнёра: <code>{escape(partner_number(row['partner_order_id']) or '—')}</code>\n"
            f"Тип: <b>{escape(row['event_type'])}</b>\n"
            f"Детали: {escape(row.get('detail') or '—')}",
        ))
    for row in queue.get("paused_tables", []):
        messages.append((
            "table", row["id"], "paused",
            f"⛔ <b>CASH-стол остановлен</b> <code>{escape(row['id'])}</code>\n"
            f"Причина: {escape(row.get('paused_reason') or 'не указана')}",
        ))
    return messages


def fiat_order_message(order):
    events = "\n".join(
        "• #{id} {type} · {status}{detail}".format(
            id=escape(str(event["event_id"])), type=escape(event["event_type"]),
            status=escape(event["status"]),
            detail=" · " + escape(event["detail"]) if event.get("detail") else "",
        )
        for event in order.get("events", [])
    ) or "событий пока нет"
    return (
        f"\u20bd <b>Fiat P2P</b> <code>{human_id('fiat_order', order['id'])}</code>\n"
        f"Статус: <b>{escape(order['status'])}</b>\n"
        f"Пользователь: <code>{escape(order['user_id'])}</code>\n"
        f"Сумма: {_usdt(order['requested_micros'])} USDT / "
        f"{_rub(order.get('fiat_kopecks'))} {escape(order['currency'])}\n"
        f"Ордер партнёра: <code>{escape(partner_number(order.get('partner_order_id')) or 'не создан')}</code>\n"
        f"Полный id: <code>{escape(order['id'])}</code>\n"
        f"Трейдер: {escape(order.get('trader_username') or '—')} · "
        f"реквизиты {escape(order.get('requisites_tail') or '—')}\n"
        f"Истекает: {escape(str(order.get('expires_at') or '—'))}\n"
        f"Детали: {escape(order.get('detail') or '—')}\n"
        f"События:\n{events}"
    )


def reconciliation_message(report):
    mismatches = "\n".join(
        "• <code>{order}</code> — {reason}".format(
            order=escape(str(row["order_id"])), reason=escape(row["reason"]),
        )
        for row in report["mismatches"]
    )
    orders, ledger, balances = report["orders"], report["ledger"], report["balances"]
    lines = [
        ("✅" if report["balanced"] else "❗") + f" <b>Сверка RUB · {escape(report['day'])}</b>",
        "",
        "<b>Заявки</b>",
        f"Зачислено заявок: <b>{orders['count']}</b>",
        f"Получено от игроков: <b>{escape(orders['charged_rub'])} ₽</b>",
        "",
        "<b>USDT</b>",
        f"Зачислено игрокам: <b>{escape(orders['credited_usdt'])} USDT</b>",
        f"По внутренней книге: {escape(ledger['credited_usdt'])} USDT",
        f"Комиссия: <b>{escape(orders['fee_usdt'])} USDT</b>",
        f"По внутренней книге комиссии: {escape(ledger['fee_usdt'])} USDT",
        "",
        "<b>Баланс</b>",
        f"Изменение расчётного баланса за день: <b>{escape(ledger['clearing_usdt'])} USDT</b>",
        f"Расчётный баланс: <b>{escape(balances['clearing_usdt'])} USDT</b>",
        f"Баланс комиссий: <b>{escape(balances['fee_usdt'])} USDT</b>",
    ]
    if mismatches:
        lines.extend(["", "<b>Расхождения</b>", mismatches])
    return "\n".join(lines)


def user_card(user):
    balances = user["balances"]
    hold = user.get("hold")
    cancellations = user.get("cancellations_after_payment") or 0
    lines = [
        f"👤 <b>{escape(user['display_name'])}</b> <code>{escape(user['id'])}</code>",
        f"Telegram: <code>{user['telegram_user_id']}</code>",
        f"Доступно: {escape(balances['available']['usdt'])} USDT / "
        f"{escape(balances['available']['units'])} CASH",
        f"За столами: {escape(balances['escrow']['usdt'])} USDT",
        f"В выводе: {escape(balances['withdrawal']['usdt'])} USDT",
    ]
    if hold:
        lines.append(
            f"🚫 <b>Заморожен</b>: {escape(hold['reason'])} "
            f"(оператор <code>{escape(hold['operator_id'])}</code>)"
        )
    if cancellations:
        lines.append(f"⚠️ Отмен после «я оплатил» за сутки: {cancellations}")
    return "\n".join(lines)
