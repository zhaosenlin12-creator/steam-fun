from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
import zlib

import pytest

from steamfun_mirror.storage import MirrorStore


def _load_course_audit_module():
    try:
        return importlib.import_module("steamfun_mirror.course_audit")
    except ModuleNotFoundError as exc:
        pytest.fail(f"steamfun_mirror.course_audit is missing: {exc}")


def _encode_presinfo(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(body)).decode("ascii")


def test_build_course_offline_report_classifies_missing_material_assets(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39525,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Watermelon Fan",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )
    store.upsert_curriculum_material_archive(
        39525,
        {
            "root_url_count": 1,
            "fetched_asset_count": 2,
            "missing_asset_count": 1,
            "all_local": False,
            "last_verified_at": "2026-06-11T12:00:00",
            "manifest": {
                "root_urls": ["https://wugecdn.steam.fun/course/index.html"],
                "visited_urls": ["https://wugecdn.steam.fun/course/index.html"],
                "missing_assets": [
                    {"asset_url": "https://wugecdn.steam.fun/course/data/player.js", "present": False}
                ],
            },
        },
    )

    report = course_audit.build_course_offline_report(store)

    assert report["summary"]["total_materials"] == 1
    assert report["summary"]["missing_resource_materials"] == 1
    assert report["materials"][0]["status"] == "missing_resource"
    assert report["materials"][0]["missing_asset_count"] == 1


def test_build_course_offline_report_summarizes_upstream_hosts(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39526,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Host Audit Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
            "other_meterial_url": "https://steamfun-cdn.oss-cn-zhangjiakou.aliyuncs.com/materials/a.pdf",
        }
    )
    store.upsert_curriculum_material_archive(
        39526,
        {
            "root_url_count": 2,
            "fetched_asset_count": 2,
            "missing_asset_count": 0,
            "all_local": True,
            "last_verified_at": "2026-06-11T12:10:00",
            "manifest": {
                "root_urls": [
                    "https://wugecdn.steam.fun/course/index.html",
                    "https://steamfun-cdn.oss-cn-zhangjiakou.aliyuncs.com/materials/a.pdf",
                ],
                "visited_urls": [
                    "https://wugecdn.steam.fun/course/index.html",
                    "https://wugecdn.steam.fun/course/data/player.js?8E49BC96",
                    "https://wugecdn.steam.fun/course/data/slide1.js",
                    "https://wugecdn.steam.fun/course/data/slide1.css",
                    "https://wugecdn.steam.fun/course/data/fnt0.woff",
                    "https://steamfun-cdn.oss-cn-zhangjiakou.aliyuncs.com/materials/a.pdf",
                ],
                "missing_assets": [],
            },
        },
    )

    report = course_audit.build_course_offline_report(store)

    assert report["summary"]["total_materials"] == 1
    assert report["summary"]["missing_resource_materials"] == 0
    assert report["summary"]["upstream_host_count"] == 2
    assert report["summary"]["upstream_hosts"] == [
        "steamfun-cdn.oss-cn-zhangjiakou.aliyuncs.com",
        "wugecdn.steam.fun",
    ]
    assert report["materials"][0]["upstream_hosts"] == [
        "steamfun-cdn.oss-cn-zhangjiakou.aliyuncs.com",
        "wugecdn.steam.fun",
    ]


