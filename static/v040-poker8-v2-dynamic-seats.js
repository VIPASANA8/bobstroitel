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
    // Both up on the top band rather than facing each other across the
    // middle of the felt. Side-by-side is how the pair reads as opponents at
    // the same table; at y:50 they sat level with the pot and board, one on
    // each flank, and the whole top of the felt stood empty. x:20/80 and
    // y:14 are the upper-wing values 5 and 6 already use, so the pair lands
    // in the band those were measured to clear the pot label from.
    2: [[20, 14], [80, 14]],
    3: [[50, 13], [18, 70], [82, 70]],
    // 4, 5 and 6 share one lower band at y:75. At 66 (64 on the hexagon) the
    // lower side seats' hole-card boxes ran into the community-card row:
    // measured 33px of vertical overlap on a 765px viewport and 54px at 640,
    // with their horizontal edges crossing the board as well, so a spectator
    // watching from the side had the street covered by a player. 75 clears a
    // five-card board and those cards from 640px through 874px, and stays
    // wide of the bottom-centre seat, a third of the felt away horizontally.
    // Only the spectator layouts move; a seated player's own ring is
    // untouched, and so are the top rows below.
    4: [[24, 14], [76, 14], [83, 75], [17, 75]],
    // The top three are staggered, not stacked in a row. At pole y:14 with
    // wings at y:19 the three name plates overlapped vertically by 14px
    // while sitting 5px apart horizontally -- measured on a 317x615 phone
    // felt -- so they read as one wall of boxes across the top. Pole 12 and
    // wings 21 put 10px of clear air between the pole's plate and theirs,
    // and the pole's cards still land 5px inside the felt. Both stay off the
    // pot, the chips, the summary strip and the board.
    5: [[50, 12], [20, 21], [80, 21], [85, 75], [15, 75]],
    // The top three use two distinct levels: the pole takes the former wing
    // level at y:14 and both wings move down together to y:19. All three stay
    // above the reserved pot/board band, which begins below y:22.
    //
    // The lower pair went 61 -> 64 to get off the community cards, measured
    // on a 321x760 phone felt where the board occupies y 47-58% and a seat
    // centred at 61% spans 56-66% ("не перекрывать улицу"). 64 cleared the
    // board itself but not the hole cards above those seats, which is why it
    // moved again to the shared 75 band above. What 64 also bought -- a
    // 20-point gap to the bottom pole, so the ring read as a hexagon rather
    // than two rows -- is what 75 gives up; the pole is cleared sideways
    // instead, which is what the test now checks.
    6: [[50, 12], [83, 21], [83, 75], [50, 85], [17, 75], [17, 21]],
  };

  // Desktop has its own ring. The felt there is a 16:10 oval (1228x722 at
  // 1080p) where the phone's is tall and narrow, and the percentages above
  // were worked out against the narrow one: on a wide table they left the
  // top third empty and crowded three boxes along the bottom. Keeping them
  // separate also unpicks the knot where a phone fix moved desktop and back.
  const DESKTOP_LAYOUTS = {
    1: [[50, 86]],
    2: [[50, 86], [50, 12]],
    3: [[50, 86], [18, 30], [82, 30]],
    4: [[50, 86], [16, 62], [50, 12], [84, 62]],
    5: [[50, 86], [15, 62], [26, 18], [74, 18], [85, 62]],
    6: [[50, 86], [16, 68], [16, 26], [50, 12], [84, 26], [84, 68]],
  };

  // Watching, so nobody owns the near chair: the ring closes over the bottom
  // and the empty seat that carries the invitation takes it instead.
  const DESKTOP_SPECTATOR_LAYOUTS = {
    1: [[50, 12]],
    2: [[26, 18], [74, 18]],
    3: [[50, 12], [18, 60], [82, 60]],
    4: [[26, 16], [74, 16], [84, 62], [16, 62]],
    5: [[50, 10], [20, 22], [80, 22], [85, 64], [15, 64]],
    6: [[50, 10], [82, 24], [82, 70], [50, 88], [18, 70], [18, 24]],
  };

  const ringsFor = viewer => (isDesktop()
    ? (viewer ? DESKTOP_LAYOUTS : DESKTOP_SPECTATOR_LAYOUTS)
    : (viewer ? LAYOUTS : SPECTATOR_LAYOUTS));

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

      /* The invitation is a chair, so it takes the chair's own shape: the
         avatar's circle, in the avatar's place, with the label where the
         name plate goes. It used to be a 29px dashed dot floating inside a
         44px button with the word tucked under it -- next to a real seat it
         read as a stray control rather than a place at the table. The
         numbers are v038's and v039's own avatar/identity geometry, kept in
         variables so the two modes differ by four values instead of two
         copies of every rule. */
      body.v014.poker8-v2-sixmax .seat.v040-sit-slot{
        --p8-sit-size:44px;--p8-sit-top:0px;--p8-sit-label-top:40px;--p8-sit-label-w:90px;--p8-sit-glyph:20px;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat.v040-sit-slot{
        --p8-sit-size:88px;--p8-sit-top:2px;--p8-sit-label-top:82px;--p8-sit-label-w:116px;--p8-sit-glyph:27px;
      }
      body.v014.poker8-v2-sixmax .seat.v040-sit-slot .seat-empty{
        position:absolute!important;left:50%!important;top:var(--p8-sit-top)!important;
        transform:translateX(-50%)!important;
        width:var(--p8-sit-size)!important;height:var(--p8-sit-size)!important;
        min-height:0!important;min-width:0!important;padding:0!important;
        display:block!important;border:0!important;background:none!important;
        border-radius:50%!important;overflow:visible!important;z-index:4;
      }
      body.v014.poker8-v2-sixmax .seat.v040-sit-slot .empty-avatar{
        display:grid!important;place-items:center!important;
        /* Its own pixels, not a percentage of the button: a percentage height
           depends on the parent resolving one, and where it did not the ring
           collapsed to the glyph's line box and drew as a flat ellipse
           instead of a circle. aspect-ratio holds it round even then. */
        width:var(--p8-sit-size)!important;height:var(--p8-sit-size)!important;
        aspect-ratio:1!important;box-sizing:border-box!important;
        border:2px dashed rgba(75,255,181,.72)!important;border-radius:50%!important;
        background:rgba(0,0,0,.62)!important;color:rgba(75,255,181,.72)!important;
        font-size:var(--p8-sit-glyph)!important;line-height:1!important;
      }
      /* The word sits on a plate, the way a name does. Bare text under the
         circle was the half of this that still did not look like a seat. Same
         box as .seat-identity in v038 -- position, width, padding, radius and
         ground -- with the empty seat's own mint edge instead of the accent
         hue a taken seat carries. */
      body.v014.poker8-v2-sixmax .seat.v040-sit-slot .seat-empty strong{
        position:absolute!important;left:50%!important;top:var(--p8-sit-label-top)!important;
        transform:translateX(-50%)!important;width:var(--p8-sit-label-w)!important;
        box-sizing:border-box!important;padding:5px 6px 4px!important;
        border:1px solid rgba(75,255,181,.72)!important;border-radius:9px!important;
        background:linear-gradient(180deg,rgba(0,0,0,.98),rgba(0,0,0,.995))!important;
        color:rgba(75,255,181,.72)!important;font-size:10px!important;line-height:1.1!important;
        letter-spacing:.06em!important;text-align:center!important;
      }
      /* Held for you. Claiming a seat during a hand always worked -- the
         queue seats you at the boundary -- but the chair carried on offering
         itself, so the only sign anything had happened was in the header.
         The ring closes and fills, and the word changes; pressing it again
         does nothing, since cancelling lives in the header. */
      body.v014.poker8-v2-sixmax.p8-seat-reserved .seat.v040-sit-slot .seat-empty{
        pointer-events:none!important;
      }
      body.v014.poker8-v2-sixmax.p8-seat-reserved .seat.v040-sit-slot .empty-avatar{
        border-style:solid!important;background:rgba(75,255,181,.18)!important;
        font-size:0!important;
      }
      /* Laid over the circle rather than placed in it: the "+" it replaces is
         a bare text node, and grid wraps that in an anonymous item even at
         font-size:0, so the tick was auto-placed into a second row and sat
         below centre. Absolute inset:0 has no such neighbour to queue behind. */
      body.v014.poker8-v2-sixmax.p8-seat-reserved .seat.v040-sit-slot .empty-avatar{
        position:relative!important;
      }
      body.v014.poker8-v2-sixmax.p8-seat-reserved .seat.v040-sit-slot .empty-avatar::after{
        content:"✓";position:absolute;inset:0;
        display:grid;place-items:center;
        font-size:var(--p8-sit-glyph);line-height:1;
      }
      body.v014.poker8-v2-sixmax.p8-seat-reserved .seat.v040-sit-slot .seat-empty strong{
        font-size:0!important;
      }
      body.v014.poker8-v2-sixmax.p8-seat-reserved .seat.v040-sit-slot .seat-empty strong::after{
        content:"ВАШЕ МЕСТО";
        font-size:10px;letter-spacing:.06em;
      }
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
    // Whether a seat is taken is app.js's answer, and the seat-card it drew is
    // where that answer lives. gameState.players is the last *dealt* hand's
    // roster and outlives the people in it -- on a table that can no longer
    // deal it never updates again -- so reading it directly laid the felt out
    // for players who had already left: ghost boxes on the ring, everybody
    // real pushed into the wrong layout, and the Сесть button carried off to
    // a player's position. app.js filters the same thing by current_seats
    // (see playerAtSeat), which is why only its output can be trusted here.
    const card = seat.querySelector(".seat-card");
    if (!card) return null;
    const physical = Number(seat.dataset.seat);
    // The roster is still the better source for *who* it is when it has them;
    // .viewer-seat is app.js's own "is this you" marker for when it does not.
    return Object.values(gameState?.players || {}).find(player => Number(player?.seat) === physical)
      || { seat: physical, id: null, isViewerCard: card.classList.contains("viewer-seat") };
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

    const table = ringsFor(viewer);
    const points = table[count] || (viewer ? LAYOUTS[count] : SPECTATOR_LAYOUTS[count]);
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
    // Cleared on the way out, or it outlives the seat's turn at being taken.
    // Half a dozen layers pin a seat by [data-visual-seat="N"], at the same
    // specificity as the rule below that reads --v040-seat-x, so a stale
    // attribute is not a tie v040 wins -- load order decides, and v040 loses.
    // A leftover "1" on the seat holding the Сесть button pinned it to the
    // first chair's arc position in the corner, whatever coordinates it had
    // just been given.
    allSeats.forEach(seat => {
      if (!activeSet.has(seat)) delete seat.dataset.visualSeat;
    });

    const ring = table[6] || LAYOUTS[6];
    const used = points.slice(0, active.length);
    const spare = ring.filter(([x, y]) =>
      used.every(([ax, ay]) => Math.hypot(x - ax, y - ay) > 12));
    // The hero's own chair, read off the seated ring rather than written out:
    // it is 50/80 on the phone and 50/86 on the desktop oval, and an
    // invitation that sits anywhere else is not "where you would end up".
    const heroPoint = ringsFor(true)[6][0];
    if (sitSeat) moveSeatTo(sitSeat, heroPoint[0], heroPoint[1]);
    allSeats
      .filter(seat => !activeSet.has(seat) && seat !== sitSeat)
      .forEach((seat, index) => {
        const point = spare[index % Math.max(1, spare.length)];
        if (point) moveSeatTo(seat, point[0], point[1]);
      });

    // Revealed last, and only now that every seat above has its coordinates.
    // Doing this first meant anything that went wrong in between -- a layout
    // with fewer points than players, a class combination matching neither
    // half of the stylesheet -- left a seat on screen with nothing positioning
    // it, so it fell back to style.css's seven-seat ring. That is how the
    // Сесть button kept turning up in the top-left corner instead of the
    // hero's chair. A seat that cannot be placed now simply stays hidden.
    allSeats.forEach(seat => {
      const shown = activeSet.has(seat) || seat === sitSeat;
      seat.classList.toggle("v040-empty-seat", !shown);
      seat.classList.toggle("v040-dynamic-seat", shown);
      seat.classList.toggle("v040-sit-slot", seat === sitSeat);
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
