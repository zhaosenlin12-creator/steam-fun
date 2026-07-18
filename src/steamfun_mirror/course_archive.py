from __future__ import annotations

import base64
import datetime as dt
import json
import re
import zlib
from collections import deque
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from .config import BASE_URL
from .discovery import extract_referenced_urls
from .rewrite import LOCAL_EXTERNAL_PREFIX
from .server import _fetch_static_asset
from .storage import MirrorStore


ROOT_URL_FIELDS = (
    "ppt_url",
    "stu_note_url",
    "teach_template_url",
    "home_template_url",
    "other_meterial_url",
    "video_url",
    "lession_plan_url",
    "train_video_url",
    "exampal_work_url",
)
TEXTUAL_CONTENT_MARKERS = ("json", "javascript", "ecmascript", "css", "html", "svg", "xml", "text")
TEXTUAL_SUFFIXES = {".css", ".htm", ".html", ".js", ".json", ".mjs", ".svg", ".txt", ".xml"}
PRESINFO_RE = re.compile(r'var presInfo = "([A-Za-z0-9+/=]+)"')


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _material_payload(store: MirrorStore, material_id: int) -> dict[str, Any]:
    local_snapshot = store.get_local_curriculum_material_snapshot(material_id)
    if isinstance(local_snapshot, dict):
        return local_snapshot
    material = store.find_curriculum_material(material_id)
    if isinstance(material, dict):
        return material
    raise ValueError(f"Curriculum material not found: {material_id}")


def _live_url_from_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        return text
    if text.startswith(f"{LOCAL_EXTERNAL_PREFIX}/"):
        suffix = text[len(LOCAL_EXTERNAL_PREFIX):].lstrip("/")
        host, separator, asset_path = suffix.partition("/")
        if not host:
            return None
        if not separator:
            return f"https://{host}"
        return f"https://{host}/{asset_path}"
    if text.startswith("/"):
        return urljoin(f"{BASE_URL}/", text)
    return None


def _root_urls(material: dict[str, Any]) -> list[str]:
    root_urls: list[str] = []
    seen: set[str] = set()
    for field in ROOT_URL_FIELDS:
        live_url = _live_url_from_value(material.get(field))
        if not live_url or live_url in seen:
            continue
        seen.add(live_url)
        root_urls.append(live_url)
    return root_urls


def _is_static_asset_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    path = parsed.path or ""
    if path.startswith("/api/") or path.startswith("/java-api/"):
        return False
    return True


def _within_course_scope(root_urls: list[str], candidate_url: str) -> bool:
    candidate = str(candidate_url or "").strip()
    if not candidate:
        return False
    parsed_candidate = urlparse(candidate)
    if parsed_candidate.scheme not in {"http", "https"}:
        return False

    for root_url in root_urls:
        parsed_root = urlparse(root_url)
        if parsed_root.scheme not in {"http", "https"}:
            continue
        if parsed_candidate.netloc != parsed_root.netloc:
            continue
        root_dir = parsed_root.path.rsplit("/", 1)[0].rstrip("/") + "/"
        if parsed_candidate.path.startswith(root_dir):
            return True
    return False


def _is_textual_asset(url: str, content_type: str) -> bool:
    normalized = content_type.lower()
    if any(marker in normalized for marker in TEXTUAL_CONTENT_MARKERS):
        return True
    return Path(urlparse(url).path).suffix.lower() in TEXTUAL_SUFFIXES


def _decode_text_body(body: bytes) -> str:
    return body.decode("utf-8", errors="ignore")