def test_build_course_offline_runtime_audit_report_classifies_runtime_violations(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()

    report = course_audit.build_course_runtime_audit_report(
        {
            "all_passed": True,
            "network_audit": {
                "external_request_count": 1,
                "failed_response_count": 1,
                "page_error_count": 1,
                "console_error_count": 1,
                "external_requests": [
                    {"url": "https://wugecdn.steam.fun/course/a.js", "host": "wugecdn.steam.fun"}
                ],
                "failed_responses": [
                    {"url": "http://127.0.0.1:8000/_external/x/y.js", "status": 424}
                ],
                "page_errors": [{"message": "Unexpected token ')'"}],
                "console_errors": [{"text": "Network Error"}],
            },
        }
    )

    assert report["strict_local_passed"] is False
    assert report["violations"]["external_request_count"] == 1
    assert report["violations"]["failed_response_count"] == 1
    assert report["violations"]["page_error_count"] == 1
    assert report["violations"]["console_error_count"] == 1


def test_build_course_offline_runtime_audit_report_passes_clean_local_run(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()

    report = course_audit.build_course_runtime_audit_report(
        {
            "all_passed": True,
            "network_audit": {
                "external_request_count": 0,
                "failed_response_count": 0,
                "page_error_count": 0,
                "console_error_count": 0,
                "external_requests": [],
                "failed_responses": [],
                "page_errors": [],
                "console_errors": [],
            },
        }
    )

    assert report["strict_local_passed"] is True
    assert report["business_flow_passed"] is True
    assert report["violations"]["external_request_count"] == 0


def test_build_course_offline_report_flags_ispring_shell_without_runtime_assets(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39530,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Incomplete iSpring Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )
    store.upsert_curriculum_material_archive(
        39530,
        {
            "root_url_count": 1,
            "fetched_asset_count": 2,
            "missing_asset_count": 0,
            "all_local": True,
            "last_verified_at": "2026-06-12T12:00:00",
            "manifest": {
                "root_urls": ["https://wugecdn.steam.fun/course/index.html"],
                "visited_urls": [
                    "https://wugecdn.steam.fun/course/index.html",
                    "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
                ],
                "missing_assets": [],
            },
        },
    )

    report = course_audit.build_course_offline_report(store)

    assert report["summary"]["total_materials"] == 1
    assert report["summary"]["missing_resource_materials"] == 1
    assert report["materials"][0]["status"] == "missing_resource"


def test_build_course_offline_report_flags_missing_presinfo_runtime_assets_even_when_partial_runtime_exists(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39533,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Partial Runtime Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    presinfo = _encode_presinfo(
        {
            "s": [
                {
                    "s": "data/slide1.js",
                    "c": "data/slide1.css",
                },
                {
                    "s": "data/slide2.js",
                    "c": "data/slide2.css",
                },
            ],
            "f": [{"u": ["data/fnt0.woff"]}],
        }
    )
    store.store_external_asset(
        "https://wugecdn.steam.fun/course/index.html",
        (
            f'<html><script src="data/player.js"></script>'
            f"<script>var presInfo = \"{presinfo}\";</script></html>"
        ).encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
    )
    store.store_external_asset(
        "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
        b'console.log("player");',
        headers={"content-type": "application/javascript; charset=utf-8"},
    )
    store.store_external_asset(
        "https://wugecdn.steam.fun/course/data/slide1.js",
        b'console.log("slide1");',
        headers={"content-type": "application/javascript; charset=utf-8"},
    )
    store.store_external_asset(
        "https://wugecdn.steam.fun/course/data/fnt0.woff",
        b"WOFF",
        headers={"content-type": "font/woff"},
    )
    store.upsert_curriculum_material_archive(
        39533,
        {
            "root_url_count": 1,
            "fetched_asset_count": 4,
            "missing_asset_count": 0,
            "all_local": True,
            "last_verified_at": "2026-06-13T01:30:00",
            "manifest": {
                "root_urls": ["https://wugecdn.steam.fun/course/index.html"],
                "visited_urls": [
                    "https://wugecdn.steam.fun/course/index.html",
                    "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
                    "https://wugecdn.steam.fun/course/data/slide1.js",
                    "https://wugecdn.steam.fun/course/data/fnt0.woff",
                ],
                "missing_assets": [],
            },
        },
    )
    store.replace_curriculum_material_archive_assets(
        39533,
        [
            {
                "material_id": 39533,
                "asset_url": "https://wugecdn.steam.fun/course/index.html",
                "local_path": "external/wugecdn.steam.fun/course/index.html",
                "status": 200,
                "content_type": "text/html; charset=utf-8",
                "required": True,
                "present": True,
            },
            {
                "material_id": 39533,
                "asset_url": "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
                "local_path": "external/wugecdn.steam.fun/course/data/player.js",
                "status": 200,
                "content_type": "application/javascript; charset=utf-8",
                "required": True,
                "present": True,
            },
            {
                "material_id": 39533,
                "asset_url": "https://wugecdn.steam.fun/course/data/slide1.js",
                "local_path": "external/wugecdn.steam.fun/course/data/slide1.js",
                "status": 200,
                "content_type": "application/javascript; charset=utf-8",
                "required": True,
                "present": True,
            },
            {
                "material_id": 39533,
                "asset_url": "https://wugecdn.steam.fun/course/data/fnt0.woff",
                "local_path": "external/wugecdn.steam.fun/course/data/fnt0.woff",
                "status": 200,
                "content_type": "font/woff",
                "required": True,
                "present": True,
            },
        ],
    )

    report = course_audit.build_course_offline_report(store)

    assert report["summary"]["total_materials"] == 1
    assert report["summary"]["missing_resource_materials"] == 1
    assert report["materials"][0]["status"] == "missing_resource"


def test_build_course_offline_report_flags_query_versioned_ispring_shell_without_runtime_assets(tmp_path: Path) -> None:
    course_audit = _load_course_audit_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39538,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Versioned iSpring Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html?v=2.0",
        }
    )

    presinfo = _encode_presinfo(
        {
            "s": [
                {
                    "s": "data/slide1.js",
                    "c": "data/slide1.css",
                }
            ],
            "f": [{"u": ["data/fnt0.woff"]}],
        }
    )
    store.store_external_asset(
        "https://wugecdn.steam.fun/course/index.html?v=2.0",
        (
            f'<html><script src="data/player.js?ABC12345"></script>'
            f"<script>var presInfo = \"{presinfo}\";</script></html>"
        ).encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
    )
    store.store_external_asset(
        "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
        b'console.log("player");',
        headers={"content-type": "application/javascript; charset=utf-8"},
    )
    store.upsert_curriculum_material_archive(
        39538,
        {
            "root_url_count": 1,
            "fetched_asset_count": 2,
            "missing_asset_count": 0,
            "all_local": True,
            "last_verified_at": "2026-06-14T00:30:00",
            "manifest": {
                "root_urls": ["https://wugecdn.steam.fun/course/index.html?v=2.0"],
                "visited_urls": [
                    "https://wugecdn.steam.fun/course/index.html?v=2.0",
                    "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
                ],
                "missing_assets": [],
            },
        },
    )
    store.replace_curriculum_material_archive_assets(
        39538,
        [
            {
                "material_id": 39538,
                "asset_url": "https://wugecdn.steam.fun/course/index.html?v=2.0",
                "local_path": "external/wugecdn.steam.fun/course/index.html",
                "status": 200,
                "content_type": "text/html; charset=utf-8",
                "required": True,
                "present": True,
            },
            {
                "material_id": 39538,
                "asset_url": "https://wugecdn.steam.fun/course/data/player.js?ABC12345",
                "local_path": "external/wugecdn.steam.fun/course/data/player.js",
                "status": 200,
                "content_type": "application/javascript; charset=utf-8",
                "required": True,
                "present": True,
            },
        ],
    )

    report = course_audit.build_course_offline_report(store)

    assert report["summary"]["total_materials"] == 1
    assert report["summary"]["missing_resource_materials"] == 1
    assert report["materials"][0]["status"] == "missing_resource"
