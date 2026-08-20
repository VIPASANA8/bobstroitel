"""The message formatter ported from board2.

Escape first, introduce tags second: every assertion below about safety rests
on that order, so the tests state it directly rather than trusting the grammar.
"""

import json
import re
import subprocess
from pathlib import Path

SOURCE = Path("static/chat-format.js")


def render(*texts):
    """Run the real file under node and render each input."""
    script = (
        "global.window = {}; global.Event = function(){};\n"
        f"new Function(require('fs').readFileSync({json.dumps(str(SOURCE))},'utf8'))();\n"
        f"const inputs = {json.dumps(list(texts))};\n"
        "console.log(JSON.stringify(inputs.map(t => window.Poker8ChatFormat.render(t))));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return json.loads(out.stdout)


def test_the_inline_grammar_came_across():
    bold, italic, strike, code, spoiler = render(
        "**жир**", "*курсив*", "~~зачёркнуто~~", "`код`", "||секрет||")
    assert bold == "<strong>жир</strong>"
    assert italic == "<em>курсив</em>"
    assert strike == "<s>зачёркнуто</s>"
    assert 'class="p8-chat-code">код</code>' in code
    assert "data-chat-spoiler" in spoiler and "секрет" in spoiler


def test_markup_a_player_types_is_text_not_markup():
    [rendered] = render('<img src=x onerror=alert(1)><script>alert(2)</script>')
    assert "<img" not in rendered and "<script" not in rendered
    assert "&lt;img" in rendered and "&lt;script" in rendered


def test_a_link_has_to_be_a_scheme_we_allow():
    """A refused link stays literal text -- the scheme is still visible in it,
    which is the point: it is shown, not followed."""
    ok, script, data = render(
        "[да](https://example.com)", "[нет](javascript:alert(1))", "[нет](data:text/html,x)")
    assert 'href="https://example.com"' in ok and "<a " in ok
    for refused in (script, data):
        assert "<a " not in refused, refused
        assert "href=" not in refused, refused


def test_a_bare_url_becomes_a_link_without_swallowing_the_full_stop():
    [rendered] = render("смотри https://bubbledouble.cc/table. дальше")
    assert 'href="https://bubbledouble.cc/table"' in rendered
    assert rendered.rstrip().endswith(". дальше")


def test_emphasis_does_not_reach_inside_code():
    """Code and links are parked as placeholders before the emphasis rules run,
    which is the only reason an asterisk in a code span survives."""
    [rendered] = render("**жир** и `звёздочка *внутри*`")
    assert "<strong>жир</strong>" in rendered
    assert "*внутри*" in rendered and "<em>внутри</em>" not in rendered


def test_a_fence_becomes_a_block_and_an_unclosed_one_does_not():
    block, open_fence = render("```\nplain <b>x</b>\n```", "```ещё пишу")
    assert 'class="p8-chat-block"' in block and "&lt;b&gt;" in block
    assert "p8-chat-block" not in open_fence, "somebody mid-sentence is not a code block"


def test_the_placeholder_pattern_uses_a_digit_class_not_an_escape():
    """A backslash has to survive both a template literal and a JS string to
    reach the regex; twice it did not, and every code span, spoiler and link
    rendered as the literal placeholder text instead."""
    source = SOURCE.read_text(encoding="utf-8")
    assert 'NULL + "MD([0-9]+)" + NULL' in source


def test_the_table_renders_chat_through_it():
    online = Path("static/online-table.js").read_text(encoding="utf-8")
    markup = Path("static/index.html").read_text(encoding="utf-8")
    assert "Poker8ChatFormat.render" in online
    assert "escapeHtml(row.text" not in online, "the raw-escape path is gone"
    assert "chat-format.js?v=" in markup
    for kind in ("bold", "italic", "strike", "code", "spoiler", "link"):
        assert f'data-chat-format="{kind}"' in markup


def test_the_cap_leaves_room_for_the_markers():
    server = Path("online/chat.py").read_text(encoding="utf-8")
    router = Path("app/routers/chat.py").read_text(encoding="utf-8")
    # One name for the limit, so the column, the router and the check cannot
    # drift apart again -- they already had, and Postgres was the one to say so.
    assert "CHAT_TEXT_MAX = 1000" in server
    assert "len(text) > CHAT_TEXT_MAX" in server
    assert "max_length=CHAT_TEXT_MAX" in router
    assert re.search(r'maxlength="1000"', Path("static/index.html").read_text(encoding="utf-8"))
    # And the column has to be at least as wide, or the database is the one
    # that says no -- with the player seeing a 500 for a message it accepted.
    assert 'Column("text", String(1000)' in Path("online/schema.py").read_text(encoding="utf-8")
