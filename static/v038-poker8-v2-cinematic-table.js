(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v038-poker8-v2-cinematic-table-style";
  style.textContent = `
    @media (max-width:780px){
      body.v014.poker8-v2-sixmax{
        --p8-wood-dark:#120804;
        --p8-wood-mid:#51270f;
        --p8-felt:#003b24;
        --table-stage-h:calc(100dvh - 278px)!important;
        --seat-3-y:20%!important;
        background:
          linear-gradient(90deg,rgba(0,0,0,.55),transparent 20%,transparent 80%,rgba(0,0,0,.55)),
          repeating-linear-gradient(96deg,#080402 0 7px,#180b05 8px 14px,#0c0503 15px 23px)!important;
      }

      body.v014.poker8-v2-sixmax .mobile-game-header::after{display:none!important;content:none!important;}

      body.v014.poker8-v2-sixmax .table-frame{
        height:var(--table-stage-h)!important;
        min-height:var(--table-stage-h)!important;
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{top:20%!important;}

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

      body.v014.poker8-v2-sixmax .table-glow{
        display:block!important;
        inset:10%!important;
        border-radius:50%!important;
        background:radial-gradient(ellipse,rgba(21,121,74,.15),transparent 68%)!important;
      }

      body.v014.poker8-v2-sixmax .seat{width:90px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:124px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{--seat-accent:195;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{--seat-accent:190;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{--seat-accent:282;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{--seat-accent:142;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{--seat-accent:34;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{--seat-accent:300;}

      body.v014.poker8-v2-sixmax .seat-card{
        --seat-neon:hsl(var(--seat-accent),92%,62%);
        min-height:60px!important;
        padding:19px 6px 6px!important;
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
        top:-30px!important;
        width:50px!important;height:50px!important;
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
        width:50px!important;height:50px!important;
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
        min-height:66px!important;padding-top:22px!important;
        border-color:rgba(48,188,255,.92)!important;
        box-shadow:0 0 0 1px rgba(48,188,255,.14),0 0 20px rgba(31,165,255,.34),0 9px 20px rgba(0,0,0,.62)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap{top:-33px!important;width:56px!important;height:56px!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{width:56px!important;height:56px!important;border-color:#35bfff!important;font-size:12px!important;}
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

      @media (max-width:370px){
        body.v014.poker8-v2-sixmax .seat{width:84px!important;}
        body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:116px!important;}
        body.v014.poker8-v2-sixmax .avatar-wrap{transform:scale(.92);transform-origin:center bottom;}
        body.v014.poker8-v2-sixmax .board-cards .card{width:39px!important;height:56px!important;}
      }
    }
  `;
  document.head.appendChild(style);
})();
