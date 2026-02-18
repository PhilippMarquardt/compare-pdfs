import { useState } from 'react'
import type {
  AnalysisStatus,
  CheckStatus,
  GlobalCheckResult,
  GlobalPageAnalysis,
  SectionCheck,
  SectionCheckResult,
  SectionPageAnalysisResult,
} from '../types/job'

const PREVIEW_LENGTH = 80
const PREVIEW_ROWS = 3

const STATUS_DOT: Record<CheckStatus, string> = {
  ok: 'bg-green-500',
  maybe: 'bg-yellow-400',
  issue: 'bg-red-500',
}

const STATUS_BADGE: Record<CheckStatus, string> = {
  ok: 'bg-green-100 text-green-700',
  maybe: 'bg-yellow-100 text-yellow-700',
  issue: 'bg-red-100 text-red-700',
}

const STATUS_LABELS: Record<CheckStatus, string> = {
  ok: 'Pass',
  maybe: 'Unclear',
  issue: 'Fail',
}

const STATUS_PRIORITY: Record<CheckStatus, number> = {
  issue: 0,
  maybe: 1,
  ok: 2,
}

const CARD_INDICATOR: Record<CheckStatus, string> = {
  ok: 'bg-green-500',
  maybe: 'bg-yellow-400',
  issue: 'bg-red-500',
}

const CARD_ACCENT: Record<CheckStatus, string> = {
  ok: 'border-l-2 border-l-green-400',
  maybe: 'border-l-2 border-l-yellow-400',
  issue: 'border-l-2 border-l-red-400',
}

const RECTANGLE_CLASS =
  'h-[120px] rounded-md border border-slate-200 bg-white px-2.5 py-2.5'

type AnyCheck = GlobalCheckResult | SectionCheck

interface DetailModalState {
  title: string
  checks: AnyCheck[]
}

interface AnalysisPanelProps {
  globalAnalysis: GlobalPageAnalysis | null
  globalStatus: AnalysisStatus
  globalProgress: number
  globalTotal: number
  onStartGlobal: () => void
  sections: { name: string; content_type: string }[]
  sectionResults: SectionPageAnalysisResult | null
  sectionAnalysisStatus: AnalysisStatus
  sectionAnalysisProgress: number
  sectionAnalysisTotal: number
  onStartSectionAnalysis: () => void
  sectionDetectionDone: boolean
}

