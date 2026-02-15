import type { PairStatus } from '../types/job'

const STATUS_STYLES: Record<PairStatus, string> = {
  pending: 'bg-gray-100 text-gray-600',
  running: 'bg-blue-100 text-blue-700',
  ok: 'bg-green-100 text-green-700',
  needs_attention: 'bg-yellow-100 text-yellow-700',
  broken: 'bg-red-100 text-red-700',
}

const STATUS_LABELS: Record<PairStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  ok: 'OK',
  needs_attention: 'Needs Attention',
  broken: 'Broken',
}

interface StatusBadgeProps {
  status: PairStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  )
}
