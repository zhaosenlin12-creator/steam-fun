from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from steamfun_mirror.course_snapshot import import_captured_course_domain  # noqa: E402
from steamfun_mirror.storage import MirrorStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import captured course-domain data into local snapshot tables.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = MirrorStore(args.root)
    summary = import_captured_course_domain(store)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
