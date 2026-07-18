from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from steamfun_mirror.auth import LiveAuthClient  # noqa: E402
from steamfun_mirror.config import AccountConfig, BASE_URL  # noqa: E402
from steamfun_mirror.discovery import extract_absolute_urls, extract_referenced_urls  # noqa: E402
from steamfun_mirror.rewrite import is_same_origin_host  # noqa: E402
from steamfun_mirror.storage import MirrorStore  # noqa: E402


STATIC_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}
TEXTUAL_CONTENT_MARKERS = ("json", "javascript", "css", "html", "svg", "xml", "text")
STATIC_SUFFIXES = {
    ".js",
    ".css",
    ".ico",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rar",
    ".7z",
    ".txt",
    ".html",
    ".sb3",
    ".sjr",
    ".py",
    ".cpp",
    ".c",
    ".java",
}
LOG_404_RE = re.compile(r'"GET (?P<path>\S+) HTTP/[^"]+" 404 Not Found')


def _is_textual_content_type(content_type: str) -> bool:
    return any(marker in content_type.lower() for marker in TEXTUAL_CONTENT_MARKERS)


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _is_static_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if not parsed.scheme.startswith("http"):
        return False
    if parsed.path.startswith("/api/") or parsed.path.startswith("/java-api/"):
        return False
    suffix = Path(parsed.path).suffix.lower()
    return suffix in STATIC_SUFFIXES or not suffix


def _canonical_get_url(base_url: str, path: str, params: dict[str, Any]) -> str:
    query = [(key, str(value)) for key, value in params.items() if value is not None]
    return urljoin(base_url, path) + ("?" + urlencode(query) if query else "")


def _store_api_response(
    store: MirrorStore,
    profile_name: str,
    method: str,
    url: str,
    response: requests.Response,
    *,
    request_body: bytes | None = None,
) -> None:
    store.store_api_response(
        profile_name,
        method=method,
        url=url,
        status=response.status_code,
        headers=dict(response.headers),
        body=response.content,
        request_body=request_body,
    )


def _authorized_get_json(
    store: MirrorStore,
    session: requests.Session,
    token: str,
    profile_name: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    response = session.get(
        urljoin(base_url, path),
        params=params,
        headers={
            "Authorization": token,
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": STATIC_FETCH_HEADERS["User-Agent"],
        },
        timeout=60,
    )
    response.raise_for_status()
    _store_api_response(store, profile_name, "GET", response.url, response)
    payload = response.json()
    if not payload.get("success"):
        error = payload.get("error") or {}
        raise RuntimeError(error.get("message") or f"Remote API request failed: {response.url}")
    return payload


def _candidate_live_urls(live_url: str) -> list[str]:
    parsed = urlparse(live_url)
    candidates = [live_url]
    if not is_same_origin_host(parsed.netloc) and parsed.scheme == "https":
        candidates.append(parsed._replace(scheme="http").geturl())
    return candidates


def _guess_referers(live_url: str) -> list[str]:
    parsed = urlparse(live_url)
    referers: list[str] = [f"{BASE_URL}/"]
    if (
        "wugecdn.steam.fun" in parsed.netloc
        and "/courses/" in parsed.path
        and "/index/" in parsed.path
        and "/data/" in parsed.path
    ):
        lesson_root = parsed.path.split("/data/", 1)[0]
        referers.insert(0, f"{parsed.scheme}://{parsed.netloc}{lesson_root}/index.html")
    elif parsed.path.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".json", ".html")):
        parent = parsed.path.rsplit("/", 1)[0]
        if parent:
            referers.insert(0, f"{parsed.scheme}://{parsed.netloc}{parent}/index.html")
    deduped: list[str] = []
    seen: set[str] = set()
    for referer in referers:
        if referer in seen:
            continue
        seen.add(referer)
        deduped.append(referer)
    return deduped


def _fetch_and_store_asset(
    store: MirrorStore,
    session: requests.Session,
    live_url: str,
    *,
    referer: str | None = None,
) -> tuple[bool, list[str]]:
    parsed = urlparse(live_url)
    existing = store.lookup_asset(live_url)
    if existing is not None and existing["body"]:
        return False, []

    referers = [referer] if referer else []
    referers.extend(_guess_referers(live_url))
    textual_body: str | None = None
    stored = False
    final_url = live_url

    for candidate_url in _candidate_live_urls(live_url):
        for candidate_referer in referers:
            headers = {
                **STATIC_FETCH_HEADERS,
                "Referer": candidate_referer,
                "Origin": BASE_URL,
            }
            try:
                response = session.get(candidate_url, headers=headers, timeout=60)
            except requests.RequestException:
                continue
            if response.status_code >= 400:
                continue

            final_url = response.url or candidate_url
            try:
                if is_same_origin_host(parsed.netloc):
                    store.store_origin_asset(
                        final_url,
                        response.content,
                        status=response.status_code,
                        headers=dict(response.headers),
                    )
                else:
                    store.store_external_asset(
                        final_url,
                        response.content,
                        status=response.status_code,
                        headers=dict(response.headers),
                    )
            except (OSError, ValueError):
                continue
            stored = True

            content_type = response.headers.get("content-type", "")
            if _is_textual_content_type(content_type):
                try:
                    textual_body = response.text
                except Exception:
                    textual_body = None
            break
        if stored:
            break

    discovered_refs: list[str] = []
    if textual_body:
        discovered_refs = [url for url in extract_referenced_urls(final_url, textual_body) if _is_static_url(url)]
    return stored, discovered_refs


