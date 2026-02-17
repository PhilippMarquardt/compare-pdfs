import asyncio
import logging
from pathlib import Path

from rapidfuzz import fuzz, process

from ..models import (
    AnalysisStatus,
    CheckStatus,
    SectionCheck,
    SectionCheckResult,
    SectionPageAnalysisResult,
)
from . import analysis_store, job_store, section_analysis_store
from .paired_sections import _render_page_image
from .section_analysis import _crop_section, analyze_section

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 4
PROGRESS_PERSIST_INTERVAL = 10
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
MATCH_THRESHOLD = 75


def _resolve_path(job_id: str, category: str, filename: str) -> str:
    return str(UPLOADS_DIR / job_id / category / filename)


def _match_sections(
    ref_names: list[str], test_names: list[str],
) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """Match ref section names to test section names.
    Returns: (matched_pairs, ref_only, test_only)
    """
    matched: list[tuple[str, str]] = []
    used_test: set[str] = set()

    for rn in ref_names:
        # Exact match first
        if rn in test_names and rn not in used_test:
            matched.append((rn, rn))
            used_test.add(rn)
            continue
        # Fuzzy match
        available = [tn for tn in test_names if tn not in used_test]
        if available:
            m = process.extractOne(rn, available, scorer=fuzz.WRatio)
            if m and m[1] >= MATCH_THRESHOLD:
                matched.append((rn, m[0]))
                used_test.add(m[0])
                continue

    ref_only = [rn for rn in ref_names if not any(rn == p[0] for p in matched)]
    test_only = [tn for tn in test_names if tn not in used_test]

    return matched, ref_only, test_only


async def _analyze_page_sections(
    job_id: str, pair_id: str,
    ref_path: str, test_path: str, page_num: int,
) -> None:
    """Analyze all sections on a single page pair."""
    ref_analysis = analysis_store.get(job_id, pair_id, "reference", page_num)
    test_analysis = analysis_store.get(job_id, pair_id, "test", page_num)

    if not ref_analysis and not test_analysis:
        section_analysis_store.store(
            job_id, pair_id, page_num,
            SectionPageAnalysisResult(page_number=page_num, results=[]),
        )
        return

    ref_sections = {s.name: s for s in (ref_analysis.sections if ref_analysis else [])}
    test_sections = {s.name: s for s in (test_analysis.sections if test_analysis else [])}

    # Match sections
    matched, ref_only, test_only = _match_sections(
        list(ref_sections.keys()), list(test_sections.keys()),
    )

    # Render full page images
    ref_image, test_image = await asyncio.gather(
        asyncio.to_thread(_render_page_image, ref_path, page_num),
        asyncio.to_thread(_render_page_image, test_path, page_num),
    )

    results: list[SectionCheckResult] = []

    # Analyze matched section pairs
    for ref_name, test_name in matched:
        ref_sec = ref_sections[ref_name]
        test_sec = test_sections[test_name]

        ref_crop = _crop_section(ref_image, ref_sec.bbox)
        test_crop = _crop_section(test_image, test_sec.bbox)

        try:
            result = await analyze_section(ref_crop, test_crop, ref_name)
            results.append(result)
        except Exception as e:
            logger.error("section analysis error %s p%d %s: %s", pair_id, page_num, ref_name, e)
            results.append(SectionCheckResult(
                section_name=ref_name,
                checks=[SectionCheck(
                    check_name="Analysis error",
                    status=CheckStatus.maybe,
                    explanation=f"Analysis failed: {e}",
                )],
                matched_instructions=False,
            ))

    # Flag sections only on reference (missing from test)
    for name in ref_only:
        results.append(SectionCheckResult(
            section_name=name,
            checks=[SectionCheck(
                check_name="Section presence",
                status=CheckStatus.issue,
                explanation="Section missing on test page",
            )],
            matched_instructions=False,
        ))

    # Flag sections only on test (missing from reference)
    for name in test_only:
        results.append(SectionCheckResult(
            section_name=name,
            checks=[SectionCheck(
                check_name="Section presence",
                status=CheckStatus.issue,
                explanation="Section missing on reference page",
            )],
            matched_instructions=False,
        ))

    section_analysis_store.store(
        job_id, pair_id, page_num,
        SectionPageAnalysisResult(page_number=page_num, results=results),
    )


async def run_section_analysis(job_id: str) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    # Section detection must be done
    if job.analysis_status != AnalysisStatus.done:
        logger.error("Cannot run section analysis: section detection not done for job %s", job_id)
        return

    work_items: list[tuple[str, str, str, int]] = []
    for pair in job.pairs:
        ref_path = _resolve_path(job_id, "reference", pair.filename)
        test_path = _resolve_path(job_id, "test", pair.filename)
        max_pages = max(pair.page_count_reference, pair.page_count_test)
        for pg in range(1, max_pages + 1):
            work_items.append((pair.pair_id, ref_path, test_path, pg))

    job.section_analysis_status = AnalysisStatus.running
    job.section_analysis_total = len(work_items)
    job.section_analysis_progress = 0
    job_store.persist_job(job)

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    completed = 0

    async def bounded(pair_id: str, ref_path: str, test_path: str, pg: int):
        nonlocal completed
        async with semaphore:
            try:
                await _analyze_page_sections(job_id, pair_id, ref_path, test_path, pg)
            except Exception as e:
                logger.error("section analysis pipeline error job=%s pair=%s p%d: %s", job_id, pair_id, pg, e)
            finally:
                completed += 1
                job.section_analysis_progress = completed
                if (
                    completed == job.section_analysis_total
                    or completed % PROGRESS_PERSIST_INTERVAL == 0
                ):
                    job_store.persist_job(job)

    try:
        await asyncio.gather(*(
            bounded(pid, ref, test, pg)
            for pid, ref, test, pg in work_items
        ))
        job.section_analysis_status = AnalysisStatus.done
        job_store.persist_job(job)
    except Exception as e:
        logger.error("section analysis pipeline failed job=%s: %s", job_id, e)
        job.section_analysis_status = AnalysisStatus.failed
        job_store.persist_job(job)
