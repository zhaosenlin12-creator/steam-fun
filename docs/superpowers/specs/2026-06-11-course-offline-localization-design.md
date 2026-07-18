# Steam Fun Course Offline Localization Design

**Date:** 2026-06-11

**Status:** Draft approved in conversation, written for implementation handoff

**Owner:** Codex session working in `D:\kaifa\steam_fun`

## Goal

Turn the course-related domain of the `steam_fun` project into a fully local offline package that can be used continuously after disconnection from the internet.

The final system must satisfy all of the following:

- Course-related pages, APIs, and resources work after the machine is disconnected from the network.
- No course-related browser request points to `steam.fun`, `wugecdn.steam.fun`, `*.aliyuncs.com`, or any other original upstream resource host.
- Course selection, class opening, teaching-plan generation, student course entry, and in-course content usage all run from local data and local assets.
- Confirmed requirements, evidence, standards, and remaining gaps are all recorded in repo artifacts.

## Scope

This design is intentionally broader than "fix one page" and narrower than "mirror the entire platform."

Included scope:

- Course center
- Lesson preparation center
- Class course selection
- Teaching plan creation and retrieval
- Student course entry
- Course PPT/iframe content
- Course code/template files
- Handouts, videos, images, posters, supporting assets
- Course-related API data and local structured persistence
- Offline verification and completeness reporting

Excluded unless later requested:

- Non-course domains that do not affect the course chain
- Full platform parity for unrelated admin modules
- Production deployment packaging beyond local offline use

## Confirmed User Requirements

The user explicitly confirmed the following:

1. The target is `full packaging`, not patching sample pages.
2. Course-related resources must no longer point to original OSS or upstream hosts.
3. The system must continue to work while offline, not just after a one-time test.
4. The project should localize data, backend behavior, frontend behavior, and static resources.
5. Confirmed findings and implementation rules must be written down in project documents.

## Current State Summary

The repository is not a normal split frontend/backend app. It is a replay-and-rewrite local mirror project built around:

- `src/steamfun_mirror/server.py` for FastAPI replay, rewrite, and fallbacks
- `src/steamfun_mirror/storage.py` for SQLite metadata and blob paths
- `origin/steam.fun/` for captured same-origin assets
- `external/` for mirrored third-party assets
- `routes/` for captured HTML routes
- `runtime/api/` and SQLite entries for captured API responses

The existing system already provides:

- SPA shell replay
- Static asset replay and URL rewriting
- API replay from captured responses
- Local fallback responses for many teacher/student paths
- Course-related bootstrap logic for direct page entry

The current failure mode is not "the main course URLs are absent." The failure mode is that the local system still depends on large numbers of upstream subresources and mixed runtime data sources.

## Root Cause Evidence

The following was confirmed during investigation:

1. Historical sample acceptance for material `39525` showed that a few representative course pages can render locally.
2. That historical verification was too narrow and cannot prove the entire course domain is offline-safe.
3. A structured scan over local course material data found:
   - `630` course materials with `ppt_url`
   - `630` mirrored main `ppt_url` entries present locally
   - `630` mirrored `img_url` entries present locally
   - `523` mirrored `stu_note_url` entries present locally
   - `526` mirrored `teach_template_url` entries present locally
   - `521` mirrored `home_template_url` entries present locally
   - `536` mirrored `other_meterial_url` entries present locally
   - `567` mirrored `lession_plan_url` entries present locally
4. A recursive reference check over PPT entry pages found:
   - `510` course materials still reference missing child resources
   - Typical missing child resources include `data/apple-touch-icon.png`, `data/browsersupport.js`, `data/favicon.ico`, `data/jquery.min.js`, `data/jquery.cokie.min.js`, `data/player.js`, `data/ksahdklgjls.js`, and media files such as `sound1.mp3`
5. Therefore the real root cause is:
   - Main course assets are only partially localized
   - Recursive child dependencies are not fully mirrored
   - Runtime behavior still mixes local structured data, captured API payloads, and opportunistic fallbacks

## Design Principles

This implementation must follow these principles:

1. `Offline-first, not proxy-first`
   Runtime behavior should stop behaving like a partial mirror that can silently degrade to upstream expectations.

2. `Structured local truth`
   Captured APIs are an import source, not the final authority for course-domain runtime.

3. `Recursive asset closure`
   A course material is not complete until all of its reachable required assets are local.

4. `Explicit failure over silent drift`
   Missing local assets or missing local data should be reported and recorded, not silently bypassed.

5. `Verifiable completeness`
   Every course material and every major chain step must have machine-generated completeness evidence.

## Target Architecture

The course domain will be organized into four layers.

### 1. Data Layer

The course domain must be backed by a stable local data model in SQLite.

Required local entities:

- Subjects
- Curriculums
- Curriculum materials
- Classes
- Class-student relations
- Teaching plans
- Teaching-plan-student relations
- Template/work relationships
- Course-domain permission and status flags

Target runtime rule:

- Course-domain runtime reads structured local tables first
- Captured API payloads become import material and fallback evidence, not the primary live source

Additional requirement:

- Every `curriculum_material` gets a completeness row describing all relevant URLs, local readiness, and last verification time

### 2. Resource Layer

Resource localization must use course material assets as the root set.

Per material root URLs to crawl:

