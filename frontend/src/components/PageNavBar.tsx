interface PageNavBarProps {
  filename: string
  currentPage: number
  totalPages: number
  zoom: number
  onPrev: () => void
  onNext: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomReset: () => void
}

export function PageNavBar({
  filename,
  currentPage,
  totalPages,
  zoom,
  onPrev,
  onNext,
  onZoomIn,
  onZoomOut,
  onZoomReset,
}: PageNavBarProps) {
  return (
    <div className="flex items-center justify-between h-10 px-4 border-b border-gray-200 bg-white shrink-0">
      <span className="text-sm font-medium text-gray-700 truncate">
        {filename}
      </span>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <button
            onClick={onZoomOut}
            className="px-2 py-0.5 text-sm text-gray-600 hover:text-gray-900"
            title="Zoom out"
          >
            &minus;
          </button>
          <button
            onClick={onZoomReset}
            className="px-2 py-0.5 text-xs text-gray-500 hover:text-gray-900 tabular-nums min-w-[3.5rem] text-center"
            title="Reset zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            onClick={onZoomIn}
            className="px-2 py-0.5 text-sm text-gray-600 hover:text-gray-900"
            title="Zoom in"
          >
            +
          </button>
        </div>
        <div className="w-px h-4 bg-gray-200" />
        <div className="flex items-center gap-2">
          <button
            onClick={onPrev}
            disabled={currentPage <= 1}
            className="px-2 py-0.5 text-sm text-gray-600 hover:text-gray-900 disabled:text-gray-300 disabled:cursor-not-allowed"
          >
            &larr;
          </button>
          <span className="text-sm text-gray-600 tabular-nums">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={onNext}
            disabled={currentPage >= totalPages}
            className="px-2 py-0.5 text-sm text-gray-600 hover:text-gray-900 disabled:text-gray-300 disabled:cursor-not-allowed"
          >
            &rarr;
          </button>
        </div>
      </div>
    </div>
  )
}
