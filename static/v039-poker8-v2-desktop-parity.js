(() => {
  "use strict";

  const DESKTOP_QUERY = "(min-width: 781px)";

  function syncDesktopMode() {
    document.body.classList.toggle(
      "poker8-desktop-v2",
      window.matchMedia?.(DESKTOP_QUERY)?.matches ?? false,
    );
  }

  const style = document.createElement("style");
  style.id = "v039-poker8-v2-desktop-parity-style";
  style.textContent = `
    /* Keep the right-hand mobile clusters inside the felt safe area. */
    @media (max-width:780px){
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:86.5%!important;top:24%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:84.5%!important;top:59%!important;}
    }

    /* Desktop inherits the same dark wood, green felt and neon-seat language as mobile. */
    @media (min-width:781px){
      body.v014.poker8-desktop-v2{
        --p8-wood-dark:#0c0503;
        --p8-wood-mid:#51270f;
        --p8-felt:#003b24;
        --seat-0-x:50%; --seat-0-y:80%;
        --seat-1-x:17%; --seat-1-y:70%;
        --seat-2-x:13%; --seat-2-y:39%;
        --seat-3-x:30%; --seat-3-y:17%;
        --seat-4-x:70%; --seat-4-y:17%;
        --seat-5-x:83%; --seat-5-y:39%;
        --seat-6-x:80%; --seat-6-y:70%;
        color:#eafff6!important;
        background:
          radial-gradient(ellipse at 50% 26%,rgba(15,95,58,.16),transparent 43%),
          repeating-linear-gradient(96deg,#000000 0 8px,#180b05 9px 17px,#0c0503 18px 27px)!important;
      }

      body.v014.poker8-desktop-v2 .mobile-game-header,
      body.v014.poker8-desktop-v2 #mobileDrawer,
      body.v014.poker8-desktop-v2 #mobileDrawerBackdrop{display:none!important;}
      body.v014.poker8-desktop-v2 .room-ambience{position:fixed!important;inset:0!important;width:100%!important;height:100dvh!important;opacity:.28!important;filter:saturate(.68) brightness(.55)!important;pointer-events:none!important;z-index:0!important;}
      body.v014.poker8-desktop-v2 .app-shell{position:relative!important;z-index:1!important;width:min(1720px,calc(100% - 40px))!important;margin:0 auto!important;}
      body.v014.poker8-desktop-v2 .topbar{
        min-height:74px!important;padding:13px 18px!important;
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
      }
      body.v014.poker8-desktop-v2 .mobile-header-utility{display:flex!important;gap:8px!important;align-items:center!important;}
      /* Room to breathe that a 374px phone could not spare: the labels stop
         being clipped to an ellipsis and the hit target grows to match the
         42px chat/hint squares beside them. */
      body.v014.poker8-desktop-v2 .mobile-header-seat-actions button{
        min-height:42px!important;padding:9px 14px!important;
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
      body.v014.poker8-desktop-v2 .panel,
      body.v014.poker8-desktop-v2 .history-card,
      body.v014.poker8-desktop-v2 .online-chat-panel{
        border-color:rgba(64,237,167,.18)!important;
        background:linear-gradient(180deg,rgba(7,16,15,.94),rgba(0,0,0,.96))!important;
        box-shadow:0 12px 26px rgba(0,0,0,.34),inset 0 1px rgba(142,255,209,.03)!important;
      }

      body.v014.poker8-desktop-v2 .table-frame{
        height:clamp(620px,calc(100dvh - 156px),860px)!important;
        min-height:620px!important;padding:8px!important;overflow:hidden!important;
        border:1px solid rgba(44,255,172,.13)!important;border-radius:28px!important;
        background:
          linear-gradient(90deg,rgba(0,0,0,.58),transparent 17%,transparent 83%,rgba(0,0,0,.58)),
          url("/static/assets/poker8-v2-table-mobile.webp") center/cover no-repeat,
          repeating-linear-gradient(96deg,#000000 0 8px,#180b05 9px 17px,#0c0503 18px 27px)!important;
        box-shadow:0 24px 54px rgba(0,0,0,.55),inset 0 0 0 1px rgba(255,194,114,.05)!important;
      }
      body.v014.poker8-desktop-v2 .felt{
        width:calc(100% - 76px)!important;height:calc(100% - 50px)!important;inset:25px 38px!important;
        border:2px solid rgba(35,255,159,.84)!important;border-radius:49% / 38%!important;
        background:radial-gradient(ellipse at 50% 45%,rgba(0,74,43,.90),rgba(0,35,22,.98) 68%,rgba(7,16,15,.99))!important;
        box-shadow:inset 0 0 0 8px rgba(0,8,5,.57),inset 0 0 44px rgba(0,0,0,.68),0 0 22px rgba(38,255,167,.34)!important;
      }
      body.v014.poker8-desktop-v2 .felt::before{display:block!important;inset:16px!important;border:1px solid rgba(44,255,172,.34)!important;border-radius:inherit!important;background:none!important;}
      body.v014.poker8-desktop-v2 .felt::after{display:none!important;}
      body.v014.poker8-desktop-v2 .table-glow{display:block!important;inset:16%!important;background:radial-gradient(ellipse,rgba(25,179,101,.16),transparent 68%)!important;}

      /* $= (suffix match): same spectator-position gap as v038 -- a
         spectator's "spectator-N" dataset (v040) needs to hit these too. */
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="0"]{left:var(--seat-0-x)!important;top:var(--seat-0-y)!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="1"]{left:var(--seat-1-x)!important;top:var(--seat-1-y)!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="2"]{left:var(--seat-2-x)!important;top:var(--seat-2-y)!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="3"]{left:var(--seat-3-x)!important;top:var(--seat-3-y)!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="4"]{left:var(--seat-4-x)!important;top:var(--seat-4-y)!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="5"]{left:var(--seat-5-x)!important;top:var(--seat-5-y)!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat$="6"]{left:var(--seat-6-x)!important;top:var(--seat-6-y)!important;}
      body.v014.poker8-desktop-v2 .seat{width:128px!important;height:140px!important;min-height:0!important;z-index:20!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat="0"]{width:144px!important;height:150px!important;z-index:28!important;}
      body.v014.poker8-desktop-v2 .seat-card{width:100%!important;height:100%!important;min-height:0!important;padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;overflow:visible!important;}
      body.v014.poker8-desktop-v2 .avatar-wrap{position:absolute!important;left:50%!important;top:2px!important;transform:translateX(-50%)!important;width:88px!important;height:88px!important;z-index:4!important;}
      body.v014.poker8-desktop-v2 .player-avatar{width:88px!important;height:88px!important;border:2px solid hsl(var(--avatar-hue) 95% 68%)!important;background:radial-gradient(circle at 50% 30%,hsl(var(--avatar-hue) 62% 44% / .46),transparent 31%),radial-gradient(circle at 50% 78%,#07100f 0 42%,#000000 70%)!important;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 20px hsl(var(--avatar-hue) 92% 56% / .42),inset 0 -12px 20px rgba(0,0,0,.52)!important;}
      body.v014.poker8-desktop-v2 .avatar-wrap::before,body.v014.poker8-desktop-v2 .avatar-wrap::after{display:none!important;}
      body.v014.poker8-desktop-v2 .seat-identity{position:absolute!important;z-index:6!important;left:50%!important;top:82px!important;transform:translateX(-50%)!important;width:116px!important;min-height:43px!important;padding:7px 8px 6px!important;border:1px solid hsl(var(--avatar-hue) 88% 58% / .72)!important;border-radius:10px!important;background:linear-gradient(180deg,rgba(0,0,0,.98),rgba(0,0,0,.995))!important;box-shadow:0 0 14px hsl(var(--avatar-hue) 88% 55% / .22),0 8px 16px rgba(0,0,0,.64)!important;text-align:center!important;}
      body.v014.poker8-desktop-v2 .seat-name{max-width:82px!important;font-size:10px!important;line-height:1!important;}
      body.v014.poker8-desktop-v2 .seat-stack{margin-top:4px!important;font-size:15px!important;line-height:1!important;color:hsl(var(--avatar-hue) 95% 68%)!important;}
      body.v014.poker8-desktop-v2 .bot-level,body.v014.poker8-desktop-v2 .position-chip{display:none!important;}
      body.v014.poker8-desktop-v2 .player-cards{position:absolute!important;z-index:3!important;left:50%!important;top:-80px!important;bottom:auto!important;transform:translateX(-50%)!important;min-height:0!important;gap:3px!important;pointer-events:none!important;}
      body.v014.poker8-desktop-v2 .player-cards .card.back{width:34px!important;height:47px!important;border-color:hsl(var(--avatar-hue) 95% 72% / .82)!important;background:repeating-linear-gradient(45deg,hsl(var(--avatar-hue) 62% 38% / .76) 0 3px,hsl(var(--avatar-hue) 62% 16% / .98) 3px 6px)!important;box-shadow:inset 0 0 0 2px rgba(0,0,0,.50),0 0 10px hsl(var(--avatar-hue) 94% 58% / .30)!important;}
      /* Same avatar size and plate as every other seat -- the hero used to be
         smaller than everyone else here, which read as a rendering bug. Only
         the "this is you" border colour stays hero-specific. */
      body.v014.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-avatar{border-color:#35bfff!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-cards{top:-30px!important;z-index:9!important;gap:4px!important;}
      body.v014.poker8-desktop-v2 .seat[data-visual-seat="0"] .player-cards .card{width:40px!important;height:56px!important;border-color:#56c8ff!important;box-shadow:0 0 12px rgba(47,184,255,.46),0 5px 9px rgba(0,0,0,.54)!important;}
      body.v014.poker8-desktop-v2 .dealer-button{right:-6px!important;bottom:28px!important;z-index:12!important;}

      body.v014.poker8-desktop-v2 .table-center{transform:translate(-50%,-50%) scale(.94)!important;z-index:12!important;}
      /* Same on desktop: the player stays lit, the cards go. */
      body.v014.poker8-desktop-v2 .seat-card.folded{opacity:1!important;filter:none!important;}
      body.v014.poker8-desktop-v2 .seat-card.folded .player-cards{display:none!important;}
      body.v014.poker8-desktop-v2 .seat-card.folded .seat-identity{background:linear-gradient(180deg,rgba(9,10,10,.98),rgba(0,0,0,.995))!important;}
      body.v014.poker8-desktop-v2 .seat-identity{backdrop-filter:blur(5px)!important;}
      body.v014.poker8-desktop-v2 .player-status{
        position:absolute!important;z-index:10!important;left:auto!important;right:5px!important;top:7px!important;
        width:auto!important;height:21px!important;min-height:21px!important;max-height:21px!important;box-sizing:border-box!important;padding:4px 6px!important;
        overflow:hidden!important;display:flex!important;align-items:center!important;transform:none!important;writing-mode:horizontal-tb!important;white-space:nowrap!important;
        border:1px solid rgba(255,142,128,.54)!important;border-radius:999px!important;
        background:rgba(22,8,9,.92)!important;color:#ffb8ad!important;
        font-size:10px!important;line-height:1!important;letter-spacing:.06em!important;
        box-shadow:0 4px 10px rgba(0,0,0,.42)!important;
      }
      body.v014.poker8-desktop-v2 .board-cards .card{width:58px!important;height:80px!important;border-color:rgba(98,255,170,.82)!important;background:linear-gradient(150deg,#07100f,#000000)!important;box-shadow:0 0 12px rgba(35,255,159,.32),0 6px 11px rgba(0,0,0,.58)!important;}
      body.v014.poker8-desktop-v2 .pot-total{border-color:rgba(60,225,150,.26)!important;background:rgba(4,31,20,.78)!important;box-shadow:0 5px 13px rgba(0,0,0,.42)!important;}
      /* v019-center-polish sets display:flex!important on the same selector
         family, so the hide needs !important here to actually win. */
      body.v014.poker8-desktop-v2.p8-no-pot .pot-total{display:none!important;}
      body.v014.poker8-desktop-v2 .pot-total strong{color:#eafff6!important;font-size:27px!important;}
      body.v014.poker8-desktop-v2 .street-badge{border-color:rgba(63,244,173,.30)!important;background:rgba(10,26,18,.82)!important;color:#b8ffda!important;}
      body.v014.poker8-desktop-v2 .online-state-panel{border-color:rgba(63,244,173,.34)!important;background:rgba(4,31,20,.92)!important;box-shadow:0 0 20px rgba(44,247,169,.14)!important;}
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

         Two columns instead: the table and its controls on the left, chat
         beside them full height. The felt keeps a sane width and centres. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .layout{
        display:grid!important;
        grid-template-columns:minmax(0,1fr) 330px!important;
        grid-template-rows:minmax(0,1fr) auto!important;
        grid-template-areas:"table chat" "actions chat"!important;
        gap:14px!important;
        height:calc(100dvh - 76px)!important;
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
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .table-frame{
        width:min(100%,940px)!important;height:100%!important;margin-inline:auto!important;
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
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatPanel{
        grid-area:chat!important;height:100%!important;min-height:0!important;
        display:flex!important;flex-direction:column!important;
      }
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 #chatMessages{flex:1 1 auto!important;min-height:0!important;overflow-y:auto!important;}
      /* The panel keeps the mobile arrangement -- a fixed height with its
         controls absolutely placed inside it. Making it position:static and
         height:auto collapsed it to sixteen pixels, because absolute children
         contribute nothing to an auto height. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .sidebar{
        grid-area:actions!important;width:min(100%,940px)!important;margin-inline:auto!important;
        height:var(--p8-hud-h)!important;
        /* One column. The other four panels here -- solver, stats, saved
           tables, format -- are trainer leftovers, hidden on a network table,
           and their empty tracks squeezed the action panel into a quarter of
           the bar. */
        grid-template-columns:minmax(0,1fr)!important;
      }
      /* The controls inside are placed absolutely against phone widths, so on
         a 940px bar they huddled in a 207px column against the left edge.
         Give them a box their own size and centre that instead of trying to
         re-pin every one of them. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2 .action-panel{
        position:relative!important;width:min(100%,520px)!important;margin-inline:auto!important;
      }
      /* The stage is a grid row here, not a subtraction from the viewport. */
      body.v014.poker8-v2-sixmax.poker8-desktop-v2{
        --p8-bottom-reserve:0px!important;
        --table-stage-h:100%!important;
      }
  `;

  document.head.appendChild(style);
  syncDesktopMode();
  window.addEventListener("resize", syncDesktopMode, { passive: true });
})();
