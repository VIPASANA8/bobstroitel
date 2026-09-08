from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CSS = re.sub(
    r"/\*.*?\*/",
    "",
    (ROOT / "static" / "game-tabs.css").read_text(encoding="utf-8"),
    flags=re.DOTALL,
)
LOBBY = (ROOT / "static" / "lobby.html").read_text(encoding="utf-8")
CUBE = (ROOT / "static" / "cube.html").read_text(encoding="utf-8")


def normalize_selector(selector: str) -> str:
    selector = re.sub(r"\s+", " ", selector.strip())
    return re.sub(r"\s*>\s*", ">", selector)


def declarations(body: str) -> dict[str, str]:
    return {
        name.strip().lower(): re.sub(r"\s+", "", value).lower()
        for declaration in body.split(";")
        if ":" in declaration
        for name, value in [declaration.split(":", 1)]
    }


def specificity(selector: str) -> tuple[int, int, int]:
    return (
        selector.count("#"),
        selector.count(".") + selector.count("[") + selector.count(":"),
        len(re.findall(r"(?:^|[ >])([a-z][\w-]*)", selector)),
    )


def rules() -> list[tuple[str, dict[str, str], int]]:
    parsed = []
    for order, match in enumerate(re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS)):
        body = declarations(match.group(2))
        for selector in match.group(1).split(","):
            parsed.append((normalize_selector(selector), body, order))
    return parsed


CSS_RULES = rules()


def effective_declarations(*selectors: str) -> dict[str, str]:
    wanted = {normalize_selector(selector) for selector in selectors}
    effective = {}
    matching = [
        (specificity(selector), order, body)
        for selector, body, order in CSS_RULES
        if selector in wanted
    ]
    assert matching, f"missing CSS rules: {', '.join(sorted(wanted))}"
    for _, _, body in sorted(matching, key=lambda item: (item[0], item[1])):
        effective.update(body)
    return effective


def test_game_tabs_use_equal_selected_segment_visuals():
    inactive = effective_declarations(".game-tab")
    poker = effective_declarations(".game-tab", ".game-tab.is-active", ".game-tab-poker.is-active")
    cube = effective_declarations(".game-tab", ".game-tab.is-active", ".game-tab-cube.is-active")
    poker_icon = effective_declarations(".game-tab>i", ".game-tab-poker.is-active>i")
    cube_icon = effective_declarations(".game-tab>i", ".game-tab-cube.is-active>i")

    assert inactive.get("border") == "1pxsolidtransparent"
    assert inactive.get("color") == "#747985"
    assert poker.get("color") == "#fff"
    assert cube.get("color") == "#fff"
    assert poker.get("font-weight") == "700"
    assert cube.get("font-weight") == "700"

    assert poker.get("background") == "rgba(181,140,255,.12)"
    assert poker.get("border-color") == "rgba(181,140,255,.45)"
    assert poker.get("box-shadow") == "inset0012pxrgba(181,140,255,.06)"
    assert poker_icon.get("color") == "#b58cff"

    assert cube.get("background") == "rgba(183,255,38,.11)"
    assert cube.get("border-color") == "rgba(183,255,38,.4)"
    assert cube.get("box-shadow") == "inset0012pxrgba(183,255,38,.05)"
    assert cube_icon.get("color") == "#b7ff26"


def test_pages_keep_the_existing_active_tab_mapping():
    assert '<a class="game-tab game-tab-poker is-active" href="/" aria-current="page">' in LOBBY
    assert '<a class="game-tab game-tab-cube" href="/cube">' in LOBBY
    assert '<a class="game-tab game-tab-poker" href="/">' in CUBE
    assert '<a class="game-tab game-tab-cube is-active" href="/cube" aria-current="page">' in CUBE
    assert LOBBY.count('aria-current="page"') == 1
    assert CUBE.count('aria-current="page"') == 1
