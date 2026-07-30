"""Persistent demo data helpers for the audit script.

Replaces the audit's random ``audit_validity_<ts>`` student and
``AUDIT-FLOW-<ts>`` class with a fixed set of demo entities that are
created once and reused across audit runs. This makes the audit output
comparable run-to-run instead of accumulating fresh garbage each run.

The helpers are idempotent: each one first asks the local SQLite store
whether the demo entity already exists, and only calls the live API to
create it when missing.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import requests

from steamfun_mirror.storage import MirrorStore


DEMO_STUDENT_ACCOUNT = "demo_persist_student"
DEMO_STUDENT_REALNAME = "Demo Persist Student"
DEMO_STUDENT_PHONE = "13900139999"
DEMO_STUDENT_SCHOOL = "Persist Demo School"
DEMO_STUDENT_REMARK = "persist-demo-seed"

DEMO_CLASS_NAME = "DEMO-PERSIST-CLASS"
DEMO_CLASS_WEEK_JSON = [6]
DEMO_CLASS_WEEK_STR = "Sat"
DEMO_CLASS_TIME_STR = "09:00-10:30"
DEMO_CLASS_SUBJECT_ID = 1
DEMO_CLASS_CURRICULUM_ID = 501
DEMO_CLASS_TYPE = 1  # 正式班
DEMO_CLASS_TEACHING_TYPE = 1  # 面授课

DEMO_LESSON_TITLES = ["Persist Lesson 1", "Persist Lesson 2"]
DEMO_LESSON_CURRICULUM_MATERIAL_IDS = [7001, 7002]


# ---------- Local store helpers (idempotent lookups) ----------


def find_local_student_by_account(store: MirrorStore, account: str) -> dict[str, Any] | None:
    """Return the ``local_students`` row whose ``name`` matches ``account``."""
    with store._connect() as connection:  # noqa: SLF001
        row = connection.execute(
            "SELECT id, name, realname, campus_id FROM local_students "
            "WHERE name = ? ORDER BY id DESC LIMIT 1",
            (account,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "realname": row["realname"],
        "campus_id": row["campus_id"],
    }


def find_local_class_for_teacher(
    store: MirrorStore, *, name: str, lecturer_id: int, campus_id: int
) -> dict[str, Any] | None:
    """Return the demo class row matching name + lecturer + campus."""
    with store._connect() as connection:  # noqa: SLF001
        row = connection.execute(
            """
            SELECT id, name, lecturer_id, lecturer_name, educational_institution_campus_id
            FROM local_classes
            WHERE name = ? AND lecturer_id = ? AND educational_institution_campus_id = ?
              AND deleted = 0
            ORDER BY id DESC LIMIT 1
            """,
            (name, lecturer_id, campus_id),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def find_local_plans_for_class(store: MirrorStore, class_id: int) -> list[dict[str, Any]]:
    """Return all (non-deleted) teaching plans attached to ``class_id``."""
    with store._connect() as connection:  # noqa: SLF001
        rows = connection.execute(
            """
            SELECT id, curriculum_class_id, lecturer_id, title, custom_lesson_title
            FROM local_teaching_plans
            WHERE curriculum_class_id = ? AND deleted = 0
            ORDER BY id
            """,
            (class_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def is_student_in_class(store: MirrorStore, *, class_id: int, student_user_id: int) -> bool:
    with store._connect() as connection:  # noqa: SLF001
        row = connection.execute(
            """
            SELECT 1 FROM local_class_students
            WHERE class_id = ? AND student_user_id = ?
              AND (out_class_date IS NULL OR out_class_date = '')
            LIMIT 1
            """,
            (class_id, student_user_id),
        ).fetchone()
    return row is not None


def summarize_persistence(store: MirrorStore) -> dict[str, Any]:
    student = find_local_student_by_account(store, DEMO_STUDENT_ACCOUNT)
    return {
        "student_account": DEMO_STUDENT_ACCOUNT,
        "student_present": student is not None,
        "student_row": student,
        "class_name": DEMO_CLASS_NAME,
    }


# ---------- Idempotent ensure-via-API helpers ----------


def ensure_persist_student(
    session: requests.Session,
    store: MirrorStore,
    campus_id: int,
    *,
    teacher_headers: dict[str, str],
    base_url: str = "http://127.0.0.1:8000",
) -> dict[str, Any]:
    """Return the demo student, creating it if missing."""
    existing = find_local_student_by_account(store, DEMO_STUDENT_ACCOUNT)
    if existing is not None:
        return {
            "request": {"account": DEMO_STUDENT_ACCOUNT, "reused": True},
            "response": {"content": {"studentId": existing["id"]}},
            "student_id": existing["id"],
            "account": DEMO_STUDENT_ACCOUNT,
            "reused": True,
        }

    payload = {
        "eduCampusId": campus_id,
        "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
        "normalState": "1",
        "name": DEMO_STUDENT_ACCOUNT,
        "realName": DEMO_STUDENT_REALNAME,
        "sex": "M",
        "parentAPhoneNum": DEMO_STUDENT_PHONE,
        "schoolName": DEMO_STUDENT_SCHOOL,
        "grade": "",
        "leader": "",
        "remark": DEMO_STUDENT_REMARK,
        "studyDate": "2026-05-18",
    }
    response = session.post(
        f"{base_url}/java-api/school/stu/create",
        headers=teacher_headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    created = response.json()
    return {
        "request": payload,
        "response": created,
        "student_id": created["content"]["studentId"],
        "account": DEMO_STUDENT_ACCOUNT,
        "reused": False,
    }


def ensure_persist_class(
    session: requests.Session,
    store: MirrorStore,
    *,
    teacher_headers: dict[str, str],
    teacher_user_id: int,
    teacher_real_name: str,
    campus_id: int,
    base_url: str = "http://127.0.0.1:8000",
) -> dict[str, Any]:
    """Return the demo class, creating it if missing."""
    existing = find_local_class_for_teacher(
        store,
        name=DEMO_CLASS_NAME,
        lecturer_id=teacher_user_id,
        campus_id=campus_id,
    )
    if existing is not None:
        return {
            "request": {"class_name": DEMO_CLASS_NAME, "reused": True},
            "response": {"content": {"id": existing["id"]}},
            "class_id": existing["id"],
            "class_name": DEMO_CLASS_NAME,
            "reused": True,
        }

    payload = {
        "className": DEMO_CLASS_NAME,
        "campusId": campus_id,
        "lecturer_id": teacher_user_id,
        "lecturer_name": teacher_real_name,
        "curriculum_class_type": DEMO_CLASS_TYPE,
        "teaching_type": DEMO_CLASS_TEACHING_TYPE,
        "week_json": DEMO_CLASS_WEEK_JSON,
        "week_str": DEMO_CLASS_WEEK_STR,
        "time_str": DEMO_CLASS_TIME_STR,
        "subjectIdArr": [DEMO_CLASS_SUBJECT_ID],
        "curriculumIdArr": [DEMO_CLASS_CURRICULUM_ID],
    }
    response = session.post(
        f"{base_url}/api/create/class",
        headers=teacher_headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    created = response.json()
    return {
        "request": payload,
        "response": created,
        "class_id": created["content"]["id"],
        "class_name": DEMO_CLASS_NAME,
        "reused": False,
    }


def ensure_persist_lessons(
    session: requests.Session,
    store: MirrorStore,
    *,
    teacher_headers: dict[str, str],
    class_id: int,
    base_url: str = "http://127.0.0.1:8000",
) -> dict[str, Any]:
    """Ensure the demo class has 2 lessons; reuse existing ones if present."""
    existing = find_local_plans_for_class(store, class_id)
    if len(existing) >= 2:
        return {
            "lesson_ids": [row["id"] for row in existing],
            "reused": True,
            "existing_count": len(existing),
        }

    # Need to bulk-add lessons. Choose fixed material IDs.
    lesson_ids = DEMO_LESSON_CURRICULUM_MATERIAL_IDS
    response = session.post(
        f"{base_url}/api/bulk/add/tch/plan/to/class",
        headers=teacher_headers,
        json={"classId": class_id, "lessonIds": lesson_ids},
        timeout=30,
    )
    response.raise_for_status()
    bulk_add = response.json()
    # Re-fetch the plans to capture the newly inserted IDs.
    after = find_local_plans_for_class(store, class_id)
    return {
        "lesson_ids": [row["id"] for row in after],
        "reused": False,
        "bulk_add_response": bulk_add,
    }


def ensure_student_in_class(
    session: requests.Session,
    store: MirrorStore,
    *,
    teacher_headers: dict[str, str],
    class_id: int,
    student_user_id: int,
    base_url: str = "http://127.0.0.1:8000",
) -> dict[str, Any]:
    """Add the demo student to the demo class; no-op if already attached."""
    if is_student_in_class(
        store, class_id=class_id, student_user_id=student_user_id
    ):
        return {
            "already_attached": True,
            "class_id": class_id,
            "student_user_id": student_user_id,
        }

    response = session.post(
        f"{base_url}/api/add/student/class/relation",
        headers=teacher_headers,
        json={"classId": class_id, "stuIds": [student_user_id]},
        timeout=30,
    )
    response.raise_for_status()
    return {
        "already_attached": False,
        "response": response.json(),
        "class_id": class_id,
        "student_user_id": student_user_id,
    }
