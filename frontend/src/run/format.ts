import type { DisputeCategory, Money, Verdict } from '../api/types'

export const verdictLabel: Record<Verdict, string> = {
  accepted: 'Accepted',
  partially_accepted: 'Partially accepted',
  rejected: 'Rejected',
  goodwill_credit: 'Goodwill credit',
  not_a_dispute: 'Not a dispute',
  fraud_referral: 'Fraud referral',
}

/** Tailwind colour classes per verdict; the colours mean the same thing everywhere. */
export const verdictTone: Record<Verdict, { text: string; band: string }> = {
  accepted: { text: 'text-accepted', band: 'border-accepted' },
  partially_accepted: { text: 'text-partial', band: 'border-partial' },
  rejected: { text: 'text-rejected', band: 'border-rejected' },
  goodwill_credit: { text: 'text-partial', band: 'border-partial' },
  not_a_dispute: { text: 'text-informed', band: 'border-informed' },
  fraud_referral: { text: 'text-informed', band: 'border-informed' },
}

export const categoryLabel: Record<DisputeCategory, string> = {
  NKN: 'No Knowledge', RET: 'Returned or Refused', CNC: 'Cancelled',
  CNR: 'Continuity or Recurring Billing', DMG: 'Damaged Merchandise',
  DSS: 'Dissatisfied with Service', DUP: 'Duplicate or Multiple Transactions',
  NRC: 'Not Received', OVR: 'Overcharged', PDD: 'Paid by Other Means',
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export const money = (value: Money) => usd.format(Number(value))

/** snake_case or CamelCase as separate words. */
export const words = (name: string) => name.replaceAll('_', ' ').replace(/([a-z])([A-Z])/g, '$1 $2')
