from enum import Enum

from pydantic import BaseModel


class ReportType(str, Enum):
    none = "none"
    multi_asset_mandatsreporting = "multi_asset_mandatsreporting"
    equity_report = "equity_report"
    fixed_income_report = "fixed_income_report"


class PairStatus(str, Enum):
    pending = "pending"
    running = "running"
    ok = "ok"
    needs_attention = "needs_attention"
    broken = "broken"


class AnalysisStatus(str, Enum):
    idle = "idle"
    running = "running"
    done = "done"
    failed = "failed"


class PdfPair(BaseModel):
    pair_id: str
    filename: str
    reference_path: str
    test_path: str
    status: PairStatus = PairStatus.pending
    page_count_reference: int
    page_count_test: int


class CheckStatus(str, Enum):
    ok = "ok"
    maybe = "maybe"
    issue = "issue"


class GlobalCheckResult(BaseModel):
    check_name: str
    status: CheckStatus
    explanation: str


class GlobalPageAnalysis(BaseModel):
    page_number: int
    checks: list[GlobalCheckResult]


class SectionCheck(BaseModel):
    check_name: str
    status: CheckStatus
    explanation: str


class SectionCheckResult(BaseModel):
    section_name: str
    checks: list[SectionCheck]
    matched_instructions: bool


class SectionPageAnalysisResult(BaseModel):
    page_number: int
    results: list[SectionCheckResult]


class Section(BaseModel):
    name: str
    content_type: str
    element_ids: list[str]
    bbox: list[float]


class PageAnalysis(BaseModel):
    page_number: int
    page_width: float
    page_height: float
    sections: list[Section]


class JobMetadata(BaseModel):
    job_id: str
    report_type: str
    pairs: list[PdfPair]
    unmatched_reference: list[str] = []
    unmatched_test: list[str] = []
    created_at: str
    analysis_status: AnalysisStatus = AnalysisStatus.idle
    analysis_progress: int = 0
    analysis_total: int = 0
    analysis_error: str | None = None
    global_analysis_status: AnalysisStatus = AnalysisStatus.idle
    global_analysis_progress: int = 0
    global_analysis_total: int = 0
    section_analysis_status: AnalysisStatus = AnalysisStatus.idle
    section_analysis_progress: int = 0
    section_analysis_total: int = 0
