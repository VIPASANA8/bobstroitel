from pathlib import Path

from app.routers.telegram import WELCOME


EXPECTED = (
    "<b>Привет! 👋</b>\n\n"
    "Играйте в <b>POKER</b>, бросайте кубик в <b>CUBE</b> и выводите средства "
    "в <b>рублях или USDT</b>.\n\n"
    "♠️ <b>POKER:</b> donbass.win\n\n"
    "🎲 <b>CUBE:</b> donbass.win/cube\n\n"
    "Или играйте прямо в Telegram — нажмите кнопку <b>«Играть»</b>.\n\n"
    "👥 <b>Приглашайте друзей и зарабатывайте от 5 до 15% с их игры!</b>"
)


def test_player_bot_welcome_copy_and_html_mode():
    assert WELCOME == EXPECTED
    source = Path("app/routers/telegram.py").read_text(encoding="utf-8")
    assert 'WELCOME + (REFERRAL_LINE.format(link=link) if link else "")' in source
    assert 'parse_mode="HTML"' in source
