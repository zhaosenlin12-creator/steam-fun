from __future__ import annotations

import gzip
import hashlib
import json
import mimetypes
import shutil
import sqlite3
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import brotli

from .config import MirrorPaths


STUDENT_OVERLAY_FIELDS = (
    "deleted",
    "quit",
    "normal_state",
    "end_date",
    "zone_auth",
    "test_auth",
    "oj_auth",
    "oj_analysis_auth",
    "oj_testcase_auth",
    "stu_note_auth",
    "p_auth",
    "wechat_bound",
    "parent_wechat",
    "wcm_flag",
    "open_id",
    "authorizer_openid",
    "last_password_reset_at",
)

TEACHING_PLAN_OVERLAY_FIELDS = (
    "zone_auth",
    "oj_analysis_auth",
    "test_case_auth",
    "editor_showhint_auth",
    "class_work_url",
    "example_work_url",
    "homework_work_url",
    "source_tch_plan_id",
)


def _normalized_body_digest(body: bytes | None) -> str:
    if not body:
        return ""
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        normalized = body
    else:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


def _currmat_request_body_variants(body: bytes | None) -> list[bytes]:
    if not body:
        return []
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return []
    if not isinstance(payload, dict) or "currMatId" not in payload:
        return []

    curr_mat_id = payload.get("currMatId")
    variants: list[Any] = [{"currMatId": curr_mat_id}]
    if isinstance(curr_mat_id, str):
        stripped = curr_mat_id.strip()
        if stripped.isdigit():
            variants.append({"currMatId": int(stripped)})
    elif isinstance(curr_mat_id, int):
        variants.append({"currMatId": str(curr_mat_id)})

    serialized: list[bytes] = []
    seen: set[bytes] = set()
    for variant in variants:
        encoded = json.dumps(variant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if encoded in seen:
            continue
        seen.add(encoded)
        serialized.append(encoded)
    return serialized


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def api_cache_key(method: str, url: str, body: bytes | None = None) -> str:
    normalized_method = method.lower()
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "t"]
    query.sort()
    normalized_url = urlunparse(parsed._replace(query=urlencode(query)))
    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:16]
    body_digest = _normalized_body_digest(body)
    if body_digest:
        return f"{normalized_method}_{digest}_{body_digest}"
    return f"{normalized_method}_{digest}"


ASSET_EXTENSION_OVERRIDES = {
    "application/ecmascript": ".js",
    "application/javascript": ".js",
    "application/json": ".json",
    "application/wasm": ".wasm",
    "application/xhtml+xml": ".html",
    "application/xml": ".xml",
    "audio/mpeg": ".mp3",
    "font/woff": ".woff",
    "font/woff2": ".woff2",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "text/css": ".css",
    "text/ecmascript": ".js",
    "text/html": ".html",
    "text/javascript": ".js",
    "text/json": ".json",
    "text/plain": ".txt",
    "text/xml": ".xml",
}


def _normalized_content_type_value(content_type: str | None) -> str:
    return str(content_type or "").split(";", 1)[0].strip().lower()


def _asset_suffix_from_content_type(content_type: str | None) -> str:
    normalized = _normalized_content_type_value(content_type)
    if not normalized:
        return ""
    override = ASSET_EXTENSION_OVERRIDES.get(normalized)
    if override:
        return override
    guessed = mimetypes.guess_extension(normalized, strict=False) or ""
    if guessed == ".jpe":
        return ".jpg"
    return guessed


def _normalize_asset_storage_path(raw_path: str, *, default_index_suffix: str, content_type: str | None = None) -> str:
    cleaned_path = raw_path.lstrip("/")
    derived_suffix = _asset_suffix_from_content_type(content_type)
    if not cleaned_path:
        return f"index{derived_suffix or default_index_suffix}"
    if raw_path.endswith("/"):
        leaf = f"index{derived_suffix or default_index_suffix}"
        cleaned_path = f"{cleaned_path}{leaf}"
    elif not Path(cleaned_path).suffix:
        path_obj = Path(cleaned_path)
        synthetic_name = f"{path_obj.name}__asset__{derived_suffix}" if derived_suffix else f"{path_obj.name}__asset__"
        parent = path_obj.parent.as_posix()
        cleaned_path = synthetic_name if parent == "." else f"{parent}/{synthetic_name}"
    if cleaned_path and len(cleaned_path) > 180:
        suffix = Path(cleaned_path).suffix.lower() or derived_suffix
        digest = hashlib.sha256(cleaned_path.encode("utf-8")).hexdigest()
        cleaned_path = f"__hashed__/{digest}{suffix}"
    return cleaned_path


