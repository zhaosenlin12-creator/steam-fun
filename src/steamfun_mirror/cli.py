from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .capture import MirrorCapture
from .server import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="steam.fun local mirror")
    parser.add_argument("--root", default=".", help="Project root directory.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Capture discovery, auth, routes, and APIs.")
    capture_parser.add_argument("--teacher-username", required=True)
    capture_parser.add_argument("--teacher-password", required=True)
    capture_parser.add_argument("--student-username", required=True)
    capture_parser.add_argument("--student-password", required=True)
    capture_parser.add_argument("--route-limit", type=int, default=None)
    capture_parser.add_argument("--visible", action="store_true", help="Run the browser in visible mode.")

    serve_parser = subparsers.add_parser("serve", help="Start the local replay server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--no-live-proxy", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.command == "capture":
        capture = MirrorCapture(root)
        summary = capture.capture(
            teacher_username=args.teacher_username,
            teacher_password=args.teacher_password,
            student_username=args.student_username,
            student_password=args.student_password,
            route_limit=args.route_limit,
            headless=not args.visible,
        )
        print(summary)
        return

    if args.command == "serve":
        app = create_app(root, allow_live_proxy=not args.no_live_proxy)
        uvicorn.run(app, host=args.host, port=args.port)
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
