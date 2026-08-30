"""Desktop chat is a window, not a layout row or a second mobile overlay."""

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.e2e


@pytest.fixture
def chat_page(online_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1192, "height": 882})
        page.request.post(f"{online_server}/api/auth/dev/202")
        rows = [dict(id=str(i), table_id="micro-a", user_id="another-user",
                     display_name="cold archive" if i % 2 else "MAKTRAXER",
                     text=f"Сообщение {i}: **хорошая раздача**",
                     created_at="2026-08-30T12:20:00+00:00") for i in range(40)]
        rows[-1]["text"] = "я" * 900
        page.route("**/api/tables/micro-a/chat", lambda route:
                   route.fulfill(json={"messages": rows}) if route.request.method == "GET"
                   else route.continue_())
        page.goto(f"{online_server}/table?table=micro-a", wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('p8-boot-ready') && document.querySelector('#chatPanel').dataset.p8Furnished")
        expect(page.locator(".p8-chat-row")).to_have_count(40)
        page.locator("#mobileChatButton").click()
        expect(page.locator("#chatPanel")).to_be_visible()
        yield page
        browser.close()


def _drag(page, locator, dx, dy):
    box = locator.bounding_box()
    x, y = box["x"] + 16, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=8)
    page.mouse.up()


def _in_view(page):
    page.wait_for_function("""() => {
        const box = document.querySelector('#chatPanel').getBoundingClientRect();
        return box.x >= 0 && box.y >= 0 && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1;
    }""")
    box = page.locator("#chatPanel").bounding_box()
    assert box["x"] >= 0 and box["y"] >= 0, box
    assert box["x"] + box["width"] <= page.viewport_size["width"] + 1, box
    assert box["y"] + box["height"] <= page.viewport_size["height"] + 1, box


def test_window_moves_resizes_and_never_moves_the_table(chat_page):
    page = chat_page
    panel = page.locator("#chatPanel")
    before = panel.bounding_box()
    felt = page.locator(".felt").bounding_box()
    _drag(page, panel.locator("h2"), -250, 40)
    moved = panel.bounding_box()
    assert moved["x"] == pytest.approx(before["x"] - 250, abs=1)
    assert moved["y"] == pytest.approx(before["y"] + 40, abs=1)
    resize = page.get_by_role("button", name="Изменить размер чата")
    _drag(page, resize, 80, 40)
    enlarged = panel.bounding_box()
    assert enlarged["width"] == pytest.approx(moved["width"] + 80, abs=1)
    assert enlarged["height"] == pytest.approx(moved["height"] + 40, abs=1)
    page.get_by_role("textbox", name="Сообщение").fill("Черновик")
    page.get_by_role("button", name="Свернуть чат").click()
    assert panel.bounding_box()["height"] <= 72
    expect(page.locator("#chatForm")).to_be_hidden()
    page.get_by_role("button", name="Развернуть чат").click()
    expect(page.get_by_role("textbox", name="Сообщение")).to_have_value("Черновик")
    assert panel.bounding_box()["height"] == pytest.approx(enlarged["height"], abs=1)
    page.get_by_role("button", name="Закрыть чат", exact=True).click()
    expect(panel).to_be_hidden()
    page.locator("#mobileChatButton").click()
    assert panel.bounding_box() == enlarged
    assert page.locator(".felt").bounding_box() == felt
    page.set_viewport_size({"width": 781, "height": 420})
    _in_view(page)
    _drag(page, panel.locator("h2"), -1200, -1000)
    _in_view(page)
    page.get_by_role("button", name="Вернуть положение чата").click()
    _in_view(page)
    panel.locator("h2").focus()
    x = panel.bounding_box()["x"]
    page.keyboard.press("ArrowLeft")
    assert panel.bounding_box()["x"] == pytest.approx(x - 10, abs=1)


def test_desktop_feed_wraps_and_uses_the_window_height(chat_page):
    page = chat_page
    expect(page.locator(".chat-turn-banner")).to_be_hidden()
    feed = page.locator("#chatMessages")
    assert feed.bounding_box()["height"] > 260
    assert feed.evaluate("e => e.scrollWidth <= e.clientWidth")
    assert feed.evaluate("e => e.scrollHeight - e.scrollTop - e.clientHeight < 24"), feed.evaluate("e => ({top:e.scrollTop, height:e.scrollHeight, client:e.clientHeight})")
    expect(feed.locator("time").last).to_be_visible()
    expect(page.locator("#chatPanel .chat-close")).to_have_css("position", "absolute")


def test_new_messages_dont_pull_reader_from_history(chat_page, online_server):
    page = chat_page
    feed = page.locator("#chatMessages")
    feed.evaluate("e => e.scrollTop = 0")
    page.request.post(f"{online_server}/api/tables/micro-a/chat", data={"text": "Новое в конце"})
    expect(feed.locator(".p8-chat-row").last).to_contain_text("Новое в конце")
    assert feed.evaluate("e => e.scrollTop") == 0
    page.get_by_role("button", name="Новые сообщения ↓").click()
    assert feed.evaluate("e => e.scrollHeight - e.scrollTop - e.clientHeight < 24")


def test_multiline_send_errors_keep_the_draft(chat_page):
    page = chat_page
    editor = page.get_by_role("textbox", name="Сообщение")
    assert editor.evaluate("e => e.tagName") == "TEXTAREA"
    editor.fill("Первая строка")
    editor.press("End")
    editor.press("Shift+Enter")
    page.keyboard.insert_text("Вторая строка")
    expect(editor).to_have_value("Первая строка\nВторая строка")
    page.route("**/api/tables/micro-a/chat", lambda route: route.fulfill(status=429, json={"detail": "rate limited"}))
    editor.press("Enter")
    expect(page.locator(".chat-send-status")).to_contain_text("Не удалось отправить")
    expect(editor).to_have_value("Первая строка\nВторая строка")
    expect(page.locator("#chatForm button")).to_be_enabled()
    page.unroute("**/api/tables/micro-a/chat")
    editor.press("Enter")
    expect(editor).to_have_value("")
    expect(page.locator(".p8-chat-row").last).to_contain_text("Вторая строка")


def test_phone_keeps_fullpage_chat_and_its_input(chat_page):
    page = chat_page
    page.get_by_role("textbox", name="Сообщение").fill("Черновик")
    page.get_by_role("button", name="Свернуть чат").click()
    page.set_viewport_size({"width": 390, "height": 844})
    panel = page.locator("#chatPanel")
    assert panel.bounding_box() == {"x": 0, "y": 0, "width": 390, "height": 844}
    expect(page.locator("#chatForm")).to_be_visible()
    expect(page.locator(".chat-window-tools")).to_be_hidden()
    assert page.locator("#chatInput").evaluate("e => e.tagName") == "INPUT"
    expect(page.get_by_role("textbox", name="Сообщение")).to_have_value("Черновик")
    page.set_viewport_size({"width": 1192, "height": 882})
    _in_view(page)
    expect(page.get_by_role("textbox", name="Сообщение")).to_have_value("Черновик")
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
