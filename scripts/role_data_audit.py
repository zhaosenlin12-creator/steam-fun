from __future__ import annotations

import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from steamfun_mirror.browser_audit import navigate_for_audit, summarize_browser_events
from steamfun_mirror.runtime_audit import get_login_flow


ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("STEAMFUN_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUTDIR = ROOT / "runtime" / f"role_data_audit_{dt.datetime.now():%Y%m%d_%H%M%S}"

ACCOUNTS = {
    "admin": "18164173640",
    "teacher": "zhaosenlin",
    "student": "lbschenmuran",
}

BACK_HOME_LABEL = "".join(chr(code) for code in (0x8FD4, 0x56DE, 0x9996, 0x9875))


class EventRecorder:
    def __init__(self, page: Page) -> None:
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.request_failures: list[dict[str, str]] = []
        self.bad_responses: list[dict[str, Any]] = []
        self.external_requests: list[str] = []

        page.on("console", self._on_console)
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)
        page.on("request", self._on_request)

    def _on_console(self, message) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)

    def _on_request_failed(self, request) -> None:
        failure = request.failure
        failure_text = failure.get("errorText", "") if isinstance(failure, dict) else str(failure or "")
        if "err_aborted" not in failure_text.lower():
            self.request_failures.append({"url": request.url, "failure": failure_text})

    def _on_response(self, response) -> None:
        if response.status >= 400:
            self.bad_responses.append({"status": response.status, "url": response.url})

    def _on_request(self, request) -> None:
        parsed = urlparse(request.url)
        if parsed.scheme in {"http", "https"} and parsed.netloc != urlparse(BASE).netloc:
            self.external_requests.append(request.url)

    def summary(self) -> dict[str, Any]:
        summary = summarize_browser_events(
            console_messages=[{"type": "error", "text": text} for text in self.console_errors],
            page_errors=[{"message": message} for message in self.page_errors],
            request_failures=self.request_failures,
            bad_responses=self.bad_responses,
        )
        summary["external_requests"] = list(self.external_requests)
        summary["passed"] = summary["passed"] and not self.external_requests
        return summary


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def page_state(page: Page) -> dict[str, Any]:
    body = page.locator("body").inner_text().strip()
    return {
        "url": page.url,
        "path": urlparse(page.url).path,
        "title": page.title(),
        "body_length": len(body),
        "horizontal_overflow": page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ),
    }


def navigate(page: Page, path: str, *, settle_ms: int = 1200) -> None:
    navigate_for_audit(
        page,
        f"{BASE}{path}",
        networkidle_timeout_ms=7000,
        settle_timeout_ms=settle_ms,
    )


def fetch_json(page: Page, path: str) -> dict[str, Any]:
    return page.evaluate(
        """async (path) => {
            const response = await fetch(path, {credentials: 'same-origin'});
            let body = null;
            try { body = await response.json(); } catch (error) {}
            return {status: response.status, body};
        }""",
        path,
    )


def require_success(response: dict[str, Any], description: str) -> dict[str, Any]:
    body = response.get("body")
    if response.get("status") != 200 or not isinstance(body, dict) or body.get("success") is not True:
        raise AssertionError(f"{description}: unexpected response {response}")
    content = body.get("content")
    if not isinstance(content, dict):
        raise AssertionError(f"{description}: missing content object")
    return content


