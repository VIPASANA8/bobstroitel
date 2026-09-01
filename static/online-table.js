(() => {
  const tableId = new URLSearchParams(location.search).get("table");
  if (!tableId) return;

  window.Poker8OnlineTable = true;

  const tablePageStyle = document.createElement("style");
  tablePageStyle.textContent = `
    .poker8-online .online-state-panel{display:flex;align-items:center;gap:14px;margin:0 0 12px;padding:12px 14px;border:1px solid rgba(64,237,167,.28);border-radius:14px;background:rgba(4,31,20,.82)}
    .poker8-online .online-state-panel[hidden]{display:none!important}
    .poker8-online .online-state-panel strong{color:#8ff2c0;font-size:12px}
    .poker8-online .online-state-panel span{flex:1;color:#9aada3;font-size:12px}
    .poker8-online .online-state-panel button{padding:10px 14px;font-size:15px;border:1px solid rgba(64,237,167,.5);border-radius:10px;background:#0a3b2b;color:#b8ffda;font-weight:850;cursor:pointer}
    .poker8-online .online-connection-status{position:fixed;right:14px;bottom:12px;z-index:1000;padding:5px 9px;border:1px solid rgba(64,237,167,.28);border-radius:999px;background:rgba(7,16,15,.82);color:#91e8ba;font:700 10px monospace}
    .poker8-online .online-chat-panel{display:block;grid-column:2;align-self:start;margin-top:0;padding:16px;border:1px solid rgba(64,237,167,.28);border-radius:18px;background:rgba(10,26,18,.86)}
    .poker8-online .online-chat-panel h2{margin:0 0 12px;color:#91e8ba;font-size:15px}
    .poker8-online #chatMessages{max-height:240px;overflow:auto;color:#c3d7cc;font-size:12px;line-height:1.6}
    .poker8-online #chatForm{display:flex;gap:8px;margin-top:12px}
    /* Chat formatting, ported from board2 with the renderer. */
    .poker8-online .p8-chat-row{line-height:1.45;word-break:break-word}
    .poker8-online .p8-chat-code{padding:1px 4px;border-radius:4px;background:rgba(120,255,200,.10);border:1px solid rgba(120,255,200,.18);font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.92em}
    .poker8-online .p8-chat-block{margin:5px 0;padding:7px 9px;border-radius:8px;overflow-x:auto;background:rgba(7,16,15,.82);border:1px solid rgba(120,255,200,.16)}
    .poker8-online .p8-chat-block code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.9em;white-space:pre}
    .poker8-online .p8-chat-link{color:#7dffd0;text-decoration:underline;text-underline-offset:2px}
    /* Blurred rather than blanked: the line keeps its shape, so the length of
       the secret is not readable from the gap it leaves. */
    .poker8-online .p8-chat-spoiler{border-radius:4px;background:rgba(120,255,200,.10);cursor:pointer;filter:blur(4px);transition:filter .18s ease}
    .poker8-online .p8-chat-spoiler.is-revealed{filter:none;cursor:auto;background:transparent}
    .poker8-online .p8-chat-toolbar{display:flex;gap:5px;padding:4px 0 2px}
    .poker8-online .p8-chat-toolbar button{min-width:26px;height:24px;padding:0 6px;border-radius:6px;border:1px solid rgba(120,255,200,.20);background:rgba(6,22,17,.72);color:#c9ffe3;font-size:10px;font-weight:800;cursor:pointer;line-height:1}
    .poker8-online .p8-chat-toolbar button:hover{border-color:rgba(120,255,200,.44)}
    @media (prefers-reduced-motion:reduce){.poker8-online .p8-chat-spoiler{transition:none}}
    .poker8-online #chatInput{min-width:0;flex:1;padding:11px;border:1px solid #294d3e;border-radius:10px;background:#07100f;color:#f4f5ee}
    .poker8-online #chatForm button{padding:0 15px;border:0;border-radius:10px;background:#91e8ba;color:#041f14;font-weight:900}
    .poker8-online :is(.chat-window-tools,.chat-resize,.chat-latest,.chat-send-status,.chat-compose-hint,#chatDesktopInput,.p8-chat-time){display:none}
    .poker8-online :is(.p8-chat-meta,.p8-chat-text){display:contents}
    .poker8-online .local-only-control,.poker8-online .solver-panel,.poker8-online .stats-panel,.poker8-online .saved-tables-panel,.poker8-online .format-panel{display:none!important}
    /* Local-trainer controls that are wrong on ANY online table, at ANY
       width. They were only ever hidden by viewport -- .seat-edit solely in
       mobile.css:77, whose <link> is gated to max-width:780px, and
       .table-count solely inside style.css's own max-width:780px blocks --
       so on desktop a "•••" seat-editor sat on every bot and the header
       still read "4 / 7 игроков" (tables are six-max; the 7 is a literal
       left over from the seven-seat era). Mode is the right key, not width:
       these must stay above the @media(max-width:780px) block below, and
       they must stay scoped to .poker8-online so local mode keeps them. */
    .poker8-online .seat-edit,.poker8-online .table-count{display:none!important}
    /* The drawer's three trainer controls: online the server deals, runs the
       next hand and never pauses, so all three did nothing here. Hidden by
       mode rather than deleted -- the local trainer still needs them -- and
       the divider goes with them, or it would open the drawer. */
    .poker8-online #mobileDrawerNewHand,.poker8-online #mobileDrawerInfinite,
    .poker8-online #mobileDrawerPause,.poker8-online .mobile-drawer-divider{display:none!important}
    /* Same reasoning for the identity block: an online table is not
       "ЛОКАЛЬНЫЙ ТРЕНАЖЁР", and the build tag beside it is meaningless to a
       player. The markup stays for local mode; Phase 2 fills this space
       with the table's own name and blinds. */
    .poker8-online .topbar .brand-wrap .eyebrow,.poker8-online .topbar h1{display:none!important}
    .poker8-online .mobile-drawer-divider{height:1px;margin:8px 0;border:0;background:rgba(126,202,165,.20)}
    .poker8-online .mobile-drawer .network-table-action{display:block;width:100%;margin:6px 0;padding:12px;border:1px solid rgba(95,237,170,.34);border-radius:10px;background:rgba(4,31,20,.84);color:#c9ffe3;text-align:left;font-weight:850}
    /* [hidden] is only display:none in the user-agent sheet, so the rule above
       -- which does set display -- silently outranked it and every button the
       drawer meant to hide stayed on screen: "Занять место" while already
       seated, and both room-owner controls to people who own nothing. */
    .poker8-online .mobile-drawer .network-table-action[hidden]{display:none}
    .poker8-online .mobile-drawer .network-table-action.danger{border-color:rgba(255,125,111,.34);color:#ffc1b6;background:rgba(52,14,12,.58)}
    .poker8-online.p8-observer-mode #actionButtons,.poker8-online.p8-observer-mode #sizingWrap,.poker8-online.p8-observer-mode .mobile-turn-tools,.poker8-online.p8-observer-mode #mobileAutoActionBar,.poker8-online.p8-observer-mode .v038-hud-summary{display:none!important}
    .poker8-online.p8-observer-mode #mobileTimerCard,.poker8-online.p8-observer-mode #mobileSelectedCard{display:none!important}
    .poker8-online.p8-observer-mode .action-panel{border-color:rgba(64,237,167,.34)}
    /* An observer has nothing to press, so the panel is an empty framed box
       520x214 sitting under the table -- and on desktop it also kept the table
       from using the room it left behind. This lived inside the phone's media
       query, so only phones ever got it. */
    .poker8-online.p8-observer-mode{--p8-hud-h:0px!important;--p8-bottom-reserve:0px!important}
    .poker8-online.p8-observer-mode .sidebar,
    .poker8-online.p8-observer-mode .action-panel{display:none!important}
    .p8-funds-dialog{width:min(92vw,360px);padding:22px 20px 18px;border:1px solid rgba(64,237,167,.42);border-radius:16px;background:linear-gradient(160deg,#031b13,#07100f);color:#dcf7e8;box-shadow:0 24px 70px rgba(0,0,0,.62)}
    .p8-funds-dialog::backdrop{background:rgba(0,8,5,.72)}
    .p8-funds-dialog h2{margin:0 0 12px;color:#ffd9a8;font:800 20px/1.15 Inter,ui-sans-serif,system-ui;letter-spacing:-.01em}
    .p8-funds-lead{margin:0 0 12px;color:#d6ece0;font-size:12px;line-height:1.45}
    .p8-funds-lead[hidden]{display:none}
    .p8-funds-again{width:100%;padding:13px;border:0;border-radius:11px;background:linear-gradient(120deg,#3defb0,#2aa87c);color:#04211c;font:800 15px/1 Inter,ui-sans-serif,system-ui;cursor:pointer}
    .p8-funds-again[hidden]{display:none}
    .p8-funds-offer[hidden]{display:none}
    .p8-funds-sums{margin:0 0 18px;color:#a9c6b8;font-size:12px;line-height:1.75}
    .p8-funds-sums b{color:#eaffef;font-size:15px;font-variant-numeric:tabular-nums}
    .p8-funds-offer{display:grid;gap:8px;padding:14px;border:1px solid rgba(86,200,255,.34);border-radius:12px;background:rgba(6,26,36,.72)}
    .p8-funds-offer strong{color:#bde9ff;font-size:15px}
    .p8-funds-offer span{color:#8fb3c4;font-size:12px;line-height:1.35}
    .p8-funds-offer button{margin-top:2px;padding:12px;border:0;border-radius:10px;background:linear-gradient(120deg,#2fd6a0,#35c6ff);color:#04211c;font:800 12px/1 Inter,ui-sans-serif,system-ui;cursor:pointer}
    .p8-funds-offer button:disabled{background:rgba(120,150,150,.26);color:#8ca59c;cursor:default}
    .p8-funds-close{width:100%;margin-top:14px;padding:12px;border:1px solid rgba(95,237,170,.34);border-radius:10px;background:rgba(4,31,20,.84);color:#c9ffe3;font:800 12px/1 Inter,ui-sans-serif,system-ui;cursor:pointer}
    /* Same mint tokens as .p8-funds-dialog just above -- this is the same
       kind of modal (a stop on the way into a seat), not a new colour. */
    .p8-buyin-dialog{width:min(92vw,340px);padding:22px 20px 18px;border:1px solid rgba(64,237,167,.42);border-radius:16px;background:linear-gradient(160deg,#031b13,#07100f);color:#dcf7e8;box-shadow:0 24px 70px rgba(0,0,0,.62)}
    .p8-buyin-dialog::backdrop{background:rgba(0,8,5,.72)}
    .p8-buyin-dialog h2{margin:0 0 6px;color:#eaffef;font:800 20px/1.15 Inter,ui-sans-serif,system-ui;letter-spacing:-.01em}
    .p8-buyin-note{margin:0 0 18px;color:#a9c6b8;font-size:12px;line-height:1.45}
    .p8-buyin-value{margin:0 0 10px;color:#eaffef;font:800 27px/1 Inter,ui-sans-serif,system-ui;font-variant-numeric:tabular-nums;text-align:center}
    .p8-buyin-value span{margin-left:6px;color:#8ff2c0;font-size:12px;font-weight:800}
    .p8-buyin-dialog input[type="range"]{width:100%;margin:0 0 20px;accent-color:#3defb0}
    .p8-buyin-actions{display:flex;gap:8px}
    .p8-buyin-actions button{flex:1;padding:13px;border:0;border-radius:11px;font:800 15px/1 Inter,ui-sans-serif,system-ui;cursor:pointer}
    .p8-buyin-actions [data-cancel]{background:rgba(4,31,20,.84);border:1px solid rgba(95,237,170,.34);color:#c9ffe3}
    .p8-buyin-actions [data-confirm]{background:linear-gradient(120deg,#3defb0,#2aa87c);color:#04211c}
    .poker8-online.p8-action-pending #actionButtons{opacity:.62;pointer-events:none;filter:saturate(.72)}
    @media(max-width:780px){
      .poker8-online .felt > .online-state-panel{position:absolute;left:50%;top:59%;right:auto;bottom:auto;z-index:76;width:min(84vw,348px);margin:0;padding:10px 12px;transform:translate(-50%,-50%);display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 12px;border-color:rgba(64,237,167,.48);background:linear-gradient(135deg,rgba(4,31,20,.94),rgba(7,16,15,.96));box-shadow:0 12px 28px rgba(0,0,0,.42),0 0 20px rgba(44,247,169,.10);transition:width 180ms ease,padding 180ms ease,top 180ms ease}
      .poker8-online .felt > .online-state-panel strong{grid-column:1;color:#a8ffd4;font-size:15px;line-height:1.1}
      .poker8-online .felt > .online-state-panel span{grid-column:1;color:#c3d7cc;font-size:10px;line-height:1.25}
      .poker8-online .felt > .online-state-panel button{grid-column:2;grid-row:1 / span 2;align-self:center;min-height:42px;padding:9px 12px;white-space:nowrap}
      /* Nothing to press while the seat is only pending: a full card sitting over
         the felt just to say "please wait" hides the table for no reason. Collapse
         it to a slim strip near the rail and hand the middle back to the game. */
      .poker8-online .felt > .online-state-panel.is-pending{top:8px;transform:translateX(-50%);width:min(78vw,300px);padding:6px 10px;grid-template-columns:1fr;box-shadow:0 6px 16px rgba(0,0,0,.36)}
      .poker8-online .felt > .online-state-panel.is-pending strong{font-size:10px}
      .poker8-online .felt > .online-state-panel.is-pending span{font-size:10px}
      .poker8-online .felt > .online-state-panel.is-pending button{display:none}
      .poker8-online .online-chat-panel{display:none!important;position:fixed;left:10px;right:10px;bottom:calc(92px + env(safe-area-inset-bottom));z-index:130;margin:0}
      /* Open means the whole page. A 200px strip over the felt was too small
         to read a conversation in and too big to ignore. */
      .poker8-online .online-chat-panel.is-open{
        display:flex!important;flex-direction:column;inset:0;left:0;right:0;top:0;bottom:0;
        /* The base rule carries align-self:start from when this was a card in
           a grid. A fixed box in a grid container with a non-stretch alignment
           shrinks to its content instead of honouring top:0 and bottom:0 -- it
           came out 375x215 in an 812px viewport. Say the height outright. */
        align-self:stretch;height:100dvh;max-height:100dvh;
        z-index:140;margin:0;padding:0;border-radius:0;border:0;
        background:linear-gradient(180deg,#021312,#07100f)
      }
      .poker8-online .online-chat-panel.is-open > h2{
        flex:none;margin:0;padding:calc(12px + env(safe-area-inset-top)) 14px 10px;
        border-bottom:1px solid rgba(120,255,200,.16);font-size:15px
      }
      /* max-height:240px comes from the docked version and survives into this
         one, leaving 440px of empty panel under the composer. */
      .poker8-online .online-chat-panel.is-open #chatMessages{
        flex:1 1 auto;min-height:0;max-height:none;overflow-y:auto;padding:12px 14px;
        display:flex;flex-direction:column;gap:7px
      }
      .poker8-online .online-chat-panel.is-open .p8-chat-toolbar{flex:none;padding:0 14px}
      .poker8-online .online-chat-panel.is-open #chatForm{
        flex:none;margin:0;padding:8px 14px calc(12px + env(safe-area-inset-bottom))
      }
      .poker8-online .chat-close{
        position:absolute;top:calc(8px + env(safe-area-inset-top));right:10px;width:34px;height:34px;
        border-radius:10px;border:1px solid rgba(120,255,200,.22);background:rgba(6,22,17,.9);
        color:#c9ffe3;font-size:20px;font-weight:800;line-height:1;cursor:pointer
      }
      /* Your turn is happening behind this. The banner sits over the chat, says
         how long is left, and is itself the way back to the table -- missing a
         hand because you were reading is the one thing a full-page chat must
         not cause. */
      .poker8-online .chat-turn-banner{
        display:none;flex:none;align-items:center;justify-content:space-between;gap:10px;
        margin:0;padding:11px 14px;border:0;width:100%;cursor:pointer;text-align:left;
        background:linear-gradient(90deg,#ffc44d,#ff9d3d);color:#20160a;
        font-weight:900;font-size:12px
      }
      .poker8-online .online-chat-panel.is-open .chat-turn-banner.is-live{display:flex}
      .poker8-online .chat-turn-banner b{font-variant-numeric:tabular-nums;font-size:15px}
      .poker8-online .chat-turn-banner.is-urgent{animation:p8ChatTurnPulse .9s ease-in-out infinite}
      @keyframes p8ChatTurnPulse{50%{filter:brightness(1.18)}}
      @media (prefers-reduced-motion:reduce){.poker8-online .chat-turn-banner.is-urgent{animation:none}}
      .poker8-online .online-connection-status{right:10px;bottom:8px}
      /* The header buttons below replace this card on mobile -- keeping both
         would mean two competing seat prompts on a screen with room for one. */
      .poker8-online #readyPanel{display:none!important}
      /* Header is position:fixed already, so this centres on the header
         itself regardless of the hamburger/utility groups' own widths --
         safe here specifically because the wider two-button pair (the one
         that overlapped chat/hint when this trick was tried for it) is
         always hidden while this class is on. */
      .poker8-online .mobile-header-seat-actions.ready-up-only{
        position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);margin:0;
      }
      /* Phone-header layout only. The pair used to butt straight up against
         the hamburger on one side and the chat/hint icons on the other --
         fine once nothing overlapped, but still touching both edges of its
         own slot; this margin is the slack. order puts the group between
         them. Both are about *this* header, so they stay width-gated --
         unlike everything under the closing brace below. */
      .poker8-online .mobile-header-seat-actions{order:1;margin:0 4px}
      /* Was .mobile-chat-button itself, back when it sat directly in the
         header next to #mobileHeaderSeatActions -- v037 and this file append
         their header items independently, so whichever ran last used to
         decide the visual order. Chat now sits inside its own utility group
         with the rankings hint (see v037's ensureChatButton); the order
         belongs on that group so it is still always last/rightmost. */
      .poker8-online .mobile-header-utility{order:2}
      .poker8-online .mobile-header-utility{margin-left:auto!important}
    }
    /* ------------------------------------------------------------------
       How the seat/utility buttons LOOK, as opposed to where the phone
       header puts them. All of this used to live inside the block above,
       so desktop -- where the very same nodes get relocated into
       .top-actions (see v039) -- inherited none of it and would have
       rendered them unstyled. Identical rules, simply no longer
       width-gated: mobile is unaffected, desktop gains them.
       ------------------------------------------------------------------ */
      .poker8-online .mobile-header-seat-actions{
        display:flex;gap:6px;min-width:0;
      }
      .poker8-online .mobile-header-seat-actions[hidden]{display:none!important}
      /* Two competing seat prompts is exactly what the phone rule above
         avoids; desktop now has the same pair, so it drops the card too --
         but only once placeHeaderActions has actually parked the buttons in
         the topbar, so a failure there leaves #readyPanel as the fallback
         rather than stranding desktop with no way to sit down. */
      .poker8-online.p8-desktop-header-actions #readyPanel{display:none!important}
      .poker8-online .mobile-header-seat-actions button{
        min-height:38px;padding:7px 8px;border:1px solid rgba(255,212,71,.42);border-radius:12px;
        background:rgba(4,31,20,.86);color:#fff6e0;font:800 10px/1 Inter,ui-sans-serif,system-ui;
        white-space:nowrap;cursor:pointer;
        /* Both labels at full width leave ~16px of slack on a 374px screen and
           none at all below ~358px. Shrinking to an ellipsis is the only
           behaviour here that degrades instead of overflowing. */
        min-width:0;overflow:hidden;text-overflow:ellipsis;
      }
      /* Fixed rather than content-width: "Занять место" swaps to "В очереди"
         and "Наблюдать" swaps to "Отменить" in the same slot (see
         syncHeaderSeatButtons), and an auto width visibly resized the whole
         pair on every click. The width is measured from the widest of those
         four labels in whatever font actually rendered -- 88px was measured
         in Inter, and a phone that falls back to its own system face draws
         the same string wider, which cut "Занять место" to "Занять ме...".
         text-align centres the shorter label instead of hugging the left. */
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat,
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve{
        width:var(--p8-seat-action-w,88px);text-align:center;
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat{
        border-color:rgba(64,237,167,.7);background:#0a3b2b;
      }
      /* "В очереди" is a state, not an offer -- it must not look pressable. */
      .poker8-online .mobile-header-seat-actions button:disabled{
        opacity:.6;cursor:default;
      }
      /* Its own colour (not just the shimmer) reads as a distinct mode from
         "Занять место", not a dimmer variant of it. */
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve{
        border-color:rgba(201,168,255,.55);background:#24103e;color:#f2e9ff;
      }
      /* A selected observer mode is a stable state, not a second call to
         action. Queueing is quieter still: one status dot says the request is
         alive without competing with the controls on the felt. */
      .poker8-online .mobile-header-seat-actions button.mode-active{
        position:relative;color:#eafff6;
      }
      .poker8-online .mobile-header-seat-actions button.mode-active:disabled{opacity:1;}
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat.mode-active{
        padding-left:18px;border-color:rgba(85,243,168,.52)!important;
        background:#0a3b2b;color:#b8ffda;box-shadow:inset 0 0 12px rgba(85,243,168,.07);
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat.mode-active::before{
        content:"";position:absolute;left:9px;top:50%;transform:translateY(-50%);
        width:6px;height:6px;border-radius:50%;background:#55f3a8;
        box-shadow:0 0 7px rgba(85,243,168,.55);
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve.mode-active{
        border-color:rgba(201,168,255,.62)!important;color:#f2e9ff;
        box-shadow:inset 0 0 12px rgba(201,168,255,.08);
      }
      /* Same green as #mobileHeaderTakeSeat just above -- it is the same kind
         of element, a go-ahead button in this header, not a new colour. */
      .poker8-online .mobile-header-seat-actions #mobileHeaderReadyUp{
        border-color:rgba(64,237,167,.7);background:#0a3b2b;color:#b8ffda;
        animation:p8HeaderReadyPulse 1.6s ease-in-out infinite;
      }
      @keyframes p8HeaderReadyPulse{0%,100%{box-shadow:0 0 0 0 rgba(64,237,167,.35)}50%{box-shadow:0 0 0 4px rgba(64,237,167,0)}}
      @media (prefers-reduced-motion:reduce){
        .poker8-online .mobile-header-seat-actions #mobileHeaderReadyUp{animation:none}
      }
      /* v037 built the chat/hint pair in the table's old cyan; recoloured to
         the same violet as #mobileHeaderObserve above so the whole header
         utility row -- seat actions, chat, hint -- reads as one accent
         instead of three unrelated ones (mint, cyan, and now this). */
      .poker8-online .mobile-chat-button,
      .poker8-online .mobile-hint-button{
        border-color:rgba(201,168,255,.6)!important;
        background:rgba(18,7,30,.78)!important;
        box-shadow:0 0 14px rgba(201,168,255,.16),inset 0 0 12px rgba(201,168,255,.08)!important;
        color:#eaddff!important;
      }
      .poker8-online .mobile-chat-button .chat-bubble{fill:rgba(201,168,255,.20)!important;}
    @media(max-width:780px){
      /* Observer mode's header borrowed the seated player's opaque black/
         photo background (v032, v038) wholesale. A viewer with no seat has
         nothing that contrast was protecting, so it can loosen into the same
         violet glass the lobby already uses instead of a solid black bar. */
      .poker8-online.p8-observer-mode .mobile-game-header{
        background-image:none!important;
        background:linear-gradient(180deg,rgba(36,16,62,.72),rgba(7,16,15,.90))!important;
        backdrop-filter:blur(16px)!important;
        border-bottom-color:rgba(201,168,255,.24)!important;
        box-shadow:0 10px 26px rgba(18,7,30,.4)!important;
      }
      /* v038 derives --table-stage-h from these two vars, so zeroing them here
         (custom-property !important still beats v038's later non-important
         declaration) expands the felt into the space the hidden action panel
         would otherwise still reserve for nothing but an empty black slab.
         Overriding --table-stage-h directly as well, rather than only its
         inputs, caps how far that expansion goes: on a tall phone the raw
         calc reaches ~2.4x the felt's width, which stretches every seat
         layout percentage (tuned for ~1.6x) into a tube where the ring no
         longer follows the felt's edge. */
      /* The stage formula is the phone's -- desktop takes its height from the
         grid row instead, so only this part stays behind the media query. */
      body.v014.poker8-v2-sixmax.p8-observer-mode{
        --table-stage-h:calc(100dvh - 50px)!important;
      }
    }
  `;
  document.head.appendChild(tablePageStyle);
  document.body.classList.add("poker8-online");

  const $ = id => document.getElementById(id);
  const mobileQuery = window.matchMedia?.("(max-width: 780px)");
  function placeReadyPanel() {
    const panel = $("readyPanel");
    const felt = document.querySelector(".felt");
    if (!panel || !felt) return;
    // The felt at every width. The pending strip spent a version in the desktop
    // topbar as well, to report that a seat request had landed -- but the
    // header's own "В очереди" button already says exactly that, in the place
    // the request was made from, so the strip was the same news twice and it
    // cost the bar a second row. On desktop it is now simply hidden (v039);
    // this only has to put it somewhere for the phone.
    if (panel.parentElement !== felt) felt.append(panel);
  }
  placeReadyPanel();
  mobileQuery?.addEventListener?.("change", placeReadyPanel);

  // Same trick as placeReadyPanel above, for the seat/utility buttons.
  // ensureHeaderSeatButtons already builds them and syncHeaderSeatButtons
  // already keeps them in step on every render, at every width -- they were
  // simply parked inside #mobileGameHeader, which v039 hides on desktop, so
  // desktop had no take-seat/observe pair, no combos hint, and therefore no
  // way to reach the buy-in slider (its only caller is the take-seat click).
  // Moving the existing nodes keeps every handler, every state sync and the
  // travelling-light glow exactly as they are -- no second copy to drift.
  function placeHeaderActions() {
    const header = document.getElementById("mobileGameHeader");
    const topActions = document.querySelector(".topbar .top-actions");
    const groups = [$("mobileHeaderSeatActions"), $("mobileHeaderUtility")].filter(Boolean);
    if (!groups.length || !header) return;
    const phone = Boolean(mobileQuery?.matches);
    const host = phone ? header : topActions;
    if (!host) return;
    for (const group of groups) {
      if (group.parentElement !== host) host.append(group);
    }
    // ...except that on desktop the seat pair moves one level up, to sit
    // straight after the room's name and blinds rather than at the far end of
    // the right-hand cluster. "Нажмите на аватар" is an instruction about the
    // table being looked at, not one more control to reach for, and at the end
    // of a wide bar it was a caption with nothing near it. v039 gives it the
    // auto margin that leaves the rest of the bar exactly where it was.
    const seatGroup = $("mobileHeaderSeatActions");
    const bar = topActions?.parentElement;
    if (!phone && seatGroup && topActions && bar && seatGroup.parentElement !== bar) {
      bar.insertBefore(seatGroup, topActions);
    }
    // The way back to the lobby lives in the drawer, and v039 hides the
    // drawer on desktop -- so a desktop table was a room with no door: the
    // only exits were the browser's back button and closing the tab. Moved
    // the same way the seat buttons are, so returnToLobby and its
    // cancel-ready-then-disconnect stay bound to the one node. On a phone it
    // goes back where it was, above "Покинуть стол", which is the order the
    // drawer reads in.
    const drawer = document.getElementById("mobileDrawer");
    // Appended in order rather than inserted before a sibling: an anchor that
    // is not where it was assumed to be makes insertBefore throw, and a throw
    // here would abort the rest of this function. These two are the last
    // things in the drawer, so appending them is the order it reads in.
    for (const id of ["mobileDrawerLobby", "mobileDrawerLeave"]) {
      const button = document.getElementById(id);
      if (!button || !drawer) continue;
      const home = phone ? drawer : host;
      if (button.parentElement !== home) home.append(button);
    }
    // Only claimed once the buttons are actually in the desktop header, so a
    // failure above can never leave desktop with no way to sit down at all:
    // #readyPanel stays as the fallback until this says otherwise.
    document.body.classList.toggle("p8-desktop-header-actions", !phone);
    sizeHeaderSeatButtons();
  }
  placeHeaderActions();
  mobileQuery?.addEventListener?.("change", placeHeaderActions);
  // A webview can report its width before it has settled, and the media
  // query only fires when the breakpoint is actually crossed -- so a first
  // pass that read the wrong side would leave the drawer's buttons in a
  // header nobody can see until the next snapshot render happened to fix it.
  window.addEventListener("resize", placeHeaderActions, { passive: true });

  const units = value => Math.round(Number(value || 0));
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#003399;",
  }[char]));
  let table = null;
  let viewerState = "spectator";
  //: The seat the server counts as actually seated, straight from it --
  //: null while a seat is only held or leaving. See viewer_seat_no.
  let viewerSeatedSeat = null;
  let latestState = null;
  let pollTimer = null;
  let lastRenderKey = null;
  let readyInFlight = false;
  let readyUpInFlight = false;
  // Whether this table is a room the viewer opened. Asked once, from the
  // endpoint the lobby already uses: the snapshot carries created_by but not
  // who is looking, and one room per player makes an id match the whole proof.
  let ownsThisRoom = false;

  window.addEventListener("poker8:action-pending", event => {
    document.body.classList.toggle("p8-action-pending", Boolean(event.detail?.pending));
  });

  function setText(id, value) {
    const node = $(id);
    if (node) node.textContent = String(value ?? "");
  }

  function firstOpenSeat(state) {
    const occupied = new Set(Object.values(state?.players || {}).map(player => Number(player.seat)));
    return [0, 1, 2, 3, 4, 5].find(seat => !occupied.has(seat)) ?? 0;
  }

  function phaseLabel(state) {
    let phase = state?.phase || "waiting";
    // The runtime drops to "waiting" for the instant between clearing a hand and
    // dealing the next one. Showing it makes the label flicker mid-countdown.
    if (phase === "waiting" && state?.next_hand_at && Date.parse(state.next_hand_at) > Date.now()) phase = "countdown";
    // Every other phase reads in Russian; "COUNTDOWN" was the one word of
    // English in the pill, and the line under it already counts the seconds.
    return { waiting: "ОЖИДАНИЕ", countdown: "ПЕРЕРЫВ", active: "РАЗДАЧА", result: "ВСКРЫТИЕ", paused: "ПАУЗА" }[phase] || phase.toUpperCase();
  }

  // Fills the space Phase 1 emptied: the topbar (desktop-only -- mobile.css
  // hides .topbar outright) used to read "ЛОКАЛЬНЫЙ ТРЕНАЖЁР / Poker Trainer
  // v0.13" and "N / 7 игроков" on a six-max online table. max_seats is the
  // table's own number, which is what made the hardcoded 7 wrong.
  function syncTableIdentity(state) {
    const host = document.querySelector(".topbar .brand-wrap > div:last-child");
    if (!host || !table) return;
    let box = document.getElementById("p8TableIdentity");
    if (!box) {
      box = document.createElement("div");
      box.id = "p8TableIdentity";
      box.className = "p8-table-identity";
      // Name and blinds only. A second "Инструкция" button lived here for a
      // while, opening the panel the header's "?" already opens, two controls
      // apart in the same bar -- the same door twice.
      box.innerHTML = '<b data-name></b><small data-meta></small>';
      host.appendChild(box);
    }
    // Same units-to-money convention the lobby prints blinds with.
    const money = value => (Number(value || 0) / 100).toFixed(2);
    const seats = Number(table.max_seats) || 6;
    // current_seats is the live roster and the only one right between hands;
    // occupancy is the last hand's count and stands in when it is absent.
    const taken = Object.keys(state?.current_seats || {}).length
      || Number(state?.occupancy) || 0;
    box.querySelector("[data-name]").textContent = table.name || "Стол";
    box.querySelector("[data-meta]").textContent =
      `${money(table.small_blind_units)} / ${money(table.big_blind_units)} · ${taken} из ${seats} мест`;
  }

  function ensureHeaderSeatButtons() {
    const header = document.getElementById("mobileGameHeader");
    if (!header || document.getElementById("mobileHeaderSeatActions")) return;
    const wrap = document.createElement("div");
    wrap.id = "mobileHeaderSeatActions";
    wrap.className = "mobile-header-seat-actions";
    wrap.innerHTML = `
      <button id="mobileHeaderTakeSeat" type="button">Занять место</button>
      <button id="mobileHeaderObserve" type="button">Наблюдать</button>
      <button id="mobileHeaderReadyUp" type="button" hidden>Нажмите на аватар</button>
    `;
    header.appendChild(wrap);
    $("mobileHeaderTakeSeat").addEventListener("click", () => {
      // Queued already means the seat request is in flight -- the label
      // reads "В очереди" and the button is disabled, so a click here can
      // only be the queued state's own listener firing on a disabled
      // element in some browsers; showing the picker again would let
      // someone queue a second buy-in choice mid-request.
      if (viewerState === "waiting") return;
      showBuyInDialog();
    });
    $("mobileHeaderObserve").addEventListener("click", () => {
      // Only does anything while queued: it gives the seat back and returns
      // the viewer to plain watching. Already watching means nothing to do.
      if (viewerState !== "waiting") return;
      cancelQueue().catch(error => alert(error.message));
    });
    // Same action the avatar itself performs -- this is just a second place
    // to reach it, for someone who stayed seated between hands and would
    // otherwise have no way back to "ready" without a card sitting over the
    // board they came to keep watching.
    $("mobileHeaderReadyUp").addEventListener("click", () => {
      readyUp().catch(error => alert(error.message));
    });
  }

  // The seat-number equivalent of state.viewer_player_id: players only lists
  // whoever was dealt into the last hand, so between hands (or for a seat
  // that bought in mid-hand) the seat has to come from current_seats instead
  // -- same fallback app.js's own seatHtml uses to find this same viewer.
  function viewerSeatNo(state) {
    const viewerId = state?.viewer_player_id;
    if (!viewerId) return null;
    const fromHand = state.players?.[viewerId];
    if (fromHand) return Number(fromHand.seat);
    for (const [seatNo, row] of Object.entries(state.current_seats || {})) {
      // current_seats also carries seats that are only held for the next
      // boundary, and seats on their way out. The server counts neither as
      // seated, so treating one as this viewer's seat put a "mark ready"
      // button in front of somebody who had no seat to be ready in.
      if (row?.id === viewerId && (!row.state || row.state === "seated")) return Number(seatNo);
    }
    return null;
  }

  // A native <dialog>: it brings its own backdrop, focus trap and Esc handling,
  // none of which is worth reimplementing for one modal.
  function ensureFundsDialog() {
    const existing = document.getElementById("p8FundsDialog");
    if (existing) return existing;
    const dialog = document.createElement("dialog");
    dialog.id = "p8FundsDialog";
    dialog.className = "p8-funds-dialog";
    dialog.innerHTML = `
      <h2 data-title>Недостаточно средств</h2>
      <p class="p8-funds-lead" data-lead hidden></p>
      <p class="p8-funds-sums">
        Вход за этот стол — <b data-need>—</b><br>
        На вашем балансе — <b data-have>—</b>
      </p>
      <button type="button" class="p8-funds-again" data-again hidden>Занять место снова</button>
      <div class="p8-funds-offer" data-offer>
        <strong>Пополнить баланс</strong>
        <span data-topup-note>Оплата в USDT скоро будет доступна</span>
        <button type="button" data-topup disabled>Пополнить через USDT</button>
      </div>
      <button type="button" class="p8-funds-close" data-close>Понятно</button>
    `;
    document.body.appendChild(dialog);
    dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
    dialog.querySelector("[data-again]").addEventListener("click", () => {
      dialog.close();
      ready().catch(error => alert(error.message));
    });
    dialog.querySelector("[data-topup]").addEventListener("click", () => {
      // The single seam the payment flow plugs into: register a handler and the
      // button turns live, with no other change to this file.
      window.Poker8TopUp?.open?.({ requiredUnits: dialog.dataset.requiredUnits });
    });
    return dialog;
  }

  function showFundsDialog({ title, lead, requiredUnits, availableUnits }) {
    const dialog = ensureFundsDialog();
    // In big blinds: the unit every other number on the table already uses.
    // Raw chip counts appear nowhere the player can see.
    const bb = value => `${Math.floor(Number(value || 0) / Math.max(1, units(table?.big_blind_units)))} ББ`;
    dialog.dataset.requiredUnits = String(requiredUnits ?? "");
    dialog.querySelector("[data-title]").textContent = title;
    const leadEl = dialog.querySelector("[data-lead]");
    leadEl.textContent = lead || "";
    leadEl.hidden = !lead;
    dialog.querySelector("[data-need]").textContent = bb(requiredUnits);
    dialog.querySelector("[data-have]").textContent = bb(availableUnits);

    // Busting out does not always mean being broke: the table stack is gone,
    // but the wallet may still cover another buy-in. Offering a top-up then
    // would be answering a question the player did not ask.
    const affordable = Number(availableUnits || 0) >= Number(requiredUnits || 0);
    dialog.querySelector("[data-again]").hidden = !affordable;
    dialog.querySelector("[data-offer]").hidden = affordable;

    const topUp = dialog.querySelector("[data-topup]");
    const live = Boolean(window.Poker8TopUp?.open);
    topUp.disabled = !live;
    dialog.querySelector("[data-topup-note]").textContent = live
      ? "Пополнение откроется в отдельном окне"
      : "Оплата в USDT скоро будет доступна";
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function showInsufficientFunds(requiredUnits, availableUnits) {
    showFundsDialog({ title: "Недостаточно средств", requiredUnits, availableUnits });
  }

  // A native <dialog>, same reasoning as ensureFundsDialog just above.
  //: Which seat the dialog was opened for. The header's "Занять место" has
  //: no particular one in mind, so it stays null and the server takes the
  //: first free chair; a click on the seat itself means that chair.
  let pendingBuyInSeat = null;

  function ensureBuyInDialog() {
    const existing = document.getElementById("p8BuyInDialog");
    if (existing) return existing;
    const dialog = document.createElement("dialog");
    dialog.id = "p8BuyInDialog";
    dialog.className = "p8-buyin-dialog";
    dialog.innerHTML = `
      <h2>Сколько фишек взять?</h2>
      <p class="p8-buyin-note" data-note>От <b data-min>—</b> до <b data-max>—</b> ББ</p>
      <div class="p8-buyin-value"><span data-value>—</span><span>ББ</span></div>
      <input type="range" data-slider />
      <div class="p8-buyin-actions">
        <button type="button" data-cancel>Отмена</button>
        <button type="button" data-confirm>Занять место</button>
      </div>
    `;
    document.body.appendChild(dialog);
    const slider = dialog.querySelector("[data-slider]");
    slider.addEventListener("input", () => {
      dialog.querySelector("[data-value]").textContent = slider.value;
    });
    dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
    dialog.querySelector("[data-confirm]").addEventListener("click", () => {
      const bb = Number(slider.value);
      dialog.close();
      ready(pendingBuyInSeat, bb).catch(error => alert(error.message));
    });
    return dialog;
  }

  // min/max_buy_in_bb come straight off the table row (see catalogue.py) --
  // every table can set its own range, so nothing here is hardcoded.
  function showBuyInDialog(seatNo = null) {
    pendingBuyInSeat = Number.isFinite(seatNo) ? seatNo : null;
    const dialog = ensureBuyInDialog();
    const min = Number(table?.min_buy_in_bb) || 40;
    const max = Math.max(min, Number(table?.max_buy_in_bb) || 100);
    const slider = dialog.querySelector("[data-slider]");
    slider.min = String(min);
    slider.max = String(max);
    slider.step = "1";
    // 40 was the flat default every ready() call used before this dialog
    // existed -- clamped into range so a table whose own minimum sits above
    // 40 does not start the slider outside its own bounds.
    slider.value = String(Math.min(max, Math.max(min, 40)));
    dialog.querySelector("[data-min]").textContent = String(min);
    dialog.querySelector("[data-max]").textContent = String(max);
    dialog.querySelector("[data-value]").textContent = slider.value;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    // Same Telegram Desktop webview focus gap as the lobby's own dialogs.
    requestAnimationFrame(() => slider.focus());
  }

  // Set right before a cancel this tab itself asked for, so the very next
  // "cancelled" queue_state noticeLostSeatRequest sees doesn't get read as
  // an involuntary loss -- the server marks both a self-cancel and an
  // insufficient-funds cancel with the exact same "cancelled" state (see
  // cancel_ready and the funds check in seating.py), so nothing in that
  // state alone can tell them apart. Only this tab's own click can.
  let voluntaryCancelInFlight = false;

  async function cancelQueue() {
    voluntaryCancelInFlight = true;
    await window.Poker8Transport.cancelReady();
    await refreshState();
  }

  //: Every label either button can carry -- the width has to fit the widest,
  //: or the swap resizes the pair.
  const SEAT_ACTION_LABELS = ["Занять место", "Наблюдать", "В очереди", "Отменить"];

  // Measured rather than assumed: the 88px this replaces was right in Inter
  // and too narrow in the system face a phone falls back to, which truncated
  // the longest label. Capped so a very wide face cannot push the pair into
  // the utility group beside it; the ellipsis is still there underneath.
  function sizeHeaderSeatButtons() {
    const wrap = $("mobileHeaderSeatActions");
    const button = $("mobileHeaderTakeSeat");
    if (!wrap || !button) return;
    const style = window.getComputedStyle(button);
    const probe = document.createElement("span");
    probe.style.cssText = `position:absolute;visibility:hidden;white-space:nowrap;font:${style.font}`;
    document.body.appendChild(probe);
    let widest = 0;
    for (const label of SEAT_ACTION_LABELS) {
      probe.textContent = label;
      widest = Math.max(widest, probe.getBoundingClientRect().width);
    }
    probe.remove();
    if (!widest) return;
    const chrome = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight)
      + parseFloat(style.borderLeftWidth) + parseFloat(style.borderRightWidth);
    const width = Math.min(Math.ceil(widest + chrome) + 2, Math.round(window.innerWidth * 0.34));
    wrap.style.setProperty("--p8-seat-action-w", `${width}px`);
  }

  function syncHeaderSeatButtons(state) {
    const wrap = $("mobileHeaderSeatActions");
    if (!wrap) return;
    const readyButton = $("mobileHeaderReadyUp");
    const take = $("mobileHeaderTakeSeat");
    const observe = $("mobileHeaderObserve");

    // Seated and nothing dealt to them yet -- the case that used to be a card
    // over the felt saying "НАЖМИТЕ НА АВАТАР" for someone who never got up.
    // The avatar's own checkmark and pulse already carry the state; this is
    // just a second way to reach the same toggle, up where the seat/observe
    // pair lives when there's no seat/observe choice to make.
    // From the server, not inferred: viewer_state says "seated" for a seat
    // that is only held or leaving too. Falls back to the last REST value
    // for websocket pushes, which do not carry the field.
    const seatNo = viewerState === "seated" ? (state?.viewer_seat_no ?? viewerSeatedSeat) : null;
    const awaitingReady = viewerState === "seated" && isPreHand() && seatNo != null
      && !(state?.ready_seats || []).includes(seatNo);
    if (readyButton) readyButton.hidden = !awaitingReady;
    // Solo mode: with the seat/observe pair hidden, the wrap shrinks to fit
    // this one button and inherits wherever the header's hamburger-vs-utility
    // width imbalance happens to land it -- off-centre, worse the longer this
    // button's own label runs. Centring the wrap itself on the header only
    // when it's carrying just this button is safe precisely because it's
    // never sharing the row with the wider pair that overlapping chat/hint
    // in the first place (see the wrap's own flow-layout fix above).
    wrap.classList.toggle("ready-up-only", awaitingReady);

    const offer = ["spectator", "waiting"].includes(viewerState);
    if (take) take.hidden = !offer;
    if (observe) observe.hidden = !offer;
    wrap.hidden = !offer && !awaitingReady;
    if (!offer) return;
    // The pair reads as "where you are now / what you can switch to", both
    // driven by the server's own answer. The old version highlighted a stored
    // preference instead, which could disagree with the actual state -- and
    // "Наблюдать" did nothing at all beyond moving that highlight.
    const queued = viewerState === "waiting";
    if (take) {
      take.textContent = queued ? "В очереди" : "Занять место";
      take.disabled = queued;
      // mode-active marks which button reflects where the viewer actually is
      // right now -- the same thing aria-pressed already says -- not which
      // one is still on offer. Queued *is* "taking a seat" in progress, so
      // that's when this one lights up, matching aria-pressed just below.
      take.classList.toggle("mode-active", queued);
      take.setAttribute("aria-pressed", String(queued));
      take.title = queued
        ? "Место забронировано — вы сядете после текущей раздачи"
        : "Занять свободное место за этим столом";
    }
    if (observe) {
      observe.textContent = queued ? "Отменить" : "Наблюдать";
      observe.disabled = false;
      observe.classList.toggle("mode-active", !queued);
      observe.setAttribute("aria-pressed", String(!queued));
      observe.title = queued
        ? "Отказаться от места и просто смотреть"
        : "Вы наблюдаете за столом";
    }
  }

  //: Refreshed every second while the chat covers the table, so the count is
  //: the player's real remaining time and not whatever the last snapshot said.
  let chatTurnTicker = null;
  const desktopChat = window.matchMedia("(min-width:781px)");
  let chatGeometry = null;
  let chatPointer = null;
  let chatSending = false;

  const chatEditor = () => $(desktopChat.matches ? "chatDesktopInput" : "chatInput");

  function placeChatWindow() {
    const chat = $("chatPanel");
    if (!chat || !desktopChat.matches) return;
    const width = Math.min(chatGeometry?.width || 400, innerWidth - 24);
    const height = Math.min(chatGeometry?.height || 520, innerHeight - 24);
    const visibleHeight = chat.classList.contains("is-collapsed") ? 64 : height;
    chatGeometry = {
      width, height,
      x: Math.max(12, Math.min(chatGeometry?.x ?? innerWidth - width - 24, innerWidth - width - 12)),
      y: Math.max(12, Math.min(chatGeometry?.y ?? 96, innerHeight - visibleHeight - 12)),
    };
    for (const [key, value] of Object.entries(chatGeometry)) chat.style.setProperty(`--chat-${key}`, `${value}px`);
  }

  function scrollChatToLatest() {
    const feed = $("chatMessages");
    if (feed) feed.scrollTop = feed.scrollHeight;
    $("chatPanel")?.classList.remove("has-new-messages");
  }

  function syncChatBreakpoint() {
    const chat = $("chatPanel");
    const heading = chat?.querySelector("h2");
    if (!heading) return;
    heading.tabIndex = desktopChat.matches ? 0 : -1;
    heading.title = desktopChat.matches ? "Перетащите окно · стрелки на клавиатуре перемещают его" : "";
    if (!desktopChat.matches) setChatCollapsed(false);
    placeChatWindow();
  }

  function setChatCollapsed(collapsed) {
    const chat = $("chatPanel");
    chat.classList.toggle("is-collapsed", collapsed);
    const button = chat.querySelector(".chat-minimize");
    button.setAttribute("aria-label", collapsed ? "Развернуть чат" : "Свернуть чат");
    button.title = button.getAttribute("aria-label");
    button.setAttribute("aria-expanded", String(!collapsed));
    button.textContent = collapsed ? "+" : "−";
    placeChatWindow();
  }

  function ensureChatFurniture() {
    const chat = $("chatPanel");
    if (!chat || chat.dataset.p8Furnished) return;
    chat.dataset.p8Furnished = "1";

    const banner = document.createElement("button");
    banner.type = "button";
    banner.className = "chat-turn-banner";
    banner.innerHTML = '<span>Ваш ход — вернуться за стол</span><b></b>';
    chat.insertBefore(banner, chat.querySelector("#chatMessages"));

    const close = document.createElement("button");
    close.type = "button";
    close.className = "chat-close";
    close.setAttribute("aria-label", "Закрыть чат");
    close.textContent = "×";
    chat.appendChild(close);

    const controls = document.createElement("div");
    controls.className = "chat-window-tools";
    controls.innerHTML = '<button type="button" class="chat-reset" aria-label="Вернуть положение чата" title="Вернуть положение чата">↺</button><button type="button" class="chat-minimize" aria-label="Свернуть чат" aria-expanded="true" title="Свернуть чат">−</button>';
    chat.appendChild(controls);
    const resize = document.createElement("button");
    resize.type = "button";
    resize.className = "chat-resize";
    resize.setAttribute("aria-label", "Изменить размер чата");
    resize.title = "Перетащите угол · стрелки меняют размер";
    chat.appendChild(resize);
    const latest = document.createElement("button");
    latest.type = "button";
    latest.className = "chat-latest";
    latest.textContent = "Новые сообщения ↓";
    chat.insertBefore(latest, $("chatFormat"));
    const status = document.createElement("div");
    status.className = "chat-send-status";
    status.setAttribute("role", "status");
    chat.appendChild(status);
    const hint = document.createElement("div");
    hint.className = "chat-compose-hint";
    hint.textContent = "Enter — отправить · Shift + Enter — новая строка";
    chat.appendChild(hint);
    const editor = document.createElement("textarea");
    editor.id = "chatDesktopInput";
    editor.rows = 2;
    editor.maxLength = 1000;
    editor.placeholder = "Напишите за стол…";
    editor.setAttribute("aria-label", "Сообщение");
    $("chatInput").after(editor);
    // Each layout retains its native editor. Only editing copies the draft,
    // so a round trip through the phone width doesn't strip desktop newlines.
    for (const input of [editor, $("chatInput")]) input.addEventListener("input", () => {
      (input === editor ? $("chatInput") : editor).value = input.value;
      status.textContent = "";
    });
    editor.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        $("chatForm").requestSubmit();
      }
    });
    controls.querySelector(".chat-minimize").addEventListener("click", () => setChatCollapsed(!chat.classList.contains("is-collapsed")));
    controls.querySelector(".chat-reset").addEventListener("click", () => { chatGeometry = null; placeChatWindow(); });
    latest.addEventListener("click", scrollChatToLatest);
    $("chatMessages").addEventListener("scroll", () => {
      const feed = $("chatMessages");
      if (feed.scrollHeight - feed.scrollTop - feed.clientHeight < 32) chat.classList.remove("has-new-messages");
    });
    const heading = chat.querySelector("h2");
    for (const handle of [heading, resize]) {
      handle.addEventListener("pointerdown", event => {
        if (!desktopChat.matches || event.button !== 0) return;
        placeChatWindow();
        chatPointer = { id: event.pointerId, x: event.clientX, y: event.clientY, geometry: { ...chatGeometry } };
        handle.setPointerCapture(event.pointerId);
        event.preventDefault();
      });
      handle.addEventListener("pointermove", event => {
        if (!desktopChat.matches || chatPointer?.id !== event.pointerId) return;
        const dx = event.clientX - chatPointer.x, dy = event.clientY - chatPointer.y;
        const start = chatPointer.geometry;
        chatGeometry = handle === resize
          ? { ...start, width: Math.max(320, Math.min(start.width + dx, innerWidth - start.x - 12)), height: Math.max(300, Math.min(start.height + dy, innerHeight - start.y - 12)) }
          : { ...start, x: start.x + dx, y: start.y + dy };
        placeChatWindow();
      });
      handle.addEventListener("lostpointercapture", () => { chatPointer = null; });
      handle.addEventListener("keydown", event => {
        if (!desktopChat.matches || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        placeChatWindow();
        const horizontal = ["ArrowLeft", "ArrowRight"].includes(event.key);
        const key = handle === resize ? (horizontal ? "width" : "height") : (horizontal ? "x" : "y");
        chatGeometry[key] += ["ArrowLeft", "ArrowUp"].includes(event.key) ? -10 : 10;
        if (handle === resize) chatGeometry[key] = Math.max(horizontal ? 320 : 300, chatGeometry[key]);
        placeChatWindow();
      });
    }
    desktopChat.addEventListener("change", syncChatBreakpoint);
    window.addEventListener("resize", placeChatWindow);
    syncChatBreakpoint();
  }

  function closeChat() {
    const chat = $("chatPanel");
    if (!chat) return;
    chat.classList.remove("is-open");
    chat.hidden = true;
    $("mobileChatButton")?.setAttribute("aria-expanded", "false");
    if (desktopChat.matches) $("mobileChatButton")?.focus();
    syncChatTurnBanner();
  }

  function chatTurnSecondsLeft() {
    const state = latestState;
    if (!state || state.phase !== "active") return null;
    if (!state.viewer_player_id || state.acting_player !== state.viewer_player_id) return null;
    if (!state.action_deadline) return null;
    return Math.max(0, Math.ceil((Date.parse(state.action_deadline) - Date.now()) / 1000));
  }

  function syncChatTurnBanner() {
    const chat = $("chatPanel");
    const banner = chat?.querySelector(".chat-turn-banner");
    if (!banner) return;
    const open = chat.classList.contains("is-open");
    const seconds = open ? chatTurnSecondsLeft() : null;
    const live = seconds !== null;
    banner.classList.toggle("is-live", live);
    banner.classList.toggle("is-urgent", live && seconds <= 10);
    if (live) banner.querySelector("b").textContent = `${seconds} c`;

    if (live && chatTurnTicker === null) {
      chatTurnTicker = setInterval(syncChatTurnBanner, 1000);
    } else if (!live && chatTurnTicker !== null) {
      clearInterval(chatTurnTicker);
      chatTurnTicker = null;
    }
  }

  function renderOnlineChrome(state) {
    setText("mobileStreetLabel", phaseLabel(state));

    const observerMode = ["spectator", "waiting"].includes(viewerState);
    document.body.classList.toggle("p8-observer-mode", observerMode);
    // Seated, a hand running, and no part in it -- folded, or the seat was
    // claimed after the cards were out. The controls have nothing to do with
    // this hand, so they go; see the .p8-not-in-hand rules in v039. The panel
    // itself stays, because collapsing it mid-hand would jump the table.
    const viewerInHand = Boolean(
      state?.viewer_player_id
      && state.players?.[state.viewer_player_id]
      && !state.players[state.viewer_player_id].folded,
    );
    document.body.classList.toggle(
      "p8-not-in-hand",
      !observerMode && Boolean(state?.hand_id) && !viewerInHand,
    );
    // Claiming a seat mid-hand already worked -- the queue holds it and seats
    // you at the boundary -- but the felt did not say so: the chair carried
    // on offering itself as if nothing had been pressed, and the only sign
    // was the header. The seat being held is the one still carrying the
    // offer, since the queue takes the same seat renderSeats offers, so the
    // class is all v040 needs to mark the right chair.
    document.body.classList.toggle("p8-seat-reserved", viewerState === "waiting");
    ensureHeaderSeatButtons();
    // The nodes do not exist at module init, and v037 appends the chat/hint
    // group later still, so the initial call above cannot have placed them.
    // Idempotent -- it only touches a group whose parent is already wrong.
    placeHeaderActions();
    syncTableIdentity(state);
    syncHeaderSeatButtons(state);
    // Stays available even after the header prompt is dismissed -- it's the
    // way back once someone decides they want to play after all.
    const drawerTakeSeat = $("mobileDrawerTakeSeat");
    if (drawerTakeSeat) drawerTakeSeat.hidden = !observerMode;
    const ready = $("readyPanel");
    if (ready) {
      // The queue seats players at the next hand boundary, so the panel stays
      // available while a hand is running.
      ready.hidden = !["spectator", "waiting"].includes(viewerState);
      const occupiedSeats = new Set(Object.values(state?.players || {}).map(player => Number(player.seat)));
      const totalSeats = Number(table?.max_seats || 6);
      const hasFreeSeat = occupiedSeats.size < totalSeats;
      const waitingText = hasFreeSeat
        ? "Место забронировано — вход после текущей раздачи"
        : "Все места заняты — ждём освобождение между раздачами";
      const title = ready.querySelector("strong");
      if (title) title.textContent = viewerState === "waiting" ? "Место забронировано" : hasFreeSeat ? "Займите место" : "Встаньте в очередь";
      setText("queueStatus", viewerState === "waiting" ? waitingText : hasFreeSeat
        ? "Первое свободное место · бай-ин 40 ББ"
        : "Свободных мест нет — забронируйте вход после раздачи");
      const button = $("readyButton");
      if (button) {
        button.disabled = viewerState === "waiting";
        button.textContent = viewerState === "waiting" ? "Бронь принята" : hasFreeSeat ? "Занять место" : "Встать в очередь";
      }
      // Pending has nothing to click, so the full card only blocks the table.
      ready.classList.toggle("is-pending", viewerState === "waiting");
    }
    const chat = $("chatPanel");
    if (chat) {
      ensureChatFurniture();
      const mobile = window.matchMedia?.("(max-width:780px)")?.matches;
      chat.hidden = Boolean(mobile && !chat.classList.contains("is-open"));
      syncChatTurnBanner();
    }
    ["infiniteMode", "spectatorPause", "abortHand", "newHand", "mobilePrimaryAction"].forEach(id => {
      if ($(id)) $(id).classList.add("local-only-control");
    });
  }

  function snapshotRenderKey(state) {
    const players = Object.values(state?.players || {})
      .map(player => [player.id, player.seat, player.stack, player.folded, player.street_invested]);
    return JSON.stringify([
      viewerState,
      state?.hand_id,
      state?.phase,
      state?.revision,
      state?.street,
      state?.acting_player,
      state?.pot,
      state?.action_deadline,
      state?.result_clear_at,
      state?.next_hand_at,
      state?.ready_seats,
      state?.hand_starts_at,
      players,
    ]);
  }

  function renderObserverCopy(state) {
    if (!["spectator", "waiting"].includes(viewerState)) return;
    const actor = state?.players?.[state?.acting_player];
    setText("actionPanelKicker", viewerState === "waiting" ? "МЕСТО ЗАБРОНИРОВАНО" : "НАБЛЮДЕНИЕ");
    setText("turnTitle", actor ? `Ход: ${actor.name || "игрок"}` : "Смотрите раздачу");
    setText("hint", viewerState === "waiting"
      ? "Вход за стол произойдёт после текущей раздачи."
      : "Смотрите раздачу. Чтобы играть, займите свободное место.");
    if ($("actionTimer")) $("actionTimer").hidden = true;
  }

  // Whether this viewer holds a seat is decided by the server on every
  // snapshot, and the socket delivers one per viewer with their own
  // viewer_player_id. viewerState otherwise only advances on the REST refresh,
  // whose failures the 3s poll swallows -- so a single dropped refresh used to
  // pin a seated player in observer mode, which hides the whole action panel,
  // for the rest of the session and across reloads.
  //
  // Only the seated/not-seated half is recoverable here: queue membership is
  // not in the snapshot. That is enough, because both non-seated values gate
  // the table identically, and the REST refresh restores the exact one.
  function reconcileViewerState(state) {
    if (!state) return;
    if (state.viewer_player_id) {
      viewerState = "seated";
    } else if (viewerState === "seated") {
      viewerState = "spectator";
    }
  }

  let heldSeatLastSnapshot = false;
  // The seat's own stack, in units, from the last snapshot where the viewer
  // still held it -- captured *before* it disappears, since by the time
  // viewer_player_id is gone there is nothing left in the state naming which
  // seat used to be theirs. Distinguishes the two things that both make the
  // seat vanish the same way: a genuinely empty stack (below one big blind)
  // versus coordinator.py's AFK eviction, which frees a seat that never
  // confirmed ready for several hands running regardless of how many chips
  // are still on it -- reported live as "Фишки закончились" showing after
  // simply not pressing the avatar to start.
  let lastKnownSeatStackUnits = null;

  // Losing the stack takes the seat away at the next boundary, and the player
  // simply became a spectator mid-session with nothing said. Leaving on purpose
  // navigates away from this page, so a seat that disappears under someone
  // still sitting here is the table releasing it.
  function noticeBustOut(state) {
    const seatedNow = Boolean(state?.viewer_player_id);
    const lost = heldSeatLastSnapshot && !seatedNow;
    if (seatedNow) {
      const viewerId = state.viewer_player_id;
      const fromHand = state.players?.[viewerId];
      const seatNo = fromHand ? Number(fromHand.seat) : viewerSeatNo(state);
      const fromSeat = seatNo != null ? state.current_seats?.[seatNo] : null;
      const bb = fromHand ? Number(fromHand.stack) : fromSeat ? Number(fromSeat.stack) : null;
      if (bb != null) lastKnownSeatStackUnits = Math.round(bb * units(table?.big_blind_units));
    }
    heldSeatLastSnapshot = seatedNow;
    if (!lost) return;
    const bigBlindUnits = units(table?.big_blind_units);
    // null (never captured a stack) reads as busted too -- the safer default
    // when the cause genuinely can't be told apart.
    const genuinelyBusted = lastKnownSeatStackUnits == null || lastKnownSeatStackUnits < bigBlindUnits;
    lastKnownSeatStackUnits = null;
    // The wallet is only known to the profile endpoint, and this is a rare
    // moment, so one extra call is cheaper than tracking it on every snapshot.
    fetch("/api/profile")
      .then(response => (response.ok ? response.json() : null))
      .then(profile => showFundsDialog(genuinelyBusted ? {
        title: "Фишки закончились",
        lead: "Стек за столом опустел, и место освободилось.",
        requiredUnits: bigBlindUnits * 40,
        availableUnits: profile?.available_units ?? 0,
      } : {
        title: "Место освободилось",
        lead: "Вы не подтвердили готовность вовремя, и место занял кто-то другой.",
        requiredUnits: bigBlindUnits * 40,
        availableUnits: profile?.available_units ?? 0,
      }))
      .catch(() => {});
  }

  function renderSnapshot(state) {
    // Only the REST route stamps viewer_seat_no; the websocket snapshot -- which
    // is what actually drives a live table -- has never carried it. Between
    // hands `game` is null, so the seat id is the only thing tying a chair to
    // the viewer, and without it v040 found no hero: it rotated the table into
    // spectator layout, drew the "Сесть" offer over the seat the viewer was
    // already sitting in, and left the ready countdown with no avatar to ring,
    // so it fell back to the middle of the felt on top of the board.
    // viewerSeatedSeat is the REST route's last answer, so it is only trusted
    // while the server still calls this viewer a player -- once they stand up
    // it names a seat that is somebody else's now.
    if (state && state.viewer_seat_no == null && state.viewer_player_id) {
      state.viewer_seat_no = viewerSeatNo(state) ?? viewerSeatedSeat;
    }
    latestState = state;
    noticeBustOut(state);
    reconcileViewerState(state);
    renderOnlineChrome(state);
    // v038's ready-countdown ring already renders from any endsAt timestamp
    // (it was built for the local table's own 5s grace period) -- reused
    // here as-is, just fed from the server's own deadlines. hand_starts_at
    // (everyone ready, cards land in 5s) takes priority when it's armed;
    // otherwise ready_deadline (the 30s some-still-not-ready window) drives
    // the same ring, so players who haven't clicked ready see their clock
    // running instead of no countdown at all.
    const countdownEndsAt = state?.hand_starts_at || state?.ready_deadline;
    window.dispatchEvent(new CustomEvent("poker8:ready-countdown", {
      detail: { endsAt: countdownEndsAt ? Date.parse(countdownEndsAt) : 0 },
    }));
    const key = snapshotRenderKey(state);
    if (key === lastRenderKey) return;
    lastRenderKey = key;
    window.Poker8LegacyView?.renderSnapshot({ table, state, viewerState });
    renderObserverCopy(state);
  }

  async function refreshState() {
    const response = await fetch(`/api/tables/${encodeURIComponent(tableId)}`);
    if (!response.ok) throw new Error("Не удалось загрузить состояние стола");
    const payload = await response.json();
    table = payload.table;
    const cash = table.asset === "CASH_USDT";
    document.body.classList.toggle("p8-cash-test", cash);
    if (cash) {
      let badge = document.getElementById("p8CashTestBadge");
      if (!badge) {
        badge = document.createElement("div");
        badge.id = "p8CashTestBadge";
        badge.className = "online-connection-status";
        badge.style.cssText = "left:14px;right:auto;border-color:rgba(255,160,100,.45);color:#ffb37f";
        badge.textContent = "ТЕСТ · CASH НЕНАСТОЯЩИЙ";
        document.body.appendChild(badge);
      }
      window.Poker8TopUp = {open: () => { location.href = "/static/lobby.html#cash"; }};
    }
    viewerState = payload.viewer_state || viewerState;
    viewerSeatedSeat = payload.viewer_seat_no ?? null;
    noticeLostSeatRequest(payload.queue_state);
    window.Poker8Transport?.setRevision?.(payload.state?.revision);
    renderSnapshot(payload.state);
  }

  let lastQueueState = null;

  // A seat request can die without the player doing anything: the table stays
  // full past the request's lifetime, or the balance stops covering the buy-in.
  // Both used to just revert the button to "Занять место" with no explanation,
  // which reads as the request having been dropped for no reason.
  function noticeLostSeatRequest(queueState) {
    const previous = lastQueueState;
    const selfCancelled = voluntaryCancelInFlight;
    voluntaryCancelInFlight = false;
    lastQueueState = queueState || null;
    if (previous !== "waiting") return;
    if (lastQueueState === "expired") {
      alert("Место так и не освободилось, и заявка истекла.\nПопробуйте занять место ещё раз.");
    } else if (lastQueueState === "cancelled" && !selfCancelled) {
      alert("Заявка на место отменена — на балансе не хватило фишек на вход.");
    }
  }

  async function ready(seatNo = null, buyInBB = null) {
    if (readyInFlight || viewerState === "seated" || viewerState === "held" || viewerState === "leaving") return;
    // Asked up front when the table is known to need one, to skip a request
    // that would only come back asking for it -- the server checks again
    // regardless (table.has_password reflects what it knew at the last
    // snapshot, not necessarily this instant).
    let password = null;
    if (table?.has_password) {
      password = window.prompt("Эта комната закрыта паролем. Введите пароль:");
      if (password == null) return;
    }
    readyInFlight = true;
    const button = $("readyButton");
    if (button) button.disabled = true;
    // 40 ББ stays the default for every caller that never offered a choice
    // (a direct seat click, the ready-up avatar shortcut); the header's own
    // "Занять место" is the one path that asks first, via showBuyInDialog.
    const buyInUnits = buyInBB != null
      ? Math.round(buyInBB * units(table?.big_blind_units))
      : units(table?.big_blind_units) * 40;
    try {
      // A seat the player actually pointed at wins over the first free one.
      const result = await window.Poker8Transport.ready(
        seatNo == null ? firstOpenSeat(latestState) : seatNo, buyInUnits, password);
      viewerState = result.queue_state === "waiting" ? "waiting" : viewerState;
      await refreshState();
    } catch (error) {
      // One seat per player across the whole network, so the server refuses
      // this one and names the table already holding them. Swallowing that
      // made the button look simply broken: pressing "Занять место" left the
      // label untouched, raised nothing, and changed no state.
      const detail = error?.data?.detail;
      if (detail?.code === "insufficient_funds") {
        showInsufficientFunds(detail.required_units, detail.available_units);
        return;
      }
      if (detail?.code === "already_seated") {
        await refreshState();
        // Same table: the refresh above already turned the header into the
        // seated view, which explains itself. Another table needs saying.
        if (detail.table_id && detail.table_id !== tableId) {
          const go = window.confirm(
            "У вас уже есть место за другим столом — играть за двумя сразу нельзя.\nПерейти к своему столу?"
          );
          if (go) location.href = `/table?table=${encodeURIComponent(detail.table_id)}`;
        }
        return;
      }
      if (detail?.code === "wrong_password") {
        alert("Неверный пароль.");
        return;
      }
      throw error;
    } finally {
      readyInFlight = false;
    }
  }

  function isPreHand() {
    if (!latestState) return true;
    if (latestState.terminal) return true;
    // A seat that bought in while a hand was already running sits out that
    // hand entirely (state.players has nothing for them -- see current_seats
    // on the server). There is no live action of theirs a ready toggle could
    // possibly be confused with, so they must still be able to mark ready
    // for whichever hand deals next, exactly like between two hands.
    const viewerId = latestState.viewer_player_id;
    return Boolean(viewerId && !latestState.players?.[viewerId]);
  }

  async function readyUp() {
    // Toggling mid-hand would just be marking readiness for whichever hand
    // deals next, which is confusing -- gate the same way v024 does locally.
    //
    // viewerState is not enough on its own: the server reports "seated" for a
    // seat that is merely held for the next boundary, or on its way out,
    // while the endpoint behind this call counts only a seat in state
    // "seated" and answers "take a seat before marking ready" for the rest.
    // viewerSeatNo applies that same rule, so gating on it means the button
    // is offered exactly when the call behind it can succeed.
    if (readyUpInFlight || viewerState !== "seated" || !isPreHand()) return;
    if ((latestState?.viewer_seat_no ?? viewerSeatedSeat) == null) return;
    readyUpInFlight = true;
    try {
      await window.Poker8Transport.readyUp();
      await refreshState();
    } finally {
      readyUpInFlight = false;
    }
  }

  // Ported from board2 -- see static/chat-format.js for what came across and
  // what was left behind. The renderer escapes before it introduces a single
  // tag, so nothing a player types can become markup.
  const chatText = text => window.Poker8ChatFormat
    ? window.Poker8ChatFormat.render(text || "")
    : escapeHtml(text || "");
  const chatRow = row => {
    const rawDate = String(row.created_at || "");
    // SQLite history may serialize UTC without an offset; live websocket rows
    // include +00:00. Treat both representations as UTC, not browser-local.
    const date = new Date(rawDate && /(?:Z|[+-]\d\d:?\d\d)$/i.test(rawDate) ? rawDate : `${rawDate}Z`);
    const time = Number.isFinite(date.getTime())
      ? `<time class="p8-chat-time" datetime="${date.toISOString()}" title="${escapeHtml(date.toLocaleString("ru-RU"))}">${date.toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit"})}</time>` : "";
    return `<div class="p8-chat-row" data-chat-id="${escapeHtml(row.id || "")}"><div class="p8-chat-meta"><b>${escapeHtml(row.display_name || "Игрок")}</b>${time}</div> <div class="p8-chat-text">${chatText(row.text)}</div></div>`;
  };

  function appendChat(row) {
    const feed = $("chatMessages");
    if (!feed) return;
    if (row.id && Array.from(feed.children).some(child => child.dataset.chatId === row.id)) return;
    const follow = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 32;
    feed.insertAdjacentHTML("beforeend", chatRow(row));
    if (desktopChat.matches) {
      const chat = $("chatPanel");
      if (follow && chat.classList.contains("is-open") && !chat.classList.contains("is-collapsed")) scrollChatToLatest();
      else chat.classList.add("has-new-messages");
    }
  }

  async function loadChat() {
    const payload = await window.Poker8Transport.loadChat().catch(() => ({ messages: [] }));
    const target = $("chatMessages");
    if (!target) return;
    // A socket message can arrive while history is loading. Keep it and
    // deduplicate by id instead of replacing the entire feed with older data.
    const live = Array.from(target.children);
    const rows = payload.messages || [];
    const ids = new Set(rows.map(row => row.id));
    target.innerHTML = rows.map(chatRow).join("");
    for (const node of live) if (!ids.has(node.dataset.chatId)) target.appendChild(node);
    if (desktopChat.matches && $("chatPanel")?.classList.contains("is-open")) scrollChatToLatest();
  }

  function showRejection(reason) {
    const target = $("connectionStatus");
    if (target) target.textContent = `отклонено: ${reason || "неизвестно"}`;
    // The snapshot the action was based on is stale by definition here.
    window.Poker8Transport.resync();
  }

  async function checkRoomOwnership() {
    const response = await fetch("/api/lobby/rooms/mine");
    if (!response.ok) return;
    ownsThisRoom = (await response.json()).room?.id === tableId;
    syncOwnerMenu();
  }

  function syncOwnerMenu() {
    const button = $("mobileDrawerCloseRoom");
    if (button) button.hidden = !ownsThisRoom;
  }

  async function closeOwnRoom() {
    if (!window.confirm("Закрыть комнату? Все, кто за столом, выйдут, а фишки вернутся на балансы.")) return;
    const response = await fetch(`/api/lobby/rooms/${encodeURIComponent(tableId)}/close`, { method: "POST" });
    if (!response.ok) return alert("Не удалось закрыть комнату. Попробуйте ещё раз.");
    window.Poker8Transport.disconnect();
    location.href = "/";
  }

  async function returnToLobby() {
    // Do not call /leave here: closing the socket changes a seated player to
    // held, which preserves the place for a short reconnect window.
    if (viewerState === "waiting") await window.Poker8Transport.cancelReady();
    window.Poker8Transport.disconnect();
    location.href = "/";
  }

  async function leaveTable() {
    // Fired, not awaited. Folding a hand out can take the server a few
    // seconds, and there is nothing in the answer this page needs -- waiting
    // for it only left the player staring at a table they had already left.
    // The request outlives the navigation; the lobby shows the wait and
    // re-sends the leave if it never landed.
    if (viewerState === "waiting") {
      await window.Poker8Transport.cancelReady();
    } else if (["seated", "held"].includes(viewerState)) {
      await window.Poker8Transport.leaveInBackground();
    }
    window.Poker8Transport.disconnect();
    location.href = "/";
  }

  function bindControls() {
    // Delegated on document, not the seat element: v038 rebuilds seat markup
    // on every render, so a direct listener would be lost the moment a
    // snapshot redraws the table.
    document.addEventListener("click", event => {
      if (!event.target?.closest?.('.seat[data-visual-seat="0"] .avatar-wrap')) return;
      readyUp().catch(error => { alert(error.message); });
    });
    document.addEventListener("keydown", event => {
      if (!["Enter", " "].includes(event.key)) return;
      if (!event.target?.matches?.('.seat[data-visual-seat="0"] .avatar-wrap')) return;
      event.preventDefault();
      readyUp().catch(error => { alert(error.message); });
    });
    // Delegated, like the hero avatar above and for the same reason: the
    // mobile layers rebuild the seat ring on every snapshot, so a listener
    // bound to a seat button dies with the node it was bound to.
    document.addEventListener("click", event => {
      const button = event.target?.closest?.("[data-add-seat]");
      if (!button) return;
      event.preventDefault();
      // Once the request is in, this same chair reads "ВАШЕ МЕСТО" (v040), so
      // pressing it is a press on your own reservation -- it gives the seat
      // back. No confirm: the header's "Отменить" does not ask either, and
      // this is the same action in the place people look for it first.
      if (viewerState === "waiting") {
        cancelQueue().catch(error => alert(error.message));
        return;
      }
      // The same dialog the header's "Занять место" opens. Sitting down from
      // the felt used to skip it and buy in for a flat 40 ББ, so the two ways
      // into the same seat bought different stacks.
      showBuyInDialog(Number(button.dataset.addSeat));
    });
    $("mobileDrawerTakeSeat")?.addEventListener("click", () => {
      ready().catch(error => alert(error.message));
    });
    $("mobileDrawerCloseRoom")?.addEventListener("click", () => closeOwnRoom().catch(error => alert(error.message)));
    $("mobileDrawerLobby")?.addEventListener("click", () => returnToLobby().catch(error => alert(error.message)));
    $("mobileDrawerLeave")?.addEventListener("click", async () => {
      // Leaving your own room does not close it, and one player may have only
      // one open room at a time -- so somebody who left and then tried to open
      // another was told they already had one, with no idea which or why. Say
      // it here instead of letting them find out in the lobby.
      const message = ownsThisRoom
        ? "Выйти из своей комнаты? Без игроков она закроется сама через 1,5 минуты — или закройте её сразу кнопкой «Закрыть комнату»."
        : viewerState === "waiting"
          ? "Отменить очередь на место?"
          : "Покинуть стол? Во время раздачи выход будет выполнен после её завершения.";
      if (window.confirm(message)) await leaveTable().catch(error => alert(error.message));
    });
    // Delegated, because v037 creates this button and v037 runs after boot:
    // binding to it here found nothing, and the ?. swallowed that silently, so
    // the button sat in the header doing nothing and said nothing about it.
    document.addEventListener("click", event => {
      const button = event.target?.closest?.("#mobileChatButton");
      if (!button) return;
      const chat = $("chatPanel");
      if (!chat) return;
      const open = !chat.classList.contains("is-open");
      ensureChatFurniture();
      chat.classList.toggle("is-open", open);
      chat.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      if (open && desktopChat.matches) {
        setChatCollapsed(false);
        if (!chat.dataset.p8Opened) {
          chat.dataset.p8Opened = "1";
          scrollChatToLatest();
        }
        chatEditor()?.focus();
      }
      syncChatTurnBanner();
    });
    // The banner and the cross both put the table back in front of you.
    document.addEventListener("click", event => {
      if (event.target?.closest?.(".chat-turn-banner, .chat-close")) closeChat();
    });
    // Reading a conversation must never be why a hand was missed, so Escape
    // gets out too.
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && $("chatPanel")?.classList.contains("is-open")) closeChat();
    });
    // Same reason as the chat button above: v037 creates it, and v037 runs
    // after boot.
    document.addEventListener("click", event => {
      if (event.target?.closest?.("#mobileHintButton")) {
        const modal = $("handRankingsModal");
        if (modal) modal.hidden = !modal.hidden;
        return;
      }
      if (event.target?.closest?.(".hr-backdrop, #handRankingsClose")) {
        const modal = $("handRankingsModal");
        if (modal) modal.hidden = true;
      }
    });
    document.addEventListener("keydown", event => {
      const modal = $("handRankingsModal");
      if (event.key === "Escape" && modal && !modal.hidden) modal.hidden = true;
    });
    $("readyButton")?.addEventListener("click", () => ready().catch(error => { alert(error.message); }));
    // The toolbar wraps the selection; an empty selection drops the pair in and
    // leaves the caret between them, so it works as "start writing in bold" too.
    const MARKERS = {bold: "**", italic: "*", strike: "~~", code: "`", spoiler: "||"};
    $("chatFormat")?.addEventListener("click", event => {
      const button = event.target?.closest?.("[data-chat-format]");
      if (!button) return;
      const kind = button.dataset.chatFormat;
      const input = chatEditor();
      if (kind === "link") {
        window.Poker8ChatFormat?.wrapSelection(input, "[", "](https://)");
        return;
      }
      const marker = MARKERS[kind];
      if (marker) window.Poker8ChatFormat?.wrapSelection(input, marker);
    });
    // Spoilers are click-to-reveal, and delegated because the feed is redrawn
    // whole on every message.
    $("chatMessages")?.addEventListener("click", event => {
      const spoiler = event.target?.closest?.("[data-chat-spoiler]");
      if (spoiler) spoiler.classList.add("is-revealed");
    });
    $("chatForm")?.addEventListener("submit", async event => {
      event.preventDefault();
      const input = chatEditor();
      const text = input?.value.trim();
      const status = $("chatPanel").querySelector(".chat-send-status");
      if (!text || chatSending) return;
      if (text.length > 1000) {
        status.textContent = `Слишком длинное сообщение (${text.length}/1000). Черновик сохранён.`;
        return;
      }
      const draft = input.value;
      const button = $("chatForm").querySelector('button[type="submit"]');
      chatSending = true;
      button.disabled = true;
      status.textContent = "";
      try {
        const row = await window.Poker8Transport.sendChat(text);
        appendChat(row);
        if (input.value === draft) {
          input.value = "";
          $("chatInput").value = "";
          $("chatDesktopInput").value = "";
        }
        if (desktopChat.matches) scrollChatToLatest();
      } catch (error) {
        status.textContent = "Не удалось отправить. Черновик сохранён — попробуйте ещё раз.";
        if (!desktopChat.matches) alert(status.textContent);
      } finally {
        chatSending = false;
        button.disabled = false;
      }
    });
  }

  async function boot() {
    bindControls();
    // Table pages must authenticate the Telegram Mini App before the first
    // snapshot; otherwise a retained guest cookie masks the real @username.
    await window.Poker8Auth?.ensureSession?.();
    // Ownership never changes while the page is open, so this is asked once.
    // A failure here only costs the owner their two menu items, so it must not
    // take the rest of the table down with it.
    await checkRoomOwnership().catch(() => {});
    await refreshState();
    clearInterval(pollTimer);
    // The socket now carries coordinator-driven changes too, so this is only a
    // safety net for a dropped connection.
    pollTimer = setInterval(() => refreshState().catch(() => {}), 3000);
    window.Poker8Transport.connect(tableId, {
      onStatus: status => setText("connectionStatus", status),
      onMessage: message => {
        if (message.state) renderSnapshot(message.state);
        if (message.type === "chat") appendChat(message.message || {});
        if (message.type === "command_rejected") showRejection(message.reason);
      },
    });
    await loadChat();
  }

  boot().catch(error => {
    setText("connectionStatus", "ошибка");
    const target = $("result");
    if (target) target.textContent = error.message;
  });
})();
