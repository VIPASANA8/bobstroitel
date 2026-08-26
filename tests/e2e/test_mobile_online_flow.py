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
        page.locator(".table-frame").wait_for(state="visible")
        page.locator("#mobileConnectionDot").wait_for(state="visible")
        page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'РАЗДАЧА'", timeout=20000)
        page.wait_for_function("document.body.classList.contains('local-player-active')", timeout=20000)
        page.wait_for_function("document.querySelectorAll('.seat .seat-card').length >= 3", timeout=20000)
        assert page.locator(".viewer-seat .player-cards .card:not(.back)").count() == 2
        assert page.locator("#readyPanel").is_hidden()

        observer_context = browser.new_context(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        observer_page = observer_context.new_page()
        observer_context.request.post(f"{online_server}/api/auth/dev/202")
        observer_page.goto(page.url, wait_until="domcontentloaded")
        observer_page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'РАЗДАЧА'", timeout=10000)
        observer_page.wait_for_function("document.body.classList.contains('spectator-mode')", timeout=10000)
        assert observer_page.locator(".seat-card .player-cards .card:not(.back)").count() == 0
        assert observer_page.locator(".seat-card .player-cards .card.back").count() >= 4
        observer_context.close()

        deadline = time.monotonic() + 20
        while page.locator("#mobileStreetLabel").inner_text() != "ВСКРЫТИЕ" and time.monotonic() < deadline:
            buttons = page.locator("#actionButtons button").all()
            enabled = [button for button in buttons if button.is_visible() and button.is_enabled()]
            fold = next((button for button in enabled if button.get_attribute("data-action-key") == "fold"), None)
            if fold is not None:
                fold.evaluate("el => { if (el.disabled) return false; el.click(); return true; }")
            else:
                passive = next((button for button in enabled if button.get_attribute("data-action-key") in {"check", "call"}), None)
                if passive is not None:
                    passive.evaluate("el => { if (el.disabled) return false; el.click(); return true; }")
                else:
                    page.wait_for_timeout(100)
        assert page.locator("#mobileStreetLabel").inner_text() == "ВСКРЫТИЕ"

        page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'COUNTDOWN'", timeout=5000)
        assert "Новая раздача" in page.locator("#newHandCountdown").inner_text()
        page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'РАЗДАЧА'", timeout=5000)

        page.locator("#mobileChatButton").click()
        page.locator("#chatInput").fill("hello from e2e")
        page.locator("#chatInput").press("Enter")
        page.get_by_text("hello from e2e").wait_for(state="visible")

        page.evaluate("window.Poker8Transport.disconnect(); window.Poker8Transport.reconnect();")
        page.wait_for_function("document.querySelector('#connectionStatus')?.textContent === 'connected'", timeout=10000)
        page.wait_for_function("document.body.classList.contains('local-player-active')", timeout=10000)

        page.goto(f"{online_server}/static/profile.html", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#profileName')?.textContent === 'Dev Player'", timeout=10000)
        page.locator("#handHistory .history-row").first.wait_for(state="visible")
        page.locator("#ledger .history-row").first.wait_for(state="visible")
        page.locator("#returnToTable").click()
        page.wait_for_url("**/table?table=*")
        page.locator(".table-frame").wait_for(state="visible")

        page.goto(f"{online_server}/static/profile.html", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#profileName')?.textContent === 'Dev Player'", timeout=10000)
        assert page.locator("#profileName").inner_text() == "Dev Player"
        browser.close()
