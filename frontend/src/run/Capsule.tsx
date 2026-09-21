import type { CSSProperties, ReactNode } from 'react'

/** What a section holds; each kind has its own colour token (`--color-<tone>`) in index.css. */
export type Tone = 'model' | 'reason' | 'next' | 'plan' | 'hypo' | 'facts' | 'tools' | 'input'

interface CapsuleProps {
  tone: Tone
  title: ReactNode
  /** A short pill at the right of the title: a count, a schema name. */
  pill?: ReactNode
  open?: boolean
  /** The model's own answer gets a solid header. */
  strong?: boolean
  children: ReactNode
}

/** A collapsible, colour-coded section of the inspector. */
export function Capsule({ tone, title, pill, open = false, strong = false, children }: CapsuleProps) {
  return (
    <details
      open={open}
      className={strong ? 'capsule capsule-strong' : 'capsule'}
      style={{ '--tone': `var(--color-${tone})` } as CSSProperties}
    >
      <summary>
        {title}
        {pill != null && <span className="capsule-pill">{pill}</span>}
      </summary>
      <div className="capsule-body">{children}</div>
    </details>
  )
}

/** Small read-only badge for visit metadata (turn, time, tokens). */
export function Pill({ children }: { children: ReactNode }) {
  return <span className="rounded-full border bg-vellum px-2 py-px text-xs text-graphite">{children}</span>
}
