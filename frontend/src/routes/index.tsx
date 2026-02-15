import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { NewComparisonModal } from '../components/NewComparisonModal'

export const Route = createFileRoute('/')({
  component: HomeComponent,
})

function HomeComponent() {
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div className="flex-1 p-6">
      <div className="max-w-5xl">
        <button
          onClick={() => setModalOpen(true)}
          className="px-5 py-2.5 text-sm font-medium text-white bg-gray-900 rounded-md hover:bg-gray-800 transition-colors"
        >
          New Comparison
        </button>
      </div>
      <NewComparisonModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}
