from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests

from .config import (
    AccountConfig,
    BASE_URL,
    STUDENT_FRESH_DATA_PATH,
    TEACHER_FRESH_DATA_PATH,
)
from .rewrite import rewrite_external_urls


def md5_base64(value: str) -> str:
    digest = hashlib.md5(value.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def teacher_login_payload(
    username: str,
    password: str,
    captcha_verify_param: str = "",
) -> dict[str, str]:
    return {
        "userName": username,
        "password": md5_base64(password),
        "captchaVerifyParam": captcha_verify_param,
    }


def student_login_payload(
    username: str,
    password: str,
    captcha_verify_param: str = "",
) -> dict[str, str]:
    return {
        "userName": username,
        "password": md5_base64(password),
        "captchaVerifyParam": captcha_verify_param,
    }


def flatten_permission_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for node in nodes:
        user_resource = node.get("userResource")
        if user_resource:
            flattened.append(user_resource)
        children = node.get("children") or []
        flattened.extend(flatten_permission_tree(children))
    return flattened


def localize_external_values(value: Any) -> Any:
    if isinstance(value, str):
        return rewrite_external_urls(value)
    if isinstance(value, list):
        return [localize_external_values(item) for item in value]
    if isinstance(value, dict):
        return {key: localize_external_values(item) for key, item in value.items()}
    return value


def build_vuex_state(
    profile_name: str,
    token: str,
    fresh_auth_data: dict[str, Any],
    permission_tree: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    identity = fresh_auth_data.get("identity", 0)
    user_info = fresh_auth_data.get("userInfo") or {}
    school_info = fresh_auth_data.get("schoolInfo") or {}
    role_list = fresh_auth_data.get("roleList") or []

    if identity == 2 or profile_name == "student":
        username = ((user_info.get("stuUserInfo") or {}).get("realName")) or ""
        is_principal = False
        permissions = []
        roles: list[Any] | str = ""
    else:
        username = user_info.get("realName") or ""
        is_principal = bool(user_info.get("principal"))
        permissions = permission_tree or []
        roles = role_list

    return {
        "user": {
            "username": username,
            "token": token,
            "adminUserName": "",
            "adminUserId": None,
            "adminToken": "",
            "isSuperAdmin": False,
            "is_principal": is_principal,
            "roleList": roles,
            "selected_schools": [],
            "permisionList": permissions,
            "adminpermisionList": [],
            "userInfo": user_info,
            "schoolInfo": school_info,
            "identity": identity,
            "eduTchList": [],
        }
    }


@dataclass
class CapturedProfile:
    profile_name: str
    username: str
    password_hash: str
    login_path: str
    token: str
    login_content: Any
    fresh_data: dict[str, Any]
    fresh_data_path: str
    vuex_state: dict[str, Any]
    login_response_headers: dict[str, Any]
    fresh_data_headers: dict[str, Any]


class LiveAuthClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def capture_profile(self, account: AccountConfig) -> CapturedProfile:
        login_url = urljoin(self.base_url, account.login_path)
        if account.profile_name == "student":
            login_payload = student_login_payload(account.username, account.password)
        else:
            login_payload = teacher_login_payload(account.username, account.password)

        login_response = self.session.post(
            login_url,
            json=login_payload,
            headers={
                "Header-Account": account.username,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=self.timeout,
        )
        login_data = login_response.json()
        login_content = self._unwrap_success(login_data, login_url)
        login_content = localize_external_values(login_content)

        if account.profile_name == "student":
            token = str(login_content)
            permission_tree: list[dict[str, Any]] = []
        else:
            token = str(login_content.get("token") or "")
            auth_tree = json.loads(login_content.get("authTree") or "{}")
            permission_tree = flatten_permission_tree(auth_tree.get("children") or [])

        fresh_data_path = STUDENT_FRESH_DATA_PATH if account.profile_name == "student" else TEACHER_FRESH_DATA_PATH
        fresh_data_url = urljoin(self.base_url, fresh_data_path)
        fresh_data_response = self.session.post(
            fresh_data_url,
            json={},
            headers={
                "Authorization": token,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=self.timeout,
        )
        raw_fresh_data = self._unwrap_success(fresh_data_response.json(), fresh_data_url)
        normalized_fresh_data = self._normalize_fresh_data(account.profile_name, raw_fresh_data)
        normalized_fresh_data = localize_external_values(normalized_fresh_data)
        vuex_state = build_vuex_state(
            profile_name=account.profile_name,
            token=token,
            fresh_auth_data=normalized_fresh_data,
            permission_tree=permission_tree,
        )

        return CapturedProfile(
            profile_name=account.profile_name,
            username=account.username,
            password_hash=md5_base64(account.password),
            login_path=account.login_path,
            token=token,
            login_content=login_content,
            fresh_data=normalized_fresh_data,
            fresh_data_path=fresh_data_path,
            vuex_state=vuex_state,
            login_response_headers=dict(login_response.headers),
            fresh_data_headers=dict(fresh_data_response.headers),
        )

    @staticmethod
    def _unwrap_success(payload: dict[str, Any], url: str) -> Any:
        if payload.get("success"):
            return payload.get("content")
        error = payload.get("error") or {}
        message = error.get("message") or f"Live auth request failed: {url}"
        raise RuntimeError(message)

    @staticmethod
    def _normalize_fresh_data(profile_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if profile_name == "student":
            return {
                "identity": 2,
                "userInfo": {"stuUserInfo": payload.get("stuUserInfo") or {}},
                "schoolInfo": payload.get("schoolInfo") or {},
                "roleList": [],
            }
        return {
            "identity": 1,
            "userInfo": payload.get("userInfo") or {},
            "schoolInfo": payload.get("schoolInfo") or {},
            "roleList": payload.get("roleList") or [],
        }
