import os
from datetime import datetime
from uuid import uuid4

from ..models import JobMetadata, PdfPair
from .pdf_utils import get_page_count

_jobs: dict[str, JobMetadata] = {}


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

    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> JobMetadata | None:
    return _jobs.get(job_id)
