(function () {
  'use strict';

  const interactive = 'a, button, input, select, textarea, canvas, label, summary, dialog[open], [role="button"], [contenteditable]:not([contenteditable="false"])';

  window.Poker8SwipeNav = function (target, direction, destination, enabled) {
    let start = null;

    target.addEventListener('touchstart', function (event) {
      start = null;
      if ((enabled && !enabled()) || event.touches.length !== 1 || event.target.closest(interactive)) return;
      const touch = event.changedTouches[0];
      start = {id: touch.identifier, x: touch.clientX, y: touch.clientY};
    }, {passive: true});

    target.addEventListener('touchcancel', function () {
      start = null;
    }, {passive: true});

    target.addEventListener('touchend', function (event) {
      if (!start) return;
      const touch = Array.from(event.changedTouches).find(item => item.identifier === start.id);
      if (!touch) return;
      const dx = touch.clientX - start.x;
      const dy = touch.clientY - start.y;
      start = null;
      if ((enabled && !enabled()) || event.touches.length) return;
      if (Math.abs(dx) < 72 || Math.abs(dx) <= Math.abs(dy) * 1.4) return;
      if ((direction === 'left' && dx < 0) || (direction === 'right' && dx > 0)) {
        window.location.href = destination;
      }
    }, {passive: true});
  };
}());
