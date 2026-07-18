from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:8000"
ROOT = Path(r"D:\kaifa\steam_fun")
OUTDIR = ROOT / "runtime" / f"acceptance_{dt.datetime.now():%Y%m%d_%H%M%S}"
REQUEST_TIMEOUT = 30


PAGES = [
    {
        "name": "exam_management",
        "url": f"{BASE}/exam-management",
        "checks": [
            ("text", "考试"),
            ("text", "练习"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "practice_management",
        "url": f"{BASE}/practice-management",
        "checks": [
            ("text", "练习"),
            ("text", "题库"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "competition_platform_bank",
        "url": f"{BASE}/competitionCenter/questionBankCenter/platform",
        "checks": [
            ("text", "平台"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "competition_campus_bank",
        "url": f"{BASE}/competitionCenter/questionBankCenter/campus",
        "checks": [
            ("text", "校区"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "exam_stu_new_exam",
        "url": f"{BASE}/exam-stu/new-exam",
        "checks": [
            ("text", "姓名:"),
            ("text", "账号:"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "exam_stu_practice_record",
        "url": f"{BASE}/exam-stu/practice-record",
        "checks": [
            ("text", "练习详情"),
            ("text", "返回"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "exam_paper_detail",
        "url": f"{BASE}/exam/paper-detail",
        "checks": [
            ("text", "试卷详情"),
            ("text", "返回"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "exam_practice_detail",
        "url": f"{BASE}/exam/practice-detail",
        "checks": [
            ("text", "练习详情"),
            ("text", "返回"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "prepare_lessons_root",
        "url": f"{BASE}/code-classroom/prepare-lessons",
        "checks": [
            ("text", "Jrcode"),
            ("text", "Scratch"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "teacher_myclass",
        "url": f"{BASE}/code-classroom/myClass",
        "checks": [
            ("text", "Jrcode"),
            ("text", "Scratch"),
            ("text", "Python"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "teachplan",
        "url": f"{BASE}/school-home-page/class-management1/teachplan1",
        "checks": [
            ("text", "2026"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "platform_curriculum",
        "url": f"{BASE}/background/course-management/platform-curriculum",
        "checks": [
            ("text", "Jrcode"),
            ("text", "Scratch"),
            ("text", "1299"),
        ],
        "wait_ms": 7000,
    },
    {
        "name": "school_curriculum",
        "url": f"{BASE}/background/course-management/school-curriculum",
        "checks": [
            ("text", "课程管理"),
            ("text", "课程体系名称"),
            ("text", "1299"),
        ],
    },
    {
        "name": "students_management",
        "url": f"{BASE}/school-home-page/class-management1/students-management1",
        "checks": [
            ("text", "学员管理"),
            ("text", "新增学员"),
            ("text", "lbschenmuran"),
        ],
    },
    {
        "name": "prepare_ppt",
        "url": f"{BASE}/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=39525&tchPlanId=999999",
        "checks": [
            ("text", "备课资料"),
            ("text", "课堂成果"),
            ("text", "开始创作"),
        ],
    },
    {
        "name": "teach_ppt",
        "url": f"{BASE}/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999",
        "checks": [
            ("text", "课程工具"),
            ("text", "课堂成果"),
            ("text", "学员管理"),
        ],
    },
]


RESOURCE_PROBES = [
    {
        "name": "prepare_video",
        "url": (
            f"{BASE}/_external/wugecdn.steam.fun/courses/a_jrcode_course/"
            "ac_shortTerm_course/Jrcode_202505_SummerWatermelon/video/"
            "1%E8%A5%BF%E7%93%9C%E9%A3%8E%E6%89%87%E5%A4%A7%E4%BD%9C%E6%88%98.mp4"
        ),
    },
    {
        "name": "prepare_iframe_index",
        "url": (
            f"{BASE}/_external/wugecdn.steam.fun/courses/a_jrcode_course/"
            "ac_shortTerm_course/Jrcode_202505_SummerWatermelon/"
            "01%E8%A5%BF%E7%93%9C%E9%A3%8E%E6%89%87%E5%A4%A7%E4%BD%9C%E6%88%98/index.html"
            "?usercode=22489f72-14a3-4020-8f5f-374bd6ec3eba"
        ),
    },
    {
        "name": "teach_result_icon",
        "url": f"{BASE}/img/%E8%AF%BE%E5%A0%82%E6%88%90%E6%9E%9C.png",
    },
    {
        "name": "student_avatar",
        "url": f"{BASE}/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
    },
    {
        "name": "student_handout_pdf",
        "url": (
            f"{BASE}/_external/wugecdn.steam.fun/courses/a_jrcode_course/"
            "ab_general_course/version2.0/Jrcode_01_32_2/hand_out/"
            "01%E5%88%9D%E6%AC%A1%E6%8C%91%E6%88%98%E8%AE%B2%E4%B9%89.pdf"
        ),
    },
    {
        "name": "teach_template_sjr",
        "url": (
            f"{BASE}/_external/jrcodework.oss-cn-zhangjiakou.aliyuncs.com/CourseTemplate/"
            "5e6b207df178450c488dd543/5fa5eca28b95b91eec7fb5b2/release/"
            "5fa5eca28b95b91eec7fb5b24cbe6980-1ea0-11eb-a503-5509c51070f41.sjr"
        ),
    },
    {
        "name": "course_poster_png",
        "url": (
            f"{BASE}/_external/wugecdn.steam.fun/courses/a_jrcode_course/"
            "ab_general_course/version2.0/Jrcode_01_32_2/poster_course/"
            "01-%E5%88%9D%E6%AC%A1%E6%8C%91%E6%88%98.png"
        ),
    },
]


def safe_screenshot(page, path: Path, *, full_page: bool = True) -> dict:
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


def first_visible_index(locator) -> int | None:
    for idx in range(locator.count()):
        if locator.nth(idx).is_visible():
            return idx
    return None


def split_request_failures(raw_failures: list[dict]) -> tuple[list[dict], list[dict]]:
    actionable: list[dict] = []
    aborted: list[dict] = []
    for failure in raw_failures:
        normalized = failure["failure"].lower()
        if "err_aborted" in normalized:
            aborted.append(failure)
        else:
            actionable.append(failure)
    return actionable, aborted


def is_login_redirect(url: str) -> bool:
    return "/login" in url


def safe_count(locator) -> int:
    try:
        return locator.count()
    except Exception:
        return -1


def resource_probe() -> list[dict]:
    session = requests.Session()
    results: list[dict] = []
    for spec in RESOURCE_PROBES:
        row = {"name": spec["name"], "url": spec["url"]}
        try:
            response = session.get(spec["url"], timeout=REQUEST_TIMEOUT, stream=True)
            first_chunk = b""
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    first_chunk = chunk[:64]
                    break
            row.update(
                {
                    "status": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "content_length": response.headers.get("content-length", ""),
                    "first_chunk_hex": first_chunk.hex(),
                }
            )
        except Exception as exc:
            row["error"] = str(exc)
        results.append(row)
    return results


def collect_more_menu_state(page) -> dict:
    row = page.locator("tbody tr").first
    if row.count() == 0:
        return {"found": False, "reason": "no_rows"}
    last_td = row.locator("td").nth(row.locator("td").count() - 1)
    spans = last_td.locator("span")
    if spans.count() < 2:
        return {"found": False, "reason": "missing_more_span"}
    box = spans.nth(1).bounding_box()
    if not box:
        return {"found": False, "reason": "missing_bounding_box"}
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(1500)
    items = page.locator(".el-dropdown-menu__item")
    visible_items = []
    for idx in range(items.count()):
        item = items.nth(idx)
        if item.is_visible():
            visible_items.append(item.inner_text())
    return {
        "found": True,
        "box": box,
        "item_count": items.count(),
        "visible_item_count": len(visible_items),
        "items": visible_items[:16],
    }


def collect_student_bulk_actions(page) -> list[dict]:
    labels = [
        "批量设置有效期",
        "批量设置权限",
        "批量删除",
        "批量退学",
        "批量恢复",
        "批量解绑",
        "批量重置密码",
    ]
    results: list[dict] = []
    checkbox = page.locator("tbody tr input[type='checkbox']").first
    if checkbox.count() > 0:
        try:
            checkbox.check(force=True)
            page.wait_for_timeout(1000)
        except Exception as exc:
            results.append({"label": "select_first_row", "error": str(exc)})
    for label in labels:
        locator = page.get_by_text(label, exact=True)
        row: dict = {"label": label, "count": locator.count()}
        idx = first_visible_index(locator)
        row["visible_index"] = idx
        if idx is None:
            results.append(row)
            continue
        try:
            locator.nth(idx).click(timeout=10000)
            page.wait_for_timeout(2000)
            row["after_url"] = page.url
            row["body_sample"] = page.locator("body").inner_text()[:1000]
            dialog = page.locator(".el-dialog:visible")
            row["dialog_count"] = dialog.count()
            if dialog.count() > 0:
                row["dialog_text"] = dialog.first.inner_text()[:800]
                close_btn = dialog.first.locator(".el-dialog__headerbtn")
                if close_btn.count() > 0:
                    close_btn.first.click()
                    page.wait_for_timeout(800)
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
        except Exception as exc:
            row["error"] = str(exc)
        results.append(row)
    return results


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1900, "height": 1000})

        for spec in PAGES:
            console_errors: list[str] = []
            page_errors: list[str] = []
            request_failures: list[dict] = []
            bad_responses: list[dict] = []
            invalid_token_responses: list[dict] = []

            def on_console(msg):
                if msg.type == "error":
                    console_errors.append(msg.text)

            def on_page_error(exc):
                page_errors.append(str(exc))

            def on_request_failed(req):
                failure = req.failure
                if isinstance(failure, dict):
                    failure_text = failure.get("errorText", "unknown")
                elif isinstance(failure, str):
                    failure_text = failure
                else:
                    failure_text = "unknown"
                request_failures.append(
                    {
                        "url": req.url,
                        "method": req.method,
                        "failure": failure_text,
                    }
                )

            def on_response(resp):
                if resp.status >= 400:
                    bad_responses.append({"url": resp.url, "status": resp.status})
                    return
                if len(invalid_token_responses) >= 12:
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
                if "InvalidToken" in body:
                    invalid_token_responses.append(
                        {
                            "url": resp.url,
                            "status": resp.status,
                            "body_sample": body[:400],
                        }
                    )

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)
            page.on("response", on_response)

            page.goto(spec["url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(spec.get("wait_ms", 6000))

            screenshot = OUTDIR / f"{spec['name']}.png"
            screenshot_state = safe_screenshot(page, screenshot, full_page=True)

            visible_checks = []
            for check_type, value in spec["checks"]:
                if check_type == "text":
                    count = page.locator(f"text={value}").count()
                    visible_checks.append({"type": check_type, "value": value, "count": count})

            actionable_failures, aborted_failures = split_request_failures(request_failures)
            page_state = {
                "name": spec["name"],
                "url": spec["url"],
                "final_url": page.url,
                "is_login_redirect": is_login_redirect(page.url),
                "title": page.title(),
                "visible_checks": visible_checks,
                "console_errors": console_errors,
                "page_errors": page_errors,
                "request_failures": actionable_failures,
                "aborted_request_failures": aborted_failures,
                "bad_responses": bad_responses,
                "invalid_token_responses": invalid_token_responses,
                "screenshot": screenshot_state,
                "body_sample": page.locator("body").inner_text()[:1200],
                "body_length": len(page.locator("body").inner_text()),
                "table_rows": safe_count(page.locator("tbody tr")),
                "iframe_count": safe_count(page.locator("iframe")),
                "img_count": safe_count(page.locator("img")),
            }

            if spec["name"] in {"prepare_ppt", "teach_ppt"}:
                iframe_srcs = page.locator("iframe").evaluate_all(
                    """els => els.map(el => ({src: el.getAttribute('src') || '', id: el.id || ''}))"""
                )
                page_state["iframes"] = iframe_srcs
                if spec["name"] == "prepare_ppt":
                    videos = page.locator("video").evaluate_all(
                        """els => els.map(el => ({
                            src: el.currentSrc || el.getAttribute('src') || '',
                            readyState: el.readyState,
                            networkState: el.networkState
                        }))"""
                    )
                    page_state["videos"] = videos

            results.append(page_state)
            page.remove_listener("console", on_console)
            page.remove_listener("pageerror", on_page_error)
            page.remove_listener("requestfailed", on_request_failed)
            page.remove_listener("response", on_response)

        page.goto(
            f"{BASE}/school-home-page/class-management1/students-management1",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(3000)
        add_btn = page.locator("text=新增学员")
        interaction = {"found": add_btn.count() > 0}
        add_idx = first_visible_index(add_btn)
        interaction["visible_index"] = add_idx
        if add_idx is not None:
            add_btn.nth(add_idx).click(timeout=10000)
            page.wait_for_timeout(3000)
            interaction["after_url"] = page.url
            interaction["after_title"] = page.title()
            interaction["body_sample"] = page.locator("body").inner_text()[:800]
            shot = OUTDIR / "student_add.png"
            interaction["screenshot"] = safe_screenshot(page, shot, full_page=True)
        (OUTDIR / "student_add.json").write_text(json.dumps(interaction, ensure_ascii=False, indent=2), encoding="utf-8")

        page.goto(
            f"{BASE}/school-home-page/class-management1/students-management1",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(3000)
        more_menu = collect_more_menu_state(page)
        more_shot = OUTDIR / "student_more_menu.png"
        more_menu["screenshot"] = safe_screenshot(page, more_shot, full_page=False)
        (OUTDIR / "student_more_menu.json").write_text(json.dumps(more_menu, ensure_ascii=False, indent=2), encoding="utf-8")

        page.goto(
            f"{BASE}/school-home-page/class-management1/students-management1",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(3000)
        bulk_actions = collect_student_bulk_actions(page)
        (OUTDIR / "student_bulk_actions.json").write_text(
            json.dumps(bulk_actions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        page.goto(
            f"{BASE}/school-home-page/class-management1/teachplan1",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(4000)
        teachplan_toggle = {"found": False}
        list_view = page.locator(".el-switch__label--right")
        if list_view.count() > 0 and list_view.first.is_visible():
            teachplan_toggle["found"] = True
            list_view.first.click(timeout=10000)
            page.wait_for_timeout(4000)
            teachplan_toggle["after_url"] = page.url
            teachplan_toggle["after_title"] = page.title()
            teachplan_toggle["table_rows"] = safe_count(page.locator("tbody tr"))
            teachplan_toggle["body_sample"] = page.locator("body").inner_text()[:1000]
            shot = OUTDIR / "teachplan_list_view.png"
            teachplan_toggle["screenshot"] = safe_screenshot(page, shot, full_page=True)
        (OUTDIR / "teachplan_list_view.json").write_text(
            json.dumps(teachplan_toggle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        browser.close()

    (OUTDIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTDIR / "resource_probes.json").write_text(
        json.dumps(resource_probe(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTDIR / "meta.json").write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "base": BASE,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
