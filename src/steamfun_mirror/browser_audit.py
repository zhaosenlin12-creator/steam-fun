from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


DEFAULT_GOTO_TIMEOUT_MS = 60000
DEFAULT_NETWORKIDLE_TIMEOUT_MS = 15000
DEFAULT_SETTLE_TIMEOUT_MS = 5000
BENIGN_ABORTED_ROUTE_PATHS = frozenset(
    {
        "/code-classroom/prepare-lessons/prepare/undefined",
        "/code-classroom/teach-lessons/lessons/undefined",
    }
)
BENIGN_ABORTED_DOWNLOAD_SUFFIXES = (
    ".pdf",
    ".mp3",
    ".mp4",
    ".m4a",
    ".wav",
    ".webm",
)


def navigate_for_audit(
    page: Page,
    url: str,
    *,
    goto_timeout_ms: int = DEFAULT_GOTO_TIMEOUT_MS,
    networkidle_timeout_ms: int = DEFAULT_NETWORKIDLE_TIMEOUT_MS,
    settle_timeout_ms: int = DEFAULT_SETTLE_TIMEOUT_MS,
) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=networkidle_timeout_ms)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(settle_timeout_ms)


def classify_request_failure(url: str, failure: str) -> str:
    normalized_failure = str(failure or "").strip().lower()
    if "err_aborted" not in normalized_failure:
        return "actionable"

    parsed = urlparse(str(url or ""))
    normalized_path = (parsed.path or "").strip().lower()
    if normalized_path in BENIGN_ABORTED_ROUTE_PATHS:
        return "benign_aborted"
    if normalized_path.endswith(BENIGN_ABORTED_DOWNLOAD_SUFFIXES):
        return "benign_aborted"
    return "actionable"


def split_request_failures(raw_failures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actionable: list[dict[str, Any]] = []
    benign_aborted: list[dict[str, Any]] = []
    for row in raw_failures:
        if classify_request_failure(str(row.get("url") or ""), str(row.get("failure") or "")) == "benign_aborted":
            benign_aborted.append(row)
        else:
            actionable.append(row)
    return actionable, benign_aborted
