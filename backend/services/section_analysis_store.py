from ..models import SectionPageAnalysisResult

_results: dict[tuple[str, str, int], SectionPageAnalysisResult] = {}


def store(
    job_id: str, pair_id: str, page_number: int,
    analysis: SectionPageAnalysisResult,
) -> None:
    _results[(job_id, pair_id, page_number)] = analysis


def get(
    job_id: str, pair_id: str, page_number: int,
) -> SectionPageAnalysisResult | None:
    return _results.get((job_id, pair_id, page_number))
