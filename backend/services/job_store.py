import os
import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..models import AnalysisStatus, JobMetadata, PdfPair
from .pdf_utils import get_page_count

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
RUN_INTERRUPTED_ERROR = "Interrupted by backend restart"

_jobs: dict[str, JobMetadata] = {}


def _persist_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = [
        _jobs[job_id].model_dump(mode="json")
        for job_id in sorted(
            _jobs.keys(),
            key=lambda key: _jobs[key].created_at,
            reverse=True,
        )
    ]
    temp_file = JOBS_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_file.replace(JOBS_FILE)


def _reconcile_running_jobs() -> None:
    changed = False
    for job in _jobs.values():
        if job.analysis_status == AnalysisStatus.running:
            job.analysis_status = AnalysisStatus.failed
            job.analysis_error = RUN_INTERRUPTED_ERROR
            changed = True
        if job.global_analysis_status == AnalysisStatus.running:
            job.global_analysis_status = AnalysisStatus.failed
            changed = True
        if job.section_analysis_status == AnalysisStatus.running:
            job.section_analysis_status = AnalysisStatus.failed
            changed = True
    if changed:
        _persist_all()


def _load_from_disk() -> None:
    if not JOBS_FILE.exists():
        return
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            logger.warning("Ignoring jobs file: expected list")
            return
        for row in raw:
            job = JobMetadata.model_validate(row)
            _jobs[job.job_id] = job
        _reconcile_running_jobs()
    except Exception:
        logger.exception("Failed to load jobs from disk")


def persist_job(job: JobMetadata) -> None:
    _jobs[job.job_id] = job
    _persist_all()


def create_job(
    job_id: str,
    report_type: str,
    reference_dir: str,
    test_dir: str,
    reference_filenames: list[str],
    test_filenames: list[str],
) -> JobMetadata:
    reference_set = set(reference_filenames)
    test_set = set(test_filenames)

    matched = reference_set & test_set
    unmatched_reference = sorted(reference_set - matched)
    unmatched_test = sorted(test_set - matched)

    pairs: list[PdfPair] = []
    for filename in sorted(matched):
        pair_id = uuid4().hex[:12]
        ref_disk_path = os.path.join(reference_dir, filename)
        test_disk_path = os.path.join(test_dir, filename)
        pairs.append(
            PdfPair(
                pair_id=pair_id,
                filename=filename,
                reference_path=f"/api/jobs/{job_id}/files/reference/{filename}",
                test_path=f"/api/jobs/{job_id}/files/test/{filename}",
                page_count_reference=get_page_count(ref_disk_path),
                page_count_test=get_page_count(test_disk_path),
            )
        )

    job = JobMetadata(
        job_id=job_id,
        report_type=report_type,
        pairs=pairs,
        unmatched_reference=unmatched_reference,
        unmatched_test=unmatched_test,
        created_at=datetime.now().isoformat(),
    )

    persist_job(job)
    return job


def get_job(job_id: str) -> JobMetadata | None:
    return _jobs.get(job_id)


def list_jobs() -> list[JobMetadata]:
    return sorted(_jobs.values(), key=lambda job: job.created_at, reverse=True)


_load_from_disk()
