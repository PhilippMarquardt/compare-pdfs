import type { GlobalPageAnalysis, JobMetadata, PageAnalysis, SectionPageAnalysisResult } from '../types/job'

// Deployment note: after changing API_BASE, run `npm run build` in `frontend/`
// and copy the built frontend folder into `compare-pdfs` before `git add/commit`.
const API_BASE =
  (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env
    ?.VITE_API_BASE_URL ?? '/api'

export async function createJob(
  referenceFiles: File[],
  testFiles: File[],
  reportType: string,
): Promise<JobMetadata> {
  const form = new FormData()
  referenceFiles.forEach((f) => form.append('reference_files', f))
  testFiles.forEach((f) => form.append('test_files', f))
  form.append('report_type', reportType)

  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    throw new Error(`Create job failed: ${res.status}`)
  }
  return res.json()
}

export async function getJob(jobId: string): Promise<JobMetadata> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`)
  if (!res.ok) {
    throw new Error(`Get job failed: ${res.status}`)
  }
  return res.json()
}

export async function listJobs(): Promise<JobMetadata[]> {
  const res = await fetch(`${API_BASE}/api/jobs`)
  if (!res.ok) {
    throw new Error(`List jobs failed: ${res.status}`)
  }
  return res.json()
}

export async function startComparison(jobId: string, mode: 'paired' | 'single' | 'raw' | 'elements' = 'paired'): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/compare?mode=${mode}`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Start comparison failed: ${res.status}`)
  }
}

export async function getPageSections(
  jobId: string,
  pairId: string,
  page: number,
  category: 'reference' | 'test',
): Promise<PageAnalysis | null> {
  const res = await fetch(
    `${API_BASE}/api/jobs/${jobId}/pairs/${pairId}/sections?page=${page}&category=${category}`,
  )
  if (!res.ok) {
    throw new Error(`Get sections failed: ${res.status}`)
  }
  return res.json()
}

export async function startSectionAnalysis(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/section-analyze`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Start section analysis failed: ${res.status}`)
  }
}

export async function getSectionAnalysisResults(
  jobId: string,
  pairId: string,
  page: number,
): Promise<SectionPageAnalysisResult | null> {
  const res = await fetch(
    `${API_BASE}/api/jobs/${jobId}/pairs/${pairId}/section-results?page=${page}`,
  )
  if (!res.ok) {
    throw new Error(`Get section results failed: ${res.status}`)
  }
  return res.json()
}

export async function startGlobalAnalysis(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/global-analyze`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Start global analysis failed: ${res.status}`)
  }
}

export async function getGlobalAnalysis(
  jobId: string,
  pairId: string,
  page: number,
): Promise<GlobalPageAnalysis | null> {
  const res = await fetch(
    `${API_BASE}/api/jobs/${jobId}/pairs/${pairId}/global?page=${page}`,
  )
  if (!res.ok) {
    throw new Error(`Get global analysis failed: ${res.status}`)
  }
  return res.json()
}

export async function getSectionInstructions(
  sectionName: string,
): Promise<{ instructions: string; matched_name: string | null }> {
  const res = await fetch(
    `${API_BASE}/api/section-instructions/${encodeURIComponent(sectionName)}`,
  )
  if (!res.ok) {
    throw new Error(`Get section instructions failed: ${res.status}`)
  }
  return res.json()
}

export async function saveSectionInstructions(
  sectionName: string,
  instructions: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/section-instructions/${encodeURIComponent(sectionName)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instructions }),
    },
  )
  if (!res.ok) {
    throw new Error(`Save section instructions failed: ${res.status}`)
  }
}

export async function deleteSectionInstructions(
  sectionName: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/section-instructions/${encodeURIComponent(sectionName)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) {
    throw new Error(`Delete section instructions failed: ${res.status}`)
  }
}

export async function sendSectionChat(
  jobId: string,
  pairId: string,
  sectionName: string,
  page: number,
  message: string,
): Promise<{ response: string }> {
  const res = await fetch(
    `${API_BASE}/api/jobs/${jobId}/pairs/${pairId}/section-chat`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_name: sectionName, page, message }),
    },
  )
  if (!res.ok) {
    throw new Error(`Section chat failed: ${res.status}`)
  }
  return res.json()
}

export async function getSectionChatContext(
  jobId: string,
  pairId: string,
  sectionName: string,
  page: number,
): Promise<{
  reference_image_data_url: string | null
  test_image_data_url: string | null
  reference_text_excerpt: string
  test_text_excerpt: string
}> {
  const qs = new URLSearchParams({
    section_name: sectionName,
    page: String(page),
  })
  const res = await fetch(
    `${API_BASE}/api/jobs/${jobId}/pairs/${pairId}/section-chat-context?${qs.toString()}`,
  )
  if (!res.ok) {
    throw new Error(`Get section chat context failed: ${res.status}`)
  }
  return res.json()
}

export async function getGeneralInstructions(): Promise<{ section_generic: string; global_template: string }> {
  const res = await fetch(`${API_BASE}/api/instructions/general`)
  if (!res.ok) {
    throw new Error(`Get general instructions failed: ${res.status}`)
  }
  return res.json()
}

export async function saveGeneralInstructions(
  sectionGeneric: string,
  globalTemplate: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/instructions/general`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      section_generic: sectionGeneric,
      global_template: globalTemplate,
    }),
  })
  if (!res.ok) {
    throw new Error(`Save general instructions failed: ${res.status}`)
  }
}

export function getPdfUrl(
  jobId: string,
  category: 'reference' | 'test',
  filename: string,
): string {
  return `${API_BASE}/api/jobs/${jobId}/files/${category}/${encodeURIComponent(filename)}`
}
