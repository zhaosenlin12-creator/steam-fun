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
OUTDIR = ROOT / "runtime" / f"runtime_flow_audit_{dt.datetime.now():%Y%m%d_%H%M%S}"

ROLE_ACCOUNTS = {
    "admin": "18164173640",
    "teacher": "zhaosenlin",
    "student": "lbschenmuran",
}

ROLE_ROUTES = {
    "admin": (
        ("/workspace/admin", "/school-home-page/class-management1"),
        ("/workspace/admin#teachers", "/school-home-page/class-management1"),
        ("/workspace/admin#campuses", "/school-home-page/class-management1"),
        ("/background/course-management/platform-curriculum", "/school-home-page/class-management1"),
        (
            "/background/course-management/school-curriculum",
            "/school-home-page/course-list",
        ),
        ("/school-home-page/school-user-list", "/school-home-page/school-user-list"),
        ("/school-home-page/class-management1", "/school-home-page/class-management1"),
        ("/school-home-page/class-management1/students-management1", "/school-home-page/class-management1/students-management1"),
    ),
    "teacher": (
        ("/workspace/teacher", "/code-classroom/classroom-index"),
        ("/code-classroom/classroom-index", "/code-classroom/classroom-index"),
        (
            "/school-home-page/class-management1/class-management1",
            "/school-home-page/class-management1",
        ),
        (
            "/school-home-page/class-management1/students-management1",
            "/school-home-page/class-management1/students-management1",
        ),
        (
            "/school-home-page/class-management1/teachplan1",
            "/school-home-page/class-management1/teachplan1",
        ),
        ("/code-classroom/prepare-lessons", "/code-classroom/prepare-lessons"),
        (
            "/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=39525&tchPlanId=999999",
            "/code-classroom/prepare-lessons/prepare/ppt",
        ),
        (
            "/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999",
            "/code-classroom/teach-lessons/lessons/ppt",
        ),
        ("/school-home-page/orderpay", "/code-classroom/classroom-index"),
    ),
    "student": (
        ("/code-classroom/myClass", "/code-classroom/myClass"),
    ),
}

ROLE_HOME_RETURN = {
    "admin": (
        "/school-home-page/class-management1",
        "返回首页",
        "/school-home-page/class-management1",
    ),
    "teacher": (
        "/code-classroom/classroom-index",
        "首页",
        "/code-classroom/classroom-index",
    ),
    "student": (
        "/code-classroom/myClass",
        "首页",
        "/code-classroom/myClass",
    ),
}

DISABLED_FEATURE_MARKERS = (
    "orderpay",
    "financial",
    "recharge",
    "starcoin",
    "starmanagement",
    "cluemanagement",
    "order-report",
    "enrollmentoperation",
)


class EventRecorder:
    def __init__(self, page: Page) -> None:
        self.console_messages: list[dict[str, Any]] = []
        self.page_errors: list[dict[str, Any]] = []
        self.request_failures: list[dict[str, Any]] = []
        self.expected_navigation_aborts: list[dict[str, Any]] = []
        self.bad_responses: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []
        self._expecting_navigation = False
        page.on(
            "console",
            lambda message: self.console_messages.append(
                {
                    "type": message.type,
                    "text": message.text,
                    "location": message.location,
                }
            ),
        )
        page.on(
            "pageerror",
            lambda error: self.page_errors.append({"message": str(error)}),
        )
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)
        page.on(
            "request",
            lambda request: self.requests.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type,
                }
            ),
        )

    def _on_response(self, response) -> None:
        if response.status >= 400:
            self.bad_responses.append(
                {
                    "url": response.url,
                    "status": int(response.status),
                    "method": response.request.method,
                }
            )

    def _on_request_failed(self, request) -> None:
        row = {
            "url": request.url,
            "method": request.method,
            "resource_type": request.resource_type,
            "failure": str(request.failure or ""),
        }
        if self._expecting_navigation and "err_aborted" in row["failure"].lower():
            self.expected_navigation_aborts.append(row)
            return
        self.request_failures.append(row)

    def begin_expected_navigation(self) -> None:
        self._expecting_navigation = True

    def end_expected_navigation(self) -> None:
        self._expecting_navigation = False

    def summary(self) -> dict[str, Any]:
        summary = summarize_browser_events(
            console_messages=self.console_messages,
            page_errors=self.page_errors,
            request_failures=self.request_failures,
            bad_responses=self.bad_responses,
        )
        base_host = urlparse(BASE).netloc
        external_requests = [
            row
            for row in self.requests
            if urlparse(row["url"]).scheme in {"http", "https"}
            and urlparse(row["url"]).netloc != base_host
        ]
        disabled_feature_requests = [
            row
            for row in self.requests
            if row["resource_type"] != "document"
            and any(marker in row["url"].lower() for marker in DISABLED_FEATURE_MARKERS)
        ]
        summary["external_requests"] = external_requests
        summary["disabled_feature_requests"] = disabled_feature_requests
        summary["expected_navigation_aborts"] = list(self.expected_navigation_aborts)
        summary["request_count"] = len(self.requests)
        summary["passed"] = summary["passed"] and not external_requests and not disabled_feature_requests
        return summary


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def path_of(url: str) -> str:
    return urlparse(url).path or "/"


