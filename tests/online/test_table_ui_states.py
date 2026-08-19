from pathlib import Path


def test_table_contains_online_state_surfaces():
    html = Path("static/index.html").read_text(encoding="utf-8")
    for element_id in ("readyPanel", "queueStatus", "connectionStatus", "chatPanel", "newHandCountdown"):
        assert f'id="{element_id}"' in html


def test_system_player_has_no_large_ai_badge():
    script = Path("static/app.js").read_text(encoding="utf-8")
    assert 'seatAvatar.textContent = "AI"' not in script


def test_viewer_state_is_reconciled_from_every_snapshot():
    """viewerState gates the entire action panel through p8-observer-mode, but
    it only advances on the REST refresh, whose failures the poll swallows. The
    socket delivers a per-viewer snapshot carrying viewer_player_id, so a
    seated player must never stay stuck in observer mode waiting for a refresh
    that may never succeed."""
    script = Path("static/online-table.js").read_text(encoding="utf-8")

    assert "function reconcileViewerState(state)" in script
    # Runs on every snapshot, not just the REST one.
    assert "reconcileViewerState(state);" in script
    reconcile_at = script.index("function reconcileViewerState(state)")
    render_at = script.index("function renderSnapshot(state)")
    call_at = script.index("reconcileViewerState(state);", render_at)
    chrome_at = script.index("renderOnlineChrome(state);", render_at)
    # The observer-mode class is derived in renderOnlineChrome, so the
    # reconciliation has to land before it, not after.
    assert reconcile_at < render_at < call_at < chrome_at


def test_taking_a_seat_explains_a_refusal_instead_of_silently_bouncing():
    """One seat per player across the network. The refusal used to be caught
    and dropped, so pressing "Занять место" while seated elsewhere changed
    nothing at all -- no label change, no message, no state -- which reads as a
    broken button. The server names the blocking table; use it."""
    source = Path("static/online-table.js").read_text(encoding="utf-8")

    assert 'detail?.code === "already_seated"' in source
    # Matched on the structured code, not on a substring of a Russian sentence.
    assert 'includes("already has a network seat")' not in source
    # A different table has to be surfaced and offered, not swallowed.
    assert "detail.table_id !== tableId" in source
    assert "window.confirm(" in source
    assert "location.href = `/table?table=${encodeURIComponent(detail.table_id)}`" in source
