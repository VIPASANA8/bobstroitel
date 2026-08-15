import time

from playwright.sync_api import Page, sync_playwright
import pytest


pytestmark = pytest.mark.e2e


def test_mobile_online_flow(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page: Page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        page.goto(online_server, wait_until="networkidle")
        assert page.locator("#tableGrid .table-card").count() == 6
        assert page.locator("#wallet").inner_text().endswith("PLAY")
        assert "/ 6" in page.locator("#tableGrid .table-card").first.inner_text()

        page.locator("#quickPlay").click()
        assert page.locator("#buyInUnits").input_value() == "4000"
        page.locator("#confirmReady").click()
        page.wait_for_url("**/table?table=*")
        page.locator("#onlineSurface").wait_for(state="visible")
        page.locator("#onlineConnection").wait_for(state="visible")
        page.wait_for_function("document.querySelector('#onlinePhase')?.textContent === 'ACTIVE'", timeout=20000)
        page.wait_for_function("document.querySelector('#onlineSurface')?.dataset.viewerState === 'seated'", timeout=20000)
        page.wait_for_function("document.querySelectorAll('#onlinePlayers article').length >= 2", timeout=20000)
        assert page.locator("#onlineReady strong").inner_text() in {"Наблюдатель", "В очереди"}
        assert any("•• ••" not in text for text in page.locator("#onlinePlayers b").all_inner_texts())

        observer_context = browser.new_context(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        observer_page = observer_context.new_page()
        observer_page.goto(online_server, wait_until="domcontentloaded")
        observer_page.evaluate("fetch('/api/auth/dev/202', {method: 'POST'})")
        observer_page.goto(page.url, wait_until="domcontentloaded")
        observer_page.wait_for_function("document.querySelector('#onlinePhase')?.textContent === 'ACTIVE'", timeout=10000)
        assert all("•• ••" in text for text in observer_page.locator("#onlinePlayers b").all_inner_texts())
        observer_context.close()

        deadline = time.monotonic() + 20
        while page.locator("#onlinePhase").inner_text() != "RESULT" and time.monotonic() < deadline:
            buttons = page.locator("#onlineActions button").all()
            enabled = [button for button in buttons if button.is_visible() and button.is_enabled()]
            fold = next((button for button in enabled if button.get_attribute("data-action") == "fold"), None)
            if fold is not None:
                fold.evaluate("el => { if (el.disabled) return false; el.click(); return true; }")
            elif enabled:
                enabled[0].evaluate("el => { if (el.disabled) return false; el.click(); return true; }")
            else:
                page.wait_for_timeout(100)
        assert page.locator("#onlinePhase").inner_text() == "RESULT"

        page.locator("#onlineChatInput").fill("hello from e2e")
        page.locator("#onlineChatForm").press("Enter")
        page.get_by_text("hello from e2e").wait_for(state="visible")

        page.evaluate("window.Poker8Transport.disconnect(); window.Poker8Transport.reconnect();")
        page.wait_for_function("document.querySelector('#onlineConnection')?.textContent === 'connected'", timeout=10000)
        page.wait_for_function("document.querySelector('#onlineSurface')?.dataset.viewerState === 'seated'", timeout=10000)

        page.wait_for_timeout(3500)
        assert page.locator("#onlinePhase").inner_text() in {"RESULT", "COUNTDOWN"}
        page.wait_for_function("document.querySelector('#onlinePhase')?.textContent === 'COUNTDOWN'", timeout=5000)
        assert "Новая раздача" in page.locator("#onlineCountdown").inner_text()
        page.wait_for_function("document.querySelector('#onlinePhase')?.textContent === 'ACTIVE'", timeout=5000)

        page.locator("a[href='/static/profile.html']").click()
        page.wait_for_url("**/static/profile.html")
        page.wait_for_function("document.querySelector('#profileName')?.textContent === 'Dev Player'", timeout=10000)
        page.locator("#handHistory .history-row").first.wait_for(state="visible")
        page.locator("#ledger .history-row").first.wait_for(state="visible")
        page.locator("#returnToTable").click()
        page.wait_for_url("**/table?table=*")
        page.locator("#onlineSurface").wait_for(state="visible")

        page.locator("a[href='/static/profile.html']").click()
        page.wait_for_url("**/static/profile.html")
        page.wait_for_function("document.querySelector('#profileName')?.textContent === 'Dev Player'", timeout=10000)
        assert page.locator("#profileName").inner_text() == "Dev Player"
        browser.close()
