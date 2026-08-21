(() => {
  "use strict";

  // The class is the switch now: it is added at every width, so the media
  // half of this test only kept desktop out of everything below.
  const isMobileV2 = () => document.body.classList.contains("poker8-v2-sixmax");

  const style = document.createElement("style");
  style.id = "v038-poker8-v2-cinematic-table-style";
  style.textContent = `
    /* Was @media (max-width:780px). The v2 table is the table now, at every
       width; desktop geometry is tuned in v039. */
    @media all{
      body.v014.poker8-v2-sixmax{
        --p8-wood-dark:#120804;
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
          repeating-linear-gradient(96deg,#080402 0 7px,#180b05 8px 14px,#0c0503 15px 23px)!important;
      }

      body.v014.poker8-v2-sixmax .mobile-game-header::after{display:none!important;content:none!important;}
      body.v014.poker8-v2-sixmax .mobile-game-header{
        background-image:
          linear-gradient(90deg,rgba(0,3,2,.86),transparent 38%,transparent 62%,rgba(0,3,2,.86)),
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

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{left:50%!important;top:80%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:7%!important;top:58%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:7%!important;top:22%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{left:50%!important;top:13%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:84%!important;top:22%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:84%!important;top:58%!important;}

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
        transform:rotateX(5deg) scale(.985,1.025)!important;
        transform-origin:50% 54%!important;
        transform-style:preserve-3d!important;
        background:transparent!important;
        outline:0!important;
        box-shadow:none!important;
      }

      body.v014.poker8-v2-sixmax .felt::before,
      body.v014.poker8-v2-sixmax .felt::after{display:none!important;}

      body.v014.poker8-v2-sixmax .felt :is(.seat-card,.board-cards .card,.pot-total>*,.pot-chips>*,.bet-marker>*){
        rotate:x -5deg;
      }

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
          #050707;
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
        background-image:var(--profile-avatar-image,radial-gradient(circle at 50% 32%,hsla(var(--seat-accent),62%,46%,.45),transparent 31%),radial-gradient(circle at 50% 78%,#07110e 0 42%,#010303 70%))!important;
        background-position:center!important;
        background-size:cover!important;
        color:#f5fff9!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 16px hsla(var(--seat-accent),96%,58%,.46),inset 0 -10px 18px rgba(0,0,0,.50)!important;
        font-size:15px!important;
      }
      body.v014.poker8-v2-sixmax .player-avatar span{opacity:0!important;}
      body.v014.poker8-v2-sixmax .player-avatar::before{
        content:"";position:absolute;z-index:2;left:16%;right:16%;top:14%;height:52%;border-radius:48% 48% 42% 42% / 54% 54% 32% 32%;
        background:
          radial-gradient(ellipse at 50% 45%,rgba(3,10,8,.22) 0 24%,rgba(0,2,2,.90) 55%,#000 76%),
          linear-gradient(135deg,hsla(var(--seat-accent),58%,24%,.62),#010303 58%);
        clip-path:polygon(50% 0,84% 16%,100% 72%,76% 92%,63% 68%,50% 61%,37% 68%,24% 92%,0 72%,16% 16%);
        filter:drop-shadow(0 0 5px hsla(var(--seat-accent),92%,60%,.32));
      }
      body.v014.poker8-v2-sixmax .player-avatar::after{
        content:"";position:absolute;z-index:1;left:7%;right:7%;bottom:-3%;height:54%;border-radius:50% 50% 42% 42%;
        background:radial-gradient(ellipse at 50% 0,hsla(var(--seat-accent),52%,24%,.30),transparent 50%),linear-gradient(160deg,#07100d,#000 72%);
        clip-path:polygon(17% 13%,39% 0,61% 0,83% 13%,100% 100%,0 100%);
      }
      body.v014.poker8-v2-sixmax .player-avatar[style*="--profile-avatar-image"]::before,
      body.v014.poker8-v2-sixmax .player-avatar[style*="--profile-avatar-image"]::after{display:none!important;}
      body.v014.poker8-v2-sixmax .player-avatar[style*="--profile-avatar-image"] span{opacity:1!important;}

      body.v014.poker8-v2-sixmax .seat-identity{
        position:absolute!important;z-index:6;left:50%!important;top:47px!important;transform:translateX(-50%)!important;
        width:96px!important;min-height:38px!important;padding:6px 7px 5px!important;border-radius:9px!important;
        transition:border-color 220ms ease,box-shadow 220ms ease,filter 220ms ease!important;
        border:1px solid hsla(var(--seat-accent),90%,60%,.72)!important;background:linear-gradient(180deg,rgba(9,8,10,.98),rgba(1,3,4,.995))!important;
        box-shadow:0 0 12px hsla(var(--seat-accent),92%,55%,.24),0 7px 14px rgba(0,0,0,.62)!important;text-align:center!important;
      }
      body.v014.poker8-v2-sixmax .seat-topline{display:block!important;}
      /* The plate is 92px wide; the name was capped at 68 and cut inside a box
         that had room to spare. It takes the plate now, and seatDisplayName
         keeps what it hands over short enough to land. */
      body.v014.poker8-v2-sixmax .seat-name{max-width:100%!important;font-size:10px!important;line-height:1.1!important;}
      body.v014.poker8-v2-sixmax .seat-stack{margin-top:3px!important;font-size:15px!important;line-height:1!important;color:var(--seat-neon)!important;}
      body.v014.poker8-v2-sixmax .seat-name,
      body.v014.poker8-v2-sixmax .seat-stack{margin-inline:auto!important;}
      body.v014.poker8-v2-sixmax .bot-level{display:none!important;}
      body.v014.poker8-v2-sixmax .position-chip{display:none!important;font-size:10px!important;padding:1px 3px!important;}
      body.v014.poker8-v2-sixmax .seat-meta{margin-top:3px!important;}
      body.v014.poker8-v2-sixmax .seat-card > .v024-ready-badge{display:none!important;}
      body.v014.poker8-v2-sixmax .player-status:is(.status-fold,.status-turn,.status-thinking){display:none!important;}
      body.v014.poker8-v2-sixmax .v028-center-ready{display:none!important;}
      body.v014.poker8-v2-sixmax .deck-anchor{display:none!important;}

      /* Above the label, not across it. Both hang off one variable, so the
         ring follows the prompt when a five or six handed layout moves it
         down -- they used to be positioned independently and overlapped. */
      body.v014.poker8-v2-sixmax .v038-ready-countdown{
        position:absolute;z-index:74;left:50%;top:calc(var(--p8-prompt-y, 36%) - 64px);transform:translate(-50%,-50%);
        display:none;place-items:center;width:62px;height:62px;border-radius:50%;
        border:2px solid #72ffb5;background:rgba(1,20,13,.88);color:#e8fff3;
        box-shadow:0 0 0 3px rgba(0,5,3,.72),0 0 22px rgba(72,255,169,.58),inset 0 0 18px rgba(70,255,170,.14);
        font-size:27px;font-weight:950;text-shadow:0 0 10px rgba(98,255,190,.86);pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .v038-ready-countdown.visible{display:grid;}

      body.v014.poker8-v2-sixmax .v038-turn-timer,
      body.v014.poker8-v2-sixmax .v038-turn-context{
        position:absolute;z-index:73;bottom:18px;display:none;pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .v038-turn-timer.visible{display:grid;}
      body.v014.poker8-v2-sixmax .v038-turn-timer{
        left:calc(25% - 20.5px);width:54px;height:54px;transform:translateX(-50%);place-items:center;border-radius:50%;
        background:conic-gradient(#ff38c7 var(--timer-progress,100%),rgba(255,56,199,.12) 0);
        filter:drop-shadow(0 0 9px rgba(255,56,199,.66));
      }
      body.v014.poker8-v2-sixmax .v038-turn-timer::before{
        content:"";position:absolute;inset:4px;border-radius:50%;background:#07100d;border:1px solid rgba(255,95,215,.72);
      }
      body.v014.poker8-v2-sixmax .v038-turn-timer b{position:relative;color:#fff;font-size:20px;line-height:1;text-shadow:0 0 7px #ff38c7;}
      body.v014.poker8-v2-sixmax .v038-turn-timer small{position:absolute;bottom:-11px;color:#ff87df;font-size:10px;font-weight:900;letter-spacing:.08em;}
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
        border:2px solid #72ffb5;background:rgba(0,30,20,.38);color:#dffff0;
        box-shadow:0 0 0 2px rgba(0,8,5,.72),0 0 18px rgba(72,255,169,.72),inset 0 0 14px rgba(83,255,181,.18);
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
        border:1px solid #71ffc1;background:#031b13;color:#fff;font-size:12px;font-weight:950;
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
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-name{font-size:10px!important;max-width:66px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{font-size:15px!important;color:#35c6ff!important;}

      body.v014.poker8-v2-sixmax .seat-card.v038-action-fold .player-avatar{
        border-color:#ff4d42!important;box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 20px rgba(255,77,66,.64),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v038-action-passive .player-avatar{
        border-color:#55cfff!important;box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 20px rgba(85,207,255,.62),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v038-action-aggressive .player-avatar{
        border-color:#55f16e!important;box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 20px rgba(85,241,110,.62),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v038-action-all-in .player-avatar{
        border-color:#ffc44d!important;box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 22px rgba(255,196,77,.70),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.v032-folded.v038-action-fold{opacity:1!important;filter:none!important;}

      body.v014.poker8-v2-sixmax .v038-room-prompt{
        /* y:36% sits over the pot/board strip, which is empty whenever this
           prompt shows (no hand running) -- and it's the one vertical band
           every seat layout now deliberately avoids, so the prompt can no
           longer land on top of another seat's avatar. */
        position:absolute;z-index:72;left:50%;top:var(--p8-prompt-y, 36%);transform:translate(-50%,-50%);display:none;width:max-content;max-width:78%;
        padding:10px 14px;border:1px solid rgba(61,235,190,.58);border-radius:12px;background:rgba(1,18,13,.88);text-align:center;
        box-shadow:0 0 18px rgba(46,239,186,.22);pointer-events:auto;cursor:pointer;
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
      @keyframes v038ReadyPulse{50%{border-color:#6edcff;box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 28px rgba(67,199,255,.82),inset 0 -10px 18px rgba(0,0,0,.50)}}

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
        box-shadow:inset 0 0 0 2px rgba(0,0,0,.48),0 0 9px hsla(var(--seat-accent),94%,58%,.28)!important;
      }
      body.v014.poker8-v2-sixmax .player-cards .card.back:first-child{transform:rotate(-8deg) translateX(2px)!important;}
      body.v014.poker8-v2-sixmax .player-cards .card.back:last-child{transform:rotate(8deg) translateX(-2px)!important;}

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards{top:-47px!important;z-index:9!important;gap:4px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card{
        width:43px!important;height:61px!important;border-radius:6px!important;
        background:linear-gradient(150deg,#07110d,#010303)!important;
        color:#effff7!important;border:1px solid #56c8ff!important;
        box-shadow:0 0 12px rgba(47,184,255,.54),0 5px 10px rgba(0,0,0,.50),inset 0 0 10px rgba(58,208,255,.08)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card.red{color:#ff6759!important;border-color:#ff674d!important;box-shadow:0 0 12px rgba(255,87,70,.46),0 5px 10px rgba(0,0,0,.50)!important;}
      body.v014.poker8-v2-sixmax .viewer-seat .player-cards .card-rank{left:5px!important;top:3px!important;font-size:15px!important;font-weight:950!important;}
      body.v014.poker8-v2-sixmax .viewer-seat .player-cards .card-suit{font-size:27px!important;filter:drop-shadow(0 0 4px currentColor)!important;}
      body.v014.poker8-v2-sixmax .player-cards .card:not(.back){
        background:linear-gradient(150deg,#07110d,#010303)!important;color:#edfff7!important;
        border-color:hsla(var(--seat-accent),100%,70%,.88)!important;box-shadow:0 0 10px hsla(var(--seat-accent),96%,58%,.42)!important;
      }

      body.v014.poker8-v2-sixmax .board-cards{gap:3px!important;}
      body.v014.poker8-v2-sixmax .board-cards .card{
        width:45px!important;height:63px!important;
        border:1px solid rgba(98,255,170,.82)!important;border-radius:5px!important;
        background:linear-gradient(150deg,#07110d 0%,#010303 100%)!important;
        color:#ecfff4!important;
        box-shadow:0 0 10px rgba(48,255,158,.36),0 6px 10px rgba(0,0,0,.58),inset 0 0 12px rgba(32,255,147,.07)!important;
      }
      body.v014.poker8-v2-sixmax .board-cards .card.red{color:#df392c!important;border-color:#ff5f43!important;box-shadow:0 0 9px rgba(255,82,54,.26),0 5px 9px rgba(0,0,0,.48)!important;}

      body.v014.poker8-v2-sixmax .pot-total{
        min-width:74px!important;padding:4px 9px!important;border-radius:7px!important;
        border-color:rgba(60,225,150,.22)!important;background:rgba(1,31,18,.66)!important;
        box-shadow:inset 0 0 12px rgba(57,228,152,.04),0 4px 11px rgba(0,0,0,.34)!important;
      }
      body.v014.poker8-v2-sixmax .pot-total-label{font-size:10px!important;letter-spacing:.08em!important;}
      body.v014.poker8-v2-sixmax .pot-total strong{font-size:20px!important;line-height:1!important;}
      /* v019-center-polish sets display:flex!important on the same selector
         family, so the hide needs !important here to actually win. */
      body.v014.poker8-v2-sixmax.p8-no-pot .pot-total{display:none!important;}

      body.v014.poker8-v2-sixmax .pot-chips .chip-cluster.pot-cluster{height:52px!important;min-width:124px!important;filter:drop-shadow(0 8px 6px rgba(0,0,0,.54))!important;}
      body.v014.poker8-v2-sixmax .pot-chips .chip-column.pot-stack{width:22px!important;height:48px!important;}
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
        margin-top:-4px!important;padding:2px 6px!important;border:0!important;background:rgba(1,7,6,.84)!important;
        color:#ecfff5!important;font-size:12px!important;font-weight:900!important;line-height:1!important;
        text-shadow:0 0 5px rgba(236,255,245,.42)!important;box-shadow:0 2px 5px rgba(0,0,0,.42)!important;
      }

      body.v014.poker8-v2-sixmax .dealer-button{
        border:1px solid #ecece2!important;background:radial-gradient(circle at 32% 28%,#fff,#d9d9ce 60%,#83867c)!important;
        color:#181a17!important;box-shadow:0 2px 6px rgba(0,0,0,.62)!important;
      }

      body.v014.poker8-v2-sixmax .seat .seat-card.v032-in-hand:not(.v032-active-turn){
        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn{
        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .player-avatar{
        border-color:#55fff2!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 25px rgba(85,255,242,.78),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .player-avatar,
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .seat-identity{
        animation:v038ActiveTurnPulse 1.35s ease-in-out infinite;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .seat-identity{
        border-color:#55fff2!important;
        box-shadow:0 0 18px rgba(85,255,242,.66),0 7px 14px rgba(0,0,0,.62)!important;
      }
      /* Pulse the outline only: box-shadow here loses to the !important base rules,
         so the glow has to ride on filter, and drop-shadow traces the element edge
         instead of washing the whole plate like brightness() did. */
      @keyframes v038ActiveTurnPulse{0%,100%{filter:drop-shadow(0 0 2px rgba(85,255,242,.40))}50%{filter:drop-shadow(0 0 9px rgba(85,255,242,.95))}}
      @media (prefers-reduced-motion:reduce){body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn :is(.player-avatar,.seat-identity){animation:none!important;}}
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
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 18px rgba(238,180,65,.45),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }

      body.v014.poker8-v2-sixmax .pot-total{top:25%!important;}
      body.v014.poker8-v2-sixmax .board-cards{top:38%!important;}
      body.v014.poker8-v2-sixmax .pot-chips{top:47%!important;}

      body.v014.poker8-v2-sixmax .sidebar{transform:none!important;height:var(--p8-hud-h)!important;}
      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        display:block!important;
        width:100%!important;height:var(--p8-hud-h)!important;min-height:var(--p8-hud-h)!important;
        padding:7px 8px!important;margin:0!important;overflow:hidden!important;
        border:1px solid rgba(83,123,112,.46)!important;border-radius:0!important;
        background:linear-gradient(180deg,rgba(7,13,12,.995),rgba(1,4,4,1))!important;
        box-shadow:0 -8px 24px rgba(0,0,0,.52),inset 0 0 22px rgba(50,255,191,.025)!important;
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
        display:grid;grid-template-columns:repeat(3,1fr);align-items:center;text-align:center;
        border-bottom:1px solid rgba(95,132,121,.18);font-size:10px;letter-spacing:.10em;color:#8ca59c;
      }
      body.v014.poker8-v2-sixmax .v038-hud-summary b{display:block;margin-top:1px;font-size:15px;line-height:1;color:#39bfff;letter-spacing:0;}
      body.v014.poker8-v2-sixmax .v038-hud-summary span:nth-child(2) b{color:#59e77c;}
      body.v014.poker8-v2-sixmax .v038-hud-summary span:nth-child(3) b{color:#ff9e45;}
      body.v014.poker8-v2-sixmax .sizing-wrap{display:contents!important;}
      body.v014.poker8-v2-sixmax .sizing-wrap > label{display:none!important;}
      body.v014.poker8-v2-sixmax .quick-sizes{
        position:absolute!important;left:8px;right:8px;top:35px!important;height:39px;
        display:grid!important;grid-template-columns:repeat(5,1fr)!important;gap:4px!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button{
        min-height:39px!important;height:39px!important;padding:3px 2px!important;border-radius:6px!important;font-size:10px!important;
        color:#fff!important;text-shadow:0 0 5px rgba(255,255,255,.48)!important;
        transition:color 180ms ease,border-color 180ms ease,box-shadow 180ms ease,background 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button strong{display:block;font-size:10px!important;line-height:1!important;color:#fff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button small{display:block;margin-top:3px;font-size:10px!important;line-height:1!important;color:#f4f7ff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button.v038-max-size{
        color:#fff5bd!important;border-color:rgba(255,196,77,.88)!important;background:rgba(45,31,6,.78)!important;
        box-shadow:0 0 11px rgba(255,184,45,.28),inset 0 0 8px rgba(255,196,77,.10)!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button.v038-size-selected{
        color:#fff!important;border-color:#ff3bd5!important;background:rgba(55,4,47,.94)!important;
        box-shadow:0 0 0 1px rgba(255,59,213,.45),0 0 13px rgba(255,59,213,.72),inset 0 0 10px rgba(255,59,213,.16)!important;
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
        height:6px;border:0;border-radius:999px;background:linear-gradient(90deg,#21b8ff 0%,#7357ff 34%,#ff39cf 68%,#ffc83d 100%);
        box-shadow:0 0 8px rgba(65,196,255,.55),0 0 10px rgba(255,57,207,.38);
      }
      body.v014.poker8-v2-sixmax #amountSlider::-moz-range-track{
        height:6px;border:0;border-radius:999px;background:linear-gradient(90deg,#21b8ff 0%,#7357ff 34%,#ff39cf 68%,#ffc83d 100%);
        box-shadow:0 0 8px rgba(65,196,255,.55),0 0 10px rgba(255,57,207,.38);
      }
      body.v014.poker8-v2-sixmax #amountSlider::-webkit-slider-thumb{
        width:17px;height:17px;margin-top:-6px;appearance:none;border:2px solid #fff;border-radius:50%;background:#ff3bd2;
        box-shadow:0 0 0 2px rgba(255,59,210,.32),0 0 12px #ff3bd2;
      }
      body.v014.poker8-v2-sixmax #amountSlider::-moz-range-thumb{
        width:17px;height:17px;border:2px solid #fff;border-radius:50%;background:#ff3bd2;
        box-shadow:0 0 0 2px rgba(255,59,210,.32),0 0 12px #ff3bd2;
      }
      body.v014.poker8-v2-sixmax .amount-row{display:none!important;}
      body.v014.poker8-v2-sixmax .action-grid{
        order:5;display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:repeat(2,44px)!important;gap:5px!important;
        position:absolute!important;z-index:4;left:8px;right:8px;bottom:4px!important;height:93px!important;
        padding:2px 0!important;background:#010403!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot{
        --v038-action:#49caff;
        position:relative;grid-column:auto!important;grid-row:auto!important;width:auto!important;max-width:none!important;min-width:0!important;min-height:44px!important;height:44px!important;border-radius:8px!important;font-size:10px!important;
        color:var(--v038-action)!important;border-color:var(--v038-action)!important;background:rgba(1,7,8,.98)!important;
        box-shadow:0 0 10px color-mix(in srgb,var(--v038-action) 38%,transparent),inset 0 0 9px color-mix(in srgb,var(--v038-action) 10%,transparent)!important;
        transition:color 180ms ease,border-color 180ms ease,box-shadow 180ms ease,background 180ms ease,filter 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot.fold{--v038-action:#ff4d42;}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.check{--v038-action:#55cfff;}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.call{--v038-action:#39c8ff;}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.raise{--v038-action:#55f16e;}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.all-in{--v038-action:#ffc44d;}
      body.v014.poker8-v2-sixmax .action-grid .action-slot.queued{
        color:var(--v038-action)!important;border-color:#ff3bd5!important;
        background:linear-gradient(180deg,rgba(55,4,47,.96),rgba(15,2,14,.99))!important;
        box-shadow:0 0 0 1px rgba(255,59,213,.38),0 0 17px rgba(255,59,213,.62),inset 0 0 9px rgba(255,59,213,.16)!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot.queued::after{
        content:"✓"!important;position:absolute!important;top:-6px!important;right:-4px!important;width:20px!important;height:20px!important;
        display:grid!important;place-items:center!important;border-radius:50%!important;background:#ff3bd5!important;color:#fff!important;font-size:12px!important;
        box-shadow:0 0 10px rgba(255,59,213,.72)!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot:disabled{
        opacity:1!important;color:color-mix(in srgb,var(--v038-action) 35%,transparent)!important;
        border-color:color-mix(in srgb,var(--v038-action) 48%,transparent)!important;box-shadow:none!important;cursor:default!important;
      }
      body.v014.poker8-v2-sixmax .v038-actions-unavailable{
        position:absolute;inset:0;display:grid;place-content:center;text-align:center;
        border:1px solid rgba(89,232,184,.24);border-radius:9px;background:linear-gradient(135deg,rgba(3,19,14,.98),rgba(1,5,5,.99));
        color:#c7f9df;box-shadow:inset 0 0 18px rgba(76,255,181,.05);
      }
      body.v014.poker8-v2-sixmax .v038-actions-unavailable strong{font-size:12px;letter-spacing:.06em;color:#7dffd0;}
      body.v014.poker8-v2-sixmax .v038-actions-unavailable span{margin-top:5px;font-size:10px;color:#9db9ad;}
      body.v014.poker8-v2-sixmax .v038-action-label{display:block;font-weight:900;letter-spacing:.035em;line-height:1.05;}
      body.v014.poker8-v2-sixmax .v038-action-amount{display:block;margin-top:2px;font-size:12px;font-weight:900;line-height:1;}
      body.v014.poker8-v2-sixmax .v038-action-amount.v038-amount-pulse{animation:v038AmountPulse 180ms ease-out;}
      body.v014.poker8-v2-sixmax .action-slot.v038-armed::after{
        content:"";position:absolute;left:5px;right:5px;bottom:3px;height:2px;border-radius:9px;background:#ffc44d;
        transform-origin:left center;animation:v038ConfirmDrain var(--v038-arm-ms,3000ms) linear forwards;box-shadow:0 0 7px rgba(255,196,77,.85);
      }
      body.v014.poker8-v2-sixmax .action-slot.v038-armed::before{
        content:attr(data-arm-label);position:absolute;right:6px;bottom:5px;color:#ffc44d;font-size:10px;font-weight:900;letter-spacing:.06em;
      }
      @keyframes v038AmountPulse{50%{transform:scale(1.08);filter:brightness(1.45)}100%{transform:scale(1);filter:none}}
      @keyframes v038ConfirmDrain{to{transform:scaleX(0)}}
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .quick-sizes button,
        body.v014.poker8-v2-sixmax .action-grid .action-slot{transition:none!important;}
        body.v014.poker8-v2-sixmax .v038-action-amount.v038-amount-pulse{animation:none!important;}
        body.v014.poker8-v2-sixmax .action-slot.v038-armed::after{animation:none!important;transform:scaleX(1);}
        body.v014.poker8-v2-sixmax.v038-room-awaiting .player-avatar{animation:none!important;}
        body.v014.poker8-v2-sixmax .felt{transition-duration:80ms!important;}
      }
      body.v014.poker8-v2-sixmax .app-shell{
        height:100dvh!important;min-height:100dvh!important;overflow:hidden!important;
        padding-bottom:var(--p8-bottom-reserve)!important;
        background:linear-gradient(180deg,transparent 0 calc(100% - var(--p8-bottom-reserve)),#010403 calc(100% - var(--p8-bottom-reserve)) 100%)!important;
      }

      @media (max-width:370px){
        /* The two .seat width overrides that used to live here never actually
           applied: v040's per-player-count rule has higher specificity and
           always won regardless of viewport width. Removed as dead weight. */
        body.v014.poker8-v2-sixmax .avatar-wrap{transform:translateX(-50%) scale(.92)!important;transform-origin:center bottom;}
        body.v014.poker8-v2-sixmax .board-cards .card{width:39px!important;height:56px!important;}
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

  let readyCountdownEndsAt = 0;
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
      const action = latest.get(player?.id);
      const family = action === "fold" ? "fold"
        : ["check", "call"].includes(action) ? "passive"
        : ["bet", "raise"].includes(action) ? "aggressive"
        : action === "all_in" ? "all-in" : "";
      if (family) card.classList.add(`v038-action-${family}`);
    });
  }

  function syncTableTurnHud() {
    const host = document.querySelector(".table-frame");
    if (!host) return;
    let timer = host.querySelector(".v038-turn-timer");
    let context = host.querySelector(".v038-turn-context");
    if (!timer) {
      timer = document.createElement("div");
      timer.className = "v038-turn-timer";
      timer.innerHTML = '<b>30</b><small>СЕК</small>';
      host.appendChild(timer);
    }
    if (!context) {
      context = document.createElement("div");
      context.className = "v038-turn-context";
      context.innerHTML = "<span></span>";
      host.appendChild(context);
    }
    const active = Boolean(game && !game.terminal && game.acting_player);
    timer.classList.toggle("visible", active);
    if (!active) {
      context.classList.remove("visible");
      window.clearInterval(turnVisualTicker);
      turnVisualTicker = 0;
      turnVisualToken = "";
      return;
    }
    const token = `${game.hand_id}:${game.street}:${game.acting_player}:${game.history?.length || 0}`;
    if (turnVisualToken !== token) {
      turnVisualToken = token;
      turnVisualStartedAt = Date.now();
    }
    // Whose turn it is already reads off the seat's own glow -- repeating the
    // acting player's name and a turn label here was the same information
    // twice. The bet amount is the only thing this box adds that the glow
    // doesn't show, so there's nothing to show (no empty pill either) without one.
    const actor = game.players?.[game.acting_player];
    const invested = Number(actor?.street_invested || 0);
    context.classList.toggle("visible", invested > 0);
    setText(context.querySelector("span"), invested > 0 ? `ПОСТАВИЛ · ${compactStackLabel(invested)}` : "");
    // The server owns the clock and folds on its own deadline, so a locally
    // restarted countdown would promise time the player does not have.
    const deadline = game.action_deadline ? Date.parse(game.action_deadline) : NaN;
    const left = Number.isNaN(deadline)
      ? Math.max(0, TURN_VISUAL_MS - (Date.now() - turnVisualStartedAt))
      : Math.max(0, deadline - Date.now());
    const seconds = Math.ceil(left / 1000);
    setText(timer.querySelector("b"), String(seconds));
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

  // Returns whether the prompt has anything to say at all.
  function syncOnlineRoomPrompt(prompt) {
    const heroSeat = document.querySelector('.seat[data-visual-seat="0"]');
    const seated = !tableData?.spectator_only;
    // A spectator is already told exactly this by the "Занять место /
    // Наблюдатель" pair in the header, which also says which of the two they
    // are in right now. A card repeating it over the felt only hid the table
    // they came to watch.
    if (!seated) return false;
    // The server can report "seated" a moment before the seat actually shows
    // up here -- seats are still drawn from the current hand's player list,
    // and a fresh seat only joins that list at the next hand boundary. Until
    // then there is nothing to click, so don't tell the viewer to click it.
    if (!heroSeat) {
      prompt.innerHTML = "<strong>МЕСТО ЗАНЯТО</strong><span>Раздача начнётся с вашим участием совсем скоро</span>";
    } else {
      const heroSeatNo = Number(heroSeat.dataset.seat);
      const viewerReady = (tableData?.ready_seats || []).includes(heroSeatNo);
      prompt.innerHTML = viewerReady
        ? "<strong>ЖДЁМ ОСТАЛЬНЫХ</strong><span>Раздача начнётся, как только все будут готовы</span>"
        : "<strong>НАЖМИТЕ НА АВАТАР</strong><span>Отметьте готовность, чтобы начать раздачу</span>";
    }
    prompt.setAttribute("role", "status");
    prompt.removeAttribute("tabindex");
    prompt.setAttribute("aria-live", "polite");
    return true;
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
      // Sitting out a hand that started before this seat joined looks exactly
      // like "room" here too (no cards, no action of theirs) -- the prompt
      // must stay up so they still see "click your avatar" while it runs.
      // Only when there is no hand to look at. While one runs, this card sat
      // over the board and the pot to say something the avatar's own checkmark
      // and pulse now say -- covering the table the player came to watch.
      const hasSomethingToSay = syncOnlineRoomPrompt(prompt);
      prompt?.classList.toggle("visible", hasSomethingToSay && room);
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
    let countdown = felt.querySelector(".v038-ready-countdown");
    if (!countdown) {
      countdown = document.createElement("div");
      countdown.className = "v038-ready-countdown";
      countdown.setAttribute("aria-live", "polite");
      felt.appendChild(countdown);
    }
    return countdown;
  }

  function setReadyCountdown(endsAt) {
    readyCountdownEndsAt = Number(endsAt || 0);
    window.clearInterval(readyCountdownTicker);
    readyCountdownTicker = 0;
    syncAvatarReadyControl();
    const countdown = ensureReadyCountdown();
    countdown?.classList.toggle("visible", Boolean(readyCountdownEndsAt));
    setText(countdown, String(Math.max(1, Math.ceil((readyCountdownEndsAt - Date.now()) / 1000))));
    if (!readyCountdownEndsAt) return;
    readyCountdownTicker = window.setInterval(() => {
      syncAvatarReadyControl();
      setText(countdown, String(Math.max(1, Math.ceil((readyCountdownEndsAt - Date.now()) / 1000))));
      if (Date.now() >= readyCountdownEndsAt) {
        window.clearInterval(readyCountdownTicker);
        readyCountdownTicker = 0;
        countdown?.classList.remove("visible");
      }
    }, 200);
  }

  let referenceActive = false;
  let presetSnapshot = null;
  let armedUntil = 0;
  let armedSource = "";
  let armedFingerprint = "";
  let armedTimer = 0;
  let presetSettleTimer = 0;
  const COMMIT_CONFIRM_MS = 3000;
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

  function clearArmedAction(render = true) {
    window.clearTimeout(armedTimer);
    armedTimer = 0;
    armedUntil = 0;
    armedSource = "";
    armedFingerprint = "";
    if (render) queueSync();
  }

  function viewerIsLeaving() {
    return window.Poker8OnlineTable?.viewerState === "leaving"
      || document.body.classList.contains("p8-leaving");
  }

  function armedFingerprintOf(source) {
    const amount = Number(document.getElementById("amount")?.value || 0);
    return [game?.hand_id, game?.street, game?.acting_player, game?.history?.length || 0, source, source === "aggressive" ? amount : ""].join(":");
  }

  function fireArmedCommit(source, amount) {
    const fingerprint = armedFingerprint;
    clearArmedAction(false);
    if (!game || game.terminal || !isLocalHumanTurn()) return;
    // The spot has to be the one that was armed: a new street, a new actor or
    // a changed amount all mean this is no longer the bet they asked for.
    if (fingerprint !== armedFingerprintOf(source)) return queueSync();
    const legal = game.human_legal_actions || [];
    clearPendingAction(false);
    if (source === "aggressive") {
      sendAction(legal.includes("raise") ? "raise" : "bet", amount);
    } else if (source === "fold") {
      sendAction("fold", 0);
    } else {
      sendAction("all_in", 0);
    }
    queueSync();
  }

  function confirmCommit(source, localTurn, amount, legal) {
    // Off turn there is no clock to run against: it stays a pre-action.
    if (!localTurn) {
      clearArmedAction(false);
      togglePendingAction(source);
      renderMobileSelectedCard();
      queueSync();
      return;
    }
    // Already on the way out: the seat is going and the server folds the hand
    // itself, so a beat to reconsider is a beat wasted. Send it and be done.
    if (viewerIsLeaving()) {
      clearArmedAction(false);
      clearPendingAction(false);
      return sendAction(source === "fold" ? "fold" : "all_in", 0);
    }
    // The two irreversible presses -- the whole stack, and the hand itself --
    // get a beat to take back. The first press arms it and a bar drains across
    // the button; it fires on its own, and pressing again inside the window is
    // how you cancel, not how you confirm.
    const fingerprint = armedFingerprintOf(source);
    if (armedSource === source && armedFingerprint === fingerprint) {
      clearArmedAction();
      return;
    }
    clearArmedAction(false);
    // Never let the bar be the reason a turn times out: if the server's own
    // deadline lands first, commit there instead, half a second early so the
    // command has time to reach it.
    const deadline = game?.action_deadline ? Date.parse(game.action_deadline) : NaN;
    const armFor = Number.isFinite(deadline)
      ? Math.max(400, Math.min(COMMIT_CONFIRM_MS, deadline - Date.now() - 500))
      : COMMIT_CONFIRM_MS;
    armedSource = source;
    armedFingerprint = fingerprint;
    armedUntil = Date.now() + armFor;
    armedTimer = window.setTimeout(() => fireArmedCommit(source, amount), armFor);
    queueSync();
  }

  function ensureHudSummary() {
    const panel = document.querySelector(".action-panel");
    if (!panel) return;
    let summary = panel.querySelector(".v038-hud-summary");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "v038-hud-summary";
      summary.innerHTML = '<span>УРАВНЯТЬ<b data-v038-call>0.00</b></span><span>БАНК<b data-v038-pot>0.00</b></span><span>СТАВКА<b data-v038-bet>0.00</b></span>';
      panel.prepend(summary);
    }
    const call = typeof estimatedLocalToCall === "function" ? formatBB(estimatedLocalToCall()) : "0.00 ББ";
    const pot = document.getElementById("pot")?.textContent?.trim() || "0.00 ББ";
    const amount = document.getElementById("amount")?.value || "0.00";
    setText(summary.querySelector("[data-v038-call]"), stripHudUnit(call));
    setText(summary.querySelector("[data-v038-pot]"), stripHudUnit(pot));
    setText(summary.querySelector("[data-v038-bet]"), stripHudUnit(amount));
  }

  function configureReferenceActions() {
    const grid = document.getElementById("actionButtons");
    const current = [...(grid?.querySelectorAll("[data-v038-reference-action]") || [])];
    if (!grid) return;
    const alive = localPlayerAlive();
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
    const leftKey = localTurn ? (legal.includes("check") ? "check" : "fold") : (toCall > 0 ? "fold" : "check");
    const atMax = Math.abs(amount - Number(bounds.max || 0)) < 1e-9;
    const aggressiveLabel = Number(game?.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "RAISE" : "BET";
    if (armedSource && (armedUntil <= Date.now() || armedFingerprint !== armedFingerprintOf(armedSource))) {
      clearArmedAction(false);
    }
    const defs = [
      { key:"call", label:"CALL", amount:stripHudUnit(formatBB(toCall)), cls:"call" },
      { key:"all_in", label:"ALL-IN", amount:stripHudUnit(formatBB(allInTotal)), cls:"all-in", allIn:true },
      { key:leftKey, label:leftKey === "check" ? "CHECK" : "FOLD", amount:"", cls:leftKey },
      { key:"aggressive", label:atMax ? "ALL-IN" : aggressiveLabel, amount:stripHudUnit(formatBB(atMax ? allInTotal : amount)), cls:atMax ? "all-in" : "raise", allIn:atMax },
    ];
    if (current.length !== 4) {
      grid.innerHTML = "";
      defs.forEach(() => grid.appendChild(document.createElement("button")));
    }
    grid.dataset.v038ReferenceActions = "1";
    [...grid.children].forEach((button, index) => {
      try {
        const def = defs[index];
        const slot = ["call", "all_in", "left", "aggressive"][index];
        button.type = "button";
        button.dataset.actionKey = def.key;
        button.dataset.v038Slot = slot;
        button.dataset.v038ReferenceAction = "1";
        button.className = `action-slot ${def.cls}`;
        button.classList.toggle("queued", pendingAction?.kind === def.key);
        const armed = armedSource === def.key && (Boolean(def.allIn) || def.key === "fold");
        button.classList.toggle("v038-armed", armed);
        if (armed) {
          // Set once, on the render that arms it. Rewriting the duration on
          // every later render restarts the animation, so the bar would snap
          // back to full width each time a snapshot arrived.
          if (!button.dataset.armLabel) {
            const left = Math.max(0, armedUntil - Date.now());
            button.style.setProperty("--v038-arm-ms", `${left}ms`);
            button.dataset.armLabel = `${Math.max(1, Math.round(left / 1000))} СЕК`;
          }
        } else if (button.dataset.armLabel) {
          button.style.removeProperty("--v038-arm-ms");
          delete button.dataset.armLabel;
        }
        if (def.allIn) button.dataset.v038AllInTrigger = "1";
        else delete button.dataset.v038AllInTrigger;
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
          value.classList.remove("v038-amount-pulse");
          void value.offsetWidth;
          value.classList.add("v038-amount-pulse");
        }
        button.setAttribute("aria-label", `${def.label}${def.amount ? ` ${def.amount}` : ""}`);
        let enabled = Boolean(game && !game.terminal && alive && !window.Poker8Transport?.isActionPending?.());
        if (localTurn) {
          if (def.key === "check") enabled = enabled && legal.includes("check");
          else if (def.key === "fold") enabled = enabled && legal.includes("fold");
          else if (def.key === "call") enabled = enabled && legal.includes("call");
          else if (def.key === "all_in") enabled = enabled && legal.includes("all_in");
          else if (def.allIn) enabled = enabled && (legal.includes("bet") || legal.includes("raise"));
          else enabled = enabled && (legal.includes("bet") || legal.includes("raise"));
        } else {
          // While another player acts, every enabled control is an explicit
          // pre-action. It is revalidated against the snapshot at execution.
          if (def.key === "call") enabled = enabled && toCall > 0;
          button.setAttribute("aria-description", "Предвыбор: действие будет перепроверено на вашем ходе");
        }
        button.disabled = !enabled;
        button.onclick = () => {
          if (!game || game.terminal || !localPlayerAlive() || window.Poker8Transport?.isActionPending?.()) return;
          const liveTurn = isLocalHumanTurn();
          const liveLegal = game.human_legal_actions || [];
          const liveToCall = estimatedLocalToCall();
          const liveAmount = Number(document.getElementById("amount")?.value || amountBounds().value || 0);
          const liveKey = slot === "left"
            ? (liveTurn ? (liveLegal.includes("check") ? "check" : "fold") : (liveToCall > 0 ? "fold" : "check"))
            : slot === "aggressive" ? "aggressive" : slot;
          // Не исполнять команду от button, если между её отрисовкой и касанием пришёл новый snapshot.
          if (button.dataset.actionKey !== liveKey) {
            queueSync();
            return;
          }
          const liveAllIn = slot === "all_in" || (slot === "aggressive" && Math.abs(liveAmount - Number(amountBounds().max || 0)) < 1e-9);
          if (liveAllIn) return confirmCommit(slot === "aggressive" ? "aggressive" : "all_in", liveTurn, liveAmount, liveLegal);
          // Folding is as final as shoving, so it arms the same way. Checking
          // is not -- the left slot is one or the other depending on the spot.
          if (liveKey === "fold") return confirmCommit("fold", liveTurn, 0, liveLegal);
          if (!liveTurn) {
            togglePendingAction(liveKey);
            renderMobileSelectedCard();
            queueSync();
            return;
          }
          clearPendingAction(false);
          if (liveKey === "check") return sendAction("check", 0);
          if (liveKey === "fold") return sendAction("fold", 0);
          if (liveKey === "call") return sendAction("call", 0);
          return sendAction(liveLegal.includes("raise") ? "raise" : "bet", liveAmount);
        };
      } catch (error) {
        console.error("[v038] configureReferenceActions button failed", error);
      }
    });
  }

  function teardownFinalReference() {
    if (!referenceActive) return;
    referenceActive = false;
    clearArmedAction(false);
    clearPresetSelection();
    window.clearTimeout(presetSettleTimer);
    presetSettleTimer = 0;
    window.clearInterval(turnVisualTicker);
    turnVisualTicker = 0;
    turnVisualToken = "";
    cancelRoomReset();
    document.body.classList.remove("v038-room-awaiting");
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
    runSyncStep(ensurePresetButtons);
    runSyncStep(ensureHudSummary);
    runSyncStep(syncSeatStackLabels);
    runSyncStep(syncTableNumberLabels);
    runSyncStep(syncAvatarReadyControl);
    runSyncStep(syncAllSeatReadyMarks);
    runSyncStep(syncSeatActionStates);
    runSyncStep(ensureReadyCountdown);
    runSyncStep(syncTableTurnHud);
    runSyncStep(syncCompletedHandReset);
    runSyncStep(configureReferenceActions);
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
    if (buttons) new MutationObserver(queueSync).observe(buttons, { childList:true });
    const sizing = document.getElementById("sizingWrap");
    if (sizing && !sizing.dataset.v038InputSync) {
      sizing.dataset.v038InputSync = "1";
      sizing.addEventListener("input", event => {
        if (event.target?.matches?.("#amountSlider")) scheduleSettledPreset();
        else clearPresetSelection();
        clearArmedAction(false);
        queueSync();
      });
    }
    if (!document.body.dataset.v038ClickSync) {
      document.body.dataset.v038ClickSync = "1";
      document.addEventListener("click", event => {
        if (event.target?.closest?.("#amountMinus,#amountPlus")) clearPresetSelection();
        if (armedSource && !event.target?.closest?.("[data-v038-all-in-trigger]")) clearArmedAction();
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
