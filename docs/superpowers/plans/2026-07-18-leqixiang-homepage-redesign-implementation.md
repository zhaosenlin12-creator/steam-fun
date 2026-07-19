# 乐启享机器人首页重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `steamfun_mirror` 的根路径 `/` 改造成 `乐启享机器人` 的中文品牌首页，同时保留现有 `/login`、`/background/login`、老师/学生/管理员业务路由与登录后跳转逻辑。

**Architecture:** 不去侵入既有抓取页面，而是在 `server.py` 增加一个独立的根首页路由和一个独立的站点静态资源路由。首页 HTML 由新的 `homepage.py` 负责渲染，资源全部本地化到包内目录，前端交互只用原生 CSS/JS 实现，学员展示墙借鉴 `prisma-web` 的穹顶交互但不引入 React 运行时。

**Tech Stack:** Python 3.10, FastAPI, pytest, package-local static assets, vanilla HTML/CSS/JavaScript.

---

## File Map

- Create: `src/steamfun_mirror/homepage.py`
  负责首页内容数据、HTML 渲染、静态资源路径解析。
- Modify: `src/steamfun_mirror/server.py`
  增加 `/` 官网首页路由和 `/_site/homepage/{asset_path:path}` 静态资源路由。
- Create: `src/steamfun_mirror/site_assets/homepage/styles.css`
  官网首页样式、响应式布局、玻璃质感、滚动节奏和 3D 展示墙视觉。
- Create: `src/steamfun_mirror/site_assets/homepage/app.js`
  导航滚动、滚动 reveal、首屏动效、学员穹顶自动旋转/拖拽。
