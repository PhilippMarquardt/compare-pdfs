import { useState, useCallback, useEffect } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import {
  getJob, getPdfUrl, startComparison, getPageSections,
  startGlobalAnalysis, getGlobalAnalysis,
  startSectionAnalysis, getSectionAnalysisResults,
} from '../../lib/api'
import { ComparisonSidebar } from '../../components/ComparisonSidebar'
import { PageNavBar } from '../../components/PageNavBar'
import { SyncedPdfViewer } from '../../components/SyncedPdfViewer'
import { AnalysisPanel } from '../../components/AnalysisPanel'
import { ResizeHandle } from '../../components/ResizeHandle'
import { SectionChatModal } from '../../components/SectionChatModal'
import type { PageAnalysis, GlobalPageAnalysis, SectionPageAnalysisResult, Section } from '../../types/job'

export const Route = createFileRoute('/compare/$jobId')({
  loader: ({ params }) => getJob(params.jobId),
  component: CompareComponent,
})

const MIN_ZOOM = 0.5
const MAX_ZOOM = 5

function CompareComponent() {
  const loaderData = Route.useLoaderData()
  const [job, setJob] = useState(loaderData)
  const [selectedPairIndex, setSelectedPairIndex] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [refSections, setRefSections] = useState<PageAnalysis | null>(null)
  const [testSections, setTestSections] = useState<PageAnalysis | null>(null)
  const [analysisMode, setAnalysisMode] = useState<'paired' | 'single' | 'raw' | 'elements'>('paired')
  const [globalAnalysis, setGlobalAnalysis] = useState<GlobalPageAnalysis | null>(null)
  const [sectionResults, setSectionResults] = useState<SectionPageAnalysisResult | null>(null)
  const [sidebarWidth, setSidebarWidth] = useState(200)
  const [panelWidth, setPanelWidth] = useState(420)
  const [chatSection, setChatSection] = useState<Section | null>(null)

  const selectedPair = job.pairs[selectedPairIndex]

  const handleSidebarResize = useCallback((delta: number) => {
    setSidebarWidth((w) => Math.min(500, Math.max(200, w + delta)))
  }, [])

  const handlePanelResize = useCallback((delta: number) => {
    setPanelWidth((w) => Math.min(500, Math.max(200, w + delta)))
  }, [])

  const handleSelectPair = useCallback((index: number) => {
    setSelectedPairIndex(index)
    setCurrentPage(1)
    setZoom(1)
    setRefSections(null)
    setTestSections(null)
    setGlobalAnalysis(null)
    setSectionResults(null)
  }, [])

  const handlePageLoaded = useCallback((numPages: number) => {
    setTotalPages(numPages)
  }, [])

  const handlePrev = useCallback(() => {
    setCurrentPage((p) => Math.max(1, p - 1))
  }, [])

  const handleNext = useCallback(() => {
    setCurrentPage((p) => Math.min(totalPages, p + 1))
  }, [totalPages])

  const handleZoomIn = useCallback(() => {
    setZoom((z) => Math.min(z * 1.25, MAX_ZOOM))
  }, [])

  const handleZoomOut = useCallback(() => {
    setZoom((z) => Math.max(z * 0.8, MIN_ZOOM))
  }, [])

  const handleZoomReset = useCallback(() => {
    setZoom(1)
  }, [])

  const handleZoomChange = useCallback((newZoom: number) => {
    setZoom(newZoom)
  }, [])

  const handleStartComparison = useCallback(async () => {
    await startComparison(job.job_id, analysisMode)
    setJob((j) => ({ ...j, analysis_status: 'running' as const, analysis_progress: 0 }))
  }, [job.job_id, analysisMode])

  const handleStartGlobal = useCallback(async () => {
    await startGlobalAnalysis(job.job_id)
    setJob((j) => ({ ...j, global_analysis_status: 'running' as const, global_analysis_progress: 0 }))
  }, [job.job_id])

  const handleSectionClick = useCallback((section: Section) => {
    setChatSection(section)
  }, [])

  const handleStartSectionAnalysis = useCallback(async () => {
    await startSectionAnalysis(job.job_id)
    setJob((j) => ({ ...j, section_analysis_status: 'running' as const, section_analysis_progress: 0 }))
  }, [job.job_id])

  // Poll job status while any analysis is running
  useEffect(() => {
    const anyRunning = job.analysis_status === 'running'
      || job.global_analysis_status === 'running'
      || job.section_analysis_status === 'running'
    if (!anyRunning) return
    const interval = setInterval(async () => {
      try {
        const updated = await getJob(job.job_id)
        setJob(updated)
      } catch {
        // ignore polling errors
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [job.analysis_status, job.global_analysis_status, job.section_analysis_status, job.job_id])

  // Fetch sections for current page
  useEffect(() => {
    if (job.analysis_status === 'idle' || !selectedPair) {
      setRefSections(null)
      setTestSections(null)
      return
    }
    let cancelled = false
    async function fetchSections() {
      try {
        const [ref, test] = await Promise.all([
          getPageSections(job.job_id, selectedPair.pair_id, currentPage, 'reference'),
          getPageSections(job.job_id, selectedPair.pair_id, currentPage, 'test'),
        ])
        if (!cancelled) {
          setRefSections(ref)
          setTestSections(test)
        }
      } catch {
        // sections not ready yet
      }
    }
    fetchSections()
    return () => { cancelled = true }
  }, [job.analysis_status, job.analysis_progress, job.job_id, selectedPair?.pair_id, currentPage])

  // Fetch global analysis for current page
  useEffect(() => {
    if (job.global_analysis_status === 'idle' || !selectedPair) {
      setGlobalAnalysis(null)
      return
    }
    let cancelled = false
    async function fetchGlobal() {
      try {
        const result = await getGlobalAnalysis(job.job_id, selectedPair.pair_id, currentPage)
        if (!cancelled) setGlobalAnalysis(result)
      } catch {
        // not ready yet
      }
    }
    fetchGlobal()
    return () => { cancelled = true }
  }, [job.global_analysis_status, job.global_analysis_progress, job.job_id, selectedPair?.pair_id, currentPage])

  // Fetch section analysis results for current page
  useEffect(() => {
    if (job.section_analysis_status === 'idle' || !selectedPair) {
      setSectionResults(null)
      return
    }
    let cancelled = false
    async function fetchResults() {
      try {
        const result = await getSectionAnalysisResults(job.job_id, selectedPair.pair_id, currentPage)
        if (!cancelled) setSectionResults(result)
      } catch {
        // not ready yet
      }
    }
    fetchResults()
    return () => { cancelled = true }
  }, [job.section_analysis_status, job.section_analysis_progress, job.job_id, selectedPair?.pair_id, currentPage])

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowLeft') {
        setCurrentPage((p) => Math.max(1, p - 1))
      } else if (e.key === 'ArrowRight') {
        setCurrentPage((p) => Math.min(totalPages, p + 1))
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [totalPages])

  if (!selectedPair) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        No pairs found
      </div>
    )
  }

  const referenceUrl = getPdfUrl(job.job_id, 'reference', selectedPair.filename)
  const testUrl = getPdfUrl(job.job_id, 'test', selectedPair.filename)

  const sectionNames = refSections
    ? refSections.sections.map((s) => ({ name: s.name, content_type: s.content_type }))
    : []

  return (
    <>
    <div className="flex-1 flex min-h-0">
      <div style={{ width: sidebarWidth }} className="shrink-0">
        <ComparisonSidebar
          job={job}
          selectedPairIndex={selectedPairIndex}
          onSelectPair={handleSelectPair}
        />
      </div>
      <ResizeHandle onResize={handleSidebarResize} />
      <div style={{ width: panelWidth }} className="shrink-0">
        <AnalysisPanel
          globalAnalysis={globalAnalysis}
          globalStatus={job.global_analysis_status}
          globalProgress={job.global_analysis_progress}
          globalTotal={job.global_analysis_total}
          onStartGlobal={handleStartGlobal}
          sections={sectionNames}
          sectionResults={sectionResults}
          sectionAnalysisStatus={job.section_analysis_status}
          sectionAnalysisProgress={job.section_analysis_progress}
          sectionAnalysisTotal={job.section_analysis_total}
          onStartSectionAnalysis={handleStartSectionAnalysis}
          sectionDetectionDone={job.analysis_status === 'done'}
        />
      </div>
      <ResizeHandle onResize={handlePanelResize} />
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <PageNavBar
          filename={selectedPair.filename}
          currentPage={currentPage}
          totalPages={totalPages}
          zoom={zoom}
          onPrev={handlePrev}
          onNext={handleNext}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onZoomReset={handleZoomReset}
        />
        {job.analysis_status === 'idle' && (
          <div className="h-9 flex items-center gap-3 px-4 border-b border-gray-200 bg-gray-50 shrink-0">
            <div className="flex items-center gap-1 bg-gray-200 rounded p-0.5">
              <button
                onClick={() => setAnalysisMode('paired')}
                className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${analysisMode === 'paired' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                Paired
              </button>
              <button
                onClick={() => setAnalysisMode('single')}
                className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${analysisMode === 'single' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                Single
              </button>
              <button
                onClick={() => setAnalysisMode('raw')}
                className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${analysisMode === 'raw' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                Raw
              </button>
              <button
                onClick={() => setAnalysisMode('elements')}
                className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${analysisMode === 'elements' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                Elements
              </button>
            </div>
            <button
              onClick={handleStartComparison}
              className="px-3 py-1 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded"
            >
              Analyze
            </button>
          </div>
        )}
        {job.analysis_status === 'running' && (
          <div className="h-9 flex items-center gap-3 px-4 border-b border-gray-200 bg-blue-50 shrink-0">
            <span className="text-xs text-blue-700">
              Analyzing... {job.analysis_progress}/{job.analysis_total} pages
            </span>
            <div className="flex-1 h-1.5 bg-blue-100 rounded-full overflow-hidden max-w-48">
              <div
                className="h-full bg-blue-600 rounded-full transition-all"
                style={{
                  width: job.analysis_total
                    ? `${(job.analysis_progress / job.analysis_total) * 100}%`
                    : '0%',
                }}
              />
            </div>
          </div>
        )}
        {job.analysis_status === 'failed' && (
          <div className="h-9 flex items-center px-4 border-b border-gray-200 bg-red-50 shrink-0">
            <span className="text-xs text-red-700">
              Analysis failed{job.analysis_error ? `: ${job.analysis_error}` : ''}
            </span>
          </div>
        )}
        <SyncedPdfViewer
          referenceUrl={referenceUrl}
          testUrl={testUrl}
          pageNumber={currentPage}
          zoom={zoom}
          onZoomChange={handleZoomChange}
          onPageLoaded={handlePageLoaded}
          referenceSections={refSections}
          testSections={testSections}
          onSectionClick={handleSectionClick}
        />
        <div className="shrink-0" />
      </div>
    </div>
    {chatSection && selectedPair && (
      <SectionChatModal
        onClose={() => setChatSection(null)}
        sectionName={chatSection.name}
        jobId={job.job_id}
        pairId={selectedPair.pair_id}
        page={currentPage}
      />
    )}
    </>
  )
}
