"""What a spectator can actually see of the street, measured in a browser.

The lower side seats used to sit at y:64-66. Their hole-card boxes ran into
the community-card row -- 33px of vertical overlap on a 765px viewport, 54px
at 640 -- so from the side a player covered the board. They share one y:75
band now, and this pins that at the viewport heights the overlap was
measured across.

The pot is checked in the same pass because it lives in the same strip: one
centred cluster sitting four pixels above the amount plate, rather than two
piles held apart by a fixed-width row.
"""

import pytest
from playwright.sync_api import Page, sync_playwright

pytestmark = pytest.mark.e2e

#: The heights the overlap was measured across, smallest phone to tallest.
VIEWPORT_HEIGHTS = (640, 720, 765, 874)

#: Room -> how many bots it seats, i.e. the spectator layout under test.
ROOMS = {"low-b": 4, "mid-a": 5, "mid-b": 6}

#: The gap v038's syncPotChipStack holds between chips and the pot plate.
POT_CHIP_GAP = 4

#: Room for a rounded pixel on each side of the measured gap.
TOLERANCE = 1

#: Clone the last board card until five are on the felt. A bot-only table
#: reaches the river on its own schedule, and waiting for it would make a
#: geometry check hostage to how the hand happens to play; the clones carry
#: the real card box, which is the only part being measured.
FIVE_CARD_BOARD = """() => {
  const board = document.querySelector('.board-cards');
  if (!board) return 0;
  const card = board.querySelector('.card');
  if (!card) return 0;
  while (board.querySelectorAll('.card').length < 5) {
    board.appendChild(card.cloneNode(true));
  }
  window.syncComponentUi?.(window.game, window.tableData);
  return board.querySelectorAll('.card').length;
}"""

MEASURE = """() => {
  const box = node => {
    if (!node) return null;
    const r = node.getBoundingClientRect();
    return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, cx: r.left + r.width / 2};
  };
  const seats = [...document.querySelectorAll('.seat.v040-dynamic-seat')]
    .filter(seat => !seat.classList.contains('v040-sit-slot'))
    .map(seat => ({
      y: parseFloat(seat.style.getPropertyValue('--v040-seat-y')) || 0,
      // The cards overhang the box upward, so they are the topmost thing a
      // seat puts on the felt and the part that reached the board first.
      top: Math.min(box(seat).top, box(seat.querySelector('.player-cards'))?.top ?? Infinity),
    }));
  return {
    felt: box(document.querySelector('.felt')),
    board: box(document.querySelector('.board-cards')),
    chips: box(document.querySelector('#potChips')),
    pot: box(document.querySelector('.pot-total')),
    seats,
  };
}"""


def _open_as_spectator(browser, server, table, height):
    context = browser.new_context(viewport={"width": 390, "height": height}, device_scale_factor=1)
    context.request.post(f"{server}/api/auth/dev/202")
    page: Page = context.new_page()
    # Six bot-only rooms all dealing into one sqlite process; the default 30s
    # is not always enough for the third room to answer.
    page.set_default_timeout(60000)
    page.goto(f"{server}/table?table={table}", wait_until="domcontentloaded", timeout=60000)
    return context, page


@pytest.mark.parametrize("height", VIEWPORT_HEIGHTS)
def test_the_spectator_strip_is_readable_at_every_phone_height(spectator_server, height):
    """Both halves of the same strip, measured on one render: the lower side
    seats must start below the board, and the pot must be a single cluster
    centred on the felt four pixels above the amount plate."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for table, players in ROOMS.items():
                context, page = _open_as_spectator(browser, spectator_server, table, height)
                try:
                    page.wait_for_function(
                        f"document.body.classList.contains('p8-player-count-{players}')")
                    page.wait_for_function("document.body.classList.contains('p8-spectator-layout')")
                    # A board on the felt means a hand is running, which is
                    # also what puts money in the pot for the chips below.
                    page.wait_for_function("document.querySelectorAll('.board-cards .card').length > 0")
                    page.wait_for_function(
                        "document.querySelector('#potChips')?.classList.contains('has-chips')")
                    assert page.evaluate(FIVE_CARD_BOARD) == 5, (table, height)

                    measured = page.evaluate(MEASURE)
                    board, chips, pot, felt = (
                        measured["board"], measured["chips"], measured["pot"], measured["felt"])

                    lower = [seat for seat in measured["seats"] if seat["y"] > 56]
                    assert lower, (table, height, measured["seats"])
                    for seat in lower:
                        assert seat["top"] >= board["bottom"], (
                            f"{table} at {height}px: a lower seat starts "
                            f"{board['bottom'] - seat['top']:.0f}px above the board's bottom edge")

                    assert page.locator("#potChips .chip-cluster").count() == 1, (table, height)
                    assert abs(chips["cx"] - felt["cx"]) <= TOLERANCE, (
                        f"{table} at {height}px: chips off-centre by {chips['cx'] - felt['cx']:.1f}px")
                    gap = pot["top"] - chips["bottom"]
                    assert gap >= POT_CHIP_GAP - TOLERANCE, (
                        f"{table} at {height}px: chips sit only {gap:.1f}px above the pot")
                    assert gap <= POT_CHIP_GAP + TOLERANCE, (
                        f"{table} at {height}px: chips drift {gap:.1f}px above the pot")
                finally:
                    context.close()
        finally:
            browser.close()
