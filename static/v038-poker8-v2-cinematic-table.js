(() => {
  "use strict";

  const MOBILE = "(max-width: 780px)";
  const isMobileV2 = () => window.matchMedia?.(MOBILE)?.matches
    && document.body.classList.contains("poker8-v2-sixmax");

  const style = document.createElement("style");
  style.id = "v038-poker8-v2-cinematic-table-style";
  style.textContent = `
    @media (max-width:780px){
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
        --seat-4-x:93%!important;--seat-4-y:22%!important;
        --seat-5-x:93%!important;--seat-5-y:58%!important;
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
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:93%!important;top:22%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:93%!important;top:58%!important;}

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

      body.v014.poker8-v2-sixmax .seat{width:104px!important;height:116px!important;min-height:0!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:132px!important;height:132px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{--seat-accent:195;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{--seat-accent:190;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{--seat-accent:282;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{--seat-accent:142;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{--seat-accent:34;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{--seat-accent:300;}

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
        width:74px!important;height:74px!important;margin:0!important;
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
      body.v014.poker8-v2-sixmax.v038-room-awaiting .avatar-wrap::before,
      body.v014.poker8-v2-sixmax.v038-room-awaiting .avatar-wrap::after,
      body.v014.poker8-v2-sixmax.v038-room-resetting .avatar-wrap::before,
      body.v014.poker8-v2-sixmax.v038-room-resetting .avatar-wrap::after,
      body.v014.poker8-v2-sixmax.v038-hand-complete .avatar-wrap::before,
      body.v014.poker8-v2-sixmax.v038-hand-complete .avatar-wrap::after{opacity:0!important;}

      body.v014.poker8-v2-sixmax .player-avatar{
        position:relative!important;
        width:74px!important;height:74px!important;
        transition:border-color 220ms ease,box-shadow 220ms ease,filter 220ms ease!important;
        border:2px solid hsla(var(--seat-accent),100%,70%,.88)!important;
        background-image:var(--profile-avatar-image,radial-gradient(circle at 50% 32%,hsla(var(--seat-accent),62%,46%,.45),transparent 31%),radial-gradient(circle at 50% 78%,#07110e 0 42%,#010303 70%))!important;
        background-position:center!important;
        background-size:cover!important;
        color:#f5fff9!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 16px hsla(var(--seat-accent),96%,58%,.46),inset 0 -10px 18px rgba(0,0,0,.50)!important;
        font-size:13px!important;
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
        position:absolute!important;z-index:6;left:50%!important;top:70px!important;transform:translateX(-50%)!important;
        width:96px!important;min-height:38px!important;padding:6px 7px 5px!important;border-radius:9px!important;
        transition:border-color 220ms ease,box-shadow 220ms ease,filter 220ms ease!important;
        border:1px solid hsla(var(--seat-accent),90%,60%,.72)!important;background:linear-gradient(180deg,rgba(9,8,10,.98),rgba(1,3,4,.995))!important;
        box-shadow:0 0 12px hsla(var(--seat-accent),92%,55%,.24),0 7px 14px rgba(0,0,0,.62)!important;text-align:center!important;
      }
      body.v014.poker8-v2-sixmax .seat-topline{display:block!important;}
      body.v014.poker8-v2-sixmax .seat-name{max-width:68px!important;font-size:9px!important;line-height:1!important;}
      body.v014.poker8-v2-sixmax .seat-stack{margin-top:3px!important;font-size:12px!important;line-height:1!important;color:var(--seat-neon)!important;}
      body.v014.poker8-v2-sixmax .seat-name,
      body.v014.poker8-v2-sixmax .seat-stack{margin-inline:auto!important;}
      body.v014.poker8-v2-sixmax .bot-level{display:none!important;}
      body.v014.poker8-v2-sixmax .position-chip{display:none!important;font-size:6px!important;padding:1px 3px!important;}
      body.v014.poker8-v2-sixmax .seat-meta{margin-top:3px!important;}
      body.v014.poker8-v2-sixmax .seat-card > .v024-ready-badge{display:none!important;}
      body.v014.poker8-v2-sixmax .player-status:is(.status-fold,.status-turn,.status-thinking){display:none!important;}
      body.v014.poker8-v2-sixmax .v028-center-ready{display:none!important;}
      body.v014.poker8-v2-sixmax .deck-anchor{display:none!important;}

      body.v014.poker8-v2-sixmax .v038-ready-countdown{
        position:absolute;z-index:74;left:50%;top:calc(55% - 66px);transform:translate(-50%,-50%);
        display:none;place-items:center;width:62px;height:62px;border-radius:50%;
        border:2px solid #72ffb5;background:rgba(1,20,13,.88);color:#e8fff3;
        box-shadow:0 0 0 3px rgba(0,5,3,.72),0 0 22px rgba(72,255,169,.58),inset 0 0 18px rgba(70,255,170,.14);
        font-size:29px;font-weight:950;text-shadow:0 0 10px rgba(98,255,190,.86);pointer-events:none;
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
      body.v014.poker8-v2-sixmax .v038-turn-timer b{position:relative;color:#fff;font-size:18px;line-height:1;text-shadow:0 0 7px #ff38c7;}
      body.v014.poker8-v2-sixmax .v038-turn-timer small{position:absolute;bottom:-11px;color:#ff87df;font-size:6px;font-weight:900;letter-spacing:.08em;}
      body.v014.poker8-v2-sixmax .v038-turn-context.visible{display:block;}
      body.v014.poker8-v2-sixmax .v038-turn-context{
        left:calc(75% + 20.5px);transform:translateX(-50%);width:max-content;min-width:82px;max-width:116px;padding:6px 8px;border:1px solid #2de8df;border-radius:9px;
        background:rgba(2,19,18,.92);color:#dffffc;text-align:center;box-shadow:0 0 14px rgba(45,232,223,.38);
      }
      body.v014.poker8-v2-sixmax .v038-turn-context strong{display:block;color:#55fff2;font-size:11px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
      body.v014.poker8-v2-sixmax .v038-turn-context span{display:block;margin-top:3px;color:#ecfffd;font-size:10px;font-weight:850;line-height:1;}
      body.v014.poker8-v2-sixmax .v038-turn-context span:empty{display:none;}

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
        font-size:30px;font-weight:950;line-height:1;text-shadow:0 0 10px rgba(104,255,190,.95);pointer-events:none;
      }
      body.v014.poker8-v2-sixmax.v028-prehand-center-ready .avatar-wrap.v038-viewer-ready .v038-ready-mark{display:grid;}
      body.v014.poker8-v2-sixmax .v038-ready-mark small{
        position:absolute;right:-7px;bottom:-5px;display:grid;place-items:center;width:25px;height:25px;border-radius:50%;
        border:1px solid #71ffc1;background:#031b13;color:#fff;font-size:12px;font-weight:950;
        box-shadow:0 0 12px rgba(75,255,181,.70);
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-card{
        min-height:0!important;padding:0!important;border:0!important;box-shadow:none!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap{top:9px!important;width:82px!important;height:82px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{width:82px!important;height:82px!important;border-color:#35bfff!important;font-size:14px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-identity{top:84px!important;width:122px!important;min-height:42px!important;z-index:12!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-name{font-size:10px!important;max-width:92px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{font-size:13px!important;color:#35c6ff!important;}

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
      body.v014.poker8-v2-sixmax .seat-card.v032-folded.v038-action-fold{opacity:.48!important;filter:none!important;}

      body.v014.poker8-v2-sixmax .v038-room-prompt{
        position:absolute;z-index:72;left:50%;top:55%;transform:translate(-50%,-50%);display:none;width:max-content;max-width:78%;
        padding:10px 14px;border:1px solid rgba(61,235,190,.58);border-radius:12px;background:rgba(1,18,13,.88);text-align:center;
        box-shadow:0 0 18px rgba(46,239,186,.22);pointer-events:auto;cursor:pointer;
      }
      body.v014.poker8-v2-sixmax .v038-room-prompt.visible{display:block;}
      body.v014.poker8-v2-sixmax .v038-room-prompt strong{display:block;color:#7dffd0;font-size:13px;line-height:1.05;letter-spacing:.06em;}
      body.v014.poker8-v2-sixmax .v038-room-prompt span{display:block;margin-top:5px;color:#dfffee;font-size:9px;line-height:1.1;}
      body.v014.poker8-v2-sixmax.v038-room-awaiting .seat[data-visual-seat="0"] .avatar-wrap:not(.v038-viewer-ready) .player-avatar{
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
      body.v014.poker8-v2-sixmax .viewer-seat .player-cards .card-rank{left:5px!important;top:3px!important;font-size:13px!important;font-weight:950!important;}
      body.v014.poker8-v2-sixmax .viewer-seat .player-cards .card-suit{font-size:24px!important;filter:drop-shadow(0 0 4px currentColor)!important;}
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
      body.v014.poker8-v2-sixmax .pot-total-label{font-size:8px!important;letter-spacing:.08em!important;}
      body.v014.poker8-v2-sixmax .pot-total strong{font-size:20px!important;line-height:1!important;}

      body.v014.poker8-v2-sixmax .pot-chips .chip-cluster.pot-cluster{height:52px!important;min-width:124px!important;filter:drop-shadow(0 8px 6px rgba(0,0,0,.54))!important;}
      body.v014.poker8-v2-sixmax .pot-chips .chip-column.pot-stack{width:22px!important;height:48px!important;}
      body.v014.poker8-v2-sixmax .pot-chips .poker-chip{
        width:22px!important;height:9px!important;border-width:1px!important;
        transform:translateX(-50%) translateY(calc(var(--i) * -3.6px))!important;
        box-shadow:0 2px 3px rgba(0,0,0,.58),inset 0 2px 0 rgba(255,255,255,.28),inset 0 -3px 0 rgba(0,0,0,.40)!important;
      }
      body.v014.poker8-v2-sixmax .pot-chips .poker-chip::before{left:3px!important;right:3px!important;height:4px!important;}
      body.v014.poker8-v2-sixmax .pot-chips .chip-column:nth-child(3n+2) .poker-chip{filter:hue-rotate(92deg) saturate(1.45)!important;}
      body.v014.poker8-v2-sixmax .pot-chips .chip-column:nth-child(3n) .poker-chip{filter:hue-rotate(214deg) saturate(1.35)!important;}

      body.v014.poker8-v2-sixmax .bet-marker .chip-cluster.compact{transform:scale(.82)!important;transform-origin:center bottom!important;}
      body.v014.poker8-v2-sixmax .bet-marker span{
        margin-top:-4px!important;padding:2px 6px!important;border:0!important;background:rgba(1,7,6,.84)!important;
        color:#ecfff5!important;font-size:11px!important;font-weight:900!important;line-height:1!important;
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
        box-shadow:0 0 18px rgba(85,255,242,.66)!important;
      }
      @keyframes v038ActiveTurnPulse{50%{filter:brightness(1.16);box-shadow:0 0 0 4px rgba(1,5,5,.92),0 0 34px rgba(85,255,242,.94),inset 0 -10px 18px rgba(0,0,0,.50)}}
      @media (prefers-reduced-motion:reduce){body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn :is(.player-avatar,.seat-identity){animation:none!important;}}
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-folded{
        opacity:.28!important;filter:saturate(.18) brightness(.68)!important;box-shadow:none!important;
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
        border-bottom:1px solid rgba(95,132,121,.18);font-size:6px;letter-spacing:.10em;color:#8ca59c;
      }
      body.v014.poker8-v2-sixmax .v038-hud-summary b{display:block;margin-top:1px;font-size:13px;line-height:1;color:#39bfff;letter-spacing:0;}
      body.v014.poker8-v2-sixmax .v038-hud-summary span:nth-child(2) b{color:#59e77c;}
      body.v014.poker8-v2-sixmax .v038-hud-summary span:nth-child(3) b{color:#ff9e45;}
      body.v014.poker8-v2-sixmax .sizing-wrap{display:contents!important;}
      body.v014.poker8-v2-sixmax .sizing-wrap > label{display:none!important;}
      body.v014.poker8-v2-sixmax .quick-sizes{
        position:absolute!important;left:8px;right:8px;top:35px!important;height:39px;
        display:grid!important;grid-template-columns:repeat(5,1fr)!important;gap:4px!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button{
        min-height:39px!important;height:39px!important;padding:3px 2px!important;border-radius:6px!important;font-size:8px!important;
        color:#fff!important;text-shadow:0 0 5px rgba(255,255,255,.48)!important;
        transition:color 180ms ease,border-color 180ms ease,box-shadow 180ms ease,background 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button strong{display:block;font-size:9px!important;line-height:1!important;color:#fff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button small{display:block;margin-top:3px;font-size:8px!important;line-height:1!important;color:#f4f7ff!important;}
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
        display:grid!important;place-items:center!important;border-radius:50%!important;background:#ff3bd5!important;color:#fff!important;font-size:11px!important;
        box-shadow:0 0 10px rgba(255,59,213,.72)!important;
      }
      body.v014.poker8-v2-sixmax .action-grid .action-slot:disabled{
        opacity:1!important;color:color-mix(in srgb,var(--v038-action) 35%,transparent)!important;
        border-color:color-mix(in srgb,var(--v038-action) 48%,transparent)!important;box-shadow:none!important;cursor:default!important;
      }
      body.v014.poker8-v2-sixmax .v038-action-label{display:block;font-weight:900;letter-spacing:.035em;line-height:1.05;}
      body.v014.poker8-v2-sixmax .v038-action-amount{display:block;margin-top:2px;font-size:11px;font-weight:900;line-height:1;}
      body.v014.poker8-v2-sixmax .v038-action-amount.v038-amount-pulse{animation:v038AmountPulse 180ms ease-out;}
      @keyframes v038AmountPulse{50%{transform:scale(1.08);filter:brightness(1.45)}100%{transform:scale(1);filter:none}}
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
        background:linear-gradient(180deg,transparent 0 calc(100% - var(--p8-bottom-reserve)),#010403 calc(100% - var(--p8-bottom-reserve)) 100%)!important;
      }

      @media (max-width:370px){
        body.v014.poker8-v2-sixmax .seat{width:90px!important;}
        body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:120px!important;}
        body.v014.poker8-v2-sixmax .avatar-wrap{transform:translateX(-50%) scale(.92)!important;transform-origin:center bottom;}
        body.v014.poker8-v2-sixmax .board-cards .card{width:39px!important;height:56px!important;}
      }

      /* Portrait-first edge-action composition. Shared pixel offsets keep the
         five opponent centers on one circle instead of a percentage ellipse. */
      body.v014.poker8-v2-sixmax{
        --p8-header-h:52px;
        --p8-arc-radius:calc(46vw);
        --p8-arc-diagonal:calc(var(--p8-arc-radius) * .70710678);
        --p8-arc-top:38px;
        --p8-arc-center-y:calc(var(--p8-arc-top) + var(--p8-arc-radius));
        --p8-seat-angles:"180 135 90 45 0";
        --table-stage-h:calc(100dvh - var(--p8-header-h))!important;
      }
      body.v014.poker8-v2-sixmax .mobile-game-header{
        position:fixed!important;z-index:120;inset:0 0 auto!important;height:var(--p8-header-h)!important;
        display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:8px!important;
        padding:2px 8px!important;background:linear-gradient(180deg,rgba(2,12,8,.98),rgba(2,8,6,.92))!important;
        border-bottom:1px solid rgba(70,255,184,.18)!important;box-shadow:0 8px 22px rgba(0,0,0,.34)!important;
      }
      body.v014.poker8-v2-sixmax :is(.mobile-menu-button,.mobile-chat-button,#mobileHelpButton){
        width:48px!important;height:48px!important;min-width:48px!important;min-height:48px!important;border-radius:14px!important;
      }
      body.v014.poker8-v2-sixmax .mobile-chat-button{margin-left:auto!important;}
      body.v014.poker8-v2-sixmax #mobileHelpButton{
        display:grid;place-items:center;padding:0;border:1px solid rgba(62,226,190,.62);background:rgba(3,18,13,.88);color:#e2fff4;font-size:20px;font-weight:900;
        box-shadow:0 0 13px rgba(45,233,176,.14),inset 0 0 11px rgba(64,255,196,.05);
      }
      body.v014.poker8-v2-sixmax #mobileConnectionDot{
        display:block;width:8px;height:8px;flex:0 0 8px;border-radius:50%;background:#55f3a8;box-shadow:0 0 9px rgba(85,243,168,.92);
      }
      body.v014.poker8-v2-sixmax #connectionStatus{display:none!important;}
      body.v014.poker8-v2-sixmax .app-shell{
        height:100dvh!important;min-height:100dvh!important;padding:var(--p8-header-h) 0 0!important;overflow:hidden!important;background:#030604!important;
      }
      body.v014.poker8-v2-sixmax .table-frame{
        height:calc(100dvh - var(--p8-header-h))!important;min-height:0!important;padding:0 5px!important;overflow:visible!important;
        background-size:100vw 100%!important;background-position:center!important;
      }
      body.v014.poker8-v2-sixmax .felt{
        height:100%!important;transform:none!important;transform-style:flat!important;
      }
      body.v014.poker8-v2-sixmax .seat{width:90px!important;height:104px!important;min-height:0!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{left:50%!important;top:calc(100% - 86px)!important;bottom:auto!important;width:116px!important;height:132px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:calc(50% - var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:calc(50% - var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{left:50%!important;top:var(--p8-arc-top)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:calc(50% + var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:calc(50% + var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
      body.v014.poker8-v2-sixmax .avatar-wrap{
        top:0!important;width:44px!important;height:44px!important;transform:translateX(-50%)!important;transform-origin:center!important;
      }
      body.v014.poker8-v2-sixmax .player-avatar{width:44px!important;height:44px!important;font-size:12px!important;}
      body.v014.poker8-v2-sixmax .seat-identity{
        top:40px!important;width:90px!important;min-height:44px!important;padding:5px 6px 4px!important;border-radius:9px!important;
      }
      body.v014.poker8-v2-sixmax .seat-name{max-width:78px!important;font-size:12px!important;line-height:1.05!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;}
      body.v014.poker8-v2-sixmax .seat-stack{font-size:16px!important;line-height:1!important;white-space:nowrap!important;}
      body.v014.poker8-v2-sixmax .player-cards{top:-31px!important;}
      body.v014.poker8-v2-sixmax .player-cards .card{width:32px!important;height:44px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap{top:9px!important;width:48px!important;height:48px!important;transform:translateX(-50%)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{width:48px!important;height:48px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-identity{top:54px!important;width:108px!important;min-height:47px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-name{max-width:96px!important;font-size:13px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{font-size:18px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards{top:-52px!important;gap:4px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card{width:50px!important;height:70px!important;}
      body.v014.poker8-v2-sixmax .board-cards .card{width:46px!important;height:64px!important;}
      body.v014.poker8-v2-sixmax .pot-total{top:41%!important;}
      body.v014.poker8-v2-sixmax .pot-chips{top:45%!important;}
      body.v014.poker8-v2-sixmax .board-cards{top:49%!important;}
      body.v014.poker8-v2-sixmax .sidebar,
      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        position:fixed!important;z-index:80;inset:var(--p8-header-h) 0 0!important;width:auto!important;height:auto!important;min-height:0!important;
        padding:0!important;margin:0!important;overflow:visible!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;pointer-events:none!important;
      }
      body.v014.poker8-v2-sixmax .action-panel :is(button,input){pointer-events:auto!important;}
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
        border:1px solid rgba(77,255,188,.42)!important;border-radius:18px!important;background:rgba(2,10,7,.96)!important;box-shadow:0 0 28px rgba(33,242,164,.22)!important;
      }
      body.v014.poker8-v2-sixmax.v038-sizing-open .sizing-wrap{display:block!important;}
      body.v014.poker8-v2-sixmax.v038-sizing-open .action-grid .action-slot{visibility:hidden!important;}
      body.v014.poker8-v2-sixmax .mobile-sizing-head{display:flex;align-items:center;justify-content:center;min-height:44px;margin-bottom:7px;position:relative;}
      body.v014.poker8-v2-sixmax #mobileSizingAmount{color:#fff;font-size:24px;font-weight:950;line-height:1;text-shadow:0 0 12px rgba(67,236,185,.46);}
      body.v014.poker8-v2-sixmax #mobileSizingCancel{
        position:absolute;right:0;top:0;width:44px;height:44px;border:1px solid rgba(139,184,164,.35);border-radius:12px;background:#07130f;color:#cbddd5;font-size:24px;
      }
      body.v014.poker8-v2-sixmax .quick-sizes{
        position:static!important;height:auto!important;display:grid!important;grid-template-columns:repeat(5,minmax(48px,1fr))!important;gap:5px!important;margin:0!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button{min-height:48px!important;height:48px!important;padding:4px 2px!important;font-size:10px!important;}
      body.v014.poker8-v2-sixmax .bet-slider-row{position:static!important;height:32px!important;margin:7px 0 5px!important;display:block!important;}
      body.v014.poker8-v2-sixmax #amountSlider{height:32px!important;}
      body.v014.poker8-v2-sixmax #mobileSizingConfirm{
        width:100%!important;min-height:50px!important;border:1px solid rgba(75,255,181,.72);border-radius:13px;background:linear-gradient(180deg,rgba(15,72,48,.96),rgba(4,32,21,.98));color:#eafff4;font-size:12px;font-weight:950;letter-spacing:.04em;box-shadow:0 0 17px rgba(62,244,170,.18);
      }
      body.v014.poker8-v2-sixmax .action-slot[data-action-key="aggressive"]{touch-action:none!important;}
      body.v014.poker8-v2-sixmax #mobileBetRail{
        display:block;position:fixed;z-index:99;top:calc(var(--p8-header-h) + 10px);right:0;bottom:calc(72px + env(safe-area-inset-bottom));width:76px;
        border:1px solid rgba(75,255,181,.55);border-right:0;border-radius:18px 0 0 18px;background:linear-gradient(180deg,rgba(10,55,38,.94),rgba(2,13,9,.96));
        box-shadow:0 0 24px rgba(41,238,165,.22);pointer-events:none;
      }
      body.v014.poker8-v2-sixmax #mobileBetRail::before{
        content:"";position:absolute;top:22px;bottom:22px;right:18px;width:3px;border-radius:3px;background:linear-gradient(180deg,#ff9f43 0 8%,#45f0ae 28% 100%);opacity:.8;
      }
      body.v014.poker8-v2-sixmax #mobileBetRailAmount{
        position:fixed;z-index:100;right:12px;top:clamp(calc(var(--p8-header-h) + 12px),calc(var(--v038-rail-y, 50vh) - 25px),calc(100vh - 128px));
        min-width:104px;min-height:50px;padding:0 12px;display:grid;place-items:center;border-radius:14px 0 0 14px;background:#061b12;color:#fff;font-size:20px;font-weight:950;white-space:nowrap;
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
      body.v014.poker8-v2-sixmax .avatar-wrap>.v038-turn-timer{
        position:absolute;z-index:14;left:50%;top:50%;bottom:auto;width:calc(100% + 10px);height:calc(100% + 10px);transform:translate(-50%,-50%);display:grid;place-items:center;border-radius:50%;
        background:conic-gradient(#57ffd0 var(--timer-progress,100%),rgba(87,255,208,.10) 0);filter:drop-shadow(0 0 8px rgba(87,255,208,.72));pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .avatar-wrap>.v038-turn-timer::before{content:"";position:absolute;inset:3px;border-radius:50%;background:rgba(2,10,7,.18);border:1px solid rgba(87,255,208,.68);}
      body.v014.poker8-v2-sixmax .avatar-wrap>.v038-turn-timer b{
        position:absolute;left:calc(100% - 4px);top:50%;min-width:29px;padding:4px 5px;transform:translateY(-50%);border-radius:8px;background:#061710;color:#fff;font-size:13px;line-height:1;text-align:center;text-shadow:0 0 7px #55ffe0;box-shadow:0 0 10px rgba(85,255,224,.35);
      }
      body.v014.poker8-v2-sixmax .avatar-wrap>.v038-turn-timer small{display:none;}
      body.v014.poker8-v2-sixmax #mobileConnectionDot[data-state="connecting"]{background:#8aa99b;box-shadow:0 0 7px rgba(138,169,155,.58);}
      body.v014.poker8-v2-sixmax #mobileConnectionDot[data-state="reconnecting"]{background:#ffbd55;box-shadow:0 0 9px rgba(255,189,85,.88);}
      body.v014.poker8-v2-sixmax #mobileConnectionDot[data-state="error"]{background:#ff554f;box-shadow:0 0 9px rgba(255,85,79,.88);}
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
      document.getElementById("mobileMenuButton")?.after(dot);
    }
    if (!document.getElementById("mobileHelpButton")) {
      const help = document.createElement("button");
      help.id = "mobileHelpButton";
      help.type = "button";
      help.setAttribute("aria-label", "Помощь");
      help.textContent = "?";
      header.appendChild(help);
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
  let readyCountdownTicker = 0;
  let viewerReadySnapshot = false;

  function syncAvatarReadyControl() {
    const wrap = document.querySelector('.seat[data-visual-seat="0"] .avatar-wrap');
    if (!wrap) return;
    let mark = wrap.querySelector(".v038-ready-mark");
    if (!mark) {
      mark = document.createElement("span");
      mark.className = "v038-ready-mark";
      mark.innerHTML = '<b>✓</b>';
      wrap.appendChild(mark);
    }
    const ready = viewerReadySnapshot;
    const preHand = !game;
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
    document.querySelectorAll(".seat-card").forEach(card => {
      if (card.closest('.seat[data-visual-seat="0"]')) return;
      const wrap = card.querySelector(".avatar-wrap");
      if (!wrap) return;
      if (game) {
        wrap.classList.remove("v038-viewer-ready");
        wrap.querySelector(".v038-seat-ready-check")?.remove();
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
    const token = `${game.hand_id}:${game.street}:${game.acting_player}:${game.history?.length || 0}`;
    if (turnVisualToken !== token) {
      turnVisualToken = token;
      turnVisualStartedAt = Date.now();
    }
    const left = Math.max(0, TURN_VISUAL_MS - (Date.now() - turnVisualStartedAt));
    const seconds = Math.ceil(left / 1000);
    setText(timer.querySelector("b"), String(seconds));
    timer.style.setProperty("--timer-progress", `${left / TURN_VISUAL_MS * 100}%`);
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

  function syncOnlineRoomPrompt(prompt) {
    const seated = !tableData?.spectator_only;
    prompt.innerHTML = seated
      ? "<strong>НОВАЯ РАЗДАЧА СКОРО</strong><span>Стол запускается автоматически</span>"
      : "<strong>ВЫ НАБЛЮДАЕТЕ</strong><span>Откройте лобби, чтобы занять место</span>";
    prompt.setAttribute("role", "status");
    prompt.removeAttribute("tabindex");
    prompt.setAttribute("aria-live", "polite");
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
      syncOnlineRoomPrompt(prompt);
      prompt?.classList.toggle("visible", room);
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
  let sizingMode = null;
  let betGesture = null;
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

  function mobileActionDefinitions({ localTurn, legal, toCall, amount, allInTotal, aggressiveLabel }) {
    const available = action => !localTurn || legal.includes(action);
    if (toCall > 0) {
      return [
        { key:"fold", label:"FOLD", amount:"", cls:"fold", edge:"left", slot:"top", enabled:available("fold") },
        { key:"call", label:"CALL", amount:stripHudUnit(formatBB(toCall)), cls:"call", edge:"right", slot:"top", enabled:available("call") },
        { key:"aggressive", label:aggressiveLabel, amount:stripHudUnit(formatBB(amount)), cls:"raise", edge:"right", slot:"bottom", enabled:available("raise") },
      ].filter(def => def.enabled);
    }
    return [
      { key:"check", label:"CHECK", amount:"", cls:"check", edge:"left", slot:"top", enabled:available("check") },
      { key:"fold", label:"FOLD", amount:"", cls:"fold", edge:"left", slot:"bottom", enabled:available("fold") },
      { key:"aggressive", label:"BET", amount:stripHudUnit(formatBB(amount)), cls:"raise", edge:"right", slot:"top", enabled:available("bet") },
      { key:"all_in", label:"ALL IN", amount:stripHudUnit(formatBB(allInTotal)), cls:"all-in", edge:"right", slot:"bottom", enabled:available("all_in"), allIn:true },
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
    const legal = game?.human_legal_actions || [];
    const toCall = estimatedLocalToCall();
    const amount = Number(document.getElementById("amount")?.value || amountBounds().value || 0);
    const bounds = amountBounds();
    const allInTotal = Number(localViewerPlayer()?.stack || 0) + Number(localViewerPlayer()?.street_invested || 0);
    const aggressiveLabel = Number(game?.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "RAISE" : "BET";
    const defs = mobileActionDefinitions({ localTurn, legal, toCall, amount, allInTotal, aggressiveLabel });
    const aggressive = defs.find(def => def.key === "aggressive");
    const atMax = Math.abs(amount - Number(bounds.max || 0)) < 1e-9;
    if (aggressive && atMax) {
      aggressive.label = "ALL IN";
      aggressive.amount = stripHudUnit(formatBB(allInTotal));
      aggressive.cls = "all-in";
      aggressive.allIn = true;
    }
    const signature = defs.map(def => def.key).join("|");
    if (grid.dataset.v038ActionSignature !== signature) {
      grid.innerHTML = "";
      defs.forEach(() => grid.appendChild(document.createElement("button")));
      grid.dataset.v038ActionSignature = signature;
    }
    grid.dataset.v038ReferenceActions = "1";
    [...grid.children].forEach((button, index) => {
      const def = defs[index];
      button.type = "button";
      button.disabled = false;
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
        value.classList.remove("v038-amount-pulse");
        void value.offsetWidth;
        value.classList.add("v038-amount-pulse");
      }
      button.setAttribute("aria-label", `${def.label}${def.amount ? ` ${def.amount}` : ""}`);
      button.onclick = () => {
        if (button.dataset.v038SuppressClick) {
          button.removeAttribute("data-v038-suppress-click");
          return;
        }
        if (!game || game.terminal || !alive) return;
        if (def.allIn) return openSizingMode("all_in", bounds.max);
        if (def.key === "aggressive") return openSizingMode(aggressiveLabel === "RAISE" ? "raise" : "bet", amount);
        if (!localTurn) {
          togglePendingAction(def.key);
          renderMobileSelectedCard();
          queueSync();
          return;
        }
        clearPendingAction(false);
        if (def.key === "check") return sendAction("check", 0);
        if (def.key === "fold") return sendAction("fold", 0);
        if (def.key === "call") return sendAction("call", 0);
      };
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

  function syncFinalReference() {
    if (!isMobileV2()) {
      teardownFinalReference();
      return;
    }
    referenceActive = true;
    const legal = game?.human_legal_actions || [];
    const aggressiveLegal = !isLocalHumanTurn() || legal.includes("bet") || legal.includes("raise") || legal.includes("all_in");
    if (sizingMode && (!game || game.terminal || !localPlayerAlive() || !aggressiveLegal)) closeSizingMode(false);
    ensurePresetButtons();
    ensureHudSummary();
    ensureMobileHeaderControls();
    syncSeatStackLabels();
    syncTableNumberLabels();
    syncAvatarReadyControl();
    syncAllSeatReadyMarks();
    syncSeatActionStates();
    ensureReadyCountdown();
    syncTableTurnHud();
    syncCompletedHandReset();
    configureReferenceActions();
    syncSizingModeText();
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
