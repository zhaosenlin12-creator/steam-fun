from steamfun_mirror.runtime_audit import get_login_flow
from steamfun_mirror.runtime_audit import has_login_token
from steamfun_mirror.runtime_audit import should_force_post_login_navigation


def test_get_login_flow_returns_teacher_role_tab_and_fallback() -> None:
    flow = get_login_flow("teacher")

    assert flow.path == "/login"
    assert flow.role_tab_selector == '.tab[data-target="teacher"]'
    assert flow.fallback_path == "/code-classroom/classroom-index"


def test_get_login_flow_returns_student_role_tab_and_fallback() -> None:
    flow = get_login_flow("student")

    assert flow.path == "/login"
    assert flow.role_tab_selector == '.tab[data-target="student"]'
    assert flow.fallback_path == "/code-classroom/myClass"


def test_get_login_flow_returns_admin_background_entry() -> None:
    flow = get_login_flow("admin")

    assert flow.path == "/background/login"
    assert flow.role_tab_selector == '.tab[data-target="teacher"]'
    assert flow.fallback_path == "/school-home-page/class-management1"


def test_has_login_token_reads_vuex_user_token() -> None:
    assert has_login_token({"vuex": '{"user":{"token":"abc123"}}'}) is True


def test_has_login_token_rejects_empty_or_invalid_storage() -> None:
    assert has_login_token({"vuex": '{"user":{"token":""}}'}) is False
    assert has_login_token({"vuex": "not-json"}) is False
    assert has_login_token({}) is False


def test_should_force_post_login_navigation_when_token_stays_on_login() -> None:
    assert should_force_post_login_navigation(
        "http://127.0.0.1:8000/login",
        {"vuex": '{"user":{"token":"abc123"}}'},
    )


def test_should_force_post_login_navigation_false_without_token() -> None:
    assert (
        should_force_post_login_navigation(
            "http://127.0.0.1:8000/login",
            {"vuex": '{"user":{"token":""}}'},
        )
        is False
    )


def test_should_force_post_login_navigation_false_after_redirect() -> None:
    assert (
        should_force_post_login_navigation(
            "http://127.0.0.1:8000/code-classroom/myClass",
            {"vuex": '{"user":{"token":"abc123"}}'},
        )
        is False
    )
