import re
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
        # The balance is a number now -- PLAY is the only currency there is,
        # so naming it in the header said nothing. The profile chip took its place.
        assert re.fullmatch(r"[\d\s.,]+", page.locator("#wallet").inner_text())
        assert page.locator(".profile-chip").is_visible()
        assert page.locator("#tableGrid .table-card .seats").first.get_attribute("aria-label").endswith("из 6 мест")

        page.locator("#quickPlay").click()
        page.locator("#buyInDialog").wait_for(state="visible")
        assert page.locator("#buyInUnits").input_value() == "4000"
        page.locator("#confirmReady").click()
        page.wait_for_url("**/table?table=*")
        page.locator(".table-frame").wait_for(state="visible")
        page.locator("#mobileConnectionDot").wait_for(state="visible")
        page.wait_for_function("document.body.classList.contains('p8-can-ready')", timeout=20000)
        page.locator('.seat[data-visual-seat="0"] .avatar-wrap').click()
        page.wait_for_function("document.body.classList.contains('local-player-active')", timeout=30000)
        page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'РАЗДАЧА'", timeout=20000)
        # The deterministic fixture activates two bots globally, not two bots
        # at every table. micro-a currently has one bot, so this hand is the
        # viewer plus that bot.
        page.wait_for_function("document.querySelectorAll('.seat .seat-card').length >= 2", timeout=20000)
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

        page.locator("#mobileChatButton").click()
        page.locator("#chatInput").fill("hello from e2e")
        page.locator("#chatInput").press("Enter")
        page.get_by_text("hello from e2e").wait_for(state="visible")
        page.locator("#mobileChatButton").click()
        page.locator("#chatPanel").wait_for(state="hidden")

        page.evaluate("window.Poker8Transport.disconnect(); window.Poker8Transport.reconnect();")
        page.wait_for_function("document.querySelector('#connectionStatus')?.textContent === 'connected'", timeout=10000)
        page.wait_for_function("document.body.classList.contains('local-player-active')", timeout=10000)

        deadline = time.monotonic() + 20
        while page.locator("#mobileStreetLabel").inner_text() != "ВСКРЫТИЕ" and time.monotonic() < deadline:
            acted = page.evaluate("""() => {
                const enabled = [...document.querySelectorAll('#actionButtons button')]
                    .filter(button => !button.disabled && button.getClientRects().length);
                const target = enabled.find(button => button.dataset.actionKey === 'fold')
                    || enabled.find(button => ['check', 'call'].includes(button.dataset.actionKey));
                if (!target) return false;
                target.click();
                return true;
            }""")
            if not acted:
                page.wait_for_timeout(100)
        assert page.locator("#mobileStreetLabel").inner_text() == "ВСКРЫТИЕ"

        page.wait_for_function("document.body.classList.contains('p8-can-ready')", timeout=12000)
        page.locator('.seat[data-visual-seat="0"] .avatar-wrap').click()
        page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'ПЕРЕРЫВ'", timeout=15000)
        # The "next hand in N sec" line is gone -- the ring on the hero's own
        # avatar counts the same seconds, on the seat it belongs to.
        assert page.locator("#newHandCountdown").count() == 0
        page.wait_for_function("document.querySelector('#mobileStreetLabel')?.textContent === 'РАЗДАЧА'", timeout=15000)

        page.goto(f"{online_server}/static/profile.html", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#profileName')?.textContent === 'Dev Player'", timeout=10000)
        page.locator("#handHistory .history-row").first.wait_for(state="visible")
        page.get_by_role("tab", name="Операции").click()
        page.locator("#ledger .history-row").first.wait_for(state="visible")
        page.locator("#returnToTable").click()
        page.wait_for_url("**/table?table=*")
        page.locator(".table-frame").wait_for(state="visible")

        page.goto(f"{online_server}/static/profile.html", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#profileName')?.textContent === 'Dev Player'", timeout=10000)
        assert page.locator("#profileName").inner_text() == "Dev Player"
        browser.close()
