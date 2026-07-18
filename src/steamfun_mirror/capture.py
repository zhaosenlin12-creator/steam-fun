from __future__ import annotations

import json
import mimetypes
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests

from .auth import CapturedProfile, LiveAuthClient
from .config import AccountConfig, BASE_URL, XHR_CAPTURE_RE
from .discovery import (
    extract_absolute_urls,
    extract_api_paths,
    extract_referenced_urls,
    extract_routes,
    extract_shell_assets,
    find_app_bundle_url,
)
from .rewrite import is_same_origin_host
from .storage import MirrorStore


TEXTUAL_CONTENT_MARKERS = ("json", "javascript", "css", "html", "svg", "xml", "text")
STATIC_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}
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


def _is_textual_content_type(content_type: str) -> bool:
    return any(marker in content_type.lower() for marker in TEXTUAL_CONTENT_MARKERS)


def _is_static_url(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        return False
    if parsed.path.startswith("/api/") or parsed.path.startswith("/java-api/"):
        return False
    suffix = Path(parsed.path).suffix.lower()
    if suffix in STATIC_SUFFIXES:
        return True
    guessed, _ = mimetypes.guess_type(parsed.path)
    return bool(guessed)


def _filter_routes(profile_name: str, routes: Iterable[str]) -> list[str]:
    filtered: list[str] = []
    for route in routes:
        if route == "/404" or ":" in route:
            continue
        if profile_name == "student" and route.startswith("/background"):
            continue
        filtered.append(route)
    prioritized = ["/", "/school-home-page", "/code-classroom", "/community/home"]
    unique = []
    seen = set()
    for route in prioritized + sorted(set(filtered)):
        if route in seen or route not in filtered and route not in prioritized:
            continue
        seen.add(route)
        unique.append(route)
    return unique


def _bootstrap_action(base_url: str, vuex_state: dict[str, Any], target_url: str):
    serialized = json.dumps(vuex_state, ensure_ascii=False)

    def action(page):
        page.evaluate(
            """([vuexValue]) => {
                localStorage.setItem("vuex", vuexValue);
                window.isUpdatingFromStorage = false;
            }""",
            [serialized],
        )
        page.goto(target_url, wait_until="networkidle")
        page.wait_for_timeout(1500)

    return action


class MirrorCapture:
    def __init__(self, root: Path, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.store = MirrorStore(root)
        self.http = requests.Session()

    def _fetch_static_asset(self, url: str) -> requests.Response | None:
        parsed = urlparse(url)
        candidate_urls = [url]
        if not is_same_origin_host(parsed.netloc) and parsed.scheme == "https":
            candidate_urls.append(parsed._replace(scheme="http").geturl())

        headers = {
            **STATIC_FETCH_HEADERS,
            "Referer": f"{self.base_url}/",
            "Origin": self.base_url,
        }

        for candidate_url in candidate_urls:
            try:
                response = self.http.get(candidate_url, headers=headers, timeout=60, stream=True)
            except requests.RequestException:
                continue
            if response.status_code < 400:
                return response
            response.close()
        return None

    def _cache_streamed_asset(
        self,
        url: str,
        response: requests.Response,
    ) -> tuple[dict[str, Any], str, bytes | None]:
        headers = dict(response.headers)
        content_type = headers.get("content-type", "")
        is_textual = _is_textual_content_type(content_type)
        collected = bytearray() if is_textual else None

        def chunk_iter():
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                if collected is not None:
                    collected.extend(chunk)
                yield chunk

        host = urlparse(url).netloc
        if is_same_origin_host(host):
            self.store.store_origin_asset_stream(url, chunk_iter(), status=response.status_code, headers=headers)
        else:
            self.store.store_external_asset_stream(url, chunk_iter(), status=response.status_code, headers=headers)
        return headers, content_type, bytes(collected) if collected is not None else None

    def capture(
        self,
        *,
        teacher_username: str,
        teacher_password: str,
        student_username: str,
        student_password: str,
        route_limit: int | None = None,
        headless: bool = True,
    ) -> dict[str, Any]:
        print("[capture] discovery start", flush=True)
        discovery = self.capture_discovery()
        print(
            f"[capture] discovery done routes={len(discovery['routes'])} "
            f"api={len(discovery['api_paths'])} shell_assets={len(discovery['shell_assets'])}",
            flush=True,
        )
        auth_client = LiveAuthClient(self.base_url)
        print("[capture] auth teacher start", flush=True)
        teacher = auth_client.capture_profile(
            AccountConfig(
                profile_name="teacher",
                username=teacher_username,
                password=teacher_password,
                login_path="/java-api/school/tch/login",
                initial_route="/school-home-page",
            )
        )
        print("[capture] auth teacher done", flush=True)
        print("[capture] auth student start", flush=True)
        student = auth_client.capture_profile(
            AccountConfig(
                profile_name="student",
                username=student_username,
                password=student_password,
                login_path="/java-api/student/stu/login",
                initial_route="/code-classroom",
            )
        )
        print("[capture] auth student done", flush=True)
        self._store_profile(teacher)
        self._store_profile(student)
        self._store_fresh_data_api(teacher)
        self._store_fresh_data_api(student)
        print("[capture] teacher course material enrichment start", flush=True)
        self.enrich_teacher_course_materials(teacher)
        print("[capture] teacher course material enrichment done", flush=True)
        print("[capture] teacher route capture start", flush=True)
        self.capture_routes_for_profile(teacher, discovery["routes"], route_limit=route_limit, headless=headless)
        print("[capture] teacher route capture done", flush=True)
        print("[capture] student route capture start", flush=True)
        self.capture_routes_for_profile(student, discovery["routes"], route_limit=route_limit, headless=headless)
        print("[capture] student route capture done", flush=True)
        summary = {
            "base_url": self.base_url,
            "route_count": len(discovery["routes"]),
            "api_count": len(discovery["api_paths"]),
            "shell_asset_count": len(discovery["shell_assets"]),
            "profiles": [
                {"profile_name": teacher.profile_name, "username": teacher.username},
                {"profile_name": student.profile_name, "username": student.username},
            ],
        }
        self.store.store_discovery("summary", summary)
        return summary

    def capture_discovery(self) -> dict[str, Any]:
        home_response = self.http.get(self.base_url, timeout=30)
        home_response.raise_for_status()
        shell_html = home_response.text
        self.store.store_origin_asset(
            f"{self.base_url}/",
            shell_html.encode("utf-8"),
            status=home_response.status_code,
            headers=dict(home_response.headers),
        )

        shell_assets = extract_shell_assets(shell_html)
        app_bundle_path = find_app_bundle_url(shell_assets)
        if not app_bundle_path:
            raise RuntimeError("Unable to locate app bundle from the shell HTML.")

        app_bundle_url = urljoin(self.base_url, app_bundle_path)
        app_response = self.http.get(app_bundle_url, timeout=60)
        app_response.raise_for_status()
        app_js = app_response.text
        self.store.store_origin_asset(
            app_bundle_url,
            app_response.content,
            status=app_response.status_code,
            headers=dict(app_response.headers),
        )

        routes = extract_routes(app_js)
        api_paths = extract_api_paths(app_js)
        discovery = {
            "shell_assets": shell_assets,
            "app_bundle_url": app_bundle_url,
            "routes": routes,
            "api_paths": api_paths,
        }
        self.store.store_discovery("shell_assets", shell_assets)
        self.store.store_discovery("routes", routes)
        self.store.store_discovery("api_paths", api_paths)
        self._mirror_assets(seed_urls=[urljoin(self.base_url, asset) for asset in shell_assets if asset.startswith("/")])
        self._mirror_assets(seed_urls=[url for url in shell_assets if url.startswith("http")])
        return discovery

    def _store_profile(self, profile: CapturedProfile) -> None:
        self.store.store_profile(
            profile_name=profile.profile_name,
            username=profile.username,
            password_hash=profile.password_hash,
            login_path=profile.login_path,
            token=profile.token,
            login_content=profile.login_content,
            fresh_auth=profile.fresh_data,
            vuex_state=profile.vuex_state,
        )
        self.store.store_discovery(f"profile_{profile.profile_name}", asdict(profile))

    def _store_fresh_data_api(self, profile: CapturedProfile) -> None:
        body = json.dumps(
            {"success": True, "content": profile.fresh_data},
            ensure_ascii=False,
        ).encode("utf-8")
        self.store.store_api_response(
            profile.profile_name,
            method="POST",
            url=urljoin(self.base_url, profile.fresh_data_path),
            status=200,
            headers={"content-type": "application/json; charset=utf-8"},
            body=body,
            request_body=b"",
        )

    def _mirror_assets(self, *, seed_urls: list[str]) -> None:
        queue: deque[str] = deque(seed_urls)
        seen: set[str] = set()

        while queue:
            url = queue.popleft()
            if url in seen or not _is_static_url(url):
                continue
            seen.add(url)

            cached_asset = self.store.lookup_asset(url)
            if cached_asset is not None and cached_asset["body"]:
                body = cached_asset["body"]
                content_type = cached_asset["content_type"]
                if not _is_textual_content_type(content_type):
                    continue
                text = body.decode("utf-8", errors="ignore")
            else:
                response = self._fetch_static_asset(url)
                if response is None:
                    continue
                with response:
                    headers, content_type, collected_body = self._cache_streamed_asset(url, response)
                if not _is_textual_content_type(content_type):
                    continue
                if collected_body is None:
                    continue
                text = collected_body.decode("utf-8", errors="ignore")

            for ref in extract_referenced_urls(url, text):
                if _is_static_url(ref):
                    queue.append(ref)

    def _authorized_get_json(
        self,
        profile: CapturedProfile,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = urljoin(self.base_url, path)
        response = self.http.get(
            url,
            params=params,
            headers={
                "Authorization": profile.token,
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": STATIC_FETCH_HEADERS["User-Agent"],
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        self.store.store_api_response(
            profile.profile_name,
            method="GET",
            url=response.url,
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
            request_body=b"",
        )
        if not payload.get("success"):
            raise RuntimeError(
                (payload.get("error") or {}).get("message")
                or f"Teacher enrichment request failed: {response.url}"
            )
        return payload

    def _seed_currmat_detail_response(
        self,
        profile_name: str,
        material: dict[str, Any],
        *,
        tch_plan_id: int | str | None = None,
    ) -> None:
        material_id = material.get("id")
        if material_id in (None, ""):
            return

        content = {
            "curriculumMaterial": self._build_curriculum_material_detail(material),
            "tchPlanInfo": {"id": tch_plan_id} if tch_plan_id not in (None, "") else {},
        }
        body = json.dumps(
            {"success": True, "content": content, "error": {"message": "", "code": ""}},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"content-type": "application/json; charset=utf-8"}
        url = urljoin(self.base_url, "/java-api/school/currMat/detail")
        request_variants = [{"currMatId": material_id}]
        if tch_plan_id not in (None, ""):
            request_variants.append({"currMatId": material_id, "tchPlanId": tch_plan_id})

        for request_payload in request_variants:
            request_body = json.dumps(
                request_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            self.store.store_api_response(
                profile_name,
                method="POST",
                url=url,
                status=200,
                headers=headers,
                body=body,
                request_body=request_body,
            )

    @staticmethod
    def _build_curriculum_material_detail(material: dict[str, Any]) -> dict[str, Any]:
        def to_json_file_list(url_value: Any) -> Any:
            if not url_value:
                return url_value
            if isinstance(url_value, str) and url_value.strip().startswith("["):
                return url_value
            filename = ""
            if isinstance(url_value, str):
                parsed = urlparse(url_value)
                filename = Path(parsed.path).name
            return json.dumps(
                [{"url": url_value, "name": filename, "length": "0KB"}],
                ensure_ascii=False,
            )

        detail = {
            "id": material.get("id"),
            "subjectId": material.get("subject_id"),
            "curriculumId": material.get("curriculum_id"),
            "eduId": material.get("educational_institution_id"),
            "title": material.get("title") or "",
            "sortNum": material.get("sort_num"),
            "remarks": material.get("remarks"),
            "createdTime": material.get("created_time"),
            "imgUrl": material.get("img_url") or "",
            "desc": material.get("desc") or "",
            "pptUrl": material.get("ppt_url") or "",
            "stuNoteUrl": material.get("stu_note_url") or "",
            "knowledgePointUrl": material.get("knowledge_point_url") or "",
            "videoUrl": material.get("video_url") or "",
            "lessionPlanUrl": material.get("lession_plan_url") or "",
            "trainVideoUrl": material.get("train_video_url") or "",
            "exampleVideoUrl": material.get("exampal_video_url") or "",
            "assemblePitcureState": material.get("assemble_pitcure_state"),
            "assemblePitcure": material.get("assemble_pitcure"),
            "assemblePitcurePdf": material.get("assemble_pitcure_pdf"),
            "totalStorage": material.get("total_storage"),
            "exampleWorkUrl": material.get("exampal_work_url") or "",
            "teachTemplateUrl": material.get("teach_template_url") or "",
            "homeTemplateUrl": material.get("home_template_url") or "",
            "otherMaterialUrl": material.get("other_meterial_url") or "",
            "isPost": material.get("is_post"),
        }
        if material.get("educational_institution_id"):
            for field_name in ("pptUrl", "stuNoteUrl", "lessionPlanUrl"):
                detail[field_name] = to_json_file_list(detail[field_name])
        return detail

    @staticmethod
    def _extract_curriculum_asset_urls(curriculum: dict[str, Any]) -> list[str]:
        asset_urls: list[str] = []
        for key in ("img_url",):
            value = curriculum.get(key)
            if isinstance(value, str) and value.startswith("http"):
                asset_urls.append(value)
        for key in ("markdown_explain", "html_explain", "curriculum_data_url"):
            value = curriculum.get(key)
            if isinstance(value, str) and value:
                asset_urls.extend(extract_absolute_urls(value))
        return sorted({url for url in asset_urls if url})

    @staticmethod
    def _extract_material_asset_urls(material: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        for key in (
            "img_url",
            "ppt_url",
            "stu_note_url",
            "knowledge_point_url",
            "video_url",
            "lession_plan_url",
            "train_video_url",
            "exampal_video_url",
            "assemble_pitcure",
            "assemble_pitcure_pdf",
            "exampal_work_url",
            "teach_template_url",
            "home_template_url",
            "other_meterial_url",
        ):
            value = material.get(key)
            if isinstance(value, str) and value.startswith("http"):
                urls.append(value)
            elif isinstance(value, str) and value.strip().startswith("["):
                try:
                    parsed = json.loads(value)
                except Exception:
                    continue
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            url = item.get("url")
                            if isinstance(url, str) and url.startswith("http"):
                                urls.append(url)
        return sorted({url for url in urls if url})

    def enrich_teacher_course_materials(self, profile: CapturedProfile) -> None:
        campus_payload = self._authorized_get_json(profile, "/api/get/user/campus/list")
        campus_rows = ((campus_payload.get("content") or {}).get("userDeptList") or [])
        campus_ids = sorted(
            {
                int(row.get("dept_id"))
                for row in campus_rows
                if row.get("dept_id") not in (None, "")
            }
        )
        if not campus_ids:
            school_info = profile.fresh_data.get("schoolInfo") or {}
            fallback_campus_id = school_info.get("eduCampusId")
            if fallback_campus_id not in (None, ""):
                campus_ids = [int(fallback_campus_id)]
        if not campus_ids:
            return

        campus_id_arr = json.dumps(campus_ids, ensure_ascii=False, separators=(",", ":"))
        self._authorized_get_json(profile, "/api/get/educational_institution_campus/list")
        self._authorized_get_json(
            profile,
            "/api/get/campus/arr/subject/list",
            params={"campusIdArr": campus_id_arr},
        )

        for campus_id in campus_ids:
            subject_payload = self._authorized_get_json(
                profile,
                "/api/get/campus/subject/list",
                params={"campusId": str(campus_id)},
            )
            subject_rows = ((subject_payload.get("content") or {}).get("campusSubjectList") or [])
            subject_ids = [row.get("id") for row in subject_rows if row.get("id") not in (None, "")]
            if not subject_ids:
                subject_ids = [""]

            for subject_id in subject_ids:
                page_no = 1
                while True:
                    curriculum_payload = self._authorized_get_json(
                        profile,
                        "/api/get/campus/curriculum/list/by/page",
                        params={
                            "campusIds": campus_id_arr,
                            "subjectId": "" if subject_id == "" else str(subject_id),
                            "teaching_type": "",
                            "curriculum_type": "",
                            "page_no": str(page_no),
                            "page_size": "100",
                        },
                    )
                    curriculum_rows = ((curriculum_payload.get("content") or {}).get("campusAuthList") or [])
                    if not curriculum_rows:
                        break

                    for curriculum_row in curriculum_rows:
                        curriculum_info = curriculum_row.get("curriculumInfo") or {}
                        asset_urls = self._extract_curriculum_asset_urls(curriculum_info)
                        if asset_urls:
                            self._mirror_assets(seed_urls=asset_urls)

                        curriculum_id = curriculum_info.get("id") or curriculum_row.get("curriculum_id")
                        if curriculum_id in (None, ""):
                            continue
                        material_payload = self._authorized_get_json(
                            profile,
                            "/api/prepare/get/currculumMaterialList",
                            params={
                                "curriculum_id": str(curriculum_id),
                                "page_no": "1",
                                "page_size": "200",
                            },
                        )
                        material_rows = (
                            (material_payload.get("content") or {}).get("curriculumMaterialList")
                            or (material_payload.get("content") or {}).get("currculumMaterialList")
                            or []
                        )
                        for material in material_rows:
                            material_asset_urls = self._extract_material_asset_urls(material)
                            if material_asset_urls:
                                self._mirror_assets(seed_urls=material_asset_urls)
                            self._seed_currmat_detail_response(profile.profile_name, material)

                    if len(curriculum_rows) < 100:
                        break
                    page_no += 1

    def capture_routes_for_profile(
        self,
        profile: CapturedProfile,
        routes: list[str],
        *,
        route_limit: int | None = None,
        headless: bool = True,
    ) -> None:
        filtered_routes = _filter_routes(profile.profile_name, routes)
        if route_limit is not None:
            filtered_routes = filtered_routes[:route_limit]

        browser_profile_dir = self.store.fresh_browser_profile_dir(profile.profile_name)

        from scrapling.fetchers import DynamicSession

        with DynamicSession(
            headless=headless,
            network_idle=True,
            disable_resources=False,
            capture_xhr=XHR_CAPTURE_RE,
            user_data_dir=str(browser_profile_dir),
            timeout=60000,
        ) as session:
            print(
                f"[capture] {profile.profile_name} bootstrap start routes={len(filtered_routes)}",
                flush=True,
            )
            bootstrap_response = session.fetch(
                f"{self.base_url}/login",
                page_action=_bootstrap_action(
                    self.base_url,
                    profile.vuex_state,
                    urljoin(self.base_url, profile.profile_name == "teacher" and "/school-home-page" or "/code-classroom"),
                ),
                wait_selector="#app",
                wait_selector_state="attached",
                network_idle=True,
            )
            self._record_route_response(profile.profile_name, "/", bootstrap_response)
            print(
                f"[capture] {profile.profile_name} bootstrap done final_url={bootstrap_response.url}",
                flush=True,
            )

            for index, route in enumerate(filtered_routes, start=1):
                route_url = urljoin(self.base_url, route)
                try:
                    response = session.fetch(
                        route_url,
                        network_idle=True,
                        wait=1200,
                        wait_selector="#app",
                        wait_selector_state="attached",
                    )
                except Exception:
                    print(
                        f"[capture] {profile.profile_name} {index}/{len(filtered_routes)} failed {route}",
                        flush=True,
                    )
                    continue
                self._record_route_response(profile.profile_name, route, response)
                print(
                    f"[capture] {profile.profile_name} {index}/{len(filtered_routes)} "
                    f"status={response.status} route={route} final_url={response.url}",
                    flush=True,
                )

    def _record_route_response(self, profile_name: str, route: str, response: Any) -> None:
        html = response.body.decode(response.encoding or "utf-8", errors="ignore")
        self.store.store_route_capture(
            profile_name=profile_name,
            route=route,
            final_url=response.url,
            status=response.status,
            html=html,
            captured_xhr_count=len(response.captured_xhr),
        )
        route_asset_refs = extract_referenced_urls(response.url, html)
        if route_asset_refs:
            self._mirror_assets(seed_urls=route_asset_refs)

        for xhr in response.captured_xhr:
            headers = dict(xhr.headers)
            body = xhr.body
            self.store.store_api_response(
                profile_name,
                method=getattr(xhr, "method", "GET"),
                url=xhr.url,
                status=xhr.status,
                headers=headers,
                body=body,
                request_body=getattr(xhr, "request_body", None),
            )

            content_type = headers.get("content-type", "")
            if not _is_textual_content_type(content_type):
                continue

            try:
                text = body.decode(xhr.encoding or "utf-8", errors="ignore")
            except Exception:
                continue

            asset_urls = extract_absolute_urls(text)
            if asset_urls:
                self._mirror_assets(seed_urls=asset_urls)
