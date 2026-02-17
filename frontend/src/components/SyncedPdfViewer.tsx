import { useRef, useCallback, useEffect, useLayoutEffect } from 'react'
import { PdfViewer } from './PdfViewer'
import type { PageAnalysis, Section } from '../types/job'

interface SyncedPdfViewerProps {
  referenceUrl: string
  testUrl: string
  pageNumber: number
  zoom?: number
  onZoomChange?: (zoom: number) => void
  onPageLoaded?: (totalPages: number) => void
  referenceSections?: PageAnalysis | null
  testSections?: PageAnalysis | null
  onSectionClick?: (section: Section) => void
}

type ViewerSide = 'left' | 'right'

interface PaneAnchor {
  hasCanvas: boolean
  canvasOriginX: number
  canvasOriginY: number
  localX: number
  localY: number
  fallbackContentX: number
  fallbackContentY: number
  viewportX: number
  viewportY: number
}

interface PendingZoom {
  targetZoom: number
  ratio: number
  left: PaneAnchor
  right: PaneAnchor
  debugId?: number
  debug?: {
    side: ViewerSide
    deltaY: number
    currentZoom: number
    targetZoom: number
    factor: number
    sourceX: number
    sourceY: number
    otherX: number
    otherY: number
  }
}

interface PendingWheel {
  side: ViewerSide
  clientX: number
  clientY: number
  deltaY: number
}

const MIN_ZOOM = 0.5
const MAX_ZOOM = 5
const ZOOM_SENSITIVITY = 0.0012
const MIN_WHEEL_FACTOR = 0.8
const MAX_WHEEL_FACTOR = 1.25
const DEBUG_ZOOM = false

