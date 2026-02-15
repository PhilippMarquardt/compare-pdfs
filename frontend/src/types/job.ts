export type PairStatus =
  | 'pending'
  | 'running'
  | 'ok'
  | 'needs_attention'
  | 'broken'

export type ReportType =
  | 'none'
  | 'multi_asset_mandatsreporting'
  | 'equity_report'
  | 'fixed_income_report'

export const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  none: 'None (generic)',
  multi_asset_mandatsreporting: 'Multi Asset Mandatsreporting',
  equity_report: 'Equity Report',
  fixed_income_report: 'Fixed Income Report',
}

export interface PdfPair {
  pair_id: string
  filename: string
  reference_path: string
  test_path: string
  status: PairStatus
  page_count_reference: number
  page_count_test: number
}

export type AnalysisStatus = 'idle' | 'running' | 'done' | 'failed'

export interface Section {
  name: string
  content_type: string
  element_ids: string[]
  bbox: [number, number, number, number]
}

export interface PageAnalysis {
  page_number: number
  page_width: number
  page_height: number
  sections: Section[]
}

export type CheckStatus = 'ok' | 'maybe' | 'issue'

export interface GlobalCheckResult {
  check_name: string
  status: CheckStatus
  explanation: string
}

export interface GlobalPageAnalysis {
  page_number: number
  checks: GlobalCheckResult[]
}

export interface SectionCheck {
  check_name: string
  status: CheckStatus
  explanation: string
}

export interface SectionCheckResult {
  section_name: string
  checks: SectionCheck[]
  matched_instructions: boolean
}

export interface SectionPageAnalysisResult {
  page_number: number
  results: SectionCheckResult[]
}

export interface JobMetadata {
  job_id: string
  report_type: ReportType
  pairs: PdfPair[]
  unmatched_reference: string[]
  unmatched_test: string[]
  created_at: string
  analysis_status: AnalysisStatus
  analysis_progress: number
  analysis_total: number
  analysis_error: string | null
  global_analysis_status: AnalysisStatus
  global_analysis_progress: number
  global_analysis_total: number
  section_analysis_status: AnalysisStatus
  section_analysis_progress: number
  section_analysis_total: number
}
