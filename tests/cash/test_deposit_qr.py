"""The deposit QR is generated in the page, so nothing here can check it by
eye -- and a code that encodes the wrong address sends USDT nowhere.

The encoder was verified by decoding: 34 strings were rendered to canvas and
read back with jsQR, an independent implementation, covering both address
shapes, every version boundary (14/15, 26/27, 42/43, 62/63, 84/85, 106/107)
and the maximum payload. All 34 round-tripped. These goldens are the matrices
from that verified build, so a regression shows up as a changed hash rather
than as a code somebody notices at a wallet.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
QR_JS = ROOT / "static" / "qr.js"
PROFILE = (ROOT / "static" / "profile.html").read_text(encoding="utf-8")
CASHIER_JS = (ROOT / "static" / "cash-cashier.js").read_text(encoding="utf-8")

#: text -> (module count, sha256 prefix of the flattened matrix)
GOLDEN = {
    # cash/trc20.py MOCK_ADDRESS, the address the pilot actually hands out.
    "TMockPoker8C2C111111111111111111111": (29, "8bb593e69026c7f7966c4d9ddd581d69"),
    # A real TRON address, 34 characters.
    "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE": (29, "1d7f25a68b6a2aa9885c7eba097835c6"),
}

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="needs node to run the encoder")


def _encode(texts):
    """Run the shipped encoder under node and hash what it produces."""
    script = """
      global.window = {};
      require(process.argv[1]);
      const QR = global.window.Poker8QR;
      const out = {};
      for (const text of JSON.parse(process.argv[2])) {
        const grid = QR.matrix(text);
        out[text] = grid && {
          modules: grid.length,
          flat: grid.map(row => row.map(cell => (cell ? "1" : "0")).join("")).join(""),
        };
      }
      process.stdout.write(JSON.stringify(out));
    """
    done = subprocess.run(
        # json.dumps escapes non-ASCII, so the argument stays plain on the way
        # in; the way back is UTF-8 and must be told so, or Windows decodes it
        # with the console codepage and the keys come back mangled.
        [NODE, "-e", script, str(QR_JS), json.dumps(texts)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    return json.loads(done.stdout)


@needs_node
def test_the_encoder_still_draws_the_verified_codes():
    produced = _encode(list(GOLDEN))
    for text, (modules, digest) in GOLDEN.items():
        got = produced[text]
        assert got is not None, text
        assert got["modules"] == modules, text
        assert hashlib.sha256(got["flat"].encode()).hexdigest()[:32] == digest, text


@needs_node
def test_it_refuses_what_it_cannot_encode_instead_of_guessing():
    """Version 6 at level M holds 106 bytes, and byte mode is Latin-1 without
    an ECI header we do not emit. Both cases return nothing, and the panel
    falls back to the address in text -- which is still payable."""
    produced = _encode(["y" * 106, "y" * 107, "адрес"])
    assert produced["y" * 106] is not None
    assert produced["y" * 107] is None
    assert produced["адрес"] is None


def test_the_code_is_inline_and_fetches_nothing():
    """An artifact-style page cannot reach a CDN, which is why this exists at
    all instead of a library."""
    source = QR_JS.read_text(encoding="utf-8")
    for reached_out in ("http://", "https://cdn", "import(", "fetch("):
        assert reached_out not in source.replace('"http://www.w3.org/2000/svg"', ""), reached_out


def test_the_panel_shows_the_code_for_the_address_it_prints():
    assert '/static/qr.js?v=' in PROFILE
    assert "window.Poker8QR?.svg(payload.address" in CASHIER_JS
    # The white ground and quiet zone travel with the code: the panel behind it
    # is nearly black, and a scanner needs both.
    assert 'fill="#ffffff"' in QR_JS.read_text(encoding="utf-8")
