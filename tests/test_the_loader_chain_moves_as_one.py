"""Every layer the page actually asks for has to carry the same cache-bust.

Found by sweeping the served URLs rather than the served files: the chain
had drifted into three different slugs at once. online-table.js and v041
were still requested as `?v=mobile-layout-prod-15` and v040 as
`?v=seat-levels-2`, while index.html had been bumped several times past
both. The files on the server were current -- fetching them by hand proved
that -- but the page was asking for them under URLs that had not changed in
many deploys, so any browser holding a cached copy kept serving the old
one. That is invisible to a `curl` of the file and to every test that reads
the file from disk, which is why it survived so long.
"""

import re
from pathlib import Path

STATIC = Path("static")
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
COMPONENT_UI = (STATIC / "component-ui.js").read_text(encoding="utf-8")
V037 = (STATIC / "v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")

#: Each link in the chain: (source, the file it pulls in).
CHAIN = [
    (INDEX, "component-ui.js"),
    (INDEX, "online-table.js"),
    (COMPONENT_UI, "v037-poker8-v2-reference-table.js"),
    (V037, "v038-poker8-v2-cinematic-table.js"),
    (V037, "v040-poker8-v2-dynamic-seats.js"),
    (V037, "v041-poker8-v2-turn-clarity.js"),
]


def _slugs(source, filename):
    found = re.findall(re.escape(filename) + r"\?v=([A-Za-z0-9._-]+)", source)
    assert found, f"{filename} is pulled in without any ?v= at all"
    return set(found)


def test_every_link_in_the_chain_carries_the_same_cache_bust():
    seen = {}
    for source, filename in CHAIN:
        for slug in _slugs(source, filename):
            seen.setdefault(slug, []).append(filename)
    assert len(seen) == 1, f"the chain is split across {len(seen)} slugs: {seen}"


def test_the_layers_that_draw_the_table_are_versioned_at_all():
    """An unversioned src is cached by the browser for good; these five are
    the ones that change."""
    for source, filename in CHAIN:
        assert f'{filename}"' not in source, f"{filename} is loaded with no ?v="


def test_the_table_page_asks_for_one_cache_bust_and_no_more():
    """Per-file slugs are what let three of them sit many deploys apart while
    each looked deliberate. One value for everything index.html pulls in
    costs a single extra fetch on a deploy and removes the whole class."""
    slugs = set(re.findall(r"/static/[A-Za-z0-9._-]+\.(?:js|css)\?v=([A-Za-z0-9._-]+)", INDEX))
    assert len(slugs) == 1, f"index.html asks for {len(slugs)} different slugs: {sorted(slugs)}"
    chain_slug = next(iter(_slugs(INDEX, "component-ui.js")))
    assert slugs == {chain_slug}, "the page and the chain it loads must agree"
