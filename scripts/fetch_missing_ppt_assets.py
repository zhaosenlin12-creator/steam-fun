from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from steamfun_mirror.discovery import extract_referenced_urls  # noqa: E402
from steamfun_mirror.server import _fetch_static_asset  # noqa: E402
from steamfun_mirror.storage import MirrorStore  # noqa: E402


DEFAULT_LESSON_IDS = [58951, 7858, 14592, 14672, 7577, 14593]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch missing PPT assets for specific lessons.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root path.")
    parser.add_argument(
        "--lesson-id",
        type=int,
        action="append",
        dest="lesson_ids",
        help="Specific curriculum material id to repair. Can be repeated.",
    )
    return parser.parse_args()


def _store_asset(store: MirrorStore, live_url: str) -> tuple[bool, str]:
    existing = store.lookup_asset(live_url)
    if existing is not None and existing.get("body"):
        return False, "already_present"

    response = _fetch_static_asset(live_url)
    if response is None:
        return False, "fetch_failed"

    with response:
        headers = dict(response.headers)
        body = b"".join(chunk for chunk in response.iter_content(chunk_size=1024 * 256) if chunk)

    if not body:
        return False, "empty_body"

    store.store_external_asset_stream(live_url, [body], status=200, headers=headers)
    return True, headers.get("content-type", "")


def _mirror_ppt_tree(store: MirrorStore, ppt_url: str) -> tuple[list[dict], list[dict]]:
    queue: deque[str] = deque([ppt_url])
    seen: set[str] = set()
    fetched: list[dict] = []
    failed: list[dict] = []

    while queue:
        live_url = queue.popleft()
        if live_url in seen:
            continue
        seen.add(live_url)

        stored, meta = _store_asset(store, live_url)
        if meta in {"fetch_failed", "empty_body"}:
            failed.append({"url": live_url, "reason": meta})
            continue

        if stored:
            fetched.append({"url": live_url, "content_type": meta})

        asset = store.lookup_asset(live_url)
        body = asset.get("body") if isinstance(asset, dict) else b""
        content_type = str((asset or {}).get("content_type") or meta or "")
        if not body or "html" not in content_type.lower() and "javascript" not in content_type.lower() and "css" not in content_type.lower():
            continue
        try:
            text = body.decode("utf-8", errors="ignore")
        except Exception:
            continue

        for ref_url in extract_referenced_urls(live_url, text):
            if "wugecdn.steam.fun" not in ref_url:
                continue
            if ref_url not in seen:
                queue.append(ref_url)

    return fetched, failed


def main() -> None:
    args = parse_args()
    store = MirrorStore(args.root)
    lesson_ids = args.lesson_ids or DEFAULT_LESSON_IDS
    fetched = []
    failed = []

    for lesson_id in lesson_ids:
        material = store.find_curriculum_material(lesson_id) or {}
        ppt_url = str(material.get("ppt_url") or "").strip()
        if not ppt_url:
            failed.append({"lesson_id": lesson_id, "reason": "missing_ppt_url"})
            continue

        lesson_fetched, lesson_failed = _mirror_ppt_tree(store, ppt_url)
        fetched.extend({"lesson_id": lesson_id, **item} for item in lesson_fetched)
        failed.extend({"lesson_id": lesson_id, **item} for item in lesson_failed)

    print({"fetched": len(fetched), "failed": len(failed), "fetched_items": fetched, "failed_items": failed})


if __name__ == "__main__":
    main()
