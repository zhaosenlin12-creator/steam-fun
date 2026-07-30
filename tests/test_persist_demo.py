from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _make_store():
    tmp = Path(tempfile.mkdtemp(prefix="steamfun_persist_"))
    from steamfun_mirror.storage import MirrorStore
    store = MirrorStore(tmp)
    return store, tmp


def _seed_student(store, *, name: str, realname: str = "Test Student", campus_id: int = 851):
    with store._connect() as conn:
        cur = conn.execute(
            "INSERT INTO local_students "
            "(name, realname, campus_id, sex, normal_state, phone_num, school_name, "
            " grade, leader, remark, study_date, headimg_url) "
            "VALUES (?, ?, ?, 'M', '1', '13900139999', 'Test School', "
            " '', '', '', '2026-05-18', '/_external/x.png')",
            (name, realname, campus_id),
        )
        return int(cur.lastrowid)


def _seed_class(store, *, name: str, lecturer_id: int, campus_id: int = 851, lecturer_name: str = "Test Teacher"):
    with store._connect() as conn:
        cur = conn.execute(
            "INSERT INTO local_classes "
            "(name, educational_institution_campus_id, lecturer_id, lecturer_name, deleted) "
            "VALUES (?, ?, ?, ?, 0)",
            (name, campus_id, lecturer_id, lecturer_name),
        )
        return int(cur.lastrowid)


def _seed_plan(store, *, class_id: int, title: str = "Lesson", lecturer_id: int = 1):
    with store._connect() as conn:
        cur = conn.execute(
            "INSERT INTO local_teaching_plans "
            "(curriculum_class_id, lecturer_id, title, deleted) "
            "VALUES (?, ?, ?, 0)",
            (class_id, lecturer_id, title),
        )
        return int(cur.lastrowid)


def _seed_class_student(store, *, class_id: int, student_user_id: int):
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO local_class_students "
            "(class_id, student_user_id, in_class_date) "
            "VALUES (?, ?, '2026-05-18')",
            (class_id, student_user_id),
        )


def test_find_student_by_account_returns_none_when_missing():
    store, tmp = _make_store()
    try:
        from persist_demo import find_local_student_by_account, DEMO_STUDENT_ACCOUNT
        assert find_local_student_by_account(store, DEMO_STUDENT_ACCOUNT) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_find_student_by_account_returns_row_when_present():
    store, tmp = _make_store()
    try:
        from persist_demo import find_local_student_by_account, DEMO_STUDENT_ACCOUNT
        _seed_student(store, name=DEMO_STUDENT_ACCOUNT)
        row = find_local_student_by_account(store, DEMO_STUDENT_ACCOUNT)
        assert row is not None
        assert row["name"] == DEMO_STUDENT_ACCOUNT
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_find_student_by_account_skips_soft_deleted_student():
    store, tmp = _make_store()
    try:
        from persist_demo import find_local_student_by_account, DEMO_STUDENT_ACCOUNT

        student_id = _seed_student(store, name=DEMO_STUDENT_ACCOUNT)
        store.upsert_student_overlay(student_id, {"deleted": 1, "quit": 0})

        assert find_local_student_by_account(store, DEMO_STUDENT_ACCOUNT) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_find_class_for_teacher_filters_by_lecturer_and_campus():
    store, tmp = _make_store()
    try:
        from persist_demo import find_local_class_for_teacher, DEMO_CLASS_NAME
        _seed_class(store, name=DEMO_CLASS_NAME, lecturer_id=999)
        assert find_local_class_for_teacher(
            store, name=DEMO_CLASS_NAME, lecturer_id=12385, campus_id=851
        ) is None
        _seed_class(store, name=DEMO_CLASS_NAME, lecturer_id=12385, lecturer_name="zhaosenlin")
        row = find_local_class_for_teacher(
            store, name=DEMO_CLASS_NAME, lecturer_id=12385, campus_id=851
        )
        assert row is not None
        assert row["name"] == DEMO_CLASS_NAME
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_find_class_skips_deleted():
    store, tmp = _make_store()
    try:
        from persist_demo import find_local_class_for_teacher, DEMO_CLASS_NAME
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO local_classes "
                "(name, educational_institution_campus_id, lecturer_id, lecturer_name, deleted) "
                "VALUES (?, 851, 12385, 'zhaosenlin', 1)",
                (DEMO_CLASS_NAME,),
            )
        assert find_local_class_for_teacher(
            store, name=DEMO_CLASS_NAME, lecturer_id=12385, campus_id=851
        ) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_find_plans_for_class_returns_only_active():
    store, tmp = _make_store()
    try:
        from persist_demo import find_local_plans_for_class
        cid = _seed_class(store, name="x", lecturer_id=1)
        _seed_plan(store, class_id=cid, title="active1")
        _seed_plan(store, class_id=cid, title="active2")
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO local_teaching_plans "
                "(curriculum_class_id, lecturer_id, title, deleted) VALUES (?, 1, 'gone', 1)",
                (cid,),
            )
        plans = find_local_plans_for_class(store, cid)
        assert len(plans) == 2
        assert {p["title"] for p in plans} == {"active1", "active2"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_is_student_in_class_detaches_when_out_class_date_set():
    store, tmp = _make_store()
    try:
        from persist_demo import is_student_in_class
        cid = _seed_class(store, name="y", lecturer_id=1)
        _seed_class_student(store, class_id=cid, student_user_id=42)
        assert is_student_in_class(store, class_id=cid, student_user_id=42) is True
        with store._connect() as conn:
            conn.execute(
                "UPDATE local_class_students SET out_class_date='2026-06-01' "
                "WHERE class_id=? AND student_user_id=?",
                (cid, 42),
            )
        assert is_student_in_class(store, class_id=cid, student_user_id=42) is False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_summarize_persistence_reports_missing_student():
    store, tmp = _make_store()
    try:
        from persist_demo import summarize_persistence, DEMO_STUDENT_ACCOUNT, DEMO_CLASS_NAME
        snap = summarize_persistence(store)
        assert snap["student_present"] is False
        assert snap["student_account"] == DEMO_STUDENT_ACCOUNT
        assert snap["class_name"] == DEMO_CLASS_NAME
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ensure_persist_student_uses_teacher_authorization_headers():
    store, tmp = _make_store()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"content": {"studentId": 101}}

    class Session:
        def __init__(self):
            self.headers = None

        def post(self, url, *, headers, json, timeout):
            self.headers = headers
            return Response()

    try:
        from persist_demo import ensure_persist_student

        session = Session()
        result = ensure_persist_student(
            session,
            store,
            851,
            teacher_headers={"Authorization": "Bearer teacher-token"},
        )

        assert result["student_id"] == 101
        assert session.headers == {"Authorization": "Bearer teacher-token"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
