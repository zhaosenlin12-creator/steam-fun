from __future__ import annotations

import json
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
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "content": {
                    "campusSubjectList": [
                        {
                            "id": 1,
                            "name": "Jrcode",
                            "code": 1,
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/curriculum/list/by/page?t=1&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "content": {
                    "campusAuthList": [
                        {
                            "curriculumInfo": {
                                "id": 3429,
                                "subject_id": 1,
                                "title": "Summer Watermelon",
                            }
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 39525,
                            "subject_id": 1,
                            "curriculum_id": 3429,
                            "title": "Watermelon Fan",
                            "ppt_url": "https://wugecdn.steam.fun/a/index.html",
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    summary = import_captured_course_domain(store)

    assert summary["subjects"] == 1
    assert summary["curriculums"] == 1
    assert summary["materials"] == 1
    assert store.get_local_curriculum_material_snapshot(39525)["title"] == "Watermelon Fan"


def test_import_captured_course_domain_backfills_curriculum_subject_metadata(tmp_path: Path) -> None:
    store = MirrorStore(tmp_path)

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/subject/list?t=1&campusId=851",
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "content": {
                    "campusSubjectList": [
                        {"id": 1, "name": "Jrcode", "code": 1},
                        {"id": 2, "name": "Scratch", "code": 2},
                    ]
                }
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/curriculum/list/by/page?t=1&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "content": {
                    "campusAuthList": [
                        {
                            "subjectName": "Scratch",
                            "curriculumInfo": {
                                "id": 3429,
                                "title": "Scratch Intro",
                            },
                        },
                        {
                            "subjectId": 1,
                            "subjectName": "   ",
                            "curriculumInfo": {
                                "id": 3430,
                                "title": "Jrcode Builder",
                            },
                        },
                        {
                            "subject_id": 2,
                            "subjectName": "Subject 2",
                            "curriculumInfo": {
                                "id": 3431,
                                "title": "Scratch Builder",
                            },
                        },
                    ]
                }
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps({"content": {"curriculumMaterialList": []}}, ensure_ascii=False).encode("utf-8"),
    )

    summary = import_captured_course_domain(store)
    scratch_intro = store.get_local_curriculum_snapshot(3429)
    jrcode_builder = store.get_local_curriculum_snapshot(3430)
    scratch_builder = store.get_local_curriculum_snapshot(3431)

    assert summary["subjects"] == 2
    assert summary["curriculums"] == 3
    assert summary["materials"] == 0

    assert scratch_intro is not None
    assert scratch_intro["subject_id"] == 2
    assert scratch_intro["subject_name"] == "Scratch"

    assert jrcode_builder is not None
    assert jrcode_builder["subject_id"] == 1
    assert jrcode_builder["subject_name"] == "Jrcode"

    assert scratch_builder is not None
    assert scratch_builder["subject_id"] == 2
    assert scratch_builder["subject_name"] == "Scratch"
