from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


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
    if not args.manifest:
        print(json.dumps({"status": "error", "reason": "--manifest is required"}))
        return 2
    sessions = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    sessions = sessions.get("sessions", sessions) if isinstance(sessions, (dict, list)) else []
    if len(sessions) < args.connections:
        print(json.dumps({"status": "error", "reason": "manifest has fewer sessions than connections"}))
        return 2
    table_ids = {entry["table_id"] for entry in sessions[:args.connections]}
    if len(table_ids) < args.tables:
        print(json.dumps({"status": "error", "reason": "manifest has fewer tables than requested"}))
        return 2

    parsed = urlparse(args.base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_base = f"{scheme}://{parsed.netloc}"
    latencies: list[float] = []
    connect_latencies: list[float] = []
    failures = 0
    disconnects = 0
    stale_revisions = 0
    message_counts: Counter[str] = Counter()
    duplicate_command_results = 0
    seen_command_ids: set[str] = set()
    lock = asyncio.Lock()

    async def one(index: int, entry: dict) -> None:
        nonlocal failures, disconnects, stale_revisions, duplicate_command_results
        uri = f"{ws_base}/ws/tables/{entry['table_id']}"
        started = time.perf_counter()
        try:
            async with connect(uri, additional_headers={"Cookie": entry["cookie"]}, open_timeout=10, ping_interval=None) as socket:
                await socket.recv()
                async with lock:
                    connect_latencies.append((time.perf_counter() - started) * 1000)
                deadline = time.monotonic() + args.duration
                sequence = 0
                while time.monotonic() < deadline:
                    sequence += 1
                    sent_at = time.perf_counter()
                    await socket.send(json.dumps({"type": "ping", "sent_at": sequence}))
                    response = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))
                    async with lock:
                        latencies.append((time.perf_counter() - sent_at) * 1000)
                        message_counts[response.get("type", "unknown")] += 1
                        command_id = response.get("command_id")
                        if command_id:
                            if command_id in seen_command_ids:
                                duplicate_command_results += 1
                            seen_command_ids.add(command_id)
                    if response.get("type") == "snapshot" and response.get("reason") == "stale_revision":
                        stale_revisions += 1
                    if sequence % 10 == 0:
                        await socket.send(json.dumps({"type": "resync", "revision": 0}))
                        response = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))
                        async with lock:
                            message_counts[response.get("type", "unknown")] += 1
                            command_id = response.get("command_id")
                            if command_id:
                                if command_id in seen_command_ids:
                                    duplicate_command_results += 1
                                seen_command_ids.add(command_id)
                    await asyncio.sleep(1)
        except (ConnectionClosed, OSError, TimeoutError, asyncio.TimeoutError, ValueError, KeyError):
            if time.monotonic() < deadline if "deadline" in locals() else True:
                async with lock:
                    failures += 1
            else:
                async with lock:
                    disconnects += 1

    await asyncio.gather(*(one(index, entry) for index, entry in enumerate(sessions[:args.connections])))
    total = args.connections
    sorted_latencies = sorted(latencies)
    sorted_connect_latencies = sorted(connect_latencies)
    p50 = statistics.median(sorted_latencies) if sorted_latencies else None
    p95 = sorted_latencies[max(0, int(len(sorted_latencies) * 0.95) - 1)] if sorted_latencies else None
    connect_p50 = statistics.median(sorted_connect_latencies) if sorted_connect_latencies else None
    connect_p95 = sorted_connect_latencies[max(0, int(len(sorted_connect_latencies) * 0.95) - 1)] if sorted_connect_latencies else None
    failure_rate = failures / total
    payload = {
        "status": "pass" if failure_rate <= 0.01 and (p95 is None or p95 <= 500) and duplicate_command_results == 0 else "fail",
        "connections": total, "tables": len(table_ids), "duration_seconds": args.duration,
        "connect_failures": failures, "unexpected_disconnects": disconnects,
        "failure_rate": failure_rate, "event_count": len(latencies), "p50_ms": p50, "p95_ms": p95,
        "connect_p50_ms": connect_p50, "connect_p95_ms": connect_p95,
        "stale_revisions": stale_revisions, "duplicate_command_results": duplicate_command_results,
        "message_types": dict(message_counts),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
