# Course Offline Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the course-related domain of `steam_fun` into a fully local offline package whose data, assets, and runtime behavior no longer depend on upstream `steam.fun`, `wugecdn`, or OSS hosts.

**Architecture:** Extend `MirrorStore` so the course domain has structured local snapshot tables plus per-material archive/completeness state. Build a recursive course asset archiver that closes all required child references, then switch the FastAPI server to strict local rules for course-domain APIs and resources. Finish with an offline audit that proves the class-selection -> teaching-plan -> student-entry -> in-course-content chain works without upstream network access.

**Tech Stack:** Python 3.10, FastAPI, SQLite, requests, pytest, Playwright-based browser scripts, existing `steamfun_mirror` storage/server/discovery modules.

---

## File Map

**Core persistence**

- Modify: `src/steamfun_mirror/storage.py`
  Add course snapshot tables, archive tables, and read/write helpers for local curriculum materials, archive manifests, and asset status.

**Course snapshot import**

- Create: `src/steamfun_mirror/course_snapshot.py`
  Normalize captured course-domain API payloads into stable local SQLite tables.
- Create: `scripts/build_course_snapshot.py`
  CLI entrypoint to rebuild the course-domain local snapshot from captured payloads.

**Recursive asset closure**

- Modify: `src/steamfun_mirror/discovery.py`
  Expand reference extraction to include more course asset patterns.
- Create: `src/steamfun_mirror/course_archive.py`
  Crawl root material URLs, recursively fetch child assets, and persist material manifests/completeness state.
- Create: `scripts/fetch_course_archive.py`
  CLI entrypoint for one-time online archival of all course materials.

**Strict local runtime**

- Create: `src/steamfun_mirror/course_offline.py`
  Hold course-domain strict-local helpers, host audit helpers, and course-specific local lookup policy.
- Modify: `src/steamfun_mirror/server.py`
  Route course-domain APIs/resources through strict local helpers and explicit miss reporting.

**Offline audit**

- Create: `src/steamfun_mirror/course_audit.py`
  Build material-level completeness summaries and host-audit reports.
- Create: `scripts/course_offline_audit.py`
  Produce offline readiness reports and optionally drive browser verification.
- Modify: `scripts/management_flow_audit.py`
  Reuse the existing browser flow audit to assert offline-only course hosts.
- Modify: `README.md`
  Document the full archive -> serve -> offline verify workflow.

**Tests**

- Modify: `tests/test_storage.py`
- Create: `tests/test_course_snapshot.py`
- Modify: `tests/test_discovery.py`
- Create: `tests/test_course_archive.py`
- Modify: `tests/test_server.py`
- Create: `tests/test_course_audit.py`

---

### Task 1: Add Course Snapshot And Archive Persistence

**Files:**
- Modify: `src/steamfun_mirror/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing persistence tests**

```python
from pathlib import Path

from steamfun_mirror.storage import MirrorStore


def test_course_snapshot_tables_persist_material_and_archive_state(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    store.upsert_local_subject_snapshot({"id": 1, "name": "Jrcode", "code": 1})
    store.upsert_local_curriculum_snapshot(
        {
            "id": 3429,
            "subject_id": 1,
            "title": "Summer Watermelon",
            "number_of_courses": 8,
            "img_url": "/_external/wugecdn.steam.fun/courses/poster.png",
        }
    )
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39525,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Watermelon Fan",
            "ppt_url": "https://wugecdn.steam.fun/courses/a/index.html",
            "video_url": "https://wugecdn.steam.fun/courses/a/video.mp4",
        }
    )
    store.upsert_curriculum_material_archive(
        39525,
        {
            "root_url_count": 3,
            "fetched_asset_count": 12,
            "missing_asset_count": 1,
            "all_local": False,
            "last_verified_at": "2026-06-11T12:00:00",
        },
    )
    store.replace_curriculum_material_archive_assets(
        39525,
        [
            {
                "asset_url": "https://wugecdn.steam.fun/courses/a/index.html",
                "local_path": "external/wugecdn.steam.fun/courses/a/index.html",
                "status": 200,
                "content_type": "text/html",
                "required": True,
                "present": True,
            },
            {
                "asset_url": "https://wugecdn.steam.fun/courses/a/data/player.js",
                "local_path": "",
                "status": 0,
                "content_type": "",
                "required": True,
                "present": False,
            },
        ],
    )

    material = store.get_local_curriculum_material_snapshot(39525)
    archive = store.get_curriculum_material_archive(39525)

    assert material is not None
    assert material["title"] == "Watermelon Fan"
    assert archive["archive"]["missing_asset_count"] == 1
    assert archive["assets"][1]["asset_url"].endswith("player.js")
    assert archive["assets"][1]["present"] is False
```

- [ ] **Step 2: Run the storage test to verify it fails**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py::test_course_snapshot_tables_persist_material_and_archive_state -v
```

Expected: `FAIL` with `AttributeError` for missing snapshot/archive methods or SQLite table errors.

- [ ] **Step 3: Implement local snapshot and archive tables in `storage.py`**

```python
connection.executescript(
    """
    CREATE TABLE IF NOT EXISTS local_subject_snapshots (
        id INTEGER PRIMARY KEY,
        code INTEGER,
        name TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS local_curriculum_snapshots (
        id INTEGER PRIMARY KEY,
        subject_id INTEGER,
        title TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS local_curriculum_material_snapshots (
        id INTEGER PRIMARY KEY,
        subject_id INTEGER,
        curriculum_id INTEGER,
        title TEXT NOT NULL,
        ppt_url TEXT,
        video_url TEXT,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS curriculum_material_archives (
        material_id INTEGER PRIMARY KEY,
        root_url_count INTEGER NOT NULL DEFAULT 0,
        fetched_asset_count INTEGER NOT NULL DEFAULT 0,
        missing_asset_count INTEGER NOT NULL DEFAULT 0,
        all_local INTEGER NOT NULL DEFAULT 0,
        last_verified_at TEXT,
        manifest_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS curriculum_material_archive_assets (
        material_id INTEGER NOT NULL,
        asset_url TEXT NOT NULL,
        local_path TEXT NOT NULL DEFAULT '',
        status INTEGER NOT NULL DEFAULT 0,
        content_type TEXT NOT NULL DEFAULT '',
        required INTEGER NOT NULL DEFAULT 1,
        present INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (material_id, asset_url)
    );
    """
)
```

