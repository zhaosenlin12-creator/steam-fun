from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from steamfun_mirror.browser_audit import navigate_for_audit


BASE = "http://127.0.0.1:8000"
ROOT = Path(r"D:\kaifa\steam_fun")
OUTDIR = ROOT / "runtime" / f"ppt_legacy_text_fix_{dt.datetime.now():%Y%m%d_%H%M%S}"
TARGETS = {
    104: {
        "teach_url": f"{BASE}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=104&teaching_plan_id=999999",
    },
    398: {
        "teach_url": f"{BASE}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=398&teaching_plan_id=999999",
    },
    14603: {
        "teach_url": f"{BASE}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=14603&teaching_plan_id=999999",
    },
}


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


def inspect_frame(frame) -> dict[str, Any]:
    return frame.evaluate(
        """() => {
          const spans = Array.from(document.querySelectorAll('span[id^="txt"]')).map((node) => {
            const style = window.getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            const parent = node.parentElement;
            const parentStyle = parent ? window.getComputedStyle(parent) : null;
            return {
              id: node.id,
              text: (node.textContent || '').trim(),
              dataWidth: node.getAttribute('data-width'),
              width: rect.width,
              height: rect.height,
              whiteSpace: style.whiteSpace,
              position: style.position,
              lineHeight: style.lineHeight,
              parentWidth: parent ? parent.getBoundingClientRect().width : null,
              parentWhiteSpace: parentStyle ? parentStyle.whiteSpace : null,
              parentStyle: parent ? parent.getAttribute('style') || '' : '',
            };
          });
          return {
            href: location.href,
            title: document.title,
            bodyText: document.body ? document.body.innerText.slice(0, 4000) : '',
            legacyGuardPresent: !!window.__localLegacyIspringTextGuard,
            spans,
          };
        }"""
    )


def inspect_page(page) -> dict[str, Any]:
    iframe_element = page.locator("iframe").first
    frame_box = iframe_element.bounding_box()
    frame = page.frames[1] if len(page.frames) > 1 else page.main_frame
    try:
        frame.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(4000)
    state = inspect_frame(frame)
    state["frame_box"] = frame_box
    state["outer_url"] = page.url
    state["outer_title"] = page.title()
    state["outer_body_sample"] = page.locator("body").inner_text()[:1500]
    return state


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900}, locale="zh-CN")

        for material_id, spec in TARGETS.items():
            page = context.new_page()
            watchers = attach_watchers(page)
            navigate_for_audit(page, spec["teach_url"])
            state = inspect_page(page)
            shot = OUTDIR / f"{material_id}_teach.png"
            page.screenshot(path=str(shot), full_page=True)
            result = {
                "material_id": material_id,
                "network": watchers,
                "state": state,
                "screenshot": str(shot),
            }
            dump_json(OUTDIR / f"{material_id}.json", result)
            summary.append(result)
            page.close()

        browser.close()

    dump_json(OUTDIR / "summary.json", summary)
    print(str(OUTDIR))


if __name__ == "__main__":
    main()
