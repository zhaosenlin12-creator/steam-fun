from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from steamfun_mirror.course_archive import archive_course_material  # noqa: E402
from steamfun_mirror.course_audit import build_course_offline_report  # noqa: E402
from steamfun_mirror.storage import MirrorStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-archive incomplete iSpring course materials.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root path.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap on number of materials to re-archive. 0 means no limit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = MirrorStore(args.root)
    report = build_course_offline_report(store)
    material_ids = [int(item["material_id"]) for item in report["materials"] if item.get("status") == "missing_resource"]
    if args.limit > 0:
        material_ids = material_ids[: args.limit]

    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for material_id in material_ids:
        try:
            archived = archive_course_material(store, material_id)
        except Exception as exc:
            failures.append({"material_id": material_id, "error": str(exc)})
            continue
        results.append(
            {
                "material_id": material_id,
                "fetched_asset_count": int(archived.get("fetched_asset_count") or 0),
                "missing_asset_count": int(archived.get("missing_asset_count") or 0),
            }
        )

    print(
        json.dumps(
            {
                "requested_material_count": len(material_ids),
                "archived_material_count": len(results),
                "failed_material_count": len(failures),
                "materials": results[:50],
                "sample_failures": failures[:20],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
