import { useState, useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { UploadDropzone } from './UploadDropzone'
import { createJob } from '../lib/api'
import { type ReportType, REPORT_TYPE_LABELS } from '../types/job'

interface NewComparisonModalProps {
  isOpen: boolean
  onClose: () => void
}

const reportTypes = Object.entries(REPORT_TYPE_LABELS) as [
  ReportType,
  string,
][]

export function NewComparisonModal({
  isOpen,
  onClose,
}: NewComparisonModalProps) {
  const navigate = useNavigate()
  const [referenceFiles, setReferenceFiles] = useState<File[]>([])
  const [testFiles, setTestFiles] = useState<File[]>([])
  const [reportType, setReportType] = useState<ReportType>('none')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = useCallback(() => {
    setReferenceFiles([])
    setTestFiles([])
    setReportType('none')
    setError(null)
  }, [])

  const handleClose = useCallback(() => {
    reset()
    onClose()
  }, [reset, onClose])

  const handleSubmit = useCallback(async () => {
    if (referenceFiles.length === 0 || testFiles.length === 0) return
    setIsSubmitting(true)
    setError(null)
    try {
      const job = await createJob(referenceFiles, testFiles, reportType)
      reset()
      onClose()
      navigate({ to: '/compare/$jobId', params: { jobId: job.job_id } })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setIsSubmitting(false)
    }
  }, [referenceFiles, testFiles, reportType, navigate, onClose, reset])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
      />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          New Comparison
        </h2>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <UploadDropzone
            label="Reference PDFs"
            files={referenceFiles}
            onFilesChange={setReferenceFiles}
          />
          <UploadDropzone
            label="Test PDFs"
            files={testFiles}
            onFilesChange={setTestFiles}
          />
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Report Type
          </label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value as ReportType)}
            className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {reportTypes.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <p className="text-sm text-red-600 mb-4">{error}</p>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={
              isSubmitting ||
              referenceFiles.length === 0 ||
              testFiles.length === 0
            }
            className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Uploading...' : 'Start Comparison'}
          </button>
        </div>
      </div>
    </div>
  )
}
