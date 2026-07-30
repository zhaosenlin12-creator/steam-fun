from __future__ import annotations

import gzip
import json
from pathlib import Path
import re

import brotli
from fastapi.testclient import TestClient
import requests

import steamfun_mirror.server as server_module
from steamfun_mirror.server import create_app
from steamfun_mirror.storage import MirrorStore


class FakeResponse:
    def __init__(self, *, content: bytes, content_type: str, status_code: int = 200):
        self.content = content
        self.headers = {"content-type": content_type}
        self.status_code = status_code

    def iter_content(self, chunk_size: int = 8192):
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index:index + chunk_size]

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _write_shell(root: Path) -> None:
    target = root / "origin" / "steam.fun"
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text("<!doctype html><html><body>shell</body></html>", encoding="utf-8")


def _flatten_permission_tree_for_storage(nodes: list[dict]) -> list[dict]:
    flattened: list[dict] = []
    for node in nodes:
        merged = {key: value for key, value in node.items() if key not in {"children", "userResource"}}
        user_resource = node.get("userResource")
        if isinstance(user_resource, dict):
            merged.update(user_resource)
        flattened.append(merged)

        children = node.get("children")
        if isinstance(children, list):
            flattened.extend(_flatten_permission_tree_for_storage(children))
    return flattened


def _store_teacher_profile(
    root: Path,
    *,
    profile_name: str = "teacher",
    username: str = "teacher",
    token: str = "teacher-token",
    auth_tree: str = '{"children":[]}',
    permissions: list[dict] | None = None,
    user_info: dict | None = None,
    school_info: dict | None = None,
) -> None:
    store = MirrorStore(root)
    permissions = permissions or []
    user_info = user_info or {}
    school_info_payload = {"eduCampusId": 851}
    if school_info:
        school_info_payload.update(school_info)
    store.store_profile(
        profile_name=profile_name,
        username=username,
        password_hash="hash",
        login_path="/java-api/school/tch/login",
        token=token,
        login_content={"authTree": auth_tree, "token": token},
        fresh_auth={"identity": 1, "userInfo": user_info, "schoolInfo": school_info_payload, "roleList": []},
        vuex_state={
            "user": {
                "token": token,
                "permisionList": permissions,
                "adminpermisionList": permissions,
                "userInfo": user_info,
                "schoolInfo": school_info_payload,
                "identity": 1,
            }
        },
    )


def _store_student_profile(
    root: Path,
    *,
    token: str = "student-token",
    fresh_auth: dict | None = None,
    vuex_state: dict | None = None,
) -> None:
    store = MirrorStore(root)
    fresh_auth_payload = fresh_auth or {"identity": 2, "userInfo": {}, "schoolInfo": {}, "roleList": []}
    vuex_payload = vuex_state or {"user": {"permisionList": []}}
    store.store_profile(
        profile_name="student",
        username="student",
        password_hash="hash",
        login_path="/java-api/student/stu/login",
        token=token,
        login_content={"token": token},
        fresh_auth=fresh_auth_payload,
        vuex_state=vuex_payload,
    )


def _core_background_auth_tree_payload() -> dict:
    return {
        "children": [
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "dataOverview", "name": "数据概览", "sort": 1},
                            }
                        ],
                        "userResource": {"alias": "dataBoard", "name": "数据看板", "sort": 1},
                    }
                ],
                "userResource": {"alias": "pageHome", "name": "首页", "sort": 1},
            },
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "currentStudent", "name": "在读学员", "sort": 1},
                            }
                        ],
                        "userResource": {"alias": "students-management1", "name": "学员管理", "sort": 1},
                    },
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "inClass", "name": "在读班级", "sort": 1},
                            }
                        ],
                        "userResource": {"alias": "class-management1", "name": "班级管理", "sort": 2},
                    },
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "callRecord", "name": "点名记录", "sort": 1},
                            }
                        ],
                        "userResource": {"alias": "classRecord", "name": "上课记录", "sort": 3},
                    },
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "courseScheduled", "name": "已排课", "sort": 1},
                            }
                        ],
                        "userResource": {"alias": "teachplan1", "name": "教学计划", "sort": 4},
                    },
                ],
                "userResource": {"alias": "tchCenter", "name": "教务中心", "sort": 5},
            },
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "courseQuery", "name": "查询", "sort": 1},
                            },
                            {
                                "children": [],
                                "userResource": {"alias": "school-curriculum", "name": "课程体系", "sort": 2},
                            },
                        ],
                        "userResource": {"alias": "course-list", "name": "课程管理", "sort": 1},
                    }
                ],
                "userResource": {"alias": "courseCenter", "name": "课程中心", "sort": 6},
            },
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "school-user-list", "name": "员工权限", "sort": 1},
                            },
                            {
                                "children": [],
                                "userResource": {"alias": "platform", "name": "课程管理", "sort": 2},
                            },
                        ],
                        "userResource": {"alias": "permissionsettings", "name": "权限设置", "sort": 1},
                    }
                ],
                "userResource": {"alias": "systemSetting", "name": "系统设置", "sort": 9},
            },
        ]
    }




