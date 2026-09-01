"""Taking a seat while a hand is running, and being told it worked.

The queue has always accepted a mid-hand claim and seated the player at the
next boundary. What was missing was on the felt: the chair carried on
reading "Сесть" as though nothing had been pressed, so the only sign was a
line in the header.
"""

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

pytestmark = pytest.mark.e2e

#: Read out of the layer rather than repeated here, so the word on the felt
#: and the word this test expects cannot drift apart.
HELD_LABEL = re.search(
    r'v040-sit-slot .seat-empty strong::after\{\s*content:"([^"]+)"',
    Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8"),
).group(1)

CHAIR = """() => {
  const seat = document.querySelector('.seat.v040-sit-slot');
  if (!seat) return null;
  const ring = seat.querySelector('.empty-avatar');
  const label = seat.querySelector('strong');
  const heroSize = parseFloat(getComputedStyle(seat).getPropertyValue('--p8-hero-avatar-size'));
  const box = node => {
    if (!node) return null;
    const r = node.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height)};
  };
  return {
    ring: box(ring),
    hero: {w: Math.round(heroSize), h: Math.round(heroSize)},
    borderStyle: ring && getComputedStyle(ring).borderStyle,
    label: label && (getComputedStyle(label, '::after').content || '').replace(/"/g, '') || label?.textContent,
    clickable: getComputedStyle(seat.querySelector('.seat-empty')).pointerEvents,
  };
}"""


#: 202 is the observer the board-clearance test watches with. Claiming a
#: seat here would seat it for the rest of the session -- the server is
#: session-scoped and shared -- and that test would then be looking at a
#: seated layout. This one plays the other profile and gives the seat back.
CLAIMANT = 101


def test_a_seat_claimed_during_a_hand_is_held_and_says_so(spectator_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 390, "height": 765}, device_scale_factor=1)
            context.request.post(f"{spectator_server}/api/auth/dev/{CLAIMANT}")
            page: Page = context.new_page()
            page.set_default_timeout(60000)
            page.goto(f"{spectator_server}/table?table=low-b", wait_until="domcontentloaded", timeout=60000)

            page.wait_for_function("document.body.classList.contains('p8-spectator-layout')")
            page.wait_for_function("!!document.querySelector('.seat.v040-sit-slot [data-add-seat]')")
            # A board on the felt is a hand in progress, which is the case
            # the queue exists for.
            page.wait_for_function("document.querySelectorAll('.board-cards .card').length > 0")

            offered = page.evaluate(CHAIR)
            assert offered["ring"] == offered["hero"], "the empty chair is not the size of the hero avatar"
            assert offered["borderStyle"] == "dashed", offered
            assert offered["clickable"] != "none"

            # The seat opens the same buy-in dialog the header's "Занять
            # место" does -- sitting from the felt used to skip it and buy in
            # for a flat 40, so the same chair cost a different stack
            # depending on which control was pressed.
            page.locator(".seat.v040-sit-slot [data-add-seat]").click()
            dialog = page.locator("[data-confirm]")
            dialog.wait_for(state="visible")
            dialog.click()
            page.wait_for_function("document.body.classList.contains('p8-seat-reserved')")

            held = page.evaluate(CHAIR)
            assert held["ring"] == held["hero"], "the held chair changed size"
            assert held["borderStyle"] == "solid", held
            assert held["label"] == HELD_LABEL, held
            assert held["clickable"] != "none", "the held chair is also the cancel control"

            page.locator(".seat.v040-sit-slot [data-add-seat]").click()
            page.wait_for_function("!document.body.classList.contains('p8-seat-reserved')")

            # Hand the seat back, so a rerun starts from the same table this
            # one found: cancel while still queued, leave once seated.
            context.request.post(f"{spectator_server}/api/tables/low-b/leave")
            context.close()
        finally:
            browser.close()
