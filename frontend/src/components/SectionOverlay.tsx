import type { Section } from '../types/job'

const COLORS = [
  [255, 0, 0],
  [0, 150, 0],
  [0, 0, 255],
  [255, 165, 0],
  [128, 0, 128],
  [0, 200, 200],
  [255, 105, 180],
  [139, 69, 19],
  [0, 100, 0],
  [75, 0, 130],
]

interface SectionOverlayProps {
  sections: Section[]
  pageWidth: number
  pageHeight: number
  onSectionClick?: (section: Section) => void
}

export function SectionOverlay({
  sections,
  pageWidth,
  pageHeight,
  onSectionClick,
}: SectionOverlayProps) {
  if (!sections.length || !pageWidth || !pageHeight) return null

  return (
    <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
      {sections.map((section, i) => {
        const [r, g, b] = COLORS[i % COLORS.length]
        const [x0, y0, x1, y1] = section.bbox
        const left = `${(x0 / pageWidth) * 100}%`
        const top = `${(y0 / pageHeight) * 100}%`
        const width = `${((x1 - x0) / pageWidth) * 100}%`
        const height = `${((y1 - y0) / pageHeight) * 100}%`

        return (
          <div
            key={`${section.name}-${i}`}
            className={`absolute pointer-events-auto${onSectionClick ? ' cursor-pointer' : ''}`}
            onClick={() => onSectionClick?.(section)}
            style={{
              left,
              top,
              width,
              height,
              backgroundColor: `rgba(${r}, ${g}, ${b}, 0.12)`,
              border: `2px solid rgba(${r}, ${g}, ${b}, 0.5)`,
              borderRadius: 2,
            }}
            title={`${section.name} (${section.content_type})`}
          >
            <span
              className="absolute -top-5 left-0 text-[10px] font-medium px-1 py-0.5 rounded whitespace-nowrap"
              style={{
                backgroundColor: `rgba(${r}, ${g}, ${b}, 0.7)`,
                color: 'white',
              }}
            >
              {section.name}
            </span>
          </div>
        )
      })}
    </div>
  )
}