def navigate(page: Page, path: str, *, settle_ms: int = 1500) -> None:
    navigate_for_audit(
        page,
        f"{BASE}{path}",
        networkidle_timeout_ms=7000,
        settle_timeout_ms=settle_ms,
    )


def safe_state(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          let user = {};
          try {
            const parsed = JSON.parse(localStorage.getItem('vuex') || '{}');
            user = (parsed && parsed.user) || {};
          } catch (error) {}
          return {
            href: location.href,
            title: document.title,
            bodyLength: document.body ? document.body.innerText.trim().length : 0,
            horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
            mirrorProfile: sessionStorage.getItem('mirror_profile'),
            sessionKeys: Object.keys(sessionStorage).sort(),
            localKeys: Object.keys(localStorage).sort(),
            hasToken: Boolean(String(user.token || '').trim()),
            identity: user.identity,
            roleFlags: {
              isAdmin: user.isAdmin,
              isTeacher: user.isTeacher,
              isStudent: user.isStudent
            }
          };
        }"""
    )


def login(context, role: str, *, artifact_suffix: str = "desktop") -> dict[str, Any]:
    flow = get_login_flow(role)
    form = "#form-student" if role == "student" else "#form-teacher"
    page = context.new_page()
    events = EventRecorder(page)
    result: dict[str, Any] = {"role": role, "error": None}
    try:
        navigate(page, flow.path, settle_ms=500)
        if flow.role_tab_selector:
            page.locator(flow.role_tab_selector).click()
        page.locator(f'{form} input[name="userName"]').fill(ROLE_ACCOUNTS[role])
        page.locator(f'{form} input[name="password"]').fill("123456")
        page.locator(f'{form} button[type="submit"]').click()
        page.wait_for_url(lambda url: path_of(url) == flow.fallback_path, timeout=20000)
        try:
            page.wait_for_load_state("networkidle", timeout=7000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(1000)
        state = safe_state(page)
        if path_of(state["href"]) != flow.fallback_path:
            raise AssertionError(
                f"{role}: expected landing {flow.fallback_path}, got {state['href']}"
            )
        if state["mirrorProfile"] != role or not state["hasToken"]:
            raise AssertionError(f"{role}: incomplete authenticated state: {state}")
        if state["bodyLength"] <= 0:
            raise AssertionError(f"{role}: landing page is blank")
        if state["horizontalOverflow"]:
            raise AssertionError(f"{role}: landing page has horizontal viewport overflow")
        forbidden_selector = "[data-teacher-only]:visible" if role == "admin" else "[data-admin-only]:visible"
        forbidden_controls = page.locator(forbidden_selector).count()
        if forbidden_controls:
            raise AssertionError(
                f"{role}: landing page exposes {forbidden_controls} controls for another role"
            )
        result["visible_forbidden_controls"] = forbidden_controls
        result["state"] = state
        result["screenshot"] = str(OUTDIR / f"{role}_login_{artifact_suffix}.png")
        page.screenshot(path=result["screenshot"], full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        try:
            error_path = OUTDIR / f"{role}_login_{artifact_suffix}_error.png"
            page.screenshot(path=str(error_path), full_page=True)
            result["error_screenshot"] = str(error_path)
        except Exception:
            pass
    finally:
        result["events"] = events.summary()
        page.close()
    result["passed"] = result["error"] is None and result["events"]["passed"]
    return result


def audit_logout(context, role: str) -> dict[str, Any]:
    page = context.new_page()
    events = EventRecorder(page)
    result: dict[str, Any] = {"role": role, "error": None}
    try:
        navigate(page, "/logout", settle_ms=500)
        page.wait_for_url(lambda url: path_of(url) == "/login", timeout=15000)
        before_reload = safe_state(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        after_reload = safe_state(page)
        profile_cookie_present = any(
            cookie.get("name") == "mirror_profile"
            for cookie in context.cookies(BASE)
        )
        for phase, state in (("before reload", before_reload), ("after reload", after_reload)):
            if path_of(state["href"]) != "/login":
                raise AssertionError(f"{role}: logout {phase} ended at {state['href']}")
            if state["mirrorProfile"] is not None or state["hasToken"]:
                raise AssertionError(f"{role}: authenticated state survived logout {phase}: {state}")
        if profile_cookie_present:
            raise AssertionError(f"{role}: mirror_profile cookie survived logout")
        result["before_reload"] = before_reload
        result["after_reload"] = after_reload
        result["profile_cookie_present"] = profile_cookie_present
        result["screenshot"] = str(OUTDIR / f"{role}_logout.png")
        page.screenshot(path=result["screenshot"], full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
    finally:
        result["events"] = events.summary()
        page.close()
    result["passed"] = result["error"] is None and result["events"]["passed"]
    return result


def route_artifact_name(role: str, path: str) -> str:
    normalized = path.split("?", 1)[0].strip("/").replace("/", "_")
    return f"{role}_{normalized or 'root'}"


def probe_route(context, role: str, path: str, expected_path: str) -> dict[str, Any]:
    page = context.new_page()
    events = EventRecorder(page)
    name = route_artifact_name(role, path)
    result: dict[str, Any] = {"role": role, "requested": path, "error": None}
    try:
        navigate(page, path)
        state = safe_state(page)
        if path_of(state["href"]) != expected_path:
            raise AssertionError(
                f"{role}: {path} ended at {state['href']} instead of {expected_path}"
            )
        if state["bodyLength"] <= 0:
            raise AssertionError(f"{role}: {path} rendered a blank page")
        if state["mirrorProfile"] not in {None, role}:
            raise AssertionError(f"{role}: {path} leaked profile {state['mirrorProfile']!r}")
        result["state"] = state
        result["screenshot"] = str(OUTDIR / f"{name}.png")
        page.screenshot(path=result["screenshot"], full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        try:
            error_path = OUTDIR / f"{name}_error.png"
            page.screenshot(path=str(error_path), full_page=True)
            result["error_screenshot"] = str(error_path)
        except Exception:
            pass
    finally:
        result["events"] = events.summary()
        page.close()
    result["passed"] = result["error"] is None and result["events"]["passed"]
    return result


def audit_home_return(context, role: str) -> dict[str, Any]:
    source_path, label, expected_path = ROLE_HOME_RETURN[role]
    page = context.new_page()
    events = EventRecorder(page)
    result: dict[str, Any] = {
        "role": role,
        "source_path": source_path,
        "label": label,
        "expected_path": expected_path,
        "error": None,
    }
    try:
        navigate(page, source_path, settle_ms=1800)
        candidates = page.get_by_text(label, exact=True)
        visible_candidates = [
            candidates.nth(index)
            for index in range(candidates.count())
            if candidates.nth(index).is_visible()
        ]
        if len(visible_candidates) != 1:
            raise AssertionError(
                f"{role}: expected one visible {label!r} control on {source_path}, "
                f"found {len(visible_candidates)}"
            )
        before = safe_state(page)
        events.begin_expected_navigation()
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                visible_candidates[0].click()
        finally:
            events.end_expected_navigation()
        page.wait_for_url(lambda url: path_of(url) == expected_path, timeout=15000)
        if role == "student":
            page.wait_for_timeout(2000)
            page.wait_for_function(
                """() => {
                    const body = document.body ? document.body.innerText : '';
                    if (body.includes('Loading')) return false;
                    const visible = (selector) => Array.from(document.querySelectorAll(selector))
                        .some((node) => node.getBoundingClientRect().width > 0
                            && node.getBoundingClientRect().height > 0
                            && getComputedStyle(node).visibility !== 'hidden');
                    return visible('.class-list-wrapper .el-col') || visible('.el-empty');
                }""",
                timeout=15000,
            )
        else:
            page.wait_for_function(
                "() => !(document.body && document.body.innerText.includes('Loading'))",
                timeout=10000,
            )
        page.wait_for_timeout(1000)
        after = safe_state(page)
        if path_of(after["href"]) != expected_path:
            raise AssertionError(
                f"{role}: {label} ended at {after['href']} instead of {expected_path}"
            )
        if after["bodyLength"] <= 0:
            raise AssertionError(f"{role}: {label} rendered a blank role home")
        if after["horizontalOverflow"]:
            raise AssertionError(f"{role}: role home has horizontal viewport overflow")
        result["before"] = before
        result["after"] = after
        result["screenshot"] = str(OUTDIR / f"{role}_home_return.png")
        page.screenshot(path=result["screenshot"], full_page=False)
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        try:
            error_path = OUTDIR / f"{role}_home_return_error.png"
            page.screenshot(path=str(error_path), full_page=True)
            result["error_screenshot"] = str(error_path)
        except Exception:
            pass
    finally:
        result["events"] = events.summary()
        page.close()
    result["passed"] = result["error"] is None and result["events"]["passed"]
    return result


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(),
        "base_url": BASE,
        "artifact_dir": str(OUTDIR),
        "roles": {},
        "fatal_error": None,
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for role, routes in ROLE_ROUTES.items():
                    context = browser.new_context(viewport={"width": 1440, "height": 900})
                    role_result: dict[str, Any] = {
                        "login": login(context, role),
                        "routes": [],
                    }
                    if role_result["login"]["passed"]:
                        role_result["routes"] = [
                            probe_route(context, role, path, expected_path)
                            for path, expected_path in routes
                        ]
                        role_result["home_return"] = audit_home_return(context, role)
                        role_result["logout"] = audit_logout(context, role)
                    else:
                        role_result["home_return"] = {"passed": False, "error": "login failed"}
                        role_result["logout"] = {"passed": False, "error": "login failed"}
                    role_result["passed"] = (
                        role_result["login"]["passed"]
                        and len(role_result["routes"]) == len(routes)
                        and all(route["passed"] for route in role_result["routes"])
                        and role_result["home_return"]["passed"]
                        and role_result["logout"]["passed"]
                    )
                    mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
                    role_result["mobile_login"] = login(
                        mobile_context,
                        role,
                        artifact_suffix="mobile",
                    )
                    mobile_context.close()
                    role_result["passed"] = role_result["passed"] and role_result["mobile_login"]["passed"]
                    summary["roles"][role] = role_result
                    context.close()
            finally:
                browser.close()
    except Exception as exc:
        summary["fatal_error"] = str(exc)
        summary["fatal_traceback"] = traceback.format_exc()

    summary["all_passed"] = (
        summary["fatal_error"] is None
        and len(summary["roles"]) == len(ROLE_ROUTES)
        and all(result["passed"] for result in summary["roles"].values())
    )
    dump_json(OUTDIR / "summary.json", summary)

    print(f"audit_artifacts={OUTDIR}")
    for role, result in summary["roles"].items():
        failed_routes = [
            route["requested"] for route in result["routes"] if not route["passed"]
        ]
        print(
            f"role.{role}={result['passed']} "
            f"login={result['login']['passed']} "
            f"home_return={result['home_return']['passed']} "
            f"failed_routes={failed_routes}"
        )
    print(f"all_passed={summary['all_passed']}")
    raise SystemExit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
