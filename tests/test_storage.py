from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from steamfun_mirror.storage import MirrorStore


EXTERNAL_AVATAR_URL = "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
LOCAL_AVATAR_URL = "/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"


def test_local_campus_upsert_preserves_id_sparse_fields_and_state(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    created = store.upsert_local_campus(
        {
            "id": 851,
            "name": "中心校区",
            "address": "科创路 1 号",
            "phone": "021-55550000",
            "state": 1,
        }
    )
    disabled = store.upsert_local_campus({"id": 851, "state": 0})

    assert created == {
        "id": 851,
        "name": "中心校区",
        "address": "科创路 1 号",
        "phone": "021-55550000",
        "state": 1,
    }
    assert disabled["name"] == "中心校区"
    assert disabled["state"] == 0
    assert MirrorStore(tmp_path).list_local_campuses() == [disabled]


def test_local_campus_requires_name_when_creating(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    try:
        store.upsert_local_campus({"id": 852, "state": 1})
    except ValueError as exc:
        assert str(exc) == "Campus name is required"
    else:
        raise AssertionError("Expected a missing campus name to be rejected")


def test_store_profile_localizes_nested_external_urls_before_persisting(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    store.store_profile(
        profile_name="teacher",
        username="teacher",
        password_hash="hash",
        login_path="/java-api/school/tch/login",
        token="teacher-token",
        login_content={"avatar": EXTERNAL_AVATAR_URL, "bundle": "https://steam.fun/js/app.js"},
        fresh_auth={"userInfo": {"userImageUrl": EXTERNAL_AVATAR_URL}},
        vuex_state={"user": {"userInfo": {"userImageUrl": EXTERNAL_AVATAR_URL}}},
    )

    profile = store.get_profile("teacher")
    assert profile is not None
    assert profile["login_content"]["avatar"] == LOCAL_AVATAR_URL
    assert profile["login_content"]["bundle"] == "/js/app.js"
    assert profile["fresh_auth"]["userInfo"]["userImageUrl"] == LOCAL_AVATAR_URL
    assert profile["vuex_state"]["user"]["userInfo"]["userImageUrl"] == LOCAL_AVATAR_URL

    with sqlite3.connect(store.db_path) as connection:
        row = connection.execute(
            "SELECT login_content_json, fresh_auth_json, vuex_json FROM profiles WHERE profile_name = 'teacher'"
        ).fetchone()

    assert row is not None
    assert EXTERNAL_AVATAR_URL not in row[0]
    assert EXTERNAL_AVATAR_URL not in row[1]
    assert EXTERNAL_AVATAR_URL not in row[2]
    assert LOCAL_AVATAR_URL in row[0]
    assert LOCAL_AVATAR_URL in row[1]
    assert LOCAL_AVATAR_URL in row[2]


def test_init_db_migrates_legacy_profile_json_to_local_urls(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO profiles (
                profile_name, username, password_hash, login_path, token,
                login_content_json, fresh_auth_json, vuex_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "teacher",
                "teacher",
                "hash",
                "/java-api/school/tch/login",
                "teacher-token",
                json.dumps({"avatar": EXTERNAL_AVATAR_URL}, ensure_ascii=False),
                json.dumps({"userInfo": {"userImageUrl": EXTERNAL_AVATAR_URL}}, ensure_ascii=False),
                json.dumps({"user": {"userInfo": {"userImageUrl": EXTERNAL_AVATAR_URL}}}, ensure_ascii=False),
            ),
        )

    reopened = MirrorStore(tmp_path)
    profile = reopened.get_profile("teacher")
    assert profile is not None
    assert profile["login_content"]["avatar"] == LOCAL_AVATAR_URL
    assert profile["fresh_auth"]["userInfo"]["userImageUrl"] == LOCAL_AVATAR_URL
    assert profile["vuex_state"]["user"]["userInfo"]["userImageUrl"] == LOCAL_AVATAR_URL

    with sqlite3.connect(reopened.db_path) as connection:
        row = connection.execute(
            "SELECT login_content_json, fresh_auth_json, vuex_json FROM profiles WHERE profile_name = 'teacher'"
        ).fetchone()

    assert row is not None
    assert EXTERNAL_AVATAR_URL not in row[0]
    assert EXTERNAL_AVATAR_URL not in row[1]
    assert EXTERNAL_AVATAR_URL not in row[2]
    assert LOCAL_AVATAR_URL in row[0]
    assert LOCAL_AVATAR_URL in row[1]
    assert LOCAL_AVATAR_URL in row[2]


def test_create_local_student_localizes_external_avatar_url(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "name": "mirror-student",
            "realName": "Mirror Student",
            "sex": "M",
            "normalState": "1",
            "parentAPhoneNum": "13800138000",
            "schoolName": "Mirror School",
            "grade": "6",
            "leader": "Teacher Li",
            "remark": "",
            "studyDate": "2026-05-15",
            "headimgUrl": EXTERNAL_AVATAR_URL,
        }
    )

    assert student["headimg_url"] == LOCAL_AVATAR_URL

    rows = store.list_local_students()
    assert len(rows) == 1
    assert rows[0]["headimg_url"] == LOCAL_AVATAR_URL


def test_next_local_ids_skip_deleted_class_and_teaching_plan_rows(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    reusable_class_id = store.next_class_id()
    store.upsert_local_class(
        {
            "id": reusable_class_id,
            "className": "Deleted Seed Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    store.upsert_local_class({"id": reusable_class_id, "deleted": 1})

    reusable_plan_id = store.next_teaching_plan_id()
    store.upsert_local_teaching_plan(
        {
            "id": reusable_plan_id,
            "curriculum_class_id": 3001,
            "subject_id": 1,
            "curriculum_id": 501,
            "curriculum_meterial_id": 7001,
            "class_date": "2026-05-24",
            "start_class_date": "2026-05-24 09:00:00",
            "end_class_date": "2026-05-24 10:30:00",
            "sort_num": 1,
            "custom_lesson_title": "Deleted Seed Lesson",
        }
    )
    store.mark_teaching_plan_deleted(reusable_plan_id)

    assert store.next_class_id() == reusable_class_id + 1
    assert store.next_teaching_plan_id() == reusable_plan_id + 1


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


def test_course_snapshot_upserts_merge_sparse_updates_and_survive_reopen(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    store.upsert_local_subject_snapshot({"id": 1, "name": "Jrcode", "code": 1, "sort_num": 3})
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
            "img_url": "/_external/wugecdn.steam.fun/courses/a/poster.png",
        }
    )

    store.upsert_local_subject_snapshot({"id": 1, "code": 2})
    store.upsert_local_curriculum_snapshot({"id": 3429, "title": "Summer Watermelon Updated"})
    store.upsert_local_curriculum_material_snapshot({"id": 39525, "title": "Watermelon Fan Updated"})

    reopened = MirrorStore(tmp_path)
    subject = reopened.get_local_subject_snapshot(1)
    curriculum = reopened.get_local_curriculum_snapshot(3429)
    material = reopened.get_local_curriculum_material_snapshot(39525)

    assert subject is not None
    assert subject["name"] == "Jrcode"
    assert subject["code"] == 2
    assert subject["sort_num"] == 3

    assert curriculum is not None
    assert curriculum["subject_id"] == 1
    assert curriculum["title"] == "Summer Watermelon Updated"
    assert curriculum["img_url"] == "/_external/wugecdn.steam.fun/courses/poster.png"
    assert curriculum["number_of_courses"] == 8

    assert material is not None
    assert material["subject_id"] == 1
    assert material["curriculum_id"] == 3429
    assert material["title"] == "Watermelon Fan Updated"
    assert material["ppt_url"] == "/_external/wugecdn.steam.fun/courses/a/index.html"
    assert material["video_url"] == "/_external/wugecdn.steam.fun/courses/a/video.mp4"
    assert material["img_url"] == "/_external/wugecdn.steam.fun/courses/a/poster.png"


def test_curriculum_material_archive_assets_replace_deduplicates_and_reopens_cleanly(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    store.upsert_curriculum_material_archive(
        39525,
        {
            "root_url_count": 2,
            "fetched_asset_count": 2,
            "missing_asset_count": 0,
            "all_local": True,
            "last_verified_at": "2026-06-11T12:00:00",
        },
    )
    store.replace_curriculum_material_archive_assets(
        39525,
        [
            {
                "asset_url": "https://wugecdn.steam.fun/courses/a/index.html",
                "local_path": "external/wugecdn.steam.fun/courses/a/index-v1.html",
                "status": 200,
                "content_type": "text/html",
                "required": True,
                "present": True,
            },
            {
                "asset_url": "https://wugecdn.steam.fun/courses/a/index.html",
                "local_path": "external/wugecdn.steam.fun/courses/a/index-v2.html",
                "status": 200,
                "content_type": "text/html",
                "required": True,
                "present": True,
            },
            {
                "asset_url": "https://wugecdn.steam.fun/courses/a/data/player.js",
                "local_path": "external/wugecdn.steam.fun/courses/a/data/player.js",
                "status": 200,
                "content_type": "application/javascript",
                "required": False,
                "present": True,
            },
        ],
    )

    first_archive = store.get_curriculum_material_archive(39525)

    assert first_archive is not None
    assert first_archive["archive"]["all_local"] is True
    assert isinstance(first_archive["archive"]["all_local"], bool)
    assert len(first_archive["assets"]) == 2
    assert sum(1 for row in first_archive["assets"] if row["asset_url"].endswith("index.html")) == 1

    html_asset = next(row for row in first_archive["assets"] if row["asset_url"].endswith("index.html"))
    js_asset = next(row for row in first_archive["assets"] if row["asset_url"].endswith("player.js"))

    assert html_asset["local_path"].endswith("index-v2.html")
    assert html_asset["required"] is True
    assert html_asset["present"] is True
    assert isinstance(html_asset["required"], bool)
    assert isinstance(html_asset["present"], bool)
    assert js_asset["required"] is False
    assert js_asset["present"] is True

    store.replace_curriculum_material_archive_assets(
        39525,
        [
            {
                "asset_url": "https://wugecdn.steam.fun/courses/a/audio.mp3",
                "local_path": "external/wugecdn.steam.fun/courses/a/audio.mp3",
                "status": 200,
                "content_type": "audio/mpeg",
                "required": True,
                "present": False,
            }
        ],
    )

    reopened = MirrorStore(tmp_path)
    archive = reopened.get_curriculum_material_archive(39525)

    assert archive is not None
    assert archive["archive"]["all_local"] is True
    assert isinstance(archive["archive"]["all_local"], bool)
    assert len(archive["assets"]) == 1
    assert archive["assets"][0]["asset_url"].endswith("audio.mp3")
    assert archive["assets"][0]["required"] is True
    assert archive["assets"][0]["present"] is False


def test_replace_curriculum_material_archive_assets_creates_parent_archive_row(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    store.replace_curriculum_material_archive_assets(
        50001,
        [
            {
                "asset_url": "https://wugecdn.steam.fun/courses/z/index.html",
                "local_path": "external/wugecdn.steam.fun/courses/z/index.html",
                "status": 200,
                "content_type": "text/html",
                "required": True,
                "present": True,
            }
        ],
    )

    with sqlite3.connect(store.db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(1) FROM curriculum_material_archives WHERE material_id = ?",
            (50001,),
        ).fetchone()

    assert row is not None
    assert row[0] == 1


def test_course_snapshot_upserts_allow_explicit_clear_of_optional_fields(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

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

    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39525,
            "ppt_url": "",
            "video_url": None,
        }
    )

    reopened = MirrorStore(tmp_path)
    material = reopened.get_local_curriculum_material_snapshot(39525)

    assert material is not None
    assert material["ppt_url"] == ""
    assert material["video_url"] == ""


def test_store_external_assets_allow_extensionless_parent_and_descendant_paths(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    parent_path = store.store_external_asset(
        "https://github.com/zloirock/core-js",
        b'console.log("root");',
        headers={"content-type": "application/javascript; charset=utf-8"},
    )
    child_path = store.store_external_asset(
        "https://github.com/zloirock/core-js/internals/to-object",
        b'export default "child";',
        headers={"content-type": "application/javascript; charset=utf-8"},
    )

    parent_asset = store.lookup_asset("https://github.com/zloirock/core-js")
    child_asset = store.lookup_asset("https://github.com/zloirock/core-js/internals/to-object")

    assert parent_path != child_path
    assert parent_asset is not None
    assert child_asset is not None
    assert (store.root / parent_asset["local_path"]).is_file()
    assert (store.root / child_asset["local_path"]).is_file()
    assert parent_asset["body"] == b'console.log("root");'
    assert child_asset["body"] == b'export default "child";'


def test_store_external_assets_migrates_legacy_extensionless_conflicts(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    legacy_relative_path = "external/github.com/zloirock/core-js"
    legacy_path = store.root / legacy_relative_path
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_body = b'console.log("legacy");'
    legacy_path.write_bytes(legacy_body)

    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO assets (url, local_path, status, content_type, sha256)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "https://github.com/zloirock/core-js",
                legacy_relative_path,
                200,
                "application/javascript; charset=utf-8",
                "legacy-digest",
            ),
        )

    child_path = store.store_external_asset(
        "https://github.com/zloirock/core-js/internals/to-object",
        b'export default "child";',
        headers={"content-type": "application/javascript; charset=utf-8"},
    )

    migrated_parent_asset = store.lookup_asset("https://github.com/zloirock/core-js")
    child_asset = store.lookup_asset("https://github.com/zloirock/core-js/internals/to-object")

    assert child_path == "external/github.com/zloirock/core-js/internals/to-object__asset__.js"
    assert migrated_parent_asset is not None
    assert migrated_parent_asset["local_path"] == "external/github.com/zloirock/core-js__asset__.js"
    assert (store.root / migrated_parent_asset["local_path"]).is_file()
    assert migrated_parent_asset["body"] == legacy_body
    assert child_asset is not None
