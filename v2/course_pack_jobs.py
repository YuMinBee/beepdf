from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from v2.course_packs import create_course_pack


def create_course_pack_job(
    paths: list[str],
    output_root: str = "outputs",
    max_chunk_chars: int = 900,
    pack_id: str | None = None,
) -> dict:
    job_id = _new_job_id()
    total_documents = len(paths)
    job = {
        "job_id": job_id,
        "status": "running",
        "stage": "ingesting_documents",
        "progress": 0.05,
        "processed_documents": 0,
        "total_documents": total_documents,
        "pack_id": pack_id,
        "course_pack": {},
        "warnings": [],
        "error": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _write_job(job, output_root=output_root)

    try:
        _update_job(
            job,
            output_root=output_root,
            stage="building_course_pack",
            progress=0.35,
            processed_documents=0,
        )
        course_pack = create_course_pack(
            paths=paths,
            output_root=output_root,
            max_chunk_chars=max_chunk_chars,
            pack_id=pack_id,
        )
        _update_job(
            job,
            output_root=output_root,
            status="succeeded",
            stage="completed",
            progress=1.0,
            processed_documents=course_pack.get("document_count", total_documents),
            pack_id=course_pack.get("pack_id"),
            course_pack=course_pack,
            warnings=course_pack.get("warnings", []),
        )
    except Exception as exc:  # pragma: no cover - defensive job status path
        _update_job(
            job,
            output_root=output_root,
            status="failed",
            stage="failed",
            progress=job.get("progress", 0.0),
            error=str(exc),
            warnings=[*job.get("warnings", []), str(exc)],
        )
    return job


def load_course_pack_job(job_id: str, output_root: str = "outputs") -> dict:
    path = course_pack_job_path(job_id, output_root=output_root)
    if not path.exists():
        return {
            "job_id": job_id,
            "status": "not_found",
            "stage": "missing",
            "progress": 0.0,
            "processed_documents": 0,
            "total_documents": 0,
            "warnings": [f"course pack job not found: {job_id}"],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def course_pack_job_path(job_id: str, output_root: str = "outputs") -> Path:
    return Path(output_root) / "course_pack_jobs" / f"{job_id}.json"


def _update_job(job: dict, output_root: str, **updates) -> None:
    job.update(updates)
    job["updated_at"] = _now_iso()
    _write_job(job, output_root=output_root)


def _write_job(job: dict, output_root: str) -> None:
    path = course_pack_job_path(job["job_id"], output_root=output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"job_{stamp}_{uuid4().hex[:6]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
