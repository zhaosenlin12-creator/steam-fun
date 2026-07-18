from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from steamfun_mirror.browser_audit import navigate_for_audit, split_request_failures


BASE = "http://127.0.0.1:8000"
ROOT = Path(r"D:\kaifa\steam_fun")
OUTDIR = ROOT / "runtime" / f"ppt_loading_feedback_{dt.datetime.now():%Y%m%d_%H%M%S}"
PAGE_URL = f"{BASE}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=398&teaching_plan_id=999999"
ACTIONS = [
    ("class_result", "课堂成果"),
    ("teach_template", "授课模板"),
    ("student_handout", "学生讲义"),
    ("start_create", "开始创作"),
]


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def attach_watchers(page) -> dict[str, Any]:
    state: dict[str, Any] = {
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
        "bad_responses": [],
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
        state["failed_requests"].append(
            {
                "url": req.url,
                "method": req.method,
                "failure": failure_text,
            }
        )

    def on_response(resp) -> None:
        if resp.status >= 400:
            state["bad_responses"].append({"url": resp.url, "status": resp.status})

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)
    return state


def overlay_state(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const overlay = document.querySelector('.local-course-loading-overlay');
          const host = document.querySelector('.local-course-loading-host');
          return {
            exists: !!overlay,
            visible: !!(overlay && overlay.classList.contains('is-visible')),
            text: overlay ? (overlay.innerText || '').trim() : '',
            hostLoading: !!(host && host.classList.contains('is-loading')),
          };
        }"""
    )


def component_state(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const element = Array.from(document.querySelectorAll('*')).find(
            el => el.__vue__ && el.__vue__.$options && el.__vue__.$options.name === 'teach-ppt'
          );
          const vue = element && element.__vue__;
          if (!vue) return { found: false };
          return {
            found: true,
            drawer: !!vue.drawer,
            drawer1: !!vue.drawer1,
            project_url: vue.project_url || '',
            project_url1: vue.project_url1 || '',
          };
        }"""
    )


def click_action(page, label: str) -> None:
    locator = page.locator(".content_right").get_by_text(label, exact=True)
    if locator.count() == 0:
        locator = page.get_by_text(label, exact=True)
    for idx in range(locator.count()):
        item = locator.nth(idx)
        try:
            if not item.is_visible():
                continue
            item.evaluate("(el) => el.click()")
            return
        except Exception:
            continue
    raise RuntimeError(f"action not found: {label}")


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900}, locale="zh-CN")

        for action_name, label in ACTIONS:
            page = context.new_page()
            watchers = attach_watchers(page)
            popup_result: dict[str, Any] | None = None
            navigate_for_audit(page, PAGE_URL)

            before = {
                "overlay": overlay_state(page),
                "component": component_state(page),
            }

            popup_page = None
            try:
                with context.expect_page(timeout=2500) as popup_info:
                    click_action(page, label)
                popup_page = popup_info.value
            except Exception:
                click_action(page, label)

            page.wait_for_timeout(600)
            after_600ms = {
                "overlay": overlay_state(page),
                "component": component_state(page),
            }
            page.wait_for_timeout(1600)
            after_2200ms = {
                "overlay": overlay_state(page),
                "component": component_state(page),
            }
            page.wait_for_timeout(4000)
            after_6200ms = {
                "overlay": overlay_state(page),
                "component": component_state(page),
            }

            if popup_page is not None:
                try:
                    popup_page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                popup_page.wait_for_timeout(2500)
                popup_result = {
                    "url": popup_page.url,
                    "title": popup_page.title(),
                    "body_sample": popup_page.locator("body").inner_text()[:800],
                }
                popup_page.close()

            shot = OUTDIR / f"{action_name}.png"
            page.screenshot(path=str(shot), full_page=True)
            actionable_failures, benign_aborted_failures = split_request_failures(watchers["failed_requests"])
            watchers["failed_requests"] = actionable_failures
            watchers["benign_aborted_requests"] = benign_aborted_failures
            result = {
                "action": action_name,
                "label": label,
                "before": before,
                "after_600ms": after_600ms,
                "after_2200ms": after_2200ms,
                "after_6200ms": after_6200ms,
                "popup": popup_result,
                "network": watchers,
                "screenshot": str(shot),
            }
            dump_json(OUTDIR / f"{action_name}.json", result)
            summary.append(result)
            page.close()

        browser.close()

    dump_json(OUTDIR / "summary.json", summary)
    print(str(OUTDIR))


if __name__ == "__main__":
    main()
