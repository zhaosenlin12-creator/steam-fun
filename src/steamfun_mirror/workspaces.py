from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .capabilities import capabilities_for_role, resolve_profile_role
from .config import TEACHER_LOGIN_PATH
from .storage import MirrorStore


WORKSPACE_ASSET_ROOT = Path(__file__).resolve().parent / "site_assets" / "workspace"


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _profile_user_info(profile: dict[str, Any]) -> dict[str, Any]:
    fresh_auth = profile.get("fresh_auth") if isinstance(profile.get("fresh_auth"), dict) else {}
    user_info = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
    return user_info


def _profile_school_info(profile: dict[str, Any]) -> dict[str, Any]:
    fresh_auth = profile.get("fresh_auth") if isinstance(profile.get("fresh_auth"), dict) else {}
    school_info = fresh_auth.get("schoolInfo") if isinstance(fresh_auth.get("schoolInfo"), dict) else {}
    return school_info


def _profile_user_id(profile: dict[str, Any]) -> int | None:
    user_info = _profile_user_info(profile)
    user_state = (profile.get("vuex_state") or {}).get("user") or {}
    state_info = user_state.get("userInfo") if isinstance(user_state.get("userInfo"), dict) else {}
    for value in (
        user_info.get("id"),
        user_info.get("userId"),
        user_state.get("userId"),
        user_state.get("adminUserId"),
        state_info.get("id"),
        state_info.get("userId"),
    ):
        normalized = _as_int(value)
        if normalized is not None:
            return normalized
    return None


def _display_name(profile: dict[str, Any]) -> str:
    user_info = _profile_user_info(profile)
    return str(
        user_info.get("realName")
        or user_info.get("realname")
        or user_info.get("userRealname")
        or profile.get("username")
        or ""
    ).strip()


def _is_active_class(row: dict[str, Any]) -> bool:
    return not bool(_as_int(row.get("deleted"))) and _as_int(row.get("end_class_state")) not in {1, 2}


def _plan_date(row: dict[str, Any]) -> date | None:
    for key in ("class_date", "classDate", "start_class_date", "startClassDate"):
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
    return None


def _lesson_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_int(row.get("id")) or 0,
        "classId": _as_int(row.get("curriculum_class_id") or row.get("classId")) or 0,
        "className": str(row.get("className") or row.get("class_name") or "").strip(),
        "title": str(row.get("custom_lesson_title") or row.get("title") or "课程教学").strip(),
        "startTime": str(row.get("start_class_date") or row.get("startClassDate") or "").strip(),
        "endTime": str(row.get("end_class_date") or row.get("endClassDate") or "").strip(),
        "materialId": _as_int(row.get("curriculum_meterial_id") or row.get("curriculumMaterialId")) or 0,
    }


def _student_count(store: MirrorStore) -> int:
    student_ids: set[str] = set()
    for row in [*store.list_campus_user_students(), *store.list_local_students()]:
        student_id = str(row.get("id") or row.get("stuId") or row.get("studentId") or "").strip()
        if student_id:
            student_ids.add(student_id)
    return len(student_ids)


def _teacher_count(store: MirrorStore) -> int:
    count = 0
    for profile in store.list_profiles(login_path=TEACHER_LOGIN_PATH):
        if resolve_profile_role(profile.get("profile_name"), profile) == "teacher":
            count += 1
    return count


def sanitize_notice_text(value: Any) -> str:
    unescaped = html.unescape(str(value or ""))
    return re.sub(r"<[^>]+>", "", unescaped).replace("\xa0", " ").strip()


