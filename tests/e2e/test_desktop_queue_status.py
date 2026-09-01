"""The pending-seat state belongs in the header controls, not on a player."""

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.e2e


def test_queue_status_stays_in_the_header_at_every_width(online_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1485, "height": 831})
            page.request.post(f"{online_server}/api/auth/dev/202")
            payload = page.request.get(f"{online_server}/api/tables/mid-b").json()
            payload.update(viewer_state="waiting", queue_state="waiting")
            page.route("**/api/tables/mid-b", lambda route: route.fulfill(json=payload))
            page.goto(f"{online_server}/table?table=mid-b", wait_until="domcontentloaded")
            panel = page.locator("#readyPanel")
            actions = page.locator("#mobileHeaderSeatActions")
            take = page.locator("#mobileHeaderTakeSeat")
            observe = page.locator("#mobileHeaderObserve")
            page.wait_for_function("!!document.getElementById('v040-poker8-v2-dynamic-seats-style') && document.body.classList.contains('p8-boot-ready')")
            page.wait_for_function("document.querySelector('#readyPanel').classList.contains('is-pending')")
            for width in (1485, 1192, 781):
                page.set_viewport_size({"width": width, "height": 831})
                page.wait_for_timeout(150)
                assert panel.is_hidden()
                assert actions.is_visible()
                assert actions.locator("..").get_attribute("class") == "topbar"
                assert page.locator("#readyPanel").count() == 1
                assert take.is_disabled()
                assert take.inner_text() == "В очереди"
                assert observe.inner_text() == "Отменить"
                box = actions.bounding_box()
                header = page.locator(".topbar").bounding_box()
                brand = page.locator(".brand-wrap").bounding_box()
                utilities = page.locator(".top-actions").bounding_box()
                assert box and header and brand and utilities
                assert box["x"] >= brand["x"] + brand["width"] - 1
                assert box["x"] + box["width"] <= utilities["x"] + 1
                assert box["y"] >= header["y"] - 1
                assert box["y"] + box["height"] <= header["y"] + header["height"] + 1
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(150)
            # The same nodes move into the mobile header; there is no second
            # queue control to drift or duplicate the state.
            assert panel.is_hidden()
            assert panel.locator("..").get_attribute("class") == "felt"
            assert actions.is_visible()
            assert actions.locator("..").get_attribute("id") == "mobileGameHeader"
            assert take.is_disabled()
            assert observe.inner_text() == "Отменить"
        finally:
            browser.close()
