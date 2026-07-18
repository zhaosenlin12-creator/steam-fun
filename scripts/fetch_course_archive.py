from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from steamfun_mirror.course_archive import archive_course_material  # noqa: E402
from steamfun_mirror.storage import MirrorStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive recursive curriculum material course assets.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root path.")
    parser.add_argument(
        "--material-id",
        type=int,
        action="append",
        dest="material_ids",
        help="Curriculum material id to archive. Can be repeated.",
    )
    return parser.parse_args()


def _material_ids(store: MirrorStore, explicit_ids: list[int] | None) -> list[int]:
    if explicit_ids:
        return explicit_ids
    material_ids: list[int] = []
    for snapshot in store.list_local_curriculum_material_snapshots():
        material_id = snapshot.get("id")
        if isinstance(material_id, int):
            material_ids.append(material_id)
    return material_ids


def main() -> None:
    args = parse_args()
    store = MirrorStore(args.root)
    material_ids = _material_ids(store, args.material_ids)

    reports: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    total_fetched_assets = 0
    total_missing_assets = 0

    for material_id in material_ids:
        try:
            report = archive_course_material(store, material_id)
        except Exception as exc:
            failures.append({"material_id": material_id, "error": str(exc)})
            continue
        reports.append(report)
        total_fetched_assets += int(report.get("fetched_asset_count") or 0)
        total_missing_assets += int(report.get("missing_asset_count") or 0)

    summary = {
        "requested_material_count": len(material_ids),
        "archived_material_count": len(reports),
        "failed_material_count": len(failures),
        "total_fetched_assets": total_fetched_assets,
        "total_missing_assets": total_missing_assets,
        "materials": reports,
        "sample_failures": failures[:20],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