def test_profile_role_distinguishes_admin_teacher_and_student(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[{"userResource":{"alias":"school-curriculum"}}]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9001, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9001, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    _store_teacher_profile(tmp_path)
    _store_student_profile(tmp_path)

    assert server_module._profile_role("admin", store.get_profile("admin")) == "admin"
    assert server_module._profile_role("teacher", store.get_profile("teacher")) == "teacher"
    assert server_module._profile_role("student", store.get_profile("student")) == "student"


def test_role_capabilities_define_canonical_workspaces_and_route_scope() -> None:
    assert server_module._default_frontend_route_for_role("admin") == "/background/course-management/school-curriculum"
    assert server_module._default_frontend_route_for_role("teacher") == "/code-classroom/classroom-index"
    assert server_module._default_frontend_route_for_role("student") == "/code-classroom/myClass"
    assert server_module._allowed_frontend_roles("/school-home-page/school-user-list") == frozenset({"admin"})
    assert server_module._allowed_frontend_roles("/workspace/admin") is None
    assert server_module._allowed_frontend_roles("/workspace/teacher") is None
    assert server_module._allowed_frontend_roles("/school-home-page/orderpay") == frozenset()


def test_curated_permission_trees_include_core_operations_and_exclude_disabled_modules() -> None:
    admin_tree = server_module._curated_permission_tree("admin")
    teacher_tree = server_module._curated_permission_tree("teacher")
    admin_serialized = json.dumps(admin_tree, ensure_ascii=False)
    teacher_serialized = json.dumps(teacher_tree, ensure_ascii=False)

    assert "school-user-list" in admin_serialized
    assert "schoolSys" in admin_serialized
    assert "class-management1" in admin_serialized
    assert "teachplan1" in teacher_serialized
    assert "school-user-list" not in teacher_serialized
    for disabled_alias in ("orderpay", "financialCenter", "starManagement", "clueManagement", "order-report"):
        assert disabled_alias not in admin_serialized
        assert disabled_alias not in teacher_serialized


def test_curated_permission_tree_preserves_legacy_tab_action_lookup_contract() -> None:
    teacher_tree = server_module._curated_permission_tree("teacher")

    def find(alias: str) -> dict[str, Any]:
        pending = list(teacher_tree)
        while pending:
            node = pending.pop()
            if node.get("alias") == alias:
                return node
            pending.extend(node.get("children") or [])
        raise AssertionError(f"missing permission node: {alias}")

    current_students = find("currentStudent")
    scheduled = find("courseScheduled")
    unscheduled = find("unscheduledClass")

    assert any(child["name"] == "查询" for child in current_students["children"])
    assert any(child["name"] == "查询" for child in scheduled["children"])
    assert any(child["name"] == "查询" for child in unscheduled["children"])
    assert all(child["viewScope"] == 0 for child in current_students["children"])
    assert all(child["viewScope"] == 0 for child in scheduled["children"])
    assert all(child["viewScope"] == 0 for child in unscheduled["children"])


def test_runtime_guards_redirect_authenticated_spa_root_to_canonical_role_home() -> None:
    html = "<!doctype html><html><head></head><body></body></html>"

    patched = server_module._inject_runtime_guards(html)

    assert "__localCoreRouteCleanup" not in patched
    assert "__localNonCoreDashboardGuard" not in patched
    assert "__localPostLoginRedirectGuard" in patched
    assert "admin:'/background/course-management/school-curriculum'" in patched
    assert "teacher:'/code-classroom/classroom-index'" in patched
    assert "student:'/code-classroom/myClass'" in patched
    assert "event.stopImmediatePropagation()" in patched
    assert "redirecting=true" in patched
    assert "history.pushState" in patched
    assert "window.location.replace(targets[role])" in patched
    assert "/workspace/admin" not in patched
    assert "/workspace/teacher" not in patched
    assert "/school-home-page/class-management1/students-management1" not in patched


def test_runtime_guards_add_path_scoped_student_myclass_responsive_layout() -> None:
    html = "<!doctype html><html><head></head><body></body></html>"

    patched = server_module._inject_runtime_guards(html)

    assert "__localStudentMyClassLayout" in patched
    assert "local-student-myclass" in patched
    assert "html.local-student-myclass .school-home-page>.frame>.menu" in patched
    assert "html.local-student-myclass .school-home-page>.frame>section" in patched


def test_admin_workspace_bootstrap_contains_operational_metrics(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="principal",
        token="admin-token",
        user_info={"id": 9001, "realName": "Principal"},
        school_info={"eduCampusId": 851, "name": "Mirror School"},
    )
    store = MirrorStore(tmp_path)
    store.upsert_local_campus({"id": 851, "name": "中心校区"})
    store.create_local_student(
        {
            "eduCampusId": 851,
            "name": "student-one",
            "realName": "Student One",
            "sex": "",
            "normalState": "1",
            "parentAPhoneNum": "",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "",
            "headimgUrl": "",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "admin")

    response = client.get("/api/workspace/bootstrap")

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["role"] == "admin"
    assert content["displayName"] == "Principal"
    assert {"teachers", "activeClasses", "students", "todayLessons"} <= set(content["metrics"])
    assert content["metrics"]["students"] == 1
    assert content["campuses"][0]["id"] == 851


def test_teacher_workspace_bootstrap_only_returns_own_classes(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        user_info={"id": 12385, "userId": 12385, "realName": "Teacher Li"},
    )
    store = MirrorStore(tmp_path)
    store.upsert_local_class({"id": 4101, "name": "我的机器人班", "campusId": 851, "lecturer_id": 12385})
    store.upsert_local_class({"id": 4102, "name": "其他教师班", "campusId": 851, "lecturer_id": 99881})
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/api/workspace/bootstrap")

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["role"] == "teacher"
    assert content["displayName"] == "Teacher Li"
    assert [row["id"] for row in content["classes"]] == [4101]


def test_workspace_bootstrap_requires_authenticated_session(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/api/workspace/bootstrap")

    assert response.status_code == 401


def test_workspace_pages_redirect_to_canonical_role_homes(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_profile(tmp_path, profile_name="admin", username="principal", token="admin-token")
    app = create_app(tmp_path, allow_live_proxy=False)

    anonymous = TestClient(app)
    anonymous_response = anonymous.get("/workspace/admin", follow_redirects=False)
    assert anonymous_response.status_code in {302, 303, 307}
    assert anonymous_response.headers["location"].startswith("/login?next=")

    admin = TestClient(app)
    admin.cookies.set("mirror_profile", "admin")
    admin_response = admin.get("/workspace/admin", follow_redirects=False)
    assert admin_response.status_code in {302, 303, 307}
    assert admin_response.headers["location"] == "/background/course-management/school-curriculum"

    teacher = TestClient(app)
    teacher.cookies.set("mirror_profile", "teacher")
    teacher_response = teacher.get("/workspace/teacher", follow_redirects=False)
    assert teacher_response.status_code in {302, 303, 307}
    assert teacher_response.headers["location"] == "/code-classroom/classroom-index"

    forbidden = teacher.get("/workspace/admin", follow_redirects=False)
    assert forbidden.status_code in {302, 303, 307}
    assert forbidden.headers["location"] == "/code-classroom/classroom-index"


def test_workspace_static_assets_remain_local_for_workspace_apis(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    assert client.get("/_site/workspace/styles.css").status_code == 200
    assert client.get("/_site/workspace/app.js").status_code == 200


def test_workspace_mobile_navigation_control_is_hidden_on_desktop(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    styles = client.get("/_site/workspace/styles.css").text

    assert ".icon-button.mobile-menu{display:none}" in styles
    assert "@media(max-width:760px)" in styles
    assert ".icon-button.mobile-menu{display:grid}" in styles


def test_workspace_hidden_role_controls_cannot_be_overridden_by_layout_styles(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    styles = client.get("/_site/workspace/styles.css").text

    assert "[hidden]{display:none!important}" in styles


def test_workspace_script_wires_teacher_and_campus_management_actions(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    script = client.get("/_site/workspace/app.js").text

    assert 'request("/api/workspace/teachers' in script
    assert 'request("/api/workspace/campuses' in script
    assert "loadTeachers" in script
    assert "loadCampuses" in script
    assert "openTeacherDialog" in script
    assert "openCampusDialog" in script
    assert "/password" in script


def test_workspace_dialog_cancel_controls_bypass_required_field_validation(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    template = Path(server_module.__file__).resolve().parent / "site_assets" / "workspace" / "index.html"
    page = template.read_text(encoding="utf-8")
    script = client.get("/_site/workspace/app.js").text

    assert page.count('type="button" data-dialog-cancel') == 2
    assert 'value="cancel" type="submit"' not in page
    assert 'querySelectorAll("[data-dialog-cancel]")' in script
    assert 'document.getElementById("record-dialog").close()' in script


def test_admin_workspace_teacher_lifecycle_controls_login_and_campus_scope(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="principal",
        token="admin-token",
        user_info={"id": 9001, "realName": "Principal"},
    )
    store = MirrorStore(tmp_path)
    store.upsert_local_campus({"id": 851, "name": "中心校区"})
    admin = TestClient(create_app(tmp_path, allow_live_proxy=False))
    admin.cookies.set("mirror_profile", "admin")

    created_response = admin.post(
        "/api/workspace/teachers",
        json={
            "name": "teacher-new",
            "realName": "New Teacher",
            "password": "StrongPass123",
            "eduCampusIdList": [851],
            "eduRoleIdList": [1],
            "state": "在职",
            "tchState": True,
        },
    )

    assert created_response.status_code == 200
    created = created_response.json()["content"]
    assert created["name"] == "teacher-new"
    assert created["eduCampusIdList"] == [851]
    assert created["tchState"] is True

    login = TestClient(create_app(tmp_path, allow_live_proxy=False)).post(
        "/java-api/school/tch/login",
        json={"userName": "teacher-new", "password": "StrongPass123"},
    )
    assert login.json()["success"] is True
    assert login.json()["mirror"]["redirect"] == "/code-classroom/classroom-index"

    disabled_response = admin.patch(
        f"/api/workspace/teachers/{created['userId']}",
        json={"state": "停用", "tchState": False},
    )
    assert disabled_response.status_code == 200
    assert disabled_response.json()["content"]["tchState"] is False

    disabled_login = TestClient(create_app(tmp_path, allow_live_proxy=False)).post(
        "/java-api/school/tch/login",
        json={"userName": "teacher-new", "password": "StrongPass123"},
    )
    assert disabled_login.json()["success"] is False
    assert disabled_login.json()["error"]["code"] == "AccountDisabled"

    enabled_response = admin.patch(
        f"/api/workspace/teachers/{created['userId']}",
        json={"state": "在职", "tchState": True},
    )
    assert enabled_response.json()["content"]["tchState"] is True
    reset_response = admin.post(
        f"/api/workspace/teachers/{created['userId']}/password",
        json={"password": "ResetPass456"},
    )
    assert reset_response.status_code == 200
    old_password_login = TestClient(create_app(tmp_path, allow_live_proxy=False)).post(
        "/java-api/school/tch/login",
        json={"userName": "teacher-new", "password": "StrongPass123"},
    )
    new_password_login = TestClient(create_app(tmp_path, allow_live_proxy=False)).post(
        "/java-api/school/tch/login",
        json={"userName": "teacher-new", "password": "ResetPass456"},
    )
    assert old_password_login.json()["success"] is False
    assert new_password_login.json()["success"] is True


def test_workspace_teacher_delete_rejects_class_reference(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, profile_name="admin", username="principal", token="admin-token")
    admin = TestClient(create_app(tmp_path, allow_live_proxy=False))
    admin.cookies.set("mirror_profile", "admin")
    created = admin.post(
        "/api/workspace/teachers",
        json={"name": "teacher-linked", "realName": "Linked Teacher", "password": "StrongPass123"},
    ).json()["content"]
    MirrorStore(tmp_path).upsert_local_class(
        {"id": 4201, "name": "引用班级", "campusId": 851, "lecturer_id": created["userId"]}
    )

    response = admin.delete(f"/api/workspace/teachers/{created['userId']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TeacherInUse"
    assert MirrorStore(tmp_path).get_profile(f"teacher_{created['userId']}") is not None


def test_teacher_cannot_mutate_workspace_staff_or_campuses(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    assert client.post("/api/workspace/teachers", json={"name": "blocked"}).status_code == 403
    assert client.post("/api/workspace/campuses", json={"name": "blocked"}).status_code == 403


def test_employee_setting_and_campus_compatibility_use_workspace_services(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="principal",
        token="admin-token",
        user_info={"id": 9001, "realName": "Principal"},
    )
    _store_teacher_profile(
        tmp_path,
        username="teacher-one",
        token="teacher-token",
        user_info={"id": 12385, "realName": "Teacher One"},
    )
    MirrorStore(tmp_path).upsert_local_campus({"id": 851, "name": "中心校区"})
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "admin")

    employees = client.post(
        "/java-api/school/tch/employeeSetting/selectEmployList",
        json={"pageNum": 1, "pageSize": 20},
    )
    campuses = client.get("/api/get/school/right/info")
    campus_teachers = client.get(
        "/java-api/school/edu/campus/selectEduCampusTchList",
        params={"eduCampusId": 851},
    )

    assert employees.status_code == 200
    assert any(row["name"] == "teacher-one" for row in employees.json()["content"]["records"])
    assert campuses.status_code == 200
    assert campuses.json()["content"]["campusList"][0]["id"] == 851
    assert campus_teachers.status_code == 200
    assert any(row["name"] == "teacher-one" for row in campus_teachers.json()["content"])


def _store_runtime_student_profile(root: Path, *, token: str = "student-token") -> None:
    _store_student_profile(
        root,
        token=token,
        fresh_auth={
            "identity": 2,
            "userInfo": {
                "stuUserInfo": {
                    "id": 400057,
                    "name": "lbschenmuran",
                    "eduCampusId": 851,
                    "stuUserInfo": {"id": 400057, "realName": "Chen Muran", "sex": "M", "eduCampusId": 851},
                }
            },
            "schoolInfo": {"id": 834, "name": "Mirror School", "eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": token,
                "permisionList": [],
                "userInfo": {
                    "stuUserInfo": {
                        "id": 400057,
                        "name": "lbschenmuran",
                        "eduCampusId": 851,
                        "stuUserInfo": {"id": 400057, "realName": "Chen Muran", "sex": "M", "eduCampusId": 851},
                    }
                },
                "schoolInfo": {"id": 834, "name": "Mirror School", "eduCampusId": 851},
                "identity": 2,
            }
        },
    )


def _store_student_management_captures(root: Path, *, stu_id: int = 2001) -> None:
    store = MirrorStore(root)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/stu/selectStudy?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "pageNum": 1,
                    "pageSize": 20,
                    "totalSize": 1,
                    "totalPages": 1,
                    "content": [
                        {
                            "stuId": stu_id,
                            "stuName": "Local Mirror Student",
                            "normalState": 1,
                            "stuAccount": "mirror-student",
                            "className": "--",
                            "openId": "openid-1",
                            "authorizerOpenid": None,
                            "parentWeChat": "已绑定(1)",
                            "wcmFlag": "未绑定",
                            "endDate": "2026-05-19",
                            "eduCampusName": "Default Campus",
                            "sex": "M",
                            "age": None,
                            "birthday": None,
                            "kinship": None,
                            "phoneNum": "13800138000",
                            "contactInformation": None,
                            "schoolName": "Mirror School",
                            "grade": None,
                            "leader": None,
                            "leaderName": "",
                            "createdTime": "2026-05-13 06:24:42",
                            "activeStatus": False,
                            "totalActiveTime": 0,
                        }
                    ],
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/stu/queryClsStuMsg?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "id": stu_id,
                    "stuId": stu_id,
                    "normalState": 1,
                    "zoneAuth": 1,
                    "testAuth": 0,
                    "ojAuth": 0,
                    "ojAnalysisAuth": 0,
                    "ojTestcaseAuth": 0,
                    "stuNoteAuth": 0,
                    "pAuth": 0,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )


def _store_teacher_campus_user_capture(root: Path, *, students: list[dict]) -> None:
    store = MirrorStore(root)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/user/list?t=1&campusId=851",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "campusUserList": students,
                    "total": len(students),
                    "page_no": 1,
                    "page_size": max(len(students), 1),
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )


def _store_invalid_token_response(
    root: Path,
    url: str,
    *,
    profile_name: str = "teacher",
    method: str = "GET",
    message: str = "异地登录",
    request_body: bytes | None = None,
) -> None:
    store = MirrorStore(root)
    store.store_api_response(
        profile_name,
        method=method,
        url=url,
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": False,
                "error": {"code": "InvalidToken", "message": message},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        request_body=request_body,
    )


def _store_unauthorized_response(root: Path, url: str, *, profile_name: str = "teacher") -> None:
    store = MirrorStore(root)
    store.store_api_response(
        profile_name,
        method="GET",
        url=url,
        status=401,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": False,
                "error": {"code": "InvalidToken", "message": "寮傚湴鐧诲綍"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )


def _store_teacher_course_chain_captures(root: Path) -> None:
    store = MirrorStore(root)

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/user/campus/list?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "userDeptList": [
                        {
                            "id": 41885,
                            "dept_id": 851,
                            "user_id": 12385,
                            "campusName": "Default Campus",
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/subject/list?t=1&campusId=851",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "campusSubjectList": [
                        {"id": 1, "name": "Jrcode", "code": 1, "sort_num": 1, "state": 1, "is_vaild": True},
                        {"id": 2, "name": "Scratch", "code": 2, "sort_num": 2, "state": 1, "is_vaild": True},
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/curriculum/list/by/page?t=1&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "campusAuthList": [
                        {
                            "id": 9001,
                            "campusName": "Default Campus",
                            "educational_institution_campus_id": 851,
                            "subjectName": "Jrcode",
                            "price": 199,
                            "curriculumInfo": {
                                "id": 501,
                                "subject_id": 1,
                                "title": "编程启蒙J1/J2",
                                "number_of_courses": 32,
                                "teaching_type": 1,
                                "curriculum_type": 2,
                                "difficulty": 1,
                                "for_grade": "中班及以上",
                                "suggested_duration": "1.5h",
                                "curriculum_desc": "启蒙课程",
                                "img_url": "https://cdn.example.com/curriculum-j1.png",
                            },
                        },
                        {
                            "id": 9002,
                            "campusName": "Default Campus",
                            "educational_institution_campus_id": 851,
                            "subjectName": "Python",
                            "price": 299,
                            "curriculumInfo": {
                                "id": 901,
                                "subject_id": 3,
                                "title": "Python图形化",
                                "number_of_courses": 12,
                                "teaching_type": 1,
                                "curriculum_type": 3,
                                "difficulty": 2,
                                "for_grade": "三年级及以上",
                                "suggested_duration": "1.5h",
                                "curriculum_desc": "Python课程",
                                "img_url": "https://cdn.example.com/curriculum-python.png",
                            },
                        },
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=501&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 7001,
                            "subject_id": 1,
                            "curriculum_id": 501,
                            "title": "初次挑战",
                            "sort_num": 1,
                            "img_url": "https://cdn.example.com/lesson-1.png",
                            "ppt_url": "https://cdn.example.com/lesson-1/index.html",
                        },
                        {
                            "id": 7002,
                            "subject_id": 1,
                            "curriculum_id": 501,
                            "title": "动画进阶",
                            "sort_num": 2,
                            "img_url": "https://cdn.example.com/lesson-2.png",
                            "ppt_url": "https://cdn.example.com/lesson-2/index.html",
                        },
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=901&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 7101,
                            "subject_id": 3,
                            "curriculum_id": 901,
                            "title": "海龟绘图",
                            "sort_num": 1,
                            "img_url": "https://cdn.example.com/python-1.png",
                            "ppt_url": "https://cdn.example.com/python-1/index.html",
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/teaching/plan/list?t=1&campusIds=[851]&page_no=1&page_size=1000",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "teachingPlan": [
                        {
                            "id": 81001,
                            "educational_institution_id": 834,
                            "educational_institution_campus_id": 851,
                            "subject_id": 1,
                            "curriculum_id": 501,
                            "curriculum_class_id": 3001,
                            "lecturer_id": 11075,
                            "lecturerName": "Teacher A",
                            "curriculum_meterial_id": 7001,
                            "start_class_date": "2026-05-10 18:30:00",
                            "end_class_date": "2026-05-10 20:00:00",
                            "class_date": "2026-05-10",
                            "sign_state": 1,
                            "teachingPlanState": "已开课",
                            "classInfo": {
                                "id": 3001,
                                "name": "周日18:30 Jrcode",
                                "educational_institution_campus_id": 851,
                                "curriculum_class_type": 1,
                                "teaching_type": 1,
                                "week_json": [7],
                                "week_str": "周日",
                                "time_str": "18:30-20:00",
                                "end_class_state": 0,
                                "subjectInfoList": [{"id": 1, "name": "Jrcode"}],
                                "curriculumInfoList": [{"id": 501, "title": "编程启蒙J1/J2", "img_url": "https://cdn.example.com/curriculum-j1.png"}],
                            },
                            "lessionInfo": {"title": "初次挑战", "img_url": "https://cdn.example.com/lesson-1.png"},
                        },
                        {
                            "id": 81002,
                            "educational_institution_id": 834,
                            "educational_institution_campus_id": 851,
                            "subject_id": 1,
                            "curriculum_id": 501,
                            "curriculum_class_id": 3001,
                            "lecturer_id": 11075,
                            "lecturerName": "Teacher A",
                            "curriculum_meterial_id": 7002,
                            "start_class_date": "2026-05-17 18:30:00",
                            "end_class_date": "2026-05-17 20:00:00",
                            "class_date": "2026-05-17",
                            "sign_state": 2,
                            "teachingPlanState": "未开课",
                            "classInfo": {
                                "id": 3001,
                                "name": "周日18:30 Jrcode",
                                "educational_institution_campus_id": 851,
                                "curriculum_class_type": 1,
                                "teaching_type": 1,
                                "week_json": [7],
                                "week_str": "周日",
                                "time_str": "18:30-20:00",
                                "end_class_state": 0,
                                "subjectInfoList": [{"id": 1, "name": "Jrcode"}],
                                "curriculumInfoList": [{"id": 501, "title": "编程启蒙J1/J2", "img_url": "https://cdn.example.com/curriculum-j1.png"}],
                            },
                            "lessionInfo": {"title": "动画进阶", "img_url": "https://cdn.example.com/lesson-2.png"},
                        },
                        {
                            "id": 82001,
                            "educational_institution_id": 834,
                            "educational_institution_campus_id": 851,
                            "subject_id": 3,
                            "curriculum_id": 901,
                            "curriculum_class_id": 3002,
                            "lecturer_id": 11076,
                            "lecturerName": "Teacher B",
                            "curriculum_meterial_id": 7101,
                            "start_class_date": "2026-05-11 19:00:00",
                            "end_class_date": "2026-05-11 20:30:00",
                            "class_date": "2026-05-11",
                            "sign_state": 1,
                            "teachingPlanState": "已开课",
                            "classInfo": {
                                "id": 3002,
                                "name": "周一19:00 Python",
                                "educational_institution_campus_id": 851,
                                "curriculum_class_type": 2,
                                "teaching_type": 1,
                                "week_json": [1],
                                "week_str": "周一",
                                "time_str": "19:00-20:30",
                                "end_class_state": 1,
                                "subjectInfoList": [{"id": 3, "name": "Python"}],
                                "curriculumInfoList": [{"id": 901, "title": "Python图形化", "img_url": "https://cdn.example.com/curriculum-python.png"}],
                            },
                            "lessionInfo": {"title": "海龟绘图", "img_url": "https://cdn.example.com/python-1.png"},
                        },
                    ],
                    "total": 3,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )


def _store_competition_source_captures(root: Path) -> None:
    store = MirrorStore(root)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/exam/getBankSourceListWithoutPageForNew?t=1&source_type=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "sourceList": {
                        "matchSourceList": [
                            {
                                "id": 4,
                                "title": "蓝桥杯",
                                "sort_num": 3,
                                "source_type": 1,
                                "match_type": 1,
                                "match_url": "https://www.lanqiaoqingshao.cn/home",
                                "match_img_url": "https://cdn.example.com/lanqiao.png",
                                "match_sign_info": "关注官方网站",
                                "realExamNum": 435,
                                "trainNum": 0,
                            },
                            {
                                "id": 11,
                                "title": "信息素养大赛",
                                "sort_num": 2,
                                "source_type": 1,
                                "match_type": 1,
                                "match_url": "https://ceic.example.com",
                                "match_img_url": "https://cdn.example.com/ceic.png",
                                "match_sign_info": "关注官方网站",
                                "realExamNum": 517,
                                "trainNum": 386,
                            },
                        ]
                    }
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/exam/getTestQuestionBankSourceListWithoutPage?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "testQuestionBankSourceList": [
                        {"id": 4, "title": "蓝桥杯", "realExamNum": 435, "trainNum": 0},
                        {"id": 11, "title": "信息素养大赛", "realExamNum": 517, "trainNum": 386},
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

def test_student_fresh_data_is_normalized_for_legacy_frontend_shape(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_student_profile(
        tmp_path,
        token="student-token",
        fresh_auth={
            "identity": 2,
            "userInfo": {
                "stuUserInfo": {
                    "id": 400057,
                    "name": "lbschenmuran",
                    "eduCampusId": 851,
                    "stuUserInfo": {"realName": "陈沐然", "sex": "男"},
                }
            },
            "schoolInfo": {"id": 834, "name": "乐启享机器人"},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "student-token",
                "permisionList": [],
                "userInfo": {
                    "stuUserInfo": {
                        "id": 400057,
                        "name": "lbschenmuran",
                        "eduCampusId": 851,
                        "stuUserInfo": {"realName": "陈沐然", "sex": "男"},
                    }
                },
                "schoolInfo": {"id": 834, "name": "乐启享机器人"},
                "identity": 2,
            }
        },
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/student/stu/freshData?t=1",
        headers={"Authorization": "Bearer student-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["identity"] == 2
    assert content["userInfo"]["stuUserInfo"]["name"] == "lbschenmuran"
    assert content["stuUserInfo"]["name"] == "lbschenmuran"
    assert content["stuUserInfo"]["stuUserInfo"]["realName"] == "陈沐然"
    assert content["stuBaseInfo"]["realName"] == "陈沐然"


def test_teacher_fresh_data_uses_fresh_auth_user_info(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        user_info={
            "id": 12385,
            "name": "zhaosenlin",
            "realName": "赵森林",
            "phoneNum": "18164173640",
        },
        school_info={"id": 834, "name": "乐启享机器人"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/school/tch/freshData?t=1",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["identity"] == 1
    assert content["userInfo"]["id"] == 12385
    assert content["userInfo"]["realName"] == "赵森林"
    assert content["schoolInfo"]["name"] == "乐启享机器人"


def test_student_subject_endpoints_use_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_runtime_student_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/stu/subject/auth?t=1",
        profile_name="student",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/stu/work/subject?t=1",
        profile_name="student",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    subject_response = client.get(
        "/api/stu/get/stu/subject/auth?t=2",
        headers={"Authorization": "Bearer student-token"},
    )
    work_subject_response = client.get(
        "/api/stu/get/stu/work/subject?t=2",
        headers={"Authorization": "Bearer student-token"},
    )

    assert subject_response.status_code == 200
    assert work_subject_response.status_code == 200

    subject_content = subject_response.json()["content"]
    work_subject_content = work_subject_response.json()["content"]
    assert subject_content["total"] >= 1
    assert work_subject_content["total"] >= 1
    assert subject_content["subjectList"][0]["code"] == 1
    assert work_subject_content["subjectList"][0]["subjectCode"] == "1"


def test_student_course_views_use_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_runtime_student_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/indexinfo/for/new?t=1",
        profile_name="student",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/index/tch/work/list?t=1&page_no=1&page_size=20",
        profile_name="student",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/tch/work/list?t=1&subject_code=1&page_no=1&page_size=20",
        profile_name="student",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/stu/class/list?t=1&page_no=1&page_size=16",
        profile_name="student",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/stu/tch/plan/list?t=1&page_no=1&page_size=20",
        profile_name="student",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/stu/get/stu/timetable/new?t=1&page_no=1&page_size=20",
        profile_name="student",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    index_info_response = client.get(
        "/api/stu/get/indexinfo/for/new?t=2",
        headers={"Authorization": "Bearer student-token"},
    )
    index_work_response = client.get(
        "/api/stu/get/index/tch/work/list?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )
    work_response = client.get(
        "/api/stu/get/tch/work/list?t=2&subject_code=1&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )
    class_response = client.get(
        "/api/stu/get/stu/class/list?t=2&page_no=1&page_size=16",
        headers={"Authorization": "Bearer student-token"},
    )
    plan_response = client.get(
        "/api/stu/get/stu/tch/plan/list?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )
    timetable_response = client.get(
        "/api/stu/get/stu/timetable/new?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )
    timetable_no_page_response = client.get(
        "/api/stu/getStuTimetableNewWithOutPageInfo?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )

    assert index_info_response.status_code == 200
    index_info_content = index_info_response.json()["content"]
    assert {"workNum", "tchWorkNum", "loginDuration"} <= set(index_info_content)

    assert index_work_response.status_code == 200
    index_work_content = index_work_response.json()["content"]
    assert index_work_content["total"] >= 1
    assert index_work_content["page_no"] == 1
    assert index_work_content["page_size"] == 20
    assert index_work_content["workList"][0]["workUrl"] != ""

    assert work_response.status_code == 200
    work_content = work_response.json()["content"]
    assert work_content["total"] >= 1
    assert work_content["page_no"] == 1
    assert work_content["page_size"] == 20
    work_row = work_content["workList"][0]
    assert work_row["subjectCode"] == "1"
    assert work_row["stuUserId"] == 400057
    assert work_row["workUrl"] != ""

    assert class_response.status_code == 200
    class_content = class_response.json()["content"]
    assert class_content["total"] >= 1
    assert len(class_content["classlist"]) >= 1
    class_row = class_content["classlist"][0]
    assert class_row["curriculumInfo"]["img_url"] != ""
    assert class_row["curriculumInfo"]["number_of_courses"] >= 1
    assert "week_str" in class_row
    assert "time_str" in class_row

    assert plan_response.status_code == 200
    plan_content = plan_response.json()["content"]
    assert plan_content["total"] >= 1
    assert len(plan_content["tchPlanList"]) >= 1
    plan_row = plan_content["tchPlanList"][0]
    assert plan_row["classInfo"]["name"] != ""
    assert plan_row["lessionInfo"]["title"] != ""
    assert plan_row["stuTchPlanInfo"]["classWorkInfo"]["work_url"] != ""
    assert plan_row["stuTchPlanInfo"]["homeWorkInfo"]["work_url"] != ""

    assert timetable_response.status_code == 200
    assert timetable_response.json()["content"]["total"] >= 1
    assert timetable_no_page_response.status_code == 200
    assert timetable_no_page_response.json()["content"]["total"] >= 1


def test_external_course_thumbnail_falls_back_to_poster_asset(tmp_path: Path) -> None:
    poster_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "b_scratch_course"
        / "bb_general_course"
        / "version2.0"
        / "poster"
        / "09sample.png"
    )
    poster_path.parent.mkdir(parents=True, exist_ok=True)
    poster_bytes = b"\x89PNG\r\n\x1a\nposter"
    poster_path.write_bytes(poster_bytes)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/courses/b_scratch_course/bb_general_course/version2.0/thbn09sample.png"
    )

    assert response.status_code == 200
    assert response.content == poster_bytes


def test_external_course_slide_thumbnail_falls_back_to_poster_asset(tmp_path: Path) -> None:
    poster_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "b_scratch_course"
        / "bb_general_course"
        / "version3.0"
        / "poster"
        / "86sample-poster.png"
    )
    poster_path.parent.mkdir(parents=True, exist_ok=True)
    poster_bytes = b"\x89PNG\r\n\x1a\nslide-poster"
    poster_path.write_bytes(poster_bytes)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/courses/b_scratch_course/bb_general_course/version3.0/"
        "index/86sample/data/thmb1.jpg"
    )

    assert response.status_code == 200
    assert response.content == poster_bytes


def test_missing_external_course_slide_thumbnail_returns_transparent_png(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/courses/b_scratch_course/bb_general_course/version3.0/"
        "index/86sample/data/thmb2.png"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == server_module.TRANSPARENT_PNG_BYTES


def test_teacher_ppt_placeholder_icons_return_transparent_png(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    for asset_path in (
        "/img/play@2x.e008c712.png",
        "/img/rankingPodium@2x.266e0811.png",
        "/img/rankingTitle@2x.a9a389cf.png",
    ):
        response = client.get(asset_path)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert len(response.content) > 0


def test_jrcode_ui_off_assets_fall_back_to_on_assets(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    page_on = tmp_path / "origin" / "steam.fun" / "jrcode" / "assets" / "ui" / "pageOn.png"
    page_on.parent.mkdir(parents=True, exist_ok=True)
    page_on.write_bytes(b"page-on-bytes")
    num_on = tmp_path / "origin" / "steam.fun" / "jrcode" / "assets" / "ui" / "numOn.svg"
    num_on.write_text("<svg>num-on</svg>", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    page_off = client.get("/jrcode/assets/ui/pageOff.png")
    num_off = client.get("/jrcode/assets/ui/numOff.svg")

    assert page_off.status_code == 200
    assert page_off.content == b"page-on-bytes"
    assert num_off.status_code == 200
    assert num_off.text == "<svg>num-on</svg>"


def test_teacher_points_rule_tag_check_returns_local_success_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post("/java-api/points/tch/ruleTag/check?t=1778956152341", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["content"] == []
    assert payload["error"] == {"message": "", "code": ""}


def test_points_star_rule_returns_array_payload_for_frontend_iteration(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post("/java-api/points/sch/eduCampus/starRule?t=1778976340961", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"], list)
    assert payload["content"]
    assert payload["content"][0] == {"scene": "上课", "behavior": "上课和老师互动"}


def test_points_star_rule_prefers_local_array_payload_over_cached_object_response(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/points/sch/eduCampus/starRule",
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "success": True,
                "content": {"flag": True, "starNumLimit": 5},
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        request_body=b"{}",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/points/sch/eduCampus/starRule?t=1778976340961",
        headers={"Authorization": "Bearer teacher-token"},
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"], list)
    assert payload["content"]


def test_frontend_route_like_path_falls_back_to_shell(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page/class-management1/students-management1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "shell" in response.text
    assert "unhandledrejection" in response.text
    assert "var fcn=window.fcn;" in response.text
    assert "editor_opentype" in response.text


def test_teacher_students_management_route_bootstraps_schoolinfo_session(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, school_info={"id": 834, "name": "Mirror School", "eduCampusId": 851})
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page/class-management1/students-management1")

    assert response.status_code == 200
    assert "localStorage.setItem('vuex',JSON.stringify(data))" in response.text
    assert "sessionStorage.setItem('schoolInfo',JSON.stringify(data))" in response.text


def test_shell_fallback_removes_optional_prefetch_but_keeps_required_assets(tmp_path: Path) -> None:
    target = tmp_path / "origin" / "steam.fun"
    (target / "css").mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(
        (
            "<!doctype html><html><head>"
            '<link rel="prefetch" href="/css/chunk-missing.123456.css">'
            '<link rel="prefetch" href="/css/chunk-present.123456.css">'
            '<link rel="preload" href="/js/app.js" as="script">'
            '<link rel="stylesheet" href="/css/app.css">'
            "</head><body>shell</body></html>"
        ),
        encoding="utf-8",
    )
    (target / "css" / "chunk-present.123456.css").write_text("body{color:#222;}", encoding="utf-8")
    (target / "css" / "app.css").write_text("body{background:#fff;}", encoding="utf-8")
    (target / "js").mkdir(parents=True, exist_ok=True)
    (target / "js" / "app.js").write_text("console.log('app');", encoding="utf-8")
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page/class-management1/students-management1")

    assert response.status_code == 200
    assert '/css/chunk-missing.123456.css' not in response.text
    assert '/css/chunk-present.123456.css' not in response.text
    assert '/js/app.js' in response.text
    assert '/css/app.css' in response.text


def test_shell_fallback_removes_present_and_missing_js_prefetch_assets(tmp_path: Path) -> None:
    target = tmp_path / "origin" / "steam.fun"
    (target / "js").mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(
        (
            "<!doctype html><html><head>"
            '<link rel="prefetch" href="/js/chunk-missing.123456.js">'
            '<link rel="prefetch" href="/js/chunk-present.123456.js">'
            '<link rel="stylesheet" href="/css/app.css">'
            "</head><body>shell</body></html>"
        ),
        encoding="utf-8",
    )
    (target / "js" / "chunk-present.123456.js").write_text("console.log('present');", encoding="utf-8")
    (target / "css").mkdir(parents=True, exist_ok=True)
    (target / "css" / "app.css").write_text("body{background:#fff;}", encoding="utf-8")
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page/class-management1/students-management1")

    assert response.status_code == 200
    assert '/js/chunk-missing.123456.js' not in response.text
    assert '/js/chunk-present.123456.js' not in response.text


def test_classroom_ppt_routes_include_local_narrow_layout_guard(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    for route in (
        "/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=39525&tchPlanId=999999",
        "/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999",
    ):
        response = client.get(route, headers={"Authorization": "Bearer teacher-token"})

        assert response.status_code == 200
        assert "local-classroom-ppt" in response.text
        assert "course-left-ppt" in response.text
        assert "content_right" in response.text


def test_benign_placeholder_route_returns_minimal_html_instead_of_shell(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    for route in (
        "/code-classroom/prepare-lessons/prepare/undefined?usercode=test",
        "/code-classroom/teach-lessons/lessons/undefined?usercode=test",
    ):
        response = client.get(route)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.text == "<!doctype html><html><head><meta charset='utf-8'></head><body></body></html>"


def test_public_root_serves_marketing_homepage(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "乐启享" in response.text
    assert "系统培养孩子的科技素养与创造力" in response.text
    assert 'href="/login"' in response.text
    assert "18164173640" in response.text
    assert "texture.png" not in response.text



def test_root_with_teacher_cookie_still_serves_marketing_homepage(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, username="zhaosenlin", user_info={"id": 12385, "realName": "Teacher Li"})
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "乐启享机器人" in response.text


def test_root_with_student_cookie_still_serves_marketing_homepage(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "student")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "乐启享机器人" in response.text


def test_root_with_admin_cookie_still_serves_marketing_homepage(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[{"userResource":{"alias":"school-curriculum"}}]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9001, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9001, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "admin")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "乐启享机器人" in response.text


def test_marketing_homepage_contains_required_sections(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="hero"' in response.text
    assert 'id="about"' in response.text
    assert 'id="cinema"' in response.text
    assert 'id="collection"' in response.text
    assert 'id="signal"' in response.text
    assert "hero-stage" in response.text
    assert "about-stage" in response.text
    assert "cinema-stage" in response.text
    assert "collection-stage" in response.text
    assert "signal-stage" in response.text
    assert "从乐高启蒙 到 AI 创造" in response.text
    assert "让好奇心 在指尖生长" in response.text
    assert "不止于搭建 · 更创造未来" in response.text
    assert "把每一个奇思妙想 · 都变成作品" in response.text
    assert "与未来同行 · 从第一块积木开始" in response.text
    assert "7 年深耕 · STEAM 教育" in response.text
    assert "乐高启蒙 · 机器人工程 · 编程思维" in response.text
    assert "让每一次好奇 · 都被认真对待" in response.text
    assert "扫码 · 让孩子的未来 提前开始" in response.text
    assert "乐启享" in response.text
    assert "18164173640" in response.text
    assert "宜昌市猇亭区金岭路59-1号" in response.text
    assert "/_site/courses/" in response.text
    assert 'href="/login"' in response.text
    assert 'class="hero-menu-toggle"' in response.text
    assert 'id="heroNav"' in response.text
    assert 'nav-link--external' in response.text
    assert 'href="/competitions.html"' in response.text
    assert 'target="_blank"' in response.text
    assert "森林老师" in response.text
    assert "senlin-c1n.pages.dev" in response.text
    assert "student-001" in response.text
    assert "student-150" in response.text
    assert "honors/3eec15d34062bf6ef680de67fb74689f" in response.text
    assert "honors/3c4b1c9a" not in response.text
    assert "home/1.webp" in response.text
    assert "showreel-birthday.mp4" in response.text
    assert "ai-camp-clip.mp4" in response.text
    assert "showreel-dance.mp4" not in response.text
    assert "codebn.cn" not in response.text
    assert "honor-carousel" in response.text
    assert "campus-carousel" in response.text
    assert "imageLightbox" in response.text
    assert "site-footer" in response.text
    assert "鄂ICP" in response.text
    assert "camp2.webp" in response.text
    assert "cinema-wall" in response.text
    assert "texture.png" not in response.text



def test_homepage_typewriter_starts_within_the_normal_rotation_cycle(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    script = client.get("/_site/homepage/app.js").text

    assert script.count("setTimeout(tick, 120);") >= 2
    assert script.count("const holdDelay = 850;") >= 2
    assert "let unitIndex = 0;" in script
    assert "let uIdx = 0;" in script
    assert script.count("let deleting = false;") >= 2
    assert "unitIndex -= 1" in script
    assert "uIdx -= 1" in script
    assert "const typeDelay = 48;" in script
    assert "const typeDelay = 44;" in script
    assert "setTimeout(tick, 30000);" not in script
    assert "setTimeout(tick, 24000);" not in script


def test_homepage_static_asset_route_serves_local_css(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_site/homepage/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_homepage_static_asset_route_serves_local_logo(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_site/homepage/media/logo.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")


def test_homepage_static_asset_route_wires_mobile_nav_toggle(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    script = client.get("/_site/homepage/app.js").text

    assert "hero-menu-toggle" in script
    assert "hero-nav-open" in script
    assert "is-menu-open" in script
    assert "window.matchMedia('(max-width: 1023.98px)')" in script


def test_public_course_legacy_routes_are_not_claimed_by_logged_in_spa(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, profile_name="admin", username="principal", token="admin-token")
    _store_teacher_profile(tmp_path)
    _store_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    for profile_name in ("admin", "teacher", "student"):
        client.cookies.set("mirror_profile", profile_name)

        courses = client.get("/courses.html", follow_redirects=False)
        detail = client.get("/course-detail.html?id=lego-large", follow_redirects=False)

        assert courses.status_code == 200
        assert detail.status_code == 200
        assert "课程体系 - 乐启享编程教育" in courses.text
        assert "课程详情 - 乐启享编程教育" in detail.text
        assert 'href="/#hero"' in courses.text
        assert 'href="/#hero"' in detail.text
        assert "/background/course-management" not in courses.text
        assert "/code-classroom/classroom-index" not in courses.text
        assert courses.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert detail.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"


def test_competitions_page_is_localized_and_has_no_form_fields(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/competitions.html")

    assert response.status_code == 200
    assert 'class="navbar"' in response.text
    assert 'id="home" class="hero"' in response.text
    assert 'class="hero-media"' in response.text
    assert "/_site/homepage/media/hero-cloudfront-20260331-045634.mp4" in response.text
    assert "探索科技未来" in response.text
    assert "科技竞赛项目" in response.text
    assert "科技特长生" in response.text
    assert "contact-static-section" in response.text
    assert "competitionContactTitle" in response.text
    assert "data-contact-title-phrases" in response.text
    assert "乐启享 版权所有" in response.text
    assert "乐慧享" not in response.text
    assert "慧享编程" not in response.text
    assert "/_site/competitions/styles.css" in response.text
    assert "/_site/competitions/images/yichang-yizhong1.webp" in response.text
    assert "/_site/competitions/images/qr-liuteacher.png" in response.text
    assert 'class="hero-stage"' not in response.text
    assert 'class="hero-header"' not in response.text
    assert "<form" not in response.text
    assert "<input" not in response.text
    assert "<textarea" not in response.text


def test_competitions_static_asset_route_wires_mobile_nav_toggle(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    script = client.get("/_site/competitions/app.js").text

    assert "nav-open" in script
    assert "nav-toggle" in script
    assert "nav-menu" in script
    assert "lazy-load" in script
    assert "hero-menu-toggle" not in script


def test_competitions_page_preserves_canonical_interactions(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    page = client.get("/competitions.html").text
    script = client.get("/_site/competitions/app.js").text

    assert 'onclick="showCompetitionDetail(' in page
    assert 'id="loadMoreCompetitions"' in page
    assert "展开全部赛事" in page
    assert 'id="loadMoreCertification"' in page
    assert 'id="certificationDetails"' in page
    assert 'id="loadMoreStudents"' in page
    assert 'id="moreStudents"' in page
    assert "展开全部学生案例" in page
    assert 'href="https://kejitechangsheng.com/category/quanguo"' in page
    assert 'target="_blank"' in page
    assert page.count('class="competition-card"') == 12
    assert page.count('class="student-card"') == 6
    assert page.count('class="detail-card"') == 4
    assert page.count('class="school-item"') == 7
    assert "function createCompetitionModal" in page
    assert "competition-modal-overlay" in page
    assert "competition-detail-modal modal modal-scroll" in page
    assert "role', 'dialog'" in page
    assert "function scrollToContactForm" in page
    assert "function setupLoadMore" in script
    assert "function setupCompetitionDetails" in script
    assert "收起更多赛事" in script
    assert "收起详细信息" in script
    assert "收起学生案例" in script


def test_frontend_route_uses_captured_html_when_available(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_student_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html="<html><body>captured classroom</body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "student")

    response = client.get("/code-classroom")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "captured classroom" in response.text
    assert "unhandledrejection" in response.text
    assert "editor_opentype" in response.text


def test_student_code_classroom_snapshot_is_served_without_scripts(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_student_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom",
        status=200,
        html="<html><body><div>teacher snapshot</div><script>window.teacher = true;</script></body></html>",
        captured_xhr_count=0,
    )
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html=(
            "<html><body>"
            '<div class="el-image logo_img"><div class="el-image__error">加载失败</div><!----></div>'
            '<div class="el-message-box__wrapper">密码提示</div>'
            '<div class="v-modal"></div>'
            "<div>student snapshot</div>"
            "<script>window.shouldNotRun = true;</script>"
            "</body></html>"
        ),
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "student")

    response = client.get("/code-classroom")

    assert response.status_code == 200
    assert "student snapshot" in response.text
    assert "window.shouldNotRun" not in response.text
    assert "el-message-box__wrapper" not in response.text
    assert 'class="v-modal"' not in response.text
    assert "加载失败" not in response.text
    assert "nanxueshengtouxiang-min.png" in response.text


def test_teacher_classroom_index_prefers_teacher_snapshot_when_authorized(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html="<html><body><div>teacher classroom index</div><script>window.teacher = true;</script></body></html>",
        captured_xhr_count=0,
    )
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom/classroom-index",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html="<html><body><div>student classroom index</div><script>window.student = true;</script></body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/code-classroom/classroom-index",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert "teacher classroom index" in response.text
    assert "student classroom index" not in response.text


def test_login_redirect_capture_is_skipped_for_route_like_pages(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom/prepare-lessons",
        final_url="https://steam.fun/login?redirect=prepare-lessons",
        status=200,
        html="<html><body>bad login snapshot</body></html>",
        captured_xhr_count=1,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/code-classroom/prepare-lessons")

    assert response.status_code == 200
    assert "shell" in response.text
    assert "bad login snapshot" not in response.text


def test_excluded_school_home_subroute_redirects_teacher_to_workspace(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/school-home-page",
        final_url="https://steam.fun/school-home-page",
        status=200,
        html="<html><body><div>teacher home capture</div></body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page/orderpay", follow_redirects=False)

    assert response.status_code in {302, 303, 307}
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_duplicate_school_home_class_route_redirects_to_normalized_path(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/school-home-page/class-management1/class-management1?t=1",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/school-home-page/class-management1?t=1"


def test_teacher_auth_bootstrap_uses_curated_nested_permissions(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    auth_tree_payload = {
        "children": [
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "userResource": {"alias": "student-query", "name": "查询", "sort": 0},
                            }
                        ],
                        "userResource": {"alias": "students-management1", "name": "学员管理", "sort": 1},
                    }
                ],
                "userResource": {"alias": "tchCenter", "name": "教务中心", "sort": 5},
            }
        ]
    }
    _store_teacher_profile(
        tmp_path,
        auth_tree=json.dumps(auth_tree_payload, ensure_ascii=False),
        permissions=_flatten_permission_tree_for_storage(auth_tree_payload["children"]),
    )
    store = MirrorStore(tmp_path)

    script = server_module._build_teacher_auth_bootstrap(store)

    assert script is not None
    start = script.index("var data=") + len("var data=")
    end = script.index(";try{localStorage.setItem('vuex',JSON.stringify(data));}catch(e){}")
    bootstrap_payload = json.loads(script[start:end].replace("<\\/", "</"))

    permissions = bootstrap_payload["user"]["permisionList"]
    assert permissions[0]["alias"] == "tchCenter"
    assert permissions[0]["children"][0]["alias"] == "students-management1"
    assert permissions[0]["children"][0]["children"][0]["alias"] == "currentStudent"
    assert permissions[0]["children"][0]["children"][0]["children"][0]["alias"] == "studentDetails"
    admin_permissions = bootstrap_payload["user"]["adminpermisionList"]
    assert admin_permissions[0]["permission_key"] == "tchCenter"
    assert admin_permissions[0]["children"][0]["permission_key"] == "students-management1"
    assert admin_permissions[0]["children"][0]["children"][0]["permission_key"] == "currentStudent"
    serialized = json.dumps(admin_permissions, ensure_ascii=False)
    assert "student-query" not in serialized
    assert "orderpay" not in serialized


def test_fresh_auth_data_returns_curated_teacher_auth_tree(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, auth_tree='{"children":[{"userResource":{"alias":"students-management1"}}]}')
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/auth/sch/freshAuthData?t=123",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json()["content"]["flag"] is True
    message = json.loads(response.json()["content"]["message"])
    serialized = json.dumps(message, ensure_ascii=False)
    assert "students-management1" in serialized
    assert "teachplan1" in serialized
    assert "school-user-list" not in serialized
    assert "orderpay" not in serialized


def test_fresh_auth_data_limits_auth_tree_for_core_background_referer(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    auth_tree_payload = _core_background_auth_tree_payload()
    _store_teacher_profile(
        tmp_path,
        auth_tree=json.dumps(auth_tree_payload, ensure_ascii=False),
        permissions=_flatten_permission_tree_for_storage(auth_tree_payload["children"]),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/auth/sch/freshAuthData?t=123",
        headers={
            "Authorization": "Bearer teacher-token",
            "Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum",
        },
    )

    assert response.status_code == 200
    message = response.json()["content"]["message"]
    filtered_auth_tree = json.loads(message)
    assert {node["userResource"]["alias"] for node in filtered_auth_tree["children"]} == {
        "tchCenter",
        "courseCenter",
    }
    serialized = json.dumps(filtered_auth_tree, ensure_ascii=False)
    assert "pageHome" not in serialized
    assert "systemSetting" not in serialized
    assert "classRecord" in serialized
    assert "school-user-list" not in serialized
    assert "school-curriculum" in serialized


def test_local_teacher_login_sets_profile_cookie_for_teacher_like_account(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[{"userResource":{"alias":"school-curriculum"}}]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9001, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9001, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/tch/login",
        json={"userName": "18164173640", "password": "admin-hash", "captchaVerifyParam": ""},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.cookies.get("mirror_profile") == "admin"


def test_local_student_login_auto_provisions_string_token_profile(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    created = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "1399000001",
            "realName": "Local Student Login",
            "sex": "M",
            "parentAPhoneNum": "1399000001",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-07-18",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/student/stu/login",
        json={"userName": "1399000001", "password": "123456", "captchaVerifyParam": ""},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"], str)
    assert payload["content"]
    assert response.cookies.get("mirror_profile") == f"local_student_{created['id']}"

    profile = store.get_profile(f"local_student_{created['id']}")
    assert profile is not None
    assert isinstance(profile["login_content"], str)
    assert profile["login_content"] == payload["content"]
    assert profile["vuex_state"]["user"]["token"] == payload["content"]


def test_local_teacher_login_accepts_plaintext_password_for_hashed_profile(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="4QrcOUm6Wau+VuBX8g+IPg==",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[{"userResource":{"alias":"school-curriculum"}}]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9001, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9001, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/tch/login",
        json={"userName": "18164173640", "password": "123456", "captchaVerifyParam": ""},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.cookies.get("mirror_profile") == "admin"


def test_admin_fresh_auth_user_data_falls_back_to_teacher_profile(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    permissions = [
        {
            "name": "课程管理",
            "icon_url": "el-icon-notebook-1",
            "children": [{"name": "课程体系", "permission_key": "school-curriculum"}],
        }
    ]
    _store_teacher_profile(
        tmp_path,
        permissions=permissions,
        user_info={"realname": "Teacher Realname", "userId": 12385},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/api/admin/fresh/auth/user/data?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        data={},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["token"] == "teacher-token"
    assert content["userId"] == 12385
    assert content["userRealname"] == "Teacher Realname"
    serialized = json.dumps(content["authUserPermission"], ensure_ascii=False)
    assert "class-management1" in serialized
    assert "school-curriculum" in serialized
    assert "school-user-list" not in serialized
    assert "orderpay" not in serialized


def test_admin_fresh_auth_user_data_uses_teacher_like_profile_from_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, username="zhaosenlin", token="teacher-token")
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[{"userResource":{"alias":"school-curriculum","name":"课程体系"}}]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9002, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "permisionList": [],
                "adminpermisionList": [{"name": "课程体系", "permission_key": "school-curriculum"}],
                "userInfo": {"id": 9002, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/api/admin/fresh/auth/user/data?t=1",
        headers={"Authorization": "Bearer admin-token"},
        data={},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["token"] == "admin-token"
    assert content["userId"] == 9002
    assert content["userRealname"] == "Admin Realname"
    serialized = json.dumps(content["authUserPermission"], ensure_ascii=False)
    assert "school-user-list" in serialized
    assert "schoolSys" in serialized
    assert "orderpay" not in serialized


def test_admin_fresh_auth_user_data_builds_permissions_from_auth_tree_when_admin_list_empty(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    auth_tree_payload = {
        "children": [
            {
                "children": [
                    {
                        "children": [],
                        "userResource": {"alias": "students-management1", "name": "学员管理", "sort": 1},
                    }
                ],
                "userResource": {"alias": "tchCenter", "name": "教务中心", "sort": 5},
            }
        ]
    }
    _store_teacher_profile(
        tmp_path,
        auth_tree=json.dumps(auth_tree_payload, ensure_ascii=False),
        permissions=_flatten_permission_tree_for_storage(auth_tree_payload["children"]),
        user_info={"realname": "Teacher Realname", "userId": 12385},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/api/admin/fresh/auth/user/data?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        data={},
    )

    assert response.status_code == 200
    permissions = response.json()["content"]["authUserPermission"]
    assert permissions[0]["permission_key"] == "tchCenter"
    assert permissions[0]["children"][0]["permission_key"] == "students-management1"
    assert permissions[0]["children"][0]["name"] == "\u5b66\u5458\u7ba1\u7406"


def test_admin_fresh_auth_user_data_prefers_local_permissions_over_stale_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    auth_tree_payload = {
        "children": [
            {
                "children": [
                    {
                        "children": [],
                        "userResource": {"alias": "class-management1", "name": "班级管理", "sort": 2},
                    }
                ],
                "userResource": {"alias": "tchCenter", "name": "教务中心", "sort": 5},
            }
        ]
    }
    _store_teacher_profile(
        tmp_path,
        auth_tree=json.dumps(auth_tree_payload, ensure_ascii=False),
        permissions=_flatten_permission_tree_for_storage(auth_tree_payload["children"]),
        user_info={"realname": "Teacher Realname", "userId": 12385},
    )
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/api/admin/fresh/auth/user/data?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "token": "teacher-token",
                    "userId": 12385,
                    "userName": "teacher",
                    "userRealname": "Teacher Realname",
                    "authUserPermission": [],
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        request_body=b"",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/api/admin/fresh/auth/user/data?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        data={},
    )

    assert response.status_code == 200
    permissions = response.json()["content"]["authUserPermission"]
    assert permissions[0]["permission_key"] == "tchCenter"
    serialized = json.dumps(permissions, ensure_ascii=False)
    assert "class-management1" in serialized
    assert "teachplan1" in serialized
    assert "orderpay" not in serialized


def test_teacher_fresh_auth_user_data_uses_curated_permissions_for_background_referer(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    auth_tree_payload = _core_background_auth_tree_payload()
    _store_teacher_profile(
        tmp_path,
        auth_tree=json.dumps(auth_tree_payload, ensure_ascii=False),
        permissions=_flatten_permission_tree_for_storage(auth_tree_payload["children"]),
        user_info={"realname": "Teacher Realname", "userId": 12385},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/api/admin/fresh/auth/user/data?t=1",
        headers={
            "Authorization": "Bearer teacher-token",
            "Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum",
        },
        data={},
    )

    assert response.status_code == 200
    permissions = response.json()["content"]["authUserPermission"]
    assert {node["permission_key"] for node in permissions} == {"tchCenter", "courseCenter"}
    teach_center = next(node for node in permissions if node["permission_key"] == "tchCenter")
    assert {child["permission_key"] for child in teach_center["children"]} == {
        "students-management1",
        "class-management1",
        "teachplan1",
        "classRecord",
    }
    serialized = json.dumps(permissions, ensure_ascii=False)
    assert "classRecord" in serialized
    assert "systemSetting" not in serialized
    assert "school-user-list" not in serialized
    assert "school-curriculum" in serialized


def test_admin_subject_list_falls_back_to_captured_teacher_subjects(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/subject/list?campusId=851",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "campusSubjectList": [
                        {"id": 2, "name": "Scratch", "sort_num": 2},
                        {"id": 1, "name": "Jrcode", "sort_num": 1},
                    ]
                },
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/admin/get/getAdminSubjectListWithOutPageInfo?t=1&subject_state=1",
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum"},
    )

    assert response.status_code == 200
    assert response.json()["content"]["subject_list"] == [
        {"id": 1, "name": "Jrcode", "sort_num": 1},
        {"id": 2, "name": "Scratch", "sort_num": 2},
    ]


def test_admin_curriculum_list_falls_back_to_captured_teacher_curriculum_list(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url=(
            "https://steam.fun/api/get/campus/curriculum/list/by/page"
            "?campusIds=%5B851%5D&subjectId=1&teaching_type=&curriculum_type=&page_no=1&page_size=100"
        ),
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "campusAuthList": [
                        {
                            "id": 9001,
                            "curriculum_id": 2002,
                            "educational_institution_id": 834,
                            "educational_institution_campus_id": 851,
                            "campusName": "默认校区",
                            "price": 0,
                            "curriculumInfo": {
                                "id": 2002,
                                "subject_id": 2,
                                "sort_num": 20,
                                "title": "Scratch 体验课",
                                "subjectName": "Scratch",
                                "teaching_type": 1,
                                "curriculum_type": 1,
                                "img_url": "https://example.com/scratch.png",
                                "curriculum_desc": "scratch",
                                "number_of_courses": 4,
                                "state": "正常",
                                "difficulty": 1,
                                "for_grade": "中班",
                                "suggested_duration": "1h",
                            },
                        },
                        {
                            "id": 9002,
                            "curriculum_id": 1001,
                            "educational_institution_id": 834,
                            "educational_institution_campus_id": 851,
                            "campusName": "默认校区",
                            "price": 199,
                            "curriculumInfo": {
                                "id": 1001,
                                "subject_id": 1,
                                "sort_num": 10,
                                "title": "Jrcode 常规课",
                                "subjectName": "Jrcode",
                                "teaching_type": 1,
                                "curriculum_type": 2,
                                "img_url": "https://example.com/jrcode.png",
                                "curriculum_desc": "jrcode",
                                "number_of_courses": 8,
                                "state": "正常",
                                "difficulty": 2,
                                "for_grade": "大班",
                                "suggested_duration": "1.5h",
                            },
                        },
                    ],
                },
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/admin/get/school/curriculum/list"
            "?t=1&check_state=2&subject_id=1&teaching_type=1&curriculum_type=2&page_no=1&page_size=20"
        ),
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum"},
    )

    assert response.status_code == 200
    assert response.json()["content"]["total"] == 1
    assert response.json()["content"]["page_no"] == 1
    assert response.json()["content"]["page_size"] == 20
    assert response.json()["content"]["curriculum_list"][0] == {
        "id": 1001,
        "subject_id": 1,
        "sort_num": 10,
        "title": "Jrcode 常规课",
        "subjectName": "Jrcode",
        "teaching_type": 1,
        "curriculum_type": 2,
        "img_url": "/_external/example.com/jrcode.png",
        "curriculum_desc": "jrcode",
        "number_of_courses": 8,
        "state": "正常",
        "difficulty": 2,
        "for_grade": "大班",
        "suggested_duration": "1.5h",
        "campusAuthId": 9002,
        "price": 199,
        "campusName": "默认校区",
        "created_time": None,
        "educational_institution_id": 834,
        "educational_institution_campus_id": 851,
        "check_state": None,
        "is_effective": True,
        "total_storage": 0,
        "totalStorage": 0,
        "storage": 0,
        "storage_size": 0,
        "storageSize": 0,
        "lessionTotalStorage": 0,
        "lessonTotalStorage": 0,
        "useStorage": 0,
        "use_storage": 0,
        "usedStorage": 0,
        "occupySpace": 0,
        "remainTraffic": 0,
        "remain_storage": 0,
        "remainStorage": 0,
    }


def test_replay_api_decompresses_brotli_json_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    payload = {"success": True, "content": {"userList": []}}
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/user/list?t=1&campusId=851",
        status=200,
        headers={
            "content-type": "application/json; charset=utf-8",
            "content-encoding": "br",
        },
        body=brotli.compress(json.dumps(payload).encode("utf-8")),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/campus/user/list?t=99&campusId=851",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {"userList": []},
        "error": {"message": "", "code": ""},
    }


def test_homepage_payload_is_hydrated_for_success_payloads(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        user_info={"realName": "Mirror Teacher", "headimgUrl": "https://cdn.example.com/teacher.png"},
        school_info={"id": 834, "name": "Mirror School", "eduCampusId": 851},
    )
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/homepage?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps({"success": True, "content": {"schoolInfo": None}}).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/homepage?t=99",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] == {"message": "", "code": ""}
    assert payload["content"]["schoolInfo"]["id"] == 834
    assert payload["content"]["schoolInfo"]["name"] == "Mirror School"
    assert payload["content"]["schoolInfo"]["eduCampusId"] == 851
    assert payload["content"]["userInfo"]["realName"] == "Mirror Teacher"
    assert payload["content"]["userInfo"]["headimgUrl"] == "/_external/cdn.example.com/teacher.png"
    assert payload["content"]["homepageData"]["homepage"]["logo_img_url"] == "/_external/cdn.example.com/teacher.png"
    assert (
        payload["content"]["homepageData"]["homepage"]["modal_img_url"]
        == "/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
    )
    assert payload["content"]["imgUrl"] == "/_external/cdn.example.com/teacher.png"


def test_student_homepage_payload_is_hydrated_from_student_profile(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, school_info={"id": 834, "name": "Mirror School", "eduCampusId": 851})
    _store_runtime_student_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "student",
        method="GET",
        url="https://steam.fun/api/get/homepage?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {"schoolInfo": None, "userInfo": None, "homepageData": None},
                "error": {"message": "", "code": ""},
            }
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/homepage?t=2",
        headers={"Authorization": "Bearer student-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["content"]["schoolInfo"]["name"] == "Mirror School"
    assert payload["content"]["schoolInfo"]["eduCampusId"] == 851
    assert payload["content"]["schoolInfo"]["theme_color"] == "#1778FF"
    assert payload["content"]["userInfo"]["stuUserInfo"]["name"] == "lbschenmuran"
    assert payload["content"]["userInfo"]["stuUserInfo"]["stuUserInfo"]["realName"] == "Chen Muran"
    assert (
        payload["content"]["userInfo"]["userImageUrl"]
        == "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"
    )
    assert (
        payload["content"]["homepageData"]["homepage"]["logo_img_url"]
        == "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"
    )
    assert (
        payload["content"]["homepageData"]["homepage"]["modal_img_url"]
        == "/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
    )
    assert (
        payload["content"]["imgUrl"]
        == "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"
    )


def test_replay_api_distinguishes_post_body_variants(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/currMat/detail?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps({"success": True, "content": {"name": "ppt-1"}}).encode("utf-8"),
        request_body=b'{"id":1}',
    )
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/currMat/detail?t=2",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps({"success": True, "content": {"name": "ppt-2"}}).encode("utf-8"),
        request_body=b'{"id":2}',
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    first = client.post(
        "/java-api/school/currMat/detail?t=99",
        headers={"Authorization": "Bearer teacher-token"},
        json={"id": 1},
    )
    second = client.post(
        "/java-api/school/currMat/detail?t=100",
        headers={"Authorization": "Bearer teacher-token"},
        json={"id": 2},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["content"]["name"] == "ppt-1"
    assert second.json()["content"]["name"] == "ppt-2"


def test_replay_api_currmat_detail_falls_back_to_currmat_id_only_variant(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/currMat/detail",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps({"success": True, "content": {"name": "fallback-hit"}}).encode("utf-8"),
        request_body=b'{"currMatId":39525}',
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/currMat/detail?t=100",
        headers={"Authorization": "Bearer teacher-token"},
        json={"currMatId": 39525, "tchPlanId": 999999},
    )

    assert response.status_code == 200
    assert response.json()["content"]["name"] == "fallback-hit"


def test_currmat_detail_post_uses_requested_material_for_template_urls(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=501&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 7002,
                            "subject_id": 2,
                            "curriculum_id": 501,
                            "title": "Requested Lesson",
                            "ppt_url": "https://cdn.example.com/requested/index.html",
                            "teach_template_url": "https://cdn.example.com/requested/teach.sb3",
                            "exampal_work_url": "https://cdn.example.com/requested/example.sb3",
                            "home_template_url": "https://cdn.example.com/requested/home.sb3",
                        },
                        {
                            "id": 9001,
                            "subject_id": 2,
                            "curriculum_id": 501,
                            "title": "Default Lesson",
                            "ppt_url": "https://cdn.example.com/default/index.html",
                            "video_url": "https://cdn.example.com/default/video.mp4",
                            "stu_note_url": "https://cdn.example.com/default/note.pdf",
                            "teach_template_url": "https://cdn.example.com/default/teach.sb3",
                            "exampal_work_url": "https://cdn.example.com/default/example.sb3",
                            "home_template_url": "https://cdn.example.com/default/home.sb3",
                            "other_meterial_url": "https://cdn.example.com/default/poster.png",
                        },
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/currMat/detail?t=100",
        headers={"Authorization": "Bearer teacher-token"},
        json={"currMatId": 7002, "tchPlanId": 88001},
    )

    assert response.status_code == 200
    payload = response.json()["content"]
    assert payload["curriculumMaterial"]["id"] == 7002
    assert payload["tchPlanInfo"]["classWorkUrl"] == "/_external/cdn.example.com/requested/teach.sb3"
    assert payload["tchPlanInfo"]["exampleWorkUrl"] == "/_external/cdn.example.com/requested/example.sb3"
    assert payload["tchPlanInfo"]["homeworkWorkUrl"] == "/_external/cdn.example.com/requested/home.sb3"


def test_static_javascript_is_patched_for_missing_error_guard(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    js_path = tmp_path / "origin" / "steam.fun" / "js" / "app.js"
    js_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.write_text("if(e.data.error.message||e.data.error.code){return true}", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/js/app.js")

    assert response.status_code == 200
    assert "(((e||{}).data||{}).error||{}).message" in response.text
    assert "(((e||{}).data||{}).error||{}).code" in response.text


def test_static_javascript_repairs_known_route_watcher_syntax_regression(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    js_path = tmp_path / "origin" / "steam.fun" / "js" / "app.js"
    js_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.write_text(
        'function demo(e,t){if(this.$nextTick(()=>{const t=document.getElementById("home_top");'
        'e&&(e.path.includes("/competitionCenter")||e.path.includes("/community/"))?'
        't&&(t.style.display="none"):t&&(t.style.display="block")}),e&&"/"!==e.path||e.name))'
        '{if(e.name===t.name)return!1;this.handleRouteReady()}if(e.data.error.message||e.data.error.code){return true}}',
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/js/app.js")

    assert response.status_code == 200
    assert 'e.name)){if(e.name===t.name)return!1;this.handleRouteReady()}' not in response.text
    assert 'e.name){if(e.name===t.name)return!1;this.handleRouteReady()}' in response.text
    assert "(((e||{}).data||{}).error||{}).message" in response.text
    assert "(((e||{}).data||{}).error||{}).code" in response.text


def test_static_html_rewrites_same_origin_absolute_urls_to_local_paths(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    html_path = tmp_path / "origin" / "steam.fun" / "lessonWork" / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        '<a href="https://steam.fun/login?redirect=abc">login</a>'
        '<script>const shareUrl="https://steam.fun/lessonWork/index.html?workId=1";</script>'
        '<img src="https://wugecdn.steam.fun/resources/static/example.png">',
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/lessonWork/index.html")

    assert response.status_code == 200
    assert 'href="/login?redirect=abc"' in response.text
    assert '"https://steam.fun/lessonWork/index.html?workId=1"' not in response.text
    assert '"/lessonWork/index.html?workId=1"' in response.text
    assert '/_external/wugecdn.steam.fun/resources/static/example.png' in response.text


def test_static_javascript_without_rewrite_markers_skips_inline_rewrite(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)
    js_path = tmp_path / "origin" / "steam.fun" / "js" / "runtime.js"
    js_path.parent.mkdir(parents=True, exist_ok=True)
    original = "window.__mirror_runtime__=1;" + ("var n=1;" * 200000)
    js_path.write_text(original, encoding="utf-8")

    def _fail_rewrite(_: str) -> str:
        raise AssertionError("rewrite_external_urls should not run for plain runtime bundles")

    monkeypatch.setattr(server_module, "rewrite_external_urls", _fail_rewrite)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/js/runtime.js")

    assert response.status_code == 200
    assert response.text == original


def test_large_textual_asset_is_streamed_without_rewrite(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    js_path = tmp_path / "origin" / "steam.fun" / "js" / "big.js"
    js_path.parent.mkdir(parents=True, exist_ok=True)
    content = "https://wugecdn.steam.fun/original.js;" + ("a" * (5 * 1024 * 1024))
    js_path.write_text(content, encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/js/big.js")

    assert response.status_code == 200
    assert response.text.startswith("https://wugecdn.steam.fun/original.js;")
    assert "/_external/" not in response.text[:200]


def test_rewrite_body_returns_decompressed_payload_when_large_encoded_asset_skips_rewrite() -> None:
    original = b"https://wugecdn.steam.fun/original.js;" + (b"a" * (server_module.INLINE_REWRITE_MAX_BYTES + 64))
    encoded = gzip.compress(original)

    body = server_module._maybe_rewrite_body(
        encoded,
        "application/javascript",
        {"content-encoding": "gzip"},
    )

    assert body == original


def test_rewrite_body_falls_back_to_original_bytes_on_memory_error(monkeypatch) -> None:
    body = b"https://wugecdn.steam.fun/original.js"

    def _raise_memory_error(_: str) -> str:
        raise MemoryError

    monkeypatch.setattr(server_module, "rewrite_external_urls", _raise_memory_error)

    assert server_module._maybe_rewrite_body(body, "application/javascript") == body


def test_rewrite_body_injects_legacy_ispring_text_nowrap_guard() -> None:
    body = (
        "<html><head><title>course</title></head><body>"
        "<script>"
        "loadHandler&&loadHandler(0,'<div style=\"width:0px;\">"
        "<span id=\"txt3_daaf66\" style=\"left:73.6px;top:46.754px;\">"
        "小病毒大威力"
        "</span></div>','{\"s\":[]}');"
        "</script>"
        "</body></html>"
    ).encode("utf-8")

    rewritten = server_module._maybe_rewrite_body(body, "text/html; charset=utf-8").decode("utf-8")

    assert "__localLegacyIspringTextGuard" in rewritten
    assert 'span[id^="txt"]' in rewritten
    assert "node.style.whiteSpace='nowrap'" in rewritten


def test_rewrite_body_injects_classroom_loading_feedback_guard() -> None:
    body = (
        "<html><head><title>course</title></head><body>"
        "<div id='app'></div>"
        "</body></html>"
    ).encode("utf-8")

    rewritten = server_module._maybe_rewrite_body(body, "text/html; charset=utf-8").decode("utf-8")

    assert "__localClassroomLoadingUi" in rewritten
    assert "local-course-loading-overlay" in rewritten
    assert "var mountTarget=document.body||document.documentElement;" in rewritten
    assert "iframe.contentDocument&&iframe.contentDocument.readyState==='complete'" in rewritten
    assert "setTimeout(function(){hideLoading(true);},4500);" in rewritten
    assert "document.addEventListener('pointerdown',maybePulseFromInteraction,true);" in rewritten
    assert "if(now-lastInteractionPulseAt<800){return;}" in rewritten
    assert "正在加载资源" in rewritten
    assert "正在准备课件内容" in rewritten


def test_rewrite_body_does_not_inject_core_route_cleanup_guard() -> None:
    body = (
        "<html><head><title>course</title></head><body>"
        "<nav><a href='/competitionCenter/questionBankCenter/platform'>??</a></nav>"
        "</body></html>"
    ).encode("utf-8")

    rewritten = server_module._maybe_rewrite_body(body, "text/html; charset=utf-8").decode("utf-8")

    assert "__localCoreRouteCleanup" not in rewritten
    assert "allowedSubmenus" not in rewritten
    assert "allowedMenuItems" not in rewritten


def test_teacher_teach_deep_link_bootstraps_session_context(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 39525,
                            "subject_id": 1,
                            "curriculum_id": 3429,
                            "title": "西瓜风扇大作战",
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999")

    assert response.status_code == 200
    assert "sessionStorage.setItem('Classroom',JSON.stringify(data.Classroom))" in response.text
    assert '"curriculum_meterial_id": 39525' in response.text
    assert '"id": 999999' in response.text
    assert "teacherPlanList" in response.text


def test_teacher_prepare_deep_link_prefers_teacher_classroom_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html="<html><body><div>teacher classroom capture</div><script>window.teacher = true;</script></body></html>",
        captured_xhr_count=0,
    )
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom/prepare-lessons/prepare/ppt",
        final_url="https://steam.fun/login?redirect=prepare-ppt",
        status=200,
        html="<html><body>student login capture</body></html>",
        captured_xhr_count=1,
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 39525,
                            "subject_id": 1,
                            "curriculum_id": 3429,
                            "title": "prepare material",
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            }
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=39525&tchPlanId=999999")

    assert response.status_code == 200
    assert "teacher classroom capture" in response.text
    assert "student login capture" not in response.text
    assert "localStorage.setItem('vuex',JSON.stringify(data))" in response.text
    assert "sessionStorage.setItem('Classroom',JSON.stringify(data.Classroom))" in response.text


def test_teacher_prepare_root_prefers_teacher_classroom_capture_and_default_session(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html="<html><body><div>teacher classroom capture</div></body></html>",
        captured_xhr_count=0,
    )
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom/prepare-lessons",
        final_url="https://steam.fun/login?redirect=prepare-lessons",
        status=200,
        html="<html><body>student login capture</body></html>",
        captured_xhr_count=1,
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 39525,
                            "subject_id": 1,
                            "curriculum_id": 3429,
                            "title": "prepare root material",
                            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
                            "stu_note_url": "https://wugecdn.steam.fun/course/handout.pdf",
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            }
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/code-classroom/prepare-lessons")

    assert response.status_code == 200
    assert "teacher classroom capture" in response.text
    assert "student login capture" not in response.text
    assert "sessionStorage.setItem('Classroom',JSON.stringify(data.Classroom))" in response.text
    assert '"curriculum_meterial_id": 39525' in response.text


def test_teacher_myclass_root_prefers_teacher_classroom_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/code-classroom",
        final_url="https://steam.fun/code-classroom/classroom-index",
        status=200,
        html="<html><body><div>teacher myclass capture</div></body></html>",
        captured_xhr_count=0,
    )
    store.store_route_capture(
        profile_name="student",
        route="/code-classroom/myClass",
        final_url="https://steam.fun/login?redirect=myClass",
        status=200,
        html="<html><body>student login capture</body></html>",
        captured_xhr_count=1,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/code-classroom/myClass")

    assert response.status_code == 200
    assert "teacher myclass capture" in response.text
    assert "student login capture" not in response.text
    assert "localStorage.setItem('vuex',JSON.stringify(data))" in response.text


def test_student_myclass_route_bootstraps_student_vuex_and_schoolinfo(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, school_info={"id": 834, "name": "Mirror School", "eduCampusId": 851})
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/code-classroom/myClass",
        headers={"Authorization": "Bearer student-token"},
    )

    assert response.status_code == 200
    assert "localStorage.setItem('vuex',JSON.stringify(data))" in response.text
    assert "sessionStorage.setItem('schoolInfo',JSON.stringify(data))" in response.text
    assert '"identity":2' in response.text
    assert '"userImageUrl":"/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"' in response.text
    assert '"theme_color":"#1778FF"' in response.text


def test_local_api_fallback_returns_empty_teacher_plan_list(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/getTeachingPlanList?page_no=2&page_size=3&start_date=2026-05-13+00:00:00&end_date=2026-05-13+23:59:59",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {"teachingPlan": [], "total": 0, "page_no": 2, "page_size": 3},
        "error": {"message": "", "code": ""},
    }


def test_local_api_fallback_returns_teacher_user_info_for_course_packages(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        user_info={"realName": "Teacher Li", "userId": 12385},
        school_info={"eduDomain": "school.steam.fun"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/api/get/user/info/by/user/code?usercode=22489f72-14a3-4020-8f5f-374bd6ec3eba")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {"username": "Teacher Li", "domain": "school.steam.fun"},
        "error": {"message": "", "code": ""},
    }


def test_local_api_currmat_detail_defaults_to_local_teacher_material(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=3429&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "curriculumMaterialList": [
                        {
                            "id": 39525,
                            "subject_id": 1,
                            "curriculum_id": 3429,
                            "title": "default material",
                            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
                            "stu_note_url": "https://wugecdn.steam.fun/course/handout.pdf",
                            "teach_template_url": "https://wugecdn.steam.fun/course/template.sb3",
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            }
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/currMat/detail?t=100",
        headers={"Authorization": "Bearer teacher-token"},
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["content"]["curriculumMaterial"]["id"] == 39525
    assert payload["content"]["curriculumMaterial"]["title"] == "default material"


def test_replay_api_curriculum_material_spelling_alias_hits_legacy_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/prepare/get/currculumMaterialList?curriculum_id=793&page_no=1&page_size=200",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {"curriculumMaterialList": [{"id": 1, "title": "legacy-material"}]},
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/prepare/get/curriculumMaterialList?curriculum_id=793",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json()["content"]["curriculumMaterialList"][0]["title"] == "legacy-material"


def test_replay_api_infers_teacher_profile_from_referer(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/curriculum/list/by/page?campusIds=%5B851%5D&subjectId=2&teaching_type=&curriculum_type=&page_no=1&page_size=20",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {"campusAuthList": [{"curriculum_id": 793}]},
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/campus/curriculum/list/by/page?campusIds=[851]&subjectId=2&teaching_type=&curriculum_type=&page_no=1&page_size=20",
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum"},
    )

    assert response.status_code == 200
    assert response.json()["content"]["campusAuthList"][0]["curriculum_id"] == 793


def test_replay_api_treats_course_management_referer_as_teacher_profile(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/curriculum/list/by/page?campusIds=%5B851%5D&subjectId=2&teaching_type=&curriculum_type=&page_no=1&page_size=20",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {"campusAuthList": [{"curriculum_id": 793}]},
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/campus/curriculum/list/by/page?campusIds=[851]&subjectId=2&teaching_type=&curriculum_type=&page_no=1&page_size=20",
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum"},
    )

    assert response.status_code == 200
    assert response.json()["content"]["campusAuthList"][0]["curriculum_id"] == 793


def test_local_curriculum_page_fallback_synthesizes_missing_page_from_cached_catalog(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/campus/curriculum/list/by/page?campusIds=[851]&subjectId=&teaching_type=&curriculum_type=&page_no=2&page_size=1",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["total"] == 2
    assert content["page_no"] == 2
    assert content["page_size"] == 1
    assert content["campusAuthList"][0]["curriculumInfo"]["id"] == 901
    assert content["campusAuthList"][0]["subjectName"] == "Python"
    assert content["campusAuthList"][0]["curriculumInfo"]["total_storage"] == 0
    assert content["campusAuthList"][0]["curriculumInfo"]["totalStorage"] == 0
    assert content["campusAuthList"][0]["curriculumInfo"]["useStorage"] == 0
    assert content["campusAuthList"][0]["curriculumInfo"]["remainTraffic"] == 0


def test_local_xm_order_list_fallback_returns_empty_finance_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/xm/getXmOrderList?campusIdArr=[851]&type=[]&state=[%221%22,%222%22]&page_no=3&page_size=10",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "xmOrderListObj": [],
            "finalAmountSum": 0,
            "unpaidAmountSum": 0,
            "total": 0,
            "page_no": 3,
            "page_size": 10,
        },
        "error": {"message": "", "code": ""},
    }


def test_local_header_set_fallback_returns_finance_column_defaults(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getHeaderSet?table_type=TCH_XMORDERINFO",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    header_list = response.json()["content"]["headerList"]
    assert [row["code"] for row in header_list] == ["3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
    assert header_list[0]["prop"] == "orderType"
    assert header_list[-1]["headDesc"] == "订单状态"


def test_local_lesson_cost_fallback_returns_empty_paged_table(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/lessonHourRecord/selectLessonCost?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"eduCampusId": 851, "pageRequest": {"pageNum": 2, "pageSize": 15}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "pageNum": 2,
            "pageSize": 15,
            "totalSize": 0,
            "totalPages": 0,
            "content": [],
            "records": [],
            "rows": [],
            "list": [],
            "totalContent": {"totalCostMoney": 0, "totalLessonHourNum": 0},
        },
        "error": {"message": "", "code": ""},
    }


def test_local_order_pay_detail_fallback_returns_empty_paged_table(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/orderPayRecord/selectOrderPayDetail?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"eduCampusId": 851, "pageRequest": {"pageNum": 4, "pageSize": 12}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "pageNum": 4,
            "pageSize": 12,
            "totalSize": 0,
            "totalPages": 0,
            "content": [],
            "records": [],
            "rows": [],
            "list": [],
            "totalContent": {"totalIncome": 0, "totalExpenses": 0},
        },
        "error": {"message": "", "code": ""},
    }


def test_local_competition_source_info_fallback_uses_cached_source_catalog(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_competition_source_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/exam/getBankSourceInfo?source_id=4",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    source_info = response.json()["content"]["sourceInfo"]
    assert source_info["id"] == 4
    assert source_info["title"] == "蓝桥杯"
    assert source_info["realExamNum"] == 435
    assert source_info["match_img_url"].startswith("/_external/")


def test_platform_rights_ignores_stale_invalid_token_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "public",
        method="POST",
        url="https://steam.fun/java-api/school/edu/getPlatformRights?t=1",
        status=401,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": False,
                "content": {"code": "InvalidToken", "message": "异地登录"},
                "error": {"code": "InvalidToken", "message": "异地登录"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        request_body=b"",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/edu/getPlatformRights?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["error"] == {"message": "", "code": ""}




def test_school_user_list_route_rejects_teacher_role(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, username="zhaosenlin", token="teacher-token")
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/school-home-page/school-user-list",
        final_url="https://steam.fun/school-home-page/school-user-list",
        status=200,
        html="<html><body><div>school user list page</div></body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page/school-user-list", follow_redirects=False)

    assert response.status_code in {302, 303, 307}
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_school_user_list_supports_local_teacher_account_crud_endpoints(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        username="zhaosenlin",
        token="teacher-token",
        user_info={"id": 12385, "userId": 12385, "realName": "Teacher Li", "realname": "Teacher Li"},
        school_info={"eduCampusId": 851, "name": "Mirror School"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    role_response = client.get(
        "/java-api/auth/sch/eduRole/queryListNoCheck?t=1&pageNum=1&pageSize=100",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert role_response.status_code == 200
    role_rows = role_response.json()["content"]
    assert isinstance(role_rows, list)
    assert role_rows
    assert any(row.get("tchState") for row in role_rows)

    list_response = client.post(
        "/api/admin/get/auth/user/list?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduCampusId": 851,
            "realName": "",
            "name": "",
            "phoneNum": "",
            "state": "??",
            "roleId": "",
            "pageRequest": {"pageNum": 1, "pageSize": 10},
        },
    )
    assert list_response.status_code == 200
    list_content = list_response.json()["content"]
    assert list_content["totalSize"] >= 1
    first_row = list_content["content"][0]
    assert first_row["userId"] == 12385
    assert first_row["realName"] in {"Teacher Li", "zhaosenlin"}
    assert "roleNames" in first_row

    detail_response = client.post(
        "/api/admin/get/auth/user/info?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"userId": 12385},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["content"]
    assert detail["userId"] == 12385
    assert detail["realName"] in {"Teacher Li", "zhaosenlin"}
    assert isinstance(detail["eduCampusIdList"], list)
    assert isinstance(detail["eduRoleIdList"], list)
    assert isinstance(detail["subjectCurriculumDtoList"], list)

    create_response = client.post(
        "/api/admin/add/or/update/auth/user?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "name": "newteacher01",
            "password": "MTIzNDU2",
            "realName": "New Teacher",
            "nickName": "NT",
            "sex": "?",
            "userImageUrl": "",
            "phoneNum": "13800138000",
            "isFullOrPart": "??",
            "state": "??",
            "roleIdList": [1],
            "eduCampusIdList": [851],
            "subjectCurriculumList": [],
            "platformTch": True,
            "eduTch": True,
            "tchJiaoyanAuth": True,
            "tchShiziAuth": True,
            "tchShixunAuth": True,
            "tchKtslAuth": True,
            "tchKftdAuth": True,
            "noticeAuth": True,
            "ojPermission": True,
            "prepareContentAuth": True,
        },
    )
    assert create_response.status_code == 200
    created_user = create_response.json()["content"]
    assert created_user["name"] == "newteacher01"
    created_user_id = created_user["userId"]

    reset_response = client.post(
        "/api/admin/auth/user/update/password?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"userId": created_user_id, "password": "bmV3cGFzcw=="},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["content"]["is_update"] is True

    login_response = client.post(
        "/java-api/school/tch/login",
        json={"userName": "newteacher01", "password": "newpass", "captchaVerifyParam": ""},
    )
    assert login_response.status_code == 200
    assert login_response.json()["success"] is True
    assert login_response.cookies.get("mirror_profile")

    unbind_response = client.post(
        "/java-api/school//tch/employeeSetting/resetWeMiniOpenid?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"userId": created_user_id},
    )
    assert unbind_response.status_code == 200
    assert unbind_response.json()["content"]["is_delete"] is True

    update_response = client.post(
        "/api/admin/add/or/update/auth/user?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "userId": created_user_id,
            "name": "newteacher01",
            "realName": "New Teacher 2",
            "nickName": "NT2",
            "sex": "?",
            "phoneNum": "13800138001",
            "isFullOrPart": "??",
            "state": "??",
            "roleIdList": [1],
            "eduCampusIdList": [851],
            "subjectCurriculumList": [],
            "platformTch": False,
            "eduTch": True,
            "tchJiaoyanAuth": False,
            "tchShiziAuth": True,
            "tchShixunAuth": False,
            "tchKtslAuth": True,
            "tchKftdAuth": False,
            "noticeAuth": True,
            "ojPermission": False,
            "prepareContentAuth": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"]["realName"] == "New Teacher 2"

    delete_response = client.post(
        "/api/admin/delete/auth/user?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"userId": created_user_id},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["content"]["is_delete"] is True

    list_after_delete = client.post(
        "/api/admin/get/auth/user/list?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduCampusId": 851,
            "realName": "",
            "name": "newteacher01",
            "phoneNum": "",
            "state": "",
            "roleId": "",
            "pageRequest": {"pageNum": 1, "pageSize": 20},
        },
    )
    assert list_after_delete.status_code == 200
    assert all(row["userId"] != created_user_id for row in list_after_delete.json()["content"]["content"])
def test_admin_campus_query_uses_local_fallback_from_teacher_campus_catalog(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="18164173640",
        token="admin-token",
        user_info={"realname": "超级管理员", "userId": 3394},
        school_info={"eduCampusId": 851, "name": "乐启享机器人", "eduDomain": "lqx"},
    )
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/school/edu/campus/queryListByUserId?t=1&userId=3394",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] == {"message": "", "code": ""}
    assert isinstance(payload["content"], list)
    assert payload["content"][0]["dept_id"] == 851
    assert payload["content"][0]["campusName"] == "Default Campus"
    assert payload["content"][0]["user_id"] == 12385


def test_school_notice_board_uses_local_fallback_and_recent_notice_count(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"userId": 12385, "realname": "Teacher Li"})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/tch/notice/list?t=1&read_state=1&page_no=1&page_size=10",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "notReadNum": 2,
                    "noticeUserList": [
                        {
                            "id": 101,
                            "notice_id": 9001,
                            "user_id": 12385,
                            "is_read": False,
                            "created_time": "2026-05-18 09:00:00",
                            "noticeInfo": {"id": 9001, "title": "最新通知", "content": "<p>latest</p>"},
                        },
                        {
                            "id": 100,
                            "notice_id": 9000,
                            "user_id": 12385,
                            "is_read": True,
                            "created_time": "2026-05-17 09:00:00",
                            "noticeInfo": {"id": 9000, "title": "旧通知", "content": "<p>old</p>"},
                        },
                    ],
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/tch/notice/list/for/school/board?t=1&page_no=1&page_size=3",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["notReadNum"] == 2
    assert content["total"] == 2
    assert content["page_no"] == 1
    assert content["page_size"] == 3
    assert len(content["noticeUserList"]) == 2
    assert content["noticeUserList"][0]["noticeInfo"]["title"] == "最新通知"


def test_recent_notice_fallback_uses_notice_catalog_when_direct_capture_missing(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"userId": 12385})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/tch/notice/list?t=1&read_state=1&page_no=1&page_size=10",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "noticeUserList": [
                        {
                            "id": 200,
                            "notice_id": 9900,
                            "user_id": 12385,
                            "is_read": False,
                            "created_time": "2026-05-18 10:30:00",
                            "noticeInfo": {"id": 9900, "title": "未读通知"},
                        },
                        {
                            "id": 199,
                            "notice_id": 9899,
                            "user_id": 12385,
                            "is_read": True,
                            "created_time": "2026-05-17 10:30:00",
                            "noticeInfo": {"id": 9899, "title": "已读通知"},
                        },
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getTchRecentNotReadNotice?t=1",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "notReadNotice": {
                "id": 200,
                "notice_id": 9900,
                "user_id": 12385,
                "is_read": False,
                "created_time": "2026-05-18 10:30:00",
                "noticeInfo": {"id": 9900, "title": "未读通知"},
            },
            "notReadNum": 1,
        },
        "error": {"message": "", "code": ""},
    }


def test_visit_record_select_list_uses_local_empty_page_fallback(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/visitRecord/selectList?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 2, "pageSize": 15}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "pageNum": 2,
            "pageSize": 15,
            "totalSize": 0,
            "totalPages": 0,
            "content": [],
            "records": [],
            "rows": [],
            "list": [],
            "total": 0,
            "pageRequest": {"pageNum": 2, "pageSize": 15},
            "totalContent": {"recordCount": 0},
        },
        "error": {"message": "", "code": ""},
    }


def test_tch_lesson_work_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/tch/lesson/work?t=1&tchPlanId=999999",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/tch/lesson/work?t=2&tchPlanId=999999",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {"tchLessonWork": None},
        "error": {"message": "", "code": ""},
    }


def test_student_work_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        (
            "https://steam.fun/api/tch/get/stu/lesson/tch/work/list"
            "?t=1&subject_code=1&is_marking=&type=&teaching_plan_id=999999&page_no=1&page_size=20"
        ),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/tch/get/stu/lesson/tch/work/list"
            "?t=2&subject_code=1&is_marking=&type=&teaching_plan_id=999999&page_no=1&page_size=20"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["total"] == 1
    assert content["page_no"] == 1
    assert content["page_size"] == 20
    assert len(content["workList"]) == 1
    row = content["workList"][0]
    assert row["subjectCode"] == "1"
    assert row["workType"] == "1"
    assert row["eduId"] == 834
    assert row["title"] != ""
    assert row["workUrl"].endswith("/index.html")
    assert row["covers"].endswith(".png")


def test_teacher_marking_work_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        (
            "https://steam.fun/api/tch/get/tch/stu/tch/work/list"
            "?t=1&subject_code=1&is_marking=&work_type=&page_no=1&page_size=20"
        ),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/tch/get/tch/stu/tch/work/list"
            "?t=2&subject_code=1&is_marking=&work_type=&page_no=1&page_size=20"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["subjectCode"] == "1"
    assert content["subjectName"] == "Jrcode"
    assert content["lessonId"] == 7001
    assert content["lessonTitle"] != ""
    assert content["total"] == 1
    assert content["page_no"] == 1
    assert content["page_size"] == 20
    assert len(content["workList"]) == 1
    row = content["workList"][0]
    assert row["lessonId"] == 7001
    assert row["teachingPlanId"] == 81001
    assert row["workUrl"].endswith("/index.html")


def test_tch_lesson_work_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/tch/lesson/work/list?t=1&page_no=1&page_size=20",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/tch/lesson/work/list?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["total"] == 1
    assert content["page_no"] == 1
    assert content["page_size"] == 20
    assert len(content["workList"]) == 1
    assert len(content["lessonWorkList"]) == 1
    assert len(content["tchLessonWorkList"]) == 1
    assert content["tchLessonWorkInfo"]["lessonId"] == 7001
    assert content["tchLeesonWorkInfo"]["subjectCode"] == "1"
    assert content["workList"][0]["workUrl"].endswith("/index.html")


def test_school_exam_and_paper_lists_use_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/exam/get/school/exam/list?t=1&page_no=1&page_size=20",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/exam/getSchoolLessonExamList?t=1&page_no=1&page_size=20",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/exam/getKeepPaperList?t=1&page_no=1&page_size=20",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    exam_response = client.get(
        "/api/exam/get/school/exam/list?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    classroom_response = client.get(
        "/api/exam/getSchoolLessonExamList?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    keep_paper_response = client.get(
        "/api/exam/getKeepPaperList?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert exam_response.status_code == 200
    assert exam_response.json()["content"] == {
        "examList": [],
        "schoolExamList": [],
        "list": [],
        "rows": [],
        "total": 0,
        "page_no": 1,
        "page_size": 20,
    }

    assert classroom_response.status_code == 200
    assert classroom_response.json()["content"] == {
        "examList": [],
        "schoolLessonExamList": [],
        "list": [],
        "rows": [],
        "total": 0,
        "page_no": 1,
        "page_size": 20,
    }

    assert keep_paper_response.status_code == 200
    assert keep_paper_response.json()["content"] == {
        "paperList": [],
        "keepPaperList": [],
        "list": [],
        "rows": [],
        "total": 0,
        "page_no": 1,
        "page_size": 20,
    }


def test_training_list_and_info_use_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/tch/training/list?t=1&page_no=1&page_size=20",
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/admin/get/tch/training/list?t=1&page_no=1&page_size=20",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    teacher_list = client.get(
        "/api/get/tch/training/list?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    admin_list = client.get(
        "/api/admin/get/tch/training/list?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    info_response = client.get(
        "/api/get/tch/training/info?t=2&tch_training_id=42",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert teacher_list.status_code == 200
    assert teacher_list.json()["content"] == {
        "tchTrainingList": [],
        "list": [],
        "rows": [],
        "total": 0,
        "page_no": 1,
        "page_size": 20,
    }

    assert admin_list.status_code == 200
    assert admin_list.json()["content"] == {
        "tchTrainingList": [],
        "list": [],
        "rows": [],
        "total": 0,
        "page_no": 1,
        "page_size": 20,
    }

    assert info_response.status_code == 200
    info_payload = info_response.json()["content"]["tchTrainingInfo"]
    assert info_payload["id"] == 42
    assert info_payload["chapterInfoArr"][0]["videoInfoArr"][0]["video_url"] == ""


def test_school_open_miss_class_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/tch/xmedu/getSchoolOpenMissClass?t=1&name=&subject_id=",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/xmedu/getSchoolOpenMissClass?t=2&name=&subject_id=",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"]["classList"], list)
    assert "total" in payload["content"]


def test_school_community_work_query_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/community/work/queryStuWorkList?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/community/work/queryStuWorkList?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageNum": 1, "pageSize": 10, "subjectCode": "1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["pageNum"] == 1
    assert content["pageSize"] == 10
    assert content["totalSize"] == 1
    assert content["totalPages"] == 1
    assert content["total"] == 1
    assert len(content["content"]) == 1
    assert len(content["records"]) == 1
    assert len(content["rows"]) == 1
    assert len(content["list"]) == 1
    assert len(content["workList"]) == 1
    assert len(content["stuWorkList"]) == 1
    assert len(content["schoolCreateWorkStuList"]) == 1
    row = content["content"][0]
    assert row["subjectCode"] == "1"
    assert row["workType"] == "1"
    assert row["workUrl"].endswith("/index.html")


def test_competition_center_auth_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        (
            "https://steam.fun/api/test/school/question/bank/auth"
            "?t=1&permission_key=CompetitionCenter-QuestionBankCenter-Platform"
        ),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/test/school/question/bank/auth"
            "?t=2&permission_key=CompetitionCenter-QuestionBankCenter-Platform"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {"is_have_auth": True},
        "error": {"message": "", "code": ""},
    }


def test_competition_center_subroute_redirects_to_teacher_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/competitionCenter/questionBankCenter/platform", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_exam_management_subroute_redirects_to_teacher_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/exam-management", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_practice_management_subroute_redirects_to_teacher_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/practice-management", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_exam_management_namespaced_route_redirects_to_teacher_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/exam/exam-management", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_exam_student_subroute_redirects_to_student_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/exam-stu/new-exam", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/myClass"


def test_exam_student_subroute_without_profile_redirects_to_student_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/exam-stu/new-exam", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/myClass"


def test_exam_student_practice_record_redirects_to_student_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/exam-stu/practice-record", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/myClass"


def test_stuexam_question_list_and_submit_answer_roundtrip(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/api/stuexam/get/stu/exam/question/list?examId=242055")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["exam"]["id"] == 242055
    assert content["paper"]["id"] == 156584
    assert content["questionList"]
    question_id = content["questionList"][0]["id"]

    submit_response = client.post(
        "/api/stuexam/check/single/question",
        data={
            "examId": "242055",
            "questionId": str(question_id),
            "questionScore": "15",
            "answer": "A",
        },
        headers={"x-mirror-profile": "student"},
    )

    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["success"] is True
    assert submit_payload["content"]["stuExamQuestionId"]

    answer_response = client.get(
        f"/api/stuexam/get/stu/question/answer?examId=242055&questionId={question_id}",
        headers={"x-mirror-profile": "student"},
    )

    assert answer_response.status_code == 200
    answer_payload = answer_response.json()
    assert answer_payload["success"] is True
    assert answer_payload["content"]["stuExamQuestion"]["answer"] == "A"

    result_response = client.get(
        f"/api/stuexam/get/exam/result/question/list?examId=242055&questionId={question_id}",
        headers={"x-mirror-profile": "student"},
    )

    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["success"] is True
    assert result_payload["content"]["questionList"][0]["stu_answer"] == "A"


def test_practice_record_question_list_fallback_includes_exam_and_paper(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/exam/get/practice/record/question/list/for/tch?examId=228978&examStuRecordId=2289781",
        headers={"x-mirror-profile": "student"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["exam"]["id"] == 228978
    assert content["exam"]["is_show_answer"] is True
    assert content["paper"]["id"]
    assert content["questionList"]
    assert content["realname"] == "Chen Muran"


def test_practice_record_question_list_uses_exam_stu_record_id_when_exam_id_is_missing(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/exam/get/practice/record/question/list/for/tch?examStuRecordId=2289781",
        headers={"x-mirror-profile": "student"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["exam"]["id"] == 228978
    assert "2024" in content["exam"]["title"]


def test_student_wear_state_fallback_returns_title_resource_array(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_runtime_student_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/points/stu/order/wearState?t=1",
        headers={"Authorization": "Bearer student-token"},
        json={"stuId": 400057},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert isinstance(content, list)
    assert [row["category"] for row in content] == [0, 1, 3]
    assert all("pictureUrl" in row for row in content)
    assert all("cueWord" in row for row in content)


def test_competition_center_banner_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/school/banner/list?t=1&banner_type=2",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/school/banner/list?t=2&banner_type=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {"bannerList": [], "banner_list": []},
        "error": {"message": "", "code": ""},
    }


def test_competition_center_question_bank_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        (
            "https://steam.fun/api/exam/get/school/question/bank/list"
            "?t=1&source_id=&subject_id=&title=&search_question_bank_type=2"
            "&post_state=&isShowSelfPaper=false&page_no=1&page_size=20"
        ),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/exam/get/school/question/bank/list"
            "?t=2&source_id=&subject_id=&title=&search_question_bank_type=2"
            "&post_state=&isShowSelfPaper=false&page_no=1&page_size=20"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "questionBankList": [],
            "question_bank_list": [],
            "total": 0,
            "page_no": 1,
            "page_size": 20,
        },
        "error": {"message": "", "code": ""},
    }


def test_competition_center_select_curr_cls_uses_local_fallback_when_capture_is_unauthorized(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_unauthorized_response(tmp_path, "https://steam.fun/java-api/school/tch/selectCurrCls?t=1")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/school/tch/selectCurrCls?t=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert isinstance(response.json()["content"], list)


def test_competition_center_question_types_uses_local_fallback_when_capture_is_unauthorized(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_unauthorized_response(
        tmp_path,
        "https://steam.fun/java-api/exam/sch/testExam/getQuestionTypesAndSubjects?t=1",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/java-api/exam/sch/testExam/getQuestionTypesAndSubjects?t=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "subjectList" in response.json()["content"]
    assert "questionTypes" in response.json()["content"]


def test_teacher_directory_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        user_info={
            "id": 12385,
            "name": "zhaosenlin",
            "realName": "赵森林",
            "phoneNum": "13000000000",
        },
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/tch/common/selectByEduCampusId?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/tch/common/selectByEduCampusId?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"eduCampusId": 851},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"], list)
    assert any(row["name"] == "zhaosenlin" for row in payload["content"])


def test_school_file_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/school/file/list?t=1",
        message="寮傚湴鐧诲綍",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/school/file/list?t=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "fileList": [],
            "schoolFileList": [],
            "list": [],
            "rows": [],
            "total": 0,
            "page_no": 1,
            "page_size": 20,
        },
        "error": {"message": "", "code": ""},
    }


def test_teacher_teaching_plan_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/tch/get/teaching/plan/list?t=1&class_id=3001",
        message="寮傚湴鐧诲綍",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/get/teaching/plan/list?t=2&class_id=3001&page_no=1&page_size=10",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"]["teachingPlan"], list)
    assert any(row["curriculum_class_id"] == 3001 for row in payload["content"]["teachingPlan"])


def test_teacher_get_teaching_plan_list_uses_local_fallback_for_class_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/teaching/plan/list?t=1&campusIds=[851]&page_no=1&page_size=1000",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert isinstance(content["teachingPlan"], list)
    assert content["teachingPlan"]
    assert any(row["curriculum_class_id"] == 3001 for row in content["teachingPlan"])


def test_teacher_get_teaching_plan_list_uses_local_fallback_for_filtered_calendar_query(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/get/teaching/plan/list"
            "?t=1781475209504"
            "&className="
            "&lecturer_id="
            "&campusIds=[851]"
            "&end_class_state=2"
            "&is_have_class_date=1"
            "&start_date=2026-06-01+00:00:00"
            "&end_date=2026-07-01+00:00:00"
            "&page_no=1"
            "&page_size=1000"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert isinstance(content["teachingPlan"], list)
    assert content["total"] >= 0


def test_teacher_teaching_plan_list_returns_class_detail_shape_for_class_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/get/teaching/plan/list?t=2&class_id=3001",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert isinstance(content["teaching_plan_list"], list)
    assert content["teaching_plan_list"]
    assert content["teaching_plan_list"][0]["originalIndex"] == 0
    assert content["classInfo"]["id"] == 3001
    assert isinstance(content["classInfo"]["curriculumList"], list)


def test_teacher_evaluate_student_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/tch/getStuTchPlanListForEvaluate?t=1&teachingPlanId=81001&page_no=1&page_size=10",
        message="寮傚湴鐧诲綍",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/getStuTchPlanListForEvaluate?t=2&teachingPlanId=81001&page_no=1&page_size=10",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"]["stuTchPlanList"], list)
    assert payload["content"]["total"] == 0


def test_student_set_end_date_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/stu/setEndDate?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/stu/setEndDate?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001, "endDate": "2026-05-31"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "is_update": True,
            "updatedStuIds": [2001],
            "successCount": 1,
        },
        "error": {"message": "", "code": ""},
    }


def test_student_batch_set_end_date_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/stu/batchSetEndDate?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/stu/batchSetEndDate?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuIds": [2001, 2002], "endDate": "2026-05-31"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "is_update": True,
            "updatedStuIds": [2001, 2002],
            "successCount": 2,
        },
        "error": {"message": "", "code": ""},
    }


def test_student_set_end_date_persists_for_cached_student_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_management_captures(tmp_path, stu_id=2001)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/stu/setEndDate?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    update_response = client.post(
        "/java-api/school/stu/setEndDate?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001, "endDate": "2026-06-30"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"]["updatedStuIds"] == [2001]

    list_response = client.post(
        "/java-api/school/stu/selectStudy?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert list_response.status_code == 200
    rows = list_response.json()["content"]["content"]
    target = next(row for row in rows if row["stuId"] == 2001)
    assert target["endDate"] == "2026-06-30"


def test_student_set_end_date_supports_daynum_payload_from_ui(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    created = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "daynum-student",
            "realName": "DayNum Student",
            "sex": "M",
            "parentAPhoneNum": "13800138009",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-18",
        }
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/stu/setEndDate?t=1",
        method="POST",
        message="鏉冮檺璁よ瘉寮傚父",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/stu/setEndDate?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"type": 1, "endDate": "", "dayNum": "30", "stuId": created["id"]},
    )

    assert response.status_code == 200
    assert response.json()["content"]["updatedStuIds"] == [created["id"]]

    overlay = store.get_student_overlay(created["id"])
    assert overlay is not None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", overlay["end_date"])
    assert overlay["end_date"] != "2026-05-18"

    list_response = client.post(
        "/java-api/school/stu/selectStudy?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert list_response.status_code == 200
    rows = list_response.json()["content"]["content"]
    target = next(row for row in rows if row["stuId"] == created["id"])
    assert target["endDate"] == overlay["end_date"]


def test_student_batch_set_end_date_persists_for_multiple_cached_student_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_management_captures(tmp_path, stu_id=2001)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/stu/selectStudy?t=3",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "pageNum": 1,
                    "pageSize": 20,
                    "totalSize": 2,
                    "totalPages": 1,
                    "content": [
                        {
                            "stuId": 2001,
                            "stuName": "Local Mirror Student",
                            "normalState": 1,
                            "stuAccount": "mirror-student",
                            "className": "--",
                            "parentWeChat": "已绑定(1)",
                            "wcmFlag": "未绑定",
                            "endDate": "2026-05-19",
                            "eduCampusName": "Default Campus",
                            "phoneNum": "13800138000",
                            "schoolName": "Mirror School",
                            "createdTime": "2026-05-13 06:24:42",
                        },
                        {
                            "stuId": 2002,
                            "stuName": "Second Student",
                            "normalState": 1,
                            "stuAccount": "mirror-student-2",
                            "className": "--",
                            "parentWeChat": "未绑定",
                            "wcmFlag": "未绑定",
                            "endDate": "2026-05-21",
                            "eduCampusName": "Default Campus",
                            "phoneNum": "13800138001",
                            "schoolName": "Mirror School",
                            "createdTime": "2026-05-13 06:24:42",
                        },
                    ],
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        request_body=json.dumps({"pageRequest": {"pageNum": 1, "pageSize": 20}}, ensure_ascii=False).encode("utf-8"),
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/stu/batchSetEndDate?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    update_response = client.post(
        "/java-api/school/stu/batchSetEndDate?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuIds": [2001, 2002], "endDate": "2026-07-01"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"]["updatedStuIds"] == [2001, 2002]

    list_response = client.post(
        "/java-api/school/stu/selectStudy?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert list_response.status_code == 200
    rows = {row["stuId"]: row for row in list_response.json()["content"]["content"]}
    assert rows[2001]["endDate"] == "2026-07-01"
    assert rows[2002]["endDate"] == "2026-07-01"


def test_student_select_study_keeps_cached_student_rows_when_no_local_students_exist(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_campus_user_capture(
        tmp_path,
        students=[
            {
                "id": 398164,
                "name": "lbschenzhihao",
                "normal_state": 2,
                "class_str": "JR补课",
                "campusName": "默认校区",
                "schoolName": "乐启享机器人",
                "schoolDomain": "lqx",
                "enddate": "2026-05-11 23:59:59",
                "studentUserInfo": {
                    "id": 412914,
                    "realname": "陈志豪",
                    "sex": "男",
                    "phone_num": "",
                    "school_name": "",
                    "grade": "",
                    "headimg_url": "https://wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
                },
                "stuClassArr": [{"className": "JR补课"}],
                "zone_auth": 1,
                "oj_auth": 1,
                "p_auth": 1,
            }
        ],
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/school/stu/selectStudy?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/stu/selectStudy?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )

    assert response.status_code == 200
    rows = response.json()["content"]["content"]
    target = next(row for row in rows if row["stuId"] == 398164)
    assert target["stuAccount"] == "lbschenzhihao"
    assert target["stuName"] == "陈志豪"
    assert target["className"] == "JR补课"


def test_classes_list_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        (
            "https://steam.fun/api/get/classes/list"
            "?t=1&week_json=[]&campusIds=[851]&curriculum_class_type=&className="
            "&lecturer_id=&subject_id=&curriculum_id=&teaching_type=&end_class_state=0&page_no=1&page_size=20"
        ),
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/get/classes/list"
            "?t=2&week_json=[]&campusIds=[851]&curriculum_class_type=&className="
            "&lecturer_id=&subject_id=&curriculum_id=&teaching_type=&end_class_state=0&page_no=1&page_size=20"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["total"] >= 1
    assert any(row["id"] == 3001 for row in content["class_list"])
    target = next(row for row in content["class_list"] if row["id"] == 3001)
    assert target["name"] == "周日18:30 Jrcode"
    assert target["subject_id_list"] == [1]
    assert target["curriculum_id_list"] == [501]
    assert target["student_total_num"] >= 0


def test_student_class_and_timetable_only_include_classes_for_current_student(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    _store_student_profile(
        tmp_path,
        token="student-token",
        fresh_auth={
            "identity": 2,
            "userInfo": {
                "stuUserInfo": {
                    "id": 398164,
                    "name": "lbschenzhihao",
                    "eduCampusId": 851,
                    "stuUserInfo": {"id": 412914, "realName": "陈志豪", "sex": "男", "eduCampusId": 851},
                }
            },
            "schoolInfo": {"id": 834, "name": "Mirror School", "eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "student-token",
                "permisionList": [],
                "userInfo": {
                    "stuUserInfo": {
                        "id": 398164,
                        "name": "lbschenzhihao",
                        "eduCampusId": 851,
                        "stuUserInfo": {"id": 412914, "realName": "陈志豪", "sex": "男", "eduCampusId": 851},
                    }
                },
                "schoolInfo": {"id": 834, "name": "Mirror School", "eduCampusId": 851},
                "identity": 2,
            }
        },
    )
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/class/student/list?classId=3001&realname=&page_no=1&page_size=100",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "studentList": [
                        {
                            "id": 9001,
                            "student_user_id": 398164,
                            "curriculum_class_id": 3001,
                            "studentInfo": {
                                "id": 398164,
                                "name": "lbschenzhihao",
                                "headimg_url": "https://cdn.example.com/student-1.png",
                                "studentUserInfo": {"realname": "陈志豪"},
                            },
                            "missStuTchPlanNum": 0,
                            "missStuTchPlanArr": [],
                        }
                    ],
                    "page_no": 1,
                    "page_size": 100,
                    "total": 1,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/class/student/list?classId=3002&realname=&page_no=1&page_size=100",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "studentList": [
                        {
                            "id": 9002,
                            "student_user_id": 499999,
                            "curriculum_class_id": 3002,
                            "studentInfo": {
                                "id": 499999,
                                "name": "other-student",
                                "headimg_url": "https://cdn.example.com/student-2.png",
                                "studentUserInfo": {"realname": "Other Student"},
                            },
                            "missStuTchPlanNum": 0,
                            "missStuTchPlanArr": [],
                        }
                    ],
                    "page_no": 1,
                    "page_size": 100,
                    "total": 1,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    class_response = client.get(
        "/api/stu/get/stu/class/list?t=1&page_no=1&page_size=16",
        headers={"Authorization": "Bearer student-token"},
    )
    timetable_response = client.get(
        "/api/stu/get/stu/timetable/new?t=1&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )

    assert class_response.status_code == 200
    class_rows = class_response.json()["content"]["classlist"]
    assert [row["id"] for row in class_rows] == [3001]

    assert timetable_response.status_code == 200
    timetable_rows = timetable_response.json()["content"]["tchPlanList"]
    assert {row["curriculum_class_id"] for row in timetable_rows} == {3001}


def test_points_order_query_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/java-api/points/sch/order/queryList?t=1",
        method="POST",
        message="权限认证异常",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/points/sch/order/queryList?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 2, "pageSize": 15}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "content": {
            "pageNum": 2,
            "pageSize": 15,
            "totalSize": 0,
            "totalPages": 0,
            "content": [],
            "records": [],
            "rows": [],
            "list": [],
        },
        "error": {"message": "", "code": ""},
    }


def test_admin_latest_total_info_uses_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        school_info={
            "name": "Mirror School",
            "maxStudentNum": 200,
            "maxTeacherNum": 5,
            "stuRemainTime": 180,
        },
    )
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/admin/get/latest/sys/total/info?t=1",
        message="出现异常，请联系管理员",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/admin/get/latest/sys/total/info?t=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["content"]["latestSysTotalInfo"]["eduName"] == "Mirror School"
    assert payload["content"]["latestSysTotalInfo"]["maxStudentNum"] == 200
    assert payload["content"]["latestSysTotalInfo"]["maxTeacherNum"] == 5
    assert payload["content"]["latestSysTotalInfo"]["normal_class_num"] >= 0


def test_admin_student_subject_stats_use_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, school_info={"name": "Mirror School"})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/admin/get/stu/num/by/subject?t=1",
        message="出现异常，请联系管理员",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/admin/get/stu/num/by/subject?t=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"]["schoolNumList"], list)
    assert any(row["subjectInfo"]["name"] == "Jrcode" for row in payload["content"]["schoolNumList"])


def test_admin_school_subject_stats_use_local_fallback_when_capture_is_invalid_token(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, school_info={"name": "Mirror School"})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/admin/get/school/num/by/school/subject?t=1",
        message="出现异常，请联系管理员",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/admin/get/school/num/by/school/subject?t=2",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["content"]["schoolNumList"], list)
    assert any(row["schoolNum"] == 1 for row in payload["content"]["schoolNumList"])


def test_background_login_route_does_not_bootstrap_teacher_context_without_session(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/background/login")

    assert response.status_code == 200
    assert "shell" in response.text
    assert "localStorage.setItem('vuex',JSON.stringify(data))" not in response.text
    assert '"adminToken":"teacher-token"' not in response.text


def test_login_route_clears_stale_profile_state_and_expires_cookie(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/login")

    assert response.status_code == 200
    assert "shell" in response.text
    assert "localStorage.removeItem('vuex')" in response.text
    assert "sessionStorage.removeItem('mirror_profile')" in response.text
    assert "localStorage.setItem('vuex',JSON.stringify(data))" not in response.text
    assert response.headers["cache-control"].startswith("no-store")
    assert "mirror_profile=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_background_login_route_uses_professional_local_login_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/background/chatgpt",
        final_url="https://steam.fun/background/login?redirect=chatgpt",
        status=200,
        html=(
            '<html><body><div class="login-page">'
            '<input placeholder="请输入手机号" />'
            '<input placeholder="请输入密码" />'
            '<button>登 录</button>'
            "</div></body></html>"
        ),
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/background/login")

    assert response.status_code == 200
    assert 'class="login-shell"' in response.text
    assert "学员 / 家长登录" in response.text
    assert "教师 / 管理员登录" in response.text
    assert "sessionStorage.removeItem('mirror_profile')" in response.text


def test_background_login_route_prefers_local_password_form_when_admin_profile_exists(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="4QrcOUm6Wau+VuBX8g+IPg==",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9002, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "adminToken": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9002, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    store.store_route_capture(
        profile_name="teacher",
        route="/background/chatgpt",
        final_url="https://steam.fun/background/login?redirect=chatgpt",
        status=200,
        html=(
            '<html><body><div class="login-page">'
            '<input placeholder="�������ֻ���" />'
            '<input placeholder="����������" />'
            '<button>��ȡ��֤��</button>'
            '<button>�� ¼</button>'
            "</div></body></html>"
        ),
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/background/login")

    assert response.status_code == 200
    assert 'action="/java-api/school/tch/login"' in response.text
    assert 'name="userName"' in response.text
    assert 'name="password"' in response.text
    assert "captchaVerifyParam" in response.text
    assert "sessionStorage.removeItem('mirror_profile')" in response.text
    assert "����������" not in response.text


def test_background_subroute_without_session_redirects_to_login(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9002, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "adminToken": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9002, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    store.store_route_capture(
        profile_name="teacher",
        route="/background/course-management/school-curriculum",
        final_url="https://steam.fun/background/login?redirect=school-curriculum",
        status=200,
        html="<html><body>login snapshot</body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/background/course-management/school-curriculum",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")




def test_local_background_curriculum_page_uses_curated_bootstrap_without_dom_hiding(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="zhaosenlin",
        token="teacher-token",
    )
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/background/course-management/school-curriculum",
        final_url="https://steam.fun/background/course-management/school-curriculum",
        status=200,
        html=(
            '<html><body><div id="app">'
            '<ul role="menu" class="el-menu">'
            '<li role="menuitem" class="el-submenu"><div class="el-submenu__title">首页</div></li>'
            '<li role="menuitem" class="el-menu-item">数据看板</li>'
            '<li role="menuitem" class="el-submenu"><div class="el-submenu__title">前台业务</div></li>'
            '<li role="menuitem" class="el-submenu"><div class="el-submenu__title">教务中心</div></li>'
            '<li role="menuitem" class="el-submenu"><div class="el-submenu__title">上课记录</div></li>'
            '<li role="menuitem" class="el-submenu"><div class="el-submenu__title">课程中心</div></li>'
            '<li role="menuitem" class="el-submenu"><div class="el-submenu__title">系统设置</div></li>'
            '</ul>'
            '</div></body></html>'
        ),
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "admin")

    response = client.get(
        "/background/course-management/school-curriculum",
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum"},
    )

    assert response.status_code == 200
    assert "首页" in response.text
    assert "前台业务" in response.text
    assert '"school-user-list"' in response.text
    assert '"schoolSys"' in response.text
    assert '"orderpay"' not in response.text
    assert "__localCoreRouteCleanup" not in response.text


def test_local_background_curriculum_page_bootstrap_uses_admin_teaching_permissions(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    auth_tree_payload = _core_background_auth_tree_payload()
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="zhaosenlin",
        token="teacher-token",
        auth_tree=json.dumps(auth_tree_payload, ensure_ascii=False),
        permissions=_flatten_permission_tree_for_storage(auth_tree_payload["children"]),
    )
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/background/course-management/school-curriculum",
        final_url="https://steam.fun/background/course-management/school-curriculum",
        status=200,
        html="<html><body><div>curriculum page</div></body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "admin")

    response = client.get(
        "/background/course-management/school-curriculum",
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/school-curriculum"},
    )

    assert response.status_code == 200
    start = response.text.index("var data=") + len("var data=")
    end = response.text.index(";try{localStorage.setItem('vuex',JSON.stringify(data));}catch(e){}")
    bootstrap_payload = json.loads(response.text[start:end].replace("<\\/", "</"))
    permissions = bootstrap_payload["user"]["permisionList"]
    assert {node["alias"] for node in permissions} == {"tchCenter", "courseCenter", "systemSetting"}
    teach_center = next(node for node in permissions if node["alias"] == "tchCenter")
    assert {child["alias"] for child in teach_center["children"]} == {
        "students-management1",
        "class-management1",
        "teachplan1",
        "classRecord",
    }
    assert "classRecord" in json.dumps(teach_center, ensure_ascii=False)
    course_center = next(node for node in permissions if node["alias"] == "courseCenter")
    assert {child["alias"] for child in course_center["children"]} == {"course-list"}
    assert "school-curriculum" in json.dumps(course_center, ensure_ascii=False)

    admin_permissions = bootstrap_payload["user"]["adminpermisionList"]
    assert {node["permission_key"] for node in admin_permissions} == {"tchCenter", "courseCenter", "systemSetting"}
    admin_teach_center = next(node for node in admin_permissions if node["permission_key"] == "tchCenter")
    assert {child["permission_key"] for child in admin_teach_center["children"]} == {
        "students-management1",
        "class-management1",
        "teachplan1",
        "classRecord",
    }
    assert "school-user-list" in json.dumps(admin_permissions, ensure_ascii=False)
    assert "schoolSys" in json.dumps(admin_permissions, ensure_ascii=False)
    assert "systemSetting" in json.dumps(admin_permissions, ensure_ascii=False)
    assert "pageHome" not in json.dumps(permissions, ensure_ascii=False)


def test_background_subroute_bootstraps_selected_admin_profile_from_cookie(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, username="zhaosenlin", token="teacher-token")
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9002, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "adminToken": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9002, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    store.store_route_capture(
        profile_name="teacher",
        route="/background/course-management/school-curriculum",
        final_url="https://steam.fun/background/login?redirect=school-curriculum",
        status=200,
        html="<html><body>login snapshot</body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    client.cookies.set("mirror_profile", "admin")
    response = client.get("/background/course-management/school-curriculum")

    assert response.status_code == 200
    assert "shell" in response.text
    assert '"adminToken":"admin-token"' in response.text
    assert 'sessionStorage.setItem(\'mirror_profile\',"admin")' in response.text


def test_school_home_subroute_without_session_redirects_to_login(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_route_capture(
        profile_name="teacher",
        route="/school-home-page",
        final_url="https://steam.fun/school-home-page",
        status=200,
        html="<html><body><div>teacher home capture</div></body></html>",
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/school-home-page/orderpay", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")


def test_legacy_competition_question_bank_alias_redirects_to_teacher_core_route(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/competitionCenter/questionBank?tabComponent=platformQuestionBank", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/code-classroom/classroom-index"


def test_platform_curriculum_route_redirects_to_admin_workspace(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, profile_name="admin", username="18164173640", token="admin-token")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/background/course-management/platform-curriculum", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/background/course-management/school-curriculum"


def test_missing_asset_path_does_not_fall_back_to_shell(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/fonts/element-icons.woff")

    assert response.status_code == 404
    assert response.text == ""


def test_same_origin_hashed_asset_falls_back_to_available_local_variant(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    origin_root = tmp_path / "origin" / "steam.fun"
    (origin_root / "js").mkdir(parents=True, exist_ok=True)
    (origin_root / "css").mkdir(parents=True, exist_ok=True)
    (origin_root / "js" / "app.f5edd84f.js").write_text("console.log('local app bundle');", encoding="utf-8")
    (origin_root / "css" / "app.c6a9522f.css").write_text("body { color: #123456; }", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    js_response = client.get("/js/app.52acf064.js")
    css_response = client.get("/css/app.41c2ceb6.css")

    assert js_response.status_code == 200
    assert "local app bundle" in js_response.text
    assert "javascript" in js_response.headers["content-type"]
    assert css_response.status_code == 200
    assert "color: #123456" in css_response.text
    assert css_response.headers["content-type"].startswith("text/css")


def test_same_origin_hashed_js_fallback_skips_html_mislabeled_bundle(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    origin_root = tmp_path / "origin" / "steam.fun"
    (origin_root / "js").mkdir(parents=True, exist_ok=True)
    (origin_root / "js" / "app.1cc45b56.js").write_text(
        "<!DOCTYPE html><html><body>bad bundle</body></html>",
        encoding="utf-8",
    )
    (origin_root / "js" / "app.f5edd84f.js").write_text("console.log('healthy app bundle');", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/js/app.52acf064.js")

    assert response.status_code == 200
    assert "healthy app bundle" in response.text
    assert "<!DOCTYPE html>" not in response.text


def test_missing_same_origin_asset_is_proxied_and_cached(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)

    def fake_get(url: str, headers: dict[str, str], timeout: int = 60, stream: bool = False):
        assert url == "https://steam.fun/fonts/element-icons.woff"
        assert headers["Referer"] == "https://steam.fun/"
        return FakeResponse(content=b"font-bytes", content_type="font/woff")

    monkeypatch.setattr("steamfun_mirror.server.requests.get", fake_get)
    client = TestClient(create_app(tmp_path, allow_live_proxy=True))

    response = client.get("/fonts/element-icons.woff")

    assert response.status_code == 200
    assert response.content == b"font-bytes"
    assert response.headers["content-type"].startswith("font/woff")
    assert (tmp_path / "origin" / "steam.fun" / "fonts" / "element-icons.woff").read_bytes() == b"font-bytes"


def test_missing_external_asset_is_proxied_and_cached(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)

    def fake_get(url: str, headers: dict[str, str], timeout: int = 60, stream: bool = False):
        assert url == "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
        return FakeResponse(content=b"jpeg-bytes", content_type="image/jpeg")

    monkeypatch.setattr("steamfun_mirror.server.requests.get", fake_get)
    client = TestClient(create_app(tmp_path, allow_live_proxy=True))

    response = client.get("/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg")

    assert response.status_code == 200
    assert response.content == b"jpeg-bytes"
    assert response.headers["content-type"].startswith("image/jpeg")
    assert (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "resources"
        / "static"
        / "homepage"
        / "person-icon.jpeg"
    ).read_bytes() == b"jpeg-bytes"


def test_external_course_asset_with_query_is_served_from_indexed_local_archive(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_external_asset(
        "https://wugecdn.steam.fun/courses/demo/data/player.js?8E49BC96",
        b"console.log('local player');",
        headers={"content-type": "application/javascript"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_external/wugecdn.steam.fun/courses/demo/data/player.js?8E49BC96")

    assert response.status_code == 200
    assert "local player" in response.text
    assert response.headers["content-type"].startswith("application/javascript")


def test_external_course_asset_marked_missing_in_archive_does_not_proxy_or_stub(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.upsert_local_curriculum_material_snapshot(
        {
            "id": 39525,
            "subject_id": 1,
            "curriculum_id": 3429,
            "title": "Watermelon Fan",
            "ppt_url": "https://wugecdn.steam.fun/course/index.html",
        }
    )
    store.upsert_curriculum_material_archive(
        39525,
        {
            "root_url_count": 1,
            "fetched_asset_count": 1,
            "missing_asset_count": 1,
            "all_local": False,
            "last_verified_at": "2026-06-11T12:00:00",
        },
    )
    store.replace_curriculum_material_archive_assets(
        39525,
        [
            {
                "asset_url": "https://wugecdn.steam.fun/course/data/player.js",
                "local_path": "",
                "status": 0,
                "content_type": "",
                "required": True,
                "present": False,
            }
        ],
    )

    calls = {"proxy": 0, "stub": 0}

    def fail_proxy(*args, **kwargs):
        calls["proxy"] += 1
        raise AssertionError("course strict-local mode must not proxy missing course assets")

    def fail_stub(*args, **kwargs):
        calls["stub"] += 1
        raise AssertionError("course strict-local mode must not synthesize missing course assets")

    monkeypatch.setattr(server_module, "_proxy_and_cache_asset", fail_proxy)
    monkeypatch.setattr(server_module, "_synthetic_missing_asset_response", fail_stub)
    client = TestClient(create_app(tmp_path, allow_live_proxy=True))

    response = client.get("/_external/wugecdn.steam.fun/course/data/player.js")

    assert response.status_code == 424
    assert calls == {"proxy": 0, "stub": 0}


def test_external_asset_alias_without_underscore_serves_same_asset(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_external_asset(
        "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg",
        b"jpeg-bytes",
        headers={"content-type": "image/jpeg"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg")

    assert response.status_code == 200
    assert response.content == b"jpeg-bytes"
    assert response.headers["content-type"].startswith("image/jpeg")


def test_external_asset_retries_http_when_https_fetch_fails(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)
    attempted_urls: list[str] = []

    def fake_get(url: str, headers: dict[str, str], timeout: int = 60, stream: bool = False):
        attempted_urls.append(url)
        if url.startswith("https://"):
            raise requests.RequestException("ssl failure")
        return FakeResponse(content=b"http-jpeg", content_type="image/jpeg")

    monkeypatch.setattr("steamfun_mirror.server.requests.get", fake_get)
    client = TestClient(create_app(tmp_path, allow_live_proxy=True))

    response = client.get("/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg")

    assert response.status_code == 200
    assert response.content == b"http-jpeg"
    assert attempted_urls == [
        "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg",
        "http://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg",
    ]


def test_external_asset_can_be_served_from_legacy_origin_host_path(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    legacy_path = (
        tmp_path
        / "origin"
        / "wugecdn.steam.fun"
        / "resources"
        / "static"
        / "school-management"
        / "steam_bg_2.jpg"
    )
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(b"legacy-jpeg")

    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    response = client.get("/_external/wugecdn.steam.fun/resources/static/school-management/steam_bg_2.jpg")

    assert response.status_code == 200
    assert response.content == b"legacy-jpeg"
    assert response.headers["content-type"].startswith("image/jpeg")


def test_external_asset_with_non_ascii_path_is_served_from_encoded_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_external_asset(
        "https://wugecdn.steam.fun/resources/static/teachppt/%E8%AF%BE%E5%A0%82%E9%A2%98%E7%9B%AE.png",
        b"teachppt-icon",
        headers={"content-type": "image/png"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_external/wugecdn.steam.fun/resources/static/teachppt/%E8%AF%BE%E5%A0%82%E9%A2%98%E7%9B%AE.png")

    assert response.status_code == 200
    assert response.content == b"teachppt-icon"
    assert response.headers["content-type"].startswith("image/png")


def test_external_browsersupport_js_keeps_svg_namespace_and_disables_unsupported_redirect(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_external_asset(
        "https://wugecdn.steam.fun/courses/demo/data/browsersupport.js",
        (
            'function i(){return n.createElementNS.call(n,"http://www.w3.org/2000/svg",arguments[0])};'
            'e("data/html5-unsupported.html");'
        ).encode("utf-8"),
        headers={"content-type": "application/javascript"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_external/wugecdn.steam.fun/courses/demo/data/browsersupport.js")

    assert response.status_code == 200
    assert 'http://www.w3.org/2000/svg' in response.text
    assert '/_external/www.w3.org/2000/svg' not in response.text
    assert 'e("data/html5-unsupported.html");' not in response.text
    assert "performRedirectIfNeeded=function(){return!1}" in response.text


def test_external_player_js_disables_resume_prompt_overlay(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_external_asset(
        "https://wugecdn.steam.fun/courses/demo/data/player.js",
        (
            'class Gr{constructor(){this.Iw="never"}wu(){return this.Iw}}'
            'if("resumePlayback"==a.action()&&"prompt"==this.G.settings().Vc().wu()){'
            'FM(this.Gk,{mn:"PB_RESUME_PRESENTATION_WINDOW_TEXT"}).then(e=>e)}'
        ).encode("utf-8"),
        headers={"content-type": "application/javascript"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_external/wugecdn.steam.fun/courses/demo/data/player.js")

    assert response.status_code == 200
    assert '&&"prompt"==this.G.settings().Vc().wu()' not in response.text
    assert '&&"never"==this.G.settings().Vc().wu()' in response.text
    assert 'wu(){return this.Iw}' not in response.text
    assert 'wu(){return "never"}' in response.text


def test_same_origin_app_js_disables_version_reload_loop(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_origin_asset(
        "https://steam.fun/js/app.test.js",
        (
            'function ye(){try{fetch("/version.json?v="+Date.now()).then(e=>200===e.status?e.json():null)'
            '.then(e=>{e&&"v1778659402095"!=e.version&&window.location.reload()})}catch(e){console.log(e)}}'
        ).encode("utf-8"),
        headers={"content-type": "application/javascript"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/js/app.test.js")

    assert response.status_code == 200
    assert 'window.location.reload()' not in response.text
    assert 'e&&"v1778659402095"!=e.version&&void 0' in response.text


def test_same_origin_asset_with_encoded_capture_path_is_served(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_origin_asset(
        "https://steam.fun/img/%E8%AF%BE%E5%A0%82%E6%88%90%E6%9E%9C.png",
        b"same-origin-icon",
        headers={"content-type": "image/png"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/img/%E8%AF%BE%E5%A0%82%E6%88%90%E6%9E%9C.png")

    assert response.status_code == 200
    assert response.content == b"same-origin-icon"
    assert response.headers["content-type"].startswith("image/png")


def test_same_origin_teachppt_icon_falls_back_to_external_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_external_asset(
        "https://wugecdn.steam.fun/resources/static/teachppt/%E8%AF%BE%E5%A0%82%E6%88%90%E6%9E%9C.png",
        b"teachppt-icon",
        headers={"content-type": "image/png"},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/img/%E8%AF%BE%E5%A0%82%E6%88%90%E6%9E%9C.png")

    assert response.status_code == 200
    assert response.content == b"teachppt-icon"
    assert response.headers["content-type"].startswith("image/png")


def test_external_summerwatermelon_sjr_falls_back_to_local_sq_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    relative_path = "external/jrcodework.oss-cn-zhangjiakou.aliyuncs.com/__hashed__/local-sjr.sjr"
    body_path = tmp_path / relative_path
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_bytes(b"local-sjr")
    with store._connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO assets (url, local_path, status, content_type, sha256)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "https://jrcodework.oss-cn-zhangjiakou.aliyuncs.com/"
                "CourseTemplate/courses/a_jrcode_course/ac_shortTerm_course/"
                "Jrcode_202505_SQ/sjr/"
                "%E8%A5%BF%E7%93%9C%E9%A3%8E%E6%89%87%E5%A4%A7%E4%BD%9C%E6%88%98(%E5%AE%8C%E6%95%B4%E7%89%88).sjr",
                relative_path,
                200,
                "application/octet-stream",
                "test-sha",
            ),
        )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/jrcodework.oss-cn-zhangjiakou.aliyuncs.com/"
        "CourseTemplate/courses/a_jrcode_course/ac_shortTerm_course/"
        "Jrcode_202505_SummerWatermelon/sjr/"
        "%E8%A5%BF%E7%93%9C%E9%A3%8E%E6%89%87%E5%A4%A7%E4%BD%9C%E6%88%98%28%E5%AE%8C%E6%95%B4%E7%89%88%29.sjr"
    )

    assert response.status_code == 200
    assert response.content == b"local-sjr"
    assert response.headers["content-type"].startswith("application/octet-stream")


def test_same_origin_crocodile02_svg_falls_back_to_crocodile05(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    fallback_path = tmp_path / "origin" / "steam.fun" / "jrcode" / "svglibrary" / "Crocodile05.svg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text("<svg id='crocodile-05'></svg>", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/jrcode/svglibrary/Crocodile02.svg")

    assert response.status_code == 200
    assert "crocodile-05" in response.text
    assert response.headers["content-type"].startswith("image/svg+xml")


def test_same_origin_missing_svg_library_asset_uses_placeholder(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/jrcode/svglibrary/Course1_01_b.svg")

    assert response.status_code == 200
    assert "Course1_01_b" in response.text
    assert response.headers["content-type"].startswith("image/svg+xml")


def test_external_course_data_asset_falls_back_to_sibling_lesson_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    sibling_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "demo-course"
        / "index"
        / "lesson-b"
        / "data"
        / "jquery.min.js"
    )
    sibling_path.parent.mkdir(parents=True, exist_ok=True)
    sibling_path.write_text("console.log('sibling jquery');", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/"
        "courses/demo-course/index/lesson-a/data/jquery.min.js"
    )

    assert response.status_code == 200
    assert "sibling jquery" in response.text
    assert response.headers["content-type"].startswith("text/javascript") or response.headers["content-type"].startswith(
        "application/javascript"
    )


def test_external_course_data_asset_fetch_uses_lesson_page_referer(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)
    seen_requests: list[tuple[str, dict[str, str]]] = []

    def fake_get(url: str, headers: dict[str, str], timeout: int = 60, stream: bool = False):
        seen_requests.append((url, dict(headers)))
        return FakeResponse(content=b"body{color:red;}", content_type="text/css")

    monkeypatch.setattr("steamfun_mirror.server.requests.get", fake_get)
    client = TestClient(create_app(tmp_path, allow_live_proxy=True))

    response = client.get("/_external/wugecdn.steam.fun/courses/demo-course/index/lesson-a/data/slide1.css")

    assert response.status_code == 200
    assert response.text == "body{color:red;}"
    assert seen_requests == [
        (
            "https://wugecdn.steam.fun/courses/demo-course/index/lesson-a/data/slide1.css",
            {
                "User-Agent": seen_requests[0][1]["User-Agent"],
                "Accept": "*/*",
                "Referer": "https://wugecdn.steam.fun/courses/demo-course/index/lesson-a/index.html",
                "Origin": "https://wugecdn.steam.fun",
            },
        )
    ]


def test_external_course_data_asset_falls_back_to_subject_wide_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    fallback_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "b_scratch_course"
        / "bb_general_course"
        / "version3.0"
        / "aa_01_part1_40"
        / "index"
        / "40绘画的艺术"
        / "data"
        / "player.js"
    )
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text("console.log('subject-wide player');", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/"
        "courses/b_scratch_course/bb_general_course/version3.0/"
        "aa_02_part41-80/index/46经典接鸡蛋/data/player.js"
    )

    assert response.status_code == 200
    assert "subject-wide player" in response.text
    assert response.headers["content-type"].startswith("text/javascript") or response.headers["content-type"].startswith(
        "application/javascript"
    )


def test_external_course_data_asset_falls_back_to_nested_index_data_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    fallback_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "b_scratch_course"
        / "bb_general_course"
        / "version3.0"
        / "aa_02_part41-80"
        / "index"
        / "46经典接鸡蛋"
        / "46经典接鸡蛋备份"
        / "data"
        / "player.js"
    )
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text("console.log('nested index player');", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/"
        "courses/b_scratch_course/bb_general_course/version3.0/"
        "aa_02_part41-80/index/46%E7%BB%8F%E5%85%B8%E6%8E%A5%E9%B8%A1%E8%9B%8B/data/player.js"
    )

    assert response.status_code == 200
    assert "nested index player" in response.text
    assert response.headers["content-type"].startswith("text/javascript") or response.headers["content-type"].startswith(
        "application/javascript"
    )


def test_external_course_slide_asset_does_not_fall_back_to_sibling_lesson_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    sibling_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "demo-course"
        / "index"
        / "lesson-b"
        / "data"
        / "slide1.js"
    )
    sibling_path.parent.mkdir(parents=True, exist_ok=True)
    sibling_path.write_text("console.log('wrong sibling slide');", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/"
        "courses/demo-course/index/lesson-a/data/slide1.js"
    )

    assert response.status_code == 404


def test_external_course_slide_asset_does_not_fall_back_to_subject_wide_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    fallback_path = (
        tmp_path
        / "external"
        / "wugecdn.steam.fun"
        / "courses"
        / "b_scratch_course"
        / "bb_general_course"
        / "version3.0"
        / "aa_01_part1_40"
        / "index"
        / "lesson-a"
        / "data"
        / "slide1.js"
    )
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text("console.log('wrong subject slide');", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/_external/wugecdn.steam.fun/"
        "courses/b_scratch_course/bb_general_course/version3.0/"
        "aa_02_part41-80/index/lesson-b/data/slide1.js"
    )

    assert response.status_code == 404


def test_external_host_root_falls_back_to_cms_landing_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    fallback_path = tmp_path / "external" / "ceic.kpcb.org.cn" / "cms"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text("<html><body>ceic cms landing</body></html>", encoding="utf-8")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_external/ceic.kpcb.org.cn/")

    assert response.status_code == 200
    assert "ceic cms landing" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_tch_work_self_remark_local_fallback_supports_crud(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    empty = client.get("/api/tchWorkSelfRemark/get")
    assert empty.status_code == 200
    assert empty.json() == {
        "success": True,
        "content": {"tchWorkSelfRemarkList": []},
        "error": {"message": "", "code": ""},
    }

    created = client.post("/api/tchWorkSelfRemark/createOrUpdate", data={"remark": "优秀示例"})
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["success"] is True
    created_id = created_payload["content"]["id"]
    assert created_payload["content"]["remark"] == "优秀示例"

    listed = client.get("/api/tchWorkSelfRemark/get")
    assert listed.status_code == 200
    assert listed.json()["content"]["tchWorkSelfRemarkList"] == [{"id": created_id, "remark": "优秀示例"}]

    updated = client.post(
        "/api/tchWorkSelfRemark/createOrUpdate",
        data={"remark_id": str(created_id), "remark": "更新后的评语"},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == {"id": created_id, "remark": "更新后的评语"}

    deleted = client.post("/api/tchWorkSelfRemark/delete", data={"remark_id": str(created_id)})
    assert deleted.status_code == 200
    assert deleted.json()["content"] == {"deleted": True}

    final_list = client.get("/api/tchWorkSelfRemark/get")
    assert final_list.status_code == 200
    assert final_list.json()["content"]["tchWorkSelfRemarkList"] == []


def test_local_student_create_fallback_persists_and_appears_in_campus_user_list(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, school_info={"name": "默认校区", "eduDomain": "lqx"})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/user/list?campusId=851",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {"campusUserList": []},
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    created = client.post(
        "/java-api/school/stu/create?t=1",
        json={
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "autoaccept123",
            "realName": "自动验收学员",
            "sex": "男",
            "parentAPhoneNum": "13800138000",
            "schoolName": "本地验收学校",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-13",
        },
    )

    assert created.status_code == 200
    assert created.json()["success"] is True
    created_id = created.json()["content"]["studentId"]

    listed = client.get("/api/get/campus/user/list?campusId=851", headers={"Authorization": "Bearer teacher-token"})

    assert listed.status_code == 200
    campus_user_list = listed.json()["content"]["campusUserList"]
    assert campus_user_list[0]["id"] == created_id
    assert campus_user_list[0]["name"] == "autoaccept123"
    assert campus_user_list[0]["studentUserInfo"]["realname"] == "自动验收学员"


def test_local_wechat_qr_fallback_takes_precedence_over_live_proxy(tmp_path: Path, monkeypatch) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)

    async def _fail_proxy(*args, **kwargs):
        raise AssertionError("local fallback should resolve before live proxy")

    monkeypatch.setattr(server_module, "_proxy_and_cache", _fail_proxy)
    client = TestClient(create_app(tmp_path, allow_live_proxy=True))

    response = client.get("/api/wechat/get/qr/code?t=1&stuId=2001")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert isinstance(response.json()["content"]["qucodeData"]["data"], list)
    assert len(response.json()["content"]["qucodeData"]["data"]) > 0


def test_student_management_auth_and_unbind_overlay_rewrites_replayed_payloads(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_management_captures(tmp_path, stu_id=2001)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    updated = client.post(
        "/java-api/school/stu/updateAuth?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001, "zoneAuth": 0, "ojAuth": 1, "pAuth": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == {"is_update": True}

    queried = client.post(
        "/java-api/school/stu/queryClsStuMsg?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001},
    )
    assert queried.status_code == 200
    assert queried.json()["content"]["zoneAuth"] == 0
    assert queried.json()["content"]["ojAuth"] == 1
    assert queried.json()["content"]["pAuth"] == 1

    unbound = client.post(
        "/api/delete/stu/user/openid?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001},
    )
    assert unbound.status_code == 200
    assert unbound.json()["content"] == {"is_delete": True}

    listed = client.post(
        "/java-api/school/stu/selectStudy?t=4",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert listed.status_code == 200
    row = listed.json()["content"]["content"][0]
    assert row["stuId"] == 2001
    assert row["openId"] is None
    assert row["parentWeChat"] == server_module.DEFAULT_UNBOUND_TEXT


def test_student_management_quit_back_delete_and_resetpwd_persist_overlay_state(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_management_captures(tmp_path, stu_id=2001)
    store = MirrorStore(tmp_path)
    campus_user_list = [{"studentUserInfo": {"realname": "自动验收学员"}}]
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    reset_pwd = client.post(
        "/java-api/school/stu/resetPwd?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"id": 2001},
    )
    assert reset_pwd.status_code == 200
    assert reset_pwd.json()["content"] == {"is_update": True}
    overlay = store.get_student_overlay(2001)
    assert overlay is not None
    assert overlay["last_password_reset_at"]

    quit_response = client.post(
        "/java-api/school/stu/quit?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001},
    )
    assert quit_response.status_code == 200
    assert quit_response.json()["content"] == {"is_quit": True}

    after_quit = client.post(
        "/java-api/school/stu/selectStudy?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert after_quit.status_code == 200
    assert after_quit.json()["content"]["content"] == []
    assert after_quit.json()["content"]["totalSize"] == 0

    history_after_quit = client.post(
        "/java-api/school/stu/selectStuOut?t=3b",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert history_after_quit.status_code == 200
    assert history_after_quit.json()["content"]["content"][0]["stuId"] == 2001
    assert history_after_quit.json()["content"]["totalSize"] == 1

    back_response = client.post(
        "/java-api/school/stu/back?t=4",
        headers={"Authorization": "Bearer teacher-token"},
        json={"stuId": 2001},
    )
    assert back_response.status_code == 200
    assert back_response.json()["content"] == {"is_back": True}

    after_back = client.post(
        "/java-api/school/stu/selectStudy?t=5",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert after_back.status_code == 200
    assert after_back.json()["content"]["content"][0]["stuId"] == 2001

    history_after_back = client.post(
        "/java-api/school/stu/selectStuOut?t=5b",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert history_after_back.status_code == 200
    assert history_after_back.json()["content"]["content"] == []
    assert history_after_back.json()["content"]["totalSize"] == 0

    batch_deleted = client.post(
        "/java-api/school/stu/batchDelete?t=6",
        headers={"Authorization": "Bearer teacher-token"},
        json=[2001],
    )
    assert batch_deleted.status_code == 200
    assert batch_deleted.json()["content"] == {"2001": None}

    after_delete = client.post(
        "/java-api/school/stu/selectStudy?t=7",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )
    assert after_delete.status_code == 200
    assert after_delete.json()["content"]["content"] == []
    assert after_delete.json()["content"]["totalSize"] == 0
    assert campus_user_list[0]["studentUserInfo"]["realname"] == "自动验收学员"


def test_teacher_auth_bootstrap_populates_selected_schools_and_campus_ids(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"}, school_info={"name": "Mirror School"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)

    bootstrap = server_module._build_teacher_auth_bootstrap(store)

    assert bootstrap is not None
    match = re.search(r"var data=(.*?);try\{localStorage", bootstrap)
    assert match is not None
    state = json.loads(match.group(1))
    assert state["user"]["selected_schools"] == [851]
    assert state["user"]["schoolInfo"]["eduCampusId"] == 851
    assert state["user"]["userInfo"]["educationalInstitutionCampusId"] == 851


def test_invalid_token_subject_list_uses_local_catalog(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(tmp_path, "https://steam.fun/api/get/school/subject/list?t=1")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/api/get/school/subject/list?t=1", headers={"Authorization": "Bearer teacher-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    subject_ids = {item["id"] for item in payload["content"]["subjectList"]}
    assert {1, 3}.issubset(subject_ids)


def test_get_subject_uses_local_catalog(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/api/getSubject?t=1&curriculum_type=1", headers={"Authorization": "Bearer teacher-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    subject_ids = {item["id"] for item in payload["content"]["subjectList"]}
    assert {1, 3}.issubset(subject_ids)


def test_get_subject_and_curriculum_list_for_class_add_lesson_uses_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getSubjectAndCurriculumListForClassAddLesson?t=1",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert any(row["id"] == 1 for row in payload["content"]["subjectList"])
    assert any(row["id"] == 501 for row in payload["content"]["curriculumList"])


def test_get_subject_and_curriculum_list_for_class_add_lesson_filters_subject_ids(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getSubjectAndCurriculumListForClassAddLesson?t=1&subject_ids=%5B1%5D",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    rows = payload["content"]["curriculumList"]
    assert rows
    assert {row["subject_id"] for row in rows} == {1}
    assert any(row["id"] == 501 for row in rows)
    assert all(row["subjectName"] == "Jrcode" for row in rows)


def test_get_subject_and_curriculum_list_for_class_add_lesson_uses_referer_class_context(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9002, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "adminToken": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9002, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    store.upsert_local_class(
        {
            "id": 3901,
            "className": "Referer Scoped Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getSubjectAndCurriculumListForClassAddLesson?t=1&userId=12385&subject_ids=&curriculum_type=",
        headers={
            "Authorization": "Bearer teacher-token",
            "Referer": "http://testserver/school-home-page/class-management1/divide-class1?id=3901&campus_id=851&lecturer_id=12385",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    subject_rows = payload["content"]["subjectList"]
    curriculum_rows = payload["content"]["curriculumList"]
    assert {row["id"] for row in subject_rows} == {1}
    assert {row["id"] for row in curriculum_rows} == {501}
    assert {row["subject_id"] for row in curriculum_rows} == {1}


def test_zone_subject_list_augments_python_and_cpp_from_local_catalog(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/zone/school/subject/list?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "subjectList": [
                        {"id": 1, "name": "Jrcode", "code": 1, "sort_num": 1, "state": 1, "is_vaild": True},
                        {"id": 2, "name": "Scratch", "code": 2, "sort_num": 2, "state": 1, "is_vaild": True},
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/api/get/zone/school/subject/list?t=1", headers={"Authorization": "Bearer teacher-token"})

    assert response.status_code == 200
    subject_rows = response.json()["content"]["subjectList"]
    subject_ids = {item["id"] for item in subject_rows}
    assert {1, 2, 3, 4}.issubset(subject_ids)
    assert next(item for item in subject_rows if item["id"] == 3)["name"] == "Python"
    assert next(item for item in subject_rows if item["id"] == 4)["name"] == "C++"


def test_teacher_subject_catalog_replaces_placeholder_subject_name_with_default_label(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/campus/subject/list?t=1&campusId=851",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "campusSubjectList": [
                        {"id": 1, "name": "Jrcode", "code": 1, "sort_num": 1, "state": 1, "is_vaild": True},
                        {"id": 2, "name": "Scratch", "code": 2, "sort_num": 2, "state": 1, "is_vaild": True},
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/teaching/plan/list?page_no=1&page_size=20",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "teachingPlan": [
                        {
                            "id": 3901,
                            "subject_id": 3,
                            "curriculum_class_id": 8101,
                            "classInfo": {
                                "id": 8101,
                                "name": "Python Class",
                                "subjectInfoList": [],
                            },
                        }
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    subject_rows = server_module._teacher_subject_catalog(store)

    assert next(item for item in subject_rows if item["id"] == 3)["name"] == "Python"


def test_invalid_token_curriculum_title_list_uses_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/all/campus/all/curriculum/title/list?t=1&campusIds=[851]",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/all/campus/all/curriculum/title/list?t=1&campusIds=%5B851%5D",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    rows = response.json()["content"]["campusCurriculumList"]
    assert [row["id"] for row in rows] == [501, 901]
    assert rows[0]["subjectName"] == "Jrcode"


def test_invalid_token_platform_curriculum_uses_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/curriculum/list?t=1&subject_id=&teaching_type=&curriculum_type=&page_no=1&page_size=20",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/curriculum/list?t=1&subject_id=&teaching_type=&curriculum_type=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["total"] == 2
    assert content["curriculum_list"][0]["subjectName"] == "Jrcode"
    assert content["curriculumList"][1]["title"] == "Python图形化"


def test_invalid_token_admin_curriculum_detail_uses_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/get/curriculum?curriculum_id=501",
        profile_name="admin",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/curriculum?curriculum_id=501",
        headers={"Referer": "http://127.0.0.1:8000/background/course-management/preview-curriculum?id=501"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert len(content["curriculum"]) == 1
    assert content["curriculum"][0]["id"] == 501
    assert content["curriculum"][0]["subject_id"] == 1
    assert content["curriculum"][0]["title"] == "编程启蒙J1/J2"
    assert content["curriculum"][0]["curriculum_desc"] == "启蒙课程"
    assert content["curriculum"][0]["number_of_courses"] == 32
    assert content["curriculum"][0]["img_url"] == "/_external/cdn.example.com/curriculum-j1.png"
    assert content["curriculum"][0]["curriculum_data_url"] == "[]"
    assert [row["id"] for row in content["curriculum_material_list"]] == [7001, 7002]
    assert content["curriculum_material_list"][0]["ppt_url"] == "/_external/cdn.example.com/lesson-1/index.html"
    assert content["curriculum_material_list"][1]["img_url"] == "/_external/cdn.example.com/lesson-2.png"


def test_runtime_patch_reroutes_admin_preview_course_to_local_ppt_route() -> None:
    source = (
        'var existing="/code-classroom/prepare-lessons/prepare/ppt";'
        'PreviewCourse(u){console.log("超管审核课程"),console.log(u),'
        'this.$router.push({name:"look-curriculum",params:{curriculumMaterial:u}})}'
    )

    patched = server_module._patch_known_frontend_runtime(source, "application/javascript; charset=utf-8")

    assert 'name:"look-curriculum"' not in patched
    assert '/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id=' in patched
    assert 'teaching_plan_id=999999' in patched
    assert "window.location.assign(" in patched


def test_javascript_bundle_with_admin_preview_old_route_still_flags_for_rewrite() -> None:
    body = (
        b'PreviewCourse(u){console.log("admin"),'
        b'this.$router.push({name:"look-curriculum",params:{curriculumMaterial:u}})}'
    )

    assert server_module._body_might_need_rewrite(body, "application/javascript; charset=utf-8") is True


def test_invalid_token_teacher_curriculum_uses_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/tch/get/tch/curriculum?t=1&subject_id=1&teaching_type=&course_type=&curriculumTitle=&lessonTitle=&page_no=1&page_size=20",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/get/tch/curriculum?t=1&subject_id=1&teaching_type=&course_type=&curriculumTitle=&lessonTitle=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["total"] == 1
    row = content["curriculumList"][0]
    assert row["id"] == 501
    assert row["curriculumMaterialNum"] == 2
    assert row["lessonTitleList"] == ["初次挑战", "动画进阶"]


def test_invalid_token_teacher_classlist_prefers_local_teacher_rows_over_student_empty(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(
        tmp_path,
        "https://steam.fun/api/tch/class/get/classlist?t=1&subject_id=&teaching_type=&course_state=&course_week=&course_time=&end_class_state=1&name=&page_no=1&page_size=8",
    )
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "student",
        method="GET",
        url="https://steam.fun/api/tch/class/get/classlist?t=1&subject_id=&teaching_type=&course_state=&course_week=&course_time=&end_class_state=1&name=&page_no=1&page_size=8",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {"success": True, "content": {"userSubject": [], "classlist": [], "classlist_total": 0, "page_no": 1, "page_size": 8}},
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/class/get/classlist?t=1&subject_id=&teaching_type=&course_state=&course_week=&course_time=&end_class_state=1&name=&page_no=1&page_size=8",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["classlist_total"] == 1
    assert content["classlist"][0]["name"] == "周一19:00 Python"
    assert content["classlist"][0]["subjectNameList"] == ["Python"]


def test_student_myclass_classlist_prefers_local_student_rows_over_cached_empty_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    _store_runtime_student_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "student",
        method="GET",
        url=(
            "https://steam.fun/api/tch/class/get/classlist"
            "?t=1&end_class_state=0&week_json=[]&subject_id=&teaching_type="
            "&course_state=&course_week=&course_time=&name=&page_no=1&page_size=16"
        ),
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "userSubject": [],
                    "classlist": [],
                    "classlist_total": 0,
                    "page_no": 1,
                    "page_size": 16,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        (
            "/api/tch/class/get/classlist"
            "?t=1&end_class_state=0&week_json=[]&subject_id=&teaching_type="
            "&course_state=&course_week=&course_time=&name=&page_no=1&page_size=16"
        ),
        headers={"Authorization": "Bearer student-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["classlist_total"] == 1
    assert {row["name"] for row in content["classlist"]} == {"周日18:30 Jrcode"}
    assert {row["id"] for row in content["userSubject"]} == {1}


def test_invalid_token_educational_institution_info_uses_local_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385}, school_info={"name": "Mirror School", "is_encryption": True})
    _store_teacher_course_chain_captures(tmp_path)
    _store_invalid_token_response(tmp_path, "https://steam.fun/api/get/educational_institution_info?t=1")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/educational_institution_info?t=1",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["eduCampusId"] == 851
    assert content["educational_institution_obj"][0]["is_encryption"] is True
    assert content["educational_institution_class_day_list"] == []


def test_local_teaching_plan_student_list_fallback_returns_rollcall_shape(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "mirror-local-1",
            "realName": "Local Mirror Student",
            "sex": "男",
            "parentAPhoneNum": "13800138000",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getTeachingPlanStuListWithXmArr?t=1&teachingPlanId=81001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert {"curriculumClassInfo", "stuPlanList", "tchPlanInfo"}.issubset(content)
    assert content["tchPlanInfo"]["id"] == 81001
    assert content["curriculumClassInfo"]["lesson_hour"] == 1
    row = content["stuPlanList"][0]
    assert row["studentInfo"]["studentUserInfo"]["realname"] == "Local Mirror Student"
    assert row["studentInfo"]["name"] == "mirror-local-1"
    assert row["sign_state"] is None
    assert row["stu_tch_plan_type"] == 1


def test_local_class_student_list_fallback_uses_cached_class_capture_with_filtering(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/class/student/list?classId=3001&realname=&page_no=1&page_size=100",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "studentList": [
                        {
                            "id": 9001,
                            "student_user_id": 2001,
                            "curriculum_class_id": 3001,
                            "studentInfo": {
                                "id": 2001,
                                "name": "mirror-stu-1",
                                "headimg_url": "https://cdn.example.com/student-1.png",
                                "studentUserInfo": {"realname": "Mirror Student One"},
                            },
                            "missStuTchPlanNum": 0,
                            "missStuTchPlanArr": [],
                        },
                        {
                            "id": 9002,
                            "student_user_id": 2002,
                            "curriculum_class_id": 3001,
                            "studentInfo": {
                                "id": 2002,
                                "name": "mirror-stu-2",
                                "headimg_url": "https://cdn.example.com/student-2.png",
                                "studentUserInfo": {"realname": "Another Student"},
                            },
                            "missStuTchPlanNum": 1,
                            "missStuTchPlanArr": [],
                        },
                    ],
                    "page_no": 1,
                    "page_size": 100,
                    "total": 2,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/class/student/list?t=1&classId=3001&realname=Mirror&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["total"] == 1
    assert content["studentList"][0]["studentInfo"]["studentUserInfo"]["realname"] == "Mirror Student One"
    assert content["studentList"][0]["studentInfo"]["headimg_url"].startswith("/_external/")
    assert content["totalSize"] == 1
    assert content["content"][0]["stuName"] == "Mirror Student One"
    assert content["content"][0]["account"] == "mirror-stu-1"


def test_local_class_student_list_returns_flat_content_for_class_detail_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/class/student/list?classId=3001&realname=&page_no=1&page_size=100",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "studentList": [
                        {
                            "id": 9001,
                            "student_user_id": 2001,
                            "curriculum_class_id": 3001,
                            "created_time": "2026-05-18 10:00:00",
                            "in_class_date": "2026-05-18 10:00:00",
                            "studentInfo": {
                                "id": 2001,
                                "name": "mirror-stu-1",
                                "wallet": 9,
                                "oj_analysis_auth": True,
                                "oj_auth": False,
                                "p_auth": True,
                                "stu_note_auth": True,
                                "test_auth": True,
                                "zone_auth": False,
                                "oj_testcase_auth": False,
                                "educational_institution_campus_id": 851,
                                "phone_num": "13800138000",
                                "studentUserInfo": {
                                    "realname": "Mirror Student One",
                                    "sex": "F",
                                    "parent_a": "妈妈",
                                    "parent_a_phone_num": "13800138000",
                                },
                            },
                            "missStuTchPlanNum": 0,
                            "missStuTchPlanArr": [],
                        }
                    ],
                    "page_no": 1,
                    "page_size": 100,
                    "total": 1,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/class/student/list?t=1&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["totalSize"] == 1
    assert content["content"][0]["stuId"] == 2001
    assert content["content"][0]["account"] == "mirror-stu-1"
    assert content["content"][0]["starNum"] == 9
    assert content["content"][0]["stuName"] == "Mirror Student One"
    assert content["content"][0]["phoneNum"] == "13800138000"


def test_teacher_like_admin_token_uses_teacher_local_class_fallbacks(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, username="zhaosenlin", token="teacher-token", user_info={"id": 12385, "realName": "Teacher Li"})
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="18164173640",
        password_hash="admin-hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"authTree": '{"children":[]}', "token": "admin-token"},
        fresh_auth={
            "identity": 1,
            "userInfo": {"id": 9002, "realName": "Admin Realname"},
            "schoolInfo": {"eduCampusId": 851},
            "roleList": [],
        },
        vuex_state={
            "user": {
                "token": "admin-token",
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": {"id": 9002, "realName": "Admin Realname"},
                "schoolInfo": {"eduCampusId": 851},
                "identity": 1,
            }
        },
    )
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/class/student/list?classId=3001&realname=&page_no=1&page_size=100",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "studentList": [
                        {
                            "id": 9001,
                            "student_user_id": 2001,
                            "curriculum_class_id": 3001,
                            "studentInfo": {
                                "id": 2001,
                                "name": "mirror-stu-1",
                                "headimg_url": "https://cdn.example.com/student-1.png",
                                "studentUserInfo": {"realname": "Mirror Student One"},
                            },
                            "missStuTchPlanNum": 0,
                            "missStuTchPlanArr": [],
                        }
                    ],
                    "page_no": 1,
                    "page_size": 100,
                    "total": 1,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/class/student/list?t=1&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["total"] == 1
    assert content["studentList"][0]["studentInfo"]["studentUserInfo"]["realname"] == "Mirror Student One"


def test_local_teaching_plan_by_class_id_fallback_uses_cached_capture_with_filters(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/teaching/plan/by/class/id?classes_id=3001&title=&sign_state=",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "teaching_plan_list": [
                        {
                            "id": 81001,
                            "curriculum_class_id": 3001,
                            "sign_state": 1,
                            "sign_state_new": 2,
                            "subject_id": 3,
                            "subject_name": "Python",
                            "lessionInfo": {
                                "title": "Python Intro",
                                "img_url": "https://cdn.example.com/python-intro.png",
                            },
                            "stuTchPlanArr": [{"sign_state": 1}, {"sign_state": 2}],
                            "expected_count": 2,
                            "actual_count": 1,
                        },
                        {
                            "id": 81002,
                            "curriculum_class_id": 3001,
                            "sign_state": 2,
                            "sign_state_new": 2,
                            "subject_id": 1,
                            "subject_name": "Jrcode",
                            "lessionInfo": {
                                "title": "Jrcode Warmup",
                                "img_url": "https://cdn.example.com/jrcode-warmup.png",
                            },
                            "stuTchPlanArr": [{"sign_state": 2}],
                            "expected_count": 1,
                            "actual_count": 0,
                        },
                    ]
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/teaching/plan/by/class/id?t=1&classes_id=3001&title=Python&sign_state=1",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert len(content["teaching_plan_list"]) == 1
    assert content["teaching_plan_list"][0]["id"] == 81001
    assert content["teaching_plan_list"][0]["lessionInfo"]["img_url"].startswith("/_external/")


def test_teacher_classlist_includes_local_class_without_existing_teaching_plan(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.upsert_local_class(
        {
            "id": 3901,
            "className": "Local Empty Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [3],
            "week_str": "Wed",
            "time_str": "18:00-19:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/class/get/classlist?t=1&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    rows = response.json()["content"]["classlist"]
    target = next(row for row in rows if row["id"] == 3901)
    assert target["name"] == "Local Empty Class"
    assert target["tchPlanNum"] == 0
    assert target["subjectIdList"] == [1]
    assert target["curriculumIdList"] == [501]


def test_add_and_change_student_class_relations_persist_locally(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "class-flow-1",
            "realName": "Class Flow One",
            "sex": "M",
            "parentAPhoneNum": "13800138121",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    student_id = student["id"]
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    added = client.post(
        "/api/add/student/class/relation?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classId": 3001, "stuIds": [student_id]},
    )
    assert added.status_code == 200

    class_3001_after_add = client.get(
        f"/api/get/class/student/list?t=2&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert class_3001_after_add.status_code == 200
    class_3001_rows = class_3001_after_add.json()["content"]["studentList"]
    assert [row["student_user_id"] for row in class_3001_rows] == [student_id]

    changed = client.post(
        "/api/change/stu/class?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"oldClassId": 3001, "classId": 3002, "stuIds": [student_id]},
    )
    assert changed.status_code == 200

    class_3001_after_change = client.get(
        f"/api/get/class/student/list?t=4&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    class_3002_after_change = client.get(
        f"/api/get/class/student/list?t=5&classId=3002&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert class_3001_after_change.status_code == 200
    assert class_3002_after_change.status_code == 200
    assert class_3001_after_change.json()["content"]["studentList"] == []
    assert [row["student_user_id"] for row in class_3002_after_change.json()["content"]["studentList"]] == [student_id]

    deleted = client.post(
        "/api/del/student/class/relation?t=6",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classId": 3002, "stuIds": [student_id]},
    )
    assert deleted.status_code == 200

    class_3002_after_delete = client.get(
        f"/api/get/class/student/list?t=7&classId=3002&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert class_3002_after_delete.status_code == 200
    assert class_3002_after_delete.json()["content"]["studentList"] == []


def test_add_student_class_relation_accepts_divide_page_student_data_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "divide-add-payload",
            "realName": "Divide Add Payload",
            "sex": "F",
            "parentAPhoneNum": "13800138137",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    student_id = student["id"]
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    added = client.post(
        "/api/add/student/class/relation?t=divide",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "studentDataArr": json.dumps(
                [
                    {
                        "student_user_id": student_id,
                        "receiptGoodsId": student_id * 10 + 1,
                    }
                ]
            ),
            "curriculum_class_id": 3001,
            "addToOldPlan": 0,
        },
    )

    assert added.status_code == 200
    added_payload = added.json()["content"]
    assert added_payload["is_create"] is True
    assert added_payload["failarr"] == []
    assert added_payload["failArr"] == []
    assert added_payload["updatedStuIds"] == [student_id]

    class_after_add = client.get(
        "/api/get/class/student/list?t=after-add&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert class_after_add.status_code == 200
    assert [row["student_user_id"] for row in class_after_add.json()["content"]["studentList"]] == [student_id]


def test_change_student_class_accepts_divide_page_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "normalState": "1",
            "name": "divide-change-payload",
            "realName": "Divide Change Payload",
            "sex": "F",
            "parentAPhoneNum": "13800138122",
            "studyDate": "2026-05-16",
        }
    )
    student_id = student["id"]
    store.upsert_local_class_student_relation(
        class_id=3001,
        student_user_id=student_id,
        in_class_date="2026-05-16",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    changed = client.post(
        "/api/change/stu/class?t=divide",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "student_user_id": student_id,
            "now_class_id": 3001,
            "change_class_id": 3002,
            "addToOldPlan": 0,
        },
    )

    assert changed.status_code == 200
    changed_payload = changed.json()["content"]
    assert changed_payload["is_change"] is True
    assert changed_payload["sourceClassId"] == 3001
    assert changed_payload["targetClassId"] == 3002
    assert changed_payload["updatedStuIds"] == [student_id]

    class_3001_after_change = client.get(
        f"/api/get/class/student/list?t=source&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    class_3002_after_change = client.get(
        f"/api/get/class/student/list?t=target&classId=3002&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert class_3001_after_change.status_code == 200
    assert class_3002_after_change.status_code == 200
    assert class_3001_after_change.json()["content"]["studentList"] == []
    assert [row["student_user_id"] for row in class_3002_after_change.json()["content"]["studentList"]] == [student_id]


def test_del_student_class_relation_accepts_divide_page_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "normalState": "1",
            "name": "divide-remove-payload",
            "realName": "Divide Remove Payload",
            "sex": "M",
            "parentAPhoneNum": "13800138123",
            "studyDate": "2026-05-16",
        }
    )
    student_id = student["id"]
    store.upsert_local_class_student_relation(
        class_id=3001,
        student_user_id=student_id,
        in_class_date="2026-05-16",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    deleted = client.post(
        "/api/del/student/class/relation?t=divide",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "studentIds": json.dumps([student_id]),
            "curriculum_class_id": 3001,
        },
    )

    assert deleted.status_code == 200
    deleted_payload = deleted.json()["content"]
    assert deleted_payload["is_delete"] is True
    assert deleted_payload["failArr"] == []
    assert deleted_payload["updatedStuIds"] == [student_id]
    assert deleted_payload["successCount"] == 1

    class_after_delete = client.get(
        f"/api/get/class/student/list?t=after-delete&classId=3001&realname=&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert class_after_delete.status_code == 200
    assert class_after_delete.json()["content"]["studentList"] == []


def test_xm_account_endpoints_use_local_student_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "finance-local-1",
            "realName": "Finance Local One",
            "sex": "M",
            "parentAPhoneNum": "13800138131",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    account_list = client.post(
        "/java-api/school/xmAccountStu/queryAccountList?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )

    assert account_list.status_code == 200
    account_rows = account_list.json()["content"]["content"]
    account_row = next(row for row in account_rows if row["student_user_id"] == student["id"])
    assert account_row["account_no"]
    assert account_row["stuNames"] == "Finance Local One"

    student_info = client.get(
        f"/api/xm/getStuInfoForFinacialPages?t=2&stuId={student['id']}",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert student_info.status_code == 200
    student_info_payload = student_info.json()["content"]
    assert "stuBuyAmount" in student_info_payload
    assert student_info_payload["xmGoodsList"][0]["id"] == student["id"] * 10 + 1

    account_info = client.get(
        f"/api/xm/getXmAccountInfoByStuId?t=3&stuId={student['id']}",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert account_info.status_code == 200
    xm_account_row = account_info.json()["content"]["xmAccountList"][0]
    assert xm_account_row["student_user_id"] == student["id"]
    assert xm_account_row["account_no"] == account_row["account_no"]


def test_curr_cls_delete_prefers_local_fallback_and_hides_deleted_class(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="POST",
        url="https://steam.fun/java-api/school/currCls/delete?t=1",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {"is_delete": False, "source": "captured"},
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    deleted = client.post(
        "/java-api/school/currCls/delete?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"id": 3001},
    )

    assert deleted.status_code == 200
    assert deleted.json()["content"]["is_delete"] is True

    classlist_response = client.get(
        "/api/tch/class/get/classlist?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert classlist_response.status_code == 200
    remaining_ids = {row["id"] for row in classlist_response.json()["content"]["classlist"]}
    assert 3001 not in remaining_ids


def test_teaching_plan_student_list_uses_local_class_membership_instead_of_all_students(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    first_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "rollcall-local-1",
            "realName": "Rollcall Local One",
            "sex": "M",
            "parentAPhoneNum": "13800138122",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "rollcall-local-2",
            "realName": "Rollcall Local Two",
            "sex": "F",
            "parentAPhoneNum": "13800138123",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class_student_relation(
        class_id=3001,
        student_user_id=first_student["id"],
        in_class_date="2026-05-16",
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getTeachingPlanStuListWithXmArr?t=1&teachingPlanId=81001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert [row["student_user_id"] for row in content["stuPlanList"]] == [first_student["id"]]


def test_add_student_to_teaching_plan_persists_to_rollcall_list(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    first_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "plan-local-1",
            "realName": "Plan Local One",
            "sex": "M",
            "parentAPhoneNum": "13800138124",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    second_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "plan-local-2",
            "realName": "Plan Local Two",
            "sex": "F",
            "parentAPhoneNum": "13800138125",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=first_student["id"], in_class_date="2026-05-16")
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=second_student["id"], in_class_date="2026-05-16")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    added = client.post(
        "/api/add/stu/to/teaching/plan?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"tchPlanId": 81001, "stuIds": [second_student["id"]]},
    )
    assert added.status_code == 200

    response = client.get(
        "/api/getTeachingPlanStuListWithXmArr?t=2&teachingPlanId=81001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert [row["student_user_id"] for row in content["stuPlanList"]] == [second_student["id"]]


def test_create_class_and_bulk_add_update_delete_teaching_plan_persist_locally(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    created = client.post(
        "/api/create/class?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "className": "Schedule Flow Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        },
    )
    assert created.status_code == 200
    created_class_id = created.json()["content"]["id"]

    classlist_response = client.get(
        "/api/tch/class/get/classlist?t=2&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert classlist_response.status_code == 200
    assert any(row["id"] == created_class_id for row in classlist_response.json()["content"]["classlist"])

    updated_class = client.post(
        "/api/update/classes?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "id": created_class_id,
            "className": "Schedule Flow Class Updated",
            "week_json": [7],
            "week_str": "Sun",
            "time_str": "10:00-11:30",
        },
    )
    assert updated_class.status_code == 200

    classlist_after_update = client.get(
        "/api/tch/class/get/classlist?t=4&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert classlist_after_update.status_code == 200
    updated_class_row = next(row for row in classlist_after_update.json()["content"]["classlist"] if row["id"] == created_class_id)
    assert updated_class_row["name"] == "Schedule Flow Class Updated"
    assert updated_class_row["week_json"] == [7]
    assert updated_class_row["time_str"] == "10:00-11:30"

    bulk_added = client.post(
        "/api/bulk/add/tch/plan/to/class?t=5",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classId": created_class_id, "lessonIds": [7001, 7002]},
    )
    assert bulk_added.status_code == 200

    plan_list_response = client.get(
        f"/api/get/teaching/plan/by/class/id?t=6&classes_id={created_class_id}&title=&sign_state=",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert plan_list_response.status_code == 200
    created_plan_rows = plan_list_response.json()["content"]["teaching_plan_list"]
    assert len(created_plan_rows) == 2
    created_plan_id = created_plan_rows[0]["id"]

    updated = client.post(
        "/api/update/teaching/plan?t=7",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "tchPlanId": created_plan_id,
            "custom_lesson_title": "Local Updated Lesson",
            "class_date": "2026-05-24",
            "start_class_date": "2026-05-24 09:00:00",
            "end_class_date": "2026-05-24 10:30:00",
            "sort_num": 9,
        },
    )
    assert updated.status_code == 200

    updated_plan_list_response = client.get(
        f"/api/get/teaching/plan/by/class/id?t=8&classes_id={created_class_id}&title=Local Updated Lesson&sign_state=",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert updated_plan_list_response.status_code == 200
    updated_rows = updated_plan_list_response.json()["content"]["teaching_plan_list"]
    assert [row["id"] for row in updated_rows] == [created_plan_id]
    assert updated_rows[0]["custom_lesson_title"] == "Local Updated Lesson"
    assert updated_rows[0]["class_date"] == "2026-05-24"

    deleted = client.post(
        "/api/delete/tch/plan?t=9",
        headers={"Authorization": "Bearer teacher-token"},
        json={"tchPlanId": created_plan_id},
    )
    assert deleted.status_code == 200

    after_delete = client.get(
        f"/api/get/teaching/plan/by/class/id?t=10&classes_id={created_class_id}&title=&sign_state=",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert after_delete.status_code == 200
    assert all(row["id"] != created_plan_id for row in after_delete.json()["content"]["teaching_plan_list"])


def test_create_class_and_bulk_add_skip_reuse_of_deleted_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)

    reusable_class_id = store.next_class_id()
    store.upsert_local_class(
        {
            "id": reusable_class_id,
            "className": "Deleted Seed Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    store.upsert_local_class({"id": reusable_class_id, "deleted": 1})

    reusable_plan_id = store.next_teaching_plan_id()
    store.upsert_local_teaching_plan(
        {
            "id": reusable_plan_id,
            "curriculum_class_id": 3001,
            "subject_id": 1,
            "curriculum_id": 501,
            "curriculum_meterial_id": 7001,
            "class_date": "2026-05-24",
            "start_class_date": "2026-05-24 09:00:00",
            "end_class_date": "2026-05-24 10:30:00",
            "sort_num": 1,
            "custom_lesson_title": "Deleted Seed Lesson",
        }
    )
    store.mark_teaching_plan_deleted(reusable_plan_id)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    created = client.post(
        "/api/create/class?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "className": "Deleted Row Reuse Guard",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        },
    )

    assert created.status_code == 200
    created_payload = created.json()["content"]
    created_class_id = created_payload["id"]
    assert created_class_id > reusable_class_id
    assert created_payload["classInfo"]["deleted"] is False

    bulk_added = client.post(
        "/api/bulk/add/tch/plan/to/class?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classId": created_class_id, "lessonIds": [7001, 7002]},
    )

    assert bulk_added.status_code == 200
    created_plan_ids = bulk_added.json()["content"]["tchPlanIds"]
    assert len(created_plan_ids) == 2
    assert len(set(created_plan_ids)) == 2
    assert min(created_plan_ids) > reusable_plan_id

    plan_list_response = client.get(
        f"/api/get/teaching/plan/by/class/id?t=3&classes_id={created_class_id}&title=&sign_state=",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert plan_list_response.status_code == 200
    created_plan_rows = plan_list_response.json()["content"]["teaching_plan_list"]
    assert len(created_plan_rows) == 2
    assert {row["id"] for row in created_plan_rows} == set(created_plan_ids)


def test_student_class_list_prefers_captured_classes_over_newer_local_audit_classes(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_runtime_student_profile(tmp_path)
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_api_response(
        "teacher",
        method="GET",
        url="https://steam.fun/api/get/class/student/list?classId=3001&realname=&page_no=1&page_size=100",
        status=200,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(
            {
                "success": True,
                "content": {
                    "studentList": [
                        {
                            "id": 9001,
                            "student_user_id": 400057,
                            "curriculum_class_id": 3001,
                            "created_time": "2026-05-18 10:00:00",
                            "in_class_date": "2026-05-18 10:00:00",
                            "studentInfo": {
                                "id": 400057,
                                "name": "lbschenmuran",
                                "headimg_url": "https://cdn.example.com/student-1.png",
                                "studentUserInfo": {"realname": "Chen Muran"},
                            },
                            "missStuTchPlanNum": 0,
                            "missStuTchPlanArr": [],
                        }
                    ],
                    "page_no": 1,
                    "page_size": 100,
                    "total": 1,
                },
                "error": {"message": "", "code": ""},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    store.upsert_local_class(
        {
            "id": 3901,
            "className": "AUDIT-FLOW-LOCAL",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    store.upsert_local_class_student_relation(class_id=3901, student_user_id=400057, in_class_date="2026-05-18")
    store.upsert_local_teaching_plan(
        {
            "id": 99001,
            "curriculum_class_id": 3901,
            "subject_id": 1,
            "curriculum_id": 501,
            "curriculum_meterial_id": 7001,
            "class_date": "2026-06-20",
            "start_class_date": "2026-06-20 09:00:00",
            "end_class_date": "2026-06-20 10:30:00",
            "sort_num": 1,
            "custom_lesson_title": "Local Audit Lesson",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    class_response = client.get(
        "/api/stu/get/stu/class/list?t=1&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )
    timetable_response = client.get(
        "/api/stu/get/stu/timetable/new?t=1&page_no=1&page_size=20",
        headers={"Authorization": "Bearer student-token"},
    )

    assert class_response.status_code == 200
    class_rows = class_response.json()["content"]["classlist"]
    assert [row["id"] for row in class_rows][:2] == [3001, 3901]

    assert timetable_response.status_code == 200
    timetable_rows = timetable_response.json()["content"]["tchPlanList"]
    assert [row["curriculum_class_id"] for row in timetable_rows][:3] == [3001, 3001, 3901]


def test_divide_class_route_bootstraps_course_arranging_session_state(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_profile(
        tmp_path,
        profile_name="admin",
        username="admin",
        token="admin-token",
        user_info={"id": 9001, "realName": "Admin User"},
    )
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.upsert_local_class(
        {
            "id": 3901,
            "className": "Direct Bootstrap Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "direct-class-student",
            "realName": "Direct Class Student",
            "sex": "M",
            "parentAPhoneNum": "13800138131",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class_student_relation(class_id=3901, student_user_id=student["id"], in_class_date="2026-05-16")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    redirect_response = client.get(
        "/school-home-page/class-management1/divide-class1?id=3901&campus_id=851&lecturer_id=12385",
        follow_redirects=False,
    )

    assert redirect_response.status_code == 307
    assert "is_cost_lesson_hour=false" in redirect_response.headers["location"]
    assert "curriculum_class_type=1" in redirect_response.headers["location"]

    response = client.get(
        "/school-home-page/class-management1/divide-class1?id=3901&campus_id=851&lecturer_id=12385",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert "sessionStorage.setItem('courseArranging',JSON.stringify(data))" in response.text
    assert '"id":3901' in response.text
    assert '"name":"Direct Bootstrap Class"' in response.text

    unauthenticated_response = client.get(
        "/school-home-page/class-management1/divide-class1?id=3901&campus_id=851&lecturer_id=12385",
    )

    assert unauthenticated_response.status_code == 200
    assert 'class="login-shell"' in unauthenticated_response.text
    assert "sessionStorage.setItem('courseArranging',JSON.stringify(data))" not in unauthenticated_response.text

    admin_response = client.get(
        "/school-home-page/class-management1/divide-class1?id=3901&campus_id=851&lecturer_id=12385",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert admin_response.status_code == 200
    assert "sessionStorage.setItem('courseArranging',JSON.stringify(data))" in admin_response.text
    assert '"id":3901' in admin_response.text
    assert '"name":"Direct Bootstrap Class"' in admin_response.text


def test_class_candidate_student_endpoints_exclude_existing_members(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    first_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "candidate-class-1",
            "realName": "Candidate Class One",
            "sex": "M",
            "parentAPhoneNum": "13800138126",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    second_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "candidate-class-2",
            "realName": "Candidate Class Two",
            "sex": "F",
            "parentAPhoneNum": "13800138127",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=first_student["id"], in_class_date="2026-05-16")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    formal_response = client.get(
        "/api/getNoXmStuForClassAddStu?t=1&classId=3001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    xmedu_response = client.get(
        "/api/xmedu/getStuListForAddStuToClass?t=2&classId=3001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert formal_response.status_code == 200
    assert xmedu_response.status_code == 200
    assert [row["id"] for row in formal_response.json()["content"]["studentList"]] == [second_student["id"]]
    assert [row["id"] for row in xmedu_response.json()["content"]["studentList"]] == [second_student["id"]]


def test_class_candidate_student_endpoints_ignore_staff_rows_from_campus_user_capture(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    _store_teacher_campus_user_capture(
        tmp_path,
        students=[
            {
                "id": 3394,
                "name": "18164173640",
                "realname": "超级管理员",
                "phone_num": "18164173640",
                "is_platform_tch": False,
                "is_edu_tch": False,
                "is_super_administrator": True,
            },
            {
                "id": 11075,
                "name": "yangtao",
                "realname": "杨陶",
                "phone_num": "18827288771",
                "is_platform_tch": True,
                "is_edu_tch": True,
                "is_super_administrator": False,
            },
        ],
    )
    store = MirrorStore(tmp_path)
    local_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "candidate-class-clean",
            "realName": "Candidate Class Clean",
            "sex": "M",
            "parentAPhoneNum": "13800138132",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getNoXmStuForClassAddStu?t=1&classId=3001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["content"]["studentList"]] == [local_student["id"]]


def test_no_divide_student_list_returns_only_unassigned_student_candidates(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    current_class_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "current-class-student",
            "realName": "Current Class Student",
            "sex": "M",
            "parentAPhoneNum": "13800138133",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    other_class_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "other-class-student",
            "realName": "Other Class Student",
            "sex": "F",
            "parentAPhoneNum": "13800138134",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    unassigned_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "unassigned-student",
            "realName": "Unassigned Student",
            "sex": "F",
            "parentAPhoneNum": "13800138135",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class(
        {
            "id": 3002,
            "name": "Other Local Class",
            "campusId": 851,
            "curriculum_class_type": 1,
        }
    )
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=current_class_student["id"], in_class_date="2026-05-16")
    store.upsert_local_class_student_relation(class_id=3002, student_user_id=other_class_student["id"], in_class_date="2026-05-16")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/no/divide/student/list?t=1&classId=3001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    rows = response.json()["content"]["studentList"]
    assert [row["id"] for row in rows] == [unassigned_student["id"]]
    assert rows[0]["stuClassArr"] == []
    assert rows[0]["ClassGoodsInfo"]["student_user_id"] == unassigned_student["id"]


def test_no_divide_receipt_student_candidates_include_receipt_detail_payloads(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    unassigned_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "receipt-candidate",
            "realName": "Receipt Candidate",
            "sex": "F",
            "parentAPhoneNum": "13800138136",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    candidates = client.get(
        "/api/get/no/divide/student/list?t=1&classId=3001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert candidates.status_code == 200
    rows = candidates.json()["content"]["studentList"]
    assert [row["id"] for row in rows] == [unassigned_student["id"]]
    candidate = rows[0]
    class_goods_info = candidate["ClassGoodsInfo"]
    receipt_info = class_goods_info["receiptInfo"]
    assert receipt_info["id"]
    assert isinstance(receipt_info["num"], int)
    assert receipt_info["student_user_id"] == unassigned_student["id"]
    assert candidate["stuClassGoodsInfoArr"][0]["receiptInfo"]["id"] == receipt_info["id"]
    assert candidate["xmGoodsList"][0]["receiptInfo"]["id"] == receipt_info["id"]

    charge_goods = client.get(
        f"/api/get/receipt/charge/goods/list?t=2&receipt_id={receipt_info['id']}",
        headers={"Authorization": "Bearer teacher-token"},
    )
    receipt_accounts = client.get(
        f"/api/get/receipt/account/list?t=3&receipt_id={receipt_info['id']}",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert charge_goods.status_code == 200
    assert receipt_accounts.status_code == 200
    charge_goods_rows = charge_goods.json()["content"]["receiptChargeGoodsList"]
    receipt_account_rows = receipt_accounts.json()["content"]["receiptAccountList"]
    assert charge_goods_rows[0]["receipt_id"] == receipt_info["id"]
    assert charge_goods_rows[0]["receiptInfo"]["student_user_id"] == unassigned_student["id"]
    assert charge_goods_rows[0]["type"] == "2"
    assert charge_goods_rows[0]["original_unit_price"] == 0
    assert charge_goods_rows[0]["now_unit_price"] == 0
    assert charge_goods_rows[0]["discount"] == 100
    assert charge_goods_rows[0]["give_num"] == 0
    assert receipt_account_rows[0]["receipt_id"] == receipt_info["id"]


def test_teaching_plan_candidate_student_endpoints_exclude_existing_members(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    first_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "candidate-plan-1",
            "realName": "Candidate Plan One",
            "sex": "M",
            "parentAPhoneNum": "13800138128",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    second_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "candidate-plan-2",
            "realName": "Candidate Plan Two",
            "sex": "F",
            "parentAPhoneNum": "13800138129",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=first_student["id"], in_class_date="2026-05-16")
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=second_student["id"], in_class_date="2026-05-16")
    store.upsert_local_teaching_plan_student_relation(teaching_plan_id=81001, student_user_id=first_student["id"])
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    formal_response = client.get(
        "/api/get/formal/student/list/for/addto/tch/plan?t=1&teachingPlanId=81001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    xmedu_response = client.get(
        "/api/xmedu/getStuListForAddStuToTchPlan?t=2&teachingPlanId=81001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert formal_response.status_code == 200
    assert xmedu_response.status_code == 200
    assert [row["id"] for row in formal_response.json()["content"]["studentList"]] == [second_student["id"]]
    assert [row["id"] for row in xmedu_response.json()["content"]["studentList"]] == [second_student["id"]]


def test_class_change_and_lesson_candidate_endpoints_return_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "candidate-move-1",
            "realName": "Candidate Move One",
            "sex": "M",
            "parentAPhoneNum": "13800138130",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    created_class = store.upsert_local_class(
        {
            "id": 3905,
            "className": "Lesson Candidate Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    store.upsert_local_class_student_relation(class_id=3001, student_user_id=student["id"], in_class_date="2026-05-16")
    store.upsert_local_teaching_plan(
        {
            "id": 99001,
            "curriculum_class_id": created_class["id"],
            "subject_id": 1,
            "curriculum_id": 501,
            "curriculum_meterial_id": 7001,
            "class_date": "2026-05-24",
            "start_class_date": "2026-05-24 09:00:00",
            "end_class_date": "2026-05-24 10:30:00",
            "sort_num": 1,
            "custom_lesson_title": "Existing Lesson",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    class_change_response = client.get(
        f"/api/get/class/list/for/stu/change/class?t=1&stuId={student['id']}&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    lesson_response = client.get(
        f"/api/getLessonListForClassAddLesson?t=2&classId={created_class['id']}&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert class_change_response.status_code == 200
    assert lesson_response.status_code == 200
    class_ids = {row["id"] for row in class_change_response.json()["content"]["classList"]}
    assert {3001, 3002, created_class["id"]}.issubset(class_ids)
    lesson_ids = [row["id"] for row in lesson_response.json()["content"]["lessonList"]]
    assert 7001 not in lesson_ids
    assert 7002 in lesson_ids


def test_get_lesson_list_for_class_add_lesson_supports_frontend_curriculum_only_query(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getLessonListForClassAddLesson?t=1&curriculum_id=%5B501%5D&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    rows = payload["content"]["lessonList"]
    assert rows
    assert {row["curriculum_id"] for row in rows} == {501}
    assert {row["subject_id"] for row in rows} == {1}
    assert rows[0]["curriculum_title"] == "编程启蒙J1/J2"
    assert rows[0]["subject_title"] == "Jrcode"


def test_get_lesson_list_for_class_add_lesson_supports_frontend_lesson_title_query(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getLessonListForClassAddLesson?t=1&lesson_title=%E5%88%9D%E6%AC%A1&curriculum_id=%5B501%5D&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    rows = payload["content"]["lessonList"]
    assert [row["id"] for row in rows] == [7001]
    assert rows[0]["title"] == "初次挑战"


def test_get_lesson_list_for_class_add_lesson_uses_referer_class_context_for_frontend_curriculum_pool(
    tmp_path: Path,
) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.upsert_local_class(
        {
            "id": 3905,
            "className": "Referer Lesson Scope Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/getLessonListForClassAddLesson?t=1&lesson_title=&curriculum_id=%5B501,901%5D&page_no=1&page_size=20",
        headers={
            "Authorization": "Bearer teacher-token",
            "Referer": "http://testserver/school-home-page/class-management1/divide-class1?id=3905&campus_id=851&lecturer_id=12385",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    rows = payload["content"]["lessonList"]
    assert rows
    assert {row["curriculum_id"] for row in rows} == {501}
    assert {row["subject_id"] for row in rows} == {1}
    assert [row["id"] for row in rows] == [7001, 7002]


def test_update_all_notice_read_uses_local_success_payload(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/api/update/updateAllNoticeRead?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["content"]["is_update"] is True


def test_delete_class_api_alias_marks_local_class_deleted(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    created = client.post(
        "/api/create/class?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "className": "Delete Alias Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        },
    )
    assert created.status_code == 200
    created_class_id = created.json()["content"]["id"]

    deleted = client.post(
        "/api/delete/class?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classIds": [created_class_id]},
    )

    assert deleted.status_code == 200
    deleted_payload = deleted.json()["content"]
    assert deleted_payload["is_delete"] is True
    assert deleted_payload["deletedClassIds"] == [created_class_id]

    classlist_response = client.get(
        "/api/tch/class/get/classlist?t=3&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert classlist_response.status_code == 200
    remaining_ids = {row["id"] for row in classlist_response.json()["content"]["classlist"]}
    assert created_class_id not in remaining_ids


def test_curr_cls_delete_accepts_raw_id_array_body(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    created = client.post(
        "/api/create/class?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "className": "Delete Raw Array Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        },
    )
    assert created.status_code == 200
    created_class_id = created.json()["content"]["id"]

    deleted = client.post(
        "/java-api/school/currCls/delete?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json=[created_class_id],
    )

    assert deleted.status_code == 200
    deleted_payload = deleted.json()["content"]
    assert deleted_payload["is_delete"] is True
    assert deleted_payload["deletedClassIds"] == [created_class_id]
    assert deleted_payload["successCount"] == 1

    classlist_response = client.get(
        "/api/tch/class/get/classlist?t=3&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert classlist_response.status_code == 200
    remaining_ids = {row["id"] for row in classlist_response.json()["content"]["classlist"]}
    assert created_class_id not in remaining_ids


def test_end_class_state_update_accepts_form_body_and_moves_class_to_graduated_list(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    created = client.post(
        "/api/create/class?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "className": "Graduate Flow Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        },
    )
    assert created.status_code == 200
    created_class_id = created.json()["content"]["id"]

    graduated = client.post(
        "/api/update/classes/end/class/state?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        data={"id": str(created_class_id), "end_class_state": "1"},
    )

    assert graduated.status_code == 200
    graduated_payload = graduated.json()["content"]
    assert graduated_payload["is_update"] is True
    assert graduated_payload["updatedClassIds"] == [created_class_id]
    assert graduated_payload["successCount"] == 1
    assert graduated_payload["classInfo"]["id"] == created_class_id
    assert graduated_payload["classInfo"]["end_class_state"] == 1

    active_list = client.get(
        (
            "/api/get/classes/list"
            "?t=3&week_json=[]&campusIds=[851]&curriculum_class_type=&className="
            "&lecturer_id=&subject_id=&curriculum_id=&teaching_type=&end_class_state=0&page_no=1&page_size=20"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert active_list.status_code == 200
    active_ids = {row["id"] for row in active_list.json()["content"]["class_list"]}
    assert created_class_id not in active_ids

    graduated_list = client.get(
        (
            "/api/get/classes/list"
            "?t=4&week_json=[]&campusIds=[851]&curriculum_class_type=&className="
            "&lecturer_id=&subject_id=&curriculum_id=&teaching_type=&end_class_state=1&page_no=1&page_size=20"
        ),
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert graduated_list.status_code == 200
    graduated_ids = {row["id"] for row in graduated_list.json()["content"]["class_list"]}
    assert created_class_id in graduated_ids


def test_count_signed_teaching_plan_uses_local_class_snapshot(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/currCls/countSignedTchPlan?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classId": 3001},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["count"] == 1
    assert content["signedCount"] == 1
    assert content["sign_tchplan_num"] == 1


def test_local_exam_student_statistics_fallback_returns_paginated_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "exam-local-1",
            "realName": "Exam Local Student",
            "sex": "男",
            "parentAPhoneNum": "13800138001",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/exam/sch/testExamStu/getList?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"classId": None, "keyword": "exam-local", "flag": True, "pageRequest": {"pageNum": 1, "pageSize": 20}},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["totalSize"] == 1
    row = content["content"][0]
    assert row["studentName"] == "Exam Local Student"
    assert row["studentAccount"] == "exam-local-1"
    assert row["examCount"] == 0
    assert row["practiceCount"] == 0
    assert row["lessonExamCount"] == 0
    assert row["wrongQuestionCount"] == 0


def test_local_school_board_main_data_fallback_returns_metric_snapshot(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "board-local-1",
            "realName": "Board Local Student",
            "sex": "男",
            "parentAPhoneNum": "13800138002",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/get/school/board/main/data?t=1&campusIds=%5B851%5D",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    content = response.json()["content"]
    assert content["formalNum"] == 1
    assert content["lessonRecordNum"] == 3
    assert content["consumeHour"] >= 3
    assert {"todayFormalNum", "todayLessonRecordNum", "todayConsumeHour"}.issubset(content)


def test_dashboard_endpoints_accept_user_campus_row_id_alias(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "name": "dashboard-alias-local-1",
            "realName": "Dashboard Alias Student",
            "normalState": "1",
            "schoolName": "Mirror School",
            "studyDate": "2026-05-20",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    board_response = client.get(
        "/api/get/school/board/main/data?t=1&campusIds=%5B41885%5D",
        headers={"Authorization": "Bearer teacher-token"},
    )
    metric_response = client.post(
        "/java-api/school/stu/board/recSoa?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusId": 41885,
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
        },
    )
    comment_response = client.post(
        "/java-api/school/tch/board/classCmtQuery?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusId": 41885,
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
            "pageRequest": {"pageNum": 1, "pageSize": 10},
        },
    )

    assert board_response.status_code == 200
    board_content = board_response.json()["content"]
    assert board_content["formalNum"] >= 1
    assert board_content["lessonRecordNum"] == 3
    assert board_content["consumeHour"] >= 3

    assert metric_response.status_code == 200
    metric_content = metric_response.json()["content"]
    assert metric_content["formalNum"] >= 1
    assert metric_content["tryNum"] == 0

    assert comment_response.status_code == 200
    comment_content = comment_response.json()["content"]
    assert comment_content["totalSize"] == 3


def test_admin_dashboard_metric_endpoints_use_local_fallbacks(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "name": "dashboard-local-1",
            "realName": "Dashboard Local Student",
            "normalState": "1",
            "schoolName": "Mirror School",
            "studyDate": "2026-05-20",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    payload = {
        "eduId": 834,
        "eduCampusId": 851,
        "startDate": "2026-05-01 00:00:00",
        "endDate": "2026-05-31 23:59:59",
    }

    clue_response = client.post(
        "/java-api/school/intend/board/soa?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json=payload,
    )
    student_response = client.post(
        "/java-api/school/stu/board/recSoa?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json=payload,
    )
    record_response = client.post(
        "/java-api/school/tch/board/recordSoa?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json=payload,
    )
    income_response = client.post(
        "/java-api/school/stu/board/incomeSoa?t=4",
        headers={"Authorization": "Bearer teacher-token"},
        json=payload,
    )

    assert clue_response.status_code == 200
    assert student_response.status_code == 200
    assert record_response.status_code == 200
    assert income_response.status_code == 200

    clue_content = clue_response.json()["content"]
    student_content = student_response.json()["content"]
    record_content = record_response.json()["content"]
    income_content = income_response.json()["content"]

    assert clue_content["intendNum"] == 0
    assert clue_content["todayIntendNum"] == 0
    assert clue_content["todayComeNum"] == 0
    assert student_content["formalNum"] >= 1
    assert student_content["tryNum"] == 0
    assert record_content["lessonRecordNum"] == 3
    assert income_content["consumeHour"] >= 3
    assert {"todayFormalNum", "todayLessonRecordNum", "todayConsumeHour"}.issubset(
        {
            "todayFormalNum": student_content["todayFormalNum"],
            "todayLessonRecordNum": record_content["todayLessonRecordNum"],
            "todayConsumeHour": income_content["todayConsumeHour"],
        }
    )


def test_admin_dashboard_chart_endpoints_use_local_fallbacks(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "name": "dashboard-chart-local-1",
            "realName": "Dashboard Chart Student",
            "normalState": "1",
            "schoolName": "Mirror School",
            "studyDate": "2026-05-20",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    clue_chart_response = client.post(
        "/java-api/school/intend/board/echarts/stat?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusId": 851,
            "startDate": "2026-05-10 00:00:00",
            "endDate": "2026-05-12 23:59:59",
        },
    )
    student_pie_response = client.post(
        "/java-api/school/stu/board/echarts/recStat?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"eduId": 834, "eduCampusId": 851},
    )
    teacher_record_response = client.post(
        "/java-api/school/tch/board/echarts/recordStat?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusId": 851,
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
        },
    )
    consume_chart_response = client.post(
        "/java-api/school/stu/board/echarts/consumeStat?t=4",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusIdList": [851],
            "startDate": "2026-05-10 00:00:00",
            "endDate": "2026-05-12 23:59:59",
        },
    )
    teacher_attendance_response = client.post(
        "/java-api/school/tch/board/echarts/attnStat?t=5",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusId": 851,
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
        },
    )
    campus_attendance_response = client.post(
        "/java-api/school/edu/campus/echarts/attnStat?t=6",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusIdList": [851],
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
        },
    )
    campus_consume_response = client.post(
        "/java-api/school/edu/campus/consumeDayStat?t=7",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusIdList": [851],
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
        },
    )

    assert clue_chart_response.status_code == 200
    clue_chart_content = clue_chart_response.json()["content"]
    assert clue_chart_content["dateList"] == ["2026-05-10", "2026-05-11", "2026-05-12"]
    assert clue_chart_content["intendNumList"] == [0, 0, 0]
    assert clue_chart_content["comeNumList"] == [0, 0, 0]

    assert student_pie_response.status_code == 200
    student_pie_content = student_pie_response.json()["content"]
    assert student_pie_content["formalNum"] >= 1
    assert student_pie_content["tryNum"] == 0

    assert teacher_record_response.status_code == 200
    teacher_record_content = teacher_record_response.json()["content"]
    assert teacher_record_content["hourNameList"] == ["Teacher A", "Teacher B"]
    assert teacher_record_content["hourList"] == [2.0, 1.0]
    assert teacher_record_content["numNameList"] == ["Teacher A", "Teacher B"]
    assert teacher_record_content["numList"] == [2, 1]

    assert consume_chart_response.status_code == 200
    consume_chart_content = consume_chart_response.json()["content"]
    assert consume_chart_content["dateList"] == ["2026-05-10", "2026-05-11", "2026-05-12"]
    assert len(consume_chart_content["consumeVoList"]) == 1
    assert consume_chart_content["consumeVoList"][0]["id"] == 851
    assert consume_chart_content["consumeVoList"][0]["lessonNumList"] == [1, 1, 0]
    assert consume_chart_content["consumeVoList"][0]["lessonHourList"] == [1.0, 1.0, 0.0]

    assert teacher_attendance_response.status_code == 200
    teacher_attendance_content = teacher_attendance_response.json()["content"]
    assert teacher_attendance_content["tchNameList"] == ["Teacher A", "Teacher B"]
    assert teacher_attendance_content["rateList"] == [50.0, 100.0]

    assert campus_attendance_response.status_code == 200
    campus_attendance_content = campus_attendance_response.json()["content"]
    assert campus_attendance_content["eduCampusIdList"] == [851]
    assert campus_attendance_content["percentList"] == [66.67]

    assert campus_consume_response.status_code == 200
    campus_consume_content = campus_consume_response.json()["content"]
    assert campus_consume_content["eduCampusIdList"] == [851]
    assert campus_consume_content["numList"] == [3.0]


def test_admin_dashboard_teacher_and_comment_endpoints_use_local_fallbacks(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385})
    _store_teacher_course_chain_captures(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    teacher_response = client.post(
        "/java-api/school/tch/selectTchListByCampus?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"eduCampusIdList": [851]},
    )
    comment_response = client.post(
        "/java-api/school/tch/board/classCmtQuery?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={
            "eduId": 834,
            "eduCampusId": 851,
            "startDate": "2026-05-01 00:00:00",
            "endDate": "2026-05-31 23:59:59",
            "pageRequest": {"pageNum": 1, "pageSize": 10},
        },
    )

    assert teacher_response.status_code == 200
    teacher_rows = teacher_response.json()["content"]
    assert [row["realName"] for row in teacher_rows] == ["Teacher A", "Teacher B"]

    assert comment_response.status_code == 200
    comment_content = comment_response.json()["content"]
    assert comment_content["totalSize"] == 3
    first_row = comment_content["content"][0]
    assert first_row["className"]
    assert first_row["tchName"] in {"Teacher A", "Teacher B"}
    assert first_row["title"]
    assert first_row["tchPlanId"] > 0
    assert "classTime" in first_row
    assert {"realNum", "dueNum", "lessonWork", "homeWork", "commentRealNum", "commentDueNum"}.issubset(first_row)


def test_same_origin_click_download_icon_uses_synthetic_png(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/img/clickDownload.afff976e.png")

    assert response.status_code == 200
    assert response.content == server_module.TRANSPARENT_PNG_BYTES
    assert response.headers["content-type"].startswith("image/png")


def test_teaching_plan_overlay_endpoints_persist_into_bootstrap_and_detail(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    bootstrap_before = client.get(
        "/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert bootstrap_before.status_code == 200
    assert '"editor_showhint_auth":true' in bootstrap_before.text

    zone_updated = client.post(
        "/api/update/teaching/plan/zone/auth?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"teachingPlanId": 999999, "zone_auth": 0},
    )
    showhint_updated = client.post(
        "/api/updateTeachingPlanEditorShowhintAuth?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"teachingPlanId": 999999, "editor_showhint_auth": 0},
    )
    oj_updated = client.post(
        "/api/update/teaching/plan/oj/analysis/auth?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"teachingPlanId": 999999, "oj_analysis_auth": 1},
    )
    testcase_updated = client.post(
        "/api/updateTeachingPlanTestCaseAuth?t=4",
        headers={"Authorization": "Bearer teacher-token"},
        json={"teachingPlanId": 999999, "test_case_auth": 0},
    )

    assert zone_updated.status_code == 200
    assert showhint_updated.status_code == 200
    assert oj_updated.status_code == 200
    assert testcase_updated.status_code == 200

    overlay = store.get_teaching_plan_overlay(999999)
    assert overlay is not None
    assert overlay["zone_auth"] == 0
    assert overlay["editor_showhint_auth"] == 0
    assert overlay["oj_analysis_auth"] == 1
    assert overlay["test_case_auth"] == 0

    bootstrap_after = client.get(
        "/code-classroom/teach-lessons/lessons/ppt?curriculumMaterial_id=39525&teaching_plan_id=999999",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert bootstrap_after.status_code == 200
    assert '"zone_auth":false' in bootstrap_after.text
    assert '"editor_showhint_auth":false' in bootstrap_after.text
    assert '"oj_analysis_auth":true' in bootstrap_after.text
    assert '"oj_analysis_TEST":false' in bootstrap_after.text

    detail = client.post(
        "/java-api/school/currMat/detail?t=5",
        headers={"Authorization": "Bearer teacher-token"},
        json={"currMatId": 39525, "tchPlanId": 999999},
    )
    assert detail.status_code == 200
    tch_plan_info = detail.json()["content"]["tchPlanInfo"]
    assert tch_plan_info["teachingPlanId"] == 999999
    assert tch_plan_info["exampleWorkUrl"]


def test_select_study_direct_local_fallback_uses_account_name_when_realname_is_placeholder(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "audit_local_1",
            "realName": "??????",
            "sex": "M",
            "parentAPhoneNum": "13800138111",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/stu/selectStudy?t=1",
        headers={"Authorization": "Bearer teacher-token"},
        json={"pageRequest": {"pageNum": 1, "pageSize": 20}},
    )

    assert response.status_code == 200
    row = response.json()["content"]["content"][0]
    assert row["stuName"] == "audit_local_1"
    assert row["stuAccount"] == "audit_local_1"


def test_local_work_copy_and_sync_endpoints_return_local_content(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "audit_local_1",
            "realName": "??????",
            "sex": "M",
            "parentAPhoneNum": "13800138112",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "copy_target_2",
            "realName": "Copy Target 2",
            "sex": "F",
            "parentAPhoneNum": "13800138113",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    work_list = client.get(
        "/api/tch/get/stu/lesson/tch/work/list?t=1&subject_code=1&teaching_plan_id=999999&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert work_list.status_code == 200
    assert any(row["name"] == "audit_local_1" for row in work_list.json()["content"]["workList"])

    copy_list = client.get(
        "/api/getWorkListForCopyToStuTchPlan?t=2&teaching_plan_id=999999&work_id=999999001&work_type=1&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert copy_list.status_code == 200
    copy_content = copy_list.json()["content"]
    assert copy_content["tchLeesonWorkInfo"]["title"]
    assert copy_content["tchLeesonWorkInfo"]["name"] == "Teacher Li"
    assert any(row["name"] == "Copy Target 2" for row in copy_content["workList"])

    copied = client.post(
        "/api/tmpWorkCopyToStuTchPlan?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"subject_code": 1, "work_id": 999999001, "tmp_work_id": 395250001, "tmp_work_type": 1},
    )
    assert copied.status_code == 200
    assert copied.json()["content"]["is_update"] is True


def test_teacher_classroom_student_plan_list_endpoint_returns_local_rows(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    first_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "audit_local_1",
            "realName": "Audit Local One",
            "sex": "M",
            "parentAPhoneNum": "13800138112",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    second_student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "audit_local_2",
            "realName": "Audit Local Two",
            "sex": "F",
            "parentAPhoneNum": "13800138113",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class_student_relation(class_id=3901, student_user_id=first_student["id"], in_class_date="2026-05-18")
    store.upsert_local_class_student_relation(class_id=3901, student_user_id=second_student["id"], in_class_date="2026-05-18")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/get/stu/tch/plan/list/by/tch/id?t=1&teachingPlanId=999999&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    content = payload["content"]
    assert content["total"] == 2
    assert len(content["stuTchPlanList"]) == 2
    row = content["stuTchPlanList"][0]
    assert row["teachingPlanId"] == 999999
    assert row["student_user_id"] in {first_student["id"], second_student["id"]}
    assert row["subject_id"] == 1
    assert row["classWorkState"] is True
    assert row["homeWorkState"] is True
    assert row["classWorkInfo"]["work_url"] != ""
    assert row["classWorkInfo"]["work_type"] == 1
    assert row["classWorkInfo"]["title"] != ""
    assert row["homeWorkInfo"]["work_url"] != ""
    assert row["homeWorkInfo"]["work_type"] == 2
    assert row["homeWorkInfo"]["title"] != ""
    assert row["stuInfo"]["id"] == row["student_user_id"]
    assert row["tchPlanInfo"]["id"] == 999999


def test_teaching_plan_student_rows_always_expose_array_xm_goods_list(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    student = store.create_local_student(
        {
            "eduCampusId": 851,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "xm-goods-local",
            "realName": "XM Goods Local",
            "sex": "M",
            "parentAPhoneNum": "13800138112",
            "schoolName": "Mirror School",
            "grade": "",
            "leader": "",
            "remark": "",
            "studyDate": "2026-05-16",
        }
    )
    store.upsert_local_class(
        {
            "id": 3901,
            "className": "XM Goods Class",
            "campusId": 851,
            "lecturer_id": 12385,
            "lecturer_name": "Teacher Li",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "Sat",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
        }
    )
    store.upsert_local_class_student_relation(class_id=3901, student_user_id=student["id"], in_class_date="2026-05-18")
    store.upsert_local_teaching_plan(
        {
            "id": 999999,
            "curriculum_class_id": 3901,
            "subject_id": 1,
            "curriculum_id": 501,
            "curriculum_meterial_id": 7001,
            "class_date": "2026-05-24",
            "start_class_date": "2026-05-24 09:00:00",
            "end_class_date": "2026-05-24 10:30:00",
            "sort_num": 1,
            "custom_lesson_title": "Existing Lesson",
        }
    )
    store.upsert_local_teaching_plan_student_relation(
        teaching_plan_id=999999,
        student_user_id=student["id"],
        xm_goods_id=None,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get(
        "/api/tch/get/stu/tch/plan/list/by/tch/id?t=1&teachingPlanId=999999&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )

    assert response.status_code == 200
    rows = response.json()["content"]["stuTchPlanList"]
    assert rows and isinstance(rows[0]["xmGoodsList"], list)


def test_get_tch_plan_list_for_add_tmp_and_bulk_template_sync_use_local_overlay(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, user_info={"id": 12385, "realName": "Teacher Li"})
    _store_teacher_course_chain_captures(tmp_path)
    store = MirrorStore(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    listing = client.get(
        "/api/getTchPlanListForAddTmp?t=1&tchPlanId=81001&page_no=1&page_size=20",
        headers={"Authorization": "Bearer teacher-token"},
    )
    assert listing.status_code == 200
    assert all(row["id"] != 81001 for row in listing.json()["content"]["teachingPlan"])

    synced = client.post(
        "/api/bulkUpdateTchPlanTemplate?t=2",
        headers={"Authorization": "Bearer teacher-token"},
        json={"tchPlanId": 999999, "tchPlanIdArr": "[91001,91002]"},
    )
    assert synced.status_code == 200
    assert synced.json()["content"]["successCount"] == 2

    overlay = store.get_teaching_plan_overlay(91001)
    assert overlay is not None
    assert overlay["source_tch_plan_id"] == 999999
    assert overlay["example_work_url"]

    detail = client.post(
        "/java-api/school/currMat/detail?t=3",
        headers={"Authorization": "Bearer teacher-token"},
        json={"currMatId": 39525, "tchPlanId": 91001},
    )
    assert detail.status_code == 200
    assert detail.json()["content"]["tchPlanInfo"]["sourceTchPlanId"] == 999999

    reset = client.post(
        "/api/bulkResetTchPlanTemplate?t=4",
        headers={"Authorization": "Bearer teacher-token"},
        json={"tchPlanIdArr": "[91001]"},
    )
    assert reset.status_code == 200
    cleared_overlay = store.get_teaching_plan_overlay(91001)
    assert cleared_overlay is not None
    assert cleared_overlay["source_tch_plan_id"] is None

def test_logout_endpoint_clears_cookie_and_serves_redirect_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/logout")

    assert response.status_code == 200
    assert "cache-control" in response.headers
    assert response.headers["cache-control"].startswith("no-store")
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "mirror_profile=" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header
    body = response.text
    assert "sessionStorage.removeItem" in body
    assert "window.location.replace" in body
    assert "/login" in body


def test_logout_endpoint_accepts_post_method(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post("/logout")

    assert response.status_code == 200
    assert "Max-Age=0" in response.headers.get("set-cookie", "")


def test_spa_pages_do_not_inject_location_reload_override(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    store = MirrorStore(tmp_path)
    captured_html = '<html><body><div id="app"></div></body></html>'
    store.store_route_capture(
        profile_name="teacher",
        route="/school-home-page",
        final_url="https://steam.fun/school-home-page",
        status=200,
        html=captured_html,
        captured_xhr_count=0,
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/school-home-page")
    assert response.status_code == 200
    assert 'Object.defineProperty(window.location,"reload"' not in response.text


def test_login_html_has_no_demo_account_hints(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    """The login page must not advertise demo accounts."""
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    response = client.get("/login")
    assert response.status_code == 200
    body = response.text
    for forbidden in ("演示账号", "通用密码", "lbschenmuran", "zhaosenlin", "18164173640"):
        assert forbidden not in body, "demo hint present: %r" % forbidden
    assert "demo-info" not in body


def test_login_route_serves_professional_local_login_page(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/login")

    assert response.status_code == 200
    assert 'class="login-shell"' in response.text
    assert 'data-target="student"' in response.text
    assert 'data-target="teacher"' in response.text
    assert "sessionStorage.removeItem('mirror_profile')" in response.text
    assert "var mirror=data.mirror||{}" in response.text
    assert "isAdmin:role==='admin'" in response.text
    assert "isTeacher:role==='teacher'" in response.text
    assert "isStudent:role==='student'" in response.text
    assert "登录后进入" not in response.text
    assert response.headers["cache-control"].startswith("no-store")
    for forbidden in ("演示账号", "通用密码", "lbschenmuran", "zhaosenlin", "18164173640"):
        assert forbidden not in response.text


def test_frontend_runtime_routes_spa_logout_to_logout_endpoint() -> None:
    source = (
        'this.$store.dispatch("LogOut").then(()=>{'
        'sessionStorage.setItem("schoolInfo",null),'
        'localStorage.removeItem("editor_opentype"),'
        'this.$message.success("退出成功"),'
        'this.$router.push({path:"/"}),location.reload()})'
    )

    patched = server_module._maybe_rewrite_body(
        source.encode("utf-8"),
        "application/javascript",
    ).decode("utf-8")

    assert 'window.location.assign("/logout")' in patched
    assert "location.reload()" not in patched


def test_frontend_runtime_routes_admin_logout_to_logout_endpoint() -> None:
    source = (
        'layout(){this.$store.dispatch("AdminLogOut").then(()=>{'
        'this.$message.success("\u9000\u51fa\u6210\u529f"),'
        'this.$router.push({path:"/background/login"}),'
        'sessionStorage.setItem("schoolInfo",null)})}'
    )

    patched = server_module._maybe_rewrite_body(
        source.encode("utf-8"),
        "application/javascript",
    ).decode("utf-8")

    assert 'window.location.assign("/logout")' in patched
    assert 'this.$router.push({path:"/background/login"})' not in patched


def test_teacher_login_does_not_accept_default_password_as_bypass(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path, username="teacher-with-another-password")
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/tch/login",
        json={"userName": "teacher-with-another-password", "password": "123456"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.cookies.get("mirror_profile") is None


def test_admin_login_returns_authoritative_role_and_redirect(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="admin-user",
        password_hash=server_module._hash_login_password("admin-password"),
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"token": "admin-token"},
        fresh_auth={"identity": 1, "userInfo": {}, "schoolInfo": {}, "roleList": []},
        vuex_state={"user": {"token": "admin-token", "identity": 1}},
    )
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.post(
        "/java-api/school/tch/login",
        json={"userName": "admin-user", "password": "admin-password"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["mirror"] == {
        "profile": "admin",
        "role": "admin",
        "redirect": "/background/course-management/school-curriculum",
    }
    login_auth_tree = json.loads(response.json()["content"]["authTree"])
    login_permissions = json.dumps(login_auth_tree, ensure_ascii=False)
    assert "school-user-list" in login_permissions
    assert "schoolSys" in login_permissions
    assert "orderpay" not in login_permissions
    assert "HttpOnly" in response.headers["set-cookie"]


def test_protected_frontend_routes_require_login_and_enforce_role(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_profile(tmp_path)
    store = MirrorStore(tmp_path)
    store.store_profile(
        profile_name="admin",
        username="admin",
        password_hash="hash",
        login_path="/java-api/school/tch/login",
        token="admin-token",
        login_content={"token": "admin-token"},
        fresh_auth={"identity": 1, "userInfo": {}, "schoolInfo": {}, "roleList": []},
        vuex_state={"user": {"token": "admin-token", "identity": 1}},
    )

    anonymous = TestClient(create_app(tmp_path, allow_live_proxy=False))
    anonymous_response = anonymous.get("/school-home-page", follow_redirects=False)
    assert anonymous_response.status_code in {302, 303, 307}
    assert anonymous_response.headers["location"].startswith("/login?next=")

    student = TestClient(create_app(tmp_path, allow_live_proxy=False))
    student.cookies.set("mirror_profile", "student")
    student_response = student.get("/school-home-page", follow_redirects=False)
    assert student_response.status_code in {302, 303, 307}
    assert student_response.headers["location"] == "/code-classroom/myClass"

    teacher = TestClient(create_app(tmp_path, allow_live_proxy=False))
    teacher.cookies.set("mirror_profile", "teacher")
    teacher_response = teacher.get(
        "/background/course-management/school-curriculum",
        follow_redirects=False,
    )
    assert teacher_response.status_code in {302, 303, 307}
    assert teacher_response.headers["location"] == "/code-classroom/classroom-index"

    admin = TestClient(create_app(tmp_path, allow_live_proxy=False))
    admin.cookies.set("mirror_profile", "admin")
    admin_response = admin.get("/code-classroom", follow_redirects=False)
    assert admin_response.status_code in {302, 303, 307}
    assert admin_response.headers["location"] == "/background/course-management/school-curriculum"


def test_role_specific_api_prefixes_reject_missing_and_mismatched_sessions(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    _store_student_profile(tmp_path)
    app = create_app(tmp_path, allow_live_proxy=False)

    anonymous = TestClient(app)
    assert anonymous.get("/java-api/school/tch/freshData").status_code == 401

    student = TestClient(app)
    student.cookies.set("mirror_profile", "student")
    assert student.get("/java-api/school/tch/freshData").status_code == 403

    teacher = TestClient(app)
    teacher.cookies.set("mirror_profile", "teacher")
    assert teacher.get("/java-api/student/stu/freshData").status_code == 403
