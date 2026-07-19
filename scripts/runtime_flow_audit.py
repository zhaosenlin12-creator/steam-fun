from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from steamfun_mirror.browser_audit import navigate_for_audit, split_request_failures
from steamfun_mirror.runtime_audit import get_login_flow
from steamfun_mirror.runtime_audit import should_force_post_login_navigation


BASE = "http://127.0.0.1:8000"
OUTDIR = Path(r"D:\kaifa\steam_fun\runtime\runtime_flow_audit")
OUTDIR.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _storage_state(page) -> tuple[dict[str, str], dict[str, str]]:
    state = page.evaluate(
        """() => {
            const ls = {};
            const ss = {};
            try {
              for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                ls[k] = localStorage.getItem(k);
              }
            } catch (e) {}
            try {
              for (let i = 0; i < sessionStorage.length; i++) {
                const k = sessionStorage.key(i);
                ss[k] = sessionStorage.getItem(k);
              }
            } catch (e) {}
            return { localStorage: ls, sessionStorage: ss };
        }"""
    )
    return state["localStorage"], state["sessionStorage"]


def _storage_state_with_retry(page, *, attempts: int = 3, wait_ms: int = 1000) -> tuple[dict[str, str], dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return _storage_state(page)
        except Exception as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            page.wait_for_timeout(wait_ms)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
    raise RuntimeError(f"unable to read storage state: {last_error}")


def login(page, username: str, password: str, *, role: str) -> None:
    flow = get_login_flow(role)
    navigate_for_audit(page, f"{BASE}{flow.path}", settle_timeout_ms=1500)
    page.wait_for_timeout(1500)
    if flow.role_tab_selector is not None:
        page.locator(flow.role_tab_selector).click()
        page.wait_for_timeout(800)
    inputs = page.locator("input:visible")
    count = inputs.count()
    if count < 2:
        raise RuntimeError(f"expected visible login inputs for {role} on {flow.path}, found {count}")
    inputs.nth(0).fill(username)
    inputs.nth(1).fill(password)
    buttons = page.locator("button:visible")
    submit = buttons.filter(has_text="立即登录")
    if submit.count() > 0:
        submit.first.click()
    elif buttons.count() > 0:
        buttons.first.click()
    else:
        page.keyboard.press("Enter")
    try:
        page.wait_for_function(
            """() => {
                try {
                    const raw = localStorage.getItem('vuex') || '';
                    const parsed = raw ? JSON.parse(raw) : {};
                    const token = ((((parsed || {}).user) || {}).token || '').trim();
                    if (token) {
                        return true;
                    }
                } catch (e) {}
                const path = location.pathname || '';
                return path !== '/login' && path !== '/background/login';
            }""",
            timeout=10000,
        )
    except Exception:
        pass
    page.wait_for_timeout(1200)
    local_storage, _ = _storage_state_with_retry(page)
    if should_force_post_login_navigation(page.url, local_storage):
        navigate_for_audit(page, f"{BASE}{flow.fallback_path}", settle_timeout_ms=2000)


def snapshot_page(page, name: str) -> dict[str, Any]:
    state: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            state = page.evaluate(
                """() => {
                    const ls = {};
                    const ss = {};
                    try {
                      for (let i = 0; i < localStorage.length; i++) {
                        const k = localStorage.key(i);
                        ls[k] = localStorage.getItem(k);
                      }
                    } catch (e) {}
                    try {
                      for (let i = 0; i < sessionStorage.length; i++) {
                        const k = sessionStorage.key(i);
                        ss[k] = sessionStorage.getItem(k);
                      }
                    } catch (e) {}
                    return {
                      href: location.href,
                      title: document.title,
                      text: document.body ? document.body.innerText.slice(0, 4000) : '',
                      localStorage: ls,
                      sessionStorage: ss,
                    };
                }"""
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                page.wait_for_timeout(1000)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                continue
            raise
    if state is None:
        raise RuntimeError(f"snapshot failed for {name}: {last_error}")
    page.screenshot(path=str(OUTDIR / f"{name}.png"), full_page=True)
    dump_json(OUTDIR / f"{name}.json", state)
    return state


def page_probe(
    context,
    *,
    url: str,
    name: str,
    wait_ms: int = 4000,
) -> dict[str, Any]:
    page = context.new_page()
    failures: list[dict[str, Any]] = []
    console: list[dict[str, Any]] = []

    page.on(
        "requestfailed",
        lambda req: failures.append(
            {
                "url": req.url,
                "method": req.method,
                "failure": req.failure,
            }
        ),
    )
    page.on(
        "console",
        lambda msg: console.append(
            {
                "type": msg.type,
                "text": msg.text,
            }
        ),
    )

    navigate_for_audit(page, url, settle_timeout_ms=wait_ms)
    actionable_failures, benign_aborted_failures = split_request_failures(failures)
    state = snapshot_page(page, name)
    result = {
        "name": name,
        "url": url,
        "final_url": state["href"],
        "title": state["title"],
        "text_excerpt": state["text"][:1200],
        "request_failures": actionable_failures,
        "benign_aborted_requests": benign_aborted_failures,
        "console_errors": [item for item in console if item["type"] in {"error", "warning"}],
    }
    dump_json(OUTDIR / f"{name}.probe.json", result)
    page.close()
    return result


def main() -> None:
    results: dict[str, Any] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        admin_context = browser.new_context(ignore_https_errors=True)
        admin_page = admin_context.new_page()
        login(admin_page, "18164173640", "123456", role="admin")
        results["admin_login"] = snapshot_page(admin_page, "admin_login")
        admin_page.close()

        teacher_context = browser.new_context(ignore_https_errors=True)
        teacher_page = teacher_context.new_page()
        login(teacher_page, "zhaosenlin", "123456", role="teacher")
        results["teacher_login"] = snapshot_page(teacher_page, "teacher_login")
        teacher_page.close()

        student_context = browser.new_context(ignore_https_errors=True)
        student_page = student_context.new_page()
        login(student_page, "lbschenmuran", "123456", role="student")
        results["student_login"] = snapshot_page(student_page, "student_login")
        student_page.close()

        probes = {
            "admin_platform_curriculum": (admin_context, f"{BASE}/background/course-management/platform-curriculum"),
            "admin_school_curriculum": (admin_context, f"{BASE}/background/course-management/school-curriculum"),
            "teacher_class_management": (teacher_context, f"{BASE}/school-home-page/class-management1/class-management1"),
            "teacher_students_management": (teacher_context, f"{BASE}/school-home-page/class-management1/students-management1"),
            "teacher_teachplan": (teacher_context, f"{BASE}/school-home-page/class-management1/teachplan1"),
            "teacher_prepare_root": (teacher_context, f"{BASE}/code-classroom/prepare-lessons"),
            "teacher_prepare_ppt": (
                teacher_context,
                f"{BASE}/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=39525&tchPlanId=999999",
            ),
            "teacher_teach_ppt": (
                teacher_context,
                f"{BASE}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999",
            ),
            "student_myclass": (student_context, f"{BASE}/code-classroom/myClass"),
        }

        for name, (context, url) in probes.items():
            results[name] = page_probe(context, url=url, name=name)

        browser.close()

    dump_json(OUTDIR / "summary.json", results)


if __name__ == "__main__":
    main()
