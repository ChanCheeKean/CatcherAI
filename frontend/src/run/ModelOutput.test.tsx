import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ModelOutput } from './ModelOutput'

describe('ModelOutput hypotheses', () => {
  it("shows the adjudicator's claim, verdict, reasoning and evidence, not only the verdict", () => {
    render(
      <ModelOutput
        schema="CaseReport"
        output={{
          hypotheses: [
            {
              hypothesis: 'The Offer was added to another Card',
              status: 'accepted',
              why: 'The Offer is enrolled on the Platinum Card.',
              evidence: [{ claim: 'Enrolled on CRD-C01', node_ids: ['CRD-C01'], edge_ids: ['E-0507358'] }],
            },
          ],
        }}
      />,
    )
    expect(screen.getByText('The Offer was added to another Card')).toBeTruthy()
    expect(screen.getByText('accepted')).toBeTruthy()
    expect(screen.getByText('The Offer is enrolled on the Platinum Card.')).toBeTruthy()
    expect(screen.getByText('E-0507358')).toBeTruthy()
  })

  it('still shows a working hypothesis with its support and against lines', () => {
    render(
      <ModelOutput
        schema="Triage"
        output={{ hypotheses: [{ label: 'Descriptor confusion', status: 'plausible', support: ['Merchant is known'], against: [] }] }}
      />,
    )
    expect(screen.getByText('Descriptor confusion')).toBeTruthy()
    expect(screen.getByText('Merchant is known')).toBeTruthy()
  })
})
