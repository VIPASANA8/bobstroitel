(() => {
  "use strict";

  const RANK_VALUE = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"T":10,"J":11,"Q":12,"K":13,"A":14};
  const CLASS_NAMES = ["старшая карта","пара","две пары","тройка","стрит","флеш","фулл-хаус","каре","стрит-флеш"];
  const RANK_GROUP = {14:"тузы",13:"короли",12:"дамы",11:"валеты",10:"десятки",9:"девятки",8:"восьмёрки",7:"семёрки",6:"шестёрки",5:"пятёрки",4:"четвёрки",3:"тройки",2:"двойки"};
  const RANK_SINGLE = {14:"туз",13:"король",12:"дама",11:"валет",10:"10",9:"9",8:"8",7:"7",6:"6",5:"5",4:"4",3:"3",2:"2"};
  const RANK_SHORT = {14:"A",13:"K",12:"Q",11:"J",10:"10",9:"9",8:"8",7:"7",6:"6",5:"5",4:"4",3:"3",2:"2"};

  let dismissedHand = null;

  function straightHigh(ranks) {
    const unique = [...new Set(ranks)].sort((a,b) => b-a);
    if (unique.includes(14)) unique.push(1);
    let run = 1;
    for (let i = 1; i < unique.length; i++) {
      if (unique[i - 1] - 1 === unique[i]) {
        run += 1;
        if (run >= 5) return unique[i - 4];
      } else {
        run = 1;
      }
    }
    return null;
  }

  function evaluateFive(cards) {
    const ranks = cards.map(card => RANK_VALUE[card?.[0]]).filter(Boolean);
    const suits = cards.map(card => card?.[1]);
    const counts = new Map();
    ranks.forEach(rank => counts.set(rank, (counts.get(rank) || 0) + 1));
    const groups = [...counts.entries()].map(([rank,count]) => [count,rank]).sort((a,b) => b[0]-a[0] || b[1]-a[1]);
    const flush = new Set(suits).size === 1;
    const straight = straightHigh(ranks);
    if (flush && straight) return [8, straight];
    if (groups[0]?.[0] === 4) {
      const quad = groups[0][1];
      return [7, quad, Math.max(...ranks.filter(r => r !== quad))];
    }
    const trips = [...counts.entries()].filter(([,c]) => c === 3).map(([r]) => r).sort((a,b) => b-a);
    const pairs = [...counts.entries()].filter(([,c]) => c === 2).map(([r]) => r).sort((a,b) => b-a);
    if (trips.length && (trips.length >= 2 || pairs.length)) return [6, trips[0], trips.length >= 2 ? trips[1] : pairs[0]];
    if (flush) return [5, ...[...ranks].sort((a,b) => b-a)];
    if (straight) return [4, straight];
    if (trips.length) {
      const kickers = ranks.filter(r => r !== trips[0]).sort((a,b) => b-a).slice(0,2);
      return [3, trips[0], ...kickers];
    }
    if (pairs.length >= 2) {
      const [high, low] = pairs;
      return [2, high, low, Math.max(...ranks.filter(r => r !== high && r !== low))];
    }
    if (pairs.length === 1) {
      const pair = pairs[0];
      return [1, pair, ...ranks.filter(r => r !== pair).sort((a,b) => b-a).slice(0,3)];
    }
    return [0, ...[...ranks].sort((a,b) => b-a)];
  }

  function combinationsFive(cards) {
    const out = [];
    for (let a=0; a<cards.length-4; a++)
      for (let b=a+1; b<cards.length-3; b++)
        for (let c=b+1; c<cards.length-2; c++)
          for (let d=c+1; d<cards.length-1; d++)
            for (let e=d+1; e<cards.length; e++) out.push([cards[a],cards[b],cards[c],cards[d],cards[e]]);
    return out;
  }

  function compareScore(a,b) {
    const n = Math.max(a.length,b.length);
    for (let i=0; i<n; i++) {
      const av = a[i] || 0, bv = b[i] || 0;
      if (av !== bv) return av > bv ? 1 : -1;
    }
    return 0;
  }

  function scoreHand(hole, board) {
    const cards = [...(hole || []), ...(board || [])];
    if (cards.length < 5 || cards.some(code => !code || code === "??")) return null;
    let best = null;
    for (const combo of combinationsFive(cards)) {
      const score = evaluateFive(combo);
      if (!best || compareScore(score,best) > 0) best = score;
    }
    return best;
  }

  function describeScore(score) {
    if (!score) return "комбинация недоступна";
    const category = score[0];
    if (category === 8) return `стрит-флеш до ${RANK_SINGLE[score[1]] || score[1]}`;
    if (category === 7) return `каре: ${RANK_GROUP[score[1]]}, кикер ${RANK_SINGLE[score[2]]}`;
    if (category === 6) return `фулл-хаус: ${RANK_GROUP[score[1]]} + ${RANK_GROUP[score[2]]}`;
    if (category === 5) return `флеш: ${score.slice(1).map(r => RANK_SHORT[r]).join("-")}`;
    if (category === 4) return `стрит до ${RANK_SINGLE[score[1]] || score[1]}`;
    if (category === 3) return `тройка: ${RANK_GROUP[score[1]]}, кикеры ${RANK_SINGLE[score[2]]} и ${RANK_SINGLE[score[3]]}`;
    if (category === 2) return `две пары: ${RANK_GROUP[score[1]]} и ${RANK_GROUP[score[2]]}, кикер ${RANK_SINGLE[score[3]]}`;
    if (category === 1) return `пара: ${RANK_GROUP[score[1]]}, кикеры ${score.slice(2).map(r => RANK_SINGLE[r]).join(", ")}`;
    return `старшая карта: ${score.slice(1).map(r => RANK_SHORT[r]).join("-")}`;
  }

  function hasVisibleCards(player) {
    return Array.isArray(player?.hole_cards) && player.hole_cards.length === 2 && player.hole_cards.every(code => code && code !== "??");
  }

  function primaryWinnerIds() {
    const firstPot = Array.isArray(game?.result_details) ? game.result_details.find(row => Array.isArray(row?.winners) && row.winners.length) : null;
    return firstPot?.winners || game?.winners || [];
  }

  function strongestPlayer(ids) {
    let best = null;
    for (const id of ids) {
      const player = game?.players?.[id];
      if (!player || !hasVisibleCards(player)) continue;
      const score = scoreHand(player.hole_cards, game.board);
      if (!score) continue;
      if (!best || compareScore(score,best.score) > 0) best = { player, score };
    }
    return best;
  }

  function showdownComparison() {
    if (!game?.terminal || !Array.isArray(game.board) || game.board.length !== 5) return null;
    const viewer = typeof localViewerPlayer === "function" ? localViewerPlayer() : null;
    if (!viewer || viewer.folded || !hasVisibleCards(viewer)) return null;

    const winners = primaryWinnerIds();
    if (!winners.length) return null;

    const viewerScore = scoreHand(viewer.hole_cards, game.board);
    if (!viewerScore) return null;

    const viewerWonPrimary = winners.includes(viewer.id);
    let outcome = "loss";
    let opponentInfo = null;

    if (viewerWonPrimary) {
      if (winners.length > 1) {
        outcome = "tie";
        opponentInfo = strongestPlayer(winners.filter(id => id !== viewer.id));
      } else {
        outcome = "win";
        const others = (game.seat_order || []).filter(id => id !== viewer.id && !game.players?.[id]?.folded);
        opponentInfo = strongestPlayer(others);
      }
    } else {
      outcome = "loss";
      opponentInfo = strongestPlayer(winners);
    }

    if (!opponentInfo) return null;
    return {
      outcome,
      viewer,
      viewerScore,
      opponent: opponentInfo.player,
      opponentScore: opponentInfo.score,
      amount: Number(game.result_details?.[0]?.amount || 0),
    };
  }

  function miniCards(cards) {
    return (cards || []).map(code => {
      const rank = code?.[0] === "T" ? "10" : (code?.[0] || "?");
      const suit = code?.[1];
      const symbol = {s:"♠",h:"♥",d:"♦",c:"♣"}[suit] || "";
      const red = suit === "h" || suit === "d";
      return `<span class="v025-mini-card${red ? " red" : ""}"><b>${rank}</b><i>${symbol}</i></span>`;
    }).join("");
  }

  function reasonText(info) {
    if (info.outcome === "tie") return "комбинации равны — банк делится";
    const viewerClass = CLASS_NAMES[info.viewerScore[0]];
    const opponentClass = CLASS_NAMES[info.opponentScore[0]];
    if (info.viewerScore[0] !== info.opponentScore[0]) {
      const stronger = info.outcome === "win" ? viewerClass : opponentClass;
      const weaker = info.outcome === "win" ? opponentClass : viewerClass;
      return `${stronger} старше, чем ${weaker}`;
    }
    return `одинаковый тип комбинации — решают старшие карты и кикеры`;
  }

  function modalNode() {
    let modal = document.getElementById("v025ShowdownModal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "v025ShowdownModal";
    modal.className = "v025-showdown-modal";
    modal.hidden = true;
    modal.innerHTML = `<section><button class="v025-close" type="button" aria-label="Закрыть">×</button><div class="v025-body"></div></section>`;
    document.body.appendChild(modal);
    modal.querySelector(".v025-close")?.addEventListener("click", () => {
      dismissedHand = game?.hand_id || dismissedHand;
      modal.hidden = true;
    });
    return modal;
  }

  function renderComparisonModal() {
    const modal = modalNode();
    if (!game?.terminal) {
      modal.hidden = true;
      return;
    }
    if (dismissedHand === game.hand_id) return;

    const info = showdownComparison();
    if (!info) {
      modal.hidden = true;
      return;
    }

    const title = info.outcome === "win" ? "ПОБЕДА" : info.outcome === "tie" ? "ДЕЛЁЖ" : "ПОРАЖЕНИЕ";
    const subtitle = info.outcome === "win" ? "ваша комбинация сильнее" : info.outcome === "tie" ? "одинаковая сила руки" : `${info.opponent.name} выигрывает`;
    const body = modal.querySelector(".v025-body");
    body.innerHTML = `
      <div class="v025-head ${info.outcome}">
        <strong>${title}</strong>
        <span>${escapeHtml(subtitle)}${info.amount > 0 ? ` · ${formatBB(info.amount)}` : ""}</span>
      </div>
      <div class="v025-compare-row winner">
        <div class="v025-who"><small>${info.outcome === "win" ? "СОПЕРНИК" : "ПОБЕДИТЕЛЬ"}</small><b>${escapeHtml(info.opponent.name)}</b></div>
        <div class="v025-cards">${miniCards(info.opponent.hole_cards)}</div>
        <div class="v025-hand">${escapeHtml(describeScore(info.opponentScore))}</div>
      </div>
      <div class="v025-versus">VS</div>
      <div class="v025-compare-row viewer">
        <div class="v025-who"><small>ВЫ</small><b>${escapeHtml(info.viewer.name || "Вы")}</b></div>
        <div class="v025-cards">${miniCards(info.viewer.hole_cards)}</div>
        <div class="v025-hand">${escapeHtml(describeScore(info.viewerScore))}</div>
      </div>
      <div class="v025-reason">${escapeHtml(reasonText(info))}</div>
    `;
    modal.hidden = false;
  }

  function syncShowdownLayout() {
    const active = Boolean(game?.terminal && Array.isArray(game.board) && game.board.length === 5);
    document.body.classList.toggle("v025-showdown-layout", active);
    if (!active) {
      const modal = document.getElementById("v025ShowdownModal");
      if (modal) modal.hidden = true;
    }
  }

  const originalAnimateShowdownReveal = animateShowdownReveal;
  animateShowdownReveal = async function animateShowdownRevealV025(previousState, nextState) {
    if (nextState?.terminal && nextState?.board?.length === 5) document.body.classList.add("v025-showdown-layout");
    return originalAnimateShowdownReveal(previousState, nextState);
  };

  const originalRenderGame = renderGame;
  renderGame = function renderGameV025() {
    originalRenderGame();
    syncShowdownLayout();
    renderComparisonModal();
  };

  const style = document.createElement("style");
  style.id = "v025-showdown-compare-style";
  style.textContent = `
    @media (max-width:780px){
      /* Keep the five-card board as a protected center lane during showdown. */
      body.v014.v025-showdown-layout .seat[data-visual-seat="2"]{left:4.5% !important;}
      body.v014.v025-showdown-layout .seat[data-visual-seat="5"]{left:95.5% !important;}
      body.v014.v025-showdown-layout .seat[data-visual-seat="2"] .player-cards .card,
      body.v014.v025-showdown-layout .seat[data-visual-seat="5"] .player-cards .card{
        width:31px !important;
        height:43px !important;
        font-size:12px !important;
      }

      .v025-showdown-modal{
        position:fixed;
        top:58px;
        left:50%;
        z-index:4600;
        width:min(374px,calc(100vw - 18px));
        transform:translateX(-50%);
        pointer-events:none;
      }
      .v025-showdown-modal[hidden]{display:none !important;}
      .v025-showdown-modal>section{
        position:relative;
        pointer-events:auto;
        padding:10px 11px 11px;
        border:1px solid rgba(94,184,255,.48);
        border-radius:17px;
        background:linear-gradient(180deg,rgba(3,12,29,.985),rgba(2,7,20,.995));
        box-shadow:0 16px 42px rgba(0,0,0,.52),0 0 22px rgba(73,163,255,.12),inset 0 0 22px rgba(82,143,255,.04);
        backdrop-filter:blur(10px);
      }
      .v025-close{
        position:absolute;
        top:7px;
        right:8px;
        width:27px;
        height:27px;
        border:0;
        border-radius:9px;
        background:rgba(255,255,255,.055);
        color:#9db0c9;
        font-size:19px;
        line-height:1;
      }
      .v025-head{padding:0 34px 8px 1px;border-bottom:1px solid rgba(96,133,190,.18);}
      .v025-head strong{display:block;font-size:14px;line-height:1;font-weight:950;letter-spacing:.08em;}
      .v025-head span{display:block;margin-top:4px;color:#94a7c2;font-size:9px;font-weight:750;}
      .v025-head.win strong{color:#78f0bb;}
      .v025-head.loss strong{color:#ff91a8;}
      .v025-head.tie strong{color:#ffd37c;}

      .v025-compare-row{
        display:grid;
        grid-template-columns:76px 61px minmax(0,1fr);
        align-items:center;
        gap:7px;
        min-height:46px;
        padding:7px 1px;
      }
      .v025-who small{display:block;color:#6f84a3;font-size:7px;font-weight:900;letter-spacing:.12em;}
      .v025-who b{display:block;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#eef5ff;font-size:10px;}
      .v025-cards{display:flex;gap:3px;}
      .v025-mini-card{
        width:27px;
        height:36px;
        display:grid;
        place-items:center;
        align-content:center;
        border-radius:5px;
        border:1px solid rgba(0,0,0,.17);
        background:linear-gradient(160deg,#fff,#e7edf2);
        color:#111820;
        box-shadow:0 3px 8px rgba(0,0,0,.28);
        line-height:.8;
      }
      .v025-mini-card.red{color:#ce3245;}
      .v025-mini-card b{font-size:10px;}
      .v025-mini-card i{font-size:11px;font-style:normal;}
      .v025-hand{color:#dbe6f5;font-size:9px;font-weight:800;line-height:1.25;}
      .v025-versus{
        height:1px;
        position:relative;
        background:linear-gradient(90deg,transparent,rgba(100,137,192,.26),transparent);
        color:#66809f;
        font-size:7px;
        font-weight:950;
        text-align:center;
      }
      .v025-versus::after{content:"VS";position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);padding:0 6px;background:#030b1d;}
      .v025-reason{
        margin-top:2px;
        padding:6px 8px;
        border-radius:8px;
        background:rgba(62,94,145,.10);
        color:#9fb2cc;
        font-size:8px;
        font-weight:750;
        text-align:center;
      }
    }
  `;
  document.head.appendChild(style);
})();
