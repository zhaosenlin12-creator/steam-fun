from steamfun_mirror.auth import (
    build_vuex_state,
    localize_external_values,
    md5_base64,
    student_login_payload,
    teacher_login_payload,
)


def test_md5_base64_matches_frontend_password_encoding() -> None:
    assert md5_base64("123456") == "4QrcOUm6Wau+VuBX8g+IPg=="


def test_teacher_login_payload_matches_frontend_shape() -> None:
    assert teacher_login_payload("teacher", "abc123", "captcha-token") == {
        "userName": "teacher",
        "password": md5_base64("abc123"),
        "captchaVerifyParam": "captcha-token",
    }


def test_student_login_payload_matches_frontend_shape() -> None:
    assert student_login_payload("student", "123456") == {
        "userName": "student",
        "password": md5_base64("123456"),
        "captchaVerifyParam": "",
    }


def test_build_vuex_state_for_teacher_uses_teacher_profile_fields() -> None:
    state = build_vuex_state(
        profile_name="teacher",
        token="teacher-token",
        fresh_auth_data={
            "identity": 1,
            "userInfo": {"realName": "Teacher Li", "principal": True},
            "schoolInfo": {"name": "Steam School"},
            "roleList": [{"name": "教务"}],
        },
        permission_tree=[{"name": "课程管理"}],
    )

    assert state["user"]["token"] == "teacher-token"
    assert state["user"]["identity"] == 1
    assert state["user"]["username"] == "Teacher Li"
    assert state["user"]["is_principal"] is True
    assert state["user"]["permisionList"] == [{"name": "课程管理"}]


def test_build_vuex_state_for_student_uses_student_profile_fields() -> None:
    state = build_vuex_state(
        profile_name="student",
        token="student-token",
        fresh_auth_data={
            "identity": 2,
            "userInfo": {"stuUserInfo": {"realName": "Student Chen"}},
            "schoolInfo": {"name": "Steam School"},
        },
    )

    assert state["user"]["token"] == "student-token"
    assert state["user"]["identity"] == 2
    assert state["user"]["username"] == "Student Chen"
    assert state["user"]["is_principal"] is False
    assert state["user"]["permisionList"] == []


def test_localize_external_values_rewrites_nested_external_urls() -> None:
    payload = {
        "avatar": "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg",
        "items": [
            {"cover": "https://steamfun.oss-cn-zhangjiakou.aliyuncs.com/a.png"},
            "https://steam.fun/js/app.js",
        ],
    }

    localized = localize_external_values(payload)

    assert localized["avatar"] == "/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
    assert localized["items"][0]["cover"] == "/_external/steamfun.oss-cn-zhangjiakou.aliyuncs.com/a.png"
    assert localized["items"][1] == "/js/app.js"