```python
def upsert_local_curriculum_material_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = self._localize_persisted_value(payload)
    with self._connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO local_curriculum_material_snapshots (
                id, subject_id, curriculum_id, title, ppt_url, video_url, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                _coerce_int(normalized.get("id")),
                _coerce_int(normalized.get("subject_id")),
                _coerce_int(normalized.get("curriculum_id")),
                str(normalized.get("title") or ""),
                str(normalized.get("ppt_url") or ""),
                str(normalized.get("video_url") or ""),
                json.dumps(normalized, ensure_ascii=False),
            ),
        )
    return self.get_local_curriculum_material_snapshot(normalized.get("id"))
```

- [ ] **Step 4: Run the storage tests to verify the new persistence works**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py -q
```

Expected: the new snapshot/archive test passes and existing storage tests remain green.

- [ ] **Step 5: Commit the persistence layer**

```powershell
git -C D:\kaifa add steam_fun/src/steamfun_mirror/storage.py steam_fun/tests/test_storage.py
git -C D:\kaifa commit -m "feat: persist course snapshot and archive state"
```

### Task 2: Import Captured Course Data Into Stable Local Tables

**Files:**
- Create: `src/steamfun_mirror/course_snapshot.py`
- Create: `scripts/build_course_snapshot.py`
- Test: `tests/test_course_snapshot.py`

- [ ] **Step 1: Write the failing snapshot import test**

```python
from pathlib import Path

from steamfun_mirror.course_snapshot import import_captured_course_domain
from steamfun_mirror.storage import MirrorStore


def test_import_captured_course_domain_populates_local_snapshot_tables(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/subject/list?t=1&campusId=851",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=b'{"success":true,"content":{"campusSubjectList":[{"id":1,"name":"Jrcode","code":1}]}}',
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/curriculum/list/by/page?t=1&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=(
            b'{"success":true,"content":{"campusAuthList":[{"id":9001,"subjectName":"Jrcode",'
            b'"curriculumInfo":{"id":3429,"subject_id":1,"title":"Summer Watermelon"}}]}}'
        ),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=(
            b'{"success":true,"content":{"curriculumMaterialList":[{"id":39525,"subject_id":1,'
            b'"curriculum_id":3429,"title":"Watermelon Fan","ppt_url":"https://wugecdn.steam.fun/a/index.html"}]}}'
        ),
    )

    summary = import_captured_course_domain(store)

    assert summary["subjects"] == 1
    assert summary["curriculums"] == 1
    assert summary["materials"] == 1
    assert store.get_local_curriculum_material_snapshot(39525)["title"] == "Watermelon Fan"
```

- [ ] **Step 2: Run the snapshot import test to verify it fails**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_course_snapshot.py::test_import_captured_course_domain_populates_local_snapshot_tables -v
```

Expected: `FAIL` with `ModuleNotFoundError` or missing `import_captured_course_domain`.

- [ ] **Step 3: Implement `course_snapshot.py` and the rebuild CLI**

```python
def import_captured_course_domain(store: MirrorStore) -> dict[str, int]:
    subject_count = 0
    curriculum_count = 0
    material_count = 0

    for subject in store.list_campus_subjects():
        if not isinstance(subject, dict):
            continue
        store.upsert_local_subject_snapshot(subject)
        subject_count += 1

    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue
        curriculum = dict(entry.get("curriculumInfo") or {})
        curriculum.setdefault("subject_id", entry.get("subject_id") or (entry.get("curriculumInfo") or {}).get("subject_id"))
        curriculum.setdefault("subject_name", entry.get("subjectName") or "")
        store.upsert_local_curriculum_snapshot(curriculum)
        curriculum_count += 1

    for material in store.list_curriculum_materials():
        if not isinstance(material, dict):
            continue
        store.upsert_local_curriculum_material_snapshot(material)
        material_count += 1

    return {"subjects": subject_count, "curriculums": curriculum_count, "materials": material_count}
```

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild local course-domain snapshot tables.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    store = MirrorStore(args.root)
    summary = import_captured_course_domain(store)
    print(json.dumps(summary, ensure_ascii=False))
```

- [ ] **Step 4: Run the snapshot import tests**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_course_snapshot.py -q
```

Expected: import summary matches the captured test data and the local snapshot tables are populated.

- [ ] **Step 5: Commit the snapshot importer**

```powershell
git -C D:\kaifa add steam_fun/src/steamfun_mirror/course_snapshot.py steam_fun/scripts/build_course_snapshot.py steam_fun/tests/test_course_snapshot.py
git -C D:\kaifa commit -m "feat: import captured course data into local snapshots"
```

### Task 3: Implement Full Recursive Course Asset Closure

**Files:**
- Modify: `src/steamfun_mirror/discovery.py`
- Create: `src/steamfun_mirror/course_archive.py`
- Create: `scripts/fetch_course_archive.py`
- Test: `tests/test_discovery.py`
- Test: `tests/test_course_archive.py`

- [x] **Step 1: Write the failing discovery and archive tests**

