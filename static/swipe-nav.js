(function () {
  'use strict';

  const interactive = 'a, button, input, select, textarea, canvas, [role="button"], [contenteditable]:not([contenteditable="false"])';

  window.Poker8SwipeNav = function (target, direction, destination) {
    let start = null;

    target.addEventListener('pointerdown', function (event) {
      start = null;
      if (event.pointerType !== 'touch' || event.target.closest(interactive)) return;
      start = {id: event.pointerId, x: event.clientX, y: event.clientY};
    });

    target.addEventListener('pointercancel', function (event) {
      if (start && event.pointerId === start.id) start = null;
    });

    target.addEventListener('pointerup', function (event) {
      if (!start || event.pointerId !== start.id) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      start = null;
      if (Math.abs(dx) < 72 || Math.abs(dx) <= Math.abs(dy) * 1.4) return;
      if ((direction === 'left' && dx < 0) || (direction === 'right' && dx > 0)) {
        window.location.href = destination;
      }
    });
  };
}());
