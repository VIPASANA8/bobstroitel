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


def _split_label(partner_bps):
    partner = int(partner_bps or 0)
    owner = 10_000 - partner
    return f"{_share_percent(owner)}/{_share_percent(partner)}"


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
        "",
        "<b>Выплаты</b>",
        f"В ожидании: <b>{escape(str(totals.get('pending', '0')))} USDT</b>",
        f"Доступно к выплате: <b>{escape(str(totals.get('available', '0')))} USDT</b>",
        f"Отменено: <b>{escape(str(totals.get('reversed', '0')))} USDT</b>",
        "",
        f"<b>Начислено по играм · последние {len(settlements)} расчётов</b>",
        f"♠️ POKER: <b>{_usdt(poker)} USDT</b>",
        f"🎲 CUBE: <b>{_usdt(cube)} USDT</b>",
    ]

    groups = report.get("largest_groups") or []
    if groups:
        lines.extend(["", "<b>Крупнейшие реферальные группы</b>"])
        for row in groups[:5]:
            invited = int(row.get("invited") or 0)
            lines.append(
                f"• <code>{escape(str(row['referrer_id']))}</code> — приглашено {invited}"
            )
    else:
        lines.extend(["", "Рефералов пока нет."])
    return "\n".join(lines)


def _partner_totals(report):
    settlements = report.get("settlements") or []
    posted = [row for row in settlements if row.get("posted")]
    partner = _sum(posted, "amount_micros")
    # net_micros is Cube result after referral cost and agreed Cube
    # adjustments. Subtracting the posted partner share leaves RICK's side of
    # the same paying periods without double-counting report-only rows.
    owner = _sum(posted, "net_micros") - partner
    return posted, owner, partner


def partner_message(report):
    shares = report.get("shares") or []
    posted, owner, partner = _partner_totals(report)
    current_bps = int(shares[0].get("share_bps") or 0) if shares else 0

    return "\n".join([
        "🤝 <b>Партнёр / CUBE</b>",
        f"Текущая доля: <b>{_split_label(current_bps)}</b>",
        f"BOOSTER: <b>{_usdt(partner)} USDT</b>",
        f"RICK: <b>{_usdt(owner)} USDT</b>",
        "",
        f"Закрытых платёжных периодов: {len(posted)}",
    ])


def economy_message(referrals, partner, overview=None):
    ref = _referral_totals_micros(referrals)
    posted, _owner, partner_total = _partner_totals(partner)
    shares = partner.get("shares") or []
    current_bps = int(shares[0].get("share_bps") or 0) if shares else 0
    referral_active = ref["pending"] + ref["available"]
    overview = overview or {}
    cube = int(overview.get("cube_house_micros", _sum(posted, "net_micros")) or 0)
    poker = int(overview.get("poker_house_micros", 0) or 0)

    return "\n".join([
        "📊 <b>Экономика проекта</b>",
        "",
        f"CUBE: <b>{_usdt(cube)} USDT</b>",
        f"POKER: <b>{_usdt(poker)} USDT</b>",
        "",
        f"BOOSTER: <b>{_usdt(partner_total)} USDT</b> ({_share_percent(current_bps)}%)",
        f"Платёжных периодов: {len(posted)}",
        "",
        "<b>Реферальные выплаты · всё время</b>",
        f"Начислено и не отменено: {_usdt(referral_active)} USDT",
        f"• hold: {_usdt(ref['pending'])} USDT",
        f"• available: {_usdt(ref['available'])} USDT",
        f"• reversed: {_usdt(ref['reversed'])} USDT",
    ])
