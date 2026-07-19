from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the current worktree preview.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8019)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))

    from steamfun_mirror.server import create_app

    app = create_app(root, allow_live_proxy=False)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
