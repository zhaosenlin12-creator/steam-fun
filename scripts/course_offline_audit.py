from __future__ import annotations

import argparse
import json
from pathlib import Path

from steamfun_mirror.course_audit import build_course_offline_report
from steamfun_mirror.storage import MirrorStore


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit offline readiness of localized course materials.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=ROOT / "runtime" / "course_offline_report.json")
    args = parser.parse_args()

    store = MirrorStore(args.root)
    report = build_course_offline_report(store)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
