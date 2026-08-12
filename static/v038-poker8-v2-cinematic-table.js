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
        --p8-hud-h:260px;
        --p8-bottom-reserve:46px;
        --table-stage-h:calc(100dvh - 50px - var(--p8-hud-h) - var(--p8-bottom-reserve))!important;
        --seat-0-y:86%!important;
        --seat-1-y:67%!important;
        --seat-2-y:31%!important;
        --seat-3-y:20%!important;
        --seat-4-y:31%!important;
        --seat-5-y:67%!important;
        --pot-y:29%!important;
        --pot-chips-y:54%!important;
        --board-y:43%!important;
        background:
          linear-gradient(90deg,rgba(0,0,0,.55),transparent 20%,transparent 80%,rgba(0,0,0,.55)),
          repeating-linear-gradient(96deg,#080402 0 7px,#180b05 8px 14px,#0c0503 15px 23px)!important;
      }

      body.v014.poker8-v2-sixmax .mobile-game-header::after{display:none!important;content:none!important;}

      body.v014.poker8-v2-sixmax .table-frame{
        height:var(--table-stage-h)!important;
        min-height:var(--table-stage-h)!important;
        perspective:var(--p8-perspective)!important;
        perspective-origin:50% 22%!important;
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{top:86%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{top:67%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{top:31%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{top:20%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{top:31%!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{top:67%!important;}

      body.v014.poker8-v2-sixmax .table-frame{
        padding:0 5px 1px!important;
        background:
          radial-gradient(ellipse at 50% 34%,rgba(110,56,18,.22),transparent 58%),
          repeating-linear-gradient(96deg,rgba(44,20,8,.78) 0 7px,rgba(12,6,3,.94) 8px 15px,rgba(55,25,9,.72) 16px 22px)!important;
        box-shadow:inset 0 18px 34px rgba(0,0,0,.55),inset 0 -18px 34px rgba(0,0,0,.66)!important;
      }

      body.v014.poker8-v2-sixmax .felt{
        border-width:15px!important;
        border-radius:49% / 36%!important;
        transform:rotateX(5deg) scale(.985,1.025)!important;
        transform-origin:50% 54%!important;
        transform-style:preserve-3d!important;
        background:
          radial-gradient(circle at 25% 18%,rgba(69,151,103,.12),transparent 27%) padding-box,
          radial-gradient(circle at 76% 74%,rgba(0,8,5,.30),transparent 34%) padding-box,
          repeating-radial-gradient(ellipse at 50% 50%,rgba(255,255,255,.012) 0 1px,transparent 1px 5px) padding-box,
          linear-gradient(145deg,#075234 0%,#003d25 46%,#002c1b 100%) padding-box,
          repeating-linear-gradient(102deg,#1a0b04 0 6px,#713714 7px 13px,#2d1407 14px 20px,#8b4c20 21px 27px,#281106 28px 35px) border-box!important;
        outline:2px solid rgba(4,11,7,.92)!important;
        box-shadow:
          inset 0 0 86px rgba(0,0,0,.48),
          inset 0 0 0 2px rgba(47,255,170,.64),
          inset 0 0 0 5px rgba(0,35,22,.92),
          inset 0 0 0 7px rgba(41,255,166,.30),
          0 0 0 2px rgba(100,51,18,.58),
          0 0 0 5px rgba(7,3,2,.94),
          0 0 24px rgba(28,239,167,.20),
          0 18px 38px rgba(0,0,0,.64)!important;
      }

      body.v014.poker8-v2-sixmax .felt::before{
        inset:10px!important;
        border:1px solid rgba(57,255,179,.62)!important;
        box-shadow:0 0 9px rgba(40,255,174,.34),inset 0 0 9px rgba(40,255,174,.14)!important;
      }

      body.v014.poker8-v2-sixmax .felt :is(.seat-card,.board-cards .card,.pot-total>*,.pot-chips>*,.bet-marker>*){
        rotate:x -5deg;
      }

      body.v014.poker8-v2-sixmax .table-glow{
        display:block!important;
        inset:10%!important;
        border-radius:50%!important;
        background:radial-gradient(ellipse,rgba(21,121,74,.15),transparent 68%)!important;
      }

      body.v014.poker8-v2-sixmax .seat{width:96px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:128px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{--seat-accent:195;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{--seat-accent:190;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{--seat-accent:282;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{--seat-accent:142;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{--seat-accent:34;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{--seat-accent:300;}

      body.v014.poker8-v2-sixmax .seat-card{
        --seat-neon:hsl(var(--seat-accent),92%,62%);
        min-height:64px!important;
        padding:21px 6px 7px!important;
        border:1px solid hsla(var(--seat-accent),90%,60%,.72)!important;
        border-radius:12px!important;
        background:linear-gradient(180deg,rgba(8,8,10,.97),rgba(1,3,4,.995))!important;
        box-shadow:0 0 12px hsla(var(--seat-accent),92%,55%,.20),0 8px 17px rgba(0,0,0,.58),inset 0 1px 0 rgba(255,255,255,.05)!important;
      }

      body.v014.poker8-v2-sixmax .seat-card::after{
        content:"";
        position:absolute;
        z-index:2;
        left:8px;right:8px;top:2px;height:1px;
        border-radius:100%;
        background:linear-gradient(90deg,transparent,hsla(var(--seat-accent),100%,78%,.64),transparent);
        box-shadow:0 0 6px hsla(var(--seat-accent),100%,62%,.48);
        pointer-events:none;
      }

      body.v014.poker8-v2-sixmax .avatar-wrap{
        top:-33px!important;
        width:54px!important;height:54px!important;
        margin:0 auto!important;
        isolation:isolate;
      }

      body.v014.poker8-v2-sixmax .avatar-wrap::before,
      body.v014.poker8-v2-sixmax .avatar-wrap::after{
        content:"";
        position:absolute;
        z-index:-2;
        top:-22px;
        width:28px;height:39px;
        border:1px solid hsla(var(--seat-accent),95%,72%,.78);
        border-radius:5px;
        background:
          radial-gradient(circle at 50% 48%,transparent 0 5px,hsla(var(--seat-accent),85%,72%,.35) 5px 6px,transparent 6px),
          repeating-linear-gradient(45deg,hsla(var(--seat-accent),65%,36%,.74) 0 3px,hsla(var(--seat-accent),65%,15%,.96) 3px 6px),
          #050707;
        box-shadow:inset 0 0 0 2px rgba(0,0,0,.54),0 0 10px hsla(var(--seat-accent),95%,56%,.28),0 5px 9px rgba(0,0,0,.55);
      }
      body.v014.poker8-v2-sixmax .avatar-wrap::before{left:-3px;transform:rotate(-12deg);transform-origin:bottom right;}
      body.v014.poker8-v2-sixmax .avatar-wrap::after{right:-3px;transform:rotate(12deg);transform-origin:bottom left;}
      body.v014.poker8-v2-sixmax .seat-card:has(.player-cards:not(:empty)) .avatar-wrap::before,
      body.v014.poker8-v2-sixmax .seat-card:has(.player-cards:not(:empty)) .avatar-wrap::after{opacity:0;}

      body.v014.poker8-v2-sixmax .player-avatar{
        width:54px!important;height:54px!important;
        border:2px solid hsla(var(--seat-accent),100%,70%,.88)!important;
        background-image:var(--profile-avatar-image,radial-gradient(circle at 50% 32%,hsla(var(--seat-accent),62%,46%,.45),transparent 31%),radial-gradient(circle at 50% 78%,#07110e 0 42%,#010303 70%))!important;
        background-position:center!important;
        background-size:cover!important;
        color:#f5fff9!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 16px hsla(var(--seat-accent),96%,58%,.46),inset 0 -10px 18px rgba(0,0,0,.50)!important;
        font-size:11px!important;
      }

      body.v014.poker8-v2-sixmax .seat-name{max-width:68px!important;font-size:9px!important;line-height:1!important;}
      body.v014.poker8-v2-sixmax .seat-stack{margin-top:3px!important;font-size:12px!important;line-height:1!important;color:var(--seat-neon)!important;}
      body.v014.poker8-v2-sixmax .bot-level{display:none!important;}
      body.v014.poker8-v2-sixmax .position-chip{font-size:6px!important;padding:1px 3px!important;}
      body.v014.poker8-v2-sixmax .seat-meta{margin-top:3px!important;}

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-card{
        min-height:70px!important;padding-top:24px!important;
        border-color:rgba(48,188,255,.92)!important;
        box-shadow:0 0 0 1px rgba(48,188,255,.14),0 0 20px rgba(31,165,255,.34),0 9px 20px rgba(0,0,0,.62)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap{top:-36px!important;width:60px!important;height:60px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{width:60px!important;height:60px!important;border-color:#35bfff!important;font-size:12px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-name{font-size:10px!important;max-width:92px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{font-size:13px!important;color:#35c6ff!important;}

      body.v014.poker8-v2-sixmax .player-cards{
        top:-51px!important;bottom:auto!important;margin:0!important;min-height:0!important;gap:2px!important;
      }
      body.v014.poker8-v2-sixmax .player-cards .card.back{
        width:30px!important;height:42px!important;border-radius:5px!important;
        border:1px solid hsla(var(--seat-accent),95%,75%,.80)!important;
        background:
          radial-gradient(circle at center,transparent 0 6px,hsla(var(--seat-accent),90%,74%,.42) 6px 7px,transparent 7px),
          repeating-linear-gradient(45deg,hsla(var(--seat-accent),62%,38%,.74) 0 3px,hsla(var(--seat-accent),62%,16%,.96) 3px 6px)!important;
        box-shadow:inset 0 0 0 2px rgba(0,0,0,.48),0 0 9px hsla(var(--seat-accent),94%,58%,.28)!important;
      }
      body.v014.poker8-v2-sixmax .player-cards .card.back:first-child{transform:rotate(-8deg) translateX(2px)!important;}
      body.v014.poker8-v2-sixmax .player-cards .card.back:last-child{transform:rotate(8deg) translateX(-2px)!important;}

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards{top:-64px!important;gap:4px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card{
        width:43px!important;height:61px!important;border-radius:6px!important;
        background:linear-gradient(150deg,#f7f5e9,#d8d5c9)!important;
        color:#101b1a!important;border:1px solid #56c8ff!important;
        box-shadow:0 0 10px rgba(47,184,255,.38),0 5px 10px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card.red{color:#df3a2d!important;border-color:#ff674d!important;}

      body.v014.poker8-v2-sixmax .board-cards{gap:3px!important;}
      body.v014.poker8-v2-sixmax .board-cards .card{
        width:42px!important;height:59px!important;
        border:1px solid rgba(98,255,170,.82)!important;border-radius:5px!important;
        background:linear-gradient(150deg,#faf9ee 0%,#deddd1 100%)!important;
        color:#101b18!important;
        box-shadow:0 0 9px rgba(48,255,158,.28),0 5px 9px rgba(0,0,0,.48),inset 0 0 0 1px rgba(255,255,255,.60)!important;
      }
      body.v014.poker8-v2-sixmax .board-cards .card.red{color:#df392c!important;border-color:#ff5f43!important;box-shadow:0 0 9px rgba(255,82,54,.26),0 5px 9px rgba(0,0,0,.48)!important;}

      body.v014.poker8-v2-sixmax .pot-total{
        min-width:74px!important;padding:4px 9px!important;border-radius:7px!important;
        border-color:rgba(60,225,150,.22)!important;background:rgba(1,31,18,.66)!important;
        box-shadow:inset 0 0 12px rgba(57,228,152,.04),0 4px 11px rgba(0,0,0,.34)!important;
      }
      body.v014.poker8-v2-sixmax .pot-total-label{font-size:8px!important;letter-spacing:.08em!important;}
      body.v014.poker8-v2-sixmax .pot-total strong{font-size:18px!important;line-height:1!important;}

      body.v014.poker8-v2-sixmax .pot-chips .chip-cluster.pot-cluster{height:48px!important;min-width:112px!important;filter:drop-shadow(0 7px 5px rgba(0,0,0,.48))!important;}
      body.v014.poker8-v2-sixmax .pot-chips .chip-column.pot-stack{width:19px!important;height:44px!important;}
      body.v014.poker8-v2-sixmax .pot-chips .poker-chip{
        width:19px!important;height:8px!important;border-width:1px!important;
        transform:translateX(-50%) translateY(calc(var(--i) * -3.2px))!important;
        box-shadow:0 2px 2px rgba(0,0,0,.50),inset 0 2px 0 rgba(255,255,255,.24),inset 0 -3px 0 rgba(0,0,0,.36)!important;
      }
      body.v014.poker8-v2-sixmax .pot-chips .poker-chip::before{left:3px!important;right:3px!important;height:3px!important;}

      body.v014.poker8-v2-sixmax .bet-marker .chip-cluster.compact{transform:scale(.82)!important;transform-origin:center bottom!important;}
      body.v014.poker8-v2-sixmax .bet-marker span{
        margin-top:-7px!important;padding:1px 4px!important;border:0!important;background:rgba(1,7,6,.76)!important;
        color:#ecfff5!important;font-size:7px!important;box-shadow:none!important;
      }

      body.v014.poker8-v2-sixmax .dealer-button{
        border:1px solid #ecece2!important;background:radial-gradient(circle at 32% 28%,#fff,#d9d9ce 60%,#83867c)!important;
        color:#181a17!important;box-shadow:0 2px 6px rgba(0,0,0,.62)!important;
      }

      body.v014.poker8-v2-sixmax .seat .seat-card.v032-in-hand:not(.v032-active-turn){
        border-color:hsla(var(--seat-accent),90%,60%,.72)!important;
        box-shadow:0 0 12px hsla(var(--seat-accent),92%,55%,.20),0 8px 17px rgba(0,0,0,.58)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn{
        border-color:rgba(255,166,61,.92)!important;
        box-shadow:0 0 0 1px rgba(255,157,44,.24),0 0 22px rgba(255,130,20,.38),0 9px 20px rgba(0,0,0,.62)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .player-avatar{
        border-color:#ffad49!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 20px rgba(255,143,35,.54),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.v032-folded{
        opacity:.28!important;filter:saturate(.18) brightness(.68)!important;box-shadow:none!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.all-in{
        border-color:#e7bb5c!important;
        box-shadow:0 0 0 1px rgba(231,187,92,.20),0 0 18px rgba(231,161,54,.32),0 9px 20px rgba(0,0,0,.62)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.all-in .player-avatar{
        border-color:#f1c867!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 18px rgba(238,180,65,.45),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }

      body.v014.poker8-v2-sixmax .pot-total{top:29%!important;}
      body.v014.poker8-v2-sixmax .board-cards{top:43%!important;}
      body.v014.poker8-v2-sixmax .pot-chips{top:54%!important;}

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
        position:absolute!important;left:8px;right:8px;top:7px!important;height:34px;
        display:grid;grid-template-columns:repeat(3,1fr);align-items:center;text-align:center;
        border-bottom:1px solid rgba(95,132,121,.18);font-size:6px;letter-spacing:.10em;color:#8ca59c;
      }
      body.v014.poker8-v2-sixmax .v038-hud-summary b{display:block;margin-top:1px;font-size:13px;line-height:1;color:#39bfff;letter-spacing:0;}
      body.v014.poker8-v2-sixmax .v038-hud-summary span:nth-child(2) b{color:#59e77c;}
      body.v014.poker8-v2-sixmax .v038-hud-summary span:nth-child(3) b{color:#ff9e45;}
      body.v014.poker8-v2-sixmax .sizing-wrap{display:contents!important;}
      body.v014.poker8-v2-sixmax .sizing-wrap > label{display:none!important;}
      body.v014.poker8-v2-sixmax .quick-sizes{
        position:absolute!important;left:8px;right:8px;top:45px!important;height:34px;
        display:grid!important;grid-template-columns:repeat(5,1fr)!important;gap:4px!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button{
        min-height:32px!important;height:32px!important;padding:2px!important;border-radius:6px!important;font-size:7px!important;
        color:#fff!important;text-shadow:0 0 5px rgba(255,255,255,.48)!important;
        transition:color 180ms ease,border-color 180ms ease,box-shadow 180ms ease,background 180ms ease!important;
      }
      body.v014.poker8-v2-sixmax .quick-sizes button strong{font-size:8px!important;line-height:1!important;color:#fff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button small{font-size:6px!important;line-height:1!important;color:#f4f7ff!important;}
      body.v014.poker8-v2-sixmax .quick-sizes button.v038-size-selected{
        color:#fff!important;border-color:#ff3bd5!important;background:rgba(55,4,47,.94)!important;
        box-shadow:0 0 0 1px rgba(255,59,213,.45),0 0 13px rgba(255,59,213,.72),inset 0 0 10px rgba(255,59,213,.16)!important;
      }
      body.v014.poker8-v2-sixmax .bet-slider-row{order:3;height:22px!important;padding:0 5px!important;}
      body.v014.poker8-v2-sixmax .bet-slider-row{
        position:absolute!important;left:8px;right:8px;top:123px!important;height:22px!important;padding:0 5px!important;
      }
      body.v014.poker8-v2-sixmax #amountSlider{height:20px!important;}
      body.v014.poker8-v2-sixmax .amount-row{
        position:absolute!important;left:8px;right:8px;top:83px!important;
        min-height:36px!important;height:36px!important;margin:0!important;padding:2px!important;border-radius:8px!important;
      }
      body.v014.poker8-v2-sixmax .amount-row::before{display:none!important;content:none!important;}
      body.v014.poker8-v2-sixmax .amount-step{width:32px!important;height:30px!important;}
      body.v014.poker8-v2-sixmax .amount-row input[type=number]{height:30px!important;font-size:17px!important;}
      body.v014.poker8-v2-sixmax .action-grid{
        order:5;display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:repeat(2,44px)!important;gap:6px!important;
        position:absolute!important;z-index:4;left:8px;right:8px;bottom:4px!important;height:94px!important;
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
      body.v014.poker8-v2-sixmax .action-slot.v038-all-in-armed::after{
        content:"";position:absolute;left:5px;right:5px;bottom:3px;height:2px;border-radius:9px;background:#ffc44d;
        transform-origin:left center;animation:v038ConfirmDrain 3000ms linear forwards;box-shadow:0 0 7px rgba(255,196,77,.85);
      }
      body.v014.poker8-v2-sixmax .action-slot.v038-all-in-armed::before{
        content:"3 SEC";position:absolute;right:6px;bottom:5px;color:#ffc44d;font-size:5px;font-weight:900;letter-spacing:.06em;
      }
      @keyframes v038AmountPulse{50%{transform:scale(1.08);filter:brightness(1.45)}100%{transform:scale(1);filter:none}}
      @keyframes v038ConfirmDrain{to{transform:scaleX(0)}}
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .quick-sizes button,
        body.v014.poker8-v2-sixmax .action-grid .action-slot{transition:none!important;}
        body.v014.poker8-v2-sixmax .v038-action-amount.v038-amount-pulse{animation:none!important;}
        body.v014.poker8-v2-sixmax .action-slot.v038-all-in-armed::after{animation:none!important;}
        body.v014.poker8-v2-sixmax .action-slot.v038-all-in-armed::before{content:"CONFIRM · 3 SEC";}
      }
      body.v014.poker8-v2-sixmax .app-shell{
        height:100dvh!important;min-height:100dvh!important;overflow:hidden!important;
        padding-bottom:var(--p8-bottom-reserve)!important;
        background:linear-gradient(180deg,transparent 0 calc(100% - var(--p8-bottom-reserve)),#010403 calc(100% - var(--p8-bottom-reserve)) 100%)!important;
      }

      @media (max-width:370px){
        body.v014.poker8-v2-sixmax .seat{width:90px!important;}
        body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:120px!important;}
        body.v014.poker8-v2-sixmax .avatar-wrap{transform:scale(.92);transform-origin:center bottom;}
        body.v014.poker8-v2-sixmax .board-cards .card{width:39px!important;height:56px!important;}
      }
    }
  `;
  document.head.appendChild(style);

  const setText = (node, value) => {
    if (node && node.textContent !== value) node.textContent = value;
  };

  let referenceActive = false;
  let presetSnapshot = null;
  let allInArmedUntil = 0;
  let allInArmedSource = "";
  let allInArmedFingerprint = "";
  let allInTimer = 0;
  const ALL_IN_CONFIRM_MS = 3000;

  function clearPresetSelection() {
    document.querySelectorAll(".quick-sizes .v038-size-selected").forEach(button => button.classList.remove("v038-size-selected"));
  }

  function selectPreset(button) {
    clearPresetSelection();
    button?.classList.add("v038-size-selected");
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
  }

  function clearAllInConfirmation(render = true) {
    window.clearTimeout(allInTimer);
    allInTimer = 0;
    allInArmedUntil = 0;
    allInArmedSource = "";
    allInArmedFingerprint = "";
    if (render) queueSync();
  }

  function allInFingerprint(source) {
    const amount = Number(document.getElementById("amount")?.value || 0);
    return [game?.hand_id, game?.street, game?.acting_player, game?.history?.length || 0, source, source === "aggressive" ? amount : ""].join(":");
  }

  function confirmAllIn(source, localTurn, amount, legal) {
    const now = Date.now();
    const fingerprint = allInFingerprint(source);
    if (allInArmedSource !== source || allInArmedUntil <= now || allInArmedFingerprint !== fingerprint) {
      clearAllInConfirmation(false);
      allInArmedSource = source;
      allInArmedUntil = now + ALL_IN_CONFIRM_MS;
      allInArmedFingerprint = fingerprint;
      allInTimer = window.setTimeout(() => clearAllInConfirmation(), ALL_IN_CONFIRM_MS);
      queueSync();
      return;
    }
    clearAllInConfirmation(false);
    if (source === "aggressive") {
      if (!localTurn) {
        togglePendingAction("aggressive");
        renderMobileSelectedCard();
        queueSync();
        return;
      }
      clearPendingAction(false);
      return sendAction(legal.includes("raise") ? "raise" : "bet", amount);
    }
    if (!localTurn) {
      togglePendingAction("all_in");
      renderMobileSelectedCard();
      queueSync();
      return;
    }
    clearPendingAction(false);
    return sendAction("all_in", 0);
  }

  function ensureHudSummary() {
    const panel = document.querySelector(".action-panel");
    if (!panel) return;
    let summary = panel.querySelector(".v038-hud-summary");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "v038-hud-summary";
      summary.innerHTML = '<span>УРАВНЯТЬ<b data-v038-call>0.00 ББ</b></span><span>БАНК<b data-v038-pot>0.00 ББ</b></span><span>СТАВКА<b data-v038-bet>0.00 ББ</b></span>';
      panel.prepend(summary);
    }
    const call = typeof estimatedLocalToCall === "function" ? formatBB(estimatedLocalToCall()) : "0.00 ББ";
    const pot = document.getElementById("pot")?.textContent?.trim() || "0.00 ББ";
    const amount = document.getElementById("amount")?.value || "0.00";
    setText(summary.querySelector("[data-v038-call]"), call);
    setText(summary.querySelector("[data-v038-pot]"), pot);
    setText(summary.querySelector("[data-v038-bet]"), `${amount} ББ`);
  }

  function configureReferenceActions() {
    const grid = document.getElementById("actionButtons");
    const current = [...(grid?.querySelectorAll("[data-v038-reference-action]") || [])];
    if (!grid) return;
    const alive = localPlayerAlive();
    const localTurn = isLocalHumanTurn();
    const legal = game?.human_legal_actions || [];
    const toCall = estimatedLocalToCall();
    const amount = Number(document.getElementById("amount")?.value || amountBounds().value || 0);
    const bounds = amountBounds();
    const allInTotal = Number(localViewerPlayer()?.stack || 0) + Number(localViewerPlayer()?.street_invested || 0);
    const leftKey = localTurn ? (legal.includes("check") ? "check" : "fold") : (toCall > 0 ? "fold" : "check");
    const atMax = Math.abs(amount - Number(bounds.max || 0)) < 1e-9;
    const aggressiveLabel = Number(game?.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "RAISE" : "BET";
    if (allInArmedSource && (allInArmedUntil <= Date.now() || allInArmedFingerprint !== allInFingerprint(allInArmedSource))) {
      clearAllInConfirmation(false);
    }
    const defs = [
      { key:"call", label:"CALL", amount:formatBB(toCall), cls:"call" },
      { key:"all_in", label:allInArmedSource === "all_in" ? "CONFIRM" : "ALL IN", amount:formatBB(allInTotal), cls:"all-in", allIn:true },
      { key:leftKey, label:leftKey === "check" ? "CHECK" : "FOLD", amount:"", cls:leftKey },
      { key:"aggressive", label:allInArmedSource === "aggressive" ? "CONFIRM" : atMax ? "ALL IN" : aggressiveLabel, amount:formatBB(atMax ? allInTotal : amount), cls:atMax ? "all-in" : "raise", allIn:atMax },
    ];
    if (current.length !== 4) {
      grid.innerHTML = "";
      defs.forEach(() => grid.appendChild(document.createElement("button")));
    }
    grid.dataset.v038ReferenceActions = "1";
    [...grid.children].forEach((button, index) => {
      const def = defs[index];
      button.type = "button";
      button.dataset.actionKey = def.key;
      button.dataset.v038ReferenceAction = "1";
      button.className = `action-slot ${def.cls}`;
      button.classList.toggle("queued", pendingAction?.kind === def.key);
      button.classList.toggle("v038-all-in-armed", allInArmedSource === def.key);
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
      let enabled = Boolean(game && !game.terminal && alive);
      if (localTurn) {
        if (def.key === "check") enabled = legal.includes("check");
        else if (def.key === "fold") enabled = legal.includes("fold");
        else if (def.key === "call") enabled = legal.includes("call");
        else if (def.key === "all_in") enabled = legal.includes("all_in");
        else if (def.allIn) enabled = legal.includes("bet") || legal.includes("raise");
        else enabled = legal.includes("bet") || legal.includes("raise");
      } else if (def.key === "call") enabled = enabled && toCall > 0;
      button.disabled = !enabled;
      button.onclick = () => {
        if (!game || game.terminal || !alive) return;
        if (def.allIn) return confirmAllIn(def.key, localTurn, amount, legal);
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
        return sendAction(legal.includes("raise") ? "raise" : "bet", amount);
      };
    });
  }

  function teardownFinalReference() {
    if (!referenceActive) return;
    referenceActive = false;
    clearAllInConfirmation(false);
    clearPresetSelection();
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
    ensurePresetButtons();
    ensureHudSummary();
    configureReferenceActions();
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

  const start = () => {
    syncFinalReference();
    const buttons = document.getElementById("actionButtons");
    if (buttons) new MutationObserver(queueSync).observe(buttons, { childList:true });
    const sizing = document.getElementById("sizingWrap");
    if (sizing && !sizing.dataset.v038InputSync) {
      sizing.dataset.v038InputSync = "1";
      sizing.addEventListener("input", event => {
        clearPresetSelection();
        clearAllInConfirmation(false);
        queueSync();
      });
    }
    if (!document.body.dataset.v038ClickSync) {
      document.body.dataset.v038ClickSync = "1";
      document.addEventListener("click", event => {
        if (event.target?.closest?.("#amountMinus,#amountPlus")) clearPresetSelection();
        if (allInArmedSource && !event.target?.closest?.("[data-v038-all-in-trigger]")) clearAllInConfirmation();
      });
    }
  };

  window.addEventListener("resize", queueSync);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once:true });
  else start();
})();
