"""The acceptance server without the two-bot fixture.

`server.py` narrows the roster to system-01/02 so a hand plays out the same
way every run. Spectator layouts need the opposite: enough bots for the
lobby to seed its real 4-, 5- and 6-player rooms, which is what the seat
geometry is being measured at.
"""

from __future__ import annotations

import os

from app.online import create_app
from online.config import Settings

app = create_app(Settings.from_mapping(os.environ))
