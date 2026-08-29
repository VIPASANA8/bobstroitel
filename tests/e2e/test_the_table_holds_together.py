"""The shape of the table, measured in a browser, at the sizes it is used at.

Twenty-eight layers stack their styles onto this page and the last one wins,
so what any of them does is decided by load order and selector length
together -- and neither is written down anywhere. Every bug this file was
built out of had the same shape: a rule meant for one surface reached the
other, and nothing failed until somebody looked at a screenshot.

So this asserts what a screenshot would have shown, at three sizes:

  * nothing overflows the window sideways;
  * the felt is inside its frame, the frame is inside its row, and both are
    centred on the column;
  * the table picture is fitted to the frame rather than to the window --
    100vw is what cut both ends off the table on desktop;
  * every seat, and the cards it holds, land on the felt;
  * watching a table, nobody is drawn in the chair the "Сесть" invitation
    belongs in;
  * the pot cluster is centred;
  * the phone never takes the desktop's scale factor.

It is deliberately blind to colour, spacing and taste. It exists so that
deleting a layer is a thing that can be checked rather than guessed at, and
it should fail loudly the moment one of them is deleted too many.
"""

import pytest
from playwright.sync_api import Page, sync_playwright

pytestmark = pytest.mark.e2e

#: Two desktop sizes and a phone. 1526x921 is the window the desktop bugs
#: were reported from; 1920x1080 is where the scale factor reaches its cap.
VIEWPORTS = [
    ("desktop", 1526, 921),
    ("desktop-large", 1920, 1080),
    ("phone", 390, 844),
]

#: Bot-only rooms the lobby seeds, smallest to largest, so the seat ring is
#: measured at more than one player count.
ROOMS = ("micro-a", "mid-a", "mid-b")

#: A rounded pixel either side of every edge comparison.
SLACK = 2

MEASURE = """() => {
  const box = node => {
    if (!node) return null;
    const r = node.getBoundingClientRect();
    if (!r.width && !r.height) return null;
    return {
      top: r.top, bottom: r.bottom, left: r.left, right: r.right,
      width: r.width, height: r.height, cx: r.left + r.width / 2,
      cy: r.top + r.height / 2,
    };
  };
  const felt = document.querySelector('.felt');
  const frame = document.querySelector('.table-frame');
  if (!felt || !frame || !box(felt) || !box(frame)) return null;
  const style = getComputedStyle(frame);
  const seats = [...document.querySelectorAll('.seat.v040-dynamic-seat')].map(seat => {
    const cards = [...seat.querySelectorAll('.player-cards .card')].map(box).filter(Boolean);
    return {
      slot: seat.classList.contains('v040-sit-slot'),
      visual: seat.dataset.visualSeat || null,
      y: parseFloat(seat.style.getPropertyValue('--v040-seat-y')) || null,
      box: box(seat),
      cardTop: cards.length ? Math.min(...cards.map(c => c.top)) : null,
      cardBottom: cards.length ? Math.max(...cards.map(c => c.bottom)) : null,
    };
  }).filter(seat => seat.box);
  return {
    viewport: {width: innerWidth, height: innerHeight},
    scrollWidth: document.documentElement.scrollWidth,
    watching: document.body.classList.contains('p8-spectator-layout'),
    uiScale: parseFloat(getComputedStyle(document.body).getPropertyValue('--p8-ui-scale')) || 1,
    frameBackgroundSize: style.backgroundSize,
    layout: box(document.querySelector('.layout')),
    column: box(document.querySelector('.left-column')),
    frame: box(frame),
    felt: box(felt),
    centre: box(document.querySelector('.table-center')),
    pot: box(document.querySelector('.pot-total')),
    sidebar: box(document.querySelector('.sidebar')),
    panel: box(document.querySelector('.action-panel')),
    seats,
  };
}"""


