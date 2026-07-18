from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse


LOGIN_PAGE_PATHS = frozenset({"/login", "/background/login"})


@dataclass(frozen=True)
class LoginFlow:
    path: str
    role_tab_selector: str | None
    fallback_path: str


_LOGIN_FLOWS: dict[str, LoginFlow] = {
    "admin": LoginFlow(
        path="/background/login",
        role_tab_selector=None,
        fallback_path="/background/course-management/school-curriculum",
    ),
    "teacher": LoginFlow(
        path="/login",
        role_tab_selector="#tab-manager",
        fallback_path="/school-home-page/class-management1/students-management1",
    ),
    "student": LoginFlow(
        path="/login",
        role_tab_selector="#tab-student",
        fallback_path="/code-classroom/myClass",
    ),
}


def get_login_flow(role: str) -> LoginFlow:
    try:
        return _LOGIN_FLOWS[role]
    except KeyError as exc:
        raise ValueError(f"Unsupported login role: {role}") from exc


def has_login_token(local_storage: dict[str, str]) -> bool:
    raw_vuex = str(local_storage.get("vuex") or "").strip()
    if not raw_vuex:
        return False
    try:
        parsed = json.loads(raw_vuex)
    except json.JSONDecodeError:
        return False
    token = str(((parsed.get("user") or {}).get("token") or "")).strip()
    return bool(token)


def is_login_page(url: str) -> bool:
    return (urlparse(url).path or "").strip() in LOGIN_PAGE_PATHS


def should_force_post_login_navigation(url: str, local_storage: dict[str, str]) -> bool:
    return is_login_page(url) and has_login_token(local_storage)