def _mirror_referenced_assets(
    store: MirrorStore,
    session: requests.Session,
    seed_url: str,
    seed_text: str,
    *,
    referer: str,
) -> dict[str, int]:
    queue: deque[tuple[str, str]] = deque((url, referer) for url in extract_referenced_urls(seed_url, seed_text))
    seen: set[str] = set()
    fetched = 0

    while queue:
        url, current_referer = queue.popleft()
        if url in seen or not _is_static_url(url):
            continue
        seen.add(url)
        stored, refs = _fetch_and_store_asset(store, session, url, referer=current_referer)
        if stored:
            fetched += 1
        for ref in refs:
            if ref not in seen:
                queue.append((ref, url))

    return {"visited": len(seen), "fetched": fetched}


def _request_path_to_live_url(request_path: str) -> str:
    parsed = urlparse(request_path)
    if parsed.path.startswith("/_external/"):
        _, _, host, asset_path = parsed.path.split("/", 3)
        live_url = f"https://{host}/{asset_path}"
    else:
        live_url = urljoin(BASE_URL, parsed.path)
    if parsed.query:
        live_url = f"{live_url}?{parsed.query}"
    return live_url


def repair_assets_from_log(
    store: MirrorStore,
    session: requests.Session,
    log_path: Path,
) -> dict[str, Any]:
    missing_paths: list[str] = []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = LOG_404_RE.search(line)
            if match is None:
                continue
            request_path = match.group("path")
            if request_path.startswith("/api/") or request_path.startswith("/java-api/"):
                continue
            missing_paths.append(request_path)

    fetched = 0
    failed: list[str] = []
    for request_path in sorted(set(missing_paths)):
        live_url = _request_path_to_live_url(request_path)
        stored, _ = _fetch_and_store_asset(store, session, live_url)
        if stored:
            fetched += 1
        else:
            failed.append(request_path)

    return {
        "requested": len(set(missing_paths)),
        "fetched": fetched,
        "failed": failed[:200],
    }


def repair_course_html_dependencies(
    store: MirrorStore,
    session: requests.Session,
    course_root: Path,
) -> dict[str, Any]:
    html_files = sorted(course_root.rglob("index.html"))
    scanned = 0
    fetched = 0
    visited = 0
    failures: list[str] = []

    for html_path in html_files:
        try:
            relative = html_path.relative_to(store.root)
        except ValueError:
            continue
        parts = relative.parts
        if len(parts) < 3:
            continue
        host = parts[1]
        asset_path = "/".join(parts[2:])
        if parts[0] == "external":
            live_url = f"https://{host}/{asset_path}"
        else:
            live_url = urljoin(BASE_URL, "/" + asset_path)
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            failures.append(str(html_path))
            continue
        scanned += 1
        stats = _mirror_referenced_assets(store, session, live_url, html_text, referer=live_url)
        fetched += stats["fetched"]
        visited += stats["visited"]

    return {
        "html_files": scanned,
        "visited_refs": visited,
        "fetched_assets": fetched,
        "failures": failures[:200],
    }


