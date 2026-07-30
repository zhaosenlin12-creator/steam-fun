from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from steamfun_mirror.browser_audit import navigate_for_audit, split_request_failures
from steamfun_mirror.runtime_audit import get_login_flow


ROOT = Path(r"D:\kaifa\steam_fun")
DEFAULT_BASE = os.environ.get("STEAMFUN_BASE_URL", "http://127.0.0.1:8000")
TEACHER_ACCOUNT = os.environ.get("STEAMFUN_TEACHER_ACCOUNT", "zhaosenlin")
TEACHER_PASSWORD = os.environ.get("STEAMFUN_TEACHER_PASSWORD", "123456")
POPUP_WAIT_TIMEOUT_MS = 1_500
ACTION_SETTLE_TIMEOUT_MS = 1_000


def navigate(page: Page, url: str) -> None:
    navigate_for_audit(
        page,
        url,
        networkidle_timeout_ms=1_500,
        settle_timeout_ms=500,
    )


def build_scenarios(base: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "prepare_ppt",
            "role": "teacher",
            "component": "prepare-ppt",
            "url": f"{base}/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=7001&tchPlanId=5182933",
            "actions": [
                {"name": "prepare_material", "label": "\u5907\u8bfe\u8d44\u6599"},
                {"name": "class_result", "label": "\u8bfe\u5802\u6210\u679c"},
                {"name": "teach_template", "label": "\u6388\u8bfe\u6a21\u677f"},
                {"name": "home_template", "label": "\u4f5c\u4e1a\u6a21\u677f"},
                {"name": "start_create", "label": "\u5f00\u59cb\u521b\u4f5c"},
            ],
        },
        {
            "name": "teach_ppt",
            "role": "teacher",
            "component": "teach-ppt",
            "url": f"{base}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=7001&teaching_plan_id=5182933",
            "actions": [
                {"name": "course_tools", "label": "\u8bfe\u7a0b\u5de5\u5177"},
                {"name": "class_result", "label": "\u8bfe\u5802\u6210\u679c"},
                {"name": "teach_template", "label": "\u6388\u8bfe\u6a21\u677f"},
                {"name": "home_template", "label": "\u4f5c\u4e1a\u6a21\u677f"},
                {"name": "template_sync", "label": "\u6a21\u677f\u540c\u6b65"},
                {"name": "learning_data", "label": "\u5b66\u4e60\u8d44\u6599"},
                {"name": "knowledge_poster", "label": "\u77e5\u8bc6\u70b9\u6d77\u62a5"},
                {"name": "student_management", "label": "\u5b66\u5458\u7ba1\u7406"},
                {"name": "roll_call", "label": "\u70b9\u540d\u4e0a\u8bfe"},
                {"name": "student_works", "label": "\u5b66\u751f\u4f5c\u54c1"},
                {"name": "community", "label": "\u4f5c\u54c1\u793e\u533a"},
                {"name": "start_create", "label": "\u5f00\u59cb\u521b\u4f5c"},
            ],
        },
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit classroom PPT action flows.")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base URL for the local mirror.")
    parser.add_argument(
        "--outdir",
        default=str(ROOT / "runtime" / f"click_audit_{dt.datetime.now():%Y%m%d_%H%M%S}"),
        help="Directory to store screenshots and JSON results.",
    )
    return parser.parse_args()


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return normalized.strip("_") or "item"


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


def is_login_redirect(url: str) -> bool:
    return "/login" in url


def authenticate_teacher(page: Page, base: str) -> str:
    flow = get_login_flow("teacher")
    login_url = f"{base.rstrip('/')}{flow.path}"
    navigate(page, login_url)
    if flow.role_tab_selector:
        page.locator(flow.role_tab_selector).click()
    page.locator('#form-teacher input[name="userName"]').fill(TEACHER_ACCOUNT)
    page.locator('#form-teacher input[name="password"]').fill(TEACHER_PASSWORD)
    page.locator('#form-teacher button[type="submit"]').click()
    page.wait_for_url(lambda url: urlparse(url).path == flow.fallback_path, timeout=20_000)
    page.wait_for_timeout(800)
    if urlparse(page.url).path != flow.fallback_path:
        raise AssertionError(f"teacher login landed on {page.url}")
    return page.url


def open_teacher_context(browser, base: str) -> tuple[BrowserContext, str]:
    context = browser.new_context(viewport={"width": 1900, "height": 1000}, locale="zh-CN")
    login_page = context.new_page()
    try:
        return context, authenticate_teacher(login_page, base)
    except Exception:
        context.close()
        raise
    finally:
        login_page.close()


def audit_result_passed(result: dict[str, Any]) -> bool:
    if result.get("error") or result.get("is_login_redirect"):
        return False
    for nested_key in ("popup", "probe"):
        nested = result.get(nested_key)
        if isinstance(nested, dict) and (
            nested.get("is_login_redirect")
            or nested.get("navigation_error")
            or nested.get("page_errors")
            or nested.get("request_failures")
            or nested.get("bad_responses")
        ):
            return False
    return not any(
        result.get(key)
        for key in ("page_errors", "request_failures", "bad_responses", "invalid_token_responses")
    )


