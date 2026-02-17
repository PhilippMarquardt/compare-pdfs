import { useState } from 'react'
import type {
  GlobalPageAnalysis,
  CheckStatus,
  AnalysisStatus,
  SectionPageAnalysisResult,
  SectionCheckResult,
} from '../types/job'

const STATUS_DOT: Record<CheckStatus, string> = {
  ok: 'bg-green-500',
  maybe: 'bg-yellow-400',
  issue: 'bg-red-500',
}

const STATUS_BORDER: Record<CheckStatus, string> = {
  ok: 'border-l-green-500',
  maybe: 'border-l-yellow-400',
  issue: 'border-l-red-500',
}

const STATUS_BADGE: Record<CheckStatus, string> = {
  ok: 'bg-green-100 text-green-700',
  maybe: 'bg-yellow-100 text-yellow-700',
  issue: 'bg-red-100 text-red-700',
}

const STATUS_LABELS: Record<CheckStatus, string> = {
  ok: 'OK',
  maybe: 'Review',
  issue: 'Issue',
}

function worstStatus(result: SectionCheckResult): CheckStatus {
  let worst: CheckStatus = 'ok'
  for (const c of result.checks) {
    if (c.status === 'issue') return 'issue'
    if (c.status === 'maybe') worst = 'maybe'
  }
  return worst
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
  const [expandedSection, setExpandedSection] = useState<SectionCheckResult | null>(null)

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
        {/* Global Checks */}
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
                    width: globalTotal
                      ? `${(globalProgress / globalTotal) * 100}%`
                      : '0%',
                  }}
                />
              </div>
            </div>
          )}

          {globalStatus === 'idle' && (
            <p className="text-xs text-gray-400">Not started</p>
          )}

          {globalAnalysis && globalAnalysis.checks.length > 0 && (
            <div className="space-y-2">
              {globalAnalysis.checks.map((check) => (
                <div
                  key={check.check_name}
                  className={`rounded-lg border border-gray-200 border-l-4 ${STATUS_BORDER[check.status]} bg-white px-3 py-2.5 shadow-sm`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-gray-800">
                      {check.check_name}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${STATUS_BADGE[check.status]}`}
                    >
                      {STATUS_LABELS[check.status]}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                    {check.explanation}
                  </p>
                </div>
              ))}
            </div>
          )}

          {globalStatus === 'done' && !globalAnalysis && (
            <p className="text-xs text-gray-400">No results for this page</p>
          )}
        </div>

        {/* Per-Section Analysis */}
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
            <div className="space-y-2">
              {sections.map((s, i) => {
                const result = resultsByName.get(s.name)
                const border = result
                  ? STATUS_BORDER[worstStatus(result)]
                  : 'border-l-gray-300'

                return (
                  <div
                    key={`${s.name}-${i}`}
                    onClick={result && result.checks.length > 0 ? () => setExpandedSection(result) : undefined}
                    className={`rounded-lg border border-gray-200 border-l-4 ${border} bg-white px-3 py-2 shadow-sm ${
                      result && result.checks.length > 0 ? 'cursor-pointer hover:shadow-md hover:border-gray-300 transition-all' : ''
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-800 mb-1">{s.name}</p>
                    {result && result.checks.length > 0 ? (
                      <div className="space-y-0.5">
                        {result.checks.map((check, ci) => (
                          <div key={ci} className="flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[check.status]}`} />
                            <span className="text-xs text-gray-600 truncate">{check.check_name}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[11px] text-gray-400">{s.content_type}</p>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-gray-400">Run section detection first</p>
          )}
        </div>
      </div>

      {/* Section detail modal */}
      {expandedSection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setExpandedSection(null)}
          />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-base font-semibold text-gray-900">
                {expandedSection.section_name}
              </p>
              <button
                onClick={() => setExpandedSection(null)}
                className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 1l12 12M13 1L1 13" />
                </svg>
              </button>
            </div>
            <div className="space-y-3">
              {expandedSection.checks.map((check, ci) => (
                <div
                  key={ci}
                  className={`rounded-lg border border-gray-200 border-l-4 ${STATUS_BORDER[check.status]} px-3 py-2.5`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-800">
                      {check.check_name}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${STATUS_BADGE[check.status]}`}
                    >
                      {STATUS_LABELS[check.status]}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">
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