- Create: `src/steamfun_mirror/site_assets/homepage/media/logo.png`
- Create: `src/steamfun_mirror/site_assets/homepage/media/hero-video.mp4`
- Create: `src/steamfun_mirror/site_assets/homepage/media/teacher-liu.jpg`
- Create: `src/steamfun_mirror/site_assets/homepage/media/teacher-xiang.jpg`
- Create: `src/steamfun_mirror/site_assets/homepage/media/teacher-zhou.jpg`
- Create: `src/steamfun_mirror/site_assets/homepage/media/teacher-yang.jpg`
- Create: `src/steamfun_mirror/site_assets/homepage/media/teacher-senlin.jpg`
- Create: `src/steamfun_mirror/site_assets/homepage/media/teacher-zhao.jpg`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-1.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-2.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-3.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-4.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-5.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-6.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-7.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/student-8.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/course-lego.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/course-robot.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/course-python.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/course-ai.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/honor-1.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/honor-2.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/honor-3.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/honor-4.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/campus-1.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/campus-2.webp`
- Create: `src/steamfun_mirror/site_assets/homepage/media/campus-3.webp`
- Modify: `tests/test_server.py`
  覆盖 `/` 首页行为、静态资源路由行为、登录入口保留与 cookie 不再触发首页重定向。

---

### Task 1: 用 TDD 改写根首页行为

**Files:**
- Modify: `tests/test_server.py`
- Modify: `src/steamfun_mirror/server.py`

- [ ] **Step 1: 先写失败测试，定义新的 `/` 行为**

```python
def test_public_root_serves_marketing_homepage(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "乐启享机器人" in response.text
    assert 'href="/login"' in response.text
    assert "从乐高启蒙到 AI 创造" in response.text


def test_root_with_existing_teacher_cookie_still_serves_marketing_homepage(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    _store_teacher_profile(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["location"] if "location" in response.headers else "" == ""
    assert "乐启享机器人" in response.text
    assert "/school-home-page/class-management1/students-management1" not in response.headers.get("location", "")


def test_homepage_static_asset_route_serves_local_css(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/_site/homepage/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
```

- [ ] **Step 2: 运行这几个测试，确认它们先失败**

Run:

```powershell
python -m pytest tests/test_server.py -k "marketing_homepage or homepage_static_asset_route or public_root_serves_marketing_homepage or existing_teacher_cookie" -q
```

Expected: `FAIL`，因为当前 `/` 还是 307 重定向，`/_site/homepage/styles.css` 也不存在。

- [ ] **Step 3: 在 `server.py` 增加独立首页路由和首页资源路由**

```python
@app.get("/")
def marketing_homepage(request: Request) -> Response:
    return Response(
        content=render_marketing_homepage(request).encode("utf-8"),
        media_type="text/html",
    )


@app.get("/_site/homepage/{asset_path:path}")
def homepage_static_asset(asset_path: str) -> Response:
    candidate = homepage_asset_path(asset_path)
    if candidate is None:
        return Response(status_code=404)
    return _static_response_or_404(candidate, expected_asset_path=asset_path)
```

- [ ] **Step 4: 重跑根首页测试，确认新路由接管 `/`**

Run:

```powershell
python -m pytest tests/test_server.py -k "marketing_homepage or homepage_static_asset_route or public_root_serves_marketing_homepage or existing_teacher_cookie" -q
```

Expected: 首页相关测试通过，既有 `/login` 与业务路由测试尚未被触碰。

- [ ] **Step 5: 提交根入口行为切换**

```powershell
git add src/steamfun_mirror/server.py tests/test_server.py
git commit -m "feat: serve marketing homepage from root"
```

### Task 2: 构建中文品牌首页与本地化资源

**Files:**
- Create: `src/steamfun_mirror/homepage.py`
- Create: `src/steamfun_mirror/site_assets/homepage/styles.css`
- Create: `src/steamfun_mirror/site_assets/homepage/app.js`
- Create: `src/steamfun_mirror/site_assets/homepage/media/*`

- [ ] **Step 1: 先写失败测试，钉住首页信息架构**

```python
def test_marketing_homepage_contains_required_sections(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/")

    assert 'id="brand"' in response.text
    assert 'id="faculty"' in response.text
    assert 'id="gallery"' in response.text
    assert 'id="courses"' in response.text
    assert 'id="honors"' in response.text
    assert 'id="campus"' in response.text
    assert 'id="showreel"' in response.text
    assert 'id="contact"' in response.text
    assert response.text.count(">登录<") == 1
    assert "https://codebn.cn/courses.html" in response.text
```

- [ ] **Step 2: 运行结构测试，确认当前首页还不满足**

Run:

```powershell
python -m pytest tests/test_server.py -k "marketing_homepage_contains_required_sections" -q
```

Expected: `FAIL`，因为渲染函数和资源目录还没有实现完整内容。

- [ ] **Step 3: 在 `homepage.py` 建立首页数据和 HTML 渲染函数**

```python
HOMEPAGE_TITLE = "乐启享机器人"
HOMEPAGE_SUBTITLE = "从乐高启蒙到 AI 创造，系统培养孩子的科技素养与创造力"


def render_marketing_homepage(request: Request) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{HOMEPAGE_TITLE}</title>
    <link rel="stylesheet" href="/_site/homepage/styles.css">
  </head>
  <body>
    <header class="site-header">...</header>
    <main>
      <section id="brand">...</section>
      <section id="faculty">...</section>
      <section id="gallery">...</section>
      <section id="courses">...</section>
      <section id="honors">...</section>
      <section id="campus">...</section>
      <section id="showreel">...</section>
      <section id="contact">...</section>
    </main>
    <script src="/_site/homepage/app.js" defer></script>
  </body>
</html>"""
```

- [ ] **Step 4: 本地化真实参考资源并完成 CSS/JS**

Run:

```powershell
New-Item -ItemType Directory -Force src\steamfun_mirror\site_assets\homepage\media | Out-Null
Copy-Item C:\Users\Administrator\Desktop\logo.png src\steamfun_mirror\site_assets\homepage\media\logo.png
Copy-Item D:\kaifa\_references\leqixiang_web\public\home\3.mp4 src\steamfun_mirror\site_assets\homepage\media\hero-video.mp4
Copy-Item "D:\kaifa\_references\leqixiang_web\images\teacher_photo\刘老师  校长 创始人.jpg" src\steamfun_mirror\site_assets\homepage\media\teacher-liu.jpg
Copy-Item "D:\kaifa\_references\leqixiang_web\images\teacher_photo\向老师 乐高专家.jpg" src\steamfun_mirror\site_assets\homepage\media\teacher-xiang.jpg
Copy-Item "D:\kaifa\_references\leqixiang_web\images\teacher_photo\周老师  硬件专家.jpg" src\steamfun_mirror\site_assets\homepage\media\teacher-zhou.jpg
Copy-Item "D:\kaifa\_references\leqixiang_web\images\teacher_photo\杨老师  教学主管.jpg" src\steamfun_mirror\site_assets\homepage\media\teacher-yang.jpg
Copy-Item "D:\kaifa\_references\leqixiang_web\images\teacher_photo\森林老师  副校长 合伙人.jpg" src\steamfun_mirror\site_assets\homepage\media\teacher-senlin.jpg
Copy-Item "D:\kaifa\_references\leqixiang_web\images\teacher_photo\赵老师 教务财务.jpg" src\steamfun_mirror\site_assets\homepage\media\teacher-zhao.jpg
```

`styles.css` 里完成深色高保真骨架、蓝橙品牌过渡、玻璃导航、课程卡、荣誉墙、视频段和联系方式并列布局；`app.js` 里完成滚动导航和学员穹顶自动旋转/拖拽。

- [ ] **Step 5: 重跑首页结构测试并检查首页资源是否都能加载**

Run:

```powershell
python -m pytest tests/test_server.py -k "marketing_homepage_contains_required_sections or homepage_static_asset_route or public_root_serves_marketing_homepage" -q
```

Expected: 首页结构测试全部通过。

- [ ] **Step 6: 提交首页渲染与资源**

```powershell
git add src/steamfun_mirror/homepage.py src/steamfun_mirror/site_assets/homepage src/steamfun_mirror/server.py tests/test_server.py
git commit -m "feat: add leqixiang marketing homepage"
```

### Task 3: 回归验证登录入口和现有系统不受影响

**Files:**
- Modify: `tests/test_server.py`
- Verify: `src/steamfun_mirror/server.py`

- [ ] **Step 1: 追加回归测试，确认首页不影响现有登录和业务路由**

```python
def test_login_route_still_clears_stale_profile_cookie(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))
    client.cookies.set("mirror_profile", "teacher")

    response = client.get("/login")

    assert response.status_code == 200
    assert "set-cookie" in response.headers


def test_business_route_still_falls_back_to_shell(tmp_path: Path) -> None:
    _write_shell(tmp_path)
    client = TestClient(create_app(tmp_path, allow_live_proxy=False))

    response = client.get("/school-home-page/class-management1/students-management1")

    assert response.status_code == 200
    assert "shell" in response.text
```

- [ ] **Step 2: 跑首页相关与关键回归测试**

Run:

```powershell
python -m pytest tests/test_server.py -k "root or homepage or login_route_clears_stale_profile_state or frontend_route_like_path_falls_back_to_shell or teacher_students_management_route_bootstraps_schoolinfo_session or student_myclass_route_bootstraps_student_vuex_and_schoolinfo" -q
```

Expected: 首页行为和关键登录/路由回归测试通过。

- [ ] **Step 3: 运行更完整的 `test_server.py`，确认没有引入新的首页回归**

Run:

```powershell
python -m pytest tests/test_server.py -q
```

Expected: 允许保留仓库已知失败，但不能新增首页相关失败；如果失败数增加，先定位并修正。

- [ ] **Step 4: 本地查看 git diff，确认只改首页相关内容**

Run:

```powershell
git status --short
git diff -- src/steamfun_mirror/server.py src/steamfun_mirror/homepage.py src/steamfun_mirror/site_assets/homepage tests/test_server.py
```

Expected: diff 只包含首页、资源路由和测试变更，没有误改教学系统其他逻辑。

- [ ] **Step 5: 提交验证后的最终版本**

```powershell
git add src/steamfun_mirror/server.py src/steamfun_mirror/homepage.py src/steamfun_mirror/site_assets/homepage tests/test_server.py docs/superpowers/plans/2026-07-18-leqixiang-homepage-redesign-implementation.md
git commit -m "feat: redesign public homepage for leqixiang"
```

## Self-Review

1. Spec coverage
   `/` 首页、中文品牌、单一登录入口、师资、学员展示墙、课程入口、赛事成果、校区环境、品牌视频、联系方式、本地化资源、保持业务路由不动，全部有对应任务。
2. Placeholder scan
   计划里没有 `TODO`、`TBD`、`后续补` 这类占位语。
3. Type consistency
   首页入口统一使用 `render_marketing_homepage()` 和 `homepage_asset_path()`，前后任务引用一致。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-18-leqixiang-homepage-redesign-implementation.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

This thread already has an isolated worktree and the user asked to continue推进，所以直接按 Inline Execution 执行。
