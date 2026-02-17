import { useCallback, useEffect, useState } from 'react'
import { Link, createFileRoute } from '@tanstack/react-router'
import { NewComparisonModal } from '../components/NewComparisonModal'
import { GeneralInstructionsModal } from '../components/GeneralInstructionsModal'
import { listJobs } from '../lib/api'
import { REPORT_TYPE_LABELS, type AnalysisStatus, type JobMetadata } from '../types/job'

export const Route = createFileRoute('/')({
  component: HomeComponent,
})

const ANALYSIS_STATUS_STYLES: Record<AnalysisStatus, string> = {
  idle: 'bg-slate-100 text-slate-600',
  running: 'bg-blue-100 text-blue-700',
  done: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

function AnalysisStatusPill({ value }: { value: AnalysisStatus }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${ANALYSIS_STATUS_STYLES[value]}`}>
      {value}
    </span>
  )
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function HomeComponent() {
  const [modalOpen, setModalOpen] = useState(false)
  const [instructionsOpen, setInstructionsOpen] = useState(false)
  const [jobs, setJobs] = useState<JobMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadJobs = useCallback(async () => {
    try {
      setError(null)
      const rows = await listJobs()
      setJobs(rows)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load runs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadJobs()
    const interval = setInterval(loadJobs, 5000)
    return () => clearInterval(interval)
  }, [loadJobs])

  const hasRuns = jobs.length > 0

  return (
    <div className="flex-1 overflow-y-auto bg-white">
      <div className="mx-auto w-full max-w-7xl px-6 py-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Comparison Runs</h1>
            <p className="mt-1 text-sm text-slate-500">
              Start new comparisons, revisit previous runs, and maintain shared analysis instructions.
            </p>
          </div>
          <div className="flex items-center gap-3 sm:justify-end">
            <button
              onClick={() => setInstructionsOpen(true)}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
            >
              Edit General Instructions
            </button>
            <button
              onClick={() => setModalOpen(true)}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              New Comparison
            </button>
          </div>
        </header>

        {error && (
          <p className="mt-4 text-sm text-red-600">{error}</p>
        )}

        <section className="mt-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Run History</h2>
            <div className="text-xs text-slate-500">
              {loading ? 'Refreshing...' : `${jobs.length} run${jobs.length === 1 ? '' : 's'}`}
            </div>
          </div>

          {!loading && !hasRuns && !error && (
            <div className="py-10 text-center text-sm text-slate-600">
              No comparisons have been started yet.
            </div>
          )}

          {hasRuns && (
            <div className="overflow-x-auto border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3 font-medium">Created</th>
                    <th className="px-5 py-3 font-medium">Job</th>
                    <th className="px-5 py-3 font-medium">Report</th>
                    <th className="px-5 py-3 font-medium">Pairs</th>
                    <th className="px-5 py-3 font-medium">Unmatched</th>
                    <th className="px-5 py-3 font-medium">Section Detect</th>
                    <th className="px-5 py-3 font-medium">Global</th>
                    <th className="px-5 py-3 font-medium">Section</th>
                    <th className="px-5 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {jobs.map((job) => (
                    <tr key={job.job_id} className="text-sm text-slate-700">
                      <td className="px-5 py-3 whitespace-nowrap">{formatDate(job.created_at)}</td>
                      <td className="px-5 py-3 font-mono text-xs text-slate-600" title={job.job_id}>{job.job_id}</td>
                      <td className="px-5 py-3 whitespace-nowrap">{REPORT_TYPE_LABELS[job.report_type] ?? job.report_type}</td>
                      <td className="px-5 py-3 whitespace-nowrap">{job.pairs.length}</td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        R {job.unmatched_reference.length} / T {job.unmatched_test.length}
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap"><AnalysisStatusPill value={job.analysis_status} /></td>
                      <td className="px-5 py-3 whitespace-nowrap"><AnalysisStatusPill value={job.global_analysis_status} /></td>
                      <td className="px-5 py-3 whitespace-nowrap"><AnalysisStatusPill value={job.section_analysis_status} /></td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        <Link
                          to="/compare/$jobId"
                          params={{ jobId: job.job_id }}
                          className="inline-flex rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
      <NewComparisonModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
      <GeneralInstructionsModal
        isOpen={instructionsOpen}
        onClose={() => setInstructionsOpen(false)}
      />
    </div>
  )
}
