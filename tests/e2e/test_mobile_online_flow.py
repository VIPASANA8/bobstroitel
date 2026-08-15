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

        page.locator("#quickPlay").click()
        page.locator("#confirmReady").click()
        page.wait_for_url("**/table?table=*")
        page.locator("#onlineSurface").wait_for(state="visible")
        page.locator("#onlineConnection").wait_for(state="visible")
        page.wait_for_timeout(1000)
        assert page.locator("#onlinePhase").inner_text() in {"WAITING", "ACTIVE", "RESULT", "COUNTDOWN"}
        assert page.locator("#onlineMessages").count() == 1

        page.locator("a[href='/static/profile.html']").click()
        page.wait_for_url("**/static/profile.html")
        page.locator("#profileName").wait_for(state="visible")
        assert page.locator("#profileName").inner_text() == "Dev Player"
        browser.close()
