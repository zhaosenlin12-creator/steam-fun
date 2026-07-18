from __future__ import annotations

import base64
import importlib
import json
import zlib
from pathlib import Path

import pytest

from steamfun_mirror.storage import MirrorStore


class FakeResponse:
    def __init__(self, *, content: bytes, content_type: str, status_code: int = 200):
        self.content = content
        self.headers = {"content-type": content_type}
        self.status_code = status_code

    def iter_content(self, chunk_size: int = 8192):
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index:index + chunk_size]

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _load_course_archive_module():
    try:
        return importlib.import_module("steamfun_mirror.course_archive")
    except ModuleNotFoundError as exc:
        pytest.fail(f"steamfun_mirror.course_archive is missing: {exc}")


def _encode_presinfo(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(body)).decode("ascii")


def test_archive_course_material_records_missing_child_assets(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
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

    def fake_fetch_static_asset(live_url: str):
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=(
                    b'<html><script src="data/player.js"></script>'
                    b'<audio src="data/intro.mp3"></audio></html>'
                ),
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/player.js":
            return FakeResponse(
                content=b'console.log("player");',
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/intro.mp3":
            return None
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39525)

    assert report["material_id"] == 39525
    assert report["fetched_asset_count"] == 2
    assert report["missing_asset_count"] == 1
    assert len(report["missing_assets"]) == 1
    assert report["missing_assets"][0]["asset_url"].endswith("intro.mp3")


def test_archive_course_material_fetches_wasm_assets_discovered_via_fetch(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39526,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Wasm Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    def fake_fetch_static_asset(live_url: str):
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=b'<html><script>fetch("runtime/config.wasm")</script></html>',
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/runtime/config.wasm":
            return FakeResponse(
                content=b"\x00asm\x01\x00\x00\x00",
                content_type="application/wasm",
            )
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39526)

    assert report["material_id"] == 39526
    assert report["fetched_asset_count"] == 2
    assert report["missing_asset_count"] == 0
    assert any(
        asset["asset_url"].endswith("config.wasm") and asset["present"] is True
        for asset in report["assets"]
    )


def test_archive_course_material_resolves_external_js_relative_assets_from_document_base(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39528,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "External JS Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    def fake_fetch_static_asset(live_url: str):
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=b'<html><script src="data/player.js"></script></html>',
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/player.js":
            return FakeResponse(
                content=b'const styles=".tool{cursor:url(data/lock.cur), no-drop}";',
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/lock.cur":
            return FakeResponse(
                content=b"CUR",
                content_type="application/octet-stream",
            )
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39528)

    assert report["material_id"] == 39528
    assert report["fetched_asset_count"] == 3
    assert report["missing_asset_count"] == 0
    assert any(
        asset["asset_url"] == "https://wugecdn.steam.fun/course/data/lock.cur" and asset["present"] is True
        for asset in report["assets"]
    )


def test_archive_course_material_ignores_unscoped_absolute_urls_in_inline_js(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39527,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Scoped URL Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    fetched_urls: list[str] = []

    def fake_fetch_static_asset(live_url: str):
        fetched_urls.append(live_url)
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=(
                    b'<html><script>'
                    b'const source="https://github.com/zloirock/core-js";'
                    b'fetch("runtime/config.wasm")'
                    b'</script></html>'
                ),
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/runtime/config.wasm":
            return FakeResponse(
                content=b"\x00asm\x01\x00\x00\x00",
                content_type="application/wasm",
            )
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39527)

    assert report["fetched_asset_count"] == 2
    assert "https://github.com/zloirock/core-js" not in fetched_urls


def test_archive_course_material_fetches_ispring_presinfo_assets(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39529,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "iSpring Lesson",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    presinfo = _encode_presinfo(
        {
            "s": [
                {
                    "s": "data/slide1.js",
                    "c": "data/slide1.css",
                    "T": {"i": "data/thmb1.png", "w": 78, "h": 43},
                }
            ],
            "f": [{"u": ["data/fnt0.woff"]}],
        }
    )

    def fake_fetch_static_asset(live_url: str):
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=(
                    f'<html><script src="data/player.js"></script>'
                    f"<script>var presInfo = \"{presinfo}\";</script></html>"
                ).encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/player.js":
            return FakeResponse(
                content=b'console.log("player");',
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/slide1.js":
            return FakeResponse(
                content=b'console.log("slide1");',
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/slide1.css":
            return FakeResponse(
                content=b".slide{display:block;}",
                content_type="text/css; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/thmb1.png":
            return FakeResponse(
                content=b"PNG",
                content_type="image/png",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/fnt0.woff":
            return FakeResponse(
                content=b"WOFF",
                content_type="font/woff",
            )
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39529)

    assert report["material_id"] == 39529
    assert report["fetched_asset_count"] == 6
    assert report["missing_asset_count"] == 0
    assert any(
        asset["asset_url"] == "https://wugecdn.steam.fun/course/data/slide1.js" and asset["present"] is True
        for asset in report["assets"]
    )
    assert any(
        asset["asset_url"] == "https://wugecdn.steam.fun/course/data/fnt0.woff" and asset["present"] is True
        for asset in report["assets"]
    )


def test_archive_course_material_fetches_assets_embedded_in_slide_js_markup(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39531,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "iSpring Slide Assets",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    presinfo = _encode_presinfo(
        {
            "s": [
                {
                    "s": "data/slide1.js",
                    "c": "data/slide1.css",
                }
            ]
        }
    )

    def fake_fetch_static_asset(live_url: str):
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=(
                    f'<html><script src="data/player.js"></script>'
                    f"<script>var presInfo = \"{presinfo}\";</script></html>"
                ).encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/player.js":
            return FakeResponse(
                content=b'console.log("player");',
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/slide1.js":
            return FakeResponse(
                content=(
                    b"(function(){"
                    b"window.__slide='<img src=\"data/img0.png\"><video poster=\"data/poster.png\">"
                    b"<source src=\"data/video1.mp4\" type=\"video/mp4\"></video>';"
                    b"})();"
                ),
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/slide1.css":
            return FakeResponse(
                content=b".slide{display:block;}",
                content_type="text/css; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/img0.png":
            return FakeResponse(
                content=b"PNG",
                content_type="image/png",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/poster.png":
            return FakeResponse(
                content=b"PNG",
                content_type="image/png",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/video1.mp4":
            return FakeResponse(
                content=b"MP4",
                content_type="video/mp4",
            )
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39531)

    assert report["fetched_asset_count"] == 7
    assert report["missing_asset_count"] == 0
    assert any(
        asset["asset_url"] == "https://wugecdn.steam.fun/course/data/img0.png" and asset["present"] is True
        for asset in report["assets"]
    )
    assert any(
        asset["asset_url"] == "https://wugecdn.steam.fun/course/data/video1.mp4" and asset["present"] is True
        for asset in report["assets"]
    )


def test_archive_course_material_ignores_third_party_and_invalid_embedded_slide_urls(tmp_path: Path, monkeypatch) -> None:
    course_archive = _load_course_archive_module()
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39532,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Scoped iSpring Slide Assets",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )

    presinfo = _encode_presinfo(
        {
            "s": [
                {
                    "s": "data/slide1.js",
                    "c": "data/slide1.css",
                }
            ]
        }
    )

    fetched_urls: list[str] = []

    def fake_fetch_static_asset(live_url: str):
        fetched_urls.append(live_url)
        if live_url == "https://wugecdn.steam.fun/course/index.html":
            return FakeResponse(
                content=(
                    f'<html><script src="data/player.js"></script>'
                    f"<script>var presInfo = \"{presinfo}\";</script></html>"
                ).encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/player.js":
            return FakeResponse(
                content=b'console.log("player");',
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/slide1.js":
            return FakeResponse(
                content=(
                    b"(function(){"
                    b"window.__slide='<img src=\"data/img0.png\">"
                    b"<img src=\"https://huewq7h021.feishu.cn/docs/image/png\">"
                    b"<script src=\"https://huewq7h021.feishu.cn/docs/.+www\\\\.instagram\\\\.com\\\\/embed\\\\.js\"></script>"
                    b"<img src=\"http://\xe0\xb8\x87\xe0\xb9\x84\xe0\xb8\x87\xe0\xb8\xb6\xe0\xb8\x87\xe0\xb9\x83\xe0\xb8\x87\xe0\xb9\x84\"></img>';"
                    b"})();"
                ),
                content_type="application/javascript; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/slide1.css":
            return FakeResponse(
                content=b".slide{display:block;}",
                content_type="text/css; charset=utf-8",
            )
        if live_url == "https://wugecdn.steam.fun/course/data/img0.png":
            return FakeResponse(
                content=b"PNG",
                content_type="image/png",
            )
        pytest.fail(f"Unexpected fetch: {live_url}")

    monkeypatch.setattr(course_archive, "_fetch_static_asset", fake_fetch_static_asset)

    report = course_archive.archive_course_material(store, 39532)

    assert report["missing_asset_count"] == 0
    assert "https://huewq7h021.feishu.cn/docs/image/png" not in fetched_urls
    assert not any("instagram" in url for url in fetched_urls)