```python
from pathlib import Path

from steamfun_mirror.course_archive import archive_course_material
from steamfun_mirror.discovery import extract_referenced_urls
from steamfun_mirror.storage import MirrorStore


def test_extract_referenced_urls_includes_audio_video_iframe_and_css_targets() -> None:
    html = """
    <iframe src="slides/index.html"></iframe>
    <audio src="audio/intro.mp3"></audio>
    <video poster="images/poster.png"><source src="video/lesson.mp4"></video>
    <div style="background-image:url('images/bg.png')"></div>
    """

    refs = extract_referenced_urls("https://wugecdn.steam.fun/course/index.html", html)

    assert "https://wugecdn.steam.fun/course/slides/index.html" in refs
    assert "https://wugecdn.steam.fun/course/audio/intro.mp3" in refs
    assert "https://wugecdn.steam.fun/course/video/lesson.mp4" in refs
    assert "https://wugecdn.steam.fun/course/images/bg.png" in refs


def test_archive_course_material_records_missing_child_assets(tmp_path: Path, monkeypatch) -> None:
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

    payloads = {
        "https://wugecdn.steam.fun/course/index.html": (b'<script src="data/player.js"></script><audio src="data/intro.mp3"></audio>', "text/html"),
        "https://wugecdn.steam.fun/course/data/player.js": (b'console.log(\"ok\")', "application/javascript"),
    }

    def fake_fetch(url: str):
        item = payloads.get(url)
        if item is None:
            return None
        body, content_type = item
        return FakeResponse(content=body, content_type=content_type)

    monkeypatch.setattr("steamfun_mirror.course_archive._fetch_static_asset", fake_fetch)

    report = archive_course_material(store, 39525)

    assert report["material_id"] == 39525
    assert report["fetched_asset_count"] == 2
    assert report["missing_asset_count"] == 1
    assert any(row["asset_url"].endswith("intro.mp3") for row in report["missing_assets"])
```

- [x] **Step 2: Run the failing archive tests**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_discovery.py tests/test_course_archive.py -q
```

Expected: `FAIL` because discovery misses required references and `archive_course_material` does not exist yet.

- [x] **Step 3: Implement recursive archiving and per-material manifests**

```python
TEXT_REF_RE = re.compile(
    r"""(?:src|href|poster)=["']([^"']+)["']|url\(["']?([^"')]+)|fetch\(["']([^"']+)["']""",
    re.IGNORECASE,
)
```

```python
def archive_course_material(store: MirrorStore, material_id: int) -> dict[str, Any]:
    material = store.get_local_curriculum_material_snapshot(material_id) or store.find_curriculum_material(material_id) or {}
    root_urls = [url for url in (
        material.get("ppt_url"),
        material.get("stu_note_url"),
        material.get("teach_template_url"),
        material.get("home_template_url"),
        material.get("other_meterial_url"),
        material.get("video_url"),
        material.get("lession_plan_url"),
    ) if str(url or "").strip()]

    queue: deque[str] = deque(root_urls)
    seen: set[str] = set()
    present_assets: list[dict[str, Any]] = []
    missing_assets: list[dict[str, Any]] = []

    while queue:
        live_url = queue.popleft()
        if live_url in seen:
            continue
        seen.add(live_url)
        result = fetch_and_store_course_asset(store, material_id, live_url)
        if result["present"]:
            present_assets.append(result)
            if result["is_textual"]:
                for ref_url in result["referenced_urls"]:
                    if ref_url not in seen:
                        queue.append(ref_url)
        else:
            missing_assets.append(result)

    store.upsert_curriculum_material_archive(
        material_id,
        {
            "root_url_count": len(root_urls),
            "fetched_asset_count": len(present_assets),
            "missing_asset_count": len(missing_assets),
            "all_local": len(missing_assets) == 0,
            "last_verified_at": datetime.utcnow().isoformat(timespec="seconds"),
        },
    )
    store.replace_curriculum_material_archive_assets(material_id, [*present_assets, *missing_assets])
    return store.build_curriculum_material_archive_report(material_id)
```

- [x] **Step 4: Run the archive-related tests**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_discovery.py tests/test_course_archive.py -q
```

Expected: new reference extraction and recursive archive reporting both pass.

- [ ] **Step 5: Commit the archiver**

**Execution Notes (2026-06-12)**

- Real blockers fixed in this task: extensionless asset path collisions, JS/CSS false-positive reference extraction, and external JS relative asset resolution using the wrong base URL.
- Added regression coverage for `fetch("...")` references, archive ignore rules for unrelated absolute URLs, extensionless asset migration, and external JS assets that must inherit the document base when resolving `url(data/lock.cur)`-style references.
- Verified with `D:\kaifa\steam_fun\.venv\Scripts\python.exe -m pytest D:\kaifa\steam_fun	ests	est_discovery.py D:\kaifa\steam_fun	ests	est_course_archive.py D:\kaifa\steam_fun	ests	est_storage.py -q` -> `19 passed`.
- Verified with `D:\kaifa\steam_fun\.venv\Scripts\python.exe D:\kaifa\steam_fun\scriptsetch_course_archive.py --root D:\kaifa\steam_fun --material-id 17` -> `18 fetched`, `0 missing`, `all_local=true`.

```powershell
git -C D:\kaifa add steam_fun/src/steamfun_mirror/discovery.py steam_fun/src/steamfun_mirror/course_archive.py steam_fun/scripts/fetch_course_archive.py steam_fun/tests/test_discovery.py steam_fun/tests/test_course_archive.py
git -C D:\kaifa commit -m "feat: archive full recursive course assets"
```

### Task 4: Enforce Strict Local Rules For Course-Domain Runtime

**Files:**
- Create: `src/steamfun_mirror/course_offline.py`
- Modify: `src/steamfun_mirror/server.py`
- Test: `tests/test_server.py`

- [x] **Step 1: Write the failing strict-local server tests**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from steamfun_mirror.server import create_app
from steamfun_mirror.storage import MirrorStore