- `ppt_url`
- `stu_note_url`
- `teach_template_url`
- `home_template_url`
- `other_meterial_url`
- `video_url`
- `lession_plan_url`
- Additional dynamic URLs returned by `currMat/detail` when relevant

Recursive parsing targets:

- HTML `script/src`
- HTML `link/href`
- HTML `img/src`
- HTML `audio`, `video`, `source`
- HTML `iframe/src`
- CSS `url(...)`
- JS and inline text references discoverable with current URL extraction rules
- Player/manifests and `data/*` resource trees

Required outputs:

- Local file storage for every captured asset
- Canonical `upstream URL -> local path` mapping
- Per-material manifest with:
  - root URLs
  - local paths
  - fetched resource count
  - missing resource count
  - missing resource list
  - content-type distribution
  - last verification time

Completion rule:

- A material is not complete if even one required asset reference is unresolved

### 3. Service Layer

Runtime behavior must be changed from "best effort local replay" to "strict local operation" for the course domain.

Course-domain paths in strict mode include at least:

- Course center
- Prepare-lessons routes
- Teach-lessons routes
- Class course-selection routes
- Teaching-plan routes
- Student class/course-entry routes
- `currMat/detail`
- Course-related static and iframe resources

Required runtime rules:

1. Course API read order:
   - structured local tables
   - explicit local archived responses where needed
   - explicit local-miss errors

2. Course resource read order:
   - direct local asset mapping
   - per-material manifest mapping
   - explicit local-miss response with audit logging

3. Upstream external resource requests in the course domain are defects, not acceptable runtime behavior.

4. Direct deep links must receive deterministic local bootstrap state:
   - local auth identity
   - local class context
   - local teaching-plan context
   - local material context

5. Service logs must record:
   - opened material id
   - local resources used
   - missing resources
   - attempted upstream hosts
   - final offline pass/fail status

### 4. Verification Layer

The final project must ship with offline verification artifacts, not only code changes.

Verification must cover the full operational chain:

1. Course list visible in admin/teacher views
2. Class can select course
3. Teaching plan can be created or resolved locally
4. Class-student relationship can be read locally
5. Student can enter the class/course view
6. Prepare PPT page can open offline
7. Teach PPT page can open offline
8. PPT/iframe child resources load offline
9. Handouts, templates, posters, code files, and media load offline

Required verification outputs:

- Material-by-material completeness report
- Offline browser acceptance report
- Host-request audit proving no original upstream host remains in course flows
- Clear classification for each failed material:
  - `missing_resource`
  - `missing_data`
  - `page_logic_failure`
  - `verification_failure`

## Implementation Strategy

The implementation should proceed in this order:

1. Build a course material completeness model in SQLite
2. Build a recursive asset closure script for all course materials
3. Import or normalize course-domain structured data from captured payloads into stable local tables
4. Change course-domain runtime reads to prefer stable local structured data
5. Enforce strict local serving rules for course-domain resources
6. Add completeness and offline verification scripts
7. Run online fill once, then re-run in offline mode until all target chains pass

## Expected Deliverables

The final deliverable set must include all of the following:

- Local SQLite data covering the course domain
- Fully localized course resource directory tree
- Per-material completeness manifest/report
- Offline acceptance scripts
- Updated runtime logic that serves course-domain requests locally
- Runbook for starting and verifying the offline package
- Recorded residual issue list if anything remains out of scope

## Risks And Mitigations

### Risk 1: Hidden JS-discovered asset references

Some course pages may construct URLs at runtime instead of declaring them statically.

Mitigation:

- Combine static recursive parsing with browser-driven request capture
- Feed discovered runtime URLs back into the manifest and fetch queue

### Risk 2: Mixed runtime truth between local tables and archived APIs

The current project already mixes local tables and captured responses.

Mitigation:

- Make course-domain runtime lookup order deterministic
- Record which source provided each response during verification

### Risk 3: Large asset volume

Full course localization may generate a large on-disk asset set.

Mitigation:

- Record counts and sizes in manifests
- Avoid duplicate fetches through canonical URL lookup
- Reuse current asset index in `MirrorStore`

### Risk 4: Direct deep-link page assumptions

Some pages rely on SPA lifecycle timing and local/session storage assumptions.

Mitigation:

- Keep existing bootstrap injection patterns where proven useful
- Normalize them into explicit offline bootstrap helpers
- Validate with direct deep-link acceptance tests

## Acceptance Criteria

The work is considered complete only when all of the following are true:

1. Course-domain flows work after disconnection from the network.
2. No browser request in verified course flows targets original upstream domains.
3. The course material completeness report shows zero unresolved required resources for the accepted scope.
4. The class selection -> teaching plan -> student course entry -> in-course content chain passes in automated verification.
5. The project contains written records of:
   - requirements
   - root cause evidence
   - implementation rules
   - verification results
   - remaining issues, if any

## Out-Of-Scope Failure Definition

The following outcomes do **not** count as success:

- A few example materials work while many materials still miss `data/*` assets
- Pages render only while online
- Pages render while still requesting original OSS or upstream domains
- Runtime falls back to upstream-dependent assumptions without recording the miss
- Success claims are based only on one sample material or one historical report

## Next Step

After this design is reviewed, the next artifact should be a detailed implementation plan that breaks the work into executable steps for:

- data normalization
- full asset closure
- service strict-local mode
- offline verification