def external_asset_path(url: str, *, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    cleaned_path = _normalize_asset_storage_path(parsed.path, default_index_suffix="", content_type=content_type)
    return f"external/{parsed.netloc}/{cleaned_path}"


def origin_asset_path(url: str, *, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or "steam.fun"
    cleaned_path = _normalize_asset_storage_path(parsed.path, default_index_suffix=".html", content_type=content_type)
    return f"origin/{host}/{cleaned_path}"


def route_html_path(profile_name: str, route: str) -> str:
    cleaned = route.strip("/") or "root"
    cleaned = cleaned.replace(":", "__param__")
    cleaned = cleaned.replace("?", "_")
    cleaned = cleaned.replace("&", "_")
    cleaned = cleaned.replace("=", "_")
    return f"routes/{profile_name}/{cleaned}.html"


def _content_type(headers: dict[str, Any]) -> str:
    for key, value in headers.items():
        if key.lower() == "content-type":
            return str(value)
    return "application/octet-stream"


def _decode_response_body(body: bytes, headers: dict[str, Any]) -> bytes:
    encoding = ""
    for key, value in headers.items():
        if key.lower() == "content-encoding":
            encoding = str(value).lower()
            break
    if not encoding:
        return body

    decoded = body
    for part in reversed([item.strip() for item in encoding.split(",") if item.strip()]):
        try:
            if part == "br":
                decoded = brotli.decompress(decoded)
            elif part == "gzip":
                decoded = gzip.decompress(decoded)
            elif part == "deflate":
                decoded = zlib.decompress(decoded)
        except Exception:
            return body
    return decoded


class MirrorStore:
    def __init__(self, root: Path):
        self.paths = MirrorPaths(root.resolve())
        self._class_payload_cache: dict[str, dict[str, Any] | None] = {}
        self._ensure_dirs()
        self.init_db()

    @property
    def root(self) -> Path:
        return self.paths.root

    @property
    def db_path(self) -> Path:
        return self.paths.db_path

    def browser_profile_dir(self, profile_name: str) -> Path:
        path = self.paths.browser_dir / profile_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def fresh_browser_profile_dir(self, profile_name: str) -> Path:
        path = (self.paths.browser_dir / f"{profile_name}_capture").resolve()
        browser_root = self.paths.browser_dir.resolve()
        if browser_root != path.parent:
            raise ValueError(f"Refusing to reset browser profile outside {browser_root}: {path}")
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _ensure_dirs(self) -> None:
        for path in (
            self.paths.runtime_dir,
            self.paths.browser_dir,
            self.paths.origin_dir,
            self.paths.discovery_dir,
            self.paths.api_dir,
            self.paths.route_dir,
            self.paths.external_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    profile_name TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    login_path TEXT NOT NULL,
                    token TEXT NOT NULL,
                    login_content_json TEXT NOT NULL,
                    fresh_auth_json TEXT NOT NULL,
                    vuex_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS assets (
                    url TEXT PRIMARY KEY,
                    local_path TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS routes (
                    profile_name TEXT NOT NULL,
                    route TEXT NOT NULL,
                    final_url TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    html_path TEXT NOT NULL,
                    captured_xhr_count INTEGER NOT NULL,
                    PRIMARY KEY (profile_name, route)
                );

                CREATE TABLE IF NOT EXISTS api_responses (
                    profile_name TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    method TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    headers_json TEXT NOT NULL,
                    body_path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    PRIMARY KEY (profile_name, cache_key)
                );

                CREATE TABLE IF NOT EXISTS tch_work_self_remarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    remark TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS local_campuses (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    state INTEGER NOT NULL DEFAULT 1,
                    created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campus_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    realname TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    normal_state TEXT NOT NULL,
                    phone_num TEXT NOT NULL,
                    school_name TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    leader TEXT NOT NULL,
                    remark TEXT NOT NULL,
                    study_date TEXT NOT NULL,
                    headimg_url TEXT NOT NULL,
                    created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS student_overlays (
                    stu_id INTEGER PRIMARY KEY,
                    deleted INTEGER NOT NULL DEFAULT 0,
                    quit INTEGER NOT NULL DEFAULT 0,
                    normal_state TEXT,
                    end_date TEXT,
                    zone_auth INTEGER,
                    test_auth INTEGER,
                    oj_auth INTEGER,
                    oj_analysis_auth INTEGER,
                    oj_testcase_auth INTEGER,
                    stu_note_auth INTEGER,
                    p_auth INTEGER,
                    wechat_bound INTEGER,
                    parent_wechat TEXT,
                    wcm_flag TEXT,
                    open_id TEXT,
                    authorizer_openid TEXT,
                    last_password_reset_at TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS teaching_plan_overlays (
                    teaching_plan_id INTEGER PRIMARY KEY,
                    zone_auth INTEGER,
                    oj_analysis_auth INTEGER,
                    test_case_auth INTEGER,
                    editor_showhint_auth INTEGER,
                    class_work_url TEXT,
                    example_work_url TEXT,
                    homework_work_url TEXT,
                    source_tch_plan_id INTEGER,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_classes (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    educational_institution_campus_id INTEGER NOT NULL DEFAULT 0,
                    lecturer_id INTEGER,
                    lecturer_name TEXT,
                    assistant_teacher_id INTEGER,
                    curriculum_class_type INTEGER,
                    teaching_type INTEGER,
                    end_class_state INTEGER,
                    week_json TEXT NOT NULL DEFAULT '[]',
                    week_str TEXT NOT NULL DEFAULT '',
                    time_str TEXT NOT NULL DEFAULT '',
                    subject_id_list_json TEXT NOT NULL DEFAULT '[]',
                    curriculum_id_list_json TEXT NOT NULL DEFAULT '[]',
                    class_code TEXT,
                    is_cost_lesson_hour INTEGER NOT NULL DEFAULT 0,
                    deleted INTEGER NOT NULL DEFAULT 0,
                    membership_override INTEGER NOT NULL DEFAULT 0,
                    created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_class_students (
                    class_id INTEGER NOT NULL,
                    student_user_id INTEGER NOT NULL,
                    xm_goods_id INTEGER,
                    receipt_goods_id INTEGER,
                    in_class_date TEXT,
                    out_class_date TEXT,
                    out_class_reason TEXT,
                    created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (class_id, student_user_id)
                );

                CREATE TABLE IF NOT EXISTS local_teaching_plans (
                    id INTEGER PRIMARY KEY,
                    curriculum_class_id INTEGER NOT NULL,
                    educational_institution_campus_id INTEGER NOT NULL DEFAULT 0,
                    lecturer_id INTEGER,
                    lecturer_name TEXT,
                    subject_id INTEGER,
                    curriculum_id INTEGER,
                    curriculum_meterial_id INTEGER,
                    class_date TEXT,
                    start_class_date TEXT,
                    end_class_date TEXT,
                    sign_state INTEGER,
                    sign_state_new INTEGER,
                    sign_date TEXT,
                    cost_lesson_hour REAL,
                    sort_num INTEGER,
                    title TEXT,
                    custom_lesson_title TEXT,
                    custom_lesson_desc TEXT,
                    is_cost_lesson_hour INTEGER NOT NULL DEFAULT 0,
                    deleted INTEGER NOT NULL DEFAULT 0,
                    student_override INTEGER NOT NULL DEFAULT 0,
                    created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_teaching_plan_students (
                    teaching_plan_id INTEGER NOT NULL,
                    student_user_id INTEGER NOT NULL,
                    stu_tch_plan_type INTEGER NOT NULL DEFAULT 1,
                    sign_state INTEGER,
                    sign_date TEXT,
                    cost_state TEXT,
                    cost_lesson_hour REAL,
                    over_lesson_hour REAL,
                    not_come_reason TEXT,
                    remark TEXT,
                    xm_goods_id INTEGER,
                    receipt_goods_id INTEGER,
                    created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (teaching_plan_id, student_user_id)
                );

                CREATE TABLE IF NOT EXISTS local_student_exam_runs (
                    exam_id INTEGER NOT NULL,
                    stu_id INTEGER NOT NULL DEFAULT 0,
                    paper_id INTEGER,
                    title TEXT,
                    started_at TEXT,
                    submitted_at TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (exam_id, stu_id)
                );

                CREATE TABLE IF NOT EXISTS local_student_exam_answers (
                    exam_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    stu_id INTEGER NOT NULL DEFAULT 0,
                    stu_exam_question_id INTEGER NOT NULL,
                    answer TEXT,
                    question_score REAL,
                    score REAL,
                    submitted_at TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (exam_id, question_id, stu_id)
                );

                CREATE TABLE IF NOT EXISTS local_subject_snapshots (
                    id INTEGER PRIMARY KEY,
                    code INTEGER,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_curriculum_snapshots (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_curriculum_material_snapshots (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER,
                    curriculum_id INTEGER,
                    title TEXT NOT NULL,
                    ppt_url TEXT,
                    video_url TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS curriculum_material_archives (
                    material_id INTEGER PRIMARY KEY,
                    root_url_count INTEGER NOT NULL DEFAULT 0,
                    fetched_asset_count INTEGER NOT NULL DEFAULT 0,
                    missing_asset_count INTEGER NOT NULL DEFAULT 0,
                    all_local INTEGER NOT NULL DEFAULT 0,
                    last_verified_at TEXT,
                    manifest_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS curriculum_material_archive_assets (
                    material_id INTEGER NOT NULL,
                    asset_url TEXT NOT NULL,
                    local_path TEXT NOT NULL DEFAULT '',
                    status INTEGER NOT NULL DEFAULT 0,
                    content_type TEXT NOT NULL DEFAULT '',
                    required INTEGER NOT NULL DEFAULT 1,
                    present INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (material_id, asset_url)
                );
                """
            )
            self._run_localization_migrations(connection)

    @staticmethod
    def _localize_persisted_value(value: Any) -> Any:
        from .auth import localize_external_values

        return localize_external_values(value)

    def _run_localization_migrations(self, connection: sqlite3.Connection) -> None:
        self._ensure_optional_column(connection, "student_overlays", "end_date", "TEXT")
        self._migrate_profile_json_to_local_urls(connection)
        self._migrate_local_student_assets_to_local_urls(connection)

    @staticmethod
    def _ensure_optional_column(
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        existing_columns = {
            str(row["name"]).strip()
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

    def _migrate_profile_json_to_local_urls(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT profile_name, login_content_json, fresh_auth_json, vuex_json
            FROM profiles
            """
        ).fetchall()
        for row in rows:
            updates: dict[str, str] = {}
            for field in ("login_content_json", "fresh_auth_json", "vuex_json"):
                raw_value = row[field]
                try:
                    payload = json.loads(raw_value)
                except Exception:
                    continue
                localized_payload = self._localize_persisted_value(payload)
                serialized = json.dumps(localized_payload, ensure_ascii=False)
                if serialized != raw_value:
                    updates[field] = serialized

            if not updates:
                continue

            connection.execute(
                """
                UPDATE profiles
                SET login_content_json = ?, fresh_auth_json = ?, vuex_json = ?
                WHERE profile_name = ?
                """,
                (
                    updates.get("login_content_json", row["login_content_json"]),
                    updates.get("fresh_auth_json", row["fresh_auth_json"]),
                    updates.get("vuex_json", row["vuex_json"]),
                    row["profile_name"],
                ),
            )

    def _migrate_local_student_assets_to_local_urls(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, headimg_url
            FROM local_students
            """
        ).fetchall()
        for row in rows:
            headimg_url = row["headimg_url"] or ""
            localized_headimg_url = str(self._localize_persisted_value(headimg_url) or "").strip()
            if localized_headimg_url == headimg_url:
                continue
            connection.execute(
                "UPDATE local_students SET headimg_url = ? WHERE id = ?",
                (localized_headimg_url, row["id"]),
            )

    def write_bytes(self, relative_path: str, body: bytes) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def write_text(self, relative_path: str, text: str) -> Path:
        return self.write_bytes(relative_path, text.encode("utf-8"))

    def write_json(self, relative_path: str, payload: Any) -> Path:
        return self.write_text(relative_path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _relocate_conflicting_asset_ancestor(self, relative_path: str) -> None:
        target_path = self.root / relative_path
        for ancestor in target_path.parents:
            if ancestor == self.root:
                break
            if not ancestor.exists() or not ancestor.is_file():
                continue
            ancestor_relative = ancestor.relative_to(self.root).as_posix()
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT url, content_type, local_path FROM assets WHERE local_path = ?",
                    (ancestor_relative,),
                ).fetchone()
            if row is None:
                raise FileExistsError(f"Conflicting unmanaged asset path: {ancestor}")
            content_type = str(row["content_type"] or "")
            is_external = ancestor_relative.startswith("external/")
            replacement_path = (
                external_asset_path(str(row["url"]), content_type=content_type)
                if is_external
                else origin_asset_path(str(row["url"]), content_type=content_type)
            )
            replacement_full_path = self.root / replacement_path
            if replacement_full_path == ancestor:
                raise FileExistsError(f"Unable to relocate conflicting asset path: {ancestor}")
            replacement_full_path.parent.mkdir(parents=True, exist_ok=True)
            ancestor.replace(replacement_full_path)
            with self._connect() as connection:
                connection.execute(
                    "UPDATE assets SET local_path = ? WHERE url = ?",
                    (replacement_path, row["url"]),
                )

    def _prune_replaced_asset_file(self, prior_local_path: str | None, next_local_path: str) -> None:
        previous = str(prior_local_path or "").strip()
        if not previous or previous == next_local_path:
            return
        previous_path = self.root / previous
        if previous_path.exists() and previous_path.is_file():
            previous_path.unlink()

    def store_discovery(self, name: str, payload: Any) -> Path:
        return self.write_json(f"runtime/discovery/{name}.json", payload)

    def store_origin_asset(
        self,
        url: str,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, Any] | None = None,
    ) -> str:
        return self.store_origin_asset_stream(url, [body], status=status, headers=headers)

    def store_external_asset(
        self,
        url: str,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, Any] | None = None,
    ) -> str:
        return self.store_external_asset_stream(url, [body], status=status, headers=headers)

    def store_origin_asset_stream(
        self,
        url: str,
        chunks: Any,
        *,
        status: int = 200,
        headers: dict[str, Any] | None = None,
    ) -> str:
        return self._store_asset_stream(url, chunks, external=False, status=status, headers=headers)

    def store_external_asset_stream(
        self,
        url: str,
        chunks: Any,
        *,
        status: int = 200,
        headers: dict[str, Any] | None = None,
    ) -> str:
        return self._store_asset_stream(url, chunks, external=True, status=status, headers=headers)

    def _store_asset_stream(
        self,
        url: str,
        chunks: Any,
        *,
        external: bool,
        status: int = 200,
        headers: dict[str, Any] | None = None,
    ) -> str:
        headers = headers or {}
        content_type = _content_type(headers)
        relative_path = (
            external_asset_path(url, content_type=content_type)
            if external
            else origin_asset_path(url, content_type=content_type)
        )
        existing = self.lookup_asset(url)
        previous_local_path = str((existing or {}).get("local_path") or "")
        self._relocate_conflicting_asset_ancestor(relative_path)
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with path.open("wb") as handle:
            for chunk in chunks:
                if not chunk:
                    continue
                handle.write(chunk)
                digest.update(chunk)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO assets (url, local_path, status, content_type, sha256)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    url,
                    relative_path,
                    status,
                    content_type,
                    digest.hexdigest(),
                ),
            )
        self._prune_replaced_asset_file(previous_local_path, relative_path)
        return relative_path

    def lookup_asset(self, url: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT url, local_path, status, content_type, sha256
                FROM assets
                WHERE url = ?
                """,
                (url,),
            ).fetchone()
        if row is None:
            return None
        body_path = self.root / row["local_path"]
        return {
            "url": row["url"],
            "local_path": row["local_path"],
            "status": row["status"],
            "content_type": row["content_type"],
            "sha256": row["sha256"],
            "body": body_path.read_bytes() if body_path.exists() else b"",
        }

    def all_asset_urls(self) -> set[str]:
        """Return every known asset URL keyed exactly as stored."""
        with self._connect() as connection:
            rows = connection.execute("SELECT url FROM assets").fetchall()
        return {row["url"] for row in rows}

    def store_profile(
        self,
        *,
        profile_name: str,
        username: str,
        password_hash: str,
        login_path: str,
        token: str,
        login_content: Any,
        fresh_auth: Any,
        vuex_state: Any,
    ) -> None:
        login_content = self._localize_persisted_value(login_content)
        fresh_auth = self._localize_persisted_value(fresh_auth)
        vuex_state = self._localize_persisted_value(vuex_state)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO profiles (
                    profile_name, username, password_hash, login_path, token,
                    login_content_json, fresh_auth_json, vuex_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_name,
                    username,
                    password_hash,
                    login_path,
                    token,
                    json.dumps(login_content, ensure_ascii=False),
                    json.dumps(fresh_auth, ensure_ascii=False),
                    json.dumps(vuex_state, ensure_ascii=False),
                ),
            )

    def get_profile(self, profile_name: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE profile_name = ?",
                (profile_name,),
            ).fetchone()
        return self._row_to_profile(row)

    def get_profile_by_username(self, username: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE username = ?",
                (username,),
            ).fetchone()
        return self._row_to_profile(row)

    def get_profile_by_token(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE token = ?",
                (token,),
            ).fetchone()
        return self._row_to_profile(row)

    def list_profiles(self, *, login_path: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM profiles"
        params: tuple[Any, ...] = ()
        if login_path is not None:
            query += " WHERE login_path = ?"
            params = (login_path,)
        query += " ORDER BY profile_name"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        profiles: list[dict[str, Any]] = []
        for row in rows:
            profile = self._row_to_profile(row)
            if profile is not None:
                profiles.append(profile)
        return profiles

    def delete_profile(self, profile_name: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM profiles WHERE profile_name = ?",
                (profile_name,),
            )
        return cursor.rowcount > 0

    def find_local_student_by_username(self, username: str) -> dict[str, Any] | None:
        """Look up a local_students row by account name or phone number."""
        if not username:
            return None
        normalized = str(username).strip()
        if not normalized:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, campus_id, name, realname, sex, normal_state, phone_num,
                       school_name, grade, leader, remark, study_date, headimg_url, created_time
                FROM local_students
                WHERE name = ? OR phone_num = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (normalized, normalized),
            ).fetchone()
        return self._local_student_row_to_dict(row) if row is not None else None

    def upsert_student_login_profile(
        self,
        student_row: dict[str, Any],
        *,
        password_hash: str,
        token: str,
        login_path: str,
    ) -> dict[str, Any]:
        """Provision or update a profiles row for a local student so they can sign in."""
        student_id = int(student_row.get("id") or 0)
        if student_id <= 0:
            raise ValueError("student_row must have a positive id")
        username = str(student_row.get("name") or student_row.get("phone_num") or "").strip()
        if not username:
            raise ValueError("student_row must have a username or phone number")
        profile_name = f"local_student_{student_id}"

        student_info_payload = {
            "id": student_id,
            "eduId": int(student_row.get("campus_id") or 0) or 834,
            "name": username,
            "zoneAuth": True,
            "code": f"local-student-{student_id}",
            "headimgUrl": str(student_row.get("headimg_url") or ""),
            "stuNoteAuth": True,
            "eduCampusId": int(student_row.get("campus_id") or 851),
            "testAuth": True,
            "ojAuth": True,
            "ojAnalysisAuth": True,
            "createdTime": str(student_row.get("created_time") or ""),
            "ojTestcaseAuth": True,
            "stuUserInfo": {
                "id": student_id,
                "schoolName": str(student_row.get("school_name") or ""),
                "sex": str(student_row.get("sex") or ""),
                "birthday": None,
                "grade": str(student_row.get("grade") or "") or None,
                "parentA": None,
                "parentAPhoneNum": str(student_row.get("phone_num") or ""),
                "parentB": None,
                "parentBPhoneNum": "",
                "createdTime": str(student_row.get("created_time") or ""),
                "realName": str(student_row.get("realname") or username),
                "nickname": "",
                "remark": str(student_row.get("remark") or ""),
                "leader": str(student_row.get("leader") or "") or None,
                "eduId": int(student_row.get("campus_id") or 0) or 834,
            },
            "pauth": True,
        }

        fresh_auth = {
            "identity": 2,
            "userInfo": {"stuUserInfo": student_info_payload},
            "schoolInfo": {
                "id": int(student_row.get("campus_id") or 834),
                "name": str(student_row.get("school_name") or "") or "Local Campus",
                "domain": "local",
                "offTime": "2099-12-31 23:59:59",
                "maxTeacherNum": 5,
                "maxStudentNum": 10000,
                "stuRemainTime": 99999,
                "authorize": False,
                "stopDate": None,
                "isTry": False,
                "questionBankPermission": True,
                "ojPermission": True,
                "pointAuth": True,
                "zoneShareAuth": False,
                "adminNoticeAuth": True,
                "questionBankShowType": 2,
                "themeColor": "#1778FF",
                "authorizerNickName": "",
                "authorizerHeadImg": "",
                "authorizerQrcodeUrl": "",
                "authorizerServiceTypeInfo": None,
                "authorizerVerifyTypeInfo": None,
                "useStorage": 0.0,
                "totalStorage": 52428800.0,
                "remainTraffic": 52428800.0,
                "ojRankTotalAuth": True,
                "wechatQr": True,
                "wechatMiniQr": True,
                "stuZoneAuth": True,
                "typingPlanetAuth": True,
            },
            "roleList": [],
        }

        login_content = token

        vuex_state = {
            "user": {
                "username": username,
                "token": token,
                "adminUserName": "",
                "adminUserId": None,
                "adminToken": "",
                "isSuperAdmin": False,
                "is_principal": False,
                "roleList": "",
                "selected_schools": [],
                "permisionList": [],
                "adminpermisionList": [],
                "userInfo": student_info_payload,
                    "stuUserInfo": student_info_payload["stuUserInfo"],
                "realname": str(student_row.get("realname") or username),
                "isStudent": True,
                "isTeacher": False,
                "isAdmin": False,
                "eduCampusId": int(student_row.get("campus_id") or 851),
                "eduId": int(student_row.get("campus_id") or 0) or 834,
                "schoolId": int(student_row.get("campus_id") or 834),
                "campusId": int(student_row.get("campus_id") or 851),
            },
        }

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO profiles (
                    profile_name, username, password_hash, login_path, token,
                    login_content_json, fresh_auth_json, vuex_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_name,
                    username,
                    password_hash,
                    login_path,
                    token,
                    json.dumps(login_content, ensure_ascii=False),
                    json.dumps(fresh_auth, ensure_ascii=False),
                    json.dumps(vuex_state, ensure_ascii=False),
                ),
            )

        return {
            "profile_name": profile_name,
            "username": username,
            "password_hash": password_hash,
            "login_path": login_path,
            "token": token,
            "login_content": login_content,
            "fresh_auth": fresh_auth,
            "vuex_state": vuex_state,
        }

    def _row_to_profile(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "profile_name": row["profile_name"],
            "username": row["username"],
            "password_hash": row["password_hash"],
            "login_path": row["login_path"],
            "token": row["token"],
            "login_content": json.loads(row["login_content_json"]),
            "fresh_auth": json.loads(row["fresh_auth_json"]),
            "vuex_state": json.loads(row["vuex_json"]),
        }

    def store_api_response(
        self,
        profile_name: str,
        *,
        method: str,
        url: str,
        status: int,
        headers: dict[str, Any],
        body: bytes,
        request_body: bytes | None = None,
    ) -> str:
        cache_key = api_cache_key(method, url, request_body)
        relative_path = f"runtime/api/{profile_name}/{cache_key}.bin"
        self.write_bytes(relative_path, body)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO api_responses (
                    profile_name, cache_key, method, url, status, headers_json, body_path, content_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_name,
                    cache_key,
                    method.upper(),
                    url,
                    status,
                    json.dumps(dict(headers), ensure_ascii=False),
                    relative_path,
                    _content_type(dict(headers)),
                ),
            )
        return relative_path

    def lookup_api_response(
        self,
        profile_name: str,
        *,
        method: str,
        url: str,
        request_body: bytes | None = None,
    ) -> dict[str, Any] | None:
        cache_keys = [api_cache_key(method, url, request_body)]
        legacy_key = api_cache_key(method, url)
        if legacy_key not in cache_keys:
            cache_keys.append(legacy_key)
        parsed = urlparse(url)
        if parsed.path == "/java-api/school/currMat/detail":
            for body_variant in _currmat_request_body_variants(request_body):
                variant_key = api_cache_key(method, url, body_variant)
                if variant_key not in cache_keys:
                    cache_keys.append(variant_key)
        with self._connect() as connection:
            row = None
            for cache_key in cache_keys:
                row = connection.execute(
                    """
                    SELECT * FROM api_responses
                    WHERE profile_name = ? AND cache_key = ?
                    """,
                    (profile_name, cache_key),
                ).fetchone()
                if row is not None:
                    break
        if row is None:
            return None
        body_path = self.root / row["body_path"]
        return {
            "profile_name": row["profile_name"],
            "cache_key": row["cache_key"],
            "method": row["method"],
            "url": row["url"],
            "status": row["status"],
            "headers": json.loads(row["headers_json"]),
            "body_path": row["body_path"],
            "body": body_path.read_bytes() if body_path.exists() else b"",
            "content_type": row["content_type"],
        }

    def find_curriculum_material(self, curr_mat_id: int | str) -> dict[str, Any] | None:
        wanted = str(curr_mat_id).strip()
        if not wanted:
            return None
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT body_path
                FROM api_responses
                WHERE method = 'GET'
                  AND profile_name = 'teacher'
                  AND url LIKE '%/api/prepare/get/currculumMaterialList%'
                ORDER BY url
                """,
            ).fetchall()
        for row in rows:
            body_path = self.root / row["body_path"]
            if not body_path.exists():
                continue
            try:
                payload = json.loads(body_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            content = payload.get("content") or {}
            materials = content.get("curriculumMaterialList") or content.get("currculumMaterialList") or []
            if not isinstance(materials, list):
                continue
            for material in materials:
                if isinstance(material, dict) and str(material.get("id", "")).strip() == wanted:
                    return material
        return None

    def list_curriculum_materials(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT body_path
                FROM api_responses
                WHERE method = 'GET'
                  AND profile_name = 'teacher'
                  AND url LIKE '%/api/prepare/get/currculumMaterialList%'
                ORDER BY url
                """,
            ).fetchall()

        materials_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            body_path = self.root / row["body_path"]
            if not body_path.exists():
                continue
            try:
                payload = json.loads(body_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            content = payload.get("content") or {}
            materials = content.get("curriculumMaterialList") or content.get("currculumMaterialList") or []
            if not isinstance(materials, list):
                continue
            for material in materials:
                if not isinstance(material, dict):
                    continue
                material_id = str(material.get("id", "")).strip()
                if not material_id or material_id in materials_by_id:
                    continue
                materials_by_id[material_id] = material

        def sort_key(material: dict[str, Any]) -> tuple[int, int, int]:
            return (
                int(material.get("curriculum_id") or 0),
                int(material.get("sort_num") or material.get("sortNum") or 0),
                int(material.get("id") or 0),
            )

        return sorted(materials_by_id.values(), key=sort_key)

    def _local_subject_snapshot_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(
            {
                "id": row["id"],
                "code": row["code"],
                "name": row["name"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def list_local_subject_snapshots(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, code, name, payload_json, updated_at
                FROM local_subject_snapshots
                ORDER BY id
                """
            ).fetchall()
        return [self._local_subject_snapshot_row_to_dict(row) for row in rows]

    def get_local_subject_snapshot(self, subject_id: int | str | None) -> dict[str, Any] | None:
        normalized_subject_id = _coerce_int(subject_id)
        if normalized_subject_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, code, name, payload_json, updated_at
                FROM local_subject_snapshots
                WHERE id = ?
                """,
                (normalized_subject_id,),
            ).fetchone()
        return self._local_subject_snapshot_row_to_dict(row) if row is not None else None

    @staticmethod
    def _merge_snapshot_payload(current: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current or {})
        merged.update(updates)
        return merged

    def upsert_local_subject_snapshot(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        normalized = self._localize_persisted_value(payload)
        subject_id = _coerce_int(normalized.get("id"))
        if subject_id is None:
            return None
        merged = self._merge_snapshot_payload(self.get_local_subject_snapshot(subject_id), normalized)
        merged["id"] = subject_id
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_subject_snapshots (
                    id, code, name, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    subject_id,
                    _coerce_int(merged.get("code")),
                    str(merged.get("name") or ""),
                    json.dumps(merged, ensure_ascii=False),
                ),
            )
        return self.get_local_subject_snapshot(subject_id)

    def _local_curriculum_snapshot_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(
            {
                "id": row["id"],
                "subject_id": row["subject_id"],
                "title": row["title"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def list_local_curriculum_snapshots(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, subject_id, title, payload_json, updated_at
                FROM local_curriculum_snapshots
                ORDER BY id
                """
            ).fetchall()
        return [self._local_curriculum_snapshot_row_to_dict(row) for row in rows]

    def get_local_curriculum_snapshot(self, curriculum_id: int | str | None) -> dict[str, Any] | None:
        normalized_curriculum_id = _coerce_int(curriculum_id)
        if normalized_curriculum_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, subject_id, title, payload_json, updated_at
                FROM local_curriculum_snapshots
                WHERE id = ?
                """,
                (normalized_curriculum_id,),
            ).fetchone()
        return self._local_curriculum_snapshot_row_to_dict(row) if row is not None else None

    def upsert_local_curriculum_snapshot(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        normalized = self._localize_persisted_value(payload)
        curriculum_id = _coerce_int(normalized.get("id"))
        if curriculum_id is None:
            return None
        merged = self._merge_snapshot_payload(self.get_local_curriculum_snapshot(curriculum_id), normalized)
        merged["id"] = curriculum_id
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_curriculum_snapshots (
                    id, subject_id, title, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    curriculum_id,
                    _coerce_int(merged.get("subject_id")),
                    str(merged.get("title") or ""),
                    json.dumps(merged, ensure_ascii=False),
                ),
            )
        return self.get_local_curriculum_snapshot(curriculum_id)

    def _local_curriculum_material_snapshot_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(
            {
                "id": row["id"],
                "subject_id": row["subject_id"],
                "curriculum_id": row["curriculum_id"],
                "title": row["title"],
                "ppt_url": row["ppt_url"],
                "video_url": row["video_url"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def list_local_curriculum_material_snapshots(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, subject_id, curriculum_id, title, ppt_url, video_url, payload_json, updated_at
                FROM local_curriculum_material_snapshots
                ORDER BY id
                """
            ).fetchall()
        return [self._local_curriculum_material_snapshot_row_to_dict(row) for row in rows]

    def get_local_curriculum_material_snapshot(self, material_id: int | str | None) -> dict[str, Any] | None:
        normalized_material_id = _coerce_int(material_id)
        if normalized_material_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, subject_id, curriculum_id, title, ppt_url, video_url, payload_json, updated_at
                FROM local_curriculum_material_snapshots
                WHERE id = ?
                """,
                (normalized_material_id,),
            ).fetchone()
        return self._local_curriculum_material_snapshot_row_to_dict(row) if row is not None else None

    def upsert_local_curriculum_material_snapshot(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        normalized = self._localize_persisted_value(payload)
        material_id = _coerce_int(normalized.get("id"))
        if material_id is None:
            return None
        merged = self._merge_snapshot_payload(self.get_local_curriculum_material_snapshot(material_id), normalized)
        merged["id"] = material_id
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_curriculum_material_snapshots (
                    id, subject_id, curriculum_id, title, ppt_url, video_url, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    material_id,
                    _coerce_int(merged.get("subject_id")),
                    _coerce_int(merged.get("curriculum_id")),
                    str(merged.get("title") or ""),
                    str(merged.get("ppt_url") or ""),
                    str(merged.get("video_url") or ""),
                    json.dumps(merged, ensure_ascii=False),
                ),
            )
        return self.get_local_curriculum_material_snapshot(material_id)

    def _curriculum_material_archive_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            manifest = json.loads(row["manifest_json"])
        except Exception:
            manifest = {}
        return {
            "material_id": row["material_id"],
            "root_url_count": row["root_url_count"],
            "fetched_asset_count": row["fetched_asset_count"],
            "missing_asset_count": row["missing_asset_count"],
            "all_local": bool(row["all_local"]),
            "last_verified_at": row["last_verified_at"],
            "manifest": manifest if isinstance(manifest, dict) else {},
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _curriculum_material_archive_asset_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "material_id": row["material_id"],
            "asset_url": row["asset_url"],
            "local_path": row["local_path"],
            "status": row["status"],
            "content_type": row["content_type"],
            "required": bool(row["required"]),
            "present": bool(row["present"]),
        }

    def get_curriculum_material_archive(self, material_id: int | str | None) -> dict[str, Any] | None:
        normalized_material_id = _coerce_int(material_id)
        if normalized_material_id is None:
            return None
        with self._connect() as connection:
            archive_row = connection.execute(
                """
                SELECT material_id, root_url_count, fetched_asset_count, missing_asset_count,
                       all_local, last_verified_at, manifest_json, updated_at
                FROM curriculum_material_archives
                WHERE material_id = ?
                """,
                (normalized_material_id,),
            ).fetchone()
            asset_rows = connection.execute(
                """
                SELECT material_id, asset_url, local_path, status, content_type, required, present
                FROM curriculum_material_archive_assets
                WHERE material_id = ?
                ORDER BY rowid
                """,
                (normalized_material_id,),
            ).fetchall()
        if archive_row is None:
            return None
        return {
            "archive": self._curriculum_material_archive_row_to_dict(archive_row),
            "assets": [self._curriculum_material_archive_asset_row_to_dict(row) for row in asset_rows],
        }

    def upsert_curriculum_material_archive(
        self,
        material_id: int | str | None,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized_material_id = _coerce_int(material_id)
        if normalized_material_id is None:
            return None
        current_archive = (self.get_curriculum_material_archive(normalized_material_id) or {}).get("archive") or {}
        manifest = self._localize_persisted_value(
            updates.get("manifest")
            if "manifest" in updates
            else updates.get("manifest_json", current_archive.get("manifest", {}))
        )
        if isinstance(manifest, str):
            try:
                manifest = json.loads(manifest)
            except Exception:
                manifest = {}
        if not isinstance(manifest, dict):
            manifest = {}
        merged = {
            "root_url_count": self._normalize_optional_int(
                updates.get("root_url_count"),
                current_archive.get("root_url_count"),
            )
            or 0,
            "fetched_asset_count": self._normalize_optional_int(
                updates.get("fetched_asset_count"),
                current_archive.get("fetched_asset_count"),
            )
            or 0,
            "missing_asset_count": self._normalize_optional_int(
                updates.get("missing_asset_count"),
                current_archive.get("missing_asset_count"),
            )
            or 0,
            "all_local": int(
                bool(
                    self._normalize_optional_int(
                        updates.get("all_local"),
                        current_archive.get("all_local"),
                    )
                    or 0
                )
            ),
            "last_verified_at": self._normalize_optional_text(
                updates.get("last_verified_at"),
                current_archive.get("last_verified_at"),
            ),
            "manifest_json": json.dumps(manifest, ensure_ascii=False),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO curriculum_material_archives (
                    material_id, root_url_count, fetched_asset_count, missing_asset_count,
                    all_local, last_verified_at, manifest_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normalized_material_id,
                    merged["root_url_count"],
                    merged["fetched_asset_count"],
                    merged["missing_asset_count"],
                    merged["all_local"],
                    merged["last_verified_at"],
                    merged["manifest_json"],
                ),
            )
        return self.get_curriculum_material_archive(normalized_material_id)

    def replace_curriculum_material_archive_assets(
        self,
        material_id: int | str | None,
        assets: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        normalized_material_id = _coerce_int(material_id)
        if normalized_material_id is None:
            return None
        normalized_assets_by_url: dict[str, tuple[Any, ...]] = {}
        for asset in assets:
            asset_url = str(asset.get("asset_url") or "").strip()
            if not asset_url:
                continue
            normalized_assets_by_url[asset_url] = (
                normalized_material_id,
                asset_url,
                str(asset.get("local_path") or ""),
                self._normalize_optional_int(asset.get("status")) or 0,
                str(asset.get("content_type") or ""),
                int(bool(self._normalize_optional_int(asset.get("required"), 1) if asset.get("required") is not None else 1)),
                int(bool(self._normalize_optional_int(asset.get("present"), 0) if asset.get("present") is not None else 0)),
            )
        normalized_assets = list(normalized_assets_by_url.values())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO curriculum_material_archives (
                    material_id
                ) VALUES (?)
                """,
                (normalized_material_id,),
            )
            connection.execute(
                "DELETE FROM curriculum_material_archive_assets WHERE material_id = ?",
                (normalized_material_id,),
            )
            if normalized_assets:
                connection.executemany(
                    """
                    INSERT INTO curriculum_material_archive_assets (
                        material_id, asset_url, local_path, status, content_type, required, present
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    normalized_assets,
                )
        return self.get_curriculum_material_archive(normalized_material_id)

    def load_api_payloads(
        self,
        profile_name: str,
        url_fragment: str,
        *,
        method: str = "GET",
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT body_path, headers_json
                FROM api_responses
                WHERE method = ?
                  AND profile_name = ?
                  AND url LIKE ?
                ORDER BY url
                """,
                (method.upper(), profile_name, f"%{url_fragment}%"),
            ).fetchall()

        payloads: list[dict[str, Any]] = []
        for row in rows:
            body_path = self.root / row["body_path"]
            if not body_path.exists():
                continue
            try:
                headers = json.loads(row["headers_json"])
                body = _decode_response_body(body_path.read_bytes(), headers)
                payload = json.loads(body.decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _load_teacher_api_payloads(self, url_fragment: str) -> list[dict[str, Any]]:
        return self.load_api_payloads("teacher", url_fragment)

    def list_campus_subjects(self) -> list[dict[str, Any]]:
        subjects_by_id: dict[str, dict[str, Any]] = {}
        for payload in self._load_teacher_api_payloads("/api/get/campus/subject/list"):
            content = payload.get("content") or {}
            subjects = content.get("campusSubjectList") or []
            if not isinstance(subjects, list):
                continue
            for subject in subjects:
                if not isinstance(subject, dict):
                    continue
                subject_id = str(subject.get("id", "")).strip()
                if not subject_id or subject_id in subjects_by_id:
                    continue
                subjects_by_id[subject_id] = subject

        return sorted(
            subjects_by_id.values(),
            key=lambda subject: (
                int(subject.get("sort_num") or 0),
                int(subject.get("id") or 0),
            ),
        )

    def list_campus_curriculum_auths(self) -> list[dict[str, Any]]:
        entries_by_curriculum_id: dict[str, dict[str, Any]] = {}
        for payload in self._load_teacher_api_payloads("/api/get/campus/curriculum/list/by/page"):
            content = payload.get("content") or {}
            entries = content.get("campusAuthList") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                curriculum_info = entry.get("curriculumInfo") or {}
                curriculum_id = str(
                    curriculum_info.get("id")
                    or entry.get("curriculum_id")
                    or entry.get("id")
                    or ""
                ).strip()
                if not curriculum_id or curriculum_id in entries_by_curriculum_id:
                    continue
                entries_by_curriculum_id[curriculum_id] = entry

        def sort_key(entry: dict[str, Any]) -> tuple[int, int]:
            curriculum_info = entry.get("curriculumInfo") or {}
            return (
                int(curriculum_info.get("sort_num") or 0),
                int(curriculum_info.get("id") or entry.get("curriculum_id") or 0),
            )

        return sorted(entries_by_curriculum_id.values(), key=sort_key)

    def list_competition_sources(self) -> list[dict[str, Any]]:
        sources_by_id: dict[str, dict[str, Any]] = {}

        def merge_source(candidate: Any) -> None:
            if not isinstance(candidate, dict):
                return
            localized_candidate = self._localize_persisted_value(candidate)
            source_id = str(localized_candidate.get("id") or "").strip()
            if not source_id:
                return

            current = dict(sources_by_id.get(source_id, {}))
            for key, value in localized_candidate.items():
                if current.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                    current[key] = value

            current["id"] = _coerce_int(localized_candidate.get("id")) or localized_candidate.get("id")
            if current.get("title") in (None, ""):
                current["title"] = f"Source {source_id}"
            current.setdefault("sort_num", _coerce_int(localized_candidate.get("sort_num")) or int(source_id))
            current.setdefault("source_type", localized_candidate.get("source_type") or 1)
            current.setdefault("match_type", localized_candidate.get("match_type") or 1)
            current.setdefault("realExamNum", _coerce_int(localized_candidate.get("realExamNum")) or 0)
            current.setdefault("trainNum", _coerce_int(localized_candidate.get("trainNum")) or 0)
            sources_by_id[source_id] = current

        for payload in self._load_teacher_api_payloads("/api/exam/getBankSourceListWithoutPageForNew"):
            content = payload.get("content") or {}
            source_list = content.get("sourceList") or {}
            if isinstance(source_list, dict):
                iterable_groups = source_list.values()
            elif isinstance(source_list, list):
                iterable_groups = [source_list]
            else:
                iterable_groups = []

            for group in iterable_groups:
                if not isinstance(group, list):
                    continue
                for candidate in group:
                    merge_source(candidate)

        for payload in self._load_teacher_api_payloads("/api/exam/getTestQuestionBankSourceListWithoutPage"):
            content = payload.get("content") or {}
            entries = content.get("testQuestionBankSourceList") or []
            if not isinstance(entries, list):
                continue
            for candidate in entries:
                merge_source(candidate)

        return sorted(
            sources_by_id.values(),
            key=lambda source: (
                _coerce_int(source.get("sort_num")) or 0,
                _coerce_int(source.get("id")) or 0,
            ),
        )

    def find_competition_source(self, source_id: int | str | None) -> dict[str, Any] | None:
        if source_id is None:
            return None
        normalized = str(source_id).strip()
        if not normalized.isdigit():
            return None
        target_id = int(normalized)
        for source in self.list_competition_sources():
            if _coerce_int(source.get("id")) == target_id:
                return source
        return None

    def list_user_campuses(self) -> list[dict[str, Any]]:
        campuses_by_id: dict[str, dict[str, Any]] = {}
        for payload in self._load_teacher_api_payloads("/api/get/user/campus/list"):
            content = payload.get("content") or {}
            entries = content.get("userDeptList") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                campus_id = str(entry.get("dept_id") or entry.get("id") or "").strip()
                if not campus_id or campus_id in campuses_by_id:
                    continue
                campuses_by_id[campus_id] = entry

        return sorted(campuses_by_id.values(), key=lambda campus: int(campus.get("dept_id") or campus.get("id") or 0))

    @staticmethod
    def _local_campus_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "address": str(row["address"] or ""),
            "phone": str(row["phone"] or ""),
            "state": int(row["state"]),
        }

    def list_local_campuses(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, address, phone, state FROM local_campuses ORDER BY id"
            ).fetchall()
        return [self._local_campus_row_to_dict(row) for row in rows]

    def get_local_campus(self, campus_id: int | str | None) -> dict[str, Any] | None:
        normalized_id = _coerce_int(campus_id)
        if normalized_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, address, phone, state FROM local_campuses WHERE id = ?",
                (normalized_id,),
            ).fetchone()
        return self._local_campus_row_to_dict(row) if row is not None else None

    def upsert_local_campus(self, payload: dict[str, Any]) -> dict[str, Any]:
        campus_id = _coerce_int(payload.get("id") or payload.get("campusId") or payload.get("eduCampusId"))
        current = self.get_local_campus(campus_id)
        if campus_id is None:
            with self._connect() as connection:
                row = connection.execute("SELECT COALESCE(MAX(id), 1000) AS max_id FROM local_campuses").fetchone()
            campus_id = int(row["max_id"] or 1000) + 1
        name = str(
            payload.get("name")
            or payload.get("campusName")
            or payload.get("dept_name")
            or (current or {}).get("name")
            or ""
        ).strip()
        if not name:
            raise ValueError("Campus name is required")
        address = str(payload.get("address", (current or {}).get("address") or "") or "").strip()
        phone = str(payload.get("phone", (current or {}).get("phone") or "") or "").strip()
        state_value = payload.get("state")
        state = int(bool((current or {}).get("state", 1))) if state_value is None else int(bool(_coerce_int(state_value)))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_campuses (id, name, address, phone, state, created_time, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    address = excluded.address,
                    phone = excluded.phone,
                    state = excluded.state,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (campus_id, name, address, phone, state),
            )
        return self.get_local_campus(campus_id) or {
            "id": campus_id,
            "name": name,
            "address": address,
            "phone": phone,
            "state": state,
        }

    def list_campuses(self) -> list[dict[str, Any]]:
        campuses: dict[int, dict[str, Any]] = {}
        for captured in self.list_user_campuses():
            campus_id = _coerce_int(
                captured.get("id") or captured.get("dept_id") or captured.get("eduCampusId")
            )
            if campus_id is None:
                continue
            row = self._localize_persisted_value(captured)
            row.setdefault("id", campus_id)
            row.setdefault("name", row.get("campusName") or row.get("dept_name") or f"Campus {campus_id}")
            row.setdefault("address", "")
            row.setdefault("phone", "")
            row.setdefault("state", 1)
            campuses[campus_id] = row
        for local in self.list_local_campuses():
            base = campuses.get(local["id"], {})
            base.update(local)
            base["campusName"] = local["name"]
            base["dept_name"] = local["name"]
            campuses[local["id"]] = base
        return [campuses[campus_id] for campus_id in sorted(campuses)]

    def list_teaching_plans(self) -> list[dict[str, Any]]:
        return self._list_merged_teaching_plans()

    def list_classes(self) -> list[dict[str, Any]]:
        return self._list_merged_classes()

    def list_campus_user_students(self, campus_id: int | str | None = None) -> list[dict[str, Any]]:
        target_campus = str(campus_id).strip() if campus_id is not None else ""
        students_by_id: dict[str, dict[str, Any]] = {}
        for payload in self._load_teacher_api_payloads("/api/get/campus/user/list"):
            content = payload.get("content") or {}
            entries = content.get("campusUserList") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                student_id = str(entry.get("id") or "").strip()
                if not student_id:
                    continue
                campus_name = str(entry.get("campusName") or "").strip()
                if target_campus and campus_name:
                    # when only campus name is present, keep the row because payloads omit numeric campus ids
                    pass
                if student_id in students_by_id:
                    continue
                students_by_id[student_id] = self._localize_persisted_value(entry)
        return sorted(
            students_by_id.values(),
            key=lambda row: (
                str(row.get("created_time") or ""),
                _coerce_int(row.get("id")) or 0,
            ),
            reverse=True,
        )

    def get_class_student_payload(self, class_id: int | str | None) -> dict[str, Any] | None:
        normalized_class_id = str(class_id).strip()
        if not normalized_class_id:
            return None
        cache_key = normalized_class_id
        if cache_key in self._class_payload_cache:
            return self._class_payload_cache[cache_key]
        local_content = self._build_local_class_student_payload(normalized_class_id)
        if local_content is not None:
            self._class_payload_cache[cache_key] = local_content
            return local_content
        captured = self._get_captured_class_student_payload(normalized_class_id)
        self._class_payload_cache[cache_key] = captured
        return captured

    def get_teaching_plan_by_class_payload(self, class_id: int | str | None) -> dict[str, Any] | None:
        normalized_class_id = str(class_id).strip()
        if not normalized_class_id:
            return None
        local_content = self._build_local_teaching_plan_by_class_payload(normalized_class_id)
        if local_content is not None:
            return local_content
        return self._get_captured_teaching_plan_by_class_payload(normalized_class_id)

    def list_tch_work_self_remarks(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, remark
                FROM tch_work_self_remarks
                ORDER BY id DESC
                """
            ).fetchall()
        return [{"id": row["id"], "remark": row["remark"]} for row in rows]

    def save_tch_work_self_remark(self, remark: str, remark_id: int | str | None = None) -> dict[str, Any]:
        normalized_remark = str(remark).strip()
        if not normalized_remark:
            raise ValueError("remark must not be empty")

        with self._connect() as connection:
            target_id: int | None = None
            if remark_id is not None and str(remark_id).strip().isdigit():
                target_id = int(str(remark_id).strip())
            if target_id is not None:
                existing = connection.execute(
                    "SELECT id FROM tch_work_self_remarks WHERE id = ?",
                    (target_id,),
                ).fetchone()
                if existing is not None:
                    connection.execute(
                        "UPDATE tch_work_self_remarks SET remark = ? WHERE id = ?",
                        (normalized_remark, target_id),
                    )
                    row_id = target_id
                else:
                    cursor = connection.execute(
                        "INSERT INTO tch_work_self_remarks (remark) VALUES (?)",
                        (normalized_remark,),
                    )
                    row_id = int(cursor.lastrowid)
            else:
                cursor = connection.execute(
                    "INSERT INTO tch_work_self_remarks (remark) VALUES (?)",
                    (normalized_remark,),
                )
                row_id = int(cursor.lastrowid)

            row = connection.execute(
                "SELECT id, remark FROM tch_work_self_remarks WHERE id = ?",
                (row_id,),
            ).fetchone()
        return {"id": row["id"], "remark": row["remark"]} if row is not None else {"id": row_id, "remark": normalized_remark}

    def delete_tch_work_self_remark(self, remark_id: int | str) -> bool:
        raw = str(remark_id).strip()
        if not raw.isdigit():
            return False
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM tch_work_self_remarks WHERE id = ?",
                (int(raw),),
            )
            return cursor.rowcount > 0

    def create_local_student(self, payload: dict[str, Any]) -> dict[str, Any]:
        campus_id_raw = payload.get("eduCampusId")
        campus_id = int(campus_id_raw) if str(campus_id_raw).strip().isdigit() else 0
        localized_headimg_url = str(self._localize_persisted_value(payload.get("headimgUrl") or "") or "").strip()
        record = {
            "campus_id": campus_id,
            "name": str(payload.get("name") or "").strip(),
            "realname": str(payload.get("realName") or payload.get("realname") or "").strip(),
            "sex": str(payload.get("sex") or "").strip(),
            "normal_state": str(payload.get("normalState") or "").strip(),
            "phone_num": str(payload.get("parentAPhoneNum") or payload.get("phoneNum") or "").strip(),
            "school_name": str(payload.get("schoolName") or "").strip(),
            "grade": str(payload.get("grade") or "").strip(),
            "leader": str(payload.get("leader") or "").strip(),
            "remark": str(payload.get("remark") or "").strip(),
            "study_date": str(payload.get("studyDate") or "").strip(),
            "headimg_url": localized_headimg_url,
        }

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_students (
                    campus_id, name, realname, sex, normal_state, phone_num,
                    school_name, grade, leader, remark, study_date, headimg_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["campus_id"],
                    record["name"],
                    record["realname"],
                    record["sex"],
                    record["normal_state"],
                    record["phone_num"],
                    record["school_name"],
                    record["grade"],
                    record["leader"],
                    record["remark"],
                    record["study_date"],
                    record["headimg_url"],
                ),
            )
            row_id = int(cursor.lastrowid)
            row = connection.execute(
                """
                SELECT id, campus_id, name, realname, sex, normal_state, phone_num,
                       school_name, grade, leader, remark, study_date, headimg_url, created_time
                FROM local_students
                WHERE id = ?
                """,
                (row_id,),
            ).fetchone()

        return self._local_student_row_to_dict(row) if row is not None else {
            "id": row_id,
            **record,
            "created_time": "",
        }

    def list_local_students(self, campus_id: int | str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT id, campus_id, name, realname, sex, normal_state, phone_num,
                   school_name, grade, leader, remark, study_date, headimg_url, created_time
            FROM local_students
        """
        params: tuple[Any, ...] = ()
        if campus_id is not None and str(campus_id).strip().isdigit():
            query += " WHERE campus_id = ?"
            params = (int(str(campus_id).strip()),)
        query += " ORDER BY id DESC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._local_student_row_to_dict(row) for row in rows]

    def find_cached_student_row(self, stu_id: int | str | None) -> dict[str, Any] | None:
        normalized_stu_id = self._normalize_student_id(stu_id)
        if normalized_stu_id is None:
            return None
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT body_path
                FROM api_responses
                WHERE profile_name = 'teacher'
                  AND (
                    url LIKE '%/java-api/school/stu/selectStudy%'
                    OR url LIKE '%/java-api/school/getStudentList%'
                    OR url LIKE '%/api/get/campus/user/list%'
                    OR url LIKE '%/java-api/school/stu/queryClsStuMsg%'
                  )
                ORDER BY rowid DESC
                """,
            ).fetchall()

        for row in rows:
            body_path = self.root / row["body_path"]
            if not body_path.exists():
                continue
            try:
                payload = json.loads(body_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            match = self._find_student_row_in_payload(payload, normalized_stu_id)
            if match is not None:
                return match
        return None

    @staticmethod
    def _local_student_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "campus_id": row["campus_id"],
            "name": row["name"],
            "realname": row["realname"],
            "sex": row["sex"],
            "normal_state": row["normal_state"],
            "phone_num": row["phone_num"],
            "school_name": row["school_name"],
            "grade": row["grade"],
            "leader": row["leader"],
            "remark": row["remark"],
            "study_date": row["study_date"],
            "headimg_url": row["headimg_url"],
            "created_time": row["created_time"],
        }

    @staticmethod
    def _find_student_row_in_payload(payload: Any, stu_id: int) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        content = payload.get("content")
        if isinstance(content, dict):
            candidates = (
                content.get("content"),
                content.get("studentList"),
                content.get("campusUserList"),
            )
            for candidate in candidates:
                if isinstance(candidate, list):
                    for row in candidate:
                        if isinstance(row, dict) and MirrorStore._payload_student_row_id(row) == stu_id:
                            return json.loads(json.dumps(row, ensure_ascii=False))
            if MirrorStore._payload_student_row_id(content) == stu_id:
                return json.loads(json.dumps(content, ensure_ascii=False))
        return None

    @staticmethod
    def _payload_student_row_id(row: dict[str, Any]) -> int | None:
        for key in ("stuId", "id", "studentId", "userId"):
            value = row.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().isdigit():
                return int(value.strip())
        return None

    def get_student_overlay(self, stu_id: int | str | None) -> dict[str, Any] | None:
        normalized_stu_id = self._normalize_student_id(stu_id)
        if normalized_stu_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT stu_id, deleted, quit, normal_state, end_date, zone_auth, test_auth, oj_auth,
                       oj_analysis_auth, oj_testcase_auth, stu_note_auth, p_auth,
                       wechat_bound, parent_wechat, wcm_flag, open_id, authorizer_openid,
                       last_password_reset_at, updated_at
                FROM student_overlays
                WHERE stu_id = ?
                """,
                (normalized_stu_id,),
            ).fetchone()
        return self._student_overlay_row_to_dict(row) if row is not None else None

    def list_historical_student_ids(self) -> list[int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT stu_id
                FROM student_overlays
                WHERE quit = 1
                  AND COALESCE(deleted, 0) = 0
                ORDER BY stu_id DESC
                """
            ).fetchall()
        return [int(row["stu_id"]) for row in rows]

    def upsert_student_overlay(self, stu_id: int | str | None, updates: dict[str, Any]) -> dict[str, Any] | None:
        normalized_stu_id = self._normalize_student_id(stu_id)
        if normalized_stu_id is None:
            return None
        normalized_updates = self._normalize_student_overlay_updates(updates)
        current = self.get_student_overlay(normalized_stu_id) or self._student_overlay_defaults(normalized_stu_id)
        merged = {**current, **normalized_updates}

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO student_overlays (
                    stu_id, deleted, quit, normal_state, end_date, zone_auth, test_auth, oj_auth,
                    oj_analysis_auth, oj_testcase_auth, stu_note_auth, p_auth,
                    wechat_bound, parent_wechat, wcm_flag, open_id, authorizer_openid,
                    last_password_reset_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normalized_stu_id,
                    int(bool(merged.get("deleted"))),
                    int(bool(merged.get("quit"))),
                    merged.get("normal_state"),
                    merged.get("end_date"),
                    merged.get("zone_auth"),
                    merged.get("test_auth"),
                    merged.get("oj_auth"),
                    merged.get("oj_analysis_auth"),
                    merged.get("oj_testcase_auth"),
                    merged.get("stu_note_auth"),
                    merged.get("p_auth"),
                    merged.get("wechat_bound"),
                    merged.get("parent_wechat"),
                    merged.get("wcm_flag"),
                    merged.get("open_id"),
                    merged.get("authorizer_openid"),
                    merged.get("last_password_reset_at"),
                ),
            )
        return self.get_student_overlay(normalized_stu_id)

    def bulk_upsert_student_overlay(self, stu_ids: list[Any], updates: dict[str, Any]) -> list[int]:
        changed_ids: list[int] = []
        for stu_id in stu_ids:
            normalized_stu_id = self._normalize_student_id(stu_id)
            if normalized_stu_id is None:
                continue
            if self.upsert_student_overlay(normalized_stu_id, updates) is not None:
                changed_ids.append(normalized_stu_id)
        return changed_ids

    def update_student_study_date(self, stu_id: int | str | None, end_date: str | None) -> bool:
        normalized_stu_id = self._normalize_student_id(stu_id)
        if normalized_stu_id is None:
            return False
        normalized_end_date = str(end_date or "").strip()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE local_students SET study_date = ? WHERE id = ?",
                (normalized_end_date, normalized_stu_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _normalize_student_id(value: int | str | None) -> int | None:
        if isinstance(value, int):
            return value
        if value is None:
            return None
        text = str(value).strip()
        if not text or not text.isdigit():
            return None
        return int(text)

    @staticmethod
    def _student_overlay_defaults(stu_id: int) -> dict[str, Any]:
        return {
            "stu_id": stu_id,
            "deleted": 0,
            "quit": 0,
            "normal_state": None,
            "end_date": None,
            "zone_auth": None,
            "test_auth": None,
            "oj_auth": None,
            "oj_analysis_auth": None,
            "oj_testcase_auth": None,
            "stu_note_auth": None,
            "p_auth": None,
            "wechat_bound": None,
            "parent_wechat": None,
            "wcm_flag": None,
            "open_id": None,
            "authorizer_openid": None,
            "last_password_reset_at": None,
            "updated_at": None,
        }

    @staticmethod
    def _normalize_student_overlay_updates(updates: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for field in STUDENT_OVERLAY_FIELDS:
            if field not in updates:
                continue
            value = updates[field]
            if field in {
                "deleted",
                "quit",
                "zone_auth",
                "test_auth",
                "oj_auth",
                "oj_analysis_auth",
                "oj_testcase_auth",
                "stu_note_auth",
                "p_auth",
                "wechat_bound",
            }:
                normalized[field] = MirrorStore._normalize_optional_flag(value)
            elif field in {"normal_state", "end_date"}:
                text = str(value).strip() if value not in (None, "") else ""
                normalized[field] = text or None
            else:
                text = str(value).strip() if value not in (None, "") else ""
                normalized[field] = text or None
        return normalized

    @staticmethod
    def _normalize_optional_flag(value: Any) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return 1 if value else 0
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return 1
        if text in {"0", "false", "no", "n", "off"}:
            return 0
        if text.isdigit():
            return 1 if int(text) else 0
        return None

    @staticmethod
    def _student_overlay_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "stu_id": row["stu_id"],
            "deleted": row["deleted"],
            "quit": row["quit"],
            "normal_state": row["normal_state"],
            "end_date": row["end_date"],
            "zone_auth": row["zone_auth"],
            "test_auth": row["test_auth"],
            "oj_auth": row["oj_auth"],
            "oj_analysis_auth": row["oj_analysis_auth"],
            "oj_testcase_auth": row["oj_testcase_auth"],
            "stu_note_auth": row["stu_note_auth"],
            "p_auth": row["p_auth"],
            "wechat_bound": row["wechat_bound"],
            "parent_wechat": row["parent_wechat"],
            "wcm_flag": row["wcm_flag"],
            "open_id": row["open_id"],
            "authorizer_openid": row["authorizer_openid"],
            "last_password_reset_at": row["last_password_reset_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _teaching_plan_overlay_defaults(teaching_plan_id: int) -> dict[str, Any]:
        return {
            "teaching_plan_id": teaching_plan_id,
            "zone_auth": None,
            "oj_analysis_auth": None,
            "test_case_auth": None,
            "editor_showhint_auth": None,
            "class_work_url": None,
            "example_work_url": None,
            "homework_work_url": None,
            "source_tch_plan_id": None,
            "updated_at": None,
        }

    @staticmethod
    def _normalize_teaching_plan_id(value: int | str | None) -> int | None:
        if isinstance(value, int):
            return value
        if value is None:
            return None
        text = str(value).strip()
        if not text or not text.isdigit():
            return None
        return int(text)

    @staticmethod
    def _normalize_teaching_plan_overlay_updates(updates: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for field in TEACHING_PLAN_OVERLAY_FIELDS:
            if field not in updates:
                continue
            value = updates[field]
            if field in {"zone_auth", "oj_analysis_auth", "test_case_auth", "editor_showhint_auth"}:
                normalized[field] = MirrorStore._normalize_optional_flag(value)
            elif field == "source_tch_plan_id":
                normalized[field] = MirrorStore._normalize_teaching_plan_id(value)
            else:
                text = str(value).strip() if value not in (None, "") else ""
                normalized[field] = text or None
        return normalized

    @staticmethod
    def _teaching_plan_overlay_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "teaching_plan_id": row["teaching_plan_id"],
            "zone_auth": row["zone_auth"],
            "oj_analysis_auth": row["oj_analysis_auth"],
            "test_case_auth": row["test_case_auth"],
            "editor_showhint_auth": row["editor_showhint_auth"],
            "class_work_url": row["class_work_url"],
            "example_work_url": row["example_work_url"],
            "homework_work_url": row["homework_work_url"],
            "source_tch_plan_id": row["source_tch_plan_id"],
            "updated_at": row["updated_at"],
        }

    def get_teaching_plan_overlay(self, teaching_plan_id: int | str | None) -> dict[str, Any] | None:
        normalized_teaching_plan_id = self._normalize_teaching_plan_id(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT teaching_plan_id, zone_auth, oj_analysis_auth, test_case_auth,
                       editor_showhint_auth, class_work_url, example_work_url,
                       homework_work_url, source_tch_plan_id, updated_at
                FROM teaching_plan_overlays
                WHERE teaching_plan_id = ?
                """,
                (normalized_teaching_plan_id,),
            ).fetchone()
        return self._teaching_plan_overlay_row_to_dict(row) if row is not None else None

    def upsert_teaching_plan_overlay(self, teaching_plan_id: int | str | None, updates: dict[str, Any]) -> dict[str, Any] | None:
        normalized_teaching_plan_id = self._normalize_teaching_plan_id(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return None
        normalized_updates = self._normalize_teaching_plan_overlay_updates(updates)
        current = self.get_teaching_plan_overlay(normalized_teaching_plan_id) or self._teaching_plan_overlay_defaults(normalized_teaching_plan_id)
        merged = {**current, **normalized_updates}

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO teaching_plan_overlays (
                    teaching_plan_id, zone_auth, oj_analysis_auth, test_case_auth,
                    editor_showhint_auth, class_work_url, example_work_url,
                    homework_work_url, source_tch_plan_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normalized_teaching_plan_id,
                    merged.get("zone_auth"),
                    merged.get("oj_analysis_auth"),
                    merged.get("test_case_auth"),
                    merged.get("editor_showhint_auth"),
                    merged.get("class_work_url"),
                    merged.get("example_work_url"),
                    merged.get("homework_work_url"),
                    merged.get("source_tch_plan_id"),
                ),
            )
        return self.get_teaching_plan_overlay(normalized_teaching_plan_id)

    def bulk_upsert_teaching_plan_overlay(self, teaching_plan_ids: list[Any], updates: dict[str, Any]) -> list[int]:
        changed_ids: list[int] = []
        for teaching_plan_id in teaching_plan_ids:
            normalized_teaching_plan_id = self._normalize_teaching_plan_id(teaching_plan_id)
            if normalized_teaching_plan_id is None:
                continue
            if self.upsert_teaching_plan_overlay(normalized_teaching_plan_id, updates) is not None:
                changed_ids.append(normalized_teaching_plan_id)
        return changed_ids

    def delete_teaching_plan_overlay(self, teaching_plan_id: int | str | None) -> bool:
        normalized_teaching_plan_id = self._normalize_teaching_plan_id(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return False
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM teaching_plan_overlays WHERE teaching_plan_id = ?",
                (normalized_teaching_plan_id,),
            )
            return cursor.rowcount > 0

    def get_local_student_exam_run(
        self,
        exam_id: int | str | None,
        *,
        stu_id: int | str | None = 0,
    ) -> dict[str, Any] | None:
        normalized_exam_id = self._normalize_student_exam_id(exam_id)
        normalized_stu_id = self._normalize_student_exam_id(stu_id, default=0)
        if normalized_exam_id is None or normalized_stu_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT exam_id, stu_id, paper_id, title, started_at, submitted_at, updated_at
                FROM local_student_exam_runs
                WHERE exam_id = ? AND stu_id = ?
                """,
                (normalized_exam_id, normalized_stu_id),
            ).fetchone()
        return self._local_student_exam_run_row_to_dict(row) if row is not None else None

    def upsert_local_student_exam_run(
        self,
        exam_id: int | str | None,
        updates: dict[str, Any],
        *,
        stu_id: int | str | None = 0,
    ) -> dict[str, Any] | None:
        normalized_exam_id = self._normalize_student_exam_id(exam_id)
        normalized_stu_id = self._normalize_student_exam_id(stu_id, default=0)
        if normalized_exam_id is None or normalized_stu_id is None:
            return None
        current = self.get_local_student_exam_run(normalized_exam_id, stu_id=normalized_stu_id) or {
            "exam_id": normalized_exam_id,
            "stu_id": normalized_stu_id,
            "paper_id": None,
            "title": None,
            "started_at": None,
            "submitted_at": None,
            "updated_at": "",
        }
        merged = {
            **current,
            "paper_id": self._normalize_optional_int(updates.get("paper_id"), current.get("paper_id")),
            "title": self._normalize_optional_text(updates.get("title"), current.get("title")),
            "started_at": self._normalize_optional_text(updates.get("started_at"), current.get("started_at")),
            "submitted_at": self._normalize_optional_text(updates.get("submitted_at"), current.get("submitted_at")),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_student_exam_runs (
                    exam_id, stu_id, paper_id, title, started_at, submitted_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normalized_exam_id,
                    normalized_stu_id,
                    merged.get("paper_id"),
                    merged.get("title"),
                    merged.get("started_at"),
                    merged.get("submitted_at"),
                ),
            )
        return self.get_local_student_exam_run(normalized_exam_id, stu_id=normalized_stu_id)

    def get_local_student_exam_answer(
        self,
        exam_id: int | str | None,
        question_id: int | str | None,
        *,
        stu_id: int | str | None = 0,
    ) -> dict[str, Any] | None:
        normalized_exam_id = self._normalize_student_exam_id(exam_id)
        normalized_question_id = self._normalize_student_exam_id(question_id)
        normalized_stu_id = self._normalize_student_exam_id(stu_id, default=0)
        if normalized_exam_id is None or normalized_question_id is None or normalized_stu_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT exam_id, question_id, stu_id, stu_exam_question_id, answer, question_score,
                       score, submitted_at, updated_at
                FROM local_student_exam_answers
                WHERE exam_id = ? AND question_id = ? AND stu_id = ?
                """,
                (normalized_exam_id, normalized_question_id, normalized_stu_id),
            ).fetchone()
        return self._local_student_exam_answer_row_to_dict(row) if row is not None else None

    def list_local_student_exam_answers(
        self,
        exam_id: int | str | None,
        *,
        stu_id: int | str | None = 0,
    ) -> list[dict[str, Any]]:
        normalized_exam_id = self._normalize_student_exam_id(exam_id)
        normalized_stu_id = self._normalize_student_exam_id(stu_id, default=0)
        if normalized_exam_id is None or normalized_stu_id is None:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT exam_id, question_id, stu_id, stu_exam_question_id, answer, question_score,
                       score, submitted_at, updated_at
                FROM local_student_exam_answers
                WHERE exam_id = ? AND stu_id = ?
                ORDER BY question_id
                """,
                (normalized_exam_id, normalized_stu_id),
            ).fetchall()
        return [self._local_student_exam_answer_row_to_dict(row) for row in rows]

    def upsert_local_student_exam_answer(
        self,
        exam_id: int | str | None,
        question_id: int | str | None,
        updates: dict[str, Any],
        *,
        stu_id: int | str | None = 0,
    ) -> dict[str, Any] | None:
        normalized_exam_id = self._normalize_student_exam_id(exam_id)
        normalized_question_id = self._normalize_student_exam_id(question_id)
        normalized_stu_id = self._normalize_student_exam_id(stu_id, default=0)
        if normalized_exam_id is None or normalized_question_id is None or normalized_stu_id is None:
            return None
        current = self.get_local_student_exam_answer(
            normalized_exam_id,
            normalized_question_id,
            stu_id=normalized_stu_id,
        ) or {
            "exam_id": normalized_exam_id,
            "question_id": normalized_question_id,
            "stu_id": normalized_stu_id,
            "stu_exam_question_id": normalized_exam_id * 100000 + normalized_question_id,
            "answer": None,
            "question_score": None,
            "score": None,
            "submitted_at": None,
            "updated_at": "",
        }
        merged = {
            **current,
            "stu_exam_question_id": self._normalize_student_exam_id(
                updates.get("stu_exam_question_id"),
                default=current.get("stu_exam_question_id"),
            ),
            "answer": self._normalize_optional_text(updates.get("answer"), current.get("answer")),
            "question_score": self._normalize_optional_float(updates.get("question_score"), current.get("question_score")),
            "score": self._normalize_optional_float(updates.get("score"), current.get("score")),
            "submitted_at": self._normalize_optional_text(updates.get("submitted_at"), current.get("submitted_at")),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_student_exam_answers (
                    exam_id, question_id, stu_id, stu_exam_question_id, answer, question_score,
                    score, submitted_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normalized_exam_id,
                    normalized_question_id,
                    normalized_stu_id,
                    merged.get("stu_exam_question_id") or (normalized_exam_id * 100000 + normalized_question_id),
                    merged.get("answer"),
                    merged.get("question_score"),
                    merged.get("score"),
                    merged.get("submitted_at"),
                ),
            )
        return self.get_local_student_exam_answer(
            normalized_exam_id,
            normalized_question_id,
            stu_id=normalized_stu_id,
        )

    @staticmethod
    def _local_student_exam_run_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "exam_id": row["exam_id"],
            "stu_id": row["stu_id"],
            "paper_id": row["paper_id"],
            "title": row["title"],
            "started_at": row["started_at"],
            "submitted_at": row["submitted_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _local_student_exam_answer_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "exam_id": row["exam_id"],
            "question_id": row["question_id"],
            "stu_id": row["stu_id"],
            "stu_exam_question_id": row["stu_exam_question_id"],
            "answer": row["answer"],
            "question_score": row["question_score"],
            "score": row["score"],
            "submitted_at": row["submitted_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _normalize_student_exam_id(value: int | str | None, *, default: int | None = None) -> int | None:
        normalized = _coerce_int(value)
        if normalized is not None:
            return normalized
        return default

    @staticmethod
    def _json_clone(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False))

    @staticmethod
    def _decode_json_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return list(value)
        if value in (None, ""):
            return []
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
                if isinstance(parsed, list):
                    return parsed
            return [item.strip() for item in text.split(",") if item.strip()]
        return [value]

    @staticmethod
    def _normalize_int_list(*values: Any) -> list[int]:
        normalized: list[int] = []
        for value in values:
            for item in MirrorStore._decode_json_list(value):
                normalized_item = _coerce_int(item)
                if normalized_item is None or normalized_item in normalized:
                    continue
                normalized.append(normalized_item)
        return normalized

    @staticmethod
    def _normalize_optional_text(*values: Any) -> str | None:
        for value in values:
            if value in (None, ""):
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _normalize_optional_int(*values: Any) -> int | None:
        for value in values:
            normalized = _coerce_int(value)
            if normalized is not None:
                return normalized
        return None

    @staticmethod
    def _normalize_optional_float(*values: Any) -> float | None:
        for value in values:
            if value in (None, ""):
                continue
            if isinstance(value, (int, float)):
                return float(value)
            text = str(value).strip()
            if not text:
                continue
            try:
                return float(text)
            except ValueError:
                continue
        return None

    def _campus_name_map(self) -> dict[int, str]:
        campus_name_map: dict[int, str] = {}
        for campus in self.list_user_campuses():
            if not isinstance(campus, dict):
                continue
            campus_id = _coerce_int(campus.get("dept_id") or campus.get("id"))
            campus_name = str(campus.get("campusName") or campus.get("name") or "").strip()
            if campus_id is None or not campus_name:
                continue
            campus_name_map[campus_id] = campus_name
        return campus_name_map

    def _subject_info_map(self) -> dict[int, dict[str, Any]]:
        subject_map: dict[int, dict[str, Any]] = {}
        for subject in self.list_campus_subjects():
            if not isinstance(subject, dict):
                continue
            subject_id = _coerce_int(subject.get("id"))
            if subject_id is None:
                continue
            subject_map[subject_id] = self._localize_persisted_value(subject)
        return subject_map

    def _curriculum_info_map(self) -> dict[int, dict[str, Any]]:
        curriculum_map: dict[int, dict[str, Any]] = {}
        for entry in self.list_campus_curriculum_auths():
            if not isinstance(entry, dict):
                continue
            curriculum_info = entry.get("curriculumInfo") if isinstance(entry.get("curriculumInfo"), dict) else {}
            curriculum_id = _coerce_int(curriculum_info.get("id") or entry.get("curriculum_id") or entry.get("id"))
            if curriculum_id is None:
                continue
            merged = {
                **self._localize_persisted_value(curriculum_info),
                "subject_id": _coerce_int(curriculum_info.get("subject_id") or entry.get("subject_id")),
                "subjectName": entry.get("subjectName") or entry.get("subject_name") or "",
                "subject_name": entry.get("subjectName") or entry.get("subject_name") or "",
            }
            curriculum_map[curriculum_id] = merged
        return curriculum_map

    def _curriculum_material_map(self) -> dict[int, dict[str, Any]]:
        material_map: dict[int, dict[str, Any]] = {}
        for material in self.list_curriculum_materials():
            if not isinstance(material, dict):
                continue
            material_id = _coerce_int(material.get("id"))
            if material_id is None:
                continue
            material_map[material_id] = self._localize_persisted_value(material)
        return material_map

    def _captured_classes_by_id(self) -> dict[int, dict[str, Any]]:
        classes_by_id: dict[int, dict[str, Any]] = {}
        for payload in self._load_teacher_api_payloads("/api/get/classes/list"):
            content = payload.get("content") or {}
            entries = content.get("class_list") or content.get("classList") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                class_id = _coerce_int(entry.get("id"))
                if class_id is None or class_id in classes_by_id:
                    continue
                classes_by_id[class_id] = self._localize_persisted_value(entry)
        return classes_by_id

    def _local_class_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        subject_id_list = self._normalize_int_list(row["subject_id_list_json"])
        curriculum_id_list = self._normalize_int_list(row["curriculum_id_list_json"])
        week_json = self._decode_json_list(row["week_json"])
        normalized_week_json: list[Any] = []
        for item in week_json:
            normalized_week_json.append(_coerce_int(item) if _coerce_int(item) is not None else item)
        return {
            "id": row["id"],
            "name": row["name"],
            "educational_institution_campus_id": row["educational_institution_campus_id"],
            "lecturer_id": row["lecturer_id"],
            "lecturer_name": row["lecturer_name"],
            "assistant_teacher_id": row["assistant_teacher_id"],
            "curriculum_class_type": row["curriculum_class_type"],
            "teaching_type": row["teaching_type"],
            "end_class_state": row["end_class_state"],
            "week_json": normalized_week_json,
            "week_str": row["week_str"],
            "time_str": row["time_str"],
            "subject_id_list": subject_id_list,
            "subjectIdList": self._json_clone(subject_id_list),
            "curriculum_id_list": curriculum_id_list,
            "curriculumIdList": self._json_clone(curriculum_id_list),
            "class_code": row["class_code"],
            "is_cost_lesson_hour": bool(row["is_cost_lesson_hour"]),
            "deleted": bool(row["deleted"]),
            "membership_override": bool(row["membership_override"]),
            "created_time": row["created_time"],
            "updated_at": row["updated_at"],
        }

    def list_local_classes(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, educational_institution_campus_id, lecturer_id, lecturer_name,
                       assistant_teacher_id, curriculum_class_type, teaching_type, end_class_state,
                       week_json, week_str, time_str, subject_id_list_json, curriculum_id_list_json,
                       class_code, is_cost_lesson_hour, deleted, membership_override, created_time, updated_at
                FROM local_classes
                ORDER BY id
                """
            ).fetchall()
        return [self._local_class_row_to_dict(row) for row in rows]

    def get_local_class(self, class_id: int | str | None) -> dict[str, Any] | None:
        normalized_class_id = _coerce_int(class_id)
        if normalized_class_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, educational_institution_campus_id, lecturer_id, lecturer_name,
                       assistant_teacher_id, curriculum_class_type, teaching_type, end_class_state,
                       week_json, week_str, time_str, subject_id_list_json, curriculum_id_list_json,
                       class_code, is_cost_lesson_hour, deleted, membership_override, created_time, updated_at
                FROM local_classes
                WHERE id = ?
                """,
                (normalized_class_id,),
            ).fetchone()
        return self._local_class_row_to_dict(row) if row is not None else None

    def _list_merged_classes(self) -> list[dict[str, Any]]:
        captured_rows = self._captured_classes_by_id()
        local_rows_by_id = {
            _coerce_int(row.get("id")) or 0: row
            for row in self.list_local_classes()
            if isinstance(row, dict) and _coerce_int(row.get("id")) is not None
        }
        campus_name_map = self._campus_name_map()
        subject_info_map = self._subject_info_map()
        curriculum_info_map = self._curriculum_info_map()

        merged_rows: list[dict[str, Any]] = []
        all_class_ids = sorted({*captured_rows.keys(), *local_rows_by_id.keys()})
        for class_id in all_class_ids:
            base = self._json_clone(captured_rows.get(class_id) or {})
            local = local_rows_by_id.get(class_id) or {}
            if local.get("deleted"):
                continue

            subject_id_list = self._normalize_int_list(
                local.get("subject_id_list"),
                local.get("subjectIdList"),
                base.get("subject_id_list"),
                base.get("subjectIdList"),
            )
            curriculum_id_list = self._normalize_int_list(
                local.get("curriculum_id_list"),
                local.get("curriculumIdList"),
                base.get("curriculum_id_list"),
                base.get("curriculumIdList"),
                base.get("curriculumIdArr"),
            )
            week_json = self._decode_json_list(local.get("week_json") if "week_json" in local else base.get("week_json"))

            row = {
                **base,
                "id": class_id,
                "name": self._normalize_optional_text(local.get("name"), base.get("name"), base.get("className")) or f"Class {class_id}",
                "educational_institution_campus_id": self._normalize_optional_int(
                    local.get("educational_institution_campus_id"),
                    base.get("educational_institution_campus_id"),
                )
                or 0,
                "lecturer_id": self._normalize_optional_int(local.get("lecturer_id"), base.get("lecturer_id")),
                "lecturer_name": self._normalize_optional_text(local.get("lecturer_name"), base.get("lecturer_name")),
                "assistant_teacher_id": self._normalize_optional_int(
                    local.get("assistant_teacher_id"),
                    base.get("assistant_teacher_id"),
                ),
                "curriculum_class_type": self._normalize_optional_int(
                    local.get("curriculum_class_type"),
                    base.get("curriculum_class_type"),
                )
                or 1,
                "teaching_type": self._normalize_optional_int(local.get("teaching_type"), base.get("teaching_type")) or 1,
                "end_class_state": self._normalize_optional_int(local.get("end_class_state"), base.get("end_class_state")),
                "week_json": week_json,
                "week_str": self._normalize_optional_text(local.get("week_str"), base.get("week_str")) or "",
                "time_str": self._normalize_optional_text(local.get("time_str"), base.get("time_str")) or "",
                "subject_id_list": subject_id_list,
                "subjectIdList": self._json_clone(subject_id_list),
                "curriculum_id_list": curriculum_id_list,
                "curriculumIdList": self._json_clone(curriculum_id_list),
                "class_code": self._normalize_optional_text(local.get("class_code"), base.get("class_code")) or f"local-class-{class_id}",
                "is_cost_lesson_hour": bool(
                    self._normalize_optional_int(local.get("is_cost_lesson_hour"), base.get("is_cost_lesson_hour")) or 0
                ),
                "membership_override": bool(local.get("membership_override") or False),
                "campusName": base.get("campusName")
                or campus_name_map.get(
                    self._normalize_optional_int(local.get("educational_institution_campus_id"), base.get("educational_institution_campus_id"))
                    or -1
                )
                or "",
            }
            row["subjectInfoList"] = [
                self._json_clone(subject_info_map[subject_id])
                for subject_id in subject_id_list
                if subject_id in subject_info_map
            ]
            row["curriculumInfoList"] = [
                self._json_clone(curriculum_info_map[curriculum_id])
                for curriculum_id in curriculum_id_list
                if curriculum_id in curriculum_info_map
            ]
            merged_rows.append(row)

        merged_rows.sort(
            key=lambda row: (
                -(_coerce_int(row.get("student_total_num") or row.get("stuNum")) or 0),
                str(row.get("name") or ""),
            )
        )
        return merged_rows

    def find_class(self, class_id: int | str | None) -> dict[str, Any] | None:
        normalized_class_id = _coerce_int(class_id)
        if normalized_class_id is None:
            return None
        local_class = self.get_local_class(normalized_class_id)
        if isinstance(local_class, dict) and local_class.get("deleted"):
            return None
        for row in self.list_classes():
            if _coerce_int((row or {}).get("id")) == normalized_class_id:
                return row
        for plan in self.list_teaching_plans():
            if not isinstance(plan, dict):
                continue
            class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
            plan_class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
            if plan_class_id != normalized_class_id:
                continue
            return self._json_clone(class_info) if class_info else {
                "id": normalized_class_id,
                "name": plan.get("className") or f"Class {normalized_class_id}",
                "educational_institution_campus_id": plan.get("educational_institution_campus_id") or 0,
                "lecturer_id": plan.get("lecturer_id"),
                "lecturer_name": plan.get("lecturerName"),
            }
        return None

    def next_class_id(self) -> int:
        max_id = 3000
        with self._connect() as connection:
            row = connection.execute("SELECT MAX(id) AS max_id FROM local_classes").fetchone()
        if row is not None:
            max_id = max(max_id, _coerce_int(row["max_id"]) or max_id)
        for row in self.list_classes():
            if not isinstance(row, dict):
                continue
            max_id = max(max_id, _coerce_int(row.get("id")) or max_id)
        for plan in self.list_teaching_plans():
            if not isinstance(plan, dict):
                continue
            class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
            max_id = max(
                max_id,
                _coerce_int(class_info.get("id") or plan.get("curriculum_class_id")) or max_id,
            )
        return max_id + 1

    def upsert_local_class(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        class_id = _coerce_int(payload.get("id") or payload.get("classId")) or self.next_class_id()
        current = self.get_local_class(class_id) or self.find_class(class_id) or {}
        subject_id_list = self._normalize_int_list(
            payload.get("subject_id_list"),
            payload.get("subjectIdList"),
            payload.get("subjectIds"),
            payload.get("subjectIdArr"),
            payload.get("subject_id"),
            current.get("subject_id_list"),
            current.get("subjectIdList"),
        )
        curriculum_id_list = self._normalize_int_list(
            payload.get("curriculum_id_list"),
            payload.get("curriculumIdList"),
            payload.get("curriculumIds"),
            payload.get("curriculumIdArr"),
            payload.get("curriculum_id"),
            current.get("curriculum_id_list"),
            current.get("curriculumIdList"),
        )
        week_json = self._decode_json_list(payload.get("week_json") if "week_json" in payload else current.get("week_json"))
        name = self._normalize_optional_text(payload.get("name"), payload.get("className"), current.get("name"), current.get("className"))
        normalized = {
            "id": class_id,
            "name": name or f"Class {class_id}",
            "educational_institution_campus_id": self._normalize_optional_int(
                payload.get("educational_institution_campus_id"),
                payload.get("campusId"),
                current.get("educational_institution_campus_id"),
            )
            or 0,
            "lecturer_id": self._normalize_optional_int(payload.get("lecturer_id"), current.get("lecturer_id")),
            "lecturer_name": self._normalize_optional_text(payload.get("lecturer_name"), current.get("lecturer_name")),
            "assistant_teacher_id": self._normalize_optional_int(
                payload.get("assistant_teacher_id"),
                current.get("assistant_teacher_id"),
            ),
            "curriculum_class_type": self._normalize_optional_int(
                payload.get("curriculum_class_type"),
                current.get("curriculum_class_type"),
            )
            or 1,
            "teaching_type": self._normalize_optional_int(payload.get("teaching_type"), current.get("teaching_type")) or 1,
            "end_class_state": self._normalize_optional_int(payload.get("end_class_state"), current.get("end_class_state")) or 0,
            "week_json": json.dumps(week_json, ensure_ascii=False),
            "week_str": self._normalize_optional_text(payload.get("week_str"), current.get("week_str")) or "",
            "time_str": self._normalize_optional_text(payload.get("time_str"), current.get("time_str")) or "",
            "subject_id_list_json": json.dumps(subject_id_list, ensure_ascii=False),
            "curriculum_id_list_json": json.dumps(curriculum_id_list, ensure_ascii=False),
            "class_code": self._normalize_optional_text(payload.get("class_code"), current.get("class_code")) or f"local-class-{class_id}",
            "is_cost_lesson_hour": int(bool(self._normalize_optional_int(payload.get("is_cost_lesson_hour"), current.get("is_cost_lesson_hour")) or 0)),
            "deleted": int(bool(self._normalize_optional_int(payload.get("deleted"), current.get("deleted")) or 0)),
            "membership_override": int(
                bool(self._normalize_optional_int(payload.get("membership_override"), current.get("membership_override")) or 0)
            ),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_classes (
                    id, name, educational_institution_campus_id, lecturer_id, lecturer_name,
                    assistant_teacher_id, curriculum_class_type, teaching_type, end_class_state,
                    week_json, week_str, time_str, subject_id_list_json, curriculum_id_list_json,
                    class_code, is_cost_lesson_hour, deleted, membership_override, created_time, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_time FROM local_classes WHERE id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    normalized["id"],
                    normalized["name"],
                    normalized["educational_institution_campus_id"],
                    normalized["lecturer_id"],
                    normalized["lecturer_name"],
                    normalized["assistant_teacher_id"],
                    normalized["curriculum_class_type"],
                    normalized["teaching_type"],
                    normalized["end_class_state"],
                    normalized["week_json"],
                    normalized["week_str"],
                    normalized["time_str"],
                    normalized["subject_id_list_json"],
                    normalized["curriculum_id_list_json"],
                    normalized["class_code"],
                    normalized["is_cost_lesson_hour"],
                    normalized["deleted"],
                    normalized["membership_override"],
                    normalized["id"],
                ),
            )
        return self.get_local_class(class_id)

    def set_class_membership_override(self, class_id: int | str | None, membership_override: bool = True) -> dict[str, Any] | None:
        normalized_class_id = _coerce_int(class_id)
        if normalized_class_id is None:
            return None
        return self.upsert_local_class({"id": normalized_class_id, "membership_override": int(bool(membership_override))})

    def is_class_membership_overridden(self, class_id: int | str | None) -> bool:
        local_class = self.get_local_class(class_id)
        return bool((local_class or {}).get("membership_override"))

    def _local_class_student_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "class_id": row["class_id"],
            "student_user_id": row["student_user_id"],
            "xm_goods_id": row["xm_goods_id"],
            "receipt_goods_id": row["receipt_goods_id"],
            "in_class_date": row["in_class_date"],
            "out_class_date": row["out_class_date"],
            "out_class_reason": row["out_class_reason"],
            "created_time": row["created_time"],
            "updated_at": row["updated_at"],
        }

    def list_local_class_students(self, class_id: int | str | None) -> list[dict[str, Any]]:
        normalized_class_id = _coerce_int(class_id)
        if normalized_class_id is None:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT class_id, student_user_id, xm_goods_id, receipt_goods_id, in_class_date,
                       out_class_date, out_class_reason, created_time, updated_at
                FROM local_class_students
                WHERE class_id = ?
                ORDER BY created_time, student_user_id
                """,
                (normalized_class_id,),
            ).fetchall()
        return [self._local_class_student_row_to_dict(row) for row in rows]

    def upsert_local_class_student_relation(
        self,
        *,
        class_id: int | str | None,
        student_user_id: int | str | None,
        xm_goods_id: Any = None,
        receipt_goods_id: Any = None,
        in_class_date: str | None = None,
        out_class_date: str | None = None,
        out_class_reason: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_class_id = _coerce_int(class_id)
        normalized_student_id = _coerce_int(student_user_id)
        if normalized_class_id is None or normalized_student_id is None:
            return None
        current_rows = {row["student_user_id"]: row for row in self.list_local_class_students(normalized_class_id)}
        current = current_rows.get(normalized_student_id, {})
        normalized = {
            "class_id": normalized_class_id,
            "student_user_id": normalized_student_id,
            "xm_goods_id": _coerce_int(xm_goods_id if xm_goods_id not in (None, "") else current.get("xm_goods_id")),
            "receipt_goods_id": _coerce_int(
                receipt_goods_id if receipt_goods_id not in (None, "") else current.get("receipt_goods_id")
            ),
            "in_class_date": self._normalize_optional_text(in_class_date, current.get("in_class_date")) or "",
            "out_class_date": self._normalize_optional_text(out_class_date, current.get("out_class_date")),
            "out_class_reason": self._normalize_optional_text(out_class_reason, current.get("out_class_reason")),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_class_students (
                    class_id, student_user_id, xm_goods_id, receipt_goods_id, in_class_date,
                    out_class_date, out_class_reason, created_time, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(
                        (SELECT created_time FROM local_class_students WHERE class_id = ? AND student_user_id = ?),
                        CURRENT_TIMESTAMP
                    ),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    normalized["class_id"],
                    normalized["student_user_id"],
                    normalized["xm_goods_id"],
                    normalized["receipt_goods_id"],
                    normalized["in_class_date"],
                    normalized["out_class_date"],
                    normalized["out_class_reason"],
                    normalized["class_id"],
                    normalized["student_user_id"],
                ),
            )
        self.set_class_membership_override(normalized_class_id, True)
        self._class_payload_cache.pop(str(normalized_class_id), None)
        rows = {row["student_user_id"]: row for row in self.list_local_class_students(normalized_class_id)}
        return rows.get(normalized_student_id)

    def delete_local_class_student_relations(self, class_id: int | str | None, student_ids: list[Any]) -> list[int]:
        normalized_class_id = _coerce_int(class_id)
        normalized_student_ids = [
            normalized_student_id
            for normalized_student_id in (_coerce_int(student_id) for student_id in student_ids)
            if normalized_student_id is not None
        ]
        if normalized_class_id is None or not normalized_student_ids:
            return []
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM local_class_students WHERE class_id = ? AND student_user_id = ?",
                [(normalized_class_id, student_id) for student_id in normalized_student_ids],
            )
        self.set_class_membership_override(normalized_class_id, True)
        self._class_payload_cache.pop(str(normalized_class_id), None)
        return normalized_student_ids

    def _student_snapshot_by_id(self, student_id: int | str | None) -> dict[str, Any]:
        normalized_student_id = _coerce_int(student_id) or 0
        for student in self.list_local_students():
            if _coerce_int(student.get("id")) != normalized_student_id:
                continue
            display_name = str(student.get("realname") or student.get("name") or f"Student {normalized_student_id}").strip()
            return {
                "id": normalized_student_id,
                "name": student.get("name") or f"student-{normalized_student_id}",
                "headimg_url": student.get("headimg_url") or "",
                "studentUserInfo": {
                    "id": normalized_student_id,
                    "realname": display_name,
                    "headimg_url": student.get("headimg_url") or "",
                    "phone_num": student.get("phone_num") or "",
                    "school_name": student.get("school_name") or "",
                    "grade": student.get("grade") or "",
                },
            }

        cached = self.find_cached_student_row(normalized_student_id)
        if isinstance(cached, dict):
            nested = cached.get("studentUserInfo") if isinstance(cached.get("studentUserInfo"), dict) else {}
            display_name = (
                cached.get("stuName")
                or nested.get("realname")
                or cached.get("realName")
                or cached.get("name")
                or f"Student {normalized_student_id}"
            )
            return {
                "id": normalized_student_id,
                "name": cached.get("stuAccount") or cached.get("name") or f"student-{normalized_student_id}",
                "headimg_url": cached.get("headimg_url") or nested.get("headimg_url") or "",
                "studentUserInfo": {
                    "id": normalized_student_id,
                    "realname": str(display_name).strip(),
                    "headimg_url": cached.get("headimg_url") or nested.get("headimg_url") or "",
                },
            }

        for student in self.list_campus_user_students():
            if _coerce_int(student.get("id")) != normalized_student_id:
                continue
            nested = student.get("studentUserInfo") if isinstance(student.get("studentUserInfo"), dict) else {}
            display_name = student.get("realName") or nested.get("realname") or student.get("name") or f"Student {normalized_student_id}"
            return {
                "id": normalized_student_id,
                "name": student.get("name") or f"student-{normalized_student_id}",
                "headimg_url": student.get("headimg_url") or nested.get("headimg_url") or "",
                "studentUserInfo": {
                    "id": normalized_student_id,
                    "realname": str(display_name).strip(),
                    "headimg_url": student.get("headimg_url") or nested.get("headimg_url") or "",
                },
            }

        return {
            "id": normalized_student_id,
            "name": f"student-{normalized_student_id}",
            "headimg_url": "",
            "studentUserInfo": {
                "id": normalized_student_id,
                "realname": f"Student {normalized_student_id}",
                "headimg_url": "",
            },
        }

    def _build_class_student_payload_row(self, relation: dict[str, Any]) -> dict[str, Any]:
        student_id = _coerce_int(relation.get("student_user_id")) or 0
        student_info = self._student_snapshot_by_id(student_id)
        headimg_url = (
            (student_info.get("studentUserInfo") if isinstance(student_info.get("studentUserInfo"), dict) else {}).get("headimg_url")
            or student_info.get("headimg_url")
            or ""
        )
        return {
            "id": student_id,
            "student_user_id": student_id,
            "curriculum_class_id": _coerce_int(relation.get("class_id")) or 0,
            "xm_goods_id": relation.get("xm_goods_id"),
            "receiptGoodsId": relation.get("receipt_goods_id"),
            "in_class_date": relation.get("in_class_date") or relation.get("created_time") or "",
            "out_class_date": relation.get("out_class_date"),
            "out_class_reason": relation.get("out_class_reason"),
            "is_vaild": True,
            "created_time": relation.get("created_time") or "",
            "studentInfo": {
                "id": student_id,
                "name": student_info.get("name") or f"student-{student_id}",
                "headimg_url": headimg_url,
                "studentUserInfo": self._json_clone(student_info.get("studentUserInfo") or {}),
            },
            "missStuTchPlanNum": 0,
            "missStuTchPlanArr": [],
        }

    def ensure_local_class_membership_snapshot(self, class_id: int | str | None) -> list[dict[str, Any]]:
        normalized_class_id = _coerce_int(class_id)
        if normalized_class_id is None:
            return []
        if self.is_class_membership_overridden(normalized_class_id):
            return self.list_local_class_students(normalized_class_id)
        captured = self._get_captured_class_student_payload(str(normalized_class_id)) or {}
        self.set_class_membership_override(normalized_class_id, True)
        student_rows = captured.get("studentList") if isinstance(captured, dict) else []
        if isinstance(student_rows, list):
            for row in student_rows:
                if not isinstance(row, dict):
                    continue
                student_info = row.get("studentInfo") if isinstance(row.get("studentInfo"), dict) else {}
                self.upsert_local_class_student_relation(
                    class_id=normalized_class_id,
                    student_user_id=row.get("student_user_id") or student_info.get("id"),
                    xm_goods_id=row.get("xm_goods_id"),
                    receipt_goods_id=row.get("receiptGoodsId") or row.get("receipt_goods_id"),
                    in_class_date=self._normalize_optional_text(row.get("in_class_date"), row.get("created_time")) or "",
                    out_class_date=self._normalize_optional_text(row.get("out_class_date")),
                    out_class_reason=self._normalize_optional_text(row.get("out_class_reason")),
                )
        return self.list_local_class_students(normalized_class_id)

    def _build_local_class_student_payload(self, normalized_class_id: int | str) -> dict[str, Any] | None:
        class_id = _coerce_int(normalized_class_id)
        if class_id is None:
            return None
        relations = self.list_local_class_students(class_id)
        if not relations and not self.is_class_membership_overridden(class_id):
            return None
        student_list = [self._build_class_student_payload_row(relation) for relation in relations]
        return {
            "studentList": student_list,
            "list": self._json_clone(student_list),
            "rows": self._json_clone(student_list),
            "page_no": 1,
            "page_size": len(student_list) or 1,
            "total": len(student_list),
        }

    def _get_captured_class_student_payload(self, normalized_class_id: int | str) -> dict[str, Any] | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT url, body_path, headers_json
                FROM api_responses
                WHERE method = 'GET'
                  AND profile_name = 'teacher'
                  AND url LIKE '%/api/get/class/student/list%'
                ORDER BY url
                """
            ).fetchall()

        best_content: dict[str, Any] | None = None
        best_score = -1
        for row in rows:
            body_path = self.root / row["body_path"]
            if not body_path.exists():
                continue
            try:
                headers = json.loads(row["headers_json"])
                payload = json.loads(_decode_response_body(body_path.read_bytes(), headers).decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            content = payload.get("content") or {}
            student_list = content.get("studentList") or []
            if not isinstance(content, dict) or not isinstance(student_list, list):
                continue

            parsed = urlparse(row["url"])
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            row_class_id = str(
                query.get("classId")
                or query.get("class_id")
                or query.get("classes_id")
                or ""
            ).strip()
            if not row_class_id and student_list:
                first_row = student_list[0] if isinstance(student_list[0], dict) else {}
                row_class_id = str((first_row or {}).get("curriculum_class_id") or "").strip()
            if row_class_id != str(normalized_class_id).strip():
                continue

            total = _coerce_int(content.get("total")) or len(student_list)
            score = max(total, len(student_list))
            if score <= best_score:
                continue
            best_score = score
            best_content = self._localize_persisted_value(content)

        return best_content

    def _captured_teaching_plans_by_id(self) -> dict[int, dict[str, Any]]:
        plans_by_id: dict[int, dict[str, Any]] = {}
        for payload in self._load_teacher_api_payloads("/api/get/teaching/plan/list"):
            content = payload.get("content") or {}
            entries = content.get("teachingPlan") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                plan_id = _coerce_int(entry.get("id"))
                if plan_id is None or plan_id in plans_by_id:
                    continue
                plans_by_id[plan_id] = self._localize_persisted_value(entry)
        return plans_by_id

    def _local_teaching_plan_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "curriculum_class_id": row["curriculum_class_id"],
            "educational_institution_campus_id": row["educational_institution_campus_id"],
            "lecturer_id": row["lecturer_id"],
            "lecturer_name": row["lecturer_name"],
            "subject_id": row["subject_id"],
            "curriculum_id": row["curriculum_id"],
            "curriculum_meterial_id": row["curriculum_meterial_id"],
            "class_date": row["class_date"],
            "start_class_date": row["start_class_date"],
            "end_class_date": row["end_class_date"],
            "sign_state": row["sign_state"],
            "sign_state_new": row["sign_state_new"],
            "sign_date": row["sign_date"],
            "cost_lesson_hour": row["cost_lesson_hour"],
            "sort_num": row["sort_num"],
            "title": row["title"],
            "custom_lesson_title": row["custom_lesson_title"],
            "custom_lesson_desc": row["custom_lesson_desc"],
            "is_cost_lesson_hour": bool(row["is_cost_lesson_hour"]),
            "deleted": bool(row["deleted"]),
            "student_override": bool(row["student_override"]),
            "created_time": row["created_time"],
            "updated_at": row["updated_at"],
        }

    def list_local_teaching_plans(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, curriculum_class_id, educational_institution_campus_id, lecturer_id, lecturer_name,
                       subject_id, curriculum_id, curriculum_meterial_id, class_date, start_class_date,
                       end_class_date, sign_state, sign_state_new, sign_date, cost_lesson_hour, sort_num,
                       title, custom_lesson_title, custom_lesson_desc, is_cost_lesson_hour, deleted,
                       student_override, created_time, updated_at
                FROM local_teaching_plans
                ORDER BY id
                """
            ).fetchall()
        return [self._local_teaching_plan_row_to_dict(row) for row in rows]

    def get_local_teaching_plan(self, teaching_plan_id: int | str | None) -> dict[str, Any] | None:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, curriculum_class_id, educational_institution_campus_id, lecturer_id, lecturer_name,
                       subject_id, curriculum_id, curriculum_meterial_id, class_date, start_class_date,
                       end_class_date, sign_state, sign_state_new, sign_date, cost_lesson_hour, sort_num,
                       title, custom_lesson_title, custom_lesson_desc, is_cost_lesson_hour, deleted,
                       student_override, created_time, updated_at
                FROM local_teaching_plans
                WHERE id = ?
                """,
                (normalized_teaching_plan_id,),
            ).fetchone()
        return self._local_teaching_plan_row_to_dict(row) if row is not None else None

    def _list_merged_teaching_plans(self) -> list[dict[str, Any]]:
        captured_rows = self._captured_teaching_plans_by_id()
        local_rows_by_id = {
            _coerce_int(row.get("id")) or 0: row
            for row in self.list_local_teaching_plans()
            if isinstance(row, dict) and _coerce_int(row.get("id")) is not None
        }
        class_rows_by_id = {
            _coerce_int(row.get("id")) or 0: row
            for row in self.list_classes()
            if isinstance(row, dict) and _coerce_int(row.get("id")) is not None
        }
        subject_info_map = self._subject_info_map()
        curriculum_info_map = self._curriculum_info_map()
        material_map = self._curriculum_material_map()
        campus_name_map = self._campus_name_map()

        rows: list[dict[str, Any]] = []
        all_plan_ids = sorted({*captured_rows.keys(), *local_rows_by_id.keys()})
        for plan_id in all_plan_ids:
            base = self._json_clone(captured_rows.get(plan_id) or {})
            local = local_rows_by_id.get(plan_id) or {}
            if local.get("deleted"):
                continue

            base_class_info = base.get("classInfo") if isinstance(base.get("classInfo"), dict) else {}
            base_lesson_info = base.get("lessionInfo") if isinstance(base.get("lessionInfo"), dict) else {}
            class_id = self._normalize_optional_int(
                local.get("curriculum_class_id"),
                base.get("curriculum_class_id"),
                base_class_info.get("id"),
            )
            if class_id is None:
                continue

            class_row = class_rows_by_id.get(class_id) or {}
            curriculum_material_id = self._normalize_optional_int(
                local.get("curriculum_meterial_id"),
                base.get("curriculum_meterial_id"),
                base.get("curriculum_material_id"),
                base_class_info.get("curriculum_meterial_id"),
                base_class_info.get("curriculum_material_id"),
            )
            material = material_map.get(curriculum_material_id or -1, {})
            subject_id = self._normalize_optional_int(
                local.get("subject_id"),
                base.get("subject_id"),
                material.get("subject_id"),
            )
            curriculum_id = self._normalize_optional_int(
                local.get("curriculum_id"),
                base.get("curriculum_id"),
                material.get("curriculum_id"),
            )
            local_campus_id = _coerce_int(local.get("educational_institution_campus_id"))
            if local_campus_id is not None and local_campus_id <= 0:
                local_campus_id = None
            campus_id = self._normalize_optional_int(
                local_campus_id,
                class_row.get("educational_institution_campus_id"),
                base.get("educational_institution_campus_id"),
                base_class_info.get("educational_institution_campus_id"),
            ) or 0
            local_lecturer_id = _coerce_int(local.get("lecturer_id"))
            if local_lecturer_id is not None and local_lecturer_id <= 0:
                local_lecturer_id = None
            lecturer_id = self._normalize_optional_int(
                local_lecturer_id,
                class_row.get("lecturer_id"),
                base.get("lecturer_id"),
                base_class_info.get("lecturer_id"),
            ) or 0
            lecturer_name = self._normalize_optional_text(
                local.get("lecturer_name"),
                class_row.get("lecturer_name"),
                base.get("lecturerName"),
                base_class_info.get("lecturerName"),
                base_class_info.get("lectureName"),
            ) or ""
            subject_id_list = self._normalize_int_list(
                class_row.get("subject_id_list"),
                class_row.get("subjectIdList"),
                subject_id,
            )
            curriculum_id_list = self._normalize_int_list(
                class_row.get("curriculum_id_list"),
                class_row.get("curriculumIdList"),
                curriculum_id,
            )
            class_info = {
                **base_class_info,
                "id": class_id,
                "name": self._normalize_optional_text(class_row.get("name"), base_class_info.get("name"), base.get("className")) or f"Class {class_id}",
                "educational_institution_campus_id": campus_id,
                "curriculum_class_type": self._normalize_optional_int(
                    class_row.get("curriculum_class_type"),
                    base_class_info.get("curriculum_class_type"),
                )
                or 1,
                "teaching_type": self._normalize_optional_int(class_row.get("teaching_type"), base_class_info.get("teaching_type")) or 1,
                "week_json": self._decode_json_list(class_row.get("week_json") if "week_json" in class_row else base_class_info.get("week_json")),
                "week_str": self._normalize_optional_text(class_row.get("week_str"), base_class_info.get("week_str")) or "",
                "time_str": self._normalize_optional_text(class_row.get("time_str"), base_class_info.get("time_str")) or "",
                "end_class_state": self._normalize_optional_int(class_row.get("end_class_state"), base_class_info.get("end_class_state")) or 0,
                "lecturer_id": lecturer_id,
                "lecturerName": lecturer_name,
                "lectureName": lecturer_name,
                "subjectInfoList": [
                    self._json_clone(subject_info_map[row_subject_id])
                    for row_subject_id in subject_id_list
                    if row_subject_id in subject_info_map
                ],
                "curriculumInfoList": [
                    self._json_clone(curriculum_info_map[row_curriculum_id])
                    for row_curriculum_id in curriculum_id_list
                    if row_curriculum_id in curriculum_info_map
                ],
                "is_cost_lesson_hour": bool(
                    self._normalize_optional_int(
                        local.get("is_cost_lesson_hour"),
                        class_row.get("is_cost_lesson_hour"),
                        base_class_info.get("is_cost_lesson_hour"),
                    )
                    or 0
                ),
            }
            lesson_info = self._json_clone(base_lesson_info)
            if material:
                for key in ("id", "title", "desc", "img_url", "ppt_url", "video_url", "stu_note_url", "teach_template_url", "home_template_url"):
                    if lesson_info.get(key) in (None, "") and material.get(key) not in (None, ""):
                        lesson_info[key] = material.get(key)
            custom_lesson_title = self._normalize_optional_text(local.get("custom_lesson_title"), base.get("custom_lesson_title"))
            custom_lesson_desc = self._normalize_optional_text(local.get("custom_lesson_desc"), base.get("custom_lesson_desc"))
            if custom_lesson_title:
                lesson_info["title"] = custom_lesson_title
            if custom_lesson_desc:
                lesson_info["desc"] = custom_lesson_desc
            if lesson_info.get("title") in (None, ""):
                lesson_info["title"] = self._normalize_optional_text(base.get("title"), material.get("title")) or f"Lesson {plan_id}"
            row = {
                **base,
                "id": plan_id,
                "curriculum_class_id": class_id,
                "educational_institution_campus_id": campus_id,
                "lecturer_id": lecturer_id,
                "lecturerName": lecturer_name,
                "className": class_info.get("name") or f"Class {class_id}",
                "campusName": base.get("campusName") or campus_name_map.get(campus_id, ""),
                "subject_id": subject_id or 0,
                "curriculum_id": curriculum_id or 0,
                "curriculum_meterial_id": curriculum_material_id or 0,
                "class_date": self._normalize_optional_text(local.get("class_date"), base.get("class_date")) or "",
                "start_class_date": self._normalize_optional_text(local.get("start_class_date"), base.get("start_class_date")) or "",
                "end_class_date": self._normalize_optional_text(local.get("end_class_date"), base.get("end_class_date")) or "",
                "sign_state": self._normalize_optional_int(local.get("sign_state"), base.get("sign_state")) or 0,
                "sign_state_new": self._normalize_optional_int(
                    local.get("sign_state_new"),
                    base.get("sign_state_new"),
                    local.get("sign_state"),
                    base.get("sign_state"),
                )
                or 0,
                "sign_date": self._normalize_optional_text(local.get("sign_date"), base.get("sign_date")) or "",
                "cost_lesson_hour": self._normalize_optional_float(local.get("cost_lesson_hour"), base.get("cost_lesson_hour")) or 0.0,
                "sort_num": self._normalize_optional_int(local.get("sort_num"), base.get("sort_num")) or 0,
                "title": self._normalize_optional_text(local.get("title"), base.get("title"), lesson_info.get("title")) or "",
                "custom_lesson_title": custom_lesson_title or "",
                "custom_lesson_desc": custom_lesson_desc,
                "is_cost_lesson_hour": bool(
                    self._normalize_optional_int(
                        local.get("is_cost_lesson_hour"),
                        base.get("is_cost_lesson_hour"),
                        class_info.get("is_cost_lesson_hour"),
                    )
                    or 0
                ),
                "classInfo": class_info,
                "lessionInfo": lesson_info,
                "student_override": bool(local.get("student_override") or False),
            }
            rows.append(row)

        rows.sort(
            key=lambda row: (
                str(row.get("start_class_date") or row.get("class_date") or ""),
                _coerce_int(row.get("sort_num")) or 0,
                _coerce_int(row.get("id")) or 0,
            )
        )
        return rows

    def find_teaching_plan(self, teaching_plan_id: int | str | None) -> dict[str, Any] | None:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return None
        for row in self.list_teaching_plans():
            if _coerce_int((row or {}).get("id")) == normalized_teaching_plan_id:
                return row
        return None

    def next_teaching_plan_id(self) -> int:
        max_id = 80000
        with self._connect() as connection:
            row = connection.execute("SELECT MAX(id) AS max_id FROM local_teaching_plans").fetchone()
        if row is not None:
            max_id = max(max_id, _coerce_int(row["max_id"]) or max_id)
        for row in self.list_teaching_plans():
            if not isinstance(row, dict):
                continue
            max_id = max(max_id, _coerce_int(row.get("id")) or max_id)
        return max_id + 1

    def upsert_local_teaching_plan(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        plan_id = _coerce_int(payload.get("id") or payload.get("teaching_plan_id") or payload.get("tchPlanId") or payload.get("teachingPlanId"))
        if plan_id is None:
            plan_id = self.next_teaching_plan_id()
        current = self.get_local_teaching_plan(plan_id) or self.find_teaching_plan(plan_id) or {}
        class_info = current.get("classInfo") if isinstance(current.get("classInfo"), dict) else {}
        class_id = self._normalize_optional_int(
            payload.get("curriculum_class_id"),
            payload.get("classId"),
            payload.get("classes_id"),
            current.get("curriculum_class_id"),
            class_info.get("id"),
        )
        if class_id is None:
            return None
        class_row = self.find_class(class_id) or {}
        normalized = {
            "id": plan_id,
            "curriculum_class_id": class_id,
            "educational_institution_campus_id": self._normalize_optional_int(
                payload.get("educational_institution_campus_id"),
                current.get("educational_institution_campus_id"),
                class_row.get("educational_institution_campus_id"),
                class_info.get("educational_institution_campus_id"),
            )
            or 0,
            "lecturer_id": self._normalize_optional_int(
                payload.get("lecturer_id"),
                current.get("lecturer_id"),
                class_row.get("lecturer_id"),
                class_info.get("lecturer_id"),
            ),
            "lecturer_name": self._normalize_optional_text(
                payload.get("lecturer_name"),
                current.get("lecturerName"),
                class_row.get("lecturer_name"),
                class_info.get("lecturerName"),
                class_info.get("lectureName"),
            ),
            "subject_id": self._normalize_optional_int(payload.get("subject_id"), current.get("subject_id")),
            "curriculum_id": self._normalize_optional_int(payload.get("curriculum_id"), current.get("curriculum_id")),
            "curriculum_meterial_id": self._normalize_optional_int(
                payload.get("curriculum_meterial_id"),
                payload.get("curriculum_material_id"),
                payload.get("lessonId"),
                current.get("curriculum_meterial_id"),
            )
            or 0,
            "class_date": self._normalize_optional_text(payload.get("class_date"), current.get("class_date")) or "",
            "start_class_date": self._normalize_optional_text(payload.get("start_class_date"), current.get("start_class_date")) or "",
            "end_class_date": self._normalize_optional_text(payload.get("end_class_date"), current.get("end_class_date")) or "",
            "sign_state": self._normalize_optional_int(payload.get("sign_state"), current.get("sign_state")) or 0,
            "sign_state_new": self._normalize_optional_int(
                payload.get("sign_state_new"),
                current.get("sign_state_new"),
                payload.get("sign_state"),
                current.get("sign_state"),
            )
            or 0,
            "sign_date": self._normalize_optional_text(payload.get("sign_date"), current.get("sign_date")) or "",
            "cost_lesson_hour": self._normalize_optional_float(payload.get("cost_lesson_hour"), current.get("cost_lesson_hour")) or 0.0,
            "sort_num": self._normalize_optional_int(payload.get("sort_num"), current.get("sort_num")) or 0,
            "title": self._normalize_optional_text(payload.get("title"), current.get("title")),
            "custom_lesson_title": self._normalize_optional_text(payload.get("custom_lesson_title"), payload.get("customLessonTitle"), current.get("custom_lesson_title")),
            "custom_lesson_desc": self._normalize_optional_text(payload.get("custom_lesson_desc"), payload.get("customLessonDesc"), current.get("custom_lesson_desc")),
            "is_cost_lesson_hour": int(bool(self._normalize_optional_int(payload.get("is_cost_lesson_hour"), current.get("is_cost_lesson_hour")) or 0)),
            "deleted": int(bool(self._normalize_optional_int(payload.get("deleted"), current.get("deleted")) or 0)),
            "student_override": int(bool(self._normalize_optional_int(payload.get("student_override"), current.get("student_override")) or 0)),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_teaching_plans (
                    id, curriculum_class_id, educational_institution_campus_id, lecturer_id, lecturer_name,
                    subject_id, curriculum_id, curriculum_meterial_id, class_date, start_class_date,
                    end_class_date, sign_state, sign_state_new, sign_date, cost_lesson_hour, sort_num,
                    title, custom_lesson_title, custom_lesson_desc, is_cost_lesson_hour, deleted,
                    student_override, created_time, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_time FROM local_teaching_plans WHERE id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    normalized["id"],
                    normalized["curriculum_class_id"],
                    normalized["educational_institution_campus_id"],
                    normalized["lecturer_id"],
                    normalized["lecturer_name"],
                    normalized["subject_id"],
                    normalized["curriculum_id"],
                    normalized["curriculum_meterial_id"],
                    normalized["class_date"],
                    normalized["start_class_date"],
                    normalized["end_class_date"],
                    normalized["sign_state"],
                    normalized["sign_state_new"],
                    normalized["sign_date"],
                    normalized["cost_lesson_hour"],
                    normalized["sort_num"],
                    normalized["title"],
                    normalized["custom_lesson_title"],
                    normalized["custom_lesson_desc"],
                    normalized["is_cost_lesson_hour"],
                    normalized["deleted"],
                    normalized["student_override"],
                    normalized["id"],
                ),
            )
        return self.get_local_teaching_plan(plan_id)

    def mark_teaching_plan_deleted(self, teaching_plan_id: int | str | None) -> dict[str, Any] | None:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return None
        return self.upsert_local_teaching_plan({"id": normalized_teaching_plan_id, "deleted": 1})

    def set_teaching_plan_student_override(self, teaching_plan_id: int | str | None, student_override: bool = True) -> dict[str, Any] | None:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return None
        return self.upsert_local_teaching_plan({"id": normalized_teaching_plan_id, "student_override": int(bool(student_override))})

    def is_teaching_plan_student_overridden(self, teaching_plan_id: int | str | None) -> bool:
        local_plan = self.get_local_teaching_plan(teaching_plan_id)
        return bool((local_plan or {}).get("student_override"))

    def _local_teaching_plan_student_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "teaching_plan_id": row["teaching_plan_id"],
            "student_user_id": row["student_user_id"],
            "stu_tch_plan_type": row["stu_tch_plan_type"],
            "sign_state": row["sign_state"],
            "sign_date": row["sign_date"],
            "cost_state": row["cost_state"],
            "cost_lesson_hour": row["cost_lesson_hour"],
            "over_lesson_hour": row["over_lesson_hour"],
            "not_come_reason": row["not_come_reason"],
            "remark": row["remark"],
            "xm_goods_id": row["xm_goods_id"],
            "receipt_goods_id": row["receipt_goods_id"],
            "created_time": row["created_time"],
            "updated_at": row["updated_at"],
        }

    def list_local_teaching_plan_students(self, teaching_plan_id: int | str | None) -> list[dict[str, Any]]:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT teaching_plan_id, student_user_id, stu_tch_plan_type, sign_state, sign_date,
                       cost_state, cost_lesson_hour, over_lesson_hour, not_come_reason, remark,
                       xm_goods_id, receipt_goods_id, created_time, updated_at
                FROM local_teaching_plan_students
                WHERE teaching_plan_id = ?
                ORDER BY created_time, student_user_id
                """,
                (normalized_teaching_plan_id,),
            ).fetchall()
        return [self._local_teaching_plan_student_row_to_dict(row) for row in rows]

    def upsert_local_teaching_plan_student_relation(
        self,
        *,
        teaching_plan_id: int | str | None,
        student_user_id: int | str | None,
        stu_tch_plan_type: Any = 1,
        sign_state: Any = None,
        sign_date: str | None = None,
        cost_state: str | None = None,
        cost_lesson_hour: Any = None,
        over_lesson_hour: Any = None,
        not_come_reason: str | None = None,
        remark: str | None = None,
        xm_goods_id: Any = None,
        receipt_goods_id: Any = None,
    ) -> dict[str, Any] | None:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        normalized_student_id = _coerce_int(student_user_id)
        if normalized_teaching_plan_id is None or normalized_student_id is None:
            return None
        current_rows = {row["student_user_id"]: row for row in self.list_local_teaching_plan_students(normalized_teaching_plan_id)}
        current = current_rows.get(normalized_student_id, {})
        normalized = {
            "teaching_plan_id": normalized_teaching_plan_id,
            "student_user_id": normalized_student_id,
            "stu_tch_plan_type": self._normalize_optional_int(stu_tch_plan_type, current.get("stu_tch_plan_type")) or 1,
            "sign_state": self._normalize_optional_int(sign_state, current.get("sign_state")),
            "sign_date": self._normalize_optional_text(sign_date, current.get("sign_date")),
            "cost_state": self._normalize_optional_text(cost_state, current.get("cost_state")) or "1",
            "cost_lesson_hour": self._normalize_optional_float(cost_lesson_hour, current.get("cost_lesson_hour")),
            "over_lesson_hour": self._normalize_optional_float(over_lesson_hour, current.get("over_lesson_hour")),
            "not_come_reason": self._normalize_optional_text(not_come_reason, current.get("not_come_reason")),
            "remark": self._normalize_optional_text(remark, current.get("remark")),
            "xm_goods_id": self._normalize_optional_int(xm_goods_id, current.get("xm_goods_id")),
            "receipt_goods_id": self._normalize_optional_int(receipt_goods_id, current.get("receipt_goods_id")),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO local_teaching_plan_students (
                    teaching_plan_id, student_user_id, stu_tch_plan_type, sign_state, sign_date,
                    cost_state, cost_lesson_hour, over_lesson_hour, not_come_reason, remark,
                    xm_goods_id, receipt_goods_id, created_time, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(
                        (SELECT created_time FROM local_teaching_plan_students WHERE teaching_plan_id = ? AND student_user_id = ?),
                        CURRENT_TIMESTAMP
                    ),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    normalized["teaching_plan_id"],
                    normalized["student_user_id"],
                    normalized["stu_tch_plan_type"],
                    normalized["sign_state"],
                    normalized["sign_date"],
                    normalized["cost_state"],
                    normalized["cost_lesson_hour"],
                    normalized["over_lesson_hour"],
                    normalized["not_come_reason"],
                    normalized["remark"],
                    normalized["xm_goods_id"],
                    normalized["receipt_goods_id"],
                    normalized["teaching_plan_id"],
                    normalized["student_user_id"],
                ),
            )
        self.set_teaching_plan_student_override(normalized_teaching_plan_id, True)
        rows = {row["student_user_id"]: row for row in self.list_local_teaching_plan_students(normalized_teaching_plan_id)}
        return rows.get(normalized_student_id)

    def delete_local_teaching_plan_student_relations(self, teaching_plan_id: int | str | None, student_ids: list[Any]) -> list[int]:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        normalized_student_ids = [
            normalized_student_id
            for normalized_student_id in (_coerce_int(student_id) for student_id in student_ids)
            if normalized_student_id is not None
        ]
        if normalized_teaching_plan_id is None or not normalized_student_ids:
            return []
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM local_teaching_plan_students WHERE teaching_plan_id = ? AND student_user_id = ?",
                [(normalized_teaching_plan_id, student_id) for student_id in normalized_student_ids],
            )
        self.set_teaching_plan_student_override(normalized_teaching_plan_id, True)
        return normalized_student_ids

    def ensure_local_teaching_plan_student_snapshot(self, teaching_plan_id: int | str | None) -> list[dict[str, Any]]:
        normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
        if normalized_teaching_plan_id is None:
            return []
        if self.is_teaching_plan_student_overridden(normalized_teaching_plan_id):
            return self.list_local_teaching_plan_students(normalized_teaching_plan_id)
        plan = self.find_teaching_plan(normalized_teaching_plan_id) or {}
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = self._normalize_optional_int(plan.get("curriculum_class_id"), class_info.get("id"))
        self.set_teaching_plan_student_override(normalized_teaching_plan_id, True)
        if class_id is not None:
            class_payload = self.get_class_student_payload(class_id) or {}
            student_rows = class_payload.get("studentList") if isinstance(class_payload, dict) else []
            if isinstance(student_rows, list):
                for row in student_rows:
                    if not isinstance(row, dict):
                        continue
                    student_info = row.get("studentInfo") if isinstance(row.get("studentInfo"), dict) else {}
                    self.upsert_local_teaching_plan_student_relation(
                        teaching_plan_id=normalized_teaching_plan_id,
                        student_user_id=row.get("student_user_id") or student_info.get("id"),
                        xm_goods_id=row.get("xm_goods_id"),
                        receipt_goods_id=row.get("receiptGoodsId") or row.get("receipt_goods_id"),
                        cost_lesson_hour=plan.get("cost_lesson_hour"),
                    )
        return self.list_local_teaching_plan_students(normalized_teaching_plan_id)

    def _build_local_teaching_plan_by_class_payload(self, normalized_class_id: int | str) -> dict[str, Any] | None:
        class_id = _coerce_int(normalized_class_id)
        if class_id is None:
            return None
        captured_plan_ids = {
            plan_id
            for plan_id, plan in self._captured_teaching_plans_by_id().items()
            if _coerce_int(((plan.get("classInfo") or {}).get("id")) or plan.get("curriculum_class_id")) == class_id
        }
        with self._connect() as connection:
            local_count = connection.execute(
                """
                SELECT COUNT(1) AS count
                FROM local_teaching_plans
                WHERE curriculum_class_id = ?
                   OR id IN (
                        SELECT id
                        FROM local_teaching_plans
                        WHERE id IN ({placeholders})
                   )
                """.format(placeholders=",".join("?" for _ in captured_plan_ids) or "NULL"),
                (class_id, *captured_plan_ids),
            ).fetchone()
        if not captured_plan_ids and not local_count["count"]:
            return None
        if captured_plan_ids and not local_count["count"]:
            return None

        class_student_payload = self.get_class_student_payload(class_id) or {}
        class_student_rows = class_student_payload.get("studentList") if isinstance(class_student_payload, dict) else []
        expected_count = len(class_student_rows) if isinstance(class_student_rows, list) else 0
        subject_map = self._subject_info_map()
        rows: list[dict[str, Any]] = []
        for plan in self.list_teaching_plans():
            if not isinstance(plan, dict):
                continue
            plan_class_id = _coerce_int(((plan.get("classInfo") or {}).get("id")) or plan.get("curriculum_class_id"))
            if plan_class_id != class_id:
                continue
            plan_id = _coerce_int(plan.get("id")) or 0
            plan_student_rows = self.list_local_teaching_plan_students(plan_id) if self.is_teaching_plan_student_overridden(plan_id) else []
            rows.append(
                {
                    "id": plan_id,
                    "lessionInfo": self._json_clone(plan.get("lessionInfo") or {}),
                    "subject_id": plan.get("subject_id"),
                    "subject_name": (
                        (subject_map.get(_coerce_int(plan.get("subject_id")) or -1) or {}).get("name")
                        or plan.get("subjectName")
                        or ""
                    ),
                    "lecturer_id": plan.get("lecturer_id"),
                    "lecturer_name": plan.get("lecturerName") or ((plan.get("classInfo") or {}).get("lecturerName")) or "",
                    "start_class_date": plan.get("start_class_date"),
                    "end_class_date": plan.get("end_class_date"),
                    "class_date": plan.get("class_date"),
                    "sign_state": plan.get("sign_state"),
                    "sign_state_new": plan.get("sign_state_new"),
                    "sign_date": plan.get("sign_date"),
                    "cost_lesson_hour": plan.get("cost_lesson_hour"),
                    "sort_num": plan.get("sort_num"),
                    "curriculum_class_id": class_id,
                    "educational_institution_campus_id": plan.get("educational_institution_campus_id"),
                    "custom_lesson_title": plan.get("custom_lesson_title") or "",
                    "custom_lesson_desc": plan.get("custom_lesson_desc"),
                    "stuTchPlanArr": [],
                    "expected_count": expected_count,
                    "actual_count": len(plan_student_rows) if plan_student_rows else 0,
                }
            )
        rows.sort(
            key=lambda row: (
                str(row.get("class_date") or row.get("start_class_date") or ""),
                _coerce_int(row.get("sort_num")) or 0,
                _coerce_int(row.get("id")) or 0,
            )
        )
        return {
            "teaching_plan_list": rows,
            "teachingPlanList": self._json_clone(rows),
            "list": self._json_clone(rows),
            "rows": self._json_clone(rows),
        }

    def _get_captured_teaching_plan_by_class_payload(self, normalized_class_id: int | str) -> dict[str, Any] | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT url, body_path, headers_json
                FROM api_responses
                WHERE method = 'GET'
                  AND profile_name = 'teacher'
                  AND url LIKE '%/api/get/teaching/plan/by/class/id%'
                ORDER BY url
                """
            ).fetchall()

        best_content: dict[str, Any] | None = None
        best_score = -1
        for row in rows:
            body_path = self.root / row["body_path"]
            if not body_path.exists():
                continue
            try:
                headers = json.loads(row["headers_json"])
                payload = json.loads(_decode_response_body(body_path.read_bytes(), headers).decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            content = payload.get("content") or {}
            teaching_plan_list = content.get("teaching_plan_list") or []
            if not isinstance(content, dict) or not isinstance(teaching_plan_list, list):
                continue

            parsed = urlparse(row["url"])
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            row_class_id = str(
                query.get("classes_id")
                or query.get("classId")
                or query.get("class_id")
                or ""
            ).strip()
            if not row_class_id and teaching_plan_list:
                first_row = teaching_plan_list[0] if isinstance(teaching_plan_list[0], dict) else {}
                row_class_id = str((first_row or {}).get("curriculum_class_id") or "").strip()
            if row_class_id != str(normalized_class_id).strip():
                continue

            score = len(teaching_plan_list)
            if score <= best_score:
                continue
            best_score = score
            best_content = self._localize_persisted_value(content)

        return best_content

    def store_route_capture(
        self,
        *,
        profile_name: str,
        route: str,
        final_url: str,
        status: int,
        html: str,
        captured_xhr_count: int,
    ) -> str:
        relative_path = route_html_path(profile_name, route)
        self.write_text(relative_path, html)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO routes (
                    profile_name, route, final_url, status, html_path, captured_xhr_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_name,
                    route,
                    final_url,
                    status,
                    relative_path,
                    captured_xhr_count,
                ),
            )
        return relative_path

    def lookup_route_capture(self, route: str, *, preferred_profile: str | None = None) -> dict[str, Any] | None:
        preferred_rank = {
            "admin": "WHEN 'admin' THEN 0 WHEN 'teacher' THEN 1 WHEN 'student' THEN 2 ELSE 3",
            "teacher": "WHEN 'teacher' THEN 0 WHEN 'student' THEN 1 ELSE 2",
            "student": "WHEN 'student' THEN 0 WHEN 'teacher' THEN 1 ELSE 2",
        }.get(preferred_profile, "WHEN 'teacher' THEN 0 WHEN 'student' THEN 1 ELSE 2")
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT profile_name, route, final_url, status, html_path, captured_xhr_count
                FROM routes
                WHERE route = ?
                ORDER BY CASE profile_name
                    {preferred_rank}
                END
                LIMIT 1
                """,
                (route,),
            ).fetchone()
        if row is None:
            return None
        return {
            "profile_name": row["profile_name"],
            "route": row["route"],
            "final_url": row["final_url"],
            "status": row["status"],
            "html_path": row["html_path"],
            "captured_xhr_count": row["captured_xhr_count"],
        }
