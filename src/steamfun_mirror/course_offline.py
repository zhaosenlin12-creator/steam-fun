from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from fastapi.responses import JSONResponse

from .storage import MirrorStore


def _archive_url_variants(live_url: str) -> list[str]:
    normalized = str(live_url or "").strip()
    if not normalized:
        return []
    variants = [normalized]
    parsed = urlparse(normalized)
    if parsed.query:
        variants.append(urlunparse(parsed._replace(query="")))
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in variants:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def lookup_course_archive_asset(store: MirrorStore, live_url: str) -> dict[str, Any] | None:
    variants = _archive_url_variants(live_url)
    if not variants:
        return None
    placeholders = ", ".join("?" for _ in variants)
    with store._connect() as connection:
        rows = connection.execute(
            f"""
            SELECT a.material_id, a.asset_url, a.local_path, a.status, a.content_type, a.required, a.present,
                   ar.all_local, ar.last_verified_at
            FROM curriculum_material_archive_assets a
            JOIN curriculum_material_archives ar ON ar.material_id = a.material_id
            WHERE a.asset_url IN ({placeholders})
            """,
            variants,
        ).fetchall()
    rows_by_url = {str(row["asset_url"]): row for row in rows}
    for candidate in variants:
        row = rows_by_url.get(candidate)
        if row is None:
            continue
        return {
            "material_id": row["material_id"],
            "asset_url": row["asset_url"],
            "local_path": row["local_path"],
            "status": row["status"],
            "content_type": row["content_type"],
            "required": bool(row["required"]),
            "present": bool(row["present"]),
            "all_local": bool(row["all_local"]),
            "last_verified_at": row["last_verified_at"],
        }
    return None


def build_course_asset_not_local_response(record: dict[str, Any], requested_url: str) -> JSONResponse:
    return JSONResponse(
        status_code=424,
        content={
            "success": False,
            "error": {
                "code": "COURSE_ASSET_NOT_LOCAL",
                "message": "Course asset is not available in the local offline archive.",
                "material_id": int(record.get("material_id") or 0),
                "asset_url": requested_url,
                "archive_asset_url": str(record.get("asset_url") or requested_url),
            },
        },
    )


__all__ = ["build_course_asset_not_local_response", "lookup_course_archive_asset"]
