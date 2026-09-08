from html import escape


def _usdt(micros):
    value = int(micros or 0)
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 1_000_000)
    rendered = str(whole) if not fraction else f"{whole}.{fraction:06d}".rstrip("0")
    return sign + rendered


def _sum(rows, key):
    return sum(int(row.get(key) or 0) for row in rows)


def _share_percent(bps):
    value = int(bps or 0)
    whole, fraction = divmod(value, 100)
    return str(whole) if not fraction else f"{whole}.{fraction:02d}".rstrip("0")


def _referral_totals_micros(report):
    totals = {"pending": 0, "available": 0, "reversed": 0}
    # totals_usdt is intentionally the authoritative all-time total from the
    # backend. Convert its decimal strings back to micros only for arithmetic
    # in the combined /economy card; display paths keep the original values.
    for status, raw in (report.get("totals_usdt") or {}).items():
        if status not in totals:
            continue
        text = str(raw or "0")
        negative = text.startswith("-")
        if negative:
            text = text[1:]
        whole, _, fraction = text.partition(".")
        micros = int(whole or 0) * 1_000_000 + int((fraction + "000000")[:6])
        totals[status] = -micros if negative else micros
    return totals


def referral_message(report):
    totals = report.get("totals_usdt") or {}
    settlements = report.get("settlements") or []
    active = [row for row in settlements if row.get("status") != "reversed"]
    poker = _sum((row for row in active if row.get("source") == "poker"), "amount_micros")
    cube = _sum((row for row in active if row.get("source") == "cube"), "amount_micros")

    lines = [
        "👥 <b>Реферальная программа</b>",
        f"На hold: <b>{escape(str(totals.get('pending', '0')))} USDT</b>",
        f"Доступно реферерам: <b>{escape(str(totals.get('available', '0')))} USDT</b>",
        f"Отменено / reversed: <b>{escape(str(totals.get('reversed', '0')))} USDT</b>",
        "",
        f"Последние {len(settlements)} расчётов:",
        f"• Poker RevShare: {_usdt(poker)} USDT",
        f"• CUBE RevShare: {_usdt(cube)} USDT",
    ]

    groups = report.get("largest_groups") or []
    if groups:
        lines.extend(["", "<b>Крупнейшие реферальные группы</b>"])
        for row in groups[:5]:
            lines.append(
                f"• <code>{escape(str(row['referrer_id']))}</code> — {int(row.get('invited') or 0)} приглашённых"
            )
    else:
        lines.extend(["", "Реферальных групп пока нет"])
    return "\n".join(lines)


def _partner_totals(report):
    settlements = report.get("settlements") or []
    posted = [row for row in settlements if row.get("posted")]
    partner = _sum(posted, "amount_micros")
    # net_micros is Cube result after referral cost and agreed Cube
    # adjustments. Subtracting the posted partner share leaves the owner's
    # side of the same paying periods without double-counting report-only rows.
    owner = _sum(posted, "net_micros") - partner
    return posted, owner, partner


def partner_message(report):
    settlements = report.get("settlements") or []
    shares = report.get("shares") or []
    posted, owner, partner = _partner_totals(report)
    current_bps = int(shares[0].get("share_bps") or 0) if shares else 0

    lines = [
        "🤝 <b>Партнёр / CUBE</b>",
        f"Текущая доля партнёра: <b>{_share_percent(current_bps)}%</b>",
        f"Партнёр заработал по закрытым платёжным периодам: <b>{_usdt(partner)} USDT</b>",
        f"Твоя сторона CUBE по тем же периодам: <b>{_usdt(owner)} USDT</b>",
        f"Закрытых платёжных периодов: {len(posted)}",
    ]

    if settlements:
        row = settlements[0]
        owner_period = int(row.get("net_micros") or 0) - int(row.get("amount_micros") or 0)
        lines.extend([
            "",
            f"<b>Последний расчёт · {escape(str(row.get('period_kind') or '—'))}</b>",
            f"{escape(str(row.get('period_start') or '—'))} → {escape(str(row.get('period_end') or '—'))}",
            f"Валовый CUBE P&L: {_usdt(row.get('gross_micros'))} USDT",
            f"Реферальные расходы CUBE: {_usdt(row.get('referral_cost_micros'))} USDT",
            f"Корректировки CUBE: {_usdt(row.get('adjustment_micros'))} USDT",
            f"Чистый CUBE: {_usdt(row.get('net_micros'))} USDT",
            f"Партнёр: {_usdt(row.get('amount_micros'))} USDT · твоя сторона: {_usdt(owner_period)} USDT",
            f"Carryover: {_usdt(row.get('carryover_after_micros'))} USDT",
            "Статус: " + ("✅ платёжный период" if row.get("posted") else "ℹ️ отчётный период"),
        ])
    return "\n".join(lines)


def economy_message(referrals, partner):
    ref = _referral_totals_micros(referrals)
    posted, owner, partner_total = _partner_totals(partner)
    shares = partner.get("shares") or []
    current_bps = int(shares[0].get("share_bps") or 0) if shares else 0
    referral_active = ref["pending"] + ref["available"]

    return "\n".join([
        "📊 <b>Экономика проекта</b>",
        "<i>CUBE — только закрытые платёжные периоды партнёрки.</i>",
        "",
        f"Твоя сторона CUBE: <b>{_usdt(owner)} USDT</b>",
        f"Партнёр: <b>{_usdt(partner_total)} USDT</b> ({_share_percent(current_bps)}%)",
        f"Платёжных периодов: {len(posted)}",
        "",
        "<b>Реферальные выплаты · всё время</b>",
        f"Начислено и не отменено: {_usdt(referral_active)} USDT",
        f"• hold: {_usdt(ref['pending'])} USDT",
        f"• available: {_usdt(ref['available'])} USDT",
        f"• reversed: {_usdt(ref['reversed'])} USDT",
        "",
        "Подробнее: /partner и /referrals",
    ])