export function SyncedPdfViewer({
  referenceUrl,
  testUrl,
  pageNumber,
  zoom = 1,
  onZoomChange,
  onPageLoaded,
  referenceSections,
  testSections,
  onSectionClick,
}: SyncedPdfViewerProps) {
  const rootRef = useRef<HTMLDivElement>(null)
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const onZoomChangeRef = useRef(onZoomChange)
  onZoomChangeRef.current = onZoomChange
  const zoomRef = useRef(zoom)
  const syncingRef = useRef(false)
  const zoomInFlightRef = useRef(false)
  const pendingZoomRef = useRef<PendingZoom | null>(null)
  const pendingWheelRef = useRef<PendingWheel | null>(null)
  const processWheelRef = useRef<() => void>(() => {})
  const releaseSyncRafRef = useRef<number | null>(null)
  const wheelRafRef = useRef<number | null>(null)
  const debugCounterRef = useRef(0)
  zoomRef.current = zoom

  const beginSync = useCallback(() => {
    syncingRef.current = true
    if (releaseSyncRafRef.current !== null) {
      window.cancelAnimationFrame(releaseSyncRafRef.current)
    }
    releaseSyncRafRef.current = window.requestAnimationFrame(() => {
      syncingRef.current = false
      releaseSyncRafRef.current = null
    })
  }, [])

  const syncScrollTo = useCallback((target: HTMLDivElement | null, top: number, left: number) => {
    if (!target) return
    target.scrollTop = top
    target.scrollLeft = left
  }, [])

  const handleLeftScroll = useCallback(
    (scrollTop: number, scrollLeft: number) => {
      if (syncingRef.current) return
      beginSync()
      syncScrollTo(rightRef.current, scrollTop, scrollLeft)
    },
    [beginSync, syncScrollTo],
  )

  const handleRightScroll = useCallback(
    (scrollTop: number, scrollLeft: number) => {
      if (syncingRef.current) return
      beginSync()
      syncScrollTo(leftRef.current, scrollTop, scrollLeft)
    },
    [beginSync, syncScrollTo],
  )

  const scheduleWheelProcess = useCallback(() => {
    if (wheelRafRef.current !== null) return
    wheelRafRef.current = window.requestAnimationFrame(() => {
      wheelRafRef.current = null
      processWheelRef.current()
    })
  }, [])

  useLayoutEffect(() => {
    const pending = pendingZoomRef.current
    if (!pending) return
    if (Math.abs(pending.targetZoom - zoom) > 0.0001) return
    pendingZoomRef.current = null

    const applyZoomAnchor = (
      pane: ViewerSide,
      container: HTMLDivElement | null,
      anchor: PaneAnchor,
    ) => {
      if (!container) return { pane, missing: true }

      const nextLeft = anchor.hasCanvas
        ? anchor.canvasOriginX + anchor.localX * pending.ratio - anchor.viewportX
        : anchor.fallbackContentX * pending.ratio - anchor.viewportX
      const nextTop = anchor.hasCanvas
        ? anchor.canvasOriginY + anchor.localY * pending.ratio - anchor.viewportY
        : anchor.fallbackContentY * pending.ratio - anchor.viewportY

      const maxLeft = Math.max(0, container.scrollWidth - container.clientWidth)
      const maxTop = Math.max(0, container.scrollHeight - container.clientHeight)

      container.scrollLeft = Math.min(Math.max(nextLeft, 0), maxLeft)
      container.scrollTop = Math.min(Math.max(nextTop, 0), maxTop)

      const expectedContentX = anchor.hasCanvas
        ? anchor.canvasOriginX + anchor.localX * pending.ratio
        : anchor.fallbackContentX * pending.ratio
      const expectedContentY = anchor.hasCanvas
        ? anchor.canvasOriginY + anchor.localY * pending.ratio
        : anchor.fallbackContentY * pending.ratio
      const actualContentX = container.scrollLeft + anchor.viewportX
      const actualContentY = container.scrollTop + anchor.viewportY

      return {
        pane,
        hasCanvas: anchor.hasCanvas,
        canvasOriginX: anchor.canvasOriginX,
        canvasOriginY: anchor.canvasOriginY,
        localX: anchor.localX,
        localY: anchor.localY,
        expectedLeft: nextLeft,
        expectedTop: nextTop,
        appliedLeft: container.scrollLeft,
        appliedTop: container.scrollTop,
        clampedX: container.scrollLeft - nextLeft,
        clampedY: container.scrollTop - nextTop,
        errX: actualContentX - expectedContentX,
        errY: actualContentY - expectedContentY,
        maxLeft,
        maxTop,
      }
    }

    beginSync()
    const leftMetrics = applyZoomAnchor('left', leftRef.current, pending.left)
    const rightMetrics = applyZoomAnchor('right', rightRef.current, pending.right)
    zoomInFlightRef.current = false
    if (pendingWheelRef.current) {
      scheduleWheelProcess()
    }
    if (DEBUG_ZOOM) {
      console.log(`[zoom-debug #${pending.debugId ?? '?'}] apply`, {
        zoom,
        ratio: pending.ratio,
        debug: pending.debug,
        left: leftMetrics,
        right: rightMetrics,
      })
    }
  }, [zoom, beginSync, scheduleWheelProcess])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return

    processWheelRef.current = () => {
      if (zoomInFlightRef.current) return

      const pendingWheel = pendingWheelRef.current
      pendingWheelRef.current = null
      if (!pendingWheel || !onZoomChangeRef.current) return

      const left = leftRef.current
      const right = rightRef.current
      if (!left || !right) return

      const side = pendingWheel.side
      const source = side === 'left' ? left : right
      const other = side === 'left' ? right : left
      const sourceRect = source.getBoundingClientRect()

      const sourceX = Math.min(
        Math.max(pendingWheel.clientX - sourceRect.left, 0),
        source.clientWidth,
      )
      const sourceY = Math.min(
        Math.max(pendingWheel.clientY - sourceRect.top, 0),
        source.clientHeight,
      )
      const otherX =
        source.clientWidth > 0
          ? (sourceX / source.clientWidth) * other.clientWidth
          : other.clientWidth / 2
      const otherY =
        source.clientHeight > 0
          ? (sourceY / source.clientHeight) * other.clientHeight
          : other.clientHeight / 2

      const currentZoom = zoomRef.current
      const wheelFactor = Math.exp(-pendingWheel.deltaY * ZOOM_SENSITIVITY)
      const factor = Math.min(Math.max(wheelFactor, MIN_WHEEL_FACTOR), MAX_WHEEL_FACTOR)
      const targetZoom = Math.min(Math.max(currentZoom * factor, MIN_ZOOM), MAX_ZOOM)
      if (targetZoom === currentZoom) return
      const debugId = ++debugCounterRef.current

      const ratio = targetZoom / currentZoom
      const capturePaneAnchor = (
        container: HTMLDivElement,
        viewportX: number,
        viewportY: number,
      ): PaneAnchor => {
        const fallbackContentX = container.scrollLeft + viewportX
        const fallbackContentY = container.scrollTop + viewportY
        const containerRect = container.getBoundingClientRect()
        const canvas = container.querySelector('canvas')
        if (!canvas) {
          return {
            hasCanvas: false,
            canvasOriginX: 0,
            canvasOriginY: 0,
            localX: 0,
            localY: 0,
            fallbackContentX,
            fallbackContentY,
            viewportX,
            viewportY,
          }
        }

        const canvasRect = canvas.getBoundingClientRect()
        const canvasOriginX = container.scrollLeft + (canvasRect.left - containerRect.left)
        const canvasOriginY = container.scrollTop + (canvasRect.top - containerRect.top)
        const localX = Math.max(0, Math.min(fallbackContentX - canvasOriginX, canvasRect.width))
        const localY = Math.max(0, Math.min(fallbackContentY - canvasOriginY, canvasRect.height))

        return {
          hasCanvas: true,
          canvasOriginX,
          canvasOriginY,
          localX,
          localY,
          fallbackContentX,
          fallbackContentY,
          viewportX,
          viewportY,
        }
      }

      const sourceAnchor = capturePaneAnchor(source, sourceX, sourceY)
      const otherAnchor = capturePaneAnchor(other, otherX, otherY)

      pendingZoomRef.current =
        side === 'left'
          ? {
              targetZoom,
              ratio,
              left: sourceAnchor,
              right: otherAnchor,
              debugId,
              debug: {
                side,
                deltaY: pendingWheel.deltaY,
                currentZoom,
                targetZoom,
                factor,
                sourceX,
                sourceY,
                otherX,
                otherY,
              },
            }
          : {
              targetZoom,
              ratio,
              left: otherAnchor,
              right: sourceAnchor,
              debugId,
              debug: {
                side,
                deltaY: pendingWheel.deltaY,
                currentZoom,
                targetZoom,
                factor,
                sourceX,
                sourceY,
                otherX,
                otherY,
              },
            }

      if (DEBUG_ZOOM) {
        console.log(`[zoom-debug #${debugId}] wheel-batch`, {
          side,
          deltaY: pendingWheel.deltaY,
          currentZoom,
          targetZoom,
          ratio,
          factor,
          sourceX,
          sourceY,
          otherX,
          otherY,
          sourceScrollLeft: source.scrollLeft,
          sourceScrollTop: source.scrollTop,
          otherScrollLeft: other.scrollLeft,
          otherScrollTop: other.scrollTop,
        })
      }

      zoomInFlightRef.current = true
      zoomRef.current = targetZoom
      onZoomChangeRef.current(targetZoom)
    }

    function handleWheel(e: WheelEvent) {
      if (!onZoomChangeRef.current) return

      const target = e.target as Node | null
      const left = leftRef.current
      const right = rightRef.current
      if (!left || !right || !target) return

      let side: ViewerSide | null = null
      let source: HTMLDivElement | null = null
      if (left.contains(target)) {
        side = 'left'
        source = left
      } else if (right.contains(target)) {
        side = 'right'
        source = right
      }
      if (!side || !source) return

      e.preventDefault()

      let deltaY = e.deltaY
      if (e.deltaMode === WheelEvent.DOM_DELTA_LINE) deltaY *= 16
      if (e.deltaMode === WheelEvent.DOM_DELTA_PAGE) deltaY *= source.clientHeight

      const current = pendingWheelRef.current
      if (current && current.side === side) {
        pendingWheelRef.current = {
          side,
          clientX: e.clientX,
          clientY: e.clientY,
          deltaY: current.deltaY + deltaY,
        }
      } else {
        pendingWheelRef.current = {
          side,
          clientX: e.clientX,
          clientY: e.clientY,
          deltaY,
        }
      }

      scheduleWheelProcess()
    }

    root.addEventListener('wheel', handleWheel, { passive: false })
    return () => root.removeEventListener('wheel', handleWheel)
  }, [scheduleWheelProcess])

  // Center scrolls on page/URL change once the canvas has rendered
  useEffect(() => {
    let active = true
    let raf: number
    let attempts = 0

    function tryCenter() {
      if (!active) return
      attempts++
      const left = leftRef.current
      const right = rightRef.current
      if (!left || !right) return

      const canvas = left.querySelector('canvas') as HTMLCanvasElement | null
      if (!canvas || !canvas.style.width) {
        if (attempts < 120) raf = requestAnimationFrame(tryCenter)
        return
      }

      beginSync()
      for (const el of [left, right]) {
        el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2
        el.scrollTop = (el.scrollHeight - el.clientHeight) / 2
      }
    }

    raf = requestAnimationFrame(tryCenter)
    return () => { active = false; cancelAnimationFrame(raf) }
  }, [pageNumber, referenceUrl, testUrl, beginSync])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return

    let panning = false
    let startX = 0
    let startY = 0
    let startScrollLeft = 0
    let startScrollTop = 0
    let panTarget: HTMLDivElement | null = null

    function handlePointerDown(e: PointerEvent) {
      if (e.button !== 1) return
      e.preventDefault()

      const target = e.target as Node | null
      const left = leftRef.current
      const right = rightRef.current
      if (!left || !right || !target) return

      let container: HTMLDivElement | null = null
      if (left.contains(target)) container = left
      else if (right.contains(target)) container = right
      if (!container) return

      panning = true
      panTarget = container
      startX = e.clientX
      startY = e.clientY
      startScrollLeft = container.scrollLeft
      startScrollTop = container.scrollTop
      root.style.cursor = 'grabbing'
      root.setPointerCapture(e.pointerId)
    }

    function handlePointerMove(e: PointerEvent) {
      if (!panning || !panTarget) return
      panTarget.scrollLeft = startScrollLeft - (e.clientX - startX)
      panTarget.scrollTop = startScrollTop - (e.clientY - startY)
    }

    function handlePointerUp(e: PointerEvent) {
      if (!panning) return
      panning = false
      panTarget = null
      root.style.cursor = ''
      root.releasePointerCapture(e.pointerId)
    }

    function handleMouseDown(e: MouseEvent) {
      if (e.button === 1) e.preventDefault()
    }

    root.addEventListener('pointerdown', handlePointerDown)
    root.addEventListener('pointermove', handlePointerMove)
    root.addEventListener('pointerup', handlePointerUp)
    root.addEventListener('mousedown', handleMouseDown)

    return () => {
      root.removeEventListener('pointerdown', handlePointerDown)
      root.removeEventListener('pointermove', handlePointerMove)
      root.removeEventListener('pointerup', handlePointerUp)
      root.removeEventListener('mousedown', handleMouseDown)
    }
  }, [])

  useEffect(() => {
    return () => {
      if (releaseSyncRafRef.current !== null) {
        window.cancelAnimationFrame(releaseSyncRafRef.current)
      }
      if (wheelRafRef.current !== null) {
        window.cancelAnimationFrame(wheelRafRef.current)
      }
    }
  }, [])

  return (
    <div ref={rootRef} className="flex flex-1 min-h-0">
      <PdfViewer
        url={referenceUrl}
        pageNumber={pageNumber}
        label="Reference"
        zoom={zoom}
        onPageLoaded={onPageLoaded}
        scrollRef={leftRef}
        onScroll={handleLeftScroll}
        sections={referenceSections}
        style={{ flex: 1 }}
        onSectionClick={onSectionClick}
      />
      <div className="w-px bg-gray-200 shrink-0" />
      <PdfViewer
        url={testUrl}
        pageNumber={pageNumber}
        label="Test"
        zoom={zoom}
        scrollRef={rightRef}
        onScroll={handleRightScroll}
        sections={testSections}
        style={{ flex: 1 }}
        onSectionClick={onSectionClick}
      />
    </div>
  )
}
