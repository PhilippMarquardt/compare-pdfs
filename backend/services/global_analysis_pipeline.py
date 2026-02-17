import asyncio
import logging
from pathlib import Path

from ..models import AnalysisStatus
from . import global_analysis_store, job_store
from .global_analysis import analyze_page_global

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 4
PROGRESS_PERSIST_INTERVAL = 10
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"


def _resolve_path(job_id: str, category: str, filename: str) -> str:
    return str(UPLOADS_DIR / job_id / category / filename)


async def run_global_analysis(job_id: str) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    work_items: list[tuple[str, str, str, int]] = []
    for pair in job.pairs:
        ref_path = _resolve_path(job_id, "reference", pair.filename)
        test_path = _resolve_path(job_id, "test", pair.filename)
        max_pages = max(pair.page_count_reference, pair.page_count_test)
        for pg in range(1, max_pages + 1):
            work_items.append((pair.pair_id, ref_path, test_path, pg))

    job.global_analysis_status = AnalysisStatus.running
    job.global_analysis_total = len(work_items)
    job.global_analysis_progress = 0
    job_store.persist_job(job)

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    completed = 0

    async def bounded(pair_id: str, ref_path: str, test_path: str, pg: int):
        nonlocal completed
        async with semaphore:
            try:
                result = await analyze_page_global(ref_path, test_path, pg)
                global_analysis_store.store(job_id, pair_id, pg, result)
            except Exception as e:
                logger.error("global analysis error job=%s pair=%s p%d: %s", job_id, pair_id, pg, e)
            finally:
                completed += 1
                job.global_analysis_progress = completed
                if (
                    completed == job.global_analysis_total
                    or completed % PROGRESS_PERSIST_INTERVAL == 0
                ):
                    job_store.persist_job(job)

    try:
        await asyncio.gather(*(
            bounded(pid, ref, test, pg)
            for pid, ref, test, pg in work_items
        ))
        job.global_analysis_status = AnalysisStatus.done
        job_store.persist_job(job)
    except Exception as e:
        logger.error("global analysis pipeline failed job=%s: %s", job_id, e)
        job.global_analysis_status = AnalysisStatus.failed
        job_store.persist_job(job)
