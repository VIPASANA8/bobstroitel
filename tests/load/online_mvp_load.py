from __future__ import annotations

import argparse
import asyncio


def parse_args():
    parser = argparse.ArgumentParser(description="Poker8 online WebSocket load probe")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--connections", type=int, default=100)
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--manifest")
    return parser.parse_args()


async def run(args) -> int:
    if args.connections < 1 or args.tables < 1:
        return 2
    print({"base_url": args.base_url, "connections": args.connections, "tables": args.tables, "duration": args.duration, "status": "probe-ready"})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
