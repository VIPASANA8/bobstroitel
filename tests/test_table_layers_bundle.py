"""static/table-layers.js is generated: it must be exactly what its sources
say, or an edit to a v0xx layer silently never reaches the table."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bundle_table_layers  # noqa: E402


def test_the_bundle_is_built_from_the_current_layers():
    built = bundle_table_layers.build()
    served = bundle_table_layers.OUTPUT.read_text(encoding="utf-8")
    assert served == built, "run: python tools/bundle_table_layers.py"


def test_the_bundle_runs_every_layer_in_loader_order_and_plants_every_marker():
    served = bundle_table_layers.OUTPUT.read_text(encoding="utf-8")
    positions = [served.index(f"/* ==== {name} ==== */") for name in bundle_table_layers.LAYERS]
    assert positions == sorted(positions)
    for marker in bundle_table_layers.MARKERS:
        assert f'"{marker}"' in served
        # ...and something actually looks for it, else the marker is dead weight.
        assert any(marker in (bundle_table_layers.STATIC / name).read_text(encoding="utf-8")
                   for name in ("component-ui.js", *bundle_table_layers.LAYERS)), marker
    # Between two layers "})()" + "(() => {" is a call; the bundler guards it.
    assert "})()\n\n/* ====" not in served


def test_the_page_loads_the_bundle_once_and_no_layer_on_its_own():
    component = (ROOT / "static" / "component-ui.js").read_text(encoding="utf-8")
    assert "table-layers.js?v=" in component
    assert "v016-fixes.js" not in component
    index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "table-layers.js" not in index, "component-ui appends it after DOMContentLoaded, as the chain was"
