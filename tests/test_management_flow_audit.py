from scripts import management_flow_audit


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.checked = False

    def raise_for_status(self) -> None:
        self.checked = True

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _canonical_admin_audit_result() -> dict:
    return {
        "is_login_redirect": False,
        "contains_canonical_admin_home": True,
        "class_page": {
            "contains_class_management": True,
            "contains_create_class": True,
            "rows": 1,
        },
        "student_page": {
            "contains_student_management": True,
            "contains_create_student": True,
            "rows": 1,
        },
        "mobile_overflow_free": True,
    }


def test_admin_page_passed_accepts_the_canonical_class_management_shell() -> None:
    assert management_flow_audit.admin_page_passed(_canonical_admin_audit_result()) is True


def test_admin_page_passed_rejects_legacy_admin_home_expectation() -> None:
    result = _canonical_admin_audit_result()
    result["contains_canonical_admin_home"] = False
    result["contains_original_admin_home"] = True

    assert management_flow_audit.admin_page_passed(result) is False


def test_cleanup_audit_student_deletes_the_created_student_through_the_api(monkeypatch) -> None:
    monkeypatch.setattr(management_flow_audit, "BASE", "http://testserver")
    response = FakeResponse({"success": True, "content": {"7": None}})
    session = FakeSession(response)

    result = management_flow_audit.cleanup_audit_student(
        session,
        {"Authorization": "Bearer teacher-token"},
        student_id=7,
    )

    assert response.checked is True
    assert result == {"student_id": 7, "deleted": True}
    assert session.calls == [
        {
            "url": session.calls[0]["url"],
            "headers": {"Authorization": "Bearer teacher-token"},
            "json": [7],
            "timeout": management_flow_audit.REQUEST_TIMEOUT,
        }
    ]
    assert session.calls[0]["url"].startswith("http://testserver/java-api/school/stu/batchDelete?t=")
