# Last Verified Snapshot

最近一次端到端绿灯：**2026-07-17 00:46 (本地时间)**

## 测试结果

| 项 | 结果 |
| --- | --- |
| 单元测试 | 15 / 15 通过 (`tests/test_runtime_audit_helpers.py` + `tests/test_persist_demo.py`) |
| Management Flow Audit | all_passed = True |
| Runtime Flow Audit | 12 / 12 probe 文件全部生成 |

## 持久化 demo 数据

| 实体 | 稳定 id | 复用标记 |
| --- | --- | --- |
| 学生 | `demo_persist_student` id=**37** | reused=true |
| 班级 | `DEMO-PERSIST-CLASS` id=**143567** | reused=true |
| 教学计划 #1 | id=**5182933** | reused=true |
| 教学计划 #2 | id=**5182934** | reused=true |
| 班级-学员关系 | (class 143567, student 37) | already_attached=true |

跨次审计 id 完全稳定，再跑 `management_flow_audit` 也不会产生新数据。

## 三角色端到端链路

- **管理员** 18164173640：进入课程中心 → 课程体系 ✅
- **老师** zhaosenlin：学员管理 / 班级管理 / 教学计划 / 课程中心 全部命中；学生 validity 改期接口通过（UI + API 一致 = 2026-09-15）
- **学生** lbschenmuran：登录成功，进入我的班级 ✅

## 网络层

- external_request_count = 0（没有任何请求逃逸到外部 OSS/CDN）
- failed_response_count = 0
- page_error_count = 0
- console_error_count = 0

## 部署建议

机构老师/学生只要拉这份项目，执行：

```powershell
python -m steamfun_mirror.cli --root . serve --host 0.0.0.0 --port 8000 --no-live-proxy
```

然后用浏览器打开 `http://<server-ip>:8000/` 即可。详细步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。
