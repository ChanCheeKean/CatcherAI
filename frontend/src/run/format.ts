import type { Money, Verdict } from '../api/types'

export const verdictLabel: Record<Verdict, string> = {
  accepted: 'Accepted',
  partially_accepted: 'Partially accepted',
  rejected: 'Rejected',
  not_a_dispute: 'Not a dispute',
}

/** Tailwind colour classes per verdict; the colours mean the same thing everywhere. */
export const verdictTone: Record<Verdict, { text: string; band: string }> = {
  accepted: { text: 'text-accepted', band: 'border-accepted' },
  partially_accepted: { text: 'text-partial', band: 'border-partial' },
  rejected: { text: 'text-rejected', band: 'border-rejected' },
  not_a_dispute: { text: 'text-informed', band: 'border-informed' },
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export const money = (value: Money) => usd.format(Number(value))

export const words = (snake: string) => snake.replaceAll('_', ' ')
