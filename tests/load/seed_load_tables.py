from __future__ import annotations

import os


def main() -> int:
    if os.environ.get("POKER8_ENV") != "test":
        raise SystemExit("refusing to seed load tables unless POKER8_ENV=test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
