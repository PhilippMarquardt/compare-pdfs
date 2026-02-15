from ..models import PageAnalysis

_results: dict[tuple[str, str, str, int], PageAnalysis] = {}


def store(
    job_id: str, pair_id: str, category: str, page_number: int,
    analysis: PageAnalysis,
) -> None:
    _results[(job_id, pair_id, category, page_number)] = analysis


def get(
    job_id: str, pair_id: str, category: str, page_number: int,
) -> PageAnalysis | None:
    return _results.get((job_id, pair_id, category, page_number))
