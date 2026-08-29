(() => {
  "use strict";

  const isMobileV2 = () => window.matchMedia?.("(max-width: 780px)")?.matches ?? false;

  const style = document.createElement("style");
  style.id = "v038-poker8-v2-cinematic-table-style";
  style.textContent = `
    /* Was @media (max-width:780px). The v2 table is the table now, at every
       width; desktop geometry is tuned in v039. */
    @media all{
      body.v014.poker8-v2-sixmax{
        --p8-wood-dark:#0c0503;
        --p8-wood-mid:#51270f;
        --p8-felt:#003b24;
        --p8-perspective:900px;
        --p8-hud-h:214px;
        --p8-bottom-reserve:46px;
        --table-stage-h:calc(100dvh - 50px - var(--p8-hud-h) - var(--p8-bottom-reserve))!important;
        --seat-0-x:50%!important;--seat-0-y:80%!important;
        --seat-1-x:7%!important;--seat-1-y:58%!important;
        --seat-2-x:7%!important;--seat-2-y:22%!important;
        --seat-3-x:50%!important;--seat-3-y:13%!important;
        --seat-4-x:84%!important;--seat-4-y:22%!important;
        --seat-5-x:84%!important;--seat-5-y:58%!important;
        --pot-y:25%!important;
        --pot-chips-y:47%!important;
        --board-y:38%!important;
        background:
          linear-gradient(90deg,rgba(0,0,0,.55),transparent 20%,transparent 80%,rgba(0,0,0,.55)),
          repeating-linear-gradient(96deg,#000000 0 7px,#180b05 8px 14px,#0c0503 15px 23px)!important;
      }

      body.v014.poker8-v2-sixmax .mobile-game-header::after{display:none!important;content:none!important;}
      body.v014.poker8-v2-sixmax .mobile-game-header{
        background-image:
          linear-gradient(90deg,rgba(0,0,0,.86),transparent 38%,transparent 62%,rgba(0,0,0,.86)),
          url("/static/assets/poker8-v2-table-mobile.webp")!important;
        background-size:100% 100%,100vw calc(var(--table-stage-h) + 50px)!important;
        background-position:center,center top!important;
        background-repeat:no-repeat!important;
        border-bottom-color:rgba(29,255,192,.10)!important;
        box-shadow:0 10px 24px rgba(0,0,0,.44)!important;
      }

      /* style.css sizes .layout/.left-column to the full viewport, and
         component-ui.css only undoes that for :not(.poker8-v2-sixmax). Left as
         is here, the left column alone fills .app-shell's whole content box, so
         the .sidebar holding the action panel is laid out *past* the bottom of
         .app-shell -- which is overflow:hidden, so every action button becomes
         invisible and unreachable with no way to scroll to it. The table frame
         is already pinned to --table-stage-h and the panel to --p8-hud-h, and
         those two exactly fill the content box, so the column only has to stop
         claiming height it was never meant to own. */
      body.v014.poker8-v2-sixmax .layout,
      body.v014.poker8-v2-sixmax .left-column{
        min-height:0!important;height:auto!important;flex:none!important;
      }

      body.v014.poker8-v2-sixmax .table-frame{
        height:var(--table-stage-h)!important;
        min-height:var(--table-stage-h)!important;
        perspective:var(--p8-perspective)!important;
        perspective-origin:50% 22%!important;
        overflow:visible!important;
      }

      /* $= (suffix match), not =, so a spectator's "spectator-N" dataset (v040)
         still resolves a hexagon slot -- an exact ="N" match leaves every
         spectator seat with no left/top at all, and every earlier layer
         (component-ui.css, v032, v039) has the same exact-match gap, so
         nothing in the chain positions a spectator's seats. */
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="0"]{left:50%!important;top:80%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="1"]{left:7%!important;top:58%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="2"]{left:7%!important;top:22%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="3"]{left:50%!important;top:13%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="4"]{left:84%!important;top:22%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="5"]{left:84%!important;top:58%!important;}

      body.v014.poker8-v2-sixmax .table-frame{
        padding:0 5px 1px!important;
        background-image:
          linear-gradient(90deg,rgba(0,0,0,.48),transparent 14%,transparent 86%,rgba(0,0,0,.48)),
          url("/static/assets/poker8-v2-table-mobile.webp")!important;
        background-size:100vw calc(var(--table-stage-h) + 50px)!important;
        background-position:center,center -50px!important;
        background-repeat:no-repeat!important;
        box-shadow:inset 0 10px 20px rgba(0,0,0,.20),inset 0 -10px 22px rgba(0,0,0,.34),0 0 30px rgba(0,0,0,.34)!important;
      }

      body.v014.poker8-v2-sixmax .felt{
        width:calc(100% - 44px)!important;
        box-sizing:border-box!important;
        margin-inline:auto!important;
        border:0!important;
        border-radius:49% / 36%!important;
        /* Was rotateX(5deg) scale(.985,1.025) with preserve-3d. Every child
           that shows counter-rotated by -5deg to sit upright again, so the
           tilt cancelled out -- but the scale did not, and it sized every
           seat plate to a fractional pixel: 92.4 instead of 92. Text
           rasterised at one size and resampled at another is what "blurry
           nicknames" was. The felt's shape comes from its border-radius. */
        transform-origin:50% 54%!important;
        background:transparent!important;
        outline:0!important;
        box-shadow:none!important;
      }

      body.v014.poker8-v2-sixmax .felt::before,
      body.v014.poker8-v2-sixmax .felt::after{display:none!important;}


      body.v014.poker8-v2-sixmax .table-glow{
        display:none!important;
        inset:10%!important;
        border-radius:50%!important;
        background:radial-gradient(ellipse,rgba(21,121,74,.15),transparent 68%)!important;
      }

      body.v014.poker8-v2-sixmax .seat{width:69px!important;height:77px!important;min-height:0!important;}
      /* $= (suffix match) so a spectator's "spectator-N" dataset (v040) still
         resolves an accent color -- an exact ="N" match leaves it undefined,
         which silently drops every hsla(var(--seat-accent)…) declaration below. */
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="0"]{--seat-accent:195;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="1"]{--seat-accent:190;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="2"]{--seat-accent:282;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="3"]{--seat-accent:142;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="4"]{--seat-accent:34;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat$="5"]{--seat-accent:300;}

      body.v014.poker8-v2-sixmax .seat-card{
        --seat-neon:hsl(var(--seat-accent),92%,62%);
        width:100%!important;height:100%!important;min-height:0!important;padding:0!important;
        border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;overflow:visible!important;
      }
      body.v014.poker8-v2-sixmax .seat-card:is(.v032-in-hand,.v032-active-turn,.all-in){
        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;
      }

      body.v014.poker8-v2-sixmax .seat-card::before,
      body.v014.poker8-v2-sixmax .seat-card::after{display:none!important;content:none!important;background:none!important;box-shadow:none!important;}

      body.v014.poker8-v2-sixmax .avatar-wrap{
        position:absolute!important;z-index:4;left:50%!important;top:4px!important;transform:translateX(-50%)!important;
        width:49px!important;height:49px!important;margin:0!important;
        isolation:isolate;
      }
      body.v014.poker8-v2-sixmax .avatar-wrap::before,
      body.v014.poker8-v2-sixmax .avatar-wrap::after{
        content:"";
        position:absolute;
        z-index:-2;
        top:-23px;
        width:39px;height:52px;
        border:1px solid hsla(var(--seat-accent),95%,72%,.78);
        border-radius:5px;
        background:
          radial-gradient(circle at 50% 48%,transparent 0 5px,hsla(var(--seat-accent),85%,72%,.35) 5px 6px,transparent 6px),
          repeating-linear-gradient(45deg,hsla(var(--seat-accent),65%,36%,.74) 0 3px,hsla(var(--seat-accent),65%,15%,.96) 3px 6px),
          #000000;
        box-shadow:inset 0 0 0 2px rgba(0,0,0,.54),0 0 13px hsla(var(--seat-accent),95%,56%,.34),0 6px 10px rgba(0,0,0,.58);
      }
      body.v014.poker8-v2-sixmax .avatar-wrap::before{left:-8px;transform:rotate(-12deg);transform-origin:bottom right;}
      body.v014.poker8-v2-sixmax .avatar-wrap::after{right:-8px;transform:rotate(12deg);transform-origin:bottom left;}
      body.v014.poker8-v2-sixmax .seat-card:has(.player-cards:not(:empty)) .avatar-wrap::before,
      body.v014.poker8-v2-sixmax .seat-card:has(.player-cards:not(:empty)) .avatar-wrap::after{opacity:0;}
      /* These two are decoration for an idle table, not real cards. Once a hand
         is running a seat either holds actual cards -- which hide them via the
         rule above -- or is sitting the hand out, and then a pair of card backs
         behind the avatar says the opposite of the prompt telling that player
         the hand is going on without them. p8-no-pot marks "no hand at all". */
      body.v014.poker8-v2-sixmax:not(.p8-no-pot) .avatar-wrap::before,
      body.v014.poker8-v2-sixmax:not(.p8-no-pot) .avatar-wrap::after{opacity:0;}
      body.v014.poker8-v2-sixmax.v038-room-awaiting .avatar-wrap::before,
      body.v014.poker8-v2-sixmax.v038-room-awaiting .avatar-wrap::after,
      body.v014.poker8-v2-sixmax.v038-room-resetting .avatar-wrap::before,
      body.v014.poker8-v2-sixmax.v038-room-resetting .avatar-wrap::after,
      body.v014.poker8-v2-sixmax.v038-hand-complete .avatar-wrap::before,
      body.v014.poker8-v2-sixmax.v038-hand-complete .avatar-wrap::after{opacity:0!important;}

      body.v014.poker8-v2-sixmax .player-avatar{
        position:relative!important;
        width:49px!important;height:49px!important;
        transition:border-color 220ms ease,box-shadow 220ms ease,filter 220ms ease!important;
        border:2px solid hsla(var(--seat-accent),100%,70%,.88)!important;
        background-image:var(--profile-avatar-image,radial-gradient(circle at 50% 32%,hsla(var(--seat-accent),62%,46%,.45),transparent 31%),radial-gradient(circle at 50% 78%,#07100f 0 42%,#000000 70%))!important;
        background-position:center!important;
        background-size:cover!important;
        color:#effbf4!important;
        box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 16px hsla(var(--seat-accent),96%,58%,.46),inset 0 -10px 18px rgba(0,0,0,.50)!important;
        font-size:15px!important;
      }
      body.v014.poker8-v2-sixmax .player-avatar span{opacity:0!important;}
      body.v014.poker8-v2-sixmax .player-avatar::before{
        content:"";position:absolute;z-index:2;left:16%;right:16%;top:14%;height:52%;border-radius:48% 48% 42% 42% / 54% 54% 32% 32%;
        background:
          radial-gradient(ellipse at 50% 45%,rgba(7,16,15,.22) 0 24%,rgba(0,0,0,.90) 55%,#000000 76%),
          linear-gradient(135deg,hsla(var(--seat-accent),58%,24%,.62),#000000 58%);
        clip-path:polygon(50% 0,84% 16%,100% 72%,76% 92%,63% 68%,50% 61%,37% 68%,24% 92%,0 72%,16% 16%);
        filter:drop-shadow(0 0 5px hsla(var(--seat-accent),92%,60%,.32));
      }
      body.v014.poker8-v2-sixmax .player-avatar::after{
        content:"";position:absolute;z-index:1;left:7%;right:7%;bottom:-3%;height:54%;border-radius:50% 50% 42% 42%;
        background:radial-gradient(ellipse at 50% 0,hsla(var(--seat-accent),52%,24%,.30),transparent 50%),linear-gradient(160deg,#07100f,#000000 72%);
        clip-path:polygon(17% 13%,39% 0,61% 0,83% 13%,100% 100%,0 100%);
      }
      body.v014.poker8-v2-sixmax .player-avatar[style*="--profile-avatar-image"]::before,
      body.v014.poker8-v2-sixmax .player-avatar[style*="--profile-avatar-image"]::after{display:none!important;}
      body.v014.poker8-v2-sixmax .player-avatar[style*="--profile-avatar-image"] span{opacity:1!important;}

      body.v014.poker8-v2-sixmax .seat-identity{
        position:absolute!important;z-index:6;left:50%!important;top:47px!important;transform:translateX(-50%)!important;
        width:84px!important;min-height:32px!important;padding:3px 6px 4px!important;border-radius:8px!important;
        transition:border-color 220ms ease,box-shadow 220ms ease,filter 220ms ease!important;
        border:1px solid hsla(var(--seat-accent),90%,60%,.72)!important;background:linear-gradient(180deg,rgba(0,0,0,.98),rgba(0,0,0,.995))!important;
        box-shadow:0 0 12px hsla(var(--seat-accent),92%,55%,.24),0 7px 14px rgba(0,0,0,.62)!important;text-align:center!important;
      }
      /* What this player has put in this street, written where they are
         rather than on the felt beside them. The avatar is 49px and the
         number can be five characters, so it takes the middle of the disc on
         its own ground -- the silhouette behind it is decoration, the number
         is not. */
      body.v014.poker8-v2-sixmax .player-avatar{position:relative!important;}
      body.v014.poker8-v2-sixmax .seat-wager{
        position:absolute!important;left:50%!important;top:50%!important;
        transform:translate(-50%,-50%)!important;z-index:4;
        min-width:34px;padding:2px 5px;border-radius:7px;
        background:rgba(9,10,10,.86);
        color:#eafff6;font-size:12px;font-weight:900;line-height:1;letter-spacing:-.01em;
        font-variant-numeric:tabular-nums;text-align:center;white-space:nowrap;
        box-shadow:0 1px 4px rgba(0,0,0,.55);
      }
      /* The felt between the players and the pot is empty now. */
      body.v014.poker8-v2-sixmax .wager-layer .bet-marker{display:none!important;}

      body.v014.poker8-v2-sixmax .seat-topline{display:block!important;}
      /* The name takes the whole plate; seatDisplayName measures what it hands
         over so it lands, and CSS finishes anything still too long. */
      body.v014.poker8-v2-sixmax .seat-name{max-width:100%!important;font-size:10px!important;line-height:1.1!important;}
      body.v014.poker8-v2-sixmax .seat-stack{margin-top:1px!important;font-size:15px!important;line-height:1!important;color:var(--seat-neon)!important;}
      body.v014.poker8-v2-sixmax .seat-name,
      body.v014.poker8-v2-sixmax .seat-stack{margin-inline:auto!important;}
      body.v014.poker8-v2-sixmax .bot-level{display:none!important;}
      body.v014.poker8-v2-sixmax .position-chip{display:none!important;font-size:10px!important;padding:1px 3px!important;}
      body.v014.poker8-v2-sixmax .seat-meta{margin-top:3px!important;}
      body.v014.poker8-v2-sixmax .seat-card > .v024-ready-badge{display:none!important;}
      body.v014.poker8-v2-sixmax .player-status:is(.status-fold,.status-turn,.status-thinking){display:none!important;}
      body.v014.poker8-v2-sixmax .v028-center-ready{display:none!important;}
      body.v014.poker8-v2-sixmax .deck-anchor{display:none!important;}

      /* Dead center of the felt -- verified against the live table: the pot
         chips sat at this exact row before the pot moved to flank the amount
         (see .pot-chips below), so 50% is the felt's real visual middle, not
         a guess. Nothing else occupies that ground before a hand deals. */
      body.v014.poker8-v2-sixmax .v038-ready-countdown{
        position:absolute;z-index:74;left:50%;top:50%;transform:translate(-50%,-50%);
        display:none;place-items:center;width:62px;height:62px;border-radius:50%;
        border:2px solid #72ffb5;background:rgba(6,22,17,.88);color:#eafff6;
        box-shadow:0 0 0 3px rgba(0,0,0,.72),0 0 22px rgba(72,255,169,.58),inset 0 0 18px rgba(72,255,169,.14);
        font-size:27px;font-weight:950;text-shadow:0 0 10px rgba(91,255,194,.86);pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .v038-ready-countdown.visible{display:grid;}

      body.v014.poker8-v2-sixmax .v038-turn-timer,
      body.v014.poker8-v2-sixmax .v038-turn-context{
        position:absolute;z-index:73;bottom:18px;display:none;pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .v038-turn-timer.visible{display:grid;}
      body.v014.poker8-v2-sixmax .v038-turn-timer{
        left:calc(25% - 20.5px);width:54px;height:54px;transform:translateX(-50%);place-items:center;border-radius:50%;
        background:conic-gradient(var(--turn) var(--timer-progress,100%),var(--turn-dim) 0);
        filter:drop-shadow(0 0 9px color-mix(in srgb,var(--turn) 66%,transparent));
      }
      body.v014.poker8-v2-sixmax .v038-turn-timer::before{
        content:"";position:absolute;inset:4px;border-radius:50%;background:#07100f;border:1px solid color-mix(in srgb,var(--turn) 72%,transparent);
      }
      body.v014.poker8-v2-sixmax .v038-turn-timer b{position:relative;color:#ffffff;font-size:20px;line-height:1;text-shadow:0 0 7px var(--turn);}
      /* No number, so no unit under it. */
      body.v014.poker8-v2-sixmax .v038-turn-timer.v038-untimed small{display:none!important;}
      body.v014.poker8-v2-sixmax .v038-turn-timer small{position:absolute;bottom:-11px;color:color-mix(in srgb,var(--turn) 62%,#ffffff);font-size:10px;font-weight:900;letter-spacing:.08em;}
      body.v014.poker8-v2-sixmax .v038-turn-context.visible{display:block;}
      body.v014.poker8-v2-sixmax .v038-turn-context{
        left:calc(75% + 20.5px);transform:translateX(-50%);width:max-content;min-width:82px;max-width:116px;padding:6px 8px;border:1px solid #2de8df;border-radius:9px;
        background:rgba(2,19,18,.92);color:#dffffc;text-align:center;box-shadow:0 0 14px rgba(45,232,223,.38);
      }
      body.v014.poker8-v2-sixmax .v038-turn-context span{display:block;color:#ecfffd;font-size:10px;font-weight:850;line-height:1;}

      body.v014.poker8-v2-sixmax.v028-prehand-center-ready .seat[data-visual-seat="0"] .avatar-wrap{
        cursor:pointer!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap.v038-viewer-ready .player-avatar{
        filter:brightness(.38) saturate(.72)!important;
        transition:filter 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .v038-ready-mark{
        position:absolute;z-index:12;inset:4px;display:none;place-items:center;border-radius:50%;
        border:2px solid #72ffb5;background:rgba(4,31,20,.38);color:#dfffee;
        box-shadow:0 0 0 2px rgba(0,8,5,.72),0 0 18px rgba(72,255,169,.72),inset 0 0 14px rgba(75,255,181,.18);
        font-size:27px;font-weight:950;line-height:1;text-shadow:0 0 10px rgba(104,255,190,.95);pointer-events:none;
      }
      body.v014.poker8-v2-sixmax.v028-prehand-center-ready .avatar-wrap.v038-viewer-ready .v038-ready-mark{display:grid;}
      /* v028 only marks "no hand at all", so while a hand ran without this seat
         the checkmark had nowhere to appear and a card over the felt had to say
         it in words. p8-can-ready marks the real condition -- a ready toggle is
         available right now -- which also covers sitting a running hand out. */
      body.v014.poker8-v2-sixmax.p8-can-ready .avatar-wrap.v038-viewer-ready .v038-ready-mark{display:grid;}
      body.v014.poker8-v2-sixmax .v038-ready-mark small{
        position:absolute;right:-7px;bottom:-5px;display:grid;place-items:center;width:25px;height:25px;border-radius:50%;
        border:1px solid #71ffc1;background:#031b13;color:#ffffff;font-size:12px;font-weight:950;
        box-shadow:0 0 12px rgba(75,255,181,.70);
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-card{
        min-height:0!important;padding:0!important;border:0!important;box-shadow:none!important;
      }
      /* Avatar size and position are dropped here on purpose (item 5: every
         seat's avatar is now the same size, hero included) -- only the
         cosmetic "this is you" cue (border color) stays hero-specific. */
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{border-color:#35bfff!important;font-size:15px!important;}
      /* Plate stays the same width and position as every other seat's --
         a wider hero plate was the last piece of asymmetric hero sizing. */
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-name{font-size:10px!important;max-width:100%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{font-size:15px!important;color:#35c6ff!important;}

      body.v014.poker8-v2-sixmax .seat-card.v038-action-fold .player-avatar{
        border-color:#ff4d42!important;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 20px rgba(255,77,66,.64),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v038-action-passive .player-avatar{
        border-color:#55cfff!important;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 20px rgba(85,207,255,.62),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v038-action-aggressive .player-avatar{
        border-color:#55f16e!important;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 20px rgba(85,241,110,.62),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v038-action-all-in .player-avatar{
        border-color:#ffc44d!important;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 22px rgba(255,196,77,.70),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v032-folded.v038-action-fold{opacity:1!important;filter:none!important;}

      body.v014.poker8-v2-sixmax .v038-room-prompt{
        /* y:36% sits over the pot/board strip, which is empty whenever this
           prompt shows (no hand running) -- and it's the one vertical band
           every seat layout now deliberately avoids, so the prompt can no
           longer land on top of another seat's avatar.

           At max-width:78% the card reached almost edge to edge on a 321px
           felt. Narrower, every local-room message wraps instead of reaching
           toward the side seats. */
        position:absolute;z-index:72;left:50%;top:var(--p8-prompt-y, 36%);transform:translate(-50%,-50%);display:none;width:max-content;max-width:64%;
        padding:10px 14px;border:1px solid rgba(61,235,190,.58);border-radius:12px;background:rgba(2,19,18,.88);text-align:center;
        box-shadow:0 0 18px rgba(28,238,188,.22);pointer-events:auto;cursor:pointer;
      }
      body.v014.poker8-v2-sixmax .v038-room-prompt.visible{display:block;}
      /* Past four players the ring closes up and the upper side seats climb
         into the 36% band, so the prompt has to drop below them to stop
         covering an avatar. Still above the pot strip, which is empty
         whenever this prompt is on screen. */
      body.v014.poker8-v2-sixmax.p8-player-count-5,
      body.v014.poker8-v2-sixmax.p8-player-count-6{--p8-prompt-y:47%;}
      body.v014.poker8-v2-sixmax .v038-room-prompt strong{display:block;color:#7dffd0;font-size:15px;line-height:1.05;letter-spacing:.06em;}
      body.v014.poker8-v2-sixmax .v038-room-prompt span{display:block;margin-top:5px;color:#dfffee;font-size:10px;line-height:1.1;}
      body.v014.poker8-v2-sixmax.v038-room-awaiting .seat[data-visual-seat="0"] .avatar-wrap:not(.v038-viewer-ready) .player-avatar,
      body.v014.poker8-v2-sixmax.p8-can-ready .seat[data-visual-seat="0"] .avatar-wrap:not(.v038-viewer-ready) .player-avatar{
        animation:v038ReadyPulse 1.7s ease-in-out infinite;
      }
      body.v014.poker8-v2-sixmax .felt{transition:opacity 260ms ease,filter 260ms ease!important;}
      body.v014.poker8-v2-sixmax.v038-room-resetting .felt{opacity:.18!important;filter:brightness(.42) blur(2px)!important;}
      @keyframes v038ReadyPulse{50%{border-color:#6edcff;box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 28px rgba(53,198,255,.82),inset 0 -10px 18px rgba(0,0,0,.50)}}

      body.v014.poker8-v2-sixmax .player-cards{
        position:absolute!important;z-index:2!important;left:50%!important;top:-13px!important;bottom:auto!important;transform:translateX(-50%)!important;margin:0!important;min-height:0!important;gap:2px!important;
        transition:opacity 220ms ease,transform 220ms ease!important;
      }
      body.v014.poker8-v2-sixmax.v038-room-resetting .player-cards{opacity:0!important;transform:translateX(-50%) translateY(-12px) scale(.92)!important;}
      body.v014.poker8-v2-sixmax.v038-hand-complete .player-cards{opacity:0!important;transform:translateX(-50%) translateY(-12px) scale(.92)!important;}
      body.v014.poker8-v2-sixmax .player-cards .card.back{
        width:34px!important;height:48px!important;border-radius:5px!important;
        border:1px solid hsla(var(--seat-accent),95%,75%,.80)!important;
        background:
          radial-gradient(circle at center,transparent 0 6px,hsla(var(--seat-accent),90%,74%,.42) 6px 7px,transparent 7px),
          repeating-linear-gradient(45deg,hsla(var(--seat-accent),62%,38%,.74) 0 3px,hsla(var(--seat-accent),62%,16%,.96) 3px 6px)!important;
        box-shadow:inset 0 0 0 2px rgba(0,0,0,.48),0 4px 9px rgba(0,0,0,.46)!important;
      }
      body.v014.poker8-v2-sixmax .player-cards .card.back:first-child{transform:rotate(-8deg) translateX(2px)!important;}
      body.v014.poker8-v2-sixmax .player-cards .card.back:last-child{transform:rotate(8deg) translateX(-2px)!important;}

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards{top:-47px!important;z-index:9!important;gap:4px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card{
        width:43px!important;height:61px!important;border-radius:6px!important;
        background:linear-gradient(150deg,#07100f,#000000)!important;
        color:#eafff6!important;border:1px solid #56c8ff!important;
        box-shadow:0 0 12px rgba(47,184,255,.54),0 5px 10px rgba(0,0,0,.50),inset 0 0 10px rgba(47,207,255,.08)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card.red{color:#ff6759!important;border-color:#ff674d!important;box-shadow:0 0 12px rgba(255,87,70,.46),0 5px 10px rgba(0,0,0,.50)!important;}
      body.v014.poker8-v2-sixmax .viewer-seat .player-cards .card-rank{left:5px!important;top:3px!important;font-size:15px!important;font-weight:950!important;}
      body.v014.poker8-v2-sixmax .viewer-seat .player-cards .card-suit{font-size:27px!important;filter:drop-shadow(0 0 4px currentColor)!important;}
      body.v014.poker8-v2-sixmax .player-cards .card:not(.back){
        background:linear-gradient(150deg,#07100f,#000000)!important;color:#eafff6!important;
        border-color:hsla(var(--seat-accent),100%,70%,.88)!important;box-shadow:0 0 10px hsla(var(--seat-accent),96%,58%,.42)!important;
      }

      body.v014.poker8-v2-sixmax .board-cards{gap:3px!important;}
      body.v014.poker8-v2-sixmax .board-cards .card{
        width:45px!important;height:63px!important;
        border:1px solid rgba(98,255,170,.82)!important;border-radius:5px!important;
        background:linear-gradient(150deg,#07100f 0%,#000000 100%)!important;
        color:#eafff6!important;
        box-shadow:0 6px 10px rgba(0,0,0,.58),inset 0 0 12px rgba(32,255,147,.07)!important;
      }
      body.v014.poker8-v2-sixmax .board-cards .card.red{color:#df392c!important;border-color:#ff5f43!important;box-shadow:0 5px 9px rgba(0,0,0,.48)!important;}
      /* Which of your own cards -- hole or board -- make up your current best
         hand, live as the board fills in. Reuses the all-in glow colour
         (.seat-card.all-in .player-avatar below) rather than a new one: both
         mean "this is the strong part," so one colour does both jobs. */
      body.v014.poker8-v2-sixmax .board-cards .card.hand-combo,
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card.hand-combo{
        border-color:#f1c867!important;
        box-shadow:0 0 0 2px rgba(238,180,65,.42),0 0 16px rgba(238,180,65,.62),inset 0 0 10px rgba(238,180,65,.16)!important;
      }

      body.v014.poker8-v2-sixmax .pot-total{
        min-width:74px!important;padding:4px 9px!important;border-radius:7px!important;
        border-color:rgba(60,225,150,.22)!important;background:rgba(4,31,20,.66)!important;
        box-shadow:inset 0 0 12px rgba(60,225,150,.04),0 4px 11px rgba(0,0,0,.34)!important;
      }
      body.v014.poker8-v2-sixmax .pot-total-label{font-size:10px!important;letter-spacing:.08em!important;}
      /* Above the chip wings even though the plaque behind it (.pot-total,
         below) is not -- position+z-index here lets the number escape its
         own parent's stacking context, so it stays readable if a wing ever
         grazes the plaque, without the plaque's own background needing to
         out-rank the chips too. */
      body.v014.poker8-v2-sixmax .pot-total strong{
        font-size:20px!important;line-height:1!important;
        position:relative!important;z-index:3!important;
      }
      /* v019-center-polish sets display:flex!important on the same selector
         family, so the hide needs !important here to actually win. */
      body.v014.poker8-v2-sixmax.p8-no-pot .pot-total{display:none!important;}

      /* Two piles flanking the amount instead of one cluster piled under the
         board -- renderPotChips now splits the count into a left and a right
         .chip-cluster.pot-wing, laid out with the same flex row every other
         cluster on the felt already uses (see .chip-cluster in style.css). */
      body.v014.poker8-v2-sixmax .pot-chips .chip-cluster.pot-wing{height:52px!important;min-width:0!important;filter:drop-shadow(0 8px 6px rgba(0,0,0,.54))!important;}
      body.v014.poker8-v2-sixmax .pot-chips .chip-column{width:22px!important;height:48px!important;margin:0 -5px!important;}
      body.v014.poker8-v2-sixmax .pot-chips .poker-chip{
        width:22px!important;height:9px!important;border-width:1px!important;
        transform:translateX(-50%) translateY(calc(var(--i) * -3.6px))!important;
        box-shadow:0 2px 3px rgba(0,0,0,.58),inset 0 2px 0 rgba(255,255,255,.28),inset 0 -3px 0 rgba(0,0,0,.40)!important;
      }
      body.v014.poker8-v2-sixmax .pot-chips .poker-chip::before{left:3px!important;right:3px!important;height:4px!important;}
      /* Each column already renders one denomination's real colour (set by
         chipsForAmount in app.js) -- shifting every 3rd column's hue by
         position on top of that mixed denominations together at random,
         which is what read as the pot's chips being coloured/layered wrong. */

      body.v014.poker8-v2-sixmax .bet-marker .chip-cluster.compact{transform:scale(.82)!important;transform-origin:center bottom!important;}
      body.v014.poker8-v2-sixmax .bet-marker span{
        margin-top:-4px!important;padding:2px 6px!important;border:0!important;background:rgba(0,0,0,.84)!important;
        color:#eafff6!important;font-size:12px!important;font-weight:900!important;line-height:1!important;
        text-shadow:0 0 5px rgba(234,255,246,.42)!important;box-shadow:0 2px 5px rgba(0,0,0,.42)!important;
      }

      body.v014.poker8-v2-sixmax .dealer-button{
        border:1px solid #ecece2!important;background:radial-gradient(circle at 32% 28%,#ffffff,#d9d9ce 60%,#83867c)!important;
        color:#181a17!important;box-shadow:0 2px 6px rgba(0,0,0,.62)!important;
      }

      body.v014.poker8-v2-sixmax .seat .seat-card.v032-in-hand:not(.v032-active-turn){
        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn{
        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;
      }
      /* The turn is drawn once, in v041, in the turn colour. This layer used
         to draw it again in cyan with a pulse of its own, and v032 draws it a
         third time in orange -- so the acting seat carried three indicators in
         three colours, and the cyan pulse survived on top of the magenta ring
         because only this layer declared an animation. */
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .player-avatar{
        border-color:var(--turn-ring)!important;
        box-shadow:
          0 0 0 1px color-mix(in srgb,var(--turn-ring) 92%,transparent),
          0 0 10px 1px color-mix(in srgb,var(--turn-ring) 62%,transparent),
          0 0 26px 7px color-mix(in srgb,var(--turn-ring) 34%,transparent),
          0 0 52px 16px color-mix(in srgb,var(--turn-ring) 14%,transparent),
          inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .seat-identity{
        border-color:var(--turn)!important;
        box-shadow:0 0 18px color-mix(in srgb,var(--turn) 66%,transparent),0 7px 14px rgba(0,0,0,.62)!important;
      }
      /* Folding takes your cards, not your seat. Dimming the whole player to
         28% made them read as gone -- the name and stack you want to keep
         reading went with the hand. They stay lit like everyone else, and the
         cards beside the avatar are simply not there any more, which is what
         the table itself would show you. */
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-folded{
        opacity:1!important;filter:none!important;box-shadow:none!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-folded .player-cards{
        display:none!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.all-in{
        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.all-in .player-avatar{
        border-color:#f1c867!important;
        box-shadow:0 0 0 3px rgba(0,0,0,.92),0 0 18px rgba(238,180,65,.45),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }

      /* No z-index here on purpose -- any explicit value (even a low one)
         would make .pot-total its own stacking context and trap the number
         inside it below the chip wings regardless of the number's own
         z-index. Left at auto, the plaque paints at the base level (below
         .pot-chips's explicit z-index:2), while .pot-total strong's own
         z-index (above) escapes upward into the shared ancestor context
         instead of being capped by its parent. */
      body.v014.poker8-v2-sixmax .pot-total{top:25%!important;}
      /* Was 38%, 4px below the pot at the time -- and the wing seats at 5/6
         active viewers sat inside this same band (see v040's SPECTATOR_LAYOUTS
         fix), so the two nearly touched too. With those seats moved clear,
         checked every player count in both hero and spectator mode: no plate
         touches the pot or a board card at 34%, with 17-25px to spare on
         every side. */
      body.v014.poker8-v2-sixmax .board-cards{top:34%!important;}
      /* One centred cluster. It used to be two piles held apart by a fixed
         170px row (justify-content:space-between), which is fine for a big
         pot and wrong for a small one: one or two columns arrived as two
         lone stacks marooned either side of the plate. The row now shrinks
         to its chips -- width:auto with the inherited min-width (170px from
         .neon-ref-v107, 92px from the base rule) cleared, or the box keeps
         its old span and re-centres the cluster inside empty air.
         Full opacity immediately, no transition: the base .has-chips rule
         fades opacity in over .18s, and renderPotChips can repaint several
         times a second while a decision is on the clock -- each repaint
         restarts that transition, so the pile could sit at its
         .15-opacity starting point indefinitely instead of ever reaching 1. */
      body.v014.poker8-v2-sixmax .pot-chips{
        top:25%!important;width:auto!important;min-width:0!important;max-width:66%!important;
        display:flex!important;justify-content:center!important;align-items:flex-end!important;
        opacity:1!important;transition:none!important;z-index:2!important;
      }

      body.v014.poker8-v2-sixmax .sidebar{transform:none!important;height:var(--p8-hud-h)!important;}
      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        display:block!important;
        width:100%!important;height:var(--p8-hud-h)!important;min-height:var(--p8-hud-h)!important;
        padding:7px 8px!important;margin:0!important;overflow:hidden!important;
        border:1px solid rgba(83,123,112,.46)!important;border-radius:0!important;
        background:linear-gradient(180deg,rgba(7,16,15,.995),rgba(0,0,0,1))!important;
        box-shadow:0 -8px 24px rgba(0,0,0,.52),inset 0 0 22px rgba(29,255,192,.025)!important;
        transform:none!important;
      }
      body.v014.poker8-v2-sixmax .action-panel::after{display:none!important;content:none!important;}
      body.v014.poker8-v2-sixmax .action-panel > .panel-kicker,
      body.v014.poker8-v2-sixmax .action-panel > h2,
      body.v014.poker8-v2-sixmax .action-panel > .hint,
      body.v014.poker8-v2-sixmax .action-panel > .turn-meta,
      body.v014.poker8-v2-sixmax .action-panel > .mobile-turn-tools,
      body.v014.poker8-v2-sixmax .action-panel > .mobile-auto-action{display:none!important;}
      body.v014.poker8-v2-sixmax .v038-hud-summary{
        position:absolute!important;left:8px;right:8px;top:4px!important;height:28px;
        display:grid;grid-template-columns:repeat(2,1fr);align-items:center;text-align:center;
        border-bottom:1px solid rgba(95,132,121,.18);font-size:10px;letter-spacing:.10em;color:#8ca59c;
      }
      body.v014.poker8-v2-sixmax .v038-hud-summary b{
        display:block;margin-top:1px;font-size:15px;line-height:1;letter-spacing:0;
        color:#eafff6;font-variant-numeric:tabular-nums;
      }
      /* On the felt it is one line, not the panel's stacked pair: the gap
         between the pot's bottom and the board's top measures 24px on a
         321x760 phone felt, and the stacked version is 28px. */
      body.v014.poker8-v2-sixmax .v038-hud-summary.on-felt{
        /* Every one of these is load-bearing and was found by measuring, not
           by reading: something in the stack pins this element fixed with a
           bottom offset once it leaves the action panel (243px tall), and a
           min-height of ~39px held it at 38px even against height:20px
           !important -- min-height beats height. Zeroed, the strip is its
           content: 15px, which is what lets it sit in the 24px gap between
           the pot's bottom and the board's top on a 321x760 phone felt. */
        position:absolute!important;bottom:auto!important;
        left:50%!important;right:auto!important;top:var(--v038-summary-top,41%)!important;
        /* A plate of its own, in the pot's colours -- it read as text lying
           loose on the felt before. */
        padding:4px 10px!important;border-radius:7px!important;
        border:1px solid rgba(60,225,150,.22)!important;
        background:rgba(4,31,20,.66)!important;
        height:auto!important;min-height:0!important;
        transform:translateX(-50%);z-index:6;
        display:flex!important;gap:16px;align-items:baseline;white-space:nowrap;
      }
      body.v014.poker8-v2-sixmax .v038-hud-summary.on-felt span{
        display:block!important;min-height:0!important;line-height:1!important;
      }
      /* One line here, not the panel's stacked label-over-value pair. */
      body.v014.poker8-v2-sixmax .v038-hud-summary.on-felt b{
        display:inline!important;margin:0 0 0 5px!important;line-height:1!important;
      }
      body.v014.poker8-v2-sixmax .sizing-wrap{display:contents!important;}
      body.v014.poker8-v2-sixmax .sizing-wrap > label{display:none!important;}
      body.v014.poker8-v2-sixmax .quick-sizes{
        position:absolute!important;left:8px;right:8px;top:35px!important;height:39px;
        display:grid!important;grid-template-columns:repeat(5,1fr)!important;gap:4px!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button{
        min-height:39px!important;height:39px!important;padding:3px 2px!important;border-radius:6px!important;font-size:10px!important;
        color:#ffffff!important;text-shadow:none!important;
        transition:color 180ms ease,border-color 180ms ease,box-shadow 180ms ease,background 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button strong{display:block;font-size:10px!important;line-height:1!important;color:#ffffff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button small{display:block;margin-top:3px;font-size:10px!important;line-height:1!important;color:#f2f6ff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button.v038-max-size{
        --size-accent:var(--act-allin);
        color:#fff5bd!important;border-color:color-mix(in srgb,var(--act-allin) 88%,transparent)!important;background:rgba(44,29,2,.78)!important;
        box-shadow:0 0 11px rgba(255,184,45,.28),inset 0 0 8px rgba(255,196,77,.10)!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button.v038-size-selected{
        color:#ffffff!important;border-color:var(--size-accent)!important;
        background:color-mix(in srgb,var(--size-accent) 20%,#090a0a)!important;
        box-shadow:0 0 0 1px color-mix(in srgb,var(--size-accent) 55%,transparent),0 0 13px color-mix(in srgb,var(--size-accent) 62%,transparent),inset 0 0 10px color-mix(in srgb,var(--size-accent) 16%,transparent)!important;
      }
      body.v014.poker8-v2-sixmax .bet-slider-row{
        position:absolute!important;left:10px;right:10px;top:79px!important;height:25px!important;padding:0!important;
        display:block!important;
      }
      body.v014.poker8-v2-sixmax .bet-slider-row span{display:none!important;}
      body.v014.poker8-v2-sixmax #amountSlider{
        width:100%!important;height:25px!important;margin:0!important;appearance:none!important;background:transparent!important;
      }
      body.v014.poker8-v2-sixmax #amountSlider::-webkit-slider-runnable-track{
        height:6px;border:0;border-radius:999px;background:linear-gradient(90deg,var(--act-check) 0%,var(--act-raise) 52%,var(--act-allin) 100%);
      }
      body.v014.poker8-v2-sixmax #amountSlider::-moz-range-track{
        height:6px;border:0;border-radius:999px;background:linear-gradient(90deg,var(--act-check) 0%,var(--act-raise) 52%,var(--act-allin) 100%);
      }
      body.v014.poker8-v2-sixmax #amountSlider::-webkit-slider-thumb{
        width:17px;height:17px;margin-top:-6px;appearance:none;border:2px solid #ffffff;border-radius:50%;background:var(--act-raise);
        box-shadow:0 0 0 2px color-mix(in srgb,var(--act-raise) 32%,transparent);
      }
      body.v014.poker8-v2-sixmax #amountSlider::-moz-range-thumb{
        width:17px;height:17px;border:2px solid #ffffff;border-radius:50%;background:var(--act-raise);
        box-shadow:0 0 0 2px color-mix(in srgb,var(--act-raise) 32%,transparent);
      }
      body.v014.poker8-v2-sixmax .amount-row{display:none!important;}
      body.v014.poker8-v2-sixmax .action-grid{
        order:5;display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:repeat(2,44px)!important;gap:5px!important;
        position:absolute!important;z-index:4;left:8px;right:8px;bottom:4px!important;height:93px!important;
        padding:2px 0!important;background:#000000!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot{
        --v038-action:var(--act-check);
        position:relative;grid-column:auto!important;grid-row:auto!important;width:auto!important;max-width:none!important;min-width:0!important;min-height:44px!important;height:44px!important;border-radius:8px!important;font-size:10px!important;
        color:var(--v038-action)!important;border-color:var(--v038-action)!important;background:rgba(0,0,0,.98)!important;
        box-shadow:0 0 10px color-mix(in srgb,var(--v038-action) 38%,transparent),inset 0 0 9px color-mix(in srgb,var(--v038-action) 10%,transparent)!important;
        transition:color 180ms ease,border-color 180ms ease,box-shadow 180ms ease,background 180ms ease,filter 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot.fold{--v038-action:var(--act-fold);}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.check{--v038-action:var(--act-check);}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.call{--v038-action:var(--act-check);}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.raise{--v038-action:var(--act-raise);}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.all-in{--v038-action:var(--act-allin);}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.queued{
        color:var(--v038-action)!important;border-color:var(--v038-action)!important;
        background:linear-gradient(180deg,color-mix(in srgb,var(--v038-action) 22%,#07100f),#000000)!important;
        box-shadow:0 0 0 1px color-mix(in srgb,var(--v038-action) 60%,transparent),0 0 17px color-mix(in srgb,var(--v038-action) 55%,transparent),inset 0 0 9px color-mix(in srgb,var(--v038-action) 16%,transparent)!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot.queued::after{
        content:"✓"!important;position:absolute!important;top:-6px!important;right:-4px!important;width:20px!important;height:20px!important;
        display:grid!important;place-items:center!important;border-radius:50%!important;background:var(--v038-action)!important;color:#000000!important;font-size:12px!important;
        box-shadow:0 0 10px color-mix(in srgb,var(--v038-action) 70%,transparent)!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot:disabled{
        opacity:1!important;color:color-mix(in srgb,var(--v038-action) 35%,transparent)!important;
        border-color:color-mix(in srgb,var(--v038-action) 48%,transparent)!important;box-shadow:none!important;cursor:default!important;
      }
      body.v014.poker8-v2-sixmax .v038-actions-unavailable{
        position:absolute;inset:0;display:grid;place-content:center;text-align:center;
        border:1px solid rgba(89,232,184,.24);border-radius:9px;background:linear-gradient(135deg,rgba(2,19,18,.98),rgba(0,0,0,.99));
        color:#c9ffe3;box-shadow:inset 0 0 18px rgba(75,255,181,.05);
      }
      body.v014.poker8-v2-sixmax .v038-actions-unavailable strong{font-size:12px;letter-spacing:.06em;color:#7dffd0;}
      body.v014.poker8-v2-sixmax .v038-actions-unavailable span{margin-top:5px;font-size:10px;color:#9db9ad;}
      body.v014.poker8-v2-sixmax .v038-action-label{display:block;font-weight:900;letter-spacing:.035em;line-height:1.05;}
      body.v014.poker8-v2-sixmax .v038-action-amount{display:block;margin-top:2px;font-size:12px;font-weight:900;line-height:1;}
      body.v014.poker8-v2-sixmax .v038-action-amount.v038-amount-pulse{animation:v038AmountPulse 180ms ease-out;}
      @keyframes v038AmountPulse{50%{filter:brightness(1.5)}100%{filter:none}}
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .quick-sizes button,
        body.v014.poker8-v2-sixmax .action-grid .action-slot{transition:none!important;}
        body.v014.poker8-v2-sixmax .v038-action-amount.v038-amount-pulse{animation:none!important;}
        body.v014.poker8-v2-sixmax.v038-room-awaiting .player-avatar{animation:none!important;}
        body.v014.poker8-v2-sixmax .felt{transition-duration:80ms!important;}
      }
      body.v014.poker8-v2-sixmax .app-shell{
        height:100dvh!important;min-height:100dvh!important;overflow:hidden!important;
        padding-bottom:var(--p8-bottom-reserve)!important;
        background:linear-gradient(180deg,transparent 0 calc(100% - var(--p8-bottom-reserve)),#000000 calc(100% - var(--p8-bottom-reserve)) 100%)!important;
      }

      @media (max-width:780px){
      /* Portrait-first edge-action composition. Shared pixel offsets keep the
         five opponent centers on one circle instead of a percentage ellipse. */
      body.v014.poker8-v2-sixmax{
        --p8-header-h:52px;
        --p8-seat-safe-inset:50px;
        --p8-arc-radius:min(46vw,calc(50vw - var(--p8-seat-safe-inset)));
        --p8-arc-diagonal:calc(var(--p8-arc-radius) * .70710678);
        --p8-arc-half:calc(var(--p8-arc-radius) * .5);
        --p8-arc-wide:calc(var(--p8-arc-radius) * .8660254);
        /* The old 38px pin compressed all five opponents against the header.
           At 78px the top pole lands at the former upper-wing level, while
           both wing pairs move down by the same 40px. */
        --p8-arc-top:78px;
        --p8-arc-center-y:calc(var(--p8-arc-top) + var(--p8-arc-radius));
        --p8-seat-angles:"180 135 90 45 0";
        --table-stage-h:calc(100dvh - var(--p8-header-h))!important;
      }
      body.v014.poker8-v2-sixmax .mobile-game-header{
        position:fixed!important;z-index:120;inset:0 0 auto!important;height:var(--p8-header-h)!important;
        display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:8px!important;
        padding:2px 8px!important;background:linear-gradient(180deg,rgba(0,8,5,.98),rgba(0,8,5,.92))!important;
        border-bottom:1px solid rgba(75,255,181,.18)!important;box-shadow:0 8px 22px rgba(0,0,0,.34)!important;
      }
      body.v014.poker8-v2-sixmax :is(.mobile-menu-button,.mobile-chat-button){
        width:48px!important;height:48px!important;min-width:48px!important;min-height:48px!important;border-radius:14px!important;
      }
      body.v014.poker8-v2-sixmax .mobile-header-utility{margin-left:auto!important;}
      /* Out of the header and into the bottom-right corner: beside the
         hamburger it sat in the one row the eye uses for actions, and a
         connection light is ambient, not something you act on. Fixed rather
         than moved in the DOM -- it has no layout relationship to anything
         around it. */
      body.v014.poker8-v2-sixmax #mobileConnectionDot{
        display:block;width:8px;height:8px;flex:0 0 8px;border-radius:50%;background:#55f3a8;box-shadow:0 0 9px rgba(85,243,168,.92);
        position:fixed!important;right:12px!important;left:auto!important;top:auto!important;
        bottom:calc(12px + env(safe-area-inset-bottom))!important;z-index:200!important;pointer-events:none;
      }
      body.v014.poker8-v2-sixmax #connectionStatus{display:none!important;}
      body.v014.poker8-v2-sixmax .app-shell{
        height:100dvh!important;min-height:100dvh!important;padding:var(--p8-header-h) 0 0!important;overflow:hidden!important;background:#000805!important;
      }
      body.v014.poker8-v2-sixmax .table-frame{
        height:calc(100dvh - var(--p8-header-h))!important;min-height:0!important;padding:0 5px!important;overflow:visible!important;
        background-size:100vw 100%!important;background-position:center!important;
      }
      body.v014.poker8-v2-sixmax .felt{
        height:100%!important;transform:none!important;transform-style:flat!important;
      }
      body.v014.poker8-v2-sixmax .seat{width:90px!important;height:104px!important;min-height:0!important;}
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat{
        --v040-flip-x:0px!important;--v040-flip-y:0px!important;transition:none!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{--v040-seat-x:50%!important;--v040-seat-y:calc(100% - 86px)!important;--p8-hero-avatar-top:9px;--p8-hero-avatar-size:48px;--p8-hero-label-top:54px;--p8-hero-label-w:108px;left:50%!important;top:calc(100% - 86px)!important;bottom:auto!important;width:116px!important;height:132px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{--v040-seat-x:calc(50% - var(--p8-arc-radius))!important;--v040-seat-y:var(--p8-arc-center-y)!important;left:calc(50% - var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{--v040-seat-x:calc(50% - var(--p8-arc-diagonal))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;left:calc(50% - var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{--v040-seat-x:50%!important;--v040-seat-y:var(--p8-arc-top)!important;left:50%!important;top:var(--p8-arc-top)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{--v040-seat-x:calc(50% + var(--p8-arc-diagonal))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;left:calc(50% + var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{--v040-seat-x:calc(50% + var(--p8-arc-radius))!important;--v040-seat-y:var(--p8-arc-center-y)!important;left:calc(50% + var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat[data-visual-seat="1"]{--v040-seat-x:50%!important;--v040-seat-y:var(--p8-arc-top)!important;left:50%!important;top:var(--p8-arc-top)!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-3 .seat[data-visual-seat="1"]{--v040-seat-x:calc(50% - var(--p8-arc-diagonal))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;left:calc(50% - var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-3 .seat[data-visual-seat="2"]{--v040-seat-x:calc(50% + var(--p8-arc-diagonal))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;left:calc(50% + var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-4 .seat[data-visual-seat="1"]{--v040-seat-x:calc(50% - var(--p8-arc-wide))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-half))!important;left:calc(50% - var(--p8-arc-wide))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-half))!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-4 .seat[data-visual-seat="2"]{--v040-seat-x:50%!important;--v040-seat-y:var(--p8-arc-top)!important;left:50%!important;top:var(--p8-arc-top)!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-4 .seat[data-visual-seat="3"]{--v040-seat-x:calc(50% + var(--p8-arc-wide))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-half))!important;left:calc(50% + var(--p8-arc-wide))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-half))!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat[data-visual-seat="1"]{--v040-seat-x:calc(50% - var(--p8-arc-radius))!important;--v040-seat-y:var(--p8-arc-center-y)!important;left:calc(50% - var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat[data-visual-seat="2"]{--v040-seat-x:calc(50% - var(--p8-arc-half))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-wide))!important;left:calc(50% - var(--p8-arc-half))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-wide))!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat[data-visual-seat="3"]{--v040-seat-x:calc(50% + var(--p8-arc-half))!important;--v040-seat-y:calc(var(--p8-arc-center-y) - var(--p8-arc-wide))!important;left:calc(50% + var(--p8-arc-half))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-wide))!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat[data-visual-seat="4"]{--v040-seat-x:calc(50% + var(--p8-arc-radius))!important;--v040-seat-y:var(--p8-arc-center-y)!important;left:calc(50% + var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
      body.v014.poker8-v2-sixmax .avatar-wrap{
        top:0!important;width:44px!important;height:44px!important;transform:translateX(-50%)!important;transform-origin:center!important;
      }
      body.v014.poker8-v2-sixmax .player-avatar{width:44px!important;height:44px!important;font-size:12px!important;}
      body.v014.poker8-v2-sixmax .seat-identity{
        top:40px!important;width:90px!important;min-height:44px!important;padding:5px 6px 4px!important;border-radius:9px!important;
      }
      body.v014.poker8-v2-sixmax .seat-name{max-width:100%!important;font-size:12px!important;line-height:1.05!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;}
      body.v014.poker8-v2-sixmax .seat-stack{font-size:16px!important;line-height:1!important;white-space:nowrap!important;}
      body.v014.poker8-v2-sixmax .player-cards{top:-31px!important;}
      body.v014.poker8-v2-sixmax .player-cards .card{width:32px!important;height:44px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap{top:var(--p8-hero-avatar-top)!important;width:var(--p8-hero-avatar-size)!important;height:var(--p8-hero-avatar-size)!important;transform:translateX(-50%)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{width:var(--p8-hero-avatar-size)!important;height:var(--p8-hero-avatar-size)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-identity{top:var(--p8-hero-label-top)!important;width:var(--p8-hero-label-w)!important;min-height:47px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-name{max-width:100%!important;font-size:13px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{font-size:18px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards{top:-52px!important;gap:4px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card{width:50px!important;height:70px!important;}
      body.v014.poker8-v2-sixmax .board-cards .card{width:46px!important;height:64px!important;}
      /* Pot lifted 38% -> 34%. It sat directly on top of the call/bet strip
         with nothing between them; the four points it gives up are what that
         strip now has to breathe in. */
      body.v014.poker8-v2-sixmax .pot-chips{top:29%!important;}
      body.v014.poker8-v2-sixmax .pot-total{top:34%!important;}
      body.v014.poker8-v2-sixmax .board-cards{top:47%!important;}
      body.v014.poker8-v2-sixmax .sidebar,
      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        position:fixed!important;z-index:80;inset:var(--p8-header-h) 0 0!important;width:auto!important;height:auto!important;min-height:0!important;
        padding:0!important;margin:0!important;overflow:visible!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;backdrop-filter:none!important;filter:none!important;contain:none!important;will-change:auto!important;pointer-events:none!important;
      }
      body.v014.poker8-v2-sixmax .action-panel :is(button,input){pointer-events:auto!important;}
      body.v014.poker8-v2-sixmax .v038-hud-summary{
        position:fixed!important;z-index:82;left:96px!important;right:96px!important;top:auto!important;bottom:calc(183px + env(safe-area-inset-bottom))!important;
        height:38px!important;min-height:38px!important;padding:3px 4px!important;border:1px solid rgba(75,255,181,.32)!important;border-radius:10px!important;
        background:rgba(0,8,5,.88)!important;box-shadow:0 0 14px rgba(41,238,165,.12)!important;pointer-events:none!important;
        font-size:10px!important;line-height:1!important;letter-spacing:0!important;
      }
      body.v014.poker8-v2-sixmax .v038-hud-summary b{margin-top:3px!important;font-size:15px!important;}
      body.v014.poker8-v2-sixmax .action-grid{display:contents!important;}
      body.v014.poker8-v2-sixmax .action-grid .action-slot{
        position:fixed!important;z-index:90;width:88px!important;max-width:88px!important;min-height:58px!important;height:auto!important;padding:8px 7px!important;
      }
      body.v014.poker8-v2-sixmax .action-slot[data-edge="left"]{left:0!important;right:auto!important;border-left:0!important;border-radius:0 16px 16px 0!important;}
      body.v014.poker8-v2-sixmax .action-slot[data-edge="right"]{right:0!important;left:auto!important;border-right:0!important;border-radius:16px 0 0 16px!important;}
      body.v014.poker8-v2-sixmax .action-slot[data-slot="top"]{top:auto!important;bottom:calc(152px + env(safe-area-inset-bottom))!important;}
      body.v014.poker8-v2-sixmax .action-slot[data-slot="bottom"]{top:auto!important;bottom:calc(84px + env(safe-area-inset-bottom))!important;}
      body.v014.poker8-v2-sixmax .sizing-wrap{
        display:none!important;position:fixed!important;z-index:96;left:50%!important;right:auto!important;top:auto!important;bottom:calc(150px + env(safe-area-inset-bottom))!important;
        width:min(344px,calc(100vw - 16px))!important;height:auto!important;transform:translateX(-50%)!important;padding:10px!important;
        border:1px solid rgba(71,255,190,.42)!important;border-radius:18px!important;background:rgba(0,8,5,.96)!important;box-shadow:0 0 28px rgba(44,247,169,.22)!important;
      }
      body.v014.poker8-v2-sixmax.v038-sizing-open .sizing-wrap{display:block!important;}
      body.v014.poker8-v2-sixmax.v038-sizing-open .action-grid .action-slot{visibility:hidden!important;}
      body.v014.poker8-v2-sixmax .mobile-sizing-head{display:flex;align-items:center;justify-content:center;min-height:44px;margin-bottom:7px;position:relative;}
      body.v014.poker8-v2-sixmax #mobileSizingAmount{color:#fff;font-size:24px;font-weight:950;line-height:1;text-shadow:0 0 12px rgba(63,238,188,.46);}
      body.v014.poker8-v2-sixmax #mobileSizingCancel{
        position:absolute;right:0;top:0;width:44px;height:44px;border:1px solid rgba(139,184,164,.35);border-radius:12px;background:#0a1512;color:#cbddd5;font-size:24px;
      }
      body.v014.poker8-v2-sixmax .quick-sizes{
        position:static!important;height:auto!important;display:grid!important;grid-template-columns:repeat(5,minmax(48px,1fr))!important;gap:5px!important;margin:0!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button{min-height:48px!important;height:48px!important;padding:4px 2px!important;font-size:10px!important;}
      body.v014.poker8-v2-sixmax .bet-slider-row{position:static!important;height:32px!important;margin:7px 0 5px!important;display:block!important;}
      body.v014.poker8-v2-sixmax #amountSlider{height:32px!important;}
      body.v014.poker8-v2-sixmax #mobileSizingConfirm{
        width:100%!important;min-height:50px!important;border:1px solid rgba(75,255,181,.72);border-radius:13px;background:linear-gradient(180deg,rgba(15,72,48,.96),rgba(4,31,20,.98));color:#eafff6;font-size:12px;font-weight:950;letter-spacing:.04em;box-shadow:0 0 17px rgba(63,244,173,.18);
      }
      body.v014.poker8-v2-sixmax .action-slot[data-action-key="aggressive"]{touch-action:none!important;}
      body.v014.poker8-v2-sixmax #mobileBetRail{
        display:block;position:fixed;z-index:99;top:calc(var(--p8-header-h) + 10px);right:0;bottom:calc(72px + env(safe-area-inset-bottom));width:76px;
        border:1px solid rgba(75,255,181,.55);border-right:0;border-radius:18px 0 0 18px;background:linear-gradient(180deg,rgba(7,53,37,.94),rgba(0,8,5,.96));
        box-shadow:0 0 24px rgba(41,238,165,.22);pointer-events:none;
      }
      body.v014.poker8-v2-sixmax #mobileBetRail::before{
        content:"";position:absolute;top:22px;bottom:22px;right:18px;width:3px;border-radius:3px;background:linear-gradient(180deg,#ff9f43 0 8%,#3defb0 28% 100%);opacity:.8;
      }
      body.v014.poker8-v2-sixmax #mobileBetRailAmount{
        position:fixed;z-index:100;right:12px;top:clamp(calc(var(--p8-header-h) + 12px),calc(var(--v038-rail-y, 50vh) - 25px),calc(100vh - 128px));
        min-width:104px;min-height:50px;padding:0 12px;display:grid;place-items:center;border-radius:14px 0 0 14px;background:#031b13;color:#fff;font-size:20px;font-weight:950;white-space:nowrap;
        border:1px solid rgba(75,255,181,.72);box-shadow:0 0 18px rgba(41,238,165,.28);
      }
      body.v014.poker8-v2-sixmax #mobileBetRail[aria-hidden="true"]{display:none!important;}
      body.v014.poker8-v2-sixmax .seat{--seat-accent:155!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{--seat-accent:195!important;}
      body.v014.poker8-v2-sixmax .seat:has(.v032-active-turn){--seat-accent:165!important;}
      body.v014.poker8-v2-sixmax .seat:has(.all-in){--seat-accent:34!important;}
      body.v014.poker8-v2-sixmax .felt .seat .seat-card:is(.folded,.v032-folded){opacity:.45!important;filter:saturate(.28) brightness(.72)!important;}
      body.v014.poker8-v2-sixmax .felt .seat .seat-card:is(.folded,.v032-folded) .avatar-wrap::before,
      body.v014.poker8-v2-sixmax .felt .seat .seat-card:is(.folded,.v032-folded) .avatar-wrap::after{opacity:0!important;}
      body.v014.poker8-v2-sixmax .seat-card.v038-disconnected{opacity:.58!important;filter:saturate(.15) brightness(.72)!important;}
      body.v014.poker8-v2-sixmax .avatar-wrap>:is(.v038-turn-timer,.v038-ready-countdown){
        position:absolute;z-index:14;left:50%;top:50%;bottom:auto;width:calc(100% + 10px);height:calc(100% + 10px);transform:translate(-50%,-50%);place-items:center;border:0!important;border-radius:50%;
        background:none!important;box-shadow:none!important;filter:drop-shadow(0 0 8px rgba(87,255,208,.72));pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .avatar-wrap>:is(.v038-turn-timer,.v038-ready-countdown)::before{
        content:"";position:absolute;inset:0;border:0;border-radius:50%;background:conic-gradient(#57ffd0 var(--timer-progress,100%),rgba(87,255,208,.10) 0);
        -webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 4px),#000 0);mask:radial-gradient(farthest-side,transparent calc(100% - 4px),#000 0);
      }
      body.v014.poker8-v2-sixmax .avatar-wrap>:is(.v038-turn-timer,.v038-ready-countdown) b{
        position:absolute;left:calc(100% - 4px);top:50%;min-width:29px;padding:4px 5px;transform:translateY(-50%);border-radius:8px;background:#061611;color:#fff;font-size:13px;line-height:1;text-align:center;text-shadow:0 0 7px #55ffe0;box-shadow:0 0 10px rgba(85,255,224,.35);
      }
      body.v014.poker8-v2-sixmax .avatar-wrap>:is(.v038-turn-timer,.v038-ready-countdown) small{display:none;}
      /* Was bottom:2px -- down at the plate, where it read as decoration on
         the name rather than as this player's button. Beside the avatar
         instead, mirroring the turn timer that the rule above hangs on the
         avatar's right edge at calc(100% - 4px): the same 4px bite out of
         the avatar, on the left, vertically centred. The avatar is 44px
         from the seat's top, so top:11px centres the 22px badge on it. */
      body.v014.poker8-v2-sixmax .dealer-button{left:-6px!important;right:auto!important;top:11px!important;bottom:auto!important;width:22px!important;height:22px!important;}
      body.v014.poker8-v2-sixmax #mobileConnectionDot[data-state="connecting"]{background:#8aa99b;box-shadow:0 0 7px rgba(138,169,155,.58);}
      body.v014.poker8-v2-sixmax #mobileConnectionDot[data-state="reconnecting"]{background:#ffbd55;box-shadow:0 0 9px rgba(255,189,85,.88);}
      body.v014.poker8-v2-sixmax #mobileConnectionDot[data-state="error"]{background:#ff554f;box-shadow:0 0 9px rgba(255,85,79,.88);}
      }
    }
  `;
  document.head.appendChild(style);

  const setText = (node, value) => {
    if (node && node.textContent !== value) node.textContent = value;
  };

  function compactStackLabel(raw) {
    const value = Number(String(raw || "").replace(/[^\d.-]/g, ""));
    if (!Number.isFinite(value)) return raw;
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1).replace(/\.0$/, "")}M`;
    if (value >= 10_000) return `${(value / 1_000).toFixed(value >= 100_000 ? 0 : 1).replace(/\.0$/, "")}K`;
    if (value >= 1_000) return Math.round(value).toLocaleString("en-US");
    return value.toFixed(2).replace(/\.00$/, "");
  }

  function syncSeatStackLabels() {
    document.querySelectorAll(".seat-stack").forEach(stack => {
      if (!stack.dataset.v038FullStack) stack.dataset.v038FullStack = stack.textContent || "";
      const source = stack.dataset.v038FullStack;
      setText(stack, compactStackLabel(source));
      stack.setAttribute("aria-label", source);
    });
  }

  function syncTableNumberLabels() {
    document.querySelectorAll(".pot-total strong,.bet-marker span").forEach(label => {
      const rendered = label.textContent || "";
      if (/ББ/i.test(rendered) || !label.dataset.v038FullValue) label.dataset.v038FullValue = rendered;
      const source = label.dataset.v038FullValue;
      setText(label, String(source).replace(/\s*ББ\s*$/i, ""));
      label.setAttribute("aria-label", source);
    });
  }

  function ensureMobileHeaderControls() {
    const header = document.getElementById("mobileGameHeader");
    if (!header) return;
    let dot = document.getElementById("mobileConnectionDot");
    if (!dot) {
      dot = document.createElement("span");
      dot.id = "mobileConnectionDot";
      dot.setAttribute("role", "status");
      dot.setAttribute("aria-label", "Подключение");
      // Appended to the body, not into the header. The header carries a
      // backdrop-filter, and that makes it the containing block for any
      // fixed descendant -- so the dot's right/bottom resolved against the
      // 50px header and it parked in the header's own corner instead of the
      // screen's. Nothing here has a layout relationship to the header.
      document.body.appendChild(dot);
    }
    syncConnectionDot();
  }

  function syncConnectionDot() {
    const dot = document.getElementById("mobileConnectionDot");
    if (!dot) return;
    const raw = document.getElementById("connectionStatus")?.textContent?.trim().toLowerCase() || "";
    const state = raw === "connected" ? "connected"
      : raw.includes("reconnect") || raw.includes("перепод") ? "reconnecting"
      : raw.includes("error") || raw.includes("ошиб") || raw.includes("offline") ? "error"
      : "connecting";
    const labels = {
      connected:"Подключено",
      reconnecting:"Переподключение",
      error:"Ошибка соединения",
      connecting:"Подключение",
    };
    dot.dataset.state = state;
    dot.setAttribute("aria-label", labels[state]);
  }

  let readyCountdownEndsAt = 0;
  let readyCountdownDuration = 1;
  let readyCountdownTicker = 0;
  let viewerReadySnapshot = false;

  function syncAvatarReadyControl() {
    const seat = document.querySelector('.seat[data-visual-seat="0"]');
    const wrap = seat?.querySelector(".avatar-wrap");
    if (!wrap) return;
    let mark = wrap.querySelector(".v038-ready-mark");
    if (!mark) {
      mark = document.createElement("span");
      mark.className = "v038-ready-mark";
      mark.innerHTML = '<b>✓</b>';
      wrap.appendChild(mark);
    }
    // Online: the server is the source of truth for who's clicked ready.
    // Local: v024's own sessionStorage-backed toggle (dead on network tables).
    const ready = window.Poker8OnlineTable
      ? (tableData?.ready_seats || []).includes(Number(seat.dataset.seat))
      : viewerReadySnapshot;
    // A seat that bought in mid-hand sits that hand out entirely (game exists,
    // but this viewer isn't one of game.players) -- readyUp() in online-table.js
    // already accepts a ready toggle then, so the avatar needs to look and
    // behave clickable then too, not just once game goes back to null.
    const preHand = !game || !game.players?.[game.viewer_player_id];
    // Drives both the checkmark and the "tap me" pulse, so the avatar carries
    // the whole state on its own and no card has to sit over the table.
    document.body.classList.toggle("p8-can-ready", preHand && !tableData?.spectator_only);
    wrap.classList.toggle("v038-viewer-ready", ready && preHand);
    wrap.toggleAttribute("role", preHand);
    if (preHand) {
      wrap.setAttribute("role", "button");
      wrap.setAttribute("tabindex", "0");
      wrap.setAttribute("aria-label", ready ? "Отменить готовность" : "Готов к раздаче");
    } else {
      wrap.removeAttribute("role");
      wrap.removeAttribute("tabindex");
      wrap.removeAttribute("aria-label");
    }
  }

  function syncAllSeatReadyMarks() {
    const isOnline = Boolean(window.Poker8OnlineTable);
    const onlineReadySeats = isOnline ? (tableData?.ready_seats || []) : null;
    document.querySelectorAll(".seat-card").forEach(card => {
      if (card.closest('.seat[data-visual-seat="0"]')) return;
      const wrap = card.querySelector(".avatar-wrap");
      if (!wrap) return;
      if (game) {
        wrap.classList.remove("v038-viewer-ready");
        wrap.querySelector(".v038-seat-ready-check")?.remove();
        return;
      }
      // Online: reflect each seat's real click. Local: every non-hero seat
      // is a bot, always ready -- unchanged from before this was online-aware.
      const seatNo = Number(card.closest(".seat")?.dataset.seat);
      const ready = isOnline ? onlineReadySeats.includes(seatNo) : true;
      if (!ready) {
        wrap.querySelector(".v038-seat-ready-check")?.remove();
        wrap.classList.remove("v038-viewer-ready");
        return;
      }
      let mark = wrap.querySelector(".v038-seat-ready-check");
      if (!mark) {
        mark = document.createElement("span");
        mark.className = "v038-ready-mark v038-seat-ready-check";
        mark.innerHTML = "<b>✓</b>";
        wrap.appendChild(mark);
      }
      wrap.classList.add("v038-viewer-ready");
    });
  }

  let turnVisualToken = "";
  let turnVisualStartedAt = 0;
  let turnVisualTicker = 0;
  const TURN_VISUAL_MS = 30000;

  const ACTION_CLASSES = ["v038-action-fold", "v038-action-passive", "v038-action-aggressive", "v038-action-all-in"];

  function syncSeatActionStates() {
    const latest = new Map();
    (game?.history || []).forEach(row => latest.set(row.player_id, row.action));
    document.querySelectorAll('.seat[data-seat]').forEach(seat => {
      const card = seat.querySelector(".seat-card");
      if (!card) return;
      card.classList.remove(...ACTION_CLASSES);
      const player = Object.values(game?.players || {}).find(item => Number(item?.seat) === Number(seat.dataset.seat));
      card.classList.toggle("v038-disconnected", Boolean(player?.disconnected || player?.connected === false || player?.status === "disconnected"));
      const action = latest.get(player?.id);
      const family = action === "fold" ? "fold"
        : ["check", "call"].includes(action) ? "passive"
        : ["bet", "raise"].includes(action) ? "aggressive"
        : action === "all_in" ? "all-in" : "";
      if (family) card.classList.add(`v038-action-${family}`);
    });
  }

  function syncTableTurnHud() {
    let timer = document.querySelector(".v038-turn-timer");
    document.querySelectorAll(".v038-turn-context").forEach(node => node.remove());
    const active = Boolean(game && !game.terminal && game.acting_player);
    const actor = active ? game.players?.[game.acting_player] : null;
    const host = actor ? document.querySelector(`.seat[data-seat="${Number(actor.seat)}"] .avatar-wrap`) : null;
    if (!active || !host) {
      timer?.remove();
      window.clearInterval(turnVisualTicker);
      turnVisualTicker = 0;
      turnVisualToken = "";
      return;
    }
    if (!timer) {
      timer = document.createElement("div");
      timer.className = "v038-turn-timer";
      timer.innerHTML = '<b>30</b><small>СЕК</small>';
    }
    if (timer.parentElement !== host) host.appendChild(timer);
    timer.classList.add("visible");
    // The server owns the clock and folds on its own deadline, so a locally
    // restarted countdown would promise time the player does not have.
    //
    // It only keeps a clock for a human: action_deadline is null for a bot,
    // and that is not an omission -- a bot is never timed out. The ring used
    // to invent a 30-second countdown for them anyway, keyed to a token that
    // changes on every action, so as the turn moved round the table the
    // number visibly jumped back to 30 again and again. The ring still marks
    // whose turn it is; it just does not claim to be counting anything.
    const deadline = game.action_deadline ? Date.parse(game.action_deadline) : NaN;
    const timed = !Number.isNaN(deadline);
    timer.classList.toggle("v038-untimed", !timed);
    if (!timed) {
      setText(timer.querySelector("b"), "");
      timer.style.setProperty("--timer-progress", "100%");
      window.clearInterval(turnVisualTicker);
      turnVisualTicker = 0;
      turnVisualToken = "";
      return;
    }
    const left = Math.max(0, deadline - Date.now());
    setText(timer.querySelector("b"), String(Math.ceil(left / 1000)));
    timer.style.setProperty("--timer-progress", `${Math.min(100, left / TURN_VISUAL_MS * 100)}%`);
    if (!turnVisualTicker) turnVisualTicker = window.setInterval(syncTableTurnHud, 250);
  }

  let roomResetTimer = 0;
  let roomResetHandId = "";
  const HAND_RESULT_HOLD_MS = 7000;
  const ROOM_FADE_MS = 260;

  function ensureRoomPrompt() {
    const felt = document.querySelector(".felt");
    if (!felt) return null;
    let prompt = felt.querySelector(".v038-room-prompt");
    if (!prompt) {
      prompt = document.createElement("div");
      prompt.className = "v038-room-prompt";
      prompt.innerHTML = "<strong>НОВАЯ РАЗДАЧА</strong><span>Нажмите на свою аватарку</span>";
      prompt.setAttribute("role", "button");
      prompt.setAttribute("tabindex", "0");
      prompt.setAttribute("aria-label", "Готов к новой раздаче");
      felt.appendChild(prompt);
    }
    return prompt;
  }

  function cancelRoomReset() {
    window.clearTimeout(roomResetTimer);
    roomResetTimer = 0;
    roomResetHandId = "";
    document.body.classList.remove("v038-room-resetting");
  }

  function syncCompletedHandReset() {
    const room = !game;
    document.body.classList.toggle("v038-hand-complete", Boolean(game?.terminal));
    document.body.classList.toggle("v038-room-awaiting", room);
    const prompt = ensureRoomPrompt();
    if (window.Poker8OnlineTable) {
      // Online state lives on the header and hero avatar; the central prompt
      // belongs only to the local trainer's idle room.
      prompt?.classList.remove("visible");
      cancelRoomReset();
      return;
    }
    prompt?.classList.toggle("visible", room);
    if (!game?.terminal) {
      cancelRoomReset();
      return;
    }
    if (roomResetHandId === game.hand_id) return;
    cancelRoomReset();
    roomResetHandId = game.hand_id;
    if (typeof clearAutomationTimer === "function") clearAutomationTimer();
    roomResetTimer = window.setTimeout(() => {
      roomResetTimer = 0;
      if (!game?.terminal || game.hand_id !== roomResetHandId) return;
      document.body.classList.add("v038-room-resetting");
      window.setTimeout(() => {
        if (!game?.terminal || game.hand_id !== roomResetHandId) return;
        game = null;
        document.body.classList.remove("v038-room-resetting");
        renderGame();
      }, ROOM_FADE_MS);
    }, HAND_RESULT_HOLD_MS);
  }

  function ensureReadyCountdown() {
    const felt = document.querySelector(".felt");
    if (!felt) return null;
    const hero = document.querySelector('.seat[data-visual-seat="0"] .avatar-wrap');
    const host = hero || felt;
    let countdown = document.querySelector(".v038-ready-countdown");
    if (!countdown) {
      countdown = document.createElement("div");
      countdown.className = "v038-ready-countdown";
      countdown.setAttribute("aria-live", "polite");
      countdown.innerHTML = "<b>1</b>";
    }
    if (countdown.parentElement !== host) host.appendChild(countdown);
    return countdown;
  }

  function setReadyCountdown(endsAt) {
    readyCountdownEndsAt = Number(endsAt || 0);
    readyCountdownDuration = Math.max(1, readyCountdownEndsAt - Date.now());
    window.clearInterval(readyCountdownTicker);
    readyCountdownTicker = 0;
    syncAvatarReadyControl();
    const countdown = ensureReadyCountdown();
    countdown?.classList.toggle("visible", Boolean(readyCountdownEndsAt));
    const initialLeft = Math.max(0, readyCountdownEndsAt - Date.now());
    setText(countdown?.querySelector("b"), String(Math.max(1, Math.ceil(initialLeft / 1000))));
    countdown?.style.setProperty("--timer-progress", `${Math.min(100, initialLeft / readyCountdownDuration * 100)}%`);
    if (!readyCountdownEndsAt) return;
    readyCountdownTicker = window.setInterval(() => {
      syncAvatarReadyControl();
      const liveCountdown = ensureReadyCountdown();
      const left = Math.max(0, readyCountdownEndsAt - Date.now());
      liveCountdown?.classList.add("visible");
      setText(liveCountdown?.querySelector("b"), String(Math.max(1, Math.ceil(left / 1000))));
      liveCountdown?.style.setProperty("--timer-progress", `${Math.min(100, left / readyCountdownDuration * 100)}%`);
      if (Date.now() >= readyCountdownEndsAt) {
        window.clearInterval(readyCountdownTicker);
        readyCountdownTicker = 0;
        liveCountdown?.classList.remove("visible");
      }
    }, 200);
  }

  let referenceActive = false;
  let presetSnapshot = null;
  let sizingMode = null;
  let betGesture = null;
  let lastActionRowActor = "";
  let presetSettleTimer = 0;
  const PRESET_SETTLE_MS = 1000;

  const stripHudUnit = value => String(value ?? "").replace(/\s*ББ\s*$/i, "").trim();

  function clearPresetSelection() {
    document.querySelectorAll(".quick-sizes .v038-size-selected").forEach(button => button.classList.remove("v038-size-selected"));
  }

  function selectPreset(button) {
    window.clearTimeout(presetSettleTimer);
    presetSettleTimer = 0;
    clearPresetSelection();
    button?.classList.add("v038-size-selected");
  }

  function presetAmount(button) {
    const input = document.getElementById("amount");
    if (button.classList.contains("v038-min-size")) return Number(input?.min || 0);
    if (button.classList.contains("v038-max-size")) return Number(input?.max || 0);
    return presetTarget(Number(button.dataset.sizing || 0));
  }

  function scheduleSettledPreset() {
    window.clearTimeout(presetSettleTimer);
    clearPresetSelection();
    presetSettleTimer = window.setTimeout(() => {
      presetSettleTimer = 0;
      const amount = Number(document.getElementById("amount")?.value || 0);
      const buttons = [...document.querySelectorAll(".quick-sizes button")];
      const nearest = buttons.reduce((best, button) => (
        !best || Math.abs(presetAmount(button) - amount) < Math.abs(presetAmount(best) - amount) ? button : best
      ), null);
      selectPreset(nearest);
    }, PRESET_SETTLE_MS);
  }

  function setAmountToBoundary(kind, button) {
    const input = document.getElementById("amount");
    if (!input) return;
    input.value = kind === "min" ? input.min : input.max;
    input.dispatchEvent(new Event("input", { bubbles:true }));
    selectPreset(button);
  }

  function closeSizingMode(render = true) {
    sizingMode = null;
    document.body.classList.remove("v038-sizing-open");
    document.getElementById("sizingWrap")?.setAttribute("aria-hidden", "true");
    if (render) queueSync();
  }

  function syncSizingModeText() {
    const amount = Number(document.getElementById("amount")?.value || 0);
    if (sizingMode) sizingMode.value = amount;
    setText(document.getElementById("mobileSizingAmount"), `${stripHudUnit(formatBB(amount))} BB`);
    setText(
      document.getElementById("mobileSizingConfirm"),
      sizingMode?.action === "raise" ? "ПОДТВЕРДИТЬ РЕЙЗ" : sizingMode?.action === "all_in" ? "ПОДТВЕРДИТЬ ALL-IN" : "ПОДТВЕРДИТЬ СТАВКУ",
    );
  }

  function openSizingMode(action, amount = null) {
    const bounds = amountBounds();
    const value = Math.min(bounds.max, Math.max(bounds.min, amount ?? bounds.value));
    sizingMode = { action, value };
    syncAmountControls(value);
    document.body.classList.add("v038-sizing-open");
    const wrap = document.getElementById("sizingWrap");
    if (wrap) {
      wrap.hidden = false;
      wrap.setAttribute("aria-hidden", "false");
    }
    syncSizingModeText();
    queueSync();
  }

  function verticalBetSteps() {
    const bounds = amountBounds();
    return [bounds.min, 2, 4, presetTarget(.5), presetTarget(.67), presetTarget(1), bounds.max]
      .map(value => Math.min(bounds.max, Math.max(bounds.min, Number(value || bounds.min))))
      .filter((value, index, values) => index === 0 || Math.abs(value - values[index - 1]) > 1e-9)
      .sort((left, right) => left - right)
      .filter((value, index, values) => index === 0 || Math.abs(value - values[index - 1]) > 1e-9);
  }

  function hideBetRail() {
    document.getElementById("mobileBetRail")?.setAttribute("aria-hidden", "true");
  }

  function beginVerticalBetGesture(event) {
    const button = event.target?.closest?.('[data-action-key="aggressive"]');
    if (!button || !isMobileV2() || !game || game.terminal || !localPlayerAlive()) return;
    const amount = Number(document.getElementById("amount")?.value || amountBounds().value || 0);
    const steps = verticalBetSteps();
    const startIndex = steps.reduce((best, value, index) => (
      Math.abs(value - amount) < Math.abs(steps[best] - amount) ? index : best
    ), 0);
    betGesture = {
      pointerId:event.pointerId,
      button,
      startY:event.clientY,
      startIndex,
      steps,
      active:false,
      action:Number(game.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "raise" : "bet",
    };
    button.setPointerCapture?.(event.pointerId);
  }

  function updateVerticalBetGesture(event) {
    if (!betGesture || event.pointerId !== betGesture.pointerId) return;
    const distance = betGesture.startY - event.clientY;
    if (!betGesture.active && Math.abs(distance) < 10) return;
    if (!betGesture.active) {
      betGesture.active = true;
      openSizingMode(betGesture.action, betGesture.steps[betGesture.startIndex]);
      document.getElementById("mobileBetRail")?.setAttribute("aria-hidden", "false");
    }
    event.preventDefault();
    const index = Math.min(
      betGesture.steps.length - 1,
      Math.max(0, betGesture.startIndex + Math.round(distance / 46)),
    );
    const value = betGesture.steps[index];
    syncAmountControls(value);
    syncSizingModeText();
    setText(document.getElementById("mobileBetRailAmount"), `${stripHudUnit(formatBB(value))} BB`);
    document.documentElement.style.setProperty("--v038-rail-y", `${event.clientY}px`);
  }

  function finishVerticalBetGesture(event) {
    if (!betGesture || event.pointerId !== betGesture.pointerId) return;
    const { active, button, pointerId } = betGesture;
    betGesture = null;
    button.releasePointerCapture?.(pointerId);
    hideBetRail();
    if (!active) return;
    button.dataset.v038SuppressClick = "1";
    window.setTimeout(() => button.removeAttribute("data-v038-suppress-click"), 0);
    syncSizingModeText();
    queueSync();
  }

  function confirmSizingMode() {
    if (!sizingMode || !game || game.terminal) return closeSizingMode();
    const { action, value } = sizingMode;
    const localTurn = isLocalHumanTurn();
    closeSizingMode(false);
    if (!localTurn) {
      togglePendingAction(action === "all_in" ? "all_in" : "aggressive");
      renderMobileSelectedCard();
      queueSync();
      return;
    }
    clearPendingAction(false);
    if (action === "all_in") return sendAction("all_in", 0);
    return sendAction(action, value);
  }

  function ensurePresetButtons() {
    const row = document.querySelector(".quick-sizes");
    if (!row) return;
    if (!presetSnapshot || presetSnapshot.some(item => !item.button.isConnected)) {
      const buttons = [...row.querySelectorAll("button:not(.v038-min-size)")].slice(0, 4);
      if (buttons.length < 4) return;
      presetSnapshot = buttons.map(button => ({
        button,
        className:button.className,
        html:button.innerHTML,
        sizing:button.getAttribute("data-sizing"),
        onclick:button.onclick,
      }));
    }
    const original = presetSnapshot.map(item => item.button);

    let min = row.querySelector(".v038-min-size");
    if (!min) {
      min = document.createElement("button");
      min.type = "button";
      min.className = "v038-boundary-size v038-min-size";
      row.prepend(min);
    }

    original[0].dataset.sizing = "0.50";
    original[1].dataset.sizing = "1.00";
    original[2].dataset.sizing = "0.67";
    original[3].removeAttribute("data-sizing");
    original[3].classList.add("v038-boundary-size", "v038-max-size");
    min.onclick = () => setAmountToBoundary("min", min);
    original.slice(0, 3).forEach(button => {
      button.onclick = () => {
        if (!game) return;
        syncAmountControls(presetTarget(Number(button.dataset.sizing || 0)));
        selectPreset(button);
      };
    });
    original[3].onclick = () => setAmountToBoundary("max", original[3]);

    const labels = ["1/2 POT", "POT", "2/3 POT"];
    original.slice(0, 3).forEach((button, index) => {
      let strong = button.querySelector("strong");
      if (!strong) {
        strong = document.createElement("strong");
        button.prepend(strong);
      }
      setText(strong, labels[index]);
    });
    setText(min, "MIN");
    setText(original[3], "MAX");
    row.querySelectorAll("button small").forEach(value => setText(value, stripHudUnit(value.textContent)));
  }

  function positionHudSummary(summary, host) {
    const pot = document.querySelector(".pot-total");
    const board = document.getElementById("board");
    if (!summary.classList.contains("on-felt") || !pot || !board) {
      summary.style.removeProperty("--v038-summary-top");
      return;
    }
    const hostRect = host.getBoundingClientRect();
    const potRect = pot.getBoundingClientRect();
    const boardRect = board.getBoundingClientRect();
    const summaryRect = summary.getBoundingClientRect();
    if (!potRect.height || !boardRect.height || !summaryRect.height || boardRect.top <= potRect.bottom) {
      summary.style.removeProperty("--v038-summary-top");
      return;
    }
    const top = (potRect.bottom + boardRect.top - summaryRect.height) / 2 - hostRect.top;
    summary.style.setProperty("--v038-summary-top", `${top}px`);
  }

  function ensureHudSummary() {
    // On a phone this belongs on the felt, in the gap between the pot and
    // the board -- down in the action panel it is outside where the eye is
    // during a hand. Desktop keeps it in the panel, which has room for the
    // stacked label/value pair. Re-checked on every sync, so a resize moves
    // it without any listener of its own.
    const onFelt = window.matchMedia?.("(max-width:780px)")?.matches ?? false;
    const host = document.querySelector(onFelt ? ".table-center" : ".action-panel");
    if (!host) return;
    let summary = document.querySelector(".v038-hud-summary");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "v038-hud-summary";
      // No БАНК column: the pot is printed on the felt immediately above
      // this strip, so carrying it here said the same number twice.
      summary.innerHTML = '<span>УРАВНЯТЬ<b data-v038-call>0.00</b></span><span>СТАВКА<b data-v038-bet>0.00</b></span>';
    }
    if (summary.parentElement !== host) {
      if (onFelt) host.appendChild(summary);
      else host.prepend(summary);
    }
    summary.classList.toggle("on-felt", onFelt);
    positionHudSummary(summary, host);
    const call = typeof estimatedLocalToCall === "function" ? formatBB(estimatedLocalToCall()) : "0.00 ББ";
    const raw = Number(document.getElementById("amount")?.value);
    const amount = typeof formatBB === "function" && Number.isFinite(raw) ? formatBB(raw) : "0.00";
    setText(summary.querySelector("[data-v038-call]"), stripHudUnit(call));
    setText(summary.querySelector("[data-v038-bet]"), stripHudUnit(amount));
  }

  function mobileActionDefinitions({ localTurn, legal, toCall, amount, allInTotal, aggressiveLabel }) {
    const available = action => !localTurn || legal.includes(action);
    // One arrangement whether or not there is a bet to call, because the
    // hand a thumb has learned should not move between streets:
    //
    //     ALL-IN  |  CHECK/CALL
    //     FOLD    |  RAISE/BET
    //
    // The grid fills left to right, top to bottom, so this order is the
    // layout. Leaving is on the left, staying in is on the right.
    if (toCall > 0) {
      return [
        { key:"all_in", label:"ALL-IN", amount:stripHudUnit(formatBB(allInTotal)), cls:"all-in", edge:"left", slot:"top", enabled:available("all_in"), allIn:true },
        { key:"call", label:"CALL", amount:stripHudUnit(formatBB(toCall)), cls:"call", edge:"right", slot:"top", enabled:available("call") },
        { key:"fold", label:"FOLD", amount:"", cls:"fold", edge:"left", slot:"bottom", enabled:available("fold") },
        { key:"aggressive", label:aggressiveLabel, amount:stripHudUnit(formatBB(amount)), cls:"raise", edge:"right", slot:"bottom", enabled:available("raise") },
      ].filter(def => def.enabled);
    }
    return [
      { key:"all_in", label:"ALL-IN", amount:stripHudUnit(formatBB(allInTotal)), cls:"all-in", edge:"left", slot:"top", enabled:available("all_in"), allIn:true },
      { key:"check", label:"CHECK", amount:"", cls:"check", edge:"right", slot:"top", enabled:available("check") },
      { key:"fold", label:"FOLD", amount:"", cls:"fold", edge:"left", slot:"bottom", enabled:available("fold") },
      { key:"aggressive", label:"BET", amount:stripHudUnit(formatBB(amount)), cls:"raise", edge:"right", slot:"bottom", enabled:available("bet") },
    ].filter(def => def.enabled);
  }

  function configureReferenceActions() {
    const grid = document.getElementById("actionButtons");
    if (!grid) return;
    const alive = localPlayerAlive();
    if (!game || game.terminal || !alive) {
      grid.innerHTML = "";
      delete grid.dataset.v038ActionSignature;
      return;
    }
    const localTurn = isLocalHumanTurn();
    // Never leave a row of action-looking but inert buttons during result,
    // countdown, observer and folded states. An active opponent turn is still
    // interactive: taps there create a safely revalidated pre-action.
    if (!game || game.terminal || !alive) {
      const title = game?.terminal ? "НОВАЯ РАЗДАЧА СКОРО" : "ДЕЙСТВИЯ НЕДОСТУПНЫ";
      const detail = game?.terminal ? "Стол запускается автоматически" : "Сядьте за стол или дождитесь следующей раздачи";
      grid.dataset.v038ReferenceActions = "1";
      grid.innerHTML = `<div class="v038-actions-unavailable" role="status"><strong>${title}</strong><span>${detail}</span></div>`;
      return;
    }
    const legal = game?.human_legal_actions || [];
    const toCall = estimatedLocalToCall();
    const amount = Number(document.getElementById("amount")?.value || amountBounds().value || 0);
    const bounds = amountBounds();
    const allInTotal = Number(localViewerPlayer()?.stack || 0) + Number(localViewerPlayer()?.street_invested || 0);
    const aggressiveLabel = Number(game?.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "RAISE" : "BET";
    const actorNow = `${game?.hand_id || ""}:${game?.acting_player || ""}`;
    const actorChanged = actorNow !== lastActionRowActor;
    lastActionRowActor = actorNow;
    const defs = mobileActionDefinitions({ localTurn, legal, toCall, amount, allInTotal, aggressiveLabel });
    const aggressive = defs.find(def => def.key === "aggressive");
    const atMax = Math.abs(amount - Number(bounds.max || 0)) < 1e-9;
    // Only when there is no ALL-IN slot of its own to say it. Raising to the
    // maximum *is* all-in, and with the dedicated button present this used to
    // put the same word on two of the four.
    const hasAllInSlot = defs.some(def => def.key === "all_in");
    if (aggressive && atMax && !hasAllInSlot) {
      aggressive.label = "ALL-IN";
      aggressive.amount = stripHudUnit(formatBB(allInTotal));
      aggressive.cls = "all-in";
      aggressive.allIn = true;
    }
    const signature = defs.map(def => def.key).join("|");
    if (grid.dataset.v038ActionSignature !== signature || grid.children.length !== defs.length) {
      grid.innerHTML = "";
      defs.forEach(() => grid.appendChild(document.createElement("button")));
      grid.dataset.v038ActionSignature = signature;
    }
    grid.dataset.v038ReferenceActions = "1";
    [...grid.children].forEach((button, index) => {
      try {
        const def = defs[index];
        button.type = "button";
        button.dataset.actionKey = def.key;
        button.dataset.edge = def.edge;
        button.dataset.slot = def.slot;
        button.dataset.v038ReferenceAction = "1";
        button.className = `action-slot ${def.cls}`;
        button.classList.toggle("queued", pendingAction?.kind === def.key);
        let label = button.querySelector(".v038-action-label");
        let value = button.querySelector(".v038-action-amount");
        if (!label || !value) {
          button.innerHTML = '<span class="v038-action-label"></span><span class="v038-action-amount"></span>';
          label = button.firstElementChild;
          value = button.lastElementChild;
        }
        setText(label, def.label);
        if (value.textContent !== def.amount) {
          setText(value, def.amount);
          if (!actorChanged) {
            value.classList.remove("v038-amount-pulse");
            void value.offsetWidth;
            value.classList.add("v038-amount-pulse");
          }
        }
        button.setAttribute("aria-label", `${def.label}${def.amount ? ` ${def.amount}` : ""}`);
        button.disabled = Boolean(window.Poker8Transport?.isActionPending?.());
        if (!localTurn) {
          button.setAttribute("aria-description", "Предвыбор: действие будет перепроверено на вашем ходе");
        } else {
          button.removeAttribute("aria-description");
        }
        button.onclick = () => {
          if (button.dataset.v038SuppressClick) {
            button.removeAttribute("data-v038-suppress-click");
            return;
          }
          if (!game || game.terminal || !localPlayerAlive() || window.Poker8Transport?.isActionPending?.()) return;
          const liveTurn = isLocalHumanTurn();
          const liveLegal = game.human_legal_actions || [];
          const liveAmount = Number(document.getElementById("amount")?.value || amountBounds().value || 0);
          if (def.key === "aggressive") {
            if (liveTurn && !liveLegal.some(action => ["bet", "raise", "all_in"].includes(action))) return queueSync();
            return openSizingMode(aggressiveLabel === "RAISE" ? "raise" : "bet", liveAmount);
          }
          if (def.allIn) {
            if (liveTurn && !liveLegal.includes("all_in")) return queueSync();
            return openSizingMode("all_in", amountBounds().max);
          }
          if (liveTurn && !liveLegal.includes(def.key)) return queueSync();
          if (!liveTurn) {
            togglePendingAction(def.key);
            renderMobileSelectedCard();
            queueSync();
            return;
          }
          clearPendingAction(false);
          return sendAction(def.key, 0);
        };
      } catch (error) {
        console.error("[v038] configureReferenceActions button failed", error);
      }
    });
  }

  function teardownFinalReference() {
    if (!referenceActive) return;
    referenceActive = false;
    closeSizingMode(false);
    betGesture = null;
    hideBetRail();
    clearPresetSelection();
    window.clearTimeout(presetSettleTimer);
    presetSettleTimer = 0;
    window.clearInterval(turnVisualTicker);
    turnVisualTicker = 0;
    turnVisualToken = "";
    cancelRoomReset();
    document.body.classList.remove("v038-sizing-open", "v038-room-awaiting");
    document.getElementById("sizingWrap")?.setAttribute("aria-hidden", "true");
    document.getElementById("mobileBetRail")?.setAttribute("aria-hidden", "true");
    document.querySelector(".v038-turn-timer")?.remove();
    document.querySelector(".v038-turn-context")?.remove();
    document.querySelector(".v038-room-prompt")?.remove();
    document.querySelectorAll(".seat-card").forEach(card => card.classList.remove(...ACTION_CLASSES));
    document.querySelectorAll(".seat-stack[data-v038-full-stack]").forEach(stack => {
      setText(stack, stack.dataset.v038FullStack);
      stack.removeAttribute("data-v038-full-stack");
      stack.removeAttribute("aria-label");
    });
    document.querySelectorAll("[data-v038-full-value]").forEach(label => {
      setText(label, label.dataset.v038FullValue);
      label.removeAttribute("data-v038-full-value");
      label.removeAttribute("aria-label");
    });
    document.querySelector(".v038-hud-summary")?.remove();
    document.querySelector(".v038-min-size")?.remove();
    presetSnapshot?.forEach(item => {
      const { button } = item;
      button.className = item.className;
      button.innerHTML = item.html;
      button.onclick = item.onclick;
      if (item.sizing == null) button.removeAttribute("data-sizing");
      else button.setAttribute("data-sizing", item.sizing);
    });
    if (typeof refreshQuickSizeLabels === "function") refreshQuickSizeLabels();
    document.getElementById("actionButtons")?.removeAttribute("data-v038-reference-actions");
    if (typeof renderPersistentActionButtons === "function") renderPersistentActionButtons();
  }

  // The action buttons are the one control a player cannot play without --
  // an exception thrown by any earlier cosmetic step (stack labels, ready
  // marks, the turn HUD...) must never be able to stop configureReferenceActions
  // from running. Each step is isolated so one bad step can't take the rest down.
  //: The chips sit this far above the pot plate.
  const POT_CHIP_GAP = 4;

  // The cluster's height is not fixed -- it grows with the pot, since taller
  // stacks mean a taller box -- so a single top in the stylesheet is right
  // for one pot size and wrong for the rest: too low and the chips sit on
  // the plate, too high and they drift toward the board. Measure both boxes
  // instead and close the gap to POT_CHIP_GAP.
  //
  // Worked as a correction to wherever the chips currently are, rather than
  // as a position inside the felt, so it does not care which ancestor the
  // chips are actually positioned against. Once applied the correction is
  // zero, so re-running it on every sync is stable.
  function syncPotChipStack() {
    const chips = document.getElementById("potChips");
    const pot = document.querySelector(".pot-total");
    if (!chips || !pot) return;
    const chipsBox = chips.getBoundingClientRect();
    const potBox = pot.getBoundingClientRect();
    const currentTop = parseFloat(getComputedStyle(chips).top);
    // Nothing to measure -- an empty pot, or a felt that has not been painted
    // yet. The stylesheet's own top is the fallback, so give it back rather
    // than freezing the chips wherever the last measured pot left them.
    if (!chipsBox.height || !potBox.height || !Number.isFinite(currentTop)) {
      chips.style.removeProperty("top");
      return;
    }
    const corrected = currentTop + (potBox.top - POT_CHIP_GAP - chipsBox.bottom);
    chips.style.setProperty("top", `${Math.round(corrected)}px`, "important");
  }

  function runSyncStep(fn) {
    try {
      fn();
    } catch (error) {
      console.error(`[v038] ${fn.name} failed`, error);
    }
  }

  function syncFinalReference() {
    if (!isMobileV2()) {
      teardownFinalReference();
      return;
    }
    referenceActive = true;
    const legal = game?.human_legal_actions || [];
    const aggressiveLegal = !isLocalHumanTurn() || legal.includes("bet") || legal.includes("raise") || legal.includes("all_in");
    if (sizingMode && (!game || game.terminal || !localPlayerAlive() || !aggressiveLegal)) closeSizingMode(false);
    runSyncStep(ensurePresetButtons);
    runSyncStep(ensureHudSummary);
    runSyncStep(ensureMobileHeaderControls);
    runSyncStep(syncSeatStackLabels);
    runSyncStep(syncTableNumberLabels);
    runSyncStep(syncAvatarReadyControl);
    runSyncStep(syncAllSeatReadyMarks);
    runSyncStep(syncSeatActionStates);
    runSyncStep(ensureReadyCountdown);
    runSyncStep(syncTableTurnHud);
    runSyncStep(syncCompletedHandReset);
    runSyncStep(configureReferenceActions);
    runSyncStep(syncSizingModeText);
    runSyncStep(syncPotChipStack);
  }

  let syncQueued = false;
  const queueSync = () => {
    if (syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(() => {
      syncQueued = false;
      syncFinalReference();
    });
  };

  // A rejected action -- or a resync that lands back on unchanged state --
  // never moves online-table.js's own snapshot-dedup hash (revision,
  // acting_player, stacks, ...), so renderSnapshot() short-circuits and
  // configureReferenceActions() never runs again. isActionPending() itself
  // goes back to false (the transport is healthy, the overlay disappears),
  // but the buttons stay disabled from the render that fired while it was
  // still true -- inert for the rest of that turn, reported live as the
  // action row simply freezing. Force one more pass whenever pending flips
  // back off, independent of whether the snapshot actually changed.
  window.addEventListener("poker8:action-pending", event => {
    if (!event.detail?.pending) queueSync();
  });

  const previousSync = window.syncComponentUi;
  window.syncComponentUi = function syncV038FinalReference(gameState, tableState) {
    previousSync?.(gameState, tableState);
    queueSync();
  };

  const previousQueueAutomation = queueAutomation;
  queueAutomation = function queueV038Automation(delay = null) {
    if (isMobileV2() && game?.terminal) {
      clearAutomationTimer();
      return;
    }
    return previousQueueAutomation(delay);
  };

  const start = () => {
    syncFinalReference();
    const buttons = document.getElementById("actionButtons");
    if (buttons) {
      new MutationObserver(queueSync).observe(buttons, { childList:true });
      buttons.addEventListener("pointerdown", beginVerticalBetGesture);
      window.addEventListener("pointermove", updateVerticalBetGesture, { passive:false });
      window.addEventListener("pointerup", finishVerticalBetGesture);
      window.addEventListener("pointercancel", finishVerticalBetGesture);
    }
    const connection = document.getElementById("connectionStatus");
    if (connection) new MutationObserver(syncConnectionDot).observe(connection, { childList:true, characterData:true, subtree:true });
    const sizing = document.getElementById("sizingWrap");
    if (sizing && !sizing.dataset.v038InputSync) {
      sizing.dataset.v038InputSync = "1";
      sizing.addEventListener("input", event => {
        if (event.target?.matches?.("#amountSlider")) scheduleSettledPreset();
        else clearPresetSelection();
        syncSizingModeText();
        queueSync();
      });
    }
    document.getElementById("mobileSizingConfirm")?.addEventListener("click", confirmSizingMode);
    document.getElementById("mobileSizingCancel")?.addEventListener("click", () => closeSizingMode());
    if (!document.body.dataset.v038ClickSync) {
      document.body.dataset.v038ClickSync = "1";
      document.addEventListener("click", event => {
        if (event.target?.closest?.("#amountMinus,#amountPlus")) clearPresetSelection();
      });
    }
  };

  window.addEventListener("resize", queueSync);
  window.addEventListener("poker8:ready-countdown", event => setReadyCountdown(event.detail?.endsAt));
  window.addEventListener("poker8:ready-snapshot", event => {
    viewerReadySnapshot = Boolean(event.detail?.viewerReady && event.detail?.preHand);
    syncAvatarReadyControl();
  });
  document.addEventListener("click", event => {
    if (window.Poker8OnlineTable) return;
    if (!isMobileV2() || game || !event.target?.closest?.('.seat[data-visual-seat="0"], .v038-room-prompt')) return;
    window.dispatchEvent(new CustomEvent("poker8:toggle-ready"));
  });
  document.addEventListener("keydown", event => {
    if (window.Poker8OnlineTable) return;
    if (!isMobileV2() || game || !["Enter", " "].includes(event.key) || !event.target?.matches?.('.seat[data-visual-seat="0"] .avatar-wrap, .v038-room-prompt')) return;
    event.preventDefault();
    window.dispatchEvent(new CustomEvent("poker8:toggle-ready"));
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once:true });
  else start();
})();
