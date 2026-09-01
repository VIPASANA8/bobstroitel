from html import escape


def _usdt(micros):
    whole, fraction = divmod(int(micros), 1_000_000)
    return str(whole) if not fraction else f"{whole}.{fraction:06d}".rstrip("0")


def queue_messages(queue):
    messages = []
    for row in queue.get("withdrawals", []):
        messages.append((
            "withdrawal", row["id"], row["status"],
            f"💸 <b>Вывод</b> <code>{escape(row['id'])}</code>\n"
            f"Статус: <b>{escape(row['status'])}</b>\n"
            f"Пользователь: <code>{escape(row['user_id'])}</code>\n"
            f"Сумма: {_usdt(row['amount_micros'])} USDT\n"
            f"Адрес: <code>{escape(row['destination_address'])}</code>",
        ))
    for row in queue.get("payment_reviews", []):
        messages.append((
            "payment", row["id"], row["status"],
            f"🔎 <b>Платёж на разборе</b> <code>{escape(row['id'])}</code>\n"
            f"Сумма: {_usdt(row['amount_micros'])} USDT\n"
            f"TX: <code>{escape(row['tx_hash'])}</code>\n"
            f"Deposit: <code>{escape(str(row.get('deposit_id') or 'не найден'))}</code>",
        ))
    for row in queue.get("paused_tables", []):
        messages.append((
            "table", row["id"], "paused",
            f"⛔ <b>CASH-стол остановлен</b> <code>{escape(row['id'])}</code>\n"
            f"Причина: {escape(row.get('paused_reason') or 'не указана')}",
        ))
    return messages