def test_course_external_asset_does_not_proxy_upstream_when_manifest_marks_it_missing(tmp_path: Path, monkeypatch) -> None:
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
            "fetched_asset_count": 1,
            "missing_asset_count": 1,
            "all_local": False,
            "last_verified_at": "2026-06-11T12:00:00",
        },
    )
    store.replace_curriculum_material_archive_assets(
        39525,
        [
            {
                "asset_url": "https://wugecdn.steam.fun/course/data/player.js",
                "local_path": "",
                "status": 0,
                "content_type": "",
                "required": True,
                "present": False,
            }
        ],
    )

    called = {"proxy": 0}

    def fail_proxy(*args, **kwargs):
        called["proxy"] += 1
        raise AssertionError("course strict-local mode must not proxy missing course assets")

    monkeypatch.setattr("steamfun_mirror.server._proxy_and_cache_asset", fail_proxy)

    client = TestClient(create_app(tmp_path, allow_live_proxy=True))
    response = client.get("/_external/wugecdn.steam.fun/course/data/player.js")

    assert response.status_code == 424
    assert called["proxy"] == 0
    assert "LocalCourseAssetMiss" in response.text
```

- [x] **Step 2: Run the strict-local server test to verify it fails**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_server.py::test_course_external_asset_does_not_proxy_upstream_when_manifest_marks_it_missing -v
```

Expected: `FAIL` because the current server still allows generic asset behavior instead of strict course-domain policy.

- [x] **Step 3: Implement course strict-local helpers and wire them into `server.py`**

```python
STRICT_COURSE_HOST_SUFFIXES = ("steam.fun", "wugecdn.steam.fun", "aliyuncs.com")


def is_strict_course_asset_request(store: MirrorStore, host: str, asset_path: str) -> bool:
    live_url = f"https://{host}/{asset_path.lstrip('/')}"
    return store.find_material_id_by_asset_url(live_url) is not None


def build_course_asset_miss_response(store: MirrorStore, live_url: str) -> Response:
    payload = {
        "success": False,
        "error": {
            "code": "LocalCourseAssetMiss",
            "message": f"Missing localized course asset: {live_url}",
        },
    }
    return JSONResponse(payload, status_code=424)
```

```python
if is_strict_course_asset_request(store, host, asset_path):
    live_url = _build_live_url(host, f"/{asset_path}", request.url.query)
    local_asset = store.lookup_asset(live_url)
    if local_asset is not None:
        return _static_response_or_404(store.root / local_asset["local_path"], expected_asset_path=asset_path)
    return build_course_asset_miss_response(store, live_url)
```

- [x] **Step 4: Run the server regression slice**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_server.py -q
```

Expected: the new strict-local test passes and existing course bootstrap tests stay green.

- [ ] **Step 5: Commit strict local runtime enforcement**

**Execution Notes (2026-06-12)**

- Added [`src/steamfun_mirror/course_offline.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/course_offline.py) to resolve course archive entries by exact asset URL, including query-string variants.
- `/_external/...` now checks course archive manifest state before generic proxy/synthetic handling: exact archived local file serves directly; archived-but-missing course assets return `424 COURSE_ASSET_NOT_LOCAL` and do not proxy upstream.
- This also fixes query-string course assets such as `player.js?8E49BC96`, which can now be served from indexed hashed local files instead of falling through to synthetic responses.
- Tightened generic missing-asset fallback so missing JS/CSS/fonts no longer pretend to load successfully, and shell prefetch pruning now preserves directly-present local assets on disk.
- Verified with `D:\kaifa\steam_fun\.venv\Scripts\python.exe -m pytest D:\kaifa\steam_fun	ests	est_server.py -q` -> `203 passed`.

```powershell
git -C D:\kaifa add steam_fun/src/steamfun_mirror/course_offline.py steam_fun/src/steamfun_mirror/server.py steam_fun/tests/test_server.py
git -C D:\kaifa commit -m "feat: enforce strict local rules for course runtime"
```

### Task 5: Add Offline Completeness Reports And Browser Audit

**Files:**
- Create: `src/steamfun_mirror/course_audit.py`
- Create: `scripts/course_offline_audit.py`
- Modify: `scripts/management_flow_audit.py`
- Test: `tests/test_course_audit.py`

- [x] **Step 1: Write the failing completeness and host-audit tests**

```python
from pathlib import Path

from steamfun_mirror.course_audit import build_course_offline_report
from steamfun_mirror.storage import MirrorStore


def test_build_course_offline_report_classifies_missing_material_assets(tmp_path: Path) -> None:
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
        },
    )

    report = build_course_offline_report(store)

    assert report["summary"]["total_materials"] == 1
    assert report["summary"]["missing_resource_materials"] == 1
    assert report["materials"][0]["status"] == "missing_resource"
```

- [x] **Step 2: Run the failing audit test**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_course_audit.py::test_build_course_offline_report_classifies_missing_material_assets -v
```

Expected: `FAIL` with missing module/function.

- [x] **Step 3: Implement the report builder and browser audit CLI**

```python
def build_course_offline_report(store: MirrorStore) -> dict[str, Any]:
    materials: list[dict[str, Any]] = []
    missing_resource_materials = 0

    for material in store.list_local_curriculum_material_snapshots():
        archive = store.get_curriculum_material_archive(material["id"]) or {}
        archive_row = archive.get("archive") or {}
        missing_count = int(archive_row.get("missing_asset_count") or 0)
        status = "passed" if missing_count == 0 else "missing_resource"
        if status == "missing_resource":
            missing_resource_materials += 1
        materials.append(
            {
                "material_id": material["id"],
                "title": material["title"],
                "status": status,
                "missing_asset_count": missing_count,
            }
        )

    return {
        "summary": {
            "total_materials": len(materials),
            "missing_resource_materials": missing_resource_materials,
        },
        "materials": materials,
    }