def repair_classroom_endpoints(
    store: MirrorStore,
    session: requests.Session,
    token: str,
    *,
    profile_name: str = "teacher",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    class_ids: list[int] = []
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
        if class_id is not None and class_id not in class_ids:
            class_ids.append(class_id)

    stored_urls: list[str] = []
    failed: list[dict[str, Any]] = []
    student_fetches = 0
    plan_fetches = 0

    headers = {
        "Authorization": token,
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": STATIC_FETCH_HEADERS["User-Agent"],
    }

    def capture_get(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        response = session.get(urljoin(base_url, path), params=params, headers=headers, timeout=60)
        store.store_api_response(
            profile_name,
            method="GET",
            url=response.url,
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )
        stored_urls.append(response.url)
        try:
            payload = response.json()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        for asset_url in extract_absolute_urls(json.dumps(payload, ensure_ascii=False)):
            _fetch_and_store_asset(store, session, asset_url)
        return payload

    for class_id in class_ids:
        student_payload = capture_get(
            "/api/get/class/student/list",
            {"classId": class_id, "realname": "", "page_no": 1, "page_size": 200},
        )
        student_fetches += 1
        if not isinstance(student_payload, dict) or not student_payload.get("success"):
            failed.append({"class_id": class_id, "path": "/api/get/class/student/list"})

        plan_payload = capture_get(
            "/api/get/teaching/plan/by/class/id",
            {"classes_id": class_id, "title": "", "sign_state": ""},
        )
        plan_fetches += 1
        if not isinstance(plan_payload, dict) or not plan_payload.get("success"):
            failed.append({"class_id": class_id, "path": "/api/get/teaching/plan/by/class/id"})

    return {
        "class_count": len(class_ids),
        "student_fetches": student_fetches,
        "plan_fetches": plan_fetches,
        "api_records": len(stored_urls),
        "failed": failed[:200],
    }


def repair_competition_endpoints(
    store: MirrorStore,
    session: requests.Session,
    token: str,
    *,
    profile_name: str = "teacher",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    stored_urls: list[str] = []

    def fetch_and_track(path: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = _authorized_get_json(
            store,
            session,
            token,
            profile_name,
            path,
            params=params,
            base_url=base_url,
        )
        stored_urls.append(_canonical_get_url(base_url, path, params))
        for asset_url in extract_absolute_urls(json.dumps(payload, ensure_ascii=False)):
            _fetch_and_store_asset(store, session, asset_url)
        return payload

    fetch_and_track("/api/exam/getBankSourceListWithoutPageForNew", {"source_type": 1})
    fetch_and_track("/api/exam/getTestQuestionBankSourceListWithoutPage", {})

    source_ids = [
        source_id
        for source_id in (
            _coerce_int(source.get("id"))
            for source in store.list_competition_sources()
        )
        if source_id is not None
    ]
    source_ids = sorted(set(source_ids))

    question_bank_fetches = 0
    for source_id in source_ids:
        fetch_and_track("/api/exam/getBankSourceInfo", {"source_id": source_id})
        fetch_and_track("/api/exam/getTestQuestionBankSourceTagListWithoutPage", {"source_id": source_id})
        for match_bank_type in (1, 2):
            page_no = 1
            while True:
                payload = fetch_and_track(
                    "/api/exam/get/school/question/bank/list",
                    {
                        "source_id": source_id,
                        "subject_id": "",
                        "title": "",
                        "search_question_bank_type": 1,
                        "post_state": "",
                        "isShowSelfPaper": False,
                        "source_tag_id": "",
                        "match_bank_type": match_bank_type,
                        "page_no": page_no,
                        "page_size": 100,
                    },
                )
                question_bank_fetches += 1
                content = payload.get("content") or {}
                rows = content.get("questionBankList") or []
                total = _coerce_int(content.get("total")) or 0
                if not isinstance(rows, list) or not rows:
                    break
                if page_no * 100 >= total or len(rows) < 100:
                    break
                page_no += 1

    return {
        "source_count": len(source_ids),
        "api_records": len(stored_urls),
        "question_bank_fetches": question_bank_fetches,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair missing local mirror assets and endpoint captures.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root path.")
    parser.add_argument("--base-url", default=BASE_URL, help="Upstream base URL.")
    parser.add_argument("--teacher-username", required=True, help="Teacher account username.")
    parser.add_argument("--teacher-password", required=True, help="Teacher account password.")
    parser.add_argument(
        "--log-path",
        type=Path,
        default=ROOT / "runtime" / "server_8000_current.stdout.log",
        help="Server log file used to identify missing asset requests.",
    )
    parser.add_argument(
        "--skip-course-html-scan",
        action="store_true",
        help="Skip recursive dependency fetches rooted from local course HTML files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = MirrorStore(args.root)
    auth_client = LiveAuthClient(args.base_url)
    teacher_profile = auth_client.capture_profile(
        AccountConfig(
            profile_name="teacher",
            username=args.teacher_username,
            password=args.teacher_password,
            login_path="/java-api/school/tch/login",
            initial_route="/school-home-page",
        )
    )
    session = auth_client.session

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = args.root / "runtime" / f"repair_{timestamp}"
    outdir.mkdir(parents=True, exist_ok=True)

    competition_stats = repair_competition_endpoints(
        store,
        session,
        teacher_profile.token,
        profile_name=teacher_profile.profile_name,
        base_url=args.base_url,
    )
    classroom_stats = repair_classroom_endpoints(
        store,
        session,
        teacher_profile.token,
        profile_name=teacher_profile.profile_name,
        base_url=args.base_url,
    )
    log_stats = repair_assets_from_log(store, session, args.log_path)
    if args.skip_course_html_scan:
        course_stats = {"html_files": 0, "visited_refs": 0, "fetched_assets": 0, "failures": []}
    else:
        course_stats = repair_course_html_dependencies(
            store,
            session,
            args.root / "external" / "wugecdn.steam.fun" / "courses",
        )

    summary = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "competition": competition_stats,
        "classroom": classroom_stats,
        "log_assets": log_stats,
        "course_html": course_stats,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