function truncateText(text: string, maxLength = PREVIEW_LENGTH): string {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1)}...`
}

function sortChecksBySeverity<T extends AnyCheck>(checks: T[]): T[] {
  return [...checks].sort((a, b) => STATUS_PRIORITY[a.status] - STATUS_PRIORITY[b.status])
}

function getAggregateStatus(checks: AnyCheck[]): CheckStatus | null {
  if (checks.some((c) => c.status === 'issue')) return 'issue'
  if (checks.some((c) => c.status === 'maybe')) return 'maybe'
  if (checks.length > 0) return 'ok'
  return null
}

export function AnalysisPanel({
  globalAnalysis,
  globalStatus,
  globalProgress,
  globalTotal,
  onStartGlobal,
  sections,
  sectionResults,
  sectionAnalysisStatus,
  sectionAnalysisProgress,
  sectionAnalysisTotal,
  onStartSectionAnalysis,
  sectionDetectionDone,
}: AnalysisPanelProps) {
  const [detailModal, setDetailModal] = useState<DetailModalState | null>(null)

  const resultsByName = new Map<string, SectionCheckResult>()
  if (sectionResults) {
    for (const r of sectionResults.results) {
      resultsByName.set(r.section_name, r)
    }
  }

  return (
    <aside className="h-full bg-white flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200">
        <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
          Analysis Overview
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Global Checks
            </p>
            {globalStatus === 'idle' && (
              <button
                onClick={onStartGlobal}
                className="px-2.5 py-1 text-[11px] font-medium text-white bg-blue-600 hover:bg-blue-700 rounded"
              >
                Run
              </button>
            )}
          </div>

          {globalStatus === 'running' && (
            <div className="mb-3">
              <span className="text-[11px] text-blue-600">
                Analyzing... {globalProgress}/{globalTotal}
              </span>
              <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden mt-1">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{
                    width: globalTotal ? `${(globalProgress / globalTotal) * 100}%` : '0%',
                  }}
                />
              </div>
            </div>
          )}

          {globalStatus === 'idle' && (
            <p className="text-xs text-gray-400">Not started</p>
          )}

          {globalAnalysis && globalAnalysis.checks.length > 0 && (
            (() => {
              const sortedChecks = sortChecksBySeverity(globalAnalysis.checks)
              const previewChecks = sortedChecks.slice(0, PREVIEW_ROWS)
              const hiddenCount = sortedChecks.length - previewChecks.length
              const aggregate = getAggregateStatus(sortedChecks)
              return (
                <button
                  type="button"
                  onClick={() => setDetailModal({
                    title: 'Global Checks',
                    checks: sortedChecks,
                  })}
                  className={`${RECTANGLE_CLASS} w-full text-left hover:border-slate-300 transition-colors ${aggregate ? CARD_ACCENT[aggregate] : ''}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">Page Checklist</p>
                    <span
                      className={`h-2.5 w-2.5 rounded-full shrink-0 ${aggregate ? CARD_INDICATOR[aggregate] : 'bg-slate-300'}`}
                    />
                  </div>
                  <ul className="mt-1.5 space-y-1 overflow-hidden">
                    {previewChecks.map((check, i) => (
                      <li key={`${check.check_name}-${i}`} className="flex items-start gap-1.5 min-w-0">
                        <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${STATUS_DOT[check.status]}`} />
                        <span className="text-[11px] leading-4 text-slate-700 truncate">
                          {truncateText(check.check_name)}
                        </span>
                      </li>
                    ))}
                    {hiddenCount > 0 && (
                      <li className="text-[11px] leading-4 text-slate-500">
                        +{hiddenCount} more
                      </li>
                    )}
                  </ul>
                </button>
              )
            })()
          )}

          {globalStatus === 'done' && !globalAnalysis && (
            <p className="text-xs text-gray-400">No results for this page</p>
          )}
        </div>

        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Section Analysis
            </p>
            {sectionDetectionDone && sectionAnalysisStatus === 'idle' && (
              <button
                onClick={onStartSectionAnalysis}
                className="px-2.5 py-1 text-[11px] font-medium text-white bg-blue-600 hover:bg-blue-700 rounded"
              >
                Run
              </button>
            )}
          </div>

          {sectionAnalysisStatus === 'running' && (
            <div className="mb-3">
              <span className="text-[11px] text-blue-600">
                Analyzing... {sectionAnalysisProgress}/{sectionAnalysisTotal}
              </span>
              <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden mt-1">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{
                    width: sectionAnalysisTotal
                      ? `${(sectionAnalysisProgress / sectionAnalysisTotal) * 100}%`
                      : '0%',
                  }}
                />
              </div>
            </div>
          )}

          {sections.length > 0 ? (
            <div
              className="grid gap-2"
              style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}
            >
              {sections.map((s, i) => {
                const result = resultsByName.get(s.name)
                const hasChecks = !!result && result.checks.length > 0
                const sortedChecks = hasChecks ? sortChecksBySeverity(result.checks) : []
                const previewChecks = sortedChecks.slice(0, PREVIEW_ROWS)
                const hiddenCount = sortedChecks.length - previewChecks.length
                const aggregate = getAggregateStatus(sortedChecks)
                return (
                  <button
                    key={`${s.name}-${i}`}
                    type="button"
                    onClick={hasChecks ? () => setDetailModal({
                      title: s.name,
                      checks: sortedChecks,
                    }) : undefined}
                    className={`${RECTANGLE_CLASS} w-full text-left ${aggregate ? CARD_ACCENT[aggregate] : ''} ${hasChecks ? 'cursor-pointer hover:border-slate-300 transition-colors' : 'cursor-default'}`}
                    aria-disabled={!hasChecks}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900 truncate" title={s.name}>
                        {s.name}
                      </p>
                      <span
                        className={`h-2.5 w-2.5 rounded-full shrink-0 ${aggregate ? CARD_INDICATOR[aggregate] : 'bg-slate-300'}`}
                      />
                    </div>
                    {hasChecks ? (
                      <ul className="mt-1.5 space-y-1 overflow-hidden">
                        {previewChecks.map((check, ci) => (
                          <li key={ci} className="flex items-start gap-1.5 min-w-0">
                            <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${STATUS_DOT[check.status]}`} />
                            <span className="text-[11px] leading-4 text-slate-700 truncate">
                              {truncateText(check.check_name)}
                            </span>
                          </li>
                        ))}
                        {hiddenCount > 0 && (
                          <li className="text-[11px] leading-4 text-slate-500">
                            +{hiddenCount} more
                          </li>
                        )}
                      </ul>
                    ) : (
                      <div className="mt-1.5 text-[11px] leading-4 text-slate-400">
                        <p>{s.content_type}</p>
                        <p>No section checks yet</p>
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-gray-400">Run section detection first</p>
          )}
        </div>
      </div>

      {detailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setDetailModal(null)}
          />
          <div className="relative w-full max-w-2xl max-h-[80vh] mx-4 bg-white rounded-md border border-slate-200 shadow-xl p-5 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <p className="text-base font-semibold text-slate-900 truncate" title={detailModal.title}>
                {detailModal.title}
              </p>
              <button
                onClick={() => setDetailModal(null)}
                className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 1l12 12M13 1L1 13" />
                </svg>
              </button>
            </div>

            <div className="space-y-3 overflow-y-auto pr-1">
              {sortChecksBySeverity(detailModal.checks).map((check, ci) => (
                <div key={ci} className="rounded-md border border-slate-200 px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${STATUS_DOT[check.status]}`} />
                    <span className="text-sm font-semibold text-slate-900">
                      {check.check_name}
                    </span>
                    <span
                      className={`ml-auto text-[10px] font-semibold px-2 py-0.5 rounded shrink-0 ${STATUS_BADGE[check.status]}`}
                    >
                      {STATUS_LABELS[check.status]}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 mt-2 leading-relaxed whitespace-pre-wrap">
                    {check.explanation}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
