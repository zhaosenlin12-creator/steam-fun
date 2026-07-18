from __future__ import annotations

import datetime as dt
import os
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.parse import urlparse

import requests
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from steamfun_mirror.browser_audit import navigate_for_audit
from steamfun_mirror.storage import MirrorStore

import persist_demo


BASE = "http://127.0.0.1:8000"
ROOT = Path(r"D:\kaifa\steam_fun")
OUTDIR = ROOT / "runtime" / f"management_flow_audit_{dt.datetime.now():%Y%m%d_%H%M%S}"
DB_PATH = ROOT / "runtime" / "mirror.sqlite3"
STORE = MirrorStore(ROOT)
REQUEST_TIMEOUT = 30
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _new_network_audit() -> dict[str, Any]:
    return {
        "external_requests": [],
        "failed_responses": [],
        "page_errors": [],
        "console_errors": [],
    }


def _register_page_network_audit(page: Page, network_audit: dict[str, Any]) -> None:
    def on_request(req) -> None:
        parsed = urlparse(req.url)
        host = (parsed.hostname or "").strip().lower()
        if parsed.scheme in {"http", "https"} and host and host not in LOCAL_HOSTS:
            network_audit["external_requests"].append(
                {"url": req.url, "method": req.method, "host": host, "resource_type": req.resource_type}
            )

    def on_response(resp) -> None:
        try:
            status = int(resp.status)
        except Exception:
            return
        if status >= 400:
            network_audit["failed_responses"].append({"url": resp.url, "status": status})

    def on_pageerror(exc) -> None:
        network_audit["page_errors"].append({"message": str(exc), "repr": repr(exc)})

    def on_console(msg) -> None:
        if msg.type != "error":
            return
        network_audit["console_errors"].append(
            {"text": msg.text, "location": msg.location, "type": msg.type}
        )

    page.on("request", on_request)
    page.on("response", on_response)
    page.on("pageerror", on_pageerror)
    page.on("console", on_console)


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_screenshot(page: Page, path: Path, *, full_page: bool = True) -> dict[str, Any]:
    try:
        page.screenshot(path=str(path), full_page=full_page)
        return {"ok": True, "path": str(path), "full_page": full_page}
    except Exception as exc:
        if full_page:
            try:
                page.screenshot(path=str(path), full_page=False)
                return {
                    "ok": True,
                    "path": str(path),
                    "full_page": False,
                    "fallback_from_full_page": True,
                    "error": str(exc),
                }
            except Exception as fallback_exc:
                return {
                    "ok": False,
                    "path": str(path),
                    "error": str(fallback_exc),
                    "initial_error": str(exc),
                }
        return {"ok": False, "path": str(path), "error": str(exc)}


def body_sample(page: Page, *, limit: int = 2000) -> str:
    try:
        return page.locator("body").inner_text()[:limit]
    except Exception as exc:
        return f"<body unavailable: {exc}>"


def load_profiles() -> dict[str, dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT profile_name, token, fresh_auth_json FROM profiles ORDER BY profile_name"
        ).fetchall()

    profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        fresh_auth = json.loads(row["fresh_auth_json"])
        profiles[row["profile_name"]] = {
            "token": row["token"],
            "fresh_auth": fresh_auth,
        }
    return profiles


def open_page(context: BrowserContext, path: str, *, wait_ms: int = 4000) -> Page:
    page = context.new_page()
    navigate_for_audit(page, f"{BASE}{path}", settle_timeout_ms=wait_ms)
    return page


def find_row(page: Page, account: str):
    return page.locator("tbody tr", has=page.get_by_text(account, exact=True)).first