def attach_watchers(page: Page) -> dict[str, Any]:
    state: dict[str, Any] = {
        "console_errors": [],
        "page_errors": [],
        "request_failures": [],
        "bad_responses": [],
        "invalid_token_responses": [],
        "dialogs": [],
        "downloads": [],
    }

    def on_console(msg) -> None:
        if msg.type == "error":
            state["console_errors"].append(msg.text)

    def on_page_error(exc: Exception) -> None:
        state["page_errors"].append(str(exc))

    def on_request_failed(req) -> None:
        failure = req.failure
        if isinstance(failure, dict):
            failure_text = failure.get("errorText", "unknown")
        elif isinstance(failure, str):
            failure_text = failure
        else:
            failure_text = "unknown"
        state["request_failures"].append(
            {
                "url": req.url,
                "method": req.method,
                "failure": failure_text,
            }
        )

    def on_response(resp) -> None:
        if resp.status >= 400:
            state["bad_responses"].append({"url": resp.url, "status": resp.status})
            return
        if len(state["invalid_token_responses"]) >= 12:
            return
        if "/api/" not in resp.url and "/java-api/" not in resp.url:
            return
        content_type = resp.headers.get("content-type", "")
        if "json" not in content_type.lower():
            return
        try:
            body = resp.text()
        except Exception:
            return
        if "InvalidToken" in body or "\u5f02\u5730\u767b\u5f55" in body:
            state["invalid_token_responses"].append(
                {
                    "url": resp.url,
                    "status": resp.status,
                    "body_sample": body[:400],
                }
            )

    def on_dialog(dialog) -> None:
        state["dialogs"].append({"type": dialog.type, "message": dialog.message})
        dialog.dismiss()

    def on_download(download) -> None:
        state["downloads"].append(
            {
                "url": download.url,
                "suggested_filename": download.suggested_filename,
            }
        )

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)
    page.on("dialog", on_dialog)
    page.on("download", on_download)
    return state


def visible_count(locator) -> int:
    visible = 0
    for idx in range(locator.count()):
        try:
            if locator.nth(idx).is_visible():
                visible += 1
        except Exception:
            continue
    return visible


def find_action_locator(page: Page, label: str):
    locator = page.get_by_text(label, exact=True)
    candidates: list[tuple[float, int]] = []
    for idx in range(locator.count()):
        item = locator.nth(idx)
        try:
            if not item.is_visible():
                continue
            box = item.bounding_box()
        except Exception:
            continue
        if box:
            candidates.append((box["y"], idx))
    if candidates:
        candidates.sort(reverse=True)
        return locator.nth(candidates[0][1])

    fuzzy = page.get_by_text(label, exact=False)
    fuzzy_candidates: list[tuple[float, int]] = []
    for idx in range(fuzzy.count()):
        item = fuzzy.nth(idx)
        try:
            if not item.is_visible():
                continue
            box = item.bounding_box()
        except Exception:
            continue
        if box:
            fuzzy_candidates.append((box["y"], idx))
    if fuzzy_candidates:
        fuzzy_candidates.sort(reverse=True)
        return fuzzy.nth(fuzzy_candidates[0][1])
    return None


def component_state(page: Page, component_name: str) -> dict[str, Any]:
    return page.evaluate(
        """
(componentName) => {
  const element = Array.from(document.querySelectorAll('*')).find(
    el => el.__vue__ && el.__vue__.$options && el.__vue__.$options.name === componentName
  );
  const vue = element && element.__vue__;
  if (!vue) {
    return {found: false};
  }
  return {
    found: true,
    project_url: vue.project_url || '',
    project_url1: vue.project_url1 || '',
    drawer: !!vue.drawer,
    drawer1: !!vue.drawer1,
    dialogVisible: !!vue.dialogVisible,
    dialogVisible1: !!vue.dialogVisible1,
    dialogVisible7: !!vue.dialogVisible7,
    sync_drawer: !!vue.sync_drawer,
    project_targets: [
      vue.project_url || '',
      vue.project_url1 || '',
      vue.stu_note_url || '',
      vue.other_meterial_url || '',
      vue.code_url || '',
      vue.ppt_url || ''
    ].filter(Boolean),
    curriculumMaterial: vue.curriculumMaterial || null,
    tchPlanId: vue.tchPlanId || vue.teachingPlanId || '',
    workInfo: vue.workInfo || null,
  };
}
""",
        component_name,
    )


def body_sample(page: Page, limit: int = 1200) -> str:
    try:
        return page.locator("body").inner_text()[:limit]
    except Exception as exc:
        return f"<body unavailable: {exc}>"


def pick_probe_target(action_label: str, state: dict[str, Any]) -> str | None:
    if not state.get("found"):
        return None
    if state.get("project_url1"):
        return str(state["project_url1"])
    if state.get("project_url"):
        return str(state["project_url"])
    if action_label == "\u5b66\u751f\u8bb2\u4e49":
        for candidate in state.get("project_targets", []):
            if ".pdf" in candidate.lower():
                return str(candidate)
    if action_label == "\u5b66\u4e60\u8d44\u6599":
        for candidate in state.get("project_targets", []):
            if candidate and candidate != state.get("project_url"):
                return str(candidate)
    return None


