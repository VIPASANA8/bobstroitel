from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "game-tabs.css").read_text(encoding="utf-8")
LOBBY = (ROOT / "static" / "lobby.html").read_text(encoding="utf-8")
CUBE = (ROOT / "static" / "cube.html").read_text(encoding="utf-8")


def rule(selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", CSS)
    assert match, f"missing CSS rule: {selector}"
    return re.sub(r"\s+", "", match.group(1)).lower()


def test_game_tabs_use_equal_selected_segment_visuals():
    inactive = rule(".game-tab")
    active = rule(".game-tab.is-active")
    poker = rule(".game-tab-poker.is-active")
    poker_icon = rule(".game-tab-poker.is-active>i")
    cube = rule(".game-tab-cube.is-active")
    cube_icon = rule(".game-tab-cube.is-active>i")

    assert "border:1pxsolidtransparent" in inactive
    assert "color:#747985" in inactive
    assert "color:#fff" in active
    assert "font-weight:700" in active

    assert "background:rgba(181,140,255,.12)" in poker
    assert "border-color:rgba(181,140,255,.45)" in poker
    assert "box-shadow:inset00" in poker
    assert "color:#b58cff" in poker_icon

    assert "background:rgba(183,255,38,.11)" in cube
    assert "border-color:rgba(183,255,38,.4)" in cube
    assert "box-shadow:inset00" in cube
    assert "color:#b7ff26" in cube_icon


def test_pages_keep_the_existing_active_tab_mapping():
    assert 'class="game-tab game-tab-poker is-active"' in LOBBY
    assert 'class="game-tab game-tab-cube"' in LOBBY
    assert 'class="game-tab game-tab-poker"' in CUBE
    assert 'class="game-tab game-tab-cube is-active"' in CUBE
    assert LOBBY.count('aria-current="page"') == 1
    assert CUBE.count('aria-current="page"') == 1
