# Last Verified Snapshot

Recently verified: **2026-07-31 04:02 (Asia/Shanghai)**

## Verification Results

| Check | Result |
| --- | --- |
| Full test suite | `345 passed` |
| Role data audit | `all_passed=True` |
| Runtime flow audit | `all_passed=True` |
| External browser requests | None |
| Console, page, and HTTP errors | None in the role and runtime audits |

## Verified Public Flow

- The public homepage remains available at `/` regardless of an authenticated session.
- The public course and competition pages return to `/#hero`, rather than a logged-in teaching page.
- The homepage and public course pages do not request Google Fonts or other external font hosts.
- The competition page is local and the public course/competition navigation remains separate from logged-in workspaces.

## Verified Role Flow

- Administrator `18164173640`: lands at `/school-home-page/class-management1`; the former dark course-center URL redirects to `/school-home-page/course-list`.
- Teacher `zhaosenlin`: lands at `/code-classroom/classroom-index`, sees the local course catalog and preparation material/PPT route.
- Student `lbschenmuran`: lands at `/code-classroom/myClass`, sees the assigned class, both teaching plans, and attendance states.
- Shared local data: class `143567` has its assigned student and teaching plans `5182933`, `5182934`.

## Responsive Check

- Administrator mobile workspace was checked in a 390px viewport.
- The page width remains 390px, the navigation drawer opens and closes correctly, and selecting a student-management menu item reaches `/school-home-page/class-management1/students-management1` without horizontal overflow.

## Local Run

```powershell
python -m steamfun_mirror --root . serve --host 0.0.0.0 --port 8000 --no-live-proxy
```

Open `http://<server-ip>:8000/`. Deployment details are in [DEPLOYMENT.md](DEPLOYMENT.md).
