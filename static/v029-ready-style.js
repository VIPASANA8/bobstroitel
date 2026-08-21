(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v029-ready-style";
  style.textContent = `
    @media (max-width:780px){
      /* Cleaner status: indicator, not a second button. */
      body.v014 .v028-center-ready{
        width:190px !important;
        gap:12px !important;
      }

      body.v014 .v028-center-status{
        position:relative !important;
        min-width:0 !important;
        width:auto !important;
        height:25px !important;
        padding:0 6px 0 20px !important;
        border:0 !important;
        border-radius:0 !important;
        background:transparent !important;
        box-shadow:none !important;
        color:#ffbd65 !important;
        font-size:10px !important;
        font-weight:950 !important;
        letter-spacing:.08em !important;
        text-shadow:0 0 10px rgba(255,163,65,.18) !important;
      }

      body.v014 .v028-center-status::after{
        content:"";
        position:absolute;
        left:20px;
        right:6px;
        bottom:0;
        height:1px;
        background:linear-gradient(90deg,rgba(255,163,65,.75),rgba(255,163,65,0));
        opacity:.75;
      }

      body.v014 .v028-center-status i{
        position:absolute !important;
        left:4px !important;
        top:50% !important;
        width:7px !important;
        height:7px !important;
        transform:translateY(-50%) !important;
        background:#ffab43 !important;
        box-shadow:0 0 11px rgba(255,171,67,.72) !important;
      }

      body.v014 .v028-center-status.ready{
        background:transparent !important;
        border:0 !important;
        color:#78ffc8 !important;
        box-shadow:none !important;
        text-shadow:0 0 10px rgba(81,239,174,.18) !important;
      }

      body.v014 .v028-center-status.ready::after{
        background:linear-gradient(90deg,rgba(71,230,168,.72),rgba(71,230,168,0));
      }

      body.v014 .v028-center-status.ready i{
        background:#5fedaa !important;
        box-shadow:0 0 11px rgba(95,237,170,.72) !important;
      }

      /* Main control: dark glass with a bright edge, more Poker8-like. */
      body.v014 .v028-center-ready-button{
        position:relative !important;
        width:172px !important;
        height:46px !important;
        overflow:hidden !important;
        border:1px solid rgba(47,207,255,.50) !important;
        border-radius:14px !important;
        background:linear-gradient(180deg,rgba(12,20,39,.96),rgba(8,13,26,.99)) !important;
        color:#eef4f8 !important;
        font-size:12px !important;
        font-weight:950 !important;
        letter-spacing:.075em !important;
        text-shadow:0 1px 3px rgba(0,0,0,.8) !important;
        box-shadow:0 9px 24px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.055),inset 0 0 20px rgba(42,154,255,.045) !important;
      }

      body.v014 .v028-center-ready-button::before{
        content:"";
        position:absolute;
        left:13px;
        right:13px;
        bottom:0;
        height:2px;
        border-radius:99px 99px 0 0;
        background:linear-gradient(90deg,#2fcfff,#8b62ff);
        box-shadow:0 0 10px rgba(75,191,255,.48);
      }

      body.v014 .v028-center-ready-button::after{
        content:"→";
        position:absolute;
        right:15px;
        top:50%;
        transform:translateY(-52%);
        color:#7bdcff;
        font-size:15px;
        font-weight:800;
        opacity:.9;
      }

      body.v014 .v028-center-ready-button.start{
        border-color:rgba(72,239,180,.55) !important;
        background:linear-gradient(180deg,rgba(7,39,35,.97),rgba(2,19,18,.99)) !important;
        color:#eafff6 !important;
        box-shadow:0 9px 24px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.055),inset 0 0 20px rgba(55,220,162,.045) !important;
      }

      body.v014 .v028-center-ready-button.start::before{
        background:linear-gradient(90deg,#3defb0,#34d6ff);
        box-shadow:0 0 10px rgba(61,235,190,.45);
      }

      body.v014 .v028-center-ready-button.start::after{
        content:"▶";
        color:#7ff0bf;
        font-size:12px;
      }

      body.v014 .v028-center-ready-button:not(:disabled):hover{
        border-color:rgba(85,219,255,.78) !important;
        box-shadow:0 0 17px rgba(53,191,255,.12),0 9px 24px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.065) !important;
      }

      body.v014 .v028-center-ready-button:not(:disabled):active{
        transform:translateY(1px) scale(.985) !important;
      }
    }
  `;
  document.head.appendChild(style);
})();
