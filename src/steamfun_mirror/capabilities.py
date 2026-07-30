from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any

from .config import STUDENT_LOGIN_PATH


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    href: str
    icon: str


@dataclass(frozen=True)
class RoleCapabilities:
    role: str
    default_route: str
    navigation: tuple[NavigationItem, ...]
    frontend_prefixes: tuple[str, ...]
    api_scopes: tuple[str, ...]

    def navigation_payload(self) -> list[dict[str, str]]:
        return [asdict(item) for item in self.navigation]


ADMIN_NAVIGATION = (
    NavigationItem("overview", "班级与排课", "/school-home-page/class-management1", "layout-dashboard"),
    NavigationItem("teachers", "教师账号", "/school-home-page/school-user-list", "users"),
    NavigationItem("classes", "班级与排课", "/school-home-page/class-management1", "calendar-days"),
    NavigationItem("students", "学员管理", "/school-home-page/class-management1/students-management1", "graduation-cap"),
    NavigationItem("courses", "课程管理", "/school-home-page/course-list", "library"),
    NavigationItem("campuses", "校区设置", "/school-home-page/schoolSys", "building-2"),
)

TEACHER_NAVIGATION = (
    NavigationItem("overview", "班级管理", "/code-classroom/classroom-index", "layout-dashboard"),
    NavigationItem("classes", "我的班级", "/code-classroom/classroom-index", "school"),
    NavigationItem("preparation", "备课中心", "/code-classroom/prepare-lessons", "notebook-pen"),
    NavigationItem("plans", "教学计划", "/school-home-page/class-management1/teachplan1", "calendar-check"),
    NavigationItem("students", "学员视图", "/school-home-page/class-management1/students-management1", "users"),
)

STUDENT_NAVIGATION = (
    NavigationItem("classes", "我的课程", "/code-classroom/myClass", "book-open"),
    NavigationItem("records", "学习记录", "/code-classroom/myClass#records", "chart-no-axes-column"),
)


ROLE_CAPABILITIES: dict[str, RoleCapabilities] = {
    "admin": RoleCapabilities(
        role="admin",
        default_route="/school-home-page/class-management1",
        navigation=ADMIN_NAVIGATION,
        frontend_prefixes=(
            "/school-home-page/school-user-list",
            "/school-home-page/schoolSys",
            "/school-home-page/class-management1",
            "/school-home-page",
            "/background/course-management/school-curriculum",
            "/background",
        ),
        api_scopes=("workspace:admin", "staff:write", "campus:write", "teaching:write"),
    ),
    "teacher": RoleCapabilities(
        role="teacher",
        default_route="/code-classroom/classroom-index",
        navigation=TEACHER_NAVIGATION,
        frontend_prefixes=(
            "/code-classroom/classroom-index",
            "/code-classroom/myClass",
            "/code-classroom/prepare-lessons",
            "/code-classroom/teach-lessons",
            "/school-home-page/class-management1",
            "/school-home-page",
        ),
        api_scopes=("workspace:teacher", "teaching:read", "teaching:write"),
    ),
    "student": RoleCapabilities(
        role="student",
        default_route="/code-classroom/myClass",
        navigation=STUDENT_NAVIGATION,
        frontend_prefixes=(
            "/code-classroom/myClass",
            "/code-classroom/classroom-index",
            "/code-classroom",
            "/exam-stu",
        ),
        api_scopes=("workspace:student", "learning:read", "learning:write"),
    ),
}


def _permission(alias: str, label: str, *children: dict[str, Any]) -> dict[str, Any]:
    return {
        "alias": alias,
        "name": label,
        "viewScope": 0,
        "children": list(children),
    }


_STUDENT_VIEW = _permission(
    "students-management1",
    "学员管理",
    _permission(
        "currentStudent",
        "在读学员",
        _permission("studentDetails", "查询"),
        _permission("addnewstudent1", "新增学员"),
        _permission("batchAddStu", "批量新增学员"),
        _permission("batchSettingValid", "批量设置账号有效期"),
        _permission("batchDeleteStu", "批量删除"),
        _permission("exportStu", "导出数据"),
    ),
    _permission("historyStu", "历史学员", _permission("historyStuQuery", "查询")),
)
_CLASS_VIEW = _permission(
    "class-management1",
    "班级管理",
    _permission(
        "inClass",
        "在读班级",
        _permission("inClassQuery,divide-class1,allDivide-class", "查询"),
        _permission("create-openclass1", "新建班级"),
    ),
    _permission("graduationClass", "结业班级", _permission("graduationClassQuery", "查询")),
)
_PLAN_VIEW = _permission(
    "teachplan1",
    "教学计划",
    _permission("unscheduledClass", "未排课", _permission("unscheduledClassQuery", "查询")),
    _permission(
        "courseScheduled",
        "已排课",
        _permission("courseScheduledQuery", "查询"),
        _permission("exportScheduled", "导出"),
    ),
)
_CLASS_RECORDS = _permission(
    "classRecord",
    "上课记录",
    _permission(
        "callRecord",
        "点名记录",
        _permission("callRecordQuery", "查询"),
        _permission("exportCallRecord", "导出点名记录"),
    ),
    _permission("evalDetails", "点评详情"),
)
_COURSE_CENTER = _permission(
    "courseCenter",
    "课程中心",
    _permission(
        "course-list",
        "课程管理",
        _permission("courseQuery,prepare-ppt", "查询"),
        _permission("school-curriculum", "课程体系"),
    ),
)

