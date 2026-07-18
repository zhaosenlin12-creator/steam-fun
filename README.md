# steam_fun mirror

Local offline delivery workspace for the course-domain flows of `steam_fun`.

## Course Offline Workflow

1. Rebuild local course snapshot tables:
   `D:/kaifa/steam_fun/.venv/Scripts/python.exe scripts/build_course_snapshot.py --root D:/kaifa/steam_fun`
2. Fetch every required course asset while online:
   `D:/kaifa/steam_fun/.venv/Scripts/python.exe scripts/fetch_course_archive.py --root D:/kaifa/steam_fun`
3. Generate the offline completeness report:
   `D:/kaifa/steam_fun/.venv/Scripts/python.exe scripts/course_offline_audit.py --root D:/kaifa/steam_fun`
4. Start the local server without upstream proxy:
   `powershell -File scripts/run_server.ps1 -Port 8000 -NoLiveProxy`
5. Run the browser verification flow:
   `D:/kaifa/steam_fun/.venv/Scripts/python.exe scripts/management_flow_audit.py`

## Latest Verified Results

- Snapshot rebuild: `subjects=2`, `curriculums=48`, `materials=630`
- Full course archive: `requested_material_count=630`, `archived_material_count=630`, `failed_material_count=0`, `total_missing_assets=0`
- Offline course audit: `total_materials=630`, `missing_resource_materials=0`, `not_archived_materials=0`
- Browser management flow audit: `admin_page=true`, `student_validity_flow=true`, `class_flow=true`, `all_passed=true`
- Strict local runtime audit: `strict_local_passed=true`, `external_request_count=0`, `failed_response_count=0`, `page_error_count=0`, `console_error_count=0`
- Fresh strict rerun on `2026-06-12 21:17:31`: `all_passed=true`, `strict_local_passed=true`
- Targeted regression slice after strict rerun: `5 passed`
- Server regression suite: `205 passed`
- Full selected regression slice: `228 passed`

## Runtime Artifacts

- `runtime/mirror.sqlite3`
- `runtime/course_offline_report.json`
- `runtime/course_archive_full_summary.json`
- `runtime/management_flow_audit_20260612_211731/summary.json`

## Notes

- Runtime verification was executed against `http://127.0.0.1:8000` with `--no-live-proxy`.
- The latest strict browser audit was re-run on `2026-06-12 21:17:31` and recorded zero external browser requests, zero failed responses, zero page errors, and zero console errors during the verified management and course flows.
- Archived manifests may still retain source-host metadata such as `wugecdn.steam.fun`, but runtime requests for the verified management and course flows were served locally through `127.0.0.1:8000` only.
- The critical offline chain verified in this workspace is: class creation -> class student assignment -> teaching plan bulk add -> teacher PPT entry -> student class entry.
