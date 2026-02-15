import { Link } from '@tanstack/react-router'

export function AppNavBar() {
  return (
    <nav className="flex items-center h-12 px-4 border-b border-gray-200 bg-white shrink-0">
      <Link to="/" className="text-base font-semibold text-gray-900">
        PDF Compare
      </Link>
    </nav>
  )
}