SPA_PERMISSION_TREES: dict[str, tuple[dict[str, Any], ...]] = {
    "admin": (
        _permission("tchCenter", "教务中心", _STUDENT_VIEW, _CLASS_VIEW, _PLAN_VIEW, _CLASS_RECORDS),
        _COURSE_CENTER,
        _permission(
            "systemSetting",
            "系统设置",
            _permission(
                "permissionsettings",
                "权限设置",
                _permission(
                    "school-user-list",
                    "教师账号",
                    _permission("school-edit-user-info", "查询"),
                    _permission("createAccount", "新建教师"),
                ),
                _permission(
                    "schoolSys",
                    "校区设置",
                    _permission("campusQuery", "查询"),
                    _permission("createCampus", "新建校区"),
                ),
            ),
        ),
    ),
    "teacher": (
        _permission("tchCenter", "教务中心", _STUDENT_VIEW, _CLASS_VIEW, _PLAN_VIEW, _CLASS_RECORDS),
        _COURSE_CENTER,
    ),
    "student": (),
}


def permission_tree_for_role(role: str | None) -> list[dict[str, Any]]:
    return copy.deepcopy(list(SPA_PERMISSION_TREES.get(str(role or ""), ())))


EXCLUDED_FRONTEND_PREFIXES = (
    "/school-home-page/orderpay",
    "/school-home-page/front-desk",
    "/school-home-page/enrollment",
    "/school-home-page/finance",
    "/school-home-page/report",
    "/school-home-page/star",
    "/school-home-page/store",
    "/background/course-management/platform-curriculum",
)


def _matches_prefix(path: str, prefix: str) -> bool:
    normalized = "/" + str(path or "").strip("/")
    normalized_prefix = "/" + prefix.strip("/")
    return normalized == normalized_prefix or normalized.startswith(normalized_prefix + "/")


def capabilities_for_role(role: str | None) -> RoleCapabilities | None:
    return ROLE_CAPABILITIES.get(str(role or "").strip())


def default_route_for_role(role: str | None) -> str | None:
    capabilities = capabilities_for_role(role)
    return capabilities.default_route if capabilities is not None else None


def roles_for_frontend_route(path: str) -> frozenset[str] | None:
    normalized = "/" + str(path or "").split("?", 1)[0].strip("/")
    if any(_matches_prefix(normalized, prefix) for prefix in EXCLUDED_FRONTEND_PREFIXES):
        return frozenset()

    matches: list[tuple[int, str]] = []
    for role, capabilities in ROLE_CAPABILITIES.items():
        for prefix in capabilities.frontend_prefixes:
            if _matches_prefix(normalized, prefix):
                matches.append((len(prefix), role))
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    return frozenset(role for length, role in matches if length == longest)


def resolve_profile_role(profile_name: str | None, profile: dict[str, Any] | None = None) -> str | None:
    normalized_name = str(profile_name or "").strip()
    if isinstance(profile, dict):
        login_path = str(profile.get("login_path") or "").strip()
        fresh_auth = profile.get("fresh_auth") if isinstance(profile.get("fresh_auth"), dict) else {}
        user_info = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
        if login_path == STUDENT_LOGIN_PATH or int(fresh_auth.get("identity") or 0) == 2:
            return "student"
        actual_name = str(profile.get("profile_name") or normalized_name).strip()
        role_ids = fresh_auth.get("roleList") or user_info.get("roleList") or []
        is_principal = bool(
            fresh_auth.get("is_principal")
            or fresh_auth.get("principal")
            or user_info.get("is_principal")
            or user_info.get("principal")
            or 5 in role_ids
            or "5" in role_ids
        )
        if actual_name == "admin" or is_principal:
            return "admin"
        if actual_name == "student" or actual_name.startswith("local_student_"):
            return "student"
        if actual_name:
            return "teacher"

    if normalized_name == "admin":
        return "admin"
    if normalized_name == "student" or normalized_name.startswith("local_student_"):
        return "student"
    if normalized_name:
        return "teacher"
    return None
