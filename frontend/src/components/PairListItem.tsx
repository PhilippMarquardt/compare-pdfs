import type { PdfPair } from '../types/job'
import { StatusBadge } from './StatusBadge'

interface PairListItemProps {
  pair: PdfPair
  isSelected: boolean
  onClick: () => void
}

export function PairListItem({ pair, isSelected, onClick }: PairListItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 flex items-center justify-between gap-2 transition-colors ${
        isSelected
          ? 'bg-blue-50 border-l-2 border-blue-500'
          : 'border-l-2 border-transparent hover:bg-gray-50'
      }`}
    >
      <span className="text-sm text-gray-800 truncate">{pair.filename}</span>
      <StatusBadge status={pair.status} />
    </button>
  )
}
