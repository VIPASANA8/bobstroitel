(() => {
  "use strict";

  const MOBILE_QUERY = "(max-width: 780px)";
  const DESKTOP_QUERY = "(min-width: 781px)";
  const isMobile = () => window.matchMedia?.(MOBILE_QUERY)?.matches ?? false;
  const isDesktop = () => window.matchMedia?.(DESKTOP_QUERY)?.matches ?? false;

  // Pot/board/chips sit in a fixed proportional band regardless of felt
  // height (they're positioned in %, top:25/38/47 -- see v038/v019): roughly
  // y 22%-56%, x 14%-86%. Every seat point below keeps its centre outside
  // that band with margin for the seat's own half-height, or the seat visibly
  // sits on top of the pot/board/cards.
  const LAYOUTS = {
    1: [[50, 80]],
    2: [[50, 80], [50, 15]],
    3: [[50, 80], [18, 14], [82, 14]],
    4: [[50, 80], [14, 66], [50, 13], [86, 66]],
    5: [[50, 80], [12, 63], [24, 14], [76, 14], [88, 63]],
    6: [[50, 80], [12, 61], [12, 19], [50, 13], [88, 19], [88, 61]],
  };

  // В режиме наблюдения у стола нет закреплённого нижнего места.
  // Поэтому два активных игрока выводятся слева и справа, а не друг напротив друга.
  // The upper-side points in the 5 and 6 entries used to sit at y:38 and
  // y:31 -- squarely inside the pot/board band the comment above warns
  // about, unlike every other entry here. Measured live: the board's actual
  // card rects overlapped the seat-identity plate by up to 54px, and the
  // plate painted over the card (it has the higher z-index), so part of a
  // community card was hidden behind a player's name. Moved to y:20, next to
  // the top pole the same way LAYOUTS[6]'s own upper-side seats sit near its
  // top pole (13 and 19) -- clear of the band, not just barely.
  //: The seat at 50%/80% is the hero's, and while nobody is sitting there it
  //: is where the "take a seat" control goes -- so no spectator layout may
  //: use the bottom-centre unless the room is full and there is no seat to
  //: offer. That is why 4 and 5 spread across the top and the sides instead
  //: of putting somebody where the invitation belongs, and why 1 sits at the
  //: top rather than in the chair being offered.
  const SPECTATOR_LAYOUTS = {
    1: [[50, 13]],
    2: [[12, 50], [88, 50]],
    3: [[50, 13], [18, 70], [82, 70]],
    4: [[24, 14], [76, 14], [83, 66], [17, 66]],
    // Was three seats crammed onto the same y:14-16 top band and only two
    // down at y:78, leaving the whole middle band empty on both sides --
    // lopsided, not a pentagon. Reuses the 4-seat entry's own proven y bands
    // (13, 66, 88) plus the top pair's x spread from LAYOUTS[5] (24/76)
    // instead of inventing new numbers: two top, two mid-sides, one bottom.
    5: [[50, 9], [20, 14], [80, 14], [85, 66], [15, 66]],
    // Same lopsidedness the 5-seat entry had, one row flatter: the two
    // lower-side seats sat at y:69, only 16 points off the bottom pole's
    // 85 -- reported live as two dense rows, top and bottom, with no
    // hexagon bulge. The upper pair stays at y:14 (the pot-label collision
    // fix two comments up is specific to that y, not renegotiable here);
    // the lower pair moves to y:61 -- LAYOUTS[6]'s own proven lower-wing
    // value -- which clears the bottom pole by the same margin the upper
    // wings already clear the top pole by.
    //
    // That margin didn't actually exist yet: the top pole sat at y:15, one
    // point off the wings' 14 -- reported live as the top-left/top-right
    // seats reading at the same height as the top-center one, no bulge at
    // all up there either. The pot-collision ceiling only bounds the wings
    // from going lower (closer to the pot); moving the pole *up* moves it
    // further from the pot, not closer, so it isn't bound by that fix --
    // y:9 is the same clearance from y:14 the bottom pole (y:85) already
    // gets from its own wings (y:61).
    // The lower pair moved again, 61 -> 64. Measured on a 321x760 phone
    // felt: the board occupies y 47-58%, and a seat centred at 61% spans
    // 56-66%, so both lower-side seats sat on top of the community cards
    // ("не перекрывать улицу"). 64% starts the box at 63%, clear of the
    // board's 58% bottom, and still leaves the 20-point gap to the bottom
    // pole that keeps this a hexagon rather than two rows.
    6: [[50, 9], [83, 14], [83, 64], [50, 85], [17, 64], [17, 14]],
  };

  const style = document.createElement("style");
  style.id = "v040-poker8-v2-dynamic-seats-style";
  style.textContent = `
    /* Was @media (max-width:780px). The v2 table is the table now, at every
       width; desktop geometry is tuned in v039. */
    @media all{
      body.v014.poker8-v2-sixmax .seat.v040-empty-seat{display:none!important;}
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat{
        left:var(--v040-seat-x)!important;top:var(--v040-seat-y)!important;
        transform:translate(calc(-50% + var(--v040-flip-x, 0px)),calc(-50% + var(--v040-flip-y, 0px)))!important;
        /* No will-change here. It promoted every seat to its own raster layer,
           which was then resampled through the felt's transform -- paying a
           layer per seat to make the text softer. */
        /* Only the position needs to visibly flip. A live table re-renders
           this element from scratch on every snapshot, which restarts any
           transition on it before it can finish -- animating width/height
           here left the seat box stuck near its pre-transition size
           indefinitely. Dropping them makes the size exact on every paint,
           independent of how often re-renders arrive. */
        transition:transform 460ms cubic-bezier(.22,.8,.24,1)!important;
      }
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-card,
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .avatar-wrap,
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-identity{
        transition:transform 460ms cubic-bezier(.22,.8,.24,1),opacity 220ms ease!important;
      }
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat,
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-card,
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .avatar-wrap,
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-identity{transition:none!important;}
      }
      /* Boxes shrunk ~0.66x to match the item-6 avatar resize (74px -> 49px). */
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat{width:79px!important;height:83px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-3 .seat.v040-dynamic-seat{width:71px!important;height:79px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-4 .seat.v040-dynamic-seat,
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat.v040-dynamic-seat,
      /* count-6 was never listed, so a full table fell through to the base
         .seat box -- 90x104, larger than the five-player one right above it
         and the reason six seats crowd the felt on a phone. */
      body.v014.poker8-v2-sixmax.p8-player-count-6 .seat.v040-dynamic-seat{width:67px!important;height:77px!important;}
      /* The hero seat used to be pinned at a fixed 87x87 regardless of player
         count -- now it takes the same per-count size as every other seat. */
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] .avatar-wrap{top:7px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] .seat-identity{top:50px!important;}
    }
    @media (min-width:781px){
      body.v014.poker8-desktop-v2 .seat.v040-empty-seat{display:none!important;}
      /* A percentage alone cannot keep the top row on the felt. The seat box
         is a fixed 148px here, so its centre needs at least half of that plus
         the ~20px the hole cards overhang above it; the tallest box here is 154px
         (two players), so the floor is 100px. The top pole sits
         at 9% of the felt, which is only 70px on a 780px felt and 74px on the
         shorter seated one, so the box already started 4px above the felt and
         the cards were clipped away entirely (reported live: "карты
         улетают"). The floor is in pixels because the shortfall is in pixels:
         it binds on a short felt and does nothing on a tall one, so the
         hexagon keeps its spread wherever there is room for it. */
      body.v014.poker8-desktop-v2 .seat.v040-dynamic-seat{
        left:var(--v040-seat-x)!important;top:max(var(--v040-seat-y),100px)!important;
        transform:translate(calc(-50% + var(--v040-flip-x, 0px)),calc(-50% + var(--v040-flip-y, 0px)))!important;
        transition:transform 320ms cubic-bezier(.22,.8,.24,1)!important;
        will-change:transform;
      }
      body.v014.poker8-desktop-v2.p8-player-count-2 .seat.v040-dynamic-seat{width:146px!important;height:154px!important;}
      body.v014.poker8-desktop-v2.p8-player-count-3 .seat.v040-dynamic-seat{width:140px!important;height:152px!important;}
      body.v014.poker8-desktop-v2.p8-player-count-4 .seat.v040-dynamic-seat,
      body.v014.poker8-desktop-v2.p8-player-count-5 .seat.v040-dynamic-seat,
      body.v014.poker8-desktop-v2.p8-player-count-6 .seat.v040-dynamic-seat{width:134px!important;height:148px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"]{width:144px!important;height:150px!important;z-index:28!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-cards{top:-30px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-cards .card{width:40px!important;height:56px!important;}
    }
  `;
  document.head.appendChild(style);

  function playerForSeat(gameState, seat) {
    const physical = Number(seat.dataset.seat);
    const fromGame = Object.values(gameState?.players || {}).find(player => Number(player?.seat) === physical) || null;
    if (fromGame) return fromGame;
    // A seat can be occupied without being in gameState.players -- e.g.
    // someone seated while a hand they aren't dealt into is running (see
    // current_seats on the server, and the same fallback in app.js's
    // seatHtml/renderSeats). The seat-card app.js already rendered for them
    // is the only signal of that here; .viewer-seat is the same fallback's
    // own "is this you" marker, reused instead of re-deriving it a third time.
    const card = seat.querySelector(".seat-card");
    if (!card) return null;
    return { seat: physical, id: null, isViewerCard: card.classList.contains("viewer-seat") };
  }

  function orderedActiveSeats(gameState, tableState) {
    const seats = [...document.querySelectorAll(".seat[data-seat]")];
    const active = seats.filter(seat => playerForSeat(gameState, seat));
    if (!active.length) return { active, viewer: null };

    const viewerId = gameState?.viewer_player_id;
    let viewer = active.find(seat => {
      const player = playerForSeat(gameState, seat);
      return player?.id === viewerId || player?.isViewerCard;
    }) || null;
    if (!viewer) {
      const currentProfile = gameState?.active_profile_id || tableState?.active_profile_id;
      viewer = active.find(seat => {
        const player = playerForSeat(gameState, seat);
        return Boolean(player?.profile_id && (!currentProfile || player.profile_id === currentProfile));
      }) || null;
    }

    const anchor = viewer ? Number(viewer.dataset.seat) : Number(active[0].dataset.seat);
    const clockwise = [...active].sort((a, b) => {
      const distance = seat => ((Number(seat.dataset.seat) - anchor) % 6 + 6) % 6;
      return distance(a) - distance(b);
    });
    if (viewer) return { active: [viewer, ...clockwise.filter(seat => seat !== viewer)], viewer };
    return { active: clockwise, viewer: null };
  }

  function moveSeatTo(seat, x, y) {
    const nextX = `${x}%`;
    const nextY = `${y}%`;
    if (seat.style.getPropertyValue("--v040-seat-x") === nextX
      && seat.style.getPropertyValue("--v040-seat-y") === nextY) return;

    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    if (reduceMotion || typeof seat.getBoundingClientRect !== "function") {
      seat.style.setProperty("--v040-seat-x", nextX);
      seat.style.setProperty("--v040-seat-y", nextY);
      seat.style.setProperty("--v040-flip-x", "0px");
      seat.style.setProperty("--v040-flip-y", "0px");
      return;
    }

    const before = seat.getBoundingClientRect();
    seat.style.setProperty("--v040-seat-x", nextX);
    seat.style.setProperty("--v040-seat-y", nextY);
    const after = seat.getBoundingClientRect();
    const deltaX = Math.round(before.left - after.left);
    const deltaY = Math.round(before.top - after.top);
    if (!deltaX && !deltaY) return;

    const token = (Number(seat.dataset.v040MotionToken || "0") + 1);
    seat.dataset.v040MotionToken = String(token);
    seat.style.setProperty("--v040-flip-x", `${deltaX}px`);
    seat.style.setProperty("--v040-flip-y", `${deltaY}px`);
    const settle = () => {
      if (seat.dataset.v040MotionToken !== String(token)) return;
      seat.style.setProperty("--v040-flip-x", "0px");
      seat.style.setProperty("--v040-flip-y", "0px");
    };
    requestAnimationFrame(() => requestAnimationFrame(settle));
  }

  // The boot cloak in index.html comes off here, not when the last stylesheet
  // loads. Until a seat has been through the pass below it sits at style.css's
  // seven-seat defaults, so lifting the cloak on load showed that layout for as
  // long as the first snapshot took to arrive -- reported as a crooked table
  // flashing on entry. Wrapped so every exit path clears it, including the
  // empty-table one: with no seats to place there is nothing left to jump.
  //: Bounded retry for the case below -- roughly two seconds at 60fps.
  let placementRetries = 0;

  function applyDynamicLayout(gameState, tableState, isRetry) {
    // Every real render restarts the budget. Keying it to the first failure
    // instead burned all 120 frames during boot -- the layer chain calls this
    // with nulls long before the opening snapshot lands, so the retries were
    // spent and gone by the time the seat cards actually appeared.
    if (!isRetry) placementRetries = 0;
    let placed = false;
    try {
      placed = applyDynamicLayoutInner(gameState, tableState) === true;
    } finally {
      // The cloak comes off only once the seats are actually where they
      // belong. Until then they hold style.css's seven-seat defaults, and
      // app.js has drawn a roster into them -- revealing that is the crooked
      // table. A genuinely empty table is covered by index.html's failsafe
      // rather than by guessing here: three seconds of "loading" beats
      // showing a wrong table, and it only happens with nobody seated.
      if (placed) {
        document.body.classList.add("p8-boot-ready");
      } else if (placementRetries < 120) {
        // This sync can land before app.js has painted the seat cards, and
        // on an idle table the snapshot never changes again -- renderSnapshot
        // dedups on its own hash -- so nothing would ever call us a second
        // time. Without this the table stays unpositioned for good, which is
        // exactly what a one-bot table showed.
        placementRetries += 1;
        requestAnimationFrame(() => applyDynamicLayout(window.game, window.tableData, true));
      }
    }
  }

  function applyDynamicLayoutInner(gameState, tableState) {
    if (!isMobile() && !isDesktop()) return false;
    const allSeats = [...document.querySelectorAll(".seat[data-seat]")];
    const { active, viewer } = orderedActiveSeats(gameState, tableState);
    const count = Math.min(6, active.length);
    if (!count) return false;

    const activeSet = new Set(active);
    // While the viewer has no seat and the room is not full, one empty seat
    // stays on the felt as the invitation to sit -- in the hero's chair,
    // which is where they would end up. Every other empty seat stays hidden;
    // six of them scattered round the ring is furniture, not an offer.
    // Which empty seat carries the offer is app.js's decision, not ours:
    // renderSeats picks one `offeredSeat` and leaves the other empty seats
    // with no markup at all. Finding our own would be a second guess from a
    // different source (DOM seat order vs tableData.seats, .seat-card vs
    // occupant_type) and the two would drift apart -- we would place a blank
    // box on the felt and hide the real button. So: follow the button.
    const sitSeat = !viewer && count < 6
      ? allSeats.find(seat => !activeSet.has(seat) && seat.querySelector("[data-add-seat]")) || null
      : null;
    allSeats.forEach(seat => {
      const shown = activeSet.has(seat) || seat === sitSeat;
      seat.classList.toggle("v040-empty-seat", !shown);
      seat.classList.toggle("v040-dynamic-seat", shown);
      seat.classList.toggle("v040-sit-slot", seat === sitSeat);
    });
    // This runs on every snapshot/poll, i.e. continuously on a live table. A
    // remove-then-add of the class the body already carries still restarts
    // the width/height/transform transitions on .v040-dynamic-seat (verified:
    // it happens even with no other DOM change), so the seat box never
    // settles at its target size on an active table -- it sits stuck near
    // its pre-transition width for as long as renders keep arriving.
    const countClass = `p8-player-count-${count}`;
    if (!document.body.classList.contains(countClass)) {
      document.body.classList.remove(...[1, 2, 3, 4, 5, 6].map(value => `p8-player-count-${value}`));
      document.body.classList.add(countClass);
    }

    const points = !viewer && SPECTATOR_LAYOUTS[count] ? SPECTATOR_LAYOUTS[count] : LAYOUTS[count];
    document.body.classList.toggle("p8-spectator-layout", !viewer);
    active.forEach((seat, index) => {
      const [x, y] = points[index];
      seat.dataset.visualSeat = viewer ? String(index) : `spectator-${index}`;
      moveSeatTo(seat, x, y);
    });

    // The seats nobody is sitting in were never given a point, so they kept
    // the legacy seven-seat percentages from style.css -- which on a wide felt
    // put them outside the ellipse entirely. They are how a player sits down
    // now, so they have to be places at the table, not leftovers beside it.
    // Each takes a slot on the full ring that no active seat is near.
    const ring = (!viewer && SPECTATOR_LAYOUTS[6]) || LAYOUTS[6];
    const used = points.slice(0, active.length);
    const spare = ring.filter(([x, y]) =>
      used.every(([ax, ay]) => Math.hypot(x - ax, y - ay) > 12));
    if (sitSeat) moveSeatTo(sitSeat, 50, 80);
    allSeats
      .filter(seat => !activeSet.has(seat) && seat !== sitSeat)
      .forEach((seat, index) => {
        const point = spare[index % Math.max(1, spare.length)];
        if (point) moveSeatTo(seat, point[0], point[1]);
      });
    // Seats are where they belong -- the caller uses this to decide the boot
    // cloak can come off.
    return true;
  }

  const previousLayout = window.syncComponentSeatLayout;
  window.syncComponentSeatLayout = function syncPoker8DynamicSeatLayout(gameState, tableState) {
    previousLayout?.(gameState, tableState);
    applyDynamicLayout(gameState, tableState);
  };

  const previousUi = window.syncComponentUi;
  window.syncComponentUi = function syncPoker8DynamicSeatUi(gameState, tableState) {
    previousUi?.(gameState, tableState);
    applyDynamicLayout(gameState, tableState);
  };

  window.addEventListener("resize", () => applyDynamicLayout(window.game, window.tableData), { passive: true });

  // Lay the table out once on load, rather than only waiting to be called.
  // This layer is appended late in the chain, so on a table that renders once
  // and then sits still -- one that cannot deal, so no snapshot ever differs
  // and renderSnapshot's dedup never lets another render through -- the hooks
  // above are attached after the only render that was ever going to happen.
  // Nothing then positions a seat, and the table stays on style.css's
  // seven-seat defaults for good. The retry inside carries this until the
  // seat cards exist.
  applyDynamicLayout(window.game, window.tableData);
})();