def build_workspace_payload(store: MirrorStore, profile: dict[str, Any]) -> dict[str, Any]:
    role = resolve_profile_role(profile.get("profile_name"), profile)
    capabilities = capabilities_for_role(role)
    if capabilities is None:
        raise ValueError("Unsupported workspace role")

    school_info = _profile_school_info(profile)
    campuses = store.list_campuses()
    common: dict[str, Any] = {
        "role": role,
        "displayName": _display_name(profile),
        "schoolName": str(school_info.get("name") or school_info.get("eduName") or "教学机构").strip(),
        "navigation": capabilities.navigation_payload(),
        "campuses": campuses,
    }

    classes = [row for row in store.list_classes() if isinstance(row, dict)]
    plans = [row for row in store.list_teaching_plans() if isinstance(row, dict)]
    today = date.today()

    if role == "admin":
        active_classes = [row for row in classes if _is_active_class(row)]
        today_lessons = [_lesson_payload(row) for row in plans if _plan_date(row) == today]
        unassigned_classes = [
            row for row in active_classes if _as_int(row.get("lecturer_id") or row.get("lecturerId")) in {None, 0}
        ]
        common.update(
            {
                "metrics": {
                    "teachers": _teacher_count(store),
                    "activeClasses": len(active_classes),
                    "students": _student_count(store),
                    "todayLessons": len(today_lessons),
                },
                "todayLessons": today_lessons,
                "exceptions": [
                    {
                        "type": "unassigned-class",
                        "label": str(row.get("name") or row.get("className") or "未命名班级"),
                        "href": f"/school-home-page/class-management1/divide-class1?id={_as_int(row.get('id')) or 0}",
                    }
                    for row in unassigned_classes
                ],
            }
        )
        return common

    if role == "teacher":
        teacher_id = _profile_user_id(profile)
        own_classes = [
            row
            for row in classes
            if teacher_id is not None
            and _as_int(row.get("lecturer_id") or row.get("lecturerId")) == teacher_id
            and _is_active_class(row)
        ]
        own_class_ids = {_as_int(row.get("id")) for row in own_classes}
        own_plans = [
            row
            for row in plans
            if _as_int(row.get("lecturer_id") or row.get("lecturerId")) == teacher_id
            or _as_int(row.get("curriculum_class_id") or row.get("classId")) in own_class_ids
        ]
        today_lessons = [_lesson_payload(row) for row in own_plans if _plan_date(row) == today]
        common.update(
            {
                "teacherId": teacher_id,
                "metrics": {
                    "classes": len(own_classes),
                    "todayLessons": len(today_lessons),
                    "pendingPreparation": sum(
                        1 for row in own_plans if not _as_int(row.get("curriculum_meterial_id"))
                    ),
                },
                "classes": own_classes,
                "todayLessons": today_lessons,
            }
        )
        return common

    common.update({"metrics": {}, "classes": []})
    return common


def workspace_asset_path(asset_path: str) -> Path | None:
    normalized = str(asset_path or "").replace("\\", "/").lstrip("/")
    candidate = (WORKSPACE_ASSET_ROOT / normalized).resolve()
    if WORKSPACE_ASSET_ROOT.resolve() not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def render_workspace_html(role: str, profile: dict[str, Any]) -> str:
    capabilities = capabilities_for_role(role)
    if capabilities is None:
        raise ValueError("Unsupported workspace role")
    template = (WORKSPACE_ASSET_ROOT / "index.html").read_text(encoding="utf-8")
    nav_html = "".join(
        (
            f'<a class="nav-link" data-nav-key="{html.escape(item.key)}" '
            f'href="{html.escape(item.href)}"><span class="nav-mark" aria-hidden="true"></span>'
            f'<span>{html.escape(item.label)}</span></a>'
        )
        for item in capabilities.navigation
    )
    boot = {
        "role": role,
        "defaultRoute": capabilities.default_route,
        "displayName": _display_name(profile),
    }
    replacements = {
        "{{ROLE}}": html.escape(role),
        "{{ROLE_LABEL}}": "机构管理员" if role == "admin" else "授课教师",
        "{{PAGE_TITLE}}": "机构运营工作台" if role == "admin" else "教学工作台",
        "{{DEFAULT_ROUTE}}": capabilities.default_route,
        "{{NAVIGATION}}": nav_html,
        "{{BOOTSTRAP}}": json.dumps(boot, ensure_ascii=False).replace("</", "<\\/"),
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
