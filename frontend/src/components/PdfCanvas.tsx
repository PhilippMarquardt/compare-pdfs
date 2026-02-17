import { useEffect, useLayoutEffect, useRef, useState, useCallback } from 'react'
import type { ReactNode } from 'react'
import { pdfjsLib } from '../lib/pdf-worker'
import type { PDFDocumentProxy } from 'pdfjs-dist'

interface PdfCanvasProps {
  url: string
  pageNumber: number
  zoom?: number
  fitWidth: number
  fitHeight: number
  onPageLoaded?: (totalPages: number) => void
  onBaseSize?: (size: { width: number; height: number }) => void
  overlay?: ReactNode
}

export function PdfCanvas({
  url,
  pageNumber,
  zoom = 1,
  fitWidth,
  fitHeight,
  onPageLoaded,
  onBaseSize,
  overlay,
}: PdfCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const docRef = useRef<{ url: string; doc: PDFDocumentProxy } | null>(null)
  const renderTaskRef = useRef<ReturnType<
    Awaited<ReturnType<PDFDocumentProxy['getPage']>>['render']
  > | null>(null)
  const renderSeqRef = useRef(0)
  const zoomTimerRef = useRef<number>(0)
  const lastNotifiedUrlRef = useRef<string>('')
  const [baseSize, setBaseSize] = useState<{ width: number; height: number } | null>(null)
  const [renderZoom, setRenderZoom] = useState(zoom)

  // Debounce zoom for re-rendering — CSS zoom is instant, buffer re-render follows after settling
  useEffect(() => {
    clearTimeout(zoomTimerRef.current)
    zoomTimerRef.current = window.setTimeout(() => {
      setRenderZoom(zoom)
    }, 200)
    return () => clearTimeout(zoomTimerRef.current)
  }, [zoom])

  const getDoc = useCallback(
    async (pdfUrl: string): Promise<PDFDocumentProxy> => {
      if (docRef.current?.url === pdfUrl) {
        return docRef.current.doc
      }
      const doc = await pdfjsLib.getDocument(pdfUrl).promise
      docRef.current = { url: pdfUrl, doc }
      return doc
    },
    [],
  )

  useLayoutEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    if (!baseSize) {
      canvas.style.width = ''
      canvas.style.height = ''
      return
    }
    canvas.style.width = `${Math.floor(baseSize.width * zoom)}px`
    canvas.style.height = `${Math.floor(baseSize.height * zoom)}px`
  }, [baseSize, zoom])

  useEffect(() => {
    let cancelled = false
    const renderSeq = ++renderSeqRef.current

    async function renderPage() {
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel()
        renderTaskRef.current = null
      }

      const canvas = canvasRef.current
      if (!canvas || fitWidth <= 0 || fitHeight <= 0) return

      try {
        const doc = await getDoc(url)
        if (cancelled) return

        if (lastNotifiedUrlRef.current !== url) {
          lastNotifiedUrlRef.current = url
          onPageLoaded?.(doc.numPages)
        }

        const page = await doc.getPage(pageNumber)
        if (cancelled) return

        const pageViewport = page.getViewport({ scale: 1 })
        const fitScale = Math.min(
          fitWidth / pageViewport.width,
          fitHeight / pageViewport.height,
        )

        const cssWidth = pageViewport.width * fitScale
        const cssHeight = pageViewport.height * fitScale
        setBaseSize({ width: cssWidth, height: cssHeight })
        onBaseSize?.({ width: cssWidth, height: cssHeight })

        const dpr = window.devicePixelRatio || 1
        const renderScale = fitScale * (renderZoom + 1) * dpr
        const renderViewport = page.getViewport({ scale: renderScale })

        const MAX_CANVAS_AREA = 100_000_000
        const rawArea = renderViewport.width * renderViewport.height
        const finalViewport = rawArea > MAX_CANVAS_AREA
          ? page.getViewport({ scale: renderScale * Math.sqrt(MAX_CANVAS_AREA / rawArea) })
          : renderViewport

        const renderCanvas = document.createElement('canvas')
        renderCanvas.width = finalViewport.width
        renderCanvas.height = finalViewport.height
        const renderCtx = renderCanvas.getContext('2d')
        if (!renderCtx) return

        const renderTask = page.render({
          canvas: renderCanvas,
          canvasContext: renderCtx,
          viewport: finalViewport,
        })
        renderTaskRef.current = renderTask
        await renderTask.promise
        if (cancelled || renderSeqRef.current !== renderSeq) return

        const targetCanvas = canvasRef.current
        if (!targetCanvas) return

        targetCanvas.width = renderCanvas.width
        targetCanvas.height = renderCanvas.height
        const targetCtx = targetCanvas.getContext('2d')
        if (!targetCtx) return
        targetCtx.setTransform(1, 0, 0, 1, 0, 0)
        targetCtx.clearRect(0, 0, targetCanvas.width, targetCanvas.height)
        targetCtx.drawImage(renderCanvas, 0, 0)
      } catch (err: unknown) {
        if (err instanceof Error && err.message === 'Rendering cancelled') return
        if (!cancelled) {
          console.error('PDF render error:', err)
        }
      }
    }

    renderPage()

    return () => {
      cancelled = true
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel()
        renderTaskRef.current = null
      }
    }
  }, [url, pageNumber, renderZoom, fitWidth, fitHeight, getDoc, onPageLoaded])

  useEffect(() => {
    return () => {
      if (docRef.current) {
        docRef.current.doc.destroy()
        docRef.current = null
      }
    }
  }, [])

  return (
    <div className="relative inline-block">
      <canvas ref={canvasRef} className="block bg-white" />
      {overlay}
    </div>
  )
}
