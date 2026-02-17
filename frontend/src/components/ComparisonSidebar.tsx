import type { JobMetadata } from '../types/job'
import { REPORT_TYPE_LABELS } from '../types/job'
import { PairListItem } from './PairListItem'

interface ComparisonSidebarProps {
  job: JobMetadata
  selectedPairIndex: number
  onSelectPair: (index: number) => void
}

export function ComparisonSidebar({
  job,
  selectedPairIndex,
  onSelectPair,
}: ComparisonSidebarProps) {
  return (
    <aside className="h-full bg-white flex flex-col overflow-hidden">
      <div className="px-3 py-3 border-b border-gray-200">
        <p className="text-xs text-gray-500 uppercase tracking-wide">
          {REPORT_TYPE_LABELS[job.report_type] ?? job.report_type}
        </p>
        <p className="text-xs text-gray-400 mt-1">
          {job.pairs.length} pair{job.pairs.length !== 1 ? 's' : ''}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {job.pairs.map((pair, index) => (
          <PairListItem
            key={pair.pair_id}
            pair={pair}
            isSelected={index === selectedPairIndex}
            onClick={() => onSelectPair(index)}
          />
        ))}

        {job.unmatched_reference.length > 0 && (
          <div className="px-3 py-2 border-t border-gray-100">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Unmatched Reference
            </p>
            {job.unmatched_reference.map((name) => (
              <p key={name} className="text-sm text-gray-500 py-0.5 truncate">
                {name}
              </p>
            ))}
          </div>
        )}

        {job.unmatched_test.length > 0 && (
          <div className="px-3 py-2 border-t border-gray-100">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Unmatched Test
            </p>
            {job.unmatched_test.map((name) => (
              <p key={name} className="text-sm text-gray-500 py-0.5 truncate">
                {name}
              </p>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