```

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Audit offline readiness of localized course materials.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=ROOT / "runtime" / "course_offline_report.json")
    args = parser.parse_args()
    store = MirrorStore(args.root)
    report = build_course_offline_report(store)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
```

- [x] **Step 4: Run the audit tests and browser flow audit**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_course_audit.py -q
.\.venv\Scripts\python.exe scripts\course_offline_audit.py --root D:\kaifa\steam_fun
```

Expected: unit tests pass and the CLI prints a JSON summary with `total_materials` and `missing_resource_materials`.

- [ ] **Step 5: Commit audit/report tooling**

**Execution Notes (2026-06-12)**

- Added [`src/steamfun_mirror/course_audit.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/course_audit.py) and [`scripts/course_offline_audit.py`](/D:/kaifa/steam_fun/scripts/course_offline_audit.py); the offline report now summarizes `total_materials`, `missing_resource_materials`, `not_archived_materials`, and archived source hosts.
- Verified with `D:/kaifa/steam_fun/.venv/Scripts/python.exe D:/kaifa/steam_fun/scripts/course_offline_audit.py --root D:/kaifa/steam_fun` -> `{"total_materials": 630, "missing_resource_materials": 0, "not_archived_materials": 0, "upstream_host_count": 3, ...}`.
- Verified archived material closure with `D:/kaifa/steam_fun/runtime/course_archive_full_summary.json` -> `requested_material_count=630`, `archived_material_count=630`, `failed_material_count=0`, `total_missing_assets=0`.
- The reported `upstream_hosts` describe archived source metadata only; runtime verification for the management and course flows was completed later under `--no-live-proxy` against local paths on `127.0.0.1:8000`.

**Execution Notes (2026-06-13, strict PPT runtime audit)**

