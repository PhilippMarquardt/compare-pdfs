import { useState, useEffect, useCallback } from 'react'
import {
  getSectionChatContext,
  getSectionInstructions,
  saveSectionInstructions,
  sendSectionChat,
} from '../lib/api'

interface SectionChatModalProps {
  onClose: () => void
  sectionName: string
  jobId: string
  pairId: string
  page: number
}

interface SectionChatContext {
  reference_image_data_url: string | null
  test_image_data_url: string | null
}

export function SectionChatModal({
  onClose,
  sectionName,
  jobId,
  pairId,
  page,
}: SectionChatModalProps) {
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [contextData, setContextData] = useState<SectionChatContext | null>(null)
  const [loadingContext, setLoadingContext] = useState(true)
  const [contextError, setContextError] = useState<string | null>(null)

  const [instructionText, setInstructionText] = useState('')
  const [matchedName, setMatchedName] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [loadingInstructions, setLoadingInstructions] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoadingContext(true)
    setContextError(null)
    getSectionChatContext(jobId, pairId, sectionName, page)
      .then((result) => {
        if (!cancelled) {
          setContextData(result)
          setLoadingContext(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setContextData(null)
          setContextError(e instanceof Error ? e.message : 'Failed to load section context')
          setLoadingContext(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [jobId, pairId, sectionName, page])

  useEffect(() => {
    let cancelled = false
    setLoadingInstructions(true)
    getSectionInstructions(sectionName)
      .then((result) => {
        if (!cancelled) {
          setInstructionText(result.instructions)
          setMatchedName(result.matched_name)
          setLoadingInstructions(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setInstructionText('')
          setMatchedName(null)
          setLoadingInstructions(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [sectionName])

  const handleSend = useCallback(async () => {
    if (!message.trim() || loading) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const result = await sendSectionChat(jobId, pairId, sectionName, page, message)
      setResponse(result.response)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat request failed')
    } finally {
      setLoading(false)
    }
  }, [message, loading, jobId, pairId, sectionName, page])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      await saveSectionInstructions(sectionName, instructionText)
      setMatchedName(sectionName)
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }, [sectionName, instructionText])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-6xl mx-4 h-[78vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 shrink-0">
          <h2 className="text-sm font-semibold text-gray-900">{sectionName}</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M1 1l12 12M13 1L1 13" />
            </svg>
          </button>
        </div>

        <div className="shrink-0 border-b border-gray-200 p-3">
          {loadingContext ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="h-44 rounded-md border border-gray-200 bg-gray-50 animate-pulse" />
              <div className="h-44 rounded-md border border-gray-200 bg-gray-50 animate-pulse" />
            </div>
          ) : contextError ? (
            <p className="text-sm text-red-600">{contextError}</p>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-md border border-gray-200 p-2 min-w-0">
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Old / Reference
                </p>
                <div className="h-36 bg-gray-50 border border-gray-100 rounded flex items-center justify-center overflow-hidden">
                  {contextData?.reference_image_data_url ? (
                    <img
                      src={contextData.reference_image_data_url}
                      alt="Reference section crop"
                      className="max-h-full max-w-full object-contain"
                    />
                  ) : (
                    <p className="text-xs text-gray-400">No reference crop available</p>
                  )}
                </div>
              </div>

              <div className="rounded-md border border-gray-200 p-2 min-w-0">
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  New / Test
                </p>
                <div className="h-36 bg-gray-50 border border-gray-100 rounded flex items-center justify-center overflow-hidden">
                  {contextData?.test_image_data_url ? (
                    <img
                      src={contextData.test_image_data_url}
                      alt="Test section crop"
                      className="max-h-full max-w-full object-contain"
                    />
                  ) : (
                    <p className="text-xs text-gray-400">No test crop available</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-1 min-h-0">
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 overflow-y-auto p-4">
              {loading && (
                <div className="flex items-center gap-2 text-sm text-blue-600">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Thinking...
                </div>
              )}
              {error && <p className="text-sm text-red-600">{error}</p>}
              {response && !loading && (
                <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                  {response}
                </div>
              )}
              {!response && !loading && !error && (
                <p className="text-sm text-gray-400">
                  Ask a question about this section...
                </p>
              )}
            </div>

            <div className="flex gap-2 p-3 border-t border-gray-200 shrink-0">
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-400"
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={loading || !message.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send
              </button>
            </div>
          </div>

          <div className="w-72 flex flex-col border-l border-gray-200 p-4 shrink-0">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Section Instructions
            </p>
            {matchedName && (
              <p className="text-[10px] text-blue-500 mb-1">
                Matched: {matchedName}
              </p>
            )}
            {loadingInstructions ? (
              <p className="text-xs text-gray-400">Loading...</p>
            ) : (
              <>
                <textarea
                  value={instructionText}
                  onChange={(e) => setInstructionText(e.target.value)}
                  placeholder="Enter section-specific instructions..."
                  className="flex-1 text-xs text-gray-700 bg-gray-50 border border-gray-200 rounded px-2 py-1.5 resize-none focus:outline-none focus:border-blue-400"
                />
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="mt-2 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
