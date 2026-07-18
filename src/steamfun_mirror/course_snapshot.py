from __future__ import annotations

from typing import Any

from .storage import MirrorStore


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


def _subject_name(payload: dict[str, Any]) -> str:
    return str(payload.get("name") or payload.get("subjectName") or payload.get("subject_name") or "").strip()


def _is_placeholder_subject_name(name: Any, subject_id: int | None = None) -> bool:
    normalized = str(name or "").strip()
    if not normalized:
        return True
    if subject_id is not None and normalized == f"Subject {subject_id}":
        return True
    parts = normalized.split()
    return len(parts) == 2 and parts[0] == "Subject" and parts[1].isdigit()


def _normalized_subject_name(name: Any, subject_id: int | None = None) -> str | None:
    normalized = str(name or "").strip()
    if _is_placeholder_subject_name(normalized, subject_id):
        return None
    return normalized


def _curriculum_snapshot_from_auth_entry(
    entry: dict[str, Any],
    subject_names_by_id: dict[int, str],
    subject_ids_by_name: dict[str, int],
) -> dict[str, Any]:
    curriculum_info = entry.get("curriculumInfo")
    curriculum = dict(curriculum_info) if isinstance(curriculum_info, dict) else {}

    if not curriculum.get("id"):
        curriculum["id"] = entry.get("curriculum_id") or entry.get("id")

    subject_id = curriculum.get("subject_id")
    if subject_id in (None, ""):
        subject_id = entry.get("subject_id") or entry.get("subjectId")
        if subject_id not in (None, ""):
            curriculum["subject_id"] = subject_id

    normalized_subject_id = _coerce_int(curriculum.get("subject_id"))
    subject_name = (
        _normalized_subject_name(curriculum.get("subject_name"), normalized_subject_id)
        or _normalized_subject_name(curriculum.get("subjectName"), normalized_subject_id)
        or _normalized_subject_name(entry.get("subjectName"), normalized_subject_id)
        or _normalized_subject_name(entry.get("subject_name"), normalized_subject_id)
    )
    if normalized_subject_id is None and subject_name:
        normalized_subject_id = subject_ids_by_name.get(subject_name.casefold())
        if normalized_subject_id is not None:
            curriculum["subject_id"] = normalized_subject_id

    catalog_subject_name = subject_names_by_id.get(normalized_subject_id or -1)
    if catalog_subject_name:
        subject_name = catalog_subject_name

    if subject_name:
        curriculum["subject_name"] = subject_name
        curriculum["subjectName"] = subject_name

    return curriculum


def import_captured_course_domain(store: MirrorStore) -> dict[str, int]:
    summary = {
        "subjects": 0,
        "curriculums": 0,
        "materials": 0,
    }
    subject_names_by_id: dict[int, str] = {}
    subject_ids_by_name: dict[str, int] = {}

    for subject in store.list_campus_subjects():
        snapshot = store.upsert_local_subject_snapshot(subject)
        if snapshot is None:
            continue
        summary["subjects"] += 1
        subject_id = _coerce_int(snapshot.get("id"))
        subject_name = _normalized_subject_name(_subject_name(snapshot), subject_id)
        if subject_id is not None and subject_name:
            subject_names_by_id[subject_id] = subject_name
            subject_ids_by_name[subject_name.casefold()] = subject_id

    for entry in store.list_campus_curriculum_auths():
        curriculum = _curriculum_snapshot_from_auth_entry(entry, subject_names_by_id, subject_ids_by_name)
        snapshot = store.upsert_local_curriculum_snapshot(curriculum)
        if snapshot is None:
            continue
        summary["curriculums"] += 1

    for material in store.list_curriculum_materials():
        snapshot = store.upsert_local_curriculum_material_snapshot(material)
        if snapshot is None:
            continue
        summary["materials"] += 1

    return summary


__all__ = ["import_captured_course_domain"]
