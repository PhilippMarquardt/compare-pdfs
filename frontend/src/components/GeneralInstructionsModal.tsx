import { useCallback, useEffect, useMemo, useState } from 'react'
import { getGeneralInstructions, saveGeneralInstructions } from '../lib/api'

interface GeneralInstructionsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function GeneralInstructionsModal({
  isOpen,
  onClose,
}: GeneralInstructionsModalProps) {
  const [sectionGeneric, setSectionGeneric] = useState('')
  const [globalTemplate, setGlobalTemplate] = useState('')
  const [initialSectionGeneric, setInitialSectionGeneric] = useState('')
  const [initialGlobalTemplate, setInitialGlobalTemplate] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    async function load() {
      setIsLoading(true)
      setError(null)
      try {
        const payload = await getGeneralInstructions()
        if (cancelled) return
        setSectionGeneric(payload.section_generic)
        setGlobalTemplate(payload.global_template)
        setInitialSectionGeneric(payload.section_generic)
        setInitialGlobalTemplate(payload.global_template)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load instructions')
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [isOpen])

  const isDirty = useMemo(() => (
    sectionGeneric !== initialSectionGeneric
    || globalTemplate !== initialGlobalTemplate
  ), [sectionGeneric, initialSectionGeneric, globalTemplate, initialGlobalTemplate])

  const handleSave = useCallback(async () => {
    if (!isDirty) return
    setIsSaving(true)
    setError(null)
    try {
      await saveGeneralInstructions(sectionGeneric, globalTemplate)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save instructions')
    } finally {
      setIsSaving(false)
    }
  }, [isDirty, sectionGeneric, globalTemplate, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-[1px]" onClick={onClose} />
      <div className="relative w-full max-w-5xl rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">General Analysis Instructions</h2>
          <p className="mt-1 text-sm text-slate-500">
            Update shared instructions used across section-level and global analysis.
          </p>
        </div>

        <div className="grid gap-5 p-6 lg:grid-cols-2">
          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-800">Section Generic Instructions</h3>
            <p className="text-xs text-slate-500">
              Use one checklist bullet per line (example: <code>- Verify ...</code>) for <code>section_instructions.md</code> under <code>## Generic</code>.
            </p>
            <textarea
              value={sectionGeneric}
              onChange={(e) => setSectionGeneric(e.target.value)}
              className="h-64 w-full resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              spellCheck={false}
              disabled={isLoading || isSaving}
            />
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-800">Global Analysis Template</h3>
            <p className="text-xs text-slate-500">
              Use <code>### Check Name</code> headings, and only bullet checklist items under each heading. One bullet equals one model check.
            </p>
            <textarea
              value={globalTemplate}
              onChange={(e) => setGlobalTemplate(e.target.value)}
              className="h-64 w-full resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              spellCheck={false}
              disabled={isLoading || isSaving}
            />
          </section>
        </div>

        {error && (
          <p className="px-6 pb-2 text-sm text-red-600">{error}</p>
        )}

        <div className="flex items-center justify-end gap-3 border-t border-slate-200 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            disabled={isSaving}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isLoading || isSaving || !isDirty}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isSaving ? 'Saving...' : 'Save Instructions'}
          </button>
        </div>
      </div>
    </div>
  )
}
