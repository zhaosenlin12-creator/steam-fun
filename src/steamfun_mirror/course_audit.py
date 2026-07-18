from __future__ import annotations

import base64
import json
import re
import zlib
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from .rewrite import LOCAL_EXTERNAL_PREFIX
from .storage import MirrorStore


COURSE_URL_FIELDS = (
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
PRESINFO_RE = re.compile(r'var presInfo = "([A-Za-z0-9+/=]+)"')


def _asset_url_variants(url: str) -> list[str]:
    normalized = str(url or "").strip()
    if not normalized:
        return []
    variants = [normalized]
    parsed = urlparse(normalized)
    if parsed.query:
        variants.append(urlunparse(parsed._replace(query="")))

    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in variants:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _iter_candidate_urls(material: dict[str, Any], archive: dict[str, Any]) -> Iterable[str]:
    for field in COURSE_URL_FIELDS:
        value = str((material or {}).get(field) or "").strip()
        if value:
            yield value
    manifest = (archive.get("archive") or {}).get("manifest") or {}
    if isinstance(manifest, dict):
        for key in ("root_urls", "visited_urls"):
            values = manifest.get(key)
            if isinstance(values, list):
                for value in values:
                    normalized = str(value or "").strip()
                    if normalized:
                        yield normalized
        missing_assets = manifest.get("missing_assets")
        if isinstance(missing_assets, list):
            for item in missing_assets:
                if not isinstance(item, dict):
                    continue
                normalized = str(item.get("asset_url") or "").strip()
                if normalized:
                    yield normalized


def _extract_hosts(urls: Iterable[str]) -> list[str]:
    hosts: set[str] = set()
    for url in urls:
        normalized = str(url or "").strip()
        if normalized.startswith(f"{LOCAL_EXTERNAL_PREFIX}/"):
            suffix = normalized[len(LOCAL_EXTERNAL_PREFIX):].lstrip("/")
            host, _, _ = suffix.partition("/")
            if host:
                hosts.add(host)
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc:
            hosts.add(parsed.netloc)
    return sorted(hosts)


def _looks_like_incomplete_ispring_archive(archive: dict[str, Any]) -> bool:
    assets = archive.get("assets") or []
    asset_urls: list[str] = []
    if isinstance(assets, list):
        asset_urls.extend(
            str((asset or {}).get("asset_url") or "").strip()
            for asset in assets
            if isinstance(asset, dict)
        )
    manifest = (archive.get("archive") or {}).get("manifest") or {}
    if isinstance(manifest, dict):
        visited_urls = manifest.get("visited_urls")
        if isinstance(visited_urls, list):
            asset_urls.extend(str(value or "").strip() for value in visited_urls)
    if not asset_urls:
        return False

    has_index_html = any(urlparse(url).path.endswith("/index.html") for url in asset_urls)
    has_player_js = any("/data/player.js" in url for url in asset_urls)
    if not has_index_html or not has_player_js:
        return False

    has_slide_runtime = any("/data/slide" in url and (".js" in url or ".css" in url) for url in asset_urls)
    has_font_runtime = any("/data/fnt" in url and ".woff" in url for url in asset_urls)
    return not has_slide_runtime or not has_font_runtime


def _declared_presinfo_runtime_assets(store: MirrorStore, archive: dict[str, Any]) -> set[str]:
    assets = archive.get("assets") or []
    index_url = ""
    index_local_path = ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_url = str(asset.get("asset_url") or "").strip()
        if not urlparse(asset_url).path.endswith("/index.html"):
            continue
        local_path = str(asset.get("local_path") or "").strip()
        if not local_path:
            continue
        for candidate_url in _asset_url_variants(asset_url):
            indexed_asset = store.lookup_asset(candidate_url)
            if indexed_asset is None:
                continue
            candidate_local_path = str(indexed_asset.get("local_path") or "").strip()
            if not candidate_local_path:
                continue
            index_url = candidate_url
            index_local_path = candidate_local_path
            break
        if index_url and index_local_path:
            break
    if not index_url or not index_local_path:
        return set()

    index_file = store.root / index_local_path
    if not index_file.is_file():
        return set()

    match = PRESINFO_RE.search(index_file.read_text("utf-8", errors="ignore"))
    if match is None:
        return set()

    try:
        payload = zlib.decompress(base64.b64decode(match.group(1)))
        presinfo = json.loads(payload.decode("utf-8"))
    except Exception:
        return set()

    base_url = index_url.rsplit("/", 1)[0] + "/"
    declared: set[str] = set()

    def add(candidate: str) -> None:
        normalized = str(candidate or "").strip()
        if not normalized or normalized.startswith("data.local-only/"):
            return
        if normalized.startswith("data/slide") and (normalized.endswith(".js") or normalized.endswith(".css")):
            declared.add(f"{base_url}{normalized}")
        if normalized.startswith("data/fnt") and (normalized.endswith(".woff") or normalized.endswith(".woff2")):
            declared.add(f"{base_url}{normalized}")

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"s", "c", "u", "i", "src", "poster"}:
                    if isinstance(value, str):
                        add(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                add(item)
                walk(value)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(presinfo)
    return declared


def _archive_missing_declared_presinfo_runtime_assets(store: MirrorStore, archive: dict[str, Any]) -> bool:
    declared_runtime_assets = _declared_presinfo_runtime_assets(store, archive)
    if not declared_runtime_assets:
        return False

    assets = archive.get("assets") or []
    present_asset_urls = {
        str((asset or {}).get("asset_url") or "").strip()
        for asset in assets
        if isinstance(asset, dict) and bool(asset.get("present"))
    }
    return any(asset_url not in present_asset_urls for asset_url in declared_runtime_assets)


def build_course_offline_report(store: MirrorStore) -> dict[str, Any]:
    materials_report: list[dict[str, Any]] = []
    all_hosts: set[str] = set()
    missing_resource_materials = 0
    not_archived_materials = 0

    for material in store.list_local_curriculum_material_snapshots():
        material_id = int(material.get("id") or 0)
        archive = store.get_curriculum_material_archive(material_id) or {"archive": {}, "assets": []}
        archive_row = archive.get("archive") or {}
        missing_asset_count = int(archive_row.get("missing_asset_count") or 0)
        fetched_asset_count = int(archive_row.get("fetched_asset_count") or 0)
        root_url_count = int(archive_row.get("root_url_count") or 0)
        all_local = bool(archive_row.get("all_local"))
        if not archive_row:
            status = "not_archived"
            not_archived_materials += 1
        elif (
            missing_asset_count > 0
            or not all_local
            or _looks_like_incomplete_ispring_archive(archive)
            or _archive_missing_declared_presinfo_runtime_assets(store, archive)
        ):
            status = "missing_resource"
            missing_resource_materials += 1
        else:
            status = "passed"

        upstream_hosts = _extract_hosts(_iter_candidate_urls(material, archive))
        all_hosts.update(upstream_hosts)
        materials_report.append(
            {
                "material_id": material_id,
                "title": str(material.get("title") or ""),
                "status": status,
                "root_url_count": root_url_count,
                "fetched_asset_count": fetched_asset_count,
                "missing_asset_count": missing_asset_count,
                "all_local": all_local,
                "last_verified_at": archive_row.get("last_verified_at"),
                "upstream_hosts": upstream_hosts,
            }
        )

    return {
        "summary": {
            "total_materials": len(materials_report),
            "missing_resource_materials": missing_resource_materials,
            "not_archived_materials": not_archived_materials,
            "upstream_host_count": len(all_hosts),
            "upstream_hosts": sorted(all_hosts),
        },
        "materials": materials_report,
    }


def build_course_runtime_audit_report(summary: dict[str, Any]) -> dict[str, Any]:
    network_audit = summary.get("network_audit") if isinstance(summary, dict) else {}
    if not isinstance(network_audit, dict):
        network_audit = {}

    external_request_count = int(network_audit.get("external_request_count") or 0)
    failed_response_count = int(network_audit.get("failed_response_count") or 0)
    page_error_count = int(network_audit.get("page_error_count") or 0)
    console_error_count = int(network_audit.get("console_error_count") or 0)
    business_flow_passed = bool((summary or {}).get("all_passed"))
    strict_local_passed = (
        business_flow_passed
        and external_request_count == 0
        and failed_response_count == 0
        and page_error_count == 0
        and console_error_count == 0
    )

    return {
        "business_flow_passed": business_flow_passed,
        "strict_local_passed": strict_local_passed,
        "violations": {
            "external_request_count": external_request_count,
            "failed_response_count": failed_response_count,
            "page_error_count": page_error_count,
            "console_error_count": console_error_count,
        },
        "evidence": {
            "external_requests": list(network_audit.get("external_requests") or []),
            "failed_responses": list(network_audit.get("failed_responses") or []),
            "page_errors": list(network_audit.get("page_errors") or []),
            "console_errors": list(network_audit.get("console_errors") or []),
        },
    }


__all__ = ["build_course_offline_report", "build_course_runtime_audit_report"]
