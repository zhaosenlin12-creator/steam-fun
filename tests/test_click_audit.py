from scripts import click_audit


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    def click(self) -> None:
        self.page.actions.append(("click", self.selector, ""))

    def fill(self, value: str) -> None:
        self.page.actions.append(("fill", self.selector, value))


class FakePage:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str, str]] = []
        self.waits: list[tuple[str, int]] = []
        self.url = "http://127.0.0.1:8000/code-classroom/classroom-index"

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def wait_for_url(self, predicate, *, timeout: int) -> None:
        assert predicate(self.url)
        self.waits.append(("url", timeout))

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.waits.append((state, timeout))

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(("timeout", timeout))

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.context = FakeContext()
        self.context_options: dict[str, object] | None = None

    def new_context(self, **kwargs) -> FakeContext:
        self.context_options = kwargs
        return self.context


def test_classroom_tool_audit_uses_teacher_session_and_local_fixture_ids() -> None:
    scenarios = click_audit.build_scenarios("http://127.0.0.1:8000")

    assert {scenario["role"] for scenario in scenarios} == {"teacher"}
    assert all("curriculumMaterial_id=7001" in scenario["url"] for scenario in scenarios)
    assert "tchPlanId=5182933" in scenarios[0]["url"]
    assert "teaching_plan_id=5182933" in scenarios[1]["url"]


def test_classroom_tool_audit_only_declares_visible_page_actions() -> None:
    scenarios = click_audit.build_scenarios("http://127.0.0.1:8000")
    prepare_labels = {action["label"] for action in scenarios[0]["actions"]}
    teach_labels = {action["label"] for action in scenarios[1]["actions"]}

    assert prepare_labels == {"备课资料", "课堂成果", "授课模板", "作业模板", "开始创作"}
    assert teach_labels == {
        "课程工具",
        "课堂成果",
        "授课模板",
        "作业模板",
        "模板同步",
        "学习资料",
        "知识点海报",
        "学员管理",
        "点名上课",
        "学生作品",
        "作品社区",
        "开始创作",
    }


def test_authenticate_teacher_opens_teacher_tab_and_waits_for_workspace(monkeypatch) -> None:
    page = FakePage()
    navigations: list[str] = []
    monkeypatch.setattr(
        click_audit,
        "navigate_for_audit",
        lambda _page, url, **_kwargs: navigations.append(url),
    )

    result = click_audit.authenticate_teacher(page, "http://127.0.0.1:8000/")

    assert result == "http://127.0.0.1:8000/code-classroom/classroom-index"
    assert navigations == ["http://127.0.0.1:8000/login"]
    assert page.actions == [
        ("click", '.tab[data-target="teacher"]', ""),
        ("fill", '#form-teacher input[name="userName"]', "zhaosenlin"),
        ("fill", '#form-teacher input[name="password"]', "123456"),
        ("click", '#form-teacher button[type="submit"]', ""),
    ]
    assert ("url", 20_000) in page.waits
    assert not any(wait[0] == "networkidle" for wait in page.waits)


def test_open_teacher_context_authenticates_once_and_closes_login_page(monkeypatch) -> None:
    browser = FakeBrowser()
    authenticated_pages: list[FakePage] = []
    monkeypatch.setattr(
        click_audit,
        "authenticate_teacher",
        lambda page, _base: authenticated_pages.append(page) or "http://127.0.0.1:8000/code-classroom/classroom-index",
    )

    context, authenticated_url = click_audit.open_teacher_context(browser, "http://127.0.0.1:8000")

    assert context is browser.context
    assert authenticated_url.endswith("/code-classroom/classroom-index")
    assert authenticated_pages == [browser.context.page]
    assert browser.context.page.closed is True
    assert browser.context_options == {"viewport": {"width": 1900, "height": 1000}, "locale": "zh-CN"}


def test_audit_result_passed_rejects_missing_actions_and_login_redirects() -> None:
    assert click_audit.audit_result_passed({"error": "label_not_found"}) is False
    assert click_audit.audit_result_passed({"is_login_redirect": True}) is False
    assert click_audit.audit_result_passed({"is_login_redirect": False}) is True


def test_classroom_tool_audit_uses_bounded_local_ui_waits() -> None:
    assert click_audit.POPUP_WAIT_TIMEOUT_MS == 1_500
    assert click_audit.ACTION_SETTLE_TIMEOUT_MS == 1_000


def test_classroom_tool_audit_navigation_uses_bounded_page_settle(monkeypatch) -> None:
    calls: list[tuple[object, str, dict[str, int]]] = []
    monkeypatch.setattr(
        click_audit,
        "navigate_for_audit",
        lambda page, url, **kwargs: calls.append((page, url, kwargs)),
    )
    page = object()

    click_audit.navigate(page, "http://127.0.0.1:8000/code-classroom/prepare-lessons")

    assert calls == [
        (
            page,
            "http://127.0.0.1:8000/code-classroom/prepare-lessons",
            {"networkidle_timeout_ms": 1_500, "settle_timeout_ms": 500},
        )
    ]
