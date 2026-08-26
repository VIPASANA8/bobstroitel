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
    .poker8-online.p8-action-pending #actionButtons::after{content:'Отправляем действие…';display:block;grid-column:1 / -1;text-align:center;color:#a8ffd4;font-size:10px;font-weight:800;padding:5px}
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
      /* Was absolutely positioned at left:50% + translate(-50%,-50%) to centre
         the pair on the header regardless of the buttons on either side. Out
         of flow, nothing reserved its width: with both Russian labels showing,
         the group runs ~198px wide and centres to x:88-286 on a 374px screen,
         while the right-hand utility group (two 42px buttons + 8px gap, 13px
         padding) starts at x:269 -- so the chat button painted on top of
         "Наблюдать" and the hint button ran off the edge. In flow, the
         header's own space-between still puts it in the middle and makes the
         overlap structurally impossible at any width. */
      .poker8-online .mobile-header-seat-actions{
        display:flex;order:1;gap:6px;min-width:0;
        /* The pair used to butt straight up against the hamburger on one
           side and the chat/hint icons on the other -- fine once nothing
           overlapped, but still touching both edges of its own slot. This
           margin is the slack that keeps it visibly clear of both. */
        margin:0 4px;
      }
      .poker8-online .mobile-header-seat-actions[hidden]{display:none!important}
      /* Header is position:fixed already, so this centres on the header
         itself regardless of the hamburger/utility groups' own widths --
         safe here specifically because the wider two-button pair (the one
         that overlapped chat/hint when this trick was tried for it) is
         always hidden while this class is on. */
      .poker8-online .mobile-header-seat-actions.ready-up-only{
        position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);margin:0;
      }
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
         pair on every click. 88px fits the longer label of each pair with
         the tighter padding above; text-align centres the shorter one in it
         instead of hugging the left edge. */
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat,
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve{
        width:88px;text-align:center;
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
      /* The picked mode gets a moving gradient ring instead of a flat border --
         a 1px inset keeps the button's own background as the solid interior,
         so only the ring itself shows the gradient/shimmer. */
      .poker8-online .mobile-header-seat-actions button.mode-active{
        /* !important: #mobileHeaderObserve's own id rule sets border-color
           too, and an id always outranks this class selector on specificity. */
        position:relative;border-color:transparent!important;color:#eafff6;
      }
      /* Both the ring and the halo below used to fade to 62% with the rest
         of the button under button:disabled's own opacity -- for
         #mobileHeaderTakeSeat that's exactly "В очереди", the one state
         this glow exists to announce, so it was dimming the very thing it
         was supposed to highlight. */
      .poker8-online .mobile-header-seat-actions button.mode-active:disabled{opacity:1;}
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat.mode-active{
        box-shadow:0 0 16px rgba(64,237,167,.55);
      }
      /* A wedge of the button's own accent colour, riding a rotating
         --glow-angle around the ring -- not a shimmer sliding side to side,
         an actual point of light that travels the full perimeter. */
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat.mode-active::before{
        content:"";position:absolute;inset:-1px;z-index:-1;border-radius:inherit;
        background:conic-gradient(from var(--glow-angle),transparent 0 75%,#7dfff0 88%,transparent 100%);
        animation:p8HeaderGlowSpin 2.6s linear infinite;
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderTakeSeat.mode-active::after{
        content:"";position:absolute;inset:1px;z-index:-1;border-radius:inherit;background:#0a3b2b;
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve.mode-active{
        color:#f2e9ff;box-shadow:0 0 16px rgba(201,168,255,.55);
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve.mode-active::before{
        content:"";position:absolute;inset:-1px;z-index:-1;border-radius:inherit;
        background:conic-gradient(from var(--glow-angle),transparent 0 75%,#eaddff 88%,transparent 100%);
        animation:p8HeaderGlowSpin 2.6s linear infinite;
      }
      .poker8-online .mobile-header-seat-actions #mobileHeaderObserve.mode-active::after{
        content:"";position:absolute;inset:1px;z-index:-1;border-radius:inherit;background:#24103e;
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
      @property --glow-angle{syntax:'<angle>';inherits:false;initial-value:0deg}
      @keyframes p8HeaderGlowSpin{to{--glow-angle:360deg}}
      @media (prefers-reduced-motion:reduce){
        .poker8-online .mobile-header-seat-actions button.mode-active::before{animation:none}
      }
      /* Was .mobile-chat-button itself, back when it sat directly in the
         header next to #mobileHeaderSeatActions -- v037 and this file append
         their header items independently, so whichever ran last used to
         decide the visual order. Chat now sits inside its own utility group
         with the rankings hint (see v037's ensureChatButton); the order
         belongs on that group so it is still always last/rightmost. */
      .poker8-online .mobile-header-utility{order:2}
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
    const layout = document.querySelector(".layout");
    if (!panel || !felt || !layout) return;
    if (mobileQuery?.matches) {
      if (panel.parentElement !== felt) felt.append(panel);
    } else if (panel.parentElement !== layout) {
      layout.prepend(panel);
    }
  }
  placeReadyPanel();
  mobileQuery?.addEventListener?.("change", placeReadyPanel);

  const units = value => Math.round(Number(value || 0));
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#003399;",
  }[char]));
  let table = null;
  let viewerState = "spectator";
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

  function countdownText(state) {
    const phase = state?.phase;
    if (phase !== "result" && phase !== "countdown") return "";
    // Both phases count to the same moment. The result phase used to count to
    // result_clear_at -- three seconds earlier -- while promising the next
    // hand, so the number ran down to one, then jumped back up and started
    // again the instant the phase changed.
    const target = state.next_hand_at || (phase === "result" ? state.result_clear_at : null);
    if (!target) return "";
    const seconds = Math.max(0, Math.ceil((Date.parse(target) - Date.now()) / 1000));
    return `Следующая раздача через ${seconds} сек.`;
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
      if (row?.id === viewerId) return Number(seatNo);
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
      ready(null, bb).catch(error => alert(error.message));
    });
    return dialog;
  }

  // min/max_buy_in_bb come straight off the table row (see catalogue.py) --
  // every table can set its own range, so nothing here is hardcoded.
  function showBuyInDialog() {
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
    const seatNo = viewerState === "seated" ? viewerSeatNo(state) : null;
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
  }

  function closeChat() {
    const chat = $("chatPanel");
    if (!chat) return;
    chat.classList.remove("is-open");
    chat.hidden = true;
    $("mobileChatButton")?.setAttribute("aria-expanded", "false");
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
    setText("newHandCountdown", countdownText(state));
    const countdown = $("newHandCountdown");
    if (countdown) countdown.hidden = !countdownText(state);

    const observerMode = ["spectator", "waiting"].includes(viewerState);
    document.body.classList.toggle("p8-observer-mode", observerMode);
    ensureHeaderSeatButtons();
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
    viewerState = payload.viewer_state || viewerState;
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
    if (readyUpInFlight || viewerState !== "seated" || !isPreHand()) return;
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
  const chatRow = row => `<div class="p8-chat-row"><b>${escapeHtml(row.display_name || "Игрок")}</b> ${chatText(row.text)}</div>`;

  function appendChat(row) {
    $("chatMessages")?.insertAdjacentHTML("beforeend", chatRow(row));
  }

  async function loadChat() {
    const payload = await window.Poker8Transport.loadChat().catch(() => ({ messages: [] }));
    const target = $("chatMessages");
    if (!target) return;
    target.innerHTML = (payload.messages || []).map(chatRow).join("");
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
      if (!event.target?.closest?.('.seat[data-visual-seat="0"] .avatar-wrap, .v038-room-prompt')) return;
      readyUp().catch(error => { alert(error.message); });
    });
    document.addEventListener("keydown", event => {
      if (!["Enter", " "].includes(event.key)) return;
      if (!event.target?.matches?.('.seat[data-visual-seat="0"] .avatar-wrap, .v038-room-prompt')) return;
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
      ready(Number(button.dataset.addSeat)).catch(error => alert(error.message));
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
      const input = $("chatInput");
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
      const input = $("chatInput");
      const text = input?.value.trim();
      if (!text) return;
      await window.Poker8Transport.sendChat(text);
      input.value = "";
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
