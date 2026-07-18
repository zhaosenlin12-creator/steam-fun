from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_URL = "https://steam.fun"
TEACHER_LOGIN_PATH = "/java-api/school/tch/login"
STUDENT_LOGIN_PATH = "/java-api/student/stu/login"
FRESH_AUTH_PATH = "/java-api/auth/sch/freshAuthData"
TEACHER_FRESH_DATA_PATH = "/java-api/school/tch/freshData"
STUDENT_FRESH_DATA_PATH = "/java-api/student/stu/freshData"
XHR_CAPTURE_RE = r"https://steam\.fun/(?:api|java-api)/.*"


@dataclass(frozen=True)
class AccountConfig:
    profile_name: str
    username: str
    password: str
    login_path: str
    initial_route: str = "/"


@dataclass(frozen=True)
class MirrorPaths:
    root: Path

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def db_path(self) -> Path:
        return self.runtime_dir / "mirror.sqlite3"

    @property
    def browser_dir(self) -> Path:
        return self.runtime_dir / "browser_profiles"

    @property
    def origin_dir(self) -> Path:
        return self.runtime_dir / "origin"

    @property
    def discovery_dir(self) -> Path:
        return self.runtime_dir / "discovery"

    @property
    def api_dir(self) -> Path:
        return self.runtime_dir / "api"

    @property
    def route_dir(self) -> Path:
        return self.runtime_dir / "routes"

    @property
    def external_dir(self) -> Path:
        return self.runtime_dir / "external"