def probe_target_page(
    context: BrowserContext,
    url: str,
    outdir: Path,
    prefix: str,
    *,
    base: str,
) -> dict[str, Any]:
    page = context.new_page()
    watchers = attach_watchers(page)
    target_url = urljoin(base, url) if url.startswith("/") else url
    navigation_error = None
    try:
        navigate(page, target_url)
    except Exception as exc:
        navigation_error = str(exc)
        page.wait_for_timeout(2000)

    actionable_failures, benign_aborted_failures = split_request_failures(watchers["request_failures"])
    watchers["request_failures"] = actionable_failures
    watchers["benign_aborted_requests"] = benign_aborted_failures

    shot = outdir / f"{prefix}_target.png"
    result = {
        "requested_url": target_url,
        "final_url": page.url,
        "title": page.title(),
        "is_login_redirect": is_login_redirect(page.url),
        "body_sample": body_sample(page),
        "body_length": len(body_sample(page, limit=20000)),
        "screenshot": safe_screenshot(page, shot, full_page=True) if navigation_error is None else None,
        "navigation_error": navigation_error,
        **watchers,
    }
    page.close()
    return result


def run_action(
    context: BrowserContext,
    scenario: dict[str, Any],
    action: dict[str, str],
    outdir: Path,
    *,
    base: str,
    authenticated_url: str,
) -> dict[str, Any]:
    page = context.new_page()
    watchers = attach_watchers(page)
    navigate(page, scenario["url"])

    target = find_action_locator(page, action["label"])
    result: dict[str, Any] = {
        "scenario": scenario["name"],
        "action": action["name"],
        "label": action["label"],
        "authenticated_url": authenticated_url,
        "initial_url": page.url,
        "component_before": component_state(page, scenario["component"]),
        "body_before": body_sample(page),
        "visible_text_count": visible_count(page.get_by_text(action["label"], exact=True)),
        "popup": None,
        "probe": None,
    }

    if target is None:
        result["error"] = "label_not_found"
        shot = outdir / f"{scenario['name']}_{action['name']}_missing.png"
        result["screenshot"] = safe_screenshot(page, shot, full_page=True)
        result.update(watchers)
        page.close()
        return result

    popup_page: Page | None = None
    try:
        with context.expect_page(timeout=POPUP_WAIT_TIMEOUT_MS) as popup_info:
            target.click(timeout=10000)
        popup_page = popup_info.value
    except PlaywrightTimeoutError:
        popup_page = None

    page.wait_for_timeout(ACTION_SETTLE_TIMEOUT_MS)
    result["final_url"] = page.url
    result["is_login_redirect"] = is_login_redirect(page.url)
    result["component_after"] = component_state(page, scenario["component"])
    result["body_after"] = body_sample(page)
    shot = outdir / f"{scenario['name']}_{action['name']}.png"
    result["screenshot"] = safe_screenshot(page, shot, full_page=True)
    actionable_failures, benign_aborted_failures = split_request_failures(watchers["request_failures"])
    watchers["request_failures"] = actionable_failures
    watchers["benign_aborted_requests"] = benign_aborted_failures
    result.update(watchers)

    if popup_page is not None:
        popup_watchers = attach_watchers(popup_page)
        popup_page.wait_for_load_state("domcontentloaded", timeout=15000)
        popup_page.wait_for_timeout(ACTION_SETTLE_TIMEOUT_MS)
        popup_shot = outdir / f"{scenario['name']}_{action['name']}_popup.png"
        result["popup"] = {
            "final_url": popup_page.url,
            "title": popup_page.title(),
            "is_login_redirect": is_login_redirect(popup_page.url),
            "body_sample": body_sample(popup_page),
            "screenshot": safe_screenshot(popup_page, popup_shot, full_page=True),
            **popup_watchers,
        }
        popup_page.close()
    else:
        probe_target = pick_probe_target(action["label"], result["component_after"])
        if probe_target:
            result["probe"] = probe_target_page(
                context,
                probe_target,
                outdir,
                f"{scenario['name']}_{action['name']}",
                base=base,
            )

    page.close()
    return result


def main() -> None:
    args = parse_args()
    base = args.base.rstrip("/")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(base)
    results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for scenario in scenarios:
            scenario_dir = outdir / safe_name(scenario["name"])
            scenario_dir.mkdir(parents=True, exist_ok=True)
            if scenario["role"] != "teacher":
                raise ValueError(f"Unsupported classroom audit role: {scenario['role']}")
            context, authenticated_url = open_teacher_context(browser, base)
            try:
                for action in scenario["actions"]:
                    results.append(
                        run_action(
                            context,
                            scenario,
                            action,
                            scenario_dir,
                            base=base,
                            authenticated_url=authenticated_url,
                        )
                    )
            finally:
                context.close()
        browser.close()

    (outdir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(outdir)
    all_passed = bool(results) and all(audit_result_passed(result) for result in results)
    print(f"all_passed={all_passed}")
    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
