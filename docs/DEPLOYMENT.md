# Steam.Fun 本地部署指南

## 给谁用

这套本地化镜像面向**机构老师**（备课、开班、上课）和**学生**（登录、加入班级、上课），
**管理员**负责维护课程体系和老师账号。三种角色登录入口都在同一个 `127.0.0.1:8000`，
按账号自动路由到对应的工作台。

## 一台机器、5 分钟跑起来

### 1. 准备

- Windows 10/11（开发环境实测），或任意能跑 Python 3.10+ 的系统
- 端口 `8000` 空闲
- 已经克隆并解压 `D:\kaifa\steam_fun`（项目根目录）

### 2. 启动服务

```powershell
cd D:\kaifa\steam_fun
python -m steamfun_mirror.cli --root . serve --host 127.0.0.1 --port 8000 --no-live-proxy
```

> 想给同网段的其他老师/同学访问，把 `127.0.0.1` 改成 `0.0.0.0`，并确保 Windows 防火墙放行 8000。
> 不需要 `--live-proxy`：所有外部资源（OSS / wugecdn）都已在 `runtime/_external/` 下镜像好。

启动成功后日志会显示：

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 3. 打开浏览器

| 角色 | 入口 URL | 账号 | 密码 |
| --- | --- | --- | --- |
| 管理员 | http://127.0.0.1:8000/school-home-page/class-management1 | `18164173640` | `123456` |
| 老师 | http://127.0.0.1:8000/school-home-page/class-management1/students-management1 | `zhaosenlin` | `123456` |
| 学生 | http://127.0.0.1:8000/code-classroom/myClass | `lbschenmuran` | `123456` |

如果想换账号，先到 `runtime/mirror.sqlite3` 的 `profiles` 表里加；登录后立即生效。

## 4. 核心链路验证（建议每月做一次）

```powershell
# 单元测试
python -m pytest tests/test_runtime_audit_helpers.py tests/test_persist_demo.py -v

# 管理链路全流程审计（学生新增/班级开班/教学计划/老师备课/学生进入班级）
python -m scripts.management_flow_audit

# 前端 12 个核心页面巡检
python -m scripts.runtime_flow_audit
```

两份审计的 summary 会落在 `runtime/management_flow_audit_<时间戳>/summary.json` 和
`runtime/runtime_flow_audit/summary.json`。绿色条件是：

- `all_passed = true`
- `persistence.class_reused/lessons_reused/student_reused/student_already_attached` 全为 true
- `network_audit.failed_response_count` 和 `console_error_count` 均为 0

## 数据存在哪里

| 用途 | 路径 |
| --- | --- |
| SQLite 持久化（账号/班级/学生/教学计划） | `runtime/mirror.sqlite3` |
| 课程素材/PPT/视频镜像 | `runtime/_external/` |
| 浏览器登录态缓存 | `runtime/browser_profiles/` |
| API 抓包快照 | `runtime/api/`, `runtime/routes/` |
| 审计运行记录 | `runtime/management_flow_audit_<时间戳>/` |

要清空所有业务数据重置到出厂状态：

```powershell
Stop-Process -Name python -Force    # 先停服务
Remove-Item runtime\mirror.sqlite3
```

下次启动会自动建空库；登录接口会返回空白列表，再走一遍 `ensure_persist_*` 助手即可重建 demo 数据。

## 备份 / 迁移

```powershell
# 备份
Copy-Item runtime\mirror.sqlite3 backup\mirror_<日期>.sqlite3

# 恢复
Stop-Process -Name python -Force
Copy-Item backup\mirror_<日期>.sqlite3 runtime\mirror.sqlite3
```

`mirror.sqlite3` 是单文件数据库，整库迁移即可保留全部账号、班级、学生、教学计划、备课记录。

## 添加新老师账号

1. 登录管理员界面 → 后台 → 课程中心 → 用户管理
2. 新建用户，角色选"教师"
3. 在 `runtime/mirror.sqlite3` 的 `profiles` 表里插入一行，参考 `teacher` 行填 `profile_name`、`token`、`fresh_auth_json`
4. 用新账号登录 `http://127.0.0.1:8000/` ，会自动进入老师工作台

## 添加新校区

`runtime/mirror.sqlite3` 的 `local_classes.educational_institution_campus_id` 字段是校区 id。
新建班级时把这个 id 填上即可。所有 API 调用都会自动按校区隔离。

## 老师备课 → 开班 → 上课 完整流程

1. 老师登录 `http://127.0.0.1:8000/`
2. 进入 **课程中心** → **备课**，选课件 → 写教案
3. 进入 **教务中心** → **班级管理** → **开班**
   - 班级名（如"周六 Scratch 班"）
   - 上课时间（周几、第几节）
   - 关联课程（之前备过的课件）
4. 班级创建后，老师在班级详情页 **添加学员**（学员必须先在 **学员管理** 里建好账号）
5. 上课时：进入 **我的班级** → 点击该班级 → 进入教室（PPT/编程）
6. 学生登录后 → **我的班级** → 进入上课

## 常见问题

- **启动报错 `ModuleNotFoundError: No module named scripts.xxx`**：确认 `cwd` 是 `D:\kaifa\steam_fun`。
- **学生登录后看不到班级**：老师需要在 **班级管理 → 添加学员** 把该学生加进来；学生必须先在 **学员管理** 注册。
- **接口一直 404**：检查 URL 是否在 `_inject_runtime_guards` 黑名单外；超过 15 个被关闭的看板模块都返回空列表。
- **审计脚本卡死**：通常是浏览器在加载外部 JS。等 90 秒就会自然超时；不要强杀。