- User-reported PPT failures were narrowed to runtime iSpring assets declared inside `presInfo`, especially `data/slide*.js`, `data/slide*.css`, and `data/fnt*.woff`.
- Added regression coverage in [`tests/test_course_audit.py`](/D:/kaifa/steam_fun/tests/test_course_audit.py) for the case where an archive looks `all_local=true` but only contains a partial runtime subset from `presInfo`.
- Tightened [`src/steamfun_mirror/course_audit.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/course_audit.py) so offline audit now reads archived `index.html`, decodes `presInfo`, and flags the material as `missing_resource` if any declared `slide/css/font` runtime asset is absent from `curriculum_material_archive_assets`.
- This exposed that the previous `missing_resource_materials: 0` result was an under-report: it only proved the archive shell existed, not that PPT runtime assets were complete.
- Fresh strict audit on `2026-06-13` reported `{"total_materials":630,"missing_resource_materials":486,"not_archived_materials":0,...}` while a long-running rearchive was still in progress. Earlier in the same run, the strict count had already dropped from `558` to `496`, then to `491`, and then to `486`, confirming the recursive rearchive pipeline is repairing real PPT runtime gaps rather than only changing metadata.
- Empirical rearchive samples:
  - `174 足球小将`: `fetched_asset_count` `18 -> 177`
  - `310 汽车组装`: `fetched_asset_count` `19 -> 337`
  - `39525 西瓜风扇大作战`: `fetched_asset_count` `19 -> 211`
- For each of those samples, the post-rearchive `presInfo`-declared runtime asset set had `missing_after_rearchive = 0`.
- Real browser strict audits on `http://127.0.0.1:8000/code-classroom/teach-lessons/lessons/ppt` with `curriculumMaterial_id in {2065, 14624, 6533, 174, 310, 39525}` all returned:
  - `bad_responses=[]`
  - `failed_requests=[]`
  - `console_errors=[]`
  - `page_errors=[]`
- Current conclusion: the core PPT problem is not a remaining frontend route bug. It is a historical archive-completeness problem affecting hundreds of PPT materials whose runtime `slide/css/font` assets were never fully localized. The repair path is confirmed: strict audit + recursive rearchive + browser revalidation.
- Completion checkpoint after the full recursive rearchive:
  - `D:/kaifa/steam_fun/.venv/Scripts/python.exe D:/kaifa/steam_fun/scripts/course_offline_audit.py --root D:/kaifa/steam_fun`
  - Output: `{"total_materials":630,"missing_resource_materials":0,"not_archived_materials":0,...}`
- Independent database-level verification after the same run:
  - `ppt_materials = 630`
  - `checked_with_presinfo = 609`
  - `materials_with_missing_declared_runtime = 0`
- Final strict browser sampling on `2026-06-13` covered user-reported samples plus high-asset-count samples:
  - `2065 花样滑冰-舞蹈艺术家-上`
  - `14624 查牙山洞寻宝记`
  - `6533 大红灯笼高高挂`
  - `174 足球小将`
  - `310 汽车组装`
  - `39525 西瓜风扇大作战`
  - `712 四方争霸2`
  - `14657 四方争霸1`
  - `35130 哪吒大战无量仙翁`
  - `58951 骐骥送福记`
- Every sampled PPT page returned:
  - `bad_responses=[]`
  - `failed_requests=[]`
  - `console_errors=[]`
  - `page_errors=[]`

**Execution Notes (2026-06-13, legacy iSpring text + classroom interaction re-audit)**

- User-reported residual PPT failures were narrowed again and split into two different categories:
  - PPT body rendering: no longer a missing-asset problem after the full recursive rearchive.
  - A small subset of older iSpring exports still rendered text vertically/wrapped incorrectly in local Chromium because the text layer lived under `width:0px` containers with `white-space: normal`.
- Added `LEGACY_ISPRING_TEXT_LAYOUT_GUARD` to [`src/steamfun_mirror/server.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/server.py) and injected it through `_inject_runtime_guards`.
  - The guard scans `span[id^="txt"]` nodes in legacy iSpring decks.
  - When a node is absolutely positioned, declares a positive `data-width`, but collapses under a `width:0px` parent and becomes multi-line, the guard forces both parent and child text flow to `white-space: nowrap`.
- Added regression coverage in [`tests/test_server.py`](/D:/kaifa/steam_fun/tests/test_server.py):
  - `test_rewrite_body_injects_legacy_ispring_text_nowrap_guard`
  - `test_rewrite_body_injects_classroom_loading_feedback_guard`
- Real browser PPT re-audit against the local offline server:
  - Artifact: `D:/kaifa/steam_fun/runtime/ppt_legacy_text_fix_20260613_225111/summary.json`
  - Sampled materials: `104`, `398`, `14603`
  - All three returned:
    - `console_errors=[]`
    - `page_errors=[]`
    - `failed_requests=[]`
    - `bad_responses=[]`
  - `398` was the key user-reported broken sample; the latest screenshot confirms the title text is restored to horizontal layout instead of vertical/wrapped corruption.
- Added `CLASSROOM_LOADING_FEEDBACK_GUARD` to [`src/steamfun_mirror/server.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/server.py) so classroom PPT pages now show an immediate loading overlay after clicking the right-hand tool actions.
  - The overlay is mounted safely onto `document.body || document.documentElement`.
  - Existing and dynamically created iframes are watched so the overlay closes after content becomes ready.
  - The guard was adjusted after a real-browser failure where `appendChild` hit `null`; that error is no longer present.
- Real browser interaction audit for the right-hand PPT tools:
  - Artifact: `D:/kaifa/steam_fun/runtime/ppt_loading_feedback_20260613_232445/summary.json`
  - Verified actions: `class_result`, `teach_template`, `student_handout`, `start_create`
  - Overlay appears within about `600ms` after click in all sampled actions.
  - Overlay closes again once the target drawer/popup/page is ready.
  - Latest result:
    - `console_errors=[]`
    - `page_errors=[]`
    - `bad_responses=[]`
  - `student_handout` still records `net::ERR_ABORTED`, but only because the browser hands the localized PDF off as a download/open action; there is no `404`, `4xx`, `5xx`, or missing local resource behind it.
- Additional direct browser audit on `2026-06-13` re-confirmed that the current offline classroom routes can be opened directly without a prior manual login hop:
  - Artifact: `D:/kaifa/steam_fun/runtime/course_ppt_direct_audit_20260613_234626/summary.json`
  - Materials `104`, `398`, `14603` again returned:
    - `console_errors=[]`
    - `page_errors=[]`
    - `failed_requests=[]`
    - `bad_responses=[]`
  - This was important because an older audit probe had started failing at the login page after that page defaulted to the student tab. The classroom pages themselves were still healthy; the broken part was the audit script's login assumption, not the course runtime.
- Full click-flow audit for a representative localized course (`39525`) confirms the right-hand course actions are wired into local targets in both `prepare_ppt` and `teach_ppt` views:
  - Artifact: `D:/kaifa/steam_fun/runtime/click_audit_20260613_235057/results.json`
  - Confirmed working local targets:
    - `课堂成果` -> local `jrcode/teachjr.html`
    - `授课模板` -> local `jrcode/teachjr.html`
    - `作业模板` -> local `jrcode/teachjr.html`
    - `学习资料` -> local archived PPT resource URL
    - `学生讲义` -> local archived PDF download/open
    - `开始创作` -> local `jrcode/teachjrwork.html` popup
  - No action redirected back to `/login`.
  - No action produced `bad_responses`.
  - The remaining `net::ERR_ABORTED` events are limited to browser-controlled media/PDF handoff cases and did not correspond to broken local assets.

**Execution Notes (2026-06-15, teachplan fallback repair + interaction timing re-audit)**

- A fresh user-driven browser interaction audit exposed a real local functional gap that the broader management audit had not hit:
  - Clicking `教学计划` from the class-management route issued `GET /api/get/teaching/plan/list?...`
  - The local server returned `404`, producing:
    - console error `Failed to load resource: the server responded with a status of 404 (Not Found)`
    - page error `Error: Request failed with status code 404`
  - Evidence before repair: [`runtime/interactive_audit_20260615/summary.json`](/D:/kaifa/steam_fun/runtime/interactive_audit_20260615/summary.json)
- Root cause was not missing data. It was a local fallback routing gap:
  - [`src/steamfun_mirror/server.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/server.py) already handled `/api/tch/get/teaching/plan/list`
  - but did not treat `/api/get/teaching/plan/list` as an equivalent local teacher fallback path.
- Added regression coverage in [`tests/test_server.py`](/D:/kaifa/steam_fun/tests/test_server.py):
  - `test_teacher_get_teaching_plan_list_uses_local_fallback_for_filtered_calendar_query`
  - This reproduces the real browser calendar query shape with `campusIds`, `end_class_state`, `start_date`, and `end_date`.
- Repaired local runtime handling in [`src/steamfun_mirror/server.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/server.py):
  - added `/api/get/teaching/plan/list` to `LOCAL_TEACHER_FALLBACK_PATHS`
  - added `/api/get/teaching/plan/list` to `LOCAL_TEACHER_PREFER_LOCAL_FALLBACK_PATHS`
  - made `/api/get/teaching/plan/list` reuse the same local teaching-plan payload builder as `/api/tch/get/teaching/plan/list`
- Verified the fix with fresh regression evidence:
  - `D:/kaifa/steam_fun/.venv/Scripts/python.exe -m pytest D:/kaifa/steam_fun/tests/test_server.py -k "test_teacher_get_teaching_plan_list_uses_local_fallback_for_filtered_calendar_query or test_teacher_get_teaching_plan_list_uses_local_fallback_for_class_page or test_teacher_teaching_plan_list_returns_class_detail_shape_for_class_page" -q` -> `3 passed`
  - `D:/kaifa/steam_fun/.venv/Scripts/python.exe -m pytest D:/kaifa/steam_fun/tests/test_server.py -k "teacher_teaching_plan_list or teaching_plan_list" -q` -> `4 passed`
- Re-ran the real browser management audit after the fallback repair:
  - Artifact: [`runtime/management_flow_audit_20260615_062448/summary.json`](/D:/kaifa/steam_fun/runtime/management_flow_audit_20260615_062448/summary.json)
  - Result: `all_passed=true`
  - Strict local network evidence remained clean:
    - `external_request_count=0`
    - `failed_response_count=0`
    - `page_error_count=0`
    - `console_error_count=0`
- Re-ran acceptance artifacts after the repair:
  - Artifacts: [`runtime/acceptance_20260615_062448/results.json`](/D:/kaifa/steam_fun/runtime/acceptance_20260615_062448/results.json), [`runtime/acceptance_20260615_062448/teachplan_list_view.json`](/D:/kaifa/steam_fun/runtime/acceptance_20260615_062448/teachplan_list_view.json)
  - `teachplan` page and list-view toggle both rendered from local runtime artifacts without a `404`.
- Re-audited the user-visible loading feedback for classroom PPT side actions:
  - Earlier timing probes showed `学生讲义` and `开始创作` appearing to show feedback only after about `10s`, while `课堂成果` appeared almost immediately.
  - Root-cause analysis showed the old guard relied too heavily on later mutation/iframe signals for some actions, so user perception could lag behind the actual click.
  - Updated [`src/steamfun_mirror/server.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/server.py) so the loading overlay arms on `pointerdown` as well as `click`, with short de-duplication to prevent double pulses.
  - Added regression assertions to `test_rewrite_body_injects_classroom_loading_feedback_guard` so this earlier trigger is not lost.
- Fresh targeted browser timing re-check after the guard update:
  - `学生讲义` first visible loading overlay: about `132ms`
  - `开始创作` first visible loading overlay in isolated re-check: about `85ms`
  - `课堂成果` first visible loading overlay: about `131ms`
  - These isolated checks confirm the slow-feedback symptom was reduced to immediate local acknowledgment on click instead of multi-second silent waiting.

- Fresh strict admin preview browser re-audit confirmed the campus-management PPT preview chain is repaired in the real local runtime, not only in unit tests:
  - Artifact: [`runtime/admin_preview_verify_20260615/result.json`](/D:/kaifa/steam_fun/runtime/admin_preview_verify_20260615/result.json)
  - Artifact: [`runtime/admin_preview_verify_20260615/preview_page.png`](/D:/kaifa/steam_fun/runtime/admin_preview_verify_20260615/preview_page.png)
  - Logged in as admin `18164173640`, opened `/background/course-management/preview-curriculum?id=16&type=正常`, and confirmed the page rendered `32` lesson rows.
  - The admin preview page itself completed with:
    - `failed_response_count=0`
    - `console_error_count=0`
    - `page_error_count=0`
    - `aliyun_sts_request_count=0`
- Fresh click-through verification from that repaired admin preview path confirmed the first `预览` action now lands on the full local PPT classroom page:
  - Artifact: [`runtime/admin_preview_click_verify2_20260615/result.json`](/D:/kaifa/steam_fun/runtime/admin_preview_click_verify2_20260615/result.json)
  - Artifact: [`runtime/admin_preview_click_verify2_20260615/after_click.png`](/D:/kaifa/steam_fun/runtime/admin_preview_click_verify2_20260615/after_click.png)
  - Final browser URL after click:
    - `/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=171&teaching_plan_id=999999`
  - Strict network/runtime evidence for that click path:
    - `look_curriculum_request_count=0`
    - `aliyun_sts_request_count=0`
    - `prepare_ppt_request_count=1`
    - `failed_response_count=0`
    - `console_error_count=0`
    - `page_error_count=0`
  - The rendered destination was the complete local PPT classroom view with central PPT player, right-side `师训视频`, and the expected teaching actions such as `课堂成果`, `授课模板`, `作业模板`, `学生讲义`, and `开始创作`.

```powershell
git -C D:\kaifa add steam_fun/src/steamfun_mirror/course_audit.py steam_fun/scripts/course_offline_audit.py steam_fun/scripts/management_flow_audit.py steam_fun/tests/test_course_audit.py
git -C D:\kaifa commit -m "feat: add offline course completeness audit"
```

### Task 6: Document And Run The Full Archive -> Offline Verification Workflow

**Files:**
- Modify: `README.md`

- [x] **Step 1: Add the operator runbook to `README.md`**

```markdown
## Course Offline Workflow

1. Rebuild local course snapshot tables:
   `.\.venv\Scripts\python.exe scripts\build_course_snapshot.py --root D:\kaifa\steam_fun`
2. Fetch every required course asset while online:
   `.\.venv\Scripts\python.exe scripts\fetch_course_archive.py --root D:\kaifa\steam_fun`
3. Generate the offline completeness report:
   `.\.venv\Scripts\python.exe scripts\course_offline_audit.py --root D:\kaifa\steam_fun`
4. Start the local server without upstream proxy:
   `.\.venv\Scripts\python.exe -m steamfun_mirror --root D:\kaifa\steam_fun serve --host 127.0.0.1 --port 8000 --no-live-proxy`
5. Run browser verification for class selection, teaching-plan, and student-entry flows in offline mode.
```

- [x] **Step 2: Run the full local verification sequence**

Run:

```powershell
cd D:\kaifa\steam_fun
.\.venv\Scripts\python.exe scripts\build_course_snapshot.py --root D:\kaifa\steam_fun
.\.venv\Scripts\python.exe scripts\fetch_course_archive.py --root D:\kaifa\steam_fun
.\.venv\Scripts\python.exe scripts\course_offline_audit.py --root D:\kaifa\steam_fun
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py tests/test_course_snapshot.py tests/test_discovery.py tests/test_course_archive.py tests/test_server.py tests/test_course_audit.py -q
```

Expected:

- Snapshot import prints non-zero course counts
- Course archive run prints zero unresolved assets for accepted materials, or a concrete miss list to fix
- Audit report prints a summary with `missing_resource_materials: 0` for the completed scope
- All listed tests pass

- [x] **Step 3: Run offline browser acceptance**

Run:

```powershell
cd D:\kaifa\steam_fun
powershell -File scripts\run_server.ps1 -Port 8000 -NoLiveProxy
.\.venv\Scripts\python.exe scripts\management_flow_audit.py
```

Expected:

- The generated report shows the class-selection -> teaching-plan -> student-entry -> teach-ppt chain passes
- The course-domain host audit shows no requests to `steam.fun`, `wugecdn.steam.fun`, or `*.aliyuncs.com`

- [x] **Step 4: Record the final deliverables**

```text
runtime/course_offline_report.json
runtime/course_archive_manifest/
runtime/management_flow_audit_*/
runtime/mirror.sqlite3
```

- [ ] **Step 5: Commit the runbook update**

**Execution Notes (2026-06-12)**

- Browser acceptance blocker root cause was a historical syntax corruption in local bundle `origin/steam.fun/js/app.f5edd84f.js`: the `App` route watcher contained `e.name)){`, which produced `Unexpected token ')'` before the management page could boot.
- Added regression test `test_static_javascript_repairs_known_route_watcher_syntax_regression` and a narrow runtime bundle repair in [`src/steamfun_mirror/server.py`](/D:/kaifa/steam_fun/src/steamfun_mirror/server.py) so the damaged watcher fragment is repaired before serving local JS.
- Re-verified the management page after restart: `/school-home-page/class-management1/students-management1` had no `pageerror`, rendered 81 table rows, and issued local `/api/` and `/java-api/` requests through `http://127.0.0.1:8000`.
- Verified browser acceptance with `D:/kaifa/steam_fun/.venv/Scripts/python.exe D:/kaifa/steam_fun/scripts/management_flow_audit.py` -> [`runtime/management_flow_audit_20260612_051504/summary.json`](/D:/kaifa/steam_fun/runtime/management_flow_audit_20260612_051504/summary.json) where `admin_page.passed=true`, `student_validity_flow.passed=true`, `class_flow.passed=true`, and `all_passed=true`.
- Verified server regression with `D:/kaifa/steam_fun/.venv/Scripts/python.exe -m pytest D:/kaifa/steam_fun/tests/test_server.py -q` -> `205 passed`.
- Verified full selected regression with `D:/kaifa/steam_fun/.venv/Scripts/python.exe -m pytest D:/kaifa/steam_fun/tests/test_storage.py D:/kaifa/steam_fun/tests/test_course_snapshot.py D:/kaifa/steam_fun/tests/test_discovery.py D:/kaifa/steam_fun/tests/test_course_archive.py D:/kaifa/steam_fun/tests/test_server.py D:/kaifa/steam_fun/tests/test_course_audit.py -q` -> `228 passed`.
- Added strict browser-runtime evidence to `management_flow_audit.py`; verified with [`runtime/management_flow_audit_20260612_210802/summary.json`](/D:/kaifa/steam_fun/runtime/management_flow_audit_20260612_210802/summary.json) that `strict_local_passed=true`, `external_request_count=0`, `failed_response_count=0`, `page_error_count=0`, and `console_error_count=0`.
- Fresh strict rerun completed with `D:/kaifa/steam_fun/.venv/Scripts/python.exe D:/kaifa/steam_fun/scripts/course_offline_audit.py --root D:/kaifa/steam_fun` -> `{"total_materials":630,"missing_resource_materials":0,"not_archived_materials":0,...}` and `D:/kaifa/steam_fun/.venv/Scripts/python.exe D:/kaifa/steam_fun/scripts/management_flow_audit.py` -> [`runtime/management_flow_audit_20260612_211731/summary.json`](/D:/kaifa/steam_fun/runtime/management_flow_audit_20260612_211731/summary.json), again confirming `all_passed=true`, `external_request_count=0`, `failed_response_count=0`, `page_error_count=0`, and `console_error_count=0`.
- Verified targeted strict-audit regression slice after the fresh rerun with `D:/kaifa/steam_fun/.venv/Scripts/python.exe -m pytest D:/kaifa/steam_fun/tests/test_course_audit.py D:/kaifa/steam_fun/tests/test_server.py -q -k "route_watcher_syntax_regression or course_audit"` -> `5 passed`.

```powershell
git -C D:\kaifa add steam_fun/README.md
git -C D:\kaifa commit -m "docs: document offline course localization workflow"
```

---

## Self-Review

### Spec coverage

- Local structured course truth: covered by Tasks 1 and 2.
- Recursive full asset closure: covered by Task 3.
- Strict local course runtime: covered by Task 4.
- Completeness reporting and offline verification: covered by Tasks 5 and 6.
- Recorded operator workflow and deliverables: covered by Task 6.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each task names exact files and concrete commands.
- Each code-bearing step includes example code instead of abstract instructions.

### Type consistency

- Snapshot helpers use `upsert_local_*_snapshot` naming consistently.
- Archive helpers use `upsert_curriculum_material_archive` and `replace_curriculum_material_archive_assets`.
- Audit helpers use `build_course_offline_report` consistently across tests and CLI references.
