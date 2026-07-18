# Steam.fun Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local steam.fun mirror that can authenticate as teacher or student, replay captured APIs, serve mirrored static assets, and boot the SPA fully from local resources.

**Architecture:** Use `Scrapling` for session-backed route capture and XHR recording, SQLite for mirror metadata, a file store for response bodies/assets, and FastAPI as the local replay server. Login is performed through the real teacher/student APIs, then projected into a browser session by writing the same `vuex` localStorage shape that the production SPA expects.

**Tech Stack:** Python 3.10, Scrapling fetchers, SQLite, FastAPI, Uvicorn, pytest.

---

### Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `scripts/bootstrap.ps1`
- Create: `src/steamfun_mirror/__init__.py`

- [ ] Define a minimal Python package and runtime dependencies.
- [ ] Add a bootstrap script that creates `.venv`, installs `-e ../Scrapling[fetchers]`, then installs the local package in editable mode.
- [ ] Document the mirror directories, capture flow, and local serve commands.

### Task 2: Discovery and Rewrite Primitives

**Files:**
- Create: `src/steamfun_mirror/discovery.py`
- Create: `src/steamfun_mirror/rewrite.py`
- Create: `tests/test_discovery.py`
- Create: `tests/test_rewrite.py`

- [ ] Add failing tests for JS route extraction, API path extraction, shell asset extraction, and external URL rewriting.
- [ ] Implement deterministic regex-based discovery from the SPA shell and `app.js`.
- [ ] Ensure OSS and third-party static URLs can be rewritten to local replay paths.

### Task 3: Persistence Layer

**Files:**
- Create: `src/steamfun_mirror/storage.py`
- Create: `tests/test_storage.py`

- [ ] Add failing tests for mirror path normalization, SQLite initialization, and idempotent API record keys.
- [ ] Implement a file-backed blob store plus SQLite tables for auth profiles, assets, routes, and API responses.

### Task 4: Auth and Session Projection

**Files:**
- Create: `src/steamfun_mirror/auth.py`
- Create: `tests/test_auth.py`

- [ ] Add failing tests for password hashing, teacher/student login payload shapes, and `vuex` localStorage state generation.
- [ ] Implement direct auth calls for teacher and student accounts plus `freshAuthData` capture.

### Task 5: Scrapling Capture Pipeline

**Files:**
- Create: `src/steamfun_mirror/capture.py`
- Create: `src/steamfun_mirror/cli.py`

- [ ] Build route capture on top of `DynamicSession` or `StealthySession` with `capture_xhr`.
- [ ] Inject login state into browser localStorage before protected route traversal.
- [ ] Save shell HTML, XHR responses, discovered assets, and route diagnostics.

### Task 6: Local Replay Server

**Files:**
- Create: `src/steamfun_mirror/server.py`
- Create: `tests/test_server.py`

- [ ] Replay `/api/*` and `/java-api/*` responses from recorded fixtures.
- [ ] Serve mirrored static assets and a local version of the SPA shell with rewritten third-party resource URLs.
- [ ] Provide lightweight local auth endpoints that map credentials to recorded teacher/student profiles.

### Task 7: Verification

**Files:**
- Modify: `README.md`

- [ ] Run pytest for discovery, auth, storage, and replay tests.
- [ ] Run a live capture for teacher and student.
- [ ] Boot the local FastAPI server and verify the SPA shell and API replay endpoints respond correctly.