def list_from(content: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        rows = content.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def row_id(row: dict[str, Any]) -> int | None:
    for key in ("id", "classId", "teachingPlanId", "tchPlanId", "student_user_id", "studentUserId"):
        value = row.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def row_name(row: dict[str, Any]) -> str:
    for key in ("name", "className", "title", "realname", "realName"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    student = row.get("studentInfo") if isinstance(row.get("studentInfo"), dict) else {}
    nested = student.get("studentUserInfo") if isinstance(student.get("studentUserInfo"), dict) else {}
    for source in (nested, student):
        for key in ("realname", "realName", "name"):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    return ""


def login(browser, role: str) -> tuple[Any, Page, EventRecorder, dict[str, Any]]:
    flow = get_login_flow(role)
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = context.new_page()
    events = EventRecorder(page)
    navigate(page, flow.path, settle_ms=500)
    if flow.role_tab_selector:
        page.locator(flow.role_tab_selector).click()
    form = "#form-student" if role == "student" else "#form-teacher"
    page.locator(f'{form} input[name="userName"]').fill(ACCOUNTS[role])
    page.locator(f'{form} input[name="password"]').fill("123456")
    page.locator(f'{form} button[type="submit"]').click()
    page.wait_for_url(lambda url: urlparse(url).path == flow.fallback_path, timeout=20000)
    try:
        page.wait_for_load_state("networkidle", timeout=7000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(800)
    state = page_state(page)
    if state["path"] != flow.fallback_path or state["body_length"] <= 0 or state["horizontal_overflow"]:
        raise AssertionError(f"{role}: invalid login landing {state}")
    return context, page, events, state


def audit_admin(browser) -> dict[str, Any]:
    context, page, events, landing = login(browser, "admin")
    result: dict[str, Any] = {"landing": landing}
    try:
        class_content = require_success(
            fetch_json(page, "/api/get/classes/list?page_no=1&page_size=50"), "admin class list"
        )
        classes = list_from(class_content, "classList", "rows", "list")
        if not classes:
            raise AssertionError("admin class list is empty")
        class_id = row_id(classes[0])
        class_name = row_name(classes[0])
        if class_id is None or not class_name:
            raise AssertionError(f"admin class list is incomplete: {classes[0]}")

        student_content = require_success(
            fetch_json(page, f"/api/get/class/student/list?classId={class_id}"), "admin class students"
        )
        students = list_from(student_content, "studentList", "rows", "list")
        student_names = [row_name(student) for student in students]
        if not students or not any(student_names):
            raise AssertionError(f"admin class {class_id} has no resolvable students")

        plan_content = require_success(
            fetch_json(page, f"/api/get/teaching/plan/by/class/id?classes_id={class_id}"), "admin plans"
        )
        plans = list_from(plan_content, "teaching_plan_list", "rows", "list")
        plan_ids = [row_id(plan) for plan in plans]
        if not plans or any(plan_id is None for plan_id in plan_ids):
            raise AssertionError(f"admin class {class_id} has no valid plans")

        catalog_content = require_success(
            fetch_json(page, "/api/admin/get/school/curriculum/list?check_state=2&page_no=1&page_size=20"),
            "admin course catalog",
        )
        catalog = list_from(catalog_content, "curriculum_list", "curriculumList", "rows", "list")
        catalog_titles = [row_name(row) for row in catalog]
        if not catalog or not any(catalog_titles):
            raise AssertionError("admin course catalog is empty")

        navigate(page, "/school-home-page/class-management1/students-management1")
        student_page = page_state(page)
        body = page.locator("body").inner_text()
        if not any(name in body for name in student_names if name):
            raise AssertionError("admin student page does not render the class student")
        return_home = page.get_by_text(BACK_HOME_LABEL, exact=True)
        if return_home.count() == 0:
            raise AssertionError("admin student page has no return-home control")
        return_home.last.click()
        page.wait_for_timeout(900)
        return_state = page_state(page)
        if return_state["path"] != "/school-home-page/class-management1":
            raise AssertionError(f"admin return-home went to {return_state['path']}")

        navigate(page, "/school-home-page/course-list")
        course_page = page_state(page)
        course_body = page.locator("body").inner_text()
        if not any(title in course_body for title in catalog_titles if title):
            raise AssertionError("admin course page does not render the local catalog")

        legacy = fetch_json(page, "/__mirror__/health")
        if legacy.get("status") != 200:
            raise AssertionError("admin health check failed")
        navigate(page, "/background/course-management/school-curriculum", settle_ms=700)
        legacy_state = page_state(page)
        if legacy_state["path"] != "/school-home-page/course-list":
            raise AssertionError(f"legacy admin course route went to {legacy_state['path']}")

        result.update(
            {
                "class_id": class_id,
                "class_name": class_name,
                "student_names": student_names,
                "plan_ids": [int(plan_id) for plan_id in plan_ids if plan_id is not None],
                "catalog_titles": catalog_titles,
                "student_page": student_page,
                "return_home": return_state,
                "course_page": course_page,
                "legacy_course_route": legacy_state,
            }
        )
        page.screenshot(path=str(OUTDIR / "admin_course_page.png"), full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        page.screenshot(path=str(OUTDIR / "admin_error.png"), full_page=True)
    finally:
        result["events"] = events.summary()
        context.close()
    result["passed"] = "error" not in result and result["events"]["passed"]
    return result


def audit_teacher(browser, admin: dict[str, Any]) -> dict[str, Any]:
    context, page, events, landing = login(browser, "teacher")
    result: dict[str, Any] = {"landing": landing}
    try:
        class_id = int(admin["class_id"])
        expected_plans = set(admin["plan_ids"])
        expected_course_titles = set(admin["catalog_titles"])
        class_content = require_success(
            fetch_json(page, "/api/tch/getTchIndexClassListWithTchPlanInfo?page_no=1&page_size=50"),
            "teacher class list",
        )
        classes = list_from(class_content, "classList", "classlist", "rows", "list")
        class_rows = [row for row in classes if row_id(row) == class_id]
        if len(class_rows) != 1:
            raise AssertionError(f"teacher cannot see exactly one matching class {class_id}")
        visible_plan_ids = {row_id(row) for row in list_from(class_content, "tchPlanList", "teachingPlanList")}
        if not expected_plans.issubset(visible_plan_ids):
            raise AssertionError(f"teacher plans {visible_plan_ids} do not contain {expected_plans}")

        catalog_content = require_success(
            fetch_json(page, "/api/get/campus/curriculum/list/by/page?page_no=1&page_size=20"),
            "teacher course catalog",
        )
        catalog = list_from(catalog_content, "campusAuthList", "rows", "list")
        catalog_titles = [row_name(row.get("curriculumInfo") if isinstance(row.get("curriculumInfo"), dict) else row) for row in catalog]
        if not set(catalog_titles).intersection(expected_course_titles):
            raise AssertionError("teacher course catalog does not match the admin catalog")

        materials_content = require_success(
            fetch_json(page, "/api/prepare/get/currculumMaterialList?curriculum_id=501&page_no=1&page_size=20"),
            "teacher material list",
        )
        materials = list_from(materials_content, "curriculumMaterialList", "currculumMaterialList", "rows", "list")
        material_id = row_id(materials[0]) if materials else None
        if material_id is None:
            raise AssertionError("teacher material list is empty")

        navigate(page, "/code-classroom/prepare-lessons")
        preparation_page = page_state(page)
        preparation_body = page.locator("body").inner_text()
        if not any(title in preparation_body for title in catalog_titles if title):
            raise AssertionError("teacher preparation page does not render the local catalog")

        plan_id = min(expected_plans)
        navigate(page, f"/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id={material_id}&tchPlanId={plan_id}")
        ppt_page = page_state(page)
        if ppt_page["body_length"] <= 0:
            raise AssertionError("teacher PPT page is blank")

        result.update(
            {
                "class_id": class_id,
                "plan_ids": sorted(int(plan_id) for plan_id in visible_plan_ids if plan_id is not None),
                "catalog_titles": catalog_titles,
                "material_id": material_id,
                "preparation_page": preparation_page,
                "ppt_page": ppt_page,
            }
        )
        page.screenshot(path=str(OUTDIR / "teacher_ppt_page.png"), full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        page.screenshot(path=str(OUTDIR / "teacher_error.png"), full_page=True)
    finally:
        result["events"] = events.summary()
        context.close()
    result["passed"] = "error" not in result and result["events"]["passed"]
    return result


def audit_student(browser, admin: dict[str, Any]) -> dict[str, Any]:
    context, page, events, landing = login(browser, "student")
    result: dict[str, Any] = {"landing": landing}
    try:
        class_id = int(admin["class_id"])
        expected_plans = set(admin["plan_ids"])
        class_name = str(admin["class_name"])
        class_content = require_success(
            fetch_json(page, "/api/stu/get/stu/class/list?page_no=1&page_size=20"), "student class list"
        )
        classes = list_from(class_content, "classList", "classlist", "rows", "list")
        if [row for row in classes if row_id(row) == class_id] != [row for row in classes if row_id(row) == class_id][:1]:
            raise AssertionError(f"student class list duplicates class {class_id}")
        if not any(row_id(row) == class_id for row in classes):
            raise AssertionError(f"student cannot see class {class_id}")

        timetable_content = require_success(
            fetch_json(page, "/api/stu/get/stu/timetable/new?page_no=1&page_size=50"), "student timetable"
        )
        timetable = list_from(timetable_content, "tchPlanList", "stuTchPlanList", "rows", "list")
        timetable_ids = {row_id(row) for row in timetable}
        if not expected_plans.issubset(timetable_ids):
            raise AssertionError(f"student timetable {timetable_ids} does not contain {expected_plans}")
        attendance_states = {int(row.get("sign_state") or row.get("signState") or 0) for row in timetable}
        if not attendance_states.intersection({0, 1}):
            raise AssertionError("student timetable has no attendance state")

        navigate(page, "/code-classroom/myClass")
        class_page = page_state(page)
        if class_name not in page.locator("body").inner_text():
            raise AssertionError("student class page does not render the assigned class")

        result.update(
            {
                "class_id": class_id,
                "class_page": class_page,
                "timetable_plan_ids": sorted(int(plan_id) for plan_id in timetable_ids if plan_id is not None),
                "attendance_states": sorted(attendance_states),
            }
        )
        page.screenshot(path=str(OUTDIR / "student_class_page.png"), full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        page.screenshot(path=str(OUTDIR / "student_error.png"), full_page=True)
    finally:
        result["events"] = events.summary()
        context.close()
    result["passed"] = "error" not in result and result["events"]["passed"]
    return result


def audit_public_return(browser) -> dict[str, Any]:
    context, page, events, _ = login(browser, "admin")
    result: dict[str, Any] = {}
    try:
        for name, path, selector in (
            ("competitions", "/competitions.html", ".nav-logo"),
            ("courses", "/courses", '.nav-links a[href="/#hero"]'),
        ):
            navigate(page, path, settle_ms=700)
            link = page.locator(selector).first
            if link.count() == 0 or link.get_attribute("href") != "/#hero":
                raise AssertionError(f"{name}: homepage link is missing or incorrect")
            link.click(timeout=5000)
            page.wait_for_timeout(700)
            state = page_state(page)
            if state["path"] != "/":
                raise AssertionError(f"{name}: homepage link went to {state['path']}")
            result[name] = state
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        page.screenshot(path=str(OUTDIR / "public_return_error.png"), full_page=True)
    finally:
        result["events"] = events.summary()
        context.close()
    result["passed"] = "error" not in result and result["events"]["passed"]
    return result


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"base_url": BASE, "generated_at": dt.datetime.now().isoformat()}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            summary["admin"] = audit_admin(browser)
            summary["teacher"] = audit_teacher(browser, summary["admin"])
            summary["student"] = audit_student(browser, summary["admin"])
            summary["public_return"] = audit_public_return(browser)
        except Exception as exc:
            summary["fatal_error"] = str(exc)
            summary["traceback"] = traceback.format_exc()
        finally:
            browser.close()

    summary["all_passed"] = (
        "fatal_error" not in summary
        and all(summary.get(key, {}).get("passed") for key in ("admin", "teacher", "student", "public_return"))
    )
    dump_json(OUTDIR / "summary.json", summary)
    print(f"audit_artifacts={OUTDIR}")
    print(f"all_passed={summary['all_passed']}")
    raise SystemExit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
