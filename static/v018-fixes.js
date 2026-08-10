(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v018-mobile-space-pass";
  style.textContent = `
    @media (max-width:780px){
      /* Remove the persistent auto-action info bar and give that height back to the table. */
      body.v014{
        --table-stage-h:clamp(540px,calc(100dvh - 300px),590px) !important;
      }

      body.v014 #mobileAutoActionBar,
      body.v014 .mobile-auto-action{
        display:none !important;
      }

      /* Controls now begin lower because the table owns more of the viewport. */
      body.v014 .action-panel,
      body.v014.local-player-active .sidebar .action-panel,
      body.v014.human-turn .sidebar .action-panel{
        padding-bottom:calc(8px + env(safe-area-inset-bottom)) !important;
      }
    }

    @media (max-width:370px){
      body.v014{
        --table-stage-h:clamp(510px,calc(100dvh - 292px),555px) !important;
      }
    }
  `;
  document.head.appendChild(style);
})();