def gather_teacher_context(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    teacher_fresh_auth = profiles["teacher"]["fresh_auth"]
    teacher_user_info = teacher_fresh_auth["userInfo"]
    teacher_school_info = teacher_fresh_auth["schoolInfo"]
    campus_id = (
        teacher_school_info.get("eduCampusId")
        or teacher_school_info.get("educationalInstitutionCampusId")
        or teacher_school_info.get("campusId")
        or teacher_user_info.get("eduCampusId")
        or teacher_user_info.get("educationalInstitutionCampusId")
        or teacher_user_info.get("campusId")
        or 851
    )
    return {
        "teacher_token": profiles["teacher"]["token"],
        "admin_token": profiles["admin"]["token"],
        "student_token": profiles["student"]["token"],
        "teacher_user_id": teacher_user_info["id"],
        "teacher_real_name": teacher_user_info["realName"],
        "campus_id": int(campus_id),
        "student_user_id": teacher_user_info.get("studentUserId"),
        "audit_student_id": teacher_school_info.get("auditStudentId"),
        "student_profile_id": teacher_school_info.get("studentProfileId"),
    }


def student_profile_info(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    student_user_info = profiles["student"]["fresh_auth"]["userInfo"]["stuUserInfo"]
    return {
        "student_user_id": student_user_info["id"],
        "student_account": student_user_info["name"],
        "student_real_name": student_user_info["stuUserInfo"]["realName"],
    }


def create_audit_student(session: requests.Session, campus_id: int) -> dict[str, Any]:
    """Idempotent wrapper around ``persist_demo.ensure_persist_student``.

    Reused across audit runs so the student validity flow always operates
    on the same demo student record.
    """
    return persist_demo.ensure_persist_student(
        session, STORE, campus_id, base_url=BASE
    )


def audit_student_validity_flow(
    browser: Browser,
    session: requests.Session,
    teacher_headers: dict[str, str],
    *,
    campus_id: int,
    network_audit: dict[str, Any],
) -> dict[str, Any]:
    created = create_audit_student(session, campus_id)
    result: dict[str, Any] = {
        "created_student": created,
    }

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1900, "height": 1000})
    page = context.new_page()
    api_events: list[dict[str, Any]] = []
    _register_page_network_audit(page, network_audit)

    def on_response(resp) -> None:
        if "/java-api/school/stu/" not in resp.url:
            return
        try:
            content_type = resp.headers.get("content-type", "")
            body = resp.text()[:500] if "json" in content_type.lower() else ""
        except Exception:
            body = ""
        api_events.append({"url": resp.url, "status": resp.status, "body": body})

    page.on("response", on_response)
    navigate_for_audit(page, f"{BASE}/school-home-page/class-management1/students-management1", settle_timeout_ms=4000)
    result["page_before"] = {
        "url": page.url,
        "title": page.title(),
        "is_login_redirect": "/login" in page.url,
        "body_sample": body_sample(page),
        "screenshot": safe_screenshot(page, OUTDIR / "student_validity_before.png"),
    }

    row = find_row(page, created["account"])
    row.wait_for(timeout=10000)
    date_link = row.locator("a").first
    result["date_before"] = date_link.inner_text().strip()
    date_link.click()
    page.wait_for_timeout(1500)

    dialog = page.locator(".el-dialog:visible").first
    dialog.wait_for(timeout=10000)
    buttons = dialog.locator("button")
    button_texts = [buttons.nth(index).inner_text().strip() for index in range(buttons.count())]
    result["dialog_before"] = {
        "text": dialog.inner_text()[:800],
        "buttons": button_texts,
    }

    # Buttons in this dialog are: [close-icon, 7 days, 1 month,
    # 3 months, 6 months, 1 year, cancel, confirm]. Pick "1 month" by
    # text so the choice is robust against any UI tweak that reorders
    # the icon-only button.
    one_month_button = dialog.get_by_role("button", name=re.compile(r"1\s*个月"))
    if one_month_button.count() == 0:
        buttons.nth(2).click()
    else:
        one_month_button.first.click(force=True)
    page.wait_for_timeout(1000)
    dialog_text_after_choose = dialog.inner_text()
    expected_match = re.search(r"有效期至：\s*(\d{4}-\d{2}-\d{2})", dialog_text_after_choose)
    result["dialog_after_choose"] = {
        "text": dialog_text_after_choose[:800],
        "expected_date": expected_match.group(1) if expected_match else None,
    }

    confirm_button = dialog.get_by_role("button", name=re.compile(r"^\s*确\s*定\s*$"))
    if confirm_button.count() == 0:
        buttons.nth(buttons.count() - 1).click()
    else:
        confirm_button.first.click(force=True)
    page.wait_for_timeout(5000)
    page.wait_for_timeout(1500)

    # The list page does not auto-reload after the dialog closes, so
    # refresh it explicitly so the row reflects the new end date.
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    refreshed_row = find_row(page, created["account"])
    refreshed_row.wait_for(timeout=10000)
    result["date_after_ui"] = refreshed_row.locator("a").first.inner_text().strip()
    result["page_after"] = {
        "url": page.url,
        "title": page.title(),
        "is_login_redirect": "/login" in page.url,
        "body_sample": body_sample(page),
        "screenshot": safe_screenshot(page, OUTDIR / "student_validity_after.png"),
    }
    result["api_events"] = [
        item
        for item in api_events
        if "setEndDate" in item["url"] or "selectStudy" in item["url"]
    ]

    list_response = session.post(
        f"{BASE}/java-api/school/stu/selectStudy?t={int(time.time())}",
        headers=teacher_headers,
        json={"pageRequest": {"pageNum": 1, "pageSize": 100}},
        timeout=REQUEST_TIMEOUT,
    )
    list_response.raise_for_status()
    rows = list_response.json()["content"]["content"]
    api_row = next(row for row in rows if row["stuId"] == created["student_id"])
    result["date_after_api"] = api_row["endDate"]
    result["api_row"] = {
        "stuId": api_row["stuId"],
        "stuAccount": api_row["stuAccount"],
        "endDate": api_row["endDate"],
    }
    result["passed"] = (
        result["dialog_after_choose"]["expected_date"] is not None
        and result["date_after_ui"] == result["dialog_after_choose"]["expected_date"]
        and result["date_after_api"] == result["dialog_after_choose"]["expected_date"]
    )

    context.close()
    return result


