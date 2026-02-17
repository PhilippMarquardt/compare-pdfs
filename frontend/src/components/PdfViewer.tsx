import { useState, useEffect, useRef, useCallback } from 'react'
import type { RefObject } from 'react'
import { PdfCanvas } from './PdfCanvas'
import { SectionOverlay } from './SectionOverlay'
import type { PageAnalysis, Section } from '../types/job'

interface PdfViewerProps {
  url: string
  pageNumber: number
  label: string
  zoom?: number
  onPageLoaded?: (totalPages: number) => void
  scrollRef?: RefObject<HTMLDivElement | null>
  onScroll?: (scrollTop: number, scrollLeft: number) => void
  sections?: PageAnalysis | null
  style?: React.CSSProperties
  onSectionClick?: (section: Section) => void
}

export function PdfViewer({
  url,
  pageNumber,
  label,
  zoom = 1,
  onPageLoaded,
  scrollRef,
  onScroll,
  sections,
  style,
  onSectionClick,
}: PdfViewerProps) {
  const measureRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })
  const [baseSize, setBaseSize] = useState<{ width: number; height: number } | null>(null)

  useEffect(() => {
    const el = measureRef.current
    if (!el) return
    let timeoutId: number
    let initialized = false
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (!initialized) {
        initialized = true
        setContainerSize({ width, height })
      } else {
        clearTimeout(timeoutId)
        timeoutId = window.setTimeout(() => {
          setContainerSize({ width, height })
        }, 150)
      }
    })
    observer.observe(el)
    return () => {
      clearTimeout(timeoutId)
      observer.disconnect()
    }
  }, [])

  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const el = e.currentTarget
      onScroll?.(el.scrollTop, el.scrollLeft)
    },
    [onScroll],
  )

  return (
    <div className="flex flex-col min-w-0 min-h-0" style={style}>
      <div className="h-8 flex items-center px-3 border-b border-gray-200 bg-gray-50 shrink-0">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          {label}
        </span>
      </div>
      <div ref={measureRef} className="flex-1 min-h-0 relative">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="absolute inset-0 overflow-auto bg-gray-100 scrollbar-hidden"
        >
          <div
            style={{
              paddingTop: containerSize.height,
              paddingBottom: containerSize.height,
              paddingLeft: containerSize.width,
              paddingRight: containerSize.width,
              width: 'fit-content',
            }}
          >
            {containerSize.width > 0 && containerSize.height > 0 && (
              <PdfCanvas
                url={url}
                pageNumber={pageNumber}
                zoom={zoom}
                fitWidth={containerSize.width - 32}
                fitHeight={containerSize.height - 32}
                onPageLoaded={onPageLoaded}
                onBaseSize={setBaseSize}
                overlay={
                  sections && baseSize ? (
                    <SectionOverlay
                      sections={sections.sections}
                      pageWidth={sections.page_width}
                      pageHeight={sections.page_height}
                      onSectionClick={onSectionClick}
                    />
                  ) : null
                }
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