def _iter_ispring_presinfo_urls(base_url: str, text: str) -> Iterable[str]:
    match = PRESINFO_RE.search(text)
    if match is None:
        return []
    try:
        payload = zlib.decompress(base64.b64decode(match.group(1)))
        presinfo = json.loads(payload.decode("utf-8"))
    except Exception:
        return []

    discovered: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        candidate = str(candidate or "").strip()
        if not candidate:
            return
        if candidate.startswith("data.local-only/"):
            return
        if candidate.startswith(("data:", "blob:", "#", "javascript:")):
            return
        if "<" in candidate or ">" in candidate:
            return
        if "/" not in candidate and not Path(candidate).suffix:
            return
        resolved = urljoin(base_url, candidate)
        if resolved not in seen:
            seen.add(resolved)
            discovered.append(resolved)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"s", "c", "sl", "i", "u", "src", "poster"}:
                    if isinstance(value, str):
                        add(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                add(item)
                elif key == "h" and isinstance(value, str):
                    for ref_url in extract_referenced_urls(
                        base_url,
                        value,
                        include_absolute_urls=False,
                        include_html_attrs=True,
                    ):
                        if ref_url not in seen:
                            seen.add(ref_url)
                            discovered.append(ref_url)
                walk(value)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(presinfo)
    return discovered


def _iter_slide_markup_urls(base_url: str, text: str) -> Iterable[str]:
    for ref_url in extract_referenced_urls(
        base_url,
        text,
        include_absolute_urls=False,
        include_html_attrs=True,
    ):
        yield ref_url


def _asset_present(asset: dict[str, Any] | None, store: MirrorStore) -> bool:
    if not isinstance(asset, dict):
        return False
    local_path = str(asset.get("local_path") or "").strip()
    if not local_path:
        return bool(asset.get("body"))
    return (store.root / local_path).exists()


def _existing_asset_record(store: MirrorStore, asset_url: str) -> dict[str, Any] | None:
    asset = store.lookup_asset(asset_url)
    if not _asset_present(asset, store):
        return None
    return asset


def _store_fetched_asset(store: MirrorStore, asset_url: str, body: bytes, *, status: int, headers: dict[str, Any]) -> dict[str, Any]:
    store.store_external_asset_stream(asset_url, [body], status=status, headers=headers)
    stored = store.lookup_asset(asset_url)
    if stored is None:
        return {
            "url": asset_url,
            "local_path": "",
            "status": status,
            "content_type": str(headers.get("content-type") or ""),
            "body": body,
        }
    return stored


def _fetch_or_load_asset(store: MirrorStore, asset_url: str) -> tuple[dict[str, Any] | None, bool]:
    existing = _existing_asset_record(store, asset_url)
    if existing is not None:
        return existing, False

    response = _fetch_static_asset(asset_url)
    if response is None:
        return None, False

    with response:
        headers = dict(response.headers)
        body = b"".join(chunk for chunk in response.iter_content(chunk_size=1024 * 256) if chunk)
        stored = _store_fetched_asset(
            store,
            asset_url,
            body,
            status=int(getattr(response, "status_code", 200) or 200),
            headers=headers,
        )
    return stored, True


def _build_present_asset_row(material_id: int, asset_url: str, asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "material_id": material_id,
        "asset_url": asset_url,
        "local_path": str(asset.get("local_path") or ""),
        "status": int(asset.get("status") or 0),
        "content_type": str(asset.get("content_type") or ""),
        "required": True,
        "present": True,
    }


def _build_missing_asset_row(material_id: int, asset_url: str) -> dict[str, Any]:
    return {
        "material_id": material_id,
        "asset_url": asset_url,
        "local_path": "",
        "status": 0,
        "content_type": "",
        "required": True,
        "present": False,
    }


def archive_course_material(store: MirrorStore, material_id: int) -> dict[str, Any]:
    normalized_material_id = _coerce_int(material_id)
    if normalized_material_id is None:
        raise ValueError(f"Invalid curriculum material id: {material_id}")

    material = _material_payload(store, normalized_material_id)
    root_urls = _root_urls(material)
    queue: deque[tuple[str, str]] = deque((url, url) for url in root_urls)
    visited: set[str] = set()
    parsed_contexts: set[tuple[str, str]] = set()
    asset_rows_by_url: dict[str, dict[str, Any]] = {}
    missing_assets: list[dict[str, Any]] = []

    while queue:
        asset_url, parse_base_url = queue.popleft()
        if not _is_static_asset_url(asset_url):
            continue

        should_fetch = asset_url not in visited
        if should_fetch:
            visited.add(asset_url)

        asset, fetched_now = _fetch_or_load_asset(store, asset_url)
        if asset is None:
            if asset_url not in asset_rows_by_url:
                missing_row = _build_missing_asset_row(normalized_material_id, asset_url)
                asset_rows_by_url[asset_url] = missing_row
                missing_assets.append(
                    {
                        "asset_url": asset_url,
                        "required": True,
                        "present": False,
                        "status": 0,
                        "discovered_from": [],
                    }
                )
            continue

        present_row = _build_present_asset_row(normalized_material_id, asset_url, asset)
        asset_rows_by_url[asset_url] = present_row

        content_type = str(asset.get("content_type") or "")
        body = asset.get("body") if isinstance(asset.get("body"), bytes) else b""
        if not body or not _is_textual_asset(asset_url, content_type):
            continue

        path_suffix = Path(urlparse(asset_url).path).suffix.lower()
        is_javascript_asset = "javascript" in content_type.lower() or path_suffix in {".js", ".mjs"}
        resolution_base_url = parse_base_url if is_javascript_asset else asset_url
        parse_context = (asset_url, resolution_base_url)
        if parse_context in parsed_contexts:
            continue
        parsed_contexts.add(parse_context)

        base_url = asset_url
        if fetched_now:
            fetched_base_url = getattr(asset, "url", None)
            if isinstance(fetched_base_url, str) and fetched_base_url.strip():
                base_url = fetched_base_url
        include_html_attrs = not is_javascript_asset
        for ref_url in extract_referenced_urls(
            resolution_base_url,
            _decode_text_body(body),
            include_absolute_urls=False,
            include_html_attrs=include_html_attrs,
        ):
            if not _is_static_asset_url(ref_url):
                continue
            if not _within_course_scope(root_urls, ref_url):
                continue
            child_suffix = Path(urlparse(ref_url).path).suffix.lower()
            child_is_javascript = child_suffix in {".js", ".mjs"}
            child_parse_base_url = resolution_base_url if child_is_javascript else ref_url
            if (ref_url, child_parse_base_url) not in parsed_contexts:
                queue.append((ref_url, child_parse_base_url))

        if path_suffix == ".html":
            for ref_url in _iter_ispring_presinfo_urls(asset_url, _decode_text_body(body)):
                if not _is_static_asset_url(ref_url):
                    continue
                if not _within_course_scope(root_urls, ref_url):
                    continue
                child_suffix = Path(urlparse(ref_url).path).suffix.lower()
                child_is_javascript = child_suffix in {".js", ".mjs"}
                child_parse_base_url = resolution_base_url if child_is_javascript else ref_url
                if (ref_url, child_parse_base_url) not in parsed_contexts:
                    queue.append((ref_url, child_parse_base_url))

        if is_javascript_asset:
            for ref_url in _iter_slide_markup_urls(resolution_base_url, _decode_text_body(body)):
                if not _is_static_asset_url(ref_url):
                    continue
                if not _within_course_scope(root_urls, ref_url):
                    continue
                child_suffix = Path(urlparse(ref_url).path).suffix.lower()
                child_is_javascript = child_suffix in {".js", ".mjs"}
                child_parse_base_url = resolution_base_url if child_is_javascript else ref_url
                if (ref_url, child_parse_base_url) not in parsed_contexts:
                    queue.append((ref_url, child_parse_base_url))

    ordered_rows = list(asset_rows_by_url.values())
    fetched_asset_count = sum(1 for row in ordered_rows if row["present"])
    missing_asset_count = len(missing_assets)
    manifest = {
        "material_id": normalized_material_id,
        "title": str(material.get("title") or ""),
        "root_urls": root_urls,
        "visited_urls": list(asset_rows_by_url.keys()),
        "missing_assets": missing_assets,
    }

    store.upsert_curriculum_material_archive(
        normalized_material_id,
        {
            "root_url_count": len(root_urls),
            "fetched_asset_count": fetched_asset_count,
            "missing_asset_count": missing_asset_count,
            "all_local": missing_asset_count == 0,
            "last_verified_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "manifest": manifest,
        },
    )
    store.replace_curriculum_material_archive_assets(normalized_material_id, ordered_rows)

    archive_state = store.get_curriculum_material_archive(normalized_material_id) or {"archive": {}, "assets": []}
    return {
        "material_id": normalized_material_id,
        "fetched_asset_count": int((archive_state.get("archive") or {}).get("fetched_asset_count") or 0),
        "missing_asset_count": int((archive_state.get("archive") or {}).get("missing_asset_count") or 0),
        "missing_assets": [asset for asset in archive_state.get("assets", []) if not asset.get("present")],
        "archive": archive_state.get("archive") or {},
        "assets": archive_state.get("assets") or [],
    }


__all__ = ["archive_course_material"]
