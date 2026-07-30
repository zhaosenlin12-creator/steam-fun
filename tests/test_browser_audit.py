from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from steamfun_mirror import browser_audit
from steamfun_mirror.browser_audit import navigate_for_audit, split_request_failures


class _FakePage:
    def __init__(self, *, fail_networkidle: bool = False) -> None:
        self.fail_networkidle = fail_networkidle
        self.calls: list[tuple[str, object, object]] = []

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.calls.append(("goto", url, wait_until))
        self.calls.append(("goto-timeout", timeout, None))

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.calls.append(("wait_for_load_state", state, timeout))
        if self.fail_networkidle:
            raise PlaywrightTimeoutError("networkidle timeout")

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.calls.append(("wait_for_timeout", timeout_ms, None))


def test_navigate_for_audit_waits_for_domcontentloaded_and_settle_timeout() -> None:
    page = _FakePage()

    navigate_for_audit(page, "http://127.0.0.1:8000/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=398")

    assert page.calls == [
        ("goto", "http://127.0.0.1:8000/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=398", "domcontentloaded"),
        ("goto-timeout", 60000, None),
        ("wait_for_load_state", "networkidle", 15000),
        ("wait_for_timeout", 5000, None),
    ]


def test_navigate_for_audit_ignores_networkidle_timeout_and_still_settles() -> None:
    page = _FakePage(fail_networkidle=True)

    navigate_for_audit(page, "http://127.0.0.1:8000/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=104")

    assert page.calls[-1] == ("wait_for_timeout", 5000, None)


def test_split_request_failures_classifies_download_and_placeholder_abort_as_benign() -> None:
    actionable, benign = split_request_failures(
        [
            {"url": "http://127.0.0.1:8000/code-classroom/teach-lessons/lessons/undefined?usercode=1", "failure": "net::ERR_ABORTED"},
            {"url": "http://127.0.0.1:8000/_external/wugecdn.steam.fun/course/handout.pdf", "failure": "net::ERR_ABORTED"},
            {"url": "http://127.0.0.1:8000/_external/wugecdn.steam.fun/course/script.js", "failure": "net::ERR_CONNECTION_RESET"},
        ]
    )

    assert len(actionable) == 1
    assert actionable[0]["url"].endswith("script.js")
    assert len(benign) == 2


def test_summarize_browser_events_fails_on_every_actionable_channel() -> None:
    summary = browser_audit.summarize_browser_events(
        console_messages=[
            {"type": "log", "text": "ready"},
            {"type": "warning", "text": "deprecated"},
        ],
        page_errors=[{"message": "render failed"}],
        request_failures=[
            {"url": "http://127.0.0.1:8000/course.mp4", "failure": "net::ERR_ABORTED"},
            {"url": "http://127.0.0.1:8000/app.js", "failure": "net::ERR_CONNECTION_RESET"},
        ],
        bad_responses=[{"url": "http://127.0.0.1:8000/api/data", "status": 500}],
    )

    assert summary["passed"] is False
    assert summary["console_errors"] == [{"type": "warning", "text": "deprecated"}]
    assert summary["page_errors"] == [{"message": "render failed"}]
    assert summary["request_failures"] == [
        {"url": "http://127.0.0.1:8000/app.js", "failure": "net::ERR_CONNECTION_RESET"}
    ]
    assert summary["benign_aborted_requests"] == [
        {"url": "http://127.0.0.1:8000/course.mp4", "failure": "net::ERR_ABORTED"}
    ]
    assert summary["bad_responses"] == [{"url": "http://127.0.0.1:8000/api/data", "status": 500}]


def test_summarize_browser_events_passes_with_only_benign_activity() -> None:
    summary = browser_audit.summarize_browser_events(
        console_messages=[{"type": "log", "text": "ready"}],
        page_errors=[],
        request_failures=[
            {"url": "http://127.0.0.1:8000/course.pdf", "failure": "net::ERR_ABORTED"}
        ],
        bad_responses=[],
    )

    assert summary["passed"] is True
    assert summary["benign_aborted_requests"]
