import argparse
import asyncio
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(args.app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
