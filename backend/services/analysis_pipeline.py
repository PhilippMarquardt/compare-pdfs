import asyncio
import logging
from pathlib import Path

from ..models import AnalysisStatus
from . import analysis_store, job_store
from .paired_sections import analyze_page_pair

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 4
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"


def _resolve_path(job_id: str, category: str, filename: str) -> str:
    return str(UPLOADS_DIR / job_id / category / filename)


async def run_analysis(job_id: str, mode: str = "paired") -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    # Build work items: one per page per pair (paired call covers both ref+test)
    work_items: list[tuple[str, str, str, int]] = []
    for pair in job.pairs:
        ref_path = _resolve_path(job_id, "reference", pair.filename)
        test_path = _resolve_path(job_id, "test", pair.filename)
        max_pages = max(pair.page_count_reference, pair.page_count_test)
        for pg in range(1, max_pages + 1):
            work_items.append((pair.pair_id, ref_path, test_path, pg))

    job.analysis_status = AnalysisStatus.running
    job.analysis_total = len(work_items)
    job.analysis_progress = 0

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    completed = 0

    async def bounded(pair_id: str, ref_path: str, test_path: str, pg: int):
        nonlocal completed
        async with semaphore:
            try:
                ref_analysis, test_analysis = await analyze_page_pair(
                    ref_path, test_path, pg, mode=mode,
                )
                analysis_store.store(job_id, pair_id, "reference", pg, ref_analysis)
                analysis_store.store(job_id, pair_id, "test", pg, test_analysis)
            except Exception as e:
                logger.error("analysis error job=%s pair=%s p%d: %s", job_id, pair_id, pg, e)
            finally:
                completed += 1
                job.analysis_progress = completed

    try:
        await asyncio.gather(*(
            bounded(pid, ref, test, pg)
            for pid, ref, test, pg in work_items
        ))
        job.analysis_status = AnalysisStatus.done
    except Exception as e:
        job.analysis_status = AnalysisStatus.failed
        job.analysis_error = str(e)
