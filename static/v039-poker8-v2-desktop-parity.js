(() => {
  "use strict";

  const DESKTOP_QUERY = "(min-width: 781px)";
  const actionPanel = document.querySelector(".action-panel");
  const actionHome = actionPanel?.parentElement;
  const actionNext = actionPanel?.nextSibling;

  function syncDesktopMode() {
    const desktop = window.matchMedia?.(DESKTOP_QUERY)?.matches ?? false;
    document.body.classList.toggle("poker8-desktop-v2", desktop);
    const frame = document.querySelector(".table-frame");
    if (!actionPanel || !actionHome || !frame) return;
    if (desktop && actionPanel.parentElement !== frame) frame.appendChild(actionPanel);
    else if (!desktop && actionPanel.parentElement !== actionHome) {
      actionHome.insertBefore(actionPanel, actionNext?.parentElement === actionHome ? actionNext : actionHome.firstChild);
    }
  }

  const style = document.createElement("style");
  style.id = "v039-poker8-v2-desktop-parity-style";
  style.textContent = `
    /* The phone ring is v038's arc, and only v038's arc.

       Two seats used to be pulled off it here, in percentages, to keep the
       right-hand pair "inside the felt safe area" -- which is what
       --p8-seat-safe-inset already buys, on both sides. The result was a ring
       whose right half was 9% lower than its left, and worse, which half won
       was decided by stylesheet order: these rules and v040's tie on
       specificity, this file re-appends itself to the end of <head> on load,
       and v038's own sheet is created whenever its script happens to finish
       loading. So the same table could come up on the arc or off it. */

    /* Desktop inherits the same dark wood, green felt and neon-seat language as mobile. */
    @media (min-width:781px){
      body.v014.poker8-desktop-v2{
        --p8-wood-dark:#0c0503;
        --p8-wood-mid:#51270f;
        --p8-felt:#003b24;
        color:#eafff6!important;
        background:
          radial-gradient(ellipse at 50% 26%,rgba(15,95,58,.16),transparent 43%),
          repeating-linear-gradient(96deg,#000000 0 8px,#180b05 9px 17px,#0c0503 18px 27px)!important;
      }

      /* A photographed floor instead of the three-tone stripe that stood in
         for one. Fixed and covering, so it does not slide with the layout or
         tile into a seam: it is one room, not a pattern.

         Three classes, not two: v038 paints this same property on
         body.v014.poker8-v2-sixmax from a stylesheet appended after this
         one, so at equal specificity it wins on source order -- which is
         also how its 100vw background-size outlived the frame rule above. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2{
        background:
          radial-gradient(ellipse at 50% 26%,rgba(15,95,58,.16),transparent 43%),
          url("/static/assets/room-wood-desktop.webp") center/cover no-repeat fixed,
          #0c0503!important;
      }

      body.v014.poker8-desktop-v2 .mobile-game-header,
      body.v014.poker8-desktop-v2 #mobileDrawer,
      body.v014.poker8-desktop-v2 #mobileDrawerBackdrop{display:none!important;}
      body.v014.poker8-desktop-v2 .room-ambience{position:fixed!important;inset:0!important;width:100%!important;height:100dvh!important;opacity:.28!important;filter:saturate(.68) brightness(.55)!important;pointer-events:none!important;z-index:0!important;}
      /* A flex column so the in-flow topbar takes its own height and .layout
         claims exactly what is left, instead of both guessing at 76px. */
      body.v014.poker8-desktop-v2 .app-shell{position:relative!important;z-index:1!important;width:min(1720px,calc(100% - 40px))!important;margin:0 auto!important;display:flex!important;flex-direction:column!important;height:100dvh!important;padding-top:10px!important;padding-bottom:0!important;box-sizing:border-box!important;}
      /* style.css:2590 (.neon-ref-v107 .topbar) leaves this absolute at
         inset:0 0 auto with z-index:310 -- an overlay from the alpha design,
         where it floated over a full-bleed table. It therefore reserves no
         height: .layout started at y:50 while the bar occupied 0-76, so the
         chat panel's own "Чат стола" heading (y:67-86) was painted over by
         it. Measured live at 1732px. In flow it reserves its height and the
         overlap cannot happen. style.css:2335 also caps it at 1440px, which
         on a 1692px shell read as a detached floating card rather than the
         page's own header -- so it spans the shell here instead.
         pointer-events comes back with it: the alpha bar was click-through
         because the table was underneath, which is no longer true. */
      body.v014.poker8-desktop-v2 .topbar{
        position:relative!important;inset:auto!important;
        flex-direction:row!important;align-items:center!important;
        /* The same min(1500px,100%) style.css:2589 gives .layout one line
           above the rule this is undoing -- so the bar and the content it
           heads share an edge instead of the bar overhanging it by ~92px
           on a 1720px shell. */
        max-width:none!important;width:min(1500px,100%)!important;
        margin-inline:auto!important;
        pointer-events:auto!important;
        /* Trimmed from 74/13 now that the bar costs real vertical space
           instead of floating: on a 720p desktop the seated felt loses
           whatever this takes, and 44px of content box still clears the
           42px buttons inside it. */
        /* style.css:2590 sets a hard height:76px, so min-height alone was
           inert -- the bar stayed 76 tall no matter what. */
        height:auto!important;min-height:66px!important;padding:11px 18px!important;
        border:1px solid rgba(40,255,183,.18)!important;border-radius:0 0 18px 18px!important;
        background:linear-gradient(180deg,rgba(7,16,15,.94),rgba(0,0,0,.82))!important;
        box-shadow:0 12px 28px rgba(0,0,0,.44),inset 0 -1px rgba(71,255,190,.08)!important;
      }
      body.v014.poker8-desktop-v2 .brand-mark{border-color:#37dca2!important;background:#022d1d!important;color:#9fffd9!important;box-shadow:0 0 16px rgba(55,220,162,.24)!important;}
      /* The table's own name and stakes, standing in for the local-trainer
         identity that used to sit here (see online-table.js's syncTableIdentity
         and the mode-scoped hides beside it). */
      body.v014.poker8-desktop-v2 .p8-table-identity b{
        display:block;color:#eafff6;font-size:15px;line-height:1.25;letter-spacing:-.01em;
      }
      body.v014.poker8-desktop-v2 .p8-table-identity small{
        display:block;margin-top:2px;color:#8ca59c;font-size:12px;line-height:1.25;
      }
      /* .top-actions is an empty flex row on an online table once the
         local-trainer buttons are hidden -- it is where placeHeaderActions
         parks the seat pair and the chat/hint group. The phone header's own
         order/margin rules are width-gated away, so the layout is stated
         here instead of inherited. */
      body.v014.poker8-desktop-v2 .top-actions{
        display:flex!important;align-items:center!important;gap:8px!important;
        min-width:0!important;flex:0 1 auto!important;
        /* style.css:502 lets this group wrap. That was free while the bar held
           only the brand and these controls; once the reservation strip took
           its 300px out of the same line the controls spilled onto a second
           row and the header stood twice as tall. Nowrap makes the strip the
           thing that gives -- it is the one flexible item in the bar -- rather
           than the header growing to swallow the overflow. */
        flex-wrap:nowrap!important;
      }
      /* ...and the controls themselves keep their width while it does. */
      body.v014.poker8-desktop-v2 .top-actions > *{flex:0 0 auto!important;}
      body.v014.poker8-desktop-v2 .mobile-header-utility{display:flex!important;gap:8px!important;align-items:center!important;}
      /* placeHeaderActions parks the seat pair here, as a sibling of the
         identity and the control cluster. The auto margin is what keeps it
         next to the identity: .topbar is space-between, and an auto margin
         takes the free space before the cluster rather than around it. */
      body.v014.poker8-desktop-v2 .topbar > .mobile-header-seat-actions{
        margin-right:auto!important;flex:0 0 auto!important;
      }
      /* Room to breathe that a 374px phone could not spare: the labels stop
         being clipped to an ellipsis and the hit target grows to match the
         42px chat/hint squares beside them. */
      body.v014.poker8-desktop-v2 .mobile-header-seat-actions button{
        min-height:42px!important;padding:9px 14px!important;
      }
      /* The drawer's own buttons, parked in this header on desktop (see
         placeHeaderActions). Their drawer styling is scoped to
         .mobile-drawer, so out here they need the header's shape. */
      body.v014.poker8-desktop-v2 .top-actions #mobileDrawerLobby,
      body.v014.poker8-desktop-v2 .top-actions #mobileDrawerLeave{
        width:auto!important;min-height:42px!important;padding:9px 14px!important;
        border:1px solid rgba(64,237,167,.34)!important;border-radius:11px!important;
        background:rgba(4,31,20,.72)!important;color:#b8ffda!important;
        font:700 13px/1 Inter,ui-sans-serif,system-ui!important;
        white-space:nowrap!important;cursor:pointer!important;
      }
      /* Same danger colours it wears in the drawer -- this one gives up a
         seat, and the one beside it only stops watching. */
      body.v014.poker8-desktop-v2 .top-actions #mobileDrawerLeave{
        border-color:rgba(255,125,111,.34)!important;
        background:rgba(52,14,12,.58)!important;color:#ffc1b6!important;
      }
      body.v014.poker8-desktop-v2 .mobile-header-seat-actions #mobileHeaderTakeSeat,
      body.v014.poker8-desktop-v2 .mobile-header-seat-actions #mobileHeaderObserve{
        width:auto!important;min-width:104px!important;
      }
      body.v014.poker8-desktop-v2 .eyebrow, body.v014.poker8-desktop-v2 .panel-kicker{color:#eab873!important;letter-spacing:.14em!important;}
      body.v014.poker8-desktop-v2 .topbar h1{color:#eafff6!important;}
      body.v014.poker8-desktop-v2 .layout{grid-template-columns:minmax(0,1fr) 296px!important;gap:18px!important;align-items:start!important;}
      body.v014.poker8-desktop-v2 .left-column{min-width:0!important;}
      body.v014.poker8-desktop-v2 .sidebar{gap:14px!important;}
      /* :not(.action-panel) -- the action panel is a .panel too, and this
         rule has always claimed it and always lost: v036 and v038 paint that
         one, and this only wins for the panels nobody else touches. Saying
         so is what makes this file's place in the load order stop mattering;
         with the claim still here, moving the file repainted the panel's
         border and shadow (measured: the last three differences of fifty). */
      body.v014.poker8-desktop-v2 .panel:not(.action-panel),
      body.v014.poker8-desktop-v2 .history-card,
      body.v014.poker8-desktop-v2 .online-chat-panel{
        border-color:rgba(64,237,167,.18)!important;
        background:linear-gradient(180deg,rgba(7,16,15,.94),rgba(0,0,0,.96))!important;
        box-shadow:0 12px 26px rgba(0,0,0,.34),inset 0 1px rgba(142,255,209,.03)!important;
      }

      body.v014.poker8-desktop-v2 .table-frame{
        height:clamp(620px,calc(100dvh - 156px),860px)!important;
        /* padding, overflow and box-shadow used to be here too. All three are
           absolute values, so declared and computed can be compared honestly
           -- and all three lose to v038 on the live table (padding is
           0 5px 1px, overflow is visible). Losing is the only thing making
           them harmless: they would wake up the moment this file's place in
           the load order changed. The border and the radius below win, so
           they stay. */
        min-height:620px!important;
        border:1px solid rgba(44,255,172,.13)!important;border-radius:28px!important;
        background:
          linear-gradient(90deg,rgba(0,0,0,.58),transparent 17%,transparent 83%,rgba(0,0,0,.58)),
          url("/static/assets/poker8-v2-table-mobile.webp") center/cover no-repeat,
          repeating-linear-gradient(96deg,#000000 0 8px,#180b05 9px 17px,#0c0503 18px 27px)!important;
      }
      /* The paint this file used to put on the felt -- its own green
         gradient, neon border and inset shadow -- is v037/v038's now, and
         every one of those values loses to them today. Removed 2026-08-29.

         The size stays, and the reason is the whole lesson of that day: this
         .felt is position:relative, so the inset beside it only offsets the
         box, it does not stretch it. The height *is* the felt's height. It
         looked dead in a dry run only because moving this file changed the
         frame's padding, and a percentage measured against a different
         parent computes differently without losing anything. Percentages
         cannot be judged by their computed value. */
      body.v014.poker8-desktop-v2 .felt{
        width:calc(100% - 76px)!important;height:calc(100% - 50px)!important;inset:25px 38px!important;
      }
      /* An inner ring on the felt used to be stated here, and a glow in the
         middle of it below the ::after. Both lose today, and by more than a
         value: v038 hides this ::before outright and draws the glow at its
         own inset with its own gradient. Measured live -- display:none
         against display:block, 10% against 16%. They were the last two
         declarations in this block that a change of load order could have
         woken up. Removed 2026-08-29; docs/layer-cleanup.md. */
      body.v014.poker8-desktop-v2 .felt::after{display:none!important;}

      /* A fixed seven-point ring used to be stated here, in --seat-N-x/y and
         seven [data-visual-seat$="N"] rules. v040 has placed every seat since
         it arrived: it writes --v040-seat-x/y per seat and per player count,
         off a ring chosen for the felt's shape and for whether you hold a
         seat. Measured 2026-08-29 by moving this file's <style> to the end of
         <head> on the live table: the seats jump to mirrored positions, which
         is this ring waking up. It has not placed a seat in a long time, and
         holding it here only means a future load-order change moves the
         table. Removed; see docs/layer-cleanup.md. */

      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat{width:128px!important;height:140px!important;min-height:0!important;z-index:20!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat="0"]{width:144px!important;height:150px!important;z-index:28!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-card{width:100%!important;height:100%!important;min-height:0!important;padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;overflow:visible!important;}
      /* The head has a ceiling of its own. Everything on this table takes
         --p8-ui-scale, and at the top of that range an 88px avatar paints
         119px, which is a portrait rather than a seat marker. Dividing the
         cap by the scale means the growth stops at 92px painted: nothing
         changes until the factor passes ~1.05, and the biggest screens get
         a head the size the middling ones already had.

         The plate and the dealer button hang off the same value, so the 6px
         the name plate tucks under the chin holds at every size. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2{
        --p8-avatar:min(88px,calc(92px / var(--p8-ui-scale)));
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .avatar-wrap{position:absolute!important;left:50%!important;top:2px!important;transform:translateX(-50%)!important;width:var(--p8-avatar)!important;height:var(--p8-avatar)!important;z-index:4!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-avatar{width:var(--p8-avatar)!important;height:var(--p8-avatar)!important;border:2px solid hsl(var(--avatar-hue) 95% 68%)!important;background:radial-gradient(circle at 50% 30%,hsl(var(--avatar-hue) 62% 44% / .46),transparent 31%),radial-gradient(circle at 50% 78%,#07100f 0 42%,#000000 70%)!important;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 20px hsl(var(--avatar-hue) 92% 56% / .42),inset 0 -12px 20px rgba(0,0,0,.52)!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .avatar-wrap::before,body.v014.poker8-v2-sixmax.poker8-desktop-v2 .avatar-wrap::after{display:none!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-identity{position:absolute!important;z-index:6!important;left:50%!important;top:calc(var(--p8-avatar) - 6px)!important;transform:translateX(-50%)!important;width:116px!important;min-height:43px!important;padding:7px 8px 6px!important;border:1px solid hsl(var(--avatar-hue) 88% 58% / .72)!important;border-radius:10px!important;background:linear-gradient(180deg,rgba(0,0,0,.98),rgba(0,0,0,.995))!important;box-shadow:0 0 14px hsl(var(--avatar-hue) 88% 55% / .22),0 8px 16px rgba(0,0,0,.64)!important;text-align:center!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-name{max-width:82px!important;font-size:10px!important;line-height:1!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-stack{margin-top:4px!important;font-size:15px!important;line-height:1!important;color:hsl(var(--avatar-hue) 95% 68%)!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .bot-level,body.v014.poker8-v2-sixmax.poker8-desktop-v2 .position-chip{display:none!important;}
      /* In front of the head, fanned, whole.

         They used to sit behind it at top:-20px, so all anyone saw was the
         20px strip above the hair -- and on the top row that strip is the
         part nearest the felt's edge, which is what made them look cut off.
         Nothing about that reads as a pair of cards on a table this size.

         In front and lower: the pair now lives inside the seat box entirely
         (-14 to 41 of a 148px box), which is also what lets the top row's
         pixel floor come down -- the overhang it has to clear is 14px now,
         not 20. The bottom edge stops 5px short of the avatar's centre,
         where the stake is printed. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-cards{--p8-card-factor:var(--p8-center-scale);position:absolute!important;z-index:8!important;left:50%!important;top:-14px!important;bottom:auto!important;transform:translateX(-50%)!important;min-height:0!important;gap:0!important;pointer-events:none!important;}
      /* The board's parent is scaled down; seats are not. Compensate once
         so every card has the same painted size, including hidden backs. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .board-cards .card,
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat] .player-cards .card{
        width:calc(var(--p8-card-w) * var(--p8-card-factor,1))!important;
        height:calc(var(--p8-card-h) * var(--p8-card-factor,1))!important;
        flex:0 0 auto!important;box-sizing:border-box!important;
      }
      /* The fan. Rotated about the bottom edge, which is where a held pair
         pivots, and overlapped so the two read as one hand rather than two
         cards standing side by side. :not(:last-child) so a lone card -- a
         showdown that only turned one over -- stays straight. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-cards .card{
        transform-origin:50% 100%!important;
      }
      /* Revealed opponents use the same readable rank/suit scale as the hero. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat] .player-cards .card-rank{left:5px!important;top:3px!important;font-size:15px!important;font-weight:950!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat] .player-cards .card-suit{font-size:27px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-cards .card:first-child:not(:last-child){
        transform:rotate(-6deg)!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-cards .card:last-child:not(:first-child){
        transform:rotate(6deg)!important;margin-left:-7px!important;
      }
      /* The desktop card back is v038's card back. This drew a second one off
         --avatar-hue -- per-player colour, no centre ring -- so the same deck
         had two faces depending on the window width. Sizes still come from
         the --p8-card-w rule above; only the picture is shared. */
      /* Same avatar size and plate as every other seat -- the hero used to be
         smaller than everyone else here, which read as a rendering bug. Only
         the "this is you" border colour stays hero-specific. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-avatar{border-color:#35bfff!important;}
      /* Face down goes back behind the head.

         In front, a pair of backs is just a green rectangle over somebody's
         face -- there is nothing on it to read, so all it does is hide the
         seat. Face up there is: those stay in front, fanned, where the cards
         are the point. So the z-order follows what is on the card, and a
         back also goes back up to its old peek, since behind the avatar only
         the strip above it shows. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-cards:has(.card.back){
        z-index:3!important;top:-20px!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-cards:has(.card.back){
        z-index:3!important;top:-26px!important;
      }

      /* The hero keeps its own accent, not a different card size. :where
         excludes backs without outranking the red-suit or best-hand accent. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-cards{top:-22px!important;z-index:12!important;gap:0!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-cards .card:where(:not(.back)){border-color:#56c8ff!important;box-shadow:0 0 12px rgba(47,184,255,.46),0 5px 9px rgba(0,0,0,.54)!important;}
      /* Beside the avatar on its left, the way the phone places it -- it sat
         bottom-right of the whole seat box here, which on a 146x154 box reads
         as floating off the seat rather than belonging to it. The avatar is
         88px centred in that box, so its left edge is at 29px and this sits
         just outside it, centred on the same line. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .dealer-button{
        left:-5px!important;top:calc(var(--p8-avatar) / 2 - 13px)!important;right:auto!important;bottom:auto!important;
        width:30px!important;height:30px!important;z-index:12!important;
      }

      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .table-center{transform:translate(-50%,-50%) scale(calc(var(--p8-center-scale) * var(--p8-ui-scale)))!important;z-index:12!important;}
      /* The rest of what the felt itself draws. The seats and the centre
         cluster take the factor where they are defined; these four are laid
         out against the felt directly, so they take it here.

         The two on the bottom edge grow from that edge -- their own
         translateX keeps them centred on their column, and an origin at the
         bottom stops the growth from pushing them through the rail. The
         other two are already centred on a point and grow about it. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .street-splash{
        transform:translate(-50%,-50%) scale(calc(.86 * var(--p8-ui-scale)))!important;
      }
      /* The ready ring used to be able to land on .felt, which is not scaled,
         so it needed the factor applied by hand. It now only ever hangs on the
         hero's avatar-wrap, inside a seat that already carries the same scale,
         and it sizes itself off that avatar -- so this rule was applying the
         factor a second time and drawing the ring smaller than the head it is
         supposed to ring. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .v038-turn-timer,
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .v038-turn-context{
        transform:translateX(-50%) scale(var(--p8-ui-scale))!important;
        transform-origin:bottom center!important;
      }
      /* Same on desktop: the player stays lit, the cards go. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-card.folded{opacity:1!important;filter:none!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-card.folded .player-cards{display:none!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-card.folded .seat-identity{background:linear-gradient(180deg,rgba(9,10,10,.98),rgba(0,0,0,.995))!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-identity{backdrop-filter:blur(5px)!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .player-status{
        position:absolute!important;z-index:10!important;left:auto!important;right:5px!important;top:7px!important;
        width:auto!important;height:21px!important;min-height:21px!important;max-height:21px!important;box-sizing:border-box!important;padding:4px 6px!important;
        overflow:hidden!important;display:flex!important;align-items:center!important;transform:none!important;writing-mode:horizontal-tb!important;white-space:nowrap!important;
        border:1px solid rgba(255,142,128,.54)!important;border-radius:999px!important;
        background:rgba(22,8,9,.92)!important;color:#ffb8ad!important;
        font-size:10px!important;line-height:1!important;letter-spacing:.06em!important;
        box-shadow:0 4px 10px rgba(0,0,0,.42)!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .board-cards .card{border-color:rgba(98,255,170,.82)!important;background:linear-gradient(150deg,#07100f,#000000)!important;box-shadow:0 0 12px rgba(35,255,159,.32),0 6px 11px rgba(0,0,0,.58)!important;}
      /* The board card the viewer's hand is actually made of.

         v038 paints it amber, but that rule and the mint one directly above
         tie on specificity -- five classes each -- and this file re-appends
         itself to the end of <head>, so on desktop the mint won and the card
         went back to looking like every other one. The hero's own two cards
         never had the problem: v038 reaches them through .viewer-seat as well,
         which is one class more than anything here. Same amber, restated after
         the rule that was overwriting it. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .board-cards .card.hand-combo{
        border-color:#f1c867!important;
        box-shadow:0 0 0 2px rgba(238,180,65,.42),0 0 16px rgba(238,180,65,.62),inset 0 0 10px rgba(238,180,65,.16)!important;
      }
      /* Same reading order as the phone -- chips, then the amount, then the
         board -- which desktop had upside down: the board sat at 42% of the
         felt with the pot below it at 63%. Placed against this oval rather
         than inherited from the tall one: the top seats' plates end at 25%
         and the bottom seats' boxes begin at 59%, so the run 26 -> 58 is the
         band that is actually free. */
      /* Chips, then the amount, then the board -- the order the phone reads
         in, which desktop had upside down: the board sat above a pot below
         it. These three live in normal flow inside .table-center here (they
         are absolutely placed on the phone, where that box is the whole
         felt), so the fix is the flow's own order, not a top percentage --
         on a relative element that only nudges it along from where the flow
         already put it, which is what pushed the cluster into the lower
         third. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .table-center{
        display:flex!important;flex-direction:column!important;
        align-items:center!important;justify-content:center!important;gap:12px!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .pot-chips{order:1!important;top:auto!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .pot-total{order:2!important;top:auto!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .board-cards{order:3!important;top:auto!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .pot-total{border-color:rgba(60,225,150,.26)!important;background:rgba(4,31,20,.78)!important;box-shadow:0 5px 13px rgba(0,0,0,.42)!important;}
      /* v019-center-polish sets display:flex!important on the same selector
         family, so the hide needs !important here to actually win. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2.p8-no-pot .pot-total{display:none!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .pot-total strong{color:#eafff6!important;font-size:27px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .street-badge{border-color:rgba(63,244,173,.30)!important;background:rgba(10,26,18,.82)!important;color:#b8ffda!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .online-state-panel{border-color:rgba(63,244,173,.34)!important;background:rgba(4,31,20,.92)!important;box-shadow:0 0 20px rgba(44,247,169,.14)!important;}
      body.v014.poker8-desktop-v2 .online-connection-status{border-color:rgba(68,231,210,.48)!important;background:rgba(2,19,18,.92)!important;color:#8effd1!important;}
      body.v014.poker8-desktop-v2 .btn.primary,body.v014.poker8-desktop-v2 .action-grid button.primary{border-color:#62efb3!important;background:linear-gradient(135deg,#8effd1,#47e6a8)!important;color:#041f14!important;box-shadow:0 0 18px rgba(64,237,167,.24)!important;}

      @media (max-width:1000px){
        body.v014.poker8-desktop-v2 .app-shell{width:calc(100% - 24px)!important;}
        body.v014.poker8-desktop-v2 .layout{grid-template-columns:1fr!important;}
        body.v014.poker8-desktop-v2 .sidebar{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;}
        body.v014.poker8-desktop-v2 .table-frame{height:clamp(590px,70dvh,760px)!important;}
      }
    }

      /* Desktop geometry for the v2 table.

         The layout is one column on a phone: table, chat, then the action
         panel, sized to fill 100dvh. Given 1440x900 that stack came to 1110px
         and the action panel landed at y=967 -- below the fold, on a page that
         does not scroll. The felt also ran the full 1364px, which is not a
         shape a poker table has.

         The controls now live inside the table frame, so this is one stable
         row at every hand state. Chat remains an overlay. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .layout{
        display:grid!important;
        /* One column. The chat was a permanent 330px card whether anyone was
           talking or not, and it took the width the table needed to stop
           being square. It opens over the felt now, from the same button the
           phone uses -- which already sits in this header. */
        grid-template-columns:minmax(0,1fr)!important;
        grid-template-rows:minmax(0,1fr)!important;
        grid-template-areas:"table"!important;
        gap:0!important;
        /* Was height:calc(100dvh - 76px) -- the 76 stood for a topbar that
           was out of flow and reserved nothing. Now that it is in flow (see
           the .topbar rule above) subtracting it as well would count it
           twice and push the page past the viewport. The shell is a flex
           column, so the remaining space is simply what is left. */
        flex:1 1 auto!important;
        height:auto!important;
        min-height:0!important;
        padding-bottom:12px!important;
        box-sizing:border-box!important;
      }
      /* height:100%, not auto: --table-stage-h is a percentage of this box, and
         against an auto height it resolved to nought -- the felt came out
         940x3. The grid row is the definite height everything hangs off. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .left-column{
        grid-area:table!important;min-height:0!important;height:100%!important;
        display:flex!important;flex-direction:column!important;justify-content:center!important;
      }
      /* The biggest table this row can hold, inside a band of felt shapes.

         Before: the width was min(column, 1240px, free height * 1.6). The
         1240 cap is what bound on any real desktop -- 1235x778 in a 1486x805
         row on the window from the report -- so dragging the window wider
         changed nothing at all. A single fixed ratio has the same fault in
         the other direction: the width would then follow the height alone,
         and widening the window would still do nothing.

         So each side takes what it can up to the shape the other allows: the
         width may stretch the felt to 1.9, and the height may square it back
         to 1.6, whichever runs out first. Inside that band both drags move
         the table; outside it the extra space stays black, which is the
         right answer -- a felt at 2.4 is a corridor, not a table.

         The -50px is the felt's own vertical inset inside the frame (the
         .felt rule above), so the numbers here are the shape of the green,
         not of the wood around it. */
      /* The room the table actually has. The CSS values are a first-paint
         fallback -- 344/150 are the page's furniture at the time this was
         written, and .table-frame is hidden until p8-boot-ready anyway --
         and syncStage() below replaces them with the row's measured box, so
         a change to the topbar or the action panel cannot silently shrink
         the table again. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2{
        --p8-felt-widest:1.9;
        --p8-felt-squarest:1.6;
        --p8-stage-h:calc(100dvh - 344px);
        --p8-stage-w:calc(100vw - 40px);
        /* Everything drawn on this table is a fixed pixel size, tuned when
           the frame was 1240x775. It can be half again that now, and a seat
           plate does not grow with it. syncStage() measures the knob; 1 is
           the size everything was drawn at. */
        --p8-ui-scale:1;
        --p8-center-scale:.94;
        --p8-card-w:66px;
        --p8-card-h:92px;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2.p8-observer-mode{--p8-stage-h:calc(100dvh - 150px);}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .table-frame{
        width:min(100%,var(--p8-stage-w),calc((var(--p8-stage-h) - 50px) * var(--p8-felt-widest)))!important;
        height:min(100%,var(--p8-stage-h),calc(var(--p8-stage-w) / var(--p8-felt-squarest) + 50px))!important;
        aspect-ratio:auto!important;
        min-height:0!important;max-height:100%!important;
        margin-inline:auto!important;
        /* The table photo is the table -- .felt carries no background of its
           own here, it only positions the seats -- and v038 paints it at
           "100vw by the stage height, pushed up 50px". Both are true on a
           phone, where the frame is the full width of the window. On desktop
           the frame is narrower than the window, so the picture was drawn
           wider than the box that clips it and both ends of the table were
           cut clean off at the frame's edge -- 32px a side on the window from
           the report, and more the wider the window got, because the picture
           follows the window while the table follows its row. Same story
           above: -50px took the top rail with it.

           Fit it to the frame, which is the box it is a picture of. Nothing
           is cut at any size.

           The picture is the landscape table now (1618x972, ratio 1.67).
           The frame's own ratio floats between 1.5 and 1.78 across the band
           above, so it is stretched by under a tenth at either end -- on a
           photograph of wood and baize that is not a thing anyone can see,
           and it beats cropping the ends off. */
        background-image:url("/static/assets/poker8-v2-table-desktop.webp")!important;
        background-size:100% 100%!important;
        background-position:center!important;
        background-repeat:no-repeat!important;
      }
      /* Everyone else's confirmation.

         v038 gates the tick on p8-can-ready, which is about *this* viewer's
         own ready button -- so watching a table, or sitting a hand out,
         showed nobody's readiness at all, on a screen with room for it.
         syncAllSeatReadyMarks only marks seats between hands and never the
         hero's own, so this cannot leak into a running hand. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .avatar-wrap.v038-viewer-ready .v038-ready-mark{
        display:grid!important;
      }

      /* The offer card is only a fallback if the header buttons are missing. */
      body.v014.poker8-desktop-v2 .felt > #readyPanel{
        position:absolute!important;z-index:76!important;
        left:50%!important;right:auto!important;bottom:auto!important;
        transform:translateX(-50%) scale(var(--p8-ui-scale))!important;
        transform-origin:top center!important;
        margin:0!important;grid-template-columns:minmax(0,1fr) auto!important;
        gap:3px 12px!important;text-align:left!important;
        border:1px solid rgba(64,237,167,.48)!important;border-radius:14px!important;
        background:linear-gradient(135deg,rgba(4,31,20,.94),rgba(7,16,15,.96))!important;
        box-shadow:0 12px 28px rgba(0,0,0,.42),0 0 20px rgba(44,247,169,.10)!important;
      }
      /* The offer card is the header's job here, so it shows only if the
         header never took the buttons -- the same fallback the hide in
         online-table.js is gated on. Then it keeps the phone's own place,
         the middle of the felt. */
      body.v014.poker8-desktop-v2 .felt > #readyPanel{
        top:52%!important;width:min(46%,380px)!important;padding:12px 14px!important;
      }
      body.v014.poker8-desktop-v2:not(.p8-desktop-header-actions) .felt > #readyPanel{
        display:grid!important;
      }
      /* No reservation strip in the bar. It said what the header's own
         "В очереди" button says, beside that button, and cost the bar the
         300px that pushed its controls onto a second row. */
      body.v014.poker8-desktop-v2 .felt > #readyPanel strong{grid-column:1!important;color:#a8ffd4!important;font-size:16px!important;line-height:1.1!important;}
      body.v014.poker8-desktop-v2 .felt > #readyPanel span{grid-column:1!important;color:#c3d7cc!important;font-size:12px!important;line-height:1.3!important;}
      body.v014.poker8-desktop-v2 .felt > #readyPanel button{grid-column:2!important;grid-row:1 / span 2!important;align-self:center!important;min-height:42px!important;padding:9px 14px!important;white-space:nowrap!important;}

      /* Over the felt rather than beside it, and only once asked for. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatPanel{
        display:none!important;
        position:fixed!important;top:96px!important;right:20px!important;bottom:20px!important;
        left:auto!important;width:380px!important;height:auto!important;z-index:140!important;
        margin:0!important;border-radius:18px!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatPanel.is-open{
        display:flex!important;flex-direction:column!important;
      }
      /* The felt sat 66px inside the frame on the left and 12px past it on the
         right -- a twelve-pixel border counted outside the box, plus whatever
         centred it against something else. Pin it to the frame's own box. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .felt{
        box-sizing:border-box!important;width:100%!important;
        margin-left:0!important;margin-right:0!important;
        min-width:0!important;
        /* left:38px is the phone layout nudging the felt clear of its rail.
           On a centred desktop frame it just pushed the table off the right
           edge -- 41px in on the left, 37px past it on the right. */
        left:0!important;right:auto!important;
      }
      /* An observer's action panel is hidden; without matching the specificity
         of the desktop .sidebar rule above, it kept its grid box. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2.p8-observer-mode .sidebar{display:none!important}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .history-card{display:none!important;}
      /* Was a docked column in the grid's "chat" area. It is an overlay now
         (see the rule further up): the permanent 330px card was holding the
         width that kept the table square. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatPanel{
        grid-area:auto!important;min-height:0!important;
        display:none!important;flex-direction:column!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatPanel.is-open{display:flex!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatMessages{flex:1 1 auto!important;min-height:0!important;overflow-y:auto!important;}
      /* The old 214px action row was the page jump: observer/seated state
         changed that row and therefore the table's own height. The real panel
         is reparented into .table-frame above; the leftover sidebar has no
         layout job and the frame never gives space back to it. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2{--p8-hud-h:0px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .sidebar{display:none!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .table-frame > .action-panel{
        position:absolute!important;z-index:70!important;inset:0!important;
        width:100%!important;height:100%!important;min-height:0!important;
        margin:0!important;padding:0!important;transform:none!important;
        border:0!important;border-radius:0!important;background:transparent!important;
        box-shadow:none!important;backdrop-filter:none!important;overflow:visible!important;
        pointer-events:none!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .action-panel > :is(.panel-kicker,h2,.hint,.turn-meta,.mobile-turn-tools,.mobile-auto-action){display:none!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #actionButtons{
        display:contents!important;position:static!important;inset:auto!important;
        width:auto!important;height:auto!important;padding:0!important;background:transparent!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #actionButtons .action-slot{
        position:absolute!important;z-index:4!important;
        width:clamp(128px,18%,176px)!important;max-width:none!important;
        min-height:46px!important;height:46px!important;padding:7px 10px!important;
        border-radius:11px!important;font-size:12px!important;pointer-events:auto!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #actionButtons .action-slot[data-edge="left"]{left:16px!important;right:auto!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #actionButtons .action-slot[data-edge="right"]{right:16px!important;left:auto!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #actionButtons .action-slot[data-slot="top"]{top:auto!important;bottom:70px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #actionButtons .action-slot[data-slot="bottom"]{top:auto!important;bottom:16px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .v038-action-amount{font-size:12px!important;}

      /* Sizing is transient, like the phone: no permanent preset/slider block.
         It opens over the felt and therefore cannot resize the page. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #sizingWrap{
        display:none!important;position:absolute!important;z-index:8!important;
        left:50%!important;right:auto!important;top:50%!important;bottom:auto!important;
        width:min(360px,calc(100% - 40px))!important;height:auto!important;
        transform:translate(-50%,-50%)!important;padding:10px!important;
        border:1px solid rgba(71,255,190,.42)!important;border-radius:16px!important;
        background:rgba(0,8,5,.97)!important;box-shadow:0 18px 42px rgba(0,0,0,.60),0 0 28px rgba(44,247,169,.18)!important;
        pointer-events:auto!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2.v038-sizing-open #sizingWrap{display:block!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2.v038-sizing-open #actionButtons .action-slot{visibility:hidden!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .mobile-sizing-head{display:flex!important;align-items:center!important;justify-content:center!important;min-height:40px!important;margin-bottom:7px!important;position:relative!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #mobileSizingAmount{font-size:24px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #mobileSizingCancel{display:block!important;position:absolute!important;right:0!important;top:0!important;width:40px!important;height:40px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .quick-sizes{position:static!important;display:grid!important;grid-template-columns:repeat(5,1fr)!important;height:auto!important;margin:0!important;gap:5px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .quick-sizes button{height:40px!important;min-height:40px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .bet-slider-row{position:static!important;display:block!important;height:30px!important;margin:7px 0 5px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #mobileSizingConfirm{display:block!important;width:100%!important;min-height:44px!important;}
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #mobileBetRail{display:none!important;}

      /* Nothing to press: the hand is running and this seat is not in it. */
      body.v014.poker8-desktop-v2.p8-not-in-hand #actionButtons,
      body.v014.poker8-desktop-v2.p8-not-in-hand #sizingWrap,
      body.v014.poker8-desktop-v2.p8-not-in-hand #mobileAutoActionBar{display:none!important;}
      /* The stage is a grid row here, not a subtraction from the viewport. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2{
        --p8-bottom-reserve:0px!important;
        --table-stage-h:100%!important;
      }
  `;

  /* The table row's own box, handed to the CSS above. Reading it beats
     subtracting a list of remembered heights from the viewport: the topbar,
     the gap and the action panel are already in it, and so is whatever
     replaces them later. No feedback loop -- the row is a 1fr grid track, so
     its size does not depend on the frame it sizes. */
  /* The size everything on this table was drawn at. */
  const BASE = { w: 1240, h: 775 };
  const CAP = 1.35;
  /* And a floor. The factor only ever grew, so a window smaller than the size
     these pixel values were drawn at got the full-size furniture on a smaller
     table -- measured at 1067x632: a 964x458 felt carrying 88px heads, a
     centre cluster 54% of the felt's height, and the top seats' name plates
     lying across the pot's chips.

     0.82 rather than lower because the text goes with it: a 10px name is 8px
     there, and the next step down stops being readable before it stops being
     cramped. */
  const FLOOR = 0.82;

  /* How much bigger the table is than the size its pixel values were tuned
     at, by area -- a table that grew mostly in width still counts, which
     taking the smaller of the two dimensions would have thrown away.

     Worked out from .layout rather than from the frame itself, so a scale
     read off the frame cannot feed back into the thing it scales. */
  function uiScale(layout) {
    const row = layout.height;
    const width = Math.min(layout.width, (row - 50) * 1.9);
    const height = Math.min(row, width / 1.6 + 50);
    const grown = Math.sqrt((width * height) / (BASE.w * BASE.h));
    return Math.min(CAP, Math.max(FLOOR, grown));
  }

  function syncStage() {
    const column = document.querySelector(".left-column");
    if (!column) return;
    const box = column.getBoundingClientRect();
    if (box.height < 1 || box.width < 1) return;
    document.body.style.setProperty("--p8-stage-h", `${Math.round(box.height)}px`);
    document.body.style.setProperty("--p8-stage-w", `${Math.round(box.width)}px`);
    const layout = document.querySelector(".layout")?.getBoundingClientRect();
    if (layout?.height > 1) {
      // Desktop's knob, and only desktop's. Before it could shrink, "always
      // at least 1" kept it harmless on a phone by accident; now that it can
      // go below, the phone has to be said out loud -- a factor sitting there
      // for nobody to read is how the next layer reads it.
      const desktop = document.body.classList.contains("poker8-desktop-v2");
      document.body.style.setProperty(
        "--p8-ui-scale", desktop ? uiScale(layout).toFixed(3) : "1");
    }
  }

  document.head.appendChild(style);
  /* And again once everything else has had its say.

     This file is a static tag in index.html, so it runs before every layer
     component-ui and v037 append -- which is why its rules have needed three
     classes to beat v038's two, and why two of this week's faults were pure
     source order (the table picture sized to the window, the page's floor).
     Re-appending the same element moves it to the end of <head>, so desktop
     geometry is simply last, without moving the script itself: the class
     this file sets on <body> still lands before anything reads it.

     Verified before doing it, by making the same move by hand on the live
     table and diffing every computed property: 3 differences across 25
     elements, all of them the .action-panel claim above, and 0 once that
     claim was dropped. */
  window.addEventListener("load", () => document.head.appendChild(style), { once: true });
  syncDesktopMode();
  syncStage();
  if (window.ResizeObserver) {
    const watch = new ResizeObserver(syncStage);
    for (const name of [".left-column", ".layout"]) {
      const node = document.querySelector(name);
      if (node) watch.observe(node);
    }
  }
  window.addEventListener("resize", () => { syncDesktopMode(); syncStage(); }, { passive: true });
})();