def _open(browser, server, table, width, height):
    context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
    context.request.post(f"{server}/api/auth/dev/202")
    page: Page = context.new_page()
    # Six bot-only rooms dealing into one sqlite process; the default 30s is
    # not always enough for the third room to answer.
    page.set_default_timeout(60000)
    page.goto(f"{server}/table?table={table}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function("document.body.classList.contains('p8-boot-ready')")
    return context, page


def _inside(inner, outer, name, where, slack=SLACK):
    assert inner["left"] >= outer["left"] - slack, f"{where}: {name} runs {outer['left'] - inner['left']:.0f}px past the left edge"
    assert inner["right"] <= outer["right"] + slack, f"{where}: {name} runs {inner['right'] - outer['right']:.0f}px past the right edge"
    assert inner["top"] >= outer["top"] - slack, f"{where}: {name} starts {outer['top'] - inner['top']:.0f}px above the top edge"
    assert inner["bottom"] <= outer["bottom"] + slack, f"{where}: {name} ends {inner['bottom'] - outer['bottom']:.0f}px below the bottom edge"


@pytest.mark.parametrize("name,width,height", VIEWPORTS)
@pytest.mark.parametrize("table", ROOMS)
def test_the_table_holds_its_shape(spectator_server, table, name, width, height):
    where = f"{table} at {name} {width}x{height}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context, page = _open(browser, spectator_server, table, width, height)
            try:
                measured = page.wait_for_function(MEASURE).json_value()
                assert measured, where

                # Nothing hangs off the side of the window. Every layout fault
                # this file was built from showed up here first.
                assert measured["scrollWidth"] <= measured["viewport"]["width"] + SLACK, (
                    f"{where}: the page is {measured['scrollWidth'] - measured['viewport']['width']:.0f}px "
                    "wider than the window")

                felt, frame = measured["felt"], measured["frame"]
                _inside(felt, frame, "the felt", where)
                if measured["column"]:
                    _inside(frame, measured["column"], "the table frame", where)
                if measured["layout"]:
                    assert abs(frame["cx"] - measured["layout"]["cx"]) <= SLACK, (
                        f"{where}: the table sits {frame['cx'] - measured['layout']['cx']:.0f}px off the column's centre")

                # The picture is of this table, so it is sized to this table.
                # Sized to the window instead -- "100vw", which is right on a
                # phone and wrong on a desktop, where the frame is narrower --
                # the frame clips both ends of the table off.
                #
                # Read as painted width, not as written: the computed value
                # has already resolved vw to pixels, so the units it was
                # authored in cannot be seen from here. A percentage is by
                # definition the frame's own; a length has to match it.
                for layer in measured["frameBackgroundSize"].split(","):
                    painted = layer.strip().split()[0]
                    if painted.endswith("px"):
                        assert abs(float(painted[:-2]) - frame["width"]) <= SLACK, (
                            f"{where}: the table picture is painted {painted} wide in a "
                            f"{frame['width']:.0f}px frame, so the frame clips it")

                # Seats, and the cards they hold, belong on the felt.
                for seat in measured["seats"]:
                    label = "the empty chair" if seat["slot"] else f"seat {seat['visual']}"
                    _inside(seat["box"], felt, label, where, slack=SLACK + 1)
                    if seat["cardTop"] is not None:
                        assert seat["cardTop"] >= felt["top"] - SLACK, (
                            f"{where}: {label}'s cards start {felt['top'] - seat['cardTop']:.0f}px above the felt")
                        assert seat["cardBottom"] <= felt["bottom"] + SLACK, (
                            f"{where}: {label}'s cards end {seat['cardBottom'] - felt['bottom']:.0f}px below the felt")

                # Watching, the near chair is the invitation's, and a player
                # drawn into it is the layout thinking somebody else is you.
                slots = [seat for seat in measured["seats"] if seat["slot"]]
                players = [seat for seat in measured["seats"] if not seat["slot"]]

                # This session never sits down, so the page is watching -- and
                # has to say so. Stated before the chair check below rather
                # than as a condition of it: when the layout decides somebody
                # else is you, both of that check's own preconditions vanish
                # (no watching class, no invitation) and it would pass by
                # having nothing to look at.
                assert measured["watching"], (
                    f"{where}: the page is in the seated layout for a viewer who holds no seat")
                if len(players) < 6:
                    assert slots, f"{where}: watching a table with a free seat, and no invitation to take it"

                if slots and players:
                    # Not "far from" -- the phone's ring is tight enough that
                    # five points between two chairs is normal there. The
                    # fault this catches is a player standing exactly where
                    # the invitation stands, which is what the layout does
                    # when it has decided somebody else is you.
                    for slot in slots:
                        for seat in players:
                            same_place = (
                                slot["box"] is not None and seat["box"] is not None
                                and abs(slot["box"]["cx"] - seat["box"]["cx"]) <= 4
                                and abs(slot["box"]["cy"] - seat["box"]["cy"]) <= 4
                            )
                            assert not same_place, (
                                f"{where}: seat {seat['visual']} is drawn in the chair the "
                                "invitation holds")

                if measured["centre"]:
                    assert abs(measured["centre"]["cx"] - felt["cx"]) <= SLACK, (
                        f"{where}: the centre cluster is {measured['centre']['cx'] - felt['cx']:.0f}px off centre")
                    _inside(measured["centre"], felt, "the centre cluster", where)

                # The action bar, when there is one, is centred under the table.
                if measured["panel"] and measured["layout"]:
                    assert abs(measured["panel"]["cx"] - measured["layout"]["cx"]) <= SLACK, (
                        f"{where}: the action panel is "
                        f"{measured['panel']['cx'] - measured['layout']['cx']:.0f}px off the column's centre")

                # The scale factor is desktop's alone, and never shrinks
                # anything below the size it was drawn at.
                assert measured["uiScale"] >= 1, f"{where}: scale {measured['uiScale']}"
                if name == "phone":
                    assert measured["uiScale"] == 1, (
                        f"{where}: the phone took the desktop's scale factor ({measured['uiScale']})")
            finally:
                context.close()
        finally:
            browser.close()
