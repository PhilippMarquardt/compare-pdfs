from ..models import GlobalPageAnalysis

_results: dict[tuple[str, str, int], GlobalPageAnalysis] = {}


def store(
    job_id: str, pair_id: str, page_number: int,
    analysis: GlobalPageAnalysis,
) -> None:
    _results[(job_id, pair_id, page_number)] = analysis


def get(
    job_id: str, pair_id: str, page_number: int,
) -> GlobalPageAnalysis | None:
    return _results.get((job_id, pair_id, page_number))