def create_audit_class(
    session: requests.Session,
    teacher_headers: dict[str, str],
    *,
    teacher_user_id: int,
    teacher_real_name: str,
    campus_id: int,
) -> dict[str, Any]:
    """Idempotent wrapper around ``persist_demo.ensure_persist_class``.

    Reuses the persistent demo class across audit runs; creates it once.
    """
    return persist_demo.ensure_persist_class(
        session,
        STORE,
        teacher_headers=teacher_headers,
        teacher_user_id=teacher_user_id,
        teacher_real_name=teacher_real_name,
        campus_id=campus_id,
        base_url=BASE,
    )


def choose_lesson_ids(
    session: requests.Session,
    teacher_headers: dict[str, str],
    *,
    class_id: int,
) -> list[int]:
    response = session.get(
        f"{BASE}/api/getLessonListForClassAddLesson?t={int(time.time())}&classId={class_id}&page_no=1&page_size=20",
        headers=teacher_headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    rows = response.json()["content"]["lessonList"]
    lesson_ids = [int(row["id"]) for row in rows[:2]]
    if not lesson_ids:
        # Keep the runtime audit aligned with the persisted local fixtures
        # used by the regression suite.
        lesson_ids = [7001, 7002]
    return lesson_ids


def class_detail_route(
    *,
    campus_id: int,
    class_id: int,
    teacher_user_id: int,
) -> str:
    encoded_goods = quote("[]", safe="")
    return (
        "/school-home-page/class-management1/divide-class1"
        f"?campus_id={campus_id}&id={class_id}&is_cost_lesson_hour=false"
        f"&lesson_hour=&curriculum_class_type=1&classXmGoodsArr={encoded_goods}"
        f"&lecturer_id={teacher_user_id}"
    )


def cleanup_audit_class(
    session: requests.Session,
    teacher_headers: dict[str, str],
    *,
    class_id: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {"class_id": class_id, "deleted_plan_ids": [], "deleted_class_ids": []}

    plan_list_response = session.get(
        f"{BASE}/api/get/teaching/plan/by/class/id?t={int(time.time())}&classes_id={class_id}&title=&sign_state=",
        headers=teacher_headers,
        timeout=REQUEST_TIMEOUT,
    )
    plan_list_response.raise_for_status()
    plan_rows = plan_list_response.json()["content"]["teaching_plan_list"]
    plan_ids = [int(row["id"]) for row in plan_rows if row.get("id") is not None]
    result["plan_ids_before_delete"] = plan_ids

    if plan_ids:
        delete_plan_response = session.post(
            f"{BASE}/api/delete/tch/plan?t={int(time.time())}",
            headers=teacher_headers,
            json={"tchPlanIds": plan_ids},
            timeout=REQUEST_TIMEOUT,
        )
        delete_plan_response.raise_for_status()
        result["delete_plans_response"] = delete_plan_response.json()
        result["deleted_plan_ids"] = plan_ids

    delete_class_response = session.post(
        f"{BASE}/api/delete/class?t={int(time.time())}",
        headers=teacher_headers,
        json={"classIds": [class_id]},
        timeout=REQUEST_TIMEOUT,
    )
    delete_class_response.raise_for_status()
    result["delete_class_response"] = delete_class_response.json()
    result["deleted_class_ids"] = [class_id]
    return result


def audit_class_flow(
    browser: Browser,
    session: requests.Session,
    teacher_headers: dict[str, str],
    *,
    teacher_user_id: int,
    teacher_real_name: str,
    campus_id: int,
    student_user_id: int,
    student_account: str,
    network_audit: dict[str, Any],
) -> dict[str, Any]:
    created_class = create_audit_class(
        session,
        teacher_headers,
        teacher_user_id=teacher_user_id,
        teacher_real_name=teacher_real_name,
        campus_id=campus_id,
    )
    add_student_info = persist_demo.ensure_student_in_class(
        session,
        STORE,
        teacher_headers=teacher_headers,
        class_id=created_class["class_id"],
        student_user_id=student_user_id,
        base_url=BASE,
    )
    lessons_info = persist_demo.ensure_persist_lessons(
        session,
        STORE,
        teacher_headers=teacher_headers,
        class_id=created_class["class_id"],
        base_url=BASE,
    )
    lesson_ids = lessons_info["lesson_ids"]
    result: dict[str, Any] = {
        "created_class": created_class,
        "add_student": add_student_info,
        "lesson_ids": lesson_ids,
        "bulk_add_lessons": lessons_info.get("bulk_add_response", {"reused": lessons_info["reused"]}),
        "persistence": {
            "student_reused": created_class.get("reused", False),
            "class_reused": created_class.get("reused", False),
            "lessons_reused": lessons_info.get("reused", False),
            "student_already_attached": add_student_info.get("already_attached", False),
            "class_id": created_class["class_id"],
            "lesson_ids": list(lesson_ids),
        },
    }

    class_student_response = session.get(
        f"{BASE}/api/get/class/student/list?t={int(time.time())}&classId={created_class['class_id']}&realname=&page_no=1&page_size=20",
        headers=teacher_headers,
        timeout=REQUEST_TIMEOUT,
    )
    class_student_response.raise_for_status()
    student_rows = class_student_response.json()["content"]["studentList"]
    result["class_student_list"] = {
        "total": len(student_rows),
        "student_accounts": [row["studentInfo"]["name"] for row in student_rows],
    }

    plan_list_response = session.get(
        f"{BASE}/api/get/teaching/plan/by/class/id?t={int(time.time())}&classes_id={created_class['class_id']}&title=&sign_state=",
        headers=teacher_headers,
        timeout=REQUEST_TIMEOUT,
    )
    plan_list_response.raise_for_status()
    plan_rows = plan_list_response.json()["content"]["teaching_plan_list"]
    if not plan_rows:
        raise RuntimeError("No teaching plans returned after bulk add")
    first_plan = plan_rows[0]
    result["teaching_plans"] = {
        "count": len(plan_rows),
        "first_plan": {
            "id": first_plan.get("id"),
            "curriculum_meterial_id": (
                first_plan.get("curriculum_meterial_id")
                or first_plan.get("curriculumMaterialId")
                or first_plan.get("curriculum_material_id")
                or lesson_ids[0]
            ),
            "title": (
                first_plan.get("custom_lesson_title")
                or (first_plan.get("lessionInfo") or {}).get("title")
                or ""
            ),
        },
    }

    material_id = result["teaching_plans"]["first_plan"]["curriculum_meterial_id"]
    if not material_id:
        raise RuntimeError("Could not resolve curriculum material id for first audit plan")

    teacher_context = browser.new_context(ignore_https_errors=True, viewport={"width": 1900, "height": 1000})
    class_detail_page = open_page(
        teacher_context,
        class_detail_route(
            campus_id=campus_id,
            class_id=created_class["class_id"],
            teacher_user_id=teacher_user_id,
        ),
    )
    _register_page_network_audit(class_detail_page, network_audit)
    class_detail_body = body_sample(class_detail_page)
    result["class_detail_page"] = {
        "url": class_detail_page.url,
        "title": class_detail_page.title(),
        "is_login_redirect": "/login" in class_detail_page.url,
        "body_sample": class_detail_body,
        "contains_class_name": created_class["class_name"] in class_detail_body,
        "contains_student_account": student_account in class_detail_body,
        "screenshot": safe_screenshot(class_detail_page, OUTDIR / "class_detail.png"),
    }

    teach_ppt_page = open_page(
        teacher_context,
        f"/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id={material_id}&teaching_plan_id={first_plan['id']}",
    )
    _register_page_network_audit(teach_ppt_page, network_audit)
    teach_ppt_body = body_sample(teach_ppt_page)
    result["teach_ppt_page"] = {
        "url": teach_ppt_page.url,
        "title": teach_ppt_page.title(),
        "is_login_redirect": "/login" in teach_ppt_page.url,
        "body_sample": teach_ppt_body,
        "contains_tool_text": "课程工具" in teach_ppt_body,
        "screenshot": safe_screenshot(teach_ppt_page, OUTDIR / "teach_ppt.png"),
    }
    teacher_context.close()

    student_context = browser.new_context(ignore_https_errors=True, viewport={"width": 1900, "height": 1000})
    student_page = open_page(student_context, "/code-classroom/myClass", wait_ms=5000)
    _register_page_network_audit(student_page, network_audit)
    student_body = body_sample(student_page, limit=4000)
    result["student_myclass_page"] = {
        "url": student_page.url,
        "title": student_page.title(),
        "is_login_redirect": "/login" in student_page.url,
        "body_sample": student_body,
        "contains_class_name": created_class["class_name"] in student_body,
        "screenshot": safe_screenshot(student_page, OUTDIR / "student_myclass.png"),
    }
    student_context.close()

    result["passed"] = (
        student_account in result["class_student_list"]["student_accounts"]
        and result["class_detail_page"]["contains_class_name"]
        and result["class_detail_page"]["contains_student_account"]
        and result["teach_ppt_page"]["contains_tool_text"]
        and result["student_myclass_page"]["contains_class_name"]
    )
    return result


def audit_admin_page(browser: Browser, *, network_audit: dict[str, Any]) -> dict[str, Any]:
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1900, "height": 1000})
    page = open_page(context, "/background/course-management/school-curriculum")
    _register_page_network_audit(page, network_audit)
    body = body_sample(page)
    result = {
        "url": page.url,
        "title": page.title(),
        "is_login_redirect": "/login" in page.url,
        "contains_admin_username": "18164173640" in body,
        "contains_curriculum_text": "课程体系名称" in body,
        "body_sample": body,
        "screenshot": safe_screenshot(page, OUTDIR / "admin_school_curriculum.png"),
    }
    context.close()
    result["passed"] = (
        not result["is_login_redirect"]
        and result["contains_admin_username"]
        and result["contains_curriculum_text"]
    )
    return result


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    profiles = load_profiles()
    teacher_context = gather_teacher_context(profiles)
    student_info = student_profile_info(profiles)
    teacher_headers = {"Authorization": f"Bearer {teacher_context['teacher_token']}"}

    summary: dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(),
        "base_url": BASE,
    }
    network_audit = _new_network_audit()

    with requests.Session() as session:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                summary["admin_page"] = audit_admin_page(browser, network_audit=network_audit)
                summary["student_validity_flow"] = audit_student_validity_flow(
                    browser,
                    session,
                    teacher_headers,
                    campus_id=teacher_context["campus_id"],
                    network_audit=network_audit,
                )
                summary["class_flow"] = audit_class_flow(
                    browser,
                    session,
                    teacher_headers,
                    teacher_user_id=teacher_context["teacher_user_id"],
                    teacher_real_name=teacher_context["teacher_real_name"],
                    campus_id=teacher_context["campus_id"],
                    student_user_id=student_info["student_user_id"],
                    student_account=student_info["student_account"],
                    network_audit=network_audit,
                )
            finally:
                class_flow = summary.get("class_flow") or {}
                created_class = class_flow.get("created_class") or {}
                class_id = created_class.get("class_id")
                class_reused = bool(created_class.get("reused"))
                if class_id and not class_reused:
                    try:
                        summary.setdefault("class_flow_cleanup", cleanup_audit_class(
                            session,
                            teacher_headers,
                            class_id=int(class_id),
                        ))
                    except Exception as exc:
                        summary["class_flow_cleanup_error"] = str(exc)
                elif class_id:
                    summary["class_flow_cleanup"] = {
                        "skipped": True,
                        "reason": "persistent demo class is reused across runs",
                        "class_id": class_id,
                    }
                browser.close()

    summary["all_passed"] = all(
        summary[section]["passed"]
        for section in ("admin_page", "student_validity_flow", "class_flow")
    )
    summary["network_audit"] = {
        "external_requests": network_audit["external_requests"],
        "failed_responses": network_audit["failed_responses"],
        "page_errors": network_audit["page_errors"],
        "console_errors": network_audit["console_errors"],
        "external_request_count": len(network_audit["external_requests"]),
        "failed_response_count": len(network_audit["failed_responses"]),
        "page_error_count": len(network_audit["page_errors"]),
        "console_error_count": len(network_audit["console_errors"]),
    }
    dump_json(OUTDIR / "summary.json", summary)


if __name__ == "__main__":
    main()
