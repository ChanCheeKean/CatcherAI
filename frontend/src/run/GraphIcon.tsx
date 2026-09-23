import { useRunPanels } from './RunContext'

const shapes = {
  person: <><circle cx="10" cy="7" r="3" /><path d="M4 16c0-3 3-5 6-5s6 2 6 5" /></>,
  swap: <path d="M4 7h11l-3-3M16 13H5l3 3" />,
  scroll: <path d="M6 3h9v11a3 3 0 0 1-3 3H5a2 2 0 0 0 2-2V3M6 3a2 2 0 0 0-2 2v1h2M9 7h4M9 10h4" />,
  flag: <path d="M5 17V3M5 4h10l-2 3.5 2 3.5H5" />,
}

export function Icon({ label, size = 18 }: { label: string; size?: number }) {
  const { graphModel } = useRunPanels()
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {shapes[graphModel.labelStyle(label).icon]}
    </svg>
  )
}
